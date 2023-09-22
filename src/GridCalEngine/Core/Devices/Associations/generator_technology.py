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
from GridCalEngine.Core.Devices import Generator, Technology


class GeneratorTechnology(EditableDevice):

    def __init__(self,
                 name: str = '',
                 code: str = '',
                 idtag: Union[str, None] = None,
                 generator: Union[Generator, None] = None,
                 technology: Union[Technology, None] = None,
                 proportion: float = 1.0):
        """
        Technology to generator association
        :param name: name of the association
        :param code: secondary id
        :param idtag: UUID code
        :param generator: Generator object
        :param technology: Technology object
        :param proportion: share of the generator associated to the technology
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.GeneratorTechnologyAssociation)

        self.generator = generator

        self.technology = technology

        self.proportion = proportion

        self.register(key='generator', units='', tpe=DeviceType.GeneratorDevice, definition='Generator object')
        self.register(key='technology', units='', tpe=DeviceType.Technology, definition='Technology object')
        self.register(key='proportion', units='p.u.', tpe=float,
                      definition='Share of the generator associated to the technology')

    def get_properties_dict(self, version=3):
        data = {'id': self.idtag,
                'name': self.name,
                'code': self.code,
                'generator': self.generator,
                'technology': self.technology,
                'proportion': self.proportion
                }
        return data

    def get_profiles_dict(self, version=3):
        data = {'id': self.idtag}
        return data

    def get_units_dict(self, version=3):
        data = {}
        return data
