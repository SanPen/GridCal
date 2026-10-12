# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Auxiliary algebraic EMT ZIP-load template.

The runtime equations expose powers, square roots, and divisions through
auxiliary algebraic constraints.  This is useful for symbolic/tensor processing,
but the reciprocal-voltage constraint makes the formulation auxiliary rational
rather than purely multilinear in the strict polynomial sense.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import (
    _get_active_phases,
    _get_delta_branch_specs,
    _get_phase_count_name,
    wrap_delta_referenced_load_emt_template,
    wrap_ground_referenced_load_emt_template,
)
from VeraGridEngine.Templates.Emt.load_zip_emt_template import _get_api_power_references, _get_voltage_reference
from VeraGridEngine.Utils.Symbolic.block import Expr, Var
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, ShuntConnectionType, VarPowerFlowReferenceType


def get_load_ZIP_emt_multilinear_template(
    vf: VarFactory,
    phA: bool = True,
    phB: bool = True,
    phC: bool = True,
    connection_type: ShuntConnectionType | None = None,
    name: str = "ZIP_Load_EMT_3ph_ml",
) -> EmtModelTemplate:
    """Build a ZIP load whose runtime equations avoid direct powers and division.

    The voltage magnitude, square, ZIP powers, and reciprocal-current terms are
    represented with auxiliary variables and algebraic constraints.  The current
    calculation still uses a reciprocal auxiliary variable constrained by
    ``V2_inv * (V2 + eps) = 1``, so the runtime model matches the TeX auxiliary
    rational algebraic form, not a strictly multilinear polynomial form.

    Initialization equations still use direct analytic expressions to seed the
    auxiliaries.
    """
    bus_active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    core_ph_a: bool = phA
    core_ph_b: bool = phB
    core_ph_c: bool = phC

    if connection_type == ShuntConnectionType.Delta:
        branch_specs = _get_delta_branch_specs(bus_active_phases)
        if len(branch_specs) == 0:
            raise ValueError("Delta EMT ZIP loads require at least one active delta branch")
        core_ph_a = any(branch_label == "AB" for branch_label, _, _ in branch_specs)
        core_ph_b = any(branch_label == "BC" for branch_label, _, _ in branch_specs)
        core_ph_c = any(branch_label == "CA" for branch_label, _, _ in branch_specs)

    active_phases: List[str] = _get_active_phases(phA=core_ph_a, phB=core_ph_b, phC=core_ph_c)
    phase_count: int = len(bus_active_phases)
    resolved_name: str = _get_phase_count_name(base_name="ZIP_Load_EMT_ML", phase_count=phase_count, requested_name=name)

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = resolved_name
    templ.block.name = resolved_name

    c2: Expr = vf.add_const(2.0)
    v0: Var = vf.add_var(name=f"V0")
    a1: Var = vf.add_var(name=f"a1")
    a2: Var = vf.add_var(name=f"a2")
    a3: Var = vf.add_var(name=f"a3")
    a4: Var = vf.add_var(name=f"a4")
    a5: Var = vf.add_var(name=f"a5")
    a6: Var = vf.add_var(name=f"a6")
    k_sogi: Var = vf.add_var(name=f"k_sogi")
    eps: Var = vf.add_var(name=f"eps")
    omega: Var = vf.add_var(name=f"omega")

    templ.block.event_dict[v0] = vf.add_const(float(np.sqrt(2.0)))
    templ.block.event_dict[k_sogi] = vf.add_const(float(np.sqrt(2.0)))
    templ.block.event_dict[eps] = vf.add_const(1e-12)
    templ.block.event_dict[a1] = vf.add_const(1.0)
    templ.block.event_dict[a2] = vf.add_const(0.0)
    templ.block.event_dict[a3] = vf.add_const(0.0)
    templ.block.event_dict[a4] = vf.add_const(1.0)
    templ.block.event_dict[a5] = vf.add_const(0.0)
    templ.block.event_dict[a6] = vf.add_const(0.0)
    templ.block.parameters[omega] = vf.add_const(None)

    voltage_vars: Dict[str, Var] = dict()
    voltage_derivative_vars: Dict[str, Var] = dict()
    p0_vars: Dict[str, Var] = dict()
    q0_vars: Dict[str, Var] = dict()
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

    for phase_label in active_phases:
        voltage_var: Var = vf.add_var(name=f"v_{phase_label}", reference=_get_voltage_reference(phase_label))
        voltage_derivative_var: Var = vf.add_var(name=f"d_v_{phase_label}")
        p0_var: Var = vf.add_var(name=f"P0_{phase_label}")
        q0_var: Var = vf.add_var(name=f"Q0_{phase_label}")

        templ.block.event_dict[voltage_derivative_var] = vf.add_const(None)
        # Device P/Q values establish the baseline, but load-power references
        # remain event targets throughout the EMT simulation.
        templ.block.event_dict[p0_var] = vf.add_const(None)
        templ.block.event_dict[q0_var] = vf.add_const(None)
        voltage_vars[phase_label] = voltage_var
        voltage_derivative_vars[phase_label] = voltage_derivative_var
        p0_vars[phase_label] = p0_var
        q0_vars[phase_label] = q0_var
        in_vars.append(voltage_var)

        u_var: Var = vf.add_var(name=f"u_{phase_label}")
        q_var: Var = vf.add_var(name=f"q_{phase_label}")
        d_u_var: Var = vf.add_diff_var(name=f"d_u_{phase_label}", base_var=u_var)
        d_q_var: Var = vf.add_diff_var(name=f"d_q_{phase_label}", base_var=q_var)
        state_vars.extend([u_var, q_var])
        diff_vars.extend([d_u_var, d_q_var])
        state_eqs.append(k_sogi * omega * (voltage_var - u_var) - omega * q_var)
        state_eqs.append(omega * u_var)

        u_aux: Var = vf.add_var(name=f"u_aux_{phase_label}")
        q_aux: Var = vf.add_var(name=f"q_aux_{phase_label}")
        v2_var: Var = vf.add_var(name=f"V{phase_label}2")
        vm_var: Var = vf.add_var(name=f"Vm{phase_label}")
        vm_aux: Var = vf.add_var(name=f"Vm_aux_{phase_label}")
        ratio_var: Var = vf.add_var(name=f"r{phase_label}")
        ratio_aux: Var = vf.add_var(name=f"r_aux_{phase_label}")
        p_var: Var = vf.add_var(name=f"P_{phase_label}")
        q_load_var: Var = vf.add_var(name=f"Q_{phase_label}")
        v2_inv_var: Var = vf.add_var(name=f"V{phase_label}2_inv")
        current_var: Var = vf.add_var(name=f"i_{phase_label}")

        p_vars[phase_label] = p_var
        q_load_vars[phase_label] = q_load_var
        current_vars[phase_label] = current_var
        algebraic_vars.extend([u_aux, q_aux, v2_var, vm_var, vm_aux, ratio_var, ratio_aux, p_var, q_load_var, v2_inv_var, current_var])

        v2_expr = u_var * u_aux + q_var * q_aux
        algebraic_eqs.append(u_aux - u_var)
        algebraic_eqs.append(q_aux - q_var)
        algebraic_eqs.append(v2_var - v2_expr)
        algebraic_eqs.append(vm_aux - vm_var)
        algebraic_eqs.append(vm_var * vm_aux - (v2_var + eps))
        algebraic_eqs.append(ratio_var * v0 - vm_var)
        algebraic_eqs.append(ratio_aux - ratio_var)
        algebraic_eqs.append(p_var + p0_var * (a1 * ratio_var * ratio_aux + a2 * ratio_var + a3))
        algebraic_eqs.append(q_load_var + q0_var * (a4 * ratio_var * ratio_aux + a5 * ratio_var + a6))
        algebraic_eqs.append(v2_inv_var * (v2_var + eps) - vf.add_const(1.0))
        algebraic_eqs.append(current_var + c2 * (u_var * (-p_var) + q_var * (-q_load_var)) * v2_inv_var)

        init_eqs[u_var] = voltage_var
        init_eqs[q_var] = -voltage_derivative_var / omega
        init_eqs[u_aux] = u_var
        init_eqs[q_aux] = q_var
        init_eqs[v2_var] = u_var * u_var + q_var * q_var
        init_eqs[vm_var] = sym.sqrt(v2_var + eps)
        init_eqs[vm_aux] = vm_var
        init_eqs[ratio_var] = vm_var / v0
        init_eqs[ratio_aux] = ratio_var
        init_eqs[p_var] = -(p0_var * (a1 * ratio_var * ratio_var + a2 * ratio_var + a3))
        init_eqs[q_load_var] = -(q0_var * (a4 * ratio_var * ratio_var + a5 * ratio_var + a6))
        init_eqs[v2_inv_var] = vf.add_const(1.0) / (v2_var + eps)
        init_eqs[current_var] = -c2 * (u_var * (-p_var) + q_var * (-q_load_var)) / (v2_var + eps)
        diff_init_eqs[d_u_var] = voltage_derivative_var
        diff_init_eqs[d_q_var] = omega * u_var

    if connection_type == ShuntConnectionType.Delta:
        templ.block.set_parameter_in_model(var_name=f"V0", new_value=float(np.sqrt(6.0)))

    templ.block.in_vars = in_vars
    templ.block.out_vars = list(current_vars[phase_label] for phase_label in active_phases)
    templ.block.state_vars = state_vars
    templ.block.diff_vars = diff_vars
    templ.block.state_eqs = state_eqs
    templ.block.algebraic_vars = algebraic_vars
    templ.block.algebraic_eqs = algebraic_eqs
    templ.block.init_eqs = init_eqs
    templ.block.diff_init_eqs = diff_init_eqs

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: voltage_vars.get("A", None),
        VarPowerFlowReferenceType.v_B: voltage_vars.get("B", None),
        VarPowerFlowReferenceType.v_C: voltage_vars.get("C", None),
        VarPowerFlowReferenceType.P_A: p_vars.get("A", None),
        VarPowerFlowReferenceType.Q_A: q_load_vars.get("A", None),
        VarPowerFlowReferenceType.P_B: p_vars.get("B", None),
        VarPowerFlowReferenceType.Q_B: q_load_vars.get("B", None),
        VarPowerFlowReferenceType.P_C: p_vars.get("C", None),
        VarPowerFlowReferenceType.Q_C: q_load_vars.get("C", None),
        VarPowerFlowReferenceType.i_A: current_vars.get("A", None),
        VarPowerFlowReferenceType.i_B: current_vars.get("B", None),
        VarPowerFlowReferenceType.i_C: current_vars.get("C", None),
        VarPowerFlowReferenceType.d_v_A: voltage_derivative_vars.get("A", None),
        VarPowerFlowReferenceType.d_v_B: voltage_derivative_vars.get("B", None),
        VarPowerFlowReferenceType.d_v_C: voltage_derivative_vars.get("C", None),
    }

    api_obj_mapping: Dict[ParamPowerFlowReferenceType, Var] = dict({
        ParamPowerFlowReferenceType.omega_base: omega,
    })
    for phase_label in active_phases:
        p_reference: ParamPowerFlowReferenceType
        q_reference: ParamPowerFlowReferenceType
        p_reference, q_reference = _get_api_power_references(phase_label=phase_label)
        api_obj_mapping[p_reference] = p0_vars[phase_label]
        api_obj_mapping[q_reference] = q0_vars[phase_label]
    templ.block.api_obj_mapping = api_obj_mapping

    if connection_type is None:
        return templ
    if connection_type == ShuntConnectionType.Delta:
        return wrap_delta_referenced_load_emt_template(vf=vf, core_template=templ, active_phases=bus_active_phases, name=resolved_name)
    return wrap_ground_referenced_load_emt_template(
        vf=vf,
        core_template=templ,
        active_phases=bus_active_phases,
        connection_type=connection_type,
        name=resolved_name,
    )
