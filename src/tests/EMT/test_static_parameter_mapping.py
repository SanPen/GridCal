# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Injections.external_grid import ExternalGrid
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.current_injection import CurrentInjection
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.static_generator import StaticGenerator
from VeraGridEngine.Devices.Injections.shunt import Shunt
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import (
    StaticParameterMappingDiagnostics,
    assign_api_mapping_value_if_present,
    assign_static_api_object_mapping_for_device,
    get_all_line_matrix_keys,
    get_line_c_keys,
    get_line_linv_keys,
    get_line_r_keys,
    get_line_g_keys,
    get_load_power_phase_values_pu_abc,
)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.injection_operating_point import (
    EmtInjectionOperatingPoint,
)
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from tests.EMT.test_injection_operating_point import _build_balanced_results, build_balanced_emt_injection_operating_point
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.converter_emt_multilinear_template import (
    get_emt_ideal_converter_multilinear,
)
from VeraGridEngine.Templates.Emt.converter_emt_template import (
    get_emt_ideal_converter,
    get_full_pseudo_emt_converter,
)
from VeraGridEngine.Templates.Emt.converter_soft_switched_emt_template import (
    get_soft_switched_emt_converter,
)
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import (
    get_switched_emt_converter,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DynamicSimulationMode,
    ExternalGridMode,
    ParamPowerFlowReferenceType,
    WindingType,
)


