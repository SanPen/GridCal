import numpy as np
import pandas as pd

from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_options \
    import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_runnable \
    import PowerFlow
from GridCal.Engine.Simulations.PowerFlow.steady_state.solver_type import \
    SolverType
from tests.research.power_flow.helm.get_grid_lynn_5_bus_wiki import \
    get_grid_lynn_5_bus_wiki


def test_helm_stable():
    grid = get_grid_lynn_5_bus_wiki()

    power_flow_options = PowerFlowOptions(
        solver_type=SolverType.HELM_STABLE,
        # Base method to use
        verbose=False,
        # Verbose option where available
        tolerance=1e-6,  # power error in p.u.
        max_iter=25,  # maximum iteration number
        control_q=True
        # if to control the reactive power
    )
    power_flow = PowerFlow(grid, power_flow_options)
    power_flow.run()

    headers = ['voltage_per_unit (p.u.)', 'voltage_angle (Deg)', 'voltage_real', 'voltage_imaginary']
    voltage_per_unit = np.abs(power_flow.results.voltage)
    voltage_angle = np.angle(power_flow.results.voltage, deg=True)
    voltage_real = power_flow.results.voltage.real
    voltage_imaginary = power_flow.results.voltage.imag
    voltage_data = np.c_[voltage_per_unit, voltage_angle, voltage_real, voltage_imaginary]
    v_data_frame = pd.DataFrame(data=voltage_data, columns=headers, index=grid.bus_names)
    print('\n', v_data_frame)

    headers = ['Loading (%)', 'Current(p.u.)', 'Power (MVA)']
    branch_loading_per_cent = np.abs(power_flow.results.loading) * 100
    branch_current = np.abs(power_flow.results.Ibranch)
    branch_power_complex = np.abs(power_flow.results.Sbranch)
    branch_data = np.c_[branch_loading_per_cent, branch_current, branch_power_complex]
    branch_data_frame = pd.DataFrame(data=branch_data, columns=headers, index=grid.branch_names)
    print('\n', branch_data_frame)

    print('\nError:', power_flow.results.error)
    print('Elapsed time (s):', power_flow.results.elapsed)
