# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Integration tests binding the FMI 2.0 runtime to private staging."""

from __future__ import annotations

import hashlib
import inspect
import os
from pathlib import Path
from unittest.mock import Mock, call
import zipfile

import pytest

from VeraGridEngine.IO.fmu.Elements.bindings import FmuImportConfig
from VeraGridEngine.IO.fmu.model_description import (
    FmuInterfaceMode,
    FmuModelDescription,
    FmuVariableDescription,
    FmuVariableType,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.Elements.description import (
    FmiOneCoSimulationCapabilities,
)
from VeraGridEngine.IO.fmu.native_binary import _resolve_legacy_host_binary
from VeraGridEngine.IO.fmu.host import FmuRuntimeHost, open_fmu_runtime_host
from VeraGridEngine.IO.fmu.staging import FmuStagingArea, stage_fmu_source


class _RecordingRuntime:
    """Record the lifecycle calls made by :class:`FmuRuntimeHost`.

    :param staging_root: Private root that must still exist during native release.
    """

    __slots__ = (
        "staging_root",
        "setup_count",
        "enter_initialization_count",
        "exit_initialization_count",
        "terminate_count",
        "free_count",
        "root_existed_during_free",
    )

    def __init__(self, staging_root: Path) -> None:
        """Initialize zeroed lifecycle counters.

        :param staging_root: Private root observed during ``freeInstance``.
        :return: None.
        """

        self.staging_root: Path = staging_root
        self.setup_count: int = 0
        self.enter_initialization_count: int = 0
        self.exit_initialization_count: int = 0
        self.terminate_count: int = 0
        self.free_count: int = 0
        self.root_existed_during_free: bool = False

    def setupExperiment(
        self,
        tolerance: float | None,
        startTime: float,
        stopTime: float | None,
    ) -> None:
        """Record one FMI setup transition.

        :param tolerance: Optional relative tolerance.
        :param startTime: Simulation start time.
        :param stopTime: Optional simulation stop time.
        :return: None.
        """

        self.setup_count += 1

    def enterInitializationMode(self) -> None:
        """Record entry into FMI initialization mode.

        :return: None.
        """

        self.enter_initialization_count += 1

    def exitInitializationMode(self) -> None:
        """Record exit from FMI initialization mode.

        :return: None.
        """

        self.exit_initialization_count += 1

    def terminate(self) -> None:
        """Record one FMI termination request.

        :return: None.
        """

        self.terminate_count += 1

    def freeInstance(self) -> None:
        """Record native release and whether staging still exists.

        :return: None.
        """

        self.free_count += 1
        self.root_existed_during_free = self.staging_root.exists()


def _co_simulation_artifact() -> Path:
    """Return the certified repository FMI 2.0 Co-Simulation artifact.

    :return: Absolute path to the versioned Windows FMU.
    """

    tests_root: Path = Path(__file__).resolve().parents[1]
    artifact: Path = tests_root / "data" / "fmi" / "artifacts" / "FrequencyLoadPilot.fmu"
    return artifact


def _model_exchange_artifact() -> Path:
    """Return the existing repository FMI 2.0 Model Exchange artifact.

    :return: Absolute path to the versioned Windows FMU.
    """

    tests_root: Path = Path(__file__).resolve().parents[1]
    artifact: Path = (
        tests_root
        / "data"
        / "fmi"
        / "artifacts"
        / "ExampleRmsMeDevice.fmu"
    )
    return artifact


def _require_windows_fmpy() -> None:
    """Skip native runtime tests when their versioned platform is unavailable.

    :return: None.
    """

    pytest.importorskip("fmpy")
    if os.name == "nt":
        pass
    else:
        pytest.skip("The versioned runtime fixtures contain Windows binaries")


def _archive_digest(path: Path) -> str:
    """Return the exact SHA-256 digest of one small test artifact.

    :param path: Archive path to hash.
    :return: Lowercase hexadecimal SHA-256 digest.
    """

    digest: str = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _write_invalid_runtime_fmu(path: Path) -> Path:
    """Copy a valid FMI 2.0 artifact with an invalid current-host binary.

    :param path: Destination archive path.
    :return: Written invalid-runtime FMU path.
    """

    source: Path = _co_simulation_artifact()
    platform_name: str
    library_suffix: str
    platform_name, library_suffix = _resolve_legacy_host_binary()
    native_binary_entry: str = (
        f"binaries/{platform_name}/FrequencyLoadPilot{library_suffix}"
    )
    with zipfile.ZipFile(source, mode="r") as source_archive, zipfile.ZipFile(
        path,
        mode="w",
    ) as destination_archive:
        info: zipfile.ZipInfo
        for info in source_archive.infolist():
            # The canonical host binary is written exactly once after the
            # remaining certified entries have been copied unchanged.
            if info.filename == native_binary_entry:
                pass
            else:
                if info.is_dir():
                    archive_entry_data: bytes = b""
                else:
                    archive_entry_data = source_archive.read(info)
                destination_archive.writestr(info, archive_entry_data)

        # A malformed file at the current host path passes preflight and then
        # exercises FMPy's native load failure and VeraGrid's cleanup path.
        destination_archive.writestr(
            native_binary_entry,
            b"not-a-native-library",
        )
    return path


def _write_missing_symbol_runtime_fmu(path: Path) -> Path:
    """Copy a loadable FMI 2.0 FMU while removing one required export.

    The replacement preserves the PE layout and string length, so Windows can
    load the DLL and FMPy fails only when resolving the required FMI symbol.

    :param path: Destination archive path.
    :return: Written FMU whose native library lacks ``fmi2Instantiate``.
    """

    source: Path = _co_simulation_artifact()
    original_symbol: bytes = b"fmi2Instantiate"
    replacement_symbol: bytes = b"xmi2Instantiate"
    replaced_symbol_count: int = 0
    with zipfile.ZipFile(source, mode="r") as source_archive, zipfile.ZipFile(
        path,
        mode="w",
    ) as destination_archive:
        info: zipfile.ZipInfo
        for info in source_archive.infolist():
            if info.is_dir():
                payload: bytes = b""
            else:
                payload = source_archive.read(info)
                if info.filename.endswith(".dll"):
                    current_count: int = payload.count(original_symbol)
                    payload = payload.replace(original_symbol, replacement_symbol)
                    replaced_symbol_count += current_count
                else:
                    pass
            destination_archive.writestr(info, payload)
    if replaced_symbol_count > 0:
        pass
    else:
        raise AssertionError("The certified FMU does not export fmi2Instantiate")
    return path


def _write_fmi_three_fmu(path: Path) -> Path:
    """Write one valid minimal FMI 3.0 archive for the runtime gate.

    :param path: Destination archive path.
    :return: Written FMI 3.0 archive path.
    """

    xml_bytes: bytes = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<fmiModelDescription fmiVersion="3.0" modelName="future" '
        b'instantiationToken="future-token">\n'
        b'  <CoSimulation modelIdentifier="future_model"/>\n'
        b'  <ModelVariables>\n'
        b'    <Float64 name="time" valueReference="0" '
        b'causality="independent" variability="continuous"/>\n'
        b'  </ModelVariables>\n'
        b'  <ModelStructure/>\n'
        b'</fmiModelDescription>\n'
    )
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("modelDescription.xml", xml_bytes)
    return path


