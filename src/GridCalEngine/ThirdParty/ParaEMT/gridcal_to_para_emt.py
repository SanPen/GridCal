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
from GridCalEngine.ThirdParty.ParaEMT.Lib_BW import PFData, DyData, Initialize, EmtSimu, States, States_ibr
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

    # types
    dyd0.gen_type = np.asarray([])
    dyd0.exc_type = np.asarray([])
    dyd0.gov_type = np.asarray([])
    dyd0.pss_type = np.asarray([])

    dyd0.gen_Ra = np.asarray([])  # pu on machine MVA base
    dyd0.gen_X0 = np.asarray([])  # pu on machine MVA base

    # gen
    dyd0.gen_n = 0

    # GENROU
    dyd0.gen_genrou_bus = np.asarray([])
    dyd0.gen_genrou_id = np.asarray([])
    dyd0.gen_genrou_Td0p = np.asarray([])
    dyd0.gen_genrou_Td0pp = np.asarray([])
    dyd0.gen_genrou_Tq0p = np.asarray([])
    dyd0.gen_genrou_Tq0pp = np.asarray([])
    dyd0.gen_H = np.asarray([])  # pu on machine MVA base
    dyd0.gen_D = np.asarray([])  # pu on machine MVA base
    dyd0.gen_genrou_Xd = np.asarray([])  # pu on machine MVA base
    dyd0.gen_genrou_Xq = np.asarray([])  # pu on machine MVA base
    dyd0.gen_genrou_Xdp = np.asarray([])  # pu on machine MVA base
    dyd0.gen_genrou_Xqp = np.asarray([])  # pu on machine MVA base
    dyd0.gen_genrou_Xdpp = np.asarray([])  # pu on machine MVA base
    dyd0.gen_genrou_Xl = np.asarray([])  # pu on machine MVA base
    dyd0.gen_genrou_S10 = np.asarray([])
    dyd0.gen_genrou_S12 = np.asarray([])
    dyd0.gen_genrou_idx = np.asarray([])
    dyd0.gen_genrou_n = 0
    dyd0.gen_genrou_xi_st = 0
    dyd0.gen_genrou_odr = 0

    # exc
    dyd0.exc_n = 0

    # SEXS
    dyd0.exc_sexs_bus = np.asarray([])
    dyd0.exc_sexs_id = np.asarray([])
    dyd0.exc_sexs_TA_o_TB = np.asarray([])
    dyd0.exc_sexs_TA = np.asarray([])
    dyd0.exc_sexs_TB = np.asarray([])
    dyd0.exc_sexs_K = np.asarray([])
    dyd0.exc_sexs_TE = np.asarray([])
    dyd0.exc_sexs_Emin = np.asarray([])  # pu on EFD base
    dyd0.exc_sexs_Emax = np.asarray([])  # pu on EFD base
    dyd0.exc_sexs_idx = np.asarray([])
    dyd0.exc_sexs_n = 0
    dyd0.exc_sexs_xi_st = 0
    dyd0.exc_sexs_odr = 0

    # gov
    dyd0.gov_n = 0

    # TGOV1
    dyd0.gov_tgov1_bus = np.asarray([])
    dyd0.gov_tgov1_id = np.asarray([])
    dyd0.gov_tgov1_R = np.asarray([])  # pu on machine MVA base
    dyd0.gov_tgov1_T1 = np.asarray([])
    dyd0.gov_tgov1_Vmax = np.asarray([])  # pu on machine MVA base
    dyd0.gov_tgov1_Vmin = np.asarray([])  # pu on machine MVA base
    dyd0.gov_tgov1_T2 = np.asarray([])
    dyd0.gov_tgov1_T3 = np.asarray([])
    dyd0.gov_tgov1_Dt = np.asarray([])  # pu on machine MVA base
    dyd0.gov_tgov1_idx = np.asarray([])
    dyd0.gov_tgov1_n = 0
    dyd0.gov_tgov1_xi_st = 0
    dyd0.gov_tgov1_odr = 0

    # HYGOV
    dyd0.gov_hygov_bus = np.asarray([])
    dyd0.gov_hygov_id = np.asarray([])
    dyd0.gov_hygov_R = np.asarray([])  # pu on machine MVA base
    dyd0.gov_hygov_r = np.asarray([])  # pu on machine MVA base
    dyd0.gov_hygov_Tr = np.asarray([])
    dyd0.gov_hygov_Tf = np.asarray([])
    dyd0.gov_hygov_Tg = np.asarray([])
    dyd0.gov_hygov_VELM = np.asarray([])
    dyd0.gov_hygov_GMAX = np.asarray([])
    dyd0.gov_hygov_GMIN = np.asarray([])
    dyd0.gov_hygov_TW = np.asarray([])
    dyd0.gov_hygov_At = np.asarray([])
    dyd0.gov_hygov_Dturb = np.asarray([])  # pu on machine MVA base
    dyd0.gov_hygov_qNL = np.asarray([])
    dyd0.gov_hygov_idx = np.asarray([])
    dyd0.gov_hygov_n = 0
    dyd0.gov_hygov_xi_st = 0
    dyd0.gov_hygov_odr = 0

    # GAST
    dyd0.gov_gast_bus = np.asarray([])
    dyd0.gov_gast_id = np.asarray([])
    dyd0.gov_gast_R = np.asarray([])
    dyd0.gov_gast_T1 = np.asarray([])
    dyd0.gov_gast_T2 = np.asarray([])
    dyd0.gov_gast_T3 = np.asarray([])
    dyd0.gov_gast_LdLmt = np.asarray([])
    dyd0.gov_gast_KT = np.asarray([])
    dyd0.gov_gast_VMAX = np.asarray([])
    dyd0.gov_gast_VMIN = np.asarray([])
    dyd0.gov_gast_Dturb = np.asarray([])
    dyd0.gov_gast_idx = np.asarray([])
    dyd0.gov_gast_n = 0
    dyd0.gov_gast_xi_st = 0
    dyd0.gov_gast_odr = 0

    ## pss
    dyd0.pss_n = 0

    # IEEEST
    dyd0.pss_ieeest_bus = np.asarray([])
    dyd0.pss_ieeest_id = np.asarray([])
    dyd0.pss_ieeest_A1 = np.asarray([])
    dyd0.pss_ieeest_A2 = np.asarray([])
    dyd0.pss_ieeest_A3 = np.asarray([])
    dyd0.pss_ieeest_A4 = np.asarray([])
    dyd0.pss_ieeest_A5 = np.asarray([])
    dyd0.pss_ieeest_A6 = np.asarray([])
    dyd0.pss_ieeest_T1 = np.asarray([])
    dyd0.pss_ieeest_T2 = np.asarray([])
    dyd0.pss_ieeest_T3 = np.asarray([])
    dyd0.pss_ieeest_T4 = np.asarray([])
    dyd0.pss_ieeest_T5 = np.asarray([])
    dyd0.pss_ieeest_T6 = np.asarray([])
    dyd0.pss_ieeest_KS = np.asarray([])
    dyd0.pss_ieeest_LSMAX = np.asarray([])
    dyd0.pss_ieeest_LSMIN = np.asarray([])
    dyd0.pss_ieeest_VCU = np.asarray([])
    dyd0.pss_ieeest_VCL = np.asarray([])
    dyd0.pss_ieeest_idx = np.asarray([])
    dyd0.pss_ieeest_n = 0
    dyd0.pss_ieeest_xi_st = 0
    dyd0.pss_ieeest_odr = 0

    dyd0.ec_Lad = np.asarray([])
    dyd0.ec_Laq = np.asarray([])
    dyd0.ec_Ll = np.asarray([])
    dyd0.ec_Lffd = np.asarray([])
    dyd0.ec_L11d = np.asarray([])
    dyd0.ec_L11q = np.asarray([])
    dyd0.ec_L22q = np.asarray([])
    dyd0.ec_Lf1d = np.asarray([])

    dyd0.ec_Ld = np.asarray([])
    dyd0.ec_Lq = np.asarray([])
    dyd0.ec_L0 = np.asarray([])

    dyd0.ec_Ra = np.asarray([])
    dyd0.ec_Rfd = np.asarray([])
    dyd0.ec_R1d = np.asarray([])
    dyd0.ec_R1q = np.asarray([])
    dyd0.ec_R2q = np.asarray([])

    dyd0.ec_Lfd = np.asarray([])
    dyd0.ec_L1d = np.asarray([])
    dyd0.ec_L1q = np.asarray([])
    dyd0.ec_L2q = np.asarray([])

    dyd0.base_es = np.asarray([])
    dyd0.base_is = np.asarray([])
    dyd0.base_Is = np.asarray([])
    dyd0.base_Zs = np.asarray([])
    dyd0.base_Ls = np.asarray([])
    dyd0.base_ifd = np.asarray([])
    dyd0.base_efd = np.asarray([])
    dyd0.base_Zfd = np.asarray([])
    dyd0.base_Lfd = np.asarray([])

    ## IBR parameters
    dyd0.ibr_n = 0
    dyd0.ibr_odr = 0

    dyd0.ibr_kVbase = np.asarray([])
    dyd0.ibr_MVAbase = np.asarray([])
    dyd0.ibr_fbase = np.asarray([])
    dyd0.ibr_Ibase = np.asarray([])

    dyd0.ibr_regca_bus = np.asarray([])
    dyd0.ibr_regca_id = np.asarray([])
    dyd0.ibr_regca_LVPLsw = np.asarray([])
    dyd0.ibr_regca_Tg = np.asarray([])
    dyd0.ibr_regca_Rrpwr = np.asarray([])
    dyd0.ibr_regca_Brkpt = np.asarray([])
    dyd0.ibr_regca_Zerox = np.asarray([])
    dyd0.ibr_regca_Lvpl1 = np.asarray([])
    dyd0.ibr_regca_Volim = np.asarray([])
    dyd0.ibr_regca_Lvpnt1 = np.asarray([])
    dyd0.ibr_regca_Lvpnt0 = np.asarray([])
    dyd0.ibr_regca_Iolim = np.asarray([])
    dyd0.ibr_regca_Tfltr = np.asarray([])
    dyd0.ibr_regca_Khv = np.asarray([])
    dyd0.ibr_regca_Iqrmax = np.asarray([])
    dyd0.ibr_regca_Iqrmin = np.asarray([])
    dyd0.ibr_regca_Accel = np.asarray([])

    dyd0.ibr_reecb_bus = np.asarray([])
    dyd0.ibr_reecb_id = np.asarray([])
    dyd0.ibr_reecb_PFFLAG = np.asarray([])
    dyd0.ibr_reecb_VFLAG = np.asarray([])
    dyd0.ibr_reecb_QFLAG = np.asarray([])
    dyd0.ibr_reecb_PQFLAG = np.asarray([])
    dyd0.ibr_reecb_Vdip = np.asarray([])
    dyd0.ibr_reecb_Vup = np.asarray([])
    dyd0.ibr_reecb_Trv = np.asarray([])
    dyd0.ibr_reecb_dbd1 = np.asarray([])
    dyd0.ibr_reecb_dbd2 = np.asarray([])
    dyd0.ibr_reecb_Kqv = np.asarray([])
    dyd0.ibr_reecb_Iqhl = np.asarray([])
    dyd0.ibr_reecb_Iqll = np.asarray([])
    dyd0.ibr_reecb_Vref0 = np.asarray([])
    dyd0.ibr_reecb_Tp = np.asarray([])
    dyd0.ibr_reecb_Qmax = np.asarray([])
    dyd0.ibr_reecb_Qmin = np.asarray([])
    dyd0.ibr_reecb_Vmax = np.asarray([])
    dyd0.ibr_reecb_Vmin = np.asarray([])
    dyd0.ibr_reecb_Kqp = np.asarray([])
    dyd0.ibr_reecb_Kqi = np.asarray([])
    dyd0.ibr_reecb_Kvp = np.asarray([])
    dyd0.ibr_reecb_Kvi = np.asarray([])
    dyd0.ibr_reecb_Tiq = np.asarray([])
    dyd0.ibr_reecb_dPmax = np.asarray([])
    dyd0.ibr_reecb_dPmin = np.asarray([])
    dyd0.ibr_reecb_Pmax = np.asarray([])
    dyd0.ibr_reecb_Pmin = np.asarray([])
    dyd0.ibr_reecb_Imax = np.asarray([])
    dyd0.ibr_reecb_Tpord = np.asarray([])

    dyd0.ibr_repca_bus = np.asarray([])
    dyd0.ibr_repca_id = np.asarray([])
    dyd0.ibr_repca_remote_bus = np.asarray([])
    dyd0.ibr_repca_branch_From_bus = np.asarray([])
    dyd0.ibr_repca_branch_To_bus = np.asarray([])
    dyd0.ibr_repca_branch_id = np.asarray([])
    dyd0.ibr_repca_VCFlag = np.asarray([])
    dyd0.ibr_repca_RefFlag = np.asarray([])
    dyd0.ibr_repca_FFlag = np.asarray([])
    dyd0.ibr_repca_Tfltr = np.asarray([])
    dyd0.ibr_repca_Kp = np.asarray([])
    dyd0.ibr_repca_Ki = np.asarray([])
    dyd0.ibr_repca_Tft = np.asarray([])
    dyd0.ibr_repca_Tfv = np.asarray([])
    dyd0.ibr_repca_Vfrz = np.asarray([])
    dyd0.ibr_repca_Rc = np.asarray([])
    dyd0.ibr_repca_Xc = np.asarray([])
    dyd0.ibr_repca_Kc = np.asarray([])
    dyd0.ibr_repca_emax = np.asarray([])
    dyd0.ibr_repca_emin = np.asarray([])
    dyd0.ibr_repca_dbd1 = np.asarray([])
    dyd0.ibr_repca_dbd2 = np.asarray([])
    dyd0.ibr_repca_Qmax = np.asarray([])
    dyd0.ibr_repca_Qmin = np.asarray([])
    dyd0.ibr_repca_Kpg = np.asarray([])
    dyd0.ibr_repca_Kig = np.asarray([])
    dyd0.ibr_repca_Tp = np.asarray([])
    dyd0.ibr_repca_fdbd1 = np.asarray([])
    dyd0.ibr_repca_fdbd2 = np.asarray([])
    dyd0.ibr_repca_femax = np.asarray([])
    dyd0.ibr_repca_femin = np.asarray([])
    dyd0.ibr_repca_Pmax = np.asarray([])
    dyd0.ibr_repca_Pmin = np.asarray([])
    dyd0.ibr_repca_Tg = np.asarray([])
    dyd0.ibr_repca_Ddn = np.asarray([])
    dyd0.ibr_repca_Dup = np.asarray([])

    # PLL for bus freq/ang measurement
    dyd0.pll_bus = np.asarray([])
    dyd0.pll_ke = np.asarray([])
    dyd0.pll_te = np.asarray([])
    dyd0.bus_odr = 0

    # bus volt magnitude measurement
    dyd0.vm_bus = np.asarray([])
    dyd0.vm_te = np.asarray([])

    # measurement method
    dyd0.mea_bus = np.asarray([])
    dyd0.mea_method = np.asarray([])

    # load
    dyd0.load_odr = 0

    return dyd0


