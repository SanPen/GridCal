
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("TkAgg")


# data
z12 = 0.001 + 0.1 * 1j  # linea AC 1-2
z34 = 0.05              # linea DC 3-4
z56 = 0.001 + 0.1 * 1j  # linea AC 5-6

y12 = 1 / z12
g34 = 1 / z34
y56 = 1 / z56

a1 = 0.0001
b1 = 0.015
c1 = 0.02

a2 = 0.0001
b2 = 0.015
c2 = 0.02

V1 = 1.05 * np.exp(1j * 0.0)
Vm2 = 1.03
Sl2 = 0.4 + 0.3 * 1j  # load at 2
Vm3 = 1.04
Pf4 = -0.98
Qt5 = 0.3
Sl5 = 1.0 + 0.5 * 1j  # load at 5
V6 = 1 * np.exp(1j * 0.0)

def pol2rec(m, a):
    return m * np.exp(1j * a)

def f1(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2):
    # balance de P en 2
    V2 = Vm2 * np.exp(1j * d2)
    V5 = Vm5 * np.exp(1j * d5)

    i2 = (V2 - V1) * y12 + np.conj(Sl2 / V2) + np.conj((Pf2 + 1j * Qf2) / V2)
    # i2 = (V2 - V1) * y12 + np.conj(Sl2 / V2) + np.conj((Pf2 + 1j * Qf2) / V2) + (V2 - V5) * y25
    return np.real(i2)

def f2(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2):
    # balance de Q en 2
    V2 = Vm2 * np.exp(1j * d2)
    V5 = Vm5 * np.exp(1j * d5)

    i2 = (V2 - V1) * y12 + np.conj(Sl2 / V2) + np.conj((Pf2 + 1j * Qf2) / V2)
    # i2 = (V2 - V1) * y12 + np.conj(Sl2 / V2) + np.conj((Pf2 + 1j * Qf2) / V2) + (V2 - V5) * y25
    return np.imag(i2)

def f3(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2):
    # balance de P en 5
    V2 = Vm2 * np.exp(1j * d2)
    V5 = Vm5 * np.exp(1j * d5)

    i5 = (V5 - V6) * y56 + np.conj(Sl5 / V5) + np.conj((Pt5 + 1j * Qt5) / V5) 
    # i5 = (V5 - V6) * y56 + np.conj(Sl5 / V5) + np.conj((Pt5 + 1j * Qt5) / V5) + (V5 - V2) * y25
    return np.real(i5)

def f4(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2):
    # balance de Q en 5
    V2 = Vm2 * np.exp(1j * d2)
    V5 = Vm5 * np.exp(1j * d5)

    i5 = (V5 - V6) * y56 + np.conj(Sl5 / V5) + np.conj((Pt5 + 1j * Qt5) / V5) 
    # i5 = (V5 - V6) * y56 + np.conj(Sl5 / V5) + np.conj((Pt5 + 1j * Qt5) / V5) + (V5 - V2) * y25
    return np.imag(i5)

def f5(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2):
    # balance de P en 3 (DC)
    i3 = Pt3 / Vm3 + (Vm3 - Vm4) * g34
    return i3

def f6(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2):
    # balance de P en 4 (DC)
    i4 = Pf4 / Vm4 + (Vm4 - Vm3) * g34
    return i4

def f7(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2):
    # los convertidores no tienen impedancia y se trabaja con las potencias como incógnitas
    # Pfrom + Pt + Ploss = 0 en el convertidor 1
    ploss1 = a1 + b1 * np.sqrt(Pf2**2 + Qf2**2) / Vm2 + c1 * (Pf2**2 + Qf2**2) / Vm2**2
    return ploss1 - Pf2 - Pt3

def f8(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2):
    # los convertidores no tienen impedancia y se trabaja con las potencias como incógnitas
    # Pfrom + Pt + Ploss = 0 en el convertidor 2
    ploss2 = a2 + b2 * np.sqrt(Pt5**2 + Qt5**2) / Vm5 + c2 * (Pt5**2 + Qt5**2) / Vm5**2
    return ploss2 - Pf4 - Pt5