def _build_recording_host(
    source: Path,
    staging_parent: Path,
) -> tuple[FmuRuntimeHost, _RecordingRuntime, FmuStagingArea]:
    """Build a host around a recording runtime and real private staging.

    :param source: Inspected FMI 2.0 Co-Simulation archive.
    :param staging_parent: Caller-owned parent for the private child.
    :return: Host, recording runtime, and staging owner.
    """

    metadata: FmuModelDescription = read_fmu_model_description(source)
    if metadata.inspection_receipt is None:
        raise AssertionError("Test FMU metadata must include an inspection receipt")
    else:
        pass
    staging: FmuStagingArea = stage_fmu_source(
        source,
        metadata.inspection_receipt,
        staging_parent=staging_parent,
    )
    runtime: _RecordingRuntime = _RecordingRuntime(staging.get_root())
    config: FmuImportConfig = FmuImportConfig(fmu_path=source, extraction_root=staging_parent)
    host: FmuRuntimeHost = FmuRuntimeHost(
        config=config,
        metadata=metadata,
        mode=FmuInterfaceMode.CO_SIMULATION,
        extracted_dir=staging.get_fmu_directory(),
        owns_extracted_dir=True,
        model_description=object(),
        runtime=runtime,
        staging_area=staging,
    )
    return host, runtime, staging


