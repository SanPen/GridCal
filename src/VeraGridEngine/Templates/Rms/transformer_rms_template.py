# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from VeraGridEngine.enumerations import DeviceType, TapPhaseControl, TapModuleControl, WindingType, ParamPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var, sin, cos
from VeraGridEngine.enumerations import WindingsConnection


def parse_windings_connection(conn: WindingsConnection) -> tuple[WindingType, WindingType]:
    """
    Parse a WindingsConnection enum into (conn_f, conn_t) WindingType values.
    
    WindingsConnection values are two-character strings:
    - G: GroundedStar
    - S: NeutralStar (ungrounded star)  
    - D: Delta
    
    Examples:
    - GG -> (GroundedStar, GroundedStar)
    - GD -> (GroundedStar, Delta)
    - DD -> (Delta, Delta)
    """
    conn_str = str(conn)
    if len(conn_str) != 2:
        raise ValueError(f"Invalid WindingsConnection: {conn}")

    char_to_winding = {
        'G': WindingType.GroundedStar,
        'S': WindingType.NeutralStar,
        'D': WindingType.Delta,
    }

    conn_f = char_to_winding.get(conn_str[0])
    conn_t = char_to_winding.get(conn_str[1])

    if conn_f is None or conn_t is None:
        raise ValueError(f"Invalid WindingsConnection characters: {conn_str}")

    return conn_f, conn_t


