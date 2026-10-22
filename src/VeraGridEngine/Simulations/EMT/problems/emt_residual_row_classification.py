# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Structural affinity classification of the residual rows of an EMT problem.

Rows follow the solver order: one ``d_x - f(x, y)`` row per state equation,
then one row per algebraic equation. The classification is metadata only and
does not modify the problem.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Dict, FrozenSet, List, Set, Tuple

import numpy as np
import numpy.typing as npt

from VeraGridEngine.enumerations import ExpressionAffinity, ResidualRowAffinityCode
from VeraGridEngine.Utils.canonical_json import canonical_json_bytes
from VeraGridEngine.Utils.Symbolic.structural_affinity import StructuralAffinityAnalyzer
from VeraGridEngine.Utils.Symbolic.symbolic import Var

if TYPE_CHECKING:
    from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
else:
    pass


class EmtResidualRowClassification:
    """
    Immutable per-row structural affinity of an EMT residual system.
    """

    __slots__ = (
        "_row_affinities",
        "_state_row_count",
        "_opaque_row_indices",
        "_nonlinear_support_uids",
    )

    def __init__(self,
                 row_affinities: Tuple[ExpressionAffinity, ...],
                 state_row_count: int,
                 opaque_row_indices: Tuple[int, ...],
                 nonlinear_support_uids: FrozenSet[int]) -> None:
        """
        Store the classification of one residual system.

        :param row_affinities: Affinity of every residual row in solver order.
        :param state_row_count: Number of leading state rows.
        :param opaque_row_indices: Rows whose support could not be determined structurally.
        :param nonlinear_support_uids: Union of the unknown supports of the NONLINEAR rows.
        """
        self._row_affinities: Tuple[ExpressionAffinity, ...] = row_affinities
        self._state_row_count: int = state_row_count
        self._opaque_row_indices: Tuple[int, ...] = opaque_row_indices
        self._nonlinear_support_uids: FrozenSet[int] = nonlinear_support_uids

    def _indices_of(self, affinities: Tuple[ExpressionAffinity, ...]) -> Tuple[int, ...]:
        """
        Return the rows whose affinity is one of the given values.

        :param affinities: Accepted affinities.
        :return: Row indices in ascending order.
        """
        indices: List[int] = list()
        for row_index, affinity in enumerate(self._row_affinities):
            if affinity in affinities:
                indices.append(row_index)
            else:
                pass
        return tuple(indices)

    def get_row_affinities(self) -> Tuple[ExpressionAffinity, ...]:
        """
        Return the affinity of every residual row.

        :return: Affinities in solver row order.
        """
        return self._row_affinities

    def get_state_row_count(self) -> int:
        """
        Return the number of leading state rows.

        :return: Number of state equations.
        """
        return self._state_row_count

    def get_affine_row_indices(self) -> Tuple[int, ...]:
        """
        Return the rows classified exactly AFFINE.

        :return: Row indices in ascending order.
        """
        return self._indices_of((ExpressionAffinity.AFFINE,))

    def get_nonlinear_row_indices(self) -> Tuple[int, ...]:
        """
        Return the rows classified NONLINEAR.

        :return: Row indices in ascending order.
        """
        return self._indices_of((ExpressionAffinity.NONLINEAR,))

    def get_unknown_free_row_indices(self) -> Tuple[int, ...]:
        """
        Return the rows classified CONSTANT or EXCITATION.

        :return: Row indices in ascending order.
        """
        return self._indices_of((ExpressionAffinity.CONSTANT, ExpressionAffinity.EXCITATION))

    def get_opaque_row_indices(self) -> Tuple[int, ...]:
        """
        Return the rows containing nodes outside the supported operator set.

        :return: Row indices in ascending order.
        """
        return self._opaque_row_indices

    def get_nonlinear_support_uids(self) -> FrozenSet[int]:
        """
        Return the unknowns referenced by the NONLINEAR rows (the set N).

        :return: Unknown uids, derivative placeholders mapped to their origin.
        """
        return self._nonlinear_support_uids


