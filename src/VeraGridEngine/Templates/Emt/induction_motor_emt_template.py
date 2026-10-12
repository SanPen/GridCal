# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""EMT induction-motor templates.

This module provides three EMT induction-motor builders that share the same
external ABC bus interface and the same load-oriented power-flow parameter
mappings. The recommended implementation is the Level-2 single-cage EMT model.

Model overview
--------------

The templates represent an induction motor as a three-phase EMT load connected
to instantaneous ABC terminal voltages. Internally, the electrical equations are
written in stationary ``alpha-beta`` coordinates through the amplitude-invariant
Clarke transform. Flux linkages are the dynamic electrical states, stator and
rotor currents are algebraic variables obtained from the inductance relations,
and the normalized rotor speed is the mechanical state.

The Level-2 model is a single-cage induction motor. It includes two stator flux
equations, two rotor flux equations, one rotor-speed swing equation, the
current-flux algebraic constraints, active/reactive power equations,
electromagnetic torque, mechanical load torque and slip. The mechanical load is
modelled as a quadratic speed-dependent torque, which is a common default for
fan- and pump-like motor loads. The sign convention at the EMT bus is load
oriented: the internal motor current absorbs power, while the exported ABC
current variables are the currents injected into the network, hence the opposite
sign in the ABC current equations.

The Level-3 model keeps the same external ABC interface but replaces the single
rotor cage with two parallel rotor cages sharing the same magnetizing branch.
This increases the fidelity of the rotor transient response while preserving the
same torque, slip, power and terminal-current conventions.

Initialization reconstructs peak phasors from the instantaneous terminal
voltages and their derivatives, converts the power-flow P/Q targets into phase
current phasors, extracts a positive-sequence equivalent operating point,
estimates a physically bounded slip and then seeds currents, fluxes, speed,
powers, electromagnetic torque and the nominal mechanical-load coefficient.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block, Expr, Var
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType


_PI: float = math.pi
_SQRT3: float = math.sqrt(3.0)
_A_POS: complex = complex(-0.5, _SQRT3 / 2.0)
_A_NEG: complex = complex(-0.5, -_SQRT3 / 2.0)


def _build_motor_external_mapping(
    v_a: Var,
    v_b: Var,
    v_c: Var,
    i_a: Var,
    i_b: Var,
    i_c: Var,
    d_v_a: Var,
    d_v_b: Var,
    d_v_c: Var,
) -> Dict[VarPowerFlowReferenceType, Var | None]:
    """Build one ABC load external mapping for the motor.

    :param v_a: Phase-A terminal voltage.
    :param v_b: Phase-B terminal voltage.
    :param v_c: Phase-C terminal voltage.
    :param i_a: Phase-A injected current.
    :param i_b: Phase-B injected current.
    :param i_c: Phase-C injected current.
    :param d_v_a: Phase-A voltage derivative.
    :param d_v_b: Phase-B voltage derivative.
    :param d_v_c: Phase-C voltage derivative.
    :return: EMT external mapping dictionary.
    """
    return dict({
        VarPowerFlowReferenceType.v_N: None,
        VarPowerFlowReferenceType.v_A: v_a,
        VarPowerFlowReferenceType.v_B: v_b,
        VarPowerFlowReferenceType.v_C: v_c,
        VarPowerFlowReferenceType.P: None,
        VarPowerFlowReferenceType.Q: None,
        VarPowerFlowReferenceType.P_N: None,
        VarPowerFlowReferenceType.Q_N: None,
        VarPowerFlowReferenceType.P_A: None,
        VarPowerFlowReferenceType.Q_A: None,
        VarPowerFlowReferenceType.P_B: None,
        VarPowerFlowReferenceType.Q_B: None,
        VarPowerFlowReferenceType.P_C: None,
        VarPowerFlowReferenceType.Q_C: None,
        VarPowerFlowReferenceType.i_N: None,
        VarPowerFlowReferenceType.i_A: i_a,
        VarPowerFlowReferenceType.i_B: i_b,
        VarPowerFlowReferenceType.i_C: i_c,
        VarPowerFlowReferenceType.phi_v: None,
        VarPowerFlowReferenceType.phi: None,
        VarPowerFlowReferenceType.Vpk: None,
        VarPowerFlowReferenceType.Ipk: None,
        VarPowerFlowReferenceType.d_v_N: None,
        VarPowerFlowReferenceType.d_v_A: d_v_a,
        VarPowerFlowReferenceType.d_v_B: d_v_b,
        VarPowerFlowReferenceType.d_v_C: d_v_c,
    })


def _build_motor_api_mapping(
    omega_base: Var,
    p0_a: Var,
    p0_b: Var,
    p0_c: Var,
    q0_a: Var,
    q0_b: Var,
    q0_c: Var,
) -> Dict[ParamPowerFlowReferenceType, Var]:
    """Build the API parameter mapping used by EMT initialization.

    :param omega_base: Electrical base speed in rad/s.
    :param p0_a: Phase-A active-power target.
    :param p0_b: Phase-B active-power target.
    :param p0_c: Phase-C active-power target.
    :param q0_a: Phase-A reactive-power target.
    :param q0_b: Phase-B reactive-power target.
    :param q0_c: Phase-C reactive-power target.
    :return: API object mapping dictionary.
    """
    return dict({
        ParamPowerFlowReferenceType.omega_base: omega_base,
        ParamPowerFlowReferenceType.Pl0_A: p0_a,
        ParamPowerFlowReferenceType.Pl0_B: p0_b,
        ParamPowerFlowReferenceType.Pl0_C: p0_c,
        ParamPowerFlowReferenceType.Ql0_A: q0_a,
        ParamPowerFlowReferenceType.Ql0_B: q0_b,
        ParamPowerFlowReferenceType.Ql0_C: q0_c,
    })


def _phase_peak_phasor(voltage_var: Var, derivative_var: Var, omega_base: Var, eps: Expr) -> Expr:
    """Return one peak complex phasor from EMT ``v`` and ``d_v`` inputs.

    :param voltage_var: Instantaneous phase voltage at ``t = 0``.
    :param derivative_var: Instantaneous voltage derivative at ``t = 0``.
    :param omega_base: Electrical base speed in rad/s.
    :param eps: Small positive denominator protection.
    :return: Complex peak phasor expression.
    """
    # Reconstruct the sinusoidal peak phasor from the initial voltage and its derivative.
    return derivative_var / (omega_base + eps) + sym.Const(complex(0.0, 1.0)) * voltage_var


def _abc_to_alpha_beta(a_val: Expr, b_val: Expr, c_val: Expr) -> Tuple[Expr, Expr]:
    """Apply the amplitude-invariant Clarke transform to one ABC triple.

    :param a_val: Phase-A value.
    :param b_val: Phase-B value.
    :param c_val: Phase-C value.
    :return: Tuple ``(alpha, beta)``.
    """
    # Convert phase-domain quantities into stationary alpha-beta axes.
    alpha_val: Expr = sym.Const(2.0 / 3.0) * (a_val - sym.Const(0.5) * b_val - sym.Const(0.5) * c_val)
    beta_val: Expr = sym.Const(1.0 / _SQRT3) * (b_val - c_val)
    return alpha_val, beta_val


