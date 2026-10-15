# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from abc import ABC
import numpy as np
from typing import Any, Dict, List, Optional, Protocol, Tuple

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, hard_sat, heaviside, piecewise, get_expression_vars
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import (
    build_api_parameter_initial_values_by_uid,
    resolve_parameter_initial_expression,
)
from VeraGridEngine.enumerations import DynamicEventTransitionType, VarPowerFlowReferenceType


def _get_diff_var_sort_key(diff_var: Var) -> int:
    """
    Return the ordering key used to sort differential variables.

    :param diff_var: Differential variable to inspect.
    :return: Sorting key associated with the differential variable.
    """
    return diff_var.diff_order


def _get_external_mapping(mdl: Block) -> Optional[Dict[Any, Var]]:
    """
    Return the external mapping associated with a model block.

    :param mdl: Model block to inspect.
    :return: External mapping dictionary or None.
    """
    external_mapping: Optional[Dict[Any, Var]] = mdl.external_mapping

    if external_mapping is None:
        return None
    else:
        return external_mapping


def _register_equation_variable_aliases(state_eqs: List[Any],
                                        algebraic_eqs: List[Any],
                                        diff_init_eqs: Dict[Var, Any],
                                        init_eqs: Dict[Var, Any],
                                        compiler_names_dict: Dict[int, str],
                                        alias_names_dict: Dict[int, str]) -> None:
    """
    Register compiler-name aliases for vars referenced only through cloned expressions.

    Saved editor models can preserve symbolic expressions that reference one ``Var``
    instance while the canonical problem collections store another instance with the
    same stable ``uid``. The EMT compilers index by ``uid``, so this helper scans
    the final equations and ensures every referenced uid has one compiler-name entry
    before any expression-to-numba conversion happens.

    :param state_eqs: State equations collected from the system block tree.
    :type state_eqs: List[Any]
    :param algebraic_eqs: Algebraic equations collected from the system block tree.
    :type algebraic_eqs: List[Any]
    :param diff_init_eqs: Differential initialization equations.
    :type diff_init_eqs: Dict[Var, Any]
    :param init_eqs: Initialization equations.
    :type init_eqs: Dict[Var, Any]
    :param compiler_names_dict: Problem compiler-name mapping keyed by uid.
    :type compiler_names_dict: Dict[int, str]
    :param alias_names_dict: Problem alias mapping keyed by uid.
    :type alias_names_dict: Dict[int, str]
    :return: None.
    :rtype: None
    """
    expression_groups: List[List[Any]] = list()
    expression_group: List[Any]
    expression_item: Any
    referenced_var: Var

    expression_groups.append(state_eqs)
    expression_groups.append(algebraic_eqs)
    expression_groups.append(list(diff_init_eqs.values()))
    expression_groups.append(list(init_eqs.values()))

    for expression_group in expression_groups:
        for expression_item in expression_group:
            for referenced_var in get_expression_vars(expression_item):
                if referenced_var.uid in compiler_names_dict:
                    pass
                else:
                    compiler_names_dict[referenced_var.uid] = referenced_var.name
                    alias_names_dict[referenced_var.uid] = referenced_var.name


def _collect_block_tree_sequence(root_block: Block) -> List[Block]:
    """
    Return the symbolic block tree in root-first traversal order.

    :param root_block: Root symbolic block.
    :return: Ordered block list including the root and every descendant.
    """
    ordered_blocks: List[Block] = list()
    pending_blocks: List[Block] = list([root_block])
    pending_index: int = 0
    current_block: Block
    child_block: Block

    while pending_index < len(pending_blocks):
        current_block = pending_blocks[pending_index]
        pending_index += 1
        ordered_blocks.append(current_block)

        for child_block in current_block.children:
            pending_blocks.append(child_block)

    return ordered_blocks


def _collect_hierarchical_init_equations(root_block: Block) -> tuple[Dict[Var, Any], Dict[Var, Any]]:
    """
    Collect initialization equations from the full block hierarchy.

    :param root_block: Root symbolic block.
    :return: Tuple ``(init_eqs, diff_init_eqs)`` merged from the hierarchy.
    """
    block_sequence: List[Block] = _collect_block_tree_sequence(root_block)
    init_eqs: Dict[Var, Any] = dict()
    diff_init_eqs: Dict[Var, Any] = dict()
    block_item: Block
    init_var: Var
    init_expr: Any

    for block_item in block_sequence:
        for init_var, init_expr in block_item.init_eqs.items():
            init_eqs[init_var] = init_expr

        for init_var, init_expr in block_item.diff_init_eqs.items():
            diff_init_eqs[init_var] = init_expr

    return init_eqs, diff_init_eqs


def _collect_hierarchical_runtime_equations(root_block: Block) -> Dict[int, Any]:
    """
    Collect runtime event and mode equations from the full block hierarchy.

    :param root_block: Root symbolic block.
    :return: Runtime equation lookup keyed by variable uid.
    """
    block_sequence: List[Block] = _collect_block_tree_sequence(root_block)
    runtime_equation_lookup: Dict[int, Any] = dict()
    block_item: Block
    runtime_var: Var
    runtime_expr: Any

    for block_item in block_sequence:
        for runtime_var, runtime_expr in block_item.event_dict.items():
            runtime_equation_lookup[runtime_var.uid] = runtime_expr

        for runtime_var, runtime_expr in block_item.mode_dict.items():
            runtime_equation_lookup[runtime_var.uid] = runtime_expr

    return runtime_equation_lookup


