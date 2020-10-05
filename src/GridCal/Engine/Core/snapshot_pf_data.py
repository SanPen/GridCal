# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
import pandas as pd
from typing import List

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian
from GridCal.Engine.Core.common_functions import compile_types
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Simulations.sparse_solve import get_sparse_type
from GridCal.Engine.Core.DataStructures import *
import GridCal.Engine.Core.admittance_matrices as ycalc

sparse_type = get_sparse_type()


class SnapshotCircuit:

    def __init__(self, nbus, nline, ndcline, ntr, nvsc, nhvdc, nload, ngen, nbatt, nshunt, nstagen, sbase):
        """

        :param nbus:
        :param nline:
        :param ndcline:
        :param ntr:
        :param nvsc:
        :param nhvdc:
        :param nload:
        :param ngen:
        :param nbatt:
        :param nshunt:
        :param nstagen:
        :param sbase:
        """

        self.nbus = nbus
        self.nline = nline
        self.ndcline = ndcline
        self.ntr = ntr
        self.nvsc = nvsc
        self.nhvdc = nhvdc
        self.nload = nload
        self.ngen = ngen
        self.nbatt = nbatt
        self.nshunt = nshunt
        self.nstagen = nstagen

        self.nbr = nline + ntr + nvsc + ndcline

        self.Sbase = sbase

        # --------------------------------------------------------------------------------------------------------------
        # Data structures
        # --------------------------------------------------------------------------------------------------------------
        self.bus_data = BusData(nbus=nbus)
        self.branch_data = BranchData(nbr=self.nbr, nbus=nbus)
        self.line_data = LinesData(nline=nline, nbus=nbus)
        self.dc_line_data = DcLinesData(ndcline=ndcline, nbus=nbus)
        self.transformer_data = TransformerData(ntr=ntr, nbus=nbus)
        self.hvdc_data = HvdcData(nhvdc=nhvdc, nbus=nbus)
        self.vsc_data = VscData(nvsc=nvsc, nbus=nbus)
        self.load_data = LoadData(nload=nload, nbus=nbus)
        self.static_generator_data = StaticGeneratorData(nstagen=nstagen, nbus=nbus)
        self.battery_data = BatteryData(nbatt=nbatt, nbus=nbus)
        self.generator_data = GeneratorData(ngen=ngen, nbus=nbus)
        self.shunt_data = ShuntData(nshunt=nshunt, nbus=nbus)

        # --------------------------------------------------------------------------------------------------------------
        # Results
        # --------------------------------------------------------------------------------------------------------------

        self.Cf_ = None
        self.Ct_ = None

        self.Vbus_ = None
        self.Sbus_ = None
        self.Ibus_ = None
        self.Yshunt_from_devices_ = None

        self.Qmax_bus_ = None
        self.Qmin_bus_ = None

        self.Ybus_ = None
        self.Yf_ = None
        self.Yt_ = None

        # Admittance for HELM / AC linear
        self.Yseries_ = None
        self.Yshunt_ = None

        # Admittances for Fast-Decoupled
        self.B1_ = None
        self.B2_ = None

        # Admittances for Linear
        self.Bbus_ = None
        self.Bf_ = None
        self.Bpqpv_ = None
        self.Bref_ = None

        self.original_bus_idx = np.arange(self.nbus)
        self.original_branch_idx = np.arange(self.nbr)
        self.original_line_idx = np.arange(self.nline)
        self.original_tr_idx = np.arange(self.ntr)
        self.original_dc_line_idx = np.arange(self.ndcline)
        self.original_vsc_idx = np.arange(self.nvsc)
        self.original_hvdc_idx = np.arange(self.nhvdc)
        self.original_gen_idx = np.arange(self.ngen)
        self.original_bat_idx = np.arange(self.nbatt)
        self.original_load_idx = np.arange(self.nload)
        self.original_stagen_idx = np.arange(self.nstagen)
        self.original_shunt_idx = np.arange(self.nshunt)

        self.pq_ = None
        self.pv_ = None
        self.vd_ = None
        self.pqpv_ = None

        self.available_structures = ['Vbus',
                                     'Sbus',
                                     'Ibus',
                                     'Ybus',
                                     'Yf',
                                     'Yt',
                                     'Cf',
                                     'Ct',
                                     'Yshunt',
                                     'Yseries',
                                     "B'",
                                     "B''",
                                     'Types',
                                     'Jacobian',
                                     'Qmin',
                                     'Qmax',
                                     'pq',
                                     'pv',
                                     'vd',
                                     'pqpv',
                                     'original_bus_idx',
                                     'original_branch_idx',
                                     'original_line_idx',
                                     'original_tr_idx',
                                     'original_gen_idx',
                                     'original_bat_idx'
                                     ]

    def get_injections(self, normalize=True):
        """
        Compute the power
        :return: return the array of power injections in MW if normalized is false, in p.u. otherwise
        """

        # load
        Sbus = self.load_data.get_injections_per_bus()  # MW (negative already)

        # static generators
        Sbus += self.static_generator_data.get_injections_per_bus()

        # generators
        Sbus += self.generator_data.get_injections_per_bus()

        # battery
        Sbus += self.battery_data.get_injections_per_bus()

        # HVDC forced power
        if self.nhvdc:
            # Pf and Pt come with the correct sign already
            Sbus += self.hvdc_data.get_injections_per_bus()

        if normalize:
            Sbus /= self.Sbase

        return Sbus

    def consolidate_information(self):
        """
        Consolidates the information of this object
        :return:
        """

        self.nbus = len(self.bus_data)
        self.nline = len(self.line_data)
        self.ndcline = len(self.dc_line_data)
        self.ntr = len(self.transformer_data)
        self.nvsc = len(self.vsc_data)
        self.nhvdc = len(self.hvdc_data)
        self.nload = len(self.load_data)
        self.ngen = len(self.generator_data)
        self.nbatt = len(self.battery_data)
        self.nshunt = len(self.shunt_data)
        self.nstagen = len(self.static_generator_data)
        self.nbr = self.nline + self.ntr + self.nvsc + self.ndcline

        self.original_bus_idx = np.arange(self.nbus)
        self.original_branch_idx = np.arange(self.nbr)
        self.original_line_idx = np.arange(self.nline)
        self.original_tr_idx = np.arange(self.ntr)
        self.original_dc_line_idx = np.arange(self.ndcline)
        self.original_vsc_idx = np.arange(self.nvsc)
        self.original_hvdc_idx = np.arange(self.nhvdc)
        self.original_gen_idx = np.arange(self.ngen)
        self.original_bat_idx = np.arange(self.nbatt)
        self.original_load_idx = np.arange(self.nload)
        self.original_stagen_idx = np.arange(self.nstagen)
        self.original_shunt_idx = np.arange(self.nshunt)

        self.branch_data.C_branch_bus_f = self.branch_data.C_branch_bus_f.tocsc()
        self.branch_data.C_branch_bus_t = self.branch_data.C_branch_bus_t.tocsc()

        self.line_data.C_line_bus = self.line_data.C_line_bus.tocsc()
        self.dc_line_data.C_dc_line_bus = self.dc_line_data.C_dc_line_bus.tocsc()
        self.transformer_data.C_tr_bus = self.transformer_data.C_tr_bus.tocsc()
        self.hvdc_data.C_hvdc_bus_f = self.hvdc_data.C_hvdc_bus_f.tocsc()
        self.hvdc_data.C_hvdc_bus_t = self.hvdc_data.C_hvdc_bus_t.tocsc()
        self.vsc_data.C_vsc_bus = self.vsc_data.C_vsc_bus.tocsc()

        self.load_data.C_bus_load = self.load_data.C_bus_load.tocsr()
        self.battery_data.C_bus_batt = self.battery_data.C_bus_batt.tocsr()
        self.generator_data.C_bus_gen = self.generator_data.C_bus_gen.tocsr()
        self.shunt_data.C_bus_shunt = self.shunt_data.C_bus_shunt.tocsr()
        self.static_generator_data.C_bus_static_generator = self.static_generator_data.C_bus_static_generator.tocsr()

        self.bus_data.bus_installed_power = self.generator_data.get_installed_power_per_bus()
        self.bus_data.bus_installed_power += self.battery_data.get_installed_power_per_bus()

    def re_calc_admittance_matrices(self, tap_module):
        """

        :param tap_module:
        :return:
        """
        self.Ybus_, self.Yf_, self.Yt_ = ycalc.compute_admittances(R=self.branch_data.R,
                                                                   X=self.branch_data.X,
                                                                   G=self.branch_data.G,
                                                                   B=self.branch_data.B,
                                                                   k=self.branch_data.k,
                                                                   m=tap_module,
                                                                   mf=self.branch_data.tap_f,
                                                                   mt=self.branch_data.tap_t,
                                                                   theta=self.branch_data.theta,
                                                                   Beq=self.branch_data.Beq,
                                                                   Cf=self.Cf,
                                                                   Ct=self.Ct,
                                                                   G0=self.branch_data.G0,
                                                                   If=np.zeros(len(self.branch_data)),
                                                                   a=self.branch_data.a,
                                                                   b=self.branch_data.b,
                                                                   c=self.branch_data.c,
                                                                   Yshunt_bus=self.Yshunt_from_devices)

    @property
    def Vbus(self):

        if self.Vbus_ is None:
            self.Vbus_ = self.bus_data.Vbus.copy()

        return self.Vbus_

    @property
    def Sbus(self):

        if self.Sbus_ is None:
            self.Sbus_ = self.get_injections(normalize=True)

        return self.Sbus_

    @property
    def Ibus(self):

        if self.Ibus_ is None:
            self.Ibus_ = np.zeros(len(self.bus_data), dtype=complex)

        return self.Ibus_

    @property
    def Qmax_bus(self):

        if self.Qmax_bus_ is None:
            self.Qmax_bus_, self.Qmin_bus_ = self.compute_reactive_power_limits()

        return self.Qmax_bus_

    @property
    def Qmin_bus(self):

        if self.Qmin_bus_ is None:
            self.Qmax_bus_, self.Qmin_bus_ = self.compute_reactive_power_limits()

        return self.Qmin_bus_

    @property
    def Yshunt_from_devices(self):

        # compute on demand and store
        if self.Yshunt_from_devices_ is None:
            self.Yshunt_from_devices_ = self.shunt_data.get_injections_per_bus() / self.Sbase

        return self.Yshunt_from_devices_

    @property
    def bus_types(self):
        return self.bus_data.bus_types

    @property
    def bus_installed_power(self):
        return self.bus_data.bus_installed_power

    @property
    def bus_names(self):
        return self.bus_data.bus_names

    @property
    def branch_names(self):
        return self.branch_data.branch_names

    @property
    def tr_names(self):
        return self.transformer_data.tr_names

    @property
    def hvdc_names(self):
        return self.hvdc_data.hvdc_names

    @property
    def tr_tap_position(self):
        return self.transformer_data.tr_tap_position

    @property
    def tr_tap_mod(self):
        return self.transformer_data.tr_tap_mod

    @property
    def tr_bus_to_regulated_idx(self):
        return self.transformer_data.tr_bus_to_regulated_idx

    @property
    def tr_max_tap(self):
        return self.transformer_data.tr_max_tap

    @property
    def tr_min_tap(self):
        return self.transformer_data.tr_min_tap

    @property
    def tr_tap_inc_reg_up(self):
        return self.transformer_data.tr_tap_inc_reg_up

    @property
    def tr_tap_inc_reg_down(self):
        return self.transformer_data.tr_tap_inc_reg_down

    @property
    def tr_vset(self):
        return self.transformer_data.tr_vset

    @property
    def F(self):
        return self.branch_data.F

    @property
    def T(self):
        return self.branch_data.T

    @property
    def branch_rates(self):
        return self.branch_data.branch_rates

    @property
    def hvdc_Pf(self):
        return self.hvdc_data.hvdc_Pf

    @property
    def hvdc_loading(self):
        return self.hvdc_data.get_loading()

    @property
    def hvdc_losses(self):
        return self.hvdc_data.get_losses()

    @property
    def Cf(self):

        # compute on demand and store
        if self.Cf_ is None:
            self.Cf_, self.Ct_ = ycalc.compute_connectivity(branch_active=self.branch_data.branch_active,
                                                            Cf_=self.branch_data.C_branch_bus_f,
                                                            Ct_=self.branch_data.C_branch_bus_t)
        return self.Cf_

    @property
    def Ct(self):

        # compute on demand and store
        if self.Ct_ is None:
            self.Cf_, self.Ct_ = ycalc.compute_connectivity(branch_active=self.branch_data.branch_active,
                                                            Cf_=self.branch_data.C_branch_bus_f,
                                                            Ct_=self.branch_data.C_branch_bus_t)
        return self.Ct_

    @property
    def Ybus(self):

        # compute admittances on demand
        if self.Ybus_ is None:

            self.Ybus_, self.Yf_, self.Yt_ = ycalc.compute_admittances(R=self.branch_data.R,
                                                                       X=self.branch_data.X,
                                                                       G=self.branch_data.G,
                                                                       B=self.branch_data.B,
                                                                       k=self.branch_data.k,
                                                                       m=self.branch_data.m,
                                                                       mf=self.branch_data.tap_f,
                                                                       mt=self.branch_data.tap_t,
                                                                       theta=self.branch_data.theta,
                                                                       Beq=self.branch_data.Beq,
                                                                       Cf=self.Cf,
                                                                       Ct=self.Ct,
                                                                       G0=self.branch_data.G0,
                                                                       If=np.zeros(len(self.branch_data)),
                                                                       a=self.branch_data.a,
                                                                       b=self.branch_data.b,
                                                                       c=self.branch_data.c,
                                                                       Yshunt_bus=self.Yshunt_from_devices)
        return self.Ybus_

    @property
    def Yf(self):

        if self.Yf_ is None:
            x = self.Ybus  # call the constructor of Yf

        return self.Yf_

    @property
    def Yt(self):

        if self.Yt_ is None:
            x = self.Ybus  # call the constructor of Yt

        return self.Yt_

    @property
    def Yseries(self):

        # compute admittances on demand
        if self.Yseries_ is None:

            self.Yseries_, self.Yshunt_ = ycalc.compute_split_admittances(R=self.branch_data.R,
                                                                          X=self.branch_data.X,
                                                                          G=self.branch_data.G,
                                                                          B=self.branch_data.B,
                                                                          k=self.branch_data.k,
                                                                          m=self.branch_data.m,
                                                                          mf=self.branch_data.tap_f,
                                                                          mt=self.branch_data.tap_t,
                                                                          theta=self.branch_data.theta,
                                                                          Beq=self.branch_data.Beq,
                                                                          Cf=self.Cf,
                                                                          Ct=self.Ct,
                                                                          G0=self.branch_data.G0,
                                                                          If=np.zeros(len(self.branch_data)),
                                                                          a=self.branch_data.a,
                                                                          b=self.branch_data.b,
                                                                          c=self.branch_data.c,
                                                                          Yshunt_bus=self.Yshunt_from_devices)
        return self.Yseries_

    @property
    def Yshunt(self):

        if self.Yshunt_ is None:
            x = self.Yseries  # call the constructor of Yshunt

        return self.Yshunt_

    @property
    def B1(self):

        if self.B1_ is None:

            self.B1_, self.B2_ = ycalc.compute_fast_decoupled_admittances(X=self.branch_data.X,
                                                                          B=self.branch_data.B,
                                                                          m=self.branch_data.m,
                                                                          mf=self.branch_data.vf_set,
                                                                          mt=self.branch_data.vt_set,
                                                                          Cf=self.Cf,
                                                                          Ct=self.Ct)
        return self.B1_

    @property
    def B2(self):

        if self.B2_ is None:
            x = self.B1  # call the constructor of B2

        return self.B2_

    @property
    def Bbus(self):

        if self.Bbus_ is None:
            self.Bbus_, self.Bf_ = ycalc.compute_linear_admittances(X=self.branch_data.X,
                                                                    m=self.branch_data.m,
                                                                    Cf=self.Cf,
                                                                    Ct=self.Ct)
            self.Bpqpv_ = self.Bbus_[np.ix_(self.pqpv, self.pqpv)]
            self.Bref_ = self.Bbus_[np.ix_(self.pqpv, self.vd)]

        return self.Bbus_

    @property
    def Bf(self):

        if self.Bf_ is None:
            x = self.Bbus  # call the constructor of Bf

        return self.Bf_

    @property
    def Bpqpv(self):

        if self.Bpqpv_ is None:
            x = self.Bbus  # call the constructor of Bpqpv

        return self.Bpqpv_

    @property
    def Bref(self):

        if self.Bref_ is None:
            x = self.Bbus  # call the constructor of Bref

        return self.Bref_

    @property
    def vd(self):

        if self.vd_ is None:
            self.vd_, self.pq_, self.pv_, self.pqpv_ = compile_types(Sbus=self.Sbus, types=self.bus_data.bus_types)

        return self.vd_

    @property
    def pq(self):

        if self.pq_ is None:
            x = self.vd  # call the constructor

        return self.pq_

    @property
    def pv(self):

        if self.pv_ is None:
            x = self.vd  # call the constructor

        return self.pv_

    @property
    def pqpv(self):

        if self.pqpv_ is None:
            x = self.vd  # call the constructor

        return self.pqpv_

    def compute_reactive_power_limits(self):
        """
        compute the reactive power limits in place
        :return: Qmax_bus, Qmin_bus
        """
        # generators
        Qmax_bus = self.generator_data.get_qmax_per_bus()
        Qmin_bus = self.generator_data.get_qmin_per_bus()

        if self.nbatt > 0:
            # batteries
            Qmax_bus += self.battery_data.get_qmax_per_bus()
            Qmin_bus += self.battery_data.get_qmin_per_bus()

        if self.nhvdc > 0:
            # hvdc from
            Qmax_bus += self.hvdc_data.get_qmax_from_per_bus()
            Qmin_bus += self.hvdc_data.get_qmin_from_per_bus()

            # hvdc to
            Qmax_bus += self.hvdc_data.get_qmax_to_per_bus()
            Qmin_bus += self.hvdc_data.get_qmin_to_per_bus()

        # fix zero values
        Qmax_bus[Qmax_bus == 0] = 1e20
        Qmin_bus[Qmin_bus == 0] = -1e20

        return Qmax_bus, Qmin_bus

    def get_structure(self, structure_type) -> pd.DataFrame:
        """
        Get a DataFrame with the input.

        Arguments:

            **structure_type** (str): 'Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries' or 'Types'

        Returns:

            pandas DataFrame

        """

        if structure_type == 'Vbus':

            df = pd.DataFrame(data=self.Vbus, columns=['Voltage (p.u.)'], index=self.bus_data.bus_names)

        elif structure_type == 'Sbus':
            df = pd.DataFrame(data=self.Sbus, columns=['Power (p.u.)'], index=self.bus_data.bus_names)

        elif structure_type == 'Ibus':
            df = pd.DataFrame(data=self.Ibus, columns=['Current (p.u.)'], index=self.bus_data.bus_names)

        elif structure_type == 'Ybus':
            df = pd.DataFrame(data=self.Ybus.toarray(),
                              columns=self.bus_data.bus_names,
                              index=self.bus_data.bus_names)

        elif structure_type == 'Yf':
            df = pd.DataFrame(data=self.Yf.toarray(),
                              columns=self.bus_data.bus_names,
                              index=self.branch_data.branch_names)

        elif structure_type == 'Yt':
            df = pd.DataFrame(data=self.Yt.toarray(),
                              columns=self.bus_data.bus_names,
                              index=self.branch_data.branch_names)

        elif structure_type == 'Cf':
            df = pd.DataFrame(data=self.Cf.toarray(),
                              columns=self.bus_data.bus_names,
                              index=self.branch_data.branch_names)

        elif structure_type == 'Ct':
            df = pd.DataFrame(data=self.Ct.toarray(),
                              columns=self.bus_data.bus_names,
                              index=self.branch_data.branch_names)

        elif structure_type == 'Yshunt':
            df = pd.DataFrame(data=self.Yshunt, columns=['Shunt admittance (p.u.)'], index=self.bus_data.bus_names)

        elif structure_type == 'Yseries':
            df = pd.DataFrame(data=self.Yseries.toarray(),
                              columns=self.bus_data.bus_names,
                              index=self.bus_data.bus_names)

        elif structure_type == "B'":
            df = pd.DataFrame(data=self.B1.toarray(), columns=self.bus_data.bus_names, index=self.bus_data.bus_names)

        elif structure_type == "B''":
            df = pd.DataFrame(data=self.B2.toarray(), columns=self.bus_data.bus_names, index=self.bus_data.bus_names)

        elif structure_type == 'Types':
            df = pd.DataFrame(data=self.bus_types, columns=['Bus types'], index=self.bus_data.bus_names)

        elif structure_type == 'Qmin':
            df = pd.DataFrame(data=self.Qmin_bus, columns=['Qmin'], index=self.bus_data.bus_names)

        elif structure_type == 'Qmax':
            df = pd.DataFrame(data=self.Qmax_bus, columns=['Qmax'], index=self.bus_data.bus_names)

        elif structure_type == 'pq':
            df = pd.DataFrame(data=self.pq, columns=['pq'], index=self.bus_data.bus_names[self.pq])

        elif structure_type == 'pv':
            df = pd.DataFrame(data=self.pv, columns=['pv'], index=self.bus_data.bus_names[self.pv])

        elif structure_type == 'vd':
            df = pd.DataFrame(data=self.vd, columns=['vd'], index=self.bus_data.bus_names[self.vd])

        elif structure_type == 'pqpv':
            df = pd.DataFrame(data=self.pqpv, columns=['pqpv'], index=self.bus_data.bus_names[self.pqpv])

        elif structure_type == 'original_bus_idx':
            df = pd.DataFrame(data=self.original_bus_idx, columns=['original_bus_idx'], index=self.bus_data.bus_names)

        elif structure_type == 'original_branch_idx':
            df = pd.DataFrame(data=self.original_branch_idx,
                              columns=['original_branch_idx'],
                              index=self.branch_data.branch_names)

        elif structure_type == 'original_line_idx':
            df = pd.DataFrame(data=self.original_line_idx,
                              columns=['original_line_idx'],
                              index=self.line_data.line_names)

        elif structure_type == 'original_tr_idx':
            df = pd.DataFrame(data=self.original_tr_idx,
                              columns=['original_tr_idx'],
                              index=self.transformer_data.tr_names)

        elif structure_type == 'original_gen_idx':
            df = pd.DataFrame(data=self.original_gen_idx,
                              columns=['original_gen_idx'],
                              index=self.generator_data.generator_names)

        elif structure_type == 'Jacobian':

            J = Jacobian(self.Ybus, self.Vbus, self.Ibus, self.pq, self.pqpv)

            """
            J11 = dS_dVa[array([pvpq]).T, pvpq].real
            J12 = dS_dVm[array([pvpq]).T, pq].real
            J21 = dS_dVa[array([pq]).T, pvpq].imag
            J22 = dS_dVm[array([pq]).T, pq].imag
            """
            npq = len(self.pq)
            npv = len(self.pv)
            npqpv = npq + npv
            cols = ['dS/dVa'] * npqpv + ['dS/dVm'] * npq
            rows = cols
            df = pd.DataFrame(data=J.toarray(), columns=cols, index=rows)

        else:

            raise Exception('PF input: structure type not found')

        return df