class TrafoRmsTemplate(RmsModelTemplate):
    __slots__ = (
        "tpe",
        "_block",
    )

    def __init__(self, vf: VarFactory, name: str = "rms_trafo_template"):
        """
        Created the RMS Template of a Bus
        :param vf: VarFactory
        :param name: Name of the RMS Model
        """
        super().__init__(name=name)

        vf = vf
        self.tpe: DeviceType = DeviceType.Transformer2WDevice
        Qf = vf.add_var("Qf", reference=VarPowerFlowReferenceType.Qf)
        Qt = vf.add_var("Qt", reference=VarPowerFlowReferenceType.Qt)
        Pf = vf.add_var("Pf", reference=VarPowerFlowReferenceType.Pf)
        Pt = vf.add_var("Pt", reference=VarPowerFlowReferenceType.Pt)
        m = vf.add_var('m')
        phi = vf.add_var('phi')
        gt = vf.add_var("g")
        bt = vf.add_var("b")
        gFe = vf.add_var('gFe')
        bmu = vf.add_var('bmu')
        vtap_f = vf.add_var('vtap_f')
        vtap_t = vf.add_var('vtap_t')

        # print(f"DEBUG Trafo: R={trafo.R}, X={trafo.X}, G={trafo.G}, B={trafo.B}")
        # print(f"DEBUG Trafo: tap_mod={trafo.tap_module}, tap_phase={trafo.tap_phase}, vtap_f={vtap_f}, vtap_t={vtap_t}")
        # print(f"vtap  p is {vtap_f}")
        # print(f"vtap  t is {vtap_t}")
        # print(f'ys is {ys} ysh is {ysh}')
        Vmf = vf.add_var('Vmf', reference=VarPowerFlowReferenceType.Vmf)
        Vaf = vf.add_var('Vaf', reference=VarPowerFlowReferenceType.Vaf)
        Vmt = vf.add_var('Vmt', reference=VarPowerFlowReferenceType.Vmt)
        Vat = vf.add_var('Vat', reference=VarPowerFlowReferenceType.Vat)
        inputs = [Vmf, Vaf, Vmt, Vat]
        # Calculate phase displacement matching transformer_admittance logic
        # Use conn attribute (preserves user intent) instead of conn_f/conn_t (may be overwritten by template)
        # conn_f, conn_t = parse_windings_connection(trafo.conn)
        # conn_y_from = conn_f == WindingType.NeutralStar or conn_f == WindingType.GroundedStar
        # conn_y_to = conn_t == WindingType.NeutralStar or conn_t == WindingType.GroundedStar
        # if conn_f == WindingType.Delta and conn_y_to:  # Dy
        #    phase_displacement = np.deg2rad(60.0)
        # elif conn_y_from and conn_t == WindingType.Delta:  # Yd
        #    phase_displacement = np.deg2rad(0.0)
        # else:
        #    phase_displacement = 0.0

        phase_displacement = 0
        theta_hk = Vaf - Vat
        # Keep terminal powers in the same semantic order as the RMS branch
        # root interface.  The Dynamic Editor persists graphical ports by
        # index, so a different order would silently cross Qf and Pt when the
        # complete transformer block is connected to its device wrappers.
        block = Block(
            algebraic_vars=[Pf, Qf, Pt, Qt],
            algebraic_eqs=[
                # From side: Pf = Re(Vf * (Yff*Vf + Yft*Vt)*)
                Pf - ((Vmf ** 2 * (gFe / 2 + gt)) / (m * vtap_f) ** 2 - gt / (m * vtap_f * vtap_t) * Vmf * Vmt * cos(
                    theta_hk - phi) - bt / (m * vtap_f * vtap_t) * Vmf * Vmt * sin(
                    theta_hk - phi - phase_displacement)),
                Qf - (-Vmf ** 2 * (bmu / 2 + bt) / (m * vtap_f) ** 2 - gt / (m * vtap_f * vtap_t) * Vmf * Vmt * sin(
                    theta_hk - phi) + bt / (m * vtap_f * vtap_t) * Vmf * Vmt * cos(
                    theta_hk - phi - phase_displacement)),
                # To side: Pt = Re(Vt * (Ytf*Vf + Ytt*Vt)*)
                Pt - ((Vmt ** 2 * (gFe / 2 + gt)) / vtap_t ** 2 - gt / (m * vtap_f * vtap_t) * Vmt * Vmf * cos(
                    theta_hk - phi) + bt / (m * vtap_f * vtap_t) * Vmt * Vmf * sin(
                    theta_hk - phi - phase_displacement)),
                Qt - (-Vmt ** 2 * (bmu / 2 + bt) / vtap_t ** 2 + gt / (m * vtap_f * vtap_t) * Vmt * Vmf * sin(
                    theta_hk - phi) + bt / (m * vtap_f * vtap_t) * Vmt * Vmf * cos(
                    theta_hk - phi - phase_displacement)),
            ],
            in_vars=[Vmf, Vaf, Vmt, Vat],
            out_vars=[Pf, Qf, Pt, Qt],
        )
        block.external_mapping = {
            VarPowerFlowReferenceType.Pf: Pf,
            VarPowerFlowReferenceType.Pt: Pt,
            VarPowerFlowReferenceType.Qf: Qf,
            VarPowerFlowReferenceType.Qt: Qt,
            VarPowerFlowReferenceType.Vaf: Vaf,
            VarPowerFlowReferenceType.Vmf: Vmf,
            VarPowerFlowReferenceType.Vmt: Vmt,
            VarPowerFlowReferenceType.Vat: Vat,
        }
        block.api_obj_mapping = {
            ParamPowerFlowReferenceType.g: gt,
            ParamPowerFlowReferenceType.b: bt,
            ParamPowerFlowReferenceType.gFe: gFe,
            ParamPowerFlowReferenceType.bsh: bmu,
            ParamPowerFlowReferenceType.tap_module: m,
            ParamPowerFlowReferenceType.tap_phase: phi,
            ParamPowerFlowReferenceType.vtap_f: vtap_f,
            ParamPowerFlowReferenceType.vtap_t: vtap_t,
        }

        block.parameters[gt] = vf.add_const(0.0)
        block.parameters[bt] = vf.add_const(0.0)
        block.parameters[gFe] = vf.add_const(0.0)
        block.parameters[bmu] = vf.add_const(0.0)
        block.parameters[m] = vf.add_const(1.0)
        block.parameters[phi] = vf.add_const(0.0)
        block.parameters[vtap_f] = vf.add_const(1.0)
        block.parameters[vtap_t] = vf.add_const(1.0)
        #
        # if trafo.tap_module_control_mode != TapModuleControl.fixed:
        #    del block.event_dict[m]
        #        block.init_eqs[m] = vf.add_const(trafo.tap_module)

        #        Ki = vf.add_var('Ki_mod')
        #        Kd = vf.add_var('Kd_mod')
        #        var_ref = vf.add_var('var_ref')

        #        block.event_dict[Ki] = vf.add_const(0.1)
        #        block.event_dict[Kd] = vf.add_const(0.1)

        #        if trafo.tap_module_control_mode == TapModuleControl.Qf:
        #            control_var = Qf
        #            block.event_dict[var_ref] = vf.add_const(trafo.Qset)
        #        elif trafo.tap_module_control_mode == TapModuleControl.Qt:
        #            control_var = Qt
        #            block.event_dict[var_ref] = vf.add_const(trafo.Qset)
        #        elif trafo.tap_module_control_mode == TapModuleControl.Vm:
        #            control_var = Vmt
        #            block.event_dict[var_ref] = vf.add_const(trafo.vset)

        #        PI_control_block, _, _ = tf_to_block(
        #            var_factory=vf,
        #            num=[Ki],
        #            den=[Kd, vf.add_const(1)],
        #            x=control_var - var_ref,
        #            y=m,
        #        )
        #        block.add(PI_control_block)

        #    if trafo.tap_phase_control_mode != TapPhaseControl.fixed:
        #        discretized_control = True
        #        if discretized_control:
        #            del block.event_dict[phi]
        #            block.init_eqs[phi] = vf.add_const(trafo.tap_phase)

        #            Ki = vf.add_var('Ki_phase')
        #            Kp = vf.add_var('Kp_phase')
        #            Tm = vf.add_var('Tm')
        #            var_ref = vf.add_var('var_ref')
        #            block.event_dict[Ki] = vf.add_const(0.1)
        #            block.event_dict[Kp] = vf.add_const(0.1)
        #            block.event_dict[Tm] = vf.add_const(0.1)

        #            if trafo.tap_phase_control_mode == TapPhaseControl.Pf:
        #                control_var = Pf
        #                block.event_dict[var_ref] = vf.add_const(trafo.Pset / Sbase)
        #            elif trafo.tap_phase_control_mode == TapPhaseControl.Pt:
        #                control_var = Pt
        #                block.event_dict[var_ref] = vf.add_const(trafo.Pset / Sbase)

        #            discretized_control,_ = discrete_control_block(
        #                var_factory=vf,
        #                m=m,
        #                m_min=trafo.tap_phase_min,
        #                m_max=trafo.tap_phase_max,
        #                delta_m=trafo.tap_phase_step,
        #                v=control_var,
        #                v_ref=var_ref,
        #                delta_v=0.01,
        #                ts=Tm,
        #            )
        #            block.children.append(discretized_control)
        #        else:
        #            del block.event_dict[phi]
        #            block.init_eqs[phi] = vf.add_const(trafo.tap_phase)

        #            Ki = vf.add_var('Ki_phase')
        #            Kp = vf.add_var('Kp_phase')
        #            var_ref = vf.add_var('var_ref')
        #            block.event_dict[Ki] = vf.add_const(0.1)
        #            block.event_dict[Kp] = vf.add_const(0.1)

        #            if trafo.tap_phase_control_mode == TapPhaseControl.Pf:
        #                control_var = Pf
        #                block.event_dict[var_ref] = vf.add_const(trafo.Pset / Sbase)
        #            elif trafo.tap_phase_control_mode == TapPhaseControl.Pt:
        #                control_var = Pt
        #                block.event_dict[var_ref] = vf.add_const(trafo.Pset / Sbase)

        #            PI_control_block, _ = tf_to_block(
        #                var_factory=vf,
        #                num=[Ki, Kp],
        #                den=[0, vf.add_const(1)],
        #                x=control_var - var_ref,
        #                y=phi,
        #                name="Phase_Control_PI"
        #            )
        #            block.children.append(PI_control_block)
        #    block.unify_blocks()

        block.in_vars = inputs

        self._block.children.append(block)
        self._block.external_mapping = block.external_mapping
        self._block.in_vars = inputs
        self._block.out_vars = block.out_vars


