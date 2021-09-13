import GridCal.Engine as gc
import numpy as np
import scipy.sparse as sp
import numba as nb


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
    pqpv = np.r_[pv, pq]
    npqpv = len(pqpv)
    n_rows = len(pqpv) + len(pq)
    n_cols = len(pqpv) + len(pq)

    nnz = 0
    p = 0
    Jx = np.empty(G.nnz * 4, dtype=float)  # data
    Ji = np.empty(G.nnz * 4, dtype=int)  # indices
    Jp = np.empty(n_cols + 1, dtype=int)  # pointers
    Jp[p] = 0

    # generate lookup for the non immediate axis (for CSC it is the rows) -> index lookup
    lookup_pqpv = np.zeros(G.shape[0], dtype=int)
    lookup_pqpv[pqpv] = np.arange(len(pqpv), dtype=int)

    lookup_pq = np.zeros(G.shape[0], dtype=int)
    lookup_pq[pq] = np.arange(len(pq), dtype=int)

    for j in pqpv:  # sliced columns
        
        # fill in J1
        for k in range(G.indptr[j], G.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = G.indices[k]
            ii = lookup_pqpv[i]

            if pqpv[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = F[i] * (G.data[k] * E[j] - B.data[k] * F[j]) - \
                              E[i] * (B.data[k] * E[j] + G.data[k] * F[j])
                else:
                    Jx[nnz] = -Q[i] - B.data[k] * (E[i] + F[i])

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
                    Jx[nnz] = P[i] - G.data[k] * (E[i] + F[i])

                Ji[nnz] = ii + npqpv
                nnz += 1

        p += 1
        Jp[p] = nnz

    # J2 and J4
    for j in pq:  # sliced columns

        # fill in J2
        for k in range(G.indptr[j], G.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = G.indices[k]
            ii = lookup_pqpv[i]

            if pqpv[ii] == i:  # rows
                # entry found
                if i != j:
                    Jx[nnz] = E[i] * (G.data[k] * E[j] - B.data[k] * F[j])  \
                            + F[i] * (B.data[k] * E[j] + G.data[k] * F[j])
                else:
                    Jx[nnz] = P[i] + G.data[k] * (E[i] + F[i])

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
                    Jx[nnz] = F[i] * (G.data[k] * E[j] - B.data[k] * F[j]) \
                            - E[i] * (B.data[k] * E[j] + G.data[k] * F[j])
                else:
                    Jx[nnz] = Q[i] - B.data[k] * (E[i] + F[i])

                Ji[nnz] = ii + npqpv
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
                    Jx[nnz] = F[i] * (Gx[k] * E[j] - Bx[k] * F[j]) - \
                              E[i] * (Bx[k] * E[j] + Gx[k] * F[j])
                else:
                    Jx[nnz] = - Q[i] - Bx[k] * (E[i] + F[i])

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
                    Jx[nnz] = - E[i] * (Gx[k] * E[j] - Bx[k] * F[j]) \
                              - F[i] * (Bx[k] * E[j] + Gx[k] * F[j])
                else:
                    Jx[nnz] = P[i] - Gx[k] * (E[i] + F[i])

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
                    Jx[nnz] = E[i] * (Gx[k] * E[j] - Bx[k] * F[j]) \
                              + F[i] * (Bx[k] * E[j] + Gx[k] * F[j])
                else:
                    Jx[nnz] = P[i] + Gx[k] * (E[i] + F[i])

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
                    Jx[nnz] = F[i] * (Gx[k] * E[j] - Bx[k] * F[j]) \
                              - E[i] * (Bx[k] * E[j] + Gx[k] * F[j])
                else:
                    Jx[nnz] = Q[i] - Bx[k] * (E[i] + F[i])

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
    fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'

    grid = gc.FileOpen(fname).open()
    nc = gc.compile_snapshot_opf_circuit(grid)

    V = nc.Vbus
    Scalc = V * np.conj(nc.Ybus * V)

    # J = jacobian1(G=nc.Ybus.real,
    #               B=nc.Ybus.imag,
    #               P=Scalc.real,
    #               Q=Scalc.imag,
    #               E=V.real,
    #               F=V.imag,
    #               pq=nc.pq,
    #               pv=nc.pv)

    J = jacobian2(Y=nc.Ybus,
                  S=Scalc,
                  V=V,
                  pq=nc.pq,
                  pv=nc.pv)
    print(J.toarray())
    print(J.shape)
