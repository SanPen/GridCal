# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import hashlib
import math
import struct
import unicodedata
from typing import Tuple

from VeraGridEngine.enumerations import (
    IeeeCigreDllDataType,
    IeeeCigreDllModelMode,
    NativeModelInterface,
    NativeSampleTimeSource,
)
from VeraGridEngine.IO.manufacturer_native.model_info import (
    ManufacturerNativeModelInfo,
    ManufacturerNativeParameterInfo,
    ManufacturerNativeSignalInfo,
)


class _CanonicalReader:
    """Bounds-checked reader for canonical ModelInfo bytes."""

    __slots__ = ("data", "offset", "text_bytes")

    def __init__(self, data: bytes) -> None:
        """Create a reader.

        :param data: Complete canonical byte sequence.
        :return: None.
        """
        self.data: bytes = data
        self.offset: int = 0
        self.text_bytes: int = 0

    def read(self, size: int) -> bytes:
        """Read exactly ``size`` bytes.

        :param size: Number of bytes to read.
        :return: Selected byte sequence.
        """
        end: int = self.offset + size
        if size < 0 or end > len(self.data):
            raise ValueError("Canonical ModelInfo is truncated")
        else:
            value: bytes = self.data[self.offset:end]
            self.offset = end
            return value

    def uint8(self) -> int:
        """Read one unsigned byte.

        :return: Unsigned byte value.
        """
        return int(self.read(1)[0])

    def uint32(self) -> int:
        """Read one big-endian unsigned 32-bit integer.

        :return: Unsigned integer value.
        """
        return int(struct.unpack(">I", self.read(4))[0])

    def text(self) -> str:
        """Read strict UTF-8 NFC text with a uint32 length.

        :return: Decoded canonical text.
        """
        size: int = self.uint32()
        if size > 16 * 1024:
            raise ValueError("One IEEE/CIGRE metadata string exceeds 16 KiB")
        else:
            self.text_bytes += size
        if self.text_bytes > 8 * 1024 * 1024:
            raise ValueError("Combined IEEE/CIGRE metadata strings exceed 8 MiB")
        else:
            value: str = self.read(size).decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", value) != value:
            raise ValueError("IEEE/CIGRE metadata text is not NFC-normalized")
        else:
            return value


def _put_uint32(target: bytearray, value: int, name: str) -> None:
    """Append one checked uint32.

    :param target: Destination buffer.
    :param value: Value to append.
    :param name: Diagnostic field name.
    :return: None.
    """
    if value < 0 or value > 0xffffffff:
        raise ValueError(f"{name} is outside uint32 range")
    else:
        target.extend(struct.pack(">I", value))


def _put_text(target: bytearray, value: str, name: str) -> int:
    """Append one normalized UTF-8 text value.

    :param target: Destination buffer.
    :param value: Text value.
    :param name: Diagnostic field name.
    :return: UTF-8 payload size.
    """
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    else:
        encoded: bytes = unicodedata.normalize("NFC", value).encode("utf-8", errors="strict")
    if len(encoded) > 16 * 1024:
        raise ValueError(f"{name} exceeds 16 KiB")
    else:
        _put_uint32(target, len(encoded), name)
        target.extend(encoded)
        return len(encoded)


def _finite(value: float, name: str) -> float:
    """Validate a finite float and normalize negative zero.

    :param value: Candidate value.
    :param name: Diagnostic field name.
    :return: Canonical finite value.
    """
    converted: float = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    else:
        pass
    if converted == 0.0:
        return 0.0
    else:
        return converted


def _integer_bytes(value: int | float | str,
                   size: int,
                   signed: bool,
                   name: str) -> bytes:
    """Encode an integer with an exact range diagnostic.

    :param value: Candidate scalar value.
    :param size: Storage width in bytes.
    :param signed: Signed integer flag.
    :param name: Diagnostic field name.
    :return: Big-endian integer bytes.
    """
    try:
        return int(value).to_bytes(size, byteorder="big", signed=signed)
    except OverflowError as ex:
        raise ValueError(f"{name} is outside its declared integer range") from ex


