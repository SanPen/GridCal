# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
from scipy.sparse import csc_matrix
import VeraGridEngine.Simulations.Derivatives.csc_derivatives as cscdiff
import VeraGridEngine.Simulations.Derivatives.ac_jacobian as cscjac
import VeraGridEngine.Simulations.Derivatives.matpower_derivatives as mdiff
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import polar_to_rect
from VeraGridEngine.Simulations.OPF.NumericalMethods.ac_opf_derivatives import compute_branch_power_derivatives
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Utils.Sparse.csc2 import mat_to_scipy, scipy_to_cxmat, CxCSC
import VeraGridEngine.api as gce


def test_bus_derivatives():
    """
    Test the bus derivatives
    :return:
    """
    Ybus = csc_matrix([[0.1 - 9.999j, - 0.1 + 9.999j, 0. + 0.j, 0. + 0.j, 0. + 0.j, 0. + 0.j],
                       [-0.1 + 9.999j, 1.9574 - 10.5489j, - 1.0852 + 0.1809j, 0. + 0.j, - 0.7763 + 0.3697j, 0. + 0.j],
                       [0. + 0.j, - 1.0852 + 0.1809j, 1.5797 - 0.2603j, - 0.4878 + 0.j, 0. + 0.j, 0. + 0.j],
                       [0. + 0.j, 0. + 0.j, - 0.4878 + 0.j, 1.4534 - 0.4252j, - 0.9807 + 0.3326j, 0. + 0.j],
                       [0. + 0.j, - 0.7763 + 0.3697j, 0. + 0.j, - 0.9477 + 0.4174j, 1.8415 - 10.744j, - 0.1 + 9.999j],
                       [0. + 0.j, 0. + 0.j, 0. + 0.j, 0. + 0.j, - 0.1 + 9.999j, 0.1 - 9.999j]])

    Vm = np.array([1.1, 1.096, 1.0975, 1.104, 1.1261, 1.12])
    Va = np.array([0., 0.0004, 0.0656, 0.0656, - 0.0269, - 0.0259])
    V = polar_to_rect(Vm, Va)

    Ybus_x = Ybus.data
    Ybus_p = Ybus.indptr
    Ybus_i = Ybus.indices
    nbus = 6

    dS_dVm_x, dS_dVa_x = cscdiff.dSbus_dV_numba_sparse_csc(Ybus_x, Ybus_p, Ybus_i, V, Vm)
    dS_dVm1 = CxCSC(nbus, nbus, len(dS_dVm_x), False).set(Ybus_i, Ybus_p, dS_dVm_x).toarray()
    dS_dVa1 = CxCSC(nbus, nbus, len(dS_dVa_x), False).set(Ybus_i, Ybus_p, dS_dVa_x).toarray()

    dSbus_dVa, dSbus_dVm = mdiff.dSbus_dV_matpower(Ybus, V)
    dS_dVa2 = scipy_to_cxmat(dSbus_dVa).toarray()
    dS_dVm2 = scipy_to_cxmat(dSbus_dVm).toarray()

    okVa = np.allclose(dS_dVa1, dS_dVa2)
    okVm = np.allclose(dS_dVm1, dS_dVm2)
    assert okVa
    assert okVm

    print()


