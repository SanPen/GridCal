from __future__ import annotations

from pathlib import Path
from concurrent.futures import CancelledError
from enum import Enum
from multiprocessing import active_children
from multiprocessing.process import BaseProcess
import os
import shutil
from tempfile import gettempdir
from time import monotonic, sleep
from threading import Event, Thread
import zipfile

import numpy as np
import pytest
from fmpy import extract, simulate_fmu

from VeraGridEngine.enumerations import FmiVersion, InterfaceType
from VeraGridEngine.IO.fmu.interface import (
    FmuValidationControl, FmuValidationPhase, export_model_as_fmu,
    _validate_exported_fmu, _release_export_validation, package_validated_fmu,
)
from VeraGridEngine.IO.fmu.compiler import compile_fmu_shared_library
from VeraGridEngine.IO.fmu.CosimulationInterface.build import host_build_capable
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.IO.fmu.config import ExportConfig
from VeraGridEngine.IO.fmu.CosimulationInterface.export_ir import build_export_model
from VeraGridEngine.IO.fmu.model import flatten_block
from VeraGridEngine.IO.fmu.archive import package_fmu, prepare_fmu_staging_dir
from VeraGridEngine.IO.fmu.logic import build_co_simulation_logic_entries
from VeraGridEngine.IO.fmu.model import build_model_snapshot, reconstruct_block
from VeraGridEngine.IO.fmu.CosimulationInterface.xml_writer import emit_model_description
from VeraGridEngine.IO.fmu.config import ExportConfig as MeExportConfig
from VeraGridEngine.Utils.Compiler.interface import Compiler, CompilerInterface
from tests.FMI.fmi_test_support import build_test_fmi_compiler
from examples.fmi.powerfactory_first_order.run_powerfactory_first_order import (
    PowerFactoryCompatibilityProfile, build_powerfactory_compatibility_fmu,
)


class _ExportValidationFault(Enum):
    """Choose actual native loader failures for isolated export regressions."""

    CRASH = 1
    HANG = 2
    ZERO_EXIT = 3
    LOAD_FAILURE = 4


class _ValidationLoadBehavior(Enum):
    """Select meaningful native startup/unload timing regression fixtures."""

    SLOW_START = 1
    HANG_UNLOAD = 2


class _ExportCancellationRequester(Thread):
    """Request cancellation only after an observable test-owned entry marker."""

    __slots__: tuple[str, ...] = ("_marker", "_control", "_expected_phase", "observed_native", "started", "finished", "accepted")

    def __init__(self: _ExportCancellationRequester, marker: Path, control: FmuValidationControl, expected_phase: FmuValidationPhase | None = None) -> None:
        """Retain the exact marker and operation targeted by this test thread.

        :param marker: Native-entry marker, or a controlled publication barrier.
        :param control: Only operation that this thread may cancel.
        :param expected_phase: Native phase to observe; None for lock-order tests.
        :return: None.
        """
        super().__init__(daemon=True)
        self._marker: Path = marker
        self._control: FmuValidationControl = control
        self._expected_phase: FmuValidationPhase | None = expected_phase
        self.observed_native: bool = False
        self.started: Event = Event()
        self.finished: Event = Event()
        self.accepted: bool | None = None

    def run(self: _ExportCancellationRequester) -> None:
        """Observe actual entry before cancelling, with a bounded fixture wait.

        :return: None. Expired observation still cancels cleanup, but the test
            requires observed_native and cannot mistake bootstrap for coverage.
        """
        deadline: float = monotonic() + 120.0
        ready: bool = False
        terminal: bool = False
        while not ready and not terminal and monotonic() < deadline:
            ready = self._marker.is_file()
            if self._expected_phase is not None:
                phase: FmuValidationPhase = self._control.get_phase()
                ready = ready and phase == self._expected_phase
                terminal = phase in (FmuValidationPhase.FAILED, FmuValidationPhase.CANCELLED, FmuValidationPhase.COMPLETED)
            else:
                pass
            if ready or terminal:
                pass
            else:
                sleep(0.01)
        self.observed_native = ready
        self.started.set()
        self.accepted = self._control.cancel()
        self.finished.set()


class _ValidationProcessProbe(BaseProcess):
    """Exercise cleanup decisions without creating or targeting any OS process."""

    __slots__: tuple[str, ...] = ("_has_pid", "_stops_after_kill", "_running", "terminated", "killed", "joined", "join_limits", "closed")

    def __init__(self: _ValidationProcessProbe, has_pid: bool, stops_after_kill: bool) -> None:
        """Declare whether this fixture proves an owned process can stop.

        :param has_pid: Whether process startup supplied a usable identity.
        :param stops_after_kill: Whether kill establishes child death.
        :return: None; no OS process is started.
        """
        super().__init__()
        self._has_pid: bool = has_pid
        self._stops_after_kill: bool = stops_after_kill
        self._running: bool = True
        self.terminated: bool = False
        self.killed: bool = False
        self.joined: int = 0
        self.join_limits: list[float | None] = list((None, None))
        self.closed: bool = False

    @property
    def pid(self: _ValidationProcessProbe) -> int | None:
        """Expose fixture identity without resolving any real process.

        :return: Fixed inert identity or None for an interrupted start.
        """
        return 123 if self._has_pid else None

    @property
    def exitcode(self: _ValidationProcessProbe) -> int | None:
        """Expose confirmed fixture exit independently of a stop request.

        :return: Zero only after kill established death; otherwise None.
        """
        return None if self._running else 0

    def is_alive(self: _ValidationProcessProbe) -> bool:
        """Report the declared fixture lifetime.

        :return: True until the configured kill outcome establishes death.
        """
        return self._running

    def terminate(self: _ValidationProcessProbe) -> None:
        """Record a deliberately ineffective graceful termination.

        :return: None; this fixture requires escalation to kill.
        """
        self.terminated = True

    def kill(self: _ValidationProcessProbe) -> None:
        """Apply the explicitly selected fixture shutdown outcome.

        :return: None; a requested kill alone never proves success.
        """
        self.killed = True
        self._running = not self._stops_after_kill

    def join(self: _ValidationProcessProbe, timeout: float | None = None) -> None:
        """Record bounded waits without sleeping or touching the OS.

        :param timeout: Shutdown wait selected by the lifecycle owner.
        :return: None.
        """
        assert self.joined < 2
        self.join_limits[self.joined] = timeout
        self.joined += 1

    def close(self: _ValidationProcessProbe) -> None:
        """Confirm that handle release occurs only after safe ownership proof.

        :return: None; closing a live identified fixture is a test failure.
        """
        assert not self._running or not self._has_pid
        self.closed = True


