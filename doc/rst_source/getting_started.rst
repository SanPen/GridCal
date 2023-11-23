.. _getting_started:

Getting Started
===============


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

API
---

Since day one, GridCal was meant to be used as a library as much as it
was meant to be used from the user interface. Following, we include some
usage examples, but feel free to check the
`documentation <https://gridcal.readthedocs.io>`__ out where you will
find a complete description of the theory, the models and the objects.

Understanding the program structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All simulations in GridCal are handled by the simulation drivers. The
structure is as follows:

Any driver is fed with the data model (``MultiCircuit`` object), the
respective driver options, and often another object relative to specific
inputs for that driver. The driver is run, storing the driver results
object. Although this may seem overly complicated, it has proven to be
maintainable and very convenient.

Snapshot vs. time series
~~~~~~~~~~~~~~~~~~~~~~~~

GridCal has dual structure to handle legacy cases (snapshot), as well as
cases with many variations (time series)

-  A **snapshot** is the grid for a particular moment in time. This
   includes the infrastructure plus the variable values of that
   infraestructure such as the load, the generation, the rating, etc.

-  The **time series** record the variations of the magnitudes that can
   vary. These are aplied along with the infrastructure definition.

In GridCal, the inputs do not get modified by the simulation results.
This very important concept, helps maintaining the independence of the
inputs and outputs, allowing the replicability of the results. This key
feature is not true for other open-source of comercial programs.

A snapshot or any point of the time series, may be compiled to a
``NumericalCircuit``. This object holds the numerical arrays and
matrices of a time step, ready for the numerical methods. For those
simulations that require many time steps, a collection of
``NumericalCircuit`` is compiled and used.

It may seem that this extra step is redundant. However the compilation
step is composed by mere copy operations, which are fast. This steps
benefits greatly the efficiency of the numerical calculations since the
arrays are aligned in memory. The GridCal data model is object-oriented,
while the numerical circuit is array-oriented (despite beign packed into
objects)

Loading a grid
~~~~~~~~~~~~~~

.. code:: python

   import GridCalEngine.api as gce

   # load a grid
   my_grid = gce.open_file("my_file.gridcal")

GridCal supports a plethora of file formats:

-  CIM 16 (.zip and .xml)
-  CGMES 2.4.15 (.zip and .xml)
-  PSS/e raw and rawx versions 29 to 35, including USA market excahnge
   RAW-30 specifics.
-  Matpower .m files directly.
-  DigSilent .DGS (not fully compatible)
-  PowerWorld .EPC (not fully compatible, supports substation
   coordinates)

Save a grid
~~~~~~~~~~~

.. code:: python

   import GridCalEngine.api as gce

   # load a grid
   my_grid = gce.open_file("my_file.gridcal")

   # save
   gce.save_file(my_grid, "my_file_2.gridcal")

Creating a Grid using the API objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We are going to create a very simple 5-node grid from the excellent book
*Power System Load Flow Analysis by Lynn Powell*.

.. code:: python

   import GridCalEngine.api as gce

   # declare a circuit object
   grid = gce.MultiCircuit()

   # Add the buses and the generators and loads attached
   bus1 = gce.Bus('Bus 1', vnom=20)
   # bus1.is_slack = True  # we may mark the bus a slack
   grid.add_bus(bus1)

   # add a generator to the bus 1
   gen1 = gce.Generator('Slack Generator', vset=1.0)
   grid.add_generator(bus1, gen1)

   # add bus 2 with a load attached
   bus2 = gce.Bus('Bus 2', vnom=20)
   grid.add_bus(bus2)
   grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

   # add bus 3 with a load attached
   bus3 = gce.Bus('Bus 3', vnom=20)
   grid.add_bus(bus3)
   grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))

   # add bus 4 with a load attached
   bus4 = gce.Bus('Bus 4', vnom=20)
   grid.add_bus(bus4)
   grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

   # add bus 5 with a load attached
   bus5 = gce.Bus('Bus 5', vnom=20)
   grid.add_bus(bus5)
   grid.add_load(bus5, gce.Load('load 5', P=50, Q=20))

   # add Lines connecting the buses
   grid.add_line(gce.Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.02))
   grid.add_line(gce.Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.02))
   grid.add_line(gce.Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.02))
   grid.add_line(gce.Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.02))
   grid.add_line(gce.Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.02))
   grid.add_line(gce.Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.03))
   grid.add_line(gce.Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.02))

Power Flow
~~~~~~~~~~

