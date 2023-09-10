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

from GridCalEngine.Core.Devices.enumerations import BranchType
from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType, GCProp


class UndergroundLineType(EditableDevice):

    def __init__(self, name='UndergroundLine', idtag=None, rating=1, R=0, X=0, G=0, B=0, R0=0, X0=0, G0=0, B0=0):
        """
        Constructor
        :param name: name of the device
        :param rating: rating in kA
        :param R: Resistance of positive sequence in Ohm/km
        :param X: Reactance of positive sequence in Ohm/km
        :param G: Conductance of positive sequence in Ohm/km
        :param B: Susceptance of positive sequence in Ohm/km
        :param R0: Resistance of zero sequence in Ohm/km
        :param X0: Reactance of zero sequence in Ohm/km
        :param G0: Conductance of zero sequence in Ohm/km
        :param B0: Susceptance of zero sequence in Ohm/km
        :param tpe:
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                active=True,
                                device_type=DeviceType.UnderGroundLineDevice)

        self.tpe = BranchType.Line

        self.rating = rating

        # impedances and admittances per unit of length
        self.R = R
        self.X = X
        self.G = G
        self.B = B

        self.R0 = R0
        self.X0 = X0
        self.G0 = G0
        self.B0 = B0

        self.register(key='rating', units='kA', tpe=float, definition='Current rating of the cable')
        self.register(key='R', units='Ohm/km', tpe=float, definition='Positive-sequence resistance per km')
        self.register(key='X', units='Ohm/km', tpe=float, definition='Positive-sequence reactance per km')
        self.register(key='G', units='S/km', tpe=float, definition='Positive-sequence shunt conductance per km')
        self.register(key='B', units='S/km', tpe=float, definition='Positive-sequence shunt susceptance per km')
        self.register(key='R0', units='Ohm/km', tpe=float, definition='Zero-sequence resistance per km')
        self.register(key='X0', units='Ohm/km', tpe=float, definition='Zero-sequence reactance per km')
        self.register(key='G0', units='S/km', tpe=float, definition='Zero-sequence shunt conductance per km')
        self.register(key='B0', units='S/km', tpe=float, definition='Zero-sequence shunt susceptance per km')

    def z_series(self):
        """
        positive sequence series impedance in Ohm per unit of length
        """
        return self.R + 1j * self.X

    def y_shunt(self):
        """
        positive sequence shunt admittance in S per unit of length
        """
        return self.G + 1j * self.B

    def change_base(self, Sbase_old, Sbase_new):
        b = Sbase_new / Sbase_old

        self.R *= b
        self.X *= b
        self.G *= b
        self.B *= b

        self.R0 *= b
        self.X0 *= b
        self.G0 *= b
        self.B0 *= b

