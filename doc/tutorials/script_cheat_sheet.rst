Gr  .. _script_cheat_sheet:

Script Cheat Sheet
==================

This page was created as a resource to be able to better use GridCal as a Python library. The page contains everything from importing the library, opening models, running simulations, visualizing results, etc.

Importing the Library
---------------------
Create a Python script, and add the library there are two options:

1. Specific Engine Features
^^^^^^^^^^^^^^^^^^^^^^^^^^^
In this case we are going to import only: branches, buses, generators, loads, types, power flow options, power flow solver types,
power flow drivers, multicircuit and time series (it is not limited to the options below).

.. code-block:: python

    from GridCal.Engine.Devices.branch import Branch, BranchTemplate
    from GridCal.Engine.Devices.bus import Bus
    from GridCal.Engine.Devices.generator import Generator
    from GridCal.Engine.Devices.load import Load
    from GridCal.Engine.Devices.types import BranchType
    from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, SolverType
    from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
    from GridCal.Engine.Core.multi_circuit import MultiCircuit
    from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeries


2. The Entire Engine
^^^^^^^^^^^^^^^^^^^^
In this case we are going to import everything automatically (recommended).

.. code-block:: python

    from GridCal.Engine import *

Opening GridCal File
--------------------
Here is how you can open an **existing** GridCal file to your script so you can work with it:

1. Make sure FileOpen Module is imported
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Import the engine and the file handler module below:

.. code-block:: python

    from GridCal.Engine import *
    from GridCal.Engine.IO.file_handler import FileOpen


2. Define and open model
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    grid = FileOpen(**Models_path**).open()

You can open files with the following extensions:
    - .xls
    - .xlsx
    - .gridcal
    - .sqlite
    - .dgs
    - .m
    - .dpx
    - .json
    - .raw
    - .xml

Once you have opened a GridCal model (previous subsection), here is all you can do:
    -

Saving GridCal File
--------------------
Here is how you can save an GridCal model to your script so you can work with it:

1. Make sure FileSave Module is imported
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Import the engine and the file handler module below:

.. code-block:: python

    from GridCal.Engine import *
    from GridCal.Engine.IO.file_handler import FileSave

2. Save GridCal model
^^^^^^^^^^^^^^^^^^^^^
This assumes you have a GridCal file open, defined and unsaved in your code.

.. code-block:: python

    grid = FileSave(**Models_path**).save()

You can save files with the following extensions:
    - .xls
    - .xlsx
    - .gridcal
    - .sqlite
    - .dgs
    - .m
    - .dpx
    - .json
    - .raw
    - .xml

Creating a New GridCal Model
----------------------------


View GridCal Model
------------------


Running a Power Flow
--------------------

Running a Time Series Power Flow
--------------------------------

Visualize Results
-----------------

Functions Listing
-----------------
Here is a list of some useful functions:
-