def get_pf_island(circuit: SnapshotCircuit, bus_idx) -> "SnapshotCircuit":
    """
    Get the island corresponding to the given buses
    :param bus_idx: array of bus indices
    :return: SnapshotCircuit
    """

    # find the indices of the devices of the island
    line_idx = circuit.line_data.get_island(bus_idx)
    dc_line_idx = circuit.dc_line_data.get_island(bus_idx)
    tr_idx = circuit.transformer_data.get_island(bus_idx)
    vsc_idx = circuit.vsc_data.get_island(bus_idx)
    hvdc_idx = circuit.hvdc_data.get_island(bus_idx)
    br_idx = circuit.branch_data.get_island(bus_idx)

    load_idx = circuit.load_data.get_island(bus_idx)
    stagen_idx = circuit.static_generator_data.get_island(bus_idx)
    gen_idx = circuit.generator_data.get_island(bus_idx)
    batt_idx = circuit.battery_data.get_island(bus_idx)
    shunt_idx = circuit.shunt_data.get_island(bus_idx)

    nc = SnapshotCircuit(nbus=len(bus_idx),
                         nline=len(line_idx),
                         ndcline=len(dc_line_idx),
                         ntr=len(tr_idx),
                         nvsc=len(vsc_idx),
                         nhvdc=len(hvdc_idx),
                         nload=len(load_idx),
                         ngen=len(gen_idx),
                         nbatt=len(batt_idx),
                         nshunt=len(shunt_idx),
                         nstagen=len(stagen_idx),
                         sbase=circuit.Sbase)

    # set the original indices
    nc.original_bus_idx = bus_idx
    nc.original_branch_idx = br_idx
    nc.original_line_idx = line_idx
    nc.original_tr_idx = tr_idx
    nc.original_dc_line_idx = dc_line_idx
    nc.original_vsc_idx = vsc_idx
    nc.original_hvdc_idx = hvdc_idx
    nc.original_gen_idx = gen_idx
    nc.original_bat_idx = batt_idx
    nc.original_load_idx = load_idx
    nc.original_stagen_idx = stagen_idx
    nc.original_shunt_idx = shunt_idx

    # slice data
    nc.bus_data = circuit.bus_data.slice(bus_idx)
    nc.branch_data = circuit.branch_data.slice(br_idx, bus_idx)
    nc.line_data = circuit.line_data.slice(line_idx, bus_idx)
    nc.transformer_data = circuit.transformer_data.slice(tr_idx, bus_idx)
    nc.hvdc_data = circuit.hvdc_data.slice(hvdc_idx, bus_idx)
    nc.vsc_data = circuit.vsc_data.slice(vsc_idx, bus_idx)
    nc.dc_line_data = circuit.dc_line_data.slice(dc_line_idx, bus_idx)
    nc.load_data = circuit.load_data.slice(load_idx, bus_idx)
    nc.static_generator_data = circuit.static_generator_data.slice(stagen_idx, bus_idx)
    nc.battery_data = circuit.battery_data.slice(batt_idx, bus_idx)
    nc.generator_data = circuit.generator_data.slice(gen_idx, bus_idx)
    nc.shunt_data = circuit.shunt_data.slice(shunt_idx, bus_idx)

    return nc