def classify_emt_residual_rows(problem: EmtProblemTemplate) -> EmtResidualRowClassification:
    """
    Classify every residual row of an EMT problem by structural affinity.

    Unknowns are the state and algebraic variables; derivative placeholders are
    never unknowns. Constant parameters and the step size ``h`` are epoch
    constants; runtime parameters and time are excitations. A state row
    ``d_x - f`` is classified analytically without constructing variables.

    :param problem: EMT problem to classify.
    :return: Classification in solver row order.
    """
    state_vars: List[Var] = problem.get_state_vars()
    state_eqs: List[object] = problem.get_state_eqs()
    algebraic_eqs: List[object] = problem.get_algebraic_eqs()

    unknown_uids: Set[int] = set()
    for var in state_vars:
        unknown_uids.add(var.uid)
    for var in problem.get_algebraic_vars():
        unknown_uids.add(var.uid)

    epoch_constant_uids: Set[int] = set()
    for var in problem.get_constant_parameters():
        epoch_constant_uids.add(var.uid)

    excitation_uids: Set[int] = {problem.glob_time.uid}
    for var in problem.get_variable_parameters():
        excitation_uids.add(var.uid)

    analyzer: StructuralAffinityAnalyzer = StructuralAffinityAnalyzer(
        unknown_uids=unknown_uids,
        epoch_constant_uids=epoch_constant_uids,
        excitation_uids=excitation_uids,
        excitation_names={"time", problem.TIME_NAME},
        epoch_constant_names={"h"},
    )

    affinities: List[ExpressionAffinity] = list()
    opaque_rows: List[int] = list()
    nonlinear_support: Set[int] = set()

    for row_index, state_eq in enumerate(state_eqs):
        # The derivative term is discretised through the root of the state's base_var chain.
        origin: Var = state_vars[row_index]
        while origin.base_var is not None:
            origin = origin.base_var

        rhs_affinity: ExpressionAffinity = analyzer.classify(state_eq)
        support: Set[int] = set(analyzer.get_unknown_support(state_eq))
        if origin.uid in unknown_uids and rhs_affinity != ExpressionAffinity.NONLINEAR:
            affinity: ExpressionAffinity = ExpressionAffinity.AFFINE
            support.add(origin.uid)
        elif origin.uid in unknown_uids:
            affinity = ExpressionAffinity.NONLINEAR
            support.add(origin.uid)
        else:
            affinity = ExpressionAffinity.NONLINEAR

        affinities.append(affinity)
        if analyzer.is_opaque(state_eq):
            opaque_rows.append(row_index)
        else:
            pass
        if affinity == ExpressionAffinity.NONLINEAR:
            nonlinear_support.update(support)
        else:
            pass

    for algebraic_index, algebraic_eq in enumerate(algebraic_eqs):
        row_index = len(state_eqs) + algebraic_index
        affinity = analyzer.classify(algebraic_eq)
        affinities.append(affinity)
        if analyzer.is_opaque(algebraic_eq):
            opaque_rows.append(row_index)
        else:
            pass
        if affinity == ExpressionAffinity.NONLINEAR:
            nonlinear_support.update(analyzer.get_unknown_support(algebraic_eq))
        else:
            pass

    return EmtResidualRowClassification(
        row_affinities=tuple(affinities),
        state_row_count=len(state_eqs),
        opaque_row_indices=tuple(opaque_rows),
        nonlinear_support_uids=frozenset(nonlinear_support),
    )


