# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any, List, Tuple

import numpy as np

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_bundle import JMartiFitBundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import JMartiModeRuntimeData
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import JMartiRuntimeData
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import build_jmarti_runtime_data
from VeraGridEngine.Utils.Symbolic.block import Block, Var
from VeraGridEngine.enumerations import VarPowerFlowReferenceType


class JMartiHistoryRuntime:
    """
    Runtime companion for a JMARTI line in reduced active-phase space.

    The first implementation uses a constant modal basis and one scalar fit per
    mode. The runtime keeps all convolution-like states internally and exposes
    only phase-domain Norton history current injections back to the EMT solver.
    """

    __slots__ = (
        'line',
        'block',
        'h',
        'runtime_data',
        'ph_labels',
        'ph_mask',
        'phase_idx',
        'active_ph',
        'm',
        'Ih_f',
        'Ih_t',
        'direct_yc_modal',
        'direct_zc_modal',
        'direct_yc_phase',
        'max_delay_steps',
        'buffer_size',
        'buf_a_f',
        'buf_a_t',
        'yc_state_from',
        'yc_state_to',
        'hres_state_from',
        'hres_state_to',
        'yc_order_counts',
        'hres_order_counts',
        'v_f_vars',
        'v_t_vars',
        'idx_vf',
        'idx_vt',
        'idx_p_hf',
        'idx_p_ht',
    )

    def __init__(self, line: Any, line_block: Block, h: float) -> None:
        """
        Build one JMARTI runtime companion.

        :param line: Line-like branch device carrying one fit bundle or runtime data.
        :param line_block: Symbolic JMARTI line block.
        :param h: EMT time step in seconds.
        :return: None.
        """
        self.line = line
        self.block = line_block
        self.h = float(h)
        self.runtime_data = _resolve_jmarti_runtime_data(line=line, line_block=line_block, time_step_s=self.h)

        self.ph_labels: List[str] = list(["N", "A", "B", "C"])
        self.ph_mask: np.ndarray = np.asarray([
            bool(line.ys.phN),
            bool(line.ys.phA),
            bool(line.ys.phB),
            bool(line.ys.phC),
        ], dtype=bool)
        idx_global: np.ndarray = np.where(self.ph_mask)[0]
        self.phase_idx: List[int] = list(int(i) for i in idx_global)
        self.active_ph: List[str] = list(self.ph_labels[i] for i in self.phase_idx)
        self.m: int = len(self.active_ph)
        self.Ih_f: List[Var] = _extract_jmarti_history_vars(line_block=self.block, prefix="Ih_f_", active_ph=self.active_ph, line_name=line.name)
        self.Ih_t: List[Var] = _extract_jmarti_history_vars(line_block=self.block, prefix="Ih_t_", active_ph=self.active_ph, line_name=line.name)
        self.direct_yc_modal: np.ndarray = np.zeros(self.m, dtype=np.complex128)
        self.direct_zc_modal: np.ndarray = np.zeros(self.m, dtype=np.complex128)
        self.direct_yc_phase: np.ndarray = np.zeros((self.m, self.m), dtype=np.complex128)
        self.max_delay_steps: int = 0
        self.buffer_size: int = 0
        self.buf_a_f: np.ndarray = np.zeros((1, self.m), dtype=np.complex128)
        self.buf_a_t: np.ndarray = np.zeros((1, self.m), dtype=np.complex128)
        self.yc_state_from: np.ndarray = np.zeros((self.m, 1), dtype=np.complex128)
        self.yc_state_to: np.ndarray = np.zeros((self.m, 1), dtype=np.complex128)
        self.hres_state_from: np.ndarray = np.zeros((self.m, 1), dtype=np.complex128)
        self.hres_state_to: np.ndarray = np.zeros((self.m, 1), dtype=np.complex128)
        self.yc_order_counts: np.ndarray = np.zeros(self.m, dtype=np.int64)
        self.hres_order_counts: np.ndarray = np.zeros(self.m, dtype=np.int64)
        self.v_f_vars = None
        self.v_t_vars = None
        self.idx_vf = None
        self.idx_vt = None
        self.idx_p_hf = None
        self.idx_p_ht = None

        _initialize_jmarti_runtime_storage(self)

    def bind_terminals(self, v_f_vars: List[Any], v_t_vars: List[Any]) -> None:
        """
        Bind the bus terminal voltage variables for the active phases only.

        :param v_f_vars: Full from-side bus voltage variable list in NABC order.
        :param v_t_vars: Full to-side bus voltage variable list in NABC order.
        :return: None.
        """
        self.v_f_vars = list()
        self.v_t_vars = list()
        phase_list_index: int = 0
        phase_name: str
        from_side_full_layout: bool = len(v_f_vars) == 4
        to_side_full_layout: bool = len(v_t_vars) == 4
        source_index: int

        while phase_list_index < len(self.phase_idx):
            full_index: int = self.phase_idx[phase_list_index]
            phase_name = self.active_ph[phase_list_index]

            if from_side_full_layout:
                source_index = full_index
            else:
                source_index = phase_list_index
            vf_var = v_f_vars[source_index]

            if to_side_full_layout:
                source_index = full_index
            else:
                source_index = phase_list_index
            vt_var = v_t_vars[source_index]

            if vf_var is None:
                raise ValueError(
                    f"JMARTI line '{self.line.name}' has active phase '{phase_name}' "
                    f"but from-bus '{self.line.bus_from.name}' does not provide the corresponding EMT voltage variable."
                )
            else:
                pass

            if vt_var is None:
                raise ValueError(
                    f"JMARTI line '{self.line.name}' has active phase '{phase_name}' "
                    f"but to-bus '{self.line.bus_to.name}' does not provide the corresponding EMT voltage variable."
                )
            else:
                pass

            self.v_f_vars.append(vf_var)
            self.v_t_vars.append(vt_var)
            phase_list_index += 1

    def get_nodal_injections(self) -> Tuple[List[Any], List[Any]]:
        """
        Return the phase-domain Norton injections seen by the EMT nodal solver.

        :return: Tuple ``(i_from_full, i_to_full)`` in fixed NABC order.
        """
        if self.v_f_vars is None or self.v_t_vars is None:
            raise RuntimeError("bind_terminals(...) must be called before get_nodal_injections().")
        else:
            pass

        i_f_red: List[Any] = list()
        i_t_red: List[Any] = list()
        row_index: int = 0
        col_index: int
        expr_f: Any
        expr_t: Any

        while row_index < self.m:
            expr_f = self.Ih_f[row_index]
            expr_t = self.Ih_t[row_index]
            col_index = 0

            while col_index < self.m:
                expr_f = expr_f + self.direct_yc_phase[row_index, col_index] * self.v_f_vars[col_index]
                expr_t = expr_t + self.direct_yc_phase[row_index, col_index] * self.v_t_vars[col_index]
                col_index += 1

            i_f_red.append(expr_f)
            i_t_red.append(expr_t)
            row_index += 1

        i_f_full: List[Any] = list([None, None, None, None])
        i_t_full: List[Any] = list([None, None, None, None])
        phase_index: int = 0

        while phase_index < len(self.phase_idx):
            full_index = self.phase_idx[phase_index]
            i_f_full[full_index] = i_f_red[phase_index]
            i_t_full[full_index] = i_t_red[phase_index]
            phase_index += 1

        return i_f_full, i_t_full

    def setup_indices(self, uid2idx_vars: dict, uid2idx_event_params: dict, params_offset: int = 0) -> None:
        """
        Bind solver indices used during the history update.

        :param uid2idx_vars: Variable index map.
        :param uid2idx_event_params: Event-parameter index map.
        :param params_offset: Runtime-parameter offset.
        :return: None.
        """
        self.idx_vf = [uid2idx_vars[v.uid] for v in self.v_f_vars]
        self.idx_vt = [uid2idx_vars[v.uid] for v in self.v_t_vars]
        self.idx_p_hf = [uid2idx_event_params[p.uid] + params_offset for p in self.Ih_f]
        self.idx_p_ht = [uid2idx_event_params[p.uid] + params_offset for p in self.Ih_t]

    def get_mode_count(self) -> int:
        """
        Return the number of modal channels carried by the runtime.

        :return: Number of modal channels.
        """
        return self.m

    def initialize_from_initial_point(self,
                                      v_f0_red: np.ndarray,
                                      v_t0_red: np.ndarray,
                                      i_f0_red: np.ndarray,
                                      i_t0_red: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Initialize buffers and history parameters from one steady-state point.

        :param v_f0_red: From-side active-phase voltages in phase coordinates.
        :param v_t0_red: To-side active-phase voltages in phase coordinates.
        :param i_f0_red: From-side active-phase currents in phase coordinates.
        :param i_t0_red: To-side active-phase currents in phase coordinates.
        :return: Tuple ``(ih_f_phase, ih_t_phase)`` used to seed event parameters.
        """
        v_f0_modal: np.ndarray = self.runtime_data.get_modal_transform_inv() @ np.asarray(v_f0_red, dtype=np.complex128)
        v_t0_modal: np.ndarray = self.runtime_data.get_modal_transform_inv() @ np.asarray(v_t0_red, dtype=np.complex128)
        i_f0_modal: np.ndarray = self.runtime_data.get_modal_transform_inv() @ np.asarray(i_f0_red, dtype=np.complex128)
        i_t0_modal: np.ndarray = self.runtime_data.get_modal_transform_inv() @ np.asarray(i_t0_red, dtype=np.complex128)
        a_f0_modal: np.ndarray = 0.5 * (v_f0_modal + self.direct_zc_modal * i_f0_modal)
        a_t0_modal: np.ndarray = 0.5 * (v_t0_modal + self.direct_zc_modal * i_t0_modal)
        ih_f_modal: np.ndarray = np.zeros(self.m, dtype=np.complex128)
        ih_t_modal: np.ndarray = np.zeros(self.m, dtype=np.complex128)
        buffer_index: int = 0
        mode_index: int = 0
        mode_data: JMartiModeRuntimeData
        current_hres_from: complex
        current_hres_to: complex
        yc_input_from: complex
        yc_input_to: complex
        yc_order_count: int
        hres_order_count: int

        while buffer_index < self.buffer_size:
            self.buf_a_f[buffer_index, :] = a_f0_modal
            self.buf_a_t[buffer_index, :] = a_t0_modal
            buffer_index += 1

        self.yc_state_from.fill(0.0)
        self.yc_state_to.fill(0.0)
        self.hres_state_from.fill(0.0)
        self.hres_state_to.fill(0.0)

        while mode_index < self.m:
            mode_data = self.runtime_data.get_mode_data()[mode_index]
            yc_order_count = int(self.yc_order_counts[mode_index])
            hres_order_count = int(self.hres_order_counts[mode_index])

            if hres_order_count > 0:
                self.hres_state_from[mode_index, :hres_order_count] = _build_jmarti_steady_state_state_row(
                    alpha=mode_data.get_hres_alpha(),
                    beta=mode_data.get_hres_beta(),
                    input_value=a_t0_modal[mode_index],
                )
                self.hres_state_to[mode_index, :hres_order_count] = _build_jmarti_steady_state_state_row(
                    alpha=mode_data.get_hres_alpha(),
                    beta=mode_data.get_hres_beta(),
                    input_value=a_f0_modal[mode_index],
                )
            else:
                pass

            current_hres_from = (
                mode_data.get_hres_constant_term() * a_t0_modal[mode_index]
                + _sum_state_row(self.hres_state_from, mode_index, hres_order_count)
            )
            current_hres_to = (
                mode_data.get_hres_constant_term() * a_f0_modal[mode_index]
                + _sum_state_row(self.hres_state_to, mode_index, hres_order_count)
            )
            yc_input_from = v_f0_modal[mode_index] - 2.0 * current_hres_from
            yc_input_to = v_t0_modal[mode_index] - 2.0 * current_hres_to

            if yc_order_count > 0:
                self.yc_state_from[mode_index, :yc_order_count] = _build_jmarti_steady_state_state_row(
                    alpha=mode_data.get_yc_alpha(),
                    beta=mode_data.get_yc_beta(),
                    input_value=yc_input_from,
                )
                self.yc_state_to[mode_index, :yc_order_count] = _build_jmarti_steady_state_state_row(
                    alpha=mode_data.get_yc_alpha(),
                    beta=mode_data.get_yc_beta(),
                    input_value=yc_input_to,
                )
            else:
                pass

            ih_f_modal[mode_index] = _sum_state_row(self.yc_state_from, mode_index, yc_order_count) - 2.0 * self.direct_yc_modal[mode_index] * current_hres_from
            ih_t_modal[mode_index] = _sum_state_row(self.yc_state_to, mode_index, yc_order_count) - 2.0 * self.direct_yc_modal[mode_index] * current_hres_to
            mode_index += 1

        return (
            self.runtime_data.get_modal_transform() @ ih_f_modal,
            self.runtime_data.get_modal_transform() @ ih_t_modal,
        )

    def initialize_from_fundamental_phasors(self,
                                            v_f0_phasor_red: np.ndarray,
                                            v_t0_phasor_red: np.ndarray,
                                            i_f0_phasor_red: np.ndarray,
                                            i_t0_phasor_red: np.ndarray,
                                            system_frequency_hz: float) -> tuple[np.ndarray, np.ndarray]:
        """
        Initialize one JMARTI runtime from one sinusoidal fundamental operating point.

        The runtime states represent first-order discrete filters, so their
        consistent steady state under a balanced sinusoidal operating point is not
        the constant-input equilibrium. This initializer seeds the internal modal
        states with the periodic discrete-time solution at the requested
        fundamental frequency.

        :param v_f0_phasor_red: From-side phase phasors in RMS complex form.
        :param v_t0_phasor_red: To-side phase phasors in RMS complex form.
        :param i_f0_phasor_red: From-side branch-current phasors in RMS complex form.
        :param i_t0_phasor_red: To-side branch-current phasors in RMS complex form.
        :param system_frequency_hz: Fundamental system frequency in Hz.
        :return: Tuple ``(ih_f_phase, ih_t_phase)`` used to seed event parameters.
        """
        omega = 2.0 * np.pi * float(system_frequency_hz)
        inverse = self.runtime_data.get_modal_transform_inv()
        vf_analytic = -1j * np.sqrt(2.0) * np.asarray(v_f0_phasor_red)
        vt_analytic = -1j * np.sqrt(2.0) * np.asarray(v_t0_phasor_red)
        self.buf_a_f.fill(0.0)
        self.buf_a_t.fill(0.0)
        for states in (self.yc_state_from, self.yc_state_to,
                       self.hres_state_from, self.hres_state_to):
            states.fill(0.0)

        # A real sinusoid contains both frequency signs. Filter coefficients
        # may be complex (conjugate pole pairs), so taking real(state) alone
        # would discard information required by the recurrence.
        for sign in (1, -1):
            advance = np.exp(sign * 1j * omega * self.h)
            vf = inverse @ (vf_analytic if sign == 1 else vf_analytic.conj()) / 2.0
            vt = inverse @ (vt_analytic if sign == 1 else vt_analytic.conj()) / 2.0
            for k, mode in enumerate(self.runtime_data.get_mode_data()):
                fraction = min(max(mode.get_residual_delay_s() / self.h, 0.0), 1.0)
                delay = advance ** (-mode.get_delay_step_count()) * (1.0 - fraction + fraction / advance)
                h_response = mode.get_hres_constant_term() + np.sum(
                    mode.get_hres_beta() / (advance - mode.get_hres_alpha()))
                propagation = h_response * delay
                # v_f = a_f + H*a_t and v_t = a_t + H*a_f.
                af, at = np.linalg.solve(np.array([[1, propagation], [propagation, 1]]),
                                         np.array([vf[k], vt[k]]))
                for slot in range(self.buffer_size):
                    sample_index = 0 if slot == 0 else slot - self.buffer_size
                    self.buf_a_f[slot, k] += af * advance ** sample_index
                    self.buf_a_t[slot, k] += at * advance ** sample_index
                for states, incoming in ((self.hres_state_from, at), (self.hres_state_to, af)):
                    count = int(self.hres_order_counts[k])
                    states[k, :count] += _build_jmarti_periodic_state_row(
                        mode.get_hres_alpha(), mode.get_hres_beta(), delay * incoming, advance)
                for states, local, remote in ((self.yc_state_from, vf[k], at),
                                               (self.yc_state_to, vt[k], af)):
                    count = int(self.yc_order_counts[k])
                    states[k, :count] += _build_jmarti_periodic_state_row(
                        mode.get_yc_alpha(), mode.get_yc_beta(), local - 2 * propagation * remote, advance)

        # Preserve the supplied PF terminal currents at t=0. If the PF network
        # differs from the fitted line, that mismatch must be resolved upstream.
        return (
            np.sqrt(2.0) * np.imag(i_f0_phasor_red) - self.direct_yc_phase @ (np.sqrt(2.0) * np.imag(v_f0_phasor_red)),
            np.sqrt(2.0) * np.imag(i_t0_phasor_red) - self.direct_yc_phase @ (np.sqrt(2.0) * np.imag(v_t0_phasor_red)),
        )

    def update_history(self, step_counter: int, x_prev: np.ndarray, full_params: np.ndarray) -> None:
        """
        Prepare the target-step history from the previous accepted EMT state.

        :param step_counter: Current accepted step counter.
        :param x_prev: Previous accepted state vector.
        :param full_params: Flat runtime parameter vector.
        :return: None.
        """
        # The solver first calls at t=0, then at target t=(k+1)*h with
        # the accepted state at k*h. The startup call must not advance filters.
        if step_counter == 0:
            return
        step_counter -= 1
        v_f_now_phase: np.ndarray = np.asarray([x_prev[index] if index >= 0 else 0.0 for index in self.idx_vf], dtype=np.complex128)
        v_t_now_phase: np.ndarray = np.asarray([x_prev[index] if index >= 0 else 0.0 for index in self.idx_vt], dtype=np.complex128)
        v_f_now_modal: np.ndarray = self.runtime_data.get_modal_transform_inv() @ v_f_now_phase
        v_t_now_modal: np.ndarray = self.runtime_data.get_modal_transform_inv() @ v_t_now_phase
        # The outgoing voltage wave is a = v - b, where b is the
        # propagated incoming wave. Using (v + i/Yc_direct)/2 is valid only
        # for constant Yc and corrupts the frequency-dependent line response.
        a_f_now_modal = np.empty(self.m, dtype=np.complex128)
        a_t_now_modal = np.empty(self.m, dtype=np.complex128)
        for k, mode in enumerate(self.runtime_data.get_mode_data()):
            incoming_f = mode.get_hres_constant_term() * _get_delayed_incident_wave(
                self, k, step_counter, self.buf_a_t, next_step=False)
            incoming_t = mode.get_hres_constant_term() * _get_delayed_incident_wave(
                self, k, step_counter, self.buf_a_f, next_step=False)
            incoming_f += _sum_state_row(self.hres_state_from, k, int(self.hres_order_counts[k]))
            incoming_t += _sum_state_row(self.hres_state_to, k, int(self.hres_order_counts[k]))
            a_f_now_modal[k] = v_f_now_modal[k] - incoming_f
            a_t_now_modal[k] = v_t_now_modal[k] - incoming_t
        current_buffer_index: int = step_counter % self.buffer_size
        self.buf_a_f[current_buffer_index, :] = a_f_now_modal
        self.buf_a_t[current_buffer_index, :] = a_t_now_modal

        ih_f_next_modal: np.ndarray = np.zeros(self.m, dtype=np.complex128)
        ih_t_next_modal: np.ndarray = np.zeros(self.m, dtype=np.complex128)
        mode_index: int = 0

        while mode_index < self.m:
            ih_f_next_modal[mode_index] = _update_jmarti_mode_history(
                runtime=self,
                mode_index=mode_index,
                step_counter=step_counter,
                local_voltage_modal=v_f_now_modal[mode_index],
                remote_incident_buffer=self.buf_a_t,
                yc_state=self.yc_state_from,
                hres_state=self.hres_state_from,
            )
            ih_t_next_modal[mode_index] = _update_jmarti_mode_history(
                runtime=self,
                mode_index=mode_index,
                step_counter=step_counter,
                local_voltage_modal=v_t_now_modal[mode_index],
                remote_incident_buffer=self.buf_a_f,
                yc_state=self.yc_state_to,
                hres_state=self.hres_state_to,
            )
            mode_index += 1

        ih_f_next_phase: np.ndarray = self.runtime_data.get_modal_transform() @ ih_f_next_modal
        ih_t_next_phase: np.ndarray = self.runtime_data.get_modal_transform() @ ih_t_next_modal
        phase_index: int = 0

        while phase_index < self.m:
            full_params[self.idx_p_hf[phase_index]] = float(np.real(ih_f_next_phase[phase_index]))
            full_params[self.idx_p_ht[phase_index]] = float(np.real(ih_t_next_phase[phase_index]))
            phase_index += 1


JMARTI_BLOCK_FIT_BUNDLE_ATTR: str = "_jmarti_fit_bundle"
JMARTI_BLOCK_RUNTIME_DATA_ATTR: str = "_jmarti_runtime_data"


def set_jmarti_block_fit_bundle(block: Block, fit_bundle: JMartiFitBundle | None) -> None:
    """
    Attach one optional JMARTI fit bundle to one EMT block.

    :param block: Target EMT block.
    :param fit_bundle: Optional offline fit bundle.
    :return: None.
    """
    if fit_bundle is None:
        block.jmarti_fit_bundle = None
    else:
        block.jmarti_fit_bundle = fit_bundle


def get_jmarti_block_fit_bundle(block: Block | None) -> JMartiFitBundle | None:
    """
    Return the optional JMARTI fit bundle attached to one EMT block.

    :param block: Candidate EMT block.
    :return: Attached fit bundle or ``None``.
    """
    if isinstance(block, Block):
        fit_bundle: object | None = block.jmarti_fit_bundle

        if isinstance(fit_bundle, JMartiFitBundle):
            return fit_bundle
        else:
            return None
    else:
        return None


def set_jmarti_block_runtime_data(block: Block, runtime_data: JMartiRuntimeData | None) -> None:
    """
    Attach one optional discretized JMARTI runtime data object to one EMT block.

    :param block: Target EMT block.
    :param runtime_data: Optional runtime data.
    :return: None.
    """
    if runtime_data is None:
        block.jmarti_runtime_data = None
    else:
        block.jmarti_runtime_data = runtime_data


def get_jmarti_block_runtime_data(block: Block | None) -> JMartiRuntimeData | None:
    """
    Return the optional JMARTI runtime data attached to one EMT block.

    :param block: Candidate EMT block.
    :return: Attached runtime data or ``None``.
    """
    if isinstance(block, Block):
        runtime_data: object | None = block.jmarti_runtime_data

        if isinstance(runtime_data, JMartiRuntimeData):
            return runtime_data
        else:
            return None
    else:
        return None


def _resolve_jmarti_runtime_data(line: Any, line_block: Block, time_step_s: float) -> JMartiRuntimeData:
    """
    Resolve one discrete JMARTI runtime dataset from the line object.

    :param line: Line-like branch device.
    :param line_block: EMT block carrying the JMARTI configuration and optional fit.
    :param time_step_s: EMT time step in seconds.
    :return: Runtime-ready JMARTI dataset.
    :raises ValueError: If no JMARTI fit information is attached to the line.
    """
    if isinstance(line, Line) and isinstance(line_block, Block):
        attached_runtime_data: JMartiRuntimeData | None = get_jmarti_block_runtime_data(line_block)

        if attached_runtime_data is not None:
            return attached_runtime_data
        else:
            attached_fit_bundle: JMartiFitBundle | None = get_jmarti_block_fit_bundle(line_block)

            if attached_fit_bundle is not None:
                runtime_data: JMartiRuntimeData = build_jmarti_runtime_data(attached_fit_bundle, time_step_s)
                set_jmarti_block_runtime_data(line_block, runtime_data)
                return runtime_data
            else:
                raise ValueError(f"JMARTI line '{line.name}' requires one fit bundle or one runtime data object attached to its EMT block")
    else:
        raise ValueError("JMARTI runtime expects a Line-compatible object")


def _extract_jmarti_history_vars(line_block: Block,
                                 prefix: str,
                                 active_ph: List[str],
                                 line_name: str) -> List[Var]:
    """
    Extract one ordered list of history-current event variables.

    :param line_block: JMARTI symbolic line block.
    :param prefix: History-variable prefix.
    :param active_ph: Active phase labels.
    :param line_name: Line name used in diagnostics.
    :return: Ordered history-variable list.
    """
    vars_by_name: dict[str, Var] = dict((var.name, var) for var in line_block.event_dict.keys())
    out: List[Var] = list()
    phase_index: int = 0
    key_name: str
    phase_label: str

    while phase_index < len(active_ph):
        phase_label = active_ph[phase_index]
        key_name = f"{prefix}{phase_label}"

        if key_name in vars_by_name:
            out.append(vars_by_name[key_name])
        else:
            raise ValueError(f"Missing JMARTI history var '{key_name}' for line '{line_name}'")

        phase_index += 1

    return out


def _initialize_jmarti_runtime_storage(runtime: JMartiHistoryRuntime) -> None:
    """
    Allocate the numerical storage used by one JMARTI runtime.

    :param runtime: Target JMARTI runtime.
    :return: None.
    """
    mode_index: int = 0
    max_yc_order: int = 0
    max_hres_order: int = 0
    mode_data: JMartiModeRuntimeData
    modal_direct_terms: np.ndarray = np.zeros(runtime.m, dtype=np.complex128)

    while mode_index < runtime.m:
        mode_data = runtime.runtime_data.get_mode_data()[mode_index]
        runtime.yc_order_counts[mode_index] = mode_data.get_yc_alpha().size
        runtime.hres_order_counts[mode_index] = mode_data.get_hres_alpha().size
        modal_direct_terms[mode_index] = mode_data.get_yc_constant_term()
        max_yc_order = max(max_yc_order, int(runtime.yc_order_counts[mode_index]))
        max_hres_order = max(max_hres_order, int(runtime.hres_order_counts[mode_index]))
        mode_index += 1

    runtime.direct_yc_modal = modal_direct_terms
    runtime.direct_zc_modal = np.zeros(runtime.m, dtype=np.complex128)
    non_zero_mask: np.ndarray = np.abs(runtime.direct_yc_modal) > 1.0e-14
    runtime.direct_zc_modal[non_zero_mask] = 1.0 / runtime.direct_yc_modal[non_zero_mask]
    runtime.direct_yc_phase = np.real(
        runtime.runtime_data.get_modal_transform()
        @ np.diag(runtime.direct_yc_modal)
        @ runtime.runtime_data.get_modal_transform_inv()
    )
    runtime.max_delay_steps = max(int(mode_data.get_delay_step_count()) for mode_data in runtime.runtime_data.get_mode_data())
    runtime.buffer_size = max(2, runtime.max_delay_steps + 2)
    runtime.buf_a_f = np.zeros((runtime.buffer_size, runtime.m), dtype=np.complex128)
    runtime.buf_a_t = np.zeros((runtime.buffer_size, runtime.m), dtype=np.complex128)
    runtime.yc_state_from = np.zeros((runtime.m, max(1, max_yc_order)), dtype=np.complex128)
    runtime.yc_state_to = np.zeros((runtime.m, max(1, max_yc_order)), dtype=np.complex128)
    runtime.hres_state_from = np.zeros((runtime.m, max(1, max_hres_order)), dtype=np.complex128)
    runtime.hres_state_to = np.zeros((runtime.m, max(1, max_hres_order)), dtype=np.complex128)


def _get_delayed_incident_wave(runtime: JMartiHistoryRuntime,
                               mode_index: int,
                               step_counter: int,
                               remote_incident_buffer: np.ndarray,
                               next_step: bool) -> complex:
    """
    Return one delayed outgoing wave sample for the requested mode.

    :param runtime: Owning JMARTI runtime.
    :param mode_index: Modal channel index.
    :param step_counter: Current accepted step counter.
    :param remote_incident_buffer: Ring buffer of remote outgoing waves.
    :param next_step: Whether to sample the delay for the next step.
    :return: Delayed outgoing wave.
    """
    mode_data: JMartiModeRuntimeData = runtime.runtime_data.get_mode_data()[mode_index]
    delay_step_count: int = mode_data.get_delay_step_count()
    residual_delay_s: float = mode_data.get_residual_delay_s()
    interpolation_fraction_previous: float = 0.0
    interpolation_fraction_current: float = 1.0
    delayed_step_index: int
    previous_step_index: int

    if runtime.h > 0.0:
        interpolation_fraction_previous = min(max(residual_delay_s / runtime.h, 0.0), 1.0)
    else:
        interpolation_fraction_previous = 0.0

    interpolation_fraction_current = 1.0 - interpolation_fraction_previous

    if delay_step_count == 0:
        delayed_step_index = step_counter + 1 if next_step else step_counter
    else:
        if next_step:
            delayed_step_index = step_counter + 1 - delay_step_count
        else:
            delayed_step_index = step_counter - delay_step_count

    if interpolation_fraction_previous > 0.0:
        previous_step_index = delayed_step_index - 1
        return complex(
            interpolation_fraction_previous * remote_incident_buffer[previous_step_index % runtime.buffer_size, mode_index]
            + interpolation_fraction_current * remote_incident_buffer[delayed_step_index % runtime.buffer_size, mode_index]
        )
    else:
        return complex(remote_incident_buffer[delayed_step_index % runtime.buffer_size, mode_index])


def _sum_state_row(state_matrix: np.ndarray, mode_index: int, order_count: int) -> complex:
    """
    Return the sum of one active row segment in a padded state matrix.

    :param state_matrix: Padded state matrix.
    :param mode_index: Modal row index.
    :param order_count: Active order in that row.
    :return: Sum of the active row entries.
    """
    if order_count > 0:
        return complex(np.sum(state_matrix[mode_index, :order_count]))
    else:
        return 0.0 + 0.0j


def _update_jmarti_state_row(state_matrix: np.ndarray,
                             mode_index: int,
                             order_count: int,
                             alpha: np.ndarray,
                             beta: np.ndarray,
                             input_value: complex) -> None:
    """
    Update one padded row of first-order discrete states.

    :param state_matrix: Padded state matrix.
    :param mode_index: Modal row index.
    :param order_count: Active order in that row.
    :param alpha: Active transition multipliers.
    :param beta: Active input gains.
    :param input_value: Current scalar input.
    :return: None.
    """
    if order_count > 0:
        state_matrix[mode_index, :order_count] = alpha * state_matrix[mode_index, :order_count] + beta * input_value
    else:
        pass


def _build_jmarti_steady_state_state_row(alpha: np.ndarray,
                                         beta: np.ndarray,
                                         input_value: complex) -> np.ndarray:
    """
    Return the discrete steady-state of one first-order JMARTI state row.

    :param alpha: Exact state-transition multipliers.
    :param beta: Exact input gains.
    :param input_value: Constant scalar input.
    :return: Steady-state row values.
    """
    denominator: np.ndarray = 1.0 - np.asarray(alpha, dtype=np.complex128)
    steady_state: np.ndarray = np.zeros_like(np.asarray(beta, dtype=np.complex128))
    non_zero_mask: np.ndarray = np.abs(denominator) > 1.0e-14
    steady_state[non_zero_mask] = np.asarray(beta, dtype=np.complex128)[non_zero_mask] * input_value / denominator[non_zero_mask]
    return steady_state


def _build_jmarti_periodic_state_row(alpha: np.ndarray,
                                     beta: np.ndarray,
                                     input_value: complex,
                                     lambda_step: complex) -> np.ndarray:
    """
    Return the discrete periodic state of one first-order JMARTI state row.

    :param alpha: Exact state-transition multipliers.
    :param beta: Exact input gains.
    :param input_value: Fundamental-frequency analytic input sample at ``n=0``.
    :param lambda_step: One-step complex phase advance ``exp(j*w*h)``.
    :return: Periodic steady-state row values.
    """
    denominator: np.ndarray = complex(lambda_step) - np.asarray(alpha, dtype=np.complex128)
    periodic_state: np.ndarray = np.zeros_like(np.asarray(beta, dtype=np.complex128))
    non_zero_mask: np.ndarray = np.abs(denominator) > 1.0e-14
    periodic_state[non_zero_mask] = np.asarray(beta, dtype=np.complex128)[non_zero_mask] * input_value / denominator[non_zero_mask]
    return periodic_state


def _update_jmarti_mode_history(runtime: JMartiHistoryRuntime,
                                mode_index: int,
                                step_counter: int,
                                local_voltage_modal: complex,
                                remote_incident_buffer: np.ndarray,
                                yc_state: np.ndarray,
                                hres_state: np.ndarray) -> complex:
    """
    Advance one modal channel and return the next-step history current.

    :param runtime: Owning JMARTI runtime.
    :param mode_index: Modal channel index.
    :param step_counter: Current accepted step counter.
    :param local_voltage_modal: Local terminal voltage in modal coordinates.
    :param remote_incident_buffer: Ring buffer of remote outgoing waves.
    :param yc_state: Padded local Yc state matrix.
    :param hres_state: Padded propagation-filter state matrix.
    :return: Next-step history current in modal coordinates.
    """
    mode_data: JMartiModeRuntimeData = runtime.runtime_data.get_mode_data()[mode_index]
    yc_order_count: int = int(runtime.yc_order_counts[mode_index])
    hres_order_count: int = int(runtime.hres_order_counts[mode_index])
    delayed_wave_current: complex = _get_delayed_incident_wave(runtime, mode_index, step_counter, remote_incident_buffer, next_step=False)
    current_hres_output: complex = mode_data.get_hres_constant_term() * delayed_wave_current + _sum_state_row(hres_state, mode_index, hres_order_count)
    yc_input_current: complex = local_voltage_modal - 2.0 * current_hres_output

    _update_jmarti_state_row(
        state_matrix=hres_state,
        mode_index=mode_index,
        order_count=hres_order_count,
        alpha=mode_data.get_hres_alpha(),
        beta=mode_data.get_hres_beta(),
        input_value=delayed_wave_current,
    )
    _update_jmarti_state_row(
        state_matrix=yc_state,
        mode_index=mode_index,
        order_count=yc_order_count,
        alpha=mode_data.get_yc_alpha(),
        beta=mode_data.get_yc_beta(),
        input_value=yc_input_current,
    )

    delayed_wave_next: complex = _get_delayed_incident_wave(runtime, mode_index, step_counter, remote_incident_buffer, next_step=True)
    next_hres_output: complex = mode_data.get_hres_constant_term() * delayed_wave_next + _sum_state_row(hres_state, mode_index, hres_order_count)
    next_yc_dynamic_output: complex = _sum_state_row(yc_state, mode_index, yc_order_count)
    return next_yc_dynamic_output - 2.0 * runtime.direct_yc_modal[mode_index] * next_hres_output
