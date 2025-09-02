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

from VeraGridEngine import DynamicVarType

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver  # compose_system_block
import VeraGridEngine.api as gce

# In this script a small system in build with a Generator a Load and a line. Generator is connected to bus 1 and Load is connected to bus 2.
# The system is uncontrolled and there are no events applyed.

# ----------------------------------------------------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------------------------------------------------
pi = Const(math.pi)

# for the lines

r_0, x_0, bsh_0 = 0.005,   0.05,   0.02187
r_1, x_1, bsh_1 = 0.005,   0.05,   0.02187

def compute_gb(r, x):
    denominator = r + 1j*x
    y = 1 / denominator
    return y.real, y.imag

g_0, b_0 = compute_gb(r_0, x_0)
g_1, b_1 = compute_gb(r_1, x_1)

# Line 0
g_0 = Const(g_0)
b_0 = Const(b_0)
bsh_0 = Const(bsh_0)

# Line 1
g_1 = Const(g_1)
b_1 = Const(b_1)
bsh_1 = Const(bsh_1)

# Generator 0
fn_0 = Const(60.0)
M_0 = Const(4.0)
D_0 = Const(1.0)
ra_0 = Const(0.0)
xd_0 = Const(0.3)
omega_ref_0 = Const(1.0)
Kp_0 = Const(0.0)
Kp_0 = Const(0.0)
Ki_0 = Const(0.0)

# Generator 1
fn_1 = Const(60.0)
M_1 = Const(4.0)
D_1 = Const(1.0)
ra_1 = Const(0.0)
xd_1 = Const(0.3)
omega_ref_1 = Const(1.0)
Kp_1 = Const(0.0)
Kp_1 = Const(0.0)
Ki_1 = Const(0.0)

# ----------------------------------------------------------------------------------------------------------------------
# Build system
# ----------------------------------------------------------------------------------------------------------------------

t = Var("t")

# Build the system to compute the powerflow
grid = gce.MultiCircuit(Sbase=100, fbase=60.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=20, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=20)
bus2 = gce.Bus(name="Bus2", Vnom=20)
grid.add_bus(bus0)
grid.add_bus(bus1)
grid.add_bus(bus2)

# Lines
line0 = gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus2, r=0.005, x=0.05, b=0.02187, rate=900.0)
line1 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.005, x=0.05, b=0.02187, rate=900.0)
grid.add_line(line0)
grid.add_line(line1)

# load
load0 = gce.Load(P= 7.5, Q= 1.0)
grid.add_load(bus=bus2, api_obj=load0)

# Generators
gen0 = gce.Generator(name="Gen0", P=4.0, vset=1.0, Snom = 900)
gen1 = gce.Generator(name="Gen2", P=3.5, vset=1.0, Snom = 900)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_generator(bus=bus1, api_obj=gen1)

# Run PF
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

# ----------------------------------------------------------------------------------------------------------------------
# Build init guess and solver
# ----------------------------------------------------------------------------------------------------------------------
# Voltages
v0 = res.voltage[0]
v1 = res.voltage[1]
v2 = res.voltage[2]

# Powers
Sb0 = res.Sbus[0] / grid.Sbase
Sb1 = res.Sbus[1] / grid.Sbase
Sb2 = res.Sbus[2] / grid.Sbase

Sf = res.Sf / grid.Sbase
St = res.St / grid.Sbase

Pf0_0 = Sf[0].real
Qf0_0 = Sf[0].imag
Pt0_0 = St[0].real
Qt0_0 = St[0].imag

Pf0_1 = Sf[1].real
Qf0_1 = Sf[1].imag
Pt0_1 = St[1].real
Qt0_1 = St[1].imag

# Currents
i0 = np.conj(Sb0 / v0)  # ī = (p - jq) / v̄*
i1 = np.conj(Sb1 / v1)  # ī = (p - jq) / v̄*
i2 = np.conj(Sb2 / v2)  # ī = (p - jq) / v̄*