def x2var(x):
    d2 = x[0]
    d5 = x[1]
    Vm4 = x[2]
    Vm5 = x[3]
    Pf2 = x[4]
    Pt3 = x[5]
    Pt5 = x[6]
    Qf2 = x[7]
    return d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2


def var2x(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2):
    x = np.zeros(8)
    x[0] = d2
    x[1] = d5
    x[2] = Vm4
    x[3] = Vm5
    x[4] = Pf2
    x[5] = Pt3
    x[6] = Pt5
    x[7] = Qf2
    return x


def fx(x):

    d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2 = x2var(x)

    f = np.empty(len(x))

    f[0] = f1(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2)
    f[1] = f2(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2)
    f[2] = f3(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2)
    f[3] = f4(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2)
    f[4] = f5(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2)
    f[5] = f6(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2)
    f[6] = f7(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2)
    f[7] = f8(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2)

    return f


def calc_jacobian(func, x, h=1e-5):
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.

    :param func: Vector-valued function (R^n -> R^m).
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a numpy array.
    """
    nx = len(x)
    f0 = func(x)
    jac = np.zeros((len(f0), nx))

    for i in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[i] += h
        f_plus_h = func(x_plus_h)
        jac[:, i] = (f_plus_h - f0) / h

    return jac


def calc_hessian(func, x, h=1e-5):
    """
    Compute the Hessian matrix of `func` at `x` using finite differences.

    :param func: Scalar-valued function (R^n -> R).
    :param x: Point at which to evaluate the Hessian (numpy array).
    :param h: Small step for finite difference.
    :return: Hessian matrix as a numpy array.
    """
    n = len(x)
    hessian = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            x_ijp = np.copy(x)
            x_ijp[i] += h
            x_ijp[j] += h
            f_ijp = func(x_ijp)

            x_ijm = np.copy(x)
            x_ijm[i] += h
            x_ijm[j] -= h
            f_ijm = func(x_ijm)

            x_jim = np.copy(x)
            x_jim[i] -= h
            x_jim[j] += h
            f_jim = func(x_jim)

            x_jjm = np.copy(x)
            x_jjm[i] -= h
            x_jjm[j] -= h
            f_jjm = func(x_jjm)

            hessian[i, j] = (f_ijp - f_ijm - f_jim + f_jjm) / (4 * h ** 2)

    return hessian


# Initialization
d2 = 0.0
d5 = 0.0
Vm4 = 1.0
Vm5 = 1.0
Pf2 = 1e-10
Pt3 = 1e-10
Pt5 = 1e-10
Qf2 = 1e-10

Nmax = 30
alpha = 1.0
error = []

x = var2x(d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2)

for i in range(Nmax):

    df = fx(x)

    V2 = Vm2 * np.exp(1j * d2)
    V5 = Vm5 * np.exp(1j * d5)

    # J with auto diff
    J = calc_jacobian(fx, x, h=1e-6)

    dx = alpha * np.linalg.solve(J, df)
    ncond = np.linalg.cond(J)

    x -= dx
    d2, d5, Vm4, Vm5, Pf2, Pt3, Pt5, Qf2 = x2var(x)

    error.append(max(abs(df)))


V = np.array([V1,
              pol2rec(Vm2, d2),
              pol2rec(Vm3, 0),
              pol2rec(Vm4, 0),
              pol2rec(Vm5, d5),
              V6])

node_df = pd.DataFrame(data={"Vm": np.abs(V), "Va": np.angle(V)},
                       index=[f'Bus {i+1}' for i in range(6)])
print(node_df)
print("df:", df)

plt.plot(np.arange(Nmax), np.log10(error))
plt.xlabel('Iteration')
plt.ylabel('log10(error)')
plt.show()
