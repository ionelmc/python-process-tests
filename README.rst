========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - tests
      - | |github-actions|
        |
    * - package
      - | |version| |wheel| |supported-versions| |supported-implementations|
        | |commits-since|

.. |github-actions| image:: https://github.com/ionelmc/python-process-tests/actions/workflows/github-actions.yml/badge.svg
    :alt: GitHub Actions Build Status
    :target: https://github.com/ionelmc/python-process-tests/actions

.. |version| image:: https://img.shields.io/pypi/v/process-tests.svg
    :alt: PyPI Package latest release
    :target: https://pypi.org/project/process-tests

.. |wheel| image:: https://img.shields.io/pypi/wheel/process-tests.svg
    :alt: PyPI Wheel
    :target: https://pypi.org/project/process-tests

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/process-tests.svg
    :alt: Supported versions
    :target: https://pypi.org/project/process-tests

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/process-tests.svg
    :alt: Supported implementations
    :target: https://pypi.org/project/process-tests

.. |commits-since| image:: https://img.shields.io/github/commits-since/ionelmc/python-process-tests/v3.0.0.svg
    :alt: Commits since latest release
    :target: https://github.com/ionelmc/python-process-tests/compare/v3.0.0...main



.. end-badges

Tools for testing processes.

* Free software: BSD 2-Clause License

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
