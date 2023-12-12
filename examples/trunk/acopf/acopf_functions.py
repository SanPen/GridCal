import math
import numpy as np


##### Funtions used in the formulation of the AC-OPF problem

# Objective function

def f(x, c2, c1):
    # x = [P1, P2, ...]
    return sum(c2[i] * x[i] ** 2 + c1[i] * x[i] for i in range(len(x)))


def gradf(x, c2, c1):
    l = []
    l.extend([2 * x[i] * c2[i] + c1[i] for i in range(len(x))])
    return np.array(l)


def hessf(x, c2):
    hess = zeros((len(x), len(x)))
    for i in range(len(x)):
        hess[i][i] = 2 * c2[i]
    return hess

# Equality constraints

def Pij(x, Gij, Bij):
    # x = [Pij, vi, vj, phiij]
    return Gij * (x[1] ** 2 - x[1] * x[2] * math.cos(x[3])) - Bij * x[1] * x[2] * math.sin(x[3]) - x[0]


def gradPij(x, Gij, Bij):
    grad0 = -1
    grad1 = Gij * (2 * x[1] - x[2] * math.cos(x[3])) - Bij * x[2] * math.sin(x[3])
    grad2 = Gij * (- x[1] * math.cos(x[3])) - Bij * x[1] * math.sin(x[3])
    grad3 = Gij * (x[1] * x[2] * math.sin(x[3])) - Bij * x[1] * x[2] * math.cos(x[3])

    return np.array([grad0, grad1, grad2, grad3])


def hessPij(x, Gij, Bij):

    hess = np.zeros((4,4))

    hess[1][1] = 2 * Gij
    hess[1][2] = -Gij * math.cos(x[3]) - Bij * math.sin(x[3])
    hess[1][3] = Gij * x[2] * math.sin(x[3]) - Bij * x[2] * math.cos(x[3])
    hess[2][3] = Gij * x[1] * math.sin(x[3]) - Bij * x[1] * math.cos(x[3])
    hess[3][3] = Gij * x[1] * x[2] * math.cos(x[3]) + Bij * x[1] * x[2] * math.sin(x[3])

    hess[2][1] = hess[1][2]
    hess[3][1] = hess[1][3]
    hess[3][2] = hess[2][3]

    return hess


def Qij(x, Gij, Bij):
    # x = [Pij, vi, vj, phiij]
    return Bij * (x[1] * x[2] * math.cos(x[3]) - x[1] ** 2) - Gij * x[1] * x[2] * math.sin(x[3]) - x[0]


def gradQij(x, Gij, Bij):

    grad0 = -1
    grad1 = Bij * (x[2] * math.cos(x[3]) - 2 * x[1]) - Gij * x[2] * math.sin(x[3])
    grad2 = Bij * (x[1] * math.cos(x[3])) - Gij * x[1] * math.sin(x[3])
    grad3 = -Bij * (x[1] * x[2] * math.sin(x[3])) - Gij * x[1] * x[2] * math.cos(x[3])

    return np.array([grad0, grad1, grad2, grad3])


def hessQij(x, Gij, Bij):

    hess = np.zeros((4,4))

    hess[1][1] = -2 * Bij
    hess[1][2] = Bij * math.cos(x[3]) - Gij * math.sin(x[3])
    hess[1][3] = -Bij * x[2] * math.sin(x[3]) - Gij * x[2] * math.cos(x[3])
    hess[2][3] = -Bij * x[1] * math.sin(x[3]) - Gij * x[1] * math.cos(x[3])
    hess[3][3] = -Bij * x[1] * x[2] * math.cos(x[3]) + Gij * x[1] * x[2] * math.sin(x[3])

    hess[2][1] = hess[1][2]
    hess[3][1] = hess[1][3]
    hess[3][2] = hess[2][3]

    return


def Pi(x, Pdi):
    # x = [Pi, Pij, Pik, ...]
    return sum(x[1:]) + Pdi - x[0]


def gradPi(x):
    l = [-1]
    l.extend([1] * len(x[1:]))
    return np.array(l)


def Qi(x, Qdi):
    # x = [Qi, Qij, Qik, ...]
    return sum(x[1:]) + Qdi - x[0]


def gradQi(x):
    l = [-1]
    l.extend([1] * len(x[1:]))
    return np.array(l)


def PLoss(x, Rij):
    # x = [lij, Pij, Pji]
    return x[1] + x[2] - Rij * x[0]


def gradPloss():
    return np.array([-1, 1, 1])


def QLoss(x, Xij):
    # x = [lij, Qij, Qji]
    return x[1] + x[2] - Xij * x[0]


def gradQLoss():
    return np.array([-1, 1, 1])


# Inequality functions:

def Smax(x, su):
    # x = [Pij, Qij]
    return su - x[0] ** 2 - x[1] ** 2


def gradSmax(x):
    return np.array([-2 * x[0], -2 * x[1]])


def hessSmax():
    return np.array([[-2, 0], [0, -2]])

################################
