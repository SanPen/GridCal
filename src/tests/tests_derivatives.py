import os
import numpy as np
import GridCalEngine.Simulations.derivatives.csc_derivatives as cscdiff
import GridCalEngine.Simulations.derivatives.matpower_derivatives as mdiff
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Utils.Sparse.csc2 import mat_to_scipy
import GridCalEngine.api as gce


def check_dSf_dVm(dSf_dVm1, br_idx, bus_idx, nc: NumericalCircuit):
    """

    :param dSf_dVm1:
    :param br_idx:
    :param bus_idx:
    :param nc:
    :return:
    """
    dSf_dVm2 = cscdiff.dSf_dVm_csc(nbus=nc.nbus,
                                   br_indices=br_idx,
                                   bus_indices=bus_idx,
                                   yff=nc.admittances_.yff,
                                   yft=nc.admittances_.yft,
                                   V=nc.Vbus,
                                   F=nc.F, T=nc.T)

    dSf_dVm3 = dSf_dVm1[np.ix_(br_idx, bus_idx)]

    # print(f"dSf_dVm1 (matpower):\n {dSf_dVm1.real.toarray()}")
    # print(f"dSf_dVm3 (matpower):\n {dSf_dVm3.real.toarray()}")
    # print(f"dSf_dVm2 (new):\n {dSf_dVm2.real.toarray()}")

    assert np.allclose(dSf_dVm3.toarray(), dSf_dVm2.toarray())


def check_dSf_dVa(dSf_dVa1, br_idx, bus_idx, nc: NumericalCircuit):
    """

    :param dSf_dVa1:
    :param br_idx:
    :param bus_idx:
    :param nc:
    :return:
    """
    dSf_dVa2 = cscdiff.dSf_dVa_csc(nbus=nc.nbus,
                                   br_indices=br_idx,
                                   bus_indices=bus_idx,
                                   yff=nc.admittances_.yff,
                                   yft=nc.admittances_.yft,
                                   V=nc.Vbus,
                                   F=nc.F, T=nc.T)

    dSf_dVa3 = dSf_dVa1[np.ix_(br_idx, bus_idx)]

    # print(f"dSf_dVa1 (matpower):\n {dSf_dVa1.real.toarray()}")
    # print(f"dSf_dVa3 (matpower):\n {dSf_dVa3.real.toarray()}")
    # print(f"dSf_dVa2 (new):\n {dSf_dVa2.real.toarray()}")

    assert np.allclose(dSf_dVa3.toarray(), dSf_dVa2.toarray())


def check_dSt_dVm(dSt_dVm1, br_idx, bus_idx, nc: NumericalCircuit):
    """

    :param dSt_dVm1:
    :param br_idx:
    :param bus_idx:
    :param nc:
    :return:
    """
    dSt_dVm2 = cscdiff.dSt_dVm_csc(nbus=nc.nbus,
                                   br_indices=br_idx,
                                   bus_indices=bus_idx,
                                   ytt=nc.admittances_.ytt,
                                   ytf=nc.admittances_.ytf,
                                   V=nc.Vbus,
                                   F=nc.F, T=nc.T)

    dSt_dVm3 = dSt_dVm1[np.ix_(br_idx, bus_idx)]

    # print(f"dSf_dVm1 (matpower):\n {dSf_dVm1.real.toarray()}")
    # print(f"dSf_dVm3 (matpower):\n {dSf_dVm3.real.toarray()}")
    # print(f"dSf_dVm2 (new):\n {dSf_dVm2.real.toarray()}")

    assert np.allclose(dSt_dVm3.toarray(), dSt_dVm2.toarray())


