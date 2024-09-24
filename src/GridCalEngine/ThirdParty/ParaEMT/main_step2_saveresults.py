# --------------------------------------------
#  EMT solver plotting function
#  2020-2024 Bin Wang, Min Xiong
#  Last modified: 8/15/24,
# --------------------------------------------
import pickle
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():
    # read sim data
    systemN = 6
    ts = 50e-6  # time step

    output_snp_ful = 'sim_snp_S' + str(systemN) + '_' + str(int(ts * 1e6)) + 'u.pkl'
    output_snp_1pt = 'sim_snp_S' + str(systemN) + '_' + str(int(ts * 1e6)) + 'u_1pt.pkl'
    output_res = 'sim_res_S' + str(systemN) + '_' + str(int(ts * 1e6)) + 'u.pkl'

    # with open(output_snp_ful,'rb') as f:
    with open(output_res, 'rb') as f:
        pfd, dyd, ini, emt = pickle.load(f)

    Vbus = []
    for j in range(3):  # Three phase
        if j == 0:
            V_phase = 'Va'
        if j == 1:
            V_phase = 'Vb'
        if j == 2:
            V_phase = 'Vc'
        for i in range(len(pfd.bus_num)):
            Vbus.append(str(pfd.bus_num[i]) + '_' + pfd.bus_name[i] + '_' + V_phase)
    dfbus = pd.DataFrame(np.transpose(emt.v))
    dfbus.to_csv("emt_3phaseV.csv", header=Vbus, index=False)

    Cbus = []
    for i in range(len(pfd.bus_num)):
        Cbus.append(str(pfd.bus_num[i]) + '_' + pfd.bus_name[i] + '_' + 'ze')
        Cbus.append(str(pfd.bus_num[i]) + '_' + pfd.bus_name[i] + '_' + 'de')
        Cbus.append(str(pfd.bus_num[i]) + '_' + pfd.bus_name[i] + '_' + 'we')
        Cbus.append(str(pfd.bus_num[i]) + '_' + pfd.bus_name[i] + '_' + 'vt')
        Cbus.append(str(pfd.bus_num[i]) + '_' + pfd.bus_name[i] + '_' + 'vtm')
        Cbus.append(str(pfd.bus_num[i]) + '_' + pfd.bus_name[i] + '_' + 'dvtm')

    if len(pfd.bus_num) > 0:
        dfbus = pd.DataFrame(np.transpose(emt.x_bus))
        dfbus.to_csv("emt_x_bus.csv", header=Cbus, index=False)

    C = ['Time']
    for i in range(dyd.gen_genrou_n):
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'dt')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'w')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'id')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'iq')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'ifd')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'i1d')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'i1q')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'i2q')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'ed')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'eq')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'psyd')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'psyq')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'psyfd')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'psy1q')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'psy1d')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'psy2q')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'te')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_' + 'qe')

    dfsgbase = pd.DataFrame(np.transpose(pfd.gen_MVA_base))
    dfsgbase.to_csv("emt_gen_mvabase.csv")

    ibrbase = pd.DataFrame(np.transpose(pfd.ibr_MVA_base))
    ibrbase.to_csv("emt_ibr_mvabase.csv")

    for i in range(dyd.exc_sexs_n):
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_SEXS_' + 'v1')
        C.append(str(pfd.gen_bus[i]) + '_' + pfd.gen_id[i] + '_SEXS_' + 'EFD')

    for i in range(dyd.gov_tgov1_n):
        j = int(dyd.gov_tgov1_idx[i])
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_TGOV1_' + 'P1')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_TGOV1_' + 'P2')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_TGOV1_' + 'Pm')

    for i in range(dyd.gov_hygov_n):
        j = int(dyd.gov_hygov_idx[i])
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_HYGOV_' + 'xe')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_HYGOV_' + 'xc')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_HYGOV_' + 'xg')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_HYGOV_' + 'xq')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_HYGOV_' + 'Pm')

    for i in range(dyd.gov_gast_n):
        j = int(dyd.gov_gast_idx[i])
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_GAST_' + 'P1')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_GAST_' + 'P2')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_GAST_' + 'P3')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_GAST_' + 'Pm')

    for i in range(dyd.pss_ieeest_n):
        j = int(dyd.pss_ieeest_idx[i])
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'y1')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'y2')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'y3')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'y4')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'y5')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'y6')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'y7')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'x1')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'x2')
        C.append(str(pfd.gen_bus[j]) + '_' + pfd.gen_id[j] + '_IEEEST_' + 'vs')

    Cibr = []
    for i in range(dyd.ibr_n):
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_regca_' + 's0')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_regca_' + 's1')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_regca_' + 's2')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_regca_' + 'Vmp')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_regca_' + 'Vap')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_regca_' + 'i1')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_regca_' + 'i2')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_regca_' + 'ip2rr')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 's0')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 's1')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 's2')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 's3')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 's4')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 's5')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 'Ipcmd')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 'Iqcmd')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 'Pref')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 'Qref')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 'q2vPI')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_reecb_' + 'v2iPI')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 's0')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 's1')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 's2')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 's3')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 's4')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 's5')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 's6')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'Vref')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'Qref')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'Freq_ref')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'Plant_ref')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'LineMW')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'LineMvar')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'LineMVA')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'QVdbout')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'fdbout')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'vq2qPI')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'p2pPI')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'Vf')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'Pe')
        Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_repca_' + 'Qe')
        # Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_pll_' + 'ze')
        # Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_pll_' + 'de')
        # Cibr.append(str(pfd.ibr_bus[i]) + '_' + pfd.ibr_id[i] + '_pll_' + 'we')

    t = emt.t.reshape(len(emt.t), 1)
    x = np.insert(np.transpose(emt.x), 0, np.transpose(t), axis=1)
    df = pd.DataFrame(x)
    df.to_csv("emt_x.csv", header=C, index=False)

    if len(pfd.ibr_bus) > 0:
        dfibr = pd.DataFrame(np.transpose(emt.x_ibr))
        dfibr.to_csv("emt_xibr.csv", header=Cibr, index=False)

    Cload = []
    for i in range(len(pfd.load_bus)):
        Cload.append(str(pfd.load_bus[i]) + '_' + pfd.load_id[i] + '_' + 'ZL_mag')
        Cload.append(str(pfd.load_bus[i]) + '_' + pfd.load_id[i] + '_' + 'ZL_ang')
        Cload.append(str(pfd.load_bus[i]) + '_' + pfd.load_id[i] + '_' + 'PL')
        Cload.append(str(pfd.load_bus[i]) + '_' + pfd.load_id[i] + '_' + 'QL')
    if len(pfd.load_bus) > 0:
        dfLd = pd.DataFrame(np.transpose(emt.x_load))
        dfLd.to_csv("emt_x_load.csv", header=Cload, index=False)


main()
