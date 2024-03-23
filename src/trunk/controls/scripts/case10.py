# Made up case with 10 nodes, 2 VSCs, 1 controlled transformer
import numpy as np
import pandas as pd

# Data 1
d1 = 0.0
d10 = 0.0

V1 = 1.0
V4 = 1.01
V7 = 0.99
V10 = 1.0

S2sp = - (0.3 + 0.1 * 1j)
S3sp = - (0.2 + 0.05 * 1j)
P4sp = 0.2
P5sp = 0.1
P6sp = 0.15
S7sp = - (0.1 + 0.1 * 1j)
S8sp = - (0.2 + 0.05 * 1j)
S9sp = - (0.3 + 0.1 * 1j)

Pf8 = -0.1
Pt6 = 0.12
Qf3 = 0.05

# Data 2
m = 1.0
Ys = 1.0 / (0.0 + 0.1 * 1j)

Y12 = 1.0 / (0.1 + 0.3 * 1j)
Y13 = 1.0 / (0.1 + 0.3 * 1j)
Y23 = 1.0 / (0.1 + 0.3 * 1j)
G45 = 1.0 / 0.1
G46 = 1.0 / 0.1
G56 = 1.0 / 0.1
Y78 = 1.0 / (0.1 + 0.3 * 1j)
Y89 = 1.0 / (0.1 + 0.3 * 1j)
Y910 = 1.0 / (0.1 + 0.3 * 1j)

a = 0.01
b = 0.02
c = 0.04


# Equations
# x = [d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8]
x = []


def unpack_x(x):
    d2 = x[0]
    d3 = x[1]
    d7 = x[2]
    d8 = x[3]
    d9 = x[4]
    V2 = x[5]
    V3 = x[6]
    V5 = x[7]
    V6 = x[8]
    V8 = x[9]
    V9 = x[10]
    tau1 = x[11]
    Pf3 = x[12]
    Pt4 = x[13]
    Pf7 = x[14]
    Qf7 = x[15]
    Qf8 = x[16]
    return d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8

def pack_x(d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8):
    x = [d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8]
    return x
    
def complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9):
    V2c = V2 * np.exp(1j * d2)
    V3c = V3 * np.exp(1j * d3)
    V7c = V7 * np.exp(1j * d7)
    V8c = V8 * np.exp(1j * d8)
    V9c = V9 * np.exp(1j * d9)
    return V2c, V3c, V7c, V8c, V9c