class _ExportLibraryCompilerHandler(CompilerInterface):
    """Replay prepared library bytes through the real public export path."""

    __slots__: tuple[str, ...] = ("_library_path",)

    def __init__(self: _ExportLibraryCompilerHandler, library_path: Path) -> None:
        """Retain one caller-owned fault fixture without discovering tools.

        :param library_path: Already prepared native or corrupt library file.
        :return: None.
        """
        self._library_path: Path = library_path
        super().__init__("export-fixture")

    def _is_setup_valid(self: _ExportLibraryCompilerHandler) -> bool:
        """Report whether the explicitly supplied library fixture exists.

        :return: True exactly when the replay source is an existing file.
        """
        return self._library_path.is_file()

    def compile(self: _ExportLibraryCompilerHandler, source_files: list[str], output_dir: str, lib_name: str = "", include_directories: list[str] | None = None) -> str:
        """Deliver controlled output bytes through the compiler facade.

        :param source_files: Exporter inputs, intentionally unchanged.
        :param output_dir: Facade-owned destination directory.
        :param lib_name: Library name requested by the exporter.
        :param include_directories: Exporter headers, intentionally unchanged.
        :return: Prepared fixture copied to the requested native output.
        """
        output: Path = Path(output_dir) / lib_name
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._library_path, output)
        return str(output)


def build_simple_block() -> Block:
    x = Var("x")
    dx = Var("dx", base_var=x)
    y = Var("y")
    u = Var("u")
    p = Var("p")
    mode = Var("mode")

    child = Block(
        state_vars=[x],
        state_eqs=[-x + u + p],
        algebraic_vars=[y],
        algebraic_eqs=[y - x],
        diff_vars=[dx],
        parameters={p: Const(2.0)},
        init_values={x: Const(1.0), y: Const(1.0)},
        init_eqs={y: x},
        event_dict={mode: Const(1.0)},
        in_vars=[u],
        out_vars=[y],
    )
    return Block(children=[child], name="SimpleModel")


@pytest.mark.parametrize("interface", (InterfaceType.CO_SIMULATION, InterfaceType.MODEL_EXCHANGE))
@pytest.mark.parametrize("fmi_version", tuple(FmiVersion))
def test_successful_export_removes_owned_build_root(tmp_path: Path, interface: InterfaceType, fmi_version: FmiVersion) -> None:
    """Compile and package a real FMU, then remove its automatic build directory.

    :param tmp_path: Owned output directory supplied by pytest.
    :param interface: Cover both existing CS and ME exporter cleanup owners.
    :param fmi_version: FMI family whose native entry points must load.
    :return: None; native build, archive or retained automatic-build failures fail.
    """
    compiler: Compiler | None = build_test_fmi_compiler()
    if compiler is None:
        pytest.skip("No saved usable Clang session is available")
    else:
        pass
    output_path: Path = tmp_path / "cleanup.fmu"
    cfg: ExportConfig = ExportConfig(interface_type=interface, model_name="CleanupModel",
                                     output_path=output_path, compile_binary=True, keep_build_dir=False,
                                     fmi_version=fmi_version)
    exported_path: Path = export_model_as_fmu(model=build_simple_block(), cfg=cfg, compiler=compiler)
    assert exported_path == output_path and output_path.is_file()
    # Both exporters create automatic roots beside the output; only the package
    # and caller-owned data may survive a successful build with cleanup enabled.
    assert tuple(tmp_path.glob("veragrid_fmu*_build_*")) == tuple()
    archive: zipfile.ZipFile
    name: str
    with zipfile.ZipFile(output_path) as archive:
        assert "modelDescription.xml" in archive.namelist()
        assert any(name.startswith("binaries/") for name in archive.namelist())


