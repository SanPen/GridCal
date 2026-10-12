# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Host-native reproducibility gates for the generated FMI 3 test FMU."""

from __future__ import annotations

from pathlib import Path
import zipfile

import fmpy
from fmpy.fmi1 import FMICallException
from fmpy.fmi3 import FMU3Slave, fmi3FMUState
from fmpy.model_description import ModelDescription
from fmpy.template import create_fmu
import pytest

from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from tests.FMI.fmi_three_compiled_fixture import (
    FmiThreeCompiledFixtureProfile,
    _create_fmi_three_scalar_model_description,
    _install_fmi_three_behavior,
)
from VeraGridEngine.IO.fmu.Elements.bindings import FmuImportConfig
from VeraGridEngine.IO.fmu import FmiThreeWorkerHostLimits
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuCsDeviceConfigRecord,
    FmuMeDeviceConfigRecord,
    load_fmu_cs_device_config,
    load_fmu_me_device_config,
)
from VeraGridEngine.IO.fmu.Elements.inspection import FmuInspectionResult, inspect_fmu
from VeraGridEngine.IO.fmu.model_description import (
    FmuModelDescription,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.Elements.description import (
    FmiThreeCoSimulationCapabilities,
)
from VeraGridEngine.IO.fmu.native_binary import (
    resolve_fmi_three_host_binary,
    validate_fmi_three_native_binary,
)
from VeraGridEngine.IO.fmu.profile import (
    validate_fmi_three_co_simulation_worker_profile,
)
from VeraGridEngine.IO.fmu.fmu_device_integration import configure_fmu_template
from VeraGridEngine.enumerations import (
    DeviceType,
    FmuInterfaceMode,
    FmuTemplateDomain,
    FmuTemplateMode,
)


def _open_fmi_three_reference_runtime(
    compiled_fmu_path: Path,
    extracted_directory: Path,
    instantiation_token_override: str | None,
) -> FMU3Slave:
    """Load the generated FMU through FMPy's resolved FMI 3 symbol surface.

    :param compiled_fmu_path: Host-native temporary FMU fixture.
    :param extracted_directory: Fresh directory receiving the FMU contents.
    :param instantiation_token_override: Token used instead of declared metadata.
    :return: Loaded but not yet instantiated FMPy Co-Simulation runtime.
    """

    fmpy.extract(compiled_fmu_path, unzipdir=extracted_directory)
    fmpy_description: ModelDescription = fmpy.read_model_description(
        compiled_fmu_path,
        validate=True,
    )
    if fmpy_description.coSimulation is not None:
        if fmpy_description.coSimulation.modelIdentifier is not None:
            model_identifier: str = fmpy_description.coSimulation.modelIdentifier
        else:
            raise AssertionError("FMPy did not retain the Co-Simulation identifier")
    else:
        raise AssertionError("FMPy did not retain the Co-Simulation interface")
    if instantiation_token_override is not None:
        instantiation_token: str = instantiation_token_override
    else:
        if fmpy_description.instantiationToken is not None:
            instantiation_token = fmpy_description.instantiationToken
        else:
            raise AssertionError("FMPy did not retain the instantiation token")

    # Construction resolves the FMI 3 function table while leaving the FMU
    # uninstantiated so each test controls when instantiate() is called.
    return FMU3Slave(
        guid=instantiation_token,
        modelIdentifier=model_identifier,
        unzipDirectory=str(extracted_directory),
        instanceName="veragrid-fmi-three-reference-lifecycle",
    )


def test_compiled_fmi_three_fmu_passes_inspection_profile_and_preflight(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
) -> None:
    """Verify required scalar fixture assets while product runtime stays gated.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Host-native temporary FMU fixture.
    :return: None.
    """

    inspection: FmuInspectionResult = inspect_fmu(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    metadata: FmuModelDescription = read_fmu_model_description(
        compiled_fmi_three_scalar_co_simulation_fmu
    )
    validate_fmi_three_co_simulation_worker_profile(
        metadata=metadata,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
    )
    capabilities: FmiThreeCoSimulationCapabilities | None = (
        metadata.fmi_three_co_simulation_capabilities
    )
    if capabilities is not None:
        pass
    else:
        raise AssertionError(
            "The compiled Co-Simulation fixture lost its capabilities"
        )
    assert capabilities.provides_intermediate_update
    assert capabilities.might_return_early_from_do_step
    assert capabilities.can_return_early_after_intermediate_update
    assert capabilities.has_event_mode
    model_identifier: str = metadata.get_model_identifier(
        FmuInterfaceMode.CO_SIMULATION
    )
    validate_fmi_three_native_binary(
        receipt=inspection.receipt,
        model_identifier=model_identifier,
    )

    # The packaged FMU must own both its reference sources and its exact native
    # binary. No external file participates after this archive is produced.
    platform_tuple: str
    library_suffix: str
    platform_tuple, library_suffix = resolve_fmi_three_host_binary()
    expected_binary_entry: str = (
        f"binaries/{platform_tuple}/{model_identifier}{library_suffix}"
    )
    assert inspection.receipt.get_contains_source_code()
    assert inspection.receipt.binary_entries == (expected_binary_entry,)
    with zipfile.ZipFile(compiled_fmi_three_scalar_co_simulation_fmu, "r") as archive:
        archive_entries: set[str] = set(archive.namelist())
        packaged_model_source: str = archive.read("sources/model.c").decode("utf-8")
    assert "modelDescription.xml" in archive_entries
    assert "sources/buildDescription.xml" in archive_entries
    assert "sources/model.c" in archive_entries
    assert "sources/fmi3PlatformTypes.h" in archive_entries
    assert "sources/fmi3FunctionTypes.h" in archive_entries
    assert "sources/fmi3Functions.h" in archive_entries
    assert expected_binary_entry in archive_entries
    assert packaged_model_source.count("fmi3Status fmi3DoStep(") == 1
    assert "const fmi3Float64 completedObservation" in packaged_model_source
    assert "fmi3Boolean early_return_allowed;" in packaged_model_source
    assert (
        "model->early_return_allowed = earlyReturnAllowed;"
        in packaged_model_source
    )

    # Interface selection is now shared by FMI 2 and FMI 3. Worker-profile
    # validation remains a separate responsibility of the concrete consumer.
    import_config: FmuImportConfig = FmuImportConfig(
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu
    )
    assert (
        import_config.resolve_execution_mode(metadata)
        == FmuInterfaceMode.CO_SIMULATION
    )


@pytest.mark.parametrize(
    ("domain", "mode"),
    (
        (FmuTemplateDomain.RMS, FmuTemplateMode.CO_SIMULATION),
        (FmuTemplateDomain.RMS, FmuTemplateMode.MODEL_EXCHANGE),
        (FmuTemplateDomain.EMT, FmuTemplateMode.CO_SIMULATION),
        (FmuTemplateDomain.EMT, FmuTemplateMode.MODEL_EXCHANGE),
    ),
)
def test_compiled_fmi_three_fmu_configures_supported_templates(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    domain: FmuTemplateDomain,
    mode: FmuTemplateMode,
) -> None:
    """Persist one explicit worker policy through every FMI 3 template path.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Dual-interface native
        FMI 3 scalar fixture.
    :param domain: VeraGrid simulation domain selected by the test case.
    :param mode: FMI interface selected by the test case.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=65536,
        maximum_float64_values_per_request=32,
        response_timeout_seconds=3.0,
        graceful_join_timeout_seconds=1.0,
        terminate_join_timeout_seconds=0.5,
        kill_join_timeout_seconds=0.25,
    )
    template: FmuTemplate = FmuTemplate(name="")
    var_factory: VarFactory = VarFactory(
        name=f"FmiThree{domain.value}{mode.value}TemplateFactory"
    )
    configured_template: FmuTemplate = configure_fmu_template(
        template=template,
        var_factory=var_factory,
        fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        device_tpe=DeviceType.LoadDevice,
        domain=domain,
        mode=mode,
        worker_limits=worker_limits,
    )
    restored_limits: FmiThreeWorkerHostLimits | None
    if mode == FmuTemplateMode.CO_SIMULATION:
        cs_record: FmuCsDeviceConfigRecord | None = load_fmu_cs_device_config(
            configured_template.serialized_config
        )
        if cs_record is not None:
            restored_limits = cs_record.worker_limits
        else:
            raise AssertionError("FMI 3 Co-Simulation template record was not restored")
    else:
        me_record: FmuMeDeviceConfigRecord | None = load_fmu_me_device_config(
            configured_template.serialized_config
        )
        if me_record is not None:
            restored_limits = me_record.worker_limits
        else:
            raise AssertionError("FMI 3 Model Exchange template record was not restored")
    if restored_limits is not None:
        pass
    else:
        raise AssertionError("FMI 3 template record lost its explicit worker limits")
    assert configured_template is template
    assert restored_limits.maximum_frame_size == worker_limits.maximum_frame_size
    assert (
        restored_limits.maximum_float64_values_per_request
        == worker_limits.maximum_float64_values_per_request
    )
    assert (
        restored_limits.response_timeout_seconds
        == worker_limits.response_timeout_seconds
    )
    assert (
        restored_limits.graceful_join_timeout_seconds
        == worker_limits.graceful_join_timeout_seconds
    )
    assert (
        restored_limits.terminate_join_timeout_seconds
        == worker_limits.terminate_join_timeout_seconds
    )
    assert (
        restored_limits.kill_join_timeout_seconds
        == worker_limits.kill_join_timeout_seconds
    )


def test_compiled_fmi_three_fmu_supports_deterministic_scalar_steps(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Verify two exact synthetic scalar steps through the native FMI 3 ABI.

    This direct reference smoke test is deliberately outside VeraGrid's runtime
    host. It proves the generated source advances time and computes its declared
    non-electrical scalar observation without weakening the product execution gate.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Host-native temporary FMU fixture.
    :param tmp_path: Isolated extraction directory supplied by pytest.
    :return: None.
    """

    extracted_directory: Path = tmp_path / "reference-runtime"
    runtime: FMU3Slave = _open_fmi_three_reference_runtime(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        extracted_directory=extracted_directory,
        instantiation_token_override=None,
    )
    instantiated: bool = False
    try:
        assert runtime.fmi3GetVersion() == b"3.0"
        runtime.instantiate(
            visible=False,
            loggingOn=False,
            eventModeUsed=False,
            earlyReturnAllowed=False,
            requiredIntermediateVariables=list(),
        )
        instantiated = True
        runtime.enterInitializationMode(
            tolerance=1.0e-6,
            startTime=1.0,
            stopTime=2.0,
        )
        runtime.setFloat64(list((1,)), list((2.0,)))
        initialized_values: list[float] = runtime.getFloat64(list((0, 1, 2)))
        assert initialized_values == pytest.approx(list((1.0, 2.0, 0.0)))
        runtime.exitInitializationMode()
        first_step: tuple[bool, bool, bool, float] = runtime.doStep(
            currentCommunicationPoint=1.0,
            communicationStepSize=0.25,
        )
        assert first_step == (False, False, False, 1.25)
        first_values: list[float] = runtime.getFloat64(list((0, 1, 2)))
        assert first_values == pytest.approx(list((1.25, 2.0, 3.25)))
        runtime.setFloat64(list((1,)), list((-1.0,)))
        second_step: tuple[bool, bool, bool, float] = runtime.doStep(
            currentCommunicationPoint=1.25,
            communicationStepSize=0.25,
        )
        assert second_step == (False, False, False, 1.5)
        second_values: list[float] = runtime.getFloat64(list((0, 1, 2)))
        assert second_values == pytest.approx(list((1.5, -1.0, 0.5)))
        runtime.terminate()
    finally:
        if instantiated:
            runtime.freeInstance()
        else:
            runtime.freeLibrary()


def test_compiled_fmi_three_scalar_fixture_exposes_int32_access_and_rollback(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Verify direct Int32 ABI access and mixed native-state restoration.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Host-native scalar FMU.
    :param tmp_path: Isolated extraction directory supplied by pytest.
    :return: None.
    """

    runtime: FMU3Slave = _open_fmi_three_reference_runtime(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        extracted_directory=tmp_path / "int32-reference-runtime",
        instantiation_token_override=None,
    )
    instantiated: bool = False
    native_state: fmi3FMUState | None = None
    try:
        runtime.instantiate(
            visible=False,
            loggingOn=False,
            eventModeUsed=False,
            earlyReturnAllowed=False,
            requiredIntermediateVariables=list(),
        )
        instantiated = True
        runtime.enterInitializationMode(
            tolerance=1.0e-6,
            startTime=0.0,
            stopTime=1.0,
        )
        runtime.setFloat64(list((1,)), list((2.0,)))
        runtime.setInt32(list((7,)), list((-2,)))
        assert runtime.getInt32(list((7, 8))) == list((-2, 0))
        runtime.exitInitializationMode()

        native_state = runtime.getFMUState()
        runtime.setFloat64(list((1,)), list((3.0,)))
        runtime.setInt32(list((7,)), list((-2147483648,)))
        assert runtime.doStep(
            currentCommunicationPoint=0.0,
            communicationStepSize=0.25,
        ) == (False, False, False, 0.25)
        assert runtime.getInt32(list((8, 7))) == list(
            (-2147483648, -2147483648)
        )

        # One native snapshot restores Float64, Int32, outputs, and time together.
        runtime.setFMUState(native_state)
        assert runtime.getFloat64(list((0, 1, 2))) == pytest.approx(
            list((0.0, 2.0, 0.0))
        )
        assert runtime.getInt32(list((7, 8))) == list((-2, 0))
        runtime.terminate()
    finally:
        if native_state is not None:
            runtime.freeFMUState(native_state)
        else:
            pass
        if instantiated:
            runtime.freeInstance()
        else:
            runtime.freeLibrary()


def test_compiled_fmi_three_fmu_rejects_zero_communication_step(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Return an FMI error for a zero communication step.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Host-native temporary FMU fixture.
    :param tmp_path: Isolated extraction directory supplied by pytest.
    :return: None.
    """

    runtime: FMU3Slave = _open_fmi_three_reference_runtime(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        extracted_directory=tmp_path / "invalid-step-runtime",
        instantiation_token_override=None,
    )
    instantiated: bool = False
    try:
        runtime.instantiate(
            visible=False,
            loggingOn=False,
            eventModeUsed=False,
            earlyReturnAllowed=False,
            requiredIntermediateVariables=list(),
        )
        instantiated = True
        runtime.enterInitializationMode(
            tolerance=None,
            startTime=0.0,
            stopTime=None,
        )
        runtime.exitInitializationMode()
        with pytest.raises(FMICallException, match="fmi3DoStep failed with status 3"):
            runtime.doStep(
                currentCommunicationPoint=0.0,
                communicationStepSize=0.0,
            )
    finally:
        if instantiated:
            runtime.freeInstance()
        else:
            runtime.freeLibrary()


def test_fmi_three_scalar_behavior_rejects_fmpy_template_drift(
    tmp_path: Path,
) -> None:
    """Fail before compilation when the approved FMPy doStep stub changes.

    :param tmp_path: Isolated directory holding one altered generated source.
    :return: None.
    """

    staging_directory: Path = tmp_path / "changed-template"
    source_fmu_path: Path = tmp_path / "rendered-source.fmu"
    create_fmu(
        _create_fmi_three_scalar_model_description(),
        source_fmu_path,
    )
    fmpy.extract(source_fmu_path, unzipdir=staging_directory)
    model_source_path: Path = staging_directory / "sources" / "model.c"
    generated_source: bytearray = bytearray(model_source_path.read_bytes())
    do_step_marker: bytes = b"fmi3Status fmi3DoStep("
    do_step_start: int = generated_source.find(do_step_marker)
    if do_step_start >= 0:
        drift_index: int = do_step_start + len(do_step_marker)
        generated_source[drift_index] = ord(" ")
    else:
        raise AssertionError("The installed FMPy template has no doStep block")
    model_source_path.write_bytes(bytes(generated_source))
    with pytest.raises(AssertionError, match="changed the FMI 3 doStep source block"):
        _install_fmi_three_behavior(
            staging_directory=staging_directory,
            fixture_profile=FmiThreeCompiledFixtureProfile.SCALAR,
        )


def test_compiled_fmi_three_fmu_rejects_wrong_instantiation_token(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Verify the native FMI 3 boundary rejects a mismatched identity token.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Host-native temporary FMU fixture.
    :param tmp_path: Isolated extraction directory supplied by pytest.
    :return: None.
    """

    runtime: FMU3Slave = _open_fmi_three_reference_runtime(
        compiled_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        extracted_directory=tmp_path / "wrong-token-runtime",
        instantiation_token_override="wrong-veragrid-instantiation-token",
    )
    try:
        with pytest.raises(Exception, match="Failed to instantiate FMU"):
            runtime.instantiate(
                visible=False,
                loggingOn=False,
                eventModeUsed=False,
                earlyReturnAllowed=False,
                requiredIntermediateVariables=list(),
            )
    finally:
        runtime.freeLibrary()
