import errno
import os
import queue as Queue
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from io import StringIO
from logging import getLogger
from typing import IO

try:
    import fcntl
except ImportError:
    fcntl = False

__version__ = '3.0.0'

logger = getLogger(__name__)

BUFFSIZE = 8192
BAD_FD_ERRORS = tuple(getattr(errno, name) for name in ['EBADF', 'EBADFD', 'ENOTCONN'] if hasattr(errno, name))


class PipeBuffer:
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
                data = os.read(self.fd, BUFFSIZE)
                if not data:
                    break
                if isinstance(data, bytes):
                    data = data.decode(errors='backslashreplace')
                self.buff.write(data)
        except OSError as exc:
            if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS):
                logger.exception('%r failed to read from FD %s: %r', self, self.fd, exc)
        return self.buff.getvalue()

    def reset(self):
        self.buff = StringIO()

    def cleanup(self):
        pass


class FileBuffer:
    def __init__(self, path):
        self.fh = open(path, 'rb')
        self.position = 0

    def read(self):
        """
        Read any available data fd. Does NOT block.
        """
        self.fh.seek(self.position)
        data = self.fh.read()
        return data.decode(errors='backslashreplace')

    def reset(self):
        self.position = self.fh.seek(0, os.SEEK_END)

    def cleanup(self):
        self.fh.close()


class ThreadedBuffer:
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
            except OSError as exc:
                if exc.errno != errno.EAGAIN:
                    logger.exception('%r failed to read from %s: %r', self, self.fh, exc)
                    return

    def read(self):
        while 1:
            try:
                data = self.queue.get_nowait()
            except Queue.Empty:
                break
            if isinstance(data, bytes):
                data = data.decode(errors='backslashreplace')
            self.buff.write(data)
        return self.buff.getvalue()

    def cleanup(
        self,
    ):
        self.thread.join()


class TestProcess:
    __test__ = False

    def __init__(self, *args, stdout: IO = subprocess.PIPE, **kwargs):
        kwargs.setdefault('env', os.environ)
        kwargs.setdefault('bufsize', 1)
        kwargs.setdefault('universal_newlines', True)
        kwargs.setdefault('stderr', subprocess.STDOUT)
        kwargs.setdefault('close_fds', sys.platform != 'win32')

        if stdout is subprocess.PIPE:
            self.proc = subprocess.Popen(args, stdout=stdout, **kwargs)
            self.buff = (PipeBuffer if fcntl else ThreadedBuffer)(self.proc.stdout)
        else:
            self.buff = FileBuffer(stdout.name)
            self.proc = subprocess.Popen(args, stdout=stdout, **kwargs)
        self.trailer = ''

    def read(self):
        return self.buff.read() + self.trailer

    @property
    def is_alive(self):
        return self.proc.poll() is None

    def signal(self, sig):
        self.proc.send_signal(sig)

    def __repr__(self):
        return f'TestProcess(pid={self.proc.pid}, is_alive={self.is_alive})'

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
                            logger.exception('%r failed to terminate process: %r', self, exc)
                else:
                    return
                time.sleep(0.2)
            try:
                logger.critical('%s killing unresponsive process!', self)
                self.proc.kill()
            except OSError as exc:
                if exc.errno != errno.ESRCH:
                    raise
        finally:
            try:
                data, _ = self.proc.communicate()
                try:
                    if isinstance(data, bytes):
                        data = data.decode(errors='backslashreplace')
                except Exception as exc:
                    logger.exception('%s failed to decode %r: %r', self, data, exc)
                    raise
                self.trailer = data
            except OSError as exc:
                if exc.errno != errno.EAGAIN:
                    logger.exception('%s failed to cleanup buffers: %r', self, exc)
            except Exception as exc:
                logger.exception('%s failed to cleanup buffers: %r', self, exc)
            try:
                self.buff.cleanup()
            except Exception as exc:
                logger.exception('%s failed to cleanup: %r', self, exc)

    close = __exit__


class TestSocket(PipeBuffer if fcntl else ThreadedBuffer):
    __test__ = False

    def __init__(self, sock):
        self.sock = sock
        self.fh = sock.makefile('rbw', buffering=1)

        if fcntl:
            sock.setblocking(0)
            super().__init__(sock)
        else:
            super().__init__(self.fh)

    def __enter__(self):
        return self

    def __exit__(self, exc_type=None, exc_value=None, exc_traceback=None):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        except OSError as exc:
            if exc.errno not in BAD_FD_ERRORS:
                raise

    close = __exit__


def wait_for_strings(cb, seconds, *strings):
    """
    This checks that *string appear in cb(), IN THE GIVEN ORDER !
    """
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

    raise AssertionError(f'Waited {seconds:0.2f}secs but {check_strings} did not appear in output in the given order !')


@contextmanager
def dump_on_error(cb, heading=None):
    try:
        yield
    except Exception:
        print(f' {heading or cb} '.center(100, '*'))
        print(cb())
        print('*' * 100)
        raise


@contextmanager
def dump_always(cb, heading=None):
    try:
        yield
    finally:
        print(f' {heading or cb} '.center(100, '*'))
        print(cb())
        print('*' * 100)
