# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
from math import sqrt

from GridCal.Engine.Devices.transformer import TransformerType


def test_transformer_definition():
    Vf = 20.0  # kV
    Vt = 0.4  # kV
    Sn = 0.5  # MVA
    Vsc_ = 6.0  # %
    Pcu_ = 6.0  # kW
    # Pfe_ = 1.4  # kW
    # I0_ = 0.28  # %
    Pfe_ = 0.0  # kW
    I0_ = 0.0  # %
    tpe = TransformerType(hv_nominal_voltage=Vf,
                          lv_nominal_voltage=Vt,
                          nominal_power=Sn,
                          copper_losses=Pcu_,
                          iron_losses=Pfe_,
                          no_load_current=I0_,
                          short_circuit_voltage=Vsc_,
                          gr_hv1=0.5,
                          gx_hv1=0.5)
    z, zl = tpe.get_impedances(VH=Vf, VL=Vt, Sbase=100)
    print(z)
    print(zl)
    # ------------------------------------------------------------------------------------------------------------------
    # Revert the calcs
    # ------------------------------------------------------------------------------------------------------------------
    if zl.real > 0 and zl.imag > 0:
        yl = 1.0 / zl
        G = yl.real
        B = yl.imag
    else:
        G = 0
        B = 0
    R = z.real
    X = z.imag
    Sn = Sn
    print()
    print('R', R)
    print('X', X)
    print('G', G)
    print('B', B)
    zsc = sqrt(R * R + 1 / (X * X))
    Vsc = 100.0 * zsc
    Pcu = R * Sn * 1000.0
    if abs(G) > 0.0 and abs(B) > 0.0:
        zl = 1.0 / complex(G, B)
        rfe = zl.real
        xm = zl.imag

        Pfe = 1000.0 * Sn / rfe

        k = 1 / (rfe * rfe) + 1 / (xm * xm)
        I0 = 100.0 * sqrt(k)
    else:
        Pfe = 1e20
        I0 = 1e20
    print('Vsc', Vsc, Vsc_)
    print('Pcu', Pcu, Pcu_)
    print('I0', I0, I0_)
    print('Pfe', Pfe, Pfe_)
    tpe2 = TransformerType(hv_nominal_voltage=Vf,
                           lv_nominal_voltage=Vt,
                           nominal_power=Sn,
                           copper_losses=Pcu,
                           iron_losses=Pfe,
                           no_load_current=I0,
                           short_circuit_voltage=Vsc,
                           gr_hv1=0.5,
                           gx_hv1=0.5)
    z2, zl2 = tpe2.get_impedances(VH=Vf, VL=Vt, Sbase=100)
    print(z2)
    print(zl2)


if __name__ == '__main__':
    test_transformer_definition()
