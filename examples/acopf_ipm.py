import math
import pandas as pd
from scipy import sparse
import numpy as np
import timeit
from jax import grad, hessian
import jax.numpy as jnp
import random


##Equality functions:

def Pij(x, Gij, Bij):
    # x = [Pij, vi, vj, phiij]
    return -Gij * (x[1] ** 2 - x[1] * x[2] * jnp.cos(x[3])) + Bij * x[1] * x[2] * jnp.sin(x[3]) - x[0]


def Qij(x, Gij, Bij):
    # x = [Pij, vi, vj, phiij]
    return -Bij * (x[1] * x[2] * jnp.cos(x[3]) - x[1] ** 2) + Gij * x[1] * x[2] * jnp.sin(x[3]) - x[0]


def Pi(x, Pdi):
    # x = [Pi, Pij, Pik, ...]
    return sum(x[1:]) + Pdi - x[0]


def Qi(x, Qdi):
    # x = [Qi, Qij, Qik, ...]
    return sum(x[1:]) + Qdi - x[0]


def PLoss(x, Rij):
    # x = [lij, Pij, Pji]
    return x[1] + x[2] - Rij * x[0]


def QLoss(x, Xij):
    # x = [lij, Qij, Qji]
    return x[1] + x[2] - Xij * x[0]


# Objective function

def fobj(x, c2, c1):
    # x = [P1, P2, ...]
    return sum(c2[i] * x[i] ** 2 + c1[i] * x[i] for i in range(len(x)))


# Inequality functions:

def Smax(x, su):
    # x = [Pij, Qij]
    return su - x[0] ** 2 - x[1] ** 2


def EqIndex(N, L, V_U, V_L, P_U, P_L, Q_U, Q_L):
    '''
    In this function, we check which of the bounds for the nodal constraints will be treated as equalities.

    '''
    NE = 2 * N + 5 * L - 1  # Qi for the slack is not included in the optimization problem.
    NI = 6 * N + 2 * L - 2  # No bounds for the slack Q
    islack = 0
    for n in range(N):

        if V_U[n] == V_L[n]:
            NI -= 2
            NE += 1
        if P_U[n] == P_L[n]:
            NI -= 2
            NE += 1
        if n > islack:
            bounce_n = 1
        if n != islack:
            if Q_U[n - bounce_n] == Q_L[n - bounce_n]:
                NI -= 2
                NE += 1

    return NE, NI


