import math
import numpy as np


# Functions used in the formulation of the AC-OPF problem

# Objective function

def f(x, c2, c1):
    # x = [P1, P2, ...]
    return sum(c2[i] * x[i] ** 2 + c1[i] * x[i] for i in range(len(x)))


def gradf(x, c2, c1):
    lis = []
    lis.extend([2 * x[i] * c2[i] + c1[i] for i in range(len(x))])
    return np.array(lis)


def hessf(x, c2):
    hess = np.zeros((len(x), len(x)))
    for i in range(len(x)):
        hess[i][i] = 2 * c2[i]
    return hess

# Equality constraints


def pij(x, gii, gij, bij):
    # x = [Pij, vi, vj, phiij]
    # return gij * (x[1] ** 2 - x[1] * x[2] * math.cos(x[3])) - bij * x[1] * x[2] * math.sin(x[3]) - x[0]
    return gii * (x[1] ** 2) + x[1] * x[2] * (gij * math.cos(x[3]) + bij * math.sin(x[3])) - x[0]  # Check 3.19 ExaGO


def grad_pij(x, gii, gij, bij):
    # grad0 = -1
    # grad1 = gij * (2 * x[1] - x[2] * math.cos(x[3])) - bij * x[2] * math.sin(x[3])
    # grad2 = gij * (- x[1] * math.cos(x[3])) - bij * x[1] * math.sin(x[3])
    # grad3 = gij * (x[1] * x[2] * math.sin(x[3])) - bij * x[1] * x[2] * math.cos(x[3])

    grad0 = -1
    grad1 = 2 * gii * x[1] + x[2] * (gij * math.cos(x[3]) + bij * math.sin(x[3]))
    grad2 = x[1] * (gij * math.cos(x[3]) + bij * math.sin(x[3]))
    grad3 = x[1] * x[2] * (- gij * math.sin(x[3]) + bij * math.cos(x[3]))

    return np.array([grad0, grad1, grad2, grad3])


def hess_pij(x, gii, gij, bij):

    hess = np.zeros((4, 4))

#    hess[1][1] = 2 * gij
#    hess[1][2] = -gij * math.cos(x[3]) - bij * math.sin(x[3])
#    hess[1][3] = gij * x[2] * math.sin(x[3]) - bij * x[2] * math.cos(x[3])
#    hess[2][3] = gij * x[1] * math.sin(x[3]) - bij * x[1] * math.cos(x[3])
#    hess[3][3] = gij * x[1] * x[2] * math.cos(x[3]) + bij * x[1] * x[2] * math.sin(x[3])

    hess[1][1] = 2 * gii
    hess[1][2] = gij * math.cos(x[3]) - bij * math.sin(x[3])
    hess[1][3] = x[2] * (- gij * math.sin(x[3]) + bij * math.cos(x[3]))
    hess[2][3] = x[1] * (- gij * math.sin(x[3]) + bij * math.cos(x[3]))
    hess[3][3] = x[1] * x[2] * (- gij * math.cos(x[3]) - bij * math.sin(x[3]))

    hess[2][1] = hess[1][2]
    hess[3][1] = hess[1][3]
    hess[3][2] = hess[2][3]

    return hess


def qij(x, gij, bii, bij):
    # x = [Pij, vi, vj, phiij]
    # return bij * (x[1] * x[2] * math.cos(x[3]) - x[1] ** 2) - gij * x[1] * x[2] * math.sin(x[3]) - x[0]

    return -bii * (x[1] ** 2) + x[1] * x[2] * (- bij * math.cos(x[3]) + gij * math.sin(x[3])) - x[0]  # Check 3.20 ExaGO


def grad_qij(x, gij, bii, bij):

    # grad0 = -1
    # grad1 = bij * (x[2] * math.cos(x[3]) - 2 * x[1]) - gij * x[2] * math.sin(x[3])
    # grad2 = bij * (x[1] * math.cos(x[3])) - gij * x[1] * math.sin(x[3])
    # grad3 = -bij * (x[1] * x[2] * math.sin(x[3])) - gij * x[1] * x[2] * math.cos(x[3])

    grad0 = -1
    grad1 = - 2 * bii * x[1] + x[2] * (- bij * math.cos(x[3]) + gij * x[2] * math.sin(x[3]))
    grad2 = x[1] * (- bij * math.cos(x[3]) + gij * math.sin(x[3]))
    grad3 = x[1] * x[2] * (bij * math.sin(x[3]) + gij * math.cos(x[3]))

    return np.array([grad0, grad1, grad2, grad3])


def hess_qij(x, gij, bii, bij):

    hess = np.zeros((4, 4))

    # hess[1][1] = -2 * bij
    # hess[1][2] = bij * math.cos(x[3]) - gij * math.sin(x[3])
    # hess[1][3] = -bij * x[2] * math.sin(x[3]) - gij * x[2] * math.cos(x[3])
    # hess[2][3] = -bij * x[1] * math.sin(x[3]) - gij * x[1] * math.cos(x[3])
    # hess[3][3] = -bij * x[1] * x[2] * math.cos(x[3]) + gij * x[1] * x[2] * math.sin(x[3])

    hess[1][1] = - 2 * bii
    hess[1][2] = - bij * math.cos(x[3]) - gij * math.sin(x[3])
    hess[1][3] = x[2] * (bij * math.sin(x[3]) + gij * math.cos(x[3]))
    hess[2][3] = x[1] * (bij * math.sin(x[3]) + gij * math.cos(x[3]))
    hess[3][3] = x[1] * x[2] * (bij * math.cos(x[3]) - gij * math.sin(x[3]))

    hess[2][1] = hess[1][2]
    hess[3][1] = hess[1][3]
    hess[3][2] = hess[2][3]

    return hess


def pi(x, pd):
    # x = [Pi, Pij, Pik, ...]
    return sum(x[1:]) + pd - x[0]


def grad_pi(x):
    lis = [-1]
    lis.extend([1] * len(x[1:]))
    return np.array(lis)


def qi(x, qd):
    # x = [Qi, Qij, Qik, ...]
    return sum(x[1:]) + qd - x[0]


def grad_qi(x):
    lis = [-1]
    lis.extend([1] * len(x[1:]))
    return np.array(lis)


def ploss(x, rij):
    # x = [lij, Pij, Pji]
    return x[1] + x[2] - rij * x[0]


def grad_ploss():
    return np.array([-1, 1, 1])


def qloss(x, xij):
    # x = [lij, Qij, Qji]
    return x[1] + x[2] - xij * x[0]


def grad_qloss():
    return np.array([-1, 1, 1])


# Inequality functions:

def smax(x, su):
    # x = [Pij, Qij]
    return x[0] ** 2 + x[1] ** 2 - su


def grad_smax(x):
    return np.array([2 * x[0], 2 * x[1]])


def hess_smax():
    return np.array([[2, 0], [0, 2]])

################################
