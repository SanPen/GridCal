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
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)

def pegase_example89():
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

def acdc10_example():
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



def fubm_caseHVDC_vt_normalNR():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'Grids_and_profiles/grids/1951 Bus RTE.xlsx'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)

    results = gce.power_flow(grid, options=pf_options)
    results.converged

    print(results.get_bus_df())
    # print()
    # print(results.get_branch_df())
    print("Error:", results.error)
    print("Converged?", results.converged)

def fubm_caseHVDC_vt():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'Grids_and_profiles/grids/IEEE 5 Bus.xlsx'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)
    results.converged

    print(results.get_bus_df())
    print()
    # print(results.get_branch_df())
    print("Error:", results.error)
    print("Converged?", results.converged)


def whatever_func():
    import time
    start = time.time()
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'Grids_and_profiles/grids/IEEE 5 Bus.xlsx'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)
    results.converged

    print(results.get_bus_df())
    
    
    #compare to normal NR
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
    results_normal = gce.power_flow(grid, options=pf_options)
    
    print(results.get_bus_df().loc[:, ['Vm', 'Va']])
    print(results_normal.get_bus_df().loc[:, ['Vm', 'Va']])
    df_diff = abs((results.get_bus_df().loc[:, ['Vm', 'Va']] - results_normal.get_bus_df().loc[:, ['Vm', 'Va']])/ results_normal.get_bus_df().loc[:, ['Vm', 'Va']]) * 100
    print(df_diff)

    #find the largest difference
    print("biggest error:")
    vm_array = df_diff['Vm'].to_numpy()
    va_array = df_diff['Va'].to_numpy()
    print("Vm:", max(vm_array))
    print("Va:", max(va_array))

    end = time.time() - start
    print("Time:", end)


def ieee5bus_example():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'Grids_and_profiles/grids/IEEE 5 Bus.xlsx'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def fumbexample():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'Grids_and_profiles/grids/fubm_caseHVDC_vt.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def fumbexample_w_ourControls():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/fubm_caseHVDC_vt_wControls.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def ieee5_w_ourControls():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/IEEE 5 Bus_wControls.xlsx'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def simple2bus_wOurControls():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/simple2bus.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)

def doubleVSCsystem():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/doubleVSCsystem.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def simple3busacdc_wOurControls():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gridcal_models/simple3busacdc.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)

def threebusacdc():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/3busacdc.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)

def simple3busacdc():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/3busacdc_simple.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def complex6bus():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/complex6bus.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def simple3busacdc_controllingPower_wtrafo():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/3busacdc_simple_powerControl_wtrafo.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def newthing():
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/newthing.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10, max_iter=15)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)

def simple3busacdc_controllingPower_notrafo():
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/3busacdc_simple_powerControl_notrafo.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10, max_iter=15)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)

def simple3busac_pure():
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/3busAC.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)

def simple4busacdc_wTrafo():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/4busacdc_wTrafo.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def simple4busacdc_wControllableTrafo():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/4busacdc_wControllableTrafo.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def simple4busacdc_wControllableTrafo_remoteControl():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/4busacdc_wControllableTrafo_remote.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def simple4busacdc_pure():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/4busacdc.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

    results = gce.power_flow(grid, options=pf_options)

    print(results.get_bus_df())
    print()
    print(results.get_branch_df())
    print("Error:", results.error)


def simple3busacdc_controllingPower():
    # file_path = 'C:/Users/raiya/Desktop/gridcal_models/pegase89.gridcal'
    file_path = 'C:/Users/raiya/Desktop/gpf_testers/3busacdc_simple_powerControl.gridcal'
    grid = gce.FileOpen(file_path).open()
    assert grid is not None
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.GENERALISED, verbose=1, tolerance=1e-10)

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


import os

def whatever(directory_path, file_names, log_path):
    # Open the log file for appending so each run adds to the log file instead of overwriting it
    with open(log_path, 'a') as log_file:
        for file_name in file_names:
            full_path = os.path.join(directory_path, file_name)
            log_file.write(f"{file_name}: Processing...\n")  # Log that processing is starting
            log_file.flush()  # Ensure the entry is written immediately
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


def whatever_traditionalPF(directory_path, file_names, log_path):
    # Open the log file for appending so each run adds to the log file instead of overwriting it
    with open(log_path, 'a') as log_file:
        for file_name in file_names:
            full_path = os.path.join(directory_path, file_name)
            log_file.write(f"{file_name}: Processing...\n")  # Log that processing is starting
            log_file.flush()  # Ensure the entry is written immediately
            try:
                grid = gce.FileOpen(full_path).open()
                if grid:
                    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
                    results = gce.power_flow(grid, options=pf_options)
                    result_text = f"{results.get_bus_df()}\n"
                    result_text += f"{file_name}: Converged={results.converged}\n"
                else:
                    result_text = f"{file_name}: Failed to load grid\n"
            except Exception as e:
                result_text = f"{file_name}: Exception={str(e)}\n"
            
            log_file.write(result_text)  # Write the final result
            log_file.flush()  # Ensure that each entry is written and saved immediately

