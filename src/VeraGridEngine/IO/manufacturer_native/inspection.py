# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import IeeeCigreDllDataType, IeeeCigreDllModelMode
from typing import Tuple

from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import (
    ManufacturerNativeBinarySource,
    ManufacturerNativeBinaryVariant,
)
from VeraGridEngine.enumerations import (
    IeeeCigreDllPlatform,
    IeeeCigreDllVerificationStatus,
    NativeModelInterface,
)
from VeraGridEngine.IO.manufacturer_native.binary_validation import _inspect_native_binary
from VeraGridEngine.IO.manufacturer_native.model_info import ManufacturerNativeModelInfo
from VeraGridEngine.IO.manufacturer_native.model_info_codec import (
    decode_manufacturer_native_model_info,
    digest_manufacturer_native_model_info,
)
from VeraGridEngine.IO.manufacturer_native.runtime_host import (
    ManufacturerNativeWorkerHost,
    prepare_manufacturer_native_worker_host,
)
from VeraGridEngine.IO.manufacturer_native.worker_artifact import (
    ManufacturerNativeWorkerArtifact,
    resolve_manufacturer_native_worker,
)
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection
from VeraGridEngine.IO.manufacturer_native.worker_protocol import (
    ManufacturerNativeWorkerOpcode,
    ManufacturerNativeWorkerRequest,
    ManufacturerNativeWorkerResponse,
    ManufacturerNativeWorkerStatus,
    decode_manufacturer_native_worker_response,
    encode_manufacturer_native_worker_request,
)
from VeraGridEngine.IO.native_runtime import (
    ExternalNativeWorkerProcessOwner,
    NativeWorkerLimits,
    stage_native_library,
)


class ManufacturerNativeInspectionLimits:
    """Finite limits applied before and during isolated library inspection."""

    __slots__ = ("worker_limits", "inspection_timeout_seconds")

    def __init__(self,
                 worker_limits: NativeWorkerLimits | None = None,
                 inspection_timeout_seconds: float = 5.0) -> None:
        """Create inspection limits.

        :param worker_limits: Shared staging, transport and allocation limits.
        :param inspection_timeout_seconds: Maximum child inspection duration.
        :return: None.
        """
        if inspection_timeout_seconds <= 0.0 or inspection_timeout_seconds > 60.0:
            raise ValueError("IEEE/CIGRE inspection timeout must be in (0, 60] seconds")
        else:
            pass
        self.worker_limits: NativeWorkerLimits = (
            NativeWorkerLimits() if worker_limits is None else worker_limits
        )
        self.inspection_timeout_seconds: float = inspection_timeout_seconds


class ManufacturerNativeInspectionResult:
    """Complete immutable evidence produced before Assets mutation."""

    __slots__ = (
        "platform", "binary_sha256", "binary_size", "dependencies", "model_info",
        "canonical_model_info", "model_info_sha256", "verification_status",
    )

    def __init__(self,
                 platform: IeeeCigreDllPlatform,
                 binary_sha256: str,
                 binary_size: int,
                 dependencies: Tuple[str, ...],
                 model_info: ManufacturerNativeModelInfo,
                 canonical_model_info: bytes,
                 model_info_sha256: str,
                 verification_status: IeeeCigreDllVerificationStatus) -> None:
        """Store one successful bounded inspection.

        :param platform: Exact host platform inspected.
        :param binary_sha256: SHA-256 of staged manufacturer bytes.
        :param binary_size: Exact primary binary size.
        :param dependencies: Ordered statically declared OS-runtime basenames.
        :param model_info: Sole typed decoding of canonical metadata.
        :param canonical_model_info: Exact canonical metadata bytes.
        :param model_info_sha256: Digest of the canonical metadata bytes.
        :param verification_status: Qualification state reached by this inspection.
        :return: None.
        """
        self.platform: IeeeCigreDllPlatform = platform
        self.binary_sha256: str = binary_sha256
        self.binary_size: int = binary_size
        self.dependencies: Tuple[str, ...] = dependencies
        self.model_info: ManufacturerNativeModelInfo = model_info
        self.canonical_model_info: bytes = canonical_model_info
        self.model_info_sha256: str = model_info_sha256
        self.verification_status: IeeeCigreDllVerificationStatus = verification_status