@pytest.mark.parametrize("use_kw", (False, True))
@pytest.mark.parametrize("explicit", (False, True))
@pytest.mark.parametrize("active", (False, True))
def test_phase_load_units_preserve_explicit_mw_and_total_fallback(use_kw: bool, explicit: bool, active: bool) -> None:
    """Preserve Load phase MW while normalizing only balanced total input units.

    :param use_kw: Interpret Load total P/Q in kW/kVAr.
    :param explicit: Populate explicit phase powers in MW/MVAr.
    :param active: Runtime balanced activity must not erase phase declarations.
    :return: None; source mutation, incorrect scaling or family leakage fails.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    bus: Bus = grid.add_bus(Bus(Vnom=10.0))
    scale: float = 1000.0 if use_kw else 1.0
    # Different explicit powers make a mistaken total fallback observable.
    load: Load = grid.add_load(bus, Load(P=30.0 * scale, Q=12.0 * scale,
        P1=9.0 if explicit else 0.0, P2=10.0 if explicit else 0.0, P3=11.0 if explicit else 0.0,
        Q1=3.0 if explicit else 0.0, Q2=4.0 if explicit else 0.0, Q3=5.0 if explicit else 0.0, active=active))
    load.use_kw = use_kw
    original: tuple[float, ...] = (load.P, load.Q, load.Pa, load.Pb, load.Pc, load.Qa, load.Qb, load.Qc)
    p_abc: np.ndarray
    q_abc: np.ndarray
    p_abc, q_abc = get_load_power_phase_values_pu_abc(load, grid)
    expected_p: np.ndarray = np.array((0.09, 0.1, 0.11) if explicit else (0.1, 0.1, 0.1))
    expected_q: np.ndarray = np.array((0.03, 0.04, 0.05) if explicit else (0.04, 0.04, 0.04))
    np.testing.assert_allclose(p_abc, expected_p, atol=1e-14)
    np.testing.assert_allclose(q_abc, expected_q, atol=1e-14)
    # Native direct references and the array mapper must agree before activity events.
    references: tuple[ParamPowerFlowReferenceType, ...] = (
        ParamPowerFlowReferenceType.Pl0_A, ParamPowerFlowReferenceType.Pl0_B, ParamPowerFlowReferenceType.Pl0_C,
        ParamPowerFlowReferenceType.Ql0_A, ParamPowerFlowReferenceType.Ql0_B, ParamPowerFlowReferenceType.Ql0_C)
    targets: tuple[Var, ...] = tuple(Var(name=str(reference)) for reference in references)
    block: Block = _make_block(dict(zip(references, targets)))
    mapping: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(grid, load, block, mapping, None)
    index: int
    for index in range(3):
        assert np.isclose(mapping[targets[index]].value, expected_p[index])
        assert np.isclose(mapping[targets[index + 3]].value, expected_q[index])
    # The common runtime provider consumes total-power units and gates only
    # the seed of inactive devices; raw phase declarations above stay intact.
    balanced_results: PowerFlowResults = _build_balanced_results(n_gen=0)
    operating_point: EmtInjectionOperatingPoint = build_balanced_emt_injection_operating_point(
        grid=grid,
        power_flow_results=balanced_results,
        bus_dict=dict(((bus, 0),)),
        injection_devices=list(grid.get_injection_devices_iter()),
    )
    balanced: np.ndarray = operating_point.get_ac_seed(0)
    expected_balanced: np.ndarray
    if active:
        expected_balanced = np.array((0j, -0.1 - 0.04j, -0.1 - 0.04j, -0.1 - 0.04j))
    else:
        expected_balanced = np.zeros(4, dtype=np.complex128)
    np.testing.assert_allclose(balanced, expected_balanced)
    assert original == (load.P, load.Q, load.Pa, load.Pb, load.Pc, load.Qa, load.Qb, load.Qc)
    # StaticGenerator totals retain their previous MW/MVAr contract.
    generator: StaticGenerator = StaticGenerator(P=30.0, Q=12.0)
    generator_p: np.ndarray
    generator_q: np.ndarray
    generator_p, generator_q = get_load_power_phase_values_pu_abc(generator, grid)
    np.testing.assert_allclose(generator_p, np.full(3, 0.1))
    np.testing.assert_allclose(generator_q, np.full(3, 0.04))


def _make_grid(sbase: float = 100.0, fbase: float = 50.0) -> SimpleNamespace:
    """Create a small grid-like object for static-mapping tests."""
    return SimpleNamespace(Sbase=sbase, fBase=fbase)


def _make_var(name: str) -> Var:
    """Create one symbolic parameter variable for test blocks."""
    return Var(name=name)


def _make_block(
        mapping: dict[ParamPowerFlowReferenceType, Var | None],
        event_keys: set[ParamPowerFlowReferenceType] | None = None,
) -> Block:
    """Create a block whose mapped variables have their declared local owner.

    :param mapping: API references and their optional symbolic targets.
    :param event_keys: Mapping keys whose targets are explicitly event-capable.
    :return: Block with static targets in ``parameters`` and runtime targets in
        ``event_dict``.
    """
    parameters: dict[Var, Const] = dict()
    event_dict: dict[Var, Const] = dict()
    explicit_event_keys: set[ParamPowerFlowReferenceType]
    if event_keys is None:
        explicit_event_keys = set()
    else:
        explicit_event_keys = set(event_keys)
    key: ParamPowerFlowReferenceType
    target: Var | None

    for key, target in mapping.items():
        if target is None:
            pass
        elif key in explicit_event_keys:
            event_dict[target] = Const(None)
        else:
            parameters[target] = Const(None)

    return Block(
        api_obj_mapping=dict(mapping),
        parameters=parameters,
        event_dict=event_dict,
    )


def _const_value(mapping: dict[Var, Const], block: Block, key: ParamPowerFlowReferenceType) -> float:
    """Return the assigned constant value for one exposed mapping key."""
    target: Var | None = block.api_obj_mapping[key]
    assert target is not None
    value: Const = mapping[target]
    assert isinstance(value, Const)
    assert value.value is not None
    return float(value.value)


def test_assign_api_mapping_initializes_event_target_without_mutating_block() -> None:
    """API mapping must seed an event target only in problem-side storage."""
    target: Var = _make_var("event_param")
    block: Block = Block(
        api_obj_mapping=dict({ParamPowerFlowReferenceType.Pl0: target}),
        event_dict=dict({target: Const(9.0)}),
    )
    problem_mapping: dict[Var, Const] = dict()

    assigned: bool = assign_api_mapping_value_if_present(
        mdl=block,
        key=ParamPowerFlowReferenceType.Pl0,
        value=1.0,
        logger=None,
        device_name="device",
        problem_mapping=problem_mapping,
    )

    assert assigned is True
    assert target not in block.parameters
    assert float(block.event_dict[target].value) == 9.0
    assert float(problem_mapping[target].value) == 1.0


def test_assign_api_mapping_initializes_mode_target_without_mutating_block() -> None:
    """API mapping must seed a mode target only in problem-side storage.

    :return: None.
    """
    target: Var = _make_var("mode_param")
    fallback: Const = Const(0.0)
    block: Block = Block(
        api_obj_mapping=dict({ParamPowerFlowReferenceType.converter_control_mode_1: target}),
        mode_dict=dict({target: fallback}),
    )
    problem_mapping: dict[Var, Const] = dict()

    assigned: bool = assign_api_mapping_value_if_present(
        mdl=block,
        key=ParamPowerFlowReferenceType.converter_control_mode_1,
        value=1.0,
        logger=None,
        device_name="device",
        problem_mapping=problem_mapping,
    )

    assert assigned is True
    assert target not in block.parameters
    assert target not in block.event_dict
    assert block.mode_dict[target] is fallback
    assert float(problem_mapping[target].value) == 1.0


def test_api_mapping_reports_when_device_value_overrides_template_fallback() -> None:
    """Report a resolved API value that replaces a concrete local fallback.

    :return: None.
    """
    grid: SimpleNamespace = _make_grid(sbase=100.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    load: Load = Load(name="load", P=30.0)
    load.bus = bus
    target: Var = _make_var("mapped_with_fallback")
    block: Block = Block(
        name="fallback_block",
        api_obj_mapping=dict({ParamPowerFlowReferenceType.Pl0: target}),
        event_dict=dict({target: Const(9.0)}),
    )
    problem_mapping: dict[Var, Const] = dict()
    logger: Logger = Logger()
    diagnostics: StaticParameterMappingDiagnostics = StaticParameterMappingDiagnostics(
        logger=logger,
        simulation_mode=DynamicSimulationMode.RMS,
    )

    assign_static_api_object_mapping_for_device(
        grid=grid,
        device=load,
        mdl=block,
        logger=diagnostics,
        problem_mapping=problem_mapping,
    )

    assert float(problem_mapping[target].value) == -0.3
    assert float(block.event_dict[target].value) == 9.0
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == "API-object initial value overrides the model-template fallback."
    assert logger.entries[0].device_class == DynamicSimulationMode.RMS.value


def test_api_mapping_required_device_source_does_not_report_override() -> None:
    """Treat ``Const(None)`` as a required source rather than a fallback.

    :return: None.
    """
    grid: SimpleNamespace = _make_grid(sbase=100.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    load: Load = Load(name="load", P=30.0)
    load.bus = bus
    target: Var = _make_var("required_device_value")
    block: Block = Block(
        name="required_source_block",
        api_obj_mapping=dict({ParamPowerFlowReferenceType.Pl0: target}),
        parameters=dict({target: Const(None)}),
    )
    problem_mapping: dict[Var, Const] = dict()
    logger: Logger = Logger()

    assign_static_api_object_mapping_for_device(
        grid=grid,
        device=load,
        mdl=block,
        logger=logger,
        problem_mapping=problem_mapping,
    )

    assert float(problem_mapping[target].value) == -0.3
    assert len(logger.entries) == 0


def test_api_mapping_rejects_conflicting_values_for_one_symbolic_uid() -> None:
    """Keep the first value when two API sources disagree for one target.

    :return: None.
    """
    grid: SimpleNamespace = _make_grid(sbase=100.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    load: Load = Load(name="load", P=30.0, Q=12.0)
    load.bus = bus
    first_target: Var = _make_var("first_conflicting_target")
    cloned_target: Var = Var(
        name="cloned_conflicting_target",
        uid=first_target.uid,
        non_mutable_uid=first_target.non_mutable_uid,
    )
    first_block: Block = Block(
        name="first_conflicting_block",
        api_obj_mapping=dict({ParamPowerFlowReferenceType.Pl0: first_target}),
        parameters=dict({first_target: Const(None)}),
    )
    cloned_block: Block = Block(
        name="cloned_conflicting_block",
        api_obj_mapping=dict({ParamPowerFlowReferenceType.Ql0: cloned_target}),
        parameters=dict({cloned_target: Const(None)}),
    )
    root_block: Block = Block(children=list([first_block, cloned_block]))
    problem_mapping: dict[Var, Const] = dict()
    logger: Logger = Logger()

    assign_static_api_object_mapping_for_device(
        grid=grid,
        device=load,
        mdl=root_block,
        logger=logger,
        problem_mapping=problem_mapping,
    )

    assert float(problem_mapping[first_target].value) == -0.3
    assert float(problem_mapping[cloned_target].value) == -0.3
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == (
        "Conflicting API-object initial values target the same symbolic parameter; later value skipped."
    )


def test_api_mapping_accepts_repeated_identical_value_for_one_symbolic_uid() -> None:
    """Allow several API references when their resolved value is identical.

    :return: None.
    """
    grid: SimpleNamespace = _make_grid(sbase=100.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    load: Load = Load(name="load", P=30.0, Q=30.0)
    load.bus = bus
    first_target: Var = _make_var("first_idempotent_target")
    cloned_target: Var = Var(
        name="cloned_idempotent_target",
        uid=first_target.uid,
        non_mutable_uid=first_target.non_mutable_uid,
    )
    first_block: Block = Block(
        name="first_idempotent_block",
        api_obj_mapping=dict({ParamPowerFlowReferenceType.Pl0: first_target}),
        parameters=dict({first_target: Const(None)}),
    )
    cloned_block: Block = Block(
        name="cloned_idempotent_block",
        api_obj_mapping=dict({ParamPowerFlowReferenceType.Ql0: cloned_target}),
        parameters=dict({cloned_target: Const(None)}),
    )
    root_block: Block = Block(children=list([first_block, cloned_block]))
    problem_mapping: dict[Var, Const] = dict()
    logger: Logger = Logger()

    assign_static_api_object_mapping_for_device(
        grid=grid,
        device=load,
        mdl=root_block,
        logger=logger,
        problem_mapping=problem_mapping,
    )

    assert float(problem_mapping[first_target].value) == -0.3
    assert float(problem_mapping[cloned_target].value) == -0.3
    assert len(logger.entries) == 0


def test_mapping_context_without_logger_keeps_numeric_assignment() -> None:
    """Keep static mapping active when a problem is constructed silently.

    :return: None.
    """
    target: Var = _make_var("silent_static_parameter")
    block: Block = Block(
        api_obj_mapping=dict({ParamPowerFlowReferenceType.device_active: target}),
        parameters=dict({target: Const(0.0)}),
    )
    problem_mapping: dict[Var, Const] = dict()
    diagnostics: StaticParameterMappingDiagnostics = StaticParameterMappingDiagnostics(
        logger=None,
        simulation_mode=DynamicSimulationMode.RMS,
    )

    assigned: bool = assign_api_mapping_value_if_present(
        mdl=block,
        key=ParamPowerFlowReferenceType.device_active,
        value=1.0,
        logger=diagnostics,
        device_name="device",
        problem_mapping=problem_mapping,
    )

    assert assigned is True
    assert float(problem_mapping[target].value) == 1.0


def test_missing_keys_are_skipped_silently() -> None:
    """Missing ``api_obj_mapping`` keys must not create parameters."""
    block: Block = _make_block(dict())

    assigned: bool = assign_api_mapping_value_if_present(
        mdl=block,
        key=ParamPowerFlowReferenceType.device_active,
        value=1.0,
        logger=None,
        device_name="device",
    )

    assert assigned is False
    assert len(block.parameters) == 0


def test_api_mapping_requires_same_block_parameter_owner() -> None:
    """Reject a target which is not declared by the mapping block.

    :return: None.
    """
    target: Var = _make_var("undeclared_static_param")
    block: Block = Block(
        api_obj_mapping=dict({ParamPowerFlowReferenceType.device_active: target}),
    )
    problem_mapping: dict[Var, Const] = dict()

    assigned: bool = assign_api_mapping_value_if_present(
        mdl=block,
        key=ParamPowerFlowReferenceType.device_active,
        value=1.0,
        logger=None,
        device_name="device",
        problem_mapping=problem_mapping,
    )

    assert assigned is False
    assert problem_mapping == dict()


def test_mapping_diagnostics_report_the_requesting_simulation_domain() -> None:
    """Label identical mapping-contract warnings as RMS or EMT by caller.

    :return: None.
    """
    simulation_modes: tuple[DynamicSimulationMode, DynamicSimulationMode] = (
        DynamicSimulationMode.RMS,
        DynamicSimulationMode.EMT,
    )
    simulation_mode: DynamicSimulationMode

    for simulation_mode in simulation_modes:
        target: Var = _make_var(f"undeclared_{simulation_mode.value}")
        block: Block = Block(
            api_obj_mapping=dict({
                ParamPowerFlowReferenceType.device_active: target,
            }),
        )
        logger: Logger = Logger()
        diagnostics: StaticParameterMappingDiagnostics = StaticParameterMappingDiagnostics(
            logger=logger,
            simulation_mode=simulation_mode,
        )

        assigned: bool = assign_api_mapping_value_if_present(
            mdl=block,
            key=ParamPowerFlowReferenceType.device_active,
            value=1.0,
            logger=diagnostics,
            device_name="device",
            problem_mapping=dict(),
        )

        assert assigned is False
        assert len(logger.entries) == 1
        assert logger.entries[0].device_class == simulation_mode.value


def test_converter_templates_keep_api_mappings_on_local_parameter_owners() -> None:
    """Enforce owner-local storage for every EMT converter mapping.

    :return: None.
    """
    templates: list[Block] = list((
        get_emt_ideal_converter(vf=VarFactory()).block,
        get_emt_ideal_converter_multilinear(vf=VarFactory()).block,
        get_full_pseudo_emt_converter(vf=VarFactory()).block,
        get_switched_emt_converter(vf=VarFactory()).block,
        get_soft_switched_emt_converter(vf=VarFactory()).block,
    ))
    root_block: Block
    current_block: Block
    mapping_key: ParamPowerFlowReferenceType
    mapping_target: Var | None

    for root_block in templates:
        for current_block in root_block.get_all_blocks():
            for mapping_key, mapping_target in current_block.api_obj_mapping.items():
                assert mapping_target is not None
                target_is_constant: bool = mapping_target in current_block.parameters
                target_is_runtime: bool = mapping_target in current_block.event_dict
                assert target_is_constant != target_is_runtime


def test_soft_switched_converter_maps_all_vsc_loss_coefficients() -> None:
    """Seed all three loss terms from the device rather than template defaults."""
    grid = _make_grid()
    dc_bus = Bus(name="dc", Vnom=2.0, is_dc=True)
    ac_bus = Bus(name="ac", Vnom=20.0)
    vsc = VSC(name="vsc", bus_from=dc_bus, bus_to=ac_bus)
    vsc.alpha1 = 0.004
    vsc.alpha2 = 0.02
    vsc.alpha3 = 0.03
    model = get_soft_switched_emt_converter(vf=VarFactory()).block
    values: dict[Var, Const] = {}

    assign_static_api_object_mapping_for_device(
        grid=grid, device=vsc, mdl=model, problem_mapping=values, logger=None
    )

    owner = next(
        block for block in model.get_all_blocks()
        if ParamPowerFlowReferenceType.alpha1 in block.api_obj_mapping
    )
    for key, expected in (
        (ParamPowerFlowReferenceType.alpha1, vsc.alpha1),
        (ParamPowerFlowReferenceType.alpha2, vsc.alpha2),
        (ParamPowerFlowReferenceType.alpha3, vsc.alpha3),
    ):
        target = owner.api_obj_mapping[key]
        assert target is not None
        assert np.isclose(float(values[target].value), expected)


def test_load_subset_mapping_assigns_only_requested_keys() -> None:
    """A model exposing a subset of load keys must receive only that subset."""
    grid: SimpleNamespace = _make_grid()
    bus: Bus = Bus(name="bus", Vnom=20.0)
    load: Load = Load(name="load", P1=30.0, Q1=12.0, active=False)
    load.bus = bus

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.device_active: _make_var("active"),
            ParamPowerFlowReferenceType.Pl0_A: _make_var("pa"),
        })
    )
    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=load, mdl=block, problem_mapping = problem_mapping, logger=None)

    assert len(problem_mapping.items()) == 2
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.device_active), 0.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Pl0_A), 0.3)


def test_external_grid_enum_mapping_is_explicit() -> None:
    """External-grid modes must map through explicit enum conversion."""
    grid: SimpleNamespace = _make_grid()
    bus: Bus = Bus(name="bus", Vnom=20.0)
    external_grid: ExternalGrid = ExternalGrid(name="eg", Vm=1.03, Va=0.2, mode=ExternalGridMode.VD)
    external_grid.bus = bus

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.external_grid_mode_code: _make_var("mode"),
            ParamPowerFlowReferenceType.external_grid_vm_pu: _make_var("vm"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=external_grid, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.external_grid_mode_code), 3.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.external_grid_vm_pu), 1.03)


def test_existing_load_mapping_values_remain_unchanged() -> None:
    """Historical AC-load EMT keys must keep their existing values."""
    grid: SimpleNamespace = _make_grid(sbase=100.0, fbase=60.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    load: Load = Load(name="load", P1=30.0, P2=20.0, P3=10.0, Q1=15.0, Q2=10.0, Q3=5.0)
    load.bus = bus

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.Pl0_A: _make_var("pla"),
            ParamPowerFlowReferenceType.Pl0_B: _make_var("plb"),
            ParamPowerFlowReferenceType.Pl0_C: _make_var("plc"),
            ParamPowerFlowReferenceType.Ql0_A: _make_var("qla"),
            ParamPowerFlowReferenceType.Ql0_B: _make_var("qlb"),
            ParamPowerFlowReferenceType.Ql0_C: _make_var("qlc"),
            ParamPowerFlowReferenceType.omega_base: _make_var("omega"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=load, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Pl0_A), 0.3)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Pl0_B), 0.2)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Pl0_C), 0.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Ql0_A), 0.15)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Ql0_B), 0.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Ql0_C), 0.05)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.omega_base), 2.0 * np.pi * 60.0)


def test_balanced_load_values_are_distributed_to_phase_keys() -> None:
    """Balanced load totals must feed per-phase static keys when phases are empty."""
    grid: SimpleNamespace = _make_grid(sbase=90.0, fbase=50.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    load: Load = Load(name="load", P=27.0, Q=9.0, G=18.0, B=6.0, Ir=12.0, Ii=3.0)
    load.bus = bus

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.Pl0_A: _make_var("pa"),
            ParamPowerFlowReferenceType.Ql0_B: _make_var("qb"),
            ParamPowerFlowReferenceType.load_gc_pu: _make_var("gc"),
            ParamPowerFlowReferenceType.load_ba_pu: _make_var("ba"),
            ParamPowerFlowReferenceType.load_irb_pu: _make_var("irb"),
            ParamPowerFlowReferenceType.load_iic_pu: _make_var("iic"),
            ParamPowerFlowReferenceType.Pl0_C: _make_var("plc"),
            ParamPowerFlowReferenceType.Ql0_A: _make_var("qla"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=load, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Pl0_A), 0.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Ql0_B), 1.0 / 30.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.load_gc_pu), 1.0 / 15.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.load_ba_pu), 1.0 / 45.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.load_irb_pu), 2.0 / 45.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.load_iic_pu), 1.0 / 90.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Pl0_C), 0.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Ql0_A), 1.0 / 30.0)


def test_load_api_mapping_seeds_runtime_targets_without_mutating_block() -> None:
    """Load API mapping must initialize event targets only in problem storage."""
    grid: SimpleNamespace = _make_grid(sbase=100.0, fbase=60.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    load: Load = Load(name="load", P=90.0, Q=30.0)
    load.bus = bus

    p_target: Var = _make_var("pla_evt")
    q_target: Var = _make_var("qla_evt")
    omega_target: Var = _make_var("omega_evt")
    block: Block = Block(
        api_obj_mapping=dict({
            ParamPowerFlowReferenceType.Pl0_A: p_target,
            ParamPowerFlowReferenceType.Ql0_A: q_target,
            ParamPowerFlowReferenceType.omega_base: omega_target,
        }),
        event_dict=dict({
            p_target: Const(0.0),
            q_target: Const(0.0),
            omega_target: Const(0.0),
        }),
    )

    problem_mapping: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(
        grid=grid,
        device=load,
        mdl=block,
        problem_mapping=problem_mapping,
        logger=None,
    )

    # Storage ownership remains unchanged: api_obj_mapping supplies the runtime
    # baseline without moving event-capable variables into parameters.
    assert p_target not in block.parameters
    assert q_target not in block.parameters
    assert omega_target not in block.parameters
    assert np.isclose(float(block.event_dict[p_target].value), 0.0)
    assert np.isclose(float(block.event_dict[q_target].value), 0.0)
    assert np.isclose(float(block.event_dict[omega_target].value), 0.0)
    assert np.isclose(float(problem_mapping[p_target].value), 0.3)
    assert np.isclose(float(problem_mapping[q_target].value), 0.1)
    assert np.isclose(float(problem_mapping[omega_target].value), 2.0 * np.pi * 60.0)


@pytest.mark.parametrize("active,use_kw", ((True, False), (True, True), (False, False), (False, True)))
@pytest.mark.parametrize("physical_p,physical_q,system_base,expected_p,expected_q",
                         ((10.0, 1.0, 100.0, -0.1, -0.01),
                          (-0.3, 0.0, 2.0, 0.15, 0.0),
                          (0.0, -0.3, 5.0, 0.0, 0.06)))
@pytest.mark.parametrize("runtime", (False, True))
@pytest.mark.parametrize("mapped", ((True, True), (True, False), (False, True)))
def test_balanced_ac_load_mapping_units_activity(
        active: bool, use_kw: bool, physical_p: float, physical_q: float,
        system_base: float, expected_p: float, expected_q: float,
        runtime: bool, mapped: tuple[bool, bool]) -> None:
    """Check physical-equivalent balanced powers and preserve separate contracts.

    :param active: Initial physical load activity.
    :param use_kw: Store equivalent source values in kW/kVAr when true.
    :param physical_p: Equivalent MW constant power.
    :param physical_q: Equivalent MVAr constant power.
    :param system_base: MVA normalization base.
    :param expected_p: Independently specified active injection in p.u.
    :param expected_q: Independently specified reactive injection in p.u.
    :param runtime: Declare the requested targets as event parameters.
    :param mapped: Request balanced P and Q independently.
    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=system_base, fbase=60.0)
    bus: Bus = grid.add_bus(Bus(Vnom=20.0))
    source_scale: float = 1000.0 if use_kw else 1.0
    load: Load = grid.add_load(bus=bus, api_obj=Load(
        P=physical_p * source_scale, Q=physical_q * source_scale, active=active))
    load.use_kw = use_kw
    original: tuple[float, float, bool, bool] = (load.P, load.Q, load.active, load.use_kw)
    p_target: Var = _make_var("balanced P")
    q_target: Var = _make_var("balanced Q")
    mapping: dict[ParamPowerFlowReferenceType, Var | None] = dict((
        (ParamPowerFlowReferenceType.device_active, _make_var("activity")),
        (ParamPowerFlowReferenceType.Pl0_A, _make_var("phase P")),
        (ParamPowerFlowReferenceType.Ql0_A, _make_var("phase Q")),
        (ParamPowerFlowReferenceType.omega_base, _make_var("frequency"))))
    if mapped[0]:
        mapping[ParamPowerFlowReferenceType.Pl0] = p_target
    else:
        pass
    if mapped[1]:
        mapping[ParamPowerFlowReferenceType.Ql0] = q_target
    else:
        pass
    event_keys: set[ParamPowerFlowReferenceType] = set(mapping) if runtime else set()
    block: Block = _make_block(mapping, event_keys)
    # Unrequested slots keep their declared manual source. Requested targets
    # receive an effective baseline in problem storage, never in this block.
    if runtime:
        block.event_dict[p_target] = Const(0.777)
        block.event_dict[q_target] = Const(-0.333)
    else:
        block.parameters[p_target] = Const(0.777)
        block.parameters[q_target] = Const(-0.333)
    declarations: dict[Var, Expr | Const] = block.event_dict if runtime else block.parameters
    declaration_values: dict[Var, float | None] = dict()
    target: Var
    expression: Expr | Const
    for target, expression in declarations.items():
        assert isinstance(expression, Const)
        declaration_values[target] = expression.value
    problem_mapping: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(grid, load, block, problem_mapping, None)
    if mapped[0]:
        assert float(problem_mapping[p_target].value) == pytest.approx(expected_p if active else 0.0)
    else:
        assert p_target not in problem_mapping
    if mapped[1]:
        assert float(problem_mapping[q_target].value) == pytest.approx(expected_q if active else 0.0)
    else:
        assert q_target not in problem_mapping
    # Total P/Q fallback uses the source unit; activity does not erase the
    # declared phase power or change the independent activity reference.
    assert _const_value(problem_mapping, block, ParamPowerFlowReferenceType.Pl0_A) == pytest.approx(load.P / (3.0 * system_base * source_scale))
    assert _const_value(problem_mapping, block, ParamPowerFlowReferenceType.Ql0_A) == pytest.approx(load.Q / (3.0 * system_base * source_scale))
    assert _const_value(problem_mapping, block, ParamPowerFlowReferenceType.device_active) == float(active)
    assert _const_value(problem_mapping, block, ParamPowerFlowReferenceType.omega_base) == pytest.approx(120.0 * np.pi)
    for target, expression in declarations.items():
        assert isinstance(expression, Const)
        assert expression.value == declaration_values[target]
    # The separate DC branch intentionally retains its original positive
    # declared P/G values, including the historical activity/unit behavior.
    dc_bus: Bus = grid.add_bus(Bus(Vnom=20.0, is_dc=True))
    dc_load: Load = grid.add_load(bus=dc_bus, api_obj=Load(P=load.P, G=12.0, active=active))
    dc_load.use_kw = use_kw
    dc_block: Block = _make_block(dict((
        (ParamPowerFlowReferenceType.Pl0, _make_var("DC P")),
        (ParamPowerFlowReferenceType.g, _make_var("DC G")))))
    dc_mapping: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(grid, dc_load, dc_block, dc_mapping, None)
    assert _const_value(dc_mapping, dc_block, ParamPowerFlowReferenceType.Pl0) == pytest.approx(load.P / system_base)
    assert _const_value(dc_mapping, dc_block, ParamPowerFlowReferenceType.g) == pytest.approx(12.0 / system_base)
    assert (load.P, load.Q, load.active, load.use_kw) == original


