# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from enum import IntEnum
import hashlib
import io
import math
import struct
from typing import Tuple

from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import ManufacturerNativeBinaryVariant
from VeraGridEngine.enumerations import (
    IeeeCigreDllDataType,
    IeeeCigreDllModelMode,
    NativeModelInterface,
    NativeSampleTimeSource,
)
from VeraGridEngine.IO.manufacturer_native.model_info import ManufacturerNativeModelInfo, ManufacturerNativeParameterInfo, ManufacturerNativeSignalInfo
from VeraGridEngine.IO.manufacturer_native.model_info_codec import decode_manufacturer_native_model_info, encode_manufacturer_native_model_info
from VeraGridEngine.IO.native_runtime import NativeWorkerLimits


class ManufacturerNativeWorkerOpcode(IntEnum):
    """Protocol opcode values shared with the prepared native worker."""

    INSPECT = 1
    PREPARE = 2
    INITIALIZE = 3
    SAMPLE = 4
    CLOSE = 5


class ManufacturerNativeWorkerMessageKind(IntEnum):
    """Protocol message kinds shared with the prepared native worker."""

    REQUEST = 1
    RESPONSE = 2


class ManufacturerNativeWorkerStatus(IntEnum):
    """Protocol status values shared with the prepared native worker."""

    OK = 0
    BAD_MAGIC = 1
    BAD_VERSION = 2
    BAD_KIND = 3
    BAD_OPCODE = 4
    BAD_REQUEST_ID = 5
    BAD_LENGTH = 6
    BAD_PAYLOAD = 7
    BAD_STATE = 8
    ABI_FAILURE = 9
    DEPENDENCY_FAILURE = 10
    CONTENT_IDENTITY_FAILURE = 11


class ManufacturerNativeWorkerCallOperation(IntEnum):
    """Raw ABI call identifiers returned by the prepared native worker."""

    FIRST_CALL = 1
    CHECK_PARAMETERS = 2
    INITIALIZE = 3
    OUTPUTS = 4
    TERMINATE = 5


class ManufacturerNativeWorkerInstanceRequest:
    """One explicitly typed instance row sent to the native worker."""

    __slots__ = ("instance_id", "model_mode", "inputs", "overrides")

    def __init__(self,
                 instance_id: str,
                 model_mode: IeeeCigreDllModelMode | None,
                 inputs: Tuple[int | float, ...],
                 overrides: Tuple[Tuple[int, int, bool, int | float | str], ...]) -> None:
        """Store one immutable request row.

        :param instance_id: Sorted unique runtime instance identifier.
        :param model_mode: EMT or RMS for initialization, otherwise None.
        :param inputs: Complete flattened input vector.
        :param overrides: Complete typed initialization overrides.
        :return: None.
        """
        self.instance_id: str = instance_id
        self.model_mode: IeeeCigreDllModelMode | None = model_mode
        self.inputs: Tuple[int | float, ...] = inputs
        self.overrides: Tuple[Tuple[int, int, bool, int | float | str], ...] = overrides


class ManufacturerNativeWorkerRequest:
    """One semantic request with an explicit opcode and typed rows."""

    __slots__ = ("opcode", "instances", "sample_time")

    def __init__(self,
                 opcode: ManufacturerNativeWorkerOpcode,
                 instances: Tuple[ManufacturerNativeWorkerInstanceRequest, ...] = tuple(),
                 sample_time: float | None = None) -> None:
        """Create one request after checking its opcode-specific shape.

        :param opcode: Exact worker operation.
        :param instances: Sorted instance rows for initialize or sample.
        :param sample_time: Positive boundary time for sample.
        :return: None.
        """
        if opcode == ManufacturerNativeWorkerOpcode.INITIALIZE:
            if len(instances) == 0 or sample_time is not None:
                raise ValueError("Manufacturer INITIALIZE request shape is invalid")
            else:
                row: ManufacturerNativeWorkerInstanceRequest
                for row in instances:
                    if row.model_mode is None:
                        raise ValueError("Manufacturer initialization row needs a model mode")
                    else:
                        pass
        elif opcode == ManufacturerNativeWorkerOpcode.SAMPLE:
            if len(instances) == 0 or sample_time is None or not math.isfinite(sample_time) or sample_time <= 0.0:
                raise ValueError("Manufacturer SAMPLE request shape is invalid")
            else:
                row: ManufacturerNativeWorkerInstanceRequest
                for row in instances:
                    if row.model_mode is not None or len(row.overrides) != 0:
                        raise ValueError("Manufacturer sample rows cannot contain initialization fields")
                    else:
                        pass
        else:
            if len(instances) != 0 or sample_time is not None:
                raise ValueError("Manufacturer worker control request cannot contain instance rows")
            else:
                pass
        self.opcode: ManufacturerNativeWorkerOpcode = opcode
        self.instances: Tuple[ManufacturerNativeWorkerInstanceRequest, ...] = instances
        self.sample_time: float | None = sample_time


