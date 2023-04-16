# GridCal
# Copyright (C) 2023 Santiago Peñate Vera
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


class Technology(EditableDevice):

    def __init__(self, name='', code='', idtag=None):
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
                                editable_headers={'idtag': GCProp('', str, 'Unique ID'),
                                                  'code': GCProp('', str, 'Secondary ID in another system.'),
                                                  'name': GCProp('', str, 'Name of the technology'),
                                                  'name2': GCProp('', str, 'Name 2 of the technology'),
                                                  'name3': GCProp('', str, 'Name 3 of the technology'),
                                                  'name4': GCProp('', str, 'Name 4 of the technology'),
                                                  },
                                non_editable_attributes=['idtag'],
                                properties_with_profile={})

        self.name2 = ""
        self.name3 = ""
        self.name4 = ""

    def get_properties_dict(self):

        data = {'id': self.idtag,
                'name': self.name,
                'name2': self.name2,
                'name3': self.name3,
                'name4': self.name4,
                'code': self.code
                }
        return data

    def get_profiles_dict(self):
        data = {'id': self.idtag}
        return data

    def get_units_dict(self):
        data = {}
        return data