def check_dSt_dVa(dSt_dVa1, br_idx, bus_idx, nc: NumericalCircuit):
    """

    :param dSt_dVa1:
    :param br_idx:
    :param bus_idx:
    :param nc:
    :return:
    """
    dSt_dVa2 = cscdiff.dSt_dVa_csc(nbus=nc.nbus,
                                   br_indices=br_idx,
                                   bus_indices=bus_idx,
                                   ytf=nc.admittances_.ytf,
                                   V=nc.Vbus,
                                   F=nc.F, T=nc.T)

    dSt_dVa3 = dSt_dVa1[np.ix_(br_idx, bus_idx)]

    # print(f"dSt_dVa1 (matpower):\n {dSt_dVa1.real.toarray()}")
    # print(f"dSt_dVa3 (matpower):\n {dSt_dVa3.real.toarray()}")
    # print(f"dSt_dVa2 (new):\n {dSt_dVa2.real.toarray()}")

    assert np.allclose(dSt_dVa3.toarray(), dSt_dVa2.toarray())


def test_branch_derivatives() -> None:
    """
    Test the branch derivatives
    :return:
    """
    fname = os.path.join("data", "grids", "RAW", "IEEE 14 bus.raw")
    grid = gce.open_file(filename=fname)
    nc = gce.compile_numerical_circuit_at(grid)

    dSf_dVa1, dSf_dVm1, dSt_dVa1, dSt_dVm1 = mdiff.dSbr_dV_matpower(Yf=nc.Yf,
                                                                    Yt=nc.Yt,
                                                                    V=nc.Vbus,
                                                                    F=nc.F,
                                                                    T=nc.T,
                                                                    Cf=nc.Cf,
                                                                    Ct=nc.Ct)

    test_data = [
        {
            "bus_idx": np.array([1, 2, 3, 4, 5, 6, 7]),
            "br_idx": np.array([10, 12, 14]),
        },
        {
            "bus_idx": np.array([1, 2, 3, 4, 5, 6, 7]),
            "br_idx": np.array([2, 3, 4]),
        },
        {
            "bus_idx": np.arange(nc.nbus),
            "br_idx": np.arange(nc.nbr),
        },
    ]

    for dta in test_data:
        br_idx = dta["br_idx"]
        bus_idx = dta["bus_idx"]
        check_dSf_dVm(dSf_dVm1, br_idx, bus_idx, nc)
        check_dSf_dVa(dSf_dVa1, br_idx, bus_idx, nc)
        check_dSt_dVm(dSt_dVm1, br_idx, bus_idx, nc)
        check_dSt_dVa(dSt_dVa1, br_idx, bus_idx, nc)


def check_dSbus_dtau(dSbus_dsh1, br_idx, bus_idx, Ys, nc: NumericalCircuit):
    """

    :param dSbus_dsh1:
    :param br_idx:
    :param bus_idx:
    :param Ys:
    :param nc:
    :return:
    """
    dSbus_dsh2 = cscdiff.dSbus_dtau_csc(nbus=nc.nbus,
                                        bus_indices=bus_idx,
                                        tau_indices=br_idx,
                                        F=nc.F,
                                        T=nc.T,
                                        Ys=Ys,
                                        k2=nc.branch_data.k,
                                        tap=nc.branch_data.tap,
                                        V=nc.Vbus)

    dSbus_dsh3 = mat_to_scipy(dSbus_dsh1)[np.ix_(bus_idx, br_idx)]

    # print(f"dSbus_dsh1 (matpower):\n {dSbus_dsh1.real.toarray()}")
    # print(f"dSbus_dsh3 (matpower):\n {dSbus_dsh3.real.toarray()}")
    # print(f"dSbus_dsh2 (new):\n {dSbus_dsh2.real.toarray()}")

    assert np.allclose(dSbus_dsh3.toarray(), dSbus_dsh2.toarray())


def check_dSf_dtau(dSf_dtau1, sf_indices, tau_indices, Ys, nc: NumericalCircuit):
    """

    :param dSf_dtau1:
    :param sf_indices:
    :param tau_indices:
    :param Ys:
    :param nc:
    :return:
    """
    dSf_dtau2 = cscdiff.dSf_dtau_csc(sf_indices=sf_indices,
                                     tau_indices=tau_indices,
                                     F=nc.F,
                                     T=nc.T,
                                     Ys=Ys,
                                     K2=nc.branch_data.k,
                                     tap=nc.branch_data.tap,
                                     V=nc.Vbus)

    dSf_dtau3 = mat_to_scipy(dSf_dtau1)[np.ix_(sf_indices, tau_indices)]

    # print(f"dSf_dtau1 (matpower):\n {dSf_dtau1.real.toarray()}")
    # print(f"dSf_dtau3 (matpower):\n {dSf_dtau3.real.toarray()}")
    # print(f"dSf_dtau2 (new):\n {dSf_dtau2.real.toarray()}")

    assert np.allclose(dSf_dtau3.toarray(), dSf_dtau2.toarray())


