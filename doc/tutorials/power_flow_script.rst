.. _power_flow_scrip:

Create a grid and run a time series power flow
--------------------------------------------------

In this example we are going to create a a 5-bus grid from scratch, create fictitious load and generation profiles
and then run a power flow and a time series power flow. Finally the results will be stored in an excel file.

.. code-block:: python

    import numpy as np
    import pandas as pd
    import datetime as dt
    from GridCal.Engine import *

    ####################################################################################################################
    # Define the circuit
    #
    # A circuit contains all the grid information regardless of the islands formed or the amount of devices
    ####################################################################################################################

    # create a circuit

    grid = MultiCircuit(name='lynn 5 bus')

    # let's create a master profile
    date0 = dt.datetime(2021, 1, 1)
    time_array = pd.DatetimeIndex([date0 + dt.timedelta(hours=i) for i in range(24)])
    x = np.linspace(-np.pi, np.pi, len(time_array))
    y = np.abs(np.sin(x))
    df_0 = pd.DataFrame(data=y, index=time_array)  # complex values

    # set the grid master time profile
    grid.time_profile = df_0.index

    ####################################################################################################################
    # Define the buses
    ####################################################################################################################
    # I will define this bus with all the properties so you see
    bus1 = Bus(name='Bus1',
               vnom=10,   # Nominal voltage in kV
               vmin=0.9,  # Bus minimum voltage in per unit
               vmax=1.1,  # Bus maximum voltage in per unit
               xpos=0,    # Bus x position in pixels
               ypos=0,    # Bus y position in pixels
               height=0,  # Bus height in pixels
               width=0,   # Bus width in pixels
               active=True,   # Is the bus active?
               is_slack=False,  # Is this bus a slack bus?
               area='Defualt',  # Area (for grouping purposes only)
               zone='Default',  # Zone (for grouping purposes only)
               substation='Default'  # Substation (for grouping purposes only)
               )

    # the rest of the buses are defined with the default parameters
    bus2 = Bus(name='Bus2')
    bus3 = Bus(name='Bus3')
    bus4 = Bus(name='Bus4')
    bus5 = Bus(name='Bus5')

    # add the bus objects to the circuit
    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)
    grid.add_bus(bus5)

    ####################################################################################################################
    # Add the loads
    ####################################################################################################################

    # In GridCal, the loads, generators ect are stored within each bus object:

    # we'll define the first load completely
    l2 = Load(name='Load',
              G=0, B=0,  # admittance of the ZIP model in MVA at the nominal voltage
              Ir=0, Ii=0,  # Current of the ZIP model in MVA at the nominal voltage
              P=40, Q=20,  # Power of the ZIP model in MVA
              active=True,  # Is active?
              mttf=0.0,  # Mean time to failure
              mttr=0.0  # Mean time to recovery
              )
    grid.add_load(bus2, l2)

    # Define the others with the default parameters
    grid.add_load(bus3, Load(P=25, Q=15))
    grid.add_load(bus4, Load(P=40, Q=20))
    grid.add_load(bus5, Load(P=50, Q=20))

    ####################################################################################################################
    # Add the generators
    ####################################################################################################################

    g1 = Generator(name='gen',
                   active_power=0.0,  # Active power in MW, since this generator is used to set the slack , is 0
                   voltage_module=1.0,  # Voltage set point to control
                   Qmin=-9999,  # minimum reactive power in MVAr
                   Qmax=9999,  # Maximum reactive power in MVAr
                   Snom=9999,  # Nominal power in MVA
                   power_prof=None,  # power profile
                   vset_prof=None,  # voltage set point profile
                   active=True  # Is active?
                   )
    grid.add_generator(bus1, g1)

    ####################################################################################################################
    # Add the lines
    ####################################################################################################################

    br1 = Branch(bus_from=bus1,
                 bus_to=bus2,
                 name='Line 1-2',
                 r=0.05,  # resistance of the pi model in per unit
                 x=0.11,  # reactance of the pi model in per unit
                 g=1e-20,  # conductance of the pi model in per unit
                 b=0.02,  # susceptance of the pi model in per unit
                 rate=50,  # Rate in MVA
                 tap=1.0,  # Tap value (value close to 1)
                 shift_angle=0,  # Tap angle in radians
                 active=True,  # is the branch active?
                 mttf=0,  # Mean time to failure
                 mttr=0,  # Mean time to recovery
                 branch_type=BranchType.Line,  # Branch type tag
                 length=1,  # Length in km (to be used with templates)
                 template=BranchTemplate()  # Branch template (The default one is void)
                 )
    grid.add_branch(br1)

    grid.add_branch(Branch(bus1, bus3, name='Line 1-3', r=0.05, x=0.11, b=0.02, rate=50))
    grid.add_branch(Branch(bus1, bus5, name='Line 1-5', r=0.03, x=0.08, b=0.02, rate=80))
    grid.add_branch(Branch(bus2, bus3, name='Line 2-3', r=0.04, x=0.09, b=0.02, rate=3))
    grid.add_branch(Branch(bus2, bus5, name='Line 2-5', r=0.04, x=0.09, b=0.02, rate=10))
    grid.add_branch(Branch(bus3, bus4, name='Line 3-4', r=0.06, x=0.13, b=0.03, rate=30))
    grid.add_branch(Branch(bus4, bus5, name='Line 4-5', r=0.04, x=0.09, b=0.02, rate=30))

    ####################################################################################################################
    # Overwrite the default profiles with the custom ones
    ####################################################################################################################

    for load in grid.get_loads():
        load.P_prof = load.P * df_0.values[:, 0]
        load.Q_prof = load.Q * df_0.values[:, 0]

    for gen in grid.get_static_generators():
        gen.P_prof = gen.Q * df_0.values[:, 0]
        gen.Q_prof = gen.Q * df_0.values[:, 0]

    for gen in grid.get_generators():
        gen.P_prof = gen.P * df_0.values[:, 0]

    ####################################################################################################################
    # Run a power flow simulation
    ####################################################################################################################

    # We need to specify power flow options
    pf_options = PowerFlowOptions(solver_type=SolverType.NR,  # Base method to use
                                  verbose=False,  # Verbose option where available
                                  tolerance=1e-6,  # power error in p.u.
                                  max_iter=25,  # maximum iteration number
                                  control_q=True  # if to control the reactive power
                                  )

    # Declare and execute the power flow simulation
    pf = PowerFlowDriver(grid, pf_options)
    pf.run()

    writer = pd.ExcelWriter('Results.xlsx')
    # now, let's compose a nice DataFrame with the voltage results
    headers = ['Vm (p.u.)', 'Va (Deg)', 'Vre', 'Vim']
    Vm = np.abs(pf.results.voltage)
    Va = np.angle(pf.results.voltage, deg=True)
    Vre = pf.results.voltage.real
    Vim = pf.results.voltage.imag
    data = np.c_[Vm, Va, Vre, Vim]
    v_df = pd.DataFrame(data=data, columns=headers, index=grid.bus_names)
    # print('\n', v_df)
    v_df.to_excel(writer, sheet_name='V')

    # Let's do the same for the branch results
    headers = ['Loading (%)', 'Power from (MVA)']
    loading = np.abs(pf.results.loading) * 100
    power = np.abs(pf.results.Sf)
    data = np.c_[loading, power]
    br_df = pd.DataFrame(data=data, columns=headers, index=grid.branch_names)
    br_df.to_excel(writer, sheet_name='Br')

    # Finally the execution metrics
    print('\nError:', pf.results.error)
    print('Elapsed time (s):', pf.results.elapsed, '\n')

    ####################################################################################################################
    # Run a time series power flow simulation
    ####################################################################################################################

    ts = TimeSeries(grid=grid,
                    options=pf_options,
                    opf_time_series_results=None,
                    start_=0,
                    end_=None)

    ts.run()

    print()
    print('-' * 200)
    print('Time series')
    print('-' * 200)
    print('Voltage time series')
    df_voltage = pd.DataFrame(data=np.abs(ts.results.voltage), columns=grid.bus_names, index=grid.time_profile)
    df_voltage.to_excel(writer, sheet_name='Vts')
    print(df_voltage)

    writer.close()




