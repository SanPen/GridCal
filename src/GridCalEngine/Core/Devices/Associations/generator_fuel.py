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
from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType
from GridCalEngine.Core.Devices import Generator, Fuel


class GeneratorFuel(EditableDevice):

    def __init__(self,
                 name: str = '',
                 code: str = '',
                 idtag: Union[str, None] = None,
                 generator: Union[Generator, None] = None,
                 fuel: Union[Fuel, None] = None,
                 rate: float = 0.0):
        """
        Generator to fuel association
        :param name: name of the association
        :param code: secondary id
        :param idtag: UUID code
        :param generator: Generator object
        :param fuel: Fuel object
        :param rate: fuel consumption rate in the generator (t/MWh)
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.GeneratorFuelAssociation)

        self.generator = generator

        self.fuel = fuel

        self.rate = rate

        self.register(key='generator', units='', tpe=DeviceType.GeneratorDevice, definition='Generator')
        self.register(key='fuel', units='', tpe=DeviceType.FuelDevice, definition='Fuel')
        self.register(key='rate', units='t/MWh', tpe=float,
                      definition='Fuel consumption rate in the generator')

    def get_properties_dict(self, version=3):
        data = {'id': self.idtag,
                'name': self.name,
                'code': self.code,
                'generator': self.generator,
                'fuel': self.fuel,
                'rate': self.rate
                }
        return data

    def get_profiles_dict(self, version=3):
        data = {'id': self.idtag}
        return data

    def get_units_dict(self, version=3):
        data = {}
        return data