def _validated_int32_array(values: object, name: str) -> npt.NDArray[np.int32]:
    """
    Validate an integer index array and return an immutable native int32 copy.

    :param values: One-dimensional numpy array of integer (not bool) dtype.
    :param name: Array name used in error messages.
    :return: C-contiguous int32 array backed by immutable bytes.
    :raises ValueError: When the array is not a one-dimensional integer array
        or holds values outside the int32 range.
    """
    if not isinstance(values, np.ndarray):
        raise ValueError(name + " must be a numpy array")
    elif values.ndim != 1:
        raise ValueError(name + " must be one-dimensional")
    elif values.dtype == np.bool_ or not np.issubdtype(values.dtype, np.integer):
        raise ValueError(name + " must have an integer dtype")
    else:
        pass

    int32_info: np.iinfo = np.iinfo(np.int32)
    if values.size > 0 and (int(values.min()) < int(int32_info.min) or int(values.max()) > int(int32_info.max)):
        raise ValueError(name + " holds values outside the int32 range")
    else:
        pass

    # Backing the array with immutable bytes makes writeable impossible to re-enable.
    native: npt.NDArray[np.int32] = np.ascontiguousarray(values, dtype=np.int32)
    return np.frombuffer(native.tobytes(), dtype=np.int32)


def _is_strictly_ascending_within(values: npt.NDArray[np.int32], upper_bound: int) -> bool:
    """
    Tell whether an index array is strictly ascending within [0, upper_bound).

    :param values: Index array.
    :param upper_bound: Exclusive upper bound.
    :return: True when every value is in range and the array is strictly ascending.
    """
    if values.size == 0:
        return True
    else:
        in_range: bool = int(values[0]) >= 0 and int(values[-1]) < upper_bound
        return in_range and bool(np.all(np.diff(values) > 0))


