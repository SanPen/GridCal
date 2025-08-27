# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from matplotlib import pyplot as plt

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from GridCalEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver
import GridCalEngine.api as gce

# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------
# Load system
# TODO: be careful! this is _noshunt, such that the initialization it's easier because we have one device per bus. 
# In scriptin_gridcal_hardcoded there are also shunt elements!
grid = gce.open_file('Two_Areas_PSS_E/Benchmark_4ger_33_2015_noshunt.raw')

res = gce.power_flow(grid)

# # Print results
print(res.get_bus_df())
print(res.get_branch_df())
print(f"Converged: {res.converged}")

#
# grid = gce.MultiCircuit()
#
# # Buses
# bus1 = gce.Bus(name="Bus1", Vnom=20)
# bus2 = gce.Bus(name="Bus2", Vnom=20)
# bus3 = gce.Bus(name="Bus3", Vnom=20)
# bus4 = gce.Bus(name="Bus4", Vnom=20)
# bus5 = gce.Bus(name="Bus5", Vnom=230)
# bus6 = gce.Bus(name="Bus6", Vnom=230)
# bus7 = gce.Bus(name="Bus7", Vnom=230)
# bus8 = gce.Bus(name="Bus8", Vnom=230)
# bus9 = gce.Bus(name="Bus9", Vnom=230)
# bus10 = gce.Bus(name="Bus10", Vnom=230)
# bus11 = gce.Bus(name="Bus11", Vnom=230)
#
# grid.add_bus(bus1)
# grid.add_bus(bus2)
# grid.add_bus(bus3)
# grid.add_bus(bus4)
# grid.add_bus(bus5)
# grid.add_bus(bus6)
# grid.add_bus(bus7)
# grid.add_bus(bus8)
# grid.add_bus(bus9)
# grid.add_bus(bus10)
# grid.add_bus(bus11)
#
# # Line
# line0 = grid.add_line(
#     gce.Line(name="line 5-6-1", bus_from=bus5, bus_to=bus6,
#              r=0.00500, x=0.05000, b=0.02187, rate=750.0))
#
# line1 = grid.add_line(
#     gce.Line(name="line 5-6-2", bus_from=bus5, bus_to=bus6,
#              r=0.00500, x=0.05000, b=0.02187, rate=750.0))
#
# line2 = grid.add_line(
#     gce.Line(name="line 6-7-1", bus_from=bus6, bus_to=bus7,
#              r=0.00300, x=0.03000, b=0.00583, rate=700.0))
#
# line3 = grid.add_line(
#     gce.Line(name="line 6-7-2", bus_from=bus6, bus_to=bus7,
#              r=0.00300, x=0.03000, b=0.00583, rate=700.0))
#
# line4 = grid.add_line(
#     gce.Line(name="line 6-7-3", bus_from=bus6, bus_to=bus7,
#              r=0.00300, x=0.03000, b=0.00583, rate=700.0))
#
# line5 = grid.add_line(
#     gce.Line(name="line 7-8-1", bus_from=bus7, bus_to=bus8,
#              r=0.01100, x=0.11000, b=0.19250, rate=400.0))
#
# line6 = grid.add_line(
#     gce.Line(name="line 7-8-2", bus_from=bus7, bus_to=bus8,
#              r=0.01100, x=0.11000, b=0.19250, rate=400.0))
#
# line7 = grid.add_line(
#     gce.Line(name="line 8-9-1", bus_from=bus8, bus_to=bus9,
#              r=0.01100, x=0.11000, b=0.19250, rate=400.0))
#
# line8 = grid.add_line(
#     gce.Line(name="line 8-9-2", bus_from=bus8, bus_to=bus9,
#              r=0.01100, x=0.11000, b=0.19250, rate=400.0))
#
# line9 = grid.add_line(
#     gce.Line(name="line 9-10-1", bus_from=bus9, bus_to=bus10,
#              r=0.00300, x=0.03000, b=0.00583, rate=700.0))
#
# line10 = grid.add_line(
#     gce.Line(name="line 9-10-2", bus_from=bus9, bus_to=bus10,
#              r=0.00300, x=0.03000, b=0.00583, rate=700.0))
#
# line11 = grid.add_line(
#     gce.Line(name="line 9-10-3", bus_from=bus9, bus_to=bus10,
#              r=0.00300, x=0.03000, b=0.00583, rate=700.0))
#
# line12 = grid.add_line(
#     gce.Line(name="line 10-11-1", bus_from=bus10, bus_to=bus11,
#              r=0.00500, x=0.05000, b=0.02187, rate=750.0))
#
# line13 = grid.add_line(
#     gce.Line(name="line 10-11-2", bus_from=bus10, bus_to=bus11,
#              r=0.00500, x=0.05000, b=0.02187, rate=750.0))
#
# # Transformers
#
# trafo_G1 = grid.add_line(
#     gce.Line(name="trafo 5-1", bus_from=bus5, bus_to=bus1,
#              r=0.00000, x=0.15000, b=0.0, rate=900.0))
#
# trafo_G2 = grid.add_line(
#     gce.Line(name="trafo 6-2", bus_from=bus6, bus_to=bus2,
#              r=0.00000, x=0.15000, b=0.0, rate=900.0))
#
# trafo_G3 = grid.add_line(
#     gce.Line(name="trafo 11-3", bus_from=bus11, bus_to=bus3,
#              r=0.00000, x=0.15000, b=0.0, rate=900.0))
#
# trafo_G4 = grid.add_line(
#     gce.Line(name="trafo 10-4", bus_from=bus10, bus_to=bus4,
#              r=0.00000, x=0.15000, b=0.0, rate=900.0))
#
# # load
# load1 = grid.add_load(bus=bus7, api_obj=gce.Load(P=967.0, Q=100.0))
#
# load2 = grid.add_load(bus=bus9, api_obj=gce.Load(P=1767.0, Q=100.0))
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
#
# # Generators
# gen1 = gce.Generator(
#     name="Gen1", P=700.0, vset=1.03, Snom=900.0,
#     x1=0.0333333, r1=0.0, freq=60.0,
#     vf=1.0,
#     tm0=700.0/900.0,   # ≈ 0.7778
#     M=117.0, D=90.0,
#     omega_ref=1.0,
#     Kp=0.0, Ki=0.0
# )
#
# gen2 = gce.Generator(
#     name="Gen2", P=700.0, vset=1.01, Snom=900.0,
#     x1=0.0333333, r1=0.0, freq=60.0,
#     vf=1.0,
#     tm0=700.0/900.0,   # ≈ 0.7778
#     M=117.0, D=90.0,
#     omega_ref=1.0,
#     Kp=0.0, Ki=0.0
# )
#
# gen3 = gce.Generator(
#     name="Gen3", P=719.091, vset=1.03, Snom=900.0,
#     x1=0.0333333, r1=0.0, freq=60.0,
#     vf=1.0,
#     tm0=719.091/900.0,  # ≈ 0.7990
#     M=111.15, D=90.0,
#     omega_ref=1.0,
#     Kp=0.0, Ki=0.0
# )
#
# gen4 = gce.Generator(
#     name="Gen4", P=700.0, vset=1.01, Snom=900.0,
#     x1=0.0333333, r1=0.0, freq=60.0,
#     vf=1.0,
#     tm0=700.0/900.0,   # ≈ 0.7778
#     M=111.15, D=90.0,
#     omega_ref=1.0,
#     Kp=0.0, Ki=0.0
# )
#
#
# grid.add_generator(bus=bus1, api_obj=gen1)
# grid.add_generator(bus=bus2, api_obj=gen2)
# grid.add_generator(bus=bus3, api_obj=gen3)
# grid.add_generator(bus=bus4, api_obj=gen4)
# # # Run power flow
# res = gce.power_flow(grid)
#
# # # Print results
# print(res.get_bus_df())
# print(res.get_branch_df())
# print(f"Converged: {res.converged}")

