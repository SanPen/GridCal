# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.enumerations import DeviceType, SubstationTypes


class VoltageLevelTemplate(EditableDevice):

    def __init__(self, name='', code='', idtag: str | None = None,
                 device_type=DeviceType.GenericArea, voltage: float = 10):
        """

        :param name:
        :param code:
        :param idtag:
        :param device_type:
        :param voltage:
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=device_type)

        self.vl_type: SubstationTypes = SubstationTypes.SingleBar
        self.voltage: float = voltage
        self.n_line_positions: int = 0
        self.n_transformer_positions: int = 0
        self.add_disconnectors: bool = False

        self.register(key='vl_type', units='', tpe=SubstationTypes, definition='Voltage level type', editable=True)

        self.register(key='voltage', units='KV', tpe=float, definition='Voltage.', editable=True)

        self.register(key='n_line_positions', units='', tpe=int,
                      definition='Number of line positions to add.', editable=True)

        self.register(key='n_transformer_positions', units='', tpe=int,
                      definition='Number of transformer positions to add.', editable=True)

        self.register(key='add_disconnectors', units='', tpe=bool,
                      definition='Add disconnectors additionally to the circuit breakers', editable=True)