# Generator 0
# Delta angle
delta0_0 = np.angle(v0 + (ra_0.value + 1j * xd_0.value) * i0)
# dq0 rotation
rot_0 = np.exp(-1j * (delta0_0 - np.pi / 2))
# dq voltages and currents
v_d0_0 = np.real(v0 * rot_0)
v_q0_0 = np.imag(v0 * rot_0)
i_d0_0 = np.real(i0 * rot_0)
i_q0_0 = np.imag(i0 * rot_0)
# others
psid0_0 = ra_0.value * i_q0_0 + v_q0_0
psiq0_0 = -ra_0.value * i_d0_0 - v_d0_0
vf0_0 = psid0_0 + xd_0.value * i_d0_0
te0_0 = psid0_0 * i_q0_0 - psiq0_0 * i_d0_0

tm0_0 = Const(te0_0)
vf_0 = Const(vf0_0)

print("tm0")
print(tm0_0)

print("vf_0")
print(vf_0)

# Generator 1
# Delta angle
delta0_1 = np.angle(v1 + (ra_1.value + 1j * xd_1.value) * i1)
# dq0 rotation
rot_1 = np.exp(-1j * (delta0_1 - np.pi / 2))
# dq voltages and currents
v_d0_1 = np.real(v1 * rot_1)
v_q0_1 = np.imag(v1 * rot_1)
i_d0_1 = np.real(i1 * rot_1)
i_q0_1 = np.imag(i1 * rot_1)
# others
psid0_1 = ra_1.value * i_q0_1 + v_q0_1
psiq0_1 = -ra_1.value * i_d0_1 - v_d0_1
vf0_1 = psid0_1 + xd_1.value * i_d0_1
te0_1 = psid0_1 * i_q0_1 - psiq0_1 * i_d0_1

tm0_1 = Const(te0_1)
vf_1 = Const(vf0_1)

print("tm1")
print(tm0_1)

print("vf_1")
print(vf_1)

# -----------------------------------------------------
# Variables
# -----------------------------------------------------
# Line 0
Pline_to_0 = Var("Pline_to_0")
Qline_to_0 = Var("Qline_to_0")
Pline_from_0 = Var("Pline_from_0")
Qline_from_0 = Var("Qline_from_0")
Vline_to_0 = Var("Vline_to_0")
dline_to_0 = Var("dline_to_0")
Vline_from_0 = Var("Vline_from_0")
dline_from_0 = Var("dline_from_0")

# Line 1
Pline_to_1 = Var("Pline_to_1")
Qline_to_1 = Var("Qline_to_1")
Pline_from_1 = Var("Pline_from_1")
Qline_from_1 = Var("Qline_from_1")
Vline_to_1 = Var("Vline_to_1")
dline_to_1 = Var("dline_to_1")
Vline_from_1 = Var("Vline_from_1")
dline_from_1 = Var("dline_from_1")

# Gencls 0
delta_0 = Var("delta_0")
omega_0 = Var("omega_0")
psid_0 = Var("psid_0")
psiq_0 = Var("psiq_0")
i_d_0 = Var("i_d_0")
i_q_0 = Var("i_q_0")
v_d_0 = Var("v_d_0")
v_q_0 = Var("v_q_0")
t_e_0 = Var("t_e_0")
P_g_0 = Var("P_e_0")
Q_g_0 = Var("Q_e_0")
dg_0 = Var("dg_0")
Vg_0 = Var("Vg_0")
et_0 = Var("et_0")
tm_0 = Var("tm_0")

# Gencls 1
delta_1 = Var("delta_1")
omega_1 = Var("omega_1")
psid_1 = Var("psid_1")
psiq_1 = Var("psiq_1")
i_d_1 = Var("i_d_1")
i_q_1 = Var("i_q_1")
v_d_1 = Var("v_d_1")
v_q_1 = Var("v_q_1")
t_e_1 = Var("t_e_1")
P_g_1 = Var("P_e_1")
Q_g_1 = Var("Q_e_1")
dg_1 = Var("dg_1")
Vg_1 = Var("Vg_1")
et_1 = Var("et_1")
tm_1 = Var("tm_1")