class EmtResidualRowMap:
    """
    Immutable residual row map of an EMT problem for external solvers.

    Arrays are native int32, C-contiguous and read-only, keyed by VeraGrid
    solver row index, and fingerprinted with the SHA-256 digest of their
    canonical JSON together with the model identity.

    Rows and columns follow VeraGrid solver order: state rows (d_x - f) then
    algebraic rows; state unknowns then algebraic unknowns. Codes: CONSTANT=0,
    EXCITATION=1, AFFINE=2, NONLINEAR=3. The Jacobian rows of AFFINE rows are
    invariant while constant parameters, the step size h and the integration
    method are unchanged; runtime parameters and time change only residual
    values, never the Jacobian of AFFINE rows. Opaque rows are coded NONLINEAR
    and their support is every unknown. Binding to the consumer program is
    through model_identity, which the consumer must check.
    """

    __slots__ = (
        "_model_identity",
        "_n_rows",
        "_n_columns",
        "_state_row_count",
        "_row_affinity",
        "_opaque_rows",
        "_nonlinear_support_columns",
        "_layout_fingerprint",
    )

    def __init__(self,
                 model_identity: str,
                 n_rows: int,
                 n_columns: int,
                 state_row_count: int,
                 row_affinity: npt.NDArray[np.integer],
                 opaque_rows: npt.NDArray[np.integer],
                 nonlinear_support_columns: npt.NDArray[np.integer]) -> None:
        """
        Validate and store one residual row map.

        :param model_identity: Identity of the consumer model, 1..256 printable ASCII characters.
        :param n_rows: Number of residual rows.
        :param n_columns: Number of unknowns; must equal n_rows.
        :param state_row_count: Number of leading state rows (and state columns).
        :param row_affinity: ResidualRowAffinityCode of every row in solver order.
        :param opaque_rows: Strictly ascending opaque row indices, all coded NONLINEAR.
        :param nonlinear_support_columns: Strictly ascending unknown columns of the NONLINEAR rows.
        :raises ValueError: When any structural invariant does not hold.
        """
        # Model identity: 1..256 characters in 0x20..0x7E.
        if type(model_identity) is not str or len(model_identity) < 1 or len(model_identity) > 256:
            raise ValueError("model_identity must be a str of 1..256 characters")
        else:
            pass
        character: str
        for character in model_identity:
            if ord(character) < 0x20 or ord(character) > 0x7E:
                raise ValueError("model_identity must contain only printable ASCII characters")
            else:
                pass

        # Scalars: exact int, square system, state rows inside the system.
        if type(n_rows) is not int or type(n_columns) is not int or type(state_row_count) is not int:
            raise ValueError("n_rows, n_columns and state_row_count must be int")
        elif n_rows < 0:
            raise ValueError("n_rows must be non-negative")
        elif n_columns != n_rows:
            raise ValueError("n_columns must equal n_rows for a square EMT residual system")
        elif state_row_count < 0 or state_row_count > n_rows:
            raise ValueError("state_row_count must lie within [0, n_rows]")
        else:
            pass

        # Arrays: one-dimensional int32 values, then their own invariants.
        affinity: npt.NDArray[np.int32] = _validated_int32_array(row_affinity, "row_affinity")
        opaque: npt.NDArray[np.int32] = _validated_int32_array(opaque_rows, "opaque_rows")
        support: npt.NDArray[np.int32] = _validated_int32_array(nonlinear_support_columns, "nonlinear_support_columns")
        lowest_code: int = int(ResidualRowAffinityCode.CONSTANT)
        highest_code: int = int(ResidualRowAffinityCode.NONLINEAR)
        if affinity.shape[0] != n_rows:
            raise ValueError("row_affinity must have n_rows entries")
        elif affinity.size > 0 and (int(affinity.min()) < lowest_code or int(affinity.max()) > highest_code):
            raise ValueError("row_affinity holds codes outside ResidualRowAffinityCode")
        elif not _is_strictly_ascending_within(opaque, n_rows):
            raise ValueError("opaque_rows must be strictly ascending within [0, n_rows)")
        elif opaque.size > 0 and not bool(np.all(affinity[opaque] == highest_code)):
            raise ValueError("opaque rows must be coded NONLINEAR")
        elif not _is_strictly_ascending_within(support, n_columns):
            raise ValueError("nonlinear_support_columns must be strictly ascending within [0, n_columns)")
        else:
            pass

        self._model_identity: str = model_identity
        self._n_rows: int = n_rows
        self._n_columns: int = n_columns
        self._state_row_count: int = state_row_count
        self._row_affinity: npt.NDArray[np.int32] = affinity
        self._opaque_rows: npt.NDArray[np.int32] = opaque
        self._nonlinear_support_columns: npt.NDArray[np.int32] = support

        # Fingerprint of the layout bound to the model identity.
        payload: Dict[str, object] = dict()
        payload["schema"] = self.get_schema()
        payload["model_identity"] = model_identity
        payload["n_rows"] = n_rows
        payload["n_columns"] = n_columns
        payload["state_row_count"] = state_row_count
        payload["row_affinity"] = affinity.tolist()
        payload["opaque_rows"] = opaque.tolist()
        payload["nonlinear_support_columns"] = support.tolist()
        self._layout_fingerprint: str = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()

    def get_schema(self) -> str:
        """
        Return the interchange schema name.

        :return: Schema name.
        """
        return "veragrid-emt-residual-row-map-v1"

    def get_semantics(self) -> str:
        """
        Return the normative semantic note of the map.

        :return: Semantic note, also carried by the class docstring and the manifest.
        """
        return ("Rows and columns follow VeraGrid solver order: state rows (d_x - f) then algebraic rows; state unknowns then algebraic unknowns. "
                "Codes: CONSTANT=0, EXCITATION=1, AFFINE=2, NONLINEAR=3. The Jacobian rows of AFFINE rows are invariant while constant parameters, "
                "the step size h and the integration method are unchanged; runtime parameters and time change only residual values, never the "
                "Jacobian of AFFINE rows. Opaque rows are coded NONLINEAR and their support is every unknown. Binding to the consumer program is "
                "through model_identity, which the consumer must check.")

    def get_model_identity(self) -> str:
        """
        Return the identity of the consumer model.

        :return: Model identity.
        """
        return self._model_identity

    def get_n_rows(self) -> int:
        """
        Return the number of residual rows.

        :return: Number of rows.
        """
        return self._n_rows

    def get_n_columns(self) -> int:
        """
        Return the number of unknowns.

        :return: Number of columns.
        """
        return self._n_columns

    def get_state_row_count(self) -> int:
        """
        Return the number of leading state rows, also the number of state columns.

        :return: Number of state rows.
        """
        return self._state_row_count

    def get_row_affinity(self) -> npt.NDArray[np.int32]:
        """
        Return the affinity code of every row.

        :return: Read-only int32 array of ResidualRowAffinityCode values in solver row order.
        """
        return self._row_affinity

    def get_opaque_rows(self) -> npt.NDArray[np.int32]:
        """
        Return the opaque rows.

        :return: Read-only strictly ascending int32 row indices.
        """
        return self._opaque_rows

    def get_nonlinear_support_columns(self) -> npt.NDArray[np.int32]:
        """
        Return the unknown columns referenced by the NONLINEAR rows.

        :return: Read-only strictly ascending int32 column indices.
        """
        return self._nonlinear_support_columns

    def get_layout_fingerprint(self) -> str:
        """
        Return the SHA-256 fingerprint of the layout and model identity.

        :return: Hex digest.
        """
        return self._layout_fingerprint