def test_fmi_two_integer_initialization_prevalidates_before_native_access(
    tmp_path: Path,
) -> None:
    """Validate the complete Integer batch before setup and preserve write order.

    :param tmp_path: Isolated directory used as the direct host location.
    :return: None.
    """

    integer_input: FmuVariableDescription = FmuVariableDescription(
        name="integer_input",
        value_reference=10,
        variable_type=FmuVariableType.INTEGER,
        causality="input",
        variability="discrete",
        initial="exact",
        start="-2",
        derivative_index=None,
    )
    integer_output: FmuVariableDescription = FmuVariableDescription(
        name="integer_output",
        value_reference=11,
        variable_type=FmuVariableType.INTEGER,
        causality="output",
        variability="discrete",
        initial="calculated",
        start=None,
        derivative_index=None,
    )
    fixed_integer: FmuVariableDescription = FmuVariableDescription(
        name="fixed_integer",
        value_reference=12,
        variable_type=FmuVariableType.INTEGER,
        causality="parameter",
        variability="fixed",
        initial="exact",
        start="3",
        derivative_index=None,
    )
    real_input: FmuVariableDescription = FmuVariableDescription(
        name="real_input",
        value_reference=13,
        variable_type=FmuVariableType.REAL,
        causality="input",
        variability="continuous",
        initial="exact",
        start="0",
        derivative_index=None,
    )
    model_identifiers: dict[FmuInterfaceMode, str] = dict()
    model_identifiers[FmuInterfaceMode.CO_SIMULATION] = "integer_model"
    metadata: FmuModelDescription = FmuModelDescription(
        path=tmp_path / "integer-model.fmu",
        fmi_version="2.0",
        model_name="IntegerModel",
        guid="integer-guid",
        variable_naming_convention="flat",
        number_of_event_indicators=0,
        interface_modes=(FmuInterfaceMode.CO_SIMULATION,),
        model_identifiers=model_identifiers,
        platforms=tuple(),
        variables=(integer_input, integer_output, fixed_integer, real_input),
    )
    runtime: Mock = Mock()
    host: FmuRuntimeHost = FmuRuntimeHost(
        config=FmuImportConfig(fmu_path=metadata.path),
        metadata=metadata,
        mode=FmuInterfaceMode.CO_SIMULATION,
        extracted_dir=tmp_path,
        owns_extracted_dir=False,
        model_description=object(),
        runtime=runtime,
    )
    try:
        with pytest.raises(ValueError, match="names and values must align"):
            host.initialize(
                integer_start_variable_names=("integer_input",),
                integer_start_values=tuple(),
            )
        with pytest.raises(ValueError, match="Python int"):
            host.initialize(
                integer_start_variable_names=("integer_input",),
                integer_start_values=(True,),
            )
        with pytest.raises(ValueError, match="outside signed Int32"):
            host.initialize(
                integer_start_variable_names=("integer_input",),
                integer_start_values=(2147483648,),
            )
        with pytest.raises(ValueError, match="Duplicate"):
            host.initialize(
                integer_start_variable_names=("integer_input", "integer_input"),
                integer_start_values=(-2, 3),
            )
        with pytest.raises(RuntimeError, match="is not Integer"):
            host.initialize(
                integer_start_variable_names=("real_input",),
                integer_start_values=(1,),
            )
        with pytest.raises(RuntimeError, match="not writable"):
            host.initialize(
                integer_start_variable_names=("integer_output",),
                integer_start_values=(1,),
            )
        runtime.setupExperiment.assert_not_called()

        real_start_values: dict[str, float] = dict()
        real_start_values["real_input"] = 1.5
        host.initialize(
            start_values=real_start_values,
            integer_start_variable_names=("integer_input", "fixed_integer"),
            integer_start_values=(-2, 4),
        )
        real_call_index: int = runtime.method_calls.index(
            call.setReal([13], [1.5])
        )
        integer_call_index: int = runtime.method_calls.index(
            call.setInteger([10, 12], [-2, 4])
        )
        assert real_call_index < integer_call_index
    finally:
        host.close()


