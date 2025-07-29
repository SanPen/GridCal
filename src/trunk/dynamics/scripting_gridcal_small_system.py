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
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver #compose_system_block
import GridCalEngine.api as gce

# In this script a small system in build with a Generator a Load and a line. Generator is connected to bus 1 and Load is connected to bus 2.
# The system is uncontrolled and there are no events applyed.

# ----------------------------------------------------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------------------------------------------------
# line
g_0 = Const(5)
b_0 = Const(-12)
bsh_0 = Const(0.03)


pi = Const(math.pi)

# Generator
fn = Const(50.0)
M = Const(1.0)
D = Const(1.0)
ra = Const(0.3)
xd = Const(0.86138701)

omega_ref = Const(1.0)
Kp = Const(1.0)
Ki = Const(10.0)
Kw = Const(10.0)

# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------
# Build the system to compute the powerflow
grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus1 = gce.Bus(name="Bus1", Vnom=10, is_slack=True)
bus2 = gce.Bus(name="Bus2", Vnom=10)
grid.add_bus(bus1)
grid.add_bus(bus2)

# Line
line = grid.add_line(gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=100.0))

# load
load_grid = grid.add_load(bus=bus2, api_obj=gce.Load(P= 10, Q= 10))

# Generators
gen1 = gce.Generator(name="Gen1", P=10, vset=1.0, Snom = 900)
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



# ----------------------------------------------------------------------------------------------------------------------
# Intialization
# ----------------------------------------------------------------------------------------------------------------------
v1 = res.voltage[0]
v2 = res.voltage[1]

Sb1 = res.Sbus[0] / grid.Sbase
Sb2 = res.Sbus[1] / grid.Sbase

Sf = res.Sf / grid.Sbase
St = res.St / grid.Sbase

Pf0 = Sf[0].real
Qf0 = Sf[0].imag
Pt0 = St[0].real
Qt0 = St[0].imag

# Generator
# Current from power and voltage
i1 = np.conj(Sb1 / v1)  # ī = (p - jq) / v̄*
i2 = np.conj(Sb2 / v2)  # ī = (p - jq) / v̄*

# Delta angle
delta0 = np.angle(v1 + (ra.value + 1j * xd.value) * i1)

# dq0 rotation
rot = np.exp(-1j * (delta0 - np.pi / 2))

# dq voltages and currents
v_d0 = np.real(v1 * rot)
v_q0 = np.imag(v1 * rot)
i_d0 = np.real(i1 * rot)
i_q0 = np.imag(i1 * rot)

# inductances
psid0 = ra.value * i_q0 + v_q0
psiq0 = -ra.value * i_d0 - v_d0
vf0 = psid0 + xd.value * i_d0
t_e0 = psid0 * i_q0 - psiq0 * i_d0

# ----------------------------------------------------------------------------------------------------------------------
tm0 = Const(t_e0)
vf = Const(vf0)
tm = Const(t_e0)
# ----------------------------------------------------------------------------------------------------------------------

# Line 0
Pline_to = Var("Pline_to")
Qline_to = Var("Qline_to")
Pline_from = Var("Pline_from")
Qline_from = Var("Qline_from")
Vline_to = Var("Vline_to")
dline_to = Var("dline_to")
Vline_from = Var("Vline_from")
dline_from = Var("dline_from")

# Gencls 1
delta = Var("delta")
omega = Var("omega")
psid = Var("psid")
psiq = Var("psiq")
i_d = Var("i_d")
i_q = Var("i_q")
v_d = Var("v_d")
v_q = Var("v_q")
t_e = Var("t_e")
P_g = Var("P_e")
Q_g = Var("Q_e")
dg = Var("dg")

Vg = Var("Vg")

# Load
Pl = Var("Pl")
Ql = Var("Ql")

# -----------------------------------------------------
# Buses
# -----------------------------------------------------

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
        - Pline_to + Pl,
        - Qline_to + Ql
    ],
    algebraic_vars=[Pline_to, Qline_to]
)

# -----------------------------------------------------------------------------------
# Lines
# -----------------------------------------------------------------------------------

