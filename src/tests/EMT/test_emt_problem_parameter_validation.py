"""Tests for contextual EMT parameter diagnostics."""

from __future__ import annotations
from typing import Dict
import numpy as np
import pytest
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import resolve_constant_parameter_initial_value
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_governor_emt
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import (
    get_generator_thevenin_rl_emt_template_with_ref,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, Expr
from VeraGridEngine.enumerations import (
    DynamicSimulationMode,
    EmtInitializationMethod,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
    DynamicDeviceTemplateType,
    DynamicIntegrationMethod,
    EmtSolverTypes,
    SolverType,
)
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import (
    get_shunt_r_emt_template,
    get_shunt_l_emt_template,
    get_shunt_c_emt_template,
)
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model


def _build_runtime_seed_test_problem() -> EmtProblemDae:
    """Build the minimum problem-local storage required by runtime seed helpers.

    The object deliberately bypasses full electrical construction so these unit
    tests exercise only ownership and mutation semantics.

    :return: Uninitialized EMT problem with empty runtime storage.
    """
    problem: EmtProblemDae = EmtProblemDae.__new__(EmtProblemDae)
    problem._temp_init_guess = dict()
    problem._temp_post_init_guess = dict()
    problem._uid2idx_event_params = dict()
    problem._event_params_values = np.zeros(0, dtype=np.float64)
    problem._event_parameters_eqs = list()
    problem._runtime_parameter_eqs0 = list()
    problem._runtime_all_parameters_source = list()
    problem._runtime_all_eqs_source = list()
    problem._local_external_mapping_by_block_uid = dict()
    return problem


def _assert_mapping_target_is_required_runtime_parameter(
        block: Block,
        key: ParamPowerFlowReferenceType,
) -> None:
    """Verify that one PF-derived API target is owned by runtime storage.

    Generator-sharing values are calculated after static parameter assembly.
    Requiring an unresolved event placeholder protects that ordering and ensures
    the value cannot be accepted as a static fallback.

    :param block: Block that owns both the API mapping and runtime declaration.
    :param key: PF-derived generator-sharing mapping key to inspect.
    :return: None.
    """
    target: Var | None = block.api_obj_mapping.get(key, None)

    assert isinstance(target, Var)
    assert target in block.event_dict
    assert block.event_dict[target].value is None
    assert target not in block.parameters


def test_pf_derived_generator_sharing_targets_are_runtime_parameters() -> None:
    """Keep all predefined generator-sharing targets outside static parameters.

    The power-flow seed is only available after the EMT device model has passed
    static validation. Each predefined template must therefore expose sharing
    targets through ``event_dict`` while retaining its local API mapping.

    :return: None.
    """
    governor_factory: VarFactory = VarFactory()
    governor_block: Block = get_governor_emt(vf=governor_factory).block
    _assert_mapping_target_is_required_runtime_parameter(
        block=governor_block,
        key=ParamPowerFlowReferenceType.generator_share_p_ref,
    )

    simple_generator_factory: VarFactory = VarFactory()
    simple_generator_block: Block = get_simple_generator_emt_template(
        vf=simple_generator_factory,
    ).block
    _assert_mapping_target_is_required_runtime_parameter(
        block=simple_generator_block,
        key=ParamPowerFlowReferenceType.generator_share_p_ref,
    )
    _assert_mapping_target_is_required_runtime_parameter(
        block=simple_generator_block,
        key=ParamPowerFlowReferenceType.generator_share_q_ref,
    )

    thevenin_factory: VarFactory = VarFactory()
    thevenin_root: Block = get_generator_thevenin_rl_emt_template_with_ref(
        vf=thevenin_factory,
    ).block
    thevenin_block: Block = thevenin_root.children[0]
    _assert_mapping_target_is_required_runtime_parameter(
        block=thevenin_block,
        key=ParamPowerFlowReferenceType.generator_share_enable,
    )
    _assert_mapping_target_is_required_runtime_parameter(
        block=thevenin_block,
        key=ParamPowerFlowReferenceType.generator_share_p_ref,
    )
    _assert_mapping_target_is_required_runtime_parameter(
        block=thevenin_block,
        key=ParamPowerFlowReferenceType.generator_share_q_ref,
    )


def test_unresolved_emt_constant_reports_device_block_and_mapping() -> None:
    """Report the complete model ownership of a null EMT constant.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("r_dc")
    owner_block: Block = Block(
        name="R-L equations",
        parameters=dict(((parameter, Const(None)),)),
    )
    root_block: Block = Block(name="DC line", children=list((owner_block,)))
    static_parameter_values: Dict[Var, Const] = dict()

    with pytest.raises(ValueError) as exception_info:
        resolve_constant_parameter_initial_value(
            device=device,
            simulation_mode=DynamicSimulationMode.EMT,
            root_block=root_block,
            owner_block=owner_block,
            parameter=parameter,
            declared_value=Const(None),
            problem_mapping=static_parameter_values,
        )

    message: str = str(exception_info.value)
    assert "Unresolved EMT constant parameter" in message
    assert "r_dc" in message
    assert "R-L equations" in message
    assert "DC link" in message
    assert "not targeted by any api_obj_mapping" in message


def test_emt_constant_accepts_a_uid_equivalent_static_mapping() -> None:
    """Resolve an EMT constant from a cloned variable with the same UID.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("r_dc")
    mapped_parameter: Var = Var(
        "r_dc",
        uid=parameter.uid,
        non_mutable_uid=parameter.non_mutable_uid,
    )
    owner_block: Block = Block(
        name="R-L equations",
        parameters=dict(((parameter, Const(None)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.dc_line_r_pu, parameter),)),
    )
    root_block: Block = Block(
        name="DC line",
        children=list((owner_block,)),
    )
    static_parameter_values: Dict[Var, Const] = dict(((mapped_parameter, Const(0.02)),))

    resolved_value: Const = resolve_constant_parameter_initial_value(
        device=device,
        simulation_mode=DynamicSimulationMode.EMT,
        root_block=root_block,
        owner_block=owner_block,
        parameter=parameter,
        declared_value=Const(None),
        problem_mapping=static_parameter_values,
    )

    assert resolved_value.value == pytest.approx(0.02)


def test_emt_problem_ignores_mapping_only_static_target() -> None:
    """Do not register one EMT static value unless ``parameters`` declares it.

    :return: None.
    """
    parameter: Var = Var("mapping_only")
    block: Block = Block(
        name="legacy mapping-only block",
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.dc_line_r_pu, parameter),)),
    )
    problem: EmtProblemTemplate = EmtProblemTemplate(
        sys_block=block,
        static_parameter_values_mapping=dict(((parameter, Const(0.25)),)),
        glob_time=Var("time"),
    )

    assert problem.get_constant_parameters() == list()
    assert problem.get_parameters_values() == list()


