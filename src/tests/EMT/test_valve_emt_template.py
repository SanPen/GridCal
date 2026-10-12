# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Tuple

import numpy as np

import VeraGridEngine.api as gce
import VeraGridEngine.Templates as tem
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper, JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.dc_line_emt_template import get_dc_line_emt_template
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.converter_emt_template import get_emt_ideal_converter
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Emt.valve_emt_template import get_valve_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DeviceType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    FmuTemplateDomain,
    SolverType,
    ValveEmtModelVariant,
    ValveEmtType,
    ValveInitializationState,
    VarPowerFlowReferenceType,
)


class GenericEmtProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by valve-template unit tests.
    """

    __slots__ = []


class LoadStepBoundaryUpdater(BoundaryUpdateWrapper):
    """
    Apply a DC load-power step while preserving the EMT-problem boundary update.
    """

    __slots__ = [
        "_problem",
        "_param_full_idx",
        "_step_time_s",
        "_initial_value_pu",
        "_final_value_pu",
    ]

    def __init__(
            self,
            problem: EmtProblemDae,
            param_full_idx: int,
            step_time_s: float,
            initial_value_pu: float,
            final_value_pu: float,
    ) -> None:
        """
        Build one DC load-step boundary updater.

        :param problem: EMT problem owning the runtime state.
        :param param_full_idx: Full-parameter-vector index of the DC load power parameter.
        :param step_time_s: Time instant of the power step.
        :param initial_value_pu: Initial load power in p.u.
        :param final_value_pu: Final load power in p.u.
        :return: None.
        """
        self._problem = problem
        self._param_full_idx = int(param_full_idx)
        self._step_time_s = float(step_time_s)
        self._initial_value_pu = float(initial_value_pu)
        self._final_value_pu = float(final_value_pu)

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Apply the scheduled load step and forward the update to the EMT problem.

        :param t: Current simulation time.
        :param x: Accepted EMT state vector.
        :param params: Full parameter vector.
        :return: None.
        """
        if float(t) < self._step_time_s:
            params[self._param_full_idx] = self._initial_value_pu
        else:
            params[self._param_full_idx] = self._final_value_pu

        self._problem.emt_boundary_update(float(t), x, params)

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the earliest forced event from the load step or the wrapped problem.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event time or ``None``.
        """
        problem_time: float | None = self._problem.get_next_forced_event_time(float(t_prev), float(t_target))

        if float(t_prev) < self._step_time_s <= float(t_target):
            local_time: float | None = self._step_time_s
        else:
            local_time = None

        if problem_time is None:
            return local_time
        else:
            pass

        if local_time is None:
            return problem_time
        else:
            pass

        if problem_time <= local_time:
            return problem_time
        else:
            return local_time


class GateScheduleBoundaryUpdater(BoundaryUpdateWrapper):
    """
    Apply a piecewise-constant gate schedule while preserving the EMT-problem update.
    """

    __slots__ = [
        "_problem",
        "_gate_param_idx",
        "_mode_param_idx",
        "_event_time_s",
        "_event_value",
        "_record_time_s",
        "_record_gate",
        "_record_mode",
        "_record_count",
    ]

    def __init__(
            self,
            problem: EmtProblemDae,
            gate_param_idx: int,
            mode_param_idx: int,
            event_time_s: np.ndarray,
            event_value: np.ndarray,
            max_records: int,
    ) -> None:
        """
        Build one valve-gate boundary updater.

        :param problem: EMT problem owning the runtime state.
        :param gate_param_idx: Runtime index of the gate parameter.
        :param mode_param_idx: Runtime index of the retained valve mode.
        :param event_time_s: Sorted event times.
        :param event_value: Piecewise-constant gate values.
        :param max_records: Maximum number of recorded samples.
        :return: None.
        """
        self._problem = problem
        self._gate_param_idx = int(gate_param_idx)
        self._mode_param_idx = int(mode_param_idx)
        self._event_time_s = np.array(event_time_s, copy=True)
        self._event_value = np.array(event_value, copy=True)
        self._record_time_s = np.zeros(max_records, dtype=float)
        self._record_gate = np.zeros(max_records, dtype=float)
        self._record_mode = np.zeros(max_records, dtype=float)
        self._record_count = 0

    def _get_gate_value(self, time_s: float) -> float:
        """
        Return the scheduled gate value at one time instant.

        :param time_s: Current simulation time.
        :return: Gate value.
        """
        event_idx: int = 0
        gate_value: float = float(self._event_value[0])

        while event_idx < len(self._event_time_s):
            if time_s >= float(self._event_time_s[event_idx]):
                gate_value = float(self._event_value[event_idx])
            else:
                pass
            event_idx += 1

        return gate_value

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Apply the gate command and forward the update to the EMT problem.

        :param t: Current simulation time.
        :param x: Accepted EMT state vector.
        :param params: Full parameter vector.
        :return: None.
        """
        gate_value: float = self._get_gate_value(float(t))
        params[self._gate_param_idx] = gate_value
        self._problem.emt_boundary_update(float(t), x, params)

        if self._record_count < len(self._record_time_s):
            self._record_time_s[self._record_count] = float(t)
            self._record_gate[self._record_count] = gate_value
            self._record_mode[self._record_count] = float(params[self._mode_param_idx])
            self._record_count += 1
        else:
            pass

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the earliest forced event from the gate schedule or the wrapped problem.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event time or ``None``.
        """
        event_idx: int = 0
        problem_time: float | None = self._problem.get_next_forced_event_time(float(t_prev), float(t_target))
        local_time: float | None = None

        while event_idx < len(self._event_time_s):
            event_time: float = float(self._event_time_s[event_idx])
            if float(t_prev) < event_time <= float(t_target):
                local_time = event_time
                event_idx = len(self._event_time_s)
            else:
                event_idx += 1

        if problem_time is None:
            return local_time
        else:
            pass

        if local_time is None:
            return problem_time
        else:
            pass

        if problem_time <= local_time:
            return problem_time
        else:
            return local_time

    def get_record_time_s(self) -> np.ndarray:
        """
        Return the recorded control-update time vector.

        :return: Recorded control-update time vector.
        """
        return np.array(self._record_time_s[:self._record_count], copy=True)

    def get_record_gate(self) -> np.ndarray:
        """
        Return the recorded gate trace.

        :return: Recorded gate trace.
        """
        return np.array(self._record_gate[:self._record_count], copy=True)

    def get_record_mode(self) -> np.ndarray:
        """
        Return the recorded retained valve-mode trace.

        :return: Recorded retained valve-mode trace.
        """
        return np.array(self._record_mode[:self._record_count], copy=True)


class StandaloneGateScheduleBoundaryUpdater(BoundaryUpdateWrapper):
    """
    Apply one gate schedule on top of a standalone block-owned boundary updater.
    """

    __slots__ = [
        "_base_updater",
        "_gate_param_idx",
        "_mode_param_idx",
        "_event_time_s",
        "_event_value",
        "_record_time_s",
        "_record_gate",
        "_record_mode",
        "_record_count",
    ]

    def __init__(
            self,
            base_updater: BoundaryUpdateWrapper | None,
            gate_param_idx: int,
            mode_param_idx: int,
            event_time_s: np.ndarray,
            event_value: np.ndarray,
            max_records: int,
    ) -> None:
        """
        Build one standalone gate-schedule boundary updater.

        :param base_updater: Optional updater generated from the block procedural logic.
        :param gate_param_idx: Runtime index of the gate parameter.
        :param mode_param_idx: Runtime index of the retained valve mode.
        :param event_time_s: Sorted event times.
        :param event_value: Piecewise-constant gate values.
        :param max_records: Maximum number of recorded samples.
        :return: None.
        """
        self._base_updater = base_updater
        self._gate_param_idx = int(gate_param_idx)
        self._mode_param_idx = int(mode_param_idx)
        self._event_time_s = np.array(event_time_s, copy=True)
        self._event_value = np.array(event_value, copy=True)
        self._record_time_s = np.zeros(max_records, dtype=float)
        self._record_gate = np.zeros(max_records, dtype=float)
        self._record_mode = np.zeros(max_records, dtype=float)
        self._record_count = 0

    def _get_gate_value(self, time_s: float) -> float:
        """
        Return the scheduled gate value at one time instant.

        :param time_s: Current simulation time.
        :return: Scheduled gate value.
        """
        event_idx: int = 0
        gate_value: float = float(self._event_value[0])

        while event_idx < len(self._event_time_s):
            if time_s >= float(self._event_time_s[event_idx]):
                gate_value = float(self._event_value[event_idx])
            else:
                pass
            event_idx += 1

        return gate_value

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Apply the gate command and then delegate to the optional base updater.

        :param t: Current simulation time.
        :param x: Accepted EMT state vector.
        :param params: Full parameter vector.
        :return: None.
        """
        gate_value: float = self._get_gate_value(float(t))
        params[self._gate_param_idx] = gate_value

        if self._base_updater is not None:
            self._base_updater.update(float(t), x, params)
        else:
            pass

        if self._record_count < len(self._record_time_s):
            self._record_time_s[self._record_count] = float(t)
            self._record_gate[self._record_count] = gate_value
            self._record_mode[self._record_count] = float(params[self._mode_param_idx])
            self._record_count += 1
        else:
            pass

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the earliest forced event from the gate schedule or the delegated updater.

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event time or ``None``.
        """
        event_idx: int = 0
        local_time: float | None = None
        base_time: float | None

        while event_idx < len(self._event_time_s):
            event_time: float = float(self._event_time_s[event_idx])
            if float(t_prev) < event_time <= float(t_target):
                local_time = event_time
                event_idx = len(self._event_time_s)
            else:
                event_idx += 1

        if self._base_updater is None:
            base_time = None
        else:
            base_time = self._base_updater.get_next_forced_event_time(float(t_prev), float(t_target))

        if local_time is None:
            return base_time
        else:
            pass

        if base_time is None:
            return local_time
        else:
            pass

        if local_time <= base_time:
            return local_time
        else:
            return base_time

    def get_record_time_s(self) -> np.ndarray:
        """
        Return the recorded control-update time vector.

        :return: Recorded control-update time vector.
        """
        return np.array(self._record_time_s[:self._record_count], copy=True)

    def get_record_gate(self) -> np.ndarray:
        """
        Return the recorded gate trace.

        :return: Recorded gate trace.
        """
        return np.array(self._record_gate[:self._record_count], copy=True)

    def get_record_mode(self) -> np.ndarray:
        """
        Return the recorded retained mode trace.

        :return: Recorded retained mode trace.
        """
        return np.array(self._record_mode[:self._record_count], copy=True)


def _build_default_emt_options() -> gce.EmtOptions:
    """
    Return a compact EMT options object for valve integration tests.

    :return: EMT options instance.
    """
    return gce.EmtOptions(
        time_step=5e-6,
        simulation_time=0.01,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.ConsistentNewton,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=0,
    )


def _run_power_flow(grid: gce.MultiCircuit) -> Tuple[object, object]:
    """
    Run the balanced and three-phase PF used to seed EMT initialization.

    :param grid: Circuit under test.
    :return: Tuple ``(pf_results, pf_results_3ph)``.
    """
    pf_options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=100,
        tolerance=1e-6,
        control_q=True,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    pf_results: object = gce.power_flow(grid=grid, options=pf_options)

    pf_options_3ph: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    power_flow_3ph: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, pf_options_3ph)
    power_flow_3ph.run()
    pf_results_3ph: object = power_flow_3ph.results
    return pf_results, pf_results_3ph


def _run_balanced_power_flow(grid: gce.MultiCircuit) -> PowerFlowResults:
    """
    Run only the balanced PF used by the lightweight runtime valve/DC-line tests.

    :param grid: Circuit under test.
    :return: Balanced PF results object.
    """
    pf_options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=100,
        tolerance=1e-6,
        control_q=True,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    return gce.power_flow(grid=grid, options=pf_options)


def _find_var_in_block_by_name(name: str, block: Block) -> Var | None:
    """
    Return one symbolic variable from a block hierarchy by name.

    :param name: Requested symbolic-variable name.
    :param block: Root symbolic block.
    :return: Matching variable or ``None``.
    """
    variable: object
    child_block: object
    nested_result: Var | None

    for variable in block.algebraic_vars:
        if variable.name == name:
            return variable
        else:
            pass

    for variable in block.state_vars:
        if variable.name == name:
            return variable
        else:
            pass

    for variable in list(block.event_dict.keys()):
        if variable.name == name:
            return variable
        else:
            pass

    for variable in block.diff_vars:
        if variable.name == name:
            return variable
        else:
            pass

    for child_block in block.children:
        nested_result = _find_var_in_block_by_name(name, child_block)
        if nested_result is not None:
            return nested_result
        else:
            pass

    return None


def _build_demo_branch_circuit(
        branch_name: str,
        load_power_mw: float,
        load_conductance_mw: float = 0.0,
) -> Tuple[gce.MultiCircuit, gce.Bus, gce.Bus, gce.Bus, gce.Generator, gce.VSC, gce.DcLine, gce.Load]:
    """
    Build the compact AC/DC circuit used by the runtime valve/DC-line tests.

    :param branch_name: Name assigned to the branch host device.
    :param load_power_mw: DC load active power in MW.
    :param load_conductance_mw: DC load conductance term in equivalent MW at 1.0 p.u.
    :return: Circuit and the main devices.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=100.0, fbase=50.0)
    bus_ac: gce.Bus = gce.Bus(name="Bus_AC", Vnom=230.0, is_slack=True)
    bus_dc_from: gce.Bus = gce.Bus(name="Bus_DC_From", Vnom=320.0, is_dc=True)
    bus_dc_to: gce.Bus = gce.Bus(name="Bus_DC_To", Vnom=320.0, is_dc=True)
    generator: gce.Generator = gce.Generator(name="Generator", vset=1.0, Snom=100.0, freq=50.0, r1=0.001, x1=0.4)
    vsc: gce.VSC = gce.VSC(
        name="VSC",
        bus_from=bus_dc_from,
        bus_to=bus_ac,
        rate=100.0,
        control1=ConverterControlType.Qac,
        control2=ConverterControlType.Vm_dc,
        control1_val=0.0,
        control2_val=1.0,
    )
    dc_branch: gce.DcLine = gce.DcLine(name=branch_name, bus_from=bus_dc_from, bus_to=bus_dc_to, r=0.02, rate=100.0)
    # The runtime tests need explicit control over whether the DC sink behaves as
    # a constant-power term or as a conductance term. Keeping both constructor
    # inputs visible here avoids hidden dependence on the static-mapping policy.
    dc_load: gce.Load = gce.Load(name="DC_Load", P=load_power_mw, Q=0.0, G=load_conductance_mw)

    grid.add_bus(bus_ac)
    grid.add_bus(bus_dc_from)
    grid.add_bus(bus_dc_to)
    grid.add_generator(bus_ac, generator)
    grid.add_vsc(vsc)
    grid.add_dc_line(dc_branch)
    grid.add_load(bus_dc_to, dc_load)

    return grid, bus_ac, bus_dc_from, bus_dc_to, generator, vsc, dc_branch, dc_load


