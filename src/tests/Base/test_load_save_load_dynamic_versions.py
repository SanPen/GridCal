# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ParamPowerFlowReferenceType,
    RmsInitializationMethod,
    SolverType,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import BlockParser
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var


def _build_dynamic_version_power_flow_options() -> PowerFlowOptions:
    """Build the common operating-point options for legacy dynamic grids.

    The tolerance matches the GUI setting required by the historical Kundur
    cases. The remaining controls are fixed so all archived versions are
    exercised with the same deterministic operating-point calculation.

    :return: Power-flow options shared by the RMS and EMT compatibility cases.
    """
    options: PowerFlowOptions = PowerFlowOptions(
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
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    return options


def _build_dynamic_version_rms_options() -> RmsOptions:
    """Build a short RMS run that exercises initialization and integration.

    :return: RMS options for the legacy-file compatibility simulations.
    """
    options: RmsOptions = RmsOptions(
        time_step=0.001,
        simulation_time=0.01,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=1000,
        verbose=0,
    )
    return options


def _build_dynamic_version_emt_options() -> EmtOptions:
    """Build a short EMT run that exercises initialization and integration.

    :return: EMT options for the legacy-file compatibility simulations.
    """
    options: EmtOptions = EmtOptions(
        time_step=5e-6,
        simulation_time=2.5e-5,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Auto,
        verbose=0,
    )
    return options


def _ensure_active_rms_event_group(grid: MultiCircuit) -> None:
    """Ensure that an RMS driver run executes at least one event group.

    Historical engine-only archives can contain the complete dynamic model but
    no event group because the GUI used to create the base group at run time.
    Adding an empty active group reproduces that base-case simulation without
    changing any archived event.

    :param grid: Loaded legacy grid that will be simulated.
    :return: None.
    """
    has_active_group: bool = False
    rms_event_group: RmsEventsGroup
    for rms_event_group in grid.rms_events_groups:
        if rms_event_group.active:
            has_active_group = True
        else:
            pass
    if has_active_group:
        pass
    else:
        grid.add_rms_events_group(RmsEventsGroup(name="Legacy RMS base case"))


def _ensure_active_emt_event_group(grid: MultiCircuit) -> None:
    """Ensure that an EMT driver run executes at least one event group.

    Historical engine-only archives can omit the GUI-created base group. An
    empty active group is sufficient to exercise EMT initialization and every
    integration step while preserving all events loaded from the file.

    :param grid: Loaded legacy grid that will be simulated.
    :return: None.
    """
    has_active_group: bool = False
    emt_event_group: EmtEventsGroup
    for emt_event_group in grid.emt_events_groups:
        if emt_event_group.active:
            has_active_group = True
        else:
            pass
    if has_active_group:
        pass
    else:
        grid.add_emt_events_group(EmtEventsGroup(name="Legacy EMT base case"))


def _simulate_legacy_rms_file(file_path: str) -> None:
    """Open, simulate and release one historical RMS grid.

    :param file_path: Path to the historical ``.veragrid`` archive.
    :return: None.
    """
    # Load one archive in an isolated function scope so its complete circuit and
    # driver are released before the next archive is opened by the caller.
    grid: MultiCircuit = gce.open_file(file_path)
    _ensure_active_rms_event_group(grid=grid)

    # RMS initialization consumes a balanced operating point. Checking it here
    # distinguishes file-compatibility failures from dynamic-solver failures.
    power_flow_driver: PowerFlowDriver = PowerFlowDriver(
        grid=grid,
        options=_build_dynamic_version_power_flow_options(),
    )
    power_flow_driver.run()
    assert bool(np.all(power_flow_driver.results.converged)), (
        f"Power flow did not converge for legacy RMS file: {file_path}"
    )
    assert power_flow_driver.logger.has_errors() is False, (
        f"Power flow reported errors for legacy RMS file: {file_path}"
    )

    # Run all active groups and require an actual trajectory from each one. The
    # active mask prevents intentionally disabled archived groups from being
    # mistaken for failed simulations.
    rms_driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=_build_dynamic_version_rms_options(),
        pf_results=power_flow_driver.results,
    )
    rms_driver.run()
    assert rms_driver.results is not None, (
        f"RMS driver produced no results for legacy file: {file_path}"
    )
    rms_results: RmsResults = rms_driver.results
    group_count: int = len(grid.rms_events_groups)
    active_group_mask: np.ndarray = np.zeros(group_count, dtype=bool)
    group_index: int
    rms_event_group: RmsEventsGroup
    for group_index, rms_event_group in enumerate(grid.rms_events_groups):
        active_group_mask[group_index] = rms_event_group.active
    assert bool(np.any(active_group_mask)), (
        f"No active RMS event group was available for legacy file: {file_path}"
    )
    assert bool(np.all(rms_results.has_event_group_results[active_group_mask])), (
        f"RMS simulation produced no samples for legacy file: {file_path}"
    )
    assert bool(np.all(rms_results.well_initialized[active_group_mask])), (
        f"RMS simulation was not well initialized for legacy file: {file_path}"
    )
    assert bool(np.all(rms_results.converged[active_group_mask])), (
        f"RMS simulation did not converge for legacy file: {file_path}"
    )
    assert bool(np.all(np.isfinite(rms_results.values[-1, :, active_group_mask]))), (
        f"RMS simulation did not populate its final requested sample for legacy file: {file_path}"
    )
    assert rms_driver.logger.has_errors() is False, (
        f"RMS simulation reported errors for legacy file: {file_path}"
    )


