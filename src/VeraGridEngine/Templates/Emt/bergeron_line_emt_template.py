# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import scipy.linalg as spla
from typing import List, Tuple, Any

from VeraGridEngine.Utils.Symbolic.block import Block, Var
from VeraGridEngine.enumerations import DeviceType, EmtLineTypes, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp


def _build_symmetric_abc_matrix_from_sequence_values(positive_sequence_value: complex,
                                                     zero_sequence_value: complex) -> np.ndarray:
    """
    Reconstruct one symmetric ABC matrix from one pair of sequence values.

    :param positive_sequence_value: Positive-sequence scalar value.
    :param zero_sequence_value: Zero-sequence scalar value.
    :return: Symmetric 3x3 phase-domain matrix.
    """
    diagonal_value: complex = (2.0 * positive_sequence_value + zero_sequence_value) / 3.0
    off_diagonal_value: complex = (zero_sequence_value - positive_sequence_value) / 3.0
    matrix_abc: np.ndarray = np.full((3, 3), off_diagonal_value, dtype=np.complex128)
    np.fill_diagonal(matrix_abc, diagonal_value)
    return matrix_abc


def _get_sequence_zero_value(primary_value: float, zero_value: float) -> float:
    """
    Resolve one usable zero-sequence scalar from one line object.

    The balanced branch data model may omit explicit zero-sequence values. In that
    case the Bergeron fallback must still build one symmetric phase-domain model.
    The least surprising approximation is to reuse the positive-sequence value.

    :param primary_value: Positive-sequence scalar value.
    :param zero_value: Candidate zero-sequence scalar value.
    :return: Zero-sequence scalar selected for reconstruction.
    """
    if abs(float(zero_value)) > 1.0e-20:
        return float(zero_value)
    else:
        return float(primary_value)