@pytest.mark.parametrize("interface", (InterfaceType.CO_SIMULATION, InterfaceType.MODEL_EXCHANGE))
@pytest.mark.parametrize("fmi_version", tuple(FmiVersion))
def test_export_validation_rejects_missing_runtime_functions(
    tmp_path: Path, interface: InterfaceType, fmi_version: FmiVersion,
) -> None:
    """Reject a packaged native library missing its declared FMI functions.

    :param tmp_path: Isolated native build and archive directory.
    :param interface: CS or ME loader to exercise on the current host.
    :param fmi_version: FMI family whose required functions must be resolved.
    :return: None; acceptance or leaked native references fail the test.
    """
    compiler: Compiler | None = build_test_fmi_compiler()
    if compiler is None or compiler.get_handler() is None:
        pytest.skip("No usable native compiler is available")
    else:
        pass
    config: ExportConfig = ExportConfig(
        interface_type=interface, fmi_version=fmi_version, model_name="MissingFunctions",
        output_path=tmp_path / "valid.fmu", compile_binary=True,
    )
    valid_fmu: Path = export_model_as_fmu(build_simple_block(), config, compiler)
    staged: Path = tmp_path / "staged"
    extract(str(valid_fmu), unzipdir=str(staged))
    binaries: tuple[Path, ...] = tuple((staged / "binaries").glob("*/*"))
    assert len(binaries) == 1
    library: Path = binaries[0]
    source: Path = tmp_path / "missing.c"
    source.write_text("int unrelated_function(void) { return 0; }\n", encoding="utf-8")
    # Compilation intentionally accepts this library. Validation must fail by
    # loading the packaged interface, without consulting a symbol-list tool.
    compile_fmu_shared_library(
        (source,), (tmp_path,), library,
        compiler=compiler,
    )
    invalid_fmu: Path = package_fmu(staged, tmp_path / "invalid.fmu")
    working_directory: Path = Path.cwd()
    with pytest.raises(RuntimeError, match="fmi"):
        _validate_exported_fmu(invalid_fmu, config)
    assert Path.cwd() == working_directory
    # A failed constructor must unload its partial library owner as well. The
    # validation temporary directory cannot be removed on Windows otherwise.
    _validate_exported_fmu(valid_fmu, config)
    invalid_fmu.unlink()
    valid_fmu.unlink()


@pytest.mark.parametrize("interface", (InterfaceType.CO_SIMULATION, InterfaceType.MODEL_EXCHANGE))
@pytest.mark.parametrize("fmi_version", tuple(FmiVersion))
@pytest.mark.parametrize("fault", tuple(_ExportValidationFault))
def test_export_validation_contains_native_load_faults(
    tmp_path: Path, interface: InterfaceType, fmi_version: FmiVersion, fault: _ExportValidationFault,
) -> None:
    """Contain real load-time termination/hang and preserve parent ownership.

    :param tmp_path: Owned fixture, native evidence and final-output directory.
    :param interface: Public exporter interface under test.
    :param fmi_version: Declared FMI version packaged around the fault library.
    :param fault: Native initializer behavior, including a misleading zero exit.
    :return: None; missing entry evidence, publication or leaked ownership fails.
    """
    selected: Compiler | None = build_test_fmi_compiler()
    if selected is None:
        pytest.skip("No saved usable Clang session is available")
    else:
        pass
    config: ExportConfig = ExportConfig(model_name="NativeFault", output_path=tmp_path / "final.fmu", interface_type=interface, fmi_version=fmi_version)
    library: Path = tmp_path / config.library_name
    marker: Path = tmp_path / "native-entered"
    if fault == _ExportValidationFault.LOAD_FAILURE:
        library.write_bytes(b"NOT_A_NATIVE_LIBRARY")
    else:
        action: str
        if fault == _ExportValidationFault.CRASH:
            action = "abort();"
        elif fault == _ExportValidationFault.ZERO_EXIT:
            action = "exit(0);"
        else:
            action = "for (;;) { }"
        source: Path = tmp_path / "native_fault.c"
        marker_literal: str = marker.as_posix().replace('"', '\\"')
        initialization: str = f'FILE* marker = fopen("{marker_literal}", "wb"); if (marker != NULL) {{ fputs("entered", marker); fclose(marker); }} {action}'
        if os.name == "nt":
            native_code: str = "#include <stdio.h>\n#include <stdlib.h>\nint __stdcall DllMain(void* module, unsigned long reason, void* reserved) { if (reason == 1) { " + initialization + " } else { } return 1; }\n"
        else:
            native_code = "#include <stdio.h>\n#include <stdlib.h>\n__attribute__((constructor)) static void native_fault(void) { " + initialization + " }\n"
        source.write_text(native_code, encoding="utf-8")
        compile_fmu_shared_library((source,), (tmp_path,), library, selected)
    # Replay the prepared bytes through both real exporter branches, without
    # replacing their functions or weakening the normal compiler abstraction.
    previous_output: bytes = b"previous-valid-output"
    config.output_path.write_bytes(previous_output)
    cwd_before: Path = Path.cwd()
    temporary_before: set[Path] = set(Path(gettempdir()).glob("veragrid_fmu_validation_*"))
    child: BaseProcess
    children_before: set[int | None] = set(child.pid for child in active_children())
    started_at: float = monotonic()
    control: FmuValidationControl = FmuValidationControl()
    requester: _ExportCancellationRequester | None = None
    if fault == _ExportValidationFault.HANG:
        requester = _ExportCancellationRequester(marker, control, FmuValidationPhase.LOADING)
        requester.start()
    else:
        pass
    try:
        with pytest.raises((RuntimeError, CancelledError)):
            export_model_as_fmu(build_simple_block(), config, Compiler(compiler_handler=_ExportLibraryCompilerHandler(library)), control)
    finally:
        if requester is not None:
            requester.join(timeout=3.0)
        else:
            pass
    if requester is not None:
        assert not requester.is_alive() and requester.observed_native and requester.accepted
        assert control.get_phase() == FmuValidationPhase.CANCELLED
    else:
        assert control.get_phase() == FmuValidationPhase.FAILED
    # This is a fixture observation bound, never a product acceptance deadline.
    assert monotonic() - started_at < 140.0
    assert config.output_path.read_bytes() == previous_output
    assert Path.cwd() == cwd_before
    assert set(Path(gettempdir()).glob("veragrid_fmu_validation_*")) == temporary_before
    assert set(child.pid for child in active_children()) == children_before
    assert tuple(tmp_path.glob(".veragrid_fmu_candidate_*")) == tuple()
    assert tuple(tmp_path.glob("veragrid_fmu*_build_*")) == tuple()
    if fault == _ExportValidationFault.LOAD_FAILURE:
        assert not marker.exists()
    else:
        # This proves the native initializer actually ran, so an import/startup
        # timeout cannot masquerade as coverage of a non-returning native load.
        assert marker.read_text(encoding="utf-8") == "entered"


