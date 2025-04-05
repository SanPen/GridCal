import os
import GridCalEngine.api as gce
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import ac_optimal_power_flow


def case_v0() -> None:
    """
    Test case14 from matpower. Tests multiple situations
    :return:
    """
    # Load basic grid
    file_path = os.path.join('src', 'trunk', 'scopf', 'bus4_v0.gridcal')
    grid = gce.FileOpen(file_path).open()

    # Set options
    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(control_q=False)
    opf_base_options = gce.OptimalPowerFlowOptions(ips_method=gce.SolverType.NR, 
                                                   ips_tolerance=1e-8,
                                                   ips_iterations=50,
                                                   acopf_mode=gce.AcOpfMode.ACOPFstd)
    opf_slack_options = gce.OptimalPowerFlowOptions(ips_method=gce.SolverType.NR, 
                                                    ips_tolerance=1e-8,
                                                    ips_iterations=50,
                                                    acopf_mode=gce.AcOpfMode.ACOPFslacks)

    # Run cases without and with slacks
    base_sol = ac_optimal_power_flow(nc=nc, pf_options=pf_options, opf_options=opf_base_options)
    slack_sol = ac_optimal_power_flow(nc=nc, pf_options=pf_options, opf_options=opf_slack_options)

    return None


if __name__ == '__main__':
    case_v0()