def P2(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S2calc = V2c * (np.conj(V2c) - np.conj(V1)) * np.conj(Y12) + V2c * (np.conj(V2c) - np.conj(V3c)) * np.conj(Y23)
    return np.real(S2calc) - np.real(S2sp)

def Q2(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S2calc = V2c * (np.conj(V2c) - np.conj(V1)) * np.conj(Y12) + V2c * (np.conj(V2c) - np.conj(V3c)) * np.conj(Y23)
    return np.imag(S2calc) - np.imag(S2sp)

def P3(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S3calc = V3c * (np.conj(V3c) - np.conj(V1)) * np.conj(Y13) + V3c * (np.conj(V3c) - np.conj(V2c)) * np.conj(Y23) + Pf3 + 1j * Qf3
    return np.real(S3calc) - np.real(S3sp)

def Q3(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S3calc = V3c * (np.conj(V3c) - np.conj(V1)) * np.conj(Y13) + V3c * (np.conj(V3c) - np.conj(V2c)) * np.conj(Y23) + Pf3 + 1j * Qf3
    return np.imag(S3calc) - np.imag(S3sp)

def P4(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    P4calc = V4 * (V4 - V5) * G45 + V4 * (V4 - V6) * G46 + Pt4
    return P4calc - P4sp

def P5(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    P5calc = V5 * (V5 - V4) * G45 + V5 * (V5 - V6) * G56
    return P5calc - P5sp

def P6(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    P6calc = V6 * (V6 - V4) * G46 + V6 * (V6 - V5) * G56 + Pt6
    return P6calc - P6sp

def P7(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S7calc = V7c * (np.conj(V7c) - np.conj(V8c)) * np.conj(Y78) + Pf7 + 1j * Qf7
    return np.real(S7calc) - np.real(S7sp)

def Q7(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S7calc = V7c * (np.conj(V7c) - np.conj(V8c)) * np.conj(Y78) + Pf7 + 1j * Qf7
    return np.imag(S7calc) - np.imag(S7sp)

def P8(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S8calc = V8c * (np.conj(V8c) - np.conj(V7c)) * np.conj(Y78) + V8c * (np.conj(V8c) - np.conj(V9c)) * np.conj(Y89) + Pf8 + 1j * Qf8
    return np.real(S8calc) - np.real(S8sp)

def Q8(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S8calc = V8c * (np.conj(V8c) - np.conj(V7c)) * np.conj(Y78) + V8c * (np.conj(V8c) - np.conj(V9c)) * np.conj(Y89) + Pf8 + 1j * Qf8
    return np.imag(S8calc) - np.imag(S8sp)

def P9(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S9calc = V9c * (np.conj(V9c) - np.conj(V8c)) * np.conj(Y89) + V9c * (np.conj(V9c) - np.conj(V10)) * np.conj(Y910)
    return np.real(S9calc) - np.real(S9sp)

def Q9(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    S9calc = V9c * (np.conj(V9c) - np.conj(V8c)) * np.conj(Y89) + V9c * (np.conj(V9c) - np.conj(V10)) * np.conj(Y910)
    return np.imag(S9calc) - np.imag(S9sp)

def VSC1(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    loss1 = a + b * np.sqrt(Pf3**2 + Qf3**2) / V3 + c * (Pf3**2 + Qf3**2) / V3**2
    return loss1 - Pf3 - Pt4

def VSC2(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    loss2 = a + b * np.sqrt(Pf7**2 + Qf7**2) / V7 + c * (Pf7**2 + Qf7**2) / V7**2
    return loss2 - Pf7 - Pt6

def Ptr(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    Strcalc = V8**2 * np.conj(Ys) / m**2 - V8c * np.conj(V10) * np.conj(Ys) / (m * np.exp(1j * tau1))
    return np.real(Strcalc) - np.real(Pf8 + 1j * Qf8)

def Qtr(x):
    d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
    V2c, V3c, V7c, V8c, V9c = complex_V(V2, V3, V7, V8, V9, d2, d3, d7, d8, d9)
    Strcalc = V8**2 * np.conj(Ys) / m**2 - V8c * np.conj(V10) * np.conj(Ys) / (m * np.exp(1j * tau1))
    return np.imag(Strcalc) - np.imag(Pf8 + 1j * Qf8)


# start loop
func = [P2, Q2, P3, Q3, P4, P5, P6, P7, Q7, P8, Q8, P9, Q9, VSC1, VSC2, Ptr, Qtr]

d2 = 0.0
d3 = 0.0
d7 = 0.0
d8 = 0.0
d9 = 0.0
V2 = 1.0
V3 = 1.0
V5 = 1.0
V6 = 1.0
V8 = 1.0
V9 = 1.0
tau1 = 0.0
Pf3 = 0.0
Pt4 = 0.0
Pf7 = 0.0
Qf7 = 0.0
Qf8 = 0.0

delta = 1e-6

n_unk = len(func)

x = pack_x(d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8)

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

print(f'Final x: {x}')
    
# Debug
# d2, d3, d7, d8, d9, V2, V3, V5, V6, V8, V9, tau1, Pf3, Pt4, Pf7, Qf7, Qf8 = unpack_x(x)
# i78 = (V7 * np.exp(1j * d7) - V8 * np.exp(1j * d8)) * Y78
# i98 = (V9 * np.exp(1j * d9) - V8 * np.exp(1j * d8)) * Y89
# itr8 = - (i78 + i98)
# str8 = V8 * np.exp(1j * d8) * np.conj(itr8)
# print(str8)

# i56 = (V5 - V6) * G56
# i46 = (V4 - V6) * G46
# pt6 = V6 * (i56 + i46)
# print(pt6)

# i31 = (V3 * np.exp(1j * d3) - V1) * Y13
# i32 = (V3 * np.exp(1j * d3) - V2 * np.exp(1j * d2)) * Y23
# sfvsc1 = - V3 * np.exp(1j * d3) * (np.conj(i31) + np.conj(i32)) + S3sp
# print(sfvsc1)

