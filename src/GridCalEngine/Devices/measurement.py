# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.Branches.winding import Winding
from GridCalEngine.Devices.Branches.switch import Switch
from GridCalEngine.Devices.Branches.series_reactance import SeriesReactance
from GridCalEngine.Devices.Branches.upfc import UPFC
from GridCalEngine.enumerations import DeviceType

# NOTE: These area here because this object loads first than the types file with the types aggregations

SE_BRANCH_TYPES = Union[
    Line,
    DcLine,
    Transformer2W,
    UPFC,
    Winding,
    Switch,
    SeriesReactance
]
MEASURABLE_OBJECT = Union[Bus, SE_BRANCH_TYPES]


class MeasurementTemplate(EditableDevice):
    """
    Measurement class
    """

    __slots__ = (
        'value',
        'sigma',
        'api_object',
    )

    def __init__(self, value: float,
                 uncertainty: float,
                 api_obj: MEASURABLE_OBJECT,
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
        self.value = float(value)
        self.sigma = float(uncertainty)
        self.api_object: MEASURABLE_OBJECT = api_obj

        self.register("value", tpe=float, definition="Value of the measurement")
        self.register("sigma", tpe=float, definition="Uncertainty of the measurement")
        self.register("api_object", tpe=MEASURABLE_OBJECT, definition="Object where the measurement happens")


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
                                     device_type=DeviceType.PMeasurementDevice)


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
                                     device_type=DeviceType.QMeasurementDevice)


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


class VaMeasurement(MeasurementTemplate):
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
                                     device_type=DeviceType.VaMeasurementDevice)


class PfMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.PfMeasurementDevice)


class QfMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.QfMeasurementDevice)


class PtMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.PtMeasurementDevice)


class QtMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.QtMeasurementDevice)


class IfMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.IfMeasurementDevice)


class ItMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.ItMeasurementDevice)
