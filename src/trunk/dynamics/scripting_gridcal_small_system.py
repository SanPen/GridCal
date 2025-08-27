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

# In this script a small system in build with two Generators a Load, two lines and 3 buses.
# The system is uncontrolled.

# ----------------------------------------------------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------------------------------------------------
# line0
g_0 = Const(5)
b_0 = Const(-12)
bsh_0 = Const(0.03)

# line1
g_1 = Const(5)
b_1 = Const(-12)
bsh_1 = Const(0.03)


pi = Const(math.pi)

# Generator 0
fn_0 = Const(50.0)
M_0 = Const(10.0)
D_0 = Const(1.0)
ra_0 = Const(0.3)
xd_0 = Const(0.86138701)

omega_ref_0 = Const(1.0)
Kp_0 = Const(0.0)
Ki_0 = Const(0.0)
Kw_0 = Const(0.0)

# Generator 1
fn_1 = Const(50.0)
M_1 = Const(10.0)
D_1 = Const(1.0)
ra_1 = Const(0.3)
xd_1 = Const(0.86138701)

omega_ref_1 = Const(1.0)
Kp_1 = Const(0.0)
Ki_1 = Const(0.0)
Kw_1 = Const(0.0)


# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------
# Build the system to compute the powerflow
grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=10)
bus2 = gce.Bus(name="Bus2", Vnom=10)
grid.add_bus(bus0)
grid.add_bus(bus1)
grid.add_bus(bus2)

# Line
line0 = grid.add_line(gce.Line(name="line 0-2", bus_from=bus0, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0))
line1 = grid.add_line(gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0))

# load
load_grid = grid.add_load(bus=bus2, api_obj=gce.Load(P= 10, Q= 10))

# Generators
gen0 = gce.Generator(name="Gen0", P=10, vset=1.0, Snom = 900,
                    x1=0.86138701, r1=0.3, freq=50.0,
                    m_torque0=0.1,
                    M=10.0,
                    D=1.0,
                    omega_ref=1.0,
                    Kp=1.0,
                    Ki=10.0,
                    Kw=10.0)

gen1 = gce.Generator(name="Gen1", P=10, vset=1.0, Snom = 900,
                    x1=0.86138701, r1=0.3, freq=50.0,
                    m_torque0=0.1,
                    M=10.0,
                    D=1.0,
                    omega_ref=1.0,
                    Kp=1.0,
                    Ki=10.0,
                    Kw=10.0)
grid.add_generator(bus=bus0, api_obj=gen0)
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
v0 = res.voltage[0]
v1 = res.voltage[1]
v2 = res.voltage[2]

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

# Generator 0
# Current from power and voltage
i0 = np.conj(Sb0 / v0)  # ī = (p - jq) / v̄*
i1 = np.conj(Sb1 / v1)  # ī = (p - jq) / v̄*
i2 = np.conj(Sb2 / v2)  # ī = (p - jq) / v̄*

# Delta angle
delta0_0 = np.angle(v0 + (ra_0.value + 1j * xd_0.value) * i0)

# dq0 rotation
rot_0 = np.exp(-1j * (delta0_0 - np.pi / 2))

# dq voltages and currents
v_d0_0 = np.real(v0 * rot_0)
v_q0_0 = np.imag(v0 * rot_0)
i_d0_0 = np.real(i0 * rot_0)
i_q0_0 = np.imag(i0 * rot_0)

# inductances
psid0_0 = ra_0.value * i_q0_0 + v_q0_0
psiq0_0 = -ra_0.value * i_d0_0 - v_d0_0
vf0_0 = psid0_0 + xd_0.value * i_d0_0
t_e0_0 = psid0_0 * i_q0_0 - psiq0_0 * i_d0_0

# ----------------------------------------------------------------------------------------------------------------------
tm0_0 = Const(0.1)
vf_0 = Const(vf0_0)
tm_0 = Const(t_e0_0)
# ----------------------------------------------------------------------------------------------------------------------

