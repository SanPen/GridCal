# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET



def read_required_attribute(
    element: ET.Element,
    attribute_name: str,
    fmi_attribute_owner: str,
    path: Path,
) -> str:
    """Return one required, non-empty FMI XML attribute.

    :param element: XML element containing the attribute.
    :param attribute_name: Required FMI attribute.
    :param fmi_attribute_owner: FMI element or variable that owns the attribute.
    :param path: FMU source path included in validation errors.
    :return: Exact non-empty attribute text.
    :raises ValueError: If the attribute is absent or only whitespace.
    """

    attribute_value: str | None = element.attrib.get(attribute_name, None)
    if attribute_value is None:
        raise ValueError(
            f"{fmi_attribute_owner} in {path} is missing required attribute {attribute_name}"
        )
    else:
        if len(attribute_value.strip()) > 0:
            return attribute_value
        else:
            raise ValueError(
                f"{fmi_attribute_owner} in {path} has empty required attribute {attribute_name}"
            )


def _normalize_fmi_unsigned_decimal(
    raw_attribute_value: str,
    attribute_name: str,
    fmi_attribute_owner: str,
    path: Path,
    bit_width: int,
) -> str:
    """Normalize FMI unsigned decimal text before bounded conversion.

    :param raw_attribute_value: Source attribute text.
    :param attribute_name: FMI attribute being parsed.
    :param fmi_attribute_owner: FMI element or variable that owns the attribute.
    :param path: FMU source path included in validation errors.
    :param bit_width: Unsigned integer width used in the lexical diagnostic.
    :return: Canonical unsigned digits without a sign or redundant leading zeros.
    :raises ValueError: If the lexical form is invalid.
    """

    normalized_value: str = raw_attribute_value.strip()
    if re.fullmatch(r"\+?[0-9]+", normalized_value) is None:
        raise ValueError(
            f"{fmi_attribute_owner} attribute {attribute_name} in {path} is not an unsigned "
            f"{bit_width}-bit integer"
        )
    else:
        if normalized_value.startswith("+"):
            unsigned_digits: str = normalized_value[1:]
        else:
            unsigned_digits = normalized_value

    significant_digits: str = unsigned_digits.lstrip("0")
    if len(significant_digits) == 0:
        significant_digits = "0"
    else:
        pass
    return significant_digits


def parse_fmi_uint32(
    raw_attribute_value: str,
    attribute_name: str,
    fmi_attribute_owner: str,
    path: Path,
) -> int:
    """Parse one FMI ``xs:unsignedInt`` value without Python-only syntax.

    :param raw_attribute_value: Source attribute text.
    :param attribute_name: FMI attribute being parsed.
    :param fmi_attribute_owner: FMI element or variable that owns the attribute.
    :param path: FMU source path included in validation errors.
    :return: Parsed unsigned 32-bit integer.
    :raises ValueError: If the lexical form or value is invalid.
    """

    significant_digits: str = _normalize_fmi_unsigned_decimal(
        raw_attribute_value=raw_attribute_value,
        attribute_name=attribute_name,
        fmi_attribute_owner=fmi_attribute_owner,
        path=path,
        bit_width=32,
    )

    # Compare the normalized decimal text before conversion. This keeps even a
    # bounded but adversarial XML attribute from reaching Python's large-integer
    # conversion limit while preserving valid leading-zero forms.
    if len(significant_digits) < 10:
        return int(significant_digits)
    else:
        if len(significant_digits) == 10 and significant_digits <= "4294967295":
            return int(significant_digits)
        else:
            raise ValueError(
                f"{fmi_attribute_owner} attribute {attribute_name} in {path} exceeds unsigned "
                "32-bit range"
            )


def parse_fmi_uint64(
    raw_attribute_value: str,
    attribute_name: str,
    fmi_attribute_owner: str,
    path: Path,
) -> int:
    """Parse one FMI ``xs:unsignedLong`` value without Python-only syntax.

    :param raw_attribute_value: Source attribute text.
    :param attribute_name: FMI attribute being parsed.
    :param fmi_attribute_owner: FMI element or variable that owns the attribute.
    :param path: FMU source path included in validation errors.
    :return: Parsed unsigned 64-bit integer.
    :raises ValueError: If the lexical form or value is invalid.
    """

    significant_digits: str = _normalize_fmi_unsigned_decimal(
        raw_attribute_value=raw_attribute_value,
        attribute_name=attribute_name,
        fmi_attribute_owner=fmi_attribute_owner,
        path=path,
        bit_width=64,
    )

    # Decimal text comparison bounds adversarial input before integer conversion.
    if len(significant_digits) < 20:
        return int(significant_digits)
    else:
        if (
            len(significant_digits) == 20
            and significant_digits <= "18446744073709551615"
        ):
            return int(significant_digits)
        else:
            raise ValueError(
                f"{fmi_attribute_owner} attribute {attribute_name} in {path} exceeds unsigned "
                "64-bit range"
            )


