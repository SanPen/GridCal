# --------------------------------------------
#  EMT solver library
#  2020-2024 Bin Wang, Min Xiong
#  Last modified: 08/15/2024
# --------------------------------------------
## xlrd v1.2.0 is used to support xlsx format

import math
import pickle
import sys
from functools import reduce

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as la
import xlrd

from lib_numba import (numba_predictX, numba_updateIg, numba_updateIibr, numba_updateX, numba_updateXibr, numba_BusMea,
                       numba_updateIhis, numba_InitNet)
from partitionutil import form_bbd
from serial_bbd_matrix import schur_bbd_lu

alpha = np.exp(1j * 2 * np.pi / 3)
Ainv = np.asarray([[1, 1, 1], [1, alpha * alpha, alpha], [1, alpha, alpha * alpha]]) / 3.0


# ---------------------------------------------------------------------------
# power flow data class
class PFData:
    """
    PFData
    """

    @staticmethod
    def load_from_json(storage):
        """

        :param storage:
        :return:
        """
        my_pfd = PFData()
        for k in my_pfd.__dict__.keys():
            setattr(my_pfd, k, getattr(storage, k))
        return my_pfd

    def __init__(self):
        # system data
        self.basemva = []
        self.ws = []

        # bus data
        self.bus_num = np.asarray([])
        self.bus_type = np.asarray([])
        self.bus_Vm = np.asarray([])
        self.bus_Va = np.asarray([])
        self.bus_kV = np.asarray([])
        self.bus_basekV = np.asarray([])
        self.bus_name = np.asarray([])

        # load data
        self.load_id = np.asarray([])
        self.load_bus = np.asarray([])
        self.load_Z = np.asarray([])
        self.load_I = np.asarray([])
        self.load_P = np.asarray([])
        self.load_MW = np.asarray([])
        self.load_Mvar = np.asarray([])

        # IBR data
        self.ibr_bus = np.asarray([])
        self.ibr_id = np.asarray([])
        self.ibr_MW = np.asarray([])
        self.ibr_Mvar = np.asarray([])
        self.ibr_MVA_base = np.asarray([])

        # generator data
        self.gen_id = np.asarray([])
        self.gen_bus = np.asarray([])
        self.gen_S = np.asarray([])
        self.gen_mod = np.asarray([])
        self.gen_MW = np.asarray([])
        self.gen_Mvar = np.asarray([])
        self.gen_MVA_base = np.asarray([])

        # line data
        self.line_from = np.asarray([])
        self.line_to = np.asarray([])
        self.line_id = np.asarray([])
        self.line_P = np.asarray([])
        self.line_Q = np.asarray([])
        self.line_RX = np.asarray([])
        self.line_chg = np.asarray([])

        # xfmr data
        self.xfmr_from = np.asarray([])
        self.xfmr_to = np.asarray([])
        self.xfmr_id = np.asarray([])
        self.xfmr_P = np.asarray([])
        self.xfmr_Q = np.asarray([])
        self.xfmr_RX = np.asarray([])
        self.xfmr_k = np.asarray([])

        # shunt data
        self.shnt_bus = np.asarray([])
        self.shnt_id = np.asarray([])
        self.shnt_gb = np.asarray([])

        # switched shunt data
        self.shnt_sw_bus = np.asarray([])
        self.shnt_sw_gb = np.asarray([])

    def getdata(self, psspy):
        # system data
        self.basemva = psspy.sysmva()
        self.ws = 2 * math.pi * 60

        # bus data
        self.bus_num = np.asarray(psspy.abusint(-1, 2, 'NUMBER')[1][0])
        self.bus_type = np.asarray(psspy.abusint(-1, 2, 'TYPE')[1][0])
        self.bus_Vm = np.asarray(psspy.abusreal(-1, 2, 'PU')[1][0])
        self.bus_Va = np.asarray(psspy.abusreal(-1, 2, 'ANGLED')[1][0])
        self.bus_kV = np.asarray(psspy.abusreal(-1, 2, 'KV')[1][0])
        self.bus_basekV = np.asarray(psspy.abusreal(-1, 2, 'BASE')[1][0])
        self.bus_name = psspy.abuschar(-1, 1, 'NAME')[1][0]

        # load data
        self.load_id = psspy.aloadchar(-1, 1, 'ID')[1][0]
        self.load_bus = np.asarray(psspy.aloadint(-1, 1, 'NUMBER')[1][0])
        self.load_Z = np.asarray(psspy.aloadcplx(-1, 1, 'YLACT')[1][0])
        self.load_I = np.asarray(psspy.aloadcplx(-1, 1, 'ILACT')[1][0])
        self.load_P = np.asarray(psspy.aloadcplx(-1, 1, 'MVAACT')[1][0])
        self.load_MW = self.load_Z.real + self.load_I.real + self.load_P.real
        self.load_Mvar = self.load_Z.imag + self.load_I.imag + self.load_P.imag

        # IBR data
        self.ibr_bus = np.asarray([])
        self.ibr_id = np.asarray([])
        self.ibr_MW = np.asarray([])
        self.ibr_Mvar = np.asarray([])

        # generator data
        self.gen_id = psspy.amachchar(-1, 4, 'ID')[1][0].rstrip()
        self.gen_bus = np.asarray(psspy.amachint(-1, 4, 'NUMBER')[1][0])
        self.gen_S = np.asarray(psspy.amachcplx(-1, 4, 'PQGEN')[1][0])
        self.gen_mod = np.asarray(psspy.amachint(-1, 4, 'WMOD')[1][0])
        self.gen_MW = np.round((self.gen_S.real) * 10000) / 10000
        self.gen_Mvar = np.round((self.gen_S.imag) * 10000) / 10000
        self.gen_MVA_base = np.asarray(psspy.amachreal(-1, 4, 'MBASE')[1][0])
        self.gen_status = np.asarray(psspy.amachint(-1, 4, 'STATUS')[1][0])

        gen_off = []
        for i in range(len(self.gen_id)):
            if self.gen_status[i] == 0:
                gen_off.append(i)

        self.gen_id = np.delete(self.gen_id, [gen_off])
        self.gen_bus = np.delete(self.gen_bus, [gen_off])
        self.gen_MVA_base = np.delete(self.gen_MVA_base, [gen_off])
        self.gen_S = np.delete(self.gen_S, [gen_off])
        self.gen_mod = np.delete(self.gen_mod, [gen_off])
        self.gen_MW = np.delete(self.gen_MW, [gen_off])
        self.gen_Mvar = np.delete(self.gen_Mvar, [gen_off])
        self.gen_status = np.delete(self.gen_status, [gen_off])

        ibr_idx = np.where((self.gen_mod == 1) | (self.gen_mod == 3))
        for i in range(len(ibr_idx[0])):
            last_found = ibr_idx[0][len(ibr_idx[0]) - i - 1]
            self.ibr_bus = np.append(self.ibr_bus, self.gen_bus[last_found])
            self.ibr_id = np.append(self.ibr_id, self.gen_id[last_found])
            self.ibr_MW = np.append(self.ibr_MW, self.gen_MW[last_found])
            self.ibr_Mvar = np.append(self.ibr_Mvar, self.gen_Mvar[last_found])
            self.ibr_MVA_base = np.append(self.ibr_MVA_base, self.gen_MVA_base[last_found])

            self.gen_id = np.delete(self.gen_id, [last_found])
            self.gen_bus = np.delete(self.gen_bus, [last_found])
            self.gen_MVA_base = np.delete(self.gen_MVA_base, [last_found])
            self.gen_S = np.delete(self.gen_S, [last_found])
            self.gen_mod = np.delete(self.gen_mod, [last_found])
            self.gen_MW = np.delete(self.gen_MW, [last_found])
            self.gen_Mvar = np.delete(self.gen_Mvar, [last_found])

        self.ibr_bus = np.flipud(self.ibr_bus)
        self.ibr_id = np.flipud(self.ibr_id)
        self.ibr_MW = np.flipud(self.ibr_MW)
        self.ibr_Mvar = np.flipud(self.ibr_Mvar)
        self.ibr_MVA_base = np.flipud(self.ibr_MVA_base)

        # line data
        self.line_from = np.asarray(psspy.abrnint(-1, 1, 1, 1, 1, ['FROMNUMBER'])[1][0])
        self.line_to = np.asarray(psspy.abrnint(-1, 1, 1, 1, 1, ['TONUMBER'])[1][0])
        self.line_id = psspy.abrnchar(-1, 0, 0, 1, 1, ['ID'])[1][0]
        self.line_P = np.asarray(psspy.abrnreal(-1, 1, 1, 1, 1, ['P'])[1][0])
        self.line_Q = np.asarray(psspy.abrnreal(-1, 1, 1, 1, 1, ['Q'])[1][0])
        self.line_RX = np.asarray(psspy.abrncplx(-1, 1, 1, 1, 1, ['RX'])[1][0])
        self.line_chg = np.asarray(psspy.abrnreal(-1, 1, 1, 1, 1, ['CHARGING'])[1][0])

        # xfmr data
        self.xfmr_from = np.asarray(psspy.atrnint(-1, 1, 1, 1, 1, ['FROMNUMBER'])[1][0])
        self.xfmr_to = np.asarray(psspy.atrnint(-1, 1, 1, 1, 1, ['TONUMBER'])[1][0])
        self.xfmr_id = psspy.atrnchar(-1, 0, 0, 1, 1, ['ID'])[1][0]
        self.xfmr_P = np.asarray(psspy.atrnreal(-1, 1, 1, 1, 1, ['P'])[1][0])
        self.xfmr_Q = np.asarray(psspy.atrnreal(-1, 1, 1, 1, 1, ['Q'])[1][0])
        self.xfmr_RX = np.asarray(psspy.atrncplx(-1, 1, 1, 1, 1, ['RXACT'])[1][0])
        self.xfmr_k = np.asarray(psspy.atrnreal(-1, 1, 1, 1, 1, ['RATIO'])[1][0])

        # shunt data
        self.shnt_bus = np.asarray(psspy.afxshuntint(-1, 1, 'NUMBER')[1][0])
        self.shnt_id = psspy.afxshuntchar(-1, 1, 'ID')[1][0]
        self.shnt_gb = np.asarray(psspy.afxshuntcplx(-1, 1, ['SHUNTNOM'])[1][0])

        # switched shunt data
        self.shnt_sw_bus = np.asarray(psspy.aswshint(-1, 1, 'NUMBER')[1][0])
        self.shnt_sw_gb = np.asarray(psspy.aswshcplx(-1, 1, ['YSWACT'])[1][0])

    def LargeSysGenerator(self, ItfcBus, r, c):
        if r * c == 1:
            pfd = self
            return pfd

        upb = ItfcBus[0]
        rtb = ItfcBus[1]
        dnb = ItfcBus[2]
        lfb = ItfcBus[3]

        # initialization
        pfd = PFData()

        # duplication
        pfd.basemva = self.basemva
        pfd.ws = self.ws

        for i in range(r):
            for j in range(c):
                k = c * i + (j + 1)
                # bus
                pfd.bus_Va.extend(self.bus_Va)
                pfd.bus_Vm.extend(self.bus_Vm)
                pfd.bus_basekV.extend(self.bus_basekV)
                pfd.bus_kV.extend(self.bus_kV)
                # bus name is skipped
                pfd.bus_num.extend(self.bus_num + len(self.bus_num) * (k - 1))
                pfd.bus_type.extend(self.bus_type)  # slack in other blocks to be modified

                # load
                if len(self.load_bus) > 0:
                    pfd.load_I.extend(self.load_I)
                    pfd.load_MW.extend(self.load_MW)
                    pfd.load_Mvar.extend(self.load_Mvar)
                    pfd.load_P.extend(self.load_P)
                    pfd.load_Z.extend(self.load_Z)
                    pfd.load_bus.extend(self.load_bus + len(self.bus_num) * (k - 1))
                    pfd.load_id.extend(self.load_id)

                # shunt
                if len(self.shnt_bus) > 0:
                    pfd.shnt_gb.extend(self.shnt_gb)
                    pfd.shnt_bus.extend(self.shnt_bus + len(self.bus_num) * (k - 1))
                    pfd.shnt_id.extend(self.shnt_id)

                # generator
                pfd.gen_MVA_base.extend(self.gen_MVA_base)
                pfd.gen_MW.extend(self.gen_MW)
                pfd.gen_Mvar.extend(self.gen_Mvar)
                pfd.gen_S.extend(self.gen_S)
                pfd.gen_bus.extend(self.gen_bus + len(self.bus_num) * (k - 1))
                pfd.gen_id.extend(self.gen_id)
                pfd.gen_mod.extend(self.gen_mod)

                # line
                if len(self.line_from) > 0:
                    pfd.line_P.extend(self.line_P)
                    pfd.line_Q.extend(self.line_Q)
                    pfd.line_RX.extend(self.line_RX)
                    pfd.line_chg.extend(self.line_chg)
                    pfd.line_from.extend(self.line_from + len(self.bus_num) * (k - 1))
                    pfd.line_id.extend(self.line_id)
                    pfd.line_to.extend(self.line_to + len(self.bus_num) * (k - 1))

                # transformer
                if len(self.xfmr_from) > 0:
                    pfd.xfmr_P.extend(self.xfmr_P)
                    pfd.xfmr_Q.extend(self.xfmr_Q)
                    pfd.xfmr_RX.extend(self.xfmr_RX)
                    pfd.xfmr_from.extend(self.xfmr_from + len(self.bus_num) * (k - 1))
                    pfd.xfmr_id.extend(self.xfmr_id)
                    pfd.xfmr_k.extend(self.xfmr_k)
                    pfd.xfmr_to.extend(self.xfmr_to + len(self.bus_num) * (k - 1))

        idx = pfd.bus_type.index(3)
        flag = 1
        while flag == 1:
            try:
                idx = pfd.bus_type.index(3, idx + 1)
            except ValueError:
                flag = 0
            else:
                pfd.bus_type[idx] = int(2)

        # interconnection by adding new lines/transformers
        # list out all required branches
        branch_to_add = np.zeros([2 * r * c - r - c, 2], dtype=int)
        nn = 0
        for i in range(r):
            for j in range(c):
                k = c * i + (j + 1)

                if j != c - 1:
                    kr = k + 1
                    branch_to_add[nn][0] = (k - 1) * len(self.bus_num) + rtb
                    branch_to_add[nn][1] = (kr - 1) * len(self.bus_num) + lfb
                    nn = nn + 1

                if i != r - 1:
                    kd = k + c
                    branch_to_add[nn][0] = (k - 1) * len(self.bus_num) + dnb
                    branch_to_add[nn][1] = (kd - 1) * len(self.bus_num) + upb
                    nn = nn + 1

        # adding lines
        LinePmax = 100  # set a flow limit, since do not want to see large flow in interconncetion lines
        for i in range(len(branch_to_add)):
            FromB = branch_to_add[i][0]
            ToB = branch_to_add[i][1]

            FromB_G = []
            ToB_G = []
            if FromB in pfd.gen_bus:
                FromB_G = pfd.gen_bus.index(FromB)
                PG_From = pfd.gen_MW[FromB_G]
            else:
                print('Error: Interfacing bus should be generator bus.\n')

            if ToB in pfd.gen_bus:
                ToB_G = pfd.gen_bus.index(ToB)
                PG_To = pfd.gen_MW[ToB_G]
            else:
                print('Error: Interfacing bus should be generator bus.\n')

            tempP = min(PG_From / 3, PG_To / 3, LinePmax) / pfd.basemva
            tempX = pfd.bus_Vm[FromB - 1] * pfd.bus_Vm[ToB - 1] * math.sin(
                abs(pfd.bus_Va[FromB - 1] - pfd.bus_Va[ToB - 1])) / tempP

            if abs(tempX) < 1e-5:
                tempX = 0.05

            chg = 1e-5
            # add the branch
            if abs(pfd.bus_basekV[FromB - 1] - pfd.bus_basekV[
                ToB - 1]) < 1e-5:  # kV level is the same, this is a line
                tempr = tempX / 10.0
                pfd.line_P.append(0.0)
                pfd.line_Q.append(0.0)
                pfd.line_RX.append(complex(tempr, tempX))
                pfd.line_chg.append(chg)
                pfd.line_from.append(min(FromB, ToB))
                pfd.line_id.append('1')
                pfd.line_to.append(max(FromB, ToB))

            else:  # this is a transformer
                tempr = tempX / 100.0
                if pfd.bus_basekV[FromB - 1] > pfd.bus_basekV[ToB - 1]:
                    pfd.xfmr_from.append(FromB)
                    pfd.xfmr_to.append(ToB)
                else:
                    pfd.xfmr_from.append(ToB)
                    pfd.xfmr_to.append(FromB)

                pfd.xfmr_id.append('1')
                pfd.xfmr_P.append(0.0)
                pfd.xfmr_Q.append(0.0)
                pfd.xfmr_RX.append(complex(tempr, tempX))
                pfd.xfmr_k.append(1.0)

            # actual line flow
            Vf = complex(pfd.bus_Vm[FromB - 1] * math.cos(pfd.bus_Va[FromB - 1]),
                         pfd.bus_Vm[FromB - 1] * math.sin(pfd.bus_Va[FromB - 1]))
            Vt = complex(pfd.bus_Vm[ToB - 1] * math.cos(pfd.bus_Va[ToB - 1]),
                         pfd.bus_Vm[ToB - 1] * math.sin(pfd.bus_Va[ToB - 1]))
            tempI = (Vf - Vt) / complex(tempr, tempX)
            tempS_From = Vf * np.conjugate(tempI)
            tempS_To = Vt * np.conjugate(-tempI)

            # adjust from side
            # adjust MW
            if np.real(tempS_From) > 0:  # need to add generation
                pfd.gen_MW[FromB_G] = pfd.gen_MW[FromB_G] + np.real(
                    tempS_From) * pfd.basemva  # not run into during testing
            elif np.real(tempS_From) < 0:  # need to add load
                if FromB in pfd.load_bus:  # there is an existing load
                    idx = pfd.load_bus.index(FromB)
                    pfd.load_MW[idx] = pfd.load_MW[idx] - np.real(tempS_From) * pfd.basemva
                    pfd.load_P[idx] = pfd.load_P[idx] - complex(np.real(tempS_From) * pfd.basemva, 0.0)
                else:  # no existing load, need to add one
                    pfd.load_bus.append(FromB)
                    pfd.load_id.append('1')
                    pfd.load_P.append(complex(-np.real(tempS_From) * pfd.basemva, 0.0))
                    pfd.load_Z.append(0.0)
                    pfd.load_I.append(0.0)
                    pfd.load_MW.append(-np.real(tempS_From) * pfd.basemva)
                    pfd.load_Mvar.append(0.0)
            else:
                pass

            # adjust Mvar
            if np.imag(tempS_From) > 0:  # need to add shunt
                if FromB in pfd.shnt_bus:  # there is an existing shunt
                    idx = pfd.shnt_bus.index(FromB)
                    pfd.shnt_gb[idx] = pfd.shnt_gb[idx] + complex(0.0, np.imag(tempS_From) * pfd.basemva)
                else:  # no existing shunt, need to add one
                    pfd.shnt_bus.append(FromB)
                    pfd.shnt_id.append('1')
                    pfd.shnt_gb.append(complex(0.0, np.imag(tempS_From) * pfd.basemva))
            elif np.imag(tempS_From) < 0:  # need to add Mvar load   # not run into during testing
                if FromB in pfd.load_bus:  # there is an existing load
                    idx = pfd.load_bus.index(FromB)
                    pfd.load_Mvar[idx] = pfd.load_Mvar[idx] - np.imag(tempS_From) * pfd.basemva
                    pfd.load_P[idx] = pfd.load_P[idx] - complex(0.0, np.imag(tempS_From) * pfd.basemva)
                else:  # no existing load, need to add one
                    pfd.load_bus.append(FromB)
                    pfd.load_id.append('1')
                    pfd.load_P.append(complex(0.0, -np.imag(tempS_From) * pfd.basemva))
                    pfd.load_Z.append(0.0)
                    pfd.load_I.append(0.0)
                    pfd.load_Mvar.append(-np.imag(tempS_From) * pfd.basemva)
                    pfd.load_MW.append(0.0)
            else:
                pass

            # adjust To side
            # adjust MW
            if np.real(tempS_To) > 0:  # need to add generation
                pfd.gen_MW[ToB_G] = pfd.gen_MW[ToB_G] + np.real(
                    tempS_To) * pfd.basemva  # not run into during testing
            elif np.real(tempS_To) < 0:  # need to add load
                if ToB in pfd.load_bus:  # there is an existing load
                    idx = pfd.load_bus.index(ToB)
                    pfd.load_MW[idx] = pfd.load_MW[idx] - np.real(tempS_To) * pfd.basemva
                    pfd.load_P[idx] = pfd.load_P[idx] - complex(np.real(tempS_To) * pfd.basemva, 0.0)
                else:  # no existing load, need to add one
                    pfd.load_bus.append(ToB)
                    pfd.load_id.append('1')
                    pfd.load_P.append(complex(-np.real(tempS_To) * pfd.basemva, 0.0))
                    pfd.load_Z.append(0.0)
                    pfd.load_I.append(0.0)
                    pfd.load_MW.append(-np.real(tempS_To) * pfd.basemva)
                    pfd.load_Mvar.append(0.0)
            else:
                pass

            # adjust Mvar
            if np.imag(tempS_To) > 0:  # need to add shunt
                if ToB in pfd.shnt_bus:  # there is an existing shunt
                    idx = pfd.shnt_bus.index(ToB)
                    pfd.shnt_gb[idx] = pfd.shnt_gb[idx] + complex(0.0, np.imag(tempS_To) * pfd.basemva)
                else:  # no existing shunt, need to add one
                    pfd.shnt_bus.append(ToB)
                    pfd.shnt_id.append('1')
                    pfd.shnt_gb.append(complex(0.0, np.imag(tempS_To) * pfd.basemva))
            elif np.imag(tempS_To) < 0:  # need to add Mvar load   # not run into during testing
                if ToB in pfd.load_bus:  # there is an existing load
                    idx = pfd.load_bus.index(ToB)
                    pfd.load_Mvar[idx] = pfd.load_Mvar[idx] - np.imag(tempS_To) * pfd.basemva
                    pfd.load_P[idx] = pfd.load_P[idx] - complex(0.0, np.imag(tempS_To) * pfd.basemva)
                else:  # no existing load, need to add one
                    pfd.load_bus.append(ToB)
                    pfd.load_id.append('1')
                    pfd.load_P.append(complex(0.0, -np.imag(tempS_To) * pfd.basemva))
                    pfd.load_Z.append(0.0)
                    pfd.load_I.append(0.0)
                    pfd.load_Mvar.append(-np.imag(tempS_To) * pfd.basemva)
                    pfd.load_MW.append(0.0)
            else:
                pass

        return pfd

        def lists_to_arrays(self):
            for k in self.__dict__.keys():
                attr = getattr(self, k)
                if type(attr) is list:
                    setattr(self, k, np.array(attr))
            return


