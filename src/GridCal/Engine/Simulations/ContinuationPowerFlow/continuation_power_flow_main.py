import os

import numpy as np
import matplotlib as mpl

from GridCal.Engine.IO import FileOpen
from GridCal.Engine.Simulations.ContinuationPowerFlow.continuation_power_flow import \
    VCParametrization, VCStopAt
from GridCal.Engine.Simulations.ContinuationPowerFlow.voltage_collapse_driver import \
    VoltageCollapseOptions, VoltageCollapseInput, VoltageCollapse
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_options import \
    PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_runnable import \
    PowerFlow
from GridCal.Engine.Simulations.PowerFlow.steady_state.reactive_control_mode import \
    ReactivePowerControlMode
from GridCal.Engine.Simulations.PowerFlow.steady_state.solver_type import \
    SolverType

if __name__ == '__main__':

    # fname = os.path.join('..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    fname = os.path.join('..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'lynn5buspv.xlsx')

    print('Reading...')
    main_circuit = FileOpen(fname).open()
    options = PowerFlowOptions(SolverType.NR, verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True)

    ####################################################################################################################
    # PowerFlow
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlow(main_circuit, options)
    power_flow.run()

    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sbranch|:', abs(power_flow.results.Sbranch))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())

    ####################################################################################################################
    # Voltage collapse
    ####################################################################################################################
    vc_options = VoltageCollapseOptions(step=0.001,
                                        approximation_order=VCParametrization.ArcLength,
                                        adapt_step=True,
                                        step_min=0.00001,
                                        step_max=0.2,
                                        error_tol=1e-3,
                                        tol=1e-6,
                                        max_it=20,
                                        stop_at=VCStopAt.Full,
                                        verbose=False)

    # just for this test
    numeric_circuit = main_circuit.compile()
    numeric_inputs = numeric_circuit.compute()
    Sbase = np.ma.zeros(len(main_circuit.buses), dtype=complex)
    Vbase = np.ma.zeros(len(main_circuit.buses), dtype=complex)
    for c in numeric_inputs:
        Sbase[c.original_bus_idx] = c.Sbus
        Vbase[c.original_bus_idx] = c.Vbus

    unitary_vector = -1 + 2 * np.random.random(len(main_circuit.buses))

    # unitary_vector = random.random(len(grid.buses))
    vc_inputs = VoltageCollapseInput(Sbase=Sbase,
                                     Vbase=Vbase,
                                     Starget=Sbase * (1 + unitary_vector))
    vc = VoltageCollapse(circuit=main_circuit, options=vc_options, inputs=vc_inputs)
    vc.run()
    df = vc.results.plot()

    print(df)

    mpl.pyplot.show()
