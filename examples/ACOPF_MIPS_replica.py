import math
import numpy as np
from scipy import sparse
from ACOPF_init_test import *
from ACOPF_functions import *
import GridCalEngine.api as gce


def init_state(N, L):

    ID_V, ID_TH, ID_PG, ID_QG, ID_PHI, ID_PIJ, ID_QIJ, ID_PJI, ID_QJI, ID_LIJ = indexing()

    for n in N:
        Y[]

    return


def solver(nc, mu, gam):
    N, L, LINES, V_U, V_L, P_U, P_L, Q_U, Q_L, PD, QD, SMAX, DELTA_MAX = grid_parameters(nc:gce.NumericalCircuit)

    mu = 10
    gamma = 100
    error = 10000
    YK = INIT_STATE()
    PI = [0] * NE
    LAMBDA = [0] * NI
    T = [0] * NI

    while error < mu:


        f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx = feval(N, L, LINES, V_U, V_L, P_U, P_L, Q_U, Q_L, PD, QD, SMAX, DELTA_MAX, YK)

        M = fxx + Gxx @ PI + Hxx @ LAMBDA+ Hx.transpose() @ 1/T @ LAMBDA @ Hx
        N =  fx.transpose() + Gx.transpose() @ PI + Hx.transpose() @ LAMBDA + Hx.transpose() @ 1/T @ (gamma * E - LAMBDA @ H)

        J1 = sparse.hstack([M, Gx.transpose()])
        J2 = sparse.hstack([Gx, sparse.csc_matrix((NE,NE))])

        J = sparse.vstack([J1, J2])

        r = - sparse.vstack([N, G])

        dXP = sparse.linalg.spsolve(J, r)

        dX = dXP[0 : NV]
        dP = dXP[NV : NE + NV]
        dT = - H - T - Hx @ dX
        dL = - LAMBDA + 1/T @ (gamma * E - LAMBDA_MAT @ dP)

        alfap = step_calculation(T, dT)
        alfad = step_calculation(L, dL)

    return



def brock_eval():
    return



def feval(N, L, LINES, V_U, V_L, P_U, P_L, Q_U, Q_L, PD, QD, SMAX, DELTA_MAX, YK):



    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx


def step_calculation():
    return