class EmtBoundaryUpdateProtocol(Protocol):
    """
    Structural protocol implemented by EMT boundary update providers.
    """
    __slots__ = ()

    def update(self, t: float, x: Vec, params: Vec) -> float | None:
        """
        Update the full parameter vector and return a shortened retry target.
        """
        ...

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the next exact-alignment event time inside ``(t_prev, t_target]``.
        """
        ...

    def resolve_step(self, accepted: bool, params: Vec) -> float | None:
        """Resolve a prepared external boundary step after Newton.

        :param accepted: Whether the EMT numerical step converged.
        :param params: Full runtime-parameter vector.
        :return: Earlier state-event retry time, or ``None``.
        """
        ...

    def commit_boundary(self, t: float, x: Vec, params: Vec) -> None:
        """Advance post-accepted external sample-and-hold runtimes.

        :param t: Accepted solver boundary.
        :param x: Accepted state vector.
        :param params: Mutable runtime parameter vector.
        :return: None.
        """
        ...


def _implements_forced_event_time_api(boundary_updater: Any) -> bool:
    """
    Return whether one boundary updater type implements ``get_next_forced_event_time``.

    :param boundary_updater: Boundary updater instance.
    :return: ``True`` when the API is implemented.
    """
    return "get_next_forced_event_time" in dir(boundary_updater)


def _implements_step_resolution_api(boundary_updater: Any) -> bool:
    """Return whether one boundary updater implements ``resolve_step``.

    :param boundary_updater: Boundary updater instance.
    :return: ``True`` when transactional step resolution is implemented.
    """

    return "resolve_step" in dir(boundary_updater)



def _implements_commit_boundary_api(boundary_updater: Any) -> bool:
    """Return whether an updater implements a boundary commit callback.

    :param boundary_updater: Boundary updater instance.
    :return: ``True`` when boundary commit is implemented.
    """
    updater_type: type = type(boundary_updater)
    base_type: type
    for base_type in updater_type.__mro__:
        if "commit_boundary" in base_type.__dict__:
            return True
        else:
            pass
    return False

def _emt_event_spec_time_sort_key(event_spec: Dict[str, float | str | None]) -> float:
    """
    Return the sorting key of one EMT runtime-event specification.

    :param event_spec: EMT runtime-event specification.
    :return: Event start time.
    """
    return float(event_spec["time"])


def resolve_solver_boundary_updater(
        problem: "EmtProblemTemplate",
        boundary_updater: EmtBoundaryUpdateProtocol | None,
        t0: float,
) -> EmtBoundaryUpdateProtocol | None:
    """
    Resolve the boundary updater consumed by an EMT solver.

    The problem-owned updater remains the default, but demos and legacy callers
    may still provide external wrappers that only implement ``update()``.
    """
    problem.reset_boundary_update_state(float(t0))

    if boundary_updater is None:
        return problem.boundary_update

    return boundary_updater

def get_solver_forced_event_time(
        boundary_updater: EmtBoundaryUpdateProtocol | None,
        t_prev: float,
        t_target: float,
) -> float | None:
    """
    Query the next forced-alignment event time if the updater exposes it.

    Legacy boundary updaters that only implement ``update()`` are treated as
    having no forced event alignment requirements.
    """
    if boundary_updater is None:
        return None
    else:
        pass

    if _implements_forced_event_time_api(boundary_updater):
        pass
    else:
        return None

    next_time: float | None = boundary_updater.get_next_forced_event_time(float(t_prev), float(t_target))

    if next_time is None:
        return None
    else:
        return float(next_time)


def resolve_solver_boundary_step(
        boundary_updater: EmtBoundaryUpdateProtocol | None,
        accepted: bool,
        params: Vec,
        committed_time: float | None = None,
        committed_state: Vec | None = None,
) -> float | None:
    """Resolve a prepared external boundary step when the updater supports it.

    Legacy and native boundary updaters without transactional FMU ME state do
    not need a resolution callback.

    :param boundary_updater: Effective boundary updater used by the solver.
    :param accepted: Whether the EMT Newton step converged.
    :param params: Full runtime-parameter vector receiving resolved outputs.
    :param committed_time: Accepted boundary time for sample-and-hold runtimes.
    :param committed_state: Accepted state for sample-and-hold inputs.
    :return: Earlier state-event retry time, or ``None``.
    """

    if boundary_updater is None:
        retry_time: float | None = None
    else:
        if _implements_step_resolution_api(boundary_updater):
            retry_time = boundary_updater.resolve_step(
                accepted=accepted,
                params=params,
            )
        else:
            retry_time = None
    if (accepted and retry_time is None and boundary_updater is not None
            and committed_time is not None and committed_state is not None
            and _implements_commit_boundary_api(boundary_updater)):
        boundary_updater.commit_boundary(float(committed_time), committed_state, params)
    else:
        pass
    return retry_time


def is_problem_owned_boundary_updater(problem: "EmtProblemTemplate",
                                     boundary_updater: EmtBoundaryUpdateProtocol | None) -> bool:
    """
    Return whether the updater is owned by the EMT problem itself.

    This distinguishes endogenous problem boundary logic from external wrappers
    supplied by tests or demos.
    """
    if boundary_updater is None:
        return False

    if boundary_updater is problem:
        return True

    problem_boundary_updater = problem.boundary_update

    if problem_boundary_updater is None:
        return False

    return boundary_updater is problem_boundary_updater


def _freeze_runtime_expr_at_time(expr: Any, time_var: Var, sample_time: float) -> Any:
    """
    Freeze one runtime expression at an explicit time value.

    :param expr: Runtime expression to freeze.
    :param time_var: Global symbolic time variable.
    :param sample_time: Time used to evaluate the expression boundary.
    :return: Time-frozen symbolic expression.
    """
    if isinstance(expr, (Expr, Var, Const)):
        return expr.subs(dict({time_var: Const(float(sample_time))})).simplify()
    else:
        return expr


def _build_ramp_runtime_expr(
    time_var: Var,
    start_time: float,
    end_time: float,
    before_expr: Any,
    final_value: float,
) -> Any:
    """
    Build one linear ramp transition on top of an existing runtime expression.

    :param time_var: Global symbolic time variable.
    :param start_time: Ramp start time.
    :param end_time: Ramp end time.
    :param before_expr: Expression active before the ramp starts.
    :param final_value: Final runtime value after the ramp ends.
    :return: Combined symbolic expression.
    """
    start_expr: Any = _freeze_runtime_expr_at_time(before_expr, time_var, start_time)
    duration_expr: Const = Const(float(end_time - start_time))
    time_offset_expr: Any = time_var - Const(float(start_time))
    progress_expr: Any = hard_sat(time_offset_expr / duration_expr, Const(0.0), Const(1.0))
    ramp_expr: Any = start_expr + progress_expr * (Const(float(final_value)) - start_expr)
    started_expr: Any = heaviside(time_var - Const(float(start_time)))
    ended_expr: Any = heaviside(time_var - Const(float(end_time)))
    return (Const(1.0) - started_expr) * before_expr + started_expr * (
        (Const(1.0) - ended_expr) * ramp_expr + ended_expr * Const(float(final_value))
    )


class EmtProblemTemplate(ABC):
    """
    Intermediate layer that manages DAE plumbing including indexing, variable mapping,
    and event updating, regardless of whether the system comes from an electrical
    circuit or a generic mathematical model.
    """

    VARS_NAME = "vars"
    VARIABLE_PARAMS_NAME = "vprms"
    CONSTANT_PARAMS_NAME = "cprms"
    DIFF_NAME = "diff"
    TIME_NAME = "glob_time"

    __slots__ = (
        "sys_block",
        "grid",
        "_glob_time",
        "_newton_trace_collector",
        "_init_eqs_flat",
        "_diff_init_eqs_flat",
        "_state_vars",
        "_algebraic_vars",
        "_state_eqs",
        "_algebraic_eqs",
        "_diff_vars",
        "_static_parameter_values",
        "_api_parameter_initial_values_by_uid",
        "_variable_parameters",
        "_event_parameters_eqs",
        "_runtime_mode_uids",
        "_constant_parameters",
        "_parameters_values",
        "_runtime_all_parameters_source",
        "_runtime_all_eqs_source",
        "_runtime_continuous_parameters",
        "_runtime_mode_parameters",
        "_runtime_continuous_eqs",
        "_runtime_mode_eqs",
        "_runtime_continuous_slice",
        "_runtime_mode_slice",
        "_vars_glob_name2uid",
        "init_guess",
        "event_params_init_dict",
        "diff_init_guess",
        "_event_params_values",
        "_constant_params_values",
        "progress_signal",
        "progress_text",
        "_n_vars",
        "_n_state",
        "_n_alg",
        "_n_algebraic",
        "_n_diff",
        "_n_params",
        "_n_event_params",
        "_uid2idx_vars",
        "_uid2idx_diff",
        "_uid2idx_params",
        "_uid2idx_event_params",
        "_compiler_names_dict",
        "_alias_names_dict",
        "_uid2idx_t",
    )

    def __init__(self,
                 sys_block: Block,
                 static_parameter_values_mapping: Dict[Var, Const],
                 glob_time: Var,
                 init_eqs_flat: Dict[Var, Any] | None = None,
                 diff_init_eqs_flat: Dict[Var, Any] | None = None,
                 vars_glob_name2uid: Dict[str, int] | None = None,
                 progress_signal: DummySignal | None = None,
                 progress_text: DummySignal | None = None,
                 )->None:
        """
        Initialize the EMT problem template.

        :param sys_block: Root symbolic block that defines the EMT problem.
        :param static_parameter_values_mapping: Problem-local initial values
            resolved from owner-local API-object mappings.
        :param glob_time: Global time variable used by runtime expressions.
        :param init_eqs_flat: Optional pre-collected initialization equations.
        :param diff_init_eqs_flat: Optional pre-collected differential initialization equations.
        :param vars_glob_name2uid: Optional pre-collected variable-name lookup.
        :return: None
        """
        super().__init__()
        self.sys_block: Block = sys_block
        existing_grid: MultiCircuit | None
        try:
            existing_grid = self.grid
        except AttributeError:
            existing_grid = None
        self.grid: MultiCircuit | None = existing_grid
        self._glob_time: Var = glob_time
        self._newton_trace_collector: Optional[Any] = None
        self._init_eqs_flat: Dict[Var, Any] = dict()
        self._diff_init_eqs_flat: Dict[Var, Any] = dict()

        block_sequence: List[Block] = _collect_block_tree_sequence(self.sys_block)
        hierarchical_init_eqs: Dict[Var, Any]
        hierarchical_diff_init_eqs: Dict[Var, Any]
        block_item: Block
        runtime_var: Var
        runtime_expr: Any
        const_var: Var
        const_expr: Const

        if init_eqs_flat is None or diff_init_eqs_flat is None:
            hierarchical_init_eqs, hierarchical_diff_init_eqs = _collect_hierarchical_init_equations(self.sys_block)
            self._init_eqs_flat = hierarchical_init_eqs
            self._diff_init_eqs_flat = hierarchical_diff_init_eqs
        else:
            self._init_eqs_flat = dict(init_eqs_flat)
            self._diff_init_eqs_flat = dict(diff_init_eqs_flat)

        self._state_vars: List[Var] = list()
        self._algebraic_vars: List[Var] = list()
        self._state_eqs: List[Any] = list()
        self._algebraic_eqs: List[Any] = list()
        self._diff_vars: List[Var] = list()

        self._static_parameter_values: Dict[Var, Const] = dict()
        self._api_parameter_initial_values_by_uid: Dict[int, Const] = build_api_parameter_initial_values_by_uid(
            problem_mapping=static_parameter_values_mapping,
        )
        registered_parameter_uids: set[int] = set()
        self._variable_parameters: List[Var] = list()
        self._event_parameters_eqs: List[Any] = list()
        self._runtime_mode_uids: set[int] = set()

        # The API-object mapping provides initial values only. Block.parameters,
        # Block.event_dict and Block.mode_dict remain authoritative for immutable,
        # continuous-runtime and discrete-runtime roles, matching RMS.
        for block_item in block_sequence:
            self._state_vars.extend(block_item.state_vars)
            self._algebraic_vars.extend(block_item.algebraic_vars)
            self._state_eqs.extend(block_item.state_eqs)
            self._algebraic_eqs.extend(block_item.algebraic_eqs)
            self._diff_vars.extend(block_item.diff_vars)

            for const_var, const_expr in block_item.parameters.items():
                if const_var.uid in registered_parameter_uids:
                    raise ValueError(
                        f"EMT constant parameter '{const_var.name}' (uid={const_var.uid}) "
                        + "is declared more than once in the block hierarchy."
                    )
                else:
                    registered_parameter_uids.add(const_var.uid)

                    resolved_const_expression: Expr | Const = resolve_parameter_initial_expression(
                        parameter=const_var,
                        declared_expression=const_expr,
                        problem_mapping=static_parameter_values_mapping,
                    )
                    if isinstance(resolved_const_expression, Const):
                        self._static_parameter_values[const_var] = resolved_const_expression
                    else:
                        raise TypeError(
                            f"EMT immutable parameter '{const_var.name}' (uid={const_var.uid}) "
                            + f"in block '{block_item.name}' must resolve to Const."
                        )

            for runtime_var, runtime_expr in block_item.event_dict.items():
                self._variable_parameters.append(runtime_var)
                resolved_runtime_expression: Expr | Const = resolve_parameter_initial_expression(
                    parameter=runtime_var,
                    declared_expression=runtime_expr,
                    problem_mapping=static_parameter_values_mapping,
                )
                # The block keeps its runtime declaration while the problem
                # stores the authoritative mapped value as the initial baseline.
                self._event_parameters_eqs.append(resolved_runtime_expression)

            for runtime_var, runtime_expr in block_item.mode_dict.items():
                self._variable_parameters.append(runtime_var)
                resolved_mode_expression: Expr | Const = resolve_parameter_initial_expression(
                    parameter=runtime_var,
                    declared_expression=runtime_expr,
                    problem_mapping=static_parameter_values_mapping,
                )
                self._event_parameters_eqs.append(resolved_mode_expression)
                self._runtime_mode_uids.add(runtime_var.uid)

        self._constant_parameters: List[Var] = list(self._static_parameter_values.keys())
        self._parameters_values: List[Const] = list(self._static_parameter_values.values())

        self._runtime_all_parameters_source: List[Var] = list(self._variable_parameters)
        self._runtime_all_eqs_source: List[Any] = list(self._event_parameters_eqs)

        self._runtime_continuous_parameters: List[Var] = list()
        self._runtime_mode_parameters: List[Var] = list()

        self._runtime_continuous_eqs: List[Any] = list()
        self._runtime_mode_eqs: List[Any] = list()

        self._runtime_continuous_slice: slice = slice(0, 0)
        self._runtime_mode_slice: slice = slice(0, 0)

        if vars_glob_name2uid is None:
            self._vars_glob_name2uid: Dict[str, int] = dict()
        else:
            self._vars_glob_name2uid = dict(vars_glob_name2uid)

        self._rebuild_runtime_parameter_partition()

        self.init_guess: Dict[int, float] = dict()
        self.event_params_init_dict: Dict[int, float | int | complex | None] = dict()
        for runtime_var in self._variable_parameters:
            mapped_runtime_expr = self._api_parameter_initial_values_by_uid.get(runtime_var.uid, None)
            if mapped_runtime_expr is None or mapped_runtime_expr.value is None:
                pass
            else:
                self.event_params_init_dict[runtime_var.uid] = mapped_runtime_expr.value
        self.diff_init_guess: Dict[int, float] = dict()
        # self._vars_info: Dict[Any, List[Var]] = dict()

        self._finalize_order_and_maps()
        self._event_params_values: Vec = np.zeros(0, dtype=np.float64)
        self._constant_params_values: Vec = np.zeros(0, dtype=np.float64)
        self._build_runtime_param_vectors()

        self.progress_signal = DummySignal() if progress_signal is None else progress_signal
        self.progress_text = DummySignal(str) if progress_text is None else progress_text

    @property
    def glob_time(self) -> Var:
        """
        Return the global time symbolic variable.

        :return: Global time symbolic variable.
        """
        return self._glob_time

    @property
    def boundary_update(self) -> EmtBoundaryUpdateProtocol | None:
        """
        Return the boundary update provider consumed by EMT solvers.

        Problems without endogenous boundary logic return ``None``.
        """
        return None

    def report_progress(self, val: float) -> None:
        """
        Emit one absolute progress update.

        :param val: Progress value in percent.
        :type val: float
        :return: None
        :rtype: None
        """
        if self.progress_signal is not None:
            self.progress_signal.emit(val)
        else:
            pass

    def report_progress2(self, current: int, total: int) -> None:
        """
        Emit one progress update from a zero-based iteration index.

        :param current: Zero-based iteration index.
        :type current: int
        :param total: Total number of iterations.
        :type total: int
        :return: None
        :rtype: None
        """
        if self.progress_signal is not None:
            val: float = ((current + 1) / total) * 100
            self.progress_signal.emit(val)
        else:
            pass

    def _finalize_order_and_maps(self)->None:
        """
        Build canonical ordering, index maps and internal counters.

        :return: None
        """

        self._diff_vars = sorted(self._diff_vars, key=_get_diff_var_sort_key)

        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_vars = self._n_state + self._n_alg
        self._n_event_params = len(self._variable_parameters)
        self._n_params = len(self._constant_parameters)
        self._n_diff = len(self._diff_vars)
        self._n_algebraic = len(self._algebraic_eqs)

        self._compiler_names_dict: Dict[int, str] = dict()
        self._alias_names_dict: Dict[int, str] = dict()
        self._uid2idx_vars: Dict[int, int] = dict()
        self._uid2idx_event_params: Dict[int, int] = dict()
        self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()

        self._vars_glob_name2uid = dict(self._vars_glob_name2uid)

        i: int = 0
        for v in self._state_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            if v.name in self._vars_glob_name2uid:
                pass
            else:
                self._vars_glob_name2uid[v.name] = v.uid
            i += 1

        for v in self._algebraic_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            if v.name in self._vars_glob_name2uid:
                pass
            else:
                self._vars_glob_name2uid[v.name] = v.uid
            i += 1

        for j, p in enumerate(self._constant_parameters):
            self._compiler_names_dict[p.uid] = f"{self.CONSTANT_PARAMS_NAME}[{j}]"
            self._alias_names_dict[p.uid] = f"{self.CONSTANT_PARAMS_NAME}_{j}"
            self._uid2idx_params[p.uid] = j

        for k, p in enumerate(self._variable_parameters):
            self._compiler_names_dict[p.uid] = f"{self.VARIABLE_PARAMS_NAME}[{k}]"
            self._alias_names_dict[p.uid] = f"{self.VARIABLE_PARAMS_NAME}_{k}"
            self._uid2idx_event_params[p.uid] = k

        for k, d in enumerate(self._diff_vars):
            self._compiler_names_dict[d.uid] = f"{self.DIFF_NAME}[{k}]"
            self._alias_names_dict[d.uid] = f"{self.DIFF_NAME}_{k}"
            self._uid2idx_diff[d.uid] = k
            if d.name in self._vars_glob_name2uid:
                pass
            else:
                self._vars_glob_name2uid[d.name] = d.uid

        # Saved editor models can keep equation trees that still reference cloned
        # ``Var`` objects carrying the same uid as the canonical problem vars or
        # static parameters. Populate any missing uid-based compiler aliases from
        # the final equations so expression compilation stays robust after model
        # round-trips through the editor.
        _register_equation_variable_aliases(
            state_eqs=self._state_eqs,
            algebraic_eqs=self._algebraic_eqs,
            diff_init_eqs=self._diff_init_eqs_flat,
            init_eqs=self._init_eqs_flat,
            compiler_names_dict=self._compiler_names_dict,
            alias_names_dict=self._alias_names_dict,
        )

        self._compiler_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._uid2idx_t[self._glob_time.uid] = 0

    def _build_runtime_param_vectors(self) -> None:
        """
        Build and initialize runtime and constant parameter buffers.

        Runtime parameters are kept in a single flat vector. Continuous and mode
        families are only distinguished by slices and by the update rules applied
        later during the simulation.

        :return: None
        """
        n_runtime: int = self.get_variable_parameter_number()

        self._event_params_values = np.zeros(n_runtime, dtype=np.float64)

        if n_runtime > 0:
            self._event_params_values = self._initialize_runtime_parameter_values(0.0, seed_values=self._event_params_values)
            self._event_params_values = self.def_event_params_fn(
                self._event_params_values,
                0.0,
                defer_unavailable_dependencies=True,
            )
        else:
            pass

        self._constant_params_values = np.array(
            [parameter.value for parameter in self._parameters_values],
            dtype=np.float64
        )

    def rebuild_runtime_param_vectors(self) -> None:
        """
        Rebuild the runtime and constant parameter buffers.

        :return: None
        """
        self._build_runtime_param_vectors()

    def set_events_group(self, emt_events_group: EmtEventsGroup | None) -> None:
        """Apply a selected EMT events group to the runtime parameter equations.

        The method is generic with respect to the specific EMT templates used in the
        problem. Any runtime parameter exposed through `event_dict` / `mode_dict`
        can be reassigned with a piecewise time function driven by the selected
        group of `grid.emt_events`.
        """
        active_runtime_eqs = list(self._runtime_all_eqs_source)

        collect_events = {param.uid: list() for param in self._variable_parameters}
        uid_to_parameter = {param.uid: param for param in self._variable_parameters}
        if self.grid is None:
            emt_events = list()
        else:
            emt_events = self.grid.emt_events

        if emt_events_group is None:
            selected_events = list()
        else:
            selected_events = [
                evt for evt in emt_events
                if evt.group is not None and evt.group.idtag == emt_events_group.idtag
            ]

        for emt_evt in selected_events:
            parameter = emt_evt.parameter
            parameter_uid = parameter.uid if isinstance(parameter, Var) else None

            if parameter_uid in collect_events:
                transition_type: DynamicEventTransitionType = emt_evt.transition_type
                end_time = emt_evt.end_time

                collect_events[parameter_uid].append(
                    dict({
                        "time": float(emt_evt.time),
                        "value": float(emt_evt.value),
                        "end_time": None if end_time is None else float(end_time),
                        "transition_type": transition_type,
                    })
                )

        for parameter_uid, event_specs in collect_events.items():
            if len(event_specs) == 0:
                pass
            else:
                parameter = uid_to_parameter[parameter_uid]
                param_index = self._variable_parameters.index(parameter)
                active_expr = active_runtime_eqs[param_index]
                sorted_specs = sorted(event_specs, key=_emt_event_spec_time_sort_key)

                for event_spec in sorted_specs:
                    if event_spec["transition_type"] == DynamicEventTransitionType.Ramp:
                        start_time = float(event_spec["time"])
                        end_time_raw = event_spec["end_time"]

                        if end_time_raw is None:
                            raise ValueError("Ramp EMT events require an end_time")
                        else:
                            pass

                        end_time = float(end_time_raw)

                        if end_time > start_time:
                            pass
                        else:
                            raise ValueError("Ramp EMT events require end_time greater than time")

                        active_expr = _build_ramp_runtime_expr(
                            time_var=self._glob_time,
                            start_time=start_time,
                            end_time=end_time,
                            before_expr=active_expr,
                            final_value=float(event_spec["value"]),
                        )
                    else:
                        active_expr = piecewise(
                            time_var=self._glob_time,
                            t_events=np.asarray([float(event_spec["time"])], dtype=np.float64),
                            new_values=np.asarray([float(event_spec["value"] )], dtype=np.float64),
                            default_value=active_expr,
                        )

                active_runtime_eqs[param_index] = active_expr

        self._runtime_all_eqs_source = active_runtime_eqs
        self._rebuild_runtime_parameter_partition()
        self._build_runtime_param_vectors()

    def reset_boundary_update_state(self, t0: float = 0.0) -> None:
        """
        Reset runtime parameter values before a new EMT simulation starts.

        :param t0: Initial simulation time.
        :return: None
        """
        self._event_params_values = self._initialize_runtime_parameter_values(float(t0), seed_values=self._event_params_values)
        self._event_params_values = self.def_event_params_fn(self._event_params_values, float(t0))

    def get_compiler_names_dict(self) -> Dict[int, str]:
        """
        Return the compiler-name mapping used by symbolic kernels.

        :return: Compiler-name dictionary.
        """
        return dict(self._compiler_names_dict)

    def get_alias_names_dict(self) -> Dict[int, str]:
        """
        Return the alias-name mapping used by symbolic kernels.

        :return: Alias-name dictionary.
        """
        return dict(self._alias_names_dict)

    def get_event_parameter_equations(self) -> List[Any]:
        """
        Return the runtime event-parameter equations.

        :return: Event-parameter equations.
        """
        return list(self._event_parameters_eqs)

    def _rebuild_runtime_parameter_partition(self) -> None:
        """
        Rebuild the runtime parameter partition.

        The runtime parameters are stored in a single flat vector, but their
        order is redefined so that continuous runtime inputs appear first and
        retained discrete mode parameters appear afterwards.

        :return: None
        """
        self._runtime_continuous_parameters = list()
        self._runtime_mode_parameters = list()

        self._runtime_continuous_eqs = list()
        self._runtime_mode_eqs = list()

        n_source: int = len(self._runtime_all_parameters_source)
        i: int = 0

        while i < n_source:
            parameter: Var = self._runtime_all_parameters_source[i]
            equation: Any = self._runtime_all_eqs_source[i]

            if parameter.uid in self._runtime_mode_uids:
                self._runtime_mode_parameters.append(parameter)
                self._runtime_mode_eqs.append(equation)
            else:
                self._runtime_continuous_parameters.append(parameter)
                self._runtime_continuous_eqs.append(equation)

            i += 1

        self._variable_parameters = list()
        self._event_parameters_eqs = list()

        for parameter in self._runtime_continuous_parameters:
            self._variable_parameters.append(parameter)

        for parameter in self._runtime_mode_parameters:
            self._variable_parameters.append(parameter)

        for equation in self._runtime_continuous_eqs:
            self._event_parameters_eqs.append(equation)

        for equation in self._runtime_mode_eqs:
            self._event_parameters_eqs.append(equation)

        n_continuous: int = len(self._runtime_continuous_parameters)
        n_mode: int = len(self._runtime_mode_parameters)

        self._runtime_continuous_slice = slice(0, n_continuous)
        self._runtime_mode_slice = slice(n_continuous, n_continuous + n_mode)

    def refresh_runtime_equations_from_hierarchy(self) -> None:
        """
        Refresh canonical runtime equations from the current block hierarchy.

        :return: None
        """
        runtime_equation_lookup: Dict[int, Any] = _collect_hierarchical_runtime_equations(self.sys_block)
        refreshed_equations: List[Any] = list()
        runtime_parameter: Var

        for runtime_parameter in self._runtime_all_parameters_source:
            mapped_runtime_expression: Const | None = self._api_parameter_initial_values_by_uid.get(
                runtime_parameter.uid,
                None,
            )
            if mapped_runtime_expression is not None:
                # API-object initialization has precedence over the template
                # fallback and must remain the baseline used to build events.
                refreshed_equations.append(mapped_runtime_expression)
            elif runtime_parameter.uid in runtime_equation_lookup:
                refreshed_equations.append(runtime_equation_lookup[runtime_parameter.uid])
            else:
                runtime_idx: int | None = self.uid2idx_event_params.get(runtime_parameter.uid, None)
                if runtime_idx is None or runtime_idx >= len(self._event_parameters_eqs):
                    refreshed_equations.append(Const(None))
                else:
                    refreshed_equations.append(self._event_parameters_eqs[runtime_idx])

        self._runtime_all_eqs_source = refreshed_equations
        self._rebuild_runtime_parameter_partition()

    def set_runtime_mode_parameters(self, mode_parameters: List[Var]) -> None:
        """
        Classify a subset of runtime parameters as retained discrete mode parameters.

        The physical storage remains a single flat runtime vector. This method
        only changes the semantic partition and rebuilds the associated index maps
        and runtime initialization buffers.

        :param mode_parameters: Runtime parameters to classify as mode parameters.
        :return: None
        """
        valid_runtime_uids: set[int] = set()
        selected_mode_uids: set[int] = set()

        for parameter in self._runtime_all_parameters_source:
            valid_runtime_uids.add(parameter.uid)

        for parameter in mode_parameters:
            if parameter.uid in valid_runtime_uids:
                selected_mode_uids.add(parameter.uid)
            else:
                raise KeyError(
                    f"Runtime mode parameter uid={parameter.uid} does not belong to the runtime parameter source."
                )

        self._runtime_mode_uids = selected_mode_uids
        self._rebuild_runtime_parameter_partition()
        self._finalize_order_and_maps()
        self._build_runtime_param_vectors()

    def _initialize_runtime_parameter_values(self, tm: float, seed_values: Optional[Vec] = None) -> Vec:
        """
        Initialize the flat runtime parameter vector at a given time.

        This method evaluates the full runtime parameter list once in the final
        flat order. It is used for initialization only. Continuous parameters are
        then refined afterwards by def_event_params_fn().

        :param tm: Initialization time.
        :return: Initialized runtime parameter vector.
        """
        n_runtime: int = len(self._variable_parameters)
        out: Vec = np.zeros(n_runtime, dtype=np.float64)

        if seed_values is None:
            pass
        else:
            n_seed: int = min(len(seed_values), n_runtime)
            out[:n_seed] = seed_values[:n_seed]

        i: int = 0
        while i < n_runtime:
            expression: Any = self._event_parameters_eqs[i]
            if isinstance(expression, Const) and expression.value is None:
                out[i] = float(out[i])
            elif isinstance(expression, Expr) and not self._runtime_expression_dependencies_available(expression):
                # Runtime initialization happens once while the generic problem
                # storage is being assembled and again after explicit/native
                # initialization.  A model-owned runtime expression may depend
                # on algebraic or state values that are intentionally unavailable
                # during the first pass.  Preserve its provisional seed here;
                # explicit initialization will resolve the expression through
                # the full dependency graph and promote the resulting scalar.
                out[i] = float(out[i])
            else:
                out[i] = self._evaluate_runtime_expression(expression, out, tm)
            i += 1

        return out

    def _runtime_expression_dependencies_available(self, expression: Expr) -> bool:
        """Return whether a runtime expression can be evaluated at this stage.

        Runtime and constant parameters are always represented in the problem
        vectors. Algebraic, state, and differential variables become available
        only after an initialization value has been assigned. Variables owned by
        a connected sibling block are deliberately deferred to the explicit
        initialization graph, which supplies its external UID bindings.

        :param expression: Runtime initialization expression to inspect.
        :return: ``True`` when every referenced variable has a usable binding.
        """
        for variable in expression.get_vars():
            if variable.uid == self._glob_time.uid or variable.name in {"time", self.TIME_NAME}:
                pass
            elif variable.uid in self._uid2idx_event_params:
                pass
            elif variable.uid in self._uid2idx_params:
                pass
            elif variable.uid in self._uid2idx_vars:
                if self.init_guess.get(variable.uid, None) is None:
                    return False
            elif variable.uid in self._uid2idx_diff:
                if self.diff_init_guess.get(variable.uid, None) is None:
                    return False
            else:
                return False

        return True

    def _evaluate_runtime_expression(self, expression: Any, runtime_params: Vec, tm: float) -> float:
        """
        Evaluate a runtime parameter expression.

        The evaluation uses UID-based bindings to avoid ambiguous name-based
        dispatch and to keep the runtime parameter update logic deterministic.

        :param expression: Symbolic or numeric expression.
        :param runtime_params: Current flat runtime parameter vector.
        :param tm: Current time.
        :return: Numeric value of the expression.
        """
        if isinstance(expression, Const):
            if expression.value is None:
                return 0.0
            else:
                return float(expression.value)

        elif isinstance(expression, Var):
            if expression.uid == self._glob_time.uid or expression.name in {"time", self.TIME_NAME}:
                return float(tm)
            else:
                idx_runtime: int | None = self._uid2idx_event_params.get(expression.uid, None)
                if idx_runtime is not None:
                    return float(runtime_params[idx_runtime])
                else:
                    idx_const: int | None = self._uid2idx_params.get(expression.uid, None)
                    if idx_const is not None:
                        return float(self._parameters_values[idx_const].value)
                    else:
                        idx_var: int | None = self._uid2idx_vars.get(expression.uid, None)
                        if idx_var is not None:
                            init_value: float | int | complex | None = self.init_guess.get(expression.uid, None)
                            if init_value is None:
                                raise ValueError(
                                    f"EMT runtime variable '{expression.name}' "
                                    + f"(uid={expression.uid}) has no initialized state value."
                                )
                            else:
                                return float(init_value)
                        else:
                            idx_diff: int | None = self._uid2idx_diff.get(expression.uid, None)
                            if idx_diff is not None:
                                diff_init_value: float | int | complex | None = self.diff_init_guess.get(expression.uid, None)
                                if diff_init_value is None:
                                    raise ValueError(
                                        f"EMT runtime variable '{expression.name}' "
                                        + f"(uid={expression.uid}) has no initialized differential value."
                                    )
                                else:
                                    return float(diff_init_value)
                            else:
                                raise KeyError(
                                    f"EMT runtime expression variable '{expression.name}' "
                                    + f"(uid={expression.uid}) is not registered."
                                )

        elif isinstance(expression, Expr):
            uid_bindings: Dict[int, float] = dict()
            uid: int
            idx: int
            init_value: float | int | complex | None
            diff_init_value: float | int | complex | None
            var: Var

            for uid, idx in self._uid2idx_event_params.items():
                uid_bindings[uid] = float(runtime_params[idx])

            for uid, idx in self._uid2idx_params.items():
                uid_bindings[uid] = float(self._parameters_values[idx].value)

            # Runtime mode parameters such as delayed outputs may depend on the
            # already initialized algebraic, state, and differential values of
            # the EMT problem. The broader explicit-initialization algorithm has
            # already assembled those guesses before this runtime initialization
            # stage runs, so we expose them here as UID bindings. This lets one
            # retained mode variable start from the same operating point as the
            # algebraic signal it delays.
            for uid, idx in self._uid2idx_vars.items():
                init_value = self.init_guess.get(uid, None)
                if init_value is None:
                    pass
                else:
                    uid_bindings[uid] = float(init_value)

            for uid, idx in self._uid2idx_diff.items():
                diff_init_value = self.diff_init_guess.get(uid, None)
                if diff_init_value is None:
                    pass
                else:
                    uid_bindings[uid] = float(diff_init_value)

            uid_bindings[self._glob_time.uid] = float(tm)
            for var in expression.get_vars():
                if var.name in {"time", self.TIME_NAME}:
                    uid_bindings[var.uid] = float(tm)

            return float(expression.eval_uid(uid_bindings))

        else:
            return float(expression)


    def get_state_vars(self)->List[Var]:
        """
        Return the ordered list of state variables.

        :return: Ordered list of state variables.
        """
        return self._state_vars


    def get_algebraic_vars(self)->List[Var]:
        """
        Return the ordered list of algebraic variables.

        :return: Ordered list of algebraic variables.
        """
        return self._algebraic_vars

    def state_and_algebraic_vars(self) -> List[Var]:
        """
        :return:
        """
        variables = list()
        for lst in [self._state_vars, self._algebraic_vars]:
            for var in lst:
                variables.append(var)

        return variables


    def get_state_eqs(self)->List[Any]:
        """
        Return the ordered list of state equations.

        :return: Ordered list of state equations.
        """
        return self._state_eqs


    def get_algebraic_eqs(self)->List[Any]:
        """
        Return the ordered list of algebraic equations.

        :return: Ordered list of algebraic equations.
        """
        return self._algebraic_eqs


    def get_variable_parameters(self)-> List[Var]:
        """
        Return the ordered list of runtime parameters.

        :return: Ordered list of runtime parameters.
        """
        return self._variable_parameters


    def get_constant_parameters(self)-> List[Var]:
        """
        Return the ordered list of constant parameters.

        :return: Ordered list of constant parameters.
        """
        return self._constant_parameters


    def get_diff_vars(self)-> List[Var]:
        """
        Return the ordered list of differential variables.

        :return: Ordered list of differential variables.
        """
        return self._diff_vars


    def get_parameters_values(self)-> List[Const]:
        """
        Return the ordered list of constant parameter values.

        :return: Ordered list of constant parameter values.
        """
        return self._parameters_values

    def get_all_vars_number(self) -> int:
        """
        Return the total number of state and algebraic variables.

        :return: Total number of variables.
        """
        return self._n_vars

    def get_diff_var_number(self) -> int:
        """
        Return the number of differential variables.

        :return: Number of differential variables.
        """
        return self._n_diff

    def get_algebraic_var_number(self) -> int:
        """
        Return the number of algebraic variables.

        :return: Number of algebraic variables.
        """
        return self._n_alg

    def get_states_number(self) -> int:
        """
        Return the number of state variables.

        :return: Number of state variables.
        """
        return self._n_state

    def get_variable_parameter_number(self) -> int:
        """
        Return the number of runtime parameters.

        :return: Number of runtime parameters.
        """
        return self._n_event_params

    def get_x0(self) -> Vec:
        """
        Build the initial state vector from the stored initialization guess.

        :return: Initial state vector.
        """
        x = np.zeros(self._n_vars, dtype=np.float64)
        for uid, val in self.init_guess.items():
            idx = self._uid2idx_vars.get(uid, None)
            if idx is not None:
                value_float: float = float(val)
                if np.isfinite(value_float):
                    x[idx] = value_float
                else:
                    pass
            else:
                pass

        return x

    def get_dx0(self) -> Vec:
        """
        Build the initial differential vector from the stored differential initialization guess.

        :return: Initial differential vector.
        """
        dx = np.zeros(self._n_diff, dtype=np.float64)
        for uid, val in self.diff_init_guess.items():
            idx = self._uid2idx_diff.get(uid, None)
            if idx is not None:
                value_float: float = float(val)
                if np.isfinite(value_float):
                    dx[idx] = value_float
                else:
                    pass
            else:
                pass
        return dx

    def set_x0(self, x0: Vec) -> None:
        """
        Set the initial state vector guess from an array.

        :param x0: Initial state vector.
        :type x0: Vec
        :return: None.
        """
        for uid, idx in self._uid2idx_vars.items():
            if idx < len(x0):
                self.init_guess[uid] = float(x0[idx])
            else:
                pass

    def set_dx0(self, dx0: Vec) -> None:
        """
        Set the initial differential vector guess from an array.

        :param dx0: Initial differential vector.
        :type dx0: Vec
        :return: None.
        """
        for uid, idx in self._uid2idx_diff.items():
            if idx < len(dx0):
                self.diff_init_guess[uid] = float(dx0[idx])
            else:
                pass

    def def_event_params_fn(
            self,
            ev_param: Vec,
            tm: float,
            defer_unavailable_dependencies: bool = False,
    ) -> Vec:
        """
        Update only the continuous runtime parameter slice.

        Retained discrete mode parameters are preserved exactly as they enter
        this function. They are expected to be modified explicitly by the
        boundary update layer or by future event logic.

        :param ev_param: Current flat runtime parameter vector.
        :param tm: Current simulation time.
        :param defer_unavailable_dependencies: Preserve the current value when
            construction-time algebraic/state dependencies are not initialized.
        :return: Updated flat runtime parameter vector.
        """
        n_continuous: int = len(self._runtime_continuous_eqs)

        if n_continuous == 0:
            return ev_param
        else:
            out: Vec = ev_param.copy()

            i: int = 0
            while i < n_continuous:
                global_idx: int = self._runtime_continuous_slice.start + i
                expression: Any = self._runtime_continuous_eqs[i]

                if (
                    defer_unavailable_dependencies
                    and isinstance(expression, Expr)
                    and not self._runtime_expression_dependencies_available(expression)
                ):
                    pass
                else:
                    out[global_idx] = self._evaluate_runtime_expression(expression, out, tm)
                i += 1

            return out

    def update_variable_params(self, t: float) -> None:
        """
        Update the internal runtime parameter values at the given time.

        :param t: Current time.
        :return: None
        """
        self._event_params_values = self.def_event_params_fn(self._event_params_values, float(t))

    def get_full_param_index(self, uid: int) -> int:
        """
        Return the flat full-parameter index associated with the given UID.

        :param uid: Parameter unique identifier.
        :return: Flat index inside the full parameter vector.
        """
        n_ev = len(self._variable_parameters)
        if uid in self._uid2idx_event_params:
            return self._uid2idx_event_params[uid]
        if uid in self._uid2idx_params:
            return n_ev + self._uid2idx_params[uid]
        raise KeyError(f"Unknown param uid={uid}")

    def get_newton_trace_collector(self) -> Optional[Any]:
        """
        Return the Newton trace collector instance.

        :return: Newton trace collector instance or None.
        """
        return self._newton_trace_collector

    def set_newton_trace_collector(self, collector: Any)->None:
        """
        Set the Newton trace collector instance.

        :param collector: Newton trace collector instance.
        :return: None
        """
        self._newton_trace_collector = collector

    # def get_device_vars_dict(self) -> Dict[Any, List[Var]]:
    #     """
    #     Return the device-to-variable mapping dictionary.
    #
    #     :return: Device-to-variable mapping dictionary.
    #     """
    #     return self._vars_info

    def get_var_idx(self, v: Var) -> int:
        """
        Return the flat variable index associated with the given variable.

        :param v: Variable to locate.
        :return: Flat variable index.
        """
        return self._uid2idx_vars[v.uid]

    def get_diff_var_idx(self, dv: Var) -> int:
        """
        Return the flat differential index associated with the given differential variable.

        :param dv: Differential variable to locate.
        :return: Flat differential index.
        """
        return self._uid2idx_diff[dv.uid]

    @property
    def vars_glob_name2uid(self) -> Dict[str, int]:
        """
        :return:
        """
        return self._vars_glob_name2uid

    # def set_init_guess(self, mdl: Block, reference_powerflow: VarPowerFlowReferenceType, val: float) -> None:
    #     """
    #     Set the initialization guess associated with a model external mapping.
    #
    #     :param mdl: Model block containing the external mapping.
    #     :param reference_powerflow: Reference key used to locate the mapped variable.
    #     :param val: Initialization value.
    #     :return: None
    #     """
    #     external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(mdl)
    #
    #     if external_mapping is None:
    #         pass
    #     else:
    #         var: Optional[Var] = external_mapping.get(reference_powerflow, None)
    #
    #         if var is None:
    #             pass
    #         else:
    #             self.init_guess[var.uid] = float(val)



    def get_floquet_ak_stack(
            self,
            trajectory: np.ndarray,
            h: float,
            jac_evaluator: Optional[Any] = None,
            static_params: Optional[Vec] = None
    ) -> Optional[np.ndarray]:
        """
        Return the stack of transition matrices used for Floquet analysis.

        :param trajectory: State trajectory over one period.
        :param h: Time step.
        :param jac_evaluator: Optional Jacobian evaluator.
        :param static_params: Optional static parameter vector.
        :return: Stack of transition matrices or None.
        """
        return None

    def get_runtime_continuous_slice(self) -> slice:
        """
        Return the slice of continuous runtime inputs inside the flat runtime vector.

        :return: Continuous runtime slice.
        """
        return self._runtime_continuous_slice

    def get_runtime_mode_slice(self) -> slice:
        """
        Return the slice of retained mode parameters inside the flat runtime vector.

        :return: Mode runtime slice.
        """
        return self._runtime_mode_slice

    def get_runtime_continuous_parameters(self) -> List[Var]:
        """
        Return the ordered list of continuous runtime parameters.

        :return: Continuous runtime parameters.
        """
        return self._runtime_continuous_parameters

    def get_runtime_mode_parameters(self) -> List[Var]:
        """
        Return the ordered list of retained mode runtime parameters.

        :return: Mode runtime parameters.
        """
        return self._runtime_mode_parameters

    @property
    def uid2idx_vars(self)-> Dict[int, int]:
        """
        Return the UID-to-variable-index mapping.

        :return: UID-to-variable-index mapping.
        """
        return self._uid2idx_vars

    @property
    def uid2idx_params(self)-> Dict[int, int]:
        """
        Return the UID-to-constant-parameter-index mapping.

        :return: UID-to-constant-parameter-index mapping.
        """
        return self._uid2idx_params

    @property
    def uid2idx_event_params(self)-> Dict[int, int]:
        """
        Return the UID-to-runtime-parameter-index mapping.

        :return: UID-to-runtime-parameter-index mapping.
        """
        return self._uid2idx_event_params

    @property
    def uid2idx_diff(self)-> Dict[int, int]:
        """
        Return the UID-to-differential-index mapping.

        :return: UID-to-differential-index mapping.
        """
        return self._uid2idx_diff

    @property
    def event_params_values(self)-> Vec:
        """
        Return the current flat runtime parameter vector.

        :return: Current flat runtime parameter vector.
        """
        return self._event_params_values

    @property
    def event_parameters_eqs(self) -> List[Any]:
        return self._event_parameters_eqs
