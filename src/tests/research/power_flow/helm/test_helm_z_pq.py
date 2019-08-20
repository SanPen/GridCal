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


def test_helm_z_pq():
    grid = get_grid_lynn_5_bus_wiki()

    power_flow_options = PowerFlowOptions(
        solver_type=SolverType.HELM_Z_PQ,
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
    headers = ['Vm (p.u.)', 'Va (Deg)', 'Vre', 'Vim']
    Vm = np.abs(power_flow.results.voltage)
    Va = np.angle(power_flow.results.voltage, deg=True)
    Vre = power_flow.results.voltage.real
    Vim = power_flow.results.voltage.imag
    data = np.c_[Vm, Va, Vre, Vim]
    v_df = pd.DataFrame(data=data, columns=headers, index=grid.bus_names)
    print('\n', v_df)
    headers = ['Loading (%)', 'Current(p.u.)', 'Power (MVA)']
    loading = np.abs(power_flow.results.loading) * 100
    current = np.abs(power_flow.results.Ibranch)
    power = np.abs(power_flow.results.Sbranch)
    data = np.c_[loading, current, power]
    br_df = pd.DataFrame(data=data, columns=headers, index=grid.branch_names)
    print('\n', br_df)
    print('\nError:', power_flow.results.error)
    print('Elapsed time (s):', power_flow.results.elapsed)
