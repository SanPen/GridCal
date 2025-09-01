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

from VeraGridEngine.Devices.Aggregation.rms_event import RmsEvent
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver  # compose_system_block
import VeraGridEngine.api as gce

# In this script a small system in build with a Generator a Load and a line. Generator is connected to bus 1 and Load is connected to bus 2.
# The system is uncontrolled and there are no events applyed.

# ----------------------------------------------------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------------------------------------------------

# for the lines

# line0
r_0, x_0, bsh_0 = 0.005,   0.05,   0.02187

# line1
r_1, x_1, bsh_1 = 0.005,   0.05,   0.02187

pi = Const(math.pi)

# Generator 0
fn_0 = 60.0
M_0 = 4.0
D_0 = 1.0
ra_0 = 0.0
xd_0 = 0.3
omega_ref_0 = 1.0
Kp_0 = 0.0
Kp_0 = 0.0
Ki_0 = 0.0

# Generator 1
fn_1 = 60.0
M_1 = 4.0
D_1 = 1.0
ra_1 = 0.0
xd_1 = 0.3
omega_ref_1 = 1.0
Kp_1 = 0.0
Kp_1 = 0.0
Ki_1 = 0.0


# ----------------------------------------------------------------------------------------------------------------------
# Build the system
# ----------------------------------------------------------------------------------------------------------------------

t = Var("t")

grid = gce.MultiCircuit(Sbase=100, fbase=60.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=20, is_slack=True)
bus2 = gce.Bus(name="Bus2", Vnom=20)
bus1 = gce.Bus(name="Bus1", Vnom=20)
grid.add_bus(bus0)
grid.add_bus(bus1)
grid.add_bus(bus2)

# Lines
line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus2, r=0.005, x=0.05, b=0.02187, rate=900.0)
line1 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.005, x=0.05, b=0.02187, rate=900.0)
grid.add_line(line0)
grid.add_line(line1)

# load

Load0 = gce.Load(name="Load0", P= 7.5, Q= 1.0, Pl0= -0.075000000001172, Ql0= -0.009999999862208533)
Load0.time = t
load_grid = grid.add_load(bus=bus2, api_obj=Load0)

# Generators
gen0 = gce.Generator(name="Gen0", P=4, vset=1.0, Snom=900,
                     x1=xd_0, r1=ra_0, freq=fn_0,
                     vf=0.9949586567266662,
                     tm0=0.04001447535676884,
                     M=M_0,
                     D=D_0,
                     omega_ref=omega_ref_0,
                     Kp=Kp_0,
                     Ki=Ki_0,
                     )

gen1 = gce.Generator(name="Gen1", P=3.5, vset=1.0, Snom=900,
                     x1=xd_1, r1=ra_1, freq=fn_1,
                     vf=0.9950891766401684,
                     tm0=0.035000000019606944,
                     M=M_1,
                     D=D_1,
                     omega_ref=omega_ref_1,
                     Kp=Kp_1,
                     Ki=Ki_1,
                     )
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_generator(bus=bus1, api_obj=gen1)

# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------

event1 = RmsEvent(Load0, "Pl0", 0.1, 0.15)
grid.add_rms_event(event1)

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

# print power flow results

print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

logger = gce.Logger()


# ----------------------------------------------------------------------------------------------------------------------
# Build init guess and solver
# ----------------------------------------------------------------------------------------------------------------------



sys_block, init_guess = gce.initialize_rms(grid, res)
print(init_guess)

# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = BlockSolver(sys_block, t)

params_mapping = {
    # Pl0: 0.1,
    # Ql0: 0.1
}

# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------

params0 = slv.build_init_params_vector(params_mapping)

# x0 = slv.build_init_vars_vector(mapping)

x0 = slv.build_init_vars_vector_from_uid(init_guess)

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

vars_in_order = slv.sort_vars_from_uid(init_guess)

t, y = slv.simulate(
    t0=0,
    t_end=20.0,
    h=0.001,
    x0=x0,
    params0=params0,
    time = t,
    method="implicit_euler"
)

# save to csv
slv.save_simulation_to_csv('simulation_results_automatic_init.csv', t, y)
