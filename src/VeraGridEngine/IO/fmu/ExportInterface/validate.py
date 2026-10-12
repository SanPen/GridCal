# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from contextlib import contextmanager
import fmpy
import fmpy.validation
from pathlib import Path
import shutil
import tempfile
from typing import Any

from VeraGridEngine.IO.fmu.ExportInterface.export_ir import ExportModel, VariableCategory

def _default_extraction_root() -> Path:
    """Execute the `_default_extraction_root` operation.

    :return: Function result.
    """
    return Path(__file__).resolve().parent / ".fmpy_extract"


def _merge_start_values(start_values: dict[str, float] | None, input_signal: Any) -> dict[str, float]:
    """Execute the `_merge_start_values` operation.

    :param start_values: Function input.
    :param input_signal: Function input.
    :return: Function result.
    """
    merged = dict(start_values or {})
    if input_signal is None:
        return merged
    names = input_signal.dtype.names
    if names is None or len(names) == 0:
        return merged
    if len(input_signal) == 0:
        return merged
    first = input_signal[0]
    for name in names:
        if name == "time" or name in merged:
            continue
        merged[name] = float(first[name])
    return merged


def validate_export_model(export_model: ExportModel) -> list[str]:
    """Execute the `validate_export_model` operation.

    :param export_model: Function input.
    :return: Function result.
    """
    warnings: list[str] = []

    vr_values = [variable.value_reference for variable in export_model.variables]
    if len(vr_values) != len(set(vr_values)):
        raise ValueError("Duplicate FMI valueReference values detected in export model")

    names = [variable.name for variable in export_model.variables]
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    if duplicate_names:
        raise ValueError(f"Duplicate exported FMI variable names: {', '.join(duplicate_names)}")

    state_count = export_model.counts.get("states", 0)
    derivative_count = export_model.counts.get("derivatives", 0)
    if derivative_count != state_count:
        raise ValueError(f"Model Exchange export requires one derivative variable per state: {state_count} states vs {derivative_count} derivatives")

    derivative_eq_count = len([equation for equation in export_model.equations if equation.group.value == "derivative"])
    if derivative_eq_count != state_count:
        raise ValueError(f"Derivative equation count mismatch: {state_count} states vs {derivative_eq_count} derivative equations")

    algebraic_count = export_model.counts.get("algebraics", 0)
    algebraic_eq_count = len([equation for equation in export_model.equations if equation.group.value == "algebraic"])
    if algebraic_eq_count != algebraic_count:
        raise ValueError(f"Algebraic equation count mismatch: {algebraic_count} algebraics vs {algebraic_eq_count} equations")

    derivative_variables = [variable for variable in export_model.variables if variable.category == VariableCategory.DERIVATIVE]
    missing_base = [variable.name for variable in derivative_variables if variable.derivative_of_uid is None]
    if missing_base:
        raise ValueError(f"Derivative variables without base states are not exportable: {', '.join(missing_base)}")

    output_variables = [variable for variable in export_model.variables if variable.causality == "output"]
    if not output_variables:
        warnings.append("The exported model exposes no FMI outputs")

    return warnings


@contextmanager
def prepare_fmu_for_fmpy(
    fmu_path: str | Path,
    *,
    extraction_root: str | Path | None = None,
):
    """Execute the `prepare_fmu_for_fmpy` operation.

    :param fmu_path: Function input.
    :param extraction_root: Function input.
    :return: Function result.
    """
    extract = fmpy.extract

    path = Path(fmu_path)
    if path.is_dir() and (path / "modelDescription.xml").exists():
        yield path
        return

    root = Path(extraction_root) if extraction_root is not None else _default_extraction_root()
    root.mkdir(parents=True, exist_ok=True)
    extracted_dir = Path(tempfile.mkdtemp(prefix=f"{path.stem}_fmpy_", dir=str(root)))
    try:
        extract(str(path), unzipdir=str(extracted_dir))
        yield extracted_dir
    finally:
        shutil.rmtree(extracted_dir, ignore_errors=True)


def validate_fmu_with_fmpy(
    fmu_path: str | Path,
    *,
    extraction_root: str | Path | None = None,
) -> list[str]:
    """Execute the `validate_fmu_with_fmpy` operation.

    :param fmu_path: Function input.
    :param extraction_root: Function input.
    :return: Function result.
    """
    validate_fmu = fmpy.validation.validate_fmu

    with prepare_fmu_for_fmpy(fmu_path, extraction_root=extraction_root) as prepared_path:
        issues = validate_fmu(str(prepared_path))
        return list(issues or [])


def simulate_fmu_with_fmpy(
    fmu_path: str | Path,
    *,
    stop_time: float,
    output: list[str] | None = None,
    start_values: dict[str, float] | None = None,
    input_signal=None,
    extraction_root: str | Path | None = None,
    step_size: float | None = None,
):
    """Execute the `simulate_fmu_with_fmpy` operation.

    :param fmu_path: Function input.
    :param stop_time: Function input.
    :param output: Function input.
    :param start_values: Function input.
    :param input_signal: Function input.
    :param extraction_root: Function input.
    :param step_size: Function input.
    :return: Function result.
    """
    simulate_fmu = fmpy.simulate_fmu
    merged_start_values = _merge_start_values(start_values, input_signal)

    with prepare_fmu_for_fmpy(fmu_path, extraction_root=extraction_root) as prepared_path:
        return simulate_fmu(
            str(prepared_path),
            fmi_type="ModelExchange",
            solver="Euler",
            step_size=step_size,
            stop_time=stop_time,
            output=output,
            start_values=merged_start_values,
            input=input_signal,
        )
