# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, Tuple
from pathlib import Path
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSave
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup

import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_problem_factory import build_rms_problem
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.voltage_source_template import build_thevenin_voltage_source
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.line_matrix_conversion import build_physical_line_matrices_from_stored_admittances
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import build_line_static_matrices, assign_static_api_object_mapping_for_device, get_line_g_keys
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_thevenin_internal_shared_references
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicVector
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import (
    ExplicitInitializationResult,
    SymbolicVectorSingleEquationCompiler,
    build_symbolic_vector_single_equation_compiler,
    init_explicit_common,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model, set_rms_model
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtSolverTypes,
    ShuntConnectionType,
    EmtInitializationMethod,
    EmtInitializationStatus,
    TheveninSourceVoltageMode,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
    RmsInitializationMethod,
    RmsProblemTypes,
)

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.initialization_emt import (
    _collect_reduced_initialization_problem,
    run_emt_native_initialization,
)


class GenericEmtProblem(EmtProblemTemplate):
    """
    Minimal EMT problem implementation used by initialization workflow tests.
    """
    __slots__ = []


def run_common_explicit_initialization_for_test(
        problem: EmtProblemTemplate,
) -> ExplicitInitializationResult:
    """Run the same common explicit initializer used by ``EmtProblemDae``.

    This helper only adapts the generic test problem's storage to the common
    engine. It deliberately contains no initialization algorithm of its own.

    :param problem: Generic EMT problem prepared by the test fixture.
    :type problem: EmtProblemTemplate
    :return: Successful common explicit-initialization result.
    :rtype: ExplicitInitializationResult
    :raises RuntimeError: If the common initializer does not converge.
    """
    sys_vars: Dict[int, Var] = {
        variable.uid: variable
        for variable in problem.get_state_vars() + problem.get_algebraic_vars()
    }
    sys_diff_vars: Dict[int, Var] = {
        variable.uid: variable
        for variable in problem.get_diff_vars()
    }
    compile_single_equation: SymbolicVectorSingleEquationCompiler = (
        build_symbolic_vector_single_equation_compiler(
            compiler_names_dict=problem.get_compiler_names_dict(),
            alias_names_dict=problem.get_alias_names_dict(),
            vars_name=problem.VARS_NAME,
            diff_name=problem.DIFF_NAME,
            event_params_name=problem.VARIABLE_PARAMS_NAME,
            params_name=problem.CONSTANT_PARAMS_NAME,
        )
    )
    result: ExplicitInitializationResult = init_explicit_common(
        mdl=problem.sys_block,
        sys_vars=sys_vars,
        sys_diff_vars=sys_diff_vars,
        variable_parameters=problem.get_variable_parameters(),
        event_parameters_eqs=problem.event_parameters_eqs,
        constant_parameters=problem.get_constant_parameters(),
        init_guess=problem.init_guess,
        event_param_init_dict=problem.event_params_init_dict,
        diff_init_guess=problem.diff_init_guess,
        uid2idx_vars=problem.uid2idx_vars,
        uid2idx_diff=problem.uid2idx_diff,
        uid2idx_params=problem.uid2idx_params,
        uid2idx_event_params=problem.uid2idx_event_params,
        params_array=problem.get_parameters_values(),
        compile_single_equation=compile_single_equation,
        event_params_array_seed=problem.event_params_values,
    )

    if result.converged:
        problem.rebuild_runtime_param_vectors()
    else:
        raise RuntimeError(result.message)

    return result


def test_emt_registers_device_root_once_for_nested_initialization() -> None:
    """Register one recursive root when both parent and child own init equations.

    :return: None.
    """
    parent_state: Var = Var("parent_state")
    child_state: Var = Var("child_state")
    child_block: Block = Block(
        state_vars=list((child_state,)),
        state_eqs=list((Const(0.0),)),
        init_eqs=dict(((child_state, Const(2.0)),)),
        name="Nested initialization child",
    )
    parent_block: Block = Block(
        state_vars=list((parent_state,)),
        state_eqs=list((Const(0.0),)),
        init_eqs=dict(((parent_state, Const(1.0)),)),
        children=list((child_block,)),
        name="Nested initialization root",
    )
    problem: EmtProblemDae = EmtProblemDae.__new__(EmtProblemDae)
    problem._device_models_with_init_eqs = list()
    problem._device_models_with_init_eqs_seen = set()

    # Registering the device twice emulates repeated discovery without making
    # the recursive child an additional explicit-initialization entry.
    problem._register_init_model(parent_block)
    problem._register_init_model(parent_block)

    assert problem._device_models_with_init_eqs == [parent_block]
    assert problem._device_models_with_init_eqs_seen == {parent_block.uid}


def test_emt_registers_root_when_only_nested_block_has_initialization() -> None:
    """Keep the device root when initialization exists only in a descendant.

    :return: None.
    """
    child_state: Var = Var("nested_only_state")
    child_block: Block = Block(
        state_vars=list((child_state,)),
        state_eqs=list((Const(0.0),)),
        init_eqs=dict(((child_state, Const(3.0)),)),
        name="Only initialized nested block",
    )
    parent_block: Block = Block(
        children=list((child_block,)),
        name="Root without local initialization",
    )
    problem: EmtProblemDae = EmtProblemDae.__new__(EmtProblemDae)
    problem._device_models_with_init_eqs = list()
    problem._device_models_with_init_eqs_seen = set()

    problem._register_init_model(parent_block)

    assert problem._device_models_with_init_eqs == [parent_block]
    assert problem._device_models_with_init_eqs_seen == {parent_block.uid}


class SimpleInitializationContext:
    """
    Typed container for the tiny EMT initialization test problems.

    :ivar _x_var: State variable.
    :ivar _y_var: Algebraic variable.
    :ivar _dx_var: Differential variable.
    """
    __slots__ = ["_x_var", "_y_var", "_dx_var"]

    def __init__(self, x_var: Var, y_var: Var, dx_var: Var) -> None:
        """
        Build one simple initialization context.

        :param x_var: State variable.
        :param y_var: Algebraic variable.
        :param dx_var: Differential variable.
        """
        self._x_var: Var = x_var
        self._y_var: Var = y_var
        self._dx_var: Var = dx_var

    def get_x_var(self) -> Var:
        """Return the state variable."""
        return self._x_var

    def get_y_var(self) -> Var:
        """Return the algebraic variable."""
        return self._y_var

    def get_dx_var(self) -> Var:
        """Return the differential variable."""
        return self._dx_var


class TwoBusRealEmtContext:
    """
    Typed container for the real two-bus EMT benchmark case.

    :ivar _grid: Multi-circuit container.
    :ivar _bus0: Slack bus.
    :ivar _bus1: Load bus.
    :ivar _line0: EMT line.
    :ivar _load: EMT load.
    :ivar _gen0: EMT generator.
    :ivar _gen_mdl: Generator EMT block.
    :ivar _line_mdl: Line EMT block.
    :ivar _load_mdl: Load EMT block.
    :ivar _pf_results: Power-flow results object.
    """
    __slots__ = ["_grid", "_bus0", "_bus1", "_line0", "_load", "_gen0", "_gen_mdl", "_line_mdl", "_load_mdl", "_pf_results"]

    def __init__(
            self,
            grid: gce.MultiCircuit,
            bus0: gce.Bus,
            bus1: gce.Bus,
            line0: gce.Line,
            load: gce.Load,
            gen0: gce.Generator,
            gen_mdl: Block,
            line_mdl: Block,
            load_mdl: Block,
            pf_results: object,
    ) -> None:
        """
        Build one real-case context bundle.

        :param grid: Multi-circuit container.
        :param bus0: Slack bus.
        :param bus1: Load bus.
        :param line0: EMT line.
        :param load: EMT load.
        :param gen0: EMT generator.
        :param gen_mdl: Generator EMT block.
        :param line_mdl: Line EMT block.
        :param load_mdl: Load EMT block.
        :param pf_results: Power-flow results object.
        """
        self._grid: gce.MultiCircuit = grid
        self._bus0: gce.Bus = bus0
        self._bus1: gce.Bus = bus1
        self._line0: gce.Line = line0
        self._load: gce.Load = load
        self._gen0: gce.Generator = gen0
        self._gen_mdl: Block = gen_mdl
        self._line_mdl: Block = line_mdl
        self._load_mdl: Block = load_mdl
        self._pf_results: object = pf_results

    def get_grid(self) -> gce.MultiCircuit:
        """Return the grid object."""
        return self._grid

    def get_pf_results(self) -> object:
        """Return the power-flow results object."""
        return self._pf_results


class InitializationBenchmarkRecord:
    """
    Record of initialization benchmark results.

    :ivar _case_name: Name identifier for the test case.
    :ivar _method_name: Name of the initialization method used.
    :ivar _status_name: Final status of the initialization.
    :ivar _residual_inf: Infinity-norm of algebraic residual after initialization.
    :ivar _dx0_inf: Infinity-norm of derivative vector at initialization.
    :ivar _elapsed_s: Wall-clock time elapsed during initialization.
    """
    __slots__ = ["_case_name", "_method_name", "_status_name", "_residual_inf", "_dx0_inf", "_elapsed_s"]

    def __init__(
            self,
            case_name: str,
            method_name: str,
            status_name: str,
            residual_inf: float,
            dx0_inf: float,
            elapsed_s: float,
    ) -> None:
        self._case_name: str = case_name
        self._method_name: str = method_name
        self._status_name: str = status_name
        self._residual_inf: float = float(residual_inf)
        self._dx0_inf: float = float(dx0_inf)
        self._elapsed_s: float = float(elapsed_s)

    def get_case_name(self) -> str:
        """Return the case name."""
        return self._case_name

    def get_method_name(self) -> str:
        """Return the method name."""
        return self._method_name

    def get_status_name(self) -> str:
        """Return the status name."""
        return self._status_name

    def get_residual_inf(self) -> float:
        """Return the residual infinity-norm."""
        return self._residual_inf

    def get_dx0_inf(self) -> float:
        """Return the dx0 infinity-norm."""
        return self._dx0_inf

    def get_elapsed_s(self) -> float:
        """Return the elapsed time in seconds."""
        return self._elapsed_s