@pytest.mark.parametrize("interface", (InterfaceType.CO_SIMULATION, InterfaceType.MODEL_EXCHANGE))
@pytest.mark.parametrize("fmi_version", tuple(FmiVersion))
@pytest.mark.parametrize("hidden", (False, True))
def test_export_validation_rejects_single_missing_or_hidden_function(
    tmp_path: Path, interface: InterfaceType, fmi_version: FmiVersion, hidden: bool,
) -> None:
    """Reject one missing/hidden API function in an otherwise complete FMU.

    :param tmp_path: Owned generated-source and archive directory.
    :param interface: CS or ME API surface selected for the fixture.
    :param fmi_version: FMI family whose GetVersion entry point is altered.
    :param hidden: Make the function private instead of omitting its name.
    :return: None; accepting the incomplete packaged native API fails.
    """
    compiler: Compiler | None = build_test_fmi_compiler()
    if compiler is None:
        pytest.skip("No saved usable Clang session is available")
    else:
        pass
    config: ExportConfig = ExportConfig(model_name="SingleMissing", output_path=tmp_path / "valid.fmu", interface_type=interface, fmi_version=fmi_version, build_dir=tmp_path / "build", keep_build_dir=True)
    valid: Path = export_model_as_fmu(build_simple_block(), config, compiler)
    staged: Path = tmp_path / "staged"
    extract(str(valid), unzipdir=str(staged))
    libraries: tuple[Path, ...] = tuple((staged / "binaries").glob("*/*"))
    assert len(libraries) == 1
    source_root: Path = tmp_path / "build" / "source"
    symbol: str
    runtime_name: str
    if fmi_version == FmiVersion.FMI_1_0:
        symbol = "fmiGetVersion"
        runtime_name = "runtime_fmi1.c"
    elif fmi_version == FmiVersion.FMI_2_0:
        symbol = "fmi2GetVersion"
        runtime_name = "runtime_fmi2.c"
    else:
        symbol = "fmi3GetVersion"
        runtime_name = "runtime_fmi3.c"
    # Remove only the exported declaration in this copied official header. The
    # private definition then compiles without contradicting an extern export.
    removed_declarations: int = 0
    header: Path
    line: str
    for header in (source_root / "include").glob("*.h"):
        original: tuple[str, ...] = tuple(header.read_text(encoding="utf-8").splitlines(keepends=True))
        retained: tuple[str, ...] = tuple(line for line in original if not (symbol in line and line.rstrip().endswith(";") and ("Export" in line or "_Export" in line)))
        removed_declarations += len(original) - len(retained)
        header.write_text("".join(retained), encoding="utf-8")
    assert removed_declarations == 1
    runtime_source: Path = source_root / "src" / runtime_name
    runtime_text: str = runtime_source.read_text(encoding="utf-8")
    declaration: str = "const char* " + symbol + "(void)"
    assert runtime_text.count(declaration) == 1
    replacement: str = "static " + declaration if hidden else "const char* vg_omitted_version(void)"
    runtime_source.write_text(runtime_text.replace(declaration, replacement, 1), encoding="utf-8")
    sources: tuple[Path, ...] = tuple((source_root / "src").glob("*.c"))
    compile_fmu_shared_library(sources, (source_root / "include", source_root / "src"), libraries[0], compiler)
    invalid: Path = package_fmu(staged, tmp_path / "incomplete.fmu")
    with pytest.raises(RuntimeError, match="fmi.*GetVersion"):
        _validate_exported_fmu(invalid, config)
    # A rejection must release the native child and permit the next valid load.
    _validate_exported_fmu(valid, config)


@pytest.mark.parametrize("interface", (InterfaceType.CO_SIMULATION, InterfaceType.MODEL_EXCHANGE))
@pytest.mark.parametrize("fmi_version", tuple(FmiVersion))
@pytest.mark.parametrize("previous_exists", (False, True))
def test_rejected_export_preserves_previous_output(
    tmp_path: Path, interface: InterfaceType, fmi_version: FmiVersion, previous_exists: bool,
) -> None:
    """Preserve existing/absent final output across real public export failure.

    :param tmp_path: Owned output and corrupt-provider fixture directory.
    :param interface: Public exporter branch to exercise.
    :param fmi_version: Packaged FMI family under test.
    :param previous_exists: Whether a prior output must survive byte-identically.
    :return: None; rejected publication or retained candidate/build roots fails.
    """
    output: Path = tmp_path / "final.fmu"
    previous: bytes = b"preserve-this-final-output"
    if previous_exists:
        output.write_bytes(previous)
    else:
        pass
    corrupt_library: Path = tmp_path / "corrupt-library"
    corrupt_library.write_bytes(b"invalid provider output")
    config: ExportConfig = ExportConfig(model_name="Preservation", output_path=output, fmi_version=fmi_version, interface_type=interface)
    with pytest.raises(RuntimeError):
        export_model_as_fmu(build_simple_block(), config, Compiler(compiler_handler=_ExportLibraryCompilerHandler(corrupt_library)))
    if previous_exists:
        assert output.read_bytes() == previous
    else:
        assert not output.exists()
    assert tuple(tmp_path.glob(".veragrid_fmu_candidate_*")) == tuple()
    assert tuple(tmp_path.glob("veragrid_fmu*_build_*")) == tuple()
    compiler: Compiler | None = build_test_fmi_compiler()
    if compiler is None:
        pytest.skip("No saved usable Clang session is available")
    else:
        pass
    assert export_model_as_fmu(build_simple_block(), config, compiler) == output
    assert output.read_bytes() != previous


