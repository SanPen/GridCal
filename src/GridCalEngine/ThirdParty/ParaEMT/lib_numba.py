import numpy as np
import scipy.sparse as sp
import numba


@numba.jit(nopython=True, nogil=True, boundscheck=False, parallel=False)
def numba_set_coo(
        rows,
        cols,
        data,
        idx,
        rval,
        cval,
        val,
):
    """

    :param rows:
    :param cols:
    :param data:
    :param idx:
    :param rval:
    :param cval:
    :param val:
    :return:
    """
    rows[idx] = rval
    cols[idx] = cval
    data[idx] = val
    return


@numba.jit(nopython=True, nogil=True, boundscheck=False, parallel=False)
def numba_InitNet(
        # pfd
        basemva,
        ws,
        bus_num,
        bus_basekV,
        bus_Vm,
        bus_Va,
        gen_bus,
        gen_MW,
        gen_Mvar,
        line_from,
        line_to,
        line_RX,
        line_chg,
        xfmr_from,
        xfmr_to,
        xfmr_RX,
        load_bus,
        load_MW,
        load_Mvar,
        shnt_bus,
        shnt_gb,
        shnt_sw_bus,
        shnt_sw_gb,
        # OTHER
        ts,
        loadmodel_option,
):
    """

    :param basemva:
    :param ws:
    :param bus_num:
    :param bus_basekV:
    :param bus_Vm:
    :param bus_Va:
    :param gen_bus:
    :param gen_MW:
    :param gen_Mvar:
    :param line_from:
    :param line_to:
    :param line_RX:
    :param line_chg:
    :param xfmr_from:
    :param xfmr_to:
    :param xfmr_RX:
    :param load_bus:
    :param load_MW:
    :param load_Mvar:
    :param shnt_bus:
    :param shnt_gb:
    :param shnt_sw_bus:
    :param shnt_sw_gb:
    :param ts:
    :param loadmodel_option:
    :return:
    """
    nbus = len(bus_num)
    ngen = len(gen_bus)

    Init_net_VbaseA = np.zeros(nbus)
    Init_net_ZbaseA = np.zeros(nbus)
    Init_net_IbaseA = np.zeros(nbus)
    Init_net_YbaseA = np.zeros(nbus)
    Init_net_StA = np.zeros(nbus, dtype=np.complex128)

    Init_net_Vt = np.zeros(3 * nbus, dtype=np.complex128)
    Init_net_VtA = Init_net_Vt[:nbus]
    Init_net_VtB = Init_net_Vt[nbus:2 * nbus]
    Init_net_VtC = Init_net_Vt[2 * nbus:]

    Init_net_It = np.zeros(ngen, dtype=np.complex128)
    # Init_net_ItA = Init_net_It[:nbus]
    # Init_net_ItB = Init_net_It[nbus:2*nbus]
    # Init_net_ItC = Init_net_It[2*nbus:]

    Init_net_Vtha = np.zeros(ngen)

    # BEGIN FOR LOOP
    for j in range(ngen):
        i = np.where(bus_num == gen_bus[j])[0][0]
        Init_net_Vtha[j] = bus_Va[i]

    # get base
    for i in range(nbus):
        Vbase_temp = bus_basekV[i] / np.sqrt(3.0)
        Zbase_temp = Vbase_temp * Vbase_temp * 3 / basemva
        Ibase_temp = basemva / (3 * Vbase_temp)
        Ybase_temp = 1 / Zbase_temp

        Init_net_VbaseA[i] = Vbase_temp
        Init_net_ZbaseA[i] = Zbase_temp
        Init_net_IbaseA[i] = Ibase_temp
        Init_net_YbaseA[i] = Ybase_temp

        Vt_temp = complex(bus_Vm[i] * np.cos(bus_Va[i]),
                          bus_Vm[i] * np.sin(bus_Va[i])
                          )
        Init_net_VtA[i] = Vt_temp
        Init_net_VtB[i] = Vt_temp * complex(-0.5, -0.5 * np.sqrt(3.0))
        Init_net_VtC[i] = Vt_temp * complex(-0.5, 0.5 * np.sqrt(3.0))

    for i in range(ngen):
        genbus_idx = np.where(bus_num == gen_bus[i])[0][0]

        Vt_temp = complex(bus_Vm[genbus_idx] * np.cos(bus_Va[genbus_idx]),
                          bus_Vm[genbus_idx] * np.sin(bus_Va[genbus_idx])
                          )

        St_temp = complex(gen_MW[i] / basemva, gen_Mvar[i] / basemva)
        Init_net_StA[i] = St_temp
        # vt temp to be defn
        Init_net_It[i] = St_temp.conjugate() / Vt_temp.conjugate()
        pass
    # prepare G and coe matrices
    N1 = nbus
    N2 = nbus * 2
    Init_net_N = nbus * 3
    # Init_net_G0 = np.zeros((Init_net_N, Init_net_N))
    # Init_net_G0 = sp.dok_matrix((Init_net_N, Init_net_N),dtype=float)
    if loadmodel_option == 1:
        nentries = 12 * len(line_from) + 12 * len(xfmr_from) + 3 * len(load_bus) + 3 * len(shnt_bus) + 3 * len(
            shnt_sw_bus)
    else:
        nentries = 12 * len(line_from) + 12 * len(xfmr_from) + 3 * len(shnt_bus) + 3 * len(shnt_sw_bus)
    G0_rows = np.zeros(nentries, dtype=np.int64)
    G0_cols = np.zeros(nentries, dtype=np.int64)
    G0_data = np.zeros(nentries, dtype=np.float64)

    for i in range(len(shnt_sw_bus)):
        j = len(shnt_sw_bus) - i - 1
        if np.abs(shnt_sw_gb[j]) < 1e-15:
            shnt_sw_gb = np.delete(shnt_sw_gb, j)
            shnt_sw_bus = np.delete(shnt_sw_bus, j)

    if loadmodel_option == 1:
        nbranch = 9 * len(line_from) + 3 * len(xfmr_from) + 3 * len(load_bus) + 3 * len(shnt_bus) + 3 * len(shnt_sw_bus)
    else:
        nbranch = 9 * len(line_from) + 3 * len(xfmr_from) + 3 * len(shnt_bus) + 3 * len(shnt_sw_bus)
    Init_net_coe0 = np.zeros((nbranch, 9), dtype=np.complex128)

    damptrap = 1

    # BEGIN FOR LOOP
    # PI-model line
    for i in range(len(line_from)):
        Frombus = line_from[i]
        Tobus = line_to[i]
        Fidx = np.where(bus_num == Frombus)[0][0]
        Tidx = np.where(bus_num == Tobus)[0][0]
        R = np.real(line_RX[i])

        X = np.imag(line_RX[i])

        if X > 0:
            L = X / ws
            Rp = damptrap * (20.0 / 3.0 * 2.0 * L / ts)
            Rp_inv = 1.0 / Rp

            Req = (1 + R * (ts / 2.0 / L + Rp_inv)) / (ts / 2.0 / L + Rp_inv)
            icf = (1 - R * (ts / 2.0 / L - Rp_inv)) / (1 + R * (ts / 2.0 / L + Rp_inv))
            Gv1 = (ts / 2.0 / L - Rp_inv) / (1 + R * (ts / 2.0 / L + Rp_inv))
        elif X < 0:
            CL = - 1 / X / ws
            Req = R + ts / 2 / CL
            icf = (2 * R * CL - ts) / (2 * R * CL + ts)

        idx = 12 * i
        C = line_chg[i] / 2 / ws
        if C == 0:
            Rs = np.inf  # float('inf')
        else:
            Rs = 0.15 * ts / 2.0 / C
            Rc = ts / 2.0 / C
        Rs = Rs / damptrap

        if Rs == np.inf:
            numba_set_coo(G0_rows, G0_cols, G0_data, idx, Fidx, Fidx, 1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 1, Tidx, Tidx, 1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 2, Fidx, Tidx, -1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 3, Tidx, Fidx, -1 / Req)

            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 4, Fidx + N1, Fidx + N1, 1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 5, Tidx + N1, Tidx + N1, 1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 6, Fidx + N1, Tidx + N1, -1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 7, Tidx + N1, Fidx + N1, -1 / Req)

            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 8, Fidx + N2, Fidx + N2, 1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 9, Tidx + N2, Tidx + N2, 1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 10, Fidx + N2, Tidx + N2, -1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 11, Tidx + N2, Fidx + N2, -1 / Req)
        else:
            numba_set_coo(G0_rows, G0_cols, G0_data, idx, Fidx, Fidx, 1 / Req + 1 / (Rs + Rc))
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 1, Tidx, Tidx, 1 / Req + 1 / (Rs + Rc))
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 2, Fidx, Tidx, -1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 3, Tidx, Fidx, -1 / Req)

            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 4, Fidx + N1, Fidx + N1, 1 / Req + 1 / (Rs + Rc))
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 5, Tidx + N1, Tidx + N1, 1 / Req + 1 / (Rs + Rc))
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 6, Fidx + N1, Tidx + N1, -1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 7, Tidx + N1, Fidx + N1, -1 / Req)

            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 8, Fidx + N2, Fidx + N2, 1 / Req + 1 / (Rs + Rc))
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 9, Tidx + N2, Tidx + N2, 1 / Req + 1 / (Rs + Rc))
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 10, Fidx + N2, Tidx + N2, -1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 11, Tidx + N2, Fidx + N2, -1 / Req)

        # R-L branch
        iA_temp = (Init_net_Vt[Fidx] - Init_net_Vt[Tidx]) / complex(R, X)
        iB_temp = (Init_net_Vt[Fidx + N1] - Init_net_Vt[Tidx + N1]) / complex(R, X)
        iC_temp = (Init_net_Vt[Fidx + N2] - Init_net_Vt[Tidx + N2]) / complex(R, X)

        coe_idx = 9 * i
        Init_net_coe0[coe_idx, :] = np.array([Fidx, Tidx, Req, icf, Gv1, R, X, 0.0, iA_temp])
        Init_net_coe0[coe_idx + 1, :] = np.array([Fidx + N1, Tidx + N1, Req, icf, Gv1, R, X, 0.0, iB_temp])
        Init_net_coe0[coe_idx + 2, :] = np.array([Fidx + N2, Tidx + N2, Req, icf, Gv1, R, X, 0.0, iC_temp])

        # C - from branch
        iA_temp = Init_net_Vt[Fidx] * complex(0, ws * C)
        iB_temp = Init_net_Vt[Fidx + N1] * complex(0, ws * C)
        iC_temp = Init_net_Vt[Fidx + N2] * complex(0, ws * C)
        infnum = 1e10
        if Rs == np.inf:
            Init_net_coe0[coe_idx + 3, :] = np.array([Fidx, -1, infnum,
                                                      -1,
                                                      0.0,
                                                      0.0, 0.0, C, iA_temp,
                                                      ])
            Init_net_coe0[coe_idx + 4, :] = np.array([Fidx + N1, -1, infnum,
                                                      -1,
                                                      0.0,
                                                      0.0, 0.0, C, iB_temp,
                                                      ])
            Init_net_coe0[coe_idx + 5, :] = np.array([Fidx + N2, -1, infnum,
                                                      -1,
                                                      0.0,
                                                      0.0, 0.0, C, iC_temp,
                                                      ])
        else:
            Init_net_coe0[coe_idx + 3, :] = np.array([Fidx, -1, Rs + Rc,
                                                      -(Rc - Rs) / (Rc + Rs),
                                                      -1.0 / (Rc + Rs),
                                                      0.0, 0.0, C, iA_temp,
                                                      ])
            Init_net_coe0[coe_idx + 4, :] = np.array([Fidx + N1, -1, Rs + Rc,
                                                      -(Rc - Rs) / (Rc + Rs),
                                                      -1.0 / (Rc + Rs),
                                                      0.0, 0.0, C, iB_temp,
                                                      ])
            Init_net_coe0[coe_idx + 5, :] = np.array([Fidx + N2, -1, Rs + Rc,
                                                      -(Rc - Rs) / (Rc + Rs),
                                                      -1.0 / (Rc + Rs),
                                                      0.0, 0.0, C, iC_temp,
                                                      ])
        # C - to branch
        iA_temp = Init_net_Vt[Tidx] * complex(0, ws * C)
        iB_temp = Init_net_Vt[Tidx + N1] * complex(0, ws * C)
        iC_temp = Init_net_Vt[Tidx + N2] * complex(0, ws * C)
        if Rs == np.inf:
            Init_net_coe0[coe_idx + 6, :] = np.array([Tidx, -1, infnum,
                                                      -1,
                                                      0.0,
                                                      0.0, 0.0, C, iA_temp,
                                                      ])
            Init_net_coe0[coe_idx + 7, :] = np.array([Tidx + N1, -1, infnum,
                                                      -1,
                                                      -1.0 / (Rc + Rs),
                                                      0.0, 0.0, C, iB_temp,
                                                      ])
            Init_net_coe0[coe_idx + 8, :] = np.array([Tidx + N2, -1, infnum,
                                                      -1,
                                                      0.0,
                                                      0.0, 0.0, C, iC_temp,
                                                      ])
        else:
            Init_net_coe0[coe_idx + 6, :] = np.array([Tidx, -1, Rs + Rc,
                                                      -(Rc - Rs) / (Rc + Rs),
                                                      -1.0 / (Rc + Rs),
                                                      0.0, 0.0, C, iA_temp,
                                                      ])
            Init_net_coe0[coe_idx + 7, :] = np.array([Tidx + N1, -1, Rs + Rc,
                                                      -(Rc - Rs) / (Rc + Rs),
                                                      -1.0 / (Rc + Rs),
                                                      0.0, 0.0, C, iB_temp,
                                                      ])
            Init_net_coe0[coe_idx + 8, :] = np.array([Tidx + N2, -1, Rs + Rc,
                                                      -(Rc - Rs) / (Rc + Rs),
                                                      -1.0 / (Rc + Rs),
                                                      0.0, 0.0, C, iC_temp,
                                                      ])

    # R-L model xfmr
    for i in range(len(xfmr_from)):
        Frombus = xfmr_from[i]
        Tobus = xfmr_to[i]
        Fidx = np.where(bus_num == Frombus)[0][0]
        Tidx = np.where(bus_num == Tobus)[0][0]
        R = np.real(xfmr_RX[i])

        L = np.imag(xfmr_RX[i]) / ws
        Rp = damptrap * (20.0 / 3.0 * 2.0 * L / ts)

        Req = (1 + R * ts / 2.0 / L) / (ts / 2.0 / L)
        icf = (1 - R * (ts / 2.0 / L)) / (1 + R * (ts / 2.0 / L))
        Gv1 = (ts / 2.0 / L) / (1 + R * (ts / 2.0 / L))

        idx = 12 * len(line_from) + 12 * i
        numba_set_coo(G0_rows, G0_cols, G0_data, idx, Fidx, Fidx, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 1, Tidx, Tidx, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 2, Fidx, Tidx, -1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 3, Tidx, Fidx, -1 / Req)

        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 4, Fidx + N1, Fidx + N1, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 5, Tidx + N1, Tidx + N1, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 6, Fidx + N1, Tidx + N1, -1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 7, Tidx + N1, Fidx + N1, -1 / Req)

        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 8, Fidx + N2, Fidx + N2, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 9, Tidx + N2, Tidx + N2, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 10, Fidx + N2, Tidx + N2, -1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 11, Tidx + N2, Fidx + N2, -1 / Req)

        # R-L branch
        iA_temp = (Init_net_Vt[Fidx] - Init_net_Vt[Tidx]) / complex(R, ws * L)
        iB_temp = (Init_net_Vt[Fidx + N1] - Init_net_Vt[Tidx + N1]) / complex(R, ws * L)
        iC_temp = (Init_net_Vt[Fidx + N2] - Init_net_Vt[Tidx + N2]) / complex(R, ws * L)

        coe_idx = 9 * len(line_from) + 3 * i
        Init_net_coe0[coe_idx, :] = np.array([Fidx, Tidx, Req, icf,
                                              Gv1, R, L, 0.0, iA_temp])
        Init_net_coe0[coe_idx + 1, :] = np.array([Fidx + N1, Tidx + N1, Req, icf,
                                                  Gv1, R, L, 0.0, iB_temp])
        Init_net_coe0[coe_idx + 2, :] = np.array([Fidx + N2, Tidx + N2, Req, icf,
                                                  Gv1, R, L, 0.0, iC_temp])

    # const Z load model
    if loadmodel_option == 1:
        for i in range(len(load_bus)):
            Frombus = load_bus[i]
            Fidx = np.where(bus_num == Frombus)[0][0]
            Z = abs(Init_net_Vt[Fidx]) * abs(Init_net_Vt[Fidx]) / (complex(load_MW[i], - load_Mvar[i]) / basemva)
            Y = 1.0 / Z
            R = np.real(Z)
            X = np.imag(Z)

            if X > 0:
                L = X / ws
                Rp = damptrap * (20.0 / 3.0 * 2.0 * L / ts)
                Rp_inv = 1.0 / Rp

                C = 0.0
                Req = (1 + R * (ts / 2.0 / L + Rp_inv)) / (ts / 2.0 / L + Rp_inv)
                icf = (1 - R * (ts / 2.0 / L - Rp_inv)) / (1 + R * (ts / 2.0 / L + Rp_inv))
                Gv1 = (ts / 2.0 / L - Rp_inv) / (1 + R * (ts / 2.0 / L + Rp_inv))

            elif X < 0:
                L = 0
                R = 1.0 / np.real(Y)
                C = np.imag(Y) / ws
                Rs = 0.15 * ts / 2.0 / C * 0.001

                Req = 1 / (1 / R + 1 / (Rs + ts / 2.0 / C))
                icf = - (ts / 2.0 / C - Rs) / (ts / 2.0 / C + Rs)
                Gv1 = 1 / R - 1 / ((ts / 2.0 / C) + Rs)
            else:
                L = 0.0
                C = 0.0
                Req = R
                icf = 0.0
                Gv1 = 0.0

            idx = 12 * len(line_from) + 12 * len(xfmr_from) + 3 * i
            numba_set_coo(G0_rows, G0_cols, G0_data, idx, Fidx, Fidx, 1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 1, Fidx + N1, Fidx + N1, 1 / Req)
            numba_set_coo(G0_rows, G0_cols, G0_data, idx + 2, Fidx + N2, Fidx + N2, 1 / Req)

            # shnt branch
            iA_temp = Init_net_Vt[Fidx] / Z
            iB_temp = Init_net_Vt[Fidx + N1] / Z
            iC_temp = Init_net_Vt[Fidx + N2] / Z

            coe_idx = 9 * len(line_from) + 3 * len(xfmr_from) + 3 * i
            Init_net_coe0[coe_idx, :] = np.array([Fidx, -1, Req, icf, Gv1, R, L, C, iA_temp])
            Init_net_coe0[coe_idx + 1, :] = np.array([Fidx + N1, -1, Req, icf, Gv1, R, L, C, iB_temp])
            Init_net_coe0[coe_idx + 2, :] = np.array([Fidx + N2, -1, Req, icf, Gv1, R, L, C, iC_temp])
        else:
            pass

    # shunt model
    for i in range(len(shnt_bus)):
        Frombus = shnt_bus[i]
        Fidx = np.where(bus_num == Frombus)[0][0]

        Y = np.conjugate(shnt_gb[i]) / basemva
        C = - np.imag(Y) / ws
        Rs = 0.15 * ts / 2.0 / C / damptrap

        Req = Rs + ts / 2.0 / C
        icf = - (ts / 2.0 / C - Rs) / (ts / 2.0 / C + Rs)
        Gv1 = - 1.0 / (ts / 2.0 / C + Rs)

        if loadmodel_option == 1:
            idx = 12 * len(line_from) + 12 * len(xfmr_from) + 3 * len(load_bus) + 3 * i
        else:
            idx = 12 * len(line_from) + 12 * len(xfmr_from) + 3 * i
        numba_set_coo(G0_rows, G0_cols, G0_data, idx, Fidx, Fidx, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 1, Fidx + N1, Fidx + N1, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 2, Fidx + N2, Fidx + N2, 1 / Req)

        # shnt branch
        iA_temp = Init_net_Vt[Fidx] * complex(0, ws * C)
        iB_temp = Init_net_Vt[Fidx + N1] * complex(0, ws * C)
        iC_temp = Init_net_Vt[Fidx + N2] * complex(0, ws * C)

        if loadmodel_option == 1:
            coe_idx = 9 * len(line_from) + 3 * len(xfmr_from) + 3 * len(load_bus) + 3 * i
        else:
            coe_idx = 9 * len(line_from) + 3 * len(xfmr_from) + 3 * i
        Init_net_coe0[coe_idx, :] = np.array([Fidx, -1, Req, icf, Gv1, 0.0, 0.0, C, iA_temp])
        Init_net_coe0[coe_idx + 1, :] = np.array([Fidx + N1, -1, Req, icf, Gv1, 0.0, 0.0, C, iB_temp])
        Init_net_coe0[coe_idx + 2, :] = np.array([Fidx + N2, -1, Req, icf, Gv1, 0.0, 0.0, C, iC_temp])

    # switched shunt model
    for i in range(len(shnt_sw_bus)):
        Frombus = shnt_sw_bus[i]
        Fidx = np.where(bus_num == Frombus)[0][0]

        Y = np.conjugate(- shnt_sw_gb[i]) / basemva / bus_Vm[Fidx] / bus_Vm[Fidx]
        C = - np.imag(Y) / ws
        Rs = 0.15 * ts / 2.0 / C / damptrap

        Req = Rs + ts / 2.0 / C
        icf = - (ts / 2.0 / C - Rs) / (ts / 2.0 / C + Rs)
        Gv1 = - 1.0 / (ts / 2.0 / C + Rs)

        if loadmodel_option == 1:
            idx = 12 * len(line_from) + 12 * len(xfmr_from) + 3 * len(load_bus) + 3 * len(shnt_bus) + 3 * i
        else:
            idx = 12 * len(line_from) + 12 * len(xfmr_from) + 3 * len(shnt_bus) + 3 * i
        numba_set_coo(G0_rows, G0_cols, G0_data, idx, Fidx, Fidx, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 1, Fidx + N1, Fidx + N1, 1 / Req)
        numba_set_coo(G0_rows, G0_cols, G0_data, idx + 2, Fidx + N2, Fidx + N2, 1 / Req)

        # switched shnt branch
        iA_temp = Init_net_Vt[Fidx] * complex(0, ws * C)
        iB_temp = Init_net_Vt[Fidx + N1] * complex(0, ws * C)
        iC_temp = Init_net_Vt[Fidx + N2] * complex(0, ws * C)

        if loadmodel_option == 1:
            coe_idx = 9 * len(line_from) + 3 * len(xfmr_from) + 3 * len(load_bus) + 3 * len(shnt_bus) + 3 * i
        else:
            coe_idx = 9 * len(line_from) + 3 * len(xfmr_from) + 3 * len(shnt_bus) + 3 * i
        Init_net_coe0[coe_idx, :] = np.array([Fidx, -1, Req, icf, Gv1, 0.0, 0.0, C, iA_temp])
        Init_net_coe0[coe_idx + 1, :] = np.array([Fidx + N1, -1, Req, icf, Gv1, 0.0, 0.0, C, iB_temp])
        Init_net_coe0[coe_idx + 2, :] = np.array([Fidx + N2, -1, Req, icf, Gv1, 0.0, 0.0, C, iC_temp])

    # calculate pre and his terms of branch current
    Init_net_V = np.real(Init_net_Vt)
    Init_brch_Ipre = np.real(Init_net_coe0[:, 8])
    Init_node_Ihis = np.zeros(Init_net_N)
    Init_brch_Ihis = np.zeros(len(Init_brch_Ipre))

    for i in range(len(Init_brch_Ipre)):
        Fidx = int(Init_net_coe0[i, 0].real)
        Tidx = int(Init_net_coe0[i, 1].real)
        if Tidx == -1:
            if Init_net_coe0[i, 2] == 0:
                continue
            brch_Ihis_temp = Init_net_coe0[i, 3] * Init_brch_Ipre[i] + Init_net_coe0[i, 4] * (Init_net_V[Fidx])
        else:
            brch_Ihis_temp = Init_net_coe0[i, 3] * Init_brch_Ipre[i] + Init_net_coe0[i, 4] * (
                        Init_net_V[Fidx] - Init_net_V[Tidx])
            Init_node_Ihis[Tidx] += brch_Ihis_temp.real

        Init_brch_Ihis[i] = brch_Ihis_temp.real
        Init_node_Ihis[Fidx] -= brch_Ihis_temp.real

    return (Init_net_VbaseA,
            Init_net_ZbaseA,
            Init_net_IbaseA,
            Init_net_YbaseA,
            Init_net_StA,
            Init_net_Vt,
            Init_net_It,
            Init_net_N,
            Init_net_coe0,
            Init_net_V,
            Init_net_Vtha,
            Init_brch_Ipre,
            Init_node_Ihis,
            Init_brch_Ihis,
            G0_rows,
            G0_cols,
            G0_data,
            )


