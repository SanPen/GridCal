# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import time 

import numpy as np
from matplotlib import pyplot as plt

import sys
import os

from VeraGridEngine import DynamicVarType

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
import VeraGridEngine.api as gce

# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------
# Load system from .raw file
grid_1 = gce.open_file('Two_Areas_PSS_E/Benchmark_4ger_33_2015_noshunt.raw')
# Run power flow
# res_1 = gce.power_flow(grid_1)
# # # Print results
# print(res_1.get_bus_df())
# print(res_1.get_branch_df())
# print(f"Converged: {res_1.converged}")
#

# Build system

grid = gce.MultiCircuit()

# Buses
bus1 = gce.Bus(name="Bus1", Vnom=20)
bus2 = gce.Bus(name="Bus2", Vnom=20)
bus3 = gce.Bus(name="Bus3", Vnom=20)
bus4 = gce.Bus(name="Bus4", Vnom=20)
bus5 = gce.Bus(name="Bus5", Vnom=230)
bus6 = gce.Bus(name="Bus6", Vnom=230)
bus7 = gce.Bus(name="Bus7", Vnom=230)
bus8 = gce.Bus(name="Bus8", Vnom=230)
bus9 = gce.Bus(name="Bus9", Vnom=230)
bus10 = gce.Bus(name="Bus10", Vnom=230)
bus11 = gce.Bus(name="Bus11", Vnom=230)

grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus3)
grid.add_bus(bus4)
grid.add_bus(bus5)
grid.add_bus(bus6)
grid.add_bus(bus7)
grid.add_bus(bus8)
grid.add_bus(bus9)
grid.add_bus(bus10)
grid.add_bus(bus11)

# Line
line0 = grid.add_line(
    gce.Line(name="line 5-6-1", bus_from=bus5, bus_to=bus6,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0))

line1 = grid.add_line(
    gce.Line(name="line 5-6-2", bus_from=bus5, bus_to=bus6,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0))

