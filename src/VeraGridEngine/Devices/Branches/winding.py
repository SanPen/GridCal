# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
import numpy as np
from VeraGridEngine.basic_structures import Logger, Mat
from VeraGridEngine.Utils.NumericalMethods.common import fortescue_012_to_abc
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.enumerations import (WindingsConnection, WindingType, BuildStatus, TapPhaseControl, TapModuleControl)
from VeraGridEngine.Devices.Branches.transformer_type import TransformerType
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Parents.editable_device import DeviceType


class Winding(Transformer2W):
    __slots__ = ()

    def __init__(self,
                 bus_from: Bus = None,
                 bus_to: Bus = None,
                 name='Winding',
                 idtag: Union[None, str] = None,
                 code: str = '',
                 HV: Union[None, float] = None,
                 LV: Union[None, float] = None,
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
                 build_status: BuildStatus = BuildStatus.Commissioned):
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
        :param tap_module_control_mode: Tap module Control model
        :param tap_phase_control_mode: Tap phase Control model
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
        Transformer2W.__init__(self,
                               bus_from=bus_from,
                               bus_to=bus_to,
                               name=name,
                               idtag=idtag,
                               code=code,
                               HV=HV,
                               LV=LV,
                               nominal_power=nominal_power,
                               copper_losses=copper_losses,
                               iron_losses=iron_losses,
                               no_load_current=no_load_current,
                               short_circuit_voltage=short_circuit_voltage,
                               r=r,
                               x=x,
                               g=g,
                               b=b,
                               design_rate=design_rate,
                               rate=rate,
                               tap_module=tap_module,
                               tap_module_max=tap_module_max,
                               tap_module_min=tap_module_min,
                               tap_phase=tap_phase,
                               tap_phase_max=tap_phase_max,
                               tap_phase_min=tap_phase_min,
                               active=active,
                               reducible=False,
                               tolerance=tolerance,
                               cost=cost,
                               mttf=mttf,
                               mttr=mttr,
                               vset=vset,
                               Pset=Pset,
                               Qset=Qset,
                               temp_base=temp_base,
                               temp_oper=temp_oper,
                               alpha=alpha,
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
                               conn=conn,
                               capex=capex,
                               opex=opex,
                               build_status=build_status)

        self.device_type = DeviceType.WindingDevice

    def get_winding_connections(self) -> tuple[WindingType, WindingType]:
        """Resolve the external connection of historical DGS star equivalents.

        :return: From/to connections, with the internal star at the internal bus.
        """
        # Older DGS imports stored the external connection on the internal end.
        # Recognise that layout without changing the saved device or its clock.
        if (self.bus_to is not None and self.bus_to.internal
                and self.conn_f == WindingType.GroundedStar):
            return self.conn_t, WindingType.GroundedStar
        elif (self.bus_from is not None and self.bus_from.internal
              and self.conn_t == WindingType.GroundedStar):
            return WindingType.GroundedStar, self.conn_f
        else:
            return self.conn_f, self.conn_t

    def transformer_admittance(self, vtap_f: float, vtap_t: float,
                               logger: Logger) -> tuple[Mat, Mat, Mat, Mat]:
        """Build NABC blocks for one branch of a multi-winding star equivalent.

        :param vtap_f: From-side virtual tap.
        :param vtap_t: To-side virtual tap.
        :param logger: Calculation diagnostics.
        :return: Yff, Yft, Ytf and Ytt, each in NABC order.
        """
        internal_from: bool = self.bus_from is not None and self.bus_from.internal
        internal_to: bool = self.bus_to is not None and self.bus_to.internal
        if not internal_from and not internal_to:
            return super().transformer_admittance(vtap_f, vtap_t, logger)
        else:
            pass

        conn_f: WindingType
        conn_t: WindingType
        conn_f, conn_t = self.get_winding_connections()
        allowed: tuple[WindingType, ...] = (WindingType.GroundedStar, WindingType.NeutralStar,
                                           WindingType.FloatingStar, WindingType.Delta)
        if conn_f not in allowed or conn_t not in allowed:
            raise ValueError(f"Three-phase winding connection is not supported: {self.name}, {conn_f}-{conn_t}")
        else:
            pass

        z1: complex = complex(self.R, self.X)
        z2: complex = complex(self.R2, self.X2)
        if abs(z2) < 1e-12:
            # Passive transformer leakage is identical in sequences 1 and 2 in PF.
            z2 = z1
        else:
            pass
        if not np.isfinite(z1) or not np.isfinite(z2) or min(abs(z1), abs(z2)) < 1e-12:
            raise ValueError(f"Three-phase winding Z1/Z2 must be finite and nonzero: {self.name}")
        else:
            pass

        # A winding clock is its terminal lag relative to the common internal
        # reference, the opposite orientation to a conventional HV-to-LV branch.
        clock_phase: float = np.deg2rad(self.vector_group_number * 30.0) * (1 if internal_from else -1)
        yff: Mat
        yft: Mat
        ytf: Mat
        ytt: Mat
        yff, yft, ytf, ytt = super().transformer_admittance(
            vtap_f, vtap_t, logger,
            conn_f=WindingType.NeutralStar if conn_f == WindingType.FloatingStar else conn_f,
            conn_t=WindingType.NeutralStar if conn_t == WindingType.FloatingStar else conn_t,
            clock_phase=clock_phase)
        scaling: Mat = fortescue_012_to_abc(0.0, 1.0, z1 / z2)
        block: Mat
        for block in (yff, yft, ytf, ytt):
            # Keep the existing connection/tap/clock primitive for sequences 1/2.
            block[1:, 1:] = block[1:, 1:] @ scaling

        external: WindingType = conn_t if internal_from else conn_f
        explicit_neutral: bool = external == WindingType.NeutralStar and 0 in self.phases
        if external in (WindingType.GroundedStar, WindingType.Delta) or explicit_neutral:
            z0: complex = complex(self.R0, self.X0)
            if not np.isfinite(z0) or abs(z0) < 1e-12:
                raise ValueError(f"Three-phase winding Z0 must be finite and nonzero: {self.name}; "
                                 "set R0/X0 or export TypTr3 uk0hm/uk0ml/uk0hl and ur0hm/ur0ml/ur0hl")
            else:
                pass
            zero: Mat = fortescue_012_to_abc(1.0 / z0, 0.0, 0.0)
            tap_f: float = self.tap_module * vtap_f
            # A delta has no external I0 but closes a circulating path at the core.
            if external == WindingType.Delta:
                if internal_from:
                    yff[1:, 1:] += zero / (tap_f * tap_f)
                else:
                    ytt[1:, 1:] += zero / (vtap_t * vtap_t)
            else:
                yff[1:, 1:] += zero / (tap_f * tap_f)
                yft[1:, 1:] -= zero * np.exp(1j * self.tap_phase) / (tap_f * vtap_t)
                ytf[1:, 1:] -= zero * np.exp(-1j * self.tap_phase) / (tap_f * vtap_t)
                ytt[1:, 1:] += zero / (vtap_t * vtap_t)
        else:
            # An isolated star point cannot supply a zero-sequence current.
            pass

        if explicit_neutral:
            connection: Mat = np.eye(4)
            connection[1:, 0] = -1.0
            if internal_from:
                yft = yft @ connection
                ytf = connection.T @ ytf
                ytt = connection.T @ ytt @ connection
            else:
                yff = connection.T @ yff @ connection
                yft = connection.T @ yft
                ytf = ytf @ connection
        else:
            pass
        return yff, yft, ytf, ytt