def check_dSf_dVm(dSf_dVm1, br_idx, bus_idx, nc: NumericalCircuit):
    """

    :param dSf_dVm1:
    :param br_idx:
    :param bus_idx:
    :param nc:
    :return:
    """
    adm = nc.get_admittance_matrices()
    dSf_dVm2 = cscdiff.dSf_dVm_csc(nbus=nc.nbus,
                                   br_indices=br_idx,
                                   bus_indices=bus_idx,
                                   yff=adm.yff,
                                   yft=adm.yft,
                                   Vm=np.abs(nc.bus_data.Vbus),
                                   Va=np.angle(nc.bus_data.Vbus),
                                   F=nc.passive_branch_data.F,
                                   T=nc.passive_branch_data.T)

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
    adm = nc.get_admittance_matrices()
    dSf_dVa2 = cscdiff.dSf_dVa_csc(nbus=nc.nbus,
                                   br_indices=br_idx,
                                   bus_indices=bus_idx,
                                   yft=adm.yft,
                                   V=nc.bus_data.Vbus,
                                   F=nc.passive_branch_data.F,
                                   T=nc.passive_branch_data.T)

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
    adm = nc.get_admittance_matrices()
    dSt_dVm2 = cscdiff.dSt_dVm_csc(nbus=nc.nbus,
                                   br_indices=br_idx,
                                   bus_indices=bus_idx,
                                   ytt=adm.ytt,
                                   ytf=adm.ytf,
                                   Vm=np.abs(nc.bus_data.Vbus),
                                   Va=np.angle(nc.bus_data.Vbus),
                                   F=nc.passive_branch_data.F,
                                   T=nc.passive_branch_data.T)

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
    adm = nc.get_admittance_matrices()
    dSt_dVa2 = cscdiff.dSt_dVa_csc(nbus=nc.nbus,
                                   br_indices=br_idx,
                                   bus_indices=bus_idx,
                                   ytf=adm.ytf,
                                   V=nc.bus_data.Vbus,
                                   F=nc.passive_branch_data.F,
                                   T=nc.passive_branch_data.T)

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
    adm = nc.get_admittance_matrices()

    dSf_dVa1, dSf_dVm1, dSt_dVa1, dSt_dVm1 = mdiff.dSbr_dV_matpower(Yf=adm.Yf,
                                                                    Yt=adm.Yt,
                                                                    V=nc.bus_data.Vbus,
                                                                    F=nc.passive_branch_data.F,
                                                                    T=nc.passive_branch_data.T,
                                                                    Cf=nc.passive_branch_data.Cf.tocsc(),
                                                                    Ct=nc.passive_branch_data.Ct.tocsc())

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


