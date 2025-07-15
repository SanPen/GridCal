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


# define all variables and constants

g_0 = 0.208     # Series conductance (p.u.)
b_0 = -2.029    # Series susceptance (p.u.)
bsh_0 = 3.371    # Total shunt susceptance (p.u.)

g_1 = 0.208
b_1 = -2.029
bsh_1 = 3.371

g_2 = 0.208
b_2 = -2.029
bsh_2 = 3.371

g_3 = 0.208
b_3 = -2.029
bsh_3 = 3.371

g_4 = 0.208
b_4 = -2.029
bsh_4 = 3.371

g_5 = 0.208
b_5 = -2.029
bsh_5 = 3.371

g_6 =0.208
b_6 = -2.029
bsh_6 = 3.371

g_7 = 0.208
b_7 = -2.029
bsh_7 = 3.371

g_8 = 0.208
b_8 = -2.029
bsh_8 = 3.371

g_9 = 0.208
b_9 = -2.029
bsh_9 = 3.371

g_10 = 0.208
b_10 = -2.029
bsh_10 = 3.371

g_11 = 0.208
b_11 = -2.029
bsh_11 = 3.371

g_12 = 0.208
b_12 = -2.029
bsh_12 = 3.371

g_13 = 0.208
b_13 = -2.029
bsh_13 = 3.371

g_14 = 0.208
b_14 = -2.029
bsh_14 = 3.371


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

# Line 2

Pline_from_2 = Var("Pline_from_2")
Qline_from_2 = Var("Qline_from_2")
Vline_to_2 = Var("Vline_to_2")
dline_to_2 = Var("dline_to_2")
Vline_from_2 = Var("Vline_from_2")
dline_from_2 = Var("dline_from_2")
Pline_to_2 = Var("Pline_to_2")
Qline_to_2 = Var("Qline_to_2")

# Line 3

Pline_from_3 = Var("Pline_from_3")
Qline_from_3 = Var("Qline_from_3")
Pline_to_3 = Var("Pline_to_3")
Qline_to_3 = Var("Qline_to_3")
Vline_to_3 = Var("Vline_to_3")
dline_to_3 = Var("dline_to_3")
Vline_from_3 = Var("Vline_from_3")
dline_from_3 = Var("dline_from_3")

# Line 4

Pline_from_4 = Var("Pline_from_4")
Qline_from_4 = Var("Pline_from_4")
Pline_to_4 = Var("Pline_to_4")
Qline_to_4 = Var("Pline_to_4")
Vline_to_4 = Var("Vline_to_4")
dline_to_4 = Var("dline_to_4")
Vline_from_4 = Var("Vline_from_4")
dline_from_4 = Var("dline_from_4")

# Line 5

Pline_from_5 = Var("Qline_from_5")
Qline_from_5 = Var("Qline_from_5")
Pline_to_5 = Var("Qline_to_5")
Qline_to_5 = Var("Qline_to_5")
Vline_to_5 = Var("Vline_to_5")
dline_to_5 = Var("dline_to_5")
Vline_from_5 = Var("Vline_from_5")
dline_from_5 = Var("dline_from_5")

# Line 6

Pline_from_6 = Var("Qline_from_6")
Qline_from_6 = Var("Qline_from_6")
Pline_to_6 = Var("Qline_to_6")
Qline_to_6 = Var("Qline_to_6")
Vline_to_6 = Var("Vline_to_6")
dline_to_6 = Var("dline_to_6")
Vline_from_6 = Var("Vline_from_6")
dline_from_6 = Var("dline_from_6")

# Line 7

Pline_from_7 = Var("Pline_from_7")
Qline_from_7 = Var("Qline_from_7")
Pline_to_7 = Var("Pline_from_7")
Qline_to_7 = Var("Qline_from_7")
Vline_to_7 = Var("Vline_to_7")
dline_to_7 = Var("dline_to_7")
Vline_from_7 = Var("Vline_from_7")
dline_from_7 = Var("dline_from_7")


# Line 8

Pline_from_8 = Var("Pline_from_8")
Qline_from_8 = Var("Qline_from_8")
Pline_to_8 = Var("Pline_from_8")
Qline_to_8 = Var("Qline_from_8")
Vline_to_8 = Var("Vline_to_8")
dline_to_8 = Var("dline_to_8")
Vline_from_8 = Var("Vline_from_8")
dline_from_8 = Var("dline_from_8")

# Line 9

Pline_to_9 = Var("Pline_to_9")
Qline_to_9 = Var("Qline_to_9")
Pline_from_9 = Var("Pline_from_9")
Qline_from_9 = Var("Pline_from_9")
Vline_to_9 = Var("Vline_to_9")
dline_to_9 = Var("dline_to_9")
Vline_from_9 = Var("Vline_from_9")
dline_from_9 = Var("dline_from_9")

# Line 10

Pline_to_10 = Var("Pline_to_10")
Qline_to_10 = Var("Qline_to_10")
Pline_from_10 = Var("Qline_from_10")
Qline_from_10 = Var("Qline_from_10")
Vline_to_10 = Var("Vline_to_10")
dline_to_10 = Var("dline_to_10")
Vline_from_10 = Var("Vline_from_10")
dline_from_10 = Var("dline_from_10")

# Line 11

Pline_from_11 = Var("Pline_from_11")
Qline_from_11 = Var("Qline_from_11")
Vline_from_11 = Var("Vlintoe_from_11")
dline_from_11 = Var("dline_from_11")
Vline_to_11 = Var("Vline_to_11")
dline_to_11 = Var("dline_to_11")
Pline_to_11 = Var("Pline_from_11")
Qline_to_11 = Var("Qline_from_11")

# Line 12

Pline_from_12 = Var("Pline_from_12")
Qline_from_12 = Var("Qline_from_12")
Vline_from_12 = Var("Vline_from_12")
dline_from_12 = Var("dline_from_12")
Pline_to_12 = Var("Pline_to_12")
Qline_to_12 = Var("Qline_to_12")
Vline_to_12 = Var("Vline_to_12")
dline_to_12 = Var("dline_to_12")

# Line 13

Pline_to_13 = Var("Pline_to_13")
Qline_to_13 = Var("Qline_to_13")
Vline_to_13 = Var("Vline_to_13")
dline_to_13 = Var("dline_to_13")
Vline_from_13 = Var("Vline_from_13")
dline_from_13 = Var("dline_from_13")
Pline_from_13 = Var("Qline_from_13")
Qline_from_13 = Var("Qline_from_13")

# Line 14

Pline_to_14 = Var("Pline_to_14")
Qline_to_14 = Var("Qline_to_14")
Vline_to_14 = Var("Vline_to_14")
dline_to_14 = Var("dline_to_14")
Vline_from_14 = Var("Vline_from_14")
dline_from_14 = Var("dline_from_14")
Pline_from_14 = Var("Pline_from_14")
Qline_from_14 = Var("Qline_from_14")


pi = Const(math.pi)

