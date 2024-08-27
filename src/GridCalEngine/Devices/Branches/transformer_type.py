# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from typing import Tuple, Union
from numpy import sqrt
from GridCalEngine.enumerations import TapChangerTypes
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Branches.tap_changer import TapChanger


class TransformerType(EditableDevice):

    def __init__(self,
                 hv_nominal_voltage: float = 0.0,
                 lv_nominal_voltage: float = 0.0,
                 nominal_power: float = 0.001,
                 copper_losses: float = 0.0,
                 iron_losses: float = 0.0,
                 no_load_current: float = 0.0,
                 short_circuit_voltage: float = 0.0,
                 gr_hv1: float = 0.5,
                 gx_hv1: float = 0.5,
                 total_positions: int = 5,
                 neutral_position: int = 2,
                 dV: float = 0.01,
                 asymmetry_angle: float = 90.0,
                 tc_type: TapChangerTypes = TapChangerTypes.NoRegulation,
                 name: str = 'TransformerType',
                 idtag: Union[None, str] = None) -> None:
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

        self._total_positions: int = total_positions
        self._neutral_position: int = neutral_position
        self._dV: float = dV
        self._asymmetry_angle: float = asymmetry_angle
        self._tc_type: TapChangerTypes = tc_type

        self._tap_module_min = 0.0
        self._tap_module_max = 0.0
        self._tap_phase_min = 0.0
        self._tap_phase_max = 0.0

        self.recalc_taps()

        self.register(key='HV', units='kV', tpe=float, definition='Nominal voltage al the high voltage side')
        self.register(key='LV', units='kV', tpe=float, definition='Nominal voltage al the low voltage side')
        self.register(key='Sn', units='MVA', tpe=float, definition='Nominal power', old_names=['rating'])
        self.register(key='Pcu', units='kW', tpe=float, definition='Copper losses')
        self.register(key='Pfe', units='kW', tpe=float, definition='Iron losses')
        self.register(key='I0', units='%', tpe=float, definition='No-load current')
        self.register(key='Vsc', units='%', tpe=float, definition='Short-circuit voltage')

        self.register(key='tc_type', units='', tpe=TapChangerTypes, definition='Regulation type')
        self.register(key='total_positions', units='', tpe=int, definition='Number of tap positions')
        self.register(key='dV', units='p.u.', tpe=float, definition='Voltage increment per step')
        self.register(key='neutral_position', units='', tpe=int, definition='neutral poition couting from zero')
        self.register(key='asymmetry_angle', units='deg', tpe=float, definition='Asymmetry_angle')

        self.register(key='tap_module_min', units='p.u.', tpe=float, definition='Min tap module', editable=False)
        self.register(key='tap_module_max', units='p.u.', tpe=float, definition='Max tap module', editable=False)
        self.register(key='tap_phase_min', units='rad', tpe=float, definition='Min tap phase', editable=False)
        self.register(key='tap_phase_max', units='rad', tpe=float, definition='Max tap phase', editable=False)

    @property
    def tap_module_min(self):
        """

        :return:
        """
        return self._tap_module_min

    @tap_module_min.setter
    def tap_module_min(self, val: float):
        if isinstance(val, float):
            self._tap_module_min = val
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a tap_module_min')

    @property
    def tap_module_max(self):
        """

        :return:
        """
        return self._tap_module_max

    @tap_module_max.setter
    def tap_module_max(self, val: float):
        if isinstance(val, float):
            self._tap_module_max = val
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a tap_module_min')

    @property
    def tap_phase_min(self):
        """

        :return:
        """
        return self._tap_phase_min

    @tap_phase_min.setter
    def tap_phase_min(self, val: float):
        if isinstance(val, float):
            self._tap_phase_min = val
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a tap_module_min')

    @property
    def tap_phase_max(self):
        """

        :return:
        """
        return self._tap_phase_max

    @tap_phase_max.setter
    def tap_phase_max(self, val: float):
        if isinstance(val, float):
            self._tap_phase_max = val
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a tap_module_min')

    @property
    def total_positions(self):
        """

        :return:
        """
        return self._total_positions

    @total_positions.setter
    def total_positions(self, value: int):
        if isinstance(value, int):
            self._total_positions = value
            self.recalc_taps()
        else:
            raise TypeError(f'Expected int but got {type(value)}')

    @property
    def neutral_position(self):
        """

        :return:
        """
        return self._neutral_position

    @neutral_position.setter
    def neutral_position(self, value: int):
        if isinstance(value, int):
            if 0 <= value < self._total_positions:
                self._neutral_position = value
                self.recalc_taps()
            else:
                pass
        else:
            raise TypeError(f'Expected int but got {type(value)}')

    @property
    def dV(self):
        """

        :return:
        """
        return self._total_positions

    @dV.setter
    def dV(self, value: float):
        if isinstance(value, float):
            self._dV = value
            self.recalc_taps()
        else:
            raise TypeError(f'Expected int but got {type(value)}')

    @property
    def asymmetry_angle(self):
        """

        :return:
        """
        return self._asymmetry_angle

    @asymmetry_angle.setter
    def asymmetry_angle(self, value: float):
        if isinstance(value, float):
            self._asymmetry_angle = value
            self.recalc_taps()
        else:
            raise TypeError(f'Expected float but got {type(value)}')

    @property
    def tc_type(self):
        """

        :return:
        """
        return self._tc_type

    @tc_type.setter
    def tc_type(self, value: TapChangerTypes):
        if isinstance(value, TapChangerTypes):
            self._tc_type = value
            self.recalc_taps()
        else:
            raise TypeError(f'Expected TapChangerTypes but got {type(value)}')

    def get_impedances(self, VH: float, VL: float, Sbase: float):
        """
        Compute the branch parameters of a transformer from the short circuit test
        values.
        :param VH: High voltage bus nominal voltage in kV
        :param VL: Low voltage bus nominal voltage in kV
        :param Sbase: Base power in MVA (normally 100 MVA)
        :return: Zseries and Yshunt in system per unit
        """

        z_series, y_shunt = get_impedances(VH_bus=VH,
                                           VL_bus=VL,
                                           Sn=self.Sn,
                                           HV=self.HV,
                                           LV=self.LV,
                                           Pcu=self.Pcu,
                                           Pfe=self.Pfe,
                                           I0=self.I0,
                                           Vsc=self.Vsc,
                                           Sbase=Sbase,
                                           GR_hv1=self.GR_hv1)

        return z_series, y_shunt

    def get_tap_changer(self) -> TapChanger:
        """
        Get tap changer object
        :return: TapChanger
        """
        return TapChanger(total_positions=self.total_positions,
                          neutral_position=self.neutral_position,
                          dV=self.dV,
                          asymmetry_angle=self.asymmetry_angle,
                          tc_type=self.tc_type)

    def recalc_taps(self):
        """

        :return:
        """
        tc = TapChanger(total_positions=self.total_positions,
                        neutral_position=self._neutral_position,
                        dV=self._dV,
                        asymmetry_angle=self._asymmetry_angle,
                        tc_type=self._tc_type)

        self._tap_module_min = tc.get_tap_module_min()
        self._tap_module_max = tc.get_tap_module_max()
        self._tap_phase_min = tc.get_tap_phase_min()
        self._tap_phase_max = tc.get_tap_phase_max()


