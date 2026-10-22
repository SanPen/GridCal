# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Dict, List, Callable, Any, Tuple, Set, Optional
import time
import numpy as np
import pandas as pd
import scipy.sparse as sp


from VeraGridEngine.enumerations import (
    DeviceType,
    DynamicEventTransitionType,
    DynamicSimulationMode,
    ParamPowerFlowReferenceType,
    RmsVectorizedNodalBalanceKind,
)
from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr, piecewise, get_expression_vars, hard_sat)
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, RmsInitializationMethod
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
    RmsMappedPowerEntry,
    assemble_rms_mapped_power_references,
    resolve_rms_mapped_power_references,
)
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler, ProceduralExpressionCompiler, RMSCompilerVec
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
from VeraGridEngine.Utils.rms_models_types import build_equivalence_classes_dict


class RmsVectorizedMappedPowerBalanceLayout:
    """Build one vectorized layout from canonical mapped power references.

    The layout exists for one compilation and is never attached to or
    persisted with the dynamic model. Static devices supply every bus index;
    the model mapping supplies only the canonical P/Q quantity semantics.
    """

    __slots__ = (
        "_reference_pairs",
        "_active_expressions",
        "_reactive_expressions",
        "_active_row_indices",
        "_reactive_row_indices",
        "_active_bus_indices",
        "_reactive_bus_indices",
    )

    def __init__(
            self,
            entries: List[RmsMappedPowerEntry],
            active_expressions: List[Expr | Var],
            reactive_expressions: List[Expr | Var],
    ) -> None:
        """Capture the mapped references selected by a representative model.

        :param entries: Normalized mapped-power terminals.
        :param active_expressions: Signed active expressions in declaration order.
        :param reactive_expressions: Signed reactive expressions where available.
        :return: None.
        """
        if (
            len(active_expressions)
            == sum(entry.active_reference is not None for entry in entries)
            and len(reactive_expressions)
            == sum(entry.reactive_reference is not None for entry in entries)
        ):
            pass
        else:
            raise ValueError("RMS balance expressions do not match their mapped references")
        self._reference_pairs: List[Tuple[
            VarPowerFlowReferenceType | None,
            VarPowerFlowReferenceType | None,
        ]] = list(
            (entry.active_reference, entry.reactive_reference) for entry in entries
        )
        self._active_expressions: List[Expr | Var] = list(active_expressions)
        self._reactive_expressions: List[Expr | Var] = list(reactive_expressions)
        self._active_row_indices: List[int] = list()
        self._reactive_row_indices: List[int] = list()
        self._active_bus_indices: List[List[int]] = list(
            list() for _ in active_expressions
        )
        self._reactive_bus_indices: List[List[int]] = list(
            list() for _ in reactive_expressions
        )

    def validate_and_add_device(
            self,
            entries: List[RmsMappedPowerEntry],
            bus_indices: List[int],
    ) -> None:
        """Validate one equivalent instance and retain its physical buses.

        :param entries: Normalized mapped terminals of the instance.
        :param bus_indices: Physical bus for every declaration.
        :return: None.
        """
        reference_pairs = list(
            (entry.active_reference, entry.reactive_reference) for entry in entries
        )
        if (
            reference_pairs == self._reference_pairs
            and len(bus_indices) == len(self._reference_pairs)
        ):
            pass
        else:
            raise ValueError(
                "Structurally equivalent RMS models expose different power references"
            )

        entry_index: int = 0
        active_index: int = 0
        reactive_index: int = 0
        while entry_index < len(bus_indices):
            active_reference, reactive_reference = self._reference_pairs[entry_index]
            if active_reference is not None:
                self._active_bus_indices[active_index].append(bus_indices[entry_index])
                active_index += 1
            else:
                pass
            if reactive_reference is not None:
                self._reactive_bus_indices[reactive_index].append(
                    bus_indices[entry_index]
                )
                reactive_index += 1
            else:
                pass
            entry_index += 1

    def finalize(self, compiled_equations: List[Expr]) -> None:
        """Append captured expressions and freeze their exact compiled rows.

        :param compiled_equations: Representative class equation list.
        :return: None.
        """
        if len(self._active_row_indices) == 0 and len(self._reactive_row_indices) == 0:
            row_start: int = len(compiled_equations)
            self._active_row_indices = list(
                range(row_start, row_start + len(self._active_expressions))
            )
            reactive_start: int = row_start + len(self._active_expressions)
            self._reactive_row_indices = list(
                range(reactive_start, reactive_start + len(self._reactive_expressions))
            )
            compiled_equations.extend(self._active_expressions)
            compiled_equations.extend(self._reactive_expressions)
        else:
            raise ValueError("RMS mapped-power layout was finalized more than once")

    def accumulate(
            self,
            rhs_algebraic: np.ndarray,
            active_power_balance: ObjVec,
            active_power_balance_used: BoolVec,
            reactive_power_balance: ObjVec,
            reactive_power_balance_used: BoolVec,
    ) -> None:
        """Accumulate the mapped references declared by the model class.

        :param rhs_algebraic: Evaluated class equations by row and instance.
        :param active_power_balance: Active nodal accumulator.
        :param active_power_balance_used: Active accumulator occupancy mask.
        :param reactive_power_balance: Reactive nodal accumulator.
        :param reactive_power_balance_used: Reactive accumulator occupancy mask.
        :return: None.
        """
        active_index: int = 0
        while active_index < len(self._active_row_indices):
            active_values: np.ndarray = rhs_algebraic[
                self._active_row_indices[active_index]
            ]
            active_buses: List[int] = self._active_bus_indices[active_index]
            if len(active_values) == len(active_buses):
                pass
            else:
                raise ValueError("RMS mapped active-power layout has inconsistent instance count")
            active_instance_index: int = 0
            while active_instance_index < len(active_buses):
                setP(
                    active_power_balance,
                    active_power_balance_used,
                    active_buses[active_instance_index],
                    active_values[active_instance_index],
                )
                active_instance_index += 1
            active_index += 1

        reactive_index: int = 0
        while reactive_index < len(self._reactive_row_indices):
            reactive_values: np.ndarray = rhs_algebraic[
                self._reactive_row_indices[reactive_index]
            ]
            reactive_buses: List[int] = self._reactive_bus_indices[reactive_index]
            if len(reactive_values) == len(reactive_buses):
                pass
            else:
                raise ValueError("RMS mapped reactive-power layout has inconsistent instance count")
            reactive_instance_index: int = 0
            while reactive_instance_index < len(reactive_buses):
                setQ(
                    reactive_power_balance,
                    reactive_power_balance_used,
                    reactive_buses[reactive_instance_index],
                    reactive_values[reactive_instance_index],
                )
                reactive_instance_index += 1
            reactive_index += 1


class RmsVectorizedNodalBalanceLayout:
    """Store the exact compiled nodal rows shared by RHS and Jacobians.

    Each entry records its physical bus and evaluation rule at equation-build
    time. Capacitive DC rows additionally retain the UID of their bus-local
    power variable; other row kinds must not own one.
    """

    __slots__ = (
        "_kinds",
        "_bus_indices",
        "_local_power_variable_uids",
    )

    def __init__(self) -> None:
        """Create an initially empty nodal layout.

        :return: None.
        """
        self._kinds: List[RmsVectorizedNodalBalanceKind] = list()
        self._bus_indices: List[int] = list()
        self._local_power_variable_uids: List[int | None] = list()

    def add_row(
            self,
            kind: RmsVectorizedNodalBalanceKind,
            bus_index: int,
            local_power_variable_uid: int | None,
    ) -> None:
        """Register one row at the same time its equation is compiled.

        :param kind: Runtime evaluation rule of the row.
        :param bus_index: Physical bus owning the balance.
        :param local_power_variable_uid: Bus-local P variable for capacitive DC.
        :return: None.
        """
        if kind is RmsVectorizedNodalBalanceKind.CAPACITIVE_DC_POWER:
            if local_power_variable_uid is None:
                raise ValueError("Capacitive DC nodal row lacks its local power variable")
            else:
                pass
        else:
            if local_power_variable_uid is None:
                pass
            else:
                raise ValueError("Non-capacitive nodal row cannot own a local power variable")
        self._kinds.append(kind)
        self._bus_indices.append(bus_index)
        self._local_power_variable_uids.append(local_power_variable_uid)

    def evaluate(
            self,
            variables: Vec,
            variable_index_by_uid: Dict[int, int],
            active_power_balance: ObjVec,
            reactive_power_balance: ObjVec,
    ) -> np.ndarray:
        """Evaluate exactly the nodal rows registered during construction.

        :param variables: Current global state and algebraic variable vector.
        :param variable_index_by_uid: Global variable UID-to-index mapping.
        :param active_power_balance: Runtime active-power accumulator.
        :param reactive_power_balance: Runtime reactive-power accumulator.
        :return: Nodal residual values in compiled row order.
        """
        values: np.ndarray = np.empty(len(self._kinds))
        row_index: int = 0
        while row_index < len(self._kinds):
            kind: RmsVectorizedNodalBalanceKind = self._kinds[row_index]
            bus_index: int = self._bus_indices[row_index]
            if kind is RmsVectorizedNodalBalanceKind.ACTIVE_POWER:
                values[row_index] = active_power_balance[bus_index]
            else:
                if kind is RmsVectorizedNodalBalanceKind.REACTIVE_POWER:
                    values[row_index] = reactive_power_balance[bus_index]
                else:
                    if kind is RmsVectorizedNodalBalanceKind.CAPACITIVE_DC_POWER:
                        local_power_uid: int | None = (
                            self._local_power_variable_uids[row_index]
                        )
                        if local_power_uid is None:
                            raise ValueError("Capacitive DC row lost its local power variable")
                        else:
                            local_power_index: int | None = variable_index_by_uid.get(
                                local_power_uid,
                                None,
                            )
                            if local_power_index is None:
                                raise ValueError(
                                    "Capacitive DC local power variable is not compiled"
                                )
                            else:
                                values[row_index] = (
                                    variables[local_power_index]
                                    - active_power_balance[bus_index]
                                )
                    else:
                        raise ValueError("Unsupported RMS vectorized nodal balance kind")
            row_index += 1
        return values

def assign_static_parameters(elm:Any, parameter_reference: ParamPowerFlowReferenceType) -> Const:
    if elm.device_type == DeviceType.LineDevice:
        return assign_line_static_parameters(elm, parameter_reference)
    else:
        raise ValueError(f"Not possible to assign static values to {elm.device_type}")

def assign_line_static_parameters(elm: Any, parameter_reference: ParamPowerFlowReferenceType) -> Const:
    if parameter_reference == ParamPowerFlowReferenceType.g:
        return Const(float(elm.R / (elm.R ** 2 + elm.X ** 2)))
    if parameter_reference == ParamPowerFlowReferenceType.b:
        return Const(float(-elm.X / (elm.R ** 2 + elm.X ** 2)))
    if parameter_reference == ParamPowerFlowReferenceType.bsh:
        return Const(elm.B)
    if parameter_reference == ParamPowerFlowReferenceType.r:
        return Const(elm.R)
    if parameter_reference == ParamPowerFlowReferenceType.l:
        return Const(elm.X)
    else:
        raise ValueError("parameter reference expression missing")


def _tic():
    return time.perf_counter()


def _toc(t0):
    return time.perf_counter() - t0


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


