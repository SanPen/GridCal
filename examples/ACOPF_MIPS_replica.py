import math
import numpy as np
from scipy import sparse
#from ACOPF_init_test import *
#from ACOPF_functions import *
#import GridCalEngine.api as gce


def init_state(N, L):

    ID_V, ID_TH, ID_PG, ID_QG, ID_PHI, ID_PIJ, ID_QIJ, ID_PJI, ID_QJI, ID_LIJ = indexing()

    for n in N:
        pass

    return


#def solver(nc, mu, gam):
def solver():


    #N, L, LINES, V_U, V_L, P_U, P_L, Q_U, Q_L, PD, QD, SMAX, DELTA_MAX = grid_parameters(nc:gce.NumericalCircuit)

    mu = 1
    gamma = 1
    error = 100
    #YK = INIT_STATE()
    NV = 3
    NE = 0
    NI = 2

    X = [0, 0, 0]
    PI = sparse.csc_matrix([0] * NE)
    LAMBDA = sparse.csc_matrix([0] * NI)
    LAMBDA_MAT = sparse.dia_matrix(([0] * NI, 0), shape = (NI, NI))
    T = sparse.csc_matrix([0] * NI)
    T_MAT = sparse.dia_matrix(([1] * NI, 0), shape = (NI, NI))
    E = sparse.csc_matrix([1] * NV)
    while (error > gamma):


        #f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx = feval(N, L, LINES, V_U, V_L, P_U, P_L, Q_U, Q_L, PD, QD, SMAX, DELTA_MAX, YK)
        f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx = NLP_test(X, LAMBDA, PI)

        M = fxx + Gxx + Hxx  + Hx @ sparse.linalg.inv(T_MAT) @ LAMBDA_MAT @ Hx.transpose()
        N =  fx + Hx @ LAMBDA + Hx @ sparse.linalg.inv(T_MAT) @ (gamma * E - LAMBDA_MAT @ H) #+ Gx.transpose() @ PI

        J1 = sparse.hstack([M, Gx.transpose()])
        J2 = sparse.hstack([Gx, sparse.csc_matrix((NE,NE))])

        J = sparse.vstack([J1, J2]).tocsc()

        r = - sparse.vstack([N, G]).tocsc()

        dXP = sparse.linalg.spsolve(J, r)

        dX = dXP[0 : NV]
        dP = dXP[NV : NE + NV]
        dT = - H - T - Hx.transpose() @ dX
        dL = - LAMBDA + sparse.linalg.inv(T_MAT) @ (gamma * E - LAMBDA_MAT @ dP)

        #alfap = step_calculation(T, dT)
        #alfad = step_calculation(L, dL)
        TAU = 0.9995
        alphap =min(min(TAU * T / abs(dT)), 1)
        alphad = min(min(TAU * LAMBDA / abs(dL)), 1)


        alpha = 0.3
        X += dX * alphap
        T += dT * alphap
        LAMBDA += dL * alphad
        error = max(max(abs(dX)), max(abs(dL)), max(abs(dT)))
        newgamma = gamma * 0.1
        gamma = max(newgamma, 1e-8)
        print(X, error)
    print('SOLUTION: ',X, NLP_test(X, LAMBDA, PI)[0])
    return



def NLP_test(x, LAMBDA, PI):

    NV = 3
    NE = 0
    NI = 2

    f = -x[0] * x[1] - x[1] * x[2]
    fx = sparse.csc_matrix([[-x[1]],[-x[0] - x[2]],[-x[1]]])
    fxx = sparse.csc_matrix([[0, -1, 0],[-1, 0, -1],[0, -1, 0]])

    G = sparse.csc_matrix((0,0))
    Gx = sparse.csc_matrix((0,0))
    Gxx = sparse.csc_matrix((3,3))

    H = sparse.csc_matrix([[x[0] ** 2 - x[1] ** 2 + x[2] ** 2 - 2], [x[0] ** 2 + x[1] ** 2 + x[2] ** 2 - 10]])
    Hx = sparse.csc_matrix([[2 * x[0], 2 * x[0]],[-2 * x[1], 2* x[1]],[2 * x[2], 2 * x[2]]])
    Hxx = LAMBDA.toarray()[0][0] * sparse.csc_matrix([[2, 0, 0], [0, -2, 0], [0, 0, 2]])
    Hxx += LAMBDA.toarray()[0][1] * sparse.csc_matrix([[2, 0, 0], [0, 2, 0], [0, 0, 2]])



    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx





def brock_eval(x):

    NV = 3
    NE = 0
    NI = 2

    f = 100 * (x[1] - x[0] ** 2) ** 2 + (1 - x[0]) ** 2
    fx = sparse.csc_matrix([[400 * (x[1] ** 3 - x[0] * x[1]) + 2 * x[0] -  2],[ 200 * (x[1] - x[0]**2 )]])
    fxx =sparse.csc_matrix([[1200 * x[0]**2 - x[1] + 2, -400 * x[0]],[-400 * x[0], 200]])

    G = sparse.csc_matrix((0,1))
    Gx = sparse.csc_matrix((NE, NV))
    Gxx = sparse.csc_matrix((NV, NV))

    H = sparse.csc_matrix((0, 1))
    Hx = sparse.csc_matrix((NI, NV))
    Hxx = sparse.csc_matrix((NV, NV))

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx



def feval(N, L, LINES, V_U, V_L, P_U, P_L, Q_U, Q_L, PD, QD, SMAX, DELTA_MAX, YK):



    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx


def step_calculation():
    return