def parse_fmi_boolean(
    raw_attribute_value: str,
    attribute_name: str,
    fmi_attribute_owner: str,
    path: Path,
) -> bool:
    """Parse one FMI ``xs:boolean`` attribute using its exact lexical space.

    :param raw_attribute_value: Source attribute text.
    :param attribute_name: FMI attribute being parsed.
    :param fmi_attribute_owner: FMI element or variable that owns the attribute.
    :param path: FMU source path included in validation errors.
    :return: Parsed boolean value.
    :raises ValueError: If the value is not ``true``, ``false``, ``1`` or ``0``.
    """

    normalized_value: str = raw_attribute_value.strip()
    if normalized_value == "true" or normalized_value == "1":
        return True
    else:
        if normalized_value == "false" or normalized_value == "0":
            return False
        else:
            raise ValueError(
                f"{fmi_attribute_owner} attribute {attribute_name} in {path} is not a valid "
                "FMI boolean"
            )


def parse_fmi_int32(
    raw_attribute_value: str,
    attribute_name: str,
    fmi_attribute_owner: str,
    path: Path,
) -> int:
    """Parse one FMI ``xs:int`` attribute.

    :param raw_attribute_value: Source attribute text.
    :param attribute_name: FMI attribute being parsed.
    :param fmi_attribute_owner: FMI element or variable that owns the attribute.
    :param path: FMU source path included in validation errors.
    :return: Parsed signed 32-bit integer.
    :raises ValueError: If the lexical form or value is invalid.
    """

    normalized_value: str = raw_attribute_value.strip()
    if re.fullmatch(r"[+-]?[0-9]+", normalized_value) is None:
        raise ValueError(
            f"{fmi_attribute_owner} attribute {attribute_name} in {path} is not a signed "
            "32-bit integer"
        )
    else:
        if normalized_value.startswith("+") or normalized_value.startswith("-"):
            signed_digits: str = normalized_value[1:]
        else:
            signed_digits = normalized_value
        significant_digits: str = signed_digits.lstrip("0")
        if len(significant_digits) == 0:
            significant_digits = "0"
        else:
            pass

    # Bound the decimal text before conversion so adversarial attributes cannot
    # reach Python's large-integer conversion limit.
    if len(significant_digits) <= 10:
        if normalized_value.startswith("-"):
            bounded_decimal_value: str = "-" + significant_digits
        else:
            bounded_decimal_value = significant_digits
        parsed_value: int = int(bounded_decimal_value)
    else:
        raise ValueError(
            f"{fmi_attribute_owner} attribute {attribute_name} in {path} exceeds signed "
            "32-bit range"
        )

    if -2147483648 <= parsed_value <= 2147483647:
        return parsed_value
    else:
        raise ValueError(
            f"{fmi_attribute_owner} attribute {attribute_name} in {path} exceeds signed "
            "32-bit range"
        )


def parse_fmi_float(
    raw_attribute_value: str,
    attribute_name: str,
    fmi_attribute_owner: str,
    path: Path,
) -> float:
    """Parse one scalar FMI floating-point attribute.

    :param raw_attribute_value: Source attribute text.
    :param attribute_name: FMI attribute being parsed.
    :param fmi_attribute_owner: FMI element or variable that owns the attribute.
    :param path: FMU source path included in validation errors.
    :return: Parsed floating-point value.
    :raises ValueError: If the lexical form is not an FMI floating-point value.
    """

    normalized_value: str = raw_attribute_value.strip()
    finite_number_pattern: str = (
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
    )
    if (
        re.fullmatch(finite_number_pattern, normalized_value) is not None
        or normalized_value == "INF"
        or normalized_value == "-INF"
        or normalized_value == "NaN"
    ):
        if normalized_value == "INF":
            return float("inf")
        else:
            if normalized_value == "-INF":
                return float("-inf")
            else:
                return float(normalized_value)
    else:
        raise ValueError(
            f"{fmi_attribute_owner} attribute {attribute_name} in {path} is not a valid "
            "FMI floating-point value"
        )