def test_fmi_two_integer_access_obeys_lifecycle_and_metadata(
    tmp_path: Path,
) -> None:
    """Permit live Integer access and reject invalid lifecycle or metadata.

    :param tmp_path: Isolated directory used as the direct host location.
    :return: None.
    """

    integer_input: FmuVariableDescription = FmuVariableDescription(
        name="integer_input",
        value_reference=10,
        variable_type=FmuVariableType.INTEGER,
        causality="input",
        variability="discrete",
        initial="exact",
        start="-2",
        derivative_index=None,
    )
    integer_output: FmuVariableDescription = FmuVariableDescription(
        name="integer_output",
        value_reference=11,
        variable_type=FmuVariableType.INTEGER,
        causality="output",
        variability="discrete",
        initial="calculated",
        start=None,
        derivative_index=None,
    )
    fixed_integer: FmuVariableDescription = FmuVariableDescription(
        name="fixed_integer",
        value_reference=12,
        variable_type=FmuVariableType.INTEGER,
        causality="parameter",
        variability="fixed",
        initial="exact",
        start="3",
        derivative_index=None,
    )
    model_identifiers: dict[FmuInterfaceMode, str] = dict()
    model_identifiers[FmuInterfaceMode.CO_SIMULATION] = "integer_model"
    metadata: FmuModelDescription = FmuModelDescription(
        path=tmp_path / "integer-access-model.fmu",
        fmi_version="2.0",
        model_name="IntegerAccessModel",
        guid="integer-access-guid",
        variable_naming_convention="flat",
        number_of_event_indicators=0,
        interface_modes=(FmuInterfaceMode.CO_SIMULATION,),
        model_identifiers=model_identifiers,
        platforms=tuple(),
        variables=(integer_input, integer_output, fixed_integer),
    )
    runtime: Mock = Mock()
    host: FmuRuntimeHost = FmuRuntimeHost(
        config=FmuImportConfig(fmu_path=metadata.path),
        metadata=metadata,
        mode=FmuInterfaceMode.CO_SIMULATION,
        extracted_dir=tmp_path,
        owns_extracted_dir=False,
        model_description=object(),
        runtime=runtime,
    )
    with pytest.raises(RuntimeError, match="live initialized runtime"):
        host.get_integer(("integer_input",))
    with pytest.raises(RuntimeError, match="live initialized runtime"):
        host.set_integer(("integer_input",), (-2,))

    host.initialize(
        integer_start_variable_names=("integer_input", "fixed_integer"),
        integer_start_values=(-2, 3),
    )
    runtime.getInteger.return_value = [3, -2, 0]
    assert host.get_integer(("fixed_integer", "integer_input", "integer_output")) == (
        3,
        -2,
        0,
    )
    host.set_integer(("integer_input",), (2147483647,))
    runtime.getInteger.return_value = [2147483647]
    assert host.get_integer(("integer_input",)) == (2147483647,)
    with pytest.raises(RuntimeError, match="not writable during runtime"):
        host.set_integer(("fixed_integer",), (4,))
    with pytest.raises(RuntimeError, match="not writable during runtime"):
        host.set_integer(("integer_output",), (4,))
    with pytest.raises(ValueError, match="Duplicate"):
        host.get_integer(("integer_input", "integer_input"))

    host.close()
    with pytest.raises(RuntimeError, match="live initialized runtime"):
        host.get_integer(("integer_input",))


