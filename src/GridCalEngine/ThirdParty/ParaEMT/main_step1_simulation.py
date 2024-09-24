# --------------------------------------------
#  EMT solver main function
#  2020-2024 Bin Wang, Min Xiong, Deepthi Vaidhynathan, Jonathan Maack
#  Last modified: 8/15/24
# --------------------------------------------

import sys
import time
import os, sys
import json
import numpy as np
from Lib_BW import *
from psutils import *
from preprocessscript import get_json_pkl

workingfolder = '.'
os.chdir(workingfolder)

def main():
    SimMod = 1  # 0 - Save a snapshot, 1 - run from a snapshot
    DSrate = 10 # down sampling rate, i.e. results saved every DSrate sim steps.

    systemN = 6 # 1: 2-gen, 2: 9-bus, 3: 39-bus, 4: 179-bus, 5: 240-bus, 6: 2-area
    N_row = 1  # haven't tested the mxn layout, so plz don't set N_row/N_col to other nums.
    N_col = 1

    ts = 50e-6  # time step, second
    Tlen = 20  # total simulation time length, second
    t_release_f = 0.0
    loadmodel_option = 1  # 1-const rlc, 2-const z
    netMod = 'lu'
    nparts = 2 # number of blocks in BBD form

    output_snp_ful = 'sim_snp_S' + str(systemN) + '_' + str(int(ts * 1e6)) + 'u.pkl'
    output_snp_1pt = 'sim_snp_S' + str(systemN) + '_' + str(int(ts * 1e6)) + 'u_1pt.pkl'
    output_res = 'sim_res_S' + str(systemN) + '_' + str(int(ts * 1e6)) + 'u.pkl'

    input_snp = 'sim_snp_S' + str(systemN) + '_' + str(int(ts * 1e6)) + 'u_1pt.pkl'

    t0 = time.time()
    if SimMod == 0:
        (pfd, ini, dyd, emt) = initialize_emt(workingfolder, systemN, N_row, N_col, ts, Tlen, mode = netMod, nparts=nparts)
    else:
        (pfd, ini, dyd, emt) = initialize_from_snp(input_snp, netMod, nparts)

    ## ---------------------- other simulation setting ----------------------------------------------------------
    # ctrl step change
    emt.t_sc = 100
    emt.i_gen_sc = 0
    emt.flag_exc_gov = 1  # 0 - exc, 1 - gov
    emt.dsp = - 0.02
    emt.flag_sc = 1

    # gen trip
    emt.t_gentrip = 5
    emt.i_gentrip = 0   # 0: 1032 C for WECC 240-bus
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
    while tn*ts < Tlen:
        tn = tn + 1

        emt.StepChange(dyd, ini, tn)                # configure step change in exc or gov references
        emt.GenTrip(pfd, dyd, ini, tn, netMod)      # configure generation trip

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
            emt.updateIl(pfd, dyd, tn)   # update current injection from load

        tl_4 = time.time()
        emt.solveV(ini)

        tl_5 = time.time()
        emt.BusMea(pfd, dyd, tn)     # bus measurement

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
        emt.x_pred = {0:emt.x_pred[1],1:emt.x_pred[2],2:emt.x_pv_1}

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

    emt.dump_res(pfd, dyd, ini, SimMod, output_snp_ful, output_snp_1pt, output_res)

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

main()