def _simulate_legacy_emt_file(file_path: str) -> None:
    """Open, simulate and release one historical EMT grid.

    :param file_path: Path to the historical ``.veragrid`` archive.
    :return: None.
    """
    # Keep each compatibility case in its own scope so models from one archive
    # cannot remain referenced while the following archive is being loaded.
    grid: MultiCircuit = gce.open_file(file_path)
    _ensure_active_emt_event_group(grid=grid)

    # The GUI reconciles every saved EMT terminal contract before constructing
    # the driver. This step is essential for legacy coverage because historical
    # root IO variables can retain their semantic references only through the
    # saved external mapping.
    preflight_logger: Logger = grid.check_emt_models()
    assert preflight_logger.has_errors() is False, (
        f"EMT GUI preflight rejected legacy file: {file_path}\n{preflight_logger}"
    )

    # EMT uses the three-phase operating point when it is available, matching
    # the normal GUI execution path for these archived EMT systems.
    power_flow_driver: PowerFlowDriver3Ph = PowerFlowDriver3Ph(
        grid=grid,
        options=_build_dynamic_version_power_flow_options(),
    )
    power_flow_driver.run()
    assert bool(np.all(power_flow_driver.results.converged)), (
        f"Three-phase power flow did not converge for legacy EMT file: {file_path}"
    )
    assert power_flow_driver.logger.has_errors() is False, (
        f"Three-phase power flow reported errors for legacy EMT file: {file_path}"
    )

    # Simulate every active group and validate both stages reported by the EMT
    # solver: consistent initialization and converged time integration.
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=_build_dynamic_version_emt_options(),
        pf_results_3ph=power_flow_driver.results,
        pf_results=None,
    )
    emt_driver.run()
    assert emt_driver.results is not None, (
        f"EMT driver produced no results for legacy file: {file_path}"
    )
    emt_results: EmtResults = emt_driver.results
    group_count: int = len(grid.emt_events_groups)
    active_group_mask: np.ndarray = np.zeros(group_count, dtype=bool)
    group_index: int
    emt_event_group: EmtEventsGroup
    for group_index, emt_event_group in enumerate(grid.emt_events_groups):
        active_group_mask[group_index] = emt_event_group.active
    assert bool(np.any(active_group_mask)), (
        f"No active EMT event group was available for legacy file: {file_path}"
    )
    assert bool(np.all(emt_results.has_event_group_results[active_group_mask])), (
        f"EMT simulation produced no samples for legacy file: {file_path}"
    )
    assert bool(np.all(emt_results.well_initialized[active_group_mask])), (
        f"EMT simulation was not well initialized for legacy file: {file_path}"
    )
    assert bool(np.all(emt_results.converged[active_group_mask])), (
        f"EMT simulation did not converge for legacy file: {file_path}"
    )
    assert bool(np.all(np.isfinite(emt_results.values[-1, :, active_group_mask]))), (
        f"EMT simulation did not populate its final requested sample for legacy file: {file_path}"
    )
    assert bool(np.all(np.isfinite(emt_results.diff_values[-1, :, active_group_mask]))), (
        f"EMT simulation produced non-finite final derivatives for legacy file: {file_path}"
    )
    assert emt_driver.logger.has_errors() is False, (
        f"EMT simulation reported errors for legacy file: {file_path}\n"
        f"{emt_driver.logger}"
    )