# Generator 1
fn_1 = Const(60)
# tm = Const(0.1)
M_1 = Const(1.0)
D_1 = Const(100)
ra_1 = Const(0.3)
xd_1 = Const(0.86138701)
vf_1 = Const(1.081099313)
omega_ref_1 = Const(1)
Kp_1 = Const(1.0)
Ki_1 = Const(10.0)
Kw_1 = Const(10.0)

# Generator 2
fn_2 = Const(60)
# tm = Const(0.1)
M_2 = Const(1.0)
D_2 = Const(100)
ra_2 = Const(0.3)
xd_2 = Const(0.86138701)
vf_2 = Const(1.081099313)

omega_ref_2 = Const(1)
Kp_2 = Const(1.0)
Ki_2 = Const(10.0)
Kw_2 = Const(10.0)


# Generator 3
fn_3 = Const(60)
# tm = Const(0.1)
M_3 = Const(1.0)
D_3 = Const(100)
ra_3 = Const(0.3)
xd_3 = Const(0.86138701)
vf_3 = Const(1.081099313)

omega_ref_3 = Const(1)
Kp_3 = Const(1.0)
Ki_3 = Const(10.0)
Kw_3 = Const(10.0)

# Generator 4
fn_4 = Const(60)
# tm = Const(0.1)
M_4 = Const(1.0)
D_4 = Const(100)
ra_4 = Const(0.3)
xd_4 = Const(0.86138701)
vf_4 = Const(1.081099313)

omega_ref_4 = Const(1)
Kp_4 = Const(1.0)
Ki_4 = Const(10.0)
Kw_4 = Const(10.0)


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
p_g_1 = Var("P_e_1")
Q_g_1 = Var("Q_e_1")
dg_1 = Var("dg_1")
tm_1 = Var("tm_1")
et_1 = Var("et_1")
Vg_1 = Var("Vg_1")

# Gencls 2

p_g_2 = Var("p_g_2")
Q_g_2 = Var("Q_g_2")
Vg_2 = Var("Vg_2")
dg_2 = Var("dg_2")
delta_2 = Var("delta_2")
omega_2 = Var("omega_2")
psid_2 = Var("psid_2")
psiq_2 = Var("psiq_2")
i_d_2 = Var("i_d_2")
i_q_2 = Var("i_q_2")
v_d_2 = Var("v_d_2")
v_q_2 = Var("v_q_2")
t_e_2 = Var("t_e_2")
tm_2 = Var("tm_2")
et_2 = Var("et_2")


# Gencls 3

p_g_3 = Var("p_g_3")
Q_g_3 = Var("Q_g_3")
Vg_3 = Var("Vg_3")
dg_3 = Var("dg_3")
delta_3 = Var("delta_3")
omega_3 = Var("omega_3")
psid_3 = Var("psid_3")
psiq_3 = Var("psiq_3")
i_d_3 = Var("i_d_3")
i_q_3 = Var("i_q_3")
v_d_3 = Var("v_d_3")
v_q_3 = Var("v_q_3")
t_e_3 = Var("t_e_3")
tm_3 = Var("tm_3")
et_3 = Var("et_3")

# Gencls 4

p_g_4 = Var("p_g_4")
Q_g_4 = Var("Q_g_4")
Vg_4 = Var("Vg_4")
dg_4 = Var("dg_4")
delta_4 = Var("delta_4")
omega_4 = Var("omega_4")
psid_4 = Var("psid_4")
psiq_4 = Var("psiq_4")
i_d_4 = Var("i_d_4")
i_q_4 = Var("i_q_4")
v_d_4 = Var("v_d_4")
v_q_4 = Var("v_q_4")
t_e_4 = Var("t_e_4")
tm_4 = Var("tm_4")
et_4 = Var("et_4")

# Load 7
Pl_7 = Var("Pl_7")
Ql_7 = Var("Ql_7")

# Load 8
Pl_8 = Var("Pl_8")
Ql_8 = Var("Ql_8")

# Build the models

# -----------------------------------------------------
# Buses
# -----------------------------------------------------

bus1_block = Block(
    algebraic_eqs=[
        p_g_1 - Pline_from_11,
        Q_g_1 - Qline_from_11,
        Vg_1 - Vline_from_11,
        dg_1 - dline_from_11
    ],
    algebraic_vars=[Pline_from_11, Qline_from_11, Vg_1, dg_1]
)

bus2_block = Block(
    algebraic_eqs=[
        p_g_2 - Pline_from_12,
        Q_g_2 - Qline_from_12,
        Vg_2 - Vline_from_12,
        dg_2 - dline_from_12
    ],
    algebraic_vars=[Pline_from_12, Qline_from_12, Vg_2, dg_2]
)

bus3_block = Block(
    algebraic_eqs=[
        p_g_3 + Pline_to_13,
        Q_g_3 + Qline_to_13,
        Vg_3 - Vline_to_13,
        dg_3 - dline_to_13
    ],
    algebraic_vars=[Pline_to_13, Qline_to_13, Vg_3, dg_3]
)

bus4_block = Block(
    algebraic_eqs=[
        p_g_4 + Pline_to_14,
        Q_g_4 + Qline_to_14,
        Vg_4 - Vline_to_14,
        dg_4 - dline_to_14
    ],
    algebraic_vars=[Pline_to_14, Qline_to_14, Vg_4, dg_4]
)

bus5_block = Block(
    algebraic_eqs=[
        - Pline_from_0 - Pline_from_1 - Pline_to_11,
        - Qline_from_0 - Qline_from_1 - Qline_to_11,
        Pline_to_11 - Pline_from_0,
        Pline_to_11 - Pline_from_1,
        Qline_to_11 - Qline_from_0,
        Qline_to_11 - Qline_from_1

    ],
    algebraic_vars=[Pline_from_0, Pline_from_1, Pline_to_11, Qline_from_0, Qline_from_1, Qline_to_11]
)



bus6_block = Block(
    algebraic_eqs=[
        - Pline_from_2 - Pline_from_3 + Pline_to_12 + Pline_to_1 + Pline_to_0,
        - Qline_from_2 - Qline_from_3 + Qline_to_12 + Qline_to_1 + Qline_to_0,
        Pline_to_12 - Pline_from_2,
        Pline_to_12 - Pline_from_3,
        Pline_to_12 - Pline_to_0,
        Pline_to_12 - Pline_to_1,
        Qline_to_12 - Qline_from_2,
        Qline_to_12 - Qline_from_3,
        Qline_to_12 - Qline_to_0,
        Qline_to_12 - Qline_to_1
    ],
    algebraic_vars=[Pline_from_2, Pline_from_3, Pline_to_12, Pline_to_1, Pline_to_0, Qline_from_2, Qline_from_3, Qline_to_12, Qline_to_1, Qline_to_0]
)