def get_gridProperties(directory_path, file_names):
    import os
    import csv
    # CSV file to append the data
    csv_file = 'gridProperties.csv'
    # Open the log file for appending so each run adds to the log file instead of overwriting it
    for file_name in file_names:
        print(file_name)
        full_path = os.path.join(directory_path, file_name)
        # Check if file exists to decide whether to write headers
        
        grid = gce.FileOpen(full_path).open()
        """
        self.lines: List[dev.Line] = list()

        self.dc_lines: List[dev.DcLine] = list()

        self.transformers2w: List[dev.Transformer2W] = list()

        self.hvdc_lines: List[dev.HvdcLine] = list()

        self.vsc_devices: List[dev.VSC] = list()

        self.upfc_devices: List[dev.UPFC] = list()

        self.switch_devices: List[dev.Switch] = list()

        self.transformers3w: List[dev.Transformer3W] = list()

        self.windings: List[dev.Winding] = list()

        self.series_reactances: List[dev.SeriesReactance] = list()

        self.buses: List[dev.Bus] = list()

        self.voltage_levels: List[dev.VoltageLevel] = list()

        # List of loads
        self.loads: List[dev.Load] = list()

        # List of generators
        self.generators: List[dev.Generator] = list()

        # List of External Grids
        self.external_grids: List[dev.ExternalGrid] = list()

        # List of shunts
        self.shunts: List[dev.Shunt] = list()

        # List of batteries
        self.batteries: List[dev.Battery] = list()

        # List of static generators
        self.static_generators: List[dev.StaticGenerator] = list()

        # List of current injections devices
        self.current_injections: List[dev.CurrentInjection] = list()

        # List of linear shunt devices
        self.controllable_shunts: List[dev.ControllableShunt] = list()
        """
        with open(csv_file, 'a', newline='') as file:
            writer = csv.writer(file)
            file_exists = os.path.isfile(csv_file)
            if not file_exists:
                writer.writerow(["Lines", "DC Lines", "2W Transformers", "HVDC Lines", "VSC Devices", "UPFC Devices", "Switch Devices", "3W Transformers", "Windings", "Series Reactances", "Buses", "Voltage Levels", "Loads", "Generators", "External Grids", "Shunts", "Batteries", "Static Generators", "Current Injections", "Controllable Shunts"])
            writer.writerow([len(grid.lines), len(grid.dc_lines), len(grid.transformers2w), len(grid.hvdc_lines), len(grid.vsc_devices), len(grid.upfc_devices), len(grid.switch_devices), len(grid.transformers3w), len(grid.windings), len(grid.series_reactances), len(grid.buses), len(grid.voltage_levels), len(grid.loads), len(grid.generators), len(grid.external_grids), len(grid.shunts), len(grid.batteries), len(grid.static_generators), len(grid.current_injections), len(grid.controllable_shunts)])



def compare_answers(directory_path, txt_file_path, log_path):
    import pandas as pd
    #iterate through all .txt files in txt_file_path
    for file_name in os.listdir(txt_file_path):
        if file_name.endswith('.txt'):
            # Open the log file for appending so each run adds to the log file instead of overwriting it
            with open(log_path, 'a') as log_file:
                #split the file_name using the delimiter :
                #get the first part of the split
                _file_name = file_name.split(".txt")[0]
                #look for the file in the directory_path
                full_path = os.path.join(directory_path, _file_name)
                print(full_path)
                #open the grid and run using normal power flow
                grid = gce.FileOpen(full_path).open()
                pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
                results = gce.power_flow(grid, options=pf_options)
                traditional_pf_results = results.get_bus_df()
                print(traditional_pf_results.head())
                # generalised_pf_results load the file_name
                generalised_pf_results = pd.read_csv(os.path.join(txt_file_path, file_name), skiprows=2, delimiter=r'\s+', header=None)

                #print the shape of the df
                generalised_pf_results.columns = ['Voltage Magnitude', 'Voltage Angle']

                #convert the column 'Voltage Angle' from radian to degrees
                generalised_pf_results['Voltage Angle'] = generalised_pf_results['Voltage Angle'].apply(lambda x: x * 180 / 3.14159265359)
                       

                #assert that the number of rows in the two dataframes are equal
                assert len(traditional_pf_results) == len(generalised_pf_results)

                #find the biggest differences in first two columns between the two dataframes in percentage, using traditional power flow as the base
                max_diff_volt = 0
                max_diff_ang = 0

                for i in range(len(traditional_pf_results)):
                    #use the column names to access the values
                    #find the percentage difference
                    #update the max_diff_volt and max_diff_ang if the current difference is greater
                    diff_volt = abs((generalised_pf_results.iloc[i]['Voltage Magnitude'] - traditional_pf_results.iloc[i]['Vm']))
                    diff_ang = abs((generalised_pf_results.iloc[i]['Voltage Angle'] - traditional_pf_results.iloc[i]['Va']) )
                    if diff_volt > max_diff_volt:
                        max_diff_volt = diff_volt
                    if diff_ang > max_diff_ang:
                        max_diff_ang = diff_ang

                
                log_file.write(f"{file_name}, {max_diff_volt}, {max_diff_ang}\n")

