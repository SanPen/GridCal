# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pdb

import numpy as np
from matplotlib import pyplot as plt

from GridCalEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver, compose_system_block
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

res.voltage  # voltage in p.u.
res.Sf / grid.Sbase  # from power of the branches
res.St / grid.Sbase  # to power of the branches

print(res.get_bus_df())
print(res.get_branch_df())
print(f"Converged: {res.converged}")

logger = gce.Logger()
grid.initialize_rms(logger=logger)
sys = compose_system_block(grid=grid)

# sys = grid.initialize_rms(res, logger=logger)


# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = BlockSolver(sys)

pdb.set_trace()


# ----------------------------------------------------------------------------------------------------------------------
# Intialization
# ----------------------------------------------------------------------------------------------------------------------
res = gce.power_flow(grid)

print(f"Converged: {res.converged}")

# System
v1 = res.voltage[0]
v2 = res.voltage[1]

Sb1 = res.Sbus[0] / grid.Sbase
Sb2 = res.Sbus[1] / grid.Sbase
Sf = res.Sf / grid.Sbase
St = res.St / grid.Sbase

# Generator
# Current from power and voltage
i = np.conj(Sb1 / v1)  # ī = (p - jq) / v̄*
# Delta angle
delta0 = np.angle(v1 + gen.R1 + 1j * gen.X1 * i)
# dq0 rotation
rot = np.exp(-1j * (delta0 - np.pi / 2))
# dq voltages and currents
v_d0 = np.real(v1 * rot)
v_q0 = np.imag(v1 * rot)
i_d0 = np.real(i * rot)
i_q0 = np.imag(i * rot)
# inductances
psid0 = -gen.ra * i_q0 + v_q0
psiq0 = -gen.ra * i_d0 + v_d0
vf0 = - i_d0 + psid0 + gen.xd * i_d0
print(f"vf = {vf0}")

mapping = {
    dline_from: np.angle(v1),
    dline_to: np.angle(v2),
    Vline_from: np.abs(v1),
    Vline_to: np.abs(v2),
    Vg: np.abs(v1),
    dg: np.angle(v1),
    Pline_from: Sf.imag,
    Qline_from: Sf.imag,
    Pline_to: St.real,
    Qline_to: St.imag,
    Pl: Sb2.real,  # P2
    Ql: Sb2.imag,  # Q2
    delta: delta0,
    omega: 1.0,
    psid: psid0,  # d-axis flux linkage (pu)
    psiq: psiq0,  # q-axis flux linkage (pu)
    i_d: i_d0,  # d-axis stator current (pu)
    i_q: i_q0,  # q-axis stator current (pu)
    v_d: v_d0,  # d-axis voltage (pu)
    v_q: v_q0,  # q-axis voltage (pu)
    t_e: 0.1,  # electromagnetic torque (pu)
    p_g: Sb1.real,
    Q_g: Sb1.imag
}

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
x0 = slv.build_init_vars_vector(mapping)


# x0 = slv.initialize_with_newton(x0=slv.build_init_vars_vector(vars_mapping),
#                                 params0=params0)
#
x0 = slv.initialize_with_pseudo_transient_gamma(
    x0=slv.build_init_vars_vector(mapping),
    # x0=np.zeros(len(slv._state_vars) + len(slv._algebraic_vars)),
    params0=params0
)


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

vars_in_order = slv.sort_vars(mapping)

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
