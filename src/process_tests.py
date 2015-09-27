from __future__ import print_function

import atexit
import errno
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from functools import partial
from logging import getLogger

try:
    import fcntl
except ImportError:
    fcntl = False
try:
    import Queue
except ImportError:
    import queue as Queue
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
try:
    import unittest2 as unittest
except ImportError:
    import unittest

logger = getLogger(__name__)

BAD_FD_ERRORS = tuple(getattr(errno, name) for name in ['EBADF', 'EBADFD', 'ENOTCONN'] if hasattr(errno, name))
PY3 = sys.version_info[0] == 3


class BufferingBase(object):
    BUFFSIZE = 8192
    ENCODING = "utf8"

    def __init__(self, fh):
        self.buff = StringIO()
        fd = fh.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        self.fd = fd

    def read(self):
        """
        Read any available data fd. Does NOT block.
        """
        try:
            while 1:
                data = os.read(self.fd, self.BUFFSIZE)
                if not data:
                    break
                try:
                    data = data.decode(self.ENCODING)
                except Exception:
                    logger.exception("Failed to decode %r" % data)
                    raise

                self.buff.write(data)
        except OSError as e:
            if e.errno not in (
                    errno.EAGAIN, errno.EWOULDBLOCK,
                    errno.EINPROGRESS
            ):
                print("Failed to read from %s: %s" % (self.fd, e))
        return self.buff.getvalue()

    def reset(self):
        self.buff = StringIO()

    def cleanup(self):
        pass


class ThreadedBufferingBase(BufferingBase):
    def __init__(self, fh):
        self.buff = StringIO()
        self.fh = fh
        self.thread = threading.Thread(target=self.worker)
        self.thread.start()
        self.queue = Queue.Queue()

    def worker(self):
        while not self.fh.closed:
            try:
                data = self.fh.readline()
                if data:
                    self.queue.put(data)
                else:
                    time.sleep(1)
            except OSError as e:
                print("Failed to read from %s: %s" % (self.fh, e))
                raise

    def read(self):
        while 1:
            try:
                data = self.queue.get_nowait()
            except Queue.Empty:
                break
            try:
                data = data.decode(self.ENCODING)
            except Exception:
                logger.exception("Failed to decode %r" % data)
                raise
            self.buff.write(data)
        return self.buff.getvalue()

    def cleanup(self, ):
        self.thread.join()


class TestProcess(BufferingBase if fcntl else ThreadedBufferingBase):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('env', os.environ)
        kwargs.setdefault('bufsize', 1)
        self.proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kwargs
        )
        super(TestProcess, self).__init__(self.proc.stdout)

    @property
    def is_alive(self):
        return self.proc.poll() is None

    def signal(self, sig):
        self.proc.send_signal(sig)

    def __enter__(self):
        return self

    def __exit__(self, exc_type=None, exc_value=None, exc_traceback=None):
        try:
            for _ in range(5):
                if self.proc.poll() is not None:
                    return
                time.sleep(0.2)
            for _ in range(5):
                if self.proc.poll() is None:
                    try:
                        self.proc.terminate()
                    except Exception as exc:
                        if exc.errno == errno.ESRCH:
                            return
                        else:
                            print("Failed to terminate %s: %s" % (self.proc.pid, exc))
                else:
                    return
                time.sleep(0.2)
            try:
                print('Killing %s !' % self, file=sys.stderr)
                self.proc.kill()
            except OSError as exc:
                if exc.errno != errno.ESRCH:
                    raise
        finally:
            try:
                self.proc.communicate()
            except IOError as exc:
                if exc.errno != errno.EAGAIN:
                    print('\nFailed to cleanup process:\n', file=sys.stderr)
                    traceback.print_exc()
            except Exception:
                print('\nFailed to cleanup process:\n', file=sys.stderr)
                traceback.print_exc()
            try:
                self.cleanup()
            except Exception:
                print('\nFailed to cleanup process:\n', file=sys.stderr)
                traceback.print_exc()

    close = __exit__


class TestSocket(BufferingBase if fcntl else ThreadedBufferingBase):
    BUFFSIZE = 8192

    def __init__(self, sock):
        self.sock = sock
        if PY3:
            self.fh = sock.makefile('rbw', buffering=1)
        else:
            self.fh = sock.makefile(bufsize=0)

        if fcntl:
            sock.setblocking(0)
            super(TestSocket, self).__init__(sock)
        else:
            super(TestSocket, self).__init__(self.fh)

    def __enter__(self):
        return self

    def __exit__(self, exc_type=None, exc_value=None, exc_traceback=None):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        except (OSError, socket.error) as exc:
            if exc.errno not in BAD_FD_ERRORS:
                raise

    close = __exit__


def wait_for_strings(cb, seconds, *strings):
    """
    This checks that *string appear in cb(), IN THE GIVEN ORDER !
    """
    buff = '<UNINITIALIZED>'

    start = time.time()
    while True:
        buff = cb()
        check_strings = list(strings)
        check_strings.reverse()
        for line in buff.splitlines():
            if not check_strings:
                break
            while check_strings and check_strings[-1] in line:
                check_strings.pop()
        if not check_strings:
            return
        if time.time() - start > seconds:
            break
        time.sleep(0.05)

    raise AssertionError("Waited %0.2fsecs but %s did not appear in output in the given order !" % (
        seconds, check_strings
    ))


@contextmanager
def dump_on_error(cb):
    try:
        yield
    except Exception:
        print("*********** OUTPUT ***********")
        print(cb())
        print("******************************")
        raise


@contextmanager
def dump_always(cb):
    try:
        yield
    finally:
        print("*********** OUTPUT ***********")
        print(cb())
        print("******************************")


class ProcessTestCase(unittest.TestCase):
    dump_on_error = staticmethod(dump_on_error)
    wait_for_strings = staticmethod(wait_for_strings)


_cov = None


def restart_coverage():
    logger.critical("(RE)STARTING COVERAGE.")
    global _cov
    try:
        from coverage.control import coverage
        from coverage.collector import Collector
    except ImportError:
        _cov = None
        return
    if _cov:
        _cov.save()
        _cov.stop()
    if Collector._collectors:
        Collector._collectors[-1].stop()

    _cov = coverage(auto_data=True, data_suffix=True)
    _cov.start()


def setup_coverage(env_var="WITH_COVERAGE"):
    """
    Patch fork and forkpty to restart coverage measurement after fork. Expects to have a environment variable named WITH_COVERAGE set to a
    non-empty value.
    """
    if os.environ.get(env_var) == 'yes':  # don't even bother if not set
        restart_coverage()

        handler = signal.getsignal(signal.SIGTERM)
        if handler is None:
            logger.critical("SIGTERM handler not installed from python. It's getting overriden !")
            print("SIGTERM handler not installed from python. It's getting overriden !", file=sys.__stderr__)

        @partial(signal.signal, signal.SIGTERM)
        def on_atexit(signo, frame):
            if _cov:
                _cov._atexit()
            if handler == signal.SIG_DFL:
                signal.signal(signo, signal.SIG_DFL)
                os.kill(os.getpid(), signo)
            elif handler == signal.SIG_IGN:
                pass
            elif handler:
                handler(signo, frame)