def test_tau_derivatives() -> None:
    """

    :return:
    """
    # fname = os.path.join("data", "grids", "fubm_case_57_14_2MTDC_ctrls.gridcal")
    fname = os.path.join("data", "grids", "RAW", "IEEE 14 bus.raw")
    grid = gce.open_file(filename=fname)
    nc = gce.compile_numerical_circuit_at(grid)
    adm = nc.get_admittance_matrices()

    Ys = 1.0 / (nc.passive_branch_data.R + 1j * nc.passive_branch_data.X)

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
        tau_idx = dta["br_idx"]
        bus_idx = dta["bus_idx"]
        sf_idx = dta["sf_idx"]

        (dSbus_dm1, dSf_dm1, dSt_dm1,
         dSbus_dtau1, dSf_dtau1, dSt_dtau1) = compute_branch_power_derivatives(
            all_tap_m=nc.active_branch_data.tap_module,
            all_tap_tau=nc.active_branch_data.tap_angle,
            V=nc.bus_data.Vbus,
            k_m=np.empty(0, dtype=int),
            k_tau=tau_idx,
            Cf=nc.passive_branch_data.Cf.tocsc(),
            Ct=nc.passive_branch_data.Ct.tocsc(),
            F=nc.passive_branch_data.F,
            T=nc.passive_branch_data.T,
            R=nc.passive_branch_data.R,
            X=nc.passive_branch_data.X
        )

        # dSbus_dtau1, dSf_dtau1, dSt_dtau1 = cscdiff.derivatives_tau_csc_numba(nbus=nc.nbus,
        #                                                                       nbr=nc.nbr,
        #                                                                       iPxsh=tau_idx,
        #                                                                       F=nc.F,
        #                                                                       T=nc.T,
        #                                                                       Ys=Ys,
        #                                                                       kconv=nc.branch_data.k,
        #                                                                       tap=nc.branch_data.tap,
        #                                                                       V=nc.Vbus)

        # dSbus_dtau1, dSf_dtau1, dSt_dtau1 = mdiff.dS_dtau_matpower(V=nc.Vbus,
        #                                                            Cf=nc.Cf,
        #                                                            Ct=nc.Ct,
        #                                                            R=nc.branch_data.R,
        #                                                            X=nc.branch_data.X,
        #                                                            k2=nc.branch_data.k,
        #                                                            m=nc.branch_data.tap_module,
        #                                                            tau=nc.branch_data.tap_angle)

        # check_dSbus_dtau(dSbus_dtau1, br_idx, bus_idx, Ys, nc)

        dSbus_dtau2 = cscdiff.dSbus_dtau_csc(
            nbus=nc.nbus,
            bus_indices=bus_idx,
            tau_indices=tau_idx,
            F=nc.passive_branch_data.F,
            T=nc.passive_branch_data.T,
            Ys=Ys,
            tap=nc.active_branch_data.tap,
            V=nc.bus_data.Vbus
        )

        dSbus_dtau3 = dSbus_dtau1[bus_idx, :]

        # print(f"dSbus_dsh1 (matpower):\n {dSbus_dsh1.real.toarray()}")
        # print(f"dSbus_dsh3 (matpower):\n {dSbus_dsh3.real.toarray()}")
        # print(f"dSbus_dsh2 (new):\n {dSbus_dsh2.real.toarray()}")
        ok1 = np.allclose(dSbus_dtau3.toarray(), dSbus_dtau2.toarray())
        assert ok1

        # check_dSf_dtau(dSf_dtau1, sf_idx, br_idx, Ys, nc)

        dSf_dtau2 = cscdiff.dSf_dtau_csc(nbr=nc.nbr,
                                         sf_indices=sf_idx,
                                         tau_indices=tau_idx,
                                         F=nc.passive_branch_data.F,
                                         T=nc.passive_branch_data.T,
                                         Ys=Ys,
                                         tap=nc.active_branch_data.tap,
                                         V=nc.bus_data.Vbus)

        dSf_dtau3 = dSf_dtau1[sf_idx, :]

        # print(f"dSf_dtau1 (matpower):\n {dSf_dtau1.real.toarray()}")
        # print(f"dSf_dtau3 (matpower):\n {dSf_dtau3.real.toarray()}")
        # print(f"dSf_dtau2 (new):\n {dSf_dtau2.real.toarray()}")
        ok2 = np.allclose(dSf_dtau3.toarray(), dSf_dtau2.toarray())
        assert ok2

        # check_dSt_dtau(dSt_dtau1, sf_idx, br_idx, Ys, nc)

        dSt_dtau2 = cscdiff.dSt_dtau_csc(nbr=nc.nbr,
                                         st_indices=sf_idx,
                                         tau_indices=tau_idx,
                                         F=nc.passive_branch_data.F,
                                         T=nc.passive_branch_data.T,
                                         Ys=Ys,
                                         tap=nc.active_branch_data.tap,
                                         V=nc.bus_data.Vbus)

        dSt_dtau3 = dSt_dtau1[sf_idx, :]

        # print(f"dSt_dtau1 (matpower):\n {dSt_dtau1.real.toarray()}")
        # print(f"dSt_dtau3 (matpower):\n {dSt_dtau3.real.toarray()}")
        # print(f"dSt_dtau2 (new):\n {dSt_dtau2.real.toarray()}")
        ok3 = np.allclose(dSt_dtau3.toarray(), dSt_dtau2.toarray())
        assert ok3


