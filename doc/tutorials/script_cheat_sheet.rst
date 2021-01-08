Gr  .. _script_cheat_sheet:

Script Cheat Sheet
==================

This page was created as a resource to be able to better use GridCal as a Python library. The page contains everything from importing the library, opening models, running simulations, visualizing results, etc.

Importing the Library
---------------------
Create a Python script, and add the library there are two options:


1. The Entire Engine
^^^^^^^^^^^^^^^^^^^^^
In this case we are going to import everything automatically (recommended).

.. code-block:: python

    from GridCal.Engine import *

This is the way we are going to import GridCal's objects in all the tutorials, except when we import
them from a specific location (see 2). We could also import everything into a namespace in order to
avoid collisions with similarly named objects:

.. code-block:: python

    import GridCal.Engine as gce

Then you would call `gce.Bus()` instead of simply `Bus()`, like this it would be clear
that you are referring to GridCal's Bus object and not to any other object type named `Bus`.

2. Specific Engine Features
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
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
    - .xls: GridCal's old native format: tables saved into an excel file.
    - .xlsx: GridCal's old native format: tables saved into an excel file.
    - .gridcal: GridCal's native format. It is a Zip file with CSV files inside.
    - .sqlite: GridCal tables into a SQLite format.
    - .dgs: Power Factory text file.
    - .m: MatPower and it's FUBM branch of MatPower files.
    - .dpx: INESC (Portugal) exchange file format.
    - .json: REE / GridCal Json file format.
    - .raw: PSSe text file parser for versions 29, 30, 32, 33.
    - .xml: CIM version 16 (as interpreted by Power Factory...)

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
    - .json
    - .xml

The .json format is the most compatible since it is the easiest to parse and understand
from another software. The excel formats are more human-readable and easy to parse as well.

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


