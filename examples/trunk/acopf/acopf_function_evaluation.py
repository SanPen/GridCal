import math
import numpy as np
from scipy import sparse
from scipy.sparse import csc_matrix as csc
from acopf_functions import *
import GridCalEngine.api as gce
from GridCalEngine.basic_structures import Vec, CxVec


def power_flow_evaluation(nc:gce.NumericalCircuit,xk:Vec, N:int, L:int, NV:int, NE:int, NI:int):

    # For each iteration, we first calculate in matrix form the power flow using only voltage and angles. Later on,
    # we compute the values of the different gradient and hessians that appear for each constraint.

    # This should be done outside this functions, since this will loop for some iterations and it will slow the process.
    # In here just to keep track of all the variables, later on will be moved outside

    ybus = nc.Ybus
    yfrom = nc.Yf
    yto = nc.Yt
    cf = nc.Cf
    ct = nc.Ct

    ########

    # Reading the voltage magnitude and angle and expressing in polar form
    vm = xk[0:N]
    va = xk[N:2*N]
    v = csc(vm * np.exp(1j * va)).transpose()

    # Bus injections calculation
    sbus = v.dot(sparse.linalg.cg(ybus @ v))
    pbus = np.real(sbus)
    qbus = np.imag(sbus)

    #Compute nodal balance residual

    resPi = xk[id_P: id_Q] - pd - pbus
    resQi = xk[id_Q: id_phi] - qd - qbus

    # Branch power calculation
    vf = cf @ v
    vt = ct @ v

    s_from = vf.dot(sparse.linalg.cg(yf @ v))
    s_to = vt.dot(sparse.linalg.cg(yt @ v))

    p_from = np.real(s_from)
    q_from = np.imag(s_from)
    p_to = np.real(s_to)
    q_to = np.imag(s_to)

    # Compute branch power residuals

    resPfrom = xk[id_Pfrom: id_Qfrom] - p_from
    resQfrom = xk[id_Qfrom: id_Pto] - q_from
    resPto = xk[id_Pto: id_Qto] - p_to
    resQto = xk[id_Qto: id_lij] - q_to


 #Objective function

    f = xk[id_P : id_Q].power(2).multiply(c2).sum() + xk[id_P : id_Q].multiply(c1).sum()
    fx = 2 * xk[id_P : id_Q].multiply(c2)
    fxx = sparse.dia_matrix((2 * c2.toarray(), 0), shape = (NV, NV))

    # This is the structure they should have. Init as lists since modifying a csc matrix is expensive.

    # G = csc((NE, 1))
    # Gx = csc((NV, NE))
    # Gxx = csc((NV, NV))
    # H = csc((NI, 1))
    # Hx = csc((NV, NI))
    # Hxx = csc((NV, NV))

    G = []
    Gx = []
    Gxx = []
    H = []
    Hx = []
    Hxx = []






    for n in range(N):



        # TODO




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

        ce.extend([Pij([YK[l + id_Pij], YK[i], YK[j], YK[l + id_phi]], -G[i][j], -B[i][j])])
        ce.extend([Qij([YK[l + id_Qij], YK[i], YK[j], YK[l + id_phi]], -G[i][j], -B[i][j])])
        ce.extend([Pij([YK[l + id_Pji], YK[j], YK[i], -YK[l + id_phi]], -G[j][i], -B[j][i])])
        ce.extend([Qij([YK[l + id_Qji], YK[j], YK[i], -YK[l + id_phi]], -G[j][i], -B[j][i])])
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
