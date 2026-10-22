# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Public FMI model-to-FMU interface."""

from __future__ import annotations

from pathlib import Path
from concurrent.futures import CancelledError
from enum import Enum
import math
from multiprocessing import get_context
from multiprocessing.context import BaseContext
from multiprocessing.process import BaseProcess
import shutil
from tempfile import mkdtemp
from threading import Event, RLock
from typing import BinaryIO
import warnings

from fmpy import extract, read_model_description
from fmpy.fmi1 import FMU1Model, FMU1Slave
from fmpy.fmi2 import FMU2Model, FMU2Slave
from fmpy.fmi3 import FMU3Model, FMU3Slave
from fmpy.model_description import ModelDescription

from VeraGridEngine.IO.fmu.archive import package_fmu, prepare_fmu_staging_dir
from VeraGridEngine.IO.fmu.config import ExportConfig, InterfaceType, parse_declared_fmi_version
from VeraGridEngine.IO.fmu.compiler import Compiler
from VeraGridEngine.IO.fmu.config import binary_directory
from VeraGridEngine.IO.fmu.CosimulationInterface.build import build_shared_library as build_co_simulation_library
from VeraGridEngine.IO.fmu.CosimulationInterface.build import emit_c_sources as emit_co_simulation_sources
from VeraGridEngine.IO.fmu.CosimulationInterface.build import ensure_build_layout as ensure_co_simulation_layout
from VeraGridEngine.IO.fmu.CosimulationInterface.build import write_debug_resources as write_co_simulation_resources
from VeraGridEngine.IO.fmu.CosimulationInterface.export_ir import build_export_model as build_co_simulation_model
from VeraGridEngine.IO.fmu.model import flatten_model
from VeraGridEngine.IO.fmu.logic import build_co_simulation_logic_entries
from VeraGridEngine.IO.fmu.model import build_model_snapshot
from VeraGridEngine.IO.fmu.CosimulationInterface.validate import validate_export_model as validate_co_simulation_model
from VeraGridEngine.IO.fmu.CosimulationInterface.xml_writer import write_model_description as write_co_simulation_description
from VeraGridEngine.IO.fmu.ExportInterface.build import build_shared_library as build_model_exchange_library
from VeraGridEngine.IO.fmu.ExportInterface.build import emit_c_sources as emit_model_exchange_sources
from VeraGridEngine.IO.fmu.ExportInterface.build import ensure_build_layout as ensure_model_exchange_layout
from VeraGridEngine.IO.fmu.ExportInterface.build import write_debug_resources as write_model_exchange_resources
from VeraGridEngine.IO.fmu.ExportInterface.export_ir import build_export_model as build_model_exchange_model
from VeraGridEngine.IO.fmu.ExportInterface.normalize import prepare_flat_block_for_me
from VeraGridEngine.IO.fmu.logic import build_model_exchange_logic_entries
from VeraGridEngine.IO.fmu.ExportInterface.validate import validate_export_model as validate_model_exchange_model
from VeraGridEngine.IO.fmu.ExportInterface.xml_writer import write_model_description as write_model_exchange_description
from VeraGridEngine.enumerations import FmiVersion


class FmuValidationPhase(Enum):
    """Describe observed export progress without inferring native liveness."""

    NOT_STARTED = 0
    PREPARING = 1
    LOADING = 2
    UNLOADING = 3
    VALIDATED = 4
    COMPLETED = 5
    CANCELLED = 6
    FAILED = 7


