# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Dict, List, Callable, Any, Tuple, Set, Optional
import time
import numpy as np
import pandas as pd
import scipy.sparse as sp

from VeraGridEngine.enumerations import DynamicEventTransitionType
from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr, eval_uid as eval_expr_uid, piecewise,
                                                    get_expression_vars, hard_sat)
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicParamsVector, SymbolicDerivative, SymbolicJacobian
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import (
    DynamicSimulationMode,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
    RmsInitializationMethod,
)
from VeraGridEngine.basic_structures import Vec, ObjVec, BoolVec, Logger
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import (
    ExplicitInitializationResult,
    build_explicit_external_uid_values,
    build_rms_single_equation_compiler,
    init_explicit_common,
)
from VeraGridEngine.Simulations.Rms.initialization import init_pseudo_transient, _select_rms_initialization_method
from VeraGridEngine.Simulations.Rms.initialization_rms import run_rms_consistent_initialization
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import (
    RmsProblemTemplate,
    rectangular_current_from_power,
)
from VeraGridEngine.Simulations.Rms.problems.rms_terminal_power_assembly import (
    assemble_rms_mapped_power_references,
)
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler, ProceduralExpressionCompiler
from VeraGridEngine.Utils.Symbolic.bus_rms_template import (
    build_dc_bus_nodal_power_equation,
    dc_bus_rms_model_has_capacitive_state,
    get_bus_rms_algebraic_vars,
)
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block, ProceduralExpressionMode
from VeraGridEngine.Utils.procedural_logic_contract import ManufacturerNativeRuntimeSessionProtocol
from VeraGridEngine.IO.fmu.co_simulation import (
    advance_rms_fmu_cs_devices,
    align_rms_fmu_cs_device_output_parameters,
    close_rms_fmu_cs_devices,
    initialize_rms_fmu_cs_devices,
    register_rms_fmu_cs_device,
)
from VeraGridEngine.IO.fmu.model_exchange import (
    advance_rms_fmu_me_devices,
    close_rms_fmu_me_devices,
    get_next_rms_fmu_me_event_time,
    initialize_rms_fmu_me_devices,
    _prepare_rms_fmu_me_state_event_retry,
    register_rms_fmu_me_device,
    resolve_rms_fmu_me_devices,
)
from VeraGridEngine.IO.fmu.profile import FmuMeEvaluationBudget

from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import (
    StaticParameterMappingDiagnostics,
    assign_static_api_object_mapping_for_device,
    get_api_parameter_initial_value_by_uid,
    resolve_constant_parameter_initial_value,
    resolve_runtime_parameter_initial_expression,
)


from VeraGridEngine.Utils.procedural_logic import BlockProceduralLogicUpdater


def _tic():
    return time.perf_counter()


def _toc(t0):
    return time.perf_counter() - t0


def build_inactive_bus_boundary_equations(
        bus: Bus,
        init_guess: Dict[int, float | int | complex | None],
) -> List[Expr]:
    """
    Build algebraic boundary equations for one isolated inactive bus.

    Inactive buses can remain stored in legacy grids without any connected
    active network element.  Their RMS voltage variables are still present in
    the bus block, but nodal P/Q balances do not exist.  Fixing those detached
    algebraic variables at the power-flow initial point removes them from the
    active DAE without adding electrical behavior to the network.

    :param bus: Isolated inactive bus owning the RMS voltage variables.
    :param init_guess: Global RMS initial-value lookup keyed by variable uid.
    :return: One DC or two AC voltage boundary equations.
    """
    boundary_equations: List[Expr] = list()
    vdc: Var | None
    vm: Var | None
    va: Var | None
    vdc, vm, va = get_bus_rms_algebraic_vars(bus_rms_model=bus.rms_model)

    if vdc is not None:
        vdc_initial_raw: float | int | complex | None = init_guess.get(vdc.uid, 1.0)
        if vdc_initial_raw is None or not np.isfinite(vdc_initial_raw):
            vdc_initial: float = 1.0
        else:
            vdc_initial = float(np.real(vdc_initial_raw))
        boundary_equations.append(vdc - Const(vdc_initial))
    elif vm is not None and va is not None:
        vm_initial_raw: float | int | complex | None = init_guess.get(vm.uid, 1.0)
        va_initial_raw: float | int | complex | None = init_guess.get(va.uid, 0.0)
        if vm_initial_raw is None or not np.isfinite(vm_initial_raw):
            vm_initial: float = 1.0
        else:
            vm_initial = float(np.real(vm_initial_raw))
        if va_initial_raw is None or not np.isfinite(va_initial_raw):
            va_initial: float = 0.0
        else:
            va_initial = float(np.real(va_initial_raw))
        boundary_equations.append(vm - Const(vm_initial))
        boundary_equations.append(va - Const(va_initial))
    else:
        pass

    return boundary_equations


def _is_time_aligned(t_curr: float, event_time: float) -> bool:
    """
    Return whether ``t_curr`` is aligned with ``event_time`` within numeric tolerance.
    """
    machine_eps: float = float(np.finfo(np.float64).eps)
    time_tol: float = 10.0 * machine_eps * max(1.0, abs(event_time))
    return bool(abs(t_curr - event_time) <= time_tol)


def _get_mode_event_sort_key(event: Tuple[float, float, bool]) -> float:
    """
    Return the sorting key of one mode event.

    :param event: Mode event tuple ``(time, value, force_step_alignment)``.
    :return: Event time.
    """
    return event[0]


def _get_next_forced_mode_event_time(
        scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]],
        t_prev: float,
        t_target: float,
) -> Optional[float]:
    """
    Return the earliest forced-alignment mode event time in ``(t_prev, t_target]``.

    :param scheduled_mode_events: Mapping uid -> sorted list of (time, value, force_step_alignment).
    :param t_prev: Previous local solver time.
    :param t_target: Nominal macro target time.
    :return: Earliest forced event time or ``None``.
    """
    next_time: Optional[float] = None

    for _, event_list in scheduled_mode_events.items():
        for event_time, _, force_step_alignment in event_list:
            if force_step_alignment and (t_prev < event_time <= t_target):
                if next_time is None or event_time < next_time:
                    next_time = event_time

    return next_time


def _is_rms_time_strictly_after_event(t_curr: float, event_time: float) -> bool:
    """
    Return whether the current RMS time is strictly after one event time.

    The RMS reference trajectories treat the event sample itself as still
    belonging to the pre-event branch. Floating-point time accumulation can make
    a nominal sample such as ``0.1`` appear as ``0.10000000000000007``. Using
    the same alignment tolerance already employed elsewhere in the solver keeps
    boundary decisions stable and prevents one-sample-early event activation.

    :param t_curr: Current solver time.
    :param event_time: Event activation time.
    :return: ``True`` only when the current time is beyond the aligned boundary.
    """

    if _is_time_aligned(t_curr=t_curr, event_time=event_time):
        return False
    else:
        return t_curr > event_time


def _build_ramp_runtime_expr(time_var: Var,
                             start_time: float,
                             end_time: float,
                             before_expr: Expr | Const,
                             final_value: float) -> Expr:
    """
    Build one linear ramp transition on top of an existing runtime expression.

    The expression keeps the previous runtime behavior before ``start_time``,
    evolves linearly toward ``final_value`` until ``end_time``, and finally holds
    the final value after the ramp completes.

    :param time_var: Global simulation time variable.
    :param start_time: Ramp start time.
    :param end_time: Ramp end time.
    :param before_expr: Expression active before the ramp starts.
    :param final_value: Final runtime value after the ramp ends.
    :return: Runtime expression including the ramp segment.
    """
    start_expr: Expr | Const = _freeze_runtime_expr_at_time(expr=before_expr,
                                                            time_var=time_var,
                                                            sample_time=start_time)
    duration_expr: Const = Const(float(end_time - start_time))
    time_offset_expr: Expr = time_var - Const(float(start_time))
    progress_expr: Expr = hard_sat(time_offset_expr / duration_expr, Const(0.0), Const(1.0))

    # The RMS symbolic backend defines ``heaviside(0)`` as zero. A gate that is
    # multiplied directly by ``heaviside(t - start_time)`` therefore keeps the
    # pre-event branch active exactly at the ramp start and can make the first
    # post-event samples look like an immediate step after implicit integration.
    # Clamping the normalized progress and blending between the frozen pre-event
    # value and the final target removes that boundary ambiguity while preserving
    # the intended linear ramp on the open interval and the final hold after the
    # ramp end.
    return start_expr + progress_expr * (Const(float(final_value)) - start_expr)


def _get_rms_event_time_sort_key(evt: RmsEvent) -> tuple[float, float]:
    """
    Build the chronological sort key for one RMS event.

    :param evt: RMS event.
    :return: Tuple containing start and end times.

    Multi-event runtime replay must apply events in deterministic time order.
    Sorting by start time first and end time second keeps the replay stable for
    any combination of step and ramp events.
    """
    end_time_value: float
    if evt.end_time is not None:
        end_time_value = float(evt.end_time)
    else:
        end_time_value = float(evt.time)

    return float(evt.time), end_time_value


def _evaluate_rms_runtime_parameter_value_from_events(base_value: float,
                                                      event_list: List[RmsEvent],
                                                      t_curr: float) -> float:
    """
    Evaluate one RMS runtime parameter by replaying its events procedurally.

    :param base_value: Baseline parameter value before any event happens.
    :param event_list: Ordered RMS events affecting the parameter.
    :param t_curr: Current simulation time.
    :return: Runtime parameter value.

    The symbolic nested ``piecewise`` composition is fragile when several events
    act on the same continuous parameter. Procedural replay is linear in the
    number of events and naturally supports any number and combination of step
    and ramp transitions.
    """
    current_value: float = float(base_value)
    event_item: RmsEvent

    for event_item in event_list:
        if event_item.transition_type == DynamicEventTransitionType.Step:
            if _is_rms_time_strictly_after_event(t_curr=t_curr, event_time=float(event_item.time)):
                current_value = float(event_item.value)
            else:
                pass
        else:
            if event_item.transition_type == DynamicEventTransitionType.Ramp:
                start_time: float = float(event_item.time)
                end_time: float | None = event_item.end_time
                ramp_start_value: float = float(current_value)

                if end_time is not None:
                    resolved_end_time: float = float(end_time)
                    if resolved_end_time > start_time:
                        if _is_rms_time_strictly_after_event(t_curr=t_curr, event_time=start_time):
                            if t_curr >= resolved_end_time:
                                current_value = float(event_item.value)
                            else:
                                ramp_progress: float = (float(t_curr) - start_time) / (resolved_end_time - start_time)
                                if ramp_progress < 0.0:
                                    ramp_progress = 0.0
                                else:
                                    if ramp_progress > 1.0:
                                        ramp_progress = 1.0
                                    else:
                                        pass

                                current_value = ramp_start_value + ramp_progress * (float(event_item.value) - ramp_start_value)
                        else:
                            pass
                    else:
                        if _is_rms_time_strictly_after_event(t_curr=t_curr, event_time=start_time):
                            current_value = float(event_item.value)
                        else:
                            pass
                else:
                    if _is_rms_time_strictly_after_event(t_curr=t_curr, event_time=start_time):
                        current_value = float(event_item.value)
                    else:
                        pass
            else:
                if _is_rms_time_strictly_after_event(t_curr=t_curr, event_time=float(event_item.time)):
                    current_value = float(event_item.value)
                else:
                    pass

    return current_value


def _build_runtime_expression_from_single_rms_event(time_var: Var,
                                                    base_expression: Expr | Const,
                                                    event_item: RmsEvent) -> Expr | Const:
    """
    Build the legacy symbolic runtime expression for one RMS event.

    :param time_var: Global simulation time variable.
    :param base_expression: Baseline runtime expression before the event.
    :param event_item: Single RMS event affecting the parameter.
    :return: Runtime expression including the event.

    The historical RMS references were generated with a symbolic event path for
    single continuous events. Preserving that exact path keeps the legacy CSV
    tests stable while the procedural replay path is reserved for true
    multi-event combinations that are fragile under nested symbolic composition.
    """
    transition_tpe: DynamicEventTransitionType = event_item.transition_type

    if transition_tpe == DynamicEventTransitionType.Ramp:
        end_time_raw: float | None = event_item.end_time
        if end_time_raw is not None:
            end_time: float = float(end_time_raw)
            start_time: float = float(event_item.time)
            if end_time > start_time:
                return _build_ramp_runtime_expr(time_var=time_var,
                                                start_time=start_time,
                                                end_time=end_time,
                                                before_expr=base_expression,
                                                final_value=float(event_item.value))
            else:
                return piecewise(time_var=time_var,
                                 t_events=np.asarray([float(event_item.time)], dtype=np.float64),
                                 new_values=np.asarray([float(event_item.value)], dtype=np.float64),
                                 default_value=base_expression)
        else:
            return piecewise(time_var=time_var,
                             t_events=np.asarray([float(event_item.time)], dtype=np.float64),
                             new_values=np.asarray([float(event_item.value)], dtype=np.float64),
                             default_value=base_expression)
    else:
        return piecewise(time_var=time_var,
                         t_events=np.asarray([float(event_item.time)], dtype=np.float64),
                         new_values=np.asarray([float(event_item.value)], dtype=np.float64),
                         default_value=base_expression)


def _is_rms_event_routed_to_scheduled_mode(
        transition_tpe: DynamicEventTransitionType,
        parameter_uid: int,
        discrete_parameter_uids: Set[int],
        continuous_parameter_uids: Set[int],
) -> bool:
    """
    Decide whether one RMS event must use the scheduled step path.

    The RMS runtime parameter layer must support two behaviors for the same
    symbolic parameter. Step events must keep the historical scheduled update
    path used by existing reference trajectories, while ramp events must stay on
    the continuous symbolic path so the runtime parameter evolves smoothly over
    time. This helper therefore routes each event from its transition profile
    first, and only falls back to the registered parameter class when the event
    profile does not force a unique path.

    :param transition_tpe: Normalized event transition type.
    :param parameter_uid: Runtime parameter unique identifier.
    :param discrete_parameter_uids: Registered discrete/mode parameter UIDs.
    :param continuous_parameter_uids: Registered continuous parameter UIDs.
    :return: ``True`` when the event must use scheduled step handling.
    """

    if transition_tpe == DynamicEventTransitionType.Step:
        return True
    else:
        if transition_tpe == DynamicEventTransitionType.Ramp:
            return False
        else:
            if parameter_uid in discrete_parameter_uids:
                return True
            else:
                if parameter_uid in continuous_parameter_uids:
                    return False
                else:
                    return True


def _freeze_runtime_expr_at_time(expr: Expr | Const,
                                 time_var: Var,
                                 sample_time: float) -> Expr | Const:
    """
    Freeze one runtime expression at a specific time sample.

    The ramp interpolation must start from the pre-event runtime value evaluated
    exactly at the ramp start. Replacing the symbolic time variable by the start
    time preserves that baseline even when the pre-event expression also depends
    on time.

    :param expr: Runtime expression to freeze.
    :param time_var: Global simulation time variable.
    :param sample_time: Time sample used to freeze the expression.
    :return: Expression evaluated at the supplied time sample.
    """
    if isinstance(expr, Const):
        return expr
    else:
        time_binding: Dict[Var, Expr] = dict({time_var: Const(float(sample_time))})
        return expr.subs(time_binding)


