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
    error = 1000000
    #YK = INIT_STATE()
    NV = 3
    NE = 1
    NI = 2

    k = 0

    X = np.array([8., 5., 1.])
    PI = sparse.csc_matrix([1] * NE)
    LAMBDA = sparse.csc_matrix([1] * NI)
    LAMBDA_MAT = sparse.dia_matrix(([1] * NI, 0), shape = (NI, NI)).tocsc()
    T = sparse.csc_matrix([1] * NI)
    T_MAT = sparse.dia_matrix(([1] * NI, 0), shape = (NI, NI)).tocsc()
    E = sparse.csc_matrix(([1] * NI, ([i for i in range(NI)],[0] * NI)), shape = (NI, 1))
    while (error > gamma):


        #f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx = feval(N, L, LINES, V_U, V_L, P_U, P_L, Q_U, Q_L, PD, QD, SMAX, DELTA_MAX, YK)
        f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx = NLP_test(X, LAMBDA, PI)

        M = fxx + Gxx + Hxx + Hx @ sparse.linalg.inv(T_MAT) @ LAMBDA_MAT @ Hx.transpose()
        N = fx + Hx @ LAMBDA.transpose() + Hx @ sparse.linalg.inv(T_MAT) @ (gamma * E + LAMBDA_MAT @ H) + Gx @ PI.transpose()

        J1 = sparse.hstack([M, Gx])
        J2 = sparse.hstack([Gx.transpose(), sparse.csc_matrix((NE,NE))])

        J = sparse.vstack([J1, J2]).tocsc()

        r = - sparse.vstack([N, G]).tocsc()

        dXP = sparse.linalg.spsolve(J, r)

        dX = dXP[0 : NV]
        dXsp = sparse.csc_matrix(dX).transpose()
        dP = sparse.csc_matrix(dXP[NV : NE + NV])

        dT = - H - T.transpose() - Hx.transpose() @ dXsp
        dL = - LAMBDA.transpose() + sparse.linalg.inv(T_MAT) @ (gamma * E - LAMBDA_MAT @ dT)

        alphap = step_calculation(T.toarray(), dT.transpose().toarray(), NI)
        alphad = step_calculation(LAMBDA.toarray(), dL.transpose().toarray(), NI)
        #TAU = 0.9995
        #alphap = min(min(TAU * T.transpose() / abs(dT)), [1])[0]
        #alphad = min(min(TAU * LAMBDA.transpose() / abs(dL)), [1])[0]


        alpha = 0.3
        X += dX * alphap
        T += dT.transpose() * alphap
        LAMBDA += dL.transpose() * alphad
        PI += dP * alphad

        T_MAT = sparse.dia_matrix((T.toarray(), 0), shape = (NI, NI)).tocsc()
        LAMBDA_MAT =  sparse.dia_matrix((LAMBDA.toarray(), 0), shape = (NI, NI)).tocsc()

        error = max(max(abs(dX)), max(abs(dL)), max(abs(dT)), max(abs(dP)))
        newgamma = 0.1 * (T @ LAMBDA.transpose()).toarray()[0][0]/2
        gamma = max(newgamma, 1e-8)

        k+=1
        if k == 100:
            break
        print(X, error, gamma)
    print('SOLUTION: ',X, NLP_test(X, LAMBDA, PI)[0])
    return



def NLP_test(x, LAMBDA, PI):

    NV = 3
    NE = 1
    NI = 2

    f = -x[0] * x[1] - x[1] * x[2]
    fx = sparse.csc_matrix([[-x[1]], [-x[0] - x[2]], [-x[1]]])
    fxx = sparse.csc_matrix([[0, -1, 0], [-1, 0, -1], [0, -1, 0]])

    G = sparse.csc_matrix([x[0] - x[1] - x[2]])
    Gx = sparse.csc_matrix([[1],[-1], [-1]])
    Gxx = PI.toarray()[0][0] * sparse.csc_matrix((3,3))

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


def step_calculation(V, dV, NI):

    
    alpha = 1

    for i in range(NI):

        if dV[0][i] >= 0:
            pass
        else:
            alpha = min(alpha, -V[0][i]/dV[0][i])
    
    alpha = min(0.995*alpha, 1)

    return alpha





if __name__ == '__main__':
    solver()