def _stator_flux_peak_from_voltage_current(
    v_axis_peak: Expr,
    i_axis_peak: Expr,
    r_s: Var,
    omega_base: Var,
    eps: Expr,
) -> Expr:
    """Return one stator-flux peak phasor from the stator voltage equation.

    :param v_axis_peak: Axis voltage peak phasor.
    :param i_axis_peak: Axis current peak phasor.
    :param r_s: Stator resistance variable.
    :param omega_base: Electrical base speed in rad/s.
    :param eps: Small denominator protection.
    :return: Flux peak phasor.
    """
    # Solve the sinusoidal stator-voltage equation for the corresponding flux phasor.
    return -sym.Const(complex(0.0, 1.0)) * (v_axis_peak - r_s * i_axis_peak) / (omega_base + eps)


def _alpha_beta_to_abc(alpha_val: Expr, beta_val: Expr) -> Tuple[Expr, Expr, Expr]:
    """Return one inverse Clarke transform for three-wire ABC currents.

    :param alpha_val: Alpha-axis value.
    :param beta_val: Beta-axis value.
    :return: Tuple ``(a, b, c)``.
    """
    # Convert stationary alpha-beta currents back to a balanced three-wire ABC set.
    a_val: Expr = alpha_val
    b_val: Expr = -sym.Const(0.5) * alpha_val + sym.Const(_SQRT3 / 2.0) * beta_val
    c_val: Expr = -sym.Const(0.5) * alpha_val - sym.Const(_SQRT3 / 2.0) * beta_val
    return a_val, b_val, c_val


def _space_vector_positive_sequence(a_val: Expr, b_val: Expr, c_val: Expr) -> Expr:
    """Return one positive-sequence phase-A peak phasor estimate.

    :param a_val: Phase-A peak phasor.
    :param b_val: Phase-B peak phasor.
    :param c_val: Phase-C peak phasor.
    :return: Positive-sequence phase-A phasor.
    """
    # Extract the phase-A positive-sequence component from three phase phasors.
    return (a_val + sym.Const(_A_POS) * b_val + sym.Const(_A_NEG) * c_val) / sym.Const(3.0)


def _phase_values_from_positive_sequence(phase_a_positive_sequence: Expr) -> Tuple[Expr, Expr, Expr]:
    """Return balanced phase phasors from one phase-A positive-sequence phasor.

    :param phase_a_positive_sequence: Positive-sequence phase-A peak phasor.
    :return: Tuple ``(a, b, c)`` of balanced phase peak phasors.
    """
    # Rebuild a balanced ABC phasor set from the phase-A positive-sequence phasor.
    phase_a_value: Expr = phase_a_positive_sequence
    phase_b_value: Expr = sym.Const(_A_NEG) * phase_a_positive_sequence
    phase_c_value: Expr = sym.Const(_A_POS) * phase_a_positive_sequence
    return phase_a_value, phase_b_value, phase_c_value


def _parallel_impedance(left_impedance: Expr, right_impedance: Expr, eps: Expr) -> Expr:
    """Return the parallel combination of two impedances.

    :param left_impedance: First impedance.
    :param right_impedance: Second impedance.
    :param eps: Small denominator protection.
    :return: Parallel impedance.
    """
    # Compute the equivalent impedance of two parallel branches with denominator protection.
    return (left_impedance * right_impedance) / (left_impedance + right_impedance + sym.Const(complex(1e-9, 0.0)) + eps)


def _complex_power_from_peak_phasors(
    v_a_peak: Expr,
    v_b_peak: Expr,
    v_c_peak: Expr,
    i_a_peak: Expr,
    i_b_peak: Expr,
    i_c_peak: Expr,
) -> Expr:
    """Return total three-phase complex power from peak phasors.

    :param v_a_peak: Phase-A voltage peak phasor.
    :param v_b_peak: Phase-B voltage peak phasor.
    :param v_c_peak: Phase-C voltage peak phasor.
    :param i_a_peak: Phase-A current peak phasor.
    :param i_b_peak: Phase-B current peak phasor.
    :param i_c_peak: Phase-C current peak phasor.
    :return: Total three-phase complex power in per unit.
    """
    # Compute three-phase complex power from peak phasors; the 0.5 factor converts peak products to average power.
    return sym.Const(0.5) * (
        v_a_peak * sym.conj(i_a_peak)
        + v_b_peak * sym.conj(i_b_peak)
        + v_c_peak * sym.conj(i_c_peak)
    )


def _build_common_events(
    vf: VarFactory,
    block: Block,
    name: str,
) -> Dict[str, Var]:
    """Create the common motor parameters and their default values.

    :param vf: EMT variable factory.
    :param block: Target symbolic block.
    :param name: Symbolic suffix.
    :return: Dictionary with the created parameter variables.
    """
    parameters: Dict[str, Var] = dict()

    # Power-flow and base-frequency parameters used to seed the EMT initialization.
    parameters["omega_base"] = vf.add_var(name=f"omega_base")
    parameters["p0_a"] = vf.add_var(name=f"P0_A")
    parameters["p0_b"] = vf.add_var(name=f"P0_B")
    parameters["p0_c"] = vf.add_var(name=f"P0_C")
    parameters["q0_a"] = vf.add_var(name=f"Q0_A")
    parameters["q0_b"] = vf.add_var(name=f"Q0_B")
    parameters["q0_c"] = vf.add_var(name=f"Q0_C")

    # Common electrical, mechanical and numerical-protection parameters.
    parameters["r_s"] = vf.add_var(name=f"r_s")
    parameters["x_ls"] = vf.add_var(name=f"x_ls")
    parameters["x_m"] = vf.add_var(name=f"x_m")
    parameters["h"] = vf.add_var(name=f"H")
    parameters["d"] = vf.add_var(name=f"D")
    parameters["slip_init"] = vf.add_var(name=f"slip_init")
    parameters["slip_min"] = vf.add_var(name=f"slip_min")
    parameters["slip_max"] = vf.add_var(name=f"slip_max")
    parameters["speed_eps"] = vf.add_var(name=f"speed_eps")
    parameters["t_load_nom"] = vf.add_var(name=f"t_load_nom")

    # Default base frequency and per-phase power targets used before API values are injected.
    block.parameters[parameters["omega_base"]] = vf.add_const(2.0 * _PI * 50.0)
    block.parameters[parameters["p0_a"]] = vf.add_const(0.10 / 3.0)
    block.parameters[parameters["p0_b"]] = vf.add_const(0.10 / 3.0)
    block.parameters[parameters["p0_c"]] = vf.add_const(0.10 / 3.0)
    block.parameters[parameters["q0_a"]] = vf.add_const(0.04 / 3.0)
    block.parameters[parameters["q0_b"]] = vf.add_const(0.04 / 3.0)
    block.parameters[parameters["q0_c"]] = vf.add_const(0.04 / 3.0)
    # Default motor parameters and safeguards used by the symbolic event dictionary.
    block.event_dict[parameters["r_s"]] = vf.add_const(0.025)
    block.event_dict[parameters["x_ls"]] = vf.add_const(0.12)
    block.event_dict[parameters["x_m"]] = vf.add_const(3.0)
    block.event_dict[parameters["h"]] = vf.add_const(0.5)
    block.event_dict[parameters["d"]] = vf.add_const(0.0)
    block.event_dict[parameters["slip_init"]] = vf.add_const(0.02)
    block.event_dict[parameters["slip_min"]] = vf.add_const(1e-3)
    block.event_dict[parameters["slip_max"]] = vf.add_const(1.0)
    block.event_dict[parameters["speed_eps"]] = vf.add_const(1e-3)
    return parameters