class DyData():
    # Maps string governor model names to integers
    gov_model_map = {
        'GAST': 0,
        'HYGOV': 1,
        'TGOV1': 2,
    }

    def __init__(self):
        ## types
        self.gen_type = np.asarray([])
        self.exc_type = np.asarray([])
        self.gov_type = np.asarray([])
        self.pss_type = np.asarray([])

        self.gen_Ra = np.asarray([])  # pu on machine MVA base
        self.gen_X0 = np.asarray([])  # pu on machine MVA base

        ## gen
        self.gen_n = 0

        # GENROU
        self.gen_genrou_bus = np.asarray([])
        self.gen_genrou_id = np.asarray([])
        self.gen_genrou_Td0p = np.asarray([])
        self.gen_genrou_Td0pp = np.asarray([])
        self.gen_genrou_Tq0p = np.asarray([])
        self.gen_genrou_Tq0pp = np.asarray([])
        self.gen_H = np.asarray([])  # pu on machine MVA base
        self.gen_D = np.asarray([])  # pu on machine MVA base
        self.gen_genrou_Xd = np.asarray([])  # pu on machine MVA base
        self.gen_genrou_Xq = np.asarray([])  # pu on machine MVA base
        self.gen_genrou_Xdp = np.asarray([])  # pu on machine MVA base
        self.gen_genrou_Xqp = np.asarray([])  # pu on machine MVA base
        self.gen_genrou_Xdpp = np.asarray([])  # pu on machine MVA base
        self.gen_genrou_Xl = np.asarray([])  # pu on machine MVA base
        self.gen_genrou_S10 = np.asarray([])
        self.gen_genrou_S12 = np.asarray([])
        self.gen_genrou_idx = np.asarray([])
        self.gen_genrou_n = 0
        self.gen_genrou_xi_st = 0
        self.gen_genrou_odr = 0

        ## exc
        self.exc_n = 0

        # SEXS
        self.exc_sexs_bus = np.asarray([])
        self.exc_sexs_id = np.asarray([])
        self.exc_sexs_TA_o_TB = np.asarray([])
        self.exc_sexs_TA = np.asarray([])
        self.exc_sexs_TB = np.asarray([])
        self.exc_sexs_K = np.asarray([])
        self.exc_sexs_TE = np.asarray([])
        self.exc_sexs_Emin = np.asarray([])  # pu on EFD base
        self.exc_sexs_Emax = np.asarray([])  # pu on EFD base
        self.exc_sexs_idx = np.asarray([])
        self.exc_sexs_n = 0
        self.exc_sexs_xi_st = 0
        self.exc_sexs_odr = 0

        ## gov
        self.gov_n = 0

        # TGOV1
        self.gov_tgov1_bus = np.asarray([])
        self.gov_tgov1_id = np.asarray([])
        self.gov_tgov1_R = np.asarray([])  # pu on machine MVA base
        self.gov_tgov1_T1 = np.asarray([])
        self.gov_tgov1_Vmax = np.asarray([])  # pu on machine MVA base
        self.gov_tgov1_Vmin = np.asarray([])  # pu on machine MVA base
        self.gov_tgov1_T2 = np.asarray([])
        self.gov_tgov1_T3 = np.asarray([])
        self.gov_tgov1_Dt = np.asarray([])  # pu on machine MVA base
        self.gov_tgov1_idx = np.asarray([])
        self.gov_tgov1_n = 0
        self.gov_tgov1_xi_st = 0
        self.gov_tgov1_odr = 0

        # HYGOV
        self.gov_hygov_bus = np.asarray([])
        self.gov_hygov_id = np.asarray([])
        self.gov_hygov_R = np.asarray([])  # pu on machine MVA base
        self.gov_hygov_r = np.asarray([])  # pu on machine MVA base
        self.gov_hygov_Tr = np.asarray([])
        self.gov_hygov_Tf = np.asarray([])
        self.gov_hygov_Tg = np.asarray([])
        self.gov_hygov_VELM = np.asarray([])
        self.gov_hygov_GMAX = np.asarray([])
        self.gov_hygov_GMIN = np.asarray([])
        self.gov_hygov_TW = np.asarray([])
        self.gov_hygov_At = np.asarray([])
        self.gov_hygov_Dturb = np.asarray([])  # pu on machine MVA base
        self.gov_hygov_qNL = np.asarray([])
        self.gov_hygov_idx = np.asarray([])
        self.gov_hygov_n = 0
        self.gov_hygov_xi_st = 0
        self.gov_hygov_odr = 0

        # GAST
        self.gov_gast_bus = np.asarray([])
        self.gov_gast_id = np.asarray([])
        self.gov_gast_R = np.asarray([])
        self.gov_gast_T1 = np.asarray([])
        self.gov_gast_T2 = np.asarray([])
        self.gov_gast_T3 = np.asarray([])
        self.gov_gast_LdLmt = np.asarray([])
        self.gov_gast_KT = np.asarray([])
        self.gov_gast_VMAX = np.asarray([])
        self.gov_gast_VMIN = np.asarray([])
        self.gov_gast_Dturb = np.asarray([])
        self.gov_gast_idx = np.asarray([])
        self.gov_gast_n = 0
        self.gov_gast_xi_st = 0
        self.gov_gast_odr = 0

        ## pss
        self.pss_n = 0

        # IEEEST
        self.pss_ieeest_bus = np.asarray([])
        self.pss_ieeest_id = np.asarray([])
        self.pss_ieeest_A1 = np.asarray([])
        self.pss_ieeest_A2 = np.asarray([])
        self.pss_ieeest_A3 = np.asarray([])
        self.pss_ieeest_A4 = np.asarray([])
        self.pss_ieeest_A5 = np.asarray([])
        self.pss_ieeest_A6 = np.asarray([])
        self.pss_ieeest_T1 = np.asarray([])
        self.pss_ieeest_T2 = np.asarray([])
        self.pss_ieeest_T3 = np.asarray([])
        self.pss_ieeest_T4 = np.asarray([])
        self.pss_ieeest_T5 = np.asarray([])
        self.pss_ieeest_T6 = np.asarray([])
        self.pss_ieeest_KS = np.asarray([])
        self.pss_ieeest_LSMAX = np.asarray([])
        self.pss_ieeest_LSMIN = np.asarray([])
        self.pss_ieeest_VCU = np.asarray([])
        self.pss_ieeest_VCL = np.asarray([])
        self.pss_ieeest_idx = np.asarray([])
        self.pss_ieeest_n = 0
        self.pss_ieeest_xi_st = 0
        self.pss_ieeest_odr = 0

        self.ec_Lad = np.asarray([])
        self.ec_Laq = np.asarray([])
        self.ec_Ll = np.asarray([])
        self.ec_Lffd = np.asarray([])
        self.ec_L11d = np.asarray([])
        self.ec_L11q = np.asarray([])
        self.ec_L22q = np.asarray([])
        self.ec_Lf1d = np.asarray([])

        self.ec_Ld = np.asarray([])
        self.ec_Lq = np.asarray([])
        self.ec_L0 = np.asarray([])

        self.ec_Ra = np.asarray([])
        self.ec_Rfd = np.asarray([])
        self.ec_R1d = np.asarray([])
        self.ec_R1q = np.asarray([])
        self.ec_R2q = np.asarray([])

        self.ec_Lfd = np.asarray([])
        self.ec_L1d = np.asarray([])
        self.ec_L1q = np.asarray([])
        self.ec_L2q = np.asarray([])

        self.base_es = np.asarray([])
        self.base_is = np.asarray([])
        self.base_Is = np.asarray([])
        self.base_Zs = np.asarray([])
        self.base_Ls = np.asarray([])
        self.base_ifd = np.asarray([])
        self.base_efd = np.asarray([])
        self.base_Zfd = np.asarray([])
        self.base_Lfd = np.asarray([])

        ## IBR parameters
        self.ibr_n = 0
        self.ibr_odr = 0

        self.ibr_kVbase = np.asarray([])
        self.ibr_MVAbase = np.asarray([])
        self.ibr_fbase = np.asarray([])
        self.ibr_Ibase = np.asarray([])

        self.ibr_regca_bus = np.asarray([])
        self.ibr_regca_id = np.asarray([])
        self.ibr_regca_LVPLsw = np.asarray([])
        self.ibr_regca_Tg = np.asarray([])
        self.ibr_regca_Rrpwr = np.asarray([])
        self.ibr_regca_Brkpt = np.asarray([])
        self.ibr_regca_Zerox = np.asarray([])
        self.ibr_regca_Lvpl1 = np.asarray([])
        self.ibr_regca_Volim = np.asarray([])
        self.ibr_regca_Lvpnt1 = np.asarray([])
        self.ibr_regca_Lvpnt0 = np.asarray([])
        self.ibr_regca_Iolim = np.asarray([])
        self.ibr_regca_Tfltr = np.asarray([])
        self.ibr_regca_Khv = np.asarray([])
        self.ibr_regca_Iqrmax = np.asarray([])
        self.ibr_regca_Iqrmin = np.asarray([])
        self.ibr_regca_Accel = np.asarray([])

        self.ibr_reecb_bus = np.asarray([])
        self.ibr_reecb_id = np.asarray([])
        self.ibr_reecb_PFFLAG = np.asarray([])
        self.ibr_reecb_VFLAG = np.asarray([])
        self.ibr_reecb_QFLAG = np.asarray([])
        self.ibr_reecb_PQFLAG = np.asarray([])
        self.ibr_reecb_Vdip = np.asarray([])
        self.ibr_reecb_Vup = np.asarray([])
        self.ibr_reecb_Trv = np.asarray([])
        self.ibr_reecb_dbd1 = np.asarray([])
        self.ibr_reecb_dbd2 = np.asarray([])
        self.ibr_reecb_Kqv = np.asarray([])
        self.ibr_reecb_Iqhl = np.asarray([])
        self.ibr_reecb_Iqll = np.asarray([])
        self.ibr_reecb_Vref0 = np.asarray([])
        self.ibr_reecb_Tp = np.asarray([])
        self.ibr_reecb_Qmax = np.asarray([])
        self.ibr_reecb_Qmin = np.asarray([])
        self.ibr_reecb_Vmax = np.asarray([])
        self.ibr_reecb_Vmin = np.asarray([])
        self.ibr_reecb_Kqp = np.asarray([])
        self.ibr_reecb_Kqi = np.asarray([])
        self.ibr_reecb_Kvp = np.asarray([])
        self.ibr_reecb_Kvi = np.asarray([])
        self.ibr_reecb_Tiq = np.asarray([])
        self.ibr_reecb_dPmax = np.asarray([])
        self.ibr_reecb_dPmin = np.asarray([])
        self.ibr_reecb_Pmax = np.asarray([])
        self.ibr_reecb_Pmin = np.asarray([])
        self.ibr_reecb_Imax = np.asarray([])
        self.ibr_reecb_Tpord = np.asarray([])

        self.ibr_repca_bus = np.asarray([])
        self.ibr_repca_id = np.asarray([])
        self.ibr_repca_remote_bus = np.asarray([])
        self.ibr_repca_branch_From_bus = np.asarray([])
        self.ibr_repca_branch_To_bus = np.asarray([])
        self.ibr_repca_branch_id = np.asarray([])
        self.ibr_repca_VCFlag = np.asarray([])
        self.ibr_repca_RefFlag = np.asarray([])
        self.ibr_repca_FFlag = np.asarray([])
        self.ibr_repca_Tfltr = np.asarray([])
        self.ibr_repca_Kp = np.asarray([])
        self.ibr_repca_Ki = np.asarray([])
        self.ibr_repca_Tft = np.asarray([])
        self.ibr_repca_Tfv = np.asarray([])
        self.ibr_repca_Vfrz = np.asarray([])
        self.ibr_repca_Rc = np.asarray([])
        self.ibr_repca_Xc = np.asarray([])
        self.ibr_repca_Kc = np.asarray([])
        self.ibr_repca_emax = np.asarray([])
        self.ibr_repca_emin = np.asarray([])
        self.ibr_repca_dbd1 = np.asarray([])
        self.ibr_repca_dbd2 = np.asarray([])
        self.ibr_repca_Qmax = np.asarray([])
        self.ibr_repca_Qmin = np.asarray([])
        self.ibr_repca_Kpg = np.asarray([])
        self.ibr_repca_Kig = np.asarray([])
        self.ibr_repca_Tp = np.asarray([])
        self.ibr_repca_fdbd1 = np.asarray([])
        self.ibr_repca_fdbd2 = np.asarray([])
        self.ibr_repca_femax = np.asarray([])
        self.ibr_repca_femin = np.asarray([])
        self.ibr_repca_Pmax = np.asarray([])
        self.ibr_repca_Pmin = np.asarray([])
        self.ibr_repca_Tg = np.asarray([])
        self.ibr_repca_Ddn = np.asarray([])
        self.ibr_repca_Dup = np.asarray([])

        # PLL for bus freq/ang measurement
        self.pll_bus = np.asarray([])
        self.pll_ke = np.asarray([])
        self.pll_te = np.asarray([])
        self.bus_odr = 0

        # bus volt magnitude measurement
        self.vm_bus = np.asarray([])
        self.vm_te = np.asarray([])

        # measurement method
        self.mea_bus = np.asarray([])
        self.mea_method = np.asarray([])

        # load
        self.load_odr = 0

    def getdata(self, file_dydata, pfd, N):
        # detailed machine model
        dyn_data = xlrd.open_workbook(file_dydata)

        # gen
        ngen = int(len(pfd.gen_bus) / N)
        gen_data = dyn_data.sheet_by_index(0)
        self.gen_n = gen_data.ncols - 1
        if ngen > self.gen_n:
            print('Error: More generators in pf data than dyn data!!\n')
        elif self.gen_n > ngen:
            print('Warning: More generators in dyn data than pf data!!\n')
        for i in range(self.gen_n):
            flag = 0
            typei = str(gen_data.cell_value(2, i + 1))
            self.gen_type = np.append(self.gen_type, typei)
            if typei == 'GENROU':
                flag = 1
                self.gen_genrou_idx = np.append(self.gen_genrou_idx, i)
                self.gen_genrou_n = self.gen_genrou_n + 1
                nn = 1
                self.gen_genrou_bus = np.append(self.gen_genrou_bus, float(gen_data.cell_value(0, i + 1)))
                self.gen_genrou_id = np.append(self.gen_genrou_bus, gen_data.cell_value(1, i + 1))
                self.gen_genrou_Td0p = np.append(self.gen_genrou_Td0p, float(gen_data.cell_value(2 + nn, i + 1)))
                self.gen_genrou_Td0pp = np.append(self.gen_genrou_Td0pp, float(gen_data.cell_value(3 + nn, i + 1)))
                self.gen_genrou_Tq0p = np.append(self.gen_genrou_Tq0p, float(gen_data.cell_value(4 + nn, i + 1)))
                self.gen_genrou_Tq0pp = np.append(self.gen_genrou_Tq0pp, float(gen_data.cell_value(5 + nn, i + 1)))
                self.gen_H = np.append(self.gen_H, float(gen_data.cell_value(6 + nn, i + 1)))
                self.gen_D = np.append(self.gen_D, float(gen_data.cell_value(7 + nn, i + 1)))
                self.gen_genrou_Xd = np.append(self.gen_genrou_Xd, float(gen_data.cell_value(8 + nn, i + 1)))
                self.gen_genrou_Xq = np.append(self.gen_genrou_Xq, float(gen_data.cell_value(9 + nn, i + 1)))
                self.gen_genrou_Xdp = np.append(self.gen_genrou_Xdp, float(gen_data.cell_value(10 + nn, i + 1)))
                self.gen_genrou_Xqp = np.append(self.gen_genrou_Xqp, float(gen_data.cell_value(11 + nn, i + 1)))
                self.gen_genrou_Xdpp = np.append(self.gen_genrou_Xdpp, float(gen_data.cell_value(12 + nn, i + 1)))
                self.gen_genrou_Xl = np.append(self.gen_genrou_Xl, float(gen_data.cell_value(13 + nn, i + 1)))
                self.gen_genrou_S10 = np.append(self.gen_genrou_S10, float(gen_data.cell_value(14 + nn, i + 1)))
                self.gen_genrou_S12 = np.append(self.gen_genrou_S12, float(gen_data.cell_value(15 + nn, i + 1)))
                self.gen_Ra = np.append(self.gen_Ra, float(gen_data.cell_value(16 + nn, i + 1)))
                self.gen_X0 = np.append(self.gen_X0, float(gen_data.cell_value(13 + nn, i + 1)))

            if flag == 0:
                print('ERROR: Machine model not supported:')
                print(typei)
                print('\n')

        # exc
        exc_data = dyn_data.sheet_by_index(1)
        self.exc_n = exc_data.ncols - 1
        for i in range(self.exc_n):
            flag = 0
            typei = str(exc_data.cell_value(2, i + 1))
            self.exc_type = np.append(self.exc_type, typei)
            if typei == 'SEXS':
                flag = 1
                self.exc_sexs_idx = np.append(self.exc_sexs_idx, i)
                self.exc_sexs_n = self.exc_sexs_n + 1
                nn = 1
                self.exc_sexs_bus = np.append(self.exc_sexs_bus, float(exc_data.cell_value(0, i + 1)))
                self.exc_sexs_id = np.append(self.exc_sexs_id, exc_data.cell_value(1, i + 1))
                self.exc_sexs_TA_o_TB = np.append(self.exc_sexs_TA_o_TB, float(exc_data.cell_value(2 + nn, i + 1)))
                self.exc_sexs_TB = np.append(self.exc_sexs_TB, float(exc_data.cell_value(3 + nn, i + 1)))
                self.exc_sexs_K = np.append(self.exc_sexs_K, float(exc_data.cell_value(4 + nn, i + 1)))
                self.exc_sexs_TE = np.append(self.exc_sexs_TE, float(exc_data.cell_value(5 + nn, i + 1)))
                self.exc_sexs_Emin = np.append(self.exc_sexs_Emin, float(exc_data.cell_value(6 + nn, i + 1)))
                self.exc_sexs_Emax = np.append(self.exc_sexs_Emax, float(exc_data.cell_value(7 + nn, i + 1)))
                self.exc_sexs_TA = np.append(self.exc_sexs_TA, self.exc_sexs_TB[i] * self.exc_sexs_TA_o_TB[i])

            if flag == 0:
                print('ERROR: Exciter model not supported:')
                print(typei)
                print('\n')

        # gov
        gov_data = dyn_data.sheet_by_index(2)
        self.gov_n = gov_data.ncols - 1
        # self.gov_type = [""]*self.gov_n
        self.gov_type = np.empty(self.gov_n, dtype=int)
        for i in range(self.gov_n):
            flag = 0
            typei = str(gov_data.cell_value(2, i + 1))
            if typei == 'TGOV1':
                flag = 1
                self.gov_tgov1_n = self.gov_tgov1_n + 1
                self.gov_tgov1_bus = np.append(self.gov_tgov1_bus, int(gov_data.cell_value(0, i + 1)))
                tempid = str(gov_data.cell_value(1, i + 1))
                if len(str(gov_data.cell_value(1, i + 1))) == 1:
                    tempid = tempid + ' '
                self.gov_tgov1_id = np.append(self.gov_tgov1_id, tempid)
                idx1 = np.where(pfd.gen_bus == self.gov_tgov1_bus[-1])[0]
                idx2 = np.where(pfd.gen_id[idx1] == tempid)[0][0]
                self.gov_tgov1_idx = np.append(self.gov_tgov1_idx, int(idx1[idx2]))
                self.gov_type[int(idx1[idx2])] = DyData.gov_model_map[typei]
                self.gov_tgov1_R = np.append(self.gov_tgov1_R, float(gov_data.cell_value(3, i + 1)))
                self.gov_tgov1_T1 = np.append(self.gov_tgov1_T1, float(gov_data.cell_value(4, i + 1)))
                self.gov_tgov1_Vmax = np.append(self.gov_tgov1_Vmax, float(gov_data.cell_value(5, i + 1)))
                self.gov_tgov1_Vmin = np.append(self.gov_tgov1_Vmin, float(gov_data.cell_value(6, i + 1)))
                self.gov_tgov1_T2 = np.append(self.gov_tgov1_T2, float(gov_data.cell_value(7, i + 1)))
                self.gov_tgov1_T3 = np.append(self.gov_tgov1_T3, float(gov_data.cell_value(8, i + 1)))
                self.gov_tgov1_Dt = np.append(self.gov_tgov1_Dt, float(gov_data.cell_value(9, i + 1)))

            if typei == 'HYGOV':
                flag = 1
                self.gov_hygov_n = self.gov_hygov_n + 1
                self.gov_hygov_bus = np.append(self.gov_hygov_bus, int(gov_data.cell_value(0, i + 1)))
                tempid = str(gov_data.cell_value(1, i + 1))
                if len(str(gov_data.cell_value(1, i + 1))) == 1:
                    tempid = tempid + ' '
                self.gov_hygov_id = np.append(self.gov_hygov_id, tempid)
                idx1 = np.where(pfd.gen_bus == self.gov_hygov_bus[-1])[0]
                idx2 = np.where(pfd.gen_id[idx1] == tempid)[0][0]
                self.gov_hygov_idx = np.append(self.gov_hygov_idx, int(idx1[idx2]))
                self.gov_type[int(idx1[idx2])] = DyData.gov_model_map[typei]
                self.gov_hygov_R = np.append(self.gov_hygov_R, float(gov_data.cell_value(3, i + 1)))
                self.gov_hygov_r = np.append(self.gov_hygov_r, float(gov_data.cell_value(4, i + 1)))
                self.gov_hygov_Tr = np.append(self.gov_hygov_Tr, float(gov_data.cell_value(5, i + 1)))
                self.gov_hygov_Tf = np.append(self.gov_hygov_Tf, float(gov_data.cell_value(6, i + 1)))
                self.gov_hygov_Tg = np.append(self.gov_hygov_Tg, float(gov_data.cell_value(7, i + 1)))
                self.gov_hygov_VELM = np.append(self.gov_hygov_VELM, float(gov_data.cell_value(8, i + 1)))
                self.gov_hygov_GMAX = np.append(self.gov_hygov_GMAX, float(gov_data.cell_value(9, i + 1)))
                self.gov_hygov_GMIN = np.append(self.gov_hygov_GMIN, float(gov_data.cell_value(10, i + 1)))
                self.gov_hygov_TW = np.append(self.gov_hygov_TW, float(gov_data.cell_value(11, i + 1)))
                self.gov_hygov_At = np.append(self.gov_hygov_At, float(gov_data.cell_value(12, i + 1)))
                self.gov_hygov_Dturb = np.append(self.gov_hygov_Dturb, float(gov_data.cell_value(13, i + 1)))
                self.gov_hygov_qNL = np.append(self.gov_hygov_qNL, float(gov_data.cell_value(14, i + 1)))

            if typei == 'GAST':
                flag = 1
                self.gov_gast_n = self.gov_gast_n + 1
                self.gov_gast_bus = np.append(self.gov_gast_bus, float(gov_data.cell_value(0, i + 1)))
                tempid = str(gov_data.cell_value(1, i + 1))
                tempid = tempid.replace("'", " ")
                if len(tempid) == 1:
                    tempid = tempid + " "
                self.gov_gast_id = np.append(self.gov_gast_id, tempid)
                idx1 = np.where(pfd.gen_bus == self.gov_gast_bus[-1])[0]
                idx2 = np.where(pfd.gen_id[idx1] == tempid)[0][0]
                self.gov_gast_idx = np.append(self.gov_gast_idx, int(idx1[idx2]))
                self.gov_type[int(idx1[idx2])] = DyData.gov_model_map[typei]
                self.gov_gast_R = np.append(self.gov_gast_R, float(gov_data.cell_value(3, i + 1)))
                self.gov_gast_T1 = np.append(self.gov_gast_T1, float(gov_data.cell_value(4, i + 1)))
                self.gov_gast_T2 = np.append(self.gov_gast_T2, float(gov_data.cell_value(5, i + 1)))
                self.gov_gast_T3 = np.append(self.gov_gast_T3, float(gov_data.cell_value(6, i + 1)))
                self.gov_gast_LdLmt = np.append(self.gov_gast_LdLmt, float(gov_data.cell_value(7, i + 1)))
                self.gov_gast_KT = np.append(self.gov_gast_KT, float(gov_data.cell_value(8, i + 1)))
                self.gov_gast_VMAX = np.append(self.gov_gast_VMAX, float(gov_data.cell_value(9, i + 1)))
                self.gov_gast_VMIN = np.append(self.gov_gast_VMIN, float(gov_data.cell_value(10, i + 1)))
                self.gov_gast_Dturb = np.append(self.gov_gast_Dturb, float(gov_data.cell_value(11, i + 1)))

            if flag == 0:
                print('ERROR: Governor model not supported:')
                print(typei)
                print('\n')

        # pss
        pss_data = dyn_data.sheet_by_index(3)
        self.pss_n = pss_data.ncols - 1
        for i in range(self.pss_n):
            flag = 0
            typei = str(pss_data.cell_value(2, i + 1))
            self.pss_type = np.append(self.pss_type, typei)

            if typei == 'IEEEST':
                flag = 1
                self.pss_ieeest_n = self.pss_ieeest_n + 1
                self.pss_ieeest_bus = np.append(self.pss_ieeest_bus, float(pss_data.cell_value(0, i + 1)))
                tempid = str(pss_data.cell_value(1, i + 1))
                tempid = tempid.replace("'", " ")
                if len(tempid) == 1:
                    tempid = tempid + " "
                self.pss_ieeest_id = np.append(self.pss_ieeest_id, tempid)
                idx1 = np.where(pfd.gen_bus == self.pss_ieeest_bus[i])[0]
                idx2 = np.where(pfd.gen_id[idx1] == self.pss_ieeest_id[i])[0][0]
                self.pss_ieeest_idx = np.append(self.pss_ieeest_idx, idx1[idx2])
                self.pss_ieeest_A1 = np.append(self.pss_ieeest_A1, float(pss_data.cell_value(3, i + 1)))
                self.pss_ieeest_A2 = np.append(self.pss_ieeest_A2, float(pss_data.cell_value(4, i + 1)))
                self.pss_ieeest_A3 = np.append(self.pss_ieeest_A3, float(pss_data.cell_value(5, i + 1)))
                self.pss_ieeest_A4 = np.append(self.pss_ieeest_A4, float(pss_data.cell_value(6, i + 1)))
                self.pss_ieeest_A5 = np.append(self.pss_ieeest_A5, float(pss_data.cell_value(7, i + 1)))
                self.pss_ieeest_A6 = np.append(self.pss_ieeest_A6, float(pss_data.cell_value(8, i + 1)))
                self.pss_ieeest_T1 = np.append(self.pss_ieeest_T1, float(pss_data.cell_value(9, i + 1)))
                self.pss_ieeest_T2 = np.append(self.pss_ieeest_T2, float(pss_data.cell_value(10, i + 1)))
                self.pss_ieeest_T3 = np.append(self.pss_ieeest_T3, float(pss_data.cell_value(11, i + 1)))
                self.pss_ieeest_T4 = np.append(self.pss_ieeest_T4, float(pss_data.cell_value(12, i + 1)))
                self.pss_ieeest_T5 = np.append(self.pss_ieeest_T5, float(pss_data.cell_value(13, i + 1)))
                self.pss_ieeest_T6 = np.append(self.pss_ieeest_T6, float(pss_data.cell_value(14, i + 1)))
                self.pss_ieeest_KS = np.append(self.pss_ieeest_KS, float(pss_data.cell_value(15, i + 1)))
                self.pss_ieeest_LSMAX = np.append(self.pss_ieeest_LSMAX, float(pss_data.cell_value(16, i + 1)))
                self.pss_ieeest_LSMIN = np.append(self.pss_ieeest_LSMIN, float(pss_data.cell_value(17, i + 1)))
                self.pss_ieeest_VCU = np.append(self.pss_ieeest_VCU, float(pss_data.cell_value(18, i + 1)))
                self.pss_ieeest_VCL = np.append(self.pss_ieeest_VCL, float(pss_data.cell_value(19, i + 1)))

        # ibr
        regca_data = dyn_data.sheet_by_index(4)
        self.ibr_n = regca_data.ncols - 1
        for i in range(self.ibr_n):
            self.ibr_regca_bus = np.append(self.ibr_regca_bus, float(regca_data.cell_value(0, i + 1)))
            self.ibr_regca_id = np.append(self.ibr_regca_id, regca_data.cell_value(1, i + 1))
            self.ibr_regca_LVPLsw = np.append(self.ibr_regca_LVPLsw, float(regca_data.cell_value(2, i + 1)))
            self.ibr_regca_Tg = np.append(self.ibr_regca_Tg, float(regca_data.cell_value(3, i + 1)))
            self.ibr_regca_Rrpwr = np.append(self.ibr_regca_Rrpwr, float(regca_data.cell_value(4, i + 1)))
            self.ibr_regca_Brkpt = np.append(self.ibr_regca_Brkpt, float(regca_data.cell_value(5, i + 1)))
            self.ibr_regca_Zerox = np.append(self.ibr_regca_Zerox, float(regca_data.cell_value(6, i + 1)))
            self.ibr_regca_Lvpl1 = np.append(self.ibr_regca_Lvpl1, float(regca_data.cell_value(7, i + 1)))
            self.ibr_regca_Volim = np.append(self.ibr_regca_Volim, float(regca_data.cell_value(8, i + 1)))
            self.ibr_regca_Lvpnt1 = np.append(self.ibr_regca_Lvpnt1, float(regca_data.cell_value(9, i + 1)))
            self.ibr_regca_Lvpnt0 = np.append(self.ibr_regca_Lvpnt0, float(regca_data.cell_value(10, i + 1)))
            self.ibr_regca_Iolim = np.append(self.ibr_regca_Iolim, float(regca_data.cell_value(11, i + 1)))
            self.ibr_regca_Tfltr = np.append(self.ibr_regca_Tfltr, float(regca_data.cell_value(12, i + 1)))
            self.ibr_regca_Khv = np.append(self.ibr_regca_Khv, float(regca_data.cell_value(13, i + 1)))
            self.ibr_regca_Iqrmax = np.append(self.ibr_regca_Iqrmax, float(regca_data.cell_value(14, i + 1)))
            self.ibr_regca_Iqrmin = np.append(self.ibr_regca_Iqrmin, float(regca_data.cell_value(15, i + 1)))
            self.ibr_regca_Accel = np.append(self.ibr_regca_Accel, float(regca_data.cell_value(16, i + 1)))
            self.ibr_fbase = np.append(self.ibr_fbase, float(regca_data.cell_value(17, i + 1)))
            self.ibr_MVAbase = np.append(self.ibr_MVAbase, float(
                regca_data.cell_value(18, i + 1)))  # need to maintain consistence in MVAbase between pfd and dyd

            ibrbus = pfd.ibr_bus[i]
            ibrbus_idx = np.where(pfd.bus_num == ibrbus)
            self.ibr_kVbase = np.append(self.ibr_kVbase, pfd.bus_basekV[ibrbus_idx])

        reecb_data = dyn_data.sheet_by_index(5)
        for i in range(reecb_data.ncols - 1):
            self.ibr_reecb_bus = np.append(self.ibr_reecb_bus, float(reecb_data.cell_value(0, i + 1)))
            self.ibr_reecb_id = np.append(self.ibr_reecb_id, reecb_data.cell_value(1, i + 1))
            self.ibr_reecb_PFFLAG = np.append(self.ibr_reecb_PFFLAG, float(reecb_data.cell_value(2, i + 1)))
            self.ibr_reecb_VFLAG = np.append(self.ibr_reecb_VFLAG, float(reecb_data.cell_value(3, i + 1)))
            self.ibr_reecb_QFLAG = np.append(self.ibr_reecb_QFLAG, float(reecb_data.cell_value(4, i + 1)))
            self.ibr_reecb_PQFLAG = np.append(self.ibr_reecb_PQFLAG, float(reecb_data.cell_value(5, i + 1)))
            self.ibr_reecb_Vdip = np.append(self.ibr_reecb_Vdip, float(reecb_data.cell_value(6, i + 1)))
            self.ibr_reecb_Vup = np.append(self.ibr_reecb_Vup, float(reecb_data.cell_value(7, i + 1)))
            self.ibr_reecb_Trv = np.append(self.ibr_reecb_Trv, float(reecb_data.cell_value(8, i + 1)))
            self.ibr_reecb_dbd1 = np.append(self.ibr_reecb_dbd1, float(reecb_data.cell_value(9, i + 1)))
            self.ibr_reecb_dbd2 = np.append(self.ibr_reecb_dbd2, float(reecb_data.cell_value(10, i + 1)))
            self.ibr_reecb_Kqv = np.append(self.ibr_reecb_Kqv, float(reecb_data.cell_value(11, i + 1)))
            self.ibr_reecb_Iqhl = np.append(self.ibr_reecb_Iqhl, float(reecb_data.cell_value(12, i + 1)))
            self.ibr_reecb_Iqll = np.append(self.ibr_reecb_Iqll, float(reecb_data.cell_value(13, i + 1)))
            self.ibr_reecb_Vref0 = np.append(self.ibr_reecb_Vref0, float(reecb_data.cell_value(14, i + 1)))
            self.ibr_reecb_Tp = np.append(self.ibr_reecb_Tp, float(reecb_data.cell_value(15, i + 1)))
            self.ibr_reecb_Qmax = np.append(self.ibr_reecb_Qmax, float(reecb_data.cell_value(16, i + 1)))
            self.ibr_reecb_Qmin = np.append(self.ibr_reecb_Qmin, float(reecb_data.cell_value(17, i + 1)))
            self.ibr_reecb_Vmax = np.append(self.ibr_reecb_Vmax, float(reecb_data.cell_value(18, i + 1)))
            self.ibr_reecb_Vmin = np.append(self.ibr_reecb_Vmin, float(reecb_data.cell_value(19, i + 1)))
            self.ibr_reecb_Kqp = np.append(self.ibr_reecb_Kqp, float(reecb_data.cell_value(20, i + 1)))
            self.ibr_reecb_Kqi = np.append(self.ibr_reecb_Kqi, float(reecb_data.cell_value(21, i + 1)))
            self.ibr_reecb_Kvp = np.append(self.ibr_reecb_Kvp, float(reecb_data.cell_value(22, i + 1)))
            self.ibr_reecb_Kvi = np.append(self.ibr_reecb_Kvi, float(reecb_data.cell_value(23, i + 1)))
            self.ibr_reecb_Tiq = np.append(self.ibr_reecb_Tiq, float(reecb_data.cell_value(24, i + 1)))
            self.ibr_reecb_dPmax = np.append(self.ibr_reecb_dPmax, float(reecb_data.cell_value(25, i + 1)))
            self.ibr_reecb_dPmin = np.append(self.ibr_reecb_dPmin, float(reecb_data.cell_value(26, i + 1)))
            self.ibr_reecb_Pmax = np.append(self.ibr_reecb_Pmax, float(reecb_data.cell_value(27, i + 1)))
            self.ibr_reecb_Pmin = np.append(self.ibr_reecb_Pmin, float(reecb_data.cell_value(28, i + 1)))
            self.ibr_reecb_Imax = np.append(self.ibr_reecb_Imax, float(reecb_data.cell_value(29, i + 1)))
            self.ibr_reecb_Tpord = np.append(self.ibr_reecb_Tpord, float(reecb_data.cell_value(30, i + 1)))

        repca_data = dyn_data.sheet_by_index(6)
        for i in range(repca_data.ncols - 1):
            self.ibr_repca_bus = np.append(self.ibr_repca_bus, float(repca_data.cell_value(0, i + 1)))
            self.ibr_repca_id = np.append(self.ibr_repca_id, repca_data.cell_value(1, i + 1))
            self.ibr_repca_remote_bus = np.append(self.ibr_repca_remote_bus, float(repca_data.cell_value(2, i + 1)))
            self.ibr_repca_branch_From_bus = np.append(self.ibr_repca_branch_From_bus,
                                                       float(repca_data.cell_value(3, i + 1)))
            self.ibr_repca_branch_To_bus = np.append(self.ibr_repca_branch_To_bus,
                                                     float(repca_data.cell_value(4, i + 1)))
            self.ibr_repca_branch_id = np.append(self.ibr_repca_branch_id, repca_data.cell_value(5, i + 1))
            self.ibr_repca_VCFlag = np.append(self.ibr_repca_VCFlag, float(repca_data.cell_value(6, i + 1)))
            self.ibr_repca_RefFlag = np.append(self.ibr_repca_RefFlag, float(repca_data.cell_value(7, i + 1)))
            self.ibr_repca_FFlag = np.append(self.ibr_repca_FFlag, float(repca_data.cell_value(8, i + 1)))
            self.ibr_repca_Tfltr = np.append(self.ibr_repca_Tfltr, float(repca_data.cell_value(9, i + 1)))
            self.ibr_repca_Kp = np.append(self.ibr_repca_Kp, float(repca_data.cell_value(10, i + 1)))
            self.ibr_repca_Ki = np.append(self.ibr_repca_Ki, float(repca_data.cell_value(11, i + 1)))
            self.ibr_repca_Tft = np.append(self.ibr_repca_Tft, float(repca_data.cell_value(12, i + 1)))
            self.ibr_repca_Tfv = np.append(self.ibr_repca_Tfv, float(repca_data.cell_value(13, i + 1)))
            self.ibr_repca_Vfrz = np.append(self.ibr_repca_Vfrz, float(repca_data.cell_value(14, i + 1)))
            self.ibr_repca_Rc = np.append(self.ibr_repca_Rc, float(repca_data.cell_value(15, i + 1)))
            self.ibr_repca_Xc = np.append(self.ibr_repca_Xc, float(repca_data.cell_value(16, i + 1)))
            self.ibr_repca_Kc = np.append(self.ibr_repca_Kc, float(repca_data.cell_value(17, i + 1)))
            self.ibr_repca_emax = np.append(self.ibr_repca_emax, float(repca_data.cell_value(18, i + 1)))
            self.ibr_repca_emin = np.append(self.ibr_repca_emin, float(repca_data.cell_value(19, i + 1)))
            self.ibr_repca_dbd1 = np.append(self.ibr_repca_dbd1, float(repca_data.cell_value(20, i + 1)))
            self.ibr_repca_dbd2 = np.append(self.ibr_repca_dbd2, float(repca_data.cell_value(21, i + 1)))
            self.ibr_repca_Qmax = np.append(self.ibr_repca_Qmax, float(repca_data.cell_value(22, i + 1)))
            self.ibr_repca_Qmin = np.append(self.ibr_repca_Qmin, float(repca_data.cell_value(23, i + 1)))
            self.ibr_repca_Kpg = np.append(self.ibr_repca_Kpg, float(repca_data.cell_value(24, i + 1)))
            self.ibr_repca_Kig = np.append(self.ibr_repca_Kig, float(repca_data.cell_value(25, i + 1)))
            self.ibr_repca_Tp = np.append(self.ibr_repca_Tp, float(repca_data.cell_value(26, i + 1)))
            self.ibr_repca_fdbd1 = np.append(self.ibr_repca_fdbd1, float(repca_data.cell_value(27, i + 1)))
            self.ibr_repca_fdbd2 = np.append(self.ibr_repca_fdbd2, float(repca_data.cell_value(28, i + 1)))
            self.ibr_repca_femax = np.append(self.ibr_repca_femax, float(repca_data.cell_value(29, i + 1)))
            self.ibr_repca_femin = np.append(self.ibr_repca_femin, float(repca_data.cell_value(30, i + 1)))
            self.ibr_repca_Pmax = np.append(self.ibr_repca_Pmax, float(repca_data.cell_value(31, i + 1)))
            self.ibr_repca_Pmin = np.append(self.ibr_repca_Pmin, float(repca_data.cell_value(32, i + 1)))
            self.ibr_repca_Tg = np.append(self.ibr_repca_Tg, float(repca_data.cell_value(33, i + 1)))
            self.ibr_repca_Ddn = np.append(self.ibr_repca_Ddn, float(repca_data.cell_value(34, i + 1)))
            self.ibr_repca_Dup = np.append(self.ibr_repca_Dup, float(repca_data.cell_value(35, i + 1)))

        # PLL for bus freq/angle measurement
        pll_data = dyn_data.sheet_by_index(7)
        for i in range(pll_data.ncols - 1):
            self.pll_bus = np.append(self.pll_bus, float(pll_data.cell_value(0, i + 1)))
            self.pll_ke = np.append(self.pll_ke, float(pll_data.cell_value(1, i + 1)))
            self.pll_te = np.append(self.pll_te, float(pll_data.cell_value(2, i + 1)))

        # volt mag measurement
        vm_data = dyn_data.sheet_by_index(8)
        for i in range(vm_data.ncols - 1):
            self.vm_bus = np.append(self.vm_bus, float(vm_data.cell_value(0, i + 1)))
            self.vm_te = np.append(self.vm_te, float(vm_data.cell_value(1, i + 1)))

        # measurement methods
        mea_data = dyn_data.sheet_by_index(9)
        for i in range(mea_data.ncols - 1):
            self.mea_bus = np.append(self.mea_bus, float(mea_data.cell_value(0, i + 1)))
            self.mea_method = np.append(self.mea_method, float(mea_data.cell_value(1, i + 1)))

    def spreaddyd(self, pfd, dyd, N):
        dyd_dict = dyd.__dict__
        my_dyd = DyData()
        for x in dyd_dict.keys():
            newx = []
            if type(dyd_dict[x]) != np.ndarray:
                if isinstance(dyd_dict[x], int):
                    newx = dyd_dict[x] * N
                    setattr(my_dyd, x, newx)
                else:
                    print('Warning: should not see this when spreading dyn data!!')

            else:
                if (x == 'exe_sexs_bus') | (x == 'exe_sexs_bus') | (x == 'gov_gast_bus') | (x == 'pss_ieeest_bus'):
                    for i in range(N):
                        tempx = dyd_dict[x]
                        tempnewx = dyd_dict[x] + i * len(pfd.bus_num) / N
                        newx = np.concatenate((newx, tempnewx))
                elif (x == 'gov_gast_idx') | (x == 'gen_genrou_idx'):
                    for i in range(N):
                        tempx = dyd_dict[x]
                        tempnewx = dyd_dict[x] + i * len(pfd.gen_bus) / N
                        newx = np.concatenate((newx, tempnewx))
                else:
                    for i in range(N):
                        newx = np.concatenate((newx, dyd_dict[x]))
                setattr(my_dyd, x, newx)
        return my_dyd

    def ToEquiCirData(self, pfd, dyd):
        # IBR base calc
        for i in range(len(pfd.ibr_bus)):
            ibrbus = pfd.ibr_bus[i]
            ibrbus_idx = np.where(pfd.bus_num == ibrbus)[0][0]

            base_es_temp = pfd.bus_basekV[ibrbus_idx] * math.sqrt(2.0 / 3.0) * 1000.0
            base_is_temp = pfd.ibr_MVA_base[i] * 1000000.0 / (base_es_temp * 3.0 / 2.0)
            self.ibr_Ibase = np.append(self.ibr_Ibase, base_is_temp / math.sqrt(2.0))

        # Convert generator data to equivalent circuit data

        # base calculation
        for i in range(len(pfd.gen_bus)):
            genbus = pfd.gen_bus[i]
            genbus_idx = np.where(pfd.bus_num == genbus)[0][0]

            base_es_temp = pfd.bus_basekV[genbus_idx] * math.sqrt(2.0 / 3.0) * 1000.0
            self.base_es = np.append(self.base_es, base_es_temp)
            base_is_temp = pfd.gen_MVA_base[i] * 1000000.0 / (base_es_temp * 3.0 / 2.0)
            self.base_is = np.append(self.base_is, base_is_temp)
            base_Is_temp = base_is_temp / math.sqrt(2.0)
            self.base_Is = np.append(self.base_Is, base_Is_temp)
            base_Zs_temp = base_es_temp / base_is_temp
            self.base_Zs = np.append(self.base_Zs, base_Zs_temp)
            base_Ls_temp = base_Zs_temp * 1000.0 / 2.0 / 60.0 / math.pi
            self.base_Ls = np.append(self.base_Ls, base_Ls_temp)

            self.ec_Lad = np.append(self.ec_Lad, self.gen_genrou_Xd[i] - self.gen_genrou_Xl[i])
            self.ec_Laq = np.append(self.ec_Laq, self.gen_genrou_Xq[i] - self.gen_genrou_Xl[i])
            self.ec_Ll = np.append(self.ec_Ll, self.gen_genrou_Xl[i])
            self.ec_Ld = np.append(self.ec_Ld, self.ec_Lad[i] + self.ec_Ll[i])
            self.ec_Lq = np.append(self.ec_Lq, self.ec_Laq[i] + self.ec_Ll[i])
            self.ec_Lfd = np.append(self.ec_Lfd,
                                    (self.gen_genrou_Xdp[i] - self.gen_genrou_Xl[i]) * self.ec_Lad[i] / (
                                            self.ec_Lad[i] - (self.gen_genrou_Xdp[i] - self.gen_genrou_Xl[i])))
            self.ec_L1q = np.append(self.ec_L1q,
                                    (self.gen_genrou_Xqp[i] - self.gen_genrou_Xl[i]) * self.ec_Laq[i] / (
                                            self.ec_Laq[i] - (self.gen_genrou_Xqp[i] - self.gen_genrou_Xl[i])))

            z = self.gen_genrou_Xdpp[i] - self.gen_genrou_Xl[i]
            y = self.ec_Lad[i] * self.ec_Lfd[i] / (self.ec_Lad[i] + self.ec_Lfd[i])
            self.ec_L1d = np.append(self.ec_L1d, y * z / (y - z))
            self.ec_R1d = np.append(self.ec_R1d, (y + self.ec_L1d[i]) / self.gen_genrou_Td0pp[i])

            z = self.gen_genrou_Xdpp[i] - self.gen_genrou_Xl[i]
            y = self.ec_Laq[i] * self.ec_L1q[i] / (self.ec_Laq[i] + self.ec_L1q[i])
            self.ec_L2q = np.append(self.ec_L2q, y * z / (y - z))
            self.ec_R2q = np.append(self.ec_R2q, (y + self.ec_L2q[i]) / self.gen_genrou_Tq0pp[i])

            self.ec_Rfd = np.append(self.ec_Rfd, (self.ec_Lad[i] + self.ec_Lfd[i]) / self.gen_genrou_Td0p[i])
            self.ec_R1q = np.append(self.ec_R1q, (self.ec_Laq[i] + self.ec_L1q[i]) / self.gen_genrou_Tq0p[i])

            self.ec_Ra = np.append(self.ec_Ra, self.gen_Ra[i])
            self.ec_L0 = np.append(self.ec_L0, self.gen_X0[i])
            self.ec_Lf1d = np.append(self.ec_Lf1d, self.ec_Lad[i])

            self.ec_Lffd = np.append(self.ec_Lffd,
                                     self.ec_Lad[i] * self.ec_Lad[i] / (
                                             self.gen_genrou_Xd[i] - self.gen_genrou_Xdp[i]))
            self.ec_L11d = np.append(self.ec_L11d,
                                     self.ec_Lad[i] * self.ec_Lad[i] / (
                                             self.gen_genrou_Xd[i] - self.gen_genrou_Xdpp[i]))
            self.ec_L11q = np.append(self.ec_L11q,
                                     self.ec_Laq[i] * self.ec_Laq[i] / (
                                             self.gen_genrou_Xq[i] - self.gen_genrou_Xqp[i]))
            self.ec_L22q = np.append(self.ec_L22q,
                                     self.ec_Laq[i] * self.ec_Laq[i] / (
                                             self.gen_genrou_Xq[i] - self.gen_genrou_Xdpp[i]))


