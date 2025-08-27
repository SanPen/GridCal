# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import datetime
from typing import Union
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.Aggregation.modelling_authority import ModellingAuthority
from VeraGridEngine.enumerations import DeviceType


class PhysicalDevice(EditableDevice):
    """
    Parent class for Injections, Branches, Buses and other physical devices
    """
    __slots__ = (
        "modelling_authority",
        "_commissioned_date",
        "_decommissioned_date"
    )
    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 device_type: DeviceType):
        """
        PhysicalDevice
        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param device_type: DeviceType
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        self.modelling_authority: Union[ModellingAuthority, None] = None

        self._commissioned_date: int = 0
        self._decommissioned_date: int = 0

        self.register(key='modelling_authority', units='', tpe=DeviceType.ModellingAuthority,
                      definition='Modelling authority of this asset')
        self.register(key='commissioned_date', units='', tpe=int, definition='Commissioned date of the asset',
                      is_date=True)
        self.register(key='decommissioned_date', units='', tpe=int, definition='Decommissioned date of the asset',
                      is_date=True)

    @property
    def commissioned_date(self) -> int:
        """

        :return:
        """
        return self._commissioned_date

    @commissioned_date.setter
    def commissioned_date(self, val: int | datetime.datetime):
        if isinstance(val, int):
            self._commissioned_date = val
        elif isinstance(val, datetime.datetime):
            self._commissioned_date = val.timestamp()

    def set_commissioned_year(self, year: int, month=1, day=1):
        """
        Helper function to set the commissioning date of the asset
        :param year: Year
        :param month: month number
        :param day: day number
        """
        self.commissioned_date = datetime.datetime(year=year, month=month, day=day).timestamp()

    def get_commissioned_date_as_date(self) -> datetime.datetime:
        """
        Get the commissioned date as datetime
        :return:
        """
        return datetime.datetime.fromtimestamp(self._commissioned_date)

    @property
    def decommissioned_date(self) -> int:
        """

        :return:
        """
        return self._decommissioned_date

    @decommissioned_date.setter
    def decommissioned_date(self, val: int | datetime.datetime):
        if isinstance(val, int):
            self._decommissioned_date = val
        elif isinstance(val, datetime.datetime):
            self._decommissioned_date = val.timestamp()

    def set_decommissioned_year(self, year: int, month=1, day=1):
        """
        Helper function to set the decommissioning date of the asset
        :param year: Year
        :param month: month number
        :param day: day number
        """
        self.decommissioned_date = datetime.datetime(year=year, month=month, day=day).timestamp()

    def get_decommissioned_date_as_date(self) -> datetime.datetime:
        """
        Get the commissioned date as datetime
        :return:
        """
        return datetime.datetime.fromtimestamp(self._decommissioned_date)

    def initialize_rms(self):
        pass