def _put_numeric(target: bytearray,
                 data_type: IeeeCigreDllDataType,
                 value: int | float | str,
                 name: str) -> None:
    """Append one canonical numeric scalar.

    :param target: Destination buffer.
    :param data_type: Declared ABI data type.
    :param value: Scalar value.
    :param name: Diagnostic field name.
    :return: None.
    """
    if data_type in (IeeeCigreDllDataType.CHAR, IeeeCigreDllDataType.INT8):
        target.extend(_integer_bytes(value, 1, True, name))
    elif data_type == IeeeCigreDllDataType.UINT8:
        target.extend(_integer_bytes(value, 1, False, name))
    elif data_type == IeeeCigreDllDataType.INT16:
        target.extend(_integer_bytes(value, 2, True, name))
    elif data_type == IeeeCigreDllDataType.UINT16:
        target.extend(_integer_bytes(value, 2, False, name))
    elif data_type == IeeeCigreDllDataType.INT32:
        target.extend(_integer_bytes(value, 4, True, name))
    elif data_type == IeeeCigreDllDataType.UINT32:
        target.extend(_integer_bytes(value, 4, False, name))
    elif data_type == IeeeCigreDllDataType.REAL32:
        target.extend(struct.pack(">f", _finite(float(value), name)))
    elif data_type == IeeeCigreDllDataType.REAL64:
        target.extend(struct.pack(">d", _finite(float(value), name)))
    else:
        raise ValueError(f"{name} is not a numeric IEEE/CIGRE type")


def _read_numeric(reader: _CanonicalReader,
                  data_type: IeeeCigreDllDataType,
                  name: str) -> int | float:
    """Read one canonical numeric scalar.

    :param reader: Canonical byte reader.
    :param data_type: Declared ABI data type.
    :param name: Diagnostic field name.
    :return: Decoded scalar.
    """
    if data_type in (IeeeCigreDllDataType.CHAR, IeeeCigreDllDataType.INT8):
        return int.from_bytes(reader.read(1), byteorder="big", signed=True)
    elif data_type == IeeeCigreDllDataType.UINT8:
        return int.from_bytes(reader.read(1), byteorder="big", signed=False)
    elif data_type == IeeeCigreDllDataType.INT16:
        return int.from_bytes(reader.read(2), byteorder="big", signed=True)
    elif data_type == IeeeCigreDllDataType.UINT16:
        return int.from_bytes(reader.read(2), byteorder="big", signed=False)
    elif data_type == IeeeCigreDllDataType.INT32:
        return int.from_bytes(reader.read(4), byteorder="big", signed=True)
    elif data_type == IeeeCigreDllDataType.UINT32:
        return int.from_bytes(reader.read(4), byteorder="big", signed=False)
    elif data_type == IeeeCigreDllDataType.REAL32:
        return _finite(float(struct.unpack(">f", reader.read(4))[0]), name)
    elif data_type == IeeeCigreDllDataType.REAL64:
        return _finite(float(struct.unpack(">d", reader.read(8))[0]), name)
    else:
        raise ValueError(f"{name} is not a numeric IEEE/CIGRE type")


def _put_signal(target: bytearray, signal: ManufacturerNativeSignalInfo, name: str) -> int:
    """Append one validated signal record.

    :param target: Destination buffer.
    :param signal: Signal description.
    :param name: Diagnostic field name.
    :return: Combined text payload size.
    """
    text_size: int = _put_text(target, signal.name, name + ".name")
    text_size += _put_text(target, signal.description, name + ".description")
    text_size += _put_text(target, signal.unit, name + ".unit")
    if signal.data_type == IeeeCigreDllDataType.C_STRING:
        raise ValueError(f"{name} cannot use c_string_T")
    else:
        _put_uint32(target, int(signal.data_type.value), name + ".data_type")
    if signal.width < 1 or signal.width > 1_048_576:
        raise ValueError(f"{name}.width is outside the supported range")
    else:
        _put_uint32(target, signal.width, name + ".width")
    return text_size


def _read_signal(reader: _CanonicalReader, name: str) -> ManufacturerNativeSignalInfo:
    """Read one validated signal record.

    :param reader: Canonical byte reader.
    :param name: Diagnostic field name.
    :return: Decoded signal description.
    """
    signal_name: str = reader.text()
    description: str = reader.text()
    unit: str = reader.text()
    try:
        data_type: IeeeCigreDllDataType = IeeeCigreDllDataType(reader.uint32())
    except ValueError as ex:
        raise ValueError(f"{name} has an unknown data type") from ex
    width: int = reader.uint32()
    if data_type == IeeeCigreDllDataType.C_STRING or width < 1 or width > 1_048_576:
        raise ValueError(f"{name} has an unsupported type or width")
    else:
        return ManufacturerNativeSignalInfo(signal_name, description, unit, data_type, width)