def test_m_derivatives() -> None:
    """

    :return:
    """
    # fname = os.path.join("data", "grids", "fubm_case_57_14_2MTDC_ctrls.gridcal")
    fname = os.path.join("data", "grids", "RAW", "IEEE 14 bus.raw")
    grid = gce.open_file(filename=fname)
    nc = gce.compile_numerical_circuit_at(grid)

    Ys = 1.0 / (nc.passive_branch_data.R + 1j * nc.passive_branch_data.X)

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
        m_idx = dta["br_idx"]
        bus_idx = dta["bus_idx"]
        sf_idx = dta["sf_idx"]

        dSbus_dm1, dSf_dm1, dSt_dm1 = cscdiff.derivatives_ma_csc_numba(
            nbus=nc.nbus,
            nbr=nc.nbr,
            iXxma=m_idx,
            F=nc.passive_branch_data.F,
            T=nc.passive_branch_data.T,
            Ys=Ys,
            kconv=np.ones(nc.nbr),
            tap=nc.active_branch_data.tap,
            tap_module=nc.active_branch_data.tap_module,
            Bc=nc.passive_branch_data.B,
            Beq=np.zeros(nc.nbr),
            V=nc.bus_data.Vbus
        )
        dSbus_dm1, dSf_dm1, dSt_dm1 = mat_to_scipy(dSbus_dm1), mat_to_scipy(dSf_dm1), mat_to_scipy(dSt_dm1)

        # (dSbus_dm1, dSf_dm1, dSt_dm1,
        #  dSbus_dtau1, dSf_dtau1, dSt_dtau1) = compute_branch_power_derivatives(all_tap_m=nc.branch_data.tap_module,
        #                                                                        all_tap_tau=nc.branch_data.tap_angle,
        #                                                                        V=nc.Vbus,
        #                                                                        k_m=m_idx,
        #                                                                        k_tau=np.empty(0, dtype=int),
        #                                                                        Cf=nc.Cf,
        #                                                                        Ct=nc.Ct,
        #                                                                        F=nc.F,
        #                                                                        T=nc.T,
        #                                                                        R=nc.branch_data.R,
        #                                                                        X=nc.branch_data.X)

        # dSbus_dm1, dSf_dm1, dSt_dm1 = mdiff.dS_dm_matpower(V=nc.Vbus,
        #                                                    Cf=nc.Cf,
        #                                                    Ct=nc.Ct,
        #                                                    R=nc.branch_data.R,
        #                                                    X=nc.branch_data.X,
        #                                                    B=nc.branch_data.B,
        #                                                    Beq=nc.branch_data.Beq,
        #                                                    k2=nc.branch_data.k,
        #                                                    m=nc.branch_data.tap_module,
        #                                                    tau=nc.branch_data.tap_angle)

        dSbus_dm2 = cscdiff.dSbus_dm_csc(
            nbus=nc.nbus,
            bus_indices=bus_idx,
            m_indices=m_idx,
            F=nc.passive_branch_data.F,
            T=nc.passive_branch_data.T,
            Ys=Ys,
            Bc=nc.passive_branch_data.B,
            tap=nc.active_branch_data.tap,
            tap_module=nc.active_branch_data.tap_module,
            V=nc.bus_data.Vbus
        )
        dSbus_dm3 = dSbus_dm1[bus_idx, :]
        assert np.allclose(dSbus_dm3.toarray(), dSbus_dm2.toarray())

        dSf_dm2 = cscdiff.dSf_dm_csc(
            nbr=nc.nbr,
            sf_indices=sf_idx,
            m_indices=m_idx,
            F=nc.passive_branch_data.F,
            T=nc.passive_branch_data.T,
            Ys=Ys,
            Bc=nc.passive_branch_data.B,
            tap=nc.active_branch_data.tap,
            tap_module=nc.active_branch_data.tap_module,
            V=nc.bus_data.Vbus
        )
        dSf_dm3 = dSf_dm1[sf_idx, :]
        assert np.allclose(dSf_dm3.toarray(), dSf_dm2.toarray())

        dSt_dm2 = cscdiff.dSt_dm_csc(
            nbr=nc.nbr,
            st_indices=sf_idx,
            m_indices=m_idx,
            F=nc.passive_branch_data.F,
            T=nc.passive_branch_data.T,
            Ys=Ys,
            tap=nc.active_branch_data.tap,
            tap_module=nc.active_branch_data.tap_module,
            V=nc.bus_data.Vbus
        )
        dSt_dm3 = dSt_dm1[sf_idx, :]

        assert np.allclose(dSt_dm3.toarray(), dSt_dm2.toarray())