def KKT(xk, mu):
    '''
    #### PROBLEM PARAMETERS ####
    N = 2
    L = 1

    c2 = [0.65, 0.]
    c1 = [3., 0.]

    LINE = [(0,1)]
    Pd = [2.0, 0.0]
    Qd = [1.0, 0.0]

    islack = 0

    z = 0.01 + 0.05j
    y = 1 / z

    Z = np.array([[0, z], [z, 0]])
    Y = np.array([[0, y], [y, 0]])
    G = np.real(Y)
    B = np.imag(Y)
    R = np.real(Z)
    X = np.imag(Z)

    V_L = [0.95, 0.95]
    V_U = [1.05, 1.05]
    P_L = [0, 0]
    Q_L = [-10, 0]
    P_U = [10, 0]
    Q_U = [10, 0]
    DELTA_MAX = [math.pi/3]
    S_MAX = [10] #Max LINE power
    '''
    #### PROBLEM PARAMETERS ####

    N = 3
    L = 3

    # Generation costs (second and first order).
    c2 = [0.4, 0.4, 0.0]
    c1 = [0.2, 0.2, 0.0]

    # Lines in the grid, in 'from' form.
    LINE = [(0, 1), (1, 2), (0, 2)]

    # Demand vectors.
    Pd = [0.0, 0.0, 0.5]
    Qd = [0.0, 0.0, 0.2]

    # Slack bus ident.
    islack = 0

    # Line impedance and admitances.
    z = 0.01 + 0.05j
    y = 1 / z
    Z = np.array([[0, z, z], [z, 0, z], [z, z,
                                         0]])  # Probably better just having a list of z and y for each line, but may be needed when adding transformers/shunt elements.
    Y = np.array([[7.692308 - 38.461538j, -3.846154 + 19.230769j, -3.846154 + 19.230769j],
                  [-3.846154 + 19.230769j, 7.692308 - 38.461538j, -3.846154 + 19.230769j],
                  [-3.846154 + 19.230769j, -3.846154 + 19.230769j, 7.692308 - 38.461538j],
                  ])
    G = np.real(Y)
    B = np.imag(Y)
    R = np.real(Z)
    X = np.imag(Z)

    # Nodal limits
    V_L = [1.00, 0.95, 0.95]
    V_U = [1.00, 1.05, 1.05]
    P_L = [0, 0, 0]
    Q_L = [0, 0]
    P_U = [100, 100, 0]
    Q_U = [0, 0]

    # Line limits.
    DELTA_MAX = [math.pi / 4, math.pi / 4, math.pi / 4]
    S_MAX = [0.05, 0.4, 0.4]  # Max LINE power

    # Reference index for each variable are retained here, and are used to work in subspaces and then expanding to the complete space.
    id_v, id_th, id_P, id_Q, id_phi, id_Pij, id_Qij, id_Pji, id_Qji, id_lij = 0, N, 2 * N - 1, 3 * N - 1, 4 * N - 2, 4 * N - 2 + L, 4 * N - 2 + 2 * L, 4 * N - 2 + 3 * L, 4 * N - 2 + 4 * L, 4 * N - 2 + 5 * L

    ###########################

    #### ITERATION VECTORS ####

    NV = 4 * N + 5 * L - 2
    NE, NI = EqIndex(N, L, V_U, V_L, P_U, P_L, Q_U, Q_L)

    # Slicing the results vector into its subvectors (problem variables, multipliers and slack variables)
    YK = xk[0: NV]
    PI = xk[NV: NE + NV]
    PIK = sparse.csc_matrix((PI, list(range(NE)), [0, NE]))
    LAMBDA = xk[NE + NV: NV + NE + NI]
    LAMBDAK = sparse.csc_matrix((LAMBDA, list(range(NI)), [0, NI]))
    T = xk[NE + NV + NI: NV + NE + 2 * NI]
    TK = sparse.csc_matrix((T, list(range(NI)), [0, NI]))

    LAMBDA_MAT = sparse.dia_matrix((LAMBDA, [0]), shape=(NI, NI))
    T_MAT = sparse.dia_matrix((T, [0]), shape=(NI, NI))

    E = sparse.csc_matrix(([1] * NI, list(range(NI)), [0, NI]))

    #################################

    #### KKT CONDITIONS BUILDING ####

    # Computing the gradient and hessian of the objective function.
    grad_f = sparse.csc_matrix((grad(fobj)(YK[id_P:id_Q], c2, c1), ([i for i in range(id_P, id_Q)], [0] * N)),
                               shape=(NV, 1))

    hessf = hessian(fobj)(YK[id_P:id_Q], c2, c1)

    rowf = []
    colf = []

    # This is used for indexing in the complete vector space from the Active power subspace
    for i in range(N):
        rowf.extend([i + id_P] * N)
        colf.extend([i for i in range(id_P, id_Q)])

    hess_f = sparse.csc_matrix((np.concatenate(hessf), (rowf, colf)), shape=(NV, NV))

    # We will store the value of the constraints and each gradient and hessian for the given solution of each iteration.
    grad_ce = []
    grad_ci = []
    hess_ce = []
    hess_ci = []
    ce = []
    ci = []

    # Iteration over each node to build the nodal constraints.
    # Right now, the gradient and hessian functions are computed at each iteration. It will perform better if there is a single computation and
    # Then we can just evaluate it at each iteration. TO-DO
    for n in range(N):
        bounce_n = 0

        if n > islack:
            bounce_n = 1
        if n != islack:
            Pij_index = [n + id_P]
            Qij_index = [n - bounce_n + id_Q]

            # We have to differentiate from and to lines connected to the bus. We only have the from lines, and invert the indices if its on the second position for the n node.
            for k, l in enumerate(LINE):
                if l[0] == n:
                    Pij_index.append(k + id_Pij)
                    Qij_index.append(k + id_Qij)

                if l[1] == n:
                    Pij_index.append(k + id_Pji)
                    Qij_index.append(k + id_Qji)

            gradPi = grad(Pi)(np.array([YK[m] for m in Pij_index]), Pd[n])
            gradQi = grad(Qi)(np.array([YK[m] for m in Qij_index]), Qd[n])

            hessPi = hessian(Pi)(np.array([YK[m] for m in Pij_index]), Pd[n])
            hessQi = hessian(Qi)(np.array([YK[m] for m in Qij_index]), Qd[n])

            # Same as before, rows and columns for sparse indexing.
            rowP = []
            colP = []
            rowQ = []
            colQ = []

            for index in Pij_index:
                rowP += ([index] * len(Pij_index))
                colP += Pij_index

            for index in Qij_index:
                rowQ += ([index] * len(Qij_index))
                colQ += Qij_index

            ce.extend([Pi([YK[m] for m in Pij_index], Pd[n])])
            ce.extend([Qi([YK[m] for m in Qij_index], Qd[n])])

            grad_ce.extend([sparse.csc_matrix((gradPi, (Pij_index, [0] * len(Pij_index))), shape=(NV, 1))])
            grad_ce.extend([sparse.csc_matrix((gradQi, (Qij_index, [0] * len(Qij_index))), shape=(NV, 1))])

            hess_ce.extend([sparse.csc_matrix((np.concatenate(hessPi), (rowP, colP)), shape=(NV, NV))])
            hess_ce.extend([sparse.csc_matrix((np.concatenate(hessQi), (rowQ, colQ)), shape=(NV, NV))])

        if n == islack:
            Pij_index = [n + id_P]

            for k, l in enumerate(LINE):
                if l[0] == n:
                    Pij_index.append(k + id_Pij)

                if l[1] == n:
                    Pij_index.append(k + id_Pji)

            gradPi = grad(Pi)(np.array([YK[m] for m in Pij_index]), Pd[n])

            hessPi = hessian(Pi)(np.array([YK[m] for m in Pij_index]), Pd[n])

            # Same as before, rows and columns for sparse indexing.
            rowP = []
            colP = []

            for index in Pij_index:
                rowP += ([index] * len(Pij_index))
                colP += Pij_index

            ce.extend([Pi([YK[m] for m in Pij_index], Pd[n])])
            grad_ce.extend([sparse.csc_matrix((gradPi, (Pij_index, [0] * len(Pij_index))), shape=(NV, 1))])
            hess_ce.extend([sparse.csc_matrix((np.concatenate(hessPi), (rowP, colP)), shape=(NV, NV))])

            # Here we check in which nodes we impose the value of power or voltage module. If the upper and lower bounds are equal, we treat it as an equality.

        if V_U[n] == V_L[n]:
            ce.extend([YK[n] - V_U[n]])
            grad_ce.extend([sparse.csc_matrix(([1], ([n], [0])), shape=(NV, 1))])
            hess_ce.extend([0])

        if V_U[n] != V_L[n]:
            ci.extend([- YK[n] + V_U[n]])
            ci.extend([YK[n] - V_L[n]])
            grad_ci.extend([sparse.csc_matrix(([-1], ([n], [0])), shape=(NV, 1))])
            grad_ci.extend([sparse.csc_matrix(([1], ([n], [0])), shape=(NV, 1))])
            hess_ci.extend([0])
            hess_ci.extend([0])

        if P_U[n] == P_L[n]:
            ce.extend([YK[n + id_P] - P_U[n]])
            grad_ce.extend([sparse.csc_matrix(([1], ([n + id_P], [0])), shape=(NV, 1))])
            hess_ce.extend([0])

        if P_U[n] != P_L[n]:
            ci.extend([- YK[n + id_P] + P_U[n]])
            ci.extend([YK[n + id_P] - P_L[n]])
            grad_ci.extend([sparse.csc_matrix(([-1], ([n + id_P], [0])), shape=(NV, 1))])
            grad_ci.extend([sparse.csc_matrix(([1], ([n + id_P], [0])), shape=(NV, 1))])
            hess_ci.extend([0])
            hess_ci.extend([0])
        if n != islack:

            if n > islack:
                bounce_n = 1

            if Q_U[n - bounce_n] == Q_L[n - bounce_n]:
                ce.extend([YK[n - bounce_n + id_Q] - Q_U[n - bounce_n]])
                grad_ce.extend([sparse.csc_matrix(([1], ([n - bounce_n + id_Q], [0])), shape=(NV, 1))])
                hess_ce.extend([0])

            if Q_U[n - bounce_n] != Q_L[n - bounce_n]:
                ci.extend([- YK[n - bounce_n + id_Q] + Q_U[n - bounce_n]])
                ci.extend([YK[n - bounce_n + id_Q] - Q_L[n - bounce_n]])
                grad_ci.extend([sparse.csc_matrix(([-1], ([n - bounce_n + id_Q], [0])), shape=(NV, 1))])
                grad_ci.extend([sparse.csc_matrix(([1], ([n - bounce_n + id_Q], [0])), shape=(NV, 1))])
                hess_ci.extend([0])
                hess_ci.extend([0])

        # Now, we iterate for each line to build the line associated constraints
    for l in range(L):
        # We first get the nodes connected
        i, j = LINE[l]

        # We have to check wether the slack bus is one of the connected nodes, and if its index is lower than any of the nodes in the line, there has to be a bounce in the indexation.
        # This is due to the slack angle being left out of the matrix, as it was a source of singularity.
        bounce_i = 0
        bounce_j = 0
        if i > islack:
            bounce_i = -1
        if j > islack:
            bounce_j = -1

        # Again, we avoid the slack bus
        if i == islack:
            ce.extend([-YK[l + id_phi] - YK[j + id_th + bounce_j]])
            grad_ce.extend([sparse.csc_matrix(([-1, -1], ([l + id_phi, j + id_th + bounce_j], [0, 0])), shape=(NV, 1))])
            hess_ce.extend([0])
        if j == islack:
            ce.extend([-YK[l + id_phi] + YK[i + id_th + bounce_i]])
            grad_ce.extend([sparse.csc_matrix(([-1, 1], ([l + id_phi, i + id_th + bounce_i], [0, 0])), shape=(NV, 1))])
            hess_ce.extend([0])

        if i != islack and j != islack:
            ce.extend([- YK[l + id_phi] + YK[i + id_th + bounce_i] - YK[j + id_th + bounce_j]])
            grad_ce.extend([sparse.csc_matrix(
                ([-1, 1, -1], ([l + id_phi, i + id_th + bounce_i, j + id_th + bounce_j], [0, 0, 0])), shape=(NV, 1))])
            hess_ce.extend([0])

        # Here, we build the line constraints (Power flowing through the branch in from and to mode, and losses)
        gradPij = grad(Pij)(np.array([YK[l + id_Pij], YK[i], YK[j], YK[l + id_phi]]), G[i][j], B[i][j])
        gradQij = grad(Qij)(np.array([YK[l + id_Qij], YK[i], YK[j], YK[l + id_phi]]), G[i][j], B[i][j])
        gradPji = grad(Pij)(np.array([YK[l + id_Pji], YK[j], YK[i], -YK[l + id_phi]]), G[j][i], B[j][i])
        gradQji = grad(Qij)(np.array([YK[l + id_Qji], YK[j], YK[i], -YK[l + id_phi]]), G[j][i], B[j][i])
        # gradRij = grad(PLoss)(np.array([YK[l + id_lij], YK[l + id_Pij], YK[l + id_Pji]]), R[i][j])
        # gradXij = grad(QLoss)(np.array([YK[l + id_lij], YK[l + id_Qij], YK[l + id_Qji]]), X[i][j])

        hessPij = hessian(Pij)(np.array([YK[l + id_Pij], YK[i], YK[j], YK[l + id_phi]]), G[i][j], B[i][j])
        hessQij = hessian(Qij)(np.array([YK[l + id_Qij], YK[i], YK[j], YK[l + id_phi]]), G[i][j], B[i][j])
        hessPji = hessian(Pij)(np.array([YK[l + id_Pji], YK[j], YK[i], -YK[l + id_phi]]), G[j][i], B[j][i])
        hessQji = hessian(Qij)(np.array([YK[l + id_Qji], YK[j], YK[i], -YK[l + id_phi]]), G[j][i], B[j][i])
        # hessRij = hessian(PLoss)(np.array([YK[l + id_lij], YK[l + id_Pij], YK[l + id_Pji]]), R[i][j])
        # hessXij = hessian(QLoss)(np.array([YK[l + id_lij], YK[l + id_Qij], YK[l + id_Qji]]), X[i][j])

        # Again, sparse indexing.
        rowPij = [l + id_Pij] * 4 + [i] * 4 + [j] * 4 + [l + id_phi] * 4
        colPij = [l + id_Pij, i, j, l + id_phi] * 4
        rowQij = [l + id_Qij] * 4 + [i] * 4 + [j] * 4 + [l + id_phi] * 4
        colQij = [l + id_Qij, i, j, l + id_phi] * 4
        rowPji = [l + id_Pji] * 4 + [j] * 4 + [i] * 4 + [l + id_phi] * 4
        colPji = [l + id_Pji, j, i, l + id_phi] * 4
        rowQji = [l + id_Qji] * 4 + [j] * 4 + [i] * 4 + [l + id_phi] * 4
        colQji = [l + id_Qji, j, i, l + id_phi] * 4
        # rowRij = [l + id_lij]*3 + [l + id_Pij]*3 + [l + id_Pji]*3
        # colRij = [l + id_lij, l + id_Pij, l + id_Pji]*3
        # rowXij = [l + id_lij]*3 + [l + id_Qij]*3 + [l + id_Qji]*3
        # colXij = [l + id_lij, l + id_Qij, l + id_Qji]*3

        ce.extend([Pij([YK[l + id_Pij], YK[i], YK[j], YK[l + id_phi]], G[i][j], B[i][j])])
        ce.extend([Qij([YK[l + id_Qij], YK[i], YK[j], YK[l + id_phi]], G[i][j], B[i][j])])
        ce.extend([Pij([YK[l + id_Pji], YK[j], YK[i], -YK[l + id_phi]], G[j][i], B[j][i])])
        ce.extend([Qij([YK[l + id_Qji], YK[j], YK[i], -YK[l + id_phi]], G[j][i], B[j][i])])
        # ce.extend([PLoss([YK[l + id_lij], YK[l + id_Pij], YK[l + id_Pji]], R[i][j])])
        # ce.extend([QLoss([YK[l + id_lij], YK[l + id_Qij], YK[l + id_Qji]], X[i][j])])

        ci.extend([YK[l + id_phi] + DELTA_MAX[l]])
        ci.extend([- YK[l + id_phi] + DELTA_MAX[l]])

        # ci.extend([Smax([YK[l + id_Pij], YK[l + id_Qij]], S_MAX[l])])

        grad_ce.extend([sparse.csc_matrix((gradPij, ([l + id_Pij, i, j, l + id_phi], [0, 0, 0, 0])), shape=(NV, 1))])
        grad_ce.extend([sparse.csc_matrix((gradQij, ([l + id_Qij, i, j, l + id_phi], [0, 0, 0, 0])), shape=(NV, 1))])
        grad_ce.extend([sparse.csc_matrix((gradPji, ([l + id_Pji, j, i, l + id_phi], [0, 0, 0, 0])), shape=(NV, 1))])
        grad_ce.extend([sparse.csc_matrix((gradQji, ([l + id_Qji, j, i, l + id_phi], [0, 0, 0, 0])), shape=(NV, 1))])
        # grad_ce.extend([sparse.csc_matrix((gradRij, ([l + id_lij, l + id_Pij, l + id_Pji], [0, 0, 0])), shape = (NV, 1))])
        # grad_ce.extend([sparse.csc_matrix((gradXij, ([l + id_lij, l + id_Qij, l + id_Qji], [0, 0, 0])), shape = (NV, 1))])

        grad_ci.extend([sparse.csc_matrix(([1], ([l + id_phi], [0])), shape=(NV, 1))])
        grad_ci.extend([sparse.csc_matrix(([-1], ([l + id_phi], [0])), shape=(NV, 1))])

        gradSij = grad(Smax)(np.array([YK[l + id_Pij], YK[l + id_Qij]]), S_MAX[l])

        hess_ce.extend([sparse.csc_matrix((np.concatenate(hessPij), (rowPij, colPij)), shape=(NV, NV))])
        hess_ce.extend([sparse.csc_matrix((np.concatenate(hessQij), (rowQij, colQij)), shape=(NV, NV))])
        hess_ce.extend([sparse.csc_matrix((np.concatenate(hessPji), (rowPji, colPji)), shape=(NV, NV))])
        hess_ce.extend([sparse.csc_matrix((np.concatenate(hessQji), (rowQji, colQji)), shape=(NV, NV))])
        # hess_ce.extend([sparse.csc_matrix((np.concatenate(hessRij), (rowRij, colRij)), shape = (NV, NV))])
        # hess_ce.extend([sparse.csc_matrix((np.concatenate(hessXij), (rowXij, colXij)), shape = (NV, NV))])

        # hess_ci.extend([0, 0])

        # hessSij = hessian(Smax)(np.array([YK[l + id_Pij], YK[l + id_Qij]]), S_MAX[l])

        # rowSij = [l + id_Pij, l + id_Pij, l + id_Qij, l + id_Qij]
        # colSij = [l + id_Pij, l + id_Qij, l + id_Pij, l + id_Qij]

        # grad_ci.extend([sparse.csc_matrix((gradSij, ([l + id_Pij, l + id_Qij], [0, 0])), shape = (NV, 1))])

        # hess_ci.extend([sparse.csc_matrix((np.concatenate(hessSij), (rowSij, colSij)), shape = (NV, NV))])

    # We stack the gradients to be able to operate in matricial form with the multipliers.
    gC = sparse.hstack(grad_ce)
    gH = sparse.hstack(grad_ci)

    # KKT conditions calculation.

    KKT_A = grad_f - gC @ PIK - gH @ LAMBDAK
    KKT_B = sparse.vstack(ce)  # Evaluate the equalities functions at the given iteration
    KKT_C = sparse.vstack(ci) - TK  # Same for inequalities
    KKT_D = LAMBDA_MAT @ T_MAT @ E - mu * E

    # Submatrix for the jacobian of the KKT conditions that include hessian terms.
    H_A = hess_f

    # Some constraints have no hessian, and its list element is a 0. If True, pass.
    for i in range(len(hess_ce)):
        if sparse.issparse(hess_ce[i]):
            H_A -= hess_ce[i] * PI[i]

    for j in range(len(hess_ci)):
        if sparse.issparse(hess_ci[j]):
            H_A -= hess_ci[j] * LAMBDA[j]

    # Stacking of the submatrices for the jacobian as in reference books.
    M1 = sparse.hstack([H_A, -gC, -gH, sparse.csc_matrix((NV, NI))])
    M2 = sparse.hstack(
        [gC.transpose(), sparse.csc_matrix((NE, NE)), sparse.csc_matrix((NE, NI)), sparse.csc_matrix((NE, NI))])
    M3 = sparse.hstack([gH.transpose(), sparse.csc_matrix((NI, NE)), sparse.csc_matrix((NI, NI)), -sparse.eye(NI)])
    M4 = sparse.hstack([sparse.csc_matrix((NI, NV)), sparse.csc_matrix((NI, NE)), T_MAT, LAMBDA_MAT])
    M = sparse.vstack([M1, M2, M3, M4]).tocsc()

    # m=pd.DataFrame(M.toarray())
    # m.to_csv('Mat_M.csv')

    # M @ dx = r. Stacking the KKT conditions.
    r = sparse.vstack([KKT_A, KKT_B, KKT_C, KKT_D])

    return M, r


