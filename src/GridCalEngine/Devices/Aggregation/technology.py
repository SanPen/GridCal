# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class Technology(EditableDevice):

    def __init__(self, name: str = '',
                 code: str = '',
                 idtag: Union[str, None] = None,
                 color: Union[str, None] = None):
        """
        Technology
        :param name: name of the technology
        :param code: secondary id
        :param idtag: UUID code
        :param color: hexadecimal color string (i.e. #AA00FF)
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.Technology)

        self.name2 = ""
        self.name3 = ""
        self.name4 = ""

        self.color = color if color is not None else self.rnd_color()

        self.register(key='name2', units='', tpe=str, definition='Name 2 of the technology')
        self.register(key='name3', units='', tpe=str, definition='Name 3 of the technology')
        self.register(key='name4', units='', tpe=str, definition='Name 4 of the technology')
        self.register(key='color', units='', tpe=str, definition='Color to paint')
