# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import math
from pathlib import Path
from typing import Tuple

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import (
    ManufacturerNativeBinarySource,
    ManufacturerNativeBinaryVariant,
)
from VeraGridEngine.enumerations import (
    IeeeCigreDllModelMode,
    IeeeCigreDllPlatform,
    NativeModelInterface,
)
from VeraGridEngine.IO.manufacturer_native.abi_common import check_manufacturer_native_return
from VeraGridEngine.IO.manufacturer_native.model_info_codec import decode_manufacturer_native_model_info
from VeraGridEngine.IO.manufacturer_native.worker_artifact import (
    ManufacturerNativeWorkerArtifact,
    resolve_manufacturer_native_worker,
)
from VeraGridEngine.IO.manufacturer_native.worker_protocol import (
    ManufacturerNativeWorkerCallOperation,
    ManufacturerNativeWorkerCallResult,
    ManufacturerNativeWorkerInstanceRequest,
    ManufacturerNativeWorkerInstanceResult,
    ManufacturerNativeWorkerOpcode,
    ManufacturerNativeWorkerRequest,
    ManufacturerNativeWorkerResponse,
    ManufacturerNativeWorkerStatus,
    decode_manufacturer_native_worker_response,
    encode_manufacturer_native_worker_request,
    manufacturer_native_worker_call_name,
)
from VeraGridEngine.IO.native_runtime import (
    ExternalNativeWorkerProcessOwner,
    NativeWorkerLimits,
    stage_native_library,
)


