import json
import numpy as np
import os
import time

from Lib_BW import DyData, EmtSimu, Initialize, PFData
from partitionutil import form_bbd
from serial_bbd_matrix import schur_bbd_lu

from preprocessscript import get_json_pkl

import pickle
import scipy.sparse as sp
import scipy.sparse.linalg as la


# import networkx
class storage:
    """
    storage
    """
    def __init__(self, **entries):
        self.__dict__.update(entries)


def get_json_pkl(filename):
    """

    :param filename:
    :return:
    """
    f = open(filename, )
    data = json.load(f)
    for x in data.keys():
        if type(data[x]) != list:
            pass
        else:
            try:
                if "j" in data[x][0]:
                    tmp = [complex(y) for y in data[x]]
                    data[x] = np.array(tmp)
                else:
                    tmp = data[x]
                    data[x] = np.array(tmp)
            except Exception as e:
                tmp = data[x]
                data[x] = np.array(tmp)
    pfd = storage(**data)
    return pfd


def load_pfd(filename):
    """

    :param filename:
    :return:
    """
    return PFData.load_from_json(get_json_pkl(filename))


def initialize_emt(workingfolder, systemN, N_row, N_col, ts, Tlen, mode='bbd', nparts=4):
    """

    :param workingfolder:
    :param systemN:
    :param N_row:
    :param N_col:
    :param ts:
    :param Tlen:
    :param mode:
    :param nparts:
    :return:
    """
    print("Running simulation for system {:d} in layout {:d} x {:d}".format(
        systemN, N_row, N_col))

    if systemN == 1:
        pfd_name = 'pfd_4_' + str(N_row) + '_' + str(N_col)
    elif systemN == 2:
        pfd_name = 'pfd_9_' + str(N_row) + '_' + str(N_col)
    elif systemN == 3:
        pfd_name = 'pfd_39_' + str(N_row) + '_' + str(N_col)
    elif systemN == 4:
        pfd_name = 'pfd_179_' + str(N_row) + '_' + str(N_col)
    elif systemN == 5:
        pfd_name = 'pfd_240_' + str(N_row) + '_' + str(N_col)
    elif systemN == 6:
        pfd_name = 'pfd_2area_' + str(N_row) + '_' + str(N_col)
    else:
        pfd_name = []
    filename = os.path.join(workingfolder, 'cases', pfd_name + '.json')
    pfd = load_pfd(filename)

    # load dynamic data in a certain format
    if systemN == 1:
        fdyd = os.path.join('2gen_psse', '2gen.xlsx')
    elif systemN == 2:
        fdyd = os.path.join('9bus_psse', '9bus.xlsx')
    elif systemN == 3:
        fdyd = os.path.join('39bus_psse', '39bus.xls')
    elif systemN == 4:
        fdyd = os.path.join('179bus_psse', '179bus.xlsx')
    elif systemN == 5:
        fdyd = os.path.join('240bus_psse', '240bus.xls')
    elif systemN == 6:
        fdyd = os.path.join('2area_psse', 'twoarea.xls')
    else:
        pass

    print('power flow loaded')

    file_dydata = os.path.join(workingfolder, 'models', fdyd)
    dyd0 = DyData()
    dyd0.getdata(file_dydata, pfd, N_row * N_col)

    print('dyn data loaded')

    if N_row * N_col > 1:
        dyd = dyd0.spreaddyd(pfd, dyd0, N_row * N_col)
    else:
        dyd = dyd0

    print('dyn data extended')

    dyd.ToEquiCirData(pfd, dyd)

    print('converted to gen ec data')

    # Claim an instance of EmtSimu class
    emt = EmtSimu(len(pfd.gen_bus), len(pfd.ibr_bus), len(pfd.bus_num), len(pfd.load_bus))
    emt.ts = ts  # second
    emt.Tlen = Tlen  # second

    # initialize three-phase system
    # ti_0 = time.time()
    ini = Initialize(pfd, dyd)
    # ti_1 = time.time()
    ini.InitNet(pfd, emt.ts, emt.loadmodel_option)
    print('Net initialized')
    # ti_2 = time.time()
    ini.InitMac(pfd, dyd)
    print('Mac initialized')
    # ti_3 = time.time()
    ini.InitExc(pfd, dyd)
    print('Exc initialized')
    # ti_4 = time.time()
    ini.InitGov(pfd, dyd)
    print('Gov initialized')
    # ti_5 = time.time()
    ini.InitPss(pfd, dyd)
    print('Pss initialized')
    # ti_6 = time.time()
    ini.InitREGCA(pfd, dyd)
    # ti_7 = time.time()
    ini.InitREECB(pfd, dyd)
    # ti_8 = time.time()
    ini.InitREPCA(pfd, dyd)
    ini.InitPLL(pfd)
    # ti_9 = time.time()
    ini.InitBusMea(pfd)
    # ti_10 = time.time()
    ini.InitLoad(pfd)
    # ti_11 = time.time()
    ini.CheckMacEq(pfd, dyd)
    # ti_12 = time.time()
    ini.MergeMacG(pfd, dyd, emt.ts, [], mode=mode, nparts=nparts)
    print('Merged MacG')
    # ti_13 = time.time()

    # elapsed = ti_13 - ti_0
    # tini_str = """
    # Construct:   {:10.2e} {:8.2%}
    # InitNet:     {:10.2e} {:8.2%}
    # InitMac:     {:10.2e} {:8.2%}
    # InitExc:     {:10.2e} {:8.2%}
    # InitGov:     {:10.2e} {:8.2%}
    # InitPss:     {:10.2e} {:8.2%}
    # InitRegca:   {:10.2e} {:8.2%}
    # InitReecb:   {:10.2e} {:8.2%}
    # InitRepca:   {:10.2e} {:8.2%}
    # InitBusMea:  {:10.2e} {:8.2%}
    # InitLoad:    {:10.2e} {:8.2%}
    # CheckMacEq:  {:10.2e} {:8.2%}
    # MergeMacG:   {:10.2e} {:8.2%}
    # Init:        {:10.2e}
    # """.format(
    #     ti_1 - ti_0, (ti_1 - ti_0)/elapsed,
    #     ti_2 - ti_1, (ti_2 - ti_1)/elapsed,
    #     ti_3 - ti_2, (ti_3 - ti_2)/elapsed,
    #     ti_4 - ti_3, (ti_4 - ti_3)/elapsed,
    #     ti_5 - ti_4, (ti_5 - ti_4)/elapsed,
    #     ti_6 - ti_5, (ti_6 - ti_5)/elapsed,
    #     ti_7 - ti_6, (ti_7 - ti_6)/elapsed,
    #     ti_8 - ti_7, (ti_8 - ti_7) / elapsed,
    #     ti_9 - ti_8, (ti_9 - ti_8) / elapsed,
    #     ti_10 - ti_9, (ti_10 - ti_9) / elapsed,
    #     ti_11 - ti_10, (ti_11 - ti_10) / elapsed,
    #     ti_12 - ti_11, (ti_12 - ti_11) / elapsed,
    #     ti_13 - ti_12, (ti_13 - ti_12) / elapsed,
    #     elapsed
    # )
    # print(tini_str)
    ascii_art = """
     ____                 _____ __  __ _____ 
    |  _ \ __ _ _ __ __ _| ____|  \/  |_   _|
    | |_) / _` | '__/ _` |  _| | |\/| | | |  
    |  __/ (_| | | | (_| | |___| |  | | | |   copyright: NREL
    |_|   \__,_|_|  \__,_|_____|_|  |_| |_|   email: ParaEMT@nrel.gov
    """
    print(ascii_art)
    print('System initialized')
    print('Compiling the code')
    emt.preprocess(ini, pfd, dyd)
    return (pfd, ini, dyd, emt)