@pytest.mark.parametrize("interface", (InterfaceType.CO_SIMULATION, InterfaceType.MODEL_EXCHANGE))
def test_powerfactory_derivative_uses_validated_publication(tmp_path: Path, interface: InterfaceType) -> None:
    """Require native validation and exact members for a recompiled derivative.

    :param tmp_path: Owned standard/derivative source and output directories.
    :param interface: FMI 3 CS or ME compatibility adapter to build.
    :return: None; invalid derivative publication, PASS receipt or extra files fails.
    """
    compiler: Compiler | None = build_test_fmi_compiler()
    if compiler is None:
        pytest.skip("No saved usable Clang session is available")
    else:
        pass
    config: ExportConfig = ExportConfig(model_name="Derivative", output_path=tmp_path / "standard.fmu", fmi_version=FmiVersion.FMI_3_0, interface_type=interface, build_dir=tmp_path / "standard-build", keep_build_dir=True)
    standard: Path = export_model_as_fmu(build_simple_block(), config, compiler)
    cell: tuple[str, Path, str, str] = ("derivative", standard, "3.0", "cs" if interface == InterfaceType.CO_SIMULATION else "me")
    source_root: Path = tmp_path / "standard-build" / "source"
    solver_source: Path = source_root / "src" / "solver.c"
    retained_solver: Path = tmp_path / "retained_solver.c"
    solver_source.rename(retained_solver)
    try:
        # Exercise the public builder with incomplete source, not just its
        # private provenance routine. No final output may be created/replaced.
        previous_exists: bool
        for previous_exists in (False, True):
            preflight_root: Path = tmp_path / ("source-existing" if previous_exists else "source-absent")
            preflight_output: Path = preflight_root / "compatibility_fmus" / "standard_PowerFactory.fmu"
            if previous_exists:
                preflight_output.parent.mkdir(parents=True)
                preflight_output.write_bytes(b"prior-source-checked-derivative")
            else:
                pass
            with pytest.raises(ValueError, match="declared source layout"):
                build_powerfactory_compatibility_fmu(cell, source_root, preflight_root, PowerFactoryCompatibilityProfile.FMI_THREE_CONFIGURATION_MODE, compiler)
            if previous_exists:
                assert preflight_output.read_bytes() == b"prior-source-checked-derivative"
            else:
                assert not preflight_output.exists()
    finally:
        retained_solver.rename(solver_source)
    if os.name == "nt":
        derived: Path
        receipt: dict[str, object]
        derived, receipt = build_powerfactory_compatibility_fmu(cell, tmp_path / "standard-build" / "source", tmp_path / "good", PowerFactoryCompatibilityProfile.FMI_THREE_CONFIGURATION_MODE, compiler)
        assert receipt["status"] == "PASS"
        original_archive: zipfile.ZipFile
        derived_archive: zipfile.ZipFile
        with zipfile.ZipFile(standard) as original_archive:
            with zipfile.ZipFile(derived) as derived_archive:
                assert sorted(original_archive.namelist()) == sorted(derived_archive.namelist())
                name: str
                assert all("compiler_build" not in name for name in derived_archive.namelist())
        corrupt: Path = tmp_path / "corrupt.dll"
        corrupt.write_bytes(b"corrupt replacement binary")
        failed_root: Path = tmp_path / "failed"
        previous_output: Path = failed_root / "compatibility_fmus" / "standard_PowerFactory.fmu"
        previous_output.parent.mkdir(parents=True)
        previous_output.write_bytes(b"prior-derivative")
        with pytest.raises(RuntimeError):
            build_powerfactory_compatibility_fmu(cell, tmp_path / "standard-build" / "source", failed_root, PowerFactoryCompatibilityProfile.FMI_THREE_CONFIGURATION_MODE, Compiler(compiler_handler=_ExportLibraryCompilerHandler(corrupt)))
        assert previous_output.read_bytes() == b"prior-derivative"
        assert tuple(previous_output.parent.glob(".veragrid_fmu_candidate_*")) == tuple()
    else:
        # The established PowerFactory recipe supports Windows DLL derivatives.
        # Other hosts must retain its explicit rejection, not silently skip it.
        with pytest.raises(ValueError, match="exactly one Windows binary"):
            build_powerfactory_compatibility_fmu(cell, tmp_path / "standard-build" / "source", tmp_path / "unsupported", PowerFactoryCompatibilityProfile.FMI_THREE_CONFIGURATION_MODE, compiler)


def test_snapshot_roundtrip_and_flatten() -> None:
    block = build_simple_block()
    snapshot = build_model_snapshot(block)
    restored = reconstruct_block(snapshot)
    flat = flatten_block(restored)

    assert len(flat.children) == 0
    assert len(flat.state_vars) == 1
    assert len(flat.algebraic_vars) == 1
    assert len(flat.diff_vars) == 1
    assert len(flat.in_vars) == 1
    assert len(flat.out_vars) == 1
    assert flat.parameters
    assert flat.event_dict


