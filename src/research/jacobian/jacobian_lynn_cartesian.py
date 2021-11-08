import GridCal.Engine as gc
import numpy as np
import scipy.sparse as sp
import numba as nb
from math import sin, cos


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
    s1 = np.zeros(G.nnz, dtype=float)  # data
    s2 = np.zeros(G.nnz, dtype=float)  # data
    s3 = np.zeros(G.nnz, dtype=float)  # data
    s4 = np.zeros(G.nnz, dtype=float)  # data

    # pass 1
    for j in range(G.shape[1]):  # all columns

        # fill in J1
        for k in range(G.indptr[j], G.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = G.indices[k]

            # entry found
            if i != j:
                s1[i] += G.data[k] * E[j] - B.data[k] * F[j]
                s2[i] += G.data[k] * F[j] + B.data[k] * E[j]

    # pass 2
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
                    Jx[nnz] = G.data[k] * E[i] + B.data[k] * F[i]

                else:
                    Jx[nnz] = 2 * G.data[k] * E[i] + s1[i]

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
                    Jx[nnz] = G.data[k] * F[i] - B.data[k] * E[i]
                else:
                    Jx[nnz] = -2 * B.data[k] * E[i] + s2[i]

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
                    Jx[nnz] = - B.data[k] * E[i] + G.data[k] * F[i]
                else:
                    Jx[nnz] = 2 * G.data[k] * F[i] + s2[i]

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
                    Jx[nnz] = - B.data[k] * F[i] - G.data[k] * E[i]
                else:
                    Jx[nnz] = -2 * B.data[k] * F[i] + s1[i]

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
    # fname = r'C:\Users\SPV86\Documents\Git\GitHub\GridCal\Grids_and_profiles\grids\IEEE14 - ntc areas.gridcal'
    fname = r'C:\Users\SPV86\Documents\Git\GitHub\GridCal\Grids_and_profiles\grids\lynn5buspv.xlsx'

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
    Vre = [1.06, 1.04485949, 1.00790328, 1.02595, 1.02993806, 1.06921328, 1.06161576, 1.08944016, 1.05082578,
           1.04584549, 1.05342871, 1.05377697, 1.04782681, 1.02986825]
    Vim = [0., - 0.01713639, - 0.06504598, - 0.06127599, - 0.0458676, - 0.04102402, - 0.06979446, - 0.03493049,
           - 0.09534225, - 0.09050986, - 0.06846003, - 0.05909653, - 0.06322805, - 0.09800842]
    P = [0.59607251, 0.38300461, - 0.34199021, - 0.47808081, - 0.07591259, 0.48816748, 0.00019828, 0.22114178,
         - 0.29536559, - 0.0900376, - 0.03484355, - 0.06097865, - 0.13490782, - 0.14904943]
    Q = [0.18191753, - 0.06736592, - 0.21562461, 0.03907161, - 0.01588749, - 0.07033366, 0.00032195, 0.16517287,
         - 0.16587965, - 0.05795144, - 0.01790901, - 0.01595776, - 0.05789779, - 0.04994756]

    V = np.array(Vre) + 1j * np.array(Vim)
    Scalc = np.array(P) + 1j * np.array(Q)

    btypes = nc.bus_data.bus_types

    J = jacobian1(G=nc.Ybus.real.tocsc(),
                  B=nc.Ybus.imag.tocsc(),
                  P=Scalc.real,
                  Q=Scalc.imag,
                  E=V.real,
                  F=V.imag,
                  pq=nc.pq,
                  pv=nc.pv)
    print(J.toarray())
    print(J.shape)

    # print(J4)
