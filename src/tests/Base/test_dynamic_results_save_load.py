from __future__ import annotations

from pathlib import Path

import numpy as np

import VeraGridEngine.api as vg
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.IO.veragrid.zip_interface import get_session_tree
from VeraGridEngine.IO.veragrid.zip_interface import load_session_driver_objects
from VeraGrid.Session.session import SimulationSession
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import (
    get_generator_thevenin_rl_emt_template_with_ref,
)
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.enumerations import EmtSolverTypes
from VeraGridEngine.enumerations import RmsInitializationMethod
from VeraGridEngine.enumerations import RmsProblemTypes
from VeraGridEngine.enumerations import SimulationTypes
from VeraGridEngine.enumerations import ShuntConnectionType
from VeraGridEngine.enumerations import SparseSolver


def _find_name_in_block(name: str, block: Block) -> Var | None:
    """
    Find one symbolic variable by name inside a block tree.

    :param name: Target variable name.
    :param block: Root symbolic block.
    :return: Matching variable, or ``None``.
    """
    variable: Var

    for variable in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == variable.name:
            return variable
        else:
            pass

    child_block: Block

    for child_block in block.children:
        child_variable: Var | None = _find_name_in_block(name=name, block=child_block)
        if child_variable is not None:
            return child_variable
        else:
            pass

    return None


def _build_snapshot_pf_options() -> vg.PowerFlowOptions:
    """
    Build the snapshot power-flow options used before the RMS simulation.

    :return: Power-flow options.
    """
    return vg.PowerFlowOptions(
        solver_type=vg.SolverType.NR,
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
        branch_impedance_tolerance_mode=vg.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )


def _build_3ph_pf_options() -> vg.PowerFlowOptions:
    """
    Build the three-phase power-flow options used before the EMT simulation.

    :return: Power-flow options.
    """
    return vg.PowerFlowOptions(
        solver_type=vg.SolverType.NR,
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
        branch_impedance_tolerance_mode=vg.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )


def _build_rms_driver(sparse_solver: SparseSolver = SparseSolver.SuperLU,
                      integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeBackEuler,
                      problem_type: RmsProblemTypes = RmsProblemTypes.PowerBalance) -> RmsSimulationDriver:
    """
    Build and run one RMS driver for save/load roundtrip testing.

    The defaults reproduce the original roundtrip driver exactly.

    :param sparse_solver: Sparse LU selected through the RMS options.
    :param integration_method: Integration method selected through the RMS options.
    :param problem_type: RMS problem formulation selected through the RMS options.
    :return: Finished RMS simulation driver.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit(Sbase=100.0, fbase=50.0)

    # Build the minimal two-bus RMS test system used by the dynamics stack.
    bus0: vg.Bus = vg.Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus1: vg.Bus = vg.Bus(name="Bus1", Vnom=10.0)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    bus: vg.Bus
    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.var_factory)

    line0: vg.Line = vg.Line(
        name="line 0-1",
        bus_from=bus0,
        bus_to=bus1,
        r=0.029585798816568046,
        x=0.07100591715976332,
        b=0.03,
        rate=900.0,
    )
    grid.add_line(line0)

    load: vg.Load = vg.Load(P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)

    gen0: vg.Generator = vg.Generator(
        name="Gen0",
        P=10.0,
        vset=1.0,
        Snom=900.0,
        x1=0.86138701,
        r1=0.3,
        freq=50.0,
    )
    grid.add_generator(bus=bus0, api_obj=gen0)

    # Attach the real RMS symbolic models used by the simulation driver.
    gen_model: Block = get_complete_generator_template_rms(grid.var_factory).block
    line_model: Block = get_line_rms_template(grid.var_factory).block
    load_model: Block = get_load_rms_template(grid.var_factory).block

    load_model.set_parameter_in_model(var_name="Pl0", new_value=-0.0999999)
    load_model.set_parameter_in_model(var_name="Ql0", new_value=-0.009999999862208533)

    set_rms_model(device=gen0, model=gen_model, var_factory=grid.var_factory)
    set_rms_model(device=line0, model=line_model, var_factory=grid.var_factory)
    set_rms_model(device=load, model=load_model, var_factory=grid.var_factory)

    # Create one active event group so the saved results include event-group traces.
    pl0_var: Var | None = _find_name_in_block(name="Pl0", block=load_model)
    if pl0_var is None:
        raise AssertionError("Expected RMS event parameter 'Pl0' was not found.")
    else:
        pass

    events_group: RmsEventsGroup = RmsEventsGroup(name="simulation1")
    grid.add_rms_events_group(events_group)
    grid.add_rms_event(RmsEvent(device=load, parameter=pl0_var, time=0.1, value=-0.098, group=events_group))

    pf_results = vg.power_flow(grid=grid, options=_build_snapshot_pf_options())

    driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=RmsOptions(
            time_step=1.0e-3,
            simulation_time=0.2,
            tolerance=1.0e-6,
            integration_method=integration_method,
            initialization_method=RmsInitializationMethod.Explicit,
            problem_type=problem_type,
            use_init_values=False,
            max_iter=1000,
            verbose=0,
            sparse_solver=sparse_solver,
        ),
        pf_results=pf_results,
    )
    driver.run()

    if driver.results is None:
        raise AssertionError("The RMS driver did not produce results.")
    else:
        pass

    return driver


def _build_emt_driver() -> EmtSimulationDriver:
    """
    Build and run one EMT driver for save/load roundtrip testing.

    :return: Finished EMT simulation driver.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit(Sbase=2.0, fbase=50.0)
    vnom: float = 10.0

    # Build the minimal EMT network used by the existing event simulation tests.
    bus0: vg.Bus = vg.Bus(name="Bus0", Vnom=vnom, is_slack=True)
    bus1: vg.Bus = vg.Bus(name="Bus1", Vnom=vnom)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line0: vg.Line = vg.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10.0, rate=900.0)

    tower: vg.OverheadLineType = vg.OverheadLineType(name="Tower", Vnom=vnom)
    wire: vg.Wire = vg.Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1.0,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line0.apply_template(tower, grid.Sbase, grid.fBase)
    grid.add_line(line0)

    r_ph: float = 100.0
    v_ph: float = vnom / (3.0 ** 0.5)
    p_ph: float = (v_ph ** 2) / r_ph
    load: vg.Load = vg.Load(name="load", P1=p_ph, P2=p_ph, P3=p_ph, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus1, api_obj=load)

    gen0: vg.Generator = vg.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)
    grid.add_generator(bus=bus0, api_obj=gen0)

    bus_elm: vg.Bus
    for bus_elm in grid.buses:
        get_bus_emt_template(grid, bus_elm)

    gen_model: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    line_model: Block = get_pi_line_emt_template(
        vf=grid.var_factory,
        phN=False,
        phA=True,
        phB=True,
        phC=True,
    ).block
    load_model: Block = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

    set_emt_model(device=gen0, model=gen_model, var_factory=grid.var_factory)
    set_emt_model(device=line0, model=line_model, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_model, var_factory=grid.var_factory)

    # Create one active EMT event group with two resistance steps.
    r_a_var: Var | None = _find_name_in_block(name="R_A_Shunt_R_3ph", block=load_model)
    r_b_var: Var | None = _find_name_in_block(name="R_B_Shunt_R_3ph", block=load_model)
    r_c_var: Var | None = _find_name_in_block(name="R_C_Shunt_R_3ph", block=load_model)
    if r_a_var is None or r_b_var is None or r_c_var is None:
        raise AssertionError("Expected EMT event parameters were not found.")
    else:
        pass

    events_group: EmtEventsGroup = EmtEventsGroup(name="simulation1")
    grid.add_emt_events_group(events_group)
    grid.add_emt_event(EmtEvent(device=load, parameter=r_a_var, time=0.002, value=3.0, group=events_group))
    grid.add_emt_event(EmtEvent(device=load, parameter=r_b_var, time=0.002, value=3.0, group=events_group))
    grid.add_emt_event(EmtEvent(device=load, parameter=r_c_var, time=0.002, value=3.0, group=events_group))
    grid.add_emt_event(EmtEvent(device=load, parameter=r_a_var, time=0.004, value=6.0, group=events_group))
    grid.add_emt_event(EmtEvent(device=load, parameter=r_b_var, time=0.004, value=6.0, group=events_group))
    grid.add_emt_event(EmtEvent(device=load, parameter=r_c_var, time=0.004, value=6.0, group=events_group))

    power_flow_3ph: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, _build_3ph_pf_options())
    power_flow_3ph.run()

    driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=EmtOptions(
            time_step=5.0e-6,
            simulation_time=0.006,
            tolerance=1.0e-6,
            solver_type=EmtSolverTypes.Symbolic,
            integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
            verbose=0,
        ),
        pf_results_3ph=power_flow_3ph.results,
        pf_results=None,
    )
    driver.run()

    if driver.results is None:
        raise AssertionError("The EMT driver did not produce results.")
    else:
        pass

    return driver


