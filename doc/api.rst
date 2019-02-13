.. _api:

API reference
=============

**GridCal** uses an object oriented approach for all the data and simulation
management. However the object orientation is very inefficient when used in numerical
computation, that is why there are :code:`compile()` functions that extract the
information out of the objects and turn this information into vectors, matrices and
DataFrames in order to have efficient numerical computations. After having been
involved in quite some number-crunching software developments, I have found this
approach to be the best compromise between efficiency and code scalability and
maintainability.

The whole idea can be summarized as:

*Object oriented structures -> intermediate objects holding arrays -> Numerical
modules*

.. toctree::
    :maxdepth: 4

    api/multicircuit
    api/devices
    api/device_types
    api/io_structures
    api/drivers
