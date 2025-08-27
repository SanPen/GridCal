# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math

import numpy as np
from matplotlib import pyplot as plt

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# from VeraGridEngine.Utils.Symbolic.events import Events, Event
from VeraGridEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
import VeraGridEngine.api as gce

# ----------------------------------------------------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------------------------------------------------
pi = Const(math.pi)
fn = Const(50)
M = Const(10.0)
D = Const(1.0)
ra = Const(0.3)
xd = Const(0.86138701)
vf = Const(1.081099313)
tm0 = Const(0.0)

omega_ref = Const(1)
Kp = Const(1.0)
Ki = Const(10.0)

g = Const(5)
b = Const(-12)
bsh = Const(0.03)

# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------

grid = gce.MultiCircuit()

# Buses
bus1 = gce.Bus(name="Bus1", Vnom=10, is_slack=True)
bus2 = gce.Bus(name="Bus2", Vnom=10)

grid.add_bus(bus1)
grid.add_bus(bus2)


# Line
line0 = grid.add_line(gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0))


# load
load_grid = grid.add_load(bus=bus2, api_obj=gce.Load(P= -10, Q= -10))

# Generators
gen1 = gce.Generator(name="Gen1", P=10, vset=1.0, Snom=900,
                     x1=0.86138701, r1=0.3, freq=50.0,
                     vf=1.093704253855166,
                     tm0=0.10508619605291579,
                     M=10.0,
                     D=1.0,
                     omega_ref=1.0,
                     Kp=1.0,
                     Ki=10.0
                     )

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
print(res.get_branch_df())

# System

# Voltages*
v1 = res.voltage[0]
v2 = res.voltage[1]

Sb1 = res.Sbus[0] / grid.Sbase
Sb2 = res.Sbus[1] / grid.Sbase
Sf = res.Sf / grid.Sbase
St = res.St / grid.Sbase

# Generator
# Current from power and voltage*
i = np.conj(Sb1 / v1)          # ī = (p - jq) / v̄* 
# Delta angle *****
delta0 = np.angle(v1 + (ra.value + 1j*xd.value) * i)
# dq0 rotation*
rot = np.exp(-1j * (delta0 - np.pi/2))
# dq voltages and currents*
v_d0 = np.real(v1*rot)
v_q0 = np.imag(v1*rot)
i_d0 = np.real(i*rot)
i_q0 = np.imag(i*rot)
# inductances *
psid0 = ra.value * i_q0 + v_q0
psiq0 = -ra.value * i_d0 - v_d0

te0 = psid0 * i_q0 - psiq0 * i_d0 
vf0 = psid0 + xd.value * i_d0

print("vf0")
print(vf0)

# ----------------------------------------------------------------------------------------------------------------------
tm0 = Const(te0)
print("tm0")
print(tm0)

Pl0 = Const(Sb2.real)
Ql0 = Const(Sb2.imag)
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

load_block = Block(
    algebraic_eqs=[
        Pl - Pl0,
        Ql - Ql0
    ],
    algebraic_vars=[Ql, Pl],
    parameters=[]
)

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
P_g = Var("P_g")
Q_g = Var("Q_g")
Vg = Var("Vg")
dg = Var("dg")
tm = Var("tm")
et = Var("et")