class ManufacturerNativeWorkerHost:
    """Parent-side owner of one content-bound manufacturer worker."""

    __slots__ = (
        "_owner", "_variant", "_canonical_model_info", "_limits", "_logger",
        "_started", "_closed", "_initialized_ids", "_worker_executable_path",
        "_worker_identity", "_system_identity", "_staged_path",
        "_request_id", "_raw_model_info_sha256", "_native_interface",
    )

    def __init__(self,
                 owner: ExternalNativeWorkerProcessOwner,
                 worker_executable_path: Path,
                 worker_identity: bytes,
                 system_identity: Tuple[int, bytes, str],
                 staged_path: str,
                 variant: ManufacturerNativeBinaryVariant,
                 canonical_model_info: bytes,
                 limits: NativeWorkerLimits,
                 logger: Logger) -> None:
        """Adopt one staged process owner before loading native code.

        :param owner: Sole process and staging owner.
        :param worker_executable_path: Verified worker executable path.
        :param worker_identity: Verified worker SHA-256 bytes.
        :param system_identity: Approved operating-system library directory identity.
        :param staged_path: Absolute staged manufacturer library path.
        :param variant: Exact persistent platform binary identity.
        :param canonical_model_info: Persisted canonical metadata bytes.
        :param limits: Shared finite transport and allocation limits.
        :param logger: Simulation diagnostic logger.
        :return: None.
        """
        if len(canonical_model_info) == 0:
            raise ValueError("Manufacturer expected ModelInfo cannot be empty")
        elif len(worker_identity) != 32 or len(system_identity[1]) != 16:
            raise ValueError("Manufacturer worker or system identity is invalid")
        else:
            pass
        self._owner: ExternalNativeWorkerProcessOwner = owner
        self._worker_executable_path: Path = worker_executable_path
        self._worker_identity: bytes = worker_identity
        self._system_identity: Tuple[int, bytes, str] = system_identity
        self._staged_path: str = staged_path
        self._variant: ManufacturerNativeBinaryVariant = variant
        self._canonical_model_info: bytes = canonical_model_info
        self._limits: NativeWorkerLimits = limits
        self._logger: Logger = logger
        self._started: bool = False
        self._closed: bool = False
        self._initialized_ids: set[str] = set()
        self._request_id: int = 1
        self._raw_model_info_sha256: bytes = bytes()
        self._native_interface: NativeModelInterface = (
            decode_manufacturer_native_model_info(canonical_model_info).native_interface
        )

    def _request(self,
                 command: ManufacturerNativeWorkerRequest,
                 timeout_seconds: float) -> ManufacturerNativeWorkerResponse:
        """Exchange one bounded typed command with the native worker.

        :param command: Exact semantic request.
        :param timeout_seconds: Finite response deadline.
        :return: Successful typed response.
        """
        frame: bytes = encode_manufacturer_native_worker_request(
            command=command,
            request_id=self._request_id,
            staged_path=self._staged_path,
            variant=self._variant,
            native_interface=self._native_interface,
            worker_identity=self._worker_identity,
            system_identity=self._system_identity,
            canonical_model_info=self._canonical_model_info,
            limits=self._limits,
            raw_model_info_sha256=self._raw_model_info_sha256,
        )
        raw: bytes = self._owner.request(frame, timeout_seconds=timeout_seconds)
        response: ManufacturerNativeWorkerResponse = (
            decode_manufacturer_native_worker_response(raw)
        )
        if response.request_id != self._request_id or response.opcode != command.opcode:
            raise ValueError("Manufacturer native worker response identity differs")
        else:
            self._request_id = (
                1 if self._request_id == 0xffffffff else self._request_id + 1
            )
        if response.status != ManufacturerNativeWorkerStatus.OK:
            raise RuntimeError(
                "Manufacturer worker rejected command: "
                + response.status.name
                + ": "
                + response.diagnostic
            )
        else:
            if len(response.raw_model_info_sha256) == 32:
                self._raw_model_info_sha256 = response.raw_model_info_sha256
            else:
                pass
            return response

    def _check_call(self, result: ManufacturerNativeWorkerCallResult) -> None:
        """Apply the normalized return policy to one typed worker call.

        :param result: Native call outcome returned by the worker.
        :return: None.
        """
        operation_name: str = manufacturer_native_worker_call_name(result.operation)
        accepted: bool = check_manufacturer_native_return(
            return_code=result.return_code,
            operation=operation_name,
            last_error_message=result.error_message,
            last_general_message=result.general_message,
            logger=self._logger,
            cleanup=(
                result.operation == ManufacturerNativeWorkerCallOperation.TERMINATE
            ),
        )
        if (not accepted
                and result.operation != ManufacturerNativeWorkerCallOperation.TERMINATE):
            raise RuntimeError(operation_name + " failed in manufacturer library")
        else:
            pass

    def start(self) -> None:
        """Load the exact binary and verify persisted metadata before use.

        :return: None.
        """
        if self._started or self._closed:
            raise RuntimeError("Manufacturer worker start can occur exactly once")
        else:
            pass
        self._owner.start(self._worker_executable_path)
        self._started = True
        inspected: ManufacturerNativeWorkerResponse = self._request(
            ManufacturerNativeWorkerRequest(
                opcode=ManufacturerNativeWorkerOpcode.INSPECT
            ),
            self._limits.response_timeout_seconds,
        )
        if inspected.worker_sha256 != self._worker_identity:
            raise ValueError("Manufacturer runtime worker identity differs from its manifest")
        elif inspected.canonical_model_info != self._canonical_model_info:
            raise ValueError("Manufacturer runtime metadata differs from stored provider bytes")
        else:
            pass
        if len(inspected.resident_module_limitation) > 0:
            self._logger.add_warning(
                "Manufacturer resident module guard",
                comment=inspected.resident_module_limitation,
            )
        else:
            pass
        prepared: ManufacturerNativeWorkerResponse = self._request(
            ManufacturerNativeWorkerRequest(
                opcode=ManufacturerNativeWorkerOpcode.PREPARE
            ),
            self._limits.response_timeout_seconds,
        )
        message: str = prepared.stdout + prepared.stderr
        if prepared.stdout_truncated or prepared.stderr_truncated:
            self._logger.add_warning("Model_PrintInfo output was truncated")
        else:
            pass
        if prepared.return_code == 0:
            if len(message) > 0:
                self._logger.add_info("Model_PrintInfo", comment=message)
            else:
                pass
        else:
            accepted: bool = check_manufacturer_native_return(
                return_code=prepared.return_code,
                operation="Model_PrintInfo",
                last_error_message=message,
                last_general_message=message,
                logger=self._logger,
            )
            if not accepted:
                raise RuntimeError("Model_PrintInfo failed in manufacturer library")
            else:
                pass

    def initialize_instances(self,
                             specifications: Tuple[
                                 Tuple[
                                     str,
                                     IeeeCigreDllModelMode,
                                     Tuple[int | float, ...],
                                     Tuple[Tuple[int, int, bool, int | float | str], ...],
                                 ], ...
                             ]) -> Tuple[Tuple[str, Tuple[int | float, ...]], ...]:
        """Initialize one sorted batch and return its held outputs.

        :param specifications: IDs, domains, inputs and parameter overrides.
        :return: Matching instance IDs and initial outputs.
        """
        if not self._started or self._closed:
            raise RuntimeError("Manufacturer worker is not active")
        else:
            rows: list[ManufacturerNativeWorkerInstanceRequest] = list()
        previous_id: str = ""
        instance_id: str
        model_mode: IeeeCigreDllModelMode
        inputs: Tuple[int | float, ...]
        overrides: Tuple[Tuple[int, int, bool, int | float | str], ...]
        for instance_id, model_mode, inputs, overrides in specifications:
            if instance_id <= previous_id or instance_id in self._initialized_ids:
                raise ValueError("Manufacturer instance IDs must be unique and sorted")
            else:
                previous_id = instance_id
                rows.append(ManufacturerNativeWorkerInstanceRequest(
                    instance_id=instance_id,
                    model_mode=model_mode,
                    inputs=inputs,
                    overrides=overrides,
                ))
        response: ManufacturerNativeWorkerResponse = self._request(
            ManufacturerNativeWorkerRequest(
                opcode=ManufacturerNativeWorkerOpcode.INITIALIZE,
                instances=tuple(rows),
            ),
            self._limits.response_timeout_seconds,
        )
        if len(response.instances) != len(specifications):
            raise ValueError("Manufacturer initialization response cardinality differs")
        else:
            results: list[Tuple[str, Tuple[int | float, ...]]] = list()
        row_index: int
        for row_index in range(len(response.instances)):
            response_row: ManufacturerNativeWorkerInstanceResult = (
                response.instances[row_index]
            )
            expected_id: str = specifications[row_index][0]
            if response_row.instance_id != expected_id:
                raise ValueError("Manufacturer initialization response identity differs")
            else:
                call: ManufacturerNativeWorkerCallResult
                for call in response_row.calls:
                    self._check_call(call)
            results.append((expected_id, response_row.outputs))
            self._initialized_ids.add(expected_id)
        return tuple(results)

    def sample_batch(self,
                     sample_time: float,
                     samples: Tuple[Tuple[str, Tuple[int | float, ...]], ...]) -> Tuple[
                         Tuple[str, Tuple[int | float, ...]], ...
                     ]:
        """Execute one sorted accepted-boundary sample batch.

        :param sample_time: Exact positive accepted boundary time.
        :param samples: Instance IDs and complete input vectors.
        :return: Matching IDs and held output vectors.
        """
        if (not self._started or self._closed
                or not math.isfinite(sample_time) or sample_time <= 0.0):
            raise RuntimeError("Manufacturer sample order or time is invalid")
        else:
            rows: list[ManufacturerNativeWorkerInstanceRequest] = list()
        previous_id: str = ""
        instance_id: str
        inputs: Tuple[int | float, ...]
        for instance_id, inputs in samples:
            if instance_id <= previous_id or instance_id not in self._initialized_ids:
                raise ValueError("Manufacturer sample IDs must be initialized and sorted")
            else:
                previous_id = instance_id
                rows.append(ManufacturerNativeWorkerInstanceRequest(
                    instance_id=instance_id,
                    model_mode=None,
                    inputs=inputs,
                    overrides=tuple(),
                ))
        response: ManufacturerNativeWorkerResponse = self._request(
            ManufacturerNativeWorkerRequest(
                opcode=ManufacturerNativeWorkerOpcode.SAMPLE,
                instances=tuple(rows),
                sample_time=sample_time,
            ),
            self._limits.response_timeout_seconds,
        )
        if len(response.instances) != len(samples):
            raise ValueError("Manufacturer sample response cardinality differs")
        else:
            results: list[Tuple[str, Tuple[int | float, ...]]] = list()
        row_index: int
        for row_index in range(len(response.instances)):
            response_row: ManufacturerNativeWorkerInstanceResult = (
                response.instances[row_index]
            )
            expected_id: str = samples[row_index][0]
            if response_row.instance_id != expected_id or len(response_row.calls) != 1:
                raise ValueError("Manufacturer sample response identity or calls differ")
            else:
                self._check_call(response_row.calls[0])
                results.append((expected_id, response_row.outputs))
        return tuple(results)

    def close(self) -> None:
        """Request cooperative cleanup and always release process ownership.

        :return: None.
        """
        if self._closed:
            return
        else:
            self._closed = True
        first_error: BaseException | None = None
        if self._started:
            try:
                response: ManufacturerNativeWorkerResponse = self._request(
                    ManufacturerNativeWorkerRequest(
                        opcode=ManufacturerNativeWorkerOpcode.CLOSE
                    ),
                    self._limits.response_timeout_seconds,
                )
                row: ManufacturerNativeWorkerInstanceResult
                for row in response.terminated:
                    if len(row.calls) != 1:
                        raise ValueError(
                            "Manufacturer termination response call count differs"
                        )
                    else:
                        self._check_call(row.calls[0])
            except BaseException as ex:
                first_error = ex
        else:
            pass
        try:
            self._owner.close()
        except BaseException as ex:
            if first_error is None:
                first_error = ex
            else:
                pass
        if first_error is not None:
            raise RuntimeError("Manufacturer worker could not close cleanly") from first_error
        else:
            pass