def _set_common_block_metadata(
    templ: EmtModelTemplate,
    parameter_block: Block,
    name: str,
    v_a: Var,
    v_b: Var,
    v_c: Var,
    i_a: Var,
    i_b: Var,
    i_c: Var,
    d_v_a: Var,
    d_v_b: Var,
    d_v_c: Var,
    params: Dict[str, Var],
) -> None:
    """Publish the common load metadata for one motor template.

    :param templ: EMT template to populate.
    :param parameter_block: Child block that owns the mapped parameters.
    :param name: Template name.
    :param v_a: Phase-A voltage input.
    :param v_b: Phase-B voltage input.
    :param v_c: Phase-C voltage input.
    :param i_a: Phase-A injected current output.
    :param i_b: Phase-B injected current output.
    :param i_c: Phase-C injected current output.
    :param d_v_a: Phase-A voltage derivative input.
    :param d_v_b: Phase-B voltage derivative input.
    :param d_v_c: Phase-C voltage derivative input.
    :param params: Dictionary of common parameter variables.
    :return: None.
    """
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    templ.block.name = name
    templ.block.in_vars = [v_a, v_b, v_c]
    templ.block.out_vars = [i_a, i_b, i_c]
    templ.block.external_mapping = _build_motor_external_mapping(
        v_a=v_a,
        v_b=v_b,
        v_c=v_c,
        i_a=i_a,
        i_b=i_b,
        i_c=i_c,
        d_v_a=d_v_a,
        d_v_b=d_v_b,
        d_v_c=d_v_c,
    )
    # Store the mapping on the same block that declares the target parameters.
    # The recursive EMT mapper visits this child, so the root only needs to
    # expose the device interface and does not duplicate child-owned metadata.
    parameter_block.api_obj_mapping = _build_motor_api_mapping(
        omega_base=params["omega_base"],
        p0_a=params["p0_a"],
        p0_b=params["p0_b"],
        p0_c=params["p0_c"],
        q0_a=params["q0_a"],
        q0_b=params["q0_b"],
        q0_c=params["q0_c"],
    )


