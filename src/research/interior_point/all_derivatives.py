
import numpy as np
from scipy.sparse import issparse, csr_matrix as sparse, hstack as hstack_sp, vstack as vstack_sp, diags
from scipy.sparse.linalg import spsolve, splu


def all_derivatives(Ybus, Vbus, Sbus, Ibus, Cf, Ct, Cg):
    """

    :param Ybus:
    :param Vbus:
    :param Sbus:
    :param Ibus:
    :param Cf:
    :param Ct:
    :param Cg:
    :return:
    """

    n = len(Vbus)

    Vm = np.abs(Vbus)
    Va = np.angle(Vbus)
    E = diags(Vbus / Vm)
    V = diags(Vbus)
    I = diags(Ibus)
    Vconj = diags(np.conj(Vbus))
    Iconj = diags(np.conj(Ibus))

    # bus voltage first derivatives
    dV_dVa = 1j * V
    dV_dVm = E
    dE_dVa = 1j * E
    dE_dVm = sparse(n, n)

    # bus voltage second derivatives
    dV2_dVa = sparse(n, n)
    dV2_dVm = sparse(n, n)
    dE2_dVa = sparse(n, n)
    dE2_dVm = sparse(n, n)

    # branch voltage first derivatives
    dVf_dVa = 1j * Cf * V
    dVf_dVm = Cf * E
    dVt_dVa = 1j * Ct * V
    dVt_dVm = Ct * E

    # bus current injections first derivative
    dIbus_dVa = 1j * Ybus * V
    dIbus_dVm = Ybus * E

    # bus power injections first derivative
    dSbus_dVa = 1j * V * np.conj((I - Ybus * V))
    dSbus_dVm = E * np.conj((I + Ybus * V))

    dS = [dSbus_dVa, dSbus_dVm, -Cg, -1j * Cg]  # all the bus derivatives



if __name__ == '__main__':
    pass