bus7_block = Block(
    algebraic_eqs=[
        Pline_to_2 + Pline_to_3 - Pline_from_4 - Pline_from_5 - Pline_from_6 - Pl_7,
        Qline_to_2 + Qline_to_3 - Qline_from_4 - Qline_from_5 - Qline_from_6 - Ql_7,
        Pline_to_2 - Pline_from_4,
        Pline_to_2 - Pline_from_5,
        Pline_to_2 - Pline_from_6,
        Pline_to_2 - Pline_to_3,
        Qline_to_2 - Qline_from_4,
        Qline_to_2 - Qline_from_5,
        Qline_to_2 - Qline_from_6,
        Qline_to_2 - Qline_to_3

    ],
    algebraic_vars=[Pline_to_2, Pline_to_3, Pline_from_4, Pline_from_5, Pline_from_6, Qline_to_2, Qline_to_3, Qline_from_4, Qline_from_5, Qline_from_6]
)

bus8_block = Block(
    algebraic_eqs=[
        Pline_to_4 + Pline_to_5 + Pline_to_6 - Pline_from_7 - Pline_from_8 - Pl_8,
        Qline_to_4 + Qline_to_5 + Qline_to_6 - Qline_from_7 - Qline_from_8 - Ql_8,
        Pline_to_4 - Pline_from_7,
        Pline_to_4 - Pline_from_8,
        Pline_to_4 - Pline_to_5,
        Pline_to_4 - Pline_to_6,
        Qline_to_4 - Qline_from_7,
        Qline_to_4 - Qline_from_8,
        Qline_to_4 - Qline_to_5,
        Qline_to_4 - Qline_to_6
    ],
    algebraic_vars=[Pline_to_4, Pline_to_5, Pline_to_6, Pline_from_7, Pline_from_8, Qline_to_4, Qline_to_5, Qline_to_6, Qline_from_7, Qline_from_8]
)

bus9_block = Block(
    algebraic_eqs=[
        Pline_to_7 + Pline_to_8 - Pline_from_9 - Pline_from_10 - Pline_from_13,
        Qline_to_7 + Qline_to_8 - Qline_from_9 - Qline_from_10 - Qline_from_13,
        Pline_to_7 - Pline_from_9,
        Pline_to_7 - Pline_from_10,
        Pline_to_7 - Pline_from_13,
        Pline_to_7 - Pline_to_8,
        Qline_to_7 - Qline_from_9,
        Qline_to_7 - Qline_from_10,
        Qline_to_7 - Qline_from_13,
        Qline_to_7 - Qline_to_8

    ],
    algebraic_vars=[Pline_to_7, Pline_to_8, Pline_from_9, Pline_from_10, Pline_from_13, Qline_to_7, Qline_to_8, Qline_from_9, Qline_from_10, Qline_from_13]
)


bus10_block = Block(
    algebraic_eqs=[
        - Pline_from_14 + Pline_to_10 + Pline_to_9,
        - Qline_from_14 + Qline_to_10 + Qline_to_9,
        Pline_to_9 - Pline_from_14,
        Pline_to_9 - Pline_to_10,
        Qline_to_9 - Qline_from_14,
        Qline_to_9 - Qline_to_10
    ],
    algebraic_vars=[Pline_from_14, Pline_to_10, Pline_to_9, Qline_from_14, Qline_to_10, Qline_to_9]
)


# -----------------------------------------------------------------------------------
# Lines
# -----------------------------------------------------------------------------------

