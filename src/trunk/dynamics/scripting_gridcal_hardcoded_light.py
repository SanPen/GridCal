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
grid = gce.open_file('src/trunk/dynamics/Two_Areas_PSS_E/Benchmark_4ger_33_2015_noshunt.raw')
# Run power flow
res = gce.power_flow(grid)

# ----------------------------------------------------------------------------------------------------------------------
# Time Domain Simulation
# ----------------------------------------------------------------------------------------------------------------------
# TDS initialization
ss, init_guess = grid.initialize_rms(res)

# TODO: events definition and access to variable still needs to be addressed

# # # Events
# event1 = RmsEvent('Load', Pl0_7, 2500, -9.0)
# event1 = RmsEvent('Load', grid.lines[7].rms_model.model.V('Pl07'), 2500, -9.0)
# my_events = RmsEvents([])
# params_mapping = {
#     # Pl0_7: Sb7.real + Ps0_7.value
# }

# TODO: initi_guess in hardcoded was Dict(Var, float), now it's Dict((int(uid), str(name)), float) for debugging. So slv.build_init_vars_vector(init_guess) and slv.sort_vars(init_guess) needs to be addressed
# # Solver
# slv = BlockSolver(ss)
# params0 = slv.build_init_params_vector(params_mapping)
# x0 = slv.build_init_vars_vector(init_guess)
# vars_in_order = slv.sort_vars(init_guess)

# t, y = slv.simulate(
#     t0=0,
#     t_end=20.0,
#     h=0.001,
#     x0=x0,
#     params0=params0,
#     events_list=my_events,
#     method="implicit_euler"
# )

# TODO: check results and implement test once intilize_rms is wokring!
# # Save to csv
# slv.save_simulation_to_csv('simulation_results.csv', t, y)

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