Using the simplified API:

.. code:: python

   import os
   import GridCalEngine.api as gce

   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'IEEE39_1W.gridcal')
   main_circuit = gce.open_file(fname)

   results = gce.power_flow(main_circuit)

   print(main_circuit.name)
   print('Converged:', results.converged, 'error:', results.error)
   print(results.get_bus_df())
   print(results.get_branch_df())

Using the more complex library objects:

.. code:: python

   import os
   import GridCalEngine.api as gce

   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'IEEE14_from_raw.gridcal')
   main_circuit = gce.open_file(fname)

   options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
   power_flow = gce.PowerFlowDriver(main_circuit, options)
   power_flow.run()

   print(main_circuit.name)
   print('Converged:', power_flow.results.converged, 'error:', power_flow.results.error)
   print(power_flow.results.get_bus_df())
   print(power_flow.results.get_branch_df())

Output:

.. code:: text

   IEEE14_from_raw

   Converged: True error: 5.98e-08

   Bus resuts:
              Vm     Va      P      Q
   BUS 1    1.06   0.00 232.39 -16.55
   BUS 2    1.04  -4.98  18.30  30.86
   BUS 3    1.01 -12.73 -94.20   6.08
   BUS 4    1.02 -10.31 -47.80   3.90
   BUS 5    1.02  -8.77  -7.60  -1.60
   BUS 6    1.07 -14.22 -11.20   5.23
   BUS 7    1.06 -13.36   0.00   0.00
   BUS 8    1.09 -13.36   0.00  17.62
   BUS 9    1.06 -14.94 -29.50 -16.60
   BUS 10   1.05 -15.10  -9.00  -5.80
   BUS 11   1.06 -14.79  -3.50  -1.80
   BUS 12   1.06 -15.08  -6.10  -1.60
   BUS 13   1.05 -15.16 -13.50  -5.80
   BUS 14   1.04 -16.03 -14.90  -5.00

   Branch results:
               Pf     Qf      Pt     Qt               loading
   1_2_1   156.88 -20.40 -152.59  27.68 -2,040,429,074,673.33
   1_5_1    75.51   3.85  -72.75   2.23    385,498,944,321.99
   2_3_1    73.24   3.56  -70.91   1.60    356,020,306,394.25
   2_4_1    56.13  -1.55  -54.45   3.02   -155,035,233,483.95
   2_5_1    41.52   1.17  -40.61  -2.10    117,099,586,051.68
   3_4_1   -23.29   4.47   23.66  -4.84    447,311,351,720.93
   4_5_1   -61.16  15.82   61.67 -14.20  1,582,364,180,487.11
   6_11_1    7.35   3.56   -7.30  -3.44    356,047,085,671.01
   6_12_1    7.79   2.50   -7.71  -2.35    250,341,387,213.42
   6_13_1   17.75   7.22  -17.54  -6.80    721,657,405,311.13
   7_8_1    -0.00 -17.16    0.00  17.62 -1,716,296,745,837.05
   7_9_1    28.07   5.78  -28.07  -4.98    577,869,015,291.12
   9_10_1    5.23   4.22   -5.21  -4.18    421,913,877,670.92
   9_14_1    9.43   3.61   -9.31  -3.36    361,000,694,981.35
   10_11_1  -3.79  -1.62    3.80   1.64   -161,506,127,162.22
   12_13_1   1.61   0.75   -1.61  -0.75     75,395,885,855.71
   13_14_1   5.64   1.75   -5.59  -1.64    174,717,248,747.17
   4_7_1    28.07  -9.68  -28.07  11.38   -968,106,634,094.39
   4_9_1    16.08  -0.43  -16.08   1.73    -42,761,145,748.20
   5_6_1    44.09  12.47  -44.09  -8.05  1,247,068,151,943.25

Inputs analysis
~~~~~~~~~~~~~~~

GridCal can perform a summary of the inputs with the
``InputsAnalysisDriver``:

.. code:: python

   import os
   import GridCalEngine.api as gce

   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'IEEE 118 Bus - ntc_areas.gridcal')

   main_circuit = gce.open_file(fname)

   drv = gce.InputsAnalysisDriver(grid=main_circuit)
   mdl = drv.results.mdl(gce.ResultTypes.AreaAnalysis)
   df = mdl.to_df()

   print(df)

The results per area:

