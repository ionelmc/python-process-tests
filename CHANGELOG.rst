
Changelog
=========

3.0.0 (2023-11-01)
------------------

* Dropped Python 2 support.
* Added an optional non-pipe TestProcess mode. You can use file objects for processes that are too verbose for a pipe.
* Added some tests.

2.1.2 (2021-05-02)
------------------

* Fixed another regression caused by the ``universal_newlines`` for Windows.

2.1.1 (2020-07-23)
------------------

* Fixed regression caused by the ``universal_newlines`` (now the internals don't decode strings).

2.1.0 (2020-07-23)
------------------

* Applied the cookiecutter-pylibrary templates.
* ``TestProcess`` will use ``universal_newlines`` by default for the contained ``subprocess.Popen`` to make sure line buffering is actually
  used. This also fixes warnings on Python 3.

2.x (???)
---------

* Lots of wild stuff.