@numba.jit(nopython=True, nogil=True, boundscheck=False, parallel=False)
def numba_predictX(
        # self.<something>
        x_pv_1,
        x_pv_2,
        x_pv_3,
        # pfd
        gen_bus,
        ws,
        # ini
        gen_genrou_odr,
        exc_sexs_xi_st,
        exc_sexs_odr,
        # ts
        ts,
        # xlen
        xlen
):
    ngen = len(gen_bus)

    neg_id = np.zeros(ngen)
    neg_iq = np.zeros(ngen)

    pd_w = np.zeros(ngen)
    pd_id = np.zeros(ngen)
    pd_iq = np.zeros(ngen)
    pd_EFD = np.zeros(ngen)
    pd_u_d = np.zeros(ngen)
    pd_u_q = np.zeros(ngen)
    pd_dt = np.zeros(ngen)

    # POINT 1
    pv_dt_1 = np.zeros(ngen)
    pv_w_1 = np.zeros(ngen)
    pv_id_1 = np.zeros(ngen)
    pv_iq_1 = np.zeros(ngen)
    pv_ifd_1 = np.zeros(ngen)
    pv_i1d_1 = np.zeros(ngen)
    pv_i1q_1 = np.zeros(ngen)
    pv_i2q_1 = np.zeros(ngen)
    pv_psyd_1 = np.zeros(ngen)
    pv_psyq_1 = np.zeros(ngen)
    pv_EFD_1 = np.zeros(ngen)

    point_one_tuple = None
    point_two_tuple = None
    point_three_tuple = None

    for i in numba.prange(ngen):
        idx = i * gen_genrou_odr
        pv_dt_1[i] = x_pv_1[idx + 0]
        pv_w_1[i] = x_pv_1[idx + 1]
        pv_id_1[i] = x_pv_1[idx + 2]
        neg_id[i] = -x_pv_1[idx + 2]
        pv_iq_1[i] = x_pv_1[idx + 3]
        neg_iq[i] = -x_pv_1[idx + 3]
        pv_ifd_1[i] = x_pv_1[idx + 4]
        pv_i1d_1[i] = x_pv_1[idx + 5]
        pv_i1q_1[i] = x_pv_1[idx + 6]
        pv_i2q_1[i] = x_pv_1[idx + 7]
        pv_psyd_1[i] = x_pv_1[idx + 10]
        pv_psyq_1[i] = x_pv_1[idx + 11]

        idx = i * exc_sexs_odr + exc_sexs_xi_st
        pv_EFD_1[i] = x_pv_1[idx + 1]

    pv_u_d_1 = -pv_psyq_1 * pv_w_1 / ws
    pv_u_q_1 = pv_psyd_1 * pv_w_1 / ws
    pv_i_d_1 = np.vstack((neg_id, pv_ifd_1, pv_i1d_1))
    pv_i_q_1 = np.vstack((neg_iq, pv_i1q_1, pv_i2q_1))

    point_one_tuple = (
        pv_dt_1,
        pv_w_1,
        pv_id_1,
        pv_iq_1,
        pv_ifd_1,
        pv_i1d_1,
        pv_i1q_1,
        pv_i2q_1,
        pv_EFD_1,
        pv_psyd_1,
        pv_psyq_1,
        pv_u_d_1,
        pv_u_q_1,
        pv_i_d_1,
        pv_i_q_1,
    )

    # predicted point
    if xlen == 1:
        for i in numba.prange(ngen):
            pd_w[i] = pv_w_1[i]
            pd_id[i] = pv_id_1[i]
            pd_iq[i] = pv_iq_1[i]
            pd_EFD[i] = pv_EFD_1[i]
            pd_u_d[i] = pv_u_d_1[i]
            pd_u_q[i] = pv_u_q_1[i]

    else:  # two- or three-point prediction
        # POINT 2
        pv_dt_2 = np.zeros(ngen)
        pv_w_2 = np.zeros(ngen)
        pv_id_2 = np.zeros(ngen)
        pv_iq_2 = np.zeros(ngen)
        pv_ifd_2 = np.zeros(ngen)
        pv_i1d_2 = np.zeros(ngen)
        pv_i1q_2 = np.zeros(ngen)
        pv_i2q_2 = np.zeros(ngen)
        pv_EFD_2 = np.zeros(ngen)
        pv_psyd_2 = np.zeros(ngen)
        pv_psyq_2 = np.zeros(ngen)

        for i in numba.prange(ngen):
            idx = i * gen_genrou_odr
            pv_dt_2[i] = x_pv_2[idx + 0]
            pv_w_2[i] = x_pv_2[idx + 1]
            pv_id_2[i] = x_pv_2[idx + 2]
            pv_iq_2[i] = x_pv_2[idx + 3]
            pv_ifd_2[i] = x_pv_2[idx + 4]
            pv_i1d_2[i] = x_pv_2[idx + 5]
            pv_i1q_2[i] = x_pv_2[idx + 6]
            pv_i2q_2[i] = x_pv_2[idx + 7]
            pv_psyd_2[i] = x_pv_2[idx + 10]
            pv_psyq_2[i] = x_pv_2[idx + 11]

            idx = i * exc_sexs_odr + exc_sexs_xi_st
            pv_EFD_2[i] = x_pv_2[idx + 1]

        pv_u_d_2 = -pv_psyq_2 * pv_w_2 / ws
        pv_u_q_2 = pv_psyd_2 * pv_w_2 / ws
        pv_i_d_2 = np.vstack((neg_id, pv_ifd_2, pv_i1d_2))
        pv_i_q_2 = np.vstack((neg_iq, pv_i1q_2, pv_i2q_2))

        point_two_tuple = (
            pv_dt_2,
            pv_w_2,
            pv_id_2,
            pv_iq_2,
            pv_ifd_2,
            pv_i1d_2,
            pv_i1q_2,
            pv_i2q_2,
            pv_EFD_2,
            pv_psyd_2,
            pv_psyq_2,
            pv_u_d_2,
            pv_u_q_2,
            pv_i_d_2,
            pv_i_q_2,
        )

        if xlen == 2:

            for i in numba.prange(ngen):
                pd_w[i] = 2.0 * pv_w_1[i] - pv_w_2[i]
                pd_id[i] = 2.0 * pv_id_1[i] - pv_id_2[i]
                pd_iq[i] = 2.0 * pv_iq_1[i] - pv_iq_2[i]
                pd_EFD[i] = 2.0 * pv_EFD_1[i] - pv_EFD_2[i]
                pd_u_d[i] = 2.0 * pv_u_d_1[i] - pv_u_d_2[i]
                pd_u_q[i] = 2.0 * pv_u_q_1[i] - pv_u_q_2[i]
        else:  # three-point prediction
            # POINT 3
            pv_dt_3 = np.zeros(ngen)
            pv_w_3 = np.zeros(ngen)
            pv_id_3 = np.zeros(ngen)
            pv_iq_3 = np.zeros(ngen)
            pv_ifd_3 = np.zeros(ngen)
            pv_i1d_3 = np.zeros(ngen)
            pv_i1q_3 = np.zeros(ngen)
            pv_i2q_3 = np.zeros(ngen)
            pv_EFD_3 = np.zeros(ngen)
            pv_psyd_3 = np.zeros(ngen)
            pv_psyq_3 = np.zeros(ngen)

            for i in numba.prange(ngen):
                idx = i * gen_genrou_odr
                pv_dt_3[i] = x_pv_3[idx + 0]
                pv_w_3[i] = x_pv_3[idx + 1]
                pv_id_3[i] = x_pv_3[idx + 2]
                neg_id[i] = -x_pv_3[idx + 2]
                pv_iq_3[i] = x_pv_3[idx + 3]
                neg_iq[i] = -x_pv_3[idx + 3]
                pv_ifd_3[i] = x_pv_3[idx + 4]
                pv_i1d_3[i] = x_pv_3[idx + 5]
                pv_i1q_3[i] = x_pv_3[idx + 6]
                pv_i2q_3[i] = x_pv_3[idx + 7]
                pv_psyd_3[i] = x_pv_3[idx + 10]
                pv_psyq_3[i] = x_pv_3[idx + 11]

                idx = i * exc_sexs_odr + exc_sexs_xi_st
                pv_EFD_3[i] = x_pv_3[idx + 1]

            pv_u_d_3 = -pv_psyq_3 * pv_w_3 / ws
            pv_u_q_3 = pv_psyd_3 * pv_w_3 / ws
            pv_i_d_3 = np.vstack((neg_id, pv_ifd_3, pv_i1d_3))
            pv_i_q_3 = np.vstack((neg_iq, pv_i1q_3, pv_i2q_3))

            point_three_tuple = (
                pv_dt_3,
                pv_w_3,
                pv_id_3,
                pv_iq_3,
                pv_ifd_3,
                pv_i1d_3,
                pv_i1q_3,
                pv_i2q_3,
                pv_EFD_3,
                pv_psyd_3,
                pv_psyq_3,
                pv_u_d_3,
                pv_u_q_3,
                pv_i_d_3,
                pv_i_q_3
            )

            for i in numba.prange(ngen):
                pd_w[i] = 1.25 * pv_w_1[i] + 0.5 * pv_w_2[i] - 0.75 * pv_w_3[i]
                pd_id[i] = 1.25 * pv_id_1[i] + 0.5 * pv_id_2[i] - 0.75 * pv_id_3[i]
                pd_iq[i] = 1.25 * pv_iq_1[i] + 0.5 * pv_iq_2[i] - 0.75 * pv_iq_3[i]
                pd_EFD[i] = 1.25 * pv_EFD_1[i] + 0.5 * pv_EFD_2[i] - 0.75 * pv_EFD_3[i]
                pd_u_d[i] = 1.25 * pv_u_d_1[i] + 0.5 * pv_u_d_2[i] - 0.75 * pv_u_d_3[i]
                pd_u_q[i] = 1.25 * pv_u_q_1[i] + 0.5 * pv_u_q_2[i] - 0.75 * pv_u_q_3[i]

    # END 2- OR 3-POINT IF-ELSE
    # END 1- OR MORE-POINT IF-ELSE
    for i in numba.prange(ngen):
        pd_dt[i] = pv_dt_1[i] + ts * (0.5 * (pv_w_1[i] + pd_w[i]))

    return (pd_w,
            pd_id,
            pd_iq,
            pd_EFD,
            pd_u_d,
            pd_u_q,
            pd_dt,
            point_one_tuple,
            point_two_tuple,
            point_three_tuple)