def test_existing_generator_mapping_values_remain_unchanged() -> None:
    """Historical generator EMT keys must keep their existing values."""
    grid: SimpleNamespace = _make_grid(fbase=60.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    generator: Generator = Generator(name="gen", r1=0.01, x1=0.2, x0=0.08)
    generator.bus = bus

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.omega_base: _make_var("omega"),
            ParamPowerFlowReferenceType.R1: _make_var("r1"),
            ParamPowerFlowReferenceType.X1: _make_var("x1"),
            ParamPowerFlowReferenceType.X0: _make_var("x0"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=generator, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.omega_base), 2.0 * np.pi * 60.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.R1), 0.01)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.X1), 0.2)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.X0), 0.08)


def test_generator_nominal_frequency_mapping_uses_device_frequency() -> None:
    """Generator static mapping must expose its canonical device frequency."""
    grid: SimpleNamespace = _make_grid(fbase=60.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    generator: Generator = Generator(name="gen", freq=55.0)
    generator.bus = bus

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.omega_base: _make_var("omega_base"),
            ParamPowerFlowReferenceType.freq: _make_var("freq"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=generator, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.freq), 55.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.omega_base), 2.0 * np.pi * 60.0)


def test_dc_load_mapping_preserves_explicit_power_and_conductance_terms() -> None:
    """DC-load mapping must preserve the declared ``P`` and ``G`` ZIP terms."""
    grid: SimpleNamespace = _make_grid(sbase=100.0, fbase=50.0)
    bus: Bus = Bus(name="dc_bus", Vnom=20.0, is_dc=True)
    load: Load = Load(name="dc_load", P=30.0, G=12.0, Q=0.0)
    load.bus = bus

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.Pl0: _make_var("pl0"),
            ParamPowerFlowReferenceType.g: _make_var("g"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=load, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Pl0), 0.3)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.g), 0.12)


