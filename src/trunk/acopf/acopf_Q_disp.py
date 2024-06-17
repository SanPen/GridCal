# Constrain the P of gens in areas 11 and 15 to solve for Q
import numpy as np
import GridCalEngine.api as gce
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import ac_optimal_power_flow
from GridCalEngine.Simulations.OPF import opf_driver


def modify_grid(grid):
    disp_areas = ['A11', 'A15']
    dict_bus_lims = {'21215': [230, 225],
                     '11055': [410, 405],
                     '21075': [230, 225],
                     '25130': [230, 225],
                     '15005': [410, 405],
                     '15015': [410, 405]}
    tol = 1e-4
    vm_cost = 1e4

    for gen in grid.generators:
        if gen.bus.area.name in disp_areas:
            # P limits -> restrict them very close to P
            gen.Pmax = gen.P + tol
            gen.Pmin = gen.P - tol
            # Tanmax -> set pf close to 0 to get large tanmax
            gen.Pf = tol

    for bus in grid.buses:
        if bus.code in dict_bus_lims.keys():
            # Increase Vm slack cost to enforce limits
            bus.Vm_cost = vm_cost
            # Redo Vm limits from the inputs
            vm_lims = dict_bus_lims[bus.code]
            bus.Vmax = vm_lims[0] / bus.Vnom
            bus.Vmin = vm_lims[1] / bus.Vnom

    return grid


def run_acopf(grid):
    pf_options = gce.PowerFlowOptions(control_q=gce.ReactivePowerControlMode.NoControl,
                                      ignore_single_node_islands=True,
                                      max_iter=50,
                                      max_outer_loop_iter=1000,
                                      q_steepness_factor=1.0,
                                      tolerance=1e-05)
    opf_options = gce.OptimalPowerFlowOptions(ips_method=gce.SolverType.NR, ips_tolerance=1e-4,
                                              acopf_mode=gce.AcOpfMode.ACOPFslacks,
                                              lodf_tolerance=0.05,
                                              power_flow_options=pf_options,
                                              solver=gce.SolverType.NONLINEAR_OPF,
                                              verbose=1)

    acopf = opf_driver.OptimalPowerFlowDriver(grid, opf_options)
    acopf.run()
    return acopf.results


if __name__ == "__main__":
    file_path = 'C:/Users/J/Downloads/opf_ree/entrada_a_aopf.raw'
    syst = gce.FileOpen(file_path).open()

    # 1. Modify grid once to set P limits
    grid_cons = modify_grid(syst)

    # 2. Run ACOPF
    acopf_res = run_acopf(grid_cons)

    print('Finished!')
    # df_bus.to_excel('C:/Users/J/Downloads/opf_ree/bus_df.xlsx')