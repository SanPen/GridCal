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


class TechnologyCategory(EditableDevice):

    def __init__(self, name='', code='', idtag=None):
        """

        :param name:
        :param idtag:
        :param code:
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                active=True,
                                device_type=DeviceType.Technology,
                                editable_headers={'name': GCProp('', str, 'Name of the bus'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'longitude': GCProp('deg', float, 'longitude of the bus.'),
                                                  'latitude': GCProp('deg', float, 'latitude of the bus.')},
                                non_editable_attributes=['idtag'],
                                properties_with_profile={})

    def get_properties_dict(self, version=3):
        data = {'id': self.idtag,
                'name': self.name,
                'code': self.code,
                }
        return data

    def get_profiles_dict(self, version=3):
        data = {'id': self.idtag}
        return data

    def get_units_dict(self, version=3):
        data = {}
        return data


class TechnologyGroup(EditableDevice):

    def __init__(self, name='', code='', idtag=None, id_technology_category=None):
        """

        :param name:
        :param idtag:
        :param code:
        :param id_technology_category:
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                active=True,
                                device_type=DeviceType.Technology,
                                editable_headers={'name': GCProp('', str, 'Name of the bus'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'code': GCProp('deg', str, 'Code.'),
                                                  'id_technology_category': GCProp('deg', TechnologyCategory,
                                                                                'Technology category where this technology belongs')},
                                non_editable_attributes=['idtag'],
                                properties_with_profile={})

        self.id_technology_category = id_technology_category

    def get_properties_dict(self):
        data = {'id': self.idtag,
                'name': self.name,
                'code': self.code,
                'id_technology_category': self.id_technology_category if self.id_technology_category is not None else ""
                }
        return data

    def get_profiles_dict(self):
        data = {'id': self.idtag}
        return data

    def get_units_dict(self):
        data = {}
        return data


class Technology(EditableDevice):

    def __init__(self, name='', code='', idtag=None, id_technology_group=None):
        """

        :param name:
        :param idtag:
        :param code:
        :param id_technology_group:
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                active=True,
                                device_type=DeviceType.Technology,
                                editable_headers={'name': GCProp('', str, 'Name of the bus'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'code': GCProp('deg', str, 'Code.'),
                                                  'id_technology_group': GCProp('deg', TechnologyGroup,
                                                                                'Technology group where this technology belongs')},
                                non_editable_attributes=['idtag'],
                                properties_with_profile={})

        self.id_technology_group = id_technology_group

    def get_properties_dict(self):

        data = {'id': self.idtag,
                'name': self.name,
                'code': self.code,
                'id_technology_group': self.id_technology_group if self.id_technology_group is not None else ""
                }
        return data

    def get_profiles_dict(self):
        data = {'id': self.idtag}
        return data

    def get_units_dict(self):
        data = {}
        return data
