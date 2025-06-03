"""
smw_5bus_demo.py
----------------------------------
Self-contained example: 5-bus DC power-flow.
We trip line 3 (between buses 1-3) and use a Sherman–Morrison
rank-1 inverse update to get the exact post-contingency flows
without refactorising the admittance matrix.

Requires: numpy, pandas
"""

import numpy as np
import pandas as pd

# ------------------------------------------------------------
# 1. Network definition
# ------------------------------------------------------------
SLACK = 0                    # choose bus 0 as the slack/reference

#           from  to    x (p.u.)     (line index = row number)
LINES = [
    (0, 1, 0.25),    # line 0
    (0, 2, 0.20),    # line 1
    (1, 2, 0.40),    # line 2
    (1, 3, 0.30),    # line 3  <-- will be tripped
    (2, 4, 0.25),    # line 4
    (3, 4, 0.50),    # line 5
]
L = len(LINES)
b_vals = np.array([1 / x for _, _, x in LINES])        # series susceptances

buses = sorted({b for pair in LINES for b in pair[:2]})
N      = len(buses)
Nred   = N - 1                                          # slack removed
red_buses = [b for b in buses if b != SLACK]        # drop the slack first
red_id    = {b: i for i, b in enumerate(red_buses)} # contiguous 0…Nred-1

# ------------------------------------------------------------
# 2. Build reduced B_bus and branch–bus matrix B_f
# ------------------------------------------------------------
B_bus = np.zeros((Nred, Nred))
B_f   = np.zeros((L,    Nred))

for k, (f, t, x) in enumerate(LINES):
    b = 1 / x

    # contribute to reduced B_bus
    if f != SLACK and t != SLACK:
        i, j = red_id[f], red_id[t]
        B_bus[i, i] += b
        B_bus[j, j] += b
        B_bus[i, j] -= b
        B_bus[j, i] -= b
    elif f == SLACK and t != SLACK:
        j = red_id[t]
        B_bus[j, j] += b
    elif t == SLACK and f != SLACK:
        i = red_id[f]
        B_bus[i, i] += b

    # branch–bus incidence with susceptance weighting
    if f != SLACK:
        B_f[k, red_id[f]] =  b
    if t != SLACK:
        B_f[k, red_id[t]] = -b

# ------------------------------------------------------------
# 3. Base-case injections (+ = generation, − = load) [MW]
# ------------------------------------------------------------
P_dict = {1: 50, 2: 60, 3: -40, 4: -70}
P = np.array([P_dict[b] for b in buses if b != SLACK])   # (Nred,)

# Solve base DC power-flow
theta_base = np.linalg.solve(B_bus, P)                   # bus angles
flow_base  = B_f @ theta_base                            # branch flows

# ------------------------------------------------------------
# 4. Sherman–Morrison update for outage of line 3
# ------------------------------------------------------------
OUTAGED_K = 3
f_k, t_k, x_k = LINES[OUTAGED_K]
b_k = 1 / x_k

# incidence vector u_k (length Nred)
u_k = np.zeros(Nred)
if f_k != SLACK:
    u_k[red_id[f_k]] =  1.0
if t_k != SLACK:
    u_k[red_id[t_k]] = -1.0

# inverse of B_bus (small system; fine for demo)
B_inv = np.linalg.inv(B_bus)
v_k   = B_inv @ u_k
d_k   = 1.0 - b_k * (u_k @ v_k)

if abs(d_k) < 1e-10:
    raise RuntimeError("Outage causes islanding or numerically singular update.")

theta_post = theta_base + (b_k / d_k) * v_k * (u_k @ theta_base)
flow_post  = B_f @ theta_post
flow_post[OUTAGED_K] = 0.0        # tripped line carries zero

# ------------------------------------------------------------
# 5. Display results
# ------------------------------------------------------------
result = pd.DataFrame({
    "line":   range(L),
    "from":   [l[0] for l in LINES],
    "to":     [l[1] for l in LINES],
    "x":      [l[2] for l in LINES],
    "flow_pre (MW)":  flow_base.round(3),
    "flow_post (MW)": flow_post.round(3),
    "Δflow (MW)":     (flow_post - flow_base).round(3),
})

if __name__ == "__main__":
    print("\n--- 5-Bus DC Flow: Outage of Line 3 (1-3) ---\n")
    print(result.to_string(index=False))