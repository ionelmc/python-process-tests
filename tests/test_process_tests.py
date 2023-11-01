import os
import re
import socket

import pytest

from process_tests import TestProcess
from process_tests import TestSocket
from process_tests import dump_on_error
from process_tests import wait_for_strings

TIMEOUT = int(os.getenv('TESTS_TIMEOUT', 60))


def test_wait_for_strings():
    with TestProcess('python', '-c', 'print("foobar")') as proc:
        wait_for_strings(proc.read, TIMEOUT, 'foobar')
        with pytest.raises(AssertionError):
            with dump_on_error(proc.read):
                wait_for_strings(proc.read, 0.1, 'cannot be')


def test_filebuffer(tmp_path):
    with tmp_path.joinpath('stdout').open('wb') as fh:
        with TestProcess('python', '-c', 'print("foobar")', stdout=fh) as proc:
            wait_for_strings(proc.read, TIMEOUT, 'foobar')
            with pytest.raises(AssertionError):
                with dump_on_error(proc.read):
                    wait_for_strings(proc.read, 0.1, 'cannot be')


def test_socket():
    with TestProcess('python', '-mhttp.server', '0') as proc:
        with dump_on_error(proc.read, 'SERVER'):
            wait_for_strings(proc.read, TIMEOUT, 'Serving HTTP on')
            (port,) = re.match(r'Serving HTTP on .*? port (\d+) ', proc.read()).groups()
            with socket.create_connection(('127.0.0.1', int(port))) as conn:
                with TestSocket(conn) as client:
                    client.sock.send(b'GET / HTTP/1.0\n\n')
                    with dump_on_error(client.read, 'CLIENT'):
                        wait_for_strings(proc.read, TIMEOUT, 'GET / HTTP')
                        wait_for_strings(client.read, TIMEOUT, 'HTTP/1.0 200 OK')
