from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_bundle import build_jmarti_fit_bundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_options import JMartiFitOptions
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_frequency_samples import build_jmarti_frequency_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_loewner_seed import build_jmarti_mode_loewner_seed
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import build_jmarti_modal_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import estimate_jmarti_mode_delays
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_passivity import evaluate_jmarti_passivity_report
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import build_jmarti_runtime_data
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import JMartiDiscretization, JMartiModeRuntimeData, JMartiRuntimeData
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_vector_fit import build_jmarti_mode_vector_fit


def _evaluate_scalar_rational_response(frequency_hz: np.ndarray,
                                       poles_s: np.ndarray,
                                       residues: np.ndarray,
                                       constant_term: complex = 0.0 + 0.0j) -> np.ndarray:
    """
    Evaluate one scalar rational response on the imaginary axis.

    :param frequency_hz: Frequency grid in Hz.
    :param poles_s: Continuous-time poles.
    :param residues: Residues paired with ``poles_s``.
    :param constant_term: Optional constant term.
    :return: Complex response samples.
    """
    angular_frequency: np.ndarray = 2.0 * np.pi * frequency_hz
    response: np.ndarray = np.zeros(frequency_hz.size, dtype=np.complex128)
    sample_index: int = 0
    pole_index: int
    s_value: complex

    while sample_index < frequency_hz.size:
        s_value = 1j * angular_frequency[sample_index]
        response[sample_index] = complex(constant_term)
        pole_index = 0

        while pole_index < poles_s.size:
            response[sample_index] = response[sample_index] + residues[pole_index] / (s_value - poles_s[pole_index])
            pole_index += 1

        sample_index += 1

    return response


def _build_diagonal_modal_bundle() -> tuple[object, object]:
    """
    Build one small self-consistent JMARTI fit bundle and runtime dataset.

    :return: Tuple ``(fit_bundle, runtime_data)``.
    """
    frequency_hz: np.ndarray = np.asarray([10.0, 40.0, 80.0, 160.0, 320.0, 640.0], dtype=np.float64)
    z_per_length: np.ndarray = np.zeros((frequency_hz.size, 2, 2), dtype=np.complex128)
    y_per_length: np.ndarray = np.zeros((frequency_hz.size, 2, 2), dtype=np.complex128)
    mode0_pole_s: np.ndarray = np.asarray([-50.0 + 0.0j], dtype=np.complex128)
    mode1_pole_s: np.ndarray = np.asarray([-120.0 + 0.0j], dtype=np.complex128)
    mode0_residue: np.ndarray = np.asarray([0.3 + 0.0j], dtype=np.complex128)
    mode1_residue: np.ndarray = np.asarray([0.15 + 0.0j], dtype=np.complex128)
    hres_mode0_pole_s: np.ndarray = np.asarray([-80.0 + 0.0j], dtype=np.complex128)
    hres_mode1_pole_s: np.ndarray = np.asarray([-160.0 + 0.0j], dtype=np.complex128)
    hres_mode0_residue: np.ndarray = np.asarray([0.02 + 0.0j], dtype=np.complex128)
    hres_mode1_residue: np.ndarray = np.asarray([0.01 + 0.0j], dtype=np.complex128)
    sample_index: int = 0
    mode_response_yc: np.ndarray
    mode0_response_hres: np.ndarray
    mode1_response_hres: np.ndarray
    options: JMartiFitOptions
    samples = None
    modal_samples = None
    mode_delays = None
    yc_fit_mode0 = None
    yc_fit_mode1 = None
    hres_fit_mode0 = None
    hres_fit_mode1 = None
    passivity_report = None
    fit_bundle = None
    runtime_data = None

    mode_response_yc = _evaluate_scalar_rational_response(frequency_hz, mode0_pole_s, mode0_residue, constant_term=0.1 + 0.0j)
    mode0_response_hres = _evaluate_scalar_rational_response(frequency_hz, hres_mode0_pole_s, hres_mode0_residue, constant_term=0.85 + 0.0j)
    mode1_response_hres = _evaluate_scalar_rational_response(frequency_hz, hres_mode1_pole_s, hres_mode1_residue, constant_term=0.75 + 0.0j)

    while sample_index < frequency_hz.size:
        z_per_length[sample_index, :, :] = np.diag(np.asarray([
            1.0 + 0.2j * float(sample_index + 1),
            2.0 + 0.3j * float(sample_index + 1),
        ], dtype=np.complex128))
        y_per_length[sample_index, :, :] = np.diag(np.asarray([
            mode_response_yc[sample_index] * mode_response_yc[sample_index],
            mode1_response_hres[sample_index] * mode1_response_hres[sample_index],
        ], dtype=np.complex128))
        sample_index += 1

    options = JMartiFitOptions(
        forced_model_order=1,
        vf_max_iterations=8,
        passivity_frequency_sample_count=64,
    )
    samples = build_jmarti_frequency_samples(
        frequency_hz=frequency_hz,
        z_per_length=z_per_length,
        y_per_length=y_per_length,
        line_length_m=1000.0,
        phase_labels=("A", "B"),
    )
    modal_samples = build_jmarti_modal_samples(samples=samples, options=options)
    mode_delays = estimate_jmarti_mode_delays(modal_samples, options=options)
    yc_fit_mode0 = build_jmarti_mode_vector_fit(
        frequency_hz=frequency_hz,
        response_values=modal_samples.get_yc_modal()[:, 0],
        loewner_seed=build_jmarti_mode_loewner_seed(frequency_hz, modal_samples.get_yc_modal()[:, 0], "Yc", 0, options),
        options=options,
    )
    yc_fit_mode1 = build_jmarti_mode_vector_fit(
        frequency_hz=frequency_hz,
        response_values=modal_samples.get_yc_modal()[:, 1],
        loewner_seed=build_jmarti_mode_loewner_seed(frequency_hz, modal_samples.get_yc_modal()[:, 1], "Yc", 1, options),
        options=options,
    )
    hres_fit_mode0 = build_jmarti_mode_vector_fit(
        frequency_hz=frequency_hz,
        response_values=mode0_response_hres,
        loewner_seed=build_jmarti_mode_loewner_seed(frequency_hz, mode0_response_hres, "Hres", 0, options),
        options=options,
    )
    hres_fit_mode1 = build_jmarti_mode_vector_fit(
        frequency_hz=frequency_hz,
        response_values=mode1_response_hres,
        loewner_seed=build_jmarti_mode_loewner_seed(frequency_hz, mode1_response_hres, "Hres", 1, options),
        options=options,
    )
    passivity_report = evaluate_jmarti_passivity_report(
        fits=[yc_fit_mode0, yc_fit_mode1, hres_fit_mode0, hres_fit_mode1],
        low_hz=10.0,
        high_hz=640.0,
        options=options,
    )
    fit_bundle = build_jmarti_fit_bundle(
        modal_samples=modal_samples,
        mode_delays=mode_delays,
        yc_fits=[yc_fit_mode0, yc_fit_mode1],
        hres_fits=[hres_fit_mode0, hres_fit_mode1],
        passivity_report=passivity_report,
    )
    runtime_data = build_jmarti_runtime_data(fit_bundle=fit_bundle, time_step_s=1.0e-4)
    return fit_bundle, runtime_data


