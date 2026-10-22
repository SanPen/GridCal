# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Maintainable international-standard module for 'ExAc1'.

This is the runtime implementation shipped by VeraGrid.
It exposes the imported public interface, explicit symbolic equations, and
"""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex, _anti_windup_state_derivative

def build_exac1_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build the shared five-state brushless alternator and diode-bridge equations.

    Voltage sensing and phase compensation feed a bounded amplifier. The
    rotating exciter field integrates forcing minus resistive, saturation and
    generator-current demagnetization terms. Its memory has a zero lower stop
    with immediate inward recovery. Live generator field current also controls
    the diode-bridge commutation drop. Filtered rate feedback measures the
    internal exciter field-current equivalent, including all field-circuit losses.

    Inputs are generator field current, additive overexcitation voltage,
    stabilizing voltage, sensed voltage, reference voltage and additive minimum-
    excitation voltage. The output is rectified generator field voltage. Signals
    are per unit on their connected field bases and time constants are seconds.
    Five states store sensing, phase, amplifier, field and feedback memories.
    Native catalogue composition prepares operating-point port seeds and the
    scaled phase state, retaining these physical winding and rectifier equations.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :return: Shared winding and rectifier realization for controller composition.
    """
    template_name: str
    if name is None:
        template_name: str = 'ExAc1'
    else:
        template_name: str = name

    # Allocate the template container before building the symbolic surface.
    template: RmsModelTemplate = RmsModelTemplate()
    template.tpe = DeviceType.GeneratorDevice
    template.name = template_name

    # Declare every variable explicitly before the equations reference it.
    # Declare the runtime parameter variables used by the template.
    avr_A1: Var = vf.add_var('avr.A1_' + template_name)
    avr_A2: Var = vf.add_var('avr.A2_' + template_name)
    avr_Bsq: Var = vf.add_var('avr.Bsq_' + template_name)
    avr_Efd0Pu: Var = vf.add_var('avr.Efd0Pu_' + template_name)
    avr_Ir0Pu: Var = vf.add_var('avr.Ir0Pu_' + template_name)
    avr_Ka: Var = vf.add_var('avr.Ka_' + template_name)
    avr_Kc: Var = vf.add_var('avr.Kc_' + template_name)
    avr_Kd: Var = vf.add_var('avr.Kd_' + template_name)
    avr_Ke: Var = vf.add_var('avr.Ke_' + template_name)
    avr_Kf: Var = vf.add_var('avr.Kf_' + template_name)
    avr_Sq: Var = vf.add_var('avr.Sq_' + template_name)
    avr_UHigh: Var = vf.add_var('avr.UHigh_' + template_name)
    avr_ULow: Var = vf.add_var('avr.ULow_' + template_name)
    avr_Ua0: Var = vf.add_var('avr.Ua0_' + template_name)
    avr_Ub0: Var = vf.add_var('avr.Ub0_' + template_name)
    avr_Uc0: Var = vf.add_var('avr.Uc0_' + template_name)
    avr_Us0Pu: Var = vf.add_var('avr.Us0Pu_' + template_name)
    avr_UsRef0Pu: Var = vf.add_var('avr.UsRef0Pu_' + template_name)
    avr_VExc0Pu: Var = vf.add_var('avr.VExc0Pu_' + template_name)
    avr_VExcHighPu: Var = vf.add_var('avr.VExcHighPu_' + template_name)
    avr_VExcLowPu: Var = vf.add_var('avr.VExcLowPu_' + template_name)
    avr_VExcSatHighPu: Var = vf.add_var('avr.VExcSatHighPu_' + template_name)
    avr_VExcSatLowPu: Var = vf.add_var('avr.VExcSatLowPu_' + template_name)
    avr_VExcThresholdPu: Var = vf.add_var('avr.VExcThresholdPu_' + template_name)
    avr_Vr0Pu: Var = vf.add_var('avr.Vr0Pu_' + template_name)
    avr_VrMaxPu: Var = vf.add_var('avr.VrMaxPu_' + template_name)
    avr_VrMinPu: Var = vf.add_var('avr.VrMinPu_' + template_name)
    avr_Y0: Var = vf.add_var('avr.Y0_' + template_name)
    avr_add3_k1: Var = vf.add_var('avr.add3.k1_' + template_name)
    avr_add3_k2: Var = vf.add_var('avr.add3.k2_' + template_name)
    avr_add3_k3: Var = vf.add_var('avr.add3.k3_' + template_name)
    avr_const_k: Var = vf.add_var('avr.const.k_' + template_name)
    avr_derivative_T: Var = vf.add_var('avr.derivative.T_' + template_name)
    avr_derivative_initType: Var = vf.add_var('avr.derivative.initType_' + template_name)
    avr_derivative_k: Var = vf.add_var('avr.derivative.k_' + template_name)
    avr_derivative_x_start: Var = vf.add_var('avr.derivative.x_start_' + template_name)
    avr_derivative_y_start: Var = vf.add_var('avr.derivative.y_start_' + template_name)
    avr_derivative_zeroGain: Var = vf.add_var('avr.derivative.zeroGain_' + template_name)
    avr_firstOrder_T: Var = vf.add_var('avr.firstOrder.T_' + template_name)
    avr_firstOrder_initType: Var = vf.add_var('avr.firstOrder.initType_' + template_name)
    avr_firstOrder_k: Var = vf.add_var('avr.firstOrder.k_' + template_name)
    avr_firstOrder_y_start: Var = vf.add_var('avr.firstOrder.y_start_' + template_name)
    avr_gain1_k: Var = vf.add_var('avr.gain1.k_' + template_name)
    avr_integrator_initType: Var = vf.add_var('avr.integrator.initType_' + template_name)
    avr_integrator_k: Var = vf.add_var('avr.integrator.k_' + template_name)
    avr_integrator_use_reset: Var = vf.add_var('avr.integrator.use_reset_' + template_name)
    avr_integrator_use_set: Var = vf.add_var('avr.integrator.use_set_' + template_name)
    avr_integrator_y_start: Var = vf.add_var('avr.integrator.y_start_' + template_name)
    avr_leadLag_a_1: Var = vf.add_var('avr.leadLag.a[1]_' + template_name)
    avr_leadLag_a_2: Var = vf.add_var('avr.leadLag.a[2]_' + template_name)
    avr_leadLag_a_end: Var = vf.add_var('avr.leadLag.a_end_' + template_name)
    avr_leadLag_b_1: Var = vf.add_var('avr.leadLag.b[1]_' + template_name)
    avr_leadLag_b_2: Var = vf.add_var('avr.leadLag.b[2]_' + template_name)
    avr_leadLag_bb_1: Var = vf.add_var('avr.leadLag.bb[1]_' + template_name)
    avr_leadLag_bb_2: Var = vf.add_var('avr.leadLag.bb[2]_' + template_name)
    avr_leadLag_d: Var = vf.add_var('avr.leadLag.d_' + template_name)
    avr_leadLag_na: Var = vf.add_var('avr.leadLag.na_' + template_name)
    avr_leadLag_nb: Var = vf.add_var('avr.leadLag.nb_' + template_name)
    avr_leadLag_nx: Var = vf.add_var('avr.leadLag.nx_' + template_name)
    avr_leadLag_x_start_1: Var = vf.add_var('avr.leadLag.x_start[1]_' + template_name)
    avr_leadLag_y_start: Var = vf.add_var('avr.leadLag.y_start_' + template_name)
    avr_limitedFirstOrder_G_k: Var = vf.add_var('avr.limitedFirstOrder.G.k_' + template_name)
    avr_limitedFirstOrder_Gk_k: Var = vf.add_var('avr.limitedFirstOrder.Gk.k_' + template_name)
    avr_limitedFirstOrder_I_initType: Var = vf.add_var('avr.limitedFirstOrder.I.initType_' + template_name)
    avr_limitedFirstOrder_I_k: Var = vf.add_var('avr.limitedFirstOrder.I.k_' + template_name)
    avr_limitedFirstOrder_I_use_reset: Var = vf.add_var('avr.limitedFirstOrder.I.use_reset_' + template_name)
    avr_limitedFirstOrder_I_use_set: Var = vf.add_var('avr.limitedFirstOrder.I.use_set_' + template_name)
    avr_limitedFirstOrder_I_y_start: Var = vf.add_var('avr.limitedFirstOrder.I.y_start_' + template_name)
    avr_limitedFirstOrder_K: Var = vf.add_var('avr.limitedFirstOrder.K_' + template_name)
    avr_limitedFirstOrder_Y0: Var = vf.add_var('avr.limitedFirstOrder.Y0_' + template_name)
    avr_limitedFirstOrder_YMax: Var = vf.add_var('avr.limitedFirstOrder.YMax_' + template_name)
    avr_limitedFirstOrder_YMin: Var = vf.add_var('avr.limitedFirstOrder.YMin_' + template_name)
    avr_limitedFirstOrder_lim_homotopyType: Var = vf.add_var('avr.limitedFirstOrder.lim.homotopyType_' + template_name)
    avr_limitedFirstOrder_lim_limitsAtInit: Var = vf.add_var('avr.limitedFirstOrder.lim.limitsAtInit_' + template_name)
    avr_limitedFirstOrder_lim_strict: Var = vf.add_var('avr.limitedFirstOrder.lim.strict_' + template_name)
    avr_limitedFirstOrder_lim_uMax: Var = vf.add_var('avr.limitedFirstOrder.lim.uMax_' + template_name)
    avr_limitedFirstOrder_lim_uMin: Var = vf.add_var('avr.limitedFirstOrder.lim.uMin_' + template_name)
    avr_limitedFirstOrder_tFilter: Var = vf.add_var('avr.limitedFirstOrder.tFilter_' + template_name)
    avr_limiter_homotopyType: Var = vf.add_var('avr.limiter.homotopyType_' + template_name)
    avr_limiter_limitsAtInit: Var = vf.add_var('avr.limiter.limitsAtInit_' + template_name)
    avr_limiter_strict: Var = vf.add_var('avr.limiter.strict_' + template_name)
    avr_limiter_uMax: Var = vf.add_var('avr.limiter.uMax_' + template_name)
    avr_limiter_uMin: Var = vf.add_var('avr.limiter.uMin_' + template_name)
    avr_rectifierRegulationCharacteristic_A1: Var = vf.add_var('avr.rectifierRegulationCharacteristic.A1_' + template_name)
    avr_rectifierRegulationCharacteristic_A2: Var = vf.add_var('avr.rectifierRegulationCharacteristic.A2_' + template_name)
    avr_rectifierRegulationCharacteristic_UHigh: Var = vf.add_var('avr.rectifierRegulationCharacteristic.UHigh_' + template_name)
    avr_rectifierRegulationCharacteristic_ULow: Var = vf.add_var('avr.rectifierRegulationCharacteristic.ULow_' + template_name)
    avr_satChar_Asq: Var = vf.add_var('avr.satChar.Asq_' + template_name)
    avr_satChar_Bsq: Var = vf.add_var('avr.satChar.Bsq_' + template_name)
    avr_satChar_Sq: Var = vf.add_var('avr.satChar.Sq_' + template_name)
    avr_satChar_UHigh: Var = vf.add_var('avr.satChar.UHigh_' + template_name)
    avr_satChar_ULow: Var = vf.add_var('avr.satChar.ULow_' + template_name)
    avr_satChar_YHigh: Var = vf.add_var('avr.satChar.YHigh_' + template_name)
    avr_satChar_YLow: Var = vf.add_var('avr.satChar.YLow_' + template_name)
    avr_sum1_k_1: Var = vf.add_var('avr.sum1.k[1]_' + template_name)
    avr_sum1_k_2: Var = vf.add_var('avr.sum1.k[2]_' + template_name)
    avr_sum1_k_3: Var = vf.add_var('avr.sum1.k[3]_' + template_name)
    avr_sum1_k_4: Var = vf.add_var('avr.sum1.k[4]_' + template_name)
    avr_sum1_k_5: Var = vf.add_var('avr.sum1.k[5]_' + template_name)
    avr_sum1_nin: Var = vf.add_var('avr.sum1.nin_' + template_name)
    avr_tA: Var = vf.add_var('avr.tA_' + template_name)
    avr_tB: Var = vf.add_var('avr.tB_' + template_name)
    avr_tC: Var = vf.add_var('avr.tC_' + template_name)
    avr_tE: Var = vf.add_var('avr.tE_' + template_name)
    avr_tF: Var = vf.add_var('avr.tF_' + template_name)
    avr_tR: Var = vf.add_var('avr.tR_' + template_name)
    # Declare the state variables used by the template.
    avr_derivative_x: Var = vf.add_var('avr.derivative.x_' + template_name)
    avr_firstOrder_y: Var = vf.add_var('avr.firstOrder.y_' + template_name)
    avr_integrator_y: Var = vf.add_var('avr.integrator.y_' + template_name)
    avr_leadLag_x_scaled_1: Var = vf.add_var('avr.leadLag.x_scaled[1]_' + template_name)
    avr_limitedFirstOrder_I_y: Var = vf.add_var('avr.limitedFirstOrder.I.y_' + template_name)
    # Declare the algebraic/shared variables used by the template.
    START_avr_derivative_x: Var = vf.add_var('$START.avr.derivative.x_' + template_name)
    START_avr_firstOrder_y: Var = vf.add_var('$START.avr.firstOrder.y_' + template_name)
    START_avr_leadLag_x_scaled_1: Var = vf.add_var('$START.avr.leadLag.x_scaled[1]_' + template_name)
    avr_EfdPu: Var = vf.add_var('avr.EfdPu_' + template_name)
    avr_IrPu: Var = vf.add_var('avr.IrPu_' + template_name)
    avr_UOelPu: Var = vf.add_var('avr.UOelPu_' + template_name)
    avr_UPssPu: Var = vf.add_var('avr.UPssPu_' + template_name)
    avr_UUelPu: Var = vf.add_var('avr.UUelPu_' + template_name)
    avr_UsPu: Var = vf.add_var('avr.UsPu_' + template_name)
    avr_UsRefPu: Var = vf.add_var('avr.UsRefPu_' + template_name)
    avr_add3_y: Var = vf.add_var('avr.add3.y_' + template_name)
    avr_derivative_y: Var = vf.add_var('avr.derivative.y_' + template_name)
    avr_division_y: Var = vf.add_var('avr.division.y_' + template_name)
    avr_feedback_y: Var = vf.add_var('avr.feedback.y_' + template_name)
    avr_feedback1_y: Var = vf.add_var('avr.feedback1.y_' + template_name)
    avr_integrator_local_reset: Var = vf.add_var('avr.integrator.local_reset_' + template_name)
    avr_integrator_local_set: Var = vf.add_var('avr.integrator.local_set_' + template_name)
    avr_leadLag_x_1: Var = vf.add_var('avr.leadLag.x[1]_' + template_name)
    avr_leadLag_y: Var = vf.add_var('avr.leadLag.y_' + template_name)
    avr_limitedFirstOrder_G_y: Var = vf.add_var('avr.limitedFirstOrder.G.y_' + template_name)
    avr_limitedFirstOrder_Gk_y: Var = vf.add_var('avr.limitedFirstOrder.Gk.y_' + template_name)
    avr_limitedFirstOrder_I_local_reset: Var = vf.add_var('avr.limitedFirstOrder.I.local_reset_' + template_name)
    avr_limitedFirstOrder_I_local_set: Var = vf.add_var('avr.limitedFirstOrder.I.local_set_' + template_name)
    avr_limitedFirstOrder_I_u: Var = vf.add_var('avr.limitedFirstOrder.I.u_' + template_name)
    avr_limitedFirstOrder_feedback_y: Var = vf.add_var('avr.limitedFirstOrder.feedback.y_' + template_name)
    avr_limitedFirstOrder_lim_simplifiedExpr: Var = vf.add_var('avr.limitedFirstOrder.lim.simplifiedExpr_' + template_name)
    avr_limitedFirstOrder_y: Var = vf.add_var('avr.limitedFirstOrder.y_' + template_name)
    avr_limiter_simplifiedExpr: Var = vf.add_var('avr.limiter.simplifiedExpr_' + template_name)
    avr_limiter_y: Var = vf.add_var('avr.limiter.y_' + template_name)
    avr_max1_y: Var = vf.add_var('avr.max1.y_' + template_name)
    avr_rectifierRegulationCharacteristic_y: Var = vf.add_var('avr.rectifierRegulationCharacteristic.y_' + template_name)
    avr_satChar_y: Var = vf.add_var('avr.satChar.y_' + template_name)
    avr_sum1_y: Var = vf.add_var('avr.sum1.y_' + template_name)
    # Declare the differential variables used by the template.
    d_avr_derivative_x: Var = vf.add_diff_var('d_avr.derivative.x_' + template_name, base_var=avr_derivative_x)
    d_avr_firstOrder_y: Var = vf.add_diff_var('d_avr.firstOrder.y_' + template_name, base_var=avr_firstOrder_y)
    d_avr_integrator_y: Var = vf.add_diff_var('d_avr.integrator.y_' + template_name, base_var=avr_integrator_y)
    d_avr_leadLag_x_scaled_1: Var = vf.add_diff_var('d_avr.leadLag.x_scaled[1]_' + template_name, base_var=avr_leadLag_x_scaled_1)
    d_avr_limitedFirstOrder_I_y: Var = vf.add_diff_var('d_avr.limitedFirstOrder.I.y_' + template_name, base_var=avr_limitedFirstOrder_I_y)

    # Build explicit typed collections so the symbolic surface is easy to inspect.
    state_equations: list[Expr] = list()
    # The rotating field's lower stop acts on its memory as well as its output,
    # preventing negative stored flux and delayed recovery after de-excitation.
    field_derivative: Expr = avr_integrator_k * avr_feedback1_y
    state_equations.append((Const(1.0)-(Const(1.0)-sym.heaviside(avr_integrator_y))
        *sym.heaviside(-field_derivative))*field_derivative)
    state_equations.append(((avr_derivative_zeroGain * sym.Const(0.0)) + ((sym.Const(1.0) - avr_derivative_zeroGain) * ((avr_add3_y - avr_derivative_x) / avr_derivative_T))))
    state_equations.append((avr_limitedFirstOrder_I_k * avr_limitedFirstOrder_I_u))
    state_equations.append((((avr_leadLag_a_end * avr_feedback_y) - (avr_leadLag_a_2 * avr_leadLag_x_scaled_1)) / avr_leadLag_a_1))
    state_equations.append((((avr_firstOrder_k * avr_UsPu) - avr_firstOrder_y) / avr_firstOrder_T))
    state_variables: list[Var] = list()
    state_variables.append(avr_integrator_y)
    state_variables.append(avr_derivative_x)
    state_variables.append(avr_limitedFirstOrder_I_y)
    state_variables.append(avr_leadLag_x_scaled_1)
    state_variables.append(avr_firstOrder_y)
    algebraic_equations: list[Expr] = list()
    algebraic_equations.append((avr_limitedFirstOrder_y - ((sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06))) * avr_limitedFirstOrder_lim_uMax) + ((sym.Const(1.0) - sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06)))) * ((sym.heaviside(((avr_limitedFirstOrder_lim_uMin - avr_limitedFirstOrder_I_y) - sym.Const(1e-06))) * avr_limitedFirstOrder_lim_uMin) + ((sym.Const(1.0) - sym.heaviside(((avr_limitedFirstOrder_lim_uMin - avr_limitedFirstOrder_I_y) - sym.Const(1e-06)))) * avr_limitedFirstOrder_I_y))))))
    algebraic_equations.append((avr_sum1_y - (((((avr_sum1_k_1 * avr_UOelPu) + (avr_sum1_k_2 * avr_UPssPu)) + (avr_sum1_k_3 * avr_UUelPu)) + (avr_sum1_k_4 * avr_UsRefPu)) + (avr_sum1_k_5 * avr_firstOrder_y))))
    algebraic_equations.append((avr_limiter_y - ((sym.heaviside(((avr_integrator_y - avr_limiter_uMax) - sym.Const(1e-06))) * avr_limiter_uMax) + ((sym.Const(1.0) - sym.heaviside(((avr_integrator_y - avr_limiter_uMax) - sym.Const(1e-06)))) * ((sym.heaviside(((avr_limiter_uMin - avr_integrator_y) - sym.Const(1e-06))) * avr_limiter_uMin) + ((sym.Const(1.0) - sym.heaviside(((avr_limiter_uMin - avr_integrator_y) - sym.Const(1e-06)))) * avr_integrator_y))))))
    algebraic_equations.append((avr_max1_y - ((avr_limiter_y * sym.heaviside((avr_limiter_y - avr_const_k))) + (avr_const_k * (sym.Const(1) - sym.heaviside((avr_limiter_y - avr_const_k)))))))
    algebraic_equations.append((avr_satChar_y - ((sym.heaviside(((avr_limiter_y - avr_satChar_Asq) - sym.Const(1e-06))) * (avr_satChar_Bsq * ((avr_limiter_y - avr_satChar_Asq) ** sym.Const(2.0)))) + ((sym.Const(1.0) - sym.heaviside(((avr_limiter_y - avr_satChar_Asq) - sym.Const(1e-06)))) * sym.Const(0.0)))))
    algebraic_equations.append(avr_division_y-avr_Kc*avr_IrPu/avr_max1_y)
    algebraic_equations.append(avr_rectifierRegulationCharacteristic_y-_esst3a_fex(
        avr_division_y, avr_rectifierRegulationCharacteristic_ULow,
        avr_rectifierRegulationCharacteristic_UHigh,
        avr_rectifierRegulationCharacteristic_A1, avr_rectifierRegulationCharacteristic_A2))
    algebraic_equations.append((avr_EfdPu - (avr_limiter_y * avr_rectifierRegulationCharacteristic_y)))
    algebraic_equations.append(avr_add3_y-(avr_add3_k1*avr_satChar_y+avr_add3_k2*avr_limiter_y+avr_Kd*avr_IrPu))
    algebraic_equations.append((avr_feedback1_y - (avr_limitedFirstOrder_y - avr_add3_y)))
    algebraic_equations.append((avr_derivative_y - ((avr_derivative_zeroGain * sym.Const(0.0)) + ((sym.Const(1.0) - avr_derivative_zeroGain) * ((avr_derivative_k / avr_derivative_T) * (avr_add3_y - avr_derivative_x))))))
    algebraic_equations.append((avr_feedback_y - (avr_sum1_y - avr_derivative_y)))
    algebraic_equations.append((avr_leadLag_x_1 - (avr_leadLag_x_scaled_1 / avr_leadLag_a_end)))
    algebraic_equations.append((avr_leadLag_y - (((avr_leadLag_bb_2 - (avr_leadLag_d * avr_leadLag_a_2)) * avr_leadLag_x_1) + (avr_leadLag_d * avr_feedback_y))))
    algebraic_equations.append((avr_limitedFirstOrder_Gk_y - (avr_limitedFirstOrder_Gk_k * avr_leadLag_y)))
    algebraic_equations.append((avr_limitedFirstOrder_feedback_y - (avr_limitedFirstOrder_Gk_y - avr_limitedFirstOrder_y)))
    algebraic_equations.append((avr_limitedFirstOrder_G_y - (avr_limitedFirstOrder_G_k * avr_limitedFirstOrder_feedback_y)))
    # A directional stop includes equality at the bound and releases inward.
    algebraic_equations.append(avr_limitedFirstOrder_I_u-_anti_windup_state_derivative(
        avr_limitedFirstOrder_I_y, avr_limitedFirstOrder_G_y,
        avr_limitedFirstOrder_lim_uMin, avr_limitedFirstOrder_lim_uMax))
    algebraic_variables: list[Var] = list()
    algebraic_variables.append(avr_limitedFirstOrder_y)
    algebraic_variables.append(avr_sum1_y)
    algebraic_variables.append(avr_limiter_y)
    algebraic_variables.append(avr_max1_y)
    algebraic_variables.append(avr_satChar_y)
    algebraic_variables.append(avr_division_y)
    algebraic_variables.append(avr_rectifierRegulationCharacteristic_y)
    algebraic_variables.append(avr_EfdPu)
    algebraic_variables.append(avr_add3_y)
    algebraic_variables.append(avr_feedback1_y)
    algebraic_variables.append(avr_derivative_y)
    algebraic_variables.append(avr_feedback_y)
    algebraic_variables.append(avr_leadLag_x_1)
    algebraic_variables.append(avr_leadLag_y)
    algebraic_variables.append(avr_limitedFirstOrder_Gk_y)
    algebraic_variables.append(avr_limitedFirstOrder_feedback_y)
    algebraic_variables.append(avr_limitedFirstOrder_G_y)
    algebraic_variables.append(avr_limitedFirstOrder_I_u)
    algebraic_variables.append(avr_IrPu)
    algebraic_variables.append(avr_UOelPu)
    algebraic_variables.append(avr_UPssPu)
    algebraic_variables.append(avr_UUelPu)
    algebraic_variables.append(avr_UsPu)
    algebraic_variables.append(avr_UsRefPu)
    algebraic_variables.append(avr_limiter_simplifiedExpr)
    algebraic_variables.append(avr_limitedFirstOrder_lim_simplifiedExpr)
    algebraic_variables.append(avr_limitedFirstOrder_I_local_reset)
    algebraic_variables.append(avr_limitedFirstOrder_I_local_set)
    algebraic_variables.append(avr_integrator_local_reset)
    algebraic_variables.append(avr_integrator_local_set)
    algebraic_variables.append(START_avr_firstOrder_y)
    algebraic_variables.append(START_avr_leadLag_x_scaled_1)
    algebraic_variables.append(START_avr_derivative_x)
    differential_variables: list[Var] = list()
    differential_variables.append(d_avr_integrator_y)
    differential_variables.append(d_avr_derivative_x)
    differential_variables.append(d_avr_limitedFirstOrder_I_y)
    differential_variables.append(d_avr_leadLag_x_scaled_1)
    differential_variables.append(d_avr_firstOrder_y)
    input_variables: list[Var] = list()
    input_variables.append(avr_IrPu)
    input_variables.append(avr_UOelPu)
    input_variables.append(avr_UPssPu)
    input_variables.append(avr_UsPu)
    input_variables.append(avr_UsRefPu)
    input_variables.append(avr_UUelPu)
    output_variables: list[Var] = list()
    output_variables.append(avr_EfdPu)
    event_parameters: dict[Var, Expr | Const] = dict()
    event_parameters[avr_A1] = ((sym.Const(1.0) - sym.sqrt((avr_UHigh - (avr_ULow ** sym.Const(2.0))))) / avr_ULow)
    event_parameters[avr_A2] = sym.sqrt((avr_UHigh / (sym.Const(1.0) - avr_UHigh)))
    event_parameters[avr_Bsq] = ((sym.heaviside(((avr_VExcHighPu - avr_VExcThresholdPu) - sym.Const(1e-06))) * ((avr_VExcHighPu * avr_VExcSatHighPu) / ((avr_VExcHighPu - avr_VExcThresholdPu) ** sym.Const(2.0)))) + ((sym.Const(1.0) - sym.heaviside(((avr_VExcHighPu - avr_VExcThresholdPu) - sym.Const(1e-06)))) * sym.Const(0.0)))
    event_parameters[avr_Efd0Pu] = vf.add_const(1.0, name='')
    event_parameters[avr_Ir0Pu] = vf.add_const(1.0, name='')
    event_parameters[avr_Ka] = vf.add_const(200.0, name='')
    event_parameters[avr_Kc] = vf.add_const(0.0, name='')
    event_parameters[avr_Kd] = vf.add_const(0.0, name='')
    event_parameters[avr_Ke] = vf.add_const(1.0, name='')
    event_parameters[avr_Kf] = vf.add_const(0.05, name='')
    event_parameters[avr_Sq] = (((sym.heaviside(((avr_VExcHighPu - sym.Const(0.0)) - sym.Const(1e-06))) * sym.heaviside(((avr_VExcSatHighPu - sym.Const(0.0)) - sym.Const(1e-06)))) * sym.sqrt(((avr_VExcLowPu * avr_VExcSatLowPu) / (avr_VExcHighPu * avr_VExcSatHighPu)))) + ((sym.Const(1.0) - (sym.heaviside(((avr_VExcHighPu - sym.Const(0.0)) - sym.Const(1e-06))) * sym.heaviside(((avr_VExcSatHighPu - sym.Const(0.0)) - sym.Const(1e-06))))) * sym.Const(0.0)))
    event_parameters[avr_UHigh] = vf.add_const(0.75, name='')
    event_parameters[avr_ULow] = vf.add_const(0.433, name='')
    event_parameters[avr_Ua0] = (avr_Kc / (sym.Const(1.0) + (avr_A1 * avr_Kc)))
    event_parameters[avr_Ub0] = (avr_Kc * sym.sqrt((avr_UHigh / (sym.Const(1.0) + (avr_Kc ** sym.Const(2.0))))))
    event_parameters[avr_Uc0] = (avr_Kc * (avr_A2 / (sym.Const(1.0) + (avr_A2 * avr_Kc))))
    event_parameters[avr_Us0Pu] = vf.add_const(1.0, name='')
    event_parameters[avr_UsRef0Pu] = ((avr_Vr0Pu / avr_Ka) + avr_Us0Pu)
    event_parameters[avr_VExc0Pu] = (avr_Efd0Pu / avr_Y0)
    event_parameters[avr_VExcHighPu] = vf.add_const(3.1, name='')
    event_parameters[avr_VExcLowPu] = vf.add_const(2.3, name='')
    event_parameters[avr_VExcSatHighPu] = vf.add_const(0.33, name='')
    event_parameters[avr_VExcSatLowPu] = vf.add_const(0.1, name='')
    event_parameters[avr_VExcThresholdPu] = ((avr_VExcLowPu - (avr_VExcHighPu * avr_Sq)) / (sym.Const(1.0) - avr_Sq))
    event_parameters[avr_Vr0Pu] = (((sym.heaviside(((avr_VExc0Pu - avr_VExcThresholdPu) - sym.Const(1e-06))) * (avr_Bsq * ((avr_VExc0Pu - avr_VExcThresholdPu) ** sym.Const(2.0)))) + ((sym.Const(1.0) - sym.heaviside(((avr_VExc0Pu - avr_VExcThresholdPu) - sym.Const(1e-06)))) * sym.Const(0.0))) + ((avr_Ke * avr_VExc0Pu) + (avr_Kd * avr_Ir0Pu)))
    event_parameters[avr_VrMaxPu] = vf.add_const(5.0, name='')
    event_parameters[avr_VrMinPu] = vf.add_const(-5.0, name='')
    event_parameters[avr_Y0] = ((sym.heaviside(((sym.Const(0.0) - avr_Ua0) + sym.Const(1e-06))) * sym.Const(1.0)) + ((sym.Const(1.0) - sym.heaviside(((sym.Const(0.0) - avr_Ua0) + sym.Const(1e-06)))) * ((sym.heaviside(((avr_ULow - avr_Ua0) + sym.Const(1e-06))) * (sym.Const(1.0) - (avr_A1 * avr_Ua0))) + ((sym.Const(1.0) - sym.heaviside(((avr_ULow - avr_Ua0) + sym.Const(1e-06)))) * ((sym.heaviside(((avr_Uc0 - sym.Const(1.0)) + sym.Const(1e-06))) * sym.Const(0.0)) + ((sym.Const(1.0) - sym.heaviside(((avr_Uc0 - sym.Const(1.0)) + sym.Const(1e-06)))) * ((sym.heaviside(((avr_Uc0 - avr_UHigh) + sym.Const(1e-06))) * (avr_A2 * (sym.Const(1.0) - avr_Uc0))) + ((sym.Const(1.0) - sym.heaviside(((avr_Uc0 - avr_UHigh) + sym.Const(1e-06)))) * sym.sqrt((avr_UHigh - (avr_Ub0 ** sym.Const(2.0))))))))))))
    event_parameters[avr_add3_k1] = vf.add_const(1.0, name='')
    event_parameters[avr_add3_k2] = avr_Ke
    event_parameters[avr_add3_k3] = avr_Kd
    event_parameters[avr_const_k] = vf.add_const(1e-06, name='')
    event_parameters[avr_derivative_T] = avr_tF
    event_parameters[avr_derivative_k] = avr_Kf
    event_parameters[avr_derivative_x_start] = avr_Vr0Pu
    event_parameters[avr_derivative_y_start] = vf.add_const(0.0, name='')
    event_parameters[avr_firstOrder_T] = avr_tR
    event_parameters[avr_firstOrder_k] = vf.add_const(1.0, name='')
    event_parameters[avr_firstOrder_y_start] = avr_Us0Pu
    event_parameters[avr_gain1_k] = avr_Kc
    event_parameters[avr_integrator_k] = (sym.Const(1.0) / avr_tE)
    event_parameters[avr_integrator_y_start] = avr_VExc0Pu
    event_parameters[avr_leadLag_a_1] = avr_tB
    event_parameters[avr_leadLag_a_2] = vf.add_const(1.0, name='')
    event_parameters[avr_leadLag_a_end] = ((sym.heaviside(((avr_leadLag_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((avr_leadLag_a_1 ** sym.Const(2.0)) + (avr_leadLag_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06))) * avr_leadLag_a_2) + ((sym.Const(1.0) - sym.heaviside(((avr_leadLag_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((avr_leadLag_a_1 ** sym.Const(2.0)) + (avr_leadLag_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06)))) * sym.Const(1.0)))
    event_parameters[avr_leadLag_b_1] = avr_tC
    event_parameters[avr_leadLag_b_2] = vf.add_const(1.0, name='')
    event_parameters[avr_leadLag_bb_1] = avr_leadLag_b_1
    event_parameters[avr_leadLag_bb_2] = avr_leadLag_b_2
    event_parameters[avr_leadLag_d] = (avr_leadLag_bb_1 / avr_leadLag_a_1)
    event_parameters[avr_leadLag_x_start_1] = (avr_Vr0Pu / avr_Ka)
    event_parameters[avr_leadLag_y_start] = (avr_Vr0Pu / avr_Ka)
    event_parameters[avr_limitedFirstOrder_G_k] = (sym.Const(1.0) / avr_limitedFirstOrder_tFilter)
    event_parameters[avr_limitedFirstOrder_Gk_k] = avr_limitedFirstOrder_K
    event_parameters[avr_limitedFirstOrder_I_k] = vf.add_const(1.0, name='')
    event_parameters[avr_limitedFirstOrder_I_y_start] = avr_limitedFirstOrder_Y0
    event_parameters[avr_limitedFirstOrder_K] = avr_Ka
    event_parameters[avr_limitedFirstOrder_Y0] = avr_Vr0Pu
    event_parameters[avr_limitedFirstOrder_YMax] = avr_VrMaxPu
    event_parameters[avr_limitedFirstOrder_YMin] = avr_VrMinPu
    event_parameters[avr_limitedFirstOrder_lim_uMax] = avr_limitedFirstOrder_YMax
    event_parameters[avr_limitedFirstOrder_lim_uMin] = avr_limitedFirstOrder_YMin
    event_parameters[avr_limitedFirstOrder_tFilter] = avr_tA
    event_parameters[avr_limiter_uMax] = vf.add_const(999.0, name='')
    event_parameters[avr_limiter_uMin] = vf.add_const(0.0, name='')
    event_parameters[avr_rectifierRegulationCharacteristic_A1] = (((sym.heaviside(((avr_rectifierRegulationCharacteristic_ULow - sym.Const(0.0)) + sym.Const(1e-06))) * sym.heaviside(((sym.Const(0.0) - avr_rectifierRegulationCharacteristic_ULow) + sym.Const(1e-06)))) * sym.Const(0.0)) + ((sym.Const(1.0) - (sym.heaviside(((avr_rectifierRegulationCharacteristic_ULow - sym.Const(0.0)) + sym.Const(1e-06))) * sym.heaviside(((sym.Const(0.0) - avr_rectifierRegulationCharacteristic_ULow) + sym.Const(1e-06))))) * ((sym.Const(1.0) - sym.sqrt((avr_rectifierRegulationCharacteristic_UHigh - (avr_rectifierRegulationCharacteristic_ULow ** sym.Const(2.0))))) / avr_rectifierRegulationCharacteristic_ULow)))
    event_parameters[avr_rectifierRegulationCharacteristic_A2] = (((sym.heaviside(((avr_rectifierRegulationCharacteristic_UHigh - sym.Const(1.0)) + sym.Const(1e-06))) * sym.heaviside(((sym.Const(1.0) - avr_rectifierRegulationCharacteristic_UHigh) + sym.Const(1e-06)))) * sym.Const(0.0)) + ((sym.Const(1.0) - (sym.heaviside(((avr_rectifierRegulationCharacteristic_UHigh - sym.Const(1.0)) + sym.Const(1e-06))) * sym.heaviside(((sym.Const(1.0) - avr_rectifierRegulationCharacteristic_UHigh) + sym.Const(1e-06))))) * sym.sqrt((avr_rectifierRegulationCharacteristic_UHigh / (sym.Const(1.0) - avr_rectifierRegulationCharacteristic_UHigh)))))
    event_parameters[avr_rectifierRegulationCharacteristic_UHigh] = vf.add_const(0.75, name='')
    event_parameters[avr_rectifierRegulationCharacteristic_ULow] = vf.add_const(0.4330127018922193, name='')
    event_parameters[avr_satChar_Asq] = avr_VExcThresholdPu
    event_parameters[avr_satChar_Bsq] = avr_Bsq
    event_parameters[avr_satChar_Sq] = avr_Sq
    event_parameters[avr_satChar_UHigh] = avr_VExcHighPu
    event_parameters[avr_satChar_ULow] = avr_VExcLowPu
    event_parameters[avr_satChar_YHigh] = avr_VExcSatHighPu
    event_parameters[avr_satChar_YLow] = avr_VExcSatLowPu
    event_parameters[avr_sum1_k_1] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_k_2] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_k_3] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_k_4] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_k_5] = vf.add_const(-1.0, name='')
    event_parameters[avr_tA] = vf.add_const(0.02, name='')
    event_parameters[avr_tB] = vf.add_const(1.0, name='')
    event_parameters[avr_tC] = vf.add_const(1.0, name='')
    event_parameters[avr_tE] = vf.add_const(0.5, name='')
    event_parameters[avr_tF] = vf.add_const(1.0, name='')
    event_parameters[avr_tR] = vf.add_const(0.02, name='')
    event_parameters[avr_derivative_initType] = vf.add_const(1.0, name='')
    event_parameters[avr_firstOrder_initType] = vf.add_const(1.0, name='')
    event_parameters[avr_integrator_initType] = vf.add_const(3.0, name='')
    event_parameters[avr_leadLag_na] = vf.add_const(2.0, name='')
    event_parameters[avr_leadLag_nb] = vf.add_const(2.0, name='')
    event_parameters[avr_leadLag_nx] = vf.add_const(1.0, name='')
    event_parameters[avr_limitedFirstOrder_I_initType] = vf.add_const(3.0, name='')
    event_parameters[avr_limitedFirstOrder_lim_homotopyType] = vf.add_const(1.0, name='')
    event_parameters[avr_limiter_homotopyType] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_nin] = vf.add_const(5.0, name='')
    event_parameters[avr_derivative_zeroGain] = sym.heaviside(((sym.Const(2.220446049250313e-16) - sym.abs(avr_derivative_k)) - sym.Const(1e-06)))
    event_parameters[avr_integrator_use_reset] = vf.add_const(0.0, name='')
    event_parameters[avr_integrator_use_set] = vf.add_const(0.0, name='')
    event_parameters[avr_limitedFirstOrder_I_use_reset] = vf.add_const(0.0, name='')
    event_parameters[avr_limitedFirstOrder_I_use_set] = vf.add_const(0.0, name='')
    event_parameters[avr_limitedFirstOrder_lim_limitsAtInit] = vf.add_const(1.0, name='')
    event_parameters[avr_limitedFirstOrder_lim_strict] = vf.add_const(0.0, name='')
    event_parameters[avr_limiter_limitsAtInit] = vf.add_const(1.0, name='')
    event_parameters[avr_limiter_strict] = vf.add_const(0.0, name='')
    mode_parameters: dict[Var, Expr | Const] = dict()
    initial_equations: dict[Var, Expr | Const] = dict()
    initial_equations[avr_derivative_x] = avr_derivative_x_start
    initial_equations[avr_firstOrder_y] = (avr_firstOrder_k * avr_UsPu)
    initial_equations[avr_integrator_y] = avr_integrator_y_start
    initial_equations[avr_leadLag_x_scaled_1] = START_avr_leadLag_x_scaled_1
    initial_equations[avr_limitedFirstOrder_I_y] = avr_limitedFirstOrder_I_y_start
    initial_equations[avr_EfdPu] = vf.add_const(1.0, name='')
    initial_equations[avr_IrPu] = vf.add_const(1.0, name='')
    initial_equations[avr_UOelPu] = vf.add_const(0.0, name='')
    initial_equations[avr_UPssPu] = vf.add_const(0.0, name='')
    initial_equations[avr_UUelPu] = vf.add_const(0.0, name='')
    initial_equations[avr_UsPu] = vf.add_const(1.0, name='')
    initial_equations[avr_UsRefPu] = vf.add_const(1.0, name='')
    initial_equations[avr_leadLag_x_1] = avr_leadLag_x_start_1
    initial_equations[avr_leadLag_y] = avr_leadLag_y_start
    initial_equations[avr_limitedFirstOrder_y] = avr_limitedFirstOrder_Y0
    initial_equations[avr_limiter_simplifiedExpr] = vf.add_const(0.0, name='')
    initial_equations[avr_limitedFirstOrder_lim_simplifiedExpr] = vf.add_const(0.0, name='')
    initial_equations[avr_limitedFirstOrder_I_local_reset] = vf.add_const(0.0, name='')
    initial_equations[avr_limitedFirstOrder_I_local_set] = vf.add_const(0.0, name='')
    initial_equations[avr_integrator_local_reset] = vf.add_const(0.0, name='')
    initial_equations[avr_integrator_local_set] = vf.add_const(0.0, name='')
    initial_equations[avr_sum1_y] = (((((avr_sum1_k_1 * avr_UOelPu) + (avr_sum1_k_2 * avr_UPssPu)) + (avr_sum1_k_3 * avr_UUelPu)) + (avr_sum1_k_4 * avr_UsRefPu)) + (avr_sum1_k_5 * avr_firstOrder_y))
    differential_initial_equations: dict[Var, Expr | Const] = dict()
    procedural_logic_entries: list[object] = list()

    # Assemble the final block from the explicit typed collections above.
    template.block = Block(
        state_vars=state_variables,
        state_eqs=state_equations,
        algebraic_vars=algebraic_variables,
        algebraic_eqs=algebraic_equations,
        diff_vars=differential_variables,
        init_eqs=initial_equations,
        diff_init_eqs=differential_initial_equations,
        in_vars=input_variables,
        out_vars=output_variables,
        event_dict=event_parameters,
        mode_dict=mode_parameters,
        procedural_logic=procedural_logic_entries,
        name=template_name,
    )

    template.comment = 'Generator AVR/exciter EXAC1'
    return template
