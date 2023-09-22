# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType, GCProp


class EmissionGas(EditableDevice):

    def __init__(self,
                 name: str = '',
                 code: str = '',
                 idtag: Union[str, None] = None,
                 cost: float = 0.0,
                 cost_prof: Union[Vec, None] = None,
                 color: Union[str, None] = None):
        """
        Emission gas object
        :param name: name of the gas (CO2, NOx, etc.)
        :param code: secondary id
        :param idtag: UUID code
        :param cost: cost per tonn (€/t)
        :param cost_prof: profile of costs
        :param color: hexadecimal color string (i.e. #AA00FF)
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.EmissionGasDevice)

        self.cost = cost

        self.cost_prof = cost_prof

        self.color = color if color is not None else self.rnd_color()

        self.register(key='cost', units='€/t', tpe=float, definition='Cost of emissions (currency / ton)',
                      profile_name='cost_prof')
        self.register(key='color', units='', tpe=str, definition='Color to paint')

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