# Load
Pl = Var("Pl")
Ql = Var("Ql")

t = Var("t")

# -----------------------------------------------------
# Buses
# -----------------------------------------------------

bus0_block = Block(
    algebraic_eqs=[
        P_g_0 - Pline_from_0,
        Q_g_0 - Qline_from_0,
        Vg_0 - Vline_from_0,
        dg_0 - dline_from_0
    ],
    algebraic_vars=[Pline_from_0, Qline_from_0, Vg_0, dg_0]
)

bus1_block = Block(
    algebraic_eqs=[
        P_g_1 - Pline_from_1,
        Q_g_1 - Qline_from_1,
        Vg_1 - Vline_from_1,
        dg_1 - dline_from_1
    ],
    algebraic_vars=[Pline_from_1, Qline_from_1, Vg_1, dg_1]
)

bus2_block = Block(
    algebraic_eqs=[
        - Pline_to_0 - Pline_to_1 + Pl,
        - Qline_to_0 - Qline_to_1 + Ql,
        Vline_to_0 - Vline_to_1,
        dline_to_0 - dline_to_1

    ],
    algebraic_vars=[Pline_to_0, Qline_to_0, Pline_to_1, Qline_to_1]
)

# -----------------------------------------------------------------------------------
# Lines
# -----------------------------------------------------------------------------------