@numba.jit(nopython=True, nogil=True, boundscheck=False, parallel=False)
def numba_updateIg(
        # Begin "Returned" Arrays
        Igs,
        Isg,
        x_pv_1,
        ed_mod,
        eq_mod,
        theta,
        pv_his_d_1,
        pv_his_fd_1,
        pv_his_1d_1,
        pv_his_q_1,
        pv_his_1q_1,
        pv_his_2q_1,
        pv_his_red_d_1,
        pv_his_red_q_1,
        # End "Returned" Arrays
        # pfd
        gen_bus,
        bus_num,
        # dyd
        base_Is,
        ec_Rfd,
        ec_Lad,
        gen_genrou_odr,
        # ini
        Init_mac_alpha,
        Init_mac_Rd,
        Init_mac_Rq,
        Init_mac_Rd2,
        Init_mac_Rq2,
        Init_mac_Rd_coe,
        Init_mac_Rq_coe,
        Init_mac_Rav,
        Init_net_IbaseA,
        # self.xp
        pv_i_d_1,
        pv_u_d_1,
        pv_EFD_1,
        pv_i_q_1,
        pv_u_q_1,
        pd_EFD,
        pd_u_d,
        pd_u_q,
        pd_id,
        pd_iq,
        pd_dt,
        flag,
        geni,
):
    """

    :param Igs:
    :param Isg:
    :param x_pv_1:
    :param ed_mod:
    :param eq_mod:
    :param theta:
    :param pv_his_d_1:
    :param pv_his_fd_1:
    :param pv_his_1d_1:
    :param pv_his_q_1:
    :param pv_his_1q_1:
    :param pv_his_2q_1:
    :param pv_his_red_d_1:
    :param pv_his_red_q_1:
    :param gen_bus:
    :param bus_num:
    :param base_Is:
    :param ec_Rfd:
    :param ec_Lad:
    :param gen_genrou_odr:
    :param Init_mac_alpha:
    :param Init_mac_Rd:
    :param Init_mac_Rq:
    :param Init_mac_Rd2:
    :param Init_mac_Rq2:
    :param Init_mac_Rd_coe:
    :param Init_mac_Rq_coe:
    :param Init_mac_Rav:
    :param Init_net_IbaseA:
    :param pv_i_d_1:
    :param pv_u_d_1:
    :param pv_EFD_1:
    :param pv_i_q_1:
    :param pv_u_q_1:
    :param pd_EFD:
    :param pd_u_d:
    :param pd_u_q:
    :param pd_id:
    :param pd_iq:
    :param pd_dt:
    :param flag:
    :param geni:
    :return:
    """
    nbus = len(bus_num)
    ngen = len(gen_bus)

    Ias_n = Igs[:nbus]
    Ibs_n = Igs[nbus:2 * nbus]
    Ics_n = Igs[2 * nbus:]

    for i in numba.prange(ngen):
        # extract states ed and eq in previous step
        pv_ed = x_pv_1[i * gen_genrou_odr + 0 + 8]
        pv_eq = x_pv_1[i * gen_genrou_odr + 0 + 9]

        if i == geni:
            if flag == 0:
                continue
        EFD2efd = ec_Rfd[i] / ec_Lad[i]
        temp1 = np.sum(Init_mac_Rd2[i, 0, :] * pv_i_d_1[:, i])
        pv_his_d_1_temp = -Init_mac_alpha[i] * pv_ed + Init_mac_alpha[i] * pv_u_d_1[i] + temp1
        pv_his_d_1[i] = pv_his_d_1_temp

        temp2 = np.sum(Init_mac_Rd2[i, 1, :] * pv_i_d_1[:, i])
        pv_his_fd_1_temp = -Init_mac_alpha[i] * pv_EFD_1[i] * EFD2efd + temp2
        pv_his_fd_1[i] = pv_his_fd_1_temp

        temp3 = np.sum(Init_mac_Rd2[i, 2, :] * pv_i_d_1[:, i])
        pv_his_1d_1[i] = temp3

        temp4 = np.sum(Init_mac_Rq2[i, 0, :] * pv_i_q_1[:, i])
        pv_his_q_1_temp = -Init_mac_alpha[i] * pv_eq + Init_mac_alpha[i] * pv_u_q_1[i] + temp4
        pv_his_q_1[i] = pv_his_q_1_temp

        temp5 = np.sum(Init_mac_Rq2[i, 1, :] * pv_i_q_1[:, i])
        pv_his_1q_1[i] = temp5

        temp6 = np.sum(Init_mac_Rq2[i, 2, :] * pv_i_q_1[:, i])
        pv_his_2q_1[i] = temp6
        pv_his_red_d_1_temp = pv_his_d_1_temp - (
                    Init_mac_Rd_coe[i, 0] * (pv_his_fd_1_temp - pd_EFD[i] * EFD2efd) + Init_mac_Rd_coe[i, 1] * temp3)
        pv_his_red_q_1_temp = pv_his_q_1_temp - (Init_mac_Rq_coe[i, 0] * temp5 + Init_mac_Rq_coe[i, 1] * temp6)
        pv_his_red_d_1[i] = pv_his_red_d_1_temp
        pv_his_red_q_1[i] = pv_his_red_q_1_temp
        ed_temp = pd_u_d[i] + pv_his_red_d_1_temp
        eq_temp = pd_u_q[i] + pv_his_red_q_1_temp
        ed_mod_temp = ed_temp - (Init_mac_Rd[i] - Init_mac_Rq[i]) / 2.0 * pd_id[i]
        eq_mod_temp = eq_temp + (Init_mac_Rd[i] - Init_mac_Rq[i]) / 2.0 * pd_iq[i]
        id_src_temp = ed_mod_temp / Init_mac_Rav[i]
        iq_src_temp = eq_mod_temp / Init_mac_Rav[i]
        ed_mod[i] = ed_mod_temp
        eq_mod[i] = eq_mod_temp

        # theta
        genbus_idx = np.where(bus_num == gen_bus[i])[0][0]
        theta[i] = pd_dt[i] - np.pi / 2.0

        iPk = np.array([[np.cos(theta[i]), - np.sin(theta[i]), 1.0],
                        [np.cos(theta[i] - np.pi * 2.0 / 3.0), -np.sin(theta[i] - np.pi * 2.0 / 3.0), 1.0],
                        [np.cos(theta[i] + np.pi * 2.0 / 3.0), -np.sin(theta[i] + np.pi * 2.0 / 3.0), 1.0]
                        ])
        res = iPk[:, 0] * id_src_temp + iPk[:, 1] * iq_src_temp

        Isg[3 * i] = (res[0] * base_Is[i] / (Init_net_IbaseA[genbus_idx] * 1000.0))
        Isg[3 * i + 1] = (res[1] * base_Is[i] / (Init_net_IbaseA[genbus_idx] * 1000.0))
        Isg[3 * i + 2] = (res[2] * base_Is[i] / (Init_net_IbaseA[genbus_idx] * 1000.0))

        Ias_n[genbus_idx] = Ias_n[genbus_idx] + res[0] * base_Is[i] / (Init_net_IbaseA[genbus_idx] * 1000.0)
        Ibs_n[genbus_idx] = Ibs_n[genbus_idx] + res[1] * base_Is[i] / (Init_net_IbaseA[genbus_idx] * 1000.0)
        Ics_n[genbus_idx] = Ics_n[genbus_idx] + res[2] * base_Is[i] / (Init_net_IbaseA[genbus_idx] * 1000.0)


