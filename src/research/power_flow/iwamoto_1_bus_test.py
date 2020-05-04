import numpy as np
from scipy.sparse import csc_matrix, lil_matrix
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import NR_LS
"""
From the paper:
Load-Flow Solutions for Ill-Conditioned Power Systems by a Newton-Like Method
"""

# Ybus in tripplets form as per the paper
triplets = [(1, 1, 0-14.939j),
            (1, 2, 14.148+0j),
            (2, 2, 12.051 - 33.089j),
            (2, 3, 0.0 + 6.494j),
            (2, 4, -12.051 + 13.197j),
            (3, 3, 2.581 - 10.282j),
            (3, 5, -2.581 + 0.786j),
            (4, 4, 12.642 - 74.081j),
            (4, 5, 0.0 + 2.177j),
            (4, 6, 0.0 + 56.689j),
            (4, 7, -0.592 + 0.786j),
            (5, 5, 2.581 - 5.889j),
            (6, 6, 0.0 - 55.556j),
            (7, 7, 3.226 - 4.304j),
            (7, 8, -2.213 + 2.959j),
            (8, 8, 2.893 - 5.468j),
            (8, 9, -0.138 + 1.379j),
            (8, 10, -0.851 + 1.163j),
            (9, 9, 0.104 - 1.042j),
            (10, 10, 1.346 - 6.110j),
            (10, 11, -0.374 + 3.742j),
            (11, 11, 0.283 - 2.785j)]

# correct thr triplets indices to zero-base
Y = lil_matrix((11, 11), dtype=complex)
for i, j, v in triplets:
    Y[i-1, j-1] = v
Ybus = Y.tocsc()

print('Ybus')
print(Ybus.todense())
print(np.linalg.cond(Ybus.todense()))

Sbus = np.array([0+0j,
                 0+0j,
                 -0.128-0.062j,
                 0+0j,
                 -0.165-0.080j,
                 -0.09-0.068j,
                 0+0j,
                 0+0j,
                 -0.026-0.009j,
                 0+0j,
                 -0.158-0.057j])

V0 = np.ones_like(Sbus)
V0[0] = 1.024 + 0j

V, converged, norm_f, Scalc, iter_, elapsed = NR_LS(Ybus=Ybus,
                                                    Sbus=Sbus,
                                                    V0=V0,
                                                    Ibus=np.zeros_like(Sbus),
                                                    pv=np.array([], dtype=int),
                                                    pq=np.arange(1, 11, dtype=int),
                                                    tol=1e-3,
                                                    max_it=15,
                                                    acceleration_parameter=1.05)

import pandas as pd

df = pd.DataFrame(data=np.c_[np.abs(V), np.angle(V), Scalc.real, Scalc.imag],
                  columns=['Vm', 'Va', 'P', 'Q'])

print(df)
print(norm_f)