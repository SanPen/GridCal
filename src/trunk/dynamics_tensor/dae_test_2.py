# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import sys, os
file_directory = os.path.dirname(os.path.abspath(__file__))
up_two_directories = os.path.join(file_directory, '..', '..')
up_two_directories = os.path.abspath(up_two_directories)
sys.path.insert(0,up_two_directories)
print(up_two_directories)
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import numpy as np
from matplotlib import pyplot as plt

# from GridCalEngine.Utils.Symbolic.events import Events, Event
from GridCalEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from GridCalEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from GridCalEngine.Utils.Symbolic.block import Block
from GridCalEngine.Utils.MultiLinear.multilinearize import *
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver
from GridCalEngine.Utils.MultiLinear.differential_var import DiffVar, LagVar
from GridCalEngine.Utils.MultiLinear.diff_blocksolver import DiffBlock, DiffBlockSolver
import GridCalEngine.api as gce

# ----------------------------------------------------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------------------------------------------------
pi = Const(math.pi)
fn = Const(50)
M = Const(1.0)
D = Const(1)
ra = Const(0.3)
xd = Const(0.86138701)
vf = Const(1.081099313)

omega_ref = Const(1)
Kp = Const(1.0)
Ki = Const(10.0)
Kw = Const(10.0)

g = Const(5)
b = Const(-12)
bsh = Const(0.03)
tm0 = Const(1)

#Test
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

u_sin = Var('u_cos')
du_sin = DiffVar('du_sin', base_var= u_sin)
u_cos = Var('u_cos')
du_cos = DiffVar('du_cos', base_var= u_cos)
v_sin = Var('v_sin')
delta_dt = DiffVar.get_or_create('delta_dt', base_var = delta)
dg_dt = DiffVar.get_or_create('dg_dt', base_var = dg)

sin4x = Var('sin4x')
int_sin2 = Var('int_sin2')
int_xcosx = Var('int_xcosx')
int_xsinx = Var('int_xsinx')
int_sin2cos2 = Var('int_sin2cos2')
u = Var('u')

generator_block_ML = DiffBlock(
    state_eqs=[
        (2 * pi * fn) * (omega - omega_ref),  # dδ/dt
        (tm  - t_e - D * (omega - omega_ref)) / M,  # dω/dt
        (omega - omega_ref),
    
    ],
    state_vars=[delta, omega, et],
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
        (tm - tm0) + (Kp * (omega - omega_ref) + Ki * et),
        du_cos - (delta_dt - dg_dt)*u_sin,
        du_sin + (delta_dt - dg_dt)*u_cos
    ],
    algebraic_vars=[psid, psiq, i_d, i_q, v_d, v_q, t_e, P_g, Q_g, tm, u_cos, u_sin],
    parameters=[],
    diff_vars= [delta_dt, dg_dt, du_cos, du_sin],
)



generator_block_ML = DiffBlock(
    state_eqs=[
        (2 * pi * fn) * (omega - omega_ref) ,  # dδ/dt
        (tm  - t_e - D * (omega - omega_ref)) / M,  # dω/dt
        (omega - omega_ref),

    ],
    state_vars=[delta, omega, et],
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
        (tm - tm0) + (Kp * (omega - omega_ref) + Ki * et),
        delta_dt - u
    ],
    algebraic_vars=[psid, psiq, i_d, i_q, v_d, v_q, t_e, P_g, Q_g, tm, u],
    diff_vars = [delta_dt],
    parameters=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------

grid = gce.MultiCircuit()

bus1 = gce.Bus(name="Bus1", Vnom=10)
bus2 = gce.Bus(name="Bus2", Vnom=10)
grid.add_bus(bus1)
grid.add_bus(bus2)

line = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2,
                r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=100.0)
grid.add_line(line)

gen = gce.Generator(name="Gen1", P=10, vset=1.0) # PV
grid.add_generator(bus=bus1, api_obj=gen)

load = gce.Load(name="Load1", P=10, Q=10)        # PQ
grid.add_load(bus=bus2, api_obj=load)

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
i = np.conj(Sb1 / v1)          # ī = (p - jq) / v̄* 
# Delta angle 
delta0 = np.angle(v1 + (ra.value + 1j*xd.value) * i)
# dq0 rotation
rot = np.exp(-1j * (delta0 - np.pi/2))
# dq voltages and currents
v_d0 = np.real(v1*rot)
v_q0 = np.imag(v1*rot)
i_d0 = np.real(i*rot)
i_q0 = np.imag(i*rot)
# inductances 
psid0 = ra.value * i_q0 + v_q0
psiq0 = -ra.value * i_d0 - v_d0

te0 = psid0 * i_q0 - psiq0 * i_d0 
tm0 = Const(te0)
vf0 = psid0 + xd.value * i_d0
print(f"vf = {vf0}")

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

coeff_alfa = Const(1.8)
Pl0 = Var("Pl0")
Ql0 = Const(Sb2.imag)
coeff_beta = Const(8.0)
print(Sb2.imag)
load_block = Block(
    algebraic_eqs=[
        Pl - Pl0,
        Ql - Ql0
    ],
    algebraic_vars=[Ql, Pl],
    parameters=[Pl0]
)