class ManufacturerNativeWorkerCallResult:
    """Typed outcome of one manufacturer ABI call."""

    __slots__ = ("operation", "return_code", "error_message", "general_message")

    def __init__(self,
                 operation: ManufacturerNativeWorkerCallOperation,
                 return_code: int,
                 error_message: str,
                 general_message: str) -> None:
        """Store one validated ABI call result.

        :param operation: Exact ABI operation.
        :param return_code: Manufacturer return code.
        :param error_message: Manufacturer error text captured after the call.
        :param general_message: Manufacturer general text captured after the call.
        :return: None.
        """
        self.operation: ManufacturerNativeWorkerCallOperation = operation
        self.return_code: int = return_code
        self.error_message: str = error_message
        self.general_message: str = general_message


class ManufacturerNativeWorkerInstanceResult:
    """Typed worker result for one runtime instance."""

    __slots__ = ("instance_id", "calls", "outputs")

    def __init__(self,
                 instance_id: str,
                 calls: Tuple[ManufacturerNativeWorkerCallResult, ...],
                 outputs: Tuple[int | float, ...]) -> None:
        """Store one decoded instance result.

        :param instance_id: Runtime instance identifier.
        :param calls: Ordered ABI call outcomes.
        :param outputs: Complete flattened output vector.
        :return: None.
        """
        self.instance_id: str = instance_id
        self.calls: Tuple[ManufacturerNativeWorkerCallResult, ...] = calls
        self.outputs: Tuple[int | float, ...] = outputs


class ManufacturerNativeWorkerResponse:
    """Complete typed response decoded from one native worker frame."""

    __slots__ = (
        "request_id", "opcode", "status", "diagnostic", "worker_sha256",
        "maximum_observations", "imports", "canonical_model_info",
        "raw_model_info_sha256", "resident_module_limitation", "return_code",
        "stdout", "stderr", "stdout_truncated", "stderr_truncated",
        "instances", "terminated",
    )

    def __init__(self,
                 request_id: int,
                 opcode: ManufacturerNativeWorkerOpcode,
                 status: ManufacturerNativeWorkerStatus,
                 diagnostic: str = "",
                 worker_sha256: bytes = bytes(),
                 maximum_observations: int = 0,
                 imports: Tuple[str, ...] = tuple(),
                 canonical_model_info: bytes = bytes(),
                 raw_model_info_sha256: bytes = bytes(),
                 resident_module_limitation: str = "",
                 return_code: int = 0,
                 stdout: str = "",
                 stderr: str = "",
                 stdout_truncated: bool = False,
                 stderr_truncated: bool = False,
                 instances: Tuple[ManufacturerNativeWorkerInstanceResult, ...] = tuple(),
                 terminated: Tuple[ManufacturerNativeWorkerInstanceResult, ...] = tuple()) -> None:
        """Store every opcode-specific response field explicitly.

        :param request_id: Matching nonzero request identifier.
        :param opcode: Exact operation answered by the worker.
        :param status: Worker protocol status.
        :param diagnostic: Worker diagnostic for non-OK status.
        :param worker_sha256: Runtime worker identity from INSPECT.
        :param maximum_observations: Dependency observation bound.
        :param imports: Observed resident import names.
        :param canonical_model_info: Canonical typed metadata bytes.
        :param raw_model_info_sha256: Digest of the raw ABI metadata.
        :param resident_module_limitation: Documented observation limitation.
        :param return_code: Model_PrintInfo return code.
        :param stdout: Normalized captured standard output.
        :param stderr: Normalized captured standard error.
        :param stdout_truncated: Whether stdout exceeded its bound.
        :param stderr_truncated: Whether stderr exceeded its bound.
        :param instances: Initialize or sample results.
        :param terminated: Close results.
        :return: None.
        """
        self.request_id: int = request_id
        self.opcode: ManufacturerNativeWorkerOpcode = opcode
        self.status: ManufacturerNativeWorkerStatus = status
        self.diagnostic: str = diagnostic
        self.worker_sha256: bytes = worker_sha256
        self.maximum_observations: int = maximum_observations
        self.imports: Tuple[str, ...] = imports
        self.canonical_model_info: bytes = canonical_model_info
        self.raw_model_info_sha256: bytes = raw_model_info_sha256
        self.resident_module_limitation: str = resident_module_limitation
        self.return_code: int = return_code
        self.stdout: str = stdout
        self.stderr: str = stderr
        self.stdout_truncated: bool = stdout_truncated
        self.stderr_truncated: bool = stderr_truncated
        self.instances: Tuple[ManufacturerNativeWorkerInstanceResult, ...] = instances
        self.terminated: Tuple[ManufacturerNativeWorkerInstanceResult, ...] = terminated


def manufacturer_native_worker_call_name(
        operation: ManufacturerNativeWorkerCallOperation) -> str:
    """Return the IEEE/CIGRE function name for one protocol call operation.

    :param operation: Exact protocol call operation.
    :return: Stable manufacturer ABI function name.
    """
    if operation == ManufacturerNativeWorkerCallOperation.FIRST_CALL:
        return "Model_FirstCall"
    elif operation == ManufacturerNativeWorkerCallOperation.CHECK_PARAMETERS:
        return "Model_CheckParameters"
    elif operation == ManufacturerNativeWorkerCallOperation.INITIALIZE:
        return "Model_Initialize"
    elif operation == ManufacturerNativeWorkerCallOperation.OUTPUTS:
        return "Model_Outputs"
    else:
        if operation == ManufacturerNativeWorkerCallOperation.TERMINATE:
            return "Model_Terminate"
        else:
            raise ValueError("Manufacturer native call operation is invalid")