def prepare_manufacturer_native_worker_host(source: ManufacturerNativeBinarySource,
                                             variant: ManufacturerNativeBinaryVariant,
                                             canonical_model_info: bytes,
                                             limits: NativeWorkerLimits,
                                             logger: Logger,
                                             worker_artifact: ManufacturerNativeWorkerArtifact | None = None) -> ManufacturerNativeWorkerHost:
    """Verify the host worker, stage exact vendor bytes and start one owner.

    Worker verification deliberately precedes manufacturer staging so a missing
    or stale artifact cannot copy user supplied native code into a runtime area.

    :param source: File or archive member containing the selected platform bytes.
    :param variant: Exact persistent platform binary identity.
    :param canonical_model_info: Stored canonical metadata bytes.
    :param limits: Shared finite transport and allocation limits.
    :param logger: Simulation diagnostics.
    :param worker_artifact: Exact previously verified host worker, when supplied.
    :return: Started worker host after ABI and metadata checks.
    """
    if worker_artifact is not None:
        artifact: ManufacturerNativeWorkerArtifact = worker_artifact
    else:
        artifact = resolve_manufacturer_native_worker(
            prepare_if_missing=True,
            platform=variant.platform,
        )
    if artifact.platform != variant.platform:
        raise ValueError("Prepared manufacturer worker platform differs from the selected binary")
    else:
        staging = stage_native_library(source, variant, limits)
    owner: ExternalNativeWorkerProcessOwner = ExternalNativeWorkerProcessOwner(staging, limits)
    worker_executable_path: Path = artifact.executable_path
    staged_path: str = str(staging.get_library_path())
    worker_identity: bytes = bytes.fromhex(artifact.content_sha256)
    system_identity: Tuple[int, bytes, str] = (
        artifact.system_volume_serial,
        artifact.system_file_id,
        artifact.system_directory,
    )
    worker_host: ManufacturerNativeWorkerHost = ManufacturerNativeWorkerHost(
        owner=owner,
        worker_executable_path=worker_executable_path,
        worker_identity=worker_identity,
        system_identity=system_identity,
        staged_path=staged_path,
        variant=variant,
        canonical_model_info=canonical_model_info,
        limits=limits,
        logger=logger,
    )
    try:
        worker_host.start()
    except BaseException:
        worker_host.close()
        raise
    return worker_host
