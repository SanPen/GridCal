# PGD code, generic
import time
import pandas as pd
import numpy as np
from numpy import (array, dot, arccos, clip)
from numpy.linalg import norm

pd.options.display.precision = 2
pd.set_option('display.precision', 2)
np.random.seed(42)

df_b = pd.read_excel('data_10PQ.xlsx', sheet_name="buses")
df_l = pd.read_excel('data_10PQ.xlsx', sheet_name="lines")

# BEGIN INITIALIZATION OF DATA
n_b = 0
n_pq = 0
n_pv = 0
pq = []
pv = []
pq0 = []  # store pq buses indices relative to its own
pv0 = []  # store pv buses indices relative to its own
d_pq = {}  # dict of pq
d_pv = {}  # dict of pv
for i in range(len(df_b)):
    if df_b.iloc[i, 4] == "slack":  # index 0 is reserved for the slack bus
        pass

    elif df_b.iloc[i, 4] == "PQ":
        pq0.append(n_pq)
        d_pq[df_b.iloc[i, 0]] = n_pq
        n_b += 1
        n_pq += 1
        pq.append(df_b.iloc[i, 0] - 1)
        
    elif df_b.iloc[i, 4] == "PV":
        pv0.append(n_pv)
        d_pv[df_b.iloc[i, 0]] = n_pv
        n_b += 1
        n_pv += 1
        pv.append(df_b.iloc[i, 0] - 1)

n_l = len(df_l)  # number of lines

V0 = df_b.iloc[0, 3]  # the slack is always positioned in the first row
I0_pq = np.zeros(n_pq, dtype=complex)
I0_pv = np.zeros(n_pv, dtype=complex)
Y = np.zeros((n_b, n_b), dtype=complex)  # I will build it with block matrices
Y11 = np.zeros((n_pq, n_pq), dtype=complex)  # pq pq
Y12 = np.zeros((n_pq, n_pv), dtype=complex)  # pq pv
Y21 = np.zeros((n_pv, n_pq), dtype=complex)  # pv pq
Y22 = np.zeros((n_pv, n_pv), dtype=complex)  # pv pv

for i in range(n_l):
    Ys = 1 / (df_l.iloc[i, 2] + 1j * df_l.iloc[i, 3])  # series element
    Ysh = df_l.iloc[i, 4] + 1j * df_l.iloc[i, 5]  # shunt element
    t = df_l.iloc[i, 6] * np.cos(df_l.iloc[i, 7]) + 1j * df_l.iloc[i, 6] * np.sin(df_l.iloc[i, 7])  # tap as a complex number

    a = df_l.iloc[i, 0]
    b = df_l.iloc[i, 1]

    if a == 0:
        if b - 1 in pq:
            I0_pq[d_pq[b]] += V0 * Ys / t
            Y11[d_pq[b], d_pq[b]] += Ys + Ysh
        if b - 1 in pv:
            I0_pv[d_pv[b]] += V0 * Ys / t
            Y22[d_pv[b], d_pv[b]] += Ys + Ysh

    elif b == 0:
        if a - 1 in pq:
            I0_pq[d_pq[a]] += V0 * Ys / np.conj(t)
            Y11[d_pq[a], d_pq[a]] += (Ys + Ysh) / (t * np.conj(t))
        if a - 1 in pv:
            I0_pv[d_pv[a]] += V0 * Ys / np.conj(t)
            Y22[d_pv[a], d_pv[a]] += (Ys + Ysh) / (t * np.conj(t))

    else:
        if a - 1 in pq and b - 1 in pq:
            Y11[d_pq[a], d_pq[a]] += (Ys + Ysh) / (t * np.conj(t))
            Y11[d_pq[b], d_pq[b]] += Ys + Ysh
            Y11[d_pq[a], d_pq[b]] += - Ys / np.conj(t)
            Y11[d_pq[b], d_pq[a]] += - Ys / t
        
        if a - 1 in pq and b - 1 in pv:
            Y11[d_pq[a], d_pq[a]] += (Ys + Ysh) / (t * np.conj(t))
            Y22[d_pv[b], d_pv[b]] += Ys + Ysh
            Y12[d_pq[a], d_pv[b]] += - Ys / np.conj(t)
            Y21[d_pv[b], d_pq[a]] += - Ys / t

        if a - 1 in pv and b - 1 in pq:
            Y22[d_pv[a], d_pv[a]] += (Ys + Ysh) / (t * np.conj(t))
            Y11[d_pq[b], d_pq[b]] += Ys + Ysh
            Y21[d_pv[a], d_pq[b]] += - Ys / np.conj(t)
            Y12[d_pq[b], d_pv[a]] += - Ys / t

        if a - 1 in pv and b - 1 in pv:
            Y22[d_pv[a], d_pv[a]] += (Ys + Ysh) / (t * np.conj(t))
            Y22[d_pv[b], d_pv[b]] += Ys + Ysh
            Y22[d_pv[a], d_pv[b]] += - Ys / np.conj(t)
            Y22[d_pv[b], d_pv[a]] += - Ys / t