def compare_results():
    import time
    import pandas as pd
    start = time.time()
    file_names = [
        "10_bus_hvdc.gridcal",
        "10_bus_hvdc_no_oscillations.gridcal",
        "2bus_HVDC.gridcal",
        "3Bus_controlled_transformer.gridcal",
        "4Bus_SalvadorAchaDaza.gridcal",
        "5bus_HVDC.gridcal",
        "8_nodes_2_islands.gridcal",
        "8_nodes_2_islands_hvdc.gridcal",
        "ACTIVSg 500 - South Carolina 500 Bus System.gridcal",
        "Australia.xlsx",
        "Brazil11_loading05.gridcal",
        "case_ACTIVSg500.m",
        "case14.m",
        "case300.m",
        "case6ww.m",
        "case89pegase.m",
        "case9.m",
        "ding0_test_network_2_mvlv.gridcal",
        "example_transformer_tpe.xlsx",
        "GB reduced network.gridcal",
        "grid.raw",
        "Grid4Bus-OPF.gridcal",
        "hydro_grid2.gridcal",
        "hydro_grid3.gridcal",
        "hydro_IEEE39.gridcal",
        "hydro_simple.gridcal",
        "IEEE 118 Bus - ntc_areas.gridcal",
        "IEEE 118 Bus - ntc_areas.raw",
        "IEEE 118 Bus - ntc_areas_two.gridcal",
        "IEEE 118 Bus v2.raw",
        "IEEE 118.xlsx",
        "IEEE 14 bus.raw",
        "IEEE 14 zip.gridcal",
        "IEEE 14.xlsx",
        "IEEE 145 Bus.xlsx",
        "IEEE 30 Bus with storage.xlsx",
        "IEEE 30 Bus.gridcal",
        "IEEE 30 bus.raw",
        "IEEE 39 dynamic bus types.gridcal",
        "IEEE 39+HVDC line.gridcal",
        "IEEE 5 Bus.xlsx",
        "IEEE 57.xlsx",
        "IEEE 9 Bus.gridcal",
        "IEEE14 - ntc areas.gridcal",
        "IEEE14 - ntc areas_voltages.gridcal",
        "IEEE14 - ntc areas_voltages_hvdc.gridcal",
        "IEEE14 - ntc areas_voltages_hvdc_shifter.gridcal",
        "IEEE14 - ntc areas_voltages_hvdc_shifter_l10free.gridcal",
        "IEEE14_from_raw.gridcal",
        "IEEE25.gridcal",
        "IEEE39.gridcal",
        "IEEE39.xlsx",
        "IEEE39_1W.gridcal",
        "Illinois 200 Bus.gridcal",
        "Illinois200Bus.xlsx",
        "KULeuven_5node.gridcal",
        "Lynn 5 Bus (pq).gridcal",
        "Lynn 5 bus (SVC).gridcal",
        "Lynn 5 Bus pv (opf).gridcal",
        "Lynn 5 Bus pv.gridcal",
        "lynn5buspq.xlsx",
        "lynn5buspv.xlsx",
        "NETS-NYPS 68 Bus System.raw",
        "New England 68 Bus.xlsx",
        "Nord pool model.xlsx",
        "Pegasus 89 Bus.xlsx",
        "PGOC_6bus(from .raw).gridcal",
        "PGOC_6bus.gridcal",
        "PGOC_6bus_modNTC.gridcal",
        "Random grid 1000 buses.gridcal",
        "sc_test.xlsx",
        "Simple_NTC_test_grid.gridcal",
        "test_temp_correction.xlsx"
    ]

    directory_path = 'Grids_and_profiles/grids/'

    #make a dictionary that prepares to be turned into a df in the end, with the following columns: file_name, max_diff_volt, max_diff_ang, converged
    comparison_dict = {
        "file_name": [],
        "max_diff_volt": [],
        "max_diff_ang": [],
        "converged": []
    }

    for file in file_names:
        print(file)
        full_path = os.path.join(directory_path, file)
        grid = gce.FileOpen(full_path).open()
        assert grid is not None
        pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1, generalised_pf=True, tolerance=1e-10)
        try:
            results_generalised = gce.power_flow(grid, options=pf_options)
        except Exception as e:
                continue
        if results_generalised.converged:
            #run normal powerflow
            pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1)
            results_normal = gce.power_flow(grid, options=pf_options)            

            #compare the Vm and Va values of the two results
            #convert the generalised results to a df
            generalised_pf_results = results_generalised.get_bus_df()
            #convert the normal results to a df
            normal_pf_results = results_normal.get_bus_df()

            #find the biggest differences in first two columns between the two dataframes in percentage, using normal power flow as the base
            max_diff_volt = 0
            max_diff_ang = 0

            for i in range(len(normal_pf_results)):
                #use the column names to access the values
                #find the percentage difference
                #update the max_diff_volt and max_diff_ang if the current difference is greater
                diff_volt = abs((generalised_pf_results.iloc[i]['Vm'] - normal_pf_results.iloc[i]['Vm']) / normal_pf_results.iloc[i]['Vm'])
                diff_ang = abs((generalised_pf_results.iloc[i]['Va'] - normal_pf_results.iloc[i]['Va']) / normal_pf_results.iloc[i]['Va'])
                if diff_volt > max_diff_volt:
                    max_diff_volt = diff_volt
                if diff_ang > max_diff_ang:
                    max_diff_ang = diff_ang

            #append the max_diff_volt and max_diff_ang to the dictionary
            comparison_dict["max_diff_volt"].append(max_diff_volt)
            comparison_dict["max_diff_ang"].append(max_diff_ang)
            #append filename to the dictionary
            comparison_dict["file_name"].append(file)
            #append converged to the dictionary
            comparison_dict["converged"].append(results_generalised.converged)
        
        else:
            comparison_dict["max_diff_volt"].append(None)
            comparison_dict["max_diff_ang"].append(None)
            comparison_dict["file_name"].append(file)
            comparison_dict["converged"].append(results_generalised.converged)



    #return the df
    df = pd.DataFrame(comparison_dict)
    print(df)
    #end timer
    end = time.time()
    print(f"Time taken: {end - start}")
    #find how many grids converged
    print("Converged:")
    print(df['converged'].value_counts())
    #find the average max_diff_volt and max_diff_ang
    print("Average max_diff_volt:")
    print(df['max_diff_volt'].mean())
    print("Average max_diff_ang:")
    print(df['max_diff_ang'].mean())
    #median max_diff_volt and max_diff_ang
    print("Median max_diff_volt:")
    print(df['max_diff_volt'].median())
    print("Median max_diff_ang:")
    print(df['max_diff_ang'].median())
    #find the number where max_diff_volt and max_diff_ang are greater than 0.01
    print("Greater than 0.01:")
    print(df[(df['max_diff_volt'] > 0.01) | (df['max_diff_ang'] > 0.01)])



