# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import math

from typing import Dict, Iterable, List, Optional, Protocol, Tuple

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory, find_var_by_persisted_identity
from VeraGridEngine.Utils.emt_boundary_update_wrapper import BoundaryUpdateWrapper
from VeraGridEngine.Utils.procedural_logic_contract import (
    ProceduralLogicCodecContract,
    ProceduralLogicData,
    ProceduralLogicEntryContract,
    ManufacturerNativeRuntimeSessionProtocol,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp, Comparison, Const, Expr, Var
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import ProceduralLogicType

VarRemap = Dict[Expr | str, Expr]


def _read_procedural_expression_record(
        data: ProceduralLogicData,
        field_name: str,
) -> ProceduralLogicData:
    """Read one required declarative symbolic-expression record.

    Field names are normalized into an independent typed mapping so arbitrary
    imported keys cannot cross the procedural reconstruction boundary.

    :param data: Declarative procedural-logic entry.
    :param field_name: Required field containing one symbolic record.
    :return: Validated symbolic record with string field names.
    """
    raw_record: object = data.get(field_name, None)
    if isinstance(raw_record, dict):
        record: ProceduralLogicData = dict()
        raw_key: object
        raw_value: object
        for raw_key, raw_value in raw_record.items():
            if isinstance(raw_key, str):
                record[raw_key] = raw_value
            else:
                raise TypeError(
                    f"Procedural field '{field_name}' must use string keys"
                )
        else:
            pass
        return record
    else:
        raise TypeError(
            f"Procedural field '{field_name}' must be a declarative mapping"
        )


def _read_finite_procedural_float(
        data: ProceduralLogicData,
        field_name: str,
) -> float:
    """Read one required finite numeric procedural declaration.

    :param data: Declarative procedural-logic entry.
    :param field_name: Required numeric field.
    :return: Finite floating-point value.
    """
    raw_value: object = data.get(field_name, None)
    if isinstance(raw_value, (float, int)) and not isinstance(raw_value, bool):
        numeric_value: float = float(raw_value)
        if math.isfinite(numeric_value):
            return numeric_value
        else:
            raise ValueError(
                f"Procedural field '{field_name}' must be finite"
            )
    else:
        raise TypeError(
            f"Procedural field '{field_name}' must be numeric"
        )


def _read_procedural_integer(
        data: ProceduralLogicData,
        field_name: str,
) -> int:
    """Read one required integer procedural declaration.

    :param data: Declarative procedural-logic entry.
    :param field_name: Required integer field.
    :return: Exact integer value.
    """
    raw_value: object = data.get(field_name, None)
    if isinstance(raw_value, int) and not isinstance(raw_value, bool):
        return raw_value
    else:
        raise TypeError(
            f"Procedural field '{field_name}' must be an integer"
        )


class ProceduralProblem(Protocol):
    """Declare the EMT surface required by procedural runtime logic."""

    __slots__ = ()

    @property
    def uid2idx_vars(self) -> Dict[int, int]:
        """Return compiled state-variable indexes keyed by symbolic UID.

        :return: State-vector indexes keyed by stable symbolic UID.
        """
        ...

    @property
    def uid2idx_event_params(self) -> Dict[int, int]:
        """Return mutable runtime-parameter indexes keyed by symbolic UID.

        :return: Runtime-parameter indexes keyed by stable symbolic UID.
        """
        ...

    @property
    def uid2idx_params(self) -> Dict[int, int]:
        """Return constant-parameter indexes keyed by symbolic UID.

        :return: Constant-parameter indexes keyed by stable symbolic UID.
        """
        ...

    @property
    def event_params_values(self) -> Vec:
        """Return the current mutable runtime-parameter vector.

        :return: Runtime values updated by procedural boundary logic.
        """
        ...

    @property
    def glob_time(self) -> Var:
        """Return the symbolic variable representing global solver time.

        :return: Canonical symbolic solver-time variable.
        """
        ...

    @property
    def sys_block(self) -> Block:
        """Return the canonical root block compiled by the runtime problem.

        :return: Root block owning all attached procedural declarations.
        """
        ...

    def get_parameters_values(self) -> List[Const]:
        """Return constant parameter values in compiled order."""
        ...

    def get_variable_parameter_number(self) -> int:
        """Return the number of mutable runtime parameters."""
        ...

    def get_x0(self) -> Vec:
        """Return the current initialization vector."""
        ...

    def get_var_idx(self, variable: Var) -> int:
        """Return the compiled index for one symbolic variable.

        :param variable: Symbolic variable whose solver-vector index is needed.
        :return: Zero-based index in the compiled solver vector.
        """
        ...


def _expr_like_to_dict(expr: Expr | Comparison | float | int | bool) -> ProceduralLogicData:
    """
    Serialize a symbolic expression or comparison used by procedural logic.

    :param expr: Procedural expression to serialize.
    :return: Dictionary with enough information to rebuild the expression later.
    """
    if isinstance(expr, Comparison):
        rhs: Expr | float | int = expr.rhs
        if isinstance(rhs, Expr):
            rhs_expr: Expr = rhs
            rhs_data: object = rhs_expr.to_dict()
        else:
            rhs_data = rhs
        return {
            "kind": "Comparison",
            "lhs": expr.lhs.to_dict(),
            "op": expr.op.value,
            "rhs": rhs_data,
            "rhs_is_expr": isinstance(rhs, Expr),
        }
    if isinstance(expr, Expr):
        return {
            "kind": "Expr",
            "expr": expr.to_dict(),
        }
    return {
        "kind": "Scalar",
        "value": float(expr),
    }


def _expr_like_from_dict(data: ProceduralLogicData) -> Expr | Comparison:
    """
    Deserialize a symbolic expression or comparison used by procedural logic.

    :param data: Serialized expression dictionary.
    :return: Reconstructed symbolic expression or comparison.
    """
    raw_kind: object = data.get("kind", "Expr")
    if isinstance(raw_kind, str):
        kind: str = raw_kind
    else:
        raise TypeError("Procedural expression kind must be a string")
    if kind == "Expr":
        return Expr.from_dict(
            _read_procedural_expression_record(data, "expr")
        )

    if kind == "Scalar":
        return Const(_read_finite_procedural_float(data, "value"))

    if kind == "Comparison":
        rhs_is_expr_raw: object = data.get("rhs_is_expr", None)
        if isinstance(rhs_is_expr_raw, bool):
            rhs_is_expr: bool = rhs_is_expr_raw
        else:
            raise TypeError("Procedural comparison expression flag must be boolean")
        if rhs_is_expr:
            rhs: Expr | float | int = Expr.from_dict(
                _read_procedural_expression_record(data, "rhs")
            )
        else:
            rhs = _read_finite_procedural_float(data, "rhs")

        op_raw: object = data.get("op", None)
        if isinstance(op_raw, str):
            op_text: str = op_raw
        else:
            raise TypeError("Procedural comparison operator must be a string")

        return Comparison(
            lhs=Expr.from_dict(
                _read_procedural_expression_record(data, "lhs")
            ),
            op=CmpOp(op_text),
            rhs=rhs,
        )

    raise ValueError(f"Unsupported procedural expression kind '{kind}'")


def _subs_expr_like(expr: Expr | Comparison | float | int | bool, mapping: VarRemap) -> Expr | Comparison:
    """
    Apply a variable substitution to a procedural expression.

    :param expr: Expression or comparison to remap.
    :param mapping: Variable substitution map.
    :return: Remapped expression.
    """
    if isinstance(expr, Comparison):
        rhs: Expr | float | int = expr.rhs.subs(mapping) if isinstance(expr.rhs, Expr) else expr.rhs
        return Comparison(lhs=expr.lhs.subs(mapping), op=expr.op, rhs=rhs)
    if isinstance(expr, Expr):
        return expr.subs(mapping)
    return Const(float(expr))


def _build_name_mapping(var_mapping: VarRemap) -> Dict[str, str]:
    """
    Build a name-to-name remapping from a generic variable substitution map.

    :param var_mapping: Mapping used to substitute symbolic variables.
    :return: Mapping from old variable names to new variable names.
    """
    mapping: Dict[str, str] = dict()
    for old, new in var_mapping.items():
        if isinstance(old, Var) and isinstance(new, Var):
            old_var: Var = old
            new_var: Var = new
            mapping[old_var.name] = new_var.name
        elif isinstance(old, str) and isinstance(new, Var):
            new_var = new
            mapping[old] = new_var.name
    return mapping


def _remap_var_uid(var_uid: int | None, var_mapping: VarRemap) -> int | None:
    """Resolve one stored variable UID through a symbolic remapping.

    :param var_uid: Original variable UID or ``None`` for legacy name lookup.
    :param var_mapping: Symbolic variable replacement map.
    :return: Remapped UID or the original value when no mapping applies.
    """
    if var_uid is None:
        return None
    else:
        pass

    source: Expr | str
    replacement: Expr
    for source, replacement in var_mapping.items():
        if isinstance(source, Expr) and source.uid == var_uid:
            return replacement.uid
        else:
            pass

    return var_uid


def _get_expr_like_field(data: ProceduralLogicData, key: str) -> ProceduralLogicData:
    """
    Return one serialized procedural-expression field as a dictionary.

    :param data: Serialized procedural logic dictionary.
    :param key: Field name containing one serialized expression.
    :return: Serialized expression dictionary.
    """
    return _read_procedural_expression_record(data, key)


def _coerce_var_name(var_or_name: Var | str) -> str:
    """
    Normalize a variable reference to its string name.

    :param var_or_name: Symbolic variable or plain string name.
    :return: Variable name.
    """
    if isinstance(var_or_name, Var):
        symbolic_var: Var = var_or_name
        return symbolic_var.name
    else:
        name_text: str = str(var_or_name)
        return name_text


def _append_history_sample(history: List[Tuple[float, float]], sample_time: float, value: float) -> None:
    """
    Append or overwrite one time-stamped sample in a monotonic history buffer.

    :param history: In-place sample buffer.
    :param sample_time: Accepted sample time.
    :param value: Sampled value.
    :return: None.
    """
    if len(history) > 0 and abs(history[-1][0] - sample_time) <= 1e-12:
        history[-1] = (sample_time, value)
    else:
        history.append((sample_time, value))


def _history_sample_at_or_before(history: List[Tuple[float, float]], target_time: float) -> float:
    """
    Return the latest history sample not newer than ``target_time``.

    :param history: Monotonic time-stamped samples.
    :param target_time: Requested delayed lookup time.
    :return: Sampled value.
    """
    if len(history) == 0:
        return 0.0

    selected_value: float = history[0][1]
    for sample_time, sample_value in history:
        if sample_time <= target_time:
            selected_value = sample_value
        else:
            break
    return selected_value


def _prune_history_keep_last_before(history: List[Tuple[float, float]], cutoff_time: float) -> None:
    """
    Drop stale history samples while keeping the last one before ``cutoff_time``.

    :param history: Monotonic time-stamped samples.
    :param cutoff_time: Oldest time worth keeping for future delayed lookups.
    :return: None.
    """
    if len(history) <= 2:
        return

    keep_from: int = 0
    for idx, (sample_time, _sample_value) in enumerate(history):
        if sample_time <= cutoff_time:
            keep_from = idx
        else:
            break

    if keep_from > 0:
        del history[:keep_from]


def _bool_expr(expr: Expr | Comparison | float | int) -> Expr:
    """
    Convert a boolean-like procedural input into a symbolic expression.

    :param expr: Comparison, expression, or scalar encoded as 0/1.
    :return: Symbolic expression representing the boolean quantity.
    """
    if isinstance(expr, Comparison):
        comparison_expr: Comparison = expr
        return comparison_expr.to_expression()
    elif isinstance(expr, Expr):
        symbolic_expr: Expr = expr
        return symbolic_expr
    else:
        scalar_value: float = float(expr)
        return Const(scalar_value)


def _value_expr(expr: Expr | Comparison | float | int) -> Expr:
    """
    Convert a procedural scalar input into a symbolic expression.

    :param expr: Comparison, expression, or scalar value.
    :return: Symbolic expression representing the input value.
    """
    if isinstance(expr, Comparison):
        comparison_expr: Comparison = expr
        return comparison_expr.to_expression()
    elif isinstance(expr, Expr):
        symbolic_expr: Expr = expr
        return symbolic_expr
    else:
        scalar_value: float = float(expr)
        return Const(scalar_value)


def bool_and(*args: Expr | Comparison | float | int) -> Expr:
    """
    Build the boolean AND of one or more procedural expressions.

    :param args: Boolean-like expressions encoded as 0/1 values.
    :return: Expression equal to 1.0 only when all inputs are true.
    """
    if len(args) == 0:
        return Const(1.0)

    result = _bool_expr(args[0])
    for arg in args[1:]:
        result = result * _bool_expr(arg)
    return result


def bool_or(*args: Expr | Comparison | float | int) -> Expr:
    """
    Build the boolean OR of one or more procedural expressions.

    :param args: Boolean-like expressions encoded as 0/1 values.
    :return: Expression equal to 1.0 when at least one input is true.
    """
    if len(args) == 0:
        return Const(0.0)

    result = _bool_expr(args[0])
    for arg in args[1:]:
        arg_expr = _bool_expr(arg)
        result = Const(1.0) - (Const(1.0) - result) * (Const(1.0) - arg_expr)
    return result


def bool_not(arg: Expr | Comparison | float | int) -> Expr:
    """
    Build the boolean NOT of one procedural expression.

    :param arg: Boolean-like expression encoded as 0/1.
    :return: Expression equal to 1.0 when the input is false.
    """
    return Const(1.0) - _bool_expr(arg)


def bool_nand(*args: Expr | Comparison | float | int) -> Expr:
    """
    Build the boolean NAND of one or more procedural expressions.

    :param args: Boolean-like expressions encoded as 0/1 values.
    :return: Expression equal to the negated AND of the inputs.
    """
    return bool_not(bool_and(*args))


def bool_nor(*args: Expr | Comparison | float | int) -> Expr:
    """
    Build the boolean NOR of one or more procedural expressions.

    :param args: Boolean-like expressions encoded as 0/1 values.
    :return: Expression equal to the negated OR of the inputs.
    """
    return bool_not(bool_or(*args))


def bool_eor(left: Expr | Comparison | float | int, right: Expr | Comparison | float | int) -> Expr:
    """
    Build the exclusive-OR of two procedural expressions.

    :param left: Left boolean-like expression.
    :param right: Right boolean-like expression.
    :return: Expression equal to 1.0 only when exactly one input is true.
    """
    left_expr = _bool_expr(left)
    right_expr = _bool_expr(right)
    return left_expr + right_expr - Const(2.0) * left_expr * right_expr


def select(
    boolexpr: Expr | Comparison | float | int,
    when_true: Expr | Comparison | float | int,
    when_false: Expr | Comparison | float | int,
) -> Expr:
    """
    Reject equation-level select usage in the public procedural API.

    :param boolexpr: Switching condition.
    :param when_true: Value chosen for the true branch.
    :param when_false: Value chosen for the false branch.
    :return: Never returns because public equation-level selection is blocked.
    """
    _unused = (boolexpr, when_true, when_false)
    raise RuntimeError(
        "`select()` is blocked in equation expressions. Move the switching decision to "
        "`block.procedural_logic` and consume the resulting mode/flag inside the equations."
    )


def ifelse(
    boolexpr: Expr | Comparison | float | int,
    when_true: Expr | Comparison | float | int,
    when_false: Expr | Comparison | float | int,
) -> Expr:
    """
    Reject equation-level ifelse usage in the public procedural API.

    :param boolexpr: Switching condition.
    :param when_true: Value chosen for the true branch.
    :param when_false: Value chosen for the false branch.
    :return: Never returns because public equation-level selection is blocked.
    """
    _unused = (boolexpr, when_true, when_false)
    raise RuntimeError(
        "`ifelse()` is blocked in equation expressions. Move the switching decision to "
        "`block.procedural_logic` and consume the resulting mode/flag inside the equations."
    )


class ProceduralNumericEvaluator:
    """Evaluate one procedural expression against an accepted solver snapshot.

    :param logic: Bound procedural state machine that owns sample-time rules.
    :param expression: Declarative expression evaluated by the wrapper.
    """

    __slots__ = ("_logic", "_expression")

    def __init__(
            self,
            logic: "ProceduralLogicBase",
            expression: Expr | Comparison | float | int | bool,
    ) -> None:
        """Store one evaluator without creating executable source code.

        :param logic: Bound procedural state machine.
        :param expression: Declarative expression or scalar.
        :return: None.
        """
        self._logic: ProceduralLogicBase = logic
        self._expression: Expr | Comparison | float | int | bool = expression

    def __call__(self, t: float, x: Vec, params: Vec) -> float:
        """Evaluate the stored expression using one accepted runtime snapshot.

        :param t: Solver time supplied to the procedural update.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: Numeric expression value.
        """
        return self._logic.evaluate_numeric_expression(
            expr=self._expression,
            t=t,
            x=x,
            params=params,
        )


class ProceduralLogicBase(ProceduralLogicEntryContract[Expr]):
    """
    Base class for procedural logic objects attached to symbolic blocks.

    Procedural logic is evaluated outside the compiled residual kernels and is intended
    to drive runtime modes, retained flags, timers, or event scheduling in a structured way.
    """

    __slots__ = [
        "name",
        "_problem",
        "_sample_time",
        "_expr_plan_cache",
        "_comparison_expr_cache",
        "_expr_binding_cache",
    ]
    logic_tpe = ProceduralLogicType.Base

    def __init__(self, name: str = "") -> None:
        self.name = name
        self._problem: Optional[ProceduralProblem] = None
        self._sample_time: Optional[float] = None
        self._expr_plan_cache: Dict[int, List[Tuple[int, int, int]]] = dict()
        self._comparison_expr_cache: Dict[int, Expr] = dict()
        self._expr_binding_cache: Dict[int, Dict[int, float]] = dict()

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Bind the logic to a concrete EMT problem.

        :param problem: EMT problem owning the block and variable maps.
        :return: None
        """
        self._problem = problem
        self._sample_time = None
        self._expr_plan_cache = dict()
        self._comparison_expr_cache = dict()
        self._expr_binding_cache = dict()

    def _get_normalized_expr(self, expr: Expr | Comparison) -> Expr:
        if isinstance(expr, Comparison):
            key = id(expr)
            if key in self._comparison_expr_cache:
                return self._comparison_expr_cache[key]

            expr_eval = expr.to_expression()
            self._comparison_expr_cache[key] = expr_eval
            return expr_eval

        return expr

    def _build_expr_plan(self, expr_eval: Expr, problem: ProceduralProblem) -> List[Tuple[int, int, int]]:
        """Resolve every expression variable to its procedural runtime source.

        Time variables deliberately retain separate source kinds because the
        accepted sample clock and the target solver boundary have different
        semantics during an implicit step. All other variables resolve through
        the typed state, runtime-parameter, or constant-parameter mappings.

        :param expr_eval: Normalized symbolic expression to bind.
        :param problem: Procedural runtime mapping provider.
        :return: Unique ``(uid, source kind, source index)`` bindings.
        """
        # Plan tuple layout: (uid, source_kind, source_idx)
        # source_kind: 0 -> x/state-algebraic vars, 1 -> runtime params,
        # 2 -> const params, 3 -> accepted sample time, 4 -> target global time
        refs_by_uid: Dict[int, Tuple[int, int, int]] = dict()

        var: Var
        for var in expr_eval.get_vars():
            if var.name == "glob_time" or var.uid == problem.glob_time.uid:
                refs_by_uid[var.uid] = (var.uid, 4, -1)
            elif var.name == "time":
                refs_by_uid[var.uid] = (var.uid, 3, -1)
            else:
                idx_var: int | None = problem.uid2idx_vars.get(var.uid, None)
                if idx_var is not None:
                    refs_by_uid[var.uid] = (var.uid, 0, int(idx_var))
                else:
                    idx_runtime: int | None = problem.uid2idx_event_params.get(
                        var.uid,
                        None,
                    )
                    if idx_runtime is not None:
                        refs_by_uid[var.uid] = (var.uid, 1, int(idx_runtime))
                    else:
                        idx_const: int | None = problem.uid2idx_params.get(
                            var.uid,
                            None,
                        )
                        if idx_const is not None:
                            refs_by_uid[var.uid] = (var.uid, 2, int(idx_const))
                        else:
                            raise KeyError(
                                f"Unknown procedural variable '{var.name}'"
                            )

        return list(refs_by_uid.values())

    def _get_expr_plan(self, expr_eval: Expr, problem: ProceduralProblem) -> List[Tuple[int, int, int]]:
        """Return the cached runtime-reference plan for an expression.

        :param expr_eval: Symbolic expression whose variable references are needed.
        :param problem: Runtime problem that maps symbolic UIDs to storage indices.
        :return: Ordered variable UID, storage kind, and storage index tuples.
        """
        key = id(expr_eval)
        if key in self._expr_plan_cache:
            return self._expr_plan_cache[key]

        plan = self._build_expr_plan(expr_eval, problem)
        self._expr_plan_cache[key] = plan
        return plan

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Update mode or event parameters before the Newton step.

        :param t: Current solver time.
        :param x: Current accepted state.
        :param params: Runtime parameter vector to mutate in place.
        :return: None
        """
        _unused = (t, x, params)

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the next exact event time inside the interval if known.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Event time or None.
        """
        self._sample_time = float(t_prev)
        _unused = t_target
        return None

    def remap(self, var_mapping: VarRemap) -> "ProceduralLogicBase":
        """
        Clone one logic entry under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped procedural logic entry.
        """
        _unused = var_mapping
        return build_procedural_logic_entry(procedural_logic_entry_to_dict(self))

    def remap_with_structural_vars(
            self,
            var_mapping: VarRemap,
            structural_var_mapping: Dict[int, Var],
    ) -> "ProceduralLogicBase":
        """Clone one entry with symbolic and stable structural mappings.

        Ordinary procedural entries contain expressions or names and therefore
        use their established symbolic remapping. Entries holding live variable
        references override this method to consume the stable structural map.

        :param var_mapping: Variable and name substitution map.
        :param structural_var_mapping: Stable source identities mapped to cloned variables.
        :return: Remapped procedural logic entry.
        """
        _unused: Dict[int, Var] = structural_var_mapping
        return self.remap(var_mapping)

    def to_data(self) -> ProceduralLogicData:
        """Return the version-independent declarative logic representation.

        :return: Typed declarative logic data.
        """
        return procedural_logic_entry_to_dict(self)

    def _get_problem(self) -> ProceduralProblem:
        """
        Return the bound EMT problem.

        :return: Bound EMT problem.
        """
        if self._problem is None:
            raise RuntimeError("Procedural logic must be bound to an EMT problem before runtime evaluation")
        return self._problem

    def _get_sample_time(self, t: float) -> float:
        """
        Return the accepted sample time associated with the current update.

        :param t: Current solver time.
        :return: Accepted sample time.
        """
        return float(t if self._sample_time is None else self._sample_time)

    def evaluate_numeric_expression(
            self,
            expr: Expr | Comparison | float | int | bool,
            t: float,
            x: Vec,
            params: Vec,
    ) -> float:
        """
        Evaluate a procedural expression against the accepted EMT state.

        :param expr: Expression or comparison to evaluate.
        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: Numeric value of the expression.
        """
        # The evaluator always resolves symbols against the accepted state, not the Newton iterate.
        problem = self._get_problem()
        sample_time = self._get_sample_time(t)

        if isinstance(expr, (float, int)):
            return float(expr)

        expr_eval: Expr = self._get_normalized_expr(expr)

        if isinstance(expr_eval, Const):
            return 0.0 if expr_eval.value is None else float(expr_eval.value)

        if isinstance(expr_eval, Var):
            # Fast-path single variables because they dominate the procedural runtime workload.
            if expr_eval.name == "glob_time":
                # Global time belongs to the target boundary being evaluated.
                # The accepted state may still come from the previous boundary,
                # but delaying this clock would postpone time-driven selectors
                # by one complete integration step.
                return float(t)
            elif expr_eval.name == "time":
                return sample_time
            else:
                pass

            idx_var = problem.uid2idx_vars.get(expr_eval.uid, None)
            if idx_var is not None:
                return float(x[idx_var])

            idx_runtime = problem.uid2idx_event_params.get(expr_eval.uid, None)
            if idx_runtime is not None:
                return float(params[idx_runtime])

            idx_const = problem.uid2idx_params.get(expr_eval.uid, None)
            if idx_const is not None:
                n_runtime = problem.get_variable_parameter_number()
                if len(params) >= n_runtime + len(problem.get_parameters_values()):
                    return float(params[n_runtime + idx_const])
                return float(problem.get_parameters_values()[idx_const].value)

            raise KeyError(f"Unknown procedural variable '{expr_eval.name}'")

        plan: List[Tuple[int, int, int]] = self._get_expr_plan(
            expr_eval=expr_eval,
            problem=problem,
        )
        n_runtime: int = problem.get_variable_parameter_number()
        const_values: List[Const] = problem.get_parameters_values()
        params_has_consts: bool = len(params) >= n_runtime + len(const_values)
        binding_key: int = id(expr_eval)
        uid_bindings: Dict[int, float] | None = self._expr_binding_cache.get(
            binding_key,
            None,
        )
        if uid_bindings is None:
            uid_bindings = dict()
            self._expr_binding_cache[binding_key] = uid_bindings
        else:
            pass

        uid: int
        source_kind: int
        source_idx: int
        for uid, source_kind, source_idx in plan:
            if source_kind == 0:
                uid_bindings[uid] = float(x[source_idx])
            else:
                if source_kind == 1:
                    uid_bindings[uid] = float(params[source_idx])
                else:
                    if source_kind == 2:
                        if params_has_consts:
                            uid_bindings[uid] = float(
                                params[n_runtime + source_idx]
                            )
                        else:
                            uid_bindings[uid] = float(
                                const_values[source_idx].value
                            )
                    elif source_kind == 3:
                        uid_bindings[uid] = sample_time
                    else:
                        uid_bindings[uid] = float(t)

        # Declarative global time is the current solver boundary even though
        # ordinary state variables are sampled from the accepted snapshot.
        uid_bindings[problem.glob_time.uid] = float(t)

        return float(expr_eval.eval_uid(uid_bindings))

    def _eval_bool(self, expr: Expr | Comparison, t: float, x: Vec, params: Vec) -> bool:
        """
        Evaluate one procedural condition using the accepted EMT state.

        :param expr: Expression or comparison to evaluate.
        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: True when the expression evaluates above 0.5.
        """
        return self.evaluate_numeric_expression(expr, t, x, params) > 0.5

    def _build_numeric_evaluator(
            self,
            expr: Expr | Comparison | float | int | bool,
    ) -> ProceduralNumericEvaluator:
        """Build one typed evaluator without nested or generated functions.

        :param expr: Declarative procedural expression or scalar.
        :return: Evaluator bound to this procedural state machine.
        """
        self._get_problem()
        return ProceduralNumericEvaluator(logic=self, expression=expr)



class ConditionalDiagnosticLogic(ProceduralLogicBase):
    """Preserve one conditional source-model diagnostic declaratively.

    The entry deliberately owns no presentation side effect. Solver or UI code
    may later consume the typed condition and exact message according to its
    logging policy without making import-time data executable.

    :param condition_expr: Boolean expression that activates the diagnostic.
    :param message: Exact source diagnostic text.
    :param initialization_only: Whether PowerFactory evaluates it only during initialization.
    :param name: Optional diagnostic display name.
    """

    __slots__ = ("condition_expr", "message", "initialization_only")
    logic_tpe = ProceduralLogicType.ConditionalDiagnostic

    def __init__(
            self,
            condition_expr: Expr | Comparison,
            message: str,
            initialization_only: bool,
            name: str = "",
    ) -> None:
        """Store one source-model diagnostic without executing it.

        :param condition_expr: Boolean expression that activates the diagnostic.
        :param message: Exact diagnostic text.
        :param initialization_only: Whether this is an initialization-only ``outfix`` declaration.
        :param name: Optional diagnostic display name.
        :return: None.
        """
        super().__init__(name=name)
        self.condition_expr: Expr | Comparison = condition_expr
        self.message: str = message
        self.initialization_only: bool = initialization_only

    def remap(self, var_mapping: VarRemap) -> "ConditionalDiagnosticLogic":
        """Clone the diagnostic under a symbolic variable mapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped diagnostic declaration.
        """
        remapped_condition: Expr | Comparison = _subs_expr_like(
            expr=self.condition_expr,
            mapping=var_mapping,
        )
        return ConditionalDiagnosticLogic(
            condition_expr=remapped_condition,
            message=self.message,
            initialization_only=self.initialization_only,
            name=self.name,
        )


class DelayedSwitchEventLogic(ProceduralLogicBase):
    """Apply one delayed switch command on a guarded rising trigger edge."""

    __slots__ = (
        "output_var_name",
        "guard_expr",
        "trigger_expr",
        "delay_expr",
        "target_device_idtag",
        "target_switch_idtag",
        "target_terminal_index",
        "initial_closed",
        "command_closed",
        "output_idx",
        "state",
        "initialized",
        "trigger_was_high",
        "pending_event_time",
        "fired",
    )
    logic_tpe = ProceduralLogicType.DelayedSwitchEvent

    def __init__(
        self,
        output_var_name: str,
        guard_expr: Expr | Comparison,
        trigger_expr: Expr | Comparison,
        delay_expr: Expr | Comparison,
        target_device_idtag: str,
        target_switch_idtag: str,
        target_terminal_index: int,
        initial_closed: bool,
        command_closed: bool,
        name: str = "",
    ) -> None:
        """Store one executable switch-event declaration.

        :param output_var_name: Runtime mode representing the switch position.
        :param guard_expr: Event enable expression; values at least ``0.5`` enable it.
        :param trigger_expr: Expression whose rising zero crossing arms the event.
        :param delay_expr: Non-negative delay evaluated when the trigger rises.
        :param target_device_idtag: Exact physical equipment identifier.
        :param target_switch_idtag: Exact switch identifier resolved from the source slot.
        :param target_terminal_index: Physical equipment terminal containing the switch.
        :param initial_closed: Exported initial switch position.
        :param command_closed: Switch position applied when the event fires.
        :param name: Human-readable event name.
        :return: None.
        """
        super().__init__(name=name)
        self.output_var_name: str = output_var_name
        self.guard_expr: Expr | Comparison = guard_expr
        self.trigger_expr: Expr | Comparison = trigger_expr
        self.delay_expr: Expr | Comparison = delay_expr
        self.target_device_idtag: str = target_device_idtag
        self.target_switch_idtag: str = target_switch_idtag
        self.target_terminal_index: int = target_terminal_index
        self.initial_closed: bool = initial_closed
        self.command_closed: bool = command_closed
        self.output_idx: int = -1
        self.state: float = 1.0 if initial_closed else 0.0
        self.initialized: bool = False
        self.trigger_was_high: bool = False
        self.pending_event_time: Optional[float] = None
        self.fired: bool = False

    def bind(self, problem: ProceduralProblem) -> None:
        """Resolve the local switch-position mode and clear runtime state.

        :param problem: Bound RMS or EMT problem.
        :return: None.
        """
        super().bind(problem)
        output_var: Var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.state = 1.0 if self.initial_closed else 0.0
        self.initialized = False
        self.trigger_was_high = False
        self.pending_event_time = None
        self.fired = False

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """Return the exact delayed command boundary inside the next step.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Pending event time inside the interval, if any.
        """
        super().get_next_forced_event_time(t_prev, t_target)
        if (
            self.pending_event_time is not None
            and t_prev < self.pending_event_time <= t_target
        ):
            return self.pending_event_time
        else:
            return None

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """Detect a guarded rising edge and apply its delayed command once.

        :param t: Current accepted solver time.
        :param x: Current accepted state vector.
        :param params: Runtime parameter vector updated in place.
        :return: None.
        """
        trigger_high: bool = self.evaluate_numeric_expression(self.trigger_expr, t, x, params) > 0.0
        if not self.initialized:
            self.initialized = True
            self.trigger_was_high = trigger_high
        else:
            rising_edge: bool = trigger_high and not self.trigger_was_high
            guard_enabled: bool = self.evaluate_numeric_expression(self.guard_expr, t, x, params) >= 0.5
            if rising_edge and guard_enabled and not self.fired and self.pending_event_time is None:
                effective_delay_seconds: float = max(
                    0.0,
                    self.evaluate_numeric_expression(self.delay_expr, t, x, params),
                )
                self.pending_event_time = (
                    self._get_sample_time(t) + effective_delay_seconds
                )
            else:
                pass
            self.trigger_was_high = trigger_high

        if self.pending_event_time is not None and t >= self.pending_event_time - 1.0e-15:
            self.state = 1.0 if self.command_closed else 0.0
            self.pending_event_time = None
            self.fired = True
        else:
            pass
        params[self.output_idx] = self.state

    def remap(self, var_mapping: VarRemap) -> "DelayedSwitchEventLogic":
        """Clone the event under one symbolic variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped switch event.
        """
        name_mapping: Dict[str, str] = _build_name_mapping(var_mapping)
        return DelayedSwitchEventLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            guard_expr=_subs_expr_like(self.guard_expr, var_mapping),
            trigger_expr=_subs_expr_like(self.trigger_expr, var_mapping),
            delay_expr=_subs_expr_like(self.delay_expr, var_mapping),
            target_device_idtag=self.target_device_idtag,
            target_switch_idtag=self.target_switch_idtag,
            target_terminal_index=self.target_terminal_index,
            initial_closed=self.initial_closed,
            command_closed=self.command_closed,
            name=self.name,
        )


class FixedSampleLogic(ProceduralLogicBase):
    """
    Retain the initial truth value of one condition in a runtime mode variable.
    """

    __slots__ = ["output_var_name", "condition_expr", "output_idx", "initialized"]
    logic_tpe = ProceduralLogicType.FixedSample

    def __init__(self, output_var_name: str, condition_expr: Expr | Comparison, name: str = "") -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.condition_expr = condition_expr
        self.output_idx = -1
        self.initialized = False

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve the runtime output slot for this logic entry.

        :param problem: Bound EMT problem.
        :return: None
        """
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.initialized = False

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Sample the condition once and keep it fixed afterward.

        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: None
        """
        if self.initialized:
            return

        params[self.output_idx] = 1.0 if self._eval_bool(self.condition_expr, t, x, params) else 0.0
        self.initialized = True

    def remap(self, var_mapping: VarRemap) -> "FixedSampleLogic":
        """
        Clone the logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped fixed-sample logic.
        """
        name_mapping = _build_name_mapping(var_mapping)
        return FixedSampleLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            condition_expr=_subs_expr_like(self.condition_expr, var_mapping),
            name=self.name,
        )


class SampledValueLogic(ProceduralLogicBase):
    """
    Sample one expression at each accepted step and store it in a runtime mode variable.
    """

    __slots__ = [
        "output_var_name",
        "output_var_uid",
        "source_expr",
        "output_idx",
        "_source_eval",
    ]
    logic_tpe = ProceduralLogicType.SampledValue

    def __init__(
            self,
            output_var_name: str,
            source_expr: Expr | Comparison,
            name: str = "",
            output_var_uid: int | None = None,
    ) -> None:
        """Create one accepted-state projection into a runtime parameter.

        :param output_var_name: Persisted output name for legacy compatibility.
        :param source_expr: Declarative source expression.
        :param name: Optional logic name.
        :param output_var_uid: Exact canonical output UID when available.
        :return: None.
        """
        super().__init__(name=name)
        self.output_var_name: str = output_var_name
        self.output_var_uid: int | None = output_var_uid
        self.source_expr: Expr | Comparison = source_expr
        self.output_idx: int = -1
        self._source_eval: ProceduralNumericEvaluator | None = None

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve the runtime output slot for this sampled value.

        :param problem: Bound EMT problem.
        :return: None
        """
        super().bind(problem)
        if self.output_var_uid is None:
            output_var: Var = _find_var_by_name(
                problem.sys_block,
                self.output_var_name,
            )
        else:
            output_var_optional: Var | None = _find_var_by_uid_optional(
                block=problem.sys_block,
                var_uid=self.output_var_uid,
            )
            if output_var_optional is None:
                raise KeyError(
                    f"Procedural output UID '{self.output_var_uid}' was not found"
                )
            else:
                output_var = output_var_optional
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self._source_eval = self._build_numeric_evaluator(self.source_expr)

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Refresh the sampled value using the accepted state.

        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: None
        """
        if self._source_eval is None:
            self._source_eval = self._build_numeric_evaluator(self.source_expr)

        params[self.output_idx] = self._source_eval(t, x, params)

    def remap(self, var_mapping: VarRemap) -> "SampledValueLogic":
        """
        Clone the logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped sampled-value logic.
        """
        name_mapping = _build_name_mapping(var_mapping)
        return SampledValueLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            source_expr=_subs_expr_like(self.source_expr, var_mapping),
            name=self.name,
            output_var_uid=_remap_var_uid(
                var_uid=self.output_var_uid,
                var_mapping=var_mapping,
            ),
        )


class HardSaturationLogic(ProceduralLogicBase):
    """
    Sample one input and apply hard saturation to a runtime mode variable.
    """

    __slots__ = ["output_var_name", "u_expr", "u_min_expr", "u_max_expr", "output_idx", "_u_eval", "_u_min_eval", "_u_max_eval"]
    logic_tpe = ProceduralLogicType.HardSaturation

    def __init__(
        self,
        output_var_name: str,
        u_expr: Expr | Comparison,
        u_min_expr: Expr | Comparison,
        u_max_expr: Expr | Comparison,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.u_expr = u_expr
        self.u_min_expr = u_min_expr
        self.u_max_expr = u_max_expr
        self.output_idx = -1
        self._u_eval: ProceduralNumericEvaluator | None = None
        self._u_min_eval: ProceduralNumericEvaluator | None = None
        self._u_max_eval: ProceduralNumericEvaluator | None = None

    def bind(self, problem: ProceduralProblem) -> None:
        """Bind the saturation output and numeric evaluators to a problem.

        :param problem: Runtime problem that owns variables and parameter indices.
        :return: None.
        """
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self._u_eval = self._build_numeric_evaluator(self.u_expr)
        self._u_min_eval = self._build_numeric_evaluator(self.u_min_expr)
        self._u_max_eval = self._build_numeric_evaluator(self.u_max_expr)

    def update(self, t: float, x: Vec, params: Vec) -> None:
        if self._u_eval is None:
            self._u_eval = self._build_numeric_evaluator(self.u_expr)
        if self._u_min_eval is None:
            self._u_min_eval = self._build_numeric_evaluator(self.u_min_expr)
        if self._u_max_eval is None:
            self._u_max_eval = self._build_numeric_evaluator(self.u_max_expr)

        assert self._u_eval is not None
        assert self._u_min_eval is not None
        assert self._u_max_eval is not None

        u_val: float = float(self._u_eval(t, x, params))
        u_min_val: float = float(self._u_min_eval(t, x, params))
        u_max_val: float = float(self._u_max_eval(t, x, params))
        if u_min_val <= u_max_val:
            params[self.output_idx] = min(max(u_val, u_min_val), u_max_val)
        else:
            params[self.output_idx] = min(max(u_val, u_max_val), u_min_val)

    def remap(self, var_mapping: VarRemap) -> "HardSaturationLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return HardSaturationLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            u_expr=_subs_expr_like(self.u_expr, var_mapping),
            u_min_expr=_subs_expr_like(self.u_min_expr, var_mapping),
            u_max_expr=_subs_expr_like(self.u_max_expr, var_mapping),
            name=self.name,
        )


class TimeDelayLogic(ProceduralLogicBase):
    """
    Sample one input and expose its delayed value through a runtime mode variable.
    """

    __slots__ = ["output_var_name", "source_expr", "delay_expr", "output_idx", "history"]
    logic_tpe = ProceduralLogicType.TimeDelay

    def __init__(
        self,
        output_var_name: str,
        source_expr: Expr | Comparison | float | int | bool,
        delay_expr: Expr | Comparison | float | int | bool,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.source_expr = source_expr
        self.delay_expr = delay_expr
        self.output_idx = -1
        self.history: List[Tuple[float, float]] = list()

    def bind(self, problem: ProceduralProblem) -> None:
        """Bind the delayed output and reset its sample history.

        :param problem: Runtime problem that owns variables and parameter indices.
        :return: None.
        """
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.history = list()

    def update(self, t: float, x: Vec, params: Vec) -> None:
        sample_time = self._get_sample_time(t)
        source_value = self.evaluate_numeric_expression(self.source_expr, t, x, params)
        delay_value = max(
            0.0,
            self.evaluate_numeric_expression(self.delay_expr, t, x, params),
        )

        _append_history_sample(self.history, sample_time, source_value)

        if delay_value <= 0.0:
            params[self.output_idx] = source_value
            return

        target_time = sample_time - delay_value
        params[self.output_idx] = _history_sample_at_or_before(self.history, target_time)
        _prune_history_keep_last_before(self.history, target_time)

    def remap(self, var_mapping: VarRemap) -> "TimeDelayLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return TimeDelayLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            source_expr=_subs_expr_like(self.source_expr, var_mapping),
            delay_expr=_subs_expr_like(self.delay_expr, var_mapping),
            name=self.name,
        )


class MovingAverageLogic(ProceduralLogicBase):
    """
    Buffer-based moving average with optional delay before the averaging window.
    """

    __slots__ = ["output_var_name", "source_expr", "delay_expr", "window_expr", "output_idx", "history"]
    logic_tpe = ProceduralLogicType.MovingAverage

    def __init__(
        self,
        output_var_name: str,
        source_expr: Expr | Comparison | float | int | bool,
        delay_expr: Expr | Comparison | float | int | bool,
        window_expr: Expr | Comparison | float | int | bool,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.source_expr = source_expr
        self.delay_expr = delay_expr
        self.window_expr = window_expr
        self.output_idx = -1
        self.history: List[Tuple[float, float]] = list()

    def bind(self, problem: ProceduralProblem) -> None:
        """Bind the moving-average output and reset its sample history.

        :param problem: Runtime problem that owns variables and parameter indices.
        :return: None.
        """
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.history = list()

    def update(self, t: float, x: Vec, params: Vec) -> None:
        sample_time = self._get_sample_time(t)
        source_value = self.evaluate_numeric_expression(self.source_expr, t, x, params)
        delay_value = max(
            0.0,
            self.evaluate_numeric_expression(self.delay_expr, t, x, params),
        )
        window_value = max(
            0.0,
            self.evaluate_numeric_expression(self.window_expr, t, x, params),
        )

        _append_history_sample(self.history, sample_time, source_value)

        target_end = sample_time - delay_value
        if window_value <= 0.0:
            params[self.output_idx] = _history_sample_at_or_before(self.history, target_end)
            _prune_history_keep_last_before(self.history, target_end)
            return

        target_start = target_end - window_value
        values_in_window: List[float] = [value for ts, value in self.history if target_start <= ts <= target_end]
        if len(values_in_window) == 0:
            params[self.output_idx] = _history_sample_at_or_before(self.history, target_end)
        else:
            params[self.output_idx] = float(sum(values_in_window) / len(values_in_window))
        _prune_history_keep_last_before(self.history, target_start)

    def remap(self, var_mapping: VarRemap) -> "MovingAverageLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return MovingAverageLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            source_expr=_subs_expr_like(self.source_expr, var_mapping),
            delay_expr=_subs_expr_like(self.delay_expr, var_mapping),
            window_expr=_subs_expr_like(self.window_expr, var_mapping),
            name=self.name,
        )


class GradientLimiterLogic(ProceduralLogicBase):
    """
    Clamp the rate of change of one procedural value between lower and upper slopes.
    """

    __slots__ = ["output_var_name", "source_expr", "lower_rate_expr", "upper_rate_expr", "output_idx", "last_time", "held_value", "initialized"]
    logic_tpe = ProceduralLogicType.GradientLimiter

    def __init__(
        self,
        output_var_name: str,
        source_expr: Expr | Comparison | float | int | bool,
        lower_rate_expr: Expr | Comparison | float | int | bool,
        upper_rate_expr: Expr | Comparison | float | int | bool,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.source_expr = source_expr
        self.lower_rate_expr = lower_rate_expr
        self.upper_rate_expr = upper_rate_expr
        self.output_idx = -1
        self.last_time: Optional[float] = None
        self.held_value = 0.0
        self.initialized = False

    def bind(self, problem: ProceduralProblem) -> None:
        """Bind the gradient-limited output and reset its runtime state.

        :param problem: Runtime problem that owns variables and parameter indices.
        :return: None.
        """
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.last_time = None
        self.held_value = 0.0
        self.initialized = False

    def update(self, t: float, x: Vec, params: Vec) -> None:
        sample_time = self._get_sample_time(t)
        source_value = self.evaluate_numeric_expression(self.source_expr, t, x, params)
        lower_rate = self.evaluate_numeric_expression(self.lower_rate_expr, t, x, params)
        upper_rate = self.evaluate_numeric_expression(self.upper_rate_expr, t, x, params)

        if not self.initialized or self.last_time is None:
            self.held_value = source_value
            self.last_time = sample_time
            self.initialized = True
            params[self.output_idx] = self.held_value
            return

        dt = max(0.0, sample_time - self.last_time)
        lower_bound = self.held_value + lower_rate * dt
        upper_bound = self.held_value + upper_rate * dt
        if lower_bound > upper_bound:
            lower_bound, upper_bound = upper_bound, lower_bound

        self.held_value = min(max(source_value, lower_bound), upper_bound)
        self.last_time = sample_time
        params[self.output_idx] = self.held_value

    def remap(self, var_mapping: VarRemap) -> "GradientLimiterLogic":
        name_mapping = _build_name_mapping(var_mapping)
        return GradientLimiterLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            source_expr=_subs_expr_like(self.source_expr, var_mapping),
            lower_rate_expr=_subs_expr_like(self.lower_rate_expr, var_mapping),
            upper_rate_expr=_subs_expr_like(self.upper_rate_expr, var_mapping),
            name=self.name,
        )


class FlipFlopLogic(ProceduralLogicBase):
    """
    Store a binary set/reset latch in a runtime mode variable.
    """

    __slots__ = ["output_var_name", "set_expr", "reset_expr", "output_idx", "state", "initialized"]
    logic_tpe = ProceduralLogicType.FlipFlop

    def __init__(
        self,
        output_var_name: str,
        set_expr: Expr | Comparison,
        reset_expr: Expr | Comparison,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.set_expr = set_expr
        self.reset_expr = reset_expr
        self.output_idx = -1
        self.state = 0.0
        self.initialized = False

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve the runtime output slot for the latch state.

        :param problem: Bound EMT problem.
        :return: None
        """
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.state = 0.0
        self.initialized = False

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Apply set/reset semantics and write the resulting latch state.

        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: None
        """
        # First evaluate the two boolean inputs at the accepted sample state.
        set_on = self._eval_bool(self.set_expr, t, x, params)
        reset_on = self._eval_bool(self.reset_expr, t, x, params)

        if not self.initialized:
            # The initial state follows the SET input, but conflicting SET/RESET is invalid.
            if set_on and reset_on:
                raise ValueError(f"flipflop '{self.name or self.output_var_name}' cannot initialize with set=1 and reset=1")
            self.state = 1.0 if set_on else 0.0
            self.initialized = True
        elif set_on and not reset_on:
            # A pure SET edge drives the latched state high.
            self.state = 1.0
        elif (not set_on) and reset_on:
            # A pure RESET edge drives the latched state low.
            self.state = 0.0

        # The runtime parameter vector always exposes the latest latch state.
        params[self.output_idx] = self.state

    def remap(self, var_mapping: VarRemap) -> "FlipFlopLogic":
        """
        Clone the logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped flip-flop logic.
        """
        name_mapping = _build_name_mapping(var_mapping)
        return FlipFlopLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            set_expr=_subs_expr_like(self.set_expr, var_mapping),
            reset_expr=_subs_expr_like(self.reset_expr, var_mapping),
            name=self.name,
        )


class AnalogFlipFlopLogic(ProceduralLogicBase):
    """
    Store an analog value when a set/reset latch enters the high state.
    """

    __slots__ = [
        "output_var_name",
        "input_expr",
        "set_expr",
        "reset_expr",
        "output_idx",
        "state",
        "initialized",
        "held_value",
    ]
    logic_tpe = ProceduralLogicType.AnalogFlipFlop

    def __init__(
        self,
        output_var_name: str,
        input_expr: Expr | Comparison,
        set_expr: Expr | Comparison,
        reset_expr: Expr | Comparison,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.input_expr = input_expr
        self.set_expr = set_expr
        self.reset_expr = reset_expr
        self.output_idx = -1
        self.state = 0.0
        self.initialized = False
        self.held_value = 0.0

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve the runtime output slot and reset the analog latch state.

        :param problem: Bound EMT problem.
        :return: None
        """
        super().bind(problem)
        output_var = _find_var_by_name(problem.sys_block, self.output_var_name)
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.state = 0.0
        self.initialized = False
        self.held_value = 0.0

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Apply analog set/reset semantics and update the held value.

        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: None
        """
        # Evaluate the analog input and the set/reset conditions first.
        input_value = self.evaluate_numeric_expression(self.input_expr, t, x, params)
        set_on = self._eval_bool(self.set_expr, t, x, params)
        reset_on = self._eval_bool(self.reset_expr, t, x, params)

        if not self.initialized:
            # Initialization captures the current analog value only if the latch starts set.
            if set_on and reset_on:
                raise ValueError(f"aflipflop '{self.name or self.output_var_name}' cannot initialize with set=1 and reset=1")
            self.state = 1.0 if set_on else 0.0
            self.held_value = input_value
            self.initialized = True
        elif set_on and not reset_on and self.state < 0.5:
            # The analog value is captured only on the transition from 0 -> 1.
            self.state = 1.0
            self.held_value = input_value
        elif (not set_on) and reset_on and self.state > 0.5:
            # Reset releases the latch and the output follows the live input again.
            self.state = 0.0

        # Expose the held value when latched high, otherwise expose the live input.
        params[self.output_idx] = self.held_value if self.state > 0.5 else input_value

    def remap(self, var_mapping: VarRemap) -> "AnalogFlipFlopLogic":
        """
        Clone the logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped analog flip-flop logic.
        """
        name_mapping = _build_name_mapping(var_mapping)
        return AnalogFlipFlopLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            input_expr=_subs_expr_like(self.input_expr, var_mapping),
            set_expr=_subs_expr_like(self.set_expr, var_mapping),
            reset_expr=_subs_expr_like(self.reset_expr, var_mapping),
            name=self.name,
        )


class PickupDropoffLogic(ProceduralLogicBase):
    """
    Implement a delayed pickup/dropoff relay with retained binary state.
    """

    __slots__ = [
        "output_var_name",
        "output_var_uid",
        "bool_expr",
        "pickup_delay_expr",
        "drop_delay_expr",
        "output_idx",
        "state",
        "initialized",
        "pickup_started_at",
        "drop_started_at",
        "pending_pickup_time",
        "pending_drop_time",
    ]
    logic_tpe = ProceduralLogicType.PickupDropoff

    def __init__(
        self,
        output_var_name: str,
        bool_expr: Expr | Comparison,
        pickup_delay_expr: Expr | Comparison,
        drop_delay_expr: Expr | Comparison,
        name: str = "",
        output_var_uid: int | None = None,
    ) -> None:
        """Create one delayed pickup/dropoff relay state machine.

        :param output_var_name: Persisted output name for legacy lookup.
        :param bool_expr: Boolean pickup/dropoff driving expression.
        :param pickup_delay_expr: Delay before the output changes to one.
        :param drop_delay_expr: Delay before the output returns to zero.
        :param name: Optional user-facing logic name.
        :param output_var_uid: Exact canonical output UID when available.
        :return: None.
        """
        super().__init__(name=name)
        self.output_var_name = output_var_name
        self.output_var_uid: int | None = output_var_uid
        self.bool_expr = bool_expr
        self.pickup_delay_expr = pickup_delay_expr
        self.drop_delay_expr = drop_delay_expr
        self.output_idx = -1
        self.state = 0.0
        self.initialized = False
        self.pickup_started_at: Optional[float] = None
        self.drop_started_at: Optional[float] = None
        self.pending_pickup_time: Optional[float] = None
        self.pending_drop_time: Optional[float] = None

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve the runtime output slot and clear the relay timers.

        :param problem: Bound EMT problem.
        :return: None
        """
        super().bind(problem)
        if self.output_var_uid is None:
            output_var: Var = _find_var_by_name(
                problem.sys_block,
                self.output_var_name,
            )
        else:
            output_var_optional: Var | None = _find_var_by_uid_optional(
                block=problem.sys_block,
                var_uid=self.output_var_uid,
            )
            if output_var_optional is None:
                raise KeyError(
                    f"Procedural output UID '{self.output_var_uid}' was not found"
                )
            else:
                output_var = output_var_optional
        self.output_idx = int(problem.uid2idx_event_params[output_var.uid])
        self.state = 0.0
        self.initialized = False
        self.pickup_started_at = None
        self.drop_started_at = None
        self.pending_pickup_time = None
        self.pending_drop_time = None

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the next exact pickup or dropoff event inside one step.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: First pending relay event in the interval, if any.
        """
        super().get_next_forced_event_time(t_prev, t_target)
        candidates: List[float] = list()
        if self.pending_pickup_time is not None and t_prev < self.pending_pickup_time <= t_target:
            candidates.append(float(self.pending_pickup_time))
        if self.pending_drop_time is not None and t_prev < self.pending_drop_time <= t_target:
            candidates.append(float(self.pending_drop_time))
        if len(candidates) == 0:
            return None
        else:
            return min(candidates)

    def _eval_delay(self, expr: Expr | Comparison, t: float, x: Vec, params: Vec) -> float:
        """
        Evaluate one relay delay expression and clamp it to a non-negative value.

        :param expr: Delay expression.
        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: Non-negative evaluated delay.
        """
        return max(0.0, self.evaluate_numeric_expression(expr, t, x, params))

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Advance the relay timers and binary state.

        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: None
        """
        tol = 1.0e-15
        sample_time = self._get_sample_time(t)
        bool_on = self._eval_bool(self.bool_expr, t, x, params)

        if not self.initialized:
            # Initialization can trigger immediate pickup when the delay is zero.
            self.initialized = True
            if bool_on:
                pickup_delay = self._eval_delay(self.pickup_delay_expr, t, x, params)
                if pickup_delay <= tol:
                    self.state = 1.0
                else:
                    self.pickup_started_at = sample_time
                    self.pending_pickup_time = sample_time + pickup_delay

        if self.state < 0.5:
            # While the relay is low, only the pickup path can arm a pending event.
            self.drop_started_at = None
            self.pending_drop_time = None

            if bool_on:
                if self.pickup_started_at is None:
                    self.pickup_started_at = sample_time
                self.pending_pickup_time = self.pickup_started_at + self._eval_delay(self.pickup_delay_expr, t, x, params)
            else:
                self.pickup_started_at = None
                self.pending_pickup_time = None

            if self.pending_pickup_time is not None and t >= (self.pending_pickup_time - tol):
                self.state = 1.0
                self.pickup_started_at = None
                self.pending_pickup_time = None

        else:
            # While the relay is high, only the dropoff path can arm a pending event.
            self.pickup_started_at = None
            self.pending_pickup_time = None

            if not bool_on:
                if self.drop_started_at is None:
                    self.drop_started_at = sample_time
                self.pending_drop_time = self.drop_started_at + self._eval_delay(self.drop_delay_expr, t, x, params)
            else:
                self.drop_started_at = None
                self.pending_drop_time = None

            if self.pending_drop_time is not None and t >= (self.pending_drop_time - tol):
                self.state = 0.0
                self.drop_started_at = None
                self.pending_drop_time = None

        params[self.output_idx] = self.state

    def remap(self, var_mapping: VarRemap) -> "PickupDropoffLogic":
        """
        Clone the logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped pickup/dropoff logic.
        """
        name_mapping = _build_name_mapping(var_mapping)
        return PickupDropoffLogic(
            output_var_name=name_mapping.get(self.output_var_name, self.output_var_name),
            bool_expr=_subs_expr_like(self.bool_expr, var_mapping),
            pickup_delay_expr=_subs_expr_like(self.pickup_delay_expr, var_mapping),
            drop_delay_expr=_subs_expr_like(self.drop_delay_expr, var_mapping),
            name=self.name,
            output_var_uid=_remap_var_uid(
                var_uid=self.output_var_uid,
                var_mapping=var_mapping,
            ),
        )


class ResetOnRisingEdgeLogic(ProceduralLogicBase):
    """
    Apply one value reset on the rising edge of a procedural condition.
    """

    __slots__ = [
        "target_var_name",
        "reset_expr",
        "value_expr",
        "target_state_idx",
        "target_param_idx",
        "initialized",
        "last_reset_high",
    ]
    logic_tpe = ProceduralLogicType.ResetOnRisingEdge

    def __init__(
        self,
        target_var_name: str,
        reset_expr: Expr | Comparison,
        value_expr: Expr | Comparison,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.target_var_name = target_var_name
        self.reset_expr = reset_expr
        self.value_expr = value_expr
        self.target_state_idx = -1
        self.target_param_idx = -1
        self.initialized = False
        self.last_reset_high = False

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve whether the reset target is a state variable or a runtime parameter.

        :param problem: Bound EMT problem.
        :return: None
        """
        super().bind(problem)
        target_var = _find_var_by_name(problem.sys_block, self.target_var_name)
        self.target_state_idx = int(problem.uid2idx_vars.get(target_var.uid, -1))
        self.target_param_idx = int(problem.uid2idx_event_params.get(target_var.uid, -1))

        if self.target_state_idx < 0 and self.target_param_idx < 0:
            raise KeyError(f"Reset target '{self.target_var_name}' is not a state/algebraic variable nor a runtime parameter")

        self.initialized = False
        self.last_reset_high = False

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Apply the reset value only on the rising edge of the reset condition.

        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: None
        """
        reset_high = self._eval_bool(self.reset_expr, t, x, params)

        if not self.initialized:
            self.initialized = True
            self.last_reset_high = reset_high
            return

        if (not self.last_reset_high) and reset_high:
            reset_value = self.evaluate_numeric_expression(self.value_expr, t, x, params)
            if self.target_state_idx >= 0:
                x[self.target_state_idx] = reset_value
            else:
                params[self.target_param_idx] = reset_value

        self.last_reset_high = reset_high

    def remap(self, var_mapping: VarRemap) -> "ResetOnRisingEdgeLogic":
        """
        Clone the logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped reset logic.
        """
        name_mapping = _build_name_mapping(var_mapping)
        return ResetOnRisingEdgeLogic(
            target_var_name=name_mapping.get(self.target_var_name, self.target_var_name),
            reset_expr=_subs_expr_like(self.reset_expr, var_mapping),
            value_expr=_subs_expr_like(self.value_expr, var_mapping),
            name=self.name,
        )


def fixed_sample(output: Var | str, when: Expr | Comparison, name: str = "") -> FixedSampleLogic:
    """
    Build a fixed-sample selector that stores a boolean condition at initialization.

    :param output: Runtime mode variable receiving the retained value.
    :param when: Condition sampled at initialization time.
    :param name: Optional logic name.
    :return: Fixed-sample procedural logic entry.
    """
    output_name = _coerce_var_name(output)
    return FixedSampleLogic(
        output_var_name=output_name,
        condition_expr=when,
        name=output_name if name == "" else name,
    )


def selfix(boolexpr: Expr | Comparison, output: Var | str, name: str = "") -> FixedSampleLogic:
    """
    Build the procedural equivalent of PowerFactory ``selfix``.

    :param boolexpr: Condition sampled at initialization time.
    :param output: Runtime mode variable receiving the retained value.
    :param name: Optional logic name.
    :return: Fixed-sample procedural logic entry.
    """
    return fixed_sample(output=output, when=boolexpr, name=name)


def selfix_const(boolexpr: Expr | Comparison, output: Var | str, name: str = "") -> FixedSampleLogic:
    """
    Build the procedural equivalent of PowerFactory ``selfix_const``.

    :param boolexpr: Condition sampled at initialization time.
    :param output: Runtime mode variable receiving the retained value.
    :param name: Optional logic name.
    :return: Fixed-sample procedural logic entry.
    """
    return fixed_sample(output=output, when=boolexpr, name=name)


def sampled_value(output: Var | str, source: Expr | Comparison, name: str = "") -> SampledValueLogic:
    """
    Build a sampled runtime value updated outside the Newton residual.

    :param output: Runtime mode variable receiving the sampled value.
    :param source: Source expression to be evaluated at the accepted sample time.
    :param name: Optional logic name.
    :return: Sampled-value procedural logic entry.
    """
    output_name = _coerce_var_name(output)
    output_uid: int | None = output.uid if isinstance(output, Var) else None
    return SampledValueLogic(
        output_var_name=output_name,
        source_expr=source,
        name=output_name if name == "" else name,
        output_var_uid=output_uid,
    )


def hard_saturation(
    output: Var | str,
    u: Expr | Comparison,
    u_min: Expr | Comparison,
    u_max: Expr | Comparison,
    name: str = "",
) -> HardSaturationLogic:
    """
    Build one procedural hard-saturation entry updated outside Newton residuals.

    :param output: Runtime mode variable receiving saturated value.
    :param u: Unsaturated input expression.
    :param u_min: Lower saturation bound.
    :param u_max: Upper saturation bound.
    :param name: Optional logic name.
    :return: Hard-saturation procedural logic entry.
    """
    output_name = _coerce_var_name(output)
    return HardSaturationLogic(
        output_var_name=output_name,
        u_expr=u,
        u_min_expr=u_min,
        u_max_expr=u_max,
        name=output_name if name == "" else name,
    )


def lastvalue(input_expr: Expr | Comparison, output: Var | str, name: str = "") -> SampledValueLogic:
    """
    Build the procedural equivalent of PowerFactory ``lastvalue``.

    :param input_expr: Source expression to be sampled.
    :param output: Runtime mode variable receiving the sampled value.
    :param name: Optional logic name.
    :return: Sampled-value procedural logic entry.
    """
    return sampled_value(output=output, source=input_expr, name=name)


def delay(
    input_expr: Expr | Comparison | float | int | bool,
    T: Expr | Comparison | float | int | bool,
    output: Var | str,
    name: str = "",
) -> TimeDelayLogic:
    """
    Build the procedural equivalent of PowerFactory ``delay``.

    :param input_expr: Source expression to be delayed.
    :param T: Delay in seconds.
    :param output: Runtime mode variable receiving the delayed value.
    :param name: Optional logic name.
    :return: Time-delay procedural logic entry.
    """
    output_name = _coerce_var_name(output)
    return TimeDelayLogic(
        output_var_name=output_name,
        source_expr=input_expr,
        delay_expr=T,
        name=output_name if name == "" else name,
    )


def movingavg(
    input_expr: Expr | Comparison | float | int | bool,
    Tdel: Expr | Comparison | float | int | bool,
    Tlength: Expr | Comparison | float | int | bool,
    output: Var | str,
    name: str = "",
) -> MovingAverageLogic:
    """
    Build the procedural equivalent of PowerFactory ``movingavg``.

    :param input_expr: Source expression to be averaged.
    :param Tdel: Delay before the averaging window.
    :param Tlength: Averaging window length in seconds.
    :param output: Runtime mode variable receiving the averaged value.
    :param name: Optional logic name.
    :return: Moving-average procedural logic entry.
    """
    output_name = _coerce_var_name(output)
    return MovingAverageLogic(
        output_var_name=output_name,
        source_expr=input_expr,
        delay_expr=Tdel,
        window_expr=Tlength,
        name=output_name if name == "" else name,
    )


def gradlim_const(
    input_expr: Expr | Comparison | float | int | bool,
    gradmin: Expr | Comparison | float | int | bool,
    gradmax: Expr | Comparison | float | int | bool,
    output: Var | str,
    name: str = "",
) -> GradientLimiterLogic:
    """
    Build the procedural equivalent of PowerFactory ``gradlim_const``.

    :param input_expr: Source expression to be rate-limited.
    :param gradmin: Lower slope limit.
    :param gradmax: Upper slope limit.
    :param output: Runtime mode variable receiving the limited value.
    :param name: Optional logic name.
    :return: Gradient-limiter procedural logic entry.
    """
    output_name = _coerce_var_name(output)
    return GradientLimiterLogic(
        output_var_name=output_name,
        source_expr=input_expr,
        lower_rate_expr=gradmin,
        upper_rate_expr=gradmax,
        name=output_name if name == "" else name,
    )


def flipflop(boolset: Expr | Comparison, boolreset: Expr | Comparison, output: Var | str, name: str = "") -> FlipFlopLogic:
    """
    Build the procedural equivalent of PowerFactory ``flipflop``.

    :param boolset: Set condition.
    :param boolreset: Reset condition.
    :param output: Runtime mode variable storing the logical state.
    :param name: Optional logic name.
    :return: Flip-flop procedural logic entry.
    """
    output_name = _coerce_var_name(output)
    return FlipFlopLogic(
        output_var_name=output_name,
        set_expr=boolset,
        reset_expr=boolreset,
        name=output_name if name == "" else name,
    )


def aflipflop(
    x: Expr | Comparison,
    boolset: Expr | Comparison,
    boolreset: Expr | Comparison,
    output: Var | str,
    name: str = "",
) -> AnalogFlipFlopLogic:
    """
    Build the procedural equivalent of PowerFactory ``aflipflop``.

    :param x: Analog expression to store while the internal state is high.
    :param boolset: Set condition.
    :param boolreset: Reset condition.
    :param output: Runtime mode variable receiving the held analog value.
    :param name: Optional logic name.
    :return: Analog flip-flop procedural logic entry.
    """
    output_name = _coerce_var_name(output)
    return AnalogFlipFlopLogic(
        output_var_name=output_name,
        input_expr=x,
        set_expr=boolset,
        reset_expr=boolreset,
        name=output_name if name == "" else name,
    )


def pickup_dropoff(
    output: Var | str,
    boolexpr: Expr | Comparison,
    Tpick: Expr | Comparison,
    Tdrop: Expr | Comparison,
    name: str = "",
) -> PickupDropoffLogic:
    """
    Build a pickup/dropoff relay-style procedural logic entry.

    :param output: Runtime mode variable storing the relay state.
    :param boolexpr: Pickup/reset driving condition.
    :param Tpick: Pickup delay.
    :param Tdrop: Dropoff delay.
    :param name: Optional logic name.
    :return: Pickup/dropoff procedural logic entry.
    """
    output_name = _coerce_var_name(output)
    output_uid: int | None = output.uid if isinstance(output, Var) else None
    return PickupDropoffLogic(
        output_var_name=output_name,
        bool_expr=boolexpr,
        pickup_delay_expr=Tpick,
        drop_delay_expr=Tdrop,
        name=output_name if name == "" else name,
        output_var_uid=output_uid,
    )


def picdro(
    boolexpr: Expr | Comparison,
    Tpick: Expr | Comparison,
    Tdrop: Expr | Comparison,
    output: Var | str,
    name: str = "",
) -> PickupDropoffLogic:
    """
    Build the procedural equivalent of PowerFactory ``picdro``.

    :param boolexpr: Relay driving condition.
    :param Tpick: Pickup delay.
    :param Tdrop: Dropoff delay.
    :param output: Runtime mode variable storing the relay state.
    :param name: Optional logic name.
    :return: Pickup/dropoff procedural logic entry.
    """
    return pickup_dropoff(output=output, boolexpr=boolexpr, Tpick=Tpick, Tdrop=Tdrop, name=name)


def picdro_const(
    boolexpr: Expr | Comparison,
    Tpick: Expr | Comparison,
    Tdrop: Expr | Comparison,
    output: Var | str,
    name: str = "",
) -> PickupDropoffLogic:
    """
    Build the procedural equivalent of PowerFactory ``picdro_const``.

    :param boolexpr: Relay driving condition.
    :param Tpick: Pickup delay.
    :param Tdrop: Dropoff delay.
    :param output: Runtime mode variable storing the relay state.
    :param name: Optional logic name.
    :return: Pickup/dropoff procedural logic entry.
    """
    return pickup_dropoff(output=output, boolexpr=boolexpr, Tpick=Tpick, Tdrop=Tdrop, name=name)


def reset(var: Var | str, rst: Expr | Comparison, val: Expr | Comparison, name: str = "") -> ResetOnRisingEdgeLogic:
    """
    Build the procedural equivalent of PowerFactory ``reset``.

    :param var: Target runtime/state variable name.
    :param rst: Reset trigger condition.
    :param val: Value applied on the rising edge.
    :param name: Optional logic name.
    :return: Reset-on-rising-edge procedural logic entry.
    """
    target_name = _coerce_var_name(var)
    return ResetOnRisingEdgeLogic(
        target_var_name=target_name,
        reset_expr=rst,
        value_expr=val,
        name=f"{target_name}_reset" if name == "" else name,
    )


def startup_handover(
        mode: Var | str,
        t_enable: Var | str,
        name: str = "",
        on_value: Var | str | None = None,
) -> StartupHandoverLogic:
    """
    Build one exact-time startup-handover logic entry.

    :param mode: Retained mode variable that becomes ``1`` after the handover time.
    :param t_enable: Runtime parameter storing the switching-enable time.
    :param name: Optional logic name.
    :param on_value: Optional runtime parameter whose value is copied after handover.
    :return: Startup-handover procedural logic entry.
    """
    mode_name: str = _coerce_var_name(mode)
    enable_name: str = _coerce_var_name(t_enable)
    return StartupHandoverLogic(
        mode_var_name=mode_name,
        enable_time_var_name=enable_name,
        on_value_var_name=None if on_value is None else _coerce_var_name(on_value),
        name=mode_name if name == "" else name,
    )

def _iter_block_vars(block: Block) -> List[Var]:
    """
    Collect all variables reachable from one block tree.

    :param block: Root block to inspect.
    :return: Flat list of variables reachable from the tree.
    """
    vars_found: List[Var] = list()
    vars_found.extend(block.state_vars)
    vars_found.extend(block.algebraic_vars)
    vars_found.extend(block.diff_vars)
    vars_found.extend(block.in_vars)
    vars_found.extend(block.out_vars)
    vars_found.extend(list(block.event_dict.keys()))
    vars_found.extend(list(block.mode_dict.keys()))

    for child in block.children:
        vars_found.extend(_iter_block_vars(child))

    return vars_found


def _find_var_by_name(block: Block, var_name: str) -> Var:
    """
    Find one symbolic variable by name inside a block tree.

    :param block: Root block to inspect.
    :param var_name: Variable name to search.
    :return: Matching symbolic variable.
    """
    matching_var: Var | None = None
    var: Var
    for var in _iter_block_vars(block):
        if var.name == var_name:
            if matching_var is None:
                matching_var = var
            else:
                if matching_var.uid != var.uid:
                    raise KeyError(
                        f"Variable name '{var_name}' is ambiguous in block tree"
                    )
                else:
                    pass
        else:
            pass

    if matching_var is None:
        raise KeyError(f"Variable '{var_name}' not found in block tree")
    else:
        return matching_var


def _find_var_by_uid_optional(
        block: Block,
        var_uid: int,
) -> Var | None:
    """Return one exact variable by canonical UID.

    :param block: Root block to inspect.
    :param var_uid: Canonical symbolic variable UID.
    :return: Matching variable or ``None``.
    """
    var: Var
    for var in _iter_block_vars(block):
        if var.uid == var_uid:
            return var
        else:
            pass

    return None


def _find_var_by_name_optional(
        block: Block,
        var_name: str,
) -> Var | None:
    """
    Return one symbolic variable by name when it exists in the block tree.

    :param block: Root block to inspect.
    :param var_name: Variable name to search.
    :return: Matching symbolic variable or ``None``.
    """
    var: Var

    for var in _iter_block_vars(block):
        if var.name == var_name:
            return var
        else:
            pass

    return None


class DelayedThresholdLatchLogic(ProceduralLogicBase):
    """
    Comparator + timer + latch procedural logic for runtime modes.

    The logic watches one state variable, arms a timer when a threshold is crossed,
    applies a mode change after a delay, and optionally resets after a second delay.
    """

    __slots__ = [
        "monitored_var_name",
        "mode_var_name",
        "threshold",
        "delay",
        "reset_delay",
        "mode_idx",
        "monitored_idx",
        "pickup_time",
        "pending_trip_time",
        "pending_reset_time",
        "tripped",
        "trip_applied_time",
        "trip_applied_solver_time",
        "reset_applied_time",
        "reset_applied_solver_time",
        "last_t_prev",
        "trace_t",
        "trace_measure",
        "trace_comparator",
        "trace_timer_armed",
        "trace_latched",
        "trace_mode",
    ]
    logic_tpe = ProceduralLogicType.DelayedThresholdLatch

    def __init__(
        self,
        monitored_var_name: str,
        mode_var_name: str,
        threshold: float,
        delay: float,
        reset_delay: Optional[float] = None,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.monitored_var_name = monitored_var_name
        self.mode_var_name = mode_var_name
        self.threshold = float(threshold)
        self.delay = float(delay)
        self.reset_delay = None if reset_delay is None else float(reset_delay)

        self.mode_idx = -1
        self.monitored_idx = -1
        self.pickup_time: Optional[float] = None
        self.pending_trip_time: Optional[float] = None
        self.pending_reset_time: Optional[float] = None
        self.tripped = False
        self.trip_applied_time: Optional[float] = None
        self.trip_applied_solver_time: Optional[float] = None
        self.reset_applied_time: Optional[float] = None
        self.reset_applied_solver_time: Optional[float] = None
        self.last_t_prev: Optional[float] = None

        self.trace_t: List[float] = list()
        self.trace_measure: List[float] = list()
        self.trace_comparator: List[float] = list()
        self.trace_timer_armed: List[float] = list()
        self.trace_latched: List[float] = list()
        self.trace_mode: List[float] = list()

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve the monitored state and runtime mode indices.

        :param problem: Bound EMT problem.
        :return: None
        """
        super().bind(problem)
        mode_var = _find_var_by_name(problem.sys_block, self.mode_var_name)
        monitored_var = _find_var_by_name(problem.sys_block, self.monitored_var_name)
        self.mode_idx = int(problem.uid2idx_event_params[mode_var.uid])
        self.monitored_idx = int(problem.get_var_idx(monitored_var))

    def _append_trace_point(
        self,
        trace_time: float,
        measured_value: float,
        comparator: float,
        timer_armed: float,
        latched: float,
        mode_value: float,
    ) -> None:
        """
        Append one point to the internal tracing arrays.

        :param trace_time: Trace time.
        :param measured_value: Monitored value.
        :param comparator: Comparator state.
        :param timer_armed: Timer state.
        :param latched: Latch state.
        :param mode_value: Runtime mode state.
        :return: None
        """
        self.trace_t.append(float(trace_time))
        self.trace_measure.append(float(measured_value))
        self.trace_comparator.append(float(comparator))
        self.trace_timer_armed.append(float(timer_armed))
        self.trace_latched.append(float(latched))
        self.trace_mode.append(float(mode_value))

    def _record_sample_trace(self, sample_time: float, measured_value: float, params: np.ndarray) -> None:
        """
        Record one trace point at the accepted physical sample time.

        :param sample_time: Accepted sample time.
        :param measured_value: Monitored value.
        :param params: Runtime parameter vector.
        :return: None
        """
        comparator = 1.0 if measured_value >= self.threshold else 0.0
        timer_armed = 1.0 if self.pending_trip_time is not None else 0.0
        latched = 1.0 if self.tripped else 0.0
        mode_value = float(params[self.mode_idx])
        self._append_trace_point(sample_time, measured_value, comparator, timer_armed, latched, mode_value)

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the next exact trip or reset event inside one solver step.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: First pending event in the interval, if any.
        """
        super().get_next_forced_event_time(t_prev, t_target)
        self.last_t_prev = float(t_prev)
        candidates: List[float] = list()
        if self.pending_trip_time is not None and t_prev < self.pending_trip_time <= t_target:
            candidates.append(float(self.pending_trip_time))
        if self.pending_reset_time is not None and t_prev < self.pending_reset_time <= t_target:
            candidates.append(float(self.pending_reset_time))
        if len(candidates) == 0:
            return None
        else:
            return min(candidates)

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Advance the delayed-threshold latch logic and tracing state.

        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: None
        """
        tol = 1.0e-15
        sample_time = float(self.last_t_prev if self.last_t_prev is not None else t)
        measured_value = float(x[self.monitored_idx])
        comparator_on = measured_value >= self.threshold
        comparator_value = 1.0 if comparator_on else 0.0

        if self.tripped:
            # When already tripped, only the optional delayed reset can change the state.
            params[self.mode_idx] = 0.0
            if self.pending_reset_time is not None and t >= (self.pending_reset_time - tol):
                self.tripped = False
                self.reset_applied_time = float(self.pending_reset_time)
                self.reset_applied_solver_time = float(t)
                self.pickup_time = None
                self.pending_trip_time = None
                self.pending_reset_time = None
                params[self.mode_idx] = 1.0
                self._append_trace_point(t, measured_value, comparator_value, 0.0, 0.0, 1.0)
                return
            self._record_sample_trace(sample_time, measured_value, params)
            return

        if comparator_on:
            # Arm the pickup timer only once on the first threshold crossing.
            if self.pickup_time is None:
                self.pickup_time = sample_time
                self.pending_trip_time = sample_time + self.delay
        else:
            # Clearing the comparator also clears any unfinished pickup timer.
            self.pickup_time = None
            self.pending_trip_time = None

        if self.pending_trip_time is not None and t >= (self.pending_trip_time - tol):
            self.tripped = True
            self.trip_applied_time = float(self.pending_trip_time)
            self.trip_applied_solver_time = float(t)
            params[self.mode_idx] = 0.0
            if self.reset_delay is not None:
                self.pending_reset_time = self.trip_applied_time + self.reset_delay
            self.pending_trip_time = None
            self._append_trace_point(t, measured_value, comparator_value, 0.0, 1.0, 0.0)
            return

        params[self.mode_idx] = 1.0
        self._record_sample_trace(sample_time, measured_value, params)

    def get_trace_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Return the internal trace arrays as dense numpy arrays.

        :return: Tuple with times, measurements, comparator, timer, latch, and mode traces.
        """
        return (
            np.asarray(self.trace_t, dtype=float),
            np.asarray(self.trace_measure, dtype=float),
            np.asarray(self.trace_comparator, dtype=float),
            np.asarray(self.trace_timer_armed, dtype=float),
            np.asarray(self.trace_latched, dtype=float),
            np.asarray(self.trace_mode, dtype=float),
        )

    def remap(self, var_mapping: VarRemap) -> "DelayedThresholdLatchLogic":
        """
        Clone the logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped delayed-threshold latch logic.
        """
        name_mapping = _build_name_mapping(var_mapping)
        return DelayedThresholdLatchLogic(
            monitored_var_name=name_mapping.get(self.monitored_var_name, self.monitored_var_name),
            mode_var_name=name_mapping.get(self.mode_var_name, self.mode_var_name),
            threshold=self.threshold,
            delay=self.delay,
            reset_delay=self.reset_delay,
            name=self.name,
        )


class StartupHandoverLogic(ProceduralLogicBase):
    """
    One-shot startup handover for hybrid EMT converter models.

    The logic keeps one retained runtime mode at ``0`` during the averaged-startup
    interval and flips it to ``1`` exactly at ``t_enable``. This lets the DAE stay
    continuous before the handover while still forcing an exact solver split when
    the switched bridge becomes electrically active.
    """

    __slots__ = [
        "mode_var_name",
        "enable_time_var_name",
        "on_value_var_name",
        "mode_idx",
        "enable_time_idx",
        "on_value_idx",
    ]
    logic_tpe = ProceduralLogicType.StartupHandover

    def __init__(
            self,
            mode_var_name: str,
            enable_time_var_name: str,
            on_value_var_name: str | None = None,
            name: str = "",
    ) -> None:
        """
        Build one startup-handover procedural logic entry.

        :param mode_var_name: Retained runtime mode variable name.
        :param enable_time_var_name: Runtime parameter storing the handover time in seconds.
        :param name: Logic entry name.
        :return: None.
        """
        super().__init__(name=name)
        self.mode_var_name = mode_var_name
        self.enable_time_var_name = enable_time_var_name
        self.on_value_var_name = on_value_var_name
        self.mode_idx = -1
        self.enable_time_idx = -1
        self.on_value_idx = -1

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve the retained mode and enable-time runtime indices.

        :param problem: Bound EMT problem.
        :return: None.
        """
        mode_var: Var
        enable_time_var: Var

        super().bind(problem)
        mode_var = _find_var_by_name(problem.sys_block, self.mode_var_name)
        enable_time_var = _find_var_by_name(problem.sys_block, self.enable_time_var_name)
        self.mode_idx = int(problem.uid2idx_event_params[mode_var.uid])
        self.enable_time_idx = int(problem.uid2idx_event_params[enable_time_var.uid])
        if self.on_value_var_name is not None:
            on_value_var = _find_var_by_name(problem.sys_block, self.on_value_var_name)
            self.on_value_idx = int(problem.uid2idx_event_params[on_value_var.uid])
        else:
            self.on_value_idx = -1

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the exact startup-handover time when it falls inside one solver step.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Exact handover time or ``None``.
        """
        problem: ProceduralProblem
        enable_time: float

        super().get_next_forced_event_time(t_prev, t_target)
        problem = self._get_problem()
        enable_time = float(problem.event_params_values[self.enable_time_idx])

        if t_prev < enable_time <= t_target:
            return enable_time
        else:
            return None

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Update the retained startup mode from the current solver time.

        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: None.
        """
        _unused_x: Vec = x
        tol: float = 1.0e-15
        enable_time: float = float(params[self.enable_time_idx])

        if t >= (enable_time - tol):
            params[self.mode_idx] = 1.0 if self.on_value_idx < 0 else float(params[self.on_value_idx])
        else:
            params[self.mode_idx] = 0.0

    def remap(self, var_mapping: VarRemap) -> "StartupHandoverLogic":
        """
        Clone the logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped startup-handover logic.
        """
        name_mapping: Dict[str, str] = _build_name_mapping(var_mapping)
        return StartupHandoverLogic(
            mode_var_name=name_mapping.get(self.mode_var_name, self.mode_var_name),
            enable_time_var_name=name_mapping.get(self.enable_time_var_name, self.enable_time_var_name),
            on_value_var_name=(None if self.on_value_var_name is None
                               else name_mapping.get(self.on_value_var_name, self.on_value_var_name)),
            name=self.name,
        )


class ValveStateLogic(ProceduralLogicBase):
    """
    Retained conduction-state logic for generic EMT valve blocks.

    The logic updates a single retained runtime mode that encodes the active path:

    - ``+1``: forward conduction
    - ``0``: blocked state
    - ``-1``: reverse conduction through the antiparallel path
    """

    __slots__ = [
        "mode_var_name",
        "valve_type_var_name",
        "gate_var_name",
        "antiparallel_var_name",
        "voltage_eps_var_name",
        "current_eps_var_name",
        "valve_voltage_var_name",
        "valve_current_var_name",
        "mode_idx",
        "valve_type_idx",
        "gate_idx",
        "antiparallel_idx",
        "voltage_eps_idx",
        "current_eps_idx",
        "valve_voltage_idx",
        "valve_current_idx",
    ]
    logic_tpe = ProceduralLogicType.ValveState

    def __init__(
            self,
            mode_var_name: str,
            valve_type_var_name: str,
            gate_var_name: str,
            antiparallel_var_name: str,
            voltage_eps_var_name: str,
            current_eps_var_name: str,
            valve_voltage_var_name: str,
            valve_current_var_name: str,
            name: str = "",
    ) -> None:
        """
        Build one retained valve-state procedural logic entry.

        :param mode_var_name: Retained runtime mode variable name.
        :param valve_type_var_name: Runtime parameter storing the valve type code.
        :param gate_var_name: Runtime parameter storing the gate command.
        :param antiparallel_var_name: Runtime parameter enabling the reverse path.
        :param voltage_eps_var_name: Runtime parameter with the voltage deadband.
        :param current_eps_var_name: Runtime parameter with the current deadband.
        :param valve_voltage_var_name: Algebraic valve-voltage variable name.
        :param valve_current_var_name: Algebraic valve-current variable name.
        :param name: Logic entry name.
        :return: None.
        """
        super().__init__(name=name)
        self.mode_var_name = mode_var_name
        self.valve_type_var_name = valve_type_var_name
        self.gate_var_name = gate_var_name
        self.antiparallel_var_name = antiparallel_var_name
        self.voltage_eps_var_name = voltage_eps_var_name
        self.current_eps_var_name = current_eps_var_name
        self.valve_voltage_var_name = valve_voltage_var_name
        self.valve_current_var_name = valve_current_var_name
        self.mode_idx = -1
        self.valve_type_idx = -1
        self.gate_idx = -1
        self.antiparallel_idx = -1
        self.voltage_eps_idx = -1
        self.current_eps_idx = -1
        self.valve_voltage_idx = -1
        self.valve_current_idx = -1

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve the runtime and algebraic indices required by the valve logic.

        :param problem: Bound EMT problem.
        :return: None.
        """
        mode_var: Var
        valve_type_var: Var
        gate_var: Var
        antiparallel_var: Var
        voltage_eps_var: Var
        current_eps_var: Var
        valve_voltage_var: Var
        valve_current_var: Var

        super().bind(problem)
        mode_var = _find_var_by_name(problem.sys_block, self.mode_var_name)
        valve_type_var = _find_var_by_name(problem.sys_block, self.valve_type_var_name)
        gate_var = _find_var_by_name(problem.sys_block, self.gate_var_name)
        antiparallel_var = _find_var_by_name(problem.sys_block, self.antiparallel_var_name)
        voltage_eps_var = _find_var_by_name(problem.sys_block, self.voltage_eps_var_name)
        current_eps_var = _find_var_by_name(problem.sys_block, self.current_eps_var_name)
        valve_voltage_var = _find_var_by_name(problem.sys_block, self.valve_voltage_var_name)
        valve_current_var = _find_var_by_name(problem.sys_block, self.valve_current_var_name)

        self.mode_idx = int(problem.uid2idx_event_params[mode_var.uid])
        self.valve_type_idx = int(problem.uid2idx_event_params[valve_type_var.uid])
        self.gate_idx = int(problem.uid2idx_event_params[gate_var.uid])
        self.antiparallel_idx = int(problem.uid2idx_event_params[antiparallel_var.uid])
        self.voltage_eps_idx = int(problem.uid2idx_event_params[voltage_eps_var.uid])
        self.current_eps_idx = int(problem.uid2idx_event_params[current_eps_var.uid])
        self.valve_voltage_idx = int(problem.get_var_idx(valve_voltage_var))
        self.valve_current_idx = int(problem.get_var_idx(valve_current_var))

    def _get_mode_value(self, params: Vec) -> float:
        """
        Return the retained valve path mode stored in the runtime parameter vector.

        :param params: Runtime parameter vector.
        :return: Retained conduction-path mode.
        """
        return float(params[self.mode_idx])

    def _coerce_path_mode(self, raw_mode: float) -> float:
        """
        Quantize the retained path mode to ``-1``, ``0`` or ``+1``.

        :param raw_mode: Raw runtime value.
        :return: Quantized retained mode.
        """
        if raw_mode > 0.5:
            return 1.0
        else:
            pass

        if raw_mode < -0.5:
            return -1.0
        else:
            pass

        return 0.0

    def _compute_diode_mode(
            self,
            old_mode: float,
            valve_voltage: float,
            valve_current: float,
            antiparallel_enabled: bool,
            voltage_eps: float,
            current_eps: float,
    ) -> float:
        """
        Compute the retained path mode for a diode valve.

        :param old_mode: Previous retained path mode.
        :param valve_voltage: Accepted valve voltage.
        :param valve_current: Accepted valve current.
        :param antiparallel_enabled: Reverse path enable flag.
        :param voltage_eps: Voltage deadband.
        :param current_eps: Current deadband.
        :return: Updated retained path mode.
        """
        if valve_voltage > voltage_eps:
            return 1.0
        else:
            pass

        if old_mode > 0.5 and valve_current > -current_eps:
            return 1.0
        else:
            pass

        if antiparallel_enabled:
            if valve_voltage < -voltage_eps:
                return -1.0
            else:
                pass

            if old_mode < -0.5 and valve_current < current_eps:
                return -1.0
            else:
                pass
        else:
            pass

        return 0.0

    def _compute_igbt_mode(
            self,
            old_mode: float,
            valve_voltage: float,
            valve_current: float,
            gate_fired: bool,
            antiparallel_enabled: bool,
            voltage_eps: float,
            current_eps: float,
    ) -> float:
        """
        Compute the retained path mode for an IGBT valve.

        :param old_mode: Previous retained path mode.
        :param valve_voltage: Accepted valve voltage.
        :param valve_current: Accepted valve current.
        :param gate_fired: Gate command.
        :param antiparallel_enabled: Reverse path enable flag.
        :param voltage_eps: Voltage deadband.
        :param current_eps: Current deadband.
        :return: Updated retained path mode.
        """
        if gate_fired:
            if valve_voltage > -voltage_eps:
                return 1.0
            else:
                pass

            if old_mode > 0.5 and valve_current > -current_eps:
                return 1.0
            else:
                pass
        else:
            pass

        if antiparallel_enabled:
            if valve_voltage < -voltage_eps:
                return -1.0
            else:
                pass

            if old_mode < -0.5 and valve_current < current_eps:
                return -1.0
            else:
                pass

            return 0.0
        else:
            return 0.0

    def _compute_thyristor_mode(
            self,
            old_mode: float,
            valve_voltage: float,
            valve_current: float,
            gate_fired: bool,
            antiparallel_enabled: bool,
            voltage_eps: float,
            current_eps: float,
    ) -> float:
        """
        Compute the retained path mode for a thyristor valve.

        :param old_mode: Previous retained path mode.
        :param valve_voltage: Accepted valve voltage.
        :param valve_current: Accepted valve current.
        :param gate_fired: Gate command.
        :param antiparallel_enabled: Reverse path enable flag.
        :param voltage_eps: Voltage deadband.
        :param current_eps: Current deadband.
        :return: Updated retained path mode.
        """
        if old_mode > 0.5:
            if valve_current > current_eps and valve_voltage > -voltage_eps:
                return 1.0
            else:
                pass
        else:
            pass

        if gate_fired and valve_voltage > -voltage_eps:
            return 1.0
        else:
            pass

        if antiparallel_enabled:
            if valve_voltage < -voltage_eps:
                return -1.0
            else:
                pass

            if old_mode < -0.5 and valve_current < current_eps:
                return -1.0
            else:
                pass

            return 0.0
        else:
            return 0.0

    def _compute_path_mode(
            self,
            old_mode: float,
            valve_type_code: float,
            valve_voltage: float,
            valve_current: float,
            gate_fired: bool,
            antiparallel_enabled: bool,
            voltage_eps: float,
            current_eps: float,
    ) -> float:
        """
        Compute the updated retained conduction-path mode.

        :param old_mode: Previous retained path mode.
        :param valve_type_code: Runtime code describing the valve type.
        :param valve_voltage: Accepted valve voltage.
        :param valve_current: Accepted valve current.
        :param gate_fired: Gate command.
        :param antiparallel_enabled: Reverse path enable flag.
        :param voltage_eps: Voltage deadband.
        :param current_eps: Current deadband.
        :return: Updated retained path mode.
        """
        if valve_type_code < 0.5:
            return self._compute_diode_mode(
                old_mode=old_mode,
                valve_voltage=valve_voltage,
                valve_current=valve_current,
                antiparallel_enabled=antiparallel_enabled,
                voltage_eps=voltage_eps,
                current_eps=current_eps,
            )
        else:
            pass

        if valve_type_code < 1.5:
            return self._compute_igbt_mode(
                old_mode=old_mode,
                valve_voltage=valve_voltage,
                valve_current=valve_current,
                gate_fired=gate_fired,
                antiparallel_enabled=antiparallel_enabled,
                voltage_eps=voltage_eps,
                current_eps=current_eps,
            )
        else:
            pass

        return self._compute_thyristor_mode(
            old_mode=old_mode,
            valve_voltage=valve_voltage,
            valve_current=valve_current,
            gate_fired=gate_fired,
            antiparallel_enabled=antiparallel_enabled,
            voltage_eps=voltage_eps,
            current_eps=current_eps,
        )

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Update the retained conduction-path mode from the accepted EMT state.

        :param t: Current solver time.
        :param x: Accepted EMT state vector.
        :param params: Flat runtime parameter vector.
        :return: None.
        """
        old_mode: float
        valve_type_code: float
        gate_fired: bool
        antiparallel_enabled: bool
        voltage_eps: float
        current_eps: float
        valve_voltage: float
        valve_current: float
        new_mode: float

        _unused_t: float = float(t)
        old_mode = self._coerce_path_mode(self._get_mode_value(params))
        valve_type_code = float(params[self.valve_type_idx])
        gate_fired = float(params[self.gate_idx]) > 0.5
        antiparallel_enabled = float(params[self.antiparallel_idx]) > 0.5
        voltage_eps = abs(float(params[self.voltage_eps_idx]))
        current_eps = abs(float(params[self.current_eps_idx]))
        valve_voltage = float(x[self.valve_voltage_idx])
        valve_current = float(x[self.valve_current_idx])

        # The conduction mode depends on the accepted electrical state and the retained latch history.
        new_mode = self._compute_path_mode(
            old_mode=old_mode,
            valve_type_code=valve_type_code,
            valve_voltage=valve_voltage,
            valve_current=valve_current,
            gate_fired=gate_fired,
            antiparallel_enabled=antiparallel_enabled,
            voltage_eps=voltage_eps,
            current_eps=current_eps,
        )
        params[self.mode_idx] = new_mode

    def remap(self, var_mapping: VarRemap) -> "ValveStateLogic":
        """
        Clone the valve logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped valve logic.
        """
        name_mapping: Dict[str, str] = _build_name_mapping(var_mapping)
        return ValveStateLogic(
            mode_var_name=name_mapping.get(self.mode_var_name, self.mode_var_name),
            valve_type_var_name=name_mapping.get(self.valve_type_var_name, self.valve_type_var_name),
            gate_var_name=name_mapping.get(self.gate_var_name, self.gate_var_name),
            antiparallel_var_name=name_mapping.get(self.antiparallel_var_name, self.antiparallel_var_name),
            voltage_eps_var_name=name_mapping.get(self.voltage_eps_var_name, self.voltage_eps_var_name),
            current_eps_var_name=name_mapping.get(self.current_eps_var_name, self.current_eps_var_name),
            valve_voltage_var_name=name_mapping.get(self.valve_voltage_var_name, self.valve_voltage_var_name),
            valve_current_var_name=name_mapping.get(self.valve_current_var_name, self.valve_current_var_name),
            name=self.name,
        )


class ThreePhaseCarrierPwmLogic(ProceduralLogicBase):
    """
    Regularly sampled three-phase carrier PWM logic.

    The logic samples the modulation references at each carrier half-period,
    computes the exact gate transitions inside that interval, and stores the gate
    values as retained runtime modes. The symbolic DAE therefore sees piecewise
    constant gate parameters instead of symbolic comparator expressions.
    """

    __slots__ = [
        "mod_a_var_name",
        "mod_b_var_name",
        "mod_c_var_name",
        "gate_a_mode_var_name",
        "gate_b_mode_var_name",
        "gate_c_mode_var_name",
        "omega_sw_var_name",
        "carrier_phase_var_name",
        "mod_a_idx",
        "mod_b_idx",
        "mod_c_idx",
        "gate_a_idx",
        "gate_b_idx",
        "gate_c_idx",
        "omega_sw_idx",
        "carrier_phase_idx",
        "last_omega_sw",
        "initialized",
        "interval_end_time",
        "pending_transition_time",
        "pending_transition_gate",
        "current_gate",
    ]
    logic_tpe = ProceduralLogicType.ThreePhaseCarrierPwm

    def __init__(
            self,
            mod_a_var_name: str,
            mod_b_var_name: str,
            mod_c_var_name: str,
            gate_a_mode_var_name: str,
            gate_b_mode_var_name: str,
            gate_c_mode_var_name: str,
            omega_sw_var_name: str,
            carrier_phase_var_name: str,
            name: str = "",
    ) -> None:
        """
        Build one three-phase PWM logic entry.

        :param mod_a_var_name: Phase-A modulation variable name.
        :param mod_b_var_name: Phase-B modulation variable name.
        :param mod_c_var_name: Phase-C modulation variable name.
        :param gate_a_mode_var_name: Retained phase-A gate mode name.
        :param gate_b_mode_var_name: Retained phase-B gate mode name.
        :param gate_c_mode_var_name: Retained phase-C gate mode name.
        :param omega_sw_var_name: Switching angular-frequency parameter name.
        :param carrier_phase_var_name: Carrier phase-shift parameter name.
        :param name: Logic entry name.
        :return: None.
        """
        super().__init__(name=name)
        self.mod_a_var_name = mod_a_var_name
        self.mod_b_var_name = mod_b_var_name
        self.mod_c_var_name = mod_c_var_name
        self.gate_a_mode_var_name = gate_a_mode_var_name
        self.gate_b_mode_var_name = gate_b_mode_var_name
        self.gate_c_mode_var_name = gate_c_mode_var_name
        self.omega_sw_var_name = omega_sw_var_name
        self.carrier_phase_var_name = carrier_phase_var_name

        self.mod_a_idx = -1
        self.mod_b_idx = -1
        self.mod_c_idx = -1
        self.gate_a_idx = -1
        self.gate_b_idx = -1
        self.gate_c_idx = -1
        self.omega_sw_idx = -1
        self.carrier_phase_idx = -1
        self.last_omega_sw: float | None = None

        self.initialized = False
        self.interval_end_time: Optional[float] = None
        self.pending_transition_time = np.full(3, np.nan, dtype=float)
        self.pending_transition_gate = np.zeros(3, dtype=float)
        self.current_gate = np.zeros(3, dtype=float)

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve the variable indices and initialize the first PWM interval.

        :param problem: Bound EMT problem.
        :return: None.
        """
        mod_a_var: Var
        mod_b_var: Var
        mod_c_var: Var
        gate_a_var: Var
        gate_b_var: Var
        gate_c_var: Var
        omega_sw_var: Var
        carrier_phase_var: Var | None
        x0: Vec
        params0: Vec

        super().bind(problem)
        mod_a_var = _find_var_by_name(problem.sys_block, self.mod_a_var_name)
        mod_b_var = _find_var_by_name(problem.sys_block, self.mod_b_var_name)
        mod_c_var = _find_var_by_name(problem.sys_block, self.mod_c_var_name)
        gate_a_var = _find_var_by_name(problem.sys_block, self.gate_a_mode_var_name)
        gate_b_var = _find_var_by_name(problem.sys_block, self.gate_b_mode_var_name)
        gate_c_var = _find_var_by_name(problem.sys_block, self.gate_c_mode_var_name)
        omega_sw_var = _find_var_by_name(problem.sys_block, self.omega_sw_var_name)
        carrier_phase_var = _find_var_by_name_optional(problem.sys_block, self.carrier_phase_var_name)

        self.mod_a_idx = int(problem.get_var_idx(mod_a_var))
        self.mod_b_idx = int(problem.get_var_idx(mod_b_var))
        self.mod_c_idx = int(problem.get_var_idx(mod_c_var))
        self.gate_a_idx = int(problem.uid2idx_event_params[gate_a_var.uid])
        self.gate_b_idx = int(problem.uid2idx_event_params[gate_b_var.uid])
        self.gate_c_idx = int(problem.uid2idx_event_params[gate_c_var.uid])
        self.omega_sw_idx = int(problem.uid2idx_event_params[omega_sw_var.uid])

        if carrier_phase_var is None:
            self.carrier_phase_idx = -1
        else:
            self.carrier_phase_idx = int(problem.uid2idx_event_params[carrier_phase_var.uid])

        x0 = problem.get_x0().copy()
        params0 = problem.event_params_values

        # Binding initializes the retained gates so the very first EMT step starts from a consistent PWM state.
        self._rebuild_interval_schedule(sample_time=0.0, x=x0, params=params0)
        self._write_gate_modes(params0)
        self.initialized = True

    def _get_half_period(self, params: Vec) -> float:
        """
        Return the PWM carrier half-period.

        :param params: Runtime parameter vector.
        :return: Carrier half-period.
        """
        omega_sw: float = abs(float(params[self.omega_sw_idx]))

        if omega_sw > 1.0e-12:
            return float(np.pi / omega_sw)
        else:
            return 1.0e12

    def _get_interval_descriptor(self, sample_time: float, params: Vec) -> Tuple[float, bool]:
        """
        Return the end time and slope direction of the current carrier interval.

        :param sample_time: Accepted sample time.
        :param params: Runtime parameter vector.
        :return: Tuple ``(interval_end_time, carrier_rising)``.
        """
        omega_sw: float = float(params[self.omega_sw_idx])
        carrier_phase: float
        shifted_phase: float
        interval_index: int
        interval_start_time: float
        interval_end_time: float
        carrier_rising: bool
        half_period: float

        if abs(omega_sw) <= 1.0e-12:
            interval_end_time = sample_time + 1.0e12
            carrier_rising = True
        else:
            if self.carrier_phase_idx >= 0:
                carrier_phase = float(params[self.carrier_phase_idx])
            else:
                carrier_phase = 0.0

            half_period = self._get_half_period(params)
            shifted_phase = omega_sw * sample_time + carrier_phase + 0.5 * np.pi
            interval_index = int(math.floor(shifted_phase / np.pi))
            interval_start_time = (float(interval_index) * np.pi - carrier_phase - 0.5 * np.pi) / omega_sw
            interval_end_time = interval_start_time + half_period

            if interval_index % 2 == 0:
                carrier_rising = True
            else:
                carrier_rising = False

        return float(interval_end_time), carrier_rising

    def _read_modulation_values(self, x: Vec) -> np.ndarray:
        """
        Return the accepted per-phase modulation references.

        :param x: Accepted EMT state vector.
        :return: Three-phase modulation reference vector.
        """
        modulation_values: np.ndarray = np.zeros(3, dtype=float)
        modulation_values[0] = float(x[self.mod_a_idx])
        modulation_values[1] = float(x[self.mod_b_idx])
        modulation_values[2] = float(x[self.mod_c_idx])
        return modulation_values

    def _compute_phase_schedule(
            self,
            sample_time: float,
            interval_start_time: float,
            interval_end_time: float,
            carrier_rising: bool,
            modulation_value: float,
    ) -> Tuple[float, float, float]:
        """
        Compute the current gate and the next transition of one phase.

        :param sample_time: Accepted sample time.
        :param interval_start_time: Start time of the carrier interval.
        :param interval_end_time: End time of the carrier interval.
        :param carrier_rising: ``True`` when the carrier is rising in this interval.
        :param modulation_value: Held modulation reference.
        :return: Tuple ``(gate_now, transition_time_or_nan, gate_after_transition)``.
        """
        tol: float = 1.0e-12
        clipped_value: float
        transition_time: float
        gate_now: float
        gate_after: float
        interval_width: float = interval_end_time - interval_start_time

        if modulation_value > 1.0:
            clipped_value = 1.0
        else:
            if modulation_value < -1.0:
                clipped_value = -1.0
            else:
                clipped_value = modulation_value

        if carrier_rising:
            if clipped_value <= -1.0 + tol:
                gate_now = 0.0
                transition_time = np.nan
                gate_after = 0.0
            else:
                if clipped_value >= 1.0 - tol:
                    gate_now = 1.0
                    transition_time = np.nan
                    gate_after = 1.0
                else:
                    transition_time = interval_start_time + 0.5 * (clipped_value + 1.0) * interval_width
                    gate_after = 0.0
                    if sample_time < transition_time - tol:
                        gate_now = 1.0
                    else:
                        gate_now = 0.0
                        transition_time = np.nan
        else:
            if clipped_value <= -1.0 + tol:
                gate_now = 0.0
                transition_time = np.nan
                gate_after = 0.0
            else:
                if clipped_value >= 1.0 - tol:
                    gate_now = 1.0
                    transition_time = np.nan
                    gate_after = 1.0
                else:
                    transition_time = interval_start_time + 0.5 * (1.0 - clipped_value) * interval_width
                    gate_after = 1.0
                    if sample_time < transition_time - tol:
                        gate_now = 0.0
                    else:
                        gate_now = 1.0
                        transition_time = np.nan

        return gate_now, transition_time, gate_after

    def _write_gate_modes(self, params: Vec) -> None:
        """
        Store the retained gate values into the runtime parameter vector.

        :param params: Runtime parameter vector.
        :return: None.
        """
        params[self.gate_a_idx] = self.current_gate[0]
        params[self.gate_b_idx] = self.current_gate[1]
        params[self.gate_c_idx] = self.current_gate[2]

    def _rebuild_interval_schedule(self, sample_time: float, x: Vec, params: Vec) -> None:
        """
        Recompute the PWM switching schedule for the current carrier interval.

        :param sample_time: Accepted sample time.
        :param x: Accepted EMT state vector.
        :param params: Runtime parameter vector.
        :return: None.
        """
        interval_end_time: float
        carrier_rising: bool
        interval_start_time: float
        modulation_values: np.ndarray
        phase_idx: int
        gate_now: float
        transition_time: float
        gate_after: float
        half_period: float

        interval_end_time, carrier_rising = self._get_interval_descriptor(sample_time, params)
        self.last_omega_sw = float(params[self.omega_sw_idx])
        half_period = self._get_half_period(params)
        interval_start_time = interval_end_time - half_period
        modulation_values = self._read_modulation_values(x)

        self.interval_end_time = float(interval_end_time)
        self.pending_transition_time.fill(np.nan)

        phase_idx = 0
        while phase_idx < 3:
            gate_now, transition_time, gate_after = self._compute_phase_schedule(
                sample_time=sample_time,
                interval_start_time=interval_start_time,
                interval_end_time=interval_end_time,
                carrier_rising=carrier_rising,
                modulation_value=float(modulation_values[phase_idx]),
            )
            self.current_gate[phase_idx] = gate_now
            self.pending_transition_time[phase_idx] = transition_time
            self.pending_transition_gate[phase_idx] = gate_after
            phase_idx += 1

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the next PWM gate transition or carrier-boundary event.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest event in the interval, if any.
        """
        candidates: List[float] = list()
        transition_idx: int = 0

        super().get_next_forced_event_time(t_prev, t_target)

        if self.interval_end_time is not None and t_prev < self.interval_end_time <= t_target:
            candidates.append(float(self.interval_end_time))
        else:
            pass

        while transition_idx < 3:
            transition_time: float = float(self.pending_transition_time[transition_idx])
            if not np.isnan(transition_time) and t_prev < transition_time <= t_target:
                candidates.append(transition_time)
            else:
                pass
            transition_idx += 1

        if len(candidates) == 0:
            return None
        else:
            return min(candidates)

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Advance the PWM gate states from the accepted modulation references.

        :param t: Current solver time.
        :param x: Accepted EMT state vector.
        :param params: Runtime parameter vector.
        :return: None.
        """
        tol: float = 1.0e-12
        # ``x`` intentionally belongs to the previous accepted state, but gate
        # scheduling belongs to the boundary currently being prepared.  Using
        # the previous accepted time here delays every forced PWM transition to
        # the following solver step and defeats exact event alignment.
        sample_time: float = float(t)
        omega_sw_now: float = float(params[self.omega_sw_idx])
        transition_idx: int = 0

        if not self.initialized:
            self._rebuild_interval_schedule(sample_time=sample_time, x=x, params=params)
            self.initialized = True
        else:
            if self.last_omega_sw is None or abs(omega_sw_now - self.last_omega_sw) > tol:
                # Hybrid converter startup can change the effective carrier frequency from
                # zero to its nominal value.  A zero-frequency schedule has an effectively
                # infinite interval end, so it must be discarded immediately when the
                # runtime frequency changes.
                self._rebuild_interval_schedule(sample_time=sample_time, x=x, params=params)
            elif self.interval_end_time is not None and sample_time >= self.interval_end_time - tol:
                # A new carrier interval starts here, so the phase schedules are rebuilt from fresh modulation samples.
                self._rebuild_interval_schedule(sample_time=sample_time, x=x, params=params)
            else:
                while transition_idx < 3:
                    transition_time: float = float(self.pending_transition_time[transition_idx])
                    if not np.isnan(transition_time) and sample_time >= transition_time - tol:
                        # Inside the current interval, only the already scheduled edge flips the gate state.
                        self.current_gate[transition_idx] = self.pending_transition_gate[transition_idx]
                        self.pending_transition_time[transition_idx] = np.nan
                    else:
                        pass
                    transition_idx += 1

        self._write_gate_modes(params)

    def remap(self, var_mapping: VarRemap) -> "ThreePhaseCarrierPwmLogic":
        """
        Clone the PWM logic under a variable remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped PWM logic.
        """
        name_mapping: Dict[str, str] = _build_name_mapping(var_mapping)
        return ThreePhaseCarrierPwmLogic(
            mod_a_var_name=name_mapping.get(self.mod_a_var_name, self.mod_a_var_name),
            mod_b_var_name=name_mapping.get(self.mod_b_var_name, self.mod_b_var_name),
            mod_c_var_name=name_mapping.get(self.mod_c_var_name, self.mod_c_var_name),
            gate_a_mode_var_name=name_mapping.get(self.gate_a_mode_var_name, self.gate_a_mode_var_name),
            gate_b_mode_var_name=name_mapping.get(self.gate_b_mode_var_name, self.gate_b_mode_var_name),
            gate_c_mode_var_name=name_mapping.get(self.gate_c_mode_var_name, self.gate_c_mode_var_name),
            omega_sw_var_name=name_mapping.get(self.omega_sw_var_name, self.omega_sw_var_name),
            carrier_phase_var_name=name_mapping.get(self.carrier_phase_var_name, self.carrier_phase_var_name),
            name=self.name,
        )


class ThreePhaseCarrierSampledModulationLogic(ProceduralLogicBase):
    """
    Regular-sampled three-phase modulation holder using carrier half-period boundaries.

    The sampling instants intentionally follow ``ThreePhaseCarrierPwmLogic`` so a symbolic soft
    comparator can consume the same held ``m_a/m_b/m_c`` values as the procedural PWM scheduler.
    """

    __slots__ = [
        "mod_a_var_name",
        "mod_b_var_name",
        "mod_c_var_name",
        "sample_a_mode_var_name",
        "sample_b_mode_var_name",
        "sample_c_mode_var_name",
        "omega_sw_var_name",
        "carrier_phase_var_name",
        "mod_a_idx",
        "mod_b_idx",
        "mod_c_idx",
        "sample_a_idx",
        "sample_b_idx",
        "sample_c_idx",
        "omega_sw_idx",
        "carrier_phase_idx",
        "initialized",
        "interval_end_time",
    ]
    logic_tpe = ProceduralLogicType.ThreePhaseCarrierSampledModulation

    def __init__(
            self,
            mod_a_var_name: str,
            mod_b_var_name: str,
            mod_c_var_name: str,
            sample_a_mode_var_name: str,
            sample_b_mode_var_name: str,
            sample_c_mode_var_name: str,
            omega_sw_var_name: str,
            carrier_phase_var_name: str,
            name: str = "",
    ) -> None:
        """
        Build one carrier-synchronized three-phase sampled modulation holder.

        :param mod_a_var_name: Phase-A source modulation variable name.
        :param mod_b_var_name: Phase-B source modulation variable name.
        :param mod_c_var_name: Phase-C source modulation variable name.
        :param sample_a_mode_var_name: Retained phase-A sampled modulation mode name.
        :param sample_b_mode_var_name: Retained phase-B sampled modulation mode name.
        :param sample_c_mode_var_name: Retained phase-C sampled modulation mode name.
        :param omega_sw_var_name: Switching angular-frequency parameter name.
        :param carrier_phase_var_name: Carrier phase-shift parameter name.
        :param name: Logic entry name.
        :return: None.
        """
        super().__init__(name=name)
        self.mod_a_var_name = mod_a_var_name
        self.mod_b_var_name = mod_b_var_name
        self.mod_c_var_name = mod_c_var_name
        self.sample_a_mode_var_name = sample_a_mode_var_name
        self.sample_b_mode_var_name = sample_b_mode_var_name
        self.sample_c_mode_var_name = sample_c_mode_var_name
        self.omega_sw_var_name = omega_sw_var_name
        self.carrier_phase_var_name = carrier_phase_var_name
        self.mod_a_idx = -1
        self.mod_b_idx = -1
        self.mod_c_idx = -1
        self.sample_a_idx = -1
        self.sample_b_idx = -1
        self.sample_c_idx = -1
        self.omega_sw_idx = -1
        self.carrier_phase_idx = -1
        self.initialized = False
        self.interval_end_time = None

    def bind(self, problem: ProceduralProblem) -> None:
        """
        Resolve modulation, sampled-mode and carrier parameter indices.

        :param problem: Concrete EMT problem.
        :return: None.
        """
        mod_a_var: Var = _find_var_by_name(problem.sys_block, self.mod_a_var_name)
        mod_b_var: Var = _find_var_by_name(problem.sys_block, self.mod_b_var_name)
        mod_c_var: Var = _find_var_by_name(problem.sys_block, self.mod_c_var_name)
        sample_a_var: Var = _find_var_by_name(problem.sys_block, self.sample_a_mode_var_name)
        sample_b_var: Var = _find_var_by_name(problem.sys_block, self.sample_b_mode_var_name)
        sample_c_var: Var = _find_var_by_name(problem.sys_block, self.sample_c_mode_var_name)
        omega_sw_var: Var = _find_var_by_name(problem.sys_block, self.omega_sw_var_name)
        carrier_phase_var: Var | None = _find_var_by_name_optional(problem.sys_block, self.carrier_phase_var_name)

        super().bind(problem)
        self.mod_a_idx = int(problem.uid2idx_vars[mod_a_var.uid])
        self.mod_b_idx = int(problem.uid2idx_vars[mod_b_var.uid])
        self.mod_c_idx = int(problem.uid2idx_vars[mod_c_var.uid])
        self.sample_a_idx = int(problem.uid2idx_event_params[sample_a_var.uid])
        self.sample_b_idx = int(problem.uid2idx_event_params[sample_b_var.uid])
        self.sample_c_idx = int(problem.uid2idx_event_params[sample_c_var.uid])
        self.omega_sw_idx = int(problem.uid2idx_event_params[omega_sw_var.uid])
        if carrier_phase_var is None:
            self.carrier_phase_idx = -1
        else:
            self.carrier_phase_idx = int(problem.uid2idx_event_params[carrier_phase_var.uid])
        self.initialized = False
        self.interval_end_time = None

    def _get_half_period(self, params: Vec) -> float:
        """
        Return the carrier half-period from the retained switching angular frequency.

        :param params: Runtime parameter vector.
        :return: Carrier half-period in seconds.
        """
        omega_sw: float = abs(float(params[self.omega_sw_idx]))
        if omega_sw > 1.0e-12:
            return float(np.pi / omega_sw)
        else:
            return 1.0e12

    def _get_interval_end_time(self, sample_time: float, params: Vec) -> float:
        """
        Return the end time of the current carrier half-period interval.

        :param sample_time: Accepted sample time.
        :param params: Runtime parameter vector.
        :return: Current interval end time.
        """
        omega_sw: float = float(params[self.omega_sw_idx])
        carrier_phase: float
        shifted_phase: float
        interval_index: int
        interval_start_time: float

        if abs(omega_sw) <= 1.0e-12:
            return sample_time + 1.0e12
        else:
            if self.carrier_phase_idx >= 0:
                carrier_phase = float(params[self.carrier_phase_idx])
            else:
                carrier_phase = 0.0
            shifted_phase = omega_sw * sample_time + carrier_phase + 0.5 * np.pi
            interval_index = int(math.floor(shifted_phase / np.pi))
            interval_start_time = (float(interval_index) * np.pi - carrier_phase - 0.5 * np.pi) / omega_sw
            return float(interval_start_time + self._get_half_period(params))

    def _sample_modulation(self, x: Vec, params: Vec) -> None:
        """
        Store accepted modulation values into retained sampled runtime modes.

        :param x: Accepted EMT state vector.
        :param params: Runtime parameter vector to mutate.
        :return: None.
        """
        params[self.sample_a_idx] = float(x[self.mod_a_idx])
        params[self.sample_b_idx] = float(x[self.mod_b_idx])
        params[self.sample_c_idx] = float(x[self.mod_c_idx])

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Force a solver event at each carrier half-period boundary.

        :param t_prev: Previous accepted solver time.
        :param t_target: Nominal target time.
        :return: Next half-period boundary if it lies inside the step.
        """
        super().get_next_forced_event_time(t_prev, t_target)
        if self.interval_end_time is not None and t_prev < self.interval_end_time <= t_target:
            return float(self.interval_end_time)
        else:
            return None

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Sample modulation at initialization and at carrier half-period boundaries.

        :param t: Current solver time.
        :param x: Accepted EMT state vector.
        :param params: Runtime parameter vector to mutate.
        :return: None.
        """
        # The sampled values come from accepted ``x``; the interval clock must
        # nevertheless advance at the boundary currently being prepared.
        sample_time: float = float(t)
        if not self.initialized:
            self._sample_modulation(x=x, params=params)
            self.interval_end_time = self._get_interval_end_time(sample_time=sample_time, params=params)
            self.initialized = True
        else:
            if self.interval_end_time is not None and self.interval_end_time > 1.0e11 and abs(float(params[self.omega_sw_idx])) > 1.0e-12:
                self._sample_modulation(x=x, params=params)
                self.interval_end_time = self._get_interval_end_time(sample_time=sample_time, params=params)
            elif self.interval_end_time is not None and sample_time + 1.0e-12 >= self.interval_end_time:
                self._sample_modulation(x=x, params=params)
                self.interval_end_time = self._get_interval_end_time(sample_time=sample_time, params=params)
            else:
                pass

    def remap(self, var_mapping: VarRemap) -> "ThreePhaseCarrierSampledModulationLogic":
        """
        Clone this logic under a variable-name remapping.

        :param var_mapping: Variable substitution map.
        :return: Remapped sampled-modulation logic.
        """
        name_mapping: Dict[str, str] = _build_name_mapping(var_mapping)
        return ThreePhaseCarrierSampledModulationLogic(
            mod_a_var_name=name_mapping.get(self.mod_a_var_name, self.mod_a_var_name),
            mod_b_var_name=name_mapping.get(self.mod_b_var_name, self.mod_b_var_name),
            mod_c_var_name=name_mapping.get(self.mod_c_var_name, self.mod_c_var_name),
            sample_a_mode_var_name=name_mapping.get(self.sample_a_mode_var_name, self.sample_a_mode_var_name),
            sample_b_mode_var_name=name_mapping.get(self.sample_b_mode_var_name, self.sample_b_mode_var_name),
            sample_c_mode_var_name=name_mapping.get(self.sample_c_mode_var_name, self.sample_c_mode_var_name),
            omega_sw_var_name=name_mapping.get(self.omega_sw_var_name, self.omega_sw_var_name),
            carrier_phase_var_name=name_mapping.get(self.carrier_phase_var_name, self.carrier_phase_var_name),
            name=self.name,
        )


class IeeeCigreDllSignalBinding:
    """Stable connection between one ABI signal element and one symbolic variable."""

    __slots__ = ("is_input", "port_ordinal", "element_ordinal", "_variable")

    def __init__(self,
                 is_input: bool,
                 port_ordinal: int,
                 element_ordinal: int,
                 variable: Var) -> None:
        """Create one signal-element connection.

        :param is_input: ``True`` for an input port and ``False`` for an output port.
        :param port_ordinal: Zero-based stable port ordinal from ModelInfo.
        :param element_ordinal: Zero-based element ordinal inside the signal width.
        :param variable: Live symbolic variable connected to the ABI signal element.
        :return: None.
        """
        if not isinstance(variable, Var):
            raise TypeError("IEEE/CIGRE signal binding variable must be a Var")
        else:
            pass
        if port_ordinal < 0 or element_ordinal < 0:
            raise ValueError("IEEE/CIGRE signal binding ordinals must be nonnegative")
        else:
            pass
        self.is_input: bool = is_input
        self.port_ordinal: int = port_ordinal
        self.element_ordinal: int = element_ordinal
        self._variable: Var = variable

    def get_variable(self) -> Var:
        """Return the live variable connected to this ABI signal element.

        :return: Canonical symbolic variable owned by the controller block.
        """
        return self._variable


class IeeeCigreDllParameterOverride:
    """Typed per-instance override for one manufacturer parameter ordinal."""

    __slots__ = ("parameter_ordinal", "data_type", "fixed_value", "value")

    def __init__(self,
                 parameter_ordinal: int,
                 data_type: int,
                 fixed_value: bool,
                 value: int | float | str) -> None:
        """Create one typed parameter override.

        :param parameter_ordinal: Zero-based stable parameter ordinal.
        :param data_type: Exact official IEEE/CIGRE primitive type number.
        :param fixed_value: Exact manufacturer FixedValue declaration.
        :param value: Typed override value.
        :return: None.
        """
        if parameter_ordinal < 0 or data_type < 1 or data_type > 10:
            raise ValueError("IEEE/CIGRE parameter override ordinal or data type is invalid")
        else:
            pass
        if isinstance(value, str):
            encoded: bytes = value.encode("utf-8", errors="strict")
            if "\x00" in value or len(encoded) > 16 * 1024:
                raise ValueError("IEEE/CIGRE string override must be NUL-free and at most 16 KiB")
            else:
                pass
        else:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("IEEE/CIGRE numeric override must be finite")
                else:
                    pass
            else:
                raise TypeError("IEEE/CIGRE parameter override must be int, float or str")
        self.parameter_ordinal: int = parameter_ordinal
        self.data_type: int = data_type
        self.fixed_value: bool = fixed_value
        self.value: int | float | str = value


class ManufacturerNativeRebindPlan:
    """Transient, complete replacement plan for one consumer Block hierarchy."""

    __slots__ = (
        "consumer_idtag", "source_provider_idtag", "destination_provider_idtag",
        "source_model_info_sha256", "destination_model_info_sha256",
        "source_occurrence_fingerprints", "replacement_signal_records",
        "replacement_override_records",
    )

    def __init__(
            self,
            consumer_idtag: str,
            source_provider_idtag: str,
            destination_provider_idtag: str,
            source_model_info_sha256: str,
            destination_model_info_sha256: str,
            source_occurrence_fingerprints: Tuple[str, ...],
            replacement_signal_records: Tuple[
                Tuple[Tuple[bool, int, int, str, int], ...], ...
            ],
            replacement_override_records: Tuple[
                Tuple[Tuple[int, int, bool, int | float | str], ...], ...
            ],
    ) -> None:
        """Store an IO-validated plan without retaining decoded ModelInfo.

        :param consumer_idtag: Stable template identity to be rebound.
        :param source_provider_idtag: Current provider identity.
        :param destination_provider_idtag: Replacement provider identity.
        :param source_model_info_sha256: Current canonical metadata digest.
        :param destination_model_info_sha256: Replacement metadata digest.
        :param source_occurrence_fingerprints: Canonical precondition per occurrence.
        :param replacement_signal_records: Complete primitive signal replacements.
        :param replacement_override_records: Complete primitive override replacements.
        :return: None.
        """
        occurrence_count: int = len(source_occurrence_fingerprints)
        if (
                len(consumer_idtag) == 0
                or len(source_provider_idtag) == 0
                or len(destination_provider_idtag) == 0
                or occurrence_count == 0
        ):
            raise ValueError("Manufacturer native rebind plan identities are incomplete")
        else:
            pass
        if (
                len(source_model_info_sha256) != 64
                or len(destination_model_info_sha256) != 64
        ):
            raise ValueError("Manufacturer native rebind plan digests are invalid")
        else:
            pass
        if (
                len(replacement_signal_records) != occurrence_count
                or len(replacement_override_records) != occurrence_count
        ):
            raise ValueError("Manufacturer native rebind plan occurrence counts differ")
        else:
            pass
        self.consumer_idtag: str = consumer_idtag
        self.source_provider_idtag: str = source_provider_idtag
        self.destination_provider_idtag: str = destination_provider_idtag
        self.source_model_info_sha256: str = source_model_info_sha256.lower()
        self.destination_model_info_sha256: str = destination_model_info_sha256.lower()
        self.source_occurrence_fingerprints: Tuple[str, ...] = (
            source_occurrence_fingerprints
        )
        self.replacement_signal_records: Tuple[
            Tuple[Tuple[bool, int, int, str, int], ...], ...
        ] = replacement_signal_records
        self.replacement_override_records: Tuple[
            Tuple[Tuple[int, int, bool, int | float | str], ...], ...
        ] = replacement_override_records


class ManufacturerNativeControllerLogic(ProceduralLogicBase):
    """Declarative Block reference to one manufacturer native model provider."""

    __slots__ = ("provider_idtag", "model_info_sha256", "signal_bindings", "parameter_overrides")
    logic_tpe = ProceduralLogicType.ManufacturerNativeController

    def __init__(self,
                 provider_idtag: str,
                 model_info_sha256: str,
                 signal_bindings: Tuple[IeeeCigreDllSignalBinding, ...],
                 parameter_overrides: Tuple[IeeeCigreDllParameterOverride, ...],
                 name: str = "") -> None:
        """Create one provider binding without duplicating ModelInfo.

        :param provider_idtag: Stable provider identity owned by Assets.
        :param model_info_sha256: Expected canonical metadata digest.
        :param signal_bindings: Ordered signal-element graph connections.
        :param parameter_overrides: Ordered typed instance overrides.
        :param name: Optional display name.
        :return: None.
        """
        super().__init__(name=name)
        normalized_digest: str = model_info_sha256.lower()
        if len(provider_idtag) == 0:
            raise ValueError("Manufacturer native provider idtag cannot be empty")
        else:
            pass
        if len(normalized_digest) != 64 or any(char not in "0123456789abcdef" for char in normalized_digest):
            raise ValueError("Manufacturer native ModelInfo digest is invalid")
        else:
            pass
        self.provider_idtag: str = provider_idtag
        self.model_info_sha256: str = normalized_digest
        self.signal_bindings: Tuple[IeeeCigreDllSignalBinding, ...] = signal_bindings
        self.parameter_overrides: Tuple[IeeeCigreDllParameterOverride, ...] = parameter_overrides

    def to_data(self) -> ProceduralLogicData:
        """Serialize the provider binding as versioned declarative data.

        :return: Serialized provider binding without ModelInfo duplication.
        """
        signal_data: List[object] = list()
        signal_binding: IeeeCigreDllSignalBinding
        for signal_binding in self.signal_bindings:
            variable: Var = signal_binding.get_variable()
            signal_data.append([
                signal_binding.is_input,
                signal_binding.port_ordinal,
                signal_binding.element_ordinal,
                variable.name,
                variable.non_mutable_uid,
            ])
        override_data: List[object] = list()
        parameter_override: IeeeCigreDllParameterOverride
        for parameter_override in self.parameter_overrides:
            override_data.append([
                parameter_override.parameter_ordinal,
                parameter_override.data_type,
                parameter_override.fixed_value,
                parameter_override.value,
            ])
        return {
            "logic_type": self.logic_tpe.value,
            "name": self.name,
            "provider_idtag": self.provider_idtag,
            "model_info_sha256": self.model_info_sha256,
            "signal_bindings": signal_data,
            "parameter_overrides": override_data,
        }

    def remap(self, var_mapping: VarRemap) -> "ManufacturerNativeControllerLogic":
        """Clone the binding under the Block variable substitution map.

        :param var_mapping: Symbolic variable replacement map.
        :return: Remapped provider binding preserving provider identity and ordinals.
        """
        remapped_bindings: List[IeeeCigreDllSignalBinding] = list()
        binding: IeeeCigreDllSignalBinding
        for binding in self.signal_bindings:
            source_variable: Var = binding.get_variable()
            replacement_expr: Expr | None = var_mapping.get(source_variable, None)
            if isinstance(replacement_expr, Var):
                remapped_variable: Var = replacement_expr
            else:
                # A live binding already observes UID and name changes on the
                # same object. Only an explicit object replacement needs the
                # symbolic mapping; otherwise retain the canonical reference.
                remapped_variable = source_variable
            remapped_bindings.append(IeeeCigreDllSignalBinding(
                is_input=binding.is_input,
                port_ordinal=binding.port_ordinal,
                element_ordinal=binding.element_ordinal,
                variable=remapped_variable,
            ))
        return ManufacturerNativeControllerLogic(
            provider_idtag=self.provider_idtag,
            model_info_sha256=self.model_info_sha256,
            signal_bindings=tuple(remapped_bindings),
            parameter_overrides=self.parameter_overrides,
            name=self.name,
        )

    def remap_with_structural_vars(
            self,
            var_mapping: VarRemap,
            structural_var_mapping: Dict[int, Var],
    ) -> "ManufacturerNativeControllerLogic":
        """Clone native bindings through stable variable identities.

        :param var_mapping: Symbolic mapping retained for the common procedural contract.
        :param structural_var_mapping: Stable source identities mapped to cloned variables.
        :return: Remapped provider binding pointing to the cloned block variables.
        """
        _unused: VarRemap = var_mapping
        remapped_bindings: List[IeeeCigreDllSignalBinding] = list()
        binding: IeeeCigreDllSignalBinding
        for binding in self.signal_bindings:
            source_variable: Var = binding.get_variable()
            remapped_variable: Var | None = structural_var_mapping.get(
                source_variable.non_mutable_uid,
                None,
            )
            if remapped_variable is None:
                raise ValueError("IEEE/CIGRE signal binding lost its structural variable during remap")
            else:
                remapped_bindings.append(IeeeCigreDllSignalBinding(
                    is_input=binding.is_input,
                    port_ordinal=binding.port_ordinal,
                    element_ordinal=binding.element_ordinal,
                    variable=remapped_variable,
                ))
        return ManufacturerNativeControllerLogic(
            provider_idtag=self.provider_idtag,
            model_info_sha256=self.model_info_sha256,
            signal_bindings=tuple(remapped_bindings),
            parameter_overrides=self.parameter_overrides,
            name=self.name,
        )

class BlockProceduralLogicUpdater(BoundaryUpdateWrapper):
    """
    Boundary updater that delegates runtime decisions to block-attached procedural logic entries.
    """

    __slots__ = ["problem", "logic_entries", "runtime_session", "model_mode", "runtime_initialized"]

    def __init__(self,
                 problem: ProceduralProblem,
                 logic_entries: List[ProceduralLogicBase],
                 runtime_session: ManufacturerNativeRuntimeSessionProtocol | None = None,
                 model_mode: int | None = None) -> None:
        """
        Bind all procedural logic entries to one EMT problem.

        :param problem: Bound EMT problem.
        :param logic_entries: Procedural logic entries attached to the root block.
        :param runtime_session: Optional driver-owned manufacturer-native session.
        :param model_mode: Exact IEEE/CIGRE RMS or EMT mode number.
        :return: None
        """
        self.problem: ProceduralProblem = problem
        self.logic_entries: List[ProceduralLogicBase] = logic_entries
        self.runtime_session: ManufacturerNativeRuntimeSessionProtocol | None = runtime_session
        self.model_mode: int | None = model_mode
        self.runtime_initialized: bool = False
        if self.runtime_session is not None:
            if self.model_mode is None:
                raise ValueError("Native runtime session requires an exact model mode")
            else:
                self.runtime_session.preflight(problem, self.logic_entries, self.model_mode)
        else:
            pass
        for logic in self.logic_entries:
            logic.bind(problem)

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Forward one runtime update to all procedural logic entries.

        :param t: Current solver time.
        :param x: Accepted state vector.
        :param params: Runtime parameter vector.
        :return: None
        """
        for logic in self.logic_entries:
            if isinstance(logic, ManufacturerNativeControllerLogic):
                pass
            else:
                logic.update(t, x, params)
        if self.runtime_session is not None and not self.runtime_initialized:
            if abs(float(t)) <= 1e-12:
                self.runtime_session.initialize(float(t), x, params)
                self.runtime_initialized = True
            else:
                raise RuntimeError("Native runtime must initialize from the t=0 operating-point guess")
        else:
            pass

    def initialize_modes(self, t: float, x: Vec, params: Vec) -> None:
        """
        Initialize retained procedural mode outputs at startup.

        The generic EMT runtime-parameter initialization seeds ``mode_dict``
        values before the procedural layer is active. For procedural outputs such
        as sampled values and saturations, the correct startup value is the
        value produced by the procedural logic itself when evaluated at the
        initialized operating point. This startup pass applies the same update
        logic once after the continuous initialization has populated the state,
        algebraic, and differential guesses, so retained mode outputs start from
        the exact operating-point sample that the runtime layer will hold.

        :param t: Startup simulation time.
        :param x: Initialized state/algebraic vector.
        :param params: Runtime parameter vector updated in place.
        :return: None
        """
        logic: ProceduralLogicBase

        # Reuse each logic object's update rule so startup mode seeding matches
        # the runtime semantics of that procedural block exactly.
        for logic in self.logic_entries:
            logic.update(t, x, params)

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the earliest forced event requested by any procedural logic entry.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest event in the interval, if any.
        """
        candidates: List[float] = list()
        for logic in self.logic_entries:
            candidate = logic.get_next_forced_event_time(t_prev, t_target)
            if candidate is not None:
                candidates.append(candidate)
        if self.runtime_session is not None:
            native_candidate: float | None = self.runtime_session.get_next_sample_time(t_prev, t_target)
            if native_candidate is not None:
                candidates.append(native_candidate)
            else:
                pass
        else:
            pass
        if len(candidates) == 0:
            return None
        else:
            return min(candidates)

    def commit_boundary(self, t: float, x: Vec, params: Vec) -> None:
        """Commit due manufacturer controllers after an accepted network step.

        :param t: Accepted solver boundary.
        :param x: Accepted network state.
        :param params: Mutable runtime parameter vector.
        :return: None.
        """
        if self.runtime_session is not None:
            self.runtime_session.commit_boundary(t, x, params)
        else:
            pass

    def close(self) -> None:
        """Release the driver-owned native session through its single owner.

        :return: None.
        """
        if self.runtime_session is not None:
            self.runtime_session.close()
            self.runtime_session = None
        else:
            pass


def _base_logic_data(entry: ProceduralLogicBase) -> ProceduralLogicData:
    """
    Serialize the common metadata shared by all procedural logic entries.

    :param entry: Procedural logic entry.
    :return: Serialized common metadata.
    """
    return {
        "logic_type": entry.logic_tpe.value,
        "name": entry.name,
    }


def procedural_logic_entry_to_dict(entry: ProceduralLogicBase) -> ProceduralLogicData:
    """
    Serialize one procedural logic entry.

    :param entry: Procedural logic entry.
    :return: Serialized logic dictionary.
    """
    data: ProceduralLogicData = _base_logic_data(entry)

    if isinstance(entry, ManufacturerNativeControllerLogic):
        return entry.to_data()
    elif isinstance(entry, ConditionalDiagnosticLogic):
        data.update({
            "condition_expr": _expr_like_to_dict(entry.condition_expr),
            "message": entry.message,
            "initialization_only": entry.initialization_only,
        })
        return data
    elif isinstance(entry, DelayedSwitchEventLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "guard_expr": _expr_like_to_dict(entry.guard_expr),
            "trigger_expr": _expr_like_to_dict(entry.trigger_expr),
            "delay_expr": _expr_like_to_dict(entry.delay_expr),
            "target_device_idtag": entry.target_device_idtag,
            "target_switch_idtag": entry.target_switch_idtag,
            "target_terminal_index": entry.target_terminal_index,
            "initial_closed": entry.initial_closed,
            "command_closed": entry.command_closed,
        })
        return data
    elif isinstance(entry, FixedSampleLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "condition_expr": _expr_like_to_dict(entry.condition_expr),
        })
        return data
    elif isinstance(entry, SampledValueLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "output_var_uid": entry.output_var_uid,
            "source_expr": _expr_like_to_dict(entry.source_expr),
        })
        return data
    elif isinstance(entry, HardSaturationLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "u_expr": _expr_like_to_dict(entry.u_expr),
            "u_min_expr": _expr_like_to_dict(entry.u_min_expr),
            "u_max_expr": _expr_like_to_dict(entry.u_max_expr),
        })
        return data
    elif isinstance(entry, TimeDelayLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "source_expr": _expr_like_to_dict(entry.source_expr),
            "delay_expr": _expr_like_to_dict(entry.delay_expr),
        })
        return data
    elif isinstance(entry, MovingAverageLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "source_expr": _expr_like_to_dict(entry.source_expr),
            "delay_expr": _expr_like_to_dict(entry.delay_expr),
            "window_expr": _expr_like_to_dict(entry.window_expr),
        })
        return data
    elif isinstance(entry, GradientLimiterLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "source_expr": _expr_like_to_dict(entry.source_expr),
            "lower_rate_expr": _expr_like_to_dict(entry.lower_rate_expr),
            "upper_rate_expr": _expr_like_to_dict(entry.upper_rate_expr),
        })
        return data
    elif isinstance(entry, FlipFlopLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "set_expr": _expr_like_to_dict(entry.set_expr),
            "reset_expr": _expr_like_to_dict(entry.reset_expr),
        })
        return data
    elif isinstance(entry, AnalogFlipFlopLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "input_expr": _expr_like_to_dict(entry.input_expr),
            "set_expr": _expr_like_to_dict(entry.set_expr),
            "reset_expr": _expr_like_to_dict(entry.reset_expr),
        })
        return data
    elif isinstance(entry, PickupDropoffLogic):
        data.update({
            "output_var_name": entry.output_var_name,
            "output_var_uid": entry.output_var_uid,
            "bool_expr": _expr_like_to_dict(entry.bool_expr),
            "pickup_delay_expr": _expr_like_to_dict(entry.pickup_delay_expr),
            "drop_delay_expr": _expr_like_to_dict(entry.drop_delay_expr),
        })
        return data
    elif isinstance(entry, ResetOnRisingEdgeLogic):
        data.update({
            "target_var_name": entry.target_var_name,
            "reset_expr": _expr_like_to_dict(entry.reset_expr),
            "value_expr": _expr_like_to_dict(entry.value_expr),
        })
        return data
    elif isinstance(entry, DelayedThresholdLatchLogic):
        data.update({
            "monitored_var_name": entry.monitored_var_name,
            "mode_var_name": entry.mode_var_name,
            "threshold": entry.threshold,
            "delay": entry.delay,
            "reset_delay": entry.reset_delay,
        })
        return data
    elif isinstance(entry, StartupHandoverLogic):
        data.update({
            "mode_var_name": entry.mode_var_name,
            "enable_time_var_name": entry.enable_time_var_name,
            "on_value_var_name": entry.on_value_var_name,
        })
        return data
    elif isinstance(entry, ValveStateLogic):
        data.update({
            "mode_var_name": entry.mode_var_name,
            "valve_type_var_name": entry.valve_type_var_name,
            "gate_var_name": entry.gate_var_name,
            "antiparallel_var_name": entry.antiparallel_var_name,
            "voltage_eps_var_name": entry.voltage_eps_var_name,
            "current_eps_var_name": entry.current_eps_var_name,
            "valve_voltage_var_name": entry.valve_voltage_var_name,
            "valve_current_var_name": entry.valve_current_var_name,
        })
        return data
    elif isinstance(entry, ThreePhaseCarrierPwmLogic):
        data.update({
            "mod_a_var_name": entry.mod_a_var_name,
            "mod_b_var_name": entry.mod_b_var_name,
            "mod_c_var_name": entry.mod_c_var_name,
            "gate_a_mode_var_name": entry.gate_a_mode_var_name,
            "gate_b_mode_var_name": entry.gate_b_mode_var_name,
            "gate_c_mode_var_name": entry.gate_c_mode_var_name,
            "omega_sw_var_name": entry.omega_sw_var_name,
            "carrier_phase_var_name": entry.carrier_phase_var_name,
        })
        return data
    elif isinstance(entry, ThreePhaseCarrierSampledModulationLogic):
        data.update({
            "mod_a_var_name": entry.mod_a_var_name,
            "mod_b_var_name": entry.mod_b_var_name,
            "mod_c_var_name": entry.mod_c_var_name,
            "sample_a_mode_var_name": entry.sample_a_mode_var_name,
            "sample_b_mode_var_name": entry.sample_b_mode_var_name,
            "sample_c_mode_var_name": entry.sample_c_mode_var_name,
            "omega_sw_var_name": entry.omega_sw_var_name,
            "carrier_phase_var_name": entry.carrier_phase_var_name,
        })
        return data
    else:
        raise ValueError(f"Unsupported procedural logic entry '{type(entry).__name__}'")


