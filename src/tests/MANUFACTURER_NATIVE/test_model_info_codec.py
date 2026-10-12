# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import math
import struct

import pytest

from VeraGridEngine.enumerations import (
    IeeeCigreDllDataType,
    IeeeCigreDllModelMode,
    NativeModelInterface,
)
from VeraGridEngine.IO.manufacturer_native.model_info import (
    ManufacturerNativeModelInfo,
    ManufacturerNativeParameterInfo,
    ManufacturerNativeSignalInfo,
)
from VeraGridEngine.IO.manufacturer_native.model_info_codec import (
    _encode_legacy_model_info,
    decode_manufacturer_native_model_info,
    encode_manufacturer_native_model_info,
)


def _parameter(data_type: IeeeCigreDllDataType) -> ManufacturerNativeParameterInfo:
    """Create one valid parameter for a primitive ABI type.

    :param data_type: Primitive type represented by the parameter.
    :return: Valid bounded parameter metadata.
    """
    if data_type == IeeeCigreDllDataType.C_STRING:
        return ManufacturerNativeParameterInfo(
            data_type.name, "group", "description", "", data_type, True,
            "manufacturer", None, None,
        )
    elif data_type in (IeeeCigreDllDataType.REAL32, IeeeCigreDllDataType.REAL64):
        return ManufacturerNativeParameterInfo(
            data_type.name, "group", "description", "pu", data_type, False,
            1.25, -2.0, 3.0,
        )
    elif data_type in (IeeeCigreDllDataType.UINT8, IeeeCigreDllDataType.UINT16, IeeeCigreDllDataType.UINT32):
        return ManufacturerNativeParameterInfo(
            data_type.name, "group", "description", "", data_type, False,
            2, 0, 5,
        )
    else:
        return ManufacturerNativeParameterInfo(
            data_type.name, "group", "description", "", data_type, False,
            0, -2, 3,
        )


def _model_info(
        sample_time: float = 0.001,
        effective_sample_time: float | None = None,
        native_interface: NativeModelInterface = NativeModelInterface.IEEE_CIGRE_V1_1,
        interface_version: tuple[int, int, int, int] = (1, 1, 0, 0),
) -> ManufacturerNativeModelInfo:
    """Create complete canonical metadata covering all parameter types.

    :param sample_time: Fixed base sample time in seconds.
    :param effective_sample_time: Runtime period, or the declared period when omitted.
    :param native_interface: Exact manufacturer ABI family.
    :param interface_version: Four-byte interface version declaration.
    :return: Complete test metadata.
    """
    parameters: tuple[ManufacturerNativeParameterInfo, ...] = tuple(
        _parameter(data_type) for data_type in IeeeCigreDllDataType
    )
    return ManufacturerNativeModelInfo(
        interface_version=interface_version,
        model_name="Controlador Á",
        model_version="1.0",
        model_description="Stateful test model",
        general_information="IEEE/CIGRE V1.1",
        model_created="2026-09-17",
        model_creator="VeraGrid tests",
        model_last_modified_date="2026-09-17",
        model_last_modified_by="VeraGrid tests",
        model_modified_comment="none",
        model_modified_history="initial",
        fixed_step_base_sample_time=sample_time,
        model_mode=IeeeCigreDllModelMode.EMT_AND_RMS,
        input_ports=(ManufacturerNativeSignalInfo(
            "voltage", "terminal voltage", "pu", IeeeCigreDllDataType.REAL64, 2),),
        output_ports=(ManufacturerNativeSignalInfo(
            "command", "controller command", "pu", IeeeCigreDllDataType.REAL32, 1),),
        parameters=parameters,
        num_int_states=2,
        num_float_states=3,
        num_double_states=4,
        native_interface=native_interface,
        effective_sample_time=effective_sample_time,
    )


def test_model_info_roundtrip_is_byte_canonical_for_all_parameter_types() -> None:
    """All ABI parameter types must survive an exact canonical roundtrip."""
    encoded: bytes = encode_manufacturer_native_model_info(_model_info())
    decoded: ManufacturerNativeModelInfo = decode_manufacturer_native_model_info(encoded)

    assert encode_manufacturer_native_model_info(decoded) == encoded
    assert tuple(parameter.data_type for parameter in decoded.parameters) == tuple(IeeeCigreDllDataType)
    assert decoded.model_name == "Controlador Á"
    assert decoded.input_ports[0].width == 2
    assert decoded.num_double_states == 4


def _replace_encoded_sample_time(encoded: bytes,
                                 current_sample_time: float,
                                 replacement_sample_time: float) -> bytes:
    """Replace the unique canonical sample-time field for decoder tests.

    :param encoded: Valid canonical ModelInfo bytes.
    :param current_sample_time: Existing encoded sample time.
    :param replacement_sample_time: Invalid value to inject.
    :return: Canonical bytes containing the replacement field.
    """
    current_bytes: bytes = struct.pack(">d", current_sample_time)
    if encoded.count(current_bytes) != 1:
        raise AssertionError("Canonical sample-time field is not unique")
    else:
        replacement_bytes: bytes = struct.pack(">d", replacement_sample_time)
    return encoded.replace(current_bytes, replacement_bytes, 1)