def test_jmarti_fit_bundle_keeps_mode_alignment_and_optional_passivity_report() -> None:
    fit_bundle, _runtime_data = _build_diagonal_modal_bundle()

    assert fit_bundle.get_mode_count() == 2
    assert fit_bundle.get_passivity_report() is not None
    assert fit_bundle.get_yc_fits()[0].get_mode_index() == 0
    assert fit_bundle.get_hres_fits()[1].get_mode_index() == 1


def test_jmarti_runtime_data_preserves_trapezoidal_response_and_delay_split() -> None:
    """Check filter response, including the direct term, against the continuous fit."""
    fit_bundle, runtime_data = _build_diagonal_modal_bundle()
    mode_data = runtime_data.get_mode_data()[0]
    time_step: float = runtime_data.get_time_step_s()
    frequency_hz: np.ndarray = np.array([10.0, 50.0, 640.0])
    z_values: np.ndarray = np.exp(2j * np.pi * frequency_hz * time_step)
    s_values: np.ndarray = (2.0 / time_step) * (z_values - 1.0) / (z_values + 1.0)

    assert runtime_data.get_mode_count() == 2
    assert mode_data.get_delay_step_count() >= 0
    assert mode_data.get_residual_delay_s() >= 0.0
    for fit, alpha, beta, direct, proportional in (
        (fit_bundle.get_yc_fits()[0], mode_data.get_yc_alpha(), mode_data.get_yc_beta(),
         mode_data.get_yc_constant_term(), mode_data.get_yc_proportional_term()),
        (fit_bundle.get_hres_fits()[0], mode_data.get_hres_alpha(), mode_data.get_hres_beta(),
         mode_data.get_hres_constant_term(), mode_data.get_hres_proportional_term()),
    ):
        expected_response: np.ndarray = fit.get_constant_term() + fit.get_proportional_term() * s_values
        discrete_response: np.ndarray = direct + proportional * s_values
        for pole, residue in zip(fit.get_poles_s(), fit.get_residues()):
            expected_response += residue / (s_values - pole)
        for transition, gain in zip(alpha, beta):
            discrete_response += gain / (z_values - transition)
        np.testing.assert_allclose(discrete_response, expected_response, rtol=1.0e-10, atol=1.0e-12)

    source_h: float = 1e-4
    source_poles: np.ndarray = np.array((-50.0 + 20.0j,), dtype=complex)
    source_residues: np.ndarray = np.array((0.3 - 0.1j,), dtype=complex)
    source_alpha: np.ndarray = np.exp(source_poles * source_h)
    stable_beta: np.ndarray = source_residues * np.expm1(source_poles * source_h) / source_poles
    legacy_beta: np.ndarray = source_residues * (source_alpha - 1.0) / source_poles
    spelling_beta: np.ndarray
    for spelling_beta in (stable_beta, legacy_beta):
        # The old decomposition really emits a small negative residual at9h.
        # Retiming accepts only the arithmetic endpoint bound and leaves the
        # original declared source object/arrays/delay untouched.
        tau: float = 0.0009
        residual: float = tau - 9 * source_h
        assert residual < 0.0
        source_mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
            0, tau, 9, residual, source_poles, source_residues, 0.12, 0j,
            np.empty(0, dtype=complex), np.empty(0, dtype=complex), 0.8, 0j,
            source_alpha, spelling_beta, np.empty(0, dtype=complex), np.empty(0, dtype=complex),
        )
        source_data: JMartiRuntimeData = JMartiRuntimeData(source_h, 1000.0, ("A",),
            np.eye(1), np.eye(1), 50.0, (source_mode,))
        preserved_beta: np.ndarray = spelling_beta.copy()
        target: JMartiRuntimeData = build_jmarti_runtime_data(source_data, 1e-3)
        target_mode: JMartiModeRuntimeData = target.get_mode_data()[0]
        assert target is not source_data
        assert target.get_time_step_s() == 1e-3
        assert source_data.get_time_step_s() == source_h
        assert source_mode.get_residual_delay_s() == residual
        np.testing.assert_array_equal(spelling_beta, preserved_beta)
        np.testing.assert_array_equal(target_mode.get_yc_poles_s(), source_poles)
        np.testing.assert_array_equal(target_mode.get_yc_residues(), source_residues)
        np.testing.assert_allclose(target_mode.get_yc_alpha(), (1.0 + 0.5e-3 * source_poles) / (1.0 - 0.5e-3 * source_poles), rtol=0.0, atol=1e-15)
        np.testing.assert_allclose(target_mode.get_yc_beta(), 1e-3 * source_residues / (1.0 - 0.5e-3 * source_poles) ** 2, rtol=0.0, atol=1e-18)
        assert target_mode.get_delay_step_count() == 0
        np.testing.assert_allclose(target_mode.get_residual_delay_s(), tau, rtol=0.0, atol=1e-19)
        with pytest.raises(ValueError, match="delay/timestep ratio"):
            build_jmarti_runtime_data(source_data, 1e-320)

        # Invalid source metadata must never be silently replaced with a fit.
        bad_beta: np.ndarray
        bad_alpha: np.ndarray
        bad_residual: float
        for bad_beta, bad_alpha, bad_residual in (
                (spelling_beta + 0.1, source_alpha, residual),
                (spelling_beta, source_alpha + 0.1, residual),
                (spelling_beta, source_alpha, -1e-6),
                (np.array((complex(np.nan, 0.0),)), source_alpha, residual),
                (np.empty(0, dtype=complex), source_alpha, residual)):
            invalid_mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
                0, tau, 9, bad_residual, source_poles, source_residues, 0.12, 0j,
                np.empty(0, dtype=complex), np.empty(0, dtype=complex), 0.8, 0j,
                bad_alpha, bad_beta, np.empty(0, dtype=complex), np.empty(0, dtype=complex),
            )
            invalid: JMartiRuntimeData = JMartiRuntimeData(source_h, 1000.0, ("A",),
                np.eye(1), np.eye(1), 50.0, (invalid_mode,))
            with pytest.raises(ValueError):
                build_jmarti_runtime_data(invalid, 1e-3)
        np.testing.assert_array_equal(source_mode.get_yc_beta(), preserved_beta)
    # An intentional imaginary component on a zero-pole beta is not roundoff
    # merely because its absolute magnitude is small compared with one.
    poles: np.ndarray = np.array((-1e-14, 0.0), dtype=complex)
    residues: np.ndarray = np.ones(2, dtype=complex)
    alpha: np.ndarray = np.exp(poles * source_h)
    declared_beta: np.ndarray
    for declared_beta in (np.array((1e-4, 1e-4), dtype=complex),
                          np.array((0.0, 1e-4), dtype=complex)):
        tiny_mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
            0, 0.0, 0, 0.0, poles, residues, 0.12, 0j,
            np.empty(0, dtype=complex), np.empty(0, dtype=complex), 0.8, 0j,
            alpha, declared_beta, np.empty(0, dtype=complex), np.empty(0, dtype=complex),
        )
        tiny_data: JMartiRuntimeData = JMartiRuntimeData(source_h, 1000.0, ("A",),
            np.eye(1), np.eye(1), 50.0, (tiny_mode,))
        tiny_private: JMartiRuntimeData = build_jmarti_runtime_data(tiny_data, 2e-4)
        np.testing.assert_array_equal(tiny_private.get_mode_data()[0].get_yc_beta(), np.array((2e-4, 2e-4)))
    imaginary_mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
        0, 0.0, 0, 0.0, np.array((0j,)), np.array((1.0 + 0j,)), 0.12, 0j,
        np.empty(0, dtype=complex), np.empty(0, dtype=complex), 0.8, 0j,
        np.array((1.0 + 0j,)), np.array((1e-4 + 1e-15j,)),
        np.empty(0, dtype=complex), np.empty(0, dtype=complex),
    )
    imaginary_data: JMartiRuntimeData = JMartiRuntimeData(source_h, 1000.0, ("A",),
        np.eye(1), np.eye(1), 50.0, (imaginary_mode,))
    with pytest.raises(ValueError, match="beta contradicts"):
        build_jmarti_runtime_data(imaginary_data, 2e-4)
    huge_mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
        0, 1e308, 1, 0.0, np.empty(0, dtype=complex), np.empty(0, dtype=complex), 0.12, 0j,
        np.empty(0, dtype=complex), np.empty(0, dtype=complex), 0.8, 0j,
        np.empty(0, dtype=complex), np.empty(0, dtype=complex),
        np.empty(0, dtype=complex), np.empty(0, dtype=complex),
    )
    huge_data: JMartiRuntimeData = JMartiRuntimeData(1e308, 1000.0, ("A",),
        np.eye(1), np.eye(1), 50.0, (huge_mode,))
    # Every bound must itself be finite; an Inf bound cannot admit anything.
    with pytest.raises(ValueError, match="delay split"):
        build_jmarti_runtime_data(huge_data, 1e308)