class FmuValidationControl:
    """Own cancellation and the publication boundary of one export attempt.

    The control is single-use and belongs to the calling process. A separate
    caller thread may request cancellation or inspect the observed phase.
    Native children never acquire its locks. Cancellation does not preempt
    synchronous source generation or compilation; it is checked before native
    validation and final publication.
    """

    __slots__: tuple[str, ...] = ("_cancel_requested", "_lock", "_phase", "_shutdown_timeout_seconds")

    def __init__(self: FmuValidationControl, shutdown_timeout_seconds: float = 5.0) -> None:
        """Create an unused control with a bounded forced-shutdown wait.

        :param shutdown_timeout_seconds: Finite positive wait after terminate
            and after kill. This never limits validation or native startup.
        :return: None.
        """
        if math.isfinite(shutdown_timeout_seconds) and shutdown_timeout_seconds > 0.0:
            pass
        else:
            raise ValueError("Shutdown wait must be finite and positive")
        self._shutdown_timeout_seconds: float = shutdown_timeout_seconds
        self._cancel_requested: Event = Event()
        self._lock: RLock = RLock()
        self._phase: FmuValidationPhase = FmuValidationPhase.NOT_STARTED

    def cancel(self: FmuValidationControl) -> bool:
        """Request cancellation unless publication or another terminal state won.

        :return: True when the request is retained, including before start;
            False when the operation has already completed, failed or cancelled.
        """
        # Sharing the publication lock makes the return value meaningful even
        # when cancellation arrives concurrently with the final atomic rename.
        with self._lock:
            if self._phase in (FmuValidationPhase.COMPLETED, FmuValidationPhase.FAILED, FmuValidationPhase.CANCELLED):
                return False
            else:
                self._cancel_requested.set()
                return True

    def get_phase(self: FmuValidationControl) -> FmuValidationPhase:
        """Read the last observed phase without claiming progress inside a call.

        :return: Current phase; LOADING or UNLOADING may remain indefinitely
            until the native call returns or cancellation is requested.
        """
        with self._lock:
            return self._phase

    def _begin(self: FmuValidationControl) -> None:
        """Claim this control before any export-owned mutation.

        :return: None; reused controls raise ValueError without changing the
            original operation. Pre-start cancellation raises CancelledError.
        """
        with self._lock:
            if self._phase != FmuValidationPhase.NOT_STARTED:
                raise ValueError("FMU validation control is single-use")
            else:
                self._phase = FmuValidationPhase.PREPARING
            if self._cancel_requested.is_set():
                self._phase = FmuValidationPhase.CANCELLED
                raise CancelledError("FMU export cancelled before preparation")
            else:
                pass

    def _set_phase(self: FmuValidationControl, phase: FmuValidationPhase) -> None:
        """Record an observed transition in the parent-owned operation.

        :param phase: State established by the export lifecycle owner.
        :return: None.
        """
        with self._lock:
            self._phase = phase

    def _publish(self: FmuValidationControl, candidate: Path, output_path: Path) -> Path:
        """Commit validated bytes while serializing cancellation with publication.

        :param candidate: Exact archive whose isolated validation completed.
        :param output_path: Final sibling destination to replace atomically.
        :return: Final path. Cancellation before the rename preserves it.
        """
        with self._lock:
            if self._phase != FmuValidationPhase.VALIDATED:
                raise ValueError("FMU publication requires completed validation")
            else:
                pass
            if self._cancel_requested.is_set():
                self._phase = FmuValidationPhase.CANCELLED
                raise CancelledError("FMU export cancelled before publication")
            else:
                # The caller owns both paths on the same filesystem. Never
                # unlink the previous final output before this atomic commit.
                candidate.replace(output_path)
                self._phase = FmuValidationPhase.COMPLETED
                return output_path


def _run_exported_fmu_validation(
    extraction_directory: Path,
    fmi_version: FmiVersion,
    interface_type: InterfaceType,
    completion_path: Path,
    diagnostic_path: Path,
    loading_path: Path,
    unloading_path: Path,
) -> None:
    """Resolve the packaged FMI API exclusively inside a disposable child.

    :param extraction_directory: Parent-owned extraction of the candidate FMU.
    :param fmi_version: FMI family required by the export request.
    :param interface_type: Required CS or ME interface.
    :param completion_path: Parent-owned receipt written after successful unload.
    :param diagnostic_path: Parent-owned file receiving bounded error details.
    :param loading_path: Empty marker written before native API resolution.
    :param unloading_path: Empty marker written before native unload.
    :return: None. Absence of the completion receipt always means rejection.
    """
    try:
        # Normal FMPy constructors load the binary and resolve its API without
        # instantiating or simulating a model. Process exit also releases a
        # partially constructed runtime after a missing-function error.
        description: ModelDescription = read_model_description(str(extraction_directory))
        if parse_declared_fmi_version(description.fmiVersion) == fmi_version:
            pass
        else:
            raise ValueError("Packaged FMI version differs from the export request")
        model_identifier: str
        runtime: FMU1Slave | FMU2Slave | FMU3Slave | FMU1Model | FMU2Model | FMU3Model
        if interface_type == InterfaceType.CO_SIMULATION:
            if description.coSimulation is not None:
                model_identifier = description.coSimulation.modelIdentifier
            else:
                raise ValueError("Packaged FMU lacks the requested Co-Simulation interface")
            loading_path.write_bytes(b"")
            if fmi_version == FmiVersion.FMI_1_0:
                runtime = FMU1Slave(guid=description.guid, modelIdentifier=model_identifier, unzipDirectory=str(extraction_directory), requireFunctions=True)
            elif fmi_version == FmiVersion.FMI_2_0:
                runtime = FMU2Slave(guid=description.guid, modelIdentifier=model_identifier, unzipDirectory=str(extraction_directory), requireFunctions=True)
            else:
                runtime = FMU3Slave(guid=description.guid, modelIdentifier=model_identifier, unzipDirectory=str(extraction_directory), requireFunctions=True)
        elif interface_type == InterfaceType.MODEL_EXCHANGE:
            if description.modelExchange is not None:
                model_identifier = description.modelExchange.modelIdentifier
            else:
                raise ValueError("Packaged FMU lacks the requested Model Exchange interface")
            loading_path.write_bytes(b"")
            if fmi_version == FmiVersion.FMI_1_0:
                runtime = FMU1Model(guid=description.guid, modelIdentifier=model_identifier, unzipDirectory=str(extraction_directory), requireFunctions=True)
            elif fmi_version == FmiVersion.FMI_2_0:
                runtime = FMU2Model(guid=description.guid, modelIdentifier=model_identifier, unzipDirectory=str(extraction_directory), requireFunctions=True)
            else:
                runtime = FMU3Model(guid=description.guid, modelIdentifier=model_identifier, unzipDirectory=str(extraction_directory), requireFunctions=True)
        else:
            raise ValueError("Unsupported FMI export interface")
        unloading_path.write_bytes(b"")
        runtime.freeLibrary()
        # A clean exit alone is insufficient: native initialization can call
        # exit(0). Only reaching this point certifies function resolution.
        completion_path.write_bytes(b"")
    except Exception as error:
        diagnostic_path.write_bytes(str(error).encode("utf-8")[:8192])