@numba.jit(nopython=True, nogil=True, boundscheck=False, parallel=False)
def numba_updateIibr(
        # Begin "Returned" Arrays ##
        Igi,
        Iibr,
        # End "Returned" Arrays ##
        # pfd
        ibr_bus,
        bus_num,
        # dyd
        ibr_Ibase,
        # ini
        Init_net_IbaseA,
        ibr_odr,
        # self.xp
        vtemp,
        x_ibr_pv_1,
        ts,
        x_bus_pv_1,
        bus_odr,
):
    """

    :param Igi:
    :param Iibr:
    :param ibr_bus:
    :param bus_num:
    :param ibr_Ibase:
    :param Init_net_IbaseA:
    :param ibr_odr:
    :param vtemp:
    :param x_ibr_pv_1:
    :param ts:
    :param x_bus_pv_1:
    :param bus_odr:
    :return:
    """
    nbus = len(bus_num)
    nibr = len(ibr_bus)

    Iai_n = Igi[:nbus]
    Ibi_n = Igi[nbus:2 * nbus]
    Ici_n = Igi[2 * nbus:]

    for i in numba.prange(nibr):
        ibrbus_idx = np.where(bus_num == ibr_bus[i])[0][0]

        regca_s0_1 = x_ibr_pv_1[i * ibr_odr + 0]
        regca_s1_1 = x_ibr_pv_1[i * ibr_odr + 1]
        regca_i1_1 = x_ibr_pv_1[i * ibr_odr + 5]
        regca_i2_1 = x_ibr_pv_1[i * ibr_odr + 6]

        pll_de_1 = x_bus_pv_1[ibrbus_idx * bus_odr + 1]
        pll_we_1 = x_bus_pv_1[ibrbus_idx * bus_odr + 2]

        theta = pll_de_1 + ts * pll_we_1 * 2 * np.pi * 60
        iPk = np.asarray([[np.cos(theta), - np.sin(theta), 1.0],
                          [np.cos(theta - np.pi * 2.0 / 3.0), -np.sin(theta - np.pi * 2.0 / 3.0), 1.0],
                          [np.cos(theta + np.pi * 2.0 / 3.0), -np.sin(theta + np.pi * 2.0 / 3.0), 1.0]])
        ip = regca_s0_1 * regca_i2_1
        iq = - regca_s1_1 - regca_i1_1
        res = []
        for j in range(3):
            res.append(iPk[j][0] * ip + iPk[j][1] * iq)

        Iibr[3 * i] = (res[0] * ibr_Ibase[i] / (Init_net_IbaseA[ibrbus_idx] * 1000.0))
        Iibr[3 * i + 1] = (res[1] * ibr_Ibase[i] / (Init_net_IbaseA[ibrbus_idx] * 1000.0))
        Iibr[3 * i + 2] = (res[2] * ibr_Ibase[i] / (Init_net_IbaseA[ibrbus_idx] * 1000.0))

        Iai_n[ibrbus_idx] = Iai_n[ibrbus_idx] + Iibr[3 * i]
        Ibi_n[ibrbus_idx] = Ibi_n[ibrbus_idx] + Iibr[3 * i + 1]
        Ici_n[ibrbus_idx] = Ici_n[ibrbus_idx] + Iibr[3 * i + 2]
    return


@numba.jit(nopython=True, nogil=True, boundscheck=False, parallel=False)
def numba_BusMea(
        #### Altered Arguments ####
        x_bus_nx,
        #### Constant Arguments ####
        # self
        Vsol,
        x_bus_pv_1,
        nbus,
        ts,
        t_release_f,
        # pfd
        ws,
        # dyd
        bus_odr,
        vm_te,
        pll_ke,
        pll_te,
        # other
        tn,
):
    for i in numba.prange(nbus):

        idx = i * bus_odr

        ze_1 = x_bus_pv_1[idx]
        de_1 = x_bus_pv_1[idx + 1]
        we_1 = x_bus_pv_1[idx + 2]
        vt_1 = x_bus_pv_1[idx + 3]
        vtm_1 = x_bus_pv_1[idx + 4]
        dvtm_1 = x_bus_pv_1[idx + 5]

        va = Vsol[i]
        vb = Vsol[i + nbus]
        vc = Vsol[i + 2 * nbus]

        # bus voltage magnitude
        nx_vt = np.sqrt((va * va + vb * vb + vc * vc) * 2 / 3)
        x_bus_nx[idx + 3] = nx_vt

        # TODO: Seems like vtm_1 is the wrong quantity here...should be vt_1?
        nx_dvtm = (nx_vt - vtm_1) / vm_te[i]
        x_bus_nx[idx + 5] = nx_dvtm

        nx_vtm = vtm_1 + nx_dvtm * ts
        x_bus_nx[idx + 4] = nx_vtm

        # bus freq and angle by PLL
        # theta
        theta = de_1 + ts * we_1 * ws

        fshift = 2.0 * np.pi / 3.0
        vq = -2.0 / 3.0 * (np.sin(theta) * va
                           + np.sin(theta - fshift) * vb
                           + np.sin(theta + fshift) * vc)

        nx_ze = ze_1 + pll_ke[i] / pll_te[i] * vq * ts
        nx_de = de_1 + we_1 * ws * ts

        if tn * ts < t_release_f:
            nx_we = 1.0
        else:
            nx_we = 1 + pll_ke[i] * vq + ze_1

        x_bus_nx[idx] = nx_ze
        x_bus_nx[idx + 1] = nx_de
        x_bus_nx[idx + 2] = nx_we
    return


