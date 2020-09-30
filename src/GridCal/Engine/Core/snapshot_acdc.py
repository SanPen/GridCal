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
import scipy.sparse as sp
from typing import List

from GridCal.Engine.basic_structures import Logger
import GridCal.Engine.Core.topology as tp
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.Devices.enumerations import ConverterControlType, TransformerControlType
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian
from GridCal.Engine.Core.common_functions import compile_types
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Simulations.sparse_solve import get_sparse_type

sparse_type = get_sparse_type()


class AcDcSnapshotCircuit:

    def __init__(self, nbus, nline, ndcline, ntr, nvsc, nload, ngen, nbatt, nshunt, nstagen, sbase,
                 apply_temperature=False, branch_tolerance_mode: BranchImpedanceMode = BranchImpedanceMode.Specified):
        """

        :param nbus: number of buses
        :param nline: number of lines
        :param ntr: number of transformers
        :param nvsc:
        :param nhvdc:
        :param nload:
        :param ngen:
        :param nbatt:
        :param nshunt:
        """

        self.nbus = nbus
        self.nline = nline
        self.ndcline = ndcline
        self.ntr = ntr
        self.nvsc = nvsc
        self.nload = nload
        self.ngen = ngen
        self.nbatt = nbatt
        self.nshunt = nshunt
        self.nstagen = nstagen

        self.Sbase = sbase

        self.apply_temperature = apply_temperature
        self.branch_tolerance_mode = branch_tolerance_mode

        # bus ----------------------------------------------------------------------------------------------------------
        self.bus_names = np.empty(nbus, dtype=object)
        self.bus_active = np.ones(nbus, dtype=int)
        self.Vbus = np.ones(nbus, dtype=complex)
        self.bus_types = np.empty(nbus, dtype=int)
        self.bus_installed_power = np.zeros(nbus, dtype=float)
        self.bus_is_dc = np.empty(nbus, dtype=bool)

        # branch common ------------------------------------------------------------------------------------------------
        self.nbr = nline + ntr + nvsc + ndcline  # exclude the HVDC model since it is not a real branch

        self.branch_names = np.empty(self.nbr, dtype=object)
        self.branch_active = np.zeros(self.nbr, dtype=int)
        self.F = np.zeros(self.nbr, dtype=int)  # indices of the "from" buses
        self.T = np.zeros(self.nbr, dtype=int)  # indices of the "to" buses
        self.branch_rates = np.zeros(self.nbr, dtype=float)

        self.R = np.zeros(self.nbr, dtype=float)
        self.X = np.zeros(self.nbr, dtype=float)
        self.G = np.zeros(self.nbr, dtype=float)
        self.B = np.zeros(self.nbr, dtype=float)
        self.m = np.ones(self.nbr, dtype=float)
        self.k = np.ones(self.nbr, dtype=float)
        self.theta = np.zeros(self.nbr, dtype=float)
        self.Beq = np.zeros(self.nbr, dtype=float)
        self.G0 = np.zeros(self.nbr, dtype=float)

        self.tap_t = np.ones(self.nbr, dtype=float)
        self.tap_f = np.ones(self.nbr, dtype=float)

        self.Inom = np.ones(self.nbr) * 9999
        self.Pset = np.zeros(self.nbr)
        self.Qset = np.zeros(self.nbr)
        self.vf_set = np.ones(self.nbr)
        self.vt_set = np.ones(self.nbr)
        self.Kdp = np.ones(self.nbr)
        self.control_mode = np.zeros(self.nbr, dtype=object)

        self.C_branch_bus_f = sp.lil_matrix((self.nbr, nbus), dtype=int)  # connectivity branch with their "from" bus
        self.C_branch_bus_t = sp.lil_matrix((self.nbr, nbus), dtype=int)  # connectivity branch with their "to" bus

        self.C_line_bus = sp.lil_matrix((nline, nbus), dtype=int)  # this ons is just for splitting islands
        self.C_dc_line_bus = sp.lil_matrix((ndcline, nbus), dtype=int)  # this ons is just for splitting islands
        self.C_tr_bus = sp.lil_matrix((ntr, nbus), dtype=int)  # this ons is just for splitting islands
        self.C_vsc_bus = sp.lil_matrix((nvsc, nbus), dtype=int)  # this ons is just for splitting islands

        # load ---------------------------------------------------------------------------------------------------------
        self.load_names = np.empty(nload, dtype=object)
        self.load_active = np.zeros(nload, dtype=bool)
        self.load_s = np.zeros(nload, dtype=complex)

        self.C_bus_load = sp.lil_matrix((nbus, nload), dtype=int)

        # static generators --------------------------------------------------------------------------------------------
        self.static_generator_names = np.empty(nstagen, dtype=object)
        self.static_generator_active = np.zeros(nstagen, dtype=bool)
        self.static_generator_s = np.zeros(nstagen, dtype=complex)

        self.C_bus_static_generator = sp.lil_matrix((nbus, nstagen), dtype=int)

        # battery ------------------------------------------------------------------------------------------------------
        self.battery_names = np.empty(nbatt, dtype=object)
        self.battery_active = np.zeros(nbatt, dtype=bool)
        self.battery_controllable = np.zeros(nbatt, dtype=bool)
        self.battery_installed_p = np.zeros(nbatt)
        self.battery_p = np.zeros(nbatt)
        self.battery_pf = np.zeros(nbatt)
        self.battery_v = np.zeros(nbatt)
        self.battery_qmin = np.zeros(nbatt)
        self.battery_qmax = np.zeros(nbatt)

        self.C_bus_batt = sp.lil_matrix((nbus, nbatt), dtype=int)

        # generator ----------------------------------------------------------------------------------------------------
        self.generator_names = np.empty(ngen, dtype=object)
        self.generator_active = np.zeros(ngen, dtype=bool)
        self.generator_controllable = np.zeros(ngen, dtype=bool)
        self.generator_installed_p = np.zeros(ngen)
        self.generator_p = np.zeros(ngen)
        self.generator_pf = np.zeros(ngen)
        self.generator_v = np.zeros(ngen)
        self.generator_qmin = np.zeros(ngen)
        self.generator_qmax = np.zeros(ngen)

        self.C_bus_gen = sp.lil_matrix((nbus, ngen), dtype=int)

        # shunt --------------------------------------------------------------------------------------------------------
        self.shunt_names = np.empty(nshunt, dtype=object)
        self.shunt_active = np.zeros(nshunt, dtype=bool)
        self.shunt_admittance = np.zeros(nshunt, dtype=complex)

        self.C_bus_shunt = sp.lil_matrix((nbus, nshunt), dtype=int)

        # ---------------------------------------------------------------------------------------------------------------
        # Results
        # --------------------------------------------------------------------------------------------------------------

        self.Sbus = np.zeros(self.nbus, dtype=complex)
        self.Ibus = np.zeros(self.nbus, dtype=complex)
        self.Yshunt_from_devices = np.zeros(self.nbus, dtype=complex)

        self.Qmax_bus = np.zeros(self.nbus)
        self.Qmin_bus = np.zeros(self.nbus)

        self.original_bus_idx = np.arange(self.nbus)
        self.original_branch_idx = np.arange(self.nbr)
        self.original_line_idx = np.arange(self.nline)
        self.original_tr_idx = np.arange(self.ntr)
        self.original_gen_idx = np.arange(self.ngen)
        self.original_bat_idx = np.arange(self.nbatt)

        self.pq = list()
        self.pv = list()
        self.vd = list()
        self.pqpv = list()

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

    def get_injections(self):
        """
        Compute the power
        :return: nothing, the results are stored in the class
        """

        # load
        Sbus = - self.C_bus_load * (self.load_s * self.load_active)  # MW

        # static generators
        Sbus += self.C_bus_static_generator * (self.static_generator_s * self.static_generator_active)

        # generators
        Sbus += self.C_bus_gen * (self.generator_p * self.generator_active)

        # battery
        Sbus += self.C_bus_batt * (self.battery_p * self.battery_active)

        Sbus /= self.Sbase

        return Sbus

    def consolidate(self):
        """
        Consolidates the information of this object
        :return:
        """
        self.C_branch_bus_f = self.C_branch_bus_f.tocsc()
        self.C_branch_bus_t = self.C_branch_bus_t.tocsc()

        self.C_line_bus = self.C_line_bus.tocsc()
        self.C_dc_line_bus = self.C_line_bus.tocsc()
        self.C_tr_bus = self.C_tr_bus.tocsc()
        self.C_vsc_bus = self.C_vsc_bus.tocsc()

        self.C_bus_load = self.C_bus_load.tocsr()
        self.C_bus_batt = self.C_bus_batt.tocsr()
        self.C_bus_gen = self.C_bus_gen.tocsr()
        self.C_bus_shunt = self.C_bus_shunt.tocsr()
        self.C_bus_static_generator = self.C_bus_static_generator.tocsr()

        self.bus_installed_power = self.C_bus_gen * self.generator_installed_p
        self.bus_installed_power += self.C_bus_batt * self.battery_installed_p

    def get_generator_injections(self):
        """
        Compute the active and reactive power of non-controlled generators (assuming all)
        :return:
        """
        pf2 = np.power(self.generator_pf, 2.0)
        pf_sign = (self.generator_pf + 1e-20) / np.abs(self.generator_pf + 1e-20)
        Q = pf_sign * self.generator_p * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
        return self.generator_p + 1.0j * Q

    def get_battery_injections(self):
        """
        Compute the active and reactive power of non-controlled batteries (assuming all)
        :return:
        """
        pf2 = np.power(self.battery_pf, 2.0)
        pf_sign = (self.battery_pf + 1e-20) / np.abs(self.battery_pf + 1e-20)
        Q = pf_sign * self.battery_p * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
        return self.battery_p + 1.0j * Q

    def compute_injections(self):
        """
        Compute the power
        :return: nothing, the results are stored in the class
        """

        # load
        self.Sbus = - self.C_bus_load * (self.load_s * self.load_active)  # MW

        # static generators
        self.Sbus += self.C_bus_static_generator * (self.static_generator_s * self.static_generator_active)

        # generators
        self.Sbus += self.C_bus_gen * (self.get_generator_injections() * self.generator_active)

        # battery
        self.Sbus += self.C_bus_batt * (self.get_battery_injections() * self.battery_active)

        self.Sbus /= self.Sbase

    def compute_reactive_power_limits(self):
        # generators
        self.Qmax_bus = self.C_bus_gen * (self.generator_qmax * self.generator_active)
        self.Qmin_bus = self.C_bus_gen * (self.generator_qmin * self.generator_active)

        if self.nbatt > 0:
            # batteries
            self.Qmax_bus += self.C_bus_batt * (self.battery_qmax * self.battery_active)
            self.Qmin_bus += self.C_bus_batt * (self.battery_qmin * self.battery_active)

        # fix zero values
        self.Qmax_bus[self.Qmax_bus == 0] = 1e20
        self.Qmin_bus[self.Qmin_bus == 0] = -1e20

    def consolidate(self):
        """
        Computes the parameters given the filled-in information
        :return:
        """
        self.compute_injections()

        self.vd, self.pq, self.pv, self.pqpv = compile_types(Sbus=self.Sbus, types=self.bus_types)

        self.compute_reactive_power_limits()

    def get_structure(self, structure_type) -> pd.DataFrame:
        """
        Get a DataFrame with the input.

        Arguments:

            **structure_type** (str): 'Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries' or 'Types'

        Returns:

            pandas DataFrame

        """

        if structure_type == 'Vbus':

            df = pd.DataFrame(data=self.Vbus, columns=['Voltage (p.u.)'], index=self.bus_names)

        elif structure_type == 'Sbus':
            df = pd.DataFrame(data=self.Sbus, columns=['Power (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ibus':
            df = pd.DataFrame(data=self.Ibus, columns=['Current (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ybus':
            df = pd.DataFrame(data=self.Ybus.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Yf':
            df = pd.DataFrame(data=self.Yf.toarray(), columns=self.bus_names, index=self.branch_names)

        elif structure_type == 'Yt':
            df = pd.DataFrame(data=self.Yt.toarray(), columns=self.bus_names, index=self.branch_names)

        elif structure_type == 'Cf':
            df = pd.DataFrame(data=self.C_branch_bus_f.toarray(), columns=self.bus_names, index=self.branch_names)

        elif structure_type == 'Ct':
            df = pd.DataFrame(data=self.C_branch_bus_t.toarray(), columns=self.bus_names, index=self.branch_names)

        elif structure_type == 'Yshunt':
            df = pd.DataFrame(data=self.Yshunt, columns=['Shunt admittance (p.u.)'], index=self.bus_names)

        elif structure_type == 'Yseries':
            df = pd.DataFrame(data=self.Yseries.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == "B'":
            df = pd.DataFrame(data=self.B1.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == "B''":
            df = pd.DataFrame(data=self.B2.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Types':
            df = pd.DataFrame(data=self.bus_types, columns=['Bus types'], index=self.bus_names)

        elif structure_type == 'Qmin':
            df = pd.DataFrame(data=self.Qmin_bus, columns=['Qmin'], index=self.bus_names)

        elif structure_type == 'Qmax':
            df = pd.DataFrame(data=self.Qmax_bus, columns=['Qmax'], index=self.bus_names)

        elif structure_type == 'pq':
            df = pd.DataFrame(data=self.pq, columns=['pq'], index=self.bus_names[self.pq])

        elif structure_type == 'pv':
            df = pd.DataFrame(data=self.pv, columns=['pv'], index=self.bus_names[self.pv])

        elif structure_type == 'vd':
            df = pd.DataFrame(data=self.vd, columns=['vd'], index=self.bus_names[self.vd])

        elif structure_type == 'pqpv':
            df = pd.DataFrame(data=self.pqpv, columns=['pqpv'], index=self.bus_names[self.pqpv])

        elif structure_type == 'original_bus_idx':
            df = pd.DataFrame(data=self.original_bus_idx, columns=['original_bus_idx'], index=self.bus_names)

        elif structure_type == 'original_branch_idx':
            df = pd.DataFrame(data=self.original_branch_idx, columns=['original_branch_idx'], index=self.branch_names)

        elif structure_type == 'original_line_idx':
            df = pd.DataFrame(data=self.original_line_idx, columns=['original_line_idx'], index=self.line_names)

        elif structure_type == 'original_tr_idx':
            df = pd.DataFrame(data=self.original_tr_idx, columns=['original_tr_idx'], index=self.tr_names)

        elif structure_type == 'original_gen_idx':
            df = pd.DataFrame(data=self.original_gen_idx, columns=['original_gen_idx'], index=self.generator_names)

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


def get_acdc_pf_island(circuit: AcDcSnapshotCircuit, bus_idx) -> "AcDcSnapshotCircuit":
    """
    Get the island corresponding to the given buses
    :param bus_idx: array of bus indices
    :return: SnapshotCircuit
    """

    # find the indices of the devices of the island
    br_idx = tp.get_elements_of_the_island(circuit.C_branch_bus_f + circuit.C_branch_bus_t, bus_idx)
    line_idx = tp.get_elements_of_the_island(circuit.C_line_bus, bus_idx)
    dc_line_idx = tp.get_elements_of_the_island(circuit.C_dc_line_bus, bus_idx)
    tr_idx = tp.get_elements_of_the_island(circuit.C_tr_bus, bus_idx)
    vsc_idx = tp.get_elements_of_the_island(circuit.C_vsc_bus, bus_idx)

    load_idx = tp.get_elements_of_the_island(circuit.C_bus_load.T, bus_idx)
    stagen_idx = tp.get_elements_of_the_island(circuit.C_bus_static_generator.T, bus_idx)
    gen_idx = tp.get_elements_of_the_island(circuit.C_bus_gen.T, bus_idx)
    batt_idx = tp.get_elements_of_the_island(circuit.C_bus_batt.T, bus_idx)
    shunt_idx = tp.get_elements_of_the_island(circuit.C_bus_shunt.T, bus_idx)

    nc = AcDcSnapshotCircuit(nbus=len(bus_idx),
                             nline=len(line_idx),
                             ndcline=len(dc_line_idx),
                             ntr=len(tr_idx),
                             nvsc=len(vsc_idx),
                             nload=len(load_idx),
                             ngen=len(gen_idx),
                             nbatt=len(batt_idx),
                             nshunt=len(shunt_idx),
                             nstagen=len(stagen_idx),
                             sbase=circuit.Sbase,
                             apply_temperature=circuit.apply_temperature,
                             branch_tolerance_mode=circuit.branch_tolerance_mode)

    nc.original_bus_idx = bus_idx
    nc.original_branch_idx = br_idx

    nc.original_line_idx = line_idx
    nc.original_tr_idx = tr_idx
    nc.original_gen_idx = gen_idx
    nc.original_bat_idx = batt_idx

    # bus ----------------------------------------------------------------------------------------------------------
    nc.bus_names = circuit.bus_names[bus_idx]
    nc.bus_active = circuit.bus_active[bus_idx]
    nc.Vbus = circuit.Vbus[bus_idx]
    nc.bus_types = circuit.bus_types[bus_idx]

    # branch common ------------------------------------------------------------------------------------------------
    nc.branch_names = circuit.branch_names[br_idx]
    nc.branch_active = circuit.branch_active[br_idx]
    nc.F = circuit.F[br_idx]
    nc.T = circuit.T[br_idx]
    nc.branch_rates = circuit.branch_rates[br_idx]
    nc.C_branch_bus_f = circuit.C_branch_bus_f[np.ix_(br_idx, bus_idx)]
    nc.C_branch_bus_t = circuit.C_branch_bus_t[np.ix_(br_idx, bus_idx)]

    nc.R = circuit.R[br_idx]
    nc.X = circuit.X[br_idx]
    nc.G = circuit.G[br_idx]
    nc.B = circuit.B[br_idx]
    nc.m = circuit.m[br_idx]
    nc.theta = circuit.theta[br_idx]
    nc.Beq = circuit.Beq[br_idx]
    nc.G0 = circuit.G0[br_idx]

    nc.tap_f = circuit.tap_f[br_idx]
    nc.tap_t = circuit.tap_t[br_idx]

    nc.Inom = circuit.Inom[br_idx]
    nc.Pset = circuit.Pset[br_idx]
    nc.Qset = circuit.Qset[br_idx]
    nc.vf_set = circuit.vt_set[br_idx]
    nc.vt_set = circuit.vf_set[br_idx]
    nc.control_mode = circuit.control_mode[br_idx]

    # load ---------------------------------------------------------------------------------------------------------
    nc.load_names = circuit.load_names[load_idx]
    nc.load_active = circuit.load_active[load_idx]
    nc.load_s = circuit.load_s[load_idx]

    nc.C_bus_load = circuit.C_bus_load[np.ix_(bus_idx, load_idx)]

    # static generators --------------------------------------------------------------------------------------------
    nc.static_generator_names = circuit.static_generator_names[stagen_idx]
    nc.static_generator_active = circuit.static_generator_active[stagen_idx]
    nc.static_generator_s = circuit.static_generator_s[stagen_idx]

    nc.C_bus_static_generator = circuit.C_bus_static_generator[np.ix_(bus_idx, stagen_idx)]

    # battery ------------------------------------------------------------------------------------------------------
    nc.battery_names = circuit.battery_names[batt_idx]
    nc.battery_active = circuit.battery_active[batt_idx]
    nc.battery_controllable = circuit.battery_controllable[batt_idx]
    nc.battery_p = circuit.battery_p[batt_idx]
    nc.battery_pf = circuit.battery_pf[batt_idx]
    nc.battery_v = circuit.battery_v[batt_idx]
    nc.battery_qmin = circuit.battery_qmin[batt_idx]
    nc.battery_qmax = circuit.battery_qmax[batt_idx]

    nc.C_bus_batt = circuit.C_bus_batt[np.ix_(bus_idx, batt_idx)]

    # generator ----------------------------------------------------------------------------------------------------
    nc.generator_names = circuit.generator_names[gen_idx]
    nc.generator_active = circuit.generator_active[gen_idx]
    nc.generator_controllable = circuit.generator_controllable[gen_idx]
    nc.generator_p = circuit.generator_p[gen_idx]
    nc.generator_pf = circuit.generator_pf[gen_idx]
    nc.generator_v = circuit.generator_v[gen_idx]
    nc.generator_qmin = circuit.generator_qmin[gen_idx]
    nc.generator_qmax = circuit.generator_qmax[gen_idx]

    nc.C_bus_gen = circuit.C_bus_gen[np.ix_(bus_idx, gen_idx)]

    # shunt --------------------------------------------------------------------------------------------------------
    nc.shunt_names = circuit.shunt_names[shunt_idx]
    nc.shunt_active = circuit.shunt_active[shunt_idx]
    nc.shunt_admittance = circuit.shunt_admittance[shunt_idx]

    nc.C_bus_shunt = circuit.C_bus_shunt[np.ix_(bus_idx, shunt_idx)]

    return nc


def split_into_islands_acdc(numeric_circuit: AcDcSnapshotCircuit,
                            ignore_single_node_islands=False) -> List[AcDcSnapshotCircuit]:
    """
    Split circuit into islands
    :param numeric_circuit: NumericCircuit instance
    :param ignore_single_node_islands: ignore islands composed of only one bus
    :return: List[NumericCircuit]
    """

    # compute the adjacency matrix
    A = tp.get_adjacency_matrix(C_branch_bus_f=numeric_circuit.C_branch_bus_f,
                                C_branch_bus_t=numeric_circuit.C_branch_bus_t,
                                branch_active=numeric_circuit.branch_active,
                                bus_active=numeric_circuit.bus_active)

    # find the matching islands
    idx_islands = tp.find_islands(A)

    if len(idx_islands) == 1:
        numeric_circuit.consolidate()  # compute the internal magnitudes
        return [numeric_circuit]

    else:

        circuit_islands = list()  # type: List[AcDcSnapshotCircuit]

        for bus_idx in idx_islands:

            if ignore_single_node_islands:

                if len(bus_idx) > 1:
                    island = get_acdc_pf_island(numeric_circuit, bus_idx)
                    island.consolidate()  # compute the internal magnitudes
                    circuit_islands.append(island)

            else:
                island = get_acdc_pf_island(numeric_circuit, bus_idx)
                island.consolidate()  # compute the internal magnitudes
                circuit_islands.append(island)

        return circuit_islands


def compile_acdc_snapshot_circuit(circuit: MultiCircuit, apply_temperature=False,
                                  branch_tolerance_mode=BranchImpedanceMode.Specified,
                                  opf_results: OptimalPowerFlowResults = None) -> AcDcSnapshotCircuit:
    """
    Compile the information of a circuit and generate the pertinent power flow islands
    :param circuit: Circuit instance
    :param apply_temperature:
    :param branch_tolerance_mode:
    :param opf_results: OptimalPowerFlowResults instance
    :return: list of NumericIslands
    """

    logger = Logger()

    bus_dictionary = dict()

    # Element count
    nbus = len(circuit.buses)
    nload = 0
    ngen = 0
    n_batt = 0
    nshunt = 0
    nstagen = 0
    for bus in circuit.buses:
        nload += len(bus.loads)
        ngen += len(bus.controlled_generators)
        n_batt += len(bus.batteries)
        nshunt += len(bus.shunts)
        nstagen += len(bus.static_generators)

    nline = len(circuit.lines)
    ntr2w = len(circuit.transformers2w)
    nvsc = len(circuit.vsc_converters)
    # nhvdc = len(circuit.hvdc_lines)
    ndcline = len(circuit.dc_lines)

    # declare the numerical circuit
    nc = AcDcSnapshotCircuit(nbus=nbus,
                             nline=nline,
                             ndcline=ndcline,
                             ntr=ntr2w,
                             nvsc=nvsc,
                             nload=nload,
                             ngen=ngen,
                             nbatt=n_batt,
                             nshunt=nshunt,
                             nstagen=nstagen,
                             sbase=circuit.Sbase,
                             apply_temperature=apply_temperature,
                             branch_tolerance_mode=branch_tolerance_mode)

    # buses and it's connected elements (loads, generators, etc...)
    i_ld = 0
    i_gen = 0
    i_batt = 0
    i_sh = 0
    i_stagen = 0
    for i, bus in enumerate(circuit.buses):

        # bus parameters
        nc.bus_names[i] = bus.name
        nc.bus_active[i] = bus.active
        nc.bus_types[i] = bus.determine_bus_type().value

        # Add buses dictionary entry
        bus_dictionary[bus] = i

        for elm in bus.loads:
            nc.load_names[i_ld] = elm.name
            nc.load_active[i_ld] = elm.active

            if opf_results is None:
                nc.load_s[i_ld] = complex(elm.P, elm.Q)
            else:
                nc.load_s[i_ld] = complex(elm.P, elm.Q) - opf_results.load_shedding[i_ld]

            nc.C_bus_load[i, i_ld] = 1
            i_ld += 1

        for elm in bus.static_generators:
            nc.static_generator_names[i_stagen] = elm.name
            nc.static_generator_active[i_stagen] = elm.active
            nc.static_generator_s[i_stagen] = complex(elm.P, elm.Q)

            nc.C_bus_static_generator[i, i_stagen] = 1
            i_stagen += 1

        for elm in bus.controlled_generators:
            nc.generator_names[i_gen] = elm.name
            nc.generator_pf[i_gen] = elm.Pf
            nc.generator_v[i_gen] = elm.Vset
            nc.generator_qmin[i_gen] = elm.Qmin
            nc.generator_qmax[i_gen] = elm.Qmax
            nc.generator_active[i_gen] = elm.active
            nc.generator_controllable[i_gen] = elm.is_controlled
            nc.generator_installed_p[i_gen] = elm.Snom

            if opf_results is None:
                nc.generator_p[i_gen] = elm.P
            else:
                nc.generator_p[i_gen] = opf_results.generators_power[i_gen] - opf_results.generation_shedding[i_gen]

            nc.C_bus_gen[i, i_gen] = 1

            if nc.Vbus[i].real == 1.0:
                nc.Vbus[i] = complex(elm.Vset, 0)
            elif elm.Vset != nc.Vbus[i]:
                logger.append('Different set points at ' + bus.name + ': ' + str(elm.Vset) + ' !=' + str(nc.Vbus[i]))
            i_gen += 1

        for elm in bus.batteries:
            nc.battery_names[i_batt] = elm.name

            nc.battery_pf[i_batt] = elm.Pf
            nc.battery_v[i_batt] = elm.Vset
            nc.battery_qmin[i_batt] = elm.Qmin
            nc.battery_qmax[i_batt] = elm.Qmax
            nc.battery_active[i_batt] = elm.active
            nc.battery_controllable[i_batt] = elm.is_controlled
            nc.battery_installed_p[i_batt] = elm.Snom

            if opf_results is None:
                nc.battery_p[i_batt] = elm.P
            else:
                nc.battery_p[i_batt] = opf_results.battery_power[i_batt]

            nc.C_bus_batt[i, i_batt] = 1

            if nc.Vbus[i].real == 1.0:
                nc.Vbus[i] = complex(elm.Vset, 0)
            elif elm.Vset != nc.Vbus[i]:
                logger.append('Different set points at ' + bus.name + ': ' + str(elm.Vset) + ' !=' + str(nc.Vbus[i]))

            i_batt += 1

        for elm in bus.shunts:
            nc.shunt_names[i_sh] = elm.name
            nc.shunt_active[i_sh] = elm.active
            nc.shunt_admittance[i_sh] = complex(elm.G, elm.B)

            nc.C_bus_shunt[i, i_sh] = 1
            i_sh += 1

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        nc.branch_names[i] = elm.name
        nc.branch_active[i] = elm.active
        nc.branch_rates[i] = elm.rate
        f = bus_dictionary[elm.bus_from]
        t = bus_dictionary[elm.bus_to]
        nc.C_branch_bus_f[i, f] = 1
        nc.C_branch_bus_t[i, t] = 1
        nc.F[i] = f
        nc.T[i] = t

        nc.R[i] = elm.R
        nc.X[i] = elm.X
        nc.B[i] = elm.B

        nc.C_line_bus[i, f] = 1
        nc.C_line_bus[i, t] = 1

    # 2-winding transformers
    for i, elm in enumerate(circuit.transformers2w):
        ii = i + nline

        # generic stuff
        f = bus_dictionary[elm.bus_from]
        t = bus_dictionary[elm.bus_to]

        nc.branch_names[ii] = elm.name
        nc.branch_active[ii] = elm.active
        nc.branch_rates[ii] = elm.rate
        nc.C_branch_bus_f[ii, f] = 1
        nc.C_branch_bus_t[ii, t] = 1
        nc.F[ii] = f
        nc.T[ii] = t

        nc.R[ii] = elm.R
        nc.X[ii] = elm.X
        nc.G[ii] = elm.G
        nc.B[ii] = elm.B
        nc.m[ii] = elm.tap_module
        nc.theta[ii] = elm.angle
        nc.control_mode[ii] = elm.control_mode
        nc.tap_f[ii], nc.tap_t[ii] = elm.get_virtual_taps()

        if elm.control_mode == TransformerControlType.v_to:
            nc.Vbus[t] = elm.vset

        elif elm.control_mode == TransformerControlType.power_v_to:  # 2a:Vdc
            nc.Vbus[t] = elm.vset

        nc.C_tr_bus[i, f] = 1
        nc.C_tr_bus[i, t] = 1

    # VSC
    for i, elm in enumerate(circuit.vsc_converters):
        ii = i + nline + ntr2w

        # generic stuff
        f = bus_dictionary[elm.bus_from]
        t = bus_dictionary[elm.bus_to]

        nc.branch_names[ii] = elm.name
        nc.branch_active[ii] = elm.active
        nc.branch_rates[ii] = elm.rate
        nc.C_branch_bus_f[ii, f] = 1
        nc.C_branch_bus_t[ii, t] = 1
        nc.F[ii] = f
        nc.T[ii] = t

        # vsc values
        nc.R[ii] = elm.R1
        nc.X[ii] = elm.X1
        nc.G0[ii] = elm.G0
        nc.Beq[ii] = elm.Beq
        nc.m[ii] = elm.m
        nc.k[ii] = 1.0  # 0.8660254037844386  # sqrt(3)/2
        nc.theta[ii] = elm.theta
        nc.Inom[ii] = (elm.rate / nc.Sbase) / nc.Vbus[f]
        nc.Pset[ii] = elm.Pset
        nc.Qset[ii] = elm.Qset
        nc.Kdp[ii] = elm.kdp
        nc.vf_set[ii] = elm.Vac_set
        nc.vt_set[ii] = elm.Vdc_set
        nc.control_mode[ii] = elm.control_mode

        if elm.control_mode == ConverterControlType.type_1_vac:  # 1d:Vac
            nc.Vbus[t] = elm.Vac_set
        elif elm.control_mode == ConverterControlType.type_2_vdc:  # 2a:Vdc
            nc.Vbus[f] = elm.Vdc_set

        nc.C_vsc_bus[i, f] = 1
        nc.C_vsc_bus[i, t] = 1

    # DC-lines
    for i, elm in enumerate(circuit.dc_lines):
        ii = i + nline + ntr2w + nvsc

        # generic stuff
        f = bus_dictionary[elm.bus_from]
        t = bus_dictionary[elm.bus_to]

        nc.branch_names[ii] = elm.name
        nc.branch_active[ii] = elm.active
        nc.branch_rates[ii] = elm.rate
        nc.C_branch_bus_f[ii, f] = 1
        nc.C_branch_bus_t[ii, t] = 1
        nc.F[ii] = f
        nc.T[ii] = t

        # dc line values
        nc.R[ii] = elm.R

        nc.C_dc_line_bus[i, f] = 1
        nc.C_dc_line_bus[i, t] = 1

    # HVDC
    # for i, elm in enumerate(circuit.hvdc_lines):
    #     ii = i + nline + ntr2w + nvsc
    #
    #     # generic stuff
    #     f = bus_dictionary[elm.bus_from]
    #     t = bus_dictionary[elm.bus_to]
    #
    #     # hvdc values
    #     nc.hvdc_names[i] = elm.name
    #     nc.hvdc_active[i] = elm.active
    #     nc.hvdc_rate[i] = elm.rate
    #
    #     nc.hvdc_Pf[i], nc.hvdc_Pt[i] = elm.get_from_and_to_power()
    #
    #     nc.hvdc_loss_factor[i] = elm.loss_factor
    #     nc.hvdc_Vset_f[i] = elm.Vset_f
    #     nc.hvdc_Vset_t[i] = elm.Vset_t
    #     nc.hvdc_Qmin_f[i] = elm.Qmin_f
    #     nc.hvdc_Qmax_f[i] = elm.Qmax_f
    #     nc.hvdc_Qmin_t[i] = elm.Qmin_t
    #     nc.hvdc_Qmax_t[i] = elm.Qmax_t
    #
    #     # hack the bus types to believe they are PV
    #     nc.bus_types[f] = BusMode.PV.value
    #     nc.bus_types[t] = BusMode.PV.value
    #
    #     # the the bus-hvdc line connectivity
    #     nc.C_hvdc_bus_f[i, f] = 1
    #     nc.C_hvdc_bus_t[i, t] = 1

    # consolidate the information
    nc.consolidate()

    return nc