def ipm():
    # Test optimization problem.

    START = timeit.default_timer()
    """
    ###2 BUS CASE###
    N = 2
    L = 1

    #### PROBLEM PARAMETERS ####

    c2 = [0.65, 0.]
    c1 = [3., 0.]

    LINE = [(0,1)]
    Pd = [2.0, 0.0]
    Qd = [1.0, 0.0]

    islack = 0

    z = 0.01 + 0.05j
    y = 1 / z

    Z = np.array([[0, z], [z, 0]])
    Y = np.array([[0, y], [y, 0]])
    G = np.real(Y)
    B = np.imag(Y)
    R = np.real(Z)
    X = np.imag(Z) 

    V_L = [0.95, 0.95]
    V_U = [1.05, 1.05]
    P_L = [0, 0]
    Q_L = [-10, 0]
    P_U = [10, 0]
    Q_U = [10, 0]
    DELTA_MAX = [math.pi/3]
    S_MAX = [10] #Max LINE power
    """
    ### 3 BUS CASE ###

    N = 3
    L = 3

    #### PROBLEM PARAMETERS ####

    # Initialized both here and in the KKT building script. Should probably be global variables to avoid defining them multiple times.

    # Generation costs (second and first order).
    c2 = [0.4, 0.4, 0.0]
    c1 = [0.2, 0.2, 0.0]

    # Lines in the grid, in 'from' form.
    LINE = [(0, 1), (1, 2), (0, 2)]

    # Demand vectors.
    Pd = [0.0, 0.0, 0.5]
    Qd = [0.0, 0.0, 0.2]

    # Slack bus ident.
    islack = 0

    # Line impedance and admitances.
    z = 0.01 + 0.05j
    y = 1 / z
    Z = np.array([[0, z, z], [z, 0, z], [z, z,
                                         0]])  # Probably better just having a list of z and y for each line, but may be needed when adding transformers/shunt elements.
    Y = np.array([[0, y, y], [y, 0, y], [y, y, 0]])
    G = np.real(Y)
    B = np.imag(Y)
    R = np.real(Z)
    X = np.imag(Z)

    # Nodal limits
    V_L = [1.00, 0.95, 0.95]
    V_U = [1.00, 1.05, 1.05]
    P_L = [0, 0, 0]
    Q_L = [0, 0]
    P_U = [100, 100, 0]
    Q_U = [0, 0]

    # Line limits.
    DELTA_MAX = [math.pi / 4, math.pi / 4, math.pi / 4]
    S_MAX = [0.05, 0.4, 0.4]  # Max LINE power

    # Number of variables, equalities and inequalities. Used to structure the problem
    NV = 4 * N + 5 * L - 2  # Neither the theta nor the Qi of the slack bus will be included in the optimization problem.
    NE, NI = EqIndex(N, L, V_U, V_L, P_U, P_L, Q_U, Q_L)

    # Lagrange multipliers init. Initial state init. Auxiliar E vector (column of ones)
    PI = [0.5] * NE
    LAMBDA = [0.5] * NI
    T = [0.5] * NI
    E = sparse.csc_matrix(([1] * NI, list(range(NI)), [0, NI]))
    YK = state_vector()

    # Iteration parameters.
    TAU = 0.99995  # Factor of approach to 0 for the multipliers.
    mu = 10  # Homotopy parameter for LAMBDA * T = 0
    sigma = 0.35  # Descent factor for mu
    error = 10000  # Dummy value to start the while loop.
    k = 0  # Number of Iteration

    # IPM Vector. xk is the value for iteration k and dx the displacement.
    xk = np.array(YK + PI + LAMBDA + T)
    dx = np.zeros(NE + NV + 2 * NI)
    alpha_t = 0
    alpha_lambda = 0

    l_alpha_t = []
    l_alpha_lambda = []

    # Iteration until the mu value has reached a minimum epsilon.
    while mu > 0.0000005:
        # Iteration for each mu value.
        while error > mu:
            # Variables and Lagrange multipliers recalculation. Step 0: dx = 0.
            xk[0: NV] += alpha_lambda * dx[0: NV]
            xk[NV: NE + NV] += alpha_t * dx[NV: NE + NV]
            xk[NE + NV: NE + NV + NI] += alpha_lambda * dx[NE + NV: NE + NV + NI]
            xk[NE + NV + NI: NE + NV + 2 * NI] += alpha_t * dx[NE + NV + NI: NE + NV + 2 * NI]

            # KKT equations and its Jacobian Matrix calculation.
            M, r = KKT(xk, mu)

            # Displacement calculation for iteration k
            dx = sparse.linalg.spsolve(M, r)

            # Maximum displacement calculation. If below mu, convergence for that particular mu is accomplished, and will update the mu value.
            error = max(abs(dx))
            k += 1
            print(k, error)

            # Step sizing is determined by the alpha that ensures all the multipliers stay avobe 0.
            alpha_lambda = min(TAU * xk[NE + NV: NV + NE + NI] / abs(dx[NE + NV: NV + NE + NI]))
            alpha_t = min(TAU * xk[NE + NV + NI: NV + NE + 2 * NI] / abs(dx[NE + NV + NI: NV + NE + 2 * NI]))

            # After a number of iterations, jump to the following mu to search for better convergence.
            if k == 15:
                break

        print(xk[0:NV], k, error)
        k = 0  # Reset k value
        mu *= sigma  # Update sigma
        # mu = 0
        error = 10000  # Reset dummy value for the first iteration
    print('---------------------------------------------------------------')

    # print(k, error)
    print(xk[0:NV])

    END = timeit.default_timer()
    print("IPM Runtime(s): ", END - START)

    return l_alpha_lambda