@numba.jit(nopython=True, nogil=True, boundscheck=False, parallel=False)
def numba_updateX(
        # Altered Arguments
        x_pv_1,
        # self.xp
        nx_ed,
        nx_eq,
        nx_id,
        nx_iq,
        nx_ifd,
        nx_i1d,
        nx_i1q,
        nx_i2q,
        nx_psyd,
        nx_psyq,
        nx_psyfd,
        nx_psy1q,
        nx_psy1d,
        nx_psy2q,
        nx_pe,
        nx_w,
        nx_EFD,
        nx_dt,
        nx_v1,
        nx_pm,
        # Constant Arguments
        # self.xp
        pd_dt,
        pd_EFD,
        pv_his_fd_1,
        pv_his_1d_1,
        pv_his_1q_1,
        pv_his_2q_1,
        pv_dt_1,
        pv_w_1,
        pv_EFD_1,
        # pfd
        gen_bus,
        bus_num,
        ws,
        basemva,
        gen_MVA_base,
        # dyd
        gen_H,
        gen_D,
        gen_genrou_n,
        gen_genrou_odr,
        gen_genrou_xi_st,
        ec_Rfd,
        ec_Lad,
        ec_Laq,
        ec_Ll,
        ec_Lffd,
        ec_L11q,
        ec_L11d,
        ec_Lf1d,
        ec_L22q,
        pss_ieeest_A1,
        pss_ieeest_A2,
        pss_ieeest_A3,
        pss_ieeest_A4,
        pss_ieeest_A5,
        pss_ieeest_A6,
        pss_ieeest_T1,
        pss_ieeest_T2,
        pss_ieeest_T3,
        pss_ieeest_T4,
        pss_ieeest_T5,
        pss_ieeest_T6,
        pss_ieeest_KS,
        pss_ieeest_LSMAX,
        pss_ieeest_LSMIN,
        pss_ieeest_VCL,
        pss_ieeest_VCU,
        pss_ieeest_idx,
        pss_ieeest_odr,
        pss_ieeest_xi_st,
        exc_sexs_TA,
        exc_sexs_TB,
        exc_sexs_K,
        exc_sexs_TE,
        exc_sexs_Emin,
        exc_sexs_Emax,
        exc_sexs_idx,
        exc_sexs_n,
        exc_sexs_odr,
        exc_sexs_xi_st,
        gov_type,
        gov_tgov1_bus,
        gov_tgov1_id,
        gov_tgov1_Dt,
        gov_tgov1_R,
        gov_tgov1_T1,
        gov_tgov1_T2,
        gov_tgov1_T3,
        gov_tgov1_Vmax,
        gov_tgov1_Vmin,
        gov_tgov1_idx,
        gov_tgov1_n,
        gov_tgov1_odr,
        gov_tgov1_xi_st,
        gov_hygov_bus,
        gov_hygov_id,
        gov_hygov_At,
        gov_hygov_Dturb,
        gov_hygov_GMAX,
        gov_hygov_GMIN,
        gov_hygov_R,
        gov_hygov_TW,
        gov_hygov_Tf,
        gov_hygov_Tg,
        gov_hygov_Tr,
        gov_hygov_VELM,
        gov_hygov_qNL,
        gov_hygov_r,
        gov_hygov_idx,
        gov_hygov_n,
        gov_hygov_odr,
        gov_hygov_xi_st,
        gov_gast_bus,
        gov_gast_id,
        gov_gast_R,
        gov_gast_LdLmt,
        gov_gast_KT,
        gov_gast_T1,
        gov_gast_T2,
        gov_gast_T3,
        gov_gast_VMIN,
        gov_gast_VMAX,
        gov_gast_Dturb,
        gov_gast_idx,
        gov_gast_n,
        gov_gast_odr,
        gov_gast_xi_st,
        bus_odr,
        # ini
        Init_mac_Rav,
        Init_mac_Rd1,
        Init_mac_Rd1inv,
        Init_mac_Rq1,
        Init_mac_Rq1inv,
        Init_mac_Gequiv,
        tgov1_2gen,
        hygov_2gen,
        gast_2gen,
        # self.
        vref,
        gref,
        Vsol,
        Isg,
        ed_mod,
        eq_mod,
        vref_1,
        x_bus_pv_1,
        ts,
        flag_gentrip,
        i_gentrip,
):
    """

    :param x_pv_1:
    :param nx_ed:
    :param nx_eq:
    :param nx_id:
    :param nx_iq:
    :param nx_ifd:
    :param nx_i1d:
    :param nx_i1q:
    :param nx_i2q:
    :param nx_psyd:
    :param nx_psyq:
    :param nx_psyfd:
    :param nx_psy1q:
    :param nx_psy1d:
    :param nx_psy2q:
    :param nx_pe:
    :param nx_w:
    :param nx_EFD:
    :param nx_dt:
    :param nx_v1:
    :param nx_pm:
    :param pd_dt:
    :param pd_EFD:
    :param pv_his_fd_1:
    :param pv_his_1d_1:
    :param pv_his_1q_1:
    :param pv_his_2q_1:
    :param pv_dt_1:
    :param pv_w_1:
    :param pv_EFD_1:
    :param gen_bus:
    :param bus_num:
    :param ws:
    :param basemva:
    :param gen_MVA_base:
    :param gen_H:
    :param gen_D:
    :param gen_genrou_n:
    :param gen_genrou_odr:
    :param gen_genrou_xi_st:
    :param ec_Rfd:
    :param ec_Lad:
    :param ec_Laq:
    :param ec_Ll:
    :param ec_Lffd:
    :param ec_L11q:
    :param ec_L11d:
    :param ec_Lf1d:
    :param ec_L22q:
    :param pss_ieeest_A1:
    :param pss_ieeest_A2:
    :param pss_ieeest_A3:
    :param pss_ieeest_A4:
    :param pss_ieeest_A5:
    :param pss_ieeest_A6:
    :param pss_ieeest_T1:
    :param pss_ieeest_T2:
    :param pss_ieeest_T3:
    :param pss_ieeest_T4:
    :param pss_ieeest_T5:
    :param pss_ieeest_T6:
    :param pss_ieeest_KS:
    :param pss_ieeest_LSMAX:
    :param pss_ieeest_LSMIN:
    :param pss_ieeest_VCL:
    :param pss_ieeest_VCU:
    :param pss_ieeest_idx:
    :param pss_ieeest_odr:
    :param pss_ieeest_xi_st:
    :param exc_sexs_TA:
    :param exc_sexs_TB:
    :param exc_sexs_K:
    :param exc_sexs_TE:
    :param exc_sexs_Emin:
    :param exc_sexs_Emax:
    :param exc_sexs_idx:
    :param exc_sexs_n:
    :param exc_sexs_odr:
    :param exc_sexs_xi_st:
    :param gov_type:
    :param gov_tgov1_bus:
    :param gov_tgov1_id:
    :param gov_tgov1_Dt:
    :param gov_tgov1_R:
    :param gov_tgov1_T1:
    :param gov_tgov1_T2:
    :param gov_tgov1_T3:
    :param gov_tgov1_Vmax:
    :param gov_tgov1_Vmin:
    :param gov_tgov1_idx:
    :param gov_tgov1_n:
    :param gov_tgov1_odr:
    :param gov_tgov1_xi_st:
    :param gov_hygov_bus:
    :param gov_hygov_id:
    :param gov_hygov_At:
    :param gov_hygov_Dturb:
    :param gov_hygov_GMAX:
    :param gov_hygov_GMIN:
    :param gov_hygov_R:
    :param gov_hygov_TW:
    :param gov_hygov_Tf:
    :param gov_hygov_Tg:
    :param gov_hygov_Tr:
    :param gov_hygov_VELM:
    :param gov_hygov_qNL:
    :param gov_hygov_r:
    :param gov_hygov_idx:
    :param gov_hygov_n:
    :param gov_hygov_odr:
    :param gov_hygov_xi_st:
    :param gov_gast_bus:
    :param gov_gast_id:
    :param gov_gast_R:
    :param gov_gast_LdLmt:
    :param gov_gast_KT:
    :param gov_gast_T1:
    :param gov_gast_T2:
    :param gov_gast_T3:
    :param gov_gast_VMIN:
    :param gov_gast_VMAX:
    :param gov_gast_Dturb:
    :param gov_gast_idx:
    :param gov_gast_n:
    :param gov_gast_odr:
    :param gov_gast_xi_st:
    :param bus_odr:
    :param Init_mac_Rav:
    :param Init_mac_Rd1:
    :param Init_mac_Rd1inv:
    :param Init_mac_Rq1:
    :param Init_mac_Rq1inv:
    :param Init_mac_Gequiv:
    :param tgov1_2gen:
    :param hygov_2gen:
    :param gast_2gen:
    :param vref:
    :param gref:
    :param Vsol:
    :param Isg:
    :param ed_mod:
    :param eq_mod:
    :param vref_1:
    :param x_bus_pv_1:
    :param ts:
    :param flag_gentrip:
    :param i_gentrip:
    :return:
    """
    nbus = len(bus_num)
    x_pv_1_out = np.zeros(x_pv_1.shape)

    for i in numba.prange(gen_genrou_n):

        idx = gen_genrou_odr * i + gen_genrou_xi_st
        # if i == i_gentrip and flag_gentrip == 0:
        #     # x_pv_1_out[idx:idx+gen_genrou_odr] = 0.0
        #     continue

        EFD2efd = ec_Rfd[i] / ec_Lad[i]
        pv_ed = x_pv_1[idx + 8]
        pv_eq = x_pv_1[idx + 9]

        # gov pm
        if gov_type[i] == 2:  # TGOV1
            idx_gov = np.where(gov_tgov1_idx == i)[0][0]
            pv_pm = x_pv_1[gov_tgov1_odr * idx_gov + gov_tgov1_xi_st + 2]

        elif gov_type[i] == 1:  # HYGOV
            idx_gov = np.where(gov_hygov_idx == i)[0][0]
            pv_pm = x_pv_1[gov_hygov_odr * idx_gov + gov_hygov_xi_st + 4]

        elif gov_type[i] == 0:  # GAST
            idx_gov = np.where(gov_gast_idx == i)[0][0]
            pv_pm = x_pv_1[gov_gast_odr * idx_gov + gov_gast_xi_st + 3]

        else:
            print("ERROR: Unrecognized governor type: ", gov_type[i])

        # theta
        genbus_idx = np.where(bus_num == gen_bus[i])[0][0]
        theta = pd_dt[i] - np.pi / 2.0

        Pk = np.array([[np.cos(theta),
                        np.cos(theta - np.pi * 2.0 / 3.0),
                        np.cos(theta + np.pi * 2.0 / 3.0)
                        ],
                       [-np.sin(theta),
                        -np.sin(theta - np.pi * 2.0 / 3.0),
                        -np.sin(theta + np.pi * 2.0 / 3.0)
                        ],
                       [0.5, 0.5, 0.5]
                       ])

        idx_v = np.array([genbus_idx, genbus_idx + nbus, genbus_idx + 2 * nbus])

        nx_ed = 2.0 / 3.0 * np.sum(Pk[0, :] * Vsol[idx_v])
        nx_eq = 2.0 / 3.0 * np.sum(Pk[1, :] * Vsol[idx_v])

        nx_id = (ed_mod[i] - nx_ed) / Init_mac_Rav[i]
        nx_iq = (eq_mod[i] - nx_eq) / Init_mac_Rav[i]

        v1 = pd_EFD[i] * EFD2efd - pv_his_fd_1[i] + Init_mac_Rd1[i, 1, 0] * nx_id
        v2 = -pv_his_1d_1[i] + Init_mac_Rd1[i, 2, 0] * nx_id
        nx_ifd = Init_mac_Rd1inv[i, 0, 0] * v1 + Init_mac_Rd1inv[i, 0, 1] * v2
        nx_i1d = Init_mac_Rd1inv[i, 1, 0] * v1 + Init_mac_Rd1inv[i, 1, 1] * v2

        v1 = -pv_his_1q_1[i] + Init_mac_Rq1[i, 1, 0] * nx_iq
        v2 = -pv_his_2q_1[i] + Init_mac_Rq1[i, 2, 0] * nx_iq
        nx_i1q = Init_mac_Rq1inv[i, 0, 0] * v1 + Init_mac_Rq1inv[i, 0, 1] * v2
        nx_i2q = Init_mac_Rq1inv[i, 1, 0] * v1 + Init_mac_Rq1inv[i, 1, 1] * v2

        nx_psyd = (- (ec_Lad[i] + ec_Ll[i]) * nx_id + ec_Lad[i] * nx_ifd + ec_Lad[i] * nx_i1d)
        nx_psyq = (- (ec_Laq[i] + ec_Ll[i]) * nx_iq + ec_Laq[i] * nx_i1q + ec_Laq[i] * nx_i2q)
        nx_psyfd = (- ec_Lad[i] * nx_id + ec_Lffd[i] * nx_ifd + ec_Lf1d[i] * nx_i1d)
        nx_psy1q = (- ec_Laq[i] * nx_iq + ec_L11q[i] * nx_i1q + ec_Laq[i] * nx_i2q)
        nx_psy1d = (- ec_Lad[i] * nx_id + ec_Lf1d[i] * nx_ifd + ec_L11d[i] * nx_i1d)
        nx_psy2q = (- ec_Laq[i] * nx_iq + ec_Laq[i] * nx_i1q + ec_L22q[i] * nx_i2q)

        nx_pe = nx_psyd * nx_iq - nx_psyq * nx_id
        nx_qe = nx_psyd * nx_id + nx_psyq * nx_iq
        nx_w = pv_w_1[i] + (ws * (pv_pm / (pv_w_1[i] / ws) - nx_pe) - gen_D[i] * (pv_w_1[i] - ws)) / gen_H[i] / 2.0 * ts

        nx_dt = pv_dt_1[i] + (nx_w + pv_w_1[i]) / 2.0 * ts

        x_pv_1_out[idx] = nx_dt
        x_pv_1_out[idx + 1] = nx_w
        x_pv_1_out[idx + 2] = nx_id
        x_pv_1_out[idx + 3] = nx_iq
        x_pv_1_out[idx + 4] = nx_ifd
        x_pv_1_out[idx + 5] = nx_i1d
        x_pv_1_out[idx + 6] = nx_i1q
        x_pv_1_out[idx + 7] = nx_i2q
        x_pv_1_out[idx + 8] = nx_ed
        x_pv_1_out[idx + 9] = nx_eq
        x_pv_1_out[idx + 10] = nx_psyd
        x_pv_1_out[idx + 11] = nx_psyq
        x_pv_1_out[idx + 12] = nx_psyfd
        x_pv_1_out[idx + 13] = nx_psy1q
        x_pv_1_out[idx + 14] = nx_psy1d
        x_pv_1_out[idx + 15] = nx_psy2q
        # x_pv_1_out[idx + 16] = nx_pe , to be updated in UpdateX
        x_pv_1_out[idx + 16] = nx_ed * nx_id + nx_eq * nx_iq
        x_pv_1_out[idx + 17] = nx_qe

        # pss
        pss_input = (nx_w - ws) / ws  # pu freq deviation

        idx_pss1 = np.where(pss_ieeest_idx == i)[0]
        if len(idx_pss1) == 0:
            pass
        else:
            idx_pss = idx_pss1[0]
            pv_idx = pss_ieeest_odr * idx_pss + pss_ieeest_xi_st
            pv_y1 = x_pv_1[pv_idx + 0]
            pv_y2 = x_pv_1[pv_idx + 1]
            pv_y3 = x_pv_1[pv_idx + 2]
            pv_y4 = x_pv_1[pv_idx + 3]
            pv_y5 = x_pv_1[pv_idx + 4]
            pv_y6 = x_pv_1[pv_idx + 5]
            pv_y7 = x_pv_1[pv_idx + 6]
            pv_x1 = x_pv_1[pv_idx + 7]
            pv_x2 = x_pv_1[pv_idx + 8]

            dxdt = (pss_input - pv_x1) / ts
            dxdt_1 = (pv_x1 - pv_x2) / ts
            dx2dt2 = (dxdt - dxdt_1) / ts

            if pss_ieeest_A2[idx_pss] == 0:
                if pss_ieeest_A1[idx_pss] == 0:
                    temp_nx_y2 = pss_input + pss_ieeest_A5[idx_pss] * dxdt + pss_ieeest_A6[idx_pss] * dx2dt2
                    temp_nx_y1 = 0.0
                else:
                    temp_nx_y2 = pv_y2 + (pss_input + pss_ieeest_A5[idx_pss] * dxdt + pss_ieeest_A6[
                        idx_pss] * dx2dt2 - pv_y2) / pss_ieeest_A1[idx_pss] * ts
                    temp_nx_y1 = 0.0
            else:
                temp_nx_y2 = pv_y2 + pv_y1 * ts
                temp_nx_y1 = pv_y1 + (pss_input + pss_ieeest_A5[idx_pss] * dxdt + pss_ieeest_A6[idx_pss] * dx2dt2 -
                                      pv_y2 - pss_ieeest_A1[idx_pss] * pv_y1) / pss_ieeest_A2[idx_pss] * ts

            if pss_ieeest_A4[idx_pss] == 0:
                if pss_ieeest_A3[idx_pss] == 0:
                    temp_nx_y4 = temp_nx_y2
                    temp_nx_y3 = 0.0
                else:
                    temp_nx_y3 = 0.0
                    temp_nx_y4 = pv_y4 + (pv_y2 - pv_y4) / pss_ieeest_A3[idx_pss] * ts
            else:
                temp_nx_y4 = pv_y4 + pv_y3 * ts
                temp_nx_y3 = pv_y3 + (pv_y2 - pv_y4 - pss_ieeest_A3[idx_pss] *
                                      pv_y3) / pss_ieeest_A4[idx_pss] * ts

            dy4dt = (temp_nx_y4 - pv_y4) / ts
            if pss_ieeest_T2[idx_pss] == 0.0:
                temp_nx_y5 = temp_nx_y4 + dy4dt * pss_ieeest_T1[idx_pss]
            else:
                temp_nx_y5 = pv_y5 + (pv_y4 - pv_y5) / pss_ieeest_T2[idx_pss] * ts + (temp_nx_y4 - pv_y4) * \
                             pss_ieeest_T1[idx_pss] / pss_ieeest_T2[idx_pss]

            dy5dt = (temp_nx_y5 - pv_y5) / ts

            if pss_ieeest_T4[idx_pss] == 0:
                temp_nx_y6 = temp_nx_y5 - dy5dt * pss_ieeest_T3[idx_pss]
            else:
                temp_nx_y6 = pv_y6 + (pv_y5 - pv_y6 + pss_ieeest_T3[idx_pss] * dy5dt) / pss_ieeest_T4[idx_pss] * ts

            if pss_ieeest_T5[idx_pss] == 0:
                temp_nx_y7 = pv_y7 + (pss_ieeest_KS[idx_pss] * pv_y6 - pv_y7) / pss_ieeest_T6[idx_pss] * ts
            else:
                temp_nx_y7 = pv_y7 + (pss_ieeest_KS[idx_pss] * pv_y6 - pv_y7 / pss_ieeest_T5[idx_pss]) / pss_ieeest_T6[
                    idx_pss] * pss_ieeest_T5[idx_pss] * ts

            dy7dt = (temp_nx_y7 - pv_y7) / ts
            if dy7dt > pss_ieeest_LSMAX[idx_pss]:
                vss = pss_ieeest_LSMAX[idx_pss]
            elif dy7dt < pss_ieeest_LSMIN[idx_pss]:
                vss = pss_ieeest_LSMIN[idx_pss]
            else:
                vss = dy7dt

            if pss_ieeest_VCL[idx_pss] == 0:
                if pss_ieeest_VCU[idx_pss] == 0:
                    vs = vss
                else:
                    if vss > pss_ieeest_VCU[idx_pss]:
                        vs = 0.0
                    else:
                        vs = vss
            else:
                if vss < pss_ieeest_VCL[idx_pss]:
                    vs = 0.0
                else:
                    if pss_ieeest_VCU[idx_pss] == 0:
                        vs = vss
                    else:
                        if vss > pss_ieeest_VCU[idx_pss]:
                            vs = 0.0
                        else:
                            vs = vss

            if pss_ieeest_VCU[idx_pss] == 0:
                vs = vss
            else:
                if vss > pss_ieeest_VCU[idx_pss]:
                    vs = 0.0
                else:
                    vs = vss

            x_pv_1_out[pv_idx + 0] = temp_nx_y1
            x_pv_1_out[pv_idx + 1] = temp_nx_y2
            x_pv_1_out[pv_idx + 2] = temp_nx_y3
            x_pv_1_out[pv_idx + 3] = temp_nx_y4
            x_pv_1_out[pv_idx + 4] = temp_nx_y5
            x_pv_1_out[pv_idx + 5] = temp_nx_y6
            x_pv_1_out[pv_idx + 6] = temp_nx_y7
            x_pv_1_out[pv_idx + 7] = pss_input
            x_pv_1_out[pv_idx + 8] = pv_x1
            x_pv_1_out[pv_idx + 9] = vs

        # exc
        idx_exc = np.where(exc_sexs_idx == i)[0][0]
        pv_v1 = x_pv_1[exc_sexs_odr * idx_exc + exc_sexs_xi_st + 0]
        if len(idx_pss1) == 0:
            vs = 0
        else:
            pass

        vref_n = vref[i]
        dvref = (vref_n - vref_1[i]) / ts
        vref_1[i] = vref_n

        busi = np.where(bus_num == gen_bus[i])[0][0]

        vtm_1 = x_bus_pv_1[busi * bus_odr + 4]
        dvtm_1 = x_bus_pv_1[busi * bus_odr + 5]

        exc_input_vt = vtm_1
        exc_input_dvt = dvtm_1

        nx_v1 = pv_v1 + ((vref_n - exc_input_vt - pv_v1 + vs) / exc_sexs_TB[i] + exc_sexs_TA[i] / exc_sexs_TB[i] * (
                    dvref - exc_input_dvt)) * ts
        if exc_sexs_TE[i] == 0:
            EFD = exc_sexs_K[i] * pv_v1
        else:
            EFD = pv_EFD_1[i] + (exc_sexs_K[i] * pv_v1 - pv_EFD_1[i]) * ts / exc_sexs_TE[i]
        if EFD < exc_sexs_Emin[i]:
            EFD = exc_sexs_Emin[i]
        if EFD > exc_sexs_Emax[i]:
            EFD = exc_sexs_Emax[i]
        nx_EFD = EFD

        x_pv_1_out[exc_sexs_odr * idx_exc + exc_sexs_xi_st + 0] = nx_v1
        x_pv_1_out[exc_sexs_odr * idx_exc + exc_sexs_xi_st + 1] = nx_EFD

        # gov
        gov_input = nx_w / ws - 1.0
        if gov_type[i] == 2:  # 'TGOV1'
            idx_gov = np.where(gov_tgov1_idx == i)[0][0]
            pv_idx = gov_tgov1_odr * idx_gov + gov_tgov1_xi_st

            pv_p1 = x_pv_1[pv_idx + 0]
            pv_p2 = x_pv_1[pv_idx + 1]

            temp_nx_p1 = pv_p1 + ((gref[tgov1_2gen[idx_gov]] - gov_input) / gov_tgov1_R[idx_gov] - pv_p1) / \
                         gov_tgov1_T1[idx_gov] * ts
            if temp_nx_p1 > gov_tgov1_Vmax[idx_gov]:
                temp_nx_p1 = gov_tgov1_Vmax[idx_gov]
            if temp_nx_p1 < gov_tgov1_Vmin[idx_gov]:
                temp_nx_p1 = gov_tgov1_Vmin[idx_gov]
            nx_p1 = temp_nx_p1

            dp1dt = (temp_nx_p1 - pv_p1) / ts

            nx_p2 = pv_p2 + (pv_p1 - pv_p2 + dp1dt * gov_tgov1_T2[idx_gov]) / gov_tgov1_T3[idx_gov] * ts
            nx_pm = nx_p2 - gov_tgov1_Dt[idx_gov] * gov_input

            x_pv_1_out[pv_idx + 0] = nx_p1
            x_pv_1_out[pv_idx + 1] = nx_p2
            x_pv_1_out[pv_idx + 2] = nx_pm

            # # --------------------------- to bypass gov ----------------------------------
            # x_pv_1_out[pv_idx + 2] = pv_pm
            # nx_p1 = temp_nx_p1
            # nx_p2 = temp_nx_p2
            # nx_p3 = temp_nx_p3

        if gov_type[i] == 1:  # 'HYGOV'

            idx_gov = np.where(gov_hygov_idx == i)[0][0]
            pv_idx = gov_hygov_odr * idx_gov + gov_hygov_xi_st

            pv_xe = x_pv_1[pv_idx]
            pv_xc = x_pv_1[pv_idx + 1]
            pv_xg = x_pv_1[pv_idx + 2]
            pv_xq = x_pv_1[pv_idx + 3]

            idx_gov = np.where(gov_hygov_idx == i)[0][0]

            n1 = gref[hygov_2gen[idx_gov]] - (pv_xc * gov_hygov_R[idx_gov] + gov_input)
            temp_nx_xe = pv_xe + (n1 - pv_xe) / gov_hygov_Tf[idx_gov] * ts

            temp_nx_xc = pv_xc + ((temp_nx_xe - pv_xe) / ts * gov_hygov_Tr[idx_gov] +
                                  pv_xe) / gov_hygov_r[idx_gov] / gov_hygov_Tr[idx_gov] * ts
            dxcdt = (temp_nx_xc - pv_xc) / ts
            if dxcdt > gov_hygov_VELM[idx_gov]:
                temp_nx_xc = gov_hygov_VELM[idx_gov] * ts + pv_xc
            if dxcdt < - gov_hygov_VELM[idx_gov]:
                temp_nx_xc = - gov_hygov_VELM[idx_gov] * ts + pv_xc

            if temp_nx_xc > gov_hygov_GMAX[idx_gov]:
                temp_nx_xc = gov_hygov_GMAX[idx_gov]
            if temp_nx_xc < gov_hygov_GMIN[idx_gov]:
                temp_nx_xc = gov_hygov_GMIN[idx_gov]

            temp_nx_xg = pv_xg + (pv_xc - pv_xg) / gov_hygov_Tg[idx_gov] * ts
            xqxg = pv_xq / pv_xg
            temp_nx_xq = pv_xq + (1 - xqxg * xqxg) / gov_hygov_TW[idx_gov] * ts
            temp_nx_pm = (pv_xq - gov_hygov_qNL[idx_gov]) * xqxg * xqxg * gov_hygov_At[
                idx_gov] - gov_hygov_Dturb[idx_gov] * gov_input * pv_xg

            x_pv_1_out[pv_idx] = temp_nx_xe
            x_pv_1_out[pv_idx + 1] = temp_nx_xc
            x_pv_1_out[pv_idx + 2] = temp_nx_xg
            x_pv_1_out[pv_idx + 3] = temp_nx_xq
            x_pv_1_out[pv_idx + 4] = temp_nx_pm

            # # --------------------------- to bypass gov ----------------------------------
            # x_pv_1_out[pv_idx + 4] = pv_pm

        if gov_type[i] == 0:  # 'GAST'

            idx_gov = np.where(gov_gast_idx == i)[0][0]
            pv_idx = gov_gast_odr * idx_gov + gov_gast_xi_st

            pv_p1 = x_pv_1[pv_idx + 0]
            pv_p2 = x_pv_1[pv_idx + 1]
            pv_p3 = x_pv_1[pv_idx + 2]

            temp_nx_p3 = pv_p3 + (pv_p2 - pv_p3) / gov_gast_T3[idx_gov] * ts
            temp_nx_p2 = pv_p2 + (pv_p1 - pv_p2) / gov_gast_T2[idx_gov] * ts

            pl = np.minimum(gref[gast_2gen[idx_gov]] - gov_input / gov_gast_R[idx_gov],
                            (gov_gast_LdLmt[idx_gov] - temp_nx_p3) * gov_gast_KT[idx_gov] +
                            gov_gast_LdLmt[idx_gov])
            temp_nx_p1 = pv_p1 + (pl - pv_p1) / gov_gast_T1[idx_gov] * ts

            if temp_nx_p1 > gov_gast_VMAX[idx_gov]:
                temp_nx_p1 = gov_gast_VMAX[idx_gov]
            if temp_nx_p1 < gov_gast_VMIN[idx_gov]:
                temp_nx_p1 = gov_gast_VMIN[idx_gov]

            nx_pm = temp_nx_p2 - gov_gast_Dturb[idx_gov] * gov_input

            x_pv_1_out[pv_idx + 0] = temp_nx_p1
            x_pv_1_out[pv_idx + 1] = temp_nx_p2
            x_pv_1_out[pv_idx + 2] = temp_nx_p3
            x_pv_1_out[pv_idx + 3] = nx_pm

            # # --------------------------- to bypass gov ----------------------------------
            # x_pv_1_out[pv_idx + 3] = pv_pm

        # TODO: Do these calculations need to be done after a gen fault?
        # At the end of updateX in Lib_BW.py for serial version.

        va = Vsol[busi]
        vb = Vsol[busi + nbus]
        vc = Vsol[busi + 2 * nbus]

        Isg[3 * i] = Isg[3 * i] - (va * Init_mac_Gequiv[i, 0, 0] +
                                   vb * Init_mac_Gequiv[i, 0, 1] +
                                   vc * Init_mac_Gequiv[i, 0, 2]
                                   )
        Isg[3 * i + 1] = Isg[3 * i + 1] - (va * Init_mac_Gequiv[i, 1, 0]
                                           + vb * Init_mac_Gequiv[i, 1, 1]
                                           + vc * Init_mac_Gequiv[i, 1, 2]
                                           )
        Isg[3 * i + 2] = Isg[3 * i + 2] - (va * Init_mac_Gequiv[i, 2, 0]
                                           + vb * Init_mac_Gequiv[i, 2, 1]
                                           + vc * Init_mac_Gequiv[i, 2, 2]
                                           )

        ia = Isg[3 * i]
        ib = Isg[3 * i + 1]
        ic = Isg[3 * i + 2]

        # previously forgot to convert to gen base
        coefficient = 2.0 / 3.0 * basemva / gen_MVA_base[i]
        pe = (va * ia + vb * ib + vc * ic) * coefficient
        qe = ((vb - vc) * ia + (vc - va) * ib + (va - vb) * ic) / np.sqrt(3.0) * coefficient

        x_pv_1_out[i * gen_genrou_odr + 16] = pe
        x_pv_1_out[i * gen_genrou_odr + 17] = qe

    return x_pv_1_out