def test_emt_problem_maps_declared_child_static_parameter() -> None:
    """Apply one mapped value to the child block that owns the declaration.

    :return: None.
    """
    parameter: Var = Var("declared_parameter")
    child_block: Block = Block(
        name="parameter owner",
        parameters=dict(((parameter, Const(None)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.dc_line_r_pu, parameter),)),
    )
    root_block: Block = Block(name="wrapper", children=list((child_block,)))
    problem: EmtProblemTemplate = EmtProblemTemplate(
        sys_block=root_block,
        static_parameter_values_mapping=dict(((parameter, Const(0.25)),)),
        glob_time=Var("time"),
    )

    assert problem.get_constant_parameters() == list((parameter,))
    assert problem.get_parameters_values()[0].value == pytest.approx(0.25)


def test_emt_problem_maps_declared_child_event_parameter() -> None:
    """Use a mapped device value as an event parameter's initial baseline.

    :return: None.
    """
    parameter: Var = Var("event_parameter")
    mapped_parameter: Var = Var(
        "event_parameter",
        uid=parameter.uid,
        non_mutable_uid=parameter.non_mutable_uid,
    )
    child_block: Block = Block(
        name="event parameter owner",
        event_dict=dict(((parameter, Const(0.1)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, parameter),)),
    )
    root_block: Block = Block(name="wrapper", children=list((child_block,)))
    problem: EmtProblemTemplate = EmtProblemTemplate(
        sys_block=root_block,
        static_parameter_values_mapping=dict(((mapped_parameter, Const(0.25)),)),
        glob_time=Var("time"),
    )

    assert problem.get_constant_parameters() == list()
    assert problem.get_variable_parameters() == list((parameter,))
    assert problem.get_event_parameter_equations()[0].value == pytest.approx(0.25)
    assert problem.event_params_init_dict[parameter.uid] == pytest.approx(0.25)
    assert child_block.event_dict[parameter].value == pytest.approx(0.1)