def test_vsc_static_mapping_skips_runtime_control_values() -> None:
    """VSC controls must stay outside the shared static parameter mapping."""
    grid: SimpleNamespace = _make_grid(sbase=150.0, fbase=50.0)
    bus_dc: Bus = Bus(name="dc", Vnom=2.0, is_dc=True)
    bus_ac: Bus = Bus(name="ac", Vnom=20.0, is_dc=False)
    vsc: VSC = VSC(
        name="vsc",
        bus_from=bus_dc,
        bus_to=bus_ac,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Pac,
        control1_val=1.05,
        control2_val=20.0,
    )

    runtime_keys: set[ParamPowerFlowReferenceType] = set((
        ParamPowerFlowReferenceType.converter_control_mode_1,
        ParamPowerFlowReferenceType.converter_control_mode_2,
        ParamPowerFlowReferenceType.converter_control_target_1,
        ParamPowerFlowReferenceType.converter_control_target_2,
    ))
    block: Block = _make_block(
        mapping=dict({
            ParamPowerFlowReferenceType.Sbase: _make_var("sbase"),
            ParamPowerFlowReferenceType.omega_base: _make_var("omega"),
            ParamPowerFlowReferenceType.converter_control_mode_1: _make_var("c1"),
            ParamPowerFlowReferenceType.converter_control_mode_2: _make_var("c2"),
            ParamPowerFlowReferenceType.converter_control_target_1: _make_var("t1"),
            ParamPowerFlowReferenceType.converter_control_target_2: _make_var("t2"),
        }),
        event_keys=runtime_keys,
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=vsc, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Sbase), 150.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.omega_base), 2.0 * np.pi * 50.0)
    runtime_key: ParamPowerFlowReferenceType
    for runtime_key in (
            ParamPowerFlowReferenceType.converter_control_mode_1,
            ParamPowerFlowReferenceType.converter_control_mode_2,
            ParamPowerFlowReferenceType.converter_control_target_1,
            ParamPowerFlowReferenceType.converter_control_target_2,
    ):
        runtime_target: Var | None = block.api_obj_mapping.get(runtime_key, None)
        assert runtime_target is not None
        assert runtime_target not in problem_mapping
        assert runtime_target in block.event_dict
        assert block.event_dict[runtime_target].value is None


