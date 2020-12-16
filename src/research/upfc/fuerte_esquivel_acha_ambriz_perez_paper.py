"""
2-bus UPFC controller from:

A comprehensive Newton-Raphson UPFC model for the quadratic power flow
solution of practical power networks

C.R. Fuerte Esquivel, E. Acha, H. Ambriz Pérez,

IEEE 2000
"""

import numpy as np
from math import sin, cos
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

n = 2
Sbase = 100.0
voltage = np.ones(n, dtype=complex)
Ɵ = np.angle(voltage)
V = np.abs(voltage)

k = 0  # first bus
m = 1  # second bus

# branch data (only 1 UPFC) --------------------------------------------------------------------------------------------

nupfc = 1

# impedances
RcR = 0.002
XcR = 0.01
RvR = 0.002
XvR = 0.01

# UPFC set points
Pset = np.array([-20]) / Sbase
Qset = np.array([-10]) / Sbase

# state variables
VcR = np.ones(nupfc)
VvR = np.ones(nupfc)
ƟcR = np.zeros(nupfc)
ƟvR = np.zeros(nupfc)

# bus injections
P = np.array([0, -20]) / Sbase
Q = np.array([0, -10]) / Sbase

# Initial values of the UPFC -------------------------------------------------------------------------------------------

i = 0  # UPFC branch index

CI = Qset[i] - V[m] * (V[m] - V[k]) / XcR

ƟcR[i] = np.arctan(Pset[i] / CI)
VcR[i] = (XcR / V[m]) * np.sqrt(Pset[i] * Pset[i] - CI * CI)
ƟvR[i] = -np.arcsin(((V[k] - V[m]) * VcR[i] * XvR * sin(ƟcR[i])) / (VvR[i] * V[k] * XcR))

# Admittance matrix ----------------------------------------------------------------------------------------------------

# connectivity matrices
Cf = sp.lil_matrix((nupfc, n), dtype=int)
Ct = sp.lil_matrix((nupfc, n), dtype=int)

Cf[0, k] = 1
Ct[0, m] = 1

# impedance primitives
ycR = 1 / (RcR + 1j * XcR)
yvR = 1 / (RvR + 1j * XvR)

Y = np.zeros((n, n), dtype=complex)
YvR = np.zeros(nupfc, dtype=complex)

yff = np.array([ycR + yvR])
ytt = np.array([ycR])
yft = np.array([-ycR])
ytf = np.array([-ycR])

Yf = sp.diags(yff) * Cf + sp.diags(yft) * Ct
Yt = sp.diags(ytf) * Cf + sp.diags(ytt) * Ct
Y = Cf.T * Yf + Ct.T * Yt

YvR[i] = - yvR

G = Y.real
B = Y.imag

GvR = YvR.real
BvR = YvR.imag