if __name__ == '__main__':
    # ieee5_w_ourControls()
    # simple2bus_wOurControls() #converges true
    # threebusacdc()  # does not converge
    # simple3busacdc() #converges true DO NOT TOUCH
    # simple3busacdc_controllingPower() #converges true, but only if you do Power to and not power from
    # simple3busacdc_controllingPower_notrafo() #converges true only with tolerance 1e-5 and higher
    # simple3busacdc_controllingPower_wtrafo() #does not converge, but this always does not converge for some reason, must be a tolerance issue
    # simple3busac_pure() #converges true
    # simple4busacdc_pure() #converges true
    # simple4busacdc_wTrafo() #converged true because it is seen as an inactive device
    # simple4busacdc_wControllableTrafo() #converges true when controlling the powers across the transformer, lessons learnt, when you are controlling a branch power, if you try a setpont that goes agaisnt the natural flow of power ie from slack to load, youll have a hard time converging
                                        # nodal power balances derivatives look good tho
    # simple4busacdc_wControllableTrafo_remoteControl() #converges true, nodal power balances derivatives look good too
    complex6bus() #converges true, derivatives at least the nodal power balances look good


    # doubleVSCsystem()

    
    # compare_results()
    
    # acdc10_example() #converges true but there is a HVDC Link so it doesnt make sense to converge
    # fubm_caseHVDC_vt()
    # fubm_caseHVDC_vt_normalNR()clear

    # acdc3bus_example() #problem with the control
    # pegase2k_example() #runs super slow and does not converge


    # whatever_func()
    
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
