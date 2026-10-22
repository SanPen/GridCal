from __future__ import annotations

import numpy as np
import pytest

import VeraGridEngine.api as gce
from tests.EMT.test_jmarti_emt_problem_integration import _build_jmarti_fit_bundle_for_three_phase_line
from tests.EMT.test_thevenin_abc_contract import _build_source_case
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_bundle import JMartiFitBundle, build_jmarti_fit_bundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_options import JMartiFitOptions
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_frequency_samples import build_jmarti_frequency_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_loewner_seed import build_jmarti_mode_loewner_seed
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import build_jmarti_modal_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import estimate_jmarti_mode_delays
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import JMartiHistoryRuntime
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import get_jmarti_block_fit_bundle, get_jmarti_block_runtime_data, _get_delayed_incident_wave
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import set_jmarti_block_runtime_data
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import set_jmarti_block_fit_bundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import JMartiModeRuntimeData, JMartiRuntimeData, build_jmarti_runtime_data
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_vector_fit import build_jmarti_mode_vector_fit
from VeraGridEngine.Templates.Emt.jmarti_line_emt_template import get_jmarti_line_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.enumerations import TheveninSourceVoltageMode


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

    # A target-step call must advance the accepted t0 state, not only retain
    # already finite initial parameters through the remote startup no-op.
    initial_parameters: np.ndarray = full_params.copy()
    initial_buffers_from: np.ndarray = runtime.buf_a_f.copy()
    initial_buffers_to: np.ndarray = runtime.buf_a_t.copy()
    # Drive a genuine accepted voltage change: an unperturbed delayed steady
    # point can retain its parameters during the first target update.
    x_prev[0] += 0.05
    x_prev[2] -= 0.02
    runtime.update_history(step_counter=1, x_prev=x_prev, full_params=full_params)
    assert np.max(np.abs(full_params - initial_parameters)) > 1e-12
    assert max(np.max(np.abs(runtime.buf_a_f - initial_buffers_from)),
               np.max(np.abs(runtime.buf_a_t - initial_buffers_to))) > 1e-12

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