for iter in range(10):

     # mismatch vector -------------------------------------------------------------------------------------------------

     i = 0  # UPFC branch index

     PcR = VcR[i] * VcR[i] * G[m, m] + \
           VcR[i] * V[k] * (G[k, m] * cos(ƟcR[i] - Ɵ[k]) + B[k, m] * sin(ƟcR[i] - Ɵ[k])) + \
           VcR[i] * V[m] * (G[m, m] * cos(ƟcR[i] - Ɵ[m]) + B[m, m] * sin(ƟcR[i] - Ɵ[m]))  # Eq 11

     PvR = -VvR[i] * VvR[i] * GvR[i] + VvR[i] * V[k] * (GvR[i] * cos(ƟvR[i] - Ɵ[k]) + BvR[i] * sin(ƟvR[i] - Ɵ[k]))  # Eq 12

     Scalc = voltage * np.conj(Y * voltage)

     dP = P - Scalc.real
     dQ = Q - Scalc.imag

     Vf = Cf * voltage
     Vt = Ct * voltage
     If = Yf * voltage
     It = Yt * voltage
     Sf = Vf * np.conj(If)
     St = Vt * np.conj(It)

     dPb = Pset - Sf.real
     dQb = Qset - Sf.imag

     fx = np.array([dP[k], dP[m], dQ[k], dQ[m], dPb[i], dQb[i], PcR + PvR])

     # Jacobian matrix -------------------------------------------------------------------------------------------------

     i = 0  # UPFC branch index

     # The Jacobian equations at sending node are

     Hkm = V[k] * V[m] * (G[k, m] * sin(Ɵ[k] - Ɵ[m]) - B[k, m] * cos(Ɵ[k] - Ɵ[m]))  # A1

     HkcR = V[k] * VcR[i] * (G[k, m] * sin(Ɵ[k] - ƟcR[i]) - B[k, m] * cos(Ɵ[k] - ƟcR[i]))  # A2

     HkvR = V[k] * VvR[i] * (GvR[i] * sin(Ɵ[k] - ƟvR[i]) - BvR[i] * cos(Ɵ[k] - ƟvR[i]))  # A3

     Hkk = - Hkm - HkcR - HkvR  # A4

     Nkm = V[k] * V[m] * (G[k, m] * cos(Ɵ[k] - Ɵ[m]) + B[k, m] * sin(Ɵ[k] - Ɵ[m]))  # A5

     NkcR = V[k] * VcR[i] * (G[k, m] * cos(Ɵ[k] - ƟcR[i]) + B[k, m] * sin(Ɵ[k] - ƟcR[i]))  # A6

     NkvR = V[k] * VvR[i] * (GvR[i] * cos(Ɵ[k] - ƟvR[i]) + BvR[i] * sin(Ɵ[k] - ƟvR[i]))  # A7

     Nkk = 2.0 * V[k] * V[k] * G[k, k] + Nkm + NkcR + NkvR  # A8

     Jkm = - Nkm  # A9.a

     JkcR = - NkcR  # A9.b

     JkvR = -NkvR  # A10.a

     Jkk = - Nkm + NkcR + NkvR  # A10.b

     Lkm = Hkm  # A11.a

     LkcR = -HkcR  # A11.b

     LkvR = HkvR  # A12.a

     Lkk = -2.0 * V[k] * V[k] * B[k, k] - Hkk  # A12.b

     # The Jacobian equations at receiving node are:

     Hmk = V[m] * V[k] * (G[m, k] * sin(Ɵ[m] - Ɵ[k]) - B[m, k] * cos(Ɵ[m] - Ɵ[k]))  # A13

     HmcR = V[m] * VcR[i] * (G[m, m] * sin(Ɵ[m] - ƟcR[i]) - B[m, m] * cos(Ɵ[m] - ƟcR[i]))  # A14

     Hmm = - Hmk - HmcR  # A15

     Nmk = V[m] * V[k] * (G[m, k] * cos(Ɵ[m] - Ɵ[k]) + B[m, k] * sin(Ɵ[m] - Ɵ[k]))  # A16

     NmcR = V[m] * VcR[i] * (G[m, m] * cos(Ɵ[m] - ƟcR[i]) - B[m, m] * sin(Ɵ[m] - ƟcR[i]))  # A17

     Nmm = 2.0 * V[m] * V[m] * G[m, m] + Nmk + NmcR  # A18

     Jmk = -Nmk  # A19.a

     JmcR = -NmcR  # A19.b

     Jmm = Nmk + NmcR  # A19.c

     Lmk = Hmk  # A20.a

     LmcR = HmcR  # A20.b

     Lmm = -2.0 * V[m] * V[m] * B[m, m] - Hmm  # A20.c

     # terms for the series converter

     HcRk = VcR[i] * V[k] * (G[k, m] * sin(ƟcR[i] - Ɵ[k]) - B[k, m] * cos(ƟcR[i] - Ɵ[k]))  # A21

     HcRm = VcR[i] * V[m] * (G[m, m] * sin(ƟcR[i] - Ɵ[m]) - B[m, m] * cos(ƟcR[i] - Ɵ[m]))  # A22

     HcRcR = - HcRk - HcRm  # A23

     NcRk = VcR[i] * V[k] * (G[k, m] * cos(ƟcR[i] - Ɵ[k]) - B[k, m] * sin(ƟcR[i] - Ɵ[k]))  # A24

     NcRm = VcR[i] * V[m] * (G[m, m] * cos(ƟcR[i] - Ɵ[m]) + B[m, m] * sin(ƟcR[i] - Ɵ[m]))  # A25

     NcRcR = 2.0 * VcR[i] * VcR[i] * G[m, m] + NcRk + NcRm  # A26

     # The Jacobian terms of the shunt converter are:

     HvRk = VvR[i] * V[k] * (GvR[i] * sin(ƟvR[i] - Ɵ[k]) - BvR[i] * cos(ƟvR[i] - Ɵ[k]))  # A27

     HvRvR = - HvRk  # A28

     NvRk = VvR[i] * V[k] * (GvR[i] * cos(ƟvR[i] - Ɵ[k]) + BvR[i] * sin(ƟvR[i] - Ɵ[k]))

     NvRvR = -2.0 * VvR[i] * VvR[i] * GvR[i] + NvRk


     # Eq. 16
     J = [[Hkk,          Hkm,    Nkk,        Nkm,    HkcR,   NkcR,   HkvR],
          [Hmk,          Hmm,    Nmk,        Nmm,    HmcR,   NmcR,   0],
          [Jkk,          Jkm,    Lkk,        Lkm,    JkcR,   LkcR,   JkvR],
          [Jmk,          Jmm,    Lmk,        Lmm,    JmcR,   LmcR,   0],
          [Hmk,          Hmm,    Nmk,        Nmm,    HmcR,   NmcR,   0],
          [Jmk,          Jmm,    Lmk,        Lmm,    JmcR,   LmcR,   0],
          [HcRk+HvRk,    HcRm,   HcRk+NvRk,  NcRm,   HcRcR,  NcRcR,  HvRvR]]

     non_slack_indices = np.array([1, 3, 4, 5, 6])
     J = np.array(J)[non_slack_indices, :][:, non_slack_indices]


     # find the values
     # dx = np.linalg.solve(J, fx[non_slack_indices])  # this comes out singular...
     dx = np.dot(np.linalg.pinv(J), fx[non_slack_indices])

     # Eq. 17
     # Ɵ[k] += dx[0]
     # Ɵ[m] += dx[1]
     # V[k] += dx[2]
     # V[m] += dx[3]
     # ƟcR[i] += dx[4]
     # VcR[i] += dx[5]
     # ƟvR[i] += dx[6]

     # Ɵ[k] += dx[0]
     Ɵ[m] += dx[0]
     # V[k] += dx[2]
     V[m] += dx[1]
     ƟcR[i] += dx[2]
     VcR[i] += dx[3]
     ƟvR[i] += dx[4]

     print('iter:', iter)
     print('|V|', V)
     print('Ɵ', Ɵ)

print()