def test_emt_problem_maps_mode_parameter_without_changing_its_role() -> None:
    """Apply a mapped baseline while preserving a discrete mode declaration.

    :return: None.
    """
    parameter: Var = Var("mode_parameter")
    fallback: Const = Const(0.0)
    block: Block = Block(
        name="mode owner",
        mode_dict=dict(((parameter, fallback),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.converter_control_mode_1, parameter),)),
    )
    problem: EmtProblemTemplate = EmtProblemTemplate(
        sys_block=block,
        static_parameter_values_mapping=dict(((parameter, Const(1.0)),)),
        glob_time=Var("time"),
    )

    assert problem.get_variable_parameters() == list((parameter,))
    assert problem.get_event_parameter_equations()[0].value == pytest.approx(1.0)
    assert parameter in block.mode_dict
    assert parameter not in block.event_dict
    assert block.mode_dict[parameter] is fallback


def test_compiled_runtime_parameter_evaluator_uses_final_initial_values() -> None:
    """Delay compiled runtime evaluation until initialization has completed.

    Native initialization updates ``init_guess`` directly after the problem
    constructor has generated its runtime kernel. The interpreted construction
    path must observe those updates, and enabling the compiled simulation path
    must refresh its compact input vector before its first evaluation.

    :return: None.
    """
    source_var: Var = Var("initialized_source")
    runtime_parameter: Var = Var("derived_runtime_parameter")
    block: Block = Block(
        name="runtime initialization owner",
        algebraic_vars=list((source_var,)),
        algebraic_eqs=list((source_var,)),
        event_dict=dict(((runtime_parameter, source_var),)),
    )
    problem: EmtProblemTemplate = EmtProblemTemplate(
        sys_block=block,
        static_parameter_values_mapping=dict(),
        glob_time=Var("time"),
    )
    event_values: np.ndarray = problem.event_params_values.copy()

    # Reproduce the direct mutation performed by native initialization after
    # the runtime kernel and its compact bindings have already been created.
    problem.init_guess[source_var.uid] = 7.5
    interpreted_values: np.ndarray = problem.def_event_params_fn(event_values, 0.0)

    problem.enable_compiled_runtime_parameter_evaluator()
    compiled_values: np.ndarray = problem.def_event_params_fn(event_values, 0.0)

    assert interpreted_values[0] == pytest.approx(7.5)
    assert compiled_values[0] == pytest.approx(7.5)


def test_emt_api_runtime_seed_does_not_mutate_event_dict() -> None:
    """Keep an API-derived runtime value in problem-local seed storage.

    :return: None.
    """
    parameter: Var = Var("event_parameter")
    fallback: Const = Const(0.1)
    block: Block = Block(
        name="runtime owner",
        event_dict=dict(((parameter, fallback),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, parameter),)),
    )
    problem: EmtProblemDae = _build_runtime_seed_test_problem()

    problem._assign_event_mapping_value_if_present(
        mdl=block,
        key=ParamPowerFlowReferenceType.Pl0,
        value=0.25,
    )

    assert block.event_dict[parameter] is fallback
    assert problem._temp_init_guess[parameter.uid] == pytest.approx(0.25)
    assert parameter.uid not in problem._temp_post_init_guess


def test_emt_external_runtime_seed_does_not_mutate_event_dict() -> None:
    """Keep a PF-derived external runtime value outside the source Block.

    :return: None.
    """
    parameter: Var = Var("v_peak")
    fallback: Const = Const(1.0)
    block: Block = Block(
        name="runtime owner",
        event_dict=dict(((parameter, fallback),)),
        external_mapping=dict(((VarPowerFlowReferenceType.Vpk, parameter),)),
    )
    problem: EmtProblemDae = _build_runtime_seed_test_problem()

    problem.set_external_param(
        mdl=block,
        key=VarPowerFlowReferenceType.Vpk,
        value=1.25,
    )

    assert block.event_dict[parameter] is fallback
    assert problem._temp_init_guess[parameter.uid] == pytest.approx(1.25)
    assert problem._temp_post_init_guess[parameter.uid] == pytest.approx(1.25)


