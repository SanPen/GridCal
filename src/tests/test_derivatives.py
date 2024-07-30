# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os
import numpy as np
import GridCalEngine.Simulations.Derivatives.csc_derivatives as cscdiff
import GridCalEngine.Simulations.Derivatives.ac_jacobian as cscjac
import GridCalEngine.Simulations.Derivatives.matpower_derivatives as mdiff
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf_derivatives import compute_branch_power_derivatives
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


def test_tau_derivatives() -> None:
    """

    :return:
    """
    # fname = os.path.join("data", "grids", "fubm_case_57_14_2MTDC_ctrls.gridcal")
    fname = os.path.join("data", "grids", "RAW", "IEEE 14 bus.raw")
    grid = gce.open_file(filename=fname)
    nc = gce.compile_numerical_circuit_at(grid)

    Ys = 1.0 / (nc.branch_data.R + 1j * nc.branch_data.X)

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
         dSbus_dtau1, dSf_dtau1, dSt_dtau1) = compute_branch_power_derivatives(all_tap_m=nc.branch_data.tap_module,
                                                                               all_tap_tau=nc.branch_data.tap_angle,
                                                                               V=nc.Vbus,
                                                                               k_m=np.empty(0, dtype=int),
                                                                               k_tau=tau_idx,
                                                                               Cf=nc.Cf,
                                                                               Ct=nc.Ct,
                                                                               F=nc.F,
                                                                               T=nc.T,
                                                                               R=nc.branch_data.R,
                                                                               X=nc.branch_data.X)

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

        dSbus_dtau2 = cscdiff.dSbus_dtau_csc(nbus=nc.nbus,
                                             bus_indices=bus_idx,
                                             tau_indices=tau_idx,
                                             F=nc.F,
                                             T=nc.T,
                                             Ys=Ys,
                                             kconv=nc.branch_data.k,
                                             tap=nc.branch_data.tap,
                                             V=nc.Vbus)

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
                                         F=nc.F,
                                         T=nc.T,
                                         Ys=Ys,
                                         kconv=nc.branch_data.k,
                                         tap=nc.branch_data.tap,
                                         V=nc.Vbus)

        dSf_dtau3 = dSf_dtau1[sf_idx, :]

        # print(f"dSf_dtau1 (matpower):\n {dSf_dtau1.real.toarray()}")
        # print(f"dSf_dtau3 (matpower):\n {dSf_dtau3.real.toarray()}")
        # print(f"dSf_dtau2 (new):\n {dSf_dtau2.real.toarray()}")
        ok2 = np.allclose(dSf_dtau3.toarray(), dSf_dtau2.toarray())
        assert ok2

        # check_dSt_dtau(dSt_dtau1, sf_idx, br_idx, Ys, nc)

        dSt_dtau2 = cscdiff.dSt_dtau_csc(nbr=nc.nbr,
                                         sf_indices=sf_idx,
                                         tau_indices=tau_idx,
                                         F=nc.F,
                                         T=nc.T,
                                         Ys=Ys,
                                         kconv=nc.branch_data.k,
                                         tap=nc.branch_data.tap,
                                         V=nc.Vbus)

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

    Ys = 1.0 / (nc.branch_data.R + 1j * nc.branch_data.X)

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

        dSbus_dm1, dSf_dm1, dSt_dm1 = cscdiff.derivatives_ma_csc_numba(nbus=nc.nbus,
                                                                       nbr=nc.nbr,
                                                                       iXxma=m_idx,
                                                                       F=nc.F,
                                                                       T=nc.T,
                                                                       Ys=Ys,
                                                                       kconv=nc.branch_data.k,
                                                                       tap=nc.branch_data.tap,
                                                                       tap_module=nc.branch_data.tap_module,
                                                                       Bc=nc.branch_data.B,
                                                                       Beq=nc.branch_data.Beq,
                                                                       V=nc.Vbus)
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

        dSbus_dm2 = cscdiff.dSbus_dm_csc(nbus=nc.nbus,
                                         bus_indices=bus_idx,
                                         m_indices=m_idx,
                                         F=nc.F,
                                         T=nc.T,
                                         Ys=Ys,
                                         Bc=nc.branch_data.B,
                                         Beq=nc.branch_data.Beq,
                                         kconv=nc.branch_data.k,
                                         tap=nc.branch_data.tap,
                                         tap_module=nc.branch_data.tap_module,
                                         V=nc.Vbus)
        dSbus_dm3 = dSbus_dm1[bus_idx, :]
        assert np.allclose(dSbus_dm3.toarray(), dSbus_dm2.toarray())

        dSf_dm2 = cscdiff.dSf_dm_csc(nbr=nc.nbr,
                                     sf_indices=sf_idx,
                                     m_indices=m_idx,
                                     F=nc.F,
                                     T=nc.T,
                                     Ys=Ys,
                                     Bc=nc.branch_data.B,
                                     Beq=nc.branch_data.Beq,
                                     kconv=nc.branch_data.k,
                                     tap=nc.branch_data.tap,
                                     tap_module=nc.branch_data.tap_module,
                                     V=nc.Vbus)
        dSf_dm3 = dSf_dm1[sf_idx, :]
        assert np.allclose(dSf_dm3.toarray(), dSf_dm2.toarray())

        dSt_dm2 = cscdiff.dSt_dm_csc(nbr=nc.nbr,
                                     sf_indices=sf_idx,
                                     m_indices=m_idx,
                                     F=nc.F,
                                     T=nc.T,
                                     Ys=Ys,
                                     kconv=nc.branch_data.k,
                                     tap=nc.branch_data.tap,
                                     tap_module=nc.branch_data.tap_module,
                                     V=nc.Vbus)
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

    Ys = 1.0 / (nc.branch_data.R + 1j * nc.branch_data.X)

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

        dSbus_dbeq1, dSf_dbeq1, dSt_dbeq1 = cscdiff.derivatives_Beq_csc_numba(nbus=nc.nbus,
                                                                              nbr=nc.nbr,
                                                                              iBeqx=m_idx,
                                                                              F=nc.F,
                                                                              kconv=nc.branch_data.k,
                                                                              tap_module=nc.branch_data.tap_module,
                                                                              V=nc.Vbus)
        dSbus_dbeq1, dSf_dbeq1, dSt_dbeq1 = mat_to_scipy(dSbus_dbeq1), mat_to_scipy(dSf_dbeq1), mat_to_scipy(dSt_dbeq1)

        # dSbus_dbeq1, dSf_dbeq1, dSt_dbeq1 = mdiff.dS_dbeq_matpower(V=nc.Vbus,
        #                                                            Cf=nc.Cf,
        #                                                            Ct=nc.Ct,
        #                                                            k2=nc.branch_data.k,
        #                                                            m=nc.branch_data.tap_module)

        dSbus_dbeq2 = cscdiff.dSbus_dbeq_csc(nbus=nc.nbus,
                                             bus_indices=bus_idx,
                                             beq_indices=m_idx,
                                             F=nc.F,
                                             kconv=nc.branch_data.k,
                                             tap_module=nc.branch_data.tap_module,
                                             V=nc.Vbus)
        dSbus_dbeq3 = dSbus_dbeq1[bus_idx, :]
        assert np.allclose(dSbus_dbeq3.toarray(), dSbus_dbeq2.toarray())

        dSf_dbeq2 = cscdiff.dSf_dbeq_csc(nbr=nc.nbr,
                                         sf_indices=sf_idx,
                                         beq_indices=m_idx,
                                         F=nc.F,
                                         kconv=nc.branch_data.k,
                                         tap_module=nc.branch_data.tap_module,
                                         V=nc.Vbus)
        dSf_dbeq3 = dSf_dbeq1[sf_idx, :]
        assert np.allclose(dSf_dbeq3.toarray(), dSf_dbeq2.toarray())

        # dSt_dbeq is zero


def test_jacobian():
    fname = os.path.join("data", "grids", "RAW", "IEEE 14 bus.raw")
    grid = gce.open_file(filename=fname)
    nc = gce.compile_numerical_circuit_at(grid)

    idx_dtheta = np.r_[nc.pv, nc.pq, nc.pqv, nc.p]
    idx_dVm = np.r_[nc.pq, nc.p]
    idx_dP = idx_dtheta
    idx_dQ = np.r_[nc.pq, nc.pqv]

    J1 = mdiff.Jacobian(nc.Ybus, nc.Vbus, idx_dP, idx_dQ, idx_dtheta, idx_dVm)

    J3 = cscjac.AC_jacobian(nc.Ybus, nc.Vbus, idx_dtheta, idx_dVm)

    J2 = cscjac.AC_jacobianVc(nc.Ybus, nc.Vbus, idx_dtheta, idx_dVm, idx_dQ)

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
