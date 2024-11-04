# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


from typing import Union
import numpy as np
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.profile import Profile


class EmissionGas(EditableDevice):

    def __init__(self,
                 name: str = '',
                 code: str = '',
                 idtag: Union[str, None] = None,
                 cost: float = 0.0,
                 color: Union[str, None] = None):
        """
        Emission gas object
        :param name: name of the gas (CO2, NOx, etc.)
        :param code: secondary id
        :param idtag: UUID code
        :param cost: cost per tonn (e/t)
        :param color: hexadecimal color string (i.e. #AA00FF)
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.EmissionGasDevice)

        self.cost = cost

        self._cost_prof = Profile(default_value=cost, data_type=float)

        self.color = color if color is not None else self.rnd_color()

        self.register(key='cost', units='e/t', tpe=float, definition='Cost of emissions (e / ton)',
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