def test_emt_problem_rejects_duplicate_static_parameter_ownership() -> None:
    """Reject one parameter UID declared by both a wrapper and its child.

    :return: None.
    """
    parameter: Var = Var("duplicated_parameter")
    child_block: Block = Block(
        name="parameter owner",
        parameters=dict(((parameter, Const(1.0)),)),
    )
    root_block: Block = Block(
        name="invalid wrapper",
        parameters=dict(((parameter, Const(1.0)),)),
        children=list((child_block,)),
    )

    with pytest.raises(ValueError, match="declared more than once"):
        EmtProblemTemplate(
            sys_block=root_block,
            static_parameter_values_mapping=dict(),
            glob_time=Var("time"),
        )


def test_unresolved_emt_runtime_parameter_reports_required_source() -> None:
    """Reject a null runtime parameter even if init_eqs contains a duplicate.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("l_dc")
    owner_block: Block = Block(
        name="R-L equations",
        event_dict=dict(((parameter, Const(None)),)),
    )

    problem: EmtProblemDae = EmtProblemDae.__new__(EmtProblemDae)
    problem.options = EmtOptions(initialization_method=EmtInitializationMethod.Explicit)
    problem._variable_parameters = list((parameter,))
    problem._event_parameters_eqs = list((Const(None),))
    # Initialization equations belong to algebraic/state variables and must not
    # become a second parameter-value channel.
    problem._init_eqs_flat = dict(((parameter, Const(0.1)),))
    problem._runtime_parameter_owner_blocks = dict(((parameter.uid, owner_block),))
    problem._runtime_parameter_devices = dict(((parameter.uid, device),))
    problem._temp_init_guess = dict()
    problem._temp_post_init_guess = dict()
    problem.event_params_init_dict = dict()
    problem._runtime_mode_uids = set()

    with pytest.raises(ValueError, match="Unresolved EMT dynamic parameter 'l_dc'"):
        problem._validate_runtime_parameter_sources_after_power_flow()


def test_emt_runtime_parameter_accepts_power_flow_seed() -> None:
    """A PF-owned EMT placeholder is valid after its seed was recorded.

    :return: None.
    """
    device: DcLine = DcLine(name="DC link")
    parameter: Var = Var("i_dc_0")
    owner_block: Block = Block(
        name="R-L equations",
        event_dict=dict(((parameter, Const(None)),)),
    )

    problem: EmtProblemDae = EmtProblemDae.__new__(EmtProblemDae)
    problem.options = EmtOptions(initialization_method=EmtInitializationMethod.Explicit)
    problem._variable_parameters = list((parameter,))
    problem._event_parameters_eqs = list((Const(None),))
    problem._init_eqs_flat = dict()
    problem._runtime_parameter_owner_blocks = dict(((parameter.uid, owner_block),))
    problem._runtime_parameter_devices = dict(((parameter.uid, device),))
    problem._temp_init_guess = dict(((parameter.uid, 0.0),))
    problem._temp_post_init_guess = dict()
    problem.event_params_init_dict = dict()
    problem._runtime_mode_uids = set()

    problem._validate_runtime_parameter_sources_after_power_flow()


def _build_shunt_sizing_case(
        kind: DynamicDeviceTemplateType,
        nominal: float | None,
) -> tuple[MultiCircuit, Load, Generator, PowerFlowResults]:
    """Build one cold operating case with a separately declared sizing reference.

    :param kind: Built-in R, L or C family to dimension from nonzero scheduled power.
    :param nominal: Current owner-declared nominal, including an unusable null fixture.
    :return: Grid, load, declared source and unchanged zero-voltage PF handoff.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    bus: Bus = grid.add_bus(Bus(name="Cold bus", Vnom=10.0, is_slack=True))
    source: Generator = grid.add_generator(bus, Generator(name="Cold source", vset=1.0, Snom=900.0, x1=0.2, r1=0.01))
    template: EmtModelTemplate
    if kind == DynamicDeviceTemplateType.EMT_SHUNT_R_ABC:
        load: Load = grid.add_load(bus, Load(name="Sizing load", P=30.0))
        template = get_shunt_r_emt_template(grid.var_factory)
    elif kind == DynamicDeviceTemplateType.EMT_SHUNT_L_ABC:
        load = grid.add_load(bus, Load(name="Sizing load", Q=12.0))
        template = get_shunt_l_emt_template(grid.var_factory, True, True, True)
    else:
        load = grid.add_load(bus, Load(name="Sizing load", Q=-12.0))
        template = get_shunt_c_emt_template(grid.var_factory, True, True, True)
    owner: Block = template.block.children[0]
    sizing: Var = template.block.external_mapping[VarPowerFlowReferenceType.VmSizing]
    if nominal is None:
        owner.event_dict[sizing] = Const(None)
    else:
        template.block.set_parameter_in_model(sizing.name, nominal)
    # An ordinary runtime Vm with a positive default must still receive the
    # operating zero. Only the explicitly declared sizing role may use nominal.
    operating: Var = grid.var_factory.add_var("operating_vm_probe")
    owner.event_dict[operating] = Const(1.7)
    template.block.external_mapping[VarPowerFlowReferenceType.Vm] = operating
    get_bus_emt_template(grid, bus)
    set_emt_model(source, get_generator_thevenin_rl_emt_template_with_ref(grid.var_factory).block, grid.var_factory)
    set_emt_model(load, template.block, grid.var_factory)
    flow: PowerFlowDriver = PowerFlowDriver(grid, PowerFlowOptions(
        solver_type=SolverType.NR, retry_with_other_methods=False,
        tolerance=1e-10, max_iter=50, control_q=False,
    ))
    flow.run()
    assert np.all(flow.results.voltage == 0.0)
    return grid, load, source, flow.results