def _clone_rms_results_shell(results: RmsResults) -> RmsResults:
    """
    Build one empty RMS results shell with the same metadata layout.

    :param results: Original RMS results.
    :return: New RMS results shell.
    """
    return RmsResults(
        time_array=results.time_array,
        rms_events_group_names=np.array(results.rms_events_group_names, dtype=str),
        rms_events_group_idtags=np.array(results.rms_events_group_idtags, dtype=str),
        variables=list(results.variables),
        uid2idx=dict(results.uid2idx),
        vars_glob_name2uid=dict(results.vars_glob_name2uid),
        devices_vars_info=dict(results.devices_vars_info),
        parameter_value_maps=[dict() for _ in range(results.ng)],
        has_event_group_results=np.array(results.has_event_group_results, dtype=bool),
    )


def _clone_emt_results_shell(results: EmtResults) -> EmtResults:
    """
    Build one empty EMT results shell with the same metadata layout.

    :param results: Original EMT results.
    :return: New EMT results shell.
    """
    return EmtResults(
        time_array=results.time_array,
        emt_events_group_names=np.array(results.emt_events_group_names, dtype=str),
        emt_events_group_idtags=np.array(results.emt_events_group_idtags, dtype=str),
        variables=list(results.variables),
        diff_variables=list(results.diff_variables),
        uid2idx_vars=dict(results.uid2idx_vars),
        uid2idx_diff=dict(results.uid2idx_diff),
        vars_glob_name2uid=dict(results.vars_glob_name2uid),
        devices_vars_info=dict(results.devices_vars_info),
        parameter_value_maps=[dict() for _ in range(results.ng)],
        has_event_group_results=np.array(results.has_event_group_results, dtype=bool),
    )


def test_rms_results_roundtrip_through_disk(tmp_path: Path) -> None:
    """
    Run one RMS simulation, save it, reload it, and compare the results tensors.

    :param tmp_path: Temporary pytest path.
    :return: None.
    """
    driver: RmsSimulationDriver = _build_rms_driver()
    file_name: Path = tmp_path / "rms_roundtrip.veragrid"

    vg.save_file(grid=driver.grid, filename=str(file_name), drivers_to_save=[driver.get_save_data()])

    session_tree: dict[str, dict[str, list[str]]] = get_session_tree(file_name_zip=str(file_name))
    assert driver.name in session_tree
    assert driver.tpe.value in session_tree[driver.name]

    stored_data = load_session_driver_objects(
        file_name_zip=str(file_name),
        session_name=driver.name,
        study_name=driver.tpe.value,
    )
    assert "values" in stored_data
    assert isinstance(stored_data["values"], np.ndarray)

    restored_results: RmsResults = _clone_rms_results_shell(driver.results)
    restored_results.parse_saved_data(grid=driver.grid, data_dict=stored_data)
    restored_results.restore_dynamic_metadata(grid=driver.grid)
    restored_results.consolidate_after_loading()

    np.testing.assert_array_equal(restored_results.time_array.asi8, driver.results.time_array.asi8)
    np.testing.assert_array_equal(restored_results.rms_events_group_names, driver.results.rms_events_group_names)
    np.testing.assert_array_equal(restored_results.rms_events_group_idtags, driver.results.rms_events_group_idtags)
    np.testing.assert_array_equal(restored_results.has_event_group_results, driver.results.has_event_group_results)
    np.testing.assert_array_equal(restored_results.well_initialized, driver.results.well_initialized)
    np.testing.assert_array_equal(restored_results.converged, driver.results.converged)
    np.testing.assert_allclose(restored_results.values, driver.results.values)
    assert len(restored_results.variables) == len(driver.results.variables)
    assert restored_results.vars_glob_name2uid == driver.results.vars_glob_name2uid
    assert len(restored_results.devices_vars_info) == len(driver.results.devices_vars_info)
    assert restored_results.parameter_value_maps == driver.results.parameter_value_maps


