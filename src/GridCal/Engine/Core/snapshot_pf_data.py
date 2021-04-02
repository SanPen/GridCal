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
import GridCal.Engine.Core.topology as tp
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian
from GridCal.Engine.Core.common_functions import compile_types
from GridCal.Engine.Simulations.sparse_solve import get_sparse_type
import GridCal.Engine.Core.DataStructures as ds
import GridCal.Engine.Core.admittance_matrices as ycalc
from GridCal.Engine.Devices.enumerations import TransformerControlType, ConverterControlType

sparse_type = get_sparse_type()


class SnapshotData:

    def __init__(self, nbus, nline, ndcline, ntr, nvsc, nupfc, nhvdc, nload, ngen, nbatt, nshunt, nstagen, sbase, ntime=1):
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
        self.nupfc = nupfc
        self.nhvdc = nhvdc

        self.nload = nload
        self.ngen = ngen
        self.nbatt = nbatt
        self.nshunt = nshunt
        self.nstagen = nstagen
        self.ntime = ntime
        self.nbr = nline + ntr + nvsc + ndcline

        self.Sbase = sbase

        self.any_control = False
        self.iPfsh = list()  # indices of the branches controlling Pf flow with theta sh
        self.iQfma = list()  # indices of the branches controlling Qf with ma
        self.iBeqz = list()  # indices of the branches when forcing the Qf flow to zero (aka "the zero condition")
        self.iBeqv = list()  # indices of the branches when controlling Vf with Beq
        self.iVtma = list()  # indices of the branches when controlling Vt with ma
        self.iQtma = list()  # indices of the branches controlling the Qt flow with ma
        self.iPfdp = list()  # indices of the drop-Vm converters controlling the power flow with theta sh
        self.iPfdp_va = list()  # indices of the drop-Va converters controlling the power flow with theta sh
        self.iVscL = list()  # indices of the converters
        self.VfBeqbus = list()  # indices of the buses where Vf is controlled by Beq
        self.Vtmabus = list()  # indices of the buses where Vt is controlled by ma

        # --------------------------------------------------------------------------------------------------------------
        # Data structures
        # --------------------------------------------------------------------------------------------------------------
        self.bus_data = ds.BusData(nbus=nbus, ntime=ntime)
        self.branch_data = ds.BranchData(nbr=self.nbr, nbus=nbus, ntime=ntime)
        self.line_data = ds.LinesData(nline=nline, nbus=nbus, ntime=ntime)
        self.dc_line_data = ds.DcLinesData(ndcline=ndcline, nbus=nbus, ntime=ntime)
        self.transformer_data = ds.TransformerData(ntr=ntr, nbus=nbus, ntime=ntime)
        self.vsc_data = ds.VscData(nvsc=nvsc, nbus=nbus, ntime=ntime)
        self.upfc_data = ds.UpfcData(nelm=nupfc, nbus=nbus, ntime=ntime)
        self.hvdc_data = ds.HvdcData(nhvdc=nhvdc, nbus=nbus, ntime=ntime)

        self.load_data = ds.LoadData(nload=nload, nbus=nbus, ntime=ntime)
        self.static_generator_data = ds.StaticGeneratorData(nstagen=nstagen, nbus=nbus, ntime=ntime)
        self.battery_data = ds.BatteryData(nbatt=nbatt, nbus=nbus, ntime=ntime)
        self.generator_data = ds.GeneratorData(ngen=ngen, nbus=nbus, ntime=ntime)
        self.shunt_data = ds.ShuntData(nshunt=nshunt, nbus=nbus, ntime=ntime)

        self.original_bus_idx = np.arange(self.nbus)
        self.original_branch_idx = np.arange(self.nbr)
        self.original_line_idx = np.arange(self.nline)
        self.original_tr_idx = np.arange(self.ntr)
        self.original_dc_line_idx = np.arange(self.ndcline)
        self.original_vsc_idx = np.arange(self.nvsc)
        self.original_upfc_idx = np.arange(self.nupfc)
        self.original_hvdc_idx = np.arange(self.nhvdc)
        self.original_gen_idx = np.arange(self.ngen)
        self.original_bat_idx = np.arange(self.nbatt)
        self.original_load_idx = np.arange(self.nload)
        self.original_stagen_idx = np.arange(self.nstagen)
        self.original_shunt_idx = np.arange(self.nshunt)
        self.original_time_idx = np.arange(self.ntime)

        # --------------------------------------------------------------------------------------------------------------
        # Internal variables filled on demand, to be ready to consume once computed
        # --------------------------------------------------------------------------------------------------------------

        self.Cf_ = None
        self.Ct_ = None

        self.Vbus_ = None
        self.Sbus_ = None
        self.Ibus_ = None
        self.Yshunt_from_devices_ = None

        self.Qmax_bus_ = None
        self.Qmin_bus_ = None
        self.Bmax_bus_ = None
        self.Bmin_bus_ = None

        self.Admittances = None

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
                                     'original_bat_idx',
                                     'iPfsh',
                                     'iQfma',
                                     'iBeqz',
                                     'iBeqv',
                                     'iVtma',
                                     'iQtma',
                                     'iPfdp',
                                     'iVscL',
                                     'VfBeqbus',
                                     'Vtmabus'
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
        self.nupfc = len(self.upfc_data)
        self.nbr = self.nline + self.ntr + self.nvsc + self.ndcline + self.nupfc

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
        self.upfc_data.C_elm_bus = self.upfc_data.C_elm_bus.tocsc()

        self.load_data.C_bus_load = self.load_data.C_bus_load.tocsr()
        self.battery_data.C_bus_batt = self.battery_data.C_bus_batt.tocsr()
        self.generator_data.C_bus_gen = self.generator_data.C_bus_gen.tocsr()
        self.shunt_data.C_bus_shunt = self.shunt_data.C_bus_shunt.tocsr()
        self.static_generator_data.C_bus_static_generator = self.static_generator_data.C_bus_static_generator.tocsr()

        self.bus_data.bus_installed_power = self.generator_data.get_installed_power_per_bus()
        self.bus_data.bus_installed_power += self.battery_data.get_installed_power_per_bus()

        self.determine_control_indices()

    def re_calc_admittance_matrices(self, tap_module, t=0, idx=None):
        """
        Fast admittance recombination
        :param tap_module: transformer taps (if idx is provided, must have the same length as idx,
                           otherwise the length must be the number of branches)
        :param t: time index, 0 by default
        :param idx: Indices of the branches where the tap belongs,
                    if None assumes that the tap sizes is equal to the number of branches
        :return:
        """
        if idx is None:
            Ybus_, Yf_, Yt_ = self.Admittances.modify_taps(self.branch_data.m[:, t], tap_module)
        else:
            Ybus_, Yf_, Yt_ = self.Admittances.modify_taps(self.branch_data.m[np.ix_(idx, t)], tap_module)

        self.Admittances.Ybus = Ybus_
        self.Admittances.Yf = Yf_
        self.Admittances.Yt = Yt_

    def determine_control_indices(self):
        """
        This function fills in the lists of indices to control different magnitudes

        :returns idx_sh, idx_qz, idx_vf, idx_vt, idx_qt, VfBeqbus, Vtmabus

        VSC Control modes:

        in the paper's scheme:
        from -> DC
        to   -> AC

        |   Mode    |   const.1 |   const.2 |   type    |
        -------------------------------------------------
        |   1       |   theta   |   Vac     |   I       |
        |   2       |   Pf      |   Qac     |   I       |
        |   3       |   Pf      |   Vac     |   I       |
        -------------------------------------------------
        |   4       |   Vdc     |   Qac     |   II      |
        |   5       |   Vdc     |   Vac     |   II      |
        -------------------------------------------------
        |   6       | Vdc droop |   Qac     |   III     |
        |   7       | Vdc droop |   Vac     |   III     |
        -------------------------------------------------

        Indices where each control goes:
        mismatch  →  |  ∆Pf	Qf	Q@f Q@t	∆Qt
        variable  →  |  Ɵsh	Beq	m	m	Beq
        Indices   →  |  Ish	Iqz	Ivf	Ivt	Iqt
        ------------------------------------
        VSC 1	     |  -	1	-	1	-   |   AC voltage control (voltage “to”)
        VSC 2	     |  1	1	-	-	1   |   Active and reactive power control
        VSC 3	     |  1	1	-	1	-   |   Active power and AC voltage control
        VSC 4	     |  -	-	1	-	1   |   Dc voltage and Reactive power flow control
        VSC 5	     |  -	-	-	1	1   |   Ac and Dc voltage control
        ------------------------------------
        Transformer 0|	-	-	-	-	-   |   Fixed transformer
        Transformer 1|	1	-	-	-	-   |   Phase shifter → controls power
        Transformer 2|	-	-	1	-	-   |   Control the voltage at the “from” side
        Transformer 3|	-	-	-	1	-   |   Control the voltage at the “to” side
        Transformer 4|	1	-	1	-	-   |   Control the power flow and the voltage at the “from” side
        Transformer 5|	1	-	-	1	-   |   Control the power flow and the voltage at the “to” side
        ------------------------------------

        """

        # indices in the global branch scheme
        self.iPfsh = list()  # indices of the branches controlling Pf flow with theta sh
        self.iQfma = list()  # indices of the branches controlling Qf with ma
        self.iBeqz = list()  # indices of the branches when forcing the Qf flow to zero (aka "the zero condition")
        self.iBeqv = list()  # indices of the branches when controlling Vf with Beq
        self.iVtma = list()  # indices of the branches when controlling Vt with ma
        self.iQtma = list()  # indices of the branches controlling the Qt flow with ma
        self.iPfdp = list()  # indices of the drop converters controlling the power flow with theta sh
        self.iVscL = list()  # indices of the converters

        self.any_control = False

        for k, tpe in enumerate(self.branch_data.control_mode):

            if tpe == TransformerControlType.fixed:
                pass

            elif tpe == TransformerControlType.Pt:
                self.iPfsh.append(k)
                self.any_control = True

            elif tpe == TransformerControlType.Qt:
                self.iQtma.append(k)
                self.any_control = True

            elif tpe == TransformerControlType.PtQt:
                self.iPfsh.append(k)
                self.iQtma.append(k)
                self.any_control = True

            elif tpe == TransformerControlType.Vt:
                self.iVtma.append(k)
                self.any_control = True

            elif tpe == TransformerControlType.PtVt:
                self.iPfsh.append(k)
                self.iVtma.append(k)
                self.any_control = True

            # VSC ------------------------------------------------------------------------------------------------------
            elif tpe == ConverterControlType.type_0_free:  # 1a:Free
                self.iBeqz.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_1:  # 1:Vac
                self.iVtma.append(k)
                self.iBeqz.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_2:  # 2:Pdc+Qac

                self.iPfsh.append(k)
                self.iQtma.append(k)
                self.iBeqz.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_3:  # 3:Pdc+Vac
                self.iPfsh.append(k)
                self.iVtma.append(k)
                self.iBeqz.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_II_4:  # 4:Vdc+Qac
                self.iBeqv.append(k)
                self.iQtma.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_II_5:  # 5:Vdc+Vac
                self.iBeqv.append(k)
                self.iVtma.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_6:  # 6:Droop+Qac
                self.iPfdp.append(k)
                self.iQtma.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_7:  # 4a:Droop-slack
                self.iPfdp.append(k)
                self.iVtma.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_8:  # 6:Droop+Qac
                self.iPfdp_va.append(k)
                self.iQtma.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_9:  # 4a:Droop-slack
                self.iPfdp_va.append(k)
                self.iVtma.append(k)

                self.iVscL.append(k)
                self.any_control = True

            elif tpe == 0:
                pass  # required for the no-control case

            else:
                raise Exception('Unknown control type:' + str(tpe))

        # VfBeqbus_sh = list()
        # for k, is_controlled in enumerate(self.shunt_data.get_controlled_per_bus()):
        #     if is_controlled:
        #         VfBeqbus_sh.append(k)
        #         self.any_control = True

        # FUBM- Saves the "from" bus identifier for Vf controlled by Beq
        #  (Converters type II for Vdc control)
        # self.VfBeqbus = np.unique(np.r_[VfBeqbus_sh, self.F[self.iBeqv]])
        # self.VfBeqbus.sort()
        self.VfBeqbus = self.F[self.iBeqv]

        # FUBM- Saves the "to"   bus identifier for Vt controlled by ma
        #  (Converters and Transformers)
        self.Vtmabus = self.T[self.iVtma]

        self.iPfsh = np.array(self.iPfsh, dtype=np.int)
        self.iQfma = np.array(self.iQfma, dtype=np.int)
        self.iBeqz = np.array(self.iBeqz, dtype=np.int)
        self.iBeqv = np.array(self.iBeqv, dtype=np.int)
        self.iVtma = np.array(self.iVtma, dtype=np.int)
        self.iQtma = np.array(self.iQtma, dtype=np.int)
        self.iPfdp = np.array(self.iPfdp, dtype=np.int)
        self.iPfdp_va = np.array(self.iPfdp_va, dtype=np.int)
        self.iVscL = np.array(self.iVscL, dtype=np.int)

    @property
    def line_idx(self):
        return slice(0, self.nline, 1)

    @property
    def transformer_idx(self):
        return slice(self.nline, self.nline + self.ntr, 1)

    @property
    def vsc_idx(self):
        return slice(self.nline + self.ntr, self.nline + self.ntr + self.nvsc, 1)

    @property
    def dc_line_idx(self):
        return slice(self.nline + self.ntr + self.nvsc, self.nline + self.ntr + self.nvsc + self.ndcline, 1)

    @property
    def Vbus(self):

        if self.Vbus_ is None:
            self.Vbus_ = self.bus_data.Vbus.copy()

        return self.Vbus_[:, 0]

    @property
    def Sbus(self):

        if self.Sbus_ is None:
            self.Sbus_ = self.get_injections(normalize=True)

        return self.Sbus_[:, 0]

    @property
    def Ibus(self):

        if self.Ibus_ is None:
            self.Ibus_ = np.zeros(len(self.bus_data), dtype=complex)

        return self.Ibus_

    @property
    def Rates(self):
        return self.branch_data.branch_rates[:, 0]

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
    def Bmax_bus(self):

        if self.Bmax_bus_ is None:
            self.Bmax_bus_, self.Bmin_bus_ = self.compute_susceptance_limits()

        return self.Bmax_bus_

    @property
    def Bmin_bus(self):

        if self.Bmin_bus_ is None:
            self.Bmax_bus_, self.Bmin_bus_ = self.compute_susceptance_limits()

        return self.Bmin_bus_

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
    def load_names(self):
        return self.load_data.load_names

    @property
    def generator_names(self):
        return self.generator_data.generator_names

    @property
    def battery_names(self):
        return self.battery_data.battery_names

    @property
    def tr_names(self):
        return self.transformer_data.tr_names

    @property
    def hvdc_names(self):
        return self.hvdc_data.names

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
        return self.branch_data.branch_rates[:, 0]

    @property
    def hvdc_Pf(self):
        return self.hvdc_data.Pf[:, 0]

    @property
    def hvdc_Pt(self):
        return self.hvdc_data.Pt[:, 0]

    @property
    def hvdc_loading(self):
        return self.hvdc_data.get_loading()[:, 0]

    @property
    def hvdc_losses(self):
        return self.hvdc_data.get_losses()[:, 0]

    @property
    def Cf(self):

        # compute on demand and store
        if self.Cf_ is None:
            self.Cf_, self.Ct_ = ycalc.compute_connectivity(branch_active=self.branch_data.branch_active[:, 0],
                                                            Cf_=self.branch_data.C_branch_bus_f,
                                                            Ct_=self.branch_data.C_branch_bus_t)
        return self.Cf_

    @property
    def Ct(self):

        # compute on demand and store
        if self.Ct_ is None:
            self.Cf_, self.Ct_ = ycalc.compute_connectivity(branch_active=self.branch_data.branch_active[:, 0],
                                                            Cf_=self.branch_data.C_branch_bus_f,
                                                            Ct_=self.branch_data.C_branch_bus_t)
        return self.Ct_

    @property
    def Ybus(self):

        # compute admittances on demand
        if self.Admittances is None:

            self.Admittances = ycalc.compute_admittances(R=self.branch_data.R,
                                                         X=self.branch_data.X,
                                                         G=self.branch_data.G,
                                                         B=self.branch_data.B,
                                                         k=self.branch_data.k,
                                                         m=self.branch_data.m[:, 0],
                                                         mf=self.branch_data.tap_f,
                                                         mt=self.branch_data.tap_t,
                                                         theta=self.branch_data.theta[:, 0],
                                                         Beq=self.branch_data.Beq[:, 0],
                                                         Cf=self.Cf,
                                                         Ct=self.Ct,
                                                         G0=self.branch_data.G0[:, 0],
                                                         If=np.zeros(len(self.branch_data)),
                                                         a=self.branch_data.a,
                                                         b=self.branch_data.b,
                                                         c=self.branch_data.c,
                                                         Yshunt_bus=self.Yshunt_from_devices[:, 0])
        return self.Admittances.Ybus

    @property
    def Yf(self):

        if self.Admittances is None:
            x = self.Ybus  # call the constructor of Yf

        return self.Admittances.Yf

    @property
    def Yt(self):

        if self.Admittances is None:
            x = self.Ybus  # call the constructor of Yt

        return self.Admittances.Yt

    @property
    def Yseries(self):

        # compute admittances on demand
        if self.Yseries_ is None:

            self.Yseries_, self.Yshunt_ = ycalc.compute_split_admittances(R=self.branch_data.R,
                                                                          X=self.branch_data.X,
                                                                          G=self.branch_data.G,
                                                                          B=self.branch_data.B,
                                                                          k=self.branch_data.k,
                                                                          m=self.branch_data.m[:, 0],
                                                                          mf=self.branch_data.tap_f,
                                                                          mt=self.branch_data.tap_t,
                                                                          theta=self.branch_data.theta[:, 0],
                                                                          Beq=self.branch_data.Beq[:, 0],
                                                                          Cf=self.Cf,
                                                                          Ct=self.Ct,
                                                                          G0=self.branch_data.G0[:, 0],
                                                                          If=np.zeros(len(self.branch_data)),
                                                                          a=self.branch_data.a,
                                                                          b=self.branch_data.b,
                                                                          c=self.branch_data.c,
                                                                          Yshunt_bus=self.Yshunt_from_devices[:, 0])
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
                                                                          m=self.branch_data.m[:, 0],
                                                                          mf=self.branch_data.vf_set[:, 0],
                                                                          mt=self.branch_data.vt_set[:, 0],
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
                                                                    m=self.branch_data.m[:, 0],
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
            self.vd_, self.pq_, self.pv_, self.pqpv_ = compile_types(Sbus=self.Sbus,
                                                                     types=self.bus_data.bus_types)

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
        :return: Qmax_bus, Qmin_bus in per unit
        """
        # generators
        Qmax_bus = self.generator_data.get_qmax_per_bus()
        Qmin_bus = self.generator_data.get_qmin_per_bus()

        if self.nbatt > 0:
            # batteries
            Qmax_bus += self.battery_data.get_qmax_per_bus()
            Qmin_bus += self.battery_data.get_qmin_per_bus()

        if self.nshunt > 0:
            # shunts
            Qmax_bus += self.shunt_data.get_b_max_per_bus()
            Qmin_bus += self.shunt_data.get_b_min_per_bus()

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

        return Qmax_bus / self.Sbase, Qmin_bus / self.Sbase

    def compute_susceptance_limits(self):

        Bmin = self.shunt_data.get_b_min_per_bus() / self.Sbase
        Bmax = self.shunt_data.get_b_max_per_bus() / self.Sbase

        return Bmax, Bmin

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

        elif structure_type == 'original_bat_idx':
            df = pd.DataFrame(data=self.original_bat_idx,
                              columns=['original_bat_idx'],
                              index=self.battery_data.battery_names)

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

        elif structure_type == 'iPfsh':
            df = pd.DataFrame(data=self.iPfsh, columns=['iPfsh'], index=self.branch_data.branch_names[self.iPfsh])

        elif structure_type == 'iQfma':
            df = pd.DataFrame(data=self.iQfma, columns=['iQfma'], index=self.branch_data.branch_names[self.iQfma])

        elif structure_type == 'iBeqz':
            df = pd.DataFrame(data=self.iBeqz, columns=['iBeqz'], index=self.branch_data.branch_names[self.iBeqz])

        elif structure_type == 'iBeqv':
            df = pd.DataFrame(data=self.iBeqv, columns=['iBeqv'], index=self.branch_data.branch_names[self.iBeqv])

        elif structure_type == 'iVtma':
            df = pd.DataFrame(data=self.iVtma, columns=['iVtma'], index=self.branch_data.branch_names[self.iVtma])

        elif structure_type == 'iQtma':
            df = pd.DataFrame(data=self.iQtma, columns=['iQtma'], index=self.branch_data.branch_names[self.iQtma])

        elif structure_type == 'iPfdp':
            df = pd.DataFrame(data=self.iPfdp, columns=['iPfdp'], index=self.branch_data.branch_names[self.iPfdp])

        elif structure_type == 'iVscL':
            df = pd.DataFrame(data=self.iVscL, columns=['iVscL'], index=self.branch_data.branch_names[self.iVscL])

        elif structure_type == 'VfBeqbus':
            df = pd.DataFrame(data=self.VfBeqbus, columns=['VfBeqbus'], index=self.bus_data.bus_names[self.VfBeqbus])

        elif structure_type == 'Vtmabus':
            df = pd.DataFrame(data=self.Vtmabus, columns=['Vtmabus'], index=self.bus_data.bus_names[self.Vtmabus])
        else:

            raise Exception('PF input: structure type not found' +  str(structure_type))

        return df

    def get_island(self, bus_idx, time_idx=None) -> "SnapshotData":
        """
        Get the island corresponding to the given buses
        :param bus_idx: array of bus indices
        :param time_idx: array of time indices (or None for all time indices)
        :return: SnapshotData
        """

        # find the indices of the devices of the island
        line_idx = self.line_data.get_island(bus_idx)
        dc_line_idx = self.dc_line_data.get_island(bus_idx)
        tr_idx = self.transformer_data.get_island(bus_idx)
        vsc_idx = self.vsc_data.get_island(bus_idx)
        upfc_idx = self.upfc_data.get_island(bus_idx)
        hvdc_idx = self.hvdc_data.get_island(bus_idx)
        br_idx = self.branch_data.get_island(bus_idx)

        load_idx = self.load_data.get_island(bus_idx)
        stagen_idx = self.static_generator_data.get_island(bus_idx)
        gen_idx = self.generator_data.get_island(bus_idx)
        batt_idx = self.battery_data.get_island(bus_idx)
        shunt_idx = self.shunt_data.get_island(bus_idx)

        nc = SnapshotData(nbus=len(bus_idx),
                          nline=len(line_idx),
                          ndcline=len(dc_line_idx),
                          ntr=len(tr_idx),
                          nvsc=len(vsc_idx),
                          nupfc=len(upfc_idx),
                          nhvdc=len(hvdc_idx),
                          nload=len(load_idx),
                          ngen=len(gen_idx),
                          nbatt=len(batt_idx),
                          nshunt=len(shunt_idx),
                          nstagen=len(stagen_idx),
                          sbase=self.Sbase)

        # set the original indices
        nc.original_bus_idx = bus_idx
        nc.original_branch_idx = br_idx
        nc.original_line_idx = line_idx
        nc.original_tr_idx = tr_idx
        nc.original_dc_line_idx = dc_line_idx
        nc.original_vsc_idx = vsc_idx
        nc.original_upfc_idx = upfc_idx
        nc.original_hvdc_idx = hvdc_idx
        nc.original_gen_idx = gen_idx
        nc.original_bat_idx = batt_idx
        nc.original_load_idx = load_idx
        nc.original_stagen_idx = stagen_idx
        nc.original_shunt_idx = shunt_idx

        # slice data
        nc.bus_data = self.bus_data.slice(bus_idx, time_idx)
        nc.branch_data = self.branch_data.slice(br_idx, bus_idx, time_idx)
        nc.line_data = self.line_data.slice(line_idx, bus_idx, time_idx)
        nc.transformer_data = self.transformer_data.slice(tr_idx, bus_idx, time_idx)
        nc.hvdc_data = self.hvdc_data.slice(hvdc_idx, bus_idx, time_idx)
        nc.vsc_data = self.vsc_data.slice(vsc_idx, bus_idx, time_idx)
        nc.dc_line_data = self.dc_line_data.slice(dc_line_idx, bus_idx, time_idx)
        nc.load_data = self.load_data.slice(load_idx, bus_idx, time_idx)
        nc.static_generator_data = self.static_generator_data.slice(stagen_idx, bus_idx, time_idx)
        nc.battery_data = self.battery_data.slice(batt_idx, bus_idx, time_idx)
        nc.generator_data = self.generator_data.slice(gen_idx, bus_idx, time_idx)
        nc.shunt_data = self.shunt_data.slice(shunt_idx, bus_idx, time_idx)

        return nc

    def split_into_islands(self, ignore_single_node_islands=False) -> List["SnapshotData"]:
        """
        Split circuit into islands
        :param numeric_circuit: NumericCircuit instance
        :param ignore_single_node_islands: ignore islands composed of only one bus
        :return: List[NumericCircuit]
        """

        # compute the adjacency matrix
        A = tp.get_adjacency_matrix(C_branch_bus_f=self.Cf,
                                    C_branch_bus_t=self.Ct,
                                    branch_active=self.branch_data.branch_active[:, 0],
                                    bus_active=self.bus_data.bus_active[:, 0])

        # find the matching islands
        idx_islands = tp.find_islands(A)

        if len(idx_islands) == 1:
            # numeric_circuit.compute_all()  # compute the internal magnitudes
            return [self]

        else:

            circuit_islands = list()  # type: List[SnapshotData]

            for bus_idx in idx_islands:

                if ignore_single_node_islands:

                    if len(bus_idx) > 1:
                        island = self.get_island(bus_idx)
                        # island.compute_all()  # compute the internal magnitudes
                        circuit_islands.append(island)

                else:
                    island = self.get_island(bus_idx)
                    # island.compute_all()  # compute the internal magnitudes
                    circuit_islands.append(island)

            return circuit_islands


def compile_snapshot_circuit(circuit: MultiCircuit, apply_temperature=False,
                             branch_tolerance_mode=BranchImpedanceMode.Specified,
                             opf_results = None) -> SnapshotData:
    """

    :param circuit:
    :param apply_temperature:
    :param branch_tolerance_mode:
    :param opf_results:
    :return:
    """

    logger = Logger()

    # declare the numerical circuit
    nc = SnapshotData(nbus=0,
                      nline=0,
                      ndcline=0,
                      ntr=0,
                      nvsc=0,
                      nupfc=0,
                      nhvdc=0,
                      nload=0,
                      ngen=0,
                      nbatt=0,
                      nshunt=0,
                      nstagen=0,
                      sbase=circuit.Sbase)

    bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}

    nc.bus_data = ds.circuit_to_data.get_bus_data(circuit)
    nc.load_data = ds.circuit_to_data.get_load_data(circuit, bus_dict, opf_results)
    nc.static_generator_data = ds.circuit_to_data.get_static_generator_data(circuit, bus_dict)
    nc.generator_data = ds.circuit_to_data.get_generator_data(circuit, bus_dict, nc.bus_data.Vbus, logger, opf_results)
    nc.battery_data = ds.circuit_to_data.get_battery_data(circuit, bus_dict, nc.bus_data.Vbus, logger, opf_results)
    nc.shunt_data = ds.circuit_to_data.get_shunt_data(circuit, bus_dict, nc.bus_data.Vbus, logger)
    nc.line_data = ds.circuit_to_data.get_line_data(circuit, bus_dict, apply_temperature, branch_tolerance_mode)
    nc.transformer_data = ds.circuit_to_data.get_transformer_data(circuit, bus_dict)
    nc.vsc_data = ds.circuit_to_data.get_vsc_data(circuit, bus_dict)
    nc.upfc_data = ds.circuit_to_data.get_upfc_data(circuit, bus_dict)
    nc.dc_line_data = ds.circuit_to_data.get_dc_line_data(circuit, bus_dict, apply_temperature, branch_tolerance_mode)
    nc.upfc_data = ds.circuit_to_data.get_upfc_data(circuit, bus_dict)

    nc.branch_data = ds.circuit_to_data.get_branch_data(circuit, bus_dict, nc.bus_data.Vbus,
                                                        apply_temperature, branch_tolerance_mode)

    nc.hvdc_data = ds.circuit_to_data.get_hvdc_data(circuit, bus_dict, nc.bus_data.bus_types)

    nc.consolidate_information()

    return nc