def test_legacy_duplicate_device_records_are_canonicalized() -> None:
    """Keep one authoritative device for duplicate records in a legacy archive.

    VeraGrid 6.4.2 saved the Kundur loads, generators, transformers and lines
    twice. Transformer duplicates are not equivalent: the first record has an
    empty dynamic shell and the last one contains the usable RMS model. The
    loader must therefore expose the same last-record-wins objects in both its
    idtag lookup and the circuit collections.

    :return: None.
    """
    dynamic_versions_folder: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "dynamic_versions")
    )
    file_path: str = os.path.join(
        dynamic_versions_folder,
        "kundur_rms_6_4_2.veragrid",
    )

    # Opening this file exercises the compatibility boundary without running a
    # power flow or a dynamic simulation. Every repeated persisted idtag must
    # collapse to the final authoritative record before entering MultiCircuit.
    grid: MultiCircuit = gce.open_file(file_path)
    assert len(grid.get_loads()) == 2
    assert len(grid.get_generators()) == 4
    assert len(grid.get_transformers2w()) == 4
    assert len(grid.get_lines()) == 14
    assert len({device.idtag for device in grid.get_loads()}) == 2
    assert len({device.idtag for device in grid.get_generators()}) == 4
    assert len({device.idtag for device in grid.get_transformers2w()}) == 4
    assert len({device.idtag for device in grid.get_lines()}) == 14
    assert all(not device.rms_model.empty() for device in grid.get_transformers2w())


def test_legacy_kundur_wrapper_mappings_are_localized_to_owners() -> None:
    """Localize historical RMS line and load mappings on their declaration owners.

    Early Dynamic Editor saves placed line API mappings on a wrapper while the
    equation child owned concrete ``g``, ``b`` and ``bsh`` parameters. Those
    values are template fallbacks, while the mappings identify the physical
    network values required by the DAE. The same wrapper layout was used for
    load ``Pl0`` and ``Ql0``. Compatibility loading must move each mapping to
    the child owner so recursive initialization uses the saved static grid.

    :return: None.
    """
    dynamic_versions_folder: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "dynamic_versions")
    )
    file_names: tuple[str, ...] = (
        "kundur_from_gui_6_3_2.veragrid",
        "kundur_from_gui_6_3_4.veragrid",
        "kundur_from_gui_6_3_8.veragrid",
        "kundur_rms_6_5_29.veragrid",
    )
    expected_parameter_values: dict[str, float] = dict((
        ("g", 5.0),
        ("b", -12.0),
        ("bsh", 0.03),
    ))
    line_mapping_keys: set[ParamPowerFlowReferenceType] = set((
        ParamPowerFlowReferenceType.g,
        ParamPowerFlowReferenceType.b,
        ParamPowerFlowReferenceType.bsh,
    ))
    load_mapping_keys: set[ParamPowerFlowReferenceType] = set((
        ParamPowerFlowReferenceType.Pl0,
        ParamPowerFlowReferenceType.Ql0,
    ))

    file_name: str
    for file_name in file_names:
        file_path: str = os.path.join(dynamic_versions_folder, file_name)
        grid: MultiCircuit = gce.open_file(file_path)
        first_line_model: Block = grid.get_lines()[0].rms_model
        first_load_model: Block = grid.get_loads()[0].rms_model
        actual_parameter_values: dict[str, float] = dict()
        mapped_line_keys: set[ParamPowerFlowReferenceType] = set()
        mapped_load_keys: set[ParamPowerFlowReferenceType] = set()
        model_block: Block
        parameter: Var
        parameter_value: Const
        mapping_key: ParamPowerFlowReferenceType

        # Inspect the complete loaded hierarchy because old archives placed the
        # mapping and declaration on different blocks.
        for model_block in first_line_model.get_all_blocks():
            for parameter, parameter_value in model_block.parameters.items():
                if parameter.name in expected_parameter_values:
                    actual_parameter_values[parameter.name] = float(parameter_value.value)
                else:
                    pass
            for mapping_key in model_block.api_obj_mapping:
                if mapping_key in line_mapping_keys:
                    mapped_line_keys.add(mapping_key)
                else:
                    pass

        # Load fallbacks may be constants or symbolic PF initialization
        # expressions depending on the archive version. In every case the
        # physical mapping must be owned by the block that declares the target.
        for model_block in first_load_model.get_all_blocks():
            for mapping_key in model_block.api_obj_mapping:
                if mapping_key in load_mapping_keys:
                    mapped_load_keys.add(mapping_key)
                else:
                    pass

        assert actual_parameter_values == expected_parameter_values
        assert mapped_line_keys == line_mapping_keys
        assert mapped_load_keys == load_mapping_keys


