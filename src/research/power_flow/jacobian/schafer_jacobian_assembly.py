from GridCal.Engine import *
import numpy as np
import numba as nb
import scipy.sparse as sp
from scipy.sparse import lil_matrix, diags, csr_matrix


def dSbus_dV_numba_sparse_csr(Yx, Yp, Yj, V, E):  # pragma: no cover
    """
    partial derivatives of power injection w.r.t. voltage.
    :param Yx: Ybus data in CSC format
    :param Yp: Ybus indptr in CSC format
    :param Yj: Ybus indices in CSC format
    :param V: Voltage vector
    :param E: Normalized voltage vector
    :param Ibus: Currents vector
    :return: dS_dVm, dS_dVa data in CSR format, index pointer and indices are the same as the ones from Ybus
    """

    # init buffer vector
    buffer = np.zeros(len(V), dtype=np.complex128)
    Ibus = np.zeros(len(V), dtype=np.complex128)
    dS_dVm = Yx.copy()
    dS_dVa = Yx.copy()

    # iterate through sparse matrix
    for r in range(len(Yp) - 1):
        for k in range(Yp[r], Yp[r + 1]):
            # Ibus = Ybus * V
            buffer[r] += Yx[k] * V[Yj[k]]

            # Ybus * diag(Vnorm)
            dS_dVm[k] *= E[Yj[k]]

            # Ybus * diag(V)
            dS_dVa[k] *= V[Yj[k]]

        Ibus[r] += buffer[r]

        # conj(diagIbus) * diagVnorm
        buffer[r] = np.conj(buffer[r]) * E[r]

    for r in range(len(Yp) - 1):
        for k in range(Yp[r], Yp[r + 1]):
            # diag(V) * conj(Ybus * diagVnorm)
            dS_dVm[k] = np.conj(dS_dVm[k]) * V[r]

            if r == Yj[k]:
                # diagonal elements
                dS_dVa[k] = -Ibus[r] + dS_dVa[k]
                dS_dVm[k] += buffer[r]

            # 1j * diagV * conj(diagIbus - Ybus * diagV)
            dS_dVa[k] = np.conj(-dS_dVa[k]) * (1j * V[r])

    return dS_dVm, dS_dVa



fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
circuit = FileOpen(fname).open()
nc = compile_snapshot_circuit(circuit)

Ybus = nc.Ybus.tocsr()
V = nc.Vbus
E = V / np.abs(V)
S = nc.Sbus
pv = nc.pv
pq = nc.pq
pvpq = np.r_[pv, pq]

dVm_x, dVa_x = dSbus_dV_numba_sparse_csr(Ybus.data, Ybus.indptr, Ybus.indices, V, E)

nnz = 0
npvpq = len(pvpq)
npv = len(pv)
npq = len(pq)

# row pointer, dimension = pvpq.shape[0] + pq.shape[0] + 1
Jp = np.zeros(npvpq + npq + 1, dtype=int)
Jx = np.empty(len(dVm_x) * 4, dtype=float)
Jj = np.empty(len(dVm_x) * 4, dtype=int)

# generate lookup pvpq -> index pvpq (used in createJ)
pvpq_lookup = np.zeros(Ybus.shape[0], dtype=int)
pvpq_lookup[pvpq] = np.arange(npvpq)

Yp = Ybus.indptr
Yx = Ybus.data
Yj = Ybus.indices

# iterate rows of J
# first iterate pvpq (J11 and J12) (dP_dVa, dP_dVm)
for r in range(npvpq):

    # nnzStar is necessary to calculate nonzeros per row
    nnzStart = nnz

    # iterate columns of J11 = dS_dVa.real at positions in pvpq
    # check entries in row pvpq[r] of dS_dV
    for c in range(Yp[pvpq[r]], Yp[pvpq[r] + 1]):

        # check if column Yj is in pv|pq
        # cc is the transformation of the column index into the pv|pq space
        # this piece is the key to slice the columns
        cc = pvpq_lookup[Yj[c]]

        # entries for J11 and J12
        if pvpq[cc] == Yj[c]:
            # entry found
            # equals entry of J11: J[r,cc] = dS_dVa[c].real
            Jx[nnz] = dVa_x[c].real
            Jj[nnz] = cc
            nnz += 1

            # if entry is found in the "pq part" of pvpq = add entry of J12
            if cc >= npv:
                Jx[nnz] = dVm_x[c].real
                Jj[nnz] = cc + npq
                nnz += 1

    # Jp: number of non-zeros per row = nnz - nnzStart (nnz at begging of loop - nnz at end of loop)
    Jp[r + 1] = nnz - nnzStart + Jp[r]

# second: iterate pq (J21 and J22) (dQ_dVa, dQ_dVm)
for r in range(npq):

    nnzStart = nnz

    # iterate columns of J21 = dS_dVa.imag at positions in pvpq
    for c in range(Yp[pq[r]], Yp[pq[r] + 1]):

        cc = pvpq_lookup[Yj[c]]

        if pvpq[cc] == Yj[c]:
            # entry found
            # equals entry of J21: J[r + lpvpq, cc] = dS_dVa[c].imag
            Jx[nnz] = dVa_x[c].imag
            Jj[nnz] = cc
            nnz += 1

            if cc >= npv:
                # if entry is found in the "pq part" of pvpq = Add entry of J22
                Jx[nnz] = dVm_x[c].imag
                Jj[nnz] = cc + npq
                nnz += 1

    # Jp: number of non-zeros per row = nnz - nnzStart (nnz at begging of loop - nnz at end of loop)
    Jp[r + npvpq + 1] = nnz - nnzStart + Jp[r + npvpq]

# resize before generating the scipy sparse matrix
Jx.resize(Jp[-1], refcheck=False)
Jj.resize(Jp[-1], refcheck=False)

# generate scipy sparse matrix
nj = npvpq + npq
J = csr_matrix((Jx, Jj, Jp), shape=(nj, nj))
print()