def build_emt_residual_row_map(problem: EmtProblemTemplate, model_identity: str) -> EmtResidualRowMap:
    """
    Build the residual row map of an EMT problem in one call.

    :param problem: EMT problem to export.
    :param model_identity: Identity of the consumer model (for example its program hash).
    :return: Immutable residual row map.
    :raises ValueError: When the state or algebraic blocks are not square, the
        unknown index does not match the variables, or the map violates its invariants.
    """
    # Block alignment, so state_row_count is also the state-column boundary.
    state_var_count: int = len(problem.get_state_vars())
    algebraic_var_count: int = len(problem.get_algebraic_vars())
    state_row_count: int = len(problem.get_state_eqs())
    algebraic_row_count: int = len(problem.get_algebraic_eqs())
    uid2idx: Dict[int, int] = problem.uid2idx_vars
    if state_var_count != state_row_count:
        raise ValueError("The number of state variables differs from the number of state equations")
    elif algebraic_var_count != algebraic_row_count:
        raise ValueError("The number of algebraic variables differs from the number of algebraic equations")
    elif len(uid2idx) != state_var_count + algebraic_var_count:
        raise ValueError("The unknown index does not match the state and algebraic variables")
    else:
        pass

    # Classification once, then integer codes keyed by solver row.
    classification: EmtResidualRowClassification = classify_emt_residual_rows(problem)
    code_of: Dict[ExpressionAffinity, int] = dict()
    code_of[ExpressionAffinity.CONSTANT] = int(ResidualRowAffinityCode.CONSTANT)
    code_of[ExpressionAffinity.EXCITATION] = int(ResidualRowAffinityCode.EXCITATION)
    code_of[ExpressionAffinity.AFFINE] = int(ResidualRowAffinityCode.AFFINE)
    code_of[ExpressionAffinity.NONLINEAR] = int(ResidualRowAffinityCode.NONLINEAR)

    affinities: Tuple[ExpressionAffinity, ...] = classification.get_row_affinities()
    row_affinity: npt.NDArray[np.int32] = np.empty(len(affinities), dtype=np.int32)
    row_index: int
    affinity: ExpressionAffinity
    for row_index, affinity in enumerate(affinities):
        row_affinity[row_index] = code_of[affinity]
    opaque_rows: npt.NDArray[np.int32] = np.array(classification.get_opaque_row_indices(), dtype=np.int32)
    row_affinity[opaque_rows] = int(ResidualRowAffinityCode.NONLINEAR)

    # Nonlinear support uids mapped to unknown columns.
    columns: List[int] = list()
    uid: int
    for uid in classification.get_nonlinear_support_uids():
        columns.append(uid2idx[uid])
    columns.sort()

    return EmtResidualRowMap(
        model_identity=model_identity,
        n_rows=len(affinities),
        n_columns=len(uid2idx),
        state_row_count=classification.get_state_row_count(),
        row_affinity=row_affinity,
        opaque_rows=opaque_rows,
        nonlinear_support_columns=np.array(columns, dtype=np.int32),
    )