def test_close_is_idempotent_before_and_after_initialization(tmp_path: Path) -> None:
    """Verify terminate, free, and cleanup follow the exact FMI lifecycle.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _co_simulation_artifact()
    uninitialized_host: FmuRuntimeHost
    uninitialized_runtime: _RecordingRuntime
    uninitialized_staging: FmuStagingArea
    uninitialized_host, uninitialized_runtime, uninitialized_staging = _build_recording_host(
        source,
        tmp_path / "uninitialized",
    )
    initialized_host: FmuRuntimeHost
    initialized_runtime: _RecordingRuntime
    initialized_staging: FmuStagingArea
    initialized_host, initialized_runtime, initialized_staging = _build_recording_host(
        source,
        tmp_path / "initialized",
    )

    uninitialized_host.close()
    uninitialized_host.close()
    initialized_host.initialize()
    initialized_host.close()
    initialized_host.close()

    assert uninitialized_runtime.terminate_count == 0
    assert uninitialized_runtime.free_count == 1
    assert uninitialized_runtime.root_existed_during_free
    assert uninitialized_staging.is_closed()
    assert initialized_runtime.setup_count == 1
    assert initialized_runtime.enter_initialization_count == 1
    assert initialized_runtime.exit_initialization_count == 1
    assert initialized_runtime.terminate_count == 1
    assert initialized_runtime.free_count == 1
    assert initialized_runtime.root_existed_during_free
    assert initialized_staging.is_closed()


def test_real_co_simulation_runs_only_from_private_staging(tmp_path: Path) -> None:
    """Verify a certified CS FMU initializes and advances from private bytes.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    _require_windows_fmpy()
    source: Path = _co_simulation_artifact()
    source_digest: str = _archive_digest(source)
    staging_parent: Path = tmp_path / "runtime"
    staging_parent.mkdir()
    sentinel: Path = staging_parent / "keep.txt"
    sentinel.write_text("caller-owned", encoding="utf-8")
    config: FmuImportConfig = FmuImportConfig(fmu_path=source, extraction_root=staging_parent)
    host: FmuRuntimeHost = open_fmu_runtime_host(config)
    if host.staging_area is None:
        raise AssertionError("Runtime factory must transfer its staging owner to the host")
    else:
        staging_root: Path = host.staging_area.get_root()
    try:
        assert host.metadata.path == source.resolve()
        assert host.extracted_dir == host.staging_area.get_fmu_directory()
        assert host.extracted_dir != source.resolve()
        assert staging_root.parent == staging_parent.resolve()
        host.initialize()
        host.do_step(current_time=0.0, step_size=0.001)
    finally:
        host.close()
        host.close()

    assert not staging_root.exists()
    assert sentinel.read_text(encoding="utf-8") == "caller-owned"
    assert _archive_digest(source) == source_digest


def test_real_model_exchange_runs_only_from_private_staging(tmp_path: Path) -> None:
    """Verify a versioned ME FMU exposes states and derivatives from staging.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    _require_windows_fmpy()
    source: Path = _model_exchange_artifact()
    source_digest: str = _archive_digest(source)
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=source,
        extraction_root=tmp_path / "runtime",
    )
    host: FmuRuntimeHost = open_fmu_runtime_host(config)
    if host.staging_area is None:
        raise AssertionError("Runtime factory must transfer its staging owner to the host")
    else:
        staging_root: Path = host.staging_area.get_root()
    try:
        host.initialize()
        assert host.get_continuous_state_count() == 1
        assert host.get_continuous_states() == [0.0]
        assert host.get_derivatives() == [1.0]
    finally:
        host.close()

    assert not staging_root.exists()
    assert _archive_digest(source) == source_digest


def test_directory_source_is_snapshotted_before_runtime_use(tmp_path: Path) -> None:
    """Verify an extracted directory remains independent from the live runtime.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    _require_windows_fmpy()
    archive_source: Path = _co_simulation_artifact()
    archive_metadata: FmuModelDescription = read_fmu_model_description(archive_source)
    if archive_metadata.inspection_receipt is None:
        raise AssertionError("Test FMU metadata must include an inspection receipt")
    else:
        pass
    source_staging: FmuStagingArea = stage_fmu_source(
        archive_source,
        archive_metadata.inspection_receipt,
        staging_parent=tmp_path / "source-parent",
    )
    source_directory: Path = source_staging.get_fmu_directory()
    marker: Path = source_directory / "resources" / "snapshot-marker.txt"
    marker.parent.mkdir(exist_ok=True)
    marker.write_text("before", encoding="utf-8")
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=source_directory,
        extraction_root=tmp_path / "runtime-parent",
    )
    host: FmuRuntimeHost = open_fmu_runtime_host(config)
    if host.staging_area is None:
        raise AssertionError("Runtime factory must transfer its staging owner to the host")
    else:
        runtime_marker: Path = host.extracted_dir / "resources" / "snapshot-marker.txt"
        runtime_root: Path = host.staging_area.get_root()
    try:
        marker.write_text("after!", encoding="utf-8")
        assert runtime_marker.read_text(encoding="utf-8") == "before"
        host.initialize()
        host.do_step(current_time=0.0, step_size=0.001)
    finally:
        host.close()
        source_staging.close()

    assert not runtime_root.exists()


