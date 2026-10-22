# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Templates.Emt.vsc_gfm_emt import get_gfm_emt_template
from VeraGridEngine.Utils.Symbolic.block import find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType


class GenericEmtProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the GFM-EMT structural test
    """

    __slots__ = []


def _build_pf_consistent_bindings(name: str, phi: float = 0.0) -> Dict[str, float]:
    """
    Build a self-consistent steady-state operating point at ``t = 0``.

    The phase quantities are reconstructed from a positive-sequence
    operating point (peak phasors), so the EMT init equations and the
    instantaneous P / Q formulas match by construction.

    :param name: Suffix used by the template.
    :return: Mapping ``variable_name -> value`` covering every variable
        referenced by the init / algebraic / state equations.
    """
    omega_base: float = 2.0 * np.pi * 50.0
    R_s: float = 0.01
    X_s: float = 0.1
    Kdp: float = 0.05
    Kdq: float = 0.05
    tau_omega: float = 0.05
    tau_v: float = 0.05

    # Positive-sequence PF references that the EMT bridge populates and
    # that drive every init expression in the model.
    Vpk: float = np.sqrt(2.0) * 1.0
    Ipk: float = np.sqrt(2.0) * 0.4
    phi_v: float = 0.0
    v_dc: float = 2.0

    two_pi_over_3: float = 2.0 * np.pi / 3.0

    # Per-phase samples at t = 0 from the model's analytical sin-conv
    # formulas: v(t) = Vpk*sin(omega*t + phi_v), i(t) = Ipk*sin(omega*t
    # + phi_v + phi). ``phi`` is the bridge convention phi_I - phi_V so
    # that ``I_branch_phasor = conj(S/V)``.
    theta_i: float = phi_v + phi
    v_A: float = Vpk * np.sin(phi_v)
    v_B: float = Vpk * np.sin(phi_v - two_pi_over_3)
    v_C: float = Vpk * np.sin(phi_v + two_pi_over_3)
    i_A: float = Ipk * np.sin(theta_i)
    i_B: float = Ipk * np.sin(theta_i - two_pi_over_3)
    i_C: float = Ipk * np.sin(theta_i + two_pi_over_3)

    # Internal EMF computed analytically from the PF-positive-sequence
    # phasor relation ``E = V - Z * I_branch``.
    V_re: float = Vpk * np.cos(phi_v)
    V_im: float = Vpk * np.sin(phi_v)
    I_re: float = Ipk * np.cos(theta_i)
    I_im: float = Ipk * np.sin(theta_i)
    ZI_re: float = R_s * I_re - X_s * I_im
    ZI_im: float = R_s * I_im + X_s * I_re
    E_re: float = V_re - ZI_re
    E_im: float = V_im - ZI_im
    Epk_init: float = float(np.sqrt(E_re * E_re + E_im * E_im))
    theta: float = float(np.arctan2(E_im, E_re))
    e_A: float = Epk_init * np.sin(theta)
    e_B: float = Epk_init * np.sin(theta - two_pi_over_3)
    e_C: float = Epk_init * np.sin(theta + two_pi_over_3)

    # Total three-phase active/reactive power on the system base.
    Pe: float = -0.5 * Vpk * Ipk * np.cos(phi)
    Qe: float = 0.5 * Vpk * Ipk * np.sin(phi)

    return {
        "v_A": v_A,
        "v_B": v_B,
        "v_C": v_C,
        "v_dc": v_dc,
        "i_A": i_A,
        "i_B": i_B,
        "i_C": i_C,
        "theta": theta,
        "e_A": e_A,
        "e_B": e_B,
        "e_C": e_C,
        "Pe": Pe,
        "Qe": Qe,
        "i_dc": Pe / v_dc,
        "omega": 1.0,
        "Epk": Epk_init,
        "omega_base": omega_base,
        "R_s": R_s,
        "X_s": X_s,
        "Kdp": Kdp,
        "Kdq": Kdq,
        "tau_omega": tau_omega,
        "tau_v": tau_v,
        "omega_ref": 1.0,
        "Qf": 0.0,
        "Vpk_ref": Vpk,
        "phi_v_ref": phi_v,
        "Ipk_ref": Ipk,
        "phi_ref": phi,
        "P_ref": Pe,
        "Q_ref": Qe,
        "V_ref": Epk_init,
    }


def test_vsc_gfm_emt_template_exposes_expected_structure() -> None:
    """
    Build the EMT GFM template and check the structural surface a VSC
    device needs to consume (DeviceType, in / out vars, named states,
    algebraic vars).

    :return: None.
    """
    vf: VarFactory = VarFactory()
    templ = get_gfm_emt_template(vf=vf, name="G1")
    model = templ.block.children[0]

    assert templ.tpe == DeviceType.VscDevice
    assert [var.name for var in templ.block.in_vars] == ["v_A", "v_B", "v_C", "v_dc"]
    assert [var.name for var in templ.block.out_vars] == ["i_A", "i_B", "i_C", "i_dc"]
    assert [var.name for var in model.state_vars] == [
        "i_A",
        "i_B",
        "i_C",
        "theta",
        "omega",
        "Epk",
    ]
    expected_algebraic: List[str] = [
        "e_A",
        "e_B",
        "e_C",
        "Pe",
        "Qe",
        "i_dc",
    ]
    assert [var.name for var in model.algebraic_vars] == expected_algebraic

    for net_var in ["v_A", "v_B", "v_C", "i_A", "i_B", "i_C", "v_dc"]:
        assert find_name_in_block(net_var, templ.block) is not None

    assert templ.block.external_mapping[VarPowerFlowReferenceType.Vdc].name == "v_dc"
    assert templ.block.external_mapping[VarPowerFlowReferenceType.Qf].name == "Qf"


def test_vsc_gfm_emt_template_can_be_loaded_into_generic_problem() -> None:
    """
    Verify the template plugs into the generic EMT problem template
    and keeps static API values separate from runtime parameters.

    :return: None.
    """
    vf: VarFactory = VarFactory()
    templ = get_gfm_emt_template(vf=vf, name="VSC")
    model = templ.block.children[0]
    static_parameter_values_mapping: Dict[Var, Const] = dict()
    problem = GenericEmtProblem(
        sys_block=model,
        glob_time=vf.add_var("t_gfm_emt_case"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    runtime_parameter_names = [var.name for var in problem.get_variable_parameters()]

    for expected in ["Kdp", "Kdq"]:
        assert expected in runtime_parameter_names
    for expected in ["omega_base", "R_s", "X_s"]:
        assert expected in [var.name for var in model.parameters]
        assert expected not in runtime_parameter_names


@pytest.mark.parametrize("current_angle", [-0.4, 0.0, 0.4])
def test_vsc_gfm_emt_template_init_residual_is_small(current_angle) -> None:
    """
    Substitute a PF-consistent steady-state operating point into every
    variable of the template and check that the residual of every
    algebraic equation is essentially zero.

    :return: None.
    """
    vf: VarFactory = VarFactory()
    templ = get_gfm_emt_template(vf=vf, name="G1")
    model = templ.block.children[0]
    bindings: Dict[str, float] = _build_pf_consistent_bindings(name="G1", phi=current_angle)

    for idx, eq in enumerate(model.algebraic_eqs):
        residual: float = float(eq.eval(**bindings))
        assert abs(residual) < 1.0e-9, (
            f"algebraic_eq[{idx}] residual {residual:.3e} too large at the PF init point"
        )

    for var, init_expr in model.init_eqs.items():
        init_value: float = float(init_expr.eval(**bindings))
        binding_value: float = bindings[var.name]
        assert abs(init_value - binding_value) < 1.0e-9, (
            f"init_eqs[{var.name}] gives {init_value:.6e} but binding is {binding_value:.6e}"
        )

    d_theta_var = next(v for v in model.diff_vars if v.name == "d_theta")
    omega_base_val: float = bindings["omega_base"]
    assert abs(float(model.diff_init_eqs[d_theta_var].eval(**bindings)) - omega_base_val) < 1.0e-9


    # Evaluate the model-owned runtime reference, then use it in the actual
    # voltage-controller equation. No problem-level V_ref seed is needed.
    voltage_ref = next(var for var in model.event_dict if var.name == "V_ref")
    voltage_reference = float(model.event_dict[voltage_ref].eval(**bindings))
    np.testing.assert_allclose(voltage_reference, bindings["Epk"], rtol=0.0, atol=1e-12)
    assert abs(voltage_reference - bindings["Vpk_ref"]) > 1e-5
    bindings["V_ref"] = voltage_reference
    voltage_state_index = next(index for index, var in enumerate(model.state_vars) if var.name == "Epk")
    actual_derivative = float(model.state_eqs[voltage_state_index].eval(**bindings))
    np.testing.assert_allclose(actual_derivative, 0.0, rtol=0.0, atol=1e-12)