@numba.jit(nopython=True, nogil=True, boundscheck=False, parallel=False)
def numba_updateXibr(
        #### Altered Arguments ####
        # x_pv_1,
        x_ibr_pv_1,
        #### Constant Arguments ####
        # pfd
        ibr_bus,
        bus_num,
        ws,
        basemva,
        ibr_MVA_base,
        # dyd
        ibr_regca_Volim,
        ibr_regca_Khv,
        ibr_regca_Lvpnt0,
        ibr_regca_Lvpnt1,
        ibr_regca_Tg,
        ibr_regca_Iqrmax,
        ibr_regca_Iqrmin,
        ibr_regca_Tfltr,
        ibr_regca_Zerox,
        ibr_regca_Brkpt,
        ibr_regca_Rrpwr,
        ibr_reecb_PQFLAG,
        ibr_reecb_PFFLAG,
        ibr_reecb_VFLAG,
        ibr_reecb_QFLAG,
        ibr_reecb_Imax,
        ibr_reecb_Vdip,
        ibr_reecb_Vup,
        ibr_reecb_Trv,
        ibr_reecb_dbd1,
        ibr_reecb_dbd2,
        ibr_reecb_Kqv,
        ibr_reecb_Iqll,
        ibr_reecb_Iqhl,
        ibr_reecb_Tp,
        ibr_reecb_Qmin,
        ibr_reecb_Qmax,
        ibr_reecb_Kqp,
        ibr_reecb_Kqi,
        ibr_reecb_Vmin,
        ibr_reecb_Vmax,
        ibr_reecb_Kvp,
        ibr_reecb_Kvi,
        ibr_reecb_Tiq,
        ibr_reecb_dPmin,
        ibr_reecb_dPmax,
        ibr_reecb_Pmin,
        ibr_reecb_Pmax,
        ibr_reecb_Tpord,
        ibr_repca_FFlag,
        ibr_repca_VCFlag,
        ibr_repca_RefFlag,
        ibr_repca_fdbd1,
        ibr_repca_fdbd2,
        ibr_repca_Ddn,
        ibr_repca_Dup,
        ibr_repca_Tp,
        ibr_repca_femin,
        ibr_repca_femax,
        ibr_repca_Kpg,
        ibr_repca_Kig,
        ibr_repca_Pmin,
        ibr_repca_Pmax,
        ibr_repca_Tg,
        ibr_repca_Rc,
        ibr_repca_Xc,
        ibr_repca_Kc,
        ibr_repca_Tfltr,
        ibr_repca_dbd1,
        ibr_repca_dbd2,
        ibr_repca_emin,
        ibr_repca_emax,
        ibr_repca_Vfrz,
        ibr_repca_Kp,
        ibr_repca_Ki,
        ibr_repca_Qmin,
        ibr_repca_Qmax,
        ibr_repca_Tft,
        ibr_repca_Tfv,
        # ibr_pll_ke,
        # ibr_pll_te,
        # ini
        Init_ibr_N,
        Init_ibr_regca_Qgen0,
        Init_ibr_reecb_pfaref,
        Init_ibr_reecb_Vref0,
        Init_ibr_repca_Pref_out,
        # self.<something>
        Vsol,
        x_bus_pv_1,
        bus_odr,
        # vtm,
        Iibr,
        ts,
):
    nbus = len(bus_num)
    nibr = len(ibr_bus)

    for i in numba.prange(nibr):
        ibrbus = ibr_bus[i]

        ibrbus_idx = np.where(bus_num == ibrbus)[0][0]

        va = Vsol[ibrbus_idx]
        vb = Vsol[ibrbus_idx + nbus]
        vc = Vsol[ibrbus_idx + 2 * nbus]

        ia = Iibr[3 * i]
        ib = Iibr[3 * i + 1]
        ic = Iibr[3 * i + 2]

        # previously forgot to convert to IBR base
        pe = ((va * ia + vb * ib + vc * ic) * 2.0 / 3.0) * basemva / ibr_MVA_base[i]
        qe = (((vb - vc) * ia + (vc - va) * ib + (va - vb) * ic) / np.sqrt(3.0) * 2.0 / 3.0) * basemva / ibr_MVA_base[i]

        regca_s0_1 = x_ibr_pv_1[i * Init_ibr_N + 0]
        regca_s1_1 = x_ibr_pv_1[i * Init_ibr_N + 1]
        regca_s2_1 = x_ibr_pv_1[i * Init_ibr_N + 2]
        regca_Vmp_1 = x_ibr_pv_1[i * Init_ibr_N + 3]
        regca_Vap_1 = x_ibr_pv_1[i * Init_ibr_N + 4]
        regca_i1_1 = x_ibr_pv_1[i * Init_ibr_N + 5]
        regca_i2_1 = x_ibr_pv_1[i * Init_ibr_N + 6]
        regca_ip2rr = x_ibr_pv_1[i * Init_ibr_N + 7]

        reecb_s0_1 = x_ibr_pv_1[i * Init_ibr_N + 8]
        reecb_s1_1 = x_ibr_pv_1[i * Init_ibr_N + 9]
        reecb_s2_1 = x_ibr_pv_1[i * Init_ibr_N + 10]
        reecb_s3_1 = x_ibr_pv_1[i * Init_ibr_N + 11]
        reecb_s4_1 = x_ibr_pv_1[i * Init_ibr_N + 12]
        reecb_s5_1 = x_ibr_pv_1[i * Init_ibr_N + 13]
        reecb_Ipcmd_1 = x_ibr_pv_1[i * Init_ibr_N + 14]
        reecb_Iqcmd_1 = x_ibr_pv_1[i * Init_ibr_N + 15]
        reecb_Pref_1 = x_ibr_pv_1[i * Init_ibr_N + 16]
        reecb_Qext_1 = x_ibr_pv_1[i * Init_ibr_N + 17]
        reecb_q2vPI_1 = x_ibr_pv_1[i * Init_ibr_N + 18]
        reecb_v2iPI_1 = x_ibr_pv_1[i * Init_ibr_N + 19]

        repca_s0_1 = x_ibr_pv_1[i * Init_ibr_N + 20]
        repca_s1_1 = x_ibr_pv_1[i * Init_ibr_N + 21]
        repca_s2_1 = x_ibr_pv_1[i * Init_ibr_N + 22]
        repca_s3_1 = x_ibr_pv_1[i * Init_ibr_N + 23]
        repca_s4_1 = x_ibr_pv_1[i * Init_ibr_N + 24]
        repca_s5_1 = x_ibr_pv_1[i * Init_ibr_N + 25]
        repca_s6_1 = x_ibr_pv_1[i * Init_ibr_N + 26]
        repca_Vref_1 = x_ibr_pv_1[i * Init_ibr_N + 27]
        repca_Qref_1 = x_ibr_pv_1[i * Init_ibr_N + 28]
        repca_Freq_ref_1 = x_ibr_pv_1[i * Init_ibr_N + 29]
        repca_Plant_pref_1 = x_ibr_pv_1[i * Init_ibr_N + 30]
        repca_LineMW_1 = x_ibr_pv_1[i * Init_ibr_N + 31]
        repca_LineMvar_1 = x_ibr_pv_1[i * Init_ibr_N + 32]
        repca_LineMVA_1 = x_ibr_pv_1[i * Init_ibr_N + 33]
        repca_QVdbout_1 = x_ibr_pv_1[i * Init_ibr_N + 34]
        repca_fdbout_1 = x_ibr_pv_1[i * Init_ibr_N + 35]
        repca_vq2qPI_1 = x_ibr_pv_1[i * Init_ibr_N + 36]
        repca_p2pPI_1 = x_ibr_pv_1[i * Init_ibr_N + 37]

        # vm is from outside, va and vf are from PLL
        Vm = x_bus_pv_1[ibrbus_idx * bus_odr + 4]
        Va = x_bus_pv_1[ibrbus_idx * bus_odr + 1]
        Vf = x_bus_pv_1[ibrbus_idx * bus_odr + 2]

        # REGCA
        nx_regca_Vap = Va
        nx_regca_Vmp = Vm

        i1_temp = np.maximum(0.0, (Vm - ibr_regca_Volim[i]) * ibr_regca_Khv[i])
        nx_regca_i1 = i1_temp

        if Vm < ibr_regca_Lvpnt0[i]:
            i2_temp = 0.0
        elif Vm > ibr_regca_Lvpnt1[i]:
            i2_temp = 1.0
        else:
            i2_temp = (Vm - ibr_regca_Lvpnt0[i]) / (ibr_regca_Lvpnt1[i] - ibr_regca_Lvpnt0[i])

        nx_regca_i2 = i2_temp

        Ipcmd = reecb_Ipcmd_1
        Iqcmd = reecb_Iqcmd_1

        s1_temp = regca_s1_1 + (Iqcmd - regca_s1_1) / ibr_regca_Tg[i] * ts
        if Init_ibr_regca_Qgen0[i] > 0:
            if s1_temp > regca_s1_1 + ibr_regca_Iqrmax[i] * ts:
                s1_temp = regca_s1_1 + ibr_regca_Iqrmax[i] * ts
        else:
            if s1_temp < regca_s1_1 + ibr_regca_Iqrmin[i] * ts:
                s1_temp = regca_s1_1 + ibr_regca_Iqrmin[i] * ts
        nx_regca_s1 = s1_temp

        s2_temp = regca_s2_1 + (regca_Vmp_1 - regca_s2_1) / ibr_regca_Tfltr[i] * ts
        nx_regca_s2 = s2_temp

        if s2_temp < ibr_regca_Zerox[i]:
            lvpl = 0.0
        elif s2_temp > ibr_regca_Brkpt[i]:
            lvpl = 1.0
        else:
            lvpl = (s2_temp - ibr_regca_Zerox[i]) / (ibr_regca_Brkpt[i] - ibr_regca_Zerox[i])

        tempin1 = Ipcmd - regca_s0_1
        if regca_s0_1 > 0:
            if (tempin1 - regca_ip2rr) / ts > ibr_regca_Rrpwr[i]:
                tempin1 = ibr_regca_Rrpwr[i] * ts + regca_ip2rr
        else:
            if (tempin1 - regca_ip2rr) / ts < - ibr_regca_Rrpwr[i]:
                tempin1 = - ibr_regca_Rrpwr[i] * ts + regca_ip2rr

        s0_temp = regca_s0_1 + tempin1 / ibr_regca_Tg[i] * ts
        if s0_temp > lvpl:
            s0_temp = lvpl

        nx_regca_s0 = s0_temp
        nx_regca_ip2rr = tempin1

        # REECB ------------------------------------------------------------
        if ibr_reecb_PQFLAG[i] == 0:
            if np.square(ibr_reecb_Imax[i]) < Iqcmd * Iqcmd:
                print('error!')
            Ipmax = np.sqrt(np.square(ibr_reecb_Imax[i]) - Iqcmd * Iqcmd)
            Ipmin = 0.0
            Iqmax = ibr_reecb_Imax[i]
            Iqmin = -ibr_reecb_Imax[i]
        else:
            Ipmax = ibr_reecb_Imax[i]
            Ipmin = 0.0
            Iqmax = np.sqrt(np.square(ibr_reecb_Imax[i]) - Ipcmd * Ipcmd)
            Iqmin = -ibr_reecb_Imax[i]

        if (Vm < ibr_reecb_Vdip[i]) | (Vm > ibr_reecb_Vup[i]):
            Voltage_dip = 1
        else:
            Voltage_dip = 0

        s0_temp = reecb_s0_1 + (Vm - reecb_s0_1) / ibr_reecb_Trv[i] * ts
        nx_reecb_s0 = s0_temp

        v2_temp = Init_ibr_reecb_Vref0[i] - s0_temp
        if (v2_temp <= ibr_reecb_dbd2[i]) & (v2_temp >= ibr_reecb_dbd1[i]):
            v2_temp = 0.0
        else:
            if v2_temp > ibr_reecb_dbd2[i]:
                v2_temp = v2_temp - ibr_reecb_dbd2[i]
            if v2_temp < ibr_reecb_dbd1[i]:
                v2_temp = v2_temp - ibr_reecb_dbd1[i]

        Iqv = v2_temp * ibr_reecb_Kqv[i]

        Iqinj = Iqv
        if Iqv > ibr_reecb_Iqhl[i]:
            Iqinj = ibr_reecb_Iqhl[i]
        if Iqv < ibr_reecb_Iqll[i]:
            Iqinj = ibr_reecb_Iqll[i]

        s1_temp = reecb_s1_1 + (pe - reecb_s1_1) / ibr_reecb_Tp[i] * ts
        nx_reecb_s1 = s1_temp

        if ibr_reecb_PFFLAG[i] == 1:
            Q0 = s1_temp * np.tan(Init_ibr_reecb_pfaref[i])
        else:
            Q0 = repca_s3_1
        nx_reecb_Qext = repca_s3_1

        Q1 = Q0 - qe
        if Q0 > ibr_reecb_Qmax[i]:
            Q1 = ibr_reecb_Qmax[i] - qe
        if Q0 < ibr_reecb_Qmin[i]:
            Q1 = ibr_reecb_Qmin[i] - qe
        nx_reecb_q2vPI = Q1

        dQ1dt = (Q1 - reecb_q2vPI_1) / ts
        if Voltage_dip == 1:
            s2_temp = reecb_s2_1
        else:
            s2_temp = reecb_s2_1 + (dQ1dt * ibr_reecb_Kqp[i] + Q1 * ibr_reecb_Kqi[i]) * ts
            if s2_temp > ibr_reecb_Vmax[i]:
                s2_temp = ibr_reecb_Vmax[i]
            if s2_temp < ibr_reecb_Vmin[i]:
                s2_temp = ibr_reecb_Vmin[i]
        nx_reecb_s2 = s2_temp

        if ibr_reecb_VFLAG[i] == 1:
            V0 = s2_temp
        else:
            V0 = Q0

        if V0 > ibr_reecb_Vmax[i]:
            V0 = ibr_reecb_Vmax[i]
        if V0 < ibr_reecb_Vmin[i]:
            V0 = ibr_reecb_Vmin[i]
        V1 = V0 - s0_temp
        nx_reecb_v2iPI = V1

        dV1dt = (V1 - reecb_v2iPI_1) / ts
        if Voltage_dip == 1:
            s3_temp = reecb_s3_1
        else:
            s3_temp = reecb_s3_1 + (dV1dt * ibr_reecb_Kvp[i] + V1 * ibr_reecb_Kvi[i]) * ts
            if s3_temp > Iqmax:
                s3_temp = Iqmax
            if s3_temp < Iqmin:
                s3_temp = Iqmin
        nx_reecb_s3 = s3_temp

        V3 = max(s0_temp, 0.01)
        if Voltage_dip == 1:
            s4_temp = reecb_s4_1
        else:
            s4_temp = reecb_s4_1 + (Q0 / V3 - reecb_s4_1) / ibr_reecb_Tiq[i] * ts
        nx_reecb_s4 = s4_temp

        if ibr_reecb_QFLAG[i] == 1:
            i2_temp = s3_temp
        else:
            i2_temp = s4_temp

        Iqcmd = i2_temp + Iqinj
        if Iqcmd > Iqmax:
            Iqcmd = Iqmax
        if Iqcmd < Iqmin:
            Iqcmd = Iqmin
        nx_reecb_Iqcmd = Iqcmd

        if ibr_repca_FFlag[i] == 1:
            Pref = repca_s6_1
        else:
            Pref = Init_ibr_repca_Pref_out[i]

        dPdt = (Pref - reecb_Pref_1) / ts
        if dPdt > ibr_reecb_dPmax[i]:
            Pref = ibr_reecb_dPmax[i] * ts + reecb_Pref_1
        if dPdt < ibr_reecb_dPmin[i]:
            Pref = ibr_reecb_dPmin[i] * ts + reecb_Pref_1
        nx_reecb_Pref = Pref

        if Voltage_dip == 1:
            s5_temp = reecb_s5_1
        else:
            s5_temp = reecb_s5_1 + (Pref - reecb_s5_1) / ibr_reecb_Tpord[i] * ts
            if s5_temp > ibr_reecb_Pmax[i]:
                s5_temp = ibr_reecb_Pmax[i]
            if s5_temp < ibr_reecb_Pmin[i]:
                s5_temp = ibr_reecb_Pmin[i]
        nx_reecb_s5 = s5_temp

        Ipcmd = s5_temp / V3
        if Ipcmd > Ipmax:
            Ipcmd = Ipmax
        if Ipcmd < Ipmin:
            Ipcmd = Ipmin

        nx_reecb_Ipcmd = Ipcmd

        # REPCA -----------------------------------------------------
        f_temp = repca_Freq_ref_1 - Vf
        if (f_temp <= ibr_repca_fdbd2[i]) & (f_temp >= ibr_repca_fdbd1[i]):
            f_temp = 0.0
        else:
            if f_temp > ibr_repca_fdbd2[i]:
                f_temp = f_temp - ibr_repca_fdbd2[i]
            if f_temp < ibr_repca_fdbd1[i]:
                f_temp = f_temp - ibr_repca_fdbd1[i]
        nx_repca_fdbout = f_temp
        pfdroop = np.minimum(f_temp * ibr_repca_Ddn[i], 0.0) + np.maximum(f_temp * ibr_repca_Dup[i], 0.0)

        s4_temp = repca_s4_1 + (repca_LineMW_1 - repca_s4_1) / ibr_repca_Tp[i] * ts
        nx_repca_s4 = s4_temp

        P1 = repca_Plant_pref_1 - s4_temp + pfdroop
        if P1 > ibr_repca_femax[i]:
            P1 = ibr_repca_femax[i]
        if P1 < ibr_repca_femin[i]:
            P1 = ibr_repca_femin[i]
        nx_repca_p2pPI = P1

        dP1dt = (P1 - repca_p2pPI_1) / ts
        s5_temp = repca_s5_1 + (dP1dt * ibr_repca_Kpg[i] + P1 * ibr_repca_Kig[i]) * ts
        if s5_temp > ibr_repca_Pmax[i]:
            s5_temp = ibr_repca_Pmax[i]
        if s5_temp < ibr_repca_Pmin[i]:
            s5_temp = ibr_repca_Pmin[i]
        nx_repca_s5 = s5_temp

        s6_temp = repca_s6_1 + (s5_temp - repca_s6_1) / ibr_repca_Tg[i] * ts
        nx_repca_s6 = s6_temp

        Sbranch = complex(repca_LineMW_1, repca_LineMvar_1)
        Vcom = complex(Vm * np.cos(Va), Vm * np.sin(Va))
        Ibranch = np.conj(Sbranch / Vcom)

        V1_in1 = np.abs(Vcom - complex(ibr_repca_Rc[i], ibr_repca_Xc[i]) * Ibranch)
        V1_in0 = Vm + repca_LineMvar_1 * ibr_repca_Kc[i]

        if ibr_repca_VCFlag[i] == 0:
            V1 = V1_in0
        else:
            V1 = V1_in1

        s0_temp = repca_s0_1 + (V1 - repca_s0_1) / ibr_repca_Tfltr[i] * ts
        nx_repca_s0 = s0_temp
        Q1_in1 = repca_Vref_1 - s0_temp

        s1_temp = repca_s1_1 + (repca_LineMvar_1 - repca_s1_1) / ibr_repca_Tfltr[i] * ts
        nx_repca_s1 = s1_temp
        Q1_in0 = repca_Qref_1 - s1_temp

        if ibr_repca_RefFlag[i] == 0:
            Q1_in = Q1_in0
        else:
            Q1_in = Q1_in1

        if (Q1_in <= ibr_repca_dbd2[i]) & (Q1_in >= ibr_repca_dbd1[i]):
            Q1_in = 0.0
        else:
            if Q1_in > ibr_repca_dbd2[i]:
                Q1_in = Q1_in - ibr_repca_dbd2[i]
            if Q1_in < ibr_repca_dbd1[i]:
                Q1_in = Q1_in - ibr_repca_dbd1[i]

        nx_repca_QVdbout = Q1_in

        Q1 = Q1_in
        if Q1_in > ibr_repca_emax[i]:
            Q1 = ibr_repca_emax[i]
        if Q1_in < ibr_repca_emin[i]:
            Q1 = ibr_repca_emin[i]
        dQ1dt = (Q1 - repca_vq2qPI_1) / ts

        nx_repca_vq2qPI = Q1

        if Vm < ibr_repca_Vfrz[i]:
            s2_temp = repca_s2_1
        else:
            s2_temp = repca_s2_1 + (dQ1dt * ibr_repca_Kp[i] + Q1 * ibr_repca_Ki[i]) * ts
            if s2_temp > ibr_repca_Qmax[i]:
                s2_temp = ibr_repca_Qmax[i]
            if s2_temp < ibr_repca_Qmin[i]:
                s2_temp = ibr_repca_Qmin[i]
        nx_repca_s2 = s2_temp

        ds2dt = (s2_temp - repca_s2_1) / ts
        s3_temp = repca_s3_1 + (ibr_repca_Tft[i] * ds2dt + repca_s2_1 - repca_s3_1) / ibr_repca_Tfv[i] * ts
        nx_repca_s3 = s3_temp

        nx_repca_LineMW = pe
        nx_repca_LineMvar = qe
        nx_repca_LineMVA = np.abs(complex(pe, qe))

        # set point for V, Q, Freq and pref
        nx_repca_Vref = repca_Vref_1
        nx_repca_Qref = repca_Qref_1
        nx_repca_Freq_ref = repca_Freq_ref_1
        nx_repca_Plant_pref = repca_Plant_pref_1

        # # bypass ibr dynamic
        # nx_regca_s0 = regca_s0_1
        # nx_regca_s1 = regca_s1_1
        # nx_regca_i1 = regca_i1_1
        # nx_regca_i2 = regca_i2_1

        idx = Init_ibr_N * i
        x_ibr_pv_1[idx] = nx_regca_s0
        x_ibr_pv_1[idx + 1] = nx_regca_s1
        x_ibr_pv_1[idx + 2] = nx_regca_s2
        x_ibr_pv_1[idx + 3] = nx_regca_Vmp
        x_ibr_pv_1[idx + 4] = nx_regca_Vap
        x_ibr_pv_1[idx + 5] = nx_regca_i1
        x_ibr_pv_1[idx + 6] = nx_regca_i2
        x_ibr_pv_1[idx + 7] = nx_regca_ip2rr

        x_ibr_pv_1[idx + 8] = nx_reecb_s0
        x_ibr_pv_1[idx + 9] = nx_reecb_s1
        x_ibr_pv_1[idx + 10] = nx_reecb_s2
        x_ibr_pv_1[idx + 11] = nx_reecb_s3
        x_ibr_pv_1[idx + 12] = nx_reecb_s4
        x_ibr_pv_1[idx + 13] = nx_reecb_s5
        x_ibr_pv_1[idx + 14] = nx_reecb_Ipcmd
        x_ibr_pv_1[idx + 15] = nx_reecb_Iqcmd
        x_ibr_pv_1[idx + 16] = nx_reecb_Pref
        x_ibr_pv_1[idx + 17] = nx_reecb_Qext
        x_ibr_pv_1[idx + 18] = nx_reecb_q2vPI
        x_ibr_pv_1[idx + 19] = nx_reecb_v2iPI

        x_ibr_pv_1[idx + 20] = nx_repca_s0
        x_ibr_pv_1[idx + 21] = nx_repca_s1
        x_ibr_pv_1[idx + 22] = nx_repca_s2
        x_ibr_pv_1[idx + 23] = nx_repca_s3
        x_ibr_pv_1[idx + 24] = nx_repca_s4
        x_ibr_pv_1[idx + 25] = nx_repca_s5
        x_ibr_pv_1[idx + 26] = nx_repca_s6
        x_ibr_pv_1[idx + 27] = nx_repca_Vref
        x_ibr_pv_1[idx + 28] = nx_repca_Qref
        x_ibr_pv_1[idx + 29] = nx_repca_Freq_ref
        x_ibr_pv_1[idx + 30] = nx_repca_Plant_pref
        x_ibr_pv_1[idx + 31] = nx_repca_LineMW
        x_ibr_pv_1[idx + 32] = nx_repca_LineMvar
        x_ibr_pv_1[idx + 33] = nx_repca_LineMVA
        x_ibr_pv_1[idx + 34] = nx_repca_QVdbout
        x_ibr_pv_1[idx + 35] = nx_repca_fdbout
        x_ibr_pv_1[idx + 36] = nx_repca_vq2qPI
        x_ibr_pv_1[idx + 37] = nx_repca_p2pPI

        x_ibr_pv_1[idx + 38] = Vf
        x_ibr_pv_1[idx + 39] = pe
        x_ibr_pv_1[idx + 40] = qe

    return x_ibr_pv_1


