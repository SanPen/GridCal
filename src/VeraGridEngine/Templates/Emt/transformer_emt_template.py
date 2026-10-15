# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import uuid
from typing import Dict, List, Tuple

from VeraGridEngine.enumerations import (
    BlockType,
    DeviceType,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
    WindingType,
)
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_grounding_link_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Expr


def _create_transformer_editor_connection_child(var: Var, is_input: bool, name: str) -> Block:
    """
    Build one visual-only connection child used by ``Edit Hierarchy``.

    :param var: Shared root-port variable.
    :param is_input: True for one input connector.
    :param name: Child block name.
    :return: Lightweight block exposing the shared port variable.
    """
    child_block: Block = Block(name=name)

    if is_input:
        child_block.out_vars.append(var)
    else:
        child_block.in_vars.append(var)

    return child_block


def _attach_transformer_editor_diagram(root_block: Block,
                                       input_vars: List[Var],
                                       output_vars: List[Var],
                                       grounding_pairs: List[Tuple[Var, Block]]) -> None:
    """
    Attach one persisted minimal editor diagram for an EMT transformer block.

    :param root_block: Transformer root block.
    :param input_vars: Public input variables.
    :param output_vars: Public output variables.
    :param grounding_pairs: Pairs ``(neutral_input_var, grounding_link_block)``.
    :return: None.
    """
    input_blocks_by_name: Dict[str, Block] = dict()
    input_index: int
    output_index: int
    grounding_index: int
    input_var: Var
    output_var: Var
    grounding_pair: Tuple[Var, Block]

    for input_index, input_var in enumerate(input_vars):
        input_block: Block = _create_transformer_editor_connection_child(
            var=input_var,
            is_input=True,
            name=input_var.name,
        )
        root_block.add(input_block)
        root_block.diagram.add_node(
            name=input_block.name,
            x=40.0,
            y=80.0 + 80.0 * float(input_index),
            tpe=BlockType.INPUT_CONN.name,
            device_uid=input_block.uid,
        )
        input_blocks_by_name[input_var.name] = input_block

    for output_index, output_var in enumerate(output_vars):
        output_block: Block = _create_transformer_editor_connection_child(
            var=output_var,
            is_input=False,
            name=output_var.name,
        )
        root_block.add(output_block)
        root_block.diagram.add_node(
            name=output_block.name,
            x=640.0,
            y=80.0 + 50.0 * float(output_index),
            tpe=BlockType.OUTPUT_CONN.name,
            device_uid=output_block.uid,
        )

    for grounding_index, grounding_pair in enumerate(grounding_pairs):
        neutral_input_var, grounding_link_block = grounding_pair
        root_block.diagram.add_node(
            name=grounding_link_block.name,
            x=340.0,
            y=180.0 + 140.0 * float(grounding_index),
            tpe=BlockType.GROUNDING_LINK_EMT.name,
            device_uid=grounding_link_block.uid,
        )
        neutral_input_block: Block | None = input_blocks_by_name.get(neutral_input_var.name, None)

        if neutral_input_block is not None:
            root_block.diagram.add_branch(
                connectionitem_uid=uuid.uuid4().int,
                device_uid_from=neutral_input_block.uid,
                device_uid_to=grounding_link_block.uid,
                port_number_from=0,
                port_number_to=0,
                color="#587291",
            )
        else:
            pass




