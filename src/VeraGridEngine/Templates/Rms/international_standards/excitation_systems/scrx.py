# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Controlled-rectifier excitation with selectable supply and field discharge."""

from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp

def build_scrx_template(vf: VarFactory, name: str | None = None,
                        exciter_time: float = 0.5) -> RmsModelTemplate:
    """Build a controlled-rectifier excitation system with source selection.

    Voltage-reference error, stabilizing voltage and excitation-limiter signals
    pass through a lead-lag compensator and a bounded first-order regulator.
    Their two memory states describe phase compensation and regulator response;
    output limits act on the regulator before the supply-voltage multiplier.

    A bus-fed bridge scales its output with live terminal-voltage magnitude.
    An independently supplied bridge uses unity supply. This distinction must
    remain live during faults even when voltage sensing uses a compensator.

    A zero crowbar-to-field resistance ratio enables bidirectional field current.
    With a positive ratio, positive current uses the controlled bridge, while
    nonpositive current selects the reverse-discharge voltage minus the ratio
    times the air-gap field-current equivalent. This discharge path bypasses
    regulator voltage limits. Current is the field-current equivalent, not a
    stator d-axis current.

    The seven inputs are field current, overexcitation voltage, stabilizing
    voltage, voltage reference, sensed voltage, underexcitation voltage and
    terminal-voltage magnitude. The output is field voltage; all voltages and
    currents use compatible per-unit field/terminal bases and times use seconds.
    Initial regulator demand is obtained by dividing the required field voltage
    by the selected initial supply, then balancing the voltage reference.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param exciter_time: Nonnegative regulator lag in seconds; zero selects an
        algebraic bounded gain and removes its memory state exactly.
    :return: Native two-state component, or one-state component for zero lag.
    :raises ValueError: A negative or nonfinite regulator time.
    """
    if not math.isfinite(exciter_time) or exciter_time < 0:
        raise ValueError('Static-exciter regulator time must be finite and nonnegative')
    else:
        pass
    template_name: str
    if name is None:
        template_name: str = 'SCRX'
    else:
        template_name: str = name

    # Allocate the template container before building the symbolic surface.
    template: RmsModelTemplate = RmsModelTemplate()
    template.tpe = DeviceType.GeneratorDevice
    template.name = template_name

    # Declare every variable explicitly before the equations reference it.
    # Declare the runtime parameter variables used by the template.
    avr_CSwitch: Var = vf.add_var('avr.CSwitch_' + template_name)
    avr_Efd0Pu: Var = vf.add_var('avr.Efd0Pu_' + template_name)
    avr_IRotor0Pu: Var = vf.add_var('avr.IRotor0Pu_' + template_name)
    avr_K: Var = vf.add_var('avr.K_' + template_name)
    avr_RcToRfd: Var = vf.add_var('avr.RcToRfd_' + template_name)
    avr_URef0Pu: Var = vf.add_var('avr.URef0Pu_' + template_name)
    avr_UStator0Pu: Var = vf.add_var('avr.UStator0Pu_' + template_name)
    avr_Ut0Pu: Var = vf.add_var('avr.Ut0Pu_' + template_name)
    avr_Vr0Pu: Var = vf.add_var('avr.Vr0Pu_' + template_name)
    avr_VrMaxPu: Var = vf.add_var('avr.VrMaxPu_' + template_name)
    avr_VrMinPu: Var = vf.add_var('avr.VrMinPu_' + template_name)
    avr_booleanConstant_k: Var = vf.add_var('avr.booleanConstant.k_' + template_name)
    avr_gain_k: Var = vf.add_var('avr.gain.k_' + template_name)
    avr_lessEqualThreshold_threshold: Var = vf.add_var('avr.lessEqualThreshold.threshold_' + template_name)
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
    avr_sum1_k_1: Var = vf.add_var('avr.sum1.k[1]_' + template_name)
    avr_sum1_k_2: Var = vf.add_var('avr.sum1.k[2]_' + template_name)
    avr_sum1_k_3: Var = vf.add_var('avr.sum1.k[3]_' + template_name)
    avr_sum1_k_4: Var = vf.add_var('avr.sum1.k[4]_' + template_name)
    avr_sum1_k_5: Var = vf.add_var('avr.sum1.k[5]_' + template_name)
    avr_sum1_nin: Var = vf.add_var('avr.sum1.nin_' + template_name)
    avr_tA: Var = vf.add_var('avr.tA_' + template_name)
    avr_tB: Var = vf.add_var('avr.tB_' + template_name)
    avr_tE: Var = vf.add_var('avr.tE_' + template_name)
    avr_transferFunction_a_1: Var = vf.add_var('avr.transferFunction.a[1]_' + template_name)
    avr_transferFunction_a_2: Var = vf.add_var('avr.transferFunction.a[2]_' + template_name)
    avr_transferFunction_a_end: Var = vf.add_var('avr.transferFunction.a_end_' + template_name)
    avr_transferFunction_b_1: Var = vf.add_var('avr.transferFunction.b[1]_' + template_name)
    avr_transferFunction_b_2: Var = vf.add_var('avr.transferFunction.b[2]_' + template_name)
    avr_transferFunction_bb_1: Var = vf.add_var('avr.transferFunction.bb[1]_' + template_name)
    avr_transferFunction_bb_2: Var = vf.add_var('avr.transferFunction.bb[2]_' + template_name)
    avr_transferFunction_d: Var = vf.add_var('avr.transferFunction.d_' + template_name)
    avr_transferFunction_na: Var = vf.add_var('avr.transferFunction.na_' + template_name)
    avr_transferFunction_nb: Var = vf.add_var('avr.transferFunction.nb_' + template_name)
    avr_transferFunction_nx: Var = vf.add_var('avr.transferFunction.nx_' + template_name)
    avr_transferFunction_x_start_1: Var = vf.add_var('avr.transferFunction.x_start[1]_' + template_name)
    avr_transferFunction_y_start: Var = vf.add_var('avr.transferFunction.y_start_' + template_name)
    # Declare the state variables used by the template.
    avr_limitedFirstOrder_I_y: Var = vf.add_var('avr.limitedFirstOrder.I.y_' + template_name)
    avr_transferFunction_x_scaled_1: Var = vf.add_var('avr.transferFunction.x_scaled[1]_' + template_name)
    # Declare the algebraic/shared variables used by the template.
    START_avr_transferFunction_x_scaled_1: Var = vf.add_var('$START.avr.transferFunction.x_scaled[1]_' + template_name)
    avr_EfdPu: Var = vf.add_var('avr.EfdPu_' + template_name)
    avr_IRotorPu: Var = vf.add_var('avr.IRotorPu_' + template_name)
    avr_UOelPu: Var = vf.add_var('avr.UOelPu_' + template_name)
    avr_UPssPu: Var = vf.add_var('avr.UPssPu_' + template_name)
    avr_URefPu: Var = vf.add_var('avr.URefPu_' + template_name)
    avr_UStatorPu: Var = vf.add_var('avr.UStatorPu_' + template_name)
    avr_UUelPu: Var = vf.add_var('avr.UUelPu_' + template_name)
    avr_UtPu: Var = vf.add_var('avr.UtPu_' + template_name)
    avr_lessEqual_y: Var = vf.add_var('avr.lessEqual.y_' + template_name)
    avr_lessEqualThreshold_y: Var = vf.add_var('avr.lessEqualThreshold.y_' + template_name)
    avr_limitedFirstOrder_G_y: Var = vf.add_var('avr.limitedFirstOrder.G.y_' + template_name)
    avr_limitedFirstOrder_Gk_y: Var = vf.add_var('avr.limitedFirstOrder.Gk.y_' + template_name)
    avr_limitedFirstOrder_I_local_reset: Var = vf.add_var('avr.limitedFirstOrder.I.local_reset_' + template_name)
    avr_limitedFirstOrder_I_local_set: Var = vf.add_var('avr.limitedFirstOrder.I.local_set_' + template_name)
    avr_limitedFirstOrder_I_u: Var = vf.add_var('avr.limitedFirstOrder.I.u_' + template_name)
    avr_limitedFirstOrder_feedback_y: Var = vf.add_var('avr.limitedFirstOrder.feedback.y_' + template_name)
    avr_limitedFirstOrder_lim_simplifiedExpr: Var = vf.add_var('avr.limitedFirstOrder.lim.simplifiedExpr_' + template_name)
    avr_or1_y: Var = vf.add_var('avr.or1.y_' + template_name)
    avr_sum1_y: Var = vf.add_var('avr.sum1.y_' + template_name)
    avr_switch1_y: Var = vf.add_var('avr.switch1.y_' + template_name)
    avr_transferFunction_x_1: Var = vf.add_var('avr.transferFunction.x[1]_' + template_name)
    avr_transferFunction_y: Var = vf.add_var('avr.transferFunction.y_' + template_name)
    # Declare the differential variables used by the template.
    d_avr_limitedFirstOrder_I_y: Var = vf.add_diff_var('d_avr.limitedFirstOrder.I.y_' + template_name, base_var=avr_limitedFirstOrder_I_y)
    d_avr_transferFunction_x_scaled_1: Var = vf.add_diff_var('d_avr.transferFunction.x_scaled[1]_' + template_name, base_var=avr_transferFunction_x_scaled_1)

    # Build explicit typed collections so the symbolic surface is easy to inspect.
    state_equations: list[Expr] = list()
    state_equations.append((avr_limitedFirstOrder_I_k * avr_limitedFirstOrder_I_u))
    state_equations.append((((avr_transferFunction_a_end * avr_sum1_y) - (avr_transferFunction_a_2 * avr_transferFunction_x_scaled_1)) / avr_transferFunction_a_1))
    state_variables: list[Var] = list()
    state_variables.append(avr_limitedFirstOrder_I_y)
    state_variables.append(avr_transferFunction_x_scaled_1)
    algebraic_equations: list[Expr] = list()
    algebraic_equations.append((avr_switch1_y - ((sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06))) * avr_limitedFirstOrder_lim_uMax) + ((sym.Const(1.0) - sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06)))) * ((sym.heaviside(((avr_limitedFirstOrder_lim_uMin - avr_limitedFirstOrder_I_y) - sym.Const(1e-06))) * avr_limitedFirstOrder_lim_uMin) + ((sym.Const(1.0) - sym.heaviside(((avr_limitedFirstOrder_lim_uMin - avr_limitedFirstOrder_I_y) - sym.Const(1e-06)))) * avr_limitedFirstOrder_I_y))))))
    algebraic_equations.append((avr_lessEqual_y - sym.heaviside(((avr_switch1_y - avr_gain_k) + sym.Const(1e-06)))))
    algebraic_equations.append((avr_or1_y - (sym.Const(1.0) - ((sym.Const(1.0) - avr_lessEqual_y) * (sym.Const(1.0) - avr_lessEqualThreshold_y)))))
    algebraic_equations.append(avr_lessEqualThreshold_y
        -sym.heaviside(avr_lessEqualThreshold_threshold-avr_gain_k+sym.Const(1e-6)))
    # Keep terminal supply and reverse-current discharge live rather than
    # replacing either signal by its operating-point parameter alias.
    supply_voltage: Expr = avr_CSwitch + (sym.Const(1.0)-avr_CSwitch)*avr_UtPu
    bidirectional: Expr = sym.Const(1.0)-sym.heaviside(avr_RcToRfd)
    bridge_selected: Expr = bidirectional+(sym.Const(1.0)-bidirectional)*sym.heaviside(avr_IRotorPu)
    algebraic_equations.append(avr_EfdPu-(bridge_selected*supply_voltage*avr_switch1_y
        -(sym.Const(1.0)-bridge_selected)*avr_RcToRfd*avr_IRotorPu))
    algebraic_equations.append((avr_transferFunction_x_1 - (avr_transferFunction_x_scaled_1 / avr_transferFunction_a_end)))
    algebraic_equations.append((avr_transferFunction_y - (((avr_transferFunction_bb_2 - (avr_transferFunction_d * avr_transferFunction_a_2)) * avr_transferFunction_x_1) + (avr_transferFunction_d * avr_sum1_y))))
    algebraic_equations.append((avr_limitedFirstOrder_Gk_y - (avr_limitedFirstOrder_Gk_k * avr_transferFunction_y)))
    algebraic_equations.append((avr_limitedFirstOrder_feedback_y - (avr_limitedFirstOrder_Gk_y - avr_switch1_y)))
    algebraic_equations.append((avr_limitedFirstOrder_G_y - (avr_limitedFirstOrder_G_k * avr_limitedFirstOrder_feedback_y)))
    algebraic_equations.append((avr_limitedFirstOrder_I_u - (((sym.Const(1.0) - ((sym.Const(1.0) - ((sym.heaviside(((avr_limitedFirstOrder_G_y - sym.Const(0.0)) + sym.Const(1e-06))) * sym.heaviside(((avr_limitedFirstOrder_G_y - sym.Const(0.0)) + sym.Const(1e-06)))) * sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06))))) * (sym.Const(1.0) - ((((((sym.heaviside(((avr_limitedFirstOrder_G_y - sym.Const(0.0)) + sym.Const(1e-06))) * sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - avr_limitedFirstOrder_G_y) + sym.Const(1e-06)))) * sym.heaviside(((avr_limitedFirstOrder_G_y - sym.Const(0.0)) + sym.Const(1e-06)))) * sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - avr_limitedFirstOrder_G_y) + sym.Const(1e-06)))) * sym.heaviside(((avr_limitedFirstOrder_lim_uMin - avr_limitedFirstOrder_I_y) - sym.Const(1e-06))))))) * sym.Const(0.0)) + ((sym.Const(1.0) - (sym.Const(1.0) - ((sym.Const(1.0) - ((sym.heaviside(((avr_limitedFirstOrder_G_y - sym.Const(0.0)) + sym.Const(1e-06))) * sym.heaviside(((avr_limitedFirstOrder_G_y - sym.Const(0.0)) + sym.Const(1e-06)))) * sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06))))) * (sym.Const(1.0) - ((((((sym.heaviside(((avr_limitedFirstOrder_G_y - sym.Const(0.0)) + sym.Const(1e-06))) * sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - avr_limitedFirstOrder_G_y) + sym.Const(1e-06)))) * sym.heaviside(((avr_limitedFirstOrder_G_y - sym.Const(0.0)) + sym.Const(1e-06)))) * sym.heaviside(((avr_limitedFirstOrder_I_y - avr_limitedFirstOrder_lim_uMax) - sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - avr_limitedFirstOrder_G_y) + sym.Const(1e-06)))) * sym.heaviside(((avr_limitedFirstOrder_lim_uMin - avr_limitedFirstOrder_I_y) - sym.Const(1e-06)))))))) * avr_limitedFirstOrder_G_y))))
    algebraic_equations.append((avr_sum1_y - (((((avr_sum1_k_1 * avr_UOelPu) + (avr_sum1_k_2 * avr_UPssPu)) + (avr_sum1_k_3 * avr_URefPu)) + (avr_sum1_k_4 * avr_UUelPu)) + (avr_sum1_k_5 * avr_UStatorPu))))
    algebraic_variables: list[Var] = list()
    algebraic_variables.append(avr_switch1_y)
    algebraic_variables.append(avr_lessEqual_y)
    algebraic_variables.append(avr_or1_y)
    algebraic_variables.append(avr_EfdPu)
    algebraic_variables.append(avr_transferFunction_x_1)
    algebraic_variables.append(avr_transferFunction_y)
    algebraic_variables.append(avr_limitedFirstOrder_Gk_y)
    algebraic_variables.append(avr_limitedFirstOrder_feedback_y)
    algebraic_variables.append(avr_limitedFirstOrder_G_y)
    algebraic_variables.append(avr_limitedFirstOrder_I_u)
    algebraic_variables.append(avr_lessEqualThreshold_y)
    algebraic_variables.append(avr_sum1_y)
    algebraic_variables.append(avr_IRotorPu)
    algebraic_variables.append(avr_UOelPu)
    algebraic_variables.append(avr_UPssPu)
    algebraic_variables.append(avr_URefPu)
    algebraic_variables.append(avr_UStatorPu)
    algebraic_variables.append(avr_UUelPu)
    algebraic_variables.append(avr_UtPu)
    algebraic_variables.append(avr_limitedFirstOrder_lim_simplifiedExpr)
    algebraic_variables.append(avr_limitedFirstOrder_I_local_reset)
    algebraic_variables.append(avr_limitedFirstOrder_I_local_set)
    algebraic_variables.append(START_avr_transferFunction_x_scaled_1)
    differential_variables: list[Var] = list()
    differential_variables.append(d_avr_limitedFirstOrder_I_y)
    differential_variables.append(d_avr_transferFunction_x_scaled_1)
    input_variables: list[Var] = list()
    input_variables.append(avr_IRotorPu)
    input_variables.append(avr_UOelPu)
    input_variables.append(avr_UPssPu)
    input_variables.append(avr_URefPu)
    input_variables.append(avr_UStatorPu)
    input_variables.append(avr_UUelPu)
    input_variables.append(avr_UtPu)
    output_variables: list[Var] = list()
    output_variables.append(avr_EfdPu)
    event_parameters: dict[Var, Expr | Const] = dict()
    event_parameters[avr_Efd0Pu] = vf.add_const(1.0, name='')
    event_parameters[avr_IRotor0Pu] = vf.add_const(1.0, name='')
    event_parameters[avr_K] = vf.add_const(100.0, name='')
    event_parameters[avr_RcToRfd] = vf.add_const(0.0, name='')
    event_parameters[avr_URef0Pu] = (avr_UStator0Pu + (avr_Vr0Pu / avr_K))
    event_parameters[avr_UStator0Pu] = vf.add_const(1.0, name='')
    event_parameters[avr_Ut0Pu] = vf.add_const(1.0, name='')
    event_parameters[avr_Vr0Pu] = ((avr_CSwitch * avr_Efd0Pu) + ((sym.Const(1.0) - avr_CSwitch) * (avr_Efd0Pu / avr_Ut0Pu)))
    event_parameters[avr_VrMaxPu] = vf.add_const(5.0, name='')
    event_parameters[avr_VrMinPu] = vf.add_const(-5.0, name='')
    event_parameters[avr_gain_k] = (-avr_RcToRfd)
    event_parameters[avr_lessEqualThreshold_threshold] = vf.add_const(0.0, name='')
    event_parameters[avr_limitedFirstOrder_G_k] = (sym.Const(1.0) / avr_limitedFirstOrder_tFilter)
    event_parameters[avr_limitedFirstOrder_Gk_k] = avr_limitedFirstOrder_K
    event_parameters[avr_limitedFirstOrder_I_k] = vf.add_const(1.0, name='')
    event_parameters[avr_limitedFirstOrder_I_y_start] = avr_limitedFirstOrder_Y0
    event_parameters[avr_limitedFirstOrder_K] = avr_K
    event_parameters[avr_limitedFirstOrder_Y0] = avr_Vr0Pu
    event_parameters[avr_limitedFirstOrder_YMax] = avr_VrMaxPu
    event_parameters[avr_limitedFirstOrder_YMin] = avr_VrMinPu
    event_parameters[avr_limitedFirstOrder_lim_uMax] = avr_limitedFirstOrder_YMax
    event_parameters[avr_limitedFirstOrder_lim_uMin] = avr_limitedFirstOrder_YMin
    event_parameters[avr_limitedFirstOrder_tFilter] = avr_tE
    event_parameters[avr_sum1_k_1] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_k_2] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_k_3] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_k_4] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_k_5] = vf.add_const(-1.0, name='')
    event_parameters[avr_tA] = vf.add_const(0.02, name='')
    event_parameters[avr_tB] = vf.add_const(0.1, name='')
    event_parameters[avr_tE] = vf.add_const(exciter_time, name='')
    event_parameters[avr_transferFunction_a_1] = avr_tB
    event_parameters[avr_transferFunction_a_2] = vf.add_const(1.0, name='')
    event_parameters[avr_transferFunction_a_end] = ((sym.heaviside(((avr_transferFunction_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((avr_transferFunction_a_1 ** sym.Const(2.0)) + (avr_transferFunction_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06))) * avr_transferFunction_a_2) + ((sym.Const(1.0) - sym.heaviside(((avr_transferFunction_a_2 - (sym.Const(2.220446049250313e-14) * sym.sqrt(((avr_transferFunction_a_1 ** sym.Const(2.0)) + (avr_transferFunction_a_2 ** sym.Const(2.0)))))) - sym.Const(1e-06)))) * sym.Const(1.0)))
    event_parameters[avr_transferFunction_b_1] = avr_tA
    event_parameters[avr_transferFunction_b_2] = vf.add_const(1.0, name='')
    event_parameters[avr_transferFunction_bb_1] = avr_transferFunction_b_1
    event_parameters[avr_transferFunction_bb_2] = avr_transferFunction_b_2
    event_parameters[avr_transferFunction_d] = (avr_transferFunction_bb_1 / avr_transferFunction_a_1)
    event_parameters[avr_transferFunction_x_start_1] = (avr_Vr0Pu / avr_K)
    event_parameters[avr_transferFunction_y_start] = (avr_Vr0Pu / avr_K)
    event_parameters[avr_limitedFirstOrder_I_initType] = vf.add_const(3.0, name='')
    event_parameters[avr_limitedFirstOrder_lim_homotopyType] = vf.add_const(1.0, name='')
    event_parameters[avr_sum1_nin] = vf.add_const(5.0, name='')
    event_parameters[avr_transferFunction_na] = vf.add_const(2.0, name='')
    event_parameters[avr_transferFunction_nb] = vf.add_const(2.0, name='')
    event_parameters[avr_transferFunction_nx] = vf.add_const(1.0, name='')
    event_parameters[avr_CSwitch] = vf.add_const(0.0, name='')
    event_parameters[avr_booleanConstant_k] = avr_CSwitch
    event_parameters[avr_limitedFirstOrder_I_use_reset] = vf.add_const(0.0, name='')
    event_parameters[avr_limitedFirstOrder_I_use_set] = vf.add_const(0.0, name='')
    event_parameters[avr_limitedFirstOrder_lim_limitsAtInit] = vf.add_const(1.0, name='')
    event_parameters[avr_limitedFirstOrder_lim_strict] = vf.add_const(0.0, name='')
    mode_parameters: dict[Var, Expr | Const] = dict()
    initial_equations: dict[Var, Expr | Const] = dict()
    initial_equations[avr_limitedFirstOrder_I_y] = avr_limitedFirstOrder_I_y_start
    initial_equations[avr_transferFunction_x_scaled_1] = (avr_transferFunction_a_end * avr_transferFunction_x_start_1)
    initial_equations[avr_EfdPu] = vf.add_const(1.0, name='')
    initial_equations[avr_IRotorPu] = avr_IRotor0Pu
    initial_equations[avr_UOelPu] = vf.add_const(0.0, name='')
    initial_equations[avr_UPssPu] = vf.add_const(0.0, name='')
    initial_equations[avr_URefPu] = avr_URef0Pu
    initial_equations[avr_UStatorPu] = avr_UStator0Pu
    initial_equations[avr_UUelPu] = vf.add_const(0.0, name='')
    initial_equations[avr_UtPu] = avr_Ut0Pu
    initial_equations[avr_switch1_y] = avr_limitedFirstOrder_Y0
    initial_equations[avr_transferFunction_x_1] = avr_transferFunction_x_start_1
    initial_equations[avr_transferFunction_y] = avr_transferFunction_y_start
    initial_equations[avr_limitedFirstOrder_lim_simplifiedExpr] = vf.add_const(0.0, name='')
    initial_equations[avr_limitedFirstOrder_I_local_reset] = vf.add_const(0.0, name='')
    initial_equations[avr_limitedFirstOrder_I_local_set] = vf.add_const(0.0, name='')
    initial_equations[avr_lessEqualThreshold_y] = sym.heaviside(((avr_lessEqualThreshold_threshold - avr_gain_k) + sym.Const(1e-06)))
    initial_equations[avr_sum1_y] = (((((avr_sum1_k_1 * avr_UOelPu) + (avr_sum1_k_2 * avr_UPssPu)) + (avr_sum1_k_3 * avr_URefPu)) + (avr_sum1_k_4 * avr_UUelPu)) + (avr_sum1_k_5 * avr_UStatorPu))
    differential_initial_equations: dict[Var, Expr | Const] = dict()
    procedural_logic_entries: list[object] = list()

    # An instantaneous regulator has a bounded algebraic command, with no
    # dormant inverse-time alias that could divide by zero during initialization.
    if exciter_time == 0:
        state_variables.pop(0)
        state_equations.pop(0)
        differential_variables.pop(0)
        algebraic_variables.append(avr_limitedFirstOrder_I_y)
        algebraic_equations.append(avr_limitedFirstOrder_I_y-sym.hard_sat(
            avr_K*avr_transferFunction_y,avr_VrMinPu,avr_VrMaxPu))
        event_parameters[avr_limitedFirstOrder_G_k] = vf.add_const(0.0)
    else:
        pass

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

    template.comment = 'Generator AVR/exciter SCRX'
    return template
