# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict
import numpy as np

from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType, ParamPowerFlowReferenceType, EmtLineTypes
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Expr


class PiLineEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phN", units="", descr="Whether neutral is active.", tpe=bool, value=False),
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="name", units="", descr="Symbolic block name.", tpe=str, value="Pi"),
                TemplateProp(name="G_damp", units="pu", descr="Terminal numerical damping conductance.",
                             tpe=float, value=0.0),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        phN: bool = self.get_value("phN")
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        name: str = self.get_value("name")
        numerical_damping_conductance: float = self.get_value("G_damp")

        return get_pi_line_emt_template(
            self.vf, phN, phA, phB, phC, name, numerical_damping_conductance,
        )

def get_pi_line_emt_template(vf: VarFactory,
                             phN: bool = False,
                             phA: bool = True,
                             phB: bool = True,
                             phC: bool = True,
                             name: str = "Pi",
                             numerical_damping_conductance: float = 0.0) -> EmtModelTemplate:
    """
    Build the EMT pi-line template with explicit API-mapped parameters.

    The line connection defines which phases are physically present, while the
    EMT initializer later injects the electrical ``R``, ``Linv``, ``C`` and physical ``G``
    values through the block ``api_obj_mapping`` using the full 4x4 NABC enum
    contract.

    :param vf: EMT variable factory.
    :param phN: Bool. True if the line has neutral, else False.
    :param phA: Bool. True if the line has phase A, else False.
    :param phB: Bool. True if the line has phase B, else False.
    :param phC: Bool. True if the line has phase C, else False.
    :param name: Symbolic model name.
    :param numerical_damping_conductance: Optional terminal shunt conductance
        used for numerical damping. Defaults to zero so the EMT line and
        power-flow line have the same physical shunt.
    :return: EMT pi-line model template.
    :raises ValueError: If the line has no active phases.
    """

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LineDevice

    templ.name = name
    templ.block.name = EmtLineTypes.PI.value

    c0: Expr = vf.add_const(0.0)

    # -----------------------------
    # Phase mask from the line itself [N,A,B,C]
    # -----------------------------
    # The template phase layout must be driven exclusively by the explicit
    # phase flags of the current API. The optional ``line`` argument remains
    # only for backward compatibility with older callers.
    ph_mask: np.ndarray = np.array([
        phN,
        phA,
        phB,
        phC,
    ], dtype=bool)

    ph_labels: list[str] = list(("N", "A", "B", "C"))
    idx_global: np.ndarray = np.where(ph_mask)[0]  # indices in global NABC convention
    active_ph: list[str] = list(ph_labels[i] for i in idx_global)
    m: int = len(active_ph)

    if m == 0:
        raise ValueError(f"PI line '{name}' has no enabled phases in line.ys")

    # -----------------------------
    # Define the fixed NABC API mapping contract.
    # The initializer writes parameter values into these exact enum slots,
    # which is why the template must read them back with the same layout.
    # -----------------------------
    r_enums: list[list[ParamPowerFlowReferenceType]] = list([
        list([
            ParamPowerFlowReferenceType.Rnn, ParamPowerFlowReferenceType.Rna,
            ParamPowerFlowReferenceType.Rnb, ParamPowerFlowReferenceType.Rnc,
        ]),
        list([
            ParamPowerFlowReferenceType.Ran, ParamPowerFlowReferenceType.Raa,
            ParamPowerFlowReferenceType.Rab, ParamPowerFlowReferenceType.Rac,
        ]),
        list([
            ParamPowerFlowReferenceType.Rbn, ParamPowerFlowReferenceType.Rba,
            ParamPowerFlowReferenceType.Rbb, ParamPowerFlowReferenceType.Rbc,
        ]),
        list([
            ParamPowerFlowReferenceType.Rcn, ParamPowerFlowReferenceType.Rca,
            ParamPowerFlowReferenceType.Rcb, ParamPowerFlowReferenceType.Rcc,
        ]),
    ])
    linv_enums: list[list[ParamPowerFlowReferenceType]] = list([
        list([
            ParamPowerFlowReferenceType.Linv_nn, ParamPowerFlowReferenceType.Linv_na,
            ParamPowerFlowReferenceType.Linv_nb, ParamPowerFlowReferenceType.Linv_nc,
        ]),
        list([
            ParamPowerFlowReferenceType.Linv_an, ParamPowerFlowReferenceType.Linv_aa,
            ParamPowerFlowReferenceType.Linv_ab, ParamPowerFlowReferenceType.Linv_ac,
        ]),
        list([
            ParamPowerFlowReferenceType.Linv_bn, ParamPowerFlowReferenceType.Linv_ba,
            ParamPowerFlowReferenceType.Linv_bb, ParamPowerFlowReferenceType.Linv_bc,
        ]),
        list([
            ParamPowerFlowReferenceType.Linv_cn, ParamPowerFlowReferenceType.Linv_ca,
            ParamPowerFlowReferenceType.Linv_cb, ParamPowerFlowReferenceType.Linv_cc,
        ]),
    ])
    c_enums: list[list[ParamPowerFlowReferenceType]] = list([
        list([
            ParamPowerFlowReferenceType.Cnn, ParamPowerFlowReferenceType.Cna,
            ParamPowerFlowReferenceType.Cnb, ParamPowerFlowReferenceType.Cnc,
        ]),
        list([
            ParamPowerFlowReferenceType.Can, ParamPowerFlowReferenceType.Caa,
            ParamPowerFlowReferenceType.Cab, ParamPowerFlowReferenceType.Cac,
        ]),
        list([
            ParamPowerFlowReferenceType.Cbn, ParamPowerFlowReferenceType.Cba,
            ParamPowerFlowReferenceType.Cbb, ParamPowerFlowReferenceType.Cbc,
        ]),
        list([
            ParamPowerFlowReferenceType.Ccn, ParamPowerFlowReferenceType.Cca,
            ParamPowerFlowReferenceType.Ccb, ParamPowerFlowReferenceType.Ccc,
        ]),
    ])

    # -----------------------------
    g_enums: list[list[ParamPowerFlowReferenceType]] = list([
        list([ParamPowerFlowReferenceType.Gnn, ParamPowerFlowReferenceType.Gna, ParamPowerFlowReferenceType.Gnb, ParamPowerFlowReferenceType.Gnc]),
        list([ParamPowerFlowReferenceType.Gan, ParamPowerFlowReferenceType.Gaa, ParamPowerFlowReferenceType.Gab, ParamPowerFlowReferenceType.Gac]),
        list([ParamPowerFlowReferenceType.Gbn, ParamPowerFlowReferenceType.Gba, ParamPowerFlowReferenceType.Gbb, ParamPowerFlowReferenceType.Gbc]),
        list([ParamPowerFlowReferenceType.Gcn, ParamPowerFlowReferenceType.Gca, ParamPowerFlowReferenceType.Gcb, ParamPowerFlowReferenceType.Gcc]),
    ])

    # Create the symbolic model block first. The child owns both its equations
    # and static-parameter contract; problem assembly discovers it recursively,
    # so the wrapper must not duplicate those declarations.
    # -----------------------------
    block: Block = Block()
    # Bus ports have their own nominal bases. The physical line state uses the
    # common from reference; map only these declared slots for new PI Blocks.
    tap_from: Var = vf.add_var("vtap_f")
    tap_to: Var = vf.add_var("vtap_t")
    block.parameters[tap_from] = vf.add_const(1.0)
    block.parameters[tap_to] = vf.add_const(1.0)
    block.api_obj_mapping[ParamPowerFlowReferenceType.vtap_f] = tap_from
    block.api_obj_mapping[ParamPowerFlowReferenceType.vtap_t] = tap_to

    # -----------------------------
    # Create the symbolic parameter variables and publish them in the child API map.
    # The EMT problem writes numerical values into these variables later, so the
    # template equations must depend on the mapped variables instead of line data.
    # -----------------------------
    phases: list[str] = list(("n", "a", "b", "c"))
    i: int
    j: int
    for i in range(4):
        for j in range(4):
            var_r: Var = vf.add_var(f"R{phases[i]}{phases[j]}")
            block.api_obj_mapping[r_enums[i][j]] = var_r
            block.parameters[var_r] = vf.add_const(0.0)

            var_l: Var = vf.add_var(f"Linv_{phases[i]}{phases[j]}")
            block.api_obj_mapping[linv_enums[i][j]] = var_l
            block.parameters[var_l] = vf.add_const(0.0)

            var_c: Var = vf.add_var(f"C{phases[i]}{phases[j]}")
            block.api_obj_mapping[c_enums[i][j]] = var_c
            block.parameters[var_c] = vf.add_const(0.0)

            var_g: Var = vf.add_var(f"G{phases[i]}{phases[j]}")
            block.api_obj_mapping[g_enums[i][j]] = var_g
            block.parameters[var_g] = vf.add_const(0.0)

    # -----------------------------
    # Reduce the full mapped matrices using the physical line phase mask.
    # This cleanly separates topology from parameters: line.ys chooses the
    # active equations, while api_obj_mapping supplies the electrical values.
    # -----------------------------
    api_mapping: Dict[ParamPowerFlowReferenceType, Var] = block.api_obj_mapping
    r_full: list[list[Var]] = list()
    linv_full: list[list[Var]] = list()
    c_full: list[list[Var]] = list()
    g_full: np.ndarray = np.empty((4, 4), dtype=object)

    for i in range(4):
        r_row: list[Var] = list()
        linv_row: list[Var] = list()
        c_row: list[Var] = list()

        for j in range(4):
            r_row.append(api_mapping[r_enums[i][j]])
            linv_row.append(api_mapping[linv_enums[i][j]])
            c_row.append(api_mapping[c_enums[i][j]])
            g_full[i, j] = api_mapping[g_enums[i][j]]

        r_full.append(r_row)
        linv_full.append(linv_row)
        c_full.append(c_row)

    R_red: list[list[Var]] = list(list(r_full[i][j] for j in idx_global) for i in idx_global)
    Linv_red: list[list[Var]] = list(list(linv_full[i][j] for j in idx_global) for i in idx_global)
    C_red: list[list[Var]] = list(list(c_full[i][j] for j in idx_global) for i in idx_global)
    g_reduced: np.ndarray = g_full[np.ix_(idx_global, idx_global)]

    # -----------------------------
    # Create ONLY active terminal voltage input vars
    # -----------------------------
    vf_keys: dict[str, VarPowerFlowReferenceType] = dict({
        "N": VarPowerFlowReferenceType.vf_N,
        "A": VarPowerFlowReferenceType.vf_A,
        "B": VarPowerFlowReferenceType.vf_B,
        "C": VarPowerFlowReferenceType.vf_C,
    })
    vt_keys: dict[str, VarPowerFlowReferenceType] = dict({
        "N": VarPowerFlowReferenceType.vt_N,
        "A": VarPowerFlowReferenceType.vt_A,
        "B": VarPowerFlowReferenceType.vt_B,
        "C": VarPowerFlowReferenceType.vt_C,
    })
    if_keys: dict[str, VarPowerFlowReferenceType] = dict({
        "N": VarPowerFlowReferenceType.if_N,
        "A": VarPowerFlowReferenceType.if_A,
        "B": VarPowerFlowReferenceType.if_B,
        "C": VarPowerFlowReferenceType.if_C,
    })
    it_keys: dict[str, VarPowerFlowReferenceType] = dict({
        "N": VarPowerFlowReferenceType.it_N,
        "A": VarPowerFlowReferenceType.it_A,
        "B": VarPowerFlowReferenceType.it_B,
        "C": VarPowerFlowReferenceType.it_C,
    })

    vf_vars: list[Var] = list(vf.add_var(name=f"vf_{ph_label}", reference=vf_keys[ph_label]) for ph_label in active_ph)
    vt_vars: list[Var] = list(vf.add_var(name=f"vt_{ph_label}", reference=vt_keys[ph_label]) for ph_label in active_ph)
    # Pair voltage and current conversion so port power remains invariant.
    internal_voltage_from: np.ndarray = np.empty(m, dtype=object)
    internal_voltage_to: np.ndarray = np.empty(m, dtype=object)
    a: int
    b: int
    k: int
    phase_label: str
    for a in range(m):
        internal_voltage_from[a] = vf_vars[a] / tap_from
        internal_voltage_to[a] = vt_vars[a] / tap_to

    # d_vf_vars = [vf.add_diff_var(name=f"d_vf_{ph_label}", base_var=v_base) for ph_label, v_base in zip(active_ph, vf_vars)]
    # d_vt_vars = [vf.add_diff_var(name=f"d_vt_{ph_label}", base_var=v_base) for ph_label, v_base in zip(active_ph, vt_vars)]


    # -----------------------------
    # Create model vars
    # -----------------------------
    i_ser: list[Var] = list(vf.add_var(name=f"i_ser_{ph_label}") for ph_label in active_ph)
    q_f: list[Var] = list(vf.add_var(name=f"q_f_{ph_label}") for ph_label in active_ph)
    q_t: list[Var] = list(vf.add_var(name=f"q_t_{ph_label}") for ph_label in active_ph)
    d_vf_vars: list[Var] = list(vf.add_var(name=f"d_vf_{ph_label}") for ph_label in active_ph)
    d_vt_vars: list[Var] = list(vf.add_var(name=f"d_vt_{ph_label}") for ph_label in active_ph)

    di_ser: list[Var] = list(vf.add_diff_var(name=f"di_ser_{ph_label}", base_var=i_ser[k]) for k, ph_label in enumerate(active_ph))
    dq_f: list[Var] = list(vf.add_diff_var(name=f"dq_f_{ph_label}", base_var=q_f[k]) for k, ph_label in enumerate(active_ph))
    dq_t: list[Var] = list(vf.add_diff_var(name=f"dq_t_{ph_label}", base_var=q_t[k]) for k, ph_label in enumerate(active_ph))

    i_cap_f: list[Var] = list(vf.add_var(name=f"i_cap_f_{ph_label}") for ph_label in active_ph)
    i_cap_t: list[Var] = list(vf.add_var(name=f"i_cap_t_{ph_label}") for ph_label in active_ph)
    if_act: list[Var] = list(vf.add_var(name=f"if_{ph_label}", reference=if_keys[ph_label]) for ph_label in active_ph)
    it_act: list[Var] = list(vf.add_var(name=f"it_{ph_label}", reference=it_keys[ph_label]) for ph_label in active_ph)

    # -----------------------------
    # Build block
    # -----------------------------
    block.in_vars = vf_vars + vt_vars
    block.state_vars = i_ser + q_f + q_t
    block.diff_vars = di_ser + dq_f + dq_t
    block.algebraic_vars = i_cap_f + i_cap_t + if_act + it_act

    # -----------------------------
    # State equations
    # -----------------------------
    state_eqs: list[Expr] = list()

    for a in range(m):
        expr_rhs: Expr = c0
        for b in range(m):
            L_inv_ab: Var = Linv_red[a][b]
            term_b: Expr = internal_voltage_from[b] - internal_voltage_to[b]
            for k in range(m):
                R_bk: Var = R_red[b][k]
                term_b = term_b - R_bk * i_ser[k]
            expr_rhs = expr_rhs + L_inv_ab * term_b
        state_eqs.append(expr_rhs)

    for a in range(m):
        state_eqs.append(i_cap_f[a])
    for a in range(m):
        state_eqs.append(i_cap_t[a])

    block.state_eqs = state_eqs

    # -----------------------------
    # Algebraic equations
    # -----------------------------
    alg_eqs: list[Expr] = list()

    for a in range(m):
        rhs_q: Expr = c0
        for b in range(m):
            C_ab: Var = C_red[a][b]
            rhs_q = rhs_q + C_ab * internal_voltage_from[b]
        alg_eqs.append(q_f[a] - rhs_q)

    for a in range(m):
        rhs_q = c0
        for b in range(m):
            C_ab = C_red[a][b]
            rhs_q = rhs_q + C_ab * internal_voltage_to[b]
        alg_eqs.append(q_t[a] - rhs_q)

    G_damp: Var = vf.add_var("G_damp")
    block.parameters[G_damp] = vf.add_const(float(numerical_damping_conductance))
    # Reuse the full physical half-shunt expressions in terminal and initial equations.
    # Coupling and neutral entries follow the same active-coordinate reduction as C.
    physical_current_f: np.ndarray = np.empty(m, dtype=object)
    physical_current_t: np.ndarray = np.empty(m, dtype=object)
    for a in range(m):
        physical_current_f[a] = c0
        physical_current_t[a] = c0
        for b in range(m):
            physical_current_f[a] += g_reduced[a, b] * internal_voltage_from[b]
            physical_current_t[a] += g_reduced[a, b] * internal_voltage_to[b]
        # Numerical damping is a local port conductance, independently of the
        # physical half-shunt and its paired current transformation.
        alg_eqs.append(if_act[a] - ((i_ser[a] + i_cap_f[a] + physical_current_f[a]) / tap_from + G_damp * vf_vars[a]))
        alg_eqs.append(it_act[a] - ((-i_ser[a] + i_cap_t[a] + physical_current_t[a]) / tap_to + G_damp * vt_vars[a]))

    block.algebraic_eqs = alg_eqs
    block.out_vars = if_act + it_act

    # -----------------------------
    # External mapping
    # -----------------------------
    if_keys = dict({"N": VarPowerFlowReferenceType.if_N, "A": VarPowerFlowReferenceType.if_A, "B": VarPowerFlowReferenceType.if_B, "C": VarPowerFlowReferenceType.if_C})
    it_keys = dict({"N": VarPowerFlowReferenceType.it_N, "A": VarPowerFlowReferenceType.it_A, "B": VarPowerFlowReferenceType.it_B, "C": VarPowerFlowReferenceType.it_C})

    mapping: Dict[VarPowerFlowReferenceType, Var | None] = dict({
        if_keys["N"]: None, if_keys["A"]: None, if_keys["B"]: None, if_keys["C"]: None,
        it_keys["N"]: None, it_keys["A"]: None, it_keys["B"]: None, it_keys["C"]: None,
        vf_keys["N"]: None, vf_keys["A"]: None, vf_keys["B"]: None, vf_keys["C"]: None,
        vt_keys["N"]: None, vt_keys["A"]: None, vt_keys["B"]: None, vt_keys["C"]: None,
    })

    for k, phase_label in enumerate(active_ph):
        mapping[vf_keys[phase_label]] = vf_vars[k]
        mapping[vt_keys[phase_label]] = vt_vars[k]
        mapping[if_keys[phase_label]] = if_act[k]
        mapping[it_keys[phase_label]] = it_act[k]

    block.external_mapping = mapping

    d_vf_keys: dict[str, VarPowerFlowReferenceType] = dict({"N": VarPowerFlowReferenceType.d_v_N_f, "A": VarPowerFlowReferenceType.d_v_A_f, "B": VarPowerFlowReferenceType.d_v_B_f, "C": VarPowerFlowReferenceType.d_v_C_f})
    d_vt_keys: dict[str, VarPowerFlowReferenceType] = dict({"N": VarPowerFlowReferenceType.d_v_N_t, "A": VarPowerFlowReferenceType.d_v_A_t, "B": VarPowerFlowReferenceType.d_v_B_t, "C": VarPowerFlowReferenceType.d_v_C_t})

    for k, phase_label in enumerate(active_ph):
        block.external_mapping[d_vf_keys[phase_label]] = d_vf_vars[k]
        block.external_mapping[d_vt_keys[phase_label]] = d_vt_vars[k]
        block.event_dict[d_vf_vars[k]] = vf.add_const(None)
        block.event_dict[d_vt_vars[k]] = vf.add_const(None)

    # -----------------------------
    # Init equations
    # -----------------------------
    init_eqs: Dict[Var, Expr] = dict()

    for a in range(m):
        rhs_f: Expr = c0
        rhs_t: Expr = c0
        for b in range(m):
            C_ab = C_red[a][b]
            rhs_f += C_ab * internal_voltage_from[b]
            rhs_t += C_ab * internal_voltage_to[b]
        init_eqs[q_f[a]] = rhs_f
        init_eqs[q_t[a]] = rhs_t

    for a in range(m):
        i_ser_from: Expr = tap_from * (if_act[a] - G_damp * vf_vars[a]) - i_cap_f[a] - physical_current_f[a]
        i_ser_to: Expr = -tap_to * (it_act[a] - G_damp * vt_vars[a]) + i_cap_t[a] + physical_current_t[a]
        init_eqs[i_ser[a]] = 0.5 * (i_ser_from + i_ser_to)

    block.init_eqs = init_eqs

    # -----------------------------
    # Derivative initialization
    # -----------------------------
    diff_init_eqs: Dict[Var, Expr] = dict()

    for a in range(m):
        di_expression: Expr = c0
        for b in range(m):
            term_b = internal_voltage_from[b] - internal_voltage_to[b]
            for k in range(m):
                R_bk = R_red[b][k]
                term_b = term_b - R_bk * i_ser[k]
            coeff: Var = Linv_red[a][b]
            di_expression = di_expression + coeff * term_b
        diff_init_eqs[di_ser[a]] = di_expression

    for a in range(m):
        diff_init_eqs[dq_f[a]] = i_cap_f[a]
        diff_init_eqs[dq_t[a]] = i_cap_t[a]

    for a in range(m):
        rhs_i_cap_f: Expr = c0
        rhs_i_cap_t: Expr = c0
        for b in range(m):
            C_ab = C_red[a][b]
            rhs_i_cap_f += C_ab * d_vf_vars[b] / tap_from
            rhs_i_cap_t += C_ab * d_vt_vars[b] / tap_to
        init_eqs[i_cap_f[a]] = rhs_i_cap_f
        init_eqs[i_cap_t[a]] = rhs_i_cap_t

    block.diff_init_eqs = diff_init_eqs

    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars

    return templ