def _fixed_sample_logic_from_dict(data: ProceduralLogicData) -> FixedSampleLogic:
    """
    Deserialize one fixed-sample procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Fixed-sample procedural logic entry.
    """
    return FixedSampleLogic(
        output_var_name=str(data["output_var_name"]),
        condition_expr=_expr_like_from_dict(_get_expr_like_field(data, "condition_expr")),
        name=str(data.get("name", "")),
    )


def _conditional_diagnostic_logic_from_dict(
        data: ProceduralLogicData,
) -> ConditionalDiagnosticLogic:
    """Deserialize one conditional diagnostic declaration.

    :param data: Serialized logic dictionary.
    :return: Conditional diagnostic declaration.
    """
    return ConditionalDiagnosticLogic(
        condition_expr=_expr_like_from_dict(
            _get_expr_like_field(data, "condition_expr")
        ),
        message=str(data["message"]),
        initialization_only=bool(data["initialization_only"]),
        name=str(data.get("name", "")),
    )


def _delayed_switch_event_logic_from_dict(
        data: ProceduralLogicData,
) -> DelayedSwitchEventLogic:
    """Deserialize one guarded delayed switch event.

    :param data: Serialized logic dictionary.
    :return: Executable switch event.
    """
    return DelayedSwitchEventLogic(
        output_var_name=str(data["output_var_name"]),
        guard_expr=_expr_like_from_dict(_get_expr_like_field(data, "guard_expr")),
        trigger_expr=_expr_like_from_dict(_get_expr_like_field(data, "trigger_expr")),
        delay_expr=_expr_like_from_dict(_get_expr_like_field(data, "delay_expr")),
        target_device_idtag=str(data["target_device_idtag"]),
        target_switch_idtag=str(data["target_switch_idtag"]),
        target_terminal_index=_read_procedural_integer(
            data,
            "target_terminal_index",
        ),
        initial_closed=bool(data["initial_closed"]),
        command_closed=bool(data["command_closed"]),
        name=str(data.get("name", "")),
    )