def test_existing_dc_line_mapping_values_remain_unchanged() -> None:
    """Historical DC-line EMT keys must keep their existing values."""
    grid: SimpleNamespace = _make_grid()
    bus_from: Bus = Bus(name="dcf", Vnom=2.0, is_dc=True)
    bus_to: Bus = Bus(name="dct", Vnom=2.0, is_dc=True)
    dc_line: DcLine = DcLine(name="dc", bus_from=bus_from, bus_to=bus_to, r=0.5)

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.g: _make_var("g"),
            ParamPowerFlowReferenceType.b: _make_var("b"),
            ParamPowerFlowReferenceType.bsh: _make_var("bsh"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=dc_line, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.g), 2.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.b), 0.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.bsh), 0.0)


def test_transformer_direct_static_keys_receive_only_direct_values() -> None:
    """A direct-only transformer model must receive only direct static values."""
    grid: SimpleNamespace = _make_grid(fbase=50.0)
    bus_hv: Bus = Bus(name="hv", Vnom=110.0)
    bus_lv: Bus = Bus(name="lv", Vnom=20.0)
    transformer: Transformer2W = Transformer2W(
        name="xfmr",
        bus_from=bus_hv,
        bus_to=bus_lv,
        nominal_power=40.0,
        copper_losses=120.0,
        iron_losses=30.0,
        no_load_current=1.2,
        short_circuit_voltage=8.0,
        tap_module=1.05,
    )
    transformer.conn_f = WindingType.GroundedStar
    transformer.conn_t = WindingType.GroundedStar
    transformer.vector_group_number = 0

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.omega_base: _make_var("omega"),
            ParamPowerFlowReferenceType.transformer_rated_power_mva: _make_var("sn"),
            ParamPowerFlowReferenceType.transformer_open_circuit_current_pct: _make_var("i0"),
            ParamPowerFlowReferenceType.transformer_open_circuit_loss_kw: _make_var("pfe"),
            ParamPowerFlowReferenceType.transformer_short_circuit_voltage_pct: _make_var("vsc"),
            ParamPowerFlowReferenceType.transformer_short_circuit_loss_kw: _make_var("pcu"),
            ParamPowerFlowReferenceType.tap_module: _make_var("tap_module"),
            ParamPowerFlowReferenceType.transformer_nominal_voltage_ratio: _make_var("nominal_ratio"),
            ParamPowerFlowReferenceType.transformer_total_voltage_ratio: _make_var("total_ratio"),
            ParamPowerFlowReferenceType.transformer_from_connection_aa: _make_var("faa"),
            ParamPowerFlowReferenceType.transformer_to_connection_cc: _make_var("tcc"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=transformer, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.omega_base), 2.0 * np.pi * 50.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_rated_power_mva), 40.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_open_circuit_current_pct), 1.2)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_open_circuit_loss_kw), 30.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_short_circuit_voltage_pct), 8.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_short_circuit_loss_kw), 120.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.tap_module), 1.05)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_nominal_voltage_ratio), 110.0 / 20.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_total_voltage_ratio), (110.0 / 20.0) * 1.05)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_from_connection_aa), 1.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_to_connection_cc), 1.0)
    assert len(problem_mapping) == 11