def get_transformer_emt_template(
    vf: VarFactory,
    conn_f: WindingType | None = None,
    conn_t: WindingType | None = None,
    name: str = "transformer_emt_template",
) -> EmtModelTemplate:
    """
    Build a linear two-winding transformer EMT template using coupled winding currents
    as state variables.

    The winding model retains its mutual inductance. Core-loss conductance is
    split equally on a common primary-referred basis between the two terminals;
    the secondary conductance is scaled by the square of the voltage ratio.
    Winding-current initialization subtracts the respective loss currents from
    the PF terminal currents.

    Assumptions:
    - `l1`, `l2`, and `m12` already represent the physical transformer model in the
      chosen winding coordinates.
    - branch currents are positive when leaving the connected bus.
    - `if_act` and `it_act` are externally initialized by the EMT framework from the
      power-flow solution through `external_mapping`.

    :param vf: EMT variable factory.
    :param conn_f: Optional from-side winding connection.
    :param conn_t: Optional to-side winding connection.
    :param name: Symbolic model name.
    :return: EMT transformer model template.
    """

    name = "transformer_emt_template"

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.Transformer2WDevice
    templ.name = name


    if conn_f in {WindingType.GroundedStar, WindingType.NeutralStar}:
        from_has_neutral_port: bool = True
    else:
        from_has_neutral_port = False

    if conn_t in {WindingType.GroundedStar, WindingType.NeutralStar}:
        to_has_neutral_port: bool = True
    else:
        to_has_neutral_port = False

    c_eps = vf.add_const(1e-12)

    # ------------------------------------------------------------------
    # Static parameters injected from the API object
    # ------------------------------------------------------------------
    r1: Var = vf.add_var(name=f"trafo_r1")
    r2: Var = vf.add_var(name=f"trafo_r2")
    l1: Var = vf.add_var(name=f"trafo_l1")
    l2: Var = vf.add_var(name=f"trafo_l2")
    m12: Var = vf.add_var(name=f"trafo_m")
    gm: Var = vf.add_var(name=f"trafo_gm")
    total_voltage_ratio: Var = vf.add_var(name=f"trafo_tap_ratio")

    block = Block()
    block.name = name

    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_winding1_resistance_pu] = r1
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_winding2_resistance_pu] = r2
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_winding1_inductance_pu_s] = l1
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_winding2_inductance_pu_s] = l2
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_mutual_inductance_pu_s] = m12
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_magnetizing_conductance_pu] = gm
    block.api_obj_mapping[ParamPowerFlowReferenceType.transformer_total_voltage_ratio] = total_voltage_ratio
    block.parameters.update({
        r1: vf.add_const(None),
        r2: vf.add_const(None),
        l1: vf.add_const(None),
        l2: vf.add_const(None),
        m12: vf.add_const(None),
        gm: vf.add_const(None),
        total_voltage_ratio: vf.add_const(None),
    })

    # ------------------------------------------------------------------
    # Terminal voltages
    # ------------------------------------------------------------------
    vf_n: Var | None = None
    vt_n: Var | None = None
    from_ground_current: Var | None = None
    to_ground_current: Var | None = None
    from_grounding_link_block: Block | None = None
    to_grounding_link_block: Block | None = None

    if from_has_neutral_port:
        vf_n = vf.add_var(name=f"vf_N", reference=VarPowerFlowReferenceType.vf_N)
    else:
        pass

    if to_has_neutral_port:
        vt_n = vf.add_var(name=f"vt_N", reference=VarPowerFlowReferenceType.vt_N)
    else:
        pass

    if conn_f == WindingType.GroundedStar and vf_n is not None:
        from_grounding_link_template: EmtModelTemplate = get_grounding_link_emt_template(
            vf=vf,
            include_r=False,
            include_l=False,
            include_c=False,
            solid_connection=True,
            nested=True,
            name=name + "_from_grounding_link",
        )
        vf.add_connections(from_grounding_link_template.block.in_vars, [vf_n])
        from_ground_current = from_grounding_link_template.block.out_vars[0]
        from_grounding_link_block = from_grounding_link_template.block
        block.add(from_grounding_link_block)
    else:
        pass

    if conn_t == WindingType.GroundedStar and vt_n is not None:
        to_grounding_link_template: EmtModelTemplate = get_grounding_link_emt_template(
            vf=vf,
            include_r=False,
            include_l=False,
            include_c=False,
            solid_connection=True,
            nested=True,
            name=name + "_to_grounding_link",
        )
        vf.add_connections(to_grounding_link_template.block.in_vars, [vt_n])
        to_ground_current = to_grounding_link_template.block.out_vars[0]
        to_grounding_link_block = to_grounding_link_template.block
        block.add(to_grounding_link_block)
    else:
        pass

    vf_vars: list[Var] = [
        vf.add_var(name=f"vf_A", reference=VarPowerFlowReferenceType.vf_A),
        vf.add_var(name=f"vf_B", reference=VarPowerFlowReferenceType.vf_B),
        vf.add_var(name=f"vf_C", reference=VarPowerFlowReferenceType.vf_C),
    ]
    vt_vars: list[Var] = [
        vf.add_var(name=f"vt_A", reference=VarPowerFlowReferenceType.vt_A),
        vf.add_var(name=f"vt_B", reference=VarPowerFlowReferenceType.vt_B),
        vf.add_var(name=f"vt_C", reference=VarPowerFlowReferenceType.vt_C),
    ]

    # ------------------------------------------------------------------
    # Internal winding-current states
    # ------------------------------------------------------------------
    i_f: list[Var] = [
        vf.add_var(name=f"i_f_A"),
        vf.add_var(name=f"i_f_B"),
        vf.add_var(name=f"i_f_C"),
    ]
    i_t: list[Var] = [
        vf.add_var(name=f"i_t_A"),
        vf.add_var(name=f"i_t_B"),
        vf.add_var(name=f"i_t_C"),
    ]

    di_f: list[Var] = [
        vf.add_diff_var(name=f"di_f_A", base_var=i_f[0]),
        vf.add_diff_var(name=f"di_f_B", base_var=i_f[1]),
        vf.add_diff_var(name=f"di_f_C", base_var=i_f[2]),
    ]
    di_t: list[Var] = [
        vf.add_diff_var(name=f"di_t_A", base_var=i_t[0]),
        vf.add_diff_var(name=f"di_t_B", base_var=i_t[1]),
        vf.add_diff_var(name=f"di_t_C", base_var=i_t[2]),
    ]

    # ------------------------------------------------------------------
    # External branch-port currents
    # ------------------------------------------------------------------
    if_act: list[Var] = [
        vf.add_var(name=f"if_A", reference=VarPowerFlowReferenceType.if_A),
        vf.add_var(name=f"if_B", reference=VarPowerFlowReferenceType.if_B),
        vf.add_var(name=f"if_C", reference=VarPowerFlowReferenceType.if_C),
    ]
    it_act: list[Var] = [
        vf.add_var(name=f"it_A", reference=VarPowerFlowReferenceType.it_A),
        vf.add_var(name=f"it_B", reference=VarPowerFlowReferenceType.it_B),
        vf.add_var(name=f"it_C", reference=VarPowerFlowReferenceType.it_C),
    ]
    if_n_act: Var | None = vf.add_var(name=f"if_N", reference=VarPowerFlowReferenceType.if_N) if from_has_neutral_port else None
    it_n_act: Var | None = vf.add_var(name=f"it_N", reference=VarPowerFlowReferenceType.it_N) if to_has_neutral_port else None

    input_vars: list[Var] = list()
    if vf_n is not None:
        input_vars.append(vf_n)
    else:
        pass

    input_vars.extend(vf_vars)

    if vt_n is not None:
        input_vars.append(vt_n)
    else:
        pass

    input_vars.extend(vt_vars)

    algebraic_vars: list[Var] = list(if_act + it_act)
    if if_n_act is not None:
        algebraic_vars.append(if_n_act)
    else:
        pass

    if it_n_act is not None:
        algebraic_vars.append(it_n_act)
    else:
        pass

    block.in_vars = input_vars
    block.state_vars = i_f + i_t
    block.diff_vars = di_f + di_t
    block.algebraic_vars = algebraic_vars

    v_f_term: list[Expr] = list()
    v_t_term: list[Expr] = list()
    idx: int
    for idx in range(3):
        if vf_n is not None:
            v_f_term.append(vf_vars[idx] - vf_n)
        else:
            v_f_term.append(vf_vars[idx])

        if vt_n is not None:
            v_t_term.append(vt_vars[idx] - vt_n)
        else:
            v_t_term.append(vt_vars[idx])

    # ------------------------------------------------------------------
    # Coupled winding dynamics
    #
    # [l1  m12] [di_f/dt] = [vf - r1*i_f]
    # [m12 l2 ] [di_t/dt]   [vt - r2*i_t]
    #
    # Inverting the inductance matrix gives negative signs in the cross terms.
    # ------------------------------------------------------------------
    state_eqs_f: list[Expr] = []
    state_eqs_t: list[Expr] = []
    # Evaluate the nearly singular coupled matrix through its leakage terms.
    # Directly forming l1*l2-m12**2 loses precision when the static model has
    # no magnetizing shunt and the mapper consequently uses a very large Lm.
    leakage_l1: Expr = l1 - m12 * total_voltage_ratio
    leakage_l2: Expr = l2 - m12 / total_voltage_ratio
    det_l: Expr = (
        leakage_l1 * leakage_l2
        + leakage_l1 * m12 / total_voltage_ratio
        + leakage_l2 * m12 * total_voltage_ratio
    )

    for idx in range(3):
        primary_rhs: Expr = v_f_term[idx] - r1 * i_f[idx]
        secondary_rhs: Expr = v_t_term[idx] - r2 * i_t[idx]

        numerator_f: Expr = (
            leakage_l2 * primary_rhs
            + m12 * (primary_rhs / total_voltage_ratio - secondary_rhs)
        )
        numerator_t: Expr = (
            leakage_l1 * secondary_rhs
            + m12 * (total_voltage_ratio * secondary_rhs - primary_rhs)
        )
        state_eqs_f.append(numerator_f / (det_l + c_eps))
        state_eqs_t.append(numerator_t / (det_l + c_eps))

    block.state_eqs = state_eqs_f + state_eqs_t

    # ------------------------------------------------------------------
    # Port-current algebraic equations
    #
    # Split the primary-referred core-loss conductance equally. Referring the
    # secondary half through n=Vf/Vt multiplies its conductance by n**2.
    # ------------------------------------------------------------------
    g_from: Expr = gm * vf.add_const(0.5)
    g_to: Expr = g_from * total_voltage_ratio * total_voltage_ratio
    alg_eqs: list[Expr] = []
    for idx in range(3):
        alg_eqs.append(if_act[idx] - (i_f[idx] + g_from * v_f_term[idx]))
        alg_eqs.append(it_act[idx] - (i_t[idx] + g_to * v_t_term[idx]))

    if if_n_act is not None:
        neutral_from_kcl: Expr = if_n_act + if_act[0] + if_act[1] + if_act[2]

        if from_ground_current is not None:
            neutral_from_kcl = neutral_from_kcl + from_ground_current
        else:
            pass

        alg_eqs.append(neutral_from_kcl)
    else:
        pass

    if it_n_act is not None:
        neutral_to_kcl: Expr = it_n_act + it_act[0] + it_act[1] + it_act[2]

        if to_ground_current is not None:
            neutral_to_kcl = neutral_to_kcl + to_ground_current
        else:
            pass

        alg_eqs.append(neutral_to_kcl)
    else:
        pass

    block.algebraic_eqs = alg_eqs
    output_vars: list[Var] = list()
    if if_n_act is not None:
        output_vars.append(if_n_act)
    else:
        pass

    output_vars.extend(if_act)

    if it_n_act is not None:
        output_vars.append(it_n_act)
    else:
        pass

    output_vars.extend(it_act)
    block.out_vars = output_vars

    # ------------------------------------------------------------------
    # External mapping for network stamping / PF seeding
    # ------------------------------------------------------------------
    block.external_mapping = dict({
        VarPowerFlowReferenceType.if_N: if_n_act,
        VarPowerFlowReferenceType.if_A: if_act[0],
        VarPowerFlowReferenceType.if_B: if_act[1],
        VarPowerFlowReferenceType.if_C: if_act[2],
        VarPowerFlowReferenceType.it_N: it_n_act,
        VarPowerFlowReferenceType.it_A: it_act[0],
        VarPowerFlowReferenceType.it_B: it_act[1],
        VarPowerFlowReferenceType.it_C: it_act[2],
    })
    block.external_mapping[VarPowerFlowReferenceType.vf_N] = vf_n
    block.external_mapping[VarPowerFlowReferenceType.vt_N] = vt_n
    block.external_mapping[VarPowerFlowReferenceType.vf_A] = vf_vars[0]
    block.external_mapping[VarPowerFlowReferenceType.vf_B] = vf_vars[1]
    block.external_mapping[VarPowerFlowReferenceType.vf_C] = vf_vars[2]
    block.external_mapping[VarPowerFlowReferenceType.vt_A] = vt_vars[0]
    block.external_mapping[VarPowerFlowReferenceType.vt_B] = vt_vars[1]
    block.external_mapping[VarPowerFlowReferenceType.vt_C] = vt_vars[2]

    # ------------------------------------------------------------------
    # State initialization
    #
    # Remove each terminal's core-loss current before seeding the winding
    # states. This keeps initialization consistent with the port equations.
    # ------------------------------------------------------------------
    init_eqs: Dict[Var, Expr] = dict()
    for idx in range(3):
        init_eqs[i_f[idx]] = if_act[idx] - g_from * v_f_term[idx]
        init_eqs[i_t[idx]] = it_act[idx] - g_to * v_t_term[idx]

    block.init_eqs = init_eqs

    # ------------------------------------------------------------------
    # Derivative initialization aligned with runtime dynamics
    # ------------------------------------------------------------------
    diff_init_eqs: Dict[Var, Expr] = dict()
    for idx in range(3):
        primary_rhs: Expr = v_f_term[idx] - r1 * i_f[idx]
        secondary_rhs: Expr = v_t_term[idx] - r2 * i_t[idx]

        numerator_f: Expr = (
            leakage_l2 * primary_rhs
            + m12 * (primary_rhs / total_voltage_ratio - secondary_rhs)
        )
        numerator_t: Expr = (
            leakage_l1 * secondary_rhs
            + m12 * (total_voltage_ratio * secondary_rhs - primary_rhs)
        )
        diff_init_eqs[di_f[idx]] = numerator_f / (det_l + c_eps)
        diff_init_eqs[di_t[idx]] = numerator_t / (det_l + c_eps)

    block.diff_init_eqs = diff_init_eqs

    grounding_pairs: List[Tuple[Var, Block]] = list()
    if vf_n is not None and from_grounding_link_block is not None:
        grounding_pairs.append((vf_n, from_grounding_link_block))
    else:
        pass

    if vt_n is not None and to_grounding_link_block is not None:
        grounding_pairs.append((vt_n, to_grounding_link_block))
    else:
        pass

    _attach_transformer_editor_diagram(
        root_block=block,
        input_vars=input_vars,
        output_vars=output_vars,
        grounding_pairs=grounding_pairs,
    )

    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars

    return templ