class _ManufacturerNativeQualificationTrace:
    """Representative outputs separated by the two deterministic behaviors."""

    __slots__ = ("primary", "alternate")

    def __init__(self,
                 primary: Tuple[Tuple[int | float, ...], ...] | None,
                 alternate: Tuple[Tuple[int | float, ...], ...] | None) -> None:
        """Store one bounded qualification trace.

        :param primary: Outputs for the primary input behavior when present.
        :param alternate: Outputs for the alternate input behavior when present.
        :return: None.
        """
        self.primary: Tuple[Tuple[int | float, ...], ...] | None = primary
        self.alternate: Tuple[Tuple[int | float, ...], ...] | None = alternate

def _host_platform() -> IeeeCigreDllPlatform:
    """Return the exact qualified platform of this Python process.

    :return: Windows x64 or Linux x64 platform identifier.
    """
    if struct.calcsize("P") != 8:
        raise RuntimeError("IEEE/CIGRE x86 execution requires a future native 32-bit worker")
    else:
        pass
    if sys.platform == "win32":
        return IeeeCigreDllPlatform.WINDOWS_X64
    elif sys.platform.startswith("linux"):
        return IeeeCigreDllPlatform.LINUX_X64
    else:
        raise RuntimeError("IEEE/CIGRE runtime supports only Windows x64 and Linux x64")


def _file_sha256(path: Path, maximum_bytes: int) -> tuple[str, int]:
    """Hash one bounded regular file through the same open handle.

    :param path: Manufacturer binary path.
    :param maximum_bytes: Maximum accepted byte size.
    :return: Lowercase SHA-256 and exact byte count.
    """
    digest = hashlib.sha256()
    byte_count: int = 0
    with path.open("rb") as stream:
        reading: bool = True
        while reading:
            chunk: bytes = stream.read(1024 * 1024)
            if len(chunk) == 0:
                reading = False
            else:
                byte_count += len(chunk)
                if byte_count > maximum_bytes:
                    raise ValueError("Manufacturer native binary exceeds the inspection limit")
                else:
                    digest.update(chunk)
    return digest.hexdigest(), byte_count


def _qualification_inputs(model_info: ManufacturerNativeModelInfo,
                          alternate: bool) -> Tuple[int | float, ...]:
    """Build one finite representative input trace from declared signal types.

    :param model_info: Validated model metadata.
    :param alternate: Select the distinct B trace when true.
    :return: Complete flattened numeric input tuple.
    """
    values: list[int | float] = list()
    signal = None
    for signal in model_info.input_ports:
        element_index: int
        for element_index in range(signal.width):
            if signal.data_type in (IeeeCigreDllDataType.REAL32, IeeeCigreDllDataType.REAL64):
                values.append(1.0 if alternate else 0.0)
            else:
                values.append(1 if alternate else 0)
    return tuple(values)


def _qualification_overrides(model_info: ManufacturerNativeModelInfo,
                             alternate: bool) -> Tuple[Tuple[int, int, bool, int | float | str], ...]:
    """Build representative valid parameter sets for isolation traces.

    :param model_info: Validated model metadata.
    :param alternate: Select a distinct in-range value where available.
    :return: Complete sparse typed override tuple.
    """
    overrides: list[Tuple[int, int, bool, int | float | str]] = list()
    parameter_index: int
    parameter = None
    for parameter_index, parameter in enumerate(model_info.parameters):
        value: int | float | str = parameter.default_value
        if alternate and parameter.data_type != IeeeCigreDllDataType.C_STRING:
            if parameter.maximum_value is not None and parameter.maximum_value != parameter.default_value:
                value = parameter.maximum_value
            else:
                if parameter.minimum_value is not None and parameter.minimum_value != parameter.default_value:
                    value = parameter.minimum_value
                else:
                    pass
        else:
            pass
        overrides.append((
            parameter_index,
            int(parameter.data_type.value),
            parameter.fixed_value,
            value,
        ))
    return tuple(overrides)