line0_block = Block(
    algebraic_eqs=[
        Pline_from_0 - ((Vline_from_0 ** 2 * g_0) - g_0 * Vline_from_0 * Vline_to_0 * cos(
            dline_from_0 - dline_to_0) + b_0 * Vline_from_0 * Vline_to_0 * cos(dline_from_0 - dline_to_0 + np.pi / 2)),
        Qline_from_0 - (Vline_from_0 ** 2 * (-bsh_0 / 2 - b_0) - g_0 * Vline_from_0 * Vline_to_0 * sin(
            dline_from_0 - dline_to_0) + b_0 * Vline_from_0 * Vline_to_0 * sin(dline_from_0 - dline_to_0 + np.pi / 2)),
        Pline_to_0 - ((Vline_to_0 ** 2 * g_0) - g_0 * Vline_to_0 * Vline_from_0 * cos(
            dline_to_0 - dline_from_0) + b_0 * Vline_to_0 * Vline_from_0 * cos(dline_to_0 - dline_from_0 + np.pi / 2)),
        Qline_to_0 - (Vline_to_0 ** 2 * (-bsh_0 / 2 - b_0) - g_0 * Vline_to_0 * Vline_from_0 * sin(
            dline_to_0 - dline_from_0) + b_0 * Vline_to_0 * Vline_from_0 * sin(dline_to_0 - dline_from_0 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_0, Vline_from_0, dline_to_0, Vline_to_0],
    parameters=[]
)

line1_block = Block(
    algebraic_eqs=[
        Pline_from_1 - ((Vline_from_1 ** 2 * g_1) - g_1 * Vline_from_1 * Vline_to_1 * cos(
            dline_from_1 - dline_to_1) + b_1 * Vline_from_1 * Vline_to_1 * cos(dline_from_1 - dline_to_1 + np.pi / 2)),
        Qline_from_1 - (Vline_from_1 ** 2 * (-bsh_1 / 2 - b_1) - g_1 * Vline_from_1 * Vline_to_1 * sin(
            dline_from_1 - dline_to_1) + b_1 * Vline_from_1 * Vline_to_1 * sin(dline_from_1 - dline_to_1 + np.pi / 2)),
        Pline_to_1 - ((Vline_to_1 ** 2 * g_1) - g_1 * Vline_to_1 * Vline_from_1 * cos(
            dline_to_1 - dline_from_1) + b_1 * Vline_to_1 * Vline_from_1 * cos(dline_to_1 - dline_from_1 + np.pi / 2)),
        Qline_to_1 - (Vline_to_1 ** 2 * (-bsh_1 / 2 - b_1) - g_1 * Vline_to_1 * Vline_from_1 * sin(
            dline_to_1 - dline_from_1) + b_1 * Vline_to_1 * Vline_from_1 * sin(dline_to_1 - dline_from_1 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_1, Vline_from_1, dline_to_1, Vline_to_1],
    parameters=[]
)

# --------------------------------------------------------------------------
# Generators
# --------------------------------------------------------------------------

generator0_block = Block(
    state_eqs=[
        (2 * pi * fn_0) * (omega_0 - omega_ref_0),
        (tm_0 - t_e_0 - D_0 * (omega_0 - omega_ref_0)) / M_0,
        (omega_0 - omega_ref_0)
    ],
    state_vars=[delta_0, omega_0, et_0],
    algebraic_eqs=[
        psid_0 - (ra_0 * i_q_0 + v_q_0),
        psiq_0 + (ra_0 * i_d_0 + v_d_0),
        0 - (psid_0 + xd_0 * i_d_0 - vf_0),
        0 - (psiq_0 + xd_0 * i_q_0),
        v_d_0 - (Vg_0 * sin(delta_0 - dg_0)),
        v_q_0 - (Vg_0 * cos(delta_0 - dg_0)),
        t_e_0 - (psid_0 * i_q_0 - psiq_0 * i_d_0),
        P_g_0 - (v_d_0 * i_d_0 + v_q_0 * i_q_0),
        Q_g_0 - (v_q_0 * i_d_0 - v_d_0 * i_q_0),
        tm_0 - (tm0_0 + (Kp_0 * (omega_0 - omega_ref_0) + Ki_0 * et_0)),
    ],
    algebraic_vars=[psid_0, psiq_0, i_d_0, i_q_0, v_d_0, v_q_0, t_e_0, P_g_0, Q_g_0, tm_0],
    parameters=[]
)

generator1_block = Block(
    state_eqs=[
        (2 * pi * fn_1) * (omega_1 - omega_ref_1),
        (tm_1 - t_e_1 - D_1 * (omega_1 - omega_ref_1)) / M_1,
        (omega_1 - omega_ref_1)
    ],
    state_vars=[delta_1, omega_1, et_1],
    algebraic_eqs=[
        psid_1 - (ra_1 * i_q_1 + v_q_1),
        psiq_1 + (ra_1 * i_d_1 + v_d_1),
        0 - (psid_1 + xd_1 * i_d_1 - vf_1),
        0 - (psiq_1 + xd_1 * i_q_1),
        v_d_1 - (Vg_1 * sin(delta_1 - dg_1)),
        v_q_1 - (Vg_1 * cos(delta_1 - dg_1)),
        t_e_1 - (psid_1 * i_q_1 - psiq_1 * i_d_1),
        P_g_1 - (v_d_1 * i_d_1 + v_q_1 * i_q_1),
        Q_g_1 - (v_q_1 * i_d_1 - v_d_1 * i_q_1),
        tm_1 - (tm0_1 + Kp_1 * (omega_1 - omega_ref_1) + Ki_1 * et_1),
    ],
    algebraic_vars=[psid_1, psiq_1, i_d_1, i_q_1, v_d_1, v_q_1, t_e_1, P_g_1, Q_g_1, tm_1],
    parameters=[]
)

# -------------------------------------------------------------
# Load
# -------------------------------------------------------------
Pl0 = Var("Pl0")
# Pl0 = Const(Sb2.real)
Ql0 = Const(Sb2.imag)
#
# print("Pl0")
# print(Pl0)
#
# print("Ql0")
# print(Ql0)
#
# load = Block(
#     algebraic_eqs=[
#         Pl - Pl0,
#         Ql - Ql0
#     ],
#     algebraic_vars=[Ql, Pl],
#     parameters=[] #Pl0
# )

load = Block(
    algebraic_eqs=[
        Pl - Pl0,
        Ql - Ql0
    ],
    algebraic_vars=[Pl, Ql],
    init_eqs={},
    init_vars=[],
    init_params_eq={},
    parameters=[Pl0],
    parameters_eqs=[piecewise(t, 2.5, 0.15, -0.075000000001172)],
    external_mapping={
        DynamicVarType.P: Pl,
        DynamicVarType.Q: Ql
    }
)

# ----------------------------------------------------------------------------------------------------------------------
# System
# ----------------------------------------------------------------------------------------------------------------------
sys = Block(
    children=[line0_block, line1_block, load, generator0_block, generator1_block, bus0_block, bus1_block, bus2_block],
    in_vars=[]
)



vars_mapping = {
    dline_from_0: np.angle(v0),
    dline_to_0: np.angle(v2),
    Vline_from_0: np.abs(v0),
    Vline_to_0: np.abs(v2),

    Pline_from_0: Pf0_0,
    Qline_from_0: Qf0_0,
    Pline_to_0: Pt0_0,
    Qline_to_0: Qt0_0,

    dline_from_1: np.angle(v1),
    dline_to_1: np.angle(v2),
    Vline_from_1: np.abs(v1),
    Vline_to_1: np.abs(v2),

    Pline_from_1: Pf0_1,
    Qline_from_1: Qf0_1,
    Pline_to_1: Pt0_1,
    Qline_to_1: Qt0_1,

    Pl: Sb2.real,  # P2
    Ql: Sb2.imag,  # Q2

    Vg_0: np.abs(v0),
    dg_0: np.angle(v0),
    delta_0: delta0_0,
    omega_0: omega_ref_0.value,
    psid_0: psid0_0,
    psiq_0: psiq0_0,
    i_d_0: i_d0_0,
    i_q_0: i_q0_0,
    v_d_0: v_d0_0,
    v_q_0: v_q0_0,
    t_e_0: te0_0,
    P_g_0: Sb0.real,
    Q_g_0: Sb0.imag,
    tm_0: te0_0,

    Vg_1: np.abs(v1),
    dg_1: np.angle(v1),
    delta_1: delta0_1,
    omega_1: omega_ref_1.value,
    psid_1: psid0_1,
    psiq_1: psiq0_1,
    i_d_1: i_d0_1,
    i_q_1: i_q0_1,
    v_d_1: v_d0_1,
    v_q_1: v_q0_1,
    t_e_1: te0_1,
    P_g_1: Sb1.real,
    Q_g_1: Sb1.imag,
    tm_1: te0_1

}

init_guess = vars_mapping
print(init_guess)
# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = BlockSolver(sys, t)



params_mapping = {
    #Pl0: Sb2.real,
    # Ql0: 0.1
}

# Check residuals
residuals = {
    "GEN 0 f1_0: (2 * pi * fn_0) * (omega_0 - omega_ref_0)": (2 * pi.value * fn_0.value) * (1.0 - omega_ref_0.value),
    "GEN 0 f2_0: (tm - t_e_0 - D_0 * (omega_0 - omega_ref_0)) / M_0": (te0_0 - te0_0 - D_0.value * (1.0 - omega_ref_0.value)) / M_0.value,
    "GEN 0 g1_0: psid_0 - (-ra_0 * i_q0_0 + v_q0_0)": psid0_0 - (ra_0.value * i_q0_0 + v_q0_0),
    "GEN 0 g2_0: psiq_0 - (-ra_0 * i_d0_0 + v_d0_0)": psiq0_0 + (ra_0.value * i_d0_0 + v_d0_0),
    "GEN 0 g3_0: 0 - (psid0_0 + xd_0 * i_d0_0 - vf0_0)": 0 - (psid0_0 + xd_0.value * i_d0_0 - vf0_0),
    "GEN 0 g4_0: 0 - (psiq0_0 + xd_0 * i_q0_0)": 0 - (psiq0_0 + xd_0.value * i_q0_0),
    "GEN 0 g5_0: v_d0_0 - (Vg_0 * sin(delta0_0 - dg_0))": v_d0_0 - (np.abs(v0) * np.sin(delta0_0 - np.angle(v0))),
    "GEN 0 g6_0: v_q0_0 - (Vg_0 * cos(delta0_0 - dg_0))": v_q0_0 - (np.abs(v0) * np.cos(delta0_0 - np.angle(v0))),
    "GEN 0 g7_0: te0_0 - (psid0_0 * i_q0_0 - psiq0_0 * i_d0_0)": te0_0 - (psid0_0 * i_q0_0 - psiq0_0 * i_d0_0),
    "GEN 0 g8_0: (v_d0_0 * i_d0_0 + v_q0_0 * i_q0_0) - P_g_0": (v_d0_0 * i_d0_0 + v_q0_0 * i_q0_0) - Sb0.real,
    "GEN 0 g9_0: (v_q0_0 * i_d0_0 - v_d0_0 * i_q0_0) - Q_g_0": (v_q0_0 * i_d0_0 - v_d0_0 * i_q0_0) - Sb0.imag,
    "GEN 1 f1: (2 * pi * fn) * (omega - omega_ref)": (2 * pi.value * fn_1.value) * (1.0 - omega_ref_1.value),
    "GEN 1 f2: (tm - t_e - D * (omega - omega_ref)) / M": (te0_1 - te0_1 - D_1.value * (1.0 - omega_ref_1.value)) / M_1.value,
    "GEN 1 g1: psid - (-ra * i_q + v_q)": psid0_1 - (ra_1.value * i_q0_1 + v_q0_1),
    "GEN 1 g2: psiq - (-ra * i_d + v_d)": psiq0_1 + (ra_1.value * i_d0_1 + v_d0_1),
    "GEN 1 g3: 0 - (psid + xd * i_d - vf)": 0 - (psid0_1 + xd_1.value * i_d0_1 - vf0_1),
    "GEN 1 g4: 0 - (psiq + xd * i_q)": 0 - (psiq0_1 + xd_1.value * i_q0_1),
    "GEN 1 g5: v_d - (Vg * sin(delta - dg))": v_d0_1 - (np.abs(v1) * np.sin(delta0_1 - np.angle(v1))),
    "GEN 1 g6: v_q - (Vg * cos(delta - dg))": v_q0_1 - (np.abs(v1) * np.cos(delta0_1 - np.angle(v1))),
    "GEN 1 g7: t_e - (psid * i_q - psiq * i_d)": te0_1 - (psid0_1 * i_q0_1 - psiq0_1 * i_d0_1),
    "GEN 1 g8: (v_d * i_d + v_q * i_q) - p_g": (v_d0_1 * i_d0_1 + v_q0_1 * i_q0_1) - Sb1.real,
    "GEN 1 g9: (v_q * i_d - v_d * i_q) - Q_g": (v_q0_1 * i_d0_1 - v_d0_1 * i_q0_1) - Sb1.imag,
    "Bus 0 P": Sb0.real - Pf0_0,
    "Bus 0 Q": Sb0.imag - Qf0_0,
    "Bus 1 P": Sb1.real - Pf0_1,
    "Bus 1 Q": Sb1.imag - Qf0_1,
    "Bus 2 P": -Pt0_0 - Pt0_1 + Sb2.real,
    "Bus 2 Q": -Qt0_0 - Qt0_1 + Sb2.imag
}

print("\n🔍 Residuals of generator algebraic equations:\n")
for eq, val in residuals.items():
    print(f"{eq:55} = {val:.3e}")

print(vars_mapping)

# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------


params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector(vars_mapping)
vars_in_order = slv.sort_vars(vars_mapping)

t, y = slv.simulate(
    t0=0,
    t_end=20.0,
    h=0.001,
    x0=x0,
    params0=params0,
    time = t,
    method="implicit_euler"
)

# Save to csv
slv.save_simulation_to_csv('simulation_results.csv', t, y)

# Plot
plt.figure(figsize=(10, 6))
plt.plot(t, y[:, slv.get_var_idx(omega_1)], label="ω (pu)")
plt.xlabel("Time [s]")
plt.ylabel("Speed [pu]")
plt.title("Generator Speed ω vs Time")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
