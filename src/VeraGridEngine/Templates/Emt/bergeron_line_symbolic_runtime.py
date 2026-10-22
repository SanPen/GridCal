# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any, List, Tuple

import numpy as np

from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import BergeronHistoryRuntime


class BergeronHistorySymbolicRuntime(BergeronHistoryRuntime):
    """
    Symbolic helper for Bergeron history runtime.

    This class reuses the existing numerical setup (phase reduction, Gc/H matrices,
    indexing) and exposes symbolic-friendly builders for:

    - branch nodal injections
    - history recursion update expressions
    """

    __slots__ = (
        "sym_v_f_tau",
        "sym_v_t_tau",
        "sym_i_f_tau",
        "sym_i_t_tau",
        "sym_ih_f",
        "sym_ih_t",
    )

    def __init__(self, line: Any, line_block: Any, h: float, sbase: float, fbase: float) -> None:
        super().__init__(line=line, line_block=line_block, h=h, sbase=sbase, fbase=fbase)
        self.sym_v_f_tau: List[Any] | None = None
        self.sym_v_t_tau: List[Any] | None = None
        self.sym_i_f_tau: List[Any] | None = None
        self.sym_i_t_tau: List[Any] | None = None
        self.sym_ih_f: List[Any] | None = None
        self.sym_ih_t: List[Any] | None = None

    def bind_symbolic_state(
            self,
            v_f_tau: List[Any],
            v_t_tau: List[Any],
            i_f_tau: List[Any],
            i_t_tau: List[Any],
            ih_f: List[Any],
            ih_t: List[Any],
    ) -> None:
        """
        Bind reduced-phase symbolic vectors used by symbolic update/injection builders.

        :param v_f_tau: Delayed from-side voltages in reduced active-phase ordering.
        :param v_t_tau: Delayed to-side voltages in reduced active-phase ordering.
        :param i_f_tau: Delayed from-side currents in reduced active-phase ordering.
        :param i_t_tau: Delayed to-side currents in reduced active-phase ordering.
        :param ih_f: Current from-side Bergeron history terms in reduced active-phase ordering.
        :param ih_t: Current to-side Bergeron history terms in reduced active-phase ordering.
        :return: None.
        """
        expected = self.m
        all_vectors = [v_f_tau, v_t_tau, i_f_tau, i_t_tau, ih_f, ih_t]
        if any(len(vec) != expected for vec in all_vectors):
            raise ValueError(f"All reduced symbolic vectors must have length m={expected}")

        self.sym_v_f_tau = list(v_f_tau)
        self.sym_v_t_tau = list(v_t_tau)
        self.sym_i_f_tau = list(i_f_tau)
        self.sym_i_t_tau = list(i_t_tau)
        self.sym_ih_f = list(ih_f)
        self.sym_ih_t = list(ih_t)

    def get_symbolic_injections(
            self,
            v_f_vars: List[Any] | None = None,
            v_t_vars: List[Any] | None = None,
            ih_f_vars: List[Any] | None = None,
            ih_t_vars: List[Any] | None = None,
    ) -> Tuple[List[Any], List[Any]]:
        """
        Build Bergeron nodal current injections in full NABC shape.

        Equations per active phase k:
            i_f[k] = sum_j Gc[k, j] * v_f[j] + Ih_f[k]
            i_t[k] = sum_j Gc[k, j] * v_t[j] + Ih_t[k]

        :param v_f_vars: Active-phase from-side voltages (reduced ordering).
        :param v_t_vars: Active-phase to-side voltages (reduced ordering).
        :param ih_f_vars: Active-phase from-side history terms (reduced ordering).
        :param ih_t_vars: Active-phase to-side history terms (reduced ordering).
        :return: Two lists (i_f_full, i_t_full) in full NABC layout using None on missing phases.
        """
        if v_f_vars is None:
            v_f_vars = self.sym_v_f_tau
        if v_t_vars is None:
            v_t_vars = self.sym_v_t_tau
        if ih_f_vars is None:
            ih_f_vars = self.sym_ih_f
        if ih_t_vars is None:
            ih_t_vars = self.sym_ih_t

        if v_f_vars is None or v_t_vars is None or ih_f_vars is None or ih_t_vars is None:
            raise ValueError("Symbolic injection vectors are not bound. Call bind_symbolic_state(...) first.")

        if not (len(v_f_vars) == len(v_t_vars) == len(ih_f_vars) == len(ih_t_vars) == self.m):
            raise ValueError("Reduced Bergeron vectors must all have length m")

        i_f_red: List[Any] = list()
        i_t_red: List[Any] = list()

        for i in range(self.m):
            expr_f = sum(self.Gc_red[i, j] * v_f_vars[j] for j in range(self.m)) + ih_f_vars[i]
            expr_t = sum(self.Gc_red[i, j] * v_t_vars[j] for j in range(self.m)) + ih_t_vars[i]
            i_f_red.append(expr_f)
            i_t_red.append(expr_t)

        i_f_full: List[Any] = [None, None, None, None]
        i_t_full: List[Any] = [None, None, None, None]

        for k_red, k_full in enumerate(self.phase_idx):
            i_f_full[k_full] = i_f_red[k_red]
            i_t_full[k_full] = i_t_red[k_red]

        return i_f_full, i_t_full

    def get_symbolic_update(
            self,
            v_f_tau: List[Any] | None = None,
            v_t_tau: List[Any] | None = None,
            i_f_tau: List[Any] | None = None,
            i_t_tau: List[Any] | None = None,
    ) -> Tuple[List[Any], List[Any]]:
        """
        Build symbolic expressions for next Bergeron history terms.

        This mirrors the existing numerical update in ``update_history`` but accepts
        symbolic variables/expressions at delayed time tau:

            X_f = -Gc * v_t(t-tau) - i_t(t-tau)
            Y_f = -Gc * v_f(t-tau) - i_f(t-tau)
            X_t = -Gc * v_f(t-tau) - i_f(t-tau)
            Y_t = -Gc * v_t(t-tau) - i_t(t-tau)

            Ih_f_next = 0.5 * ((I + H) * X_f + (I - H) * Y_f)
            Ih_t_next = 0.5 * ((I + H) * X_t + (I - H) * Y_t)

        :param v_f_tau: Reduced delayed from-side voltages.
        :param v_t_tau: Reduced delayed to-side voltages.
        :param i_f_tau: Reduced delayed from-side currents.
        :param i_t_tau: Reduced delayed to-side currents.
        :return: (Ih_f_next, Ih_t_next) reduced-phase symbolic expressions.
        """
        if v_f_tau is None:
            v_f_tau = self.sym_v_f_tau
        if v_t_tau is None:
            v_t_tau = self.sym_v_t_tau
        if i_f_tau is None:
            i_f_tau = self.sym_i_f_tau
        if i_t_tau is None:
            i_t_tau = self.sym_i_t_tau

        if v_f_tau is None or v_t_tau is None or i_f_tau is None or i_t_tau is None:
            raise ValueError("Symbolic update vectors are not bound. Call bind_symbolic_state(...) first.")

        if not (len(v_f_tau) == len(v_t_tau) == len(i_f_tau) == len(i_t_tau) == self.m):
            raise ValueError("Reduced delayed vectors must all have length m")

        h_plus = np.eye(self.m) + self.H_red
        h_minus = np.eye(self.m) - self.H_red

        x_f: List[Any] = list()
        y_f: List[Any] = list()
        x_t: List[Any] = list()
        y_t: List[Any] = list()

        for i in range(self.m):
            x_f.append(-sum(self.Gc_red[i, j] * v_t_tau[j] for j in range(self.m)) - i_t_tau[i])
            y_f.append(-sum(self.Gc_red[i, j] * v_f_tau[j] for j in range(self.m)) - i_f_tau[i])
            x_t.append(-sum(self.Gc_red[i, j] * v_f_tau[j] for j in range(self.m)) - i_f_tau[i])
            y_t.append(-sum(self.Gc_red[i, j] * v_t_tau[j] for j in range(self.m)) - i_t_tau[i])

        ih_f_next: List[Any] = list()
        ih_t_next: List[Any] = list()

        for i in range(self.m):
            ih_f_next.append(
                0.5
                * (
                    sum(h_plus[i, j] * x_f[j] for j in range(self.m))
                    + sum(h_minus[i, j] * y_f[j] for j in range(self.m))
                )
            )
            ih_t_next.append(
                0.5
                * (
                    sum(h_plus[i, j] * x_t[j] for j in range(self.m))
                    + sum(h_minus[i, j] * y_t[j] for j in range(self.m))
                )
            )

        return ih_f_next, ih_t_next