**Output**


Node voltage results
^^^^^^^^^^^^^^^^^^^^^^^

+-------+-------------+--------------+-------------+--------------+
| Buses | Vm (p.u.)   | Va (Deg)     | Vre         | Vim          |
+-------+-------------+--------------+-------------+--------------+
| Bus1  | 1           | 0            | 1           | 0            |
+-------+-------------+--------------+-------------+--------------+
| Bus2  | 0.955324031 | -2.404433748 | 0.954482951 | -0.04007868  |
+-------+-------------+--------------+-------------+--------------+
| Bus3  | 0.954837779 | -2.363419791 | 0.954025558 | -0.039375371 |
+-------+-------------+--------------+-------------+--------------+
| Bus4  | 0.933365539 | -3.648173178 | 0.931474151 | -0.059389693 |
+-------+-------------+--------------+-------------+--------------+
| Bus5  | 0.953415236 | -2.688383579 | 0.952365912 | -0.044718922 |
+-------+-------------+--------------+-------------+--------------+

Branch results
^^^^^^^^^^^^^^^^

+----------+-------------+-------------+
| Branches | Loading (%) | Power (MVA) |
+----------+-------------+-------------+
| Line 1-2 | 99.58136275 | 49.79068138 |
+----------+-------------+-------------+
| Line 1-3 | 99.36456725 | 49.68228363 |
+----------+-------------+-------------+
| Line 1-5 | 95.04116648 | 76.03293318 |
+----------+-------------+-------------+
| Line 2-3 | 55.46650524 | 1.663995158 |
+----------+-------------+-------------+
| Line 2-5 | 50.59527577 | 5.059527578 |
+----------+-------------+-------------+
| Line 3-4 | 65.51051038 | 19.65315312 |
+----------+-------------+-------------+
| Line 4-5 | 80.98428606 | 24.29528582 |
+----------+-------------+-------------+