def _read_worker_text(stream: io.BytesIO, field_name: str) -> str:
    """Read one bounded NUL-free UTF-8 string from the worker payload.

    :param stream: Current worker payload reader.
    :param field_name: Field name used in diagnostics.
    :return: Decoded text.
    """
    length_bytes: bytes = stream.read(4)
    if len(length_bytes) != 4:
        raise ValueError(field_name + " length is truncated")
    else:
        text_length: int = struct.unpack("<I", length_bytes)[0]
    if text_length > 16 * 1024:
        raise ValueError(field_name + " exceeds 16 KiB")
    else:
        encoded_text: bytes = stream.read(text_length)
    if len(encoded_text) != text_length or b"\x00" in encoded_text:
        raise ValueError(field_name + " is invalid")
    else:
        return encoded_text.decode("utf-8", errors="strict")


def _read_worker_typed_value(stream: io.BytesIO,
                             expected_type: IeeeCigreDllDataType,
                             field_name: str) -> int | float | str:
    """Read one explicitly tagged scalar from the worker payload.

    :param stream: Current worker payload reader.
    :param expected_type: Type declared by the containing metadata record.
    :param field_name: Field name used in diagnostics.
    :return: Decoded scalar or text.
    """
    tag_raw: bytes = stream.read(1)
    if len(tag_raw) != 1 or tag_raw[0] != int(expected_type.value):
        raise ValueError(field_name + " type tag differs")
    else:
        tag: int = tag_raw[0]
    sizes: dict[int, int] = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 4, 7: 4, 8: 4, 9: 8}
    scalar_size: int | None = sizes.get(tag, None)
    if scalar_size is None:
        return _read_worker_text(stream, field_name)
    else:
        scalar_raw: bytes = stream.read(scalar_size)
    if len(scalar_raw) != scalar_size:
        raise ValueError(field_name + " is truncated")
    elif tag in (1, 2):
        return int(struct.unpack("<b", scalar_raw)[0])
    elif tag == 3:
        return int(struct.unpack("<B", scalar_raw)[0])
    elif tag == 4:
        return int(struct.unpack("<h", scalar_raw)[0])
    elif tag == 5:
        return int(struct.unpack("<H", scalar_raw)[0])
    elif tag == 6:
        return int(struct.unpack("<i", scalar_raw)[0])
    elif tag == 7:
        return int(struct.unpack("<I", scalar_raw)[0])
    elif tag == 8:
        return float(struct.unpack("<f", scalar_raw)[0])
    else:
        return float(struct.unpack("<d", scalar_raw)[0])