line_block = Block(
    algebraic_eqs=[
        Pline_from - ((Vline_from ** 2 * g_0) - g_0 * Vline_from * Vline_to * cos(
            dline_from - dline_to) + b_0 * Vline_from * Vline_to * cos(dline_from - dline_to + np.pi / 2)),
        Qline_from - (Vline_from ** 2 * (-bsh_0 / 2 - b_0) - g_0 * Vline_from * Vline_to * sin(
            dline_from - dline_to) + b_0 * Vline_from * Vline_to * sin(dline_from - dline_to + np.pi / 2)),
        Pline_to - ((Vline_to ** 2 * g_0) - g_0 * Vline_to * Vline_from * cos(
            dline_to - dline_from) + b_0 * Vline_to * Vline_from * cos(dline_to - dline_from + np.pi / 2)),
        Qline_to - (Vline_to ** 2 * (-bsh_0 / 2 - b_0) - g_0 * Vline_to * Vline_from * sin(
            dline_to - dline_from) + b_0 * Vline_to * Vline_from * sin(dline_to - dline_from + np.pi / 2)),
    ],
    algebraic_vars=[dline_from, Vline_from, dline_to, Vline_to],
    parameters=[]
)

# --------------------------------------------------------------------------
# Generators
# --------------------------------------------------------------------------

generator_block = Block(
    state_eqs=[
        (2 * pi * fn) * (omega - omega_ref),
        (tm - t_e - D * (omega - omega_ref)) / M,

    ],
    state_vars=[delta, omega],
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

    ],
    algebraic_vars=[psid, psiq, i_d, i_q, v_d, v_q, t_e, P_g, Q_g],
    parameters=[]
)

# -------------------------------------------------------------
# Load
# -------------------------------------------------------------
Pl0 = Const(Sb2.real)
Ql0 = Const(Sb2.imag)