def _sampled_value_logic_from_dict(data: ProceduralLogicData) -> SampledValueLogic:
    """
    Deserialize one sampled-value procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Sampled-value procedural logic entry.
    """
    output_var_uid_raw: object = data.get("output_var_uid", None)
    if output_var_uid_raw is None:
        output_var_uid: int | None = None
    else:
        if (
                isinstance(output_var_uid_raw, int)
                and not isinstance(output_var_uid_raw, bool)
        ):
            output_var_uid = output_var_uid_raw
        else:
            raise TypeError("Sampled-value output UID must be an integer")

    return SampledValueLogic(
        output_var_name=str(data["output_var_name"]),
        source_expr=_expr_like_from_dict(_get_expr_like_field(data, "source_expr")),
        name=str(data.get("name", "")),
        output_var_uid=output_var_uid,
    )


def _hard_saturation_logic_from_dict(data: ProceduralLogicData) -> HardSaturationLogic:
    return HardSaturationLogic(
        output_var_name=str(data["output_var_name"]),
        u_expr=_expr_like_from_dict(_get_expr_like_field(data, "u_expr")),
        u_min_expr=_expr_like_from_dict(_get_expr_like_field(data, "u_min_expr")),
        u_max_expr=_expr_like_from_dict(_get_expr_like_field(data, "u_max_expr")),
        name=str(data.get("name", "")),
    )


