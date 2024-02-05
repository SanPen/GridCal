# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from typing import Union
from GridCalEngine.Core.Devices.editable_device import EditableDevice
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.Branches.templates.parent_branch import ParentBranch
from GridCalEngine.enumerations import DeviceType


class Measurement(EditableDevice):
    """
    Measurement class
    """

    def __init__(self, value: float,
                 uncertainty: float,
                 api_obj: EditableDevice,
                 name: str,
                 idtag: Union[str, None],
                 device_type: DeviceType):
        """
        Constructor
        :param value: value
        :param uncertainty: uncertainty (standard deviation)
        :param api_obj:
        :param name:
        :param idtag:
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code="",
                                device_type=device_type)
        self.value = value
        self.sigma = uncertainty
        self.api_object: EditableDevice = api_obj

        self.register("value", "", float, "Value of the measurement")
        self.register("sigma", "", float, "Uncertainty of the measurement")
        self.register("api_object", "", EditableDevice, "Value of the measurement")


class PiMeasurement(Measurement):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: Bus, name="",
                 idtag: Union[str, None] = None):
        Measurement.__init__(self,
                             value=value,
                             uncertainty=uncertainty,
                             api_obj=api_obj,
                             name=name,
                             idtag=idtag,
                             device_type=DeviceType.PiMeasurementDevice)


class QiMeasurement(Measurement):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: Bus, name="",
                 idtag: Union[str, None] = None):
        Measurement.__init__(self,
                             value=value,
                             uncertainty=uncertainty,
                             api_obj=api_obj,
                             name=name,
                             idtag=idtag,
                             device_type=DeviceType.QiMeasurementDevice)


class VmMeasurement(Measurement):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: Bus, name="",
                 idtag: Union[str, None] = None):
        Measurement.__init__(self,
                             value=value,
                             uncertainty=uncertainty,
                             api_obj=api_obj,
                             name=name,
                             idtag=idtag,
                             device_type=DeviceType.VmMeasurementDevice)


class PfMeasurement(Measurement):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: ParentBranch, name="",
                 idtag: Union[str, None] = None):
        Measurement.__init__(self,
                             value=value,
                             uncertainty=uncertainty,
                             api_obj=api_obj,
                             name=name,
                             idtag=idtag,
                             device_type=DeviceType.PfMeasurementDevice)


class QfMeasurement(Measurement):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: ParentBranch, name="",
                 idtag: Union[str, None] = None):
        Measurement.__init__(self,
                             value=value,
                             uncertainty=uncertainty,
                             api_obj=api_obj,
                             name=name,
                             idtag=idtag,
                             device_type=DeviceType.QfMeasurementDevice)


class IfMeasurement(Measurement):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: ParentBranch, name="",
                 idtag: Union[str, None] = None):
        Measurement.__init__(self,
                             value=value,
                             uncertainty=uncertainty,
                             api_obj=api_obj,
                             name=name,
                             idtag=idtag,
                             device_type=DeviceType.IfMeasurementDevice)