def test_legacy_kundur_governor_limits_keep_runtime_storage() -> None:
    """Keep the serialized governor vector contract in historical Kundur files.

    Legacy governors store ``Pmin`` and ``Pmax`` beside their other tunable
    values in ``event_dict``. Moving only those two symbols to ``parameters``
    changes the RMS runtime-vector structure and can make an otherwise valid
    archived case fail at the first integration step.

    :return: None.
    """
    dynamic_versions_folder: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "dynamic_versions")
    )
    file_names: tuple[str, ...] = (
        "kundur_rms_6_0_22.veragrid",
        "kundur_from_gui_6_3_2.veragrid",
        "kundur_from_gui_6_3_4.veragrid",
        "kundur_from_gui_6_3_8.veragrid",
        "kundur_rms_6_5_29.veragrid",
    )
    limit_names: set[str] = set(("Pmin", "Pmax"))
    limit_mapping_keys: set[ParamPowerFlowReferenceType] = set((
        ParamPowerFlowReferenceType.Pmin,
        ParamPowerFlowReferenceType.Pmax,
    ))

    file_name: str
    for file_name in file_names:
        file_path: str = os.path.join(dynamic_versions_folder, file_name)
        grid: MultiCircuit = gce.open_file(file_path)
        generator: Generator
        for generator in grid.get_generators():
            runtime_names: set[str] = set()
            constant_names: set[str] = set()
            mapping_keys: set[ParamPowerFlowReferenceType] = set()
            model_block: Block
            parameter: Var
            mapping_key: ParamPowerFlowReferenceType

            # The governor is a descendant of the complete generator wrapper.
            # Inspect the full hierarchy so this test protects the effective
            # storage contract rather than depending on one block depth.
            for model_block in generator.rms_model.get_all_blocks():
                for parameter in model_block.event_dict:
                    if parameter.name in limit_names:
                        runtime_names.add(parameter.name)
                    else:
                        pass
                for parameter in model_block.parameters:
                    if parameter.name in limit_names:
                        constant_names.add(parameter.name)
                    else:
                        pass
                for mapping_key in model_block.api_obj_mapping:
                    if mapping_key in limit_mapping_keys:
                        mapping_keys.add(mapping_key)
                    else:
                        pass

            assert runtime_names == limit_names
            assert constant_names == set()
            assert mapping_keys == set()


def test_legacy_mode_sibling_owners_are_reported_as_ambiguous() -> None:
    """Do not choose between same-depth legacy ``mode_dict`` owners.

    :return: None.
    """
    stable_uid: int = 91001
    first_mode: Var = Var("legacy_mode", non_mutable_uid=stable_uid)
    second_mode: Var = Var("legacy_mode", non_mutable_uid=stable_uid)
    root_block: Block = Block(
        name="legacy_mode_root",
        children=list((
            Block(name="first_mode_owner", mode_dict=dict(((first_mode, Const(0.0)),))),
            Block(name="second_mode_owner", mode_dict=dict(((second_mode, Const(1.0)),))),
        )),
    )
    logger: Logger = Logger()
    parser: BlockParser = BlockParser(var_factory=VarFactory(), logger=logger)

    ambiguous_static_uids: set[int]
    ambiguous_runtime_uids: set[int]
    ambiguous_static_uids, ambiguous_runtime_uids = parser._get_ambiguous_legacy_parameter_uids(
        root_block=root_block,
    )

    assert ambiguous_static_uids == set()
    assert ambiguous_runtime_uids == set((stable_uid,))
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == "Legacy runtime parameter has multiple equivalent owners; migration was skipped"
    assert logger.entries[0].device_property == "event_dict/mode_dict"


