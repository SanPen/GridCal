
from numba import jit
from scipy.sparse import issparse
from numpy import conj, abs, allclose
from numpy import complex128, float64, int32
from numpy.core.multiarray import zeros, empty, array
from scipy.sparse import csc_matrix, vstack, hstack, diags, csr_matrix


def dSbus_dV(Ybus, V):
    """
    Computes partial derivatives of power injection w.r.t. voltage as defined in Matpower
    """

    Ibus = Ybus * V
    diagV = diags(V)
    diagIbus = diags(Ibus)
    diagVnorm = diags(V / abs(V))
    dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
    dS_dVa = 1j * diagV * conj(diagIbus - Ybus * diagV)
    return dS_dVm, dS_dVa


@jit(nopython=True, cache=False)
def dSbus_dV_numba_sparse_csc(Yx, Yp, Yi, V):  # pragma: no cover
    """
    Compute the power injection derivatives w.r.t the voltage module and angle
    :param Yx: data of Ybus in CSC format
    :param Yp: indptr of Ybus in CSC format
    :param Yi: indices of Ybus in CSC format
    :param V: Voltages vector
    :return: dS_dVm, dS_dVa data ordered in the CSC format to match the indices of Ybus
    """

    # init buffer vector
    n = len(Yp) - 1
    Ibus = zeros(n, dtype=complex128)
    Vnorm = V / np.abs(V)
    dS_dVm = Yx.copy()
    dS_dVa = Yx.copy()

    # pass 1
    for j in range(n):  # for each column ...
        for k in range(Yp[j], Yp[j + 1]):  # for each row ...
            # row index
            i = Yi[k]

            # Ibus = Ybus * V
            Ibus[i] += Yx[k] * V[j]  # Yx[k] -> Y(i,j)

            # Ybus * diagVnorm
            dS_dVm[k] = Yx[k] * Vnorm[j]

            # Ybus * diag(V)
            dS_dVa[k] = Yx[k] * V[j]

    # pass 2
    for j in range(n):  # for each column ...

        # set buffer variable: this cannot be done in the pass1
        # because Ibus is not fully formed, but here it is.
        buffer = conj(Ibus[j]) * Vnorm[j]

        for k in range(Yp[j], Yp[j + 1]):  # for each row ...

            # row index
            i = Yi[k]

            # diag(V) * conj(Ybus * diagVnorm)
            dS_dVm[k] = V[i] * conj(dS_dVm[k])

            if j == i:
                # diagonal elements
                dS_dVa[k] -= Ibus[j]
                dS_dVm[k] += buffer

            # 1j * diagV * conj(diagIbus - Ybus * diagV)
            dS_dVa[k] = conj(-dS_dVa[k]) * (1j * V[i])

    return dS_dVm, dS_dVa


def dSbus_dV_with_numba(Ybus, V):
    """
    Call the numba sparse constructor of the derivatives
    :param Ybus: Ybus in CSC format
    :param V: Voltages vector
    :return: dS_dVm, dS_dVa in CSC format
    """

    # I is subtracted from Y*V,
    # therefore it must be negative for numba version of dSbus_dV if it is not zeros anyways
    # calculates sparse data
    dS_dVm, dS_dVa = dSbus_dV_numba_sparse_csc(Ybus.data, Ybus.indptr, Ybus.indices, V)
    # generate sparse CSR matrices with computed data and return them
    # return csr_matrix((dS_dVm, Ybus.indices, Ybus.indptr)), csr_matrix((dS_dVa, Ybus.indices, Ybus.indptr))
    return csc_matrix((dS_dVm, Ybus.indices, Ybus.indptr)), csc_matrix((dS_dVa, Ybus.indices, Ybus.indptr))


def create_J_without_numba(Ybus, V, pvpq, pq):
    """
    Standard matpower-like implementation
    :param Ybus:
    :param V:
    :param pvpq:
    :param pq:
    :return:
    """
    dS_dVm, dS_dVa = dSbus_dV(Ybus, V)

    # evaluate Jacobian
    J11 = dS_dVa[array([pvpq]).T, pvpq].real
    J12 = dS_dVm[array([pvpq]).T, pq].real
    J21 = dS_dVa[array([pq]).T, pvpq].imag
    J22 = dS_dVm[array([pq]).T, pq].imag
    J = vstack([hstack([J11, J12]),
                hstack([J21, J22])], format="csr")
    return J


if __name__ == "__main__":
    import numpy as np
    from GridCal.Engine import compile_snapshot_circuit, FileOpen
    np.set_printoptions(precision=4, linewidth=100000)

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE14_from_raw.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Illinois 200 Bus.gridcal'
    grid = FileOpen(fname).open()

    nc_ = compile_snapshot_circuit(grid)

    dS_dVm1, dS_dVa1 = dSbus_dV(nc_.Ybus, nc_.Vbus)
    dS_dVm2, dS_dVa2 = dSbus_dV_with_numba(nc_.Ybus, nc_.Vbus)

    ok_Vm = allclose(dS_dVm1.toarray(), dS_dVm2.toarray())
    ok_Va = allclose(dS_dVa1.toarray(), dS_dVa2.toarray())

    print('ok_Vm', ok_Vm)
    print('ok_Va', ok_Va)
    pvpq = np.r_[nc_.pv, nc_.pq]
    J1 = create_J_without_numba(nc_.Ybus, nc_.Vbus, pvpq, nc_.pq)

    print()