class IdealTrafoRmsTemplate(RmsModelTemplate):
    """Represent an ideal two-winding transformer without a fake impedance."""

    __slots__ = (
        "tpe",
        "_block",
    )

    def __init__(
            self,
            vf: VarFactory,
            name: str = "rms_ideal_trafo_template",
    ) -> None:
        """Build the fixed-size polar DAE of an ideal transformer.

        The model preserves the exact voltage-ratio and phase constraints while
        leaving active and reactive transfer powers to the connected bus
        balances. This is the finite DAE counterpart of the zero-impedance
        branch contraction used by the static solver.

        :param vf: Variable factory shared by the owning circuit.
        :param name: Human-readable template name.
        :return: None.
        """
        super().__init__(name=name)
        self.tpe: DeviceType = DeviceType.Transformer2WDevice
        self.comment = 'Transformer two-winding ideal RMS model'

        # Four power-flow variables retain the regular transformer interface so
        # buses and result reporting do not need a case-specific code path.
        active_power_from: Var = vf.add_var("Pf")
        active_power_to: Var = vf.add_var("Pt")
        reactive_power_from: Var = vf.add_var("Qf")
        reactive_power_to: Var = vf.add_var("Qt")
        tap_module: Var = vf.add_var("m")
        tap_phase: Var = vf.add_var("phi")
        iron_conductance: Var = vf.add_var("gFe")
        magnetizing_susceptance: Var = vf.add_var("bmu")
        voltage_tap_from: Var = vf.add_var("vtap_f")
        voltage_tap_to: Var = vf.add_var("vtap_t")
        conduction_status: Var = vf.add_var("u")

        voltage_magnitude_from: Var = vf.add_var(
            "Vmf",
            VarPowerFlowReferenceType.Vmf,
        )
        voltage_angle_from: Var = vf.add_var(
            "Vaf",
            VarPowerFlowReferenceType.Vaf,
        )
        voltage_magnitude_to: Var = vf.add_var(
            "Vmt",
            VarPowerFlowReferenceType.Vmt,
        )
        voltage_angle_to: Var = vf.add_var(
            "Vat",
            VarPowerFlowReferenceType.Vat,
        )

        # Virtual taps convert both terminals to the same internal per-unit
        # base. The ideal branch then enforces equality without a large-number
        # admittance approximation that would damage the Newton conditioning.
        internal_voltage_from: Expr = (
            voltage_magnitude_from / (tap_module * voltage_tap_from)
        )
        internal_voltage_to: Expr = voltage_magnitude_to / voltage_tap_to
        total_squared_voltage: Expr = (
            internal_voltage_from ** 2 + internal_voltage_to ** 2
        )
        total_active_shunt_power: Expr = (
            iron_conductance * total_squared_voltage / 2.0
        )
        total_reactive_shunt_power: Expr = (
            -magnetizing_susceptance * total_squared_voltage / 2.0
        )

        # When closed, two equations conserve transfer power and two impose the
        # ideal voltage constraints. When open, the same four rows reduce to
        # independent zero-flow equations, preserving a fixed nonsingular DAE.
        block: Block = Block(
            algebraic_vars=[
                active_power_from,
                active_power_to,
                reactive_power_from,
                reactive_power_to,
            ],
            algebraic_eqs=[
                active_power_from
                + active_power_to
                - conduction_status * total_active_shunt_power,
                reactive_power_from
                + reactive_power_to
                - conduction_status * total_reactive_shunt_power,
                conduction_status * (internal_voltage_from - internal_voltage_to)
                + (1.0 - conduction_status) * active_power_from,
                conduction_status
                * (voltage_angle_from - voltage_angle_to - tap_phase)
                + (1.0 - conduction_status) * reactive_power_from,
            ],
            in_vars=[
                voltage_magnitude_from,
                voltage_angle_from,
                voltage_magnitude_to,
                voltage_angle_to,
            ],
        )
        block.external_mapping = dict({
            VarPowerFlowReferenceType.Pf: active_power_from,
            VarPowerFlowReferenceType.Pt: active_power_to,
            VarPowerFlowReferenceType.Qf: reactive_power_from,
            VarPowerFlowReferenceType.Qt: reactive_power_to,
            VarPowerFlowReferenceType.Vaf: voltage_angle_from,
            VarPowerFlowReferenceType.Vmf: voltage_magnitude_from,
            VarPowerFlowReferenceType.Vmt: voltage_magnitude_to,
            VarPowerFlowReferenceType.Vat: voltage_angle_to,
        })
        block.api_obj_mapping = dict({
            ParamPowerFlowReferenceType.gFe: iron_conductance,
            ParamPowerFlowReferenceType.bsh: magnetizing_susceptance,
            ParamPowerFlowReferenceType.tap_module: tap_module,
            ParamPowerFlowReferenceType.tap_phase: tap_phase,
            ParamPowerFlowReferenceType.vtap_f: voltage_tap_from,
            ParamPowerFlowReferenceType.vtap_t: voltage_tap_to,
        })
        block.parameters[iron_conductance] = vf.add_const(0.0)
        block.parameters[magnetizing_susceptance] = vf.add_const(0.0)
        block.parameters[tap_module] = vf.add_const(1.0)
        block.parameters[tap_phase] = vf.add_const(0.0)
        block.parameters[voltage_tap_from] = vf.add_const(1.0)
        block.parameters[voltage_tap_to] = vf.add_const(1.0)
        block.event_dict[conduction_status] = vf.add_const(1.0)
        block.dynamic_model_contract.rms_conduction_status_var_uid = conduction_status.uid
        block.dynamic_model_contract.rms_ideal_transformer = True
        # An ideal transformer has no local constitutive equation that fixes
        # transfer power: the two connected nodal balances determine it. Keep
        # the power-flow Pf/Pt/Qf/Qt seeds until the global DAE is assembled
        # instead of applying the underdetermined device-local initializer.
        block.dynamic_model_contract.skip_device_local_explicit_init = True
        block.dynamic_model_contract.startup_initial_reduced_polish_var_names = list([
            "Pf",
            "Pt",
            "Qf",
            "Qt",
        ])
        self._block: Block = block