def get_series_transformer_emt_template(
        vf: VarFactory,
        name: str = "series_transformer_emt_template",
        r: float | None = None,
        x: float | None = None,
        tap_module: float | None = None,
) -> EmtModelTemplate:
    """Build a three-wire series R/X transformer on the standard pu base.

    This model is intended for transformers, such as those in the balanced
    Kundur case, whose static representation contains only series R/X and a
    fixed tap. Currents use the conventional three-phase current base. The
    state is the from-terminal current, so the static R/X impedance is referred
    to that current by the squared tap in the equations. Stored R/X stay unchanged.

    :param vf: Factory owning the symbolic variables and constants.
    :param name: Model and block name.
    :param r: Static series resistance in p.u.; None uses device mapping.
    :param x: Static series reactance in p.u.; None uses device mapping.
    :param tap_module: Fixed magnitude tap; None uses device mapping.
    :return: Three-wire series transformer with from-terminal current states.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.Transformer2WDevice
    templ.name = name
    templ.block.name = name
    eps = vf.add_const(1.0e-12)
    r_ser = vf.add_var("trafo_series_r") if r is None else vf.add_const(float(r))
    x_ser = vf.add_var("trafo_series_x") if x is None else vf.add_const(float(x))
    omega_base = vf.add_var("trafo_series_omega_base")
    tap_ratio = vf.add_var("trafo_series_tap_ratio") if tap_module is None else vf.add_const(float(tap_module))
    if r is None:
        templ.block.api_obj_mapping[ParamPowerFlowReferenceType.r] = r_ser
        templ.block.parameters[r_ser] = vf.add_const(0.0)
    if x is None:
        templ.block.api_obj_mapping[ParamPowerFlowReferenceType.x] = x_ser
        templ.block.parameters[x_ser] = vf.add_const(0.0)
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.omega_base] = omega_base
    if tap_module is None:
        templ.block.api_obj_mapping[ParamPowerFlowReferenceType.tap_module] = tap_ratio
        templ.block.parameters[tap_ratio] = vf.add_const(1.0)
    templ.block.parameters[omega_base] = vf.add_const(1.0)

    vf_vars = [vf.add_var(f"vf_{phase}", reference=reference) for phase, reference in zip(
        "ABC", (VarPowerFlowReferenceType.vf_A, VarPowerFlowReferenceType.vf_B, VarPowerFlowReferenceType.vf_C))]
    vt_vars = [vf.add_var(f"vt_{phase}", reference=reference) for phase, reference in zip(
        "ABC", (VarPowerFlowReferenceType.vt_A, VarPowerFlowReferenceType.vt_B, VarPowerFlowReferenceType.vt_C))]
    currents = [vf.add_var(f"i_ser_{phase}") for phase in "ABC"]
    derivatives = [vf.add_diff_var(f"di_ser_{phase}", base_var=currents[idx])
                   for idx, phase in enumerate("ABC")]
    if_vars = [vf.add_var(f"if_{phase}", reference=reference) for phase, reference in zip(
        "ABC", (VarPowerFlowReferenceType.if_A, VarPowerFlowReferenceType.if_B, VarPowerFlowReferenceType.if_C))]
    it_vars = [vf.add_var(f"it_{phase}", reference=reference) for phase, reference in zip(
        "ABC", (VarPowerFlowReferenceType.it_A, VarPowerFlowReferenceType.it_B, VarPowerFlowReferenceType.it_C))]
    # The static equivalent uses If=(Vf-tap*Vt)/(tap²*Z) and It=-tap*If.
    tap_ratio_squared: Expr = tap_ratio * tap_ratio
    series_resistance: Expr = tap_ratio_squared * r_ser
    inductance: Expr = tap_ratio_squared * x_ser / (omega_base + eps)
    state_eqs = [
        (vf_vars[idx] - tap_ratio * vt_vars[idx] - series_resistance * currents[idx]) / (inductance + eps)
        for idx in range(3)
    ]
    templ.block.in_vars = vf_vars + vt_vars
    templ.block.state_vars = currents
    templ.block.diff_vars = derivatives
    templ.block.state_eqs = state_eqs
    templ.block.algebraic_vars = if_vars + it_vars
    templ.block.algebraic_eqs = (
        [if_vars[idx] - currents[idx] for idx in range(3)]
        + [it_vars[idx] + tap_ratio * currents[idx] for idx in range(3)]
    )
    templ.block.out_vars = if_vars + it_vars
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.vf_N: None,
        VarPowerFlowReferenceType.vf_A: vf_vars[0],
        VarPowerFlowReferenceType.vf_B: vf_vars[1],
        VarPowerFlowReferenceType.vf_C: vf_vars[2],
        VarPowerFlowReferenceType.vt_N: None,
        VarPowerFlowReferenceType.vt_A: vt_vars[0],
        VarPowerFlowReferenceType.vt_B: vt_vars[1],
        VarPowerFlowReferenceType.vt_C: vt_vars[2],
        VarPowerFlowReferenceType.if_N: None,
        VarPowerFlowReferenceType.if_A: if_vars[0],
        VarPowerFlowReferenceType.if_B: if_vars[1],
        VarPowerFlowReferenceType.if_C: if_vars[2],
        VarPowerFlowReferenceType.it_N: None,
        VarPowerFlowReferenceType.it_A: it_vars[0],
        VarPowerFlowReferenceType.it_B: it_vars[1],
        VarPowerFlowReferenceType.it_C: it_vars[2],
    }
    templ.block.init_eqs = {
        currents[idx]: 0.5 * (if_vars[idx] - it_vars[idx] / (tap_ratio + eps))
        for idx in range(3)
    }
    templ.block.diff_init_eqs = {derivatives[idx]: state_eqs[idx] for idx in range(3)}
    _attach_transformer_editor_diagram(templ.block, templ.block.in_vars, templ.block.out_vars, [])
    return templ


class TransformerEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="conn_f", units="", descr="From-side winding connection.", tpe=WindingType, value=None),
                TemplateProp(name="conn_t", units="", descr="To-side winding connection.", tpe=WindingType, value=None),
                TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str, value="transformer_emt_template"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        return get_transformer_emt_template(
            self.vf,
            conn_f=self.get_value("conn_f"),
            conn_t=self.get_value("conn_t"),
            name=self.get_value("name"),
        )