def _decode_worker_model_info(data: bytes) -> ManufacturerNativeModelInfo:
    """Decode the bounded interface-neutral metadata record emitted by C leaves.

    :param data: Exact neutral metadata payload returned by the worker.
    :return: Validated typed model metadata.
    """
    stream: io.BytesIO = io.BytesIO(data)
    interface_record: bytes = stream.read(4)
    if len(interface_record) != 4 or interface_record[1:] != bytes(3):
        raise ValueError("Manufacturer native interface record is invalid")
    elif interface_record[0] == 1:
        native_interface: NativeModelInterface = NativeModelInterface.IEEE_CIGRE_V1_1
    elif interface_record[0] == 2:
        native_interface = NativeModelInterface.IEEE_CIGRE_V1_0
    elif interface_record[0] == 3:
        native_interface = NativeModelInterface.IEC_ESE
    else:
        raise ValueError("Manufacturer native interface record is unknown")
    version_bytes: bytes = stream.read(4)
    if len(version_bytes) != 4:
        raise ValueError("Manufacturer native interface version is truncated")
    else:
        interface_version: Tuple[int, int, int, int] = (
            version_bytes[0],
            version_bytes[1],
            version_bytes[2],
            version_bytes[3],
        )
    texts: list[str] = list()
    text_index: int
    for text_index in range(13):
        texts.append(_read_worker_text(stream, "Manufacturer native metadata text"))
    sample_record: bytes = stream.read(20)
    if len(sample_record) != 20:
        raise ValueError("Manufacturer native sample record is truncated")
    else:
        declared_sample_time: float = struct.unpack_from("<d", sample_record, 0)[0]
        effective_sample_time: float = struct.unpack_from("<d", sample_record, 8)[0]
        sample_source_raw: int = sample_record[16]
        model_mode: IeeeCigreDllModelMode = IeeeCigreDllModelMode(sample_record[17])
        loadflow_raw: int = sample_record[18]
    if sample_record[19] != 0 or sample_source_raw != 1 or loadflow_raw not in (0, 1):
        raise ValueError("Manufacturer native sample discriminants are invalid")
    else:
        sample_time_source: NativeSampleTimeSource = NativeSampleTimeSource.MANUFACTURER_DECLARED
    signal_groups: list[Tuple[ManufacturerNativeSignalInfo, ...]] = list()
    group_index: int
    for group_index in range(2):
        count_bytes: bytes = stream.read(4)
        if len(count_bytes) != 4:
            raise ValueError("Manufacturer native signal count is truncated")
        else:
            signal_count: int = struct.unpack("<I", count_bytes)[0]
        signals: list[ManufacturerNativeSignalInfo] = list()
        signal_index: int
        for signal_index in range(signal_count):
            signal_texts: list[str] = list()
            field_index: int
            for field_index in range(4):
                signal_texts.append(_read_worker_text(stream, "Manufacturer native signal text"))
            signal_tail: bytes = stream.read(12)
            if len(signal_tail) != 12 or signal_tail[1:4] != bytes(3):
                raise ValueError("Manufacturer native signal record is invalid")
            else:
                data_type: IeeeCigreDllDataType = IeeeCigreDllDataType(signal_tail[0])
                width: int = struct.unpack_from("<I", signal_tail, 4)[0]
                semantic_type: int = struct.unpack_from("<I", signal_tail, 8)[0]
            if data_type == IeeeCigreDllDataType.C_STRING or width < 1:
                raise ValueError("Manufacturer native signal type or width is invalid")
            else:
                signals.append(ManufacturerNativeSignalInfo(
                    name=signal_texts[0],
                    description=signal_texts[1],
                    unit=signal_texts[2],
                    data_type=data_type,
                    width=width,
                    source_path=signal_texts[3],
                    semantic_type=semantic_type,
                ))
        signal_groups.append(tuple(signals))
    parameter_count_bytes: bytes = stream.read(4)
    if len(parameter_count_bytes) != 4:
        raise ValueError("Manufacturer native parameter count is truncated")
    else:
        parameter_count: int = struct.unpack("<I", parameter_count_bytes)[0]
    parameters: list[ManufacturerNativeParameterInfo] = list()
    parameter_index: int
    for parameter_index in range(parameter_count):
        parameter_texts: list[str] = list()
        field_index = 0
        for field_index in range(4):
            parameter_texts.append(_read_worker_text(stream, "Manufacturer native parameter text"))
        parameter_tail: bytes = stream.read(4)
        if len(parameter_tail) != 4 or parameter_tail[2:] != bytes(2):
            raise ValueError("Manufacturer native parameter discriminants are invalid")
        else:
            parameter_type: IeeeCigreDllDataType = IeeeCigreDllDataType(parameter_tail[0])
            fixed_raw: int = parameter_tail[1]
        if fixed_raw not in (0, 1):
            raise ValueError("Manufacturer native parameter FixedValue is invalid")
        else:
            default_value: int | float | str = _read_worker_typed_value(
                stream, parameter_type, "Manufacturer native parameter default",
            )
        bound_flags: bytes = stream.read(4)
        if (len(bound_flags) != 4 or bound_flags[2:] != bytes(2)
                or bound_flags[0] not in (0, 1) or bound_flags[1] not in (0, 1)):
            raise ValueError("Manufacturer native parameter bound flags are invalid")
        else:
            minimum_value: int | float | str | None = None
            maximum_value: int | float | str | None = None
        if bound_flags[0] == 1:
            minimum_value = _read_worker_typed_value(
                stream, parameter_type, "Manufacturer native parameter minimum",
            )
        else:
            pass
        if bound_flags[1] == 1:
            maximum_value = _read_worker_typed_value(
                stream, parameter_type, "Manufacturer native parameter maximum",
            )
        else:
            pass
        parameters.append(ManufacturerNativeParameterInfo(
            name=parameter_texts[0],
            group_name=parameter_texts[1],
            description=parameter_texts[2],
            unit=parameter_texts[3],
            data_type=parameter_type,
            fixed_value=bool(fixed_raw),
            default_value=default_value,
            minimum_value=minimum_value,
            maximum_value=maximum_value,
        ))
    state_bytes: bytes = stream.read(20)
    if len(state_bytes) != 20 or len(stream.read()) != 0:
        raise ValueError("Manufacturer native state record or trailing bytes are invalid")
    else:
        state_counts: Tuple[int, int, int, int, int] = struct.unpack("<IIIII", state_bytes)
    return ManufacturerNativeModelInfo(
        native_interface=native_interface,
        interface_version=interface_version,
        model_name=texts[0],
        model_version=texts[1],
        model_description=texts[2],
        version_control_info=texts[3],
        general_information=texts[4],
        model_created=texts[5],
        model_creator=texts[6],
        model_last_modified_date=texts[7],
        model_last_modified_by=texts[8],
        model_modified_comment=texts[9],
        model_modified_history=texts[10],
        code_generated_on=texts[11],
        included_solver=texts[12],
        fixed_step_base_sample_time=declared_sample_time,
        effective_sample_time=effective_sample_time,
        sample_time_source=sample_time_source,
        model_mode=model_mode,
        input_ports=signal_groups[0],
        output_ports=signal_groups[1],
        parameters=tuple(parameters),
        num_cont_states=state_counts[0],
        sizeof_misc_states=state_counts[1],
        loadflow_flag=bool(loadflow_raw),
        num_int_states=state_counts[2],
        num_float_states=state_counts[3],
        num_double_states=state_counts[4],
    )