def test_legacy_wrapper_mode_mapping_moves_to_mode_owner() -> None:
    """Localize an old wrapper API mapping without changing mode storage.

    :return: None.
    """
    stable_uid: int = 91002
    wrapper_target: Var = Var("legacy_mode", non_mutable_uid=stable_uid)
    mode_target: Var = Var("legacy_mode", non_mutable_uid=stable_uid)
    mode_fallback: Const = Const(0.25)
    mode_owner: Block = Block(
        name="legacy_mode_owner",
        mode_dict=dict(((mode_target, mode_fallback),)),
    )
    root_block: Block = Block(
        name="legacy_mode_wrapper",
        children=list((mode_owner,)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, wrapper_target),)),
    )
    parser: BlockParser = BlockParser(var_factory=VarFactory(), logger=Logger())

    migrated_count: int = parser._migrate_legacy_static_api_parameters(root_block=root_block)

    assert migrated_count == 1
    assert ParamPowerFlowReferenceType.Pl0 not in root_block.api_obj_mapping
    assert mode_owner.api_obj_mapping[ParamPowerFlowReferenceType.Pl0] is mode_target
    assert mode_owner.mode_dict[mode_target] is mode_fallback
    assert mode_target not in mode_owner.event_dict


def test_legacy_wrapper_mode_mapping_uses_deepest_owner_across_uneven_branches() -> None:
    """Select the deepest runtime owner independently of traversal order.

    :return: None.
    """
    stable_uid: int = 91003
    wrapper_target: Var = Var("legacy_mode", non_mutable_uid=stable_uid)
    deep_mode_target: Var = Var("legacy_mode", non_mutable_uid=stable_uid)
    shallow_mode_target: Var = Var("legacy_mode", non_mutable_uid=stable_uid)
    deep_mode_owner: Block = Block(
        name="deep_mode_owner",
        mode_dict=dict(((deep_mode_target, Const(0.25)),)),
    )
    deep_container: Block = Block(
        name="deep_container",
        children=list((deep_mode_owner,)),
    )
    shallow_mode_owner: Block = Block(
        name="shallow_mode_owner",
        mode_dict=dict(((shallow_mode_target, Const(0.75)),)),
    )
    root_block: Block = Block(
        name="legacy_uneven_wrapper",
        # Depth-first order places the shallow sibling after the nested owner.
        # Reversing that list would therefore choose the wrong declaration.
        children=list((deep_container, shallow_mode_owner)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, wrapper_target),)),
    )
    parser: BlockParser = BlockParser(var_factory=VarFactory(), logger=Logger())

    migrated_count: int = parser._migrate_legacy_static_api_parameters(root_block=root_block)

    assert migrated_count == 1
    assert ParamPowerFlowReferenceType.Pl0 not in root_block.api_obj_mapping
    assert deep_mode_owner.api_obj_mapping[ParamPowerFlowReferenceType.Pl0] is deep_mode_target
    assert ParamPowerFlowReferenceType.Pl0 not in shallow_mode_owner.api_obj_mapping


