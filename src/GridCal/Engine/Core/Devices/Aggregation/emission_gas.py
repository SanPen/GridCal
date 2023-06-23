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


from typing import Union
from GridCal.Engine.basic_structures import Vec
from GridCal.Engine.Core.Devices.editable_device import EditableDevice, DeviceType, GCProp


class EmissionGas(EditableDevice):

    def __init__(self, name='',
                 code='',
                 idtag=None,
                 device_type=DeviceType.EmissionGasDevice,
                 cost: float = 0.0,
                 cost_prof: Union[Vec, None] = None):
        """

        :param name:
        :param idtag:
        :param device_type:

        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                active=True,
                                device_type=device_type,
                                editable_headers={'name': GCProp('', str, 'Name of the bus'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'cost': GCProp('€/t', float, 'Cost of emissions (currency / ton)'),
                                                  },
                                non_editable_attributes=['idtag'],
                                properties_with_profile={'cost': 'cost_prof'})

        self.cost = cost

        self.cost_prof = cost_prof

    def get_properties_dict(self, version=3):

        data = {'id': self.idtag,
                'name': self.name,
                'code': self.code,
                'cost': self.cost,
                }
        return data

    def get_profiles_dict(self, version=3):
        data = {'id': self.idtag}
        return data

    def get_units_dict(self, version=3):
        data = {}
        return data
