# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Callable, Dict, Iterator, List, Tuple, Union, Optional
import numpy as np
import numba as nb
import math
import time
import hashlib
import os
import pickle
from pathlib import Path
import warnings
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from collections import defaultdict, deque

from VeraGridEngine.enumerations import (
    EmtInitializationMethod,
    EmtInitializationStatus,
    SelfImplicitSolveStatus,
)
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian, SymbolicVector
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler
from VeraGridEngine.Utils.Symbolic.symbolic import expression2numba, get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block, normalize_event_parameter_initialization
from VeraGridEngine.Utils.Symbolic.symbolic import (
    BinOp,
    Comparison,
    Var,
    Const,
    Expr,
    find_vars_order,
    hard_sat,
    heaviside,
    min as symbolic_minimum,
    max as symbolic_maximum,
)
from VeraGridEngine.Utils.procedural_logic import (
    AnalogFlipFlopLogic,
    FixedSampleLogic,
    FlipFlopLogic,
    GradientLimiterLogic,
    HardSaturationLogic,
    MovingAverageLogic,
    SampledValueLogic,
    TimeDelayLogic,
)


class SelfImplicitSolveResult:
    """Store the outcome of one scalar self-implicit initialization solve."""

    __slots__ = (
        "value",
        "converged",
        "iterations",
        "residual",
        "status",
    )

    def __init__(
            self,
            value: float,
            converged: bool,
            iterations: int,
            residual: float,
            status: SelfImplicitSolveStatus,
    ) -> None:
        """Build a scalar self-implicit solve result.

        :param value: Final candidate value. A failed solve does not commit this
            candidate to the target array.
        :param converged: Whether the residual satisfied the requested tolerance.
        :param iterations: Number of secant iterations performed.
        :param residual: Absolute fixed-point residual of the final candidate.
        :param status: Exact reason why the solve stopped.
        :return: None.
        """
        self.value: float = value
        self.converged: bool = converged
        self.iterations: int = iterations
        self.residual: float = residual
        self.status: SelfImplicitSolveStatus = status


class ExplicitInitializationResult:
    """Store the transactional outcome of common explicit initialization."""

    __slots__ = (
        "init_guess",
        "diff_init_guess",
        "converged",
        "failed_variable",
        "self_implicit_result",
        "message",
    )

    def __init__(
            self,
            init_guess: Dict[int, float | int | complex | None],
            diff_init_guess: Dict[int, float | int | complex | None],
            converged: bool,
            failed_variable: Var | None,
            self_implicit_result: SelfImplicitSolveResult | None,
            message: str,
    ) -> None:
        """Build the result returned by the common explicit initializer.

        :param init_guess: Committed algebraic and state initialization values.
        :param diff_init_guess: Committed differential initialization values.
        :param converged: Whether every required explicit equation was resolved.
        :param failed_variable: Self-implicit variable that failed, if present.
        :param self_implicit_result: Scalar failure diagnostics, if present.
        :param message: Human-readable outcome description.
        :return: None.
        """
        self.init_guess: Dict[int, float | int | complex | None] = init_guess
        self.diff_init_guess: Dict[int, float | int | complex | None] = diff_init_guess
        self.converged: bool = converged
        self.failed_variable: Var | None = failed_variable
        self.self_implicit_result: SelfImplicitSolveResult | None = self_implicit_result
        self.message: str = message

    def __iter__(self) -> Iterator[Dict[int, float | int | complex | None]]:
        """Expose the historical two-dictionary result without changing legacy callers.

        A failed result raises before yielding either dictionary, ensuring that
        tuple-unpacking callers cannot silently continue with unresolved values.

        :return: Iterator over the state/algebraic and differential guess dictionaries.
        :rtype: Iterator[Dict[int, float | int | complex | None]]
        :raises RuntimeError: If explicit initialization did not converge.
        """
        if self.converged:
            yield self.init_guess
            yield self.diff_init_guess
        else:
            raise RuntimeError(self.message)


def build_uid_bindings(
        eq: Union[Expr, Const],
        event_params_array: np.ndarray,
        x: np.ndarray,
        params_array: np.ndarray,
        dx: np.ndarray,
        uid2idx_event_params: Dict[int, int],
        uid2idx_vars: Dict[int, int],
        uid2idx_params: Dict[int, int],
        uid2idx_diff: Dict[int, int],
        init_guess: Optional[Dict[int, float]] = None,
        diff_init_guess: Optional[Dict[int, float]] = None,
        external_uid_values: Optional[Dict[int, float]] = None,
) -> Dict[int, float]:
    """
    Build the UID-to-value bindings needed to evaluate one symbolic expression.

    :param eq: Symbolic expression to analyze.
    :type eq: Union[Expr, Const]
    :param event_params_array: Runtime parameter values.
    :type event_params_array: np.ndarray
    :param x: Algebraic or state vector.
    :type x: np.ndarray
    :param params_array: Constant parameter vector.
    :type params_array: np.ndarray
    :param dx: Differential initialization vector.
    :type dx: np.ndarray
    :param uid2idx_event_params: Runtime parameter index map.
    :type uid2idx_event_params: Dict[int, int]
    :param uid2idx_vars: Variable index map.
    :type uid2idx_vars: Dict[int, int]
    :param uid2idx_params: Constant parameter index map.
    :type uid2idx_params: Dict[int, int]
    :param uid2idx_diff: Differential variable index map.
    :type uid2idx_diff: Dict[int, int]
    :param init_guess: Previously resolved state and algebraic values.
    :param diff_init_guess: Previously resolved differential values.
    :param external_uid_values: Explicit values for variables owned outside the symbolic block.
    :return: Numeric bindings for the expression variables.
    :rtype: Dict[int, float]
    """
    uid_bindings: Dict[int, float] = dict()
    vars_list: List[Var] = find_vars_order(eq)

    for vr in vars_list:
        resolved_value: Optional[float] = None
        event_idx: Optional[int] = uid2idx_event_params.get(vr.uid, None)
        state_idx: Optional[int] = uid2idx_vars.get(vr.uid, None)
        param_idx: Optional[int] = uid2idx_params.get(vr.uid, None)
        diff_idx: Optional[int] = uid2idx_diff.get(vr.uid, None)

        if event_idx is None:
            if state_idx is None:
                if param_idx is None:
                    if diff_idx is None:
                        if external_uid_values is not None and vr.uid in external_uid_values:
                            resolved_value = float(external_uid_values[vr.uid])
                        elif init_guess is not None and vr.uid in init_guess:
                            resolved_value = float(init_guess[vr.uid])
                        elif diff_init_guess is not None and vr.uid in diff_init_guess:
                            resolved_value = float(diff_init_guess[vr.uid])
                        else:
                            resolved_value = None
                    else:
                        resolved_value = float(dx[diff_idx])
                else:
                    resolved_value = float(params_array[param_idx])
            else:
                resolved_value = float(x[state_idx])
        else:
            resolved_value = float(event_params_array[event_idx])

        if resolved_value is None:
            uid_bindings = uid_bindings
        else:
            uid_bindings[vr.uid] = resolved_value

    return uid_bindings

