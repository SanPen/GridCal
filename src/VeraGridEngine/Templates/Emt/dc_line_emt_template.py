# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.Symbolic.block import Block


def get_dc_line_emt_template(vf: VarFactory, name: str = "dc_line_emt_template") -> EmtModelTemplate:
    """
    Build a DC EMT line with the same symbolic structure as the AC PI line template.

    The static DC line data currently exposes only the series resistance. To keep
    the EMT implementation aligned with the existing AC PI code structure without
    adding new static parameters, the template models:

    - one series current state,
    - one explicit shunt leg per terminal,
    - one tiny fixed electrical time constant that regularizes the series branch
      and makes it behave like a near-resistive PI section.

    With zero shunt capacitance the EMT steady state remains consistent with the
    static PF model, while the code layout stays close to ``pi_line_emt_template``.

    :param vf: Shared EMT variable factory.
    :param name: Symbolic model name.
    :return: EMT DC line template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.DCLineDevice
    templ.name = name

    block = Block()

    c0: Const = Const(0.0)
    tau_series: Const = Const(5.0e-5)
    g_damp: Const = Const(1.0e-8)
    c_shunt: Const = Const(0.0)

    # ------------------------------------------------------------------
    # External terminal voltages.
    # ------------------------------------------------------------------
    v_f_dc: Var = vf.add_var(name=f"v_f_dc", reference=VarPowerFlowReferenceType.Vf_dc)
    v_t_dc: Var = vf.add_var(name=f"v_t_dc", reference=VarPowerFlowReferenceType.Vt_dc)

    # ------------------------------------------------------------------
    # API-mapped electrical parameter.
    # ------------------------------------------------------------------
    g_ser: Var = vf.add_var(name=f"g_ser")
    block.parameters[g_ser] = Const(0.0)

    # ------------------------------------------------------------------
    # PI-structure variables.
    # ------------------------------------------------------------------
    i_ser: Var = vf.add_var(name=f"i_ser")
    q_f: Var = vf.add_var(name=f"q_f")
    q_t: Var = vf.add_var(name=f"q_t")

    di_ser: Var = vf.add_diff_var(name=f"di_ser", base_var=i_ser)
    dq_f: Var = vf.add_diff_var(name=f"dq_f", base_var=q_f)
    dq_t: Var = vf.add_diff_var(name=f"dq_t", base_var=q_t)

    i_cap_f: Var = vf.add_var(name=f"i_cap_f")
    i_cap_t: Var = vf.add_var(name=f"i_cap_t")
    i_f_dc: Var = vf.add_var(name=f"i_f_dc", reference=VarPowerFlowReferenceType.If_dc)
    i_t_dc: Var = vf.add_var(name=f"i_t_dc", reference=VarPowerFlowReferenceType.It_dc)
    p_f: Var = vf.add_var(name=f"p_f_dc", reference=VarPowerFlowReferenceType.Pf)
    p_t: Var = vf.add_var(name=f"p_t_dc", reference=VarPowerFlowReferenceType.Pt)

    # ------------------------------------------------------------------
    # Series-branch dynamics.
    # ------------------------------------------------------------------
    # The reduced-order DC PI line uses a fixed tiny time constant so the series
    # current tracks the resistive PF solution quickly without becoming algebraic.
    di_ser_expression: Expr = (g_ser * (v_f_dc - v_t_dc) - i_ser) / tau_series

    block.in_vars = list([v_f_dc, v_t_dc])
    block.state_vars = list([i_ser, q_f, q_t])
    block.diff_vars = list([di_ser, dq_f, dq_t])
    block.algebraic_vars = list([i_cap_f, i_cap_t, i_f_dc, i_t_dc, p_f, p_t])

    block.state_eqs = list([
        di_ser_expression,
        i_cap_f,
        i_cap_t,
    ])

    block.algebraic_eqs = list([
        q_f - c_shunt * v_f_dc,
        q_t - c_shunt * v_t_dc,
        i_f_dc - (i_ser + i_cap_f + g_damp * v_f_dc),
        i_t_dc - (-i_ser + i_cap_t + g_damp * v_t_dc),
        p_f - v_f_dc * i_f_dc,
        p_t - v_t_dc * i_t_dc,
    ])

    # block.out_vars = list([i_f_dc, i_t_dc, p_f, p_t])
    block.out_vars = list([i_f_dc, i_t_dc])

    block.external_mapping = dict([
        (VarPowerFlowReferenceType.Vf_dc, v_f_dc),
        (VarPowerFlowReferenceType.Vt_dc, v_t_dc),
        (VarPowerFlowReferenceType.Vdc, v_f_dc),
        (VarPowerFlowReferenceType.If_dc, i_f_dc),
        (VarPowerFlowReferenceType.It_dc, i_t_dc),
        (VarPowerFlowReferenceType.Idc, i_f_dc),
        (VarPowerFlowReferenceType.Pf, p_f),
        (VarPowerFlowReferenceType.Pt, p_t),
    ])

    block.api_obj_mapping = dict([
        (ParamPowerFlowReferenceType.g, g_ser),
    ])

    block.init_eqs = dict([
        (q_f, c_shunt * v_f_dc),
        (q_t, c_shunt * v_t_dc),
        (i_cap_f, c0),
        (i_cap_t, c0),
        (i_ser, i_f_dc - i_cap_f - g_damp * v_f_dc),
        (p_f, v_f_dc * i_f_dc),
        (p_t, v_t_dc * i_t_dc),
    ])

    block.diff_init_eqs = dict([
        (di_ser, di_ser_expression),
        (dq_f, i_cap_f),
        (dq_t, i_cap_t),
    ])

    templ.block.children.append(block)
    templ.block.name = name
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars
    return templ

def get_dc_line_with_power_input_emt_template(vf: VarFactory, name: str = "dc_line_power_input_emt") -> EmtModelTemplate:
    """
    Build a two-terminal DC EMT line with one external active-power order ``Pext``.

    The topology is a PI-type corridor arranged strictly in series as:
    ``from_node -> shunt_from -> R3L3 -> v1 -> shunt_1 -> R2L2 -> v2 -> shunt_2 -> R1L1 -> shunt_to -> to_node``.

    The model therefore contains:
    - four shunt capacitors: one at ``from``, one at ``v1``, one at ``v2``, and one at ``to``,
    - three RL branches connected in series: ``R3L3``, ``R2L2``, then ``R1L1``,
    - one injected current at ``v1`` and one injected current at ``v2`` derived from ``Pext``
      using the local node voltage.

    ``Pext`` is a runtime/event parameter. The template converts that power order into
    the local injected currents
    ``i_n1 = Pext / v1`` and ``i_n2 = Pext / v2``.

    Important implementation detail:
    - ``state_vars``, ``state_eqs`` and ``diff_vars`` are kept in exactly the same order.
    - ``algebraic_vars`` and ``algebraic_eqs`` are also kept in exactly the same order.

    :param vf: Shared EMT variable factory.
    :param name: Symbolic model name.
    :return: EMT template for the DC corridor with eventable ``Pext``.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.DCLineDevice
    templ.name = name
    block = Block()

    c0 = Const(0.0)
    eps = Const(1.0e-9)
    g_damp = Const(1.0e-8)

    v_f_dc: Var = vf.add_var(name=f"v_f_dc", reference=VarPowerFlowReferenceType.Vf_dc)
    v_t_dc: Var = vf.add_var(name=f"v_t_dc", reference=VarPowerFlowReferenceType.Vt_dc)

    r1 = vf.add_var(name=f"R1")
    l1 = vf.add_var(name=f"L1")
    r2 = vf.add_var(name=f"R2")
    l2 = vf.add_var(name=f"L2")
    r3 = vf.add_var(name=f"R3")
    l3 = vf.add_var(name=f"L3")
    c_end_f = vf.add_var(name=f"C_end_f")
    c_mid_1 = vf.add_var(name=f"C_mid_1")
    c_mid_2 = vf.add_var(name=f"C_mid_2")
    c_end_t = vf.add_var(name=f"C_end_t")
    p_ext = vf.add_var(name=f"Pext")

    v_n1 = vf.add_var(name=f"v_n1")
    v_n2 = vf.add_var(name=f"v_n2")
    q_end_f = vf.add_var(name=f"q_end_f")
    q_mid_1 = vf.add_var(name=f"q_mid_1")
    q_mid_2 = vf.add_var(name=f"q_mid_2")
    q_end_t = vf.add_var(name=f"q_end_t")
    i_r1 = vf.add_var(name=f"i_r1")
    i_r2 = vf.add_var(name=f"i_r2")
    i_r3 = vf.add_var(name=f"i_r3")

    d_q_end_f = vf.add_diff_var(name=f"d_q_end_f", base_var=q_end_f)
    d_q_mid_1 = vf.add_diff_var(name=f"d_q_mid_1", base_var=q_mid_1)
    d_q_mid_2 = vf.add_diff_var(name=f"d_q_mid_2", base_var=q_mid_2)
    d_q_end_t = vf.add_diff_var(name=f"d_q_end_t", base_var=q_end_t)
    d_i_r1 = vf.add_diff_var(name=f"d_i_r1", base_var=i_r1)
    d_i_r2 = vf.add_diff_var(name=f"d_i_r2", base_var=i_r2)
    d_i_r3 = vf.add_diff_var(name=f"d_i_r3", base_var=i_r3)

    i_cap_end_f = vf.add_var(name=f"i_cap_end_f")
    i_cap_mid_1 = vf.add_var(name=f"i_cap_mid_1")
    i_cap_mid_2 = vf.add_var(name=f"i_cap_mid_2")
    i_cap_end_t = vf.add_var(name=f"i_cap_end_t")
    i_f_dc = vf.add_var(name=f"i_f_dc", reference=VarPowerFlowReferenceType.If_dc)
    i_t_dc = vf.add_var(name=f"i_t_dc", reference=VarPowerFlowReferenceType.It_dc)
    p_f = vf.add_var(name=f"p_f_dc", reference=VarPowerFlowReferenceType.Pf)
    p_t = vf.add_var(name=f"p_t_dc", reference=VarPowerFlowReferenceType.Pt)
    i_n1 = vf.add_var(name=f"i_n1")
    i_n2 = vf.add_var(name=f"i_n2")

    i_n1_expr = p_ext / (v_n1 + eps)
    i_n2_expr = p_ext / (v_n2 + eps)

    block.in_vars = [v_f_dc, v_t_dc]

    # State ordering is explicit and must stay aligned with the differential equations.
    block.state_vars = [q_end_f, q_mid_1, q_mid_2, q_end_t, i_r1, i_r2, i_r3]
    block.diff_vars = [d_q_end_f, d_q_mid_1, d_q_mid_2, d_q_end_t, d_i_r1, d_i_r2, d_i_r3]
    block.state_eqs = [
        # d(q_end_f)/dt = current through the sending-end shunt capacitor at the from node.
        i_cap_end_f,
        # d(q_mid_1)/dt = current through the internal shunt capacitor at node v1.
        i_cap_mid_1,
        # d(q_mid_2)/dt = current through the internal shunt capacitor at node v2.
        i_cap_mid_2,
        # d(q_end_t)/dt = current through the receiving-end shunt capacitor at the to node.
        i_cap_end_t,
        # d(i_r1)/dt = RL dynamics of the last series branch between v2 and the receiving terminal.
        (v_n2 - v_t_dc - r1 * i_r1) / (l1 + eps),
        # d(i_r2)/dt = RL dynamics of the middle series branch between v1 and v2.
        (v_n1 - v_n2 - r2 * i_r2) / (l2 + eps),
        # d(i_r3)/dt = RL dynamics of the first series branch between the sending terminal and v1.
        (v_f_dc - v_n1 - r3 * i_r3) / (l3 + eps),
    ]

    # Algebraic ordering is explicit and must stay aligned with the algebraic equations.
    block.algebraic_vars = [
        i_cap_end_f,
        i_cap_mid_1,
        i_cap_mid_2,
        i_cap_end_t,
        v_n1,
        v_n2,
        i_n1,
        i_n2,
        i_f_dc,
        i_t_dc,
        p_f,
        p_t,
    ]
    block.algebraic_eqs = [
        # Sending-end capacitor current from dq/dt with q = C * v.
        q_end_f - c_end_f * v_f_dc,
        # First distributed capacitor current from dq/dt with q = C * v.
        q_mid_1 - c_mid_1 * v_n1,
        # Second distributed capacitor current from dq/dt with q = C * v.
        q_mid_2 - c_mid_2 * v_n2,
        # Receiving-end capacitor current from dq/dt with q = C * v.
        q_end_t - c_end_t * v_t_dc,
        # Current injected at node v1 from the external power order using the local node voltage.
        i_n1 - i_n1_expr,
        # Current injected at node v2 from the external power order using the local node voltage.
        i_n2 - i_n2_expr,
        # Sending-end terminal KCL: terminal current leaves through the first series branch and local shunt.
        i_f_dc - (i_r3 + i_cap_end_f + g_damp * v_f_dc),
        # Receiving-end terminal KCL: terminal current is the last series-branch return plus local shunt.
        i_t_dc - (-i_r1 + i_cap_end_t + g_damp * v_t_dc),
        # Internal-node KCL at v1: injected current equals the left and right branch currents plus the local shunt current.
        i_n1 - (-i_r3 + i_r2 + i_cap_mid_1),
        # Internal-node KCL at v2: injected current equals the left and right branch currents plus the local shunt current.
        i_n2 - (-i_r2 + i_r1 + i_cap_mid_2),
        # Sending-end active power.
        p_f - v_f_dc * i_f_dc,
        # Receiving-end active power.
        p_t - v_t_dc * i_t_dc,
    ]

    # block.out_vars = [i_f_dc, i_t_dc, p_f, p_t]
    block.out_vars = [i_f_dc, i_t_dc]
    block.external_mapping = {
        VarPowerFlowReferenceType.Vf_dc: v_f_dc,
        VarPowerFlowReferenceType.Vt_dc: v_t_dc,
        VarPowerFlowReferenceType.Vdc: v_f_dc,
        VarPowerFlowReferenceType.If_dc: i_f_dc,
        VarPowerFlowReferenceType.It_dc: i_t_dc,
        VarPowerFlowReferenceType.Idc: i_f_dc,
        VarPowerFlowReferenceType.Pf: p_f,
        VarPowerFlowReferenceType.Pt: p_t,
    }

    block.api_obj_mapping = dict()
    block.event_dict = {
        r1: Const(0.5),
        l1: Const(0.005),
        r2: Const(0.25),
        l2: Const(0.0025),
        r3: Const(0.4),
        l3: Const(0.004),
        c_end_f: Const(150.0e-6),
        c_mid_1: Const(150.0e-6),
        c_mid_2: Const(150.0e-6),
        c_end_t: Const(150.0e-6),
        p_ext: Const(0.0),
    }

    # Initialization uses the externally mapped terminal voltages/currents/powers as anchors.
    # The internal nodes start at the terminal voltages and all shunt currents start at zero,
    # so the series currents are derived directly from the nodal KCL equations.
    block.init_eqs = {
        q_end_f: c_end_f * v_f_dc,
        q_mid_1: c_mid_1 * v_f_dc,
        q_mid_2: c_mid_2 * v_t_dc,
        q_end_t: c_end_t * v_t_dc,
        # With zero receiving-end shunt current, the last series-branch current matches the
        # receiving terminal current sign convention.
        i_r1: -i_t_dc,
        # With zero internal shunt currents, the middle branch follows from the v2-node KCL.
        i_r2: i_r1 + i_n2,
        # With zero sending-end shunt current, the first series-branch current matches the
        # sending terminal current sign convention.
        i_r3: i_f_dc,
        v_n1: v_f_dc,
        v_n2: v_t_dc,
        i_cap_end_f: c0,
        i_cap_mid_1: c0,
        i_cap_mid_2: c0,
        i_cap_end_t: c0,
        i_n1: i_n1_expr,
        i_n2: i_n2_expr,
        p_f: v_f_dc * i_f_dc,
        p_t: v_t_dc * i_t_dc,
    }

    block.diff_init_eqs = {
        d_q_end_f: i_cap_end_f,
        d_q_mid_1: i_cap_mid_1,
        d_q_mid_2: i_cap_mid_2,
        d_q_end_t: i_cap_end_t,
        d_i_r1: (v_n2 - v_t_dc - r1 * i_r1) / (l1 + eps),
        d_i_r2: (v_n1 - v_n2 - r2 * i_r2) / (l2 + eps),
        d_i_r3: (v_f_dc - v_n1 - r3 * i_r3) / (l3 + eps),
    }

    templ.block.children.append(block)
    templ.block.name = name
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars
    return templ
