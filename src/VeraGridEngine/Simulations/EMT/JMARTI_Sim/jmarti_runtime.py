# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any, List, Tuple

import numpy as np

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_bundle import JMartiFitBundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import JMartiModeRuntimeData
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import JMartiRuntimeData
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import build_jmarti_runtime_data
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import is_jmarti_phase_real_runtime_data
from VeraGridEngine.Utils.Symbolic.block import Block, Var
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr
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
        'coupling_block',
        'coupling_var_factory',
        'instantaneous_h_modal',
        'phase_coupling',
        'phase_current_coupling',
        'outgoing_wave_f_re',
        'outgoing_wave_t_re',
        'incoming_voltage_f_re',
        'incoming_voltage_t_re',
        'idx_wave_f_re',
        'idx_wave_t_re',
        'idx_q_f_re',
        'idx_q_t_re',
        'initial_source_phasors',
        'initial_source_frequency_hz',
        'initial_source_available',
        'initial_phase_waves',
        'initial_voltage_offsets',
        'phase_real_kernel',
        'outgoing_wave_f_im',
        'outgoing_wave_t_im',
        'incoming_voltage_f_im',
        'incoming_voltage_t_im',
        'idx_wave_f_im',
        'idx_wave_t_im',
        'idx_q_f_im',
        'idx_q_t_im',
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

        # Companion ownership and restart storage are private to this problem.
        self.coupling_block: Block | None = None
        self.coupling_var_factory: VarFactory | None = None
        self.instantaneous_h_modal: np.ndarray = np.zeros(self.m, dtype=complex)
        self.phase_coupling: np.ndarray = np.empty((0, 0), dtype=complex)
        self.phase_current_coupling: np.ndarray = np.empty((0, 0), dtype=complex)
        self.phase_real_kernel: bool = False
        self.initial_source_phasors: np.ndarray = np.empty((4, 0), dtype=complex)
        self.initial_source_frequency_hz: float = 0.0
        self.initial_source_available: bool = False
        self.initial_phase_waves: np.ndarray = np.empty((2, 0), dtype=complex)
        self.initial_voltage_offsets: np.ndarray = np.empty((2, 0), dtype=complex)
        self.outgoing_wave_f_re: list[Var] = list()
        self.incoming_voltage_f_re: list[Var] = list()
        self.idx_wave_f_re: list[int] = list()
        self.idx_q_f_re: list[int] = list()
        self.outgoing_wave_f_im: list[Var] = list()
        self.incoming_voltage_f_im: list[Var] = list()
        self.idx_wave_f_im: list[int] = list()
        self.idx_q_f_im: list[int] = list()
        self.outgoing_wave_t_re: list[Var] = list()
        self.incoming_voltage_t_re: list[Var] = list()
        self.idx_wave_t_re: list[int] = list()
        self.idx_q_t_re: list[int] = list()
        self.outgoing_wave_t_im: list[Var] = list()
        self.incoming_voltage_t_im: list[Var] = list()
        self.idx_wave_t_im: list[int] = list()
        self.idx_q_t_im: list[int] = list()

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

        if self.coupling_block is not None:
            # The same private rows enter the common g for every backend;
            # no local division by 1-B^2 is valid at a singular direct path.
            row: int
            col: int
            for row in range(self.m):
                from_real: Expr = self.outgoing_wave_f_re[row] + self.incoming_voltage_f_re[row] - self.v_f_vars[row]
                to_real: Expr = self.outgoing_wave_t_re[row] + self.incoming_voltage_t_re[row] - self.v_t_vars[row]
                for col in range(self.m):
                    from_real = from_real + float(self.phase_coupling[row, col].real) * self.outgoing_wave_t_re[col]
                    to_real = to_real + float(self.phase_coupling[row, col].real) * self.outgoing_wave_f_re[col]
                    if self.phase_real_kernel:
                        pass
                    else:
                        from_real = from_real - float(self.phase_coupling[row, col].imag) * self.outgoing_wave_t_im[col]
                        to_real = to_real - float(self.phase_coupling[row, col].imag) * self.outgoing_wave_f_im[col]
                self.coupling_block.algebraic_eqs[row] = from_real
                self.coupling_block.algebraic_eqs[self.m + row] = to_real
                if self.phase_real_kernel:
                    pass
                else:
                    from_imag: Expr = self.outgoing_wave_f_im[row] + self.incoming_voltage_f_im[row]
                    to_imag: Expr = self.outgoing_wave_t_im[row] + self.incoming_voltage_t_im[row]
                    for col in range(self.m):
                        from_imag = from_imag + float(self.phase_coupling[row, col].imag) * self.outgoing_wave_t_re[col] + float(self.phase_coupling[row, col].real) * self.outgoing_wave_t_im[col]
                        to_imag = to_imag + float(self.phase_coupling[row, col].imag) * self.outgoing_wave_f_re[col] + float(self.phase_coupling[row, col].real) * self.outgoing_wave_f_im[col]
                    self.coupling_block.algebraic_eqs[2 * self.m + row] = from_imag
                    self.coupling_block.algebraic_eqs[3 * self.m + row] = to_imag
        else:
            pass

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
                if self.coupling_block is not None:
                    expr_f = expr_f - 2.0 * float(self.phase_current_coupling[row_index, col_index].real) * self.outgoing_wave_t_re[col_index]
                    expr_t = expr_t - 2.0 * float(self.phase_current_coupling[row_index, col_index].real) * self.outgoing_wave_f_re[col_index]
                    if self.phase_real_kernel:
                        pass
                    else:
                        expr_f = expr_f + 2.0 * float(self.phase_current_coupling[row_index, col_index].imag) * self.outgoing_wave_t_im[col_index]
                        expr_t = expr_t + 2.0 * float(self.phase_current_coupling[row_index, col_index].imag) * self.outgoing_wave_f_im[col_index]
                else:
                    pass
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
        # Own indices were allocated at construction and are filled in place.
        variables: list[Var]
        indices: list[int]
        index: int
        for variables, indices in ((self.outgoing_wave_f_re, self.idx_wave_f_re),
                                   (self.outgoing_wave_t_re, self.idx_wave_t_re),
                                   (self.outgoing_wave_f_im, self.idx_wave_f_im),
                                   (self.outgoing_wave_t_im, self.idx_wave_t_im)):
            for index in range(len(variables)):
                indices[index] = uid2idx_vars[variables[index].uid]
        for variables, indices in ((self.incoming_voltage_f_re, self.idx_q_f_re),
                                   (self.incoming_voltage_t_re, self.idx_q_t_re),
                                   (self.incoming_voltage_f_im, self.idx_q_f_im),
                                   (self.incoming_voltage_t_im, self.idx_q_t_im)):
            for index in range(len(variables)):
                indices[index] = uid2idx_event_params[variables[index].uid] + params_offset

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
        """Initialize a constant point through the full discrete Yc/H owner.

        :param v_f0_red: From-side constant active-phase voltages.
        :param v_t0_red: To-side constant active-phase voltages.
        :param i_f0_red: From-side constant active-phase currents.
        :param i_t0_red: To-side constant active-phase currents.
        :return: Real Norton offsets including instantaneous wave feedback.
        """
        return self.initialize_from_fundamental_phasors(
            1j * np.asarray(v_f0_red) / np.sqrt(2.0),
            1j * np.asarray(v_t0_red) / np.sqrt(2.0),
            1j * np.asarray(i_f0_red) / np.sqrt(2.0),
            1j * np.asarray(i_t0_red) / np.sqrt(2.0), 0.0,
        )

    def initialize_from_fundamental_phasors(self,
                                            v_f0_phasor_red: np.ndarray,
                                            v_t0_phasor_red: np.ndarray,
                                            i_f0_phasor_red: np.ndarray,
                                            i_t0_phasor_red: np.ndarray,
                                            system_frequency_hz: float) -> tuple[np.ndarray, np.ndarray]:
        """Initialize real periodic excitation without losing conjugate pole states.

        The regular boundary determines outgoing waves from terminal voltages and
        the full delayed propagation response. A numerically singular compatible
        boundary uses the supplied currents and full discrete admittance to
        determine its otherwise unobservable wave difference. Every sign/mode
        is checked before any retained buffer or filter state is modified.

        :param v_f0_phasor_red: From-side active-phase RMS voltage phasors.
        :param v_t0_phasor_red: To-side active-phase RMS voltage phasors.
        :param i_f0_phasor_red: From-side active-phase RMS current phasors.
        :param i_t0_phasor_red: To-side active-phase RMS current phasors.
        :param system_frequency_hz: Excitation frequency in Hz, including DC.
        :return: Norton histories preserving supplied physical currents at t0.
        :raises ValueError: If a singular boundary cannot be resolved compatibly.
        """
        omega: float = 2.0 * np.pi * float(system_frequency_hz)
        inverse: np.ndarray = self.runtime_data.get_modal_transform_inv()
        analytic_vf: np.ndarray = -1j * np.sqrt(2.0) * np.asarray(v_f0_phasor_red)
        analytic_vt: np.ndarray = -1j * np.sqrt(2.0) * np.asarray(v_t0_phasor_red)
        analytic_if: np.ndarray = -1j * np.sqrt(2.0) * np.asarray(i_f0_phasor_red)
        analytic_it: np.ndarray = -1j * np.sqrt(2.0) * np.asarray(i_t0_phasor_red)
        # Validate all physical inputs before any retained mutation. Shapes
        # and coefficient identity remain owned by the typed runtime dataset.
        transform: np.ndarray = self.runtime_data.get_modal_transform()
        if (np.isfinite(system_frequency_hz) and np.isfinite(omega)
                and np.isfinite(analytic_vf).all() and np.isfinite(analytic_vt).all()
                and np.isfinite(analytic_if).all() and np.isfinite(analytic_it).all()
                and np.isfinite(inverse).all() and np.isfinite(transform).all()):
            pass
        else:
            raise ValueError("JMARTI periodic terminal data, frequency or modal transform is not finite")
        advances: np.ndarray = np.exp(1j * omega * self.h * np.array((1.0, -1.0)))
        voltages_f: np.ndarray = np.empty((2, self.m), dtype=complex)
        voltages_t: np.ndarray = np.empty((2, self.m), dtype=complex)
        outgoing_f: np.ndarray = np.empty((2, self.m), dtype=complex)
        outgoing_t: np.ndarray = np.empty((2, self.m), dtype=complex)
        delays: np.ndarray = np.empty((2, self.m), dtype=complex)
        propagations: np.ndarray = np.empty((2, self.m), dtype=complex)
        sign_index: int
        mode_index: int
        mode: JMartiModeRuntimeData

        # Validate and resolve both frequency signs first. Failed preflight must
        # leave a previously initialized runtime intact instead of clearing it.
        for sign_index in range(2):
            currents_f: np.ndarray
            currents_t: np.ndarray
            if sign_index == 0:
                voltages_f[sign_index] = inverse @ analytic_vf / 2.0
                voltages_t[sign_index] = inverse @ analytic_vt / 2.0
                currents_f = inverse @ analytic_if / 2.0
                currents_t = inverse @ analytic_it / 2.0
            else:
                voltages_f[sign_index] = inverse @ analytic_vf.conj() / 2.0
                voltages_t[sign_index] = inverse @ analytic_vt.conj() / 2.0
                currents_f = inverse @ analytic_if.conj() / 2.0
                currents_t = inverse @ analytic_it.conj() / 2.0
            advance: complex = complex(advances[sign_index])
            for mode_index in range(self.m):
                mode = self.runtime_data.get_mode_data()[mode_index]
                fraction: float = min(max(mode.get_residual_delay_s() / self.h, 0.0), 1.0)
                delay: complex = advance ** (-mode.get_delay_step_count()) * (1.0 - fraction + fraction / advance)
                h_denominator: np.ndarray = advance - mode.get_hres_alpha()
                yc_denominator: np.ndarray = advance - mode.get_yc_alpha()
                if np.any(np.abs(h_denominator) <= 1.0e-14) or np.any(np.abs(yc_denominator) <= 1.0e-14):
                    raise ValueError("JMARTI periodic filter has an unresolved excitation-frequency pole")
                else:
                    pass
                h_response: complex = complex(mode.get_hres_constant_term() + np.sum(
                    mode.get_hres_beta() / h_denominator,
                ))
                yc_response: complex = complex(mode.get_yc_constant_term() + np.sum(
                    mode.get_yc_beta() / yc_denominator,
                ))
                if np.isfinite(yc_response) and np.isfinite(h_response):
                    pass
                else:
                    raise ValueError("JMARTI periodic full Yc or propagation response is not finite")
                propagation: complex = h_response * delay
                voltage_f: complex = complex(voltages_f[sign_index, mode_index])
                voltage_t: complex = complex(voltages_t[sign_index, mode_index])
                boundary: np.ndarray = np.array(((1.0, propagation), (propagation, 1.0)), dtype=complex)
                if np.isfinite(boundary).all() and np.isfinite(voltage_f) and np.isfinite(voltage_t):
                    pass
                else:
                    raise ValueError("JMARTI periodic voltage boundary is not finite")
                if abs(1.0 - propagation * propagation) <= 1.0e-14:
                    # Only this degenerate voltage boundary may use the current
                    # quadrature. Direct Yc would discard the fitted dynamics.
                    current_f: complex = complex(currents_f[mode_index])
                    current_t: complex = complex(currents_t[mode_index])
                    if not np.isfinite(yc_response) or yc_response == 0.0:
                        raise ValueError("JMARTI singular boundary cannot be resolved with zero or nonfinite full Yc")
                    else:
                        pass
                    wave_f: complex = 0.5 * (voltage_f + current_f / yc_response)
                    wave_t: complex = 0.5 * (voltage_t + current_t / yc_response)
                    residuals: np.ndarray = np.array((
                        wave_f + propagation * wave_t - voltage_f,
                        wave_t + propagation * wave_f - voltage_t,
                        yc_response * (wave_f - propagation * wave_t) - current_f,
                        yc_response * (wave_t - propagation * wave_f) - current_t,
                    ), dtype=complex)
                    # Bound each equation separately by its term magnitudes and
                    # a conservative count of scalar transform/filter/residual
                    # operations; do not use the test's physical error tolerance.
                    scales: np.ndarray = np.array((
                        max(1.0, abs(voltage_f), abs(wave_f) + abs(propagation * wave_t)),
                        max(1.0, abs(voltage_t), abs(wave_t) + abs(propagation * wave_f)),
                        max(1.0, abs(current_f), abs(yc_response * wave_f) + abs(yc_response * propagation * wave_t)),
                        max(1.0, abs(current_t), abs(yc_response * wave_t) + abs(yc_response * propagation * wave_f)),
                    ), dtype=float)
                    operation_count: int = 32 + 8 * (self.m + yc_denominator.size + h_denominator.size)
                    bounds: np.ndarray = np.finfo(np.float64).eps * operation_count * scales
                    if np.isfinite(residuals).all() and np.isfinite(bounds).all() and np.all(np.abs(residuals) <= bounds):
                        pass
                    else:
                        raise ValueError("JMARTI singular boundary has incompatible terminal voltages or currents")
                else:
                    waves: np.ndarray = np.linalg.solve(boundary, np.array((voltage_f, voltage_t), dtype=complex))
                    wave_f = complex(waves[0])
                    wave_t = complex(waves[1])
                if np.isfinite(wave_f) and np.isfinite(wave_t):
                    pass
                else:
                    raise ValueError("JMARTI periodic outgoing waves are not finite")
                outgoing_f[sign_index, mode_index] = wave_f
                outgoing_t[sign_index, mode_index] = wave_t
                delays[sign_index, mode_index] = delay
                propagations[sign_index, mode_index] = propagation

        # A real excitation contains both signs. Individual conjugate-pole
        # states remain complex even when their combined output is real.
        self.buf_a_f.fill(0.0)
        self.buf_a_t.fill(0.0)
        self.yc_state_from.fill(0.0)
        self.yc_state_to.fill(0.0)
        self.hres_state_from.fill(0.0)
        self.hres_state_to.fill(0.0)
        slot: int
        for sign_index in range(2):
            advance = complex(advances[sign_index])
            for mode_index in range(self.m):
                mode = self.runtime_data.get_mode_data()[mode_index]
                wave_f = complex(outgoing_f[sign_index, mode_index])
                wave_t = complex(outgoing_t[sign_index, mode_index])
                for slot in range(self.buffer_size):
                    sample_index: int = 0 if slot == 0 else slot - self.buffer_size
                    self.buf_a_f[slot, mode_index] += wave_f * advance ** sample_index
                    self.buf_a_t[slot, mode_index] += wave_t * advance ** sample_index
                h_count: int = int(self.hres_order_counts[mode_index])
                y_count: int = int(self.yc_order_counts[mode_index])
                self.hres_state_from[mode_index, :h_count] += _build_jmarti_periodic_state_row(
                    mode.get_hres_alpha(), mode.get_hres_beta(), delays[sign_index, mode_index] * wave_t, advance,
                )
                self.hres_state_to[mode_index, :h_count] += _build_jmarti_periodic_state_row(
                    mode.get_hres_alpha(), mode.get_hres_beta(), delays[sign_index, mode_index] * wave_f, advance,
                )
                self.yc_state_from[mode_index, :y_count] += _build_jmarti_periodic_state_row(
                    mode.get_yc_alpha(), mode.get_yc_beta(),
                    voltages_f[sign_index, mode_index] - 2.0 * propagations[sign_index, mode_index] * wave_t, advance,
                )
                self.yc_state_to[mode_index, :y_count] += _build_jmarti_periodic_state_row(
                    mode.get_yc_alpha(), mode.get_yc_beta(),
                    voltages_t[sign_index, mode_index] - 2.0 * propagations[sign_index, mode_index] * wave_f, advance,
                )

        ih_from: np.ndarray = np.sqrt(2.0) * np.imag(i_f0_phasor_red) - self.direct_yc_phase @ (np.sqrt(2.0) * np.imag(v_f0_phasor_red))
        ih_to: np.ndarray = np.sqrt(2.0) * np.imag(i_t0_phasor_red) - self.direct_yc_phase @ (np.sqrt(2.0) * np.imag(v_t0_phasor_red))
        if self.coupling_block is not None:
            # Separate known q from the instantaneous remote target waves.
            phase_from: np.ndarray = transform @ np.sum(outgoing_f, axis=0)
            phase_to: np.ndarray = transform @ np.sum(outgoing_t, axis=0)
            q_from: np.ndarray = np.sum(propagations * outgoing_t, axis=0) - self.instantaneous_h_modal * np.sum(outgoing_t, axis=0)
            q_to: np.ndarray = np.sum(propagations * outgoing_f, axis=0) - self.instantaneous_h_modal * np.sum(outgoing_f, axis=0)
            self.initial_phase_waves[0] = phase_from
            self.initial_phase_waves[1] = phase_to
            self.initial_voltage_offsets[0] = transform @ q_from
            self.initial_voltage_offsets[1] = transform @ q_to
            self.initial_source_phasors[0] = v_f0_phasor_red
            self.initial_source_phasors[1] = v_t0_phasor_red
            self.initial_source_phasors[2] = i_f0_phasor_red
            self.initial_source_phasors[3] = i_t0_phasor_red
            self.initial_source_frequency_hz = float(system_frequency_hz)
            self.initial_source_available = True
            ih_from = ih_from + 2.0 * np.real(self.phase_current_coupling @ phase_to)
            ih_to = ih_to + 2.0 * np.real(self.phase_current_coupling @ phase_from)
        else:
            pass
        return ih_from, ih_to

    def restore_initial_history(self) -> None:
        """Restore private coupled history before a new fixed-h run starts.

        :return: None; the existing problem owner republishes retained seeds.
        """
        if self.coupling_block is not None and self.initial_source_available:
            self.initialize_from_fundamental_phasors(
                self.initial_source_phasors[0], self.initial_source_phasors[1],
                self.initial_source_phasors[2], self.initial_source_phasors[3],
                self.initial_source_frequency_hz,
            )
        else:
            if self.coupling_block is not None:
                # Declared zero defaults are not promoted to physical source.
                self.buf_a_f.fill(0.0)
                self.buf_a_t.fill(0.0)
                self.yc_state_from.fill(0.0)
                self.yc_state_to.fill(0.0)
                self.hres_state_from.fill(0.0)
                self.hres_state_to.fill(0.0)
                self.initial_phase_waves.fill(0.0)
                self.initial_voltage_offsets.fill(0.0)
            else:
                pass

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
        else:
            pass
        step_counter -= 1
        v_f_now_phase: np.ndarray = np.asarray([x_prev[index] if index >= 0 else 0.0 for index in self.idx_vf], dtype=np.complex128)
        v_t_now_phase: np.ndarray = np.asarray([x_prev[index] if index >= 0 else 0.0 for index in self.idx_vt], dtype=np.complex128)
        v_f_now_modal: np.ndarray = self.runtime_data.get_modal_transform_inv() @ v_f_now_phase
        v_t_now_modal: np.ndarray = self.runtime_data.get_modal_transform_inv() @ v_t_now_phase
        # The outgoing voltage wave is a = v - b, where b is the
        # propagated incoming wave. Using (v + i/Yc_direct)/2 is valid only
        # for constant Yc and corrupts the frequency-dependent line response.
        a_f_now_modal: np.ndarray
        a_t_now_modal: np.ndarray
        index: int
        if self.coupling_block is not None:
            if any(index < 0 for index in self.idx_wave_f_re) or any(index < 0 for index in self.idx_wave_t_re):
                raise RuntimeError("JMARTI coupled accepted waves are not indexed")
            else:
                pass
            phase_from: np.ndarray = np.asarray(x_prev[self.idx_wave_f_re], dtype=complex)
            phase_to: np.ndarray = np.asarray(x_prev[self.idx_wave_t_re], dtype=complex)
            if self.phase_real_kernel:
                pass
            else:
                if any(index < 0 for index in self.idx_wave_f_im) or any(index < 0 for index in self.idx_wave_t_im):
                    raise RuntimeError("JMARTI coupled imaginary accepted waves are not indexed")
                else:
                    pass
                phase_from += 1j * x_prev[self.idx_wave_f_im]
                phase_to += 1j * x_prev[self.idx_wave_t_im]
            a_f_now_modal = self.runtime_data.get_modal_transform_inv() @ phase_from
            a_t_now_modal = self.runtime_data.get_modal_transform_inv() @ phase_to
        else:
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
        q_f_next_modal: np.ndarray = np.zeros(self.m, dtype=complex)
        q_t_next_modal: np.ndarray = np.zeros(self.m, dtype=complex)
        mode_index: int = 0

        while mode_index < self.m:
            ih_f_next_modal[mode_index], q_f_next_modal[mode_index] = _update_jmarti_mode_history(
                runtime=self,
                mode_index=mode_index,
                step_counter=step_counter,
                local_voltage_modal=v_f_now_modal[mode_index],
                remote_incident_buffer=self.buf_a_t,
                yc_state=self.yc_state_from,
                hres_state=self.hres_state_from,
            )
            ih_t_next_modal[mode_index], q_t_next_modal[mode_index] = _update_jmarti_mode_history(
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
        q_f_next_phase: np.ndarray = self.runtime_data.get_modal_transform() @ q_f_next_modal
        q_t_next_phase: np.ndarray = self.runtime_data.get_modal_transform() @ q_t_next_modal
        phase_index: int = 0

        while phase_index < self.m:
            full_params[self.idx_p_hf[phase_index]] = float(np.real(ih_f_next_phase[phase_index]))
            full_params[self.idx_p_ht[phase_index]] = float(np.real(ih_t_next_phase[phase_index]))
            if self.coupling_block is not None:
                full_params[self.idx_q_f_re[phase_index]] = q_f_next_phase[phase_index].real
                full_params[self.idx_q_t_re[phase_index]] = q_t_next_phase[phase_index].real
                if self.phase_real_kernel:
                    pass
                else:
                    full_params[self.idx_q_f_im[phase_index]] = q_f_next_phase[phase_index].imag
                    full_params[self.idx_q_t_im[phase_index]] = q_t_next_phase[phase_index].imag
            else:
                pass
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
            if attached_runtime_data.get_time_step_s() == time_step_s:
                return attached_runtime_data
            else:
                return build_jmarti_runtime_data(attached_runtime_data, time_step_s)
        else:
            attached_fit_bundle: JMartiFitBundle | None = get_jmarti_block_fit_bundle(line_block)

            if attached_fit_bundle is not None:
                runtime_data: JMartiRuntimeData = build_jmarti_runtime_data(attached_fit_bundle, time_step_s)
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
    if (np.isfinite(runtime.h) and runtime.h > 0.0
            and np.isfinite(runtime.runtime_data.get_time_step_s())
            and runtime.runtime_data.get_time_step_s() > 0.0
            and runtime.runtime_data.get_mode_count() == runtime.m
            and runtime.runtime_data.get_phase_labels() == tuple(runtime.active_ph)):
        pass
    else:
        raise ValueError("JMARTI runtime phases/timestep do not match the declared data")
    # Matching-h Data remains authoritative, but every discrete quantity used
    # by interpolation or a filter must be valid before allocation/declaration.
    # Continuous poles/residues/tau are not consumed on this path; their full
    # coherence belongs solely to the converter when a new h is requested.
    consumed_mode: JMartiModeRuntimeData
    alpha: np.ndarray
    beta: np.ndarray
    for consumed_mode in runtime.runtime_data.get_mode_data():
        if (consumed_mode.get_delay_step_count() >= 0
                and np.isfinite(consumed_mode.get_residual_delay_s())
                and np.isfinite(consumed_mode.get_yc_constant_term())
                and np.isfinite(consumed_mode.get_hres_constant_term())):
            pass
        else:
            raise ValueError("JMARTI consumed runtime delay/direct coefficients are invalid")
        for alpha, beta in ((consumed_mode.get_yc_alpha(), consumed_mode.get_yc_beta()),
                            (consumed_mode.get_hres_alpha(), consumed_mode.get_hres_beta())):
            if (alpha.ndim == 1 and beta.ndim == 1 and alpha.shape == beta.shape
                    and np.isfinite(alpha).all() and np.isfinite(beta).all()):
                pass
            else:
                raise ValueError("JMARTI consumed runtime filter arrays are invalid")
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
    # Finite coefficients alone do not guarantee representable matrix products.
    # Suppress only their expected arithmetic warnings, then reject immediately
    # before any final storage or private symbolic declarations are allocated.
    phase_admittance: np.ndarray
    with np.errstate(over="ignore", invalid="ignore"):
        phase_admittance = (runtime.runtime_data.get_modal_transform()
            @ np.diag(runtime.direct_yc_modal)
            @ runtime.runtime_data.get_modal_transform_inv())
    if phase_admittance.shape == (runtime.m, runtime.m) and np.isfinite(phase_admittance).all():
        runtime.direct_yc_phase = np.real(phase_admittance)
    else:
        raise ValueError("JMARTI computed phase admittance is not representable")

    # Instantaneous feedback is represented by private wave coordinates. B
    # uses exactly the interpolation weight used by the unchanged sampler.
    mode_index = 0
    while mode_index < runtime.m:
        mode_data = runtime.runtime_data.get_mode_data()[mode_index]
        if mode_data.get_delay_step_count() == 0:
            fraction: float = min(max(mode_data.get_residual_delay_s() / runtime.h, 0.0), 1.0)
            runtime.instantaneous_h_modal[mode_index] = mode_data.get_hres_constant_term() * (1.0 - fraction)
        else:
            pass
        mode_index += 1
    has_coupling: bool = bool(np.any(runtime.instantaneous_h_modal != 0.0))
    if has_coupling:
        runtime.phase_real_kernel = is_jmarti_phase_real_runtime_data(runtime.runtime_data)
        with np.errstate(over="ignore", invalid="ignore"):
            runtime.phase_coupling = (runtime.runtime_data.get_modal_transform()
                @ np.diag(runtime.instantaneous_h_modal)
                @ runtime.runtime_data.get_modal_transform_inv())
            runtime.phase_current_coupling = (runtime.runtime_data.get_modal_transform()
                @ np.diag(runtime.direct_yc_modal * runtime.instantaneous_h_modal)
                @ runtime.runtime_data.get_modal_transform_inv())
        if (np.isfinite(runtime.phase_coupling).all()
                and np.isfinite(runtime.phase_current_coupling).all()):
            pass
        else:
            raise ValueError("JMARTI computed phase coupling/current coupling is not representable")
    else:
        pass
    runtime.max_delay_steps = max(int(mode_data.get_delay_step_count()) for mode_data in runtime.runtime_data.get_mode_data())
    runtime.buffer_size = max(2, runtime.max_delay_steps + 2)
    runtime.buf_a_f = np.zeros((runtime.buffer_size, runtime.m), dtype=np.complex128)
    runtime.buf_a_t = np.zeros((runtime.buffer_size, runtime.m), dtype=np.complex128)
    runtime.yc_state_from = np.zeros((runtime.m, max(1, max_yc_order)), dtype=np.complex128)
    runtime.yc_state_to = np.zeros((runtime.m, max(1, max_yc_order)), dtype=np.complex128)
    runtime.hres_state_from = np.zeros((runtime.m, max(1, max_hres_order)), dtype=np.complex128)
    runtime.hres_state_to = np.zeros((runtime.m, max(1, max_hres_order)), dtype=np.complex128)
    if has_coupling:
        runtime.coupling_var_factory = VarFactory(name=f"{runtime.line.name} JMARTI private waves")
        vf: VarFactory = runtime.coupling_var_factory
        runtime.initial_source_phasors = np.zeros((4, runtime.m), dtype=complex)
        runtime.initial_phase_waves = np.zeros((2, runtime.m), dtype=complex)
        runtime.initial_voltage_offsets = np.zeros((2, runtime.m), dtype=complex)
        phase: str = runtime.active_ph[0]
        runtime.outgoing_wave_f_re = list((vf.add_var(f"a_f_re_{phase}"),)) * runtime.m
        runtime.outgoing_wave_t_re = list((vf.add_var(f"a_t_re_{phase}"),)) * runtime.m
        runtime.incoming_voltage_f_re = list((vf.add_var(f"q_f_re_{phase}"),)) * runtime.m
        runtime.incoming_voltage_t_re = list((vf.add_var(f"q_t_re_{phase}"),)) * runtime.m
        phase_index: int
        for phase_index in range(1, runtime.m):
            phase = runtime.active_ph[phase_index]
            runtime.outgoing_wave_f_re[phase_index] = vf.add_var(f"a_f_re_{phase}")
            runtime.outgoing_wave_t_re[phase_index] = vf.add_var(f"a_t_re_{phase}")
            runtime.incoming_voltage_f_re[phase_index] = vf.add_var(f"q_f_re_{phase}")
            runtime.incoming_voltage_t_re[phase_index] = vf.add_var(f"q_t_re_{phase}")
        runtime.idx_wave_f_re = list([-1] * runtime.m)
        runtime.idx_wave_t_re = list([-1] * runtime.m)
        runtime.idx_q_f_re = list([-1] * runtime.m)
        runtime.idx_q_t_re = list([-1] * runtime.m)
        if runtime.phase_real_kernel:
            coordinate_count: int = 2 * runtime.m
        else:
            coordinate_count = 4 * runtime.m
            phase = runtime.active_ph[0]
            runtime.outgoing_wave_f_im = list((vf.add_var(f"a_f_im_{phase}"),)) * runtime.m
            runtime.outgoing_wave_t_im = list((vf.add_var(f"a_t_im_{phase}"),)) * runtime.m
            runtime.incoming_voltage_f_im = list((vf.add_var(f"q_f_im_{phase}"),)) * runtime.m
            runtime.incoming_voltage_t_im = list((vf.add_var(f"q_t_im_{phase}"),)) * runtime.m
            for phase_index in range(1, runtime.m):
                phase = runtime.active_ph[phase_index]
                runtime.outgoing_wave_f_im[phase_index] = vf.add_var(f"a_f_im_{phase}")
                runtime.outgoing_wave_t_im[phase_index] = vf.add_var(f"a_t_im_{phase}")
                runtime.incoming_voltage_f_im[phase_index] = vf.add_var(f"q_f_im_{phase}")
                runtime.incoming_voltage_t_im[phase_index] = vf.add_var(f"q_t_im_{phase}")
            runtime.idx_wave_f_im = list([-1] * runtime.m)
            runtime.idx_wave_t_im = list([-1] * runtime.m)
            runtime.idx_q_f_im = list([-1] * runtime.m)
            runtime.idx_q_t_im = list([-1] * runtime.m)
        wave_groups: tuple[list[Var], ...] = (runtime.outgoing_wave_f_re, runtime.outgoing_wave_t_re, runtime.outgoing_wave_f_im, runtime.outgoing_wave_t_im)
        parameter_groups: tuple[list[Var], ...] = (runtime.incoming_voltage_f_re, runtime.incoming_voltage_t_re, runtime.incoming_voltage_f_im, runtime.incoming_voltage_t_im)
        wave_vars: list[Var] = list((runtime.outgoing_wave_f_re[0],)) * coordinate_count
        group: list[Var]
        variable: Var
        index: int = 0
        for group in wave_groups:
            for variable in group:
                wave_vars[index] = variable
                index += 1
        events: dict[Var, Expr | Const] = dict()
        for group in parameter_groups:
            for variable in group:
                events[variable] = vf.add_const(0.0)
        placeholder: Const = vf.add_const(0.0)
        rows: list[Expr] = list((placeholder,)) * coordinate_count
        runtime.coupling_block = Block(algebraic_vars=wave_vars,
            algebraic_eqs=rows,
            event_dict=events, name=f"{runtime.line.name} JMARTI wave companion")
    else:
        pass


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
                                hres_state: np.ndarray) -> tuple[complex, complex]:
    """
    Advance one modal channel and return the next-step history current.

    :param runtime: Owning JMARTI runtime.
    :param mode_index: Modal channel index.
    :param step_counter: Current accepted step counter.
    :param local_voltage_modal: Local terminal voltage in modal coordinates.
    :param remote_incident_buffer: Ring buffer of remote outgoing waves.
    :param yc_state: Padded local Yc state matrix.
    :param hres_state: Padded propagation-filter state matrix.
    :return: Next-step history current and known incoming voltage offset.
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

    next_hres_output: complex
    if runtime.coupling_block is not None and mode_data.get_delay_step_count() == 0:
        # The unwritten target slot belongs to the algebraic solve, not memory.
        next_hres_output = ((mode_data.get_hres_constant_term() - runtime.instantaneous_h_modal[mode_index])
            * remote_incident_buffer[step_counter % runtime.buffer_size, mode_index]
            + _sum_state_row(hres_state, mode_index, hres_order_count))
    else:
        delayed_wave_next: complex = _get_delayed_incident_wave(runtime, mode_index, step_counter, remote_incident_buffer, next_step=True)
        next_hres_output = mode_data.get_hres_constant_term() * delayed_wave_next + _sum_state_row(hres_state, mode_index, hres_order_count)
    next_yc_dynamic_output: complex = _sum_state_row(yc_state, mode_index, yc_order_count)
    return next_yc_dynamic_output - 2.0 * runtime.direct_yc_modal[mode_index] * next_hres_output, next_hres_output