"""
This function initializes the parameters, variables and derivatives of symbolic blocks. 
Works for both RMS and EMT simulations since the symbolic block is the same.
"""




def evaluate_explicit_init_equation(
        eq: Union[Expr, Const],
        event_params_array: np.ndarray,
        x: np.ndarray,
        params_array: np.ndarray,
        dx: np.ndarray,
        uid2idx_event_params: Dict[int, int],
        uid2idx_vars: Dict[int, int],
        uid2idx_params: Dict[int, int],
        uid2idx_diff: Dict[int, int],
        init_guess: Optional[Dict[int, float]] = None,
        diff_init_guess: Optional[Dict[int, float]] = None,
        external_uid_values: Optional[Dict[int, float]] = None,
) -> float | int | complex | None:
    """
    Evaluate one explicit initialization equation using the shared bindings.

    :param eq: Symbolic expression or constant.
    :type eq: Union[Expr, Const]
    :param event_params_array: Runtime parameter values.
    :type event_params_array: np.ndarray
    :param x: Algebraic or state vector.
    :type x: np.ndarray
    :param params_array: Constant parameter vector.
    :type params_array: np.ndarray
    :param dx: Differential initialization vector.
    :type dx: np.ndarray
    :param uid2idx_event_params: Event parameter index map.
    :type uid2idx_event_params: Dict[int, int]
    :param uid2idx_vars: Variable index map.
    :type uid2idx_vars: Dict[int, int]
    :param uid2idx_params: Constant parameter index map.
    :type uid2idx_params: Dict[int, int]
    :param uid2idx_diff: Differential variable index map.
    :type uid2idx_diff: Dict[int, int]
    :param init_guess: Previously resolved state and algebraic values.
    :param diff_init_guess: Previously resolved differential values.
    :param external_uid_values: Explicit values for variables owned outside the symbolic block.
    :return: Evaluated scalar value.
    :rtype: float
    :raises RuntimeError: If a constant equation has no concrete value.
    """
    if isinstance(eq, Const):
        return eq.value
    else:
        uid_bindings: Dict[int, float] = build_uid_bindings(
            eq=eq,
            event_params_array=event_params_array,
            x=x,
            params_array=params_array,
            dx=dx,
            uid2idx_event_params=uid2idx_event_params,
            uid2idx_vars=uid2idx_vars,
            uid2idx_params=uid2idx_params,
            uid2idx_diff=uid2idx_diff,
            init_guess=init_guess,
            diff_init_guess=diff_init_guess,
            external_uid_values=external_uid_values,
        )
        try:
            return eq.eval_uid(uid_bindings)
        except ValueError as exc:
            unresolved: List[Var] = [vr for vr in find_vars_order(eq) if vr.uid not in uid_bindings]
            unresolved_desc = ", ".join(f"{vr.name} (uid={vr.uid})" for vr in unresolved)
            raise ValueError(
                f"Failed to evaluate explicit init equation '{eq}' with unresolved vars: {unresolved_desc}"
            ) from exc


def evaluate_single_equation_fn(
        eq_fn: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], Union[np.ndarray, float]],
        x: np.ndarray,
        dx: np.ndarray,
        event_params_array: np.ndarray,
        params_array: np.ndarray,
) -> float:
    """
    Evaluate one compiled single-equation callable and normalize its scalar output.

    The backend callable may return a length-one numpy vector or a scalar-like
    numeric value. The common initializer always consumes it as a float.

    :param eq_fn: Compiled single-equation callable.
    :type eq_fn: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], Union[np.ndarray, float]]
    :param x: Algebraic or state vector.
    :type x: np.ndarray
    :param dx: Differential initialization vector.
    :type dx: np.ndarray
    :param event_params_array: Runtime parameter values.
    :type event_params_array: np.ndarray
    :param params_array: Constant parameter vector.
    :type params_array: np.ndarray
    :return: Evaluated scalar value.
    :rtype: float
    """
    result: Union[np.ndarray, float] = eq_fn(x, dx, event_params_array, params_array)

    if isinstance(result, np.ndarray):
        return float(result[0])
    else:
        return float(result)


def store_resolved_event_parameter(
        event_param: Var,
        event_params_init_dict: Dict[int, float | int | complex | None],
        event_parameters_eqs: List[Union[Expr, Const]],
        event_eq_idx: int,
        result: float | int | complex | None,
) -> None:
    """
  Store the calculated value in the equations array

    :param event_param:
    :type event_param:
    :param event_params_init_dict:
    :type event_params_init_dict:
    :param event_parameters_eqs: Global runtime-parameter equation list.
    :type event_parameters_eqs: List[Union[Expr, Const]]
    :param event_eq_idx: Index of the runtime parameter in the global list.
    :type event_eq_idx: int
    :param result: Resolved scalar value.
    :type result: float
    :return: None
    :rtype: None
    """
    resolved_event_eq: Const = Const(result)

    event_parameters_eqs[event_eq_idx] = resolved_event_eq

    event_params_init_dict[event_param.uid] = result


class SymbolicVectorSingleEquationCompiler:
    """
    Compile one self-implicit equation using the EMT symbolic-vector backend.
    """

    __slots__ = ("_compiler_names_dict", "_alias_names_dict", "_vars_name", "_diff_name", "_event_params_name", "_params_name")

    def __init__(
            self,
            compiler_names_dict: Dict[int, str],
            alias_names_dict: Dict[int, str],
            vars_name: str,
            diff_name: str,
            event_params_name: str,
            params_name: str,
    ) -> None:
        """
        Build the EMT single-equation compiler wrapper.

        :param compiler_names_dict: Compiler variable name map.
        :type compiler_names_dict: Dict[int, str]
        :param alias_names_dict: Compiler alias name map.
        :type alias_names_dict: Dict[int, str]
        :param vars_name: Symbolic-vector variable array name.
        :type vars_name: str
        :param diff_name: Symbolic-vector differential array name.
        :type diff_name: str
        :param event_params_name: Symbolic-vector runtime-parameter array name.
        :type event_params_name: str
        :param params_name: Symbolic-vector constant-parameter array name.
        :type params_name: str
        :return: None
        :rtype: None
        """
        self._compiler_names_dict: Dict[int, str] = compiler_names_dict
        self._alias_names_dict: Dict[int, str] = alias_names_dict
        self._vars_name: str = vars_name
        self._diff_name: str = diff_name
        self._event_params_name: str = event_params_name
        self._params_name: str = params_name

    def compile_equation(
            self,
            eq: Union[Expr, Const],
    ) -> Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]:
        """
        Compile one symbolic equation with the EMT symbolic-vector backend.

        :param eq: Equation to compile.
        :type eq: Union[Expr, Const]
        :return: Evaluator with signature ``(x, dx, event_params, params)``.
        :rtype: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]
        :raises TypeError: If the equation is not symbolic.
        """
        if isinstance(eq, Const):
            raise TypeError("Self-implicit initialization requires a symbolic expression, not a constant")
        else:
            compiled_eq: SymbolicVector = SymbolicVector(
                [eq],
                self._compiler_names_dict,
                self._alias_names_dict,
                self._vars_name,
                self._diff_name,
                self._event_params_name,
                self._params_name,
            )
            return compiled_eq


