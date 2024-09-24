# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from __future__ import annotations

import time
import numpy as np
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit, compile_numerical_circuit_at
from GridCalEngine.ThirdParty.ParaEMT.Lib_BW import PFData, DyData, Initialize, EmtSimu
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_zip_power


def get_pf_data(grid: MultiCircuit,
                nc: NumericalCircuit,
                pf_results: PowerFlowResults) -> PFData:
    """
    Compile GridCal data at t_idx for ParaEMT
    :param grid: MultiCircuit
    :param nc: NumericalCircuit
    :param pf_results: PowerFlowResults
    :return: PFData instance
    """

    # start filling the ParaEMT data
    emt_data = PFData()

    # system data
    emt_data.basemva = [grid.Sbase]
    emt_data.ws = [2.0 * np.pi * grid.fBase]

    # bus data
    emt_data.bus_num = np.arange(nc.nbus) + 1
    emt_data.bus_type = nc.bus_data.bus_types
    emt_data.bus_Vm = np.abs(pf_results.voltage)
    emt_data.bus_Va = np.angle(pf_results.voltage)  # TODO: deg or rad? seems to be RAD
    emt_data.bus_kV = nc.bus_data.Vnom * emt_data.bus_Vm
    emt_data.bus_basekV = nc.bus_data.Vnom
    emt_data.bus_name = nc.bus_data.names

    # load data
    S_load = compute_zip_power(
        S=nc.load_data.C_bus_elm @ (nc.load_data.S * nc.load_data.active),
        I=nc.load_data.C_bus_elm @ (nc.load_data.I * nc.load_data.active),
        Y=nc.load_data.C_bus_elm @ (nc.load_data.Y * nc.load_data.active),
        Vm=emt_data.bus_Vm
    )
    emt_data.load_id = np.arange(nc.nload) + 1
    emt_data.load_bus = nc.load_data.get_bus_indices() + 1
    emt_data.load_Z = 1.0 / nc.load_data.Y * nc.load_data.active
    emt_data.load_I = nc.load_data.I * nc.load_data.active
    emt_data.load_P = nc.load_data.S * nc.load_data.active
    emt_data.load_MW = S_load.real
    emt_data.load_Mvar = S_load.imag

    # IBR data: inverter-based resources
    emt_data.ibr_bus = np.asarray([])
    emt_data.ibr_id = np.asarray([])
    emt_data.ibr_MW = np.asarray([])
    emt_data.ibr_Mvar = np.asarray([])
    emt_data.ibr_MVA_base = np.asarray([])

    # generator data
    emt_data.gen_id = np.arange(nc.ngen) + 1
    emt_data.gen_bus = nc.generator_data.get_bus_indices() + 1

    emt_data.gen_mod = np.zeros(nc.ngen, dtype=int)  # generator mode I suppose
    emt_data.gen_MW = nc.generator_data.p * nc.Sbase  # TODO: check units
    emt_data.gen_Mvar = np.asarray([])  # TODO figure this out fropm power flow data
    emt_data.gen_S = emt_data.gen_MW + 1j * emt_data.gen_Mvar
    emt_data.gen_MVA_base = np.asarray([])  # TODO nc.generator_data.  # fill in

    # line data
    emt_data.line_from = nc.branch_data.F + 1
    emt_data.line_to = nc.branch_data.T + 1
    emt_data.line_id = np.arange(nc.nbr) + 1
    emt_data.line_P = pf_results.Sf.real
    emt_data.line_Q = pf_results.Sf.imag
    emt_data.line_RX = (nc.branch_data.R + 1j * nc.branch_data.X) * nc.branch_data.active
    emt_data.line_chg = nc.branch_data.B * nc.branch_data.active

    # xfmr data: Transformer data alrady accounted in the line part
    emt_data.xfmr_from = np.asarray([])
    emt_data.xfmr_to = np.asarray([])
    emt_data.xfmr_id = np.asarray([])
    emt_data.xfmr_P = np.asarray([])
    emt_data.xfmr_Q = np.asarray([])
    emt_data.xfmr_RX = np.asarray([])
    emt_data.xfmr_k = np.asarray([])

    # shunt data
    emt_data.shnt_bus = nc.shunt_data.get_bus_indices() + 1
    emt_data.shnt_id = np.arange(nc.nshunt) + 1
    emt_data.shnt_gb = nc.shunt_data.Y * nc.shunt_data.active

    # switched shunt data
    emt_data.shnt_sw_bus = np.asarray([])
    emt_data.shnt_sw_gb = np.asarray([])

    return emt_data