def _put_parameter(target: bytearray,
                   parameter: ManufacturerNativeParameterInfo,
                   name: str) -> int:
    """Append one validated parameter record.

    :param target: Destination buffer.
    :param parameter: Parameter description.
    :param name: Diagnostic field name.
    :return: Combined text payload size.
    """
    text_size: int = _put_text(target, parameter.name, name + ".name")
    text_size += _put_text(target, parameter.group_name, name + ".group_name")
    text_size += _put_text(target, parameter.description, name + ".description")
    text_size += _put_text(target, parameter.unit, name + ".unit")
    _put_uint32(target, int(parameter.data_type.value), name + ".data_type")
    _put_uint32(target, int(parameter.fixed_value), name + ".fixed_value")
    if parameter.data_type == IeeeCigreDllDataType.C_STRING:
        if not isinstance(parameter.default_value, str) or "\x00" in parameter.default_value:
            raise ValueError(f"{name}.default_value must be NUL-free text")
        else:
            text_size += _put_text(target, parameter.default_value, name + ".default_value")
        if parameter.minimum_value is not None or parameter.maximum_value is not None:
            raise ValueError(f"{name} c_string_T limits must be absent")
        else:
            target.extend(bytes((0, 0)))
    else:
        if parameter.minimum_value is None or parameter.maximum_value is None:
            raise ValueError(f"{name} numeric limits are required")
        else:
            pass
        if float(parameter.minimum_value) > float(parameter.default_value) or float(parameter.default_value) > float(parameter.maximum_value):
            raise ValueError(f"{name} must satisfy minimum <= default <= maximum")
        else:
            _put_numeric(target, parameter.data_type, parameter.default_value, name + ".default")
            _put_numeric(target, parameter.data_type, parameter.minimum_value, name + ".minimum")
            _put_numeric(target, parameter.data_type, parameter.maximum_value, name + ".maximum")
    return text_size


def _read_parameter(reader: _CanonicalReader, name: str) -> ManufacturerNativeParameterInfo:
    """Read one validated parameter record.

    :param reader: Canonical byte reader.
    :param name: Diagnostic field name.
    :return: Decoded parameter description.
    """
    parameter_name: str = reader.text()
    group_name: str = reader.text()
    description: str = reader.text()
    unit: str = reader.text()
    try:
        data_type: IeeeCigreDllDataType = IeeeCigreDllDataType(reader.uint32())
    except ValueError as ex:
        raise ValueError(f"{name} has an unknown data type") from ex
    fixed_raw: int = reader.uint32()
    if fixed_raw not in (0, 1):
        raise ValueError(f"{name}.fixed_value must be zero or one")
    else:
        fixed_value: bool = bool(fixed_raw)
    default_value: int | float | str
    minimum_value: int | float | str | None
    maximum_value: int | float | str | None
    if data_type == IeeeCigreDllDataType.C_STRING:
        default_value = reader.text()
        if "\x00" in default_value or reader.uint8() != 0 or reader.uint8() != 0:
            raise ValueError(f"{name} has invalid c_string_T data")
        else:
            minimum_value = None
            maximum_value = None
    else:
        default_value = _read_numeric(reader, data_type, name + ".default")
        minimum_value = _read_numeric(reader, data_type, name + ".minimum")
        maximum_value = _read_numeric(reader, data_type, name + ".maximum")
        if float(minimum_value) > float(default_value) or float(default_value) > float(maximum_value):
            raise ValueError(f"{name} must satisfy minimum <= default <= maximum")
        else:
            pass
    return ManufacturerNativeParameterInfo(
        parameter_name, group_name, description, unit, data_type, fixed_value,
        default_value, minimum_value, maximum_value,
    )

