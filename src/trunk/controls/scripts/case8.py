# Made up case with 8 nodes, 2 VSCs, 0 controlled transformer
import numpy as np
import pandas as pd

# Data 1
d1 = 0.0
d8 = 0.0

V1 = 1.0
V4 = 1.01
V7 = 0.99
V8 = 1.0

S2sp = - (0.3 + 0.1 * 1j)
S3sp = - (0.2 + 0.05 * 1j)
P4sp = 0.2
P5sp = 0.1
P6sp = 0.15
S7sp = - (0.1 + 0.1 * 1j)

Pt6 = 0.12
Qf3 = 0.05

# Data 2
Y12 = 1.0 / (0.1 + 0.3 * 1j)
Y13 = 1.0 / (0.1 + 0.3 * 1j)
Y23 = 1.0 / (0.1 + 0.3 * 1j)
G45 = 1.0 / 0.1
G46 = 1.0 / 0.1
G56 = 1.0 / 0.1
Y78 = 1.0 / (0.1 + 0.3 * 1j)

a = 0.01
b = 0.02
c = 0.04


# Equations
# x = [d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7]
x = []


def unpack_x(x):
    d2 = x[0]
    d3 = x[1]
    d7 = x[2]
    V2 = x[3]
    V3 = x[4]
    V5 = x[5]
    V6 = x[6]
    Pf3 = x[7]
    Pt4 = x[8]
    Pf7 = x[9]
    Qf7 = x[10]
    return d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7

def pack_x(d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7):
    x = [d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7]
    return x
    
def complex_V(V2, V3, V7, d2, d3, d7):
    V2c = V2 * np.exp(1j * d2)
    V3c = V3 * np.exp(1j * d3)
    V7c = V7 * np.exp(1j * d7)
    return V2c, V3c, V7c

def P2(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)
    S2calc = V2c * (np.conj(V2c) - np.conj(V1)) * np.conj(Y12) + V2c * (np.conj(V2c) - np.conj(V3c)) * np.conj(Y23)
    return np.real(S2calc) - np.real(S2sp)

def Q2(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)
    S2calc = V2c * (np.conj(V2c) - np.conj(V1)) * np.conj(Y12) + V2c * (np.conj(V2c) - np.conj(V3c)) * np.conj(Y23)
    return np.imag(S2calc) - np.imag(S2sp)

def P3(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)

    S3calc = V3c * (np.conj(V3c) - np.conj(V1)) * np.conj(Y13) + V3c * (np.conj(V3c) - np.conj(V2c)) * np.conj(Y23) + Pf3 + 1j * Qf3
    return np.real(S3calc) - np.real(S3sp)

def Q3(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)

    S3calc = V3c * (np.conj(V3c) - np.conj(V1)) * np.conj(Y13) + V3c * (np.conj(V3c) - np.conj(V2c)) * np.conj(Y23) + Pf3 + 1j * Qf3
    return np.imag(S3calc) - np.imag(S3sp)

def P4(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)

    P4calc = V4 * (V4 - V5) * G45 + V4 * (V4 - V6) * G46 + Pt4
    return P4calc - P4sp

def P5(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)

    P5calc = V5 * (V5 - V4) * G45 + V5 * (V5 - V6) * G56
    return P5calc - P5sp

def P6(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)

    P6calc = V6 * (V6 - V4) * G46 + V6 * (V6 - V5) * G56
    return P6calc - P6sp

def P7(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)

    S7calc = V7c * (np.conj(V7c) - np.conj(V8)) * np.conj(Y78) + Pf7 + 1j * Qf7
    return np.real(S7calc) - np.real(S7sp)

def Q7(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)

    S7calc = V7c * (np.conj(V7c) - np.conj(V8)) * np.conj(Y78) + Pf7 + 1j * Qf7
    return np.imag(S7calc) - np.imag(S7sp)

def VSC1(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)

    loss1 = a + b * np.sqrt(Pf3**2 + Qf3**2) / V3 + c * (Pf3**2 + Qf3**2) / V3**2
    return loss1 - Pf3 - Pt4

def VSC2(x):
    d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7 = unpack_x(x)
    V2c, V3c, V7c = complex_V(V2, V3, V7, d2, d3, d7)

    loss2 = a + b * np.sqrt(Pf7**2 + Qf7**2) / V7 + c * (Pf7**2 + Qf7**2) / V7**2
    return loss2 - Pf7 - Pt6


# start loop
func = [P2, Q2, P3, Q3, P4, P5, P6, P7, Q7, VSC1, VSC2]

d2 = 0.0
d3 = 0.0
d7 = 0.0
V2 = 1.0
V3 = 1.0
V5 = 1.0
V6 = 1.0
Pf3 = 0.0
Pt4 = 0.0
Pf7 = 0.0
Qf7 = 0.0

delta = 1e-6

n_unk = len(func)

x = pack_x(d2, d3, d7, V2, V3, V5, V6, Pf3, Pt4, Pf7, Qf7)

# Solve f = - J Ax
for k in range(10):

    f = np.zeros(n_unk, dtype=float)
    for i in range(n_unk):
        f[i] = func[i](x)

    J = np.zeros((n_unk, n_unk), dtype=float)
    for i in range(n_unk):
        for j in range(n_unk):
            x1 = x.copy()
            x1[j] += delta
            f1 = func[i](x1)
            J[i, j] = (f1 - f[i]) / delta

    
    Ax = np.linalg.solve(J, -f)

    x += Ax

    err = max(abs(f))
    print(f'Iteration {k}, error: {err}')


    