line2 = grid.add_line(
    gce.Line(name="line 6-7-1", bus_from=bus6, bus_to=bus7,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line3 = grid.add_line(
    gce.Line(name="line 6-7-2", bus_from=bus6, bus_to=bus7,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line4 = grid.add_line(
    gce.Line(name="line 6-7-3", bus_from=bus6, bus_to=bus7,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line5 = grid.add_line(
    gce.Line(name="line 7-8-1", bus_from=bus7, bus_to=bus8,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0))

line6 = grid.add_line(
    gce.Line(name="line 7-8-2", bus_from=bus7, bus_to=bus8,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0))

line7 = grid.add_line(
    gce.Line(name="line 8-9-1", bus_from=bus8, bus_to=bus9,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0))

line8 = grid.add_line(
    gce.Line(name="line 8-9-2", bus_from=bus8, bus_to=bus9,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0))

line9 = grid.add_line(
    gce.Line(name="line 9-10-1", bus_from=bus9, bus_to=bus10,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line10 = grid.add_line(
    gce.Line(name="line 9-10-2", bus_from=bus9, bus_to=bus10,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line11 = grid.add_line(
    gce.Line(name="line 9-10-3", bus_from=bus9, bus_to=bus10,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0))

line12 = grid.add_line(
    gce.Line(name="line 10-11-1", bus_from=bus10, bus_to=bus11,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0))

line13 = grid.add_line(
    gce.Line(name="line 10-11-2", bus_from=bus10, bus_to=bus11,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0))

# Transformers

trafo_G1 = grid.add_line(
    gce.Line(name="trafo 5-1", bus_from=bus5, bus_to=bus1,
             r=0.00000, x=0.15 * (100.0/900.0), b=0.0, rate=900.0))

trafo_G2 = grid.add_line(
    gce.Line(name="trafo 6-2", bus_from=bus6, bus_to=bus2,
             r=0.00000, x=0.15 * (100.0/900.0), b=0.0, rate=900.0))

trafo_G3 = grid.add_line(
    gce.Line(name="trafo 11-3", bus_from=bus11, bus_to=bus3,
             r=0.00000, x=0.15 * (100.0/900.0), b=0.0, rate=900.0))

trafo_G4 = grid.add_line(
    gce.Line(name="trafo 10-4", bus_from=bus10, bus_to=bus4,
             r=0.00000, x=0.15 * (100.0/900.0), b=0.0, rate=900.0))

# load
load1 = grid.add_load(bus=bus7, api_obj=gce.Load(P=967.0, Q=100.0))

load2 = grid.add_load(bus=bus9, api_obj=gce.Load(P=1767.0, Q=100.0))
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

# Generators
gen1 = gce.Generator(
    name="Gen1", P=700.0, vset=1.03, Snom=900.0,
    x1=0.0333333, r1=0.0, freq=60.0,
    # vf=1.0,
    # tm0=700.0/900.0,   # ≈ 0.7778
    tm0=6.9999999999011875,
    vf=1.1441074098644528,
    M=117.0, D=90.0,
    omega_ref=1.0,
    Kp=0.0, Ki=0.0
)

gen2 = gce.Generator(
    name="Gen2", P=700.0, vset=1.01, Snom=900.0,
    x1=0.0333333, r1=0.0, freq=60.0,
    # vf=1.0,
    # tm0=700.0/900.0,   # ≈ 0.7778
    tm0=6.9999999993318305,
    vf=1.1876079575330167,
    M=117.0, D=90.0,
    omega_ref=1.0,
    Kp=0.0, Ki=0.0
)

gen3 = gce.Generator(
    name="Gen3", P=719.091, vset=1.03, Snom=900.0,
    x1=0.0333333, r1=0.0, freq=60.0,
    # vf=1.0,
    # tm0=719.091/900.0,  # ≈ 0.7990
    tm0=7.377782468876932,
    vf=1.1785186916596406,
    M=111.15, D=90.0,
    omega_ref=1.0,
    Kp=0.0, Ki=0.0
)

gen4 = gce.Generator(
    name="Gen4", P=700.0, vset=1.01, Snom=900.0,
    x1=0.0333333, r1=0.0, freq=60.0,
    # vf=1.0,
    # tm0=700.0/900.0,   # ≈ 0.7778
    tm0=6.999999888676741,
    vf=1.163396359978149,
    M=111.15, D=90.0,
    omega_ref=1.0,
    Kp=0.0, Ki=0.0
)


grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_generator(bus=bus2, api_obj=gen2)
grid.add_generator(bus=bus3, api_obj=gen3)
grid.add_generator(bus=bus4, api_obj=gen4)
# # Run power flow

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

# # Print results
print(res.get_bus_df())
print(res.get_branch_df())
print(f"Converged: {res.converged}")

# ----------------------------------------------------------------------------------------------------------------------
# Time Domain Simulation
# ----------------------------------------------------------------------------------------------------------------------
# ----------
# Constants
# ----------

# General
pi = Const(math.pi)

# Generators
fn_1 = Const(60.0)
M_1 = Const(13.0 * 9.0)
D_1 = Const(10.0 * 9.0)
ra_1 = Const(0.0)
xd_1 = Const(0.3 * 100.0 / 900.0)
omega_ref_1 = Const(1.0)
Kp_1 = Const(0.0)
Ki_1 = Const(0.0)

fn_2 = Const(60.0)
M_2 = Const(13.0 * 9.0)
D_2 = Const(10.0 * 9.0)
ra_2 = Const(0.0)
xd_2 = Const(0.3 * 100.0 / 900.0)
omega_ref_2 = Const(1.0)
Kp_2 = Const(0.0)
Ki_2 = Const(0.0)

fn_3 = Const(60.0)
M_3 = Const(12.35 * 9.0)
D_3 = Const(10.0 * 9.0)
ra_3 = Const(0.0)
xd_3 = Const(0.3 * 100.0 / 900.0)
omega_ref_3 = Const(1.0)
Kp_3 = Const(0.0)
Ki_3 = Const(0.0)

fn_4 = Const(60.0)
M_4 = Const(12.35 * 9.0)
D_4 = Const(10.0 * 9.0)
ra_4 = Const(0.0)
xd_4 = Const(0.3 * 100.0 / 900.0)
omega_ref_4 = Const(1.0)
Kp_4 = Const(0.0)
Ki_4 = Const(0.0)

# Lines
r_0, x_0, bsh_0 = 0.005,   0.05,   0.02187
r_1, x_1, bsh_1 = 0.005,   0.05,   0.02187
r_2, x_2, bsh_2 = 0.003,   0.03,   0.00583
r_3, x_3, bsh_3 = 0.003,   0.03,   0.00583
r_4, x_4, bsh_4 = 0.003,   0.03,   0.00583
r_5, x_5, bsh_5 = 0.011, 0.11, 0.19250
r_6, x_6, bsh_6 = 0.011, 0.11, 0.19250
r_7, x_7, bsh_7 = 0.011, 0.11, 0.19250
r_8, x_8, bsh_8 = 0.011, 0.11, 0.19250
r_9, x_9, bsh_9 = 0.003,   0.03,   0.00583
r_10, x_10, bsh_10 = 0.003,   0.03,   0.00583
r_11, x_11, bsh_11 = 0.003,   0.03,   0.00583
r_12, x_12, bsh_12 = 0.005,   0.05,   0.02187
r_13, x_13, bsh_13 = 0.005,   0.05,   0.02187

def compute_gb(r, x):
    denominator = r + 1j*x
    y = 1 / denominator
    return y.real, y.imag

g_0, b_0 = compute_gb(r_0, x_0)
g_1, b_1 = compute_gb(r_1, x_1)
g_2, b_2 = compute_gb(r_2, x_2)
g_3, b_3 = compute_gb(r_3, x_3)
g_4, b_4 = compute_gb(r_4, x_4)
g_5, b_5 = compute_gb(r_5, x_5)
g_6, b_6 = compute_gb(r_6, x_6)
g_7, b_7 = compute_gb(r_7, x_7)
g_8, b_8 = compute_gb(r_8, x_8)
g_9, b_9 = compute_gb(r_9, x_9)
g_10, b_10 = compute_gb(r_10, x_10)
g_11, b_11 = compute_gb(r_11, x_11)
g_12, b_12 = compute_gb(r_12, x_12)
g_13, b_13 = compute_gb(r_13, x_13)

# Transformers
r_G1, x_G1, bsh_G1 = 0.0,  0.15 * (100.0/900.0),  0.0 # From Trafo base to System base
r_G2, x_G2, bsh_G2 = 0.0,  0.15 * (100.0/900.0),  0.0 # From Trafo base to System base
r_G3, x_G3, bsh_G3 = 0.0,  0.15 * (100.0/900.0),  0.0 # From Trafo base to System base
r_G4, x_G4, bsh_G4 = 0.0,  0.15 * (100.0/900.0),  0.0 # From Trafo base to System base

g_G1, b_G1 = compute_gb(r_G1, x_G1)
g_G2, b_G2 = compute_gb(r_G2, x_G2)
g_G3, b_G3 = compute_gb(r_G3, x_G3)
g_G4, b_G4 = compute_gb(r_G4, x_G4)

# ---------------
# Initialiazation
# ---------------
# Voltages
v1 = res.voltage[0]
v2 = res.voltage[1]
v3 = res.voltage[2]
v4 = res.voltage[3]
v5 = res.voltage[4]
v6 = res.voltage[5]
v7 = res.voltage[6]
v8 = res.voltage[7]
v9 = res.voltage[8]
v10 = res.voltage[9]
v11 = res.voltage[10]

# Normalize
Sbus = res.Sbus / grid.Sbase
Sf = res.Sf / grid.Sbase
St = res.St / grid.Sbase

Sb1 = Sbus[0] 
Sb2 = Sbus[1] 
Sb3 = Sbus[2] 
Sb4 = Sbus[3] 
Sb5 = Sbus[4] 
Sb6 = Sbus[5] 
Sb7 = Sbus[6] 
Sb8 = Sbus[7] 
Sb9 = Sbus[8] 
Sb10 = Sbus[9] 
Sb11 = Sbus[10] 

Pf0_0 = Sf[0].real
Qf0_0 = Sf[0].imag
Pt0_0 = St[0].real
Qt0_0 = St[0].imag

Pf0_1 = Sf[1].real
Qf0_1 = Sf[1].imag
Pt0_1 = St[1].real
Qt0_1 = St[1].imag

Pf0_2 = Sf[2].real
Qf0_2 = Sf[2].imag
Pt0_2 = St[2].real
Qt0_2 = St[2].imag

Pf0_3 = Sf[3].real
Qf0_3 = Sf[3].imag
Pt0_3 = St[3].real
Qt0_3 = St[3].imag

Pf0_4 = Sf[4].real
Qf0_4 = Sf[4].imag
Pt0_4 = St[4].real
Qt0_4 = St[4].imag

Pf0_5 = Sf[5].real
Qf0_5 = Sf[5].imag
Pt0_5 = St[5].real
Qt0_5 = St[5].imag

Pf0_6 = Sf[6].real
Qf0_6 = Sf[6].imag
Pt0_6 = St[6].real
Qt0_6 = St[6].imag

Pf0_7 = Sf[7].real
Qf0_7 = Sf[7].imag
Pt0_7 = St[7].real
Qt0_7 = St[7].imag

Pf0_8 = Sf[8].real
Qf0_8 = Sf[8].imag
Pt0_8 = St[8].real
Qt0_8 = St[8].imag

Pf0_9 = Sf[9].real
Qf0_9 = Sf[9].imag
Pt0_9 = St[9].real
Qt0_9 = St[9].imag

Pf0_10 = Sf[10].real
Qf0_10 = Sf[10].imag
Pt0_10 = St[10].real
Qt0_10 = St[10].imag

Pf0_11 = Sf[11].real
Qf0_11 = Sf[11].imag
Pt0_11 = St[11].real
Qt0_11 = St[11].imag

Pf0_12 = Sf[12].real
Qf0_12 = Sf[12].imag
Pt0_12 = St[12].real
Qt0_12 = St[12].imag

Pf0_13 = Sf[13].real
Qf0_13 = Sf[13].imag
Pt0_13 = St[13].real
Qt0_13 = St[13].imag

Pf0_G1 = Sf[14].real
Qf0_G1 = Sf[14].imag
Pt0_G1 = St[14].real
Qt0_G1 = St[14].imag

Pf0_G2 = Sf[15].real
Qf0_G2 = Sf[15].imag
Pt0_G2 = St[15].real
Qt0_G2 = St[15].imag

Pf0_G3 = Sf[16].real
Qf0_G3 = Sf[16].imag
Pt0_G3 = St[16].real
Qt0_G3 = St[16].imag

Pf0_G4 = Sf[17].real
Qf0_G4 = Sf[17].imag
Pt0_G4 = St[17].real
Qt0_G4 = St[17].imag

# Generator
# Current from power and voltage
i1 = np.conj(Sb1 / v1)          # ī = (p - jq) / v̄*
i2 = np.conj(Sb2 / v2)          # ī = (p - jq) / v̄*
i3 = np.conj(Sb3 / v3)          # ī = (p - jq) / v̄*
i4 = np.conj(Sb4 / v4)          # ī = (p - jq) / v̄*
# Delta angle
E_1 = v1 + (ra_1.value + 1j * xd_1.value) * i1
E_2 = v2 + (ra_2.value + 1j * xd_2.value) * i2
E_3 = v3 + (ra_3.value + 1j * xd_3.value) * i3
E_4 = v4 + (ra_4.value + 1j * xd_4.value) * i4

deltac_1 = np.log(E_1 / np.abs(E_1))
deltac_2 = np.log(E_2 / np.abs(E_2))
deltac_3 = np.log(E_3 / np.abs(E_3))
deltac_4 = np.log(E_4 / np.abs(E_4))

delta0_1 = np.imag(deltac_1)
delta0_2 = np.imag(deltac_2)
delta0_3 = np.imag(deltac_3)
delta0_4 = np.imag(deltac_4)

# dq0 rotation
rot_1 = np.exp(-1j * (delta0_1 - np.pi/2))
rot_2 = np.exp(-1j * (delta0_2 - np.pi/2))
rot_3 = np.exp(-1j * (delta0_3 - np.pi/2))
rot_4 = np.exp(-1j * (delta0_4 - np.pi/2))

# dq voltages and currents
v_d0_1 = np.real(v1*rot_1)
v_q0_1 = np.imag(v1*rot_1)
i_d0_1 = np.real(i1*rot_1)
i_q0_1 = np.imag(i1*rot_1)
psid0_1 = ra_1.value * i_q0_1 + v_q0_1
psiq0_1 = -ra_1.value * i_d0_1 - v_d0_1
vf0_1 = psid0_1 + xd_1.value * i_d0_1
te0_1 = psid0_1 * i_q0_1 - psiq0_1 * i_d0_1

v_d0_2 = np.real(v2 * rot_2)
v_q0_2 = np.imag(v2 * rot_2)
i_d0_2 = np.real(i2 * rot_2)
i_q0_2 = np.imag(i2 * rot_2)
psid0_2 = ra_2.value * i_q0_2 + v_q0_2
psiq0_2 = -ra_2.value * i_d0_2 - v_d0_2
vf0_2 = psid0_2 + xd_2.value * i_d0_2
te0_2 = psid0_2 * i_q0_2 - psiq0_2 * i_d0_2

v_d0_3 = np.real(v3 * rot_3)
v_q0_3 = np.imag(v3 * rot_3)
i_d0_3 = np.real(i3 * rot_3)
i_q0_3 = np.imag(i3 * rot_3)
psid0_3 = ra_3.value * i_q0_3 + v_q0_3
psiq0_3 = -ra_3.value * i_d0_3 - v_d0_3
vf0_3 = psid0_3 + xd_3.value * i_d0_3
te0_3 = psid0_3 * i_q0_3 - psiq0_3 * i_d0_3

v_d0_4 = np.real(v4 * rot_4)
v_q0_4 = np.imag(v4 * rot_4)
i_d0_4 = np.real(i4 * rot_4)
i_q0_4 = np.imag(i4 * rot_4)
psid0_4 = ra_4.value * i_q0_4 + v_q0_4
psiq0_4 = -ra_4.value * i_d0_4 - v_d0_4
vf0_4 = psid0_4 + xd_4.value * i_d0_4
te0_4 = psid0_4 * i_q0_4 - psiq0_4 * i_d0_4

# ----------------------------------------------------------------------------------------------------------------------
# ----------
# Variables
# ----------

t = Var("t")


# Line 0
Pline_from_0 = Var("Pline_from_0")
Qline_from_0 = Var("Qline_from_0")
Vline_from_0 = Var("Vline_from_0")
dline_from_0 = Var("dline_from_0")
Pline_to_0 = Var("Pline_to_0")
Qline_to_0 = Var("Qline_to_0")
Vline_to_0 = Var("Vline_to_0")
dline_to_0 = Var("dline_to_0")

# Line 1
Pline_from_1 = Var("Pline_from_1")
Qline_from_1 = Var("Qline_from_1")
Vline_from_1 = Var("Vline_from_1")
dline_from_1 = Var("dline_from_1")
Pline_to_1 = Var("Pline_to_1")
Qline_to_1 = Var("Qline_to_1")
Vline_to_1 = Var("Vline_to_1")
dline_to_1 = Var("dline_to_1")

# Line 2
Pline_from_2 = Var("Pline_from_2")
Qline_from_2 = Var("Qline_from_2")
Vline_from_2 = Var("Vline_from_2")
dline_from_2 = Var("dline_from_2")
Pline_to_2 = Var("Pline_to_2")
Qline_to_2 = Var("Qline_to_2")
Vline_to_2 = Var("Vline_to_2")
dline_to_2 = Var("dline_to_2")

# Line 3
Pline_from_3 = Var("Pline_from_3")
Qline_from_3 = Var("Qline_from_3")
Vline_from_3 = Var("Vline_from_3")
dline_from_3 = Var("dline_from_3")
Pline_to_3 = Var("Pline_to_3")
Qline_to_3 = Var("Qline_to_3")
Vline_to_3 = Var("Vline_to_3")
dline_to_3 = Var("dline_to_3")

# Line 4
Pline_from_4 = Var("Pline_from_4")
Qline_from_4 = Var("Qline_from_4")
Vline_from_4 = Var("Vline_from_4")
dline_from_4 = Var("dline_from_4")
Pline_to_4 = Var("Pline_to_4")
Qline_to_4 = Var("Qline_to_4")
Vline_to_4 = Var("Vline_to_4")
dline_to_4 = Var("dline_to_4")

# Line 5
Pline_from_5 = Var("Pline_from_5")
Qline_from_5 = Var("Qline_from_5")
Vline_from_5 = Var("Vline_from_5")
dline_from_5 = Var("dline_from_5")
Pline_to_5 = Var("Pline_to_5")
Qline_to_5 = Var("Qline_to_5")
Vline_to_5 = Var("Vline_to_5")
dline_to_5 = Var("dline_to_5")

# Line 6
Pline_from_6 = Var("Pline_from_6")
Qline_from_6 = Var("Qline_from_6")
Vline_from_6 = Var("Vline_from_6")
dline_from_6 = Var("dline_from_6")
Pline_to_6 = Var("Pline_to_6")
Qline_to_6 = Var("Qline_to_6")
Vline_to_6 = Var("Vline_to_6")
dline_to_6 = Var("dline_to_6")

# Line 7
Pline_from_7 = Var("Pline_from_7")
Qline_from_7 = Var("Qline_from_7")
Vline_from_7 = Var("Vline_from_7")
dline_from_7 = Var("dline_from_7")
Pline_to_7 = Var("Pline_to_7")
Qline_to_7 = Var("Qline_to_7")
Vline_to_7 = Var("Vline_to_7")
dline_to_7 = Var("dline_to_7")

# Line 8
Pline_from_8 = Var("Pline_from_8")
Qline_from_8 = Var("Qline_from_8")
Vline_from_8 = Var("Vline_from_8")
dline_from_8 = Var("dline_from_8")
Pline_to_8 = Var("Pline_to_8")
Qline_to_8 = Var("Qline_to_8")
Vline_to_8 = Var("Vline_to_8")
dline_to_8 = Var("dline_to_8")

# Line 9
Pline_from_9 = Var("Pline_from_9")
Qline_from_9 = Var("Qline_from_9")
Vline_from_9 = Var("Vline_from_9")
dline_from_9 = Var("dline_from_9")
Pline_to_9 = Var("Pline_to_9")
Qline_to_9 = Var("Qline_to_9")
Vline_to_9 = Var("Vline_to_9")
dline_to_9 = Var("dline_to_9")

# Line 10
Pline_from_10 = Var("Pline_from_10")
Qline_from_10 = Var("Qline_from_10")
Vline_from_10 = Var("Vline_from_10")
dline_from_10 = Var("dline_from_10")
Pline_to_10 = Var("Pline_to_10")
Qline_to_10 = Var("Qline_to_10")
Vline_to_10 = Var("Vline_to_10")
dline_to_10 = Var("dline_to_10")

# Line 11
Pline_from_11 = Var("Pline_from_11")
Qline_from_11 = Var("Qline_from_11")
Vline_from_11 = Var("Vline_from_11")
dline_from_11 = Var("dline_from_11")
Pline_to_11 = Var("Pline_to_11")
Qline_to_11 = Var("Qline_to_11")
Vline_to_11 = Var("Vline_to_11")
dline_to_11 = Var("dline_to_11")

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
Pline_from_13 = Var("Pline_from_13")
Qline_from_13 = Var("Qline_from_13")
Vline_from_13 = Var("Vline_from_13")
dline_from_13 = Var("dline_from_13")
Pline_to_13 = Var("Pline_to_13")
Qline_to_13 = Var("Qline_to_13")
Vline_to_13 = Var("Vline_to_13")
dline_to_13 = Var("dline_to_13")


# Line G1
Pline_from_G1 = Var("Pline_from_G1")
Qline_from_G1 = Var("Qline_from_G1")
Vline_from_G1 = Var("Vline_from_G1")
dline_from_G1 = Var("dline_from_G1")
Pline_to_G1 = Var("Pline_to_G1")
Qline_to_G1 = Var("Qline_to_G1")
Vline_to_G1 = Var("Vline_to_G1")
dline_to_G1 = Var("dline_to_G1")

# Line G2
Pline_from_G2 = Var("Pline_from_G2")
Qline_from_G2 = Var("Qline_from_G2")
Vline_from_G2 = Var("Vline_from_G2")
dline_from_G2 = Var("dline_from_G2")
Pline_to_G2 = Var("Pline_to_G2")
Qline_to_G2 = Var("Qline_to_G2")
Vline_to_G2 = Var("Vline_to_G2")
dline_to_G2 = Var("dline_to_G2")

# Line G3
Pline_from_G3 = Var("Pline_from_G3")
Qline_from_G3 = Var("Qline_from_G3")
Vline_from_G3 = Var("Vline_from_G3")
dline_from_G3 = Var("dline_from_G3")
Pline_to_G3 = Var("Pline_to_G3")
Qline_to_G3 = Var("Qline_to_G3")
Vline_to_G3 = Var("Vline_to_G3")
dline_to_G3 = Var("dline_to_G3")

# Line G4
Pline_from_G4 = Var("Pline_from_G4")
Qline_from_G4 = Var("Qline_from_G4")
Vline_from_G4 = Var("Vline_from_G4")
dline_from_G4 = Var("dline_from_G4")
Pline_to_G4 = Var("Pline_to_G4")
Qline_to_G4 = Var("Qline_to_G4")
Vline_to_G4 = Var("Vline_to_G4")
dline_to_G4 = Var("dline_to_G4")

# Gencls 1
delta_1 = Var("delta_1")
omega_1 = Var("omega_1")
et_1 = Var("et_1")
psid_1 = Var("psid_1")
psiq_1 = Var("psiq_1")
i_d_1 = Var("i_d_1")
i_q_1 = Var("i_q_1")
v_d_1 = Var("v_d_1")
v_q_1 = Var("v_q_1")
te_1 = Var("te_1")
tm_1 = Var("tm_1")
P_G1 = Var("P_G1")
Q_G1 = Var("Q_G1")
V_G1 = Var("V_G1")
d_G1 = Var("d_G1")

# Gencls 2
delta_2 = Var("delta_2")
omega_2 = Var("omega_2")
et_2 = Var("et_2")
psid_2 = Var("psid_2")
psiq_2 = Var("psiq_2")
i_d_2 = Var("i_d_2")
i_q_2 = Var("i_q_2")
v_d_2 = Var("v_d_2")
v_q_2 = Var("v_q_2")
te_2 = Var("te_2")
tm_2 = Var("tm_2")
P_G2 = Var("P_G2")
Q_G2 = Var("Q_G2")
V_G2 = Var("V_G2")
d_G2 = Var("d_G2")

# Gencls 3
delta_3 = Var("delta_3")
omega_3 = Var("omega_3")
et_3 = Var("et_3")
psid_3 = Var("psid_3")
psiq_3 = Var("psiq_3")
i_d_3 = Var("i_d_3")
i_q_3 = Var("i_q_3")
v_d_3 = Var("v_d_3")
v_q_3 = Var("v_q_3")
te_3 = Var("te_3")
tm_3 = Var("tm_3")
P_G3 = Var("P_G3")
Q_G3 = Var("Q_G3")
V_G3 = Var("V_G3")
d_G3 = Var("d_G3")

# Gencls 4
delta_4 = Var("delta_4")
omega_4 = Var("omega_4")
et_4 = Var("et_4")
psid_4 = Var("psid_4")
psiq_4 = Var("psiq_4")
i_d_4 = Var("i_d_4")
i_q_4 = Var("i_q_4")
v_d_4 = Var("v_d_4")
v_q_4 = Var("v_q_4")
te_4 = Var("te_4")
tm_4 = Var("tm_4")
P_G4 = Var("P_G4")
Q_G4 = Var("Q_G4")
V_G4 = Var("V_G4")
d_G4 = Var("d_G4")

# Load 7
Pload_7 = Var("Pload_7")
Qload_7 = Var("Qload_7")

# Load 9
Pload_9 = Var("Pload_9")
Qload_9 = Var("Qload_9")

# # Shunt 7
# Pshunt_7 = Var("Pshunt_7")
# Qshunt_7 = Var("Qshunt_7")
#
# # Shunt 9
# Pshunt_9 = Var("Pshunt_9")
# Qshunt_9 = Var("Qshunt_9")

# -----------------------------------------------------
# Buses
# -----------------------------------------------------
bus1_block = Block(
    algebraic_eqs=[
        P_G1 - Pline_to_G1,
        Q_G1 - Qline_to_G1,
        V_G1 - Vline_to_G1,
        d_G1 - dline_to_G1
    ],
    algebraic_vars=[Pline_to_G1, Qline_to_G1, V_G1, d_G1]
)

bus2_block = Block(
    algebraic_eqs=[
        P_G2 - Pline_to_G2,
        Q_G2 - Qline_to_G2,
        V_G2 - Vline_to_G2,
        d_G2 - dline_to_G2
    ],
    algebraic_vars=[Pline_to_G2, Qline_to_G2, V_G2, d_G2]
)

bus3_block = Block(
    algebraic_eqs=[
        P_G3 - Pline_to_G3,
        Q_G3 - Qline_to_G3,
        V_G3 - Vline_to_G3,
        d_G3 - dline_to_G3
    ],
    algebraic_vars=[Pline_to_G3, Qline_to_G3, V_G3, d_G3]
)

bus4_block = Block(
    algebraic_eqs=[
        P_G4 - Pline_to_G4,
        Q_G4 - Qline_to_G4,
        V_G4 - Vline_to_G4,
        d_G4 - dline_to_G4
    ],
    algebraic_vars=[Pline_to_G4, Qline_to_G4, V_G4, d_G4]
)

bus5_block = Block(
    algebraic_eqs=[
        - Pline_from_0 - Pline_from_1 - Pline_from_G1,
        - Qline_from_0 - Qline_from_1 - Qline_from_G1,
        Vline_from_G1 - Vline_from_0,
        Vline_from_G1 - Vline_from_1,
        dline_from_G1 - dline_from_0,
        dline_from_G1 - dline_from_1
    ],
    algebraic_vars=[Pline_from_0, Pline_from_1, Pline_from_G1, Qline_from_0, Qline_from_1, Qline_from_G1]
)

bus6_block = Block(
    algebraic_eqs=[
        - Pline_from_2 - Pline_from_3 - Pline_from_4 - Pline_from_G2 - Pline_to_1 - Pline_to_0,
        - Qline_from_2 - Qline_from_3 - Qline_from_4 - Qline_from_G2 - Qline_to_1 - Qline_to_0,
        Vline_from_G2 - Vline_from_2,
        Vline_from_G2 - Vline_from_3,
        Vline_from_G2 - Vline_to_0,
        Vline_from_G2 - Vline_to_1,
        Vline_from_G2 - Vline_from_4,
        dline_from_G2 - dline_from_2,
        dline_from_G2 - dline_from_3,
        dline_from_G2 - dline_to_0,
        dline_from_G2 - dline_to_1,
        dline_from_G2 - dline_from_4
    ],
    algebraic_vars=[Pline_from_2, Pline_from_3, Pline_from_4, Pline_from_G2, Pline_to_1, Pline_to_0, Qline_from_2, Qline_from_3, Qline_from_4, Qline_from_G2, Qline_to_1, Qline_to_0]
)

bus7_block = Block(
    algebraic_eqs=[
        - Pline_to_2 - Pline_to_3 - Pline_to_4 - Pline_from_5 - Pline_from_6 + Pload_7, #
        - Qline_to_2 - Qline_to_3 - Qline_to_4 - Qline_from_5 - Qline_from_6 + Qload_7, #
        Vline_to_2 - Vline_from_5,
        Vline_to_2 - Vline_from_6,
        Vline_to_2 - Vline_to_3,
        Vline_to_2 - Vline_to_4,
        dline_to_2 - dline_from_5,
        dline_to_2 - dline_from_6,
        dline_to_2 - dline_to_3,
        dline_to_2 - dline_to_4
    ],
    algebraic_vars=[Pline_to_2, Pline_to_3, Pline_to_4, Pline_from_5, Pline_from_6, Qline_to_2, Qline_to_3, Qline_to_4, Qline_from_5, Qline_from_6]
)

bus8_block = Block(
    algebraic_eqs=[
        - Pline_to_5 - Pline_to_6 - Pline_from_7 - Pline_from_8,
        - Qline_to_5 - Qline_to_6 - Qline_from_7 - Qline_from_8,
        Vline_to_5 - Vline_from_7,
        Vline_to_5 - Vline_from_8,
        Vline_to_5 - Vline_to_6,
        dline_to_5 - dline_from_7,
        dline_to_5 - dline_from_8,
        dline_to_5 - dline_to_6
    ],
    algebraic_vars=[Pline_to_5, Pline_to_6, Pline_from_7, Pline_from_8, Qline_to_5, Qline_to_6, Qline_from_7, Qline_from_8]
)

bus9_block = Block(
    algebraic_eqs=[
        - Pline_to_7 - Pline_to_8 - Pline_from_9 - Pline_from_10 - Pline_from_11 + Pload_9, #
        - Qline_to_7 - Qline_to_8 - Qline_from_9 - Qline_from_10 - Qline_from_11 + Qload_9, #
        Vline_to_7 - Vline_from_9,
        Vline_to_7 - Vline_from_10,
        Vline_to_7 - Vline_from_11,
        Vline_to_7 - Vline_to_8,
        dline_to_7 - dline_from_9,
        dline_to_7 - dline_from_10,
        dline_to_7 - dline_from_11,
        dline_to_7 - dline_to_8
    ],
    algebraic_vars=[Pline_to_7, Pline_to_8, Pline_from_9, Pline_from_10, Pline_from_11, Qline_to_7, Qline_to_8, Qline_from_9, Qline_from_10, Qline_from_11]
)

bus10_block = Block(
    algebraic_eqs=[
        - Pline_to_9 - Pline_to_10 - Pline_to_11 - Pline_from_G4 - Pline_from_12 - Pline_from_13,
        - Qline_to_9 - Qline_to_10 - Qline_to_11 - Qline_from_G4 - Qline_from_12 - Qline_from_13,
        Vline_from_G4 - Vline_to_9,
        Vline_from_G4 - Vline_to_10,
        Vline_from_G4 - Vline_to_11,
        Vline_from_G4 - Vline_from_12,
        Vline_from_G4 - Vline_from_13,
        dline_from_G4 - dline_to_9,
        dline_from_G4 - dline_to_10,
        dline_from_G4 - dline_to_11,
        dline_from_G4 - dline_from_12,
        dline_from_G4 - dline_from_13
    ],
    algebraic_vars=[Pline_to_9, Pline_to_10, Pline_to_11, Pline_from_G4, Pline_from_12, Pline_from_13, Qline_to_9, Qline_to_10, Qline_to_11, Qline_from_G4, Qline_from_12, Qline_from_13]
)

bus11_block = Block(
    algebraic_eqs=[
        - Pline_to_12 - Pline_to_13 - Pline_from_G3,
        - Qline_to_12 - Qline_to_13 - Qline_from_G3,
        Vline_from_G3 - Vline_to_12,
        Vline_from_G3 - Vline_to_13,
        dline_from_G3 - dline_to_12,
        dline_from_G3 - dline_to_13
    ],
    algebraic_vars=[Pline_to_12, Pline_to_13, Pline_from_G3, Qline_to_12, Qline_to_13, Qline_from_G3]
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

line_G1_block = Block(
    algebraic_eqs=[
        Pline_from_G1 - ((Vline_from_G1 ** 2 * g_G1) - g_G1 * Vline_from_G1 * Vline_to_G1 * cos(
            dline_from_G1 - dline_to_G1) + b_G1 * Vline_from_G1 * Vline_to_G1 * cos(dline_from_G1 - dline_to_G1 + np.pi / 2)),
        Qline_from_G1 - (Vline_from_G1 ** 2 * (-bsh_G1 / 2 - b_G1) - g_G1 * Vline_from_G1 * Vline_to_G1 * sin(
            dline_from_G1 - dline_to_G1) + b_G1 * Vline_from_G1 * Vline_to_G1 * sin(dline_from_G1 - dline_to_G1 + np.pi / 2)),
        Pline_to_G1 - ((Vline_to_G1 ** 2 * g_G1) - g_G1 * Vline_to_G1 * Vline_from_G1 * cos(
            dline_to_G1 - dline_from_G1) + b_G1 * Vline_to_G1 * Vline_from_G1 * cos(dline_to_G1 - dline_from_G1 + np.pi / 2)),
        Qline_to_G1 - (Vline_to_G1 ** 2 * (-bsh_G1 / 2 - b_G1) - g_G1 * Vline_to_G1 * Vline_from_G1 * sin(
            dline_to_G1 - dline_from_G1) + b_G1 * Vline_to_G1 * Vline_from_G1 * sin(dline_to_G1 - dline_from_G1 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_G1, Vline_from_G1, dline_to_G1, Vline_to_G1],
    parameters=[]
)

line_G2_block = Block(
    algebraic_eqs=[
        Pline_from_G2 - ((Vline_from_G2 ** 2 * g_G2) - g_G2 * Vline_from_G2 * Vline_to_G2 * cos(
            dline_from_G2 - dline_to_G2) + b_G2 * Vline_from_G2 * Vline_to_G2 * cos(dline_from_G2 - dline_to_G2 + np.pi / 2)),
        Qline_from_G2 - (Vline_from_G2 ** 2 * (-bsh_G2 / 2 - b_G2) - g_G2 * Vline_from_G2 * Vline_to_G2 * sin(
            dline_from_G2 - dline_to_G2) + b_G2 * Vline_from_G2 * Vline_to_G2 * sin(dline_from_G2 - dline_to_G2 + np.pi / 2)),
        Pline_to_G2 - ((Vline_to_G2 ** 2 * g_G2) - g_G2 * Vline_to_G2 * Vline_from_G2 * cos(
            dline_to_G2 - dline_from_G2) + b_G2 * Vline_to_G2 * Vline_from_G2 * cos(dline_to_G2 - dline_from_G2 + np.pi / 2)),
        Qline_to_G2 - (Vline_to_G2 ** 2 * (-bsh_G2 / 2 - b_G2) - g_G2 * Vline_to_G2 * Vline_from_G2 * sin(
            dline_to_G2 - dline_from_G2) + b_G2 * Vline_to_G2 * Vline_from_G2 * sin(dline_to_G2 - dline_from_G2 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_G2, Vline_from_G2, dline_to_G2, Vline_to_G2],
    parameters=[]
)

line_G3_block = Block(
    algebraic_eqs=[
        Pline_from_G3 - ((Vline_from_G3 ** 2 * g_G3) - g_G3 * Vline_from_G3 * Vline_to_G3 * cos(
            dline_from_G3 - dline_to_G3) + b_G3 * Vline_from_G3 * Vline_to_G3 * cos(dline_from_G3 - dline_to_G3 + np.pi / 2)),
        Qline_from_G3 - (Vline_from_G3 ** 2 * (-bsh_G3 / 2 - b_G3) - g_G3 * Vline_from_G3 * Vline_to_G3 * sin(
            dline_from_G3 - dline_to_G3) + b_G3 * Vline_from_G3 * Vline_to_G3 * sin(dline_from_G3 - dline_to_G3 + np.pi / 2)),
        Pline_to_G3 - ((Vline_to_G3 ** 2 * g_G3) - g_G3 * Vline_to_G3 * Vline_from_G3 * cos(
            dline_to_G3 - dline_from_G3) + b_G3 * Vline_to_G3 * Vline_from_G3 * cos(dline_to_G3 - dline_from_G3 + np.pi / 2)),
        Qline_to_G3 - (Vline_to_G3 ** 2 * (-bsh_G3 / 2 - b_G3) - g_G3 * Vline_to_G3 * Vline_from_G3 * sin(
            dline_to_G3 - dline_from_G3) + b_G3 * Vline_to_G3 * Vline_from_G3 * sin(dline_to_G3 - dline_from_G3 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_G3, Vline_from_G3, dline_to_G3, Vline_to_G3],
    parameters=[]
)

line_G4_block = Block(
    algebraic_eqs=[
        Pline_from_G4 - ((Vline_from_G4 ** 2 * g_G4) - g_G4 * Vline_from_G4 * Vline_to_G4 * cos(
            dline_from_G4 - dline_to_G4) + b_G4 * Vline_from_G4 * Vline_to_G4 * cos(dline_from_G4 - dline_to_G4 + np.pi / 2)),
        Qline_from_G4 - (Vline_from_G4 ** 2 * (-bsh_G4 / 2 - b_G4) - g_G4 * Vline_from_G4 * Vline_to_G4 * sin(
            dline_from_G4 - dline_to_G4) + b_G4 * Vline_from_G4 * Vline_to_G4 * sin(dline_from_G4 - dline_to_G4 + np.pi / 2)),
        Pline_to_G4 - ((Vline_to_G4 ** 2 * g_G4) - g_G4 * Vline_to_G4 * Vline_from_G4 * cos(
            dline_to_G4 - dline_from_G4) + b_G4 * Vline_to_G4 * Vline_from_G4 * cos(dline_to_G4 - dline_from_G4 + np.pi / 2)),
        Qline_to_G4 - (Vline_to_G4 ** 2 * (-bsh_G4 / 2 - b_G4) - g_G4 * Vline_to_G4 * Vline_from_G4 * sin(
            dline_to_G4 - dline_from_G4) + b_G4 * Vline_to_G4 * Vline_from_G4 * sin(dline_to_G4 - dline_from_G4 + np.pi / 2)),
    ],
    algebraic_vars=[dline_from_G4, Vline_from_G4, dline_to_G4, Vline_to_G4],
    parameters=[]
)


# -----------
# Generators
# -----------
tm0_1 = Const(te0_1)
print("tm0_1")
print(tm0_1)
vf_1  = Const(vf0_1)
print("vf_1")
print(vf_1)
tm0_2 = Const(te0_2)
print("tm0_2")
print(tm0_2)
vf_2  = Const(vf0_2)
print("vf_2")
print(vf_2)
tm0_3 = Const(te0_3)
print("tm0_3")
print(tm0_3)
vf_3  = Const(vf0_3)
print("vf_3")
print(vf_3)
tm0_4 = Const(te0_4)
print("tm0_4")
print(tm0_4)
vf_4  = Const(vf0_4)
print("vf_4")
print(vf_4)

generator_block_1 = Block(
    state_eqs=[
        (2 * pi * fn_1) * (omega_1 - omega_ref_1),
        (tm_1 - te_1 - D_1 * (omega_1 - omega_ref_1)) / M_1,
        (omega_1 - omega_ref_1)
    ],
    state_vars=[delta_1, omega_1, et_1], #
    algebraic_eqs=[
        psid_1 - (ra_1 * i_q_1 + v_q_1),
        psiq_1 + (ra_1 * i_d_1 + v_d_1),
        0 - (psid_1 + xd_1 * i_d_1 - vf_1),
        0 - (psiq_1 + xd_1 * i_q_1),
        v_d_1 - (V_G1 * sin(delta_1 - d_G1)),
        v_q_1 - (V_G1 * cos(delta_1 - d_G1)),
        te_1 - (psid_1 * i_q_1 - psiq_1 * i_d_1),
        P_G1 - (v_d_1 * i_d_1 + v_q_1 * i_q_1),
        Q_G1 - (v_q_1 * i_d_1 - v_d_1 * i_q_1),
        tm_1 - (tm0_1 + Kp_1 * (omega_1 - omega_ref_1) + Ki_1 * et_1)
    ],
    algebraic_vars=[psid_1, psiq_1, i_d_1, i_q_1, v_d_1, v_q_1, te_1, P_G1, Q_G1, tm_1], 
    parameters=[]
)

generator_block_2 = Block(
    state_eqs=[
        (2 * pi * fn_2) * (omega_2 - omega_ref_2),
        (tm_2 - te_2 - D_2 * (omega_2 - omega_ref_2)) / M_2,
        (omega_2 - omega_ref_2)
    ],
    state_vars=[delta_2, omega_2, et_2], #
    algebraic_eqs=[
        psid_2 - (ra_2 * i_q_2 + v_q_2),
        psiq_2 + (ra_2 * i_d_2 + v_d_2),
        0 - (psid_2 + xd_2 * i_d_2 - vf_2),
        0 - (psiq_2 + xd_2 * i_q_2),
        v_d_2 - (V_G2 * sin(delta_2 - d_G2)),
        v_q_2 - (V_G2 * cos(delta_2 - d_G2)),
        te_2 - (psid_2 * i_q_2 - psiq_2 * i_d_2),
        P_G2 - (v_d_2 * i_d_2 + v_q_2 * i_q_2),
        Q_G2 - (v_q_2 * i_d_2 - v_d_2 * i_q_2),
        tm_2 - (tm0_2 + Kp_2 * (omega_2 - omega_ref_2) + Ki_2 * et_2)
    ],
    algebraic_vars=[psid_2, psiq_2, i_d_2, i_q_2, v_d_2, v_q_2, te_2, P_G2, Q_G2, tm_2], 
    parameters=[]
)

generator_block_3 = Block(
    state_eqs=[
        (2 * pi * fn_3) * (omega_3 - omega_ref_3),
        (tm_3 - te_3 - D_3 * (omega_3 - omega_ref_3)) / M_3,
        (omega_3 - omega_ref_3),
    ],
    state_vars=[delta_3, omega_3, et_3], #
    algebraic_eqs=[
        psid_3 - (ra_3 * i_q_3 + v_q_3),
        psiq_3 + (ra_3 * i_d_3 + v_d_3),
        0 - (psid_3 + xd_3 * i_d_3 - vf_3),
        0 - (psiq_3 + xd_3 * i_q_3),
        v_d_3 - (V_G3 * sin(delta_3 - d_G3)),
        v_q_3 - (V_G3 * cos(delta_3 - d_G3)),
        te_3 - (psid_3 * i_q_3 - psiq_3 * i_d_3),
        P_G3 - (v_d_3 * i_d_3 + v_q_3 * i_q_3),
        Q_G3 - (v_q_3 * i_d_3 - v_d_3 * i_q_3),
        tm_3 - (tm0_3 + Kp_3 * (omega_3 - omega_ref_3) + Ki_3 * et_3)
    ],
    algebraic_vars=[psid_3, psiq_3, i_d_3, i_q_3, v_d_3, v_q_3, te_3, P_G3, Q_G3, tm_3],
    parameters=[]
)

generator_block_4 = Block(
    state_eqs=[
        (2 * pi * fn_4) * (omega_4 - omega_ref_4),
        (tm_4 - te_4 - D_4 * (omega_4 - omega_ref_4)) / M_4,
        (omega_4 - omega_ref_4),
    ],
    state_vars=[delta_4, omega_4, et_4], #
    algebraic_eqs=[
        psid_4 - (ra_4 * i_q_4 + v_q_4),
        psiq_4 + (ra_4 * i_d_4 + v_d_4),
        0 - (psid_4 + xd_4 * i_d_4 - vf_4),
        0 - (psiq_4 + xd_4 * i_q_4),
        v_d_4 - (V_G4 * sin(delta_4 - d_G4)),
        v_q_4 - (V_G4 * cos(delta_4 - d_G4)),
        te_4 - (psid_4 * i_q_4 - psiq_4 * i_d_4),
        P_G4 - (v_d_4 * i_d_4 + v_q_4 * i_q_4),
        Q_G4 - (v_q_4 * i_d_4 - v_d_4 * i_q_4),
        tm_4 - (tm0_4 + Kp_4 * (omega_4 - omega_ref_4) + Ki_4 * et_4)
    ],
    algebraic_vars=[psid_4, psiq_4, i_d_4, i_q_4, v_d_4, v_q_4, te_4, P_G4, Q_G4, tm_4],
    parameters=[]
)

# ------
# Shunt
# ------
# g_s7 = Const(0.0)
# b_s7 = Const(2.0)
# g_s9 = Const(0.0)
# b_s9 = Const(3.5)
# Ps0_7 = Const(np.abs(v7)**2 * g_s7.value)
# Qs0_7 = Const(np.abs(v7)**2 * b_s7.value)
# Ps0_9 = Const(np.abs(v9)**2 * g_s9.value)
# Qs0_9 = Const(np.abs(v9)**2 * b_s9.value)

# shunt_7 = Block(
#     algebraic_eqs=[
#         Pshunt_7 - g_s7 * Vline_to_2 ** 2,
#         Qshunt_7 - b_s7 * Vline_to_2 ** 2
#     ],
#     algebraic_vars=[Pshunt_7, Qshunt_7],
#     parameters=[]
# )
#
# shunt_9 = Block(
#     algebraic_eqs=[
#         Pshunt_9 - g_s9 * Vline_to_7 ** 2,
#         Qshunt_9 - b_s9 * Vline_to_7 ** 2
#     ],
#     algebraic_vars=[Pshunt_9, Qshunt_9],
#     parameters=[]
# )

# -----
# Load
# -----
Pl0_7 = Var('Pl0_7')
Pl0_7_default = Sb7.real
print("Pl0_7")
print(Pl0_7_default)
Ql0_7 = Const(Sb7.imag) #
print("Ql0_7")
print(Ql0_7)

Pl0_9 = Const(Sb9.real) #
print("Pl0_9")
print(Pl0_9)
Ql0_9 = Const(Sb9.imag) #
print("Ql0_9")
print(Ql0_9)

load_7 = Block(
    algebraic_eqs=[
        Pload_7 - Pl0_7,
        Qload_7 - Ql0_7
    ],
    algebraic_vars=[Pload_7, Qload_7],
    parameters=[Pl0_7],
    parameters_eqs=[piecewise(t, 2.0, -9.0, Pl0_7_default)],
    external_mapping={
        DynamicVarType.P: Pload_7,
        DynamicVarType.Q: Qload_7
    }
)

load_9 = Block(
    algebraic_eqs=[
        Pload_9 - Pl0_9,
        Qload_9 - Ql0_9
    ],
    algebraic_vars=[Pload_9, Qload_9],
    parameters=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# System
# ----------------------------------------------------------------------------------------------------------------------
sys = Block(
    children=[line_0_block, line_1_block, line_2_block, line_3_block, line_4_block, line_5_block, line_6_block, line_7_block, line_8_block, line_9_block, line_10_block, line_11_block, line_12_block, line_13_block, 
              line_G1_block, line_G2_block, line_G3_block, line_G4_block, 
              load_7, load_9,
              generator_block_1, generator_block_2, generator_block_3, generator_block_4, 
              bus1_block, bus2_block, bus3_block, bus4_block, bus5_block, bus6_block, bus7_block, bus8_block, bus9_block, bus10_block, bus11_block], #
    in_vars=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
start_building_system = time.time()

slv = BlockSolver(sys, t)

# params_mapping = {
#     Pl0_7: Sb7.real + Ps0_7.value , #
#     # u: 1.0
#     #Ql0: 0.1
# }
end_building_system = time.time()
print(f"Harcoded build system time = {end_building_system-start_building_system:.6f} [s]")

params_mapping = {}

vars_mapping = {

    Pline_from_0: Pf0_0,
    Qline_from_0: Qf0_0,
    Vline_from_0: np.abs(v5),
    dline_from_0: np.angle(v5),
    Pline_to_0: Pt0_0,
    Qline_to_0: Qt0_0,
    Vline_to_0: np.abs(v6),
    dline_to_0: np.angle(v6),
    
    Pline_from_1: Pf0_1,
    Qline_from_1: Qf0_1,
    Vline_from_1: np.abs(v5),
    dline_from_1: np.angle(v5),
    Pline_to_1: Pt0_1,
    Qline_to_1: Qt0_1,
    Vline_to_1: np.abs(v6),
    dline_to_1: np.angle(v6),

    Pline_from_2: Pf0_2,
    Qline_from_2: Qf0_2,
    Vline_from_2: np.abs(v6),
    dline_from_2: np.angle(v6),
    Pline_to_2: Pt0_2,
    Qline_to_2: Qt0_2,
    Vline_to_2: np.abs(v7),
    dline_to_2: np.angle(v7),

    Pline_from_3: Pf0_3,
    Qline_from_3: Qf0_3,
    Vline_from_3: np.abs(v6),
    dline_from_3: np.angle(v6),
    Pline_to_3: Pt0_3,
    Qline_to_3: Qt0_3,
    Vline_to_3: np.abs(v7),
    dline_to_3: np.angle(v7),

    Pline_from_4: Pf0_4,
    Qline_from_4: Qf0_4,
    Vline_from_4: np.abs(v6),
    dline_from_4: np.angle(v6),
    Pline_to_4: Pt0_4,
    Qline_to_4: Qt0_4,
    Vline_to_4: np.abs(v7),
    dline_to_4: np.angle(v7),

    Pline_from_5: Pf0_5,
    Qline_from_5: Qf0_5,
    Vline_from_5: np.abs(v7),
    dline_from_5: np.angle(v7),
    Pline_to_5: Pt0_5,
    Qline_to_5: Qt0_5,
    Vline_to_5: np.abs(v8),
    dline_to_5: np.angle(v8),

    Pline_from_6: Pf0_6,
    Qline_from_6: Qf0_6,
    Vline_from_6: np.abs(v7),
    dline_from_6: np.angle(v7),
    Pline_to_6: Pt0_6,
    Qline_to_6: Qt0_6,
    Vline_to_6: np.abs(v8),
    dline_to_6: np.angle(v8),

    Pline_from_7: Pf0_7,
    Qline_from_7: Qf0_7,
    Vline_from_7: np.abs(v8),
    dline_from_7: np.angle(v8),
    Pline_to_7: Pt0_7,
    Qline_to_7: Qt0_7,
    Vline_to_7:  np.abs(v9),
    dline_to_7: np.angle(v9),

    Pline_from_8: Pf0_8,
    Qline_from_8: Qf0_8,
    Vline_from_8: np.abs(v8),
    dline_from_8: np.angle(v8),
    Pline_to_8: Pt0_8,
    Qline_to_8: Qt0_8,
    Vline_to_8:  np.abs(v9),
    dline_to_8: np.angle(v9),

    Pline_from_9: Pf0_9,
    Qline_from_9: Qf0_9,
    Vline_from_9: np.abs(v9),
    dline_from_9: np.angle(v9),
    Pline_to_9: Pt0_9,
    Qline_to_9: Qt0_9,
    Vline_to_9: np.abs(v10),
    dline_to_9: np.angle(v10),

    Pline_from_10: Pf0_10,
    Qline_from_10: Qf0_10,
    Vline_from_10: np.abs(v9),
    dline_from_10: np.angle(v9),
    Pline_to_10: Pt0_10,
    Qline_to_10: Qt0_10,
    Vline_to_10: np.abs(v10),
    dline_to_10: np.angle(v10),

    Pline_from_11: Pf0_11,
    Qline_from_11: Qf0_11,
    Vline_from_11: np.abs(v9),
    dline_from_11: np.angle(v9),
    Pline_to_11: Pt0_11,
    Qline_to_11: Qt0_11,
    Vline_to_11: np.abs(v10),
    dline_to_11: np.angle(v10),

    Pline_from_12: Pf0_12,
    Qline_from_12: Qf0_12,
    Vline_from_12: np.abs(v10),
    dline_from_12: np.angle(v10),
    Pline_to_12: Pt0_12,
    Qline_to_12: Qt0_12,
    Vline_to_12: np.abs(v11),
    dline_to_12: np.angle(v11),
    
    Pline_from_13: Pf0_13,
    Qline_from_13: Qf0_13,
    Vline_from_13: np.abs(v10),
    dline_from_13: np.angle(v10),
    Pline_to_13: Pt0_13,
    Qline_to_13: Qt0_13,
    Vline_to_13: np.abs(v11),
    dline_to_13: np.angle(v11),

    Pline_from_G1: Pf0_G1,
    Qline_from_G1: Qf0_G1,
    Vline_from_G1: np.abs(v5),
    dline_from_G1: np.angle(v5),
    Pline_to_G1: Pt0_G1,
    Qline_to_G1: Qt0_G1,
    Vline_to_G1: np.abs(v1),
    dline_to_G1: np.angle(v1),

    Pline_from_G2: Pf0_G2,
    Qline_from_G2: Qf0_G2,
    Vline_from_G2: np.abs(v6),
    dline_from_G2: np.angle(v6),
    Pline_to_G2: Pt0_G2,
    Qline_to_G2: Qt0_G2,
    Vline_to_G2: np.abs(v2),
    dline_to_G2: np.angle(v2),

    Pline_from_G3: Pf0_G3,
    Qline_from_G3: Qf0_G3,
    Vline_from_G3: np.abs(v11),
    dline_from_G3: np.angle(v11),
    Pline_to_G3: Pt0_G3,
    Qline_to_G3: Qt0_G3,
    Vline_to_G3: np.abs(v3),
    dline_to_G3: np.angle(v3),

    Pline_from_G4: Pf0_G4,
    Qline_from_G4: Qf0_G4,
    Vline_from_G4: np.abs(v10),
    dline_from_G4: np.angle(v10),
    Pline_to_G4: Pt0_G4,
    Qline_to_G4: Qt0_G4,
    Vline_to_G4: np.abs(v4),
    dline_to_G4: np.angle(v4),

    V_G1: np.abs(v1),
    d_G1: np.angle(v1),
    delta_1: delta0_1,
    omega_1: omega_ref_1.value,
    psid_1: psid0_1,
    psiq_1: psiq0_1,
    i_d_1: i_d0_1,
    i_q_1: i_q0_1,
    v_d_1: v_d0_1,
    v_q_1: v_q0_1,
    tm_1: te0_1,
    te_1: te0_1,
    P_G1: Sb1.real,
    Q_G1: Sb1.imag,
    et_1: 0.0,

    V_G2: np.abs(v2),
    d_G2: np.angle(v2),
    delta_2: delta0_2,
    omega_2: omega_ref_2.value,
    psid_2: psid0_2,
    psiq_2: psiq0_2,
    i_d_2: i_d0_2,
    i_q_2: i_q0_2,
    v_d_2: v_d0_2,
    v_q_2: v_q0_2,
    tm_2: te0_2,
    te_2: te0_2,
    P_G2: Sb2.real,
    Q_G2: Sb2.imag,
    et_2: 0.0,

    V_G3: np.abs(v3),
    d_G3: np.angle(v3),
    delta_3: delta0_3,
    omega_3: omega_ref_3.value,
    psid_3: psid0_3,
    psiq_3: psiq0_3,
    i_d_3: i_d0_3,
    i_q_3: i_q0_3,
    v_d_3: v_d0_3,
    v_q_3: v_q0_3,
    tm_3: te0_3,
    te_3: te0_3,
    P_G3: Sb3.real,
    Q_G3: Sb3.imag,
    et_3: 0.0,

    V_G4: np.abs(v4),
    d_G4: np.angle(v4),
    delta_4: delta0_4,
    omega_4: omega_ref_4.value,
    psid_4: psid0_4,
    psiq_4: psiq0_4,
    i_d_4: i_d0_4,
    i_q_4: i_q0_4,
    v_d_4: v_d0_4,
    v_q_4: v_q0_4,
    tm_4: te0_4,
    te_4: te0_4,
    P_G4: Sb4.real,
    Q_G4: Sb4.imag,
    et_4: 0.0,

    Pload_7: Sb7.real, #+ Ps0_7.value, #
    Qload_7: Sb7.imag, #+ Qs0_7.value, #
    Pload_9: Sb9.real, #+ Ps0_9.value, #
    Qload_9: Sb9.imag, #+ Qs0_9.value, #
}

init_guess = vars_mapping
print("init_guess")
print(init_guess)

# ---------------------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------------------



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

start_simulation = time.time()

t, y = slv.simulate(
    t0=0,
    t_end=20.0,
    h=0.001,
    x0=x0,
    params0=params0,
    time = t,
    method="implicit_euler"
)

end_simulation = time.time()
print(f"Harcoded simulation time = {end_simulation-start_simulation:.6f} [s]")


# save to csv
slv.save_simulation_to_csv('simulation_results.csv', t, y)


# Generator state variables
plt.plot(t, y[:, slv.get_var_idx(omega_1)], label="ω (pu)")
plt.plot(t, y[:, slv.get_var_idx(omega_2)], label="ω (pu)")
plt.plot(t, y[:, slv.get_var_idx(omega_3)], label="ω (pu)")
plt.plot(t, y[:, slv.get_var_idx(omega_4)], label="ω (pu)")

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.xlim([0, 20.0])
# plt.ylim([0.85, 1.15])
plt.grid(True)
plt.tight_layout()
plt.show()
