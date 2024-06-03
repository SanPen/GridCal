import os
import sys

sys.path.append('C:/Users/raiya/Documents/8. eRoots/thesis/code/GridCal/src')
import GridCalEngine.api as gce
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.generalised_power_flow import run_nonlinear_opf, \
    ac_optimal_power_flow
from GridCalEngine.enumerations import TransformerControlType, AcOpfMode, ReactivePowerControlMode


def example_3bus_acopf():
    """

    :return:
    """

    grid = gce.MultiCircuit()

    b1 = gce.Bus(is_slack=True)
    b2 = gce.Bus()
    b3 = gce.Bus()

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name='line 1-2', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name='line 2-3', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_1', r=0.001, x=0.05, rate=100))
    # grid.add_line(Line(bus_from=b3, bus_to=b1, name='line 3-1_2', r=0.001, x=0.05, rate=100))

    grid.add_load(b3, gce.Load(name='L3', P=50, Q=40))
    grid.add_generator(b1, gce.Generator('G1', vset=1.00, Cost=1.0, Cost2=2.0))
    grid.add_generator(b2, gce.Generator('G2', P=10, vset=0.995, Cost=1.0, Cost2=3.0))

    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, verbose=1, ips_tolerance=1e-8,
                                              ips_iterations=25)
    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    # print('\n\n', grid.name)
    # print('\tConv:\n', power_flow.results.get_bus_df())
    # print('\tConv:\n', power_flow.results.get_branch_df())

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=3)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True)


def case_3bus():
    """

    :return:
    """

    grid = gce.MultiCircuit()

    b1 = gce.Bus(is_slack=True)
    b2 = gce.Bus()
    b3 = gce.Bus()

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    # grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name='Line 1-2', r=0.001, x=0.05, rate=100))
    # grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name='Line 2-3', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='Line 3-1', r=0.001, x=0.05, rate=100))

    grid.add_load(b3, gce.Load(name='L3', P=50, Q=20))
    grid.add_generator(b1, gce.Generator('G1', vset=1.00, Cost=1.0, Cost2=2.0))
    grid.add_generator(b2, gce.Generator('G2', P=10, vset=0.995, Cost=1.0, Cost2=3.0))

    tr1 = gce.Transformer2W(b1, b2, 'Trafo 1', control_mode=TransformerControlType.PtQt,
                            tap_module=1.01, tap_phase=0.02, r=0.001, x=0.05, tap_phase_max=0.5, tap_module_max=1.1,
                            tap_phase_min=-0.5, tap_module_min=0.9, rate=100)

    grid.add_transformer2w(tr1)

    tr2 = gce.Transformer2W(b2, b3, 'Trafo 2', control_mode=TransformerControlType.PtV,
                            tap_module=1.01, tap_phase=+0.02, r=0.004, x=0.08, tap_phase_max=0.03, tap_module_max=1.02,
                            tap_phase_min=-0.02, tap_module_min=0.98, rate=100)
    grid.add_transformer2w(tr2)

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    # print('\n\n', grid.name)
    # print('\tConv:\n', power_flow.results.get_bus_df())
    # print('\tConv:\n', power_flow.results.get_branch_df())

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, max_iter=50, verbose=3)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, plot_error=True)
    nc = compile_numerical_circuit_at(circuit=grid)


def linn5bus_example():
    """
    Grid from Lynn Powel's book
    """
    # declare a circuit object
    grid = gce.MultiCircuit()

    # Add the buses and the generators and loads attached
    bus1 = gce.Bus('Bus 1', vnom=20)
    # bus1.is_slack = True  # we may mark the bus a slack
    grid.add_bus(bus1)

    # add a generator to the bus 1
    gen1 = gce.Generator('Slack Generator', vset=1.0, Pmin=0, Pmax=1000,
                         Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)

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
    grid.add_line(gce.Line(bus1, bus2, name='line 1-2', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus3, name='line 1-3', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus5, name='line 1-5', r=0.03, x=0.08, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus2, bus3, name='line 2-3', r=0.04, x=0.09, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus2, bus5, name='line 2-5', r=0.04, x=0.09, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus3, bus4, name='line 3-4', r=0.06, x=0.13, b=0.03, rate=1000))
    grid.add_line(gce.Line(bus4, bus5, name='line 4-5', r=0.04, x=0.09, b=0.02, rate=1000))

    tr1 = gce.Transformer2W(bus1, bus2, 'Trafo 1', control_mode=TransformerControlType.PtQt,
                            tap_module=0.95, tap_phase=-0.02, r=0.05, x=0.11, tap_phase_max=0.5, tap_module_max=1.1,
                            tap_phase_min=-0.5, tap_module_min=0.9, rate=1000)

    # grid.add_transformer2w(tr1)
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, verbose=1, ips_tolerance=1e-8,
                                              ips_iterations=25)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True)


