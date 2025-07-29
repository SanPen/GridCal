# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pdb

import numpy as np
from matplotlib import pyplot as plt

from GridCalEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver
import GridCalEngine.api as gce

grid = gce.MultiCircuit()
bus1 = gce.Bus(name="Bus1", Vnom=10, is_slack=True)
bus2 = gce.Bus(name="Bus2", Vnom=10)

grid.add_bus(bus1)
grid.add_bus(bus2)

line = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2,
                r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=100.0)
grid.add_line(line)

gen = gce.Generator(name="Gen1", P=10, vset=1.081099313,
                    x1=0.86138701, r1=0.3, freq=50.0,
                    m_torque=0.1,
                    M=1.0,
                    D=4.0,
                    omega_ref=1.0,
                    Kp=1.0,
                    Ki=10.0,
                    Kw=10.0)
grid.add_generator(bus=bus1, api_obj=gen)

load = gce.Load(name="Load1", P=10, Q=10)
grid.add_load(bus=bus2, api_obj=load)

res = gce.power_flow(grid)


print(res.get_bus_df())
print(res.get_branch_df())
print(f"Converged: {res.converged}")

logger = gce.Logger()
grid.initialize_rms(logger=logger)
sys, mapping = grid.compose_system_block(res)




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
#x0 = slv.build_init_vars_vector(mapping)

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

#vars_in_order = slv.sort_vars(mapping)

vars_in_order = slv.sort_vars_from_uid(mapping)

t, y = slv.simulate(
    t0=0,
    t_end=10.0,
    h=0.001,
    x0=x0,
    params0=params0,
    events_list=my_events,
    method="implicit_euler"
)

# save to csv
slv.save_simulation_to_csv('simulation_results.csv', t, y)

fig = plt.figure(figsize=(14, 10))

# Generator state variables
plt.plot(t, y[:, slv.get_var_idx(omega)], label="ω (pu)")
# plt.plot(t, y[:, slv.get_var_idx(delta)], label="δ (rad)")
# plt.plot(t, y[:, slv.get_var_idx(et)], label="et (pu)")

# Generator algebraic variables
# plt.plot(t, y[:, slv.get_var_idx(tm)], label="Tm (pu)")
# plt.plot(t, y[:, slv.get_var_idx(psid)], label="Ψd (pu)")
# plt.plot(t, y[:, slv.get_var_idx(psiq)], label="Ψq (pu)")
# plt.plot(t, y[:, slv.get_var_idx(i_d)], label="Id (pu)")
# plt.plot(t, y[:, slv.get_var_idx(i_q)], label="Iq (pu)")
# plt.plot(t, y[:, slv.get_var_idx(v_d)], label="Vd (pu)")
# plt.plot(t, y[:, slv.get_var_idx(v_q)], label="Vq (pu)")
# plt.plot(t, y[:, slv.get_var_idx(t_e)], label="Te (pu)")
# plt.plot(t, y[:, slv.get_var_idx(p_g)], label="Pg (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Q_g)], label="Qg (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Vg)], label="Vg (pu)")
# plt.plot(t, y[:, slv.get_var_idx(dg)], label="θg (rad)")

# Line variables
# plt.plot(t, y[:, slv.get_var_idx(Pline_from)], label="Pline_from (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Qline_from)], label="Qline_from (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Pline_to)], label="Pline_to (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Qline_to)], label="Qline_to (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Vline_from)], label="Vline_from (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Vline_to)], label="Vline_to (pu)")
# plt.plot(t, y[:, slv.get_var_idx(dline_from)], label="δline_from (rad)")
# plt.plot(t, y[:, slv.get_var_idx(dline_to)], label="δline_to (rad)")

# Load variables
# plt.plot(t, y[:, slv.get_var_idx(Pl)], label="Pl (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Ql)], label="Ql (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.title("Time Series of All System Variables")
plt.grid(True)
plt.tight_layout()
plt.show()
