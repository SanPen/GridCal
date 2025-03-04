# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Type
from GridCalEngine.basic_structures import Logger

def try_get(line: str, a: int, b:int,
            tpe: Type[float] | Type[int] | Type[str],
            device: str, prop_name: str,
            logger: Logger):
    """

    :param line:
    :param a:
    :param b:
    :param tpe:
    :param device:
    :param prop_name:
    :param logger:
    :return:
    """

    if len(line) > b:
        chunk = line[a:b].strip()

        if tpe == float:
            try:
                return float(chunk)
            except ValueError as e:
                logger.add_error(msg=str(e),
                                 device=device,
                                 device_property=prop_name,
                                 value=chunk)

        elif tpe == int:
            try:
                return int(chunk)
            except ValueError as e:
                logger.add_error(msg=str(e),
                                 device=device,
                                 device_property=prop_name,
                                 value=chunk)

        elif tpe == str:
            return chunk
    else:
        if tpe == float:
            return 0.0
        elif tpe == int:
            return 0
        elif tpe == str:
            return ""
        else:
            return ""