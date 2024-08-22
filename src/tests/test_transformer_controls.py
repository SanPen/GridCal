import os
from GridCalEngine.api import *


def test_v_control_true():
    """
    Test that when the V control is enabled the voltage at the bus is the set point
    """
    options = PowerFlowOptions(SolverType.NR, control_q=True, retry_with_other_methods=False)

    fname = os.path.join('data', 'grids', 'IEEE57.gridcal')
    main_circuit = FileOpen(fname).open()

    tr = main_circuit.transformers2w[5]

    tr.tap_module_control_mode = TapModuleControl.Vm
    tr.regulation_bus = tr.bus_to
    tr.vset = 1.0

    power_flow = PowerFlowDriver(main_circuit, options)
    power_flow.run()

    v_control = np.abs(power_flow.results.voltage[42])

    assert np.allclose(tr.vset, v_control)


def test_v_control_false():
    """
    Test that when the V control is disabled the voltage at the bus is not the set point
    """
    options = PowerFlowOptions(SolverType.NR,
                               control_q=True,
                               retry_with_other_methods=False)

    fname = os.path.join('data', 'grids', 'IEEE57.gridcal')
    main_circuit = FileOpen(fname).open()

    tr = main_circuit.transformers2w[5]

    tr.tap_phase_control_mode = TapPhaseControl.fixed
    tr.vset = 1.0

    power_flow = PowerFlowDriver(main_circuit, options)
    power_flow.run()

    v_control = np.abs(power_flow.results.voltage[42])

    assert not np.allclose(tr.vset, v_control)