def _validate_exported_fmu(
    output_path: Path,
    config: ExportConfig,
    validation_control: FmuValidationControl | None = None,
) -> None:
    """Supervise the packaged library without an execution deadline.

    :param output_path: Complete candidate archive, never the final output.
    :param config: Expected FMI version and interface.
    :param validation_control: Already claimed internal control, or None for
        a standalone private validation that creates its own control.
    :return: None after successful child exit and cleanup. Cancellation raises
        CancelledError; native failures raise RuntimeError with diagnostics.
    """
    control: FmuValidationControl = validation_control if validation_control is not None else FmuValidationControl()
    if validation_control is None:
        control._begin()
    else:
        pass
    context: BaseContext = get_context("spawn")
    extraction_root: Path = Path(mkdtemp(prefix="veragrid_fmu_validation_"))
    extraction_directory: Path = extraction_root / "fmu"
    completion_path: Path = extraction_root / "complete"
    diagnostic_path: Path = extraction_root / "diagnostic"
    loading_path: Path = extraction_root / "loading"
    unloading_path: Path = extraction_root / "unloading"
    process: BaseProcess | None = None
    process_start_attempted: bool = False
    try:
        if control._cancel_requested.is_set():
            raise CancelledError("FMU validation cancelled before native startup")
        else:
            pass
        process = context.Process(
            target=_run_exported_fmu_validation,
            args=(extraction_directory, config.fmi_version, config.interface_type, completion_path, diagnostic_path, loading_path, unloading_path),
        )
        extract(str(output_path.resolve()), unzipdir=str(extraction_directory))
        process_start_attempted = True
        process.start()
        # The join interval only makes cancellation observable. It never
        # rejects slow interpreter startup, native loading or native unloading.
        while process.is_alive():
            if control._cancel_requested.is_set():
                raise CancelledError("FMU native validation cancelled; validity is unverified")
            else:
                pass
            if unloading_path.is_file():
                control._set_phase(FmuValidationPhase.UNLOADING)
            elif loading_path.is_file():
                control._set_phase(FmuValidationPhase.LOADING)
            else:
                pass
            process.join(timeout=0.1)
        if control._cancel_requested.is_set():
            raise CancelledError("FMU validation cancelled before completion")
        else:
            pass
        # Native initialization can call exit(0). A clean exit is insufficient
        # unless function resolution AND unload reached the completion receipt.
        if process.exitcode == 0 and completion_path.is_file() and completion_path.stat().st_size == 0 and not diagnostic_path.exists():
            pass
        else:
            diagnostic: str = "No successful validation receipt"
            if diagnostic_path.is_file():
                diagnostic_stream: BinaryIO
                with diagnostic_path.open("rb") as diagnostic_stream:
                    diagnostic = diagnostic_stream.read(8193).decode("utf-8", errors="replace")
            else:
                pass
            raise RuntimeError(f"FMU native validation failed (child exit {process.exitcode}): {diagnostic}")
    finally:
        _release_export_validation(process, process_start_attempted, extraction_root, control._shutdown_timeout_seconds)
    control._set_phase(FmuValidationPhase.VALIDATED)