class TrafoPhasorRmsTemplate(RmsModelTemplate):
    __slots__ = ()

    def __init__(self, vf: VarFactory, name: str = "rms_trafo_phasor_template"):
        """
        Current-based phasor RMS template for a 2-winding transformer.

        Inputs use rectangular bus voltages (Vrf, Vif, Vrt, Vit) and outputs
        branch currents directly (Irf, Iif, Irt, Iit), matching the line phasor
        template interface used by current-balance RMS formulations.
        """
        super().__init__(name=name)

        self.tpe: DeviceType = DeviceType.Transformer2WDevice
        Vrf = vf.add_var("Vrf", VarPowerFlowReferenceType.Vrf)
        Vif = vf.add_var("Vif", VarPowerFlowReferenceType.Vif)
        Vrt = vf.add_var("Vrt", VarPowerFlowReferenceType.Vrt)
        Vit = vf.add_var("Vit", VarPowerFlowReferenceType.Vit)

        Irf = vf.add_var("Irf")
        Iif = vf.add_var("Iif")
        Irt = vf.add_var("Irt")
        Iit = vf.add_var("Iit")

        gt = vf.add_var("g")
        bt = vf.add_var("b")
        gFe = vf.add_var("gFe")
        bmu = vf.add_var("bmu")
        tap_module = vf.add_var("tap_module")
        tap_phase = vf.add_var("tap_phase")
        vtap_f = vf.add_var("vtap_f")
        vtap_t = vf.add_var("vtap_t")
        phase_displacement = vf.add_var("phase_displacement")

        theta0 = tap_phase + phase_displacement
        cos_theta0 = cos(theta0)
        sin_theta0 = sin(theta0)

        k_from = tap_module * vtap_f
        k_cross = tap_module * vtap_f * vtap_t
        k_to = vtap_t

        # Admittance coefficients in rectangular form
        gff = (gFe / 2 + gt) / (k_from ** 2)
        bff = (bmu / 2 + bt) / (k_from ** 2)
        gtt = (gFe / 2 + gt) / (k_to ** 2)
        btt = (bmu / 2 + bt) / (k_to ** 2)

        # Yft = -(gt + j*bt) / (m*vtap_f*vtap_t*exp(-j*theta))
        gft = -(gt * cos_theta0 - bt * sin_theta0) / k_cross
        bft = -(gt * sin_theta0 + bt * cos_theta0) / k_cross

        # Ytf = -(gt + j*bt) / (m*vtap_f*vtap_t*exp(j*theta))
        gtf = -(gt * cos_theta0 + bt * sin_theta0) / k_cross
        btf = (gt * sin_theta0 - bt * cos_theta0) / k_cross

        block = Block(
            algebraic_vars=[Irf, Iif, Irt, Iit],
            algebraic_eqs=[
                Irf - (gff * Vrf - bff * Vif + gft * Vrt - bft * Vit),
                Iif - (bff * Vrf + gff * Vif + bft * Vrt + gft * Vit),
                Irt - (gtf * Vrf - btf * Vif + gtt * Vrt - btt * Vit),
                Iit - (btf * Vrf + gtf * Vif + btt * Vrt + gtt * Vit),
            ],
            in_vars=[Vrf, Vif, Vrt, Vit],
        )

        block.external_mapping = {
            VarPowerFlowReferenceType.Vrf: Vrf,
            VarPowerFlowReferenceType.Vif: Vif,
            VarPowerFlowReferenceType.Vrt: Vrt,
            VarPowerFlowReferenceType.Vit: Vit,
            VarPowerFlowReferenceType.Irf: Irf,
            VarPowerFlowReferenceType.Iif: Iif,
            VarPowerFlowReferenceType.Irt: Irt,
            VarPowerFlowReferenceType.Iit: Iit,
        }

        block.api_obj_mapping = {
            ParamPowerFlowReferenceType.g: gt,
            ParamPowerFlowReferenceType.b: bt,
            ParamPowerFlowReferenceType.bsh: bmu,
            ParamPowerFlowReferenceType.gFe: gFe,
            ParamPowerFlowReferenceType.tap_module: tap_module,
            ParamPowerFlowReferenceType.tap_phase: tap_phase,
            ParamPowerFlowReferenceType.vtap_f: vtap_f,
            ParamPowerFlowReferenceType.vtap_t: vtap_t,
        }

        block.parameters[gt] = vf.add_const(0.0)
        block.parameters[bt] = vf.add_const(0.0)
        block.parameters[gFe] = vf.add_const(0.0)
        block.parameters[bmu] = vf.add_const(0.0)
        block.parameters[tap_module] = vf.add_const(1.0)
        block.parameters[tap_phase] = vf.add_const(0.0)
        block.parameters[vtap_f] = vf.add_const(1.0)
        block.parameters[vtap_t] = vf.add_const(1.0)
        block.parameters[phase_displacement] = vf.add_const(0)

        self._block = block


def get_transformer2w_rms(vf: VarFactory, use_phasor_template: bool = False):
    if use_phasor_template:
        return TrafoPhasorRmsTemplate(vf=vf)
    return TrafoRmsTemplate(vf=vf)


def get_ideal_transformer2w_rms(
        vf: VarFactory,
        name: str = "rms_ideal_trafo_template",
) -> RmsModelTemplate:
    """Build the exact zero-series-impedance transformer RMS template.

    :param vf: Variable factory shared by the owning circuit.
    :param name: Human-readable template name.
    :return: Ideal-transformer RMS template.
    """
    return IdealTrafoRmsTemplate(vf=vf, name=name)

def initialize_trafo_rms(trafo: Transformer2W, vf: VarFactory):
    """

    :param trafo:
    :param vf:
    :return:
    """
    templ = TrafoRmsTemplate(vf=vf)
    trafo.rms_model = templ.block
    return templ