def _assign_dc_line_runtime_models(grid: gce.MultiCircuit, generator: gce.Generator, vsc: gce.VSC,
                                   dc_branch: gce.DcLine, dc_load: gce.Load) -> None:
    """
    Attach EMT models to the runtime DC-line test case.

    :param grid: Circuit under test.
    :param generator: Slack generator.
    :param vsc: AC/DC converter.
    :param dc_branch: DC line branch.
    :param dc_load: DC load.
    :return: None.
    """
    generator_model = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    vsc_model = get_emt_ideal_converter(vf=grid.var_factory, name=vsc.name).block
    dc_line_model = get_dc_line_emt_template(vf=grid.var_factory, name=dc_branch.name).block
    dc_load_model = get_dc_load_emt_template(vf=grid.var_factory, name="dc_load_runtime_case").block

    set_emt_model(device=generator, model=generator_model, var_factory=grid.var_factory)
    set_emt_model(device=vsc, model=vsc_model, var_factory=grid.var_factory)
    set_emt_model(device=dc_branch, model=dc_line_model, var_factory=grid.var_factory)
    set_emt_model(device=dc_load, model=dc_load_model, var_factory=grid.var_factory)


def _assign_valve_runtime_models(grid: gce.MultiCircuit, generator: gce.Generator, vsc: gce.VSC,
                                 valve_host: gce.DcLine, dc_load: gce.Load) -> None:
    """
    Attach EMT models to the runtime IGBT test case.

    :param grid: Circuit under test.
    :param generator: Slack generator.
    :param vsc: AC/DC converter.
    :param valve_host: Static branch used as the valve host.
    :param dc_load: DC load.
    :return: None.
    """
    generator_model = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    vsc_model = get_emt_ideal_converter(vf=grid.var_factory, name=vsc.name).block
    valve_model = get_valve_emt_template(
        vf=grid.var_factory,
        name=valve_host.name,
        valve_tpe=ValveEmtType.Igbt,
        model_variant=ValveEmtModelVariant.Ideal,
        initial_state=ValveInitializationState.Blocked,
        antiparallel_diode=True,
    ).block
    dc_load_model = get_dc_load_emt_template(vf=grid.var_factory, name="dc_load_runtime_case").block

    set_emt_model(device=generator, model=generator_model, var_factory=grid.var_factory)
    set_emt_model(device=vsc, model=vsc_model, var_factory=grid.var_factory)
    set_emt_model(device=valve_host, model=valve_model, var_factory=grid.var_factory)
    set_emt_model(device=dc_load, model=dc_load_model, var_factory=grid.var_factory)