.. code:: text

                  P    Pgen   Pload  Pbatt  Pstagen      Pmin      Pmax      Q    Qmin    Qmax
   IEEE118-3  -57.0   906.0   963.0    0.0      0.0 -150000.0  150000.0 -345.0 -2595.0  3071.0
   IEEE118-2 -117.0  1369.0  1486.0    0.0      0.0 -140000.0  140000.0 -477.0 -1431.0  2196.0
   IEEE118-1  174.0  1967.0  1793.0    0.0      0.0 -250000.0  250000.0 -616.0 -3319.0  6510.0

Linear analysis
~~~~~~~~~~~~~~~

We can run an PTDF equivalent of the power flow with the linear analysys
drivers:

.. code:: python

   import os
   import GridCalEngine.api as gce

   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'IEEE 5 Bus.xlsx')

   main_circuit = gce.open_file(fname)

   options_ = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=True)

   # snapshot
   sn_driver = gce.LinearAnalysisDriver(grid=main_circuit, options=options_)
   sn_driver.run()

   print("Bus results:\n", sn_driver.results.get_bus_df())
   print("Branch results:\n", sn_driver.results.get_branch_df())
   print("PTDF:\n", sn_driver.results.mdl(gce.ResultTypes.PTDF).to_df())
   print("LODF:\n", sn_driver.results.mdl(gce.ResultTypes.LODF).to_df())

Output:

.. code:: text

   Bus results:
            Vm   Va       P    Q
   Bus 0  1.0  0.0  2.1000  0.0
   Bus 1  1.0  0.0 -3.0000  0.0
   Bus 2  1.0  0.0  0.2349  0.0
   Bus 3  1.0  0.0 -0.9999  0.0
   Bus 4  1.0  0.0  4.6651  0.0

   Branch results:
                      Pf   loading
   Branch 0-1  2.497192  0.624298
   Branch 0-3  1.867892  0.832394
   Branch 0-4 -2.265084 -0.828791
   Branch 1-2 -0.502808 -0.391900
   Branch 2-3 -0.267908 -0.774300
   Branch 3-4 -2.400016 -1.000006

   PTDF:
                   Bus 0     Bus 1     Bus 2  Bus 3     Bus 4
   Branch 0-1  0.193917 -0.475895 -0.348989    0.0  0.159538
   Branch 0-3  0.437588  0.258343  0.189451    0.0  0.360010
   Branch 0-4  0.368495  0.217552  0.159538    0.0 -0.519548
   Branch 1-2  0.193917  0.524105 -0.348989    0.0  0.159538
   Branch 2-3  0.193917  0.524105  0.651011    0.0  0.159538
   Branch 3-4 -0.368495 -0.217552 -0.159538    0.0 -0.480452

   LODF:
                Branch 0-1  Branch 0-3  Branch 0-4  Branch 1-2  Branch 2-3  Branch 3-4
   Branch 0-1   -1.000000    0.344795    0.307071   -1.000000   -1.000000   -0.307071
   Branch 0-3    0.542857   -1.000000    0.692929    0.542857    0.542857   -0.692929
   Branch 0-4    0.457143    0.655205   -1.000000    0.457143    0.457143    1.000000
   Branch 1-2   -1.000000    0.344795    0.307071   -1.000000   -1.000000   -0.307071
   Branch 2-3   -1.000000    0.344795    0.307071   -1.000000   -1.000000   -0.307071
   Branch 3-4   -0.457143   -0.655205    1.000000   -0.457143   -0.457143   -1.000000

Now let’s make a comparison between the linear flows and the non-linear
flows from Newton-Raphson:

.. code:: python

   import os
   from matplotlib import pyplot as plt
   import GridCalEngine.api as gce

   plt.style.use('fivethirtyeight')


   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'IEEE39_1W.gridcal')
   main_circuit = gce.open_file(fname)

   ptdf_driver = gce.LinearAnalysisTimeSeriesDriver(grid=main_circuit)
   ptdf_driver.run()

   pf_options_ = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
   ts_driver = gce.PowerFlowTimeSeriesDriver(grid=main_circuit, options=pf_options_)
   ts_driver.run()

   fig = plt.figure(figsize=(30, 6))
   ax1 = fig.add_subplot(131)
   ax1.set_title('Newton-Raphson based flow')
   ax1.plot(ts_driver.results.Sf.real)
   ax1.set_ylabel('MW')
   ax1.set_xlabel('Time')

   ax2 = fig.add_subplot(132)
   ax2.set_title('PTDF based flow')
   ax2.plot(ptdf_driver.results.Sf.real)
   ax2.set_ylabel('MW')
   ax2.set_xlabel('Time')

   ax3 = fig.add_subplot(133)
   ax3.set_title('Difference')
   diff = ts_driver.results.Sf.real - ptdf_driver.results.Sf.real
   ax3.plot(diff)
   ax3.set_ylabel('MW')
   ax3.set_xlabel('Time')

   fig.set_tight_layout(tight=True)

   plt.show()