def test_beq_derivatives() -> None:
    """

    :return:
    """
    # fname = os.path.join("data", "grids", "fubm_case_57_14_2MTDC_ctrls.gridcal")
    fname = os.path.join("data", "grids", "RAW", "IEEE 14 bus.raw")
    grid = gce.open_file(filename=fname)
    nc = gce.compile_numerical_circuit_at(grid)

    Ys = 1.0 / (nc.passive_branch_data.R + 1j * nc.passive_branch_data.X)

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
        m_idx = dta["br_idx"]
        bus_idx = dta["bus_idx"]
        sf_idx = dta["sf_idx"]

        dSbus_dbeq1, dSf_dbeq1, dSt_dbeq1 = cscdiff.derivatives_Beq_csc_numba(
            nbus=nc.nbus,
            nbr=nc.nbr,
            iBeqx=m_idx,
            F=nc.passive_branch_data.F,
            kconv=np.ones(nc.nbr),
            tap_module=nc.active_branch_data.tap_module,
            V=nc.bus_data.Vbus
        )
        dSbus_dbeq1, dSf_dbeq1, dSt_dbeq1 = mat_to_scipy(dSbus_dbeq1), mat_to_scipy(dSf_dbeq1), mat_to_scipy(dSt_dbeq1)

        # dSbus_dbeq1, dSf_dbeq1, dSt_dbeq1 = mdiff.dS_dbeq_matpower(V=nc.Vbus,
        #                                                            Cf=nc.Cf,
        #                                                            Ct=nc.Ct,
        #                                                            k2=nc.branch_data.k,
        #                                                            m=nc.branch_data.tap_module)

        dSbus_dbeq2 = cscdiff.dSbus_dbeq_csc(nbus=nc.nbus,
                                             bus_indices=bus_idx,
                                             beq_indices=m_idx,
                                             F=nc.passive_branch_data.F,
                                             kconv=np.ones(nc.nbr),
                                             tap_module=nc.active_branch_data.tap_module,
                                             V=nc.bus_data.Vbus)
        dSbus_dbeq3 = dSbus_dbeq1[bus_idx, :]
        assert np.allclose(dSbus_dbeq3.toarray(), dSbus_dbeq2.toarray())

        dSf_dbeq2 = cscdiff.dSf_dbeq_csc(nbr=nc.nbr,
                                         sf_indices=sf_idx,
                                         beq_indices=m_idx,
                                         F=nc.passive_branch_data.F,
                                         kconv=np.ones(nc.nbr),
                                         tap_module=nc.active_branch_data.tap_module,
                                         V=nc.bus_data.Vbus)
        dSf_dbeq3 = dSf_dbeq1[sf_idx, :]
        assert np.allclose(dSf_dbeq3.toarray(), dSf_dbeq2.toarray())

        # dSt_dbeq is zero


def test_jacobian():
    fname = os.path.join("data", "grids", "RAW", "IEEE 14 bus.raw")
    grid = gce.open_file(filename=fname)
    nc = gce.compile_numerical_circuit_at(grid)

    adm = nc.get_admittance_matrices()
    idx = nc.get_simulation_indices()

    idx_dtheta = np.r_[idx.pv, idx.pq, idx.pqv, idx.p]
    idx_dVm = np.r_[idx.pq, idx.p]
    idx_dP = idx_dtheta
    idx_dQ = np.r_[idx.pq, idx.pqv]

    J1 = mdiff.Jacobian(adm.Ybus, nc.bus_data.Vbus, idx_dP, idx_dQ, idx_dtheta, idx_dVm)

    J3 = cscjac.AC_jacobian(adm.Ybus, nc.bus_data.Vbus, idx_dtheta, idx_dVm)

    J2 = cscjac.AC_jacobianVc(adm.Ybus, nc.bus_data.Vbus, idx_dtheta, idx_dVm, idx_dQ)

    ok1 = np.allclose(J1.toarray(), J2.toarray())
    ok2 = np.allclose(J1.toarray(), J3.toarray())
    ok = ok1 and ok2

    if not ok:
        print(f"J1:\n{J1.toarray()}\n")
        print(f"J2:\n{J2.toarray()}\n")
        print(f"ok {ok}")
    assert ok


if __name__ == '__main__':
    # test_branch_derivatives()
    test_tau_derivatives()
    test_m_derivatives()
    test_beq_derivatives()
    # test_jacobian()