def _time_delay_logic_from_dict(data: ProceduralLogicData) -> TimeDelayLogic:
    return TimeDelayLogic(
        output_var_name=str(data["output_var_name"]),
        source_expr=_expr_like_from_dict(_get_expr_like_field(data, "source_expr")),
        delay_expr=_expr_like_from_dict(_get_expr_like_field(data, "delay_expr")),
        name=str(data.get("name", "")),
    )


def _moving_average_logic_from_dict(data: ProceduralLogicData) -> MovingAverageLogic:
    return MovingAverageLogic(
        output_var_name=str(data["output_var_name"]),
        source_expr=_expr_like_from_dict(_get_expr_like_field(data, "source_expr")),
        delay_expr=_expr_like_from_dict(_get_expr_like_field(data, "delay_expr")),
        window_expr=_expr_like_from_dict(_get_expr_like_field(data, "window_expr")),
        name=str(data.get("name", "")),
    )


def _gradient_limiter_logic_from_dict(data: ProceduralLogicData) -> GradientLimiterLogic:
    return GradientLimiterLogic(
        output_var_name=str(data["output_var_name"]),
        source_expr=_expr_like_from_dict(_get_expr_like_field(data, "source_expr")),
        lower_rate_expr=_expr_like_from_dict(_get_expr_like_field(data, "lower_rate_expr")),
        upper_rate_expr=_expr_like_from_dict(_get_expr_like_field(data, "upper_rate_expr")),
        name=str(data.get("name", "")),
    )