.. figure:: pics%2FPTDF%20flows%20comparison.png
   :alt: PTDF flows comparison.png

   PTDF flows comparison.png

Linear optimization
~~~~~~~~~~~~~~~~~~~

.. code:: python

   import os
   import numpy as np
   import GridCalEngine.api as gce

   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'IEEE39_1W.gridcal')

   main_circuit = gce.open_file(fname)

   # declare the snapshot opf
   opf_driver = gce.OptimalPowerFlowDriver(grid=main_circuit)

   print('Solving...')
   opf_driver.run()

   print("Status:", opf_driver.results.converged)
   print('Angles\n', np.angle(opf_driver.results.voltage))
   print('Branch loading\n', opf_driver.results.loading)
   print('Gen power\n', opf_driver.results.generator_power)
   print('Nodal prices \n', opf_driver.results.bus_shadow_prices)


   # declare the time series opf
   opf_ts_driver = gce.OptimalPowerFlowTimeSeriesDriver(grid=main_circuit)

   print('Solving...')
   opf_ts_driver.run()

   print("Status:", opf_ts_driver.results.converged)
   print('Angles\n', np.angle(opf_ts_driver.results.voltage))
   print('Branch loading\n', opf_ts_driver.results.loading)
   print('Gen power\n', opf_ts_driver.results.generator_power)
   print('Nodal prices \n', opf_ts_driver.results.bus_shadow_prices)

Run a linear optimization and verify with power flow
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Often ties, you want to dispatch the generation using a linear
optimization, to then *veryfy* the results using the power exact power
flow. With GridCal, to do so is as easy as passing the results of the
OPF into the PowerFlowDriver:

.. code:: python

   import os
   import numpy as np
   import GridCalEngine.api as gce

   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'IEEE39_1W.gridcal')

   main_circuit = gce.open_file(fname)

   # declare the snapshot opf
   opf_driver = gce.OptimalPowerFlowDriver(grid=main_circuit)
   opf_driver.run()

   # create the power flow driver, with the OPF results
   pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
   pf_driver = gce.PowerFlowDriver(grid=main_circuit,
                                   options=pf_options,
                                   opf_results=opf_driver.results)
   pf_driver.run()

   # Print results
   print('Converged:', pf_driver.results.converged, '\nError:', pf_driver.results.error)
   print(pf_driver.results.get_bus_df())
   print(pf_driver.results.get_branch_df())

Outout:

.. code:: text

   OPF results:

            Va    P  Shadow price
   Bus 1  0.00  0.0           0.0
   Bus 2 -2.22  0.0           0.0
   Bus 3 -1.98  0.0           0.0
   Bus 4 -2.12  0.0           0.0
   Bus 5 -2.21  0.0           0.0

                Pf     Pt  Tap angle  Loading
   Branch 1 -31.46  31.46        0.0   -44.94
   Branch 1  -1.84   1.84        0.0   -10.20
   Branch 1  -1.84   1.84        0.0    -9.18
   Branch 1   0.14  -0.14        0.0     1.37
   Branch 1 -48.30  48.30        0.0   -53.67
   Branch 1 -35.24  35.24        0.0   -58.73
   Branch 1  -4.62   4.62        0.0   -23.11

   Power flow results:
   Converged: True
   Error: 3.13e-11

            Vm    Va         P      Q
   Bus 1  1.00  0.00  1.17e+02  12.90
   Bus 2  0.97 -2.09 -4.00e+01 -20.00
   Bus 3  0.98 -1.96 -2.50e+01 -15.00
   Bus 4  1.00 -2.61  2.12e-09  32.83
   Bus 5  0.98 -2.22 -5.00e+01 -20.00

                Pf     Qf     Pt     Qt  Loading
   Branch 1 -31.37  -2.77  31.88   1.93   -44.81
   Branch 2  -1.61  13.59   1.74 -16.24    -8.92
   Branch 3  -1.44 -20.83   1.61  19.24    -7.21
   Branch 4   0.46   5.59  -0.44  -7.46     4.62
   Branch 5 -49.02  -4.76  49.77   4.80   -54.47
   Branch 6 -34.95  -6.66  35.61   6.16   -58.25
   Branch 7  -4.60  -5.88   4.62   4.01   -23.02

