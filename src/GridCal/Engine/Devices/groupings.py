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


import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class GenericAreaGroup(EditableDevice):

    def __init__(self, name='', code='', idtag=None, device_type=DeviceType.GenericArea, latitude=0.0, longitude=0.0):
        """

        :param name:
        :param idtag:
        :param device_type:
        :param latitude:
        :param longitude:
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                active=True,
                                device_type=device_type,
                                editable_headers={'name': GCProp('', str, 'Name of the bus'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'longitude': GCProp('deg', float, 'longitude of the bus.'),
                                                  'latitude': GCProp('deg', float, 'latitude of the bus.')},
                                non_editable_attributes=['idtag'],
                                properties_with_profile={})

        self.latitude = latitude
        self.longitude = longitude

    def get_properties_dict(self, version=3):

        data = {'id': self.idtag,
                'name': self.name,
                'code': self.code
                }
        return data

    def get_profiles_dict(self, version=3):
        data = {'id': self.idtag}
        return data

    def get_units_dict(self, version=3):
        data = {}
        return data


class Substation(GenericAreaGroup):

    def __init__(self, name='Substation', idtag=None, code='', latitude=0.0, longitude=0.0):
        """

        :param name:
        :param idtag:
        :param latitude:
        :param longitude:
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.SubstationDevice,
                                  latitude=latitude,
                                  longitude=longitude)


class Area(GenericAreaGroup):

    def __init__(self, name='Area', idtag=None, code='', latitude=0.0, longitude=0.0):
        """

        :param name:
        :param idtag:
        :param latitude:
        :param longitude:
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.AreaDevice,
                                  latitude=latitude,
                                  longitude=longitude)


class Zone(GenericAreaGroup):

    def __init__(self, name='Zone', idtag=None, code='',latitude=0.0, longitude=0.0):
        """

        :param name:
        :param idtag:
        :param latitude:
        :param longitude:
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.ZoneDevice,
                                  latitude=latitude,
                                  longitude=longitude)


class Country(GenericAreaGroup):

    def __init__(self, name='Country', idtag=None, code='',latitude=0.0, longitude=0.0):
        """

        :param name:
        :param idtag:
        :param latitude:
        :param longitude:
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.CountryDevice,
                                  latitude=latitude,
                                  longitude=longitude)
