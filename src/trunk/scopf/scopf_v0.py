import os
import GridCalEngine.api as gce
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import ac_optimal_power_flow, run_nonlinear_opf


def case_v0() -> None:
    """
    Simple 4 bus system from where to build the SCOPF
    :return:
    """
    # Load basic grid
    file_path = os.path.join('src', 'trunk', 'scopf', 'bus4_v2.gridcal')
    grid = gce.FileOpen(file_path).open()

    # Set options
    pf_options = gce.PowerFlowOptions(control_q=False)
    opf_base_options = gce.OptimalPowerFlowOptions(ips_method=gce.SolverType.NR,
                                                   ips_tolerance=1e-8,
                                                   ips_iterations=50,
                                                   acopf_mode=gce.AcOpfMode.ACOPFstd)
    opf_slack_options = gce.OptimalPowerFlowOptions(ips_method=gce.SolverType.NR,
                                                    ips_tolerance=1e-8,
                                                    ips_iterations=50,
                                                    acopf_mode=gce.AcOpfMode.ACOPFslacks)

    # Run base case first
    base_sol_base = run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_base_options)
    # slack_sol_base = run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_slack_options)

    print()
    print(f"--- Base case ---")
    print(f"Base OPF loading {base_sol_base.loading} .")
    # print(f"Slacks OPF loading {slack_sol_base.loading} .")
    print(f"Generators production: {base_sol_base.Pg}")

    # Loop through N lines by recompiling the nc (faster way if using cont.?) 
    for i, line_to_disable in enumerate(grid.lines):
        print()
        print(f"--- N-1 Line Contingency {i+1}: Deactivating '{line_to_disable.name}' ---")

        # Deactivate the line in the main grid object
        grid.lines[i].active = False
       
        # Run cases without and with slacks for the contingency
        base_sol_cont = run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_base_options)
        slack_sol_cont = run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_slack_options)
        print(f"Base OPF loading: {base_sol_cont.loading}")
        print(f"Slacks OPF loading: {slack_sol_cont.loading}")
        print(f"Generators production: {base_sol_cont.Pg}")
        print(f"Line slacks F: {slack_sol_cont.sl_sf}")
        print(f"Line slacks T: {slack_sol_cont.sl_st}")

        # Reactivate the line in the main grid object for the next iteration
        grid.lines[i].active = True

    print()
    print("--- All contingencies processed ---")
    return None


if __name__ == '__main__':
    case_v0()