Short circuit
~~~~~~~~~~~~~

GridCal has unbalanced short circuit calculations. Now let’s run a
line-ground short circuit in the third bus of the South island of New
Zealand grid example from refference book *Computer Analys of Power
Systems by J.Arrillaga and C.P. Arnold*

.. code:: python

   import os
   import GridCalEngine.api as gce

   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'South Island of New Zealand.gridcal')

   grid = gce.open_file(filename=fname)

   pf_options = gce.PowerFlowOptions()
   pf = gce.PowerFlowDriver(grid, pf_options)
   pf.run()

   fault_index = 2
   sc_options = gce.ShortCircuitOptions(bus_index=fault_index,
                                        fault_type=gce.FaultType.LG)

   sc = gce.ShortCircuitDriver(grid, options=sc_options,
                               pf_options=pf_options,
                               pf_results=pf.results)
   sc.run()

   print("Short circuit power: ", sc.results.SCpower[fault_index])

Output:

.. code:: text

   Short circuit power:  -217.00 MW - 680.35j MVAr

Sequence voltage, currents and powers are also available.

Continuation power flow
~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   import os
   from matplotlib import pyplot as plt
   import GridCalEngine.api as gce
   plt.style.use('fivethirtyeight')

   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'South Island of New Zealand.gridcal')

   # open the grid file
   main_circuit = gce.FileOpen(fname).open()

   # we need to initialize with a power flow solution
   pf_options = gce.PowerFlowOptions()
   power_flow = gce.PowerFlowDriver(grid=main_circuit, options=pf_options)
   power_flow.run()

   # declare the CPF options
   vc_options = gce.ContinuationPowerFlowOptions(step=0.001,
                                                 approximation_order=gce.CpfParametrization.ArcLength,
                                                 adapt_step=True,
                                                 step_min=0.00001,
                                                 step_max=0.2,
                                                 error_tol=1e-3,
                                                 tol=1e-6,
                                                 max_it=20,
                                                 stop_at=gce.CpfStopAt.Full,
                                                 verbose=False)

   # We compose the target direction
   base_power = power_flow.results.Sbus / main_circuit.Sbase
   vc_inputs = gce.ContinuationPowerFlowInput(Sbase=base_power,
                                              Vbase=power_flow.results.voltage,
                                              Starget=base_power * 2)

   # declare the CPF driver and run
   vc = gce.ContinuationPowerFlowDriver(circuit=main_circuit,
                                        options=vc_options,
                                        inputs=vc_inputs,
                                        pf_options=pf_options)
   vc.run()

   # plot the results
   fig = plt.figure(figsize=(18, 6))

   ax1 = fig.add_subplot(121)
   res = vc.results.mdl(gce.ResultTypes.BusActivePower)
   res.plot(ax=ax1)

   ax2 = fig.add_subplot(122)
   res = vc.results.mdl(gce.ResultTypes.BusVoltage)
   res.plot(ax=ax2)

   plt.tight_layout()

.. figure:: pics%2Fcpf_south_island_new_zealand.png
   :alt: cpf_south_island_new_zealand.png

   cpf_south_island_new_zealand.png

Contingency analysis
~~~~~~~~~~~~~~~~~~~~

GriCal has contingency simulations, and it features a quite flexible way
of defining contingencies. Firs you define a contingency group, and then
define individual events that are assigned to that contingency group.
THe simulation then tries all the contingency groups and apply the
events registered in each group:

