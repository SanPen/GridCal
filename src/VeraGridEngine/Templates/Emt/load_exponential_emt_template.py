# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Phase-selective EMT exponential-load template."""

from typing import Dict, List, Tuple

import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import (
    _get_active_phases,
    _get_delta_branch_specs,
    _get_phase_count_name,
    wrap_delta_referenced_load_emt_template,
    wrap_ground_referenced_load_emt_template,
)
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.Symbolic.block import Expr, Var
from VeraGridEngine.Utils.Symbolic.symbolic import abs as symbolic_abs
from VeraGridEngine.Utils.Symbolic.symbolic import exp as symbolic_exp
from VeraGridEngine.Utils.Symbolic.symbolic import log as symbolic_log
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, ShuntConnectionType, VarPowerFlowReferenceType

def _get_current_reference(phase_label: str) -> VarPowerFlowReferenceType:
    """Return the EMT injected-current reference enum for one phase.

    :param phase_label: Phase label ``A``, ``B`` or ``C``.
    :return: Matching external current reference enum.
    """
    if phase_label == "A":
        reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType.i_A
    elif phase_label == "B":
        reference = VarPowerFlowReferenceType.i_B
    elif phase_label == "C":
        reference = VarPowerFlowReferenceType.i_C
    else:
        raise ValueError(f"Unsupported phase label '{phase_label}.'")

    return reference

class ExponentialLoadEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(vf, params=[
            TemplateProp(name="phA", units="", descr="True when phase A is active.", tpe=bool),
            TemplateProp(name="phB", units="", descr="True when phase B is active.", tpe=bool),
            TemplateProp(name="phC", units="", descr="True when phase C is active.", tpe=bool),
            TemplateProp(name="connection_type", units="", descr="Optional explicit star connection topology.", tpe=ShuntConnectionType | None),
            TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str),
        ])

    def eval(self) -> EmtModelTemplate:
        return get_exponential_load_emt(
            self.vf,
            self.get_value("phA"),
            self.get_value("phB"),
            self.get_value("phC"),
            self.get_value("connection_type"),
            self.get_value("name"),
        )


def _get_voltage_reference(phase_label: str) -> VarPowerFlowReferenceType:
    """Return the EMT voltage enum for one active phase.

    :param phase_label: Phase label in ``A``, ``B`` or ``C``.
    :return: Matching voltage reference enum.
    """
    if phase_label == "A":
        reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType.v_A
    else:
        if phase_label == "B":
            reference = VarPowerFlowReferenceType.v_B
        else:
            if phase_label == "C":
                reference = VarPowerFlowReferenceType.v_C
            else:
                raise ValueError(f"Unsupported phase label '{phase_label}'")

    return reference


def _get_api_power_references(phase_label: str) -> Tuple[ParamPowerFlowReferenceType, ParamPowerFlowReferenceType]:
    """Return the API active/reactive power enums for one active phase.

    :param phase_label: Phase label in ``A``, ``B`` or ``C``.
    :return: Tuple with API active-power and reactive-power reference enums.
    """
    if phase_label == "A":
        p_reference: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Pl0_A
        q_reference: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Ql0_A
    else:
        if phase_label == "B":
            p_reference = ParamPowerFlowReferenceType.Pl0_B
            q_reference = ParamPowerFlowReferenceType.Ql0_B
        else:
            if phase_label == "C":
                p_reference = ParamPowerFlowReferenceType.Pl0_C
                q_reference = ParamPowerFlowReferenceType.Ql0_C
            else:
                raise ValueError(f"Unsupported phase label '{phase_label}'")

    return p_reference, q_reference


# ---
class ExponentialLoadEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="connection_type", units="", descr="Star connection topology.", tpe=ShuntConnectionType, value=None),
                TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str, value="EXP_Load_EMT_3ph"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        connection_type: ShuntConnectionType | None = self.get_value("connection_type")
        name: str = self.get_value("name")

        return get_exponential_load_emt(
            self.vf, phA, phB, phC, connection_type, name
        )