def _flipflop_logic_from_dict(data: ProceduralLogicData) -> FlipFlopLogic:
    """
    Deserialize one flip-flop procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Flip-flop procedural logic entry.
    """
    return FlipFlopLogic(
        output_var_name=str(data["output_var_name"]),
        set_expr=_expr_like_from_dict(_get_expr_like_field(data, "set_expr")),
        reset_expr=_expr_like_from_dict(_get_expr_like_field(data, "reset_expr")),
        name=str(data.get("name", "")),
    )


def _analog_flipflop_logic_from_dict(data: ProceduralLogicData) -> AnalogFlipFlopLogic:
    """
    Deserialize one analog flip-flop procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Analog flip-flop procedural logic entry.
    """
    return AnalogFlipFlopLogic(
        output_var_name=str(data["output_var_name"]),
        input_expr=_expr_like_from_dict(_get_expr_like_field(data, "input_expr")),
        set_expr=_expr_like_from_dict(_get_expr_like_field(data, "set_expr")),
        reset_expr=_expr_like_from_dict(_get_expr_like_field(data, "reset_expr")),
        name=str(data.get("name", "")),
    )


def _pickup_dropoff_logic_from_dict(data: ProceduralLogicData) -> PickupDropoffLogic:
    """
    Deserialize one pickup/dropoff procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Pickup/dropoff procedural logic entry.
    """
    output_var_uid_raw: object = data.get("output_var_uid", None)
    if output_var_uid_raw is None:
        output_var_uid: int | None = None
    else:
        if (
                isinstance(output_var_uid_raw, int)
                and not isinstance(output_var_uid_raw, bool)
        ):
            output_var_uid = output_var_uid_raw
        else:
            raise TypeError("Pickup/dropoff output UID must be an integer")

    return PickupDropoffLogic(
        output_var_name=str(data["output_var_name"]),
        bool_expr=_expr_like_from_dict(_get_expr_like_field(data, "bool_expr")),
        pickup_delay_expr=_expr_like_from_dict(_get_expr_like_field(data, "pickup_delay_expr")),
        drop_delay_expr=_expr_like_from_dict(_get_expr_like_field(data, "drop_delay_expr")),
        name=str(data.get("name", "")),
        output_var_uid=output_var_uid,
    )