class RmsSingleEquationCompiler:
    """
    Compile one self-implicit equation using the RMS JIT backend.
    """

    __slots__ = ("_rms_compiler", "_func_name_prefix", "_counter")

    def __init__(
            self,
            rms_compiler: RMSCompiler,
            func_name_prefix: str = "equation",
    ) -> None:
        """
        Build the RMS single-equation compiler wrapper.

        :param rms_compiler: Configured RMS compiler instance.
        :type rms_compiler: RMSCompiler
        :param func_name_prefix: Prefix used for generated callable names.
        :type func_name_prefix: str
        :return: None
        :rtype: None
        """
        self._rms_compiler: RMSCompiler = rms_compiler
        self._func_name_prefix: str = func_name_prefix
        self._counter: int = 0

    def compile_equation(
            self,
            eq: Union[Expr, Const],
    ) -> Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]:
        """
        Compile one symbolic equation with the RMS JIT backend.

        :param eq: Equation to compile.
        :type eq: Union[Expr, Const]
        :return: Evaluator with signature ``(x, dx, event_params, params)``.
        :rtype: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]
        :raises TypeError: If the equation is not symbolic.
        """
        if isinstance(eq, Const):
            raise TypeError("Self-implicit initialization requires a symbolic expression, not a constant")
        else:
            func_name: str = f"{self._func_name_prefix}_{self._counter}"
            self._counter += 1
            compiled_eq: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray] = self._rms_compiler.compile_rhs([eq], func_name)
            return compiled_eq


def compile_single_explicit_equation(
        compile_single_equation: Union[SymbolicVectorSingleEquationCompiler, RmsSingleEquationCompiler],
        eq: Union[Expr, Const],
) -> Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], Union[np.ndarray, float]]:
    """
    Compile one equation through the explicit wrapper object.

    :param compile_single_equation: Wrapper object selecting the backend.
    :type compile_single_equation: Union[SymbolicVectorSingleEquationCompiler, RmsSingleEquationCompiler]
    :param eq: Equation to compile.
    :type eq: Union[Expr, Const]
    :return: Evaluator with signature ``(x, dx, event_params, params)``.
    :rtype: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], Union[np.ndarray, float]]
    :raises TypeError: If the wrapper object type is unsupported.
    """
    if isinstance(compile_single_equation, SymbolicVectorSingleEquationCompiler):
        compiled_eq: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray] = (
            compile_single_equation.compile_equation(eq))
        return compiled_eq
    elif isinstance(compile_single_equation, RmsSingleEquationCompiler):
        compiled_eq = compile_single_equation.compile_equation(eq)
        return compiled_eq
    else:
        raise TypeError("Unsupported explicit initialization single-equation compiler wrapper")


def add_items(blk, init_vars, init_event):
    """
    adds items from a block to the dictionary
    :param blk:
    :type blk:
    :param init_vars:
    :param init_event:
    init_dict
    :return:
    :rtype:
    """

    init_var_key: Var
    init_var_value: Union[Expr, Const]
    for init_var_key, init_var_value in blk.init_eqs.items():
        init_vars[init_var_key] = init_var_value

    diff_init_key: Var
    diff_init_value: Union[Expr, Const]
    for diff_init_key, diff_init_value in blk.diff_init_eqs.items():
        init_vars[diff_init_key] = diff_init_value

    event_key: Var
    event_value: Union[Expr, Const]
    for event_key, event_value in blk.event_dict.items():
        init_event[event_key] = event_value

    mode_key: Var
    mode_value: Union[Expr, Const]
    for mode_key, mode_value in blk.mode_dict.items():
        init_event[mode_key] = mode_value

def build_init_dict(mdl, init_vars, init_event):
    """
    builds initialization dictionary from mdl
    :param mdl:
    :type mdl:
    :param init_vars:
    :param init_event:
    :type init_vars:
    init_dict
    :return:
    :rtype:
    """
    add_items(mdl, init_vars, init_event)
    for blk in mdl.children:
        build_init_dict(blk, init_vars, init_event)


def _coerce_procedural_initial_expression(
        expression: Expr | Comparison | float | int | bool,
) -> Expr:
    """Convert one procedural startup source into a symbolic expression.

    :param expression: Procedural expression or scalar startup value.
    :return: Symbolic expression accepted by the explicit dependency graph.
    """
    if isinstance(expression, Comparison):
        result: Expr = expression.to_expression()
    elif isinstance(expression, Expr):
        result = expression
    else:
        result = Const(float(expression))
    return result


def _coerce_procedural_boolean_initial_expression(
        expression: Expr | Comparison | float | int | bool,
) -> Expr:
    """Convert one procedural condition into its zero-or-one startup value.

    Procedural runtime conditions use a strict ``> 0.5`` threshold. Explicit
    initialization must apply the same rule when a model supplies a numeric
    expression rather than a symbolic comparison.

    :param expression: Procedural condition or scalar startup value.
    :return: Symbolic zero-or-one expression matching runtime evaluation.
    """
    if isinstance(expression, Comparison):
        result: Expr = expression.to_expression()
    else:
        numeric_expression: Expr = _coerce_procedural_initial_expression(expression)
        result = heaviside(numeric_expression - Const(0.5))
    return result


def _find_procedural_initial_output(
        init_event: Dict[Var, Union[Expr, Const]],
        output_var_name: str,
        output_var_uid: int | None,
) -> Var | None:
    """Resolve one procedural output against declared runtime parameters.

    Stable UID is authoritative for current files. Name lookup remains as the
    legacy fallback and succeeds only when the name is unambiguous.

    :param init_event: Declared runtime initialization equations.
    :param output_var_name: Persisted output name used by legacy entries.
    :param output_var_uid: Stable output UID when present in the entry.
    :return: Matching runtime variable, or ``None`` when it cannot be resolved safely.
    """
    output_var: Var | None = None
    candidate_var: Var

    if output_var_uid is None:
        for candidate_var in init_event:
            if candidate_var.name == output_var_name:
                if output_var is None:
                    output_var = candidate_var
                else:
                    output_var = None
                    break
            else:
                pass
    else:
        for candidate_var in init_event:
            if candidate_var.uid == output_var_uid:
                output_var = candidate_var
                break
            else:
                pass

    return output_var


