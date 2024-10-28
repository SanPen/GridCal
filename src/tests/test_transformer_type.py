# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import numpy as np

from GridCalEngine.Devices.Branches.transformer_type import TransformerType
from GridCalEngine.Devices.Branches.transformer3w import Transformer3W
from GridCalEngine.Devices.Substation.bus import Bus


def test_transformer_type() -> None:
    """
    Test the transformer conversion from short circuits study values to system per unit values
    :return:
    """
    Vhv = 21  # primary voltage in kV
    Vlv = 0.42  # secondary voltage kV
    Sn = 0.25  # nominal power in MVA
    Pcu = 2.35  # short circuit power (copper losses) kW
    Pfe = 0.27  # no load power (iron losses) kW
    I0 = 1.0  # no load voltage in %
    Vsc = 4.6  # short-circuit voltage in %

    obj = TransformerType(hv_nominal_voltage=Vhv,
                          lv_nominal_voltage=Vlv,
                          nominal_power=Sn,
                          copper_losses=Pcu,
                          short_circuit_voltage=Vsc,
                          iron_losses=Pfe,
                          no_load_current=I0,
                          gr_hv1=0.5, gx_hv1=0.5)

    Sbase = 100
    z_series, y_shunt = obj.get_impedances(VH=Vhv, VL=Vlv, Sbase=Sbase)

    assert np.allclose(z_series, 3.76 + 18.0117295j)
    assert np.allclose(y_shunt, 2.6532597915358445e-06 - 2.456722029199863e-05j)


def test_transformer3w_test() -> None:
    """
    This test checks the conversion from short circuits study values
    to system per unit values for the delta values of a 3W transformer
    """
    b1 = Bus(Vnom=138)
    b2 = Bus(Vnom=70.5)
    b3 = Bus(Vnom=13.8)
    tr3 = Transformer3W(bus1=b1, bus2=b2, bus3=b3)

    tr3.fill_from_design_values(V1=138.0, V2=70.5, V3=13.8,
                                Sn1=120.0, Sn2=24.0, Sn3=24.0,
                                Pcu12=109.974, Pcu23=22.846, Pcu31=23.596,
                                Vsc12=5.45, Vsc23=6.73, Vsc31=5.39,
                                Pfe=0.0, I0=0.0, Sbase=100.0)

    # expected values:
    r12 = 0.000482
    r23 = 0.002059
    r31 = 0.002069
    x12 = 0.028631
    x23 = 0.145566
    x31 = 0.113396
    assert np.isclose(r12, tr3.r12)
    assert np.isclose(r23, tr3.r23)
    assert np.isclose(r31, tr3.r31)
    assert np.isclose(x12, tr3.x12)
    assert np.isclose(x23, tr3.x23)
    assert np.isclose(x31, tr3.x31)


if __name__ == '__main__':
    # template_from_impedances()

    test_transformer_type()