# ----------------------------------------------------------------------------------------------------------------------
# Time Domain Simulation
# ----------------------------------------------------------------------------------------------------------------------
# TDS initialization
ss, init_guess = gce.initialize_rms(grid, res)
print("init_guess")
print(init_guess)

# TODO: events definition and access to variable still needs to be addressed

# # # Events
# event1 = RmsEvent('Load', Pl0_7, 2500, -9.0)
# event1 = RmsEvent('Load', grid.lines[7].rms_model.model.V('Pl07'), 2500, -9.0)
my_events = RmsEvents([])
# params_mapping = {
#     # Pl0_7: Sb7.real + Ps0_7.value
# }
params_mapping = {}

# TODO: initi_guess in hardcoded was Dict(Var, float), now it's Dict((int(uid), str(name)), float) for debugging. So slv.build_init_vars_vector(init_guess) and slv.sort_vars(init_guess) needs to be addressed
# # Solver
slv = BlockSolver(ss)
params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector_from_uid(init_guess)
vars_in_order = slv.sort_vars_from_uid(init_guess)

t, y = slv.simulate(
    t0=0,
    t_end=20.0,
    h=0.001,
    x0=x0,
    params0=params0,
    events_list=my_events,
    method="implicit_euler"
)

# TODO: check results and implement test once intilize_rms is wokring!
# # Save to csv
slv.save_simulation_to_csv('simulation_results_Ieee_automatic_init.csv', t, y)

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