## WARNING: If parallelized, this function contains race conditions!!
@numba.jit(nopython=True, nogil=True, boundscheck=False, parallel=False)
def numba_updateIhis(brch_Ihis, Vsol, Init_net_coe0, nnodes):
    node_Ihis = np.zeros(nnodes)
    brch_Ipre = np.zeros(len(Init_net_coe0))

    for i in range(len(brch_Ihis)):
        Fidx = int(Init_net_coe0[i, 0].real)
        Tidx = int(Init_net_coe0[i, 1].real)

        if Init_net_coe0[i, 1] == -1:
            if Init_net_coe0[i, 2] == 0:
                continue
            brch_Ipre[i] = Vsol[Fidx] / Init_net_coe0[i, 2].real + brch_Ihis[i]
            brch_Ihis_temp = Init_net_coe0[i, 3] * brch_Ipre[i] + Init_net_coe0[i, 4] * Vsol[Fidx]
        else:
            brch_Ipre[i] = (Vsol[Fidx] - Vsol[Tidx]) / Init_net_coe0[i, 2].real + brch_Ihis[i]
            brch_Ihis_temp = Init_net_coe0[i, 3] * brch_Ipre[i] + Init_net_coe0[i, 4] * (Vsol[Fidx] - Vsol[Tidx])
            node_Ihis[Tidx] += brch_Ihis_temp.real
        brch_Ihis[i] = brch_Ihis_temp.real
        node_Ihis[Fidx] -= brch_Ihis_temp.real
    return (brch_Ipre, node_Ihis)
