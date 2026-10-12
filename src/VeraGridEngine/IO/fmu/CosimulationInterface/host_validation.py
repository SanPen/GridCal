# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
import numpy as np

from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.IO.fmu.config import ExportConfig, TargetPlatform, detect_target_platform
from VeraGridEngine.IO.fmu.CosimulationInterface.real_pilots import get_pilot_model, pilot_output_path
from VeraGridEngine.IO.fmu.CosimulationInterface.validate import simulate_fmu_with_fmpy, smoke_test_cs_fmu_with_fmpy, validate_fmu_with_fmpy


def export_and_validate_pilot(
    pilot_name: str,
    *,
    output_dir: str | Path,
    target_platform: TargetPlatform | None = None,
) -> dict[str, object]:
    """Execute the `export_and_validate_pilot` operation.

    :param pilot_name: Function input.
    :param output_dir: Function input.
    :param target_platform: Function input.
    :return: Function result.
    """
    pilot = get_pilot_model(pilot_name)
    output_path = pilot_output_path(output_dir, pilot)
    fmu_path = export_model_as_fmu(
        pilot.model,
        ExportConfig(
            model_name=pilot.name,
            output_path=output_path,
            target_platform=target_platform or detect_target_platform(),
            compile_binary=True,
        ),
    )
    return validate_exported_pilot(pilot_name, fmu_path)


def validate_exported_pilot(pilot_name: str, fmu_path: str | Path) -> dict[str, object]:
    """Execute the `validate_exported_pilot` operation.

    :param pilot_name: Function input.
    :param fmu_path: Function input.
    :return: Function result.
    """
    pilot = get_pilot_model(pilot_name)
    issues = validate_fmu_with_fmpy(fmu_path)
    input_signal = pilot.input_builder(pilot.stop_time)
    result = simulate_fmu_with_fmpy(
        fmu_path,
        stop_time=pilot.stop_time,
        output=list(pilot.outputs),
        start_values=pilot.fmpy_start_values,
        input_signal=input_signal,
    )
    smoke = smoke_test_cs_fmu_with_fmpy(
        fmu_path,
        start_values=pilot.smoke_set_values,
        step_size=min(1e-4, pilot.stop_time),
        output_name=pilot.outputs[0],
    )
    maxima = {name: float(np.max(np.abs(result[name]))) for name in pilot.outputs}
    return {
        "pilot": pilot.name,
        "fmu_path": str(fmu_path),
        "issues": issues,
        "samples": len(result),
        "last": {name: float(result[-1][name]) for name in pilot.outputs},
        "max_abs": maxima,
        "smoke": smoke,
    }
