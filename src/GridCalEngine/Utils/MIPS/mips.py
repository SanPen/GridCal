import math
import numpy as np
from scipy.sparse import csc_matrix as csc
from scipy import sparse
import timeit
from GridCalEngine.Utils.MIPS.ipm_test import brock_eval, NLP_test
from GridCalEngine.basic_structures import Vec, Mat
from typing import Callable, Tuple


# from ACOPF_init_test import *
# from ACOPF_functions import *
# import GridCalEngine.api as gce


# def solver(nc, mu, gam):
def solver(X0: Vec,
           NV: int,
           NE: int,
           NI: int,
           f_eval: Callable[[Vec, csc, csc], Tuple[Vec, csc, csc, csc, csc, csc, csc, csc, csc]],
           step_calculator: Callable[[Vec, Vec, int], float],
           gamma0=10,
           max_iter=100):
    '''

    :param X0:
    :param NV:
    :param NE:
    :param NI:
    :param f_eval:
    :param step_calculator:
    :param gamma0:
    :param max_iter:
    :return:
    '''
    START = timeit.default_timer()

    # Init iteration values
    error = 1000000
    k = 0
    X = X0.copy()
    gamma = gamma0

    # Init multiplier values. Defaulted at 1.
    PI = csc(np.ones(NE))
    LAMBDA = csc(np.ones(NI))
    LAMBDA_MAT = sparse.dia_matrix((np.ones(NI), 0), shape=(NI, NI)).tocsc()
    T = csc(np.ones(NI))
    T_MAT = sparse.dia_matrix((np.ones(NI), 0), shape=(NI, NI)).tocsc()
    inv_T = sparse.dia_matrix((np.ones(NI), 0), shape=(NI, NI)).tocsc()
    E = csc(np.ones(NI)).transpose()

    while error > gamma:

        # Evaluate the functions, gradients and hessians at the current iteration.
        f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx = f_eval(X, LAMBDA, PI)

        # Compute the submatrices of the reduced NR method
        M = fxx + Gxx + Hxx + Hx @ inv_T @ LAMBDA_MAT @ Hx.transpose()
        N = fx + Hx @ LAMBDA.transpose() + Hx @ inv_T @ (gamma * E + LAMBDA_MAT @ H) + Gx @ PI.transpose()

        # Stack the submatrices and vectors
        J1 = sparse.hstack([M, Gx])
        J2 = sparse.hstack([Gx.transpose(), csc((NE, NE))])
        J = sparse.vstack([J1, J2]).tocsc()
        r = - sparse.vstack([N, G]).tocsc()

        # Find the reduced problem residuals and split them
        dXP = sparse.linalg.spsolve(J, r)
        dX = dXP[0: NV]
        dXsp = csc(dX).transpose()
        dP = csc(dXP[NV: NE + NV])

        # Calculate the inequalities residuals using the reduced problem residuals
        dT = - H - T.transpose() - Hx.transpose() @ dXsp
        dL = - LAMBDA.transpose() + inv_T @ (gamma * E - LAMBDA_MAT @ dT)

        # Compute the maximum step allowed
        alphap = step_calculator(T.toarray(), dT.transpose().toarray(), NI)
        alphad = step_calculator(LAMBDA.toarray(), dL.transpose().toarray(), NI)

        # Update the values of the variables and multipliers
        X += dX * alphap
        T += dT.transpose() * alphap
        LAMBDA += dL.transpose() * alphad
        PI += dP * alphad
        T_MAT = sparse.dia_matrix((T.toarray(), 0), shape=(NI, NI)).tocsc()
        inv_T = sparse.dia_matrix((1 / T.toarray(), 0), shape=(NI, NI)).tocsc()
        LAMBDA_MAT = sparse.dia_matrix((LAMBDA.toarray(), 0), shape=(NI, NI)).tocsc()

        # Compute the maximum error and the new gamma value
        error = max(max(abs(dX)), max(abs(dL)), max(abs(dT)), max(abs(dP)))
        newgamma = 0.1 * (T @ LAMBDA.transpose()).toarray()[0][0] / NI
        gamma = max(newgamma, 1e-5)  # Maximum tolerance requested.

        # Add an iteration step
        k += 1
        if k == max_iter:
            # If max_iter is reached, break. Should raise a Convergency Error, TODO.
            break
        print(X, error, gamma)

    END = timeit.default_timer()
    print('SOLUTION: ', X, NLP_test(X, LAMBDA, PI)[0])
    print('Time elapsed (s): ', END - START)

    return


def step_calculation(V, dV, NI):
    alpha = 1

    for i in range(NI):

        if dV[0][i] >= 0:
            pass
        else:
            alpha = min(alpha, -V[0][i] / dV[0][i])

    alpha = min(0.999995 * alpha, 1)

    return alpha


def test_solver():
    X = np.array([2., 1., 0.])
    solver(X0=X, NV=3, NE=1, NI=2, f_eval=NLP_test, step_calculator=step_calculation)

    return


if __name__ == '__main__':
    test_solver()