generator_block = Block(
    state_eqs=[
        (2 * pi * fn) * (omega - omega_ref),  # dδ/dt
        (tm  - t_e - D * (omega - omega_ref)) / M,  # dω/dt
        (omega - omega_ref)
    ],
    state_vars=[delta, omega, et], # , et
    algebraic_eqs=[
        psid - (ra * i_q + v_q),
        psiq + (ra * i_d + v_d),
        0 - (psid + xd * i_d - vf),
        0 - (psiq + xd * i_q),
        v_d - (Vg * sin(delta - dg)),
        v_q - (Vg * cos(delta - dg)),
        t_e - (psid * i_q - psiq * i_d),
        P_g - (v_d * i_d + v_q * i_q),
        Q_g - (v_q * i_d - v_d * i_q),
        tm - (tm0 + Kp * (omega - omega_ref) + Ki * et),
    ],
    algebraic_vars=[psid, psiq, i_d, i_q, v_d, v_q, t_e, P_g, Q_g, tm], #, tm
    parameters=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------

bus1_block = Block(
    algebraic_eqs=[
        P_g - Pline_from,
        Q_g - Qline_from,
        Vg - Vline_from,
        dg - dline_from
    ],
    algebraic_vars=[Pline_from, Qline_from, Vg, dg]
)

bus2_block = Block(
    algebraic_eqs=[
        Pl - Pline_to,
        Ql - Qline_to,
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

params_mapping = {}

vars_mapping = {
    dline_from: np.angle(v1),
    dline_to: np.angle(v2),
    Vline_from: np.abs(v1),
    Vline_to: np.abs(v2),
    Vg: np.abs(v1),
    dg: np.angle(v1),
    Pline_from: Sf.real,
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
    t_e: te0,  # electromagnetic torque (pu)
    P_g: Sb1.real,
    Q_g: Sb1.imag,
    tm: te0,
    et: 0.0
}
print(vars_mapping)
# Consistency check 
residuals = {
    "f1: (2 * pi * fn) * (omega - omega_ref)": (2 * pi.value * fn.value) * (1.0 - omega_ref.value),
    "f2: (tm - t_e - D * (omega - omega_ref)) / M": (te0 - te0 - D.value * (1.0 - omega_ref.value)) / M.value,
    "g1: psid - (-ra * i_q + v_q)": psid0 - (ra.value * i_q0 + v_q0),
    "g2: psiq - (-ra * i_d + v_d)": psiq0 + (ra.value * i_d0 + v_d0),
    "g3: 0 - (psid + xd * i_d - vf)": 0 - (psid0 + xd.value * i_d0 - vf0),
    "g4: 0 - (psiq + xd * i_q)": 0 - (psiq0 + xd.value * i_q0),
    "g5: v_d - (Vg * sin(delta - dg))": v_d0 - (np.abs(v1) * np.sin(delta0 - np.angle(v1))),
    "g6: v_q - (Vg * cos(delta - dg))": v_q0 - (np.abs(v1) * np.cos(delta0 - np.angle(v1))),
    "g7: t_e - (psid * i_q - psiq * i_d)": te0 - (psid0 * i_q0 - psiq0 * i_d0),
    "g8: (v_d * i_d + v_q * i_q) - p_g": (v_d0 * i_d0 + v_q0 * i_q0) - Sb1.real,
    "g9: (v_q * i_d - v_d * i_q) - Q_g": (v_q0 * i_d0 - v_d0 * i_q0) - Sb1.imag,
    "g10: P_g - Pline_from": Sb1.real - Sf[0].real,
    "g11: Q_g - Qline_from": Sb1.imag - Sf[0].imag,
    "g14: Pl - Pline_to": Sb2.real - St[0].real,
    "g15: Ql - Qline_to": Sb2.imag - St[0].imag,
    "g16: Pl - Pl0": Sb2.real - Sb2.real,
    "g17: Ql - Ql0": Sb2.imag - Ql0.value
}

# Print results
print("\n🔍 Residuals of generator algebraic equations:\n")
for eq, val in residuals.items():
    print(f"{eq:55} = {val:.3e}")

# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------

event1 = RmsEvent('Load', Pl0, 2500, 0.15)
#event2 = Event(Ql0, 5000, 0.3)
my_events = RmsEvents([])

params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector(vars_mapping)
print("x0")
print(x0)



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
plt.plot(t, y[:, slv.get_var_idx(omega)], label="ω (pu)", color='red')
# plt.plot(t, y[:, slv.get_var_idx(dline_from)], label="dline_from (pu)", color='blue')
# plt.plot(t, y[:, slv.get_var_idx(dline_to)], label="dline_to (pu)", color='green')
# plt.plot(t, y[:, slv.get_var_idx(Vline_from)], label="Vline_from (pu)", color='black')
# plt.plot(t, y[:, slv.get_var_idx(Vline_to)], label="Vline_topu)", color='orange')

# plt.plot(t, y[:, slv.get_var_idx(t_e)], label="Te (pu)")
#plt.plot(t, y[:, slv.get_var_idx(delta)], label="δ (rad)")
#plt.plot(t, y[:, slv.get_var_idx(et)], label="et (pu)")

#Generator algebraic variables
# plt.plot(t, y[:, slv.get_var_idx(tm)], label="Tm (pu)")
#plt.plot(t, y[:, slv.get_var_idx(psid)], label="Ψd (pu)")
#plt.plot(t, y[:, slv.get_var_idx(psiq)], label="Ψq (pu)")
#plt.plot(t, y[:, slv.get_var_idx(i_d)], label="Id (pu)")
#plt.plot(t, y[:, slv.get_var_idx(i_q)], label="Iq (pu)")
#plt.plot(t, y[:, slv.get_var_idx(v_d)], label="Vd (pu)")
#plt.plot(t, y[:, slv.get_var_idx(v_q)], label="Vq (pu)")
#plt.plot(t, y[:, slv.get_var_idx(t_e)], label="Te (pu)")
#plt.plot(t, y[:, slv.get_var_idx(p_g)], label="Pg (pu)")
#plt.plot(t, y[:, slv.get_var_idx(Q_g)], label="Qg (pu)")
#plt.plot(t, y[:, slv.get_var_idx(Vg)], label="Vg (pu)")
#plt.plot(t, y[:, slv.get_var_idx(dg)], label="θg (rad)")

#Line variables
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
plt.title("Small System: Control Proof")
# plt.xlim(0, 10)
# plt.ylim(0.85, 1.15)
plt.grid(True)
plt.tight_layout()
plt.show()
