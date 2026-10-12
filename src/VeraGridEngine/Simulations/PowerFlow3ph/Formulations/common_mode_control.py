# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from scipy.linalg import null_space
from scipy.sparse import csc_matrix, diags, vstack
from scipy.sparse.csgraph import connected_components

from VeraGridEngine.basic_structures import IntVec, CxVec, Vec, BoolVec
from VeraGridEngine.DataStructures.load_data import LoadData
from VeraGridEngine.DataStructures.generator_data import GeneratorData
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.DataStructures.shunt_data import ShuntData
from VeraGridEngine.enumerations import GeneratorType, ShuntConnectionType, ShuntControlMode, WindingType
from VeraGridEngine.Simulations.PowerFlow3ph.Formulations.positive_sequence_control import PositiveSequenceControl


def common_mode_constraints(matrix: csc_matrix, shifts: csc_matrix) -> csc_matrix:
    """Project a linear device response onto bus common shifts, allowing only summation roundoff.

    :param matrix: Terminal current coefficients, before combining different devices.
    :param shifts: One common NABC displacement per bus.
    :return: Row-scaled constraints on the bus displacements.
    """
    response: csc_matrix = (matrix @ shifts).tocsc()
    scale: csc_matrix = (abs(matrix) @ abs(shifts)).tocsc()
    columns: IntVec = np.repeat(np.arange(response.shape[1]), np.diff(response.indptr))
    bounds: Vec = np.asarray(scale[response.indices, columns]).ravel()
    response.data[np.abs(response.data) <= 32 * np.finfo(float).eps * bounds] = 0.0
    response.eliminate_zeros()
    norms: Vec = np.asarray(abs(response).sum(axis=1)).ravel()
    nonzero: BoolVec = norms > 0
    norms[nonzero] = 1.0 / norms[nonzero]
    return (diags(norms, format='csc') @ response).tocsc()


