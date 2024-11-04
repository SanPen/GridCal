# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class SequenceLineType(EditableDevice):

    def __init__(self, name='SequenceLine', idtag=None, Imax=1, Vnom=1,
                 R=0, X=0, B=0, R0=0, X0=0, B0=0):
        """
        Constructor
        :param name: name of the model
        :param Imax: Line rating current in kA
        :param R: Resistance of positive sequence in Ohm/km
        :param X: Reactance of positive sequence in Ohm/km
        :param B: Susceptance of positive sequence in uS/km
        :param R0: Resistance of zero sequence in Ohm/km
        :param X0: Reactance of zero sequence in Ohm/km
        :param B0: Susceptance of zero sequence in uS/km
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code="",
                                device_type=DeviceType.SequenceLineDevice)

        self.Imax = Imax
        self.Vnom = Vnom

        # impudence and admittance per unit of length
        self.R = R
        self.X = X
        self.B = B

        self.R0 = R0
        self.X0 = X0
        self.B0 = B0

        self.register(key='Imax', units='kA', tpe=float, definition='Current rating of the line', old_names=['rating'])
        self.register(key='Vnom', units='kV', tpe=float, definition='Voltage rating of the line')
        self.register(key='R', units='Ohm/km', tpe=float, definition='Positive-sequence resistance per km')
        self.register(key='X', units='Ohm/km', tpe=float, definition='Positive-sequence reactance per km')
        self.register(key='B', units='uS/km', tpe=float, definition='Positive-sequence shunt susceptance per km')
        self.register(key='R0', units='Ohm/km', tpe=float, definition='Zero-sequence resistance per km')
        self.register(key='X0', units='Ohm/km', tpe=float, definition='Zero-sequence reactance per km')
        self.register(key='B0', units='uS/km', tpe=float, definition='Zero-sequence shunt susceptance per km')

    def get_values(self, Sbase, length):
        """
        Get the per-unit values
        :param Sbase: Base power (MVA, always use 100MVA)
        :param length: length in km
        :return: R (p.u.), x(p.u.), B(p.u.), Rate (MVA)
        """
        Vn = self.Vnom
        Zbase = (Vn * Vn) / Sbase
        Ybase = 1.0 / Zbase

        R = np.round(self.R * length / Zbase, 6)
        X = np.round(self.X * length / Zbase, 6)
        B = np.round(self.B * 1e-6 * length / Ybase, 6)

        R0 = np.round(self.R0 * length / Zbase, 6)
        X0 = np.round(self.X0 * length / Zbase, 6)
        B0 = np.round(self.B0 * 1e-6 * length / Ybase, 6)

        # get the rating in MVA = kA * kV
        rate = self.Imax * Vn * np.sqrt(3)

        return R, X, B, R0, X0, B0, rate
