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

from numpy import sqrt
from GridCal.Engine.Devices.types import BranchType
from GridCal.Engine.Devices.meta_devices import EditableDevice, DeviceType, GCProp


class TransformerType(EditableDevice):
    """
    Arguments:

        **hv_nominal_voltage** (float, 0.0): Primary side nominal voltage in kV (tied to the Branch's `bus_from`)

        **lv_nominal_voltage** (float, 0.0): Secondary side nominal voltage in kV (tied to the Branch's `bus_to`)

        **nominal_power** (float, 0.0): Transformer nominal apparent power in MVA

        **copper_losses** (float, 0.0): Copper losses in kW (also known as short circuit power)

        **iron_losses** (float, 0.0): Iron losses in kW (also known as no-load power)

        **no_load_current** (float, 0.0): No load current in %

        **short_circuit_voltage** (float, 0.0): Short circuit voltage in %

        **gr_hv1** (float, 0.5): Resistive contribution to the primary side in per unit (at the Branch's `bus_from`)

        **gx_hv1** (float, 0.5): Reactive contribution to the primary side in per unit (at the Branch's `bus_from`)

        **name** (str, "TransformerType"): Name of the type

        **tpe** (BranchType, BranchType.Transformer): Device type enumeration

    """

    def __init__(self, hv_nominal_voltage=0, lv_nominal_voltage=0, nominal_power=0.001, copper_losses=0, iron_losses=0,
                 no_load_current=0, short_circuit_voltage=0, gr_hv1=0.5, gx_hv1=0.5,
                 name='TransformerType', tpe=BranchType.Transformer):
        """

        :param hv_nominal_voltage:
        :param lv_nominal_voltage:
        :param nominal_power:
        :param copper_losses:
        :param iron_losses:
        :param no_load_current:
        :param short_circuit_voltage:
        :param gr_hv1:
        :param gx_hv1:
        :param name:
        :param tpe:
        """
        EditableDevice.__init__(self,
                                name=name,
                                active=True,
                                device_type=DeviceType.TransformerTypeDevice,
                                editable_headers={'name': GCProp('', str, "Name of the transformer type"),
                                                  'HV': GCProp('kV', float, "Nominal voltage al the high voltage side"),
                                                  'LV': GCProp('kV', float, "Nominal voltage al the low voltage side"),
                                                  'rating': GCProp('MVA', float, "Nominal power"),
                                                  'Pcu': GCProp('kW', float, "Copper losses"),
                                                  'Pfe': GCProp('kW', float, "Iron losses"),
                                                  'I0': GCProp('%', float, "No-load current"),
                                                  'Vsc': GCProp('%', float, "Short-circuit voltage")},
                                non_editable_attributes=list(),
                                properties_with_profile={})

        self.tpe = tpe

        self.HV = hv_nominal_voltage

        self.LV = lv_nominal_voltage

        self.rating = nominal_power

        self.Pcu = copper_losses

        self.Pfe = iron_losses

        self.I0 = no_load_current

        self.Vsc = short_circuit_voltage

        self.GR_hv1 = gr_hv1

        self.GX_hv1 = gx_hv1

    def get_impedances(self):
        """
        Compute the branch parameters of a transformer from the short circuit test
        values.

        Returns:

            **zs** (complex): Series impedance in per unit

            **zsh** (complex): Shunt impedance in per unit
        """

        Sn = self.rating
        Pcu = self.Pcu
        Pfe = self.Pfe
        I0 = self.I0
        Vsc = self.Vsc

        # Series impedance
        zsc = Vsc / 100.0
        rsc = (Pcu / 1000.0) / Sn
        xsc = sqrt(zsc ** 2 - rsc ** 2)
        zs = rsc + 1j * xsc

        # Shunt impedance (leakage)
        if Pfe > 0.0 and I0 > 0.0:

            rfe = Sn / (Pfe / 1000.0)
            zm = 1.0 / (I0 / 100.0)
            xm = 1.0 / sqrt((1.0 / (zm ** 2)) - (1.0 / (rfe ** 2)))
            rm = sqrt(xm * xm - zm * zm)

        else:

            rm = 0.0
            xm = 0.0

        zsh = rm + 1j * xm

        return zs, zsh