def encode_manufacturer_native_worker_request(
        command: ManufacturerNativeWorkerRequest,
        request_id: int,
        staged_path: str,
        variant: ManufacturerNativeBinaryVariant,
        native_interface: NativeModelInterface,
        worker_identity: bytes,
        system_identity: Tuple[int, bytes, str],
        canonical_model_info: bytes,
        limits: NativeWorkerLimits,
        raw_model_info_sha256: bytes,
) -> bytes:
    """Encode one typed host request into the fixed little-endian protocol.

    :param command: Explicit semantic request.
    :param request_id: Nonzero sequential uint32 request identifier.
    :param staged_path: Absolute private DLL snapshot path.
    :param variant: Exact persistent DLL identity.
    :param native_interface: Exact ABI family selected by the user.
    :param worker_identity: Verified prepared worker SHA-256.
    :param system_identity: Genuine system runtime volume, file id and final path.
    :param canonical_model_info: Stored canonical metadata bytes.
    :param limits: Finite worker limits.
    :param raw_model_info_sha256: Exact preceding INSPECT raw metadata digest.
    :return: Complete framed request.
    """
    if request_id < 1 or request_id > 0xffffffff:
        raise ValueError("Manufacturer native request id must be a nonzero uint32")
    elif len(worker_identity) != 32 or len(system_identity[1]) != 16:
        raise ValueError("Manufacturer native worker or system runtime identity is invalid")
    else:
        pass
    opcode: ManufacturerNativeWorkerOpcode = command.opcode
    payload: bytearray = bytearray()
    if opcode == ManufacturerNativeWorkerOpcode.INSPECT:
        encoded_path: bytes = staged_path.encode("utf-8", errors="strict")
        encoded_system_path: bytes = system_identity[2].encode("utf-8", errors="strict")
        if b"\x00" in encoded_path or b"\x00" in encoded_system_path:
            raise ValueError("Manufacturer native identity paths must be NUL-free")
        else:
            pass
        if native_interface == NativeModelInterface.IEEE_CIGRE_V1_1:
            interface_number: int = 1
        elif native_interface == NativeModelInterface.IEEE_CIGRE_V1_0:
            interface_number = 2
        elif native_interface == NativeModelInterface.IEC_ESE:
            interface_number = 3
        else:
            raise ValueError("Manufacturer native interface is unsupported")
        payload.extend(bytes((interface_number, 0, 0, 0)))
        payload.extend(struct.pack("<I", len(encoded_path)))
        payload.extend(encoded_path)
        payload.extend(struct.pack("<Q", variant.byte_size))
        payload.extend(bytes.fromhex(variant.content_sha256))
        payload.extend(struct.pack("<Q", system_identity[0]))
        payload.extend(system_identity[1])
        payload.extend(struct.pack("<I", len(encoded_system_path)))
        payload.extend(encoded_system_path)
        payload.extend(struct.pack(
            "<QQIIIQQQQQQQ",
            limits.maximum_binary_bytes,
            limits.maximum_frame_bytes,
            limits.maximum_instances_per_worker,
            4096,
            4096,
            limits.maximum_scalar_slots_per_instance,
            limits.maximum_state_scalars_per_instance,
            limits.maximum_instance_buffer_bytes,
            limits.maximum_worker_buffer_bytes,
            16 * 1024 * 1024,
            1024 * 1024,
            0xffffffffffffffff,
        ))
    elif opcode == ManufacturerNativeWorkerOpcode.PREPARE:
        if len(raw_model_info_sha256) != 32:
            raise ValueError("Manufacturer native PREPARE needs the preceding raw metadata digest")
        else:
            payload.extend(raw_model_info_sha256)
            payload.extend(hashlib.sha256(canonical_model_info).digest())
    elif opcode in (ManufacturerNativeWorkerOpcode.INITIALIZE, ManufacturerNativeWorkerOpcode.SAMPLE):
        model_info: ManufacturerNativeModelInfo = decode_manufacturer_native_model_info(
            canonical_model_info
        )
        flattened_input_types: list[IeeeCigreDllDataType] = list()
        signal: ManufacturerNativeSignalInfo
        for signal in model_info.input_ports:
            flattened_input_types.extend([signal.data_type] * signal.width)
        if opcode == ManufacturerNativeWorkerOpcode.SAMPLE:
            if command.sample_time is None:
                raise ValueError("Manufacturer native sample request has no time")
            else:
                payload.extend(struct.pack("<d", command.sample_time))
        else:
            pass
        payload.extend(struct.pack("<I", len(command.instances)))
        previous_id: str = ""
        row: ManufacturerNativeWorkerInstanceRequest
        for row in command.instances:
            if row.instance_id <= previous_id:
                raise ValueError("Manufacturer native instance ids must be sorted unique text")
            elif len(row.inputs) != len(flattened_input_types):
                raise ValueError("Manufacturer native input row cardinality differs from ModelInfo")
            else:
                previous_id = row.instance_id
                encoded_id: bytes = row.instance_id.encode("utf-8", errors="strict")
            if b"\x00" in encoded_id:
                raise ValueError("Manufacturer native instance id must be NUL-free")
            else:
                payload.extend(struct.pack("<I", len(encoded_id)))
                payload.extend(encoded_id)
            if opcode == ManufacturerNativeWorkerOpcode.INITIALIZE:
                if row.model_mode is None:
                    raise ValueError("Manufacturer native initialization mode is missing")
                elif row.model_mode not in (IeeeCigreDllModelMode.EMT, IeeeCigreDllModelMode.RMS):
                    raise ValueError("Manufacturer native initialization mode must be EMT or RMS")
                else:
                    payload.extend(bytes((int(row.model_mode.value), 0, 0, 0)))
            else:
                pass
            payload.extend(struct.pack("<I", len(row.inputs)))
            value_index: int
            for value_index in range(len(row.inputs)):
                data_type: IeeeCigreDllDataType = flattened_input_types[value_index]
                value: int | float = row.inputs[value_index]
                payload.extend(bytes((int(data_type.value),)))
                if data_type in (IeeeCigreDllDataType.CHAR, IeeeCigreDllDataType.INT8):
                    payload.extend(struct.pack("<b", int(value)))
                elif data_type == IeeeCigreDllDataType.UINT8:
                    payload.extend(struct.pack("<B", int(value)))
                elif data_type == IeeeCigreDllDataType.INT16:
                    payload.extend(struct.pack("<h", int(value)))
                elif data_type == IeeeCigreDllDataType.UINT16:
                    payload.extend(struct.pack("<H", int(value)))
                elif data_type == IeeeCigreDllDataType.INT32:
                    payload.extend(struct.pack("<i", int(value)))
                elif data_type == IeeeCigreDllDataType.UINT32:
                    payload.extend(struct.pack("<I", int(value)))
                elif data_type == IeeeCigreDllDataType.REAL32:
                    payload.extend(struct.pack("<f", float(value)))
                elif data_type == IeeeCigreDllDataType.REAL64:
                    payload.extend(struct.pack("<d", float(value)))
                else:
                    raise ValueError("Manufacturer native signal input cannot be text")
            if opcode == ManufacturerNativeWorkerOpcode.INITIALIZE:
                payload.extend(struct.pack("<I", len(row.overrides)))
                override: Tuple[int, int, bool, int | float | str]
                for override in row.overrides:
                    ordinal: int = override[0]
                    data_type_number: int = override[1]
                    fixed_value: bool = override[2]
                    override_value: int | float | str = override[3]
                    override_type: IeeeCigreDllDataType = IeeeCigreDllDataType(
                        data_type_number
                    )
                    payload.extend(struct.pack(
                        "<IBB2x", ordinal, data_type_number, int(fixed_value)
                    ))
                    payload.extend(bytes((data_type_number,)))
                    if override_type in (
                            IeeeCigreDllDataType.CHAR, IeeeCigreDllDataType.INT8):
                        payload.extend(struct.pack("<b", int(override_value)))
                    elif override_type == IeeeCigreDllDataType.UINT8:
                        payload.extend(struct.pack("<B", int(override_value)))
                    elif override_type == IeeeCigreDllDataType.INT16:
                        payload.extend(struct.pack("<h", int(override_value)))
                    elif override_type == IeeeCigreDllDataType.UINT16:
                        payload.extend(struct.pack("<H", int(override_value)))
                    elif override_type == IeeeCigreDllDataType.INT32:
                        payload.extend(struct.pack("<i", int(override_value)))
                    elif override_type == IeeeCigreDllDataType.UINT32:
                        payload.extend(struct.pack("<I", int(override_value)))
                    elif override_type == IeeeCigreDllDataType.REAL32:
                        payload.extend(struct.pack("<f", float(override_value)))
                    elif override_type == IeeeCigreDllDataType.REAL64:
                        payload.extend(struct.pack("<d", float(override_value)))
                    else:
                        if not isinstance(override_value, str):
                            raise TypeError("Manufacturer native string override must be text")
                        else:
                            encoded_value: bytes = override_value.encode(
                                "utf-8", errors="strict"
                            )
                        if b"\x00" in encoded_value:
                            raise ValueError(
                                "Manufacturer native string override must be NUL-free"
                            )
                        else:
                            payload.extend(struct.pack("<I", len(encoded_value)))
                            payload.extend(encoded_value)
            else:
                pass
    elif opcode == ManufacturerNativeWorkerOpcode.CLOSE:
        pass
    else:
        raise ValueError("Unknown Manufacturer native worker command")
    header: bytes = struct.pack(
        "<4sHBBIIQ",
        b"VGX1",
        1,
        ManufacturerNativeWorkerMessageKind.REQUEST,
        opcode,
        request_id,
        ManufacturerNativeWorkerStatus.OK,
        len(payload),
    )
    body: bytes = header + bytes(payload)
    if len(body) > limits.maximum_frame_bytes:
        raise ValueError("Manufacturer native request exceeds the configured frame limit")
    else:
        return struct.pack("<Q", len(body)) + body