# EMT sim
class EmtSimu():
    def __init__(self, ngen, nibr, nbus, nload):
        # three-phase synchronous machine model, unit in Ohm
        self.ts = 50e-6  # second
        self.Tlen = 0.1  # second
        self.Nlen = np.asarray([])

        self.t = {}
        self.x = {}
        self.x_pv_1 = []
        self.x_pred = {}
        self.x_ibr = {}
        self.x_ibr_pv_1 = []
        self.x_load = {}
        self.x_load_pv_1 = []
        self.x_bus = {}
        self.x_bus_pv_1 = []
        self.v = {}
        self.i = {}

        self.xp = States(ngen)  # seems not necessary, try later and see if they can be deleted
        self.xp_ibr = States_ibr(nibr)
        self.Igs = np.zeros(3 * nbus)
        self.Isg = np.zeros(3 * ngen)
        self.Igi = np.zeros(3 * nbus)
        self.Il = np.zeros(3 * nbus)  # to change to Igl and Iload
        self.Ild = np.zeros(3 * nload)
        self.Iibr = np.zeros(3 * nibr)
        self.brch_Ihis = np.asarray([])
        self.brch_Ipre = np.asarray([])
        self.node_Ihis = np.asarray([])
        self.I_RHS = np.zeros(3 * nbus)
        self.Vsol = np.zeros(3 * nbus)
        self.Vsol_1 = np.zeros(3 * nbus)

        # self.fft_vabc = []
        # self.fft_T = 1
        # self.fft_N = 0
        # self.fft_vma = {}
        # self.fft_vpn0 = {}

        self.theta = np.zeros(ngen)
        self.ed_mod = np.zeros(ngen)
        self.eq_mod = np.zeros(ngen)

        self.t_release_f = 0.1
        self.loadmodel_option = 1  # 1-const rlc, 2-const z

        # step change
        self.t_sc = 1000  # the time when the step change occurs
        self.i_gen_sc = 1  # which gen, index in pfd.gen_bus
        self.flag_exc_gov = 1  # 0 - exc, 1 - gov
        self.dsp = - 0.2  # increment
        self.flag_sc = 1  # 1 - step change to be implemented, 0 - step change completed

        # gen trip
        self.t_gentrip = 1000  # the time when the gentrip occurs
        self.i_gentrip = 1  # which gen, index in pfd.gen_bus
        self.flag_gentrip = 1  # 1 - gentrip to be implemented, 0 - gentrip completed
        self.flag_reinit = 1  # 1 - re-init to be implemented, 0 - re-init completed

        # ref at last time step (for calculating dref term)
        self.vref = np.zeros(ngen)
        self.vref_1 = np.zeros(ngen)
        self.gref = np.zeros(ngen)

        # playback
        self.data = []
        self.playback_enable = 0
        self.playback_t_chn = 0
        self.playback_sig_chn = 1
        self.playback_tn = 0

        self.data1 = []
        self.playback_enable1 = 0
        self.playback_t_chn1 = 0
        self.playback_sig_chn1 = 1
        self.playback_tn1 = 0

        # mac as I source
        self.flag_Isrc = 0

        return

    def preprocess(self, ini, pfd, dyd):
        self.t = [0.0]

        nbus = len(pfd.bus_num)
        ini.CombineX(pfd, dyd)
        self.x[0] = ini.Init_x.copy()
        self.x_ibr[0] = ini.Init_x_ibr.copy()
        self.x_bus[0] = ini.Init_x_bus.copy()
        self.x_load[0] = ini.Init_x_load.copy()
        self.x_pv_1 = ini.Init_x.copy()
        self.x_ibr_pv_1 = ini.Init_x_ibr.copy()
        self.x_bus_pv_1 = ini.Init_x_bus.copy()
        self.x_load_pv_1 = ini.Init_x_load.copy()

        self.v[0] = np.real(ini.Init_net_Vt)
        self.i[0] = np.real(ini.Init_net_It)

        # self.fft_vabc.append(np.real(ini.Init_net_Vt))
        # if self.fft_T == 1:
        #     self.fft_N = int(1/(pfd.ws/2/np.pi) / self.ts)

        # self.fft_vma[0] = np.concatenate((abs(ini.Init_net_Vt),np.angle(ini.Init_net_Vt)))
        # self.fft_vpn0[0] = np.concatenate((abs(ini.Init_net_Vt[0:nbus]), np.zeros(2*nbus), np.angle(ini.Init_net_Vt)[0:nbus], np.zeros(2*nbus)))

        self.Vsol = np.real(ini.Init_net_Vt)
        self.Vsol_1 = np.real(ini.Init_net_Vt)

        self.x_pred = {0: self.x[0], 1: self.x[0], 2: self.x[0]}

        self.brch_Ihis = ini.Init_brch_Ihis
        self.brch_Ipre = ini.Init_brch_Ipre
        self.node_Ihis = ini.Init_node_Ihis

        self.vref = ini.Init_mac_vref.copy()
        self.vref_1 = ini.Init_mac_vref.copy()
        self.gref = ini.Init_mac_gref.copy()

        return

    def predictX(self, pfd, dyd, ts):

        xlen = len(self.x)
        x_pv_1 = self.x_pv_1
        if xlen == 1:
            x_pv_2 = x_pv_1
            x_pv_3 = x_pv_1
        else:
            x_pv_2 = self.x_pred[1]
            if xlen == 2:
                x_pv_3 = x_pv_2
            else:
                x_pv_3 = self.x_pred[0]

        (self.xp.pd_w,
         self.xp.pd_id,
         self.xp.pd_iq,
         self.xp.pd_EFD,
         self.xp.pd_u_d,
         self.xp.pd_u_q,
         self.xp.pd_dt,
         point_one_tuple,
         point_two_tuple,
         point_three_tuple
         ) = numba_predictX(
            x_pv_1,
            x_pv_2,
            x_pv_3,
            pfd.gen_bus,
            pfd.ws,
            dyd.gen_genrou_odr,
            dyd.exc_sexs_xi_st,
            dyd.exc_sexs_odr,
            ts,
            xlen,
        )

        # Unpack `point_one_tuple`
        (self.xp.pv_dt_1,
         self.xp.pv_w_1,
         self.xp.pv_id_1,
         self.xp.pv_iq_1,
         self.xp.pv_ifd_1,
         self.xp.pv_i1d_1,
         self.xp.pv_i1q_1,
         self.xp.pv_i2q_1,
         self.xp.pv_EFD_1,
         self.xp.pv_psyd_1,
         self.xp.pv_psyq_1,
         self.xp.pv_u_d_1,
         self.xp.pv_u_q_1,
         self.xp.pv_i_d_1,
         self.xp.pv_i_q_1,
         ) = point_one_tuple

        if xlen > 1:
            # Unpack `point_two_tuple`
            (self.xp.pv_dt_2,
             self.xp.pv_w_2,
             self.xp.pv_id_2,
             self.xp.pv_iq_2,
             self.xp.pv_ifd_2,
             self.xp.pv_i1d_2,
             self.xp.pv_i1q_2,
             self.xp.pv_i2q_2,
             self.xp.pv_EFD_2,
             self.xp.pv_psyd_2,
             self.xp.pv_psyq_2,
             self.xp.pv_u_d_2,
             self.xp.pv_u_q_2,
             self.xp.pv_i_d_2,
             self.xp.pv_i_q_2,
             ) = point_two_tuple

        if xlen > 2:
            # Unpack `point_three_tuple`
            (self.xp.pv_dt_3,
             self.xp.pv_w_3,
             self.xp.pv_id_3,
             self.xp.pv_iq_3,
             self.xp.pv_ifd_3,
             self.xp.pv_i1d_3,
             self.xp.pv_i1q_3,
             self.xp.pv_i2q_3,
             self.xp.pv_EFD_3,
             self.xp.pv_psyd_3,
             self.xp.pv_psyq_3,
             self.xp.pv_u_d_3,
             self.xp.pv_u_q_3,
             self.xp.pv_i_d_3,
             self.xp.pv_i_q_3,
             ) = point_three_tuple
        return

    def updateIg(self, pfd, dyd, ini):
        numba_updateIg(
            self.Igs,
            self.Isg,
            self.x_pv_1,
            self.ed_mod,
            self.eq_mod,
            self.theta,
            self.xp.pv_his_d_1,
            self.xp.pv_his_fd_1,
            self.xp.pv_his_1d_1,
            self.xp.pv_his_q_1,
            self.xp.pv_his_1q_1,
            self.xp.pv_his_2q_1,
            self.xp.pv_his_red_d_1,
            self.xp.pv_his_red_q_1,
            # pfd
            pfd.gen_bus,
            pfd.bus_num,
            # dyd
            dyd.base_Is,
            dyd.ec_Rfd,
            dyd.ec_Lad,
            dyd.gen_genrou_odr,
            # ini
            ini.Init_mac_alpha,
            ini.Init_mac_Rd,
            ini.Init_mac_Rq,
            ini.Init_mac_Rd2,
            ini.Init_mac_Rq2,
            ini.Init_mac_Rd_coe,
            ini.Init_mac_Rq_coe,
            ini.Init_mac_Rav,
            ini.Init_net_IbaseA,
            # self.xp
            self.xp.pv_i_d_1,
            self.xp.pv_u_d_1,
            self.xp.pv_EFD_1,
            self.xp.pv_i_q_1,
            self.xp.pv_u_q_1,
            self.xp.pd_EFD,
            self.xp.pd_u_d,
            self.xp.pd_u_q,
            self.xp.pd_id,
            self.xp.pd_iq,
            self.xp.pd_dt,
            self.flag_gentrip,
            self.i_gentrip,
        )

    def updateIibr(self, pfd, dyd, ini):
        if len(self.v) == 1:
            vtemp = self.v[0]
        else:
            vtemp = self.Vsol

        numba_updateIibr(
            ## Begin "Returned" Arrays ##
            self.Igi,
            self.Iibr,
            ## End "Returned" Arrays ##
            # pfd
            pfd.ibr_bus,
            pfd.bus_num,
            # dyd
            dyd.ibr_Ibase,
            # ini
            ini.Init_net_IbaseA,
            dyd.ibr_odr,
            # self.xp
            vtemp,
            self.x_ibr_pv_1,
            self.ts,
            self.x_bus_pv_1,
            dyd.bus_odr,
        )

        return

    def solveV(self, ini):
        self.Vsol_1 = self.Vsol
        if self.loadmodel_option == 1:
            self.I_RHS = self.Igs + self.Igi + self.node_Ihis
        else:
            self.I_RHS = self.Igs + self.Igi + self.node_Ihis + self.Il

        if ini.admittance_mode == 'inv':
            self.Vsol = ini.Init_net_G0_inv * self.I_RHS
        elif ini.admittance_mode == 'lu':
            self.Vsol = ini.Init_net_G0_lu.solve(self.I_RHS)
        elif ini.admittance_mode == 'bbd':
            tmpIRHS = self.I_RHS[ini.index_order]
            tmpVsol = ini.Init_net_G0_bbd_lu.schur_solve(tmpIRHS)
            self.Vsol = tmpVsol[ini.inv_order]
        else:
            raise ValueError('Unrecognized mode: {}'.format(ini.admittance_mode))
        return

    def updateX(self, pfd, dyd, ini, tn):
        self.x_pv_1 = numba_updateX(
            # Altered Arguments
            self.x_pv_1,
            self.xp.nx_ed,
            self.xp.nx_eq,
            self.xp.nx_id,
            self.xp.nx_iq,
            self.xp.nx_ifd,
            self.xp.nx_i1d,
            self.xp.nx_i1q,
            self.xp.nx_i2q,
            self.xp.nx_psyd,
            self.xp.nx_psyq,
            self.xp.nx_psyfd,
            self.xp.nx_psy1q,
            self.xp.nx_psy1d,
            self.xp.nx_psy2q,
            self.xp.nx_te,
            self.xp.nx_w,
            self.xp.nx_EFD,
            self.xp.nx_dt,
            self.xp.nx_v1,
            self.xp.nx_pm,
            # Constant Arguments
            self.xp.pd_dt,
            self.xp.pd_EFD,
            self.xp.pv_his_fd_1,
            self.xp.pv_his_1d_1,
            self.xp.pv_his_1q_1,
            self.xp.pv_his_2q_1,
            self.xp.pv_dt_1,
            self.xp.pv_w_1,
            self.xp.pv_EFD_1,
            pfd.gen_bus,
            pfd.bus_num,
            pfd.ws,
            pfd.basemva,
            pfd.gen_MVA_base,
            dyd.gen_H,
            dyd.gen_D,
            dyd.gen_genrou_n,
            dyd.gen_genrou_odr,
            dyd.gen_genrou_xi_st,
            dyd.ec_Rfd,
            dyd.ec_Lad,
            dyd.ec_Laq,
            dyd.ec_Ll,
            dyd.ec_Lffd,
            dyd.ec_L11q,
            dyd.ec_L11d,
            dyd.ec_Lf1d,
            dyd.ec_L22q,
            dyd.pss_ieeest_A1,
            dyd.pss_ieeest_A2,
            dyd.pss_ieeest_A3,
            dyd.pss_ieeest_A4,
            dyd.pss_ieeest_A5,
            dyd.pss_ieeest_A6,
            dyd.pss_ieeest_T1,
            dyd.pss_ieeest_T2,
            dyd.pss_ieeest_T3,
            dyd.pss_ieeest_T4,
            dyd.pss_ieeest_T5,
            dyd.pss_ieeest_T6,
            dyd.pss_ieeest_KS,
            dyd.pss_ieeest_LSMAX,
            dyd.pss_ieeest_LSMIN,
            dyd.pss_ieeest_VCL,
            dyd.pss_ieeest_VCU,
            dyd.pss_ieeest_idx,
            dyd.pss_ieeest_odr,
            dyd.pss_ieeest_xi_st,
            dyd.exc_sexs_TA,
            dyd.exc_sexs_TB,
            dyd.exc_sexs_K,
            dyd.exc_sexs_TE,
            dyd.exc_sexs_Emin,
            dyd.exc_sexs_Emax,
            dyd.exc_sexs_idx,
            dyd.exc_sexs_n,
            dyd.exc_sexs_odr,
            dyd.exc_sexs_xi_st,
            dyd.gov_type,
            dyd.gov_tgov1_bus,
            dyd.gov_tgov1_id,
            dyd.gov_tgov1_Dt,
            dyd.gov_tgov1_R,
            dyd.gov_tgov1_T1,
            dyd.gov_tgov1_T2,
            dyd.gov_tgov1_T3,
            dyd.gov_tgov1_Vmax,
            dyd.gov_tgov1_Vmin,
            dyd.gov_tgov1_idx,
            dyd.gov_tgov1_n,
            dyd.gov_tgov1_odr,
            dyd.gov_tgov1_xi_st,
            dyd.gov_hygov_bus,
            dyd.gov_hygov_id,
            dyd.gov_hygov_At,
            dyd.gov_hygov_Dturb,
            dyd.gov_hygov_GMAX,
            dyd.gov_hygov_GMIN,
            dyd.gov_hygov_R,
            dyd.gov_hygov_TW,
            dyd.gov_hygov_Tf,
            dyd.gov_hygov_Tg,
            dyd.gov_hygov_Tr,
            dyd.gov_hygov_VELM,
            dyd.gov_hygov_qNL,
            dyd.gov_hygov_r,
            dyd.gov_hygov_idx,
            dyd.gov_hygov_n,
            dyd.gov_hygov_odr,
            dyd.gov_hygov_xi_st,
            dyd.gov_gast_bus,
            dyd.gov_gast_id,
            dyd.gov_gast_R,
            dyd.gov_gast_LdLmt,
            dyd.gov_gast_KT,
            dyd.gov_gast_T1,
            dyd.gov_gast_T2,
            dyd.gov_gast_T3,
            dyd.gov_gast_VMIN,
            dyd.gov_gast_VMAX,
            dyd.gov_gast_Dturb,
            dyd.gov_gast_idx,
            dyd.gov_gast_n,
            dyd.gov_gast_odr,
            dyd.gov_gast_xi_st,
            dyd.bus_odr,
            ini.Init_mac_Rav,
            ini.Init_mac_Rd1,
            ini.Init_mac_Rd1inv,
            ini.Init_mac_Rq1,
            ini.Init_mac_Rq1inv,
            ini.Init_mac_Gequiv,
            ini.tgov1_2gen,
            ini.hygov_2gen,
            ini.gast_2gen,
            self.vref,
            self.gref,
            self.Vsol,
            self.Isg,
            self.ed_mod,
            self.eq_mod,
            self.vref_1,
            self.x_bus_pv_1,
            self.ts,
            self.flag_gentrip,
            self.i_gentrip,
        )

        return

    def updateXibr(self, pfd, dyd, ini, ts):
        self.x_ibr_pv_1 = numba_updateXibr(
            # Altered Arguments
            self.x_ibr_pv_1,
            # Constant Arguments

            pfd.ibr_bus, pfd.bus_num, pfd.ws, pfd.basemva, pfd.ibr_MVA_base,
            dyd.ibr_regca_Volim, dyd.ibr_regca_Khv, dyd.ibr_regca_Lvpnt0, dyd.ibr_regca_Lvpnt1, dyd.ibr_regca_Tg,
            dyd.ibr_regca_Iqrmax, dyd.ibr_regca_Iqrmin, dyd.ibr_regca_Tfltr, dyd.ibr_regca_Zerox, dyd.ibr_regca_Brkpt,
            dyd.ibr_regca_Rrpwr,
            dyd.ibr_reecb_PQFLAG, dyd.ibr_reecb_PFFLAG, dyd.ibr_reecb_VFLAG, dyd.ibr_reecb_QFLAG, dyd.ibr_reecb_Imax,
            dyd.ibr_reecb_Vdip, dyd.ibr_reecb_Vup, dyd.ibr_reecb_Trv, dyd.ibr_reecb_dbd1, dyd.ibr_reecb_dbd2,
            dyd.ibr_reecb_Kqv,
            dyd.ibr_reecb_Iqll, dyd.ibr_reecb_Iqhl, dyd.ibr_reecb_Tp, dyd.ibr_reecb_Qmin, dyd.ibr_reecb_Qmax,
            dyd.ibr_reecb_Kqp, dyd.ibr_reecb_Kqi, dyd.ibr_reecb_Vmin, dyd.ibr_reecb_Vmax, dyd.ibr_reecb_Kvp,
            dyd.ibr_reecb_Kvi, dyd.ibr_reecb_Tiq,
            dyd.ibr_reecb_dPmin, dyd.ibr_reecb_dPmax, dyd.ibr_reecb_Pmin, dyd.ibr_reecb_Pmax, dyd.ibr_reecb_Tpord,
            dyd.ibr_repca_FFlag, dyd.ibr_repca_VCFlag, dyd.ibr_repca_RefFlag, dyd.ibr_repca_fdbd1, dyd.ibr_repca_fdbd2,
            dyd.ibr_repca_Ddn, dyd.ibr_repca_Dup, dyd.ibr_repca_Tp, dyd.ibr_repca_femin, dyd.ibr_repca_femax,
            dyd.ibr_repca_Kpg,
            dyd.ibr_repca_Kig, dyd.ibr_repca_Pmin, dyd.ibr_repca_Pmax, dyd.ibr_repca_Tg, dyd.ibr_repca_Rc,
            dyd.ibr_repca_Xc, dyd.ibr_repca_Kc, dyd.ibr_repca_Tfltr, dyd.ibr_repca_dbd1, dyd.ibr_repca_dbd2,
            dyd.ibr_repca_emin, dyd.ibr_repca_emax,
            dyd.ibr_repca_Vfrz, dyd.ibr_repca_Kp, dyd.ibr_repca_Ki, dyd.ibr_repca_Qmin, dyd.ibr_repca_Qmax,
            dyd.ibr_repca_Tft, dyd.ibr_repca_Tfv,
            # dyd.ibr_pll_ke,dyd.ibr_pll_te,
            dyd.ibr_odr,
            ini.Init_ibr_regca_Qgen0, ini.Init_ibr_reecb_pfaref, ini.Init_ibr_reecb_Vref0, ini.Init_ibr_repca_Pref_out,
            self.Vsol,
            self.x_bus_pv_1,
            dyd.bus_odr,
            # vtm,
            self.Iibr,
            ts,
        )

        return

    def updateIhis(self, ini):

        (brch_Ipre, node_Ihis) = numba_updateIhis(self.brch_Ihis,
                                                  self.Vsol,
                                                  ini.Init_net_coe0,
                                                  ini.Init_net_N)
        self.brch_Ipre = brch_Ipre
        self.node_Ihis = node_Ihis

        return

    def updateIl(self, pfd, dyd, tn):
        nbus = len(pfd.bus_num)
        for i in range(len(pfd.load_bus)):
            busi_idx = np.where(pfd.bus_num == pfd.load_bus[i])[0][0]

            ZL_mag = self.x_load_pv_1[i * dyd.load_odr + 0]
            ZL_ang = self.x_load_pv_1[i * dyd.load_odr + 1]

            Vmag = self.x_bus_pv_1[busi_idx * dyd.bus_odr + 3]
            Vang = self.x_bus_pv_1[busi_idx * dyd.bus_odr + 1]
            if tn * self.ts > self.t_release_f:  # before 0.1 sec, 377 rad/s is fed to load as PLL freq
                w = self.x_bus_pv_1[busi_idx * dyd.bus_odr + 2] * pfd.ws
            else:
                w = pfd.ws

            Imag = Vmag / ZL_mag

            Vanga = Vang + w * self.ts
            self.Il[busi_idx] = - Imag * np.cos(Vanga - ZL_ang)

            Vangb = Vang - 2 * np.pi / 3 + w * self.ts
            self.Il[busi_idx + nbus] = - Imag * np.cos(Vangb - ZL_ang)

            Vangc = Vang + 2 * np.pi / 3 + w * self.ts
            self.Il[busi_idx + 2 * nbus] = - Imag * np.cos(Vangc - ZL_ang)

            self.Ild[3 * i] = - Imag * np.cos(Vanga - ZL_ang)
            self.Ild[3 * i + 1] = - Imag * np.cos(Vangb - ZL_ang)
            self.Ild[3 * i + 2] = - Imag * np.cos(Vangc - ZL_ang)

    def updateXl(self, pfd, dyd, tn):

        # calc load power
        nbus = len(pfd.bus_num)
        x_load_nx = np.zeros(len(pfd.load_bus) * dyd.load_odr)
        for i in range(len(pfd.load_bus)):
            busi_idx = np.where(pfd.bus_num == pfd.load_bus[i])[0][0]

            ZL_mag = self.x_load_pv_1[i * dyd.load_odr + 0]
            ZL_ang = self.x_load_pv_1[i * dyd.load_odr + 1]
            vt_tn = self.x_bus_pv_1[busi_idx * dyd.bus_odr + 3]

            # Stemp = vt_tn * vt_tn / ZL_mag * complex(np.cos(ZL_ang), np.sin(ZL_ang))

            # check and update Zload (without update, const Z load is used)
            x_load_nx[i * dyd.load_odr + 0] = ZL_mag
            x_load_nx[i * dyd.load_odr + 1] = ZL_ang
            # x_load_nx[i * dyd.load_odr + 2] = Stemp.real
            # x_load_nx[i * dyd.load_odr + 3] = Stemp.imag

            # measured power
            busi = np.where(pfd.bus_num == pfd.load_bus[i])[0][0]
            va = self.Vsol[busi]
            vb = self.Vsol[busi + nbus]
            vc = self.Vsol[busi + 2 * nbus]

            ia = self.Ild[3 * i]
            ib = self.Ild[3 * i + 1]
            ic = self.Ild[3 * i + 2]

            # previously forgot to convert to IBR base
            pe = - ((va * ia + vb * ib + vc * ic) * 2.0 / 3.0)
            qe = - (((vb - vc) * ia + (vc - va) * ib + (va - vb) * ic) / np.sqrt(3.0) * 2.0 / 3.0)

            x_load_nx[i * dyd.load_odr + 2] = pe
            x_load_nx[i * dyd.load_odr + 3] = qe

        self.x_load_pv_1 = x_load_nx

    def BusMea(self, pfd, dyd, tn):
        nbus = len(pfd.bus_num)

        # # FFT
        # if len(self.fft_vabc) == self.fft_N:
        #     data = np.array(self.fft_vabc)
        #     fft_res = np.fft.rfft(data, self.fft_N, 0)
        #     vm = np.zeros(3*nbus)
        #     va = np.zeros(3*nbus)
        #     for i in range(3*nbus):
        #         vm[i] = abs(fft_res[1][i]) * 2 / self.fft_N
        #         va[i] = np.angle(fft_res[1][i])

        #     vma = np.concatenate((vm, va))

        #     vpn0 = np.zeros(nbus*6)
        #     for i in range(nbus):
        #         vabc_phasor = np.asarray([vma[i]*np.exp(1j*vma[i+3*nbus]), vma[i+nbus]*np.exp(1j*vma[i+4*nbus]), vma[i+2*nbus]*np.exp(1j*vma[i+5*nbus])])
        #         vpn0i = np.dot(Ainv, vabc_phasor)
        #         vpn0[i] = abs(vpn0i[2])
        #         vpn0[i+3*nbus] = np.angle(vpn0i[2])
        #         vpn0[i+nbus] = abs(vpn0i[1])
        #         vpn0[i + 4 * nbus] = np.angle(vpn0i[1])
        #         vpn0[i+2*nbus] = abs(vpn0i[0])
        #         vpn0[i + 5 * nbus] = np.angle(vpn0i[0])

        #     ## save a trace
        #     # self.fft_vma[len(self.fft_vma)] = vma
        #     # self.fft_vpn0[len(self.fft_vpn0)] = vpn0

        #     ## save the latest state only
        #     self.fft_vma = vma
        #     self.fft_vpn0 = vpn0

        # else:
        #     ## save a trace
        #     # self.fft_vma[len(self.fft_vma)] = self.fft_vma[len(self.fft_vma)-1]
        #     # self.fft_vpn0[len(self.fft_vpn0)] = self.fft_vpn0[len(self.fft_vpn0)-1]

        #     ## save the latest state only
        #     self.fft_vma = np.asarray(self.fft_vma)
        #     self.fft_vpn0 = np.asarray(self.fft_vpn0)

        # # bus volt mag measurement
        # x_bus_nx = np.zeros(nbus * dyd.bus_odr)
        # for i in range(nbus):
        #     ze_1 = self.x_bus_pv_1[i * dyd.bus_odr + 0]
        #     de_1 = self.x_bus_pv_1[i * dyd.bus_odr + 1]
        #     we_1 = self.x_bus_pv_1[i * dyd.bus_odr + 2]

        #     vt_1 = self.x_bus_pv_1[i * dyd.bus_odr + 3]
        #     vtm_1 = self.x_bus_pv_1[i * dyd.bus_odr + 4]
        #     dvtm_1 = self.x_bus_pv_1[i * dyd.bus_odr + 5]

        #     va = self.Vsol[i]
        #     vb = self.Vsol[i + nbus]
        #     vc = self.Vsol[i + 2 * nbus]

        #     # bus voltage magnitude
        #     nx_vt = np.sqrt((va * va + vb * vb + vc * vc) * 2 / 3)
        #     x_bus_nx[i * dyd.bus_odr + 3] = nx_vt

        #     nx_vtm = vtm_1 + (nx_vt - vtm_1) / dyd.vm_te[i] * self.ts
        #     x_bus_nx[i * dyd.bus_odr + 4] = nx_vtm

        #     nx_dvtm = (nx_vtm - vtm_1) / self.ts
        #     x_bus_nx[i * dyd.bus_odr + 5] = nx_dvtm

        #     # bus freq and angle by PLL
        #     # theta
        #     theta = de_1 + self.ts * we_1 * pfd.ws
        #     Pk = np.array([[np.cos(theta),
        #                     np.cos(theta - np.pi * 2.0 / 3.0),
        #                     np.cos(theta + np.pi * 2.0 / 3.0)
        #                     ],
        #                    [-np.sin(theta),
        #                     -np.sin(theta - np.pi * 2.0 / 3.0),
        #                     -np.sin(theta + np.pi * 2.0 / 3.0)
        #                     ],
        #                    [0.5, 0.5, 0.5]
        #                    ])

        #     # vd = 2.0 / 3.0 * np.sum(Pk[0, :] * [va,vb,vc])
        #     vq = 2.0 / 3.0 * np.sum(Pk[1, :] * [va, vb, vc])

        #     nx_ze = ze_1 + dyd.pll_ke[i] / dyd.pll_te[i] * vq * self.ts
        #     nx_de = de_1 + we_1 * pfd.ws * self.ts
        #     if tn * self.ts < self.t_release_f:
        #         nx_we = 1.0
        #         # x_bus_nx[i * dyd.bus_odr + 3] = vt_1
        #     else:
        #         nx_we = 1 + dyd.pll_ke[i] * vq + ze_1

        #     x_bus_nx[i * dyd.bus_odr + 0] = nx_ze
        #     x_bus_nx[i * dyd.bus_odr + 1] = nx_de
        #     x_bus_nx[i * dyd.bus_odr + 2] = nx_we
        #     # x_bus_nx[i * dyd.bus_odr + 3] = nx_vt
        x_bus_nx = np.zeros(nbus * dyd.bus_odr)

        numba_BusMea(
            x_bus_nx,
            self.Vsol,
            self.x_bus_pv_1,
            nbus,
            self.ts,
            self.t_release_f,
            pfd.ws,
            dyd.bus_odr,
            dyd.vm_te,
            dyd.pll_ke,
            dyd.pll_te,
            tn
        )
        self.x_bus_pv_1 = x_bus_nx
        return

    def StepChange(self, dyd, ini, tn):
        if tn * self.ts >= self.t_sc:
            if self.flag_sc == 1:
                if self.flag_exc_gov == 1:
                    # gov pm
                    if dyd.gov_type[self.i_gen_sc] == 2:  # 'TGOV1'
                        idx_gov = np.where(dyd.gov_tgov1_idx == self.i_gen_sc)[0][0]
                        self.gref[ini.tgov1_2gen[idx_gov]] = self.gref[ini.tgov1_2gen[idx_gov]] + self.dsp
                        self.flag_sc = 0

                    if dyd.gov_type[self.i_gen_sc] == 1:  # 'HYGOV'
                        idx_gov = np.where(dyd.gov_hygov_idx == self.i_gen_sc)[0][0]
                        self.gref[ini.hygov_2gen[idx_gov]] = self.gref[ini.hygov_2gen[idx_gov]] + self.dsp
                        self.flag_sc = 0

                    if dyd.gov_type[self.i_gen_sc] == 0:  # 'GAST'
                        idx_gov = np.where(dyd.gov_gast_idx == self.i_gen_sc)[0][0]
                        self.gref[ini.gast_2gen[idx_gov]] = self.gref[ini.gast_2gen[idx_gov]] + self.dsp
                        self.flag_sc = 0

                if self.flag_exc_gov == 0:
                    ini.Init_mac_vref[self.i_gen_sc] = ini.Init_mac_vref[self.i_gen_sc] + self.dsp
                    self.flag_sc = 0

    def GenTrip(self, pfd, dyd, ini, tn, netMod):
        if self.t_gentrip:
            if tn * self.ts >= self.t_gentrip:
                genbus_idx = int(np.where(pfd.bus_num == pfd.gen_bus[self.i_gentrip])[0])
                self.Igs[genbus_idx] = 0.0
                self.Igs[genbus_idx + len(pfd.bus_num)] = 0.0
                self.Igs[genbus_idx + 2 * len(pfd.bus_num)] = 0.0
                if self.flag_gentrip == 1:
                    ini.InitNet(pfd, self.ts, self.loadmodel_option)  # to re-create rows, cols, data for G0
                    ini.MergeMacG(pfd, dyd, self.ts, self.i_gentrip, netMod)
                    self.flag_gentrip = 0

    def Re_Init(self, pfd, dyd, ini):
        nbus = len(pfd.bus_num)
        ngen = len(pfd.gen_bus)

        # updateI_BU
        brch_Ihis = self.brch_Ihis
        Vsol = self.Vsol_1
        Init_net_coe0 = ini.Init_net_coe0

        node_Ihis = np.zeros(nbus * 3)
        brch_Ipre = self.brch_Ipre

        for i in range(len(brch_Ihis)):
            if np.sign(Init_net_coe0[i, 3]) == 1:
                c1 = 1
                c2 = 0
            else:
                c1 = 0
                c2 = 1

            Fidx = int(Init_net_coe0[i, 0].real)
            Tidx = int(Init_net_coe0[i, 1].real)

            #### IF CLAUSE ####
            if Init_net_coe0[i, 1] == -1:
                if Init_net_coe0[i, 2] == 0:
                    continue
                brch_Ihis_temp = c1 * Init_net_coe0[i, 3] * brch_Ipre[i] + c2 * np.real(Init_net_coe0[i, 4]) * Vsol[
                    Fidx]

            #### ELSE CLAUSE ####
            else:
                brch_Ihis_temp = c1 * Init_net_coe0[i, 3] * brch_Ipre[i] + c2 * np.real(Init_net_coe0[i, 4]) * (
                        Vsol[Fidx] - Vsol[Tidx])
                node_Ihis[Tidx] += brch_Ihis_temp.real
            brch_Ihis[i] = brch_Ihis_temp.real
            node_Ihis[Fidx] -= brch_Ihis_temp.real

        ## predictX
        pv_dt_1 = np.zeros(ngen)
        pd_dt = np.zeros(ngen)

        pv_w_1 = np.zeros(ngen)
        pv_w_2 = np.zeros(ngen)
        pd_w = np.zeros(ngen)

        pv_id_1 = np.zeros(ngen)
        pv_id_2 = np.zeros(ngen)
        pd_id = np.zeros(ngen)

        pv_iq_1 = np.zeros(ngen)
        pv_iq_2 = np.zeros(ngen)
        pd_iq = np.zeros(ngen)

        pv_ifd_1 = np.zeros(ngen)
        pv_i1d_1 = np.zeros(ngen)
        pv_i1q_1 = np.zeros(ngen)
        pv_i2q_1 = np.zeros(ngen)

        pv_ed_1 = np.zeros(ngen)
        pv_eq_1 = np.zeros(ngen)

        pv_EFD_1 = np.zeros(ngen)
        pv_EFD_2 = np.zeros(ngen)
        pd_EFD = np.zeros(ngen)

        pv_psyd_1 = np.zeros(ngen)
        pv_psyd_2 = np.zeros(ngen)

        pv_psyq_1 = np.zeros(ngen)
        pv_psyq_2 = np.zeros(ngen)

        pv_u_d_1 = np.zeros(ngen)
        pv_u_d_2 = np.zeros(ngen)
        pd_u_d = np.zeros(ngen)

        pv_u_q_1 = np.zeros(ngen)
        pv_u_q_2 = np.zeros(ngen)
        pd_u_q = np.zeros(ngen)

        for i in range(len(pfd.gen_bus)):
            idx = i * dyd.gen_genrou_odr + dyd.gen_genrou_xi_st

            pv_dt_1[i] = self.x_pred[0][idx + 0]

            pv_w_1[i] = self.x_pred[0][idx + 1]
            pv_w_2[i] = self.x_pred[1][idx + 1]

            pv_id_1[i] = self.x_pred[0][idx + 2]
            pv_id_2[i] = self.x_pred[1][idx + 2]

            pv_iq_1[i] = self.x_pred[0][idx + 3]
            pv_iq_2[i] = self.x_pred[1][idx + 3]

            pv_ifd_1[i] = self.x_pred[0][idx + 4]
            pv_i1d_1[i] = self.x_pred[0][idx + 5]
            pv_i1q_1[i] = self.x_pred[0][idx + 6]
            pv_i2q_1[i] = self.x_pred[0][idx + 7]

            pv_ed_1[i] = self.x_pred[0][idx + 8]
            pv_eq_1[i] = self.x_pred[0][idx + 9]

            pv_psyd_1[i] = self.x_pred[0][idx + 10]
            pv_psyd_2[i] = self.x_pred[1][idx + 10]

            pv_psyq_1[i] = self.x_pred[0][idx + 11]
            pv_psyq_2[i] = self.x_pred[1][idx + 11]

            # exc
            idx_exc = i * dyd.exc_sexs_odr + dyd.exc_sexs_xi_st
            pv_EFD_1[i] = self.x_pred[0][idx_exc + 1]
            pv_EFD_2[i] = self.x_pred[1][idx_exc + 1]

            pv_u_d_1[i] = -pv_psyq_1[i] * pv_w_1[i] / pfd.ws
            pv_u_d_2[i] = -pv_psyq_2[i] * pv_w_2[i] / pfd.ws

            pv_u_q_1[i] = pv_psyd_1[i] * pv_w_1[i] / pfd.ws
            pv_u_q_2[i] = pv_psyd_2[i] * pv_w_2[i] / pfd.ws

            pd_w[i] = 2.0 * pv_w_1[i] - pv_w_2[i]
            pd_id[i] = 2.0 * pv_id_1[i] - pv_id_2[i]
            pd_iq[i] = 2.0 * pv_iq_1[i] - pv_iq_2[i]
            pd_EFD[i] = 2.0 * pv_EFD_1[i] - pv_EFD_2[i]
            pd_u_d[i] = 2.0 * pv_u_d_1[i] - pv_u_d_2[i]
            pd_u_q[i] = 2.0 * pv_u_q_1[i] - pv_u_q_2[i]

            pd_dt[i] = pv_dt_1[i] + self.ts / 2 * (pd_w[i] + pv_w_1[i]) / 2

        #  updateIg
        Igs = self.Igs * 0

        Ias_n = Igs[:nbus]
        Ibs_n = Igs[nbus:2 * nbus]
        Ics_n = Igs[2 * nbus:]

        pv_his_d_1 = np.zeros(ngen)
        pv_his_fd_1 = np.zeros(ngen)
        pv_his_1d_1 = np.zeros(ngen)
        pv_his_q_1 = np.zeros(ngen)
        pv_his_1q_1 = np.zeros(ngen)
        pv_his_2q_1 = np.zeros(ngen)
        pv_his_red_d_1 = np.zeros(ngen)
        pv_his_red_q_1 = np.zeros(ngen)
        ed_mod = np.zeros(ngen)
        eq_mod = np.zeros(ngen)
        theta = np.zeros(ngen)

        for i in range(len(pfd.gen_bus)):
            if i == self.i_gentrip:
                if self.flag_gentrip == 0:
                    continue

            EFD2efd = dyd.ec_Rfd[i] / dyd.ec_Lad[i]

            pv_i_d_1 = [-pv_id_1[i], pv_ifd_1[i], pv_i1d_1[i]]
            pv_i_q_1 = [-pv_iq_1[i], pv_i1q_1[i], pv_i2q_1[i]]

            temp1 = np.sum(ini.Init_mac_Rd2[i, 0, :] * pv_i_d_1)
            pv_his_d_1_temp = -ini.Init_mac_alpha[i] * pv_ed_1[i] + ini.Init_mac_alpha[i] * pv_u_d_1[i] + temp1
            pv_his_d_1[i] = pv_his_d_1_temp

            temp2 = np.sum(ini.Init_mac_Rd2[i, 1, :] * pv_i_d_1)
            pv_his_fd_1_temp = -ini.Init_mac_alpha[i] * pv_EFD_1[i] * EFD2efd + temp2
            pv_his_fd_1[i] = pv_his_fd_1_temp

            temp3 = np.sum(ini.Init_mac_Rd2[i, 2, :] * pv_i_d_1)
            pv_his_1d_1[i] = temp3

            temp4 = np.sum(ini.Init_mac_Rq2[i, 0, :] * pv_i_q_1)
            pv_his_q_1_temp = -ini.Init_mac_alpha[i] * pv_eq_1[i] + ini.Init_mac_alpha[i] * pv_u_q_1[i] + temp4
            pv_his_q_1[i] = pv_his_q_1_temp

            temp5 = np.sum(ini.Init_mac_Rq2[i, 1, :] * pv_i_q_1)
            pv_his_1q_1[i] = temp5

            temp6 = np.sum(ini.Init_mac_Rq2[i, 2, :] * pv_i_q_1)
            pv_his_2q_1[i] = temp6

            pv_his_red_d_1_temp = pv_his_d_1_temp - (
                    ini.Init_mac_Rd_coe[i, 0] * (pv_his_fd_1_temp - pd_EFD[i] * EFD2efd) + ini.Init_mac_Rd_coe[
                i, 1] * temp3)
            pv_his_red_q_1_temp = pv_his_q_1_temp - (
                        ini.Init_mac_Rq_coe[i, 0] * temp5 + ini.Init_mac_Rq_coe[i, 1] * temp6)
            pv_his_red_d_1[i] = pv_his_red_d_1_temp
            pv_his_red_q_1[i] = pv_his_red_q_1_temp

            ed_temp = pd_u_d[i] + pv_his_red_d_1_temp
            eq_temp = pd_u_q[i] + pv_his_red_q_1_temp

            ed_mod_temp = ed_temp - (ini.Init_mac_Rd[i] - ini.Init_mac_Rq[i]) / 2.0 * pd_id[i]
            eq_mod_temp = eq_temp + (ini.Init_mac_Rd[i] - ini.Init_mac_Rq[i]) / 2.0 * pd_iq[i]

            id_src_temp = ed_mod_temp / ini.Init_mac_Rav[i]
            iq_src_temp = eq_mod_temp / ini.Init_mac_Rav[i]

            ed_mod[i] = ed_mod_temp
            eq_mod[i] = eq_mod_temp

            # theta
            genbus_idx = np.where(pfd.bus_num == pfd.gen_bus[i])[0][0]
            theta[i] = pd_dt[i] - np.pi / 2.0

            iPk = np.array([[np.cos(theta[i]), - np.sin(theta[i]), 1.0],
                            [np.cos(theta[i] - np.pi * 2.0 / 3.0), -np.sin(theta[i] - np.pi * 2.0 / 3.0), 1.0],
                            [np.cos(theta[i] + np.pi * 2.0 / 3.0), -np.sin(theta[i] + np.pi * 2.0 / 3.0), 1.0]
                            ])
            res = iPk[:, 0] * id_src_temp + iPk[:, 1] * iq_src_temp

            Ias_n[genbus_idx] = Ias_n[genbus_idx] + res[0] * dyd.base_Is[i] / (ini.Init_net_IbaseA[genbus_idx] * 1000.0)
            Ibs_n[genbus_idx] = Ibs_n[genbus_idx] + res[1] * dyd.base_Is[i] / (ini.Init_net_IbaseA[genbus_idx] * 1000.0)
            Ics_n[genbus_idx] = Ics_n[genbus_idx] + res[2] * dyd.base_Is[i] / (ini.Init_net_IbaseA[genbus_idx] * 1000.0)

        #  Solve v
        Vsol = ini.Init_net_G0_lu.solve(Igs + node_Ihis)

        # UpdateIhis
        node_Ihis_out = np.zeros(nbus * 3)
        brch_Ihis = np.zeros(len(Init_net_coe0))

        for i in range(len(brch_Ihis)):
            Fidx = int(Init_net_coe0[i, 0].real)
            Tidx = int(Init_net_coe0[i, 1].real)

            #### IF CLAUSE ####
            if Init_net_coe0[i, 1] == -1:
                if Init_net_coe0[i, 2] == 0:
                    continue
                brch_Ihis_temp = Init_net_coe0[i, 3] * brch_Ipre[i] + Init_net_coe0[i, 4] * Vsol[Fidx]

            #### ELSE CLAUSE ####
            else:
                brch_Ihis_temp = Init_net_coe0[i, 3] * brch_Ipre[i] + Init_net_coe0[i, 4] * (
                        Vsol[Fidx] - Vsol[Tidx])
                node_Ihis_out[Tidx] += brch_Ihis_temp.real

            brch_Ihis[i] = brch_Ihis_temp.real
            node_Ihis_out[Fidx] -= brch_Ihis_temp.real

        self.brch_Ihis = brch_Ihis
        self.node_Ihis = node_Ihis_out
        self.flag_reinit = 0

    def dump_res(self, pfd, dyd, ini, SimMod, output_snp_ful, output_snp_1pt, output_res):
        # remove SuperLU objects to be compatible with pickle
        ini.Init_net_G0_lu = []

        # output and plot
        x = []
        for k, v in self.x.items():
            x.append(v.tolist())
        self.x = np.transpose(x)

        if len(pfd.ibr_bus) > 0:
            x_ibr = []
            for k, v in self.x_ibr.items():
                x_ibr.append(v.tolist())
            self.x_ibr = np.transpose(x_ibr)

        vv = []
        for k, v in self.v.items():
            vv.append(v.tolist())
        self.v = np.transpose(vv)

        vv = []
        for k, v in self.x_bus.items():
            vv.append(v.tolist())
        self.x_bus = np.transpose(vv)

        vv = []
        for k, v in self.x_load.items():
            vv.append(v.tolist())
        self.x_load = np.transpose(vv)

        self.t = np.asarray(self.t)
        if SimMod == 0:
            pickle.dump([pfd, dyd, ini, self], open(output_snp_ful, "wb"))

            x = np.squeeze(np.delete(self.x, range(0, len(self.x[0]) - 1, 1), 1))
            self.x = {}
            self.x[0] = x

            x = np.squeeze(np.delete(self.x_bus, range(0, len(self.x_bus[0]) - 1, 1), 1))
            self.x_bus = {}
            self.x_bus[0] = x

            if len(pfd.ibr_bus) > 0:
                x = np.squeeze(np.delete(self.x_ibr, range(0, len(self.x_ibr[0]) - 1, 1), 1))
                self.x_ibr = {}
                self.x_ibr[0] = x

            if len(pfd.load_bus) > 0:
                x = np.squeeze(np.delete(self.x_load, range(0, len(self.x_load[0]) - 1, 1), 1))
                self.x_load = {}
                self.x_load[0] = x

            x = np.squeeze(np.delete(self.v, range(0, len(self.v[0]) - 1, 1), 1))
            self.v = {}
            self.v[0] = x

            pickle.dump([pfd, dyd, ini, self], open(output_snp_1pt, "wb"))
        else:
            pickle.dump([pfd, dyd, ini, self], open(output_res, "wb"))

        return