def check_dSt_dtau(dSt_dtau1, sf_indices, tau_indices, Ys, nc: NumericalCircuit):
    """

    :param dSt_dtau1:
    :param sf_indices:
    :param tau_indices:
    :param Ys:
    :param nc:
    :return:
    """
    dSt_dtau2 = cscdiff.dSt_dtau_csc(sf_indices=sf_indices,
                                     tau_indices=tau_indices,
                                     F=nc.F,
                                     T=nc.T,
                                     Ys=Ys,
                                     K2=nc.branch_data.k,
                                     tap=nc.branch_data.tap,
                                     V=nc.Vbus)

    dSt_dtau3 = mat_to_scipy(dSt_dtau1)[np.ix_(sf_indices, tau_indices)]

    # print(f"dSt_dtau1 (matpower):\n {dSt_dtau1.real.toarray()}")
    # print(f"dSt_dtau3 (matpower):\n {dSt_dtau3.real.toarray()}")
    # print(f"dSt_dtau2 (new):\n {dSt_dtau2.real.toarray()}")

    assert np.allclose(dSt_dtau3.toarray(), dSt_dtau2.toarray())


def test_tau_derivatives() -> None:
    # fname = os.path.join("data", "grids", "fubm_case_57_14_2MTDC_ctrls.gridcal")
    fname = os.path.join("data", "grids", "RAW", "IEEE 14 bus.raw")
    grid = gce.open_file(filename=fname)
    nc = gce.compile_numerical_circuit_at(grid)

    Ys = 1.0 / (nc.branch_data.R + 1j * nc.branch_data.X)
    bus_idx = np.arange(nc.nbus, dtype=np.int32)
    br_idx = np.arange(nc.nbr, dtype=np.int32)
    # br_idx = nc.k_pf_tau

    dSbus_dtau1, dSf_dtau1, dSt_dtau1 = cscdiff.derivatives_tau_csc_numba(nbus=nc.nbus,
                                                                          nbr=nc.nbr,
                                                                          iPxsh=br_idx,
                                                                          F=nc.F,
                                                                          T=nc.T,
                                                                          Ys=Ys,
                                                                          k2=nc.branch_data.k,
                                                                          tap=nc.branch_data.tap,
                                                                          V=nc.Vbus)

    test_data = [
        {
            "bus_idx": np.array([1, 2, 3, 4, 5, 6, 7]),
            "br_idx": np.array([10, 12, 14]),
            "sf_idx": np.array([1, 2, 3, 4, 5, 6, 7]),
        },
        {
            "bus_idx": np.array([1, 2, 3, 4, 5, 6, 7]),
            "br_idx": np.array([2, 3, 4]),
            "sf_idx": np.array([2, 3, 4]),
        },
        {
            "bus_idx": np.arange(nc.nbus),
            "br_idx": np.arange(nc.nbr),
            "sf_idx": np.arange(nc.nbr),
        },
    ]

    for dta in test_data:
        br_idx = dta["br_idx"]
        bus_idx = dta["bus_idx"]
        sf_idx = dta["sf_idx"]
        check_dSbus_dtau(dSbus_dtau1, br_idx, bus_idx, Ys, nc)
        check_dSf_dtau(dSf_dtau1, sf_idx, br_idx, Ys, nc)
        check_dSt_dtau(dSt_dtau1, sf_idx, br_idx, Ys, nc)


if __name__ == '__main__':
    # test_branch_derivatives()
    test_tau_derivatives()