def _encode_legacy_model_info(model_info: ManufacturerNativeModelInfo) -> bytes:
    """Encode one ModelInfo using VeraGrid's canonical V1 byte sequence.

    :param model_info: Complete typed IEEE/CIGRE metadata.
    :return: Platform-neutral canonical bytes used for persistence and digesting.
    """
    target: bytearray = bytearray(b"veragrid-ieee-cigre-model-info-v1\n")
    if model_info.interface_version != (1, 1, 0, 0):
        raise ValueError("Only IEEE/CIGRE DLL interface version 1.1.0.0 is supported")
    else:
        target.extend(bytes(model_info.interface_version))
    text_values: Tuple[Tuple[str, str], ...] = (
        ("model_name", model_info.model_name),
        ("model_version", model_info.model_version),
        ("model_description", model_info.model_description),
        ("general_information", model_info.general_information),
        ("model_created", model_info.model_created),
        ("model_creator", model_info.model_creator),
        ("model_last_modified_date", model_info.model_last_modified_date),
        ("model_last_modified_by", model_info.model_last_modified_by),
        ("model_modified_comment", model_info.model_modified_comment),
        ("model_modified_history", model_info.model_modified_history),
    )
    text_size: int = 0
    field_name: str
    text_value: str
    for field_name, text_value in text_values:
        text_size += _put_text(target, text_value, field_name)
    sample_time: float = _finite(model_info.fixed_step_base_sample_time, "FixedStepBaseSampleTime")
    # Preserve the manufacturer's declared rate because fast switched converter
    # models need periods below ordinary network-simulation step sizes.
    if sample_time <= 0.0:
        raise ValueError("FixedStepBaseSampleTime must be positive")
    else:
        target.extend(struct.pack(">d", sample_time))
    target.extend(bytes((int(model_info.model_mode.value),)))
    if len(model_info.input_ports) > 4096 or len(model_info.output_ports) > 4096:
        raise ValueError("IEEE/CIGRE input or output port count exceeds 4096")
    else:
        _put_uint32(target, len(model_info.input_ports), "NumInputPorts")
    scalar_slots: int = 0
    signal: ManufacturerNativeSignalInfo
    signal_index: int
    for signal_index, signal in enumerate(model_info.input_ports):
        text_size += _put_signal(target, signal, f"input_ports[{signal_index}]")
        scalar_slots += signal.width
    _put_uint32(target, len(model_info.output_ports), "NumOutputPorts")
    for signal_index, signal in enumerate(model_info.output_ports):
        text_size += _put_signal(target, signal, f"output_ports[{signal_index}]")
        scalar_slots += signal.width
    if scalar_slots > 1_048_576:
        raise ValueError("Combined input and output scalar slots exceed 1,048,576")
    else:
        pass
    if len(model_info.parameters) > 4096:
        raise ValueError("NumParameters exceeds 4096")
    else:
        _put_uint32(target, len(model_info.parameters), "NumParameters")
    parameter: ManufacturerNativeParameterInfo
    parameter_index: int
    for parameter_index, parameter in enumerate(model_info.parameters):
        text_size += _put_parameter(target, parameter, f"parameters[{parameter_index}]")
    if text_size > 8 * 1024 * 1024:
        raise ValueError("Combined IEEE/CIGRE metadata strings exceed 8 MiB")
    else:
        pass
    state_total: int = model_info.num_int_states + model_info.num_float_states + model_info.num_double_states
    if state_total > 10_000_000:
        raise ValueError("Combined IEEE/CIGRE state count exceeds 10,000,000")
    else:
        _put_uint32(target, model_info.num_int_states, "NumIntStates")
        _put_uint32(target, model_info.num_float_states, "NumFloatStates")
        _put_uint32(target, model_info.num_double_states, "NumDoubleStates")
    return bytes(target)