def apply_procedural_initializers(
        mdl: Block,
        init_event: Dict[Var, Union[Expr, Const]],
) -> None:
    """Promote deterministic procedural startup values into the init graph.

    Pure sampling, delay-history, gradient, saturation and startup-deterministic
    latch entries all have a well-defined first value. Their outputs remain in
    ``mode_dict`` at runtime, but their first value must participate in the same
    dependency graph as ordinary initialization equations. Timed relay and
    switching entries are deliberately excluded because their retained fallback
    is part of their startup contract and is reconciled by the boundary updater.

    :param mdl: Symbolic block whose procedural entries are inspected.
    :param init_event: Runtime initialization equations updated in place.
    :return: None.
    """
    procedural_entry: object

    for procedural_entry in mdl.procedural_logic:
        source_expression: Expr | None
        if isinstance(procedural_entry, SampledValueLogic):
            output_var_name: str = procedural_entry.output_var_name
            output_var_uid: int | None = procedural_entry.output_var_uid
            source_expression = _coerce_procedural_initial_expression(
                expression=procedural_entry.source_expr,
            )
        elif isinstance(procedural_entry, FixedSampleLogic):
            output_var_name = procedural_entry.output_var_name
            output_var_uid = None
            source_expression = _coerce_procedural_boolean_initial_expression(
                expression=procedural_entry.condition_expr,
            )
        elif isinstance(procedural_entry, HardSaturationLogic):
            output_var_name = procedural_entry.output_var_name
            output_var_uid = None
            saturation_input: Expr = _coerce_procedural_initial_expression(
                procedural_entry.u_expr,
            )
            first_limit: Expr = _coerce_procedural_initial_expression(
                procedural_entry.u_min_expr,
            )
            second_limit: Expr = _coerce_procedural_initial_expression(
                procedural_entry.u_max_expr,
            )
            lower_limit: Expr = symbolic_minimum(first_limit, second_limit)
            upper_limit: Expr = symbolic_maximum(first_limit, second_limit)
            source_expression = hard_sat(
                saturation_input,
                lower_limit,
                upper_limit,
            )
        elif isinstance(procedural_entry, TimeDelayLogic):
            output_var_name = procedural_entry.output_var_name
            output_var_uid = None
            source_expression = _coerce_procedural_initial_expression(
                expression=procedural_entry.source_expr,
            )
        elif isinstance(procedural_entry, MovingAverageLogic):
            output_var_name = procedural_entry.output_var_name
            output_var_uid = None
            source_expression = _coerce_procedural_initial_expression(
                expression=procedural_entry.source_expr,
            )
        elif isinstance(procedural_entry, GradientLimiterLogic):
            output_var_name = procedural_entry.output_var_name
            output_var_uid = None
            source_expression = _coerce_procedural_initial_expression(
                expression=procedural_entry.source_expr,
            )
        elif isinstance(procedural_entry, FlipFlopLogic):
            output_var_name = procedural_entry.output_var_name
            output_var_uid = None
            source_expression = _coerce_procedural_boolean_initial_expression(
                expression=procedural_entry.set_expr,
            )
        elif isinstance(procedural_entry, AnalogFlipFlopLogic):
            output_var_name = procedural_entry.output_var_name
            output_var_uid = None
            source_expression = _coerce_procedural_initial_expression(
                expression=procedural_entry.input_expr,
            )
        else:
            output_var_name = ""
            output_var_uid = None
            source_expression = None

        if output_var_name == "" or source_expression is None:
            pass
        else:
            output_var: Var | None = _find_procedural_initial_output(
                init_event=init_event,
                output_var_name=output_var_name,
                output_var_uid=output_var_uid,
            )
            if output_var is None:
                pass
            else:
                init_event[output_var] = source_expression

    child_block: Block
    for child_block in mdl.children:
        apply_procedural_initializers(
            mdl=child_block,
            init_event=init_event,
        )


def collect_direct_algebraic_initializers(
        mdl: Block,
        direct_initializers: Dict[Var, Expr],
) -> None:
    """Collect explicit ``variable - expression`` algebraic assignments.

    PowerFactory ``inc(...)`` expressions can depend on an intermediate
    algebraic assignment. Those intermediates must be evaluated before the
    initialization expression instead of retaining the generic work-vector
    seed.

    :param mdl: Symbolic block whose algebraic equations are inspected.
    :param direct_initializers: Direct assignments collected recursively.
    :return: None.
    """
    algebraic_var_uids: set[int] = set()
    state_var_uids: set[int] = set()
    all_blocks: List[Block] = mdl.get_all_blocks()
    nested_block: Block
    for nested_block in all_blocks:
        nested_state_var: Var
        for nested_state_var in nested_block.state_vars:
            state_var_uids.add(nested_state_var.uid)

    for nested_block in all_blocks:
        nested_algebraic_var: Var
        nested_algebraic_lists: Tuple[List[Var], ...] = (
            nested_block.algebraic_vars,
            nested_block.reformulated_vars,
            nested_block.in_vars,
            nested_block.out_vars,
        )
        nested_algebraic_list: List[Var]
        for nested_algebraic_list in nested_algebraic_lists:
            for nested_algebraic_var in nested_algebraic_list:
                if nested_algebraic_var.uid in state_var_uids:
                    pass
                else:
                    algebraic_var_uids.add(nested_algebraic_var.uid)
    algebraic_eq: Expr

    # Only accept the declarative residual shape produced for a direct
    # assignment. General implicit equations remain owned by the DAE solver.
    for algebraic_eq in mdl.algebraic_eqs:
        if (
                isinstance(algebraic_eq, BinOp)
                and algebraic_eq.op == "-"
                and isinstance(algebraic_eq.left, Var)
                and algebraic_eq.left.uid in algebraic_var_uids
                and not algebraic_eq.right.contains_var(algebraic_eq.left)
        ):
            direct_initializers[algebraic_eq.left] = algebraic_eq.right
        else:
            pass

    child_block: Block
    for child_block in mdl.children:
        collect_direct_algebraic_initializers(
            mdl=child_block,
            direct_initializers=direct_initializers,
        )


def initialization_dependency_reaches_uid(
        start_var: Var,
        target_uid: int,
        init_vars: Dict[Var, Union[Expr, Const]],
        visited_uids: set[int],
) -> bool:
    """Check whether one initialization dependency reaches a target variable.

    Direct algebraic assignments are inferred from DAE residuals rather than
    explicitly declared as initialization equations. Before admitting one of
    those inferred assignments, its dependency chain must remain acyclic with
    the authoritative explicit initialization equations.

    :param start_var: Dependency from which to traverse initialization equations.
    :param target_uid: Candidate variable whose re-entry would close a cycle.
    :param init_vars: Candidate initialization equations indexed by target variable.
    :param visited_uids: Variable identities already inspected during this traversal.
    :return: Whether the dependency chain reaches ``target_uid``.
    """
    if start_var.uid == target_uid:
        return True
    else:
        pass

    if start_var.uid in visited_uids:
        return False
    else:
        visited_uids.add(start_var.uid)

    start_equation: Union[Expr, Const] | None = None
    equation_var: Var
    equation: Union[Expr, Const]
    for equation_var, equation in init_vars.items():
        if start_equation is None and equation_var.uid == start_var.uid:
            start_equation = equation
        else:
            pass

    if start_equation is None:
        return False
    else:
        pass

    dependency_var: Var
    for dependency_var in get_expression_vars(start_equation):
        if initialization_dependency_reaches_uid(
                start_var=dependency_var,
                target_uid=target_uid,
                init_vars=init_vars,
                visited_uids=visited_uids,
        ):
            return True
        else:
            pass

    return False


