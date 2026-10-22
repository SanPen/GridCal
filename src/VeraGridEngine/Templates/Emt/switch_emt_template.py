# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict, List

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.procedural_logic import bool_and, bool_or, flipflop, sampled_value
from VeraGridEngine.Utils.Symbolic.symbolic import abs as symbolic_abs
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp, Comparison, Const, Expr, Var


def _get_active_phases(phA: bool, phB: bool, phC: bool) -> List[str]:
    """
    Return the enabled phase labels in strict A-B-C order.

    :param phA: True when phase A is active.
    :param phB: True when phase B is active.
    :param phC: True when phase C is active.
    :return: Ordered list with the active phase labels.
    """
    active_phases: List[str] = list()

    if phA:
        active_phases.append("A")
    else:
        pass

    if phB:
        active_phases.append("B")
    else:
        pass

    if phC:
        active_phases.append("C")
    else:
        pass

    if len(active_phases) == 0:
        raise ValueError("At least one phase must be enabled for an EMT switch template")
    else:
        return active_phases


def _get_from_voltage_reference(phase_label: str) -> VarPowerFlowReferenceType:
    if phase_label == "A":
        return VarPowerFlowReferenceType.vf_A
    else:
        if phase_label == "B":
            return VarPowerFlowReferenceType.vf_B
        else:
            if phase_label == "C":
                return VarPowerFlowReferenceType.vf_C
            else:
                raise ValueError(f"Unsupported phase label '{phase_label}'")


def _get_to_voltage_reference(phase_label: str) -> VarPowerFlowReferenceType:
    if phase_label == "A":
        return VarPowerFlowReferenceType.vt_A
    else:
        if phase_label == "B":
            return VarPowerFlowReferenceType.vt_B
        else:
            if phase_label == "C":
                return VarPowerFlowReferenceType.vt_C
            else:
                raise ValueError(f"Unsupported phase label '{phase_label}'")


def _get_from_current_reference(phase_label: str) -> VarPowerFlowReferenceType:
    if phase_label == "A":
        return VarPowerFlowReferenceType.if_A
    else:
        if phase_label == "B":
            return VarPowerFlowReferenceType.if_B
        else:
            if phase_label == "C":
                return VarPowerFlowReferenceType.if_C
            else:
                raise ValueError(f"Unsupported phase label '{phase_label}'")


def _get_to_current_reference(phase_label: str) -> VarPowerFlowReferenceType:
    if phase_label == "A":
        return VarPowerFlowReferenceType.it_A
    else:
        if phase_label == "B":
            return VarPowerFlowReferenceType.it_B
        else:
            if phase_label == "C":
                return VarPowerFlowReferenceType.it_C
            else:
                raise ValueError(f"Unsupported phase label '{phase_label}'")


class SwitchEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phA", units="", descr="Enable phase A.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Enable phase B.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Enable phase C.", tpe=bool, value=True),
                TemplateProp(name="signal_controlled", units="", descr="If True, expose one control input and procedural logic.", tpe=bool, value=False),
                TemplateProp(name="seed_from_pf_active", units="", descr="If True, seed the closed/open mode from Switch.active.", tpe=bool, value=True),
                TemplateProp(name="initial_closed", units="", descr="Default closed state when PF seeding is disabled.", tpe=bool, value=True),
                TemplateProp(name="use_device_conductance", units="", descr="If True, use the switch static R/X to derive the closed conductance.", tpe=bool, value=True),
                TemplateProp(name="manual_closed_conductance", units="S", descr="Manual closed conductance fallback.", tpe=float, value=1.0e4),
                TemplateProp(name="open_conductance", units="S", descr="Open-state leakage conductance.", tpe=float, value=1.0e-8),
                TemplateProp(name="switch_time_constant", units="s", descr="First-order current time constant.", tpe=float, value=1.0e-4),
                TemplateProp(name="command_threshold", units="", descr="Control threshold for the external command.", tpe=float, value=0.5),
                TemplateProp(name="algebraic_branch", units="", descr="Use an instantaneous resistive branch without artificial current dynamics.", tpe=bool, value=False),
                TemplateProp(name="closed_parallel_conductance", units="S", descr="Parallel snubber conductance present while the switch is closed.", tpe=float, value=0.0),
                TemplateProp(name="zero_current_opening", units="", descr="Open each phase at its first sampled current zero after an open command.", tpe=bool, value=False),
                TemplateProp(name="zero_current_threshold", units="p.u.", descr="Current magnitude accepted as a sampled zero for phase opening.", tpe=float, value=1.0e-3),
                TemplateProp(name="name", units="", descr="Symbolic model name.", tpe=str, value="switch_emt_template"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        signal_controlled: bool = self.get_value("signal_controlled")
        seed_from_pf_active: bool = self.get_value("seed_from_pf_active")
        initial_closed: bool = self.get_value("initial_closed")
        use_device_conductance: bool = self.get_value("use_device_conductance")
        manual_closed_conductance: float = self.get_value("manual_closed_conductance")
        open_conductance: float = self.get_value("open_conductance")
        switch_time_constant: float = self.get_value("switch_time_constant")
        command_threshold: float = self.get_value("command_threshold")
        algebraic_branch: bool = self.get_value("algebraic_branch")
        closed_parallel_conductance: float = self.get_value("closed_parallel_conductance")
        zero_current_opening: bool = self.get_value("zero_current_opening")
        zero_current_threshold: float = self.get_value("zero_current_threshold")
        name: str = self.get_value("name")

        return get_switch_emt_template(
            vf=self.vf,
            phA=phA,
            phB=phB,
            phC=phC,
            signal_controlled=signal_controlled,
            seed_from_pf_active=seed_from_pf_active,
            initial_closed=initial_closed,
            use_device_conductance=use_device_conductance,
            manual_closed_conductance=manual_closed_conductance,
            open_conductance=open_conductance,
            switch_time_constant=switch_time_constant,
            command_threshold=command_threshold,
            name=name,
            algebraic_branch=algebraic_branch,
            closed_parallel_conductance=closed_parallel_conductance,
            zero_current_opening=zero_current_opening,
            zero_current_threshold=zero_current_threshold,
        )


def get_switch_emt_template(
    vf: VarFactory,
    phA: bool = True,
    phB: bool = True,
    phC: bool = True,
    signal_controlled: bool = False,
    seed_from_pf_active: bool = True,
    initial_closed: bool = True,
    use_device_conductance: bool = True,
    manual_closed_conductance: float = 1.0e4,
    open_conductance: float = 1.0e-8,
    switch_time_constant: float = 1.0e-4,
    command_threshold: float = 0.5,
    name: str = "switch_emt_template",
    algebraic_branch: bool = False,
    closed_parallel_conductance: float = 0.0,
    zero_current_opening: bool = False,
    zero_current_threshold: float = 1.0e-3,
) -> EmtModelTemplate:
    """
    Build one phase-selective EMT switch branch template.

    :param vf: EMT variable factory.
    :param phA: Enable phase A.
    :param phB: Enable phase B.
    :param phC: Enable phase C.
    :param signal_controlled: If True, expose one control input and procedural logic.
    :param seed_from_pf_active: If True, seed the closed/open mode from `Switch.active`.
    :param initial_closed: Default closed state when PF seeding is disabled.
    :param use_device_conductance: If True, use the switch static `R/X` to derive the closed conductance.
    :param manual_closed_conductance: Manual closed conductance fallback.
    :param open_conductance: Open-state leakage conductance.
    :param switch_time_constant: First-order current time constant.
    :param command_threshold: Control threshold for the external command.
    :param name: Symbolic model name.
    :param algebraic_branch: If True, reproduce an instantaneous resistive breaker instead of adding a current lag.
    :param closed_parallel_conductance: Parallel snubber conductance also present in the closed state.
    :param zero_current_opening: If True, defer each phase opening until its current crosses zero.
    :param zero_current_threshold: Per-unit current magnitude treated as zero at a sampled boundary.
    :return: EMT switch template.
    """
    active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.SwitchDevice
    templ.name = name
    templ.block.name = name

    closed_mode: Var = vf.add_var("switch_closed_mode", reference=VarPowerFlowReferenceType.switch_closed_mode)
    templ.block.mode_dict[closed_mode] = Const(1.0 if initial_closed else 0.0, name="switch_closed_mode")

    g_device: Var = vf.add_var(f"switch_closed_g_api")
    g_manual: Var = vf.add_var(f"switch_closed_g_manual")
    g_open: Var = vf.add_var(f"switch_open_g")
    tau_var: Var = vf.add_var(f"switch_tau")
    g_parallel: Var = vf.add_var(f"switch_closed_parallel_g")
    seed_from_pf_var: Var = vf.add_var("switch_seed_from_pf", reference=VarPowerFlowReferenceType.switch_seed_from_pf)

    templ.block.parameters[g_device] = Const(0.0, name="switch_closed_g_api")
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.g] = g_device
    templ.block.event_dict[g_manual] = Const(float(manual_closed_conductance), name="switch_closed_g_manual")
    templ.block.event_dict[g_open] = Const(float(open_conductance), name="switch_open_g")
    templ.block.event_dict[tau_var] = Const(float(switch_time_constant), name="switch_tau")
    templ.block.event_dict[g_parallel] = Const(
        float(closed_parallel_conductance),
        name="switch_closed_parallel_g",
    )
    templ.block.event_dict[seed_from_pf_var] = Const(1.0 if seed_from_pf_active else 0.0, name="switch_seed_from_pf")
    if zero_current_opening:
        zero_current_threshold_var: Var = vf.add_var(f"switch_zero_current_threshold")
        templ.block.event_dict[zero_current_threshold_var] = Const(
            float(zero_current_threshold),
            name="switch_zero_current_threshold",
        )
    else:
        pass

    g_closed_eff: Expr = (
        seed_from_pf_var * g_device
        + (Const(1.0) - seed_from_pf_var) * g_manual
        + g_parallel
    )
    in_vars: List[Var] = list()
    state_vars: List[Var] = list()
    diff_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    state_eqs: List[Expr] = list()
    out_vars: List[Var] = list()
    external_mapping: Dict[VarPowerFlowReferenceType, Var | None] = dict({
        VarPowerFlowReferenceType.switch_closed_mode: closed_mode,
        VarPowerFlowReferenceType.switch_seed_from_pf: seed_from_pf_var,
        VarPowerFlowReferenceType.vf_N: None,
        VarPowerFlowReferenceType.vf_A: None,
        VarPowerFlowReferenceType.vf_B: None,
        VarPowerFlowReferenceType.vf_C: None,
        VarPowerFlowReferenceType.vt_N: None,
        VarPowerFlowReferenceType.vt_A: None,
        VarPowerFlowReferenceType.vt_B: None,
        VarPowerFlowReferenceType.vt_C: None,
        VarPowerFlowReferenceType.if_N: None,
        VarPowerFlowReferenceType.if_A: None,
        VarPowerFlowReferenceType.if_B: None,
        VarPowerFlowReferenceType.if_C: None,
        VarPowerFlowReferenceType.it_N: None,
        VarPowerFlowReferenceType.it_A: None,
        VarPowerFlowReferenceType.it_B: None,
        VarPowerFlowReferenceType.it_C: None,
        VarPowerFlowReferenceType.Sf_A: None,
        VarPowerFlowReferenceType.Sf_B: None,
        VarPowerFlowReferenceType.Sf_C: None,
        VarPowerFlowReferenceType.St_A: None,
        VarPowerFlowReferenceType.St_B: None,
        VarPowerFlowReferenceType.St_C: None,
        VarPowerFlowReferenceType.d_v_N_f: None,
        VarPowerFlowReferenceType.d_v_A_f: None,
        VarPowerFlowReferenceType.d_v_B_f: None,
        VarPowerFlowReferenceType.d_v_C_f: None,
        VarPowerFlowReferenceType.d_v_N_t: None,
        VarPowerFlowReferenceType.d_v_A_t: None,
        VarPowerFlowReferenceType.d_v_B_t: None,
        VarPowerFlowReferenceType.d_v_C_t: None,
    })

    if signal_controlled:
        command_input = vf.add_var(f"switch_cmd")
        threshold_var = vf.add_var(f"switch_cmd_threshold")
        templ.block.event_dict[threshold_var] = Const(float(command_threshold), name="switch_cmd_threshold")
        templ.block.procedural_logic.append(
            sampled_value(output=closed_mode, source=Comparison(lhs=command_input, op=CmpOp.GE, rhs=threshold_var))
        )
        in_vars.append(command_input)
    else:
        pass

    phase_label: str
    for phase_label in active_phases:
        v_from: Var = vf.add_var(f"vf_{phase_label}", reference=_get_from_voltage_reference(phase_label))
        v_to: Var = vf.add_var(f"vt_{phase_label}", reference=_get_to_voltage_reference(phase_label))
        i_from: Var = vf.add_var(f"if_{phase_label}", reference=_get_from_current_reference(phase_label))
        i_to: Var = vf.add_var(f"it_{phase_label}", reference=_get_to_current_reference(phase_label))

        in_vars.extend(list([v_from, v_to]))
        algebraic_vars.extend(list([i_from, i_to]))

        # Simulink's discrete three-phase breaker retains each conducting phase
        # after the open command until that phase current reaches its next zero.
        # Detect both an exact/small sampled current and a sign change between
        # accepted samples so a zero cannot be skipped by the fixed 10 us grid.
        if zero_current_opening:
            # The procedural latch resolves its output by symbolic name in the
            # complete block tree. Include the device name so several breakers
            # can use zero-current opening without producing ambiguous names.
            phase_closed_mode_name: str = f"switch_phase_{phase_label}_closed_mode_{name}"
            previous_current_name: str = f"switch_phase_{phase_label}_previous_current_{name}"
            phase_closed_mode: Var = vf.add_var(phase_closed_mode_name)
            previous_current: Var = vf.add_var(previous_current_name)
            templ.block.mode_dict[phase_closed_mode] = Const(
                1.0 if initial_closed else 0.0,
                name=phase_closed_mode_name,
            )
            templ.block.mode_dict[previous_current] = Const(
                0.0,
                name=previous_current_name,
            )
            command_closed: Comparison = Comparison(
                lhs=closed_mode,
                op=CmpOp.GE,
                rhs=Const(float(command_threshold)),
            )
            command_open: Comparison = Comparison(
                lhs=closed_mode,
                op=CmpOp.LT,
                rhs=Const(float(command_threshold)),
            )
            sampled_zero: Comparison = Comparison(
                lhs=symbolic_abs(i_from),
                op=CmpOp.LE,
                rhs=zero_current_threshold_var,
            )
            crossed_zero: Comparison = Comparison(
                lhs=i_from * previous_current,
                op=CmpOp.LE,
                rhs=Const(0.0),
            )
            open_at_current_zero: Expr = bool_and(
                command_open,
                bool_or(sampled_zero, crossed_zero),
            )
            templ.block.procedural_logic.append(
                flipflop(
                    boolset=command_closed,
                    boolreset=open_at_current_zero,
                    output=phase_closed_mode,
                    name=f"switch_phase_{phase_label}_zero_current_opening_{name}",
                )
            )
            # This sampler follows the latch in the procedural list, so the
            # latch compares the accepted current with the preceding sample.
            templ.block.procedural_logic.append(
                sampled_value(
                    output=previous_current,
                    source=i_from,
                    name=f"switch_phase_{phase_label}_current_memory_{name}",
                )
            )
            # A close command acts without delay. Only opening is deferred to
            # the retained phase latch, matching the breaker command semantics.
            phase_conduction_mode: Expr = bool_or(command_closed, phase_closed_mode)
        else:
            phase_conduction_mode = closed_mode
        g_eff: Expr = (
            phase_conduction_mode * g_closed_eff
            + (Const(1.0) - phase_conduction_mode) * g_open
        )
        if algebraic_branch:
            algebraic_eqs.append(i_from - g_eff * (v_from - v_to))
            algebraic_eqs.append(i_to + i_from)
        else:
            i_state: Var = vf.add_var(f"i_{phase_label}")
            di_state: Var = vf.add_diff_var(name=f"di_{phase_label}", base_var=i_state)
            state_vars.append(i_state)
            diff_vars.append(di_state)
            state_eqs.append((g_eff * (v_from - v_to) - i_state) / tau_var)
            algebraic_eqs.append(i_from - i_state)
            algebraic_eqs.append(i_to + i_state)
        out_vars.extend(list([i_from, i_to]))
        external_mapping[_get_from_voltage_reference(phase_label)] = v_from
        external_mapping[_get_to_voltage_reference(phase_label)] = v_to
        external_mapping[_get_from_current_reference(phase_label)] = i_from
        external_mapping[_get_to_current_reference(phase_label)] = i_to

    init_eqs: Dict[Var, Expr | Const] = dict()
    diff_init_eqs: Dict[Var, Expr | Const] = dict()
    state_var: Var
    state_eq: Expr

    for state_var in state_vars:
        init_eqs[state_var] = Const(0.0)

    for di_var, state_eq in zip(diff_vars, state_eqs):
        diff_init_eqs[di_var] = state_eq

    templ.block.in_vars = in_vars
    templ.block.state_vars = state_vars
    templ.block.diff_vars = diff_vars
    templ.block.algebraic_vars = algebraic_vars
    templ.block.state_eqs = state_eqs
    templ.block.algebraic_eqs = algebraic_eqs
    templ.block.out_vars = out_vars
    templ.block.external_mapping = external_mapping
    templ.block.init_eqs = init_eqs
    templ.block.diff_init_eqs = diff_init_eqs
    return templ
