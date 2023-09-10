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

from GridCalEngine.Core.Devices import TransformerType
# from math import sqrt


def test_transformer_type():

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

    assert np.allclose(z_series, 3.76+18.01j, rtol=0.01)
    assert np.allclose(y_shunt, 2.6532597915358445e-06-2.456722029199863e-05j, rtol=0.01)


if __name__ == '__main__':
    # template_from_impedances()

    test_transformer_type()
