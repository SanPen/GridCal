# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from typing import List
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import (
    VarPowerFlowReferenceType, DeviceType, ParamPowerFlowReferenceType, TheveninSourceVoltageMode,
)
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp


def get_thevenin_internal_shared_references() -> tuple[str, str, str, str]:
    """
    Return the stable shared-reference contract of the Thevenin seed variables.

    :return: Shared references for ``theta``, ``e_A``, ``e_B`` and ``e_C``.
    :rtype: tuple[str, str, str, str]
    """
    return (
        "thevenin_theta_internal",
        "thevenin_e_a_internal",
        "thevenin_e_b_internal",
        "thevenin_e_c_internal",
    )

def get_generator_thevenin_rl_emt_template_with_ref(
        vf: VarFactory,
        name: str = "emt_thevenin_eq_generator_template",
        source_voltage_mode: TheveninSourceVoltageMode = TheveninSourceVoltageMode.Balanced,
) -> EmtModelTemplate:
    """
    Build the ref-capable three-phase EMT Thevenin generator.

    The grounded reciprocal R/L matrix has equal positive and negative
    eigenvalues and an independently specified zero eigenvalue. Mean-value
    coupling applies this matrix directly in ABC coordinates. Balanced mode
    reconstructs positive-sequence internal voltage; phase mode reconstructs
    each internal voltage from the terminal phasors. The PF result type never
    chooses the source voltage capability. Sharing references remain inputs
    for orchestration and introduce no local controller.

    Inputs
    ------
    ``v_A``, ``v_B``, ``v_C``:
        Instantaneous bus terminal voltages in pu.

    States
    ------
    ``i_A``, ``i_B``, ``i_C``:
        Phase currents injected into the bus in pu.

    ``theta``:
        Absolute electrical angle of the internal balanced source in rad.

    The optional sharing references are exposed through the mappings, but they do
    not introduce extra EMT states or controller dynamics inside the template
    itself.

    Parameters
    ----------
    Static generator parameters:
        ``omega_base``, ``R_s``, ``X_s``

    PF-derived initialization parameters:
        ``phi_v``, ``phi``, ``Vpk``, ``Ipk``

    Optional sharing references:
        ``share_enable``, ``P_share_ref``, ``Q_share_ref``

    Event parameters:
        ``phi_v``, ``phi``, ``Vpk``, ``Ipk``, ``E_scale``

    Initialization
    --------------
    The PF initialization reconstructs the positive-sequence internal emf using:

    .. math::

        E = V + (R + jX) I

    and then initializes:

    * ``theta = phi_v + delta``

    This preserves the PF operating point only when the required internal EMF
    is balanced. The unbalanced variant reconstructs each phase independently.

    :param vf: EMT variable factory.
    :param name: Symbolic block name.
    :param source_voltage_mode: Explicit internal voltage capability.
    :return: Configured grounded reciprocal EMT source template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice
    templ.name = name
    theta_internal_reference: str
    e_a_internal_reference: str
    e_b_internal_reference: str
    e_c_internal_reference: str
    theta_internal_reference, e_a_internal_reference, e_b_internal_reference, e_c_internal_reference = get_thevenin_internal_shared_references()

    # ------------------------------------------------------------------
    # Constants used in symbolic expressions.
    # ------------------------------------------------------------------
    c05: sym.Const = vf.add_const(0.5)
    c_eps_emf: sym.Const = vf.add_const(1.0e-24)
    c0: sym.Const = vf.add_const(0.0)

    # ------------------------------------------------------------------
    # Inputs: terminal bus voltages in abc.
    # ------------------------------------------------------------------
    v_A: sym.Var = vf.add_var(name="v_A", reference=VarPowerFlowReferenceType.v_A)
    v_B: sym.Var = vf.add_var(name="v_B", reference=VarPowerFlowReferenceType.v_B)
    v_C: sym.Var = vf.add_var(name="v_C", reference=VarPowerFlowReferenceType.v_C)
    inputs: List[sym.Var] = list([v_A, v_B, v_C])

    # ------------------------------------------------------------------
    # States:
    # - current dynamics
    # - absolute synchronous angle
    # ------------------------------------------------------------------
    i_A: sym.Var = vf.add_var(name="i_A", reference=VarPowerFlowReferenceType.i_A)
    i_B: sym.Var = vf.add_var(name="i_B", reference=VarPowerFlowReferenceType.i_B)
    i_C: sym.Var = vf.add_var(name="i_C", reference=VarPowerFlowReferenceType.i_C)

    theta: sym.Var = vf.add_var(name="theta", shared_reference=theta_internal_reference)
    # parameter to create a phase jump
    theta_deviation_param: sym.Var = vf.add_var(name="theta_deviation_param")
    # parameter to create RoCoF
    w_scale: sym.Var = vf.add_var(name="f_scale")

    d_i_A: sym.Var = vf.add_diff_var(name="d_i_A", base_var=i_A)
    d_i_B: sym.Var = vf.add_diff_var(name="d_i_B", base_var=i_B)
    d_i_C: sym.Var = vf.add_diff_var(name="d_i_C", base_var=i_C)
    d_theta: sym.Var = vf.add_diff_var(name="d_theta", base_var=theta)

    # ------------------------------------------------------------------
    # Algebraic variables:
    # - internal phase emfs
    # - measured active/reactive power
    # ------------------------------------------------------------------
    e_A: sym.Var = vf.add_var(name="e_A", shared_reference=e_a_internal_reference)
    e_B: sym.Var = vf.add_var(name="e_B", shared_reference=e_b_internal_reference)
    e_C: sym.Var = vf.add_var(name="e_C", shared_reference=e_c_internal_reference)
    Pe: sym.Var = vf.add_var(name="Pe")
    Qe: sym.Var = vf.add_var(name="Qe")

    # ------------------------------------------------------------------
    # Static parameters and PF-derived initialization parameters.
    # ------------------------------------------------------------------
    omega_base: sym.Var = vf.add_var(name="omega_base")
    R_s: sym.Var = vf.add_var(name="R_s")
    X_s: sym.Var = vf.add_var(name="X_s")
    R_0: sym.Var = vf.add_var(name="R_0")
    X_0: sym.Var = vf.add_var(name="X_0")
    mode_marker: sym.Var = vf.add_var(name="source_voltage_mode")

    # Phase quadratures are PF-derived event parameters, using the established
    # phase current base. They initialize the states once and never multiply
    # the already converted currents by a second factor of three.
    phases: tuple[str, str, str] = ("A", "B", "C")
    voltage_real: np.ndarray = np.empty(3, dtype=object)
    voltage_imag: np.ndarray = np.empty(3, dtype=object)
    current_real: np.ndarray = np.empty(3, dtype=object)
    current_imag: np.ndarray = np.empty(3, dtype=object)
    phase_index: int
    for phase_index in range(3):
        phase: str = phases[phase_index]
        voltage_real[phase_index] = vf.add_var(name=f"UR_{phase}")
        voltage_imag[phase_index] = vf.add_var(name=f"UI_{phase}")
        current_real[phase_index] = vf.add_var(name=f"IR_{phase}")
        current_imag[phase_index] = vf.add_var(name=f"II_{phase}")

    phi_v: sym.Var = vf.add_var(name="phi_v")
    phi: sym.Var = vf.add_var(name="phi")
    Vpk: sym.Var = vf.add_var(name="Vpk")
    Ipk: sym.Var = vf.add_var(name="Ipk")

    # ------------------------------------------------------------------
    # Optional sharing references.
    # The references are exposed for higher-level orchestration only. The passive
    # Thevenin source does not use them internally.
    # ------------------------------------------------------------------
    share_enable: sym.Var = vf.add_var(name="share_enable")
    P_share_ref: sym.Var = vf.add_var(name="P_share_ref")
    Q_share_ref: sym.Var = vf.add_var(name="Q_share_ref")
    E_scale: sym.Var = vf.add_var(name="E_scale")

    # ------------------------------------------------------------------
    # PF-consistent positive-sequence internal emf.
    # This part remains identical in spirit to the original Thevenin model.
    # ------------------------------------------------------------------
    E_re: sym.Expr = Vpk + R_s * Ipk * sym.cos(phi) - X_s * Ipk * sym.sin(phi)
    E_im: sym.Expr = R_s * Ipk * sym.sin(phi) + X_s * Ipk * sym.cos(phi)
    # ``atan2`` keeps the reconstructed emf angle consistent across quadrants and
    # avoids undefined divisions when the steady-state real component is zero.
    delta_expr: sym.Expr = sym.atan2(E_im, E_re)
    Epk_expr: sym.Expr = (E_re ** 2 + E_im ** 2 + c_eps_emf) ** c05

    # ------------------------------------------------------------------
    # The ref-capable variant preserves the original passive Thevenin source.
    # The exposed reference variables are mapped for higher-level orchestration,
    # but they do not change the local source equations.
    # ------------------------------------------------------------------
    theta_speed: sym.Expr = omega_base

    # ------------------------------------------------------------------
    # Build the EMT block.
    # ------------------------------------------------------------------
    mean_current: sym.Expr = (i_A + i_B + i_C) / 3.0
    mean_drop: sym.Expr = (e_A - v_A + e_B - v_B + e_C - v_C) / 3.0
    state_eqs: List[sym.Expr] = list([
        omega_base * ((e_A - v_A - mean_drop - R_s * (i_A - mean_current)) / X_s
                      + (mean_drop - R_0 * mean_current) / X_0),
        omega_base * ((e_B - v_B - mean_drop - R_s * (i_B - mean_current)) / X_s
                      + (mean_drop - R_0 * mean_current) / X_0),
        omega_base * ((e_C - v_C - mean_drop - R_s * (i_C - mean_current)) / X_s
                      + (mean_drop - R_0 * mean_current) / X_0),
        theta_speed * w_scale,
    ])

    state_vars: List[sym.Var] = list([
        i_A,
        i_B,
        i_C,
        theta,
    ])

    # Voltage capability is structural. Balanced mode retains only E1 rather
    # than silently synthesizing E0/E2 to fit an incompatible operating point.
    emf_waveforms: np.ndarray = np.empty(3, dtype=object)
    theta_initial: sym.Expr
    marker_value: float
    phase_index: int
    if source_voltage_mode == TheveninSourceVoltageMode.Balanced:
        theta_initial = phi_v + delta_expr
        marker_value = 0.0
        offsets: tuple[float, float, float] = (0.0, -2.0 * np.pi / 3.0, 2.0 * np.pi / 3.0)
        for phase_index in range(3):
            emf_waveforms[phase_index] = E_scale * Epk_expr * sym.sin(theta + offsets[phase_index] + theta_deviation_param)
    else:
        theta_initial = c0
        marker_value = 1.0
        mean_ir: sym.Expr = (current_real[0] + current_real[1] + current_real[2]) / 3.0
        mean_ii: sym.Expr = (current_imag[0] + current_imag[1] + current_imag[2]) / 3.0
        for phase_index in range(3):
            emf_real: sym.Expr = (voltage_real[phase_index] + R_s * current_real[phase_index]
                                  - X_s * current_imag[phase_index]
                                  + (R_0 - R_s) * mean_ir - (X_0 - X_s) * mean_ii)
            emf_imag: sym.Expr = (voltage_imag[phase_index] + R_s * current_imag[phase_index]
                                  + X_s * current_real[phase_index]
                                  + (R_0 - R_s) * mean_ii + (X_0 - X_s) * mean_ir)
            emf_waveforms[phase_index] = np.sqrt(2.0) * E_scale * (
                emf_real * sym.sin(theta + theta_deviation_param)
                + emf_imag * sym.cos(theta + theta_deviation_param))

    algebraic_eqs: List[sym.Expr] = list([
        e_A - emf_waveforms[0],
        e_B - emf_waveforms[1],
        e_C - emf_waveforms[2],
        Pe - (i_A * v_A + i_B * v_B + i_C * v_C),
        Qe - (1.0 / np.sqrt(3.0)) * (
            (v_A - v_B) * i_C +
            (v_B - v_C) * i_A +
            (v_C - v_A) * i_B
        ),
    ])

    algebraic_vars: List[sym.Var] = list([e_A, e_B, e_C, Pe, Qe])

    block: Block = Block(
        state_eqs=state_eqs,
        state_vars=state_vars,
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        in_vars=inputs,
        out_vars=list([i_A, i_B, i_C]),
    )

    # The electrical values come directly from the static generator and are
    # therefore required. Using a fallback source impedance would change the
    # first EMT derivative and hide a physical-device mapping regression.
    block.parameters[omega_base] = vf.add_const(None)
    block.parameters[R_s] = vf.add_const(None)
    block.parameters[X_s] = vf.add_const(None)
    block.parameters[R_0] = vf.add_const(None)
    block.parameters[X_0] = vf.add_const(None)
    # The canonical declarative parameter survives template copy and save/load.
    block.parameters[mode_marker] = vf.add_const(marker_value)
    # Declare capability on the inner electrical owner, without duplicating the
    # authored mode or adding a declaration to the containing reference wrapper.
    block.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid = mode_marker.uid

    block.diff_vars = list([
        d_i_A,
        d_i_B,
        d_i_C,
        d_theta,
    ])

    # ------------------------------------------------------------------
    # External mapping:
    # keep the original EMT injection interface intact.
    # ------------------------------------------------------------------
    block.external_mapping = dict({
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
        VarPowerFlowReferenceType.phi_v: phi_v,
        VarPowerFlowReferenceType.phi: phi,
        VarPowerFlowReferenceType.Vpk: Vpk,
        VarPowerFlowReferenceType.Ipk: Ipk,
        VarPowerFlowReferenceType.d_v_A: None,
        VarPowerFlowReferenceType.d_v_B: None,
        VarPowerFlowReferenceType.d_v_C: None,
        VarPowerFlowReferenceType.P_A: None,
        VarPowerFlowReferenceType.Q_A: None,
        VarPowerFlowReferenceType.P_B: None,
        VarPowerFlowReferenceType.Q_B: None,
        VarPowerFlowReferenceType.P_C: None,
        VarPowerFlowReferenceType.Q_C: None,
    })

    # ------------------------------------------------------------------
    # API-object mapping:
    # static generator parameters plus optional sharing references assigned
    # by EmtProblemDae.
    # ------------------------------------------------------------------
    block.api_obj_mapping = dict({
        ParamPowerFlowReferenceType.omega_base: omega_base,
        ParamPowerFlowReferenceType.R1: R_s,
        ParamPowerFlowReferenceType.X1: X_s,
        ParamPowerFlowReferenceType.thevenin_source_r0_pu: R_0,
        ParamPowerFlowReferenceType.thevenin_source_x0_pu: X_0,
        ParamPowerFlowReferenceType.generator_share_enable: share_enable,
        ParamPowerFlowReferenceType.generator_share_p_ref: P_share_ref,
        ParamPowerFlowReferenceType.generator_share_q_ref: Q_share_ref,
    })

    # ------------------------------------------------------------------
    # Event parameters:
    # PF-derived phasor quantities plus local controller gains.
    # The gains are intentionally conservative compared with the version
    # that acted directly on dtheta/dt.
    # ------------------------------------------------------------------
    block.event_dict = dict({
        phi_v: vf.add_const(None),
        phi: vf.add_const(None),
        Vpk: vf.add_const(None),
        Ipk: vf.add_const(None),
        # This remains a pure event/runtime parameter so scripts and EMT events
        # can scale the Thevenin source magnitude from outside the model.
        E_scale: vf.add_const(1.0),
        theta_deviation_param: vf.add_const(0.0),
        w_scale: vf.add_const(1.0),
        # Sharing data depends on the solved operating point and bus topology.
        # Required runtime placeholders prevent a static fallback from hiding a
        # missing PF seed while keeping the static parameter contract physical.
        share_enable: vf.add_const(None),
        P_share_ref: vf.add_const(None),
        Q_share_ref: vf.add_const(None),
    })

    # ------------------------------------------------------------------
    # Initialization equations:
    # the sharing controller starts exactly from the PF-consistent open-loop
    # operating point, so it does not create a jump at t = 0.
    # ------------------------------------------------------------------
    block.init_eqs = dict({
        theta: theta_initial,
        i_A: np.sqrt(2.0) * current_imag[0],
        i_B: np.sqrt(2.0) * current_imag[1],
        i_C: np.sqrt(2.0) * current_imag[2],
        e_A: emf_waveforms[0],
        e_B: emf_waveforms[1],
        e_C: emf_waveforms[2],
        Pe: (i_A * v_A + i_B * v_B + i_C * v_C),
        Qe: (1.0 / np.sqrt(3.0)) * (
            (v_A - v_B) * i_C +
            (v_B - v_C) * i_A +
            (v_C - v_A) * i_B
        ),
    })

    # ------------------------------------------------------------------
    # Differential initialization equations:
    # these keep the standard EMT explicit-init semantics.
    # ------------------------------------------------------------------
    block.diff_init_eqs = dict({
        d_i_A: state_eqs[0],
        d_i_B: state_eqs[1],
        d_i_C: state_eqs[2],
        d_theta: theta_speed * w_scale,
    })

    # Reuse the existing phase-resolved PF references; their values are carried
    # by EmtProblemDae's injection seed rather than stored as physical data.
    quadrature_refs: tuple[tuple[VarPowerFlowReferenceType, ...], ...] = (
        (VarPowerFlowReferenceType.UR_A, VarPowerFlowReferenceType.UR_B, VarPowerFlowReferenceType.UR_C),
        (VarPowerFlowReferenceType.UI_A, VarPowerFlowReferenceType.UI_B, VarPowerFlowReferenceType.UI_C),
        (VarPowerFlowReferenceType.IR_A, VarPowerFlowReferenceType.IR_B, VarPowerFlowReferenceType.IR_C),
        (VarPowerFlowReferenceType.II_A, VarPowerFlowReferenceType.II_B, VarPowerFlowReferenceType.II_C),
    )
    quadrature_vars: tuple[np.ndarray, ...] = (voltage_real, voltage_imag, current_real, current_imag)
    quadrature_index: int
    for quadrature_index in range(4):
        for phase_index in range(3):
            quadrature: sym.Var = quadrature_vars[quadrature_index][phase_index]
            block.event_dict[quadrature] = vf.add_const(None)
            block.external_mapping[quadrature_refs[quadrature_index][phase_index]] = quadrature

    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = inputs
    templ.block.out_vars = block.out_vars

    return templ


class TheveninSourceEmtTemplate(TemplateDefinition):
    """Structural properties of the grounded reciprocal source factory."""

    __slots__ = ()

    def __init__(self, vf: VarFactory) -> None:
        """Expose model name and explicit internal voltage capability.

        :param vf: Factory owning the resulting symbolic model.
        :return: None.
        """
        super().__init__(vf, list((
            TemplateProp("source_voltage_mode", "", "Internal voltage capability; independent of PF result type.",
                         TheveninSourceVoltageMode, TheveninSourceVoltageMode.Balanced),
            TemplateProp("name", "", "Name of the grounded passive source.", str, "emt_thevenin_eq_generator_template"),
        )))

    def eval(self) -> EmtModelTemplate:
        """Build the source using its selected structural properties.

        :return: Source template with its canonical persisted mode marker.
        """
        name: str = self.get_value("name")
        source_voltage_mode: TheveninSourceVoltageMode = self.get_value("source_voltage_mode")
        return get_generator_thevenin_rl_emt_template_with_ref(self.vf, name, source_voltage_mode)


def get_generator_unbalanced_thevenin_rl_emt_template(
        vf: VarFactory,
        name: str = "emt_unbalanced_thevenin_eq_generator_template",
) -> EmtModelTemplate:
    """Build the phase-resolved variant using the common source equations.

    :param vf: Factory owning the model.
    :param name: Model name.
    :return: Source with independent internal phase voltages.
    """
    return get_generator_thevenin_rl_emt_template_with_ref(
        vf=vf, name=name, source_voltage_mode=TheveninSourceVoltageMode.Phase,
    )
