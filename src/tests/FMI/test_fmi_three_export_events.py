# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Native FMI 3 coverage for external, time, and state event families."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fmpy import simulate_fmu
from fmpy.validation import validate_fmu

from VeraGridEngine.IO.fmu.compiler import fmu_compiler_available
from tests.FMI.fmi_test_support import (
    export_test_fmi_three_external_discontinuity_cs_fmu,
    export_test_fmi_three_state_event_me_fmu,
    export_test_fmi_three_time_event_me_fmu,
)


@pytest.mark.skipif(not fmu_compiler_available(), reason="No usable FMU compiler is configured")
def test_fmi_three_external_discontinuity_cs(tmp_path: Path) -> None:
    """Apply one exact external step and compare the CS state with its oracle.

    :param tmp_path: Isolated directory for the generated FMU archive.
    :return: None.
    """
    fmu_path: Path = export_test_fmi_three_external_discontinuity_cs_fmu(tmp_path)
    input_schedule: np.ndarray = np.array(
        list(((0.0, 0.0), (0.02, 0.0), (0.02, 1.0), (0.05, 1.0))),
        dtype=list((("time", np.float64), ("u", np.float64))),
    )
    assert validate_fmu(str(fmu_path)) == list()
    result: np.ndarray = simulate_fmu(
        str(fmu_path),
        stop_time=0.05,
        output_interval=1.0e-3,
        input=input_schedule,
        output=list(("x",)),
    )
    expected: np.ndarray = np.maximum(0.0, result["time"] - 0.02)
    np.testing.assert_allclose(result["x"], expected, rtol=0.0, atol=2.0e-7)


@pytest.mark.skipif(not fmu_compiler_available(), reason="No usable FMU compiler is configured")
def test_fmi_three_time_event_me(tmp_path: Path) -> None:
    """Verify that ME announces and applies one ordinary time event.

    :param tmp_path: Isolated directory for the generated FMU archive.
    :return: None.
    """
    fmu_path: Path = export_test_fmi_three_time_event_me_fmu(tmp_path)
    assert validate_fmu(str(fmu_path)) == list()
    result: np.ndarray = simulate_fmu(
        str(fmu_path),
        stop_time=0.03,
        solver="Euler",
        step_size=1.0e-3,
        output_interval=1.0e-3,
        output=list(("x", "event_mode")),
    )
    rising_edges: np.ndarray = np.flatnonzero(np.diff(result["event_mode"]) > 0.5)
    assert len(rising_edges) == 1
    transition_time: float = float(result["time"][rising_edges[0] + 1])
    assert abs(transition_time - 0.01) <= 2.0e-5
    assert abs(float(result["x"][-1]) - 0.02) <= 2.0e-7


@pytest.mark.skipif(not fmu_compiler_available(), reason="No usable FMU compiler is configured")
def test_fmi_three_state_zero_crossing_me(tmp_path: Path) -> None:
    """Verify importer localization of one ME event-indicator zero crossing.

    :param tmp_path: Isolated directory for the generated FMU archive.
    :return: None.
    """
    fmu_path: Path = export_test_fmi_three_state_event_me_fmu(tmp_path)
    assert validate_fmu(str(fmu_path)) == list()
    result: np.ndarray = simulate_fmu(
        str(fmu_path),
        stop_time=0.03,
        output_interval=1.0e-3,
        output=list(("x", "event_mode")),
    )
    rising_edges: np.ndarray = np.flatnonzero(np.diff(result["event_mode"]) > 0.5)
    assert len(rising_edges) == 1
    transition_time: float = float(result["time"][rising_edges[0] + 1])
    assert abs(transition_time - 0.015) <= 2.0e-5
    np.testing.assert_allclose(result["x"], result["time"], rtol=0.0, atol=2.0e-7)