@pytest.mark.parametrize("kind", (
    DynamicDeviceTemplateType.EMT_SHUNT_R_ABC,
    DynamicDeviceTemplateType.EMT_SHUNT_L_ABC,
    DynamicDeviceTemplateType.EMT_SHUNT_C_ABC,
))
@pytest.mark.parametrize("nominal", (1.0, 1.1))
@pytest.mark.parametrize("provide_logger", (False, True))
def test_emt_sizing_initialization_reference(kind: DynamicDeviceTemplateType, nominal: float, provide_logger: bool) -> None:
    """Keep operating zero and current model sizing through construction/replay.

    :param kind: RLC family whose positive component value must remain defined.
    :param nominal: Authored model default, including an edit away from 1 pu.
    :param provide_logger: Cover omitted logger and preservation of a caller-owned logger.
    :return: None; source mutation, wrong role, stale replay or lost diagnostics fail.
    """
    grid: MultiCircuit
    load: Load
    source: Generator
    flow: PowerFlowResults
    grid, load, source, flow = _build_shunt_sizing_case(kind, nominal)
    assert load.emt_model is not None and source.emt_model is not None
    before: Dict[str, object] = load.emt_model.to_dict()
    logger: Logger | None = Logger() if provide_logger else None
    problem: EmtProblemDae = EmtProblemDae(
        grid, EmtOptions(initialization_method=EmtInitializationMethod.Explicit), pf_results=flow, logger=logger,
    )
    if logger is None:
        assert isinstance(problem.logger, Logger)
    else:
        assert problem.logger is logger
    assert "EMT impedance sizing uses declared nominal at zero PF voltage" in str(problem.logger)
    sizing: Var = load.emt_model.external_mapping[VarPowerFlowReferenceType.VmSizing]
    operating: Var = load.emt_model.external_mapping[VarPowerFlowReferenceType.Vm]
    assert problem.event_params_values[problem.uid2idx_event_params[sizing.uid]] == nominal
    assert problem.event_params_values[problem.uid2idx_event_params[operating.uid]] == 0.0
    assert np.all(flow.voltage == 0.0)
    assert load.emt_model.to_dict() == before
    # Component values have an independent unit/base oracle; scheduled power is
    # nonzero but the cold-state consumption remains zero until energization.
    omega: float = 2.0 * np.pi * grid.fBase
    expected: float
    if kind == DynamicDeviceTemplateType.EMT_SHUNT_R_ABC:
        expected = nominal ** 2 / 0.3
    elif kind == DynamicDeviceTemplateType.EMT_SHUNT_L_ABC:
        expected = nominal ** 2 / (0.12 * omega)
    else:
        expected = 0.12 / (nominal ** 2 * omega)
    owner: Block = load.emt_model.children[0]
    parameter: Var
    expression: Expr
    checked: int = 0
    for parameter, expression in owner.event_dict.items():
        if parameter.uid in (sizing.uid, operating.uid):
            pass
        else:
            component: float = float(problem.event_params_values[problem.uid2idx_event_params[parameter.uid]])
            assert np.isfinite(component) and np.isclose(component, expected, rtol=1e-12, atol=0.0)
            checked += 1
    assert checked == 3
    group: EmtEventsGroup = EmtEventsGroup(name="Sizing replay")
    grid.add_emt_events_group(group)
    problem.set_events_group(group)
    assert problem.event_params_values[problem.uid2idx_event_params[sizing.uid]] == nominal
    assert problem.event_params_values[problem.uid2idx_event_params[operating.uid]] == 0.0
    assert load.emt_model.to_dict() == before


