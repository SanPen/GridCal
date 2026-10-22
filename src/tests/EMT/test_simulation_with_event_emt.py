# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Any, cast
import pandas as pd
from pandas.testing import assert_frame_equal
import os

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.emt_event import EmtEvent

from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver

from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes, ShuntConnectionType
import VeraGridEngine.api as gce

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

def test_simulation_with_event_emt() -> None:
    """
    Compare the complete historical EMT resistance-event trajectory.

    The reference starts with automatically sized phase resistances, followed
    by events setting them to 3 pu and then 6 pu. Preserve the initial power
    flow sizing so the complete trajectory remains comparable to the CSV.

    :return: None; compare every state and derivative with the historical CSV.
    """

    #########
    # retrieve reference results df

    name = "simulation_with_event_emt.csv"

    fname = os.path.join(os.path.dirname(__file__), '..', 'data', 'dynamics', name)

    # fname = "simulation_with_event_emt.csv"

    reference_df = pd.read_csv(fname)

    ###########################################################################################################################
    # Build VeraGrid object
    grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

    # Buses
    vnom = 10  # kV
    bus0 = gce.Bus(name="Bus0", Vnom=vnom, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=vnom)

    grid.add_bus(bus0)
    grid.add_bus(bus1)

    # Lines
    line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)

    # physical configuration (Overhead line tower)
    tower = gce.OverheadLineType(name="Tower", Vnom=vnom)
    wire = gce.Wire(name="Panther 30/7 ACSR",
                    diameter=21.0,
                    diameter_internal=9.0,
                    is_tube=True,
                    r=0.1363,
                    max_current=1)
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()

    line0.apply_template(tower, grid.Sbase, grid.fBase)

    R_ph = 100  # ohm
    v_ph = vnom / (3 ** 0.5)
    P_ph = (v_ph ** 2) / R_ph  # kv*kv/ohm = MW
    Q_ph = 0.0
    load = gce.Load(name="load", P1=P_ph, P2=P_ph, P3=P_ph, Q1=Q_ph, Q2=Q_ph, Q3=Q_ph)
    load.conn = ShuntConnectionType.GroundedStar

    # Generators
    gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq=50, r1=0.001, x1=1.7)
    # r1=Ra, x1=xd'

    grid.add_line(line0)
    grid.add_generator(bus=bus0, api_obj=gen0)
    grid.add_load(bus=bus1, api_obj=load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    ######################################################################################################
    # Build Rms models
    ######################################################################################################

    # generator
    gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block

    # line
    line_mdl = get_pi_line_emt_template(vf = grid.var_factory, phN = False, phA = True, phB = True, phC = True).block

    # load
    load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

    ######################################################################################################
    # Add models to devices
    ######################################################################################################

    set_emt_model(device=gen0, model=gen_mdl, var_factory=grid.var_factory)

    set_emt_model(device=line0, model=line_mdl, var_factory=grid.var_factory)

    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    # apply event
    R_A = find_name_in_block('R_A_Shunt_R_3ph', load_mdl)
    R_B = find_name_in_block('R_B_Shunt_R_3ph', load_mdl)
    R_C = find_name_in_block('R_C_Shunt_R_3ph', load_mdl)
    events_group = EmtEventsGroup(name="simulation1")
    grid.add_emt_events_group(events_group)
    event_R_A = EmtEvent(device=load, parameter=R_A, time=0.02, value=3.0, group=events_group)
    grid.add_emt_event(event_R_A)
    event_R_B = EmtEvent(device=load, parameter=R_B, time=0.02, value=3.0, group=events_group)
    grid.add_emt_event(event_R_B)
    event_R_C = EmtEvent(device=load, parameter=R_C, time=0.02, value=3.0, group=events_group)
    grid.add_emt_event(event_R_C)

    event_R_A = EmtEvent(device=load, parameter=R_A, time=0.04, value=6.0, group=events_group)
    grid.add_emt_event(event_R_A)
    event_R_B = EmtEvent(device=load, parameter=R_B, time=0.04, value=6.0, group=events_group)
    grid.add_emt_event(event_R_B)
    event_R_C = EmtEvent(device=load, parameter=R_C, time=0.04, value=6.0, group=events_group)
    grid.add_emt_event(event_R_C)

    emt_events_group_names = np.array(0)

    pf_options = gce.PowerFlowOptions(
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
    power_flow = PowerFlowDriver3Ph(grid, pf_options)
    power_flow.run()
    res = power_flow.results

    # A reference trajectory is only valid when its steady-state seed converged.
    assert bool(res.converged)

    print(f"Converged: {res.converged}")
    print(res.get_bus_df())
    print(res.get_branch_df())

    options = EmtOptions(time_step=5e-6,
                         simulation_time=0.06,  # s
                         tolerance=1e-6,
                         solver_type=EmtSolverTypes.Symbolic,
                         integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
                         verbose=1)

    problem = EmtProblemDae(grid=grid,
                            options=options,
                            pf_results_3ph=res,
                            pf_results=None)

    problem.set_events_group(events_group)

    solver = JitSymbolicSolver(problem = problem,
                                 t0 = 0.0,
                                 t_end = options.simulation_time,
                                 h = options.time_step,
                                 method=options.integration_method,
                                 pred_method=DynamicIntegrationMethod.OdeEuler,
                                 dense_threshold=0,
                                 verbose = True)

    boundary_updater = cast(Any, problem)
    t, y, dy, well_initialized, converged = solver.simulate(boundary_updater=boundary_updater)

    # Never accept a golden trajectory from an invalid EMT initialization or run.
    assert well_initialized
    assert converged

    res = np.concatenate((y, dy), axis=1)

    cols_y = [f"y{i}" for i in range(y.shape[1])]
    cols_dy = [f"dy{i}" for i in range(dy.shape[1])]
    cols = cols_y + cols_dy

    results_df = pd.DataFrame(res, index=t, columns=cols)
    results_df.index.name = "time_s"

    # The EMT reference is a complete trajectory contract. Compare every state
    # and derivative at every simulated instant, including the initialized point
    # at t=0 and both event boundaries.
    assert list(results_df.columns) == list(reference_df.columns)
    assert_frame_equal(
        results_df.reset_index(drop=True),
        reference_df.reset_index(drop=True),
        check_dtype=False,
        check_index_type=False,
        atol=1.0e-6,
        rtol=1.0e-6,
    )


if __name__ == "__main__":
    test_simulation_with_event_emt()
