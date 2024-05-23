"""
This example is coming from the book:
Power System Load Flow Analysis - Lynn Powell

The added profile is just to demonstrate how to create load profiles properly

Author: Santiago Peñate Vera (September 2018)
"""
from GridCalEngine.api import *
from GridCalEngine.Devices import Bus
from GridCalEngine.Devices import Generator
from GridCalEngine.Devices import Load
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_driver import PowerFlowTimeSeriesDriver


def main():
    ####################################################################################################################
    # Define the circuit
    #
    # A circuit contains all the grid information regardless of the islands formed or the amount of devices
    ####################################################################################################################

    # create a circuit

    grid = MultiCircuit(name='lynn 5 bus')
    a1 = Area('Area1')
    z1 = Zone('Zone1')
    s1 = Substation('S1')

    grid.add_area(a1)
    grid.add_zone(z1)
    grid.add_substation(s1)

    # let's create a master profile

    st = datetime.datetime(2020, 1, 1)
    dates = [st + datetime.timedelta(hours=i) for i in range(24)]
    time_array = pd.to_datetime(dates)
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
               Vnom=10,  # Nominal voltage in kV
               vmin=0.9,  # Bus minimum voltage in per unit
               vmax=1.1,  # Bus maximum voltage in per unit
               xpos=0,  # Bus x position in pixels
               ypos=0,  # Bus y position in pixels
               height=0,  # Bus height in pixels
               width=0,  # Bus width in pixels
               active=True,  # Is the bus active?
               is_slack=False,  # Is this bus a slack bus?
               area=a1,  # Area (for grouping purposes only)
               zone=z1,  # Zone (for grouping purposes only)
               substation=s1  # Substation (for grouping purposes only)
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
                   P=0.0,  # Active power in MW, since this generator is used to set the slack , is 0
                   vset=1.0,  # Voltage set point to control
                   Qmin=-9999,  # minimum reactive power in MVAr
                   Qmax=9999,  # Maximum reactive power in MVAr
                   Snom=9999,  # Nominal power in MVA
                   active=True  # Is active?
                   )
    grid.add_generator(bus1, g1)

    ####################################################################################################################
    # Add the lines
    ####################################################################################################################

    br1 = Line(bus_from=bus1,
               bus_to=bus2,
               name='Line 1-2',
               r=0.05,  # resistance of the pi model in per unit
               x=0.11,  # reactance of the pi model in per unit
               b=0.02,  # susceptance of the pi model in per unit
               rate=50,  # Rate in MVA
               active=True,  # is the branch active?
               mttf=0,  # Mean time to failure
               mttr=0,  # Mean time to recovery
               length=1,  # Length in km (to be used with templates)
               )
    grid.add_line(br1)

    grid.add_line(Line(bus1, bus3, name='Line 1-3', r=0.05, x=0.11, b=0.02, rate=50))
    grid.add_line(Line(bus1, bus5, name='Line 1-5', r=0.03, x=0.08, b=0.02, rate=80))
    grid.add_line(Line(bus2, bus3, name='Line 2-3', r=0.04, x=0.09, b=0.02, rate=3))
    grid.add_line(Line(bus2, bus5, name='Line 2-5', r=0.04, x=0.09, b=0.02, rate=10))
    grid.add_line(Line(bus3, bus4, name='Line 3-4', r=0.06, x=0.13, b=0.03, rate=30))
    grid.add_line(Line(bus4, bus5, name='Line 4-5', r=0.04, x=0.09, b=0.02, rate=30))

    FileSave(grid, 'lynn5node.gridcal').save()

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

    writer = pd.ExcelWriter('Results.xlsx')  # pylint: disable=abstract-class-instantiated
    # now, let's compose a nice DataFrame with the voltage results
    headers = ['Vm (p.u.)', 'Va (Deg)', 'Vre', 'Vim']
    Vm = np.abs(pf.results.voltage)
    Va = np.angle(pf.results.voltage, deg=True)
    Vre = pf.results.voltage.real
    Vim = pf.results.voltage.imag
    data = np.c_[Vm, Va, Vre, Vim]
    v_df = pd.DataFrame(data=data, columns=headers, index=grid.get_bus_names())
    # print('\n', v_df)
    v_df.to_excel(writer, sheet_name='V')

    # Let's do the same for the branch results
    headers = ['Loading (%)', 'Current(p.u.)', 'Power (MVA)']
    loading = np.abs(pf.results.loading) * 100
    current = np.abs(pf.results.If)
    power = np.abs(pf.results.Sf)
    data = np.c_[loading, current, power]
    br_df = pd.DataFrame(data=data, columns=headers, index=grid.get_branch_names_wo_hvdc())
    br_df.to_excel(writer, sheet_name='Br')

    # Finally the execution metrics
    print('\nError:', pf.results.error)
    print('Elapsed time (s):', pf.results.elapsed, '\n')

    # print(tabulate(v_df, tablefmt="pipe", headers=v_df.columns.values))
    # print()
    # print(tabulate(br_df, tablefmt="pipe", headers=br_df.columns.values))

    ####################################################################################################################
    # Run a time series power flow simulation
    ####################################################################################################################

    ts = PowerFlowTimeSeriesDriver(grid=grid,
                                   options=pf_options,
                                   opf_time_series_results=None,
                                   time_indices=grid.get_all_time_indices())

    ts.run()

    print()
    print('-' * 200)
    print('Time series')
    print('-' * 200)
    print('Voltage time series')
    df_voltage = pd.DataFrame(data=np.abs(ts.results.voltage), columns=grid.get_bus_names(), index=grid.time_profile)
    df_voltage.to_excel(writer, sheet_name='Vts')
    writer.close()


if __name__ == '__main__':
    main()
