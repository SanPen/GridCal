# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import pandas as pd
import numpy as np
from pandas.testing import assert_frame_equal

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
# from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template_v2 import get_complete_generator_template_rms
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model

from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
import VeraGridEngine.api as gce


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


def test_simulation_with_event():
    """
    This test creates a grid, adds rms models and events and rens simulation. Then it compares results with reference.
    :return:
    :rtype:
    """

    #########
    # retrieve reference results df

    folder = os.path.join(os.path.dirname(__file__), '..', 'data', 'dynamics')
    name = "simulation_with_event.csv"

    fname = os.path.join(folder, name)

    reference_df = pd.read_csv(fname)

    ###########################################################################################################################
    # Build VeraGrid object

    #####################################################################################
    #                    Grid
    #####################################################################################

    grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

    #####################################################################################
    #                    Devices
    #####################################################################################

    # Buses
    bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10)

    grid.add_bus(bus0)
    grid.add_bus(bus1)

    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.var_factory)

    # Lines
    line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus1, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
                     rate=900.0)
    grid.add_line(line0)

    # load
    load = gce.Load(P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)

    # Generators
    gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900,
                         x1=0.86138701, r1=0.3, freq=50.0
                         )
    grid.add_generator(bus=bus0, api_obj=gen0)

    ######################################################################################################
    # Build Rms models
    ######################################################################################################

    # generator
    genqec_mdl = get_complete_generator_template_rms(grid.var_factory).block

    # line
    line_mdl = get_line_rms_template(grid.var_factory).block

    # load
    load_mdl = get_load_rms_template(grid.var_factory).block

    ######################################################################################################
    # Add models to devices
    ######################################################################################################

    set_rms_model(device=gen0, model=genqec_mdl, var_factory=grid.var_factory)

    set_rms_model(device=line0, model=line_mdl, var_factory=grid.var_factory)

    set_rms_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    ######################################################################################################
    # Create event
    ######################################################################################################

    Pl0 = find_name_in_block('Pl0', load_mdl)
    events_group = RmsEventsGroup(name="simulation1")
    grid.add_rms_events_group(events_group)
    event = RmsEvent(
        device=load,
        parameter=Pl0,
        time=0.1,
        value=-0.098,
        group=events_group,
        transition_type=DynamicEventTransitionType.Step,
    )
    grid.add_rms_event(event)

    rms_events_group_names = np.array(0)

    options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
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
    res = gce.power_flow(grid, options=options)

    print(f"Converged: {res.converged}")
    print(res.get_bus_df())
    print(res.get_branch_df())

    params_mapping = dict()

    options = RmsOptions(time_step=0.001,
                         simulation_time=1,
                         tolerance=1e-6,
                         integration_method=DynamicIntegrationMethod.DaeBackEuler,
                         initialization_method=RmsInitializationMethod.Explicit,
                         use_init_values=False,
                         max_iter=1000,
                         verbose=0)

    problem = RmsProblemDae(grid=grid,
                            options=options,
                            pf_results=res)

    problem.set_events_group(events_group)
    problem.reset_boundary_update_state(0.0)

    solver = BackEulerImplicitIntegration(
        problem=problem,
        t0=0,
        t_end=options.simulation_time,
        h=options.time_step,
        max_iter=options.max_iter
    )

    t, y, well_initialized, converged = solver.simulate()

    # The historical reference includes five internal variables that no longer
    # belong to the RMS DAE vector. Preserve the old CSV as a legacy artefact,
    # but remove only those obsolete columns before comparing every current
    # variable at every simulated time step.
    legacy_columns: list[str] = [f"var{column_index}" for column_index in range(68)]
    assert legacy_columns == list(reference_df.columns)

    legacy_result_columns: list[str] = [f"var{column_index}" for column_index in range(29)]
    legacy_result_columns.extend(
        [f"var{column_index}" for column_index in range(34, 68)]
    )

    result_columns: list[str] = [f"var{column_index}" for column_index in range(y.shape[1])]
    assert len(legacy_result_columns) == len(result_columns)

    reference_df = reference_df.loc[:, legacy_result_columns].copy()
    reference_df.columns = result_columns
    results_df: pd.DataFrame = pd.DataFrame(y, columns=result_columns)

    assert_frame_equal(
        results_df.reset_index(drop=True),
        reference_df.reset_index(drop=True),
        check_dtype=False,
        check_index_type=False,
        atol=1e-5,
        rtol=1e-5,
    )


def test_rms_event_can_store_ramp_transition_metadata() -> None:
    """
    Check that RMS events preserve ramp-transition metadata.

    :return: None.
    """
    event: RmsEvent = RmsEvent(time=0.1,
                               end_time=0.2,
                               value=1.5,
                               transition_type=DynamicEventTransitionType.Ramp)

    assert event.time == 0.1
    assert event.end_time == 0.2
    assert event.value == 1.5
    assert event.transition_type == DynamicEventTransitionType.Ramp


def test_rms_event_accepts_serialized_ramp_transition_metadata() -> None:
    """
    Check that RMS events restore ramp metadata from serialized text.

    GUI and persistence layers can reconstruct the transition profile from the
    enum string value. The RMS event object must normalize that representation so
    the solver can still recognize the event as a ramp.

    :return: None.
    """
    event: RmsEvent = RmsEvent(time=0.1,
                               end_time=0.2,
                               value=1.5,
                               transition_type=DynamicEventTransitionType.Ramp)

    assert event.time == 0.1
    assert event.end_time == 0.2
    assert event.value == 1.5
    assert event.transition_type == DynamicEventTransitionType.Ramp