for i in range(len(df_b)):  # add shunts connected directly to the bus
    a = df_b.iloc[i, 0]
    if a - 1 in pq:
        # print(d_pq[a])
        Y11[d_pq[a], d_pq[a]] += df_b.iloc[i, 5] + 1j * df_b.iloc[i, 6]
    elif a - 1 in pv:
        # print(d_pv[a])
        Y22[d_pv[a], d_pv[a]] += df_b.iloc[i, 5] + 1j * df_b.iloc[i, 6]


Y = np.block([[Y11, Y12], [Y21, Y22]])
Yinv = np.linalg.inv(Y)
Ydf = pd.DataFrame(Y)

V_mod = np.zeros(n_pv, dtype=float)
P_pq = np.zeros(n_pq, dtype=float)
P_pv = np.zeros(n_pv, dtype=float)
Q_pq = np.zeros(n_pq, dtype=float)
for i in range(len(df_b)):
    if df_b.iloc[i, 4] == "PV":
        V_mod[d_pv[df_b.iloc[i, 0]]] = df_b.iloc[i, 3]
        P_pv[d_pv[df_b.iloc[i, 0]]] = df_b.iloc[i, 1]
    elif df_b.iloc[i, 4] == "PQ":
        Q_pq[d_pq[df_b.iloc[i, 0]]] = df_b.iloc[i, 2]
        P_pq[d_pq[df_b.iloc[i, 0]]] = df_b.iloc[i, 1]
# END INITIALIZATION OF DATA


# DECOMPOSITION OF APPARENT POWERS
SSk = []
SSp = []
SSq = []
n_buses = np.shape(Y)[0]  # number of buses
n_scale = 1001  # number of discretized points, arbitrary
Qmax = 1.00  # maximum reactive power of the capacitor
Qmin = 0  # minimum reactive power of the capacitor

SKk0 = P_pq + Q_pq * 1j  # original load
SPp0 = np.ones(n_buses)  # positions of standard the loads
SQq0 = np.ones(n_scale)  # always multiply by a factor of 1, the original loads do not change

SSk.append(np.conj(SKk0))
SSp.append(np.conj(SPp0))
SSq.append(np.conj(SQq0))

print(SSk)

# go over all positions where we could have a capacitor (from bus 2 to 102)
"""
for ii in range(2, n_buses):
    SKk1 = np.zeros(n_buses, dtype=complex)  # power amplitude, in this case, it will be reactive
    SKk1[ii] = Qmax * 1j  # put a 1 because only one capacitor at a time. This is the maximum capacitor power
    SPp1 = np.zeros(n_buses)  # possible positions of the capacitor
    SPp1[ii] = 1
    SQq1 = np.arange(Qmin, Qmax, Qmax / n_scale)  # scale the powers in a discrete form
    SSk.append(np.conj(SKk1))
    SSp.append(np.conj(SPp1))
    SSq.append(np.conj(SQq1))
"""
# keep it simple, consider by now less cases
# ----------
# SKk1 = np.zeros(n_buses, dtype=complex)
# SKk1[0] = Qmax * 1j
SKk1 = 1 * np.random.rand(n_buses)  # generator of random active power
SPp1 = np.zeros(n_buses)
# for ii in range(2, n_buses):
for ii in range(n_buses):  # only a few buses
    SPp1[ii] = ii / n_buses  # for instance
