# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd


import sys
import time
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Devices.Aggregation.rms_event import RmsEvent
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
import VeraGridEngine.api as gce



# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------
# Load system
# TODO: be careful! this is _noshunt, such that the initialization it's easier because we have one device per bus. 
# In scriptin_gridcal_hardcoded there are also shunt elements!
grid_1 = gce.open_file('Two_Areas_PSS_E/Benchmark_4ger_33_2015_noshunt.raw')
# Run power flow
res_1 = gce.power_flow(grid_1)
#
# # # Print results
# print(res_1.get_bus_df())
# print(res_1.get_branch_df())
# print(f"Converged: {res_1.converged}")


# Build system

t = Var("t")

grid = gce.MultiCircuit()

# Buses
bus1 = gce.Bus(name="Bus1", Vnom=20)
bus2 = gce.Bus(name="Bus2", Vnom=20)
bus3 = gce.Bus(name="Bus3", Vnom=20)
bus4 = gce.Bus(name="Bus4", Vnom=20)
bus5 = gce.Bus(name="Bus5", Vnom=230)
bus6 = gce.Bus(name="Bus6", Vnom=230)
bus7 = gce.Bus(name="Bus7", Vnom=230)
bus8 = gce.Bus(name="Bus8", Vnom=230)
bus9 = gce.Bus(name="Bus9", Vnom=230)
bus10 = gce.Bus(name="Bus10", Vnom=230)
bus11 = gce.Bus(name="Bus11", Vnom=230)

grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus3)
grid.add_bus(bus4)
grid.add_bus(bus5)
grid.add_bus(bus6)
grid.add_bus(bus7)
grid.add_bus(bus8)
grid.add_bus(bus9)
grid.add_bus(bus10)
grid.add_bus(bus11)

# Line
line0 = grid.add_line(
    gce.Line(name="line 5-6-1", bus_from=bus5, bus_to=bus6,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0))

line1 = grid.add_line(
    gce.Line(name="line 5-6-2", bus_from=bus5, bus_to=bus6,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0))