@pytest.mark.parametrize("delay_steps,frequency_hz", (
    (1, 50.0), (3, 50.0), (8, 50.0), (3, 60.0), (3, 0.0),
))
def test_jmarti_periodic_history_matches_telegrapher_terminal_currents_after_wraparound(
        delay_steps: int, frequency_hz: float,
) -> None:
    """Verify conjugate-pole states through typed attachment and a real port orbit.

    This validates the declared discrete line kernel with prescribed voltages;
    it does not certify a fitted static line or interconnected network orbit.

    :param delay_steps: Causal delay in steps for the first heterogeneous mode.
    :param frequency_hz: Periodic excitation frequency or its constant limit.
    :return: None; assert initial filter phases and at least 401 native updates.
    """
    fixture: tuple[JMartiHistoryRuntime, np.ndarray, np.ndarray, np.ndarray] = _build_jmarti_runtime_fixture()
    original: JMartiHistoryRuntime = fixture[0]
    x_prev: np.ndarray = fixture[1]
    full_params: np.ndarray = fixture[2]
    assert original.v_f_vars is not None
    assert original.v_t_vars is not None
    assert original.idx_vf is not None
    assert original.idx_vt is not None
    assert original.idx_p_hf is not None
    assert original.idx_p_ht is not None

    # Explicit real stable coefficients isolate periodic initialization from the
    # old fitted fixture's unpaired complex kernel. Each mode has a distinct lag.
    mode_delays: tuple[float, float] = (float(delay_steps) + 0.2, float(delay_steps + 2) + 0.35)
    mode_records: list[JMartiModeRuntimeData | None] = list((None, None))
    mode_index: int
    for mode_index in range(2):
        lag: int = int(np.floor(mode_delays[mode_index]))
        fraction: float = mode_delays[mode_index] - lag
        yc_poles: np.ndarray
        yc_residues: np.ndarray
        hres_poles: np.ndarray
        hres_residues: np.ndarray
        # Conjugate residues/poles define a real impulse response while each
        # internal pole state retains its necessary complex quadrature.
        fitted_yc_alpha: np.ndarray = np.array((0.90 + 0.04j, 0.90 - 0.04j))
        fitted_yc_beta: np.ndarray = (1.0 + 0.2 * mode_index) * np.array((-0.005 + 0.002j, -0.005 - 0.002j))
        yc_poles = np.log(fitted_yc_alpha) / original.h
        yc_residues = fitted_yc_beta * yc_poles / np.expm1(yc_poles * original.h)
        fitted_hres_alpha: np.ndarray = np.array((0.97 - 0.01 * mode_index,), dtype=complex)
        fitted_hres_beta: np.ndarray = np.array((0.0003 + 0.0001 * mode_index,), dtype=complex)
        hres_poles = np.log(fitted_hres_alpha) / original.h
        hres_residues = fitted_hres_beta * hres_poles / np.expm1(hres_poles * original.h)
        yc_alpha: np.ndarray = np.exp(yc_poles * original.h)
        yc_beta: np.ndarray = yc_residues * np.expm1(yc_poles * original.h) / yc_poles
        hres_alpha: np.ndarray = np.exp(hres_poles * original.h)
        hres_beta: np.ndarray = hres_residues * np.expm1(hres_poles * original.h) / hres_poles
        mode_records[mode_index] = JMartiModeRuntimeData(
            mode_index=mode_index, tau_s=mode_delays[mode_index] * original.h,
            delay_step_count=lag, residual_delay_s=fraction * original.h,
            yc_poles_s=yc_poles, yc_residues=yc_residues,
            yc_constant_term=complex(1.1 - 0.1 * mode_index), yc_proportional_term=0.0 + 0.0j,
            hres_poles_s=hres_poles, hres_residues=hres_residues,
            hres_constant_term=complex(0.95 - 0.1 * mode_index), hres_proportional_term=0.0 + 0.0j,
            yc_alpha=yc_alpha, yc_beta=yc_beta, hres_alpha=hres_alpha, hres_beta=hres_beta,
        )
    assert mode_records[0] is not None
    assert mode_records[1] is not None
    transform: np.ndarray = np.array(((0.8, -0.6), (0.6, 0.8)), dtype=complex)
    data: JMartiRuntimeData = JMartiRuntimeData(
        time_step_s=original.h, line_length_m=1000.0, phase_labels=("A", "B"),
        modal_transform=transform, modal_transform_inv=transform.T,
        reference_frequency_hz=50.0, mode_data=(mode_records[0], mode_records[1]),
    )
    set_jmarti_block_runtime_data(block=original.block, runtime_data=data)
    runtime: JMartiHistoryRuntime = JMartiHistoryRuntime(
        line=original.line, line_block=original.block, h=original.h,
    )
    runtime.bind_terminals(v_f_vars=original.v_f_vars, v_t_vars=original.v_t_vars)
    variable_indices: dict[int, int] = dict()
    parameter_indices: dict[int, int] = dict()
    for mode_index in range(runtime.m):
        variable_indices[original.v_f_vars[mode_index].uid] = original.idx_vf[mode_index]
        variable_indices[original.v_t_vars[mode_index].uid] = original.idx_vt[mode_index]
        parameter_indices[runtime.Ih_f[mode_index].uid] = original.idx_p_hf[mode_index]
        parameter_indices[runtime.Ih_t[mode_index].uid] = original.idx_p_ht[mode_index]
    runtime.setup_indices(uid2idx_vars=variable_indices, uid2idx_event_params=parameter_indices)
    assert runtime.idx_vf is not None
    assert runtime.idx_vt is not None
    assert runtime.idx_p_hf is not None
    assert runtime.idx_p_ht is not None
    np.testing.assert_allclose(transform.T @ transform, np.eye(2), rtol=0.0, atol=1e-12)

    # Choose nontrivial outgoing analytic amplitudes, then solve the two native
    # difference-equation ports jointly. Arbitrary currents would hide drift.
    advance: complex = complex(np.exp(2j * np.pi * frequency_hz * runtime.h))
    outgoing_from: np.ndarray = np.array((0.8 - 0.2j, -0.3 + 0.7j), dtype=complex)
    outgoing_to: np.ndarray = np.array((0.5 + 0.4j, 0.6 - 0.1j), dtype=complex)
    voltage_from: np.ndarray = np.empty(runtime.m, dtype=complex)
    voltage_to: np.ndarray = np.empty(runtime.m, dtype=complex)
    current_from: np.ndarray = np.empty(runtime.m, dtype=complex)
    current_to: np.ndarray = np.empty(runtime.m, dtype=complex)
    expected_yc_from: np.ndarray = np.zeros_like(runtime.yc_state_from)
    expected_yc_to: np.ndarray = np.zeros_like(runtime.yc_state_to)
    expected_hres_from: np.ndarray = np.zeros_like(runtime.hres_state_from)
    expected_hres_to: np.ndarray = np.zeros_like(runtime.hres_state_to)
    for mode_index in range(runtime.m):
        mode: JMartiModeRuntimeData = data.get_mode_data()[mode_index]
        lag: int = mode.get_delay_step_count()
        fraction: float = mode.get_residual_delay_s() / runtime.h
        delay_transfer: complex = (1.0 - fraction) * advance ** (-lag) + fraction * advance ** (-lag - 1)
        yc_transfer: complex = complex(mode.get_yc_constant_term() + np.sum(
            mode.get_yc_beta() / (advance - mode.get_yc_alpha()),
        ))
        hres_transfer: complex = complex(mode.get_hres_constant_term() + np.sum(
            mode.get_hres_beta() / (advance - mode.get_hres_alpha()),
        ))
        delayed_from: complex = complex(delay_transfer * outgoing_to[mode_index])
        delayed_to: complex = complex(delay_transfer * outgoing_from[mode_index])
        # Telegrapher ports use the full discrete admittance and propagation;
        # the direct Norton term alone does not define the outgoing wave.
        incoming_from: complex = hres_transfer * delayed_from
        incoming_to: complex = hres_transfer * delayed_to
        voltage_from[mode_index] = outgoing_from[mode_index] + incoming_from
        voltage_to[mode_index] = outgoing_to[mode_index] + incoming_to
        current_from[mode_index] = yc_transfer * (outgoing_from[mode_index] - incoming_from)
        current_to[mode_index] = yc_transfer * (outgoing_to[mode_index] - incoming_to)
        yc_count: int = int(runtime.yc_order_counts[mode_index])
        hres_count: int = int(runtime.hres_order_counts[mode_index])
        # Evaluate both signs independently for each pole; taking real of a
        # positive-frequency pole row would erase the conjugate-pair state.
        yc_input_from: complex = complex(voltage_from[mode_index] - 2.0 * hres_transfer * delayed_from)
        yc_input_to: complex = complex(voltage_to[mode_index] - 2.0 * hres_transfer * delayed_to)
        expected_hres_from[mode_index, :hres_count] = 0.5 * mode.get_hres_beta() * (
            delayed_from / (advance - mode.get_hres_alpha())
            + delayed_from.conjugate() / (advance.conjugate() - mode.get_hres_alpha())
        )
        expected_hres_to[mode_index, :hres_count] = 0.5 * mode.get_hres_beta() * (
            delayed_to / (advance - mode.get_hres_alpha())
            + delayed_to.conjugate() / (advance.conjugate() - mode.get_hres_alpha())
        )
        expected_yc_from[mode_index, :yc_count] = 0.5 * mode.get_yc_beta() * (
            yc_input_from / (advance - mode.get_yc_alpha())
            + yc_input_from.conjugate() / (advance.conjugate() - mode.get_yc_alpha())
        )
        expected_yc_to[mode_index, :yc_count] = 0.5 * mode.get_yc_beta() * (
            yc_input_to / (advance - mode.get_yc_alpha())
            + yc_input_to.conjugate() / (advance.conjugate() - mode.get_yc_alpha())
        )
    voltage_from_phase: np.ndarray = transform @ voltage_from
    voltage_to_phase: np.ndarray = transform @ voltage_to
    current_from_phase: np.ndarray = transform @ current_from
    current_to_phase: np.ndarray = transform @ current_to

    # Initialize exactly once. The remaining run supplies only accepted terminal
    # voltages; it never resets buffers, filter states, histories or currents.
    history_from: np.ndarray
    history_to: np.ndarray
    history_from, history_to = runtime.initialize_from_fundamental_phasors(
        v_f0_phasor_red=1j * voltage_from_phase / np.sqrt(2.0),
        v_t0_phasor_red=1j * voltage_to_phase / np.sqrt(2.0),
        i_f0_phasor_red=1j * current_from_phase / np.sqrt(2.0),
        i_t0_phasor_red=1j * current_to_phase / np.sqrt(2.0),
        system_frequency_hz=frequency_hz,
    )
    full_params[runtime.idx_p_hf] = history_from.real
    full_params[runtime.idx_p_ht] = history_to.real
    np.testing.assert_allclose(runtime.hres_state_from, expected_hres_from, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.hres_state_to, expected_hres_to, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.yc_state_from, expected_yc_from, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.yc_state_to, expected_yc_to, rtol=0.0, atol=1e-12)

    if frequency_hz > 0.0:
        assert np.max(np.abs(runtime.yc_state_from.imag)) > 1e-6
    else:
        pass
    np.testing.assert_allclose(runtime.buf_a_f.imag, 0.0, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.buf_a_t.imag, 0.0, rtol=0.0, atol=1e-12)

    # The startup call must preserve every initialized store. A target-step
    # call at k subsequently consumes only the accepted voltage at k-1.
    initial_buffers_from: np.ndarray = runtime.buf_a_f.copy()
    initial_buffers_to: np.ndarray = runtime.buf_a_t.copy()
    initial_yc_from: np.ndarray = runtime.yc_state_from.copy()
    initial_yc_to: np.ndarray = runtime.yc_state_to.copy()
    initial_hres_from: np.ndarray = runtime.hres_state_from.copy()
    initial_hres_to: np.ndarray = runtime.hres_state_to.copy()
    initial_parameters: np.ndarray = full_params.copy()
    x_prev[runtime.idx_vf] = voltage_from_phase.real
    x_prev[runtime.idx_vt] = voltage_to_phase.real
    runtime.update_history(step_counter=0, x_prev=x_prev, full_params=full_params)
    np.testing.assert_array_equal(runtime.buf_a_f, initial_buffers_from)
    np.testing.assert_array_equal(runtime.buf_a_t, initial_buffers_to)
    np.testing.assert_array_equal(runtime.yc_state_from, initial_yc_from)
    np.testing.assert_array_equal(runtime.yc_state_to, initial_yc_to)
    np.testing.assert_array_equal(runtime.hres_state_from, initial_hres_from)
    np.testing.assert_array_equal(runtime.hres_state_to, initial_hres_to)
    np.testing.assert_array_equal(full_params, initial_parameters)

    # Long delays still complete several wraps. Neither histories nor internal
    # buffers/states are reseeded; prescribe only the accepted port voltages.
    steps: int = max(401, 3 * runtime.buffer_size + 1)
    step: int
    for step in range(steps + 1):
        phase_advance: complex = advance ** step
        if step > 0:
            previous_advance: complex = advance ** (step - 1)
            x_prev[runtime.idx_vf] = np.real(voltage_from_phase * previous_advance)
            x_prev[runtime.idx_vt] = np.real(voltage_to_phase * previous_advance)
            runtime.update_history(step_counter=step, x_prev=x_prev, full_params=full_params)
        else:
            pass
        target_voltage_from: np.ndarray = np.real(voltage_from_phase * phase_advance)
        target_voltage_to: np.ndarray = np.real(voltage_to_phase * phase_advance)
        actual_current_from: np.ndarray = runtime.direct_yc_phase @ target_voltage_from + full_params[runtime.idx_p_hf]
        actual_current_to: np.ndarray = runtime.direct_yc_phase @ target_voltage_to + full_params[runtime.idx_p_ht]
        np.testing.assert_allclose(actual_current_from, np.real(current_from_phase * phase_advance), rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(actual_current_to, np.real(current_to_phase * phase_advance), rtol=0.0, atol=1e-12)
        expected_history_from: np.ndarray = np.real(
            (current_from_phase - runtime.direct_yc_phase @ voltage_from_phase) * phase_advance
        )
        expected_history_to: np.ndarray = np.real(
            (current_to_phase - runtime.direct_yc_phase @ voltage_to_phase) * phase_advance
        )
        np.testing.assert_allclose(full_params[runtime.idx_p_hf], expected_history_from, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(full_params[runtime.idx_p_ht], expected_history_to, rtol=0.0, atol=1e-12)



@pytest.mark.parametrize("three_phase", (False, True))
def test_jmarti_pf_caller_transports_conventional_phase_current(three_phase: bool) -> None:
    """Compare indexed constructor Norton currents with physical PF phase currents.

    The existing three-mode fit exercises transport through the real constructor;
    it does not assert equivalence between the fitted line and the static network.

    :param three_phase: Use asymmetric PF3 instead of balanced PF results.
    :return: None; assert ABC current-base transport and actual runtime identity.
    """
    # Keep the original solved network and source fixture, then attach the existing
    # fit through the same setter used by the actual JMARTI integration fixture.
    source_case: tuple[EmtProblemDae, gce.Generator] = _build_source_case(
        mode=TheveninSourceVoltageMode.Phase, three_phase=three_phase,
    )
    source_problem: EmtProblemDae = source_case[0]
    grid: gce.MultiCircuit = source_problem.grid
    line: gce.Line = grid.lines[0]
    model: Block = get_jmarti_line_emt_template(
        vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True,
        name="Attached history audit",
    ).block
    fit_bundle: object = _build_jmarti_fit_bundle_for_three_phase_line()
    assert isinstance(fit_bundle, JMartiFitBundle)
    set_jmarti_block_fit_bundle(block=model, fit_bundle=fit_bundle)
    set_emt_model(device=line, model=model, var_factory=grid.var_factory)

    # Derive the oracle from the provider's conventional RMS current base, before
    # the fresh constructor can transport or retain any history values.
    pf: PowerFlowResults | None = source_problem.power_flow_results
    pf3: PowerFlowResults3Ph | None = source_problem.power_flow_results_3ph
    voltage_from: np.ndarray
    voltage_to: np.ndarray
    current_from: np.ndarray
    current_to: np.ndarray
    power_from: np.ndarray
    power_to: np.ndarray
    if three_phase:
        assert pf3 is not None
        voltage_from = np.array((pf3.voltage_A[0], pf3.voltage_B[0], pf3.voltage_C[0]), dtype=complex)
        voltage_to = np.array((pf3.voltage_A[1], pf3.voltage_B[1], pf3.voltage_C[1]), dtype=complex)
        current_from = np.array((pf3.If_A[0], pf3.If_B[0], pf3.If_C[0]), dtype=complex)
        current_to = np.array((pf3.It_A[0], pf3.It_B[0], pf3.It_C[0]), dtype=complex)
        power_from = np.array((pf3.Sf_A[0], pf3.Sf_B[0], pf3.Sf_C[0]), dtype=complex)
        power_to = np.array((pf3.St_A[0], pf3.St_B[0], pf3.St_C[0]), dtype=complex)
    else:
        assert pf is not None
        rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
        voltage_from = complex(pf.voltage[0]) * rotation
        voltage_to = complex(pf.voltage[1]) * rotation
        current_from = complex(pf.If[0]) * rotation
        current_to = complex(pf.It[0]) * rotation
        power_from = pf.Sf.copy()
        power_to = pf.St.copy()

    # The constructor must create and index its own attached runtime; a foreign
    # fixture called after construction would bypass the production boundary.
    problem: EmtProblemDae = EmtProblemDae(
        grid=grid, options=source_problem.options, pf_results=pf, pf_results_3ph=pf3,
    )
    assert len(problem.history_models) == 1
    runtime_candidate: object = problem.history_models[0]
    assert isinstance(runtime_candidate, JMartiHistoryRuntime)
    runtime: JMartiHistoryRuntime = runtime_candidate
    assert runtime.line is line
    assert runtime.block is line.emt_model
    assert runtime.active_ph == list(("A", "B", "C"))
    history_variables: list[Var]
    variable: Var
    for history_variables in (runtime.Ih_f, runtime.Ih_t):
        for variable in history_variables:
            assert variable.uid in problem.uid2idx_event_params

    # The remote fit initializes voltage-driven internal waves. Its returned
    # Norton seed must still transport the independent physical PF currents at t0.
    assert runtime.idx_vf is not None
    assert runtime.idx_vt is not None
    assert runtime.idx_p_hf is not None
    assert runtime.idx_p_ht is not None
    initial_state: np.ndarray = problem.get_x0()
    np.testing.assert_allclose(
        initial_state[runtime.idx_vf], np.sqrt(2.0) * voltage_from.imag, rtol=0.0, atol=1e-12,
    )
    np.testing.assert_allclose(
        initial_state[runtime.idx_vt], np.sqrt(2.0) * voltage_to.imag, rtol=0.0, atol=1e-12,
    )
    reconstructed_from: np.ndarray = (
        runtime.direct_yc_phase @ initial_state[runtime.idx_vf]
        + problem.event_params_values[runtime.idx_p_hf]
    )
    reconstructed_to: np.ndarray = (
        runtime.direct_yc_phase @ initial_state[runtime.idx_vt]
        + problem.event_params_values[runtime.idx_p_ht]
    )
    np.testing.assert_allclose(reconstructed_from, np.sqrt(2.0) * current_from.imag, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(reconstructed_to, np.sqrt(2.0) * current_to.imag, rtol=0.0, atol=1e-12)

    # History transport consumes the solved provider; it must preserve its source
    # powers rather than change PF data to fit the dynamic fixture.
    if three_phase:
        assert pf3 is not None
        np.testing.assert_array_equal(
            np.array((pf3.Sf_A[0], pf3.Sf_B[0], pf3.Sf_C[0]), dtype=complex), power_from,
        )
        np.testing.assert_array_equal(
            np.array((pf3.St_A[0], pf3.St_B[0], pf3.St_C[0]), dtype=complex), power_to,
        )
    else:
        assert pf is not None
        np.testing.assert_array_equal(pf.Sf, power_from)
        np.testing.assert_array_equal(pf.St, power_to)



@pytest.mark.parametrize("three_phase", (False, True))
def test_jmarti_pf_caller_preserves_preindex_history_seed(three_phase: bool) -> None:
    """Verify attached history promotion, native replay and buffer rebuilding.

    :param three_phase: Use asymmetric PF3 instead of balanced PF results.
    :return: None; assert physical Ih seeds across actual indexed runtime stores.
    """
    # Public attachment precedes a fresh constructor so its production caller
    # seeds the same history UIDs later promoted into the canonical runtime.
    source_case: tuple[EmtProblemDae, gce.Generator] = _build_source_case(
        mode=TheveninSourceVoltageMode.Phase, three_phase=three_phase,
    )
    source_problem: EmtProblemDae = source_case[0]
    grid: gce.MultiCircuit = source_problem.grid
    line: gce.Line = grid.lines[0]
    model: Block = get_jmarti_line_emt_template(
        vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True,
        name="Attached history audit",
    ).block
    fit_bundle: object = _build_jmarti_fit_bundle_for_three_phase_line()
    assert isinstance(fit_bundle, JMartiFitBundle)
    set_jmarti_block_fit_bundle(block=model, fit_bundle=fit_bundle)
    set_emt_model(device=line, model=model, var_factory=grid.var_factory)
    problem: EmtProblemDae = EmtProblemDae(
        grid=grid, options=source_problem.options,
        pf_results=source_problem.power_flow_results,
        pf_results_3ph=source_problem.power_flow_results_3ph,
    )
    assert len(problem.history_models) == 1
    runtime_candidate: object = problem.history_models[0]
    assert isinstance(runtime_candidate, JMartiHistoryRuntime)
    runtime: JMartiHistoryRuntime = runtime_candidate
    assert runtime.line is line
    assert runtime.block is line.emt_model
    assert runtime.active_ph == list(("A", "B", "C"))
    assert runtime.idx_p_hf is not None
    assert runtime.idx_p_ht is not None

    # A history source must provide I(0)-Yc_direct*V(0) on the physical current
    # base. This independent Norton oracle does not certify a periodic line orbit.
    voltage_from: np.ndarray
    voltage_to: np.ndarray
    current_from: np.ndarray
    current_to: np.ndarray
    if three_phase:
        pf3: PowerFlowResults3Ph | None = problem.power_flow_results_3ph
        assert pf3 is not None
        voltage_from = np.array((pf3.voltage_A[0], pf3.voltage_B[0], pf3.voltage_C[0]), dtype=complex)
        voltage_to = np.array((pf3.voltage_A[1], pf3.voltage_B[1], pf3.voltage_C[1]), dtype=complex)
        current_from = np.array((pf3.If_A[0], pf3.If_B[0], pf3.If_C[0]), dtype=complex)
        current_to = np.array((pf3.It_A[0], pf3.It_B[0], pf3.It_C[0]), dtype=complex)
    else:
        pf: PowerFlowResults | None = problem.power_flow_results
        assert pf is not None
        rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
        voltage_from = complex(pf.voltage[0]) * rotation
        voltage_to = complex(pf.voltage[1]) * rotation
        current_from = complex(pf.If[0]) * rotation
        current_to = complex(pf.It[0]) * rotation
    expected_from: np.ndarray = np.real(
        np.sqrt(2.0) * current_from.imag - runtime.direct_yc_phase @ (np.sqrt(2.0) * voltage_from.imag)
    )
    expected_to: np.ndarray = np.real(
        np.sqrt(2.0) * current_to.imag - runtime.direct_yc_phase @ (np.sqrt(2.0) * voltage_to.imag)
    )
    assert np.max(np.abs(expected_from)) > 0.0
    assert np.max(np.abs(expected_to)) > 0.0

    # Inspect each real lifecycle stage. The preserved source equations must keep
    # a later rebuild/reset from restoring the original zero history placeholders.
    stage_index: int
    side_index: int
    phase_index: int
    history_variables: list[Var]
    mapped_indices: list[int]
    expected_history: np.ndarray
    for stage_index in range(3):
        if stage_index == 1:
            problem.rebuild_runtime_param_vectors()
        elif stage_index == 2:
            problem.set_events_group(emt_events_group=None)
        else:
            pass
        for side_index in range(2):
            if side_index == 0:
                history_variables = runtime.Ih_f
                mapped_indices = runtime.idx_p_hf
                expected_history = expected_from
            else:
                history_variables = runtime.Ih_t
                mapped_indices = runtime.idx_p_ht
                expected_history = expected_to
            for phase_index in range(runtime.m):
                uid: int = history_variables[phase_index].uid
                runtime_index: int | None = problem.uid2idx_event_params.get(uid, None)
                assert runtime_index is not None
                assert mapped_indices[phase_index] == runtime_index
                temporary: float | None = problem._temp_init_guess.get(uid, None)
                preserved: float | None = problem._temp_post_init_guess.get(uid, None)
                promoted: float | None = problem.event_params_init_dict.get(uid, None)
                assert temporary is not None
                assert preserved is not None
                assert promoted is not None
                source_equation: Expr = problem._event_parameters_eqs[runtime_index]
                replay_equation: Expr = problem._runtime_parameter_eqs0[runtime_index]
                assert isinstance(source_equation, Const)
                assert isinstance(replay_equation, Const)
                assert source_equation.value is not None
                assert replay_equation.value is not None
                actual_stores: np.ndarray = np.array((
                    temporary, preserved, promoted, problem.event_params_values[runtime_index],
                    float(source_equation.value), float(replay_equation.value),
                ), dtype=float)
                expected_stores: np.ndarray = np.full(actual_stores.size, expected_history[phase_index])
                np.testing.assert_allclose(
                    actual_stores, expected_stores, rtol=0.0, atol=1e-12,
                    err_msg=f"History UID {uid} did not survive lifecycle stage {stage_index}",
                )



@pytest.mark.parametrize("frequency_hz", (0.0, 50.0, 60.0))
def test_jmarti_runtime_periodic_delay_memory_matches_retarded_samples(frequency_hz: float) -> None:
    """Compare native retained waves and interpolation with negative-time samples.

    The original fitted fixture is used only to diagnose memory; its complex
    modal kernel is not claimed to represent a real physical line orbit.

    :param frequency_hz: Excitation frequency, including the constant limit.
    :return: None; assert both buffers and current/next delayed incident samples.
    """
    fixture: tuple[JMartiHistoryRuntime, np.ndarray, np.ndarray, np.ndarray] = _build_jmarti_runtime_fixture()
    runtime: JMartiHistoryRuntime = fixture[0]
    voltage_from: np.ndarray = np.array((1.0 - 0.2j, 0.95 - 0.1j), dtype=complex)
    voltage_to: np.ndarray = np.array((0.98 - 0.18j, 0.92 - 0.09j), dtype=complex)
    current_from: np.ndarray = np.array((0.04 - 0.01j, -0.03 + 0.02j), dtype=complex)
    current_to: np.ndarray = np.array((-0.039 + 0.009j, 0.028 - 0.019j), dtype=complex)

    # Independently solve the voltage telegrapher boundary for both frequency
    # signs. The complex synthetic kernel cannot use a conjugate-wave shortcut.
    inverse_transform: np.ndarray = runtime.runtime_data.get_modal_transform_inv()
    analytic_from: np.ndarray = -1j * np.sqrt(2.0) * voltage_from
    analytic_to: np.ndarray = -1j * np.sqrt(2.0) * voltage_to
    angular_step: float = 2.0 * np.pi * frequency_hz * runtime.h
    advances: np.ndarray = np.exp(1j * angular_step * np.array((1.0, -1.0)))
    outgoing_from: np.ndarray = np.empty((2, runtime.m), dtype=complex)
    outgoing_to: np.ndarray = np.empty((2, runtime.m), dtype=complex)
    sign_index: int
    mode_index: int
    for sign_index in range(2):
        advance: complex = complex(advances[sign_index])
        voltage_from_modal: np.ndarray
        voltage_to_modal: np.ndarray
        if sign_index == 0:
            voltage_from_modal = inverse_transform @ analytic_from / 2.0
            voltage_to_modal = inverse_transform @ analytic_to / 2.0
        else:
            voltage_from_modal = inverse_transform @ analytic_from.conj() / 2.0
            voltage_to_modal = inverse_transform @ analytic_to.conj() / 2.0
        for mode_index in range(runtime.m):
            mode: JMartiModeRuntimeData = runtime.runtime_data.get_mode_data()[mode_index]
            lag: int = mode.get_delay_step_count()
            fraction: float = mode.get_residual_delay_s() / runtime.h
            assert lag >= 1
            assert 0.0 <= fraction <= 1.0
            delay: complex = (1.0 - fraction) * advance ** (-lag) + fraction * advance ** (-lag - 1)
            propagation: complex = complex(delay * (mode.get_hres_constant_term() + np.sum(
                mode.get_hres_beta() / (advance - mode.get_hres_alpha()),
            )))
            denominator: complex = 1.0 - propagation * propagation
            assert abs(denominator) > 1e-12
            outgoing_from[sign_index, mode_index] = (
                voltage_from_modal[mode_index] - propagation * voltage_to_modal[mode_index]
            ) / denominator
            outgoing_to[sign_index, mode_index] = (
                voltage_to_modal[mode_index] - propagation * voltage_from_modal[mode_index]
            ) / denominator
    runtime.initialize_from_fundamental_phasors(
        v_f0_phasor_red=voltage_from, v_t0_phasor_red=voltage_to,
        i_f0_phasor_red=current_from, i_t0_phasor_red=current_to,
        system_frequency_hz=frequency_hz,
    )

    # Slot zero is the present sample; every other retained slot is a signed
    # negative sample before n=0, even when several periods span the ring.
    signed_samples: np.ndarray = np.arange(runtime.buffer_size, dtype=np.int64) - runtime.buffer_size
    signed_samples[0] = 0
    expected_from: np.ndarray = np.zeros_like(runtime.buf_a_f)
    expected_to: np.ndarray = np.zeros_like(runtime.buf_a_t)
    for sign_index in range(2):
        phase_samples: np.ndarray = advances[sign_index] ** signed_samples
        expected_from += phase_samples[:, None] * outgoing_from[sign_index, None, :]
        expected_to += phase_samples[:, None] * outgoing_to[sign_index, None, :]
    np.testing.assert_allclose(runtime.buf_a_f, expected_from, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.buf_a_t, expected_to, rtol=0.0, atol=1e-12)

    # Check the actual sampler at both terminals and both n0 and n1 query times.
    # Its fractional interpolation is independently evaluated at retarded times.
    next_step: bool
    buffer_values: np.ndarray
    outgoing_amplitude: np.ndarray
    for mode_index in range(runtime.m):
        mode: JMartiModeRuntimeData = runtime.runtime_data.get_mode_data()[mode_index]
        lag: int = mode.get_delay_step_count()
        fraction: float = mode.get_residual_delay_s() / runtime.h
        assert lag >= 1
        for buffer_values, outgoing_amplitude in (
            (runtime.buf_a_f, outgoing_from), (runtime.buf_a_t, outgoing_to),
        ):
            for next_step in (False, True):
                query_sample: int = 1 if next_step else 0
                expected_sample: complex = 0.0 + 0.0j
                for sign_index in range(2):
                    advance = complex(advances[sign_index])
                    expected_sample += complex(outgoing_amplitude[sign_index, mode_index]) * (
                        (1.0 - fraction) * advance ** (query_sample - lag)
                        + fraction * advance ** (query_sample - lag - 1)
                    )
                actual_sample: complex = _get_delayed_incident_wave(
                    runtime=runtime, mode_index=mode_index, step_counter=0,
                    remote_incident_buffer=buffer_values, next_step=next_step,
                )
                np.testing.assert_allclose(actual_sample, expected_sample, rtol=0.0, atol=1e-12)



@pytest.mark.parametrize("delay_steps,frequency_hz,zero_order_filters,propagation_gap,incompatible_currents,zero_admittance,admittance_scale,invalid_input,invalid_is_current,invalid_from_side", (
    (0.0, 50.0, False, None, False, False, 1.0, None, False, False),
    (0.5, 50.0, False, None, False, False, 1.0, None, False, False),
    (0.5, 0.0, False, None, False, False, 1.0, None, False, False),
    (3.0, 50.0, False, None, False, False, 1.0, None, False, False),
    (3.5, 50.0, False, None, False, False, 1.0, None, False, False),
    (100.125, 50.0, False, None, False, False, 1.0, None, False, False),
    (3.5, 60.0, False, None, False, False, 1.0, None, False, False),
    (3.5, 0.0, False, None, False, False, 1.0, None, False, False),
    (3.5, 50.0, True, None, False, False, 1.0, None, False, False),
    (3.0, 0.0, False, 0.0, False, False, 1.0, None, False, False),
    (3.0, 0.0, False, 5e-15, False, False, 1.0, None, False, False),
    (3.0, 0.0, False, 1e-3, False, False, 1.0, None, False, False),
    (3.0, 0.0, False, 0.0, True, False, 1.0, None, False, False),
    (3.0, 0.0, True, 0.0, False, True, 1.0, None, False, False),
    (3.0, 0.0, False, 0.0, False, False, 1e-15, None, False, False),
    (3.0, 50.0, False, None, False, False, 1.0, np.nan, False, True),
    (3.0, 50.0, False, None, False, False, 1.0, np.inf, False, True),
    (3.0, 50.0, False, None, False, False, 1.0, np.nan, False, False),
    (3.0, 50.0, False, None, False, False, 1.0, np.inf, False, False),
    (3.0, 50.0, False, None, False, False, 1.0, np.nan, True, True),
    (3.0, 50.0, False, None, False, False, 1.0, np.inf, True, True),
    (3.0, 50.0, False, None, False, False, 1.0, np.nan, True, False),
    (3.0, 50.0, False, None, False, False, 1.0, np.inf, True, False),
))
def test_jmarti_runtime_periodic_initialization_preserves_discrete_two_port_orbit(
        delay_steps: float, frequency_hz: float, zero_order_filters: bool,
        propagation_gap: float | None, incompatible_currents: bool, zero_admittance: bool,
        admittance_scale: float, invalid_input: float | None,
        invalid_is_current: bool, invalid_from_side: bool,
) -> None:
    """Drive the actual updater with an independently consistent real port orbit.

    This validates the declared discrete line kernel with prescribed voltages;
    it does not certify a fitted static line or interconnected network orbit.

    :param delay_steps: Causal delay in steps for the first heterogeneous mode.
    :param frequency_hz: Periodic excitation frequency or its constant limit.
    :param zero_order_filters: Use only direct kernel terms and no filter states.
    :param propagation_gap: Optional distance of direct propagation from unity.
    :param incompatible_currents: Reject mismatched singular terminal currents.
    :param zero_admittance: Reject an unresolved zero-Yc singular boundary.
    :param admittance_scale: Preserve finite nonzero full Yc at small magnitude.
    :param invalid_input: Optional NaN/Inf terminal input for nonmutation checks.
    :param invalid_is_current: Contaminate current rather than voltage.
    :param invalid_from_side: Contaminate from-side rather than to-side input.
    :return: None; assert compatible orbit or unchanged stores after rejection.
    """
    fixture: tuple[JMartiHistoryRuntime, np.ndarray, np.ndarray, np.ndarray] = _build_jmarti_runtime_fixture()
    original: JMartiHistoryRuntime = fixture[0]
    x_prev: np.ndarray = fixture[1]
    full_params: np.ndarray = fixture[2]
    assert original.v_f_vars is not None
    assert original.v_t_vars is not None
    assert original.idx_vf is not None
    assert original.idx_vt is not None
    assert original.idx_p_hf is not None
    assert original.idx_p_ht is not None

    # Explicit real stable coefficients isolate periodic initialization from the
    # old fitted fixture's unpaired complex kernel. Each mode has a distinct lag.
    if delay_steps < 1.0:
        mode_delays: tuple[float, float] = (delay_steps, delay_steps + 0.25)
    elif delay_steps == 3.0:
        mode_delays = (3.0, 4.0)
    elif delay_steps == 100.125:
        mode_delays = (100.125, 87.75)
    else:
        mode_delays = (3.5, 5.25)
    mode_records: list[JMartiModeRuntimeData | None] = list((None, None))
    mode_index: int
    for mode_index in range(2):
        lag: int = int(np.floor(mode_delays[mode_index]))
        fraction: float = mode_delays[mode_index] - lag
        yc_poles: np.ndarray
        yc_residues: np.ndarray
        hres_poles: np.ndarray
        hres_residues: np.ndarray
        if zero_order_filters:
            yc_poles = np.zeros(0, dtype=complex)
            yc_residues = np.zeros(0, dtype=complex)
            hres_poles = np.zeros(0, dtype=complex)
            hres_residues = np.zeros(0, dtype=complex)
        else:
            yc_poles = np.array((-50.0 - 30.0 * mode_index,), dtype=complex)
            yc_residues = np.array((0.3 - 0.1 * mode_index,), dtype=complex)
            hres_poles = np.array((-80.0 - 40.0 * mode_index,), dtype=complex)
            hres_residues = np.array((0.02 - 0.005 * mode_index,), dtype=complex)
        # Unity propagation at DC makes the voltage boundary singular. Keep
        # the dynamic Yc terms to prove the repair uses full Yc, not its direct term.
        if propagation_gap is not None:
            hres_poles = np.zeros(0, dtype=complex)
            hres_residues = np.zeros(0, dtype=complex)
            hres_constant: complex = complex(1.0 - propagation_gap)
        else:
            hres_constant = complex(0.8 - 0.1 * mode_index)
        if zero_admittance:
            yc_poles = np.zeros(0, dtype=complex)
            yc_residues = np.zeros(0, dtype=complex)
            yc_constant: complex = 0.0 + 0.0j
        else:
            yc_constant = complex(0.1 - 0.02 * mode_index)
        yc_residues *= admittance_scale
        yc_constant *= admittance_scale
        yc_alpha: np.ndarray = np.exp(yc_poles * original.h)
        yc_beta: np.ndarray = yc_residues * np.expm1(yc_poles * original.h) / yc_poles
        hres_alpha: np.ndarray = np.exp(hres_poles * original.h)
        hres_beta: np.ndarray = hres_residues * np.expm1(hres_poles * original.h) / hres_poles
        mode_records[mode_index] = JMartiModeRuntimeData(
            mode_index=mode_index, tau_s=mode_delays[mode_index] * original.h,
            delay_step_count=lag, residual_delay_s=fraction * original.h,
            yc_poles_s=yc_poles, yc_residues=yc_residues,
            yc_constant_term=yc_constant, yc_proportional_term=0.0 + 0.0j,
            hres_poles_s=hres_poles, hres_residues=hres_residues,
            hres_constant_term=hres_constant, hres_proportional_term=0.0 + 0.0j,
            yc_alpha=yc_alpha, yc_beta=yc_beta, hres_alpha=hres_alpha, hres_beta=hres_beta,
        )
    assert mode_records[0] is not None
    assert mode_records[1] is not None
    transform: np.ndarray = np.array(((0.8, -0.6), (0.6, 0.8)), dtype=complex)
    data: JMartiRuntimeData = JMartiRuntimeData(
        time_step_s=original.h, line_length_m=1000.0, phase_labels=("A", "B"),
        modal_transform=transform, modal_transform_inv=transform.T,
        reference_frequency_hz=50.0, mode_data=(mode_records[0], mode_records[1]),
    )
    set_jmarti_block_runtime_data(block=original.block, runtime_data=data)
    if delay_steps == 0.0:
        # Matching-h input retains its declared identity, but all consumed
        # channels must be checked before the first short mode declares waves.
        checked_mode: JMartiModeRuntimeData = data.get_mode_data()[1]
        ya: np.ndarray = checked_mode.get_yc_alpha()
        yb: np.ndarray = checked_mode.get_yc_beta()
        ha: np.ndarray = checked_mode.get_hres_alpha()
        hb: np.ndarray = checked_mode.get_hres_beta()
        yd: complex = checked_mode.get_yc_constant_term()
        hd: complex = checked_mode.get_hres_constant_term()
        residual_value: float = checked_mode.get_residual_delay_s()
        invalid_inputs: tuple[tuple[int, float, complex, complex, np.ndarray, np.ndarray, np.ndarray, np.ndarray], ...] = (
            (0, np.nan, yd, hd, ya, yb, ha, hb),
            (0, np.inf, yd, hd, ya, yb, ha, hb),
            (0, -np.inf, yd, hd, ya, yb, ha, hb),
            (-1, residual_value, yd, hd, ya, yb, ha, hb),
            (0, residual_value, complex(np.nan), hd, ya, yb, ha, hb),
            (0, residual_value, complex(np.inf), hd, ya, yb, ha, hb),
            (0, residual_value, yd, complex(np.nan), ya, yb, ha, hb),
            (0, residual_value, yd, complex(np.inf), ya, yb, ha, hb),
            (0, residual_value, yd, hd, np.array(0.9, dtype=complex), yb, ha, hb),
            (0, residual_value, yd, hd, ya, np.array(0.003, dtype=complex), ha, hb),
            (0, residual_value, yd, hd, ya, np.empty(0, dtype=complex), ha, hb),
            (0, residual_value, yd, hd, np.full_like(ya, np.nan), yb, ha, hb),
            (0, residual_value, yd, hd, ya, np.full_like(yb, np.inf), ha, hb),
            (0, residual_value, yd, hd, ya, yb, np.full_like(ha, np.nan), hb),
            (0, residual_value, yd, hd, ya, yb, ha, np.empty(0, dtype=complex)),
        )
        variable: Var
        source_events: tuple[int, ...] = tuple(variable.uid for variable in original.block.event_dict)
        source_algebraic: tuple[int, ...] = tuple(variable.uid for variable in original.block.algebraic_vars)
        invalid_lag: int
        invalid_residual: float
        invalid_yd: complex
        invalid_hd: complex
        invalid_ya: np.ndarray
        invalid_yb: np.ndarray
        invalid_ha: np.ndarray
        invalid_hb: np.ndarray
        for invalid_lag, invalid_residual, invalid_yd, invalid_hd, invalid_ya, invalid_yb, invalid_ha, invalid_hb in invalid_inputs:
            invalid_mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
                1, checked_mode.get_tau_s(), invalid_lag, invalid_residual,
                checked_mode.get_yc_poles_s(), checked_mode.get_yc_residues(), invalid_yd, 0j,
                checked_mode.get_hres_poles_s(), checked_mode.get_hres_residues(), invalid_hd, 0j,
                invalid_ya, invalid_yb, invalid_ha, invalid_hb,
            )
            invalid_data: JMartiRuntimeData = JMartiRuntimeData(original.h, 1000.0, ("A", "B"),
                transform, transform.T, 50.0, (data.get_mode_data()[0], invalid_mode))
            set_jmarti_block_runtime_data(original.block, invalid_data)
            with pytest.raises(ValueError, match="consumed runtime"):
                JMartiHistoryRuntime(original.line, original.block, original.h)
            assert get_jmarti_block_runtime_data(original.block) is invalid_data
            assert tuple(variable.uid for variable in original.block.event_dict) == source_events
            assert tuple(variable.uid for variable in original.block.algebraic_vars) == source_algebraic
        # Both direct inputs are finite, but their product cannot enter a
        # representable current row. Reject before allocating private Vars.
        overflow_mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
            1, 0.0, 0, 0.0, np.empty(0, dtype=complex), np.empty(0, dtype=complex), 1e308, 0j,
            np.empty(0, dtype=complex), np.empty(0, dtype=complex), 1e308, 0j,
            np.empty(0, dtype=complex), np.empty(0, dtype=complex),
            np.empty(0, dtype=complex), np.empty(0, dtype=complex),
        )
        overflow_data: JMartiRuntimeData = JMartiRuntimeData(original.h, 1000.0, ("A", "B"),
            transform, transform.T, 50.0, (data.get_mode_data()[0], overflow_mode))
        set_jmarti_block_runtime_data(original.block, overflow_data)
        with pytest.raises(ValueError, match="not representable"):
            JMartiHistoryRuntime(original.line, original.block, original.h)
        assert get_jmarti_block_runtime_data(original.block) is overflow_data
        assert tuple(variable.uid for variable in original.block.event_dict) == source_events
        assert tuple(variable.uid for variable in original.block.algebraic_vars) == source_algebraic
        # The producer's valid negative endpoint stays literal source data.
        # The existing sampler alone applies its established effective weight.
        endpoint_tau: float = 0.0009
        endpoint_residual: float = endpoint_tau - 9 * original.h
        assert endpoint_residual < 0.0
        endpoint_mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
            1, endpoint_tau, 9, endpoint_residual,
            checked_mode.get_yc_poles_s(), checked_mode.get_yc_residues(), yd, 0j,
            checked_mode.get_hres_poles_s(), checked_mode.get_hres_residues(), hd, 0j,
            ya, yb, ha, hb,
        )
        endpoint_data: JMartiRuntimeData = JMartiRuntimeData(original.h, 1000.0, ("A", "B"),
            transform, transform.T, 50.0, (data.get_mode_data()[0], endpoint_mode))
        set_jmarti_block_runtime_data(original.block, endpoint_data)
        endpoint_runtime: JMartiHistoryRuntime = JMartiHistoryRuntime(original.line, original.block, original.h)
        assert endpoint_runtime.runtime_data is endpoint_data
        assert get_jmarti_block_runtime_data(original.block) is endpoint_data
        assert endpoint_mode.get_residual_delay_s() == endpoint_residual
        endpoint_runtime.buf_a_t[:, 1] = np.arange(endpoint_runtime.buffer_size)
        endpoint_sample: complex = _get_delayed_incident_wave(endpoint_runtime, 1, 0, endpoint_runtime.buf_a_t, False)
        assert endpoint_sample == endpoint_runtime.buf_a_t[(-9) % endpoint_runtime.buffer_size, 1]
        assert tuple(variable.uid for variable in original.block.event_dict) == source_events
        assert tuple(variable.uid for variable in original.block.algebraic_vars) == source_algebraic
        # A finite vector is not an m*m current operator. This causal case
        # checks only consumed dimensions, not a new B0 inverse-identity policy.
        first_mode: JMartiModeRuntimeData = data.get_mode_data()[0]
        causal_first_mode: JMartiModeRuntimeData = JMartiModeRuntimeData(
            0, 3 * original.h, 3, 0.0,
            first_mode.get_yc_poles_s(), first_mode.get_yc_residues(), first_mode.get_yc_constant_term(), 0j,
            first_mode.get_hres_poles_s(), first_mode.get_hres_residues(), first_mode.get_hres_constant_term(), 0j,
            first_mode.get_yc_alpha(), first_mode.get_yc_beta(), first_mode.get_hres_alpha(), first_mode.get_hres_beta(),
        )
        invalid_dimensions: JMartiRuntimeData = JMartiRuntimeData(original.h, 1000.0, ("A", "B"),
            transform[0], transform.T, 50.0, (causal_first_mode, endpoint_mode))
        set_jmarti_block_runtime_data(original.block, invalid_dimensions)
        with pytest.raises(ValueError, match="phase admittance"):
            JMartiHistoryRuntime(original.line, original.block, original.h)
        assert get_jmarti_block_runtime_data(original.block) is invalid_dimensions
        assert tuple(variable.uid for variable in original.block.event_dict) == source_events
        assert tuple(variable.uid for variable in original.block.algebraic_vars) == source_algebraic
        set_jmarti_block_runtime_data(original.block, data)
    else:
        pass
    runtime: JMartiHistoryRuntime = JMartiHistoryRuntime(
        line=original.line, line_block=original.block, h=original.h,
    )
    runtime.bind_terminals(v_f_vars=original.v_f_vars, v_t_vars=original.v_t_vars)
    variable_indices: dict[int, int] = dict()
    parameter_indices: dict[int, int] = dict()
    for mode_index in range(runtime.m):
        variable_indices[original.v_f_vars[mode_index].uid] = original.idx_vf[mode_index]
        variable_indices[original.v_t_vars[mode_index].uid] = original.idx_vt[mode_index]
        parameter_indices[runtime.Ih_f[mode_index].uid] = original.idx_p_hf[mode_index]
        parameter_indices[runtime.Ih_t[mode_index].uid] = original.idx_p_ht[mode_index]
    # Unit coverage supplies the independently solved accepted wave into the
    # runtime's own declared coordinates. Attached network tests solve these
    # coordinates through shared g rather than prescribing them.
    next_variable: int = x_prev.size
    next_parameter: int = full_params.size
    wave_group: list[Var]
    q_group: list[Var]
    variable: Var
    for wave_group in (runtime.outgoing_wave_f_re, runtime.outgoing_wave_t_re,
                       runtime.outgoing_wave_f_im, runtime.outgoing_wave_t_im):
        for variable in wave_group:
            variable_indices[variable.uid] = next_variable
            next_variable += 1
    for q_group in (runtime.incoming_voltage_f_re, runtime.incoming_voltage_t_re,
                    runtime.incoming_voltage_f_im, runtime.incoming_voltage_t_im):
        for variable in q_group:
            parameter_indices[variable.uid] = next_parameter
            next_parameter += 1
    x_prev = np.zeros(next_variable)
    full_params = np.zeros(next_parameter)
    runtime.setup_indices(uid2idx_vars=variable_indices, uid2idx_event_params=parameter_indices)
    assert runtime.idx_vf is not None
    assert runtime.idx_vt is not None
    assert runtime.idx_p_hf is not None
    assert runtime.idx_p_ht is not None
    np.testing.assert_allclose(transform.T @ transform, np.eye(2), rtol=0.0, atol=1e-12)

    # Choose nontrivial outgoing analytic amplitudes, then solve the two native
    # difference-equation ports jointly. Arbitrary currents would hide drift.
    advance: complex = complex(np.exp(2j * np.pi * frequency_hz * runtime.h))
    outgoing_from: np.ndarray = np.array((0.8 - 0.2j, -0.3 + 0.7j), dtype=complex)
    outgoing_to: np.ndarray = np.array((0.5 + 0.4j, 0.6 - 0.1j), dtype=complex)
    voltage_from: np.ndarray = np.empty(runtime.m, dtype=complex)
    voltage_to: np.ndarray = np.empty(runtime.m, dtype=complex)
    current_from: np.ndarray = np.empty(runtime.m, dtype=complex)
    current_to: np.ndarray = np.empty(runtime.m, dtype=complex)
    expected_yc_from: np.ndarray = np.zeros_like(runtime.yc_state_from)
    expected_yc_to: np.ndarray = np.zeros_like(runtime.yc_state_to)
    expected_hres_from: np.ndarray = np.zeros_like(runtime.hres_state_from)
    expected_hres_to: np.ndarray = np.zeros_like(runtime.hres_state_to)
    for mode_index in range(runtime.m):
        mode: JMartiModeRuntimeData = data.get_mode_data()[mode_index]
        lag: int = mode.get_delay_step_count()
        fraction: float = mode.get_residual_delay_s() / runtime.h
        delay_transfer: complex = (1.0 - fraction) * advance ** (-lag) + fraction * advance ** (-lag - 1)
        yc_transfer: complex = complex(mode.get_yc_constant_term() + np.sum(
            mode.get_yc_beta() / (advance - mode.get_yc_alpha()),
        ))
        hres_transfer: complex = complex(mode.get_hres_constant_term() + np.sum(
            mode.get_hres_beta() / (advance - mode.get_hres_alpha()),
        ))
        delayed_from: complex = complex(delay_transfer * outgoing_to[mode_index])
        delayed_to: complex = complex(delay_transfer * outgoing_from[mode_index])
        # Telegrapher ports use the full discrete admittance and propagation;
        # the direct Norton term alone does not define the outgoing wave.
        incoming_from: complex = hres_transfer * delayed_from
        incoming_to: complex = hres_transfer * delayed_to
        voltage_from[mode_index] = outgoing_from[mode_index] + incoming_from
        voltage_to[mode_index] = outgoing_to[mode_index] + incoming_to
        current_from[mode_index] = yc_transfer * (outgoing_from[mode_index] - incoming_from)
        current_to[mode_index] = yc_transfer * (outgoing_to[mode_index] - incoming_to)
        yc_count: int = int(runtime.yc_order_counts[mode_index])
        hres_count: int = int(runtime.hres_order_counts[mode_index])
        expected_hres_from[mode_index, :hres_count] = np.real(mode.get_hres_beta() * delayed_from / (advance - mode.get_hres_alpha()))
        expected_hres_to[mode_index, :hres_count] = np.real(mode.get_hres_beta() * delayed_to / (advance - mode.get_hres_alpha()))
        expected_yc_from[mode_index, :yc_count] = np.real(mode.get_yc_beta() * (
            voltage_from[mode_index] - 2.0 * hres_transfer * delayed_from
        ) / (advance - mode.get_yc_alpha()))
        expected_yc_to[mode_index, :yc_count] = np.real(mode.get_yc_beta() * (
            voltage_to[mode_index] - 2.0 * hres_transfer * delayed_to
        ) / (advance - mode.get_yc_alpha()))
    voltage_from_phase: np.ndarray = transform @ voltage_from
    voltage_to_phase: np.ndarray = transform @ voltage_to
    current_from_phase: np.ndarray = transform @ current_from
    current_to_phase: np.ndarray = transform @ current_to

    # Invalid singular data must fail preflight without changing an existing
    # initialized runtime; no fabricated fallback is accepted as physical data.
    if incompatible_currents or zero_admittance or invalid_input is not None:
        if zero_admittance:
            # No valid singular Y=0 source exists; preserve declared defaults.
            pass
        else:
            runtime.initialize_from_fundamental_phasors(
                1j * voltage_from_phase / np.sqrt(2.0), 1j * voltage_to_phase / np.sqrt(2.0),
                1j * current_from_phase / np.sqrt(2.0), 1j * current_to_phase / np.sqrt(2.0), frequency_hz,
            )
        retained_arrays: tuple[np.ndarray, ...] = (
            runtime.buf_a_f, runtime.buf_a_t, runtime.yc_state_from,
            runtime.yc_state_to, runtime.hres_state_from, runtime.hres_state_to, full_params,
        )
        retained_copies: tuple[np.ndarray, ...] = tuple(array.copy() for array in retained_arrays)
        if incompatible_currents:
            current_from_phase[0] += 0.1
        else:
            pass
        rms_voltage_from: np.ndarray = 1j * voltage_from_phase / np.sqrt(2.0)
        rms_voltage_to: np.ndarray = 1j * voltage_to_phase / np.sqrt(2.0)
        rms_current_from: np.ndarray = 1j * current_from_phase / np.sqrt(2.0)
        rms_current_to: np.ndarray = 1j * current_to_phase / np.sqrt(2.0)
        failure_message: str
        if invalid_input is not None:
            failure_message = "not finite"
            if invalid_is_current:
                if invalid_from_side:
                    rms_current_from[0] = complex(invalid_input, 0.0)
                else:
                    rms_current_to[0] = complex(invalid_input, 0.0)
            else:
                if invalid_from_side:
                    rms_voltage_from[0] = complex(invalid_input, 0.0)
                else:
                    rms_voltage_to[0] = complex(invalid_input, 0.0)
        else:
            failure_message = "singular boundary"
        with pytest.raises(ValueError, match=failure_message):
            runtime.initialize_from_fundamental_phasors(
                v_f0_phasor_red=rms_voltage_from, v_t0_phasor_red=rms_voltage_to,
                i_f0_phasor_red=rms_current_from, i_t0_phasor_red=rms_current_to,
                system_frequency_hz=frequency_hz,
            )
        array_index: int
        for array_index in range(len(retained_arrays)):
            np.testing.assert_array_equal(retained_arrays[array_index], retained_copies[array_index])
        return
    else:
        pass

    # Initialize exactly once. The remaining run supplies only accepted terminal
    # voltages; it never resets buffers, filter states, histories or currents.
    history_from: np.ndarray
    history_to: np.ndarray
    if frequency_hz == 0.0:
        history_from, history_to = runtime.initialize_from_initial_point(
            voltage_from_phase.real, voltage_to_phase.real,
            current_from_phase.real, current_to_phase.real,
        )
    else:
        history_from, history_to = runtime.initialize_from_fundamental_phasors(
            v_f0_phasor_red=1j * voltage_from_phase / np.sqrt(2.0),
            v_t0_phasor_red=1j * voltage_to_phase / np.sqrt(2.0),
            i_f0_phasor_red=1j * current_from_phase / np.sqrt(2.0),
            i_t0_phasor_red=1j * current_to_phase / np.sqrt(2.0),
            system_frequency_hz=frequency_hz,
        )
    full_params[runtime.idx_p_hf] = history_from.real
    full_params[runtime.idx_p_ht] = history_to.real
    if runtime.coupling_block is not None:
        full_params[runtime.idx_q_f_re] = runtime.initial_voltage_offsets[0].real
        full_params[runtime.idx_q_t_re] = runtime.initial_voltage_offsets[1].real
        assert runtime.phase_real_kernel
        expected_wave_vars: list[Var] = list((runtime.outgoing_wave_f_re[0],)) * (2 * runtime.m)
        for mode_index in range(runtime.m):
            expected_wave_vars[mode_index] = runtime.outgoing_wave_f_re[mode_index]
            expected_wave_vars[runtime.m + mode_index] = runtime.outgoing_wave_t_re[mode_index]
        assert runtime.coupling_block.algebraic_vars == expected_wave_vars
        outgoing_from_phase: np.ndarray = transform @ outgoing_from
        outgoing_to_phase: np.ndarray = transform @ outgoing_to
    else:
        outgoing_from_phase = transform @ outgoing_from
        outgoing_to_phase = transform @ outgoing_to
    np.testing.assert_allclose(runtime.hres_state_from, expected_hres_from, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.hres_state_to, expected_hres_to, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.yc_state_from, expected_yc_from, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.yc_state_to, expected_yc_to, rtol=0.0, atol=1e-12)

    # Tiny currents cannot hide incorrect recovered wave amplitude behind
    # an absolute current tolerance. Check the physical outgoing waves directly.
    np.testing.assert_allclose(runtime.buf_a_f[0], outgoing_from.real, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.buf_a_t[0], outgoing_to.real, rtol=0.0, atol=1e-12)

    # The startup call must preserve every initialized store. A target-step
    # call at k subsequently consumes only the accepted voltage at k-1.
    initial_buffers_from: np.ndarray = runtime.buf_a_f.copy()
    initial_buffers_to: np.ndarray = runtime.buf_a_t.copy()
    initial_yc_from: np.ndarray = runtime.yc_state_from.copy()
    initial_yc_to: np.ndarray = runtime.yc_state_to.copy()
    initial_hres_from: np.ndarray = runtime.hres_state_from.copy()
    initial_hres_to: np.ndarray = runtime.hres_state_to.copy()
    initial_parameters: np.ndarray = full_params.copy()
    x_prev[runtime.idx_vf] = voltage_from_phase.real
    x_prev[runtime.idx_vt] = voltage_to_phase.real
    runtime.update_history(step_counter=0, x_prev=x_prev, full_params=full_params)
    np.testing.assert_array_equal(runtime.buf_a_f, initial_buffers_from)
    np.testing.assert_array_equal(runtime.buf_a_t, initial_buffers_to)
    np.testing.assert_array_equal(runtime.yc_state_from, initial_yc_from)
    np.testing.assert_array_equal(runtime.yc_state_to, initial_yc_to)
    np.testing.assert_array_equal(runtime.hres_state_from, initial_hres_from)
    np.testing.assert_array_equal(runtime.hres_state_to, initial_hres_to)
    np.testing.assert_array_equal(full_params, initial_parameters)

    # Long delays still complete several wraps. Neither histories nor internal
    # buffers/states are reseeded; prescribe only the accepted port voltages.
    steps: int = max(401, 3 * runtime.buffer_size + 1)
    step: int
    for step in range(steps + 1):
        phase_advance: complex = advance ** step
        if step > 0:
            previous_advance: complex = advance ** (step - 1)
            x_prev[runtime.idx_vf] = np.real(voltage_from_phase * previous_advance)
            x_prev[runtime.idx_vt] = np.real(voltage_to_phase * previous_advance)
            if runtime.coupling_block is not None:
                x_prev[runtime.idx_wave_f_re] = np.real(outgoing_from_phase * previous_advance)
                x_prev[runtime.idx_wave_t_re] = np.real(outgoing_to_phase * previous_advance)
            else:
                pass
            runtime.update_history(step_counter=step, x_prev=x_prev, full_params=full_params)
        else:
            pass
        target_voltage_from: np.ndarray = np.real(voltage_from_phase * phase_advance)
        target_voltage_to: np.ndarray = np.real(voltage_to_phase * phase_advance)
        actual_current_from: np.ndarray = runtime.direct_yc_phase @ target_voltage_from + full_params[runtime.idx_p_hf]
        actual_current_to: np.ndarray = runtime.direct_yc_phase @ target_voltage_to + full_params[runtime.idx_p_ht]
        if runtime.coupling_block is not None:
            target_wave_from: np.ndarray = np.real(outgoing_from_phase * phase_advance)
            target_wave_to: np.ndarray = np.real(outgoing_to_phase * phase_advance)
            actual_current_from -= 2.0 * np.real(runtime.phase_current_coupling @ target_wave_to)
            actual_current_to -= 2.0 * np.real(runtime.phase_current_coupling @ target_wave_from)
            expected_q_from: np.ndarray = np.real((voltage_from_phase - outgoing_from_phase
                - runtime.phase_coupling @ outgoing_to_phase) * phase_advance)
            expected_q_to: np.ndarray = np.real((voltage_to_phase - outgoing_to_phase
                - runtime.phase_coupling @ outgoing_from_phase) * phase_advance)
            np.testing.assert_allclose(full_params[runtime.idx_q_f_re], expected_q_from, rtol=0.0, atol=1e-12)
            np.testing.assert_allclose(full_params[runtime.idx_q_t_re], expected_q_to, rtol=0.0, atol=1e-12)
        else:
            pass
        np.testing.assert_allclose(actual_current_from, np.real(current_from_phase * phase_advance), rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(actual_current_to, np.real(current_to_phase * phase_advance), rtol=0.0, atol=1e-12)
        expected_history_from: np.ndarray = np.real(
            (current_from_phase - runtime.direct_yc_phase @ voltage_from_phase) * phase_advance
        )
        expected_history_to: np.ndarray = np.real(
            (current_to_phase - runtime.direct_yc_phase @ voltage_to_phase) * phase_advance
        )
        if runtime.coupling_block is not None:
            expected_history_from += 2.0 * np.real(runtime.phase_current_coupling @ target_wave_to)
            expected_history_to += 2.0 * np.real(runtime.phase_current_coupling @ target_wave_from)
        else:
            pass
        np.testing.assert_allclose(full_params[runtime.idx_p_hf], expected_history_from, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(full_params[runtime.idx_p_ht], expected_history_to, rtol=0.0, atol=1e-12)

    # A coupled invalid inverse is rejected before a companion graph can exist.
    if runtime.coupling_block is not None:
        inconsistent: JMartiRuntimeData = JMartiRuntimeData(
            original.h, 1000.0, ("A", "B"), 2.0 * transform, transform.T,
            50.0, data.get_mode_data(),
        )
        set_jmarti_block_runtime_data(original.block, inconsistent)
        with pytest.raises(ValueError, match="transform/inverse"):
            JMartiHistoryRuntime(original.line, original.block, original.h)
        set_jmarti_block_runtime_data(original.block, data)
    else:
        pass
    # New-problem h resolution must use Data, even when an older Fit is attached.
    original_fit: JMartiFitBundle | None = get_jmarti_block_fit_bundle(original.block)
    retimed: JMartiHistoryRuntime = JMartiHistoryRuntime(original.line, original.block, 2.0 * original.h)
    assert get_jmarti_block_runtime_data(original.block) is data
    assert get_jmarti_block_fit_bundle(original.block) is original_fit
    assert retimed.runtime_data is not data
    assert retimed.runtime_data.get_time_step_s() == 2.0 * original.h
    for mode_index in range(runtime.m):
        original_mode: JMartiModeRuntimeData = data.get_mode_data()[mode_index]
        private_mode: JMartiModeRuntimeData = retimed.runtime_data.get_mode_data()[mode_index]
        np.testing.assert_array_equal(private_mode.get_yc_poles_s(), original_mode.get_yc_poles_s())
        np.testing.assert_array_equal(private_mode.get_yc_residues(), original_mode.get_yc_residues())
        poles: np.ndarray = original_mode.get_yc_poles_s()
        residues: np.ndarray = original_mode.get_yc_residues()
        denominator: np.ndarray = 1.0 - 0.5 * retimed.h * poles
        expected_alpha: np.ndarray = (1.0 + 0.5 * retimed.h * poles) / denominator
        np.testing.assert_allclose(private_mode.get_yc_alpha(), expected_alpha, rtol=0.0, atol=1e-15)
        np.testing.assert_allclose(private_mode.get_yc_beta(), retimed.h * residues / denominator ** 2,
                                   rtol=0.0, atol=1e-15)
        # These source records use ZOH coefficients and continuous direct terms.
        expected_direct: complex = original_mode.get_yc_constant_term() + np.sum(0.5 * retimed.h * residues / denominator)
        np.testing.assert_allclose(private_mode.get_yc_constant_term(), expected_direct, rtol=0.0, atol=1e-15)
    # An intentional tiny imaginary direct coefficient cannot authorize deleting
    # the imaginary target coordinates, even near the singular B=1 boundary.
    if runtime.coupling_block is not None:
        first: JMartiModeRuntimeData = data.get_mode_data()[0]
        perturbed: JMartiModeRuntimeData = JMartiModeRuntimeData(
            0, first.get_tau_s(), first.get_delay_step_count(), first.get_residual_delay_s(),
            first.get_yc_poles_s(), first.get_yc_residues(), first.get_yc_constant_term(), 0j,
            first.get_hres_poles_s(), first.get_hres_residues(), 1.0 + 1e-15j, 0j,
            first.get_yc_alpha(), first.get_yc_beta(), first.get_hres_alpha(), first.get_hres_beta(),
        )
        nonreal: JMartiRuntimeData = JMartiRuntimeData(original.h, 1000.0, ("A", "B"),
            transform, transform.T, 50.0, (perturbed, data.get_mode_data()[1]))
        set_jmarti_block_runtime_data(original.block, nonreal)
        general: JMartiHistoryRuntime = JMartiHistoryRuntime(original.line, original.block, original.h)
        assert not general.phase_real_kernel
        assert len(general.outgoing_wave_f_im) == runtime.m
        assert general.phase_coupling.imag[0, 0] != 0.0
        set_jmarti_block_runtime_data(original.block, data)
    else:
        pass