def test_transformer_equivalent_circuit_keys_receive_only_derived_values() -> None:
    """A derived-only transformer model must receive only derived equivalent-circuit values."""
    grid: SimpleNamespace = _make_grid(fbase=50.0)
    bus_hv: Bus = Bus(name="hv", Vnom=110.0)
    bus_lv: Bus = Bus(name="lv", Vnom=20.0)
    transformer: Transformer2W = Transformer2W(
        name="xfmr_classical",
        bus_from=bus_hv,
        bus_to=bus_lv,
        HV=110.0,
        LV=20.0,
        r=0.02,
        x=0.08,
        g=0.001,
        b=0.0,
        tap_module=1.1,
        tap_phase=0.0,
    )

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.transformer_winding1_resistance_pu: _make_var("r1"),
            ParamPowerFlowReferenceType.transformer_winding2_resistance_pu: _make_var("r2"),
            ParamPowerFlowReferenceType.transformer_winding1_inductance_pu_s: _make_var("l1"),
            ParamPowerFlowReferenceType.transformer_winding2_inductance_pu_s: _make_var("l2"),
            ParamPowerFlowReferenceType.transformer_mutual_inductance_pu_s: _make_var("m"),
            ParamPowerFlowReferenceType.transformer_magnetizing_conductance_pu: _make_var("g"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=transformer, mdl=block, problem_mapping=problem_mapping, logger=None)

    omega: float = 2.0 * np.pi * 50.0
    total_ratio: float = (110.0 / 20.0) * 1.1
    total_ratio_square: float = total_ratio * total_ratio
    # A zero static susceptance represents an absent magnetizing branch. The
    # finite 1e7-pu fallback keeps the coupled-inductance matrix invertible while
    # making the artificial magnetizing current electrically negligible.
    x_magnetizing: float = 1.0e7
    magnetizing_l_primary: float = x_magnetizing / omega
    magnetizing_l_secondary: float = magnetizing_l_primary / total_ratio_square
    mutual_inductance: float = magnetizing_l_primary / total_ratio
    leakage_l_primary: float = 0.5 * 0.08 / omega
    leakage_l_secondary: float = leakage_l_primary / total_ratio_square

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_winding1_resistance_pu), 0.01)
    assert np.isclose(
        _const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_winding2_resistance_pu),
        0.01 / total_ratio_square,
    )
    assert np.isclose(
        _const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_winding1_inductance_pu_s),
        leakage_l_primary + magnetizing_l_primary,
    )
    assert np.isclose(
        _const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_winding2_inductance_pu_s),
        leakage_l_secondary + magnetizing_l_secondary,
    )
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_mutual_inductance_pu_s), mutual_inductance)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_magnetizing_conductance_pu), 0.001)
    assert len(problem_mapping) == 6


def test_transformer_direct_and_derived_keys_receive_both_sets() -> None:
    """A transformer model exposing direct and derived keys must receive both sets."""
    grid: SimpleNamespace = _make_grid(fbase=50.0)
    bus_hv: Bus = Bus(name="hv", Vnom=110.0)
    bus_lv: Bus = Bus(name="lv", Vnom=20.0)
    transformer: Transformer2W = Transformer2W(
        name="xfmr_both",
        bus_from=bus_hv,
        bus_to=bus_lv,
        HV=110.0,
        LV=20.0,
        nominal_power=40.0,
        copper_losses=120.0,
        iron_losses=30.0,
        no_load_current=1.2,
        short_circuit_voltage=8.0,
        r=0.02,
        x=0.08,
        g=0.001,
        b=0.0,
        tap_module=1.1,
        tap_phase=0.0,
    )

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.tap_module: _make_var("tap_module"),
            ParamPowerFlowReferenceType.transformer_total_voltage_ratio: _make_var("total_ratio"),
            ParamPowerFlowReferenceType.transformer_winding1_resistance_pu: _make_var("r1"),
            ParamPowerFlowReferenceType.transformer_mutual_inductance_pu_s: _make_var("m"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=transformer, mdl=block, problem_mapping=problem_mapping, logger=None)

    omega: float = 2.0 * np.pi * 50.0
    total_ratio: float = (110.0 / 20.0) * 1.1
    # Preserve the open-magnetizing-branch approximation used when B is zero.
    x_magnetizing: float = 1.0e7
    magnetizing_l_primary: float = x_magnetizing / omega
    mutual_inductance: float = magnetizing_l_primary / total_ratio

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.tap_module), 1.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_total_voltage_ratio), total_ratio)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_winding1_resistance_pu), 0.01)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_mutual_inductance_pu_s), mutual_inductance)
    assert len(problem_mapping) == 4


def test_transformer_missing_keys_are_skipped() -> None:
    """Transformer mapping must skip missing direct and derived keys."""
    grid: SimpleNamespace = _make_grid(fbase=50.0)
    bus_hv: Bus = Bus(name="hv", Vnom=110.0)
    bus_lv: Bus = Bus(name="lv", Vnom=20.0)
    transformer: Transformer2W = Transformer2W(
        name="xfmr_skip",
        bus_from=bus_hv,
        bus_to=bus_lv,
        r=0.0,
        x=0.0,
    )

    block: Block = _make_block(dict())

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=transformer, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert len(block.parameters) == 0


def test_transformer_ratio_key_semantics_are_not_ambiguous() -> None:
    """Transformer ratio keys must keep one stable meaning each."""
    grid: SimpleNamespace = _make_grid(fbase=50.0)
    bus_hv: Bus = Bus(name="hv", Vnom=110.0)
    bus_lv: Bus = Bus(name="lv", Vnom=20.0)
    transformer: Transformer2W = Transformer2W(name="xfmr_ratio", bus_from=bus_hv, bus_to=bus_lv, HV=110.0, LV=20.0, tap_module=1.1)

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.transformer_tap_ratio: _make_var("tap_ratio_legacy"),
            ParamPowerFlowReferenceType.tap_module: _make_var("tap_module"),
            ParamPowerFlowReferenceType.transformer_nominal_voltage_ratio: _make_var("nominal_ratio"),
            ParamPowerFlowReferenceType.transformer_total_voltage_ratio: _make_var("total_ratio"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=transformer, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_tap_ratio), 1.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.tap_module), 1.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_nominal_voltage_ratio), 5.5)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.transformer_total_voltage_ratio), 6.05)


def test_existing_line_mapping_values_remain_unchanged() -> None:
    """Uncoupled line EMT matrix values must use direct line reactance and shunt."""
    grid: SimpleNamespace = _make_grid(fbase=50.0)
    bus_from: Bus = Bus(name="from", Vnom=20.0)
    bus_to: Bus = Bus(name="to", Vnom=20.0)
    line: Line = Line(name="line", bus_from=bus_from, bus_to=bus_to, r=0.1, x=0.2, b=0.3)
    line.ys.phA = True
    line.ys.phB = True
    line.ys.phC = True

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.Rnn: _make_var("rnn"),
            ParamPowerFlowReferenceType.Raa: _make_var("raa"),
            ParamPowerFlowReferenceType.Rbb: _make_var("rbb"),
            ParamPowerFlowReferenceType.Rcc: _make_var("rcc"),
            ParamPowerFlowReferenceType.Linv_aa: _make_var("laa"),
            ParamPowerFlowReferenceType.Caa: _make_var("caa"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=line, mdl=block, problem_mapping=problem_mapping, logger=None)

    omega: float = 2.0 * np.pi * 50.0
    expected_linv: float = omega / 0.2
    expected_c: float = 0.3 / (2.0 * omega)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Rnn), 0.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Raa), 0.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Rbb), 0.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Rcc), 0.1)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Linv_aa), expected_linv)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Caa), expected_c)