def _mode_for_qualification(model_info: ManufacturerNativeModelInfo) -> IeeeCigreDllModelMode:
    """Choose one exact supported execution domain for qualification.

    :param model_info: Validated model metadata.
    :return: RMS when supported, otherwise EMT.
    """
    if model_info.model_mode in (IeeeCigreDllModelMode.RMS, IeeeCigreDllModelMode.EMT_AND_RMS):
        return IeeeCigreDllModelMode.RMS
    else:
        if model_info.model_mode == IeeeCigreDllModelMode.EMT:
            return IeeeCigreDllModelMode.EMT
        else:
            raise ValueError("IEEE/CIGRE model declares no supported execution domain")


def _qualification_trace(
        source: ManufacturerNativeBinarySource,
        variant: ManufacturerNativeBinaryVariant,
        canonical_bytes: bytes,
        model_info: ManufacturerNativeModelInfo,
        limits: NativeWorkerLimits,
        alternate_order: Tuple[bool, ...],
        worker_artifact: ManufacturerNativeWorkerArtifact | None = None) -> _ManufacturerNativeQualificationTrace:
    """Run one fresh representative multi-instance ordering trace.

    :param source: Stable manufacturer binary locator.
    :param variant: Exact content identity.
    :param canonical_bytes: Expected metadata bytes.
    :param model_info: Validated typed metadata.
    :param limits: Finite staging and process limits.
    :param alternate_order: Primary or alternate behavior in execution order.
    :param worker_artifact: Exact verified worker used for this inspection when supplied.
    :return: Explicit primary and alternate output traces.
    """
    logger: Logger = Logger()
    host: ManufacturerNativeWorkerHost = prepare_manufacturer_native_worker_host(
        source=source,
        variant=variant,
        canonical_model_info=canonical_bytes,
        limits=limits,
        logger=logger,
        worker_artifact=worker_artifact,
    )
    try:
        mode: IeeeCigreDllModelMode = _mode_for_qualification(model_info)
        specifications: list[tuple[
            str,
            IeeeCigreDllModelMode,
            Tuple[int | float, ...],
            Tuple[Tuple[int, int, bool, int | float | str], ...],
        ]] = list()
        identities: list[tuple[str, bool]] = list()
        order_index: int
        alternate: bool
        for order_index, alternate in enumerate(alternate_order):
            behavior_name: str = "B" if alternate else "A"
            instance_id: str = f"{order_index:02d}:{behavior_name}"
            identities.append((instance_id, alternate))
            specifications.append((
                instance_id,
                mode,
                _qualification_inputs(model_info, alternate),
                _qualification_overrides(model_info, alternate),
            ))
        initialized: Tuple[Tuple[str, Tuple[int | float, ...]], ...] = (
            host.initialize_instances(tuple(specifications))
        )
        primary_values: list[Tuple[int | float, ...]] | None = None
        alternate_values: list[Tuple[int | float, ...]] | None = None
        result_index: int
        result_id: str
        outputs: Tuple[int | float, ...]
        for result_index, (result_id, outputs) in enumerate(initialized):
            expected_id: str = identities[result_index][0]
            alternate = identities[result_index][1]
            if result_id != expected_id:
                raise ValueError("IEEE/CIGRE qualification response order changed")
            elif alternate:
                alternate_values = [outputs]
            else:
                primary_values = [outputs]
        sample_index: int
        for sample_index in range(1, 4):
            requested: list[tuple[str, Tuple[int | float, ...]]] = list()
            instance_id = ""
            for instance_id, alternate in identities:
                requested.append((
                    instance_id,
                    _qualification_inputs(model_info, alternate),
                ))
            sampled: Tuple[Tuple[str, Tuple[int | float, ...]], ...] = (
                host.sample_batch(
                    sample_time=(
                        float(sample_index)
                        * model_info.fixed_step_base_sample_time
                    ),
                    samples=tuple(requested),
                )
            )
            for result_index, (result_id, outputs) in enumerate(sampled):
                expected_id = identities[result_index][0]
                alternate = identities[result_index][1]
                if result_id != expected_id:
                    raise ValueError("IEEE/CIGRE qualification sample order changed")
                elif alternate:
                    if alternate_values is None:
                        raise ValueError("Alternate qualification trace was not initialized")
                    else:
                        alternate_values.append(outputs)
                else:
                    if primary_values is None:
                        raise ValueError("Primary qualification trace was not initialized")
                    else:
                        primary_values.append(outputs)
        primary: Tuple[Tuple[int | float, ...], ...] | None = (
            None if primary_values is None else tuple(primary_values)
        )
        alternate_trace: Tuple[Tuple[int | float, ...], ...] | None = (
            None if alternate_values is None else tuple(alternate_values)
        )
        return _ManufacturerNativeQualificationTrace(
            primary=primary,
            alternate=alternate_trace,
        )
    finally:
        host.close()