def _read_worker_capture(stream: io.BytesIO, capture_name: str) -> str:
    """Read one bounded normalized PREPARE capture.

    :param stream: Current response payload reader.
    :param capture_name: Diagnostic capture name.
    :return: Normalized UTF-8 text.
    """
    length_raw: bytes = stream.read(8)
    if len(length_raw) != 8:
        raise ValueError("Manufacturer native " + capture_name + " length is truncated")
    else:
        capture_length: int = struct.unpack("<Q", length_raw)[0]
        capture_raw: bytes = stream.read(capture_length)
    if len(capture_raw) != capture_length:
        raise ValueError("Manufacturer native " + capture_name + " is truncated")
    else:
        decoded_capture: str = capture_raw.decode("utf-8", errors="replace")
        return decoded_capture.replace("\r\n", "\n").replace("\r", "\n")


def _read_worker_call_result(
        stream: io.BytesIO) -> ManufacturerNativeWorkerCallResult:
    """Read one explicitly typed ABI call result.

    :param stream: Current response payload reader.
    :return: Decoded call result.
    """
    call_prefix: bytes = stream.read(8)
    if len(call_prefix) != 8 or call_prefix[1:4] != bytes(3):
        raise ValueError("Manufacturer native call record is invalid")
    else:
        operation: ManufacturerNativeWorkerCallOperation = (
            ManufacturerNativeWorkerCallOperation(call_prefix[0])
        )
        return_code: int = struct.unpack_from("<i", call_prefix, 4)[0]
    error_message: str = _read_worker_text(stream, "Manufacturer native error message")
    general_message: str = _read_worker_text(
        stream, "Manufacturer native general message"
    )
    return ManufacturerNativeWorkerCallResult(
        operation=operation,
        return_code=return_code,
        error_message=error_message,
        general_message=general_message,
    )