def split_into_islands(numeric_circuit: SnapshotCircuit, ignore_single_node_islands=False) -> List[SnapshotCircuit]:
    """
    Split circuit into islands
    :param numeric_circuit: NumericCircuit instance
    :param ignore_single_node_islands: ignore islands composed of only one bus
    :return: List[NumericCircuit]
    """

    # compute the adjacency matrix
    A = tp.get_adjacency_matrix(C_branch_bus_f=numeric_circuit.branch_data.C_branch_bus_f,
                                C_branch_bus_t=numeric_circuit.branch_data.C_branch_bus_t,
                                branch_active=numeric_circuit.branch_data.branch_active,
                                bus_active=numeric_circuit.bus_data.bus_active)

    # find the matching islands
    idx_islands = tp.find_islands(A)

    if len(idx_islands) == 1:
        # numeric_circuit.compute_all()  # compute the internal magnitudes
        return [numeric_circuit]

    else:

        circuit_islands = list()  # type: List[SnapshotCircuit]

        for bus_idx in idx_islands:

            if ignore_single_node_islands:

                if len(bus_idx) > 1:
                    island = get_pf_island(numeric_circuit, bus_idx)
                    # island.compute_all()  # compute the internal magnitudes
                    circuit_islands.append(island)

            else:
                island = get_pf_island(numeric_circuit, bus_idx)
                # island.compute_all()  # compute the internal magnitudes
                circuit_islands.append(island)

        return circuit_islands


