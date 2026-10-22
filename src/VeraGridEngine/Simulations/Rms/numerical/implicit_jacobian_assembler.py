# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Fixed-pattern assembly of the implicit Backward Euler Jacobian.

The Backward Euler Newton matrix of an RMS DAE is::

    | I - h*J11   -h*J12 |
    | J21          J22   |

The compiled block Jacobians reuse fixed CSC templates, so the packed pattern of
this matrix does not change between Newton corrections. The assembler builds that
pattern and the scatter maps once and afterwards only rewrites the values, using
the same floating-point operations as the SciPy expression it replaces. Whenever
reusing the pattern could produce a different matrix (non-canonical or malformed
blocks, other formats, or an exactly zero value in the I - h*J11 block, which the
SciPy subtraction would drop), the SciPy expression itself is evaluated instead.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse import csc_matrix, spmatrix

from VeraGridEngine.Utils.Sparse.csc import pack_4_by_4_scipy


def _csc_storage_is_consistent(indptr: np.ndarray, indices: np.ndarray, data: np.ndarray, shape: tuple[int, int]) -> bool:
    """
    Check that CSC arrays describe exactly nnz stored entries of the given shape.

    :param indptr: Column pointer array.
    :param indices: Row index array.
    :param data: Value array.
    :param shape: Matrix shape (rows, columns).
    :return: True when len(indptr) == columns + 1, indptr[0] == 0 and data and indices hold indptr[-1] entries.
    """
    consistent: bool = int(indptr.shape[0]) == int(shape[1]) + 1
    if consistent:
        consistent = int(indptr[0]) == 0 and int(data.shape[0]) == int(indices.shape[0]) == int(indptr[-1])
    else:
        pass
    return consistent


def _csc_pattern_is_canonical(indptr: np.ndarray, indices: np.ndarray, n_rows: int) -> bool:
    """
    Check from the arrays that a CSC pattern is canonical and in range.

    SciPy's cached has_canonical_format flag is not used because it does not follow
    in-place rewrites of the index arrays.

    :param indptr: Column pointer array (storage already checked as consistent).
    :param indices: Row index array.
    :param n_rows: Number of rows.
    :return: True when indptr is non-decreasing, every row index is within [0, n_rows)
        and row indices strictly increase inside every column.
    """
    canonical: bool = bool(np.all(np.diff(indptr) >= 0))
    nnz: int = int(indptr[-1])
    if canonical and nnz > 0:
        canonical = int(indices.min()) >= 0 and int(indices.max()) < n_rows
    else:
        pass
    if canonical and nnz > 1:
        # A non-increasing step between consecutive entries is only allowed where a new column starts.
        column_start: np.ndarray = np.zeros(nnz - 1, dtype=bool)
        starts: np.ndarray = indptr[1:-1]
        inner_starts: np.ndarray = starts[(starts > 0) & (starts < nnz)]
        column_start[inner_starts - 1] = True
        canonical = bool(np.all((np.diff(indices) > 0) | column_start))
    else:
        pass
    return canonical


