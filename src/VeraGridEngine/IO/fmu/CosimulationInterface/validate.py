# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from contextlib import contextmanager
import fmpy
import fmpy.fmi2
import fmpy.validation
from pathlib import Path
import shutil
import tempfile

from VeraGridEngine.IO.fmu.CosimulationInterface.export_ir import ExportModel, VariableCategory

def validate_export_model(export_model: ExportModel) -> list[str]:
    """Execute the `validate_export_model` operation.

    :param export_model: Function input.
    :return: Function result.
    """
    warnings: list[str] = []

    vr_values = [variable.value_reference for variable in export_model.exposed_variables() if variable.value_reference is not None]
    if len(vr_values) != len(set(vr_values)):
        raise ValueError("Duplicate FMI valueReference values detected in export model")

    exposed_names = [variable.name for variable in export_model.exposed_variables()]
    duplicate_names = sorted({name for name in exposed_names if exposed_names.count(name) > 1})
    if duplicate_names:
        raise ValueError(f"Duplicate exposed FMI variable names: {', '.join(duplicate_names)}")

    state_count = export_model.counts.get("states", 0)
    algebraic_count = export_model.counts.get("algebraics", 0)
    state_eq_count = len([equation for equation in export_model.equations if equation.group.value == "state"])
    algebraic_eq_count = len([equation for equation in export_model.equations if equation.group.value == "algebraic"])
    if state_count != state_eq_count:
        raise ValueError(f"State equation count mismatch: {state_count} states vs {state_eq_count} equations")
    if algebraic_count != algebraic_eq_count:
        raise ValueError(f"Algebraic equation count mismatch: {algebraic_count} algebraics vs {algebraic_eq_count} equations")

    output_variables = [variable for variable in export_model.variables if variable.exposed and variable.causality == "output"]
    if len(output_variables) == 0:
        warnings.append("The exported model exposes no FMI outputs")

    diff_variables = [variable for variable in export_model.variables if variable.category == VariableCategory.DIFF]
    missing_base = [variable.name for variable in diff_variables if variable.diff_base_uid is None]
    if missing_base:
        raise ValueError(f"Diff variables without base states are not exportable: {', '.join(missing_base)}")

    base_variables = {variable.uid: variable for variable in export_model.variables}
    invalid_base: list[str] = []
    for variable in diff_variables:
        base_uid = variable.diff_base_uid
        if base_uid is None:
            continue
        if base_variables[base_uid].category not in {VariableCategory.STATE, VariableCategory.ALGEBRAIC}:
            invalid_base.append(variable.name)
    if invalid_base:
        raise ValueError(f"Diff variables must reference state or algebraic bases: {', '.join(invalid_base)}")

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

    root = Path(extraction_root) if extraction_root is not None else path.parent
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
    output_interval: float | None = None,
):
    """Execute the `simulate_fmu_with_fmpy` operation.

    :param fmu_path: Function input.
    :param stop_time: Function input.
    :param output: Function input.
    :param start_values: Function input.
    :param input_signal: Function input.
    :param extraction_root: Function input.
    :param output_interval: Function input.
    :return: Function result.
    """
    simulate_fmu = fmpy.simulate_fmu

    with prepare_fmu_for_fmpy(fmu_path, extraction_root=extraction_root) as prepared_path:
        return simulate_fmu(
            str(prepared_path),
            stop_time=stop_time,
            output=output,
            start_values=start_values or {},
            input=input_signal,
            output_interval=output_interval,
        )


def smoke_test_cs_fmu_with_fmpy(
    fmu_path: str | Path,
    *,
    start_values: dict[str, float] | None = None,
    step_size: float = 1e-4,
    output_name: str,
    extraction_root: str | Path | None = None,
) -> dict[str, float]:
    """Execute the `smoke_test_cs_fmu_with_fmpy` operation.

    :param fmu_path: Function input.
    :param start_values: Function input.
    :param step_size: Function input.
    :param output_name: Function input.
    :param extraction_root: Function input.
    :return: Function result.
    """
    fmi2_module = fmpy.fmi2
    read_model_description = fmpy.read_model_description
    FMU2Slave = fmi2_module.FMU2Slave

    with prepare_fmu_for_fmpy(fmu_path, extraction_root=extraction_root) as extracted_dir:
        model_description = read_model_description(str(extracted_dir))
        value_references = {variable.name: variable.valueReference for variable in model_description.modelVariables}
        slave = FMU2Slave(
            guid=model_description.guid,
            modelIdentifier=model_description.coSimulation.modelIdentifier,
            unzipDirectory=str(extracted_dir),
            instanceName=model_description.modelName,
        )

        slave.instantiate()
        try:
            slave.setupExperiment(startTime=0.0)
            slave.enterInitializationMode()
            if start_values:
                vr = [value_references[name] for name in start_values]
                values = [float(start_values[name]) for name in start_values]
                slave.setReal(vr, values)
            slave.exitInitializationMode()
            before = float(slave.getReal([value_references[output_name]])[0])
            slave.doStep(currentCommunicationPoint=0.0, communicationStepSize=step_size)
            after = float(slave.getReal([value_references[output_name]])[0])
            slave.reset()
            slave.setupExperiment(startTime=0.0)
            slave.enterInitializationMode()
            slave.exitInitializationMode()
            reset_value = float(slave.getReal([value_references[output_name]])[0])
            slave.terminate()
            return {
                "before": before,
                "after": after,
                "reset": reset_value,
            }
        finally:
            slave.freeInstance()