def _reset_on_rising_edge_logic_from_dict(data: ProceduralLogicData) -> ResetOnRisingEdgeLogic:
    """
    Deserialize one reset-on-rising-edge procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Reset-on-rising-edge procedural logic entry.
    """
    return ResetOnRisingEdgeLogic(
        target_var_name=str(data["target_var_name"]),
        reset_expr=_expr_like_from_dict(_get_expr_like_field(data, "reset_expr")),
        value_expr=_expr_like_from_dict(_get_expr_like_field(data, "value_expr")),
        name=str(data.get("name", "")),
    )


def _delayed_threshold_latch_logic_from_dict(data: ProceduralLogicData) -> DelayedThresholdLatchLogic:
    """
    Deserialize one delayed-threshold-latch procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Delayed-threshold-latch procedural logic entry.
    """
    reset_delay_raw: object = data.get("reset_delay", None)
    if reset_delay_raw is None:
        reset_delay_value: Optional[float] = None
    else:
        reset_delay_value = _read_finite_procedural_float(
            data,
            "reset_delay",
        )
    threshold_value: float = _read_finite_procedural_float(data, "threshold")
    delay_value: float = _read_finite_procedural_float(data, "delay")
    return DelayedThresholdLatchLogic(
        monitored_var_name=str(data["monitored_var_name"]),
        mode_var_name=str(data["mode_var_name"]),
        threshold=threshold_value,
        delay=delay_value,
        reset_delay=reset_delay_value,
        name=str(data.get("name", "")),
    )