def get_all_uids_from_block_composition_dict(block_composition_dict: Dict[int, List[int]]) -> List[int]:
    return [uid for uids in block_composition_dict.values() for uid in uids]


class RmsProblemDaeFullVec(RmsProblemTemplate):
    """
    DAE (Differential-Algebraic Equation) class to store and manage.

    Responsibilities:
        - Store state and algebraic variables (x, y)
        - Store Jacobian matrices
        - Store residual equations
        - Store sparsity patterns
    """
    VARS_NAME = "vrs"
    VARS_BUS_VM_NAME = "varsbusvm"
    VARS_BUS_VA_NAME = "varsbusva"
    VARS_BUS_VMF_NAME = "varsbusvmf"
    VARS_BUS_VAF_NAME = "varsbusvaf"
    VARS_BUS_VMT_NAME = "varsbusvmt"
    VARS_BUS_VAT_NAME = "varsbusvat"
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
        "_algebraic_vars_equiv_class_dict",
        "_algebraic_eqs_equiv_class_dict",
        "_state_vars",
        "_state_eqs",
        "_state_vars_equiv_class_dict",
        "_state_eqs_equiv_class_dict",
        "_diff_vars",
        "_diff_vars_equiv_class_dict",
        "_variable_parameters",
        "_variable_parameters_equiv_class_dict",
        "_event_parameters_eqs0",
        "_event_parameters_eqs",
        "_constant_parameters",
        "_constant_parameters_equiv_class_dict",
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
        "_rhs_algeb_fn_by_types",
        "_rhs_state_fn_by_types",
        "_rhs_algeb_energy_balance_fn",
        "_j11_fn_by_types",
        "_j12_fn_by_types",
        "_j21_fn_by_types",
        "_j22_fn_by_types",
        "_jbalance_fn",
        "_jbalance_state_fn",
        "_balance_equations",
        "_variable_parameters_values",
        "_last_variable_parameters_values",
        "_constant_params",
        "_block_boundary_updater",
        "_fmu_cs_adapters",
        "_fmu_cs_initialized",
        "_fmu_me_adapters",
        "_fmu_me_initialized",
        "_fmu_me_evaluation_budget",
        "_n_vars",
        "_n_state",
        "_n_alg",
        "_n_algebraic",
        "_n_diff",
        "_n_params",
        "_n_event_params",
        "_class_n_vars",
        "_class_n_diff",
        "_class_n_params",
        "_class_n_event_params",
        "_uid2idx_vars",
        "_uid2idx_diff",
        "_uid2idx_params",
        "_uid2idx_event_params",
        "_uid2idx_vars_vec",
        "_uid2idx_diff_vec",
        "_uid2idx_params_vec",
        "_uid2idx_event_params_vec",
        "_vars_glob_name2uid",
        "_compiler_names_dict",
        "_compiler_names_dict_vect",
        "_alias_names_dict",
        "_alias_names_dict_vect",
        "_vars_info",
        "_glob_time",
        "_state_algeb_vars",
        "_x_gather_idx",
        "_dx_gather_idx",
        "_vp_gather_idx",
        "_cp_gather_idx",
        "_input_matrices_by_model",
        "_model_algebraic_eq_start_idx",
        "_model_state_eq_start_idx",
        "_jac_algeb_col_off",
        "_jac_state_col_off",
        "_jac_global_data",
        "_prof_timings",
        "block_composition_dict",
        "equivalence_dict",
        "reference_class_for_all_blocks_dict",
        "variables_equivalence_dict",
        "P_used_vec",
        "P_vec",
        "Q_used_vec",
        "Q_vec",
        "_balance_eqs_p_equiv_class_dict",
        "_balance_eqs_q_equiv_class_dict",
        "_device_algebraic_rows_by_model_type",
        "_external_time_parameter",
        "_external_time_uids",
        "_j22_global_cols",
        "_j22_global_rows",
        "_jbalance_state_template",
        "_jbalance_template",
        "_mapped_power_layout_by_model_type",
        "_mapped_power_registered_model_uids",
        "_nodal_balance_layout",
        "_rhs_algeb_scatter_idx",
        "_rhs_algeb_source_rows",
        "_rhs_state_scatter_idx",
        "branch_bus_p_vec",
        "branch_bus_q_vec",
        "bus_dict",
        "line_model_types",
        "mdl_index2bus",
        "mdl_index2busfrom",
        "mdl_index2busto",
        "_uid2idx_t",
    )

    def __init__(self,
                 grid: MultiCircuit,
                 options: RmsOptions,
                 pf_results: PowerFlowResults,
                 progress_signal: DummySignal | None = None,
                 progress_text: DummySignal | None = None,
                 cancel_checker: bool = False,
                 logger: Logger | None = None) -> None:
        """Build the fully vectorized RMS differential-algebraic problem.

        :param grid: Grid containing the static network and RMS models.
        :param options: RMS simulation and initialization options.
        :param pf_results: Power-flow operating point used for initialization.
        :param progress_signal: Optional signal used to report numeric progress.
        :param progress_text: Optional signal used to report progress messages.
        :param cancel_checker: Compatibility flag reserved for cancellation checks.
        :param logger: Optional logger used for model and initialization diagnostics.
        :return: None.
        """
        super().__init__(progress_signal=progress_signal,
                         progress_text=progress_text)

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

        # Keep the exact nodal row order used by both RHS and Jacobian assembly.
        self._balance_equations: List[Expr | Const] = list()
        self._nodal_balance_layout: RmsVectorizedNodalBalanceLayout = (
            RmsVectorizedNodalBalanceLayout()
        )

        # for vectorization, a dict of [equivalence class uid, list of expressions], every item corresponds to a type of model
        # when precessing the first model op a type the dictionaries will be filled.
        self._algebraic_eqs_equiv_class_dict: Dict[int, List[Expr]] = dict()
        self._algebraic_vars_equiv_class_dict: Dict[int, List[Var]] = dict()
        self._state_eqs_equiv_class_dict: Dict[int, List[Expr]] = dict()
        self._state_vars_equiv_class_dict: Dict[int, List[Var]] = dict()
        self._diff_vars_equiv_class_dict: Dict[int, List[Var]] = dict()
        self._constant_parameters_equiv_class_dict: Dict[int, List[Var]] = dict()
        self._variable_parameters_equiv_class_dict: Dict[int, List[Var]] = dict()

        # imput matrices by model for vectorization
        self._input_matrices_by_model: Dict[int, List[Vec]] = dict()

        # precomputed gather indices for vectorized input assembly
        self._x_gather_idx: Dict[int, np.ndarray] = dict()
        self._dx_gather_idx: Dict[int, np.ndarray] = dict()
        self._vp_gather_idx: Dict[int, np.ndarray] = dict()
        self._cp_gather_idx: Dict[int, np.ndarray] = dict()
        self._rhs_state_scatter_idx: Dict[int, np.ndarray] = dict()
        self._rhs_algeb_scatter_idx: Dict[int, np.ndarray] = dict()
        self._rhs_algeb_source_rows: Dict[int, np.ndarray] = dict()
        self._device_algebraic_rows_by_model_type: Dict[int, List[int]] = dict()

        # Jacobian vectorization: per-type column offsets for global assembly
        self._jac_state_col_off: Dict[int, np.ndarray] = dict()
        self._jac_algeb_col_off: Dict[int, np.ndarray] = dict()

        # Global Jacobian templates and scatter maps for Vec assembly
        # Each entry: (csc_template, scatter_map)
        # scatter_map[model_type] -> array (nnz_type, n_inst) of global data indices
        self._jac_global_data: Dict[str, Tuple[sp.csc_matrix, Dict[int, np.ndarray]]] = dict()

        # mapping from model uid â†’ global start index of its state equations
        self._model_state_eq_start_idx: Dict[int, int] = dict()
        self._model_algebraic_eq_start_idx: Dict[int, int] = dict()

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
        self._scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]] = dict()
        self._mode_event_cursor: Dict[int, int] = dict()
        self._active_events_group: RmsEventsGroup | None = None
        self._mode_runtime_expression_by_uid: Dict[int, Expr | Const] = dict()
        self._mode_runtime_initialized_uids: Set[int] = set()
        self._procedural_expression_compiler: ProceduralExpressionCompiler | None = None
        self._procedural_logic_updater: BlockProceduralLogicUpdater | None = None
        self._manufacturer_native_runtime_session: ManufacturerNativeRuntimeSessionProtocol | None = None

        self._rhs_state_fn_by_types: Dict[int, Callable[[Vec, Vec, Vec, Vec], Vec]] = dict()
        self._rhs_algeb_fn_by_types: Dict[int, Callable[[Vec, Vec, Vec, Vec], Vec]] = dict()
        self._rhs_algeb_energy_balance_fn: Callable[[Vec, Vec, Vec, Vec], Vec] | None = None

        self._j11_fn_by_types: Dict[int, Callable[[Vec, Vec, Vec, Vec, float], np.ndarray] | None] = dict()
        self._j12_fn_by_types: Dict[int, Callable[[Vec, Vec, Vec, Vec, float], np.ndarray] | None] = dict()
        self._j21_fn_by_types: Dict[int, Callable[[Vec, Vec, Vec, Vec, float], np.ndarray] | None] = dict()
        self._j22_fn_by_types: Dict[int, Callable[[Vec, Vec, Vec, Vec, float], np.ndarray] | None] = dict()

        # precomputed J22 global row/col indices for triplet assembly
        self._j22_global_rows: Dict[int, np.ndarray] = dict()
        self._j22_global_cols: Dict[int, np.ndarray] = dict()

        self._jbalance_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None
        self._jbalance_state_fn: Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix] | None = None
        self._jbalance_state_template: sp.csc_matrix | None = None
        self._jbalance_template: sp.csc_matrix | None = None
        # The JIT compilers return allocation wrappers with these public call signatures.
        self._derivative_fn: Callable[[Vec, Vec, Vec, float], Vec] | None = None
        self._event_params_fn: Callable[[Vec, float], Vec] | None = None

        self._variable_parameters_values: Optional[Vec] = None
        self._last_variable_parameters_values: Optional[Vec] = None
        self._constant_params: Optional[Vec] = None
        self._block_boundary_updater: Any | None = None
        self._fmu_cs_adapters: List[object] = list()
        self._fmu_cs_initialized: bool = False
        self._fmu_me_adapters: List[object] = list()
        self._fmu_me_initialized: bool = False
        self._fmu_me_evaluation_budget: FmuMeEvaluationBudget | None = None
        self._prof_timings: Dict[str, float] = dict()

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

        # dictionaries for compilation names in vectorized
        self._compiler_names_dict_vect: Dict[int, Dict[int, str]]= dict()
        self._alias_names_dict_vect: Dict[int, Dict[int, str]]= dict()

        # per-class variable/parameter counters (indices restart from 0 for each class)
        self._class_n_vars: Dict[int, int] = dict()
        self._class_n_diff: Dict[int, int] = dict()
        self._class_n_params: Dict[int, int] = dict()
        self._class_n_event_params: Dict[int, int] = dict()

        # dictionaries for compilation names
        self._compiler_names_dict: Dict[int, str] = dict()
        self._alias_names_dict: Dict[int, str] = dict()

        # dictionaries for variable position in the variables arrays vectorized
        self._uid2idx_vars_vec: Dict[int, Dict[int, int]] = dict()
        self._uid2idx_event_params_vec: Dict[int, Dict[int, int]] = dict()
        self._uid2idx_params_vec: Dict[int, Dict[int, int]] = dict()
        self._uid2idx_diff_vec: Dict[int, Dict[int, int]] = dict()

        # dictionaries for variable position in the variables arrays
        self._uid2idx_vars: Dict[int, int] = dict()
        self._uid2idx_event_params: Dict[int, int] = dict()
        self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()

        # balace equations vectorized
        self._balance_eqs_p_equiv_class_dict: Dict[int, Vec] = dict()
        self._balance_eqs_q_equiv_class_dict: Dict[int, Vec] = dict()
        self.mdl_index2bus: Dict[int, List[int]] = dict()
        self.mdl_index2busfrom: Dict[int, List[int]] = dict()
        self.mdl_index2busto: Dict[int, List[int]] = dict()
        self.line_model_types: List[int] = list()
        self._mapped_power_layout_by_model_type: Dict[
            int,
            RmsVectorizedMappedPowerBalanceLayout,
        ] = dict()
        self._mapped_power_registered_model_uids: Set[int] = set()


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
        self.P_vec: ObjVec = np.zeros(n, dtype=object)
        self.Q_vec: ObjVec = np.zeros(n, dtype=object)
        self.P_used_vec: BoolVec = np.zeros(n, dtype=bool)
        self.Q_used_vec: BoolVec = np.zeros(n, dtype=bool)
        self.branch_bus_p_vec = np.zeros(n, dtype=float)
        self.branch_bus_q_vec = np.zeros(n, dtype=float)

        P: ObjVec = np.zeros(n, dtype=object)
        Q: ObjVec = np.zeros(n, dtype=object)
        P_used: BoolVec = np.zeros(n, dtype=bool)
        Q_used: BoolVec = np.zeros(n, dtype=bool)

        # general indexes for variables and parameters
        self._n_vars = 0
        self._n_params = 0
        self._n_event_params = 0
        self._n_diff = 0

        print("starting to type models")

        self.equivalence_dict, self.variables_equivalence_dict, self.block_composition_dict, self.reference_class_for_all_blocks_dict = build_equivalence_classes_dict(self.grid)
        print("typing models done!")
        ######################################## Initialize devices ########################################

        # initialize buses
        self.bus_dict: Dict[Bus, int] = dict()

        for bus_num, elm in enumerate(self.grid.buses):

            self.bus_dict[elm] = bus_num

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

                if VarPowerFlowReferenceType.If_dc in elm.rms_model.external_mapping:
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
                        configured_method=self.options.initialization_method, mdl=elm.rms_model,
                        init_guess=self.init_guess, uid2idx_vars=self._uid2idx_vars)
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
                            external_uid_values=self._get_explicit_external_uid_values(
                                mdl=elm.rms_model,
                            ),
                            verbose=bool(self.options.verbose > 0),
                        )
                        if explicit_initialization_result.converged:
                            self.init_guess = explicit_initialization_result.init_guess
                            diff_init_guess_common = explicit_initialization_result.diff_init_guess
                        else:
                            raise RuntimeError(explicit_initialization_result.message)
                    elif initialization_method == RmsInitializationMethod.PseudoTransient:
                        self.init_guess = init_pseudo_transient(
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
                # add model to system block
                self.sys_block.add(elm.rms_model)

                # add variable to conservation equations of the bus to which the element is connected
                f = self.bus_dict[elm.bus_from]
                t = self.bus_dict[elm.bus_to]

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
                f = self.bus_dict[elm.bus_from]
                t = self.bus_dict[elm.bus_to]
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

                f = self.bus_dict[elm.bus_from]
                t = self.bus_dict[elm.bus_to]
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
                    configured_method=self.options.initialization_method, mdl=elm.rms_model,
                    init_guess=self.init_guess, uid2idx_vars=self._uid2idx_vars)
                if initialization_method in (RmsInitializationMethod.Explicit, RmsInitializationMethod.ConsistentNewton):
                    # common initialization to integrate
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
                        external_uid_values=self._get_explicit_external_uid_values(
                            mdl=elm.rms_model,
                        ),
                        verbose=bool(self.options.verbose > 0),
                    )
                    if explicit_initialization_result.converged:
                        self.init_guess = explicit_initialization_result.init_guess
                        diff_init_guess_common = explicit_initialization_result.diff_init_guess
                    else:
                        raise RuntimeError(explicit_initialization_result.message)

                elif initialization_method == RmsInitializationMethod.PseudoTransient:
                    self.init_guess = init_pseudo_transient(
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

        injection_init_data = self.get_injection_init_data(bus_dict=self.bus_dict)

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
                bus_index = self.bus_dict[elm.bus]

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

                # Keep the per-device PF dispatch for AC and DC injections. The
                # bus aggregate cannot identify the share owned by this model.
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.P,
                                    Sdev.real)

                if elm.bus.is_dc:
                    # Reactive power is not part of the DC model contract.
                    pass
                else:
                    self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Q,
                                        Sdev.imag)

                    # Keep power and current coordinates on the identical
                    # converged operating point before explicit initialization.
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

                k = self.bus_dict[elm.bus]
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
                    configured_method=self.options.initialization_method, mdl=elm.rms_model,
                    init_guess=self.init_guess, uid2idx_vars=self._uid2idx_vars)
                if initialization_method in (RmsInitializationMethod.Explicit, RmsInitializationMethod.ConsistentNewton):

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
                        external_uid_values=self._get_explicit_external_uid_values(
                            mdl=elm.rms_model,
                        ),
                        verbose=bool(self.options.verbose > 0),
                    )
                    if explicit_initialization_result.converged:
                        self.init_guess = explicit_initialization_result.init_guess
                        diff_init_guess_common = explicit_initialization_result.diff_init_guess
                    else:
                        raise RuntimeError(explicit_initialization_result.message)
                    # initialize variables with no init equation assigned
                    # run_rms_consistent_initialization(self, self.options)

                elif initialization_method == RmsInitializationMethod.PseudoTransient:
                    self.init_guess = init_pseudo_transient(
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
                        max_iter=100,
                        tol=min(1e-5, self.options.tolerance),
                        verbose=bool(self.options.verbose > 0),
                    )

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
            else:
                pass

        # Freeze mapped-power auxiliary rows only after every model instance has
        # populated its final equivalence class and physical bus mappings.
        self._finalize_mapped_power_layouts()

        # add the nodal balance equations
        for i, elm in enumerate(self.grid.buses):
            if not P_used[i] and not Q_used[i]:
                raise ValueError("Isolated RMS bus has no nodal balance equation")
            else:
                if elm.is_dc:
                    dc_balance_equation: Expr | Const = build_dc_bus_nodal_power_equation(
                        bus_rms_model=elm.rms_model,
                        nodal_power_balance=P[i],
                    )
                    self._algebraic_eqs.append(dc_balance_equation)
                    self._balance_equations.append(dc_balance_equation)
                    has_capacitive_state: bool = dc_bus_rms_model_has_capacitive_state(
                        bus_rms_model=elm.rms_model,
                    )
                    if has_capacitive_state:
                        local_power_variable: Var | None = (
                            elm.rms_model.E(VarPowerFlowReferenceType.P)
                            if VarPowerFlowReferenceType.P
                            in elm.rms_model.external_mapping else None
                        )
                        if local_power_variable is not None:
                            self._nodal_balance_layout.add_row(
                                kind=RmsVectorizedNodalBalanceKind.CAPACITIVE_DC_POWER,
                                bus_index=i,
                                local_power_variable_uid=local_power_variable.uid,
                            )
                        else:
                            raise ValueError(
                                "Capacitive DC bus lacks its compiled local power variable"
                            )
                    else:
                        self._nodal_balance_layout.add_row(
                            kind=RmsVectorizedNodalBalanceKind.ACTIVE_POWER,
                            bus_index=i,
                            local_power_variable_uid=None,
                        )
                else:
                    # Converter terminals remain physical AC buses in the
                    # canonical topology, with both reactive and active rows.
                    self._algebraic_eqs.append(Q[i])
                    self._algebraic_eqs.append(P[i])
                    self._balance_equations.append(Q[i])
                    self._balance_equations.append(P[i])
                    self._nodal_balance_layout.add_row(
                        kind=RmsVectorizedNodalBalanceKind.REACTIVE_POWER,
                        bus_index=i,
                        local_power_variable_uid=None,
                    )
                    self._nodal_balance_layout.add_row(
                        kind=RmsVectorizedNodalBalanceKind.ACTIVE_POWER,
                        bus_index=i,
                        local_power_variable_uid=None,
                    )

        # Imported time inputs retain their source UIDs but share one typed
        # runtime value slot. Register it before dt/delta so the established
        # final-two integration-parameter layout remains unchanged.
        self._variable_parameters.append(self._external_time_parameter)
        self._event_parameters_eqs0.append(Const(0.0))
        self._runtime_all_parameters_source.append(self._external_time_parameter)
        self._runtime_all_eqs_source.append(Const(0.0))
        self._compiler_names_dict[self._external_time_parameter.uid] = (
            f"{self.VARIABLE_PARAMS_NAME}[{self._n_event_params}]"
        )
        self._alias_names_dict[self._external_time_parameter.uid] = (
            f"{self.VARIABLE_PARAMS_NAME}_{self._n_event_params}"
        )
        self._uid2idx_event_params[self._external_time_parameter.uid] = (
            self._n_event_params
        )
        self._n_event_params += 1

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
        self._bind_external_time_compiler_names()

        for it, eq in enumerate(self._event_parameters_eqs0):
            if isinstance(eq, Const) and eq.value is None:
                raise Exception(f' Event parameter {self._variable_parameters[it]} has None Value')

        # Complete assembly includes the original nodal balance rows.

    def _get_explicit_external_uid_values(self, mdl: Block) -> Dict[int, float]:
        """Bind imported explicit inputs and retain exact time-source UIDs.

        :param mdl: Symbolic model whose explicit equations can consume time.
        :return: Startup input values keyed by exact imported variable UIDs.
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
        """Route imported time UIDs through the typed runtime parameter slot.

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

    def _set_external_time_value(self, time_value: float) -> None:
        """Store the current solver time in the typed runtime parameter slot.

        :param time_value: Current local RMS solver time in seconds.
        :return: None.
        """
        external_time_index: int | None = self._uid2idx_event_params.get(
            self._external_time_parameter.uid,
            None,
        )
        if external_time_index is None or self._variable_parameters_values is None:
            pass
        else:
            self._variable_parameters_values[external_time_index] = float(time_value)

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
            collect_continuous_events: Dict[int, List[dict[str, Any]]] = {
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
                                collect_continuous_events[parameter_uid].append(
                                    dict({
                                        # Historical RMS ``event_dict`` step events were evaluated through the
                                        # symbolic runtime parameter path at the event time itself. Restoring that
                                        # exact activation time preserves the legacy ``Pl0`` trajectories while the
                                        # ramp branch below continues to use the dedicated continuous interpolation
                                        # logic introduced for ramp support.
                                        "time": float(rms_evt.time),
                                        "value": float(rms_evt.value),
                                        "end_time": None,
                                        "transition_type": DynamicEventTransitionType.Step,
                                    })
                                )
                            else:
                                pass
                    else:
                        if parameter_uid in collect_continuous_events:
                            collect_continuous_events[parameter_uid].append(
                                dict({
                                    "time": float(rms_evt.time),
                                    "value": float(rms_evt.value),
                                    "end_time": None if rms_evt.end_time is None else float(rms_evt.end_time),
                                    "transition_type": transition_tpe,
                                })
                            )
                        else:
                            pass

        for parameter_uid, event_specs in collect_continuous_events.items():
            if len(event_specs) == 0:
                pass
            else:
                parameter_index: int | None = None
                runtime_parameter: Var

                # The continuous-event replacement must target the exact runtime
                # parameter slot inside ``_runtime_all_parameters_source``. Using
                # the broader event-parameter index map can hit a different slot
                # once extra runtime parameters such as ``dt`` and ``delta`` are
                # appended later in the RMS setup.
                for runtime_parameter_index, runtime_parameter in enumerate(self._runtime_all_parameters_source):
                    if runtime_parameter.uid == parameter_uid:
                        parameter_index = runtime_parameter_index
                        break
                    else:
                        pass

                if parameter_index is None:
                    active_expr = Const(0.0)
                else:
                    active_expr = active_runtime_eqs[parameter_index]
                sorted_specs: List[dict[str, Any]] = sorted(event_specs, key=lambda event_spec: float(event_spec["time"]))
                event_spec: dict[str, Any]

                for event_spec in sorted_specs:
                    transition_tpe: DynamicEventTransitionType = event_spec["transition_type"]

                    if transition_tpe == DynamicEventTransitionType.Ramp:
                        start_time: float = float(event_spec["time"])
                        end_time_raw: Any = event_spec["end_time"]

                        if end_time_raw is not None:
                            end_time: float = float(end_time_raw)

                            if end_time > start_time:
                                active_expr = _build_ramp_runtime_expr(time_var=self._glob_time,
                                                                      start_time=start_time,
                                                                      end_time=end_time,
                                                                      before_expr=active_expr,
                                                                      final_value=float(event_spec["value"]))
                            else:
                                active_expr = piecewise(time_var=self._glob_time,
                                                        t_events=np.asarray([float(event_spec["time"])], dtype=np.float64),
                                                        new_values=np.asarray([float(event_spec["value"])], dtype=np.float64),
                                                        default_value=active_expr)
                        else:
                            active_expr = piecewise(time_var=self._glob_time,
                                                    t_events=np.asarray([float(event_spec["time"])], dtype=np.float64),
                                                    new_values=np.asarray([float(event_spec["value"])], dtype=np.float64),
                                                    default_value=active_expr)
                    else:
                        active_expr = piecewise(time_var=self._glob_time,
                                                t_events=np.asarray([float(event_spec["time"])], dtype=np.float64),
                                                new_values=np.asarray([float(event_spec["value"])], dtype=np.float64),
                                                default_value=active_expr)

                if parameter_index is None:
                    pass
                else:
                    active_runtime_eqs[parameter_index] = active_expr

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
        rms_compiler_all_models = RMSCompiler(
            variables=self._state_algeb_vars,
            diff_vars=self._diff_vars,
            v_params=self._variable_parameters,
            c_params=self._constant_parameters,
            compiler_names_dict=self._compiler_names_dict
        )
        timings["Compiler Setup"] = _toc(t0)

        t0 = _tic()
        self._derivative_fn = rms_compiler_all_models.compile_derivative_fn(self._uid2idx_vars)
        timings["SymbolicDerivative"] = _toc(t0)

        t0 = _tic()
        self._event_params_fn = rms_compiler_all_models.compile_event_params_fn(
            eqs=self._event_parameters_eqs,
            alias_names_dict=self._alias_names_dict,
            EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
            TIME_NAME=self.TIME_NAME,
        )
        timings["Event parameters"] = _toc(t0)

        t0 = _tic()
        # here we iterate throurgh equivalence_dict and fill the self._rhs_by_types
        for model_type in self.equivalence_dict.keys():
            if  self._algebraic_eqs_equiv_class_dict[model_type] or self._state_eqs_equiv_class_dict[model_type]:

                rms_compiler = RMSCompilerVec(
                    variables=self._state_vars_equiv_class_dict[model_type] + self._algebraic_vars_equiv_class_dict[model_type],
                    diff_vars=self._diff_vars_equiv_class_dict[model_type],
                    v_params=self._variable_parameters_equiv_class_dict[model_type],
                    c_params=self._constant_parameters_equiv_class_dict[model_type],
                    compiler_names_dict=self._compiler_names_dict_vect[model_type]
                )

                rhs_algeb_fn = rms_compiler.compile_rhs(self._algebraic_eqs_equiv_class_dict[model_type], "rhs_algeb_" + str(model_type))
                device_algebraic_rows: List[int] = (
                    self._device_algebraic_rows_by_model_type.get(
                        model_type,
                        list(),
                    )
                )
                device_algebraic_equations: List[Expr] = list(
                    self._algebraic_eqs_equiv_class_dict[model_type][row_index]
                    for row_index in device_algebraic_rows
                )
                if len(self._state_eqs_equiv_class_dict[model_type]) != 0:
                    t0 = _tic()
                    rhs_state_fn = rms_compiler.compile_rhs(self._state_eqs_equiv_class_dict[model_type], "rhs_state_" + str(model_type))
                    timings["RHS state"] = _toc(t0)

                    t0 = _tic()
                    j11_fn = rms_compiler.compile_sparse_jacobian(self._state_eqs_equiv_class_dict[model_type], self._state_vars_equiv_class_dict[model_type], "j11_" + str(model_type))
                    timings["J11 (dF/dx)"] = _toc(t0)

                    t0 = _tic()
                    j12_fn = rms_compiler.compile_sparse_jacobian(self._state_eqs_equiv_class_dict[model_type], self._algebraic_vars_equiv_class_dict[model_type], "j12_" + str(model_type))
                    timings["J12 (dF/dy)"] = _toc(t0)

                    t0 = _tic()
                    j21_fn = rms_compiler.compile_sparse_jacobian(device_algebraic_equations, self._state_vars_equiv_class_dict[model_type], "j21_" + str(model_type))
                    timings["J21 (dG/dx)"] = _toc(t0)

                    t0 = _tic()
                    j22_fn = rms_compiler.compile_sparse_jacobian(device_algebraic_equations, self._algebraic_vars_equiv_class_dict[model_type], "j22_" + str(model_type))
                    timings["J22 (dG/dy)"] = _toc(t0)

                else:
                    t0 = _tic()
                    j22_fn = rms_compiler.compile_sparse_jacobian(device_algebraic_equations, self._algebraic_vars_equiv_class_dict[model_type], "j22_" + str(model_type))
                    timings["J22 only (no states)"] = _toc(t0)

                    rhs_state_fn = None
                    j11_fn = None
                    j12_fn = None
                    j21_fn = None

                self._rhs_state_fn_by_types[model_type] = rhs_state_fn
                self._rhs_algeb_fn_by_types[model_type] = rhs_algeb_fn

                self._j11_fn_by_types[model_type] = j11_fn
                self._j12_fn_by_types[model_type] = j12_fn
                self._j21_fn_by_types[model_type] = j21_fn
                self._j22_fn_by_types[model_type] = j22_fn

        self._jbalance_state_fn = rms_compiler_all_models.compile_sparse_jacobian(
            self._balance_equations, self._state_vars, "j_balance_state"
        )
        if len(self._balance_equations) > 0:
            self._jbalance_fn = rms_compiler_all_models.compile_sparse_jacobian(
                self._balance_equations, self._algebraic_vars, "j_balance"
            )

        if self.options.verbose > 0:
            print(f"Model compiled with {self._n_vars} variables")
            print("\nCompilation timing summary:")
            for k, v in timings.items():
                print(f"  {k:30s}: {v:8.4f} s")
            print(f"\nTotal JIT compile time: {sum(timings.values()):.4f} s")

        self._precompute_gather_indices()

        variable_parameters_init = np.ones(self.get_variable_parameter_number())

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

        # Build global Jacobian templates for Vec assembly
        self._build_global_jacobian_templates()
        self._precompute_balance_jacobian_templates()

        # we mark the problem as ready for simulation
        if self.options.initialization_method in (
                RmsInitializationMethod.ConsistentNewton, RmsInitializationMethod.Auto,
                RmsInitializationMethod.PseudoTransient):
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

    def _build_global_jacobian_templates(self):
        n_states = self.get_states_number()
        n_algebraic = self._n_algebraic

        # Each Jacobian block references variables that are NOT necessarily
        # contiguous in the global variable vector (bus branch algebraic
        # variables sit at local positions 0..n_bus_vars-1, then block state
        # vars, then block algebraic vars).  We therefore build a column
        # index mapping per (local_col, instance) from _x_gather_idx instead
        # of using a single offset per instance.
        block_specs = [
            ("j11", "_j11_fn_by_types", "_model_state_eq_start_idx", False, False),
            ("j12", "_j12_fn_by_types", "_model_state_eq_start_idx", False, True),
            ("j21", "_j21_fn_by_types", "_model_algebraic_eq_start_idx", True, False),
            ("j22", "_j22_fn_by_types", "_model_algebraic_eq_start_idx", True, True),
        ]

        # Map block to the wrk_vars list used during compilation
        wrt_vars_key = {
            "j11": "_state_vars_equiv_class_dict",
            "j12": "_algebraic_vars_equiv_class_dict",
            "j21": "_state_vars_equiv_class_dict",
            "j22": "_algebraic_vars_equiv_class_dict",
        }

        for block_name, fn_key, row_key, algeb_rows, algeb_cols in block_specs:
            fn_dict = getattr(self, fn_key)
            row_off_dict = getattr(self, row_key)

            entries = []
            nnz_per_type = {}

            for model_type, fn in fn_dict.items():
                if fn is None:
                    continue
                indices, indptr, n_rows_type, n_cols_type = fn.get_sparsity()
                nnz_type = len(indices)
                if nnz_type == 0:
                    continue

                model_uids = [model_type] + self.equivalence_dict.get(model_type, [])
                n_inst = len(model_uids)
                nnz_per_type[model_type] = (nnz_type, n_inst)

                local_rows = np.asarray(indices, dtype=np.intp)
                col_counts = np.diff(indptr)
                local_cols = np.repeat(np.arange(n_cols_type, dtype=np.intp), col_counts)

                # Build column index map: (lc, inst) -> global column index
                wrt_vars_list = getattr(self, wrt_vars_key[block_name]).get(model_type, [])
                uid2pos = self._uid2idx_vars_vec.get(model_type, {})
                x_gather = self._x_gather_idx.get(model_type)
                if x_gather is None:
                    continue
                col_idx = np.zeros((n_cols_type, n_inst), dtype=np.intp)
                for lc, var in enumerate(wrt_vars_list):
                    local_pos = uid2pos.get(var.uid, 0)
                    col_idx[lc, :] = x_gather[local_pos, :n_inst]
                    if algeb_cols:
                        col_idx[lc, :] -= n_states

                for j, uid in enumerate(model_uids):
                    row_off = row_off_dict.get(uid, 0)
                    for i in range(nnz_type):
                        gr = local_rows[i] + row_off
                        gc = col_idx[local_cols[i], j]
                        entries.append((gc, gr, model_type, j, i))

            # Sort by (col, row) to establish CSC data order
            entries.sort(key=lambda e: (e[0], e[1]))

            # Build CSC matrix directly from sorted entries.
            # We must NOT use sp.coo_matrix here because it merges duplicate
            # (row, col) entries, which would shrink the data array and break
            # the scatter-map indexing.  Entries are already sorted by (col, row).
            n_rows_global = n_algebraic if algeb_rows else n_states
            n_cols_global = n_algebraic if algeb_cols else n_states

            if entries:
                nnz_total = len(entries)
                j_data = np.zeros(nnz_total, dtype=np.float64)
                csc_indices = np.array([e[1] for e in entries], dtype=np.int32)
                csc_indptr = np.zeros(n_cols_global + 1, dtype=np.int32)
                for e in entries:
                    csc_indptr[e[0] + 1] += 1
                np.cumsum(csc_indptr, out=csc_indptr)
                csc = sp.csc_matrix(
                    (j_data, csc_indices, csc_indptr),
                    shape=(n_rows_global, n_cols_global)
                )
            else:
                csc = sp.csc_matrix((n_rows_global, n_cols_global), dtype=np.float64)

            # Build scatter map: for each model type, 2D array (nnz_type, n_inst)
            # of indices into the CSC data array (same order as sorted entries).
            scatter_map = {}
            for data_idx, (gc, gr, mt, j, i) in enumerate(entries):
                if mt not in scatter_map:
                    nnz_t, n_i = nnz_per_type[mt]
                    scatter_map[mt] = np.empty((nnz_t, n_i), dtype=np.intp)
                scatter_map[mt][i, j] = data_idx

            self._jac_global_data[block_name] = (csc, scatter_map)

    def _precompute_balance_jacobian_templates(self) -> None:
        n_states = self.get_states_number()
        n_algebraic = self._n_algebraic
        n_balance = len(self._balance_equations)

        if n_balance == 0:
            return

        n_device_eqs = n_algebraic - n_balance

        if self._jbalance_state_fn is not None:
            indices, indptr, n_rows_bal, n_cols_bal = self._jbalance_state_fn.get_sparsity()
            if len(indices) > 0:
                col_counts = np.diff(indptr)
                cols = np.repeat(np.arange(n_cols_bal, dtype=np.int32), col_counts)
                rows = np.asarray(indices, dtype=np.int32) + n_device_eqs
                data = np.zeros(len(rows), dtype=np.float64)
                self._jbalance_state_template = sp.csc_matrix(
                    (data, rows, np.concatenate(([0], np.cumsum(col_counts, dtype=np.int32)))),
                    shape=(n_algebraic, n_states),
                )

        if self._jbalance_fn is not None:
            indices, indptr, n_rows_bal, n_cols_bal = self._jbalance_fn.get_sparsity()
            if len(indices) > 0:
                col_counts = np.diff(indptr)
                cols = np.repeat(np.arange(n_cols_bal, dtype=np.int32), col_counts)
                rows = np.asarray(indices, dtype=np.int32) + n_device_eqs
                data = np.zeros(len(rows), dtype=np.float64)
                self._jbalance_template = sp.csc_matrix(
                    (data, rows, np.concatenate(([0], np.cumsum(col_counts, dtype=np.int32)))),
                    shape=(n_algebraic, n_algebraic),
                )

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
        """Reject null full-vectorized RMS modes without a startup owner.

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

    def _set_manufacturer_native_runtime_session(
            self,
            runtime_session: ManufacturerNativeRuntimeSessionProtocol | None,
    ) -> None:
        """Attach or detach the driver-owned manufacturer runtime session."""
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
        """Commit manufacturer model outputs after an accepted RMS step."""
        updater: BlockProceduralLogicUpdater | None = self._block_boundary_updater
        if updater is not None and self._manufacturer_native_runtime_session is not None:
            if self._constant_params is None:
                constant_params: Vec = np.zeros(0, dtype=float)
            else:
                constant_params = self._constant_params
            full_params: Vec = np.concatenate((self._variable_parameters_values.copy(), constant_params))
            updater.commit_boundary(float(t), x, full_params)
            self._variable_parameters_values[:] = full_params[:self.get_variable_parameter_number()]

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
                # by the mapped RMS reference path. The symbolic backend applies
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
        self._set_external_time_value(time_value=float(t0))

    def def_event_params_fn(self, ev_param: Vec, t: float) -> Vec:
        """
        Evaluate runtime event parameter expressions while preserving mode latches.

        :param ev_param: Current runtime parameter vector.
        :param t: Simulation time.
        :return: Updated runtime parameter vector.
        """
        runtime_continuous_eqs: List[Expr | Const] = self._runtime_continuous_eqs
        runtime_mode_slice: slice = self._runtime_mode_slice

        n_continuous = len(runtime_continuous_eqs)

        if n_continuous == 0 or self._event_params_fn is None:
            return ev_param

        mode_snapshot: Optional[Vec]= None
        if runtime_mode_slice.start != runtime_mode_slice.stop:
            mode_snapshot = ev_param[runtime_mode_slice].copy()

        updated = self._event_params_fn(ev_param, t)
        updated = self._event_params_fn(updated, t)

        if runtime_mode_slice.start == runtime_mode_slice.stop:
            return updated
        else:
            assert mode_snapshot is not None
            updated[runtime_mode_slice] = mode_snapshot

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

        if self._event_params_fn is None:
            raise ValueError("_event_params_fn is None")
        else:
            pass

        if scheduled_t is None:
            scheduled_time = float(t)
        else:
            scheduled_time = float(scheduled_t)

        self._variable_parameters_values = self.def_event_params_fn(self._variable_parameters_values, t)
        self._apply_scheduled_mode_events(scheduled_time, self._variable_parameters_values)
        self._set_external_time_value(time_value=float(t))

        # Match the scalar RMS contract. Each procedural entry owns its retained
        # state, while memoryless entries consume every supplied state snapshot.
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
            equivalence_class_uid: int | None,
            runtime_expression: Expr | Const | None = None,
    ) -> None:
        """Register one runtime parameter using the canonical RMS mapping contract.

        Device-backed initialization is resolved by symbolic UID, while the
        declaring block remains authoritative for whether the variable belongs
        to ``event_dict`` or ``mode_dict``. The full-vectorized bookkeeping is
        populated only after the same validation used by ``RmsProblemDae``.

        :param elm: Physical device owning the complete RMS model.
        :param mdl: Block which locally declares the runtime parameter.
        :param parameter: Runtime parameter being registered.
        :param declared_expression: Local fallback or initialization expression.
        :param equivalence_class_uid: Vectorized model-class UID, if available.
        :param runtime_expression: Optional retained runtime expression override.
        :return: None.
        """
        existing_event_parameter_index: int | None = self._uid2idx_event_params.get(
            parameter.uid,
            None,
        )
        if existing_event_parameter_index is None:
            pass
        elif self._variable_parameters[existing_event_parameter_index] is parameter:
            # Wrapper blocks may re-expose the exact same child-owned runtime
            # variable. Registering it twice would duplicate one physical slot.
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

        # Register the class-local slot before the global slot so both layouts
        # retain the same parameter order used by the vectorized compiler.
        if equivalence_class_uid is not None:
            class_index: int = self._class_n_event_params.get(equivalence_class_uid, 0)
            self._compiler_names_dict_vect[equivalence_class_uid][parameter.uid] = (
                f"{self.VARIABLE_PARAMS_NAME}[{class_index}]"
            )
            self._alias_names_dict_vect[equivalence_class_uid][parameter.uid] = (
                f"{self.VARIABLE_PARAMS_NAME}_{class_index}"
            )
            self._uid2idx_event_params_vec[equivalence_class_uid][parameter.uid] = class_index
            self._variable_parameters_equiv_class_dict[equivalence_class_uid].append(parameter)
            self._class_n_event_params[equivalence_class_uid] = class_index + 1
        else:
            pass

        self._compiler_names_dict[parameter.uid] = (
            f"{self.VARIABLE_PARAMS_NAME}[{self._n_event_params}]"
        )
        self._alias_names_dict[parameter.uid] = (
            f"{self.VARIABLE_PARAMS_NAME}_{self._n_event_params}"
        )
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

    def add_variables_to_compilation_dicts(
            self,
            elm: ALL_DEV_TYPES,
            mdl: Block,
    ) -> None:
        """Register one block tree in the vectorized compilation mappings.

        The physical network device remains constant while recursion visits
        the root model and every symbolic child. This preserves the association
        needed to project compiled variables back to the owning device.

        :param elm: Physical VeraGrid device owning the complete model tree.
        :param mdl: Current canonical block in the recursive traversal.
        :return: None.
        """

        self.add_block_variables_to_compilation_dicts(elm, mdl)
        for child in mdl.children:
            self.add_variables_to_compilation_dicts(elm, child)

    def _get_terminal_balance_model_type(self, mdl: Block) -> int | None:
        """Return the vectorized equivalence-class owner of one root model.

        :param mdl: Root device model whose physical contract is being registered.
        :return: Representative model UID, or None when no class owns the model.
        """
        if mdl.uid in self.equivalence_dict:
            model_type: int | None = mdl.uid
        else:
            model_type = next(
                (
                    representative_uid
                    for representative_uid, member_uids
                    in self.reference_class_for_all_blocks_dict.items()
                    if mdl.uid in member_uids
                ),
                None,
            )
        return model_type

    def _register_mapped_power_balance(
            self,
            elm: ALL_DEV_TYPES,
            mdl: Block,
            model_type: int,
    ) -> None:
        """Register mapped references and topology of one physical root model.

        :param elm: Physical device owning the mapped model.
        :param mdl: Root RMS block.
        :param model_type: Representative vectorized model UID.
        :return: None.
        """
        if mdl.uid in self._mapped_power_registered_model_uids:
            return
        else:
            self._mapped_power_registered_model_uids.add(mdl.uid)

        entries: List[RmsMappedPowerEntry]
        if elm in self.grid.get_injection_devices_iter():
            entries = resolve_rms_mapped_power_references(
                model=mdl,
                bus_index=self.bus_dict[elm.bus],
                bus_is_dc=elm.bus.is_dc,
            )
        else:
            entries = resolve_rms_mapped_power_references(
                model=mdl,
                bus_from_index=self.bus_dict[elm.bus_from],
                bus_to_index=self.bus_dict[elm.bus_to],
                bus_from_is_dc=elm.bus_from.is_dc,
                bus_to_is_dc=elm.bus_to.is_dc,
                ignore_dc_from_reactive=elm in self.grid.get_vsc(),
            )
        bus_indices = [entry.bus_index for entry in entries]
        active_expressions = [
            entry.sign * entry.active_power
            for entry in entries if entry.active_power is not None
        ]
        reactive_expressions = [
            entry.sign * entry.reactive_power
            for entry in entries if entry.reactive_power is not None
        ]

        if len(entries) > 0:
            layout: RmsVectorizedMappedPowerBalanceLayout | None = (
                self._mapped_power_layout_by_model_type.get(model_type, None)
            )
            if layout is None:
                if mdl.uid == model_type:
                    layout = RmsVectorizedMappedPowerBalanceLayout(
                        entries=entries,
                        active_expressions=active_expressions,
                        reactive_expressions=reactive_expressions,
                    )
                    self._mapped_power_layout_by_model_type[model_type] = layout
                else:
                    raise ValueError(
                        "RMS mapped balance was registered before its representative"
                    )
            else:
                pass
            layout.validate_and_add_device(
                entries=entries,
                bus_indices=bus_indices,
            )
        else:
            pass

    def _finalize_mapped_power_layouts(self) -> None:
        """Append and describe mapped balance rows after device registration.

        Repeated visits to an equivalence-class representative can rebuild its
        compiled equation list while devices are initialized. Finalization at
        this boundary guarantees that mapped-power rows cannot be erased by
        a later visit and that all instance bus lists are complete.

        :return: None.
        """
        model_type: int
        layout: RmsVectorizedMappedPowerBalanceLayout
        for model_type, layout in self._mapped_power_layout_by_model_type.items():
            layout.finalize(
                compiled_equations=self._algebraic_eqs_equiv_class_dict[model_type]
            )

    def add_block_variables_to_compilation_dicts(self, elm: ALL_DEV_TYPES, mdl: Block):
        """
        add variables and parameters info to the system block

        :param elm:
        :type elm: Union[VeraGridEngine.Devices.Substation.bus.Bus, VeraGridEngine.Devices.Injections.load.Load]
        :param mdl:
        :type mdl: VeraGridEngine.Utils.Symbolic.block.Block
        :param external_mapping:
        :return:
        :rtype: None
        """

        is_root_device_model: bool = mdl.uid == elm.rms_model.uid
        # Static device topology and the canonical P/Q reference mapping own
        # network assembly. Persisted terminal-contract metadata is accepted
        # for backward compatibility but is ignored by the runtime compiler.
        is_physical_device_root: bool = bool(
            is_root_device_model and not isinstance(elm, Bus)
        )
        terminal_model_type: int | None
        if is_physical_device_root:
            terminal_model_type = self._get_terminal_balance_model_type(mdl=mdl)
            if terminal_model_type is None:
                raise ValueError(
                    "Root RMS model has no vectorized equivalence-class owner"
                )
            else:
                pass
        else:
            terminal_model_type = None

        if mdl.uid in self.equivalence_dict.keys():
            self._compiler_names_dict_vect[mdl.uid] = dict()
            self._alias_names_dict_vect[mdl.uid] = dict()
            self._uid2idx_vars_vec[mdl.uid] = dict()
            self._uid2idx_params_vec[mdl.uid] = dict()
            self._uid2idx_event_params_vec[mdl.uid] = dict()
            self._uid2idx_diff_vec[mdl.uid] = dict()
            self._input_matrices_by_model[mdl.uid] = [np.zeros(1), np.zeros(1), np.zeros(1), np.zeros(1)]
            self._state_vars_equiv_class_dict[mdl.uid] = list()
            self._algebraic_vars_equiv_class_dict[mdl.uid] = list()
            self._diff_vars_equiv_class_dict[mdl.uid] = list()
            self._constant_parameters_equiv_class_dict[mdl.uid] = list()
            self._variable_parameters_equiv_class_dict[mdl.uid] = list()
            self._state_eqs_equiv_class_dict[mdl.uid] = list()
            self._algebraic_eqs_equiv_class_dict[mdl.uid] = list()
            self._device_algebraic_rows_by_model_type[mdl.uid] = list()
            self._balance_eqs_p_equiv_class_dict[mdl.uid] = np.zeros(6, dtype=object)
            self._balance_eqs_q_equiv_class_dict[mdl.uid] = np.zeros(6, dtype=object)

            # we add bus variables for vectorization
            class_idx = self._class_n_vars.get(mdl.uid, 0)
            if elm in self.grid.get_branches_iter():
                Vdcf, Vmf, Vaf = get_bus_rms_algebraic_vars(elm.bus_from.rms_model)
                if Vdcf is not None:
                    self._compiler_names_dict_vect[mdl.uid][Vdcf.uid] = f"{self.VARS_NAME}[{class_idx}]"
                    self._alias_names_dict_vect[mdl.uid][Vdcf.uid] = f"{self.VARS_NAME}_{class_idx}"
                    self._uid2idx_vars_vec[mdl.uid][Vdcf.uid] = class_idx
                    if dc_bus_rms_model_has_capacitive_state(elm.bus_from.rms_model):
                        self._state_vars_equiv_class_dict[mdl.uid].append(Vdcf)
                    else:
                        self._algebraic_vars_equiv_class_dict[mdl.uid].append(Vdcf)
                    self._class_n_vars[mdl.uid] = class_idx + 1
                else:
                    self._compiler_names_dict_vect[mdl.uid][Vmf.uid] = f"{self.VARS_NAME}[{class_idx}]"
                    self._alias_names_dict_vect[mdl.uid][Vmf.uid] = f"{self.VARS_NAME}_{class_idx}"
                    self._uid2idx_vars_vec[mdl.uid][Vmf.uid] = class_idx
                    self._algebraic_vars_equiv_class_dict[mdl.uid].append(Vmf)
                    self._class_n_vars[mdl.uid] = class_idx + 1
                    class_idx = self._class_n_vars.get(mdl.uid, 0)
                    self._compiler_names_dict_vect[mdl.uid][Vaf.uid] = f"{self.VARS_NAME}[{class_idx}]"
                    self._alias_names_dict_vect[mdl.uid][Vaf.uid] = f"{self.VARS_NAME}_{class_idx}"
                    self._uid2idx_vars_vec[mdl.uid][Vaf.uid] = class_idx
                    self._algebraic_vars_equiv_class_dict[mdl.uid].append(Vaf)
                    self._class_n_vars[mdl.uid] = class_idx + 1

                class_idx = self._class_n_vars.get(mdl.uid, 0)
                Vdct, Vmt, Vat = get_bus_rms_algebraic_vars(elm.bus_to.rms_model)
                if Vdct is not None:
                    self._compiler_names_dict_vect[mdl.uid][Vdct.uid] = f"{self.VARS_NAME}[{class_idx}]"
                    self._alias_names_dict_vect[mdl.uid][Vdct.uid] = f"{self.VARS_NAME}_{class_idx}"
                    self._uid2idx_vars_vec[mdl.uid][Vdct.uid] = class_idx
                    if dc_bus_rms_model_has_capacitive_state(elm.bus_to.rms_model):
                        self._state_vars_equiv_class_dict[mdl.uid].append(Vdct)
                    else:
                        self._algebraic_vars_equiv_class_dict[mdl.uid].append(Vdct)
                    self._class_n_vars[mdl.uid] = class_idx + 1
                else:
                    self._compiler_names_dict_vect[mdl.uid][Vmt.uid] = f"{self.VARS_NAME}[{class_idx}]"
                    self._alias_names_dict_vect[mdl.uid][Vmt.uid] = f"{self.VARS_NAME}_{class_idx}"
                    self._uid2idx_vars_vec[mdl.uid][Vmt.uid] = class_idx
                    self._algebraic_vars_equiv_class_dict[mdl.uid].append(Vmt)
                    self._class_n_vars[mdl.uid] = class_idx + 1
                    class_idx = self._class_n_vars.get(mdl.uid, 0)
                    self._compiler_names_dict_vect[mdl.uid][Vat.uid] = f"{self.VARS_NAME}[{class_idx}]"
                    self._alias_names_dict_vect[mdl.uid][Vat.uid] = f"{self.VARS_NAME}_{class_idx}"
                    self._uid2idx_vars_vec[mdl.uid][Vat.uid] = class_idx
                    self._algebraic_vars_equiv_class_dict[mdl.uid].append(Vat)
                    self._class_n_vars[mdl.uid] = class_idx + 1

            if elm in self.grid.get_injection_devices_iter():
                Vdc, Vm, Va = get_bus_rms_algebraic_vars(elm.bus.rms_model)
                class_idx = self._class_n_vars.get(mdl.uid, 0)
                if Vdc is not None:
                    self._compiler_names_dict_vect[mdl.uid][Vdc.uid] = f"{self.VARS_NAME}[{class_idx}]"
                    self._alias_names_dict_vect[mdl.uid][Vdc.uid] = f"{self.VARS_NAME}_{class_idx}"
                    self._uid2idx_vars_vec[mdl.uid][Vdc.uid] = class_idx
                    if dc_bus_rms_model_has_capacitive_state(elm.bus.rms_model):
                        self._state_vars_equiv_class_dict[mdl.uid].append(Vdc)
                    else:
                        self._algebraic_vars_equiv_class_dict[mdl.uid].append(Vdc)
                    self._class_n_vars[mdl.uid] = class_idx + 1
                else:
                    self._compiler_names_dict_vect[mdl.uid][Vm.uid] = f"{self.VARS_NAME}[{class_idx}]"
                    self._alias_names_dict_vect[mdl.uid][Vm.uid] = f"{self.VARS_NAME}_{class_idx}"
                    self._uid2idx_vars_vec[mdl.uid][Vm.uid] = class_idx
                    self._algebraic_vars_equiv_class_dict[mdl.uid].append(Vm)
                    self._class_n_vars[mdl.uid] = class_idx + 1
                    class_idx = self._class_n_vars.get(mdl.uid, 0)
                    self._compiler_names_dict_vect[mdl.uid][Va.uid] = f"{self.VARS_NAME}[{class_idx}]"
                    self._alias_names_dict_vect[mdl.uid][Va.uid] = f"{self.VARS_NAME}_{class_idx}"
                    self._uid2idx_vars_vec[mdl.uid][Va.uid] = class_idx
                    self._algebraic_vars_equiv_class_dict[mdl.uid].append(Va)
                    self._class_n_vars[mdl.uid] = class_idx + 1


        equiv_class_uid = next((uid for uid, list_uid in self.block_composition_dict.items() if mdl.uid in list_uid), None)

        # i is for variables
        for v in mdl.state_vars:
            if v.uid in self._uid2idx_vars:
                raise ValueError(f"State variable '{v.name}' (uid={v.uid}) is already registered in the system. "
                                 f"Previous device may have created a duplicate variable.")
            if equiv_class_uid:

                class_idx = self._class_n_vars.get(equiv_class_uid, 0)
                self._compiler_names_dict_vect[equiv_class_uid][v.uid] = f"{self.VARS_NAME}[{class_idx}]"
                self._alias_names_dict_vect[equiv_class_uid][v.uid] = f"{self.VARS_NAME}_{class_idx}"
                self._uid2idx_vars_vec[equiv_class_uid][v.uid] = class_idx
                self._state_vars_equiv_class_dict[equiv_class_uid].append(v)
                self._class_n_vars[equiv_class_uid] = class_idx + 1


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
                raise ValueError(f"Algebraic variable '{v.name}' (uid={v.uid}) is already registered in the system. "
                                 f"Previous device may have created a duplicate variable.")

            if equiv_class_uid:

                class_idx = self._class_n_vars.get(equiv_class_uid, 0)
                self._compiler_names_dict_vect[equiv_class_uid][v.uid] = f"{self.VARS_NAME}[{class_idx}]"
                self._alias_names_dict_vect[equiv_class_uid][v.uid] = f"{self.VARS_NAME}_{class_idx}"
                self._uid2idx_vars_vec[equiv_class_uid][v.uid] = class_idx
                self._algebraic_vars_equiv_class_dict[equiv_class_uid].append(v)
                self._class_n_vars[equiv_class_uid] = class_idx + 1

                if v.ref == VarPowerFlowReferenceType.P:
                    self._balance_eqs_p_equiv_class_dict[equiv_class_uid][0] = v

                if v.ref == VarPowerFlowReferenceType.Pf:
                    self._balance_eqs_p_equiv_class_dict[equiv_class_uid][2] = -v
                    self.line_model_types.append(equiv_class_uid)

                if v.ref == VarPowerFlowReferenceType.Pt:
                    self._balance_eqs_p_equiv_class_dict[equiv_class_uid][3] = -v

                if v.ref == VarPowerFlowReferenceType.Q:
                    self._balance_eqs_q_equiv_class_dict[equiv_class_uid][1] = v

                if v.ref == VarPowerFlowReferenceType.Qf:
                    self._balance_eqs_q_equiv_class_dict[equiv_class_uid][4] = -v

                if v.ref == VarPowerFlowReferenceType.Qt:
                    self._balance_eqs_q_equiv_class_dict[equiv_class_uid][5] = -v

                if v.ref == VarPowerFlowReferenceType.P:
                    if equiv_class_uid not in self.mdl_index2bus.keys():
                        self.mdl_index2bus[equiv_class_uid] = list()
                    self.mdl_index2bus[equiv_class_uid].append(self.bus_dict[elm.bus])
                if v.ref == VarPowerFlowReferenceType.Pf:
                    if equiv_class_uid not in self.mdl_index2busfrom.keys():
                        self.mdl_index2busfrom[equiv_class_uid] = list()
                    self.mdl_index2busfrom[equiv_class_uid].append(self.bus_dict[elm.bus_from])

                if v.ref == VarPowerFlowReferenceType.Pt:
                    if equiv_class_uid not in self.mdl_index2busto.keys():
                        self.mdl_index2busto[equiv_class_uid] = list()
                    self.mdl_index2busto[equiv_class_uid].append(self.bus_dict[elm.bus_to])
            else:
                uid_class = next((uid for uid, list_uid in self.reference_class_for_all_blocks_dict.items() if mdl.uid in list_uid), None)
                if uid_class is not None:
                    if v.ref == VarPowerFlowReferenceType.P:
                        if uid_class not in self.mdl_index2bus.keys():
                            self.mdl_index2bus[uid_class] = list()
                        self.mdl_index2bus[uid_class].append(self.bus_dict[elm.bus])
                    if v.ref == VarPowerFlowReferenceType.Pf:
                        if uid_class not in self.mdl_index2busfrom.keys():
                            self.mdl_index2busfrom[uid_class] = list()
                        self.mdl_index2busfrom[uid_class].append(self.bus_dict[elm.bus_from])

                    if v.ref == VarPowerFlowReferenceType.Pt:
                        if uid_class not in self.mdl_index2busto.keys():
                            self.mdl_index2busto[uid_class] = list()
                        self.mdl_index2busto[uid_class].append(self.bus_dict[elm.bus_to])




            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{self._n_vars}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{self._n_vars}"

            self._uid2idx_vars[v.uid] = self._n_vars
            self._register_global_var_name(name_key=v.name + elm.name, uid=v.uid, block=mdl)
            self.add_device_var(dev=elm, var=v)
            self.sys_vars[v.uid] = v
            self._algebraic_vars.append(v)
            self._n_vars += 1

        for ep, const in mdl.parameters.items():
            if ep.uid in self._uid2idx_params:
                raise ValueError(f"Parameter '{ep.name}' (uid={ep.uid}) is already registered in the system. "
                                 f"Previous device may have created a duplicate parameter.")
            else:
                pass

            resolved_parameter_value: Const = resolve_constant_parameter_initial_value(
                device=elm,
                simulation_mode=DynamicSimulationMode.RMS,
                root_block=elm.rms_model,
                owner_block=mdl,
                parameter=ep,
                declared_value=const,
                problem_mapping=self._static_parameters_values_mapping,
            )

            if equiv_class_uid is not None:

                class_idx = self._class_n_params.get(equiv_class_uid, 0)
                self._compiler_names_dict_vect[equiv_class_uid][ep.uid] = f"{self.CONSTANT_PARAMS_NAME}[{class_idx}]"
                self._alias_names_dict_vect[equiv_class_uid][ep.uid] = f"{self.CONSTANT_PARAMS_NAME}_{class_idx}"
                self._uid2idx_params_vec[equiv_class_uid][ep.uid] = class_idx
                self._constant_parameters_equiv_class_dict[equiv_class_uid].append(ep)
                self._class_n_params[equiv_class_uid] = class_idx + 1
            else:
                pass

            self._compiler_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}[{self._n_params}]"
            self._alias_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}_{self._n_params}"

            self._uid2idx_params[ep.uid] = self._n_params
            self._constant_parameters.append(ep)
            # Store only the concrete value already resolved with the canonical
            # UID-aware RMS helper. This prevents cloned legacy variables from
            # missing their mapping and rejects unresolved ``Const(None)``
            # placeholders before they reach the numerical compiler.
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
                equivalence_class_uid=equiv_class_uid,
            )

        for ep, eq in mdl.mode_dict.items():
            self._register_event_parameter_for_block(
                elm=elm,
                mdl=mdl,
                parameter=ep,
                declared_expression=eq,
                equivalence_class_uid=equiv_class_uid,
            )

        # l is for differential vars
        for v in mdl.diff_vars:
            if v.uid in self._uid2idx_diff:
                raise ValueError(f"Differential variable '{v.name}' (uid={v.uid}) is already registered in the system. "
                                 f"Previous device may have created a duplicate differential variable.")
            if equiv_class_uid:

                class_idx = self._class_n_diff.get(equiv_class_uid, 0)
                self._compiler_names_dict_vect[equiv_class_uid][v.uid] = f"{self.DIFF_NAME}[{class_idx}]"
                self._alias_names_dict_vect[equiv_class_uid][v.uid] = f"{self.DIFF_NAME}_{class_idx}"
                self._uid2idx_diff_vec[equiv_class_uid][v.uid] = class_idx
                self._diff_vars_equiv_class_dict[equiv_class_uid].append(v)
                self._class_n_diff[equiv_class_uid] = class_idx + 1


            self._compiler_names_dict[v.uid] = f"{self.DIFF_NAME}[{self._n_diff}]"
            self._alias_names_dict[v.uid] = f"{self.DIFF_NAME}_{self._n_diff}"
            self._uid2idx_diff[v.uid] = self._n_diff
            self._register_global_var_name(name_key=v.name + elm.name, uid=v.uid, block=mdl)
            self.add_device_var(dev=elm, var=v)
            self._diff_vars.append(v)
            self._n_diff += 1


        if equiv_class_uid:

            self._state_eqs_equiv_class_dict[equiv_class_uid].extend(mdl.state_eqs)
            algebraic_row_start: int = len(
                self._algebraic_eqs_equiv_class_dict[equiv_class_uid]
            )
            self._device_algebraic_rows_by_model_type[equiv_class_uid].extend(
                range(
                    algebraic_row_start,
                    algebraic_row_start + len(mdl.algebraic_eqs),
                )
            )
            self._algebraic_eqs_equiv_class_dict[equiv_class_uid].extend(mdl.algebraic_eqs)
            print("")

        if is_physical_device_root:
            if terminal_model_type is None:
                raise ValueError("RMS mapped-power model lacks a vectorized equivalence class")
            else:
                self._register_mapped_power_balance(
                    elm=elm,
                    mdl=mdl,
                    model_type=terminal_model_type,
                )
        else:
            pass

        self._model_state_eq_start_idx[mdl.uid] = len(self._state_eqs)
        self._state_eqs.extend(mdl.state_eqs)
        self._model_algebraic_eq_start_idx[mdl.uid] = len(self._algebraic_eqs)
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
        if reference_powerflow in mdl.external_mapping:
            var: Var = mdl.E(reference_powerflow)
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

    @property
    def event_params_values(self) -> Vec:
        """Return the mutable runtime event-parameter vector.

        :return: Runtime parameter values owned by this RMS problem.
        :raises ValueError: If runtime parameters have not been initialized.
        """
        if self._variable_parameters_values is None:
            raise ValueError("Runtime event parameters are not initialized")
        else:
            return self._variable_parameters_values

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

        # Resolved baseline constants supply startup values omitted by the
        # sparse explicit seed map, especially branch activity u=1.
        parameter_index: int
        parameter_expression: Expr | Const
        for parameter_index, parameter_expression in enumerate(self._event_parameters_eqs0):
            if isinstance(parameter_expression, Const) and parameter_expression.value is not None:
                x[parameter_index] = float(parameter_expression.value)
            else:
                pass

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

    ########### vectorized functions ##########################

    def _precompute_gather_indices(self) -> None:
        model_types = self._rhs_algeb_fn_by_types.keys()
        for model_type in model_types:
            var_equiv_lists = self.variables_equivalence_dict.get(model_type, [])
            var_equiv: Dict[int, List[int]] = {}
            for eq_list in var_equiv_lists:
                var_equiv[eq_list[0]] = eq_list

            n_inst = len(self.equivalence_dict.get(model_type, [])) + 1

            # x variables
            n_vars = len(self._uid2idx_vars_vec.get(model_type, {}))
            if n_vars:
                idx_x = np.zeros((n_vars, n_inst), dtype=np.intp)
                for var_uid, var_pos in self._uid2idx_vars_vec[model_type].items():
                    eq_list = var_equiv.get(var_uid, [var_uid])
                    for i, uid in enumerate(eq_list):
                        idx_x[var_pos, i] = self._uid2idx_vars[uid]
                self._x_gather_idx[model_type] = idx_x

            # dx variables
            n_dx = len(self._uid2idx_diff_vec.get(model_type, {}))
            if n_dx:
                idx_dx = np.zeros((n_dx, n_inst), dtype=np.intp)
                for var_uid, var_pos in self._uid2idx_diff_vec[model_type].items():
                    eq_list = var_equiv.get(var_uid, [var_uid])
                    for i, uid in enumerate(eq_list):
                        idx_dx[var_pos, i] = self._uid2idx_diff[uid]
                self._dx_gather_idx[model_type] = idx_dx

            # vp params
            n_vp = len(self._uid2idx_event_params_vec.get(model_type, {}))
            if n_vp:
                idx_vp = np.zeros((n_vp, n_inst), dtype=np.intp)
                for vp_uid, vp_pos in self._uid2idx_event_params_vec[model_type].items():
                    eq_list = var_equiv.get(vp_uid, [vp_uid])
                    for i, uid in enumerate(eq_list):
                        idx_vp[vp_pos, i] = self._uid2idx_event_params[uid]
                self._vp_gather_idx[model_type] = idx_vp

            # cp params
            n_cp = len(self._uid2idx_params_vec.get(model_type, {}))
            if n_cp:
                idx_cp = np.zeros((n_cp, n_inst), dtype=np.intp)
                for cp_uid, cp_pos in self._uid2idx_params_vec[model_type].items():
                    eq_list = var_equiv.get(cp_uid, [cp_uid])
                    for i, uid in enumerate(eq_list):
                        idx_cp[cp_pos, i] = self._uid2idx_params[uid]
                self._cp_gather_idx[model_type] = idx_cp

            n_state_eqs = len(self._state_eqs_equiv_class_dict.get(model_type, []))
            if n_state_eqs:
                idx_rhs_state = np.zeros((n_state_eqs, n_inst), dtype=np.intp)
                for inst_idx, uid in enumerate([model_type] + self.equivalence_dict.get(model_type, [])):
                    start = self._model_state_eq_start_idx[uid]
                    idx_rhs_state[:, inst_idx] = start + np.arange(n_state_eqs, dtype=np.intp)
                self._rhs_state_scatter_idx[model_type] = idx_rhs_state

            device_algebraic_rows: List[int] = (
                self._device_algebraic_rows_by_model_type.get(model_type, list())
            )
            n_device_algebraic_eqs: int = len(device_algebraic_rows)
            if n_device_algebraic_eqs > 0:
                idx_rhs_algeb = np.zeros(
                    (n_device_algebraic_eqs, n_inst),
                    dtype=np.intp,
                )
                for inst_idx, uid in enumerate([model_type] + self.equivalence_dict.get(model_type, [])):
                    start = self._model_algebraic_eq_start_idx[uid]
                    idx_rhs_algeb[:, inst_idx] = start + np.arange(
                        n_device_algebraic_eqs,
                        dtype=np.intp,
                    )
                self._rhs_algeb_scatter_idx[model_type] = idx_rhs_algeb
                self._rhs_algeb_source_rows[model_type] = np.array(
                    device_algebraic_rows,
                    dtype=np.intp,
                )
            else:
                pass

    def update_input_matrices_by_model(self, x: Vec, dx: Vec):
        _t0 = time.time()
        for model_type in self._rhs_algeb_fn_by_types.keys():
            self._input_matrices_by_model[model_type][0] = x[self._x_gather_idx[model_type]]
            dx_gather = self._dx_gather_idx.get(model_type)
            if dx_gather is not None:
                self._input_matrices_by_model[model_type][1] = dx[dx_gather]
            vp_gather = self._vp_gather_idx.get(model_type)
            if vp_gather is not None:
                self._input_matrices_by_model[model_type][2] = self._variable_parameters_values[vp_gather]
            cp_gather = self._cp_gather_idx.get(model_type)
            if cp_gather is not None:
                self._input_matrices_by_model[model_type][3] = self._constant_params[cp_gather]
        self._prof_timings['total_gather_time'] = self._prof_timings.get('total_gather_time', 0.0) + time.time() - _t0



    def rhs_state_vec(self) -> Vec:

        # here we need to iterate through equivalence_dict and build rhs for every model and then
        # fill the complete rhs
        complete_rhs_state = np.zeros(len(self._state_eqs))
        for model_type in self._rhs_state_fn_by_types.keys():
            rhs_state_fn = self._rhs_state_fn_by_types[model_type]
            if rhs_state_fn is not None:
                _t0 = time.time()
                rhs_state = rhs_state_fn(self._input_matrices_by_model[model_type][0],
                                         self._input_matrices_by_model[model_type][1],
                                         self._input_matrices_by_model[model_type][2],
                                         self._input_matrices_by_model[model_type][3])
                _t1 = time.time()
                if rhs_state.ndim == 1:
                    rhs_state = rhs_state.reshape(-1, 1)
                scatter_idx = self._rhs_state_scatter_idx.get(model_type)
                if scatter_idx is not None:
                    complete_rhs_state[scatter_idx] = rhs_state
                self._prof_timings['rhs_state_filler_total'] = self._prof_timings.get('rhs_state_filler_total', 0.0) + _t1 - _t0
                self._prof_timings['rhs_state_scatter_total'] = self._prof_timings.get('rhs_state_scatter_total', 0.0) + time.time() - _t1

        return complete_rhs_state

    def rhs_algebraic_vec(self, x: Vec, dx: Vec) -> Vec:
        self.P_vec[:] = 0.0
        self.P_used_vec[:] = False
        self.Q_vec[:] = 0.0
        self.Q_used_vec[:] = False

        # here we need to iterate through equivalence_dict and build rhs for every model and then
        # fill the complete rhs
        complete_rhs_algeb = np.zeros(len(self._algebraic_eqs))

        for model_type in self._rhs_algeb_fn_by_types.keys():
            rhs_algeb_fn = self._rhs_algeb_fn_by_types[model_type]
            _t0 = time.time()
            rhs_algeb = rhs_algeb_fn(self._input_matrices_by_model[model_type][0],
                                     self._input_matrices_by_model[model_type][1],
                                     self._input_matrices_by_model[model_type][2],
                                     self._input_matrices_by_model[model_type][3])
            # here we will have in the last two positions the values for P and Q to be summed up to P and Q
            _t1 = time.time()
            if rhs_algeb.ndim == 1:
                rhs_algeb = rhs_algeb.reshape(-1, 1)
            scatter_idx = self._rhs_algeb_scatter_idx.get(model_type)
            source_rows: np.ndarray | None = self._rhs_algeb_source_rows.get(
                model_type,
                None,
            )
            if scatter_idx is not None and source_rows is not None:
                complete_rhs_algeb[scatter_idx] = rhs_algeb[source_rows, :]
            else:
                pass
            self._prof_timings['rhs_algeb_filler_total'] = self._prof_timings.get('rhs_algeb_filler_total', 0.0) + _t1 - _t0
            self._prof_timings['rhs_algeb_scatter_total'] = self._prof_timings.get('rhs_algeb_scatter_total', 0.0) + time.time() - _t1

            # Only root device-equivalence classes contribute to the network
            # power balance. Internal sub-block classes can have algebraic RHS
            # functions too, but they do not own bus mappings and therefore
            # must be skipped here.
            mapped_layout: RmsVectorizedMappedPowerBalanceLayout | None = (
                self._mapped_power_layout_by_model_type.get(model_type, None)
            )
            if mapped_layout is not None:
                mapped_layout.accumulate(
                    rhs_algebraic=rhs_algeb,
                    active_power_balance=self.P_vec,
                    active_power_balance_used=self.P_used_vec,
                    reactive_power_balance=self.Q_vec,
                    reactive_power_balance_used=self.Q_used_vec,
                )
            else:
                pass

        rhs_energy_balance: np.ndarray = self._nodal_balance_layout.evaluate(
            variables=x,
            variable_index_by_uid=self._uid2idx_vars,
            active_power_balance=self.P_vec,
            reactive_power_balance=self.Q_vec,
        )
        if len(rhs_energy_balance) == len(self._balance_equations):
            pass
        else:
            raise ValueError("RMS nodal RHS layout differs from its compiled equations")
        complete_rhs_algeb[-len(rhs_energy_balance):] = rhs_energy_balance
        # energy balance equations
        # if self._rhs_algeb_energy_balance_fn is None:
        #     raise ValueError("_rhs_algeb_balance_fn is None")
        # rhs_energy_balance = self._rhs_algeb_energy_balance_fn(x, dx, self._variable_parameters_values, self._constant_params)
        # complete_rhs_algeb[-len(rhs_energy_balance):] = rhs_energy_balance

        return complete_rhs_algeb

    def _fill_jacobian_block(self, block_name: str, fn_key: str, h: float) -> sp.csc_matrix:
        csc_template, scatter_map = self._jac_global_data[block_name]
        if csc_template.nnz == 0:
            return csc_template

        csc_template.data[:] = 0.0

        _t0 = time.time()
        fn_dict = getattr(self, fn_key)
        for model_type, fn in fn_dict.items():
            if fn is None:
                continue
            data_out = fn(
                self._input_matrices_by_model[model_type][0],
                self._input_matrices_by_model[model_type][1],
                self._input_matrices_by_model[model_type][2],
                self._input_matrices_by_model[model_type][3],
                h,
            )
            if data_out.ndim == 1:
                data_out = data_out.reshape(-1, 1)
            smap = scatter_map.get(model_type)
            if smap is not None:
                csc_template.data[smap] = data_out
        _t1 = time.time()
        self._prof_timings['jac_filler_' + block_name] = self._prof_timings.get('jac_filler_' + block_name, 0.0) + _t1 - _t0

        return csc_template

    def get_j11_vec(self, h: float) -> sp.csc_matrix:
        if not self._jac_global_data.get("j11"):
            raise ValueError("J11 templates not built")
        return self._fill_jacobian_block("j11", "_j11_fn_by_types", h)

    def get_j12_vec(self, h: float) -> sp.csc_matrix:
        if not self._jac_global_data.get("j12"):
            raise ValueError("J12 templates not built")
        return self._fill_jacobian_block("j12", "_j12_fn_by_types", h)

    def get_j21_vec(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        if not self._jac_global_data.get("j21"):
            raise ValueError("J21 templates not built")
        j21 = self._fill_jacobian_block("j21", "_j21_fn_by_types", h)
        if self._jbalance_state_fn is not None and self._jbalance_state_template is not None:
            j_bal = self._jbalance_state_fn(x, dx, self._variable_parameters_values, self._constant_params, h)
            if j_bal.nnz > 0:
                j_bal_padded = self._jbalance_state_template.copy()
                j_bal_padded.data[:] = j_bal.data
                j21 = (j21 + j_bal_padded).tocsc()
        return j21

    @staticmethod
    def _add_balance_equations_to_j22(j_bal: sp.csc_matrix, n_algebraic: int,
                                      j22: sp.csc_matrix | None = None) -> sp.csc_matrix:
        n_bal = j_bal.shape[0]
        n_device = n_algebraic - n_bal
        top = sp.csc_matrix((n_device, n_algebraic), dtype=np.float64)
        bal_block = sp.vstack([top, j_bal]).tocsc()
        if j22 is not None:
            return (j22 + bal_block).tocsc()
        return bal_block

    def get_j22_vec(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        if self._jac_global_data.get("j22"):
            j22 = self._fill_jacobian_block("j22", "_j22_fn_by_types", h)
        else:
            j22 = sp.csc_matrix((self._n_algebraic, self._n_algebraic), dtype=np.float64)

        if self._jbalance_fn is not None and self._jbalance_template is not None:
            j_bal = self._jbalance_fn(x, dx, self._variable_parameters_values, self._constant_params, h)
            if j_bal.nnz > 0:
                j_bal_padded = self._jbalance_template.copy()
                j_bal_padded.data[:] = j_bal.data
                j22 = (j22 + j_bal_padded).tocsc()

        return j22

    def rhs_algebraic(self, x: Vec, dx: Vec) -> Vec:
        """Evaluate the algebraic residual through the full-vectorized owner.

        The shared initial projector supplies a new candidate on every Newton
        and line-search evaluation, so the per-model inputs must be gathered
        from that exact candidate before evaluating the established residual.

        :param x: Current state and algebraic variable values.
        :param dx: Current differential-variable values.
        :return: Algebraic residual for the supplied candidate.
        """
        # Refresh every per-model input from the current projection candidate.
        self.update_input_matrices_by_model(x=x, dx=dx)
        # Reuse the supported full-vectorized assembly without duplicating equations.
        return self.rhs_algebraic_vec(x=x, dx=dx)

    def get_j22(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """Evaluate the algebraic Jacobian through the full-vectorized owner.

        :param x: Current state and algebraic variable values.
        :param dx: Current differential-variable values.
        :param h: Numerical step supplied by the shared projection interface.
        :return: Algebraic Jacobian in compressed sparse column format.
        """
        # Gather the same candidate used by the residual before assembling J22.
        self.update_input_matrices_by_model(x=x, dx=dx)
        # Preserve the existing full-vectorized and network-balance assembly.
        return self.get_j22_vec(x=x, dx=dx, h=h)

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
        n_diff = self.get_diff_var_number()
        vp = self._variable_parameters_values
        cp = self._constant_params

        n_vars = self._n_vars
        E_value = np.zeros((n_vars, n_vars))
        E_partial = E_call(x, dx, vp, cp, h=0).toarray()

        E_value[:, :n_diff] = E_partial
        E_value[:n_states, :n_states] -= np.eye(n_states, dtype=E_value.dtype)

        return E_value