def test_native_load_failure_cleans_private_child_and_preserves_parent(tmp_path: Path) -> None:
    """Verify a non-loadable FMI 2.0 binary leaves no staging residue.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    source: Path = _write_invalid_runtime_fmu(tmp_path / "invalid.fmu")
    source_digest: str = _archive_digest(source)
    staging_parent: Path = tmp_path / "runtime"
    staging_parent.mkdir()
    sentinel: Path = staging_parent / "keep.txt"
    sentinel.write_text("caller-owned", encoding="utf-8")
    config: FmuImportConfig = FmuImportConfig(fmu_path=source, extraction_root=staging_parent)
    working_directory: Path = Path.cwd()

    with pytest.raises(Exception, match="Failed to load shared library"):
        open_fmu_runtime_host(config)
    assert Path.cwd() == working_directory
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()
    assert sentinel.read_text(encoding="utf-8") == "caller-owned"
    assert _archive_digest(source) == source_digest


def test_native_symbol_failure_unloads_library_and_cleans_staging(tmp_path: Path) -> None:
    """Verify a post-LoadLibrary symbol failure releases all private state.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    _require_windows_fmpy()
    source: Path = _write_missing_symbol_runtime_fmu(tmp_path / "missing-symbol.fmu")
    source_digest: str = _archive_digest(source)
    staging_parent: Path = tmp_path / "runtime"
    staging_parent.mkdir()
    sentinel: Path = staging_parent / "keep.txt"
    sentinel.write_text("caller-owned", encoding="utf-8")
    config: FmuImportConfig = FmuImportConfig(fmu_path=source, extraction_root=staging_parent)
    working_directory: Path = Path.cwd()

    with pytest.raises(AttributeError, match="fmi2Instantiate"):
        open_fmu_runtime_host(config)
    assert Path.cwd() == working_directory
    assert tuple(staging_parent.glob("veragrid_fmu_stage_*")) == tuple()
    assert sentinel.read_text(encoding="utf-8") == "caller-owned"
    assert _archive_digest(source) == source_digest