def _startup_handover_logic_from_dict(data: ProceduralLogicData) -> StartupHandoverLogic:
    """
    Deserialize one startup-handover procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Startup-handover procedural logic entry.
    """
    return StartupHandoverLogic(
        mode_var_name=str(data["mode_var_name"]),
        enable_time_var_name=str(data["enable_time_var_name"]),
        on_value_var_name=(None if data.get("on_value_var_name", None) is None
                           else str(data["on_value_var_name"])),
        name=str(data.get("name", "")),
    )


def _valve_state_logic_from_dict(data: ProceduralLogicData) -> ValveStateLogic:
    """
    Deserialize one retained valve-state procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Valve-state procedural logic entry.
    """
    return ValveStateLogic(
        mode_var_name=str(data["mode_var_name"]),
        valve_type_var_name=str(data["valve_type_var_name"]),
        gate_var_name=str(data["gate_var_name"]),
        antiparallel_var_name=str(data["antiparallel_var_name"]),
        voltage_eps_var_name=str(data["voltage_eps_var_name"]),
        current_eps_var_name=str(data["current_eps_var_name"]),
        valve_voltage_var_name=str(data["valve_voltage_var_name"]),
        valve_current_var_name=str(data["valve_current_var_name"]),
        name=str(data.get("name", "")),
    )