.. code:: python

   import os
   from GridCalEngine.api import *
   import GridCalEngine.basic_structures as bs

   folder = os.path.join('..', 'Grids_and_profiles', 'grids')
   fname = os.path.join(folder, 'IEEE 5 Bus.xlsx')

   main_circuit = FileOpen(fname).open()

   branches = main_circuit.get_branches()

   # manually generate the contingencies
   for i, br in enumerate(branches):
       # add a contingency group
       group = ContingencyGroup(name="contingency {}".format(i+1))
       main_circuit.add_contingency_group(group)

       # add the branch contingency to the groups, only groups are failed at once
       con = Contingency(device_idtag=br.idtag, name=br.name, group=group)
       main_circuit.add_contingency(con)

   # add a special contingency
   group = ContingencyGroup(name="Special contingency")
   main_circuit.add_contingency_group(group)
   main_circuit.add_contingency(Contingency(device_idtag=branches[3].idtag,
                                            name=branches[3].name, group=group))
   main_circuit.add_contingency(Contingency(device_idtag=branches[5].idtag,
                                            name=branches[5].name, group=group))

   pf_options = PowerFlowOptions(solver_type=SolverType.NR)

   # declare the contingency options
   options_ = ContingencyAnalysisOptions(distributed_slack=True,
                                         correct_values=True,
                                         use_provided_flows=False,
                                         Pf=None,
                                         pf_results=None,
                                         engine=bs.ContingencyEngine.PowerFlow,
                                         # if no power flow options are provided
                                         # a linear power flow is used
                                         pf_options=pf_options)

   linear_multiple_contingencies = LinearMultiContingencies(grid=main_circuit)

   simulation = ContingencyAnalysisDriver(grid=main_circuit,
                                          options=options_,
                                          linear_multiple_contingencies=linear_multiple_contingencies)

   simulation.run()

   # print results
   df = simulation.results.mdl(ResultTypes.BranchActivePowerFrom).to_df()
   print("Contingency flows:\n", df)

Output:

.. code:: text

   Contingency flows:
                          Branch 0-1  Branch 0-3  Branch 0-4  Branch 1-2  Branch 2-3  Branch 3-4
   # contingency 1          0.000000  322.256814 -112.256814 -300.000000 -277.616985 -350.438026
   # contingency 2        314.174885    0.000000 -104.174887   11.387545   34.758624 -358.359122
   # contingency 3        180.382705   29.617295    0.000000 -120.547317  -97.293581 -460.040537
   # contingency 4        303.046401  157.540574 -250.586975    0.000000   23.490000 -214.130663
   # contingency 5        278.818887  170.710914 -239.529801  -23.378976    0.000000 -225.076976
   # contingency 6        323.104522  352.002620 -465.107139   20.157096   43.521763    0.000000
   # Special contingency  303.046401  372.060738 -465.107139    0.000000   23.490000    0.000000

This simulation can also be done for time series.

State estimation
~~~~~~~~~~~~~~~~

Now lets program the example from the state estimation reference book
*State Estimation in Electric Power Systems by A. Monticelli*.

.. code:: python

   from GridCalEngine.api import *

   m_circuit = MultiCircuit()

   b1 = Bus('B1', is_slack=True)
   b2 = Bus('B2')
   b3 = Bus('B3')

   br1 = Line(b1, b2, 'Br1', r=0.01, x=0.03, rate=100.0)
   br2 = Line(b1, b3, 'Br2', r=0.02, x=0.05, rate=100.0)
   br3 = Line(b2, b3, 'Br3', r=0.03, x=0.08, rate=100.0)

   # add measurements
   br1.measurements.append(Measurement(0.888, 0.008, MeasurementType.Pflow))
   br2.measurements.append(Measurement(1.173, 0.008, MeasurementType.Pflow))

   b2.measurements.append(Measurement(-0.501, 0.01, MeasurementType.Pinj))

   br1.measurements.append(Measurement(0.568, 0.008, MeasurementType.Qflow))
   br2.measurements.append(Measurement(0.663, 0.008, MeasurementType.Qflow))

   b2.measurements.append(Measurement(-0.286, 0.01, MeasurementType.Qinj))

   b1.measurements.append(Measurement(1.006, 0.004, MeasurementType.Vmag))
   b2.measurements.append(Measurement(0.968, 0.004, MeasurementType.Vmag))

   m_circuit.add_bus(b1)
   m_circuit.add_bus(b2)
   m_circuit.add_bus(b3)

   m_circuit.add_branch(br1)
   m_circuit.add_branch(br2)
   m_circuit.add_branch(br3)

   # Declare the simulation driver and run
   se = StateEstimation(circuit=m_circuit)
   se.run()

   print(se.results.get_bus_df())
   print(se.results.get_branch_df())

Output:

.. code:: text

             Vm        Va         P        Q
   B1  0.999629  0.000000  2.064016  1.22644
   B2  0.974156 -1.247547  0.000000  0.00000
   B3  0.943890 -2.745717  0.000000  0.00000

                Pf         Qf   Pt   Qt    loading
   Br1   89.299199  55.882169  0.0  0.0  55.882169
   Br2  117.102446  66.761871  0.0  0.0  66.761871
   Br3   38.591163  22.775597  0.0  0.0  22.775597