# states class
class States():
    def __init__(self, ngen):
        self.pv_dt_1 = np.zeros(ngen)
        self.pv_dt_2 = np.zeros(ngen)
        self.pv_dt_3 = np.zeros(ngen)
        self.pd_dt = np.zeros(ngen)
        self.nx_dt = np.zeros(ngen)

        self.pv_w_1 = np.zeros(ngen)
        self.pv_w_2 = np.zeros(ngen)
        self.pv_w_3 = np.zeros(ngen)
        self.pd_w = np.zeros(ngen)
        self.nx_w = np.zeros(ngen)

        self.pv_id_1 = np.zeros(ngen)
        self.pv_id_2 = np.zeros(ngen)
        self.pv_id_3 = np.zeros(ngen)
        self.pd_id = np.zeros(ngen)
        self.nx_id = np.zeros(ngen)

        self.pv_iq_1 = np.zeros(ngen)
        self.pv_iq_2 = np.zeros(ngen)
        self.pv_iq_3 = np.zeros(ngen)
        self.pd_iq = np.zeros(ngen)
        self.nx_iq = np.zeros(ngen)

        self.pv_ifd_1 = np.zeros(ngen)
        self.pv_ifd_2 = np.zeros(ngen)
        self.pv_ifd_3 = np.zeros(ngen)
        self.nx_ifd = np.zeros(ngen)

        self.pv_i1d_1 = np.zeros(ngen)
        self.pv_i1d_2 = np.zeros(ngen)
        self.pv_i1d_3 = np.zeros(ngen)
        self.nx_i1d = np.zeros(ngen)

        self.pv_i1q_1 = np.zeros(ngen)
        self.pv_i1q_2 = np.zeros(ngen)
        self.pv_i1q_3 = np.zeros(ngen)
        self.nx_i1q = np.zeros(ngen)

        self.pv_i2q_1 = np.zeros(ngen)
        self.pv_i2q_2 = np.zeros(ngen)
        self.pv_i2q_3 = np.zeros(ngen)
        self.nx_i2q = np.zeros(ngen)

        self.pv_ed_1 = np.zeros(ngen)
        self.pv_ed_2 = np.zeros(ngen)
        self.pv_ed_3 = np.zeros(ngen)
        self.nx_ed = np.zeros(ngen)

        self.pv_eq_1 = np.zeros(ngen)
        self.pv_eq_2 = np.zeros(ngen)
        self.pv_eq_3 = np.zeros(ngen)
        self.nx_eq = np.zeros(ngen)

        self.pv_psyd_1 = np.zeros(ngen)
        self.pv_psyd_2 = np.zeros(ngen)
        self.pv_psyd_3 = np.zeros(ngen)
        self.nx_psyd = np.zeros(ngen)

        self.pv_psyq_1 = np.zeros(ngen)
        self.pv_psyq_2 = np.zeros(ngen)
        self.pv_psyq_3 = np.zeros(ngen)
        self.nx_psyq = np.zeros(ngen)

        self.pv_psyfd_1 = np.zeros(ngen)
        self.pv_psyfd_2 = np.zeros(ngen)
        self.pv_psyfd_3 = np.zeros(ngen)
        self.nx_psyfd = np.zeros(ngen)

        self.pv_psy1q_1 = np.zeros(ngen)
        self.pv_psy1q_2 = np.zeros(ngen)
        self.pv_psy1q_3 = np.zeros(ngen)
        self.nx_psy1q = np.zeros(ngen)

        self.pv_psy1d_1 = np.zeros(ngen)
        self.pv_psy1d_2 = np.zeros(ngen)
        self.pv_psy1d_3 = np.zeros(ngen)
        self.nx_psy1d = np.zeros(ngen)

        self.pv_psy2q_1 = np.zeros(ngen)
        self.pv_psy2q_2 = np.zeros(ngen)
        self.pv_psy2q_3 = np.zeros(ngen)
        self.nx_psy2q = np.zeros(ngen)

        self.pv_te_1 = np.zeros(ngen)
        self.pv_te_2 = np.zeros(ngen)
        self.pv_te_3 = np.zeros(ngen)
        self.nx_te = np.zeros(ngen)

        self.pv_i_d_1 = np.zeros(ngen)
        self.pv_i_d_2 = np.zeros(ngen)
        self.pv_i_d_3 = np.zeros(ngen)

        self.pv_i_q_1 = np.zeros(ngen)
        self.pv_i_q_2 = np.zeros(ngen)
        self.pv_i_q_3 = np.zeros(ngen)

        self.pv_u_d_1 = np.zeros(ngen)
        self.pv_u_d_2 = np.zeros(ngen)
        self.pv_u_d_3 = np.zeros(ngen)
        self.pd_u_d = np.zeros(ngen)

        self.pv_u_q_1 = np.zeros(ngen)
        self.pv_u_q_2 = np.zeros(ngen)
        self.pv_u_q_3 = np.zeros(ngen)
        self.pd_u_q = np.zeros(ngen)

        self.pv_his_d_1 = np.zeros(ngen)
        self.pv_his_fd_1 = np.zeros(ngen)
        self.pv_his_1d_1 = np.zeros(ngen)
        self.pv_his_q_1 = np.zeros(ngen)
        self.pv_his_1q_1 = np.zeros(ngen)
        self.pv_his_2q_1 = np.zeros(ngen)
        self.pv_his_red_d_1 = np.zeros(ngen)
        self.pv_his_red_q_1 = np.zeros(ngen)

        # EXC
        self.pv_EFD_1 = np.zeros(ngen)
        self.pv_EFD_2 = np.zeros(ngen)
        self.pv_EFD_3 = np.zeros(ngen)
        self.pd_EFD = np.zeros(ngen)
        self.nx_EFD = np.zeros(ngen)

        # SEXS
        self.pv_v1_1 = np.zeros(ngen)
        self.pv_v1_2 = np.zeros(ngen)
        self.pv_v1_3 = np.zeros(ngen)
        self.nx_v1 = np.zeros(ngen)

        # GOV
        self.pv_pm_1 = np.zeros(ngen)
        self.pv_pm_2 = np.zeros(ngen)
        self.pv_pm_3 = np.zeros(ngen)
        self.nx_pm = np.zeros(ngen)

        # TGOV1
        self.pv_p1_1 = np.zeros(ngen)
        self.pv_p1_2 = np.zeros(ngen)
        self.pv_p1_3 = np.zeros(ngen)
        self.nx_p1 = np.zeros(ngen)

        self.pv_p2_1 = np.zeros(ngen)
        self.pv_p2_2 = np.zeros(ngen)
        self.pv_p2_3 = np.zeros(ngen)
        self.nx_p2 = np.zeros(ngen)

        # HYGOV
        self.pv_xe_1 = np.zeros(ngen)
        self.pv_xe_2 = np.zeros(ngen)
        self.pv_xe_3 = np.zeros(ngen)

        self.pv_xc_1 = np.zeros(ngen)
        self.pv_xc_2 = np.zeros(ngen)
        self.pv_xc_3 = np.zeros(ngen)

        self.pv_xg_1 = np.zeros(ngen)
        self.pv_xg_2 = np.zeros(ngen)
        self.pv_xg_3 = np.zeros(ngen)

        self.pv_xq_1 = np.zeros(ngen)
        self.pv_xq_2 = np.zeros(ngen)
        self.pv_xq_3 = np.zeros(ngen)

        # GAST
        self.pv_p1_1 = np.zeros(ngen)
        self.pv_p1_2 = np.zeros(ngen)
        self.pv_p1_3 = np.zeros(ngen)

        self.pv_p2_1 = np.zeros(ngen)
        self.pv_p2_2 = np.zeros(ngen)
        self.pv_p2_3 = np.zeros(ngen)

        self.pv_p3_1 = np.zeros(ngen)
        self.pv_p3_2 = np.zeros(ngen)
        self.pv_p3_3 = np.zeros(ngen)

        # IEEEST
        self.pv_y1_1 = np.zeros(ngen)
        self.pv_y2_1 = np.zeros(ngen)
        self.pv_y3_1 = np.zeros(ngen)
        self.pv_y4_1 = np.zeros(ngen)
        self.pv_y5_1 = np.zeros(ngen)
        self.pv_y6_1 = np.zeros(ngen)
        self.pv_y7_1 = np.zeros(ngen)
        self.pv_x1_1 = np.zeros(ngen)
        self.pv_x2_1 = np.zeros(ngen)
        self.pv_vs_1 = np.zeros(ngen)

        return


