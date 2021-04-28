"""
Compute the available transfer capacity
"""
from GridCal.Engine import *

if __name__ == '__main__':

    fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

    main_circuit = FileOpen(fname).open()

    simulation = LinearAnalysis(grid=main_circuit)
    simulation.run()

    options = PowerFlowOptions(solver_type=SolverType.NR,
                               control_q=ReactivePowerControlMode.NoControl,
                               retry_with_other_methods=True)
    power_flow = PowerFlowDriver(main_circuit, options)
    power_flow.run()

    ptdf = simulation.results.PTDF
    lodf = simulation.results.LODF
    otdf_max = simulation.get_otdf_max()
    tm = simulation.get_transfer_limits(flows=power_flow.results.Sf.real)
    tmc = simulation.get_contingency_transfer_limits(flows=power_flow.results.Sf.real)
    print()