def _decode_legacy_model_info(data: bytes) -> ManufacturerNativeModelInfo:
    """Decode and validate one exact canonical ModelInfo byte sequence.

    :param data: Complete canonical bytes stored by the provider.
    :return: Typed IEEE/CIGRE metadata.
    """
    if not isinstance(data, bytes):
        raise TypeError("Canonical ModelInfo must be immutable bytes")
    else:
        pass
    reader: _CanonicalReader = _CanonicalReader(data)
    prefix: bytes = b"veragrid-ieee-cigre-model-info-v1\n"
    if reader.read(len(prefix)) != prefix:
        raise ValueError("Canonical ModelInfo prefix is invalid")
    else:
        pass
    interface_version: Tuple[int, int, int, int] = (
        reader.uint8(), reader.uint8(), reader.uint8(), reader.uint8(),
    )
    if interface_version != (1, 1, 0, 0):
        raise ValueError("Only IEEE/CIGRE DLL interface version 1.1.0.0 is supported")
    else:
        pass
    model_name: str = reader.text()
    model_version: str = reader.text()
    model_description: str = reader.text()
    general_information: str = reader.text()
    model_created: str = reader.text()
    model_creator: str = reader.text()
    model_last_modified_date: str = reader.text()
    model_last_modified_by: str = reader.text()
    model_modified_comment: str = reader.text()
    model_modified_history: str = reader.text()
    sample_time: float = _finite(float(struct.unpack(">d", reader.read(8))[0]), "FixedStepBaseSampleTime")
    # Apply the same rule while decoding so persisted metadata cannot bypass
    # the import-time validation or acquire a different runtime meaning.
    if sample_time <= 0.0:
        raise ValueError("FixedStepBaseSampleTime must be positive")
    else:
        pass
    try:
        model_mode: IeeeCigreDllModelMode = IeeeCigreDllModelMode(reader.uint8())
    except ValueError as ex:
        raise ValueError("EMT_RMS_Mode is outside the official range") from ex
    input_count: int = reader.uint32()
    if input_count > 4096:
        raise ValueError("NumInputPorts exceeds 4096")
    else:
        pass
    inputs: list[ManufacturerNativeSignalInfo] = list()
    scalar_slots: int = 0
    signal_index: int
    for signal_index in range(input_count):
        input_signal: ManufacturerNativeSignalInfo = _read_signal(reader, f"input_ports[{signal_index}]")
        inputs.append(input_signal)
        scalar_slots += input_signal.width
    output_count: int = reader.uint32()
    if output_count > 4096:
        raise ValueError("NumOutputPorts exceeds 4096")
    else:
        pass
    outputs: list[ManufacturerNativeSignalInfo] = list()
    for signal_index in range(output_count):
        output_signal: ManufacturerNativeSignalInfo = _read_signal(reader, f"output_ports[{signal_index}]")
        outputs.append(output_signal)
        scalar_slots += output_signal.width
    if scalar_slots > 1_048_576:
        raise ValueError("Combined input and output scalar slots exceed 1,048,576")
    else:
        pass
    parameter_count: int = reader.uint32()
    if parameter_count > 4096:
        raise ValueError("NumParameters exceeds 4096")
    else:
        pass
    parameters: list[ManufacturerNativeParameterInfo] = list()
    parameter_index: int
    for parameter_index in range(parameter_count):
        parameters.append(_read_parameter(reader, f"parameters[{parameter_index}]"))
    num_int_states: int = reader.uint32()
    num_float_states: int = reader.uint32()
    num_double_states: int = reader.uint32()
    if num_int_states + num_float_states + num_double_states > 10_000_000:
        raise ValueError("Combined IEEE/CIGRE state count exceeds 10,000,000")
    else:
        pass
    if reader.offset != len(data):
        raise ValueError("Canonical ModelInfo contains trailing bytes")
    else:
        pass
    model_info: ManufacturerNativeModelInfo = ManufacturerNativeModelInfo(
        interface_version=interface_version,
        model_name=model_name,
        model_version=model_version,
        model_description=model_description,
        general_information=general_information,
        model_created=model_created,
        model_creator=model_creator,
        model_last_modified_date=model_last_modified_date,
        model_last_modified_by=model_last_modified_by,
        model_modified_comment=model_modified_comment,
        model_modified_history=model_modified_history,
        fixed_step_base_sample_time=sample_time,
        model_mode=model_mode,
        input_ports=tuple(inputs),
        output_ports=tuple(outputs),
        parameters=tuple(parameters),
        num_int_states=num_int_states,
        num_float_states=num_float_states,
        num_double_states=num_double_states,
    )
    if _encode_legacy_model_info(model_info) != data:
        raise ValueError("Canonical ModelInfo does not re-encode byte-identically")
    else:
        return model_info



def _validate_interface_version(native_interface: NativeModelInterface,
                                interface_version: Tuple[int, int, int, int]) -> None:
    """Validate the version returned for one explicitly selected ABI family.

    :param native_interface: Exact manufacturer interface selected during import.
    :param interface_version: Four-byte version returned by the binary.
    :return: None.
    """
    if native_interface == NativeModelInterface.IEEE_CIGRE_V1_1:
        expected_version: Tuple[int, int, int, int] = (1, 1, 0, 0)
    elif native_interface in (NativeModelInterface.IEEE_CIGRE_V1_0, NativeModelInterface.IEC_ESE):
        expected_version = (1, 0, 0, 0)
    else:
        raise ValueError("Native manufacturer interface is unsupported")
    if interface_version != expected_version:
        raise ValueError(
            f"{native_interface.value} requires interface version "
            f"{expected_version[0]}.{expected_version[1]}.{expected_version[2]}.{expected_version[3]}"
        )
    else:
        pass