def get_initialize_data(pfd: PFData, dyd: DyData) -> Initialize:
    """

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
    nibr = 0

    emt = EmtSimu(ngen=nc.ngen,
                  nibr=nibr,  # number of inverted based resources
                  nbus=nc.nbus,
                  nload=nc.nload)

    # three - phase synchronous machine model, unit in Ohm
    emt.ts = 50e-6  # second
    emt.Tlen = 0.1  # second
    emt.Nlen = np.asarray([])

    emt.t = {}
    emt.x = {}
    emt.x_pv_1 = []
    emt.x_pred = {}
    emt.x_ibr = {}
    emt.x_ibr_pv_1 = []
    emt.x_load = {}
    emt.x_load_pv_1 = []
    emt.x_bus = {}
    emt.x_bus_pv_1 = []
    emt.v = {}
    emt.i = {}

    emt.xp = States(nc.ngen)  # seems not necessary, try later and see if they can be deleted
    emt.xp_ibr = States_ibr(nibr)
    emt.Igs = np.zeros(3 * nc.nbus)
    emt.Isg = np.zeros(3 * nc.ngen)
    emt.Igi = np.zeros(3 * nc.nbus)
    emt.Il = np.zeros(3 * nc.nbus)  # to change to Igl and Iload
    emt.Ild = np.zeros(3 * nc.nload)
    emt.Iibr = np.zeros(3 * nibr)
    emt.brch_Ihis = np.asarray([])
    emt.brch_Ipre = np.asarray([])
    emt.node_Ihis = np.asarray([])
    emt.I_RHS = np.zeros(3 * nc.nbus)
    emt.Vsol = np.zeros(3 * nc.nbus)
    emt.Vsol_1 = np.zeros(3 * nc.nbus)

    # emt.fft_vabc = []
    # emt.fft_T = 1
    # emt.fft_N = 0
    # emt.fft_vma = {}
    # emt.fft_vpn0 = {}

    emt.theta = np.zeros(nc.ngen)
    emt.ed_mod = np.zeros(nc.ngen)
    emt.eq_mod = np.zeros(nc.ngen)

    emt.t_release_f = 0.1
    emt.loadmodel_option = 1  # 1-const rlc, 2-const z

    # step change
    emt.t_sc = 1000  # the time when the step change occurs
    emt.i_gen_sc = 1  # which gen, index in pfd.gen_bus
    emt.flag_exc_gov = 1  # 0 - exc, 1 - gov
    emt.dsp = - 0.2  # increment
    emt.flag_sc = 1  # 1 - step change to be implemented, 0 - step change completed

    # gen trip
    emt.t_gentrip = 1000  # the time when the gentrip occurs
    emt.i_gentrip = 1  # which gen, index in pfd.gen_bus
    emt.flag_gentrip = 1  # 1 - gentrip to be implemented, 0 - gentrip completed
    emt.flag_reinit = 1  # 1 - re-init to be implemented, 0 - re-init completed

    # ref at last time step (for calculating dref term)
    emt.vref = np.zeros(nc.ngen)
    emt.vref_1 = np.zeros(nc.ngen)
    emt.gref = np.zeros(nc.ngen)

    # playback
    emt.data = []
    emt.playback_enable = 0
    emt.playback_t_chn = 0
    emt.playback_sig_chn = 1
    emt.playback_tn = 0

    emt.data1 = []
    emt.playback_enable1 = 0
    emt.playback_t_chn1 = 0
    emt.playback_sig_chn1 = 1
    emt.playback_tn1 = 0

    # mac as I source
    emt.flag_Isrc = 0

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
    ini = get_initialize_data(pfd=pfd, dyd=dyd)
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