def test_export_ir_and_xml_generation(tmp_path: Path) -> None:
    block = build_simple_block()
    snapshot = build_model_snapshot(block)
    flat = flatten_block(block)
    cfg = ExportConfig(model_name="SimpleModel", output_path=tmp_path / "simple.fmu", compile_binary=False)
    logic_entries = build_co_simulation_logic_entries(flat)
    export_model = build_export_model(flat, cfg, snapshot, logic_entries)
    xml_text = emit_model_description(export_model)

    assert export_model.counts["states"] == 1
    assert export_model.counts["algebraics"] == 1
    assert export_model.counts["inputs"] == 1
    assert export_model.counts["outputs"] == 1
    assert 'modelName="SimpleModel"' in xml_text
    assert "<CoSimulation" in xml_text
    assert 'name="y"' in xml_text


def test_packager_creates_fmu_zip(tmp_path: Path) -> None:
    staging = prepare_fmu_staging_dir(tmp_path / "staging")
    (staging / "modelDescription.xml").write_text("<xml />", encoding="utf-8")
    (staging / "resources" / "manifest.json").write_text("{}", encoding="utf-8")
    output = package_fmu(staging, tmp_path / "demo.fmu")

    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        assert "modelDescription.xml" in archive.namelist()
        assert "resources/manifest.json" in archive.namelist()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_cs_export_failure_removes_owned_build_root(tmp_path: Path) -> None:
    """Remove the automatic CS build root when packaging fails.

    :param tmp_path: Isolated exporter output directory supplied by pytest.
    :return: None.
    """

    blocked_output_path: Path = tmp_path / "blocked_cs.fmu"
    blocked_output_path.mkdir()
    cfg: ExportConfig = ExportConfig(
        model_name="CleanupCsModel",
        output_path=blocked_output_path,
        compile_binary=True,
        keep_build_dir=False,
    )

    with pytest.raises(OSError):
        export_model_as_fmu(model=build_simple_block(), cfg=cfg)

    automatic_build_roots: tuple[Path, ...] = tuple(
        tmp_path.glob("veragrid_fmu_build_*")
    )
    assert automatic_build_roots == tuple()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_me_export_failure_removes_owned_build_root(tmp_path: Path) -> None:
    """Remove the automatic ME build root when packaging fails.

    :param tmp_path: Isolated exporter output directory supplied by pytest.
    :return: None.
    """

    blocked_output_path: Path = tmp_path / "blocked_me.fmu"
    blocked_output_path.mkdir()
    cfg: MeExportConfig = MeExportConfig(
        interface_type=InterfaceType.MODEL_EXCHANGE,
        model_name="CleanupMeModel",
        output_path=blocked_output_path,
        compile_binary=True,
        keep_build_dir=False,
    )

    with pytest.raises(OSError):
        export_model_as_fmu(model=build_simple_block(), cfg=cfg)

    automatic_build_roots: tuple[Path, ...] = tuple(
        tmp_path.glob("veragrid_fmu_me_build_*")
    )
    assert automatic_build_roots == tuple()


@pytest.mark.parametrize(
    "fmi_version",
    (
        FmiVersion.FMI_1_0,
        FmiVersion.FMI_2_0,
        FmiVersion.FMI_3_0,
    ),
)
@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_me_export_accepts_exact_continuous_state_start_values(
    tmp_path: Path,
    fmi_version: FmiVersion,
) -> None:
    """Apply an exact ME state start through each version's real setter.

    :param tmp_path: Isolated export and simulation directory supplied by pytest.
    :param fmi_version: FMI standard version selected for the compiled FMU.
    :return: None.
    """

    # The declared default is deliberately different from the importer-provided
    # value so the trajectory proves that the generated setter accepted the write.
    state: Var = Var("x")
    derivative: Var = Var("dx", base_var=state)
    source_block: Block = Block(
        state_vars=list((state,)),
        state_eqs=list((Const(1.0),)),
        diff_vars=list((derivative,)),
        init_values=dict(((state, Const(0.0)),)),
        out_vars=list((state,)),
        name="ExactStateStart",
    )
    model_identifier: str = "ExactStateStart" + fmi_version.value.replace(".", "")
    archive_path: Path = export_model_as_fmu(
        model=source_block,
        cfg=MeExportConfig(
            interface_type=InterfaceType.MODEL_EXCHANGE,
            model_name=model_identifier,
            output_path=tmp_path / (model_identifier + ".fmu"),
            fixed_step=1.0e-3,
            fmi_version=fmi_version,
        ),
    )

    # FMPy follows the same importer sequence observed in Simulink: it writes the
    # exact state through fmiSetReal/fmi2SetReal/fmi3SetFloat64 before initialize.
    result: np.ndarray = simulate_fmu(
        filename=str(archive_path),
        start_time=0.0,
        stop_time=2.0e-3,
        step_size=1.0e-3,
        output_interval=1.0e-3,
        output=("x",),
        start_values=dict(x=2.0),
    )
    expected_times: np.ndarray = np.array((0.0, 1.0e-3, 2.0e-3), dtype=float)
    np.testing.assert_allclose(result["time"], expected_times, rtol=0.0, atol=1.0e-15)
    np.testing.assert_allclose(result["x"][0], 2.0, rtol=0.0, atol=1.0e-12)
    np.testing.assert_allclose(
        result["x"],
        2.0 + result["time"],
        rtol=0.0,
        atol=1.0e-8,
    )