class CommonModeControl:
    """Select references only for structurally invariant, ungrounded common voltage modes."""

    __slots__ = ('phases', 'real_rows', 'imag_rows')

    def __init__(self, nc: NumericalCircuit, admittances: tuple, lookup: IntVec,
                 idx_p: IntVec, idx_q: IntVec, positive: PositiveSequenceControl) -> None:
        """Find independent floating groups using existing terminal matrices and injection models.

        :param nc: Compiled island, with the current topology and active devices.
        :param admittances: Original full NABC admittances, before passive-neutral reduction.
        :param lookup: Retained voltage indices after passive-neutral reduction.
        :param idx_p: Voltage indices with a real current-balance equation.
        :param idx_q: Voltage indices with an imaginary current-balance equation.
        :param positive: Existing positive-sequence injection and control classification.
        """
        ybus: csc_matrix = admittances[0]
        yf: csc_matrix = admittances[1]
        yt: csc_matrix = admittances[2]
        mask: BoolVec = admittances[4]
        full_lookup: IntVec = admittances[5]
        phases: np.ndarray = lookup[4 * np.arange(nc.nbus)[:, None] + np.arange(1, 4)]
        blocked: BoolVec = ~np.all(np.isin(phases, idx_p) & np.isin(phases, idx_q) & (phases >= 0), axis=1)
        # All retained conductors at a bus translate together, including an explicit neutral.
        slots: IntVec = np.flatnonzero(mask)
        shifts: csc_matrix = csc_matrix((np.ones(len(slots)), (np.arange(len(slots)), slots // 4)),
                                        shape=(len(slots), nc.nbus))
        constraints: list[csc_matrix] = list((common_mode_constraints(yf, shifts),
                                              common_mode_constraints(yt, shifts)))
        # Check each shunt separately: opposite admittances must not cancel a real earth path.
        # This also detects static-generator I0 paths directly from their stored ABC admittance.
        devices: LoadData | ShuntData
        k: int
        for devices in (nc.load_data, nc.shunt_data):
            for k in range(devices.nelm):
                bus: int = devices.bus_idx[k]
                local: IntVec = np.flatnonzero(mask[4 * bus:4 * bus + 4])
                block: np.ndarray = devices.Y3_star[4 * k + local, :][:, local]
                ones: csc_matrix = csc_matrix(np.ones((len(local), 1)))
                if common_mode_constraints(csc_matrix(block), ones).nnz:
                    blocked[bus] = True
                else:
                    pass
        # Explicit branch shunts remain references even below the precision of a large series stamp.
        connection: int
        for k in range(nc.nbr):
            if nc.passive_branch_data.G0[k] != 0 or nc.passive_branch_data.B0[k] != 0:
                for bus, connection in ((nc.passive_branch_data.F[k], nc.passive_branch_data.conn_f[k]),
                                        (nc.passive_branch_data.T[k], nc.passive_branch_data.conn_t[k])):
                    if connection not in (WindingType.Delta.idx(), WindingType.FloatingStar.idx()):
                        blocked[bus] = True
                    else:
                        pass
            else:
                pass
        # Delta and floating-star P/I models depend only on voltage differences. A star model
        # is invariant only if its current also returns through the translated explicit neutral.
        values: CxVec
        for k in range(nc.load_data.nelm):
            bus = nc.load_data.bus_idx[k]
            for values in (nc.load_data.S3_star, nc.load_data.I3_star):
                if np.any(values[4 * k + 1:4 * k + 4] != 0):
                    if values[4 * k] == 0 or full_lookup[4 * bus] < 0:
                        blocked[bus] = True
                    else:
                        pass
                else:
                    pass
        # Legacy per-phase generator powers are earth-referenced. U1 sources and induction
        # machines are invariant only when their actual connection blocks I0.
        generators: GeneratorData
        for generators in (nc.generator_data, nc.battery_data):
            for k in range(generators.nelm):
                if generators.active[k]:
                    regular: bool = generators is nc.generator_data and k in positive.regular_idx
                    asynchronous: bool = generators.tpe_int[k] == GeneratorType.Asynchronous.idx()
                    if ((regular and not asynchronous) or generators.conn[k] not in
                            (ShuntConnectionType.Delta.idx(), ShuntConnectionType.FloatingStar.idx())):
                        blocked[generators.bus_idx[k]] = True
                    else:
                        pass
                else:
                    pass
        # A variable grounded shunt remains a reference even when its present B is zero.
        # The connection also protects tiny fixed earth paths in sequence-based stamps.
        for k in range(nc.shunt_data.nelm):
            if (nc.shunt_data.active[k] and nc.shunt_data.conn[k] == ShuntConnectionType.GroundedStar.idx()
                    and (nc.shunt_data.control_mode_int[k] == ShuntControlMode.Continuous.idx()
                         or np.any(nc.shunt_data.Y3_star[4 * k:4 * k + 4] != 0))):
                blocked[nc.shunt_data.bus_idx[k]] = True
            else:
                pass
        # Retain the assembled check too, including any additional compiled passive contribution.
        constraints.append(common_mode_constraints(ybus, shifts))
        constraints.append(diags(blocked.astype(float), format='csc'))
        matrix: csc_matrix = vstack(constraints, format='csc')
        pattern: csc_matrix = abs(matrix)
        count: int
        groups: IntVec
        count, groups = connected_components((pattern.T @ pattern).tocsc(), directed=False)
        references: IntVec = np.empty(nc.nbus, dtype=int)
        used: int = 0
        group: int
        for group in range(count):
            buses: IntVec = np.flatnonzero(groups == group)
            if np.any(blocked[buses]):
                # Conservative: do not constrain partially referenced or unsupported groups.
                pass
            else:
                subset: csc_matrix = matrix[:, buses]
                rows: IntVec = np.unique(subset.indices)
                kernel: np.ndarray = null_space(subset[rows, :].toarray(),
                    rcond=32 * np.finfo(float).eps * max(1, len(rows), len(buses)))
                if kernel.shape[1] == 1:
                    # One complex reference per independent group; never set U0 at every bus.
                    references[used] = buses[np.argmax(abs(kernel[:, 0]))]
                    used += 1
                else:
                    # Ambiguous groups keep their original equations rather than adding a reference.
                    pass
        self.phases: np.ndarray = phases[references[:used]]
        # Explicit lookup also works when the legacy PQ/PV equation order is not sorted.
        p_rows: IntVec = np.full(len(lookup), -1, dtype=int)
        q_rows: IntVec = np.full(len(lookup), -1, dtype=int)
        p_rows[idx_p] = np.arange(len(idx_p))
        q_rows[idx_q] = len(idx_p) + np.arange(len(idx_q))
        self.real_rows: IntVec = p_rows[self.phases[:, 0]]
        self.imag_rows: IntVec = q_rows[self.phases[:, 0]]

    def apply(self, voltage: CxVec, residual: Vec) -> None:
        """Replace one redundant complex KCL equation per group by its voltage reference.

        :param voltage: Current retained NABC voltages.
        :param residual: Existing real current/control equations, updated in place.
        :return: None.
        """
        reference: CxVec = np.mean(voltage[self.phases], axis=1)
        residual[self.real_rows] = reference.real
        residual[self.imag_rows] = reference.imag