@pytest.mark.parametrize("sample_time", (5e-6, 1e-5, math.nextafter(0.0, 1.0)))
def test_model_info_preserves_finite_positive_sample_times(sample_time: float) -> None:
    """Canonical metadata must preserve real fast-converter sample times.

    :param sample_time: Finite positive binary64 value under test.
    :return: None.
    """
    encoded: bytes = encode_manufacturer_native_model_info(_model_info(sample_time=sample_time))
    decoded: ManufacturerNativeModelInfo = decode_manufacturer_native_model_info(encoded)

    assert decoded.fixed_step_base_sample_time == sample_time
    assert encode_manufacturer_native_model_info(decoded) == encoded


@pytest.mark.parametrize("sample_time", (0.0, -5e-6, float("nan"), float("inf"), -1.0))
def test_model_info_encoder_rejects_nonpositive_or_nonfinite_sample_times(sample_time: float) -> None:
    """The encoder must reject periods without executable fixed-step meaning.

    :param sample_time: Invalid sample time under test.
    :return: None.
    """
    with pytest.raises(ValueError, match="FixedStepBaseSampleTime"):
        encode_manufacturer_native_model_info(_model_info(sample_time=sample_time))


@pytest.mark.parametrize("sample_time", (0.0, -5e-6, float("nan"), float("inf"), -1.0))
def test_model_info_decoder_rejects_nonpositive_or_nonfinite_sample_times(sample_time: float) -> None:
    """Persisted metadata must enforce the same period rule as import.

    :param sample_time: Invalid canonical sample time under test.
    :return: None.
    """
    valid_sample_time: float = 0.001
    encoded: bytes = encode_manufacturer_native_model_info(_model_info(
        sample_time=valid_sample_time,
        effective_sample_time=0.002,
    ))
    invalid: bytes = _replace_encoded_sample_time(encoded, valid_sample_time, sample_time)

    with pytest.raises(ValueError, match="FixedStepBaseSampleTime"):
        decode_manufacturer_native_model_info(invalid)


def test_signal_ports_reject_c_string_values() -> None:
    """C strings are parameter values and cannot become signal buffers."""
    model_info: ManufacturerNativeModelInfo = _model_info()
    model_info.input_ports = (ManufacturerNativeSignalInfo(
        "invalid", "invalid", "", IeeeCigreDllDataType.C_STRING, 1),)

    with pytest.raises(ValueError, match="cannot use c_string_T"):
        encode_manufacturer_native_model_info(model_info)


@pytest.mark.parametrize(
    ("native_interface", "interface_version"),
    (
        (NativeModelInterface.IEEE_CIGRE_V1_1, (1, 1, 0, 0)),
        (NativeModelInterface.IEEE_CIGRE_V1_0, (1, 0, 0, 0)),
        (NativeModelInterface.IEC_ESE, (1, 0, 0, 0)),
    ),
)
def test_model_info_roundtrip_preserves_exact_native_interface(
        native_interface: NativeModelInterface,
        interface_version: tuple[int, int, int, int],
) -> None:
    """Schema 2 must distinguish all supported manufacturer contracts.

    :param native_interface: ABI family under test.
    :param interface_version: Version required by that ABI family.
    :return: None.
    """
    encoded: bytes = encode_manufacturer_native_model_info(_model_info(
        sample_time=5e-6,
        native_interface=native_interface,
        interface_version=interface_version,
    ))
    decoded: ManufacturerNativeModelInfo = decode_manufacturer_native_model_info(encoded)

    assert decoded.native_interface == native_interface
    assert decoded.interface_version == interface_version
    assert decoded.fixed_step_base_sample_time == 5e-6
    assert decoded.effective_sample_time == 5e-6


@pytest.mark.parametrize(
    ("native_interface", "interface_version"),
    (
        (NativeModelInterface.IEEE_CIGRE_V1_1, (1, 0, 0, 0)),
        (NativeModelInterface.IEEE_CIGRE_V1_0, (1, 1, 0, 0)),
        (NativeModelInterface.IEC_ESE, (1, 1, 0, 0)),
    ),
)
def test_model_info_rejects_interface_version_mismatch(
        native_interface: NativeModelInterface,
        interface_version: tuple[int, int, int, int],
) -> None:
    """An ABI selector cannot be persisted with another contract version.

    :param native_interface: ABI family under test.
    :param interface_version: Incompatible declared version.
    :return: None.
    """
    with pytest.raises(ValueError, match="interface version"):
        encode_manufacturer_native_model_info(_model_info(
            native_interface=native_interface,
            interface_version=interface_version,
        ))


def test_legacy_schema_one_remains_readable() -> None:
    """Existing IEEE/CIGRE 1.1 metadata must remain loadable after schema 2."""
    legacy_bytes: bytes = _encode_legacy_model_info(_model_info())
    decoded: ManufacturerNativeModelInfo = decode_manufacturer_native_model_info(legacy_bytes)

    assert decoded.native_interface == NativeModelInterface.IEEE_CIGRE_V1_1
    assert decoded.interface_version == (1, 1, 0, 0)
    assert decoded.effective_sample_time == decoded.fixed_step_base_sample_time