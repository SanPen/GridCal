# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from GridCalEngine.basic_structures import Logger


def sub_float(line: str, a: int, b: int, device: str, prop_name: str, logger: Logger) -> float:
    """
    Try to get a value from a substring
    :param line: string
    :param a: start point
    :param b: end+1 point
    :param device: device type name
    :param prop_name: property name
    :param logger: Logger to record issues
    :return: float
    """
    if len(line) > b:
        chunk = line[a:b].strip()

        try:
            return float(chunk)
        except ValueError as e:
            logger.add_error(msg=str(e),
                             device=device,
                             device_property=prop_name,
                             value=chunk)
            return 0.0
    else:
        logger.add_error(msg=f"Could not parse {prop_name} because the file row is too short",
                         device=device,
                         device_property=prop_name,
                         value=line,
                         expected_value=b)
        return 0.0


def sub_int(line: str, a: int, b: int, device: str, prop_name: str,  logger: Logger) -> int:
    """
    Try to get a value from a substring
    :param line: string
    :param a: start point
    :param b: end+1 point
    :param device: device type name
    :param prop_name: property name
    :param logger: Logger to record issues
    :return: int
    """
    if len(line) > b:
        chunk = line[a:b].strip()

        try:
            return int(chunk)
        except ValueError as e:
            logger.add_error(msg=str(e),
                             device=device,
                             device_property=prop_name,
                             value=chunk)
            return 0
    else:
        logger.add_error(msg=f"Could not parse {prop_name} because the file row is too short",
                         device=device,
                         device_property=prop_name,
                         value=line,
                         expected_value=b)
        return 0



def sub_str(line: str, a: int, b: int, device: str, prop_name: str,  logger: Logger) -> str:
    """
    Try to get a value from a substring
    :param line: string
    :param a: start point
    :param b: end+1 point
    :param device: device type name
    :param prop_name: property name
    :param logger: Logger to record issues
    :return: string
    """

    if len(line) > b:
        chunk = line[a:b].strip()
        return chunk
    else:
        logger.add_error(msg=f"Could not parse {prop_name} because the file row is too short",
                         device=device,
                         device_property=prop_name,
                         value=line,
                         expected_value=b)
        return ""
