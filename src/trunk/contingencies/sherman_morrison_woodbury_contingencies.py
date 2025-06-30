"""
smw_5bus_two_outages.py
------------------------------------------------
5-bus DC power-flow with TWO simultaneous line outages
handled via a rank-2 Sherman–Morrison–Woodbury update.
"""

import numpy as np
import pandas as pd

# ----------------- 1. Network definition -----------------
SLACK = 0
LINES = [
    (0, 1, 0.25),  # line 0  <-- outaged
    (0, 2, 0.20),  # line 1
    (1, 2, 0.40),  # line 2
    (1, 3, 0.30),  # line 3  <-- outaged
    (2, 4, 0.25),  # line 4
    (3, 4, 0.50),  # line 5
]
OUTAGED = [0, 3]                                # simultaneous outages
L = len(LINES)

buses  = sorted({b for l in LINES for b in l[:2]})
N      = len(buses)
Nred   = N - 1
red_buses = [b for b in buses if b != SLACK]        # drop the slack first
red_id    = {b: i for i, b in enumerate(red_buses)} # contiguous 0…Nred-1

# ----------------- 2. Build B_bus and B_f ----------------
B_bus = np.zeros((Nred, Nred))
B_f   = np.zeros((L,    Nred))

for k, (f, t, x) in enumerate(LINES):
    b = 1 / x
    if f != SLACK and t != SLACK:
        i, j = red_id[f], red_id[t]
        B_bus[i, i] += b;  B_bus[j, j] += b
        B_bus[i, j] -= b;  B_bus[j, i] -= b
    elif f == SLACK and t != SLACK:
        B_bus[red_id[t], red_id[t]] += b
    elif t == SLACK and f != SLACK:
        B_bus[red_id[f], red_id[f]] += b

    if f != SLACK:
        B_f[k, red_id[f]] =  b
    if t != SLACK:
        B_f[k, red_id[t]] = -b

# ----------------- 3. Base injections --------------------
P = np.array([50, 60, -40, -70])  # buses 1-4 (bus 0 is slack)
theta_base = np.linalg.solve(B_bus, P)
flow_base  = B_f @ theta_base

# ----------------- 4. Rank-2 Woodbury update -------------
r = len(OUTAGED)
U = np.zeros((Nred, r))
D = np.zeros((r, r))
for col, k in enumerate(OUTAGED):
    f_k, t_k, x_k = LINES[k]
    b_k = 1 / x_k
    D[col, col] = b_k
    if f_k != SLACK:
        U[red_id[f_k], col] =  1
    if t_k != SLACK:
        U[red_id[t_k], col] = -1

B_inv   = np.linalg.inv(B_bus)
V       = B_inv @ U
M_inv   = np.linalg.inv(np.linalg.inv(D) - U.T @ V)
B_inv2  = B_inv + V @ M_inv @ V.T

theta_post = B_inv2 @ P
flow_post  = B_f @ theta_post
flow_post[OUTAGED] = 0.0

# ----------------- 5. Results table ----------------------
df = pd.DataFrame({
    "line":   range(L),
    "from":   [l[0] for l in LINES],
    "to":     [l[1] for l in LINES],
    "x":      [l[2] for l in LINES],
    "flow_pre (MW)":  flow_base.round(3),
    "flow_post (MW)": flow_post.round(3),
    "Δflow (MW)":     (flow_post - flow_base).round(3),
})

if __name__ == "__main__":
    print("\n--- 5-Bus DC Flow: Outage of Lines 0 (0-1) & 3 (1-3) ---\n")
    print(df.to_string(index=False))