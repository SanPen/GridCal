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
import numpy as np
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class Fuel(EditableDevice):

    def __init__(self, name='',
                 code='',
                 idtag: Union[str, None] = None,
                 cost: float = 0.0,
                 color: Union[str, None] = None):
        """
        Fuel
        :param name: name of the generator fuel
        :param code: secondary id
        :param idtag: UUID code
        :param cost: cost of the fuel per ton (e/t)
        :param color: hexadecimal color string (i.e. #AA00FF)
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.FuelDevice)

        self.cost = cost

        self._cost_prof = Profile(default_value=cost, data_type=float)

        self.color = color if color is not None else self.rnd_color()

        self.register(key='cost', units='e/t', tpe=float, definition='Cost of fuel (e / ton)',
                      profile_name='cost_prof')
        self.register(key='color', units='', tpe=str, definition='Color to paint')

    @property
    def cost_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._cost_prof

    @cost_prof.setter
    def cost_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._cost_prof = val
        elif isinstance(val, np.ndarray):
            self._cost_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a cost_prof')
