# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class UndergroundLineType(EditableDevice):

    def __init__(self, name: str = 'UndergroundLine', idtag: None | str = None, Imax: float = 1.0,
                 Vnom: float = 1.0, R: float = 0.0, X: float = 0.0, B: float = 0.0,
                 R0: float = 0.0, X0: float = 0.0, B0: float = 0.0) -> None:
        """
        Constructor
        :param name: name of the device
        :param Imax: rating in kA
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
                                code='',
                                device_type=DeviceType.UnderGroundLineDevice)

        self.Imax = float(Imax)
        self.Vnom = float(Vnom)

        # impudence and admittance per unit of length
        self.R = float(R)
        self.X = float(X)
        self.B = float(B)

        self.R0 = float(R0)
        self.X0 = float(X0)
        self.B0 = float(B0)

        self.register(key='Imax', units='kA', tpe=float, definition='Current rating of the line', old_names=['rating'])
        self.register(key='Vnom', units='kV', tpe=float, definition='Voltage rating of the line')
        self.register(key='R', units='Ohm/km', tpe=float, definition='Positive-sequence resistance per km')
        self.register(key='X', units='Ohm/km', tpe=float, definition='Positive-sequence reactance per km')
        self.register(key='B', units='uS/km', tpe=float, definition='Positive-sequence shunt susceptance per km')
        self.register(key='R0', units='Ohm/km', tpe=float, definition='Zero-sequence resistance per km')
        self.register(key='X0', units='Ohm/km', tpe=float, definition='Zero-sequence reactance per km')
        self.register(key='B0', units='uS/km', tpe=float, definition='Zero-sequence shunt susceptance per km')

    def get_values(self, Sbase: float, length: float):
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
        B = np.round(self.B * 1e6 * length / Ybase, 6)

        R0 = np.round(self.R0 * length / Zbase, 6)
        X0 = np.round(self.X0 * length / Zbase, 6)
        B0 = np.round(self.B0 * 1e6 * length / Ybase, 6)

        # get the rating in MVA = kA * kV
        rate = self.Imax * Vn * np.sqrt(3)

        return R, X, B, R0, X0, B0, rate

    def z_series(self):
        """
        positive sequence series impedance in Ohm per unit of length
        """
        return self.R + 1j * self.X

    def y_shunt(self):
        """
        positive sequence shunt admittance in S per unit of length
        """
        return 1j * self.B

    def change_base(self, Sbase_old, Sbase_new):
        """
        change the per unit base
        :param Sbase_old: old base in MVA
        :param Sbase_new: new base in MVA
        """
        b = Sbase_new / Sbase_old

        self.R *= b
        self.X *= b
        self.B *= b

        self.R0 *= b
        self.X0 *= b
        self.B0 *= b