def get_dyn_data(grid: MultiCircuit) -> DyData:
    """

    :param grid:
    :return:
    """
    dyd0 = DyData()

    return dyd0


def get_initialize_data(grid: MultiCircuit, pfd: PFData, dyd: DyData) -> Initialize:
    """

    :param grid:
    :param pfd:
    :param dyd:
    :return:
    """

    ini = Initialize(pfd, dyd)

    return ini


def get_emt_simu_data(nc: NumericalCircuit) -> EmtSimu:
    """

    :param nc:
    :return:
    """
    emt = EmtSimu(ngen=nc.ngen,
                  nibr=0,  # TODO: what is this?
                  nbus=nc.nbus,
                  nload=nc.nload)

    return emt


def run_para_emt(grid: MultiCircuit,
                 t_idx: None | int = None,
                 pf_options: PowerFlowOptions | None = None,
                 DSrate: float = 10,
                 ts: float = 50e-6,
                 Tlen: float = 20,
                 t_release_f: float = 0.0,
                 loadmodel_option: int = 1,
                 netMod: str = 'lu', ):
    """

    :param grid:
    :param t_idx: time index from the profile or None for the snapshot
    :param pf_options: PowerFlowOptions if None, default ones will be used
    :param DSrate: down sampling rate, i.e. results saved every DSrate sim steps.
    :param ts: time step in seconds
    :param Tlen: total simulation time length in seconds
    :param t_release_f:
    :param loadmodel_option: 1-const rlc, 2-const z
    :param netMod:
    :return:
    """
    if pf_options is None:
        pf_options = PowerFlowOptions()

    # compile the numerical circuit
    nc: NumericalCircuit = compile_numerical_circuit_at(grid, t_idx=t_idx)

    # compute the power flow
    pf_results: PowerFlowResults = multi_island_pf_nc(nc=nc, options=pf_options)

    pfd = get_pf_data(grid=grid, nc=nc, pf_results=pf_results)
    dyd = get_dyn_data(grid=grid)
    ini = get_initialize_data(grid=grid, pfd=pfd, dyd=dyd)
    emt = get_emt_simu_data(nc=nc)

    # -------------------------------------------------------------------------------
    # the following code comes from the file main_step1_simulation
    # -------------------------------------------------------------------------------
    t0 = time.time()

    # ctrl step change
    emt.t_sc = 100
    emt.i_gen_sc = 0
    emt.flag_exc_gov = 1  # 0 - exc, 1 - gov
    emt.dsp = - 0.02
    emt.flag_sc = 1

    # gen trip
    emt.t_gentrip = 5
    emt.i_gentrip = 0  # 0: 1032 C for WECC 240-bus
    emt.flag_gentrip = 1
    emt.flag_reinit = 1

    # Before t = t_release_f, PLL freq are fixed at synchronous freq
    emt.t_release_f = t_release_f
    emt.loadmodel_option = loadmodel_option  # 1-const rlc, 2-const z

    t1 = time.time()

    t_solve = 0.0
    t_busmea = 0.0
    t_pred = 0.0
    t_upig = 0.0
    t_upir = 0.0
    t_upil = 0.0
    t_upx = 0.0
    t_upxr = 0.0
    t_upxl = 0.0
    t_save = 0.0
    t_upih = 0.0
    Nsteps = 0

    # time loop
    tn = 0
    tsave = 0
    while tn * ts < Tlen:
        tn = tn + 1

        emt.StepChange(dyd, ini, tn)  # configure step change in exc or gov references
        emt.GenTrip(pfd, dyd, ini, tn, netMod)  # configure generation trip

        tl_0 = time.time()
        emt.predictX(pfd, dyd, emt.ts)

        tl_1 = time.time()
        emt.Igs = emt.Igs * 0
        emt.updateIg(pfd, dyd, ini)

        tl_2 = time.time()
        emt.Igi = emt.Igi * 0
        emt.Iibr = emt.Iibr * 0
        emt.updateIibr(pfd, dyd, ini)

        tl_3 = time.time()
        if emt.loadmodel_option == 1:
            pass
        else:
            emt.Il = emt.Il * 0
            emt.updateIl(pfd, dyd, tn)  # update current injection from load

        tl_4 = time.time()
        emt.solveV(ini)

        tl_5 = time.time()
        emt.BusMea(pfd, dyd, tn)  # bus measurement

        tl_6 = time.time()
        emt.updateX(pfd, dyd, ini, tn)

        tl_7 = time.time()
        emt.updateXibr(pfd, dyd, ini, ts)

        tl_8 = time.time()
        if emt.loadmodel_option == 1:
            pass
        else:
            emt.updateXl(pfd, dyd, tn)

        tl_9 = time.time()
        emt.x_pred = {0: emt.x_pred[1], 1: emt.x_pred[2], 2: emt.x_pv_1}

        if np.mod(tn, DSrate) == 0:
            tsave = tsave + 1
            # save states
            emt.t.append(tn * ts)
            print("%.4f" % emt.t[-1])

            emt.x[tsave] = emt.x_pv_1.copy()

            if len(pfd.ibr_bus) > 0:
                emt.x_ibr[tsave] = emt.x_ibr_pv_1.copy()

            if len(pfd.bus_num) > 0:
                emt.x_bus[tsave] = emt.x_bus_pv_1.copy()

            if len(pfd.load_bus) > 0:
                emt.x_load[tsave] = emt.x_load_pv_1.copy()

            emt.v[tsave] = emt.Vsol.copy()

        tl_10 = time.time()

        # re-init
        if (emt.flag_gentrip == 0) & (emt.flag_reinit == 1):
            emt.Re_Init(pfd, dyd, ini)
        else:
            emt.updateIhis(ini)

        tl_11 = time.time()

        t_pred += tl_1 - tl_0
        t_upig += tl_2 - tl_1
        t_upir += tl_3 - tl_2
        t_upil += tl_4 - tl_3
        t_solve += tl_5 - tl_4
        t_busmea += tl_6 - tl_5
        t_upx += tl_7 - tl_6
        t_upxr += tl_8 - tl_7
        t_upxl += tl_9 - tl_8
        t_save += tl_10 - tl_9
        t_upih += tl_11 - tl_10

        Nsteps += 1

    t_stop = time.time()

    # emt.dump_res(pfd, dyd, ini, SimMod, output_snp_ful, output_snp_1pt, output_res)

    elapsed = t_stop - t0
    init = t1 - t0
    loop = t_stop - t1
    timing_string = """**** Timing Info ****
        Dimension:   {:8d}
        Init:        {:10.2e} {:8.2%}
        Loop:        {:10.2e} {:8.2%} {:8d} {:8.2e}
        PredX:       {:10.2e} {:8.2%} {:8d} {:8.2e}
        UpdIG:       {:10.2e} {:8.2%} {:8d} {:8.2e}
        UpdIR:       {:10.2e} {:8.2%} {:8d} {:8.2e}
        UpdIL:       {:10.2e} {:8.2%} {:8d} {:8.2e}
        Solve:       {:10.2e} {:8.2%} {:8d} {:8.2e}
        BusMea:      {:10.2e} {:8.2%} {:8d} {:8.2e}
        UpdX:        {:10.2e} {:8.2%} {:8d} {:8.2e}
        UpdXr:       {:10.2e} {:8.2%} {:8d} {:8.2e}
        UpdXL:       {:10.2e} {:8.2%} {:8d} {:8.2e}
        Save:        {:10.2e} {:8.2%} {:8d} {:8.2e}
        UpdIH:       {:10.2e} {:8.2%} {:8d} {:8.2e}
        Total:       {:10.2e}

        """.format(ini.Init_net_G0_inv.shape[0],
                   init, init / elapsed,
                   loop, loop / elapsed, Nsteps, loop / Nsteps,
                   t_pred, t_pred / elapsed, Nsteps, t_pred / Nsteps,
                   t_upig, t_upig / elapsed, Nsteps, t_upig / Nsteps,
                   t_upir, t_upir / elapsed, Nsteps, t_upir / Nsteps,
                   t_upil, t_upil / elapsed, Nsteps, t_upil / Nsteps,
                   t_solve, t_solve / elapsed, Nsteps, t_solve / Nsteps,
                   t_busmea, t_busmea / elapsed, Nsteps, t_busmea / Nsteps,
                   t_upx, t_upx / elapsed, Nsteps, t_upx / Nsteps,
                   t_upxr, t_upxr / elapsed, Nsteps, t_upxr / Nsteps,
                   t_upxl, t_upxl / elapsed, Nsteps, t_upxl / Nsteps,
                   t_save, t_save / elapsed, Nsteps, t_save / Nsteps,
                   t_upih, t_upih / elapsed, Nsteps, t_upih / Nsteps,
                   elapsed
                   )
    print(timing_string)
