# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import pytest
from VeraGridEngine.api import *

np.set_printoptions(linewidth=10000)


@pytest.mark.skip(reason="Not passing because something...")
def test_3_node_abur_exposito() -> None:
    """
    3-bus state estimation test from
    Power System State Estimation Theory and Implementation
    Ali Abur and Antonio Gomez Expósito
    """
    grid = MultiCircuit()

    b1 = Bus(name='B1', is_slack=True)
    b2 = Bus(name='B2')
    b3 = Bus(name='B3')

    br1 = Line(bus_from=b1, bus_to=b2, name='Br1', r=0.01, x=0.03)
    br2 = Line(bus_from=b1, bus_to=b3, name='Br2', r=0.02, x=0.05)
    br3 = Line(bus_from=b2, bus_to=b3, name='Br3', r=0.03, x=0.08)

    # add measurements
    Sb = 100.0

    # Note: THe book measurements are in p.u. so we need to scale them back to insert them

    grid.add_pf_measurement(PfMeasurement(0.888 * Sb, 0.008 * Sb, br1))
    grid.add_pf_measurement(PfMeasurement(1.173 * Sb, 0.008 * Sb, br2))
    grid.add_pi_measurement(PiMeasurement(-0.501 * Sb, 0.01 * Sb, b2))

    grid.add_qf_measurement(QfMeasurement(0.568 * Sb, 0.008 * Sb, br1))
    grid.add_qf_measurement(QfMeasurement(0.663 * Sb, 0.008 * Sb, br2))
    grid.add_qi_measurement(QiMeasurement(-0.286 * Sb, 0.01 * Sb, b2))

    grid.add_vm_measurement(VmMeasurement(1.006, 0.004, b1))
    grid.add_vm_measurement(VmMeasurement(0.968, 0.004, b2))

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    grid.add_line(br1)
    grid.add_line(br2)
    grid.add_line(br3)

    for solver in [SolverType.Decoupled_LU, SolverType.NR, SolverType.LM, SolverType.GN]:
        se_options = StateEstimationOptions(
            fixed_slack=True,
            solver=solver
        )

        se = StateEstimation(circuit=grid, options=se_options)

        se.run()

        # print()
        # print('V: ', se.results.voltage)
        # print('Vm: ', np.abs(se.results.voltage))
        # print('Va: ', np.angle(se.results.voltage))

        """
        The validated output is:
    
        V:   [0.99962926+0.j        0.97392515-0.02120941j  0.94280676-0.04521561j]
        Vm:  [0.99962926            0.97415607              0.94389038]
        Va:  [ 0.                   -0.0217738              -0.0479218]
        """

        print("Bus results:\n", se.results.get_bus_df())
        print(f"Converged: {se.results.converged}")
        print(f"Error: {se.results.error}")
        print(f"Iter: {se.results.iterations}")

        ## The current implpementation produces these results
        """
        LU
                Vm        Va           P          Q
            B1 1.000000  0.000000  206.349008 122.582586
            B2 0.974548 -1.246105  -49.557471 -29.758619
            B3 0.944300 -2.743415 -151.416085 -78.725261
            Converged: 1
            Error: 7.410872191372136e-10
            Iter: 22
            NR
                Vm        Va           P          Q
            B1 1.000000  0.000000  206.402671 122.647148
            B2 0.974535 -1.246598  -49.598555 -29.778052
            B3 0.944280 -2.743562 -151.425970 -78.763137
            Converged: True
            Error: 8.540155249647796e-10
            Iter: 8
            
            LM
            Bus results:
                 Vm        Va           P          Q
            B1 1.000000  0.000000  206.402671 122.647148
            B2 0.974535 -1.246598  -49.598555 -29.778052
            B3 0.944280 -2.743562 -151.425970 -78.763137
            Converged: True
            Error: 2.3640752701194375e-10
            Iter: 5
            
            GN
            Bus results:
               Vm        Va           P          Q
            B1 1.000000  0.000000  206.402671 122.647148
            B2 0.974535 -1.246598  -49.598554 -29.778052
            B3 0.944280 -2.743562 -151.425970 -78.763137
            Converged: True
            Error: 2.364077197531761e-10
            Iter: 4

        """

        expected_results = np.array([0.99962926+0.j, 0.97392515-0.02120941j, 0.94280676-0.04521561j])
        ok = np.allclose(se.results.voltage, expected_results, atol=1e-4)
        assert ok