def test_uncoupled_line_mapping_uses_direct_reactance_when_historical_slot_is_zero() -> None:
    """Pure-reactive uncoupled lines must keep a non-zero EMT series inductance."""
    grid: SimpleNamespace = _make_grid(fbase=50.0)
    bus_from: Bus = Bus(name="from", Vnom=20.0)
    bus_to: Bus = Bus(name="to", Vnom=20.0)
    line: Line = Line(name="line_rx_only", bus_from=bus_from, bus_to=bus_to, r=0.0, x=0.2, b=0.0)
    line.ys.phA = True
    line.ys.phB = True
    line.ys.phC = True

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.Linv_aa: _make_var("laa"),
            ParamPowerFlowReferenceType.Caa: _make_var("caa"),
        })
    )

    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=line, mdl=block, problem_mapping=problem_mapping, logger=None)

    omega: float = 2.0 * np.pi * 50.0

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Linv_aa), omega / 0.2)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Caa), 0.0)


def test_overhead_line_mapping_matches_original_template_based_values() -> None:
    """Overhead pi-line mapping must match the original template-based matrices."""
    grid: SimpleNamespace = _make_grid(sbase=2.0, fbase=50.0)
    bus_from: Bus = Bus(name="from", Vnom=10.0)
    bus_to: Bus = Bus(name="to", Vnom=10.0)
    line: Line = Line(name="line", bus_from=bus_from, bus_to=bus_to, length=10.0)

    tower: OverheadLineType = OverheadLineType(name="Tower", Vnom=10.0)
    wire: Wire = Wire(
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
    line.apply_template(tower, grid.Sbase, grid.fBase)

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.Linv_aa: _make_var("laa"),
            ParamPowerFlowReferenceType.Caa: _make_var("caa"),
        })
    )
    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=line, mdl=block, problem_mapping=problem_mapping, logger=None)

    omega: float = 2.0 * np.pi * float(grid.fBase)
    voltage_base: float = float(bus_from.Vnom) * 1.0e3
    sbase_va: float = float(grid.Sbase) * 1.0e6
    zbase: float = (voltage_base * voltage_base) / sbase_va
    ybase: float = 1.0 / zbase
    z_phys_total: np.ndarray = tower.z_nabc * float(line.length)
    y_phys_total: np.ndarray = tower.y_nabc * float(line.length)
    z_pu: np.ndarray = z_phys_total / zbase
    y_pu: np.ndarray = y_phys_total / ybase
    l_expected: np.ndarray = np.imag(z_pu) / omega
    c_expected: np.ndarray = (np.imag(y_pu) / omega) / 2.0
    linv_expected: np.ndarray = np.linalg.inv(l_expected)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Linv_aa), float(linv_expected[0, 0]))
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.Caa), float(c_expected[0, 0]))


def _assert_line_matrix_mapping_for_phase_mask(
        phase_mask: tuple[bool, bool, bool, bool],
) -> None:
    """Check the complete fixed NABC mapping for one physical phase mask.

    Distinct diagonal and mutual entries make row, column and phase permutation
    errors observable. The stored shunt matrix includes the historical ``1e6``
    factor expected by the line persistence contract.

    :param phase_mask: Active NABC conductors of the physical line.
    :return: None.
    """
    grid: SimpleNamespace = _make_grid(sbase=100.0, fbase=50.0)
    bus_from: Bus = Bus(name="from", Vnom=10.0)
    bus_to: Bus = Bus(name="to", Vnom=10.0)
    line: Line = Line(name="matrix_line", bus_from=bus_from, bus_to=bus_to)
    line.disable_auto_updates()

    resistance_pu: np.ndarray = np.array(
        [
            [0.40, 0.01, 0.02, 0.03],
            [0.01, 0.50, 0.04, 0.05],
            [0.02, 0.04, 0.60, 0.06],
            [0.03, 0.05, 0.06, 0.70],
        ],
        dtype=np.float64,
    )
    reactance_pu: np.ndarray = np.array(
        [
            [0.80, 0.07, 0.08, 0.09],
            [0.07, 0.90, 0.10, 0.11],
            [0.08, 0.10, 1.00, 0.12],
            [0.09, 0.11, 0.12, 1.10],
        ],
        dtype=np.float64,
    )
    susceptance_pu: np.ndarray = np.array(
        [
            [0.40, -0.01, -0.02, -0.03],
            [-0.01, 0.50, -0.04, -0.05],
            [-0.02, -0.04, 0.60, -0.06],
            [-0.03, -0.05, -0.06, 0.70],
        ],
        dtype=np.float64,
    )
    impedance_pu: np.ndarray = resistance_pu + 1.0j * reactance_pu
    stored_series_admittance_pu: np.ndarray = np.linalg.inv(impedance_pu).astype(np.complex128)
    stored_shunt_admittance_pu: np.ndarray = (
        1.0j * susceptance_pu * 1.0e6
    ).astype(np.complex128)
    line.ys.values = stored_series_admittance_pu
    line.ysh.values = stored_shunt_admittance_pu
    line.ys.phN = phase_mask[0]
    line.ys.phA = phase_mask[1]
    line.ys.phB = phase_mask[2]
    line.ys.phC = phase_mask[3]
    line.ysh.phN = phase_mask[0]
    line.ysh.phA = phase_mask[1]
    line.ysh.phB = phase_mask[2]
    line.ysh.phC = phase_mask[3]

    api_mapping: dict[ParamPowerFlowReferenceType, Var | None] = dict()
    mapping_key: ParamPowerFlowReferenceType
    for mapping_key in get_all_line_matrix_keys():
        api_mapping[mapping_key] = _make_var(f"mapped_{mapping_key.name}")

    block: Block = _make_block(api_mapping)
    problem_mapping: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(
        grid=grid,
        device=line,
        mdl=block,
        problem_mapping=problem_mapping,
        logger=None,
    )

    active_indices: np.ndarray = np.flatnonzero(np.asarray(phase_mask, dtype=bool))
    active_selector: tuple[np.ndarray, np.ndarray] = np.ix_(active_indices, active_indices)
    omega_base: float = 2.0 * np.pi * float(grid.fBase)
    resistance_active: np.ndarray = resistance_pu[active_selector]
    inductance_active: np.ndarray = reactance_pu[active_selector] / omega_base
    inverse_inductance_active: np.ndarray = np.linalg.inv(inductance_active)
    capacitance_active: np.ndarray = susceptance_pu[active_selector] / (2.0 * omega_base)
    expected_resistance: np.ndarray = np.zeros((4, 4), dtype=np.float64)
    expected_inverse_inductance: np.ndarray = np.zeros((4, 4), dtype=np.float64)
    expected_capacitance: np.ndarray = np.zeros((4, 4), dtype=np.float64)
    expected_resistance[active_selector] = resistance_active
    expected_inverse_inductance[active_selector] = inverse_inductance_active
    expected_capacitance[active_selector] = capacitance_active

    resistance_keys: list[list[ParamPowerFlowReferenceType]] = get_line_r_keys()
    inverse_inductance_keys: list[list[ParamPowerFlowReferenceType]] = get_line_linv_keys()
    capacitance_keys: list[list[ParamPowerFlowReferenceType]] = get_line_c_keys()
    row_index: int = 0
    while row_index < 4:
        column_index: int = 0
        while column_index < 4:
            assert np.isclose(
                _const_value(problem_mapping, block, resistance_keys[row_index][column_index]),
                expected_resistance[row_index, column_index],
            )
            assert np.isclose(
                _const_value(problem_mapping, block, inverse_inductance_keys[row_index][column_index]),
                expected_inverse_inductance[row_index, column_index],
            )
            assert np.isclose(
                _const_value(problem_mapping, block, capacitance_keys[row_index][column_index]),
                expected_capacitance[row_index, column_index],
            )
            column_index += 1
        row_index += 1