def _qualify_instance_isolation(source: ManufacturerNativeBinarySource,
                                variant: ManufacturerNativeBinaryVariant,
                                canonical_bytes: bytes,
                                model_info: ManufacturerNativeModelInfo,
                                limits: NativeWorkerLimits,
                                worker_artifact: ManufacturerNativeWorkerArtifact) -> None:
    """Compare primary, alternate and interleaved instance traces.

    :param source: Stable manufacturer binary locator.
    :param variant: Exact content identity.
    :param canonical_bytes: Expected metadata bytes.
    :param model_info: Validated typed metadata.
    :param limits: Finite staging and process limits.
    :param worker_artifact: Exact verified worker used for all traces.
    :return: None after every representative trace matches.
    """
    trace_primary: _ManufacturerNativeQualificationTrace = _qualification_trace(
        source, variant, canonical_bytes, model_info, limits, (False,), worker_artifact
    )
    trace_alternate: _ManufacturerNativeQualificationTrace = _qualification_trace(
        source, variant, canonical_bytes, model_info, limits, (True,), worker_artifact
    )
    trace_primary_alternate: _ManufacturerNativeQualificationTrace = (
        _qualification_trace(
            source, variant, canonical_bytes, model_info, limits, (False, True), worker_artifact
        )
    )
    trace_alternate_primary: _ManufacturerNativeQualificationTrace = (
        _qualification_trace(
            source, variant, canonical_bytes, model_info, limits, (True, False), worker_artifact
        )
    )
    if (trace_primary.primary is None
            or trace_primary.primary != trace_primary_alternate.primary
            or trace_primary.primary != trace_alternate_primary.primary):
        raise ValueError(
            "Manufacturer model failed primary instance-isolation qualification"
        )
    else:
        pass
    if (trace_alternate.alternate is None
            or trace_alternate.alternate != trace_primary_alternate.alternate
            or trace_alternate.alternate != trace_alternate_primary.alternate):
        raise ValueError(
            "Manufacturer model failed alternate instance-isolation qualification"
        )
    else:
        pass

