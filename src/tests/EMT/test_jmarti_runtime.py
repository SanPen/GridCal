from __future__ import annotations

import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_bundle import build_jmarti_fit_bundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_options import JMartiFitOptions
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_frequency_samples import build_jmarti_frequency_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_loewner_seed import build_jmarti_mode_loewner_seed
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import build_jmarti_modal_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import estimate_jmarti_mode_delays
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import JMartiHistoryRuntime
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import set_jmarti_block_runtime_data
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import build_jmarti_runtime_data
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_vector_fit import build_jmarti_mode_vector_fit
from VeraGridEngine.Templates.Emt.jmarti_line_emt_template import get_jmarti_line_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block


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


def _build_jmarti_runtime_fixture() -> tuple[JMartiHistoryRuntime, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build one small JMARTI runtime fixture.

    :return: Runtime, from-side voltages, to-side voltages, and runtime parameter vector.
    """
    frequency_hz: np.ndarray = np.asarray([10.0, 40.0, 80.0, 160.0, 320.0, 640.0], dtype=np.float64)
    z_per_length: np.ndarray = np.zeros((frequency_hz.size, 2, 2), dtype=np.complex128)
    y_per_length: np.ndarray = np.zeros((frequency_hz.size, 2, 2), dtype=np.complex128)
    sample_index: int = 0
    options = JMartiFitOptions(forced_model_order=1, vf_max_iterations=6)
    mode0_yc: np.ndarray = _evaluate_scalar_rational_response(
        frequency_hz,
        np.asarray([-50.0 + 0.0j], dtype=np.complex128),
        np.asarray([0.3 + 0.0j], dtype=np.complex128),
        constant_term=0.1 + 0.0j,
    )
    mode1_yc: np.ndarray = _evaluate_scalar_rational_response(
        frequency_hz,
        np.asarray([-120.0 + 0.0j], dtype=np.complex128),
        np.asarray([0.15 + 0.0j], dtype=np.complex128),
        constant_term=0.08 + 0.0j,
    )
    mode0_hres: np.ndarray = _evaluate_scalar_rational_response(
        frequency_hz,
        np.asarray([-80.0 + 0.0j], dtype=np.complex128),
        np.asarray([0.02 + 0.0j], dtype=np.complex128),
        constant_term=0.85 + 0.0j,
    )
    mode1_hres: np.ndarray = _evaluate_scalar_rational_response(
        frequency_hz,
        np.asarray([-160.0 + 0.0j], dtype=np.complex128),
        np.asarray([0.01 + 0.0j], dtype=np.complex128),
        constant_term=0.75 + 0.0j,
    )
    samples = None
    modal_samples = None
    mode_delays = None
    fit_bundle = None
    runtime_data = None
    yc_fit_mode0 = None
    yc_fit_mode1 = None
    hres_fit_mode0 = None
    hres_fit_mode1 = None
    grid = None
    bus0 = None
    bus1 = None
    line = None
    vf = None
    templ = None
    runtime = None
    uid2idx_vars = dict()
    uid2idx_event_params = dict()
    x_prev = None
    full_params = None
    v_f_vars = None
    v_t_vars = None

    while sample_index < frequency_hz.size:
        z_per_length[sample_index, :, :] = np.diag(np.asarray([
            1.0 + 0.2j * float(sample_index + 1),
            2.0 + 0.3j * float(sample_index + 1),
        ], dtype=np.complex128))
        y_per_length[sample_index, :, :] = np.diag(np.asarray([
            mode0_yc[sample_index] * mode0_yc[sample_index],
            mode1_yc[sample_index] * mode1_yc[sample_index],
        ], dtype=np.complex128))
        sample_index += 1

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
        response_values=mode0_hres,
        loewner_seed=build_jmarti_mode_loewner_seed(frequency_hz, mode0_hres, "Hres", 0, options),
        options=options,
    )
    hres_fit_mode1 = build_jmarti_mode_vector_fit(
        frequency_hz=frequency_hz,
        response_values=mode1_hres,
        loewner_seed=build_jmarti_mode_loewner_seed(frequency_hz, mode1_hres, "Hres", 1, options),
        options=options,
    )
    fit_bundle = build_jmarti_fit_bundle(
        modal_samples=modal_samples,
        mode_delays=mode_delays,
        yc_fits=[yc_fit_mode0, yc_fit_mode1],
        hres_fits=[hres_fit_mode0, hres_fit_mode1],
    )
    runtime_data = build_jmarti_runtime_data(fit_bundle=fit_bundle, time_step_s=1.0e-4)

    grid = gce.MultiCircuit(Sbase=100.0, fbase=50.0)
    bus0 = gce.Bus(name="Bus0", Vnom=110.0)
    bus1 = gce.Bus(name="Bus1", Vnom=110.0)
    line = gce.Line(name="JMartiLine", bus_from=bus0, bus_to=bus1, length=1.0)
    line.ys.phN = False
    line.ys.phA = True
    line.ys.phB = True
    line.ys.phC = False
    vf = VarFactory()
    templ = get_jmarti_line_emt_template(vf=vf, phN=False, phA=True, phB=True, phC=False, name="JMartiLine").block
    set_jmarti_block_runtime_data(templ, runtime_data)
    runtime = JMartiHistoryRuntime(line=line, line_block=templ, h=1.0e-4)

    v_f_vars = templ.in_vars[:2]
    v_t_vars = templ.in_vars[2:]
    runtime.bind_terminals(v_f_vars=v_f_vars, v_t_vars=v_t_vars)

    uid2idx_vars[v_f_vars[0].uid] = 0
    uid2idx_vars[v_f_vars[1].uid] = 1
    uid2idx_vars[v_t_vars[0].uid] = 2
    uid2idx_vars[v_t_vars[1].uid] = 3
    uid2idx_event_params[runtime.Ih_f[0].uid] = 0
    uid2idx_event_params[runtime.Ih_f[1].uid] = 1
    uid2idx_event_params[runtime.Ih_t[0].uid] = 2
    uid2idx_event_params[runtime.Ih_t[1].uid] = 3
    runtime.setup_indices(uid2idx_vars=uid2idx_vars, uid2idx_event_params=uid2idx_event_params)

    x_prev = np.asarray([1.0, 0.98, 0.97, 0.96], dtype=np.float64)
    full_params = np.zeros(4, dtype=np.float64)
    return runtime, x_prev, full_params, runtime.direct_yc_phase


def test_jmarti_runtime_get_nodal_injections_builds_phase_domain_norton_form() -> None:
    runtime, _x_prev, _full_params, direct_yc_phase = _build_jmarti_runtime_fixture()
    i_f_full, i_t_full = runtime.get_nodal_injections()

    assert i_f_full[0] is None
    assert i_t_full[0] is None
    assert i_f_full[3] is None
    assert i_t_full[3] is None
    assert runtime.get_mode_count() == 2
    assert np.abs(direct_yc_phase[0, 0]) > 0.0


def test_jmarti_runtime_history_update_produces_finite_next_history_currents() -> None:
    runtime, x_prev, full_params, _direct_yc_phase = _build_jmarti_runtime_fixture()
    ih_f_phase, ih_t_phase = runtime.initialize_from_initial_point(
        v_f0_red=np.asarray([1.0, 0.98], dtype=np.float64),
        v_t0_red=np.asarray([0.97, 0.96], dtype=np.float64),
        i_f0_red=np.asarray([0.01, 0.02], dtype=np.float64),
        i_t0_red=np.asarray([0.015, 0.018], dtype=np.float64),
    )
    full_params[0] = float(np.real(ih_f_phase[0]))
    full_params[1] = float(np.real(ih_f_phase[1]))
    full_params[2] = float(np.real(ih_t_phase[0]))
    full_params[3] = float(np.real(ih_t_phase[1]))

    runtime.update_history(step_counter=0, x_prev=x_prev, full_params=full_params)

    assert np.isfinite(full_params).all()
    assert np.max(np.abs(full_params)) > 0.0


def test_jmarti_runtime_fundamental_phasor_initialization_reproduces_initial_currents() -> None:
    runtime, _x_prev, _full_params, direct_yc_phase = _build_jmarti_runtime_fixture()
    v_f_phasor = np.asarray([1.0 - 0.2j, 0.95 - 0.1j], dtype=np.complex128)
    v_t_phasor = np.asarray([0.98 - 0.18j, 0.92 - 0.09j], dtype=np.complex128)
    i_f_phasor = np.asarray([0.04 - 0.01j, -0.03 + 0.02j], dtype=np.complex128)
    i_t_phasor = np.asarray([-0.039 + 0.009j, 0.028 - 0.019j], dtype=np.complex128)
    v_f_sample = np.sqrt(2.0) * np.imag(v_f_phasor)
    v_t_sample = np.sqrt(2.0) * np.imag(v_t_phasor)
    i_f_sample = np.sqrt(2.0) * np.imag(i_f_phasor)
    i_t_sample = np.sqrt(2.0) * np.imag(i_t_phasor)

    ih_f_phase, ih_t_phase = runtime.initialize_from_fundamental_phasors(
        v_f0_phasor_red=v_f_phasor,
        v_t0_phasor_red=v_t_phasor,
        i_f0_phasor_red=i_f_phasor,
        i_t0_phasor_red=i_t_phasor,
        system_frequency_hz=50.0,
    )

    reconstructed_i_f = direct_yc_phase @ v_f_sample + np.real(ih_f_phase)
    reconstructed_i_t = direct_yc_phase @ v_t_sample + np.real(ih_t_phase)

    assert np.allclose(reconstructed_i_f, i_f_sample, atol=5.0e-4)
    assert np.allclose(reconstructed_i_t, i_t_sample, atol=5.0e-4)


@pytest.mark.parametrize("delay_steps", [1, 3, 8])
def test_jmarti_periodic_history_matches_telegrapher_terminal_currents_after_wraparound(delay_steps):
    """Check an entire periodic orbit, not only the supplied initial sample."""
    rt, _, params, _ = _build_jmarti_runtime_fixture()
    from types import SimpleNamespace
    from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import _initialize_jmarti_runtime_storage
    # Use a real impulse response, including a conjugate pair of filter states.
    # The older fixture above fits arbitrary complex synthetic frequency data,
    # which do not enforce conjugate symmetry and cannot define this real orbit.
    mode = SimpleNamespace(
        get_yc_constant_term=lambda: 1.1,
        get_yc_alpha=lambda: np.array([.90+.04j, .90-.04j]),
        get_yc_beta=lambda: np.array([-.005+.002j, -.005-.002j]),
        get_hres_constant_term=lambda: .95,
        get_hres_alpha=lambda: np.array([.97]),
        get_hres_beta=lambda: np.array([.0003]),
        get_delay_step_count=lambda: delay_steps,
        get_residual_delay_s=lambda: .2*rt.h,
    )
    rt.runtime_data = SimpleNamespace(
        get_mode_data=lambda: (mode, mode),
        get_modal_transform=lambda: np.eye(rt.m),
        get_modal_transform_inv=lambda: np.eye(rt.m),
    )
    _initialize_jmarti_runtime_storage(rt)
    frequency = 50.0
    advance = np.exp(2j * np.pi * frequency * rt.h)
    vf = np.array([1.0 - .2j, .95 - .1j])
    vt = np.array([.98 - .18j, .92 - .09j])
    transform = rt.runtime_data.get_modal_transform()
    inverse = rt.runtime_data.get_modal_transform_inv()
    vfm, vtm = inverse @ vf, inverse @ vt
    ifm, itm = np.zeros(rt.m, complex), np.zeros(rt.m, complex)
    for k, mode in enumerate(rt.runtime_data.get_mode_data()):
        yc = mode.get_yc_constant_term() + np.sum(mode.get_yc_beta() / (advance - mode.get_yc_alpha()))
        h = mode.get_hres_constant_term() + np.sum(mode.get_hres_beta() / (advance - mode.get_hres_alpha()))
        fraction = mode.get_residual_delay_s() / rt.h
        h *= advance ** -mode.get_delay_step_count() * (1 - fraction + fraction / advance)
        # Distributed-line boundary identity, independent of Norton state layout.
        ifm[k] = yc * ((1 + h*h)*vfm[k] - 2*h*vtm[k]) / (1 - h*h)
        itm[k] = yc * ((1 + h*h)*vtm[k] - 2*h*vfm[k]) / (1 - h*h)
    current_f, current_t = transform @ ifm, transform @ itm
    hf, ht = rt.initialize_from_fundamental_phasors(vf, vt, current_f, current_t, frequency)
    params[:] = np.r_[hf.real, ht.real]
    for step in range(3 * rt.buffer_size):
        previous_rotation = advance ** max(0, step - 1)
        previous_state = np.sqrt(2) * np.imag(np.r_[vf, vt] * previous_rotation)
        rt.update_history(step, previous_state, params)
        rotation = advance ** step
        actual_f = rt.direct_yc_phase @ (np.sqrt(2)*np.imag(vf*rotation)) + params[:rt.m]
        actual_t = rt.direct_yc_phase @ (np.sqrt(2)*np.imag(vt*rotation)) + params[rt.m:]
        np.testing.assert_allclose(actual_f, np.sqrt(2)*np.imag(current_f*rotation), atol=1e-9)
        np.testing.assert_allclose(actual_t, np.sqrt(2)*np.imag(current_t*rotation), atol=1e-9)
