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


def test_helm():
    grid = get_grid_lynn_5_bus_wiki()

    power_flow_options = PowerFlowOptions(
        solver_type=SolverType.HELM_VECT_ASU,
        # Base method to use
        verbose=False,
        # Verbose option where available
        tolerance=1e-6,  # power error in p.u.
        max_iter=25,  # maximum iteration number
        control_q=True
        # if to control the reactive power
    )
    pf = PowerFlow(grid, power_flow_options)
    pf.run()
    headers = ['Vm (p.u.)', 'Va (Deg)', 'Vre', 'Vim']
    Vm = np.abs(pf.results.voltage)
    Va = np.angle(pf.results.voltage, deg=True)
    Vre = pf.results.voltage.real
    Vim = pf.results.voltage.imag
    data = np.c_[Vm, Va, Vre, Vim]
    v_df = pd.DataFrame(data=data, columns=headers, index=grid.bus_names)
    print('\n', v_df)
    headers = ['Loading (%)', 'Current(p.u.)', 'Power (MVA)']
    loading = np.abs(pf.results.loading) * 100
    current = np.abs(pf.results.Ibranch)
    power = np.abs(pf.results.Sbranch)
    data = np.c_[loading, current, power]
    br_df = pd.DataFrame(data=data, columns=headers, index=grid.branch_names)
    print('\n', br_df)
    print('\nError:', pf.results.error)
    print('Elapsed time (s):', pf.results.elapsed)