# states class
class States_ibr():
    def __init__(self, nibr):
        # IBR
        self.nx_freq = np.zeros(nibr)

        # IBR - regca
        self.nx_regca_s0 = np.zeros(nibr)
        self.nx_regca_s1 = np.zeros(nibr)
        self.nx_regca_s2 = np.zeros(nibr)

        self.nx_regca_Vmp = np.zeros(nibr)
        self.nx_regca_Vap = np.zeros(nibr)
        self.nx_regca_i1 = np.zeros(nibr)
        self.nx_regca_i2 = np.zeros(nibr)
        self.nx_regca_ip2rr = np.zeros(nibr)

        # IBR - reecb
        self.nx_reecb_s0 = np.zeros(nibr)
        self.nx_reecb_s1 = np.zeros(nibr)
        self.nx_reecb_s2 = np.zeros(nibr)
        self.nx_reecb_s3 = np.zeros(nibr)
        self.nx_reecb_s4 = np.zeros(nibr)
        self.nx_reecb_s5 = np.zeros(nibr)

        self.nx_reecb_Ipcmd = np.zeros(nibr)
        self.nx_reecb_Iqcmd = np.zeros(nibr)
        self.nx_reecb_Pref = np.zeros(nibr)
        self.nx_reecb_Qext = np.zeros(nibr)
        self.nx_reecb_q2vPI = np.zeros(nibr)
        self.nx_reecb_v2iPI = np.zeros(nibr)

        # IBR - repca
        self.nx_repca_s0 = np.zeros(nibr)
        self.nx_repca_s1 = np.zeros(nibr)
        self.nx_repca_s2 = np.zeros(nibr)
        self.nx_repca_s3 = np.zeros(nibr)
        self.nx_repca_s4 = np.zeros(nibr)
        self.nx_repca_s5 = np.zeros(nibr)
        self.nx_repca_s6 = np.zeros(nibr)

        self.nx_repca_Vref = np.zeros(nibr)
        self.nx_repca_Qref = np.zeros(nibr)
        self.nx_repca_Freq_ref = np.zeros(nibr)
        self.nx_repca_Plant_pref = np.zeros(nibr)
        self.nx_repca_LineMW = np.zeros(nibr)
        self.nx_repca_LineMvar = np.zeros(nibr)
        self.nx_repca_LineMVA = np.zeros(nibr)
        self.nx_repca_QVdbout = np.zeros(nibr)
        self.nx_repca_fdbout = np.zeros(nibr)
        self.nx_repca_Pref_out = np.zeros(nibr)
        self.nx_repca_vq2qPI = np.zeros(nibr)
        self.nx_repca_p2pPI = np.zeros(nibr)

        # IBR - PLL
        self.nx_pll_ze = np.zeros(nibr)
        self.nx_pll_de = np.zeros(nibr)
        self.nx_pll_we = np.zeros(nibr)


