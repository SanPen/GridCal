import os
import GridCalEngine.api as gce
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import run_nonlinear_opf, ac_optimal_power_flow
from GridCalEngine.Simulations.OPF.linear_opf_ts import run_linear_opf_ts
from GridCalEngine.enumerations import TransformerControlType, AcOpfMode, ReactivePowerControlMode
from GridCalEngine.Simulations.NodalCapacity.nodal_capacity_ts_driver import NodalCapacityTimeSeriesDriver
from GridCalEngine.Simulations.NodalCapacity.nodal_capacity_options import NodalCapacityOptions
import numpy as np
import pandas as pd
from GridCalEngine.enumerations import NodalCapacityMethod


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
    bus1 = gce.Bus('Bus 1', Vnom=20)
    # bus1.is_slack = True  # we may mark the bus a slack
    grid.add_bus(bus1)

    # add a generator to the bus 1
    gen1 = gce.Generator('Slack Generator', vset=1.0, Pmin=0, Pmax=1000,
                         Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)

    grid.add_generator(bus1, gen1)

    # add bus 2 with a load attached
    bus2 = gce.Bus('Bus 2', Vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

    # add bus 3 with a load attached
    bus3 = gce.Bus('Bus 3', Vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))

    # add bus 4 with a load attached
    bus4 = gce.Bus('Bus 4', Vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

    # add bus 5 with a load attached
    bus5 = gce.Bus('Bus 5', Vnom=20)
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
                                              ips_iterations=50, verbose=1, acopf_mode=AcOpfMode.ACOPFstd)
    res = run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True,
                            optimize_nodal_capacity=True,
                            nodal_capacity_sign=-1.0,
                            capacity_nodes_idx=np.array([5]))


def case14_linear_vs_nonlinear():
    """
    IEEE14
    """
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'IEEE 14 zip costs.gridcal')

    grid = gce.FileOpen(file_path).open()

    # Nonlinear OPF
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, ips_tolerance=1e-8,
                                              ips_iterations=50, verbose=1, acopf_mode=AcOpfMode.ACOPFstd)
    res = run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True,
                            optimize_nodal_capacity=True,
                            nodal_capacity_sign=-1.0,
                            capacity_nodes_idx=np.array([10, 11]))

    print('Nonlinear P nodal capacity: ', res.nodal_capacity)

    # Linear OPF
    res = run_linear_opf_ts(grid=grid,
                            optimize_nodal_capacity=True,
                            time_indices=None,
                            nodal_capacity_sign=-1.0,
                            capacity_nodes_idx=np.array([10, 11]))

    print('Linear P nodal capacity: ', res.nodal_capacity_vars.P)
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
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, acopf_mode=AcOpfMode.ACOPFslacks,
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
                                              acopf_mode=AcOpfMode.ACOPFstd, ips_tolerance=1e-7)
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
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True)


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

    # file_path = os.path.join(new_directory, 'REE Grids', 'entrada_a_aopf.raw')
    file_path = 'C:/Users/J/Documents/ree_opf/entrada_a_aopf.raw'

    grid = gce.FileOpen(file_path).open()

    disp_areas = ['A11', 'A15']
    dict_bus_lims = {'21215': [230, 225],
                     '11055': [410, 405],
                     '21075': [230, 225],
                     '25130': [230, 225],
                     '15005': [410, 405],
                     '15015': [410, 405]}
    tol = 1e-4
    vm_cost = 1e2
    i = 0
    for gen in grid.generators:
        if gen.bus.area.name in disp_areas:
            # P limits -> restrict them very close to P
            print(f'Select generator {i}')
            gen.Pmax = gen.P + tol
            gen.Pmin = gen.P - tol
            # Tanmax -> set pf close to 0 to get large tanmax
            gen.Pf = tol
        else:
            gen.enabled_dispatch = False
            gen.Pmax = gen.P + tol
            gen.Pmin = gen.P - tol

        # i += 1

    i = 0
    for bus in grid.buses:
        if bus.code in dict_bus_lims.keys():
            print(f'Grab bus {i}')
            # Change Vm slack cost to enforce limits
            bus.Vm_cost = vm_cost
            # Redo Vm limits from the inputs
            vm_lims = dict_bus_lims[bus.code]
            bus.Vmax = vm_lims[0] / bus.Vnom
            bus.Vmin = vm_lims[1] / bus.Vnom
        # i += 1

    genlist = grid.get_generation_like_devices()
    dic = {gen.code: k for k, gen in enumerate(genlist)}

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, acopf_mode=AcOpfMode.ACOPFstd,
                                              verbose=1, ips_iterations=100, ips_tolerance=1e-8)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=3)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True)


def case_nodalcap():
    cwd = os.getcwd()

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case9.m')

    grid = gce.FileOpen(file_path).open()
    grid.time_profile = pd.DatetimeIndex(["1/1/2020 10:00:00+00:00"])
    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, acopf_mode=AcOpfMode.ACOPFslacks,
                                              verbose=1, ips_iterations=150, ips_tolerance=1e-8)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=3)
    nc_options = NodalCapacityOptions(opf_options=opf_options, capacity_nodes_idx=np.array([2, 3, 6]),
                                      nodal_capacity_sign=-1.0, method=NodalCapacityMethod.NonlinearOptimization)
    case = NodalCapacityTimeSeriesDriver(grid=grid, time_indices=np.array([0]), options=nc_options)
    case.run()
    # run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=True, pf_init=True)


if __name__ == '__main__':
    # example_3bus_acopf()
    # case_3bus()
    # linn5bus_example()
    # two_grids_of_3bus()
    # case9()
    case14_linear_vs_nonlinear()
    # case14()
    # case_gb()
    # case6ww()
    # case_pegase89()
    # case300()
    # casepegase13k()
    #  casehvdc()
    # caseREE()
    # case_nodalcap()
