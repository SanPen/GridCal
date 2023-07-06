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

from GridCal.Engine.Core.Devices.editable_device import EditableDevice, DeviceType


class Technology(EditableDevice):

    def __init__(self, name='', code='', idtag=None):
        """

        :param name:
        :param code:
        :param idtag:
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                active=True,
                                device_type=DeviceType.Technology)

        self.name2 = ""
        self.name3 = ""
        self.name4 = ""

        self.register(key='name2', units='', tpe=str, definition='Name 2 of the technology')
        self.register(key='name3', units='', tpe=str, definition='Name 3 of the technology')
        self.register(key='name4', units='', tpe=str, definition='Name 4 of the technology')

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