def _put_signal_v2(target: bytearray,
                   signal: ManufacturerNativeSignalInfo,
                   name: str) -> int:
    """Append one schema-2 signal with common and legacy metadata.

    :param target: Destination canonical byte buffer.
    :param signal: Canonical signal description.
    :param name: Diagnostic field name.
    :return: Combined UTF-8 payload size.
    """
    text_size: int = _put_signal(target, signal, name)
    text_size += _put_text(target, signal.source_path, name + ".source_path")
    _put_uint32(target, signal.semantic_type, name + ".semantic_type")
    return text_size


def _read_signal_v2(reader: _CanonicalReader, name: str) -> ManufacturerNativeSignalInfo:
    """Read one schema-2 signal record.

    :param reader: Bounds-checked canonical reader.
    :param name: Diagnostic field name.
    :return: Decoded signal description.
    """
    signal: ManufacturerNativeSignalInfo = _read_signal(reader, name)
    source_path: str = reader.text()
    semantic_type: int = reader.uint32()
    return ManufacturerNativeSignalInfo(
        name=signal.name,
        description=signal.description,
        unit=signal.unit,
        data_type=signal.data_type,
        width=signal.width,
        source_path=source_path,
        semantic_type=semantic_type,
    )


def encode_manufacturer_native_model_info(model_info: ManufacturerNativeModelInfo) -> bytes:
    """Encode manufacturer metadata using canonical schema 2.

    Schema 2 records the selected ABI family and the exact effective sample
    time. This keeps IEEE/CIGRE 1.0 and IEC ESE unambiguous even though both
    interfaces report version 1.0.0.0.

    :param model_info: Complete typed manufacturer metadata.
    :return: Platform-neutral canonical bytes used for persistence and digesting.
    """
    _validate_interface_version(model_info.native_interface, model_info.interface_version)
    target: bytearray = bytearray(b"veragrid-manufacturer-native-model-info-v2\n")
    text_size: int = _put_text(target, model_info.native_interface.value, "native_interface")
    target.extend(bytes(model_info.interface_version))
    text_values: Tuple[Tuple[str, str], ...] = (
        ("model_name", model_info.model_name),
        ("model_version", model_info.model_version),
        ("model_description", model_info.model_description),
        ("version_control_info", model_info.version_control_info),
        ("general_information", model_info.general_information),
        ("model_created", model_info.model_created),
        ("model_creator", model_info.model_creator),
        ("model_last_modified_date", model_info.model_last_modified_date),
        ("model_last_modified_by", model_info.model_last_modified_by),
        ("model_modified_comment", model_info.model_modified_comment),
        ("model_modified_history", model_info.model_modified_history),
        ("code_generated_on", model_info.code_generated_on),
        ("included_solver", model_info.included_solver),
    )
    field_name: str
    text_value: str
    for field_name, text_value in text_values:
        text_size += _put_text(target, text_value, field_name)
    declared_sample_time: float = _finite(
        model_info.fixed_step_base_sample_time,
        "FixedStepBaseSampleTime",
    )
    effective_sample_time: float = _finite(
        model_info.effective_sample_time,
        "effective_sample_time",
    )
    if declared_sample_time <= 0.0:
        raise ValueError("FixedStepBaseSampleTime must be positive")
    else:
        pass
    if effective_sample_time <= 0.0:
        raise ValueError("effective_sample_time must be positive")
    else:
        target.extend(struct.pack(">d", declared_sample_time))
        target.extend(struct.pack(">d", effective_sample_time))
    text_size += _put_text(target, model_info.sample_time_source.value, "sample_time_source")
    target.extend(bytes((int(model_info.model_mode.value),)))
    if len(model_info.input_ports) > 4096 or len(model_info.output_ports) > 4096:
        raise ValueError("Manufacturer input or output port count exceeds 4096")
    else:
        _put_uint32(target, len(model_info.input_ports), "NumInputPorts")
    scalar_slots: int = 0
    signal: ManufacturerNativeSignalInfo
    signal_index: int
    for signal_index, signal in enumerate(model_info.input_ports):
        text_size += _put_signal_v2(target, signal, f"input_ports[{signal_index}]")
        scalar_slots += signal.width
    _put_uint32(target, len(model_info.output_ports), "NumOutputPorts")
    for signal_index, signal in enumerate(model_info.output_ports):
        text_size += _put_signal_v2(target, signal, f"output_ports[{signal_index}]")
        scalar_slots += signal.width
    if scalar_slots > 1_048_576:
        raise ValueError("Combined input and output scalar slots exceed 1,048,576")
    else:
        pass
    if len(model_info.parameters) > 4096:
        raise ValueError("NumParameters exceeds 4096")
    else:
        _put_uint32(target, len(model_info.parameters), "NumParameters")
    parameter: ManufacturerNativeParameterInfo
    parameter_index: int
    for parameter_index, parameter in enumerate(model_info.parameters):
        text_size += _put_parameter(target, parameter, f"parameters[{parameter_index}]")
    if text_size > 8 * 1024 * 1024:
        raise ValueError("Combined manufacturer metadata strings exceed 8 MiB")
    else:
        pass
    state_total: int = (
        model_info.num_cont_states + model_info.num_int_states
        + model_info.num_float_states + model_info.num_double_states
    )
    if state_total > 10_000_000:
        raise ValueError("Combined manufacturer state count exceeds 10,000,000")
    else:
        _put_uint32(target, model_info.num_cont_states, "NumContStates")
        _put_uint32(target, model_info.sizeof_misc_states, "SizeofMiscStates")
        target.extend(bytes((int(model_info.loadflow_flag),)))
        _put_uint32(target, model_info.num_int_states, "NumIntStates")
        _put_uint32(target, model_info.num_float_states, "NumFloatStates")
        _put_uint32(target, model_info.num_double_states, "NumDoubleStates")
    return bytes(target)