def test_dynamic_versions_run_rms_and_emt_sequentially() -> None:
    """Simulate legacy RMS and EMT archives from different releases.

    Every helper invocation owns exactly one loaded circuit and one simulation
    driver. Returning from the helper releases that case before the next archive
    is opened, which intentionally prevents cross-file symbolic state reuse.

    Each family retains representative engine-created archives and includes
    every GUI-created archive because their serialized symbolic layouts form a
    distinct legacy contract. The integration windows are intentionally short
    so the expanded compatibility matrix remains practical. Each case must
    complete its power flow, initialize consistently, produce samples and
    converge without logger errors.

    :return: None.
    """
    dynamic_versions_folder: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "dynamic_versions")
    )
    rms_file_names: tuple[str, ...] = (
        "kundur_rms_6_0_22.veragrid",
        "kundur_rms_6_1_4.veragrid",
        "kundur_rms_6_2_11.veragrid",
        "kundur_rms_6_4_2.veragrid",
        "kundur_rms_6_5_29.veragrid",
        "kundur_from_gui_6_0_22.veragrid",
        "kundur_from_gui_6_1_3.veragrid",
        "kundur_from_gui_6_1_4.veragrid",
        "kundur_from_gui_6_2_0.veragrid",
        "kundur_from_gui_6_2_11.veragrid",
        "kundur_from_gui_6_2_3.veragrid",
        "kundur_from_gui_6_2_4.veragrid",
        "kundur_from_gui_6_3_2.veragrid",
        "kundur_from_gui_6_3_4.veragrid",
        "kundur_from_gui_6_3_8.veragrid",
        "kundur_from_gui_6_4_0.veragrid",
        "kundur_from_gui_6_4_2.veragrid",
        "kundur_from_gui_6_5_0.veragrid",
        "kundur_from_gui_6_5_17.veragrid",
        "kundur_from_gui_6_5_22.veragrid",
        "kundur_from_gui_6_5_29.veragrid",
        "kundur_from_gui_6_7_7.veragrid",
    )
    emt_file_names: tuple[str, ...] = (
        "emt_syst_6_0_22.veragrid",
        "emt_syst_6_1_3.veragrid",
        "emt_syst_6_2_4.veragrid",
        "emt_syst_6_3_8.veragrid",
        "emt_syst_6_5_17.veragrid",
        "emt_syst_6_5_37.veragrid",
        "emt_syst_from_gui_6_0_22.veragrid",
        "emt_syst_from_gui_6_1_3.veragrid",
        "emt_syst_from_gui_6_1_4.veragrid",
        "emt_syst_from_gui_6_2_0.veragrid",
        "emt_syst_from_gui_6_2_11.veragrid",
        "emt_syst_from_gui_6_2_3.veragrid",
        "emt_syst_from_gui_6_2_4.veragrid",
        "emt_syst_from_gui_6_3_2.veragrid",
        "emt_syst_from_gui_6_3_4.veragrid",
        "emt_syst_from_gui_6_3_8.veragrid",
        "emt_syst_from_gui_6_4_2.veragrid",
        "emt_syst_from_gui_6_5_0.veragrid",
        "emt_syst_from_gui_6_5_17.veragrid",
        "emt_syst_from_gui_6_5_22.veragrid",
        "emt_syst_from_gui_6_5_29.veragrid",
        "emt_syst_from_gui_6_7_7.veragrid",
    )

    # Finish and release every RMS case before opening its successor.
    file_name: str
    for file_name in rms_file_names:
        rms_file_path: str = os.path.join(dynamic_versions_folder, file_name)
        _simulate_legacy_rms_file(file_path=rms_file_path)

    # Repeat the same strictly sequential lifecycle for the EMT archives.
    for file_name in emt_file_names:
        emt_file_path: str = os.path.join(dynamic_versions_folder, file_name)
        _simulate_legacy_emt_file(file_path=emt_file_path)


