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
from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType, GCProp
from GridCalEngine.Core.Devices import Generator, EmissionGas


class GeneratorEmission(EditableDevice):

    def __init__(self,
                 name: str = '',
                 code: str = '',
                 idtag: Union[str, None] = None,
                 generator: Union[Generator, None] = None,
                 emission: Union[EmissionGas, None] = None,
                 rate: float = 0.0):
        """
        Generator to emission association
        :param name: name of the association
        :param code: secondary id
        :param idtag: UUID code
        :param generator: Generator object
        :param emission: EmissionGas object
        :param rate: emissions rate of the gas in the generator (t/MWh)
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.GeneratorEmissionAssociation)

        self.generator = generator

        self.emission = emission

        self.rate = rate

        self.register(key='generator', units='', tpe=DeviceType.GeneratorDevice, definition='Generator')
        self.register(key='emission', units='', tpe=DeviceType.EmissionGasDevice, definition='Emission')
        self.register(key='rate', units='t/MWh', tpe=float,
                      definition='Emissions rate of the gas in the generator (t/MWh)')

    def get_properties_dict(self, version=3):
        data = {'id': self.idtag,
                'name': self.name,
                'code': self.code,
                'generator': self.generator,
                'emission': self.emission,
                'rate': self.rate
                }
        return data

    def get_profiles_dict(self, version=3):
        data = {'id': self.idtag}
        return data

    def get_units_dict(self, version=3):
        data = {}
        return data