def linn5bus_example2():
    """
    Grid from Lynn Powel's book
    """
    # declare a circuit object
    grid = gce.MultiCircuit()

    # Add the buses and the generators and loads attached
    bus1 = gce.Bus('Bus 1', vnom=20)
    # bus1.is_slack = True  # we may mark the bus a slack
    grid.add_bus(bus1)

    # add a generator to the bus 1
    gen1 = gce.Generator('Slack Generator', vset=1.0, Pmin=0, Pmax=1000,
                         Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)

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
    grid.add_line(gce.Line(bus1, bus2, name='line 1-2', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus3, name='line 1-3', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus5, name='line 1-5', r=0.03, x=0.08, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus2, bus3, name='line 2-3', r=0.04, x=0.09, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus2, bus5, name='line 2-5', r=0.04, x=0.09, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus3, bus4, name='line 3-4', r=0.06, x=0.13, b=0.03, rate=1000))
    grid.add_line(gce.Line(bus4, bus5, name='line 4-5', r=0.04, x=0.09, b=0.02, rate=1000))

    tr1 = gce.Transformer2W(bus1, bus2, 'Trafo 1', control_mode=TransformerControlType.PtQt,
                            tap_module=0.95, tap_phase=-0.02, r=0.05, x=0.11, tap_phase_max=0.5, tap_module_max=1.1,
                            tap_phase_min=-0.5, tap_module_min=0.9, rate=1000)

    # grid.add_transformer2w(tr1)`
    # pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def pegase_example():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'Grids_and_profiles/grids/case89pegase.m'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def pegase2k_example():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'Grids_and_profiles/grids/2869 Pegase.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def bus300_example():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'Grids_and_profiles/grids/10_bus_hvdc.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)
    results.converged

    # print(results.get_bus_df())
    # print()
    # print(results.get_branch_df())
    # print("Error:", results.error)


def ieee5bus_example():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'Grids_and_profiles/grids/IEEE 5 Bus.xlsx'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def case14_example():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/14bus_shunt.gridcal'
    file_path = 'Grids_and_profiles/grids/case14.m'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def case14_example_noshunt():
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/14bus_no_shunt.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def acdc2bus_example():
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/2busACDC.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def acdc3bus_example():
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/3busACDC.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def acdc4bus_example():
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/4busACDC.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def pegase2869_example():
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/2869 Pegase.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def two_grids_of_3bus():
    """
    3 bus grid two times
    for solving islands at the same time
    """
    grid = gce.MultiCircuit()

    # 3 bus grid
    b1 = gce.Bus(is_slack=True)
    b2 = gce.Bus()
    b3 = gce.Bus()

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name='line 1-2', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name='line 2-3', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_1', r=0.001, x=0.05, rate=100))
    # grid.add_line(Line(bus_from=b3, bus_to=b1, name='line 3-1_2', r=0.001, x=0.05, rate=100))

    grid.add_load(b3, gce.Load(name='L3', P=50, Q=20))
    grid.add_generator(b1, gce.Generator('G1', vset=1.00, Cost=1.0, Cost2=2.0))
    grid.add_generator(b2, gce.Generator('G2', P=10, vset=0.995, Cost=1.0, Cost2=3.0))

    # 3 bus grid
    b11 = gce.Bus(is_slack=True)
    b21 = gce.Bus()
    b31 = gce.Bus()

    grid.add_bus(b11)
    grid.add_bus(b21)
    grid.add_bus(b31)

    grid.add_line(gce.Line(bus_from=b11, bus_to=b21, name='line 1-2 (2)', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b21, bus_to=b31, name='line 2-3 (2)', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b31, bus_to=b11, name='line 3-1 (2)', r=0.001, x=0.05, rate=100))

    grid.add_load(b31, gce.Load(name='L3 (2)', P=50, Q=20))
    grid.add_generator(b11, gce.Generator('G1 (2)', vset=1.00, Cost=1.0, Cost2=1.5))
    grid.add_generator(b21, gce.Generator('G2 (2)', P=10, vset=0.995, Cost=1.0, Cost2=1.0))

    # hvdc = gce.HvdcLine(b11, b1, r=0.001, rate=0.4, dispatchable=0, Pset=0.05)
    # grid.add_hvdc(hvdc)
    hvdc2 = gce.HvdcLine(b11, b1, r=0.001, rate=100)
    # grid.add_hvdc(hvdc2)

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    # print('\n\n', grid.name)
    # print('\tConv:\n', power_flow.results.get_bus_df())
    # print('\tConv:\n', power_flow.results.get_branch_df())

    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, verbose=1, ips_tolerance=1e-8,
                                              ips_iterations=25)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=3, max_iter=25)
    # run_nonlinear_opf(grid=grid, pf_options=pf_options, plot_error=True)
    island = compile_numerical_circuit_at(circuit=grid, t_idx=None)

    island_res = ac_optimal_power_flow(nc=island,
                                       pf_options=pf_options,
                                       opf_options=opf_options,
                                       debug=False,
                                       use_autodiff=False,
                                       plot_error=True)