def build_single_state_single_algebraic_problem() -> Tuple[GenericEmtProblem, SimpleInitializationContext]:
    """
    Build a tiny EMT problem where explicit initialization resolves the state and
    consistent initialization resolves one algebraic variable.

    The problem consists of:
    - State variable x with differential dx
    - Algebraic variable y linked by equation y = x
    - Algebraic equation y = 2.0
    - Initial condition x = 2.0

    :returns: Tuple of (problem, context) where problem is the EMT problem
              and context contains variable references.
    """
    var_factory: VarFactory = VarFactory()
    x_var: Var = var_factory.add_var("x")
    y_var: Var = var_factory.add_var("y")
    dx_var: Var = var_factory.add_diff_var(name="d_x", base_var=x_var)

    block = Block(
        name="SingleStateSingleAlgebraicInit",
        state_vars=[x_var],
        diff_vars=[dx_var],
        state_eqs=[y_var - x_var],
        algebraic_vars=[y_var],
        algebraic_eqs=[y_var - Const(2.0)],
        init_eqs={x_var: Const(2.0)},
    )
    static_parameter_values_mapping: Dict[Var, Const] = dict()
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=var_factory.add_var("t_glob_init_0"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    context = SimpleInitializationContext(x_var=x_var, y_var=y_var, dx_var=dx_var)
    return problem, context


def build_unresolved_state_problem() -> Tuple[GenericEmtProblem, SimpleInitializationContext]:
    """
    Build a tiny EMT problem where one state is left unresolved and must be solved
    from the steady-state condition.

    The problem has no explicit initial conditions, requiring the
    initialization algorithm to find a consistent equilibrium.

    :returns: Tuple of (problem, context) where problem is the EMT problem
              and context contains variable references.
    """
    var_factory: VarFactory = VarFactory()
    x_var: Var = var_factory.add_var("x_eq")
    y_var: Var = var_factory.add_var("y_eq")
    dx_var: Var = var_factory.add_diff_var(name="d_x_eq", base_var=x_var)

    block = Block(
        name="UnresolvedStateEquilibriumInit",
        state_vars=[x_var],
        diff_vars=[dx_var],
        state_eqs=[y_var - x_var],
        algebraic_vars=[y_var],
        algebraic_eqs=[y_var - Const(3.0)],
    )
    static_parameter_values_mapping: Dict[Var, Const] = dict()
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=var_factory.add_var("t_glob_init_1"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    context = SimpleInitializationContext(x_var=x_var, y_var=y_var, dx_var=dx_var)
    return problem, context


def build_pf_seed_vs_explicit_seed_problem() -> Tuple[GenericEmtProblem, SimpleInitializationContext]:
    """
    Build a tiny EMT problem where explicit initialization changes the seeded state.

    The problem is designed to distinguish the power-flow seed from the explicit
    seed. The state variable is pre-seeded to one value, while ``init_eqs`` forces
    a different explicit initialization value.

    :returns: Tuple of (problem, context) where problem is the EMT problem and
              context contains variable references.
    """
    var_factory: VarFactory = VarFactory()
    x_var: Var = var_factory.add_var("x_pf_vs_explicit")
    y_var: Var = var_factory.add_var("y_pf_vs_explicit")
    dx_var: Var = var_factory.add_diff_var(name="d_x_pf_vs_explicit", base_var=x_var)

    block = Block(
        name="PfSeedVsExplicitSeedInit",
        state_vars=[x_var],
        diff_vars=[dx_var],
        state_eqs=[y_var - x_var],
        algebraic_vars=[y_var],
        algebraic_eqs=[y_var - x_var],
        init_eqs={x_var: Const(5.0)},
    )
    static_parameter_values_mapping: Dict[Var, Const] = dict()
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=var_factory.add_var("t_glob_init_pf_vs_explicit"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    problem.init_guess[x_var.uid] = 1.0
    problem.init_guess[y_var.uid] = 1.0
    context = SimpleInitializationContext(x_var=x_var, y_var=y_var, dx_var=dx_var)
    return problem, context


def evaluate_algebraic_residual_inf(problem: EmtProblemTemplate) -> float:
    """
    Evaluate the infinity-norm of the algebraic residual at the current stored
    initialization point.

    :param problem: EMT problem to evaluate.
    :returns: Maximum absolute residual value, or 0.0 if no algebraic equations.
    """
    algebraic_eqs: list[Expr] = problem.get_algebraic_eqs()
    if len(algebraic_eqs) == 0:
        return 0.0
    else:
        residual_fn = SymbolicVector(
            eqs=algebraic_eqs,
            compiler_names_dict=problem._compiler_names_dict,
            alias_names_dict=problem._alias_names_dict,
            VARS_NAME=problem.VARS_NAME,
            DIFF_NAME=problem.DIFF_NAME,
            EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
            PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
        )
        x0: np.ndarray = problem.get_x0()
        dx0: np.ndarray = problem.get_dx0()
        runtime_params: np.ndarray = problem.event_params_values.copy()
        runtime_params = problem.def_event_params_fn(runtime_params, 0.0)
        constant_params: np.ndarray = np.asarray([float(item.value) for item in problem.get_parameters_values()], dtype=np.float64)
        residual: np.ndarray = residual_fn(x0, dx0, runtime_params, constant_params)
        return float(np.max(np.abs(residual)))


def build_two_bus_real_emt_case(
        zip_load: bool = True,
        initialization_method: EmtInitializationMethod = EmtInitializationMethod.Auto,
        balanced_pf: bool = False,
        physical_conductance: float | None = None,
        numerical_damping_conductance: float = 0.0,
        source_voltage_mode: TheveninSourceVoltageMode = TheveninSourceVoltageMode.Balanced,
        load_q: float = 0.0,
        system_base: float = 2.0,
) -> Tuple[EmtProblemDae, TwoBusRealEmtContext]:
    """
    Build the standard real EMT two-bus benchmark case used by snapshot and
    initialization tests.

    Creates a grid with a slack generator at bus0 and a load at bus1,
    connected by a transmission line. Power flow is run to obtain
    initial operating point.

    :param zip_load: If True, use ZIP load model; otherwise use RLC shunt.
    :param initialization_method: EMT initialization method to use.
    :param balanced_pf: Use balanced rather than three-phase power flow.
    :param physical_conductance: Optional total shunt G for a diagonal physical pi fixture.
    :param numerical_damping_conductance: Optional EMT-only terminal shunt.
    :param source_voltage_mode: Explicit internal-voltage capability for the benchmark source.
    :param load_q: Total physical load reactive power in MVAr.
    :param system_base: Common three-phase power base in MVA.
    :returns: Tuple of (problem, context) with EMT problem and grid context.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=system_base, fbase=50.0)

    vnom: float = 10.0
    bus0 = gce.Bus(name="Bus0", Vnom=vnom, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=vnom)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)

    tower = gce.OverheadLineType(name="Tower", Vnom=vnom)
    wire = gce.Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line0.apply_template(tower, grid.Sbase, grid.fBase)
    if physical_conductance is None:
        pass
    else:
        # A diagonal balanced primitive allows the same physical circuit in both PF lanes.
        line0.R = 0.02
        line0.X = 0.15
        line0.B = 0.006
        line0.G = physical_conductance
        line0.disable_auto_updates()
        line0.ys.values[:] = 0.0
        line0.ys.values[1:4, 1:4] = np.eye(3) / complex(line0.R, line0.X)
        line0.ysh.values[:] = 0.0
        line0.ysh.values[1:4, 1:4] = np.eye(3) * complex(line0.G, line0.B) * 1.0e6

    r_ph: float = 100.0
    v_ph: float = vnom / (3.0 ** 0.5)
    p_ph: float = (v_ph ** 2) / r_ph
    load: gce.Load = gce.Load(name="load", P=3.0 * p_ph, Q=load_q,
                    P1=p_ph, P2=p_ph, P3=p_ph, Q1=load_q / 3.0, Q2=load_q / 3.0, Q3=load_q / 3.0)
    load.conn = ShuntConnectionType.GroundedStar

    gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq=50, r1=0.001, x1=1.7)

    grid.add_line(line0)
    grid.add_generator(bus=bus0, api_obj=gen0)
    grid.add_load(bus=bus1, api_obj=load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, source_voltage_mode=source_voltage_mode).block
    line_mdl = get_pi_line_emt_template(
        vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True,
        numerical_damping_conductance=numerical_damping_conductance,
    ).block
    if zip_load:
        load_mdl = get_load_ZIP_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block
    else:
        load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

    set_emt_model(device=gen0, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line0, model=line_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    pf_options = PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-10,
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
    power_flow = PowerFlowDriver(grid, pf_options) if balanced_pf else PowerFlowDriver3Ph(grid, pf_options)
    power_flow.run()
    pf_results = power_flow.results

    options = EmtOptions(
        time_step=5e-6,
        simulation_time=2e-4,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=initialization_method,
        verbose=0,
    )
    problem = EmtProblemDae(
        grid=grid,
        options=options,
        pf_results_3ph=None if balanced_pf else pf_results,
        pf_results=pf_results if balanced_pf else None,
    )

    context = TwoBusRealEmtContext(
        grid=grid,
        bus0=bus0,
        bus1=bus1,
        line0=line0,
        load=load,
        gen0=gen0,
        gen_mdl=gen_mdl,
        line_mdl=line_mdl,
        load_mdl=load_mdl,
        pf_results=pf_results,
    )
    return problem, context


@pytest.mark.parametrize("system_base", (2.0, 5.0))
def test_pf_rms_emt_same_physical_operating_point(system_base: float) -> None:
    """Compare native terminal quantities on one unchanged physical PF case.

    The algebraic RMS Thevenin model has no differential states; this test
    certifies consistency of this reference, not controlled-machine equilibrium.

    :param system_base: Common three-phase MVA base for all three domains.
    :return: None; current, power, voltage, loss or assembled-residual errors fail.
    """
    emt: EmtProblemDae
    context: TwoBusRealEmtContext
    emt, context = build_two_bus_real_emt_case(initialization_method=EmtInitializationMethod.ConsistentNewton,
        balanced_pf=True, physical_conductance=0.003, load_q=0.2, system_base=system_base)
    grid: gce.MultiCircuit = context.get_grid()
    pf: object = context.get_pf_results()
    assert isinstance(pf, PowerFlowResults)
    assert pf.converged
    original_voltage: np.ndarray = pf.voltage.copy()
    load: gce.Load = grid.loads[0]
    original_load: tuple[float, ...] = (load.P, load.Q, load.Pa, load.Pb, load.Pc, load.Qa, load.Qb, load.Qc)
    generator: gce.Generator = grid.generators[0]
    line: gce.Line = grid.lines[0]
    # Bind existing RMS owners to exactly the grid and PF already used by EMT.
    bus: gce.Bus
    for bus in grid.buses:
        initialize_bus_rms(bus, grid.var_factory)
    set_rms_model(generator, build_thevenin_voltage_source(grid.var_factory,
        resistance_pu=generator.R1, reactance_pu=generator.X1).block, grid.var_factory)
    set_rms_model(line, get_line_rms_template(grid.var_factory).block, grid.var_factory)
    set_rms_model(load, get_load_rms_template(grid.var_factory).block, grid.var_factory)
    rms: RmsProblemTemplate = build_rms_problem(grid, RmsOptions(problem_type=RmsProblemTypes.PowerBalance,
        initialization_method=RmsInitializationMethod.ConsistentNewton, tolerance=1e-8), pf)
    assert isinstance(rms, RmsProblemDae)
    rms.set_events_group(RmsEventsGroup(name="Shared physical reference"))
    emt.set_events_group(emt_events_group=EmtEventsGroup(name="Shared physical reference"))
    rms_values: np.ndarray = rms.get_x0()
    rms.update_variable_params(t=0.0, x_snapshot=rms_values)
    assert len(rms.state_vars) == 0
    assert np.max(np.abs(rms.rhs_algebraic(rms_values, rms.get_dx0()))) < rms.options.tolerance
    assert evaluate_algebraic_residual_inf(emt) < emt.options.init_newton_tol
    tolerance: float = max(1e-6, 10.0 * emt.options.init_newton_tol)
    rms_voltage: np.ndarray = np.empty(2, dtype=complex)
    bus_index: int
    for bus_index, bus in enumerate(grid.buses):
        magnitude: Var = bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
        angle: Var = bus.rms_model.external_mapping[VarPowerFlowReferenceType.Va]
        rms_voltage[bus_index] = rms_values[rms.uid2idx_vars[magnitude.uid]] * np.exp(1j * rms_values[rms.uid2idx_vars[angle.uid]])
    np.testing.assert_allclose(rms_voltage, pf.voltage, atol=tolerance, rtol=0.0)
    source_p: Var = generator.rms_model.external_mapping[VarPowerFlowReferenceType.P]
    source_q: Var = generator.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
    rms_source_power: complex = complex(rms_values[rms.uid2idx_vars[source_p.uid]], rms_values[rms.uid2idx_vars[source_q.uid]])
    current_real: Var = generator.rms_model.external_mapping[VarPowerFlowReferenceType.Ir]
    current_imaginary: Var = generator.rms_model.external_mapping[VarPowerFlowReferenceType.Ii]
    rms_source_current: complex = complex(rms_values[rms.uid2idx_vars[current_real.uid]], rms_values[rms.uid2idx_vars[current_imaginary.uid]])
    np.testing.assert_allclose(rms_source_power, pf.Sbus[0] / system_base, atol=tolerance, rtol=0.0)
    np.testing.assert_allclose(rms_source_current, np.conj(pf.Sbus[0] / system_base / pf.voltage[0]), atol=tolerance, rtol=0.0)
    # Recover source and line series phasors from solved i and di/dt quadratures.
    values: np.ndarray = emt.get_x0()
    derivatives: np.ndarray = emt.get_dx0()
    omega: float = 2.0 * np.pi * grid.fBase
    source_current: np.ndarray = np.empty(3, dtype=complex)
    series_current: np.ndarray = np.empty(3, dtype=complex)
    voltage_from: np.ndarray = np.empty(3, dtype=complex)
    voltage_to: np.ndarray = np.empty(3, dtype=complex)
    line_owner: Block = line.emt_model.children[0]
    phase_index: int
    reference: VarPowerFlowReferenceType
    for phase_index, reference in enumerate((VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C)):
        current: Var = generator.emt_model.external_mapping[reference]
        differential: Var = next(variable for variable in emt.get_diff_vars()
                                 if variable.base_var is not None and variable.base_var.uid == current.uid)
        source_current[phase_index] = complex(derivatives[emt.get_diff_var_idx(differential)] / omega,
                                             values[emt.get_var_idx(current)]) / np.sqrt(2.0)
        series_var: Var = line_owner.state_vars[phase_index]
        series_diff: Var = line_owner.diff_vars[phase_index]
        series_current[phase_index] = complex(derivatives[emt.get_diff_var_idx(series_diff)] / omega,
                                             values[emt.get_var_idx(series_var)]) / np.sqrt(2.0)
        derivative_f: Var = line_owner.external_mapping[(VarPowerFlowReferenceType.d_v_A_f,
            VarPowerFlowReferenceType.d_v_B_f, VarPowerFlowReferenceType.d_v_C_f)[phase_index]]
        derivative_t: Var = line_owner.external_mapping[(VarPowerFlowReferenceType.d_v_A_t,
            VarPowerFlowReferenceType.d_v_B_t, VarPowerFlowReferenceType.d_v_C_t)[phase_index]]
        voltage_from[phase_index] = complex(emt.init_guess[derivative_f.uid] / omega,
            values[emt.get_var_idx(line_owner.in_vars[phase_index])]) / np.sqrt(2.0)
        voltage_to[phase_index] = complex(emt.init_guess[derivative_t.uid] / omega,
            values[emt.get_var_idx(line_owner.in_vars[phase_index + 3])]) / np.sqrt(2.0)
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    np.testing.assert_allclose(voltage_from, pf.voltage[0] * rotation, atol=tolerance, rtol=0.0)
    np.testing.assert_allclose(voltage_to, pf.voltage[1] * rotation, atol=tolerance, rtol=0.0)
    np.testing.assert_allclose(source_current, rms_source_current * rotation, atol=tolerance, rtol=0.0)
    np.testing.assert_allclose(series_current, (voltage_from - voltage_to) / complex(line.R, line.X), atol=tolerance, rtol=0.0)
    current_from: np.ndarray = series_current + complex(line.G, line.B) * voltage_from / 2.0
    current_to: np.ndarray = -series_current + complex(line.G, line.B) * voltage_to / 2.0
    emt_terminal_power: np.ndarray = np.array((np.vdot(current_from, voltage_from), np.vdot(current_to, voltage_to))) / 3.0
    rms_terminal_power: np.ndarray = np.empty(2, dtype=complex)
    terminal_index: int
    references: tuple[VarPowerFlowReferenceType, VarPowerFlowReferenceType]
    for terminal_index, references in enumerate(((VarPowerFlowReferenceType.Pf, VarPowerFlowReferenceType.Qf),
                                               (VarPowerFlowReferenceType.Pt, VarPowerFlowReferenceType.Qt))):
        p_var: Var = line.rms_model.external_mapping[references[0]]
        q_var: Var = line.rms_model.external_mapping[references[1]]
        rms_terminal_power[terminal_index] = complex(rms_values[rms.uid2idx_vars[p_var.uid]], rms_values[rms.uid2idx_vars[q_var.uid]])
    pf_terminal_power: np.ndarray = np.array((pf.Sf[0], pf.St[0])) / system_base
    np.testing.assert_allclose(emt_terminal_power, pf_terminal_power, atol=tolerance, rtol=0.0)
    np.testing.assert_allclose(rms_terminal_power, pf_terminal_power, atol=tolerance, rtol=0.0)
    np.testing.assert_allclose(np.vdot(source_current, voltage_from) / 3.0, rms_source_power, atol=tolerance, rtol=0.0)
    np.testing.assert_allclose(-emt_terminal_power[1], complex(load.P, load.Q) / system_base, atol=tolerance, rtol=0.0)
    physical_losses: float = (line.R * np.vdot(series_current, series_current).real
        + line.G * (np.vdot(voltage_from, voltage_from).real + np.vdot(voltage_to, voltage_to).real) / 2.0) / 3.0
    assert abs(np.sum(emt_terminal_power).real - physical_losses) < tolerance
    assert abs(rms_source_power.real - load.P / system_base - physical_losses) < tolerance
    assert original_load == (load.P, load.Q, load.Pa, load.Pb, load.Pc, load.Qa, load.Qb, load.Qc)
    np.testing.assert_array_equal(pf.voltage, original_voltage)
    print("Shared PF/RMS/EMT physical reference:", system_base, "g_RMS", np.max(np.abs(rms.rhs_algebraic(rms_values, rms.get_dx0()))),
          "g_EMT", evaluate_algebraic_residual_inf(emt), "source_power_pu", rms_source_power, "loss_pu", physical_losses)


@pytest.mark.parametrize("system_base", (2.0, 5.0))
def test_shared_physical_case_no_disturbance_orbit(system_base: float) -> None:
    """Bound one cycle at three resolutions, with accuracy qualified at T/1600.

    :param system_base: Common three-phase MVA base.
    :return: None; closure, trajectory refinement or full residual errors fail.
    """
    errors: np.ndarray = np.empty(3)
    closures: np.ndarray = np.empty(3)
    period: float = 1.0 / 50.0
    step_index: int
    samples: int
    for step_index, samples in enumerate((400, 800, 1600)):
        problem: EmtProblemDae
        context: TwoBusRealEmtContext
        problem, context = build_two_bus_real_emt_case(initialization_method=EmtInitializationMethod.ConsistentNewton,
            balanced_pf=True, physical_conductance=0.003, load_q=0.2, system_base=system_base)
        problem.set_events_group(emt_events_group=EmtEventsGroup(name="No disturbance"))
        assert evaluate_algebraic_residual_inf(problem) < problem.options.init_newton_tol
        # Every declared harmonic state is tested; the source's shared angle winds.
        theta_reference: str = get_thevenin_internal_shared_references()[0]
        harmonic_states: list[Var] = list(variable for variable in problem.get_state_vars()
                                         if variable.shared_ref is None or variable.shared_ref.name != theta_reference)
        theta: Var = next(variable for variable in problem.get_state_vars()
                          if variable.shared_ref is not None and variable.shared_ref.name == theta_reference)
        indices: np.ndarray = np.array(tuple(problem.get_var_idx(variable) for variable in harmonic_states), dtype=int)
        differential_indices: np.ndarray = np.array(tuple(problem.get_diff_var_idx(next(differential
            for differential in problem.get_diff_vars() if differential.base_var is not None
            and differential.base_var.uid == variable.uid)) for variable in harmonic_states), dtype=int)
        initial: np.ndarray = problem.get_x0().copy()
        initial_derivatives: np.ndarray = problem.get_dx0().copy()
        # Check differential consistency at the actual post-replay initial point.
        constants: np.ndarray = np.array(tuple(float(value.value) for value in problem.get_parameters_values()))
        initial_runtime: np.ndarray = problem.def_event_params_fn(problem.event_params_values.copy(), 0.0)
        state_fn: SymbolicVector = SymbolicVector(eqs=problem.get_state_eqs(),
            compiler_names_dict=problem._compiler_names_dict, alias_names_dict=problem._alias_names_dict,
            VARS_NAME=problem.VARS_NAME, DIFF_NAME=problem.DIFF_NAME,
            EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME, PARAMS_NAME=problem.CONSTANT_PARAMS_NAME)
        initial_state_rhs: np.ndarray = state_fn(initial, initial_derivatives, initial_runtime, constants)
        assert np.max(np.abs(initial_state_rhs - initial_derivatives)) < problem.options.init_newton_tol
        omega: float = 2.0 * np.pi * 50.0
        phasors: np.ndarray = (initial_derivatives[differential_indices] / omega + 1j * initial[indices]) / np.sqrt(2.0)
        # Tighten Newton step consistency to distinguish discretization drift.
        problem.options.tolerance = 1e-10
        solver: StructuralCompiledSolver = build_emt_solver(options=problem.options, problem=problem,
            t0=0.0, t_end=period, h=period / samples, method=DynamicIntegrationMethod.DaeTrapezoidal)
        times: np.ndarray
        values: np.ndarray
        derivatives: np.ndarray
        initialized: bool
        converged: bool
        times, values, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
        assert initialized and converged
        assert len(times) == samples + 1 and abs(times[-1] - period) < 1e-12
        target: np.ndarray = np.sqrt(2.0) * np.imag(np.exp(1j * omega * times[:, None]) * phasors[None, :])
        normalization: np.ndarray = np.maximum(1.0, np.sqrt(2.0) * np.abs(phasors))
        errors[step_index] = np.max(np.abs(values[:, indices] - target) / normalization)
        closures[step_index] = np.max(np.abs(values[-1, indices] - initial[indices]) / normalization)
        angle_error: float = abs(values[-1, problem.get_var_idx(theta)] - initial[problem.get_var_idx(theta)] - 2.0 * np.pi)
        assert angle_error < 1e-8
        print("Orbit state errors:", samples, tuple(variable.name for variable in harmonic_states),
              np.max(np.abs(values[:, indices] - target) / normalization, axis=0), "closure", closures[step_index])
        # Replay the declared runtime equations and evaluate every assembled g row.
        residual_fn: SymbolicVector = SymbolicVector(eqs=problem.get_algebraic_eqs(),
            compiler_names_dict=problem._compiler_names_dict, alias_names_dict=problem._alias_names_dict,
            VARS_NAME=problem.VARS_NAME, DIFF_NAME=problem.DIFF_NAME,
            EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME, PARAMS_NAME=problem.CONSTANT_PARAMS_NAME)
        runtime: np.ndarray = problem.def_event_params_fn(problem.event_params_values.copy(), period)
        residual: np.ndarray = residual_fn(values[-1], derivatives[-1], runtime, constants)
        assert np.max(np.abs(residual)) < 10.0 * problem.options.tolerance
        print("Bounded EMT orbit:", system_base, samples, "trajectory", errors[step_index], "closure", closures[step_index], "g", np.max(np.abs(residual)))
    # Coarse resolutions demonstrate refinement; the absolute bound applies at T/1600.
    assert np.all(errors[1:] <= errors[:-1] + 10.0 * problem.options.init_newton_tol)
    assert np.all(closures[1:] <= closures[:-1] + 10.0 * problem.options.init_newton_tol)
    assert errors[-1] < 1e-3 and closures[-1] < 1e-3


def test_emt_driver_reports_initialization_scope(capsys: pytest.CaptureFixture[str]) -> None:
    """Report Explicit qualification through the existing report after converged steps.

    :param capsys: Pytest capture of driver output.
    :return: None; an unsupported steady-state certification label fails.
    """
    problem: EmtProblemDae
    context: TwoBusRealEmtContext
    problem, context = build_two_bus_real_emt_case(initialization_method=EmtInitializationMethod.Explicit,
        balanced_pf=True, physical_conductance=0.003)
    grid: gce.MultiCircuit = context.get_grid()
    grid.add_emt_events_group(EmtEventsGroup(name="Explicit scope"))
    problem.options.simulation_time = 4.0 * problem.options.time_step
    pf: object = context.get_pf_results()
    assert isinstance(pf, PowerFlowResults)
    driver: EmtSimulationDriver = EmtSimulationDriver(grid=grid, options=problem.options, pf_results=pf)
    driver.run()
    output: str = capsys.readouterr().out
    assert "periodic steady state was not verified" in output
    assert "steady_state_initialized" not in output and "Steady-state initialized:" not in output
    assert driver.results is not None
    assert np.all(driver.results.converged) and np.all(driver.results.well_initialized)


def test_consistent_newton_initializes_missing_algebraic_and_dx0() -> None:
    """
    Test the helper-level Explicit plus ConsistentNewton sequence on a tiny problem.

    This test explicitly runs the symbolic explicit stage first and then calls the
    native ConsistentNewton helper. It verifies that the helper pair resolves a
    simple problem with one state and one algebraic variable, producing
    x = 2.0, y = 2.0, and dx = 0.0.
    """
    problem, context = build_single_state_single_algebraic_problem()
    options = EmtOptions(initialization_method=EmtInitializationMethod.ConsistentNewton)

    explicit_result: ExplicitInitializationResult = run_common_explicit_initialization_for_test(problem)
    report = run_emt_native_initialization(problem, options)

    idx_x = problem.get_var_idx(context.get_x_var())
    idx_y = problem.get_var_idx(context.get_y_var())
    idx_dx = problem.get_diff_var_idx(context.get_dx_var())

    x0 = problem.get_x0()
    dx0 = problem.get_dx0()

    assert explicit_result.converged
    assert report.status == EmtInitializationStatus.RESOLVED
    assert abs(x0[idx_x] - 2.0) < 1e-9
    assert abs(x0[idx_y] - 2.0) < 1e-9
    assert abs(dx0[idx_dx] - 0.0) < 1e-9


def test_reduced_initialization_problem_keeps_seeded_algebraic_equations() -> None:
    """
    The reduced EMT initialization system must always include algebraic equations.

    Seeded PF guesses are only starting points; they must not suppress the
    algebraic correction stage when consistency equations are still present.
    """

    class _ProblemStub:
        __slots__ = ("init_guess", "sys_block", "_state_vars", "_state_eqs", "_algebraic_vars", "_algebraic_eqs")

        def __init__(self) -> None:
            state_var = Var("state_seeded")
            algebraic_var = Var("alg_seeded")
            self.init_guess = dict({state_var.uid: 3.0, algebraic_var.uid: 2.0})
            self.sys_block = Block()
            self.sys_block.init_eqs = dict()
            self._state_vars = list([state_var])
            self._state_eqs = list([Const(0.0)])
            self._algebraic_vars = list([algebraic_var])
            self._algebraic_eqs = list([algebraic_var - Const(1.0)])

        def get_state_vars(self) -> list[Var]:
            return self._state_vars

        def get_state_eqs(self) -> list[Const]:
            return self._state_eqs

        def get_algebraic_vars(self) -> list[Var]:
            return self._algebraic_vars

        def get_algebraic_eqs(self) -> list[Expr]:
            return self._algebraic_eqs

    payload = _collect_reduced_initialization_problem(_ProblemStub(), allow_state_equilibrium=True)

    assert payload is not None
    unknown_vars, residual_eqs, state_unknown_mask = payload
    assert [var.name for var in unknown_vars] == ["alg_seeded"]
    assert len(residual_eqs) == 1
    assert state_unknown_mask.tolist() == [0.0]


def test_consistent_newton_uses_state_equilibrium_for_unresolved_states() -> None:
    """
    Test that the native ConsistentNewton helper uses state equilibrium for unresolved states.

    Verifies that when no explicit initial conditions are provided,
    the helper finds the steady-state equilibrium with x = 3.0, y = 3.0.
    """
    problem, context = build_unresolved_state_problem()
    options = EmtOptions(initialization_method=EmtInitializationMethod.ConsistentNewton)

    report = run_emt_native_initialization(problem, options)

    idx_x = problem.get_var_idx(context.get_x_var())
    idx_y = problem.get_var_idx(context.get_y_var())
    idx_dx = problem.get_diff_var_idx(context.get_dx_var())

    x0 = problem.get_x0()
    dx0 = problem.get_dx0()

    assert report.status == EmtInitializationStatus.RESOLVED
    assert abs(x0[idx_x] - 3.0) < 1e-9
    assert abs(x0[idx_y] - 3.0) < 1e-9
    assert abs(dx0[idx_dx] - 0.0) < 1e-9


@pytest.mark.parametrize("method", [EmtInitializationMethod.ConsistentNewton, EmtInitializationMethod.PseudoTransient])
@pytest.mark.parametrize("fix_seeded_states", [True, False])
@pytest.mark.parametrize("use_init_equation", [True, False])
def test_global_initialization_can_release_seeded_states(
    method: EmtInitializationMethod, fix_seeded_states: bool, use_init_equation: bool,
) -> None:
    """A seed can be a fixed value or a starting guess for either global solver."""
    if use_init_equation:
        problem, context = build_pf_seed_vs_explicit_seed_problem()
        solved_value = 5.0
    else:
        problem, context = build_unresolved_state_problem()
        problem.init_guess[context.get_x_var().uid] = 1.0
        solved_value = 3.0
    options = EmtOptions(
        initialization_method=method, init_fix_seeded_states=fix_seeded_states,
        init_newton_tol=1e-8, init_ptc_max_iter=80,
    )
    report = run_emt_native_initialization(problem, options)
    assert report.status == EmtInitializationStatus.RESOLVED
    value = problem.get_x0()[problem.get_var_idx(context.get_x_var())]
    assert abs(value - (1.0 if fix_seeded_states else solved_value)) < 1e-7


def test_pseudo_transient_formulations_converge_on_simple_problem() -> None:
    """
    Test that the native PseudoTransient helper converges on a simple problem.

    This is a helper-level convergence test. The workflow-policy tests that prove
    pure PseudoTransient skips explicit initialization and avoids Newton are
    covered separately below.
    """
    reports = list()
    for use_backward_euler_residual in (False, True):
        problem, _ = build_unresolved_state_problem()
        options = EmtOptions(
            initialization_method=EmtInitializationMethod.PseudoTransient,
            init_newton_tol=1e-8,
            init_ptc_max_iter=80,
            init_ptc_backward_euler_residual=use_backward_euler_residual,
        )

        report = run_emt_native_initialization(problem, options)

        assert report.status == EmtInitializationStatus.RESOLVED
        assert report.method_used == EmtInitializationMethod.PseudoTransient
        assert report.final_residual_inf <= options.init_newton_tol
        reports.append(report)

    assert reports[0].pseudo_transient_steps < reports[1].pseudo_transient_steps


def test_auto_uses_global_pseudo_transient_after_newton_failure() -> None:
    """Auto must retain the global PTC fallback when its Newton stage cannot run."""
    problem, _ = build_unresolved_state_problem()
    options = EmtOptions(
        initialization_method=EmtInitializationMethod.Auto,
        init_newton_max_iter=0,
        init_newton_tol=1e-8,
        init_ptc_max_iter=80,
    )

    report = run_emt_native_initialization(problem, options)

    assert report.status == EmtInitializationStatus.RESOLVED
    assert report.method_used == EmtInitializationMethod.PseudoTransient
    assert report.newton_iterations == 0
    assert report.pseudo_transient_steps > 0


def test_explicit_mode_runs_only_explicit_in_problem_build() -> None:
    """
    Verify that Explicit mode completes during the explicit stage only.

    The top-level EMT build path must stop after explicit initialization and must
    not report any Newton or pseudo-transient work.
    """
    explicit_problem, _ = build_two_bus_real_emt_case(
        zip_load=True,
        initialization_method=EmtInitializationMethod.Explicit,
    )

    assert explicit_problem.initialization_report is not None
    assert explicit_problem.initialization_report.method_requested == EmtInitializationMethod.Explicit
    assert explicit_problem.initialization_report.method_used == EmtInitializationMethod.Explicit
    assert explicit_problem.initialization_report.status == EmtInitializationStatus.RESOLVED
    assert explicit_problem.initialization_report.newton_iterations == 0
    assert explicit_problem.initialization_report.pseudo_transient_steps == 0


def test_three_phase_line_current_seed_uses_pf_branch_flow() -> None:
    """The coupled three-phase line must not use a scalar impedance shortcut."""
    problem, context = build_two_bus_real_emt_case(
        zip_load=True,
        initialization_method=EmtInitializationMethod.Explicit,
        balanced_pf=False,
    )
    pf = problem.power_flow_results_3ph
    line = context.get_grid().lines[0]
    phase_data = (
        (VarPowerFlowReferenceType.if_A, pf.voltage_A, pf.Sf_A),
        (VarPowerFlowReferenceType.if_B, pf.voltage_B, pf.Sf_B),
        (VarPowerFlowReferenceType.if_C, pf.voltage_C, pf.Sf_C),
    )
    for current_ref, voltages, powers in phase_data:
        current_var = line.emt_model.E(current_ref)
        voltage = voltages[0]
        power = powers[0] / context.get_grid().Sbase
        expected = np.sqrt(2.0) * np.imag(3.0 * np.conj(power / voltage))
        assert np.isclose(problem.get_x0()[problem.get_var_idx(current_var)], expected, atol=1e-8)


def test_pseudotransient_mode_skips_explicit_seed_on_direct_native_path() -> None:
    """
    Verify that pure PseudoTransient keeps the power-flow seed and skips explicit init.

    The problem is seeded manually before the native initialization call. If
    explicit initialization ran, the state would move from 1.0 to 5.0 before the
    pseudo-transient loop starts. The current pure pseudo-transient policy must
    preserve the original seed because explicit initialization is intentionally
    skipped on this path.
    """
    problem, context = build_pf_seed_vs_explicit_seed_problem()
    options = EmtOptions(
        initialization_method=EmtInitializationMethod.PseudoTransient,
        init_newton_tol=1e-8,
        init_ptc_max_iter=40,
    )
    idx_x: int = problem.get_var_idx(context.get_x_var())
    x0_before: np.ndarray = problem.get_x0().copy()
    seeded_x_before: float = float(x0_before[idx_x])

    report = run_emt_native_initialization(problem, options)

    x0_after: np.ndarray = problem.get_x0()
    seeded_x_after: float = float(x0_after[idx_x])
    assert report.method_requested == EmtInitializationMethod.PseudoTransient
    assert seeded_x_before == 1.0
    assert seeded_x_after == seeded_x_before


def test_pseudotransient_mode_uses_no_newton() -> None:
    """
    Verify that pure PseudoTransient performs no Newton iterations.

    The native initialization dispatcher must keep pure PseudoTransient limited to
    the pseudo-transient path only.
    """
    problem, _ = build_unresolved_state_problem()
    options = EmtOptions(
        initialization_method=EmtInitializationMethod.PseudoTransient,
        init_newton_tol=1e-8,
        init_ptc_max_iter=80,
    )

    report = run_emt_native_initialization(problem, options)

    assert report.status == EmtInitializationStatus.RESOLVED
    assert report.method_used == EmtInitializationMethod.PseudoTransient
    assert report.newton_iterations == 0
    assert report.pseudo_transient_steps >= 0


def test_pseudotransient_mode_starts_from_pf_seed_only() -> None:
    """
    Verify that pure PseudoTransient starts from the PF seed, not the explicit seed.

    This test uses the same seed-distinguishing tiny problem as the explicit-skip
    test, but focuses on the start-value contract instead of the report fields.
    """
    problem, context = build_pf_seed_vs_explicit_seed_problem()
    options = EmtOptions(
        initialization_method=EmtInitializationMethod.PseudoTransient,
        init_newton_tol=1e-8,
        init_ptc_max_iter=40,
    )
    idx_x: int = problem.get_var_idx(context.get_x_var())

    assert float(problem.get_x0()[idx_x]) == 1.0
    report = run_emt_native_initialization(problem, options)

    assert report.method_requested == EmtInitializationMethod.PseudoTransient
    assert float(problem.get_x0()[idx_x]) == 1.0


def test_consistent_newton_mode_runs_explicit_then_newton() -> None:
    """
    Verify that ConsistentNewton uses explicit seeding and then Newton solving.

    The tiny problem has an explicit state seed and one unresolved algebraic
    variable. The explicit stage must set the state value, and the Newton stage
    must finish the consistent solve without entering the pseudo-transient path.
    """
    problem, context = build_single_state_single_algebraic_problem()
    options = EmtOptions(initialization_method=EmtInitializationMethod.ConsistentNewton)
    idx_x: int = problem.get_var_idx(context.get_x_var())
    idx_y: int = problem.get_var_idx(context.get_y_var())

    explicit_result: ExplicitInitializationResult = run_common_explicit_initialization_for_test(problem)
    x_after_explicit: np.ndarray = problem.get_x0().copy()
    report = run_emt_native_initialization(problem, options)
    x_after_native: np.ndarray = problem.get_x0()

    assert explicit_result.converged
    assert float(x_after_explicit[idx_x]) == 2.0
    assert report.status == EmtInitializationStatus.RESOLVED
    assert report.method_used == EmtInitializationMethod.ConsistentNewton
    assert report.pseudo_transient_steps == 0
    assert float(x_after_native[idx_x]) == 2.0
    assert float(x_after_native[idx_y]) == 2.0


def test_auto_initialization_is_not_worse_than_explicit_on_real_case() -> None:
    """
    Test that Auto initialization is comparable to Explicit on real case.

    Verifies that the Auto initialization method produces results
    comparable to Explicit initialization on a realistic two-bus grid.
    """
    explicit_problem, _ = build_two_bus_real_emt_case(
        zip_load=True,
        initialization_method=EmtInitializationMethod.Explicit,
    )
    auto_problem, _ = build_two_bus_real_emt_case(
        zip_load=True,
        initialization_method=EmtInitializationMethod.Auto,
    )

    explicit_res = evaluate_algebraic_residual_inf(explicit_problem)
    auto_res = evaluate_algebraic_residual_inf(auto_problem)

    assert np.isfinite(explicit_res)
    assert np.isfinite(auto_res)
    assert auto_res <= explicit_res + 1.0e-8
    assert auto_problem.initialization_report is not None
    assert auto_problem.initialization_report.status in {EmtInitializationStatus.RESOLVED, EmtInitializationStatus.FAILED}


def test_consistent_newton_solution_survives_pf_post_init_replay() -> None:
    """A solved network operating point must survive constructor PF-seed replay."""
    for balanced_pf in (False, True):
        problem, _ = build_two_bus_real_emt_case(
            zip_load=True,
            initialization_method=EmtInitializationMethod.ConsistentNewton,
            balanced_pf=balanced_pf,
            physical_conductance=0.003 if balanced_pf else None,
        )

        assert problem.initialization_report is not None
        assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED
        assert problem.initialization_report.final_residual_inf < 1.0e-8
        assert evaluate_algebraic_residual_inf(problem) < 1.0e-8


def test_untransposed_tower_uses_pf3_and_reaches_periodic_emt_voltage() -> None:
    """The tower's coupled phases need PF3 and a consistent EMT solve."""
    problem, context = build_two_bus_real_emt_case(
        zip_load=False,
        initialization_method=EmtInitializationMethod.Auto,
    )
    assert problem.power_flow_results_3ph is context.get_pf_results()
    assert problem.power_flow_results is None
    assert context.get_pf_results().converged
    assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED
    assert evaluate_algebraic_residual_inf(problem) < 1.0e-8

    problem.set_events_group(emt_events_group=EmtEventsGroup())
    solver = build_emt_solver(
        options=problem.options,
        problem=problem,
        t0=0.0,
        t_end=0.06,
        h=5.0e-6,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
    )
    times, values, _, initialized, converged = solver.simulate(boundary_updater=problem)
    assert initialized and converged
    voltage_indices = np.array([
        problem.get_var_idx(var)
        for var in problem.get_algebraic_vars()
        if var.name.startswith("v_")
    ])
    assert len(voltage_indices) == 6
    previous_cycle = int(np.argmin(np.abs(times - 0.04)))
    assert np.max(np.abs(values[-1, voltage_indices] - values[previous_cycle, voltage_indices])) < 1.0e-6


def test_pf3_explicit_tower_seed_reports_its_actual_algebraic_residual() -> None:
    """Default PI data match PF3; an optional extra shunt remains visible."""
    matched, _ = build_two_bus_real_emt_case(
        zip_load=True, initialization_method=EmtInitializationMethod.Explicit,
    )
    matched_residual = evaluate_algebraic_residual_inf(matched)
    assert matched_residual < 1.0e-9
    assert np.isclose(matched.initialization_report.final_residual_inf, matched_residual)

    damped, _ = build_two_bus_real_emt_case(
        zip_load=True, initialization_method=EmtInitializationMethod.Explicit,
        numerical_damping_conductance=1.0e-5,
    )
    damped_residual = evaluate_algebraic_residual_inf(damped)
    assert damped_residual > 1.0e-5
    assert np.isclose(damped.initialization_report.final_residual_inf, damped_residual)
    assert "algebraic residual" in damped.initialization_report.message


def test_pi_line_matrix_parameters_receive_compiler_names() -> None:
    """
    Ensure pi-line static matrix parameters are visible to EMT compilation.

    The pi-line state equations reference API-mapped matrix symbols such as
    ``Linv_aa_Pi``. Those symbols must be present in the constant-parameter map
    before the native initializer compiles the state right-hand side expressions.

    :return: None.
    """
    problem, context = build_two_bus_real_emt_case(
        zip_load=False,
        initialization_method=EmtInitializationMethod.Auto,
    )
    compiler_names_dict = problem.get_compiler_names_dict()
    line_block = context.get_grid().lines[0].emt_model
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.Linv_aa
    owner_block: Block | None = None
    mapped_parameter: Var | None = None

    # Static parameters belong to the block that publishes their API mapping.
    # Search recursively because the line root is only an interface wrapper.
    for candidate_block in line_block.get_all_blocks():
        candidate_parameter: Var | None = candidate_block.api_obj_mapping.get(mapping_key, None)
        if candidate_parameter is None:
            pass
        else:
            assert mapped_parameter is None, "Linv_aa must have exactly one owner in the line hierarchy"
            owner_block = candidate_block
            mapped_parameter = candidate_parameter

    assert owner_block is not None
    assert mapped_parameter is not None
    assert mapped_parameter.name == "Linv_aa"
    assert mapped_parameter in owner_block.parameters
    assert mapped_parameter.uid in compiler_names_dict


def test_real_pi_line_problem_uses_template_equivalent_static_matrix_values() -> None:
    """
    Ensure the real EMT pi-line build keeps the historical overhead-line values.

    This test compares the constant parameters that reach the full EMT problem
    against the original template-based line-matrix formulas used before the
    persisted ``line.ys`` and ``line.ysh`` reconstruction refactor.

    :return: None.
    """
    problem, context = build_two_bus_real_emt_case(
        zip_load=False,
        initialization_method=EmtInitializationMethod.Auto,
    )
    line = context.get_grid().lines[0]
    line_template = line.template
    assert bool(line.ys.phN) is False
    assert bool(line.ys.phA) is True
    assert bool(line.ys.phB) is True
    assert bool(line.ys.phC) is True
    assert line.ys.values.shape == (4, 4)
    assert line.ysh.values.shape == (4, 4)
    compiler_names_dict = problem.get_compiler_names_dict()
    g_full_actual: np.ndarray
    r_full_actual, l_full_actual, c_full_actual, g_full_actual = build_line_static_matrices(context.get_grid(), line)
    np.testing.assert_allclose(g_full_actual, 0.0, atol=1.0e-12)
    constant_parameters = problem.get_constant_parameters()
    constant_parameter_values = problem.get_parameters_values()
    constant_by_name: Dict[str, float] = dict()
    parameter_index: int = 0

    while parameter_index < len(constant_parameters):
        constant_by_name[constant_parameters[parameter_index].name] = float(constant_parameter_values[parameter_index].value)
        parameter_index += 1

    assert "Linv_aa" in constant_by_name
    assert "Caa" in constant_by_name
    assert any(name == "cprms[0]" for name in compiler_names_dict.values())

    omega: float = 2.0 * np.pi * float(context.get_grid().fBase)
    voltage_base: float = float(line.bus_from.Vnom) * 1.0e3
    sbase_va: float = float(context.get_grid().Sbase) * 1.0e6
    zbase: float = (voltage_base * voltage_base) / sbase_va
    ybase: float = 1.0 / zbase
    z_phys_total: np.ndarray = line_template.z_nabc * float(line.length)
    y_phys_total: np.ndarray = line_template.y_nabc * float(line.length)
    z_phys_recovered, y_phys_recovered = build_physical_line_matrices_from_stored_admittances(
        line=line,
        sbase_mva=float(context.get_grid().Sbase),
    )
    assert z_phys_recovered is not None
    assert y_phys_recovered is not None
    assert np.isclose(float(np.imag(z_phys_recovered[1, 1])), float(np.imag(z_phys_total[0, 0])))
    assert np.isclose(float(np.imag(z_phys_recovered[2, 2])), float(np.imag(z_phys_total[1, 1])))
    assert np.isclose(float(np.imag(z_phys_recovered[3, 3])), float(np.imag(z_phys_total[2, 2])))
    assert np.isclose(float(np.imag(y_phys_recovered[1, 1])), float(np.imag(y_phys_total[0, 0])))
    assert np.isclose(float(np.imag(y_phys_recovered[2, 2])), float(np.imag(y_phys_total[1, 1])))
    assert np.isclose(float(np.imag(y_phys_recovered[3, 3])), float(np.imag(y_phys_total[2, 2])))
    z_pu: np.ndarray = z_phys_total / zbase
    y_pu: np.ndarray = y_phys_total / ybase
    l_expected: np.ndarray = np.imag(z_pu) / omega
    c_expected: np.ndarray = (np.imag(y_pu) / omega) / 2.0
    linv_expected: np.ndarray = np.linalg.inv(l_expected)

    assert np.isclose(float(l_full_actual[0, 0]), float(l_expected[0, 0]))
    assert np.isclose(float(c_full_actual[0, 0]), float(c_expected[0, 0]))

    assert np.isclose(constant_by_name["Linv_aa"], float(linv_expected[0, 0]))
    assert np.isclose(constant_by_name["Caa"], float(c_expected[0, 0]))


def test_balanced_zip_load_is_initialized_by_its_model_equations() -> None:
    """Verify a balanced-PF ZIP load needs no problem-level state repair."""
    problem, context = build_two_bus_real_emt_case(
        zip_load=True,
        initialization_method=EmtInitializationMethod.Explicit,
        balanced_pf=True,
        physical_conductance=0.003,
    )
    model = context.get_grid().loads[0].emt_model
    variables = {
        var.name: var
        for block in model.get_all_blocks()
        for var in block.state_vars + block.algebraic_vars + list(block.event_dict)
    }
    def value(name: str) -> float:
        var = variables[name]
        if var.uid in problem.uid2idx_event_params:
            return float(problem.event_params_values[problem.uid2idx_event_params[var.uid]])
        return float(problem.get_x0()[problem.get_var_idx(var)])

    for phase in ("A", "B", "C"):
        u = value(f"u_{phase}")
        q = value(f"q_{phase}")
        voltage_squared = value(f"V{phase}2")
        voltage_magnitude = value(f"Vm{phase}")
        ratio = value(f"r{phase}")
        active_power = value(f"P_{phase}")
        reactive_power = value(f"Q_{phase}")
        current = value(f"i_{phase}")
        eps = value("eps")

        assert np.all(np.isfinite([
            u, q, voltage_squared, voltage_magnitude, ratio,
            active_power, reactive_power, current,
        ]))
        np.testing.assert_allclose(voltage_squared, u * u + q * q, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(voltage_magnitude, np.sqrt(voltage_squared + eps), rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(ratio, (voltage_magnitude + eps) / value("V0"), rtol=1e-10, atol=1e-12)
        active_zip = value("a1") * ratio * ratio + value("a2") * ratio + value("a3")
        reactive_zip = value("a4") * ratio * ratio + value("a5") * ratio + value("a6")
        # P0 and Q0 are device-seeded runtime parameters so events can modify
        # them after initialization without changing the ZIP model equations.
        np.testing.assert_allclose(
            active_power,
            -value(f"P0_{phase}") * active_zip,
            rtol=1e-10,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            reactive_power,
            -value(f"Q0_{phase}") * reactive_zip,
            rtol=1e-10,
            atol=1e-12,
        )
        expected_current = -3.0 * 2.0 * (u * (-active_power) + q * (-reactive_power)) / (u * u + q * q + eps)
        np.testing.assert_allclose(current, expected_current, rtol=1e-10, atol=1e-12)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])


def test_pi_line_physical_shunt_equivalence() -> None:
    """Check coupled NABC currents, losses and periodic initial derivatives.

    :return: None.
    """
    resistance: np.ndarray = 0.02 * np.eye(4) + 0.001 * np.ones((4, 4))
    reactance: np.ndarray = 0.15 * np.eye(4) + 0.01 * np.ones((4, 4))
    conductance: np.ndarray = 0.003 * np.eye(4) + 0.0002 * np.ones((4, 4))
    susceptance: np.ndarray = 0.006 * np.eye(4) + 0.0003 * np.ones((4, 4))
    from_phasors: np.ndarray = np.array((0.05 + 0.02j, 1.0 + 0.1j, -0.45 - 0.86j, -0.53 + 0.88j))
    to_phasors: np.ndarray = np.array((0.03 + 0.01j, 0.95 + 0.06j, -0.44 - 0.80j, -0.50 + 0.83j))
    voltage_derivative_f_keys: tuple[VarPowerFlowReferenceType, ...] = (
        VarPowerFlowReferenceType.d_v_N_f, VarPowerFlowReferenceType.d_v_A_f,
        VarPowerFlowReferenceType.d_v_B_f, VarPowerFlowReferenceType.d_v_C_f,
    )
    voltage_derivative_t_keys: tuple[VarPowerFlowReferenceType, ...] = (
        VarPowerFlowReferenceType.d_v_N_t, VarPowerFlowReferenceType.d_v_A_t,
        VarPowerFlowReferenceType.d_v_B_t, VarPowerFlowReferenceType.d_v_C_t,
    )
    frequency: float
    for frequency in (50.0, 60.0):
        phase_mask: tuple[bool, bool, bool, bool]
        for phase_mask in ((True, True, True, True), (False, True, True, True), (False, True, False, True)):
            grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=100.0, fbase=frequency)
            source: gce.Bus = grid.add_bus(gce.Bus(Vnom=132.0))
            target: gce.Bus = grid.add_bus(gce.Bus(Vnom=132.0))
            line: gce.Line = gce.Line(bus_from=source, bus_to=target, r=0.02, x=0.15)
            grid.add_line(line)
            # Preserve explicitly supplied phase data rather than regenerating sequence defaults.
            line.fill_3_phase_from_sequence()
            line.disable_auto_updates()
            line.ys.phN, line.ys.phA, line.ys.phB, line.ys.phC = phase_mask
            line.ysh.phN, line.ysh.phA, line.ysh.phB, line.ysh.phC = phase_mask
            active: np.ndarray = np.flatnonzero(np.array(phase_mask, dtype=bool))
            selector: tuple[np.ndarray, np.ndarray] = np.ix_(active, active)
            active_count: int = len(active)
            line.ys.values[:] = 0.0
            line.ys.values[selector] = np.linalg.inv((resistance + 1j * reactance)[selector])
            line.ysh.values[:] = 0.0
            line.ysh.values[selector] = (conductance + 1j * susceptance)[selector] * 1.0e6
            numerical: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)
            series_phasors: np.ndarray = (
                -numerical.passive_branch_data.Yft3 @ (from_phasors - to_phasors)
            )[active]
            capacitance: np.ndarray = susceptance[selector] / (4.0 * np.pi * frequency)
            damping: float
            for damping in (0.0, 1.0e-5):
                model: Block = get_pi_line_emt_template(
                    vf=grid.var_factory, phN=phase_mask[0], phA=phase_mask[1],
                    phB=phase_mask[2], phC=phase_mask[3], numerical_damping_conductance=damping,
                ).block
                child: Block = model.children[0]
                mapped: dict[Var, Const] = dict()
                assign_static_api_object_mapping_for_device(
                    grid=grid, device=line, mdl=model, problem_mapping=mapped, logger=None,
                )
                bindings: dict[int, float] = dict()
                parameter: Var
                value: Const
                for parameter, value in child.parameters.items():
                    assert value.value is not None
                    bindings[parameter.uid] = float(value.value)
                for parameter, value in mapped.items():
                    assert value.value is not None
                    bindings[parameter.uid] = float(value.value)
                from_current_phasors: np.ndarray = (
                    numerical.passive_branch_data.Yff3 @ from_phasors
                    + numerical.passive_branch_data.Yft3 @ to_phasors
                )[active] + damping * from_phasors[active]
                to_current_phasors: np.ndarray = (
                    numerical.passive_branch_data.Ytf3 @ from_phasors
                    + numerical.passive_branch_data.Ytt3 @ to_phasors
                )[active] + damping * to_phasors[active]
                samples: np.ndarray = np.arange(8) * (2.0 * np.pi / 8.0)
                terminal_power: np.ndarray = np.zeros(len(samples))
                sample_index: int
                angle: float
                for sample_index, angle in enumerate(samples):
                    rotation: complex = np.exp(1j * angle)
                    omega: float = 2.0 * np.pi * frequency
                    vf: np.ndarray = np.sqrt(2.0) * np.imag(from_phasors[active] * rotation)
                    vt: np.ndarray = np.sqrt(2.0) * np.imag(to_phasors[active] * rotation)
                    dvf: np.ndarray = omega * np.sqrt(2.0) * np.real(from_phasors[active] * rotation)
                    dvt: np.ndarray = omega * np.sqrt(2.0) * np.real(to_phasors[active] * rotation)
                    iser: np.ndarray = np.sqrt(2.0) * np.imag(series_phasors * rotation)
                    diser: np.ndarray = omega * np.sqrt(2.0) * np.real(series_phasors * rotation)
                    icap_f: np.ndarray = capacitance @ dvf
                    icap_t: np.ndarray = capacitance @ dvt
                    current_f: np.ndarray = np.sqrt(2.0) * np.imag(from_current_phasors * rotation)
                    current_t: np.ndarray = np.sqrt(2.0) * np.imag(to_current_phasors * rotation)
                    expected_states: np.ndarray = np.concatenate((iser, capacitance @ vf, capacitance @ vt))
                    expected_algebraic: np.ndarray = np.concatenate((icap_f, icap_t, current_f, current_t))
                    variable_index: int
                    for variable_index in range(active_count):
                        bindings[child.in_vars[variable_index].uid] = float(vf[variable_index])
                        bindings[child.in_vars[active_count + variable_index].uid] = float(vt[variable_index])
                        f_derivative: Var | None = child.external_mapping.get(voltage_derivative_f_keys[active[variable_index]], None)
                        t_derivative: Var | None = child.external_mapping.get(voltage_derivative_t_keys[active[variable_index]], None)
                        assert f_derivative is not None and t_derivative is not None
                        bindings[f_derivative.uid] = float(dvf[variable_index])
                        bindings[t_derivative.uid] = float(dvt[variable_index])
                    variable: Var
                    for variable_index, variable in enumerate(child.state_vars):
                        bindings[variable.uid] = float(expected_states[variable_index])
                    for variable_index, variable in enumerate(child.algebraic_vars):
                        bindings[variable.uid] = float(expected_algebraic[variable_index])
                    # The independent static primitive provides currents; the template must satisfy them.
                    equation: Expr
                    for equation in child.algebraic_eqs:
                        assert abs(float(equation.eval_uid(bindings))) < 1.0e-12
                    expected_derivatives: np.ndarray = np.concatenate((diser, icap_f, icap_t))
                    for variable_index, equation in enumerate(child.state_eqs):
                        np.testing.assert_allclose(
                            float(equation.eval_uid(bindings)), expected_derivatives[variable_index],
                            rtol=1.0e-10, atol=1.0e-12,
                        )
                    for variable, equation in child.init_eqs.items():
                        np.testing.assert_allclose(float(equation.eval_uid(bindings)), bindings[variable.uid], rtol=1.0e-10, atol=1.0e-12)
                    terminal_power[sample_index] = float((vf @ current_f + vt @ current_t) / 3.0)
                series_loss: float = float(np.real(np.vdot(series_phasors, resistance[selector] @ series_phasors)) / 3.0)
                physical_loss: float = float((
                    np.real(np.vdot(from_phasors[active], conductance[selector] @ from_phasors[active]))
                    + np.real(np.vdot(to_phasors[active], conductance[selector] @ to_phasors[active]))
                ) / 6.0)
                damping_loss: float = float(damping * (
                    np.vdot(from_phasors[active], from_phasors[active]).real
                    + np.vdot(to_phasors[active], to_phasors[active]).real
                ) / 3.0)
                np.testing.assert_allclose(np.mean(terminal_power), series_loss + physical_loss + damping_loss, rtol=1.0e-10, atol=1.0e-12)


def test_pi_line_conductance_pf_initialization() -> None:
    """Verify physical PF currents survive native initialization and step refinement.

    :return: None.
    """
    balanced_pf: bool
    for balanced_pf in (True, False):
        errors: np.ndarray = np.empty(2)
        step_index: int
        step: float
        for step_index, step in enumerate((5.0e-6, 2.5e-6)):
            problem: EmtProblemDae
            context: TwoBusRealEmtContext
            problem, context = build_two_bus_real_emt_case(
                initialization_method=EmtInitializationMethod.ConsistentNewton,
                balanced_pf=balanced_pf, physical_conductance=0.003,
            )
            assert problem.initialization_report is not None
            assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED
            assert evaluate_algebraic_residual_inf(problem) < problem.options.tolerance
            grid: gce.MultiCircuit = context.get_grid()
            line: gce.Line = grid.lines[0]
            child: Block = line.emt_model.children[0]
            problem.set_events_group(emt_events_group=EmtEventsGroup())
            solver: StructuralCompiledSolver = build_emt_solver(
                options=problem.options, problem=problem, t0=0.0, t_end=2.0e-4,
                h=step, method=DynamicIntegrationMethod.DaeTrapezoidal,
            )
            times: np.ndarray
            values: np.ndarray
            derivatives: np.ndarray
            initialized: bool
            converged: bool
            times, values, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
            assert initialized and converged
            assert np.all(np.isfinite(values))
            # Reconstruct sinusoidal terminal phasors from the initialized v and dv.
            from_phasors: np.ndarray = np.empty(3, dtype=complex)
            to_phasors: np.ndarray = np.empty(3, dtype=complex)
            omega: float = 2.0 * np.pi * grid.fBase
            phase_index: int
            for phase_index in range(3):
                from_voltage: Var = child.in_vars[phase_index]
                to_voltage: Var = child.in_vars[3 + phase_index]
                derivative_f: Var = child.external_mapping[(
                    VarPowerFlowReferenceType.d_v_A_f, VarPowerFlowReferenceType.d_v_B_f,
                    VarPowerFlowReferenceType.d_v_C_f,
                )[phase_index]]
                derivative_t: Var = child.external_mapping[(
                    VarPowerFlowReferenceType.d_v_A_t, VarPowerFlowReferenceType.d_v_B_t,
                    VarPowerFlowReferenceType.d_v_C_t,
                )[phase_index]]
                from_phasors[phase_index] = complex(
                    problem.init_guess[derivative_f.uid] / omega, values[0, problem.get_var_idx(from_voltage)],
                ) / np.sqrt(2.0)
                to_phasors[phase_index] = complex(
                    problem.init_guess[derivative_t.uid] / omega, values[0, problem.get_var_idx(to_voltage)],
                ) / np.sqrt(2.0)
            series: np.ndarray = (from_phasors - to_phasors) / complex(line.R, line.X)
            current_f: np.ndarray = series + complex(line.G, line.B) * from_phasors / 2.0
            current_t: np.ndarray = -series + complex(line.G, line.B) * to_phasors / 2.0
            rotation: np.ndarray = np.exp(1j * omega * times)
            expected: np.ndarray = np.sqrt(2.0) * np.imag(
                rotation[:, None] * np.concatenate((series, current_f, current_t))[None, :],
            )
            indices: np.ndarray = np.array(tuple(
                problem.get_var_idx(variable)
                for collection in (child.state_vars[:3], child.algebraic_vars[6:12])
                for variable in collection
            ), dtype=int)
            errors[step_index] = np.max(np.abs(values[:, indices] - expected))
            print("Physical G transient:", balanced_pf, step, errors[step_index], "residual", evaluate_algebraic_residual_inf(problem))
            assert errors[step_index] < 1.0e-4, (balanced_pf, step, errors[step_index])
            assert abs(np.real(np.vdot(from_phasors, current_f) + np.vdot(to_phasors, current_t))
                       - line.R * np.vdot(series, series).real
                       - line.G * (np.vdot(from_phasors, from_phasors).real
                                   + np.vdot(to_phasors, to_phasors).real) / 2.0) < 1.0e-12
        assert errors[1] <= errors[0] + 1.0e-10


def test_line_conductance_native_roundtrip(tmp_path: Path) -> None:
    """Persist copied G contracts while keeping a legacy saved Block unchanged.

    :param tmp_path: Isolated native archive directory.
    :return: None.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=2.0)
    source: gce.Bus = grid.add_bus(gce.Bus(name="source", Vnom=10.0))
    target: gce.Bus = grid.add_bus(gce.Bus(name="target", Vnom=10.0))
    modern: EmtModelTemplate = get_pi_line_emt_template(
        vf=grid.var_factory, phN=True, phA=True, phB=True, phC=True,
    )
    grid.add_emt_model(modern)
    legacy: EmtModelTemplate = EmtModelTemplate(name="recorded series-only line")
    legacy_voltage: Var = grid.var_factory.add_var("legacy_voltage")
    legacy_current: Var = grid.var_factory.add_var("legacy_current")
    legacy.block = Block(
        in_vars=list((legacy_voltage,)), algebraic_vars=list((legacy_current,)),
        algebraic_eqs=list((legacy_current - legacy_voltage,)),
    )
    grid.add_emt_model(legacy)
    line: gce.Line = gce.Line(name="modern", bus_from=source, bus_to=target, r=0.02, x=0.15, g=0.003)
    old_line: gce.Line = gce.Line(name="legacy", bus_from=source, bus_to=target, r=0.02, x=0.15, g=0.004)
    line.G0 = line.G
    line.G2 = line.G
    grid.add_line(line)
    grid.add_line(old_line)
    line.emt_template = modern
    # Persist independent phase data, including a nonzero neutral coupling.
    line.fill_3_phase_from_sequence()
    line.disable_auto_updates()
    line.ys.phN = True
    line.ysh.phN = True
    line.ys.values[0, 0] = 1.0 / complex(line.R, line.X)
    line.ysh.values[0, 0] = 0.001 * 1.0e6
    line.ysh.values[0, 1] = -0.0001 * 1.0e6
    line.ysh.values[1, 0] = -0.0001 * 1.0e6
    old_line.emt_template = legacy
    equations: tuple[str, ...] = tuple(str(equation) for equation in line.emt_model.children[0].algebraic_eqs)
    old_equations: tuple[str, ...] = tuple(str(equation) for equation in old_line.emt_model.algebraic_eqs)
    path: Path = tmp_path / "physical-line-g.veragrid"
    FileSave(circuit=grid, file_name=str(path)).save()
    loaded: gce.MultiCircuit = FileOpen(file_name=str(path)).open()
    assert len(loaded.lines) == 2
    assert len(loaded.emt_models) == 2
    assert tuple(str(equation) for equation in loaded.lines[0].emt_model.children[0].algebraic_eqs) == equations
    assert tuple(str(equation) for equation in loaded.lines[1].emt_model.algebraic_eqs) == old_equations
    assert loaded.lines[0].emt_template.idtag == modern.idtag
    assert loaded.lines[1].emt_template.idtag == legacy.idtag
    # Copy and persistence must keep mapping targets in their declaring Block.
    candidate: gce.Line
    for candidate in (line, loaded.lines[0]):
        mapped: dict[Var, Const] = dict()
        assign_static_api_object_mapping_for_device(
            grid=grid if candidate is line else loaded, device=candidate,
            mdl=candidate.emt_model, problem_mapping=mapped, logger=None,
        )
        owner: Block = candidate.emt_model.children[0]
        key: ParamPowerFlowReferenceType
        variable: Var
        count: int = 0
        for key, variable in owner.api_obj_mapping.items():
            if key in (
                ParamPowerFlowReferenceType.Gnn, ParamPowerFlowReferenceType.Gna, ParamPowerFlowReferenceType.Gnb, ParamPowerFlowReferenceType.Gnc,
                ParamPowerFlowReferenceType.Gan, ParamPowerFlowReferenceType.Gaa, ParamPowerFlowReferenceType.Gab, ParamPowerFlowReferenceType.Gac,
                ParamPowerFlowReferenceType.Gbn, ParamPowerFlowReferenceType.Gba, ParamPowerFlowReferenceType.Gbb, ParamPowerFlowReferenceType.Gbc,
                ParamPowerFlowReferenceType.Gcn, ParamPowerFlowReferenceType.Gca, ParamPowerFlowReferenceType.Gcb, ParamPowerFlowReferenceType.Gcc,
            ):
                count += 1
                assert any(variable is parameter for parameter in owner.parameters)
                assert mapped[variable].value is not None
                row: int
                row_keys: list[ParamPowerFlowReferenceType]
                for row, row_keys in enumerate(get_line_g_keys()):
                    if key in row_keys:
                        column: int = row_keys.index(key)
                        np.testing.assert_allclose(
                            mapped[variable].value, candidate.ysh.values[row, column].real * 1.0e-6 / 2.0,
                            rtol=1.0e-10, atol=1.0e-12,
                        )
                    else:
                        pass
            else:
                pass
        assert count == 16
        np.testing.assert_allclose(
            mapped[owner.api_obj_mapping[ParamPowerFlowReferenceType.Gaa]].value,
            candidate.G / 2.0, rtol=1.0e-10, atol=1.0e-12,
        )
    # Loading keeps the old equations; only explicit template reassignment upgrades them.
    replacement: EmtModelTemplate = loaded.lines[0].emt_template
    iteration: int
    for iteration in range(2):
        loaded.lines[1].enable_auto_updates()
        loaded.lines[1].emt_template = replacement
        assert len(loaded.lines[1].emt_model.children) == 1
        assert len(loaded.lines[1].emt_model.children[0].api_obj_mapping) == len(line.emt_model.children[0].api_obj_mapping)


def test_phase_source_runtime_pf_seed_consistency() -> None:
    """Preserve Phase-source PF quadratures through both native init stages.

    The same balanced physical benchmark is received through PF and PF3.
    The full source current phasor is recovered from its state and derivative,
    independently of the initialization report's convergence claim.

    :return: None; incorrect runtime promotion or emf consistency fails.
    """
    balanced_pf: bool
    method: EmtInitializationMethod
    for balanced_pf in (True, False):
        for method in (EmtInitializationMethod.Explicit, EmtInitializationMethod.ConsistentNewton):
            problem: EmtProblemDae
            context: TwoBusRealEmtContext
            problem, context = build_two_bus_real_emt_case(
                zip_load=True, initialization_method=method, balanced_pf=balanced_pf,
                physical_conductance=0.003, source_voltage_mode=TheveninSourceVoltageMode.Phase)
            grid: gce.MultiCircuit = context.get_grid()
            # This fixture has one source and no other injection at its bus;
            # its solved bus power therefore belongs to that source alone.
            assert len(grid.generators) == 1 and grid.loads[0].bus is not grid.generators[0].bus
            expected: np.ndarray = np.empty(3, dtype=complex)
            if balanced_pf:
                assert problem.power_flow_results is not None
                phase_rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
                expected[:] = np.conj(problem.power_flow_results.Sbus[0] / grid.Sbase
                                      / problem.power_flow_results.voltage[0]) * phase_rotation
            else:
                assert problem.power_flow_results_3ph is not None
                expected[:] = 3.0 * np.conj(np.array((
                    problem.power_flow_results_3ph.Sbus_A[0], problem.power_flow_results_3ph.Sbus_B[0],
                    problem.power_flow_results_3ph.Sbus_C[0])) / grid.Sbase / np.array((
                    problem.power_flow_results_3ph.voltage_A[0], problem.power_flow_results_3ph.voltage_B[0],
                    problem.power_flow_results_3ph.voltage_C[0])))
            values: np.ndarray = problem.get_x0()
            derivatives: np.ndarray = problem.get_dx0()
            native: np.ndarray = np.empty(3, dtype=complex)
            phase: int
            reference: VarPowerFlowReferenceType
            for phase, reference in enumerate((VarPowerFlowReferenceType.i_A,
                                               VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C)):
                current: Var = grid.generators[0].emt_model.external_mapping[reference]
                matching_derivative: Var | None = None
                differential: Var
                for differential in problem.get_diff_vars():
                    base_variable: Var | None = differential.base_var
                    if base_variable is not None and base_variable.uid == current.uid:
                        matching_derivative = differential
                    else:
                        pass
                assert matching_derivative is not None
                # EMT uses sine waveforms: the derivative carries Re(I), while
                # the instantaneous current carries Im(I). Both are required.
                native[phase] = complex(derivatives[problem.get_diff_var_idx(matching_derivative)]
                    / (2.0 * np.pi * grid.fBase), values[problem.get_var_idx(current)]) / np.sqrt(2.0)
            assert evaluate_algebraic_residual_inf(problem) < problem.options.tolerance
            np.testing.assert_allclose(native, expected, atol=problem.options.tolerance, rtol=0.0)
