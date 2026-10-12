# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Compatibility constructor for the former DC cable catalogue."""
import numpy as np
from VeraGridEngine.Devices.Branches.underground_line_type import UndergroundLineType


class DcCableType(UndergroundLineType):
    """Deprecated constructor; the resulting device is a common Cable System.

    Constructor L and C retain the old H/km and F/km units. Once constructed,
    properties follow Cable System units (X in ohm/km, C in microfarad/km).
    Use get_dc_parameters()/get_dc_values() for DC quantities. There is no
    separate device type, catalogue or persisted DC record.
    """
    __slots__ = ()

    def __init__(self, name: str = 'Cable System', idtag: str | None = None,
                 Vnom: float = 1.0, Imax: float = 1.0, R: float = 0.0,
                 L: float = 0.0, C: float = 0.0):
        omega = 2.0 * np.pi * 50.0
        super().__init__(name=name, idtag=idtag, Vnom=Vnom, Imax=Imax,
                         R=R, X=omega * L, C=C * 1.0e6,
                         B=omega * C * 1.0e6, freq=50.0)
