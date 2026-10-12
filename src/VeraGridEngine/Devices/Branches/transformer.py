# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from typing import Tuple
from VeraGridEngine.basic_structures import Logger, Mat, IntVec
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import (WindingsConnection, BuildStatus, TapPhaseControl,
                                         TapModuleControl, TapChangerTypes, WindingType, PrpCat,
                                         ParamPowerFlowReferenceType)
from VeraGridEngine.Devices.Parents.controllable_branch_parent import ControllableBranchParent
from VeraGridEngine.Devices.Branches.transformer_type import TransformerType, reverse_transformer_short_circuit_study
from VeraGridEngine.Devices.Parents.editable_device import DeviceType, GCProp
from VeraGridEngine.Utils.NumericalMethods.common import fortescue_012_to_abc


class Transformer2W(ControllableBranchParent):
    __slots__ = (
        '_HV',
        '_LV',
        '_Sn',
        '_Pcu',
        '_Pfe',
        '_I0',
        '_Vsc',
        'conn',
        'template',
        'possible_transformer_types',
        '_conn_f',
        '_conn_t',
        '_vector_group_number',
        '_phases',
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name='HV',
            units='kV',
            tpe=float,
            definition='High voltage rating',
            cat=[PrpCat.TP],
            dyn_ref=ParamPowerFlowReferenceType.transformer_winding1_rated_voltage_ll_kv,
        ),
        GCProp(
            prop_name='LV',
            units='kV',
            tpe=float,
            definition='Low voltage rating',
            cat=[PrpCat.TP],
            dyn_ref=ParamPowerFlowReferenceType.transformer_winding2_rated_voltage_ll_kv,
        ),
        GCProp(
            prop_name='Sn',
            units='MVA',
            tpe=float,
            definition='Nominal power',
            cat=[PrpCat.TP],
            dyn_ref=ParamPowerFlowReferenceType.transformer_rated_power_mva,
        ),
        GCProp(
            prop_name='Pcu',
            units='kW',
            tpe=float,
            definition='Copper losses (optional)',
            cat=[PrpCat.TP],
            dyn_ref=ParamPowerFlowReferenceType.transformer_short_circuit_loss_kw,
        ),
        GCProp(
            prop_name='Pfe',
            units='kW',
            tpe=float,
            definition='Iron losses (optional)',
            cat=[PrpCat.TP],
            dyn_ref=ParamPowerFlowReferenceType.transformer_open_circuit_loss_kw,
        ),
        GCProp(
            prop_name='I0',
            units='%',
            tpe=float,
            definition='No-load current (optional)',
            cat=[PrpCat.TP],
            dyn_ref=ParamPowerFlowReferenceType.transformer_open_circuit_current_pct,
        ),
        GCProp(
            prop_name='Vsc',
            units='%',
            tpe=float,
            definition='Short-circuit voltage (optional)',
            cat=[PrpCat.TP],
            dyn_ref=ParamPowerFlowReferenceType.transformer_short_circuit_voltage_pct,
        ),
        GCProp(
            prop_name='conn',
            units='',
            tpe=WindingsConnection,
            definition='Windings connection (from, to):G: grounded starS: ungrounded starD: delta',
            cat=[PrpCat.TP, PrpCat.PF3, PrpCat.SC],
        ),
        GCProp(
            prop_name='conn_f',
            units='',
            tpe=WindingType,
            definition='Winding 3 phase connection at the from side',
            cat=[PrpCat.TP, PrpCat.PF3, PrpCat.SC],
        ),
        GCProp(
            prop_name='conn_t',
            units='',
            tpe=WindingType,
            definition='Winding 3 phase connection at the to side',
            cat=[PrpCat.TP, PrpCat.PF3, PrpCat.SC],
        ),
        GCProp(
            prop_name='vector_group_number',
            units='',
            tpe=int,
            definition='Vector group number. It indicates the structural phase:'
                          'phase = vector_group_number · 30º',
            cat=[PrpCat.TP, PrpCat.PF3, PrpCat.SC],
            dyn_ref=ParamPowerFlowReferenceType.transformer_connection_clock,
        ),
        GCProp(
            prop_name='template',
            units='',
            tpe=DeviceType.TransformerTypeDevice,
            definition='',
            editable=False,
            cat=[PrpCat.TP],
        ),
    )

    def __init__(self,
                 bus_from: Bus | None = None,
                 bus_to: Bus | None = None,
                 name='Branch',
                 idtag: str | None = None,
                 code: str = '',
                 HV: float | None = None,
                 LV: float | None = None,
                 nominal_power: float = 0.001,
                 copper_losses: float = 0.0,
                 iron_losses: float = 0.0,
                 no_load_current: float = 0.0,
                 short_circuit_voltage: float = 0.0,
                 r: float = 1e-20,
                 x: float = 1e-5,
                 g: float = 1e-20,
                 b: float = 1e-20,
                 design_rate: float = 9999.0,
                 rate: float = 9999.0,
                 tap_module: float = 1.0,
                 tap_module_max: float = 1.2,
                 tap_module_min: float = 0.5,
                 tap_phase: float = 0.0,
                 tap_phase_max: float = 6.28,
                 tap_phase_min: float = -6.28,
                 active: bool = True,
                 reducible: bool = False,
                 tolerance: float = 0.0,
                 cost: float = 100.0,
                 mttf: float = 0.0,
                 mttr: float = 0.0,
                 vset: float = 1.0,
                 Pset: float = 0.0,
                 Qset: float = 0.0,
                 temp_base: float = 20.0,
                 temp_oper: float = 20.0,
                 alpha: float = 0.00330,
                 tap_module_control_mode: TapModuleControl = TapModuleControl.fixed,
                 tap_phase_control_mode: TapPhaseControl = TapPhaseControl.fixed,
                 template: TransformerType | None = None,
                 contingency_factor: float = 1.0,
                 protection_rating_factor: float = 1.4,
                 contingency_enabled: bool = True,
                 monitor_loading: bool = True,
                 r0: float = 1e-20,
                 x0: float = 1e-20,
                 g0: float = 1e-20,
                 b0: float = 1e-20,
                 r2: float = 1e-20,
                 x2: float = 1e-20,
                 g2: float = 1e-20,
                 b2: float = 1e-20,
                 conn: WindingsConnection = WindingsConnection.GG,
                 capex: float = 0.0,
                 opex: float = 0.0,
                 build_status: BuildStatus = BuildStatus.Commissioned,
                 tc_total_positions: int = 5,
                 tc_neutral_position: int = 2,
                 tc_normal_position: int = 2,
                 tc_dV: float = 0.01,
                 tc_asymmetry_angle=90,
                 tc_type: TapChangerTypes = TapChangerTypes.NoRegulation):
        """
        Transformer constructor
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary id
        :param bus_from: "From" :ref:`bus<Bus>` object
        :param bus_to: "To" :ref:`bus<Bus>` object
        :param HV: Higher voltage value in kV
        :param LV: Lower voltage value in kV
        :param nominal_power: Nominal power of the machine in MVA
        :param copper_losses: Copper losses in kW
        :param iron_losses: Iron losses in kW
        :param no_load_current: No load current in %
        :param short_circuit_voltage: Short circuit voltage in %
        :param r: resistance in per unit
        :param x: reactance in per unit
        :param g: shunt conductance in per unit
        :param b: shunt susceptance in per unit
        :param design_rate: Design rate (MVA)
        :param rate: rate in MVA
        :param tap_module: tap module in p.u.
        :param tap_module_max:
        :param tap_module_min:
        :param tap_phase: phase shift angle (rad)
        :param tap_phase_max:
        :param tap_phase_min:
        :param active: Is the branch active?
        :param tolerance: Tolerance specified for the branch impedance in %
        :param cost: Cost of overload (e/MW)
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param vset: Voltage set-point of the voltage controlled bus in per unit
        :param Pset: Power set point
        :param temp_base: Base temperature at which `r` is measured in °C
        :param temp_oper: Operating temperature in °C
        :param alpha: Thermal constant of the material in °C
        :param template: Branch template
        :param contingency_factor: Rating factor in case of contingency
        :param contingency_enabled: enabled for contingencies (Legacy)
        :param monitor_loading: monitor the loading (used in OPF)
        :param r0: zero-sequence resistence (p.u.)
        :param x0: zero-sequence reactance (p.u.)
        :param g0: zero-sequence conductance (p.u.)
        :param b0: zero-sequence susceptance (p.u.)
        :param r2: negative-sequence resistence (p.u.)
        :param x2: negative-sequence reactance (p.u.)
        :param g2: negative-sequence conductance (p.u.)
        :param b2: negative-sequence susceptance (p.u.)
        :param conn: transformer connection type
        :param capex: Cost of investment (e/MW)
        :param opex: Cost of operation (e/MWh)
        :param build_status: build status (now time)
        """

        ControllableBranchParent.__init__(self,
                                          name=name,
                                          idtag=idtag,
                                          code=code,
                                          bus_from=bus_from,
                                          bus_to=bus_to,
                                          active=active,
                                          reducible=reducible,
                                          design_rate=design_rate,
                                          rate=rate,
                                          r=r,
                                          x=x,
                                          g=g,
                                          b=b,
                                          tap_module=tap_module,
                                          tap_module_max=tap_module_max,
                                          tap_module_min=tap_module_min,
                                          tap_phase=tap_phase,
                                          tap_phase_max=tap_phase_max,
                                          tap_phase_min=tap_phase_min,
                                          tolerance=tolerance,
                                          cost=cost,
                                          mttf=mttf,
                                          mttr=mttr,
                                          vset=vset,
                                          Pset=Pset,
                                          Qset=Qset,
                                          regulation_branch=None,
                                          regulation_bus=None,
                                          temp_base=temp_base,
                                          temp_oper=temp_oper,
                                          alpha=alpha,
                                          # control_mode=control_mode,
                                          tap_module_control_mode=tap_module_control_mode,
                                          tap_phase_control_mode=tap_phase_control_mode,
                                          contingency_factor=contingency_factor,
                                          protection_rating_factor=protection_rating_factor,
                                          contingency_enabled=contingency_enabled,
                                          monitor_loading=monitor_loading,
                                          r0=r0,
                                          x0=x0,
                                          g0=g0,
                                          b0=b0,
                                          r2=r2,
                                          x2=x2,
                                          g2=g2,
                                          b2=b2,
                                          capex=capex,
                                          opex=opex,
                                          build_status=build_status,
                                          device_type=DeviceType.Transformer2WDevice,
                                          tc_total_positions=tc_total_positions,
                                          tc_neutral_position=tc_neutral_position,
                                          tc_normal_position=tc_normal_position,
                                          tc_dV=tc_dV,
                                          tc_asymmetry_angle=tc_asymmetry_angle,
                                          tc_type=tc_type)

        # set the high and low voltage values
        self._HV: float | None = None if HV is None else float(HV)
        self._LV: float | None = None if LV is None else float(LV)

        if self.bus_from and self.bus_to:
            self.set_hv_and_lv(HV, LV)

        self.Sn = float(nominal_power)

        self.Pcu = float(copper_losses)

        self.Pfe = float(iron_losses)

        self.I0 = float(no_load_current)

        self.Vsc = float(short_circuit_voltage)

        # connection type
        self.conn: WindingsConnection = conn

        # type template
        self.template: TransformerType | None = template

        # association with transformer templates
        # self.possible_transformer_types: Associations = Associations(device_type=DeviceType.TransformerTypeDevice)

        self._conn_f: WindingType = WindingType.GroundedStar
        self._conn_t: WindingType = WindingType.GroundedStar
        self._vector_group_number: int = 0
        self._phases: IntVec = np.array([1, 2, 3])

        # TODO: do we need to edit the phases vector?

    @property
    def conn_f(self) -> WindingType:
        return self._conn_f

    @conn_f.setter
    def conn_f(self, val: WindingType):
        if isinstance(val, WindingType):
            self._conn_f = val
        else:
            raise Exception("Conn_f is not a WindingType")

    @property
    def conn_t(self) -> WindingType:
        return self._conn_t

    @conn_t.setter
    def conn_t(self, val: WindingType):
        if isinstance(val, WindingType):
            self._conn_t = val
        else:
            raise Exception("Conn_t is not a WindingType")

    @property
    def vector_group_number(self) -> int:
        return self._vector_group_number

    @vector_group_number.setter
    def vector_group_number(self, val: int):

        val = int(val)
        if 0 <= val <= 11:
            self._vector_group_number = val
        else:
            print("Vector group out of range (0-11)")

    @property
    def phases(self) -> IntVec:
        return self._phases

    @phases.setter
    def phases(self, val: IntVec):
        if isinstance(val, np.ndarray):
            self._phases = val
        else:
            raise Exception("phases must be a numpy array (IntVec)")

    def set_hv_and_lv(self, HV: float | None, LV: float | None):
        """
        set the high and low voltage values
        :param HV: higher voltage value (kV)
        :param LV: lower voltage value (kV)
        """
        if self.bus_from is not None:
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

    def get_from_to_nominal_voltages(self) -> Tuple[float, float, bool]:
        """

        :return:
        """
        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom

        dhf = abs(self.HV - bus_f_v)
        dht = abs(self.HV - bus_t_v)

        if dhf < dht:
            # the HV side is on the from side
            tpe_f_v = self.HV
            tpe_t_v = self.LV
            hv_at_from = True
        else:
            # the HV side is on the to side
            tpe_t_v = self.HV
            tpe_f_v = self.LV
            hv_at_from = False

        return tpe_f_v, tpe_t_v, hv_at_from

    def get_virtual_taps(self) -> Tuple[float, float]:
        """
        Get the branch virtual taps

        The virtual taps generate when a transformer nominal winding voltage differs
        from the bus nominal voltage.
        :return: Virtual tap at the *from* side, **tap_t** (float, 1.0): Virtual tap at the *to* side
        """

        # resolve how the transformer is actually connected and set the virtual taps
        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom

        # obtain the nominal voltages at the from and to sides
        tpe_f_v, tpe_t_v, _ = self.get_from_to_nominal_voltages()

        tap_f = tpe_f_v / bus_f_v if bus_f_v > 0 else 1.0
        tap_t = tpe_t_v / bus_t_v if bus_t_v > 0 else 1.0

        if tap_f == 0.0:
            tap_f = 1.0

        if tap_t == 0.0:
            tap_t = 1.0

        return tap_f, tap_t

    def apply_template(self, obj: TransformerType, Sbase: float, logger=Logger()):
        """
        Apply a branch template to this object
        :param obj: TransformerType or Tower object
        :param Sbase: circuit base power in MVA
        :param logger: Log list
        """

        if isinstance(obj, TransformerType):

            self.HV = obj.HV
            self.LV = obj.LV

            # get the transformer impedance in the base of the transformer
            z_series, y_shunt = obj.get_impedances(VH=obj.HV, VL=obj.LV, Sbase=Sbase)

            self.R = z_series.real
            self.X = z_series.imag
            self.G = y_shunt.real
            self.B = y_shunt.imag

            self.rate = obj.Sn
            self.rate_prof.fill(self.rate)

            self.Sn = obj.Sn
            self.Pcu = obj.Pcu
            self.Pfe = obj.Pfe
            self.I0 = obj.I0
            self.Vsc = obj.Vsc

            self.tap_changer = obj.get_tap_changer()
            self.vector_group_number = obj.vector_group_number

            # set the from and to connection types of the windings
            _, _, hv_at_from = self.get_from_to_nominal_voltages()

            if hv_at_from:
                self.conn_f = obj.conn_hv
                self.conn_t = obj.conn_lv
            else:
                self.conn_t = obj.conn_hv
                self.conn_f = obj.conn_lv

            if self.template is not None:
                if obj != self.template:
                    self.template = obj
                else:
                    logger.add_error('Template not recognised', self.name)
            else:
                self.template = obj

            self.rms_template = obj.rms_template
            self.emt_template = obj.emt_template

    def delete_virtual_taps(self):
        """
        Set the HV and LV parameters such that any virtual tap is null
        """
        self.HV = max(self.bus_from.Vnom, self.bus_to.Vnom)
        self.LV = min(self.bus_from.Vnom, self.bus_to.Vnom)

    def fix_inconsistencies(self, logger: Logger, maximum_difference=0.1) -> bool:
        """
        Fix the inconsistencies
        :param logger:
        :param maximum_difference: proportion to be under or above
        (i.e. Transformer HV=41.9, bus HV=45 41.9/45 = 0.93 -> 0.9 <= 0.93 <= 1.1, so it's ok
        :return: were there any errors?
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
        is_phase_to_neutral = len(self.phases) == 2 and 0 in self.phases
        valid_hv = LB <= rHV <= UB or (is_phase_to_neutral and LB <= rHV * np.sqrt(3) <= UB)
        valid_lv = LB <= rLV <= UB or (is_phase_to_neutral and LB <= rLV * np.sqrt(3) <= UB)

        if not valid_hv:
            logger.add_warning("Corrected transformer HV", self.name, self.HV, HV)
            self.HV = HV
            errors = True

        if not valid_lv:
            logger.add_warning("Corrected transformer LV", self.name, self.LV, LV)
            self.LV = LV
            errors = True

        if self.R < 0.0:
            logger.add_warning("Corrected transformer R<0", self.name, self.R, -self.R)
            self.R = -self.R
            errors = True

        return errors

    def fill_design_properties(self, Pcu: float, Pfe: float, I0: float, Vsc: float, Sbase: float,
                               round_vals: bool = False) -> "Transformer2W":
        """
        Fill R, X, G, B from the short circuit study values
        :param Pcu: copper_losses (kW)
        :param Pfe: Iron losses (kW)
        :param I0: No load current in %
        :param Vsc: Short circuit voltage (%)
        :param Sbase: Base power in MVA (take always 100 MVA)
        :param round_vals: round the values?
        :return: self pointer
        """

        if self.Sn > 0:
            nominal_power = self.Sn
        else:
            if self.rate > 0:
                nominal_power = self.rate
                print(f"{self.name}: Using rate to set compute the impedances...please fill a valid nominal power")
            else:
                nominal_power = 1.0
                print(f"{self.name}: Using 1 to set compute the impedances...please fill a valid nominal power")

        tpe = TransformerType(hv_nominal_voltage=self.HV,
                              lv_nominal_voltage=self.LV,
                              nominal_power=nominal_power,
                              copper_losses=Pcu,
                              iron_losses=Pfe,
                              no_load_current=I0,
                              short_circuit_voltage=Vsc,
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              name='type from ' + self.name)

        self.Pcu = Pcu
        self.Pfe = Pfe
        self.I0 = I0
        self.Vsc = Vsc

        z_series, y_shunt = tpe.get_impedances(VH=self.HV, VL=self.LV, Sbase=Sbase)

        if round_vals:
            self.R = np.round(z_series.real, 6)
            self.X = np.round(z_series.imag, 6)
            self.G = np.round(y_shunt.real, 6)
            self.B = np.round(y_shunt.imag, 6)
        else:
            self.R = z_series.real
            self.X = z_series.imag
            self.G = y_shunt.real
            self.B = y_shunt.imag

        return self

    def get_vcc(self, Sbase: float = 100.0) -> float:
        """Return the transformer short-circuit voltage in percent.

        :param Sbase: Circuit/system power base in MVA.
        :return: Short-circuit voltage in percent.
        """
        if self.Sn > 0.0:
            nominal_power: float = self.Sn
        elif self.rate > 0.0:
            nominal_power = self.rate
        else:
            return 0.0

        if Sbase <= 0.0:
            return 0.0

        _, _, Vsc, _, _ = reverse_transformer_short_circuit_study(
            R=self.R,
            X=self.X,
            G=self.G,
            B=self.B,
            rate=nominal_power,
            Sbase=Sbase,
        )
        return float(Vsc)

    def get_transformer_type(self, Sbase: float = 100.0) -> TransformerType:
        """
        Get the equivalent transformer type of this transformer
        :return: SequenceLineType
        :param Sbase:
        :return:
        """
        if self.Vsc == 0:
            Pfe, Pcu, Vsc, I0, Sn = reverse_transformer_short_circuit_study(R=self.R,
                                                                            X=self.X,
                                                                            G=self.G,
                                                                            B=self.B,
                                                                            rate=self.Sn if self.Sn > 0.0 else self.rate,
                                                                            Sbase=Sbase)
        else:
            Pfe = self.Pfe
            Pcu = self.Pcu
            Vsc = self.Vsc
            I0 = self.I0
            Sn = self.Sn

        tpe = TransformerType(hv_nominal_voltage=self.HV,
                              lv_nominal_voltage=self.LV,
                              nominal_power=Sn,
                              copper_losses=Pcu,
                              iron_losses=Pfe,
                              no_load_current=I0,
                              short_circuit_voltage=Vsc,
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              name='type from ' + self.name)

        return tpe

    def transformer_phases(self, logger: Logger):
        phaseN = phaseA = phaseB = phaseC = 0

        for phase in self.phases:
            if phase == 0:
                phaseN = 1
            elif phase == 1:
                phaseA = 1
            elif phase == 2:
                phaseB = 1
            elif phase == 3:
                phaseC = 1
            else:
                logger.add_error(
                    f"transformer_phases: Incorrect phase value {phase} in {self.name}",
                    device=self.name
                )
                return phaseN, phaseA, phaseB, phaseC

        return phaseN, phaseA, phaseB, phaseC

    def transformer_admittance(self,
                               vtap_f: float,
                               vtap_t: float,
                               logger: Logger,
                               conn_f: WindingType | None = None,
                               conn_t: WindingType | None = None,
                               clock_phase: float | None = None) -> Tuple[Mat, Mat, Mat, Mat]:
        """
        Get the transformer 3-phase primitives
        :param vtap_f: virtual tap from
        :param vtap_t: virtual tap to
        :param logger: Calculation diagnostics.
        :param conn_f: Optional connection used by a multi-winding equivalent.
        :param conn_t: Optional connection used by a multi-winding equivalent.
        :param clock_phase: Optional from-to clock angle in radians.
        :param logger: Logger
        :return: NABC primitive matrices -> Yff, Yft, Ytf, Ytt
        """

        conn_f = self.conn_f if conn_f is None else conn_f
        conn_t = self.conn_t if conn_t is None else conn_t
        conn_y_from = conn_f == WindingType.NeutralStar or conn_f == WindingType.GroundedStar
        conn_y_to = conn_t == WindingType.NeutralStar or conn_t == WindingType.GroundedStar

        ys = 1.0 / (self.R + 1j * self.X + 1e-20)
        ysh = self.G + 1j * self.B

        yff = (ys + ysh / 2) / (self.tap_module * self.tap_module * vtap_f * vtap_f)
        yft = -ys / (self.tap_module * np.exp(-1.0j * self.tap_phase) * vtap_f * vtap_t)
        ytf = -ys / (self.tap_module * np.exp(1.0j * self.tap_phase) * vtap_t * vtap_f)
        ytt = (ys + ysh / 2) / (vtap_t * vtap_t)

        # Single-phase D-D and Y-Y transformers
        single_phase_connections = (WindingType.Delta, WindingType.FloatingStar)
        if (len(self.phases) == 2
                and conn_f in single_phase_connections
                and conn_t in single_phase_connections):
            phase_1, phase_2 = self.phases
            if not 0 <= phase_1 < phase_2 <= 3:
                logger.add_error("transformer_admittance: Unknown phase pair", device=self.name)
                zeros = np.zeros((4, 4), dtype=float)
                return zeros, zeros, zeros, zeros

            phase_pattern = np.zeros((4, 4), dtype=float)
            phase_pattern[phase_1, phase_1] = 1.0
            phase_pattern[phase_1, phase_2] = -1.0
            phase_pattern[phase_2, phase_1] = -1.0
            phase_pattern[phase_2, phase_2] = 1.0

            Yff = yff * phase_pattern
            Yft = yft * phase_pattern
            Ytf = ytf * phase_pattern
            Ytt = ytt * phase_pattern
            return Yff, Yft, Ytf, Ytt

        # Three Phase Transformer
        winding_phase: float = 0.0
        if conn_y_from and conn_y_to:  # Yy
            Yff = np.array([
                [0, 0, 0, 0],
                [0, yff, 0, 0],
                [0, 0, yff, 0],
                [0, 0, 0, yff]
            ])
            Yft = np.array([
                [0, 0, 0, 0],
                [0, yft, 0, 0],
                [0, 0, yft, 0],
                [0, 0, 0, yft]
            ])
            Ytf = np.array([
                [0, 0, 0, 0],
                [0, ytf, 0, 0],
                [0, 0, ytf, 0],
                [0, 0, 0, ytf]
            ])
            Ytt = np.array([
                [0, 0, 0, 0],
                [0, ytt, 0, 0],
                [0, 0, ytt, 0],
                [0, 0, 0, ytt]
            ])

        elif conn_y_from and conn_t == WindingType.Delta:  # 'Yd'
            winding_phase = np.pi / 6
            Yff = np.array([
                [0, 0, 0, 0],
                [0, yff, 0, 0],
                [0, 0, yff, 0],
                [0, 0, 0, yff]
            ])
            Yft = np.array([
                [0, 0, 0, 0],
                [0, yft / np.sqrt(3), -yft / np.sqrt(3), 0],
                [0, 0, yft / np.sqrt(3), -yft / np.sqrt(3)],
                [0, -yft / np.sqrt(3), 0, yft / np.sqrt(3)]
            ])
            Ytf = np.array([
                [0, 0, 0, 0],
                [0, ytf / np.sqrt(3), 0, -ytf / np.sqrt(3)],
                [0, -ytf / np.sqrt(3), ytf / np.sqrt(3), 0],
                [0, 0, -ytf / np.sqrt(3), ytf / np.sqrt(3)]
            ])
            Ytt = np.array([
                [0, 0, 0, 0],
                [0, 2 * ytt / 3, -ytt / 3, -ytt / 3],
                [0, -ytt / 3, 2 * ytt / 3, -ytt / 3],
                [0, -ytt / 3, -ytt / 3, 2 * ytt / 3]
            ])

        elif conn_y_from and self.conn_t == WindingType.GroundedZigZag:  # 'Yz'
            winding_phase = -np.pi / 6
            Yff = np.array([
                [yff, 0, 0],
                [0, yff, 0],
                [0, 0, yff]
            ])
            Yft = np.array([
                [yft / 2, 0, -yft / 2],
                [-yft / 2, yft / 2, 0],
                [0, -yft / 2, yft / 2]
            ])
            Ytf = np.array([
                [ytf / 2, -ytf / 2, 0],
                [0, ytf / 2, -ytf / 2],
                [-ytf / 2, 0, ytf / 2]
            ])
            Ytt = np.array([
                [ytt, 0, 0],
                [0, ytt, 0],
                [0, 0, ytt]
            ])

        elif conn_f == WindingType.Delta and conn_y_to:  # 'Dy'
            winding_phase = -np.pi / 6
            Yff = np.array([
                [0, 0, 0, 0],
                [0, 2 * yff / 3, -yff / 3, -yff / 3],
                [0, -yff / 3, 2 * yff / 3, -yff / 3],
                [0, -yff / 3, -yff / 3, 2 * yff / 3]
            ])
            Yft = np.array([
                [0, 0, 0, 0],
                [0, yft / np.sqrt(3), 0, -yft / np.sqrt(3)],
                [0, -yft / np.sqrt(3), yft / np.sqrt(3), 0],
                [0, 0, -yft / np.sqrt(3), yft / np.sqrt(3)]
            ])
            Ytf = np.array([
                [0, 0, 0, 0],
                [0, ytf / np.sqrt(3), -ytf / np.sqrt(3), 0],
                [0, 0, ytf / np.sqrt(3), -ytf / np.sqrt(3)],
                [0, -ytf / np.sqrt(3), 0, ytf / np.sqrt(3)]
            ])
            Ytt = np.array([
                [0, 0, 0, 0],
                [0, ytt, 0, 0],
                [0, 0, ytt, 0],
                [0, 0, 0, ytt]
            ])

        elif conn_f == WindingType.Delta and conn_t == WindingType.Delta:  # 'Dd'
            Yff = np.array([
                [0, 0, 0, 0],
                [0, 2 * yff / 3, -yff / 3, -yff / 3],
                [0, -yff / 3, 2 * yff / 3, -yff / 3],
                [0, -yff / 3, -yff / 3, 2 * yff / 3]
            ])
            Yft = np.array([
                [0, 0, 0, 0],
                [0, 2 * yft / 3, -yft / 3, -yft / 3],
                [0, -yft / 3, 2 * yft / 3, -yft / 3],
                [0, -yft / 3, -yft / 3, 2 * yft / 3]
            ])
            Ytf = np.array([
                [0, 0, 0, 0],
                [0, 2 * ytf / 3, -ytf / 3, -ytf / 3],
                [0, -ytf / 3, 2 * ytf / 3, -ytf / 3],
                [0, -ytf / 3, -ytf / 3, 2 * ytf / 3]
            ])
            Ytt = np.array([
                [0, 0, 0, 0],
                [0, 2 * ytt / 3, -ytt / 3, -ytt / 3],
                [0, -ytt / 3, 2 * ytt / 3, -ytt / 3],
                [0, -ytt / 3, -ytt / 3, 2 * ytt / 3]
            ])

        elif conn_f == WindingType.Delta and conn_t == WindingType.GroundedZigZag:  # 'Dz':
            winding_phase = -np.pi / 3
            Yff = np.array([
                [0, 0, 0, 0],
                [0, 2 * yff / 3, -yff / 3, -yff / 3],
                [0, -yff / 3, 2 * yff / 3, -yff / 3],
                [0, -yff / 3, -yff / 3, 2 * yff / 3]
            ])
            Yft = np.array([
                [0, 0, 0, 0],
                [0, yft / (2 * np.sqrt(3)), yft / (2 * np.sqrt(3)), -yft / np.sqrt(3)],
                [0, -yft / np.sqrt(3), yft / (2 * np.sqrt(3)), yft / (2 * np.sqrt(3))],
                [0, yft / (2 * np.sqrt(3)), -yft / np.sqrt(3), yft / (2 * np.sqrt(3))]
            ])
            Ytf = np.array([
                [0, 0, 0, 0],
                [0, yft / (2 * np.sqrt(3)), -yft / np.sqrt(3), yft / (2 * np.sqrt(3))],
                [0, yft / (2 * np.sqrt(3)), yft / (2 * np.sqrt(3)), -yft / np.sqrt(3)],
                [0, -yft / np.sqrt(3), yft / (2 * np.sqrt(3)), yft / (2 * np.sqrt(3))]
            ])
            Ytt = np.array([
                [0, 0, 0, 0],
                [0, ytt, 0, 0],
                [0, 0, ytt, 0],
                [0, 0, 0, ytt]
            ])

        elif conn_f == WindingType.GroundedZigZag and conn_y_to:  # 'Zy':
            winding_phase = np.pi / 6
            Yff = np.array([
                [0, 0, 0, 0],
                [0, yff, 0, 0],
                [0, 0, yff, 0],
                [0, 0, 0, yff]
            ])
            Yft = np.array([
                [0, 0, 0, 0],
                [0, yft / 2, -yft / 2, 0],
                [0, 0, yft / 2, -yft / 2],
                [0, -yft / 2, 0, yft / 2]
            ])
            Ytf = np.array([
                [0, 0, 0, 0],
                [0, ytf / 2, 0, -ytf / 2],
                [0, -ytf / 2, ytf / 2, 0],
                [0, 0, -ytf / 2, ytf / 2]
            ])
            Ytt = np.array([
                [0, 0, 0, 0],
                [0, ytt, 0, 0],
                [0, 0, ytt, 0],
                [0, 0, 0, ytt]
            ])

        elif conn_f == WindingType.GroundedZigZag and conn_t == WindingType.Delta:  # 'Zd':
            winding_phase = np.pi / 3
            Yff = np.array([
                [0, 0, 0, 0],
                [0, yff, 0, 0],
                [0, 0, yff, 0],
                [0, 0, 0, yff]
            ])
            Yft = np.array([
                [0, 0, 0, 0],
                [0, yft / (2 * np.sqrt(3)), -yft / np.sqrt(3), yft / (2 * np.sqrt(3))],
                [0, yft / (2 * np.sqrt(3)), yft / (2 * np.sqrt(3)), -yft / np.sqrt(3)],
                [0, -yft / np.sqrt(3), yft / (2 * np.sqrt(3)), yft / (2 * np.sqrt(3))]
            ])
            Ytf = np.array([
                [0, 0, 0, 0],
                [0, yft / (2 * np.sqrt(3)), yft / (2 * np.sqrt(3)), -yft / np.sqrt(3)],
                [0, -yft / np.sqrt(3), yft / (2 * np.sqrt(3)), yft / (2 * np.sqrt(3))],
                [0, yft / (2 * np.sqrt(3)), -yft / np.sqrt(3), yft / (2 * np.sqrt(3))]
            ])
            Ytt = np.array([
                [0, 0, 0, 0],
                [0, 2 * ytt / 3, -ytt / 3, -ytt / 3],
                [0, -ytt / 3, 2 * ytt / 3, -ytt / 3],
                [0, -ytt / 3, -ytt / 3, 2 * ytt / 3]
            ])

        elif conn_f == WindingType.GroundedZigZag and conn_t == WindingType.GroundedZigZag:  # 'Zz':
            Yff = np.array([
                [0, 0, 0, 0],
                [0, yff, 0, 0],
                [0, 0, yff, 0],
                [0, 0, 0, yff]
            ])
            Yft = np.array([
                [0, 0, 0, 0],
                [0, yft, 0, 0],
                [0, 0, yft, 0],
                [0, 0, 0, yft]
            ])
            Ytf = np.array([
                [0, 0, 0, 0],
                [0, ytf, 0, 0],
                [0, 0, ytf, 0],
                [0, 0, 0, ytf]
            ])
            Ytt = np.array([
                [0, 0, 0, 0],
                [0, ytt, 0, 0],
                [0, 0, ytt, 0],
                [0, 0, 0, ytt]
            ])

        else:
            logger.add_error("transformer_admittance: Unknown vector group", device=self.name)
            zeros = np.zeros((4, 4), dtype=float)
            return zeros, zeros, zeros, zeros

        # The clock specifies the total HV-to-LV lag, including the winding rotation.
        # Rotate opposite sequences oppositely and leave the zero-sequence path intact.
        if self.bus_from is not None and self.bus_to is not None:
            _, _, hv_at_from = self.get_from_to_nominal_voltages()
        else:
            hv_at_from = True
        if clock_phase is None:
            clock_phase = np.deg2rad(self.vector_group_number * 30.0) * (1 if hv_at_from else -1)
        else:
            pass
        correction: complex = np.exp(1j * (clock_phase - winding_phase))
        rotation: Mat = fortescue_012_to_abc(1.0, correction, correction.conjugate()).real
        Yft[-3:, -3:] = Yft[-3:, -3:] @ rotation
        Ytf[-3:, -3:] = rotation.T @ Ytf[-3:, -3:]
        return Yff, Yft, Ytf, Ytt

    # Scalar property accessors coerce assignments to the declared schema types.

    @property
    def HV(self) -> float:
        """
        Get ``HV``.

        :return: float
        """
        return self._HV

    @HV.setter
    def HV(self, val: float) -> None:
        """
        Set ``HV``.

        :param val: Value to assign.
        :return: None
        """
        self._HV = float(val)

    @property
    def LV(self) -> float:
        """
        Get ``LV``.

        :return: float
        """
        return self._LV

    @LV.setter
    def LV(self, val: float) -> None:
        """
        Set ``LV``.

        :param val: Value to assign.
        :return: None
        """
        self._LV = float(val)

    @property
    def Sn(self) -> float:
        """
        Get ``Sn``.

        :return: float
        """
        return self._Sn

    @Sn.setter
    def Sn(self, val: float) -> None:
        """
        Set ``Sn``.

        :param val: Value to assign.
        :return: None
        """
        self._Sn = float(val)

    @property
    def Pcu(self) -> float:
        """
        Get ``Pcu``.

        :return: float
        """
        return self._Pcu

    @Pcu.setter
    def Pcu(self, val: float) -> None:
        """
        Set ``Pcu``.

        :param val: Value to assign.
        :return: None
        """
        self._Pcu = float(val)

    @property
    def Pfe(self) -> float:
        """
        Get ``Pfe``.

        :return: float
        """
        return self._Pfe

    @Pfe.setter
    def Pfe(self, val: float) -> None:
        """
        Set ``Pfe``.

        :param val: Value to assign.
        :return: None
        """
        self._Pfe = float(val)

    @property
    def I0(self) -> float:
        """
        Get ``I0``.

        :return: float
        """
        return self._I0

    @I0.setter
    def I0(self, val: float) -> None:
        """
        Set ``I0``.

        :param val: Value to assign.
        :return: None
        """
        self._I0 = float(val)

    @property
    def Vsc(self) -> float:
        """
        Get ``Vsc``.

        :return: float
        """
        return self._Vsc

    @Vsc.setter
    def Vsc(self, val: float) -> None:
        """
        Set ``Vsc``.

        :param val: Value to assign.
        :return: None
        """
        self._Vsc = float(val)