def add_direct_algebraic_init_dependencies(
        init_vars: Dict[Var, Union[Expr, Const]],
        direct_initializers: Dict[Var, Expr],
        preserved_var_uids: set[int],
) -> None:
    """Add direct algebraic assignments required by initialization equations.

    :param init_vars: Unified explicit initialization equations, updated in place.
    :param direct_initializers: Available direct algebraic assignments.
    :param preserved_var_uids: Variables already seeded by an external operating point.
    :return: None.
    """
    dependency_added: bool = True

    # Re-scan a fixed snapshot on each pass because a newly added direct
    # assignment can itself expose another required intermediate.
    while dependency_added:
        dependency_added = False
        current_equations: List[Union[Expr, Const]] = list(init_vars.values())
        current_eq: Union[Expr, Const]
        for current_eq in current_equations:
            dependency_var: Var
            for dependency_var in get_expression_vars(current_eq):
                if dependency_var in init_vars:
                    pass
                else:
                    if dependency_var.uid in preserved_var_uids:
                        pass
                    else:
                        direct_eq: Optional[Expr] = direct_initializers.get(dependency_var, None)
                        if direct_eq is None:
                            pass
                        else:
                            # A legacy EMT terminal output can be both the seed
                            # of an explicit state initializer and a direct DAE
                            # result of that same state. Pulling the inferred DAE
                            # assignment into the explicit graph would turn two
                            # equivalent relations into an artificial cycle.
                            candidate_init_vars: Dict[Var, Union[Expr, Const]] = dict(init_vars)
                            candidate_init_vars[dependency_var] = direct_eq
                            creates_cycle: bool = False
                            direct_dependency_var: Var
                            for direct_dependency_var in get_expression_vars(direct_eq):
                                if initialization_dependency_reaches_uid(
                                        start_var=direct_dependency_var,
                                        target_uid=dependency_var.uid,
                                        init_vars=candidate_init_vars,
                                        visited_uids=set(),
                                ):
                                    creates_cycle = True
                                else:
                                    pass

                            if creates_cycle:
                                # Keep the existing work-vector/PF seed as the
                                # boundary value. Explicit declarations remain
                                # authoritative over inferred DAE assignments.
                                pass
                            else:
                                init_vars[dependency_var] = direct_eq
                                dependency_added = True

def build_explicit_init_graph(
        mdl: Block,
        preserved_var_uids: Optional[set[int]] = None,
) -> Tuple[Dict[Var, Union[Expr, Const]], Dict[Var, List[Var]], List[Var], Dict[Var, Union[Expr, Const]]]:
    """
    Build the unified dependency graph used by the explicit initializer.

    :param mdl: Symbolic block containing event, init, and diff-init equations.
    :type mdl: Block
    :param preserved_var_uids: Optional externally seeded variables that direct
        algebraic assignments must consume without replacing.
    :return: Unified equation dictionary, dependency map, and topological order.
    :rtype: Tuple[Dict[Var, Union[Expr, Const]], Dict[Var, List[Var]], List[Var]]
    :raises RuntimeError: If a cross-variable cycle is detected.
    """
    normalize_event_parameter_initialization(block=mdl)

    init_vars = dict()
    init_event = dict()
    if preserved_var_uids is None:
        preserved_uids: set[int] = set()
    else:
        preserved_uids = set(preserved_var_uids)
    build_init_dict(mdl, init_vars, init_event)
    apply_procedural_initializers(
        mdl=mdl,
        init_event=init_event,
    )

    # Event parameters own their single initialization expression directly.
    # Normalization above migrates the former Const(None) + init_eqs pattern.
    for ev_var, ev_eq in init_event.items():
        init_vars[ev_var] = ev_eq

    # Resolve only direct algebraic assignments reached from the complete
    # initialization graph, including procedural startup expressions. This
    # preserves DAE ownership of general implicit algebraics while ensuring
    # ``inc(...)`` observes the same selected branch used at the first sample.
    direct_initializers: Dict[Var, Expr] = dict()
    collect_direct_algebraic_initializers(
        mdl=mdl,
        direct_initializers=direct_initializers,
    )
    add_direct_algebraic_init_dependencies(
        init_vars=init_vars,
        direct_initializers=direct_initializers,
        preserved_var_uids=preserved_uids,
    )

    graph: Dict[Var, List[Var]] = defaultdict(list)
    in_degree: Dict[Var, int] = defaultdict(int)
    dependencies: Dict[Var, List[Var]] = dict()

    for var, eq in init_vars.items():
        vars_in_eq: List[Var] = get_expression_vars(eq)
        deps: List[Var] = list()

        for dep in vars_in_eq:
            if dep in init_vars:
                deps.append(dep)
            else:
                deps = deps

        dependencies[var] = deps

        for dep in deps:
            if dep.uid != var.uid:
                graph[dep].append(var)
                in_degree[var] += 1
            else:
                in_degree[var] = in_degree[var]

        if var not in in_degree:
            in_degree[var] = 0
        else:
            in_degree[var] = in_degree[var]

    initial_queue_items: List[Var] = list()
    for var, degree in in_degree.items():
        if degree == 0:
            initial_queue_items.append(var)
        else:
            initial_queue_items = initial_queue_items

    queue: deque[Var] = deque(initial_queue_items)
    topo_order: List[Var] = list()

    while queue:
        current_var: Var = queue.popleft()
        topo_order.append(current_var)

        for downstream_var in graph[current_var]:
            in_degree[downstream_var] -= 1
            if in_degree[downstream_var] == 0:
                queue.append(downstream_var)
            else:
                queue = queue

    if len(topo_order) != len(init_vars):
        cyclic_vars: List[str] = list()
        var_key: Var
        degree_value: int
        for var_key, degree_value in in_degree.items():
            if degree_value > 0:
                cyclic_vars.append(str(var_key.name))
            else:
                cyclic_vars = cyclic_vars

        cyclic_dependencies: List[str] = list()
        cyclic_var: Var
        for cyclic_var, deps in dependencies.items():
            if in_degree.get(cyclic_var, 0) > 0:
                dep_names: List[str] = list()
                dep_var: Var
                for dep_var in deps:
                    dep_names.append(str(dep_var.name))
                cyclic_dependencies.append(f"{cyclic_var.name} <- {dep_names}")
            else:
                cyclic_dependencies = cyclic_dependencies

        raise RuntimeError(
            "Cycle detected between different variables: "
            f"vars={cyclic_vars}; deps={cyclic_dependencies}"
        )
    else:
        return init_vars, dependencies, topo_order, init_event


