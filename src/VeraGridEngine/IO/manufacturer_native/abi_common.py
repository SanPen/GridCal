# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import ctypes

from VeraGridEngine.basic_structures import Logger


class ESEExtension(ctypes.Union):
    """Exact eight-byte extension slot shared by legacy and IEC ESE ABIs."""

    _fields_ = [
        ("UserInt8_8", ctypes.c_int8 * 8),
        ("UserUint8_8", ctypes.c_uint8 * 8),
        ("UserInt16_4", ctypes.c_int16 * 4),
        ("UserUint16_4", ctypes.c_uint16 * 4),
        ("UserInt32_2", ctypes.c_int32 * 2),
        ("UserUint32_2", ctypes.c_uint32 * 2),
        ("UserChar_8", ctypes.c_char * 8),
        ("UserReal32_2", ctypes.c_float * 2),
        ("UserReal64", ctypes.c_double),
        ("UserVoidPtr", ctypes.c_void_p),
    ]


def decode_required_text(value: bytes | None, field_name: str) -> str:
    """Copy one required bounded UTF-8 string from native metadata.

    :param value: Bytes exposed by ``ctypes.c_char_p`` or ``None``.
    :param field_name: Diagnostic field name.
    :return: Strict UTF-8 text independent of vendor-owned memory.
    """
    if value is None:
        raise ValueError(f"{field_name} is a null pointer")
    else:
        pass
    if len(value) > 16 * 1024:
        raise ValueError(f"{field_name} exceeds 16 KiB")
    else:
        return value.decode("utf-8", errors="strict")


def validate_native_count(value: int, field_name: str, maximum: int) -> int:
    """Validate one signed native count before dereferencing its array.

    :param value: Count copied from manufacturer metadata.
    :param field_name: Diagnostic field name.
    :param maximum: Inclusive resource limit.
    :return: Validated count.
    """
    if value < 0 or value > maximum:
        raise ValueError(f"{field_name} is outside 0..{maximum}")
    else:
        return value


def check_manufacturer_native_return(return_code: int,
                                     operation: str,
                                     last_error_message: str,
                                     last_general_message: str,
                                     logger: Logger,
                                     cleanup: bool = False) -> bool:
    """Apply the canonical integer return-code policy used by IEEE/CIGRE 1.1.

    :param return_code: Native function result.
    :param operation: Function name used in diagnostics.
    :param last_error_message: Bounded copied instance error message.
    :param last_general_message: Bounded copied instance general message.
    :param logger: Destination runtime logger.
    :param cleanup: Whether the operation is termination cleanup.
    :return: ``True`` for codes zero and one, otherwise ``False``.
    """
    if return_code == 0:
        return True
    elif return_code == 1:
        logger.add_warning(
            msg=f"{operation} returned a manufacturer message",
            comment=last_general_message,
        )
        return True
    elif return_code == 2:
        if cleanup:
            logger.add_error(
                msg=f"{operation} reported cleanup failure",
                comment=last_error_message,
            )
        else:
            logger.add_error(
                msg=f"{operation} reported a manufacturer error",
                comment=last_error_message,
            )
        return False
    else:
        logger.add_error(
            msg=f"{operation} returned unsupported code {return_code}",
            comment=last_error_message,
        )
        return False