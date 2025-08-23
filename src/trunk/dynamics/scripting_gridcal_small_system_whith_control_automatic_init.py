# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import pdb

import numpy as np
from matplotlib import pyplot as plt

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from GridCalEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from GridCalEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from GridCalEngine.Utils.Symbolic.block import Block
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver  # compose_system_block
import GridCalEngine.api as gce

# In this script a small system in build with a Generator a Load and a line. Generator is connected to bus 1 and Load is connected to bus 2.
# The system is uncontrolled and there are no events applyed.

# ----------------------------------------------------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------------------------------------------------
# line0
g_0 = Const(5)
b_0 = Const(-12)
bsh_0 = Const(0.03)

# line1
g_1 = Const(5)
b_1 = Const(-12)
bsh_1 = Const(0.03)

pi = Const(math.pi)

# Generator 0
fn_0 = Const(50.0)
M_0 = Const(10.0)
D_0 = Const(1.0)
ra_0 = Const(0.3)
xd_0 = Const(0.86138701)

omega_ref_0 = Const(1.0)
Kp_0 = Const(0.0)
Ki_0 = Const(0.0)

# Generator 1
fn_1 = Const(50.0)
M_1 = Const(10.0)
D_1 = Const(1.0)
ra_1 = Const(0.3)
xd_1 = Const(0.86138701)

omega_ref_1 = Const(1.0)
Kp_1 = Const(0.0)
Ki_1 = Const(0.0)

# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------
# Build the system to compute the powerflow
grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus2 = gce.Bus(name="Bus2", Vnom=10)
bus1 = gce.Bus(name="Bus1", Vnom=10)
grid.add_bus(bus0)
grid.add_bus(bus2)
grid.add_bus(bus1)

# Line
line0 = grid.add_line(
    gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
             rate=900.0))
line1 = grid.add_line(
    gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03,
             rate=900.0))

# load
load_grid = grid.add_load(bus=bus2, api_obj=gce.Load(P=10, Q=10))

# Generators
gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900,
                     x1=0.86138701, r1=0.3, freq=50.0,
                     # m_torque0=0.1,
                     M=10.0,
                     D=1.0,
                     omega_ref=1.0,
                     Kp=1.0,
                     Ki=10.0,
                     # Kw=10.0
                     )

gen1 = gce.Generator(name="Gen1", P=10, vset=1.0, Snom=900,
                     x1=0.86138701, r1=0.3, freq=50.0,
                     # m_torque0=0.1,
                     M=10.0,
                     D=1.0,
                     omega_ref=1.0,
                     Kp=1.0,
                     Ki=10.0,
                     # Kw=10.0
                     )
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_generator(bus=bus1, api_obj=gen1)

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
    three_phase_unbalanced=False
)
res = gce.power_flow(grid, options=options)

print(f"Converged: {res.converged}")
print(res.get_bus_df())

bus_df = res.get_bus_df()
value = bus_df.loc['Bus1', 'Va']
print(value)

print(res.get_branch_df())

logger = gce.Logger()
gce.initialize_rms(grid, res, logger=logger)
sys, mapping = gce.compose_system_block(grid, res)
print(mapping)

# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = BlockSolver(sys)

params_mapping = {
    # Pl0: 0.1,
    # Ql0: 0.1
}

# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------

# event1 = RmsEvent(Pl0, 5000, 0.3)
# event2 = Event(Ql0, 5000, 0.3)
# my_events = RmsEvents([event1])
my_events = RmsEvents([])
params0 = slv.build_init_params_vector(params_mapping)

# x0 = slv.build_init_vars_vector(mapping)

x0 = slv.build_init_vars_vector_from_uid(mapping)

# x0 = slv.initialize_with_newton(x0=slv.build_init_vars_vector(vars_mapping),
#                                 params0=params0)
#
# x0 = slv.initialize_with_pseudo_transient_gamma(
#     x0=slv.build_init_vars_vector(mapping),
#     # x0=np.zeros(len(slv._state_vars) + len(slv._algebraic_vars)),
#     params0=params0
# )


# x0, params0 = slv.initialise_homotopy(
#     z0=slv.build_init_vars_vector(vars_mapping),  # flat start
#     params=params0,
#     ramps=[(Pl, 0.0), (Ql, 0.0)],  # tuple of var, value to vary with the homotopy
# )

# x0, params0 = slv.initialise_homotopy_adaptive_lambda(
#     z0=slv.build_init_vars_vector(vars_mapping),  # flat start
#     params=params0,
#     ramps=[(Pl, 0.0), (Ql, 0.0)],
# )

# vars_in_order = slv.sort_vars(mapping)

vars_in_order = slv.sort_vars_from_uid(mapping)

t, y = slv.simulate(
    t0=0,
    t_end=20.0,
    h=0.001,
    x0=x0,
    params0=params0,
    events_list=my_events,
    method="implicit_euler"
)

# save to csv
slv.save_simulation_to_csv('simulation_results_automatic_init.csv', t, y)
