import GridCal.Engine as gc
import numpy as np
import scipy.sparse as sp
import numba as nb
from math import sin, cos


def dSbus_dV(Ybus, V):
    """
    Derivatives of the power injections w.r.t the voltage
    :param Ybus: Admittance matrix
    :param V: complex voltage arrays
    :return: dSbus_dVa, dSbus_dVm
    """
    diagV = sp.diags(V)
    diagE = sp.diags(V / np.abs(V))
    Ibus = Ybus * V
    diagIbus = sp.diags(Ibus)

    dSbus_dVa = 1j * diagV * np.conj(diagIbus - Ybus * diagV)  # dSbus / dVa
    dSbus_dVm = diagV * np.conj(Ybus * diagE) + np.conj(diagIbus) * diagE  # dSbus / dVm

    return dSbus_dVa, dSbus_dVm


def jacobian1(G, B, P, Q, E, F, pq, pv):
    """
    Compute the Tinney version of the AC jacobian without any sin, cos or abs
    (Lynn book page 89)

    :param G: Conductance matrix in CSC format
    :param B: Susceptance matrix in CSC format
    :param P: Real computed power
    :param Q: Imaginary computed power
    :param E: Real voltage
    :param F: Imaginary voltage
    :param pq: array pf pq indices
    :param pv: array of pv indices
    :return: CSC Jacobian matrix
    """
    pvpq = np.r_[pv, pq]
    npvpq = len(pvpq)
    n_rows = len(pvpq) + len(pq)
    n_cols = len(pvpq) + len(pq)

    Vm = np.abs(E + 1j * F)
    # Vabs2 = n2p.power(np.abs(V), 2.0)

    nnz = 0
    p = 0
    Jx = np.empty(G.nnz * 4, dtype=float)  # data
    Ji = np.empty(G.nnz * 4, dtype=int)  # indices
    Jp = np.empty(n_cols + 1, dtype=int)  # pointers
    Jp[p] = 0

    # generate lookup for the non-immediate axis (for CSC it is the rows) -> index lookup
    lookup_pvpq = np.zeros(G.shape[0], dtype=int) - 1
    # lookup_pqpv = np.zeros(np.max(G.indices) + 1, dtype=int)
    lookup_pvpq[pvpq] = np.arange(len(pvpq), dtype=int)

    lookup_pq = np.zeros(G.shape[0], dtype=int) - 1
    lookup_pq[pq] = np.arange(len(pq), dtype=int)

    """
    Jacobian structure
    
              pvpq  pq
        pvpq | J1 | J2 | 
          pq | J3 | J4 |     
    """

    # J1 and J3
    for j in pvpq:  # sliced columns
        
        # fill in J1
        for k in range(G.indptr[j], G.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = G.indices[k]
            ii = lookup_pvpq[i]

            if pvpq[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = F[i] * (G.data[k] * E[j] - B.data[k] * F[j]) - \
                              E[i] * (B.data[k] * E[j] + G.data[k] * F[j])
                else:
                    Jx[nnz] = -Q[i] - B.data[k] * (E[i] * E[i] + F[i] * F[i])

                Ji[nnz] = ii
                nnz += 1

        # fill in J3
        for k in range(G.indptr[j], G.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = G.indices[k]
            ii = lookup_pq[i]

            if pq[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = - E[i] * (G.data[k] * E[j] - B.data[k] * F[j]) \
                              - F[i] * (B.data[k] * E[j] + G.data[k] * F[j])
                else:
                    Jx[nnz] = P[i] - G.data[k] * (E[i] * E[i] + F[i] * F[i])

                Ji[nnz] = ii + npvpq
                nnz += 1

        p += 1
        Jp[p] = nnz

    # J2 and J4
    for j in pq:  # sliced columns

        # fill in J2
        for k in range(G.indptr[j], G.indptr[j + 1]):  # row entries of the column

            # row index translation to the "rows" space
            i = G.indices[k]  # global row index
            ii = lookup_pvpq[i]  # reduced row index

            if pvpq[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = (E[i] * (G.data[k] * E[j] - B.data[k] * F[j]) + F[i] * (B.data[k] * E[j] + G.data[k] * F[j])) / Vm[j]
                else:
                    Jx[nnz] = ((P[i] + G.data[k] * (E[i] * E[i] + F[i] * F[i]))) / Vm[i]

                Ji[nnz] = ii
                nnz += 1

        # fill in J4
        for k in range(G.indptr[j], G.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = G.indices[k]  # global row index
            ii = lookup_pq[i]  # reduced row index

            if pq[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = (F[i] * (G.data[k] * E[j] - B.data[k] * F[j]) - E[i] * (B.data[k] * E[j] + G.data[k] * F[j])) / Vm[j]
                else:
                    Jx[nnz] = (Q[i] - B.data[k] * (E[i] * E[i] + F[i] * F[i])) / Vm[i]

                Ji[nnz] = ii + npvpq
                nnz += 1

        p += 1
        Jp[p] = nnz

    # last pointer entry
    Jp[p] = nnz

    # reseize
    Jx = np.resize(Jx, nnz)
    Ji = np.resize(Ji, nnz)

    return sp.csc_matrix((Jx, Ji, Jp), shape=(n_rows, n_cols))


def jacobian1Polar(G, B, P, Q, E, F, pq, pv):
    """
    Compute the Tinney version of the AC jacobian without any sin, cos or abs
    (Lynn book page 89)

    :param G: Conductance matrix in CSC format
    :param B: Susceptance matrix in CSC format
    :param P: Real computed power
    :param Q: Imaginary computed power
    :param E: Real voltage
    :param F: Imaginary voltage
    :param pq: array pf pq indices
    :param pv: array of pv indices
    :return: CSC Jacobian matrix
    """
    pvpq = np.r_[pv, pq]
    npvpq = len(pvpq)
    n_rows = len(pvpq) + len(pq)
    n_cols = len(pvpq) + len(pq)

    V = E + 1j * F
    Vm = np.abs(V)
    Va = np.angle(V)
    Vabs2 = np.power(Vm, 2.0)

    nnz = 0
    p = 0
    Jx = np.empty(G.nnz * 4, dtype=float)  # data
    Ji = np.empty(G.nnz * 4, dtype=int)  # indices
    Jp = np.empty(n_cols + 1, dtype=int)  # pointers
    Jp[p] = 0

    # generate lookup for the non immediate axis (for CSC it is the rows) -> index lookup
    lookup_pvpq = np.zeros(G.shape[0], dtype=int) - 1
    # lookup_pqpv = np.zeros(np.max(G.indices) + 1, dtype=int)
    lookup_pvpq[pvpq] = np.arange(len(pvpq), dtype=int)

    lookup_pq = np.zeros(G.shape[0], dtype=int) - 1
    lookup_pq[pq] = np.arange(len(pq), dtype=int)

    """
    Jacobian structure

              pvpq  pq
        pvpq | J1 | J2 | 
          pq | J3 | J4 |     
    """

    # J1 and J3
    for j in pvpq:  # sliced columns

        # fill in J1
        for k in range(G.indptr[j], G.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = G.indices[k]
            ii = lookup_pvpq[i]

            if pvpq[ii] == i:  # rows
                # entry found
                if i != j:
                    da = Va[i] - Va[j]
                    Jx[nnz] = Vm[i] * Vm[j] * (G.data[k] * sin(da) - B.data[k] * cos(da))
                else:
                    Jx[nnz] = -Q[i] - B.data[k] * Vabs2[i]

                Ji[nnz] = ii
                nnz += 1

        # fill in J3
        for k in range(G.indptr[j], G.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = G.indices[k]
            ii = lookup_pq[i]

            if pq[ii] == i:  # rows
                # entry found
                if i != j:
                    da = Va[i] - Va[j]
                    Jx[nnz] = - Vm[i] * Vm[j] * (G.data[k] * cos(da) + B.data[k] * sin(da))
                else:
                    Jx[nnz] = P[i] - G.data[k] * Vabs2[i]

                Ji[nnz] = ii + npvpq
                nnz += 1

        p += 1
        Jp[p] = nnz

    # J2 and J4
    for j in pq:  # sliced columns

        # fill in J2
        for k in range(G.indptr[j], G.indptr[j + 1]):  # row entries of the column

            # row index translation to the "rows" space
            i = G.indices[k]  # global row index
            ii = lookup_pvpq[i]  # reduced row index

            if pvpq[ii] == i:  # rows
                # entry found
                if i != j:
                    da = Va[i] - Va[j]
                    Jx[nnz] = Vm[i] * Vm[j] * (G.data[k] * cos(da) + B.data[k] * sin(da))
                else:
                    Jx[nnz] = P[i] + G.data[k] * Vabs2[i]

                Ji[nnz] = ii
                nnz += 1

        # fill in J4
        for k in range(G.indptr[j], G.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = G.indices[k]
            ii = lookup_pq[i]

            if pq[ii] == i:  # rows
                # entry found
                if i != j:
                    da = Va[i] - Va[j]
                    Jx[nnz] = Vm[i] * Vm[j] * (G.data[k] * sin(da) - B.data[k] * cos(da))
                else:
                    Jx[nnz] = Q[i] - B.data[k] * Vabs2[i]

                Ji[nnz] = ii + npvpq
                nnz += 1

        p += 1
        Jp[p] = nnz

    # last pointer entry
    Jp[p] = nnz

    # reseize
    Jx = np.resize(Jx, nnz)
    Ji = np.resize(Ji, nnz)

    return sp.csc_matrix((Jx, Ji, Jp), shape=(n_rows, n_cols))


@nb.njit()
def jacobian_numba(nbus, Gi, Gp, Gx, Bx, P, Q, E, F, pq, pvpq):
    """
    Compute the Tinney version of the AC jacobian without any sin, cos or abs
    (Lynn book page 89)
    :param G: Conductance matrix in CSC format
    :param B: Susceptance matrix in CSC format
    :param P: Real computed power
    :param Q: Imaginary computed power
    :param E: Real voltage
    :param F: Imaginary voltage
    :param pq: array pf pq indices
    :param pv: array of pv indices
    :return: CSC Jacobian matrix
    """
    npqpv = len(pvpq)
    n_rows = len(pvpq) + len(pq)
    n_cols = len(pvpq) + len(pq)

    nnz = 0
    p = 0
    Jx = np.empty(len(Gx) * 4, dtype=nb.float64)  # data
    Ji = np.empty(len(Gx) * 4, dtype=nb.int32)  # indices
    Jp = np.empty(n_cols + 1, dtype=nb.int32)  # pointers
    Jp[p] = 0

    # generate lookup for the non immediate axis (for CSC it is the rows) -> index lookup
    lookup_pvpq = np.zeros(nbus, dtype=nb.int32)
    lookup_pvpq[pvpq] = np.arange(len(pvpq), dtype=nb.int32)

    lookup_pq = np.zeros(nbus, dtype=nb.int32)
    lookup_pq[pq] = np.arange(len(pq), dtype=nb.int32)

    for j in pvpq:  # sliced columns

        # fill in J1
        for k in range(Gp[j], Gp[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = Gi[k]
            ii = lookup_pvpq[i]

            if pvpq[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = F[i] * (Gx[k] * E[j] - Bx[k] * F[j]) - E[i] * (Bx[k] * E[j] + Gx[k] * F[j])
                else:
                    Jx[nnz] = - Q[i] - Bx[k] * (E[i] * E[i] + F[i] * F[i])

                Ji[nnz] = ii
                nnz += 1

        # fill in J3
        for k in range(Gp[j], Gp[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = Gi[k]
            ii = lookup_pq[i]

            if pq[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = - E[i] * (Gx[k] * E[j] - Bx[k] * F[j]) - F[i] * (Bx[k] * E[j] + Gx[k] * F[j])
                else:
                    Jx[nnz] = P[i] - Gx[k] * (E[i] * E[i] + F[i] * F[i])

                Ji[nnz] = ii + npqpv
                nnz += 1

        p += 1
        Jp[p] = nnz

    # J2 and J4
    for j in pq:  # sliced columns

        # fill in J2
        for k in range(Gp[j], Gp[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = Gi[k]
            ii = lookup_pvpq[i]

            if pvpq[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = E[i] * (Gx[k] * E[j] - Bx[k] * F[j]) + F[i] * (Bx[k] * E[j] + Gx[k] * F[j])
                else:
                    Jx[nnz] = P[i] + Gx[k] * (E[i] * E[i] + F[i] * F[i])

                Ji[nnz] = ii
                nnz += 1

        # fill in J4
        for k in range(Gp[j], Gp[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = Gi[k]
            ii = lookup_pq[i]

            if pq[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = F[i] * (Gx[k] * E[j] - Bx[k] * F[j]) - E[i] * (Bx[k] * E[j] + Gx[k] * F[j])
                else:
                    Jx[nnz] = Q[i] - Bx[k] * (E[i] * E[i] + F[i] * F[i])

                Ji[nnz] = ii + npqpv
                nnz += 1

        p += 1
        Jp[p] = nnz

    # last pointer entry
    Jp[p] = nnz

    # reseize
    # Jx = np.resize(Jx, nnz)
    # Ji = np.resize(Ji, nnz)

    return Jx, Ji, Jp, n_rows, n_cols, nnz


def jacobian2(Y, S, V, pq, pv):
    """

    :param Y:
    :param S:
    :param V:
    :param pq:
    :param pv:
    :return:
    """
    Jx, Ji, Jp, n_rows, n_cols, nnz = jacobian_numba(nbus=len(S),
                                                     Gi=Y.indices, Gp=Y.indptr, Gx=Y.data.real,
                                                     Bx=Y.data.imag, P=S.real, Q=S.imag,
                                                     E=V.real, F=V.imag,
                                                     pq=pq, pvpq=np.r_[pv, pq])

    Jx = np.resize(Jx, nnz)
    Ji = np.resize(Ji, nnz)

    return sp.csc_matrix((Jx, Ji, Jp), shape=(n_rows, n_cols))


if __name__ == '__main__':
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus (pq).gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
    # fname = r'C:\Users\SPV86\Documents\Git\GitHub\GridCal\Grids_and_profiles\grids\IEEE14 - ntc areas.gridcal'
    fname = '/home/santi/Documentos/Git/GitLab/newton-solver/demo/data/IEEE14.json'
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)

    # V = nc.Vbus
    # Scalc = V * np.conj(nc.Ybus * V)

    # iteration 2
    # Vre = [1.06, 1.04488675, 1.00804029, 1.02858513, 1.0324751,  1.06947115, 1.06725069, 1.08958235, 1.05583194, 1.05057218,  1.05821308, 1.05781636, 1.05172362, 1.03396823]
    # Vim = [0., - 0.01538427, - 0.06288706, - 0.05994457, - 0.04369106, - 0.03363703, - 0.06776493, - 0.03017128, - 0.09584117, - 0.08998592, - 0.06420455, - 0.05308109, - 0.05787852, - 0.09759616]
    # P = [0.55505124,  0.39924351, - 0.34117152, - 0.4930584, - 0.06031373,  0.51145912,  0.01505272, 0.23636194, - 0.33529515, - 0.09777923, - 0.02046753, - 0.05696237, - 0.12507272, - 0.15945348]
    # Q = [0.18173886, - 0.10330215, - 0.23079603,  0.05741363,  0.0073527, - 0.15016854,  0.05398631,  0.13169422, - 0.15424652, - 0.05778584, - 0.00001188, - 0.00304259, - 0.03428133, - 0.04719734]
    # iteration 2
    # Vre = [1.06, 1.04485949, 1.00790328, 1.02595, 1.02993806, 1.06921328, 1.06161576, 1.08944016, 1.05082578, 1.04584549, 1.05342871, 1.05377697, 1.04782681, 1.02986825]
    # Vim = [0., - 0.01713639, - 0.06504598, - 0.06127599, - 0.0458676, - 0.04102402, - 0.06979446, - 0.03493049, - 0.09534225, - 0.09050986, - 0.06846003, - 0.05909653, - 0.06322805, - 0.09800842]
    # P = [0.59607251,  0.38300461, - 0.34199021, - 0.47808081, - 0.07591259,  0.48816748,  0.00019828, 0.22114178, - 0.29536559, - 0.0900376, - 0.03484355, - 0.06097865, - 0.13490782, - 0.14904943]
    # Q = [0.18191753, - 0.06736592, - 0.21562461,  0.03907161, - 0.01588749, - 0.07033366,  0.00032195, 0.16517287, - 0.16587965, - 0.05795144, - 0.01790901, - 0.01595776, - 0.05789779, - 0.04994756]

    # V = np.array(Vre) + 1j * np.array(Vim)
    # Scalc = np.array(P) + 1j * np.array(Q)

    V = nc.Vbus
    Scalc = nc.Sbus

    btypes = nc.bus_data.bus_types

    dSbus_dVa, dSbus_dVm = dSbus_dV(Ybus=nc.Ybus, V=V)
    J4 = dSbus_dVm[np.ix_(nc.pq, nc.pq)].imag.todense()

    # J = jacobian1(G=nc.Ybus.real.tocsc(),
    #               B=nc.Ybus.imag.tocsc(),
    #               P=Scalc.real,
    #               Q=Scalc.imag,
    #               E=V.real,
    #               F=V.imag,
    #               pq=nc.pq,
    #               pv=nc.pv)

    # J = jacobian1Polar(G=nc.Ybus.real.tocsc(),
    #                    B=nc.Ybus.imag.tocsc(),
    #                    P=Scalc.real,
    #                    Q=Scalc.imag,
    #                    E=V.real,
    #                    F=V.imag,
    #                    pq=nc.pq,
    #                    pv=nc.pv)

    J = jacobian2(Y=nc.Ybus.tocsc(),
                  S=Scalc,
                  V=V,
                  pq=nc.pq,
                  pv=nc.pv)

    Jgc = gc.AC_jacobian(nc.Ybus, V, np.r_[nc.pv, nc.pq], nc.pq, len(nc.pv), len(nc.pq))

    print('J gómez expósito')
    print(J.toarray())
    print(J.shape)

    print('J gridcal')
    print(Jgc.toarray())
    # print(J4)