SQq1 = np.arange(Qmin, Qmax, Qmax / n_scale)

SSk.append(np.conj(SKk1))
SSp.append(np.conj(SPp1))
SSq.append(np.conj(SQq1))

print(SSk)
# ----------

# DECOMPOSITION OF VOLTAGES
Kkv = np.ones(n_buses, dtype=complex)  # amplitude vector
Ppv = np.ones(n_buses)  # position vector
Qqv = np.ones(n_scale)  # scaling vector

VVk = []
VVp = []
VVq = []

VVk.append(np.conj(Kkv))
VVp.append(np.conj(Ppv))
VVq.append(np.conj(Qqv))


# DECOMPOSITION OF CURRENTS
IIk = []
IIp = []
IIq = []

# CREATION OF C (auxiliary variables). 
# THIS FUNCTION HAS TO BE CALLED EVERY TIME WE COMPUTE A NEW RESIDUE OF I, AND ALWAYS FOLLOWS THIS


def fun_C(SSk, SSp, SSq, VVk, VVp, VVq, IIk, IIp, IIq):
    """

    :param SSk:
    :param SSp:
    :param SSq:
    :param VVk:
    :param VVp:
    :param VVq:
    :param IIk:
    :param IIp:
    :param IIq:
    :return:
    """
    Ns = len(SSk)
    Nv = len(VVk)
    n = len(IIk)
    Nc = Ns + Nv * n
    # CCk = SSk  # initialize with the S* decomposed variables
    # CCp = SSp
    # CCq = SSq

    CCk = SSk.copy()
    CCp = SSp.copy()
    CCq = SSq.copy() 
    for ii in range(Nv):
        for jj in range(n):
            CCk.append(- VVk[ii] * IIk[jj])
            CCp.append(- VVp[ii] * IIp[jj])
            CCq.append(- VVq[ii] * IIq[jj])
    return CCk, CCp, CCq, Nc, Nv, n


# DEFINITION OF NUMBER OF ITERATIONS, CAN CHANGE ARBITRARILY
n_gg = 5  # outer
n_mm = 8  # intermediate
n_kk = 10  # inner