def _get_constant_parameter_full_index(problem: EmtProblemDae, parameter_name: str) -> int:
    """
    Return the full-parameter-vector index of one constant parameter.

    :param problem: EMT problem under inspection.
    :param parameter_name: Constant-parameter symbolic name.
    :return: Full-parameter-vector index.
    """
    parameter: object
    runtime_parameter_count: int = problem.get_variable_parameter_number()

    for parameter in problem.get_constant_parameters():
        if parameter.name == parameter_name:
            return int(runtime_parameter_count + problem.uid2idx_params[parameter.uid])
        else:
            pass

    raise KeyError(f"Constant parameter '{parameter_name}' was not found")


def _extract_trace(problem: EmtProblemDae, trajectory: np.ndarray, variable: Var) -> np.ndarray:
    """
    Extract one variable trace from the EMT trajectory.

    :param problem: EMT problem under inspection.
    :param trajectory: Solver state trajectory.
    :param variable: Symbolic variable to extract.
    :return: Extracted trace.
    """
    return np.array(trajectory[:, problem.get_var_idx(variable)], copy=True)


def _create_symbolic_solver(problem: EmtProblemDae, simulation_time_s: float, time_step_s: float) -> JitSymbolicSolver:
    """
    Create the symbolic solver used by the runtime valve/DC-line tests.

    :param problem: EMT problem under test.
    :param simulation_time_s: Total EMT simulation time.
    :param time_step_s: Fixed EMT time step.
    :return: Configured symbolic EMT solver.
    """
    return JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=simulation_time_s,
        h=time_step_s,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )


def _build_constant_algebraic_var(vf: VarFactory, name: str, value: float) -> Tuple[Var, Expr]:
    """
    Build one algebraic variable constrained to a constant reference value.

    :param vf: Shared symbolic variable factory.
    :param name: Variable name.
    :param value: Constant reference value.
    :return: Tuple ``(variable, equation)``.
    """
    variable: Var = vf.add_var(name=name)
    reference_value: Const = Const(float(value))
    equation: Expr = variable - reference_value
    return variable, equation


def _set_block_runtime_parameter(block: Block, parameter_name: str, value: float) -> None:
    """
    Overwrite one block runtime-parameter default by symbolic name.

    :param block: Block to modify.
    :param parameter_name: Runtime-parameter variable name.
    :param value: New runtime default.
    :return: None.
    """
    parameter_var: Var
    found_parameter: bool = False
    updated_event_dict: Dict[Var, Const | Expr] = dict()

    for parameter_var, parameter_expr in block.event_dict.items():
        if parameter_var.name == parameter_name:
            updated_event_dict[parameter_var] = Const(float(value))
            found_parameter = True
        else:
            updated_event_dict[parameter_var] = parameter_expr

    if found_parameter:
        block.event_dict = updated_event_dict
    else:
        raise KeyError(f"Runtime parameter '{parameter_name}' was not found in block '{block.name}'")


def _connect_standalone_valve_terminals(block: Block, v_source: Var, v_load: Var) -> None:
    """
    Connect one standalone valve block to its source and load voltage variables.

    :param block: Valve block to connect.
    :param v_source: Source-side voltage variable.
    :param v_load: Load-side voltage variable.
    :return: None.
    """
    vf_terminal: Var = block.external_mapping[VarPowerFlowReferenceType.Vf_dc]
    vt_terminal: Var = block.external_mapping[VarPowerFlowReferenceType.Vt_dc]
    block.update_model(vf_terminal, v_source)
    block.update_model(vt_terminal, v_load)