def state_vector():
    '''
    Construct the state vector, which will include all the variables of the OPF.




    N = 3
    L = 3
    NV = 5*N + 11*L

    Y0 = [0]*NV
    ID_V, ID_TH, ID_PG, ID_QG, ID_W0, ID_WR, ID_WI, ID_PHI, ID_VV, ID_COSPHI, ID_SINPHI, ID_L, ID_PFROM, ID_QFROM, ID_PTO, ID_QTO = indexing(N, L)

    for n in range(N):

        Y0[n] = 1 #Inital voltage at 1 p.u.
        Y0[n + ID_TH] = 0 #Initial angle at 0 rads
        Y0[n + ID_PG] = 0
        Y0[n + ID_QG] = 0
        Y0[n + ID_W0] = 1

    for l in range(L):
        Y0[l + ID_WR] = 1
        Y0[l + ID_WI] = 0
        Y0[l + ID_PHI] = 0
        Y0[l + ID_VV] = 1
        Y0[l + ID_COSPHI] = 1
        Y0[l + ID_SINPHI] = 0
        Y0[l + ID_L] = 0
        Y0[l + ID_PFROM] = 0
        Y0[l + ID_QFROM] = 0
        Y0[l + ID_PTO] = 0
        Y0[l + ID_QTO] = 0
    '''

    N = 3
    L = 3
    NV = 4 * N + 5 * L - 2

    Y0 = [0] * NV
    ID_V, ID_TH, ID_PG, ID_QG, ID_PHI, ID_PFROM, ID_QFROM, ID_PTO, ID_QTO, ID_L = 0, N, 2 * N - 1, 3 * N - 1, 4 * N - 2, 4 * N - 2 + L, 4 * N - 2 + 2 * L, 4 * N - 2 + 3 * L, 4 * N - 2 + 4 * L, 4 * N - 2 + 5 * L
    islack = 0

    for n in range(N):

        Y0[n] = 1  # Inital voltage at 1 p.u.
        if n > islack:
            Y0[n + ID_TH - 1] = 0.5  # Initial angle at 0 rads
            Y0[n + ID_QG - 1] = 0.0
        if n < islack:
            Y0[n + ID_TH] = -0.02
            Y0[n + ID_QG] = 0.0

        Y0[n + ID_PG] = 0.0

    for l in range(L):
        Y0[l + ID_PHI] = 0.00
        # Y0[l + ID_L] = 0
        Y0[l + ID_PFROM] = 0.0
        Y0[l + ID_QFROM] = 0.0
        Y0[l + ID_PTO] = 0.0
        Y0[l + ID_QTO] = 0.0

    return Y0


if __name__ == '__main__':
    ipm()