def setP(P: ObjVec, P_used: BoolVec, k: int, val: object):
    """

    :param P:
    :param P_used:
    :param k:
    :param val:
    :return:
    """
    if not P_used[k]:
        P[k] = val
        P_used[k] = True
    else:
        P[k] += val


def setQ(Q: ObjVec, Q_used: BoolVec, k: int, val: object):
    """

    :param Q:
    :param Q_used:
    :param k:
    :param val:
    :return:
    """
    if not Q_used[k]:
        Q[k] = val
        Q_used[k] = True
    else:
        Q[k] += val


def _run_rms_model_pseudo_transient(*,
                                    auto_fallback: bool,
                                    **kwargs) -> Dict[int, float]:
    """Run model-wise PTC, allowing Auto to continue to global Newton on failure."""
    try:
        return init_pseudo_transient(**kwargs)
    except RuntimeError as error:
        if not auto_fallback:
            raise
        if kwargs.get("verbose", False):
            print(f"[RMS Auto] model-wise pseudo-transient failed; continuing to global Newton: {error}")
        return kwargs["init_guess"]


class RmsProblemDae(RmsProblemTemplate):
    """
    DAE (Differential-Algebraic Equation) class to store and manage.

    Responsibilities:
        - Store state and algebraic variables (x, y)
        - Store Jacobian matrices
        - Store residual equations
        - Store sparsity patterns
    """
    VARS_NAME = "vrs"
    VARIABLE_PARAMS_NAME = "vprms"
    CONSTANT_PARAMS_NAME = "cprms"
    DIFF_NAME = "diff"
    TIME_NAME = "glob_time"

    __slots__ = (
        "Sf",
        "St",
        "options",
        "logger",
        "init_guess",
        "event_params_init_dict",
        "sys_block",
        "sys_vars",
        "_algebraic_vars",
        "_algebraic_eqs",
        "_small_signal_reference_row",
        "_small_signal_reference_column",
        "_state_vars",
        "_state_eqs",
        "_diff_vars",
        "_variable_parameters",
        "_event_parameters_eqs0",
        "_event_parameters_eqs",
        "_constant_parameters",
        "_parameters_values",
        "_static_parameters_values_mapping",
        "_static_parameter_mapping_diagnostics",
        "_runtime_all_parameters_source",
        "_runtime_all_eqs_source",
        "_runtime_continuous_parameters",
        "_runtime_mode_parameters",
        "_runtime_continuous_eqs",
        "_runtime_mode_eqs",
        "_event_parameter_device_idtags",
        "_runtime_all_eqs_source0",
        "_runtime_continuous_slice",
        "_runtime_mode_slice",
        "_continuous_event_parameter_uids",
        "_discrete_event_parameter_uids",
        "_continuous_runtime_events",
        "_scheduled_mode_events",
        "_mode_event_cursor",
        "_active_events_group",
        "_mode_runtime_expression_by_uid",
        "_mode_runtime_initialized_uids",
        "_procedural_logic_updater",
        "_procedural_expression_compiler",
        "_manufacturer_native_runtime_session",
        "_derivative_fn",
        "_event_params_fn",
        "_rhs_algeb_fn",
        "_rhs_state_fn",
        "_j11_fn",
        "_j12_fn",
        "_j21_fn",
        "_j22_fn",
        "_fx_ct_fn",
        "_fy_ct_fn",
        "_gx_ct_fn",
        "_gy_ct_fn",
        "_variable_parameters_values",
        "_last_variable_parameters_values",
        "_constant_params",
        "_block_boundary_updater",
        "_fmu_cs_adapters",
        "_fmu_cs_initialized",
        "_fmu_me_adapters",
        "_fmu_me_initialized",
        "_fmu_me_evaluation_budget",
        "_manufacturer_native_runtime_session",
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
        "_uid2idx_t",
        "_vars_glob_name2uid",
        "_compiler_names_dict",
        "_alias_names_dict",
        "_vars_info",
        "_glob_time",
        "_external_time_parameter",
        "_external_time_uids",
        "_state_algeb_vars",
        "_manufacturer_native_runtime_session",
    )

    def __init__(self,
                 grid: MultiCircuit,
                 options: RmsOptions,
                 pf_results: PowerFlowResults,
                 progress_signal: DummySignal | None = None,
                 progress_text: DummySignal | None = None,
                 logger: Logger | None = None):
        """

        :param grid: MultiCircuit
        :param options: RmsOptions
        :param pf_results: PowerFlowResults
        :progress_signal: DummySignal
        :progress_text: DummySignal
        :param logger: Optional logger owned by the simulation driver.
        """
        super().__init__(progress_signal=progress_signal,
                         progress_text=progress_text)

        # The driver owns the logger. Direct problem construction may remain
        # silent without changing any numerical mapping behavior.
        self.logger: Logger | None = logger
        self._static_parameter_mapping_diagnostics: StaticParameterMappingDiagnostics = (
            StaticParameterMappingDiagnostics(
                logger=self.logger,
                simulation_mode=DynamicSimulationMode.RMS,
            )
        )
        self.grid: MultiCircuit = grid
        self.power_flow_results: PowerFlowResults = pf_results
        self.Sf = self.power_flow_results.Sf / self.grid.Sbase
        self.St = self.power_flow_results.St / self.grid.Sbase
        self.options: RmsOptions = options

        # this is the general init guess that will contain all the variables init value
        self.init_guess: Dict[int, float | int | complex | None] = dict()
        self.event_params_init_dict: Dict[int, float | int | complex | None] = dict()
        self.sys_block: Block = Block(children=[], in_vars=[])
        # when vectorizing this will be a list of lists
        self._algebraic_vars: List[Var] = list()
        self._algebraic_eqs: List[Expr] = list()
        self._small_signal_reference_row: int | None = None
        self._small_signal_reference_column: int | None = None
        # when vectorizing this will be a list of lists
        self._state_vars: List[Var] = list()
        self._state_eqs: List[Expr] = list()
        self._diff_vars: List[Var] = list()
        # when vectorizing this will be a list of lists
        self._variable_parameters: List[Var] = list()
        self._event_parameters_eqs0: List[Expr | Const] = list()
        self._event_parameters_eqs: List[Expr | Const] = list()
        self._constant_parameters: List[Var] = list()
        # when vectorizing this will be a list of np.array
        self._parameters_values: List[Const] = list()
        self._static_parameters_values_mapping: Dict[Var, Const] = dict()

        self._runtime_all_parameters_source: List[Var] = list()
        self._runtime_all_eqs_source: List[Expr | Const] = list()
        self._runtime_continuous_parameters: List[Var] = list()
        self._runtime_mode_parameters: List[Var] = list()
        self._runtime_continuous_eqs: List[Expr | Const] = list()
        self._runtime_mode_eqs: List[Expr | Const] = list()
        self._event_parameter_device_idtags: Dict[int, str] = dict()
        self._runtime_all_eqs_source0: List[Expr | Const] = list()
        self._runtime_continuous_slice: slice = slice(0, 0)
        self._runtime_mode_slice: slice = slice(0, 0)
        self._continuous_event_parameter_uids: Set[int] = set()
        self._discrete_event_parameter_uids: Set[int] = set()
        self._continuous_runtime_events: Dict[int, List[RmsEvent]] = dict()
        self._scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]] = dict()
        self._mode_event_cursor: Dict[int, int] = dict()
        self._active_events_group: RmsEventsGroup | None = None
        self._mode_runtime_expression_by_uid: Dict[int, Expr | Const] = dict()
        self._mode_runtime_initialized_uids: Set[int] = set()
        self._procedural_expression_compiler: ProceduralExpressionCompiler | None = None
        self._procedural_logic_updater: BlockProceduralLogicUpdater | None = None
        self._manufacturer_native_runtime_session: ManufacturerNativeRuntimeSessionProtocol | None = None

        # function pointers
        self._derivative_fn: SymbolicDerivative | None = None
        self._event_params_fn: SymbolicParamsVector | None = None
        self._rhs_algeb_fn: Callable[[Vec, Vec, Vec, Vec], Vec] | None = None
        self._rhs_state_fn: Callable[[Vec, Vec, Vec, Vec], Vec] | None = None
        self._j11_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None
        self._j12_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None
        self._j21_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None
        self._j22_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None
        self._fx_ct_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None
        self._fy_ct_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None
        self._gx_ct_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None
        self._gy_ct_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None

        self._variable_parameters_values: Optional[Vec] = None
        self._last_variable_parameters_values: Optional[Vec] = None
        self._constant_params: Optional[Vec] = None
        self._block_boundary_updater: Any | None = None
        self._fmu_cs_adapters: List[object] = list()
        self._fmu_cs_initialized: bool = False
        self._fmu_me_adapters: List[object] = list()
        self._fmu_me_initialized: bool = False
        self._fmu_me_evaluation_budget: FmuMeEvaluationBudget | None = None

        # --------------------------------------------------------------------------------------------------------------
        # Initialize the RMS problem
        # --------------------------------------------------------------------------------------------------------------

        ######################### Initialize containers#############################
        total_init_explicit_time: float = 0
        t0 = time.perf_counter()
        diff_init_guess_common: Dict[int, float | int | complex | None] = dict()

        # dictionaries to store device-variable ifo
        self._vars_info: Dict[ALL_DEV_TYPES, List[Var]] = dict()
        self._vars_glob_name2uid: Dict[str, int] = dict()

        # dictionaries for compilation names
        self._compiler_names_dict: Dict[int, str] = dict()
        self._alias_names_dict: Dict[int, str] = dict()

        # dictionaries for variable position in the variables arrays
        self._uid2idx_vars: Dict[int, int] = dict()
        self._uid2idx_event_params: Dict[int, int] = dict()
        self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()

        # We put algebraic_vars that are actually states first
        self._algebraic_vars.sort(key=lambda obj: obj.diff_var is None)
        diff_vars_from_states = [var.diff_var for var in self._state_vars]
        for i, var in enumerate(diff_vars_from_states):
            state_var = self._state_vars[i]
            if var is None:
                diff_vars_from_states[i] = self.grid.var_factory.add_diff_var(name='aux', base_var=state_var)
        diff_vars_from_algebraic = [var.diff_var for var in self._algebraic_vars if var.diff_var is not None]
        self._diff_vars = diff_vars_from_states + diff_vars_from_algebraic


        # create time global time variable and add it to the compilation dict
        self._glob_time: Var = Var(self.TIME_NAME)
        self._compiler_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._uid2idx_t[self._glob_time.uid] = 0
        self._external_time_parameter: Var = Var("rms_external_time")
        self._external_time_uids: Set[int] = set()

        # Dictionary of state and algebraic vars
        self.sys_vars: Dict[int, Var] = dict()

        # initialize balance equation arrays
        n = len(self.grid.buses)
        P: ObjVec = np.zeros(n, dtype=object)
        Q: ObjVec = np.zeros(n, dtype=object)
        P_used: BoolVec = np.zeros(n, dtype=bool)
        Q_used: BoolVec = np.zeros(n, dtype=bool)

        # general indexes for variables and parameters
        self._n_vars = 0
        self._n_params = 0
        self._n_event_params = 0
        self._n_diff = 0

        ######################################## Initialize devices ########################################

        # initialize buses
        bus_dict: Dict[Bus, int] = dict()

        for bus_num, elm in enumerate(self.grid.buses):

            bus_dict[elm] = bus_num

            self.add_variables_to_compilation_dicts(elm, elm.rms_model)

            # add init values from powerflow to initial guess
            if elm.is_dc:
                # DC bus: use Vdc (magnitude) - angle is not applicable for DC
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Vdc,
                                    float(np.abs(self.power_flow_results.voltage[bus_num])))
            else:
                # AC bus: use Vm and Va
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Vm,
                                    float(np.abs(self.power_flow_results.voltage[bus_num])))
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Va,
                                    float(np.angle(self.power_flow_results.voltage[bus_num])))

            # add model to system block
            self.sys_block.add(elm.rms_model)

        # initialize branches
        for branch_num, elm in enumerate(self.grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True)):

            if elm.rms_model.empty():
                if self.logger is not None:
                    self.logger.add_error("No RMS model",
                                          device_class=elm.device_type.value,
                                          device=elm.name)
                else:
                    pass
            else:

                assign_static_api_object_mapping_for_device(grid=self.grid,
                                                            device=elm,
                                                            mdl=elm.rms_model,
                                                            problem_mapping=self._static_parameters_values_mapping,
                                                            logger=self._static_parameter_mapping_diagnostics)

                self.add_variables_to_compilation_dicts(elm, elm.rms_model)
                register_rms_fmu_cs_device(self, elm, elm.rms_model)
                register_rms_fmu_me_device(self, elm, elm.rms_model)

                # add init values from powerflow to initial guess
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Pf, self.Sf[branch_num].real)
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Qf, self.Sf[branch_num].imag)
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Pt, self.St[branch_num].real)
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Qt, self.St[branch_num].imag)

                if elm.rms_model.external_mapping.get(VarPowerFlowReferenceType.If_dc, None) is not None:
                    from_voltage_dc: Var | None
                    from_voltage_dc, _, _ = get_bus_rms_algebraic_vars(bus_rms_model=elm.bus_from.rms_model)
                    if from_voltage_dc is not None:
                        # Reuse the DC-bus value already initialized from the PF so
                        # the branch current and its terminal voltage share one seed.
                        from_voltage_raw: float | int | complex | None = self.init_guess.get(
                            from_voltage_dc.uid,
                            None,
                        )
                        from_current: float = 0.0

                        if from_voltage_raw is not None:
                            from_voltage: float = float(np.real(from_voltage_raw))
                            if abs(from_voltage) > 1.0e-9:
                                from_current = float(self.Sf[branch_num].real / from_voltage)
                            else:
                                # A de-energized DC terminal cannot define current from P/V.
                                pass
                        else:
                            pass

                        self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.If_dc, from_current)
                    else:
                        pass
                else:
                    pass

                # Run explicit initialization for branches to solve algebraic equations
                if isinstance(elm, Transformer2W):

                    initialization_method: RmsInitializationMethod = _select_rms_initialization_method(
                        configured_method=self.options.initialization_method,
                        mdl=elm.rms_model,
                        init_guess=self.init_guess,
                        uid2idx_vars=self._uid2idx_vars,
                    )

                    if initialization_method in (RmsInitializationMethod.Explicit, RmsInitializationMethod.ConsistentNewton):
                        diff_sys_vars: Dict[int, Var] = {diff_var.uid: diff_var for diff_var in self._diff_vars}
                        rms_compiler_init = RMSCompiler(
                            variables=list(self.sys_vars.values()),
                            diff_vars=list(diff_sys_vars.values()),
                            v_params=self._variable_parameters,
                            c_params=self._constant_parameters,
                            compiler_names_dict=self._compiler_names_dict,
                        )
                        compile_single_equation = build_rms_single_equation_compiler(rms_compiler_init)

                        # New init_explicit_common path
                        explicit_initialization_result: ExplicitInitializationResult = init_explicit_common(
                            mdl=elm.rms_model,
                            sys_vars=self.sys_vars,
                            sys_diff_vars=diff_sys_vars,
                            variable_parameters=self._variable_parameters,
                            event_parameters_eqs=self._event_parameters_eqs0,
                            constant_parameters=self._constant_parameters,
                            event_param_init_dict=self.event_params_init_dict,
                            init_guess=self.init_guess,
                            diff_init_guess=diff_init_guess_common,
                            uid2idx_vars=self.uid2idx_vars,
                            uid2idx_diff=self._uid2idx_diff,
                            uid2idx_params=self._uid2idx_params,
                            uid2idx_event_params=self._uid2idx_event_params,
                            params_array=self._parameters_values,
                            compile_single_equation=compile_single_equation,
                            external_uid_values=self._get_explicit_external_uid_values(mdl=elm.rms_model),
                            verbose=bool(self.options.verbose > 0),
                        )
                        if explicit_initialization_result.converged:
                            self.init_guess = explicit_initialization_result.init_guess
                            diff_init_guess_common = explicit_initialization_result.diff_init_guess
                        else:
                            raise RuntimeError(explicit_initialization_result.message)
                    elif initialization_method == RmsInitializationMethod.PseudoTransient:
                        self.init_guess = _run_rms_model_pseudo_transient(
                            auto_fallback=self.options.initialization_method == RmsInitializationMethod.Auto,
                            mdl=elm.rms_model,
                            sys_vars=self.sys_vars,
                            variable_parameters=self._variable_parameters,
                            event_parameters_eqs=self._event_parameters_eqs0,
                            constant_parameters=self._constant_parameters,
                            init_guess=self.init_guess,
                            uid2idx_vars=self._uid2idx_vars,
                            uid2idx_params=self._uid2idx_params,
                            uid2idx_event_params=self._uid2idx_event_params,
                            compiler_names_dict=self._compiler_names_dict,
                            alias_names_dict=self._alias_names_dict,
                            VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                            TIME_NAME=self.TIME_NAME,
                            VARS_NAME=self.VARS_NAME,
                            DIFF_NAME=self.DIFF_NAME,
                            CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                            dtau0=1.0,
                            max_iter=max(500, int(self.options.max_iter)),
                            tol=min(1e-8, self.options.tolerance),
                            verbose=bool(self.options.verbose > 0),
                        )
                    else:
                        raise ValueError("Not implemented initialization method")

                # add model to system block
                self.sys_block.add(elm.rms_model)

                # add variable to conservation equations of the bus to which the element is connected
                f = bus_dict[elm.bus_from]
                t = bus_dict[elm.bus_to]

                assemble_rms_mapped_power_references(
                    model=elm.rms_model,
                    bus_from_index=f,
                    bus_to_index=t,
                    bus_from_is_dc=elm.bus_from.is_dc,
                    bus_to_is_dc=elm.bus_to.is_dc,
                    active_power_balance=P,
                    active_power_balance_used=P_used,
                    reactive_power_balance=Q,
                    reactive_power_balance_used=Q_used,
                )
        # Populating VSCs init guess
        for i, elm in enumerate(self.grid.get_vsc()):
            if elm.rms_model.empty():
                if self.logger is not None:
                    self.logger.add_error("No RMS model",
                                          device_class=elm.device_type.value,
                                          device=elm.name)
                else:
                    pass
            else:
                mdl = elm.rms_model

                assign_static_api_object_mapping_for_device(grid=self.grid,
                                                            device=elm,
                                                            mdl=mdl,
                                                            problem_mapping=self._static_parameters_values_mapping,
                                                            logger=self._static_parameter_mapping_diagnostics)


                St_vsc = self.power_flow_results.St_vsc / self.grid.Sbase
                Sf_vsc = (self.power_flow_results.Pfn_vsc[i] + self.power_flow_results.Pfp_vsc[i]) / self.grid.Sbase
                # fill init_guess

                self.add_variables_to_compilation_dicts(elm, mdl)
                f = bus_dict[elm.bus_from]
                t = bus_dict[elm.bus_to]
                pt_init = St_vsc[i].real
                qt_init = St_vsc[i].imag
                vm_t = np.abs(self.power_flow_results.voltage[t])
                im_init: float = float(
                    np.sqrt(pt_init * pt_init + qt_init * qt_init)
                    / (vm_t + 1e-12)
                )

                if i < len(self.power_flow_results.It_vsc):
                    # Power-flow VSC currents already use the system per-unit
                    # base expected by the RMS physical-terminal equations.
                    it_mag: float = float(
                        np.abs(self.power_flow_results.It_vsc[i])
                    )
                    if np.isfinite(it_mag) and it_mag > 0.0:
                        im_init = it_mag
                    else:
                        pass
                else:
                    pass

                self.set_init_guess(mdl, VarPowerFlowReferenceType.Pf, Sf_vsc)
                self.set_init_guess(mdl, VarPowerFlowReferenceType.Pt, pt_init)
                self.set_init_guess(mdl, VarPowerFlowReferenceType.Qt, qt_init)
                dc_voltage_init: float = float(
                    np.abs(self.power_flow_results.voltage[f])
                )
                dc_current_init: float = float(self.power_flow_results.If_vsc[i])
                self.set_init_guess(
                    mdl,
                    VarPowerFlowReferenceType.Vf_dc,
                    dc_voltage_init,
                )
                self.set_init_guess(
                    mdl,
                    VarPowerFlowReferenceType.Idc,
                    dc_current_init,
                )
                if VarPowerFlowReferenceType.Im in mdl.external_mapping:
                    self.set_init_guess(mdl, VarPowerFlowReferenceType.Im, im_init)
                else:
                    pass

                if elm.bus_from.is_dc and VarPowerFlowReferenceType.Qf in mdl.external_mapping:
                    if self.logger is not None:
                        self.logger.add_warning("Ignoring VSC reactive power on DC from terminal", device=elm.name)

                assemble_rms_mapped_power_references(
                    model=mdl,
                    bus_from_index=f,
                    bus_to_index=t,
                    bus_from_is_dc=elm.bus_from.is_dc,
                    bus_to_is_dc=elm.bus_to.is_dc,
                    active_power_balance=P,
                    active_power_balance_used=P_used,
                    reactive_power_balance=Q,
                    reactive_power_balance_used=Q_used,
                    ignore_dc_from_reactive=True,
                )
                self.sys_block.add(mdl)

        # Populating HVDC init guess (similar to VSCs)
        for i, elm in enumerate(self.grid.get_hvdc()):
            if elm.rms_model.empty():
                if self.logger is not None:
                    self.logger.add_error("No RMS model",
                                          device_class=elm.device_type.value,
                                          device=elm.name)
                else:
                    pass
            else:
                mdl = elm.rms_model

                self.add_variables_to_compilation_dicts(elm, mdl)

                self.set_init_guess(mdl, VarPowerFlowReferenceType.Pf_hvdc,
                                    self.power_flow_results.Pf_hvdc[i] / self.grid.Sbase)

                self.set_init_guess(mdl, VarPowerFlowReferenceType.Pt_hvdc,
                                    self.power_flow_results.Pt_hvdc[i] / self.grid.Sbase)

                f = bus_dict[elm.bus_from]
                t = bus_dict[elm.bus_to]
                assemble_rms_mapped_power_references(
                    model=mdl,
                    bus_from_index=f,
                    bus_to_index=t,
                    bus_from_is_dc=elm.bus_from.is_dc,
                    bus_to_is_dc=elm.bus_to.is_dc,
                    active_power_balance=P,
                    active_power_balance_used=P_used,
                    reactive_power_balance=Q,
                    reactive_power_balance_used=Q_used,
                )
                self.sys_block.add(mdl)

        # initialize injections

        for elm in grid.get_vsc():

            if elm.rms_model.empty():
                if self.logger is not None:
                    self.logger.add_error("No RMS model",
                                          device_class=elm.device_type.value,
                                          device=elm.name)
                else:
                    pass
            else:

                # find init values for the variables of this model
                initialization_method: RmsInitializationMethod = _select_rms_initialization_method(
                    configured_method=self.options.initialization_method,
                    mdl=elm.rms_model,
                    init_guess=self.init_guess,
                    uid2idx_vars=self._uid2idx_vars,
                )

                if initialization_method in (RmsInitializationMethod.Explicit, RmsInitializationMethod.ConsistentNewton):
                    # common initialization to integrate

                    # create constant parameters array
                    params_array: np.ndarray = np.zeros(
                        len(self._constant_parameters))  # array with the lenght of constant params
                    for param, const in elm.rms_model.parameters.items():
                        params_array[self._uid2idx_params[param.uid]] = const.value

                    diff_sys_vars: Dict[int, Var] = {diff_var.uid: diff_var for diff_var in
                                                     self._diff_vars}  # dictionary uid, var for diff_vars
                    rms_compiler_init = RMSCompiler(
                        variables=list(self.sys_vars.values()),
                        diff_vars=list(diff_sys_vars.values()),
                        v_params=self._variable_parameters,
                        c_params=self._constant_parameters,
                        compiler_names_dict=self._compiler_names_dict,
                    )
                    compile_single_equation = build_rms_single_equation_compiler(
                        rms_compiler_init)  # function to compile one equation

                    # New init_explicit_common path
                    explicit_initialization_result: ExplicitInitializationResult = init_explicit_common(
                        mdl=elm.rms_model,
                        sys_vars=self.sys_vars,
                        sys_diff_vars=diff_sys_vars,
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=self._event_parameters_eqs0,
                        constant_parameters=self._constant_parameters,
                        event_param_init_dict=self.event_params_init_dict,
                        init_guess=self.init_guess,
                        diff_init_guess=diff_init_guess_common,
                        uid2idx_vars=self.uid2idx_vars,
                        uid2idx_diff=self._uid2idx_diff,
                        uid2idx_params=self._uid2idx_params,
                        uid2idx_event_params=self._uid2idx_event_params,
                        params_array=self._parameters_values,
                        compile_single_equation=compile_single_equation,
                        external_uid_values=self._get_explicit_external_uid_values(mdl=elm.rms_model),
                        verbose=bool(self.options.verbose > 0),
                    )
                    if explicit_initialization_result.converged:
                        self.init_guess = explicit_initialization_result.init_guess
                        diff_init_guess_common = explicit_initialization_result.diff_init_guess
                    else:
                        raise RuntimeError(explicit_initialization_result.message)

                elif initialization_method == RmsInitializationMethod.PseudoTransient:
                    if isinstance(elm, InjectionParent):
                        self._seed_rms_input_initialization_from_single_bus_model(
                            mdl=elm.rms_model,
                            bus_model=elm.bus.rms_model,
                        )
                    elif isinstance(elm, BranchParent):
                        self._seed_rms_input_initialization_from_branch_bus_models(
                            mdl=elm.rms_model,
                            bus_from_model=elm.bus_from.rms_model,
                            bus_to_model=elm.bus_to.rms_model,
                        )

                    diff_sys_vars: Dict[int, Var] = {
                        diff_var.uid: diff_var for diff_var in self._diff_vars
                    }
                    rms_compiler_init = RMSCompiler(
                        variables=list(self.sys_vars.values()),
                        diff_vars=list(diff_sys_vars.values()),
                        v_params=self._variable_parameters,
                        c_params=self._constant_parameters,
                        compiler_names_dict=self._compiler_names_dict,
                    )
                    compile_single_equation = build_rms_single_equation_compiler(rms_compiler_init)
                    self.init_guess, diff_init_guess_common = init_explicit_common(
                        mdl=elm.rms_model,
                        sys_vars=self.sys_vars,
                        sys_diff_vars=diff_sys_vars,
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=self._event_parameters_eqs0,
                        constant_parameters=self._constant_parameters,
                        event_param_init_dict=self.event_params_init_dict,
                        init_guess=self.init_guess,
                        diff_init_guess=diff_init_guess_common,
                        uid2idx_vars=self.uid2idx_vars,
                        uid2idx_diff=self._uid2idx_diff,
                        uid2idx_params=self._uid2idx_params,
                        uid2idx_event_params=self._uid2idx_event_params,
                        params_array=self._parameters_values,
                        compile_single_equation=compile_single_equation,
                        external_uid_values=self._get_explicit_external_uid_values(mdl=elm.rms_model),
                        verbose=bool(self.options.verbose > 0),
                    )
                    self.init_guess = _run_rms_model_pseudo_transient(
                        auto_fallback=self.options.initialization_method == RmsInitializationMethod.Auto,
                        mdl=elm.rms_model,
                        sys_vars=self.sys_vars,
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=self._event_parameters_eqs0,
                        constant_parameters=self._constant_parameters,
                        init_guess=self.init_guess,
                        uid2idx_vars=self._uid2idx_vars,
                        uid2idx_params=self._uid2idx_params,
                        uid2idx_event_params=self._uid2idx_event_params,
                        compiler_names_dict=self._compiler_names_dict,
                        alias_names_dict=self._alias_names_dict,
                        VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                        TIME_NAME=self.TIME_NAME,
                        VARS_NAME=self.VARS_NAME,
                        DIFF_NAME=self.DIFF_NAME,
                        CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                        dtau0=1e-4,
                        max_iter=max(500, int(self.options.max_iter)),
                        tol=min(1e-8, self.options.tolerance),
                        verbose=bool(self.options.verbose > 0),
                    )

                else:
                    raise ValueError("Not implemented initialization method")
                # PF seeding already registered this canonical VSC model.
                # Initialization must not add a second procedural owner.

        injection_init_data = self.get_injection_init_data(bus_dict=bus_dict)

        for elm in grid.get_injection_devices_iter():
            Sdev: complex = injection_init_data[elm.idtag]

            if elm.rms_model.empty():
                if self.logger is not None:
                    self.logger.add_error("No RMS model",
                                          device_class=elm.device_type.value,
                                          device=elm.name)
                else:
                    pass
            else:
                bus_index = bus_dict[elm.bus]

                # Static values must be resolved before parameter registration;
                # explicit initialization then sees physical values rather than
                # template defaults (notably for shunt conductance/susceptance).
                assign_static_api_object_mapping_for_device(
                    grid=self.grid,
                    device=elm,
                    mdl=elm.rms_model,
                    problem_mapping=self._static_parameters_values_mapping,
                    logger=self._static_parameter_mapping_diagnostics,
                )

                self.add_variables_to_compilation_dicts(elm, elm.rms_model)
                register_rms_fmu_cs_device(self, elm, elm.rms_model)
                register_rms_fmu_me_device(self, elm, elm.rms_model)

                # Every injection must start from its own PF allocation. Using
                # aggregate Sbus at a DC bus would duplicate the complete net bus
                # power in every model connected to that bus.
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.P,
                                    Sdev.real)

                if elm.bus.is_dc:
                    # DC devices only require the active component of Sdev.
                    pass
                else:
                    self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Q,
                                        Sdev.imag)

                    # Some physical sources expose both P/Q and Ir/Ii. Seed the
                    # redundant current coordinates from the same solved point
                    # so their identity equations hold before Newton starts.
                    has_current_real: bool = (
                        VarPowerFlowReferenceType.Ir
                        in elm.rms_model.external_mapping
                    )
                    has_current_imaginary: bool = (
                        VarPowerFlowReferenceType.Ii
                        in elm.rms_model.external_mapping
                    )
                    if has_current_real and has_current_imaginary:
                        current_real: float
                        current_imaginary: float
                        current_real, current_imaginary = rectangular_current_from_power(
                            power=complex(Sdev),
                            voltage=complex(self.power_flow_results.voltage[bus_index]),
                        )
                        self.set_init_guess(
                            elm.rms_model,
                            VarPowerFlowReferenceType.Ir,
                            current_real,
                        )
                        self.set_init_guess(
                            elm.rms_model,
                            VarPowerFlowReferenceType.Ii,
                            current_imaginary,
                        )
                    else:
                        pass

                k = bus_dict[elm.bus]
                assemble_rms_mapped_power_references(
                    model=elm.rms_model,
                    active_power_balance=P,
                    active_power_balance_used=P_used,
                    reactive_power_balance=Q,
                    reactive_power_balance_used=Q_used,
                    bus_index=k,
                    bus_is_dc=elm.bus.is_dc,
                )

                initialization_method: RmsInitializationMethod = _select_rms_initialization_method(
                    configured_method=self.options.initialization_method,
                    mdl=elm.rms_model,
                    init_guess=self.init_guess,
                    uid2idx_vars=self._uid2idx_vars,
                )

                if initialization_method in (RmsInitializationMethod.Explicit, RmsInitializationMethod.ConsistentNewton):

                    if isinstance(elm, InjectionParent):
                        self._seed_rms_input_initialization_from_single_bus_model(mdl=elm.rms_model,
                                                                                  bus_model=elm.bus.rms_model)
                    elif isinstance(elm, BranchParent):
                        self._seed_rms_input_initialization_from_branch_bus_models(mdl=elm.rms_model,
                                                                                   bus_from_model=elm.bus_from.rms_model,
                                                                                   bus_to_model=elm.bus_to.rms_model)
                    else:
                        pass

                    # else:
                    # for common init explicit to integrate
                    diff_sys_vars: Dict[int, Var] = {diff_var.uid: diff_var for diff_var in self._diff_vars}
                    rms_compiler_init = RMSCompiler(
                        variables=list(self.sys_vars.values()),
                        diff_vars=list(diff_sys_vars.values()),
                        v_params=self._variable_parameters,
                        c_params=self._constant_parameters,
                        compiler_names_dict=self._compiler_names_dict,
                    )
                    compile_single_equation = build_rms_single_equation_compiler(rms_compiler_init)

                    # New init_explicit_common path
                    explicit_initialization_result: ExplicitInitializationResult = init_explicit_common(
                        mdl=elm.rms_model,
                        sys_vars=self.sys_vars,
                        sys_diff_vars=diff_sys_vars,
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=self._event_parameters_eqs0,
                        constant_parameters=self._constant_parameters,
                        event_param_init_dict=self.event_params_init_dict,
                        init_guess=self.init_guess,
                        diff_init_guess=diff_init_guess_common,
                        uid2idx_vars=self.uid2idx_vars,
                        uid2idx_diff=self._uid2idx_diff,
                        uid2idx_params=self._uid2idx_params,
                        uid2idx_event_params=self._uid2idx_event_params,
                        params_array=self._parameters_values,
                        compile_single_equation=compile_single_equation,
                        external_uid_values=self._get_explicit_external_uid_values(mdl=elm.rms_model),
                        verbose=bool(self.options.verbose > 0),
                    )
                    if explicit_initialization_result.converged:
                        self.init_guess = explicit_initialization_result.init_guess
                        diff_init_guess_common = explicit_initialization_result.diff_init_guess
                    else:
                        raise RuntimeError(explicit_initialization_result.message)
                    # initialize variables with no init equation assigned
                    # run_rms_native_initialization(self, self.options)

                elif initialization_method == RmsInitializationMethod.PseudoTransient:
                    self.init_guess = _run_rms_model_pseudo_transient(
                        auto_fallback=self.options.initialization_method == RmsInitializationMethod.Auto,
                        mdl=elm.rms_model,
                        sys_vars=self.sys_vars,
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=self._event_parameters_eqs0,
                        constant_parameters=self._constant_parameters,
                        init_guess=self.init_guess,
                        uid2idx_vars=self._uid2idx_vars,
                        uid2idx_params=self._uid2idx_params,
                        uid2idx_event_params=self._uid2idx_event_params,
                        compiler_names_dict=self._compiler_names_dict,
                        alias_names_dict=self._alias_names_dict,
                        VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                        TIME_NAME=self.TIME_NAME,
                        VARS_NAME=self.VARS_NAME,
                        DIFF_NAME=self.DIFF_NAME,
                        CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                        max_iter=self.options.max_iter,
                        tol=self.options.tolerance,
                        verbose=bool(self.options.verbose > 0),
                    )

                # not implemented yet
                # elif self.options.initialization_method == RmsInitializationMethod.PseudoTransient:
                #     init_pseudo_transient(
                #         mdl=elm.rms_model,
                #         sys_vars=self.sys_vars,
                #         variable_parameters=self._variable_parameters,
                #         event_parameters_eqs=self._event_parameters_eqs0,
                #         constant_parameters=self._constant_parameters,
                #         init_guess=self.init_guess,
                #         uid2idx_vars=self._uid2idx_vars,
                #         uid2idx_params=self._uid2idx_params,
                #         uid2idx_event_params=self._uid2idx_event_params,
                #         compiler_names_dict=self._compiler_names_dict,
                #         alias_names_dict=self._alias_names_dict,
                #         VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                #         TIME_NAME=self.TIME_NAME,
                #         VARS_NAME=self.VARS_NAME,
                #         DIFF_NAME=self.DIFF_NAME,
                #         CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                #         dtau0=1e0,
                #         max_iter=1000,
                #         tol=1e-6
                #     )
                else:
                    raise ValueError("Not implemented initialization method")

                self.sys_block.add(elm.rms_model)

        total_init_explicit_time += time.perf_counter() - t0
        # print(f"\nTotal time explicit initialization: {total_init_explicit_time:.6f} seconds")
        if self.logger is not None:
            self.logger.add_info("Total time explicit initialization", value=total_init_explicit_time)
        else:
            pass
        if self.progress_signal is not None:
            self.progress_signal.emit(10)

        event_eq_by_uid: Dict[int, Expr | Const] = {
            ep.uid: eq for ep, eq in zip(self._variable_parameters, self._event_parameters_eqs0)
        }
        for i, ep in enumerate(self._runtime_all_parameters_source):
            if ep.uid in self._discrete_event_parameter_uids:
                pass
            else:
                runtime_eq = self._runtime_all_eqs_source[i]
                if isinstance(runtime_eq, Const) and runtime_eq.value is None and ep.uid in event_eq_by_uid:
                    self._runtime_all_eqs_source[i] = event_eq_by_uid[ep.uid]
                else:
                    pass

        for i, eq in enumerate(self._runtime_all_eqs_source):
            if eq is None or (isinstance(eq, Const) and eq.value is None):
                raise Exception(f"Runtime event parameter {self._runtime_all_parameters_source[i]} has None Value")

        # Keep runtime event-parameter sources aligned with explicit initialization
        # results. Explicit initialization resolves scalar event parameters by
        # replacing entries in ``_event_parameters_eqs0`` with ``Const(value)``.
        # Mirror those resolved constants into runtime sources so event-group
        # baselines and runtime arrays start from the same initialized values.
        for i, eq0 in enumerate(self._event_parameters_eqs0):
            if isinstance(eq0, Const) and eq0.value is not None:
                self._runtime_all_eqs_source[i] = Const(eq0.value)
                self.event_params_init_dict[self._variable_parameters[i].uid] = float(eq0.value)
            else:
                pass

        # print("start creating balance equations")
        # add the nodal balance equations
        # Legacy split VSC models expose terminal reactive power but no AC
        # angle input because their companion transformer/control model closes
        # the virtual AC node. A standalone VSC with ``Vat`` is connected to a
        # physical AC bus and therefore requires the normal P/Q bus balances.
        ac_virtual_buses = [
            elm.bus_to.idtag
            for elm in grid.get_vsc()
            if (
                VarPowerFlowReferenceType.Qt in elm.rms_model.external_mapping
                and VarPowerFlowReferenceType.Vat not in elm.rms_model.external_mapping
            )
        ]
        for i, elm in enumerate(self.grid.buses):
            if not P_used[i] and not Q_used[i]:
                has_capacitive_dc_state: bool = (
                    elm.is_dc
                    and dc_bus_rms_model_has_capacitive_state(
                        bus_rms_model=elm.rms_model,
                    )
                )
                if has_capacitive_dc_state:
                    # With no connected power, Pbus=0 keeps the voltage state
                    # constant without leaving its algebraic bridge variable free.
                    self._algebraic_eqs.append(
                        build_dc_bus_nodal_power_equation(
                            bus_rms_model=elm.rms_model,
                            nodal_power_balance=Const(0.0),
                        )
                    )
                    if elm.active:
                        if self.logger is not None:
                            self.logger.add_error("Isolated active bus", device=elm.name, value=i)
                        else:
                            pass
                    else:
                        if self.logger is not None:
                            self.logger.add_info(
                                "Inactive capacitive DC bus retained at its initial voltage",
                                device=elm.name,
                            )
                        else:
                            pass
                else:
                    if elm.active:
                        if self.logger is not None:
                            self.logger.add_error("Isolated active bus", device=elm.name, value=i)
                        else:
                            pass
                    else:
                        # Detached out-of-service buses must not leave free algebraic
                        # voltage variables in an otherwise square RMS system.
                        boundary_equations: List[Expr] = build_inactive_bus_boundary_equations(
                            bus=elm,
                            init_guess=self.init_guess,
                        )
                        if len(boundary_equations) > 0:
                            self._algebraic_eqs.extend(boundary_equations)
                            if self.logger is not None:
                                self.logger.add_info("Inactive isolated bus fixed at its initial voltage",
                                                     device=elm.name)
                            else:
                                pass
                        else:
                            if self.logger is not None:
                                self.logger.add_error("Invalid RMS model for inactive isolated bus",
                                                      device=elm.name,
                                                      value=i)
                            else:
                                pass
            else:
                if elm.is_dc:
                    self._algebraic_eqs.append(
                        build_dc_bus_nodal_power_equation(
                            bus_rms_model=elm.rms_model,
                            nodal_power_balance=P[i],
                        )
                    )
                else:
                    # Every AC terminal in MultiCircuit is a physical bus. A
                    # VSC voltage-control equation does not replace the bus's
                    # reactive-power balance, so both nodal residuals remain
                    # owned by the RMS assembler.
                    self._algebraic_eqs.append(Q[i])

                    # The active-power balance at the AC slack bus is the
                    # redundant equation associated with the global angle
                    # gauge.  Keep it in the physical DAE, but remember its
                    # exact Jacobian position so small-signal factorization can
                    # replace it with an angle-reference row.
                    if elm.is_slack and self._small_signal_reference_row is None:
                        _, _, voltage_angle = get_bus_rms_algebraic_vars(bus_rms_model=elm.rms_model)
                        if voltage_angle is not None:
                            algebraic_column: int = self._algebraic_vars.index(voltage_angle)
                            self._small_signal_reference_row = len(self._state_eqs) + len(self._algebraic_eqs)
                            self._small_signal_reference_column = len(self._state_vars) + algebraic_column
                        else:
                            if self.logger is not None:
                                self.logger.add_error("AC slack bus has no RMS voltage-angle variable",
                                                      device=elm.name)
                            else:
                                pass
                    self._algebraic_eqs.append(P[i])

        # print("created balance equations")

        self._runtime_all_parameters_source.append(self._external_time_parameter)
        self._runtime_all_eqs_source.append(Const(0.0))

        # Imported ``time()`` variables keep their source UIDs, while the RMS
        # runtime owns one typed parameter slot whose value is updated each step.
        self._variable_parameters.append(self._external_time_parameter)
        self._event_parameters_eqs0.append(Const(0.0))
        self._compiler_names_dict[self._external_time_parameter.uid] = (
            f"{self.VARIABLE_PARAMS_NAME}[{self._n_event_params}]"
        )
        self._alias_names_dict[self._external_time_parameter.uid] = (
            f"{self.VARIABLE_PARAMS_NAME}_{self._n_event_params}"
        )
        self._uid2idx_event_params[self._external_time_parameter.uid] = self._n_event_params
        self._n_event_params += 1
        self._bind_external_time_compiler_names()

        self._runtime_all_eqs_source0 = list(self._runtime_all_eqs_source)

        ##################### To be removed when order is preserved in the first part #############################

        self._state_algeb_vars = list(self.sys_vars.values())

        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_algebraic = len(self._algebraic_eqs)

        self._uid2idx_vars: Dict[int, int] = dict()

        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()

        i = 0
        for v in self._state_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        for v in self._algebraic_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        for k, ep in enumerate(self._diff_vars):
            self._compiler_names_dict[ep.uid] = f"{self.DIFF_NAME}[{k}]"
            self._alias_names_dict[ep.uid] = f"{self.DIFF_NAME}_{k}"
            self._uid2idx_diff[ep.uid] = k

        self._compiler_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._alias_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._uid2idx_t[self._glob_time.uid] = 0

        for it, eq in enumerate(self._event_parameters_eqs0):
            if isinstance(eq, Const) and eq.value is None:
                raise Exception(f' Event parameter {self._variable_parameters[it]} has None Value')


    def _get_explicit_external_uid_values(self, mdl: Block) -> Dict[int, float]:
        """Bind imported external inputs and retain their exact runtime UIDs.

        :param mdl: Symbolic model whose explicit equations may consume time.
        :return: Startup values keyed by the exact imported variable UIDs.
        """
        external_uid_values: Dict[int, float] = build_explicit_external_uid_values(
            mdl=mdl,
            external_name_values=dict(((self.TIME_NAME, 0.0),)),
        )
        external_time_uid: int
        for external_time_uid in external_uid_values:
            self._external_time_uids.add(external_time_uid)
        return external_uid_values

    def _bind_external_time_compiler_names(self) -> None:
        """Route imported time UIDs through the typed RMS runtime parameter.

        :return: None.
        """
        external_time_index: int | None = self._uid2idx_event_params.get(
            self._external_time_parameter.uid,
            None,
        )
        if external_time_index is None:
            pass
        else:
            external_time_uid: int
            for external_time_uid in self._external_time_uids:
                self._compiler_names_dict[external_time_uid] = (
                    f"{self.VARIABLE_PARAMS_NAME}[{external_time_index}]"
                )
                self._alias_names_dict[external_time_uid] = (
                    f"{self.VARIABLE_PARAMS_NAME}_{external_time_index}"
                )

    def set_events_group(self, rms_events_group: RmsEventsGroup):
        """
        add events modifying values of event_parameters equations
        :param rms_events_group:
        :return:
        """
        same_group_requested: bool

        if self._active_events_group is None:
            same_group_requested = rms_events_group is None and len(self._scheduled_mode_events) > 0
        elif rms_events_group is None:
            same_group_requested = False
        else:
            same_group_requested = self._active_events_group.idtag == rms_events_group.idtag

        if same_group_requested and self.is_initialized():
            return
        else:
            pass
        # Preparing another group invalidates the previous runtime certificate.
        self._is_initialized: bool = False

        active_runtime_eqs: List[Expr | Const] = list(self._runtime_all_eqs_source0)

        if self._continuous_event_parameter_uids:
            collect_continuous_events: Dict[int, List[RmsEvent]] = {
                uid: list()
                for uid in self._continuous_event_parameter_uids
            }
        else:
            collect_continuous_events = dict()

        scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]] = dict()

        selected_events = self._get_rms_events_for_group(rms_events_group)

        for rms_evt in selected_events:
            if not isinstance(rms_evt.parameter, Var):
                pass
            else:
                if not self._event_targets_registered_parameter(rms_evt, int(rms_evt.parameter.uid)):
                    pass
                else:
                    parameter_uid: int = int(rms_evt.parameter.uid)
                    transition_tpe: DynamicEventTransitionType = rms_evt.transition_type
                    use_scheduled_mode: bool = _is_rms_event_routed_to_scheduled_mode(
                        transition_tpe=transition_tpe,
                        parameter_uid=parameter_uid,
                        discrete_parameter_uids=self._discrete_event_parameter_uids,
                        continuous_parameter_uids=self._continuous_event_parameter_uids,
                    )

                    # The event routing must preserve the legacy discrete step
                    # path while still allowing the same symbolic parameter to
                    # host a continuous ramp. Using the transition profile as the
                    # primary routing decision keeps the historical step response
                    # compatible with the reference CSVs and fixes the broken ramp
                    # behavior without splitting model parameters into separate
                    # symbolic registrations.
                    if use_scheduled_mode:
                        if parameter_uid in self._discrete_event_parameter_uids:
                            event_list = scheduled_mode_events.setdefault(parameter_uid, list())
                            force_step_alignment: bool = bool(rms_evt.force_step_alignment)

                            # Only true discrete/mode parameters should use the
                            # scheduled latch path. Event-dict parameters such as
                            # ``Pl0`` historically followed the symbolic piecewise
                            # path even for step events, and the stored RMS CSV
                            # references were generated from that behavior.
                            event_list.append(
                                (
                                    float(rms_evt.time),
                                    float(rms_evt.value),
                                    force_step_alignment,
                                )
                            )
                        else:
                            if parameter_uid in collect_continuous_events:
                                collect_continuous_events[parameter_uid].append(rms_evt)
                            else:
                                pass
                    else:
                        if parameter_uid in collect_continuous_events:
                            collect_continuous_events[parameter_uid].append(rms_evt)
                        else:
                            pass

        self._continuous_runtime_events = dict()

        for parameter_uid, event_list in collect_continuous_events.items():
            if len(event_list) == 0:
                pass
            else:

                sorted_events: List[RmsEvent] = sorted(event_list, key=_get_rms_event_time_sort_key)

                if len(sorted_events) == 1:
                    parameter_index: int | None = None
                    runtime_parameter: Var

                    # The single-event path keeps the historical symbolic RMS
                    # behavior so existing CSV references remain valid. Only true
                    # multi-event combinations are diverted to the procedural
                    # replay path introduced to avoid fragile nested expressions.
                    for runtime_parameter_index, runtime_parameter in enumerate(self._runtime_all_parameters_source):
                        if runtime_parameter.uid == parameter_uid:
                            parameter_index = runtime_parameter_index
                            break
                        else:
                            pass

                    if parameter_index is not None:
                        active_expr: Expr | Const = active_runtime_eqs[parameter_index]
                        active_runtime_eqs[parameter_index] = _build_runtime_expression_from_single_rms_event(
                            time_var=self._glob_time,
                            base_expression=active_expr,
                            event_item=sorted_events[0],
                        )
                    else:
                        pass
                else:
                    self._continuous_runtime_events[parameter_uid] = sorted_events

        active_runtime_eqs = self._freeze_runtime_state_references(active_runtime_eqs)

        self._runtime_all_eqs_source = active_runtime_eqs
        self._scheduled_mode_events = scheduled_mode_events

        # The active runtime equations must replace the current event-parameter
        # equations before recompilation. Otherwise the JIT event-parameter
        # function is rebuilt from the original baseline expressions and ramp
        # transitions collapse back to the pre-event constant or step value.
        self._event_parameters_eqs = list(active_runtime_eqs)

        self._rebuild_runtime_parameter_partition()
        self._bind_external_time_compiler_names()
        self._initialize_mode_event_state()
        self._initialize_procedural_logic_updater()
        self._validate_deferred_mode_parameter_sources()

        if self.get_variable_parameter_number() > 0:
            self._variable_parameters_values = np.ones(self.get_variable_parameter_number(), dtype=np.float64)
        else:
            self._variable_parameters_values = np.zeros(0, dtype=np.float64)

        # --------------------------------------------------------------------------------------------------------------
        # Compile RHS and Jacobian using JIT Compiler adaptation
        # --------------------------------------------------------------------------------------------------------------
        timings = dict()
        # print("Compiling RMS using JIT Native Compiler...")
        t0 = _tic()
        rms_compiler = RMSCompiler(
            variables=self._state_algeb_vars,
            diff_vars=self._diff_vars,
            v_params=self._variable_parameters,
            c_params=self._constant_parameters,
            compiler_names_dict=self._compiler_names_dict
        )
        timings["Compiler Setup"] = _toc(t0)

        t0 = _tic()
        self._derivative_fn = rms_compiler.compile_derivative_fn(self._uid2idx_vars)
        timings["SymbolicDerivative"] = _toc(t0)

        t0 = _tic()
        self._event_params_fn = rms_compiler.compile_event_params_fn(
            eqs=self._event_parameters_eqs,
            alias_names_dict=self._alias_names_dict,
            EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
            TIME_NAME=self.TIME_NAME,
        )
        timings["Event parameters"] = _toc(t0)

        t0 = _tic()
        self._rhs_algeb_fn = rms_compiler.compile_rhs(self._algebraic_eqs, "rhs_algeb")
        timings["RHS algebraic"] = _toc(t0)

        if len(self._state_eqs) != 0:
            t0 = _tic()
            self._rhs_state_fn = rms_compiler.compile_rhs(self._state_eqs, "rhs_state")
            timings["RHS state"] = _toc(t0)

            t0 = _tic()
            self._j11_fn = rms_compiler.compile_sparse_jacobian(self._state_eqs, self._state_vars, "j11")
            timings["J11 (dF/dx)"] = _toc(t0)
            self._fx_ct_fn = self._j11_fn

            t0 = _tic()
            self._j12_fn = rms_compiler.compile_sparse_jacobian(self._state_eqs, self._algebraic_vars, "j12")
            timings["J12 (dF/dy)"] = _toc(t0)
            self._fy_ct_fn = self._j12_fn

            t0 = _tic()
            self._j21_fn = rms_compiler.compile_sparse_jacobian(self._algebraic_eqs, self._state_vars, "j21")
            timings["J21 (dG/dx)"] = _toc(t0)
            self._gx_ct_fn = self._j21_fn

            t0 = _tic()
            self._j22_fn = rms_compiler.compile_sparse_jacobian(self._algebraic_eqs, self._algebraic_vars, "j22")
            timings["J22 (dG/dy)"] = _toc(t0)
            self._gy_ct_fn = self._j22_fn

        else:
            t0 = _tic()
            self._j22_fn = rms_compiler.compile_sparse_jacobian(self._algebraic_eqs, self._algebraic_vars, "j22")
            timings["J22 only (no states)"] = _toc(t0)
            self._gy_ct_fn = self._j22_fn

        if self.options.verbose > 0:
            print(f"Model compiled with {self._n_vars} variables")
            print("\nCompilation timing summary:")
            for k, v in timings.items():
                print(f"  {k:30s}: {v:8.4f} s")
            print(f"\nTotal JIT compile time: {sum(timings.values()):.4f} s")

        variable_parameters_init = np.ones(self.get_variable_parameter_number())

        if self._event_params_fn is None:
            self._variable_parameters_values = variable_parameters_init
        else:
            # TODO: think about this thing of calling twice here
            self._variable_parameters_values = self._event_params_fn(variable_parameters_init, 0.0)
            self._variable_parameters_values = self._event_params_fn(self._variable_parameters_values, 0.0)
        self._mode_runtime_initialized_uids = set()
        if self.get_all_vars_number() > 0 and self.get_variable_parameter_number() > 0:
            self._initialize_latched_mode_defaults(t=0.0, x=self.get_x0())

        self._constant_params = np.array([const.value for const in self._parameters_values])

        # Both RMS update paths must share the same isolated runtime state.
        self._block_boundary_updater = self._procedural_logic_updater

        if self.options.verbose > 0:
            print(f"\nTotal compile time: {sum(timings.values()):.4f} s")

        # we mark the problem as ready for simulation
        if self.options.initialization_method in (
                RmsInitializationMethod.ConsistentNewton, RmsInitializationMethod.Auto,
                RmsInitializationMethod.PseudoTransient):
            # Local PTC success does not certify the assembled network. Reuse
            # the global owner only after the final replay/latch snapshot.
            # Record the completed replay/latch snapshot in its existing UID owner.
            initial_parameter: Var
            for initial_parameter in self._variable_parameters:
                self.event_params_init_dict[initial_parameter.uid] = float(
                    self._variable_parameters_values[self._uid2idx_event_params[initial_parameter.uid]])
            consistency_converged: bool = run_rms_consistent_initialization(problem=self, options=self.options, logger=self.logger)
            if consistency_converged:
                pass
            else:
                raise RuntimeError("RMS Auto consistent initialization did not converge")
        else:
            pass
        # A failed new group must remain retryable instead of looking accepted.
        self._active_events_group = rms_events_group
        self.set_initialize_flag()

    def _set_manufacturer_native_runtime_session(
            self,
            runtime_session: ManufacturerNativeRuntimeSessionProtocol | None,
    ) -> None:
        """Install the driver-owned RMS native session in the procedural updater.

        :param runtime_session: Event-group session, or ``None`` to detach it.
        :return: None.
        """
        self._manufacturer_native_runtime_session = runtime_session
        # Finalize compiler snapshots before binding kernels to runtime indexes.
        self._rebuild_procedural_expression_compiler()
        self._procedural_logic_updater = build_boundary_updater_from_block(
            problem=self,
            expression_mode=ProceduralExpressionMode.Compiled,
            runtime_session=runtime_session,
            model_mode=2 if runtime_session is not None else None,
        )
        self._block_boundary_updater = self._procedural_logic_updater
    def resolve_manufacturer_native_boundary(self, t: float, x: Vec) -> None:
        """Advance due manufacturer controllers after an accepted RMS step.

        :param t: Accepted RMS boundary time.
        :param x: Accepted state and algebraic vector.
        :return: None.
        """
        updater: BlockProceduralLogicUpdater | None = self._block_boundary_updater
        if updater is not None and self._manufacturer_native_runtime_session is not None:
            if self._constant_params is None:
                constant_params: Vec = np.zeros(0, dtype=float)
            else:
                constant_params = self._constant_params
            full_params: Vec = np.concatenate((self._variable_parameters_values.copy(), constant_params))
            updater.commit_boundary(float(t), x, full_params)
            self._variable_parameters_values[:] = full_params[:self.get_variable_parameter_number()]
        else:
            pass
    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        t_mode = _get_next_forced_mode_event_time(self._scheduled_mode_events, t_prev, t_target)

        t_proc: Optional[float] = None
        if self._procedural_logic_updater is not None:
            t_proc = self._procedural_logic_updater.get_next_forced_event_time(t_prev, t_target)

        t_fmu: Optional[float] = get_next_rms_fmu_me_event_time(
            problem=self,
            t_prev=t_prev,
            t_target=t_target,
        )
        native_event_time: Optional[float]
        if t_mode is None:
            native_event_time = t_proc
        else:
            if t_proc is None:
                native_event_time = t_mode
            else:
                native_event_time = min(t_mode, t_proc)
        if native_event_time is None:
            return t_fmu
        else:
            if t_fmu is None:
                return native_event_time
            else:
                return min(native_event_time, t_fmu)

    def _rebuild_procedural_expression_compiler(self) -> None:
        """Snapshot finalized RMS indexes and constants before procedural binding.

        :return: None.
        """
        # Event groups can reorder runtime parameters, so kernels must use a fresh snapshot.
        self._procedural_expression_compiler = ProceduralExpressionCompiler(
            state_map=self._uid2idx_vars,
            runtime_map=self._uid2idx_event_params,
            constant_map=self._uid2idx_params,
            constant_values=self._parameters_values,
            global_time_uid=self._glob_time.uid,
        )

    def get_procedural_expression_compiler(self) -> ProceduralExpressionCompiler:
        """Return the RMS compiler shared by fused and standalone evaluators.

        :return: Compiler bound to the current RMS parameter layout.
        """
        # Direct bindings also need a compiler when no event group has been installed.
        if self._procedural_expression_compiler is None:
            self._rebuild_procedural_expression_compiler()
        else:
            pass
        assert self._procedural_expression_compiler is not None
        return self._procedural_expression_compiler

    def _initialize_procedural_logic_updater(self) -> None:
        """Build solver-owned procedural state without binding model entries.

        :return: None.
        """
        # Finalize compiler snapshots before binding kernels to runtime indexes.
        self._rebuild_procedural_expression_compiler()
        self._procedural_logic_updater = build_boundary_updater_from_block(
            problem=self,
            expression_mode=ProceduralExpressionMode.Compiled,
        )

    def _validate_deferred_mode_parameter_sources(self) -> None:
        """Reject null RMS modes that have no startup value owner.

        A ``Const(None)`` mode is valid only when explicit/API initialization
        supplied a scalar seed or a bound procedural entry owns its runtime
        slot. This prevents an unresolved declaration from silently becoming
        zero while preserving historical files whose mode has a real owner.

        :return: None.
        """
        parameter_uid: int
        expression: Expr | Const
        for parameter_uid, expression in self._mode_runtime_expression_by_uid.items():
            if isinstance(expression, Const) and expression.value is None:
                parameter_index: int | None = self._uid2idx_event_params.get(parameter_uid, None)
                seeded_value: float | int | complex | None = self.event_params_init_dict.get(
                    parameter_uid,
                    None,
                )
                has_procedural_owner: bool = (
                    parameter_index is not None
                    and self._procedural_logic_updater is not None
                    and parameter_index in self._procedural_logic_updater.get_output_parameter_indices()
                )
                if seeded_value is not None or has_procedural_owner:
                    pass
                else:
                    raise ValueError(
                        "Unresolved RMS mode parameter "
                        + f"uid={parameter_uid}: Const(None) has no API, explicit or procedural source."
                    )
            else:
                pass

    def _register_runtime_event_parameters(self, dev: ALL_DEV_TYPES, mdl: Block) -> None:
        """
        Register runtime-updatable parameters declared by the device block.
        """
        if not mdl.event_dict and not mdl.mode_dict:
            return

        mode_parameter_uids: set[int] = set()
        mode_parameter: Var
        for mode_parameter in mdl.mode_dict:
            mode_parameter_uids.add(mode_parameter.uid)

        for parameter in mdl.event_dict.keys():
            self._event_parameter_device_idtags[parameter.uid] = dev.idtag

            # ``Block.event_dict`` declares parameters that the user expects to be
            # externally drivable during the simulation. Some models, such as the
            # RMS load template, initialize those parameters with expressions that
            # reference algebraic outputs only to copy the steady-state operating
            # point at ``t = 0``. Classifying them as discrete just because the
            # initialization expression references system variables prevents ramp
            # events from ever using the continuous runtime path and collapses the
            # transition into a latched step. The runtime partition therefore uses
            # the initialization expression only as the starting value, while the
            # event_dict parameter itself remains a continuous event target.
            if parameter.uid in mode_parameter_uids:
                self._discrete_event_parameter_uids.add(parameter.uid)
            else:
                self._continuous_event_parameter_uids.add(parameter.uid)

        for parameter in mdl.mode_dict.keys():
            self._event_parameter_device_idtags[parameter.uid] = dev.idtag
            self._discrete_event_parameter_uids.add(parameter.uid)

    def _expression_references_system_vars(self, expression: Expr | Const) -> bool:
        if isinstance(expression, Const):
            return False

        try:
            vars_in_expr: List[Var] = get_expression_vars(expression)
        except Exception:
            return False

        for var in vars_in_expr:
            if var.uid in self._uid2idx_vars:
                return True

        return False

    def _event_targets_registered_parameter(self, evt: object, parameter_uid: int) -> bool:
        """
        Return whether the event targets a runtime parameter registered for this device.
        """
        if parameter_uid in self._event_parameter_device_idtags:
            registered_device_idtag: str | None = self._event_parameter_device_idtags[parameter_uid]
        else:
            registered_device_idtag = None

        try:
            event_device_idtag: str = str(evt.device_idtag)
        except Exception:
            event_device_idtag = ""

        if registered_device_idtag is None:
            return False

        if event_device_idtag == "":
            return True

        return registered_device_idtag == event_device_idtag

    @property
    def boundary_update(self):
        return self

    def _get_rms_events_for_group(self, rms_events_group: RmsEventsGroup | None) -> List[RmsEvent]:
        if rms_events_group is None:
            return list(self.grid.rms_events)

        selected_events = list()

        for evt in self.grid.rms_events:
            try:
                if evt.group.idtag == rms_events_group.idtag:
                    selected_events.append(evt)
                else:
                    pass
            except Exception:
                pass

        return selected_events

    def _freeze_runtime_state_references(self, runtime_eqs: List[Expr | Const]) -> List[Expr | Const]:
        uid_bindings: Dict[int, float] = dict()

        for uid, value in self.init_guess.items():
            if value is None:
                continue
            try:
                value_real = float(np.real(value))
            except Exception:
                continue
            if np.isfinite(value_real):
                uid_bindings[int(uid)] = value_real

        for parameter, equation in zip(self._runtime_all_parameters_source, runtime_eqs):
            if not isinstance(parameter, Var):
                continue
            if isinstance(equation, Const) and equation.value is not None:
                try:
                    value = float(equation.value)
                except Exception:
                    continue
                if np.isfinite(value):
                    uid_bindings[parameter.uid] = value

        frozen_eqs: List[Expr | Const] = list(runtime_eqs)
        for i, equation in enumerate(runtime_eqs):
            if not isinstance(equation, Expr) or isinstance(equation, Const):
                continue

            expr_vars = get_expression_vars(equation)
            if not any(isinstance(v, Var) and v.uid in self._uid2idx_vars for v in expr_vars):
                continue
            if not all(isinstance(v, Var) and v.uid in uid_bindings for v in expr_vars):
                continue

            try:
                value = float(eval_expr_uid(equation, uid_bindings))
            except Exception:
                continue
            if np.isfinite(value):
                frozen_eqs[i] = Const(value)

        return frozen_eqs

    def _rebuild_runtime_parameter_partition(self) -> None:
        self._runtime_continuous_parameters = list()
        self._runtime_mode_parameters = list()
        self._runtime_continuous_eqs = list()
        self._runtime_mode_eqs = list()

        self._uid2idx_event_params = dict()
        n_source: int = len(self._runtime_all_parameters_source)
        i: int = 0

        while i < n_source:
            parameter: Var = self._runtime_all_parameters_source[i]
            equation: Expr | Const = self._runtime_all_eqs_source[i]

            if parameter.uid in self._discrete_event_parameter_uids:
                self._runtime_mode_parameters.append(parameter)
                self._runtime_mode_eqs.append(equation)
            else:
                self._runtime_continuous_parameters.append(parameter)
                self._runtime_continuous_eqs.append(equation)
            i += 1

        self._runtime_continuous_slice = slice(0, len(self._runtime_continuous_parameters))
        self._runtime_mode_slice = slice(
            len(self._runtime_continuous_parameters),
            len(self._runtime_continuous_parameters) + len(self._runtime_mode_parameters)
        )

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

        self._n_event_params = len(self._variable_parameters)

        for k, parameter in enumerate(self._variable_parameters):
            self._uid2idx_event_params[parameter.uid] = k
            self._compiler_names_dict[parameter.uid] = f"{self.VARIABLE_PARAMS_NAME}[{k}]"
            self._alias_names_dict[parameter.uid] = f"{self.VARIABLE_PARAMS_NAME}_{k}"

    def _initialize_mode_event_state(self) -> None:
        self._mode_event_cursor = dict()

        for uid, event_list in self._scheduled_mode_events.items():
            event_list.sort(key=_get_mode_event_sort_key)
            self._mode_event_cursor[uid] = 0

    def _apply_scheduled_mode_events(self, t_curr: float, full_params: Vec) -> None:
        for uid, event_list in self._scheduled_mode_events.items():
            if uid in self._mode_event_cursor:
                event_idx: int = self._mode_event_cursor[uid]
            else:
                event_idx = 0
            n_events: int = len(event_list)

            while event_idx < n_events:
                event_time: float
                event_value: float
                force_step_alignment: bool
                event_time, event_value, force_step_alignment = event_list[event_idx]

                # Scheduled RMS step events must follow the same strict-after
                # activation boundary as the symbolic ``piecewise`` helper used
                # by the legacy RMS reference path. The symbolic backend applies
                # a new value only once ``t`` is strictly greater than the event
                # time because ``heaviside(0)`` evaluates to zero. Reusing that
                # convention here keeps scheduled mode updates aligned with the
                # historical sampled trajectories.
                if _is_rms_time_strictly_after_event(t_curr=t_curr, event_time=event_time):
                    pass
                else:
                    break

                if uid in self._uid2idx_event_params:
                    runtime_idx: Optional[int] = self._uid2idx_event_params[uid]
                else:
                    runtime_idx = None

                if force_step_alignment:
                    if _is_rms_time_strictly_after_event(t_curr=t_curr, event_time=event_time):
                        if runtime_idx is not None:
                            full_params[runtime_idx] = event_value
                        else:
                            pass
                    else:
                        raise RuntimeError(
                            f"Scheduled RMS mode event at t={event_time} requires exact step alignment, "
                            f"but current solver time is t={t_curr}."
                        )
                else:
                    if runtime_idx is not None:
                        full_params[runtime_idx] = event_value
                    else:
                        pass

                event_idx += 1

            self._mode_event_cursor[uid] = event_idx

    def _evaluate_runtime_expression_with_state(self, expression: Expr | Const, params: Vec, x: Vec, t: float) -> float:
        if isinstance(expression, Const):
            if expression.value is None:
                return 0.0
            else:
                return float(expression.value)

        if isinstance(expression, Var):
            if (
                    expression.uid == self._glob_time.uid
                    or expression.uid in self._external_time_uids
            ):
                return float(t)

            if expression.uid in self._uid2idx_event_params:
                runtime_idx = self._uid2idx_event_params[expression.uid]
            else:
                runtime_idx = None
            if runtime_idx is not None:
                return float(params[runtime_idx])

            if expression.uid in self._uid2idx_params:
                const_idx = self._uid2idx_params[expression.uid]
            else:
                const_idx = None
            if const_idx is not None:
                return float(self._parameters_values[const_idx].value)

            if expression.uid in self._uid2idx_vars:
                var_idx = self._uid2idx_vars[expression.uid]
            else:
                var_idx = None
            if var_idx is not None:
                return float(x[var_idx])

            raise KeyError(
                f"RMS runtime expression variable '{expression.name}' "
                + f"(uid={expression.uid}) is not registered."
            )

        uid_bindings: Dict[int, float] = dict()

        for uid, idx in self._uid2idx_event_params.items():
            uid_bindings[uid] = float(params[idx])

        for uid, idx in self._uid2idx_params.items():
            uid_bindings[uid] = float(self._parameters_values[idx].value)

        for uid, idx in self._uid2idx_vars.items():
            uid_bindings[uid] = float(x[idx])

        uid_bindings[self._glob_time.uid] = float(t)
        external_time_uid: int
        for external_time_uid in self._external_time_uids:
            uid_bindings[external_time_uid] = float(t)

        try:
            result: float = float(expression.eval_uid(uid_bindings))
        except (KeyError, TypeError, ValueError) as evaluation_error:
            raise ValueError(
                "RMS mode initialization expression could not be evaluated "
                + f"at t={float(t):g}: {expression}"
            ) from evaluation_error
        return result

    def _update_dynamic_mode_defaults(self, t: float, x: Vec, params: Vec) -> None:
        for uid, expression in self._mode_runtime_expression_by_uid.items():
            if uid in self._scheduled_mode_events and len(self._scheduled_mode_events[uid]) > 0:
                pass
            else:
                if uid in self._mode_runtime_initialized_uids:
                    pass
                else:
                    if uid in self._uid2idx_event_params:
                        runtime_idx = self._uid2idx_event_params[uid]
                    else:
                        runtime_idx = None

                    if runtime_idx is None:
                        pass
                    elif isinstance(expression, Const) and expression.value is None:
                        # A null mode declaration is a provisional seed owned by
                        # procedural logic. Preserve it until the startup pass.
                        self._mode_runtime_initialized_uids.add(uid)
                    else:
                        params[runtime_idx] = self._evaluate_runtime_expression_with_state(expression, params, x, t)
                        self._mode_runtime_initialized_uids.add(uid)

    def _initialize_latched_mode_defaults(self, t: float, x: Vec) -> None:
        if self._variable_parameters_values is None:
            return

        self._update_dynamic_mode_defaults(
            t=float(t),
            x=x,
            params=self._variable_parameters_values,
        )

    def reset_boundary_update_state(self, t0: float = 0.0) -> None:
        if self.get_variable_parameter_number() > 0 and self._event_params_fn is not None:
            self._variable_parameters_values = self._event_params_fn(np.ones(self.get_variable_parameter_number()),
                                                                     float(t0))
            self._variable_parameters_values = self.def_event_params_fn(self._variable_parameters_values, float(t0))
        else:
            self._variable_parameters_values = np.zeros(0, dtype=np.float64)

        self._mode_event_cursor = dict()
        self._initialize_mode_event_state()
        self._mode_runtime_initialized_uids = set()

        if self._procedural_logic_updater is not None:
            self._procedural_logic_updater.reset()
        else:
            pass

        if self.get_all_vars_number() > 0 and self.get_variable_parameter_number() > 0:
            self._initialize_latched_mode_defaults(t=float(t0), x=self.get_x0())
        else:
            pass

        if self._procedural_logic_updater is not None:
            if self._constant_params is None:
                constant_params: Vec = np.zeros(0, dtype=float)
            else:
                constant_params = self._constant_params
            full_params: Vec = np.concatenate((self._variable_parameters_values.copy(), constant_params))
            self._procedural_logic_updater.initialize_modes(
                t=float(t0),
                x=self.get_x0(),
                params=full_params,
            )
            self._variable_parameters_values[:] = full_params[:self.get_variable_parameter_number()]
        else:
            pass

    def def_event_params_fn(self, ev_param: Vec, t: float) -> Vec:
        """
        Evaluate runtime event parameter expressions while preserving mode latches.

        :param ev_param: Current runtime parameter vector.
        :param t: Simulation time.
        :return: Updated runtime parameter vector.
        """
        runtime_continuous_eqs: List[Expr | Const] = self._runtime_continuous_eqs
        runtime_mode_slice: slice = self._runtime_mode_slice

        if len(runtime_continuous_eqs) == 0 or self._event_params_fn is None:
            return ev_param
        else:
            pass

        mode_snapshot: Optional[Vec] = None
        if runtime_mode_slice.start != runtime_mode_slice.stop:
            mode_snapshot = ev_param[runtime_mode_slice].copy()
        else:
            pass

        # The symbolic event-parameter function still evaluates the baseline
        # runtime expressions. Continuous multi-event parameters are then replayed
        # procedurally below so arbitrary event combinations do not build fragile
        # nested symbolic piecewise trees.
        updated: Vec = self._event_params_fn(ev_param, t)
        updated = self._event_params_fn(updated, t)

        if mode_snapshot is not None:
            updated[runtime_mode_slice] = mode_snapshot
        else:
            pass

        parameter_uid: int
        event_list: List[RmsEvent]
        for parameter_uid, event_list in self._continuous_runtime_events.items():
            runtime_idx: Optional[int] = self._uid2idx_event_params.get(parameter_uid, None)
            if runtime_idx is not None:
                base_value: float = float(updated[runtime_idx])
                updated[runtime_idx] = _evaluate_rms_runtime_parameter_value_from_events(
                    base_value=base_value,
                    event_list=event_list,
                    t_curr=float(t),
                )
            else:
                pass

        return updated

    def update_variable_params(self,
                               t: float,
                               x_snapshot: Optional[Vec] = None,
                               scheduled_t: float | None = None) -> None:
        """
        Update the variable parameters. Continuous runtime parameters are re-evaluated,
        while retained mode parameters are left untouched unless updated by boundary
        logic.

        The RMS implicit solve needs two distinct time views. Continuous ramp-like
        parameters must be evaluated at the current local target time so the
        nonlinear solve sees the interpolated value inside the step. Historical
        scheduled step events, however, must keep the pre-event value on the
        sample aligned with the event instant and only latch afterwards. The
        optional ``scheduled_t`` argument therefore lets the caller decouple the
        continuous symbolic evaluation time from the scheduled event boundary
        time without duplicating the update logic.

        :param t: Continuous symbolic evaluation time.
        :param x_snapshot: Current state snapshot used by boundary logic.
        :param scheduled_t: Optional time used by scheduled step logic.
        :return: None.
        """
        scheduled_time: float

        if scheduled_t is None:
            scheduled_time = float(t)
        else:
            scheduled_time = float(scheduled_t)

        if self._event_params_fn is None:
            raise ValueError("_event_params_fn is None")
        else:
            variable_parameters_values = self.def_event_params_fn(self._variable_parameters_values, t)
            self._apply_scheduled_mode_events(scheduled_time, variable_parameters_values)

        self._variable_parameters_values = variable_parameters_values

        external_time_index: int | None = self._uid2idx_event_params.get(
            self._external_time_parameter.uid,
            None,
        )
        if external_time_index is None:
            pass
        else:
            self._variable_parameters_values[external_time_index] = float(t)

        # Preserve the established public contract for catalog and solver
        # callers. The procedural entries own their retention semantics, while
        # memoryless entries must see every supplied nonlinear state snapshot.
        if self._block_boundary_updater is not None and x_snapshot is not None:
            if self._constant_params is None:
                constant_params: Vec = np.zeros(0, dtype=float)
            else:
                constant_params = self._constant_params

            full_params: Vec = np.concatenate((self._variable_parameters_values.copy(), constant_params))
            self._block_boundary_updater.update(float(t), x_snapshot, full_params)
            self._variable_parameters_values[:] = full_params[:self.get_variable_parameter_number()]
        else:
            pass

    def get_static_state_matrix(self, x: Vec, dx: Vec) -> sp.csc_matrix:
        """
        Build the sparse static Jacobian used by small-signal analysis.

        Keeping the component Jacobians sparse avoids allocating the complete
        augmented matrix as a dense array before the sparse eigensolver starts.

        :param x: State and algebraic variable values.
        :param dx: Differential variable values.
        :return: Static Jacobian in compressed sparse-column format.
        """
        number_of_states: int = self.get_states_number()

        if number_of_states == 0:
            # A purely algebraic problem only contributes its algebraic block.
            algebraic_jacobian: sp.csc_matrix = self.get_j22(x, dx, 1.0e15).tocsc()
            return algebraic_jacobian
        else:
            # Preserve sparsity while assembling the differential-algebraic
            # block matrix.  Power-system Jacobians are sparse by construction.
            state_jacobian: sp.csc_matrix = self.get_j11(x, dx, 1.0e10).tocsc()
            state_to_algebraic_jacobian: sp.csc_matrix = self.get_j12(x, dx, 1.0e10).tocsc()
            algebraic_to_state_jacobian: sp.csc_matrix = self.get_j21(x, dx, 1.0e10).tocsc()
            algebraic_jacobian: sp.csc_matrix = self.get_j22(x, dx, 1.0e15).tocsc()
            static_jacobian: sp.csc_matrix = sp.bmat(
                [[state_jacobian, state_to_algebraic_jacobian],
                 [algebraic_to_state_jacobian, algebraic_jacobian]],
                format="csc",
            )
            return static_jacobian

    def get_small_signal_reference_indices(self) -> tuple[int, int] | None:
        """
        Return the Jacobian row and column that define the AC angle reference.

        The recorded row is the redundant active-power balance of the slack
        bus, while the column is that bus's RMS voltage-angle variable.

        :return: Augmented-Jacobian reference indices, or ``None`` when absent.
        """
        if (self._small_signal_reference_row is not None
                and self._small_signal_reference_column is not None):
            return self._small_signal_reference_row, self._small_signal_reference_column
        else:
            return None

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """Apply one RMS target-boundary update to retained runtime modes.

        :param t: Target solver-boundary time.
        :param x: Accepted state and algebraic snapshot.
        :param params: Mutable full parameter vector.
        :return: None.
        """
        self._update_dynamic_mode_defaults(t=t, x=x, params=params)
        if self._block_boundary_updater is not None:
            self._block_boundary_updater.update(t=t, x=x, params=params)
        else:
            pass
        self._variable_parameters_values[:] = params[: len(self._variable_parameters)]

    def _register_event_parameter_for_block(
            self,
            elm: ALL_DEV_TYPES,
            mdl: Block,
            parameter: Var,
            declared_expression: Expr | Const,
            runtime_expression: Expr | Const | None = None,
    ) -> None:
        """Register one RMS runtime parameter through the shared contract.

        The problem-local API mapping selects the initial source, while the
        declaring block remains authoritative for the runtime role. Wrapper
        blocks may re-export the same object without creating a second slot.

        :param elm: Static device which owns the complete RMS model.
        :param mdl: Block which declares the runtime parameter.
        :param parameter: Runtime parameter to register.
        :param declared_expression: Fallback declared by the block.
        :param runtime_expression: Optional expression retained for runtime use.
        :return: None.
        """
        existing_parameter_index: int | None = self._uid2idx_event_params.get(parameter.uid, None)
        if existing_parameter_index is None:
            pass
        elif self._variable_parameters[existing_parameter_index] is parameter:
            return
        else:
            raise ValueError(
                f"Event parameter '{parameter.name}' (uid={parameter.uid}) is already registered in the system. "
                + "Previous device may have created a duplicate event parameter."
            )

        mapped_initial_value: Const | None = get_api_parameter_initial_value_by_uid(
            parameter=parameter,
            problem_mapping=self._static_parameters_values_mapping,
        )
        effective_expression: Expr | Const = resolve_runtime_parameter_initial_expression(
            device=elm,
            simulation_mode=DynamicSimulationMode.RMS,
            root_block=elm.rms_model,
            owner_block=mdl,
            parameter=parameter,
            declared_expression=declared_expression,
            problem_mapping=self._static_parameters_values_mapping,
            allow_deferred_initialization=parameter.uid in self._discrete_event_parameter_uids,
        )
        if mapped_initial_value is None or mapped_initial_value.value is None:
            pass
        else:
            self.event_params_init_dict[parameter.uid] = mapped_initial_value.value

        self._compiler_names_dict[parameter.uid] = f"{self.VARIABLE_PARAMS_NAME}[{self._n_event_params}]"
        self._alias_names_dict[parameter.uid] = f"{self.VARIABLE_PARAMS_NAME}_{self._n_event_params}"
        self._uid2idx_event_params[parameter.uid] = self._n_event_params
        self._variable_parameters.append(parameter)
        self._event_parameters_eqs0.append(effective_expression)
        self._runtime_all_parameters_source.append(parameter)

        if runtime_expression is None:
            resolved_runtime_expression: Expr | Const = effective_expression
        else:
            resolved_runtime_expression = runtime_expression

        if runtime_expression is None and parameter.uid in self._discrete_event_parameter_uids:
            if isinstance(effective_expression, Const) and effective_expression.value is not None:
                resolved_runtime_expression = Const(float(effective_expression.value))
            else:
                resolved_runtime_expression = Const(0.0)
                self._mode_runtime_expression_by_uid[parameter.uid] = effective_expression
        else:
            pass

        self._runtime_all_eqs_source.append(resolved_runtime_expression)
        self._runtime_all_eqs_source0.append(resolved_runtime_expression)
        self._n_event_params += 1

    def add_variables_to_compilation_dicts(self, elm: ALL_DEV_TYPES, mdl: Block) -> None:
        """Register a complete RMS block hierarchy in compilation storage.

        :param elm: Static device which owns the complete RMS model.
        :param mdl: Current block in the recursive hierarchy traversal.
        :return: None.
        """

        self.add_block_variables_to_compilation_dicts(elm, mdl)
        for child in mdl.children:
            self.add_variables_to_compilation_dicts(elm, child)

    def add_block_variables_to_compilation_dicts(self, elm: ALL_DEV_TYPES, mdl: Block) -> None:
        """
        add variables and parameters info to the system block

        :param elm:
        :type elm: Union[VeraGridEngine.Devices.Substation.bus.Bus, VeraGridEngine.Devices.Injections.load.Load]
        :param mdl:
        :type mdl: VeraGridEngine.Utils.Symbolic.block.Block
        :return:
        :rtype: None
        """

        # i is for variables
        if isinstance(elm, InjectionParent):
            self._register_connected_input_aliases_from_single_bus_model(mdl=mdl,
                                                                         bus_model=elm.bus.rms_model)
        elif isinstance(elm, BranchParent):
            self._register_connected_input_aliases_from_branch_bus_models(mdl=mdl,
                                                                          bus_from_model=elm.bus_from.rms_model,
                                                                          bus_to_model=elm.bus_to.rms_model)
        else:
            pass

        for v in mdl.state_vars:
            if v.uid in self._uid2idx_vars:
                # RMS model wrapper blocks may legally re-expose a child-owned
                # variable through the parent interface. In that case the same
                # symbolic Var instance appears multiple times in the hierarchy
                # and must only be registered once globally.
                if self.sys_vars.get(v.uid) is v:
                    continue
                raise ValueError(f"State variable '{v.name}' (uid={v.uid}) is already registered in the system. "
                                 f"Previous device may have created a duplicate variable.")

            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{self._n_vars}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{self._n_vars}"
            self._uid2idx_vars[v.uid] = self._n_vars
            self._register_global_var_name(name_key=v.name + elm.name, uid=v.uid, block=mdl)
            self.add_device_var(dev=elm, var=v)
            self.sys_vars[v.uid] = v
            self._state_vars.append(v)
            self._n_vars += 1

        for v in mdl.algebraic_vars:
            if v.uid in self._uid2idx_vars:
                # RMS model wrapper blocks may legally re-expose a child-owned
                # variable through the parent interface. In that case the same
                # symbolic Var instance appears multiple times in the hierarchy
                # and must only be registered once globally.
                if self.sys_vars.get(v.uid) is v:
                    continue
                raise ValueError(f"Algebraic variable '{v.name}' (uid={v.uid}) is already registered in the system. "
                                 f"Previous device may have created a duplicate variable.")
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{self._n_vars}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{self._n_vars}"
            self._uid2idx_vars[v.uid] = self._n_vars
            self._register_global_var_name(name_key=v.name + elm.name, uid=v.uid, block=mdl)
            self.add_device_var(dev=elm, var=v)
            self.sys_vars[v.uid] = v
            self._algebraic_vars.append(v)
            self._n_vars += 1

        # j is for parameters

        # for ep, const in mdl.parameters.items():
        #     if ep.uid in self._uid2idx_params:
        #         raise ValueError(f"Parameter '{ep.name}' (uid={ep.uid}) is already registered in the system. "
        #                          f"Previous device may have created a duplicate parameter.")
        #     self._compiler_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}[{self._n_params}]"
        #     self._alias_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}_{self._n_params}"
        #     self._uid2idx_params[ep.uid] = self._n_params
        #     self._constant_parameters.append(ep)
        #     self._parameters_values.append(const)
        #     self._n_params += 1

        for ep, const in mdl.parameters.items():
            if ep.uid in self._uid2idx_params:
                raise ValueError(f"Parameter '{ep.name}' (uid={ep.uid}) is already registered in the system. "
                                 f"Previous device may have created a duplicate parameter.")

            resolved_parameter_value: Const = resolve_constant_parameter_initial_value(
                device=elm,
                simulation_mode=DynamicSimulationMode.RMS,
                root_block=elm.rms_model,
                owner_block=mdl,
                parameter=ep,
                declared_value=const,
                problem_mapping=self._static_parameters_values_mapping,
            )

            self._compiler_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}[{self._n_params}]"
            self._alias_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}_{self._n_params}"
            self._uid2idx_params[ep.uid] = self._n_params
            self._constant_parameters.append(ep)
            # Register only the already validated concrete value. This keeps a
            # missing static mapping from reaching the numerical compiler as a
            # late, context-free ``None`` conversion error.
            self._parameters_values.append(resolved_parameter_value)
            self._n_params += 1

        # m is for variable parameters
        self._register_runtime_event_parameters(dev=elm, mdl=mdl)

        for ep, eq in mdl.event_dict.items():
            self._register_event_parameter_for_block(
                elm=elm,
                mdl=mdl,
                parameter=ep,
                declared_expression=eq,
            )

        for ep, eq in mdl.mode_dict.items():
            self._register_event_parameter_for_block(
                elm=elm,
                mdl=mdl,
                parameter=ep,
                declared_expression=eq,
            )

        # l is for differential vars
        for v in mdl.diff_vars:
            if v.uid in self._uid2idx_diff:
                if self._diff_vars[self._uid2idx_diff[v.uid]] is v:
                    continue
                raise ValueError(f"Differential variable '{v.name}' (uid={v.uid}) is already registered in the system. "
                                 f"Previous device may have created a duplicate differential variable.")
            self._compiler_names_dict[v.uid] = f"{self.DIFF_NAME}[{self._n_diff}]"
            self._alias_names_dict[v.uid] = f"{self.DIFF_NAME}_{self._n_diff}"
            self._uid2idx_diff[v.uid] = self._n_diff
            self._register_global_var_name(name_key=v.name + elm.name, uid=v.uid, block=mdl)
            self.add_device_var(dev=elm, var=v)
            self._diff_vars.append(v)
            self._n_diff += 1

        self._state_eqs.extend(mdl.state_eqs)
        self._algebraic_eqs.extend(mdl.algebraic_eqs)

        if self.progress_signal is not None:
            self.progress_signal.emit(20)

    def set_init_guess(self,
                       mdl: Block,
                       reference_powerflow: VarPowerFlowReferenceType,
                       val: float) -> None:
        """
        Store a power-flow value as the initial guess of a mapped RMS variable.

        :param mdl: RMS model containing the external power-flow mapping.
        :param reference_powerflow: Power-flow quantity identifying the target variable.
        :param val: Initial value expressed in the RMS model's units.
        :return: None.
        """
        var: Var | None = mdl.external_mapping.get(reference_powerflow, None)
        if var is not None:
            self.init_guess[var.uid] = val
        else:
            pass

    def get_equation_at(self, i: int) -> Expr:
        """
        Get the equation at a global position
        :param i:
        :return:
        """
        if i < len(self._state_eqs):
            return self._state_eqs[i]
        else:
            i2 = i - len(self._state_eqs)
            return self._algebraic_eqs[i2]

    def get_init_guess_info(self) -> pd.DataFrame:
        """
        returns a df with uid, name, and initial value for the system variables
        :return:
        :rtype:
        """

        vars_names = list()
        for key, value in self.init_guess.items():
            var_name = self.sys_vars[key].name
            vars_names.append((key, var_name, value))

        return pd.DataFrame(data=vars_names, columns=["key", "var_name", "value"])

    def get_device_vars_dict(self) -> Dict[ALL_DEV_TYPES, List[Var]]:
        """

        :return:
        :rtype:
        """
        return self._vars_info

    def add_device_var(self, dev: ALL_DEV_TYPES, var: Var):
        """
        Associate a variable with a device
        :param dev: Device
        :param var: Variable
        """
        if dev in self._vars_info:
            var_list = self._vars_info[dev]
        else:
            var_list = None

        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            var_list.append(var)

    def get_var_idx(self, v: Var) -> int:
        """

        :param v:
        :return:
        """
        return self._uid2idx_vars[v.uid]

    @property
    def vars_glob_name2uid(self):
        """

        :return:
        """
        return self._vars_glob_name2uid

    def _register_global_var_name(self, name_key: str, uid: int, block: Block | None = None) -> None:
        prev_uid = self._vars_glob_name2uid.get(name_key)
        if prev_uid is None or prev_uid == uid:
            self._vars_glob_name2uid[name_key] = uid
            return

        block_tag = ""
        if block is not None:
            block_tag = f"::{block.name}#{block.uid}"

        disambiguated_key = f"{name_key}{block_tag}"
        if disambiguated_key == name_key:
            disambiguated_key = f"{name_key} [{uid}]"

        if disambiguated_key in self._vars_glob_name2uid and self._vars_glob_name2uid[disambiguated_key] != uid:
            raise ValueError(
                f"Global variable name collision for '{name_key}' and fallback '{disambiguated_key}': "
                f"existing uid={self._vars_glob_name2uid[disambiguated_key]}, new uid={uid}."
            )
        self._vars_glob_name2uid[disambiguated_key] = uid

    @property
    def uid2idx_vars(self):
        """
        :return:
        """
        return self._uid2idx_vars

    @property
    def uid2idx_event_params(self):
        return self._uid2idx_event_params

    @property
    def uid2idx_params(self):
        return self._uid2idx_params

    @property
    def glob_time(self):
        return self._glob_time

    def get_parameters_values(self) -> List[Const]:
        return self._parameters_values

    @property
    def get_algebraic_vars(self):
        """
        :return:
        """
        return self._algebraic_vars

    @property
    def algebraic_vars(self):
        return self._algebraic_vars

    @property
    def algebraic_eqs(self):
        """
        :return:
        """
        return self._algebraic_eqs

    @property
    def variable_parameters(self):
        """
        :return:
        """
        return self._variable_parameters

    @property
    def event_parameters_eqs(self):
        """
        :return:
        """
        return self._event_parameters_eqs

    @property
    def event_parameters_eqs0(self):
        """
        :return:
        """
        return self._event_parameters_eqs0

    @property
    def state_and_algebraic_vars(self) -> List[Var]:
        """
        :return:
        """
        variables = list()
        for lst in [self._state_vars, self._algebraic_vars]:
            for var in lst:
                variables.append(var)

        return variables

    @property
    def state_vars(self):
        """
        :return:
        """
        return self._state_vars

    @property
    def state_eqs(self):
        """
        :return:
        """
        return self._state_eqs

    def get_all_vars_number(self) -> int:
        return self._n_vars

    def get_diff_var_number(self) -> int:
        """
        Get the number of diff vars
        :return:
        """
        return len(self._diff_vars)

    def get_algebraic_var_number(self) -> int:
        return len(self._algebraic_vars)

    def get_states_number(self) -> int:
        return self._n_state

    def get_variable_parameter_number(self) -> int:
        return len(self._variable_parameters)

    def get_x0(self) -> Vec:
        """
        Helper function to build the initial vector
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._state_vars) + len(self._algebraic_vars))

        for uid, val in self.init_guess.items():
            if uid in self._uid2idx_vars:
                i = self._uid2idx_vars[uid]
                x[i] = val
        return x

    def get_eventparams0(self) -> Vec:
        """
        Helper function to build the initial vector
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._variable_parameters))

        for uid, val in self.event_params_init_dict.items():
            i = self._uid2idx_event_params[uid]
            x[i] = val
        return x

    def get_dx0(self) -> Vec:
        """
        Helper function to build the initial vector
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._diff_vars))

        # for uid, val in self.init_guess.items():
        #     i = self._uid2idx_vars[uid]
        #     x[i] = val
        return x

    def initialize_fmu_cs_devices(self, x_snapshot: Vec, t: float = 0.0) -> None:
        """
        Initialize imported FMU Co-Simulation devices before the RMS time loop starts.

        :param x_snapshot: Initial accepted state vector.
        :param t: Initial simulation time.
        :return: None.
        """

        if len(self._fmu_cs_adapters) > 0:
            initialize_rms_fmu_cs_devices(problem=self, x_snapshot=x_snapshot, time_value=t)
            align_rms_fmu_cs_device_output_parameters(problem=self, x_snapshot=x_snapshot, time_value=t)
        else:
            self._fmu_cs_initialized = True

    def advance_fmu_cs_devices(self, t: float, x_snapshot: Vec, h: float) -> bool:
        """
        Advance imported FMU Co-Simulation devices for one RMS communication step.

        :param t: Current simulation time.
        :param x_snapshot: Current accepted state vector.
        :param h: RMS communication step.
        :return: Whether at least one registered CS adapter advanced.
        """

        co_simulation_advanced: bool = False
        if len(self._fmu_cs_adapters) > 0:
            co_simulation_advanced = advance_rms_fmu_cs_devices(
                problem=self,
                time_value=t,
                x_snapshot=x_snapshot,
                step_size=h,
            )
        else:
            pass
        return co_simulation_advanced

    def close_fmu_cs_devices(self) -> None:
        """
        Release imported FMU Co-Simulation devices after the RMS simulation ends.

        :return: None.
        """

        if len(self._fmu_cs_adapters) > 0:
            close_rms_fmu_cs_devices(self)
        else:
            pass

    def initialize_fmu_me_devices(self, x_snapshot: Vec, t: float = 0.0) -> None:
        """
        Initialize imported FMU Model Exchange devices before the RMS time loop starts.

        :param x_snapshot: Initial accepted state vector.
        :param t: Initial simulation time.
        :return: None.
        """

        if len(self._fmu_me_adapters) > 0:
            initialize_rms_fmu_me_devices(problem=self, x_snapshot=x_snapshot, time_value=t)
        else:
            self._fmu_me_initialized = True

    def advance_fmu_me_devices(self, t: float, x_snapshot: Vec, h: float) -> None:
        """
        Advance imported FMU Model Exchange devices for one RMS communication step.

        :param t: Current simulation time.
        :param x_snapshot: Current accepted state vector.
        :param h: RMS communication step.
        :return: None.
        """

        if len(self._fmu_me_adapters) > 0:
            advance_rms_fmu_me_devices(problem=self, time_value=t, x_snapshot=x_snapshot, step_size=h)
        else:
            pass

    def resolve_fmu_me_devices(self, accepted: bool) -> float | None:
        """Resolve all prepared FMI ME candidates after one RMS step.

        :param accepted: Whether the RMS numerical step converged.
        :return: Earlier state-event retry time, or ``None``.
        """

        if len(self._fmu_me_adapters) > 0:
            return resolve_rms_fmu_me_devices(
                problem=self,
                accepted=accepted,
            )
        else:
            return None

    def prepare_fmu_me_state_event_retry(self) -> float | None:
        """Localize an ME state event before any CS device advances.

        :return: Global shortened target time, or ``None``.
        """

        if len(self._fmu_me_adapters) > 0:
            return _prepare_rms_fmu_me_state_event_retry(
                problem=self,
                state_event_time_tolerance=self.options.fmi_state_event_time_tolerance,
                state_event_max_iterations=self.options.fmi_state_event_max_iterations,
            )
        else:
            return None

    def close_fmu_me_devices(self) -> None:
        """
        Release imported FMU Model Exchange devices after the RMS simulation ends.

        :return: None.
        """

        if len(self._fmu_me_adapters) > 0:
            close_rms_fmu_me_devices(self)
        else:
            pass

    def get_dx(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:

        if self._derivative_fn is None:
            raise ValueError("_derivative_fn is None")

        return self._derivative_fn(x, xn, dx, h)

    def rhs_state(self, x: Vec, dx: Vec) -> Vec:

        if self._rhs_state_fn is None:
            raise ValueError("_rhs_state_fn is None")

        return self._rhs_state_fn(x, dx,
                                  self._variable_parameters_values,
                                  self._constant_params)

    def rhs_algebraic(self, x: Vec, dx: Vec) -> Vec:
        if self._rhs_algeb_fn is None:
            raise ValueError("_rhs_algeb_fn is None")

        return self._rhs_algeb_fn(x, dx,
                                  self._variable_parameters_values,
                                  self._constant_params)

    def get_j11(self, x: Vec, dx: Vec, h: float):

        if self._j11_fn is None:
            raise ValueError("_j11_fn is None")

        return self._j11_fn(x, dx,
                            self._variable_parameters_values,
                            self._constant_params,
                            h)

    def get_j12(self, x: Vec, dx: Vec, h: float):

        if self._j12_fn is None:
            raise ValueError("_j12_fn is None")

        return self._j12_fn(x, dx,
                            self._variable_parameters_values,
                            self._constant_params,
                            h)

    def get_j21(self, x: Vec, dx: Vec, h: float):

        if self._j21_fn is None:
            raise ValueError("_j21_fn is None")

        return self._j21_fn(x, dx,
                            self._variable_parameters_values,
                            self._constant_params,
                            h)

    def get_j22(self, x: Vec, dx: Vec, h: float):

        if self._j22_fn is None:
            raise ValueError("_j22_fn is None")

        return self._j22_fn(x, dx,
                            self._variable_parameters_values,
                            self._constant_params,
                            h)

    def get_fx_ct(self, x: Vec, dx: Vec) -> sp.csc_matrix:
        """
        Evaluate the continuous-time differential-state Jacobian.

        :param x: Current state vector.
        :param dx: Current state-derivative vector.
        :return: Sparse continuous-time ``df/dx`` matrix.
        """
        if self._fx_ct_fn is None:
            raise ValueError("_fx_ct_fn is None")
        return self._fx_ct_fn(x, dx, self._variable_parameters_values, self._constant_params, 0.0)

    def get_fy_ct(self, x: Vec, dx: Vec) -> sp.csc_matrix:
        """
        Evaluate the continuous-time differential-algebraic Jacobian.

        :param x: Current state vector.
        :param dx: Current state-derivative vector.
        :return: Sparse continuous-time ``df/dy`` matrix.
        """
        if self._fy_ct_fn is None:
            raise ValueError("_fy_ct_fn is None")
        return self._fy_ct_fn(x, dx, self._variable_parameters_values, self._constant_params, 0.0)

    def get_gx_ct(self, x: Vec, dx: Vec) -> sp.csc_matrix:
        """
        Evaluate the continuous-time algebraic-state Jacobian.

        :param x: Current state vector.
        :param dx: Current state-derivative vector.
        :return: Sparse continuous-time ``dg/dx`` matrix.
        """
        if self._gx_ct_fn is None:
            raise ValueError("_gx_ct_fn is None")
        return self._gx_ct_fn(x, dx, self._variable_parameters_values, self._constant_params, 0.0)

    def get_gy_ct(self, x: Vec, dx: Vec) -> sp.csc_matrix:
        """
        Evaluate the continuous-time algebraic Jacobian.

        :param x: Current state vector.
        :param dx: Current state-derivative vector.
        :return: Sparse continuous-time ``dg/dy`` matrix.
        """
        if self._gy_ct_fn is None:
            raise ValueError("_gy_ct_fn is None")
        return self._gy_ct_fn(x, dx, self._variable_parameters_values, self._constant_params, 0.0)

    def get_dt_value(self):
        return self.options.time_step

    def get_compiler_names_dict(self):
        return self._compiler_names_dict

    def get_alias_names_dict(self):
        return self._alias_names_dict

    def get_diff_vars(self):
        return self._diff_vars

    def get_E_matrix(self, x: Vec, dx: Vec):
        # We first find all diff_vars

        all_eqs = self._state_eqs + self._algebraic_eqs
        xdot = self._diff_vars
        E_call = SymbolicJacobian(
            eqs=all_eqs,
            variables=xdot,
            compiler_names_dict=self._compiler_names_dict,
            alias_names_dict=self._alias_names_dict,
            VARS_NAME=self.VARS_NAME,
            DIFF_NAME=self.DIFF_NAME,
            EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
            PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
            static=True
        )

        n_states = self.get_states_number()
        vp = self._variable_parameters_values
        cp = self._constant_params

        n_vars = self._n_vars
        E_value = np.zeros((n_vars, n_vars))
        E_partial = E_call(x, dx, vp, cp, h=0).toarray()

        # Map each d(eq)/d(diff_var_j) column to the column of the diff_var base
        # variable in the global [state_vars + algebraic_vars] ordering.
        for j, dvar in enumerate(xdot):
            base_var = dvar.base_var
            col_idx = self._uid2idx_vars.get(base_var.uid, None)
            if col_idx is None:
                continue
            E_value[:, col_idx] += E_partial[:, j]

        E_value[:n_states, :n_states] -= np.eye(n_states, dtype=E_value.dtype)

        return E_value
    def _seed_rms_input_initialization_from_single_bus_model(self, mdl: Block, bus_model: Block) -> None:
        """
        Seed explicit RMS input initialization from one connected bus model.

        :param mdl: Device RMS block whose root inputs must be initialized.
        :param bus_model: Connected bus RMS block providing authoritative values.
        :return: None.
        """
        bus_mapping: Dict[VarPowerFlowReferenceType, Var | None] = bus_model.external_mapping
        model_var: Var

        for model_var in mdl.in_vars:
            bus_var: Var | None = bus_mapping.get(model_var.ref, None)
            if bus_var is None:
                pass
            else:
                if bus_var.uid in self.uid2idx_vars:
                    self.init_guess[model_var.uid] = self.init_guess.get(
                        bus_var.uid,
                        self.get_x0()[self.uid2idx_vars[bus_var.uid]],
                    )
                else:
                    pass

    def _seed_rms_input_initialization_from_branch_bus_models(self,
                                                              mdl: Block,
                                                              bus_from_model: Block,
                                                              bus_to_model: Block) -> None:
        """
        Seed explicit RMS input initialization from the terminal bus models of one branch.

        :param mdl: Device RMS block whose root inputs must be initialized.
        :param bus_from_model: From-side bus RMS block.
        :param bus_to_model: To-side bus RMS block.
        :return: None.
        """
        from_mapping: Dict[VarPowerFlowReferenceType, Var | None] = bus_from_model.external_mapping
        to_mapping: Dict[VarPowerFlowReferenceType, Var | None] = bus_to_model.external_mapping
        model_var: Var

        for model_var in mdl.in_vars:
            bus_var: Var | None = from_mapping.get(model_var.ref, None)
            if bus_var is None:
                bus_var = to_mapping.get(model_var.ref, None)
            else:
                pass

            if bus_var is None:
                pass
            else:
                if bus_var.uid in self.uid2idx_vars:
                    self.init_guess[model_var.uid] = self.init_guess.get(
                        bus_var.uid,
                        self.get_x0()[self.uid2idx_vars[bus_var.uid]],
                    )
                else:
                    pass

    def _register_connected_input_aliases_from_single_bus_model(self, mdl: Block, bus_model: Block) -> None:
        """
        Register one-block RMS input aliases against one connected bus model.

        :param mdl: Device RMS block whose root inputs must reuse bus compiler names.
        :param bus_model: Connected bus RMS block providing authoritative compiler names.
        :return: None.
        """
        bus_mapping: Dict[VarPowerFlowReferenceType, Var | None] = bus_model.external_mapping
        in_var: Var

        for in_var in mdl.in_vars:
            bus_var: Var | None = bus_mapping.get(in_var.ref, None)
            if bus_var is None:
                pass
            else:
                if bus_var.uid in self._uid2idx_vars:
                    self._compiler_names_dict[in_var.uid] = self._compiler_names_dict[bus_var.uid]
                    self._alias_names_dict[in_var.uid] = self._alias_names_dict[bus_var.uid]
                else:
                    pass

    def _register_connected_input_aliases_from_branch_bus_models(self,
                                                                 mdl: Block,
                                                                 bus_from_model: Block,
                                                                 bus_to_model: Block) -> None:
        """
        Register one-block RMS input aliases against the terminal bus models of one branch.

        :param mdl: Device RMS block whose root inputs must reuse bus compiler names.
        :param bus_from_model: From-side bus RMS block.
        :param bus_to_model: To-side bus RMS block.
        :return: None.
        """
        from_mapping: Dict[VarPowerFlowReferenceType, Var | None] = bus_from_model.external_mapping
        to_mapping: Dict[VarPowerFlowReferenceType, Var | None] = bus_to_model.external_mapping
        in_var: Var

        for in_var in mdl.in_vars:
            bus_var: Var | None = from_mapping.get(in_var.ref, None)
            if bus_var is None:
                bus_var = to_mapping.get(in_var.ref, None)
            else:
                pass

            if bus_var is None:
                pass
            else:
                if bus_var.uid in self._uid2idx_vars:
                    self._compiler_names_dict[in_var.uid] = self._compiler_names_dict[bus_var.uid]
                    self._alias_names_dict[in_var.uid] = self._alias_names_dict[bus_var.uid]
                else:
                    pass
