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

from numpy import sqrt

from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType


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

    def __init__(self,
                 hv_nominal_voltage=0.0,
                 lv_nominal_voltage=0.0,
                 nominal_power=0.001,
                 copper_losses=0.0,
                 iron_losses=0.0,
                 no_load_current=0.0,
                 short_circuit_voltage=0.0,
                 gr_hv1=0.5,
                 gx_hv1=0.5,
                 name='TransformerType', idtag=None):
        """
        Transformer template from the short circuit study
        :param hv_nominal_voltage: Nominal voltage of the high voltage side in kV
        :param lv_nominal_voltage: Nominal voltage of the low voltage side in kV
        :param nominal_power: Nominal power of the machine in MVA
        :param copper_losses: Copper losses in kW
        :param iron_losses: Iron losses in kW
        :param no_load_current: No load current in %
        :param short_circuit_voltage: Short circuit voltage in %
        :param gr_hv1: proportion of the resistance in the HV side (i.e. 0.5)
        :param gx_hv1: proportion of the reactance in the HV side (i.e. 0.5)
        :param name: Name of the device template
        :param idtag: device UUID
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                device_type=DeviceType.TransformerTypeDevice)

        self.HV = hv_nominal_voltage

        self.LV = lv_nominal_voltage

        self.Sn = nominal_power

        self.Pcu = copper_losses

        self.Pfe = iron_losses

        self.I0 = no_load_current

        self.Vsc = short_circuit_voltage

        self.GR_hv1 = gr_hv1

        self.GX_hv1 = gx_hv1

        self.register(key='HV', units='kV', tpe=float, definition='Nominal voltage al the high voltage side')
        self.register(key='LV', units='kV', tpe=float, definition='Nominal voltage al the low voltage side')
        self.register(key='Sn', units='MVA', tpe=float, definition='Nominal power', old_names=['rating'])
        self.register(key='Pcu', units='kW', tpe=float, definition='Copper losses')
        self.register(key='Pfe', units='kW', tpe=float, definition='Iron losses')
        self.register(key='I0', units='%', tpe=float, definition='No-load current')
        self.register(key='Vsc', units='%', tpe=float, definition='Short-circuit voltage')

    def get_impedances(self, VH, VL, Sbase):
        """
        Compute the branch parameters of a transformer from the short circuit test
        values.
        :param VH: High voltage bus nominal voltage in kV
        :param VL: Low voltage bus nominal voltage in kV
        :param Sbase: Base power in MVA (normally 100 MVA)
        :return: Zseries and Yshunt in system per unit
        """

        Sn = self.Sn  # Nominal power (MVA)
        Pcu = self.Pcu    # Copper losses, AKA resistive losses (kW)
        Pfe = self.Pfe    # Iron losses, AKA magnetic losses (kW)
        I0 = self.I0      # No-load current (%)
        Vsc = self.Vsc    # Short circuit voltage(%)

        # Series impedance
        zsc = Vsc / 100.0
        rsc = (Pcu / 1000.0) / Sn
        if rsc < zsc:
            xsc = sqrt(zsc ** 2 - rsc ** 2)
        else:
            xsc = 0.0

        # series impedance in p.u. of the machine
        zs = rsc + 1j * xsc

        # Shunt impedance (leakage)
        if Pfe > 0.0 and I0 > 0.0:

            rfe = Sn / (Pfe / 1000.0)
            zm = 1.0 / (I0 / 100.0)
            val = (1.0 / (zm ** 2)) - (1.0 / (rfe ** 2))
            if val > 0:
                xm = 1.0 / sqrt(val)
                rm = sqrt(xm * xm - zm * zm)
            else:
                xm = 0.0
                rm = 0.0

        else:

            rm = 0.0
            xm = 0.0

        # shunt impedance in p.u. of the machine
        zsh = rm + 1j * xm

        # convert impedances from machine per unit to ohms
        z_base_hv = (self.HV * self.HV) / Sn
        z_base_lv = (self.LV * self.LV) / Sn

        z_series_hv = zs * self.GR_hv1 * z_base_hv  # Ohm
        z_series_lv = zs * (1 - self.GR_hv1) * z_base_lv  # Ohm
        z_shunt_hv = zsh * self.GR_hv1 * z_base_hv  # Ohm
        z_shunt_lv = zsh * (1 - self.GR_hv1) * z_base_lv  # Ohm

        # convert impedances from ohms to system per unit
        z_base_hv_sys = (VH * VH) / Sbase
        z_base_lv_sys = (VL * VL) / Sbase

        z_series = z_series_hv / z_base_hv_sys + z_series_lv / z_base_lv_sys
        z_shunt = z_shunt_hv / z_base_hv_sys + z_shunt_lv / z_base_lv_sys

        if z_shunt != 0:
            y_shunt = 1 / z_shunt
        else:
            y_shunt = 0j

        return z_series, y_shunt