def _release_export_validation(
    process: BaseProcess | None,
    process_start_attempted: bool,
    extraction_root: Path,
    shutdown_timeout_seconds: float,
) -> None:
    """Release extraction only after the owned child's death is established.

    :param process: Validation child, including a partially started process.
    :param process_start_attempted: Whether start was entered before failure.
    :param extraction_root: Exact temporary extraction root owned by this call.
    :param shutdown_timeout_seconds: Wait after terminate and after kill.
    :return: None after cleanup. Unproven death raises with the retained path.
    """
    # Native termination bypasses child finally blocks. No parent control lock
    # is shared with the child, so forced termination cannot strand that lock.
    if process is not None and process.pid is not None:
        if process.is_alive():
            try:
                process.terminate()
            except OSError:
                pass
            process.join(timeout=shutdown_timeout_seconds)
        else:
            pass
        if process.is_alive():
            try:
                process.kill()
            except OSError:
                pass
            process.join(timeout=shutdown_timeout_seconds)
        else:
            pass
        process_stopped: bool = not process.is_alive() and process.exitcode is not None
    else:
        # Interrupted start without a PID leaves ownership unknown. Keep the
        # extraction instead of assuming no child acquired its native files.
        process_stopped = not process_start_attempted
    if process_stopped:
        try:
            if process is not None:
                process.close()
            else:
                pass
        finally:
            shutil.rmtree(extraction_root)
    else:
        raise RuntimeError(f"Could not stop FMU validation child; extraction retained at {extraction_root}")


def package_validated_fmu(
    staging_dir: Path,
    config: ExportConfig,
    validation_control: FmuValidationControl | None = None,
) -> Path:
    """Claim an operation and publish only its validated packaged library.

    :param staging_dir: Complete intended members, excluding build evidence.
    :param config: Expected FMI version/interface and final destination.
    :param validation_control: Optional single-use caller cancellation control.
    :return: Final path after atomic publication; pre-commit failures preserve it.
    """
    control: FmuValidationControl = validation_control if validation_control is not None else FmuValidationControl()
    control._begin()
    try:
        return _package_validated_fmu(staging_dir, config, control)
    except BaseException as error:
        if control.get_phase() != FmuValidationPhase.COMPLETED:
            control._set_phase(FmuValidationPhase.CANCELLED if isinstance(error, (CancelledError, KeyboardInterrupt)) else FmuValidationPhase.FAILED)
        else:
            pass
        raise


def _package_validated_fmu(staging_dir: Path, config: ExportConfig, control: FmuValidationControl) -> Path:
    """Share publication between already claimed export and package operations.

    :param staging_dir: Intended archive tree owned by the caller.
    :param config: Expected FMI version/interface and final destination.
    :param control: Claimed operation; internal calls never reclaim it.
    :return: Final path after exact candidate validation and atomic replacement.
    """
    if control._cancel_requested.is_set():
        raise CancelledError("FMU export cancelled before packaging")
    else:
        pass
    output_path: Path = config.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_directory: Path = Path(mkdtemp(prefix=".veragrid_fmu_candidate_", dir=str(output_path.parent)))
    try:
        candidate: Path = package_fmu(staging_dir, candidate_directory / output_path.name)
        _validate_exported_fmu(candidate, config, control)
        return control._publish(candidate, output_path)
    finally:
        try:
            shutil.rmtree(candidate_directory)
        except OSError as error:
            if control.get_phase() == FmuValidationPhase.COMPLETED:
                # Committed valid bytes remain published. Cleanup trouble is
                # diagnostic, never evidence that their FMI validation failed.
                warnings.warn(f"FMU published; candidate cleanup failed at {candidate_directory}: {error}", RuntimeWarning, stacklevel=2)
            else:
                raise


