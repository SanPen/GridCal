
Installation
------------

GridCal is a software made in the Python programming language.
Therefore, it needs a Python interpreter installed in your operative
system.

Standalone setup
~~~~~~~~~~~~~~~~

If you don’t know what is this Python thing, we offer a windows
installation:

`Windows setup <https://www.advancedgridinsights.com/gridcal>`__

This will install GridCal as a normal windows program and you need not
to worry about any of the previous instructions. Still, if you need some
guidance, the following video might be of assistance: `Setup tutorial
(video) <https://youtu.be/SY66WgLGo54>`__.

Package installation
~~~~~~~~~~~~~~~~~~~~

We recommend to install the latest version of
`Python <www.python.org>`__ and then, install GridCal with the following
terminal command:

::

   pip install GridCal

You may need to use ``pip3`` if you are under Linux or MacOS, both of
which come with Python pre-installed already.

Run the graphical user interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you install GridCal in your local Python distribution, you can run
the graphical user interface with the following terminal command:


::
    gridcal


If this doesn't work, try:


::

   python -c "from GridCal.ExecuteGridCal import runGridCal; runGridCal()"

You may save this command in a shortcut for easy future access.

Install only the engine
~~~~~~~~~~~~~~~~~~~~~~~

Some of you may only need GridCal as a library for some other purpose
like batch calculations, AI training or simple scripting. Whatever it
may be, you can get the GridCal engine with the following terminal
command:

::

   pip install GridCalEngine

This will install the ``GridCalEngine`` package that is a dependency of
``GridCal``.

Again, you may need to use ``pip3`` if you are under Linux or MacOS.

Features
--------

GridCal is packed with feautures:

-  Large collection of devices to model electricity grids
-  AC/DC multi-grid power flow
-  AC/DC multi-grid linear optimal power flow
-  AC linear analysis (PTDF & LODF)
-  AC linear net transfer capacity calculation
-  AC+HVDC optimal net transfer capacity calculation
-  AC/DC Stochastic power flow
-  AC Short circuit
-  AC Continuation power flow
-  Contingency analysis (Power flow and LODF variants)
-  Sigma analysis (one-shot stability analysis)
-  Investments analysis
-  Bus-branch schematic
-  Substation-line map diagram
-  Time series and snapshot for most simulations
-  Overhead tower designer
-  Inputs analysis
-  Model bug report and repair
-  Import many formats (PSSe .raw/rawx, epc, dgs, matpower, pypsa, json,
   cim, cgmes)
-  Export in many formats (gridcal .xlsx/.gridcal/.json, cgmes, psse
   .raw/.rawx)

All of these are industry tested algoriths, some of which surpass most
comemercially available software. The aim is to be a drop-in replacement
for the expensive and less usable commercial software, so that you can
work, research and learn with it.

Resources
~~~~~~~~~

In an effort to ease the simulation and construction of grids, We have
included extra materials to work with. These are included in the
standalone setups.

-  `Load
   profiles <https://github.com/SanPen/GridCal/tree/master/Grids_and_profiles/equipment>`__
   for your projects.
-  `Grids <https://github.com/SanPen/GridCal/tree/master/Grids_and_profiles/grids>`__
   from IEEE and other open projects.
-  `Equipment
   catalogue <https://gridcal.readthedocs.io/en/latest/data_sheets.html>`__
   (Wires, Cables and Transformers) ready to use in GridCal.

Tutorials and examples
~~~~~~~~~~~~~~~~~~~~~~

-  `Tutorials <https://gridcal.readthedocs.io/en/latest/tutorials/tutorials_module.html>`__

-  `Cloning the repository (video) <https://youtu.be/59W_rqimB6w>`__

-  `Making a grid with profiles
   (video) <https://youtu.be/H2d_2bMsIS0>`__

-  `GridCal PlayGround
   repository <https://github.com/yasirroni/GridCalPlayground>`__ with
   some notebooks and examples.

-  `The
   tests <https://github.com/SanPen/GridCal/tree/master/src/tests>`__
   may serve as a valuable source of examples.