@pytest.mark.parametrize("pole", (0.0, -1e-14, -50.0))
def test_jmarti_retiming_preserves_direct_term_for_ambiguous_poles(pole: float) -> None:
    """Retiming uses the declared method even when alpha and beta coincide.

    :param pole: Continuous pole, including indistinguishable ZOH/trapezoidal cases.
    :return: None; verify that repeated conversion never adds the direct term twice.
    """
    step: float = 1e-4
    poles: np.ndarray = np.array((pole,), dtype=complex)
    residues: np.ndarray = np.array((0.3,), dtype=complex)
    alpha: np.ndarray
    beta: np.ndarray
    alpha = np.exp(poles * step)
    if pole == 0.0:
        beta = step * residues
    else:
        beta = residues * np.expm1(poles * step) / poles
    empty: np.ndarray = np.empty(0, dtype=complex)
    mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
        0, 0.0, 0, 0.0, poles, residues, 0.12, 0j,
        empty, empty, 0.8, 0j, alpha, beta, empty, empty,
    )
    legacy: JMartiRuntimeData = JMartiRuntimeData(
        step, 1000.0, ("A",), np.eye(1), np.eye(1), 50.0, (mode,),
    )
    assert legacy.get_discretization() == JMartiDiscretization.ZeroOrderHold
    converted: JMartiRuntimeData = build_jmarti_runtime_data(legacy, step)
    assert converted.get_discretization() == JMartiDiscretization.Trapezoidal
    retimed: JMartiRuntimeData = build_jmarti_runtime_data(converted, 2.0 * step)
    expected_direct: complex = 0.12 + step * residues[0] / (1.0 - step * pole)
    np.testing.assert_allclose(retimed.get_mode_data()[0].get_yc_constant_term(), expected_direct,
                               rtol=0.0, atol=1e-15)
    restored: JMartiRuntimeData = build_jmarti_runtime_data(retimed, step)
    np.testing.assert_allclose(restored.get_mode_data()[0].get_yc_constant_term(),
                               converted.get_mode_data()[0].get_yc_constant_term(), rtol=0.0, atol=1e-15)