def _read_worker_outputs(stream: io.BytesIO) -> Tuple[int | float, ...]:
    """Read one finite typed output vector.

    :param stream: Current response payload reader.
    :return: Immutable numeric outputs.
    """
    count_raw: bytes = stream.read(4)
    if len(count_raw) != 4:
        raise ValueError("Manufacturer native output count is truncated")
    else:
        output_count: int = struct.unpack("<I", count_raw)[0]
        outputs: list[int | float] = list()
    output_index: int
    for output_index in range(output_count):
        tag_raw: bytes = stream.read(1)
        if len(tag_raw) != 1:
            raise ValueError("Manufacturer native output tag is truncated")
        else:
            tag: int = tag_raw[0]
        if tag in (1, 2):
            scalar_size: int = 1
            scalar_format: str = "<b"
        elif tag == 3:
            scalar_size = 1
            scalar_format = "<B"
        elif tag == 4:
            scalar_size = 2
            scalar_format = "<h"
        elif tag == 5:
            scalar_size = 2
            scalar_format = "<H"
        elif tag == 6:
            scalar_size = 4
            scalar_format = "<i"
        elif tag == 7:
            scalar_size = 4
            scalar_format = "<I"
        elif tag == 8:
            scalar_size = 4
            scalar_format = "<f"
        elif tag == 9:
            scalar_size = 8
            scalar_format = "<d"
        else:
            raise ValueError("Manufacturer native output TypedValue tag is invalid")
        scalar_raw: bytes = stream.read(scalar_size)
        if len(scalar_raw) != scalar_size:
            raise ValueError("Manufacturer native output value is truncated")
        else:
            output_value: int | float = struct.unpack(scalar_format, scalar_raw)[0]
        if not math.isfinite(float(output_value)):
            raise ValueError("Manufacturer native output value is not finite")
        else:
            outputs.append(output_value)
    return tuple(outputs)