def _build_validation_probe_library(
    tmp_path: Path,
    compiler: Compiler,
    behavior: _ValidationLoadBehavior,
) -> tuple[ExportConfig, Path, Path]:
    """Prepare a complete FMI2 library with a controlled native timing boundary.

    :param tmp_path: Owned generated-source and native probe directory.
    :param compiler: Real selected compiler; no executable/provider substitution.
    :param behavior: Delay a valid load or hold a valid library inside unload.
    :return: Export config, prepared native library and real native-entry marker.
    """
    config: ExportConfig = ExportConfig(model_name="TimingProbe", output_path=tmp_path / "final.fmu", fmi_version=FmiVersion.FMI_2_0, build_dir=tmp_path / "build", keep_build_dir=True)
    export_model_as_fmu(build_simple_block(), config, compiler)
    source_root: Path = tmp_path / "build" / "source"
    source: Path = source_root / "src" / "runtime_fmi2.c"
    marker: Path = tmp_path / "native-timing-entered"
    marker_literal: str = marker.as_posix().replace('"', '\\"')
    record_entry: str = f'FILE* marker = fopen("{marker_literal}", "wb"); if (marker != NULL) {{ fputs("entered", marker); fclose(marker); }} '
    if os.name == "nt":
        reason: str = "1" if behavior == _ValidationLoadBehavior.SLOW_START else "0"
        action: str = "Sleep(31000);" if behavior == _ValidationLoadBehavior.SLOW_START else "for (;;) { }"
        native_code: str = '\n#include <stdio.h>\n__declspec(dllimport) void __stdcall Sleep(unsigned long milliseconds);\nint __stdcall DllMain(void* module, unsigned long reason, void* reserved) { if (reason == ' + reason + ') { ' + record_entry + action + ' } else { } return 1; }\n'
    else:
        attribute: str = "constructor" if behavior == _ValidationLoadBehavior.SLOW_START else "destructor"
        action = "sleep(31);" if behavior == _ValidationLoadBehavior.SLOW_START else "for (;;) { }"
        native_code = '\n#include <stdio.h>\n#include <unistd.h>\n__attribute__((' + attribute + ')) static void validation_timing_probe(void) { ' + record_entry + action + ' }\n'
    source.write_text(source.read_text(encoding="utf-8") + native_code, encoding="utf-8")
    library: Path = tmp_path / config.library_name
    sources: tuple[Path, ...] = tuple((source_root / "src").glob("*.c"))
    compile_fmu_shared_library(sources, (source_root / "include", source_root / "src"), library, compiler)
    return config, library, marker


def test_export_validation_accepts_slow_load(tmp_path: Path) -> None:
    """Accept a valid native initializer that deliberately exceeds thirty seconds.

    :param tmp_path: Owned real native library and final output directory.
    :return: None; this proves runtime success, not merely an absent deadline.
    """
    compiler: Compiler | None = build_test_fmi_compiler()
    if compiler is None:
        pytest.skip("No saved usable Clang session is available")
    else:
        pass
    config: ExportConfig
    library: Path
    marker: Path
    config, library, marker = _build_validation_probe_library(tmp_path, compiler, _ValidationLoadBehavior.SLOW_START)
    control: FmuValidationControl = FmuValidationControl()
    started_at: float = monotonic()
    output: Path = export_model_as_fmu(build_simple_block(), config, Compiler(compiler_handler=_ExportLibraryCompilerHandler(library)), control)
    assert monotonic() - started_at >= 31.0
    assert marker.read_text(encoding="utf-8") == "entered"
    assert output == config.output_path and output.is_file()
    assert control.get_phase() == FmuValidationPhase.COMPLETED
    assert not control.cancel()


def test_export_validation_cancellation_during_unload(tmp_path: Path) -> None:
    """Cancel after real function resolution when native unload does not return.

    :param tmp_path: Owned valid library, unload marker and preserved output.
    :return: None; cancellation must reap the child and retain prior FMU bytes.
    """
    compiler: Compiler | None = build_test_fmi_compiler()
    if compiler is None:
        pytest.skip("No saved usable Clang session is available")
    else:
        pass
    config: ExportConfig
    library: Path
    marker: Path
    config, library, marker = _build_validation_probe_library(tmp_path, compiler, _ValidationLoadBehavior.HANG_UNLOAD)
    previous: bytes = config.output_path.read_bytes()
    children_before: set[int | None] = set(child.pid for child in active_children())
    extraction_before: set[Path] = set(Path(gettempdir()).glob("veragrid_fmu_validation_*"))
    control: FmuValidationControl = FmuValidationControl()
    requester: _ExportCancellationRequester = _ExportCancellationRequester(marker, control, FmuValidationPhase.UNLOADING)
    requester.start()
    try:
        with pytest.raises(CancelledError):
            export_model_as_fmu(build_simple_block(), config, Compiler(compiler_handler=_ExportLibraryCompilerHandler(library)), control)
    finally:
        requester.join(timeout=3.0)
    assert not requester.is_alive() and requester.observed_native and requester.accepted
    assert control.get_phase() == FmuValidationPhase.CANCELLED
    assert config.output_path.read_bytes() == previous
    assert set(child.pid for child in active_children()) == children_before
    assert set(Path(gettempdir()).glob("veragrid_fmu_validation_*")) == extraction_before
    assert tuple(tmp_path.glob(".veragrid_fmu_candidate_*")) == tuple()


