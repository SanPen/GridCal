# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os
import time
from scipy.sparse import diags
from VeraGridEngine.api import *
from VeraGridEngine.Topology.admittance_matrices import compute_admittances, compute_admittances_fast


def __check__(fname):
    """
    Check that Ybus = Yseries + Yshunt
    :param fname: name of the VeraGrid file
    :return: True if succeeded, exception otherwise
    """
    # load the file
    main_circuit = FileOpen(fname).open()

    # compile the data
    numerical_circuit = compile_numerical_circuit_at(main_circuit, apply_temperature=False)

    # split into the possible islands
    islands = numerical_circuit.split_into_islands()

    # check the consistency of each island
    for island in islands:
        adm = island.get_admittance_matrices()
        adms = island.get_series_admittance_matrices()

        assert ((adm.Ybus - (adms.Yseries + diags(adms.Yshunt))).data < 1e-9).all()

    return True


def test1():
    """
    Check that Ybus was correctly decomposed
    :return: True if passed
    """
    fname = os.path.join('data', 'grids', 'IEEE 30 Bus with storage.xlsx')
    res = __check__(fname)
    return res


def test2():
    """
    Check that Ybus was correctly decomposed
    :return: True if passed
    """
    fname = os.path.join('data', 'grids', 'Brazil11_loading05.gridcal')
    res = __check__(fname)
    return res


def test3():
    """
    Check that Ybus was correctly decomposed
    :return: True if passed
    """
    fname = os.path.join('data', 'grids', "Iwamoto's 11 Bus.xlsx")
    res = __check__(fname)
    return res


def test_fast_admittance():
    """

    :return:
    """
    # path = os.path.join('data', 'grids', "case14.m")

    profiling = list()

    # run this one to compile the stuff
    files = [
        "case5.m",
        "case14.m",
        "case18.m",
        "case39.m",
        "case57.m",
        "case69.m",
        "case60nordic.m",
        "case118.m",
        "case89pegase.m",
        "case2868rte.m",
        "case6515rte.m",
        "case9241pegase.m",
        "case_ACTIVSg2000.m",
        "case_ACTIVSg500.m",
    ]

    # run this one to compile the stuff
    folder = os.path.join("data", "grids", "Matpower")
    for file in files:
        if file.endswith(".m"):
            print(file, "...", end="")
            path = os.path.join(folder, file)

            # load the file
            grid = FileOpen(path).open()

            print(file, " ", end="")

            # compile the data
            nc = compile_numerical_circuit_at(grid, apply_temperature=False)

            Yshunt_bus = nc.get_Yshunt_bus_pu()
            m = nc.active_branch_data.tap_module
            tau = nc.active_branch_data.tap_angle

            t0 = time.time()
            adm = compute_admittances(
                R=nc.passive_branch_data.R,
                X=nc.passive_branch_data.X,
                G=nc.passive_branch_data.G,
                B=nc.passive_branch_data.B,
                tap_module=m,
                vtap_f=nc.passive_branch_data.virtual_tap_f,
                vtap_t=nc.passive_branch_data.virtual_tap_t,
                tap_angle=tau,
                Cf=nc.passive_branch_data.Cf,
                Ct=nc.passive_branch_data.Ct,
                Yshunt_bus=Yshunt_bus,
                conn=nc.passive_branch_data.conn,
                seq=1,
                add_windings_phase=False
            )

            t1 = time.time()

            adm2 = compute_admittances_fast(
                nbus=nc.bus_data.nbus,
                R=nc.passive_branch_data.R,
                X=nc.passive_branch_data.X,
                G=nc.passive_branch_data.G,
                B=nc.passive_branch_data.B,
                tap_module=m,
                vtap_f=nc.passive_branch_data.virtual_tap_f,
                vtap_t=nc.passive_branch_data.virtual_tap_t,
                tap_angle=tau,
                F=nc.passive_branch_data.F,
                T=nc.passive_branch_data.T,
                Yshunt_bus=Yshunt_bus,
            )

            t2 = time.time()

            t_old = t1 - t0
            t_new = t2 - t1
            print(t_old, t_new)
            profiling.append((file, t_old, t_new))

            assert adm == adm2

    df = pd.DataFrame(data=profiling, columns=("name", "normal (s)", "fast (s)"))
    print(df)


def test_fast_admittance_update():
    """

    :return:
    """
    files = [
        "case5.m",
        "case14.m",
        "case18.m",
        "case39.m",
        "case57.m",
        "case69.m",
        "case60nordic.m",
        "case118.m",
        "case89pegase.m",
        "case2868rte.m",
        "case6515rte.m",
        "case9241pegase.m",
        "case_ACTIVSg2000.m",
        "case_ACTIVSg500.m",
    ]

    # run this one to compile the stuff
    folder = os.path.join("data", "grids", "Matpower")
    for file in files:
        if file.endswith(".m"):
            print(file, "...", end="")
            path = os.path.join(folder, file)

            # load the file
            grid = FileOpen(path).open()

            # compile the data
            nc = compile_numerical_circuit_at(grid, apply_temperature=False)

            Yshunt_bus = nc.get_Yshunt_bus_pu()
            m = nc.active_branch_data.tap_module
            tau = nc.active_branch_data.tap_angle

            adm0 = compute_admittances_fast(
                nbus=nc.bus_data.nbus,
                R=nc.passive_branch_data.R,
                X=nc.passive_branch_data.X,
                G=nc.passive_branch_data.G,
                B=nc.passive_branch_data.B,
                tap_module=m,
                vtap_f=nc.passive_branch_data.virtual_tap_f,
                vtap_t=nc.passive_branch_data.virtual_tap_t,
                tap_angle=tau,
                F=nc.passive_branch_data.F,
                T=nc.passive_branch_data.T,
                Yshunt_bus=Yshunt_bus,
            )

            # modify the indices
            m_idices = np.where(m != 1.0)[0]
            tau_idices = np.where(tau != 0.0)[0]
            m2 = m.copy()
            tau2 = tau.copy()
            m2[m_idices] *= 0.95
            tau2[tau_idices] *= 1.15
            br_idx = np.unique(np.r_[m_idices, tau_idices])

            adm = compute_admittances_fast(
                nbus=nc.bus_data.nbus,
                R=nc.passive_branch_data.R,
                X=nc.passive_branch_data.X,
                G=nc.passive_branch_data.G,
                B=nc.passive_branch_data.B,
                tap_module=m2,
                vtap_f=nc.passive_branch_data.virtual_tap_f,
                vtap_t=nc.passive_branch_data.virtual_tap_t,
                tap_angle=tau2,
                F=nc.passive_branch_data.F,
                T=nc.passive_branch_data.T,
                Yshunt_bus=Yshunt_bus,
            )

            adm2 = adm0.copy()
            adm2.initialize_update()
            adm2.modify_taps_fast(idx=br_idx,
                                  tap_module=m2[br_idx],
                                  tap_angle=tau2[br_idx])

            assert adm == adm2
            print("ok")




if __name__ == '__main__':
    test_fast_admittance_update()