class ImplicitJacobianAssembler:
    """
    Assembler of the Backward Euler implicit Jacobian on a reusable packed CSC pattern.

    The block index arrays seen at a pattern build are stored as copies and compared
    element-wise on every call, so an in-place rewrite of a block pattern triggers a
    rebuild instead of reusing stale scatter maps.
    """

    __slots__ = (
        "_has_pattern",
        "_block_shapes",
        "_block_indices",
        "_block_indptr",
        "_shape",
        "_indices",
        "_indptr",
        "_map_j11",
        "_map_j12",
        "_map_j21",
        "_map_j22",
        "_region",
        "_base",
        "_values",
        "_pattern_builds",
        "_fast_assemblies",
        "_fallback_assemblies",
    )

    def __init__(self) -> None:
        """
        Create an assembler without a pattern; the first eligible call builds it.
        """
        self._has_pattern: bool = False
        self._block_shapes: list[tuple[int, int]] = list()
        self._block_indices: list[np.ndarray] = list()
        self._block_indptr: list[np.ndarray] = list()
        self._shape: tuple[int, int] = (0, 0)
        self._indices: np.ndarray = np.zeros(0, dtype=np.int32)
        self._indptr: np.ndarray = np.zeros(1, dtype=np.int32)
        self._map_j11: np.ndarray = np.zeros(0, dtype=np.int64)
        self._map_j12: np.ndarray = np.zeros(0, dtype=np.int64)
        self._map_j21: np.ndarray = np.zeros(0, dtype=np.int64)
        self._map_j22: np.ndarray = np.zeros(0, dtype=np.int64)
        self._region: np.ndarray = np.zeros(0, dtype=np.int64)
        self._base: np.ndarray = np.zeros(0, dtype=np.float64)
        self._values: np.ndarray = np.zeros(0, dtype=np.float64)
        self._pattern_builds: int = 0
        self._fast_assemblies: int = 0
        self._fallback_assemblies: int = 0

    def get_pattern_build_count(self) -> int:
        """
        Return how many times the packed pattern and scatter maps were built.

        :return: Number of pattern builds.
        """
        return self._pattern_builds

    def get_fast_assembly_count(self) -> int:
        """
        Return how many matrices were assembled on the reusable pattern.

        :return: Number of fast assemblies.
        """
        return self._fast_assemblies

    def get_fallback_assembly_count(self) -> int:
        """
        Return how many matrices were assembled with the SciPy expression.

        :return: Number of fallback assemblies.
        """
        return self._fallback_assemblies

    def assemble(self, ns: int, h: float, j11: spmatrix, j12: spmatrix, j21: spmatrix, j22: spmatrix) -> csc_matrix:
        """
        Assemble [[I - h*J11, -h*J12], [J21, J22]].

        The result is identical to pack_4_by_4_scipy((sp.eye(ns) - h*J11).tocsc(), -h*J12, J21, J22):
        same canonical pattern, int32 index arrays and the same bits in every value.

        :param ns: Number of states, which is the size of the square J11 block.
        :param h: Integration step.
        :param j11: State-equation Jacobian with respect to the states.
        :param j12: State-equation Jacobian with respect to the algebraic variables.
        :param j21: Algebraic-equation Jacobian with respect to the states.
        :param j22: Algebraic-equation Jacobian with respect to the algebraic variables.
        :return: New CSC matrix owning its data, indices and indptr.
        """
        result: csc_matrix
        if self._blocks_are_eligible(ns, j11, j12, j21, j22):
            # Reuse the stored pattern when every block still has it; otherwise verify the
            # blocks from their arrays and build a new pattern for them.
            pattern_ready: bool = self._pattern_matches(j11, j12, j21, j22)
            if pattern_ready:
                pass
            else:
                pattern_ready = self._build_pattern(ns, j11, j12, j21, j22)
            if pattern_ready:
                result = self._assemble_on_pattern(ns, h, j11, j12, j21, j22)
            else:
                result = self._assemble_with_scipy(ns, h, j11, j12, j21, j22)
        else:
            result = self._assemble_with_scipy(ns, h, j11, j12, j21, j22)
        return result

    def _blocks_are_eligible(self, ns: int, j11: spmatrix, j12: spmatrix, j21: spmatrix, j22: spmatrix) -> bool:
        """
        Check the formats, value types, shapes and storage consistency required by the fast path.

        :param ns: Number of states.
        :param j11: State/state block.
        :param j12: State/algebraic block.
        :param j21: Algebraic/state block.
        :param j22: Algebraic/algebraic block.
        :return: True when the four blocks can be read as CSC arrays of the expected shapes.
        """
        eligible: bool = ns >= 1
        block: spmatrix
        for block in (j11, j12, j21, j22):
            if eligible and sp.isspmatrix_csc(block) and block.dtype == np.float64:
                eligible = _csc_storage_is_consistent(block.indptr, block.indices, block.data, block.shape)
            else:
                eligible = False
        if eligible:
            # The blocks must tile the packed matrix exactly, as pack_4_by_4_scipy requires.
            eligible = (j11.shape == (ns, ns) and j12.shape[0] == ns and j21.shape[1] == ns
                        and j22.shape == (j21.shape[0], j12.shape[1]))
        else:
            pass
        return eligible

    def _pattern_matches(self, j11: csc_matrix, j12: csc_matrix, j21: csc_matrix, j22: csc_matrix) -> bool:
        """
        Compare the current block patterns element-wise with the verified stored copies.

        :param j11: State/state block.
        :param j12: State/algebraic block.
        :param j21: Algebraic/state block.
        :param j22: Algebraic/algebraic block.
        :return: True when a pattern exists and every block shape, indices and indptr are unchanged.
        """
        matches: bool = self._has_pattern
        position: int
        block: csc_matrix
        for position, block in enumerate((j11, j12, j21, j22)):
            if matches:
                matches = (block.shape == self._block_shapes[position]
                           and np.array_equal(block.indptr, self._block_indptr[position])
                           and np.array_equal(block.indices, self._block_indices[position]))
            else:
                pass
        return matches

    def _build_pattern(self, ns: int, j11: csc_matrix, j12: csc_matrix, j21: csc_matrix, j22: csc_matrix) -> bool:
        """
        Build the packed canonical pattern and the scatter maps of the four blocks.

        :param ns: Number of states.
        :param j11: State/state block.
        :param j12: State/algebraic block.
        :param j21: Algebraic/state block.
        :param j22: Algebraic/algebraic block.
        :return: True when the blocks are canonical and the pattern was built; False to use the SciPy expression.
        """
        blocks: tuple[csc_matrix, csc_matrix, csc_matrix, csc_matrix] = (j11, j12, j21, j22)
        canonical: bool = True
        block: csc_matrix
        for block in blocks:
            if canonical:
                canonical = _csc_pattern_is_canonical(block.indptr, block.indices, int(block.shape[0]))
            else:
                pass
        built: bool
        if canonical:
            n_rows: int = ns + int(j21.shape[0])
            n_cols: int = ns + int(j12.shape[1])

            # Global (row, column) coordinates of every stored block entry plus the identity diagonal,
            # encoded as column-major keys so that sorted unique keys give the canonical CSC order.
            row_offsets: tuple[int, int, int, int] = (0, 0, ns, ns)
            col_offsets: tuple[int, int, int, int] = (0, ns, 0, ns)
            key_parts: list[np.ndarray] = list()
            position: int
            for position, block in enumerate(blocks):
                columns: np.ndarray = np.repeat(np.arange(int(block.shape[1]), dtype=np.int64), np.diff(block.indptr))
                rows: np.ndarray = block.indices.astype(np.int64)
                key_parts.append((columns + col_offsets[position]) * n_rows + (rows + row_offsets[position]))
            diagonal: np.ndarray = np.arange(ns, dtype=np.int64)
            key_parts.append(diagonal * n_rows + diagonal)
            keys: np.ndarray = np.unique(np.concatenate(key_parts))

            # Canonical packed pattern with the int32 index arrays produced by pack_4_by_4_scipy.
            self._indices = (keys % n_rows).astype(np.int32)
            self._indptr = np.zeros(n_cols + 1, dtype=np.int32)
            self._indptr[1:] = np.cumsum(np.bincount(keys // n_rows, minlength=n_cols)).astype(np.int32)
            self._shape = (n_rows, n_cols)

            # Position of each block entry in the packed value array.
            self._map_j11 = np.searchsorted(keys, key_parts[0])
            self._map_j12 = np.searchsorted(keys, key_parts[1])
            self._map_j21 = np.searchsorted(keys, key_parts[2])
            self._map_j22 = np.searchsorted(keys, key_parts[3])
            diagonal_positions: np.ndarray = np.searchsorted(keys, key_parts[4])

            # The I - h*J11 block: 1.0 on the diagonal and 0.0 elsewhere before subtracting h*J11,
            # exactly the operands of the SciPy subtraction.
            self._region = np.union1d(self._map_j11, diagonal_positions)
            self._base = np.zeros(keys.shape[0], dtype=np.float64)
            self._base[diagonal_positions] = 1.0
            self._values = np.zeros(keys.shape[0], dtype=np.float64)

            # Verified copies of the block patterns for the element-wise reuse check.
            self._block_shapes = [(int(b.shape[0]), int(b.shape[1])) for b in blocks]
            self._block_indices = [b.indices.copy() for b in blocks]
            self._block_indptr = [b.indptr.copy() for b in blocks]
            self._has_pattern = True
            self._pattern_builds += 1
            built = True
        else:
            built = False
        return built

    def _assemble_on_pattern(self, ns: int, h: float, j11: csc_matrix, j12: csc_matrix,
                             j21: csc_matrix, j22: csc_matrix) -> csc_matrix:
        """
        Write the values on the stored pattern, or use the SciPy expression if it would drop a zero.

        :param ns: Number of states.
        :param h: Integration step.
        :param j11: State/state block.
        :param j12: State/algebraic block.
        :param j21: Algebraic/state block.
        :param j22: Algebraic/algebraic block.
        :return: Assembled matrix.
        """
        values: np.ndarray = self._values

        # I - h*J11 with SciPy's operations: 1.0 - h*a on the diagonal, 0.0 - h*a elsewhere,
        # and 1.0 on diagonal positions without a J11 entry.
        values[self._region] = self._base[self._region]
        values[self._map_j11] = self._base[self._map_j11] - h * j11.data

        # -h*J12 is evaluated as (-h)*J12 by the expression it replaces; J21 and J22 are copied.
        values[self._map_j12] = (-h) * j12.data
        values[self._map_j21] = j21.data
        values[self._map_j22] = j22.data

        result: csc_matrix
        if bool(np.any(values[self._region] == 0.0)):
            # SciPy would drop this exact zero from the I - h*J11 block, changing the pattern.
            result = self._assemble_with_scipy(ns, h, j11, j12, j21, j22)
        else:
            result = csc_matrix((values.copy(), self._indices.copy(), self._indptr.copy()), shape=self._shape)
            self._fast_assemblies += 1
        return result

    def _assemble_with_scipy(self, ns: int, h: float, j11: spmatrix, j12: spmatrix,
                             j21: spmatrix, j22: spmatrix) -> csc_matrix:
        """
        Evaluate the original SciPy expression unchanged.

        :param ns: Number of states.
        :param h: Integration step.
        :param j11: State/state block.
        :param j12: State/algebraic block.
        :param j21: Algebraic/state block.
        :param j22: Algebraic/algebraic block.
        :return: Assembled matrix, or the exception the expression raises.
        """
        self._fallback_assemblies += 1
        identity: sp.dia_matrix = sp.eye(m=ns, n=ns)
        return pack_4_by_4_scipy((identity - h * j11).tocsc(), - h * j12, j21, j22)