def _decode_current_model_info(data: bytes) -> ManufacturerNativeModelInfo:
    """Decode canonical schema-2 manufacturer metadata.

    :param data: Complete canonical schema-2 bytes.
    :return: Validated typed manufacturer metadata.
    """
    reader: _CanonicalReader = _CanonicalReader(data)
    prefix: bytes = b"veragrid-manufacturer-native-model-info-v2\n"
    if reader.read(len(prefix)) != prefix:
        raise ValueError("Canonical ModelInfo schema-2 prefix is invalid")
    else:
        pass
    try:
        native_interface: NativeModelInterface = NativeModelInterface(reader.text())
    except ValueError as ex:
        raise ValueError("Canonical ModelInfo declares an unknown native interface") from ex
    interface_version: Tuple[int, int, int, int] = (
        reader.uint8(), reader.uint8(), reader.uint8(), reader.uint8(),
    )
    _validate_interface_version(native_interface, interface_version)
    model_name: str = reader.text()
    model_version: str = reader.text()
    model_description: str = reader.text()
    version_control_info: str = reader.text()
    general_information: str = reader.text()
    model_created: str = reader.text()
    model_creator: str = reader.text()
    model_last_modified_date: str = reader.text()
    model_last_modified_by: str = reader.text()
    model_modified_comment: str = reader.text()
    model_modified_history: str = reader.text()
    code_generated_on: str = reader.text()
    included_solver: str = reader.text()
    declared_sample_time: float = _finite(
        float(struct.unpack(">d", reader.read(8))[0]),
        "FixedStepBaseSampleTime",
    )
    effective_sample_time: float = _finite(
        float(struct.unpack(">d", reader.read(8))[0]),
        "effective_sample_time",
    )
    if declared_sample_time <= 0.0:
        raise ValueError("FixedStepBaseSampleTime must be positive")
    else:
        pass
    if effective_sample_time <= 0.0:
        raise ValueError("effective_sample_time must be positive")
    else:
        pass
    try:
        sample_time_source: NativeSampleTimeSource = NativeSampleTimeSource(reader.text())
    except ValueError as ex:
        raise ValueError("Canonical ModelInfo has an unknown sample-time source") from ex
    try:
        model_mode: IeeeCigreDllModelMode = IeeeCigreDllModelMode(reader.uint8())
    except ValueError as ex:
        raise ValueError("EMT_RMS_Mode is outside the official range") from ex
    input_count: int = reader.uint32()
    if input_count > 4096:
        raise ValueError("NumInputPorts exceeds 4096")
    else:
        pass
    inputs: list[ManufacturerNativeSignalInfo] = list()
    scalar_slots: int = 0
    signal_index: int
    for signal_index in range(input_count):
        input_signal: ManufacturerNativeSignalInfo = _read_signal_v2(
            reader,
            f"input_ports[{signal_index}]",
        )
        inputs.append(input_signal)
        scalar_slots += input_signal.width
    output_count: int = reader.uint32()
    if output_count > 4096:
        raise ValueError("NumOutputPorts exceeds 4096")
    else:
        pass
    outputs: list[ManufacturerNativeSignalInfo] = list()
    for signal_index in range(output_count):
        output_signal: ManufacturerNativeSignalInfo = _read_signal_v2(
            reader,
            f"output_ports[{signal_index}]",
        )
        outputs.append(output_signal)
        scalar_slots += output_signal.width
    if scalar_slots > 1_048_576:
        raise ValueError("Combined input and output scalar slots exceed 1,048,576")
    else:
        pass
    parameter_count: int = reader.uint32()
    if parameter_count > 4096:
        raise ValueError("NumParameters exceeds 4096")
    else:
        pass
    parameters: list[ManufacturerNativeParameterInfo] = list()
    parameter_index: int
    for parameter_index in range(parameter_count):
        parameters.append(_read_parameter(reader, f"parameters[{parameter_index}]"))
    num_cont_states: int = reader.uint32()
    sizeof_misc_states: int = reader.uint32()
    loadflow_raw: int = reader.uint8()
    if loadflow_raw not in (0, 1):
        raise ValueError("LoadflowFlag must be zero or one")
    else:
        loadflow_flag: bool = bool(loadflow_raw)
    num_int_states: int = reader.uint32()
    num_float_states: int = reader.uint32()
    num_double_states: int = reader.uint32()
    state_total: int = num_cont_states + num_int_states + num_float_states + num_double_states
    if state_total > 10_000_000:
        raise ValueError("Combined manufacturer state count exceeds 10,000,000")
    else:
        pass
    if reader.offset != len(data):
        raise ValueError("Canonical ModelInfo contains trailing bytes")
    else:
        pass
    model_info: ManufacturerNativeModelInfo = ManufacturerNativeModelInfo(
        interface_version=interface_version,
        model_name=model_name,
        model_version=model_version,
        model_description=model_description,
        general_information=general_information,
        model_created=model_created,
        model_creator=model_creator,
        model_last_modified_date=model_last_modified_date,
        model_last_modified_by=model_last_modified_by,
        model_modified_comment=model_modified_comment,
        model_modified_history=model_modified_history,
        fixed_step_base_sample_time=declared_sample_time,
        model_mode=model_mode,
        input_ports=tuple(inputs),
        output_ports=tuple(outputs),
        parameters=tuple(parameters),
        num_int_states=num_int_states,
        num_float_states=num_float_states,
        num_double_states=num_double_states,
        native_interface=native_interface,
        version_control_info=version_control_info,
        code_generated_on=code_generated_on,
        included_solver=included_solver,
        effective_sample_time=effective_sample_time,
        sample_time_source=sample_time_source,
        num_cont_states=num_cont_states,
        sizeof_misc_states=sizeof_misc_states,
        loadflow_flag=loadflow_flag,
    )
    if encode_manufacturer_native_model_info(model_info) != data:
        raise ValueError("Canonical ModelInfo does not re-encode byte-identically")
    else:
        return model_info


