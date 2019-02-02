.. _development:

Development
===========

Testing with pytest
-------------------

Unit test (for pytest) are included in `src\tests`. As defined in `pytest.ini`, all
files matching `test_*.py` are executed by running:

.. code::

    pytest

Files matching `*_test.py` are not executed; they were not formatted specifically for
`pytest` but were mostly done for manual testing and documentation purposes.

Additional tests should be developped for each new and existing feature. `pytest`
should be run before each commit to prevent easily detectable bugs.