def get_impedances(VH_bus: float, VL_bus: float, Sn: float, HV: float, LV: float,
                   Pcu: float, Pfe: float, I0: float, Vsc: float, Sbase: float,
                   GR_hv1: float) -> Tuple[complex, complex]:
    """
    Compute the branch parameters of a transformer from the short circuit test
    values.
    :param VH_bus: High voltage bus nominal voltage in kV
    :param VL_bus: Low voltage bus nominal voltage in kV
    :param Sn: Nominal power (MVA)
    :param HV: Transformer high voltage nominal voltage in kV
    :param LV: Transformer low voltage nominal voltage in kV
    :param Pcu: Copper losses, AKA resistive losses (kW)
    :param Pfe: Iron losses, AKA magnetic losses (kW)
    :param I0: No-load current (%)
    :param Vsc: Short-circuit voltage (%)
    :param Sbase: Base power in MVA (normally 100 MVA)
    :param GR_hv1: Share of impedance of towards the high voltage side (0 to 1)
    :return: Zseries and Yshunt in system per unit
    """

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
    z_base_hv = (HV * HV) / Sn
    z_base_lv = (LV * LV) / Sn

    z_series_hv = zs * GR_hv1 * z_base_hv  # Ohm
    z_series_lv = zs * (1.0 - GR_hv1) * z_base_lv  # Ohm
    z_shunt_hv = zsh * GR_hv1 * z_base_hv  # Ohm
    z_shunt_lv = zsh * (1.0 - GR_hv1) * z_base_lv  # Ohm

    # convert impedances from ohms to system per unit
    z_base_hv_sys = (VH_bus * VH_bus) / Sbase
    z_base_lv_sys = (VL_bus * VL_bus) / Sbase

    z_series = z_series_hv / z_base_hv_sys + z_series_lv / z_base_lv_sys
    z_shunt = z_shunt_hv / z_base_hv_sys + z_shunt_lv / z_base_lv_sys

    if z_shunt != 0:
        y_shunt = 1 / z_shunt
    else:
        y_shunt = 0j

    return z_series, y_shunt


def reverse_transformer_short_circuit_study(R: float, X: float, G: float, B: float, rate: float,
                                            Sbase: float) -> Tuple[float, float, float, float, float]:
    """
    Get the short circuit study values from the impedance values
    :param R:
    :param X:
    :param G:
    :param B:
    :param rate:
    :param Sbase: base power in MVA (100 MVA)
    :return:
    """
    """
    
    :param transformer_obj: Transformer2W
    :param Sbase: 
    :return: Pfe, Pcu, Vsc, I0, Sn
    """

    # Change the impedances to the system base
    base_change = Sbase / (rate + 1e-9)

    R = R / base_change
    X = X / base_change
    G = G / base_change
    B = B / base_change
    Sn = rate

    zsc = sqrt(R * R + X * X)
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
        Pfe = 0
        I0 = 0

    return Pfe, Pcu, Vsc, I0, Sn