def test_line_matrix_mapping_covers_every_nabc_term() -> None:
    """Map all R, inverse-L and C diagonal and mutual NABC entries.

    :return: None.
    """
    _assert_line_matrix_mapping_for_phase_mask((True, True, True, True))


def test_line_matrix_mapping_projects_noncontiguous_active_phases() -> None:
    """Project N, A and C terms while keeping every inactive-B slot zero.

    :return: None.
    """
    _assert_line_matrix_mapping_for_phase_mask((True, True, False, True))


def test_shunt_phase_keys_fall_back_to_balanced_totals() -> None:
    """Balanced shunt totals must feed per-phase shunt keys when phases are empty."""
    grid: SimpleNamespace = _make_grid(sbase=120.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    shunt: Shunt = Shunt(name="shunt", G=12.0, B=6.0)
    shunt.bus = bus

    ga =  _make_var("ga")
    bb =  _make_var("bb")

    problem_mapping = {ga: Const(0),
                       bb: Const(0)}

    api_onject_mapping = {
        ParamPowerFlowReferenceType.shunt_ga_pu: ga,
        ParamPowerFlowReferenceType.shunt_bb_pu: bb,
    }

    block: Block = _make_block(api_onject_mapping)

    assign_static_api_object_mapping_for_device(grid=grid, device=shunt, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.shunt_ga_pu), 1.0 / 30.0)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.shunt_bb_pu), 1.0 / 60.0)


def test_current_injection_phase_keys_fall_back_to_balanced_totals() -> None:
    """Balanced current-injection totals must feed per-phase keys when phases are empty."""
    grid: SimpleNamespace = _make_grid(sbase=150.0)
    bus: Bus = Bus(name="bus", Vnom=20.0)
    current_injection: CurrentInjection = CurrentInjection(name="inj", Ir=9.0, Ii=6.0)
    current_injection.bus = bus

    block: Block = _make_block(
        dict({
            ParamPowerFlowReferenceType.current_injection_ira_pu: _make_var("ira"),
            ParamPowerFlowReferenceType.current_injection_iic_pu: _make_var("iic"),
        })
    )
    problem_mapping = dict()
    assign_static_api_object_mapping_for_device(grid=grid, device=current_injection, mdl=block, problem_mapping=problem_mapping, logger=None)

    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.current_injection_ira_pu), 0.02)
    assert np.isclose(_const_value(problem_mapping, block, ParamPowerFlowReferenceType.current_injection_iic_pu), 1.0 / 75.0)


def test_line_physical_shunt_conductance_mapping() -> None:
    """Keep total line shunt conductance distinct from series admittance.

    :return: None.
    """
    power_base: float
    for power_base in (2.0, 100.0):
        grid: SimpleNamespace = _make_grid(sbase=power_base)
        source: Bus = Bus(name="source", Vnom=20.0)
        target: Bus = Bus(name="target", Vnom=20.0)
        line: Line = Line(bus_from=source, bus_to=target, r=0.01, x=0.1, g=0.003)
        block: Block = _make_block(dict((
            (ParamPowerFlowReferenceType.g, _make_var("series_g")),
            (ParamPowerFlowReferenceType.shunt_g_pu, _make_var("physical_g")),
        )))
        mapped_values: dict[Var, Const] = dict()

        # Line.G already uses the system per-unit base; injection conversion is inappropriate.
        assign_static_api_object_mapping_for_device(
            grid=grid, device=line, mdl=block, problem_mapping=mapped_values, logger=None,
        )
        assert np.isclose(
            _const_value(mapped_values, block, ParamPowerFlowReferenceType.shunt_g_pu),
            0.003, rtol=1.0e-10, atol=1.0e-12,
        )
        assert np.isclose(
            _const_value(mapped_values, block, ParamPowerFlowReferenceType.g),
            np.real(1.0 / complex(0.01, 0.1)), rtol=1.0e-10, atol=1.0e-12,
        )


def test_line_shunt_conductance_matrix_projection() -> None:
    """Compare full and partial G mappings with independent static primitives.

    :return: None.
    """
    g_keys: list[list[ParamPowerFlowReferenceType]] = get_line_g_keys()
    assert g_keys[0][1] == ParamPowerFlowReferenceType.Gna
    assert g_keys[1][0] == ParamPowerFlowReferenceType.Gan
    assert g_keys[3][3] == ParamPowerFlowReferenceType.Gcc
    physical_g: np.ndarray = 1.0e-6 * np.array((
        (0.4, -0.03, -0.02, -0.01),
        (-0.03, 0.7, -0.04, -0.02),
        (-0.02, -0.04, 0.8, -0.03),
        (-0.01, -0.02, -0.03, 0.9),
    ))
    frequency: float
    power_base: float
    voltage_base: float
    resistive: bool
    for frequency, power_base, voltage_base, resistive in (
        (50.0, 2.0, 10.0, False), (60.0, 100.0, 132.0, False), (60.0, 100.0, 20.0, True),
    ):
        phase_mask: tuple[bool, bool, bool, bool]
        for phase_mask in ((True, True, True, True), (False, True, True, True), (False, True, False, True)):
            grid: MultiCircuit = MultiCircuit(Sbase=power_base, fbase=frequency)
            source: Bus = grid.add_bus(Bus(Vnom=voltage_base))
            target: Bus = grid.add_bus(Bus(Vnom=voltage_base))
            line: Line = Line(bus_from=source, bus_to=target, r=0.08, x=0.0 if resistive else 0.4)
            grid.add_line(line)
            # Preserve explicitly supplied phase data rather than regenerating sequence defaults.
            line.fill_3_phase_from_sequence()
            line.disable_auto_updates()
            line.ys.phN, line.ys.phA, line.ys.phB, line.ys.phC = phase_mask
            line.ysh.phN, line.ysh.phA, line.ysh.phB, line.ysh.phC = phase_mask
            active: np.ndarray = np.flatnonzero(np.array(phase_mask, dtype=bool))
            selector: tuple[np.ndarray, np.ndarray] = np.ix_(active, active)
            impedance: complex = complex(0.08, 0.0 if resistive else 0.4)
            line.ys.values[:] = 0.0
            line.ys.values[selector] = np.eye(len(active), dtype=complex) / impedance
            line.ysh.values[:] = 0.0
            zbase: float = voltage_base * voltage_base / power_base
            line.ysh.values[selector] = physical_g[selector] * zbase * 1.0e6
            numerical: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)
            expected: np.ndarray = np.real(
                numerical.passive_branch_data.Yff3 + numerical.passive_branch_data.Yft3,
            )
            np.testing.assert_allclose(expected[selector], physical_g[selector] * zbase / 2.0, rtol=1.0e-10, atol=1.0e-12)
            partial: bool
            for partial in (False, True):
                mapping: dict[ParamPowerFlowReferenceType, Var] = dict()
                row: int
                col: int
                for row in range(4):
                    for col in range(4):
                        if not partial or (row, col) in ((0, 0), (1, 1), (1, 3)):
                            mapping[g_keys[row][col]] = _make_var(g_keys[row][col].name)
                        else:
                            pass
                block: Block = _make_block(mapping)
                resolved: dict[Var, Const] = dict()
                # No Linv key is requested: even singular L must not suppress valid G.
                assign_static_api_object_mapping_for_device(
                    grid=grid, device=line, mdl=block, problem_mapping=resolved, logger=None,
                )
                for row in range(4):
                    for col in range(4):
                        if g_keys[row][col] in mapping:
                            np.testing.assert_allclose(
                                _const_value(resolved, block, g_keys[row][col]),
                                expected[row, col], rtol=1.0e-10, atol=1.0e-12,
                            )
                        else:
                            pass
