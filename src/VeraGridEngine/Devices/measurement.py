# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Union

from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.winding import Winding
from VeraGridEngine.Devices.Branches.switch import Switch
from VeraGridEngine.Devices.Branches.series_reactance import SeriesReactance
from VeraGridEngine.Devices.Branches.upfc import UPFC
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.enumerations import DeviceType

# NOTE: These area here because this object loads first than the types file with the types aggregations

SE_BRANCH_TYPES = Union[
    Line,
    DcLine,
    Transformer2W,
    UPFC,
    Winding,
    Switch,
    SeriesReactance,
    Generator
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
        """
        Bus active power injection measurement
        :param value: value in MW
        :param uncertainty: standard deviation in MW
        :param api_obj: bus object
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.PMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / Sbase

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / Sbase


class QiMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: Bus, name="",
                 idtag: Union[str, None] = None):
        """
        Bus reactive power injection measurement
        :param value: value in MVAr
        :param uncertainty: standard deviation in MVAr
        :param api_obj: bus object
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.QMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / Sbase

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / Sbase


class PgMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: Generator, name="",
                 idtag: Union[str, None] = None):
        """
        Generator active power injection measurement
        :param value: value in MW
        :param uncertainty: standard deviation in MW
        :param api_obj: bus object
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.PgMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / Sbase

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / Sbase


class QgMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: Generator, name="",
                 idtag: Union[str, None] = None):
        """
        Generator reactive power injection measurement
        :param value: value in MVAr
        :param uncertainty: standard deviation in MVAr
        :param api_obj: bus object
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.QgMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / Sbase

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / Sbase


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
        """
        PfMeasurement
        :param value: Power flow in MW
        :param uncertainty: standard deviation in MW
        :param api_obj: a branch
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.PfMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / Sbase

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / Sbase


class QfMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        """
        QfMeasurement
        :param value: Power flow in MVAr
        :param uncertainty: standard deviation in MVAr
        :param api_obj: a branch
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.QfMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / Sbase

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / Sbase


class PtMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        """
        PtMeasurement
        :param value: Power flow in MW
        :param uncertainty: standard deviation in MW
        :param api_obj: a branch
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.PtMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / Sbase

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / Sbase


class QtMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        """
        QtMeasurement
        :param value: Power flow in MVAr
        :param uncertainty: standard deviation in MVAr
        :param api_obj: a branch
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.QtMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / Sbase

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / Sbase


def get_i_base(Sbase, Vbase):
    return Sbase / (Vbase * 1.732050808)


class IfMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        """
        IfMeasurement
        :param value: current flow in kA, note this is the absolute value
        :param uncertainty: standard deviation in kA
        :param api_obj: a branch
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.IfMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / get_i_base(Sbase, Vbase=self.api_object.bus_from.Vnom)

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / get_i_base(Sbase, Vbase=self.api_object.bus_from.Vnom)


class ItMeasurement(MeasurementTemplate):
    """
    Measurement class
    """

    def __init__(self, value: float, uncertainty: float, api_obj: SE_BRANCH_TYPES, name="",
                 idtag: Union[str, None] = None):
        """
        ItMeasurement
        :param value: current flow in kA, note this is the absolute value
        :param uncertainty: standard deviation in kA
        :param api_obj: a branch
        :param name: name
        :param idtag: idtag
        """
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=uncertainty,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.ItMeasurementDevice)

    def get_value_pu(self, Sbase: float):
        return self.value / get_i_base(Sbase, Vbase=self.api_object.bus_to.Vnom)

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / get_i_base(Sbase, Vbase=self.api_object.bus_to.Vnom)
