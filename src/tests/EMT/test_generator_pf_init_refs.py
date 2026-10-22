# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Analytical regressions for conventional-base EMT generator PF references."""

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.generator_emt_type_template import (
    get_generator_sauer_pai_type_emt_template,
    get_pf_positive_sequence_init_refs,
)
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType, VarPowerFlowReferenceType


def _evaluate_pf_init_references(
        voltage: np.ndarray,
        current: np.ndarray,
        template: EmtModelTemplate | None = None) -> tuple[np.ndarray, dict[int, float]]:
    """Evaluate PF references from independently prescribed ABC phasors.

    :param voltage: RMS voltage phasors on the conventional phase-voltage base.
    :param current: Injected RMS currents on the conventional phase-current base.
    :param template: Optional consumer whose PF variables need numerical bindings.
    :return: Evaluated ``(phi_v, phi, Vpk, Ipk)`` and a UID-to-value lookup.
    """
    # Phase power uses total three-phase Sbase, while V and I use phase bases.
    omega: float = 2.0 * np.pi * 50.0
    phase_power: np.ndarray = voltage * np.conj(current) / 3.0
    instantaneous: np.ndarray = np.sqrt(2.0) * voltage.imag
    derivative: np.ndarray = omega * np.sqrt(2.0) * voltage.real
    expressions: tuple[Expr, Expr, Expr, Expr] = get_pf_positive_sequence_init_refs(
        v_a=Const(float(instantaneous[0])), v_b=Const(float(instantaneous[1])),
        v_c=Const(float(instantaneous[2])),
        d_v_a=Const(float(derivative[0])), d_v_b=Const(float(derivative[1])),
        d_v_c=Const(float(derivative[2])),
        p_a=Const(float(phase_power[0].real)), q_a=Const(float(phase_power[0].imag)),
        p_b=Const(float(phase_power[1].real)), q_b=Const(float(phase_power[1].imag)),
        p_c=Const(float(phase_power[2].real)), q_c=Const(float(phase_power[2].imag)),
        omega_base=Const(omega),
    )
    values: dict[int, float] = dict()
    evaluated: np.ndarray = np.empty(4, dtype=float)
    index: int
    for index in range(4):
        evaluated[index] = float(expressions[index].eval_uid(values))

    # Bind actual consumer variables through their existing ordered inputs and maps.
    if template is not None:
        references: tuple[tuple[VarPowerFlowReferenceType, ...], ...] = (
            (VarPowerFlowReferenceType.d_v_A, VarPowerFlowReferenceType.d_v_B,
             VarPowerFlowReferenceType.d_v_C),
            (VarPowerFlowReferenceType.P_A, VarPowerFlowReferenceType.P_B,
             VarPowerFlowReferenceType.P_C),
            (VarPowerFlowReferenceType.Q_A, VarPowerFlowReferenceType.Q_B,
             VarPowerFlowReferenceType.Q_C),
        )
        inputs: np.ndarray = np.array((derivative, phase_power.real, phase_power.imag))
        row: int
        phase: int
        for phase in range(3):
            values[template.block.in_vars[phase].uid] = float(instantaneous[phase])
        for row in range(3):
            for phase in range(3):
                variable: Var = template.block.external_mapping[references[row][phase]]
                values[variable.uid] = float(inputs[row, phase])
        omega_variable: Var = template.block.api_obj_mapping[ParamPowerFlowReferenceType.omega_base]
        values[omega_variable.uid] = omega
    else:
        pass
    return evaluated, values


@pytest.mark.parametrize("voltage_angle,current_phasor", (
    (0.35, 0.5 - 0.15j), (2.2, -0.2 + 0.3j),
    (-2.2, -0.4 - 0.12j), (-0.6, 0.3 + 0.2j),
))
def test_pf_init_current_uses_total_system_power_base(
        voltage_angle: float,
        current_phasor: complex) -> None:
    """Preserve current magnitude and quadratures across voltage and power signs.

    :param voltage_angle: Phase-A voltage angle, including both negative-real quadrants.
    :param current_phasor: Independently specified phase-A injected RMS current.
    :return: None; analytical peak and phasor comparisons must agree.
    """
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    voltage_phasor: complex = 1.02 * np.exp(1j * voltage_angle)
    actual: np.ndarray
    values: dict[int, float]
    actual, values = _evaluate_pf_init_references(voltage_phasor * rotation, current_phasor * rotation)

    # Recover the phasors from peak and angle to check signs as well as amplitude.
    reconstructed: np.ndarray = np.array((
        actual[2] * np.exp(1j * actual[0]) / np.sqrt(2.0),
        actual[3] * np.exp(1j * (actual[0] + actual[1])) / np.sqrt(2.0),
    ))
    np.testing.assert_allclose(reconstructed, np.array((voltage_phasor, current_phasor)),
                               rtol=0.0, atol=1e-12)
    assert not values