def inspect_manufacturer_native(source_path: str | Path,
                           platform: IeeeCigreDllPlatform,
                           native_interface: NativeModelInterface,
                           vendor_declares_no_late_loading: bool,
                           vendor_declares_instance_isolation: bool,
                           limits: ManufacturerNativeInspectionLimits | None = None,
                            worker_artifact: ManufacturerNativeWorkerArtifact | None = None,
                            compiler_selection: NativeCompilerSelection | None = None) -> ManufacturerNativeInspectionResult:
    """Statically validate then inspect a host-compatible manufacturer library in a child.

    :param source_path: Manufacturer-supplied precompiled DLL or shared object.
    :param platform: Exact declared operating-system and architecture target.
    :param native_interface: Exact manufacturer ABI selected by the user.
    :param vendor_declares_no_late_loading: Vendor attestation required by dependency policy.
    :param vendor_declares_instance_isolation: Vendor attestation required for shared workers.
    :param limits: Optional finite inspection limits.
    :param worker_artifact: Exact prepared worker selected by the caller.
    :param compiler_selection: Explicit LLVM snapshot used when resolving a worker.
    :return: Complete pre-mutation inspection evidence.
    """
    if not vendor_declares_no_late_loading:
        raise ValueError("Vendor must declare that the model performs no late non-OS dynamic loading")
    else:
        pass
    if native_interface == NativeModelInterface.IEEE_CIGRE_V1_1:
        if not vendor_declares_instance_isolation:
            raise ValueError("Vendor must declare that mutable behavior is isolated by Instance")
        else:
            pass
    elif native_interface in (NativeModelInterface.IEEE_CIGRE_V1_0, NativeModelInterface.IEC_ESE):
        pass
    else:
        raise ValueError("Manufacturer native interface is unsupported")
    selected_limits: ManufacturerNativeInspectionLimits = (
        ManufacturerNativeInspectionLimits() if limits is None else limits
    )
    path: Path = Path(source_path).resolve()
    binary_size: int
    dependencies: Tuple[str, ...]
    binary_size, dependencies = _inspect_native_binary(
        path=path,
        platform=platform,
        maximum_size=selected_limits.worker_limits.maximum_binary_bytes,
    )
    binary_sha256: str
    hashed_size: int
    binary_sha256, hashed_size = _file_sha256(path, selected_limits.worker_limits.maximum_binary_bytes)
    if hashed_size != binary_size:
        raise ValueError("Manufacturer native binary changed during static inspection")
    else:
        pass
    host_platform: IeeeCigreDllPlatform = _host_platform()
    x86_on_windows_x64: bool = (
        platform == IeeeCigreDllPlatform.WINDOWS_X86
        and host_platform == IeeeCigreDllPlatform.WINDOWS_X64
    )
    if platform != host_platform and not x86_on_windows_x64:
        raise ValueError("Native inspection must run on a host matching the binary platform")
    else:
        pass
    extension: str = (
        ".dll"
        if platform in (IeeeCigreDllPlatform.WINDOWS_X86, IeeeCigreDllPlatform.WINDOWS_X64)
        else ".so"
    )
    member: str = (
        "native_models/manufacturer/by_sha256/"
        + binary_sha256
        + extension
    )
    variant: ManufacturerNativeBinaryVariant = ManufacturerNativeBinaryVariant(
        platform=platform,
        extension=extension,
        content_sha256=binary_sha256,
        byte_size=binary_size,
        zip_member=member,
        verification_status=IeeeCigreDllVerificationStatus.UNVERIFIED,
    )
    source: ManufacturerNativeBinarySource = ManufacturerNativeBinarySource(
        platform=platform,
        file_path=str(path),
    )
    if worker_artifact is not None and compiler_selection is not None:
        raise ValueError("Specify either a prepared worker or a compiler selection")
    else:
        pass
    if worker_artifact is not None:
        artifact: ManufacturerNativeWorkerArtifact = worker_artifact
    else:
        # Resolve the exact compiler snapshot for either worker architecture
        # before staging vendor bytes; a changed saved profile is ignored.
        artifact = resolve_manufacturer_native_worker(
            selection=compiler_selection,
            prepare_if_missing=True,
            platform=platform,
        )
    if artifact.platform != platform:
        raise ValueError("Prepared manufacturer worker platform differs from the selected binary")
    else:
        staging = stage_native_library(source, variant, selected_limits.worker_limits)
    owner: ExternalNativeWorkerProcessOwner = ExternalNativeWorkerProcessOwner(
        staging,
        selected_limits.worker_limits,
    )
    staged_path: str = str(staging.get_library_path())
    worker_identity: bytes = bytes.fromhex(artifact.content_sha256)
    system_identity: Tuple[int, bytes, str] = (
        artifact.system_volume_serial,
        artifact.system_file_id,
        artifact.system_directory,
    )
    try:
        owner.start(artifact.executable_path)
        request_frame: bytes = encode_manufacturer_native_worker_request(
            command=ManufacturerNativeWorkerRequest(
                opcode=ManufacturerNativeWorkerOpcode.INSPECT
            ),
            request_id=1,
            staged_path=staged_path,
            variant=variant,
            native_interface=native_interface,
            worker_identity=worker_identity,
            system_identity=system_identity,
            canonical_model_info=bytes(),
            limits=selected_limits.worker_limits,
            raw_model_info_sha256=bytes(),
        )
        response: ManufacturerNativeWorkerResponse = (
            decode_manufacturer_native_worker_response(
                owner.request(
                    request_frame,
                    timeout_seconds=selected_limits.inspection_timeout_seconds,
                )
            )
        )
        if (response.request_id != 1
                or response.opcode != ManufacturerNativeWorkerOpcode.INSPECT):
            raise ValueError("Native worker inspection response identity differs")
        elif response.status != ManufacturerNativeWorkerStatus.OK:
            raise ValueError(
                "Native worker rejected manufacturer inspection: "
                + response.status.name
                + ": "
                + response.diagnostic
            )
        elif response.worker_sha256 != worker_identity:
            raise ValueError("Native worker response identity differs from the selected artifact")
        else:
            pass
        close_frame: bytes = encode_manufacturer_native_worker_request(
            command=ManufacturerNativeWorkerRequest(
                opcode=ManufacturerNativeWorkerOpcode.CLOSE
            ),
            request_id=2,
            staged_path=staged_path,
            variant=variant,
            native_interface=native_interface,
            worker_identity=worker_identity,
            system_identity=system_identity,
            canonical_model_info=bytes(),
            limits=selected_limits.worker_limits,
            raw_model_info_sha256=response.raw_model_info_sha256,
        )
        close_response: ManufacturerNativeWorkerResponse = (
            decode_manufacturer_native_worker_response(owner.request(close_frame))
        )
        if (close_response.request_id == 2
                and close_response.opcode == ManufacturerNativeWorkerOpcode.CLOSE
                and close_response.status == ManufacturerNativeWorkerStatus.OK):
            pass
        else:
            raise RuntimeError("Manufacturer inspection worker did not close cleanly")
    finally:
        owner.close()
    canonical_bytes: bytes = response.canonical_model_info
    if len(canonical_bytes) == 0:
        raise ValueError("IEEE/CIGRE worker returned empty canonical metadata")
    else:
        model_info: ManufacturerNativeModelInfo = (
            decode_manufacturer_native_model_info(canonical_bytes)
        )
    qualified_variant: ManufacturerNativeBinaryVariant = ManufacturerNativeBinaryVariant(
        platform=platform,
        extension=extension,
        content_sha256=binary_sha256,
        byte_size=binary_size,
        zip_member=member,
        verification_status=IeeeCigreDllVerificationStatus.DECLARED_AND_QUALIFIED,
    )
    if native_interface == NativeModelInterface.IEEE_CIGRE_V1_1:
        _qualify_instance_isolation(
            source=source,
            variant=qualified_variant,
            canonical_bytes=canonical_bytes,
            model_info=model_info,
            limits=selected_limits.worker_limits,
            worker_artifact=artifact,
        )
    else:
        # Legacy and IEC ESE execute one instance per process, so a single
        # lifecycle smoke test verifies the ABI without assuming shared globals.
        _qualification_trace(
            source,
            qualified_variant,
            canonical_bytes,
            model_info,
            selected_limits.worker_limits,
            (False,),
            artifact,
        )
    return ManufacturerNativeInspectionResult(
        platform=platform,
        binary_sha256=binary_sha256,
        binary_size=binary_size,
        dependencies=dependencies,
        model_info=model_info,
        canonical_model_info=canonical_bytes,
        model_info_sha256=digest_manufacturer_native_model_info(model_info),
        verification_status=IeeeCigreDllVerificationStatus.DECLARED_AND_QUALIFIED,
    )