@pytest.mark.parametrize("nominal", (None, 0.0, -1.0, float("nan"), float("inf")))
def test_emt_sizing_rejects_unusable_nominal(nominal: float | None) -> None:
    """Report unusable source data before component expressions/Jacobian evaluation.

    :param nominal: Null, nonpositive or nonfinite owner-declared nominal source.
    :return: None; the contextual model contract error and diagnostic are required.
    """
    grid: MultiCircuit
    load: Load
    source: Generator
    flow: PowerFlowResults
    grid, load, source, flow = _build_shunt_sizing_case(DynamicDeviceTemplateType.EMT_SHUNT_R_ABC, nominal)
    logger: Logger = Logger()
    with pytest.raises(ValueError, match="requires a finite positive declared nominal at zero PF voltage"):
        EmtProblemDae(grid, EmtOptions(), pf_results=flow, logger=logger)
    assert "Sizing load" in str(logger) and "Vm_pf" in str(logger)


def test_emt_zero_start_energizes_after_source_event() -> None:
    """Start from zero with nonzero scheduled load and energize a finite resistor.

    :return: None; initial operating/source zero, finite trajectories and converged energization are required.
    """
    grid: MultiCircuit
    load: Load
    source: Generator
    flow: PowerFlowResults
    grid, load, source, flow = _build_shunt_sizing_case(DynamicDeviceTemplateType.EMT_SHUNT_R_ABC, 1.1)
    assert source.emt_model is not None and load.bus.emt_model is not None
    group: EmtEventsGroup = EmtEventsGroup(name="Declared source energization")
    grid.add_emt_events_group(group)
    source_voltage: Var = source.emt_model.external_mapping[VarPowerFlowReferenceType.Vpk]
    grid.add_emt_event(EmtEvent(device=source, parameter=source_voltage, time=1e-5,
                              value=float(np.sqrt(2.0) * source.Vset), group=group))
    options: EmtOptions = EmtOptions(time_step=5e-6, simulation_time=3e-5, tolerance=1e-6,
                                    solver_type=EmtSolverTypes.StructuralAD,
                                    integration_method=DynamicIntegrationMethod.DaeBackEuler,
                                    initialization_method=EmtInitializationMethod.Explicit)
    problem: EmtProblemDae = EmtProblemDae(grid, options, pf_results=flow)
    problem.set_events_group(group)
    reference: VarPowerFlowReferenceType
    voltage_indices: np.ndarray = np.fromiter(
        (problem.uid2idx_vars[load.bus.emt_model.external_mapping[reference].uid]
         for reference in (VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.v_B, VarPowerFlowReferenceType.v_C)),
        dtype=np.int64, count=3,
    )
    assert np.all(problem.get_x0()[voltage_indices] == 0.0)
    assert problem.event_params_values[problem.uid2idx_event_params[source_voltage.uid]] == 0.0
    solver: StructuralVectorizedSolver = StructuralVectorizedSolver(
        problem=problem, t0=0.0, t_end=3e-5, h=5e-6, method=DynamicIntegrationMethod.DaeBackEuler,
        pred_method=DynamicIntegrationMethod.OdeEuler, verbose=False,
    )
    times: np.ndarray
    values: np.ndarray
    derivatives: np.ndarray
    initialized: bool
    converged: bool
    times, values, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
    assert initialized and converged and times.size > 1
    assert np.all(np.isfinite(values)) and np.all(np.isfinite(derivatives))
    assert float(np.max(np.abs(values[:, voltage_indices]))) > 1e-3