def test_pf_init_preserves_positive_sequence_under_unbalance() -> None:
    """Keep the declared positive-sequence projection when all sequences are present.

    :return: None; this verifies references rather than arbitrary ABC runtime support.
    """
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    positive_voltage: complex = 0.98 * np.exp(-0.6j)
    positive_current: complex = 0.4 + 0.12j
    voltage: np.ndarray = positive_voltage * rotation + (0.03 - 0.01j) * rotation.conj() + 0.015j
    current: np.ndarray = positive_current * rotation + (0.02 - 0.03j) * rotation.conj() - 0.01j
    actual: np.ndarray
    values: dict[int, float]
    actual, values = _evaluate_pf_init_references(voltage, current)

    # A positive-sequence owner must neither discard I1 nor mix I0/I2 into it.
    np.testing.assert_allclose(actual[2:4], np.sqrt(2.0) * np.abs(
        np.array((positive_voltage, positive_current))), rtol=0.0, atol=1e-12)
    reconstructed_current: complex = actual[3] * np.exp(1j * (actual[0] + actual[1])) / np.sqrt(2.0)
    np.testing.assert_allclose(reconstructed_current, positive_current, rtol=0.0, atol=1e-12)
    assert not values


@pytest.mark.parametrize("negative_current,zero_current", (
    (0.07 - 0.025j, 0.01 + 0.015j), (0.0j, 0.0j),
))
def test_pf_init_zero_positive_sequence_current(
        negative_current: complex,
        zero_current: complex) -> None:
    """Keep zero positive current finite without prescribing an undefined angle.

    :param negative_current: Negative-sequence current component.
    :param zero_current: Zero-sequence current component; both zero gives no current.
    :return: None; references must remain finite with a zero current peak.
    """
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    voltage: np.ndarray = 1.03 * rotation
    current: np.ndarray = negative_current * rotation.conj() + zero_current
    actual: np.ndarray
    values: dict[int, float]
    actual, values = _evaluate_pf_init_references(voltage, current)
    assert np.all(np.isfinite(actual))
    np.testing.assert_allclose(actual[3], 0.0, rtol=0.0, atol=1e-12)
    assert not values


def test_simple_generator_Ipk_matches_phase_power_reference() -> None:
    """Evaluate the simple generator's actual runtime-parameter current seed.

    :return: None; Ipk must match the conventional-base current scheduled by PF.
    """
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    voltage: np.ndarray = 1.02 * np.exp(0.35j) * rotation
    current: np.ndarray = (0.5 - 0.15j) * rotation
    template: EmtModelTemplate = get_simple_generator_emt_template(vf=VarFactory())
    actual: np.ndarray
    values: dict[int, float]
    actual, values = _evaluate_pf_init_references(voltage, current, template)
    peak_current: Var = template.block.external_mapping[VarPowerFlowReferenceType.Ipk]
    seeded_peak: float = float(template.block.event_dict[peak_current].eval_uid(values))

    # Test the consumer expression against physical input, not only helper agreement.
    np.testing.assert_allclose(seeded_peak, np.sqrt(2.0) * abs(current[0]), rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(seeded_peak, actual[3], rtol=0.0, atol=1e-12)


@pytest.mark.parametrize("voltage_angle,current_phasor", (
    (0.35, 0.5 - 0.15j), (2.2, -0.2 + 0.3j),
))
def test_kundur_current_seed_matches_phase_power_reference(
        voltage_angle: float,
        current_phasor: complex) -> None:
    """Reject double conversion in Kundur's actual dq and ABC current seeds.

    :param voltage_angle: Balanced terminal voltage angle.
    :param current_phasor: Balanced injected current on the conventional phase base.
    :return: None; dq amplitude and instantaneous ABC currents must match PF.
    """
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    voltage: np.ndarray = 1.02 * np.exp(1j * voltage_angle) * rotation
    current: np.ndarray = current_phasor * rotation
    template: EmtModelTemplate = get_generator_sauer_pai_type_emt_template(vf=VarFactory())
    actual: np.ndarray
    values: dict[int, float]
    actual, values = _evaluate_pf_init_references(voltage, current, template)

    # The established ordered state/algebraic storage owns theta and dq currents.
    theta: Var = template.block.state_vars[0]
    current_d: Var = template.block.algebraic_vars[3]
    current_q: Var = template.block.algebraic_vars[4]
    assert theta.name == "theta_abs_"
    assert current_d.name == "i_d_" and current_q.name == "i_q_"
    values[theta.uid] = 0.7
    values[current_d.uid] = float(template.block.init_eqs[current_d].eval_uid(values))
    values[current_q.uid] = float(template.block.init_eqs[current_q].eval_uid(values))
    current_zero: Var = template.block.algebraic_vars[5]
    values[current_zero.uid] = float(template.block.init_eqs[current_zero].eval_uid(values))
    np.testing.assert_allclose(np.hypot(values[current_d.uid], values[current_q.uid]),
                               np.sqrt(2.0) * abs(current_phasor), rtol=0.0, atol=1e-12)

    # Reconstruct each phase from those dq seeds using the actual ABC init laws.
    references: tuple[VarPowerFlowReferenceType, ...] = (
        VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C,
    )
    phase: int
    for phase in range(3):
        phase_variable: Var = template.block.external_mapping[references[phase]]
        seeded_current: float = float(template.block.init_eqs[phase_variable].eval_uid(values))
        np.testing.assert_allclose(seeded_current, np.sqrt(2.0) * current[phase].imag,
                                   rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(actual[3], np.sqrt(2.0) * abs(current_phasor), rtol=0.0, atol=1e-12)
