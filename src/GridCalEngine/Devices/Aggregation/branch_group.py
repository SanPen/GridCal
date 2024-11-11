# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.enumerations import BranchGroupTypes


class BranchGroup(EditableDevice):

    def __init__(self,
                 name='',
                 code='',
                 idtag: Union[str, None] = None,
                 group_type: BranchGroupTypes = BranchGroupTypes.GenericGroup):
        """
        BranchGroup
        :param name: name of the generator fuel
        :param code: secondary id
        :param idtag: UUID code
        :param group_type: type of branch group
        """

        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.BranchGroupDevice)

        self._group_type: BranchGroupTypes = group_type

        self.register(key='group_type', units='', tpe=BranchGroupTypes, definition=f'Type of branch group')

    @property
    def group_type(self) -> BranchGroupTypes:
        """
        Type of branch group
        :return: BranchGroupTypes
        """
        return self._group_type

    @group_type.setter
    def group_type(self, value: BranchGroupTypes):
        if isinstance(value, BranchGroupTypes):
            self._group_type = value
        else:
            raise TypeError("Invalid group_type data type")