line2 = grid.add_line(
    gce.Line(name="line 6-7-1", bus_from=bus6, bus_to=bus7,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line3 = grid.add_line(
    gce.Line(name="line 6-7-2", bus_from=bus6, bus_to=bus7,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line4 = grid.add_line(
    gce.Line(name="line 6-7-3", bus_from=bus6, bus_to=bus7,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line5 = grid.add_line(
    gce.Line(name="line 7-8-1", bus_from=bus7, bus_to=bus8,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0))

line6 = grid.add_line(
    gce.Line(name="line 7-8-2", bus_from=bus7, bus_to=bus8,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0))

line7 = grid.add_line(
    gce.Line(name="line 8-9-1", bus_from=bus8, bus_to=bus9,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0))

line8 = grid.add_line(
    gce.Line(name="line 8-9-2", bus_from=bus8, bus_to=bus9,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0))

line9 = grid.add_line(
    gce.Line(name="line 9-10-1", bus_from=bus9, bus_to=bus10,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line10 = grid.add_line(
    gce.Line(name="line 9-10-2", bus_from=bus9, bus_to=bus10,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line11 = grid.add_line(
    gce.Line(name="line 9-10-3", bus_from=bus9, bus_to=bus10,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line12 = grid.add_line(
    gce.Line(name="line 10-11-1", bus_from=bus10, bus_to=bus11,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0))

line13 = grid.add_line(
    gce.Line(name="line 10-11-2", bus_from=bus10, bus_to=bus11,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0))

# Transformers

trafo_G1 = grid.add_line(
    gce.Line(name="trafo 5-1", bus_from=bus5, bus_to=bus1,
             r=0.00000, x=0.15 * (100.0/900.0), b=0.0, rate=900.0))

trafo_G2 = grid.add_line(
    gce.Line(name="trafo 6-2", bus_from=bus6, bus_to=bus2,
             r=0.00000, x=0.15 * (100.0/900.0), b=0.0, rate=900.0))

trafo_G3 = grid.add_line(
    gce.Line(name="trafo 11-3", bus_from=bus11, bus_to=bus3,
             r=0.00000, x=0.15 * (100.0/900.0), b=0.0, rate=900.0))

trafo_G4 = grid.add_line(
    gce.Line(name="trafo 10-4", bus_from=bus10, bus_to=bus4,
             r=0.00000, x=0.15 * (100.0/900.0), b=0.0, rate=900.0))

# load
load1 = gce.Load(name="load1", P=967.0, Q=100.0, Pl0=-9.670000000007317, Ql0=-0.9999999999967969)
load1.time = t
load1_grid = grid.add_load(bus=bus7, api_obj=load1)
# load1 = grid.add_load(bus=bus7, api_obj=gce.Load(P=967.0, Q=100.0, Pl0=-9.670000000007317, Ql0=-0.9999999999967969))

load2 = gce.Load(name="load2", P=1767.0, Q=100.0, Pl0=-17.6699999999199, Ql0=-0.999999999989467)
load2.time = t
load2_grid = grid.add_load(bus=bus9, api_obj=load2)

# load2 = grid.add_load(name="load2", bus=bus9, api_obj=gce.Load(P=1767.0, Q=100.0, Pl0=-17.6699999999199, Ql0=-0.999999999989467))
#
# # Shunt at bus 7
# shunt1 = gce.Shunt(
#     name="Shunt1",
#     G=0.0,
#     B=200.0,   # MVAr at v=1 pu
#     active=True
# )
# grid.add_shunt(bus=bus7, api_obj=shunt1)
#
# # Shunt at bus 9
# shunt2 = gce.Shunt(
#     name="Shunt2",
#     G=0.0,
#     B=350.0,   # MVAr at v=1 pu
#     active=True
# )
# grid.add_shunt(bus=bus9, api_obj=shunt2)
#

# Generators
fn_1 = 60.0
M_1 = 13.0 * 9.0
D_1 = 10.0 * 9.0
ra_1 = 0.0
xd_1 = 0.3 * 100.0 / 900.0
omega_ref_1 = 1.0
Kp_1 = 0.0
Ki_1 = 0.0

fn_2 = 60.0
M_2 = 13.0 * 9.0
D_2 = 10.0 * 9.0
ra_2 = 0.0
xd_2 = 0.3 * 100.0 / 900.0
omega_ref_2 = 1.0
Kp_2 = 0.0
Ki_2 = 0.0

fn_3 = 60.0
M_3 = 12.35 * 9.0
D_3 = 10.0 * 9.0
ra_3 = 0.0
xd_3 = 0.3 * 100.0 / 900.0
omega_ref_3 = 1.0
Kp_3 = 0.0
Ki_3 = 0.0

fn_4 = 60.0
M_4 = 12.35 * 9.0
D_4 = 10.0 * 9.0
ra_4 = 0.0
xd_4 = 0.3 * 100.0 / 900.0
omega_ref_4 = 1.0
Kp_4 = 0.0
Ki_4 = 0.0

# Generators
gen1 = gce.Generator(
    name="Gen1", P=700.0, vset=1.03, Snom=900.0,
    x1=xd_1, r1=ra_1, freq=fn_1,
    # vf=1.0,
    # tm0=700.0/900.0,   # ≈ 0.7778
    tm0=6.999999999999923,
    vf=1.141048034212655,
    M=M_1, D=D_1,
    omega_ref=omega_ref_1,
    Kp=Kp_1, Ki=Ki_1
)

gen2 = gce.Generator(
    name="Gen2", P=700.0, vset=1.01, Snom=900.0,
    x1=xd_2, r1=ra_2, freq=fn_2,
    # vf=1.0,
    # tm0=700.0/900.0,   # ≈ 0.7778
    tm0=6.999999999999478,
    vf=1.180101792122771,
    M=M_2, D=D_2,
    omega_ref=omega_ref_2,
    Kp=Kp_2, Ki=Ki_2
)

gen3 = gce.Generator(
    name="Gen3", P=719.091, vset=1.03, Snom=900.0,
    x1=xd_3, r1=ra_3, freq=fn_3,
    # vf=1.0,
    # tm0=719.091/900.0,  # ≈ 0.7990
    tm0=7.331832804674334,
    vf=1.1551307366822237,
    M=M_3, D=D_3,
    omega_ref=omega_ref_3,
    Kp=Kp_3, Ki=Ki_3
)

gen4 = gce.Generator(
    name="Gen4", P=700.0, vset=1.01, Snom=900.0,
    x1=xd_4, r1=ra_4, freq=fn_4,
    # vf=1.0,
    # tm0=700.0/900.0,   # ≈ 0.7778
    tm0=6.99999999999765,
    vf=1.2028205849036708,
    M=M_4, D=D_4,
    omega_ref=omega_ref_4,
    Kp=Kp_4, Ki=Ki_4
)


grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_generator(bus=bus2, api_obj=gen2)
grid.add_generator(bus=bus3, api_obj=gen3)
grid.add_generator(bus=bus4, api_obj=gen4)

# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------

event1 = RmsEvent(load1, "Pl0", np.array([2.5, 12.5]), np.array([-9.0, -9.01]))

event2 = RmsEvent(load1, "Ql0", np.array([16.5]), np.array([-0.8]))


grid.add_rms_event(event1)
grid.add_rms_event(event2)

# # Run power flow
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

# # Print results
print(res.get_bus_df())
print(res.get_branch_df())
print(f"Converged: {res.converged}")

# ----------------------------------------------------------------------------------------------------------------------
# Time Domain Simulation
# ----------------------------------------------------------------------------------------------------------------------
# TDS initialization
ss, init_guess = gce.initialize_rms(grid, res)
print("init_guess")
print(init_guess)


params_mapping = {}

# TODO: initi_guess in hardcoded was Dict(Var, float), now it's Dict((int(uid), str(name)), float) for debugging. So slv.build_init_vars_vector(init_guess) and slv.sort_vars(init_guess) needs to be addressed
# # Solver
start_building_system = time.time()

slv = BlockSolver(ss, t)

end_building_system = time.time()
print(f"Automatic build system time = {end_building_system-start_building_system:.6f} [s]")

params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector_from_uid(init_guess)
vars_in_order = slv.sort_vars_from_uid(init_guess)

start_simulation = time.time()

t, y = slv.simulate(
    t0=0,
    t_end=20.0,
    h=0.001,
    x0=x0,
    params0=params0,
    time=t,
    method="implicit_euler"
)

end_simulation = time.time()
print(f"Automatic simulation time = {end_simulation-start_simulation:.6f} [s]")


# TODO: check results and implement test once intilize_rms is wokring!
# # Save to csv
slv.save_simulation_to_csv('simulation_results_Ieee_automatic_init.csv', t, y, csv_saving=True)

# # Plot
# plt.plot(t, y[:, slv.get_var_idx(slv._state_vars[1])], label="ω (pu)")
# plt.plot(t, y[:, slv.get_var_idx(slv._state_vars[4])], label="ω (pu)")
# plt.plot(t, y[:, slv.get_var_idx(slv._state_vars[7])], label="ω (pu)")
# plt.plot(t, y[:, slv.get_var_idx(slv._state_vars[10])], label="ω (pu)")

# plt.legend(loc='upper right', ncol=2)
# plt.xlabel("Time (s)")
# plt.ylabel("Values (pu)")
# plt.xlim([0, 20.0])
# plt.ylim([0.85, 1.15])
# plt.grid(True)
# plt.tight_layout()
# plt.show()

#stability assessment
start_stability = time.time()

stab, Eigenvalues, V, W, PF, A = slv.stability_assessment(z=x0, params=params0, plot = True)

end_stability = time.time()
print(f"Time for stability assessment = {end_stability - start_stability:.6f} [s]")

print("State matrix A:", A.toarray())
print("Stability assessment:", stab)
print("Eigenvalues:", Eigenvalues)
#print("Right eivenvectors:", V)
#print("Left eigenvectors:", W)
print("Participation factors:", PF.toarray())

df_Eig = pd.DataFrame(Eigenvalues)
df_Eig.to_csv("Eigenvalues_results.csv", index=False)