def test_load_save_load_dynamic_versions() -> None:
    """
    This test checks if the saving and load process is correct for old dynamic versions with legacy.

    The test consists in:
    - Loading grids created from gui and from scripting with dynamic models.
    - The grids were created in old VeraGrid versions in which some symbolism might have changed compared to the current version.

    """
    folder = os.path.join('data', 'dynamic_versions')

    if not os.path.exists(os.path.join("data", "output")):
        os.makedirs(os.path.join("data", "output"))


    for name in [
        'kundur_from_gui_6_0_22.veragrid',
        'kundur_from_gui_6_1_3.veragrid',
        'kundur_from_gui_6_1_4.veragrid',
        'kundur_from_gui_6_2_0.veragrid',
        'kundur_from_gui_6_2_11.veragrid',
        'kundur_from_gui_6_2_3.veragrid',
        'kundur_from_gui_6_2_4.veragrid',
        'kundur_from_gui_6_3_2.veragrid',
        'kundur_from_gui_6_3_4.veragrid',
        'kundur_from_gui_6_3_8.veragrid',
        'kundur_from_gui_6_4_0.veragrid',
        'kundur_from_gui_6_4_2.veragrid',
        'kundur_from_gui_6_5_0.veragrid',
        'kundur_from_gui_6_5_17.veragrid',
        'kundur_from_gui_6_5_22.veragrid',
        'kundur_from_gui_6_5_29.veragrid',
        'kundur_from_gui_6_7_7.veragrid',
        'kundur_rms_6_0_22.veragrid',
        'kundur_rms_6_1_3.veragrid',
        'kundur_rms_6_1_4.veragrid',
        'kundur_rms_6_2_0.veragrid',
        'kundur_rms_6_2_11.veragrid',
        'kundur_rms_6_2_3.veragrid',
        'kundur_rms_6_2_4.veragrid',
        'kundur_rms_6_3_2.veragrid',
        'kundur_rms_6_3_4.veragrid',
        'kundur_rms_6_3_8.veragrid',
        'kundur_rms_6_4_0.veragrid',
        'kundur_rms_6_4_2.veragrid',
        'kundur_rms_6_5_0.veragrid',
        'kundur_rms_6_5_17.veragrid',
        'kundur_rms_6_5_22.veragrid',
        'kundur_rms_6_5_29.veragrid',
        'kundur_rms_6_7_7.veragrid',
        'kundur_static_6_0_22.veragrid',
        'kundur_static_6_1_3.veragrid',
        'kundur_static_6_1_4.veragrid',
        'kundur_static_6_2_0.veragrid',
        'kundur_static_6_2_11.veragrid',
        'kundur_static_6_2_3.veragrid',
        'kundur_static_6_2_4.veragrid',
        'kundur_static_6_3_2.veragrid',
        'kundur_static_6_3_4.veragrid',
        'kundur_static_6_3_8.veragrid',
        'kundur_static_6_4_0.veragrid',
        'kundur_static_6_4_2.veragrid',
        'kundur_static_6_5_0.veragrid',
        'kundur_static_6_5_17.veragrid',
        'kundur_static_6_5_22.veragrid',
        'kundur_static_6_5_29.veragrid',
        'kundur_static_6_7_7.veragrid',
        'emt_syst_from_gui_6_0_22.veragrid',
        'emt_syst_from_gui_6_1_3.veragrid',
        'emt_syst_from_gui_6_1_4.veragrid',
        'emt_syst_from_gui_6_2_0.veragrid',
        'emt_syst_from_gui_6_2_3.veragrid',
        'emt_syst_from_gui_6_2_4.veragrid',
        'emt_syst_from_gui_6_2_11.veragrid',
        'emt_syst_from_gui_6_3_2.veragrid',
        'emt_syst_from_gui_6_3_4.veragrid',
        'emt_syst_from_gui_6_3_8.veragrid',
        'emt_syst_from_gui_6_4_2.veragrid',
        'emt_syst_from_gui_6_5_0.veragrid',
        'emt_syst_from_gui_6_5_17.veragrid',
        'emt_syst_from_gui_6_5_22.veragrid',
        'emt_syst_from_gui_6_5_29.veragrid',
        'emt_syst_from_gui_6_7_7.veragrid',
        'emt_syst_6_1_3.veragrid',
        'emt_syst_6_1_4.veragrid',
        'emt_syst_6_2_0.veragrid',
        'emt_syst_6_2_3.veragrid',
        'emt_syst_6_2_4.veragrid',
        'emt_syst_6_2_11.veragrid',
        'emt_syst_6_3_2.veragrid',
        'emt_syst_6_3_4.veragrid',
        'emt_syst_6_3_8.veragrid',
        'emt_syst_6_4_2.veragrid',
        'emt_syst_6_5_0.veragrid',
        'emt_syst_6_5_17.veragrid',
        'emt_syst_6_5_22.veragrid',
        'emt_syst_6_5_37.veragrid',
        'emt_syst_6_7_7.veragrid',
        'emt_syst_static_6_1_3.veragrid',
        'emt_syst_static_6_1_4.veragrid',
        'emt_syst_static_6_2_0.veragrid',
        'emt_syst_static_6_2_3.veragrid',
        'emt_syst_static_6_2_4.veragrid',
        'emt_syst_static_6_2_11.veragrid',
        'emt_syst_static_6_3_2.veragrid',
        'emt_syst_static_6_3_4.veragrid',
        'emt_syst_static_6_3_8.veragrid',
        'emt_syst_static_6_4_2.veragrid',
        'emt_syst_static_6_5_0.veragrid',
        'emt_syst_static_6_5_17.veragrid',
        'emt_syst_static_6_5_22.veragrid',
        'emt_syst_static_6_5_37.veragrid',
        'emt_syst_static_6_7_7.veragrid',

    ]:

        print(f"Testing file {name}")
        fname = os.path.join(folder, name)

        # open the main grid
        grid1 = gce.open_file(fname)

        name, ext = os.path.splitext(os.path.basename(fname))

        fname2 = os.path.join("data", "output", name + '_to_save.veragrid')

        gce.save_file(grid=grid1, filename=fname2)

        # open the main grid again
        grid2 = gce.open_file(fname2)

        # compare the original grid with the saved one to check that they are equal
        equal, logger = grid1.compare_circuits(grid2, detailed_profile_comparison=True)

        if not equal:
            logger.print()

        # asset for failing
        assert equal

        # if all ok, we can delete the test file
        os.remove(fname2)