def compile_snapshot_circuit(circuit: MultiCircuit, apply_temperature=False,
                             branch_tolerance_mode=BranchImpedanceMode.Specified,
                             opf_results: OptimalPowerFlowResults = None) -> SnapshotCircuit:

    logger = Logger()

    # declare the numerical circuit
    nc = SnapshotCircuit(nbus=0,
                         nline=0,
                         ndcline=0,
                         ntr=0,
                         nvsc=0,
                         nhvdc=0,
                         nload=0,
                         ngen=0,
                         nbatt=0,
                         nshunt=0,
                         nstagen=0,
                         sbase=circuit.Sbase)

    bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}

    nc.bus_data = get_bus_data(circuit)
    nc.load_data = get_load_data(circuit, bus_dict, opf_results)
    nc.static_generator_data = get_static_generator_data(circuit, bus_dict)
    nc.generator_data = get_generator_data(circuit, bus_dict, nc.bus_data.Vbus, logger, opf_results)
    nc.battery_data = get_battery_data(circuit, bus_dict, nc.bus_data.Vbus, logger, opf_results)
    nc.shunt_data = get_shunt_data(circuit, bus_dict)

    nc.line_data = get_line_data(circuit, bus_dict, apply_temperature, branch_tolerance_mode)
    nc.transformer_data = get_transformer_data(circuit, bus_dict)
    nc.vsc_data = get_vsc_data(circuit, bus_dict)
    nc.dc_line_data = get_dc_line_data(circuit, bus_dict, apply_temperature, branch_tolerance_mode)
    nc.branch_data = get_branch_data(circuit, bus_dict, apply_temperature, branch_tolerance_mode)
    nc.hvdc_data = get_hvdc_data(circuit, bus_dict, nc.bus_data.bus_types)

    nc.consolidate_information()

    return nc


