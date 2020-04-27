# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

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
        idtag = idtag