def case9():
    """
    IEEE9
    """
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case9.m')

    grid = gce.FileOpen(file_path).open()
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, ips_tolerance=1e-8,
                                              ips_iterations=50, verbose=1, acopf_mode=AcOpfMode.ACOPFslacks)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=False)
    print('')


def case14():
    """
    IEEE14
    """
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')

    grid = gce.FileOpen(file_path).open()

    # grid.transformers2w[0].control_mode = TransformerControlType.PtQt
    # grid.transformers2w[1].control_mode = TransformerControlType.Pf
    # grid.transformers2w[2].control_mode = TransformerControlType.V

    # grid.delete_line(grid.lines[0])
    # grid.delete_line(grid.lines[1])
    for ll in range(len(grid.lines)):
        grid.lines[ll].monitor_loading = True

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, control_q=ReactivePowerControlMode.NoControl)
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, acopf_mode=AcOpfMode.ACOPFstd,
                                              ips_tolerance=1e-6, ips_iterations=50, verbose=1)
    res = run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True)
    print('')


def case_gb():
    """
    GB
    """
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'GB Network.gridcal')

    grid = gce.FileOpen(file_path).open()
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, verbose=1, ips_iterations=100,
                                              acopf_mode=AcOpfMode.ACOPFslacks, ips_tolerance=1e-8)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True)


def case_pegase89():
    """
    Pegase89
    """
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case89pegase.m')

    grid = gce.FileOpen(file_path).open()
    # nc = compile_numerical_circuit_at(grid)
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, verbose=1, ips_iterations=100,
                                              acopf_mode=AcOpfMode.ACOPFslacks, ips_tolerance=1e-7)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
    # ac_optimal_power_flow(nc=nc, pf_options=pf_options, plot_error=True)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True)
    grid.get_bus_branch_connectivity_matrix()
    nc = compile_numerical_circuit_at(grid)
    print('')


def case300():
    """
    case300.m
    """
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case300.m')

    grid = gce.FileOpen(file_path).open()
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, max_iter=50)
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, verbose=1, ips_iterations=100,
                                              acopf_mode=AcOpfMode.ACOPFslacks)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=False)


def casepegase13k():
    """
    Solves for pf_init=False in about a minute and 130 iterations.
    """
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case13659pegase.m')

    grid = gce.FileOpen(file_path).open()

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, verbose=1, ips_tolerance=1e-6,
                                              ips_iterations=70)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=3)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True)


def casehvdc():
    """
    IEEE14
    """
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'entrada_a_aopf.raw')

    grid = gce.FileOpen(file_path).open()

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, acopf_mode=AcOpfMode.ACOPFslacks,
                                              verbose=1, ips_iterations=150, ips_tolerance=1e-8)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=3)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True)


