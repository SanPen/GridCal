# --------------------------------------------
#  EMT solver library
#  2020-2024 Bin Wang, Min Xiong
#  Last modified: 8/15/24
# --------------------------------------------

import math
import numpy as np


# ---------------------------------------------
# power flow data class
class PFData():

    @staticmethod
    def load_from_json(storage):
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
        self.gen_status = np.asarray([])

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
        """

        :param psspy:
        """
        # system data
        self.basemva = psspy.sysmva()
        self.ws = 2 * math.pi * 60

        # bus data
        self.bus_num = np.asarray(psspy.abusint(-1, 2, 'NUMBER')[1][0])
        self.bus_type = np.asarray(psspy.abusint(-1, 2, 'TYPE')[1][0])

        self.bus_Vm = np.round(np.asarray(psspy.abusreal(-1, 2, 'PU')[1][0]) * 100000) / 100000
        self.bus_Va = np.round(np.asarray(psspy.abusreal(-1, 2, 'ANGLED')[1][0]) * 10000) / 10000 / 180 * np.pi

        self.bus_kV = np.asarray(psspy.abusreal(-1, 2, 'KV')[1][0])
        self.bus_basekV = np.asarray(psspy.abusreal(-1, 2, 'BASE')[1][0])
        self.bus_name = psspy.abuschar(-1, 1, 'NAME')[1][0]

        # load data
        self.load_id = psspy.aloadchar(-1, 1, 'ID')[1][0]
        self.load_bus = np.asarray(psspy.aloadint(-1, 1, 'NUMBER')[1][0])
        self.load_Z = np.asarray(psspy.aloadcplx(-1, 1, 'YLACT')[1][0])
        self.load_I = np.asarray(psspy.aloadcplx(-1, 1, 'ILACT')[1][0])
        self.load_P = np.asarray(psspy.aloadcplx(-1, 1, 'MVAACT')[1][0])

        self.load_MW = np.round((self.load_Z.real + self.load_I.real + self.load_P.real) * 10000) / 10000
        self.load_Mvar = np.round((self.load_Z.imag + self.load_I.imag + self.load_P.imag) * 10000) / 10000

        # generator data
        self.gen_id = psspy.amachchar(-1, 4, 'ID')[1][0]
        self.gen_bus = np.asarray(psspy.amachint(-1, 4, 'NUMBER')[1][0])
        self.gen_S = np.asarray(psspy.amachcplx(-1, 4, 'PQGEN')[1][0])
        self.gen_mod = np.asarray(psspy.amachint(-1, 4, 'WMOD')[1][0])

        self.gen_MW = np.round(self.gen_S.real * 1000) / 1000
        self.gen_Mvar = np.round(self.gen_S.imag * 1000) / 1000

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
        self.line_RX = np.round(np.asarray(psspy.abrncplx(-1, 1, 1, 1, 1, ['RX'])[1][0]) * 1000000) / 1000000
        self.line_chg = np.round(np.asarray(psspy.abrnreal(-1, 1, 1, 1, 1, ['CHARGING'])[1][0]) * 1000000) / 1000000

        # xfmr data
        self.xfmr_from = np.asarray(psspy.atrnint(-1, 1, 1, 1, 1, ['FROMNUMBER'])[1][0])
        self.xfmr_to = np.asarray(psspy.atrnint(-1, 1, 1, 1, 1, ['TONUMBER'])[1][0])
        self.xfmr_id = psspy.atrnchar(-1, 0, 0, 1, 1, ['ID'])[1][0]
        self.xfmr_P = np.asarray(psspy.atrnreal(-1, 1, 1, 1, 1, ['P'])[1][0])
        self.xfmr_Q = np.asarray(psspy.atrnreal(-1, 1, 1, 1, 1, ['Q'])[1][0])
        self.xfmr_RX = np.round(np.asarray(psspy.atrncplx(-1, 1, 1, 1, 1, ['RXACT'])[1][0]) * 1000000) / 1000000

        self.xfmr_k = np.asarray(psspy.atrnreal(-1, 1, 1, 1, 1, ['RATIO'])[1][0])
        for i in range(len(self.xfmr_to)):
            from0 = np.where(self.bus_num == self.xfmr_from[i])
            to0 = np.where(self.bus_num == self.xfmr_to[i])
            if self.bus_basekV[from0] < self.bus_basekV[to0]:
                tempn = self.xfmr_from[i]
                self.xfmr_from[i] = self.xfmr_to[i]
                self.xfmr_to[i] = tempn

        # shunt data
        self.shnt_bus = np.asarray(psspy.afxshuntint(-1, 1, 'NUMBER')[1][0])
        self.shnt_id = psspy.afxshuntchar(-1, 1, 'ID')[1][0]
        self.shnt_gb = np.asarray(psspy.afxshuntcplx(-1, 1, ['SHUNTNOM'])[1][0])

        # switched shunt data
        self.shnt_sw_bus = np.asarray(psspy.aswshint(-1, 1, 'NUMBER')[1][0])
        self.shnt_sw_gb = np.asarray(psspy.aswshcplx(-1, 1, ['YSWACT'])[1][0])

        for i in range(len(self.shnt_sw_bus)):
            j = len(self.shnt_sw_bus) - i - 1
            if np.abs(self.shnt_sw_gb[j]) < 1e-14:
                self.shnt_sw_gb = np.delete(self.shnt_sw_gb, j)
                self.shnt_sw_bus = np.delete(self.shnt_sw_bus, j)

    def LargeSysGenerator(self, ItfcBus, r, c):
        """

        :param ItfcBus:
        :param r:
        :param c:
        :return:
        """
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
                pfd.bus_Va = np.append(pfd.bus_Va, self.bus_Va)
                pfd.bus_Vm = np.append(pfd.bus_Vm, self.bus_Vm)
                pfd.bus_basekV = np.append(pfd.bus_basekV, self.bus_basekV)
                pfd.bus_kV = np.append(pfd.bus_kV, self.bus_kV)
                # bus name is skipped
                pfd.bus_num = np.append(pfd.bus_num, self.bus_num + len(self.bus_num) * (k - 1))
                pfd.bus_type = np.append(pfd.bus_type, self.bus_type)  # slack in other blocks to be modified

                # load
                if len(self.load_bus) > 0:
                    pfd.load_I = np.append(pfd.load_I, self.load_I)
                    pfd.load_MW = np.append(pfd.load_MW, self.load_MW)
                    pfd.load_Mvar = np.append(pfd.load_Mvar, self.load_Mvar)
                    pfd.load_P = np.append(pfd.load_P, self.load_P)
                    pfd.load_Z = np.append(pfd.load_Z, self.load_Z)
                    pfd.load_bus = np.append(pfd.load_bus, self.load_bus + len(self.bus_num) * (k - 1))
                    pfd.load_id = np.append(pfd.load_id, self.load_id)

                # shunt
                if len(self.shnt_bus) > 0:
                    pfd.shnt_gb = np.append(pfd.shnt_gb, self.shnt_gb)
                    pfd.shnt_bus = np.append(pfd.shnt_bus, self.shnt_bus + len(self.bus_num) * (k - 1))
                    pfd.shnt_id = np.append(pfd.shnt_id, self.shnt_id)

                # generator
                pfd.gen_MVA_base = np.append(pfd.gen_MVA_base, self.gen_MVA_base)
                pfd.gen_MW = np.append(pfd.gen_MW, self.gen_MW)
                pfd.gen_Mvar = np.append(pfd.gen_Mvar, self.gen_Mvar)
                pfd.gen_S = np.append(pfd.gen_S, self.gen_S)
                pfd.gen_bus = np.append(pfd.gen_bus, self.gen_bus + len(self.bus_num) * (k - 1))
                pfd.gen_id = np.append(pfd.gen_id, self.gen_id)
                pfd.gen_mod = np.append(pfd.gen_mod, self.gen_mod)

                # line
                if len(self.line_from) > 0:
                    pfd.line_P = np.append(pfd.line_P, self.line_P)
                    pfd.line_Q = np.append(pfd.line_Q, self.line_Q)
                    pfd.line_RX = np.append(pfd.line_RX, self.line_RX)
                    pfd.line_chg = np.append(pfd.line_chg, self.line_chg)
                    pfd.line_from = np.append(pfd.line_from, self.line_from + len(self.bus_num) * (k - 1))
                    pfd.line_id = np.append(pfd.line_id, self.line_id)
                    pfd.line_to = np.append(pfd.line_to, self.line_to + len(self.bus_num) * (k - 1))

                # transformer
                if len(self.xfmr_from) > 0:
                    pfd.xfmr_P = np.append(pfd.xfmr_P, self.xfmr_P)
                    pfd.xfmr_Q = np.append(pfd.xfmr_Q, self.xfmr_Q)
                    pfd.xfmr_RX = np.append(pfd.xfmr_RX, self.xfmr_RX)
                    pfd.xfmr_from = np.append(pfd.xfmr_from, self.xfmr_from + len(self.bus_num) * (k - 1))
                    pfd.xfmr_id = np.append(pfd.xfmr_id, self.xfmr_id)
                    pfd.xfmr_k = np.append(pfd.xfmr_k, self.xfmr_k)
                    pfd.xfmr_to = np.append(pfd.xfmr_to, self.xfmr_to + len(self.bus_num) * (k - 1))

        idx = np.where(pfd.bus_type == 3)[0][0]
        flag = 1
        while flag == 1:
            try:
                idx = np.where(pfd.bus_type[3:], idx + 1)
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
                FromB_G = np.where(pfd.gen_bus == FromB)[0][0]
                PG_From = pfd.gen_MW[FromB_G]
            else:
                print('Error: Interfacing bus should be generator bus.\n')

            if ToB in pfd.gen_bus:
                ToB_G = np.where(pfd.gen_bus == ToB)[0][0]
                PG_To = pfd.gen_MW[ToB_G]
            else:
                print('Error: Interfacing bus should be generator bus.\n')

            tempP = min(PG_From / 3, PG_To / 3, LinePmax) / pfd.basemva
            tempX = pfd.bus_Vm[FromB - 1] * pfd.bus_Vm[ToB - 1] * math.sin(abs(pfd.bus_Va[FromB - 1]
                                                                               - pfd.bus_Va[ToB - 1])) / tempP

            if abs(tempX) < 1e-5:
                tempX = 0.05

            chg = 1e-5
            # add the branch
            if abs(pfd.bus_basekV[FromB - 1] - pfd.bus_basekV[ToB - 1]) < 1e-5:  # kV level is the same, this is a line
                tempr = tempX / 10.0
                pfd.line_P = np.append(pfd.line_P, 0.0)
                pfd.line_Q = np.append(pfd.line_Q, 0.0)
                pfd.line_RX = np.append(pfd.line_RX, complex(tempr, tempX))
                pfd.line_chg = np.append(pfd.line_chg, chg)
                pfd.line_from = np.append(pfd.line_from, min(FromB, ToB))
                pfd.line_id = np.append(pfd.line_id, '1')
                pfd.line_to = np.append(pfd.line_to, max(FromB, ToB))

            else:  # this is a transformer
                tempr = tempX / 100.0
                if pfd.bus_basekV[FromB - 1] > pfd.bus_basekV[ToB - 1]:
                    pfd.xfmr_from = np.append(pfd.xfmr_from, FromB)
                    pfd.xfmr_to = np.append(pfd.xfmr_to, ToB)
                else:
                    pfd.xfmr_from = np.append(pfd.xfmr_from, ToB)
                    pfd.xfmr_to = np.append(pfd.xfmr_to, FromB)

                pfd.xfmr_id = np.append(pfd.xfmr_id, '1')
                pfd.xfmr_P = np.append(pfd.xfmr_P, 0.0)
                pfd.xfmr_Q = np.append(pfd.xfmr_Q, 0.0)
                pfd.xfmr_RX = np.append(pfd.xfmr_RX, complex(tempr, tempX))
                pfd.xfmr_k = np.append(pfd.xfmr_k, 1.0)

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
                    idx = np.where(pfd.load_bus == FromB)[0][0]
                    pfd.load_MW[idx] = pfd.load_MW[idx] - np.real(tempS_From) * pfd.basemva
                    pfd.load_P[idx] = pfd.load_P[idx] - complex(np.real(tempS_From) * pfd.basemva, 0.0)
                else:  # no existing load, need to add one
                    pfd.load_bus = np.append(pfd.load_bus, FromB)
                    pfd.load_id = np.append(pfd.load_id, '1')
                    pfd.load_P = np.append(pfd.load_P, complex(-np.real(tempS_From) * pfd.basemva, 0.0))
                    pfd.load_Z = np.append(pfd.load_Z, 0.0)
                    pfd.load_I = np.append(pfd.load_I, 0.0)
                    pfd.load_MW = np.append(pfd.load_MW, -np.real(tempS_From) * pfd.basemva)
                    pfd.load_Mvar = np.append(pfd.load_Mvar, 0.0)
            else:
                pass

            # adjust Mvar
            if np.imag(tempS_From) > 0:  # need to add shunt
                if FromB in pfd.shnt_bus:  # there is an existing shunt
                    idx = pfd.shnt_bus.index(FromB)
                    pfd.shnt_gb[idx] = pfd.shnt_gb[idx] + complex(0.0, np.imag(tempS_From) * pfd.basemva)
                else:  # no existing shunt, need to add one
                    pfd.shnt_bus = np.append(pfd.shnt_bus, FromB)
                    pfd.shnt_id = np.append(pfd.shnt_id, '1')
                    pfd.shnt_gb = np.append(pfd.shnt_gb, complex(0.0, np.imag(tempS_From) * pfd.basemva))
            elif np.imag(tempS_From) < 0:  # need to add Mvar load   # not run into during testing
                if FromB in pfd.load_bus:  # there is an existing load
                    idx = pfd.load_bus.index(FromB)
                    pfd.load_Mvar[idx] = pfd.load_Mvar[idx] - np.imag(tempS_From) * pfd.basemva
                    pfd.load_P[idx] = pfd.load_P[idx] - complex(0.0, np.imag(tempS_From) * pfd.basemva)
                else:  # no existing load, need to add one
                    pfd.load_bus = np.append(pfd.load_bus, FromB)
                    pfd.load_id = np.append(pfd.load_id, '1')
                    pfd.load_P = np.append(pfd.load_P, complex(0.0, -np.imag(tempS_From) * pfd.basemva))
                    pfd.load_Z = np.append(pfd.load_Z, 0.0)
                    pfd.load_I = np.append(pfd.load_I, 0.0)
                    pfd.load_Mvar = np.append(pfd.load_Mvar, -np.imag(tempS_From) * pfd.basemva)
                    pfd.load_MW = np.append(pfd.load_MW, 0.0)
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
                    pfd.load_bus = np.append(pfd.load_bus, ToB)
                    pfd.load_id = np.append(pfd.load_id, '1')
                    pfd.load_P = np.append(pfd.load_P, complex(-np.real(tempS_To) * pfd.basemva, 0.0))
                    pfd.load_Z = np.append(pfd.load_Z, 0.0)
                    pfd.load_I = np.append(pfd.load_I, 0.0)
                    pfd.load_MW = np.append(pfd.load_MW, -np.real(tempS_To) * pfd.basemva)
                    pfd.load_Mvar = np.append(pfd.load_Mvar, 0.0)
            else:
                pass

            # adjust Mvar
            if np.imag(tempS_To) > 0:  # need to add shunt
                if ToB in pfd.shnt_bus:  # there is an existing shunt
                    idx = pfd.shnt_bus.index(ToB)
                    pfd.shnt_gb[idx] = pfd.shnt_gb[idx] + complex(0.0, np.imag(tempS_To) * pfd.basemva)
                else:  # no existing shunt, need to add one
                    pfd.shnt_bus = np.append(pfd.shnt_bus, ToB)
                    pfd.shnt_id = np.append(pfd.shnt_id, '1')
                    pfd.shnt_gb = np.append(pfd.shnt_gb, complex(0.0, np.imag(tempS_To) * pfd.basemva))
            elif np.imag(tempS_To) < 0:  # need to add Mvar load   # not run into during testing
                if ToB in pfd.load_bus:  # there is an existing load
                    idx = pfd.load_bus.index(ToB)
                    pfd.load_Mvar[idx] = pfd.load_Mvar[idx] - np.imag(tempS_To) * pfd.basemva
                    pfd.load_P[idx] = pfd.load_P[idx] - complex(0.0, np.imag(tempS_To) * pfd.basemva)
                else:  # no existing load, need to add one
                    pfd.load_bus = np.append(pfd.load_bus, ToB)
                    pfd.load_id = np.append(pfd.load_id, '1')
                    pfd.load_P = np.append(pfd.load_P, complex(0.0, -np.imag(tempS_To) * pfd.basemva))
                    pfd.load_Z = np.append(pfd.load_Z, 0.0)
                    pfd.load_I = np.append(pfd.load_I, 0.0)
                    pfd.load_Mvar = np.append(pfd.load_Mvar, -np.imag(tempS_To) * pfd.basemva)
                    pfd.load_MW = np.append(pfd.load_MW, 0.0)
            else:
                pass

        return pfd

    def lists_to_arrays(self):
        """

        :return:
        """
        for k in self.__dict__.keys():
            attr = getattr(self, k)
            if type(attr) is list:
                setattr(self, k, np.array(attr))
        return
