"""Physical checks for coupled Bergeron propagation and resistive losses."""
from types import SimpleNamespace

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import (
    BergeronHistoryRuntime, get_bergeron_line_emt_template,
)


def make_runtime(resistance, inductance, capacitance, time_step=1e-5):
    # 10 kV / 100 MVA gives Zbase = 1 ohm; one kilometre makes totals explicit.
    omega = 2*np.pi*50
    line = SimpleNamespace(
        name="Coupled line", length=1., bus_from=SimpleNamespace(Vnom=10.),
        ys=SimpleNamespace(phN=False, phA=True, phB=True, phC=True),
        template=SimpleNamespace(z_nabc=resistance + 1j*omega*inductance,
                                 y_nabc=1j*omega*capacitance),
    )
    block = get_bergeron_line_emt_template(VarFactory()).block
    runtime = BergeronHistoryRuntime(line, block, time_step, 100., 50.)
    runtime.idx_vf = [0, 1, 2]
    runtime.idx_vt = [3, 4, 5]
    runtime.idx_p_hf = [0, 1, 2]
    runtime.idx_p_ht = [3, 4, 5]
    return runtime


def coupled_matrices():
    capacitance = np.array([[3., -.3, -.1], [-.3, 2., -.2], [-.1, -.2, 4.]])*1e-5
    inductance = np.array([[3., .4, .2], [.4, 5., .6], [.2, .6, 4.]])*1e-4
    resistance = np.array([[.08, .01, .02], [.01, .12, .015], [.02, .015, .1]])
    return resistance, inductance, capacitance


def test_characteristic_impedance_satisfies_coupled_telegrapher_equations():
    resistance, inductance, capacitance = coupled_matrices()
    runtime = make_runtime(resistance, inductance, capacitance)
    impedance = np.linalg.inv(runtime.Gc_red) - resistance/4
    np.testing.assert_allclose(impedance @ capacitance @ impedance, inductance, atol=1e-15)
    np.testing.assert_allclose(impedance, impedance.T, atol=1e-14)
    np.testing.assert_allclose(np.sort(runtime.modal_delays**2),
                               np.sort(np.linalg.eigvals(inductance @ capacitance)), atol=1e-18)


def test_dc_history_preserves_total_line_resistance_with_mutual_terms():
    resistance, inductance, capacitance = coupled_matrices()
    runtime = make_runtime(resistance, inductance, capacitance)
    current = np.array([.8, -.4, .2])
    voltage_to = np.array([1., -.6, -.4])
    voltage_from = voltage_to + resistance @ current
    runtime.initialize_buffers_from_initial_point(voltage_from, voltage_to, current, -current)
    history = np.r_[current-runtime.Gc_red@voltage_from, -current-runtime.Gc_red@voltage_to]
    expected = history.copy()
    for step in range(3*runtime.n_delay):
        runtime.update_history(step, np.r_[voltage_from, voltage_to], history)
        np.testing.assert_allclose(history, expected, atol=1e-12, rtol=0)


def test_lossless_sinusoidal_history_repeats_through_multiple_ring_wraps():
    # Independent propagation modes with distinct exact integer delays.
    rotation, _ = np.linalg.qr(np.array([[1., 2., 3.], [4., 2., 1.], [2., 3., 1.]]))
    delays = np.array([2., 3., 5.])*1e-5
    impedances = np.array([2., 3., 4.])
    inductance = rotation @ np.diag(delays*impedances) @ rotation.T
    capacitance = rotation @ np.diag(delays/impedances) @ rotation.T
    runtime = make_runtime(np.zeros((3, 3)), inductance, capacitance)
    omega = 2*np.pi*50
    voltage_from_modes = np.array([1.+.2j, -.5+.3j, .2-.1j])
    voltage_to_modes = np.array([.99+.19j, -.49+.3j, .2-.11j])
    # Analytic lossless transmission-line port currents, independently of runtime history.
    gamma = 1j*omega*delays
    current_from_modes = (np.cosh(gamma)*voltage_from_modes-voltage_to_modes)/(impedances*np.sinh(gamma))
    current_to_modes = (np.cosh(gamma)*voltage_to_modes-voltage_from_modes)/(impedances*np.sinh(gamma))
    vf, vt = rotation@voltage_from_modes, rotation@voltage_to_modes
    currents_from, currents_to = rotation@current_from_modes, rotation@current_to_modes
    runtime.initialize_buffers_from_phasors(vf, vt, currents_from, currents_to, 50.)
    history_phasor = np.r_[currents_from-runtime.Gc_red@vf, currents_to-runtime.Gc_red@vt]
    history = np.sqrt(2)*history_phasor.imag
    for step in range(4*runtime.n_delay):
        previous_time = max(0, step-1)*runtime.h
        previous_voltage = np.sqrt(2)*np.imag(np.r_[vf, vt]*np.exp(1j*omega*previous_time))
        runtime.update_history(step, previous_voltage, history)
        expected = np.sqrt(2)*np.imag(history_phasor*np.exp(1j*omega*step*runtime.h))
        np.testing.assert_allclose(history, expected, atol=1e-11, rtol=0)