def test_unconnected_version_and_mode_fail_before_staging(tmp_path: Path) -> None:
    """Verify incompatible in-process host requests fail before side effects.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmi_three_source: Path = _write_fmi_three_fmu(tmp_path / "future.fmu")
    version_parent: Path = tmp_path / "version-runtime"
    with pytest.raises(RuntimeError, match="supports FMI 1/2 execution only"):
        open_fmu_runtime_host(
            FmuImportConfig(fmu_path=fmi_three_source, extraction_root=version_parent)
        )
    assert not version_parent.exists()

    # Pin the callable boundary without replacing product dependencies: the
    # FMI-version guard must precede dependency, native, and staging calls.
    host_factory_source: str = inspect.getsource(open_fmu_runtime_host)
    guard_position: int = host_factory_source.index(
        "FmuRuntimeHost supports FMI 1/2 execution only"
    )
    dependency_position: int = host_factory_source.index("fmpy_module: Any = fmpy")
    native_validation_position: int = host_factory_source.index(
        "validate_native_binary("
    )
    staging_position: int = host_factory_source.index("stage_fmu_source(")
    assert guard_position < dependency_position
    assert guard_position < native_validation_position
    assert guard_position < staging_position

    mode_parent: Path = tmp_path / "mode-runtime"
    with pytest.raises(RuntimeError, match="does not declare preferred interface ModelExchange"):
        open_fmu_runtime_host(
            FmuImportConfig(
                fmu_path=_co_simulation_artifact(),
                preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
                extraction_root=mode_parent,
            )
        )
    assert not mode_parent.exists()


def test_fmi_one_cs_scheduler_capability_gate_fails_before_staging(
    tmp_path: Path,
) -> None:
    """Reject FMI 1 CS profiles incompatible with the existing scheduler.

    :param tmp_path: Isolated source and staging parents provided by pytest.
    :return: None.
    """

    cases: tuple[tuple[str, str, str], ...] = (
        (
            "fixed-step",
            "<CoSimulation_StandAlone><Capabilities/>"
            "</CoSimulation_StandAlone>",
            "variable communication step support",
        ),
        (
            "asynchronous",
            "<CoSimulation_StandAlone><Capabilities "
            'canHandleVariableCommunicationStepSize="true" '
            'canRunAsynchronuously="true"/></CoSimulation_StandAlone>',
            "asynchronous",
        ),
        (
            "tool",
            "<CoSimulation_Tool><Capabilities "
            'canHandleVariableCommunicationStepSize="true"/>'
            '<Model entryPoint="tool" type="application"/>'
            "</CoSimulation_Tool>",
            "original external tool",
        ),
    )
    case_name: str
    interface_xml: str
    expected_message: str
    for case_name, interface_xml, expected_message in cases:
        source: Path = tmp_path / f"{case_name}.fmu"
        xml_text: str = (
            '<fmiModelDescription fmiVersion="1.0" modelName="Legacy" '
            'modelIdentifier="legacy" guid="legacy-guid" '
            'numberOfContinuousStates="0" numberOfEventIndicators="0">'
            f"<Implementation>{interface_xml}</Implementation>"
            "<ModelVariables/></fmiModelDescription>"
        )
        archive: zipfile.ZipFile
        with zipfile.ZipFile(source, mode="w") as archive:
            archive.writestr("modelDescription.xml", xml_text.encode("utf-8"))
        staging_parent: Path = tmp_path / f"{case_name}-staging"
        with pytest.raises(RuntimeError, match=expected_message):
            open_fmu_runtime_host(
                FmuImportConfig(fmu_path=source, extraction_root=staging_parent)
            )
        assert not staging_parent.exists()


@pytest.mark.parametrize("terminal_status", (2, 5))
def test_fmi_one_cs_rejects_discard_and_pending_statuses(
    tmp_path: Path,
    terminal_status: int,
) -> None:
    """Close FMI 1 CS deterministically on discard or pending status.

    :param tmp_path: Isolated direct-host directory supplied by pytest.
    :param terminal_status: FMI discard or pending status returned by the double.
    :return: None.
    """

    identifiers: dict[FmuInterfaceMode, str] = dict()
    identifiers[FmuInterfaceMode.CO_SIMULATION] = "legacy"
    capabilities: FmiOneCoSimulationCapabilities = FmiOneCoSimulationCapabilities(
        needs_execution_tool=False,
        can_handle_variable_communication_step_size=True,
        can_handle_events=False,
        can_reject_steps=True,
        can_interpolate_inputs=False,
        max_output_derivative_order=0,
        can_run_asynchronuously=False,
        can_signal_events=False,
        can_be_instantiated_only_once_per_process=False,
        can_not_use_memory_management_functions=False,
    )
    metadata: FmuModelDescription = FmuModelDescription(
        path=tmp_path / "status.fmu",
        fmi_version="1.0",
        model_name="Legacy",
        guid="legacy-guid",
        variable_naming_convention="flat",
        number_of_continuous_states=0,
        number_of_event_indicators=0,
        interface_modes=(FmuInterfaceMode.CO_SIMULATION,),
        model_identifiers=identifiers,
        platforms=tuple(),
        variables=tuple(),
        fmi_one_co_simulation_capabilities=capabilities,
    )
    runtime: Mock = Mock()
    runtime.doStep.return_value = terminal_status
    host: FmuRuntimeHost = FmuRuntimeHost(
        config=FmuImportConfig(fmu_path=metadata.path),
        metadata=metadata,
        mode=FmuInterfaceMode.CO_SIMULATION,
        extracted_dir=tmp_path,
        owns_extracted_dir=False,
        model_description=object(),
        runtime=runtime,
    )
    host.initialized = True

    with pytest.raises(RuntimeError, match=f"terminal status {terminal_status}"):
        host.do_step(current_time=0.0, step_size=0.001)
    assert host.closed
    runtime.terminate.assert_called_once_with()
    runtime.freeInstance.assert_called_once_with()