for gg in range(n_gg):  # outer loop

    # add the blank initialization of C:
    # CCk = []
    # CCp = []
    # CCq = []

    # IIk = []
    # IIp = []
    # IIq = []

    for mm in range(n_mm):  # intermediate loop
        # define the new C
        CCk, CCp, CCq, Nc, Nv, n = fun_C(SSk, SSp, SSq, VVk, VVp, VVq, IIk, IIp, IIq)

        # initialize the residues we have to find
        IIk1 = (np.random.rand(n_buses) - np.random.rand(n_buses)) * 1  # could also try to set IIk1 = VVk1
        IIp1 = (np.random.rand(n_buses) - np.random.rand(n_buses)) * 1
        IIq1 = (np.random.rand(n_scale) - np.random.rand(n_scale)) * 1

        for kk in range(n_kk):  # inner loop
            # compute IIk1 (residues on Ik)

            prodRK = 0
            RHSk = np.zeros(n_buses, dtype=complex)
            for ii in range(Nc):
                prodRK = np.dot(IIp1, CCp[ii]) * np.dot(IIq1, CCq[ii])
                RHSk += prodRK * CCk[ii]

            prodLK = 0
            LHSk = np.zeros(n_buses, dtype=complex)
            for ii in range(Nv):
                prodLK = np.dot(IIp1, VVp[ii] * IIp1) * np.dot(IIq1, VVq[ii] * IIq1)
                LHSk += prodLK * VVk[ii]

            IIk1 = RHSk / LHSk

            # compute IIp1 (residues on Ip)
            prodRP = 0
            RHSp = np.zeros(n_buses, dtype=complex)
            for ii in range(Nc):
                prodRP = np.dot(IIk1, CCk[ii]) * np.dot(IIq1, CCq[ii])
                RHSp += prodRP * CCp[ii]

            prodLP = 0
            LHSp = np.zeros(n_buses, dtype=complex)
            for ii in range(Nv):
                prodLP = np.dot(IIk1, VVk[ii] * IIk1) * np.dot(IIq1, VVq[ii] * IIq1)
                LHSp += prodLP * VVp[ii]

            IIp1 = RHSp / LHSp

            # compute IIq1 (residues on Iq)
            prodRQ = 0
            RHSq = np.zeros(n_scale, dtype=complex)
            for ii in range(Nc):
                prodRQ = np.dot(IIk1, CCk[ii]) * np.dot(IIp1, CCp[ii])
                RHSq += prodRQ * CCq[ii]

            prodLQ = 0
            LHSq = np.zeros(n_scale, dtype=complex)
            for ii in range(Nv):
                prodLQ = np.dot(IIk1, VVk[ii] * IIk1) * np.dot(IIp1, VVp[ii] * IIp1)
                LHSq += prodLQ * VVq[ii]

            IIq1 = RHSq / LHSq

            if gg == 0 and mm == 0 and kk >= 0:
                print(IIk1[:10])
                # print(IIp1[:10])
                # print(IIq1[:10])

        IIk.append(IIk1)
        IIp.append(IIp1)
        IIq.append(IIq1)

    VVk = []
    VVp = []
    VVq = []
    PP1 = np.ones(n_buses)
    QQ1 = np.ones(n_scale)
    for ii in range(n_mm):
        # VVk.append(np.conj(np.dot(Yinv, IIk[ii] + I0_pq)))
        VVk.append(np.conj(np.dot(Yinv, IIk[ii])))
        VVp.append(IIp[ii])
        VVq.append(IIq[ii])
        # VVp = np.copy(IIp)
        # VVq = np.copy(IIq)

    # print(VVk[0][:10])
    # print(VVk[1][:10])

    # try to add I0 this way:
    VVk.append(np.conj(np.dot(Yinv, I0_pq)))
    VVp.append(PP1)
    VVq.append(QQ1)


# CHART OF VOLTAGES 
# full_map = np.multiply.outer(VVk[0], np.multiply.outer(VVp[0], VVq[0]))  # initial tridimensional representation
V_map = np.multiply.outer(np.multiply.outer(VVp[0], VVk[0]), VVq[0])  # the tridimensional representation I am looking for
for i in range(1, len(VVk)):
    V_map += np.multiply.outer(np.multiply.outer(VVp[i], VVk[i]), VVq[i])  # the tridimensional representation I am looking for
# writer = pd.ExcelWriter('Map_V.xlsx')
# for i in range(n_buses):
#     V_map_df = pd.DataFrame(V_map[:][i][:])
#     V_map_df.to_excel(writer, sheet_name=str(i))
# writer.save()

# CHART OF CURRENTS
I_map = np.multiply.outer(np.multiply.outer(IIp[0], IIk[0]), IIq[0])
for i in range(1, len(IIk)):
    I_map += np.multiply.outer(np.multiply.outer(IIp[i], IIk[i]), IIq[i])
# writer = pd.ExcelWriter('Map_I.xlsx')
# for i in range(n_buses):
#     I_map_df = pd.DataFrame(I_map[:][i][:])
#     I_map_df.to_excel(writer, sheet_name=str(i))
# writer.save()


# CHART OF POWERS
S_map = np.multiply.outer(np.multiply.outer(SSp[0], SSk[0]), SSq[0])
for i in range(1, len(SSk)):
    S_map += np.multiply.outer(np.multiply.outer(SSp[i], SSk[i]), SSq[i])
# writer = pd.ExcelWriter('Map_S.xlsx')
# for i in range(n_buses):
#     S_map_df = pd.DataFrame(S_map[:][i][:])
#     S_map_df.to_excel(writer, sheet_name=str(i))
# writer.save()

print(np.shape(SSk))
print(n_buses)