def initialize_from_snp(input_snp, netMod, nparts):
    ascii_art = """
     ____                 _____ __  __ _____ 
    |  _ \ __ _ _ __ __ _| ____|  \/  |_   _|
    | |_) / _` | '__/ _` |  _| | |\/| | | |  
    |  __/ (_| | | | (_| | |___| |  | | | |   copyright: NREL
    |_|   \__,_|_|  \__,_|_____|_|  |_| |_|   email: ParaEMT@nrel.gov
    """
    print(ascii_art)
    with open(input_snp, 'rb') as f:
        pfd, dyd, ini, emt = pickle.load(f)
        emt.t = [0.0]
        ini.Init_net_G0 = sp.coo_matrix((ini.Init_net_G0_data, (ini.Init_net_G0_rows, ini.Init_net_G0_cols)),
                                        shape=(ini.Init_net_N, ini.Init_net_N)
                                        ).tolil()
        if netMod == 'inv':
            ini.Init_net_G0_inv = la.inv(ini.Init_net_G0.tocsc())
        elif netMod == 'lu':
            ini.Init_net_G0_lu = la.splu(ini.Init_net_G0.tocsc())
        elif netMod == 'bbd':
            (BBD, idx_order, inv_order) = form_bbd(ini, nparts)
            ini.index_order = idx_order
            ini.inv_order = inv_order
            ini.Init_net_G0_bbd_lu = schur_bbd_lu(BBD)
        else:
            raise ValueError('Unrecognized mode: {}'.format(netMod))
        ini.admittance_mode = netMod
    print('System initialized')
    print('Compiling the code')
    return (pfd, ini, dyd, emt)