def decode_manufacturer_native_model_info(data: bytes) -> ManufacturerNativeModelInfo:
    """Decode canonical schema 1 or schema 2 manufacturer metadata.

    :param data: Complete canonical metadata bytes stored by the provider.
    :return: Validated typed manufacturer metadata.
    """
    if not isinstance(data, bytes):
        raise TypeError("Canonical ModelInfo must be immutable bytes")
    else:
        pass
    current_prefix: bytes = b"veragrid-manufacturer-native-model-info-v2\n"
    legacy_prefix: bytes = b"veragrid-ieee-cigre-model-info-v1\n"
    if data.startswith(current_prefix):
        return _decode_current_model_info(data)
    elif data.startswith(legacy_prefix):
        return _decode_legacy_model_info(data)
    else:
        raise ValueError("Canonical ModelInfo prefix is invalid")


def digest_manufacturer_native_model_info(model_info: ManufacturerNativeModelInfo) -> str:
    """Compute the lowercase SHA-256 of canonical schema-2 metadata.

    :param model_info: Complete typed manufacturer metadata.
    :return: Lowercase hexadecimal SHA-256 digest.
    """
    canonical_bytes: bytes = encode_manufacturer_native_model_info(model_info)
    return hashlib.sha256(canonical_bytes).hexdigest()