line_0_block = Block(
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




line_1_block = Block(
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

line_2_block = Block(
    algebraic_eqs=[
        Pline_from_2 - ((Vline_from_2 ** 2 * g_2) - g_2 * Vline_from_2 * Vline_to_2 * cos(
            dline_from_2 - dline_to_2) + b_2 * Vline_from_2 * Vline_to_2 * cos(dline_from_2 - dline_to_2 + np.pi / 2)),
        Qline_from_2 - (Vline_from_2 ** 2 * (-bsh_2 / 2 - b_2) - g_2 * Vline_from_2 * Vline_to_2 * sin(
            dline_from_2 - dline_to_2) + b_2 * Vline_from_2 * Vline_to_2 * sin(dline_from_2 - dline_to_2 + np.pi / 2)),
        Pline_to_2 - ((Vline_to_2 ** 2 * g_2) - g_2 * Vline_to_2 * Vline_from_2 * cos(
            dline_to_2 - dline_from_2) + b_2 * Vline_to_2 * Vline_from_2 * cos(dline_to_2 - dline_from_2 + np.pi / 2)),
        Qline_to_2 - (Vline_to_2 ** 2 * (-bsh_2 / 2 - b_2) - g_2 * Vline_to_2 * Vline_from_2 * sin(
            dline_to_2 - dline_from_2) + b_2 * Vline_to_2 * Vline_from_2 * sin(dline_to_2 - dline_from_2 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_2, Vline_from_2, dline_to_2, Vline_to_2],
    parameters=[]
)

line_3_block = Block(
    algebraic_eqs=[
        Pline_from_3 - ((Vline_from_3 ** 2 * g_3) - g_3 * Vline_from_3 * Vline_to_3 * cos(
            dline_from_3 - dline_to_3) + b_3 * Vline_from_3 * Vline_to_3 * cos(dline_from_3 - dline_to_3 + np.pi / 2)),
        Qline_from_3 - (Vline_from_3 ** 2 * (-bsh_3 / 2 - b_3) - g_3 * Vline_from_3 * Vline_to_3 * sin(
            dline_from_3 - dline_to_3) + b_3 * Vline_from_3 * Vline_to_3 * sin(dline_from_3 - dline_to_3 + np.pi / 2)),
        Pline_to_3 - ((Vline_to_3 ** 2 * g_3) - g_3 * Vline_to_3 * Vline_from_3 * cos(
            dline_to_3 - dline_from_3) + b_3 * Vline_to_3 * Vline_from_3 * cos(dline_to_3 - dline_from_3 + np.pi / 2)),
        Qline_to_3 - (Vline_to_3 ** 2 * (-bsh_3 / 2 - b_3) - g_3 * Vline_to_3 * Vline_from_3 * sin(
            dline_to_3 - dline_from_3) + b_3 * Vline_to_3 * Vline_from_3 * sin(dline_to_3 - dline_from_3 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_3, Vline_from_3, dline_to_3, Vline_to_3],
    parameters=[]
)

line_4_block = Block(
    algebraic_eqs=[
        Pline_from_4 - ((Vline_from_4 ** 2 * g_4) - g_4 * Vline_from_4 * Vline_to_4 * cos(
            dline_from_4 - dline_to_4) + b_4 * Vline_from_4 * Vline_to_4 * cos(dline_from_4 - dline_to_4 + np.pi / 2)),
        Qline_from_4 - (Vline_from_4 ** 2 * (-bsh_4 / 2 - b_4) - g_4 * Vline_from_4 * Vline_to_4 * sin(
            dline_from_4 - dline_to_4) + b_4 * Vline_from_4 * Vline_to_4 * sin(dline_from_4 - dline_to_4 + np.pi / 2)),
        Pline_to_4 - ((Vline_to_4 ** 2 * g_4) - g_4 * Vline_to_4 * Vline_from_4 * cos(
            dline_to_4 - dline_from_4) + b_4 * Vline_to_4 * Vline_from_4 * cos(dline_to_4 - dline_from_4 + np.pi / 2)),
        Qline_to_4 - (Vline_to_4 ** 2 * (-bsh_4 / 2 - b_4) - g_4 * Vline_to_4 * Vline_from_4 * sin(
            dline_to_4 - dline_from_4) + b_4 * Vline_to_4 * Vline_from_4 * sin(dline_to_4 - dline_from_4 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_4, Vline_from_4, dline_to_4, Vline_to_4],
    parameters=[]
)

line_5_block = Block(
    algebraic_eqs=[
        Pline_from_5 - ((Vline_from_5 ** 2 * g_5) - g_5 * Vline_from_5 * Vline_to_5 * cos(
            dline_from_5 - dline_to_5) + b_5 * Vline_from_5 * Vline_to_5 * cos(dline_from_5 - dline_to_5 + np.pi / 2)),
        Qline_from_5 - (Vline_from_5 ** 2 * (-bsh_5 / 2 - b_5) - g_5 * Vline_from_5 * Vline_to_5 * sin(
            dline_from_5 - dline_to_5) + b_5 * Vline_from_5 * Vline_to_5 * sin(dline_from_5 - dline_to_5 + np.pi / 2)),
        Pline_to_5 - ((Vline_to_5 ** 2 * g_5) - g_5 * Vline_to_5 * Vline_from_5 * cos(
            dline_to_5 - dline_from_5) + b_5 * Vline_to_5 * Vline_from_5 * cos(dline_to_5 - dline_from_5 + np.pi / 2)),
        Qline_to_5 - (Vline_to_5 ** 2 * (-bsh_5 / 2 - b_5) - g_5 * Vline_to_5 * Vline_from_5 * sin(
            dline_to_5 - dline_from_5) + b_5 * Vline_to_5 * Vline_from_5 * sin(dline_to_5 - dline_from_5 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_5, Vline_from_5, dline_to_5, Vline_to_5],
    parameters=[]
)

line_6_block = Block(
    algebraic_eqs=[
        Pline_from_6 - ((Vline_from_6 ** 2 * g_6) - g_6 * Vline_from_6 * Vline_to_6 * cos(
            dline_from_6 - dline_to_6) + b_6 * Vline_from_6 * Vline_to_6 * cos(dline_from_6 - dline_to_6 + np.pi / 2)),
        Qline_from_6 - (Vline_from_6 ** 2 * (-bsh_6 / 2 - b_6) - g_6 * Vline_from_6 * Vline_to_6 * sin(
            dline_from_6 - dline_to_6) + b_6 * Vline_from_6 * Vline_to_6 * sin(dline_from_6 - dline_to_6 + np.pi / 2)),
        Pline_to_6 - ((Vline_to_6 ** 2 * g_6) - g_6 * Vline_to_6 * Vline_from_6 * cos(
            dline_to_6 - dline_from_6) + b_6 * Vline_to_6 * Vline_from_6 * cos(dline_to_6 - dline_from_6 + np.pi / 2)),
        Qline_to_6 - (Vline_to_6 ** 2 * (-bsh_6 / 2 - b_6) - g_6 * Vline_to_6 * Vline_from_6 * sin(
            dline_to_6 - dline_from_6) + b_6 * Vline_to_6 * Vline_from_6 * sin(dline_to_6 - dline_from_6 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_6, Vline_from_6, dline_to_6, Vline_to_6],
    parameters=[]
)

line_7_block = Block(
    algebraic_eqs=[
        Pline_from_7 - ((Vline_from_7 ** 2 * g_7) - g_7 * Vline_from_7 * Vline_to_7 * cos(
            dline_from_7 - dline_to_7) + b_7 * Vline_from_7 * Vline_to_7 * cos(dline_from_7 - dline_to_7 + np.pi / 2)),
        Qline_from_7 - (Vline_from_7 ** 2 * (-bsh_7 / 2 - b_7) - g_7 * Vline_from_7 * Vline_to_7 * sin(
            dline_from_7 - dline_to_7) + b_7 * Vline_from_7 * Vline_to_7 * sin(dline_from_7 - dline_to_7 + np.pi / 2)),
        Pline_to_7 - ((Vline_to_7 ** 2 * g_7) - g_7 * Vline_to_7 * Vline_from_7 * cos(
            dline_to_7 - dline_from_7) + b_7 * Vline_to_7 * Vline_from_7 * cos(dline_to_7 - dline_from_7 + np.pi / 2)),
        Qline_to_7 - (Vline_to_7 ** 2 * (-bsh_7 / 2 - b_7) - g_7 * Vline_to_7 * Vline_from_7 * sin(
            dline_to_7 - dline_from_7) + b_7 * Vline_to_7 * Vline_from_7 * sin(dline_to_7 - dline_from_7 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_7, Vline_from_7, dline_to_7, Vline_to_7],
    parameters=[]
)

line_8_block = Block(
    algebraic_eqs=[
        Pline_from_8 - ((Vline_from_8 ** 2 * g_8) - g_8 * Vline_from_8 * Vline_to_8 * cos(
            dline_from_8 - dline_to_8) + b_8 * Vline_from_8 * Vline_to_8 * cos(dline_from_8 - dline_to_8 + np.pi / 2)),
        Qline_from_8 - (Vline_from_8 ** 2 * (-bsh_8 / 2 - b_8) - g_8 * Vline_from_8 * Vline_to_8 * sin(
            dline_from_8 - dline_to_8) + b_8 * Vline_from_8 * Vline_to_8 * sin(dline_from_8 - dline_to_8 + np.pi / 2)),
        Pline_to_8 - ((Vline_to_8 ** 2 * g_8) - g_8 * Vline_to_8 * Vline_from_8 * cos(
            dline_to_8 - dline_from_8) + b_8 * Vline_to_8 * Vline_from_8 * cos(dline_to_8 - dline_from_8 + np.pi / 2)),
        Qline_to_8 - (Vline_to_8 ** 2 * (-bsh_8 / 2 - b_8) - g_8 * Vline_to_8 * Vline_from_8 * sin(
            dline_to_8 - dline_from_8) + b_8 * Vline_to_8 * Vline_from_8 * sin(dline_to_8 - dline_from_8 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_8, Vline_from_8, dline_to_8, Vline_to_8],
    parameters=[]
)

line_9_block = Block(
    algebraic_eqs=[
        Pline_from_9 - ((Vline_from_9 ** 2 * g_9) - g_9 * Vline_from_9 * Vline_to_9 * cos(
            dline_from_9 - dline_to_9) + b_9 * Vline_from_9 * Vline_to_9 * cos(dline_from_9 - dline_to_9 + np.pi / 2)),
        Qline_from_9 - (Vline_from_9 ** 2 * (-bsh_9 / 2 - b_9) - g_9 * Vline_from_9 * Vline_to_9 * sin(
            dline_from_9 - dline_to_9) + b_9 * Vline_from_9 * Vline_to_9 * sin(dline_from_9 - dline_to_9 + np.pi / 2)),
        Pline_to_9 - ((Vline_to_9 ** 2 * g_9) - g_9 * Vline_to_9 * Vline_from_9 * cos(
            dline_to_9 - dline_from_9) + b_9 * Vline_to_9 * Vline_from_9 * cos(dline_to_9 - dline_from_9 + np.pi / 2)),
        Qline_to_9 - (Vline_to_9 ** 2 * (-bsh_9 / 2 - b_9) - g_9 * Vline_to_9 * Vline_from_9 * sin(
            dline_to_9 - dline_from_9) + b_9 * Vline_to_9 * Vline_from_9 * sin(dline_to_9 - dline_from_9 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_9, Vline_from_9, dline_to_9, Vline_to_9],
    parameters=[]
)

line_10_block = Block(
    algebraic_eqs=[
        Pline_from_10 - ((Vline_from_10 ** 2 * g_10) - g_10 * Vline_from_10 * Vline_to_10 * cos(
            dline_from_10 - dline_to_10) + b_10 * Vline_from_10 * Vline_to_10 * cos(dline_from_10 - dline_to_10 + np.pi / 2)),
        Qline_from_10 - (Vline_from_10 ** 2 * (-bsh_10 / 2 - b_10) - g_10 * Vline_from_10 * Vline_to_10 * sin(
            dline_from_10 - dline_to_10) + b_10 * Vline_from_10 * Vline_to_10 * sin(dline_from_10 - dline_to_10 + np.pi / 2)),
        Pline_to_10 - ((Vline_to_10 ** 2 * g_10) - g_10 * Vline_to_10 * Vline_from_10 * cos(
            dline_to_10 - dline_from_10) + b_10 * Vline_to_10 * Vline_from_10 * cos(dline_to_10 - dline_from_10 + np.pi / 2)),
        Qline_to_10 - (Vline_to_10 ** 2 * (-bsh_10 / 2 - b_10) - g_10 * Vline_to_10 * Vline_from_10 * sin(
            dline_to_10 - dline_from_10) + b_10 * Vline_to_10 * Vline_from_10 * sin(dline_to_10 - dline_from_10 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_10, Vline_from_10, dline_to_10, Vline_to_10],
    parameters=[]
)

line_11_block = Block(
    algebraic_eqs=[
        Pline_from_11 - ((Vline_from_11 ** 2 * g_11) - g_11 * Vline_from_11 * Vline_to_11 * cos(
            dline_from_11 - dline_to_11) + b_11 * Vline_from_11 * Vline_to_11 * cos(dline_from_11 - dline_to_11 + np.pi / 2)),
        Qline_from_11 - (Vline_from_11 ** 2 * (-bsh_11 / 2 - b_11) - g_11 * Vline_from_11 * Vline_to_11 * sin(
            dline_from_11 - dline_to_11) + b_11 * Vline_from_11 * Vline_to_11 * sin(dline_from_11 - dline_to_11 + np.pi / 2)),
        Pline_to_11 - ((Vline_to_11 ** 2 * g_11) - g_11 * Vline_to_11 * Vline_from_11 * cos(
            dline_to_11 - dline_from_11) + b_11 * Vline_to_11 * Vline_from_11 * cos(dline_to_11 - dline_from_11 + np.pi / 2)),
        Qline_to_11 - (Vline_to_11 ** 2 * (-bsh_11 / 2 - b_11) - g_11 * Vline_to_11 * Vline_from_11 * sin(
            dline_to_11 - dline_from_11) + b_11 * Vline_to_11 * Vline_from_11 * sin(dline_to_11 - dline_from_11 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_11, Vline_from_11, dline_to_11, Vline_to_11],
    parameters=[]
)

line_12_block = Block(
    algebraic_eqs=[
        Pline_from_12 - ((Vline_from_12 ** 2 * g_12) - g_12 * Vline_from_12 * Vline_to_12 * cos(
            dline_from_12 - dline_to_12) + b_12 * Vline_from_12 * Vline_to_12 * cos(dline_from_12 - dline_to_12 + np.pi / 2)),
        Qline_from_12 - (Vline_from_12 ** 2 * (-bsh_12 / 2 - b_12) - g_12 * Vline_from_12 * Vline_to_12 * sin(
            dline_from_12 - dline_to_12) + b_12 * Vline_from_12 * Vline_to_12 * sin(dline_from_12 - dline_to_12 + np.pi / 2)),
        Pline_to_12 - ((Vline_to_12 ** 2 * g_12) - g_12 * Vline_to_12 * Vline_from_12 * cos(
            dline_to_12 - dline_from_12) + b_12 * Vline_to_12 * Vline_from_12 * cos(dline_to_12 - dline_from_12 + np.pi / 2)),
        Qline_to_12 - (Vline_to_12 ** 2 * (-bsh_12 / 2 - b_12) - g_12 * Vline_to_12 * Vline_from_12 * sin(
            dline_to_12 - dline_from_12) + b_12 * Vline_to_12 * Vline_from_12 * sin(dline_to_12 - dline_from_12 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_12, Vline_from_12, dline_to_12, Vline_to_12],
    parameters=[]
)

line_13_block = Block(
    algebraic_eqs=[
        Pline_from_13 - ((Vline_from_13 ** 2 * g_13) - g_13 * Vline_from_13 * Vline_to_13 * cos(
            dline_from_13 - dline_to_13) + b_13 * Vline_from_13 * Vline_to_13 * cos(dline_from_13 - dline_to_13 + np.pi / 2)),
        Qline_from_13 - (Vline_from_13 ** 2 * (-bsh_13 / 2 - b_13) - g_13 * Vline_from_13 * Vline_to_13 * sin(
            dline_from_13 - dline_to_13) + b_13 * Vline_from_13 * Vline_to_13 * sin(dline_from_13 - dline_to_13 + np.pi / 2)),
        Pline_to_13 - ((Vline_to_13 ** 2 * g_13) - g_13 * Vline_to_13 * Vline_from_13 * cos(
            dline_to_13 - dline_from_13) + b_13 * Vline_to_13 * Vline_from_13 * cos(dline_to_13 - dline_from_13 + np.pi / 2)),
        Qline_to_13 - (Vline_to_13 ** 2 * (-bsh_13 / 2 - b_13) - g_13 * Vline_to_13 * Vline_from_13 * sin(
            dline_to_13 - dline_from_13) + b_13 * Vline_to_13 * Vline_from_13 * sin(dline_to_13 - dline_from_13 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_13, Vline_from_13, dline_to_13, Vline_to_13],
    parameters=[]
)

line_14_block = Block(
    algebraic_eqs=[
        Pline_from_14 - ((Vline_from_14 ** 2 * g_14) - g_14 * Vline_from_14 * Vline_to_14 * cos(
            dline_from_14 - dline_to_14) + b_14 * Vline_from_14 * Vline_to_14 * cos(dline_from_14 - dline_to_14 + np.pi / 2)),
        Qline_from_14 - (Vline_from_14 ** 2 * (-bsh_14 / 2 - b_14) - g_14 * Vline_from_14 * Vline_to_14 * sin(
            dline_from_14 - dline_to_14) + b_14 * Vline_from_14 * Vline_to_14 * sin(dline_from_14 - dline_to_14 + np.pi / 2)),
        Pline_to_14 - ((Vline_to_14 ** 2 * g_14) - g_14 * Vline_to_14 * Vline_from_14 * cos(
            dline_to_14 - dline_from_14) + b_14 * Vline_to_14 * Vline_from_14 * cos(dline_to_14 - dline_from_14 + np.pi / 2)),
        Qline_to_14 - (Vline_to_14 ** 2 * (-bsh_14 / 2 - b_14) - g_14 * Vline_to_14 * Vline_from_14 * sin(
            dline_to_14 - dline_from_14) + b_14 * Vline_to_14 * Vline_from_14 * sin(dline_to_14 - dline_from_14 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_14, Vline_from_14, dline_to_14, Vline_to_14],
    parameters=[]
)

# --------------------------------------------------------------------------
# Generators
# --------------------------------------------------------------------------

generator_block_1 = Block(
    state_eqs=[
        (2 * pi * fn_1) * (omega_1 - omega_ref_1),
        (tm_1 - t_e_1 - D_1 * (omega_1 - omega_ref_1)) / M_1,
        -Kp_1 * et_1 - Ki_1 * et_1 - Kw_1 * (omega_1 - omega_ref_1)
    ],
    state_vars=[delta_1, omega_1, et_1],
    algebraic_eqs=[
        et_1 - (tm_1 - t_e_1),
        psid_1 - (-ra_1 * i_q_1 + v_q_1),
        psiq_1 - (-ra_1 * i_d_1 + v_d_1),
        i_d_1 - (psid_1 + xd_1 * i_d_1 - vf_1),
        i_q_1 - (psiq_1 + xd_1 * i_q_1),
        v_d_1 - (Vg_1 * sin(delta_1 - dg_1)),
        v_q_1 - (Vg_1 * cos(delta_1 - dg_1)),
        t_e_1 - (psid_1 * i_q_1 - psiq_1 * i_d_1),
        (v_d_1 * i_d_1 + v_q_1 * i_q_1) - p_g_1,
        (v_q_1 * i_d_1 - v_d_1 * i_q_1) - Q_g_1
    ],
    algebraic_vars=[tm_1, psid_1, psiq_1, i_d_1, i_q_1, v_d_1, v_q_1, t_e_1, p_g_1, Q_g_1],
    parameters=[]
)



generator_block_2 = Block(
    state_eqs=[
        (2 * pi * fn_2) * (omega_2 - omega_ref_2),
        (tm_2 - t_e_2 - D_2 * (omega_2 - omega_ref_2)) / M_2,
        -Kp_2 * et_2 - Ki_2 * et_2 - Kw_2 * (omega_2 - omega_ref_2)
    ],
    state_vars=[delta_2, omega_2, et_2],
    algebraic_eqs=[
        et_2 - (tm_2 - t_e_2),
        psid_2 - (-ra_2 * i_q_2 + v_q_2),
        psiq_2 - (-ra_2 * i_d_2 + v_d_2),
        i_d_2 - (psid_2 + xd_2 * i_d_2 - vf_2),
        i_q_2 - (psiq_2 + xd_2 * i_q_2),
        v_d_2 - (Vg_2 * sin(delta_2 - dg_2)),
        v_q_2 - (Vg_2 * cos(delta_2 - dg_2)),
        t_e_2 - (psid_2 * i_q_2 - psiq_2 * i_d_2),
        (v_d_2 * i_d_2 + v_q_2 * i_q_2) - p_g_2,
        (v_q_2 * i_d_2 - v_d_2 * i_q_2) - Q_g_2
    ],
    algebraic_vars=[tm_2, psid_2, psiq_2, i_d_2, i_q_2, v_d_2, v_q_2, t_e_2, p_g_2, Q_g_2],
    parameters=[]
)



generator_block_3 = Block(
    state_eqs=[
        (2 * pi * fn_3) * (omega_3 - omega_ref_3),
        (tm_3 - t_e_3 - D_3 * (omega_3 - omega_ref_3)) / M_3,
        -Kp_3 * et_3 - Ki_3 * et_3 - Kw_3 * (omega_3 - omega_ref_3)
    ],
    state_vars=[delta_3, omega_3, et_3],
    algebraic_eqs=[
        et_3 - (tm_3 - t_e_3),
        psid_3 - (-ra_3 * i_q_3 + v_q_3),
        psiq_3 - (-ra_3 * i_d_3 + v_d_3),
        i_d_3 - (psid_3 + xd_3 * i_d_3 - vf_3),
        i_q_3 - (psiq_3 + xd_3 * i_q_3),
        v_d_3 - (Vg_3 * sin(delta_3 - dg_3)),
        v_q_3 - (Vg_3 * cos(delta_3 - dg_3)),
        t_e_3 - (psid_3 * i_q_3 - psiq_3 * i_d_3),
        (v_d_3 * i_d_3 + v_q_3 * i_q_3) - p_g_3,
        (v_q_3 * i_d_3 - v_d_3 * i_q_3) - Q_g_3
    ],
    algebraic_vars=[tm_3, psid_3, psiq_3, i_d_3, i_q_3, v_d_3, v_q_3, t_e_3, p_g_3, Q_g_3],
    parameters=[]
)

# Generator 4


generator_block_4 = Block(
    state_eqs=[
        (2 * pi * fn_4) * (omega_4 - omega_ref_4),
        (tm_4 - t_e_4 - D_4 * (omega_4 - omega_ref_4)) / M_4,
        -Kp_4 * et_4 - Ki_4 * et_4 - Kw_4 * (omega_4 - omega_ref_4)
    ],
    state_vars=[delta_4, omega_4, et_4],
    algebraic_eqs=[
        et_4 - (tm_4 - t_e_4),
        psid_4 - (-ra_4 * i_q_4 + v_q_4),
        psiq_4 - (-ra_4 * i_d_4 + v_d_4),
        i_d_4 - (psid_4 + xd_4 * i_d_4 - vf_4),
        i_q_4 - (psiq_4 + xd_4 * i_q_4),
        v_d_4 - (Vg_4 * sin(delta_4 - dg_4)),
        v_q_4 - (Vg_4 * cos(delta_4 - dg_4)),
        t_e_4 - (psid_4 * i_q_4 - psiq_4 * i_d_4),
        (v_d_4 * i_d_4 + v_q_4 * i_q_4) - p_g_4,
        (v_q_4 * i_d_4 - v_d_4 * i_q_4) - Q_g_4
    ],
    algebraic_vars=[tm_4, psid_4, psiq_4, i_d_4, i_q_4, v_d_4, v_q_4, t_e_4, p_g_4, Q_g_4],
    parameters=[]
)

# -------------------------------------------------------------
# Load
# -------------------------------------------------------------
Ql0_7 = Const(0.1)
Pl0_7 = Const(0.1)

#Pl0_7 = Var('Pl0_7')

load_7 = Block(
    algebraic_eqs=[
        Pl_7 - Pl0_7,
        Ql_7 - Ql0_7
    ],
    algebraic_vars=[Ql_7, Pl_7],
    parameters=[]
)
Ql0_8 = Const(0.1)
Pl0_8 = Const(0.1)

load_8 = Block(
    algebraic_eqs=[
        Pl_8 - Pl0_8,
        Ql_8 - Ql0_8
    ],
    algebraic_vars=[Ql_8, Pl_8],
    parameters=[]
)


sys = Block(
    children=[line_0_block, line_1_block, line_2_block, line_3_block, line_4_block, line_5_block, line_6_block, line_7_block, line_8_block, line_9_block, line_10_block, line_11_block, line_12_block, line_13_block, line_14_block, load_7, load_8, generator_block_1, generator_block_2, generator_block_3, generator_block_4, bus1_block, bus2_block, bus3_block, bus4_block, bus5_block, bus6_block, bus7_block, bus8_block, bus9_block, bus10_block],
    in_vars=[]
)


# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = BlockSolver(sys)

params_mapping = {
    # Pl0_7: 0.1,
    #Ql0: 0.1
}

vars_mapping = {

    dline_from_0: 15 * (np.pi / 180),
    dline_to_0: 10 * (np.pi / 180),
    Vline_from_0: 1.0,
    Vline_to_0: 0.95,

    Pline_from_0: 0.1,
    Qline_from_0: 0.2,
    Pline_to_0: -0.1,
    Qline_to_0: -0.2,

    dline_from_1: 15 * (np.pi / 180),
    dline_to_1: 10 * (np.pi / 180),
    Vline_from_1: 1.0,
    Vline_to_1: 0.95,
    Vg_1: 1.0,
    dg_1: 15 * (np.pi / 180),
    Pline_from_1: 0.1,
    Qline_from_1: 0.2,
    Pline_to_1: -0.1,
    Qline_to_1: -0.2,

    dline_from_2: 15 * (np.pi / 180),
    dline_to_2: 10 * (np.pi / 180),
    Vline_from_2: 1.0,
    Vline_to_2: 0.95,
    Vg_2: 1.0,
    dg_2: 15 * (np.pi / 180),
    Pline_from_2: 0.1,
    Qline_from_2: 0.2,
    Pline_to_2: -0.1,
    Qline_to_2: -0.2,

    dline_from_3: 15 * (np.pi / 180),
    dline_to_3: 10 * (np.pi / 180),
    Vline_from_3: 1.0,
    Vline_to_3: 0.95,
    Vg_3: 1.0,
    dg_3: 15 * (np.pi / 180),
    Pline_from_3: 0.1,
    Qline_from_3: 0.2,
    Pline_to_3: -0.1,
    Qline_to_3: -0.2,

    dline_from_4: 15 * (np.pi / 180),
    dline_to_4: 10 * (np.pi / 180),
    Vline_from_4: 1.0,
    Vline_to_4: 0.95,
    Vg_4: 1.0,
    dg_4: 15 * (np.pi / 180),
    Pline_from_4: 0.1,
    Qline_from_4: 0.2,
    Pline_to_4: -0.1,
    Qline_to_4: -0.2,

    dline_from_5: 15 * (np.pi / 180),
    dline_to_5: 10 * (np.pi / 180),
    Vline_from_5: 1.0,
    Vline_to_5: 0.95,
    Pline_from_5: 0.1,
    Qline_from_5: 0.2,
    Pline_to_5: -0.1,
    Qline_to_5: -0.2,

    dline_from_6: 15 * (np.pi / 180),
    dline_to_6: 10 * (np.pi / 180),
    Vline_from_6: 1.0,
    Vline_to_6: 0.95,
    Pline_from_6: 0.1,
    Qline_from_6: 0.2,
    Pline_to_6: -0.1,
    Qline_to_6: -0.2,

    dline_from_7: 15 * (np.pi / 180),
    dline_to_7: 10 * (np.pi / 180),
    Vline_from_7: 1.0,
    Vline_to_7: 0.95,
    Pline_from_7: 0.1,
    Qline_from_7: 0.2,
    Pline_to_7: -0.1,
    Qline_to_7: -0.2,

    dline_from_8: 15 * (np.pi / 180),
    dline_to_8: 10 * (np.pi / 180),
    Vline_from_8: 1.0,
    Vline_to_8: 0.95,
    Pline_from_8: 0.1,
    Qline_from_8: 0.2,
    Pline_to_8: -0.1,
    Qline_to_8: -0.2,

    dline_from_9: 15 * (np.pi / 180),
    dline_to_9: 10 * (np.pi / 180),
    Vline_from_9: 1.0,
    Vline_to_9: 0.95,
    Pline_from_9: 0.1,
    Qline_from_9: 0.2,
    Pline_to_9: -0.1,
    Qline_to_9: -0.2,

    dline_from_10: 15 * (np.pi / 180),
    dline_to_10: 10 * (np.pi / 180),
    Vline_from_10: 1.0,
    Vline_to_10: 0.95,
    Pline_from_10: 0.1,
    Qline_from_10: 0.2,
    Pline_to_10: -0.1,
    Qline_to_10: -0.2,

    dline_from_11: 15 * (np.pi / 180),
    dline_to_11: 10 * (np.pi / 180),
    Vline_from_11: 1.0,
    Vline_to_11: 0.95,
    Pline_from_11: 0.1,
    Qline_from_11: 0.2,
    Pline_to_11: -0.1,
    Qline_to_11: -0.2,

    dline_from_12: 15 * (np.pi / 180),
    dline_to_12: 10 * (np.pi / 180),
    Vline_from_12: 1.0,
    Vline_to_12: 0.95,
    Pline_from_12: 0.1,
    Qline_from_12: 0.2,
    Pline_to_12: -0.1,
    Qline_to_12: -0.2,

    dline_from_13: 15 * (np.pi / 180),
    dline_to_13: 10 * (np.pi / 180),
    Vline_from_13: 1.0,
    Vline_to_13: 0.95,
    Pline_from_13: 0.1,
    Qline_from_13: 0.2,
    Pline_to_13: -0.1,
    Qline_to_13: -0.2,

    dline_from_14: 15 * (np.pi / 180),
    dline_to_14: 10 * (np.pi / 180),
    Vline_from_14: 1.0,
    Vline_to_14: 0.95,
    Pline_from_14: 0.1,
    Qline_from_14: 0.2,
    Pline_to_14: -0.1,
    Qline_to_14: -0.2,



    #
    # dline_from_1: 0.0,
    # dline_to_1: 0.0,
    # Vline_from_1: 1.0,
    # Vline_to_1: 1.0,
    # Vg_1: 1.0,
    # dg_1: 0.0,
    # Pline_from_1: 0.0,
    # Qline_from_1: 0.0,
    # Pline_to_1: 0.0,
    # Qline_to_1: 0.0,
    #
    # dline_from_2: 0.0,
    # dline_to_2: 0.0,
    # Vline_from_2: 1.0,
    # Vline_to_2: 1.0,
    # Vg_2: 1.0,
    # dg_2: 0.0,
    # Pline_from_2: 0.0,
    # Qline_from_2: 0.0,
    # Pline_to_2: 0.0,
    # Qline_to_2: 0.0,
    #
    # dline_from_3: 0.0,
    # dline_to_3: 0.0,
    # Vline_from_3: 1.0,
    # Vline_to_3: 1.0,
    # Vg_3: 1.0,
    # dg_3: 0.0,
    # Pline_from_3: 0.0,
    # Qline_from_3: 0.0,
    # Pline_to_3: 0.0,
    # Qline_to_3: 0.0,
    #
    # dline_from_4: 0.0,
    # dline_to_4: 0.0,
    # Vline_from_4: 1.0,
    # Vline_to_4: 1.0,
    # Vg_4: 1.0,
    # dg_4: 0.0,
    # Pline_from_4: 0.0,
    # Qline_from_4: 0.0,
    # Pline_to_4: 0.0,
    # Qline_to_4: 0.0,
    #
    # dline_from_5: 0.0,
    # dline_to_5: 0.0,
    # Vline_from_5: 1.0,
    # Vline_to_5: 1.0,
    # Pline_from_5: 0.0,
    # Qline_from_5: 0.0,
    # Pline_to_5: 0.0,
    # Qline_to_5: 0.0,
    #
    # dline_from_6: 0.0,
    # dline_to_6: 0.0,
    # Vline_from_6: 1.0,
    # Vline_to_6: 1.0,
    # Qline_from_6: 0.0,
    # Pline_to_6: 0.0,
    # Qline_to_6: 0.0,
    #
    # dline_from_7: 0.0,
    # dline_to_7: 0.0,
    # Vline_from_7: 1.0,
    # Vline_to_7: 1.0,
    # Pline_from_7: 0.0,
    # Qline_from_7: 0.0,
    # Pline_to_7: 0.0,
    # Qline_to_7: 0.0,
    #
    # dline_from_8: 0.0,
    # dline_to_8: 0.0,
    # Vline_from_8: 1.0,
    # Vline_to_8: 1.0,
    # Pline_from_8: 0.0,
    # Qline_from_8: 0.0,
    # Pline_to_8: 0.0,
    # Qline_to_8: 0.0,
    #
    # dline_from_9: 0.0,
    # dline_to_9: 0.0,
    # Vline_from_9: 1.0,
    # Vline_to_9: 1.0,
    # Pline_from_9: 0.0,
    # Qline_from_9: 0.0,
    # Pline_to_9: 0.0,
    # Qline_to_9: 0.0,
    #
    # dline_from_10: 0.0,
    # dline_to_10: 0.0,
    # Vline_from_10: 1.0,
    # Vline_to_10: 1.0,
    #
    # Pline_from_10: 0.0,
    # Qline_from_10: 0.0,
    # Pline_to_10: 0.0,
    # Qline_to_10: 0.0,
    #
    # dline_from_11: 0.0,
    # dline_to_11: 0.0,
    # Vline_from_11: 1.0,
    # Vline_to_11: 1.0,
    # Pline_from_11: 0.0,
    # Qline_from_11: 0.0,
    # Pline_to_11: 0.0,
    # Qline_to_11: 0.0,
    #
    # dline_from_12: 0.0,
    # dline_to_12: 0.0,
    # Vline_from_12: 1.0,
    # Vline_to_12: 1.0,
    # Pline_from_12: 0.0,
    # Qline_from_12: 0.0,
    # Pline_to_12: 0.0,
    # Qline_to_12: 0.0,
    #
    # dline_from_13: 0.0,
    # dline_to_13: 0.0,
    # Vline_from_13: 1.0,
    # Vline_to_13: 1.0,
    # Pline_from_13: 0.0,
    # Qline_from_13: 0.0,
    # Pline_to_13: 0.0,
    # Qline_to_13: 0.0,
    #
    # dline_from_14: 0.0,
    # dline_to_14: 0.0,
    # Vline_from_14: 1.0,
    # Vline_to_14: 1.0,
    # Pline_from_14: 0.0,
    # Qline_from_14: 0.0,
    # Pline_to_14: 0.0,
    # Qline_to_14: 0.0,

    Pl_7: 0.1,  # P2
    Ql_7: 0.2,  # Q2
    Pl_8: 0.1,  # P2
    Ql_8: 0.2,  # Q2



    delta_1: 0.5,
    omega_1: 1.001,
    psid_1: 3.825,
    psiq_1: 0.0277,
    i_d_1: 0.1,
    i_q_1: 0.2,
    v_d_1: -0.2588,
    v_q_1: 0.9659,
    t_e_1: 0.1,
    p_g_1: 0.1673,
    Q_g_1: 0.1484,

    delta_2: 0.5,
    omega_2: 1.001,
    psid_2: 3.825,
    psiq_2: 0.0277,
    i_d_2: 0.1,
    i_q_2: 0.2,
    v_d_2: -0.2588,
    v_q_2: 0.9659,
    t_e_2: 0.1,
    p_g_2: 0.1673,
    Q_g_2: 0.1484,



    delta_3: 0.5,
    omega_3: 1.001,
    psid_3: 3.825,
    psiq_3: 0.0277,
    i_d_3: 0.1,
    i_q_3: 0.2,
    v_d_3: -0.2588,
    v_q_3: 0.9659,
    t_e_3: 0.1,
    p_g_3: 0.1673,
    Q_g_3: 0.1484,

    delta_4: 0.5,
    omega_4: 1.001,
    psid_4: 3.825,
    psiq_4: 0.0277,
    i_d_4: 0.1,
    i_q_4: 0.2,
    v_d_4: -0.2588,
    v_q_4: 0.9659,
    t_e_4: 0.1,
    p_g_4: 0.1673,
    Q_g_4: 0.1484,
}



# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------

#event1 = Event(Pl0_7, 5000, 0.3)

my_events = Events([])



params0 = slv.build_init_params_vector(params_mapping)
#x0 = slv.build_init_vars_vector(vars_mapping)

#
# x0 = slv.initialize_with_newton(x0=slv.build_init_vars_vector(vars_mapping),
#                                   params0=params0)
#
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








