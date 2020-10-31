Gr  .. _distribution_grid_library:

Distribution Grid Library
=========================

This tutorial shows different ways and actions that you can do while using GridCal as a Python Library.
This mode has various advantages such as: more efficient modeling, modeling automation, and overall a more cutomizable experience.
The tutorial will give you the tools, to create models, run studies and visualize results.

Importing the Library
=====================
Create a Python script, and add the library there are two options;

1. Specific Engine Features
---------------------------
In this case we are going to import only: branches, buses, generators, loads, types, power flow options, power flow solver types,
power flow drivers, multicircuit and time series.

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
--------------------
In this case we are going to import everything automatically.

.. code-block:: python

    from GridCal.Engine import *

Method 1 works better when you are interested in specific things and/or you want to optimize GridCal. For the rest of the tutorial we will use Method 2.

Loading an Existing Model
=========================
If you have already created a model such as the 'Distribution Grid Model' or any .gridcal file you can load it in a Python Script the following way:

.. code-block:: python

    from GridCal.Engine import *

This is specially useful if you would like to create the grid using the GUI but run analysis, visualize results or pair it with other Python tools suchas NumPy or Pandas, etc.

.. code-block:: python

    from GridCal.Engine import *

**Note:** you can still change the grid within the script but this is meant just to load a finished script.


Creating a Model
================
In this section we will create the same 'Distribution Grid' from here_.

.. _here: https://gridcal.readthedocs.io/en/latest/tutorials/distribution_grid.html

Step 0: System Overview
-----------------------

Step 1: Create a Transfomer
---------------------------

Step 2: Create Lines of Different Lengths
-----------------------------------------

Step 3: Add More Lines and Buses
--------------------------------

Step 4: Create Loads
--------------------

Step 5: Crate House 1 and House 2
---------------------------------

Step 6: Defining the Main Transformer
-------------------------------------

Step 7: Defining Load Transformers
----------------------------------

Step 8: Defining Other Transformers
-----------------------------------

Step 9: Defining Wires and Overhead Lines
-----------------------------------------

Step 10: Importing Load Profiles
--------------------------------

Running a Power Flow
====================

Running a Time Series Power Flow
================================

Vizualize Results
=================


Functions Listing
=================
Here is a list of some useful functions:
-


