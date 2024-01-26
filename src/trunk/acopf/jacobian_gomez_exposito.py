import numpy as np
import scipy.sparse as sp
from math import sin, cos
import GridCalEngine.api as gc
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_power


def jacobian_polar(G, B, P, Q, Vm, Va, pq, pv):
    """
    Compute the Tinney version of the AC jacobian

    :param G: Conductance matrix in CSC format
    :param B: Susceptance matrix in CSC format
    :param P: Real computed power
    :param Q: Imaginary computed power
    :param V: Voltage
    :param pq: array pf pq indices
    :param pv: array of pv indices
    :return: CSC Jacobian matrix
    """
    pvpq = np.r_[pv, pq]
    npvpq = len(pvpq)
    n_rows = len(pvpq) + len(pq)
    n_cols = len(pvpq) + len(pq)

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
                    Jx[nnz] = -Q[i] - B.data[k] * Vm[i] * Vm[i]

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
                    Jx[nnz] = P[i] - G.data[k] * Vm[i] * Vm[i]

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
                    Jx[nnz] = Vm[i] * (G.data[k] * cos(da) + B.data[k] * sin(da))
                else:
                    Jx[nnz] = (P[i] / Vm[i] + G.data[k] * Vm[i])

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
                    Jx[nnz] = Vm[i] * (G.data[k] * sin(da) - B.data[k] * cos(da))
                else:
                    Jx[nnz] = (Q[i] / Vm[i] - B.data[k] * Vm[i])

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


if __name__ == '__main__':
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus (pq).gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
    fname = r'/Users/eroot/PyCharmProjects/GridCal/Grids_and_profiles/grids/IEEE 14 bus.raw'
    # fname = '/home/santi/Documentos/Git/GitLab/newton-solver/demo/data/IEEE14.json'

    # open file
    grid = gc.FileOpen(fname).open()
    nc = gc.compile_numerical_circuit_at(grid)

    # compute the traditional jacobian
    Scalc = compute_power(Ybus=nc.Ybus, V=nc.Vbus)
    J = jacobian_polar(G=nc.Ybus.real.tocsc(),
                       B=nc.Ybus.imag.tocsc(),
                       P=Scalc.real,
                       Q=Scalc.imag,
                       Vm=np.abs(nc.Vbus),
                       Va=np.angle(nc.Vbus),
                       pq=nc.pq,
                       pv=nc.pv)

    # compute the gridcal jacobian
    Jgc = AC_jacobian(nc.Ybus, nc.Vbus, np.r_[nc.pv, nc.pq], nc.pq)

    print('J Gómez Expósito (mod)')
    print(J.toarray())
    print(J.shape)

    print('J gridcal')
    print(Jgc.toarray())

    diff = J.toarray() - Jgc.toarray()
    print("ok: ", np.isclose(J.toarray(), Jgc.toarray(), atol=1e-6).all())