def export_model_as_fmu(
    model: object,
    cfg: ExportConfig,
    compiler: Compiler | None = None,
    validation_control: FmuValidationControl | None = None,
) -> Path:
    """Export through the selected FMI interface with optional cancellation.

    :param model: VeraGrid symbolic model to export.
    :param cfg: Shared FMI export configuration.
    :param compiler: Optional caller-owned compiler session.
    :param validation_control: Single-use control; another caller thread may
        cancel or inspect it. Compilation is synchronous and not preempted.
    :return: Packaged FMU path after validation and atomic publication.
    """
    control: FmuValidationControl = validation_control if validation_control is not None else FmuValidationControl()
    # Claim before compilation or staging so rejected reuse cannot touch an
    # earlier operation, including one still running with this same control.
    control._begin()
    try:
        if cfg.interface_type == InterfaceType.CO_SIMULATION:
            return _export_co_simulation(model, cfg, compiler, control)
        elif cfg.interface_type == InterfaceType.MODEL_EXCHANGE:
            return _export_model_exchange(model, cfg, compiler, control)
        else:
            raise ValueError("Unsupported FMI interface type")
    except BaseException as error:
        if control.get_phase() != FmuValidationPhase.COMPLETED:
            control._set_phase(FmuValidationPhase.CANCELLED if isinstance(error, (CancelledError, KeyboardInterrupt)) else FmuValidationPhase.FAILED)
        else:
            pass
        raise


def _export_co_simulation(
    model: object,
    config: ExportConfig,
    compiler: Compiler | None,
    control: FmuValidationControl,
) -> Path:
    """Build and package one Co-Simulation FMU.

    :param model: VeraGrid symbolic model to export.
    :param config: Co-Simulation export settings.
    :param compiler: Optional caller-owned compiler session.
    :param control: Operation claimed before build preparation.
    :return: Packaged FMU path.
    """
    if not config.compile_binary:
        raise ValueError("Source-only FMU packaging is not implemented")
    snapshot = build_model_snapshot(model)
    flat_block = flatten_model(snapshot)
    logic_entries = build_co_simulation_logic_entries(flat_block)
    export_model = build_co_simulation_model(flat_block, config, snapshot, logic_entries)
    validate_co_simulation_model(export_model)
    source_dir, build_dir, staging_dir = ensure_co_simulation_layout(config)
    automatic_build_root: bool = config.build_dir is None
    build_root: Path = source_dir.parent
    export_completed: bool = False
    try:
        source_dir.mkdir(parents=True, exist_ok=True)
        staging_root: Path = prepare_fmu_staging_dir(staging_dir)
        emit_co_simulation_sources(export_model, config, source_dir)
        write_co_simulation_description(export_model, staging_root / "modelDescription.xml", config.fmi_version)
        write_co_simulation_resources(export_model, config, staging_root / "resources")
        library_path: Path = build_co_simulation_library(config, source_dir, build_dir, compiler)
        binaries_dir: Path = staging_root / "binaries" / binary_directory(config.target_platform, config.fmi_version)
        binaries_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library_path, binaries_dir / config.library_name)
        output_path: Path = _package_validated_fmu(staging_root, config, control)
        export_completed = True
        return output_path
    finally:
        if automatic_build_root and not config.keep_build_dir:
            shutil.rmtree(build_root, ignore_errors=not export_completed)


def _export_model_exchange(
    model: object,
    config: ExportConfig,
    compiler: Compiler | None,
    control: FmuValidationControl,
) -> Path:
    """Build and package one Model Exchange FMU.

    :param model: VeraGrid symbolic model to export.
    :param config: Model Exchange export settings.
    :param compiler: Optional caller-owned compiler session.
    :param control: Operation claimed before build preparation.
    :return: Packaged FMU path.
    """
    if not config.compile_binary:
        raise ValueError("Source-only FMU packaging is not implemented")
    snapshot = build_model_snapshot(model)
    flat_block = prepare_flat_block_for_me(snapshot)
    logic_entries = build_model_exchange_logic_entries(flat_block)
    export_model = build_model_exchange_model(flat_block, config, snapshot, logic_entries)
    validate_model_exchange_model(export_model)
    source_dir, build_dir, staging_dir = ensure_model_exchange_layout(config)
    automatic_build_root: bool = config.build_dir is None
    build_root: Path = source_dir.parent
    export_completed: bool = False
    try:
        source_dir.mkdir(parents=True, exist_ok=True)
        staging_root: Path = prepare_fmu_staging_dir(staging_dir)
        emit_model_exchange_sources(export_model, config, source_dir)
        write_model_exchange_description(export_model, staging_root / "modelDescription.xml", config.fmi_version)
        write_model_exchange_resources(export_model, config, staging_root / "resources")
        library_path: Path = build_model_exchange_library(config, source_dir, build_dir, compiler)
        binaries_dir: Path = staging_root / "binaries" / binary_directory(config.target_platform, config.fmi_version)
        binaries_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library_path, binaries_dir / config.library_name)
        output_path: Path = _package_validated_fmu(staging_root, config, control)
        export_completed = True
        return output_path
    finally:
        if automatic_build_root and not config.keep_build_dir:
            shutil.rmtree(build_root, ignore_errors=not export_completed)
