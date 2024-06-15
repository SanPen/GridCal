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
from __future__ import annotations
from typing import Union, TYPE_CHECKING
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import DeviceType

if TYPE_CHECKING:
    from GridCalEngine.Devices.types import ALL_DEV_TYPES, BRANCH_TYPES


class MeasurementTemplate(EditableDevice):
    """
    Measurement class
    """

    def __init__(self, value: float,
                 uncertainty: float,
                 api_obj: ALL_DEV_TYPES,
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
        self.api_object: ALL_DEV_TYPES = api_obj

        self.register("value", "", float, "Value of the measurement")
        self.register("sigma", "", float, "Uncertainty of the measurement")



class PiMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: Bus, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.PiMeasurementDevice)

        self.register("api_object", "", DeviceType.BusDevice, "Value of the measurement")


class QiMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: Bus, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.QiMeasurementDevice)

        self.register("api_object", "", DeviceType.BusDevice, "Value of the measurement")


class VmMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: Bus, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.VmMeasurementDevice)

        self.register("api_object", "", DeviceType.BusDevice, "Value of the measurement")


class PfMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.PfMeasurementDevice)

        self.register("api_object", "", DeviceType.BranchDevice, "Value of the measurement")


class QfMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.QfMeasurementDevice)

        self.register("api_object", "", DeviceType.BranchDevice, "Value of the measurement")


class IfMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.IfMeasurementDevice)

        self.register("api_object", "", DeviceType.BranchDevice, "Value of the measurement")