# --------------------------------------------
# EMT initializaiton
class Initialize():
    def __init__(self, pfd, dyd):
        nbus = len(pfd.bus_num)
        ngen = len(pfd.gen_bus)
        nload = len(pfd.load_bus)

        self.Init_x = np.asarray([])
        self.Init_x_ibr = np.asarray([])
        self.Init_x_bus = np.asarray([])
        self.Init_x_load = np.asarray([])

        # network
        self.Init_net_VbaseA = np.asarray([])
        self.Init_net_ZbaseA = np.asarray([])
        self.Init_net_IbaseA = np.asarray([])
        self.Init_net_YbaseA = np.asarray([])

        self.Init_net_StA = np.asarray([])  # phasor value
        self.Init_net_Vt = np.asarray([])
        self.Init_net_It = np.asarray([])
        self.Init_net_Vtha = np.asarray([])

        self.Init_net_N = np.asarray([])
        self.Init_net_N1 = np.asarray([])
        # self.Init_gen_N = 0
        # self.Init_ibr_N = 0

        self.Init_net_G0 = np.asarray([])
        self.Init_net_coe0 = np.asarray([])
        self.Init_net_G0_inv = np.asarray([])
        self.Init_net_G0_data = []
        self.Init_net_G0_rows = []
        self.Init_net_G0_cols = []

        self.Init_net_Gt0 = np.asarray([])

        self.Init_net_V = np.asarray([])  # instantaneous value
        self.Init_brch_Ipre = np.asarray([])
        self.Init_brch_Ihis = np.asarray([])
        self.Init_node_Ihis = np.asarray([])

        # machine
        self.Init_mac_phy = np.zeros(ngen)
        self.Init_mac_IgA = np.zeros(ngen, dtype=complex)
        self.Init_mac_dt = np.zeros(ngen)
        self.Init_mac_ed = np.zeros(ngen)
        self.Init_mac_eq = np.zeros(ngen)
        self.Init_mac_id = np.zeros(ngen)
        self.Init_mac_iq = np.zeros(ngen)

        self.Init_mac_i1d = np.zeros(ngen)
        self.Init_mac_i1q = np.zeros(ngen)
        self.Init_mac_i2q = np.zeros(ngen)
        self.Init_mac_psyd = np.zeros(ngen)
        self.Init_mac_psyq = np.zeros(ngen)
        self.Init_mac_ifd = np.zeros(ngen)
        self.Init_mac_psyfd = np.zeros(ngen)
        self.Init_mac_psy1d = np.zeros(ngen)
        self.Init_mac_psy1q = np.zeros(ngen)
        self.Init_mac_psy2q = np.zeros(ngen)
        self.Init_mac_te = np.zeros(ngen)
        self.Init_mac_qe = np.zeros(ngen)

        # machine excitation system
        self.Init_mac_v1 = np.zeros(dyd.exc_sexs_n)
        self.Init_mac_vref = np.zeros(dyd.exc_sexs_n)
        self.Init_mac_EFD = np.zeros(ngen)

        # machine governor system
        self.Init_mac_pref = np.zeros(ngen)
        self.Init_mac_pm = np.zeros(ngen)
        self.Init_mac_gref = np.zeros(ngen)

        self.Init_tgov1_p1 = np.zeros(dyd.gov_tgov1_n)
        self.Init_tgov1_p2 = np.zeros(dyd.gov_tgov1_n)
        self.Init_tgov1_gref = np.zeros(dyd.gov_tgov1_n)
        self.tgov1_2gen = np.zeros(dyd.gov_tgov1_n, dtype=int)

        self.Init_hygov_xe = np.zeros(dyd.gov_hygov_n)
        self.Init_hygov_xc = np.zeros(dyd.gov_hygov_n)
        self.Init_hygov_xg = np.zeros(dyd.gov_hygov_n)
        self.Init_hygov_xq = np.zeros(dyd.gov_hygov_n)
        self.Init_hygov_gref = np.zeros(dyd.gov_hygov_n)
        self.hygov_2gen = np.zeros(dyd.gov_hygov_n, dtype=int)

        self.Init_gast_p1 = np.zeros(dyd.gov_gast_n)
        self.Init_gast_p2 = np.zeros(dyd.gov_gast_n)
        self.Init_gast_p3 = np.zeros(dyd.gov_gast_n)
        self.Init_gast_gref = np.zeros(dyd.gov_gast_n)
        self.gast_2gen = np.zeros(dyd.gov_gast_n, dtype=int)

        # pss
        self.Init_ieeest_y1 = np.zeros(dyd.pss_ieeest_n)
        self.Init_ieeest_y2 = np.zeros(dyd.pss_ieeest_n)
        self.Init_ieeest_y3 = np.zeros(dyd.pss_ieeest_n)
        self.Init_ieeest_y4 = np.zeros(dyd.pss_ieeest_n)
        self.Init_ieeest_y5 = np.zeros(dyd.pss_ieeest_n)
        self.Init_ieeest_y6 = np.zeros(dyd.pss_ieeest_n)
        self.Init_ieeest_y7 = np.zeros(dyd.pss_ieeest_n)
        self.Init_ieeest_x1 = np.zeros(dyd.pss_ieeest_n)
        self.Init_ieeest_x2 = np.zeros(dyd.pss_ieeest_n)
        self.Init_ieeest_vs = np.zeros(dyd.pss_n)

        # machine conductance
        self.Init_mac_Ld = np.asarray([])
        self.Init_mac_Lq = np.asarray([])
        self.Init_mac_Requiv = np.asarray([])
        self.Init_mac_Gequiv = np.asarray([])
        self.Init_mac_Rd = np.asarray([])
        self.Init_mac_Rq = np.asarray([])
        self.Init_mac_Rd1 = np.asarray([])
        self.Init_mac_Rd2 = np.asarray([])
        self.Init_mac_Rq1 = np.asarray([])
        self.Init_mac_Rq2 = np.asarray([])
        self.Init_mac_Rav = np.asarray([])
        self.Init_mac_alpha = np.asarray([])

        self.Init_mac_Rd1inv = np.asarray([])
        self.Init_mac_Rq1inv = np.asarray([])
        self.Init_mac_Rd_coe = np.asarray([])
        self.Init_mac_Rq_coe = np.asarray([])

        self.Init_mac_H = np.zeros(ngen)

        # IBR - REGCA
        self.Init_ibr_regca_s0 = np.zeros(dyd.ibr_n)
        self.Init_ibr_regca_s1 = np.zeros(dyd.ibr_n)
        self.Init_ibr_regca_s2 = np.zeros(dyd.ibr_n)

        self.Init_ibr_regca_Vmp = np.zeros(dyd.ibr_n)
        self.Init_ibr_regca_Vap = np.zeros(dyd.ibr_n)
        self.Init_ibr_regca_i1 = np.zeros(dyd.ibr_n)
        self.Init_ibr_regca_Qgen0 = np.zeros(dyd.ibr_n)
        self.Init_ibr_regca_i2 = np.zeros(dyd.ibr_n)
        self.Init_ibr_regca_ip2rr = np.zeros(dyd.ibr_n)

        # IBR - REECB
        self.Init_ibr_reecb_s0 = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_s1 = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_s2 = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_s3 = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_s4 = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_s5 = np.zeros(dyd.ibr_n)

        self.Init_ibr_reecb_Vref0 = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_pfaref = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_Ipcmd = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_Iqcmd = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_Pref = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_Qext = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_q2vPI = np.zeros(dyd.ibr_n)
        self.Init_ibr_reecb_v2iPI = np.zeros(dyd.ibr_n)

        # IBR - REPCA
        self.Init_ibr_repca_s0 = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_s1 = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_s2 = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_s3 = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_s4 = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_s5 = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_s6 = np.zeros(dyd.ibr_n)

        self.Init_ibr_repca_Vref = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_Qref = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_Freq_ref = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_Plant_pref = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_LineMW = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_LineMvar = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_LineMVA = np.zeros(dyd.ibr_n, dtype=complex)
        self.Init_ibr_repca_QVdbout = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_fdbout = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_Pref_out = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_vq2qPI = np.zeros(dyd.ibr_n)
        self.Init_ibr_repca_p2pPI = np.zeros(dyd.ibr_n)

        # IBR - PLL
        self.Init_ibr_pll_ze = np.zeros(dyd.ibr_n)
        self.Init_ibr_pll_de = np.zeros(dyd.ibr_n)
        self.Init_ibr_pll_we = np.zeros(dyd.ibr_n)

        # PLL for bus freq/ang
        self.Init_pll_ze = np.zeros(nbus)
        self.Init_pll_de = np.zeros(nbus)
        self.Init_pll_we = np.zeros(nbus)

        # volt mag measurement
        self.Init_vt = np.zeros(nbus)  # calculated volt mag
        self.Init_vtm = np.zeros(nbus)  # measured volt mag (after calc)
        self.Init_dvtm = np.zeros(nbus)  # measured dvm/dt

        # load
        self.Init_ZL_ang = np.zeros(nload)
        self.Init_ZL_mag = np.zeros(nload)
        self.Init_PL = np.zeros(nload)
        self.Init_QL = np.zeros(nload)

    def InitNet(self, pfd, ts, loadmodel_option):
        (self.Init_net_VbaseA,
         self.Init_net_ZbaseA,
         self.Init_net_IbaseA,
         self.Init_net_YbaseA,
         self.Init_net_StA,
         self.Init_net_Vt,
         self.Init_net_It,
         self.Init_net_N,
         self.Init_net_coe0,
         self.Init_net_V,
         self.Init_net_Vtha,
         self.Init_brch_Ipre,
         self.Init_node_Ihis,
         self.Init_brch_Ihis,
         self.Init_net_G0_rows,
         self.Init_net_G0_cols,
         self.Init_net_G0_data,
         ) = numba_InitNet(
            pfd.basemva,
            pfd.ws,
            pfd.bus_num,
            pfd.bus_basekV,
            pfd.bus_Vm,
            pfd.bus_Va,
            pfd.gen_bus,
            pfd.gen_MW,
            pfd.gen_Mvar,
            pfd.line_from,
            pfd.line_to,
            pfd.line_RX,
            pfd.line_chg,
            pfd.xfmr_from,
            pfd.xfmr_to,
            pfd.xfmr_RX,
            pfd.load_bus,
            pfd.load_MW,
            pfd.load_Mvar,
            pfd.shnt_bus,
            pfd.shnt_gb,
            pfd.shnt_sw_bus,
            pfd.shnt_sw_gb,
            ts,
            loadmodel_option,
        )
        return

    def InitMac(self, pfd, dyd):
        for i in range(len(pfd.gen_bus)):
            genbus = pfd.gen_bus[i]
            genbus_idx = np.where(pfd.bus_num == genbus)[0][0]

            S_temp = math.sqrt(pfd.gen_MW[i] * pfd.gen_MW[i] + pfd.gen_Mvar[i] * pfd.gen_Mvar[i])
            if np.abs(S_temp) > 1e-10:
                phy_temp = math.asin(pfd.gen_Mvar[i] / S_temp)
            else:
                phy_temp = 0.0
            IgA_temp = self.Init_net_It[i] * self.Init_net_IbaseA[genbus_idx] / (dyd.base_Is[i] / 1000.0)
            dt_temp = np.sign(pfd.gen_MW[i]) * math.atan((dyd.ec_Lq[i] * abs(IgA_temp) * math.cos(
                phy_temp) - dyd.ec_Ra[i] * abs(IgA_temp) * math.sin(phy_temp)) / (
                                                                 abs(self.Init_net_Vt[genbus_idx]) + dyd.ec_Ra[i] * abs(
                                                             IgA_temp) * math.cos(phy_temp) + dyd.ec_Lq[i] * abs(
                                                             IgA_temp) * math.sin(phy_temp)))
            dt0_temp = dt_temp + pfd.bus_Va[genbus_idx]

            ed_temp = abs(self.Init_net_Vt[genbus_idx]) * math.sin(dt_temp)
            eq_temp = abs(self.Init_net_Vt[genbus_idx]) * math.cos(dt_temp)
            id_temp = abs(IgA_temp) * math.sin(dt_temp + phy_temp)
            iq_temp = abs(IgA_temp) * math.cos(dt_temp + phy_temp)

            i1d_temp = 0.0
            i1q_temp = 0.0
            i2q_temp = 0.0
            psyd_temp = eq_temp + dyd.ec_Ra[i] * iq_temp
            psyq_temp = - (ed_temp + dyd.ec_Ra[i] * id_temp)
            ifd_temp = (eq_temp + dyd.ec_Ld[i] * id_temp + dyd.ec_Ra[i] * iq_temp) / dyd.ec_Lad[i]
            efd_temp = dyd.ec_Rfd[i] * ifd_temp
            psyfd_temp = dyd.ec_Lffd[i] * ifd_temp - dyd.ec_Lad[i] * id_temp
            psy1d_temp = dyd.ec_Lad[i] * (ifd_temp - id_temp)
            psy1q_temp = - dyd.ec_Laq[i] * iq_temp
            psy2q_temp = - dyd.ec_Laq[i] * iq_temp

            ## used for a while -------------------------------------
            # pref_temp = ed_temp * id_temp + eq_temp * iq_temp
            # qe_temp = eq_temp * id_temp - ed_temp * iq_temp
            ## ---------------------------------------------------
            pref_temp = psyd_temp * iq_temp - psyq_temp * id_temp
            qe_temp = psyd_temp * id_temp + psyq_temp * iq_temp

            self.Init_mac_phy[i] = phy_temp
            self.Init_mac_IgA[i] = IgA_temp
            self.Init_mac_dt[i] = dt0_temp
            self.Init_mac_ed[i] = ed_temp
            self.Init_mac_eq[i] = eq_temp
            self.Init_mac_id[i] = id_temp
            self.Init_mac_iq[i] = iq_temp
            self.Init_mac_i1d[i] = i1d_temp
            self.Init_mac_i1q[i] = i1q_temp
            self.Init_mac_i2q[i] = i2q_temp
            self.Init_mac_psyd[i] = psyd_temp
            self.Init_mac_psyq[i] = psyq_temp
            self.Init_mac_ifd[i] = ifd_temp
            self.Init_mac_psyfd[i] = psyfd_temp
            self.Init_mac_psy1d[i] = psy1d_temp
            self.Init_mac_psy1q[i] = psy1q_temp
            self.Init_mac_psy2q[i] = psy2q_temp
            # self.Init_mac_te[i] = pref_temp
            self.Init_mac_te[i] = ed_temp * id_temp + eq_temp * iq_temp
            self.Init_mac_qe[i] = qe_temp

            # Efd initialized for excitation system
            self.Init_mac_EFD[i] = efd_temp * dyd.ec_Lad[i] / dyd.ec_Rfd[i]

            # Pref initialized for governor system
            self.Init_mac_pref[i] = pref_temp

    def InitExc(self, pfd, dyd):
        for i in range(dyd.exc_sexs_n):
            genbus = pfd.gen_bus[i]
            genbus_idx = int(np.where(pfd.bus_num == genbus)[0])

            v1 = self.Init_mac_EFD[i] / dyd.exc_sexs_K[i]
            vref = v1 + pfd.bus_Vm[genbus_idx]

            self.Init_mac_v1[i] = v1
            self.Init_mac_vref[i] = vref

    def InitGov(self, pfd, dyd):
        # TGOV1
        for govi in range(dyd.gov_tgov1_n):
            genbus = dyd.gov_tgov1_bus[govi]
            idx = np.where(pfd.gen_bus == genbus)[0]
            if len(idx) > 1:
                tempid = dyd.gov_tgov1_id[govi]
                if len(tempid) == 1:
                    tempid = tempid + ' '  # PSSE gen ID always has two digits
                idx1 = np.where(pfd.gen_id[idx] == tempid)[0][0]
                idx = idx[idx1]
            self.tgov1_2gen[govi] = int(idx)

            self.Init_mac_pm[idx] = self.Init_mac_pref[idx]
            self.Init_mac_gref[idx] = self.Init_mac_pref[idx] * dyd.gov_tgov1_R[govi]
            self.Init_tgov1_p2[govi] = self.Init_mac_pref[idx]
            self.Init_tgov1_p1[govi] = self.Init_mac_pref[idx]
            self.Init_tgov1_gref[govi] = self.Init_mac_pref[idx] * dyd.gov_tgov1_R[govi]

        # HYGOV
        for govi in range(dyd.gov_hygov_n):
            genbus = dyd.gov_hygov_bus[govi]
            idx = np.where(pfd.gen_bus == genbus)[0]
            if len(idx) > 1:
                tempid = dyd.gov_hygov_id[govi]
                if len(tempid) == 1:
                    tempid = tempid + ' '  # PSSE gen ID always has two digits
                idx1 = np.where(pfd.gen_id[idx] == tempid)[0][0]
                idx = idx[idx1]
            self.hygov_2gen[govi] = int(idx)

            Tm0 = self.Init_mac_pref[idx]
            q0 = Tm0 / dyd.gov_hygov_At[govi] + dyd.gov_hygov_qNL[govi]
            c0 = q0
            g0 = c0
            nref = g0 * dyd.gov_hygov_R[govi]

            self.Init_hygov_xe[govi] = 0.0
            self.Init_hygov_xc[govi] = c0
            self.Init_hygov_xg[govi] = g0
            self.Init_hygov_xq[govi] = q0
            self.Init_hygov_gref[govi] = nref
            self.Init_mac_pm[idx] = Tm0
            self.Init_mac_gref[idx] = nref

        # GAST
        for govi in range(dyd.gov_gast_n):

            genbus = dyd.gov_gast_bus[govi]
            idx = np.where(pfd.gen_bus == genbus)[0]
            if len(idx) > 1:
                tempid = dyd.gov_gast_id[govi]
                if len(tempid) == 1:
                    tempid = tempid + ' '  # PSSE gen ID always has two digits
                idx1 = np.where(pfd.gen_id[idx] == tempid)[0][0]
                idx = idx[idx1]
            self.gast_2gen[govi] = int(idx)

            pref = self.Init_mac_pref[idx]

            self.Init_gast_p1[govi] = pref
            self.Init_gast_p2[govi] = pref
            self.Init_gast_p3[govi] = pref
            self.Init_gast_gref[govi] = pref
            self.Init_mac_pm[idx] = pref
            self.Init_mac_gref[idx] = pref

    def InitPss(self, pfd, dyd):
        for i in range(dyd.pss_ieeest_n):
            if dyd.pss_type[i] == 'IEEEST':
                self.Init_ieeest_y1[i] = 0.0
                self.Init_ieeest_y2[i] = 0.0
                self.Init_ieeest_y3[i] = 0.0
                self.Init_ieeest_y4[i] = 0.0
                self.Init_ieeest_y5[i] = 0.0
                self.Init_ieeest_y6[i] = 0.0
                self.Init_ieeest_y7[i] = 0.0
                self.Init_ieeest_x1[i] = 0.0
                self.Init_ieeest_x2[i] = 0.0
                self.Init_ieeest_vs[i] = 0.0

    def CheckMacEq(self, pfd, dyd):
        for i in range(len(pfd.gen_bus)):
            EFD2efd = dyd.ec_Rfd[i] / dyd.ec_Lad[i]
            eq = [0] * 12
            eq[0] = self.Init_mac_ed[i] + self.Init_mac_psyq[i] + dyd.ec_Ra[i] * self.Init_mac_id[i]
            eq[1] = self.Init_mac_eq[i] - self.Init_mac_psyd[i] + dyd.ec_Ra[i] * self.Init_mac_iq[i]
            eq[2] = self.Init_mac_EFD[i] * EFD2efd - dyd.ec_Rfd[i] * self.Init_mac_ifd[i]
            eq[3] = - dyd.ec_R1d[i] * self.Init_mac_i1d[i]
            eq[4] = - dyd.ec_R1q[i] * self.Init_mac_i1q[i]
            eq[5] = - dyd.ec_R2q[i] * self.Init_mac_i2q[i]
            eq[6] = - (dyd.ec_Lad[i] + dyd.ec_Ll[i]) * self.Init_mac_id[i] + dyd.ec_Lad[i] * self.Init_mac_ifd[i] + \
                    dyd.ec_Lad[i] * self.Init_mac_i1d[i] - self.Init_mac_psyd[i]
            eq[7] = - (dyd.ec_Laq[i] + dyd.ec_Ll[i]) * self.Init_mac_iq[i] + dyd.ec_Laq[i] * self.Init_mac_i1q[i] + \
                    dyd.ec_Laq[i] * self.Init_mac_i2q[i] - self.Init_mac_psyq[i]
            eq[8] = dyd.ec_Lffd[i] * self.Init_mac_ifd[i] + dyd.ec_Lf1d[i] * self.Init_mac_i1d[i] - \
                    dyd.ec_Lad[i] * self.Init_mac_id[i] - self.Init_mac_psyfd[i]
            eq[9] = dyd.ec_Lf1d[i] * self.Init_mac_ifd[i] + dyd.ec_L11d[i] * self.Init_mac_i1d[i] - \
                    dyd.ec_Lad[i] * self.Init_mac_id[i] - self.Init_mac_psy1d[i]
            eq[10] = dyd.ec_L11q[i] * self.Init_mac_i1q[i] + dyd.ec_Laq[i] * self.Init_mac_i2q[i] - \
                     dyd.ec_Laq[i] * self.Init_mac_iq[i] - self.Init_mac_psy1q[i]
            eq[11] = dyd.ec_Laq[i] * self.Init_mac_i1q[i] + dyd.ec_L22q[i] * self.Init_mac_i2q[i] - \
                     dyd.ec_Laq[i] * self.Init_mac_iq[i] - self.Init_mac_psy2q[i]

            sos = reduce(lambda i, j: i + j * j, [eq[:1][0] ** 2] + eq[1:])
            if sos > 1e-10:
                print('Issue in machine init!!!')
                print(eq)
            else:
                pass

    def InitREGCA(self, pfd, dyd):
        for i in range(len(pfd.ibr_bus)):
            ibrbus = pfd.ibr_bus[i]
            ibrbus_idx = np.where(pfd.bus_num == ibrbus)[0]

            P = pfd.ibr_MW[i] / dyd.ibr_MVAbase[i]
            Q = pfd.ibr_Mvar[i] / dyd.ibr_MVAbase[i]
            S = complex(P, Q)
            Vm = pfd.bus_Vm[ibrbus_idx]
            Va = pfd.bus_Va[ibrbus_idx]
            Vt = complex(Vm * math.cos(Va), Vm * math.sin(Va))

            It = np.conj(S / Vt)

            Ip_out = np.real(It) * math.cos(Va) + np.imag(It) * math.sin(Va)
            Iq_out = np.imag(It) * math.cos(Va) - np.real(It) * math.sin(Va)

            i1 = max(0.0, (Vm - dyd.ibr_regca_Volim[i]) * dyd.ibr_regca_Khv[i])
            Iq = Iq_out + i1

            if Vm > dyd.ibr_regca_Lvpnt1[i]:
                i2 = 1.0
            elif Vm < dyd.ibr_regca_Lvpnt0[i]:
                i2 = 0.0
                print('ERROR: Volt mag at bus ' + str(pfd.bus_num[ibrbus_idx] + ' too low to initialize IBR!!'))
                sys.exit(0)
            else:
                i2 = (Vm - dyd.ibr_regca_Lvpnt0[i]) / (dyd.ibr_regca_Lvpnt1[i] - dyd.ibr_regca_Lvpnt0[i])
            Ip = Ip_out / i2

            s0 = Ip
            s1 = - Iq
            s2 = Vm

            self.Init_ibr_regca_s0[i] = s0
            self.Init_ibr_regca_s1[i] = s1
            self.Init_ibr_regca_s2[i] = s2

            self.Init_ibr_regca_Vmp[i] = Vm
            self.Init_ibr_regca_Vap[i] = Va
            self.Init_ibr_regca_i1[i] = i1
            self.Init_ibr_regca_Qgen0[i] = Q
            self.Init_ibr_regca_i2[i] = i2
            self.Init_ibr_regca_ip2rr[i] = 0.0

    def InitREECB(self, pfd, dyd):
        for i in range(len(pfd.ibr_bus)):
            P = pfd.ibr_MW[i] / dyd.ibr_MVAbase[i]
            Q = pfd.ibr_Mvar[i] / dyd.ibr_MVAbase[i]

            Ipcmd = self.Init_ibr_regca_s0[i]
            Iqcmd = self.Init_ibr_regca_s1[i]
            Vm = self.Init_ibr_regca_s2[i]

            s0 = Vm
            s1 = P
            s4 = Q / Vm
            s5 = P

            if dyd.ibr_reecb_Vref0[i] == 0.0:
                Vref0 = Vm
            else:
                Vref0 = dyd.ibr_reecb_Vref0[i]

            self.Init_ibr_reecb_s0[i] = s0
            self.Init_ibr_reecb_s1[i] = s1
            self.Init_ibr_reecb_s2[i] = 0.0
            self.Init_ibr_reecb_s3[i] = 0.0
            self.Init_ibr_reecb_s4[i] = s4
            self.Init_ibr_reecb_s5[i] = s5

            self.Init_ibr_reecb_Vref0[i] = Vref0
            self.Init_ibr_reecb_pfaref[i] = math.atan(Q / P)
            self.Init_ibr_reecb_Ipcmd[i] = Ipcmd
            self.Init_ibr_reecb_Iqcmd[i] = Iqcmd
            self.Init_ibr_reecb_Pref[i] = Ipcmd * Vm
            self.Init_ibr_reecb_Qext[i] = Q
            self.Init_ibr_reecb_q2vPI[i] = 0.0
            self.Init_ibr_reecb_v2iPI[i] = 0.0

    def InitREPCA(self, pfd, dyd):
        for i in range(len(pfd.ibr_bus)):
            ibrbus = pfd.ibr_bus[i]
            ibrbus_idx = np.where(pfd.bus_num == ibrbus)

            P = pfd.ibr_MW[i] / dyd.ibr_MVAbase[i]
            Q = pfd.ibr_Mvar[i] / dyd.ibr_MVAbase[i]
            S = complex(P, Q)
            Vm = pfd.bus_Vm[ibrbus_idx]
            Va = pfd.bus_Va[ibrbus_idx]
            Vt = complex(Vm * math.cos(Va), Vm * math.sin(Va))
            It = np.conj(S / Vt)

            if abs(dyd.ibr_repca_branch_From_bus[i]) + abs(dyd.ibr_repca_branch_To_bus[i]) == 0:
                Pbranch = P
                Qbranch = Q
                Sbranch = S
                Ibranch = It
            else:
                pass  # need to get the complex P, Q, S and I on the indicated branch

            if dyd.ibr_repca_remote_bus[i] == 0:
                Vreg = Vt
            else:
                remote_bus_idx = np.where(pfd.bus_num == dyd.ibr_repca_remote_bus[i])
                Vm_rem = pfd.bus_Vm[remote_bus_idx]
                Va_rem = pfd.bus_Va[remote_bus_idx]
                Vreg = complex(Vm_rem * math.cos(Va_rem), Vm_rem * math.sin(Va_rem))

            V1_in1 = np.abs(Vreg + complex(dyd.ibr_repca_Rc[i], dyd.ibr_repca_Xc[i]) * Ibranch)
            V1_in0 = Qbranch * dyd.ibr_repca_Kc[i] + Vm

            if dyd.ibr_repca_VCFlag[i] == 0:
                V1 = V1_in0
            else:
                V1 = V1_in1

            s0 = V1
            s1 = Qbranch

            if dyd.ibr_repca_FFlag[i] == 0:
                self.Init_ibr_repca_Pref_out = np.append(self.Init_ibr_repca_Pref_out, self.Init_ibr_reecb_Pref[i])
                s4 = 0.0
                s5 = 0.0
                s6 = 0.0
            else:
                s4 = Pbranch
                s5 = self.Init_ibr_reecb_Pref[i]
                s6 = self.Init_ibr_reecb_Pref[i]

            s2 = self.Init_ibr_reecb_Qext[i]
            s3 = self.Init_ibr_reecb_Qext[i]

            self.Init_ibr_repca_s0[i] = s0
            self.Init_ibr_repca_s1[i] = s1
            self.Init_ibr_repca_s2[i] = s2
            self.Init_ibr_repca_s3[i] = s3
            self.Init_ibr_repca_s4[i] = s4
            self.Init_ibr_repca_s5[i] = s5
            self.Init_ibr_repca_s6[i] = s6

            self.Init_ibr_repca_Vref[i] = s0
            self.Init_ibr_repca_Qref[i] = s1
            self.Init_ibr_repca_Freq_ref[i] = 1.0
            self.Init_ibr_repca_Plant_pref[i] = Pbranch
            self.Init_ibr_repca_LineMW[i] = Pbranch
            self.Init_ibr_repca_LineMvar[i] = Qbranch
            self.Init_ibr_repca_LineMVA[i] = Sbranch
            self.Init_ibr_repca_QVdbout[i] = 0.0
            self.Init_ibr_repca_fdbout[i] = 0.0
            self.Init_ibr_repca_vq2qPI[i] = 0.0
            self.Init_ibr_repca_p2pPI[i] = 0.0

    def InitPLL(self, pfd):
        for i in range(len(pfd.ibr_bus)):
            ibrbus = pfd.ibr_bus[i]
            ibrbus_idx = np.where(pfd.bus_num == ibrbus)

            self.Init_ibr_pll_ze[i] = 0.0
            self.Init_ibr_pll_de[i] = pfd.bus_Va[ibrbus_idx]
            self.Init_ibr_pll_we[i] = 1.0

    def InitBusMea(self, pfd):
        self.Init_pll_ze = np.zeros(len(pfd.bus_num))
        self.Init_pll_de = pfd.bus_Va
        self.Init_pll_we = np.ones(len(pfd.bus_num))

        self.Init_vt = pfd.bus_Vm  # calculated volt mag
        self.Init_vtm = pfd.bus_Vm  # measured volt mag (after calc)
        self.Init_dvtm = pfd.bus_Vm * 0  # measured dvm/dt

    def InitLoad(self, pfd):
        for i in range(len(pfd.load_bus)):
            busi_idx = np.where(pfd.bus_num == pfd.load_bus[i])[0][0]
            self.Init_PL[i] = pfd.load_MW[i] / pfd.basemva
            self.Init_QL[i] = pfd.load_Mvar[i] / pfd.basemva
            self.Init_ZL_mag[i] = pfd.bus_Vm[busi_idx] * pfd.bus_Vm[busi_idx] / np.sqrt(
                pfd.load_MW[i] * pfd.load_MW[i] + pfd.load_Mvar[i] * pfd.load_Mvar[i]) * pfd.basemva
            if pfd.load_MW[i] > 0:
                self.Init_ZL_ang[i] = np.arctan(pfd.load_Mvar[i] / pfd.load_MW[i])
            else:
                self.Init_ZL_ang[i] = np.arctan(pfd.load_Mvar[i] / pfd.load_MW[i]) + np.pi

    def MergeMacG(self, pfd, dyd, ts, i_gentrip=[], mode='inv', nparts=4):
        self.Init_net_Gt0 = sp.coo_matrix((self.Init_net_G0_data, (self.Init_net_G0_rows, self.Init_net_G0_cols)),
                                          shape=(self.Init_net_N, self.Init_net_N)
                                          ).tolil()

        self.Init_mac_Ld = np.zeros((len(pfd.gen_bus), 3, 3))
        self.Init_mac_Lq = np.zeros((len(pfd.gen_bus), 3, 3))
        self.Init_mac_Requiv = np.zeros((len(pfd.gen_bus), 3, 3))
        self.Init_mac_Gequiv = np.zeros((len(pfd.gen_bus), 3, 3))
        self.Init_mac_Rd = np.zeros(len(pfd.gen_bus))
        self.Init_mac_Rq = np.zeros(len(pfd.gen_bus))
        self.Init_mac_Rd1 = np.zeros((len(pfd.gen_bus), 3, 3))
        self.Init_mac_Rd2 = np.zeros((len(pfd.gen_bus), 3, 3))
        self.Init_mac_Rq1 = np.zeros((len(pfd.gen_bus), 3, 3))
        self.Init_mac_Rq2 = np.zeros((len(pfd.gen_bus), 3, 3))
        self.Init_mac_Rav = np.zeros(len(pfd.gen_bus))
        self.Init_mac_alpha = np.zeros(len(pfd.gen_bus))

        self.Init_mac_Rd1inv = np.zeros((len(pfd.gen_bus), 2, 2))
        self.Init_mac_Rd_coe = np.zeros((len(pfd.gen_bus), 2))
        self.Init_mac_Rq1inv = np.zeros((len(pfd.gen_bus), 2, 2))
        self.Init_mac_Rd_coe = np.zeros((len(pfd.gen_bus), 2))

        for i in range(len(pfd.gen_bus)):
            self.Init_mac_alpha[i] = 99.0 / 101.0
            Ra = dyd.ec_Ra[i]
            L0 = dyd.ec_L0[i]

            self.Init_mac_Ld[i][0][0] = dyd.ec_Lad[i] + dyd.ec_Ll[i]
            self.Init_mac_Ld[i][0][1] = dyd.ec_Lad[i]
            self.Init_mac_Ld[i][0][2] = dyd.ec_Lad[i]
            self.Init_mac_Ld[i][1][0] = dyd.ec_Lad[i]
            self.Init_mac_Ld[i][1][1] = dyd.ec_Lffd[i]
            self.Init_mac_Ld[i][1][2] = dyd.ec_Lf1d[i]
            self.Init_mac_Ld[i][2][0] = dyd.ec_Lad[i]
            self.Init_mac_Ld[i][2][1] = dyd.ec_Lf1d[i]
            self.Init_mac_Ld[i][2][2] = dyd.ec_L11d[i]

            self.Init_mac_Lq[i][0][0] = dyd.ec_Laq[i] + dyd.ec_Ll[i]
            self.Init_mac_Lq[i][0][1] = dyd.ec_Laq[i]
            self.Init_mac_Lq[i][0][2] = dyd.ec_Laq[i]
            self.Init_mac_Lq[i][1][0] = dyd.ec_Laq[i]
            self.Init_mac_Lq[i][1][1] = dyd.ec_L11q[i]
            self.Init_mac_Lq[i][1][2] = dyd.ec_Laq[i]
            self.Init_mac_Lq[i][2][0] = dyd.ec_Laq[i]
            self.Init_mac_Lq[i][2][1] = dyd.ec_Laq[i]
            self.Init_mac_Lq[i][2][2] = dyd.ec_L22q[i]

            # previously finalized
            self.Init_mac_Rd1[i][0][0] = dyd.ec_Ra[i] + (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * \
                                         self.Init_mac_Ld[i][0][0]
            self.Init_mac_Rd1[i][0][1] = 0.0 + (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * self.Init_mac_Ld[i][0][1]
            self.Init_mac_Rd1[i][0][2] = 0.0 + (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * self.Init_mac_Ld[i][0][2]
            self.Init_mac_Rd1[i][1][0] = 0.0 + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][1][0]
            self.Init_mac_Rd1[i][1][1] = dyd.ec_Rfd[i] + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][1][1]
            self.Init_mac_Rd1[i][1][2] = 0.0 + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][1][2]
            self.Init_mac_Rd1[i][2][0] = 0.0 + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][2][0]
            self.Init_mac_Rd1[i][2][1] = 0.0 + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][2][1]
            self.Init_mac_Rd1[i][2][2] = dyd.ec_R1d[i] + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][2][2]

            self.Init_mac_Rd2[i][0][0] = dyd.ec_Ra[i] * self.Init_mac_alpha[i] - (1 + self.Init_mac_alpha[i]) / (
                        ts * pfd.ws) * \
                                         self.Init_mac_Ld[i][0][0]
            self.Init_mac_Rd2[i][0][1] = 0.0 - (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * self.Init_mac_Ld[i][0][1]
            self.Init_mac_Rd2[i][0][2] = 0.0 - (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * self.Init_mac_Ld[i][0][2]
            self.Init_mac_Rd2[i][1][0] = 0.0 - (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][1][0]
            self.Init_mac_Rd2[i][1][1] = dyd.ec_Rfd[i] * self.Init_mac_alpha[i] - (1 + self.Init_mac_alpha[i]) / ts * \
                                         self.Init_mac_Ld[i][1][1]
            self.Init_mac_Rd2[i][1][2] = 0.0 - (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][1][2]
            self.Init_mac_Rd2[i][2][0] = 0.0 - (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][2][0]
            self.Init_mac_Rd2[i][2][1] = 0.0 - (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][2][1]
            self.Init_mac_Rd2[i][2][1] = 0.0 - (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Ld[i][2][1]
            self.Init_mac_Rd2[i][2][2] = dyd.ec_R1d[i] * self.Init_mac_alpha[i] - (1 + self.Init_mac_alpha[i]) / ts * \
                                         self.Init_mac_Ld[i][2][2]

            self.Init_mac_Rq1[i][0][0] = dyd.ec_Ra[i] + (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * \
                                         self.Init_mac_Lq[i][0][0]
            self.Init_mac_Rq1[i][0][1] = 0.0 + (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * self.Init_mac_Lq[i][0][1]
            self.Init_mac_Rq1[i][0][2] = 0.0 + (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * self.Init_mac_Lq[i][0][2]
            self.Init_mac_Rq1[i][1][0] = 0.0 + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][1][0]
            self.Init_mac_Rq1[i][1][1] = dyd.ec_R1q[i] + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][1][1]
            self.Init_mac_Rq1[i][1][2] = 0.0 + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][1][2]
            self.Init_mac_Rq1[i][2][0] = 0.0 + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][2][0]
            self.Init_mac_Rq1[i][2][1] = 0.0 + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][2][1]
            self.Init_mac_Rq1[i][2][2] = dyd.ec_R2q[i] + (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][2][2]

            self.Init_mac_Rq2[i][0][0] = dyd.ec_Ra[i] * self.Init_mac_alpha[i] - (1 + self.Init_mac_alpha[i]) / (
                        ts * pfd.ws) * \
                                         self.Init_mac_Lq[i][0][0]
            self.Init_mac_Rq2[i][0][1] = 0.0 - (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * self.Init_mac_Lq[i][0][1]
            self.Init_mac_Rq2[i][0][2] = 0.0 - (1 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * self.Init_mac_Lq[i][0][2]
            self.Init_mac_Rq2[i][1][0] = 0.0 - (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][1][0]
            self.Init_mac_Rq2[i][1][1] = dyd.ec_R1q[i] * self.Init_mac_alpha[i] - (1 + self.Init_mac_alpha[i]) / ts * \
                                         self.Init_mac_Lq[i][1][1]
            self.Init_mac_Rq2[i][1][2] = 0.0 - (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][1][2]
            self.Init_mac_Rq2[i][2][0] = 0.0 - (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][2][0]
            self.Init_mac_Rq2[i][2][1] = 0.0 - (1 + self.Init_mac_alpha[i]) / ts * self.Init_mac_Lq[i][2][1]
            self.Init_mac_Rq2[i][2][2] = dyd.ec_R2q[i] * self.Init_mac_alpha[i] - (1 + self.Init_mac_alpha[i]) / ts * \
                                         self.Init_mac_Lq[i][2][2]
            temp_det = self.Init_mac_Rd1[i][1][1] * self.Init_mac_Rd1[i][2][2] - self.Init_mac_Rd1[i][1][2] * \
                       self.Init_mac_Rd1[i][2][1]
            Rd1inv = [[self.Init_mac_Rd1[i][2][2] / temp_det, - self.Init_mac_Rd1[i][1][2] / temp_det],
                      [- self.Init_mac_Rd1[i][2][1] / temp_det, self.Init_mac_Rd1[i][1][1] / temp_det]]
            templ = [self.Init_mac_Rd1[i][0][1] * Rd1inv[0][0] + self.Init_mac_Rd1[i][0][2] * Rd1inv[1][0],
                     self.Init_mac_Rd1[i][0][1] * Rd1inv[0][1] + self.Init_mac_Rd1[i][0][2] * Rd1inv[1][1]]
            self.Init_mac_Rd1inv[i] = np.asarray(Rd1inv)
            self.Init_mac_Rd[i] = self.Init_mac_Rd1[i][0][0] - (
                    templ[0] * self.Init_mac_Rd1[i][1][0] + templ[1] * self.Init_mac_Rd1[i][2][0])
            self.Init_mac_Rd_coe[i] = np.asarray(templ)

            temp_det = self.Init_mac_Rq1[i][1][1] * self.Init_mac_Rq1[i][2][2] - self.Init_mac_Rq1[i][1][2] * \
                       self.Init_mac_Rq1[i][2][1]
            Rq1inv = [[self.Init_mac_Rq1[i][2][2] / temp_det, - self.Init_mac_Rq1[i][1][2] / temp_det],
                      [- self.Init_mac_Rq1[i][2][1] / temp_det, self.Init_mac_Rq1[i][1][1] / temp_det]]
            templ = [self.Init_mac_Rq1[i][0][1] * Rq1inv[0][0] + self.Init_mac_Rq1[i][0][2] * Rq1inv[1][0],
                     self.Init_mac_Rq1[i][0][1] * Rq1inv[0][1] + self.Init_mac_Rq1[i][0][2] * Rq1inv[1][1]]
            self.Init_mac_Rq1inv[i] = np.asarray(Rq1inv)

            self.Init_mac_Rq[i] = self.Init_mac_Rq1[i][0][0] - (
                    templ[0] * self.Init_mac_Rq1[i][1][0] + templ[1] * self.Init_mac_Rq1[i][2][0])
            if self.Init_mac_Rq_coe.size == 0:
                self.Init_mac_Rq_coe = np.asarray(templ)
            else:
                self.Init_mac_Rq_coe = np.vstack((self.Init_mac_Rq_coe, np.asarray(templ)))

            self.Init_mac_Rav[i] = (self.Init_mac_Rd[i] + self.Init_mac_Rq[i]) / 2.0
            R0 = Ra + (1.0 + self.Init_mac_alpha[i]) / (ts * pfd.ws) * L0

            Rs = (R0 + 2.0 * self.Init_mac_Rav[i]) / 3.0
            Rm = (R0 - self.Init_mac_Rav[i]) / 3.0

            self.Init_mac_Requiv[i][0][0] = Rs
            self.Init_mac_Requiv[i][0][1] = Rm
            self.Init_mac_Requiv[i][0][2] = Rm
            self.Init_mac_Requiv[i][1][0] = Rm
            self.Init_mac_Requiv[i][1][1] = Rs
            self.Init_mac_Requiv[i][1][2] = Rm
            self.Init_mac_Requiv[i][2][0] = Rm
            self.Init_mac_Requiv[i][2][1] = Rm
            self.Init_mac_Requiv[i][2][2] = Rs

            tempA = np.asarray([[Rs, Rm, Rm], [Rm, Rs, Rm], [Rm, Rm, Rs]])
            tempAinv = np.linalg.inv(tempA)

            genbus_idx = int(np.where(pfd.bus_num == pfd.gen_bus[i])[0])
            self.Init_mac_Gequiv[i][0][0] = tempAinv[0][0] / dyd.base_Zs[i] * self.Init_net_ZbaseA[genbus_idx]
            self.Init_mac_Gequiv[i][0][1] = tempAinv[0][1] / dyd.base_Zs[i] * self.Init_net_ZbaseA[genbus_idx]
            self.Init_mac_Gequiv[i][0][2] = tempAinv[0][2] / dyd.base_Zs[i] * self.Init_net_ZbaseA[genbus_idx]
            self.Init_mac_Gequiv[i][1][0] = tempAinv[1][0] / dyd.base_Zs[i] * self.Init_net_ZbaseA[genbus_idx]
            self.Init_mac_Gequiv[i][1][1] = tempAinv[1][1] / dyd.base_Zs[i] * self.Init_net_ZbaseA[genbus_idx]
            self.Init_mac_Gequiv[i][1][2] = tempAinv[1][2] / dyd.base_Zs[i] * self.Init_net_ZbaseA[genbus_idx]
            self.Init_mac_Gequiv[i][2][0] = tempAinv[2][0] / dyd.base_Zs[i] * self.Init_net_ZbaseA[genbus_idx]
            self.Init_mac_Gequiv[i][2][1] = tempAinv[2][1] / dyd.base_Zs[i] * self.Init_net_ZbaseA[genbus_idx]
            self.Init_mac_Gequiv[i][2][2] = tempAinv[2][2] / dyd.base_Zs[i] * self.Init_net_ZbaseA[genbus_idx]

            N1 = len(pfd.bus_num)
            N2 = len(pfd.bus_num) * 2
            if i_gentrip:
                if i_gentrip != i:
                    self.addtoG0(genbus_idx, genbus_idx, self.Init_mac_Gequiv[i][0][0])
                    self.addtoG0(genbus_idx, genbus_idx + N1, self.Init_mac_Gequiv[i][0][1])
                    self.addtoG0(genbus_idx, genbus_idx + N2, self.Init_mac_Gequiv[i][0][2])
                    self.addtoG0(genbus_idx + N1, genbus_idx, self.Init_mac_Gequiv[i][1][0])
                    self.addtoG0(genbus_idx + N1, genbus_idx + N1, self.Init_mac_Gequiv[i][1][1])
                    self.addtoG0(genbus_idx + N1, genbus_idx + N2, self.Init_mac_Gequiv[i][1][2])
                    self.addtoG0(genbus_idx + N2, genbus_idx, self.Init_mac_Gequiv[i][2][0])
                    self.addtoG0(genbus_idx + N2, genbus_idx + N1, self.Init_mac_Gequiv[i][2][1])
                    self.addtoG0(genbus_idx + N2, genbus_idx + N2, self.Init_mac_Gequiv[i][2][2])
            else:
                self.addtoG0(genbus_idx, genbus_idx, self.Init_mac_Gequiv[i][0][0])
                self.addtoG0(genbus_idx, genbus_idx + N1, self.Init_mac_Gequiv[i][0][1])
                self.addtoG0(genbus_idx, genbus_idx + N2, self.Init_mac_Gequiv[i][0][2])
                self.addtoG0(genbus_idx + N1, genbus_idx, self.Init_mac_Gequiv[i][1][0])
                self.addtoG0(genbus_idx + N1, genbus_idx + N1, self.Init_mac_Gequiv[i][1][1])
                self.addtoG0(genbus_idx + N1, genbus_idx + N2, self.Init_mac_Gequiv[i][1][2])
                self.addtoG0(genbus_idx + N2, genbus_idx, self.Init_mac_Gequiv[i][2][0])
                self.addtoG0(genbus_idx + N2, genbus_idx + N1, self.Init_mac_Gequiv[i][2][1])
                self.addtoG0(genbus_idx + N2, genbus_idx + N2, self.Init_mac_Gequiv[i][2][2])

        self.Init_net_G0 = sp.coo_matrix((self.Init_net_G0_data, (self.Init_net_G0_rows, self.Init_net_G0_cols)),
                                         shape=(self.Init_net_N, self.Init_net_N)
                                         ).tolil()

        if mode == 'inv':
            self.Init_net_G0_inv = la.inv(self.Init_net_G0.tocsc())
        elif mode == 'lu':
            self.Init_net_G0_lu = la.splu(self.Init_net_G0.tocsc())
        elif mode == 'bbd':
            (BBD, idx_order, inv_order) = form_bbd(self, nparts)
            self.index_order = idx_order
            self.inv_order = inv_order
            self.Init_net_G0_bbd_lu = schur_bbd_lu(BBD)
        else:
            raise ValueError('Unrecognized mode: {}'.format(mode))
        self.admittance_mode = mode

        return

    def addtoG0(self, row, col, addedvalue):
        found_flag = 0
        for i in range(len(self.Init_net_G0_data)):
            if (self.Init_net_G0_rows[i] == row) & (self.Init_net_G0_cols[i] == col):
                found_flag = 1
                self.Init_net_G0_data[i] += addedvalue
                return

        if found_flag == 0:
            self.Init_net_G0_data = np.append(self.Init_net_G0_data, addedvalue)
            self.Init_net_G0_rows = np.append(self.Init_net_G0_rows, row)
            self.Init_net_G0_cols = np.append(self.Init_net_G0_cols, col)

    def CombineX(self, pfd, dyd):
        xi = 0
        # machine states
        # GENROU
        dyd.gen_genrou_xi_st = xi
        dyd.gen_genrou_odr = 18
        for i in range(len(pfd.gen_bus)):
            self.Init_x = np.append(self.Init_x, self.Init_mac_dt[i])  # 1
            self.Init_x = np.append(self.Init_x, 1.0 * pfd.ws)  # 2
            self.Init_x = np.append(self.Init_x, self.Init_mac_id[i])  # 3
            self.Init_x = np.append(self.Init_x, self.Init_mac_iq[i])  # 4
            self.Init_x = np.append(self.Init_x, self.Init_mac_ifd[i])  # 5
            self.Init_x = np.append(self.Init_x, self.Init_mac_i1d[i])  # 6
            self.Init_x = np.append(self.Init_x, self.Init_mac_i1q[i])  # 7
            self.Init_x = np.append(self.Init_x, self.Init_mac_i2q[i])  # 8
            self.Init_x = np.append(self.Init_x, self.Init_mac_ed[i])  # 9
            self.Init_x = np.append(self.Init_x, self.Init_mac_eq[i])  # 10
            self.Init_x = np.append(self.Init_x, self.Init_mac_psyd[i])  # 11
            self.Init_x = np.append(self.Init_x, self.Init_mac_psyq[i])  # 12
            self.Init_x = np.append(self.Init_x, self.Init_mac_psyfd[i])  # 13
            self.Init_x = np.append(self.Init_x, self.Init_mac_psy1q[i])  # 14
            self.Init_x = np.append(self.Init_x, self.Init_mac_psy1d[i])  # 15
            self.Init_x = np.append(self.Init_x, self.Init_mac_psy2q[i])  # 16
            self.Init_x = np.append(self.Init_x, self.Init_mac_te[i])  # 17
            self.Init_x = np.append(self.Init_x, self.Init_mac_qe[i])  # 18

            xi = xi + dyd.gen_genrou_odr

        # SEXS exciter model
        dyd.exc_sexs_xi_st = xi
        dyd.exc_sexs_odr = 2
        for i in range(dyd.exc_sexs_n):
            self.Init_x = np.append(self.Init_x, self.Init_mac_v1[i])  # 1
            self.Init_x = np.append(self.Init_x, self.Init_mac_EFD[i])  # 2

            xi = xi + dyd.exc_sexs_odr

        # TGOV1 governor model
        dyd.gov_tgov1_xi_st = xi
        dyd.gov_tgov1_odr = 3
        for i in range(dyd.gov_tgov1_n):
            self.Init_x = np.append(self.Init_x, self.Init_tgov1_p1[i])  # 1
            self.Init_x = np.append(self.Init_x, self.Init_tgov1_p2[i])  # 2

            self.Init_x = np.append(self.Init_x, self.Init_mac_pm[int(dyd.gov_tgov1_idx[i])])  # 3

            xi = xi + dyd.gov_tgov1_odr

        # HYGOV governor model
        dyd.gov_hygov_xi_st = xi
        dyd.gov_hygov_odr = 5
        for i in range(dyd.gov_hygov_n):
            self.Init_x = np.append(self.Init_x, self.Init_hygov_xe[i])  # 1
            self.Init_x = np.append(self.Init_x, self.Init_hygov_xc[i])  # 2
            self.Init_x = np.append(self.Init_x, self.Init_hygov_xg[i])  # 3
            self.Init_x = np.append(self.Init_x, self.Init_hygov_xq[i])  # 4

            self.Init_x = np.append(self.Init_x, self.Init_mac_pm[int(dyd.gov_hygov_idx[i])])  # 5

            xi = xi + dyd.gov_hygov_odr

        # GAST governor model
        dyd.gov_gast_xi_st = xi
        dyd.gov_gast_odr = 4
        for i in range(dyd.gov_gast_n):
            self.Init_x = np.append(self.Init_x, self.Init_gast_p1[i])  # 1
            self.Init_x = np.append(self.Init_x, self.Init_gast_p2[i])  # 2
            self.Init_x = np.append(self.Init_x, self.Init_gast_p3[i])  # 3

            self.Init_x = np.append(self.Init_x, self.Init_mac_pm[int(dyd.gov_gast_idx[i])])  # 4

            xi = xi + dyd.gov_gast_odr

        # IEEEST
        dyd.pss_ieeest_xi_st = xi
        dyd.pss_ieeest_odr = 10
        for i in range(dyd.pss_ieeest_n):
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_y1[i])  # 1
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_y2[i])  # 2
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_y3[i])  # 3
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_y4[i])  # 4
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_y5[i])  # 5
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_y6[i])  # 6
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_y7[i])  # 7
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_x1[i])  # 8
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_x2[i])  # 9
            self.Init_x = np.append(self.Init_x, self.Init_ieeest_vs[i])  # 10

            xi = xi + dyd.pss_ieeest_odr

        dyd.ibr_odr = 41
        for i in range(len(pfd.ibr_bus)):
            # regca
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_regca_s0[i])  # 1
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_regca_s1[i])  # 2
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_regca_s2[i])  # 3
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_regca_Vmp[i])  # 4
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_regca_Vap[i])  # 5
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_regca_i1[i])  # 6
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_regca_i2[i])  # 7
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_regca_ip2rr[i])  # 8

            # reecb
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_s0[i])  # 9
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_s1[i])  # 10
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_s2[i])  # 11
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_s3[i])  # 12
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_s4[i])  # 13
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_s5[i])  # 14
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_Ipcmd[i])  # 15
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_Iqcmd[i])  # 16
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_Pref[i])  # 17
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_Qext[i])  # 18
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_q2vPI[i])  # 19
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_reecb_v2iPI[i])  # 20

            # repca
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_s0[i])  # 21
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_s1[i])  # 22
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_s2[i])  # 23
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_s3[i])  # 24
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_s4[i])  # 25
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_s5[i])  # 26
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_s6[i])  # 27
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_Vref[i])  # 28
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_Qref[i])  # 29
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_Freq_ref[i])  # 30
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_Plant_pref[i])  # 31
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_LineMW[i])  # 32
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_LineMvar[i])  # 33
            self.Init_x_ibr = np.append(self.Init_x_ibr, np.abs(self.Init_ibr_repca_LineMVA[i]))  # 34
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_QVdbout[i])  # 35
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_fdbout[i])  # 36
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_vq2qPI[i])  # 37
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_p2pPI[i])  # 38
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_Freq_ref[i])  # 39 Vf
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_LineMW[i])  # 40 Pe
            self.Init_x_ibr = np.append(self.Init_x_ibr, self.Init_ibr_repca_LineMvar[i])  # 41 Qe

        # bus measurement
        dyd.bus_odr = 6
        for i in range(len(pfd.bus_num)):
            # volt freq and angle by PLL
            self.Init_x_bus = np.append(self.Init_x_bus, self.Init_pll_ze[i])  # 1 ze
            self.Init_x_bus = np.append(self.Init_x_bus, self.Init_pll_de[i])  # 2 de
            self.Init_x_bus = np.append(self.Init_x_bus, self.Init_pll_we[i])  # 3 we

            # volt mag measurement
            self.Init_x_bus = np.append(self.Init_x_bus, self.Init_vt[i])  # 4 vt
            self.Init_x_bus = np.append(self.Init_x_bus, self.Init_vtm[i])  # 5 vtm
            self.Init_x_bus = np.append(self.Init_x_bus, self.Init_dvtm[i])  # 6 dvtm

        # load
        dyd.load_odr = 4
        for i in range(len(pfd.load_bus)):
            # volt freq and angle by PLL
            self.Init_x_load = np.append(self.Init_x_load, self.Init_ZL_mag[i])  # 1 ZL_mag
            self.Init_x_load = np.append(self.Init_x_load, self.Init_ZL_ang[i])  # 2 ZL_ang
            self.Init_x_load = np.append(self.Init_x_load, self.Init_PL[i])  # 3 PL
            self.Init_x_load = np.append(self.Init_x_load, self.Init_QL[i])  # 4 QL
