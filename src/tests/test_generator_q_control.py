import os
from GridCal.Engine import *


def test_q_control_true():
    """
    Test that when the Q control is enabled the Q limits are respected
    """
    options = PowerFlowOptions(SolverType.NR,
                               control_q=ReactivePowerControlMode.Direct,
                               retry_with_other_methods=False)

    fname = os.path.join('data', 'grids', 'IEEE57.gridcal')
    main_circuit = FileOpen(fname).open()
    power_flow = PowerFlowDriver(main_circuit, options)
    power_flow.run()

    nc = compile_snapshot_circuit(main_circuit)

    assert(power_flow.results.converged)

    Q = power_flow.results.Sbus.imag[nc.pv]
    Qmin = nc.Qmin_bus[nc.pv, 0] * nc.Sbase
    Qmax = nc.Qmax_bus[nc.pv, 0] * nc.Sbase
    l1 = Q <= Qmax
    l2 = Qmin <= Q
    ok = l1 * l2

    assert ok.all()


def test_q_control_false():
    """
    Test that when the Q control is disabled the Q limits are not respected
    """
    options = PowerFlowOptions(SolverType.NR,
                               control_q=ReactivePowerControlMode.NoControl,
                               retry_with_other_methods=False)

    fname = os.path.join('data', 'grids', 'IEEE57.gridcal')
    main_circuit = FileOpen(fname).open()
    power_flow = PowerFlowDriver(main_circuit, options)
    power_flow.run()

    nc = compile_snapshot_circuit(main_circuit)

    Q = power_flow.results.Sbus.imag
    Qmin = nc.Qmin_bus[:, 0] * nc.Sbase
    Qmax = nc.Qmax_bus[:, 0] * nc.Sbase
    l1 = Q <= Qmax
    l2 = Qmin <= Q
    ok = l1 * l2

    assert not ok.all()
