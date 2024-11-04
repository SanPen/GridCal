# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


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
