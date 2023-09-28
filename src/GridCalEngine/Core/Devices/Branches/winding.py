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

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import WindingsConnection, BuildStatus
from GridCalEngine.Core.Devices.editable_device import DeviceType
from GridCalEngine.Core.Devices.Branches.transformer import TransformerControlType
from GridCalEngine.Core.Devices.Branches.templates.parent_branch import ParentBranch
from GridCalEngine.Core.Devices.Branches.templates.transformer_type import TransformerType
from GridCalEngine.Core.Devices.Branches.tap_changer import TapChanger


class Winding(ParentBranch):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, HV=None, LV=None,
                 name='Winding', idtag=None, code='', r=1e-20, x=1e-20, g=1e-20, b=1e-20, rate=1.0, tap_module=1.0,
                 tap_module_max=1.2, tap_module_min=0.5, tap_phase=0.0, tap_phase_max=6.28, tap_phase_min=-6.28, active=True,
                 tolerance=0, cost=100.0, mttf=0, mttr=0, vset=1.0, Pset=0, bus_to_regulated=False, temp_base=20,
                 temp_oper=20, alpha=0.00330, control_mode: TransformerControlType = TransformerControlType.fixed,
                 template: TransformerType = None, rate_prof=None, Cost_prof=None, active_prof=None,
                 temp_oper_prof=None, tap_module_prof=None, tap_phase_prof=None, contingency_factor=1.0,
                 contingency_enabled=True, monitor_loading=True, contingency_factor_prof=None, r0=1e-20, x0=1e-20,
                 g0=1e-20, b0=1e-20, r2=1e-20, x2=1e-20, g2=1e-20, b2=1e-20,
                 conn: WindingsConnection = WindingsConnection.GG, capex=0, opex=0,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """

        :param bus_from: "From" :ref:`bus<Bus>` object
        :param bus_to: "To" :ref:`bus<Bus>` object
        :param HV: Higher voltage value in kV
        :param LV: Lower voltage value in kV
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary id
        :param r: resistance in per unit
        :param x: reactance in per unit
        :param g: shunt conductance in per unit
        :param b: shunt susceptance in per unit
        :param rate: rate in MVA
        :param tap_module: tap module in p.u.
        :param tap_module_max: maximum tap module
        :param tap_module_min: minimum tap module
        :param tap_phase: phase shift angle (rad)
        :param tap_phase_max: maximum tap phase (rad)
        :param tap_phase_min: minimum tap phase (rad)
        :param active: Is the branch active?
        :param tolerance: Tolerance specified for the branch impedance in %
        :param cost: Cost of overload (€/MW)
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param vset: Voltage set-point of the voltage controlled bus in per unit
        :param Pset: Power set point
        :param bus_to_regulated: Is the `bus_to` voltage regulated by this branch?
        :param temp_base: Base temperature at which `r` is measured in °C
        :param temp_oper: Operating temperature in °C
        :param alpha: Thermal constant of the material in °C
        :param control_mode: Control model
        :param template: Branch template
        :param rate_prof: Rating profile
        :param Cost_prof: Overload cost profile
        :param active_prof: Active profile
        :param temp_oper_prof: Operational temperature profile
        :param tap_module_prof: profile of tap modeules
        :param tap_phase_prof: profile of tap angles
        :param contingency_factor: Rating factor in case of contingency
        :param contingency_enabled: enabled for contingencies (Legacy)
        :param monitor_loading: monitor the loading (used in OPF)
        :param contingency_factor_prof: profile of contingency ratings
        :param r0: zero-sequence resistence (p.u.)
        :param x0: zero-sequence reactance (p.u.)
        :param g0: zero-sequence conductance (p.u.)
        :param b0: zero-sequence susceptance (p.u.)
        :param r2: negative-sequence resistence (p.u.)
        :param x2: negative-sequence reactance (p.u.)
        :param g2: negative-sequence conductance (p.u.)
        :param b2: negative-sequence susceptance (p.u.)
        :param conn: transformer connection type
        :param capex: Cost of investment (€/MW)
        :param opex: Cost of operation (€/MWh)
        :param build_status: build status (now time)
        """
        ParentBranch.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              cn_from=None,
                              cn_to=None,
                              active=active,
                              active_prof=active_prof,
                              rate=rate,
                              rate_prof=rate_prof,
                              contingency_factor=contingency_factor,
                              contingency_factor_prof=contingency_factor_prof,
                              contingency_enabled=contingency_enabled,
                              monitor_loading=monitor_loading,
                              mttf=mttf,
                              mttr=mttr,
                              build_status=build_status,
                              capex=capex,
                              opex=opex,
                              Cost=cost,
                              Cost_prof=Cost_prof,
                              device_type=DeviceType.WindingDevice)

        # set the high and low voltage values
        self.HV = 0
        self.LV = 0
        self.set_hv_and_lv(HV, LV)

        # List of measurements
        self.measurements = list()

        # branch impedance tolerance
        self.tolerance = tolerance

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x
        self.G = g
        self.B = b

        self.R0 = r0
        self.X0 = x0
        self.G0 = g0
        self.B0 = b0

        self.R2 = r2
        self.X2 = x2
        self.G2 = g2
        self.B2 = b2

        self.conn = conn

        # Conductor base and operating temperatures in ºC
        self.temp_base = temp_base
        self.temp_oper = temp_oper

        self.temp_oper_prof = temp_oper_prof

        # Conductor thermal constant (1/ºC)
        self.alpha = alpha

        # tap changer object
        self.tap_changer = TapChanger()

        # Tap module
        if tap_module != 0:
            self.tap_module = tap_module
            self.tap_changer.set_tap(self.tap_module)
        else:
            self.tap_module = self.tap_changer.get_tap()

        self.tap_module_prof = tap_module_prof
        self.tap_module_max = tap_module_max
        self.tap_module_min = tap_module_min

        # Tap angle
        self.tap_phase = tap_phase
        self.tap_phase_prof = tap_phase_prof
        self.tap_phase_max = tap_phase_max
        self.tap_phase_min = tap_phase_min

        # type template
        self.template = template

        self.vset = vset
        self.Pset = Pset

        self.control_mode = control_mode

        self.bus_to_regulated = bus_to_regulated

        if bus_to_regulated and self.control_mode == TransformerControlType.fixed:
            print(self.name, self.idtag, 'Overriding to V controller')
            self.control_mode = TransformerControlType.Vt

        self.register(key='HV', units='kV', tpe=float, definition='High voltage rating')
        self.register(key='LV', units='kV', tpe=float, definition='Low voltage rating')

        self.register(key='R', units='p.u.', tpe=float, definition='Total positive sequence resistance.')
        self.register(key='X', units='p.u.', tpe=float, definition='Total positive sequence reactance.')
        self.register(key='G', units='p.u.', tpe=float, definition='Total positive sequence shunt conductance.')
        self.register(key='B', units='p.u.', tpe=float, definition='Total positive sequence shunt susceptance.')
        self.register(key='R0', units='p.u.', tpe=float, definition='Total zero sequence resistance.')
        self.register(key='X0', units='p.u.', tpe=float, definition='Total zero sequence reactance.')
        self.register(key='G0', units='p.u.', tpe=float, definition='Total zero sequence shunt conductance.')
        self.register(key='B0', units='p.u.', tpe=float, definition='Total zero sequence shunt susceptance.')
        self.register(key='R2', units='p.u.', tpe=float, definition='Total negative sequence resistance.')
        self.register(key='X2', units='p.u.', tpe=float, definition='Total negative sequence reactance.')
        self.register(key='G2', units='p.u.', tpe=float, definition='Total negative sequence shunt conductance.')
        self.register(key='B2', units='p.u.', tpe=float, definition='Total negative sequence shunt susceptance.')
        self.register(key='conn', units='', tpe=WindingsConnection,
                      definition='Windings connection (from, to):G: grounded starS: ungrounded starD: delta')
        self.register(key='tolerance', units='%', tpe=float,
                      definition='Tolerance expected for the impedance values7% is expected for transformers0% for lines.')
        self.register(key='tap_module', units='', tpe=float, definition='Tap changer module, it a value close to 1.0',
                      profile_name='tap_module_prof')
        self.register(key='tap_module_max', units='', tpe=float, definition='Tap changer module max value')
        self.register(key='tap_module_min', units='', tpe=float, definition='Tap changer module min value')
        self.register(key='tap_phase', units='rad', tpe=float, definition='Angle shift of the tap changer.',
                      profile_name='tap_phase_prof', old_names=['angle'])

        self.register(key='tap_phase_max', units='rad', tpe=float, definition='Max angle.', old_names=['angle_max'])
        self.register(key='tap_phase_min', units='rad', tpe=float, definition='Min angle.', old_names=['angle_min'])
        self.register(key='control_mode', units='', tpe=TransformerControlType,
                      definition='Control type of the transformer')
        self.register(key='vset', units='p.u.', tpe=float,
                      definition='Objective voltage at the "to" side of the bus when regulating the tap.')
        self.register(key='Pset', units='p.u.', tpe=float,
                      definition='Objective power at the "from" side of when regulating the angle.')
        self.register(key='temp_base', units='ºC', tpe=float, definition='Base temperature at which R was measured.')
        self.register(key='temp_oper', units='ºC', tpe=float, definition='Operation temperature to modify R.',
                      profile_name='temp_oper_prof')
        self.register(key='alpha', units='1/ºC', tpe=float,
                      definition='Thermal coefficient to modify R,around a reference temperatureusing a linear '
                                 'approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,'
                                 'Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330')
        self.register(key='template', units='', tpe=DeviceType.TransformerTypeDevice, definition='', editable=False)

    def set_hv_and_lv(self, HV: float, LV: float):
        """
        set the high and low voltage values
        :param HV: higher voltage value (kV)
        :param LV: lower voltage value (kV)
        """
        if self.bus_from is not None and self.bus_to is not None:
            vh = max(self.bus_from.Vnom, self.bus_to.Vnom)
            vl = min(self.bus_from.Vnom, self.bus_to.Vnom)
        else:
            vh = 1.0
            vl = 1.0

        if HV is None:
            self.HV = vh
        else:
            self.HV = HV

        if LV is None:
            self.LV = vl
        else:
            self.LV = LV

    @property
    def R_corrected(self):
        """
        Returns a temperature corrected resistance based on a formula provided by:
        NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.R * (1 + self.alpha * (self.temp_oper - self.temp_base))

    def change_base(self, Sbase_old, Sbase_new):

        b = Sbase_new / Sbase_old

        self.R *= b
        self.X *= b
        self.G *= b
        self.B *= b

    def get_weight(self):
        return np.sqrt(self.R * self.R + self.X * self.X)

    def copy(self, bus_dict=None):
        """
        Returns a copy of the branch
        @return: A new  with the same content as this
        """

        if bus_dict is None:
            f = self.bus_from
            t = self.bus_to
        else:
            f = bus_dict[self.bus_from]
            t = bus_dict[self.bus_to]

        # z_series = complex(self.R, self.X)
        # y_shunt = complex(self.G, self.B)
        b = Winding(bus_from=f,
                    bus_to=t,
                    name=self.name,
                    r=self.R,
                    x=self.X,
                    g=self.G,
                    b=self.B,
                    rate=self.rate,
                    tap_module=self.tap_module,
                    tap_phase=self.tap_phase,
                    active=self.active,
                    mttf=self.mttf,
                    mttr=self.mttr,
                    bus_to_regulated=self.bus_to_regulated,
                    vset=self.vset,
                    temp_base=self.temp_base,
                    temp_oper=self.temp_oper,
                    alpha=self.alpha,
                    template=self.template,
                    opex=self.opex,
                    capex=self.capex)

        b.measurements = self.measurements

        b.active_prof = self.active_prof
        b.rate_prof = self.rate_prof
        b.Cost_prof = self.Cost_prof

        return b

    def flip(self):
        """
        Change the terminals' positions
        """
        F, T = self.bus_from, self.bus_to
        self.bus_to, self.bus_from = F, T

    def tap_up(self):
        """
        Move the tap changer one position up
        """
        self.tap_changer.tap_up()
        self.tap_module = self.tap_changer.get_tap()

    def tap_down(self):
        """
        Move the tap changer one position up
        """
        self.tap_changer.tap_down()
        self.tap_module = self.tap_changer.get_tap()

    def apply_tap_changer(self, tap_changer: TapChanger):
        """
        Apply a new tap changer

        Argument:

            **tap_changer** (:class:`GridCalEngine.Devices.branch.TapChanger`): Tap changer object

        """
        self.tap_changer = tap_changer

        if self.tap_module != 0:
            self.tap_changer.set_tap(self.tap_module)
        else:
            self.tap_module = self.tap_changer.get_tap()

    def get_sorted_buses_voltages(self):
        """
        GEt the sorted bus voltages
        :return: high voltage, low voltage
        """
        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom
        if bus_f_v > bus_t_v:
            return bus_f_v, bus_t_v
        else:
            return bus_t_v, bus_f_v

    def get_max_bus_nominal_voltage(self):
        return max(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_min_bus_nominal_voltage(self):
        return min(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_from_to_nominal_voltages(self):

        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom

        dhf = abs(self.HV - bus_f_v)
        dht = abs(self.HV - bus_t_v)

        if dhf < dht:
            # the HV side is on the from side
            tpe_f_v = self.HV
            tpe_t_v = self.LV
        else:
            # the HV side is on the to side
            tpe_t_v = self.HV
            tpe_f_v = self.LV

        return tpe_f_v, tpe_t_v

    def get_virtual_taps(self):
        """
        Get the branch virtual taps

        The virtual taps generate when a transformer nominal winding voltage differs
        from the bus nominal voltage.

        Returns:

            **tap_f** (float, 1.0): Virtual tap at the *from* side

            **tap_t** (float, 1.0): Virtual tap at the *to* side

        """
        # resolve how the transformer is actually connected and set the virtual taps
        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom

        # obtain the nominal voltages at the from and to sides
        tpe_f_v, tpe_t_v = self.get_from_to_nominal_voltages()

        tap_f = tpe_f_v / bus_f_v if bus_f_v > 0 else 1.0
        tap_t = tpe_t_v / bus_t_v if bus_t_v > 0 else 1.0

        if tap_f == 0.0:
            tap_f = 1.0

        if tap_t == 0.0:
            tap_t = 1.0

        return tap_f, tap_t

    def apply_template(self, obj: TransformerType, Sbase, logger=Logger()):
        """
        Apply a branch template to this object

        Arguments:
            **obj**: TransformerType or Tower object
            **Sbase** (float): circuit base power in MVA
            **logger** (list, []): Log list
        """
        if isinstance(obj, TransformerType):

            VH, VL = self.get_sorted_buses_voltages()

            # get the transformer impedance in the base of the transformer
            z_series, y_shunt = obj.get_impedances(VH=VH, VL=VL, Sbase=Sbase)

            self.R = np.round(z_series.real, 6)
            self.X = np.round(z_series.imag, 6)
            self.G = np.round(y_shunt.real, 6)
            self.B = np.round(y_shunt.imag, 6)

            self.rate = obj.Sn

            self.HV = obj.HV
            self.LV = obj.LV

            if self.template is not None:
                if obj != self.template:
                    self.template = obj
                else:
                    logger.add_error('Template not recognised', self.name)
            else:
                self.template = obj

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        data = list()
        for name, properties in self.editable_headers.items():
            obj = getattr(self, name)

            if properties.tpe == DeviceType.BusDevice:
                obj = obj.idtag

            elif properties.tpe == DeviceType.TransformerTypeDevice:
                if obj is None:
                    obj = ''
                else:
                    obj = obj.idtag

            elif properties.tpe not in [str, float, int, bool]:
                obj = str(obj)

            data.append(obj)
        return data

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        # get the virtual taps
        tap_f, tap_t = self.get_virtual_taps()

        # get the nominal voltages
        v_from, v_to = self.get_from_to_nominal_voltages()

        '''
        TransformerControlType(Enum):
        fixed = '0:Fixed'
        Pt = '1:Pt'
        Qt = '2:Qt'
        PtQt = '3:Pt+Qt'
        Vt = '4:Vt'
        PtVt = '5:Pt+Vt'
        
        '''
        control_modes = {TransformerControlType.fixed: 0,
                         TransformerControlType.Vt: 1,
                         TransformerControlType.Pt: 2,
                         TransformerControlType.PtVt: 3,
                         TransformerControlType.Qt: 4,
                         TransformerControlType.PtQt: 5}
        if version == 2:
            d = {'id': self.idtag,
                 'type': 'transformer',
                 'phases': 'ps',
                 'name': self.name,
                 'name_code': self.code,
                 'bus_from': self.bus_from.idtag,
                 'bus_to': self.bus_to.idtag,
                 'active': self.active,
                 'rate': self.rate,
                 'Vnomf': v_from,
                 'Vnomt': v_to,
                 'hv': self.HV,
                 'lv': self.LV,
                 'r': self.R,
                 'x': self.X,
                 'g': self.G,
                 'b': self.B,
                 'tap_module': self.tap_module,
                 'min_tap_module': self.tap_module_min,
                 'max_tap_module': self.tap_module_max,
                 'id_tap_module_table': "",

                 'tap_angle': self.tap_phase,
                 'min_tap_angle': self.tap_phase_min,
                 'max_tap_angle': self.tap_phase_max,
                 'id_tap_angle_table': "",

                 'control_mode': control_modes[self.control_mode],

                 # 'min_tap_position': self.tap_changer.min_tap,
                 # 'max_tap_position': self.tap_changer.max_tap,
                 # 'tap_inc_reg_down': self.tap_changer.inc_reg_down,
                 # 'tap_inc_reg_up': self.tap_changer.inc_reg_up,
                 # 'virtual_tap_from': tap_f,
                 # 'virtual_tap_to': tap_t,
                 # 'bus_to_regulated': self.bus_to_regulated,

                 'vset': self.vset,
                 'pset': self.Pset,

                 'base_temperature': self.temp_base,
                 'operational_temperature': self.temp_oper,
                 'alpha': self.alpha
                 }

        elif version == 3:
            d = {'id': self.idtag,
                 'type': 'transformer',
                 'phases': 'ps',
                 'name': self.name,
                 'name_code': self.code,
                 'bus_from': self.bus_from.idtag,
                 'bus_to': self.bus_to.idtag,
                 'active': self.active,
                 'rate': self.rate,
                 'contingency_factor1': self.contingency_factor,
                 'contingency_factor2': self.contingency_factor,
                 'contingency_factor3': self.contingency_factor,

                 'Vnomf': v_from,
                 'Vnomt': v_to,
                 'hv': self.HV,
                 'lv': self.LV,
                 'r': self.R,
                 'x': self.X,
                 'g': self.G,
                 'b': self.B,
                 'tap_module': self.tap_module,
                 'min_tap_module': self.tap_module_min,
                 'max_tap_module': self.tap_module_max,
                 'id_tap_module_table': "",

                 'tap_angle': self.tap_phase,
                 'min_tap_angle': self.tap_phase_min,
                 'max_tap_angle': self.tap_phase_max,
                 'id_tap_angle_table': "",

                 'control_mode': control_modes[self.control_mode],

                 # 'min_tap_position': self.tap_changer.min_tap,
                 # 'max_tap_position': self.tap_changer.max_tap,
                 # 'tap_inc_reg_down': self.tap_changer.inc_reg_down,
                 # 'tap_inc_reg_up': self.tap_changer.inc_reg_up,
                 # 'virtual_tap_from': tap_f,
                 # 'virtual_tap_to': tap_t,
                 # 'bus_to_regulated': self.bus_to_regulated,

                 'vset': self.vset,
                 'pset': self.Pset,

                 'base_temperature': self.temp_base,
                 'operational_temperature': self.temp_oper,
                 'alpha': self.alpha,

                 'overload_cost': self.Cost,
                 'capex': self.capex,
                 'opex': self.opex,
                 'build_status': str(self.build_status.value).lower(),
                 }
        else:
            d = dict()

        return d

    def get_profiles_dict(self, version=3):
        """

        :return:
        """
        if self.active_prof is not None:
            active_prof = self.active_prof.tolist()
            rate_prof = self.rate_prof.tolist()
        else:
            active_prof = list()
            rate_prof = list()

        return {'id': self.idtag,
                'active': active_prof,
                'rate': rate_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'rate': 'MW',
                'r': 'p.u.',
                'x': 'p.u.',
                'b': 'p.u.',
                'g': 'p.u.',
                'base_temperature': 'ºC',
                'operational_temperature': 'ºC',
                'alpha': '1/ºC'}

    def plot_profiles(self, time_series=None, my_index=0, show_fig=True):
        """
        Plot the time series results of this object
        :param time_series: TimeSeries Instance
        :param my_index: index of this object in the simulation
        :param show_fig: Show the figure?
        """

        if time_series is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            x = time_series.results.time_array

            # loading
            y = time_series.results.loading.real * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = np.abs(time_series.results.losses)
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()

    def get_coordinates(self):
        """
        Get the branch defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]

    def delete_virtual_taps(self):
        """
        Set the HV and LV parameters such that any virtual tap is null
        """
        self.HV = max(self.bus_from.Vnom, self.bus_to.Vnom)
        self.LV = min(self.bus_from.Vnom, self.bus_to.Vnom)

    def fix_inconsistencies(self, logger: Logger, maximum_difference=0.1):
        """
        Fix the inconsistencies
        :param logger:
        :param maximum_difference: proportion to be under or above (i.e. Transformer HV=41.9, bus HV=45 41.9/45 = 0.93 -> 0.9 <= 0.93 <= 1.1, so its ok
        :return:
        """
        errors = False
        HV = max(self.bus_from.Vnom, self.bus_to.Vnom)
        LV = min(self.bus_from.Vnom, self.bus_to.Vnom)

        if self.LV > self.HV:
            logger.add_warning("HV > LV", self.name, self.HV, HV)
            self.HV, self.LV = self.LV, self.HV
            errors = True

        rHV = self.HV / HV
        rLV = self.LV / LV
        LB = 1 - maximum_difference
        UB = 1 + maximum_difference
        if not (LB <= rHV <= UB):
            logger.add_warning("Corrected transformer HV", self.name, self.HV, HV)
            self.HV = HV
            errors = True

        if not (LB <= rLV <= UB):
            logger.add_warning("Corrected transformer LV", self.name, self.LV, LV)
            self.LV = LV
            errors = True

        if self.R < 0.0:
            logger.add_warning("Corrected transformer R<0", self.name, self.R, -self.R)
            self.R = -self.R
            errors = True

        return errors