def build_symbolic_vector_single_equation_compiler(
        compiler_names_dict: Dict[int, str],
        alias_names_dict: Dict[int, str],
        vars_name: str,
        diff_name: str,
        event_params_name: str,
        params_name: str,
) -> SymbolicVectorSingleEquationCompiler:
    """
    Build the EMT single-equation compiler wrapper.

    :param compiler_names_dict: Compiler variable name map.
    :type compiler_names_dict: Dict[int, str]
    :param alias_names_dict: Compiler alias name map.
    :type alias_names_dict: Dict[int, str]
    :param vars_name: SymbolicVector state or algebraic array name.
    :type vars_name: str
    :param diff_name: SymbolicVector derivative array name.
    :type diff_name: str
    :param event_params_name: SymbolicVector event parameter array name.
    :type event_params_name: str
    :param params_name: SymbolicVector constant parameter array name.
    :type params_name: str
    :return: Wrapper object compiling one equation to the common four-array signature.
    :rtype: SymbolicVectorSingleEquationCompiler
    """
    compiler_wrapper: SymbolicVectorSingleEquationCompiler = SymbolicVectorSingleEquationCompiler(
        compiler_names_dict=compiler_names_dict,
        alias_names_dict=alias_names_dict,
        vars_name=vars_name,
        diff_name=diff_name,
        event_params_name=event_params_name,
        params_name=params_name,
    )
    return compiler_wrapper


def build_rms_single_equation_compiler(
        rms_compiler: RMSCompiler,
        func_name_prefix: str = "equation",
) -> RmsSingleEquationCompiler:
    """
    Build the RMS single-equation compiler wrapper.

    :param rms_compiler: Configured RMS compiler instance.
    :type rms_compiler: RMSCompiler
    :param func_name_prefix: Prefix used to name generated callables.
    :type func_name_prefix: str
    :return: Wrapper object compiling one equation to the common four-array signature.
    :rtype: RmsSingleEquationCompiler
    """
    compiler_wrapper: RmsSingleEquationCompiler = RmsSingleEquationCompiler(
        rms_compiler=rms_compiler,
        func_name_prefix=func_name_prefix,
    )
    return compiler_wrapper


def solve_self_implicit(
        eq_fn: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], Union[np.ndarray, float]],
        x: np.ndarray,
        dx: np.ndarray,
        target_idx: int,
        target_array: np.ndarray,
        event_params_array: np.ndarray,
        params_array: np.ndarray,
        tol: float = 1e-8,
        max_iter: int = 50,
) -> SelfImplicitSolveResult:
    """
    Solve a scalar self-implicit initialization equation with the shared signature.

    :param eq_fn: Compiled single-equation callable.
    :type eq_fn: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], Union[np.ndarray, float]]
    :param x: Algebraic or state vector.
    :type x: np.ndarray
    :param dx: Differential initialization vector.
    :type dx: np.ndarray
    :param target_idx: Target index inside ``target_array``.
    :type target_idx: int
    :param target_array: Array holding the unknown being solved.
    :type target_array: np.ndarray
    :param event_params_array: Runtime parameter values.
    :type event_params_array: np.ndarray
    :param params_array: Constant parameter vector.
    :type params_array: np.ndarray
    :param tol: Secant convergence tolerance.
    :type tol: float
    :param max_iter: Maximum secant iterations.
    :type max_iter: int
    :return: Scalar solution candidate and exact convergence diagnostics. Failed
        candidates are never committed to ``target_array``.
    :rtype: SelfImplicitSolveResult
    """
    original_value: float = float(target_array[target_idx])
    if np.isfinite(original_value):
        pass
    else:
        return SelfImplicitSolveResult(
            value=original_value,
            converged=False,
            iterations=0,
            residual=float("inf"),
            status=SelfImplicitSolveStatus.INVALID_INITIAL_GUESS,
        )

    # Preserve an exact zero seed. Dead-network and black-start models use zero
    # as a physical operating point, so it must be evaluated before introducing
    # the second secant point.
    x0: float = original_value
    x1: float = x0 + 0.1
    final_candidate: float = x0
    final_residual: float = float("inf")
    iteration_index: int = 0

    try:
        target_array[target_idx] = x0
        f0: float = evaluate_single_equation_fn(
            eq_fn,
            x,
            dx,
            event_params_array,
            params_array,
        ) - x0
        if np.isfinite(f0):
            final_residual = float(abs(f0))
        else:
            target_array[target_idx] = original_value
            return SelfImplicitSolveResult(
                value=x0,
                converged=False,
                iterations=0,
                residual=float("inf"),
                status=SelfImplicitSolveStatus.NON_FINITE_RESIDUAL,
            )

        if final_residual <= tol:
            target_array[target_idx] = x0
            return SelfImplicitSolveResult(
                value=x0,
                converged=True,
                iterations=0,
                residual=final_residual,
                status=SelfImplicitSolveStatus.CONVERGED,
            )
        else:
            pass

        for iteration_index in range(1, max_iter + 1):
            target_array[target_idx] = x1
            f1: float = evaluate_single_equation_fn(
                eq_fn,
                x,
                dx,
                event_params_array,
                params_array,
            ) - x1
            final_candidate = x1
            if np.isfinite(f1):
                final_residual = float(abs(f1))
            else:
                target_array[target_idx] = original_value
                return SelfImplicitSolveResult(
                    value=final_candidate,
                    converged=False,
                    iterations=iteration_index,
                    residual=float("inf"),
                    status=SelfImplicitSolveStatus.NON_FINITE_RESIDUAL,
                )

            if final_residual <= tol:
                target_array[target_idx] = final_candidate
                return SelfImplicitSolveResult(
                    value=final_candidate,
                    converged=True,
                    iterations=iteration_index,
                    residual=final_residual,
                    status=SelfImplicitSolveStatus.CONVERGED,
                )
            else:
                denominator: float = f1 - f0
                if abs(denominator) < 1e-12:
                    target_array[target_idx] = original_value
                    return SelfImplicitSolveResult(
                        value=final_candidate,
                        converged=False,
                        iterations=iteration_index,
                        residual=final_residual,
                        status=SelfImplicitSolveStatus.SINGULAR_SECANT,
                    )
                else:
                    x2: float = x1 - f1 * (x1 - x0) / denominator
                    if np.isfinite(x2):
                        x0 = x1
                        f0 = f1
                        x1 = x2
                    else:
                        target_array[target_idx] = original_value
                        return SelfImplicitSolveResult(
                            value=x2,
                            converged=False,
                            iterations=iteration_index,
                            residual=final_residual,
                            status=SelfImplicitSolveStatus.NON_FINITE_ITERATE,
                        )
    except Exception:
        # Equation compilation/evaluation errors remain exceptional, but the
        # numerical workspace must still be restored before propagating them.
        target_array[target_idx] = original_value
        raise

    target_array[target_idx] = original_value
    return SelfImplicitSolveResult(
        value=final_candidate,
        converged=False,
        iterations=iteration_index,
        residual=final_residual,
        status=SelfImplicitSolveStatus.MAX_ITERATIONS,
    )


