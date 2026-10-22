# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Maintainable equation builders for the direct REE catalogue models.

The public modules beside this file provide the stable catalogue surface.
This module only centralises equations shared by the synchronous machines,
induction machines, loads, and turbine governors.
"""

from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_124__st_1_st_enable import build_typ_124__st_1_st_enable_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_138__1_1_st import build_typ_138__1_1_st_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_151__k_1_st import build_typ_151__k_1_st_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_169__multiply_k import build_typ_169__multiply_k_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_179__multiply_k import build_typ_179__multiply_k_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_200__1_1_s_2_x_zeta_wc_ss_wc_x_wc import build_typ_200__1_1_s_2_x_zeta_wc_ss_wc_x_wc_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_214__1_s import build_typ_214__1_s_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_298__1_stb_1_sta import build_typ_298__1_stb_1_sta_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_452__kp_1_ti_s_s_s_rst_variant import build_typ_452__kp_1_ti_s_s_s_rst_variant_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_465__kp_1_ti_s_s_s_rst_sig_hold import build_typ_465__kp_1_ti_s_s_s_rst_sig_hold_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_75__lim import build_typ_75__lim_template
from VeraGridEngine.Templates.BasicBlockCatalog.Functions.typ_76__lim_const import build_typ_76__lim_const_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp
from VeraGridEngine.Utils.Symbolic.symbolic import Comparison
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.procedural_logic import flipflop, bool_or, pickup_dropoff, ProceduralLogicBase
from VeraGridEngine.enumerations import DeviceType, InductionMachineRole


def _build_diff_vars(vf: VarFactory, state_vars: list[Var]) -> list[Var]:
    """
    Allocate derivative variables for one ordered continuous-state collection.

    :param vf: Variable factory that owns the derivative variables.
    :type vf: VarFactory
    :param state_vars: Ordered continuous-state variables.
    :type state_vars: list[Var]
    :return: Derivative variables in the same order as ``state_vars``.
    :rtype: list[Var]
    """
    diff_vars: list[Var] = list()
    state_var: Var

    # Preserve state order because solver indexing couples each derivative to this exact position.
    for state_var in state_vars:
        diff_vars.append(vf.add_diff_var(name=f"d_{state_var.name}", base_var=state_var))

    return diff_vars


def _quadratic_saturation(
    value: Expr,
    s10: Expr,
    s12: Expr,
    vf: VarFactory,
) -> Expr:
    """
    Evaluate the standard two-point quadratic saturation ``SE(value)``.

    :param value: Flux-related quantity to saturate.
    :type value: Expr
    :param s10: Saturation value measured at 1.0 pu.
    :type s10: Expr
    :param s12: Saturation value measured at 1.2 pu.
    :type s12: Expr
    :param vf: Variable factory that owns the supporting constants.
    :type vf: VarFactory
    :return: Symbolic quadratic saturation expression.
    :rtype: Expr
    """
    # Recover the quadratic coefficients from the two published saturation
    # points while guarding degenerate parameter combinations numerically.
    zero: Const = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    one: Const = vf.add_const(value=1.0)
    v12: Const = vf.add_const(value=1.2)
    root_10: Expr = sym.sqrt(sym.max(s10, zero))
    root_12: Expr = sym.sqrt(sym.max(s12, zero))
    slope: Expr = (root_12 - root_10) / (v12 - one)
    slope_safe: Expr = sym.max(slope, eps)
    intercept: Expr = one - root_10 / slope_safe
    enabled: Expr = sym.heaviside(s12 - eps) * sym.heaviside(slope - eps)
    return enabled * slope * slope * sym.max(value - intercept, zero) ** 2


def build_genrou(vf: VarFactory, name: str) -> RmsModelTemplate:
    """
    Build the six-state PSS/E GENROU round-rotor machine equations.

    :param vf: Variable factory that owns the machine symbols.
    :type vf: VarFactory
    :param name: Runtime machine name.
    :type name: str
    :return: Materialized GENROU dynamic template.
    :rtype: RmsModelTemplate
    """
    templ: RmsModelTemplate = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    id_pu: Var = vf.add_var(name=f"IdPu_{name}")
    iq_pu: Var = vf.add_var(name=f"IqPu_{name}")
    efd: Var = vf.add_var(name=f"EfdPu_{name}")
    pm: Var = vf.add_var(name=f"PmPu_{name}")

    delta: Var = vf.add_var(name=f"DeltaRad_{name}")
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    epq: Var = vf.add_var(name=f"EpqPu_{name}")
    epd: Var = vf.add_var(name=f"EpdPu_{name}")
    psikd: Var = vf.add_var(name=f"PsiKdPu_{name}")
    psikq: Var = vf.add_var(name=f"PsiKqPu_{name}")
    states: list[Var] = list((delta, omega, epq, epd, psikd, psikq))

    psi_ppd: Var = vf.add_var(name=f"PsiPPdPu_{name}")
    psi_ppq: Var = vf.add_var(name=f"PsiPPqPu_{name}")
    psi_d: Var = vf.add_var(name=f"PsiDPu_{name}")
    psi_q: Var = vf.add_var(name=f"PsiQPu_{name}")
    psi_pp: Var = vf.add_var(name=f"PsiPPPu_{name}")
    xad_ifd: Var = vf.add_var(name=f"XadIfdPu_{name}")
    xaq_ilq: Var = vf.add_var(name=f"XaqIlqPu_{name}")
    te: Var = vf.add_var(name=f"TePu_{name}")
    ud: Var = vf.add_var(name=f"UdPu_{name}")
    uq: Var = vf.add_var(name=f"UqPu_{name}")
    pe: Var = vf.add_var(name=f"PePu_{name}")

    f_hz: Var = vf.add_var(name=f"FNomHz_{name}")
    h: Var = vf.add_var(name=f"H_{name}")
    damping: Var = vf.add_var(name=f"D_{name}")
    ra: Var = vf.add_var(name=f"RaPu_{name}")
    xd: Var = vf.add_var(name=f"XdPu_{name}")
    xq: Var = vf.add_var(name=f"XqPu_{name}")
    xpd: Var = vf.add_var(name=f"XpdPu_{name}")
    xpq: Var = vf.add_var(name=f"XpqPu_{name}")
    xppd: Var = vf.add_var(name=f"XppdPu_{name}")
    xppq: Var = vf.add_var(name=f"XppqPu_{name}")
    xl: Var = vf.add_var(name=f"XlPu_{name}")
    tpd0: Var = vf.add_var(name=f"Tpd0_{name}")
    tpq0: Var = vf.add_var(name=f"Tpq0_{name}")
    tppd0: Var = vf.add_var(name=f"Tppd0_{name}")
    tppq0: Var = vf.add_var(name=f"Tppq0_{name}")
    s10: Var = vf.add_var(name=f"S10_{name}")
    s12: Var = vf.add_var(name=f"S12_{name}")
    events: dict[Var, Expr | Const] = dict()
    events[f_hz] = vf.add_const(value=50.0)
    events[h] = vf.add_const(value=3.5)
    events[damping] = vf.add_const(value=0.0)
    events[ra] = vf.add_const(value=0.0025)
    events[xd] = vf.add_const(value=1.8)
    events[xq] = vf.add_const(value=1.7)
    events[xpd] = vf.add_const(value=0.30)
    events[xpq] = vf.add_const(value=0.55)
    events[xppd] = vf.add_const(value=0.25)
    events[xppq] = vf.add_const(value=0.25)
    events[xl] = vf.add_const(value=0.20)
    events[tpd0] = vf.add_const(value=8.0)
    events[tpq0] = vf.add_const(value=0.40)
    events[tppd0] = vf.add_const(value=0.03)
    events[tppq0] = vf.add_const(value=0.05)
    events[s10] = vf.add_const(value=0.0)
    events[s12] = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    two: Const = vf.add_const(value=2.0)
    omega_b: Expr = two * vf.add_const(value=math.pi) * f_hz
    k1d: Expr = (xpd - xppd) * (xd - xpd) / sym.max((xpd - xl) ** 2, eps)
    k1q: Expr = (xpq - xppq) * (xq - xpq) / sym.max((xpq - xl) ** 2, eps)
    k3d: Expr = (xppd - xl) / sym.max(xpd - xl, eps)
    k4d: Expr = (xpd - xppd) / sym.max(xpd - xl, eps)
    k3q: Expr = (xppq - xl) / sym.max(xpq - xl, eps)
    k4q: Expr = (xpq - xppq) / sym.max(xpq - xl, eps)
    se: Expr = _quadratic_saturation(psi_pp, s10, s12, vf)

    psi_ppd_expr: Expr = epq * k3d + psikd * k4d
    psi_ppq_expr: Expr = epd * k3q + psikq * k4q
    psi_d_expr: Expr = psi_ppd - xppd * id_pu
    psi_q_expr: Expr = -psi_ppq - xppq * iq_pu
    psi_pp_expr: Expr = sym.sqrt(psi_ppd * psi_ppd + psi_ppq * psi_ppq)
    xad_expr: Expr = (
        k1d * (epq - psikd - (xpd - xl) * id_pu)
        + epq + (xd - xpd) * id_pu + se * psi_ppd
    )
    xaq_expr: Expr = (
        k1q * (epd - psikq + (xpq - xl) * iq_pu)
        + epd - (xq - xpq) * iq_pu
        + se * psi_ppq * (xq - xl) / sym.max(xd - xl, eps)
    )
    te_expr: Expr = psi_d * iq_pu - psi_q * id_pu
    ud_expr: Expr = -psi_q - ra * id_pu
    uq_expr: Expr = psi_d - ra * iq_pu
    pe_expr: Expr = ud * id_pu + uq * iq_pu

    templ.block = Block(
        state_vars=states,
        diff_vars=_build_diff_vars(vf=vf, state_vars=states),
        state_eqs=[
            omega_b * (omega - vf.add_const(value=1.0)),
            (pm - te - damping * (omega - vf.add_const(value=1.0))) / sym.max(two * h, eps),
            (efd - xad_ifd) / sym.max(tpd0, eps),
            -xaq_ilq / sym.max(tpq0, eps),
            (epq - psikd - (xpd - xl) * id_pu) / sym.max(tppd0, eps),
            (epd - psikq + (xpq - xl) * iq_pu) / sym.max(tppq0, eps),
        ],
        algebraic_vars=[psi_ppd, psi_ppq, psi_d, psi_q, psi_pp, xad_ifd, xaq_ilq, te, ud, uq, pe],
        algebraic_eqs=[
            psi_ppd - psi_ppd_expr, psi_ppq - psi_ppq_expr,
            psi_d - psi_d_expr, psi_q - psi_q_expr, psi_pp - psi_pp_expr,
            xad_ifd - xad_expr, xaq_ilq - xaq_expr, te - te_expr,
            ud - ud_expr, uq - uq_expr, pe - pe_expr,
        ],
        init_eqs={
            id_pu: vf.add_const(value=0.0), iq_pu: vf.add_const(value=0.0),
            efd: vf.add_const(value=1.0), pm: vf.add_const(value=0.0),
            delta: vf.add_const(value=0.0), omega: vf.add_const(value=1.0),
            epq: vf.add_const(value=1.0), epd: vf.add_const(value=0.0),
            psikd: vf.add_const(value=1.0), psikq: vf.add_const(value=0.0),
            psi_ppd: psi_ppd_expr, psi_ppq: psi_ppq_expr,
            psi_d: psi_d_expr, psi_q: psi_q_expr, psi_pp: psi_pp_expr,
            xad_ifd: xad_expr, xaq_ilq: xaq_expr, te: te_expr,
            ud: ud_expr, uq: uq_expr, pe: pe_expr,
        },
        event_dict=events,
        in_vars=[id_pu, iq_pu, efd, pm],
        out_vars=[ud, uq, pe, omega],
        name=name,
    )
    return templ


def build_gensal(vf: VarFactory, name: str) -> RmsModelTemplate:
    """
    Build the five-state PSS/E GENSAL salient-pole machine equations.

    :param vf: Variable factory that owns the machine symbols.
    :type vf: VarFactory
    :param name: Runtime machine name.
    :type name: str
    :return: Materialized GENSAL dynamic template.
    :rtype: RmsModelTemplate
    """
    templ: RmsModelTemplate = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    id_pu: Var = vf.add_var(name=f"IdPu_{name}")
    iq_pu: Var = vf.add_var(name=f"IqPu_{name}")
    efd: Var = vf.add_var(name=f"EfdPu_{name}")
    pm: Var = vf.add_var(name=f"PmPu_{name}")
    delta: Var = vf.add_var(name=f"DeltaRad_{name}")
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    epq: Var = vf.add_var(name=f"EpqPu_{name}")
    psikd: Var = vf.add_var(name=f"PsiKdPu_{name}")
    psi_ppq: Var = vf.add_var(name=f"PsiPPqStatePu_{name}")
    states: list[Var] = list((delta, omega, epq, psikd, psi_ppq))

    psi_ppd: Var = vf.add_var(name=f"PsiPPdPu_{name}")
    psi_d: Var = vf.add_var(name=f"PsiDPu_{name}")
    psi_q: Var = vf.add_var(name=f"PsiQPu_{name}")
    xad_ifd: Var = vf.add_var(name=f"XadIfdPu_{name}")
    te: Var = vf.add_var(name=f"TePu_{name}")
    ud: Var = vf.add_var(name=f"UdPu_{name}")
    uq: Var = vf.add_var(name=f"UqPu_{name}")
    pe: Var = vf.add_var(name=f"PePu_{name}")

    f_hz: Var = vf.add_var(name=f"FNomHz_{name}")
    h: Var = vf.add_var(name=f"H_{name}")
    damping: Var = vf.add_var(name=f"D_{name}")
    ra: Var = vf.add_var(name=f"RaPu_{name}")
    xd: Var = vf.add_var(name=f"XdPu_{name}")
    xq: Var = vf.add_var(name=f"XqPu_{name}")
    xpd: Var = vf.add_var(name=f"XpdPu_{name}")
    xppd: Var = vf.add_var(name=f"XppdPu_{name}")
    xppq: Var = vf.add_var(name=f"XppqPu_{name}")
    xl: Var = vf.add_var(name=f"XlPu_{name}")
    tpd0: Var = vf.add_var(name=f"Tpd0_{name}")
    tppd0: Var = vf.add_var(name=f"Tppd0_{name}")
    tppq0: Var = vf.add_var(name=f"Tppq0_{name}")
    s10: Var = vf.add_var(name=f"S10_{name}")
    s12: Var = vf.add_var(name=f"S12_{name}")
    events: dict[Var, Expr | Const] = dict()
    events[f_hz] = vf.add_const(value=50.0)
    events[h] = vf.add_const(value=3.5)
    events[damping] = vf.add_const(value=0.0)
    events[ra] = vf.add_const(value=0.0025)
    events[xd] = vf.add_const(value=1.8)
    events[xq] = vf.add_const(value=1.7)
    events[xpd] = vf.add_const(value=0.30)
    events[xppd] = vf.add_const(value=0.25)
    events[xppq] = vf.add_const(value=0.25)
    events[xl] = vf.add_const(value=0.20)
    events[tpd0] = vf.add_const(value=8.0)
    events[tppd0] = vf.add_const(value=0.03)
    events[tppq0] = vf.add_const(value=0.05)
    events[s10] = vf.add_const(value=0.0)
    events[s12] = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    one: Const = vf.add_const(value=1.0)
    two: Const = vf.add_const(value=2.0)
    omega_b: Expr = two * vf.add_const(value=math.pi) * f_hz
    k1d: Expr = (xpd - xppd) * (xd - xpd) / sym.max((xpd - xl) ** 2, eps)
    k3d: Expr = (xppd - xl) / sym.max(xpd - xl, eps)
    k4d: Expr = (xpd - xppd) / sym.max(xpd - xl, eps)
    se: Expr = _quadratic_saturation(epq, s10, s12, vf)
    psi_ppd_expr: Expr = epq * k3d + psikd * k4d
    psi_d_expr: Expr = psi_ppd - xppd * id_pu
    psi_q_expr: Expr = -psi_ppq - xppq * iq_pu
    xad_expr: Expr = (
        k1d * (epq - psikd - (xpd - xl) * id_pu)
        + (xd - xpd) * id_pu + (one + se) * epq
    )
    te_expr: Expr = psi_d * iq_pu - psi_q * id_pu
    ud_expr: Expr = -psi_q - ra * id_pu
    uq_expr: Expr = psi_d - ra * iq_pu
    pe_expr: Expr = ud * id_pu + uq * iq_pu
    templ.block = Block(
        state_vars=states,
        diff_vars=_build_diff_vars(vf=vf, state_vars=states),
        state_eqs=[
            omega_b * (omega - one),
            (pm - te - damping * (omega - one)) / sym.max(two * h, eps),
            (efd - xad_ifd) / sym.max(tpd0, eps),
            (epq - psikd - (xpd - xl) * id_pu) / sym.max(tppd0, eps),
            (-psi_ppq + (xq - xppq) * iq_pu) / sym.max(tppq0, eps),
        ],
        algebraic_vars=[psi_ppd, psi_d, psi_q, xad_ifd, te, ud, uq, pe],
        algebraic_eqs=[
            psi_ppd - psi_ppd_expr, psi_d - psi_d_expr,
            psi_q - psi_q_expr, xad_ifd - xad_expr, te - te_expr,
            ud - ud_expr, uq - uq_expr, pe - pe_expr,
        ],
        init_eqs={
            id_pu: vf.add_const(value=0.0), iq_pu: vf.add_const(value=0.0),
            efd: one, pm: vf.add_const(value=0.0), delta: vf.add_const(value=0.0),
            omega: one, epq: one, psikd: one, psi_ppq: vf.add_const(value=0.0),
            psi_ppd: psi_ppd_expr, psi_d: psi_d_expr, psi_q: psi_q_expr,
            xad_ifd: xad_expr, te: te_expr, ud: ud_expr, uq: uq_expr, pe: pe_expr,
        },
        event_dict=events,
        in_vars=[id_pu, iq_pu, efd, pm],
        out_vars=[ud, uq, pe, omega],
        name=name,
    )
    return templ


def build_induction_machine(
        vf: VarFactory,
        name: str,
        role: InductionMachineRole,
) -> RmsModelTemplate:
    """
    Build the shared fifth-order induction-machine equations.

    :param vf: Variable factory that owns the machine symbols.
    :type vf: VarFactory
    :param name: Runtime machine name.
    :type name: str
    :param role: Generator or motor sign and torque convention.
    :type role: InductionMachineRole
    :return: Materialized induction-machine template.
    :rtype: RmsModelTemplate
    """
    is_generator: bool = role == InductionMachineRole.GENERATOR
    templ: RmsModelTemplate = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    vd: Var = vf.add_var(name=f"VdPu_{name}")
    vq: Var = vf.add_var(name=f"VqPu_{name}")
    torque_input: Var = vf.add_var(name=f"{'TmPu' if is_generator else 'TLoad0Pu'}_{name}")
    epr: Var = vf.add_var(name=f"EprPu_{name}")
    epi: Var = vf.add_var(name=f"EpiPu_{name}")
    eppr: Var = vf.add_var(name=f"EpprPu_{name}")
    eppi: Var = vf.add_var(name=f"EppiPu_{name}")
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    states: list[Var] = list((epr, epi, eppr, eppi, omega))
    ir: Var = vf.add_var(name=f"IrPu_{name}")
    ii: Var = vf.add_var(name=f"IiPu_{name}")
    te: Var = vf.add_var(name=f"TePu_{name}")
    torque: Var = vf.add_var(name=f"{'TeGeneratorPu' if is_generator else 'TLoadPu'}_{name}")
    p: Var = vf.add_var(name=f"{'PGenPu' if is_generator else 'PLoadPu'}_{name}")
    q: Var = vf.add_var(name=f"{'QGenPu' if is_generator else 'QLoadPu'}_{name}")

    f_hz: Var = vf.add_var(name=f"FNomHz_{name}")
    ra: Var = vf.add_var(name=f"RaPu_{name}")
    xs: Var = vf.add_var(name=f"XsPu_{name}")
    xp: Var = vf.add_var(name=f"XpPu_{name}")
    xpp: Var = vf.add_var(name=f"XppPu_{name}")
    tp0: Var = vf.add_var(name=f"Tp0_{name}")
    tpp0: Var = vf.add_var(name=f"Tpp0_{name}")
    h: Var = vf.add_var(name=f"H_{name}")
    damping: Var = vf.add_var(name=f"Damp_{name}")
    events: dict[Var, Expr | Const] = dict()
    events[f_hz] = vf.add_const(value=50.0)
    events[ra] = vf.add_const(value=0.015)
    events[xs] = vf.add_const(value=3.0)
    events[xp] = vf.add_const(value=0.30)
    events[xpp] = vf.add_const(value=0.20)
    events[tp0] = vf.add_const(value=0.60)
    events[tpp0] = vf.add_const(value=0.05)
    events[h] = vf.add_const(value=0.80)
    events[damping] = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    one: Const = vf.add_const(value=1.0)
    two: Const = vf.add_const(value=2.0)
    wb: Expr = two * vf.add_const(value=math.pi) * f_hz
    slip: Expr = one - omega
    depr: Expr = wb * slip * epi - (epr + (xs - xp) * ii) / sym.max(tp0, eps)
    depi: Expr = -wb * slip * epr - (epi - (xs - xp) * ir) / sym.max(tp0, eps)
    deppr: Expr = (
        depr + wb * slip * (epi - eppi)
        - (eppr - epr + (xp - xpp) * ii) / sym.max(tpp0, eps)
    )
    deppi: Expr = (
        depi - wb * slip * (epr - eppr)
        - (eppi - epi - (xp - xpp) * ir) / sym.max(tpp0, eps)
    )
    te_motor: Expr = eppr * ir + eppi * ii
    p_motor: Expr = vd * ir + vq * ii
    q_motor: Expr = vq * ir - vd * ii
    x_sync: Expr = xs - two * xpp
    sync_den: Expr = ra * ra + x_sync * x_sync
    ir0: Expr = (-ra * vd + x_sync * vq) / sym.max(sync_den, eps)
    ii0: Expr = (-x_sync * vd - ra * vq) / sym.max(sync_den, eps)
    epr0: Expr = -(xs - xp) * ii0
    epi0: Expr = (xs - xp) * ir0
    eppr0: Expr = -(xs - xpp) * ii0
    eppi0: Expr = (xs - xpp) * ir0
    torque_expr: Expr
    p_expr: Expr
    q_expr: Expr
    domega: Expr
    if role == InductionMachineRole.GENERATOR:
        # The generator convention reports injected network power and balances
        # the mechanical input against the generated electrical torque.
        torque_expr = -te_motor
        p_expr = -p_motor
        q_expr = -q_motor
        domega = (torque_input - torque - damping * (omega - one)) / sym.max(two * h, eps)
    else:
        # Allocate motor-only coefficients inside the motor state so no optional
        # variables or impossible error state leak into the shared equations.
        a: Var = vf.add_var(name=f"A_{name}")
        b: Var = vf.add_var(name=f"B_{name}")
        d: Var = vf.add_var(name=f"D_{name}")
        exponent: Var = vf.add_var(name=f"E_{name}")
        events[a] = vf.add_const(value=0.0)
        events[b] = vf.add_const(value=0.0)
        events[d] = vf.add_const(value=0.0)
        events[exponent] = vf.add_const(value=1.0)
        c0: Expr = one - a - b - d
        torque_expr = torque_input * (a * omega ** 2 + b * omega + c0 + d * omega ** exponent)
        p_expr = p_motor
        q_expr = q_motor
        domega = (te - torque - damping * (omega - one)) / sym.max(two * h, eps)
    templ.block = Block(
        state_vars=states,
        diff_vars=_build_diff_vars(vf=vf, state_vars=states),
        state_eqs=[depr, depi, deppr, deppi, domega],
        algebraic_vars=[ir, ii, te, torque, p, q],
        algebraic_eqs=[
            vd - eppr + ra * ir - xpp * ii,
            vq - eppi + ra * ii + xpp * ir,
            te - te_motor, torque - torque_expr, p - p_expr, q - q_expr,
        ],
        init_eqs={
            vd: vf.add_const(value=0.0), vq: one,
            torque_input: vf.add_const(value=0.0),
            epr: epr0, epi: epi0, eppr: eppr0, eppi: eppi0, omega: one,
            ir: ir0, ii: ii0, te: te_motor, torque: torque_expr,
            p: p_expr, q: q_expr,
        },
        event_dict=events,
        in_vars=[vd, vq, torque_input],
        out_vars=[p, q, omega, te],
        name=name,
    )
    return templ


def build_ieel(vf: VarFactory, name: str) -> RmsModelTemplate:
    """
    Build the algebraic IEEE IEEL voltage/frequency load characteristic.

    :param vf: Variable factory that owns the load symbols.
    :type vf: VarFactory
    :param name: Runtime load name.
    :type name: str
    :return: Materialized IEEL dynamic template.
    :rtype: RmsModelTemplate
    """
    templ: RmsModelTemplate = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    voltage: Var = vf.add_var(name=f"VPu_{name}")
    frequency: Var = vf.add_var(name=f"FPu_{name}")
    p0: Var = vf.add_var(name=f"P0Pu_{name}")
    q0: Var = vf.add_var(name=f"Q0Pu_{name}")
    p: Var = vf.add_var(name=f"PLoadPu_{name}")
    q: Var = vf.add_var(name=f"QLoadPu_{name}")
    # These parameter vectors have fixed standard-defined sizes. Explicit
    # allocation makes each coefficient position directly inspectable.
    a_vars: list[Var] = list((
        vf.add_var(name=f"a1_{name}"),
        vf.add_var(name=f"a2_{name}"),
        vf.add_var(name=f"a3_{name}"),
        vf.add_var(name=f"a4_{name}"),
        vf.add_var(name=f"a5_{name}"),
        vf.add_var(name=f"a6_{name}"),
        vf.add_var(name=f"a7_{name}"),
        vf.add_var(name=f"a8_{name}"),
    ))
    n_vars: list[Var] = list((
        vf.add_var(name=f"N1_{name}"),
        vf.add_var(name=f"N2_{name}"),
        vf.add_var(name=f"N3_{name}"),
        vf.add_var(name=f"N4_{name}"),
        vf.add_var(name=f"N5_{name}"),
        vf.add_var(name=f"N6_{name}"),
    ))
    pf: Var = vf.add_var(name=f"Pf_{name}")
    events: dict[Var, Expr | Const] = dict()
    parameter_var: Var
    # Start every voltage and frequency coefficient from a neutral zero before
    # enabling the standard constant-power defaults below.
    for parameter_var in a_vars:
        events[parameter_var] = vf.add_const(value=0.0)
    for parameter_var in n_vars:
        events[parameter_var] = vf.add_const(value=0.0)
    events[a_vars[2]] = vf.add_const(value=1.0)
    events[a_vars[5]] = vf.add_const(value=1.0)
    events[pf] = vf.add_const(value=0.0)
    one: Const = vf.add_const(value=1.0)
    eps: Const = vf.add_const(value=1.0e-9)
    voltage_safe: Expr = sym.max(voltage, eps)
    p_voltage: Expr = (
        a_vars[0] * voltage_safe ** n_vars[0]
        + a_vars[1] * voltage_safe ** n_vars[1]
        + a_vars[2] * voltage_safe ** n_vars[2]
    )
    q_voltage: Expr = (
        a_vars[3] * voltage_safe ** n_vars[3]
        + a_vars[4] * voltage_safe ** n_vars[4]
        + a_vars[5] * voltage_safe ** n_vars[5]
    )
    pf_active: Expr = sym.heaviside(sym.abs(pf) - eps)
    pf_sign: Expr = sym.heaviside(pf) - sym.heaviside(-pf)
    pf_abs: Expr = sym.hard_sat(sym.abs(pf), eps, one)
    q_from_pf: Expr = pf_sign * p0 * sym.tan(sym.acos(pf_abs))
    q_reference: Expr = (one - pf_active) * q0 + pf_active * q_from_pf
    p_expr: Expr = p0 * p_voltage * (one + a_vars[6] * (frequency - one))
    q_expr: Expr = q_reference * q_voltage * (one + a_vars[7] * (frequency - one))
    templ.block = Block(
        algebraic_vars=[p, q],
        algebraic_eqs=[p - p_expr, q - q_expr],
        init_eqs={
            voltage: one, frequency: one, p0: one, q0: vf.add_const(value=0.2),
            p: p_expr, q: q_expr,
        },
        event_dict=events,
        in_vars=[voltage, frequency, p0, q0],
        out_vars=[p, q],
        name=name,
    )
    return templ


def build_tgov1(vf: VarFactory, name: str) -> RmsModelTemplate:
    """
    Build the two-state TGOV1 steam-turbine governor.

    :param vf: Variable factory that owns the governor symbols.
    :type vf: VarFactory
    :param name: Runtime governor name.
    :type name: str
    :return: Materialized TGOV1 dynamic template.
    :rtype: RmsModelTemplate
    """
    templ: RmsModelTemplate = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice
    omega: Var = vf.add_var(name=f"OmegaPu_{name}")
    pref: Var = vf.add_var(name=f"PRefPu_{name}")
    valve: Var = vf.add_var(name=f"ValvePu_{name}")
    lag: Var = vf.add_var(name=f"TurbineLagPu_{name}")
    speed_error: Var = vf.add_var(name=f"SpeedErrorPu_{name}")
    command: Var = vf.add_var(name=f"ValveCommandPu_{name}")
    pm: Var = vf.add_var(name=f"PmPu_{name}")
    r: Var = vf.add_var(name=f"R_{name}")
    t1: Var = vf.add_var(name=f"T1_{name}")
    vmax: Var = vf.add_var(name=f"Vmax_{name}")
    vmin: Var = vf.add_var(name=f"Vmin_{name}")
    t2: Var = vf.add_var(name=f"T2_{name}")
    t3: Var = vf.add_var(name=f"T3_{name}")
    dt: Var = vf.add_var(name=f"Dt_{name}")
    events: dict[Var, Expr | Const] = dict()
    events[r] = vf.add_const(value=0.05)
    events[t1] = vf.add_const(value=0.10)
    events[vmax] = vf.add_const(value=1.20)
    events[vmin] = vf.add_const(value=0.0)
    events[t2] = vf.add_const(value=0.20)
    events[t3] = vf.add_const(value=10.0)
    events[dt] = vf.add_const(value=0.0)
    eps: Const = vf.add_const(value=1.0e-9)
    one: Const = vf.add_const(value=1.0)
    speed_error_expr: Expr = omega - one
    command_expr: Expr = sym.hard_sat(pref - speed_error / sym.max(r, eps), vmin, vmax)
    lead_fraction: Expr = t2 / sym.max(t3, eps)
    pm_expr: Expr = lead_fraction * valve + (one - lead_fraction) * lag - dt * speed_error
    templ.block = Block(
        state_vars=[valve, lag],
        diff_vars=[
            vf.add_diff_var(name=f"d_{valve.name}", base_var=valve),
            vf.add_diff_var(name=f"d_{lag.name}", base_var=lag),
        ],
        state_eqs=[
            (command - valve) / sym.max(t1, eps),
            (valve - lag) / sym.max(t3, eps),
        ],
        algebraic_vars=[speed_error, command, pm],
        algebraic_eqs=[speed_error - speed_error_expr, command - command_expr, pm - pm_expr],
        init_eqs={
            omega: one, pref: vf.add_const(value=0.5), valve: vf.add_const(value=0.5),
            lag: vf.add_const(value=0.5), speed_error: vf.add_const(value=0.0),
            command: vf.add_const(value=0.5), pm: vf.add_const(value=0.5),
        },
        event_dict=events,
        in_vars=[omega, pref],
        out_vars=[pm, valve],
        name=name,
    )
    return templ


def build_generator_band_trip_relay(
        vf: VarFactory,
        name: str,
        measurement_name: str,
        lower_name: str,
        upper_name: str,
        lower_default: float,
        upper_default: float,
) -> RmsModelTemplate:
    """
    Build pickup, breaker-delay, and retained-trip stages around one admissible band.

    :param vf: Variable factory that owns the relay symbols.
    :type vf: VarFactory
    :param name: Runtime relay name.
    :type name: str
    :param measurement_name: Public measurement input name.
    :type measurement_name: str
    :param lower_name: Lower-threshold parameter name.
    :type lower_name: str
    :param upper_name: Upper-threshold parameter name.
    :type upper_name: str
    :param lower_default: Default lower threshold.
    :type lower_default: float
    :param upper_default: Default upper threshold.
    :type upper_default: float
    :return: Materialized generator trip relay.
    :rtype: RmsModelTemplate
    """
    templ: RmsModelTemplate = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    # Allocate the public measurement and relay settings before composing timing logic.
    measurement: Var = vf.add_var(name=f"{measurement_name}_{name}")
    lower: Var = vf.add_var(name=f"{lower_name}_{name}")
    upper: Var = vf.add_var(name=f"{upper_name}_{name}")
    pickup_time: Var = vf.add_var(name=f"TP_{name}")
    breaker_time: Var = vf.add_var(name=f"TB_{name}")
    manual_reset: Var = vf.add_var(name=f"ManualReset_{name}")

    pickup_mode: Var = vf.add_var(name=f"PickupMode_{name}")
    breaker_mode: Var = vf.add_var(name=f"BreakerMode_{name}")
    trip_mode: Var = vf.add_var(name=f"TripMode_{name}")

    outside_band: Var = vf.add_var(name=f"OutsideBand_{name}")
    pickup_status: Var = vf.add_var(name=f"PickupStatus_{name}")
    breaker_status: Var = vf.add_var(name=f"BreakerStatus_{name}")
    trip: Var = vf.add_var(name=f"Trip_{name}")

    zero: Const = vf.add_const(value=0.0)
    half: Const = vf.add_const(value=0.5)
    outside_expr: Expr = bool_or(measurement < lower, measurement >= upper)

    # Settings remain runtime event parameters while timer states remain procedural modes.
    event_dict: dict[Var, Expr | Const] = dict({
        lower: vf.add_const(value=lower_default),
        upper: vf.add_const(value=upper_default),
        pickup_time: vf.add_const(value=0.00005),
        breaker_time: vf.add_const(value=0.083),
        manual_reset: zero,
    })
    mode_dict: dict[Var, Expr | Const] = dict({
        pickup_mode: zero,
        breaker_mode: zero,
        trip_mode: zero,
    })
    procedural_logic: list[ProceduralLogicBase] = list([
        pickup_dropoff(
            output=pickup_mode,
            boolexpr=outside_expr,
            Tpick=pickup_time,
            Tdrop=zero,
            name=f"pickup_timer_{name}",
        ),
        pickup_dropoff(
            output=breaker_mode,
            # Arm the breaker deadline from the original threshold crossing.
            # Chaining two independent timer objects would make the second
            # stage inherit the solver's previous accepted sample time and
            # could incorrectly overlap TP and TB at an exact forced event.
            boolexpr=outside_expr,
            Tpick=pickup_time + breaker_time,
            Tdrop=zero,
            name=f"breaker_timer_{name}",
        ),
        flipflop(
            boolset=breaker_mode > half,
            boolreset=manual_reset > half,
            output=trip_mode,
            name=f"trip_latch_{name}",
        ),
    ])

    templ.block = Block(
        algebraic_vars=[outside_band, pickup_status, breaker_status, trip],
        algebraic_eqs=[
            outside_band - outside_expr,
            pickup_status - pickup_mode,
            breaker_status - breaker_mode,
            trip - trip_mode,
        ],
        init_eqs={
            measurement: vf.add_const(value=(lower_default + upper_default) / 2.0),
            outside_band: zero,
            pickup_status: zero,
            breaker_status: zero,
            trip: zero,
        },
        event_dict=event_dict,
        mode_dict=mode_dict,
        procedural_logic=procedural_logic,
        in_vars=[measurement],
        out_vars=[trip],
        name=name,
    )
    return templ


# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0




def build_scalar_gain_runtime_template(vf: VarFactory, gain_value: float, name: str) -> EmtModelTemplate:
    """
    Build one scalar gain template using the BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized gain template.
    :rtype: EmtModelTemplate
    """
    template_obj: EmtModelTemplate

    if float(gain_value) >= 0.0:
        template_obj = build_typ_179__multiply_k_template(vf=vf, name=name)
        template_obj.block.set_parameter_in_model('Multiply K__K_' + name, float(gain_value))
    else:
        template_obj = build_typ_169__multiply_k_template(vf=vf, name=name)
        template_obj.block.set_parameter_in_model('Multiply (-K)__K_' + name, abs(float(gain_value)))

    return template_obj


def _build_zero_output_runtime_template(vf: VarFactory, name: str) -> EmtModelTemplate:
    """
    Build one zero-valued source block with no external inputs.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param name: Runtime template name.
    :type name: str
    :return: Materialized zero-output template.
    :rtype: EmtModelTemplate
    """
    zero_output: Var = vf.add_var('zero_output_' + name)
    algebraic_equations: list[Expr] = list()
    algebraic_variables: list[Var] = list()
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Materialize the constant source explicitly so it can be wired into reset pins.
    algebraic_equations.append(zero_output - Const(0.0))
    algebraic_variables.append(zero_output)
    root_block.algebraic_vars = algebraic_variables
    root_block.algebraic_eqs = algebraic_equations
    root_block.out_vars = list([zero_output])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_first_order_runtime_template(
        vf: VarFactory,
        gain_value: float,
        time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> first-order` chain from BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param time_constant: First-order time constant.
    :type time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    first_order_template: EmtModelTemplate = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(time_constant))
    first_order_template.block.connect([first_order_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(first_order_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([first_order_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_second_order_runtime_template(
        vf: VarFactory,
        gain_value: float,
        wc_value: float,
        zeta_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> second-order low-pass` chain from BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param wc_value: Natural frequency parameter.
    :type wc_value: float
    :param zeta_value: Damping ratio parameter.
    :type zeta_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    second_order_template: EmtModelTemplate = build_typ_200__1_1_s_2_x_zeta_wc_ss_wc_x_wc_template(vf=vf, name=name + '_second_order')
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Configure the recovered second-order low-pass parameters first.
    second_order_template.block.set_parameter_in_model('1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__wc_' + name + '_second_order', float(wc_value))
    second_order_template.block.set_parameter_in_model('1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__zeta_' + name + '_second_order', float(zeta_value))

    if math.isclose(float(gain_value), 1.0, rel_tol=1.0e-9, abs_tol=1.0e-9):
        root_block.merge_incoming_block(second_order_template.block)
        root_block.in_vars = list([second_order_template.block.in_vars[0]])
        root_block.out_vars = list([second_order_template.block.out_vars[0]])
    else:
        gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
        second_order_template.block.connect([second_order_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
        root_block.merge_incoming_block(gain_template.block)
        root_block.merge_incoming_block(second_order_template.block)
        root_block.in_vars = list([gain_template.block.in_vars[0]])
        root_block.out_vars = list([second_order_template.block.out_vars[0]])

    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_lead_lag_then_first_order_cascade_runtime_template(
        vf: VarFactory,
        tb_value: float,
        ta_value: float,
        stage_time_constants: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one `lead-lag -> first-order cascade` chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param tb_value: Lead-lag numerator time constant.
    :type tb_value: float
    :param ta_value: Lead-lag denominator time constant.
    :type ta_value: float
    :param stage_time_constants: Ordered first-order stage time constants.
    :type stage_time_constants: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    lead_lag_template: EmtModelTemplate = build_typ_298__1_stb_1_sta_template(vf=vf, name=name + '_lead_lag')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    previous_output: Var
    stage_index: int
    stage_time_constant: float
    stage_template: EmtModelTemplate

    # Configure the leading transfer function and then append each lag stage in order.
    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Tb_' + name + '_lead_lag', float(tb_value))
    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Ta_' + name + '_lead_lag', float(ta_value))
    root_block.merge_incoming_block(lead_lag_template.block)
    previous_output = lead_lag_template.block.out_vars[0]

    for stage_index, stage_time_constant in enumerate(stage_time_constants, start=1):
        stage_template = build_typ_138__1_1_st_template(vf=vf, name=name + '_cascade_' + str(stage_index))
        stage_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_cascade_' + str(stage_index), float(stage_time_constant))
        stage_template.block.connect([stage_template.block.in_vars[0]], [previous_output])
        root_block.merge_incoming_block(stage_template.block)
        previous_output = stage_template.block.out_vars[0]

    root_block.in_vars = list([lead_lag_template.block.in_vars[0]])
    root_block.out_vars = list([previous_output])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_lead_lag_chain_runtime_template(
        vf: VarFactory,
        tb_values: tuple[float, ...],
        ta_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one sequential lead-lag chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param tb_values: Ordered numerator time constants.
    :type tb_values: tuple[float, ...]
    :param ta_values: Ordered denominator time constants.
    :type ta_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    stage_index: int
    tb_value: float
    ta_value: float
    stage_template: EmtModelTemplate
    previous_output: Var | None = None
    first_input: Var | None = None

    for stage_index, tb_value in enumerate(tb_values, start=1):
        ta_value = ta_values[stage_index - 1]
        stage_template = build_typ_298__1_stb_1_sta_template(vf=vf, name=name + '_lead_lag_' + str(stage_index))
        stage_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Tb_' + name + '_lead_lag_' + str(stage_index), float(tb_value))
        stage_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Ta_' + name + '_lead_lag_' + str(stage_index), float(ta_value))

        if previous_output is None:
            first_input = stage_template.block.in_vars[0]
        else:
            stage_template.block.connect([stage_template.block.in_vars[0]], [previous_output])

        root_block.merge_incoming_block(stage_template.block)
        previous_output = stage_template.block.out_vars[0]

    if first_input is None or previous_output is None:
        pass
    else:
        root_block.in_vars = list([first_input])
        root_block.out_vars = list([previous_output])

    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_lead_lag_runtime_template(
        vf: VarFactory,
        gain_value: float,
        tb_value: float,
        ta_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> lead-lag` chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param tb_value: Lead-lag numerator time constant.
    :type tb_value: float
    :param ta_value: Lead-lag denominator time constant.
    :type ta_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    lead_lag_template: EmtModelTemplate = build_typ_298__1_stb_1_sta_template(vf=vf, name=name + '_lead_lag')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Tb_' + name + '_lead_lag', float(tb_value))
    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Ta_' + name + '_lead_lag', float(ta_value))
    lead_lag_template.block.connect([lead_lag_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(lead_lag_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([lead_lag_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_washout_runtime_template(
        vf: VarFactory,
        gain_value: float,
        time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> washout` chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param time_constant: Washout time constant.
    :type time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    washout_template: EmtModelTemplate = build_typ_124__st_1_st_enable_template(vf=vf, name=name + '_washout')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    washout_template.block.set_parameter_in_model('sT/(1+sT) _enable__T_' + name + '_washout', float(time_constant))
    washout_template.block.connect([washout_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(washout_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([washout_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_washout_then_first_order_runtime_template(
        vf: VarFactory,
        washout_time_constant: float,
        first_order_time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `washout -> first-order` chain from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param washout_time_constant: Washout time constant.
    :type washout_time_constant: float
    :param first_order_time_constant: First-order time constant.
    :type first_order_time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    washout_template: EmtModelTemplate = build_typ_124__st_1_st_enable_template(vf=vf, name=name + '_washout')
    first_order_template: EmtModelTemplate = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    washout_template.block.set_parameter_in_model('sT/(1+sT) _enable__T_' + name + '_washout', float(washout_time_constant))
    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(first_order_time_constant))
    first_order_template.block.connect([first_order_template.block.in_vars[0]], [washout_template.block.out_vars[0]])
    root_block.merge_incoming_block(washout_template.block)
    root_block.merge_incoming_block(first_order_template.block)
    root_block.in_vars = list([washout_template.block.in_vars[0]])
    root_block.out_vars = list([first_order_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_washout_chain_then_first_order_runtime_template(
        vf: VarFactory,
        washout_time_constants: tuple[float, ...],
        first_order_time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `washout chain -> first-order` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param washout_time_constants: Ordered washout stage time constants.
    :type washout_time_constants: tuple[float, ...]
    :param first_order_time_constant: First-order time constant.
    :type first_order_time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    previous_output: Var | None = None
    first_input: Var | None = None
    stage_index: int
    washout_time_constant: float
    washout_template: EmtModelTemplate
    first_order_template: EmtModelTemplate

    for stage_index, washout_time_constant in enumerate(washout_time_constants, start=1):
        washout_template = build_typ_124__st_1_st_enable_template(vf=vf, name=name + '_washout_' + str(stage_index))
        washout_template.block.set_parameter_in_model('sT/(1+sT) _enable__T_' + name + '_washout_' + str(stage_index), float(washout_time_constant))

        if previous_output is None:
            first_input = washout_template.block.in_vars[0]
        else:
            washout_template.block.connect([washout_template.block.in_vars[0]], [previous_output])

        root_block.merge_incoming_block(washout_template.block)
        previous_output = washout_template.block.out_vars[0]

    first_order_template = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(first_order_time_constant))
    if previous_output is None:
        pass
    else:
        first_order_template.block.connect([first_order_template.block.in_vars[0]], [previous_output])
    root_block.merge_incoming_block(first_order_template.block)

    if first_input is None:
        pass
    else:
        root_block.in_vars = list([first_input])
        root_block.out_vars = list([first_order_template.block.out_vars[0]])

    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_pi_then_first_order_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        kaw_value: float,
        y_max_value: float,
        y_min_value: float,
        first_order_time_constant: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `PI -> first-order` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: PI proportional gain.
    :type kp_value: float
    :param ti_value: PI integral time constant.
    :type ti_value: float
    :param kaw_value: PI anti-windup gain.
    :type kaw_value: float
    :param y_max_value: PI upper limit.
    :type y_max_value: float
    :param y_min_value: PI lower limit.
    :type y_min_value: float
    :param first_order_time_constant: Downstream first-order time constant.
    :type first_order_time_constant: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    pi_template: EmtModelTemplate = build_limited_pi_antiwindup_runtime_template(
        vf=vf,
        kp_value=kp_value,
        ti_value=ti_value,
        kaw_value=kaw_value,
        y_max_value=y_max_value,
        y_min_value=y_min_value,
        name=name + '_pi',
    )
    first_order_template: EmtModelTemplate = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(first_order_time_constant))
    first_order_template.block.connect([first_order_template.block.in_vars[0]], [pi_template.block.out_vars[0]])
    root_block.merge_incoming_block(pi_template.block)
    root_block.merge_incoming_block(first_order_template.block)
    root_block.in_vars = list([pi_template.block.in_vars[0]])
    root_block.out_vars = list([first_order_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_pi_hold_then_lead_lag_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        tt_value: float,
        y_max_value: float,
        y_min_value: float,
        tb_value: float,
        ta_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `PI_HOLD -> lead-lag` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: Held-PI proportional gain.
    :type kp_value: float
    :param ti_value: Held-PI integral time constant.
    :type ti_value: float
    :param tt_value: Held-PI tracking time constant.
    :type tt_value: float
    :param y_max_value: Held-PI upper limit.
    :type y_max_value: float
    :param y_min_value: Held-PI lower limit.
    :type y_min_value: float
    :param tb_value: Lead-lag numerator time constant.
    :type tb_value: float
    :param ta_value: Lead-lag denominator time constant.
    :type ta_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    pi_hold_template: EmtModelTemplate = build_limited_pi_antiwindup_hold_runtime_template(
        vf=vf,
        kp_value=kp_value,
        ti_value=ti_value,
        tt_value=tt_value,
        y_max_value=y_max_value,
        y_min_value=y_min_value,
        name=name + '_pi_hold',
    )
    lead_lag_template: EmtModelTemplate = build_typ_298__1_stb_1_sta_template(vf=vf, name=name + '_lead_lag')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Tb_' + name + '_lead_lag', float(tb_value))
    lead_lag_template.block.set_parameter_in_model('(1+sTb)/(1+sTa)__Ta_' + name + '_lead_lag', float(ta_value))
    lead_lag_template.block.connect([lead_lag_template.block.in_vars[0]], [pi_hold_template.block.out_vars[0]])
    root_block.merge_incoming_block(pi_hold_template.block)
    root_block.merge_incoming_block(lead_lag_template.block)
    root_block.in_vars = list([pi_hold_template.block.in_vars[0], pi_hold_template.block.in_vars[1]])
    root_block.out_vars = list([lead_lag_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_washout_then_lead_lag_chain_runtime_template(
        vf: VarFactory,
        gain_value: float,
        washout_time_constant: float,
        tb_values: tuple[float, ...],
        ta_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> washout -> lead-lag chain` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param washout_time_constant: Washout time constant.
    :type washout_time_constant: float
    :param tb_values: Ordered lead-lag numerator time constants.
    :type tb_values: tuple[float, ...]
    :param ta_values: Ordered lead-lag denominator time constants.
    :type ta_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_washout_template: EmtModelTemplate = build_gain_then_washout_runtime_template(
        vf=vf,
        gain_value=gain_value,
        time_constant=washout_time_constant,
        name=name + '_gain_washout',
    )
    lead_lag_chain_template: EmtModelTemplate = build_lead_lag_chain_runtime_template(
        vf=vf,
        tb_values=tb_values,
        ta_values=ta_values,
        name=name + '_lead_lag_chain',
    )
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    lead_lag_chain_template.block.connect([lead_lag_chain_template.block.in_vars[0]], [gain_washout_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_washout_template.block)
    root_block.merge_incoming_block(lead_lag_chain_template.block)
    root_block.in_vars = list([gain_washout_template.block.in_vars[0]])
    root_block.out_vars = list([lead_lag_chain_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_first_order_then_gain_washout_lead_lag_chain_runtime_template(
        vf: VarFactory,
        first_order_time_constant: float,
        gain_value: float,
        washout_time_constant: float,
        tb_values: tuple[float, ...],
        ta_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one `first-order -> gain -> washout -> lead-lag chain` composite.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param first_order_time_constant: Upstream first-order time constant.
    :type first_order_time_constant: float
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param washout_time_constant: Washout time constant.
    :type washout_time_constant: float
    :param tb_values: Ordered lead-lag numerator time constants.
    :type tb_values: tuple[float, ...]
    :param ta_values: Ordered lead-lag denominator time constants.
    :type ta_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    first_order_template: EmtModelTemplate = build_typ_138__1_1_st_template(vf=vf, name=name + '_first_order')
    downstream_template: EmtModelTemplate = build_gain_then_washout_then_lead_lag_chain_runtime_template(
        vf=vf,
        gain_value=gain_value,
        washout_time_constant=washout_time_constant,
        tb_values=tb_values,
        ta_values=ta_values,
        name=name + '_downstream',
    )
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    first_order_template.block.set_parameter_in_model('1/(1+sT)__T_' + name + '_first_order', float(first_order_time_constant))
    downstream_template.block.connect([downstream_template.block.in_vars[0]], [first_order_template.block.out_vars[0]])
    root_block.merge_incoming_block(first_order_template.block)
    root_block.merge_incoming_block(downstream_template.block)
    root_block.in_vars = list([first_order_template.block.in_vars[0]])
    root_block.out_vars = list([downstream_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_lead_lag_runtime_template(
        vf: VarFactory,
        gain_value: float,
        lead_time_constant: float,
        lag_time_constant: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one limited-lead-lag wrapper from catalog primitives plus one explicit subtractor.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Wrapper gain ``K``.
    :type gain_value: float
    :param lead_time_constant: Lead time constant ``t1``.
    :type lead_time_constant: float
    :param lag_time_constant: Lag time constant ``t2``.
    :type lag_time_constant: float
    :param y_max_value: Upper output limit.
    :type y_max_value: float
    :param y_min_value: Lower output limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized limited-lead-lag template.
    :rtype: EmtModelTemplate
    """
    first_order_template: EmtModelTemplate = build_typ_151__k_1_st_template(vf=vf, name=name + '_first_order')
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_limiter')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    input_var: Var = vf.add_var('yi_' + name)
    feedback_var: Var = vf.add_var('feedback_' + name)
    denominator_value: float
    first_order_gain_value: float

    # Recover the internal first-order gain from the OpenModelica parameter identities.
    denominator_value = float(lead_time_constant) * float(gain_value)
    if math.isclose(denominator_value, 0.0, rel_tol=1.0e-9, abs_tol=1.0e-12):
        first_order_gain_value = 0.0
    else:
        first_order_gain_value = (float(lead_time_constant) - float(lag_time_constant)) / denominator_value

    first_order_template.block.set_parameter_in_model('K/(1+sT)__K_' + name + '_first_order', float(first_order_gain_value))
    first_order_template.block.set_parameter_in_model('K/(1+sT)__T_' + name + '_first_order', float(lead_time_constant))
    limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_limiter', float(y_max_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_limiter', float(y_min_value))

    # Close the feedback loop y -> first-order -> subtract -> gain -> limiter -> y.
    first_order_template.block.connect([first_order_template.block.in_vars[0]], [limiter_template.block.out_vars[0]])
    root_block.merge_incoming_block(first_order_template.block)
    root_block.algebraic_vars.append(feedback_var)
    root_block.algebraic_eqs.append(feedback_var - (input_var - first_order_template.block.out_vars[0]))
    gain_template.block.connect([gain_template.block.in_vars[0]], [feedback_var])
    limiter_template.block.connect([limiter_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(limiter_template.block)
    root_block.in_vars = list([input_var])
    root_block.out_vars = list([limiter_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_first_order_runtime_template(
        vf: VarFactory,
        gk_value: float,
        g_value: float,
        integrator_gain_value: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one limited-first-order wrapper from catalog primitives plus explicit gating algebra.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gk_value: Upstream input gain applied before feedback subtraction.
    :type gk_value: float
    :param g_value: Feedback gain applied before the limited integrator.
    :type g_value: float
    :param integrator_gain_value: Integrator gain.
    :type integrator_gain_value: float
    :param y_max_value: Upper output limit.
    :type y_max_value: float
    :param y_min_value: Lower output limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized limited-first-order template.
    :rtype: EmtModelTemplate
    """
    input_gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gk_value, name=name + '_gk')
    feedback_gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=g_value, name=name + '_g')
    integrator_template: EmtModelTemplate = build_gain_then_integrator_runtime_template(vf=vf, gain_value=integrator_gain_value, name=name + '_integrator')
    limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_limiter')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    feedback_var: Var = vf.add_var('feedback_' + name)
    gated_input_var: Var = vf.add_var('gated_input_' + name)
    upper_block_expr: Expr
    lower_block_expr: Expr
    limiter_input_var: Var = integrator_template.block.out_vars[0]
    limited_output_var: Var = limiter_template.block.out_vars[0]
    feedback_drive_var: Var = feedback_gain_template.block.out_vars[0]

    limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_limiter', float(y_max_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_limiter', float(y_min_value))

    limiter_template.block.connect([limiter_template.block.in_vars[0]], [limiter_input_var])

    # The limited-first-order wrapper subtracts the saturated output from the scaled input.
    root_block.algebraic_vars.append(feedback_var)
    root_block.algebraic_eqs.append(feedback_var - (input_gain_template.block.out_vars[0] - limited_output_var))

    # Apply the internal wiring before merging the child blocks so the merged
    # equations reference the connected variables rather than the original
    # standalone child inputs.
    feedback_gain_template.block.connect([feedback_gain_template.block.in_vars[0]], [feedback_var])

    # Freeze the integrator when the drive pushes further into an active saturation boundary.
    upper_block_expr = Comparison(lhs=feedback_drive_var, op=CmpOp.GT, rhs=0.0).to_expression() * Comparison(lhs=limiter_input_var, op=CmpOp.GE, rhs=Const(float(y_max_value))).to_expression()
    lower_block_expr = Comparison(lhs=feedback_drive_var, op=CmpOp.LT, rhs=0.0).to_expression() * Comparison(lhs=limiter_input_var, op=CmpOp.LE, rhs=Const(float(y_min_value))).to_expression()
    root_block.algebraic_vars.append(gated_input_var)
    root_block.algebraic_eqs.append(gated_input_var - ((Const(1.0) - upper_block_expr - lower_block_expr) * feedback_drive_var))
    integrator_template.block.connect([integrator_template.block.in_vars[0]], [gated_input_var])

    root_block.merge_incoming_block(input_gain_template.block)
    root_block.merge_incoming_block(feedback_gain_template.block)
    root_block.merge_incoming_block(integrator_template.block)
    root_block.merge_incoming_block(limiter_template.block)

    root_block.in_vars = list([input_gain_template.block.in_vars[0]])
    root_block.out_vars = list([limited_output_var])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_rate_limited_first_order_freeze_runtime_template(
        vf: VarFactory,
        gain_value: float,
        time_constant: float,
        dy_max_value: float,
        dy_min_value: float,
        name: str,
        include_freeze_input: bool,
) -> EmtModelTemplate:
    """
    Build one rate-limited first-order-with-freeze wrapper.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Input gain ``k``.
    :type gain_value: float
    :param time_constant: Wrapper time constant ``T``.
    :type time_constant: float
    :param dy_max_value: Upper derivative limit.
    :type dy_max_value: float
    :param dy_min_value: Lower derivative limit.
    :type dy_min_value: float
    :param name: Runtime template name.
    :type name: str
    :param include_freeze_input: Whether to expose one explicit freeze input.
    :type include_freeze_input: bool
    :return: Materialized wrapper.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    rate_limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_rate_limit')
    integrator_template: EmtModelTemplate = build_typ_214__1_s_template(vf=vf, name=name + '_integrator')
    zero_template: EmtModelTemplate | None = None
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    feedback_error_var: Var = vf.add_var('feedback_error_' + name)
    scaled_rate_var: Var = vf.add_var('scaled_rate_' + name)
    gated_rate_var: Var = vf.add_var('gated_rate_' + name)
    freeze_var: Var
    freeze_expr: Expr

    rate_limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_rate_limit', float(dy_max_value))
    rate_limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_rate_limit', float(dy_min_value))

    if include_freeze_input:
        freeze_var = vf.add_var('freeze_' + name)
        freeze_expr = freeze_var
        root_block.in_vars = list([gain_template.block.in_vars[0], freeze_var])
    else:
        zero_template = _build_zero_output_runtime_template(vf=vf, name=name + '_freeze_zero')
        freeze_expr = zero_template.block.out_vars[0]
        root_block.in_vars = list([gain_template.block.in_vars[0]])

    # Compute the first-order drive `k*u - y`, scale by `1/T`, then clamp the derivative.
    root_block.algebraic_vars.append(feedback_error_var)
    root_block.algebraic_eqs.append(feedback_error_var - (gain_template.block.out_vars[0] - integrator_template.block.out_vars[0]))
    root_block.algebraic_vars.append(scaled_rate_var)
    root_block.algebraic_eqs.append(scaled_rate_var - (feedback_error_var / Const(float(time_constant))))
    rate_limiter_template.block.connect([rate_limiter_template.block.in_vars[0]], [scaled_rate_var])

    # Freeze the state derivative whenever the external freeze signal is active.
    root_block.algebraic_vars.append(gated_rate_var)
    root_block.algebraic_eqs.append(gated_rate_var - ((Const(1.0) - freeze_expr) * rate_limiter_template.block.out_vars[0]))
    integrator_template.block.connect([integrator_template.block.in_vars[0]], [gated_rate_var])

    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(rate_limiter_template.block)
    root_block.merge_incoming_block(integrator_template.block)
    if zero_template is None:
        pass
    else:
        root_block.merge_incoming_block(zero_template.block)
    root_block.out_vars = list([integrator_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_lead_lag_chain_runtime_template(
        vf: VarFactory,
        gain_values: tuple[float, ...],
        lead_time_constants: tuple[float, ...],
        lag_time_constants: tuple[float, ...],
        y_max_values: tuple[float, ...],
        y_min_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one sequential limited-lead-lag chain from composite limited-lead-lag stages.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_values: Ordered wrapper gains.
    :type gain_values: tuple[float, ...]
    :param lead_time_constants: Ordered lead time constants.
    :type lead_time_constants: tuple[float, ...]
    :param lag_time_constants: Ordered lag time constants.
    :type lag_time_constants: tuple[float, ...]
    :param y_max_values: Ordered upper output limits.
    :type y_max_values: tuple[float, ...]
    :param y_min_values: Ordered lower output limits.
    :type y_min_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()
    previous_output: Var | None = None
    first_input: Var | None = None
    stage_index: int
    gain_value: float
    stage_template: EmtModelTemplate

    for stage_index, gain_value in enumerate(gain_values, start=1):
        stage_template = build_limited_lead_lag_runtime_template(
            vf=vf,
            gain_value=float(gain_value),
            lead_time_constant=float(lead_time_constants[stage_index - 1]),
            lag_time_constant=float(lag_time_constants[stage_index - 1]),
            y_max_value=float(y_max_values[stage_index - 1]),
            y_min_value=float(y_min_values[stage_index - 1]),
            name=name + '_limited_lead_lag_' + str(stage_index),
        )

        if previous_output is None:
            first_input = stage_template.block.in_vars[0]
        else:
            stage_template.block.connect([stage_template.block.in_vars[0]], [previous_output])

        root_block.merge_incoming_block(stage_template.block)
        previous_output = stage_template.block.out_vars[0]

    if first_input is None or previous_output is None:
        pass
    else:
        root_block.in_vars = list([first_input])
        root_block.out_vars = list([previous_output])

    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_lead_lag_chain_runtime_template(
        vf: VarFactory,
        gain_value: float,
        tb_values: tuple[float, ...],
        ta_values: tuple[float, ...],
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> lead-lag chain` composite from catalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar input gain value.
    :type gain_value: float
    :param tb_values: Ordered numerator time constants.
    :type tb_values: tuple[float, ...]
    :param ta_values: Ordered denominator time constants.
    :type ta_values: tuple[float, ...]
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    chain_template: EmtModelTemplate = build_lead_lag_chain_runtime_template(vf=vf, tb_values=tb_values, ta_values=ta_values, name=name + '_lead_lag_chain')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    chain_template.block.connect([chain_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(chain_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([chain_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_integrator_runtime_template(vf: VarFactory, gain_value: float, name: str) -> EmtModelTemplate:
    """
    Build one `gain -> integrator` chain from BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    integrator_template: EmtModelTemplate = build_typ_214__1_s_template(vf=vf, name=name + '_integrator')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    integrator_template.block.connect([integrator_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(integrator_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([integrator_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_gain_then_limiter_runtime_template(
        vf: VarFactory,
        gain_value: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one `gain -> limiter` chain from BasicBlockCatalog primitives.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param gain_value: Scalar gain value.
    :type gain_value: float
    :param y_max_value: Upper saturation limit.
    :type y_max_value: float
    :param y_min_value: Lower saturation limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized chained template.
    :rtype: EmtModelTemplate
    """
    gain_template: EmtModelTemplate = build_scalar_gain_runtime_template(vf=vf, gain_value=gain_value, name=name + '_gain')
    limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_limiter')
    root_block: Block = Block(name=name)
    output_template: EmtModelTemplate = EmtModelTemplate()

    limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_limiter', float(y_max_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_limiter', float(y_min_value))
    limiter_template.block.connect([limiter_template.block.in_vars[0]], [gain_template.block.out_vars[0]])
    root_block.merge_incoming_block(gain_template.block)
    root_block.merge_incoming_block(limiter_template.block)
    root_block.in_vars = list([gain_template.block.in_vars[0]])
    root_block.out_vars = list([limiter_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_pi_antiwindup_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        kaw_value: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one limited PI-with-antiwindup block using the shipped catalog primitive.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: Proportional gain.
    :type kp_value: float
    :param ti_value: Integral time constant.
    :type ti_value: float
    :param kaw_value: Anti-windup back-calculation gain.
    :type kaw_value: float
    :param y_max_value: Upper output limit.
    :type y_max_value: float
    :param y_min_value: Lower output limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized PI template.
    :rtype: EmtModelTemplate
    """
    pi_template: EmtModelTemplate = build_typ_452__kp_1_ti_s_s_s_rst_variant_template(vf=vf, name=name + '_pi')
    zero_template: EmtModelTemplate = _build_zero_output_runtime_template(vf=vf, name=name + '_zero')
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Configure the catalog PI block with the recovered scalar parameters.
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__Kp_' + name + '_pi', float(kp_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__Ti_' + name + '_pi', float(ti_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__Kaw_' + name + '_pi', float(kaw_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__y_max_' + name + '_pi', float(y_max_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst (variant)__y_min_' + name + '_pi', float(y_min_value))

    # Tie the reset port to zero because the imported LimPID cases do not expose reset publicly.
    pi_template.block.connect([pi_template.block.in_vars[1]], [zero_template.block.out_vars[0]])
    root_block.merge_incoming_block(zero_template.block)
    root_block.merge_incoming_block(pi_template.block)
    root_block.in_vars = list([pi_template.block.in_vars[0]])
    root_block.out_vars = list([pi_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_pi_antiwindup_hold_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        tt_value: float,
        y_max_value: float,
        y_min_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one held PI-with-antiwindup chain with an external limiter feedback path.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: Proportional gain.
    :type kp_value: float
    :param ti_value: Integral time constant.
    :type ti_value: float
    :param tt_value: Back-calculation tracking time constant.
    :type tt_value: float
    :param y_max_value: Upper output limit.
    :type y_max_value: float
    :param y_min_value: Lower output limit.
    :type y_min_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized PI-hold template.
    :rtype: EmtModelTemplate
    """
    pi_template: EmtModelTemplate = build_typ_465__kp_1_ti_s_s_s_rst_sig_hold_template(vf=vf, name=name + '_pi_hold')
    limiter_template: EmtModelTemplate = build_typ_76__lim_const_template(vf=vf, name=name + '_limiter')
    zero_template: EmtModelTemplate = _build_zero_output_runtime_template(vf=vf, name=name + '_zero')
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Configure the PI-hold primitive with the recovered controller constants.
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Kp_' + name + '_pi_hold', float(kp_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Ti_' + name + '_pi_hold', float(ti_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Tt_' + name + '_pi_hold', float(tt_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_max_' + name + '_limiter', float(y_max_value))
    limiter_template.block.set_parameter_in_model('lim_const__y_min_' + name + '_limiter', float(y_min_value))

    # Close the anti-windup loop through the limiter and ground the unused reset pins.
    pi_template.block.connect([pi_template.block.in_vars[2]], [zero_template.block.out_vars[0]])
    pi_template.block.connect([pi_template.block.in_vars[4]], [zero_template.block.out_vars[0]])
    limiter_template.block.connect([limiter_template.block.in_vars[0]], [pi_template.block.out_vars[0]])
    pi_template.block.connect([pi_template.block.in_vars[3]], [limiter_template.block.out_vars[0]])
    root_block.merge_incoming_block(zero_template.block)
    root_block.merge_incoming_block(pi_template.block)
    root_block.merge_incoming_block(limiter_template.block)
    root_block.in_vars = list([pi_template.block.in_vars[0], pi_template.block.in_vars[1]])
    root_block.out_vars = list([limiter_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template


def build_limited_pi_antiwindup_hold_variable_limit_runtime_template(
        vf: VarFactory,
        kp_value: float,
        ti_value: float,
        tt_value: float,
        name: str,
) -> EmtModelTemplate:
    """
    Build one held PI-with-antiwindup chain with variable limiter bounds.

    :param vf: Variable factory shared by the caller.
    :type vf: VarFactory
    :param kp_value: Proportional gain.
    :type kp_value: float
    :param ti_value: Integral time constant.
    :type ti_value: float
    :param tt_value: Back-calculation tracking time constant.
    :type tt_value: float
    :param name: Runtime template name.
    :type name: str
    :return: Materialized PI-hold template.
    :rtype: EmtModelTemplate
    """
    pi_template: EmtModelTemplate = build_typ_465__kp_1_ti_s_s_s_rst_sig_hold_template(vf=vf, name=name + '_pi_hold')
    limiter_template: EmtModelTemplate = build_typ_75__lim_template(vf=vf, name=name + '_limiter_var')
    zero_template: EmtModelTemplate = _build_zero_output_runtime_template(vf=vf, name=name + '_zero')
    output_template: EmtModelTemplate = EmtModelTemplate()
    root_block: Block = Block(name=name)

    # Configure the held PI primitive with the recovered scalar controller constants.
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Kp_' + name + '_pi_hold', float(kp_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Ti_' + name + '_pi_hold', float(ti_value))
    pi_template.block.set_parameter_in_model('Kp(1/Ti+s)/s (s) _rst_sig_hold__Tt_' + name + '_pi_hold', float(tt_value))

    # Close the anti-windup loop and expose the variable limiter bounds as public inputs.
    pi_template.block.connect([pi_template.block.in_vars[2]], [zero_template.block.out_vars[0]])
    pi_template.block.connect([pi_template.block.in_vars[4]], [zero_template.block.out_vars[0]])
    limiter_template.block.connect([limiter_template.block.in_vars[0]], [pi_template.block.out_vars[0]])
    pi_template.block.connect([pi_template.block.in_vars[3]], [limiter_template.block.out_vars[0]])
    root_block.merge_incoming_block(zero_template.block)
    root_block.merge_incoming_block(pi_template.block)
    root_block.merge_incoming_block(limiter_template.block)
    root_block.in_vars = list([
        pi_template.block.in_vars[0],
        pi_template.block.in_vars[1],
        limiter_template.block.in_vars[1],
        limiter_template.block.in_vars[2],
    ])
    root_block.out_vars = list([limiter_template.block.out_vars[0]])
    output_template.tpe = DeviceType.NoDevice
    output_template.name = name
    output_template.block = root_block
    return output_template