# def compile_snapshot_circuit_old(circuit: MultiCircuit, apply_temperature=False,
#                              branch_tolerance_mode=BranchImpedanceMode.Specified,
#                              opf_results: OptimalPowerFlowResults = None) -> SnapshotCircuit:
#     """
#     Compile the information of a circuit and generate the pertinent power flow islands
#     :param circuit: Circuit instance
#     :param apply_temperature:
#     :param branch_tolerance_mode:
#     :param impedance_tolerance:
#     :param opf_results: OptimalPowerFlowResults instance
#     :return: list of NumericIslands
#     """
#
#     logger = Logger()
#
#     bus_dictionary = dict()
#
#     # Element count
#     nbus = len(circuit.buses)
#     nload = 0
#     ngen = 0
#     n_batt = 0
#     nshunt = 0
#     nstagen = 0
#     for bus in circuit.buses:
#         nload += len(bus.loads)
#         ngen += len(bus.controlled_generators)
#         n_batt += len(bus.batteries)
#         nshunt += len(bus.shunts)
#         nstagen += len(bus.static_generators)
#
#     nline = len(circuit.lines)
#     ntr2w = len(circuit.transformers2w)
#     nvsc = len(circuit.vsc_converters)
#     nhvdc = len(circuit.hvdc_lines)
#     ndcline = len(circuit.dc_lines)
#
#     # declare the numerical circuit
#     nc = SnapshotCircuit(nbus=nbus,
#                          nline=nline,
#                          ndcline=ndcline,
#                          ntr=ntr2w,
#                          nvsc=nvsc,
#                          nhvdc=nhvdc,
#                          nload=nload,
#                          ngen=ngen,
#                          nbatt=n_batt,
#                          nshunt=nshunt,
#                          nstagen=nstagen,
#                          sbase=circuit.Sbase,
#                          apply_temperature=apply_temperature,
#                          branch_tolerance_mode=branch_tolerance_mode)
#
#     # buses and it's connected elements (loads, generators, etc...)
#     i_ld = 0
#     i_gen = 0
#     i_batt = 0
#     i_sh = 0
#     i_stagen = 0
#     for i, bus in enumerate(circuit.buses):
#
#         # bus parameters
#         nc.bus_names[i] = bus.name
#         nc.bus_active[i] = bus.active
#         nc.bus_types[i] = bus.determine_bus_type().value
#
#         # Add buses dictionary entry
#         bus_dictionary[bus] = i
#
#         for elm in bus.loads:
#             nc.load_names[i_ld] = elm.name
#             nc.load_active[i_ld] = elm.active
#
#             if opf_results is None:
#                 nc.load_s[i_ld] = complex(elm.P, elm.Q)
#             else:
#                 nc.load_s[i_ld] = complex(elm.P, elm.Q) - opf_results.load_shedding[i_ld]
#
#             nc.C_bus_load[i, i_ld] = 1
#             i_ld += 1
#
#         for elm in bus.static_generators:
#             nc.static_generator_names[i_stagen] = elm.name
#             nc.static_generator_active[i_stagen] = elm.active
#             nc.static_generator_s[i_stagen] = complex(elm.P, elm.Q)
#
#             nc.C_bus_static_generator[i, i_stagen] = 1
#             i_stagen += 1
#
#         for elm in bus.controlled_generators:
#             nc.generator_names[i_gen] = elm.name
#             nc.generator_pf[i_gen] = elm.Pf
#             nc.generator_v[i_gen] = elm.Vset
#             nc.generator_qmin[i_gen] = elm.Qmin
#             nc.generator_qmax[i_gen] = elm.Qmax
#             nc.generator_active[i_gen] = elm.active
#             nc.generator_controllable[i_gen] = elm.is_controlled
#             nc.generator_installed_p[i_gen] = elm.Snom
#
#             if opf_results is None:
#                 nc.generator_p[i_gen] = elm.P
#             else:
#                 nc.generator_p[i_gen] = opf_results.generators_power[i_gen] - opf_results.generation_shedding[i_gen]
#
#             nc.C_bus_gen[i, i_gen] = 1
#
#             if nc.Vbus[i].real == 1.0:
#                 nc.Vbus[i] = complex(elm.Vset, 0)
#             elif elm.Vset != nc.Vbus[i]:
#                 logger.append('Different set points at ' + bus.name + ': ' + str(elm.Vset) + ' !=' + str(nc.Vbus[i]))
#             i_gen += 1
#
#         for elm in bus.batteries:
#             nc.battery_names[i_batt] = elm.name
#
#             nc.battery_pf[i_batt] = elm.Pf
#             nc.battery_v[i_batt] = elm.Vset
#             nc.battery_qmin[i_batt] = elm.Qmin
#             nc.battery_qmax[i_batt] = elm.Qmax
#             nc.battery_active[i_batt] = elm.active
#             nc.battery_controllable[i_batt] = elm.is_controlled
#             nc.battery_installed_p[i_batt] = elm.Snom
#
#             if opf_results is None:
#                 nc.battery_p[i_batt] = elm.P
#             else:
#                 nc.battery_p[i_batt] = opf_results.battery_power[i_batt]
#
#             nc.C_bus_batt[i, i_batt] = 1
#
#             if nc.Vbus[i].real == 1.0:
#                 nc.Vbus[i] = complex(elm.Vset, 0)
#             elif elm.Vset != nc.Vbus[i]:
#                 logger.append('Different set points at ' + bus.name + ': ' + str(elm.Vset) + ' !=' + str(nc.Vbus[i]))
#
#             i_batt += 1
#
#         for elm in bus.shunts:
#             nc.shunt_names[i_sh] = elm.name
#             nc.shunt_active[i_sh] = elm.active
#             nc.shunt_admittance[i_sh] = complex(elm.G, elm.B)
#
#             nc.C_bus_shunt[i, i_sh] = 1
#             i_sh += 1
#
#     # Compile the lines
#     for i, elm in enumerate(circuit.lines):
#         # generic stuff
#         nc.branch_names[i] = elm.name
#         nc.branch_active[i] = elm.active
#         nc.branch_rates[i] = elm.rate
#         f = bus_dictionary[elm.bus_from]
#         t = bus_dictionary[elm.bus_to]
#         nc.C_branch_bus_f[i, f] = 1
#         nc.C_branch_bus_t[i, t] = 1
#         nc.F[i] = f
#         nc.T[i] = t
#
#         # impedance
#         nc.line_names[i] = elm.name
#         nc.line_R[i] = elm.R
#         nc.line_X[i] = elm.X
#         nc.line_B[i] = elm.B
#         nc.line_impedance_tolerance[i] = elm.tolerance
#         nc.C_line_bus[i, f] = 1
#         nc.C_line_bus[i, t] = 1
#
#         # Thermal correction
#         nc.line_temp_base[i] = elm.temp_base
#         nc.line_temp_oper[i] = elm.temp_oper
#         nc.line_alpha[i] = elm.alpha
#
#     # 2-winding transformers
#     for i, elm in enumerate(circuit.transformers2w):
#         ii = i + nline
#
#         # generic stuff
#         f = bus_dictionary[elm.bus_from]
#         t = bus_dictionary[elm.bus_to]
#
#         nc.branch_names[ii] = elm.name
#         nc.branch_active[ii] = elm.active
#         nc.branch_rates[ii] = elm.rate
#         nc.C_branch_bus_f[ii, f] = 1
#         nc.C_branch_bus_t[ii, t] = 1
#         nc.F[ii] = f
#         nc.T[ii] = t
#
#         # impedance
#         nc.tr_names[i] = elm.name
#         nc.tr_R[i] = elm.R
#         nc.tr_X[i] = elm.X
#         nc.tr_G[i] = elm.G
#         nc.tr_B[i] = elm.B
#
#         nc.C_tr_bus[i, f] = 1
#         nc.C_tr_bus[i, t] = 1
#
#         # tap changer
#         nc.tr_tap_mod[i] = elm.tap_module
#         nc.tr_tap_ang[i] = elm.angle
#         nc.tr_is_bus_to_regulated[i] = elm.bus_to_regulated
#         nc.tr_tap_position[i] = elm.tap_changer.tap
#         nc.tr_min_tap[i] = elm.tap_changer.min_tap
#         nc.tr_max_tap[i] = elm.tap_changer.max_tap
#         nc.tr_tap_inc_reg_up[i] = elm.tap_changer.inc_reg_up
#         nc.tr_tap_inc_reg_down[i] = elm.tap_changer.inc_reg_down
#         nc.tr_vset[i] = elm.vset
#         nc.tr_control_mode[i] = elm.control_mode
#
#         nc.tr_bus_to_regulated_idx[i] = t if elm.bus_to_regulated else f
#
#         # virtual taps for transformers where the connection voltage is off
#         nc.tr_tap_f[i], nc.tr_tap_t[i] = elm.get_virtual_taps()
#
#     # VSC
#     for i, elm in enumerate(circuit.vsc_converters):
#         ii = i + nline + ntr2w
#
#         # generic stuff
#         f = bus_dictionary[elm.bus_from]
#         t = bus_dictionary[elm.bus_to]
#
#         nc.branch_names[ii] = elm.name
#         nc.branch_active[ii] = elm.active
#         nc.branch_rates[ii] = elm.rate
#         nc.C_branch_bus_f[ii, f] = 1
#         nc.C_branch_bus_t[ii, t] = 1
#         nc.F[ii] = f
#         nc.T[ii] = t
#
#         # vsc values
#         nc.vsc_names[i] = elm.name
#         nc.vsc_R1[i] = elm.R1
#         nc.vsc_X1[i] = elm.X1
#         nc.vsc_G0[i] = elm.G0
#         nc.vsc_Beq[i] = elm.Beq
#         nc.vsc_m[i] = elm.m
#         nc.vsc_theta[i] = elm.theta
#         nc.vsc_Inom[i] = (elm.rate / nc.Sbase) / np.abs(nc.Vbus[f])
#         nc.vsc_Pset[i] = elm.Pset
#         nc.vsc_Qset[i] = elm.Qset
#         nc.vsc_Vac_set[i] = elm.Vac_set
#         nc.vsc_Vdc_set[i] = elm.Vdc_set
#         nc.vsc_control_mode[i] = elm.control_mode
#
#         nc.C_vsc_bus[i, f] = 1
#         nc.C_vsc_bus[i, t] = 1
#
#     # DC-lines
#     for i, elm in enumerate(circuit.dc_lines):
#         ii = i + nline + ntr2w + nvsc
#
#         # generic stuff
#         f = bus_dictionary[elm.bus_from]
#         t = bus_dictionary[elm.bus_to]
#
#         nc.branch_names[ii] = elm.name
#         nc.branch_active[ii] = elm.active
#         nc.branch_rates[ii] = elm.rate
#         nc.C_branch_bus_f[ii, f] = 1
#         nc.C_branch_bus_t[ii, t] = 1
#         nc.F[ii] = f
#         nc.T[ii] = t
#
#         # dc line values
#         nc.dc_line_names[i] = elm.name
#         nc.dc_line_R[i] = elm.R
#         nc.dc_line_impedance_tolerance[i] = elm.tolerance
#         nc.C_dc_line_bus[i, f] = 1
#         nc.C_dc_line_bus[i, t] = 1
#         nc.dc_F[i] = f
#         nc.dc_T[i] = t
#
#         # Thermal correction
#         nc.dc_line_temp_base[i] = elm.temp_base
#         nc.dc_line_temp_oper[i] = elm.temp_oper
#         nc.dc_line_alpha[i] = elm.alpha
#
#     # HVDC
#     for i, elm in enumerate(circuit.hvdc_lines):
#         ii = i + nline + ntr2w + nvsc
#
#         # generic stuff
#         f = bus_dictionary[elm.bus_from]
#         t = bus_dictionary[elm.bus_to]
#
#         # hvdc values
#         nc.hvdc_names[i] = elm.name
#         nc.hvdc_active[i] = elm.active
#         nc.hvdc_rate[i] = elm.rate
#
#         nc.hvdc_Pf[i], nc.hvdc_Pt[i] = elm.get_from_and_to_power()
#
#         nc.hvdc_loss_factor[i] = elm.loss_factor
#         nc.hvdc_Vset_f[i] = elm.Vset_f
#         nc.hvdc_Vset_t[i] = elm.Vset_t
#         nc.hvdc_Qmin_f[i] = elm.Qmin_f
#         nc.hvdc_Qmax_f[i] = elm.Qmax_f
#         nc.hvdc_Qmin_t[i] = elm.Qmin_t
#         nc.hvdc_Qmax_t[i] = elm.Qmax_t
#
#         # hack the bus types to believe they are PV
#         nc.bus_types[f] = BusMode.PV.value
#         nc.bus_types[t] = BusMode.PV.value
#
#         # the the bus-hvdc line connectivity
#         nc.C_hvdc_bus_f[i, f] = 1
#         nc.C_hvdc_bus_t[i, t] = 1
#
#     # consolidate the information
#     nc.consolidate_information()
#
#     return nc