def build_explicit_external_uid_values(
        mdl: Block,
        external_name_values: Dict[str, float],
) -> Dict[int, float]:
    """Resolve external symbolic inputs to their exact equation UIDs.

    Imported expressions may own external variables that are intentionally not
    part of the DAE state, derivative, or parameter vectors. The RMS wrapper
    declares their semantic names and values, while this boundary converts that
    declaration into the UID mapping consumed by the generic initializer.

    :param mdl: Symbolic block whose initialization graph consumes external inputs.
    :param external_name_values: External values keyed by declared symbolic name.
    :return: External values keyed by the exact variable UIDs used by the block.
    """
    external_uid_values: Dict[int, float] = dict()
    runtime_block: Block
    for runtime_block in mdl.get_all_blocks():
        equation_groups: List[List[Union[Expr, Const]]] = list([
            list(runtime_block.algebraic_eqs),
            list(runtime_block.state_eqs),
            list(runtime_block.differential_eqs),
            list(runtime_block.init_eqs.values()),
            list(runtime_block.diff_init_eqs.values()),
            list(runtime_block.event_dict.values()),
            list(runtime_block.mode_dict.values()),
            list(runtime_block.boolean_guards.values()),
        ])
        equation_group: List[Union[Expr, Const]]
        equation: Union[Expr, Const]
        equation_var: Var
        for equation_group in equation_groups:
            for equation in equation_group:
                for equation_var in find_vars_order(equation):
                    external_value: float | None = external_name_values.get(
                        equation_var.name,
                        None,
                    )
                    if external_value is None:
                        pass
                    else:
                        external_uid_values[equation_var.uid] = float(external_value)
                else:
                    pass
            else:
                pass
        else:
            pass
    else:
        pass

    return external_uid_values


