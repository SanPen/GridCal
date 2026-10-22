# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import TypeVar
from VeraGridEngine.IO.base.units import Unit
from VeraGridEngine.IO.base.base_property import BaseProperty
from VeraGridEngine.IO.raw.psse_file_type import PsseFileType


def coerce_psse_int(value: int | str | None, current_value: int) -> int:
    """
    Coerce a PSSE integer field while preserving the current default on invalid input.

    :param value: Candidate PSSE value.
    :param current_value: Current field value used as fallback.
    :return: Parsed integer or the current value when parsing is not possible.
    """
    parsed_value: int = current_value

    # PSSE files may leave optional numeric fields blank, so blank values keep the current default.
    if isinstance(value, str):
        stripped_value: str = value.strip()
        if stripped_value == "":
            parsed_value = current_value
        else:
            try:
                # Some PSSE writers emit integer fields as "1.0", so float parsing is the tolerant path.
                parsed_value = int(float(stripped_value))
            except ValueError:
                parsed_value = current_value
    elif value is None:
        parsed_value = current_value
    else:
        parsed_value = int(value)

    return parsed_value


def coerce_psse_float(value: float | int | str | None, current_value: float) -> float:
    """
    Coerce a PSSE floating-point field while preserving the current default on invalid input.

    :param value: Candidate PSSE value.
    :param current_value: Current field value used as fallback.
    :return: Parsed float or the current value when parsing is not possible.
    """
    parsed_value: float = current_value

    # PSSE files may leave optional numeric fields blank, so blank values keep the current default.
    if isinstance(value, str):
        stripped_value: str = value.strip()
        if stripped_value == "":
            parsed_value = current_value
        else:
            try:
                parsed_value = float(stripped_value)
            except ValueError:
                parsed_value = current_value
    elif value is None:
        parsed_value = current_value
    else:
        parsed_value = float(value)

    return parsed_value


def coerce_psse_str(value: str | int | float | None, current_value: str) -> str:
    """
    Coerce a PSSE string field.

    :param value: Candidate PSSE value.
    :param current_value: Current field value used as fallback when the value is missing.
    :return: String representation of the value or the current value when the value is missing.
    """
    parsed_value: str = current_value

    # String fields should stay editable, but a missing value should not erase an existing default.
    if value is None:
        parsed_value = current_value
    elif isinstance(value, str):
        parsed_value = value
    else:
        parsed_value = str(value)

    return parsed_value


class PsseProperty(BaseProperty):
    """
    Psse Property
    """

    __slots__ = (
        "rawx_key",
        "format_rule",
        "file_type",
    )

    def __init__(self,
                 property_name: str,
                 rawx_key: str,
                 class_type: TypeVar,
                 unit: Unit = None,
                 denominator_unit: Unit = None,
                 description: str = '',
                 max_chars=None,
                 min_value=-1e20,
                 max_value=1e20,
                 format_rule=None,
                 file_type: PsseFileType = PsseFileType.RAW):
        BaseProperty.__init__(self,
                              property_name=property_name,
                              class_type=class_type,
                              unit=unit,
                              denominator_unit=denominator_unit,
                              description=description,
                              max_chars=max_chars,
                              min_value=min_value,
                              max_value=max_value)

        self.rawx_key = rawx_key
        self.format_rule = format_rule
        # Auxiliary data belongs to its source format, never a RAWX network table.
        self.file_type: PsseFileType = file_type

    def __str__(self):
        return f'PSSeProp:{self.property_name}'
