# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from enum import Enum


class MeasurementType(Enum):
    Pinj = "Active power injection",
    Qinj = "Reactive power injection",
    Vmag = "Voltage magnitude",
    Pflow = "Active power flow",
    Qflow = "Reactive power flow",
    Iflow = "Current module flow"


class Measurement:

    def __init__(self, value, uncertainty, mtype: MeasurementType, idtag=None):
        """
        Constructor
        :param value: value
        :param uncertainty: uncertainty (standard deviation)
        :param mtype: type of measurement
        """
        self.val = value
        self.sigma = uncertainty
        self.measurement_type = mtype
        self.idtag = idtag