# Generator 1
# Current from power and voltage
i0 = np.conj(Sb0 / v0)  # ī = (p - jq) / v̄*
i1 = np.conj(Sb1 / v1)  # ī = (p - jq) / v̄*
i2 = np.conj(Sb2 / v2)  # ī = (p - jq) / v̄*

# Delta angle
delta0_1 = np.angle(v1 + (ra_1.value + 1j * xd_1.value) * i1)

# dq0 rotation
rot_1 = np.exp(-1j * (delta0_1 - np.pi / 2))

# dq voltages and currents
v_d0_1 = np.real(v1 * rot_1)
v_q0_1 = np.imag(v1 * rot_1)
i_d0_1 = np.real(i1 * rot_1)
i_q0_1 = np.imag(i1 * rot_1)

# inductances
psid0_1 = ra_1.value * i_q0_1 + v_q0_1
psiq0_1 = -ra_1.value * i_d0_1 - v_d0_1
vf0_1 = psid0_1 + xd_1.value * i_d0_1
t_e0_1 = psid0_1 * i_q0_1 - psiq0_1 * i_d0_1

# ----------------------------------------------------------------------------------------------------------------------
tm0_1 = Const(0.1)
vf_1 = Const(vf0_1)
tm_1 = Const(t_e0_1)
# --------------------------------------------------------------------------------------------------------------------


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

# Load
Pl = Var("Pl")
Ql = Var("Ql")

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
    ],
    state_vars=[delta_0, omega_0],
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
    ],
    algebraic_vars=[psid_0, psiq_0, i_d_0, i_q_0, v_d_0, v_q_0, t_e_0, P_g_0, Q_g_0],
    parameters=[]
)