def _build_standalone_valve_case(valve_tpe: ValveEmtType) -> Tuple[GenericEmtProblem, int, int, Dict[str, Var]]:
    """
    Build the standalone EMT valve case used by the behavioural tests.

    :param valve_tpe: Valve physical type.
    :return: EMT problem, gate index, retained-mode index and tracked variables.
    """
    vf: VarFactory = VarFactory()
    block_name: str = f"{valve_tpe.value.lower()}_standalone_case"
    v_source_ref: float = 1.04
    g_load_value: float
    c_load_value: float
    antiparallel_enabled: bool
    initial_state: ValveInitializationState
    v_source: Var
    v_source_eq: Expr
    v_load: Var
    d_v_load: Var
    g_load: Var
    c_load: Var
    valve_block: Block
    i_branch: Var
    v_valve: Var | None
    root_block: Block
    problem: GenericEmtProblem
    gate_idx: int
    mode_idx: int
    tracked_vars: Dict[str, Var]
    parameter: Var

    if valve_tpe == ValveEmtType.Igbt:
        g_load_value = 1.0
        c_load_value = 0.002
        antiparallel_enabled = False
        initial_state = ValveInitializationState.Blocked
    else:
        g_load_value = 0.35
        c_load_value = 0.02
        antiparallel_enabled = False
        initial_state = ValveInitializationState.Blocked

    v_source, v_source_eq = _build_constant_algebraic_var(vf=vf, name=f"v_source_{block_name}", value=v_source_ref)
    v_load = vf.add_var(name=f"v_load_{block_name}")
    d_v_load = vf.add_diff_var(name=f"d_v_load_{block_name}", base_var=v_load)
    g_load = vf.add_var(name=f"g_load_{block_name}")
    c_load = vf.add_var(name=f"c_load_{block_name}")

    valve_block = get_valve_emt_template(
        vf=vf,
        name=block_name,
        valve_tpe=valve_tpe,
        model_variant=ValveEmtModelVariant.Complete,
        initial_state=initial_state,
        antiparallel_diode=antiparallel_enabled,
    ).block
    _set_block_runtime_parameter(valve_block, "on_resistance", 0.02)
    _set_block_runtime_parameter(valve_block, "off_conductance", 1.0e-6)
    _set_block_runtime_parameter(valve_block, "forward_voltage", 0.0)
    _set_block_runtime_parameter(valve_block, "snubber_enabled", 0.0)
    _connect_standalone_valve_terminals(valve_block, v_source=v_source, v_load=v_load)

    i_branch = valve_block.external_mapping[VarPowerFlowReferenceType.If_dc]
    v_valve = _find_var_in_block_by_name("v_valve", valve_block)

    if v_valve is None:
        raise KeyError(f"Valve voltage variable for block '{block_name}' was not found")
    else:
        pass

    root_block = Block(
        name=f"StandaloneValveCase_{valve_tpe.value}",
        children=list([valve_block]),
        algebraic_vars=list([v_source]),
        algebraic_eqs=list([v_source_eq]),
        state_vars=list([v_load]),
        diff_vars=list([d_v_load]),
        state_eqs=list([(i_branch - g_load * v_load) / c_load]),
        parameters=dict([
            (g_load, Const(g_load_value)),
            (c_load, Const(c_load_value)),
        ]),
        init_eqs=dict([
            (v_source, Const(v_source_ref)),
            (v_load, Const(0.0)),
        ]),
    )
    root_block.unify_blocks()

    static_parameter_values_mapping: Dict[Var, Const] = dict(root_block.parameters)
    problem = GenericEmtProblem(
        sys_block=root_block,
        glob_time=vf.add_var(f"t_{block_name}"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    gate_idx = -1
    mode_idx = -1

    for parameter in problem.get_variable_parameters():
        if parameter.name == "gate_fired":
            gate_idx = int(problem.uid2idx_event_params[parameter.uid])
        else:
            pass

        if parameter.name == "path_mode":
            mode_idx = int(problem.uid2idx_event_params[parameter.uid])
        else:
            pass

    if gate_idx < 0 or mode_idx < 0:
        raise KeyError(f"Standalone valve runtime indices for '{block_name}' could not be resolved")
    else:
        pass

    tracked_vars = dict([
        ("v_source", v_source),
        ("v_load", v_load),
        ("i_branch", i_branch),
        ("v_valve", v_valve),
    ])
    return problem, gate_idx, mode_idx, tracked_vars


def _get_standalone_gate_schedule(valve_tpe: ValveEmtType) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return the gate schedule used by the standalone valve behavioural tests.

    :param valve_tpe: Valve physical type.
    :return: Tuple ``(event_time_s, event_value)``.
    """
    if valve_tpe == ValveEmtType.Diode:
        return np.array([0.0], dtype=float), np.array([0.0], dtype=float)
    else:
        pass

    if valve_tpe == ValveEmtType.Igbt:
        return np.array([0.0, 2.0e-3, 6.0e-3], dtype=float), np.array([0.0, 1.0, 0.0], dtype=float)
    else:
        pass

    if valve_tpe == ValveEmtType.Thyristor:
        return np.array([0.0, 2.0e-3, 2.4e-3], dtype=float), np.array([0.0, 1.0, 0.0], dtype=float)
    else:
        raise ValueError(f"Unsupported standalone valve type '{valve_tpe}'")


def _get_runtime_param_index_by_name(problem: EmtProblemTemplate, param_name: str) -> int:
    """
    Return the runtime-parameter index associated with a symbolic variable name.

    :param problem: EMT problem under inspection.
    :param param_name: Runtime-parameter symbolic name.
    :return: Runtime-parameter index.
    """
    parameter: object
    for parameter in problem.get_variable_parameters():
        if parameter.name == param_name:
            return int(problem.uid2idx_event_params[parameter.uid])
        else:
            pass

    raise KeyError(f"Runtime parameter '{param_name}' was not found")


def _get_var_index_by_name(problem: EmtProblemTemplate, var_name: str) -> int:
    """
    Return the flat algebraic/state index associated with a symbolic variable name.

    :param problem: EMT problem under inspection.
    :param var_name: Variable symbolic name.
    :return: Flat variable index.
    """
    variable: object
    for variable in problem.get_state_vars():
        if variable.name == var_name:
            return int(problem.get_var_idx(variable))
        else:
            pass

    for variable in problem.get_algebraic_vars():
        if variable.name == var_name:
            return int(problem.get_var_idx(variable))
        else:
            pass

    raise KeyError(f"Variable '{var_name}' was not found")


def add_emt_model_catalogue(grid):
    """
    Create default catalogue of EMT values
    :return:
    """
    grid.emt_models += [

        tem.get_simple_generator_emt_template(vf=grid.var_factory),
        tem.get_generator_sauer_pai_type_emt_template(vf=grid.var_factory),
        tem.get_governor_emt(vf=grid.var_factory),
        tem.get_stabilizer_emt(vf=grid.var_factory),
        tem.get_exciter_emt(vf=grid.var_factory),
        tem.get_complete_generator_template_emt(vf=grid.var_factory),

        tem.get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory),
        tem.get_emt_ideal_converter(vf=grid.var_factory),
        tem.get_full_pseudo_emt_converter(vf=grid.var_factory),
        tem.get_switched_emt_converter(vf=grid.var_factory),
        tem.get_bridge_2level_3ph_emt_template(vf=grid.var_factory),
        tem.get_bridge_filter_2level_3ph_emt_template(vf=grid.var_factory),
        tem.get_bridge_filter_control_2level_3ph_emt_template(vf=grid.var_factory),
        tem.get_dc_load_emt_template(vf=grid.var_factory),
        # tem.get_dc_line_emt_template(vf=self._var_factory),
        tem.get_dc_line_with_power_input_emt_template(vf=grid.var_factory),
        tem.get_valve_emt_template(vf=grid.var_factory),
        tem.get_transformer_emt_template(vf=grid.var_factory),
        tem.get_xfmr_emt_template(vf=grid.var_factory),
        tem.get_induction_motor_single_cage_emt_template(vf=grid.var_factory),
        tem.get_induction_motor_double_cage_emt_template(vf=grid.var_factory),
        tem.get_bess_avm_grid_following_emt_template(vf=grid.var_factory),
        tem.get_pv_avm_grid_following_emt_template(vf=grid.var_factory),
        tem.get_pv_avm_boost_grid_following_emt_template(vf=grid.var_factory),
        tem.get_gfm_emt_template(vf=grid.var_factory),

        # the following are functions that generate templates depending on phases or things
        tem.get_shunt_c_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True),
        tem.get_shunt_l_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True),
        tem.get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True),
        tem.get_exponential_load_emt(vf=grid.var_factory, phA=True, phB=True, phC=True),
        tem.get_load_ZIP_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True),
        tem.get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True),
        tem.get_bergeron_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True),

    ]


def test_generic_valve_template_is_visible_for_multiple_host_types() -> None:
    """
    Verify that the EMT valve template is exposed as a generic reusable template.

    :return: None.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit()
    add_emt_model_catalogue(grid)

    vsc_templates: List[object] = grid.get_dynamic_templates_by_device_type_and_domain(DeviceType.VscDevice, FmuTemplateDomain.EMT)
    dc_line_templates: List[object] = grid.get_dynamic_templates_by_device_type_and_domain(DeviceType.DCLineDevice, FmuTemplateDomain.EMT)

    vsc_template_names: List[str] = list(template.name for template in vsc_templates)
    dc_line_template_names: List[str] = list(template.name for template in dc_line_templates)

    assert "valve_emt_template" in vsc_template_names
    assert "valve_emt_template" in dc_line_template_names


def test_igbt_valve_uses_antiparallel_path_when_reverse_biased() -> None:
    """
    Verify that the retained valve logic enables reverse conduction for an IGBT with antiparallel diode.

    :return: None.
    """
    vf: VarFactory = VarFactory()
    templ = get_valve_emt_template(
        vf=vf,
        name="valve_logic_case",
        valve_tpe=ValveEmtType.Igbt,
        model_variant=ValveEmtModelVariant.Ideal,
        initial_state=ValveInitializationState.Blocked,
        antiparallel_diode=True,
    )
    block = templ.block
    block.unify_blocks()

    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob_valve_logic"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    updater = build_boundary_updater_from_block(problem)

    assert updater is not None

    params0: np.ndarray = problem.event_params_values.copy()
    x0: np.ndarray = problem.get_x0().copy()

    idx_mode: int = _get_runtime_param_index_by_name(problem, "path_mode")
    idx_v_valve: int = _get_var_index_by_name(problem, "v_valve")
    idx_i_valve: int = _get_var_index_by_name(problem, "i_f_dc")

    x0[idx_v_valve] = -0.2
    x0[idx_i_valve] = -0.1
    updater.update(0.0, x0, params0)

    assert params0[idx_mode] == -1.0


def test_thyristor_valve_latches_after_gate_release_until_current_extinction() -> None:
    """
    Verify that the thyristor forward path remains latched after the gate pulse disappears.

    :return: None.
    """
    vf: VarFactory = VarFactory()
    templ = get_valve_emt_template(
        vf=vf,
        name="thyristor_logic_case",
        valve_tpe=ValveEmtType.Thyristor,
        model_variant=ValveEmtModelVariant.Ideal,
        initial_state=ValveInitializationState.Blocked,
        antiparallel_diode=False,
    )
    block = templ.block
    block.unify_blocks()

    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob_thyristor_logic"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    updater = build_boundary_updater_from_block(problem)

    assert updater is not None

    params0: np.ndarray = problem.event_params_values.copy()
    x0: np.ndarray = problem.get_x0().copy()

    idx_mode: int = _get_runtime_param_index_by_name(problem, "path_mode")
    idx_gate: int = _get_runtime_param_index_by_name(problem, "gate_fired")
    idx_v_valve: int = _get_var_index_by_name(problem, "v_valve")
    idx_i_valve: int = _get_var_index_by_name(problem, "i_f_dc")

    params0[idx_gate] = 1.0
    x0[idx_v_valve] = 0.15
    x0[idx_i_valve] = 0.2
    updater.update(0.0, x0, params0)
    assert params0[idx_mode] == 1.0

    params0[idx_gate] = 0.0
    x0[idx_v_valve] = 0.05
    x0[idx_i_valve] = 0.08
    updater.update(1.0e-4, x0, params0)
    assert params0[idx_mode] == 1.0

    x0[idx_v_valve] = -0.05
    x0[idx_i_valve] = 0.0
    updater.update(2.0e-4, x0, params0)
    assert params0[idx_mode] == 0.0


def test_valve_template_initializes_mode_from_dc_power_flow_seed() -> None:
    """
    Verify that the PF-derived DC conduction seed initializes the retained path mode.

    :return: None.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=100.0, fbase=50.0)

    bus_ac: gce.Bus = gce.Bus(name="Bus_AC", Vnom=230.0, is_slack=True)
    bus_dc_from: gce.Bus = gce.Bus(name="Bus_DC_From", Vnom=320.0, is_dc=True)
    bus_dc_to: gce.Bus = gce.Bus(name="Bus_DC_To", Vnom=320.0, is_dc=True)
    gen: gce.Generator = gce.Generator(name="Generator", vset=1.0, Snom=100.0, freq=50.0, r1=0.001, x1=0.4)
    vsc: gce.VSC = gce.VSC(
        name="VSC",
        bus_from=bus_dc_from,
        bus_to=bus_ac,
        rate=100.0,
        control1=ConverterControlType.Qac,
        control2=ConverterControlType.Vm_dc,
        control1_val=0.0,
        control2_val=1.0,
    )
    dc_line_host: gce.DcLine = gce.DcLine(name="ValveHost", bus_from=bus_dc_from, bus_to=bus_dc_to, r=0.02, rate=100.0)
    dc_load: gce.Load = gce.Load(name="DC_Load", P=30.0, Q=0.0)

    grid.add_bus(bus_ac)
    grid.add_bus(bus_dc_from)
    grid.add_bus(bus_dc_to)
    grid.add_generator(bus_ac, gen)
    grid.add_vsc(vsc)
    grid.add_dc_line(dc_line_host)
    grid.add_load(bus_dc_to, dc_load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    pf_results, pf_results_3ph = _run_power_flow(grid)

    gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    vsc_mdl = get_emt_ideal_converter(vf=grid.var_factory, name=vsc.name).block
    valve_mdl = get_valve_emt_template(
        vf=grid.var_factory,
        name="ValveHost",
        valve_tpe=ValveEmtType.Igbt,
        model_variant=ValveEmtModelVariant.Ideal,
        initial_state=ValveInitializationState.FromPowerFlow,
        antiparallel_diode=True,
    ).block
    dc_load_mdl = get_dc_load_emt_template(vf=grid.var_factory, name="dc_load_for_valve_test").block

    set_emt_model(device=gen, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=vsc, model=vsc_mdl, var_factory=grid.var_factory)
    set_emt_model(device=dc_line_host, model=valve_mdl, var_factory=grid.var_factory)
    set_emt_model(device=dc_load, model=dc_load_mdl, var_factory=grid.var_factory)

    problem: EmtProblemDae = EmtProblemDae(
        grid=grid,
        options=_build_default_emt_options(),
        pf_results=pf_results,
        pf_results_3ph=pf_results_3ph,
    )

    mode_idx: int = _get_runtime_param_index_by_name(problem, "path_mode")
    pf_seed_idx: int = _get_runtime_param_index_by_name(problem, "path_mode_pf_seed")

    assert problem.event_params_values[pf_seed_idx] == 1.0
    assert problem.event_params_values[mode_idx] == 1.0

    assert problem.boundary_update is not None


def test_dc_line_runtime_case_responds_to_load_step() -> None:
    """
    Verify that the EMT DC-line runtime case reacts to one scheduled DC load step.

    :return: None.
    """
    grid, _, bus_dc_from, bus_dc_to, generator, vsc, dc_branch, dc_load = _build_demo_branch_circuit(
        branch_name="DC_Line_Runtime",
        load_power_mw=30.0,
    )

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    _assign_dc_line_runtime_models(grid, generator, vsc, dc_branch, dc_load)
    pf_results = _run_balanced_power_flow(grid)

    problem = EmtProblemDae(
        grid=grid,
        options=_build_default_emt_options(),
        pf_results=pf_results,
        pf_results_3ph=None,
    )
    solver = _create_symbolic_solver(problem, simulation_time_s=3.0e-3, time_step_s=1.0e-5)

    # This runtime case tests one explicit conductance-backed DC load step. The
    # generic Load device maps ``G`` to ``g_*`` and keeps ``P`` in ``Pl0_*`` as a
    # separate constant-power term, so this test must step the conductance
    # parameter directly instead of depending on any implicit remapping.
    load_power_idx_full = _get_constant_parameter_full_index(problem, "g")
    boundary_updater = LoadStepBoundaryUpdater(
        problem=problem,
        param_full_idx=load_power_idx_full,
        step_time_s=1.5e-3,
        initial_value_pu=0.0,
        final_value_pu=0.4,
    )

    simulation_output = solver.simulate(boundary_updater=boundary_updater)
    time_s, state_traj = simulation_output[0], simulation_output[1]

    current_trace = _extract_trace(problem, state_traj, dc_branch.emt_model.E(VarPowerFlowReferenceType.If_dc))
    from_voltage_trace = _extract_trace(problem, state_traj, bus_dc_from.emt_model.E(VarPowerFlowReferenceType.Vdc))
    to_voltage_trace = _extract_trace(problem, state_traj, bus_dc_to.emt_model.E(VarPowerFlowReferenceType.Vdc))

    # The load step creates a transient response rather than a new flat DC-line
    # equilibrium over the short simulation horizon. Compare windows immediately
    # before and after the scheduled step using the current magnitude so the
    # branch-orientation sign convention does not affect the assertion.
    pre_mask = (time_s > 0.9e-3) & (time_s < 1.4e-3)
    post_mask = (time_s > 1.55e-3) & (time_s < 2.0e-3)

    assert np.any(pre_mask)
    assert np.any(post_mask)
    assert float(np.mean(np.abs(current_trace[post_mask]))) > float(np.mean(np.abs(current_trace[pre_mask])))
    assert float(np.mean(np.abs(from_voltage_trace[post_mask] - to_voltage_trace[post_mask]))) > float(
        np.mean(np.abs(from_voltage_trace[pre_mask] - to_voltage_trace[pre_mask]))
    )


def test_dc_line_runtime_case_matches_pf_initialization() -> None:
    """
    Verify that the EMT DC-line initial condition matches the balanced PF operating point.

    :return: None.
    """
    grid, _, bus_dc_from, bus_dc_to, generator, vsc, dc_branch, dc_load = _build_demo_branch_circuit(
        branch_name="DC_Line_PF_Init",
        load_power_mw=30.0,
    )

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    _assign_dc_line_runtime_models(grid, generator, vsc, dc_branch, dc_load)
    pf_results = _run_balanced_power_flow(grid)

    problem = EmtProblemDae(
        grid=grid,
        options=_build_default_emt_options(),
        pf_results=pf_results,
        pf_results_3ph=None,
    )

    x0 = problem.get_x0()
    v_from_var = bus_dc_from.emt_model.E(VarPowerFlowReferenceType.Vdc)
    v_to_var = bus_dc_to.emt_model.E(VarPowerFlowReferenceType.Vdc)
    i_from_var = dc_branch.emt_model.E(VarPowerFlowReferenceType.If_dc)
    i_to_var = dc_branch.emt_model.E(VarPowerFlowReferenceType.It_dc)
    expected_v_from = float(np.abs(pf_results.voltage[1]))
    expected_v_to = float(np.abs(pf_results.voltage[2]))
    expected_i_from = float((np.real(pf_results.Sf[0]) / grid.Sbase) / max(expected_v_from, 1.0e-12))
    expected_i_to = float((np.real(pf_results.St[0]) / grid.Sbase) / max(expected_v_to, 1.0e-12))

    assert abs(float(x0[problem.get_var_idx(v_from_var)]) - expected_v_from) < 1.0e-9
    assert abs(float(x0[problem.get_var_idx(v_to_var)]) - expected_v_to) < 1.0e-9
    assert abs(float(x0[problem.get_var_idx(i_from_var)]) - expected_i_from) < 1.0e-9
    assert abs(float(x0[problem.get_var_idx(i_to_var)]) - expected_i_to) < 1.0e-9


def test_igbt_runtime_case_follows_gate_schedule() -> None:
    """
    Verify that the EMT IGBT runtime case follows the imposed gate schedule.

    :return: None.
    """
    grid, _, _, _, generator, vsc, valve_host, dc_load = _build_demo_branch_circuit(
        branch_name="IGBT_Runtime",
        load_power_mw=25.0,
        load_conductance_mw=25.0,
    )

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    _assign_valve_runtime_models(grid, generator, vsc, valve_host, dc_load)
    pf_results = _run_balanced_power_flow(grid)

    problem = EmtProblemDae(
        grid=grid,
        options=_build_default_emt_options(),
        pf_results=pf_results,
        pf_results_3ph=None,
    )
    solver = _create_symbolic_solver(problem, simulation_time_s=4.0e-3, time_step_s=1.0e-5)

    gate_param_idx = _get_runtime_param_index_by_name(problem, "gate_fired")
    mode_param_idx = _get_runtime_param_index_by_name(problem, "path_mode")
    boundary_updater = GateScheduleBoundaryUpdater(
        problem=problem,
        gate_param_idx=gate_param_idx,
        mode_param_idx=mode_param_idx,
        # The ideal runtime valve host becomes topologically singular if it is
        # opened at the initial operating point with an isolated constant-power
        # sink behind it. This case therefore uses an explicit conductance-backed
        # DC load, starts from the conducting PF-seeded path mode, and then turns
        # the valve off later to verify the retained gate/path schedule.
        event_time_s=np.array([0.0, 2.5e-3], dtype=float),
        event_value=np.array([1.0, 0.0], dtype=float),
        max_records=500,
    )

    solver.simulate(boundary_updater=boundary_updater)

    record_time_s = boundary_updater.get_record_time_s()
    gate_trace = boundary_updater.get_record_gate()
    mode_trace = boundary_updater.get_record_mode()

    pre_mask = record_time_s < 2.2e-3
    post_mask = record_time_s > 3.0e-3

    assert np.any(pre_mask)
    assert np.any(post_mask)
    assert float(np.min(gate_trace[pre_mask])) > 0.5
    # The retained valve mode may briefly switch between forward and reverse
    # conduction while the gate remains fired because the ideal two-terminal
    # branch has no directional current-control law. The runtime requirement of
    # this test is therefore that the path is conducting before turn-off and
    # blocked after turn-off, not that it stays strictly in forward mode.
    assert float(np.max(np.abs(mode_trace[pre_mask]))) > 0.5
    assert float(np.max(gate_trace[post_mask])) < 0.5
    assert float(np.max(mode_trace[post_mask])) < 0.5


def test_standalone_diode_case_charges_forward_and_stays_latched() -> None:
    """
    Verify that the standalone diode case charges the load and stays in forward conduction.

    :return: None.
    """
    problem, gate_idx, mode_idx, tracked_vars = _build_standalone_valve_case(ValveEmtType.Diode)
    base_updater = build_boundary_updater_from_block(problem)
    event_time_s, event_value = _get_standalone_gate_schedule(ValveEmtType.Diode)
    boundary_updater = StandaloneGateScheduleBoundaryUpdater(base_updater, gate_idx, mode_idx, event_time_s, event_value, 4000)
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=1.0e-2,
        h=1.0e-5,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )
    simulation_output = solver.simulate(boundary_updater=boundary_updater)
    time_s, state_traj = simulation_output[0], simulation_output[1]
    v_load_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["v_load"])], copy=True)
    i_branch_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["i_branch"])], copy=True)
    mode_trace = boundary_updater.get_record_mode()

    assert float(v_load_trace[0]) == 0.0
    assert float(v_load_trace[-1]) > 0.95
    assert float(np.max(i_branch_trace)) > 1.0
    assert float(np.min(i_branch_trace)) >= -1.0e-6
    assert float(mode_trace[-1]) > 0.5
    assert float(np.min(mode_trace)) >= 0.0
    assert float(np.min(np.diff(v_load_trace[50:500]))) >= -1.0e-4


def test_standalone_igbt_case_turns_on_and_off_cleanly() -> None:
    """
    Verify that the standalone IGBT case follows the gate schedule with a visible charge and discharge.

    :return: None.
    """
    problem, gate_idx, mode_idx, tracked_vars = _build_standalone_valve_case(ValveEmtType.Igbt)
    base_updater = build_boundary_updater_from_block(problem)
    event_time_s, event_value = _get_standalone_gate_schedule(ValveEmtType.Igbt)
    boundary_updater = StandaloneGateScheduleBoundaryUpdater(base_updater, gate_idx, mode_idx, event_time_s, event_value, 4000)
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=1.0e-2,
        h=1.0e-5,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )
    simulation_output = solver.simulate(boundary_updater=boundary_updater)
    time_s, state_traj = simulation_output[0], simulation_output[1]
    v_load_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["v_load"])], copy=True)
    i_branch_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["i_branch"])], copy=True)
    mode_trace = boundary_updater.get_record_mode()
    control_time_s = boundary_updater.get_record_time_s()

    pre_mask = control_time_s < 1.5e-3
    on_mask = (control_time_s > 2.2e-3) & (control_time_s < 5.5e-3)
    post_mask = control_time_s > 7.0e-3
    on_voltage_mask = (time_s > 2.2e-3) & (time_s < 5.5e-3)
    post_voltage_mask = time_s > 8.0e-3

    assert np.any(pre_mask)
    assert np.any(on_mask)
    assert np.any(post_mask)
    assert float(np.max(mode_trace[pre_mask])) < 0.5
    assert float(np.max(mode_trace[on_mask])) > 0.5
    assert float(np.max(mode_trace[post_mask])) < 0.5
    assert float(np.mean(v_load_trace[on_voltage_mask])) > 0.9
    assert float(np.mean(v_load_trace[post_voltage_mask])) < 0.4
    assert float(np.max(i_branch_trace[on_voltage_mask])) > 1.0
    assert float(np.max(np.abs(i_branch_trace[post_voltage_mask]))) < 0.05


def test_standalone_thyristor_case_latches_after_the_gate_pulse() -> None:
    """
    Verify that the standalone thyristor case remains conducting after the gate pulse disappears.

    :return: None.
    """
    problem, gate_idx, mode_idx, tracked_vars = _build_standalone_valve_case(ValveEmtType.Thyristor)
    base_updater = build_boundary_updater_from_block(problem)
    event_time_s, event_value = _get_standalone_gate_schedule(ValveEmtType.Thyristor)
    boundary_updater = StandaloneGateScheduleBoundaryUpdater(base_updater, gate_idx, mode_idx, event_time_s, event_value, 4000)
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=1.0e-2,
        h=1.0e-5,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )
    simulation_output = solver.simulate(boundary_updater=boundary_updater)
    time_s, state_traj = simulation_output[0], simulation_output[1]
    v_load_trace = np.array(state_traj[:, problem.get_var_idx(tracked_vars["v_load"])], copy=True)
    mode_trace = boundary_updater.get_record_mode()
    control_time_s = boundary_updater.get_record_time_s()

    pre_mask = control_time_s < 1.8e-3
    pulse_mask = (control_time_s > 2.05e-3) & (control_time_s < 2.35e-3)
    post_mask = control_time_s > 3.0e-3
    post_voltage_mask = time_s > 5.0e-3

    assert np.any(pre_mask)
    assert np.any(pulse_mask)
    assert np.any(post_mask)
    assert float(np.max(mode_trace[pre_mask])) < 0.5
    assert float(np.max(mode_trace[pulse_mask])) > 0.5
    assert float(np.min(mode_trace[post_mask])) > 0.5
    assert float(np.mean(v_load_trace[post_voltage_mask])) > 0.95