def caseREE():
    """
    IEEE14
    """
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..', '..'))

    file_path = os.path.join(new_directory, 'REE Grids', 'entrada_a_aopf.raw')

    grid = gce.FileOpen(file_path).open()

    disp_areas = ['A11', 'A15']
    dict_bus_lims = {'21215': [230, 225],
                     '11055': [410, 405],
                     '21075': [230, 225],
                     '25130': [230, 225],
                     '15005': [410, 405],
                     '15015': [410, 405]}
    tol = 1e-4
    vm_cost = 1e4
    i = 0
    for gen in grid.generators:
        if gen.bus.area.name in disp_areas:
            # P limits -> restrict them very close to P
            print(i)
            gen.Pmax = gen.P + tol
            gen.Pmin = gen.P - tol
            # Tanmax -> set pf close to 0 to get large tanmax
            gen.Pf = tol
        i += 1
    i = 0
    print('reset i')
    for bus in grid.buses:
        if bus.code in dict_bus_lims.keys():
            print(i)
            # Increase Vm slack cost to enforce limits
            bus.Vm_cost = vm_cost
            # Redo Vm limits from the inputs
            vm_lims = dict_bus_lims[bus.code]
            bus.Vmax = vm_lims[0] / bus.Vnom
            bus.Vmin = vm_lims[1] / bus.Vnom
        i += 1

    genlist = grid.get_generation_like_devices()
    dic = {gen.code: k for k, gen in enumerate(genlist)}

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, acopf_mode=AcOpfMode.ACOPFslacks,
                                              verbose=1, ips_iterations=150, ips_tolerance=1e-8)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=3)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=False)


import os
import GridCalEngine.api as gce


def read_processed_files(log_file_path):
    processed_files = {}
    try:
        with open(log_file_path, 'r') as file:
            for line in file:
                if "Converged" in line or "Exception" in line or "Skipped, timeout" in line:
                    filename, status = line.split(":")[0], line.split(":")[1]
                    processed_files[filename.strip()] = status.strip()
    except FileNotFoundError:
        # If the log file does not exist yet, just return an empty dictionary
        pass
    return processed_files


def test_convergence(directory_path, log_file_path):
    # Read the list of already processed files
    processed_files = read_processed_files(log_file_path)

    # Open the log file for appending so each run adds to the log file instead of overwriting it
    with open(log_file_path, 'a') as log_file:
        for file_name in os.listdir(directory_path):
            if file_name.endswith(('.gridcal', '.m', '.raw', '.xlsx')) and file_name not in processed_files:
                log_file.write(f"{file_name}: Processing...\n")  # Log that processing is starting
                log_file.flush()  # Ensure the entry is written immediately
                full_path = os.path.join(directory_path, file_name)
                try:
                    grid = gce.FileOpen(full_path).open()
                    if grid:
                        pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True)
                        results = gce.power_flow(grid, options=pf_options)
                        result_text = f"{file_name}: Converged={results.converged}\n"
                    else:
                        result_text = f"{file_name}: Failed to load grid\n"
                except Exception as e:
                    result_text = f"{file_name}: Exception={str(e)}\n"
                log_file.write(result_text)  # Write the final result
                log_file.flush()  # Ensure that each entry is written and saved immediately


if __name__ == '__main__':
    # example_3bus_acopf()
    # case_3bus()
    # linn5bus_example() #not using gpf
    # linn5bus_example2() #converges True and accurate to normal Ac pf
    # pegase_example() #Converges True
    # ieee5bus_example() #converges True
    # case14_example_noshunt() #converges true
    # case14_example() #converges True
    # acdc2bus_example() #converges True
    # acdc4bus_example() #converges true

    bus300_example()
    # acdc3bus_example() #problem with the control
    # pegase2k_example() #runs super slow and does not converge

    # two_grids_of_3bus() #does not use gpf
    # case9()
    # case14()
    # case_gb()
    # case6ww()
    # case_pegase89()
    # case300()
    # casepegase13k()
    # casehvdc()
    # caseREE()

    # # Path to your directory containing the grid files
    # directory_path = 'Grids_and_profiles/grids/'
    # # Path where you want to save the log file
    # log_file_path = 'convergence_log.txt'

    # # Call the function
    # test_convergence(directory_path, log_file_path)

    # # If you want to see the contents of the log, you can print them out:
    # with open(log_file_path, 'r') as file:
    #     print(file.read())