def test_emt_results_roundtrip_through_disk(tmp_path: Path) -> None:
    """
    Run one EMT simulation, save it, reload it, and compare the results tensors.

    :param tmp_path: Temporary pytest path.
    :return: None.
    """
    driver: EmtSimulationDriver = _build_emt_driver()
    file_name: Path = tmp_path / "emt_roundtrip.veragrid"

    vg.save_file(grid=driver.grid, filename=str(file_name), drivers_to_save=[driver.get_save_data()])

    session_tree: dict[str, dict[str, list[str]]] = get_session_tree(file_name_zip=str(file_name))
    assert driver.name in session_tree
    assert driver.tpe.value in session_tree[driver.name]

    stored_data = load_session_driver_objects(
        file_name_zip=str(file_name),
        session_name=driver.name,
        study_name=driver.tpe.value,
    )
    assert "values" in stored_data
    assert "diff_values" in stored_data
    assert isinstance(stored_data["values"], np.ndarray)
    assert isinstance(stored_data["diff_values"], np.ndarray)

    restored_results: EmtResults = _clone_emt_results_shell(driver.results)
    restored_results.parse_saved_data(grid=driver.grid, data_dict=stored_data)
    restored_results.restore_dynamic_metadata(grid=driver.grid)
    restored_results.consolidate_after_loading()

    np.testing.assert_array_equal(restored_results.time_array.asi8, driver.results.time_array.asi8)
    np.testing.assert_array_equal(restored_results.emt_events_group_names, driver.results.emt_events_group_names)
    np.testing.assert_array_equal(restored_results.emt_events_group_idtags, driver.results.emt_events_group_idtags)
    np.testing.assert_array_equal(restored_results.has_event_group_results, driver.results.has_event_group_results)
    np.testing.assert_array_equal(restored_results.well_initialized, driver.results.well_initialized)
    np.testing.assert_array_equal(restored_results.converged, driver.results.converged)
    np.testing.assert_allclose(restored_results.values, driver.results.values)
    np.testing.assert_allclose(restored_results.diff_values, driver.results.diff_values)
    assert len(restored_results.variables) == len(driver.results.variables)
    assert len(restored_results.diff_variables) == len(driver.results.diff_variables)
    assert restored_results.vars_glob_name2uid == driver.results.vars_glob_name2uid
    assert len(restored_results.devices_vars_info) == len(driver.results.devices_vars_info)
    assert restored_results.parameter_value_maps == driver.results.parameter_value_maps


def test_rms_results_register_driver_from_disk_data(tmp_path: Path) -> None:
    """
    Saved RMS results must be recoverable through the session disk-registration path.

    :param tmp_path: Temporary pytest path.
    :return: None.
    """
    driver: RmsSimulationDriver = _build_rms_driver()
    file_name: Path = tmp_path / "rms_register_driver.veragrid"

    vg.save_file(grid=driver.grid, filename=str(file_name), drivers_to_save=[driver.get_save_data()])

    stored_data = load_session_driver_objects(
        file_name_zip=str(file_name),
        session_name=driver.name,
        study_name=driver.tpe.value,
    )

    session = SimulationSession()
    logger = session.register_driver_from_disk_data(
        grid=driver.grid,
        study_name=driver.tpe.value,
        data_dict=stored_data,
    )

    assert not logger.has_logs()
    assert session.exists(SimulationTypes.RmsDynamic_run)

    _, restored_results = session.rms_dynamic_simulation
    assert restored_results is not None
    np.testing.assert_array_equal(restored_results.time_array.asi8, driver.results.time_array.asi8)
    np.testing.assert_allclose(restored_results.values, driver.results.values)
    assert restored_results.vars_glob_name2uid == driver.results.vars_glob_name2uid
    assert len(restored_results.devices_vars_info) == len(driver.results.devices_vars_info)
    assert restored_results.parameter_value_maps == driver.results.parameter_value_maps


def test_emt_results_register_driver_from_disk_data(tmp_path: Path) -> None:
    """
    Saved EMT results must be recoverable through the session disk-registration path.

    :param tmp_path: Temporary pytest path.
    :return: None.
    """
    driver: EmtSimulationDriver = _build_emt_driver()
    file_name: Path = tmp_path / "emt_register_driver.veragrid"

    vg.save_file(grid=driver.grid, filename=str(file_name), drivers_to_save=[driver.get_save_data()])

    stored_data = load_session_driver_objects(
        file_name_zip=str(file_name),
        session_name=driver.name,
        study_name=driver.tpe.value,
        )

    session = SimulationSession()
    logger = session.register_driver_from_disk_data(
        grid=driver.grid,
        study_name=driver.tpe.value,
        data_dict=stored_data,
    )

    assert not logger.has_logs()
    assert session.exists(SimulationTypes.EmtDynamic_run)

    _, restored_results = session.emt_dynamic_simulation
    assert restored_results is not None
    np.testing.assert_array_equal(restored_results.time_array.asi8, driver.results.time_array.asi8)
    np.testing.assert_allclose(restored_results.values, driver.results.values)
    np.testing.assert_allclose(restored_results.diff_values, driver.results.diff_values)
    assert restored_results.vars_glob_name2uid == driver.results.vars_glob_name2uid
    assert len(restored_results.devices_vars_info) == len(driver.results.devices_vars_info)
    assert restored_results.parameter_value_maps == driver.results.parameter_value_maps