generator1_block = Block(
    state_eqs=[
        (2 * pi * fn_1) * (omega_1 - omega_ref_1),
        (tm_1 - t_e_1 - D_1 * (omega_1 - omega_ref_1)) / M_1,
    ],
    state_vars=[delta_1, omega_1],
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
    ],
    algebraic_vars=[psid_1, psiq_1, i_d_1, i_q_1, v_d_1, v_q_1, t_e_1, P_g_1, Q_g_1],
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
    children=[line0_block, line1_block, load, generator0_block, generator1_block, bus0_block, bus1_block, bus2_block],
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
    dline_from_0: np.angle(v0),
    dline_to_0: np.angle(v0),
    Vline_from_0: np.abs(v0),
    Vline_to_0: np.abs(v0),

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
    t_e_0: t_e0_0,
    P_g_0: Sb0.real,
    Q_g_0: Sb0.imag,

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
    t_e_1: t_e0_1,
    P_g_1: Sb1.real,
    Q_g_1: Sb1.imag,

}
print(vars_mapping)
residuals = {
    "f1: (2 * pi * fn) * (omega - omega_ref)": (2 * pi.value * fn_1.value) * (1.0 - omega_ref_1.value),
    "f2: (tm - t_e - D * (omega - omega_ref)) / M": (t_e0_1 - t_e0_1 - D_1.value * (
            1.0 - omega_ref_1.value)) / M_1.value,
    "g1: psid - (-ra * i_q + v_q)": psid0_1 - (ra_1.value * i_q0_1 + v_q0_1),
    "g2: psiq - (-ra * i_d + v_d)": psiq0_1 + (ra_1.value * i_d0_1 + v_d0_1),
    "g3: 0 - (psid + xd * i_d - vf)": 0 - (psid0_1 + xd_1.value * i_d0_1 - vf0_1),
    "g4: 0 - (psiq + xd * i_q)": 0 - (psiq0_1 + xd_1.value * i_q0_1),
    "g5: v_d - (Vg * sin(delta - dg))": v_d0_1 - (np.abs(v1) * np.sin(delta0_1 - np.angle(v1))),
    "g6: v_q - (Vg * cos(delta - dg))": v_q0_1 - (np.abs(v1) * np.cos(delta0_1 - np.angle(v1))),
    "g7: t_e - (psid * i_q - psiq * i_d)": t_e0_1 - (psid0_1 * i_q0_1 - psiq0_1 * i_d0_1),
    "g8: (v_d * i_d + v_q * i_q) - p_g": (v_d0_1 * i_d0_1 + v_q0_1 * i_q0_1) - Sb1.real,
    "g9: (v_q * i_d - v_d * i_q) - Q_g": (v_q0_1 * i_d0_1 - v_d0_1 * i_q0_1) - Sb1.imag,

    "f1_0: (2 * pi * fn_0) * (omega_0 - omega_ref_0)": (2 * pi.value * fn_0.value) * (1.0 - omega_ref_0.value),
    "f2_0: (tm - t_e_0 - D_0 * (omega_0 - omega_ref_0)) / M_0": (t_e0_0 - t_e0_0 - D_0.value * (1.0 - omega_ref_0.value)) / M_0.value,
    "g1_0: psid_0 - (-ra_0 * i_q0_0 + v_q0_0)": psid0_0 - (ra_0.value * i_q0_0 + v_q0_0),
    "g2_0: psiq_0 - (-ra_0 * i_d0_0 + v_d0_0)": psiq0_0 + (ra_0.value * i_d0_0 + v_d0_0),
    "g3_0: 0 - (psid0_0 + xd_0 * i_d0_0 - vf0_0)": 0 - (psid0_0 + xd_0.value * i_d0_0 - vf0_0),
    "g4_0: 0 - (psiq0_0 + xd_0 * i_q0_0)": 0 - (psiq0_0 + xd_0.value * i_q0_0),
    "g5_0: v_d0_0 - (Vg_0 * sin(delta0_0 - dg_0))": v_d0_0 - (np.abs(v0) * np.sin(delta0_0 - np.angle(v0))),
    "g6_0: v_q0_0 - (Vg_0 * cos(delta0_0 - dg_0))": v_q0_0 - (np.abs(v0) * np.cos(delta0_0 - np.angle(v0))),
    "g7_0: t_e0_0 - (psid0_0 * i_q0_0 - psiq0_0 * i_d0_0)": t_e0_0 - (psid0_0 * i_q0_0 - psiq0_0 * i_d0_0),
    "g8_0: (v_d0_0 * i_d0_0 + v_q0_0 * i_q0_0) - P_g_0": (v_d0_0 * i_d0_0 + v_q0_0 * i_q0_0) - Sb0.real,
    "g9_0: (v_q0_0 * i_d0_0 - v_d0_0 * i_q0_0) - Q_g_0": (v_q0_0 * i_d0_0 - v_d0_0 * i_q0_0) - Sb0.imag,
    "bus 0 P": Sb0.real - Pf0_0,
    "bus 0 Q": Sb0.imag - Qf0_0,
    "bus 1 P": Sb1.real - Pf0_1,
    "bus 1 Q": Sb1.imag - Qf0_1,
    "Bus 2 P": -Pt0_0 - Pt0_1 + Sb2.real,
    "Bus 2 Q": -Qt0_0 - Qt0_1 + Sb2.imag
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
    t_end=5.0,
    h=0.001,
    x0=x0,
    params0=params0,
    events_list=my_events,
    method="implicit_euler"
)

# save to csv
slv.save_simulation_to_csv('simulation_results.csv', t, y)

# Generator state variables
plt.plot(t, y[:, slv.get_var_idx(omega_1)], label="ω (pu)")
delta_idx = slv.get_var_idx(delta_0)  
dg_idx = slv.get_var_idx(dg_0)  
cos_delta_real = np.cos(y[:, delta_idx] - y[:, dg_idx]) 
sin_delta_real = np.sin(y[:, delta_idx] - y[:, dg_idx]) 
plt.plot(t, cos_delta_real, label="cos delta real (pu)", color='gray')
plt.plot(t, sin_delta_real, label="sin delta real (pu)", color='teal')
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