def _three_phase_carrier_pwm_logic_from_dict(data: ProceduralLogicData) -> ThreePhaseCarrierPwmLogic:
    """
    Deserialize one three-phase carrier PWM procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Three-phase carrier PWM procedural logic entry.
    """
    return ThreePhaseCarrierPwmLogic(
        mod_a_var_name=str(data["mod_a_var_name"]),
        mod_b_var_name=str(data["mod_b_var_name"]),
        mod_c_var_name=str(data["mod_c_var_name"]),
        gate_a_mode_var_name=str(data["gate_a_mode_var_name"]),
        gate_b_mode_var_name=str(data["gate_b_mode_var_name"]),
        gate_c_mode_var_name=str(data["gate_c_mode_var_name"]),
        omega_sw_var_name=str(data["omega_sw_var_name"]),
        carrier_phase_var_name=str(data["carrier_phase_var_name"]),
        name=str(data.get("name", "")),
    )


def _three_phase_carrier_sampled_modulation_logic_from_dict(data: ProceduralLogicData) -> ThreePhaseCarrierSampledModulationLogic:
    """
    Deserialize one three-phase carrier sampled-modulation procedural logic entry.

    :param data: Serialized logic dictionary.
    :return: Three-phase sampled-modulation logic entry.
    """
    return ThreePhaseCarrierSampledModulationLogic(
        mod_a_var_name=str(data["mod_a_var_name"]),
        mod_b_var_name=str(data["mod_b_var_name"]),
        mod_c_var_name=str(data["mod_c_var_name"]),
        sample_a_mode_var_name=str(data["sample_a_mode_var_name"]),
        sample_b_mode_var_name=str(data["sample_b_mode_var_name"]),
        sample_c_mode_var_name=str(data["sample_c_mode_var_name"]),
        omega_sw_var_name=str(data["omega_sw_var_name"]),
        carrier_phase_var_name=str(data["carrier_phase_var_name"]),
        name=str(data.get("name", "")),
    )


def build_procedural_logic_entry(
        data: ProceduralLogicData,
        var_factory: VarFactory | None = None,
) -> ProceduralLogicBase:
    """
    Deserialize one procedural logic entry.

    :param data: Serialized logic config.
    :param var_factory: Optional factory required by entries holding live variables.
    :return: Procedural logic object.
    """
    logic_tpe_text: str = str(data.get("logic_type", data.get("logic_tpe", "")))
    logic_tpe: ProceduralLogicType = ProceduralLogicType(logic_tpe_text)

    if logic_tpe == ProceduralLogicType.ManufacturerNativeController:
        if var_factory is None:
            raise ValueError("Manufacturer native procedural logic requires a VarFactory")
        else:
            pass
        raw_bindings: object = data.get("signal_bindings", None)
        raw_overrides: object = data.get("parameter_overrides", None)
        if not isinstance(raw_bindings, list) or not isinstance(raw_overrides, list):
            raise TypeError("Manufacturer native bindings and overrides must be lists")
        else:
            pass
        signal_bindings: List[IeeeCigreDllSignalBinding] = list()
        raw_binding: object
        for raw_binding in raw_bindings:
            if not isinstance(raw_binding, list) or len(raw_binding) != 5:
                raise TypeError("Manufacturer native signal binding must contain five fields")
            else:
                pass
            is_input_raw: object = raw_binding[0]
            port_ordinal_raw: object = raw_binding[1]
            element_ordinal_raw: object = raw_binding[2]
            var_name_raw: object = raw_binding[3]
            var_uid_raw: object = raw_binding[4]
            if (
                    not isinstance(is_input_raw, bool)
                    or not isinstance(port_ordinal_raw, int)
                    or isinstance(port_ordinal_raw, bool)
                    or not isinstance(element_ordinal_raw, int)
                    or isinstance(element_ordinal_raw, bool)
                    or not isinstance(var_name_raw, str)
                    or not isinstance(var_uid_raw, int)
                    or isinstance(var_uid_raw, bool)
            ):
                raise TypeError("Manufacturer native signal binding has invalid field types")
            else:
                variable: Var | None = find_var_by_persisted_identity(
                    var_dict=var_factory.get_vars_dict(),
                    persisted_uid=var_uid_raw,
                )
                if variable is None:
                    variable = find_var_by_persisted_identity(
                        var_dict=var_factory.get_diff_var_dict(),
                        persisted_uid=var_uid_raw,
                    )
                else:
                    pass
                if variable is None:
                    raise ValueError(
                        f"Manufacturer native signal variable '{var_name_raw}' was not found in VarFactory"
                    )
                else:
                    signal_bindings.append(IeeeCigreDllSignalBinding(
                        is_input=is_input_raw,
                        port_ordinal=port_ordinal_raw,
                        element_ordinal=element_ordinal_raw,
                        variable=variable,
                    ))
        parameter_overrides: List[IeeeCigreDllParameterOverride] = list()
        raw_override: object
        for raw_override in raw_overrides:
            if not isinstance(raw_override, list) or len(raw_override) != 4:
                raise TypeError("Manufacturer native parameter override must contain four fields")
            else:
                pass
            parameter_ordinal_raw: object = raw_override[0]
            data_type_raw: object = raw_override[1]
            fixed_value_raw: object = raw_override[2]
            override_value_raw: object = raw_override[3]
            if (
                    not isinstance(parameter_ordinal_raw, int)
                    or isinstance(parameter_ordinal_raw, bool)
                    or not isinstance(data_type_raw, int)
                    or isinstance(data_type_raw, bool)
                    or not isinstance(fixed_value_raw, bool)
                    or not isinstance(override_value_raw, (int, float, str))
                    or isinstance(override_value_raw, bool)
            ):
                raise TypeError("Manufacturer native parameter override has invalid field types")
            else:
                parameter_overrides.append(IeeeCigreDllParameterOverride(
                    parameter_ordinal=parameter_ordinal_raw,
                    data_type=data_type_raw,
                    fixed_value=fixed_value_raw,
                    value=override_value_raw,
                ))
        return ManufacturerNativeControllerLogic(
            provider_idtag=str(data["provider_idtag"]),
            model_info_sha256=str(data["model_info_sha256"]),
            signal_bindings=tuple(signal_bindings),
            parameter_overrides=tuple(parameter_overrides),
            name=str(data.get("name", "")),
        )
    elif logic_tpe == ProceduralLogicType.ConditionalDiagnostic:
        return _conditional_diagnostic_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.DelayedSwitchEvent:
        return _delayed_switch_event_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.FixedSample:
        return _fixed_sample_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.SampledValue:
        return _sampled_value_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.HardSaturation:
        return _hard_saturation_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.TimeDelay:
        return _time_delay_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.MovingAverage:
        return _moving_average_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.GradientLimiter:
        return _gradient_limiter_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.FlipFlop:
        return _flipflop_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.AnalogFlipFlop:
        return _analog_flipflop_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.PickupDropoff:
        return _pickup_dropoff_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.ResetOnRisingEdge:
        return _reset_on_rising_edge_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.DelayedThresholdLatch:
        return _delayed_threshold_latch_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.StartupHandover:
        return _startup_handover_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.ValveState:
        return _valve_state_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierPwm:
        return _three_phase_carrier_pwm_logic_from_dict(data)
    elif logic_tpe == ProceduralLogicType.ThreePhaseCarrierSampledModulation:
        return _three_phase_carrier_sampled_modulation_logic_from_dict(data)
    else:
        raise ValueError(f"Unsupported procedural logic type '{logic_tpe_text}'")


def procedural_logic_to_dict(entries: List[ProceduralLogicBase]) -> List[ProceduralLogicData]:
    """
    Serialize a list of procedural logic entries.

    :param entries: Logic entries.
    :return: Serialized representation.
    """
    return [procedural_logic_entry_to_dict(entry) for entry in entries]


def procedural_logic_from_dict(
        entries: List[ProceduralLogicData | ProceduralLogicBase],
        var_factory: VarFactory | None = None,
) -> List[ProceduralLogicBase]:
    """
    Deserialize a list of procedural logic entries.

    :param entries: Serialized entries.
    :param var_factory: Optional factory required by entries holding live variables.
    :return: Procedural logic objects.
    """
    normalized_entries: List[ProceduralLogicBase] = list()
    item: object
    raw_key: object
    raw_value: object

    for item in entries:
        if isinstance(item, ProceduralLogicBase):
            normalized_entries.append(item)
        else:
            if isinstance(item, dict):
                normalized_data: ProceduralLogicData = dict()
                for raw_key, raw_value in item.items():
                    if isinstance(raw_key, str):
                        normalized_data[raw_key] = raw_value
                    else:
                        raise TypeError(
                            "Procedural logic keys must be strings"
                        )
                else:
                    pass
                normalized_entries.append(
                    build_procedural_logic_entry(
                        data=normalized_data,
                        var_factory=var_factory,
                    )
                )
            else:
                raise TypeError(
                    "Procedural logic entries must be typed objects or mappings"
                )

    return normalized_entries


def clone_procedural_logic_entries(
        entries: Iterable[ProceduralLogicEntryContract[Expr]],
        var_mapping: VarRemap,
) -> List[ProceduralLogicEntryContract[Expr]]:
    """Clone procedural logic entries under a variable remapping.

    :param entries: Source procedural logic entries.
    :param var_mapping: Mapping from old variables/names to remapped expressions.
    :return: Remapped procedural logic entries.
    """
    remapped_entries: List[ProceduralLogicEntryContract[Expr]] = list()
    entry: ProceduralLogicEntryContract[Expr]
    for entry in entries:
        remapped_entries.append(entry.remap(var_mapping))
    else:
        pass
    return remapped_entries


class ProceduralLogicCodec(ProceduralLogicCodecContract[Expr]):
    """Reconstruct procedural state machines at an explicit parse boundary."""

    __slots__ = ()

    def parse_entries(
            self,
            entries: Iterable[ProceduralLogicData],
            var_factory: VarFactory | None = None,
    ) -> Iterable[ProceduralLogicEntryContract[Expr]]:
        """Build typed state machines from declarative entry data.

        :param entries: Declarative procedural entries.
        :param var_factory: Optional factory required by entries holding live variables.
        :return: Reconstructed procedural state machines.
        """
        entry_list: List[ProceduralLogicData] = list(entries)
        return procedural_logic_from_dict(
            entries=entry_list,
            var_factory=var_factory,
        )


def build_boundary_updater_from_block(
        problem: ProceduralProblem,
        runtime_session: ManufacturerNativeRuntimeSessionProtocol | None = None,
        model_mode: int | None = None,
) -> Optional[BlockProceduralLogicUpdater]:
    """
    Build an isolated runtime updater from the logic attached to ``problem.sys_block``.

    The block hierarchy is canonical persistent model data. Runtime binding
    must therefore target reconstructed entries so solver-owned objects, such
    as progress signals, cannot become reachable from the persistent model.

    :param problem: Numerical problem containing the root block.
    :param runtime_session: Optional driver-owned manufacturer-native session.
    :param model_mode: Exact IEEE/CIGRE RMS or EMT mode number.
    :return: Boundary updater or None.
    """
    entries: List[ProceduralLogicBase] = list()
    block: Block
    contract_entry: ProceduralLogicEntryContract[Expr]
    for block in problem.sys_block.get_all_blocks():
        for contract_entry in block.procedural_logic:
            if isinstance(contract_entry, ProceduralLogicBase):
                entries.append(contract_entry)
            else:
                raise TypeError(
                    "Block procedural entries must be concrete state machines"
                )

    if len(entries) == 0:
        return None

    # Cross the declarative codec boundary for ordinary entries. Native bindings
    # retain live references to canonical model variables, so clone those entries
    # explicitly through an identity structural map instead of serializing them.
    runtime_entries: List[ProceduralLogicBase] = list()
    entry: ProceduralLogicBase
    for entry in entries:
        if isinstance(entry, ManufacturerNativeControllerLogic):
            structural_var_mapping: Dict[int, Var] = dict()
            signal_binding: IeeeCigreDllSignalBinding
            for signal_binding in entry.signal_bindings:
                binding_var: Var = signal_binding.get_variable()
                structural_var_mapping[binding_var.non_mutable_uid] = binding_var
            runtime_entries.append(entry.remap_with_structural_vars(
                var_mapping=dict(),
                structural_var_mapping=structural_var_mapping,
            ))
        else:
            serialized_entry: ProceduralLogicData = procedural_logic_entry_to_dict(entry)
            runtime_entries.append(build_procedural_logic_entry(data=serialized_entry))
    return BlockProceduralLogicUpdater(
        problem=problem,
        logic_entries=runtime_entries,
        runtime_session=runtime_session,
        model_mode=model_mode,
    )
