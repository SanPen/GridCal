# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Module providing the EmtProblemDae class, which acts as the electrical
parser for the generic BaseProblem layer. It translates electrical components
(buses, branches, injections) into the unified DAE mathematical structure.
"""

from __future__ import annotations

import time
from copy import copy
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import numpy.linalg as la
from typing import Dict, List, Any, Set, Optional, Tuple

from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.types import ALL_DEV_TYPES, INJECTION_DEVICE_TYPES
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, piecewise, Const, hard_sat, heaviside
from VeraGridEngine.Utils.Symbolic.block import Block, has_emt_internal_grounding_link, validate_dynamic_model_contract
from VeraGridEngine.enumerations import (
    VarPowerFlowReferenceType,
    ParamPowerFlowReferenceType,
    DeviceType,
    DynamicEventTransitionType,
    DynamicSimulationMode,
    EmtInitializationMethod,
    EmtInitializationStatus,
    EmtLineTypes,
    GeneratorControlMode,
    ShuntConnectionType,
    TheveninSourceVoltageMode,
)
from VeraGridEngine.basic_structures import Logger, CxVec
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import BergeronHistoryRuntime
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import JMartiHistoryRuntime
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import split_reactive_power_between_generators_and_batteries
from VeraGridEngine.Simulations.EMT.injection_operating_point import (
    EmtInjectionOperatingPoint,
    get_balanced_device_power_pu,
)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (
    split_slack_bus_quantity_between_generators_and_batteries,
)
from VeraGridEngine.Simulations.EMT.initialization_emt import EmtInitializationReport, run_emt_native_initialization, run_emt_device_pseudo_transient_initialization, validate_emt_periodic_initialization, _compute_missing_dx0, _build_hierarchical_event_equation_list, _build_event_equation_lookup_from_problem_order
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import (
    ExplicitInitializationResult,
    build_symbolic_vector_single_equation_compiler,
    init_explicit_common,
)
from VeraGridEngine.Utils.Symbolic.compiled_functions import get_compiled_functions_cache_stats
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_algebraic_vars
from VeraGridEngine.Utils.Symbolic.bus_emt_template import BusEmtTemplate, get_bus_mask
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block, ProceduralExpressionMode
from VeraGridEngine.Utils.procedural_logic_contract import ManufacturerNativeRuntimeSessionProtocol
from VeraGridEngine.IO.fmu import (
    finalize_emt_fmu_cs_devices,
    finalize_emt_fmu_me_devices,
    queue_emt_fmu_cs_device,
    queue_emt_fmu_me_device,
)

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import (
    EmtBoundaryUpdateProtocol,
    EmtProblemTemplate,
    _collect_hierarchical_init_equations,
)
from VeraGridEngine.Simulations.EMT.problems.emt_terminal_current_assembly import (
    assemble_emt_mapped_current_references,
)
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import (
    StaticParameterMappingDiagnostics,
    abc_to_nabc,
    assign_static_api_object_mapping_for_device,
    converter_control_code,
    get_api_parameter_initial_value_by_uid,
    get_line_g_keys,
    get_current_injection_phase_values_pu_abc,
    get_load_power_phase_values_pu_abc,
    get_load_impedance_phase_values_pu_abc,
    get_load_current_phase_values_pu_abc,
    get_shunt_phase_values_pu_abc,
    resolve_constant_parameter_initial_value,
    resolve_runtime_parameter_initial_expression,
)


def _balanced_pf_line_matrix_mismatch(line: Any) -> float:
    """Return the positive-sequence mismatch between PF and EMT line data."""
    if line.ys is None or line.ysh is None:
        return 0.0
    if not (line.ys.phA and line.ys.phB and line.ys.phC) or line.ys.phN:
        return 0.0
    positive_sequence_impedance: complex = complex(float(line.R), float(line.X))
    if abs(positive_sequence_impedance) <= 1.0e-15:
        return 0.0

    # Transform between ABC phases and zero, positive, negative sequences.
    phase_rotation: complex = np.exp(2j * np.pi / 3.0)
    sequence_to_phase: np.ndarray = np.array(
        [[1.0, 1.0, 1.0],
         [1.0, phase_rotation ** 2, phase_rotation],
         [1.0, phase_rotation, phase_rotation ** 2]],
        dtype=np.complex128,
    )
    phase_to_sequence: np.ndarray = np.linalg.inv(sequence_to_phase)
    balanced_phase_voltages: np.ndarray = sequence_to_phase[:, 1]

    # Apply balanced voltage to each phase matrix and inspect the current sequences.
    series_admittance_abc: np.ndarray = np.asarray(line.ys.values[1:4, 1:4])
    shunt_admittance_abc: np.ndarray = np.asarray(line.ysh.values[1:4, 1:4])
    series_current_sequences: np.ndarray = phase_to_sequence @ series_admittance_abc @ balanced_phase_voltages
    shunt_current_sequences: np.ndarray = phase_to_sequence @ shunt_admittance_abc @ balanced_phase_voltages

    expected_series_admittance: complex = 1.0 / positive_sequence_impedance
    # Compare in the stored shunt units; PF3 reverses this factor of 1e6.
    expected_shunt_admittance: complex = 1.0e6 * complex(line.G, line.B)

    # Check both the positive-sequence value and coupling into the other sequences.
    series_positive_error: float = abs(series_current_sequences[1] - expected_series_admittance)
    series_coupling_error: float = max(abs(series_current_sequences[0]), abs(series_current_sequences[2]))
    shunt_positive_error: float = abs(shunt_current_sequences[1] - expected_shunt_admittance)
    shunt_coupling_error: float = max(abs(shunt_current_sequences[0]), abs(shunt_current_sequences[2]))

    series_scale: float = max(1.0, abs(expected_series_admittance))
    shunt_scale: float = max(1.0, abs(expected_shunt_admittance))
    series_error: float = max(series_positive_error, series_coupling_error) / series_scale
    shunt_error: float = max(shunt_positive_error, shunt_coupling_error) / shunt_scale
    return float(max(series_error, shunt_error))


def _tic() -> float:
    """
    Returns the current performance counter time.
    """
    return time.perf_counter()


def _toc(t0: float) -> float:
    """
    Returns the elapsed time since t0.
    """
    return time.perf_counter() - t0


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

    The expression keeps ``before_expr`` before ``start_time``, then transitions
    linearly toward ``final_value`` until ``end_time``, and finally holds the
    final value afterwards.

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


def _xfmr_phase_permutation_matrix(clock: int) -> np.ndarray:
    """
    Return the phase permutation matrix implied by the transformer vector group.

    :param clock: Transformer vector group clock number.
    :return: 3x3 phase permutation matrix.
    """
    shift: int = (int(clock) // 4) % 3
    if shift == 0:
        return np.eye(3, dtype=float)
    else:
        if shift == 1:
            return np.array([
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0],
            ], dtype=float)
        else:
            return np.array([
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ], dtype=float)

class EmtTopologyError(Exception):
    """
    Exception raised when EMT topology validation fails.
    This includes orphaned in_vars/out_vars and floating bus phases.
    """

    def __init__(self, message: str) -> None:
        """
        :param message: Descriptive error message indicating the topology issue.
        """
        self.message = message
        super().__init__(self.message)


class EmtInterfaceValidationError(ValueError):
    """
    Exception raised when one EMT interface is incompatible with the bus shell.

    The dynamic editor may expose a maximum editable interface that is broader
    than the currently configured static network. This exception reports those
    mismatches explicitly before EMT assembly can silently skip substitutions.
    """

    def __init__(self, message: str):
        """
        Build one explicit EMT interface-validation error.

        :param message: Descriptive interface mismatch report.
        :return: None.
        """
        self.message = message
        super().__init__(self.message)


class EmtDeviceDisposition:
    """
    Enumeration-like holder describing how one ``DeviceType`` participates in EMT.

    The EMT builder must make an explicit decision for every network device type
    that can exist in a ``MultiCircuit``. Some device types participate directly
    in the EMT electrical structure, while others are metadata-only from the EMT
    point of view and must therefore resolve to an explicit no-op disposition.
    """

    __slots__ = ()

    BUS_STRUCTURAL: str = "bus_structural"
    BRANCH_STRUCTURAL: str = "branch_structural"
    INJECTION_STRUCTURAL: str = "injection_structural"
    NON_EMT_NOOP: str = "non_emt_noop"


def _build_emt_device_type_disposition_table() -> Dict[DeviceType, str]:
    """
    Build the exhaustive ``DeviceType`` to EMT-disposition table.

    The purpose of this table is architectural completeness. Every device type in
    the public enumeration must map to one explicit EMT disposition so newly added
    device types cannot silently inherit unrelated branch or injection behavior.

    :return: Mapping from ``DeviceType`` to one EMT disposition string.
    """
    disposition_table: Dict[DeviceType, str] = dict()
    device_tpe: DeviceType

    for device_tpe in DeviceType:
        disposition_table[device_tpe] = EmtDeviceDisposition.NON_EMT_NOOP

    disposition_table[DeviceType.BusDevice] = EmtDeviceDisposition.BUS_STRUCTURAL

    disposition_table[DeviceType.BranchDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.LineDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.Transformer2WDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.Transformer3WDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.TransformerNwDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.WindingDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.SeriesReactanceDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.HVDCLineDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.DCLineDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.VscDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.UpfcDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL
    disposition_table[DeviceType.SwitchDevice] = EmtDeviceDisposition.BRANCH_STRUCTURAL

    disposition_table[DeviceType.BatteryDevice] = EmtDeviceDisposition.INJECTION_STRUCTURAL
    disposition_table[DeviceType.LoadDevice] = EmtDeviceDisposition.INJECTION_STRUCTURAL
    disposition_table[DeviceType.CurrentInjectionDevice] = EmtDeviceDisposition.INJECTION_STRUCTURAL
    disposition_table[DeviceType.ControllableShuntDevice] = EmtDeviceDisposition.INJECTION_STRUCTURAL
    disposition_table[DeviceType.GeneratorDevice] = EmtDeviceDisposition.INJECTION_STRUCTURAL
    disposition_table[DeviceType.StaticGeneratorDevice] = EmtDeviceDisposition.INJECTION_STRUCTURAL
    disposition_table[DeviceType.ShuntDevice] = EmtDeviceDisposition.INJECTION_STRUCTURAL
    disposition_table[DeviceType.ExternalGridDevice] = EmtDeviceDisposition.INJECTION_STRUCTURAL

    return disposition_table


def _validate_emt_device_type_disposition_table(disposition_table: Dict[DeviceType, str]) -> None:
    """
    Validate that the EMT disposition table covers the full ``DeviceType`` enum.

    This check protects the EMT architecture against future enum growth. When one
    new ``DeviceType`` is introduced, the EMT builder must still make an explicit
    disposition decision instead of falling back to generic branch or injection
    assumptions.

    :param disposition_table: Mapping from ``DeviceType`` to EMT disposition.
    :return: None.
    """
    missing_types: List[DeviceType] = list()
    device_tpe: DeviceType

    for device_tpe in DeviceType:
        if device_tpe in disposition_table:
            pass
        else:
            missing_types.append(device_tpe)

    if len(missing_types) == 0:
        pass
    else:
        missing_names: List[str] = list()
        missing_tpe: DeviceType
        for missing_tpe in missing_types:
            missing_names.append(str(missing_tpe.name))

        raise ValueError(
            "EMT device disposition table is incomplete. Missing DeviceType entries: "
            + ", ".join(missing_names)
        )


def _unique_keep_order(seq: List[Var]) -> List[Var]:
    """
    Remove duplicated variables by UID while preserving the first appearance order.

    :param seq: Input variable sequence.
    :return: Deduplicated variable sequence.
    """
    seen: Set[int] = set()
    out: List[Var] = list()

    for item in seq:
        if item.uid in seen:
            pass
        else:
            seen.add(item.uid)
            out.append(item)

    return out

def _deduplicate_block_entities(block: Block)->None:
    """
    Removes duplicated symbolic objects within the block by UID
    while preserving their first appearance order.
    """


    block.state_vars = _unique_keep_order(block.state_vars)
    block.algebraic_vars = _unique_keep_order(block.algebraic_vars)
    block.diff_vars = _unique_keep_order(block.diff_vars)


def _get_mode_event_sort_key(event: Tuple[float, float, bool]) -> float:
    """
    Return the sorting key of a mode event.

    :param event: Mode event tuple (time, value, force_step_alignment).
    :return: Event time.
    """
    return event[0]

def _is_time_aligned(t_curr: float, event_time: float) -> bool:
    """
    Return whether the current solver time is aligned with the event time.

    :param t_curr: Current solver time.
    :param event_time: Scheduled event time.
    :return: True if the current time is aligned with the event time.
    """
    machine_eps: float = float(np.finfo(np.float64).eps)
    time_tol: float = 10.0 * machine_eps * max(1.0, abs(event_time))
    return bool(abs(t_curr - event_time) <= time_tol)

def _get_next_forced_mode_event_time(
        scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]],
        t_prev: float,
        t_target: float,
) -> Optional[float]:
    """
    Return the earliest forced-alignment mode event time in the interval
    (t_prev, t_target].

    :param t_prev: Previous solver time.
    :param t_target: Nominal target time.
    :return: Earliest forced event time or None.
    """
    next_time: Optional[float] = None

    for _, event_list in scheduled_mode_events.items():
        event_idx: int = 0

        while event_idx < len(event_list):
            event_time: float = event_list[event_idx][0]
            force_step_alignment: bool = event_list[event_idx][2]

            if force_step_alignment and (t_prev < event_time <= t_target):
                if next_time is None:
                    next_time = event_time
                else:
                    if event_time < next_time:
                        next_time = event_time
                    else:
                        pass
            else:
                pass

            event_idx += 1

    return next_time


def _continuous_event_spec_time_sort_key(event_spec: Dict[str, float | str | None]) -> float:
    """
    Return the sorting key used for one continuous-event specification.

    :param event_spec: Continuous event specification dictionary.
    :return: Event start time.
    """
    return float(event_spec["time"])

def _get_block_name(mdl: Block) -> str:
    """
    Return the block name used for logging.

    :param mdl: Block to inspect.
    :return: Block name.
    """
    if mdl.name is None:
        return "unknown"
    else:
        return str(mdl.name)


def _is_history_runtime_line_block_name(block_name: Any) -> Tuple[bool, bool]:
    """
    Return whether one EMT line block uses a retained-history runtime companion.

    :param block_name: EMT block name.
    :return: Tuple ``(is_bergeron, is_jmarti)``.
    """
    is_bergeron: bool = block_name == EmtLineTypes.Bergeron or block_name == EmtLineTypes.Bergeron.value
    is_jmarti: bool = block_name == EmtLineTypes.J_Marti or block_name == EmtLineTypes.J_Marti.value
    return is_bergeron, is_jmarti


def _get_grid_runtime_events(grid: MultiCircuit) -> List[Any]:
    """
    Return the list of scheduled runtime events available in the grid.

    :param grid: MultiCircuit instance.
    :return: List of scheduled runtime events.
    """

    return grid.emt_events

def _get_bus_v_list(
        bus_block: Block,
        ph_v_keys: List[VarPowerFlowReferenceType]
) -> List[Any]:
    """
    Return the ordered list of bus phase voltages, using None for missing phases.

    :param bus_block: Bus symbolic block.
    :param ph_v_keys: Ordered list of phase voltage keys.
    :return: Ordered list of bus phase voltage expressions or None.
    """
    out: List[Any] = list()

    for key in ph_v_keys:
        vk: Optional[Any] = _get_external_mapping_var_if_present(mdl=bus_block, key=key)

        if vk is None:
            out.append(None)
        else:
            out.append(vk)

    return out

def _get_external_mapping(mdl: Block) -> Optional[Dict[Any, Var]]:
    """
    Return the flattened external mapping exposed by one block hierarchy.

    Wrapper EMT models may keep the actual PF-to-EMT variable bindings inside
    nested child blocks. The build stage therefore needs to inspect the whole
    hierarchy and merge the first occurrence of each key so later lookup sites
    can recover child initialization references from the wrapper root.

    :param mdl: Root block to inspect.
    :return: Flattened external mapping, or ``None`` when no mapping exists.
    """
    external_mapping: Dict[Any, Var] = _collect_external_mapping_from_block(mdl)

    # An empty merged mapping means the hierarchy does not expose PF bindings.
    if len(external_mapping) == 0:
        return None
    else:
        return external_mapping


def _get_external_mapping_local(problem: Any, mdl: Block) -> Optional[Dict[Any, Var]]:
    """
    Return the problem-local flattened external mapping for one block when available.

    The EMT refactor stores resolved mappings on the problem object instead of
    rewriting the persistent model kept in ``MultiCircuit``. Callers should use
    this helper when they need the effective external mapping during build or
    initialization.

    :param problem: EMT problem instance.
    :param mdl: Root block to inspect.
    :return: Effective external mapping or ``None``.
    """
    local_registry: Any = problem._local_external_mapping_by_block_uid
    local_mapping: Optional[Dict[Any, Var]]

    if isinstance(local_registry, dict):
        local_mapping = local_registry.get(mdl.uid, None)
        if local_mapping is None:
            return _get_external_mapping(mdl)
        else:
            return local_mapping
    else:
        return _get_external_mapping(mdl)


def _has_vsc_positive_sequence_pf_contract(mdl: Block) -> bool:
    """
    Return whether one VSC block exposes the PF positive-sequence EMT contract.

    The extra PF-derived internal power seeding is only valid for converter
    templates that are explicitly initialized from the positive-sequence EMT
    references ``Vpk`` and ``phi_v``. Applying that logic to more generic VSC
    templates changes their intended initialization behavior.

    :param mdl: Root symbolic block.
    :return: ``True`` when the PF positive-sequence contract is exposed.
    """
    external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(mdl)

    if external_mapping is None:
        return False
    else:
        pass

    if VarPowerFlowReferenceType.Vpk in external_mapping and VarPowerFlowReferenceType.phi_v in external_mapping:
        return True
    else:
        return False


def _collect_block_hierarchy(mdl: Block) -> List[Block]:
    """
    Collect every block reachable from one root block.

    The EMT editor may persist one wrapper root around the actual device block.
    Rebuilding wrapper-owned metadata therefore starts by traversing the full
    hierarchy exactly once while avoiding revisiting the same block object.

    :param mdl: Root block to inspect.
    :return: Ordered list with the reachable block objects.
    """
    blocks: List[Block] = list()
    stack: List[Block] = list([mdl])
    visited: Set[int] = set()

    # The explicit stack keeps the traversal iterative and avoids recursion
    # depth concerns when the GUI creates nested wrapper structures.
    while len(stack) > 0:
        block: Block = stack.pop()
        block_id: int = id(block)

        # Every block is processed only once so merged metadata stays stable.
        if block_id not in visited:
            visited.add(block_id)
            blocks.append(block)

            # Child blocks are pushed so the caller can inspect nested metadata
            # such as PF references and explicit-init registrations.
            child: Block
            for child in block.children:
                stack.append(child)
        else:
            pass

    return blocks


def _collect_external_mapping_from_block(mdl: Block) -> Dict[Any, Var]:
    """
    Collect the external mapping from one block hierarchy.

    Wrapper models may keep the exposed PF reference variables in nested child
    blocks. This helper merges the hierarchy into one root-level mapping while
    preserving the first occurrence of each key, which matches the existing
    API-object mapping recovery strategy used by the EMT builder.

    :param mdl: Root block to inspect.
    :return: Flattened external mapping.
    """
    mapping: Dict[Any, Var] = dict()
    blocks: List[Block] = _collect_block_hierarchy(mdl)
    block: Block

    # The root block keeps precedence, while child-only keys are recovered so
    # PF-derived initialization metadata survives wrapper reconstruction.
    for block in blocks:
        local_mapping: Optional[Dict[Any, Var]] = block.external_mapping

        if local_mapping is None:
            pass
        else:
            key: Any
            value: Var
            for key, value in local_mapping.items():
                if key not in mapping:
                    mapping[key] = value
                else:
                    pass

    mapping = _sanitize_external_mapping_for_explicit_dc_terminals(mapping)

    return mapping


def _sanitize_external_mapping_for_explicit_dc_terminals(mapping: Dict[Any, Var]) -> Dict[Any, Var]:
    """
    Remove ambiguous shared DC aliases when explicit terminal mappings exist.

    GUI-loaded EMT wrappers can preserve both the legacy shared DC aliases
    (``Vdc`` / ``Idc``) and the explicit terminal contract
    (``Vf_dc`` / ``Vt_dc`` and ``If_dc`` / ``It_dc``). The structural EMT
    assembly for two-sided DC devices is defined by the explicit side-specific
    variables. Keeping the shared aliases at the merged root can reintroduce
    one-sided shortcuts that collapse the assembled sparse system and make the
    Jacobian exactly singular.

    :param mapping: Flattened external mapping collected from one block hierarchy.
    :return: Sanitized mapping that preserves only the explicit two-sided DC contract.
    """
    sanitized_mapping: Dict[Any, Var] = dict()
    # Root-contract normalization keeps unsupported optional references as
    # explicit ``None`` entries. Those placeholders do not expose a usable
    # two-terminal DC contract and therefore must not suppress a valid shared
    # ``Vdc``/``Idc`` mapping used by single-bus DC injections.
    has_vf: bool = mapping.get(VarPowerFlowReferenceType.Vf_dc, None) is not None
    has_vt: bool = mapping.get(VarPowerFlowReferenceType.Vt_dc, None) is not None
    has_if: bool = mapping.get(VarPowerFlowReferenceType.If_dc, None) is not None
    has_it: bool = mapping.get(VarPowerFlowReferenceType.It_dc, None) is not None
    key: Any
    value: Var

    for key, value in mapping.items():
        if key == VarPowerFlowReferenceType.Vdc:
            if has_vf and has_vt:
                pass
            else:
                sanitized_mapping[key] = value
        elif key == VarPowerFlowReferenceType.Idc:
            if has_if and has_it:
                pass
            else:
                sanitized_mapping[key] = value
        else:
            sanitized_mapping[key] = value

    return sanitized_mapping


def _get_connected_bus_balanced_power(pf_results: PowerFlowResults, bus_index: int, sbase: float) -> complex:
    """
    Return one balanced complex bus power in per unit.

    EMT PF seeding sometimes needs one stable fallback when branch- or
    converter-specific PF result arrays are empty even though the bus snapshot is
    valid. The bus injection is the most broadly populated source available in
    the balanced PF result container.

    :param pf_results: Balanced power-flow results.
    :param bus_index: Bus index.
    :param sbase: System base power.
    :return: Complex bus power in per unit.
    """
    try:
        return complex(pf_results.Sbus[bus_index] / sbase)
    except (AttributeError, IndexError, TypeError, ValueError):
        return 0.0 + 0.0j


def _get_bus_balanced_injection_power(pf_results: PowerFlowResults, bus_index: int, sbase: float) -> complex:
    """
    Return one balanced specified bus injection power in per unit.

    The PF ``Sbus`` array can be overwritten by the solved network injection at
    the end of the power flow. For DC branch seeding we often need the original
    scheduled bus injection sign because it reflects whether one terminal is a
    net source or sink even when branch result arrays are sparse.

    :param pf_results: Balanced power-flow results.
    :param bus_index: Bus index.
    :param sbase: System base power.
    :return: Complex specified bus injection in per unit.
    """
    try:
        return complex(pf_results.Sbus[bus_index] / sbase)
    except (AttributeError, IndexError, TypeError, ValueError):
        return 0.0 + 0.0j





def _resolve_converter_control_reference_values(control1_code: float,
                                                control2_code: float,
                                                control1_val: float,
                                                control2_val: float,
                                                p0_value: float) -> Tuple[float, float, float]:
    """
    Resolve converter control references numerically from configured control modes.

    :param control1_code: Numeric code of control 1.
    :param control2_code: Numeric code of control 2.
    :param control1_val: Numeric value of control 1.
    :param control2_val: Numeric value of control 2.
    :param p0_value: Scheduled active-power operating point.
    :return: Tuple ``(P_ref, Q_ref, Vdc_ref)``.
    """
    vm_dc_code: float = 1.0
    qac_code: float = 4.0
    pdc_code: float = 5.0
    pac_code: float = 6.0
    p_ref_value: float
    q_ref_value: float
    vdc_ref_value: float

    if abs(control1_code - vm_dc_code) < 0.5:
        vdc_ref_value = control1_val
    else:
        if abs(control2_code - vm_dc_code) < 0.5:
            vdc_ref_value = control2_val
        else:
            vdc_ref_value = 1.0

    if abs(control1_code - qac_code) < 0.5:
        q_ref_value = control1_val
    else:
        if abs(control2_code - qac_code) < 0.5:
            q_ref_value = control2_val
        else:
            q_ref_value = 0.0

    if abs(control1_code - pdc_code) < 0.5 or abs(control1_code - pac_code) < 0.5:
        p_ref_value = control1_val
    else:
        if abs(control2_code - pdc_code) < 0.5 or abs(control2_code - pac_code) < 0.5:
            p_ref_value = control2_val
        else:
            p_ref_value = p0_value

    return float(p_ref_value), float(q_ref_value), float(vdc_ref_value)


def _get_external_mapping_var_if_present(
        mdl: Block,
        key: VarPowerFlowReferenceType,
) -> Optional[Any]:
    """
    Return one mapped external variable if the model exposes the key.

    This helper intentionally does not call ``mdl.E(key)`` because ``Block.E``
    indexes ``external_mapping`` directly and raises ``KeyError`` when the key
    is absent. User models are allowed to expose only a subset of optional
    PowerFlow initialization keys.

    :param mdl: Symbolic device block.
    :param key: External mapping reference key.
    :return: Mapped variable or expression, or ``None``.
    """
    external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(mdl)

    if external_mapping is None:
        return None
    else:
        mapped_var: Optional[Any] = external_mapping.get(key, None)
        return mapped_var


def _mapped_var_already_matches_target(mapped_var: Optional[Var], target_var: Any) -> bool:
    """
    Return whether one external-mapping variable already matches its target shell variable.

    The EMT attachment layer canonicalizes many root external mappings before the
    problem builder starts. When the mapped variable already shares the target UID,
    the builder can skip one substitution entry and keep the compatibility fallback
    only for legacy or wrapper-root cases that still expose one stale mapping var.

    :param mapped_var: Variable exposed through one root external mapping entry.
    :param target_var: Authoritative bus-shell variable or ``None``.
    :return: ``True`` when no substitution is required.
    """
    if mapped_var is None:
        return False
    else:
        pass

    if isinstance(target_var, Var):
        return mapped_var.uid == target_var.uid
    else:
        return False


def _get_array_entry_if_in_range(array_obj: Any, index: int) -> Optional[Any]:
    """
    Return one array entry only when the index is valid.

    Power-flow result containers may exist while some per-phase arrays are empty,
    for example after one failed or unsupported PF attempt in the GUI. EMT should
    then skip the corresponding seed instead of raising ``IndexError`` during the
    initialization pass.

    :param array_obj: Candidate array-like object.
    :param index: Requested zero-based index.
    :return: Selected entry or ``None``.
    """
    if array_obj is None:
        return None
    else:
        pass
    try:
        array_length: int = len(array_obj)
    except TypeError:
        return None

    if 0 <= int(index) < array_length:
        return array_obj[index]
    else:
        return None


def _collect_nonfinite_problem_entries(problem: "EmtProblemDae") -> List[str]:
    """
    Collect a readable report of non-finite EMT initialization entries.

    :param problem: EMT problem instance.
    :return: Human-readable non-finite entry descriptions.
    """
    entries: List[str] = list()
    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = problem.get_dx0()
    state_and_algebraic_vars: List[Var] = problem.get_state_vars() + problem.get_algebraic_vars()
    diff_vars: List[Var] = problem.get_diff_vars()
    idx: int = 0

    while idx < len(x0):
        if np.isfinite(x0[idx]):
            pass
        else:
            if idx < len(state_and_algebraic_vars):
                entries.append(f"x0:{state_and_algebraic_vars[idx].name}={x0[idx]}")
            else:
                entries.append(f"x0:index_{idx}={x0[idx]}")
        idx += 1

    idx = 0
    while idx < len(dx0):
        if np.isfinite(dx0[idx]):
            pass
        else:
            if idx < len(diff_vars):
                entries.append(f"dx0:{diff_vars[idx].name}={dx0[idx]}")
            else:
                entries.append(f"dx0:index_{idx}={dx0[idx]}")
        idx += 1

    return entries


def _drop_nonfinite_initialization_entries(problem: "EmtProblemDae") -> None:
    """
    Remove non-finite initialization guesses so vector builders fall back to zero.

    :param problem: EMT problem instance.
    :return: None.
    """
    bad_init_uids: List[int] = list()
    bad_diff_uids: List[int] = list()
    uid: int
    value: float

    for uid, value in problem.init_guess.items():
        if np.isfinite(float(value)):
            pass
        else:
            bad_init_uids.append(uid)

    for uid in bad_init_uids:
        del problem.init_guess[uid]

    for uid, value in problem.diff_init_guess.items():
        if np.isfinite(float(value)):
            pass
        else:
            bad_diff_uids.append(uid)

    for uid in bad_diff_uids:
        del problem.diff_init_guess[uid]


def _get_bus_connected_input_var_if_present(in_var: Var,
                                            bus_model: Block) -> Optional[Var]:
    """
    Return the authoritative bus variable connected to one device input.

    :param in_var: Device root input variable.
    :param bus_model: Connected bus symbolic block.
    :return: Matching bus variable or ``None``.
    """
    bus_var: Optional[Var] = _get_external_mapping_var_if_present(mdl=bus_model, key=in_var.ref)
    return bus_var


def _get_balanced_vsc_dc_power(pf_results: PowerFlowResults, vsc_index: int) -> complex:
    """
    Return the balanced VSC DC-side active power in system-base units.

    :param pf_results: Balanced power-flow results.
    :param vsc_index: VSC index.
    :return: DC-side complex power.
    """
    pfp_value: Optional[Any] = _get_array_entry_if_in_range(pf_results.Pfp_vsc, vsc_index)
    pfn_value: Optional[Any] = _get_array_entry_if_in_range(pf_results.Pfn_vsc, vsc_index)
    pfp_float: float = 0.0 if pfp_value is None else float(pfp_value)
    pfn_float: float = 0.0 if pfn_value is None else float(pfn_value)
    # Balanced PF stores the DC-side transfer on ``Pfp_vsc`` with the network
    # branch sign convention. EMT DC-side current seeding expects the converter
    # import sign, so keep the total as provided and let the caller apply its own
    # terminal convention consistently.
    return complex(pfp_float + pfn_float, 0.0)


def _get_balanced_vsc_ac_power(pf_results: PowerFlowResults, vsc_index: int) -> complex:
    """
    Return the balanced VSC AC-side complex power in system-base units.

    Some PF result containers still leave ``St_vsc`` at zero for valid AC/DC
    operating points. In that case, use the available DC-side transfer as the
    active-power fallback so EMT initialization preserves the scheduled power.

    :param pf_results: Balanced power-flow results.
    :param vsc_index: VSC index.
    :return: AC-side complex power.
    """
    st_value: Optional[Any] = _get_array_entry_if_in_range(pf_results.St_vsc, vsc_index)
    st_complex: complex

    if st_value is None:
        return -_get_balanced_vsc_dc_power(pf_results, vsc_index)
    else:
        st_complex = complex(st_value)

    if abs(st_complex) > 1.0e-12:
        return st_complex
    else:
        return -_get_balanced_vsc_dc_power(pf_results, vsc_index)


def _find_event_var_owner(block: Block, target_var: Var) -> Optional[Block]:
    """
    Return the block that owns one runtime event parameter variable.

    GUI-authored EMT models may keep the actual runtime parameter inside a child
    block while the wrapper root exposes only proxy metadata. Runtime seeding
    therefore has to locate the block that owns the parameter before updating
    the corresponding ``event_dict`` entry.

    :param block: Root block to inspect.
    :param target_var: Runtime parameter variable to locate.
    :return: Owner block or ``None`` when the variable is not present.
    """
    blocks: List[Block] = _collect_block_hierarchy(block)
    block_item: Block

    # The hierarchy walk is explicit so wrapper roots and leaf models follow the
    # same ownership lookup path during PF-derived runtime seeding.
    for block_item in blocks:
        for event_var in block_item.event_dict.keys():
            if event_var is target_var or event_var.uid == target_var.uid:
                return block_item
            else:
                pass

    return None


def get_branch_terminal_voltage_refs(
        phase_mask: List[bool],
) -> Tuple[List[VarPowerFlowReferenceType], List[VarPowerFlowReferenceType]]:
    """
    Build terminal-voltage references for an AC branch with matching end phases.

    :param phase_mask: Active phases in NABC order, shared by both ends.
    :return: From-side and to-side reference lists, each in active NABC order.
    """
    vf_refs: List[VarPowerFlowReferenceType] = list([
        VarPowerFlowReferenceType.vf_N,
        VarPowerFlowReferenceType.vf_A,
        VarPowerFlowReferenceType.vf_B,
        VarPowerFlowReferenceType.vf_C,
    ])
    vt_refs: List[VarPowerFlowReferenceType] = list([
        VarPowerFlowReferenceType.vt_N,
        VarPowerFlowReferenceType.vt_A,
        VarPowerFlowReferenceType.vt_B,
        VarPowerFlowReferenceType.vt_C,
    ])

    from_refs: List[VarPowerFlowReferenceType] = list()
    to_refs: List[VarPowerFlowReferenceType] = list()
    for phase_index, is_active in enumerate(phase_mask):
        if is_active:
            from_refs.append(vf_refs[phase_index])
            to_refs.append(vt_refs[phase_index])
        else:
            pass

    return from_refs, to_refs


def validate_line_phase_layout(
        branch: BranchParent,
        mdl: Block,
        effective_external_mapping: Dict[Any, Var],
        logger: Logger | None,
) -> bool:
    """
    Validate that a pi-line EMT block matches the physical branch phase layout.

    The EMT parameter mapper writes reduced branch matrices into the fixed NABC
    API map using ``branch.ys``. This helper therefore checks that the symbolic
    pi-line terminal layout still matches the physical branch phase mask before
    the device is flattened into the system model. The validation result is
    independent of diagnostic availability: a missing logger suppresses the log
    entry but never turns an invalid topology into a valid one.

    :param branch: Grid branch device.
    :param mdl: EMT block associated with the branch.
    :param effective_external_mapping: Problem-local mapping already completed
        from modern declarations and compatible legacy input references.
    :param logger: Optional driver-owned logger used for diagnostics.
    :return: ``True`` when symbolic and physical terminal layouts match.
    """

    # The branch admittance mask is the physical topology source of truth, so it
    # defines which symbolic terminal voltage references must exist on the block.
    ph_mask: List[bool] = list([
        bool(branch.ys.phN),
        bool(branch.ys.phA),
        bool(branch.ys.phB),
        bool(branch.ys.phC),
    ])

    from_refs, to_refs = get_branch_terminal_voltage_refs(ph_mask)
    expected_refs: List[VarPowerFlowReferenceType] = from_refs + to_refs

    # The external-mapping keys declare the semantic branch interface. Their
    # target variables can already have been connected to bus variables, whose
    # references are ``v_*`` rather than the original ``vf_*`` and ``vt_*``.
    # Inspecting the targets or ``in_vars`` would consequently reject a valid
    # loaded model merely because its terminal connections were restored.
    all_from_refs, all_to_refs = get_branch_terminal_voltage_refs([True, True, True, True])
    terminal_refs: List[VarPowerFlowReferenceType] = all_from_refs + all_to_refs

    external_refs: List[VarPowerFlowReferenceType] = list()
    legacy_refs: List[VarPowerFlowReferenceType] = list()
    resolved_refs: List[VarPowerFlowReferenceType] = list()
    hierarchy: List[Block] = _collect_block_hierarchy(mdl)
    terminal_ref: VarPowerFlowReferenceType

    # Report each source independently. This diagnostic inspection does not
    # resolve the interface again; the authoritative result is the mapping
    # supplied by the problem-local registry.
    for terminal_ref in terminal_refs:
        has_external_ref: bool = False
        has_legacy_ref: bool = False
        hierarchy_block: Block

        for hierarchy_block in hierarchy:
            hierarchy_mapping: Dict[Any, Var] | None = hierarchy_block.external_mapping
            mapped_var: Var | None
            if hierarchy_mapping is None:
                mapped_var = None
            else:
                mapped_var = hierarchy_mapping.get(terminal_ref, None)
            if mapped_var is not None:
                has_external_ref = True
            else:
                pass

            in_var: Var
            for in_var in hierarchy_block.in_vars:
                if in_var.ref == terminal_ref:
                    has_legacy_ref = True
                else:
                    pass

        if has_external_ref:
            external_refs.append(terminal_ref)
        else:
            pass

        if has_legacy_ref:
            legacy_refs.append(terminal_ref)
        else:
            pass

        resolved_var: Var | None = effective_external_mapping.get(terminal_ref, None)
        if resolved_var is not None:
            resolved_refs.append(terminal_ref)
        else:
            pass

    # Keep the exact phase order deterministic so a misplaced terminal is also
    # diagnosed instead of being hidden by a set comparison.
    layout_is_valid: bool = resolved_refs == expected_refs
    if layout_is_valid:
        pass
    else:
        missing_refs: List[VarPowerFlowReferenceType] = list(
            terminal_ref for terminal_ref in expected_refs if terminal_ref not in resolved_refs
        )
        unexpected_refs: List[VarPowerFlowReferenceType] = list(
            terminal_ref for terminal_ref in resolved_refs if terminal_ref not in expected_refs
        )
        if logger is not None:
            logger.add_error(
                msg="Pi-line template terminal phase layout does not match the physical line phase layout.",
                device=branch.name,
                device_class=str(branch.device_type),
                value=(
                    f"external_mapping={external_refs}; legacy_in_vars={legacy_refs}; "
                    f"resolved={resolved_refs}; missing={missing_refs}; unexpected={unexpected_refs}"
                ),
                expected_value=str(expected_refs),
                device_property="emt_terminal_phase_layout",
            )
        else:
            pass

    return layout_is_valid



def _accumulate_kcl_current(
        i_kcl: Dict[int, List[Any]],
        bus_index: int,
        phase_index: int,
        current_expression: Any,
        sign: float,
) -> None:
    """
    Accumulate one symbolic current contribution into the bus KCL.

    The EMT nodal equations are KCL equations. This helper keeps the sign
    convention explicit:
    - ``sign = -1.0`` for branch currents leaving the bus,
    - ``sign = +1.0`` for injection currents entering the bus.

    :param i_kcl: Bus-phase KCL symbolic accumulator.
    :param bus_index: Bus index.
    :param phase_index: Phase index in NABC order.
    :param current_expression: Symbolic current contribution.
    :param sign: Contribution sign.
    :return: None.
    """
    if current_expression is None:
        pass
    else:
        i_kcl[bus_index][phase_index] = i_kcl[bus_index][phase_index] + sign * current_expression


def _apply_expression_substitution(expression: Any, substitution_map: Dict[Var, Var]) -> Any:
    """
    Apply one variable-substitution map to one symbolic expression.

    :param expression: Symbolic expression to rewrite.
    :param substitution_map: Variable substitution map.
    :return: Rewritten expression.
    """
    if expression is None:
        return None
    else:
        pass

    if len(substitution_map) == 0:
        return expression
    else:
        pass

    if isinstance(expression, (Expr, Var, Const)):
        return expression.subs(substitution_map).simplify()
    else:
        return expression


def _zero_ac_power_vector() -> np.ndarray:
    """
    Return a zero complex power vector in NABC order.

    :return: Zero complex power vector.
    """
    return np.zeros(4, dtype=np.complex128)


def get_currents_from_power(
        voltages: np.ndarray, phase_powers: np.ndarray, current_scale: float,
) -> np.ndarray:
    """Return RMS phase currents, preserving the supplied power-flow direction.

    Inputs have matching phase order. Use current_scale=3 for phase powers
    on total three-phase Sbase and currents on Sbase/(sqrt(3)*Vbase_LL).
    Use current_scale=1 when power and voltage bases directly give the
    desired current base. Neutral handling belongs to the caller.
    Missing phasors and voltages too small to divide by produce zero current.
    """
    if voltages.shape != phase_powers.shape:
        raise ValueError("Voltage and phase-power vectors must have matching shapes")
    currents = np.zeros(voltages.shape, dtype=np.complex128)
    for index, voltage in enumerate(voltages):
        power = phase_powers[index]
        phasors_available = not np.isnan(voltage) and not np.isnan(power)
        if phasors_available and abs(voltage) > 1e-12:
            currents[index] = current_scale * np.conj(power / voltage)
    return currents


def _phase_sequence_shift(phase_index: int) -> complex:
    """
    Return the phase shift used to reconstruct balanced phase phasors.

    Phase order is NABC.

    :param phase_index: Phase index in NABC order.
    :return: Complex unit phasor applied to the balanced bus phasor.
    """
    if phase_index == 0:
        return 0.0 + 0.0j
    else:
        if phase_index == 1:
            return 1.0 + 0.0j
        else:
            if phase_index == 2:
                return np.exp(-1j * 2.0 * np.pi / 3.0)
            else:
                return np.exp(+1j * 2.0 * np.pi / 3.0)

class EmtProblemDae(EmtProblemTemplate):
    """
    Electrical parser layer for the EMT DAE Problem.

    Responsibilities:
      - Traverses the MultiCircuit to extract electrical devices.
      - Constructs nodal KCL balances per phase.
      - Processes external piecewise events into the unified block.
      - Maintains mapping between physical devices and symbolic variables.
      - Delegates all mathematical and indexing plumbing to BaseProblem.
      - Initializes PF-based guesses AND evaluates mdl.init_eqs explicitly (Explicit init).
    """
    __slots__ = (
        "logger",
        "options",
        "power_flow_results",
        "power_flow_results_3ph",
        "build_report",
        "history_models",
        "initialization_report",
        "step_counter",
        "_device_type_disposition",
        "_local_bus_kcl_blocks",
        "_runtime_parameter_eqs0",
        "_runtime_parameter_devices",
        "_runtime_parameter_owner_blocks",
        "_event_parameter_device_idtags",
        "_event_parameter_name_lookup",
        "_active_events_group",
        "_continuous_event_parameter_uids",
        "_discrete_event_parameter_uids",
        "_scheduled_mode_events",
        "_mode_event_cursor",
        "_block_boundary_updater",
        "_fmu_cs_adapters",
        "_pending_fmu_cs_devices",
        "_fmu_me_adapters",
        "_pending_fmu_me_devices",
        "_manufacturer_native_runtime_session",
        "_device_models_with_init_eqs",
        "_device_models_with_init_eqs_seen",
        "_device_models_for_ptc",
        "_local_external_mapping_by_block_uid",
        "_static_parameter_mapping_diagnostics",
        "_temp_init_guess",
        "_temp_diff_init_guess",
        "_temp_post_init_guess",
        "_temp_post_diff_init_guess",
        "_vars2device",
        "_vars_info",
        "_manufacturer_native_runtime_session",
    )

    def __init__(self,
                 grid: MultiCircuit,
                 options: EmtOptions,
                 pf_results_3ph: PowerFlowResults3Ph | None = None,
                 pf_results: PowerFlowResults | None = None,
                 progress_signal: DummySignal | None = None,
                 progress_text: DummySignal | None = None,
                 logger: Logger | None = None) -> None:
        """
        Initializes the EMT Problem by parsing the grid and passing the
        resulting mathematical block to the BaseProblem constructor.
        :param grid: MultiCircuit
        :param options: EmtOptions
        :param pf_results_3ph: PowerFlowResults3Ph
        :param pf_results: PowerFlowResults
        :param progress_signal: progress_signal
        :param progress_text: progress_text
        :param logger: Optional logger owned by the simulation driver.
        """
        # Structural collection can emit diagnostics before the base problem is
        # constructed. Keep the supplied owner or create one for default callers.
        self.logger: Logger = Logger() if logger is None else logger
        self._static_parameter_mapping_diagnostics: StaticParameterMappingDiagnostics = (
            StaticParameterMappingDiagnostics(
                logger=self.logger,
                simulation_mode=DynamicSimulationMode.EMT,
            )
        )
        self.grid = grid
        self.options = options
        self._device_type_disposition: Dict[DeviceType, str] = _build_emt_device_type_disposition_table()
        _validate_emt_device_type_disposition_table(self._device_type_disposition)
        self.power_flow_results_3ph = pf_results_3ph
        self.power_flow_results = pf_results

        self._vars_info: Dict[ALL_DEV_TYPES, List[Var]] = dict()
        self._vars_glob_name2uid: Dict[str, int] = dict()
        self._vars2device: Dict[int, ALL_DEV_TYPES] = dict()
        self._temp_init_guess: Dict[int, float] = dict()
        self._temp_post_init_guess: Dict[int, float] = dict()
        self._temp_diff_init_guess: Dict[int, float] = dict()
        self._temp_post_diff_init_guess: Dict[int, float] = dict()
        self.initialization_report: EmtInitializationReport | None = None
        self.build_report: Dict[str, float] = dict()

        self._scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]] = dict()
        self._mode_event_cursor: Dict[int, int] = dict()
        self._runtime_parameter_eqs0: List[Any] = list()
        # Structural collection can seed PF values before the template constructor
        # creates its runtime index and value containers, so provide empty stores
        # for that pre-construction phase. The template replaces them afterwards.
        self._uid2idx_event_params: Dict[int, int] = dict()
        self._event_parameters_eqs: List[Any] = list()
        self._runtime_all_parameters_source: List[Var] = list()
        self._runtime_all_eqs_source: List[Any] = list()
        self._event_params_values: np.ndarray = np.zeros(0, dtype=np.float64)
        self._event_parameter_device_idtags: Dict[int, str] = dict()
        self._event_parameter_name_lookup: Dict[Tuple[str, str], int] = dict()
        self._continuous_event_parameter_uids: Set[int] = set()
        self._discrete_event_parameter_uids: Set[int] = set()
        self._active_events_group: EmtEventsGroup | None = None
        self._local_bus_kcl_blocks: List[Block] = list()
        self._local_external_mapping_by_block_uid: Dict[int, Dict[Any, Var]] = dict()
        self._runtime_parameter_owner_blocks: Dict[int, Block] = dict()
        self._runtime_parameter_devices: Dict[int, ALL_DEV_TYPES] = dict()

        static_parameter_values_mapping: Dict[Var, Const] = dict()

        # The explicit initialization stage must solve each device working model as
        # one unified symbolic block. Registering nested child blocks separately can
        # break coupled controller/plant operating-point seeds because sibling
        # sub-blocks are then initialized independently instead of sharing one
        # flattened dependency graph.
        self._device_models_with_init_eqs: List[Block] = list()
        self._device_models_with_init_eqs_seen: Set[int] = set()
        self._device_models_for_ptc: List[Block] = list()

        sys_block = Block(children=[], in_vars=[])
        glob_time = Var(self.TIME_NAME)

        self.history_models: List[BergeronHistoryRuntime | JMartiHistoryRuntime] = list()
        self._block_boundary_updater: Any | None = None
        self._manufacturer_native_runtime_session: ManufacturerNativeRuntimeSessionProtocol | None = None
        self.step_counter: int = 0
        self._fmu_cs_adapters: List[Any] = list()
        self._pending_fmu_cs_devices: List[Tuple[Any, Block]] = list()
        self._fmu_me_adapters: List[Any] = list()
        self._pending_fmu_me_devices: List[Tuple[Any, Block]] = list()

        t_build = _tic()
        t_phase_start: float = t_build
        cache_stats_before: Dict[str, float] = get_compiled_functions_cache_stats()

        validate_models_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        self._validate_bus_emt_models_ready()
        validate_models_s += _toc(t_phase_start)
        t_phase_start = _tic()

        self._validate_dynamic_emt_interfaces()
        self._validate_balanced_pf_line_compatibility()
        validate_interfaces_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        # build on local sys_block
        self._build_structure_and_collect(sys_block=sys_block, grid=grid, static_parameter_values_mapping=static_parameter_values_mapping )
        structure_collect_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        sys_block.unify_blocks()
        sys_block.state_vars = _unique_keep_order(sys_block.state_vars)
        sys_block.algebraic_vars = _unique_keep_order(sys_block.algebraic_vars)
        sys_block.diff_vars = _unique_keep_order(sys_block.diff_vars)
        unify_blocks_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        self._validate_connections()
        validate_connections_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        init_eqs_flat: Dict[Var, Any]
        diff_init_eqs_flat: Dict[Var, Any]

        # The concrete EMT problem now owns the canonical hierarchical init
        # collection, which makes the construction flow closer to RMS: the DAE
        # builder performs the structural traversal and the template receives the
        # already-decided symbolic inputs needed for generic bookkeeping.
        init_eqs_flat, diff_init_eqs_flat = _collect_hierarchical_init_equations(sys_block)

        super().__init__(sys_block=sys_block,
                         static_parameter_values_mapping=static_parameter_values_mapping,
                         glob_time=glob_time,
                         init_eqs_flat=init_eqs_flat,
                         diff_init_eqs_flat=diff_init_eqs_flat,
                         vars_glob_name2uid=self._vars_glob_name2uid,
                         progress_signal=progress_signal,
                         progress_text=progress_text)

        self._canonicalize_hierarchical_emt_inputs()

        self._rebuild_results_var_name_lookup()
        template_init_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        # Mark retained runtime parameters:
        #   - scheduled mode parameters
        #   - Bergeron history parameters
        mode_parameters: List[Var] = self._collect_runtime_mode_parameters()
        if len(mode_parameters) > 0:
            self.set_runtime_mode_parameters(mode_parameters)
        else:
            pass

        # Runtime parameter indices may have changed after repartitioning,
        # so Bergeron runtimes must bind their parameter indices afterwards.
        for rt in self.history_models:
            rt.setup_indices(
                uid2idx_vars=self.uid2idx_vars,
                uid2idx_event_params=self.uid2idx_event_params,
                params_offset=0,
            )

        # The retained runtime snapshot must follow the finalized flat runtime
        # vector order, not the original block-discovery order. Bergeron history
        # parameters are classified as retained mode parameters and moved to the
        # tail of the runtime vector, so preserving the already partitioned event
        # equation list keeps later event-group activation aligned with
        # ``uid2idx_event_params``.
        self._runtime_parameter_eqs0 = list(self._event_parameters_eqs)
        finalize_emt_fmu_cs_devices(self)
        finalize_emt_fmu_me_devices(self)

        self._block_boundary_updater = build_boundary_updater_from_block(
            problem=self,
            expression_mode=ProceduralExpressionMode.Compiled,
        )

        if len(self._runtime_mode_parameters) > 0:
            self._initialize_mode_event_state()
        else:
            pass
        runtime_partition_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        # 1) PF guesses
        self.init_guess.update(self._temp_init_guess)
        self.diff_init_guess.update(self._temp_diff_init_guess)
        # Rebuild canonical template fallbacks before promoting PF seeds. The
        # following loop reapplies every problem-owned seed afterwards, so the
        # source hierarchy remains immutable and cannot overwrite the operating
        # point used by explicit initialization.
        self.refresh_runtime_equations_from_hierarchy()
        for uid, value in self._temp_init_guess.items():
            runtime_idx_promote: int | None = self.uid2idx_event_params.get(uid, None)
            if runtime_idx_promote is None:
                pass
            else:
                # Promote the PF seed into both the runtime value and its
                # canonical source equation.  Updating only the flat value is
                # insufficient because explicit initialization evaluates the
                # event graph and would immediately restore the old model
                # default (commonly Vnom=1.0) before resolving dependants.
                self._set_runtime_parameter_value_by_uid(uid=uid, value=float(value))
                self.event_params_init_dict[uid] = float(value)

        # PF seeding may change a runtime parameter that is itself an input to
        # another runtime expression.  A common example is an impedance load:
        # ``Vnom`` is seeded from the solved bus voltage and ``R``/``L`` are
        # derived from ``Vnom`` and the scheduled P/Q.  Resolve that dependency
        # chain before evaluating model init equations; otherwise state seeds
        # such as an inductor's periodic current are computed with the old
        # default impedance while the simulation starts with the refreshed one.
        self._event_params_values = self._initialize_runtime_parameter_values(
            0.0,
            seed_values=self._event_params_values,
        )
        # At this point every PF-derived runtime seed has been applied and the
        # canonical event equations have been refreshed. A remaining null source
        # is therefore either owned by explicit initialization/mode logic or is a
        # genuine model contract error that should be reported with full context.
        self._validate_runtime_parameter_sources_after_power_flow()
        if self.progress_signal is not None:
            self.progress_signal.emit(5)

        # 2) Initialization stage selection.
        # PseudoTransient must work for models without initialization equations.
        # Its only starting data is the PF operating point and runtime constants.
        if (self.options.initialization_method != EmtInitializationMethod.PseudoTransient
                or self.options.init_periodic_samples):
            self._run_explicit_initialization()
        else:
            pass

        # Freeze the fully resolved problem-local runtime equations as the
        # event-free baseline. Native initialization reads the current runtime
        # equations, while later event-group activation starts from
        # ``_runtime_parameter_eqs0``. Keeping both views identical prevents the
        # post-native stage from restoring the pre-PF template placeholders now
        # that source Blocks are deliberately immutable.
        self._runtime_parameter_eqs0 = list(self._event_parameters_eqs)
        explicit_init_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        # 3) Native initialization stage selection.
        # The native stage builds the reduced consistency system for Newton and
        # Auto. PseudoTransient solves complete devices and their references.
        if self.options.init_periodic_samples:
            self.initialization_report = run_emt_native_initialization(problem=self, options=self.options)
            if self.initialization_report.status == EmtInitializationStatus.FAILED:
                raise ValueError(self.initialization_report.message)
        elif self.options.initialization_method == EmtInitializationMethod.Explicit:
            self.initialization_report = EmtInitializationReport(method_requested=EmtInitializationMethod.Explicit)
            self.initialization_report.status = EmtInitializationStatus.RESOLVED
            self.initialization_report.method_used = EmtInitializationMethod.Explicit
            self.initialization_report.message = (
                "Explicit device initialization completed; periodic steady state was not verified."
            )
        elif self.options.initialization_method == EmtInitializationMethod.PseudoTransient:
            self.initialization_report = run_emt_device_pseudo_transient_initialization(
                problem=self,
                blocks=self._device_models_for_ptc,
                options=self.options,
                check_kcl=False,
            )
            if self.initialization_report.status == EmtInitializationStatus.FAILED:
                raise ValueError(self.initialization_report.message)
        elif self.options.initialization_method == EmtInitializationMethod.Auto:
            incomplete_blocks: List[Block] = [
                block for block in self._device_models_for_ptc
                if not self._device_has_complete_explicit_seed(block)
            ]
            device_report: EmtInitializationReport | None = None
            if incomplete_blocks:
                device_report = run_emt_device_pseudo_transient_initialization(
                    problem=self,
                    blocks=incomplete_blocks,
                    options=self.options,
                    check_kcl=False,
                    require_full_coverage=False,
                )
                if device_report.status == EmtInitializationStatus.FAILED:
                    device_report = None
            if device_report is not None:
                device_report.method_requested = EmtInitializationMethod.Auto
                self.initialization_report = validate_emt_periodic_initialization(
                    problem=self,
                    blocks=self._device_models_for_ptc,
                    options=self.options,
                    report=device_report,
                )
                if self.initialization_report.status == EmtInitializationStatus.FAILED:
                    raise ValueError(self.initialization_report.message)
                self.initialization_report.message = (
                    "Auto used device-local periodic pseudo-transient initialization "
                    "for incomplete devices and verified the assembled periodic DAE."
                )
            else:
                auto_options: EmtOptions = copy(self.options)
                auto_options.initialization_method = EmtInitializationMethod.Auto
                self.initialization_report = run_emt_native_initialization(
                    problem=self,
                    options=auto_options,
                )
                self.initialization_report.method_requested = EmtInitializationMethod.Auto
        else:
            self.initialization_report = run_emt_native_initialization(problem=self, options=self.options)
        self._reapply_vsc_pf_seeds_after_native_initialization()
        # for diff_uid, diff_value in self._temp_post_diff_init_guess.items():
        #     if diff_uid in self.diff_init_guess:
        #         pass
        #     else:
        #         self.diff_init_guess[diff_uid] = float(diff_value)
        native_init_s: float = _toc(t_phase_start)
        t_phase_start = _tic()

        if self.progress_signal is not None:
            self.progress_signal.emit(10)

        # EMT event groups are activated only after the initialization stage.
        # Some runtime parameters start as Const(None) placeholders and are
        # resolved during explicit/native initialization. Wrapping them in
        # piecewise expressions before that would preserve the undefined default
        # and break the initial runtime-parameter evaluation.
        self.set_events_group(None)
        self._seed_all_switch_models()
        # ``set_events_group()`` has already rebuilt the runtime equations while
        # preserving the operating-point vector resolved by explicit/native
        # initialization. Switch seeding updates that same problem-local storage
        # directly. A generic rebuild here would start from a zero vector and
        # erase deferred PF seeds whose source Block intentionally remains
        # immutable.
        if self.initialization_report is None:
            pass
        else:
            _compute_missing_dx0(
                problem=self,
                report=self.initialization_report,
                x_full=self.get_x0(),
                dx_full=self.get_dx0(),
                runtime_params=self.event_params_values.copy(),
                constant_params=np.asarray(
                    [float(const.value) for const in self.get_parameters_values()],
                    dtype=np.float64,
                ),
                include_existing=True,
            )

        # Replay preserved PF guesses only for values the native solver did not
        # resolve. Replaying algebraic guesses over a converged native solution
        # would undo its network consistency correction.
        native_solution_resolved = (
            self.initialization_report is not None
            and self.initialization_report.status == EmtInitializationStatus.RESOLVED
            and self.initialization_report.method_used != EmtInitializationMethod.Explicit
        )
        # A DC line's two terminal current seeds form one branch-flow pair.
        # Preserve that pair together; keeping only the native correction on
        # one side can leave the stored initial point with unbalanced currents.
        dc_line_current_seed_uids = {
            mapped_var.uid
            for dc_line in self.grid.dc_lines
            for reference in (
                VarPowerFlowReferenceType.If_dc,
                VarPowerFlowReferenceType.It_dc,
                VarPowerFlowReferenceType.Idc,
            )
            if (mapped_var := _get_external_mapping_var_if_present(
                mdl=dc_line.emt_model, key=reference,
            )) is not None
        }
        post_init_guesses = {
            uid: value for uid, value in self._temp_post_init_guess.items()
            if not (
                native_solution_resolved
                and uid in self.uid2idx_vars
                and uid not in dc_line_current_seed_uids
            )
        }
        self.init_guess.update(post_init_guesses)
        self.diff_init_guess.update(self._temp_post_diff_init_guess)

        # Runtime parameters follow the same rule: once native/explicit
        # initialization is complete, any preserved PF-derived runtime seed must
        # be replayed into the canonical runtime storages as well. Otherwise a
        # later runtime-vector rebuild can keep one stale placeholder value even
        # though the variable-side post-init snapshot was preserved correctly.
        for uid, value in self._temp_post_init_guess.items():
            if uid in self.uid2idx_event_params:
                self._set_runtime_parameter_value_by_uid(uid=uid, value=float(value))
            else:
                pass

        # Keep the remaining preserved values aligned after runtime replay.
        self.init_guess.update(post_init_guesses)
        
        # Re-evaluate retained mode parameters from the final runtime equations
        # after every PF-derived runtime seed has been replayed. This keeps mode
        # values such as valve ``path_mode`` aligned with the updated runtime
        # parameter sources instead of leaving them at their earlier placeholder
        # evaluation.
        self._event_params_values = self._initialize_runtime_parameter_values(
            0.0,
            seed_values=self._event_params_values,
        )
        # PF post-init replay may replace model state/algebraic guesses after
        # explicit initialization (notably transformer winding currents). Any
        # derivative computed before that replay then belongs to the old state
        # and creates a non-zero DAE residual at t=0. Re-evaluate every model-
        # supplied differential equation from the final state and parameter
        # vectors so dx0 remains owned by, and consistent with, the model.
        if self.initialization_report is not None:
            _compute_missing_dx0(
                problem=self,
                report=self.initialization_report,
                x_full=self.get_x0(),
                dx_full=self.get_dx0(),
                runtime_params=self.event_params_values.copy(),
                constant_params=np.asarray(
                    [float(const.value) for const in self.get_parameters_values()],
                    dtype=np.float64,
                ),
                include_existing=True,
            )
            # The cached RHS compiler can retain an earlier alias value when
            # a PF-seeded algebraic reference changes late in initialization.
            # Evaluate the final equations against the final UID bindings so
            # the derivatives used by the first integration step match x0.
            final_bindings: Dict[int, float] = {
                uid: float(self.get_x0()[idx]) for uid, idx in self.uid2idx_vars.items()
            }
            final_bindings.update({
                uid: float(self.get_dx0()[idx]) for uid, idx in self.uid2idx_diff.items()
            })
            final_bindings.update({
                uid: float(self.event_params_values[idx])
                for uid, idx in self.uid2idx_event_params.items()
            })
            final_bindings.update({
                uid: float(self.get_parameters_values()[idx].value)
                for uid, idx in self.uid2idx_params.items()
            })
            final_bindings[self.glob_time.uid] = 0.0
            state_rhs_by_uid = {
                state_var.uid: equation
                for state_var, equation in zip(self.get_state_vars(), self.get_state_eqs())
            }
            for differential in self.get_diff_vars():
                base_var = differential.base_var
                if base_var is not None and base_var.uid in state_rhs_by_uid:
                    value = float(state_rhs_by_uid[base_var.uid].eval_uid(final_bindings))
                    self.diff_init_guess[differential.uid] = value
                    final_bindings[differential.uid] = value
        else:
            pass
        _drop_nonfinite_initialization_entries(self)
        if self.options.initialization_method == EmtInitializationMethod.Explicit:
            # Explicit initialization only evaluates device seeds. Record the
            # assembled network error instead of reporting the default zero.
            algebraic_residual = max(
                (abs(float(equation.eval_uid(final_bindings)))
                 for equation in self.get_algebraic_eqs()),
                default=0.0,
            )
            self.initialization_report.initial_residual_inf = algebraic_residual
            self.initialization_report.final_residual_inf = algebraic_residual
            self.initialization_report.message = (
                f"Explicit device initialization completed with algebraic residual "
                f"{algebraic_residual:.3e}; periodic steady state was not verified."
            )
            if algebraic_residual > self.options.tolerance and self.logger is not None:
                self.logger.add_warning(
                    msg="EMT explicit initialization exceeds algebraic tolerance.",
                    value=f"{algebraic_residual:.3e}",
                    expected_value=f"<= {self.options.tolerance:.3e}",
                )
        if self.options.initialization_method == EmtInitializationMethod.PseudoTransient:
            self.initialization_report = validate_emt_periodic_initialization(
                problem=self,
                blocks=self._device_models_for_ptc,
                options=self.options,
                report=self.initialization_report,
            )
            if self.initialization_report.status == EmtInitializationStatus.FAILED:
                raise ValueError(self.initialization_report.message)
        nonfinite_entries: List[str] = _collect_nonfinite_problem_entries(self)
        if len(nonfinite_entries) == 0:
            pass
        else:
            detail_text: str = "; ".join(nonfinite_entries[:20])
            if self.logger is not None:
                self.logger.add_error(
                    msg="EMT initialization left non-finite state values.",
                    device=str(self.grid.name) if self.grid is not None else "emt_problem",
                    value=detail_text,
                    expected_value="Finite x0/dx0 for every EMT variable and differential variable",
                    device_class="EMT",
                    device_property="initialization_finiteness",
                )
            else:
                pass
            raise ValueError(
                "EMT initialization produced non-finite values. "
                f"First entries: {detail_text}"
            )
        events_group_finalize_s: float = _toc(t_phase_start)

        t_done = _toc(t_build)
        cache_stats_after: Dict[str, float] = get_compiled_functions_cache_stats()
        compiled_function_cache_delta: float = cache_stats_after.get("entry_count", 0.0) - cache_stats_before.get("entry_count", 0.0)
        native_structural_cold_s: float
        native_numeric_refresh_s: float

        if self.initialization_report is None:
            native_structural_cold_s = 0.0
            native_numeric_refresh_s = 0.0
        else:
            native_structural_cold_s = float(self.initialization_report.reduced_system_build_s)
            native_numeric_refresh_s = (
                float(self.initialization_report.runtime_param_build_s)
                + float(self.initialization_report.constant_param_build_s)
                + float(self.initialization_report.initial_residual_eval_s)
                + float(self.initialization_report.newton_elapsed_s)
                + float(self.initialization_report.pseudo_transient_elapsed_s)
                + float(self.initialization_report.dx0_completion_s)
            )

        structural_cold_s: float = (
            validate_models_s
            + structure_collect_s
            + unify_blocks_s
            + validate_connections_s
            + template_init_s
            + runtime_partition_s
            + explicit_init_s
            + native_structural_cold_s
        )
        numeric_refresh_s: float = native_numeric_refresh_s + events_group_finalize_s

        self.build_report = dict(
            validate_models_s=validate_models_s,
            structure_collect_s=structure_collect_s,
            unify_blocks_s=unify_blocks_s,
            validate_connections_s=validate_connections_s,
            template_init_s=template_init_s,
            runtime_partition_s=runtime_partition_s,
            explicit_init_s=explicit_init_s,
            native_init_s=native_init_s,
            events_group_finalize_s=events_group_finalize_s,
            structural_cold_s=structural_cold_s,
            numeric_refresh_s=numeric_refresh_s,
            native_structural_cold_s=native_structural_cold_s,
            native_numeric_refresh_s=native_numeric_refresh_s,
            compiled_function_cache_delta=compiled_function_cache_delta,
            persistent_init_cache_hit=1.0 if (self.initialization_report is not None and self.initialization_report.persistent_cache_hit) else 0.0,
            persistent_init_cache_load_s=0.0 if self.initialization_report is None else float(self.initialization_report.persistent_cache_load_s),
            persistent_init_cache_store_s=0.0 if self.initialization_report is None else float(self.initialization_report.persistent_cache_store_s),
            total_s=t_done,
        )

        if options.verbose > 0:
            if self.logger is not None:
                self.logger.add_debug(f"init guess = {self.init_guess}")
                self.logger.add_debug(f"diff init guess = {self.diff_init_guess}")
            else:
                pass
            if self.initialization_report is None:
                pass
            else:
                if self.logger is not None:
                    self.logger.add_debug(
                        f"EMT initialization used {self.initialization_report.method_used} | "
                        f"status={self.initialization_report.status.name} | "
                        f"res0={self.initialization_report.initial_residual_inf:.3e} | "
                        f"resf={self.initialization_report.final_residual_inf:.3e} | "
                        f"newton={self.initialization_report.newton_iterations} | "
                        f"ptc={self.initialization_report.pseudo_transient_steps} | "
                        f"auto_dx0={self.initialization_report.automatic_dx0_count}"
                    )
                else:
                    pass
            if self.logger is not None:
                self.logger.add_debug(
                    f"EMT electrical problem parsed in {t_done:.4f}s | "
                    f"vars={self._n_vars} (state={self._n_state}, alg={self._n_alg}) | "
                    f"eqs(state={len(self._state_eqs)}, alg={len(self._algebraic_eqs)})"
                )
            else:
                pass

    # ---------------------------------------------------------------------
    # init_eqs registration + explicit init execution
    # ---------------------------------------------------------------------
    def _device_block_has_init_equations(self, mdl: Block) -> bool:
        """
        Return whether one device block contributes explicit init equations.

        :param mdl: Root block to inspect.
        :type mdl: Block
        :return: ``True`` when the device block has explicit init equations.
        :rtype: bool
        """
        init_eqs: Dict[Var, Expr] = mdl.init_eqs
        diff_init_eqs: Dict[Var, Expr] = mdl.diff_init_eqs
        has_init_eqs: bool = len(init_eqs) > 0
        has_diff_init_eqs: bool = len(diff_init_eqs) > 0

        if has_init_eqs:
            return True
        else:
            if has_diff_init_eqs:
                return True
            else:
                return False

    def _device_has_complete_explicit_seed(self, mdl: Block) -> bool:
        """Return whether explicit initialization supplied every owned EMT value."""
        has_explicit_equations = any(
            block.init_eqs or block.diff_init_eqs
            for block in mdl.get_all_blocks()
        )
        if not has_explicit_equations:
            return False
        for block in mdl.get_all_blocks():
            for variable in list(block.state_vars) + list(block.algebraic_vars):
                if variable.uid in self.uid2idx_vars:
                    value = self.init_guess.get(variable.uid, None)
                    if value is None or not np.isfinite(float(value)):
                        return False
            for differential in block.diff_vars:
                if differential.uid in self.uid2idx_diff:
                    value = self.diff_init_guess.get(differential.uid, None)
                    if value is None or not np.isfinite(float(value)):
                        return False
            for event_var, event_expr in block.event_dict.items():
                if (isinstance(event_var, Var)
                        and isinstance(event_expr, Const)
                        and event_expr.value is None
                        and event_var.uid not in self.event_params_init_dict):
                    return False
        return True

    def _register_init_model(self, mdl: Block) -> None:
        """
        Register one device root when its hierarchy owns initialization data.

        ``init_explicit_common()`` builds its graph recursively from the block it
        receives. Registering both an ancestor and one of its descendants would
        therefore evaluate the descendant more than once. The complete device
        root is retained exactly once whenever any block in its hierarchy owns
        ``init_eqs`` or ``diff_init_eqs``.

        :param mdl: Device root block.
        :type mdl: Block
        :return: None.
        :rtype: None
        """
        candidate_blocks: List[Block] = mdl.get_all_blocks()
        candidate_block: Block
        hierarchy_has_init_equations: bool = False

        # Inspect the complete hierarchy before registering anything. The
        # recursive explicit graph will later consume this same hierarchy from
        # the device root, so descendants must not become independent entries.
        for candidate_block in candidate_blocks:
            if self._device_block_has_init_equations(candidate_block):
                hierarchy_has_init_equations = True
            else:
                pass

        # Register only the root. Repeated visits of the same device are still
        # harmless, while ancestor-descendant overlap is structurally impossible.
        if hierarchy_has_init_equations:
            if mdl.uid in self._device_models_with_init_eqs_seen:
                pass
            else:
                self._device_models_with_init_eqs_seen.add(mdl.uid)
                self._device_models_with_init_eqs.append(mdl)
        else:
            pass

    def get_build_report(self) -> Dict[str, float]:
        """
        Return the EMT problem build timing report.

        :return: Build timing report.
        :rtype: Dict[str, float]
        """
        return dict(self.build_report)

    def _seed_emt_input_initialization_from_single_bus_model(self,
                                                             mdl: Block,
                                                             bus_model: Block) -> None:
        """
        Seed explicit EMT input initialization from one connected bus model.

        :param mdl: Device EMT block whose root inputs must be initialized.
        :param bus_model: Connected bus EMT block providing authoritative values.
        :return: None.
        """
        model_var: Var

        for model_var in mdl.in_vars:
            bus_var: Optional[Var] = _get_bus_connected_input_var_if_present(in_var=model_var, bus_model=bus_model)
            if bus_var is None:
                pass
            else:
                if bus_var.uid in self.uid2idx_vars:
                    self._temp_init_guess[model_var.uid] = self._temp_init_guess.get(
                        bus_var.uid,
                        self.get_x0()[self.uid2idx_vars[bus_var.uid]],
                    )
                else:
                    pass

    def _seed_emt_input_initialization_from_branch_bus_models(self,
                                                              mdl: Block,
                                                              bus_from_model: Block,
                                                              bus_to_model: Block) -> None:
        """
        Seed explicit EMT input initialization from the terminal bus models of one branch.

        :param mdl: Device EMT block whose root inputs must be initialized.
        :param bus_from_model: From-side bus EMT block.
        :param bus_to_model: To-side bus EMT block.
        :return: None.
        """
        model_var: Var

        for model_var in mdl.in_vars:
            bus_var: Optional[Var] = _get_bus_connected_input_var_if_present(in_var=model_var, bus_model=bus_from_model)
            if bus_var is None:
                bus_var = _get_bus_connected_input_var_if_present(in_var=model_var, bus_model=bus_to_model)
            else:
                pass

            if bus_var is None:
                pass
            else:
                if bus_var.uid in self.uid2idx_vars:
                    self._temp_init_guess[model_var.uid] = self._temp_init_guess.get(
                        bus_var.uid,
                        self.get_x0()[self.uid2idx_vars[bus_var.uid]],
                    )
                else:
                    pass

    def _register_connected_input_aliases_from_single_bus_model(self,
                                                                mdl: Block,
                                                                bus_model: Block) -> None:
        """
        Register one-block EMT input aliases against one connected bus model.

        :param mdl: Device EMT block whose root inputs must reuse bus compiler names.
        :param bus_model: Connected bus EMT block providing authoritative compiler names.
        :return: None.
        """
        in_var: Var

        for in_var in mdl.in_vars:
            bus_var: Optional[Var] = _get_bus_connected_input_var_if_present(in_var=in_var, bus_model=bus_model)
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
        Register one-block EMT input aliases against the terminal bus models of one branch.

        :param mdl: Device EMT block whose root inputs must reuse bus compiler names.
        :param bus_from_model: From-side bus EMT block.
        :param bus_to_model: To-side bus EMT block.
        :return: None.
        """
        in_var: Var

        for in_var in mdl.in_vars:
            bus_var: Optional[Var] = _get_bus_connected_input_var_if_present(in_var=in_var, bus_model=bus_from_model)
            if bus_var is None:
                bus_var = _get_bus_connected_input_var_if_present(in_var=in_var, bus_model=bus_to_model)
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

    def _canonicalize_hierarchical_emt_inputs(self) -> None:
        """
        Align hierarchical EMT root input aliases with canonical bus variables.

        :return: None.
        """
        injection_obj: Any
        branch_obj: Any

        for injection_obj in self.grid.get_injection_devices_iter():
            self._register_connected_input_aliases_from_single_bus_model(mdl=injection_obj.emt_model,
                                                                         bus_model=injection_obj.bus.emt_model)
            self._seed_emt_input_initialization_from_single_bus_model(mdl=injection_obj.emt_model,
                                                                      bus_model=injection_obj.bus.emt_model)

        for branch_obj in self.grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
            self._register_connected_input_aliases_from_branch_bus_models(mdl=branch_obj.emt_model,
                                                                          bus_from_model=branch_obj.bus_from.emt_model,
                                                                          bus_to_model=branch_obj.bus_to.emt_model)
            self._seed_emt_input_initialization_from_branch_bus_models(mdl=branch_obj.emt_model,
                                                                       bus_from_model=branch_obj.bus_from.emt_model,
                                                                       bus_to_model=branch_obj.bus_to.emt_model)

    def _run_explicit_initialization(self) -> None:
        """
        Run explicit initialization once per registered EMT init-owning block.

        :return: None
        :rtype: None
        """

        if len(self._device_models_with_init_eqs) == 0:
            return
        else:
            pass

        # The explicit solver works on the already assembled global variable maps,
        # while each call consumes one natural block that actually owns init
        # equations. This reduces the architectural dependence on prior block
        # flattening and moves EMT closer to the RMS-style hierarchical contract.
        sys_vars: Dict[int, Var] = {v.uid: v for v in (self._state_vars + self._algebraic_vars)}
        sys_diff_vars: Dict[int, Var] = {dv.uid: dv for dv in self._diff_vars}
        compile_single_equation: Any = build_symbolic_vector_single_equation_compiler(
            compiler_names_dict=self._compiler_names_dict,
            alias_names_dict=self._alias_names_dict,
            vars_name=self.VARS_NAME,
            diff_name=self.DIFF_NAME,
            event_params_name=self.VARIABLE_PARAMS_NAME,
            params_name=self.CONSTANT_PARAMS_NAME,
        )

        seen_blocks: Set[int] = set()

        for mdl in self._device_models_with_init_eqs:
            if mdl.uid not in seen_blocks:
                seen_blocks.add(mdl.uid)

                try:
                    params_array: np.ndarray = np.asarray(
                        [float(const.value) for const in self.get_parameters_values()],
                        dtype=np.float64,
                    )
                    canonical_event_equation_lookup: Dict[int, Any] = _build_event_equation_lookup_from_problem_order(
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=self._event_parameters_eqs,
                    )
                    explicit_event_parameters_eqs: List[Any] = _build_hierarchical_event_equation_list(
                        mdl=mdl,
                        variable_parameters=self._variable_parameters,
                        fallback_event_parameters_eqs=self._event_parameters_eqs,
                    )
                    event_parameter_index: int = 0
                    runtime_parameter: Var
                    while event_parameter_index < len(self._variable_parameters):
                        runtime_parameter = self._variable_parameters[event_parameter_index]
                        if runtime_parameter.uid in canonical_event_equation_lookup:
                            explicit_event_parameters_eqs[event_parameter_index] = canonical_event_equation_lookup[runtime_parameter.uid]
                        else:
                            pass
                        event_parameter_index += 1

                    explicit_initialization_result: ExplicitInitializationResult = init_explicit_common(
                        mdl=mdl,
                        sys_vars=sys_vars,
                        sys_diff_vars=sys_diff_vars,
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=explicit_event_parameters_eqs,
                        constant_parameters=self._constant_parameters,
                        event_param_init_dict=self.event_params_init_dict,
                        init_guess=self.init_guess,
                        diff_init_guess=self.diff_init_guess,
                        uid2idx_vars=self.uid2idx_vars,
                        uid2idx_diff=self.uid2idx_diff,
                        uid2idx_params=self.uid2idx_params,
                        uid2idx_event_params=self.uid2idx_event_params,
                        params_array=params_array,
                        compile_single_equation=compile_single_equation,
                        event_params_array_seed=self._event_params_values,
                        verbose=bool(self.options.verbose > 0),
                    )
                    if explicit_initialization_result.converged:
                        self.init_guess = explicit_initialization_result.init_guess
                        self.diff_init_guess = explicit_initialization_result.diff_init_guess
                    else:
                        raise RuntimeError(explicit_initialization_result.message)

                    # Explicit initialization resolves one PF-consistent local
                    # operating point that must survive the later constructor
                    # replay of ``_temp_post_*`` guesses. Preserve the solved
                    # values for every variable owned by this init block so the
                    # final ``get_x0()`` reflects the explicit-init solution
                    # instead of the rough pre-init PF seed.
                    block_var: Var
                    init_owner: Block
                    for init_owner in mdl.get_all_blocks():
                        for block_var in init_owner.state_vars:
                            if block_var.uid in self.init_guess:
                                self._temp_post_init_guess[block_var.uid] = float(self.init_guess[block_var.uid])
                            else:
                                pass

                        for block_var in init_owner.algebraic_vars:
                            if block_var.uid in self.init_guess:
                                self._temp_post_init_guess[block_var.uid] = float(self.init_guess[block_var.uid])
                            else:
                                pass

                        for block_var in init_owner.diff_vars:
                            if block_var.uid in self.diff_init_guess:
                                self._temp_post_diff_init_guess[block_var.uid] = float(self.diff_init_guess[block_var.uid])
                            else:
                                pass

                        for event_var in init_owner.event_dict.keys():
                            event_idx: int | None = self.uid2idx_event_params.get(event_var.uid, None)

                            if event_idx is None:
                                pass
                            else:
                                self._runtime_parameter_eqs0[event_idx] = self._event_parameters_eqs[event_idx]
                except Exception as e:
                    block_name: str = _get_block_name(mdl)
                    error_detail: str = f"{type(e).__name__}: {str(e)}"

                    if self.logger is not None:
                        self.logger.add_warning(
                            msg="EMT explicit initialization failed for device init block.",
                            device=block_name,
                            value=error_detail,
                            expected_value="Successful explicit initialization",
                            device_class="EMT",
                            device_property="init_explicit"
                        )
                    else:
                        pass

                    if self.options.verbose > 0:
                        if self.logger is not None:
                            self.logger.add_debug(
                                f"[EMT][init_explicit] failed for unified device block '{block_name}'. Error: {error_detail}"
                            )
                        else:
                            pass
                        print(
                            f"EMT explicit initialization failed for unified device block {block_name}. "
                            f"Error detail: {error_detail}"
                        )
                    else:
                        pass
            else:
                pass

        # Explicit initialization may resolve runtime parameters from equations
        # that depend on PF-seeded algebraic/state values. Promote every resolved
        # scalar through the canonical runtime setter before rebuilding the flat
        # vector, so later event setup and solver construction cannot reevaluate
        # an expression whose initialization-only dependencies are unavailable.
        runtime_uid: int
        runtime_value: float | int | complex | None
        for runtime_uid, runtime_value in self.event_params_init_dict.items():
            if runtime_value is None or runtime_uid not in self.uid2idx_event_params:
                pass
            elif isinstance(runtime_value, complex):
                if abs(runtime_value.imag) > 1.0e-12:
                    raise ValueError(
                        "EMT runtime parameter initialization produced a complex "
                        + f"value for uid={runtime_uid}: {runtime_value}."
                    )
                else:
                    self._set_runtime_parameter_value_by_uid(
                        uid=runtime_uid,
                        value=float(runtime_value.real),
                    )
            else:
                self._set_runtime_parameter_value_by_uid(
                    uid=runtime_uid,
                    value=float(runtime_value),
                )

        # Runtime promotion changes canonical source equations. Rebuild the
        # continuous/mode partition before buffer evaluation so native Newton
        # consumes the promoted PF references instead of stale placeholders.
        self._rebuild_runtime_parameter_partition()
        self._build_runtime_param_vectors()

    def _validate_dynamic_emt_interfaces(self) -> None:
        """
        Validate that dynamic EMT ports are compatible with the static bus shells.

        The editor may expose a broader maximum EMT interface than the current
        network configuration. Before any symbolic rewiring or KCL assembly takes
        place, this validation checks that every exposed electrical reference can
        be reconciled with the corresponding bus domain and EMT bus shell.

        :raises EmtInterfaceValidationError: If any device exposes incompatible
            AC, neutral, or DC EMT references.
        :return: None.
        """
        errors: List[str] = list()
        branch: Any
        injection: Any

        for branch in self.grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
            errors.extend(self._validate_emt_device_interface(device=branch))

        for injection in self.grid.get_injection_devices_iter():
            errors.extend(self._validate_emt_device_interface(device=injection))

        if len(errors) > 0:
            error_msg = "EMT interface validation failed:\n" + "\n".join(errors)
            raise EmtInterfaceValidationError(error_msg)
        else:
            pass

    def _validate_balanced_pf_line_compatibility(self) -> None:
        """Require PF3 when a PI line's phase matrices exceed the PF model."""
        if self.power_flow_results_3ph is not None or self.power_flow_results is None:
            return
        for line in self.grid.lines:
            model = line.emt_model
            if model is not None:
                # Line templates declare their runtime kind on the root block.
                # Internal state names are independent of that declaration.
                line_type: EmtLineTypes | None
                try:
                    line_type = EmtLineTypes(model.name)
                except (ValueError, TypeError):
                    line_type = None
                is_pi_line: bool = line_type == EmtLineTypes.PI
                if is_pi_line and _balanced_pf_line_matrix_mismatch(line) > 1.0e-6:
                    raise ValueError(
                        f"EMT PI line '{line.name}' has phase matrices incompatible with "
                        "balanced power flow. Run three-phase power flow and pass "
                        "its results as pf_results_3ph."
                    )

    def _validate_bus_emt_models_ready(self) -> None:
        """
        Validate that every bus exposes one ready-to-use EMT shell before build.

        EMT problem assembly relies on canonical bus voltage shells that must
        already exist when the problem constructor starts. The bus shell is not
        created inside the problem anymore because doing so hides upstream model
        materialization defects and makes the assembly contract harder to reason
        about.

        This validation therefore checks that every bus has one non-empty EMT
        model with the correct domain interface and that no deferred single-bus
        EMT devices remain pending at problem-construction time.

        :raises EmtInterfaceValidationError: When one bus shell is missing,
            incompatible with its domain, or still waiting for deferred devices.
        :return: None.
        """
        errors: List[str] = list()
        bus: Any

        for bus in self.grid.buses:
            bus_model: Block = bus.emt_model
            pending_devices: List[Any] = bus.get_pending_emt_devices()

            if bus_model.empty():
                errors.append(
                    f"  - Bus '{bus.name}' has no EMT bus shell. "
                    f"Initialize bus.emt_model before constructing EmtProblemDae."
                )
            else:
                supported_bus_voltage_refs: Set[VarPowerFlowReferenceType] = self._get_bus_voltage_refs(bus)

                if bus.is_dc:
                    if VarPowerFlowReferenceType.Vdc in supported_bus_voltage_refs:
                        pass
                    else:
                        errors.append(
                            f"  - Bus '{bus.name}' is DC but its EMT shell does not expose Vdc."
                        )
                else:
                    if len(supported_bus_voltage_refs) > 0:
                        pass
                    else:
                        errors.append(
                            f"  - Bus '{bus.name}' is AC but its EMT shell exposes no AC phase voltage references."
                        )

            if len(pending_devices) == 0:
                pass
            else:
                pending_names: List[str] = list()
                pending_device: Any
                for pending_device in pending_devices:
                    pending_names.append(str(pending_device.name))

                errors.append(
                    f"  - Bus '{bus.name}' still has pending EMT device connections: {', '.join(pending_names)}."
                )

        if len(errors) == 0:
            pass
        else:
            raise EmtInterfaceValidationError(
                "EMT bus model readiness validation failed:\n" + "\n".join(errors)
            )

    def _get_device_emt_disposition(self, device_type: DeviceType) -> str:
        """
        Return the explicit EMT disposition assigned to one ``DeviceType``.

        :param device_type: Device type to classify.
        :return: EMT disposition string.
        """
        disposition: Optional[str] = self._device_type_disposition.get(device_type, None)

        if disposition is None:
            raise ValueError(f"Missing EMT disposition for device type {device_type.name}")
        else:
            return disposition

    def _validate_emt_device_interface(self, device: Any) -> List[str]:
        """
        Validate one EMT-capable device according to its explicit disposition.

        The algorithm dispatches by ``DeviceType`` first so the EMT builder never
        relies on broad branch/injection assumptions when deciding how one device
        should be validated.

        :param device: EMT-capable network device.
        :return: List of validation errors.
        """
        disposition: str = self._get_device_emt_disposition(device.device_type)

        if disposition == EmtDeviceDisposition.BRANCH_STRUCTURAL:
            return self._validate_branch_emt_interface(device)
        else:
            if disposition == EmtDeviceDisposition.INJECTION_STRUCTURAL:
                return self._validate_injection_emt_interface(device)
            else:
                if disposition == EmtDeviceDisposition.BUS_STRUCTURAL:
                    return list()
                else:
                    if disposition == EmtDeviceDisposition.NON_EMT_NOOP:
                        return list()
                    else:
                        raise ValueError(
                            f"Unsupported EMT disposition '{disposition}' for device type {device.device_type.name}"
                        )

    def _validate_injection_emt_interface(self, injection: Any) -> List[str]:
        """
        Validate the external EMT interface exposed by one injection device.

        :param injection: Injection device to validate.
        :return: List of validation errors for this device.
        """
        present_refs: Set[VarPowerFlowReferenceType] = self._get_present_external_refs(injection.emt_model)
        errors: List[str] = list()

        errors.extend(self._validate_injection_bus_contract(
            device=injection,
            bus=injection.bus,
            side="injection",
            present_refs=present_refs,
        ))

        return errors

    def _validate_injection_bus_contract(self,
                                         device: Any,
                                         bus: Any,
                                         side: str,
                                         present_refs: Set[VarPowerFlowReferenceType]) -> List[str]:
        """
        Validate one injection-style EMT interface against one bus shell.

        :param device: Device exposing the interface.
        :param bus: Connected bus.
        :param side: User-facing side label.
        :param present_refs: Non-null external references exposed by the device.
        :return: List of validation errors.
        """
        errors: List[str] = list()
        ac_voltage_refs: List[VarPowerFlowReferenceType] = list([
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
        ])
        ac_current_to_voltage: Dict[VarPowerFlowReferenceType, VarPowerFlowReferenceType] = dict({
            VarPowerFlowReferenceType.i_N: VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.i_A: VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.i_B: VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.i_C: VarPowerFlowReferenceType.v_C,
        })
        supported_bus_voltage_refs: Set[VarPowerFlowReferenceType] = self._get_bus_voltage_refs(bus)
        voltage_ref: VarPowerFlowReferenceType
        current_ref: VarPowerFlowReferenceType
        required_voltage_ref: VarPowerFlowReferenceType

        if bus.is_dc:
            for voltage_ref in ac_voltage_refs:
                if voltage_ref in present_refs:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=voltage_ref,
                        detail="AC phase reference exposed on a DC bus.",
                    ))
                else:
                    pass

            for current_ref in ac_current_to_voltage.keys():
                if current_ref in present_refs:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=current_ref,
                        detail="AC current reference exposed on a DC bus.",
                    ))
                else:
                    pass

            if VarPowerFlowReferenceType.Vdc in present_refs and VarPowerFlowReferenceType.Vdc not in supported_bus_voltage_refs:
                errors.append(self._build_emt_interface_error(
                    device=device,
                    bus=bus,
                    side=side,
                    reference=VarPowerFlowReferenceType.Vdc,
                    detail="DC voltage reference exposed but the bus EMT shell has no Vdc variable.",
                ))
            else:
                pass

            if VarPowerFlowReferenceType.Idc in present_refs:
                if VarPowerFlowReferenceType.Vdc not in present_refs:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=VarPowerFlowReferenceType.Idc,
                        detail="DC current reference exposed without a compatible Vdc input reference.",
                    ))
                else:
                    pass

                if VarPowerFlowReferenceType.Vdc not in supported_bus_voltage_refs:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=VarPowerFlowReferenceType.Idc,
                        detail="DC current reference exposed but the bus EMT shell has no Vdc variable.",
                    ))
                else:
                    pass
            else:
                pass
        else:
            if VarPowerFlowReferenceType.Vdc in present_refs:
                errors.append(self._build_emt_interface_error(
                    device=device,
                    bus=bus,
                    side=side,
                    reference=VarPowerFlowReferenceType.Vdc,
                    detail="DC voltage reference exposed on an AC bus.",
                ))
            else:
                pass

            if VarPowerFlowReferenceType.Idc in present_refs:
                errors.append(self._build_emt_interface_error(
                    device=device,
                    bus=bus,
                    side=side,
                    reference=VarPowerFlowReferenceType.Idc,
                    detail="DC current reference exposed on an AC bus.",
                ))
            else:
                pass

            for voltage_ref in ac_voltage_refs:
                if voltage_ref in present_refs and voltage_ref not in supported_bus_voltage_refs:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=voltage_ref,
                        detail="Voltage reference exposed but the bus EMT shell does not support it.",
                    ))
                else:
                    pass

            for current_ref, required_voltage_ref in ac_current_to_voltage.items():
                if current_ref in present_refs:
                    if required_voltage_ref not in present_refs:
                        errors.append(self._build_emt_interface_error(
                            device=device,
                            bus=bus,
                            side=side,
                            reference=current_ref,
                            detail=(
                                f"Current reference exposed without a compatible "
                                f"{required_voltage_ref.value} input reference."
                            ),
                        ))
                    else:
                        pass

                    if required_voltage_ref not in supported_bus_voltage_refs:
                        errors.append(self._build_emt_interface_error(
                            device=device,
                            bus=bus,
                            side=side,
                            reference=current_ref,
                            detail="Current reference exposed but the bus EMT shell does not support the corresponding voltage phase.",
                        ))
                    else:
                        pass
                else:
                    pass

        return errors

    def _validate_branch_emt_interface(self, branch: Any) -> List[str]:
        """
        Validate the external EMT interface exposed by one branch device.

        :param branch: Branch device to validate.
        :return: List of validation errors for this branch.
        """
        present_refs: Set[VarPowerFlowReferenceType] = self._get_present_external_refs(branch.emt_model)
        errors: List[str] = list()

        errors.extend(self._validate_branch_side_emt_interface(
            device=branch,
            bus=branch.bus_from,
            side="from",
            present_refs=present_refs,
            voltage_map=dict({
                VarPowerFlowReferenceType.vf_N: VarPowerFlowReferenceType.v_N,
                VarPowerFlowReferenceType.vf_A: VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.vf_B: VarPowerFlowReferenceType.v_B,
                VarPowerFlowReferenceType.vf_C: VarPowerFlowReferenceType.v_C,
                VarPowerFlowReferenceType.Vf_dc: VarPowerFlowReferenceType.Vdc,
            }),
            current_to_voltage_map=dict({
                VarPowerFlowReferenceType.if_N: VarPowerFlowReferenceType.vf_N,
                VarPowerFlowReferenceType.if_A: VarPowerFlowReferenceType.vf_A,
                VarPowerFlowReferenceType.if_B: VarPowerFlowReferenceType.vf_B,
                VarPowerFlowReferenceType.if_C: VarPowerFlowReferenceType.vf_C,
                VarPowerFlowReferenceType.If_dc: VarPowerFlowReferenceType.Vf_dc,
            }),
        ))

        errors.extend(self._validate_branch_side_emt_interface(
            device=branch,
            bus=branch.bus_to,
            side="to",
            present_refs=present_refs,
            voltage_map=dict({
                VarPowerFlowReferenceType.vt_N: VarPowerFlowReferenceType.v_N,
                VarPowerFlowReferenceType.vt_A: VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.vt_B: VarPowerFlowReferenceType.v_B,
                VarPowerFlowReferenceType.vt_C: VarPowerFlowReferenceType.v_C,
                VarPowerFlowReferenceType.Vt_dc: VarPowerFlowReferenceType.Vdc,
            }),
            current_to_voltage_map=dict({
                VarPowerFlowReferenceType.it_N: VarPowerFlowReferenceType.vt_N,
                VarPowerFlowReferenceType.it_A: VarPowerFlowReferenceType.vt_A,
                VarPowerFlowReferenceType.it_B: VarPowerFlowReferenceType.vt_B,
                VarPowerFlowReferenceType.it_C: VarPowerFlowReferenceType.vt_C,
                VarPowerFlowReferenceType.It_dc: VarPowerFlowReferenceType.Vt_dc,
            }),
        ))

        errors.extend(self._validate_shared_branch_emt_interface(branch, present_refs))
        errors.extend(self._validate_branch_dc_mapping_collisions(branch))

        return errors

    def _validate_branch_side_emt_interface(self,
                                            device: Any,
                                            bus: Any,
                                            side: str,
                                            present_refs: Set[VarPowerFlowReferenceType],
                                            voltage_map: Dict[VarPowerFlowReferenceType, VarPowerFlowReferenceType],
                                            current_to_voltage_map: Dict[VarPowerFlowReferenceType, VarPowerFlowReferenceType]) -> List[str]:
        """
        Validate one side-specific branch EMT contract against one terminal bus.

        :param device: Branch device exposing the interface.
        :param bus: Terminal bus to validate against.
        :param side: ``from`` or ``to``.
        :param present_refs: Non-null external references exposed by the branch.
        :param voltage_map: Mapping from branch voltage refs to bus voltage refs.
        :param current_to_voltage_map: Mapping from branch current refs to branch voltage refs.
        :return: List of validation errors.
        """
        errors: List[str] = list()
        supported_bus_voltage_refs: Set[VarPowerFlowReferenceType] = self._get_bus_voltage_refs(bus)
        branch_voltage_ref: VarPowerFlowReferenceType
        bus_voltage_ref: VarPowerFlowReferenceType
        current_ref: VarPowerFlowReferenceType
        required_branch_voltage_ref: VarPowerFlowReferenceType
        required_bus_voltage_ref: VarPowerFlowReferenceType

        for branch_voltage_ref, bus_voltage_ref in voltage_map.items():
            if branch_voltage_ref in present_refs:
                if bus.is_dc and bus_voltage_ref != VarPowerFlowReferenceType.Vdc:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=branch_voltage_ref,
                        detail="AC branch voltage reference exposed on a DC bus.",
                    ))
                elif (not bus.is_dc) and bus_voltage_ref == VarPowerFlowReferenceType.Vdc:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=branch_voltage_ref,
                        detail="DC branch voltage reference exposed on an AC bus.",
                    ))
                elif bus_voltage_ref not in supported_bus_voltage_refs:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=branch_voltage_ref,
                        detail="Voltage reference exposed but the terminal bus EMT shell does not support it.",
                    ))
                else:
                    pass
            else:
                pass

        for current_ref, required_branch_voltage_ref in current_to_voltage_map.items():
            if current_ref in present_refs:
                required_bus_voltage_ref = voltage_map[required_branch_voltage_ref]

                if required_branch_voltage_ref not in present_refs:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=current_ref,
                        detail=(
                            f"Current reference exposed without a compatible "
                            f"{required_branch_voltage_ref.value} input reference."
                        ),
                    ))
                else:
                    pass

                if bus.is_dc and required_bus_voltage_ref != VarPowerFlowReferenceType.Vdc:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=current_ref,
                        detail="AC branch current reference exposed on a DC bus.",
                    ))
                elif (not bus.is_dc) and required_bus_voltage_ref == VarPowerFlowReferenceType.Vdc:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=current_ref,
                        detail="DC branch current reference exposed on an AC bus.",
                    ))
                elif required_bus_voltage_ref not in supported_bus_voltage_refs:
                    errors.append(self._build_emt_interface_error(
                        device=device,
                        bus=bus,
                        side=side,
                        reference=current_ref,
                        detail="Current reference exposed but the terminal bus EMT shell does not support the corresponding voltage phase.",
                    ))
                else:
                    pass
            else:
                pass

        return errors

    def _validate_shared_branch_emt_interface(self,
                                              branch: Any,
                                              present_refs: Set[VarPowerFlowReferenceType]) -> List[str]:
        """
        Validate shared EMT branch references used by VSC-style branch models.

        Some branch EMT templates use a single AC-side contract ``v_A/B/C`` and a
        single DC-side contract ``Vdc``/``Idc`` instead of side-specific branch
        terminal references. This validator allows that contract only when the
        network has exactly one compatible side for it.

        Two-sided DC branches are handled separately by
        ``_validate_branch_dc_mapping_collisions`` because legacy DC branch
        templates may expose shared ``Vdc`` / ``Idc`` only as aliases of their
        explicit terminal variables.

        :param branch: Branch device to validate.
        :param present_refs: Non-null external references exposed by the branch.
        :return: List of validation errors.
        """
        errors: List[str] = list()
        shared_ac_refs: Set[VarPowerFlowReferenceType] = {
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
            VarPowerFlowReferenceType.i_N,
            VarPowerFlowReferenceType.i_A,
            VarPowerFlowReferenceType.i_B,
            VarPowerFlowReferenceType.i_C,
        }
        shared_dc_refs: Set[VarPowerFlowReferenceType] = {
            VarPowerFlowReferenceType.Vdc,
            VarPowerFlowReferenceType.Idc,
        }
        shared_ac_present: Set[VarPowerFlowReferenceType] = present_refs.intersection(shared_ac_refs)
        shared_dc_present: Set[VarPowerFlowReferenceType] = present_refs.intersection(shared_dc_refs)
        ac_side_count: int = self._count_branch_sides_by_domain(branch, is_dc=False)
        dc_side_count: int = self._count_branch_sides_by_domain(branch, is_dc=True)

        if len(shared_ac_present) > 0:
            if ac_side_count == 1:
                if branch.bus_from.is_dc:
                    errors.extend(self._validate_injection_bus_contract(
                        device=branch,
                        bus=branch.bus_to,
                        side="to",
                        present_refs=shared_ac_present,
                    ))
                else:
                    errors.extend(self._validate_injection_bus_contract(
                        device=branch,
                        bus=branch.bus_from,
                        side="from",
                        present_refs=shared_ac_present,
                    ))
            else:
                errors.extend(self._build_shared_branch_domain_errors(
                    branch=branch,
                    refs=shared_ac_present,
                    expected_domain="AC",
                    side_count=ac_side_count,
                ))
        else:
            pass

        if len(shared_dc_present) > 0:
            if dc_side_count == 1:
                if branch.bus_from.is_dc:
                    errors.extend(self._validate_injection_bus_contract(
                        device=branch,
                        bus=branch.bus_from,
                        side="from",
                        present_refs=shared_dc_present,
                    ))
                else:
                    errors.extend(self._validate_injection_bus_contract(
                        device=branch,
                        bus=branch.bus_to,
                        side="to",
                        present_refs=shared_dc_present,
                    ))
            elif dc_side_count == 2:
                # Two-sided DC branches may legally expose shared aliases when the
                # real contract is still the explicit Vf/Vt and If/It terminal set.
                pass
            else:
                errors.extend(self._build_shared_branch_domain_errors(
                    branch=branch,
                    refs=shared_dc_present,
                    expected_domain="DC",
                    side_count=dc_side_count,
                ))
        else:
            pass

        return errors

    def _is_valid_legacy_shared_dc_branch_alias(self,
                                                branch: Any,
                                                reference: VarPowerFlowReferenceType) -> bool:
        """
        Return whether one shared DC branch reference is a valid legacy alias.

        Legacy two-sided DC branch templates may keep exposing ``Vdc`` or ``Idc``
        for backward compatibility even though EMT assembly now uses the explicit
        terminal contract ``Vf_dc`` / ``Vt_dc`` and ``If_dc`` / ``It_dc``.
        The shared reference is accepted only when both DC sides are present and
        the shared mapping aliases one of the already explicit terminal variables.

        :param branch: Branch device to inspect.
        :param reference: Shared DC reference to validate.
        :return: ``True`` when the shared reference is a safe legacy alias.
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(branch.emt_model)
        shared_var: Var | None
        from_var: Var | None
        to_var: Var | None

        if external_mapping is None:
            return False
        else:
            pass

        if not (branch.bus_from.is_dc and branch.bus_to.is_dc):
            return False
        else:
            pass

        if reference == VarPowerFlowReferenceType.Vdc:
            shared_var = external_mapping.get(VarPowerFlowReferenceType.Vdc, None)
            from_var = external_mapping.get(VarPowerFlowReferenceType.Vf_dc, None)
            to_var = external_mapping.get(VarPowerFlowReferenceType.Vt_dc, None)
        elif reference == VarPowerFlowReferenceType.Idc:
            shared_var = external_mapping.get(VarPowerFlowReferenceType.Idc, None)
            from_var = external_mapping.get(VarPowerFlowReferenceType.If_dc, None)
            to_var = external_mapping.get(VarPowerFlowReferenceType.It_dc, None)
        else:
            return False

        if shared_var is None or from_var is None or to_var is None:
            return False
        else:
            pass

        if shared_var.uid == from_var.uid:
            return True
        else:
            pass

        if shared_var.uid == to_var.uid:
            return True
        else:
            return False

    def _build_shared_branch_domain_errors(self,
                                           branch: Any,
                                           refs: Set[VarPowerFlowReferenceType],
                                           expected_domain: str,
                                           side_count: int) -> List[str]:
        """
        Build explicit errors for ambiguous shared branch-domain references.

        :param branch: Branch device exposing the references.
        :param refs: Shared references that could not be assigned safely.
        :param expected_domain: Domain required by the shared references.
        :param side_count: Number of compatible terminal buses found.
        :return: List of formatted error strings.
        """
        errors: List[str] = list()
        reference: VarPowerFlowReferenceType

        for reference in refs:
            errors.append(
                f"  - Device '{self._get_device_name(branch)}' ({self._get_device_type_label(branch)}) "
                f"branch ref '{reference.value}' is a shared {expected_domain} interface, but the branch has "
                f"{side_count} compatible {expected_domain} side(s). Use side-specific EMT references instead."
            )

        return errors

    def _validate_branch_dc_mapping_collisions(self, branch: Any) -> List[str]:
        """
        Validate that branch DC terminal mappings cannot collide across sides.

        :param branch: Branch device to validate.
        :return: List of validation errors.
        """
        errors: List[str] = list()
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping(branch.emt_model)
        if_dc_var: Var | None
        it_dc_var: Var | None
        v_f_dc_var: Var | None
        v_t_dc_var: Var | None
        shared_v_dc_var: Var | None
        shared_i_dc_var: Var | None

        if external_mapping is None:
            return errors
        else:
            pass

        if_dc_var = external_mapping.get(VarPowerFlowReferenceType.If_dc, None)
        it_dc_var = external_mapping.get(VarPowerFlowReferenceType.It_dc, None)
        v_f_dc_var = external_mapping.get(VarPowerFlowReferenceType.Vf_dc, None)
        v_t_dc_var = external_mapping.get(VarPowerFlowReferenceType.Vt_dc, None)
        shared_v_dc_var = external_mapping.get(VarPowerFlowReferenceType.Vdc, None)
        shared_i_dc_var = external_mapping.get(VarPowerFlowReferenceType.Idc, None)

        if if_dc_var is not None and it_dc_var is not None and if_dc_var.uid == it_dc_var.uid:
            errors.append(
                f"  - Device '{self._get_device_name(branch)}' ({self._get_device_type_label(branch)}) "
                "uses the same variable for both If_dc and It_dc. Branch DC terminal currents must be side-specific."
            )
        else:
            pass

        if v_f_dc_var is not None and v_t_dc_var is not None and v_f_dc_var.uid == v_t_dc_var.uid:
            errors.append(
                f"  - Device '{self._get_device_name(branch)}' ({self._get_device_type_label(branch)}) "
                "uses the same variable for both Vf_dc and Vt_dc. Branch DC terminal voltages must be side-specific."
            )
        else:
            pass

        if branch.bus_from.is_dc and branch.bus_to.is_dc:
            if shared_v_dc_var is not None:
                if self._is_valid_legacy_shared_dc_branch_alias(branch, VarPowerFlowReferenceType.Vdc):
                    pass
                else:
                    errors.append(
                        f"  - Device '{self._get_device_name(branch)}' ({self._get_device_type_label(branch)}) "
                        "exposes shared Vdc on a two-sided DC branch without a full side-specific alias contract. "
                        "Use Vf_dc and Vt_dc instead."
                    )
            else:
                pass

            if shared_i_dc_var is not None:
                if self._is_valid_legacy_shared_dc_branch_alias(branch, VarPowerFlowReferenceType.Idc):
                    pass
                else:
                    errors.append(
                        f"  - Device '{self._get_device_name(branch)}' ({self._get_device_type_label(branch)}) "
                        "exposes shared Idc on a two-sided DC branch without a full side-specific alias contract. "
                        "Use If_dc and It_dc instead."
                    )
            else:
                pass
        else:
            pass

        return errors

    def _count_branch_sides_by_domain(self, branch: Any, is_dc: bool) -> int:
        """
        Count the number of branch terminal buses matching one electrical domain.

        :param branch: Branch device to inspect.
        :param is_dc: ``True`` for DC buses, ``False`` for AC buses.
        :return: Number of matching terminal buses.
        """
        count: int = 0

        if branch.bus_from.is_dc == is_dc:
            count += 1
        else:
            pass

        if branch.bus_to.is_dc == is_dc:
            count += 1
        else:
            pass

        return count

    def _get_present_external_refs(self, mdl: Block) -> Set[VarPowerFlowReferenceType]:
        """
        Return the electrical external references exposed by the active root contract.

        A non-null mapping can preserve a dormant connection intent while its
        corresponding phase is absent from the root IO contract. Such mappings
        are not electrically exposed and therefore must not participate in
        interface validation.

        :param mdl: Device block to inspect.
        :return: Set of exposed external reference keys.
        """
        refs: Set[VarPowerFlowReferenceType] = set()
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(
            problem=self,
            mdl=mdl,
        )
        active_root_uids: Set[int] = set(root_var.uid for root_var in mdl.in_vars + mdl.out_vars)
        reference: Any
        mapped_var: Var | None

        if external_mapping is None:
            return refs
        else:
            pass

        for reference, mapped_var in external_mapping.items():
            if isinstance(reference, VarPowerFlowReferenceType) and mapped_var is not None:
                if mapped_var.uid in active_root_uids:
                    refs.add(reference)
                else:
                    pass
            else:
                pass

        return refs

    def _get_bus_voltage_refs(self, bus: Any) -> Set[VarPowerFlowReferenceType]:
        """
        Return the non-null bus-shell voltage references supported by one bus.

        :param bus: Bus API object.
        :return: Supported bus voltage references.
        """
        refs: Set[VarPowerFlowReferenceType] = set()
        reference: VarPowerFlowReferenceType
        candidate_refs: List[VarPowerFlowReferenceType]

        if bus.is_dc:
            candidate_refs = list([VarPowerFlowReferenceType.Vdc])
        else:
            candidate_refs = list([
                VarPowerFlowReferenceType.v_N,
                VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.v_B,
                VarPowerFlowReferenceType.v_C,
            ])

        for reference in candidate_refs:
            if _get_external_mapping_var_if_present(bus.emt_model, reference) is not None:
                refs.add(reference)
            else:
                pass

        return refs

    def _build_emt_interface_error(self,
                                   device: Any,
                                   bus: Any,
                                   side: str,
                                   reference: VarPowerFlowReferenceType,
                                   detail: str) -> str:
        """
        Build one formatted EMT interface-validation error message.

        :param device: Device that exposes the incompatible reference.
        :param bus: Connected bus.
        :param side: User-facing side label.
        :param reference: Incompatible external reference.
        :param detail: Specific mismatch explanation.
        :return: Formatted error string.
        """
        category: str = self._get_emt_interface_ref_category(reference)
        return (
            f"  - Device '{self._get_device_name(device)}' ({self._get_device_type_label(device)}) "
            f"bus '{bus.name}' side '{side}' ref '{reference.value}' [{category}]: {detail}"
        )

    def _get_emt_interface_ref_category(self, reference: VarPowerFlowReferenceType) -> str:
        """
        Classify one EMT electrical reference for user-facing error messages.

        :param reference: Electrical interface reference.
        :return: Category label such as ``AC phase``, ``neutral``, or ``DC``.
        """
        if reference in {
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.i_N,
            VarPowerFlowReferenceType.vf_N,
            VarPowerFlowReferenceType.if_N,
            VarPowerFlowReferenceType.vt_N,
            VarPowerFlowReferenceType.it_N,
        }:
            return "neutral"
        elif reference in {
            VarPowerFlowReferenceType.Vdc,
            VarPowerFlowReferenceType.Idc,
            VarPowerFlowReferenceType.Vf_dc,
            VarPowerFlowReferenceType.Vt_dc,
            VarPowerFlowReferenceType.If_dc,
            VarPowerFlowReferenceType.It_dc,
        }:
            return "DC"
        else:
            return "AC phase"

    def _get_device_name(self, device: Any) -> str:
        """
        Return one stable user-facing device name for diagnostics.

        :param device: Device to describe.
        :return: Device name when available.
        """
        try:
            return str(device.name)
        except Exception:
            return str(type(device).__name__)

    def _get_device_type_label(self, device: Any) -> str:
        """
        Return one stable user-facing device-type label for diagnostics.

        :param device: Device to describe.
        :return: Device-type label.
        """
        try:
            return str(device.device_type.value)
        except Exception:
            return str(type(device).__name__)

    def _validate_connections(self) -> None:
        """
        Validate EMT topology connectivity.

        Checks that each phase exposed by a bus must be connected to at least 2 elements
        (branches or injections). A floating phase indicates an open circuit.

        The phase connection mapping is:
        - Branch in_vars with ref vf_N/A/B/C connect to bus_from's v_N/A/B/C
        - Branch in_vars with ref vt_N/A/B/C connect to bus_to's v_N/A/B/C
        - Injection device in_vars with ref v_N/A/B/C connect to their bus's v_N/A/B/C

        :raises EmtTopologyError: If topology inconsistencies are found.
        """
        phase_ref_to_bus_phase = {
            VarPowerFlowReferenceType.vf_N: VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.vf_A: VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.vf_B: VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.vf_C: VarPowerFlowReferenceType.v_C,
            VarPowerFlowReferenceType.vt_N: VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.vt_A: VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.vt_B: VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.vt_C: VarPowerFlowReferenceType.v_C,
        }

        branch_phase_refs = {
            VarPowerFlowReferenceType.vf_N,
            VarPowerFlowReferenceType.vf_A,
            VarPowerFlowReferenceType.vf_B,
            VarPowerFlowReferenceType.vf_C,
            VarPowerFlowReferenceType.vt_N,
            VarPowerFlowReferenceType.vt_A,
            VarPowerFlowReferenceType.vt_B,
            VarPowerFlowReferenceType.vt_C,
        }
        ac_phases = [
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
        ]
        bus_phase_connections: Dict[Tuple[Any, VarPowerFlowReferenceType], Set[str]] = dict()
        invalid_line_layouts: List[str] = list()
        for bus in self.grid.buses:
            for phase in ac_phases:
                bus_phase_connections[(bus, phase)] = set()

        vsc_ac_phase_refs = {
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
        }

        for br in self.grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
            disposition: str = self._get_device_emt_disposition(br.device_type)

            if disposition == EmtDeviceDisposition.BRANCH_STRUCTURAL:
                br_emt_model: Block = br.emt_model

                if br.device_type == DeviceType.LineDevice:
                    line_external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(
                        problem=self,
                        mdl=br_emt_model,
                    )
                    if line_external_mapping is None:
                        line_external_mapping = dict()
                    else:
                        pass
                    line_layout_is_valid: bool = validate_line_phase_layout(
                        branch=br,
                        mdl=br_emt_model,
                        effective_external_mapping=line_external_mapping,
                        logger=self.logger,
                    )
                    if line_layout_is_valid:
                        pass
                    else:
                        invalid_line_layouts.append(
                            f"  - Line '{br.name}' has an EMT terminal layout that does not match its physical phases."
                        )
                else:
                    pass

                if br_emt_model is not None:
                    br_bus_from: Any = br.bus_from
                    br_bus_to: Any = br.bus_to
                    is_bergeron: bool
                    is_jmarti: bool
                    is_bergeron, is_jmarti = _is_history_runtime_line_block_name(br_emt_model.name)

                    if is_bergeron or is_jmarti:
                        br_ys: Any = br.ys

                        if br_ys.phN:
                            bus_phase_connections[(br_bus_from, VarPowerFlowReferenceType.v_N)].add(f"branch_from:{br.idtag}")
                            bus_phase_connections[(br_bus_to, VarPowerFlowReferenceType.v_N)].add(f"branch_to:{br.idtag}")
                        else:
                            pass

                        if br_ys.phA:
                            bus_phase_connections[(br_bus_from, VarPowerFlowReferenceType.v_A)].add(f"branch_from:{br.idtag}")
                            bus_phase_connections[(br_bus_to, VarPowerFlowReferenceType.v_A)].add(f"branch_to:{br.idtag}")
                        else:
                            pass

                        if br_ys.phB:
                            bus_phase_connections[(br_bus_from, VarPowerFlowReferenceType.v_B)].add(f"branch_from:{br.idtag}")
                            bus_phase_connections[(br_bus_to, VarPowerFlowReferenceType.v_B)].add(f"branch_to:{br.idtag}")
                        else:
                            pass

                        if br_ys.phC:
                            bus_phase_connections[(br_bus_from, VarPowerFlowReferenceType.v_C)].add(f"branch_from:{br.idtag}")
                            bus_phase_connections[(br_bus_to, VarPowerFlowReferenceType.v_C)].add(f"branch_to:{br.idtag}")
                        else:
                            pass
                    else:
                        branch_external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(
                            problem=self,
                            mdl=br_emt_model,
                        )
                        present_branch_refs: Set[VarPowerFlowReferenceType] = set()

                        if branch_external_mapping is not None:
                            branch_ref_key: Any
                            branch_ref_var: Var | None
                            for branch_ref_key, branch_ref_var in branch_external_mapping.items():
                                if isinstance(branch_ref_key, VarPowerFlowReferenceType) and branch_ref_var is not None:
                                    present_branch_refs.add(branch_ref_key)
                                else:
                                    pass
                        else:
                            pass

                        # Direct validation helpers can invoke this method
                        # without the normal device-registration stage. Only in
                        # that case recover legacy input references locally;
                        # production builds already have one authoritative map.
                        has_registered_branch_mapping: bool = (
                            br_emt_model.uid in self._local_external_mapping_by_block_uid
                        )
                        if has_registered_branch_mapping:
                            pass
                        else:
                            branch_block: Block
                            for branch_block in _collect_block_hierarchy(br_emt_model):
                                branch_in_var: Var
                                for branch_in_var in branch_block.in_vars:
                                    if isinstance(branch_in_var.ref, VarPowerFlowReferenceType):
                                        present_branch_refs.add(branch_in_var.ref)
                                    else:
                                        pass

                        branch_ref: VarPowerFlowReferenceType
                        for branch_ref in present_branch_refs:
                            if branch_ref in branch_phase_refs:
                                bus_phase: VarPowerFlowReferenceType = phase_ref_to_bus_phase[branch_ref]

                                if branch_ref in {
                                    VarPowerFlowReferenceType.vf_N,
                                    VarPowerFlowReferenceType.vf_A,
                                    VarPowerFlowReferenceType.vf_B,
                                    VarPowerFlowReferenceType.vf_C,
                                }:
                                    bus_phase_connections[(br_bus_from, bus_phase)].add(f"branch_from:{br.idtag}")
                                else:
                                    if branch_ref in {
                                        VarPowerFlowReferenceType.vt_N,
                                        VarPowerFlowReferenceType.vt_A,
                                        VarPowerFlowReferenceType.vt_B,
                                        VarPowerFlowReferenceType.vt_C,
                                    }:
                                        bus_phase_connections[(br_bus_to, bus_phase)].add(f"branch_to:{br.idtag}")
                                    else:
                                        pass
                            else:
                                if branch_ref in vsc_ac_phase_refs:
                                    if br_bus_to.is_dc:
                                        bus_phase_connections[(br_bus_from, branch_ref)].add(f"branch_from:{br.idtag}")
                                    else:
                                        bus_phase_connections[(br_bus_to, branch_ref)].add(f"branch_to:{br.idtag}")
                                else:
                                    pass
                else:
                    pass
            else:
                pass

        for inj in self.grid.get_injection_devices_iter():
            disposition = self._get_device_emt_disposition(inj.device_type)

            if disposition == EmtDeviceDisposition.INJECTION_STRUCTURAL:
                inj_emt_model: Block = inj.emt_model

                if inj_emt_model is not None:
                    inj_bus: Any = inj.bus
                    injection_external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(
                        problem=self,
                        mdl=inj_emt_model,
                    )
                    if injection_external_mapping is not None:
                        injection_phase: VarPowerFlowReferenceType
                        for injection_phase in ac_phases:
                            injection_voltage_var: Var | None = injection_external_mapping.get(
                                injection_phase,
                                None,
                            )
                            if injection_voltage_var is not None:
                                bus_phase_connections[(inj_bus, injection_phase)].add(f"injection:{inj.idtag}")
                            else:
                                pass
                    else:
                        pass

                    # Preserve direct validation of legacy fixtures which do
                    # not execute the normal registration stage beforehand.
                    has_registered_injection_mapping: bool = (
                        inj_emt_model.uid in self._local_external_mapping_by_block_uid
                    )
                    # Registration turns legacy hierarchy inputs referenced v_N into
                    # the neutral terminal; unregistered fixtures mirror that here.
                    injection_exposes_neutral_input: bool = False
                    if has_registered_injection_mapping:
                        pass
                    else:
                        injection_block: Block
                        for injection_block in _collect_block_hierarchy(inj_emt_model):
                            injection_in_var: Var
                            for injection_in_var in injection_block.in_vars:
                                if injection_in_var.ref in ac_phases:
                                    bus_phase_connections[(inj_bus, injection_in_var.ref)].add(
                                        f"injection:{inj.idtag}"
                                    )
                                else:
                                    pass
                                if injection_in_var.ref == VarPowerFlowReferenceType.v_N:
                                    injection_exposes_neutral_input = True
                                else:
                                    pass

                    # An internal star-point ground does not connect the bus
                    # neutral. Only a neutral terminal (the external voltage
                    # mapping, or a legacy v_N input of an unregistered model)
                    # can declare that conductor connected to this injection.
                    if (has_emt_internal_grounding_link(block=inj_emt_model)
                            and ((injection_external_mapping is not None
                                  and injection_external_mapping.get(VarPowerFlowReferenceType.v_N, None) is not None)
                                 or injection_exposes_neutral_input)):
                        bus_phase_connections[(inj_bus, VarPowerFlowReferenceType.v_N)].add(
                            f"internal_ground:{inj.idtag}"
                        )
                    else:
                        pass
                else:
                    pass
            else:
                pass

        floating_phases: List[str] = list()
        for bus in self.grid.buses:
            if not bus.is_dc:
                bus_mdl = bus.emt_model
                bus_out_refs = {v.ref for v in bus_mdl.out_vars}
                for phase in ac_phases:
                    connections = bus_phase_connections.get((bus, phase), set())
                    if phase in bus_out_refs and len(connections) < 2:
                        floating_phases.append(
                            f"  - Bus '{bus.name}' phase '{phase.value}' is floating "
                            f"(connected to {len(connections)} element(s): {connections})"
                        )
                    else:
                        pass
            else:
                pass

        topology_error_sections: List[str] = list()
        if len(invalid_line_layouts) > 0:
            topology_error_sections.append(
                "TopologyError: Invalid EMT line terminal layouts detected:\n"
                + "\n".join(invalid_line_layouts)
            )
        else:
            pass

        if len(floating_phases) > 0:
            topology_error_sections.append(
                "TopologyError: Floating bus phases detected "
                "(each phase must be connected to at least 2 elements):\n"
                + "\n".join(floating_phases)
            )
        else:
            pass

        if len(topology_error_sections) > 0:
            raise EmtTopologyError("\n".join(topology_error_sections))
        else:
            pass

    def _validate_runtime_parameter_sources_after_power_flow(self) -> None:
        """Validate EMT runtime sources after operating-point seeding.

        EMT templates intentionally leave several event parameters undefined
        until the power-flow operating point is available. Running this check
        after the seed refresh avoids rejecting those valid placeholders while
        still stopping before the expensive symbolic/native initialization when
        a parameter has no source at all.

        :return: None.
        :raises ValueError: If a runtime parameter has no numerical, symbolic,
            device-mapped, power-flow, or retained-mode source.
        """
        parameter_index: int = 0
        parameter_count: int = len(self._variable_parameters)

        while parameter_index < parameter_count:
            parameter: Var = self._variable_parameters[parameter_index]
            declared_expression: Expr | Const = self._event_parameters_eqs[parameter_index]

            if isinstance(declared_expression, Const) and declared_expression.value is None:
                owner_block: Block | None = self._runtime_parameter_owner_blocks.get(parameter.uid, None)
                device: ALL_DEV_TYPES | None = self._runtime_parameter_devices.get(parameter.uid, None)

                if owner_block is None or device is None:
                    raise ValueError(
                        "Unresolved EMT dynamic parameter "
                        + f"'{parameter.name}' (uid={parameter.uid}): its Const(None) source is not associated "
                        + "with a device and owner block in the assembled EMT problem."
                    )
                else:
                    has_power_flow_seed: bool = (
                        parameter.uid in self._temp_init_guess
                        or parameter.uid in self._temp_post_init_guess
                        or parameter.uid in self.event_params_init_dict
                    )
                    has_procedural_owner: bool = False

                    # A procedural owner is relevant only for a retained mode
                    # that still lacks a PF/API seed. Avoid consulting the
                    # assembled runtime indices for ordinary parameters, which
                    # also keeps isolated validation fixtures independent from
                    # the complete numerical-problem construction sequence.
                    if has_power_flow_seed or parameter.uid not in self._runtime_mode_uids:
                        pass
                    else:
                        runtime_parameter_index: int | None = self.uid2idx_event_params.get(
                            parameter.uid,
                            None,
                        )
                        has_procedural_owner = (
                            runtime_parameter_index is not None
                            and self._block_boundary_updater is not None
                            and runtime_parameter_index
                            in self._block_boundary_updater.get_output_parameter_indices()
                        )
                    is_pseudo_transient_unknown: bool = (
                        self.options.initialization_method == EmtInitializationMethod.PseudoTransient
                        and any(
                            dependency.uid == parameter.uid
                            for block in device.emt_model.get_all_blocks()
                            for equation in block.state_eqs + block.algebraic_eqs
                            for dependency in equation.get_vars()
                        )
                    )
                    allow_deferred_initialization: bool = (
                        has_power_flow_seed
                        or is_pseudo_transient_unknown
                        or has_procedural_owner
                    )
                    resolve_runtime_parameter_initial_expression(
                        device=device,
                        simulation_mode=DynamicSimulationMode.EMT,
                        root_block=device.emt_model,
                        owner_block=owner_block,
                        parameter=parameter,
                        declared_expression=declared_expression,
                        problem_mapping=dict(),
                        allow_deferred_initialization=allow_deferred_initialization,
                    )
            else:
                pass

            parameter_index += 1

    def _process_device_model(self,
                              dev: ALL_DEV_TYPES,
                              mdl: Block,
                              sys_block: Block,
                              static_parameter_values_mapping: Dict[Var, Const]) -> Block:
        """
        Register a device EMT model into the global system block.

        The device model is flattened before being attached to the system block.
        Static parameters and API mappings remain owned by their declaring blocks;
        recursive processing discovers child-owned declarations without copying
        them to the wrapper root.

        :param dev: Device object from the grid.
        :param mdl: Device block.
        :param sys_block: Main DAE system block.
        :param static_parameter_values_mapping: Static parameter values already
            resolved from the device API mapping.
        :return: Unified device block.
        """
        resolved_external_mapping: Dict[Any, Var]
        parameter_owner_blocks: List[Block] = _collect_block_hierarchy(mdl)

        # Validate every static declaration before flattening. Repeated symbolic
        # UIDs are an invalid ownership contract and must not be deduplicated.
        declared_parameter_uids: set[int] = set()
        validation_block: Block
        constant_parameter: Var
        declared_constant: Const
        for validation_block in mdl.get_all_blocks():
            for constant_parameter, declared_constant in validation_block.parameters.items():
                if constant_parameter.uid in declared_parameter_uids:
                    raise ValueError(
                        f"EMT constant parameter '{constant_parameter.name}' (uid={constant_parameter.uid}) "
                        + "is declared more than once in the device block hierarchy."
                    )
                else:
                    resolve_constant_parameter_initial_value(
                        device=dev,
                        simulation_mode=DynamicSimulationMode.EMT,
                        root_block=mdl,
                        owner_block=validation_block,
                        parameter=constant_parameter,
                        declared_value=declared_constant,
                        problem_mapping=static_parameter_values_mapping,
                    )
                    declared_parameter_uids.add(constant_parameter.uid)

        # The external electrical interface is distinct from static parameter
        # ownership and is flattened for the later network-connection stage.
        resolved_external_mapping = _collect_external_mapping_from_block(mdl)
        device_disposition: str = self._get_device_emt_disposition(dev.device_type)
        terminal_refs: List[VarPowerFlowReferenceType] = list()
        if device_disposition == EmtDeviceDisposition.BRANCH_STRUCTURAL:
            terminal_refs = list((
                VarPowerFlowReferenceType.vf_N,
                VarPowerFlowReferenceType.vf_A,
                VarPowerFlowReferenceType.vf_B,
                VarPowerFlowReferenceType.vf_C,
                VarPowerFlowReferenceType.vt_N,
                VarPowerFlowReferenceType.vt_A,
                VarPowerFlowReferenceType.vt_B,
                VarPowerFlowReferenceType.vt_C,
                VarPowerFlowReferenceType.Vf_dc,
                VarPowerFlowReferenceType.Vt_dc,
                VarPowerFlowReferenceType.Vdc,
                VarPowerFlowReferenceType.v_N,
                VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.v_B,
                VarPowerFlowReferenceType.v_C,
            ))
        else:
            if device_disposition == EmtDeviceDisposition.INJECTION_STRUCTURAL:
                terminal_refs = list((
                    VarPowerFlowReferenceType.v_N,
                    VarPowerFlowReferenceType.v_A,
                    VarPowerFlowReferenceType.v_B,
                    VarPowerFlowReferenceType.v_C,
                    VarPowerFlowReferenceType.Vdc,
                ))
            else:
                pass

        # Resolve only the terminal portion of the already collected mapping.
        # Modern non-null mappings are authoritative. Legacy ``in_vars`` fill
        # individual missing terminals without modifying the persistent block.
        external_terminal_targets: Dict[VarPowerFlowReferenceType, Var] = dict()
        legacy_terminal_targets: Dict[VarPowerFlowReferenceType, Var] = dict()
        terminal_conflicts: List[str] = list()
        terminal_ref: VarPowerFlowReferenceType
        parameter_owner_block: Block

        for terminal_ref in terminal_refs:
            for parameter_owner_block in parameter_owner_blocks:
                owner_external_mapping: Dict[Any, Var] | None = parameter_owner_block.external_mapping
                external_target: Var | None
                if owner_external_mapping is None:
                    external_target = None
                else:
                    external_target = owner_external_mapping.get(terminal_ref, None)
                if external_target is not None:
                    previous_external_target: Var | None = external_terminal_targets.get(terminal_ref, None)
                    if previous_external_target is None:
                        external_terminal_targets[terminal_ref] = external_target
                    else:
                        if previous_external_target.uid == external_target.uid:
                            pass
                        else:
                            terminal_conflicts.append(
                                f"external_mapping reference '{terminal_ref.value}' targets both "
                                f"'{previous_external_target.name}' and '{external_target.name}'"
                            )
                else:
                    pass

        external_target_uids: Set[int] = set()
        external_target_var: Var
        for external_target_var in external_terminal_targets.values():
            external_target_uids.add(external_target_var.uid)

        for terminal_ref in terminal_refs:
            for parameter_owner_block in parameter_owner_blocks:
                block_external_mapping: Dict[Any, Var] | None = parameter_owner_block.external_mapping
                block_declares_modern_terminal: bool = bool(
                    block_external_mapping is not None
                    and block_external_mapping.get(terminal_ref, None) is not None
                )
                has_authoritative_modern_target: bool = terminal_ref in external_terminal_targets
                inspect_block_legacy_inputs: bool = bool(
                    not has_authoritative_modern_target
                    or block_declares_modern_terminal
                )
                if inspect_block_legacy_inputs:
                    legacy_in_var: Var
                    for legacy_in_var in parameter_owner_block.in_vars:
                        if legacy_in_var.ref == terminal_ref:
                            # A modern target may already have been rebound to a bus
                            # variable whose reference resembles another terminal.
                            # Do not re-export that same variable under a second key.
                            already_mapped_under_other_key: bool = (
                                legacy_in_var.uid in external_target_uids
                                and terminal_ref not in external_terminal_targets
                            )
                            if already_mapped_under_other_key:
                                pass
                            else:
                                previous_legacy_target: Var | None = legacy_terminal_targets.get(terminal_ref, None)
                                if previous_legacy_target is None:
                                    legacy_terminal_targets[terminal_ref] = legacy_in_var
                                else:
                                    if previous_legacy_target.uid == legacy_in_var.uid:
                                        pass
                                    else:
                                        terminal_conflicts.append(
                                            f"legacy input reference '{terminal_ref.value}' targets both "
                                            f"'{previous_legacy_target.name}' and '{legacy_in_var.name}'"
                                        )
                        else:
                            pass
                else:
                    pass

        for terminal_ref in terminal_refs:
            external_target = external_terminal_targets.get(terminal_ref, None)
            legacy_target: Var | None = legacy_terminal_targets.get(terminal_ref, None)
            if external_target is not None and legacy_target is not None:
                if external_target.uid == legacy_target.uid:
                    pass
                else:
                    terminal_conflicts.append(
                        f"reference '{terminal_ref.value}' maps to modern target "
                        f"'{external_target.name}' and incompatible legacy target '{legacy_target.name}'"
                    )
            else:
                pass

        if len(terminal_conflicts) > 0:
            conflict_message: str = (
                f"Conflicting EMT terminal mappings for device '{self._get_device_name(dev)}': "
                + "; ".join(terminal_conflicts)
            )
            if self.logger is not None:
                self.logger.add_error(
                    msg="Conflicting EMT terminal mappings.",
                    device=self._get_device_name(dev),
                    device_class=self._get_device_type_label(dev),
                    value="; ".join(terminal_conflicts),
                    expected_value="One compatible target per terminal reference",
                    device_property="emt_terminal_mapping",
                )
            else:
                pass
            raise EmtTopologyError(conflict_message)
        else:
            pass

        # Rebuild the local mapping with canonical terminal ordering, followed
        # by the untouched non-terminal PF initialization references.
        ordered_external_mapping: Dict[Any, Var] = dict()
        terminal_ref_set: Set[VarPowerFlowReferenceType] = set(terminal_refs)
        for terminal_ref in terminal_refs:
            external_target = external_terminal_targets.get(terminal_ref, None)
            legacy_target = legacy_terminal_targets.get(terminal_ref, None)
            if external_target is not None:
                ordered_external_mapping[terminal_ref] = external_target
            else:
                if legacy_target is not None:
                    ordered_external_mapping[terminal_ref] = legacy_target
                else:
                    pass

        mapping_key: Any
        mapping_value: Var
        for mapping_key, mapping_value in resolved_external_mapping.items():
            if mapping_key in terminal_ref_set:
                pass
            else:
                ordered_external_mapping[mapping_key] = mapping_value

        resolved_external_mapping = _sanitize_external_mapping_for_explicit_dc_terminals(
            ordered_external_mapping
        )
        self._local_external_mapping_by_block_uid[mdl.uid] = resolved_external_mapping

        # Preserve device and block ownership until PF-derived runtime values have
        # been applied. The later validation can then explain exactly which model
        # contract left a placeholder unresolved.
        runtime_parameter: Var
        for parameter_owner_block in parameter_owner_blocks:
            for runtime_parameter in parameter_owner_block.event_dict.keys():
                self._runtime_parameter_owner_blocks[runtime_parameter.uid] = parameter_owner_block
                self._runtime_parameter_devices[runtime_parameter.uid] = dev

            for runtime_parameter in parameter_owner_block.mode_dict.keys():
                self._runtime_parameter_owner_blocks[runtime_parameter.uid] = parameter_owner_block
                self._runtime_parameter_devices[runtime_parameter.uid] = dev

        # Register runtime-updatable EMT parameters declared by the device block.
        # EMT runtime events are no longer baked into the symbolic model during the
        # parsing phase. Instead, the problem stores the event-capable parameters and
        # later activates the selected EMT event group through ``set_events_group()``.
        if not mdl.event_dict and not mdl.mode_dict:
            # Wrapper roots may keep all runtime parameters inside nested child
            # blocks, so the registration pass must still inspect the full
            # hierarchy before deciding that nothing needs to be registered.
            for parameter_owner_block in parameter_owner_blocks:
                if parameter_owner_block is mdl:
                    pass
                else:
                    for parameter in parameter_owner_block.event_dict.keys():
                        self._event_parameter_device_idtags[parameter.uid] = dev.idtag
                        self._event_parameter_name_lookup[(str(dev.idtag), str(parameter.name))] = parameter.uid
                        self._continuous_event_parameter_uids.add(parameter.uid)

                    for parameter in parameter_owner_block.mode_dict.keys():
                        self._event_parameter_device_idtags[parameter.uid] = dev.idtag
                        self._event_parameter_name_lookup[(str(dev.idtag), str(parameter.name))] = parameter.uid
                        self._discrete_event_parameter_uids.add(parameter.uid)
        else:
            for parameter in mdl.event_dict.keys():
                self._event_parameter_device_idtags[parameter.uid] = dev.idtag
                self._event_parameter_name_lookup[(str(dev.idtag), str(parameter.name))] = parameter.uid
                self._continuous_event_parameter_uids.add(parameter.uid)

            for parameter in mdl.mode_dict.keys():
                self._event_parameter_device_idtags[parameter.uid] = dev.idtag
                self._event_parameter_name_lookup[(str(dev.idtag), str(parameter.name))] = parameter.uid
                self._discrete_event_parameter_uids.add(parameter.uid)

            # Child blocks may define additional runtime parameters that are
            # not re-exported on the wrapper root. Those nested parameters
            # must also be registered so later EMT event activation and
            # runtime seeding can find them by UID and by device/name.
            for parameter_owner_block in parameter_owner_blocks:
                if parameter_owner_block is mdl:
                    pass
                else:
                    for parameter in parameter_owner_block.event_dict.keys():
                        self._event_parameter_device_idtags[parameter.uid] = dev.idtag
                        self._event_parameter_name_lookup[(str(dev.idtag), str(parameter.name))] = parameter.uid
                        self._continuous_event_parameter_uids.add(parameter.uid)

                    for parameter in parameter_owner_block.mode_dict.keys():
                        self._event_parameter_device_idtags[parameter.uid] = dev.idtag
                        self._event_parameter_name_lookup[(str(dev.idtag), str(parameter.name))] = parameter.uid
                        self._discrete_event_parameter_uids.add(parameter.uid)

        # Add model to system mappings
        # Populates tracking dictionaries to maintain the relationship between
        # electrical devices and their corresponding symbolic variables.
        block_item: Block
        for block_item in mdl.get_all_blocks():
            v: Var
            for v in block_item.state_vars:
                existing_device: ALL_DEV_TYPES | None = self._vars2device.get(v.uid, None)
                if existing_device is dev:
                    pass
                elif existing_device is None:
                    self.add_device_var(dev=dev, var=v)
                    self._vars_glob_name2uid[v.name + dev.name] = v.uid
                    self._vars2device[v.uid] = dev
                else:
                    pass

            for v in block_item.algebraic_vars:
                existing_device = self._vars2device.get(v.uid, None)
                if existing_device is dev:
                    pass
                elif existing_device is None:
                    self.add_device_var(dev=dev, var=v)
                    self._vars_glob_name2uid[v.name + dev.name] = v.uid
                    self._vars2device[v.uid] = dev
                else:
                    pass

            dv: Var
            for dv in block_item.diff_vars:
                existing_device = self._vars2device.get(dv.uid, None)
                if existing_device is dev:
                    pass
                elif existing_device is None:
                    self.add_device_var(dev=dev, var=dv)
                    self._vars_glob_name2uid[dv.name + dev.name] = dv.uid
                    self._vars2device[dv.uid] = dev
                else:
                    pass

        queue_emt_fmu_cs_device(self, dev, mdl)
        queue_emt_fmu_me_device(self, dev, mdl)

        sys_block.add(mdl)

        self._register_init_model(mdl)
        if not isinstance(dev, Bus):
            self._device_models_for_ptc.append(mdl)
        # self._register_diff_init_model(mdl)

        return mdl

    def _assign_event_mapping_value_if_present(self,
                                               mdl: Block,
                                               key: ParamPowerFlowReferenceType,
                                               value: float,
                                               ) -> None:
        """
        Assign one runtime/event parameter exposed through ``api_obj_mapping``.

        Some higher-level EMT wrappers expose PF-derived sharing targets through
        ``api_obj_mapping`` even though the actual parameter lives in
        ``event_dict``. Those values must be seeded on the runtime side before
        explicit initialization, but they must not pass through the static API
        assignment helper.

        :param mdl: EMT model block.
        :param key: API mapping reference key.
        :param value: Runtime value to assign.
        :return: None.
        """
        mapping_block: Block
        owner_block: Optional[Block]
        target: Any | None

        # Runtime initialization follows the same local-ownership traversal as
        # static mapping. A parent block does not need to copy a child mapping.
        for mapping_block in mdl.get_all_blocks():
            target = mapping_block.api_obj_mapping.get(key, None)
            if target is None:
                pass
            else:
                if isinstance(target, Var):
                    # The mapped runtime parameter may live in a nested child
                    # block. Ownership is validated on the hierarchy, but the
                    # resolved value is stored only by the numerical problem.
                    owner_block = _find_event_var_owner(mdl, target)
                    if owner_block is None:
                        pass
                    else:
                        # During structural collection the flat arrays do not
                        # exist yet, so the problem-local temporary seed is the
                        # durable hand-off to post-construction initialization.
                        self._set_runtime_parameter_seed_by_uid(
                            uid=target.uid,
                            value=float(value),
                            persist_after_native_init=False,
                        )
                else:
                    pass

    def _build_emt_bus_working_models(self, grid: MultiCircuit) -> Dict[Any, Block]:
        """
        Build the local EMT bus-shell working models.

        This mirrors the explicit bus initialization stage used by RMS. The EMT
        builder first copies the already validated canonical bus shells, and only
        afterwards processes branch and injection devices against those
        authoritative bus voltage variables.

        :param grid: Network model to assemble.
        :return: Mapping from bus objects to local working bus blocks.
        """
        bus_working_models: Dict[Any, Block] = dict()
        bus: Any

        for bus in grid.buses:
            bus_model: Block = bus.emt_model
            bus_working_models[bus] = Block(
                algebraic_vars=list(bus_model.algebraic_vars),
                out_vars=list(bus_model.out_vars),
                external_mapping=dict(bus_model.external_mapping),
                api_obj_mapping=dict(bus_model.api_obj_mapping),
            )

        return bus_working_models

    def _build_emt_branch_device(self,
                                 grid: MultiCircuit,
                                 sys_block: Block,
                                 branch: Any,
                                 branch_index: int,
                                 pf_branch_index: int,
                                 bus_dict: Dict[Any, int],
                                 bus_working_models: Dict[Any, Block],
                                 i_kcl: Dict[int, List[Any]],
                                 voltage_connection_substitution: Dict[Var, Var],
                                 static_parameter_values_mapping: Dict[Var, Const],
                                 ph_v_keys: List[VarPowerFlowReferenceType],
                                 inj_i_keys: List[VarPowerFlowReferenceType],
                                 br_if_keys: List[VarPowerFlowReferenceType],
                                 br_it_keys: List[VarPowerFlowReferenceType],
                                 br_vf_keys: List[VarPowerFlowReferenceType],
                                 br_vt_keys: List[VarPowerFlowReferenceType],
                                 vsc_idx_dict: Dict[str, int],
                                 h: float,
                                 sbase: float,
                                 fbase: float) -> int:
        """
        Build one EMT branch device and merge it into the nodal structure.

        :param grid: Network model.
        :param sys_block: Global EMT system block.
        :param branch: Branch device to process.
        :param branch_index: Branch loop index.
        :param pf_branch_index: Current PF branch index.
        :param bus_dict: Bus to index mapping.
        :param bus_working_models: Local bus working models.
        :param i_kcl: KCL accumulators.
        :param voltage_connection_substitution: Voltage substitution map.
        :param static_parameter_values_mapping: Static parameter mapping.
        :param ph_v_keys: AC bus voltage keys.
        :param inj_i_keys: Shared AC current keys.
        :param br_if_keys: From-side branch current keys.
        :param br_it_keys: To-side branch current keys.
        :param br_vf_keys: From-side branch voltage keys.
        :param br_vt_keys: To-side branch voltage keys.
        :param vsc_idx_dict: VSC idtag to PF index mapping.
        :param h: EMT time step.
        :param sbase: System base power.
        :param fbase: System base frequency.
        :return: Updated PF branch index.
        """
        disposition: str = self._get_device_emt_disposition(branch.device_type)

        if disposition == EmtDeviceDisposition.BRANCH_STRUCTURAL:
            pass
        else:
            return pf_branch_index

        f: int = bus_dict[branch.bus_from]
        t: int = bus_dict[branch.bus_to]
        br_working_mdl: Block = branch.emt_model
        assign_static_api_object_mapping_for_device(
            grid=grid,
            device=branch,
            mdl=br_working_mdl,
            problem_mapping=static_parameter_values_mapping,
            logger=self._static_parameter_mapping_diagnostics,
        )

        if branch.device_type == DeviceType.VscDevice:
            for key, value in (
                    (ParamPowerFlowReferenceType.converter_control_mode_1, converter_control_code(branch.control1)),
                    (ParamPowerFlowReferenceType.converter_control_mode_2, converter_control_code(branch.control2)),
                    (ParamPowerFlowReferenceType.converter_control_target_1, float(branch.control1_val)),
                    (ParamPowerFlowReferenceType.converter_control_target_2, float(branch.control2_val)),
            ):
                self._assign_event_mapping_value_if_present(
                    mdl=br_working_mdl,
                    key=key,
                    value=value,
                )

        # Instantaneous line waves belong to this problem, so their declarations
        # must exist before canonical registration discovers variables and seeds.
        is_bergeron: bool
        is_jmarti: bool
        is_bergeron, is_jmarti = _is_history_runtime_line_block_name(br_working_mdl.name)
        jmarti_runtime: JMartiHistoryRuntime | None = None
        if isinstance(branch, Line) and is_jmarti:
            jmarti_runtime = JMartiHistoryRuntime(line=branch, line_block=br_working_mdl, h=h)
            jmarti_runtime.bind_terminals(
                _get_bus_v_list(bus_block=bus_working_models[branch.bus_from], ph_v_keys=ph_v_keys),
                _get_bus_v_list(bus_block=bus_working_models[branch.bus_to], ph_v_keys=ph_v_keys),
            )
        else:
            pass

        mdl: Block = self._process_device_model(
            dev=branch,
            mdl=br_working_mdl,
            sys_block=sys_block,
            static_parameter_values_mapping=static_parameter_values_mapping,
        )
        if jmarti_runtime is None:
            pass
        else:
            companion: Block | None = jmarti_runtime.coupling_block
            if companion is None:
                pass
            else:
                # Register through the same device owner without attaching the
                # companion to the saved line model or the source VarFactory.
                self._process_device_model(
                    dev=branch,
                    mdl=companion,
                    sys_block=sys_block,
                    static_parameter_values_mapping=static_parameter_values_mapping,
                )
        is_vsc: bool = branch.device_type == DeviceType.VscDevice
        uses_branch_pf_slot: bool = branch.device_type not in {DeviceType.VscDevice, DeviceType.HVDCLineDevice}
        current_pf_branch_index: int = pf_branch_index
        vsc_index: int = vsc_idx_dict.get(branch.idtag, -1)

        if uses_branch_pf_slot:
            pf_branch_index += 1
        else:
            pass

        self._build_branch_device_by_type(
            grid=grid,
            branch=branch,
            mdl=mdl,
            f=f,
            t=t,
            current_pf_branch_index=current_pf_branch_index,
            bus_working_models=bus_working_models,
            i_kcl=i_kcl,
            voltage_connection_substitution=voltage_connection_substitution,
            ph_v_keys=ph_v_keys,
            inj_i_keys=inj_i_keys,
            br_if_keys=br_if_keys,
            br_it_keys=br_it_keys,
            br_vf_keys=br_vf_keys,
            br_vt_keys=br_vt_keys,
            is_vsc=is_vsc,
            vsc_index=vsc_index,
            h=h,
            sbase=sbase,
            fbase=fbase,
            is_bergeron=is_bergeron,
            is_jmarti=is_jmarti,
            static_parameter_values_mapping=static_parameter_values_mapping,
            jmarti_runtime=jmarti_runtime,
        )

        if branch_index >= 0:
            pass
        else:
            pass

        return pf_branch_index

    def _build_branch_device_by_type(self,
                                     grid: MultiCircuit,
                                     branch: Any,
                                     mdl: Block,
                                     f: int,
                                     t: int,
                                     current_pf_branch_index: int,
                                     bus_working_models: Dict[Any, Block],
                                     i_kcl: Dict[int, List[Any]],
                                     voltage_connection_substitution: Dict[Var, Var],
                                     ph_v_keys: List[VarPowerFlowReferenceType],
                                     inj_i_keys: List[VarPowerFlowReferenceType],
                                     br_if_keys: List[VarPowerFlowReferenceType],
                                     br_it_keys: List[VarPowerFlowReferenceType],
                                     br_vf_keys: List[VarPowerFlowReferenceType],
                                     br_vt_keys: List[VarPowerFlowReferenceType],
                                     is_vsc: bool,
                                     vsc_index: int,
                                     h: float,
                                     sbase: float,
                                     fbase: float,
                                     is_bergeron: bool,
                                     is_jmarti: bool,
                                     static_parameter_values_mapping: Dict[Var, Const],
                                     jmarti_runtime: JMartiHistoryRuntime | None) -> None:
        """
        Dispatch one branch build to the explicit ``DeviceType`` implementation.

        :param grid: Network model.
        :param branch: Branch device.
        :param mdl: Registered working model.
        :param f: From-bus index.
        :param t: To-bus index.
        :param current_pf_branch_index: PF branch index.
        :param bus_working_models: Local bus working models.
        :param i_kcl: KCL accumulators.
        :param voltage_connection_substitution: Voltage substitution map.
        :param ph_v_keys: AC bus voltage keys.
        :param inj_i_keys: Shared AC current keys.
        :param br_if_keys: From-side current keys.
        :param br_it_keys: To-side current keys.
        :param br_vf_keys: From-side voltage keys.
        :param br_vt_keys: To-side voltage keys.
        :param is_vsc: Whether the branch is a VSC.
        :param vsc_index: VSC PF index.
        :param h: EMT time step.
        :param sbase: System base power.
        :param fbase: System base frequency.
        :param is_bergeron: Whether the line model is Bergeron.
        :param is_jmarti: Whether the line model is JMarti.
        :param static_parameter_values_mapping: Owner-resolved static constants for PF seeding.
        :param jmarti_runtime: The line runtime already registered before indexing,
            or ``None`` for other branch implementations.
        :return: None.
        """
        if branch.device_type == DeviceType.LineDevice:
            if is_bergeron or is_jmarti:
                self._build_history_branch_device(
                    grid=grid,
                    branch=branch,
                    mdl=mdl,
                    f=f,
                    t=t,
                    current_pf_branch_index=current_pf_branch_index,
                    bus_working_models=bus_working_models,
                    i_kcl=i_kcl,
                    ph_v_keys=ph_v_keys,
                    h=h,
                    sbase=sbase,
                    fbase=fbase,
                    is_bergeron=is_bergeron,
                    jmarti_runtime=jmarti_runtime,
                )
            else:
                self._build_generic_branch_device(
                    grid=grid,
                    branch=branch,
                    mdl=mdl,
                    f=f,
                    t=t,
                    current_pf_branch_index=current_pf_branch_index,
                    bus_working_models=bus_working_models,
                    i_kcl=i_kcl,
                    voltage_connection_substitution=voltage_connection_substitution,
                    inj_i_keys=list(),
                    br_if_keys=br_if_keys,
                    br_it_keys=br_it_keys,
                    br_vf_keys=br_vf_keys,
                    br_vt_keys=br_vt_keys,
                    is_vsc=False,
                    vsc_index=-1,
                    sbase=sbase,
                    static_parameter_values_mapping=static_parameter_values_mapping,
                )
        else:
            if branch.device_type == DeviceType.Transformer2WDevice:
                self._build_generic_branch_device(
                    grid=grid,
                    branch=branch,
                    mdl=mdl,
                    f=f,
                    t=t,
                    current_pf_branch_index=current_pf_branch_index,
                    bus_working_models=bus_working_models,
                    i_kcl=i_kcl,
                    voltage_connection_substitution=voltage_connection_substitution,
                    inj_i_keys=list(),
                    br_if_keys=br_if_keys,
                    br_it_keys=br_it_keys,
                    br_vf_keys=br_vf_keys,
                    br_vt_keys=br_vt_keys,
                    is_vsc=False,
                    vsc_index=-1,
                    sbase=sbase,
                    static_parameter_values_mapping=static_parameter_values_mapping,
                )
            else:
                if branch.device_type == DeviceType.SeriesReactanceDevice:
                    self._build_generic_branch_device(
                        grid=grid,
                        branch=branch,
                        mdl=mdl,
                        f=f,
                        t=t,
                        current_pf_branch_index=current_pf_branch_index,
                        bus_working_models=bus_working_models,
                        i_kcl=i_kcl,
                        voltage_connection_substitution=voltage_connection_substitution,
                        inj_i_keys=list(),
                        br_if_keys=br_if_keys,
                        br_it_keys=br_it_keys,
                        br_vf_keys=br_vf_keys,
                        br_vt_keys=br_vt_keys,
                        is_vsc=False,
                        vsc_index=-1,
                        sbase=sbase,
                        static_parameter_values_mapping=static_parameter_values_mapping,
                    )
                else:
                    if branch.device_type == DeviceType.SwitchDevice:
                        self._build_generic_branch_device(
                            grid=grid,
                            branch=branch,
                            mdl=mdl,
                            f=f,
                            t=t,
                            current_pf_branch_index=current_pf_branch_index,
                            bus_working_models=bus_working_models,
                            i_kcl=i_kcl,
                            voltage_connection_substitution=voltage_connection_substitution,
                            inj_i_keys=list(),
                            br_if_keys=br_if_keys,
                            br_it_keys=br_it_keys,
                            br_vf_keys=br_vf_keys,
                            br_vt_keys=br_vt_keys,
                            is_vsc=False,
                            vsc_index=-1,
                            sbase=sbase,
                            static_parameter_values_mapping=static_parameter_values_mapping,
                        )
                    else:
                        if branch.device_type == DeviceType.DCLineDevice:
                            self._build_generic_branch_device(
                                grid=grid,
                                branch=branch,
                                mdl=mdl,
                                f=f,
                                t=t,
                                current_pf_branch_index=current_pf_branch_index,
                                bus_working_models=bus_working_models,
                                i_kcl=i_kcl,
                                voltage_connection_substitution=voltage_connection_substitution,
                                inj_i_keys=list(),
                                br_if_keys=br_if_keys,
                                br_it_keys=br_it_keys,
                                br_vf_keys=br_vf_keys,
                                br_vt_keys=br_vt_keys,
                                is_vsc=False,
                                vsc_index=-1,
                                sbase=sbase,
                                static_parameter_values_mapping=static_parameter_values_mapping,
                            )
                        else:
                            if branch.device_type == DeviceType.HVDCLineDevice:
                                self._build_generic_branch_device(
                                    grid=grid,
                                    branch=branch,
                                    mdl=mdl,
                                    f=f,
                                    t=t,
                                    current_pf_branch_index=current_pf_branch_index,
                                    bus_working_models=bus_working_models,
                                    i_kcl=i_kcl,
                                    voltage_connection_substitution=voltage_connection_substitution,
                                    inj_i_keys=list(),
                                    br_if_keys=br_if_keys,
                                    br_it_keys=br_it_keys,
                                    br_vf_keys=br_vf_keys,
                                    br_vt_keys=br_vt_keys,
                                    is_vsc=False,
                                    vsc_index=-1,
                                    sbase=sbase,
                                    static_parameter_values_mapping=static_parameter_values_mapping,
                                )
                            else:
                                if branch.device_type == DeviceType.VscDevice:
                                    self._build_generic_branch_device(
                                        grid=grid,
                                        branch=branch,
                                        mdl=mdl,
                                        f=f,
                                        t=t,
                                        current_pf_branch_index=current_pf_branch_index,
                                        bus_working_models=bus_working_models,
                                        i_kcl=i_kcl,
                                        voltage_connection_substitution=voltage_connection_substitution,
                                        inj_i_keys=inj_i_keys,
                                        br_if_keys=br_if_keys,
                                        br_it_keys=br_it_keys,
                                        br_vf_keys=br_vf_keys,
                                        br_vt_keys=br_vt_keys,
                                        is_vsc=True,
                                        vsc_index=vsc_index,
                                        sbase=sbase,
                                        static_parameter_values_mapping=static_parameter_values_mapping,
                                    )
                                else:
                                    self._build_generic_branch_device(
                                        grid=grid,
                                        branch=branch,
                                        mdl=mdl,
                                        f=f,
                                        t=t,
                                        current_pf_branch_index=current_pf_branch_index,
                                        bus_working_models=bus_working_models,
                                        i_kcl=i_kcl,
                                        voltage_connection_substitution=voltage_connection_substitution,
                                        inj_i_keys=inj_i_keys,
                                        br_if_keys=br_if_keys,
                                        br_it_keys=br_it_keys,
                                        br_vf_keys=br_vf_keys,
                                        br_vt_keys=br_vt_keys,
                                        is_vsc=is_vsc,
                                        vsc_index=vsc_index,
                                        sbase=sbase,
                                        static_parameter_values_mapping=static_parameter_values_mapping,
                                    )

    def _build_history_branch_device(self,
                                     grid: MultiCircuit,
                                     branch: Any,
                                     mdl: Block,
                                     f: int,
                                     t: int,
                                     current_pf_branch_index: int,
                                     bus_working_models: Dict[Any, Block],
                                     i_kcl: Dict[int, List[Any]],
                                     ph_v_keys: List[VarPowerFlowReferenceType],
                                     h: float,
                                     sbase: float,
                                     fbase: float,
                                     is_bergeron: bool,
                                     jmarti_runtime: JMartiHistoryRuntime | None) -> None:
        """
        Build one history-based line branch device.

        :param grid: Network model.
        :param branch: Branch device.
        :param mdl: Registered working model.
        :param f: From-bus index.
        :param t: To-bus index.
        :param current_pf_branch_index: PF branch index.
        :param bus_working_models: Local bus working models.
        :param i_kcl: KCL accumulators.
        :param ph_v_keys: AC bus voltage keys.
        :param h: EMT time step.
        :param sbase: System base power.
        :param fbase: System base frequency.
        :param is_bergeron: ``True`` for Bergeron, ``False`` for JMarti.
        :param jmarti_runtime: The pre-index JMARTI runtime; Bergeron does not use it.
        :return: None.
        """
        v_f_vars: List[Any] = _get_bus_v_list(bus_block=bus_working_models[branch.bus_from], ph_v_keys=ph_v_keys)
        v_t_vars: List[Any] = _get_bus_v_list(bus_block=bus_working_models[branch.bus_to], ph_v_keys=ph_v_keys)
        rt: BergeronHistoryRuntime | JMartiHistoryRuntime

        if is_bergeron:
            rt = BergeronHistoryRuntime(line=branch, line_block=mdl, h=h, sbase=sbase, fbase=fbase)
            rt.bind_terminals(v_f_vars, v_t_vars)
        elif jmarti_runtime is None:
            raise ValueError("JMARTI runtime must be registered before building its network currents.")
        else:
            rt = jmarti_runtime

        if self.power_flow_results_3ph is not None or self.power_flow_results is not None:
            if self.power_flow_results_3ph is None and self.options.verbose:
                model_name = "Bergeron" if is_bergeron else "JMARTI"
                print(f"Initializing {model_name} line variables assuming a balanced power flow")
            if is_bergeron:
                self._try_set_bergeron_pf_init(rt=rt, branch_index=current_pf_branch_index, f_bus_idx=f, t_bus_idx=t, sbase=grid.Sbase)
            else:
                self._try_set_jmarti_pf_init(rt=rt, branch_index=current_pf_branch_index, f_bus_idx=f, t_bus_idx=t, sbase=grid.Sbase)
        elif self.options.verbose:
            print("No Power Flow results given.")

        if isinstance(rt, JMartiHistoryRuntime) and rt.coupling_block is not None:
            # Both PF providers have now initialized the same physical runtime.
            # Seed the problem-owned waves and offsets once in this common path.
            if rt.initial_source_available:
                pass
            elif self.logger is None:
                pass
            else:
                self.logger.add_warning(
                    msg="JMARTI phase initialization source is incomplete; using zero numerical history.",
                    device=branch.name,
                    value="Missing PF/PF3 phase voltages or terminal powers",
                    expected_value="Complete voltage/current source; zero history is a runtime fallback",
                )
            wave_groups: tuple[List[Var], ...] = (
                rt.outgoing_wave_f_re, rt.outgoing_wave_t_re,
                rt.outgoing_wave_f_im, rt.outgoing_wave_t_im,
            )
            offset_groups: tuple[List[Var], ...] = (
                rt.incoming_voltage_f_re, rt.incoming_voltage_t_re,
                rt.incoming_voltage_f_im, rt.incoming_voltage_t_im,
            )
            group_index: int
            group_vars: List[Var]
            phase_index: int
            wave_var: Var
            wave_value: complex
            offset_value: complex
            wave_seed: float
            offset_seed: float
            if rt.initial_source_available:
                pass
            else:
                # The cold-history fallback must pass through the same retained
                # parameter stores as a PF seed, before native initialization.
                # It remains numerical runtime state, without a physical cache.
                for phase_index in range(rt.m):
                    self._set_runtime_parameter_seed_by_uid(
                        uid=rt.Ih_f[phase_index].uid,
                        value=0.0,
                        persist_after_native_init=True,
                    )
                    self._set_runtime_parameter_seed_by_uid(
                        uid=rt.Ih_t[phase_index].uid,
                        value=0.0,
                        persist_after_native_init=True,
                    )
            for group_index, group_vars in enumerate(wave_groups):
                for phase_index, wave_var in enumerate(group_vars):
                    wave_value = complex(rt.initial_phase_waves[group_index % 2, phase_index])
                    offset_value = complex(rt.initial_voltage_offsets[group_index % 2, phase_index])
                    if group_index < 2:
                        wave_seed = float(wave_value.real)
                        offset_seed = float(offset_value.real)
                    else:
                        wave_seed = float(wave_value.imag)
                        offset_seed = float(offset_value.imag)
                    self._temp_init_guess[wave_var.uid] = wave_seed
                    self._temp_post_init_guess[wave_var.uid] = wave_seed
                    self._set_runtime_parameter_seed_by_uid(
                        uid=offset_groups[group_index][phase_index].uid,
                        value=offset_seed,
                        persist_after_native_init=True,
                    )
        else:
            pass

        i_f_exprs: List[Any]
        i_t_exprs: List[Any]
        i_f_exprs, i_t_exprs = rt.get_nodal_injections()
        ph: int = 0

        while ph < 4:
            if i_f_exprs[ph] is not None:
                i_kcl[f][ph] = i_kcl[f][ph] - i_f_exprs[ph]
            else:
                pass

            if i_t_exprs[ph] is not None:
                i_kcl[t][ph] = i_kcl[t][ph] - i_t_exprs[ph]
            else:
                pass

            ph += 1

        self.history_models.append(rt)

    def _build_generic_branch_device(self,
                                     grid: MultiCircuit,
                                     branch: Any,
                                     mdl: Block,
                                     f: int,
                                     t: int,
                                     current_pf_branch_index: int,
                                     bus_working_models: Dict[Any, Block],
                                     i_kcl: Dict[int, List[Any]],
                                     voltage_connection_substitution: Dict[Var, Var],
                                     inj_i_keys: List[VarPowerFlowReferenceType],
                                     br_if_keys: List[VarPowerFlowReferenceType],
                                     br_it_keys: List[VarPowerFlowReferenceType],
                                     br_vf_keys: List[VarPowerFlowReferenceType],
                                     br_vt_keys: List[VarPowerFlowReferenceType],
                                     is_vsc: bool,
                                     vsc_index: int,
                                     sbase: float,
                                     static_parameter_values_mapping: Dict[Var, Const]) -> None:
        """
        Build one non-history branch device.

        :param grid: Network model.
        :param branch: Branch device.
        :param mdl: Registered working model.
        :param f: From-bus index.
        :param t: To-bus index.
        :param current_pf_branch_index: PF branch index.
        :param bus_working_models: Local bus working models.
        :param i_kcl: KCL accumulators.
        :param voltage_connection_substitution: Voltage substitution map.
        :param inj_i_keys: Shared AC current keys.
        :param br_if_keys: From-side current keys.
        :param br_it_keys: To-side current keys.
        :param br_vf_keys: From-side voltage keys.
        :param br_vt_keys: To-side voltage keys.
        :param is_vsc: Whether the branch is a VSC device.
        :param vsc_index: VSC PF index.
        :param sbase: System base power.
        :param static_parameter_values_mapping: Owner-resolved static constants for PF seeding.
        :return: None.
        """
        effective_external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(
            problem=self,
            mdl=mdl,
        )
        assemble_emt_mapped_current_references(
            model=mdl,
            current_balance=i_kcl,
            effective_external_mapping=effective_external_mapping,
            bus_from_index=f,
            bus_to_index=t,
            bus_from_is_dc=branch.bus_from.is_dc,
            bus_to_is_dc=branch.bus_to.is_dc,
        )

        self._connect_branch_terminal_voltages(
            branch=branch,
            mdl=mdl,
            bus_working_models=bus_working_models,
            voltage_connection_substitution=voltage_connection_substitution,
            br_vf_keys=br_vf_keys,
            br_vt_keys=br_vt_keys,
        )

        if self.power_flow_results_3ph is not None or self.power_flow_results is not None:
            if self.power_flow_results_3ph is None and self.options.verbose:
                print("Initializing branch variables assuming a balanced power flow")
            if is_vsc and vsc_index >= 0:
                self._try_set_vsc_branch_pf_init(mdl=mdl, f_bus_idx=f, t_bus_idx=t, sbase=sbase, vsc_index=vsc_index)
            else:
                self._try_set_branch_pf_init(
                    mdl=mdl, branch=branch, branch_index=current_pf_branch_index,
                    f_bus_idx=f, t_bus_idx=t, sbase=grid.Sbase,
                    static_parameter_values_mapping=static_parameter_values_mapping,
                )
        elif self.options.verbose:
            print("No Power Flow results given.")

    def _connect_branch_terminal_voltages(self,
                                          branch: Any,
                                          mdl: Block,
                                          bus_working_models: Dict[Any, Block],
                                          voltage_connection_substitution: Dict[Var, Var],
                                          br_vf_keys: List[VarPowerFlowReferenceType],
                                          br_vt_keys: List[VarPowerFlowReferenceType]) -> None:
        """
        Bind branch terminal voltage inputs to the authoritative bus-shell voltages.

        :param branch: Branch device.
        :param mdl: Registered working model.
        :param bus_working_models: Local bus working models.
        :param voltage_connection_substitution: Voltage substitution map.
        :param br_vf_keys: From-side voltage keys.
        :param br_vt_keys: To-side voltage keys.
        :return: None.
        """
        terminal_buses: List[Any] = list([branch.bus_from, branch.bus_to])
        terminal_voltage_keys: List[List[VarPowerFlowReferenceType]] = list([br_vf_keys, br_vt_keys])
        term_idx: int = 0

        while term_idx < 2:
            terminal_bus: Any = terminal_buses[term_idx]
            terminal_keys: List[VarPowerFlowReferenceType] = terminal_voltage_keys[term_idx]
            external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(
                problem=self,
                mdl=mdl,
            )

            if terminal_bus.is_dc:
                v_dc: Any
                v_dc, _, _, _ = get_bus_emt_algebraic_vars(bus_working_models[terminal_bus])

                if external_mapping is not None:
                    dc_voltage_key: VarPowerFlowReferenceType = VarPowerFlowReferenceType.Vf_dc if term_idx == 0 else VarPowerFlowReferenceType.Vt_dc
                    mapped_var: Optional[Var] = external_mapping.get(dc_voltage_key, None)
                    if mapped_var is None:
                        mapped_var = external_mapping.get(VarPowerFlowReferenceType.Vdc, None)
                    else:
                        pass

                    if mapped_var is not None:
                        if _mapped_var_already_matches_target(mapped_var=mapped_var, target_var=v_dc):
                            pass
                        else:
                            voltage_connection_substitution[mapped_var] = v_dc
                    else:
                        pass
                else:
                    pass
            else:
                v_n: Any
                v_a: Any
                v_b: Any
                v_c: Any
                v_n, v_a, v_b, v_c = get_bus_emt_algebraic_vars(bus_working_models[terminal_bus])
                terminal_voltage_vars: List[Any] = list([v_n, v_a, v_b, v_c])

                if external_mapping is not None:
                    ph: int = 0
                    while ph < 4:
                        mapped_var = external_mapping.get(terminal_keys[ph], None)
                        terminal_voltage_var = terminal_voltage_vars[ph]

                        if mapped_var is not None and terminal_voltage_var is not None:
                            if _mapped_var_already_matches_target(mapped_var=mapped_var,
                                                                 target_var=terminal_voltage_var):
                                pass
                            else:
                                voltage_connection_substitution[mapped_var] = terminal_voltage_var
                        else:
                            pass

                        ph += 1
                else:
                    pass

            term_idx += 1

    def _build_emt_injection_device(self,
                                    grid: MultiCircuit,
                                    sys_block: Block,
                                    injection: Any,
                                    injection_index: int,
                                    bus_dict: Dict[Any, int],
                                    bus_working_models: Dict[Any, Block],
                                    i_kcl: Dict[int, List[Any]],
                                    voltage_connection_substitution: Dict[Var, Var],
                                    static_parameter_values_mapping: Dict[Var, Const],
                                    ph_v_keys: List[VarPowerFlowReferenceType],
                                    inj_i_keys: List[VarPowerFlowReferenceType],
                                    seed_store: Optional[EmtInjectionOperatingPoint],
                                    generator_battery_count_same_bus: Dict[int, int]) -> None:
        """
        Build one EMT injection device and merge it into the nodal structure.

        :param grid: Network model.
        :param sys_block: Global EMT system block.
        :param injection: Injection device to process.
        :param injection_index: Injection loop index.
        :param bus_dict: Bus to index mapping.
        :param bus_working_models: Local bus working models.
        :param i_kcl: KCL accumulators.
        :param voltage_connection_substitution: Voltage substitution map.
        :param static_parameter_values_mapping: Static parameter mapping.
        :param ph_v_keys: AC bus voltage keys.
        :param inj_i_keys: Injection current keys.
        :param seed_store: Precomputed injection seed store.
        :param generator_battery_count_same_bus: Number of generators and batteries per bus.
        :return: None.
        """
        disposition: str = self._get_device_emt_disposition(injection.device_type)

        if disposition == EmtDeviceDisposition.INJECTION_STRUCTURAL:
            pass
        else:
            return

        inj_working_mdl: Block = injection.emt_model
        assign_static_api_object_mapping_for_device(
            grid=grid,
            device=injection,
            mdl=inj_working_mdl,
            problem_mapping=static_parameter_values_mapping,
            logger=self._static_parameter_mapping_diagnostics,
        )
        self._assign_event_mapping_value_if_present(
            mdl=inj_working_mdl,
            key=ParamPowerFlowReferenceType.Sbase,
            value=float(grid.Sbase),
        )

        mdl: Block = self._process_device_model(
            dev=injection,
            mdl=inj_working_mdl,
            sys_block=sys_block,
            static_parameter_values_mapping=static_parameter_values_mapping,
        )
        b: int = bus_dict[injection.bus]
        effective_external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(
            problem=self,
            mdl=mdl,
        )

        assemble_emt_mapped_current_references(
            model=mdl,
            current_balance=i_kcl,
            effective_external_mapping=effective_external_mapping,
            bus_index=b,
            bus_is_dc=injection.bus.is_dc,
        )

        self._connect_injection_bus_voltages(
            injection=injection,
            mdl=mdl,
            bus_working_models=bus_working_models,
            voltage_connection_substitution=voltage_connection_substitution,
            ph_v_keys=ph_v_keys,
        )

        self._seed_injection_device_by_type(
            injection=injection,
            mdl=mdl,
            bus_index=b,
            seed_store=seed_store,
            injection_index=injection_index,
            generator_battery_count_same_bus=generator_battery_count_same_bus,
        )

    def _seed_injection_device_by_type(self,
                                       injection: Any,
                                       mdl: Block,
                                       bus_index: int,
                                       seed_store: Optional[EmtInjectionOperatingPoint],
                                       injection_index: int,
                                       generator_battery_count_same_bus: Dict[int, int]) -> None:
        """
        Dispatch one injection seed application to the explicit ``DeviceType`` path.

        :param injection: Injection device.
        :param mdl: Registered working model.
        :param bus_index: Bus index.
        :param seed_store: Precomputed seed store.
        :param injection_index: Injection loop index.
        :param generator_battery_count_same_bus: Number of generators and batteries per bus.
        :return: None.
        """
        if seed_store is None:
            if self.options.verbose:
                print("No Power Flow results given.")
            else:
                pass
            return
        else:
            pass

        if injection.device_type == DeviceType.GeneratorDevice:
            generator_battery_count_local: int = int(generator_battery_count_same_bus[bus_index])
            self._apply_injection_seed(
                injection=injection,
                mdl=mdl,
                bus_index=bus_index,
                seed_store=seed_store,
                injection_index=injection_index,
                generator_battery_count_same_bus=generator_battery_count_local,
            )

            if not injection.bus.is_dc:
                phase_power_seed: np.ndarray = seed_store.get_ac_seed(injection_index)
                self._assign_generator_sharing_targets_from_seed(
                    inj=injection,
                    mdl=mdl,
                    phase_power=phase_power_seed,
                    generator_battery_count_same_bus=generator_battery_count_local,
                )
            else:
                pass
        else:
            if injection.device_type == DeviceType.BatteryDevice:
                generator_battery_count_local = int(generator_battery_count_same_bus[bus_index])
                self._apply_injection_seed(
                    injection=injection,
                    mdl=mdl,
                    bus_index=bus_index,
                    seed_store=seed_store,
                    injection_index=injection_index,
                    generator_battery_count_same_bus=generator_battery_count_local,
                )
                if not injection.bus.is_dc:
                    phase_power_seed = seed_store.get_ac_seed(injection_index)
                    self._assign_generator_sharing_targets_from_seed(
                        inj=injection,
                        mdl=mdl,
                        phase_power=phase_power_seed,
                        generator_battery_count_same_bus=generator_battery_count_local,
                    )
                else:
                    pass
            else:
                if injection.device_type == DeviceType.LoadDevice:
                    self._apply_injection_seed(
                        injection=injection,
                        mdl=mdl,
                        bus_index=bus_index,
                        seed_store=seed_store,
                        injection_index=injection_index,
                        generator_battery_count_same_bus=0,
                    )
                else:
                    if injection.device_type == DeviceType.ExternalGridDevice:
                        self._apply_injection_seed(
                            injection=injection,
                            mdl=mdl,
                            bus_index=bus_index,
                            seed_store=seed_store,
                            injection_index=injection_index,
                            generator_battery_count_same_bus=0,
                        )
                    else:
                        if injection.device_type == DeviceType.StaticGeneratorDevice:
                            self._apply_injection_seed(
                                injection=injection,
                                mdl=mdl,
                                bus_index=bus_index,
                                seed_store=seed_store,
                                injection_index=injection_index,
                                generator_battery_count_same_bus=0,
                            )
                        else:
                            if injection.device_type == DeviceType.ShuntDevice:
                                self._apply_injection_seed(
                                    injection=injection,
                                    mdl=mdl,
                                    bus_index=bus_index,
                                    seed_store=seed_store,
                                    injection_index=injection_index,
                                    generator_battery_count_same_bus=0,
                                )
                            else:
                                if injection.device_type == DeviceType.ControllableShuntDevice:
                                    self._apply_injection_seed(
                                        injection=injection,
                                        mdl=mdl,
                                        bus_index=bus_index,
                                        seed_store=seed_store,
                                        injection_index=injection_index,
                                        generator_battery_count_same_bus=0,
                                    )
                                else:
                                    if injection.device_type == DeviceType.CurrentInjectionDevice:
                                        self._apply_injection_seed(
                                            injection=injection,
                                            mdl=mdl,
                                            bus_index=bus_index,
                                            seed_store=seed_store,
                                            injection_index=injection_index,
                                            generator_battery_count_same_bus=0,
                                        )
                                    else:
                                        self._apply_injection_seed(
                                            injection=injection,
                                            mdl=mdl,
                                            bus_index=bus_index,
                                            seed_store=seed_store,
                                            injection_index=injection_index,
                                            generator_battery_count_same_bus=int(
                                                generator_battery_count_same_bus[bus_index]
                                            ),
                                        )


    def _connect_injection_bus_voltages(self,
                                        injection: Any,
                                        mdl: Block,
                                        bus_working_models: Dict[Any, Block],
                                        voltage_connection_substitution: Dict[Var, Var],
                                        ph_v_keys: List[VarPowerFlowReferenceType]) -> None:
        """
        Bind injection bus-voltage inputs to the authoritative bus-shell voltages.

        :param injection: Injection device.
        :param mdl: Registered working model.
        :param bus_working_models: Local bus working models.
        :param voltage_connection_substitution: Voltage substitution map.
        :param ph_v_keys: AC bus voltage keys.
        :return: None.
        """
        inj_external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(
            problem=self,
            mdl=mdl,
        )
        inj_bus_mdl: Block = bus_working_models[injection.bus]

        if injection.bus.is_dc:
            v_dc: Any
            v_dc, _, _, _ = get_bus_emt_algebraic_vars(inj_bus_mdl)

            if inj_external_mapping is not None:
                mapped_var: Optional[Var] = inj_external_mapping.get(VarPowerFlowReferenceType.Vdc, None)
                if mapped_var is not None:
                    if _mapped_var_already_matches_target(mapped_var=mapped_var, target_var=v_dc):
                        pass
                    else:
                        voltage_connection_substitution[mapped_var] = v_dc
                else:
                    pass
            else:
                pass
        else:
            v_n: Any
            v_a: Any
            v_b: Any
            v_c: Any
            v_n, v_a, v_b, v_c = get_bus_emt_algebraic_vars(inj_bus_mdl)
            inj_bus_voltage_vars: List[Any] = list([v_n, v_a, v_b, v_c])

            if inj_external_mapping is not None:
                ph: int = 0
                while ph < 4:
                    mapped_var = inj_external_mapping.get(ph_v_keys[ph], None)
                    inj_bus_voltage_var = inj_bus_voltage_vars[ph]

                    if mapped_var is not None and inj_bus_voltage_var is not None:
                        if _mapped_var_already_matches_target(mapped_var=mapped_var,
                                                             target_var=inj_bus_voltage_var):
                            pass
                        else:
                            voltage_connection_substitution[mapped_var] = inj_bus_voltage_var
                    else:
                        pass

                    ph += 1
            else:
                pass

    def _build_emt_bus_device(self,
                              sys_block: Block,
                              bus: Any,
                              bus_index: int,
                              bus_working_models: Dict[Any, Block],
                              static_parameter_values_mapping: Dict[Var, Const]) -> None:
        """
        Register one EMT bus device and seed its PF initialization.

        :param sys_block: Global EMT system block.
        :param bus: Bus device.
        :param bus_index: Bus index.
        :param bus_working_models: Local bus working models.
        :param static_parameter_values_mapping: Static parameter values already
            resolved while assembling the EMT problem.
        :return: None.
        """
        disposition: str = self._get_device_emt_disposition(bus.device_type)

        if disposition == EmtDeviceDisposition.BUS_STRUCTURAL:
            pass
        else:
            return

        bus_working_mdl: Block = bus_working_models[bus]
        mdl: Block = self._process_device_model(
            dev=bus,
            mdl=bus_working_mdl,
            sys_block=sys_block,
            static_parameter_values_mapping=static_parameter_values_mapping,
        )

        if self.power_flow_results_3ph is not None or self.power_flow_results is not None:
            if self.power_flow_results_3ph is None and self.options.verbose:
                print("Initializing bus variables assuming a balanced power flow")
            self._try_set_bus_pf_init(bus=bus, mdl=mdl, bus_index=bus_index)
        elif self.options.verbose:
            print("No Power Flow results given.")


    # ---------------------------------------------------------------------
    # BUILD STRUCTURE
    # ---------------------------------------------------------------------
    def _build_structure_and_collect(
            self,
            sys_block: Block,
            grid: MultiCircuit,
            static_parameter_values_mapping: Dict[Var, Const],
    ) -> None:
        """
        Build the EMT system structure and collect all algebraic KCL equations.

        This routine assembles the EMT nodal equations in abc coordinates.
        The unknowns are the bus phase voltages and the algebraic equations
        are the KCL balances at each bus-phase.

        The function preserves the original sign conventions:
        - Branch currents are defined as leaving the bus, therefore they are
          subtracted from the KCL accumulator.
        - Injection currents are defined as entering the bus, therefore they are
          added to the KCL accumulator.

        :param sys_block: Block containing the full system DAE.
        :param grid: Network model to assemble.
        :param static_parameter_values_mapping: Dictionary with static parameters and their values.
        :return: None.
        """
        bus_working_models: Dict[Any, Block] = self._build_emt_bus_working_models(grid=grid)
        voltage_connection_substitution: Dict[Var, Var] = dict()

        bus_dict: Dict[Any, int] = dict()

        ph_v_keys: List[VarPowerFlowReferenceType] = list([
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
        ])
        inj_i_keys: List[VarPowerFlowReferenceType] = list([
            VarPowerFlowReferenceType.i_N,
            VarPowerFlowReferenceType.i_A,
            VarPowerFlowReferenceType.i_B,
            VarPowerFlowReferenceType.i_C,
        ])
        br_if_keys: List[VarPowerFlowReferenceType] = list([
            VarPowerFlowReferenceType.if_N,
            VarPowerFlowReferenceType.if_A,
            VarPowerFlowReferenceType.if_B,
            VarPowerFlowReferenceType.if_C,
        ])
        br_it_keys: List[VarPowerFlowReferenceType] = list([
            VarPowerFlowReferenceType.it_N,
            VarPowerFlowReferenceType.it_A,
            VarPowerFlowReferenceType.it_B,
            VarPowerFlowReferenceType.it_C,
        ])
        # Keep all NABC positions here: the connector indexes by physical phase.
        br_vf_keys, br_vt_keys = get_branch_terminal_voltage_refs([True, True, True, True])

        c0: Any = Const(0.0)

        # bus loop to create the I_kcl equations
        I_kcl: Dict[int, List[Any]] = dict()
        for bus_idx, bus in enumerate(grid.buses):
            if bus.is_dc:
                I_kcl[bus_idx] = list([c0])
            else:
                I_kcl[bus_idx] = list([c0, c0, c0, c0])

            bus_dict[bus] = int(bus_idx)

        # Collect injections only after the bus dictionary has been built.
        # The generator-sharing bookkeeping needs the bus indices, so it must run
        # after bus_dict is available.
        injection_devices: List[INJECTION_DEVICE_TYPES] = list(grid.get_injection_devices_iter())

        generator_battery_count_same_bus: Dict[int, int] = dict()
        for bus_idx, _ in enumerate(grid.buses):
            generator_battery_count_same_bus[bus_idx] = 0
        for inj in injection_devices:
            bus_idx_local: int = bus_dict[inj.bus]
            if inj.active:
                if inj.device_type == DeviceType.GeneratorDevice:
                    generator_battery_count_same_bus[bus_idx_local] += 1
                elif inj.device_type == DeviceType.BatteryDevice:
                    generator_battery_count_same_bus[bus_idx_local] += 1
                else:
                    pass
            else:
                pass

        h: float = float(self.options.time_step)
        sbase: float = float(grid.Sbase)
        fbase: float = float(grid.fBase)

        vsc_idx_dict: Dict[str, int] = dict()
        for vsc_idx, vsc in enumerate(grid.vsc_devices):
            vsc_idx_dict[vsc.idtag] = vsc_idx

        pf_branch_index: int = 0

        for branch_idx, br in enumerate(grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True)):
            pf_branch_index = self._build_emt_branch_device(
                grid=grid,
                sys_block=sys_block,
                branch=br,
                branch_index=branch_idx,
                pf_branch_index=pf_branch_index,
                bus_dict=bus_dict,
                bus_working_models=bus_working_models,
                i_kcl=I_kcl,
                voltage_connection_substitution=voltage_connection_substitution,
                static_parameter_values_mapping=static_parameter_values_mapping,
                ph_v_keys=ph_v_keys,
                inj_i_keys=inj_i_keys,
                br_if_keys=br_if_keys,
                br_it_keys=br_it_keys,
                br_vf_keys=br_vf_keys,
                br_vt_keys=br_vt_keys,
                vsc_idx_dict=vsc_idx_dict,
                h=h,
                sbase=sbase,
                fbase=fbase,
            )

        # Map the same structural injections once, after branch construction.
        # Source capability and effective sequence impedances must be available
        # before allocating per-device PF3 seeds, including nested source blocks.
        mapped_injection: InjectionParent
        for mapped_injection in injection_devices:
            if self._get_device_emt_disposition(mapped_injection.device_type) == EmtDeviceDisposition.INJECTION_STRUCTURAL:
                assign_static_api_object_mapping_for_device(
                    grid=grid,
                    device=mapped_injection,
                    mdl=mapped_injection.emt_model,
                    problem_mapping=static_parameter_values_mapping,
                    logger=self.logger,
                )
            else:
                pass

        # Only PF3 needs reconstructed per-device phase powers. Balanced PF
        # powers are read directly when applying each device initialization.
        seed_store: Optional[EmtInjectionOperatingPoint] = self._build_injection_seed_store(
            grid=grid,
            bus_dict=bus_dict,
            injection_devices=injection_devices,
            sbase=grid.Sbase,
            static_parameter_values_mapping=static_parameter_values_mapping,
        )

        for injection_index, inj in enumerate(injection_devices):
            self._build_emt_injection_device(
                grid=grid,
                sys_block=sys_block,
                injection=inj,
                injection_index=injection_index,
                bus_dict=bus_dict,
                bus_working_models=bus_working_models,
                i_kcl=I_kcl,
                voltage_connection_substitution=voltage_connection_substitution,
                static_parameter_values_mapping=static_parameter_values_mapping,
                ph_v_keys=ph_v_keys,
                inj_i_keys=inj_i_keys,
                seed_store=seed_store,
                generator_battery_count_same_bus=generator_battery_count_same_bus,
            )

        bus_idx_local: int = 0
        while bus_idx_local < len(grid.buses):
            phase_idx_local: int = 0
            phase_count_local: int = len(I_kcl[bus_idx_local])
            while phase_idx_local < phase_count_local:
                I_kcl[bus_idx_local][phase_idx_local] = _apply_expression_substitution(
                    expression=I_kcl[bus_idx_local][phase_idx_local],
                    substitution_map=voltage_connection_substitution,
                )
                phase_idx_local += 1
            bus_idx_local += 1

        for bus_idx, bus in enumerate(grid.buses):
            self._build_emt_bus_device(
                sys_block=sys_block,
                bus=bus,
                bus_index=bus_idx,
                bus_working_models=bus_working_models,
                static_parameter_values_mapping=static_parameter_values_mapping,
            )

        for bus_idx, bus in enumerate(grid.buses):
            mdl: Block = bus_working_models[bus]
            bus_kcl_eqs: List[Any] = list()

            if bus.is_dc:
                v_dc_expr: Any | None = _get_external_mapping_var_if_present(
                    mdl=mdl,
                    key=VarPowerFlowReferenceType.Vdc,
                )
                if v_dc_expr is not None:
                    bus_kcl_eqs.append(I_kcl[bus_idx][0])
                else:
                    pass
            else:
                for ph_idx, v_key in enumerate(ph_v_keys):
                    v_expr: Any | None = _get_external_mapping_var_if_present(mdl=mdl, key=v_key)
                    if v_expr is not None:
                        bus_kcl_eqs.append(I_kcl[bus_idx][ph_idx])
                    else:
                        pass

            if len(bus_kcl_eqs) == 0:
                if self.logger is not None:
                    self.logger.add_error(
                        "Bus has no phases (no voltage vars)",
                        value=str(bus_idx)
                    )
                else:
                    pass
            else:
                mdl.algebraic_eqs = bus_kcl_eqs


    def _get_emt_events_for_group(self, emt_events_group: EmtEventsGroup | None) -> List[Any]:
        """
        Return the EMT events that belong to the selected group.

        ``None`` means that all EMT events registered in the grid remain active,
        which preserves the previous default behavior.
        """
        emt_events: List[Any] = _get_grid_runtime_events(self.grid)

        if emt_events_group is None:
            return emt_events

        filtered_events: List[Any] = list()

        for evt in emt_events:
            evt_group: Any = evt.group

            if evt_group is None:
                group_idtag = None
            else:
                group_idtag = evt_group.idtag

            if group_idtag == emt_events_group.idtag:
                filtered_events.append(evt)
            else:
                pass

        return filtered_events

    def _event_targets_registered_parameter(self, evt: Any, parameter_uid: int) -> bool:
        """
        Return whether the EMT event targets a runtime parameter registered in the problem.
        """
        registered_device_idtag: str | None = self._event_parameter_device_idtags.get(parameter_uid, None)
        device_idtag: Any = evt.device_idtag

        if device_idtag is None:
            event_device_idtag = ""
        else:
            event_device_idtag = str(device_idtag)

        if registered_device_idtag is None:
            return False

        if event_device_idtag == "":
            return True

        return registered_device_idtag == event_device_idtag

    def _resolve_registered_event_parameter_uid(self, evt: Any) -> int | None:
        """
        Resolve the runtime-parameter UID targeted by one EMT event.

        Events are often authored against the reusable device model stored on the
        grid element, while the EMT problem operates on cloned working models with
        fresh symbolic UIDs. This resolver first tries the direct UID match and
        then falls back to ``(device_idtag, parameter.name)`` so the event can be
        applied to the corresponding working-model parameter.

        :param evt: EMT event under inspection.
        :return: Registered runtime-parameter UID or ``None`` when not found.
        """
        if isinstance(evt.parameter, Var):
            direct_uid: int = int(evt.parameter.uid)

            if direct_uid in self._event_parameter_device_idtags:
                return direct_uid
            else:
                pass

            event_device_idtag_raw: Any = evt.device_idtag
            if event_device_idtag_raw is None:
                return None
            else:
                lookup_key: Tuple[str, str] = (str(event_device_idtag_raw), str(evt.parameter.name))
                return self._event_parameter_name_lookup.get(lookup_key, None)
        else:
            return None

    def set_events_group(self, emt_events_group: EmtEventsGroup | None) -> None:
        """
        Activate the selected EMT events group inside the problem runtime layer.

        Continuous EMT events are mapped to runtime ``piecewise(time)`` expressions.
        Discrete EMT mode events are stored as scheduled updates consumed by the
        boundary update hook used by the EMT solvers.

        :param emt_events_group: EMT events group to activate. ``None`` keeps all EMT events active.
        :return: None
        """
        # Detect whether the requested group is already active. The special case
        # with no explicitly selected group preserves the original behaviour where
        # scheduled mode events determine whether the runtime layer is initialized.
        same_group_requested: bool

        if self._active_events_group is None:
            same_group_requested = (
                    emt_events_group is None
                    and len(self._scheduled_mode_events) > 0
            )
        elif emt_events_group is None:
            same_group_requested = False
        else:
            same_group_requested = (
                    self._active_events_group.idtag == emt_events_group.idtag
            )

        # Avoid rebuilding the runtime event expressions when the requested event
        # group is already active.
        if same_group_requested:
            return
        else:
            pass

        # Start from the original runtime parameter equations. Continuous events
        # will progressively replace the affected equations with time-dependent
        # expressions, while discrete events are stored separately.
        active_runtime_eqs: List[Any] = list(self._runtime_parameter_eqs0)
        scheduled_mode_events: Dict[int, List[Tuple[float, float, bool]]] = dict()
        continuous_events: Dict[int, List[Dict[str, Any]]] = dict()

        # Pre-register only those continuous runtime parameters that can actually
        # receive continuous EMT events.
        runtime_parameter: Any

        for runtime_parameter in self.get_runtime_continuous_parameters():
            runtime_parameter_uid: int = runtime_parameter.uid

            if runtime_parameter_uid in self._continuous_event_parameter_uids:
                continuous_events[runtime_parameter_uid] = list()
            else:
                pass

        # Retrieve the events belonging to the requested group. A ``None`` group
        # retains the original semantics implemented by the group resolver.
        emt_events: List[Any] = self._get_emt_events_for_group(emt_events_group)

        # Classify every valid event as either a scheduled discrete update or a
        # continuous runtime expression modification.
        evt: Any

        for evt in emt_events:
            parameter_uid: int | None = self._resolve_registered_event_parameter_uid(
                evt
            )

            if parameter_uid is not None:
                if self._event_targets_registered_parameter(evt, parameter_uid):
                    if parameter_uid in self._discrete_event_parameter_uids:
                        # Discrete mode parameters are updated only at their event
                        # boundaries and therefore remain outside the continuous
                        # piecewise expression construction.
                        event_list: List[Tuple[float, float, bool]] = (
                            scheduled_mode_events.setdefault(
                                parameter_uid,
                                list(),
                            )
                        )

                        force_step_alignment: bool = bool(evt.force_step_alignment)

                        event_list.append(
                            (
                                float(evt.time),
                                float(evt.value),
                                force_step_alignment,
                            )
                        )
                    else:
                        if parameter_uid in continuous_events:
                            # Continuous events are stored first and converted into
                            # runtime expressions after all events have been
                            # collected, so their chronological order can be
                            # enforced deterministically.
                            transition_type: DynamicEventTransitionType = (
                                evt.transition_type
                            )
                            end_time_raw_event: Any = evt.end_time
                            normalized_end_time: float | None

                            if end_time_raw_event is None:
                                normalized_end_time = None
                            else:
                                normalized_end_time = float(end_time_raw_event)

                            continuous_event_spec: Dict[str, Any] = dict(
                                time=float(evt.time),
                                value=float(evt.value),
                                end_time=normalized_end_time,
                                transition_type=transition_type,
                            )

                            continuous_events[parameter_uid].append(
                                continuous_event_spec
                            )
                        else:
                            pass
                else:
                    pass
            else:
                pass

        # Convert the collected continuous events into the runtime expressions used
        # by the EMT solver. Each parameter is treated independently.
        continuous_parameter_uid: int
        event_specs: List[Dict[str, Any]]

        for continuous_parameter_uid, event_specs in continuous_events.items():
            if len(event_specs) != 0:
                runtime_idx: int | None = self.uid2idx_event_params.get(
                    continuous_parameter_uid,
                    None,
                )

                if runtime_idx is not None:
                    # Preserve the exact ordering semantics of the original
                    # ``sorted(..., key=_continuous_event_spec_time_sort_key)``.
                    # The helper is called explicitly rather than passed as a
                    # function pointer. The original index provides stable ordering
                    # when two events have identical sort keys.
                    indexed_event_specs: List[
                        Tuple[Any, int, Dict[str, Any]]
                    ] = list()

                    event_spec_index: int
                    event_spec_to_sort: Dict[str, Any]

                    for event_spec_index, event_spec_to_sort in enumerate(event_specs):
                        event_sort_key: Any = _continuous_event_spec_time_sort_key(
                            event_spec_to_sort
                        )

                        indexed_event_specs.append(
                            (
                                event_sort_key,
                                event_spec_index,
                                event_spec_to_sort,
                            )
                        )

                    indexed_event_specs.sort()

                    # Begin with the parameter's current runtime expression. Events
                    # are then layered chronologically on top of that expression.
                    active_expr: Any = active_runtime_eqs[runtime_idx]
                    indexed_event_spec: Tuple[Any, int, Dict[str, Any]]

                    for indexed_event_spec in indexed_event_specs:
                        event_spec: Dict[str, Any] = indexed_event_spec[2]
                        transition_type_value: Any = event_spec["transition_type"]

                        if (
                                transition_type_value
                                == DynamicEventTransitionType.Ramp
                        ):
                            # A ramp replaces the runtime expression between its
                            # start and end times and reaches the requested final
                            # value at the end of the interval.
                            start_time: float = float(event_spec["time"])
                            end_time_raw: Any = event_spec["end_time"]

                            if end_time_raw is None:
                                raise ValueError(
                                    "Ramp EMT events require an end_time"
                                )
                            else:
                                pass

                            end_time: float = float(end_time_raw)

                            if end_time > start_time:
                                pass
                            else:
                                raise ValueError(
                                    "Ramp EMT events require end_time greater than time"
                                )

                            active_expr = _build_ramp_runtime_expr(
                                time_var=self._glob_time,
                                start_time=start_time,
                                end_time=end_time,
                                before_expr=active_expr,
                                final_value=float(event_spec["value"]),
                            )
                        else:
                            # Non-ramp continuous events are represented as an
                            # instantaneous piecewise parameter value change.
                            event_time_values: np.ndarray = np.asarray(
                                (float(event_spec["time"]),),
                                dtype=np.float64,
                            )
                            event_new_values: np.ndarray = np.asarray(
                                (float(event_spec["value"]),),
                                dtype=np.float64,
                            )

                            active_expr = piecewise(
                                time_var=self._glob_time,
                                t_events=event_time_values,
                                new_values=event_new_values,
                                default_value=active_expr,
                            )

                    # Store the fully composed expression back in the same flat
                    # runtime-vector position used by the solver.
                    active_runtime_eqs[runtime_idx] = active_expr
                else:
                    # An event can only be applied when its parameter is present in
                    # the finalized runtime parameter mapping.
                    if self.logger is not None:
                        self.logger.add_warning(
                            msg=(
                                "EMT event targets one runtime parameter that is "
                                "not registered in the active problem."
                            ),
                            device_class="EMT",
                            device_property="event_parameter_uid",
                            value=str(continuous_parameter_uid),
                            expected_value="Registered EMT runtime parameter",
                        )
                    else:
                        pass
            else:
                pass

        # Commit the selected group and its newly constructed runtime event state.
        self._active_events_group = emt_events_group
        self._runtime_all_eqs_source = active_runtime_eqs
        self._scheduled_mode_events = scheduled_mode_events

        # Event-group activation only changes the runtime equations and scheduled
        # updates; it does not change the parameter ordering. Reusing the existing
        # partition avoids rebuilding constant parameter buffers and repeated list
        # reconstruction during every event-group switch.
        #
        # ``active_runtime_eqs`` is already expressed in the flat runtime-vector
        # order used by ``uid2idx_event_params`` and by the solver runtime buffer.
        # Re-splitting it through ``_runtime_all_parameters_source`` would switch
        # back to source-block order and scramble retained mode parameters such as
        # Bergeron history terms. The slices keep the continuous/mode partition
        # aligned with the finalized flat parameter layout.
        self._runtime_continuous_eqs = list(
            active_runtime_eqs[self._runtime_continuous_slice]
        )
        self._runtime_mode_eqs = list(
            active_runtime_eqs[self._runtime_mode_slice]
        )

        # The compiled kernel still belongs to the previous group. Disable and drop
        # it before the initial runtime values of this group are evaluated below,
        # so they come from this group's equations; it is rebuilt at the end.
        self._runtime_parameter_kernel = None
        self._runtime_parameter_kernel_enabled = False

        # Rebuild the unified event-equation vector without concatenating lists,
        # preserving the continuous-then-mode ordering expected by the solver.
        self._event_parameters_eqs = list(self._runtime_continuous_eqs)

        runtime_mode_equation: Any

        for runtime_mode_equation in self._runtime_mode_eqs:
            self._event_parameters_eqs.append(runtime_mode_equation)

        # Reset the cursor because scheduled mode events must be consumed again
        # according to the newly activated group.
        self._mode_event_cursor = dict()
        self._initialize_mode_event_state()

        # Event-group activation must preserve the already resolved runtime
        # operating point from explicit/native initialization. Rebuilding the
        # vector from equation defaults here would erase PF-seeded and
        # explicit-init-resolved parameters, for example Thevenin internal runtime
        # references, immediately before the first simulation step.
        variable_parameter_number: int = self.get_variable_parameter_number()

        if variable_parameter_number > 0:
            preserved_runtime_values: np.ndarray = self._event_params_values.copy()

            self._event_params_values = self._initialize_runtime_parameter_values(
                0.0,
                seed_values=preserved_runtime_values,
            )

            self._event_params_values = self.def_event_params_fn(
                self._event_params_values,
                0.0,
            )
        else:
            self._event_params_values = np.zeros(
                0,
                dtype=np.float64,
            )

        # Continuous event expressions are now final for the selected group.
        # Replace the previously generated kernel while keeping the compiled
        # path disabled until problem initialization has fully completed.
        self._runtime_parameter_kernel = None
        self._runtime_parameter_kernel_enabled = False
        self._build_runtime_parameter_kernel()

    # ---------------------------------------------------------------------
    # MAPPINGS
    # ---------------------------------------------------------------------

    def _rebuild_results_var_name_lookup(self) -> None:
        """
        Rebuild the EMT result-name lookup with unique device-qualified keys.

        ``EmtProblemTemplate`` resets ``_vars_glob_name2uid`` using raw symbolic
        names only. Saved EMT cases often reuse template-local names such as
        ``i_ser_Pi_A`` or repeated load-template names, so the raw-name map drops
        earlier variables. Rebuilding the lookup here preserves one name per UID.

        :return: None.
        """
        unique_names: Dict[str, int] = dict()
        mapped_uids: Set[int] = set()

        device: ALL_DEV_TYPES
        variables: List[Var]
        for device, variables in self._vars_info.items():
            device_idtag: str = str(device.idtag)
            device_name: str = str(device.name)

            for var in variables:
                # Build the preferred global variable name from the symbolic
                # variable name and the owning device public name so the result
                # map stays readable before any duplicate-resolution fallback.
                candidate_name: str = f"{var.name}{device_name}"

                if candidate_name in unique_names and unique_names[candidate_name] != var.uid:
                    candidate_name = f"{candidate_name}{device_idtag}"
                else:
                    pass

                if candidate_name in unique_names and unique_names[candidate_name] != var.uid:
                    candidate_name = f"{candidate_name}{var.uid}"
                else:
                    pass

                unique_names[candidate_name] = var.uid
                mapped_uids.add(var.uid)

                # GUI plot selectors and legacy result consumers use several
                # human-readable device-qualified spellings. Publish those aliases
                # as well so plotting remains robust across scripting, GUI editor,
                # and persisted EMT result workflows.
                for alias_name in [
                    f"{var.name} - {device_name}",
                    f"{var.name}_{device_name}",
                ]:
                    if alias_name in unique_names and unique_names[alias_name] != var.uid:
                        unique_names[f"{alias_name}{device_idtag}"] = var.uid
                    else:
                        unique_names[alias_name] = var.uid

        for var in self.state_and_algebraic_vars():
            if var.uid in mapped_uids:
                pass
            else:
                candidate_name = var.name
                if candidate_name in unique_names and unique_names[candidate_name] != var.uid:
                    candidate_name = f"{candidate_name}{var.uid}"
                else:
                    pass

                unique_names[candidate_name] = var.uid
                mapped_uids.add(var.uid)

        for diff_var in self.get_diff_vars():
            if diff_var.uid in mapped_uids:
                pass
            else:
                candidate_name = diff_var.name
                if candidate_name in unique_names and unique_names[candidate_name] != diff_var.uid:
                    candidate_name = f"{candidate_name}{diff_var.uid}"
                else:
                    pass

                unique_names[candidate_name] = diff_var.uid
                mapped_uids.add(diff_var.uid)

        self._vars_glob_name2uid = unique_names

    # ---------------------------------------------------------------------
    # PF INIT
    # ---------------------------------------------------------------------
    def _get_bus_voltage_vector(self, bus_index: int) -> np.ndarray:
        """Return NABC bus phasors from three-phase PF, or balanced PF otherwise."""
        if self.power_flow_results_3ph is not None:
            return self._get_bus_voltage_vector_3ph(bus_index)
        return self._get_bus_voltage_vector_balanced(bus_index)

    def _get_bus_voltage_vector_3ph(self, bus_index: int) -> np.ndarray:
        """
        Return the bus phase-voltage phasors from the three-phase PF result.

        The returned vector is in NABC order.

        :param bus_index: Bus index.
        :return: Complex voltage vector in NABC order.
        """
        voltage_vector: np.ndarray = np.zeros(4, dtype=np.complex128)

        if self.power_flow_results_3ph is None:
            pass
        else:
            voltage_vector[0] = complex(self.power_flow_results_3ph.voltage_N[bus_index])
            voltage_vector[1] = complex(self.power_flow_results_3ph.voltage_A[bus_index])
            voltage_vector[2] = complex(self.power_flow_results_3ph.voltage_B[bus_index])
            voltage_vector[3] = complex(self.power_flow_results_3ph.voltage_C[bus_index])

        return voltage_vector

    def _get_bus_voltage_vector_balanced(self, bus_index: int) -> np.ndarray:
        """
        Reconstruct balanced bus phase-voltage phasors in NABC order.

        :param bus_index: Bus index.
        :return: Complex voltage vector in NABC order.
        """
        voltage_vector: np.ndarray = np.zeros(4, dtype=np.complex128)

        if self.power_flow_results is None:
            pass
        else:
            bus_voltage: complex = complex(self.power_flow_results.voltage[bus_index])
            voltage_vector[0] = 0.0 + 0.0j
            voltage_vector[1] = bus_voltage
            voltage_vector[2] = bus_voltage * _phase_sequence_shift(2)
            voltage_vector[3] = bus_voltage * _phase_sequence_shift(3)

        return voltage_vector

    def _get_load_fixed_power_vector(self, load: Any, bus_index: int) -> np.ndarray:
        """Return NABC ZIP load power at the solved bus voltage.

        PF3 uses explicit phase data with balanced-total fallback. Balanced PF
        uses totals split equally across ABC. Consumption is negative injection.
        """
        if self.power_flow_results_3ph is not None:
            active_power, reactive_power = get_load_power_phase_values_pu_abc(load, self.grid)
            current_real, current_imag = get_load_current_phase_values_pu_abc(load, self.grid)
            conductance, susceptance = get_load_impedance_phase_values_pu_abc(load, self.grid)
            constant_power = active_power + 1j * reactive_power
            current_coefficient = current_real - 1j * current_imag
            impedance_coefficient = conductance - 1j * susceptance
        else:
            phase_base = 3.0 * self.grid.Sbase
            constant_power = np.full(3, complex(load.P, load.Q) / phase_base)
            current_coefficient = np.full(3, complex(load.Ir, -load.Ii) / phase_base)
            impedance_coefficient = np.full(3, complex(load.G, -load.B) / phase_base)

        voltages = self._get_bus_voltage_vector(bus_index)
        power_vector = _zero_ac_power_vector()
        for phase in range(3):
            voltage_magnitude = abs(voltages[phase + 1])
            current_power = current_coefficient[phase] * voltage_magnitude
            impedance_power = impedance_coefficient[phase] * voltage_magnitude ** 2
            power_vector[phase + 1] = -(constant_power[phase] + current_power + impedance_power)
        return power_vector

    def _get_shunt_fixed_power_vector(self, shunt: Any, bus_index: int) -> np.ndarray:
        """Return the shunt power injected into the bus in NABC order.

        PF3 preserves phase data with balanced-total fallback. Balanced PF uses
        the total admittance split equally across ABC, including kW conversion.
        Positive conductance consumes P; positive capacitive susceptance supplies Q.

        :param shunt: Static shunt supplying conductance and susceptance.
        :param bus_index: Bus position in the power-flow results.
        :return: Phase powers on the system power base, with zero neutral power.
        """
        conductance: np.ndarray
        susceptance: np.ndarray
        if self.power_flow_results_3ph is not None:
            conductance, susceptance = get_shunt_phase_values_pu_abc(shunt, self.grid)
        else:
            unit_scale: float = 1000.0 if shunt.use_kw else 1.0
            phase_base: float = 3.0 * self.grid.Sbase * unit_scale
            conductance = np.full(3, float(shunt.G) / phase_base)
            susceptance = np.full(3, float(shunt.B) / phase_base)

        voltages: np.ndarray = self._get_bus_voltage_vector(bus_index)
        power_vector: np.ndarray = _zero_ac_power_vector()
        for phase in range(3):
            voltage_square: float = float(abs(voltages[phase + 1]) ** 2)
            active_power: float = -conductance[phase] * voltage_square
            reactive_power: float = susceptance[phase] * voltage_square
            power_vector[phase + 1] = complex(active_power, reactive_power)
        return power_vector

    def _try_seed_colocated_balanced_pv_sources(
            self,
            grid: MultiCircuit,
            bus_index: int,
            injection_devices: List[InjectionParent],
            source_indices: np.ndarray,
            residual_power: np.ndarray,
            sbase: float,
            static_parameter_values_mapping: Dict[Var, Const],
            device_phase_power: np.ndarray,
    ) -> bool:
        """Reconstruct one complete group of declared reciprocal Balanced PV sources.

        A nodal PF3 solution does not identify individual source phase currents.
        Reuse the PF reactive-sharing policy, retain each scheduled active power,
        and recover passive zero/negative sequences from the mapped source law.
        Unsupported groups leave the existing residual allocator authoritative.

        :param grid: Canonical network supplying static generator snapshots.
        :param bus_index: AC bus position in the PF3 result.
        :param injection_devices: Devices in the same row order as the phase-power array.
        :param source_indices: Positions of the source-like devices at this bus.
        :param residual_power: Unassigned per-unit NABC power on the system base.
        :param sbase: System three-phase power base in MVA.
        :param static_parameter_values_mapping: Effective mapped constant values.
        :param device_phase_power: Temporary NABC power array, updated only after whole-group checks.
        :return: True if every group seed was committed; False leaves it untouched.
        """
        bus: Bus = grid.buses[bus_index]
        source_count: int = len(source_indices)
        if source_count > 1 and not bus.is_dc and not bus.is_slack and self.power_flow_results_3ph is not None:
            pass
        else:
            return False

        # Qfixed=0 is valid only for a bus consisting entirely of these online,
        # local voltage controllers. Exclude fixed/ZIP/shunt/mixed participants.
        injection: InjectionParent
        bus_device_count: int = 0
        for injection in injection_devices:
            if injection.bus is bus:
                if isinstance(injection, Generator) and injection.device_type == DeviceType.GeneratorDevice:
                    bus_device_count += 1
                else:
                    return False
            else:
                pass
        if bus_device_count == source_count:
            pass
        else:
            return False

        # Allocate the bounded group workspaces; no second network or retained
        # source representation is introduced into MultiCircuit or the devices.
        scheduled_p: np.ndarray = np.zeros(source_count, dtype=np.float64)
        qmin: np.ndarray = np.zeros(source_count, dtype=np.float64)
        qmax: np.ndarray = np.zeros(source_count, dtype=np.float64)
        vset: np.ndarray = np.zeros(source_count, dtype=np.float64)
        sequence_impedance: np.ndarray = np.zeros((source_count, 2), dtype=np.complex128)
        required_refs: tuple[VarPowerFlowReferenceType, ...] = (
            VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_C,
            VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C,
            VarPowerFlowReferenceType.phi_v, VarPowerFlowReferenceType.phi,
            VarPowerFlowReferenceType.Vpk, VarPowerFlowReferenceType.Ipk,
            VarPowerFlowReferenceType.UR_A, VarPowerFlowReferenceType.UR_B, VarPowerFlowReferenceType.UR_C,
            VarPowerFlowReferenceType.UI_A, VarPowerFlowReferenceType.UI_B, VarPowerFlowReferenceType.UI_C,
            VarPowerFlowReferenceType.IR_A, VarPowerFlowReferenceType.IR_B, VarPowerFlowReferenceType.IR_C,
            VarPowerFlowReferenceType.II_A, VarPowerFlowReferenceType.II_B, VarPowerFlowReferenceType.II_C,
        )
        extra_terminals: tuple[VarPowerFlowReferenceType, ...] = (
            VarPowerFlowReferenceType.i_N, VarPowerFlowReferenceType.Idc,
            VarPowerFlowReferenceType.If_dc, VarPowerFlowReferenceType.It_dc,
            VarPowerFlowReferenceType.if_N, VarPowerFlowReferenceType.if_A,
            VarPowerFlowReferenceType.if_B, VarPowerFlowReferenceType.if_C,
            VarPowerFlowReferenceType.it_N, VarPowerFlowReferenceType.it_A,
            VarPowerFlowReferenceType.it_B, VarPowerFlowReferenceType.it_C,
        )
        impedance_refs: tuple[ParamPowerFlowReferenceType, ...] = (
            ParamPowerFlowReferenceType.R1, ParamPowerFlowReferenceType.X1,
            ParamPowerFlowReferenceType.thevenin_source_r0_pu,
            ParamPowerFlowReferenceType.thevenin_source_x0_pu,
        )
        row: int
        for row in range(source_count):
            injection = injection_devices[int(source_indices[row])]
            if isinstance(injection, Generator):
                generator: Generator = injection
            else:
                return False
            if (
                    generator.get_active_at(None)
                    and generator.get_control_mode_prof_at(None) == GeneratorControlMode.V
                    and (generator.control_bus is None or generator.control_bus is bus)
                    and generator.conn == ShuntConnectionType.GroundedStar
                    and not generator.use_reactive_power_curve and not generator.use_kw
            ):
                pass
            else:
                return False
            scheduled_p[row] = generator.get_P_at(None)
            qmin[row] = generator.get_Qmin_at(None)
            qmax[row] = generator.get_Qmax_at(None)
            vset[row] = generator.get_Vset_at(None)
            if (
                    np.isfinite(scheduled_p[row]) and np.isfinite(qmin[row])
                    and np.isfinite(qmax[row]) and qmin[row] <= qmax[row]
                    and np.isfinite(vset[row]) and abs(vset[row] - vset[0]) <= 1.0e-8
            ):
                pass
            else:
                return False

            # Resolve only an explicit canonical declaration, never a name or
            # inferred equation family. Validate both tree aliases and local owner.
            root: Block = generator.emt_model
            blocks: List[Block] = root.get_all_blocks()
            source: Block | None = None
            block: Block
            for block in blocks:
                if block.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid is not None:
                    if source is None:
                        source = block
                    else:
                        return False
                else:
                    pass
            if source is None:
                return False
            else:
                validate_dynamic_model_contract(root)
                validate_dynamic_model_contract(source)

            # An empty wrapper may expose the same UID interface. A different
            # root alias or additional runtime owner cannot share this source law.
            consumed_refs: Dict[VarPowerFlowReferenceType, Var] = _collect_external_mapping_from_block(root)
            variable: Var
            input_uids: Set[int] = set(variable.uid for variable in source.in_vars)
            current_uids: Set[int] = set(variable.uid for variable in source.state_vars)
            current_uids.update(variable.uid for variable in source.out_vars)
            event_uids: Set[int] = set(variable.uid for variable in source.event_dict)
            ref_index: int
            reference: VarPowerFlowReferenceType
            for ref_index, reference in enumerate(required_refs):
                local_ref: Var | None = source.external_mapping.get(reference, None)
                consumed_ref: Var | None = consumed_refs.get(reference, None)
                if local_ref is not None and consumed_ref is not None and local_ref.uid == consumed_ref.uid:
                    if ref_index < 3:
                        owned_uids: Set[int] = input_uids
                    elif ref_index < 6:
                        owned_uids = current_uids
                    else:
                        owned_uids = event_uids
                    if local_ref.uid in owned_uids:
                        pass
                    else:
                        return False
                else:
                    return False
                for block in blocks:
                    exposed_ref: Var | None = block.external_mapping.get(reference, None)
                    if exposed_ref is None or exposed_ref.uid == local_ref.uid:
                        pass
                    else:
                        return False
            for block in blocks:
                if len(block.dynamic_model_contract.emt_terminal_current_contributions) > 0:
                    return False
                else:
                    pass
                for reference in extra_terminals:
                    if block.external_mapping.get(reference, None) is None:
                        pass
                    else:
                        return False
                if block is source:
                    pass
                elif (
                        len(block.state_eqs) > 0 or len(block.algebraic_eqs) > 0
                        or len(block.differential_eqs) > 0 or len(block.diff_vars) > 0
                        or len(block.event_dict) > 0 or len(block.mode_dict) > 0
                ):
                    return False
                else:
                    pass

            # Use the same UID-based effective constant resolution as normal
            # device construction, including mapped mode and optional Z0 fallback.
            mode_parameter: Var | None = None
            parameter: Var
            for parameter in source.parameters:
                if parameter.uid == source.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid:
                    mode_parameter = parameter
                else:
                    pass
            if mode_parameter is None:
                return False
            else:
                mode_value: Const = resolve_constant_parameter_initial_value(
                    generator, DynamicSimulationMode.EMT, root, source, mode_parameter, source.parameters[mode_parameter],
                    static_parameter_values_mapping,
                )
            source_mode: TheveninSourceVoltageMode
            if isinstance(mode_value.value, (int, float)) and not isinstance(mode_value.value, bool):
                pass
            else:
                return False
            if mode_value.value == 0:
                source_mode = TheveninSourceVoltageMode.Balanced
            elif mode_value.value == 1:
                source_mode = TheveninSourceVoltageMode.Phase
            else:
                return False
            if source_mode == TheveninSourceVoltageMode.Balanced:
                pass
            else:
                return False
            effective_impedances: np.ndarray = np.zeros(4, dtype=np.float64)
            impedance_ref: ParamPowerFlowReferenceType
            for ref_index, impedance_ref in enumerate(impedance_refs):
                parameter = source.api_obj_mapping[impedance_ref]
                resolved: Const = resolve_constant_parameter_initial_value(
                    generator, DynamicSimulationMode.EMT, root, source, parameter, source.parameters[parameter],
                    static_parameter_values_mapping,
                )
                effective_impedances[ref_index] = float(resolved.value)
            sequence_impedance[row, 0] = complex(effective_impedances[0], effective_impedances[1])
            sequence_impedance[row, 1] = complex(effective_impedances[2], effective_impedances[3])

        # Treat solved voltage/setpoint compatibility as applicability, without
        # inventing a physical setpoint or mutating the input PF3 snapshot.
        voltage: np.ndarray = np.array((self.power_flow_results_3ph.voltage_A[bus_index],
            self.power_flow_results_3ph.voltage_B[bus_index], self.power_flow_results_3ph.voltage_C[bus_index]),
            dtype=np.complex128)
        rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
        v0: complex = complex(np.mean(voltage))
        v1: complex = complex(np.mean(voltage / rotation))
        v2: complex = complex(np.mean(voltage * rotation))
        applicable: bool = bool(
            np.all(np.isfinite(voltage)) and np.all(np.isfinite(residual_power))
            and np.isfinite(sbase) and sbase > 0.0 and abs(v1) > 1.0e-12
            and np.min(np.abs(voltage)) > 1.0e-12 and abs(abs(v1) - vset[0]) <= 1.0e-6
            and abs(residual_power[0]) <= 1.0e-6
        )
        phase_power: np.ndarray = np.zeros((source_count, 4), dtype=np.complex128)
        if applicable:
            # Flat native snapshot limits use exactly the shared PF Q policy.
            # No extra clipping is applied to the already solved bus injection.
            q_allocated: np.ndarray
            q_batteries: np.ndarray
            q_allocated, q_batteries = split_reactive_power_between_generators_and_batteries(
                Qbus=np.array((np.sum(residual_power[1:]).imag * sbase,)),
                Qfixed_bus=np.zeros(1), gen_bus_idx=np.zeros(source_count, dtype=np.int64),
                Qmin_gen=qmin, Qmax_gen=qmax, gen_status=np.ones(source_count, dtype=bool),
                control_mode_int_gen=np.full(source_count, GeneratorControlMode.V.idx(), dtype=np.int64),
                Q0_gen=np.zeros(source_count), Vset_gen=vset, k_droop_gen=np.zeros(source_count),
                dead_band_gen=np.zeros(source_count), batt_bus_idx=np.zeros(0, dtype=np.int64),
                Qmin_batt=np.zeros(0), Qmax_batt=np.zeros(0), batt_status=np.zeros(0, dtype=bool),
                control_mode_int_batt=np.zeros(0, dtype=np.int64), Q0_batt=np.zeros(0),
                v_ctrl_val_gen=GeneratorControlMode.V.idx(), qv_droop_val_gen=GeneratorControlMode.QVDroop.idx(),
                Vm=np.array((abs(v1),)), enforce_q_limits=False,
            )
            group_current: np.ndarray = np.zeros(3, dtype=np.complex128)
            for row in range(source_count):
                passive_current: np.ndarray = -v0 / sequence_impedance[row, 1] - v2 / sequence_impedance[row, 0] * rotation.conj()
                passive_power: complex = complex(np.mean(voltage * passive_current.conj()))
                i1: complex = complex(np.conj((complex(scheduled_p[row], q_allocated[row]) / sbase - passive_power) / v1))
                current: np.ndarray = passive_current + i1 * rotation
                group_current += current
                phase_power[row, 1:] = voltage * current.conj() / 3.0
            applicable = bool(
                np.all(np.isfinite(phase_power)) and np.all(np.isfinite(group_current))
                and np.max(np.abs(group_current - 3.0 * np.conj(residual_power[1:] / voltage))) <= 1.0e-6
                and np.max(np.abs(np.sum(phase_power, axis=0) - residual_power)) <= 1.0e-6
            )
        else:
            pass
        if applicable:
            # Commit atomically after all electrical and interface gates pass.
            for row in range(source_count):
                device_phase_power[int(source_indices[row]), :] = phase_power[row]
            return True
        else:
            if self.logger is not None:
                self.logger.add_warning(msg="Colocated Balanced PV PF3 seed is incompatible; using existing residual allocation.",
                    device=bus.name, device_class="EMT", device_property="injection_seed_store_3ph",
                    value="Solved voltage or aggregate current/power mismatch", expected_value="Compatible complete PV snapshot")
            else:
                pass
            return False

    def _build_injection_seed_store(
            self,
            grid: MultiCircuit,
            bus_dict: Dict[Bus, int],
            injection_devices: List[INJECTION_DEVICE_TYPES],
            sbase: float,
            static_parameter_values_mapping: Dict[Var, Const],
    ) -> Optional[EmtInjectionOperatingPoint]:
        """Build a common per-device power representation for balanced PF or PF3.

        Balanced device dispatch is consumed directly. PF3 phase powers require
        allocation among sources before both paths use the same seed application.

        :param grid: Static network model.
        :param bus_dict: Bus positions in the PF results.
        :param injection_devices: Fixed device ordering for the returned store.
        :param sbase: System power base.
        :param static_parameter_values_mapping: Mapped constants for PV reconstruction.
        :return: Per-device powers, or None when neither PF result is supplied.
        """
        use_3ph: bool = self.power_flow_results_3ph is not None
        if not use_3ph and self.power_flow_results is None:
            return None
        else:
            pass
        n_buses: int = len(grid.buses)
        n_injections: int = len(injection_devices)
        generators: List[INJECTION_DEVICE_TYPES] = list(grid.get_generators())
        batteries: List[INJECTION_DEVICE_TYPES] = list(grid.get_batteries())
        n_generators: int = len(generators)
        n_batteries: int = len(batteries)

        operating_point: EmtInjectionOperatingPoint = EmtInjectionOperatingPoint(n_injections)

        # PF3 exposes only bus phase powers. Preserve them as the authoritative
        # phase targets and accumulate all non-participating device powers.
        target_bus_power: np.ndarray = np.zeros((n_buses, 4), dtype=np.complex128)
        if use_3ph:
            target_bus_power[:, 1] = self.power_flow_results_3ph.Sbus_A / sbase
            target_bus_power[:, 2] = self.power_flow_results_3ph.Sbus_B / sbase
            target_bus_power[:, 3] = self.power_flow_results_3ph.Sbus_C / sbase
        else:
            pass
        fixed_bus_power: np.ndarray = np.zeros((n_buses, 4), dtype=np.complex128)
        device_phase_power: np.ndarray = np.zeros((n_injections, 4), dtype=np.complex128)
        generator_injection_indices: np.ndarray = np.full(n_generators, -1, dtype=np.int64)
        battery_injection_indices: np.ndarray = np.full(n_batteries, -1, dtype=np.int64)

        generator_index: int = 0
        battery_index: int = 0
        injection_index: int = 0

        while injection_index < n_injections:
            injection: INJECTION_DEVICE_TYPES = injection_devices[injection_index]
            bus_index: int = int(bus_dict[injection.bus])

            # Preserve the family-to-injection mapping for active, inactive,
            # AC, and DC devices alike. PF result arrays use this family order.
            if injection.device_type == DeviceType.GeneratorDevice:
                generator_injection_indices[generator_index] = injection_index
            else:
                pass
            if injection.device_type == DeviceType.BatteryDevice:
                battery_injection_indices[battery_index] = injection_index
            else:
                pass

            if not use_3ph or injection.bus.is_dc:
                if self.power_flow_results is None:
                    if self.logger is not None:
                        self.logger.add_error(
                            msg="Three-phase EMT initialization requires balanced PF results for DC injections.",
                            device=injection.name,
                            device_class=str(injection.device_type),
                            device_property="power_flow_results",
                        )
                    else:
                        pass
                else:
                    device_power: complex = get_balanced_device_power_pu(
                        grid=grid, power_flow_results=self.power_flow_results,
                        injection=injection, bus_dict=bus_dict,
                        generator_index=generator_index, battery_index=battery_index,
                    )
                    if injection.bus.is_dc:
                        operating_point.set_dc_seed(injection_index, float(device_power.real))
                    else:
                        phase_power: np.ndarray = np.zeros(4, dtype=np.complex128)
                        phase_power[1:4] = device_power / 3.0
                        operating_point.set_ac_seed(injection_index, phase_power)
            else:
                phase_power: np.ndarray = np.zeros(4, dtype=np.complex128)

                if injection.active:
                    if injection.device_type == DeviceType.GeneratorDevice:
                        # Source powers are assigned after all fixed injections
                        # have been removed from the solved bus target.
                        pass
                    elif injection.device_type == DeviceType.BatteryDevice:
                        pass
                    elif injection.device_type == DeviceType.LoadDevice:
                        phase_power = self._get_load_fixed_power_vector(
                            load=injection,
                            bus_index=bus_index,
                        )
                    elif injection.device_type == DeviceType.StaticGeneratorDevice:
                        phase_p_abc: np.ndarray
                        phase_q_abc: np.ndarray
                        phase_p_abc, phase_q_abc = get_load_power_phase_values_pu_abc(
                            load=injection,
                            grid=grid,
                        )
                        phase_power[1:4] = phase_p_abc + 1.0j * phase_q_abc
                    elif injection.device_type == DeviceType.ExternalGridDevice:
                        phase_p_abc, phase_q_abc = get_load_power_phase_values_pu_abc(
                            load=injection,
                            grid=grid,
                        )
                        phase_power[1:4] = -(phase_p_abc + 1.0j * phase_q_abc)
                    elif injection.device_type == DeviceType.ShuntDevice:
                        phase_power = self._get_shunt_fixed_power_vector(
                            shunt=injection,
                            bus_index=bus_index,
                        )
                    elif injection.device_type == DeviceType.ControllableShuntDevice:
                        phase_power = self._get_shunt_fixed_power_vector(
                            shunt=injection,
                            bus_index=bus_index,
                        )
                    elif injection.device_type == DeviceType.CurrentInjectionDevice:
                        current_real_abc: np.ndarray
                        current_imaginary_abc: np.ndarray
                        current_real_abc, current_imaginary_abc = get_current_injection_phase_values_pu_abc(
                            current_injection=injection,
                            grid=grid,
                        )
                        voltage_vector: np.ndarray = self._get_bus_voltage_vector(bus_index)
                        phase_index: int = 1
                        while phase_index < 4:
                            specified_current: complex = complex(
                                current_real_abc[phase_index - 1],
                                current_imaginary_abc[phase_index - 1],
                            )
                            phase_power[phase_index] = -voltage_vector[phase_index] * np.conj(
                                specified_current
                            )
                            phase_index += 1
                    else:
                        phase_power[:] = 0.0 + 0.0j
                else:
                    phase_power[:] = 0.0 + 0.0j

                device_phase_power[injection_index, :] = phase_power
                if (injection.device_type == DeviceType.GeneratorDevice
                        or injection.device_type == DeviceType.BatteryDevice):
                    pass
                else:
                    fixed_bus_power[bus_index, :] += phase_power

            if injection.device_type == DeviceType.GeneratorDevice:
                generator_index += 1
            else:
                pass
            if injection.device_type == DeviceType.BatteryDevice:
                battery_index += 1
            else:
                pass
            injection_index += 1

        if not use_3ph:
            return operating_point
        else:
            pass

        # Compile the source arrays required by the existing balanced slack
        # allocator. Baselines come from balanced PF when present, so non-slack
        # source devices retain the same operating point as RMS.
        generator_bus_indices: np.ndarray = np.zeros(n_generators, dtype=np.int64)
        generator_p_min: np.ndarray = np.zeros(n_generators, dtype=np.float64)
        generator_p_max: np.ndarray = np.zeros(n_generators, dtype=np.float64)
        generator_q_min: np.ndarray = np.zeros(n_generators, dtype=np.float64)
        generator_q_max: np.ndarray = np.zeros(n_generators, dtype=np.float64)
        generator_status: np.ndarray = np.zeros(n_generators, dtype=bool)
        generator_p_base: np.ndarray = np.zeros(n_generators, dtype=np.float64)
        generator_q_base: np.ndarray = np.zeros(n_generators, dtype=np.float64)
        generator_index = 0
        while generator_index < n_generators:
            generator: INJECTION_DEVICE_TYPES = generators[generator_index]
            generator_unit_scale: float = 1000.0 if generator.use_kw else 1.0
            generator_bus_indices[generator_index] = int(bus_dict[generator.bus])
            generator_p_min[generator_index] = float(generator.Pmin) / generator_unit_scale / (3.0 * sbase)
            generator_p_max[generator_index] = float(generator.Pmax) / generator_unit_scale / (3.0 * sbase)
            generator_q_min[generator_index] = float(generator.Qmin) / generator_unit_scale / (3.0 * sbase)
            generator_q_max[generator_index] = float(generator.Qmax) / generator_unit_scale / (3.0 * sbase)
            generator_status[generator_index] = bool(generator.active and not generator.bus.is_dc)
            if self.power_flow_results is None:
                generator_p_base[generator_index] = float(generator.P) / generator_unit_scale / (3.0 * sbase)
                generator_q_base[generator_index] = float(generator.Q) / generator_unit_scale / (3.0 * sbase)
            else:
                generator_p_base[generator_index] = (
                    float(self.power_flow_results.gen_p[generator_index]) / (3.0 * sbase)
                )
                generator_q_base[generator_index] = (
                    float(self.power_flow_results.gen_q[generator_index]) / (3.0 * sbase)
                )
            generator_index += 1

        battery_bus_indices: np.ndarray = np.zeros(n_batteries, dtype=np.int64)
        battery_p_min: np.ndarray = np.zeros(n_batteries, dtype=np.float64)
        battery_p_max: np.ndarray = np.zeros(n_batteries, dtype=np.float64)
        battery_q_min: np.ndarray = np.zeros(n_batteries, dtype=np.float64)
        battery_q_max: np.ndarray = np.zeros(n_batteries, dtype=np.float64)
        battery_status: np.ndarray = np.zeros(n_batteries, dtype=bool)
        battery_p_base: np.ndarray = np.zeros(n_batteries, dtype=np.float64)
        battery_q_base: np.ndarray = np.zeros(n_batteries, dtype=np.float64)
        battery_index = 0
        while battery_index < n_batteries:
            battery: INJECTION_DEVICE_TYPES = batteries[battery_index]
            battery_unit_scale: float = 1000.0 if battery.use_kw else 1.0
            battery_bus_indices[battery_index] = int(bus_dict[battery.bus])
            battery_p_min[battery_index] = float(battery.Pmin) / battery_unit_scale / (3.0 * sbase)
            battery_p_max[battery_index] = float(battery.Pmax) / battery_unit_scale / (3.0 * sbase)
            battery_q_min[battery_index] = float(battery.Qmin) / battery_unit_scale / (3.0 * sbase)
            battery_q_max[battery_index] = float(battery.Qmax) / battery_unit_scale / (3.0 * sbase)
            battery_status[battery_index] = bool(battery.active and not battery.bus.is_dc)
            if self.power_flow_results is None:
                battery_p_base[battery_index] = float(battery.P) / battery_unit_scale / (3.0 * sbase)
                battery_q_base[battery_index] = float(battery.Q) / battery_unit_scale / (3.0 * sbase)
            else:
                battery_p_base[battery_index] = (
                    float(self.power_flow_results.battery_p[battery_index]) / (3.0 * sbase)
                )
                battery_q_base[battery_index] = (
                    float(self.power_flow_results.battery_q[battery_index]) / (3.0 * sbase)
                )
            battery_index += 1

        slack_bus_mask: np.ndarray = np.zeros(n_buses, dtype=bool)
        grid_bus_index: int = 0
        while grid_bus_index < len(grid.buses):
            grid_bus: Bus = grid.buses[grid_bus_index]
            bus_index = int(bus_dict[grid_bus])
            slack_bus_mask[bus_index] = bool(grid_bus.is_slack and not grid_bus.is_dc)
            grid_bus_index += 1

        # Allocate each solved phase independently. The helper gives all active
        # generators and batteries at a slack bus one common capability-based
        # sharing factor, exactly as balanced PF does for its final residual.
        phase_index: int = 1
        while phase_index < 4:
            generator_p_phase: np.ndarray
            battery_p_phase: np.ndarray
            generator_q_phase: np.ndarray
            battery_q_phase: np.ndarray
            generator_p_phase, battery_p_phase = split_slack_bus_quantity_between_generators_and_batteries(
                Qbus=target_bus_power[:, phase_index].real,
                Qfixed_bus=fixed_bus_power[:, phase_index].real,
                slack_bus_mask=slack_bus_mask,
                gen_bus_idx=generator_bus_indices,
                Qmin_gen=generator_p_min,
                Qmax_gen=generator_p_max,
                gen_status=generator_status,
                Q0_gen=generator_p_base,
                batt_bus_idx=battery_bus_indices,
                Qmin_batt=battery_p_min,
                Qmax_batt=battery_p_max,
                batt_status=battery_status,
                Q0_batt=battery_p_base,
                atol=1.0e-12,
            )
            generator_q_phase, battery_q_phase = split_slack_bus_quantity_between_generators_and_batteries(
                Qbus=target_bus_power[:, phase_index].imag,
                Qfixed_bus=fixed_bus_power[:, phase_index].imag,
                slack_bus_mask=slack_bus_mask,
                gen_bus_idx=generator_bus_indices,
                Qmin_gen=generator_q_min,
                Qmax_gen=generator_q_max,
                gen_status=generator_status,
                Q0_gen=generator_q_base,
                batt_bus_idx=battery_bus_indices,
                Qmin_batt=battery_q_min,
                Qmax_batt=battery_q_max,
                batt_status=battery_status,
                Q0_batt=battery_q_base,
                atol=1.0e-12,
            )

            generator_index = 0
            while generator_index < n_generators:
                injection_index = int(generator_injection_indices[generator_index])
                device_phase_power[injection_index, phase_index] = complex(
                    generator_p_phase[generator_index],
                    generator_q_phase[generator_index],
                )
                generator_index += 1

            battery_index = 0
            while battery_index < n_batteries:
                injection_index = int(battery_injection_indices[battery_index])
                device_phase_power[injection_index, phase_index] = complex(
                    battery_p_phase[battery_index],
                    battery_q_phase[battery_index],
                )
                battery_index += 1
            phase_index += 1

        # Preserve the existing reciprocal PV reconstruction only for complete
        # compatible groups. All other devices retain the upstream PF dispatch.
        source_indices: np.ndarray = np.empty(n_generators, dtype=np.int64)
        for bus_index in range(n_buses):
            source_count: int = 0
            for generator_index in range(n_generators):
                if int(bus_dict[generators[generator_index].bus]) == bus_index:
                    source_indices[source_count] = generator_injection_indices[generator_index]
                    source_count += 1
                else:
                    pass
            self._try_seed_colocated_balanced_pv_sources(
                    grid=grid,
                    bus_index=bus_index,
                    injection_devices=injection_devices,
                    source_indices=source_indices[:source_count],
                    residual_power=target_bus_power[bus_index, :] - fixed_bus_power[bus_index, :],
                    sbase=sbase,
                    static_parameter_values_mapping=static_parameter_values_mapping,
                    device_phase_power=device_phase_power,
            )

        # Store powers only. Current conversion belongs to seed application.
        for injection_index, injection in enumerate(injection_devices):
            if not injection.bus.is_dc:
                operating_point.set_ac_seed(injection_index, device_phase_power[injection_index])
            else:
                pass
        return operating_point


    def _warn_balanced_thevenin_operating_point(
            self, generator: Any, mdl: Block,
            voltages: np.ndarray, currents: np.ndarray,
    ) -> None:
        """Warn when a balanced internal source cannot sustain the PF phasors."""
        balanced_source: bool = False
        for block in mdl.get_all_blocks():
            mode_uid: int | None = block.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid
            for parameter, value in block.parameters.items():
                if parameter.uid == mode_uid:
                    balanced_source = value.value == 0.0
        # The declared source mode determines capability; both modes share theta.
        if balanced_source and self.logger is not None:
            impedance = complex(generator.R1, generator.X1)
            required_emf = voltages[1:] + impedance * currents[1:]
            rotation = np.exp(2j * np.pi / 3.0)
            positive_sequence = np.dot([1.0, rotation, rotation ** 2], required_emf) / 3.0
            balanced_emf = positive_sequence * np.array([1.0, rotation ** 2, rotation])
            mismatch = float(np.max(np.abs(required_emf - balanced_emf)))
            tolerance = 1e-6 * max(1.0, float(np.max(np.abs(required_emf))))
            if mismatch > tolerance:
                self.logger.add_warning(
                    msg=("Balanced EMT Thevenin source cannot maintain the provided PF operating point: "
                         "V + (R + jX)I requires unbalanced internal phase EMFs. "
                         "A startup transient is expected."),
                    device=generator.name,
                    value=mismatch,
                    expected_value=f"Internal EMF departure from balance <= {tolerance:.3g} pu (RMS)",
                )

    def _warn_unsupported_load_power(
            self,
            injection: Any,
            mdl: Block,
            phase_power: np.ndarray,
    ) -> None:
        """Warn when a declared R/L/C load lacks a required component.

        Models without physical component references are left unclassified.
        This checks component presence, not sizing or steady-state accuracy.
        """
        if injection.device_type != DeviceType.LoadDevice or self.logger is None:
            return

        phase_references = (
            ("A", VarPowerFlowReferenceType.R_A, VarPowerFlowReferenceType.L_A, VarPowerFlowReferenceType.C_A),
            ("B", VarPowerFlowReferenceType.R_B, VarPowerFlowReferenceType.L_B, VarPowerFlowReferenceType.C_B),
            ("C", VarPowerFlowReferenceType.R_C, VarPowerFlowReferenceType.L_C, VarPowerFlowReferenceType.C_C),
        )
        physical_references = set()
        for phase, resistance_ref, inductance_ref, capacitance_ref in phase_references:
            physical_references.update((resistance_ref, inductance_ref, capacitance_ref))

        available_components = set()
        for block in mdl.get_all_blocks():
            for reference, parameter in block.external_mapping.items():
                if reference in physical_references and parameter is not None:
                    available_components.add(reference)

        if not available_components:
            return

        power_tolerance_pu = 1.0e-9
        for phase_index, references in enumerate(phase_references, start=1):
            phase, resistance_ref, inductance_ref, capacitance_ref = references

            # Seeds use injection signs: negate them to obtain load consumption.
            active_power_pu = -float(np.real(phase_power[phase_index]))
            reactive_power_pu = -float(np.imag(phase_power[phase_index]))

            requires_active_power = abs(active_power_pu) > power_tolerance_pu
            requires_inductive_power = reactive_power_pu > power_tolerance_pu
            requires_capacitive_power = reactive_power_pu < -power_tolerance_pu

            if requires_active_power and resistance_ref not in available_components:
                self._log_unsupported_load_power(
                    load_name=injection.name, phase=phase,
                    power_type="active", power_pu=active_power_pu,
                    unit="MW", required_component="resistor",
                )
            if requires_inductive_power and inductance_ref not in available_components:
                self._log_unsupported_load_power(
                    load_name=injection.name, phase=phase,
                    power_type="inductive reactive", power_pu=reactive_power_pu,
                    unit="MVAr", required_component="inductor",
                )
            if requires_capacitive_power and capacitance_ref not in available_components:
                self._log_unsupported_load_power(
                    load_name=injection.name, phase=phase,
                    power_type="capacitive reactive", power_pu=reactive_power_pu,
                    unit="MVAr", required_component="capacitor",
                )

    def _log_unsupported_load_power(
            self,
            load_name: str,
            phase: str,
            power_type: str,
            power_pu: float,
            unit: str,
            required_component: str,
    ) -> None:
        """Record one unsupported load setpoint in physical power units."""
        power_magnitude = abs(power_pu) * self.grid.Sbase
        self.logger.add_warning(
            msg=f"EMT load model cannot provide the {power_type} power required by the power-flow setpoint.",
            device=load_name,
            value=f"phase {phase}: {power_magnitude:.6g} {unit}",
            expected_value=f"A load model with a phase-{phase} {required_component}",
        )

    def _apply_injection_seed(
            self,
            injection: INJECTION_DEVICE_TYPES,
            mdl: Block,
            bus_index: int,
            seed_store: EmtInjectionOperatingPoint,
            injection_index: int,
            generator_battery_count_same_bus: int,
    ) -> None:
        """
        Apply the precomputed PF seed of one injection into the EMT model.

        This replaces the old logic that initialized each injection directly from
        ``Sbus`` of the bus. That old logic is only valid when there is exactly one
        injection device on the bus.

        :param injection: Injection device.
        :param mdl: Injection symbolic block.
        :param bus_index: Bus index.
        :param seed_store: Precomputed seed store.
        :param injection_index: Injection position in the fixed injection list.
        :param generator_battery_count_same_bus: Number of active generators
            and batteries on the bus.
        :return: None.
        """
        if seed_store.has_seed(injection_index):
            pass
        else:
            return

        if injection.bus.is_dc:
            if self.power_flow_results is None:
                pass
            else:
                power_dc: float = seed_store.get_dc_seed(injection_index)
                voltage_dc: float = float(np.abs(self.power_flow_results.voltage[bus_index]))

                self.set_init_guess(
                    mdl=mdl,
                    reference_powerflow=VarPowerFlowReferenceType.P,
                    val=power_dc,
                )

                if abs(voltage_dc) > 1.0e-12:
                    self.set_if_exists(
                        mdl=mdl,
                        key=VarPowerFlowReferenceType.Idc,
                        value=power_dc / voltage_dc,
                    )
                else:
                    self.set_if_exists(
                        mdl=mdl,
                        key=VarPowerFlowReferenceType.Idc,
                        value=0.0,
                    )
        else:
            phase_power: np.ndarray = seed_store.get_ac_seed(injection_index)
            self._warn_unsupported_load_power(injection, mdl, phase_power)
            phase_current_vector: np.ndarray = np.zeros(4, dtype=np.complex128)
            preserve_generator_current_seed: bool

            voltage_vector: np.ndarray = self._get_bus_voltage_vector(bus_index)

            # Ordinary Vm always represents the operating state, including zero.
            # Component dimensioning opts into a separate declared reference.
            operating_vm: float = float(np.abs(voltage_vector[1]))
            self.set_if_exists(
                mdl=mdl,
                key=VarPowerFlowReferenceType.Vm,
                value=operating_vm,
                persist_after_native_init=True,
            )
            for phase_index, magnitude_key in (
                (1, VarPowerFlowReferenceType.Vm_A),
                (2, VarPowerFlowReferenceType.Vm_B),
                (3, VarPowerFlowReferenceType.Vm_C),
            ):
                self.set_if_exists(
                    mdl=mdl,
                    key=magnitude_key,
                    value=float(np.abs(voltage_vector[phase_index])),
                    persist_after_native_init=True,
                )

            sizing_mapping: Dict[VarPowerFlowReferenceType, Var | None] | None = _get_external_mapping_local(self, mdl)
            sizing_var: Var | None = None
            if sizing_mapping is None:
                pass
            else:
                sizing_var = sizing_mapping.get(VarPowerFlowReferenceType.VmSizing, None)
            if sizing_var is None:
                pass
            else:
                # This runs before super/finalization, so resolve the current
                # declaration in its owner instead of reading later flat values.
                sizing_owner: Block | None = _find_event_var_owner(mdl, sizing_var)
                sizing_error: str
                if sizing_owner is None:
                    sizing_error = (
                        f"EMT sizing reference '{sizing_var.name}' on '{injection.name}' "
                        "must be declared as a runtime parameter"
                    )
                    self.logger.add_error(sizing_error, device=injection.name)
                    raise ValueError(sizing_error)
                else:
                    pass
                sizing_vm: float
                if np.isfinite(operating_vm) and operating_vm > 0.0:
                    sizing_vm = operating_vm
                elif operating_vm == 0.0:
                    declared_nominal: Expr | None = None
                    owner_var: Var
                    owner_expression: Expr
                    for owner_var, owner_expression in sizing_owner.event_dict.items():
                        if owner_var.uid == sizing_var.uid:
                            declared_nominal = owner_expression
                        else:
                            pass
                    nominal_vm: float | None = None
                    if (
                            isinstance(declared_nominal, Const)
                            and isinstance(declared_nominal.value, (int, float, np.integer, np.floating))
                            and not isinstance(declared_nominal.value, (bool, np.bool_))
                    ):
                        nominal_vm = float(declared_nominal.value)
                    else:
                        pass
                    if nominal_vm is not None and np.isfinite(nominal_vm) and nominal_vm > 0.0:
                        sizing_vm = nominal_vm
                        self.logger.add_warning(
                            "EMT impedance sizing uses declared nominal at zero PF voltage",
                            device=injection.name,
                            value=operating_vm,
                            expected_value=nominal_vm,
                            comment=sizing_var.name,
                        )
                    else:
                        sizing_error = (
                            f"EMT sizing reference '{sizing_var.name}' on '{injection.name}' "
                            f"in block '{sizing_owner.name}' requires a finite positive "
                            "declared nominal at zero PF voltage"
                        )
                        self.logger.add_error(sizing_error, device=injection.name)
                        raise ValueError(sizing_error)
                else:
                    sizing_error = (
                        f"EMT sizing reference '{sizing_var.name}' on '{injection.name}' "
                        "requires a finite operating PF voltage magnitude"
                    )
                    self.logger.add_error(sizing_error, device=injection.name)
                    raise ValueError(sizing_error)
                # Reuse the synchronized temporary/native replay stores. Neither
                # the operating seeds nor the persisted nominal is overwritten.
                self.set_if_exists(
                    mdl=mdl,
                    key=VarPowerFlowReferenceType.VmSizing,
                    value=sizing_vm,
                    persist_after_native_init=True,
                )

            if (
                    injection.device_type == DeviceType.GeneratorDevice
                    and generator_battery_count_same_bus <= 1
            ):
                preserve_generator_current_seed = False
            else:
                preserve_generator_current_seed = True

            phase_index: int = 0
            p_total: float = 0.0
            q_total: float = 0.0

            current_keys: List[VarPowerFlowReferenceType] = list([
                VarPowerFlowReferenceType.i_N,
                VarPowerFlowReferenceType.i_A,
                VarPowerFlowReferenceType.i_B,
                VarPowerFlowReferenceType.i_C,
            ])
            active_power_keys: List[VarPowerFlowReferenceType] = list([
                VarPowerFlowReferenceType.P_N,
                VarPowerFlowReferenceType.P_A,
                VarPowerFlowReferenceType.P_B,
                VarPowerFlowReferenceType.P_C,
            ])
            reactive_power_keys: List[VarPowerFlowReferenceType] = list([
                VarPowerFlowReferenceType.Q_N,
                VarPowerFlowReferenceType.Q_A,
                VarPowerFlowReferenceType.Q_B,
                VarPowerFlowReferenceType.Q_C,
            ])

            while phase_index < 4:
                phase_voltage: complex = complex(voltage_vector[phase_index])
                phase_complex_power: complex = complex(phase_power[phase_index])

                if abs(phase_voltage) > 1.0e-12:
                    # Phase powers use Sbase; conductor currents use the three-phase Ibase.
                    phase_current: complex = 3.0 * np.conj(phase_complex_power / phase_voltage)
                else:
                    phase_current = 0.0 + 0.0j

                phase_current_vector[phase_index] = phase_current
                current_instantaneous: float = float(np.sqrt(2.0) * np.imag(phase_current))

                self.set_if_exists(
                    mdl=mdl,
                    key=current_keys[phase_index],
                    value=current_instantaneous,
                    persist_after_native_init=preserve_generator_current_seed,
                )
                self.set_if_exists(
                    mdl=mdl,
                    key=active_power_keys[phase_index],
                    value=float(np.real(phase_complex_power)),
                )
                self.set_if_exists(
                    mdl=mdl,
                    key=reactive_power_keys[phase_index],
                    value=float(np.imag(phase_complex_power)),
                )

                p_total += float(np.real(phase_complex_power))
                q_total += float(np.imag(phase_complex_power))
                phase_index += 1

            if injection.device_type == DeviceType.GeneratorDevice:
                self._warn_balanced_thevenin_operating_point(
                    injection, mdl, voltage_vector, phase_current_vector,
                )
                # Transport the already converted phase phasors to models
                # declaring these PF references. Runtime initialization needs
                # both quadratures to reconstruct each internal voltage and
                # the periodic current derivative on the same phase base.
                quadrature_keys: tuple[tuple[VarPowerFlowReferenceType, ...], ...] = (
                    (VarPowerFlowReferenceType.UR_A, VarPowerFlowReferenceType.UR_B, VarPowerFlowReferenceType.UR_C),
                    (VarPowerFlowReferenceType.UI_A, VarPowerFlowReferenceType.UI_B, VarPowerFlowReferenceType.UI_C),
                    (VarPowerFlowReferenceType.IR_A, VarPowerFlowReferenceType.IR_B, VarPowerFlowReferenceType.IR_C),
                    (VarPowerFlowReferenceType.II_A, VarPowerFlowReferenceType.II_B, VarPowerFlowReferenceType.II_C),
                )
                quadrature_values: tuple[np.ndarray, ...] = (
                    voltage_vector.real, voltage_vector.imag,
                    phase_current_vector.real, phase_current_vector.imag,
                )
                quadrature_index: int
                for quadrature_index in range(4):
                    for phase_index in range(3):
                        self.set_if_exists(
                            mdl=mdl,
                            key=quadrature_keys[quadrature_index][phase_index],
                            value=float(quadrature_values[quadrature_index][phase_index + 1]),
                        )
                self._set_vsc_pf_positive_sequence(
                    mdl=mdl,
                    VA=complex(voltage_vector[1]),
                    VB=complex(voltage_vector[2]),
                    VC=complex(voltage_vector[3]),
                    IA=complex(phase_current_vector[1]),
                    IB=complex(phase_current_vector[2]),
                    IC=complex(phase_current_vector[3]),
                )
            else:
                pass

            neutral_var = _get_external_mapping_var_if_present(
                mdl=mdl,
                key=VarPowerFlowReferenceType.i_N,
            )
            if neutral_var is not None:
                ia_var = _get_external_mapping_var_if_present(mdl=mdl, key=VarPowerFlowReferenceType.i_A)
                ib_var = _get_external_mapping_var_if_present(mdl=mdl, key=VarPowerFlowReferenceType.i_B)
                ic_var = _get_external_mapping_var_if_present(mdl=mdl, key=VarPowerFlowReferenceType.i_C)
                if ia_var is None and ib_var is None and ic_var is None:
                    pass
                else:
                    ia_inst = self._temp_init_guess.get(ia_var.uid, 0.0) if ia_var is not None else 0.0
                    ib_inst = self._temp_init_guess.get(ib_var.uid, 0.0) if ib_var is not None else 0.0
                    ic_inst = self._temp_init_guess.get(ic_var.uid, 0.0) if ic_var is not None else 0.0
                    # A grounded-star load returns phase imbalance through its
                    # internal grounding link, not the external neutral port.
                    if (injection.device_type == DeviceType.LoadDevice
                            and has_emt_internal_grounding_link(block=mdl)):
                        neutral_inst = 0.0
                    else:
                        neutral_inst = -(ia_inst + ib_inst + ic_inst)
                    self._temp_init_guess[neutral_var.uid] = float(neutral_inst)
                    self._temp_post_init_guess[neutral_var.uid] = float(neutral_inst)
            else:
                pass

            self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.P, value=p_total)
            self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Q, value=q_total)

            omega_base: float = 2.0 * np.pi * self.grid.fBase
            voltage_derivative_keys: List[VarPowerFlowReferenceType] = list([
                VarPowerFlowReferenceType.d_v_N,
                VarPowerFlowReferenceType.d_v_A,
                VarPowerFlowReferenceType.d_v_B,
                VarPowerFlowReferenceType.d_v_C,
            ])

            phase_index = 0
            while phase_index < 4:
                derivative_key: VarPowerFlowReferenceType = voltage_derivative_keys[phase_index]
                derivative_var: Optional[Any] = _get_external_mapping_var_if_present(mdl=mdl, key=derivative_key)
                if derivative_var is not None:
                    phase_voltage = complex(voltage_vector[phase_index])
                    derivative_value: float = omega_base * np.sqrt(2.0) * float(np.real(phase_voltage))
                    self.set_external_param(mdl, derivative_key, derivative_value)
                else:
                    pass
                phase_index += 1

    def _try_set_bus_pf_init(self, bus: Bus, mdl: Block, bus_index: int) -> None:
        """Seed mapped bus voltages from three-phase or balanced PF results."""
        if bus.is_dc:
            if self.power_flow_results is None:
                raise ValueError(
                    "EMT simulation with DC branches requires the non unbalanced PowerFlow to be calculated."
                )
            self.set_init_guess_and_preserve_post_init(
                mdl,
                VarPowerFlowReferenceType.Vdc,
                float(np.abs(self.power_flow_results.voltage[bus_index])),
            )
            return

        voltage_vector: np.ndarray = self._get_bus_voltage_vector(bus_index)
        omega_base: float = 2.0 * np.pi * self.grid.fBase
        phase_mappings = (
            (0, VarPowerFlowReferenceType.v_N, VarPowerFlowReferenceType.d_v_N),
            (1, VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.d_v_A),
            (2, VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.d_v_B),
            (3, VarPowerFlowReferenceType.v_C, VarPowerFlowReferenceType.d_v_C),
        )
        for phase_index, voltage_key, derivative_key in phase_mappings:
            if _get_external_mapping_var_if_present(mdl=mdl, key=voltage_key) is not None:
                phasor: complex = complex(voltage_vector[phase_index])
                self.set_init_guess_and_preserve_post_init(
                    mdl, voltage_key, float(np.sqrt(2.0) * np.imag(phasor))
                )
                self.set_diff_init_guess(
                    mdl, derivative_key, float(omega_base * np.sqrt(2.0) * np.real(phasor))
                )

    def _get_vsc_terminal_indices(self,
                                  f_bus_idx: int,
                                  t_bus_idx: int) -> Tuple[int, int, bool]:
        """
        Return ``(ac_bus_idx, dc_bus_idx, ac_is_from)`` for a VSC branch.

        The preferred detection rule is based on bus types. If the branch does
        not present the expected AC/DC split, fall back to the legacy VSC
        orientation assumption used by the PF results: from side is DC and to
        side is AC.
        """
        f_bus = self.grid.buses[f_bus_idx]
        t_bus = self.grid.buses[t_bus_idx]

        if not f_bus.is_dc and t_bus.is_dc:
            return f_bus_idx, t_bus_idx, True

        if f_bus.is_dc and not t_bus.is_dc:
            return t_bus_idx, f_bus_idx, False

        return t_bus_idx, f_bus_idx, False

    def _get_vsc_pf_powers(self, mdl: Block, ac_bus_index: int,
                           sbase: float, vsc_index: int) -> Tuple[np.ndarray, complex]:
        """Read NABC AC powers and total DC power in branch-terminal convention.

        Balanced PF splits AC power equally across ABC. PF3 retains its phase
        powers, using balanced results only when those phase powers are absent.
        """
        balanced_pf = self.power_flow_results
        three_phase_pf = self.power_flow_results_3ph
        phase_powers = _zero_ac_power_vector()
        if three_phase_pf is None:
            ac_power = _get_balanced_vsc_ac_power(balanced_pf, vsc_index) / sbase
            dc_power = _get_balanced_vsc_dc_power(balanced_pf, vsc_index) / sbase
            if _has_vsc_positive_sequence_pf_contract(mdl) and abs(ac_power) <= 1e-6:
                bus_power = -_get_connected_bus_balanced_power(balanced_pf, ac_bus_index, sbase)
                ac_power = bus_power if abs(bus_power) > 1e-12 else dc_power
            phase_powers[1:4] = ac_power / 3.0
        else:
            phase_powers[1] = three_phase_pf.St_vsc_A[vsc_index] / sbase
            phase_powers[2] = three_phase_pf.St_vsc_B[vsc_index] / sbase
            phase_powers[3] = three_phase_pf.St_vsc_C[vsc_index] / sbase
            if np.sum(np.abs(phase_powers)) < 1e-12 and balanced_pf is not None:
                ac_power = _get_balanced_vsc_ac_power(balanced_pf, vsc_index) / sbase
                phase_powers[1:4] = ac_power / 3.0
            # PF3 stores the DC transfer in Pfp_vsc; unlike balanced PF it
            # has no separate Pfn_vsc result.
            dc_power = complex(three_phase_pf.Pfp_vsc[vsc_index] / sbase)
            if abs(np.sum(phase_powers)) < 1e-12 and balanced_pf is not None:
                dc_power = _get_balanced_vsc_dc_power(balanced_pf, vsc_index) / sbase
        return phase_powers, dc_power

    def _set_vsc_pf_positive_sequence(self, mdl: Block,
                                      VA: complex, VB: complex, VC: complex,
                                      IA: complex, IB: complex, IC: complex,
                                      S_ac_total: complex | None = None) -> None:
        """Seed mapped sequence references from ABC phasors for any PF format.

        Branch callers seed their total powers separately. Injection callers
        omit S_ac_total and derive their power seed from the sequence phasors.
        """
        rotation = np.exp(2j * np.pi / 3.0)
        voltage = (VA + rotation * VB + rotation ** 2 * VC) / 3.0
        current = (IA + rotation * IB + rotation ** 2 * IC) / 3.0
        if abs(current) <= 1e-12 and S_ac_total is not None and abs(voltage) > 1e-12:
            current = np.conj(S_ac_total / voltage)

        mapping = _get_external_mapping_local(self, mdl)
        if mapping is None:
            return
        voltage_angle = float(np.angle(voltage))
        angle_difference = float(np.angle(current)) - voltage_angle
        current_angle = float(np.arctan2(np.sin(angle_difference), np.cos(angle_difference)))
        references = (
            (VarPowerFlowReferenceType.phi_v, voltage_angle),
            (VarPowerFlowReferenceType.phi, current_angle),
            (VarPowerFlowReferenceType.Vpk, float(np.sqrt(2.0) * abs(voltage))),
            (VarPowerFlowReferenceType.Ipk, float(np.sqrt(2.0) * abs(current))),
        )
        for key, value in references:
            variable = mapping.get(key)
            if variable is not None:
                self.set_external_param(mdl, key, value)
                self._temp_post_init_guess[variable.uid] = value

        if S_ac_total is None and _has_vsc_positive_sequence_pf_contract(mdl):
            export_power = -voltage * np.conj(current)
            self.set_if_exists(mdl, VarPowerFlowReferenceType.Pe, float(export_power.real))
            self.set_if_exists(mdl, VarPowerFlowReferenceType.Qe, float(export_power.imag))

    def _seed_vsc_ac_terminals(self, mdl: Block, voltages: np.ndarray,
                               currents: np.ndarray, powers: np.ndarray,
                               ac_is_from: bool) -> None:
        """Seed AC terminal mappings; leave the DC terminal's AC phases zero."""
        zero_phases = _zero_ac_power_vector()
        from_voltages = voltages if ac_is_from else zero_phases
        to_voltages = zero_phases if ac_is_from else voltages
        from_powers = powers if ac_is_from else zero_phases
        to_powers = zero_phases if ac_is_from else powers
        self._seed_branch_terminal_voltage_derivatives(mdl, from_voltages, to_voltages)
        self._seed_ac_branch_phase_powers(mdl, from_powers, to_powers)

        phase_mappings = (
            (0, VarPowerFlowReferenceType.v_N, VarPowerFlowReferenceType.i_N,
             VarPowerFlowReferenceType.if_N, VarPowerFlowReferenceType.it_N),
            (1, VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.i_A,
             VarPowerFlowReferenceType.if_A, VarPowerFlowReferenceType.it_A),
            (2, VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.i_B,
             VarPowerFlowReferenceType.if_B, VarPowerFlowReferenceType.it_B),
            (3, VarPowerFlowReferenceType.v_C, VarPowerFlowReferenceType.i_C,
             VarPowerFlowReferenceType.if_C, VarPowerFlowReferenceType.it_C),
        )
        for phase, voltage_key, current_key, from_key, to_key in phase_mappings:
            voltage_value = float(np.sqrt(2.0) * voltages[phase].imag)
            current_value = float(np.sqrt(2.0) * currents[phase].imag)
            self.set_if_exists(mdl, voltage_key, voltage_value)
            self.set_if_exists(mdl, current_key, current_value)
            self.set_if_exists(mdl, from_key, current_value if ac_is_from else 0.0)
            self.set_if_exists(mdl, to_key, 0.0 if ac_is_from else current_value)

    def _try_set_vsc_branch_pf_init(self, mdl: Block, f_bus_idx: int,
                                    t_bus_idx: int, sbase: float, vsc_index: int) -> None:
        """Read PF values, calculate phasors, then seed VSC terminal/control mappings."""
        if self.power_flow_results_3ph is None and self.power_flow_results is None:
            return

        # Read terminal voltages and powers in the PF branch convention.
        ac_bus, dc_bus, ac_is_from = self._get_vsc_terminal_indices(f_bus_idx, t_bus_idx)
        voltages = self._get_bus_voltage_vector(ac_bus)
        voltages[0] = 0.0  # VSC templates have no neutral-terminal PF seed.
        phase_powers, dc_power = self._get_vsc_pf_powers(mdl, ac_bus, sbase, vsc_index)
        ac_power = complex(np.sum(phase_powers))
        uses_positive_sequence = _has_vsc_positive_sequence_pf_contract(mdl)

        # All network terminal currents use the system three-phase current base.
        currents = get_currents_from_power(voltages, phase_powers, 3.0)
        if self.power_flow_results_3ph is not None:
            if np.sum(np.abs(currents)) <= 1e-12 and abs(voltages[1]) > 1e-12:
                phase_a_current = np.conj(ac_power / voltages[1])
                for phase in range(1, 4):
                    currents[phase] = phase_a_current * _phase_sequence_shift(phase)

        # Apply the phasors to mappings; native model equations own internal states.
        self._seed_vsc_ac_terminals(mdl, voltages, currents, phase_powers, ac_is_from)
        self._set_vsc_pf_positive_sequence(
            mdl, voltages[1], voltages[2], voltages[3],
            currents[1], currents[2], currents[3], S_ac_total=ac_power,
        )
        if self.power_flow_results is not None:
            dc_voltage = float(abs(self.power_flow_results.voltage[dc_bus]))
            dc_current = float(dc_power.real / dc_voltage) if dc_voltage > 1e-12 else 0.0
            self.set_if_exists(mdl, VarPowerFlowReferenceType.Vdc, dc_voltage,
                               persist_after_native_init=True)
            self.set_if_exists(mdl, VarPowerFlowReferenceType.If_dc, dc_current,
                               persist_after_native_init=True)

        # GFM references use converter export, opposite to AC branch flow.
        reference_power = -ac_power if uses_positive_sequence else ac_power
        if uses_positive_sequence:
            self.set_if_exists(mdl, VarPowerFlowReferenceType.Pe, float(reference_power.real))
            self.set_if_exists(mdl, VarPowerFlowReferenceType.Qe, float(reference_power.imag))
        self.set_if_exists(mdl, VarPowerFlowReferenceType.P, float(reference_power.real))
        self.set_if_exists(mdl, VarPowerFlowReferenceType.Q, float(reference_power.imag))
        # Voltage-controlled converters need solved DC transfer as feedforward,
        # even when their static API P0 is zero.
        self._assign_event_mapping_value_if_present(
            mdl=mdl, key=ParamPowerFlowReferenceType.P0, value=float(-dc_power.real * sbase),
        )
        from_power = ac_power if ac_is_from else dc_power
        to_power = dc_power if ac_is_from else ac_power
        self._seed_branch_terminal_powers(mdl, from_power, to_power)

    def _try_set_dc_branch_pf_init(
            self,
            mdl: Block,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            sbase: float,
    ) -> None:
        """
        Initialize a two-terminal DC branch from the balanced PF snapshot.

        The DC EMT branch contract uses explicit terminal voltages ``Vf_dc`` /
        ``Vt_dc`` and terminal currents ``If_dc`` / ``It_dc`` so that generic
        branch models such as valves or DC lines can derive their initial state
        from both connected buses.
        """
        pf_results = self.power_flow_results
        if pf_results is None:
            return

        eps: float = 1.0e-12
        preserve_dc_current_seed: bool = (
                _get_external_mapping_var_if_present(mdl=mdl, key=VarPowerFlowReferenceType.DcPathModeSeed) is None
        )

        try:
            v_f: float = float(np.abs(pf_results.voltage[f_bus_idx]))
        except (AttributeError, IndexError, TypeError, ValueError):
            v_f = 0.0

        try:
            v_t: float = float(np.abs(pf_results.voltage[t_bus_idx]))
        except (AttributeError, IndexError, TypeError, ValueError):
            v_t = 0.0

        try:
            s_f: complex = complex(pf_results.Sf[branch_index]) / sbase
        except (AttributeError, IndexError, TypeError, ValueError):
            s_f = 0.0 + 0.0j

        try:
            s_t: complex = complex(pf_results.St[branch_index]) / sbase
        except (AttributeError, IndexError, TypeError, ValueError):
            s_t = 0.0 + 0.0j

        i_f: float = float(np.real(s_f) / v_f) if abs(v_f) > eps else 0.0
        i_t: float = float(np.real(s_t) / v_t) if abs(v_t) > eps else 0.0
        path_mode_seed_var_present: bool = (
                _get_external_mapping_var_if_present(mdl=mdl, key=VarPowerFlowReferenceType.DcPathModeSeed) is not None
        )

        if abs(s_f) <= eps and abs(s_t) <= eps:
            # Some compact balanced DC PF cases leave the dedicated branch-flow
            # arrays effectively zero even though the connected DC injections
            # imply one non-zero transfer through the corridor. Reconstruct the
            # branch seed from the terminal net powers so both valve hosts and
            # lightweight DC lines start from a conductive operating point.
            from_bus_power: complex = _get_connected_bus_balanced_power(
                pf_results=pf_results,
                bus_index=f_bus_idx,
                sbase=sbase,
            )
            to_bus_power: complex = _get_connected_bus_balanced_power(
                pf_results=pf_results,
                bus_index=t_bus_idx,
                sbase=sbase,
            )
            from_bus_p: float = float(np.real(from_bus_power))
            to_bus_p: float = float(np.real(to_bus_power))
            inferred_branch_power: float = 0.0

            if abs(from_bus_p) > eps:
                inferred_branch_power = from_bus_p
            else:
                if abs(to_bus_p) > eps:
                    inferred_branch_power = -to_bus_p
                else:
                    inferred_branch_power = 0.0

            if abs(inferred_branch_power) > eps and abs(v_f) > eps:
                i_f = float(inferred_branch_power / v_f)
                i_t = -i_f
                s_f = complex(v_f * i_f, 0.0)
                s_t = complex(v_t * i_t, 0.0)
            else:
                if path_mode_seed_var_present:
                    if abs(from_bus_p) > eps:
                        if from_bus_p > 0.0:
                            i_f = 1.0
                            i_t = -1.0
                        else:
                            i_f = -1.0
                            i_t = 1.0
                    else:
                        if abs(to_bus_p) > eps:
                            if to_bus_p < 0.0:
                                i_f = 1.0
                                i_t = -1.0
                            else:
                                i_f = -1.0
                                i_t = 1.0
                        else:
                            # A valve host started from PF needs one definite
                            # conduction direction instead of the blocked state
                            # when the surrounding compact DC corridor leaves the
                            # balanced branch powers empty.
                            i_f = 1.0
                            i_t = -1.0
                else:
                    pass
        else:
            pass

        if abs(i_f) > eps:
            path_mode_seed: float = 1.0 if i_f >= 0.0 else -1.0
        else:
            if (v_f - v_t) > eps:
                path_mode_seed = 1.0
            else:
                if (v_f - v_t) < -eps:
                    path_mode_seed = -1.0
                else:
                    path_mode_seed = 0.0

        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Vf_dc, value=v_f, persist_after_native_init=True)
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Vt_dc, value=v_t, persist_after_native_init=True)
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.DcPathModeSeed, value=path_mode_seed, persist_after_native_init=True)
        path_mode_seed_var: Optional[Any] = _get_external_mapping_var_if_present(mdl=mdl, key=VarPowerFlowReferenceType.DcPathModeSeed)
        if isinstance(path_mode_seed_var, Var):
            self._set_runtime_parameter_seed_by_uid(
                uid=path_mode_seed_var.uid,
                value=float(path_mode_seed),
                persist_after_native_init=True,
            )
        else:
            pass
        self.set_if_exists(
            mdl=mdl,
            key=VarPowerFlowReferenceType.If_dc,
            value=i_f,
            persist_after_native_init=preserve_dc_current_seed,
        )
        self.set_if_exists(
            mdl=mdl,
            key=VarPowerFlowReferenceType.It_dc,
            value=i_t,
            persist_after_native_init=preserve_dc_current_seed,
        )
        self.set_if_exists(
            mdl=mdl,
            key=VarPowerFlowReferenceType.Idc,
            value=i_f,
            persist_after_native_init=preserve_dc_current_seed,
        )
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Pf, value=float(np.real(s_f)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Qf, value=float(np.imag(s_f)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Pt, value=float(np.real(s_t)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Qt, value=float(np.imag(s_t)))

    def _seed_branch_terminal_voltage_derivatives(
            self,
            mdl: Block,
            from_voltages: np.ndarray,
            to_voltages: np.ndarray,
    ) -> None:
        """Seed mapped branch terminal voltage derivatives from NABC phasors."""
        omega_base: float = 2.0 * np.pi * self.grid.fBase
        phase_mappings = (
            (0, VarPowerFlowReferenceType.d_v_N_f, VarPowerFlowReferenceType.d_v_N_t),
            (1, VarPowerFlowReferenceType.d_v_A_f, VarPowerFlowReferenceType.d_v_A_t),
            (2, VarPowerFlowReferenceType.d_v_B_f, VarPowerFlowReferenceType.d_v_B_t),
            (3, VarPowerFlowReferenceType.d_v_C_f, VarPowerFlowReferenceType.d_v_C_t),
        )
        for phase_index, from_key, to_key in phase_mappings:
            if _get_external_mapping_var_if_present(mdl=mdl, key=from_key) is not None:
                value: float = float(omega_base * np.sqrt(2.0) * np.real(from_voltages[phase_index]))
                self.set_external_param(mdl, from_key, value)
            if _get_external_mapping_var_if_present(mdl=mdl, key=to_key) is not None:
                value = float(omega_base * np.sqrt(2.0) * np.real(to_voltages[phase_index]))
                self.set_external_param(mdl, to_key, value)

    def _seed_branch_terminal_powers(self, mdl: Block, from_power: complex, to_power: complex) -> None:
        """Seed mapped aggregate power references at both branch terminals."""
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Pf, value=float(np.real(from_power)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Qf, value=float(np.imag(from_power)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Pt, value=float(np.real(to_power)))
        self.set_if_exists(mdl=mdl, key=VarPowerFlowReferenceType.Qt, value=float(np.imag(to_power)))

    def _seed_branch_phase_currents(
            self,
            mdl: Block,
            from_currents: np.ndarray,
            to_currents: np.ndarray,
            preserve_current_seed: bool,
            has_physical_g: bool,
    ) -> None:
        """Apply terminal currents with the PF projection's persistence policy.

        Balanced currents computed from a nonzero line impedance survive native
        initialization. PF3 and balanced power-derived currents are guesses only.
        Physical shunt conductance supplies the neutral current; otherwise derive
        it from the phase sum and leave that neutral seed free to be initialized.
        """
        phase_mappings = (
            (0, VarPowerFlowReferenceType.if_N, VarPowerFlowReferenceType.it_N),
            (1, VarPowerFlowReferenceType.if_A, VarPowerFlowReferenceType.it_A),
            (2, VarPowerFlowReferenceType.if_B, VarPowerFlowReferenceType.it_B),
            (3, VarPowerFlowReferenceType.if_C, VarPowerFlowReferenceType.it_C),
        )
        for phase_index, from_key, to_key in phase_mappings:
            from_value: float = float(np.sqrt(2.0) * np.imag(from_currents[phase_index]))
            to_value: float = float(np.sqrt(2.0) * np.imag(to_currents[phase_index]))
            self.set_if_exists(mdl=mdl, key=from_key, value=from_value,
                               persist_after_native_init=preserve_current_seed)
            self.set_if_exists(mdl=mdl, key=to_key, value=to_value,
                               persist_after_native_init=preserve_current_seed)

        if has_physical_g:
            return
        neutral_mappings = (
            (VarPowerFlowReferenceType.if_N, from_currents),
            (VarPowerFlowReferenceType.it_N, to_currents),
        )
        for neutral_key, phase_currents in neutral_mappings:
            if _get_external_mapping_var_if_present(mdl=mdl, key=neutral_key) is not None:
                neutral_current: complex = -sum(
                    phase_currents[1:4],
                    0.0 + 0.0j,
                )
                neutral_value: float = float(np.sqrt(2.0) * np.imag(neutral_current))
                self.set_if_exists(mdl=mdl, key=neutral_key, value=neutral_value,
                                   persist_after_native_init=False)

    def _seed_ac_branch_phase_powers(
            self,
            mdl: Block,
            from_powers: np.ndarray,
            to_powers: np.ndarray,
    ) -> Tuple[complex, complex]:
        """Seed available NABC phase powers and return the mapped terminal totals."""
        phase_keys = (
            (1, VarPowerFlowReferenceType.Sf_A, VarPowerFlowReferenceType.St_A),
            (2, VarPowerFlowReferenceType.Sf_B, VarPowerFlowReferenceType.St_B),
            (3, VarPowerFlowReferenceType.Sf_C, VarPowerFlowReferenceType.St_C),
        )
        from_total = 0.0 + 0.0j
        to_total = 0.0 + 0.0j
        for phase_index, from_key, to_key in phase_keys:
            from_power = from_powers[phase_index]
            to_power = to_powers[phase_index]
            if not np.isnan(from_power) and _get_external_mapping_var_if_present(mdl, from_key) is not None:
                self.set_if_exists(mdl, from_key, float(np.real(from_power)))
                from_total += from_power
            if not np.isnan(to_power) and _get_external_mapping_var_if_present(mdl, to_key) is not None:
                self.set_if_exists(mdl, to_key, float(np.real(to_power)))
                to_total += to_power
        return from_total, to_total

    def _try_set_branch_pf_init(
            self,
            mdl: Block,
            branch: BranchParent,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            sbase: float,
            static_parameter_values_mapping: Dict[Var, Const],
    ) -> None:
        """Seed an ordinary branch from three-phase or balanced power flow."""
        if self.power_flow_results_3ph is None and self.power_flow_results is None:
            return
        if self.grid.buses[f_bus_idx].is_dc or self.grid.buses[t_bus_idx].is_dc:
            self._try_set_dc_branch_pf_init(
                mdl=mdl, branch_index=branch_index,
                f_bus_idx=f_bus_idx, t_bus_idx=t_bus_idx, sbase=sbase,
            )
            return

        from_voltages, to_voltages = self.get_branch_voltages(f_bus_idx, t_bus_idx)
        shunt_conductance: np.ndarray = np.zeros((4, 4), dtype=np.float64)
        damping_conductance: float = 0.0
        project_balanced_line: bool = self.power_flow_results_3ph is None and isinstance(branch, Line)
        if project_balanced_line:
            shunt_conductance, damping_conductance = self._get_branch_emt_conductances(
                mdl, static_parameter_values_mapping,
            )
        else:
            pass
        virtual_taps: np.ndarray = np.ones(2, dtype=float)
        if project_balanced_line:
            for owner in mdl.get_all_blocks():
                for terminal, reference in enumerate((ParamPowerFlowReferenceType.vtap_f, ParamPowerFlowReferenceType.vtap_t)):
                    parameter = owner.api_obj_mapping.get(reference, None)
                    if parameter is not None:
                        value = get_api_parameter_initial_value_by_uid(parameter, static_parameter_values_mapping)
                        if value is None:
                            value = owner.parameters[parameter]
                        else:
                            pass
                        if value.value is not None and np.isfinite(float(value.value)) and float(value.value) > 0.0:
                            virtual_taps[terminal] = float(value.value)
                        else:
                            self.logger.add_warning(msg="Missing or invalid line virtual tap; using structural identity.",
                                                    device=mdl.name, value=parameter.name)
                    else:
                        pass
        else:
            pass
        from_currents, to_currents = self.get_branch_currents(
            branch_index, from_voltages, to_voltages, sbase,
            branch=branch, shunt_conductance=shunt_conductance,
            damping_conductance=damping_conductance,
            virtual_tap_from=virtual_taps[0], virtual_tap_to=virtual_taps[1],
        )
        from_powers, to_powers = self.get_branch_powers(branch_index, sbase)
        from_power, to_power = self._seed_ac_branch_phase_powers(mdl, from_powers, to_powers)
        self._seed_branch_phase_currents(
            mdl, from_currents, to_currents,
            preserve_current_seed=project_balanced_line and abs(complex(branch.R, branch.X)) > 1e-15,
            has_physical_g=bool(np.any(shunt_conductance != 0.0)),
        )
        self._seed_branch_terminal_voltage_derivatives(mdl, from_voltages, to_voltages)
        self._seed_branch_terminal_powers(mdl, from_power, to_power)

    def get_branch_powers(
            self, branch_index: int, sbase: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return complex NABC terminal powers on the total three-phase Sbase.

        PF3 supplies each phase separately; balanced PF totals are divided
        equally among A/B/C. Neutral power is zero. Missing PF3 phase entries
        are NaN, which the seed setter skips; a present zero is still applied.
        The caller must provide a PF result.
        """
        from_powers = np.zeros(4, dtype=np.complex128)
        to_powers = np.zeros(4, dtype=np.complex128)
        pf3 = self.power_flow_results_3ph
        if pf3 is not None:
            phase_powers = ((pf3.Sf_A, pf3.St_A), (pf3.Sf_B, pf3.St_B), (pf3.Sf_C, pf3.St_C))
            for phase_index, (from_phase, to_phase) in enumerate(phase_powers, start=1):
                sf = _get_array_entry_if_in_range(from_phase, branch_index)
                st = _get_array_entry_if_in_range(to_phase, branch_index)
                from_powers[phase_index] = np.nan if sf is None else complex(sf / sbase)
                to_powers[phase_index] = np.nan if st is None else complex(st / sbase)
        else:
            pf = self.power_flow_results
            from_powers[1:4] = complex(pf.Sf[branch_index] / (3.0 * sbase))
            to_powers[1:4] = complex(pf.St[branch_index] / (3.0 * sbase))
        return from_powers, to_powers

    def get_branch_voltages(self, f_bus_idx: int, t_bus_idx: int) -> Tuple[np.ndarray, np.ndarray]:
        """Return branch terminal phasors in NABC order from the available PF."""
        return self._get_bus_voltage_vector(f_bus_idx), self._get_bus_voltage_vector(t_bus_idx)

    def get_branch_currents(
            self, branch_index: int, from_voltages: np.ndarray,
            to_voltages: np.ndarray, sbase: float,
            branch: BranchParent,
            shunt_conductance: Optional[np.ndarray] = None,
            damping_conductance: float = 0.0,
            virtual_tap_from: float = 1.0, virtual_tap_to: float = 1.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return complex NABC terminal currents from the available PF.

        Balanced AC lines use the supplied static device and EMT conductances.
        Other branches and PF3 use terminal powers from the PF results.

        Currents use the phase current base Sbase / (sqrt(3) * Vbase_LL).
        PF3 phase powers are on the total three-phase Sbase, hence their
        current calculation includes a factor of three.
        """
        pf3 = self.power_flow_results_3ph
        phases = ("N", "A", "B", "C")
        from_currents = np.zeros(4, dtype=np.complex128)
        to_currents = np.zeros(4, dtype=np.complex128)
        if pf3 is not None:
            from_powers, to_powers = self.get_branch_powers(branch_index, sbase)
            from_currents[1:] = get_currents_from_power(from_voltages[1:], from_powers[1:], 3.0)
            to_currents[1:] = get_currents_from_power(to_voltages[1:], to_powers[1:], 3.0)
            return from_currents, to_currents

        pf = self.power_flow_results
        # Only static AC lines have the scalar PI representation used here.
        # Other branch types retain the currents from their own PF terminal powers.
        z_series: complex = complex(branch.R, branch.X) if isinstance(branch, Line) else 0.0j
        b_shunt: float = float(branch.B) if isinstance(branch, Line) else 0.0
        g_damp: float = damping_conductance
        physical_f: np.ndarray = np.zeros(4, dtype=np.complex128)
        physical_t: np.ndarray = np.zeros(4, dtype=np.complex128)
        if shunt_conductance is not None:
            physical_f = shunt_conductance @ from_voltages / virtual_tap_from ** 2
            physical_t = shunt_conductance @ to_voltages / virtual_tap_to ** 2
        else:
            pass
        for index, phase in enumerate(phases):
            vf, vt = from_voltages[index], to_voltages[index]
            if phase == "N":
                i_f, i_t = physical_f[index], physical_t[index]
            elif abs(z_series) > 1e-15:
                i_ser = (vf / virtual_tap_from - vt / virtual_tap_to) / z_series
                i_f = i_ser / virtual_tap_from + 1j * b_shunt / 2.0 * vf / virtual_tap_from ** 2 + physical_f[index] + g_damp * vf
                i_t = -i_ser / virtual_tap_to + 1j * b_shunt / 2.0 * vt / virtual_tap_to ** 2 + physical_t[index] + g_damp * vt
            else:
                i_f = 0.0j if abs(vf) <= 1e-12 else np.conj(pf.Sf[branch_index] / sbase / vf)
                i_t = 0.0j if abs(vt) <= 1e-12 else np.conj(pf.St[branch_index] / sbase / vt)
            from_currents[index], to_currents[index] = complex(i_f), complex(i_t)
        return from_currents, to_currents

    def _get_branch_emt_conductances(
            self, mdl: Block,
            static_parameter_values_mapping: Dict[Var, Const],
    ) -> Tuple[np.ndarray, float]:
        """Read the conductances applied by the EMT model.

        :param mdl: Working EMT branch model.
        :param static_parameter_values_mapping: Resolved static parameter values.
        :return: Physical NABC shunt conductance and additional damping conductance.
        """
        g_nabc = np.zeros((4, 4), dtype=np.float64)
        g_keys = get_line_g_keys()
        for owner in mdl.get_all_blocks():
            for row in range(4):
                for col in range(4):
                    parameter = owner.api_obj_mapping.get(g_keys[row][col])
                    if parameter is not None:
                        value = get_api_parameter_initial_value_by_uid(parameter, static_parameter_values_mapping)
                        if value is None:
                            value = owner.parameters[parameter]
                        if value.value is None:
                            self.logger.add_warning(
                                msg="Missing optional physical line conductance; using template zero shunt.",
                                device=mdl.name, value=parameter.name,
                            )
                        else:
                            g_nabc[row, col] = float(value.value)
        g_damp = 0.0
        for owner in mdl.get_all_blocks():
            for parameter, value in owner.parameters.items():
                if parameter.name == "G_damp":
                    g_damp = float(value.value)
        return g_nabc, g_damp

    def _get_history_line_pf_phasors(
            self, active_phases: List[str], branch_index: int,
            f_bus_idx: int, t_bus_idx: int, sbase: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return terminal V/I phasors in a history line's active-phase order.

        Shared PF readers supply per-phase powers on the total system base,
        so I = 3*conj(S_phase/V) for both balanced and PF3 results. History
        models use PF terminal powers, not PI-line impedance currents.
        Retain available neutral voltage and initialize neutral current to zero.
        """
        from_voltages, to_voltages = self.get_branch_voltages(f_bus_idx, t_bus_idx)
        from_powers, to_powers = self.get_branch_powers(branch_index, sbase)
        phase_order = {"N": 0, "A": 1, "B": 2, "C": 3}
        try:
            phase_indices = [phase_order[phase] for phase in active_phases]
        except KeyError as exc:
            raise ValueError(f"Unsupported phase labels in history line: {active_phases}") from exc
        v_f_phasor = from_voltages[phase_indices]
        v_t_phasor = to_voltages[phase_indices]
        from_currents = get_currents_from_power(from_voltages, from_powers, 3.0)
        to_currents = get_currents_from_power(to_voltages, to_powers, 3.0)
        from_currents[0] = 0.0
        to_currents[0] = 0.0
        i_f_phasor = from_currents[phase_indices]
        i_t_phasor = to_currents[phase_indices]
        return v_f_phasor, v_t_phasor, i_f_phasor, i_t_phasor

    def _try_set_bergeron_pf_init(
            self,
            rt: BergeronHistoryRuntime,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            sbase: float,
    ) -> None:
        """Seed Bergeron history sources and delay buffers from PF phasors."""
        v_f_phasor, v_t_phasor, i_f_phasor, i_t_phasor = self._get_history_line_pf_phasors(
            rt.active_ph, branch_index, f_bus_idx, t_bus_idx, sbase,
        )
        Ih_f0_red = np.sqrt(2.0) * (i_f_phasor.imag - rt.Gc_red @ v_f_phasor.imag)
        Ih_t0_red = np.sqrt(2.0) * (i_t_phasor.imag - rt.Gc_red @ v_t_phasor.imag)

        for k in range(rt.m):
            # PF projection precedes runtime UID indexing. Preserve these seeds
            # through runtime-vector construction and the final init replay.
            self._set_runtime_parameter_seed_by_uid(
                uid=rt.Ih_f[k].uid, value=float(Ih_f0_red[k]), persist_after_native_init=True,
            )
            self._set_runtime_parameter_seed_by_uid(
                uid=rt.Ih_t[k].uid, value=float(Ih_t0_red[k]), persist_after_native_init=True,
            )
        rt.initialize_buffers_from_phasors(
            v_f=v_f_phasor, v_t=v_t_phasor, i_f=i_f_phasor, i_t=i_t_phasor,
            frequency_hz=self.grid.fBase,
        )

    def _try_set_jmarti_pf_init(
            self,
            rt: JMartiHistoryRuntime,
            branch_index: int,
            f_bus_idx: int,
            t_bus_idx: int,
            sbase: float,
    ) -> None:
        """Initialize JMarti filters and delay histories from balanced or PF3 data."""
        if rt.coupling_block is not None and self.power_flow_results_3ph is not None:
            pf3 = self.power_flow_results_3ph
            voltage_arrays = dict(N=pf3.voltage_N, A=pf3.voltage_A, B=pf3.voltage_B, C=pf3.voltage_C)
            from_power_arrays = dict(A=pf3.Sf_A, B=pf3.Sf_B, C=pf3.Sf_C)
            to_power_arrays = dict(A=pf3.St_A, B=pf3.St_B, C=pf3.St_C)
            for phase in rt.active_ph:
                if voltage_arrays[phase] is None:
                    return
                elif phase != "N" and (from_power_arrays[phase] is None or to_power_arrays[phase] is None):
                    return
                else:
                    pass
        else:
            pass
        v_f, v_t, i_f, i_t = self._get_history_line_pf_phasors(
            rt.active_ph, branch_index, f_bus_idx, t_bus_idx, sbase,
        )
        ih_f_phase, ih_t_phase = rt.initialize_from_fundamental_phasors(
            v_f0_phasor_red=v_f,
            v_t0_phasor_red=v_t,
            i_f0_phasor_red=i_f,
            i_t0_phasor_red=i_t,
            system_frequency_hz=float(self.grid.fBase),
        )
        for phase_index in range(rt.m):
            self._set_runtime_parameter_seed_by_uid(
                uid=rt.Ih_f[phase_index].uid,
                value=float(np.real(ih_f_phase[phase_index])),
                persist_after_native_init=True,
            )
            self._set_runtime_parameter_seed_by_uid(
                uid=rt.Ih_t[phase_index].uid,
                value=float(np.real(ih_t_phase[phase_index])),
                persist_after_native_init=True,
            )

    # ---------------------------------------------------------------------
    # UTILS
    # ---------------------------------------------------------------------
    def set_if_exists(self,
                      mdl: Block,
                      key: VarPowerFlowReferenceType,
                      value: float,
                      persist_after_native_init: bool = False) -> None:
        """
        Set an initialization value only if the external mapping contains the key.

        :param mdl: Model block containing the external mapping.
        :param key: External mapping key.
        :param value: Initialization value.
        :param persist_after_native_init: Preserve the mapped guess after native initialization.
        :return: None
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(self, mdl)
        owner_block: Optional[Block]

        if external_mapping is None:
            pass
        else:
            mapped_var: Optional[Var] = external_mapping.get(key, None)

            if mapped_var is None:
                pass
            else:
                runtime_idx: int | None = None
                runtime_idx = self._uid2idx_event_params.get(mapped_var.uid, None)

                if runtime_idx is not None:
                    self._set_runtime_parameter_seed_by_uid(
                        uid=mapped_var.uid,
                        value=float(value),
                        persist_after_native_init=persist_after_native_init,
                    )
                else:
                    # GUI wrapper roots may expose one PF reference whose mutable
                    # runtime storage actually belongs to a nested child block.
                    # The assignment must therefore target the block that owns the
                    # ``event_dict`` entry instead of assuming root ownership.
                    owner_block = _find_event_var_owner(mdl, mapped_var)
                    if owner_block is None:
                        value_float: float = float(value)
                        self._temp_init_guess[mapped_var.uid] = value_float
                        if persist_after_native_init or runtime_idx is None:
                            self._temp_post_init_guess[mapped_var.uid] = value_float
                        else:
                            pass
                    else:
                        if runtime_idx is None:
                            runtime_idx_local: int | None = self.uid2idx_event_params.get(mapped_var.uid, None)
                        else:
                            runtime_idx_local = runtime_idx
                        if runtime_idx_local is None:
                            value_float = float(value)
                            self._temp_init_guess[mapped_var.uid] = value_float
                            self._temp_post_init_guess[mapped_var.uid] = value_float
                        else:
                            self._set_runtime_parameter_value_by_uid(uid=mapped_var.uid, value=float(value))
                        if persist_after_native_init or runtime_idx_local is None:
                            self._temp_post_init_guess[mapped_var.uid] = float(value)
                        else:
                            pass

    def _set_runtime_parameter_value_by_uid(self, uid: int, value: float) -> None:
        """
        Update one runtime parameter through the problem-local EMT runtime store.

        :param uid: Runtime-parameter UID.
        :param value: Runtime value.
        :return: None.
        """
        runtime_idx: Optional[int]

        runtime_idx = self._uid2idx_event_params.get(uid, None)
        if runtime_idx is not None:
            resolved_expression: Const = Const(float(value))
            self._event_params_values[runtime_idx] = float(value)
            self._event_parameters_eqs[runtime_idx] = resolved_expression

            # ``def_event_params_fn()`` evaluates the finalized continuous/mode
            # partition rather than ``_event_parameters_eqs`` directly. Keep
            # that numerical view synchronized as part of the same atomic
            # problem-local update so native initialization consumes the PF seed.
            continuous_parameter_count: int = len(self._runtime_continuous_eqs)
            if runtime_idx < continuous_parameter_count:
                self._runtime_continuous_eqs[runtime_idx] = resolved_expression
                # The compiled kernel inlines the continuous equations it was generated
                # from; drop it so the next compiled evaluation rebuilds it from the
                # updated equation instead of returning the previous value.
                self._runtime_parameter_kernel = None
            else:
                mode_index: int = runtime_idx - continuous_parameter_count
                if mode_index < len(self._runtime_mode_eqs):
                    self._runtime_mode_eqs[mode_index] = resolved_expression
                else:
                    pass

            runtime_eqs0: Any = self._runtime_parameter_eqs0
            if isinstance(runtime_eqs0, list) and runtime_idx < len(runtime_eqs0):
                runtime_eqs0[runtime_idx] = resolved_expression
            else:
                pass

            runtime_source_parameters: Any = self._runtime_all_parameters_source
            runtime_source_equations: Any = self._runtime_all_eqs_source
            if isinstance(runtime_source_parameters, list) and isinstance(runtime_source_equations, list):
                source_index: int = 0
                while source_index < len(runtime_source_parameters):
                    runtime_parameter: Any = runtime_source_parameters[source_index]
                    if isinstance(runtime_parameter, Var) and runtime_parameter.uid == uid:
                        runtime_source_equations[source_index] = resolved_expression
                    else:
                        pass
                    source_index += 1
            else:
                pass

    def _set_runtime_parameter_seed_by_uid(self, uid: int, value: float, persist_after_native_init: bool = False) -> None:
        """
        Seed one runtime parameter consistently across every EMT initialization store.

        EMT uses several synchronized containers during problem build and native
        initialization: temporary PF guesses, flat runtime values, runtime-source
        equations, and the preserved post-initialization snapshot. A runtime
        parameter seed must update all of them together or later stages can fall
        back to an older placeholder value.

        :param uid: Runtime-parameter UID.
        :param value: Seed value.
        :param persist_after_native_init: Preserve the value after native init.
        :return: None.
        """
        value_float: float = float(value)
        self._temp_init_guess[uid] = value_float

        if persist_after_native_init:
            self._temp_post_init_guess[uid] = value_float
        else:
            pass

        self._set_runtime_parameter_value_by_uid(uid=uid, value=value_float)

    def _reapply_vsc_pf_seeds_after_native_initialization(self) -> None:
        """Reapply mapped VSC terminal PF values after the native initialization stage."""
        bus_indices: Dict[Any, int] = self.grid.get_bus_index_dict()
        for vsc_index, vsc in enumerate(self.grid.vsc_devices):
            f_bus_idx = bus_indices[vsc.bus_from]
            t_bus_idx = bus_indices[vsc.bus_to]
            self._try_set_vsc_branch_pf_init(
                mdl=vsc.emt_model,
                f_bus_idx=f_bus_idx,
                t_bus_idx=t_bus_idx,
                sbase=self.grid.Sbase,
                vsc_index=vsc_index,
            )

    def _seed_all_switch_models(self) -> None:
        """Seed mapped switch modes from Switch.active when the model requests it.

        With PF seeding disabled, retain the mode initialized by the model.
        Both variables are resolved through the problem-local external mapping.
        """
        for branch in self.grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
            if branch.device_type == DeviceType.SwitchDevice and branch.emt_model is not None:
                mapping = _get_external_mapping_local(self, branch.emt_model)
                if mapping is not None:
                    closed_mode = mapping.get(VarPowerFlowReferenceType.switch_closed_mode)
                    seed_flag = mapping.get(VarPowerFlowReferenceType.switch_seed_from_pf)
                    if closed_mode is not None and seed_flag is not None:
                        seed_index = self.uid2idx_event_params[seed_flag.uid]
                        if self.event_params_values[seed_index] > 0.5:
                            self._set_runtime_parameter_value_by_uid(
                                uid=closed_mode.uid,
                                value=1.0 if branch.active else 0.0,
                            )

    def _initialize_mode_event_state(self) -> None:
        """
        Initialize the mode event cursor state.

        :return: None
        """
        for uid, event_list in self._scheduled_mode_events.items():
            event_list.sort(key=_get_mode_event_sort_key)
            self._mode_event_cursor[uid] = 0

    def _apply_scheduled_mode_events(self, t_curr: float, full_params: np.ndarray) -> None:
        """
        Apply scheduled retained mode events to the flat full parameter vector.

        :param t_curr: Current simulation time.
        :param full_params: Flat full parameter vector.
        :return: None
        """
        for uid, event_list in self._scheduled_mode_events.items():
            event_idx: int = self._mode_event_cursor.get(uid, 0)

            while event_idx < len(event_list) and t_curr >= event_list[event_idx][0]:
                event_time: float = event_list[event_idx][0]
                event_value: float = event_list[event_idx][1]
                force_step_alignment: bool = event_list[event_idx][2]

                runtime_idx: Optional[int] = self.uid2idx_event_params.get(uid, None)
                is_time_aligned: bool = _is_time_aligned(t_curr, event_time)

                if force_step_alignment:
                    if is_time_aligned:
                        if runtime_idx is not None:
                            full_params[runtime_idx] = event_value
                        else:
                            pass
                    else:
                        raise RuntimeError(
                            f"Scheduled EMT mode event at t={event_time} requires exact step alignment, "
                            f"but current solver time is t={t_curr}. Adjust the EMT time step or enable step splitting."
                        )
                else:
                    if runtime_idx is not None:
                        full_params[runtime_idx] = event_value
                    else:
                        pass

                event_idx += 1

            self._mode_event_cursor[uid] = event_idx

    def _collect_runtime_mode_parameters(self) -> List[Var]:
        """
        Collect scheduled modes and numerical history parameters in stable order.

        History currents and instantaneous JMARTI voltage offsets are updated
        from accepted steps. Retaining them prevents continuous event evaluation
        from replacing their current values with initial placeholders.

        :return: Unique retained parameters, ordered by their existing owner.
        """
        # The family count is known before collection. These are references to
        # existing parameter arrays, not copied declarations or another owner.
        group_count: int = 1 + 6 * len(self.history_models)
        parameter_collections: List[List[Var]] = list((list(),)) * group_count
        parameter_collections[0] = self.get_runtime_mode_parameters()
        group_index: int = 1
        rt: BergeronHistoryRuntime | JMartiHistoryRuntime
        for rt in self.history_models:
            parameter_collections[group_index] = rt.Ih_f
            parameter_collections[group_index + 1] = rt.Ih_t
            if isinstance(rt, JMartiHistoryRuntime):
                parameter_collections[group_index + 2] = rt.incoming_voltage_f_re
                parameter_collections[group_index + 3] = rt.incoming_voltage_t_re
                parameter_collections[group_index + 4] = rt.incoming_voltage_f_im
                parameter_collections[group_index + 5] = rt.incoming_voltage_t_im
            else:
                pass
            group_index += 6

        # Count unique UIDs first so the result never grows after allocation.
        seen: Set[int] = set()
        first_parameter: Var | None = None
        parameter_count: int = 0
        parameters: List[Var]
        parameter: Var
        for parameters in parameter_collections:
            for parameter in parameters:
                if parameter.uid not in seen:
                    seen.add(parameter.uid)
                    parameter_count += 1
                else:
                    pass
                if first_parameter is None:
                    first_parameter = parameter
                else:
                    pass

        mode_parameters: List[Var]
        if first_parameter is None:
            mode_parameters = list()
        else:
            mode_parameters = list((first_parameter,)) * parameter_count
            seen.clear()
            parameter_index: int = 0
            for parameters in parameter_collections:
                for parameter in parameters:
                    if parameter.uid in seen:
                        pass
                    else:
                        seen.add(parameter.uid)
                        mode_parameters[parameter_index] = parameter
                        parameter_index += 1
        return mode_parameters

    def add_device_var(self, dev: ALL_DEV_TYPES, var: Var)->None:
        """
        Registers a variable belonging to a specific device.
        """
        var_list = self._vars_info.get(dev, None)
        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            var_list.append(var)

    def set_init_guess(self, mdl: Block, reference_powerflow: Any, val: float) -> None:
        """
        Set the temporary initial guess for a mapped variable during the parsing phase.

        :param mdl: Model block containing the external mapping.
        :param reference_powerflow: Reference key used to locate the mapped variable.
        :param val: Initialization value.
        :return: None
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(self, mdl)

        if external_mapping is None:
            pass
        else:
            var: Optional[Var] = external_mapping.get(reference_powerflow, None)

            if var is None:
                pass
            else:
                self._temp_init_guess[var.uid] = float(val)

    def set_init_guess_and_preserve_post_init(self, mdl: Block, reference_powerflow: Any, val: float) -> None:
        """
        Set one mapped initialization guess and preserve it after native initialization.

        :param mdl: Model block containing the external mapping.
        :param reference_powerflow: Reference key used to locate the mapped variable.
        :param val: Initialization value.
        :return: None.
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(self, mdl)

        if external_mapping is None:
            pass
        else:
            var: Optional[Var] = external_mapping.get(reference_powerflow, None)

            if var is None:
                pass
            else:
                value_float: float = float(val)
                self._temp_init_guess[var.uid] = value_float
                self._temp_post_init_guess[var.uid] = value_float

    def set_diff_init_guess(self, mdl: Block, reference_powerflow: Any, val: float) -> None:
        """
        Set the temporary initial guess for a mapped differential variable during the parsing phase.

        :param mdl: Model block containing the external mapping.
        :param reference_powerflow: Reference key used to locate the mapped differential variable.
        :param val: Initialization value.
        :return: None
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(self, mdl)

        if external_mapping is None:
            pass
        else:
            diff_var: Optional[Var] = external_mapping.get(reference_powerflow, None)

            if diff_var is None:
                pass
            else:
                self._temp_diff_init_guess[diff_var.uid] = float(val)

    def set_external_param(self, mdl: Block, key: VarPowerFlowReferenceType, value: float) -> None:
        """Seed one externally mapped runtime parameter on problem-local storage.

        The source ``Block.event_dict`` declares mutability and remains unchanged.
        This method supports calls both before and after the flat runtime vectors
        have been constructed.

        :param mdl: Dynamic model which exposes the external mapping.
        :param key: Power-flow reference identifying the runtime target.
        :param value: PF-derived initial value.
        :return: None.
        """
        external_mapping: Optional[Dict[Any, Var]] = _get_external_mapping_local(self, mdl)
        var: Optional[Any]
        owner_block: Optional[Block]

        if external_mapping is None:
            var = None
        else:
            var = external_mapping.get(key, None)

        if var is None:
            return
        else:
            pass

        if isinstance(var, Var):
            runtime_idx: int | None = None
            runtime_idx = self._uid2idx_event_params.get(var.uid, None)

            if runtime_idx is None:
                runtime_source_parameters_any: Any = self._runtime_all_parameters_source
                if isinstance(runtime_source_parameters_any, list):
                    runtime_source_index: int = 0
                    while runtime_source_index < len(runtime_source_parameters_any):
                        runtime_parameter_any: Any = runtime_source_parameters_any[runtime_source_index]
                        if isinstance(runtime_parameter_any, Var) and runtime_parameter_any.uid == var.uid:
                            runtime_idx = runtime_source_index
                            break
                        else:
                            runtime_source_index += 1
                else:
                    pass
            else:
                pass

            if runtime_idx is not None:
                value_float_runtime: float = float(value)
                self._temp_init_guess[var.uid] = value_float_runtime
                self._temp_post_init_guess[var.uid] = value_float_runtime

                event_parameter_equations_any: Any = self._event_parameters_eqs
                if isinstance(event_parameter_equations_any, list) and runtime_idx < len(event_parameter_equations_any):
                    event_parameter_equations_any[runtime_idx] = Const(value_float_runtime)
                else:
                    pass

                runtime_source_equations_any: Any = self._runtime_all_eqs_source
                if isinstance(runtime_source_equations_any, list) and runtime_idx < len(runtime_source_equations_any):
                    runtime_source_equations_any[runtime_idx] = Const(value_float_runtime)
                else:
                    pass

                runtime_eqs0_any: Any = self._runtime_parameter_eqs0
                if isinstance(runtime_eqs0_any, list) and runtime_idx < len(runtime_eqs0_any):
                    runtime_eqs0_any[runtime_idx] = Const(value_float_runtime)
                else:
                    pass

                self._set_runtime_parameter_seed_by_uid(uid=var.uid, value=value_float_runtime, persist_after_native_init=True)
            else:
                # GUI wrapper roots often expose the PF reference while the actual
                # runtime parameter lives in a child ``event_dict``. Validate
                # that owner, but retain the numerical value only in problem-local
                # seed storage until the canonical runtime index map is built.
                owner_block = _find_event_var_owner(mdl, var)
                if owner_block is None:
                    pass
                else:
                    value_float: float = float(value)
                    self._set_runtime_parameter_seed_by_uid(
                        uid=var.uid,
                        value=value_float,
                        persist_after_native_init=True,
                    )
        else:
            pass

    def get_init_guess_info(self) -> pd.DataFrame:
        """
        Return a table with the explicitly initialized variable guesses.

        :return: DataFrame with UID, variable name and initialization value.
        """
        rows: List[Dict[str, Any]] = list()
        all_vars: Dict[int, Var] = dict()

        for var in self._state_vars:
            all_vars[var.uid] = var

        for var in self._algebraic_vars:
            all_vars[var.uid] = var

        for uid, value in self.init_guess.items():
            if uid in all_vars:
                rows.append({
                    "uid": uid,
                    "var_name": all_vars[uid].name,
                    "value": value,
                })
            else:
                pass

        return pd.DataFrame(rows)

    def get_device_vars_dict(self) -> Dict[ALL_DEV_TYPES, List[Var]]:
        """
        Returns the dictionary mapping electrical devices to their variables.
        """
        return self._vars_info

    @property
    def vars_glob_name2uid(self) -> Dict[str, int]:
        """
        Returns the dictionary mapping global variable names to UIDs.
        """
        return self._vars_glob_name2uid

    @property
    def boundary_update(self) -> EmtBoundaryUpdateProtocol | None:
        """
        Return the endogenous EMT boundary updater consumed by the EMT solvers.
        """
        if len(self._scheduled_mode_events) == 0 and len(self.history_models) == 0 and self._block_boundary_updater is None:
            return None
        else:
            pass

        return self

    def reset_boundary_update_state(self, t0: float = 0.0) -> None:
        """
        Reset the EMT boundary update state before a new solver run starts.

        :param t0: Initial simulation time.
        :return: None
        """
        super().reset_boundary_update_state(t0)
        self.step_counter = 0
        self._mode_event_cursor = dict()
        self._initialize_mode_event_state()
        # An advanced JMARTI runtime has changed rings and four filter stores.
        # Restore its original source before publishing the next startup seeds.
        rt: BergeronHistoryRuntime | JMartiHistoryRuntime
        for rt in self.history_models:
            if isinstance(rt, JMartiHistoryRuntime) and rt.coupling_block is not None:
                rt.restore_initial_history()
                history_from: np.ndarray
                history_to: np.ndarray
                if rt.initial_source_available:
                    voltage_from: np.ndarray = np.sqrt(2.0) * np.imag(rt.initial_source_phasors[0, :])
                    voltage_to: np.ndarray = np.sqrt(2.0) * np.imag(rt.initial_source_phasors[1, :])
                    history_from = (
                        np.sqrt(2.0) * np.imag(rt.initial_source_phasors[2, :])
                        - rt.direct_yc_phase @ voltage_from
                        + 2.0 * np.real(rt.phase_current_coupling @ rt.initial_phase_waves[1, :])
                    )
                    history_to = (
                        np.sqrt(2.0) * np.imag(rt.initial_source_phasors[3, :])
                        - rt.direct_yc_phase @ voltage_to
                        + 2.0 * np.real(rt.phase_current_coupling @ rt.initial_phase_waves[0, :])
                    )
                else:
                    history_from = np.zeros(rt.m, dtype=np.float64)
                    history_to = np.zeros(rt.m, dtype=np.float64)
                phase_index: int = 0
                while phase_index < rt.m:
                    self._set_runtime_parameter_seed_by_uid(uid=rt.Ih_f[phase_index].uid, value=float(np.real(history_from[phase_index])), persist_after_native_init=True)
                    self._set_runtime_parameter_seed_by_uid(uid=rt.Ih_t[phase_index].uid, value=float(np.real(history_to[phase_index])), persist_after_native_init=True)
                    phase_index += 1

                # Only the coordinate families that exist are populated. All
                # stores use the canonical UID seed owner and retained partition.
                offset_groups: tuple[List[Var], ...] = (
                    rt.incoming_voltage_f_re, rt.incoming_voltage_t_re,
                    rt.incoming_voltage_f_im, rt.incoming_voltage_t_im,
                )
                group_index: int
                offset_vars: List[Var]
                offset_var: Var
                offset_value: complex
                offset_seed: float
                for group_index, offset_vars in enumerate(offset_groups):
                    for phase_index, offset_var in enumerate(offset_vars):
                        offset_value = complex(rt.initial_voltage_offsets[group_index % 2, phase_index])
                        if group_index < 2:
                            offset_seed = float(offset_value.real)
                        else:
                            offset_seed = float(offset_value.imag)
                        self._set_runtime_parameter_seed_by_uid(uid=offset_var.uid, value=offset_seed, persist_after_native_init=True)
            else:
                pass
        self._block_boundary_updater = build_boundary_updater_from_block(
            problem=self,
            expression_mode=ProceduralExpressionMode.Compiled,
            runtime_session=self._manufacturer_native_runtime_session,
            model_mode=1 if self._manufacturer_native_runtime_session is not None else None,
        )

        if self._block_boundary_updater is None:
            pass
        else:
            x0: np.ndarray = self.get_x0()

            # Procedural outputs such as sampled modes and saturations are
            # retained runtime parameters. Their startup value must come from
            # evaluating the procedural logic on the initialized operating
            # point, not only from the generic mode_dict seed.
            self._block_boundary_updater.initialize_modes(float(t0), x0, self._event_params_values)

    def resolve_manufacturer_native_boundary(
            self,
            runtime_session: ManufacturerNativeRuntimeSessionProtocol | None,
    ) -> None:
        """Install the driver-owned EMT native session for subsequent resets.

        :param runtime_session: Event-group session, or ``None`` to detach it.
        :return: None.
        """
        self._manufacturer_native_runtime_session = runtime_session

    def emt_boundary_update(
            self,
            t_curr: float,
            x_prev: np.ndarray,
            full_params: np.ndarray
    ) -> None:
        """
        Update runtime boundaries before the Newton step.

        Retained mode events are applied first. Afterwards, history-dependent EMT
        models update their internal boundary data.

        :param t_curr: Current simulation time.
        :param x_prev: Previous accepted state vector.
        :param full_params: Flat full parameter vector.
        :return: None
        """
        self._apply_scheduled_mode_events(t_curr, full_params)

        if self._block_boundary_updater is not None:
            # The retained procedural logic reacts after scheduled events so it sees the latest gate commands.
            self._block_boundary_updater.update(t_curr, x_prev, full_params)
        else:
            pass

        for rt in self.history_models:
            rt.update_history(self.step_counter, x_prev, full_params)

        # Persist the updated runtime parameters so the next step sees them
        n_runtime: int = self.get_variable_parameter_number()
        self._event_params_values[:] = full_params[:n_runtime]

        self.step_counter += 1

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the earliest forced-alignment event time in the interval
        (t_prev, t_target].

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event time or None.
        """
        scheduled_time: Optional[float]
        procedural_time: Optional[float]

        scheduled_time = _get_next_forced_mode_event_time(self._scheduled_mode_events, t_prev, t_target)

        if self._block_boundary_updater is None:
            procedural_time = None
        else:
            procedural_time = self._block_boundary_updater.get_next_forced_event_time(t_prev, t_target)

        # Merge the scheduled and procedural forced-event candidates so the
        # solver advances only to the earliest boundary that requires explicit
        # alignment on the next integration step.
        if scheduled_time is None:
            return procedural_time
        else:
            pass

        if procedural_time is None:
            return scheduled_time
        else:
            pass

        if scheduled_time <= procedural_time:
            return scheduled_time
        else:
            return procedural_time

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Boundary update entry point compatible with BoundaryUpdateWrapper.

        :param t: Current simulation time.
        :param x: Previous accepted state vector.
        :param params: Flat full parameter vector.
        :return: None
        """
        self.emt_boundary_update(t, x, params)

    def commit_boundary(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """Commit due manufacturer-native samples after an accepted EMT step.

        The isolated runtime is irreversible, so it is advanced only after the
        network solve has converged. Its held outputs are then persisted in the
        problem-owned runtime vector for the next aligned sub-step.

        :param t: Accepted solver boundary time.
        :param x: Accepted EMT state vector.
        :param params: Full mutable parameter vector receiving held outputs.
        :return: None.
        """
        if self._block_boundary_updater is not None:
            self._block_boundary_updater.commit_boundary(float(t), x, params)
            runtime_parameter_count: int = self.get_variable_parameter_number()
            self._event_params_values[:] = params[:runtime_parameter_count]
        else:
            pass

    def get_floquet_ak_stack(
            self,
            trajectory: np.ndarray,
            h: float,
            jac_evaluator: Optional[Any] = None,
            static_params: Optional[np.ndarray] = None
    ) -> Optional[np.ndarray]:
        """
        Return the stack of reduced transition matrices used for Floquet analysis.

        :param trajectory: State trajectory over one period.
        :param h: Time step.
        :param jac_evaluator: Optional Jacobian evaluator.
        :param static_params: Optional static parameter vector.
        :return: Stack of reduced transition matrices or None.
        """
        if jac_evaluator is None:
            if self.logger is not None:
                self.logger.add_warning(
                    msg="No Jacobian evaluator was provided for Floquet Ak stack computation.",
                    device="EmtProblemDae",
                    value="None",
                    expected_value="Callable Jacobian evaluator",
                    device_class="EMT",
                    device_property="jac_evaluator"
                )
            else:
                pass
            return None
        else:
            pass

        n = self.get_states_number()
        steps = len(trajectory) - 1

        if steps <= 0:
            return None

        stack = np.zeros((steps, n, n), order='C')

        for i in range(steps):
            x_k = trajectory[i]

            J = jac_evaluator(x_k, static_params, x_k, None, h, None)

            J11 = J[:n, :n]
            J12 = J[:n, n:]
            J21 = J[n:, :n]
            J22 = J[n:, n:]

            J22_inv_J21 = spla.spsolve(J22, J21)

            J_red = (J11 - J12 @ J22_inv_J21)

            if sp.issparse(J_red):
                J_red = J_red.toarray()

            stack[i] = la.inv(h * J_red)

        return stack

    def get_floquet_jacobian_evaluator(self, default_jacobian_evaluator: Optional[Any] = None) -> Optional[Any]:
        """Return the Jacobian evaluator used by EMT Floquet analysis.

        Subclasses can override this to provide problem-specific Jacobian backends
        while keeping the small-signal driver unchanged.
        """
        return default_jacobian_evaluator

    def get_init_guess_table(self,
                             include_all_vars: bool = True,
                             only_in_init_guess: bool = False,
                             tol_zero: float = 1e-12) -> pd.DataFrame:
        """
        Return a table with uid, alias/name and initial value for each variable.

        include_all_vars:
            - True: include all state+algebraic vars, even if not in init_guess (value=0).
            - False: include only uids present in init_guess (or only_in_init_guess=True).

        only_in_init_guess:
            - True: filter to only those explicitly initialized (uid in init_guess).
            - False: keep everything (depending on include_all_vars).

        tol_zero:
            threshold to flag values close to zero.
        """
        # Build x0 and dx0 from current guesses
        x0 = self.get_x0()
        dx0 = self.get_dx0()

        uid2idx_vars = self.uid2idx_vars
        uid2idx_diff = self.uid2idx_diff

        # Define the sets we want to process: (Variables, Guess_Source, Index_Map, Vector, Label)
        data_sets = [
            (list(self.get_state_vars()) + list(self.get_algebraic_vars()), self.init_guess, uid2idx_vars, x0, "Var"),
            (list(self.get_diff_vars()), self.diff_init_guess, uid2idx_diff, dx0, "DiffVar")
        ]

        rows: List[Dict[str, Any]] = list()
        for vars_list, guess_dict, idx_map, vector, var_type in data_sets:
            for v in vars_list:
                uid = v.uid
                idx = idx_map.get(uid, None)
                val = float(vector[idx]) if idx is not None else 0.0

                in_guess = uid in guess_dict

                keep_row = True
                if only_in_init_guess and (not in_guess):
                    keep_row = False
                if (not include_all_vars) and (not in_guess):
                    keep_row = False

                if keep_row:
                    alias: Optional[str] = self._alias_names_dict.get(uid, None)

                    rows.append({
                        "uid": uid,
                        "type": var_type,
                        "idx": idx,  # add this
                        "alias": alias,
                        "name": v.name,
                        "value": val,
                        "in_init_guess": in_guess,
                        "is_zero": abs(val) <= tol_zero,
                    })
                else:
                    pass

        df = pd.DataFrame(rows)

        # Nice ordering: Group by type, then initialization status
        if not df.empty:
            df = df.sort_values(["type", "idx"], ascending=[False, True])

        return df

    def _assign_generator_sharing_targets_from_seed(
            self,
            inj: InjectionParent,
            mdl: Block,
            phase_power: np.ndarray,
            generator_battery_count_same_bus: int,
    ) -> None:
        """
        Assign optional sharing references to one generator from its EMT seed.

        Generator controllers may accept total active and reactive power
        references. These runtime values are derived from the already computed
        per-device EMT seed so the controller starts from the same sharing target
        used during PF-to-EMT initialization.

        :param inj: Generator device.
        :param mdl: Registered EMT model whose runtime references receive the seed.
        :param phase_power: Complex power seed in NABC order.
        :param generator_battery_count_same_bus: Number of generators and
            batteries connected to the same bus.
        :return: None.
        """
        p_ref_value: float = float(np.real(np.sum(phase_power)))
        q_ref_value: float = float(np.imag(np.sum(phase_power)))

        if self.options.verbose:
            print(f"p_ref_value = {p_ref_value} generator {inj}")
            print(f"q_ref_value = {q_ref_value} generator {inj}")

        if generator_battery_count_same_bus > 1:
            share_enable_value: float = 1.0
        else:
            share_enable_value = 0.0

        self._assign_event_mapping_value_if_present(
            mdl=mdl,
            key=ParamPowerFlowReferenceType.generator_share_enable,
            value=share_enable_value,
        )
        self._assign_event_mapping_value_if_present(
            mdl=mdl,
            key=ParamPowerFlowReferenceType.generator_share_p_ref,
            value=p_ref_value,
        )
        self._assign_event_mapping_value_if_present(
            mdl=mdl,
            key=ParamPowerFlowReferenceType.generator_share_q_ref,
            value=q_ref_value,
        )
