# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Compare three ways of obtaining the default two-bus fault's final state.

Run: .venv/bin/python examples/benchmark_dynamic_fault_equilibrium.py
Imports, pre-fault preparation, plotting and file export are outside solve timers.
Both RMS methods reuse the same compiled model and start from pre-fault values.
The legacy driver recompiles its numerical circuit during every run; its internal
Newton solve is additionally reported from the existing convergence log.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
from time import perf_counter

import numpy as np

from dynamic_fault_equilibrium import (
    BackEulerImplicitIntegration, Ref, build_case, build_hardcoded_reference,
    equilibrium_residual, prepare_prefault, solve_equilibrium, vg,
)


def benchmark(repeats: int = 7) -> dict:
    """Warm once, rotate method order, and validate every timed solution."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    start = perf_counter()
    grid, pf, problem, converter, source, fault, options = build_case()
    initial = prepare_prefault(problem)
    rms_setup = perf_counter() - start
    start = perf_counter()
    reference_pf, reference_driver = build_hardcoded_reference(fault_r=0.15)
    legacy_setup = perf_counter() - start
    np.testing.assert_allclose(pf.voltage, reference_pf.voltage[:2], atol=1e-9, rtol=0)
    vm = [problem.get_var_idx(bus.rms_model.external_mapping[Ref.Vm]) for bus in grid.buses]
    va = [problem.get_var_idx(bus.rms_model.external_mapping[Ref.Va]) for bus in grid.buses]

    def trajectory():
        problem.reset_boundary_update_state(0.0)
        solver = BackEulerImplicitIntegration(problem, t0=0.0, t_end=1.0, h=0.001,
                                             max_iter=40, tolerance=1e-9)
        start = perf_counter()
        times, values, initialized, converged = solver.simulate()
        elapsed = perf_counter() - start
        assert initialized and converged
        problem.update_variable_params(t=times[-1], x_snapshot=values[-1], scheduled_t=times[-1])
        assert np.linalg.norm(equilibrium_residual(problem, values[-1]), np.inf) < 1e-6
        return elapsed, values[-1].copy()

    def equilibrium():
        start = perf_counter()
        values, trace = solve_equilibrium(problem, initial)
        elapsed = perf_counter() - start
        assert trace[-1] < 1e-10
        return elapsed, values

    def legacy():
        # A fresh driver excludes accumulated logger/results state, while the
        # prepared grid and pre-fault solution are reused just as for RMS.
        driver = vg.ShortCircuitDriver(
            grid=reference_driver.grid, options=reference_driver.options,
            pf_options=reference_driver.pf_options, pf_results=reference_pf,
            pf_results3ph=None,
        )
        start = perf_counter()
        driver.run()
        elapsed = perf_counter() - start
        timings = []
        for entry in driver.logger.entries:
            assert "did not converge" not in entry.msg
            if entry.msg == "Short-circuit VSC Newton-Raphson converged":
                match = re.search(r"elapsed=([0-9.eE+-]+) s", str(entry.value))
                assert match is not None
                timings.append(float(match.group(1)))
        assert len(timings) == 1
        return elapsed, driver.results.voltage1[:2, 0].copy(), timings[0]

    methods = {"full_trajectory": trajectory, "direct_equilibrium": equilibrium, "legacy_driver": legacy}

    def one_round(order):
        outputs = {name: methods[name]() for name in order}
        values = outputs["direct_equilibrium"][1]
        np.testing.assert_allclose(outputs["full_trajectory"][1], values, atol=1e-6, rtol=0)
        voltage = values[vm] * np.exp(1j * values[va])
        np.testing.assert_allclose(outputs["legacy_driver"][1], voltage, atol=1e-6, rtol=0)
        return {**{name: float(output[0]) for name, output in outputs.items()},
                "legacy_newton_only": outputs["legacy_driver"][2]}

    names = list(methods)
    first_use = one_round(names)
    samples = []
    for repeat in range(repeats):
        offset = repeat % len(names)
        sample = one_round(names[offset:] + names[:offset])
        samples.append(sample)
        print(f"Run {repeat + 1}/{repeats}: " + ", ".join(f"{name}={sample[name]:.6f} s" for name in names), flush=True)
    stats = {name: {"median_seconds": float(np.median([sample[name] for sample in samples])),
                    "min_seconds": min(sample[name] for sample in samples),
                    "max_seconds": max(sample[name] for sample in samples)} for name in first_use}
    return dict(
        measured_at_utc=datetime.now(timezone.utc).isoformat(),
        python_version=platform.python_version(), platform=platform.platform(), repeats=repeats,
        physical_simulation_duration_seconds=1.0, integration_step_seconds=0.001,
        fault_application_seconds=0.1, fault_resistance_pu=0.15,
        setup_seconds={"rms_grid_power_flow_and_compilation": rms_setup,
                       "legacy_grid_and_power_flow": legacy_setup},
        first_use_solve_seconds=first_use, warm_samples_seconds=samples, warm_stats=stats,
        scope="Imports and reporting excluded. RMS setup includes model compilation and pre-fault power flow. "
              "Legacy driver timing includes numerical-circuit compilation, fault assembly and result extraction; "
              "the Newton-only timing is also reported. First-use timings are not clean-cache cold-start measurements.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path, default=Path("output/dynamic_fault_equilibrium/timing.json"))
    args = parser.parse_args()
    report = benchmark(args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"setup_seconds": report["setup_seconds"], "warm_stats": report["warm_stats"]}, indent=2))
    print(f"Saved {args.output.resolve()}")


if __name__ == "__main__":
    main()