# ----------------------------------------------------------------------------------------------------------------------
# Generator
# ----------------------------------------------------------------------------------------------------------------------


# psid - (-ra * i_q + v_q),
# psiq - (-ra * i_d + v_d),
# i_d - (psid + xd * i_d - vf),
# i_q - (psiq + xd * i_q),
# v_d - (Vg * sin(delta - dg)),
# v_q - (Vg * cos(delta - dg)),
# t_e - (psid * i_q - psiq * i_d),
# (v_d * i_d + v_q * i_q) - p_g,
# (v_q * i_d - v_d * i_q) - Q_g


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

sys = DiffBlock(
    children=[line_block, load_block, generator_block_ML, bus1_block, bus2_block],
    in_vars=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = DiffBlockSolver(sys)

# ----------------------------------------------------------------------------------------------------------------------
# Intialization
# ----------------------------------------------------------------------------------------------------------------------
grid = gce.MultiCircuit()

bus1 = gce.Bus(name="Bus1", Vnom=10)
bus2 = gce.Bus(name="Bus2", Vnom=10)
grid.add_bus(bus1)
grid.add_bus(bus2)

line = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2,
                r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=100.0)
grid.add_line(line)

gen = gce.Generator(name="Gen1", P=10, vset=1.0) # PV
grid.add_generator(bus=bus1, api_obj=gen)

load = gce.Load(name="Load1", P=10, Q=10)        # PQ
grid.add_load(bus=bus2, api_obj=load)

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
i = np.conj(Sb1 / v1)          # ī = (p - jq) / v̄*
# Delta angle
delta0 = np.angle(v1 + (ra.value + 1j*xd.value) * i)
# dq0 rotation
rot = np.exp(-1j * (delta0 - np.pi/2))
# dq voltages and currents
v_d0 = np.real(v1*rot)
v_q0 = np.imag(v1*rot)
i_d0 = np.real(i*rot)
i_q0 = np.imag(i*rot)
# inductances
psid0 = ra.value * i_q0 + v_q0
psiq0 = -ra.value * i_d0 - v_d0

vf0 = psid0 + xd.value * i_d0
dg0 = np.angle(v1)
delta_dt0 = 0
u_cos0 = np.cos(delta0 -dg0)
u_sin0 = np.sin(delta0 -dg0)
print(f"vf = {vf0}")

params_mapping = {
    Pl0: Sb2.real
    #Ql0: 0.1
}
# ----------------------------------------------------------------------------------------------------------------------
# Intialization
# ----------------------------------------------------------------------------------------------------------------------
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
    u:0,
    #u_sin: u_sin0,
    #u_cos: u_cos0,
    #v_sin: u_sin0,
    #v_cos: u_cos0,
    #int_sin2: 0.5*((delta0-dg0)-u_sin0*u_cos0),
    #int_sin2cos2:  1/32*(4*(delta0-dg0) - (4*u_cos0**3*u_sin0 - 4*u_sin0**3*u_cos)),
    #int_xcosx:  (delta0 -dg0)*(u_sin0)+ u_cos0,
    #int_xsinx: -(delta0 -dg0)*(u_cos0)+ u_sin0,
}

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
my_events = RmsEvents([event1])

params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector(vars_mapping)


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
try:
    params_mapping = {
        slv.dt: 0.001,
        Pl0: Sb2.real,
    }
except:
    params_mapping = {
        Pl0: Sb2.real,
    }

diff_vars_mapping = {
    du_cos: 0,
    du_sin: 0,
    delta_dt: 0,
    dg_dt: 0
}
diff_vars_mapping = {delta_dt: 0, dg_dt : 0}
params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector(vars_mapping)
if isinstance(slv, DiffBlockSolver):
    dx0 = slv.build_init_diffvars_vector(diff_vars_mapping)

t, y = slv.simulate(
    t0=0,
    t_end=10.0,
    h=0.001,
    x0=x0,
    dx0 = dx0,
    params0=params0,
    events_list=my_events,
    method="implicit_euler"
)

# save to csv
slv.save_simulation_to_csv('simulation_results.csv', t, y)

fig = plt.figure(figsize=(14, 10))

#Generator state variables
plt.plot(t, y[:, slv.get_var_idx(omega)], label="ω (pu)", color='red')
plt.plot(t, y[:, slv.get_var_idx(u)]/(2*pi.value*fn.value) + 1, label="ω (pu)", color='red')

#plt.plot(t, y[:, slv.get_var_idx(u_cos)], label="u cos (pu)", color='blue')
#plt.plot(t, y[:, slv.get_var_idx(u_sin)], label="u sin (pu)", color='yellow')

delta_idx = slv.get_var_idx(delta)  
cos_delta_real = np.cos(y[:, delta_idx]) 
sin_delta_real = np.sin(y[:, delta_idx]) 
plt.plot(t, cos_delta_real, label="cos delta real (pu)", color='gray')
plt.plot(t, sin_delta_real, label="sin delta real (pu)", color='teal')
#plt.plot(t, y[:, slv.get_var_idx(delta)], label="delta", color='black')
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
#plt.xlim(0, 10)
#plt.ylim(0.85, 1.15)
plt.tight_layout()
plt.grid(True)
plt.tight_layout()
plt.show()