def get_induction_motor_single_cage_emt_template(
    vf: VarFactory,
    name: str = "induction_motor_emt_template",
) -> EmtModelTemplate:
    """Build the recommended Level-2 EMT single-cage induction-motor template.

    The model uses a stationary ``alpha-beta`` formulation internally so it can
    connect directly to the existing EMT ABC bus architecture while still keeping
    explicit stator and rotor electrical dynamics.

    Mechanical torque follows a quadratic speed law, which is a practical default
    for fan- and pump-like motor loads. The nominal torque coefficient is seeded
    from the electrical initial condition so the machine starts from a consistent
    operating point when power-flow data is available.

    :param vf: EMT variable factory.
    :param name: Symbolic template name.
    :return: Configured EMT template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    block: Block = Block()
    params: Dict[str, Var] = _build_common_events(vf=vf, block=block, name=name)
    r_r: Var = vf.add_var(name=f"r_r")
    x_lr: Var = vf.add_var(name=f"x_lr")
    block.event_dict[r_r] = vf.add_const(0.02)
    block.event_dict[x_lr] = vf.add_const(0.12)

    v_a: Var = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_b: Var = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_c: Var = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)
    d_v_a: Var = vf.add_var(name=f"d_v_A")
    d_v_b: Var = vf.add_var(name=f"d_v_B")
    d_v_c: Var = vf.add_var(name=f"d_v_C")
    block.event_dict[d_v_a] = vf.add_const(None)
    block.event_dict[d_v_b] = vf.add_const(None)
    block.event_dict[d_v_c] = vf.add_const(None)

    psi_s_alpha: Var = vf.add_var(name=f"psi_s_alpha")
    psi_s_beta: Var = vf.add_var(name=f"psi_s_beta")
    psi_r_alpha: Var = vf.add_var(name=f"psi_r_alpha")
    psi_r_beta: Var = vf.add_var(name=f"psi_r_beta")
    omega_r: Var = vf.add_var(name=f"omega_r")

    d_psi_s_alpha: Var = vf.add_diff_var(name=f"d_psi_s_alpha", base_var=psi_s_alpha)
    d_psi_s_beta: Var = vf.add_diff_var(name=f"d_psi_s_beta", base_var=psi_s_beta)
    d_psi_r_alpha: Var = vf.add_diff_var(name=f"d_psi_r_alpha", base_var=psi_r_alpha)
    d_psi_r_beta: Var = vf.add_diff_var(name=f"d_psi_r_beta", base_var=psi_r_beta)
    d_omega_r: Var = vf.add_diff_var(name=f"d_omega_r", base_var=omega_r)

    i_s_alpha: Var = vf.add_var(name=f"i_s_alpha")
    i_s_beta: Var = vf.add_var(name=f"i_s_beta")
    i_r_alpha: Var = vf.add_var(name=f"i_r_alpha")
    i_r_beta: Var = vf.add_var(name=f"i_r_beta")
    i_a: Var = vf.add_var(name=f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_b: Var = vf.add_var(name=f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_c: Var = vf.add_var(name=f"i_C", reference=VarPowerFlowReferenceType.i_C)
    p_motor: Var = vf.add_var(name=f"P_motor")
    q_motor: Var = vf.add_var(name=f"Q_motor")
    torque_e: Var = vf.add_var(name=f"T_e")
    torque_m: Var = vf.add_var(name=f"T_m")
    slip: Var = vf.add_var(name=f"slip")
    v_alpha: Var = vf.add_var(name=f"v_alpha")
    v_beta: Var = vf.add_var(name=f"v_beta")

    c_eps: Expr = vf.add_const(1e-9)
    c_speed_eps: Expr = params["speed_eps"]
    c_one: Expr = vf.add_const(1.0)
    c_two: Expr = vf.add_const(2.0)
    c_three_halves: Expr = vf.add_const(1.5)

    # Convert per-unit reactances into inductances in the EMT time-domain model.
    l_s: Expr = (params["x_ls"] + params["x_m"]) / (params["omega_base"] + c_eps)
    l_r: Expr = (x_lr + params["x_m"]) / (params["omega_base"] + c_eps)
    l_m: Expr = params["x_m"] / (params["omega_base"] + c_eps)

    # Determinant of the single-cage inductance matrix used to solve currents from fluxes.
    det_lr: Expr = l_s * l_r - l_m * l_m + c_eps

    # Electrical rotor speed and speed-dependent load-torque term.
    omega_r_e: Expr = params["omega_base"] * omega_r
    omega_speed_safe: Expr = sym.max(sym.abs(omega_r), c_speed_eps)
    torque_speed_term: Expr = omega_r * omega_speed_safe

    # Terminal-voltage Clarke transform and inverse Clarke transform for motor currents.
    v_alpha_expr, v_beta_expr = _abc_to_alpha_beta(v_a, v_b, v_c)
    i_a_motor_expr, i_b_motor_expr, i_c_motor_expr = _alpha_beta_to_abc(i_s_alpha, i_s_beta)

    block.in_vars = [v_a, v_b, v_c]
    block.out_vars = [i_a, i_b, i_c]

    # Dynamic states: stator flux, rotor flux and normalized mechanical speed.
    block.state_vars = [psi_s_alpha, psi_s_beta, psi_r_alpha, psi_r_beta, omega_r]
    block.diff_vars = [d_psi_s_alpha, d_psi_s_beta, d_psi_r_alpha, d_psi_r_beta, d_omega_r]
    block.state_eqs = [
        # Stator alpha-axis flux derivative: applied voltage minus stator resistive drop.
        v_alpha - params["r_s"] * i_s_alpha,
        # Stator beta-axis flux derivative: applied voltage minus stator resistive drop.
        v_beta - params["r_s"] * i_s_beta,
        # Rotor alpha-axis flux derivative with rotor resistance and speed coupling to beta flux.
        -r_r * i_r_alpha - omega_r_e * psi_r_beta,
        # Rotor beta-axis flux derivative with rotor resistance and speed coupling to alpha flux.
        -r_r * i_r_beta + omega_r_e * psi_r_alpha,
        # Mechanical swing equation: accelerating torque divided by twice the inertia constant.
        (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    ]
    block.algebraic_vars = [
        i_s_alpha,
        i_s_beta,
        i_r_alpha,
        i_r_beta,
        i_a,
        i_b,
        i_c,
        p_motor,
        q_motor,
        torque_e,
        torque_m,
        slip,
        v_alpha,
        v_beta,
    ]
    block.algebraic_eqs = [
        # Stator alpha current obtained by inverting the single-cage flux-current relation.
        i_s_alpha - (l_r * psi_s_alpha - l_m * psi_r_alpha) / det_lr,
        # Stator beta current obtained by inverting the single-cage flux-current relation.
        i_s_beta - (l_r * psi_s_beta - l_m * psi_r_beta) / det_lr,
        # Rotor alpha current obtained from the coupled stator/rotor flux equations.
        i_r_alpha - (-l_m * psi_s_alpha + l_s * psi_r_alpha) / det_lr,
        # Rotor beta current obtained from the coupled stator/rotor flux equations.
        i_r_beta - (-l_m * psi_s_beta + l_s * psi_r_beta) / det_lr,
        # Phase-A injected current uses the opposite sign of the internally absorbed motor current.
        i_a + i_a_motor_expr,
        # Phase-B injected current uses the opposite sign of the internally absorbed motor current.
        i_b + i_b_motor_expr,
        # Phase-C injected current uses the opposite sign of the internally absorbed motor current.
        i_c + i_c_motor_expr,
        # Three-phase active power absorbed by the motor in alpha-beta coordinates.
        p_motor - c_three_halves * (v_alpha * i_s_alpha + v_beta * i_s_beta),
        # Three-phase reactive power absorbed by the motor in alpha-beta coordinates.
        q_motor - c_three_halves * (v_beta * i_s_alpha - v_alpha * i_s_beta),
        # Electromagnetic torque from the stator flux-current cross product.
        torque_e - c_three_halves * params["omega_base"] * (psi_s_alpha * i_s_beta - psi_s_beta * i_s_alpha),
        # Mechanical load torque with a quadratic speed law.
        torque_m - params["t_load_nom"] * torque_speed_term,
        # Slip is one minus normalized rotor speed.
        slip - (c_one - omega_r),
        # Alpha terminal voltage is the Clarke transform of the ABC terminal voltages.
        v_alpha - v_alpha_expr,
        # Beta terminal voltage is the Clarke transform of the ABC terminal voltages.
        v_beta - v_beta_expr,
    ]




    # Build peak voltage phasors from EMT initial voltage samples and derivatives.
    v_a_peak: Expr = _phase_peak_phasor(v_a, d_v_a, params["omega_base"], c_eps)
    v_b_peak: Expr = _phase_peak_phasor(v_b, d_v_b, params["omega_base"], c_eps)
    v_c_peak: Expr = _phase_peak_phasor(v_c, d_v_c, params["omega_base"], c_eps)

    # Convert per-phase power-flow targets into complex powers and peak current phasors.
    s_a_target: Expr = params["p0_a"] + sym.Const(complex(0.0, 1.0)) * params["q0_a"]
    s_b_target: Expr = params["p0_b"] + sym.Const(complex(0.0, 1.0)) * params["q0_b"]
    s_c_target: Expr = params["p0_c"] + sym.Const(complex(0.0, 1.0)) * params["q0_c"]
    i_a_target_peak: Expr = c_two * sym.conj(s_a_target / (v_a_peak + sym.Const(complex(1e-9, 0.0))))
    i_b_target_peak: Expr = c_two * sym.conj(s_b_target / (v_b_peak + sym.Const(complex(1e-9, 0.0))))
    i_c_target_peak: Expr = c_two * sym.conj(s_c_target / (v_c_peak + sym.Const(complex(1e-9, 0.0))))

    # Positive-sequence voltage and target current used by the equivalent-circuit initializer.
    v_pos: Expr = _space_vector_positive_sequence(v_a_peak, v_b_peak, v_c_peak)
    i_pos_target: Expr = _space_vector_positive_sequence(i_a_target_peak, i_b_target_peak, i_c_target_peak)
    # Estimate the air-gap voltage, magnetizing current and rotor branch impedance from the target point.
    z_s: Expr = params["r_s"] + sym.Const(complex(0.0, 1.0)) * params["x_ls"]
    z_m: Expr = sym.Const(complex(0.0, 1.0)) * params["x_m"]
    v_airgap_target: Expr = v_pos - z_s * i_pos_target
    i_mag_target: Expr = v_airgap_target / (z_m + sym.Const(complex(1e-9, 0.0)))
    i_rotor_target_phase: Expr = i_pos_target - i_mag_target
    z_rotor_est: Expr = v_airgap_target / (i_rotor_target_phase + sym.Const(complex(1e-9, 0.0)))
    # Bound the slip inferred from the rotor resistance and estimated rotor impedance.
    slip_from_pf: Expr = sym.hard_sat(
        r_r / sym.max(sym.real(z_rotor_est), r_r / params["slip_max"]),
        params["slip_min"],
        params["slip_max"],
    )

    # Initial normalized speed follows directly from the bounded slip.
    omega_init: Expr = c_one - slip_from_pf

    # Re-evaluate the single-cage positive-sequence equivalent circuit at the bounded slip.
    z_r: Expr = r_r / sym.max(slip_from_pf, params["slip_min"]) + sym.Const(complex(0.0, 1.0)) * x_lr
    z_par: Expr = _parallel_impedance(left_impedance=z_m, right_impedance=z_r, eps=c_eps)
    z_in: Expr = z_s + z_par
    i_pos_model: Expr = v_pos / (z_in + sym.Const(complex(1e-9, 0.0)))
    v_airgap_model: Expr = v_pos - z_s * i_pos_model
    i_mag_model: Expr = v_airgap_model / (z_m + sym.Const(complex(1e-9, 0.0)))
    i_rotor_model_phase: Expr = i_pos_model - i_mag_model
    # Convert model phase phasors into alpha-beta phasors for current and flux initialization.
    i_a_peak, i_b_peak, i_c_peak = _phase_values_from_positive_sequence(i_pos_model)
    i_r_a_peak, i_r_b_peak, i_r_c_peak = _phase_values_from_positive_sequence(i_rotor_model_phase)
    i_s_alpha_peak, i_s_beta_peak = _abc_to_alpha_beta(i_a_peak, i_b_peak, i_c_peak)
    i_r_alpha_peak, i_r_beta_peak = _abc_to_alpha_beta(i_r_a_peak, i_r_b_peak, i_r_c_peak)
    v_alpha_peak, v_beta_peak = _abc_to_alpha_beta(v_a_peak, v_b_peak, v_c_peak)
    psi_s_alpha_peak: Expr = _stator_flux_peak_from_voltage_current(
        v_axis_peak=v_alpha_peak,
        i_axis_peak=i_s_alpha_peak,
        r_s=params["r_s"],
        omega_base=params["omega_base"],
        eps=c_eps,
    )
    psi_s_beta_peak: Expr = _stator_flux_peak_from_voltage_current(
        v_axis_peak=v_beta_peak,
        i_axis_peak=i_s_beta_peak,
        r_s=params["r_s"],
        omega_base=params["omega_base"],
        eps=c_eps,
    )
    # Adjust rotor current phasors so that they are exactly consistent with the initialized stator fluxes.
    i_r_alpha_peak = (psi_s_alpha_peak - l_s * i_s_alpha_peak) / (l_m + c_eps)
    i_r_beta_peak = (psi_s_beta_peak - l_s * i_s_beta_peak) / (l_m + c_eps)

    # Rotor flux phasors follow from the single-cage inductance equations.
    psi_r_alpha_peak: Expr = l_m * i_s_alpha_peak + l_r * i_r_alpha_peak
    psi_r_beta_peak: Expr = l_m * i_s_beta_peak + l_r * i_r_beta_peak

    # Initial complex power reported by the motor from initialized voltage and current phasors.
    s_motor_init: Expr = _complex_power_from_peak_phasors(
        v_a_peak=v_a_peak,
        v_b_peak=v_b_peak,
        v_c_peak=v_c_peak,
        i_a_peak=i_a_peak,
        i_b_peak=i_b_peak,
        i_c_peak=i_c_peak,
    )

    # Runtime parameters own their initialization expressions directly.
    block.event_dict[params["t_load_nom"]] = (
        torque_e - params["d"] * (omega_r - c_one)
    ) / sym.max(omega_r * sym.abs(omega_r), c_speed_eps * c_speed_eps)

    block.init_eqs = dict({
        # Initialize transformed terminal voltages from the same Clarke equations used during simulation.
        v_alpha: v_alpha_expr,
        v_beta: v_beta_expr,
        # Initialize stator currents from the imaginary part of the steady-state peak phasors.
        i_s_alpha: sym.imag(i_s_alpha_peak),
        i_s_beta: sym.imag(i_s_beta_peak),
        # Initialize rotor currents from flux-consistent rotor current phasors.
        i_r_alpha: sym.imag(i_r_alpha_peak),
        i_r_beta: sym.imag(i_r_beta_peak),
        # Initialize network-injected phase currents with the load sign convention.
        i_a: -sym.imag(i_a_peak),
        i_b: -sym.imag(i_b_peak),
        i_c: -sym.imag(i_c_peak),
        # Initialize stator and rotor flux states from the steady-state phasors.
        psi_s_alpha: sym.imag(psi_s_alpha_peak),
        psi_s_beta: sym.imag(psi_s_beta_peak),
        psi_r_alpha: sym.imag(psi_r_alpha_peak),
        psi_r_beta: sym.imag(psi_r_beta_peak),
        # Initialize speed, slip and reported powers from the equivalent-circuit operating point.
        omega_r: omega_init,
        slip: c_one - omega_r,
        p_motor: sym.real(s_motor_init),
        q_motor: sym.imag(s_motor_init),
        # Initialize electromagnetic torque from the same torque equation used in the algebraic model.
        torque_e: c_three_halves * params["omega_base"] * (psi_s_alpha * i_s_beta - psi_s_beta * i_s_alpha),
        # Initialize mechanical torque from the nominal load coefficient and speed law.
        torque_m: params["t_load_nom"] * torque_speed_term,
    })
    block.diff_init_eqs = dict({
        # Initial stator alpha flux derivative for the DAE initializer.
        d_psi_s_alpha: v_alpha - params["r_s"] * i_s_alpha,
        # Initial stator beta flux derivative for the DAE initializer.
        d_psi_s_beta: v_beta - params["r_s"] * i_s_beta,
        # Initial rotor alpha flux derivative for the DAE initializer.
        d_psi_r_alpha: -r_r * i_r_alpha - omega_r_e * psi_r_beta,
        # Initial rotor beta flux derivative for the DAE initializer.
        d_psi_r_beta: -r_r * i_r_beta + omega_r_e * psi_r_alpha,
        # Initial rotor-speed derivative from the mechanical swing equation.
        d_omega_r: (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    })

    
    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars
    _set_common_block_metadata(
        templ=templ,
        parameter_block=block,
        name=name,
        v_a=v_a,
        v_b=v_b,
        v_c=v_c,
        i_a=i_a,
        i_b=i_b,
        i_c=i_c,
        d_v_a=d_v_a,
        d_v_b=d_v_b,
        d_v_c=d_v_c,
        params=params,
    )
    return templ


def get_induction_motor_double_cage_emt_template(
    vf: VarFactory,
    name: str = "induction_motor_double_cage_emt_template",
) -> EmtModelTemplate:
    """Build the Level-3 EMT double-cage induction-motor template.

    This model keeps the same ABC EMT terminal interface as the Level-2 block,
    but it splits the rotor current into two parallel cages that share one common
    magnetizing branch. The resulting model is better suited to capture high
    inrush current and deep-bar behaviour during startup.

    The initialization is intentionally conservative: it uses the power-flow
    target to seed the stator current and then distributes the rotor current
    between cages according to their impedances at the estimated slip.

    :param vf: EMT variable factory.
    :param name: Symbolic template name.
    :return: Configured EMT template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    block: Block = Block()
    params: Dict[str, Var] = _build_common_events(vf=vf, block=block, name=name)
    r_r1: Var = vf.add_var(name=f"r_r1")
    x_lr1: Var = vf.add_var(name=f"x_lr1")
    r_r2: Var = vf.add_var(name=f"r_r2")
    x_lr2: Var = vf.add_var(name=f"x_lr2")
    block.event_dict[r_r1] = vf.add_const(0.025)
    block.event_dict[x_lr1] = vf.add_const(0.10)
    block.event_dict[r_r2] = vf.add_const(0.080)
    block.event_dict[x_lr2] = vf.add_const(0.35)

    v_a: Var = vf.add_var(name=f"v_A", reference=VarPowerFlowReferenceType.v_A)
    v_b: Var = vf.add_var(name=f"v_B", reference=VarPowerFlowReferenceType.v_B)
    v_c: Var = vf.add_var(name=f"v_C", reference=VarPowerFlowReferenceType.v_C)
    d_v_a: Var = vf.add_var(name=f"d_v_A")
    d_v_b: Var = vf.add_var(name=f"d_v_B")
    d_v_c: Var = vf.add_var(name=f"d_v_C")
    block.event_dict[d_v_a] = vf.add_const(None)
    block.event_dict[d_v_b] = vf.add_const(None)
    block.event_dict[d_v_c] = vf.add_const(None)

    psi_s_alpha: Var = vf.add_var(name=f"psi_s_alpha")
    psi_s_beta: Var = vf.add_var(name=f"psi_s_beta")
    psi_r1_alpha: Var = vf.add_var(name=f"psi_r1_alpha")
    psi_r1_beta: Var = vf.add_var(name=f"psi_r1_beta")
    psi_r2_alpha: Var = vf.add_var(name=f"psi_r2_alpha")
    psi_r2_beta: Var = vf.add_var(name=f"psi_r2_beta")
    omega_r: Var = vf.add_var(name=f"omega_r")

    d_psi_s_alpha: Var = vf.add_diff_var(name=f"d_psi_s_alpha", base_var=psi_s_alpha)
    d_psi_s_beta: Var = vf.add_diff_var(name=f"d_psi_s_beta", base_var=psi_s_beta)
    d_psi_r1_alpha: Var = vf.add_diff_var(name=f"d_psi_r1_alpha", base_var=psi_r1_alpha)
    d_psi_r1_beta: Var = vf.add_diff_var(name=f"d_psi_r1_beta", base_var=psi_r1_beta)
    d_psi_r2_alpha: Var = vf.add_diff_var(name=f"d_psi_r2_alpha", base_var=psi_r2_alpha)
    d_psi_r2_beta: Var = vf.add_diff_var(name=f"d_psi_r2_beta", base_var=psi_r2_beta)
    d_omega_r: Var = vf.add_diff_var(name=f"d_omega_r", base_var=omega_r)

    i_s_alpha: Var = vf.add_var(name=f"i_s_alpha")
    i_s_beta: Var = vf.add_var(name=f"i_s_beta")
    i_r1_alpha: Var = vf.add_var(name=f"i_r1_alpha")
    i_r1_beta: Var = vf.add_var(name=f"i_r1_beta")
    i_r2_alpha: Var = vf.add_var(name=f"i_r2_alpha")
    i_r2_beta: Var = vf.add_var(name=f"i_r2_beta")
    i_a: Var = vf.add_var(name=f"i_A", reference=VarPowerFlowReferenceType.i_A)
    i_b: Var = vf.add_var(name=f"i_B", reference=VarPowerFlowReferenceType.i_B)
    i_c: Var = vf.add_var(name=f"i_C", reference=VarPowerFlowReferenceType.i_C)
    p_motor: Var = vf.add_var(name=f"P_motor")
    q_motor: Var = vf.add_var(name=f"Q_motor")
    torque_e: Var = vf.add_var(name=f"T_e")
    torque_m: Var = vf.add_var(name=f"T_m")
    slip: Var = vf.add_var(name=f"slip")
    v_alpha: Var = vf.add_var(name=f"v_alpha")
    v_beta: Var = vf.add_var(name=f"v_beta")

    c_eps: Expr = vf.add_const(1e-9)
    c_one: Expr = vf.add_const(1.0)
    c_two: Expr = vf.add_const(2.0)
    c_three_halves: Expr = vf.add_const(1.5)
    c_speed_eps: Expr = params["speed_eps"]

    # Convert leakage and magnetizing reactances into inductances for the double-cage model.
    l_ls: Expr = params["x_ls"] / (params["omega_base"] + c_eps)
    l_lr1: Expr = x_lr1 / (params["omega_base"] + c_eps)
    l_lr2: Expr = x_lr2 / (params["omega_base"] + c_eps)
    l_m: Expr = params["x_m"] / (params["omega_base"] + c_eps)

    # Electrical rotor speed and quadratic-speed load-torque term.
    omega_r_e: Expr = params["omega_base"] * omega_r
    torque_speed_term: Expr = omega_r * sym.max(sym.abs(omega_r), c_speed_eps)

    # The three-branch inductance matrix is identical on alpha and beta axes, so
    # one explicit symbolic inverse keeps the implementation compact and readable.
    den_matrix: Expr = (
        l_ls * l_lr1 * l_lr2
        + l_m * l_lr1 * l_lr2
        + l_m * l_ls * l_lr2
        + l_m * l_ls * l_lr1
        + c_eps
    )
    # Terminal-current sign convention and ABC-to-alpha-beta voltage relation.
    i_a_motor_expr, i_b_motor_expr, i_c_motor_expr = _alpha_beta_to_abc(i_s_alpha, i_s_beta)
    v_alpha_expr, v_beta_expr = _abc_to_alpha_beta(v_a, v_b, v_c)

    block.in_vars = [v_a, v_b, v_c]
    block.out_vars = [i_a, i_b, i_c]

    # Dynamic states: stator flux, both rotor-cage fluxes and normalized mechanical speed.
    block.state_vars = [psi_s_alpha, psi_s_beta, psi_r1_alpha, psi_r1_beta, psi_r2_alpha, psi_r2_beta, omega_r]
    block.diff_vars = [d_psi_s_alpha, d_psi_s_beta, d_psi_r1_alpha, d_psi_r1_beta, d_psi_r2_alpha, d_psi_r2_beta, d_omega_r]
    block.state_eqs = [
        # Stator alpha-axis flux derivative: applied voltage minus stator resistive drop.
        v_alpha - params["r_s"] * i_s_alpha,
        # Stator beta-axis flux derivative: applied voltage minus stator resistive drop.
        v_beta - params["r_s"] * i_s_beta,
        # First-cage rotor alpha flux derivative with resistance and speed coupling to beta flux.
        -r_r1 * i_r1_alpha - omega_r_e * psi_r1_beta,
        # First-cage rotor beta flux derivative with resistance and speed coupling to alpha flux.
        -r_r1 * i_r1_beta + omega_r_e * psi_r1_alpha,
        # Second-cage rotor alpha flux derivative with resistance and speed coupling to beta flux.
        -r_r2 * i_r2_alpha - omega_r_e * psi_r2_beta,
        # Second-cage rotor beta flux derivative with resistance and speed coupling to alpha flux.
        -r_r2 * i_r2_beta + omega_r_e * psi_r2_alpha,
        # Mechanical swing equation: accelerating torque divided by twice the inertia constant.
        (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    ]
    block.algebraic_vars = [
        i_s_alpha,
        i_s_beta,
        i_r1_alpha,
        i_r1_beta,
        i_r2_alpha,
        i_r2_beta,
        i_a,
        i_b,
        i_c,
        p_motor,
        q_motor,
        torque_e,
        torque_m,
        slip,
        v_alpha,
        v_beta,
    ]
    block.algebraic_eqs = [
        # Stator alpha current from the inverse double-cage inductance matrix.
        i_s_alpha - (
            (l_lr1 * l_lr2 + l_m * l_lr1 + l_m * l_lr2) * psi_s_alpha
            - l_m * l_lr2 * psi_r1_alpha
            - l_m * l_lr1 * psi_r2_alpha
        ) / den_matrix,
        # Stator beta current from the inverse double-cage inductance matrix.
        i_s_beta - (
            (l_lr1 * l_lr2 + l_m * l_lr1 + l_m * l_lr2) * psi_s_beta
            - l_m * l_lr2 * psi_r1_beta
            - l_m * l_lr1 * psi_r2_beta
        ) / den_matrix,
        # First-cage rotor alpha current from the coupled stator/cage flux equations.
        i_r1_alpha - (
            -l_m * l_lr2 * psi_s_alpha
            + (l_ls * l_lr2 + l_m * l_ls + l_m * l_lr2) * psi_r1_alpha
            - l_m * l_ls * psi_r2_alpha
        ) / den_matrix,
        # First-cage rotor beta current from the coupled stator/cage flux equations.
        i_r1_beta - (
            -l_m * l_lr2 * psi_s_beta
            + (l_ls * l_lr2 + l_m * l_ls + l_m * l_lr2) * psi_r1_beta
            - l_m * l_ls * psi_r2_beta
        ) / den_matrix,
        # Second-cage rotor alpha current from the coupled stator/cage flux equations.
        i_r2_alpha - (
            -l_m * l_lr1 * psi_s_alpha
            - l_m * l_ls * psi_r1_alpha
            + (l_ls * l_lr1 + l_m * l_ls + l_m * l_lr1) * psi_r2_alpha
        ) / den_matrix,
        # Second-cage rotor beta current from the coupled stator/cage flux equations.
        i_r2_beta - (
            -l_m * l_lr1 * psi_s_beta
            - l_m * l_ls * psi_r1_beta
            + (l_ls * l_lr1 + l_m * l_ls + l_m * l_lr1) * psi_r2_beta
        ) / den_matrix,
        # Phase-A injected current uses the opposite sign of the internally absorbed motor current.
        i_a + i_a_motor_expr,
        # Phase-B injected current uses the opposite sign of the internally absorbed motor current.
        i_b + i_b_motor_expr,
        # Phase-C injected current uses the opposite sign of the internally absorbed motor current.
        i_c + i_c_motor_expr,
        # Three-phase active power absorbed by the motor in alpha-beta coordinates.
        p_motor - c_three_halves * (v_alpha * i_s_alpha + v_beta * i_s_beta),
        # Three-phase reactive power absorbed by the motor in alpha-beta coordinates.
        q_motor - c_three_halves * (v_beta * i_s_alpha - v_alpha * i_s_beta),
        # Electromagnetic torque from the stator flux-current cross product.
        torque_e - c_three_halves * params["omega_base"] * (psi_s_alpha * i_s_beta - psi_s_beta * i_s_alpha),
        # Mechanical load torque with a quadratic speed law.
        torque_m - params["t_load_nom"] * torque_speed_term,
        # Slip is one minus normalized rotor speed.
        slip - (c_one - omega_r),
        # Alpha terminal voltage is the Clarke transform of the ABC terminal voltages.
        v_alpha - v_alpha_expr,
        # Beta terminal voltage is the Clarke transform of the ABC terminal voltages.
        v_beta - v_beta_expr,
    ]

    _set_common_block_metadata(
        templ=templ,
        parameter_block=block,
        name=name,
        v_a=v_a,
        v_b=v_b,
        v_c=v_c,
        i_a=i_a,
        i_b=i_b,
        i_c=i_c,
        d_v_a=d_v_a,
        d_v_b=d_v_b,
        d_v_c=d_v_c,
        params=params,
    )

    # The double-cage initializer follows the Level-2 approach: estimate slip from
    # the target point, then build one internally consistent equivalent circuit and
    # seed the EMT states from the resulting model currents and fluxes.
    # Build peak voltage phasors from EMT initial voltage samples and derivatives.
    v_a_peak: Expr = _phase_peak_phasor(v_a, d_v_a, params["omega_base"], c_eps)
    v_b_peak: Expr = _phase_peak_phasor(v_b, d_v_b, params["omega_base"], c_eps)
    v_c_peak: Expr = _phase_peak_phasor(v_c, d_v_c, params["omega_base"], c_eps)

    # Convert per-phase power-flow targets into complex powers and peak current phasors.
    s_a: Expr = params["p0_a"] + sym.Const(complex(0.0, 1.0)) * params["q0_a"]
    s_b: Expr = params["p0_b"] + sym.Const(complex(0.0, 1.0)) * params["q0_b"]
    s_c: Expr = params["p0_c"] + sym.Const(complex(0.0, 1.0)) * params["q0_c"]
    i_a_peak: Expr = c_two * sym.conj(s_a / (v_a_peak + sym.Const(complex(1e-9, 0.0))))
    i_b_peak: Expr = c_two * sym.conj(s_b / (v_b_peak + sym.Const(complex(1e-9, 0.0))))
    i_c_peak: Expr = c_two * sym.conj(s_c / (v_c_peak + sym.Const(complex(1e-9, 0.0))))
    # Positive-sequence current and voltage used by the double-cage equivalent-circuit initializer.
    i_pos: Expr = _space_vector_positive_sequence(i_a_peak, i_b_peak, i_c_peak)
    v_pos: Expr = _space_vector_positive_sequence(v_a_peak, v_b_peak, v_c_peak)

    # Estimate air-gap voltage and the total rotor equivalent impedance seen from the air-gap.
    z_s: Expr = params["r_s"] + sym.Const(complex(0.0, 1.0)) * params["x_ls"]
    y_m: Expr = sym.Const(1.0) / (sym.Const(complex(0.0, 1.0)) * params["x_m"] + sym.Const(complex(1e-9, 0.0)))
    v_airgap: Expr = v_pos - z_s * i_pos
    y_rot_total: Expr = i_pos / (v_airgap + sym.Const(complex(1e-9, 0.0))) - y_m
    z_rot_total: Expr = sym.Const(1.0) / (y_rot_total + sym.Const(complex(1e-9, 0.0)))
    # Bound the estimated slip inferred from the first-cage resistance and rotor equivalent impedance.
    slip_est: Expr = sym.hard_sat(
        r_r1 / sym.max(sym.real(z_rot_total), r_r1 / params["slip_max"]),
        params["slip_min"],
        params["slip_max"],
    )

    # Build the two rotor-cage impedances at the bounded slip.
    z_r1: Expr = r_r1 / slip_est + sym.Const(complex(0.0, 1.0)) * x_lr1
    z_r2: Expr = r_r2 / slip_est + sym.Const(complex(0.0, 1.0)) * x_lr2
    # Combine the two rotor cages in parallel, then with the magnetizing branch, to get model input current.
    z_r_total: Expr = _parallel_impedance(left_impedance=z_r1, right_impedance=z_r2, eps=c_eps)
    z_m: Expr = sym.Const(complex(0.0, 1.0)) * params["x_m"]
    z_par: Expr = _parallel_impedance(left_impedance=z_m, right_impedance=z_r_total, eps=c_eps)
    z_in: Expr = z_s + z_par
    i_pos_model: Expr = v_pos / (z_in + sym.Const(complex(1e-9, 0.0)))
    v_airgap_model: Expr = v_pos - z_s * i_pos_model
    # The internal rotor-current states use the same sign convention as the
    # Level-2 model, which is opposite to the equivalent-circuit branch current.
    i_r1_phase: Expr = -v_airgap / (z_r1 + sym.Const(complex(1e-9, 0.0)))
    i_r2_phase: Expr = -v_airgap / (z_r2 + sym.Const(complex(1e-9, 0.0)))
    # Convert positive-sequence stator and cage phasors into phase and alpha-beta quantities.
    i_a_model, i_b_model, i_c_model = _phase_values_from_positive_sequence(i_pos_model)
    i_r1_a_peak, i_r1_b_peak, i_r1_c_peak = _phase_values_from_positive_sequence(i_r1_phase)
    i_r2_a_peak, i_r2_b_peak, i_r2_c_peak = _phase_values_from_positive_sequence(i_r2_phase)
    i_s_alpha_peak, i_s_beta_peak = _abc_to_alpha_beta(i_a_peak, i_b_peak, i_c_peak)
    i_r1_alpha_peak, i_r1_beta_peak = _abc_to_alpha_beta(i_r1_a_peak, i_r1_b_peak, i_r1_c_peak)
    i_r2_alpha_peak, i_r2_beta_peak = _abc_to_alpha_beta(i_r2_a_peak, i_r2_b_peak, i_r2_c_peak)
    v_alpha_peak, v_beta_peak = _abc_to_alpha_beta(v_a_peak, v_b_peak, v_c_peak)
    psi_s_alpha_peak = _stator_flux_peak_from_voltage_current(
        v_axis_peak=v_alpha_peak,
        i_axis_peak=i_s_alpha_peak,
        r_s=params["r_s"],
        omega_base=params["omega_base"],
        eps=c_eps,
    )
    psi_s_beta_peak = _stator_flux_peak_from_voltage_current(
        v_axis_peak=v_beta_peak,
        i_axis_peak=i_s_beta_peak,
        r_s=params["r_s"],
        omega_base=params["omega_base"],
        eps=c_eps,
    )
    # Magnetizing flux is the stator flux minus stator leakage flux.
    psi_m_alpha_peak: Expr = psi_s_alpha_peak - l_ls * i_s_alpha_peak
    psi_m_beta_peak: Expr = psi_s_beta_peak - l_ls * i_s_beta_peak

    # Rotor-cage fluxes are leakage flux plus the shared magnetizing flux.
    psi_r1_alpha_peak: Expr = l_lr1 * i_r1_alpha_peak + psi_m_alpha_peak
    psi_r1_beta_peak: Expr = l_lr1 * i_r1_beta_peak + psi_m_beta_peak
    psi_r2_alpha_peak: Expr = l_lr2 * i_r2_alpha_peak + psi_m_alpha_peak
    psi_r2_beta_peak: Expr = l_lr2 * i_r2_beta_peak + psi_m_beta_peak

    # Initial complex power reported by the motor from initialized voltage and current phasors.
    s_motor_init: Expr = _complex_power_from_peak_phasors(
        v_a_peak=v_a_peak,
        v_b_peak=v_b_peak,
        v_c_peak=v_c_peak,
        i_a_peak=i_a_peak,
        i_b_peak=i_b_peak,
        i_c_peak=i_c_peak,
    )

    # Runtime parameters own their initialization expressions directly.
    block.event_dict[params["t_load_nom"]] = (
        torque_e - params["d"] * (omega_r - c_one)
    ) / sym.max(omega_r * sym.abs(omega_r), c_speed_eps * c_speed_eps)

    block.init_eqs = dict({
        # Initialize transformed terminal voltages from the same Clarke equations used during simulation.
        v_alpha: v_alpha_expr,
        v_beta: v_beta_expr,
        # Initialize stator currents from the imaginary part of the target steady-state phasors.
        i_s_alpha: sym.imag(i_s_alpha_peak),
        i_s_beta: sym.imag(i_s_beta_peak),
        # Initialize both rotor-cage currents from their steady-state phasors.
        i_r1_alpha: sym.imag(i_r1_alpha_peak),
        i_r1_beta: sym.imag(i_r1_beta_peak),
        i_r2_alpha: sym.imag(i_r2_alpha_peak),
        i_r2_beta: sym.imag(i_r2_beta_peak),
        # Initialize network-injected phase currents with the load sign convention.
        i_a: -sym.imag(i_a_peak),
        i_b: -sym.imag(i_b_peak),
        i_c: -sym.imag(i_c_peak),
        # Initialize stator and both rotor-cage flux states from the steady-state phasors.
        psi_s_alpha: sym.imag(psi_s_alpha_peak),
        psi_s_beta: sym.imag(psi_s_beta_peak),
        psi_r1_alpha: sym.imag(psi_r1_alpha_peak),
        psi_r1_beta: sym.imag(psi_r1_beta_peak),
        psi_r2_alpha: sym.imag(psi_r2_alpha_peak),
        psi_r2_beta: sym.imag(psi_r2_beta_peak),
        # Initialize speed, slip and reported powers from the equivalent-circuit operating point.
        omega_r: c_one - slip_est,
        slip: c_one - omega_r,
        p_motor: sym.real(s_motor_init),
        q_motor: sym.imag(s_motor_init),
        # Initialize electromagnetic torque from the same torque equation used in the algebraic model.
        torque_e: c_three_halves * params["omega_base"] * (psi_s_alpha * i_s_beta - psi_s_beta * i_s_alpha),
        # Initialize mechanical torque from the nominal load coefficient and speed law.
        torque_m: params["t_load_nom"] * torque_speed_term,
    })
    block.diff_init_eqs = dict({
        # Initial stator alpha flux derivative for the DAE initializer.
        d_psi_s_alpha: v_alpha - params["r_s"] * i_s_alpha,
        # Initial stator beta flux derivative for the DAE initializer.
        d_psi_s_beta: v_beta - params["r_s"] * i_s_beta,
        # Initial first-cage rotor alpha flux derivative for the DAE initializer.
        d_psi_r1_alpha: -r_r1 * i_r1_alpha - omega_r_e * psi_r1_beta,
        # Initial first-cage rotor beta flux derivative for the DAE initializer.
        d_psi_r1_beta: -r_r1 * i_r1_beta + omega_r_e * psi_r1_alpha,
        # Initial second-cage rotor alpha flux derivative for the DAE initializer.
        d_psi_r2_alpha: -r_r2 * i_r2_alpha - omega_r_e * psi_r2_beta,
        # Initial second-cage rotor beta flux derivative for the DAE initializer.
        d_psi_r2_beta: -r_r2 * i_r2_beta + omega_r_e * psi_r2_alpha,
        # Initial rotor-speed derivative from the mechanical swing equation.
        d_omega_r: (torque_e - torque_m - params["d"] * (omega_r - c_one)) / (c_two * params["h"] + c_eps),
    })
    
    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars
    return templ


# ----------------------------------------------------------------------------------------------------------------------
# INDUCTION MOTOR
# ----------------------------------------------------------------------------------------------------------------------
class InductionMotorEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="level", units="", descr="Model fidelity level (2=single-cage, 3=double-cage).", tpe=int, value=2),
                TemplateProp(name="name", units="", descr="Name of the emt model.", tpe=str, value="induction_motor_emt_template"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        level: int = self.get_value("level")
        name: str = self.get_value("name")

        return get_induction_motor_emt_template(
            self.vf, level, name
        )


def get_induction_motor_emt_template(
    vf: VarFactory,
    level: int = 2,
    name: str = "induction_motor_emt_template",
) -> EmtModelTemplate:
    """Build one induction-motor EMT template for the requested fidelity level.

    Level selection:

    * ``2``: Recommended EMT single-cage model.
    * ``3``: EMT double-cage model.

    :param vf: EMT variable factory.
    :param level: Requested model level.
    :param name: Symbolic template name.
    :return: Configured EMT template.
    :raises ValueError: If the requested level is not supported.
    """
    if level == 2:
        return get_induction_motor_single_cage_emt_template(vf=vf, name=name)
    if level == 3:
        return get_induction_motor_double_cage_emt_template(vf=vf, name=name)
    raise ValueError(f"Unsupported induction motor EMT level '{level}'")