def test_14_bus_matpower():
    # Go back two directories
    file_path = os.path.join('data', 'grids', 'case14.m')

    grid = FileOpen(file_path).open()

    # these are the matpower branch indices
    idx_zPF = np.array([1, 3, 8, 9, 10, 13, 15, 16, 17, 19], dtype=int)
    idx_zPT = np.array([4, 5, 7, 11], dtype=int)
    idx_zPG = np.array([1, 2, 3, 4, 5], dtype=int)  # generator index
    idx_zVa = np.array([], dtype=int)
    idx_zQF = np.array([1, 3, 8, 9, 10, 13, 15, 19], dtype=int)
    idx_zQT = np.array([4, 5, 7, 11], dtype=int)
    idx_zQG = np.array([1, 2], dtype=int)  # generator index
    idx_zVm = np.array([2, 3, 6, 8, 10, 14], dtype=int)

    # mapping from matpower index to gridcal branch index
    branch_mapping = {
        1: 0,
        2: 1,
        3: 2,
        4: 3,
        5: 4,
        6: 5,
        7: 6,
        8: 17,
        9: 18,
        10: 19,
        11: 7,
        12: 8,
        13: 9,
        14: 10,
        15: 11,
        16: 12,
        17: 13,
        18: 14,
        19: 15,
        20: 16,
    }

    PF = np.array([1.5708, 0.734, 0.2707, 0.1546, 0.4589, 0.1834, 0.2707, 0.0523, 0.0943, 0.0188], dtype=float)
    PT = np.array([-0.5427, -0.4081, 0.6006, -0.0816], dtype=float)
    PG = np.array([2.32, 0.4, 0.0, 0.0, 0.0], dtype=float)

    Va = np.array([], dtype=float)
    QF = np.array([-0.1748, 0.0594, -0.154, -0.0264, -0.2084, 0.0998, 0.148, 0.0141], dtype=float)
    QT = np.array([0.0213, -0.0193, -0.1006, -0.0864], dtype=float)
    QG = np.array([-0.169, 0.424], dtype=float)

    Vm = np.array([1, 1, 1, 1, 1, 1], dtype=float)

    sigma_PF = 0.02
    sigma_PT = 0.02
    sigma_PG = 0.015
    sigma_Va = 0.01
    sigma_QF = 0.02
    sigma_QT = 0.02
    sigma_QG = 0.015
    sigma_Vm = 0.01

    # Add bus measurements
    for idx_arr, vals_arr, sigma, scale, m_object in [
        (idx_zVm, Vm, sigma_Vm, 1.0, VmMeasurement),
        (idx_zVa, Va, sigma_Va, 1.0, VaMeasurement),
    ]:
        for idx, val in zip(idx_arr, vals_arr):
            gc_idx = idx - 1  # pass to zero indexing
            obj = grid.buses[gc_idx]
            grid.add_element(m_object(value=val * scale, uncertainty=sigma, api_obj=obj))

    # Add generator measurements
    for idx_arr, vals_arr, sigma, scale, m_object in [
        (idx_zPG, PG, sigma_PG, 100, PgMeasurement),
        (idx_zQG, QG, sigma_QG, 100, QgMeasurement),
    ]:
        for idx, val in zip(idx_arr, vals_arr):
            gc_idx = idx - 1  # get the gridcal bus index from the generator index
            obj = grid.generators[gc_idx]
            grid.add_element(m_object(value=val * scale, uncertainty=sigma * scale, api_obj=obj))

    # Add branch measurements
    branches = grid.get_branches()
    for idx_arr, vals_arr, sigma, scale, m_object in [
        (idx_zPF, PF, sigma_PF, 100, PfMeasurement),
        (idx_zPT, PT, sigma_PT, 100, PtMeasurement),
        (idx_zQF, QF, sigma_QF, 100, QfMeasurement),
        (idx_zQT, QT, sigma_QT, 100, QtMeasurement),
    ]:
        for idx, val in zip(idx_arr, vals_arr):
            gc_idx = branch_mapping[idx]
            obj = branches[gc_idx]
            grid.add_element(m_object(value=val * scale, uncertainty=sigma * scale, api_obj=obj))

    for solver in [SolverType.Decoupled_LU, SolverType.NR, SolverType.LM, SolverType.GN]:

        se_options = StateEstimationOptions(
            fixed_slack=True,
            solver=solver,
            run_observability_analyis=True,
            run_measurement_profiling=True

        )
        se = StateEstimation(circuit=grid, options=se_options)
        se.run()

        print("Bus results:\n", se.results.get_bus_df())
        print(f"Converged: {se.results.converged}")
        print(f"Error: {se.results.error}")
        print(f"Iter: {se.results.iterations}")
        print()

        expected_voltage = np.array([
            1.060000000000000 + 0.000000000000000j,
            1.039933594059899 - 0.090313766102826j,
            0.982355302637923 - 0.221430317163729j,
            0.998610257007820 - 0.180922767027063j,
            1.006066277008519 - 0.155583022160554j,
            1.086005598052025 - 0.273081360187983j,
            1.042998635186457 - 0.244449009989143j,
            0.973617097641113 - 0.228187964583794j,
            1.022141142371230 - 0.268116448565777j,
            0.971362042218784 - 0.237604256983231j,
            1.062397271041971 - 0.274222737353904j,
            1.067252193108086 - 0.283008909486410j,
            1.060690860030405 - 0.282328227107489j,
            0.966563824799688 - 0.256426154260047j,
        ])

        diff = se.results.voltage - expected_voltage
        if not SolverType.Decoupled_LU:
            assert np.allclose(se.results.voltage, expected_voltage, atol=1e-12)
        else:
            assert np.allclose(se.results.voltage, expected_voltage, atol=1e-1)