# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
from VeraGridEngine.api import *


def test_q_control_true() -> None:
    """
    Test that when the Q control is enabled the Q limits are respected
    """
    fname = os.path.join('data', 'grids', 'IEEE57.gridcal')
    main_circuit = FileOpen(fname).open()

    for solver_type in [SolverType.NR, SolverType.IWAMOTO, SolverType.LM, SolverType.FASTDECOUPLED]:

        options = PowerFlowOptions(solver_type,
                                   control_q=True,
                                   retry_with_other_methods=False)

        power_flow = PowerFlowDriver(main_circuit, options)
        power_flow.run()

        nc = compile_numerical_circuit_at(main_circuit)
        indices = nc.get_simulation_indices()
        Qmax_bus, Qmin_bus = nc.get_reactive_power_limits()
        assert power_flow.results.converged

        for i in indices.pv:
            tol = 1e-4  # tolerance of the comparison
            Q = power_flow.results.Sbus.imag[i]
            Qmin = Qmin_bus[i] * nc.Sbase - tol
            Qmax = Qmax_bus[i] * nc.Sbase + tol
            ok = Qmin <= Q <= Qmax

            assert ok


def test_q_control_false():
    """
    Test that when the Q control is disabled the Q limits are not respected
    """
    fname = os.path.join('data', 'grids', 'IEEE57.gridcal')
    main_circuit = FileOpen(fname).open()

    for solver_type in [SolverType.NR, SolverType.IWAMOTO, SolverType.LM, SolverType.FASTDECOUPLED]:
        options = PowerFlowOptions(solver_type,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False)

        power_flow = PowerFlowDriver(main_circuit, options)
        power_flow.run()

        nc = compile_numerical_circuit_at(main_circuit)

        Q = power_flow.results.Sbus.imag
        Qmax_bus, Qmin_bus = nc.get_reactive_power_limits()
        Qmin = Qmin_bus * nc.Sbase
        Qmax = Qmax_bus * nc.Sbase
        l_ok = Qmin <= Q
        r_ok = Q <= Qmax
        ok = l_ok.all() and r_ok.all()

        assert not ok


if __name__ == '__main__':
    test_q_control_true()