load = Block(
    algebraic_eqs=[
        Pl - Pl0,
        Ql - Ql0
    ],
    algebraic_vars=[Ql, Pl],
    parameters=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# System
# ----------------------------------------------------------------------------------------------------------------------
sys = Block(
    children=[line_block, load, generator_block, bus1_block, bus2_block],
    in_vars=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = BlockSolver(sys)

params_mapping = {
    #Pl0_7: Sb7.real,
    # Ql0: 0.1
}

vars_mapping = {

    dline_from: np.angle(v1),
    dline_to: np.angle(v2),
    Vline_from: np.abs(v1),
    Vline_to: np.abs(v2),

    Pline_from: Pf0,
    Qline_from: Qf0,
    Pline_to: Pt0,
    Qline_to: Qt0,

    Pl: Sb2.real,  # P2
    Ql: Sb2.imag,  # Q2

    Vg: np.abs(v1),
    dg: np.angle(v1),
    delta: delta0,
    omega: omega_ref.value,
    psid: psid0,
    psiq: psiq0,
    i_d: i_d0,
    i_q: i_q0,
    v_d: v_d0,
    v_q: v_q0,
    t_e: t_e0,
    P_g: Sb1.real,
    Q_g: Sb1.imag,

}

residuals = {
    "f1: (2 * pi * fn) * (omega - omega_ref)": (2 * pi.value * fn.value) * (1.0 - omega_ref.value),
    "f2: (tm - t_e - D * (omega - omega_ref)) / M": (t_e0 - t_e0 - D.value * (
            1.0 - omega_ref.value)) / M.value,
    "g1: psid - (-ra * i_q + v_q)": psid0 - (ra.value * i_q0 + v_q0),
    "g2: psiq - (-ra * i_d + v_d)": psiq0 + (ra.value * i_d0 + v_d0),
    "g3: 0 - (psid + xd * i_d - vf)": 0 - (psid0 + xd.value * i_d0 - vf0),
    "g4: 0 - (psiq + xd * i_q)": 0 - (psiq0 + xd.value * i_q0),
    "g5: v_d - (Vg * sin(delta - dg))": v_d0 - (np.abs(v1) * np.sin(delta0 - np.angle(v1))),
    "g6: v_q - (Vg * cos(delta - dg))": v_q0 - (np.abs(v1) * np.cos(delta0 - np.angle(v1))),
    "g7: t_e - (psid * i_q - psiq * i_d)": t_e0 - (psid0 * i_q0 - psiq0 * i_d0),
    "g8: (v_d * i_d + v_q * i_q) - p_g": (v_d0 * i_d0 + v_q0 * i_q0) - Sb1.real,
    "g9: (v_q * i_d - v_d * i_q) - Q_g": (v_q0 * i_d0 - v_d0 * i_q0) - Sb1.imag,
    "bus 1 P": Sb1.real - Pf0,
    "bus 1 Q": Sb1.imag - Qf0,
    "bus 2 P": Sb2.real - Pt0,
    "bus 2 Q": Sb2.imag - Qt0,

}

# Print results
print("\n🔍 Residuals of generator algebraic equations:\n")
for eq, val in residuals.items():
    print(f"{eq:55} = {val:.3e}")

# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------

my_events = RmsEvents([])

params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector(vars_mapping)

#
# x0 = slv.initialize_with_newton(x0=slv.build_init_vars_vector(vars_mapping),
#                                    params0=params0)
#
# x0 = slv.initialize_with_pseudo_transient_gamma(
#     x0=slv.build_init_vars_vector(vars_mapping),
#     # x0=np.zeros(len(slv._state_vars) + len(slv._algebraic_vars)),
#     params0=params0
#  )


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
    t_end=20.0,
    h=0.001,
    x0=x0,
    params0=params0,
    events_list=my_events,
    method="implicit_euler"
)

# save to csv
slv.save_simulation_to_csv('simulation_results.csv', t, y)

# Generator state variables
plt.plot(t, y[:, slv.get_var_idx(omega)], label="ω (pu)")
# plt.plot(t, y[:, slv.get_var_idx(delta)], label="δ (rad)")
# plt.plot(t, y[:, slv.get_var_idx(et)], label="et (pu)")


# plt.plot(t, y[:, slv.get_var_idx(Pl)], label="Pl7(pu)")
#
# plt.plot(t, y[:, slv.get_var_idx(Vline_from_12)], label="Vline_from (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Vline_to_11)], label="Vline_to (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Vline_from_14)], label="Vline_from (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Vline_to_13)], label="Vline_to (pu)")

# # Generator algebraic variables
# plt.plot(t, y[:, slv.get_var_idx(tm_1)], label="Tm (pu)")
# plt.plot(t, y[:, slv.get_var_idx(tm_2)], label="Tm (pu)")
# plt.plot(t, y[:, slv.get_var_idx(tm_3)], label="Tm (pu)")
# plt.plot(t, y[:, slv.get_var_idx(tm_4)], label="Tm (pu)")
# plt.plot(t, y[:, slv.get_var_idx(psid_1)], label="Ψd (pu)")
# plt.plot(t, y[:, slv.get_var_idx(psiq_1)], label="Ψq (pu)")
# plt.plot(t, y[:, slv.get_var_idx(i_d_1)], label="Id (pu)")
# plt.plot(t, y[:, slv.get_var_idx(i_q_1)], label="Iq (pu)")
# plt.plot(t, y[:, slv.get_var_idx(v_d_1)], label="Vd (pu)")
# plt.plot(t, y[:, slv.get_var_idx(v_q_1)], label="Vq (pu)")
# plt.plot(t, y[:, slv.get_var_idx(t_e_1)], label="Te (pu)")
# plt.plot(t, y[:, slv.get_var_idx(t_e_2)], label="Te (pu)")
# plt.plot(t, y[:, slv.get_var_idx(t_e_3)], label="Te (pu)")
# plt.plot(t, y[:, slv.get_var_idx(t_e_4)], label="Te (pu)")
# plt.plot(t, y[:, slv.get_var_idx(P_g_1)], label="Pg (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Q_g_1)], label="Qg (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Vg_1)], label="Vg (pu)")
# plt.plot(t, y[:, slv.get_var_idx(dg_1)], label="θg (rad)")

# #Line variables
# plt.plot(t, y[:, slv.get_var_idx(Pline_from_1)], label="Pline_from (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Qline_from_1)], label="Qline_from (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Pline_to_1)], label="Pline_to (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Qline_to_1)], label="Qline_to (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Vline_from_1)], label="Vline_from (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Vline_to_1)], label="Vline_to (pu)")
# plt.plot(t, y[:, slv.get_var_idx(dline_from_1)], label="δline_from (rad)")
# plt.plot(t, y[:, slv.get_var_idx(dline_to_1)], label="δline_to (rad)")
#
# Load variables
# plt.plot(t, y[:, slv.get_var_idx(Pl_7)], label="Pl (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Ql_7)], label="Ql (pu)")

# plt.plot(t, y[:, slv.get_var_idx(Pl_8)], label="Pl (pu)")
# plt.plot(t, y[:, slv.get_var_idx(Ql_8)], label="Ql (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.title("Time Series of All System Variables")
# plt.xlim([0, 20])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()
