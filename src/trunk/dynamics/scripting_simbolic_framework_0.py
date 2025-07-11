# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import pdb

import numpy as np
from matplotlib import pyplot as plt

from GridCalEngine.Utils.Symbolic.events import Events, Event
from GridCalEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from GridCalEngine.Utils.Symbolic.block import Block
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver
import GridCalEngine.api as gce

grid = gce.MultiCircuit()
bus1 = gce.Bus(name="Bus1", Vnom=10)
bus2 = gce.Bus(name="Bus2", Vnom=10)

grid.add_bus(bus1)
grid.add_bus(bus2)

line = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2,
                r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=100.0)
grid.add_line(line)

gen = gce.Generator(name="Gen1", P=10, vset=1.0)
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

# ----------------------------------------------------------------------------------------------------------------------
# Line
# ----------------------------------------------------------------------------------------------------------------------
Qline_from = Var("Qline_from")
Qline_to = Var("Qline_to")
Pline_from = Var("Pline_from")
Pline_to = Var("Pline_to")
Vline_from = Var("Vline_from")
Vline_to = Var("Vline_to")
dline_from = Var("dline_from")
dline_to = Var("dline_to")

g = Const(5)
b = Const(-12)
bsh = Const(0.03)

line_block = Block(
    algebraic_eqs=[
        Pline_from - ((Vline_from ** 2 * g) - g * Vline_from * Vline_to * cos(
            dline_from - dline_to) + b * Vline_from * Vline_to * cos(dline_from - dline_to + np.pi / 2)),
        Qline_from - (Vline_from ** 2 * (-bsh / 2 - b) - g * Vline_from * Vline_to * sin(
            dline_from - dline_to) + b * Vline_from * Vline_to * sin(dline_from - dline_to + np.pi / 2)),
        Pline_to - ((Vline_to ** 2 * g) - g * Vline_to * Vline_from * cos(
            dline_to - dline_from) + b * Vline_to * Vline_from * cos(dline_to - dline_from + np.pi / 2)),
        Qline_to - (Vline_to ** 2 * (-bsh / 2 - b) - g * Vline_to * Vline_from * sin(
            dline_to - dline_from) + b * Vline_to * Vline_from * sin(dline_to - dline_from + np.pi / 2)),
    ],
    algebraic_vars=[dline_from, Vline_from, dline_to, Vline_to],
    parameters=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------

Ql = Var("Ql")
Pl = Var("Pl")

coeff_alfa = Const(1.8)
Pl0 = Var('Pl0')
Ql0 = Const(0.1)
coeff_beta = Const(8.0)

load_block = Block(
    algebraic_eqs=[
        Pl - Pl0,
        Ql - Ql0
    ],
    algebraic_vars=[Ql, Pl],
    parameters=[Pl0]
)
#
# # ----------------------------------------------------------------------------------------------------------------------
# # Slack
# # ----------------------------------------------------------------------------------------------------------------------
#
# # Constants (parameters for the slack generator)
# fn = Const(50)           # nominal frequency (Hz)
# ra = Const(0.3)          # armature resistance
# xd = Const(0.86138701)   # d-axis reactance
#
# # Slack parameters
# theta_0 = Const(0.0) # Reference angle set point
# p_min = Const(-999.0) # Minimum active power
# p_max = Const(-999.0) # Maximum active power
#
# # Variables (algebraic)
# delta = Var("delta")     # voltage angle (set to theta_0)
# omega = Var("omega")     # frequency (set to 1.0)
# p_g = Var("p_g")         # active power output
# Q_g = Var("Q_g")         # reactive power output (free)
#
# # Slack algebraic equations
# algebraic_eqs = [
#     delta - theta_0,          # Fix voltage angle to reference
#     omega - 1.0,              # Fixed frequency at nominal
#     p_g - p_g,                # p_g free within limits
# ]
#
# # Power limits (enforced externally or in solver)
# power_limits = {
#     'p_min': p_min,
#     'p_max': p_max,
# }
#



# ----------------------------------------------------------------------------------------------------------------------
# Generator
# ----------------------------------------------------------------------------------------------------------------------

delta = Var("delta")
omega = Var("omega")
psid = Var("psid")
psiq = Var("psiq")
i_d = Var("i_d")
i_q = Var("i_q")
v_d = Var("v_d")
v_q = Var("v_q")
t_e = Var("t_e")
p_g = Var("P_e")
Q_g = Var("Q_e")
Vg = Var("Vg")
dg = Var("dg")
tm = Var("tm")
et = Var("et")

pi = Const(math.pi)
fn = Const(50)
# tm = Const(0.1)
M = Const(1.0)
D = Const(100)
ra = Const(0.3)
xd = Const(0.86138701)
vf = Const(1.081099313)

Kp = Const(1.0)
Ki = Const(10.0)
Kw = Const(10.0)

generator_block = Block(
    state_eqs=[
        # delta - (2 * pi * fn) * (omega - 1),
        # omega - (-tm / M + t_e / M - D / M * (omega - 1))
        (2 * pi * fn) * (omega - 1),  # dδ/dt
        (tm - t_e - D * (omega - 1)) / M,  # dω/dt
        -Kp * et - Ki * et - Kw * (omega - 1)  # det/dt
    ],
    state_vars=[delta, omega, et],
    algebraic_eqs=[
        et - (tm - t_e),
        psid - (-ra * i_q + v_q),
        psiq - (-ra * i_d + v_d),
        i_d - (psid + xd * i_d - vf),
        i_q - (psiq + xd * i_q),
        v_d - (Vg * sin(delta - dg)),
        v_q - (Vg * cos(delta - dg)),
        t_e - (psid * i_q - psiq * i_d),
        (v_d * i_d + v_q * i_q) - p_g,
        (v_q * i_d - v_d * i_q) - Q_g
    ],
    algebraic_vars=[tm, psid, psiq, i_d, i_q, v_d, v_q, t_e, p_g, Q_g],
    parameters=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------

bus1_block = Block(
    algebraic_eqs=[
        p_g - Pline_from,
        Q_g - Qline_from,
        Vg - Vline_from,
        dg - dline_from
    ],
    algebraic_vars=[Pline_from, Qline_from, Vg, dg]
)

bus2_block = Block(
    algebraic_eqs=[
        Pl + Pline_to,
        Ql + Qline_to,
    ],
    algebraic_vars=[Pline_to, Qline_to]
)

# ----------------------------------------------------------------------------------------------------------------------
# System
# ----------------------------------------------------------------------------------------------------------------------

sys = Block(
    children=[line_block, load_block, generator_block, bus1_block, bus2_block],
    in_vars=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = BlockSolver(sys)

params_mapping = {
    Pl0: 0.1,
    #Ql0: 0.1
}
vars_mapping = {

    # start from PF values
    # dline_from: 15 * (np.pi / 180),
    # dline_to: 10 * (np.pi / 180),
    # Vline_from: 1.0,
    # Vline_to: 0.95,
    # Vg: 1.0,
    # dg: 15 * (np.pi / 180),
    # Pline_from: 0.1,
    # Qline_from: 0.2,
    # Pline_to: -0.1,
    # Qline_to: -0.2,

    # Flat start
    dline_from: 0.0,
    dline_to: 0.0,
    Vline_from: 1.0,
    Vline_to: 1.0,
    Vg: 1.0,
    dg: 0.0,
    Pline_from: 0.0,
    Qline_from: 0.0,
    Pline_to: 0.0,
    Qline_to: 0.0,

    Pl: 0.1,  # P2
    Ql: 0.2,  # Q2
    delta: 0.5,
    omega: 1.001,
    psid: 3.825,  # d-axis flux linkage (pu)
    psiq: 0.0277,  # q-axis flux linkage (pu)
    i_d: 0.1,  # d-axis stator current (pu)
    i_q: 0.2,  # q-axis stator current (pu)
    v_d: -0.2588,  # d-axis voltage (pu)
    v_q: 0.9659,  # q-axis voltage (pu)
    t_e: 0.1,  # electromagnetic torque (pu)
    p_g: 0.1673,
    Q_g: 0.1484
}

# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------

event1 = Event(Pl0, 5000, 0.3)
#event2 = Event(Ql0, 5000, 0.3)

my_events = Events([event1])

params0 = slv.build_init_params_vector(params_mapping)
# x0 = slv.build_init_vars_vector(vars_mapping)


# x0 = slv.initialize_with_newton(x0=slv.build_init_vars_vector(vars_mapping),
#                                 params0=params0)

x0 = slv.initialize_with_pseudo_transient_gamma(
    x0=slv.build_init_vars_vector(vars_mapping),
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

vars_in_order = slv.sort_vars(vars_mapping)

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

#Generator state variables
plt.plot(t, y[:, slv.get_var_idx(omega)], label="ω (pu)")
plt.plot(t, y[:, slv.get_var_idx(delta)], label="δ (rad)")
plt.plot(t, y[:, slv.get_var_idx(et)], label="et (pu)")

#Generator algebraic variables
plt.plot(t, y[:, slv.get_var_idx(tm)], label="Tm (pu)")
plt.plot(t, y[:, slv.get_var_idx(psid)], label="Ψd (pu)")
plt.plot(t, y[:, slv.get_var_idx(psiq)], label="Ψq (pu)")
plt.plot(t, y[:, slv.get_var_idx(i_d)], label="Id (pu)")
plt.plot(t, y[:, slv.get_var_idx(i_q)], label="Iq (pu)")
plt.plot(t, y[:, slv.get_var_idx(v_d)], label="Vd (pu)")
plt.plot(t, y[:, slv.get_var_idx(v_q)], label="Vq (pu)")
plt.plot(t, y[:, slv.get_var_idx(t_e)], label="Te (pu)")
plt.plot(t, y[:, slv.get_var_idx(p_g)], label="Pg (pu)")
plt.plot(t, y[:, slv.get_var_idx(Q_g)], label="Qg (pu)")
plt.plot(t, y[:, slv.get_var_idx(Vg)], label="Vg (pu)")
plt.plot(t, y[:, slv.get_var_idx(dg)], label="θg (rad)")

#Line variables
plt.plot(t, y[:, slv.get_var_idx(Pline_from)], label="Pline_from (pu)")
plt.plot(t, y[:, slv.get_var_idx(Qline_from)], label="Qline_from (pu)")
plt.plot(t, y[:, slv.get_var_idx(Pline_to)], label="Pline_to (pu)")
plt.plot(t, y[:, slv.get_var_idx(Qline_to)], label="Qline_to (pu)")
plt.plot(t, y[:, slv.get_var_idx(Vline_from)], label="Vline_from (pu)")
plt.plot(t, y[:, slv.get_var_idx(Vline_to)], label="Vline_to (pu)")
plt.plot(t, y[:, slv.get_var_idx(dline_from)], label="δline_from (rad)")
plt.plot(t, y[:, slv.get_var_idx(dline_to)], label="δline_to (rad)")

# Load variables
plt.plot(t, y[:, slv.get_var_idx(Pl)], label="Pl (pu)")
plt.plot(t, y[:, slv.get_var_idx(Ql)], label="Ql (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.title("Time Series of All System Variables")
plt.grid(True)
plt.tight_layout()
plt.show()