def init_explicit_common(
        mdl: Block,
        sys_vars: Dict[int, Var],
        sys_diff_vars: Dict[int, Var],
        variable_parameters: List[Var],
        event_parameters_eqs: List[Union[Expr, Const]],
        constant_parameters: List[Var],
        init_guess: Dict[int, float | int | complex | None],
        event_param_init_dict: Dict[int, float | int | complex | None],
        diff_init_guess: Dict[int, float | int | complex | None],
        uid2idx_vars: Dict[int, int],
        uid2idx_diff: Dict[int, int],
        uid2idx_params: Dict[int, int],
        uid2idx_event_params: Dict[int, int],
        params_array: List[Const] | np.ndarray,
        compile_single_equation: Union[SymbolicVectorSingleEquationCompiler, RmsSingleEquationCompiler],
        external_uid_values: Optional[Dict[int, float]] = None,
        event_params_array_seed: np.ndarray | None = None,
        verbose: bool = False,
) -> ExplicitInitializationResult:
    """
    Run the universal explicit initialization core shared by RMS and EMT flows.

    :param mdl: Symbolic model block.
    :type mdl: Block
    :param sys_vars: System state and algebraic variables keyed by UID.
    :type sys_vars: Dict[int, Var]
    :param sys_diff_vars: System differential variables keyed by UID.
    :type sys_diff_vars: Dict[int, Var]
    :param variable_parameters: Runtime or event parameters.
    :type variable_parameters: List[Var]
    :param event_parameters_eqs: Runtime parameter equations storage.
    :type event_parameters_eqs: List[Union[Expr, Const]]
    :param constant_parameters: Constant parameters list.
    :type constant_parameters: List[Var]
    :param init_guess: Initialization guesses for algebraic or state variables.
    :type init_guess: Dict[int, float]
    :param event_param_init_dict: Resolved runtime-parameter values keyed by UID.
    :type event_param_init_dict: Dict[int, float | int | complex | None]
    :param diff_init_guess: Initialization guesses for differential variables.
    :type diff_init_guess: Dict[int, float]
    :param uid2idx_vars: Variable index map.
    :type uid2idx_vars: Dict[int, int]
    :param uid2idx_diff: Differential variable index map.
    :type uid2idx_diff: Dict[int, int]
    :param uid2idx_params: Constant parameter index map.
    :type uid2idx_params: Dict[int, int]
    :param uid2idx_event_params: Event parameter index map.
    :type uid2idx_event_params: Dict[int, int]
    :param params_array: Constant parameter vector in symbolic storage or numeric form.
    :type params_array: List[Const] | np.ndarray
    :param compile_single_equation: Backend-specific single-equation compiler wrapper.
    :type compile_single_equation: Union[SymbolicVectorSingleEquationCompiler, RmsSingleEquationCompiler]
    :param external_uid_values: Explicit values for variables owned outside the symbolic block.
    :type external_uid_values: Optional[Dict[int, float]]
    :param event_params_array_seed: Optional complete runtime-parameter seed vector.
    :type event_params_array_seed: np.ndarray | None
    :param verbose: Print initialization progress.
    :type verbose: bool
    :return: Transactional explicit-initialization result. The caller-owned
        dictionaries and runtime-equation list are updated only on success.
    :rtype: ExplicitInitializationResult
    """
    _ = constant_parameters

    # Resolve the complete block on local stores. A failed self-implicit
    # equation must not leave earlier variables or runtime parameters partially
    # committed to the problem.
    working_init_guess: Dict[int, float | int | complex | None] = dict(init_guess)
    working_diff_init_guess: Dict[int, float | int | complex | None] = dict(diff_init_guess)
    working_event_param_init_dict: Dict[int, float | int | complex | None] = dict(event_param_init_dict)
    working_event_parameters_eqs: List[Union[Expr, Const]] = list(event_parameters_eqs)

    # initialize array for model variables
    x: np.ndarray = np.ones(len(sys_vars))
    dx: np.ndarray = np.zeros(len(sys_diff_vars))
    if event_params_array_seed is None:
        event_params_array: np.ndarray = np.ones(len(variable_parameters))
    else:
        event_params_array = np.asarray(event_params_array_seed, dtype=np.float64).copy()
        if event_params_array.shape != (len(variable_parameters),):
            raise ValueError(
                "Explicit initialization runtime seed has shape "
                f"{event_params_array.shape}; expected {(len(variable_parameters),)}"
            )
        else:
            pass

    # RMS problem assembly retains Const wrappers so symbolic ownership is not
    # lost before compilation. Explicit evaluation consumes only concrete
    # scalars, therefore materialize a fixed-size numeric view at this boundary.
    if isinstance(params_array, np.ndarray):
        numeric_params_array: np.ndarray = np.asarray(params_array, dtype=float)
    else:
        numeric_params_array = np.zeros(len(params_array), dtype=float)
        parameter_index: int
        parameter_value: Const
        for parameter_index, parameter_value in enumerate(params_array):
            if parameter_value.value is None:
                parameter_name: str = constant_parameters[parameter_index].name
                raise ValueError(
                    f"Constant parameter '{parameter_name}' has no explicit initialization value"
                )
            else:
                numeric_params_array[parameter_index] = float(parameter_value.value)

    # Seed the working vectors with the guesses already assembled before the
    # explicit stage. The problem relies on those PF-driven values and on previously
    # resolved block values when evaluating downstream explicit equations.
    uid: int
    val: float | int | complex | None
    for uid, val in working_init_guess.items():
        if uid in uid2idx_vars:
            x[uid2idx_vars[uid]] = val
        else:
            pass

    for uid, val in working_diff_init_guess.items():
        if uid in uid2idx_diff:
            dx[uid2idx_diff[uid]] = val
        else:
            pass

    for uid, val in working_event_param_init_dict.items():
        if uid in uid2idx_event_params and val is not None:
            event_params_array[uid2idx_event_params[uid]] = val
        else:
            pass


    dic_total: Dict[Var, Union[Expr, Const]]
    dependencies: Dict[Var, List[Var]]
    topo_order: List[Var]
    init_event: Dict[Var, Union[Expr, Const]]
    dic_total, dependencies, topo_order, init_event = build_explicit_init_graph(
        mdl=mdl,
        preserved_var_uids=set(working_init_guess.keys()),
    )

    result: float | int | complex | None
    var: Var
    for var in topo_order:
        eq: Union[Expr, Const] = dic_total[var]

        if var in init_event:
            if var.uid in working_event_param_init_dict and working_event_param_init_dict[var.uid] is not None:
                result = working_event_param_init_dict[var.uid]
            else:
                result = evaluate_explicit_init_equation(
                    eq=eq,
                    event_params_array=event_params_array,
                    x=x,
                    params_array=numeric_params_array,
                    dx=dx,
                    uid2idx_event_params=uid2idx_event_params,
                    uid2idx_vars=uid2idx_vars,
                    uid2idx_params=uid2idx_params,
                    uid2idx_diff=uid2idx_diff,
                    init_guess=working_init_guess,
                    diff_init_guess=working_diff_init_guess,
                    external_uid_values=external_uid_values,
                )
            event_params_array[uid2idx_event_params[var.uid]] = result
            store_resolved_event_parameter(
                event_param=var,
                event_params_init_dict=working_event_param_init_dict,
                event_parameters_eqs=working_event_parameters_eqs,
                event_eq_idx=uid2idx_event_params[var.uid],
                result=result,
            )

            if verbose:
                print(f"event_param:{var.name} initialized with: {result}")
            else:
                pass

        else:
            if var not in dependencies[var]:
                result = evaluate_explicit_init_equation(
                    eq=eq,
                    event_params_array=event_params_array,
                    x=x,
                    params_array=numeric_params_array,
                    dx=dx,
                    uid2idx_event_params=uid2idx_event_params,
                    uid2idx_vars=uid2idx_vars,
                    uid2idx_params=uid2idx_params,
                    uid2idx_diff=uid2idx_diff,
                    init_guess=working_init_guess,
                    diff_init_guess=working_diff_init_guess,
                    external_uid_values=external_uid_values,
                )

                if var.uid in uid2idx_vars:
                    x[uid2idx_vars[var.uid]] = result
                    working_init_guess[var.uid] = result
                elif var.uid in uid2idx_diff:
                    dx[uid2idx_diff[var.uid]] = result
                    working_diff_init_guess[var.uid] = result
                else:
                    raise RuntimeError(f"Unable to classify explicit variable {var.name}")

            else:
                # Todo: refactor this to use compile_rhs function already built in jit_compiler
                eq_fn: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], Union[np.ndarray, float]] \
                    = compile_single_explicit_equation(compile_single_equation, eq)

                if var.uid in uid2idx_vars:
                    target_idx: int = uid2idx_vars[var.uid]
                    self_implicit_result: SelfImplicitSolveResult = solve_self_implicit(
                        eq_fn=eq_fn,
                        x=x,
                        dx=dx,
                        target_idx=target_idx,
                        target_array=x,
                        event_params_array=event_params_array,
                        params_array=numeric_params_array,
                    )
                    if self_implicit_result.converged:
                        result = self_implicit_result.value
                        x[target_idx] = result
                        working_init_guess[var.uid] = result
                    else:
                        failure_message: str = (
                            f"Self-implicit initialization did not converge for '{var.name}': "
                            f"status={self_implicit_result.status}, "
                            f"iterations={self_implicit_result.iterations}, "
                            f"residual={self_implicit_result.residual:.6g}."
                        )
                        return ExplicitInitializationResult(
                            init_guess=dict(init_guess),
                            diff_init_guess=dict(diff_init_guess),
                            converged=False,
                            failed_variable=var,
                            self_implicit_result=self_implicit_result,
                            message=failure_message,
                        )
                elif var.uid in uid2idx_diff:
                    target_idx = uid2idx_diff[var.uid]
                    self_implicit_result = solve_self_implicit(
                        eq_fn=eq_fn,
                        x=x,
                        dx=dx,
                        target_idx=target_idx,
                        target_array=dx,
                        event_params_array=event_params_array,
                        params_array=numeric_params_array,
                    )
                    if self_implicit_result.converged:
                        result = self_implicit_result.value
                        dx[target_idx] = result
                        working_diff_init_guess[var.uid] = result
                    else:
                        failure_message = (
                            f"Self-implicit initialization did not converge for '{var.name}': "
                            f"status={self_implicit_result.status}, "
                            f"iterations={self_implicit_result.iterations}, "
                            f"residual={self_implicit_result.residual:.6g}."
                        )
                        return ExplicitInitializationResult(
                            init_guess=dict(init_guess),
                            diff_init_guess=dict(diff_init_guess),
                            converged=False,
                            failed_variable=var,
                            self_implicit_result=self_implicit_result,
                            message=failure_message,
                        )
                else:
                    raise RuntimeError(f"Unable to classify self-implicit variable {var.name}")

            if verbose:
                print(f"explicit_init:{var.name} = {result}")
            else:
                pass


    # Commit all problem-facing stores together only after every explicit
    # equation has completed successfully.
    init_guess.clear()
    init_guess.update(working_init_guess)
    diff_init_guess.clear()
    diff_init_guess.update(working_diff_init_guess)
    event_param_init_dict.clear()
    event_param_init_dict.update(working_event_param_init_dict)
    event_equation_index: int
    for event_equation_index in range(len(event_parameters_eqs)):
        event_parameters_eqs[event_equation_index] = working_event_parameters_eqs[event_equation_index]

    return ExplicitInitializationResult(
        init_guess=init_guess,
        diff_init_guess=diff_init_guess,
        converged=True,
        failed_variable=None,
        self_implicit_result=None,
        message="Explicit initialization completed successfully.",
    )