def _build_line_parameter_matrices_from_template_or_balanced_data(line: Any,
                                                                  sbase: float,
                                                                  fbase: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build full phase-domain ``R``, ``L`` and ``C`` matrices for one Bergeron line.

    The preferred path uses the detailed EMT template matrices. When no template is
    attached, the function reconstructs one symmetric ABC equivalent from the
    balanced branch parameters already stored on the line object.

    :param line: Line API object.
    :param sbase: System base power in MVA.
    :param fbase: Nominal frequency in Hz.
    :return: Tuple ``(R_full, L_full, C_full)`` in per-unit total-line form.
    """
    w: float = 2.0 * np.pi * float(fbase)

    if line.template is not None:
        vbase_volt: float = float(line.bus_from.Vnom) * 1e3
        sbase_va: float = float(sbase) * 1e6
        zbase_ohm: float = (vbase_volt * vbase_volt) / sbase_va
        ybase_siemens: float = 1.0 / zbase_ohm

        # Bergeron travelling-wave dynamics are highly sensitive to the exact
        # per-length ``Z`` and ``Y`` matrices. The original template matrices are
        # already stored in the precise physical form expected by this model, and
        # the delay calculation in ``line.get_tau()`` still uses that same source.
        # Keeping Bergeron on the template path therefore preserves one internally
        # consistent representation for ``R/L/C`` and ``tau``.
        z_phys_m: np.ndarray = np.asarray(line.template.z_nabc, dtype=np.complex128) / 1e3
        y_phys_m: np.ndarray = np.asarray(line.template.y_nabc, dtype=np.complex128) / 1e3

        z_pu_m: np.ndarray = z_phys_m / zbase_ohm
        y_pu_m: np.ndarray = y_phys_m / ybase_siemens

        r_full: np.ndarray = np.real(z_pu_m) * float(line.length)
        l_full: np.ndarray = (np.imag(z_pu_m) / w) * float(line.length)
        c_full: np.ndarray = (np.imag(y_pu_m) / w) * float(line.length)
        return r_full, l_full, c_full
    else:
        pass

    # if line.ys is not None and line.ysh is not None:
    #     vbase_volt: float = float(line.bus_from.Vnom) * 1e3
    #     sbase_va: float = float(sbase) * 1e6
    #     zbase_ohm: float = (vbase_volt * vbase_volt) / sbase_va
    #     ybase_siemens: float = 1.0 / zbase_ohm
    #
    #     # The template stores Carson matrices per km. Bergeron uses per-meter and
    #     # then converts them to per-unit before forming the total line matrices.
    #     z_phys_m: np.ndarray = np.asarray(line.ys.values, dtype=np.complex128) / 1e3
    #     y_phys_m: np.ndarray = np.asarray(line.ysh.values, dtype=np.complex128) / 1e3
    #     z_pu_m: np.ndarray = z_phys_m / zbase_ohm
    #     y_pu_m: np.ndarray = y_phys_m / ybase_siemens
    #
    #     r_full: np.ndarray = np.real(z_pu_m) * float(line.length)
    #     l_full: np.ndarray = (np.imag(z_pu_m) / w) * float(line.length)
    #     c_full: np.ndarray = (np.imag(y_pu_m) / w) * float(line.length)
    #     return r_full, l_full, c_full



    # Without a detailed template we rebuild one symmetric 3-phase equivalent from
    # the sequence branch data. This mirrors the balanced-to-phase reconstruction
    # already used elsewhere for EMT line fitting.
    r1_value: float = float(line.R)
    x1_value: float = float(line.X)
    b1_value: float = float(line.B)
    r0_value: float = _get_sequence_zero_value(primary_value=r1_value, zero_value=float(line.R0))
    x0_value: float = _get_sequence_zero_value(primary_value=x1_value, zero_value=float(line.X0))
    b0_value: float = _get_sequence_zero_value(primary_value=b1_value, zero_value=float(line.B0))

    z1_value: complex = complex(r1_value, x1_value)
    z0_value: complex = complex(r0_value, x0_value)
    y1_value: complex = complex(0.0, b1_value)
    y0_value: complex = complex(0.0, b0_value)

    z_full: np.ndarray = _build_symmetric_abc_matrix_from_sequence_values(
        positive_sequence_value=z1_value,
        zero_sequence_value=z0_value,
    )
    y_full: np.ndarray = _build_symmetric_abc_matrix_from_sequence_values(
        positive_sequence_value=y1_value,
        zero_sequence_value=y0_value,
    )

    r_full = np.real(z_full)
    l_full = np.imag(z_full) / w
    c_full = np.imag(y_full) / w
    return r_full, l_full, c_full

class BergeronLineEmtTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(
            vf,
            params=[
                TemplateProp(name="phN", units="", descr="Whether neutral is active.", tpe=bool, value=False),
                TemplateProp(name="phA", units="", descr="Whether phase A is active.", tpe=bool, value=True),
                TemplateProp(name="phB", units="", descr="Whether phase B is active.", tpe=bool, value=True),
                TemplateProp(name="phC", units="", descr="Whether phase C is active.", tpe=bool, value=True),
                TemplateProp(name="name", units="", descr="Symbolic block name.", tpe=str, value="Bergeron"),
            ]
        )

    def eval(self) -> EmtModelTemplate:
        phN: bool = self.get_value("phN")
        phA: bool = self.get_value("phA")
        phB: bool = self.get_value("phB")
        phC: bool = self.get_value("phC")
        name: str = self.get_value("name")

        return get_bergeron_line_emt_template(
            self.vf, phN, phA, phB, phC, name,
        )


def get_bergeron_line_emt_template(
    vf: VarFactory,
    phN: bool = False,
    phA: bool = True,
    phB: bool = True,
    phC: bool = True,
    name: str | None = "Bergeron") -> EmtModelTemplate:
    """
    Create the symbolic EMT template for a Bergeron line.

    Only active phases in NABC are represented.
    The history terms are modelled as runtime-updated event parameters.
    :param vf: EMT variable factory.
    :param phN: Bool. True if the line has neutral, else False.
    :param phA: Bool. True if the line has phase A, else False.
    :param phB: Bool. True if the line has phase B, else False.
    :param phC: Bool. True if the line has phase C, else False.
    :param name: Symbolic model name.
    :return: EMT bergeron-line model template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name

    templ.block.name = EmtLineTypes.Bergeron.value


    ph_labels = ["N", "A", "B", "C"]
    ph_mask = np.array([
        phN,
        phA,
        phB,
        phC,
    ], dtype=bool)

    active_ph = [lab for lab, on in zip(ph_labels, ph_mask) if on]

    vf_keys = dict({
        "N": VarPowerFlowReferenceType.vf_N,
        "A": VarPowerFlowReferenceType.vf_A,
        "B": VarPowerFlowReferenceType.vf_B,
        "C": VarPowerFlowReferenceType.vf_C,
    })
    vt_keys = dict({
        "N": VarPowerFlowReferenceType.vt_N,
        "A": VarPowerFlowReferenceType.vt_A,
        "B": VarPowerFlowReferenceType.vt_B,
        "C": VarPowerFlowReferenceType.vt_C,
    })

    vf_vars = [vf.add_var(name=f"vf_{ph_label}", reference=vf_keys[ph_label]) for ph_label in active_ph]
    vt_vars = [vf.add_var(name=f"vt_{ph_label}", reference=vt_keys[ph_label]) for ph_label in active_ph]

    block: Block = Block()
    block.in_vars = vf_vars + vt_vars


    ih_f = [vf.add_var(f"Ih_f_{ph}") for ph in active_ph]
    ih_t = [vf.add_var(f"Ih_t_{ph}") for ph in active_ph]

    # I history
    block.event_dict = {p: vf.add_const(0.0) for p in (ih_f + ih_t)}
    block.out_vars = list()

    templ.block.children.append(block)
    templ.block.external_mapping = block.external_mapping
    templ.block.in_vars = block.in_vars
    templ.block.out_vars = block.out_vars


    return templ


class BergeronHistoryRuntime:
    """
    Runtime companion for a Bergeron line in reduced active-phase space.
    """
    __slots__ = (
        "line",
        "block",
        "h",
        "hist_if",
        "hist_it",
        "hist_Ih_f",
        "hist_Ih_t",
        "hist_Ih_f_next",
        "hist_Ih_t_next",
        "ph_labels",
        "ph_mask",
        "phase_idx",
        "active_ph",
        "m",
        "Ih_f",
        "Ih_t",
        "Gc_red",
        "H_red",
        "n_delay",
        "buf_vf",
        "buf_vt",
        "buf_if",
        "buf_it",
        "v_f_vars",
        "v_t_vars",
        "idx_vf",
        "idx_vt",
        "idx_p_hf",
        "idx_p_ht",
    )

    def __init__(self, line: Any, line_block: Block, h: float, sbase: float, fbase: float) -> None:
        self.line = line
        self.block = line_block
        self.h = float(h)

        self.hist_if: List[np.ndarray] = []
        self.hist_it: List[np.ndarray] = []
        self.hist_Ih_f: List[np.ndarray] = []
        self.hist_Ih_t: List[np.ndarray] = []
        self.hist_Ih_f_next: List[np.ndarray] = []
        self.hist_Ih_t_next: List[np.ndarray] = []

        self.ph_labels = ["N", "A", "B", "C"]
        self.ph_mask = np.array([
            bool(line.ys.phN),
            bool(line.ys.phA),
            bool(line.ys.phB),
            bool(line.ys.phC),
        ], dtype=bool)

        idx_global = np.where(self.ph_mask)[0]
        self.phase_idx: List[int] = [int(i) for i in idx_global]
        self.active_ph: List[str] = [self.ph_labels[i] for i in self.phase_idx]
        self.m: int = len(self.active_ph)

        if self.m == 0:
            raise ValueError(f"Bergeron line '{line.name}' has no enabled phases in line.ys")

        if self.block.event_dict is None:
            raise ValueError(f"Bergeron line '{line.name}': block.event_dict is None")

        self.Ih_f = self._extract_hist_vars(prefix=f"Ih_f_")
        self.Ih_t = self._extract_hist_vars(prefix=f"Ih_t_")

        w = 2.0 * np.pi * fbase
        R_full, L_full, C_full = _build_line_parameter_matrices_from_template_or_balanced_data(
            line=line,
            sbase=sbase,
            fbase=fbase,
        )

        n_mat = R_full.shape[0]

        if R_full.shape[0] != R_full.shape[1]:
            raise ValueError(
                f"Bergeron line '{line.name}' has a non-square Z matrix with shape {R_full.shape}."
            )

        if L_full.shape != R_full.shape or C_full.shape != R_full.shape:
            raise ValueError(
                f"Bergeron line '{line.name}' has inconsistent matrix shapes: "
                f"R={R_full.shape}, L={L_full.shape}, C={C_full.shape}."
            )

        if n_mat == 3:
            # Matrices are stored in compact ABC order
            if 0 in idx_global:
                raise ValueError(
                    f"Bergeron line '{line.name}' has N phase enabled but template matrices are 3x3 (ABC)."
                )
            idx_mat = idx_global - 1  # A->0, B->1, C->2

        elif n_mat == 4:
            # Matrices are stored in full NABC order
            idx_mat = idx_global

        else:
            raise ValueError(
                f"Unsupported template matrix size {R_full.shape} for line '{line.name}' "
                f"(expected 3x3 or 4x4)."
            )

        idx_mat = np.array(idx_mat, dtype=int)

        R = R_full[np.ix_(idx_mat, idx_mat)]
        L = L_full[np.ix_(idx_mat, idx_mat)]
        C = C_full[np.ix_(idx_mat, idx_mat)]

        try:
            Zc = spla.sqrtm(L @ np.linalg.inv(C))
        except Exception:
            Zc = np.eye(self.m) * np.sqrt(L[0, 0] / (C[0, 0] + 1e-20))

        Z_eq = np.real(Zc) + R / 4.0
        self.Gc_red = np.linalg.inv(Z_eq)
        self.H_red = (np.real(Zc) - R / 4.0) @ self.Gc_red

        tau = line.get_tau(w=w)
        self.n_delay = max(1, int(round(tau / self.h)))

        self.buf_vf = np.zeros((self.n_delay + 1, self.m), dtype=float)
        self.buf_vt = np.zeros((self.n_delay + 1, self.m), dtype=float)
        self.buf_if = np.zeros((self.n_delay + 1, self.m), dtype=float)
        self.buf_it = np.zeros((self.n_delay + 1, self.m), dtype=float)

        self.v_f_vars = None
        self.v_t_vars = None

        self.idx_vf = None
        self.idx_vt = None
        self.idx_p_hf = None
        self.idx_p_ht = None

    def _extract_hist_vars(self, prefix: str) -> List[Var]:
        vars_by_name = dict()
        block_item: Block
        history_var: Var
        for block_item in self.block.get_all_blocks():
            for history_var in block_item.event_dict.keys():
                vars_by_name[str(history_var.name)] = history_var
        out: List[Var] = []

        for ph in self.active_ph:
            key = f"{prefix}{ph}"
            var = vars_by_name.get(key, None)
            if var is None:
                matching_names: List[str] = list()

                for candidate_name in vars_by_name.keys():
                    if candidate_name.startswith(prefix.split("_", 2)[0] + "_" + prefix.split("_", 2)[1] + "_") and candidate_name.endswith(f"_{ph}"):
                        matching_names.append(candidate_name)
                    else:
                        pass

                if len(matching_names) == 1:
                    var = vars_by_name[matching_names[0]]
                else:
                    raise ValueError(f"Missing Bergeron history var '{key}' for line '{self.line.name}'.")
            else:
                pass
            out.append(var)

        return out

    def bind_terminals(self, v_f_vars: List[Any], v_t_vars: List[Any]) -> None:
        """
        Bind the bus terminal voltage variables for the active phases only.

        Every active line phase must be present in both terminal bus models.
        Missing voltages are treated as a topology/model consistency error.
        """
        self.v_f_vars = list()
        self.v_t_vars = list()

        for idx_full, ph in zip(self.phase_idx, self.active_ph):
            vf_i = v_f_vars[idx_full]
            vt_i = v_t_vars[idx_full]

            if vf_i is None:
                raise ValueError(
                    f"Bergeron line '{self.line.name}' has active phase '{ph}' "
                    f"but from-bus '{self.line.bus_from.name}' does not provide the corresponding EMT voltage variable."
                )

            if vt_i is None:
                raise ValueError(
                    f"Bergeron line '{self.line.name}' has active phase '{ph}' "
                    f"but to-bus '{self.line.bus_to.name}' does not provide the corresponding EMT voltage variable."
                )

            self.v_f_vars.append(vf_i)
            self.v_t_vars.append(vt_i)

    def get_nodal_injections(self) -> Tuple[List[Any], List[Any]]:
        if self.v_f_vars is None or self.v_t_vars is None:
            raise RuntimeError("bind_terminals(...) must be called before get_nodal_injections().")

        i_f_red: List[Any] = []
        i_t_red: List[Any] = []

        for i in range(self.m):
            expr_f = sum(self.Gc_red[i, j] * self.v_f_vars[j] for j in range(self.m)) + self.Ih_f[i]
            expr_t = sum(self.Gc_red[i, j] * self.v_t_vars[j] for j in range(self.m)) + self.Ih_t[i]
            i_f_red.append(expr_f)
            i_t_red.append(expr_t)

        i_f_full: List[Any] = [None, None, None, None]
        i_t_full: List[Any] = [None, None, None, None]

        for k_red, k_full in enumerate(self.phase_idx):
            i_f_full[k_full] = i_f_red[k_red]
            i_t_full[k_full] = i_t_red[k_red]

        return i_f_full, i_t_full

    def setup_indices(self, uid2idx_vars: dict, uid2idx_event_params: dict, params_offset: int = 0) -> None:
        self.idx_vf = [uid2idx_vars[v.uid] for v in self.v_f_vars]
        self.idx_vt = [uid2idx_vars[v.uid] for v in self.v_t_vars]
        self.idx_p_hf = [uid2idx_event_params[p.uid] + params_offset for p in self.Ih_f]
        self.idx_p_ht = [uid2idx_event_params[p.uid] + params_offset for p in self.Ih_t]

    def update_history(self, step_counter: int, x_prev: np.ndarray, full_params: np.ndarray) -> None:
        # The solver calls once at t=0, then before solving t=k*h with
        # x_prev at (k-1)*h. Store that accepted state at its own time index.
        k_curr = max(0, step_counter - 1) % (self.n_delay + 1)
        k_tau = (step_counter - self.n_delay) % (self.n_delay + 1)

        v_f_now = np.array([x_prev[i] if i >= 0 else 0.0 for i in self.idx_vf], dtype=float)
        v_t_now = np.array([x_prev[i] if i >= 0 else 0.0 for i in self.idx_vt], dtype=float)

        self.buf_vf[k_curr, :] = v_f_now
        self.buf_vt[k_curr, :] = v_t_now

        Ih_f_now = np.array([full_params[i] for i in self.idx_p_hf], dtype=float)
        Ih_t_now = np.array([full_params[i] for i in self.idx_p_ht], dtype=float)

        self.buf_if[k_curr, :] = self.Gc_red @ v_f_now + Ih_f_now
        self.buf_it[k_curr, :] = self.Gc_red @ v_t_now + Ih_t_now

        v_f_tau = self.buf_vf[k_tau, :]
        v_t_tau = self.buf_vt[k_tau, :]
        i_f_tau = self.buf_if[k_tau, :]
        i_t_tau = self.buf_it[k_tau, :]

        X_f = -self.Gc_red @ v_t_tau - i_t_tau
        Y_f = -self.Gc_red @ v_f_tau - i_f_tau
        X_t = -self.Gc_red @ v_f_tau - i_f_tau
        Y_t = -self.Gc_red @ v_t_tau - i_t_tau

        I = np.eye(self.m)
        I_hist_f = 0.5 * ((I + self.H_red) @ X_f + (I - self.H_red) @ Y_f)
        I_hist_t = 0.5 * ((I + self.H_red) @ X_t + (I - self.H_red) @ Y_t)

        # Current values actually used in this step
        i_f_now = self.Gc_red @ v_f_now + Ih_f_now
        i_t_now = self.Gc_red @ v_t_now + Ih_t_now

        self.hist_if.append(i_f_now.copy())
        self.hist_it.append(i_t_now.copy())
        self.hist_Ih_f.append(Ih_f_now.copy())
        self.hist_Ih_t.append(Ih_t_now.copy())

        # New history values prepared for the next step
        self.hist_Ih_f_next.append(I_hist_f.copy())
        self.hist_Ih_t_next.append(I_hist_t.copy())

        for i in range(self.m):
            full_params[self.idx_p_hf[i]] = I_hist_f[i]
            full_params[self.idx_p_ht[i]] = I_hist_t[i]


    def initialize_buffers_from_initial_point(
            self,
            v_f0_red: np.ndarray,
            v_t0_red: np.ndarray,
            i_f0_red: np.ndarray,
            i_t0_red: np.ndarray
    ) -> None:
        """
        Fill all delay buffers with the initial steady-state point.
        """
        for k in range(self.n_delay + 1):
            self.buf_vf[k, :] = v_f0_red
            self.buf_vt[k, :] = v_t0_red
            self.buf_if[k, :] = i_f0_red
            self.buf_it[k, :] = i_t0_red

    def initialize_buffers_from_phasors(
            self,
            v_f: np.ndarray,
            v_t: np.ndarray,
            i_f: np.ndarray,
            i_t: np.ndarray,
            frequency_hz: float,
    ) -> None:
        """Fill the delay ring with a periodic waveform in the EMT sine convention.

        Slot zero holds t=0. Slots 1..n_delay hold samples from
        -n_delay*h through -h, as read by update_history at startup.
        Phasors are RMS values on the system three-phase current base.
        """
        phasors = (v_f, v_t, i_f, i_t)
        buffers = (self.buf_vf, self.buf_vt, self.buf_if, self.buf_it)
        omega = 2.0 * np.pi * frequency_hz
        for k in range(self.n_delay + 1):
            sample_time = 0.0 if k == 0 else (k - self.n_delay - 1) * self.h
            rotation = np.exp(1j * omega * sample_time)
            for buffer, phasor in zip(buffers, phasors):
                buffer[k, :] = np.sqrt(2.0) * np.imag(phasor * rotation)