def get_exponential_load_emt(
    vf: VarFactory,
    phA: bool = True,
    phB: bool = True,
    phC: bool = True,
    connection_type: ShuntConnectionType | None = None,
    name: str = "EXP_Load_EMT_3ph",
) -> EmtModelTemplate:
    """Build the phase-selective EMT exponential-load template.

    The load keeps the original per-phase SOGI state model and exponential
    voltage dependence, but instantiates those equations only for the phases
    enabled by ``phA``, ``phB`` and ``phC``.

    :param vf: EMT variable factory.
    :param phA: True when phase A is active.
    :param phB: True when phase B is active.
    :param phC: True when phase C is active.
    :param connection_type: Optional explicit star connection topology.
    :param name: Symbolic block name.
    :return: Configured EMT template.
    """
    bus_active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    core_ph_a: bool = phA
    core_ph_b: bool = phB
    core_ph_c: bool = phC

    if connection_type == ShuntConnectionType.Delta:
        branch_specs = _get_delta_branch_specs(bus_active_phases)
        if len(branch_specs) == 0:
            raise ValueError("Delta EMT exponential loads require at least one active delta branch")
        else:
            pass

        core_ph_a = any(branch_label == "AB" for branch_label, _, _ in branch_specs)
        core_ph_b = any(branch_label == "BC" for branch_label, _, _ in branch_specs)
        core_ph_c = any(branch_label == "CA" for branch_label, _, _ in branch_specs)
    else:
        pass

    active_phases: List[str] = _get_active_phases(phA=core_ph_a, phB=core_ph_b, phC=core_ph_c)
    phase_count: int = len(bus_active_phases)
    resolved_name: str = _get_phase_count_name(base_name="EXP_Load_EMT", phase_count=phase_count, requested_name=name)

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = resolved_name
    templ.block.name = resolved_name

    # Shared constants stay scalar because every per-phase equation reuses the
    # same EMT formulation and only the active phase list changes the sizing.
    c2: Expr = vf.add_const(2.0)
    c05: Expr = vf.add_const(0.5)

    # Runtime parameters remain global to the load object because they are fed by
    # the EMT initialization workflow and reused across all active phases.
    v0: Var = vf.add_var(name=f"V0")
    alpha_p: Var = vf.add_var(name=f"a")
    alpha_q: Var = vf.add_var(name=f"b")
    k_sogi: Var = vf.add_var(name=f"k_sogi")
    eps: Var = vf.add_var(name=f"eps")
    omega: Var = vf.add_var(name=f"omega")

    templ.block.event_dict[v0] = vf.add_const(float(np.sqrt(2.0)))
    templ.block.event_dict[alpha_p] = vf.add_const(2.0)
    templ.block.event_dict[alpha_q] = vf.add_const(2.0)
    templ.block.event_dict[k_sogi] = vf.add_const(float(np.sqrt(2.0)))
    templ.block.event_dict[eps] = vf.add_const(1e-12)

    # All phase-indexed structures are built from the active phase list so the
    # block sizes, names and ordering match the electrical connection exactly.
    voltage_vars: Dict[str, Var] = dict()
    voltage_derivative_vars: Dict[str, Var] = dict()
    p0_vars: Dict[str, Var] = dict()
    q0_vars: Dict[str, Var] = dict()
    u_vars: Dict[str, Var] = dict()
    q_vars: Dict[str, Var] = dict()
    d_u_vars: Dict[str, Var] = dict()
    d_q_vars: Dict[str, Var] = dict()
    v2_vars: Dict[str, Var] = dict()
    vm_vars: Dict[str, Var] = dict()
    ratio_vars: Dict[str, Var] = dict()
    p_vars: Dict[str, Var] = dict()
    q_load_vars: Dict[str, Var] = dict()
    current_vars: Dict[str, Var] = dict()

    in_vars: List[Var] = list()
    state_vars: List[Var] = list()
    diff_vars: List[Var] = list()
    state_eqs: List[Expr] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    init_eqs: Dict[Var, Expr] = dict()
    diff_init_eqs: Dict[Var, Expr] = dict()

    phase_label: str
    for phase_label in active_phases:
        # These are the only bus-voltage inputs created, which is what makes the
        # symbolic block itself phase-selective without any EMT core changes.
        voltage_var: Var = vf.add_var(
            name=f"v_{phase_label}",
            reference=_get_voltage_reference(phase_label=phase_label),
        )
        voltage_derivative_var: Var = vf.add_var(name=f"d_v_{phase_label}")
        p0_var: Var = vf.add_var(name=f"P0_{phase_label}")
        q0_var: Var = vf.add_var(name=f"Q0_{phase_label}")

        templ.block.event_dict[voltage_derivative_var] = vf.add_const(None)
        # Keep device-backed load powers event-capable. Const(None) records that
        # api_obj_mapping is their exclusive initial source.
        templ.block.event_dict[p0_var] = vf.add_const(None)
        templ.block.event_dict[q0_var] = vf.add_const(None)

        voltage_vars[phase_label] = voltage_var
        voltage_derivative_vars[phase_label] = voltage_derivative_var
        p0_vars[phase_label] = p0_var
        q0_vars[phase_label] = q0_var
        in_vars.append(voltage_var)

        # Each active phase keeps the original two SOGI states and two dynamic
        # equations, so the ABC case remains mathematically identical.
        u_var: Var = vf.add_var(name=f"u_{phase_label}")
        q_var: Var = vf.add_var(name=f"q_{phase_label}")
        d_u_var: Var = vf.add_diff_var(name=f"d_u_{phase_label}", base_var=u_var)
        d_q_var: Var = vf.add_diff_var(name=f"d_q_{phase_label}", base_var=q_var)

        u_vars[phase_label] = u_var
        q_vars[phase_label] = q_var
        d_u_vars[phase_label] = d_u_var
        d_q_vars[phase_label] = d_q_var
        state_vars.append(u_var)
        state_vars.append(q_var)
        diff_vars.append(d_u_var)
        diff_vars.append(d_q_var)
        state_eqs.append(k_sogi * omega * (voltage_var - u_var) - omega * q_var)
        state_eqs.append(omega * u_var)

        # The algebraic layer is also instantiated strictly per active phase so
        # there are no inactive placeholders or index gaps in AC/BC-style cases.
        v2_var: Var = vf.add_var(name=f"V{phase_label}2")
        vm_var: Var = vf.add_var(name=f"Vm{phase_label}")
        ratio_var: Var = vf.add_var(name=f"r{phase_label}")
        ratio_sq_var: Var = vf.add_var(name=f"r2{phase_label}")
        p_var: Var = vf.add_var(name=f"P_{phase_label}")
        q_load_var: Var = vf.add_var(name=f"Q_{phase_label}")
        current_var: Var = vf.add_var(
            name=f"i_{phase_label}",
            reference=_get_current_reference(phase_label),
        )

        v2_vars[phase_label] = v2_var
        vm_vars[phase_label] = vm_var
        ratio_vars[phase_label] = ratio_var
        p_vars[phase_label] = p_var
        q_load_vars[phase_label] = q_load_var
        current_vars[phase_label] = current_var
        algebraic_vars.append(v2_var)
        algebraic_vars.append(vm_var)
        algebraic_vars.append(ratio_var)
        algebraic_vars.append(ratio_sq_var)
        algebraic_vars.append(p_var)
        algebraic_vars.append(q_load_var)
        algebraic_vars.append(current_var)

        # Newton iterations can briefly visit non-physical negative ``V^2`` values
        # before returning to the feasible region. Keep the magnitude-related
        # algebraics real-valued during those trial steps so the EMT solve degrades
        # gracefully instead of producing NaNs that poison the whole substep.
        safe_v2_expr: Expr = symbolic_abs(v2_var) + eps

        algebraic_eqs.append(v2_var - (u_var * u_var + q_var * q_var))
        algebraic_eqs.append(vm_var - (safe_v2_expr ** c05))

        # Keep the exponential-load voltage ratio strictly away from zero so the
        # generated Jacobian of ``ratio ** alpha`` does not produce hidden
        # ``1 / vm`` factors when Newton probes zero-voltage trial states.
        safe_vm_expr: Expr = vm_var + eps
        safe_ratio_sq_expr: Expr = safe_v2_expr / (v0 * v0)
        safe_power_base_expr: Expr = safe_ratio_sq_expr + eps
        p_power_expr: Expr = symbolic_exp((alpha_p / c2) * symbolic_log(safe_power_base_expr))
        q_power_expr: Expr = symbolic_exp((alpha_q / c2) * symbolic_log(safe_power_base_expr))
        algebraic_eqs.append(ratio_var - (safe_vm_expr / v0))
        algebraic_eqs.append(ratio_sq_var - safe_ratio_sq_expr)
        algebraic_eqs.append(p_var + (p0_var * p_power_expr))
        algebraic_eqs.append(q_load_var + (q0_var * q_power_expr))
        algebraic_eqs.append(current_var - (c2 * (u_var * p_var + q_var * q_load_var) / safe_v2_expr))

        # The explicit initializer consumes these seeds phase by phase using the
        # same formulas as before, now limited to the active subset.
        init_eqs[u_var] = voltage_var
        init_eqs[q_var] = -voltage_derivative_var / omega
        init_eqs[v2_var] = u_var * u_var + q_var * q_var
        init_eqs[vm_var] = safe_v2_expr ** c05
        init_eqs[ratio_var] = safe_vm_expr / v0
        init_eqs[ratio_sq_var] = safe_ratio_sq_expr
        init_eqs[p_var] = -(p0_var * p_power_expr)
        init_eqs[q_load_var] = -(q0_var * q_power_expr)
        init_eqs[current_var] = c2 * (u_var * p_var + q_var * q_load_var) / safe_v2_expr

        diff_init_eqs[d_u_var] = voltage_derivative_var
        diff_init_eqs[d_q_var] = omega * u_var

    if connection_type == ShuntConnectionType.Delta:
        # Delta branches are driven by line-to-line voltages whose nominal peak
        # magnitude is sqrt(3) times the phase-to-neutral peak base.
        templ.block.set_parameter_in_model(var_name=f"V0", new_value=float(np.sqrt(6.0)))
    else:
        pass

    block_model = templ.block.__class__(
        in_vars=in_vars,
        out_vars=list(current_vars[phase_label] for phase_label in active_phases),
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        algebraic_vars=algebraic_vars,
        algebraic_eqs=algebraic_eqs,
        init_eqs=init_eqs,
        diff_init_eqs=diff_init_eqs,
    )
    block_model.name = resolved_name
    block_model.event_dict = dict()
    # Move only device-backed runtime parameters to the physical child that
    # owns their API mappings. Model-wide controls and derivative inputs remain
    # exposed by the root without being duplicated in the child.
    for phase_label in active_phases:
        p0_var = p0_vars[phase_label]
        q0_var = q0_vars[phase_label]
        block_model.event_dict[p0_var] = templ.block.event_dict.pop(p0_var)
        block_model.event_dict[q0_var] = templ.block.event_dict.pop(q0_var)
    block_model.parameters = templ.block.parameters
    templ.block.parameters = dict()
    block_model.parameters[omega] = vf.add_const(2.0 * np.pi * 50.0)

    # The external mapping keeps the fixed EMT enum contract, but only active
    # phases publish concrete variables. Inactive phases are explicit ``None``.
    external_mapping: Dict[VarPowerFlowReferenceType, Var | None] = dict({
        VarPowerFlowReferenceType.v_A: voltage_vars.get("A", None),
        VarPowerFlowReferenceType.v_B: voltage_vars.get("B", None),
        VarPowerFlowReferenceType.v_C: voltage_vars.get("C", None),
        VarPowerFlowReferenceType.P_A: p_vars.get("A", None),
        VarPowerFlowReferenceType.Q_A: q_load_vars.get("A", None),
        VarPowerFlowReferenceType.P_B: p_vars.get("B", None),
        VarPowerFlowReferenceType.Q_B: q_load_vars.get("B", None),
        VarPowerFlowReferenceType.P_C: p_vars.get("C", None),
        VarPowerFlowReferenceType.Q_C: q_load_vars.get("C", None),
        # VarPowerFlowReferenceType.i_N: None,
        VarPowerFlowReferenceType.i_A: current_vars.get("A", None),
        VarPowerFlowReferenceType.i_B: current_vars.get("B", None),
        VarPowerFlowReferenceType.i_C: current_vars.get("C", None),
        VarPowerFlowReferenceType.d_v_A: voltage_derivative_vars.get("A", None),
        VarPowerFlowReferenceType.d_v_B: voltage_derivative_vars.get("B", None),
        VarPowerFlowReferenceType.d_v_C: voltage_derivative_vars.get("C", None),
    })
    block_model.external_mapping = external_mapping

    # The load initializer writes only the active per-phase parameters into the
    # block, which keeps template metadata aligned with the generated equations.
    api_obj_mapping: Dict[ParamPowerFlowReferenceType, Var] = dict({
        ParamPowerFlowReferenceType.omega_base: omega,
    })

    for phase_label in active_phases:
        p_reference: ParamPowerFlowReferenceType
        q_reference: ParamPowerFlowReferenceType
        p_reference, q_reference = _get_api_power_references(phase_label=phase_label)
        api_obj_mapping[p_reference] = p0_vars[phase_label]
        api_obj_mapping[q_reference] = q0_vars[phase_label]

    block_model.api_obj_mapping = api_obj_mapping

    templ.block.children.append(block_model)
    templ.block.external_mapping = block_model.external_mapping
    templ.block.in_vars = block_model.in_vars
    templ.block.out_vars = block_model.out_vars

    if connection_type is None:
        return templ
    else:
        if connection_type == ShuntConnectionType.Delta:
            return wrap_delta_referenced_load_emt_template(
                vf=vf,
                core_template=templ,
                active_phases=bus_active_phases,
                name=resolved_name,
            )
        else:
            return wrap_ground_referenced_load_emt_template(
                vf=vf,
                core_template=templ,
                active_phases=bus_active_phases,
                connection_type=connection_type,
                name=resolved_name,
            )