Time series voltage results
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

+---------------------+---+-------------------+-------------------+-------------------+-------------------+
|                     | 0 | 1                 | 2                 | 3                 | 4                 |
+=====================+===+===================+===================+===================+===================+
| 2021-01-01 00:00:00 | 1 | 1.00381101279064  | 1.00424197191543  | 1.00531077229584  | 1.00378836624627  |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 01:00:00 | 1 | 0.992441588490943 | 0.992679964919525 | 0.988491902175231 | 0.992012794689127 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 02:00:00 | 1 | 0.981398642072788 | 0.981437075141778 | 0.972128786670522 | 0.980554539794808 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 03:00:00 | 1 | 0.971456488050421 | 0.971303527762746 | 0.957370335293388 | 0.970220247825554 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 04:00:00 | 1 | 0.963385899999827 | 0.963069287324943 | 0.945369318569842 | 0.961818165699366 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 05:00:00 | 1 | 0.957870378716229 | 0.957437491303093 | 0.937155965503371 | 0.956069094792859 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 06:00:00 | 1 | 0.955409893841428 | 0.954923944571358 | 0.933488707758209 | 0.953502548649717 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 07:00:00 | 1 | 0.956236695969423 | 0.955768660165017 | 0.934721255127363 | 0.954365121060115 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 08:00:00 | 1 | 0.960272087492213 | 0.959890281812325 | 0.940733654608167 | 0.958573211183415 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 09:00:00 | 1 | 0.967141368416695 | 0.966901852266799 | 0.950956173297673 | 0.965729383333107 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 10:00:00 | 1 | 0.976240834713852 | 0.976181355516    | 0.964475719702551 | 0.975195498128214 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 11:00:00 | 1 | 0.986831642580487 | 0.98697006969342  | 0.98018286030256  | 0.986194479159182 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 12:00:00 | 1 | 0.998132174820727 | 0.998468584300177 | 0.996913301552821 | 0.997909328746612 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 13:00:00 | 1 | 0.998132174820727 | 0.998468584300178 | 0.996913301552821 | 0.997909328746612 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 14:00:00 | 1 | 0.986831642580487 | 0.986970069693419 | 0.98018286030256  | 0.986194479159182 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 15:00:00 | 1 | 0.976240834713852 | 0.976181355516    | 0.964475719702551 | 0.975195498128214 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 16:00:00 | 1 | 0.967141368416695 | 0.966901852266799 | 0.950956173297673 | 0.965729383333107 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 17:00:00 | 1 | 0.960272087492213 | 0.959890281812325 | 0.940733654608167 | 0.958573211183415 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 18:00:00 | 1 | 0.956236695969423 | 0.955768660165017 | 0.934721255127363 | 0.954365121060115 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 19:00:00 | 1 | 0.955409893841428 | 0.954923944571358 | 0.933488707758209 | 0.953502548649717 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 20:00:00 | 1 | 0.957870378716229 | 0.957437491303093 | 0.937155965503371 | 0.956069094792859 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 21:00:00 | 1 | 0.963385899999827 | 0.963069287324943 | 0.945369318569842 | 0.961818165699366 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 22:00:00 | 1 | 0.971456488050421 | 0.971303527762746 | 0.957370335293389 | 0.970220247825554 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-01 23:00:00 | 1 | 0.981398642072788 | 0.981437075141778 | 0.972128786670522 | 0.980554539794808 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-02 00:00:00 | 1 | 0.992441588490943 | 0.992679964919525 | 0.988491902175231 | 0.992012794689127 |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+
| 2021-01-02 01:00:00 | 1 | 1.00381101279064  | 1.00424197191543  | 1.00531077229584  | 1.00378836624627  |
+---------------------+---+-------------------+-------------------+-------------------+-------------------+