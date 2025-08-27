import numpy as np

import VeraGridEngine as gce
from VeraGridEngine import MultiCircuit, Bus, Line, PiMeasurement, QiMeasurement, VmMeasurement, StateEstimationOptions, \
    StateEstimation, QfMeasurement, PfMeasurement


def test_se_with_and_without_pseudo_measurements():
    grid = MultiCircuit()

    # --- Buses ---
    b1 = Bus(name='B1', is_slack=True)
    b2 = Bus(name='B2')
    b3 = Bus(name='B3')
    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    # --- Lines ---
    br1 = Line(bus_from=b1, bus_to=b2, r=0.01, x=0.03)
    br2 = Line(bus_from=b1, bus_to=b3, r=0.02, x=0.05)
    br3 = Line(bus_from=b2, bus_to=b3, r=0.03, x=0.08)
    grid.add_line(br1)
    grid.add_line(br2)
    grid.add_line(br3)

    Sb = 100.0

    # --- Sparse measurements (insufficient) ---
    grid.add_pf_measurement(PfMeasurement(0.888 * Sb, 0.008 * Sb, br1))
   # grid.add_pf_measurement(PfMeasurement(1.173 * Sb, 0.008 * Sb, br2))
    #grid.add_pi_measurement(PiMeasurement(-0.501 * Sb, 0.01 * Sb, b2))

    grid.add_qf_measurement(QfMeasurement(0.568 * Sb, 0.008 * Sb, br1))
    grid.add_qf_measurement(QfMeasurement(0.663 * Sb, 0.008 * Sb, br2))
    #grid.add_qi_measurement(QiMeasurement(-0.286 * Sb, 0.01 * Sb, b2))
    grid.add_vm_measurement(VmMeasurement(1.006, 0.004, b1))
    grid.add_vm_measurement(VmMeasurement(0.968, 0.004, b2))


    # --- SE without pseudo-measurements ---
    se_options_no_pseudo = StateEstimationOptions(
        fixed_slack=False,
        run_observability_analyis=True,
        add_pseudo_measurements=False,  # no pseudo
        pseudo_meas_std=1.0,
        solver=gce.SolverType.NR, # NR used because in LM and GN we have relaxations that tend the
        # solution to converge
        verbose=0
    )
    se_no_pseudo = StateEstimation(circuit=grid, options=se_options_no_pseudo)
    se_no_pseudo.run()
    report_no_pseudo = se_no_pseudo.results.convergence_reports[0]
    assert report_no_pseudo
    assert not report_no_pseudo.is_observable
    # Expect: no convergence
    assert not report_no_pseudo.converged(), "SE should NOT converge without pseudo-measurements."

    # --- SE with pseudo-measurements ---
    se_options_pseudo = StateEstimationOptions(
        fixed_slack=False,
        run_observability_analyis=True,
        add_pseudo_measurements=True,  # add pseudo
        pseudo_meas_std=1,
        solver=gce.SolverType.NR,
        verbose=2
    )
    se_pseudo = StateEstimation(circuit=grid, options=se_options_pseudo)
    se_pseudo.run()
    report_pseudo = se_pseudo.results.convergence_reports[0]

    assert report_pseudo.is_observable
    # Expect: convergence
    assert report_pseudo.converged(), "SE should converge once pseudo-measurements are added."

    # --- Additional sanity checks ---
    # At least 1 pseudo-measurement was created
    pseudo_meas = report_pseudo.get_pseudo_measurements()
    assert np.isclose(report_pseudo.get_pseudo_measurements()[0].value, 1513.6824, rtol=1e-6)
    assert len(pseudo_meas) > 0, "Expected pseudo-measurements to be added."

    # Unobservable buses were made observable
    unobs_before = report_no_pseudo.get_unobservable_buses()

    unobs_after = report_pseudo.get_unobservable_buses()
    assert len(unobs_before[0]) > 0, "Expected unobservable buses without pseudo-measurements."
    assert unobs_after[0]==unobs_before[0], "Expected unobservable buses without pseudo-measurements."
    print(f"unobservable_buses_before={unobs_before}",
          f"unobservable_buses_after={unobs_after}",
          f"bus_contributions={report_pseudo.get_bus_contribution()}")
    print("Test passed: SE fails without pseudo-measurements but converges when they are added.")