def test_fractional_modal_delays_interpolate_ramps_at_the_physical_time():
    resistance, inductance, capacitance = coupled_matrices()
    runtime = make_runtime(resistance, inductance, capacitance)
    slope = np.array([1., -2., 3.])
    for slot in range(runtime.n_delay+1):
        time = 0. if slot == 0 else (slot-runtime.n_delay-1)*runtime.h
        # Choose voltage such that its outgoing current-wave modal components equal slope*time.
        runtime.buf_vf[slot] = np.linalg.solve(runtime.Gc_red, runtime.current_from_modes@(slope*time))
    delayed = runtime.current_to_modes @ runtime._delayed_current_wave(0, runtime.buf_vf, runtime.buf_if)
    np.testing.assert_allclose(delayed, -slope*runtime.modal_delays, atol=1e-15)


def test_step_longer_than_propagation_is_rejected():
    with pytest.raises(ValueError, match="shortest modal travel time"):
        make_runtime(*coupled_matrices(), time_step=1.)


def test_plain_sequence_line_uses_physical_delay_without_a_tower():
    omega = 2*np.pi*50
    line = SimpleNamespace(name="Plain", template=None, R=.01, X=.03, B=.006,
                           R0=.02, X0=.06, B0=.003,
                           ys=SimpleNamespace(phN=False, phA=True, phB=True, phC=True))
    runtime = BergeronHistoryRuntime(line, get_bergeron_line_emt_template(VarFactory()).block,
                                     1e-5, 100., 50.)
    expected = np.sort(np.sqrt([line.X*line.B, line.X*line.B, line.X0*line.B0])/omega)
    np.testing.assert_allclose(runtime.modal_delays, expected, atol=1e-15)


@pytest.mark.parametrize('frequency_hz', [50., 1000.])
def test_terminal_admittance_matches_lossy_fractional_history_recurrence(frequency_hz):
    runtime = make_runtime(*coupled_matrices())
    voltages = np.array([1.+.1j, -.4-.8j, -.5+.7j, .98+.09j, -.39-.79j, -.49+.69j])
    admittance = runtime.get_terminal_admittance(frequency_hz)
    currents = admittance @ voltages
    vf, vt = voltages[:3], voltages[3:]
    current_from, current_to = currents[:3], currents[3:]
    runtime.initialize_buffers_from_phasors(vf, vt, current_from, current_to, frequency_hz)
    history_phasors = np.r_[current_from-runtime.Gc_red@vf, current_to-runtime.Gc_red@vt]
    history = np.sqrt(2)*history_phasors.imag
    omega = 2*np.pi*frequency_hz
    for step in range(4*runtime.n_delay):
        previous_time = max(0, step-1)*runtime.h
        previous_voltage = np.sqrt(2)*np.imag(voltages*np.exp(1j*omega*previous_time))
        runtime.update_history(step, previous_voltage, history)
        expected = np.sqrt(2)*np.imag(history_phasors*np.exp(1j*omega*step*runtime.h))
        np.testing.assert_allclose(history, expected, atol=1e-10, rtol=0)
