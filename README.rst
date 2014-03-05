============================
    python-process-tests
============================

.. image:: https://badge.fury.io/py/process-tests.png
    :alt: PYPI Package
    :target: https://pypi.python.org/pypi/process-tests

Tools for testing processes.

Usage
=====

::

    from process_tests import ProcessTestCase
    from process_tests import TestProcess

    class MyTestCase(ProcessTestCase):
        def test_simple(self):
            with TestProcess('mydaemon', 'arg1', 'arg2') as proc:
                with self.dump_on_error(proc.read):
                    self.wait_for_strings(proc.read, 10, # wait 10 seconds for process to output lines with these strings
                        'Started',
                        'Working',
                        'Done',
                    )


Features
========

* TODO

Examples
========

* https://github.com/ionelmc/python-redis-lock/blob/master/tests/test_redis_lock.py
* https://github.com/ionelmc/python-manhole/blob/master/tests/test_manhole.py
* https://github.com/ionelmc/python-stampede/blob/master/tests/test_stampede.py
* https://github.com/ionelmc/python-remote-pdb/blob/master/tests/test_remote_pdb.py

TODO
====

* tests
* docs

Requirements
============

:OS: Any
:Runtime: Python 2.6, 2.7, 3.2, 3.3 or PyPy

Similar projects
================

* TODO