@pytest.mark.parametrize("cancel_first", (False, True))
def test_export_validation_cancellation_boundary(tmp_path: Path, cancel_first: bool) -> None:
    """Exercise both publication orderings while another canceller is blocked.

    :param tmp_path: Owned candidate and prior output; these bytes test commit
        coordination and make no claim of having passed FMI validation.
    :param cancel_first: Choose which operation wins the serialized boundary.
    :return: None; a conflicting cancellation result or replaced prior file fails.
    """
    control: FmuValidationControl = FmuValidationControl()
    control._begin()
    control._set_phase(FmuValidationPhase.VALIDATED)
    candidate: Path = tmp_path / "candidate"
    output: Path = tmp_path / "final"
    marker: Path = tmp_path / "publication-barrier"
    candidate.write_bytes(b"new-validated-fixture")
    output.write_bytes(b"prior-fixture")
    marker.write_bytes(b"")
    requester: _ExportCancellationRequester = _ExportCancellationRequester(marker, control)
    try:
        # RLock permits the owning thread to exercise the real commit method
        # while a second thread has attempted cancellation on that same lock.
        with control._lock:
            requester.start()
            assert requester.started.wait(timeout=3.0)
            assert not requester.finished.wait(timeout=0.05)
            if cancel_first:
                assert control.cancel()
                with pytest.raises(CancelledError):
                    control._publish(candidate, output)
            else:
                assert control._publish(candidate, output) == output
    finally:
        requester.join(timeout=3.0)
    assert not requester.is_alive() and requester.accepted is False
    if cancel_first:
        assert control.get_phase() == FmuValidationPhase.CANCELLED
        assert output.read_bytes() == b"prior-fixture" and candidate.exists()
    else:
        assert control.get_phase() == FmuValidationPhase.COMPLETED
        assert output.read_bytes() == b"new-validated-fixture" and not candidate.exists()


@pytest.mark.parametrize("timeout", (0.0, -1.0, float("inf"), float("nan")))
def test_validation_control_contract(tmp_path: Path, timeout: float) -> None:
    """Protect pre-start cancellation, early reuse rejection and failure states.

    :param tmp_path: Owned build/output paths that must remain unmodified.
    :param timeout: Invalid shutdown bound, never an execution deadline.
    :return: None; prior operation state and files must survive rejected reuse.
    """
    with pytest.raises(ValueError, match="finite and positive"):
        FmuValidationControl(shutdown_timeout_seconds=timeout)
    config: ExportConfig = ExportConfig(model_name="ControlContract", output_path=tmp_path / "final.fmu", build_dir=tmp_path / "build")
    control: FmuValidationControl = FmuValidationControl()
    assert control.cancel()
    with pytest.raises(CancelledError):
        export_model_as_fmu(object(), config, validation_control=control)
    assert control.get_phase() == FmuValidationPhase.CANCELLED
    assert not (tmp_path / "build").exists() and not config.output_path.exists()
    active: FmuValidationControl = FmuValidationControl()
    active._begin()
    phase: FmuValidationPhase
    for phase in (FmuValidationPhase.PREPARING, FmuValidationPhase.COMPLETED):
        active._set_phase(phase)
        with pytest.raises(ValueError, match="single-use"):
            export_model_as_fmu(object(), config, validation_control=active)
        with pytest.raises(ValueError, match="single-use"):
            package_validated_fmu(tmp_path / "absent-staging", config, active)
        assert active.get_phase() == phase
        assert not (tmp_path / "build").exists() and not config.output_path.exists()
    failed: FmuValidationControl = FmuValidationControl()
    unsupported: ExportConfig = ExportConfig(model_name="NoCompile", output_path=tmp_path / "unsupported.fmu", compile_binary=False)
    with pytest.raises(ValueError, match="Source-only"):
        export_model_as_fmu(object(), unsupported, validation_control=failed)
    assert failed.get_phase() == FmuValidationPhase.FAILED and not failed.cancel()


@pytest.mark.parametrize("start_attempted,has_pid,stops_after_kill", ((True, True, True), (True, True, False), (True, False, False), (False, False, False)))
def test_validation_process_cleanup_contract(tmp_path: Path, start_attempted: bool, has_pid: bool, stops_after_kill: bool) -> None:
    """Keep extraction on unknown ownership and verify bounded kill escalation.

    :param tmp_path: Owned dummy extraction; no actual process is targeted.
    :param start_attempted: Whether entering start makes missing PID ambiguous.
    :param has_pid: Whether the process probe exposes a usable identity.
    :param stops_after_kill: Whether the probe confirms death after kill.
    :return: None; stop requests alone must never permit unsafe deletion.
    """
    extraction: Path = tmp_path / "extraction"
    extraction.mkdir()
    (extraction / "retained").write_bytes(b"owned-native-material")
    process: _ValidationProcessProbe = _ValidationProcessProbe(has_pid, stops_after_kill)
    if not start_attempted or has_pid and stops_after_kill:
        _release_export_validation(process, start_attempted, extraction, 0.25)
        assert not extraction.exists() and process.closed
    else:
        with pytest.raises(RuntimeError, match="extraction retained"):
            _release_export_validation(process, start_attempted, extraction, 0.25)
        assert (extraction / "retained").read_bytes() == b"owned-native-material"
        assert not process.closed
    if has_pid:
        assert process.terminated and process.killed and process.joined == 2
        assert process.join_limits == list((0.25, 0.25))
    else:
        assert not process.terminated and not process.killed and process.joined == 0
    empty: Path = tmp_path / "no-process"
    empty.mkdir()
    _release_export_validation(None, False, empty, 0.25)
    assert not empty.exists()