def decode_manufacturer_native_worker_response(
        frame: bytes) -> ManufacturerNativeWorkerResponse:
    """Decode one response into an explicit typed result.

    :param frame: Complete framed response.
    :return: Validated semantic response.
    """
    if len(frame) < 32:
        raise ValueError("Manufacturer native worker response is truncated")
    else:
        body_length: int = struct.unpack_from("<Q", frame, 0)[0]
    if body_length != len(frame) - 8:
        raise ValueError("Manufacturer native worker response outer length differs")
    else:
        magic, version, kind, opcode_raw, request_id, status_raw, payload_length = (
            struct.unpack_from("<4sHBBIIQ", frame, 8)
        )
    if magic != b"VGX1" or version != 1 or kind != ManufacturerNativeWorkerMessageKind.RESPONSE:
        raise ValueError("Manufacturer native worker response header is invalid")
    elif payload_length != len(frame) - 32:
        raise ValueError("Manufacturer native worker response payload length differs")
    else:
        opcode: ManufacturerNativeWorkerOpcode = ManufacturerNativeWorkerOpcode(
            opcode_raw
        )
        status: ManufacturerNativeWorkerStatus = ManufacturerNativeWorkerStatus(
            status_raw
        )
        stream: io.BytesIO = io.BytesIO(frame[32:])
    if status != ManufacturerNativeWorkerStatus.OK:
        diagnostic: str = _read_worker_text(
            stream, "Manufacturer native worker diagnostic"
        )
        if len(stream.read()) != 0:
            raise ValueError("Manufacturer native worker diagnostic has trailing bytes")
        else:
            return ManufacturerNativeWorkerResponse(
                request_id=request_id,
                opcode=opcode,
                status=status,
                diagnostic=diagnostic,
            )
    else:
        worker_sha256: bytes = bytes()
        maximum_observations: int = 0
        imports: Tuple[str, ...] = tuple()
        canonical_model_info: bytes = bytes()
        raw_model_info_sha256: bytes = bytes()
        resident_module_limitation: str = ""
        return_code: int = 0
        stdout: str = ""
        stderr: str = ""
        stdout_truncated: bool = False
        stderr_truncated: bool = False
        instances: Tuple[ManufacturerNativeWorkerInstanceResult, ...] = tuple()
        terminated: Tuple[ManufacturerNativeWorkerInstanceResult, ...] = tuple()
    if opcode == ManufacturerNativeWorkerOpcode.INSPECT:
        prefix: bytes = stream.read(48)
        if len(prefix) != 48 or prefix[41:] != bytes(7):
            raise ValueError("Manufacturer native INSPECT response prefix is invalid")
        else:
            worker_sha256 = prefix[:32]
            maximum_observations = struct.unpack_from("<Q", prefix, 32)[0]
            transient_unobservable: bool = prefix[40] == 1
        import_count_raw: bytes = stream.read(4)
        if len(import_count_raw) != 4:
            raise ValueError("Manufacturer native INSPECT import count is truncated")
        else:
            import_count: int = struct.unpack("<I", import_count_raw)[0]
            import_names: list[str] = list()
        import_index: int
        for import_index in range(import_count):
            import_names.append(_read_worker_text(
                stream, "Manufacturer native INSPECT import"
            ))
        raw_model_info: bytes = stream.read()
        model_info: ManufacturerNativeModelInfo = _decode_worker_model_info(
            raw_model_info
        )
        canonical_model_info = encode_manufacturer_native_model_info(model_info)
        raw_model_info_sha256 = hashlib.sha256(raw_model_info).digest()
        imports = tuple(import_names)
        if transient_unobservable:
            resident_module_limitation = (
                "A dependency loaded and unloaded wholly inside one manufacturer call "
                "cannot be observed."
            )
        else:
            pass
    elif opcode == ManufacturerNativeWorkerOpcode.PREPARE:
        return_code_raw: bytes = stream.read(4)
        if len(return_code_raw) != 4:
            raise ValueError("Manufacturer native PREPARE return code is truncated")
        else:
            return_code = struct.unpack("<i", return_code_raw)[0]
        stdout = _read_worker_capture(stream, "PREPARE stdout")
        stderr = _read_worker_capture(stream, "PREPARE stderr")
        flags: bytes = stream.read(4)
        if len(flags) != 4 or flags[2:] != bytes(2):
            raise ValueError("Manufacturer native PREPARE flags are invalid")
        else:
            stdout_truncated = flags[0] == 1
            stderr_truncated = flags[1] == 1
    elif opcode in (
            ManufacturerNativeWorkerOpcode.INITIALIZE,
            ManufacturerNativeWorkerOpcode.SAMPLE):
        count_raw: bytes = stream.read(4)
        if len(count_raw) != 4:
            raise ValueError("Manufacturer native result row count is truncated")
        else:
            row_count: int = struct.unpack("<I", count_raw)[0]
            result_rows: list[ManufacturerNativeWorkerInstanceResult] = list()
        row_index: int
        for row_index in range(row_count):
            identifier: str = _read_worker_text(
                stream, "Manufacturer native result id"
            )
            call_count_raw: bytes = stream.read(4)
            if len(call_count_raw) != 4:
                raise ValueError("Manufacturer native result call count is truncated")
            else:
                call_count: int = struct.unpack("<I", call_count_raw)[0]
                call_results: list[ManufacturerNativeWorkerCallResult] = list()
            call_index: int
            for call_index in range(call_count):
                call_results.append(_read_worker_call_result(stream))
            outputs: Tuple[int | float, ...] = _read_worker_outputs(stream)
            if (opcode == ManufacturerNativeWorkerOpcode.SAMPLE
                    and len(call_results) != 1):
                raise ValueError("Manufacturer native SAMPLE must return one call")
            else:
                result_rows.append(ManufacturerNativeWorkerInstanceResult(
                    instance_id=identifier,
                    calls=tuple(call_results),
                    outputs=outputs,
                ))
        instances = tuple(result_rows)
    elif opcode == ManufacturerNativeWorkerOpcode.CLOSE:
        count_raw = stream.read(4)
        if len(count_raw) != 4:
            raise ValueError("Manufacturer native CLOSE count is truncated")
        else:
            termination_count: int = struct.unpack("<I", count_raw)[0]
            termination_rows: list[ManufacturerNativeWorkerInstanceResult] = list()
        termination_index: int
        for termination_index in range(termination_count):
            identifier = _read_worker_text(stream, "Manufacturer native CLOSE id")
            termination_call: ManufacturerNativeWorkerCallResult = (
                _read_worker_call_result(stream)
            )
            if termination_call.operation != ManufacturerNativeWorkerCallOperation.TERMINATE:
                raise ValueError("Manufacturer native CLOSE operation is invalid")
            else:
                termination_rows.append(ManufacturerNativeWorkerInstanceResult(
                    instance_id=identifier,
                    calls=(termination_call,),
                    outputs=tuple(),
                ))
        terminated = tuple(termination_rows)
    else:
        raise ValueError("Manufacturer native worker response opcode is invalid")
    if len(stream.read()) != 0:
        raise ValueError("Manufacturer native worker response has trailing bytes")
    else:
        return ManufacturerNativeWorkerResponse(
            request_id=request_id,
            opcode=opcode,
            status=status,
            worker_sha256=worker_sha256,
            maximum_observations=maximum_observations,
            imports=imports,
            canonical_model_info=canonical_model_info,
            raw_model_info_sha256=raw_model_info_sha256,
            resident_module_limitation=resident_module_limitation,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            instances=instances,
            terminated=terminated,
        )
