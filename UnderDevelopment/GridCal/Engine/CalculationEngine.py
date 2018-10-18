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

import os
import pickle as pkl
from datetime import datetime, timedelta
from enum import Enum
from warnings import warn
import networkx as nx
import pandas as pd
import json
import numpy as np

from scipy.sparse import lil_matrix, diags, csc_matrix


from GridCal.Gui.GeneralDialogues import *
from GridCal.Engine.Numerical.JacobianBased import Jacobian
from GridCal.Engine.PlotConfig import *
from GridCal.Engine.IoStructures import TimeSeriesInput, MonteCarloInput
from GridCal.Engine.Devices import *
from GridCal.Engine.BasicStructures import BusMode
from GridCal.Engine.IoStructures import CalculationInputs
from GridCal.Engine.Numerical.JacobianBased import Jacobian
from GridCal.Engine.DeviceTypes import TransformerType, Tower, BranchTemplate, BranchType, \
                                            UndergroundLineType, SequenceLineType, Wire


def load_from_xls(filename):
    """
    Loads the excel file content to a dictionary for parsing the data
    """
    data = dict()
    xl = pd.ExcelFile(filename)
    names = xl.sheet_names

    # this dictionary sets the allowed excel sheets and the possible specific converter
    allowed_data_sheets = {'Conf': None,
                           'config': None,
                           'bus': None,
                           'branch': None,
                           'load': None,
                           'load_Sprof': complex,
                           'load_Iprof': complex,
                           'load_Zprof': complex,
                           'static_generator': None,
                           'static_generator_Sprof': complex,
                           'battery': None,
                           'battery_Vset_profiles': float,
                           'battery_P_profiles': float,
                           'controlled_generator': None,
                           'CtrlGen_Vset_profiles': float,
                           'CtrlGen_P_profiles': float,
                           'shunt': None,
                           'shunt_Y_profiles': complex,
                           'wires': None,
                           'overhead_line_types': None,
                           'underground_cable_types': None,
                           'sequence_line_types': None,
                           'transformer_types': None}

    # check the validity of this excel file
    for name in names:
        if name not in allowed_data_sheets.keys():
            raise Exception('The file sheet ' + name + ' is not allowed.\n'
                            'Did you create this file manually? Use GridCal instead.')

    # parse the file
    if 'Conf' in names:
        for name in names:

            if name.lower() == "conf":
                df = xl.parse(name)
                data["baseMVA"] = np.double(df.values[0, 1])

            elif name.lower() == "bus":
                df = xl.parse(name)
                data["bus"] = np.nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['bus_names'] = df.index.values.tolist()

            elif name.lower() == "gen":
                df = xl.parse(name)
                data["gen"] = np.nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['gen_names'] = df.index.values.tolist()

            elif name.lower() == "branch":
                df = xl.parse(name)
                data["branch"] = np.nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['branch_names'] = df.index.values.tolist()

            elif name.lower() == "storage":
                df = xl.parse(name)
                data["storage"] = np.nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['storage_names'] = df.index.values.tolist()

            elif name.lower() == "lprof":
                df = xl.parse(name, index_col=0)
                data["Lprof"] = np.nan_to_num(df.values)
                data["master_time"] = df.index

            elif name.lower() == "lprofq":
                df = xl.parse(name, index_col=0)
                data["LprofQ"] = np.nan_to_num(df.values)
                # ppc["master_time"] = df.index.values

            elif name.lower() == "gprof":
                df = xl.parse(name, index_col=0)
                data["Gprof"] = np.nan_to_num(df.values)
                data["master_time"] = df.index  # it is the same

    elif 'config' in names:  # version 2

        for name in names:

            if name.lower() == "config":
                df = xl.parse('config')
                idx = df['Property'][df['Property'] == 'BaseMVA'].index
                if len(idx) > 0:
                    data["baseMVA"] = np.double(df.values[idx, 1])
                else:
                    data["baseMVA"] = 100

                idx = df['Property'][df['Property'] == 'Version'].index
                if len(idx) > 0:
                    data["version"] = np.double(df.values[idx, 1])

                idx = df['Property'][df['Property'] == 'Name'].index
                if len(idx) > 0:
                    data["name"] = df.values[idx[0], 1]
                else:
                    data["name"] = 'Grid'

                idx = df['Property'][df['Property'] == 'Comments'].index
                if len(idx) > 0:
                    data["Comments"] = df.values[idx[0], 1]
                else:
                    data["Comments"] = ''

            else:
                # just pick the DataFrame
                df = xl.parse(name, index_col=0)

                if allowed_data_sheets[name] == complex:
                    # pandas does not read complex numbers right,
                    # so when we expect a complex number input, parse directly
                    for c in df.columns.values:
                        df[c] = df[c].apply(lambda x: np.complex(x))

                data[name] = df

    else:
        raise Exception('This excel file is not in GridCal Format')

    return data


class Graph:

    def __init__(self, adj):
        """
        Graph adapted to work with CSC sparse matrices
        see: http://www.scipy-lectures.org/advanced/scipy_sparse/csc_matrix.html
        :param adj: Adjacency matrix in lil format
        """
        self.node_number = adj.shape[0]
        self.adj = adj

    def find_islands(self):
        """
        Method to get the islands of a graph
        This is the non-recursive version
        :return: islands list where each element is a list of the node indices of the island
        """

        # Mark all the vertices as not visited
        visited = np.zeros(self.node_number, dtype=bool)

        # storage structure for the islands (list of lists)
        islands = list()

        # set the island index
        island_idx = 0

        # go though all the vertices...
        for node in range(self.node_number):

            # if the node has not been visited...
            if not visited[node]:

                # add new island, because the recursive process has already visited all the island connected to v
                # if island_idx >= len(islands):
                islands.append(list())

                # ------------------------------------------------------------------------------------------------------
                # DFS: store in the island all the reachable vertices from current vertex "node"
                #
                # declare a stack with the initial node to visit (node)
                stack = list()
                stack.append(node)

                while len(stack) > 0:

                    # pick the first element of the stack
                    v = stack.pop(0)

                    # if v has not been visited...
                    if not visited[v]:

                        # mark as visited
                        visited[v] = True

                        # add element to the island
                        islands[island_idx].append(v)

                        # Add the neighbours of v to the stack
                        start = self.adj.indptr[v]
                        end = self.adj.indptr[v + 1]
                        for i in range(start, end):
                            k = self.adj.indices[i]  # get the column index in the CSC scheme
                            if not visited[k]:
                                stack.append(k)
                            else:
                                pass
                    else:
                        pass
                #
                # ------------------------------------------------------------------------------------------------------

                # increase the islands index, because all the other connected vertices have been visited
                island_idx += 1

            else:
                pass

        # sort the islands to maintain raccord
        for island in islands:
            island.sort()

        return islands


class NumericalCircuit:

    def __init__(self, n_bus, n_br, n_ld, n_ctrl_gen, n_sta_gen, n_batt, n_sh, n_time, Sbase):
        """
        Topology constructor
        :param n_bus: number of nodes
        :param n_br: number of branches
        :param n_ld: number of loads
        :param n_ctrl_gen: number of generators
        :param n_sta_gen: number of generators
        :param n_batt: number of generators
        :param n_sh: number of shunts
        :param n_time: number of time_steps
        :param Sbase: circuit base power
        """

        # number of buses
        self.nbus = n_bus

        # number of branches
        self.nbr = n_br

        # number of time steps
        self.ntime = n_time

        self.n_batt = n_batt

        self.n_ctrl_gen = n_ctrl_gen

        # base power
        self.Sbase = Sbase

        self.time_array = None

        # bus
        self.bus_names = np.empty(n_bus, dtype=object)
        self.bus_vnom = np.zeros(n_bus, dtype=float)
        self.V0 = np.ones(n_bus, dtype=complex)
        self.Vmin = np.ones(n_bus, dtype=float)
        self.Vmax = np.ones(n_bus, dtype=float)
        self.bus_types = np.empty(n_bus, dtype=int)

        # branch
        self.branch_names = np.empty(n_br, dtype=object)

        self.F = np.zeros(n_br, dtype=int)
        self.T = np.zeros(n_br, dtype=int)

        self.R = np.zeros(n_br, dtype=float)
        self.X = np.zeros(n_br, dtype=float)
        self.G = np.zeros(n_br, dtype=float)
        self.B = np.zeros(n_br, dtype=float)
        self.tap_f = np.ones(n_br, dtype=float)  # tap generated by the difference in nominal voltage at the form side
        self.tap_t = np.ones(n_br, dtype=float)  # tap generated by the difference in nominal voltage at the to side
        self.tap_mod = np.zeros(n_br, dtype=float)  # normal tap module
        self.tap_ang = np.zeros(n_br, dtype=float)  # normal tap angle
        self.br_rates = np.zeros(n_br, dtype=float)
        self.branch_states = np.zeros(n_br, dtype=int)

        self.br_mttf = np.zeros(n_br, dtype=float)
        self.br_mttr = np.zeros(n_br, dtype=float)

        self.is_bus_to_regulated = np.zeros(n_br, dtype=int)
        self.tap_position = np.zeros(n_br, dtype=int)
        self.min_tap = np.zeros(n_br, dtype=int)
        self.max_tap = np.zeros(n_br, dtype=int)
        self.tap_inc_reg_up = np.zeros(n_br, dtype=float)
        self.tap_inc_reg_down = np.zeros(n_br, dtype=float)
        self.vset = np.zeros(n_br, dtype=float)

        self.C_branch_bus_f = lil_matrix((n_br, n_bus), dtype=int)
        self.C_branch_bus_t = lil_matrix((n_br, n_bus), dtype=int)

        self.switch_indices = list()

        # load
        self.load_names = np.empty(n_ld, dtype=object)
        self.load_power = np.zeros(n_ld, dtype=complex)
        self.load_current = np.zeros(n_ld, dtype=complex)
        self.load_admittance = np.zeros(n_ld, dtype=complex)
        self.load_enabled = np.zeros(n_ld, dtype=bool)

        self.load_mttf = np.zeros(n_ld, dtype=float)
        self.load_mttr = np.zeros(n_ld, dtype=float)

        self.load_power_profile = np.zeros((n_time, n_ld), dtype=complex)
        self.load_current_profile = np.zeros((n_time, n_ld), dtype=complex)
        self.load_admittance_profile = np.zeros((n_time, n_ld), dtype=complex)

        self.C_load_bus = lil_matrix((n_ld, n_bus), dtype=int)

        # battery
        self.battery_names = np.empty(n_batt, dtype=object)
        self.battery_power = np.zeros(n_batt, dtype=float)
        self.battery_voltage = np.zeros(n_batt, dtype=float)
        self.battery_qmin = np.zeros(n_batt, dtype=float)
        self.battery_qmax = np.zeros(n_batt, dtype=float)
        self.battery_pmin = np.zeros(n_batt, dtype=float)
        self.battery_pmax = np.zeros(n_batt, dtype=float)
        self.battery_Enom = np.zeros(n_batt, dtype=float)
        self.battery_soc_0 = np.zeros(n_batt, dtype=float)
        self.battery_discharge_efficiency = np.zeros(n_batt, dtype=float)
        self.battery_charge_efficiency = np.zeros(n_batt, dtype=float)
        self.battery_min_soc = np.zeros(n_batt, dtype=float)
        self.battery_max_soc = np.zeros(n_batt, dtype=float)
        self.battery_enabled = np.zeros(n_batt, dtype=bool)
        self.battery_dispatchable = np.zeros(n_batt, dtype=bool)

        self.battery_mttf = np.zeros(n_batt, dtype=float)
        self.battery_mttr = np.zeros(n_batt, dtype=float)

        self.battery_power_profile = np.zeros((n_time, n_batt), dtype=float)
        self.battery_voltage_profile = np.zeros((n_time, n_batt), dtype=float)

        self.C_batt_bus = lil_matrix((n_batt, n_bus), dtype=int)

        # static generator
        self.static_gen_names = np.empty(n_sta_gen, dtype=object)
        self.static_gen_power = np.zeros(n_sta_gen, dtype=complex)
        self.static_gen_enabled = np.zeros(n_sta_gen, dtype=bool)
        self.static_gen_dispatchable = np.zeros(n_sta_gen, dtype=bool)

        self.static_gen_mttf = np.zeros(n_sta_gen, dtype=float)
        self.static_gen_mttr = np.zeros(n_sta_gen, dtype=float)

        self.static_gen_power_profile = np.zeros((n_time, n_sta_gen), dtype=complex)

        self.C_sta_gen_bus = lil_matrix((n_sta_gen, n_bus), dtype=int)

        # controlled generator
        self.controlled_gen_names = np.empty(n_ctrl_gen, dtype=object)
        self.controlled_gen_power = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_voltage = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_qmin = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_qmax = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_pmin = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_pmax = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_enabled = np.zeros(n_ctrl_gen, dtype=bool)
        self.controlled_gen_dispatchable = np.zeros(n_ctrl_gen, dtype=bool)

        self.controlled_gen_mttf = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_mttr = np.zeros(n_ctrl_gen, dtype=float)

        self.controlled_gen_power_profile = np.zeros((n_time, n_ctrl_gen), dtype=float)
        self.controlled_gen_voltage_profile = np.zeros((n_time, n_ctrl_gen), dtype=float)

        self.C_ctrl_gen_bus = lil_matrix((n_ctrl_gen, n_bus), dtype=int)

        # shunt
        self.shunt_names = np.empty(n_sh, dtype=object)
        self.shunt_admittance = np.zeros(n_sh, dtype=complex)
        self.shunt_enabled = np.zeros(n_sh, dtype=bool)

        self.shunt_mttf = np.zeros(n_sh, dtype=float)
        self.shunt_mttr = np.zeros(n_sh, dtype=float)

        self.shunt_admittance_profile = np.zeros((n_time, n_sh), dtype=complex)

        self.C_shunt_bus = lil_matrix((n_sh, n_bus), dtype=int)

        # Islands indices
        self.islands = list()  # bus indices per island
        self.island_branches = list()  # branch indices per island

        self.calculation_islands = list()

    def compute(self, add_storage=True, add_generation=True):
        """
        Compute the cross connectivity matrices to determine the circuit connectivity
        towards the calculation. Additionally, compute the calculation matrices.
        """
        # Declare object to store the calculation inputs
        circuit = CalculationInputs(self.nbus, self.nbr, self.ntime, self.n_batt, self.n_ctrl_gen)

        circuit.branch_rates = self.br_rates
        circuit.F = self.F
        circuit.T = self.T
        circuit.bus_names = self.bus_names
        circuit.branch_names = self.branch_names

        circuit.C_load_bus = self.C_load_bus
        circuit.C_batt_bus = self.C_batt_bus
        circuit.C_sta_gen_bus = self.C_sta_gen_bus
        circuit.C_ctrl_gen_bus = self.C_ctrl_gen_bus
        circuit.C_shunt_bus = self.C_shunt_bus

        # needed for the tap changer
        circuit.is_bus_to_regulated = self.is_bus_to_regulated
        circuit.tap_position = self.tap_position
        circuit.min_tap = self.min_tap
        circuit.max_tap = self.max_tap
        circuit.tap_inc_reg_up = self.tap_inc_reg_up
        circuit.tap_inc_reg_down = self.tap_inc_reg_down
        circuit.vset = self.vset
        circuit.tap_ang = self.tap_ang

        # active power control
        circuit.controlled_gen_pmin = self.controlled_gen_pmin
        circuit.controlled_gen_pmax = self.controlled_gen_pmax
        circuit.controlled_gen_enabled = self.controlled_gen_enabled
        circuit.controlled_gen_dispatchable = self.controlled_gen_dispatchable
        circuit.battery_pmin = self.battery_pmin
        circuit.battery_pmax = self.battery_pmax
        circuit.battery_Enom = self.battery_Enom
        circuit.battery_soc_0 = self.battery_soc_0
        circuit.battery_discharge_efficiency = self.battery_discharge_efficiency
        circuit.battery_charge_efficiency = self.battery_charge_efficiency
        circuit.battery_min_soc = self.battery_min_soc
        circuit.battery_max_soc = self.battery_max_soc
        circuit.battery_enabled = self.battery_enabled
        circuit.battery_dispatchable = self.battery_dispatchable

        ################################################################################################################
        # loads, generators, batteries, etc...
        ################################################################################################################

        # Shunts
        Ysh = self.C_shunt_bus.T * (self.shunt_admittance / self.Sbase)

        # Loads
        S = self.C_load_bus.T * (- self.load_power / self.Sbase * self.load_enabled)
        I = self.C_load_bus.T * (- self.load_current / self.Sbase * self.load_enabled)
        Ysh += self.C_load_bus.T * (self.load_admittance / self.Sbase * self.load_enabled)

        if add_generation:
            # static generators
            S += self.C_sta_gen_bus.T * (self.static_gen_power / self.Sbase * self.static_gen_enabled)

            # controlled generators
            S += self.C_ctrl_gen_bus.T * (self.controlled_gen_power / self.Sbase * self.controlled_gen_enabled)

        # batteries
        if add_storage:
            S += self.C_batt_bus.T * (self.battery_power / self.Sbase * self.battery_enabled)

        # Qmax
        q_max = self.C_ctrl_gen_bus.T * (self.controlled_gen_qmax / self.Sbase)
        q_max += self.C_batt_bus.T * (self.battery_qmax/ self.Sbase)

        # Qmin
        q_min = self.C_ctrl_gen_bus.T * (self.controlled_gen_qmin / self.Sbase)
        q_min += self.C_batt_bus.T * (self.battery_qmin / self.Sbase)

        # assign the values
        circuit.Ysh = Ysh
        circuit.Sbus = S
        circuit.Ibus = I
        circuit.Vbus = self.V0
        circuit.Sbase = self.Sbase
        circuit.types = self.bus_types
        circuit.Qmax = q_max
        circuit.Qmin = q_min

        if self.ntime > 0:
            # Shunts
            Ysh_prof = self.C_shunt_bus.T * (self.shunt_admittance_profile / self.Sbase * self.shunt_enabled).T

            # Loads
            I_prof = self.C_load_bus.T * (- self.load_current_profile / self.Sbase * self.load_enabled).T
            Ysh_prof += self.C_load_bus.T * (self.load_admittance_profile / self.Sbase * self.load_enabled).T

            Sbus_prof = self.C_load_bus.T * (- self.load_power_profile / self.Sbase * self.load_enabled).T

            if add_generation:
                # static generators
                Sbus_prof += self.C_sta_gen_bus.T * (self.static_gen_power_profile / self.Sbase * self.static_gen_enabled).T

                # controlled generators
                Sbus_prof += self.C_ctrl_gen_bus.T * (self.controlled_gen_power_profile / self.Sbase * self.controlled_gen_enabled).T

            # batteries
            if add_storage:
                Sbus_prof += self.C_batt_bus.T * (self.battery_power_profile / self.Sbase * self.battery_enabled).T

            circuit.Ysh_prof = Ysh_prof
            circuit.Sbus_prof = Sbus_prof
            circuit.Ibus_prof = I_prof
            circuit.time_array = self.time_array

        ################################################################################################################
        # Form the admittance matrix
        ################################################################################################################

        # form the connectivity matrices with the states applied
        states_dia = diags(self.branch_states)
        Cf = states_dia * self.C_branch_bus_f
        Ct = states_dia * self.C_branch_bus_t

        Ys = 1.0 / (self.R + 1.0j * self.X)
        GBc = self.G + 1.0j * self.B
        tap = self.tap_mod * np.exp(1.0j * self.tap_ang)

        # branch primitives in vector form
        Ytt = (Ys + GBc / 2.0) / (self.tap_t * self.tap_t)
        Yff = (Ys + GBc / 2.0) / (self.tap_f * self.tap_f * tap * np.conj(tap))
        Yft = - Ys / (self.tap_f * self.tap_t * np.conj(tap))
        Ytf = - Ys / (self.tap_t * self.tap_f * tap)

        # form the admittance matrices
        Yf = diags(Yff) * Cf + diags(Yft) * Ct
        Yt = diags(Ytf) * Cf + diags(Ytt) * Ct
        Ybus = csc_matrix(Cf.T * Yf + Ct.T * Yt + diags(Ysh))

        # branch primitives in vector form
        Ytts = Ys
        Yffs = Ytts / (tap * np.conj(tap))
        Yfts = - Ys / np.conj(tap)
        Ytfs = - Ys / tap

        # form the admittance matrices of the series elements
        Yfs = diags(Yffs) * Cf + diags(Yfts) * Ct
        Yts = diags(Ytfs) * Cf + diags(Ytts) * Ct
        Yseries = csc_matrix(Cf.T * Yfs + Ct.T * Yts)

        # Form the matrices for fast decoupled
        '''
        # B1 for FDPF (no shunts, no resistance, no tap module)
        b1 = 1.0 / (self.X + 1e-20)
        B1[f, f] -= b1
        B1[f, t] -= b1
        B1[t, f] -= b1
        B1[t, t] -= b1

        # B2 for FDPF (with shunts, only the tap module)
        b2 = b1 + self.B
        B2[f, f] -= (b2 / (tap * conj(tap))).real
        B2[f, t] -= (b1 / conj(tap)).real
        B2[t, f] -= (b1 / tap).real
        B2[t, t] -= b2
        '''
        b1 = 1.0 / (self.X + 1e-20)
        B1f = diags(-b1) * Cf + diags(-b1) * Ct
        B1t = diags(-b1) * Cf + diags(-b1) * Ct
        B1 = csc_matrix(Cf.T * B1f + Ct.T * B1t)

        b2 = b1 + self.B
        b2_ff = -(b2 / (tap * np.conj(tap))).real
        b2_ft = -(b1 / np.conj(tap)).real
        b2_tf = -(b1 / tap).real
        b2_tt = - b2
        B2f = diags(b2_ff) * Cf + diags(b2_ft) * Ct
        B2t = diags(b2_tf) * Cf + diags(b2_tt) * Ct
        B2 = csc_matrix(Cf.T * B2f + Ct.T * B2t)

        # assign to the calc element
        circuit.Ybus = Ybus
        circuit.Yf = Yf
        circuit.Yt = Yt
        circuit.B1 = B1
        circuit.B2 = B2
        circuit.Yseries = Yseries
        circuit.C_branch_bus_f = Cf
        circuit.C_branch_bus_t = Ct

        circuit.Ys = Ys
        circuit.GBc = GBc
        circuit.tap_f = self.tap_f
        circuit.tap_t = self.tap_t

        ################################################################################################################
        # Bus connectivity
        ################################################################################################################
        # branch - bus connectivity
        C_branch_bus = Cf + Ct

        # Connectivity node - Connectivity node connectivity matrix
        C_bus_bus = C_branch_bus.T * C_branch_bus

        ################################################################################################################
        # Islands
        ################################################################################################################
        # find the islands of the circuit
        self.islands = Graph(csc_matrix(C_bus_bus)).find_islands()

        # clear the list of circuits
        self.calculation_islands = list()

        # find the branches that belong to each island
        self.island_branches = list()

        if len(self.islands) > 1:

            # pack the islands
            for island_bus_idx in self.islands:

                # get the branch indices of the island
                island_br_idx = self.get_branches_of_the_island(island_bus_idx, C_branch_bus)
                island_br_idx = np.sort(island_br_idx)  # sort
                self.island_branches.append(island_br_idx)

                # indices of batteries and controlled generators that belong to this island
                gen_idx = np.where(self.C_ctrl_gen_bus[:, island_bus_idx].sum(axis=0) > 0)[0]
                bat_idx = np.where(self.C_batt_bus[:, island_bus_idx].sum(axis=0) > 0)[0]

                # Get the island circuit (the bus types are computed automatically)
                # The island original indices are generated within the get_island function
                circuit_island = circuit.get_island(island_bus_idx, island_br_idx, gen_idx, bat_idx)

                # store the island
                self.calculation_islands.append(circuit_island)
        else:
            # compile bus types
            circuit.consolidate()

            # only one island, no need to split anything
            self.calculation_islands.append(circuit)

            island_bus_idx = np.arange(start=0, stop=self.nbus, step=1, dtype=int)
            island_br_idx = np.arange(start=0, stop=self.nbr, step=1, dtype=int)

            # set the indices in the island too
            circuit.original_bus_idx = island_bus_idx
            circuit.original_branch_idx = island_br_idx

            # append a list with all the branch indices for completeness
            self.island_branches.append(island_br_idx)

        # return the list of islands
        return self.calculation_islands

    def get_B(self):

        # Shunts
        Ysh = self.C_shunt_bus.T * (self.shunt_admittance / self.Sbase)

        # Loads
        Ysh += self.C_load_bus.T * (self.load_admittance / self.Sbase * self.load_enabled)

        # form the connectivity matrices with the states applied
        states_dia = diags(self.branch_states)
        Cf = states_dia * self.C_branch_bus_f
        Ct = states_dia * self.C_branch_bus_t

        Ys = 1.0 / (self.R + 1.0j * self.X)
        GBc = self.G + 1.0j * self.B
        tap = self.tap_mod * np.exp(1.0j * self.tap_ang)

        # branch primitives in vector form
        Ytt = (Ys + GBc / 2.0) / (self.tap_t * self.tap_t)
        Yff = (Ys + GBc / 2.0) / (self.tap_f * self.tap_f * tap * np.conj(tap))
        Yft = - Ys / (self.tap_f * self.tap_t * np.conj(tap))
        Ytf = - Ys / (self.tap_t * self.tap_f * tap)

        # form the admittance matrices
        Yf = diags(Yff) * Cf + diags(Yft) * Ct
        Yt = diags(Ytf) * Cf + diags(Ytt) * Ct
        Ybus = csc_matrix(Cf.T * Yf + Ct.T * Yt + diags(Ysh))

        return Ybus.imag

    @staticmethod
    def get_branches_of_the_island(island, C_branch_bus):
        """
        Get the branch indices of the island
        :param island: array of bus indices of the island
        :param C_branch_bus: connectivity matrix of the branches and the buses
        :return: array of indices of the branches
        """

        # faster method
        A = csc_matrix(C_branch_bus)
        n = A.shape[0]
        visited = np.zeros(n, dtype=bool)
        br_idx = np.zeros(n, dtype=int)
        n_visited = 0
        for k in range(len(island)):
            j = island[k]

            for l in range(A.indptr[j], A.indptr[j+1]):
                i = A.indices[l]  # row index

                if not visited[i]:
                    visited[i] = True
                    br_idx[n_visited] = i
                    n_visited += 1

        # resize vector
        br_idx = br_idx[:n_visited]

        return br_idx

    def power_flow_post_process(self, V, only_power=False):
        """
        Compute the power flows trough the branches for the complete circuit taking into account the islands
        @param V: Voltage solution array for the circuit buses
        @param only_power: compute only the power injection
        @return: Sbranch (MVA), Ibranch (p.u.), loading (p.u.), losses (MVA), Sbus(MVA)
        """
        Sbranch_all = np.zeros(self.nbr, dtype=complex)
        Ibranch_all = np.zeros(self.nbr, dtype=complex)
        loading_all = np.zeros(self.nbr, dtype=complex)
        losses_all = np.zeros(self.nbr, dtype=complex)
        Sbus_all = np.zeros(self.nbus, dtype=complex)

        for circuit in self.calculation_islands:
            # Compute the slack and pv buses power
            Sbus = circuit.Sbus

            vd = circuit.ref
            pv = circuit.pv

            # power at the slack nodes
            Sbus[vd] = V[vd] * np.conj(circuit.Ybus[vd, :][:, :].dot(V))

            # Reactive power at the pv nodes
            P = Sbus[pv].real
            Q = (V[pv] * np.conj(circuit.Ybus[pv, :][:, :].dot(V))).imag
            Sbus[pv] = P + 1j * Q  # keep the original P injection and set the calculated reactive power

            if not only_power:
                # Branches current, loading, etc
                If = circuit.Yf * V
                It = circuit.Yt * V
                Sf = (circuit.C_branch_bus_f * V) * np.conj(If)
                St = (circuit.C_branch_bus_t * V) * np.conj(It)

                # Branch losses in MVA
                losses = (Sf + St) * circuit.Sbase

                # Branch current in p.u.
                Ibranch = np.maximum(If, It)

                # Branch power in MVA
                Sbranch = np.maximum(Sf, St) * circuit.Sbase

                # Branch loading in p.u.
                loading = Sbranch / (circuit.branch_rates + 1e-9)

            else:
                Sbranch = np.zeros(self.nbr, dtype=complex)
                Ibranch = np.zeros(self.nbr, dtype=complex)
                loading = np.zeros(self.nbr, dtype=complex)
                losses = np.zeros(self.nbr, dtype=complex)
                Sbus = np.zeros(self.nbus, dtype=complex)

            # assign to master
            Sbranch_all[circuit.original_branch_idx] = Sbranch
            Ibranch_all[circuit.original_branch_idx] = Ibranch
            loading_all[circuit.original_branch_idx] = loading
            losses_all[circuit.original_branch_idx] = losses
            Sbus_all[circuit.original_bus_idx] = Sbus

        return Sbranch_all, Ibranch_all, loading_all, losses_all, Sbus_all

    def print(self, islands_only=False):
        """
        print the connectivity matrices
        :return:
        """

        if islands_only:

            print('Islands:')
            for island in self.islands:
                print('-' * 180)
                print('\nIsland:', island)
                print('\t nodes: ', self.bus_names[island])
                br_idx = self.get_branches_of_the_island(island)
                print('\t branches: ', self.branch_names[br_idx])

        else:
            if self.nbus < 100:
                # print('\nBus-Terminal\n', pd.DataFrame(self.C_cn_terminal.todense(), index=self.bus_names, columns=self.terminal_names))
                # print('\nBranch-Terminal-From\n', pd.DataFrame(self.C_branch_terminal_f.todense(), index=self.branch_names, columns=self.terminal_names))
                # print('\nBranch-Terminal-To\n', pd.DataFrame(self.C_branch_terminal_t.todense(), index=self.branch_names, columns=self.terminal_names))
                # # print('\nSwitch-Terminal\n', pd.DataFrame(self.C_switch_terminal.todense(), index=self.switch_names, columns=self.terminal_names))
                # print('\nBranch-States\n', pd.DataFrame(self.branch_states, index=self.branch_names, columns=['States']).transpose())

                # resulting
                print('\n\n' + '-' * 40 + ' RESULTS ' + '-' * 40 + '\n')
                # print('\nLoad-Bus\n', pd.DataFrame(self.C_load_bus.todense(), index=self.load_names, columns=self.bus_names))
                # print('\nShunt-Bus\n', pd.DataFrame(self.C_shunt_bus.todense(), index=self.shunt_names, columns=self.bus_names))
                # print('\nGen-Bus\n', pd.DataFrame(self.C_gen_bus.todense(), index=self.generator_names, columns=self.bus_names))
                print('\nCf (Branch from-Bus)\n',
                      pd.DataFrame(self.calc.C_branch_bus_f.astype(int).todense(), index=self.branch_names, columns=self.bus_names))
                print('\nCt (Branch to-Bus)\n',
                      pd.DataFrame(self.calc.C_branch_bus_t.astype(int).todense(), index=self.branch_names, columns=self.bus_names))
                print('\nBus-Bus (Adjacency matrix: Graph)\n', pd.DataFrame(self.C_bus_bus.todense(), index=self.bus_names, columns=self.bus_names))

                # print('\nYff\n', pd.DataFrame(self.BR_yff, index=self.branch_names, columns=['Yff']))
                # print('\nYft\n', pd.DataFrame(self.BR_yft, index=self.branch_names, columns=['Yft']))
                # print('\nYtf\n', pd.DataFrame(self.BR_ytf, index=self.branch_names, columns=['Ytf']))
                # print('\nYtt\n', pd.DataFrame(self.BR_ytt, index=self.branch_names, columns=['Ytt']))

            if len(self.islands) == 1:
                self.calc.print(self.bus_names)

            else:

                print('Islands:')
                for island in self.islands:
                    print('-' * 180)
                    print('\nIsland:', island)
                    print('\t nodes: ', self.bus_names[island])
                    br_idx = self.get_branches_of_the_island(island)
                    print('\t branches: ', self.branch_names[br_idx])

                    calc_island = self.calc.get_island(island, br_idx)
                    calc_island.print(self.bus_names[island])
                print('-' * 180)

    def plot(self, stop=True):
        """
        Plot the grid as a graph
        :param stop: stop the execution while displaying
        """

        adjacency_matrix = self.C_bus_bus.todense()
        mylabels = {i: name for i, name in enumerate(self.bus_names)}

        gr = nx.Graph(adjacency_matrix)
        nx.draw(gr, node_size=500, labels=mylabels, with_labels=True)
        if stop:
            plt.show()


class MultiCircuit:

    def __init__(self, name=''):
        """
        Multi Circuit Constructor
        """

        self.name = name

        self.comments = ''

        # Base power (MVA)
        self.Sbase = 100.0

        # Base frequency in Hz
        self.fBase = 50.0

        # Should be able to accept Branches, Lines and Transformers alike
        self.branches = list()

        # array of branch indices in the master circuit
        self.branch_original_idx = list()

        # Should accept buses
        self.buses = list()

        # array of bus indices in the master circuit
        self.bus_original_idx = list()

        # Dictionary relating the bus object to its index. Updated upon compilation
        self.buses_dict = dict()

        # List of overhead line objects
        self.overhead_line_types = list()

        # list of wire types
        self.wire_types = list()

        # underground cable lines
        self.underground_cable_types = list()

        # sequence modelled lines
        self.sequence_line_types = list()

        # List of transformer types
        self.transformer_types = list()

        # Object with the necessary inputs for a power flow study
        self.numerical_circuit = None

        # #  containing the power flow results
        # self.power_flow_results = None
        #
        # # containing the short circuit results
        # self.short_circuit_results = None
        #
        # # Object with the necessary inputs for th time series simulation
        # self.time_series_input = None
        #
        # # Object with the time series simulation results
        # self.time_series_results = None
        #
        # # Monte Carlo input object
        # self.monte_carlo_input = None
        #
        # # Monte Carlo time series batch
        # self.mc_time_series = None

        # Bus-Branch graph
        self.graph = None

        # self.power_flow_results = PowerFlowResults()

        self.bus_dictionary = dict()

        self.branch_dictionary = dict()

        self.has_time_series = False

        self.bus_names = None

        self.branch_names = None

        self.time_profile = None

        self.objects_with_profiles = [Load(), StaticGenerator(), ControlledGenerator(), Battery(), Shunt()]

        self.profile_magnitudes = dict()

        '''
        self.type_name = 'Shunt'

        self.properties_with_profile = ['Y']
        '''
        for dev in self.objects_with_profiles:
            if dev.properties_with_profile is not None:
                self.profile_magnitudes[dev.type_name] = dev.properties_with_profile

    def clear(self):

        # Should be able to accept Branches, Lines and Transformers alike
        self.branches = list()

        # array of branch indices in the master circuit
        self.branch_original_idx = list()

        # Should accept buses
        self.buses = list()

        # array of bus indices in the master circuit
        self.bus_original_idx = list()

        # Dictionary relating the bus object to its index. Updated upon compilation
        self.buses_dict = dict()

        # List of overhead line objects
        self.overhead_line_types = list()

        # list of wire types
        self.wire_types = list()

        # underground cable lines
        self.underground_cable_types = list()

        # sequence modelled lines
        self.sequence_line_types = list()

        # List of transformer types
        self.transformer_types = list()

        # Object with the necessary inputs for a power flow study
        self.numerical_circuit = None

        #  containing the power flow results
        self.power_flow_results = None

        # containing the short circuit results
        self.short_circuit_results = None

        # Object with the necessary inputs for th time series simulation
        self.time_series_input = None

        # Object with the time series simulation results
        self.time_series_results = None

        # Monte Carlo input object
        self.monte_carlo_input = None

        # Monte Carlo time series batch
        self.mc_time_series = None

        # Bus-Branch graph
        self.graph = None

        self.bus_dictionary = dict()

        self.branch_dictionary = dict()

        self.has_time_series = False

        self.bus_names = None

        self.branch_names = None

        self.time_profile = None

    def get_loads(self):
        """

        :return:
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                elm.bus = bus
            lst = lst + bus.loads
        return lst

    def get_load_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                lst.append(elm.name)
        return np.array(lst)

    def get_static_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                elm.bus = bus
            lst = lst + bus.static_generators
        return lst

    def get_static_generators_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                lst.append(elm.name)
        return np.array(lst)

    def get_shunts(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.shunts:
                elm.bus = bus
            lst = lst + bus.shunts
        return lst

    def get_shunt_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.shunts:
                lst.append(elm.name)
        return np.array(lst)

    def get_controlled_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.controlled_generators:
                elm.bus = bus
            lst = lst + bus.controlled_generators
        return lst

    def get_controlled_generator_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.controlled_generators:
                lst.append(elm.name)
        return np.array(lst)

    def get_batteries(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                elm.bus = bus
            lst = lst + bus.batteries
        return lst

    def get_battery_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                lst.append(elm.name)
        return np.array(lst)

    def get_battery_capacities(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                lst.append(elm.Enom)
        return np.array(lst)

    def get_Jacobian(self, sparse=False):
        """
        Returns the Grid Jacobian matrix
        Returns:
            Grid Jacobian Matrix in CSR sparse format or as full matrix
        """

        # Initial magnitudes
        pvpq = np.r_[self.numerical_circuit.pv, self.numerical_circuit.pq]

        J = Jacobian(Ybus=self.numerical_circuit.Ybus,
                     V=self.numerical_circuit.Vbus,
                     Ibus=self.numerical_circuit.Ibus,
                     pq=self.numerical_circuit.pq,
                     pvpq=pvpq)

        if sparse:
            return J
        else:
            return J.todense()

    def get_bus_pf_results_df(self):
        """
        Returns a Pandas DataFrame with the bus results
        :return: DataFrame
        """

        cols = ['|V| (p.u.)', 'angle (rad)', 'P (p.u.)', 'Q (p.u.)', 'Qmin', 'Qmax', 'Q ok?']

        if self.power_flow_results is not None:
            q_l = self.numerical_circuit.Qmin < self.power_flow_results.Sbus.imag
            q_h = self.power_flow_results.Sbus.imag < self.numerical_circuit.Qmax
            q_ok = q_l * q_h
            data = np.c_[np.abs(self.power_flow_results.voltage),
                         np.angle(self.power_flow_results.voltage),
                         self.power_flow_results.Sbus.real,
                         self.power_flow_results.Sbus.imag,
                         self.numerical_circuit.Qmin,
                         self.numerical_circuit.Qmax,
                         q_ok.astype(np.bool)]
        else:
            data = [0, 0, 0, 0, 0, 0]

        return pd.DataFrame(data=data, index=self.numerical_circuit.bus_names, columns=cols)

    def apply_lp_profiles(self):
        """
        Apply the LP results as device profiles
        :return:
        """
        for bus in self.buses:
            bus.apply_lp_profiles(self.Sbase)

    def copy(self):
        """
        Returns a deep (true) copy of this circuit
        @return:
        """

        cpy = MultiCircuit()

        cpy.name = self.name

        bus_dict = dict()
        for bus in self.buses:
            bus_cpy = bus.copy()
            bus_dict[bus] = bus_cpy
            cpy.buses.append(bus_cpy)

        for branch in self.branches:
            cpy.branches.append(branch.copy(bus_dict))

        cpy.Sbase = self.Sbase

        cpy.branch_original_idx = self.branch_original_idx.copy()

        cpy.bus_original_idx = self.bus_original_idx.copy()

        cpy.time_series_input = self.time_series_input.copy()

        cpy.numerical_circuit = self.numerical_circuit.copy()

        return cpy

    def get_catalogue_dict(self, branches_only=False):
        """
        Returns a dictionary with the catalogue types and the associated list of objects
        :param branches_only: only branch types
        :return: dictionary
        """
        # 'Wires', 'Overhead lines', 'Underground lines', 'Sequence lines', 'Transformers'

        if branches_only:

            catalogue_dict = {'Overhead lines': self.overhead_line_types,
                              'Transformers': self.transformer_types,
                              'Underground lines': self.underground_cable_types,
                              'Sequence lines': self.sequence_line_types}
        else:
            catalogue_dict = {'Wires': self.wire_types,
                              'Overhead lines': self.overhead_line_types,
                              'Underground lines': self.underground_cable_types,
                              'Sequence lines': self.sequence_line_types,
                              'Transformers': self.transformer_types}

        return catalogue_dict

    def get_catalogue_dict_by_name(self, type_class=None):

        d = dict()

        # ['Wires', 'Overhead lines', 'Underground lines', 'Sequence lines', 'Transformers']

        if type_class is None:
            tpes = [self.overhead_line_types,
                    self.underground_cable_types,
                    self.wire_types,
                    self.transformer_types,
                    self.sequence_line_types]

        elif type_class == 'Wires':
            tpes = self.wire_types
            name_prop = 'wire_name'

        elif type_class == 'Overhead lines':
            tpes = self.overhead_line_types
            name_prop = 'tower_name'

        elif type_class == 'Underground lines':
            tpes = self.underground_cable_types
            name_prop = 'name'

        elif type_class == 'Sequence lines':
            tpes = self.sequence_line_types
            name_prop = 'name'

        elif type_class == 'Transformers':
            tpes = self.transformer_types
            name_prop = 'name'

        else:
            tpes = list()
            name_prop = 'name'

        # make dictionary
        for tpe in tpes:
            d[getattr(tpe, name_prop)] = tpe

        return d

    def get_json_dict(self, id):
        """
        Get json dictionary
        :return: 
        """
        return {'id': id,
                'type': 'circuit',
                'phases': 'ps',
                'name': self.name,
                'Sbase': self.Sbase,
                'comments': self.comments}

    def load_file(self, filename):
        """
        Load GridCal compatible file
        @param filename:
        @return:
        """
        logger = list()

        if os.path.exists(filename):
            name, file_extension = os.path.splitext(filename)
            # print(name, file_extension)
            if file_extension.lower() in ['.xls', '.xlsx']:

                ppc = load_from_xls(filename)

                # Pass the table-like data dictionary to objects in this circuit
                if 'version' not in ppc.keys():
                    from GridCal.Engine.Importers.matpower_parser import interpret_data_v1
                    interpret_data_v1(self, ppc)
                    return logger
                elif ppc['version'] == 2.0:
                    self.load_excel(ppc)
                    return logger
                else:
                    warn('The file could not be processed')
                    return logger

            elif file_extension.lower() == '.dgs':
                from GridCal.Engine.Importers.DGS_Parser import dgs_to_circuit
                circ = dgs_to_circuit(filename)
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)

            elif file_extension.lower() == '.m':
                from GridCal.Engine.Importers.matpower_parser import parse_matpower_file
                circ = parse_matpower_file(filename)
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)

            elif file_extension.lower() == '.dpx':
                from GridCal.Engine.Importers.DPX import load_dpx
                circ, logger = load_dpx(filename)
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)

            elif file_extension.lower() == '.json':

                # the json file can be the GridCAl one or the iPA one...
                data = json.load(open(filename))

                if 'Red' in data.keys():
                    from GridCal.Engine.Importers.iPA import load_iPA
                    circ = load_iPA(filename)
                    self.buses = circ.buses
                    self.branches = circ.branches
                    self.assign_circuit(circ)
                else:
                    from GridCal.Engine.Importers.JSON_parser import parse_json
                    circ = parse_json(filename)
                    self.buses = circ.buses
                    self.branches = circ.branches
                    self.assign_circuit(circ)

            elif file_extension.lower() == '.raw':
                from GridCal.Engine.Importers.PSS_Parser import PSSeParser
                parser = PSSeParser(filename)
                circ = parser.circuit
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)
                logger = parser.logger

            elif file_extension.lower() == '.xml':
                from GridCal.Engine.Importers.CIM import CIMImport
                parser = CIMImport()
                circ = parser.load_cim_file(filename)
                self.assign_circuit(circ)
                logger = parser.logger

        else:
            warn('The file does not exist.')
            logger.append(filename + ' does not exist.')

        return logger

    def assign_circuit(self, circ):
        """
        Assign a circuit object to this object
        :param circ: instance of MultiCircuit or Circuit
        """
        self.buses = circ.buses
        self.branches = circ.branches
        self.name = circ.name
        self.Sbase = circ.Sbase
        self.fBase = circ.fBase

    def load_excel(self, data):
        """
        Interpret the new file version
        Args:
            data: Dictionary with the excel file sheet labels and the corresponding DataFrame

        Returns: Nothing, just applies the loaded data to this MultiCircuit instance

        """
        # print('Interpreting V2 data...')

        # clear all the data
        self.clear()

        self.name = data['name']

        # set the base magnitudes
        self.Sbase = data['baseMVA']

        # dictionary of branch types [name] -> type object
        branch_types = dict()

        # Set comments
        self.comments = data['Comments'] if 'Comments' in data.keys() else ''

        self.time_profile = None

        self.logger = list()

        # common function
        def set_object_attributes(obj_, attr_list, values):
            for a, attr in enumerate(attr_list):

                # Hack to change the enabled by active...
                if attr == 'is_enabled':
                    attr = 'active'

                if attr == 'type_obj':
                    attr = 'template'

                if hasattr(obj_, attr):
                    conv = obj_.edit_types[attr]  # get the type converter
                    if conv is None:
                        setattr(obj_, attr, values[a])
                    elif conv is BranchType:
                        cbr = BranchTypeConverter(None)
                        setattr(obj_, attr, cbr(values[a]))
                    else:
                        setattr(obj_, attr, conv(values[a]))
                else:
                    warn(str(obj_) + ' has no ' + attr + ' property.')

        # Add the buses ################################################################################################
        bus_dict = dict()
        if 'bus' in data.keys():
            lst = data['bus']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = Bus()
                set_object_attributes(obj, hdr, vals[i, :])
                bus_dict[obj.name] = obj
                self.add_bus(obj)
        else:
            self.logger.append('No buses in the file!')

        # add the loads ################################################################################################
        if 'load' in data.keys():
            lst = data['load']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Load()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'load_Sprof' in data.keys():
                    val = [complex(v) for v in data['load_Sprof'].values[:, i]]
                    idx = data['load_Sprof'].index
                    obj.Sprof = pd.DataFrame(data=val, index=idx)

                    if self.time_profile is None:
                        self.time_profile = idx

                if 'load_Iprof' in data.keys():
                    val = [complex(v) for v in data['load_Iprof'].values[:, i]]
                    idx = data['load_Iprof'].index
                    obj.Iprof = pd.DataFrame(data=val, index=idx)

                    if self.time_profile is None:
                        self.time_profile = idx

                if 'load_Zprof' in data.keys():
                    val = [complex(v) for v in data['load_Zprof'].values[:, i]]
                    idx = data['load_Zprof'].index
                    obj.Zprof = pd.DataFrame(data=val, index=idx)

                    if self.time_profile is None:
                        self.time_profile = idx

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Load bus is not in the buses list.\n' + str(ex))

                if obj.name == 'Load':
                    obj.name += str(len(bus.loads) + 1) + '@' + bus.name

                obj.bus = bus
                bus.loads.append(obj)
        else:
            self.logger.append('No loads in the file!')

        # add the controlled generators ################################################################################
        if 'controlled_generator' in data.keys():
            lst = data['controlled_generator']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = ControlledGenerator()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'CtrlGen_P_profiles' in data.keys():
                    val = data['CtrlGen_P_profiles'].values[:, i]
                    idx = data['CtrlGen_P_profiles'].index
                    # obj.Pprof = pd.DataFrame(data=val, index=idx)
                    obj.create_P_profile(index=idx, arr=val)

                if 'CtrlGen_Vset_profiles' in data.keys():
                    val = data['CtrlGen_Vset_profiles'].values[:, i]
                    idx = data['CtrlGen_Vset_profiles'].index
                    obj.Vsetprof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Controlled generator bus is not in the buses list.\n' + str(ex))

                if obj.name == 'gen':
                    obj.name += str(len(bus.controlled_generators) + 1) + '@' + bus.name

                obj.bus = bus
                bus.controlled_generators.append(obj)
        else:
            self.logger.append('No controlled generator in the file!')

        # add the batteries ############################################################################################
        if 'battery' in data.keys():
            lst = data['battery']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Battery()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'battery_P_profiles' in data.keys():
                    val = data['battery_P_profiles'].values[:, i]
                    idx = data['battery_P_profiles'].index
                    # obj.Pprof = pd.DataFrame(data=val, index=idx)
                    obj.create_P_profile(index=idx, arr=val)

                if 'battery_Vset_profiles' in data.keys():
                    val = data['battery_Vset_profiles'].values[:, i]
                    idx = data['battery_Vset_profiles'].index
                    obj.Vsetprof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Battery bus is not in the buses list.\n' + str(ex))

                if obj.name == 'batt':
                    obj.name += str(len(bus.batteries) + 1) + '@' + bus.name

                obj.bus = bus
                bus.batteries.append(obj)
        else:
            self.logger.append('No battery in the file!')

        # add the static generators ####################################################################################
        if 'static_generator' in data.keys():
            lst = data['static_generator']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = StaticGenerator()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'static_generator_Sprof' in data.keys():
                    val = data['static_generator_Sprof'].values[:, i]
                    idx = data['static_generator_Sprof'].index
                    obj.Sprof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Static generator bus is not in the buses list.\n' + str(ex))

                if obj.name == 'StaticGen':
                    obj.name += str(len(bus.static_generators) + 1) + '@' + bus.name

                obj.bus = bus
                bus.static_generators.append(obj)
        else:
            self.logger.append('No static generator in the file!')

        # add the shunts ###############################################################################################
        if 'shunt' in data.keys():
            lst = data['shunt']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Shunt()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'shunt_Y_profiles' in data.keys():
                    val = data['shunt_Y_profiles'].values[:, i]
                    idx = data['shunt_Y_profiles'].index
                    obj.Yprof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Shunt bus is not in the buses list.\n' + str(ex))

                if obj.name == 'shunt':
                    obj.name += str(len(bus.shunts) + 1) + '@' + bus.name

                obj.bus = bus
                bus.shunts.append(obj)
        else:
            self.logger.append('No shunt in the file!')

        # Add the wires ################################################################################################
        if 'wires' in data.keys():
            lst = data['wires']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = Wire()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_wire(obj)
        else:
            self.logger.append('No wires in the file!')

        # Add the overhead_line_types ##################################################################################
        if 'overhead_line_types' in data.keys():
            lst = data['overhead_line_types']
            if data['overhead_line_types'].values.shape[0] > 0:
                for tower_name in lst['tower_name'].unique():
                    obj = Tower()
                    vals = lst[lst['tower_name'] == tower_name].values

                    # set the tower values
                    set_object_attributes(obj, obj.edit_headers, vals[0, :])

                    # add the wires
                    for i in range(vals.shape[0]):
                        wire = Wire()
                        set_object_attributes(wire, obj.get_wire_properties(), vals[i, len(obj.edit_headers):])
                        obj.wires.append(wire)

                    self.add_overhead_line(obj)
                    branch_types[str(obj)] = obj
            else:
                pass
        else:
            self.logger.append('No overhead_line_types in the file!')

        # Add the wires ################################################################################################
        if 'underground_cable_types' in data.keys():
            lst = data['underground_cable_types']
            hdr = lst.columns.values
            vals = lst.values
            # for i in range(len(lst)):
            #     obj = UndergroundLineType()
            #     set_object_attributes(obj, hdr, vals[i, :])
            #     self.underground_cable_types.append(obj)
            #     branch_types[str(obj)] = obj
        else:
            self.logger.append('No underground_cable_types in the file!')

        # Add the sequence line types ##################################################################################
        if 'sequence_line_types' in data.keys():
            lst = data['sequence_line_types']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = SequenceLineType()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_sequence_line(obj)
                branch_types[str(obj)] = obj
        else:
            self.logger.append('No sequence_line_types in the file!')

        # Add the transformer types ####################################################################################
        if 'transformer_types' in data.keys():
            lst = data['transformer_types']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = TransformerType()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_transformer_type(obj)
                branch_types[str(obj)] = obj
        else:
            self.logger.append('No transformer_types in the file!')

        # Add the branches #############################################################################################
        if 'branch' in data.keys():
            lst = data['branch']

            # fix the old 'is_transformer' property
            if 'is_transformer' in lst.columns.values:
                lst['is_transformer'] = lst['is_transformer'].map({True: 'transformer', False: 'line'})
                lst.rename(columns={'is_transformer': 'branch_type'}, inplace=True)

            bus_from = lst['bus_from'].values
            bus_to = lst['bus_to'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus_from'))
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus_to'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                try:
                    obj = Branch(bus_from=bus_dict[str(bus_from[i])], bus_to=bus_dict[str(bus_to[i])])
                except KeyError as ex:
                    raise Exception(str(i) + ': Branch bus is not in the buses list.\n' + str(ex))

                set_object_attributes(obj, hdr, vals[i, :])

                # correct the branch template object
                template_name = str(obj.template)
                if template_name in branch_types.keys():
                    obj.template = branch_types[template_name]
                    print(template_name, 'updtaed!')

                # set the branch
                self.add_branch(obj)

        else:
            self.logger.append('No branches in the file!')

        # Other actions ################################################################################################
        self.logger += self.apply_all_branch_types()

    def save_file(self, file_path):
        """
        Save File
        :param file_path: 
        :return: 
        """

        if file_path.endswith('.xlsx'):
            logger = self.save_excel(file_path)
        elif file_path.endswith('.json'):
            logger = self.save_json(file_path)
        elif file_path.endswith('.xml'):
            logger = self.save_cim(file_path)
        else:
            logger = list()
            logger.append('File path extension not understood\n' + file_path)

        return logger

    def save_excel(self, file_path):
        """
        Save the circuit information
        :param file_path: file path to save
        :return:
        """
        logger = list()

        dfs = dict()

        # configuration ################################################################################################
        obj = list()
        obj.append(['BaseMVA', self.Sbase])
        obj.append(['Version', 2])
        obj.append(['Name', self.name])
        obj.append(['Comments', self.comments])
        dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'])

        # get the master time profile
        T = self.time_profile

        # buses ########################################################################################################
        obj = list()
        names_count = dict()
        headers = Bus().edit_headers
        if len(self.buses) > 0:
            for elm in self.buses:

                # check name: if the name is repeated, change it so that it is not
                if elm.name in names_count.keys():
                    names_count[elm.name] += 1
                    elm.name = elm.name + '_' + str(names_count[elm.name])
                else:
                    names_count[elm.name] = 1

                obj.append(elm.get_save_data())

            dta = np.array(obj).astype('str')
        else:
            dta = np.zeros((0, len(headers)))

        dfs['bus'] = pd.DataFrame(data=dta, columns=headers)

        # branches #####################################################################################################
        headers = Branch(None, None).edit_headers
        if len(self.branches) > 0:
            obj = list()
            for elm in self.branches:
                obj.append(elm.get_save_data())

            dta = np.array(obj).astype('str')
        else:
            dta = np.zeros((0, len(headers)))

        dfs['branch'] = pd.DataFrame(data=dta, columns=headers)

        # loads ########################################################################################################
        headers = Load().edit_headers
        loads = self.get_loads()
        if len(loads) > 0:
            obj = list()
            s_profiles = None
            i_profiles = None
            z_profiles = None
            hdr = list()
            for elm in loads:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if s_profiles is None and elm.Sprof is not None:
                        s_profiles = elm.Sprof.values
                        i_profiles = elm.Iprof.values
                        z_profiles = elm.Zprof.values
                    else:
                        s_profiles = np.c_[s_profiles, elm.Sprof.values]
                        i_profiles = np.c_[i_profiles, elm.Iprof.values]
                        z_profiles = np.c_[z_profiles, elm.Zprof.values]

            dfs['load'] = pd.DataFrame(data=obj, columns=headers)

            if s_profiles is not None:
                dfs['load_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)
                dfs['load_Iprof'] = pd.DataFrame(data=i_profiles.astype('str'), columns=hdr, index=T)
                dfs['load_Zprof'] = pd.DataFrame(data=z_profiles.astype('str'), columns=hdr, index=T)
        else:
            dfs['load'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # static generators ############################################################################################
        headers = StaticGenerator().edit_headers
        st_gen = self.get_static_generators()
        if len(st_gen) > 0:
            obj = list()
            hdr = list()
            s_profiles = None
            for elm in st_gen:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if s_profiles is None and elm.Sprof is not None:
                        s_profiles = elm.Sprof.values
                    else:
                        s_profiles = np.c_[s_profiles, elm.Sprof.values]

            dfs['static_generator'] = pd.DataFrame(data=obj, columns=headers)

            if s_profiles is not None:
                dfs['static_generator_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)
        else:
            dfs['static_generator'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # battery ######################################################################################################
        batteries = self.get_batteries()
        headers = Battery().edit_headers

        if len(batteries) > 0:
            obj = list()
            hdr = list()
            v_set_profiles = None
            p_profiles = None
            for elm in batteries:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if p_profiles is None and elm.Pprof is not None:
                        p_profiles = elm.Pprof.values
                        v_set_profiles = elm.Vsetprof.values
                    else:
                        p_profiles = np.c_[p_profiles, elm.Pprof.values]
                        v_set_profiles = np.c_[v_set_profiles, elm.Vsetprof.values]
            dfs['battery'] = pd.DataFrame(data=obj, columns=headers)

            if p_profiles is not None:
                dfs['battery_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
                dfs['battery_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)
        else:
            dfs['battery'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # controlled generator #########################################################################################
        con_gen = self.get_controlled_generators()
        headers = ControlledGenerator().edit_headers

        if len(con_gen) > 0:
            obj = list()
            hdr = list()
            v_set_profiles = None
            p_profiles = None
            for elm in con_gen:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None and elm.Pprof is not None:
                    if p_profiles is None:
                        p_profiles = elm.Pprof.values
                        v_set_profiles = elm.Vsetprof.values
                    else:
                        p_profiles = np.c_[p_profiles, elm.Pprof.values]
                        v_set_profiles = np.c_[v_set_profiles, elm.Vsetprof.values]

            dfs['controlled_generator'] = pd.DataFrame(data=obj, columns=headers)

            if p_profiles is not None:
                dfs['CtrlGen_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
                dfs['CtrlGen_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)
        else:
            dfs['controlled_generator'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # shunt ########################################################################################################

        shunts = self.get_shunts()
        headers = Shunt().edit_headers

        if len(shunts) > 0:
            obj = list()
            hdr = list()
            y_profiles = None
            for elm in shunts:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if y_profiles is None and elm.Yprof.values is not None:
                        y_profiles = elm.Yprof.values
                    else:
                        y_profiles = np.c_[y_profiles, elm.Yprof.values]

            dfs['shunt'] = pd.DataFrame(data=obj, columns=headers)

            if y_profiles is not None:
                dfs['shunt_Y_profiles'] = pd.DataFrame(data=y_profiles.astype(str), columns=hdr, index=T)
        else:

            dfs['shunt'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # wires ########################################################################################################

        elements = self.wire_types
        headers = Wire(name='', xpos=0, ypos=0, gmr=0, r=0, x=0, phase=0).edit_headers

        if len(elements) > 0:
            obj = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['wires'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['wires'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # overhead cable types ######################################################################################

        elements = self.overhead_line_types
        headers = Tower().get_save_headers()

        if len(elements) > 0:
            obj = list()
            for elm in elements:
                elm.get_save_data(dta_list=obj)

            dfs['overhead_line_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['overhead_line_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # underground cable types ######################################################################################

        elements = self.underground_cable_types
        headers = UndergroundLineType().edit_headers

        if len(elements) > 0:
            obj = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['underground_cable_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['underground_cable_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # sequence line types ##########################################################################################

        elements = self.sequence_line_types
        headers = SequenceLineType().edit_headers

        if len(elements) > 0:
            obj = list()
            hdr = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['sequence_line_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['sequence_line_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # transformer types ############################################################################################

        elements = self.transformer_types
        headers = TransformerType().edit_headers

        if len(elements) > 0:
            obj = list()
            hdr = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['transformer_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['transformer_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # flush-save ###################################################################################################
        writer = pd.ExcelWriter(file_path)
        for key in dfs.keys():
            dfs[key].to_excel(writer, key)

        writer.save()

        return logger

    def save_json(self, file_path):
        """
        
        :param file_path: 
        :return: 
        """

        from GridCal.Engine.Importers.JSON_parser import save_json_file
        logger = save_json_file(file_path, self)
        return logger

    def save_cim(self, file_path):
        """

        :param file_path:
        :return:
        """

        from GridCal.Engine.Importers.CIM import CIMExport

        cim = CIMExport(self)

        cim.save(file_name=file_path)

        return cim.logger

    def save_calculation_objects(self, file_path):
        """
        Save all the calculation objects of all the grids
        Args:
            file_path: path to file

        Returns:

        """

        print('Compiling...', end='')
        numerical_circuit = self.compile()
        calculation_inputs = numerical_circuit.compute()

        writer = pd.ExcelWriter(file_path)

        for c, calc_input in enumerate(calculation_inputs):

            for elm_type in calc_input.available_structures:
                name = elm_type + '_' + str(c)
                df = calc_input.get_structure(elm_type).astype(str)
                df.to_excel(writer, name)

        writer.save()

    def build_graph(self):
        """
        Build graph
        :return: self.graph
        """
        self.graph = nx.DiGraph()

        self.bus_dictionary = {bus: i for i, bus in enumerate(self.buses)}

        for i, branch in enumerate(self.branches):
            f = self.bus_dictionary[branch.bus_from]
            t = self.bus_dictionary[branch.bus_to]
            self.graph.add_edge(f, t)

        return self.graph

    def compile(self, use_opf_vals=False, opf_time_series_results=None, logger=list()):
        """
        Compile the circuit assets into an equivalent circuit that only contains matrices and vectors for calculation
        :param use_opf_vals:
        :param opf_time_series_results:
        :param logger:
        :return:
        """
        n = len(self.buses)
        m = len(self.branches)
        if self.time_profile is not None:
            n_time = len(self.time_profile)
        else:
            n_time = 0

        if use_opf_vals and opf_time_series_results is None:
            raise Exception('You want to use the OPF results but none is passed')

        self.bus_dictionary = dict()

        # Element count
        n_ld = 0
        n_ctrl_gen = 0
        n_sta_gen = 0
        n_batt = 0
        n_sh = 0
        for bus in self.buses:
            n_ld += len(bus.loads)
            n_ctrl_gen += len(bus.controlled_generators)
            n_sta_gen += len(bus.static_generators)
            n_batt += len(bus.batteries)
            n_sh += len(bus.shunts)

        # declare the numerical circuit
        circuit = NumericalCircuit(n_bus=n, n_br=m, n_ld=n_ld, n_ctrl_gen=n_ctrl_gen,
                                   n_sta_gen=n_sta_gen, n_batt=n_batt, n_sh=n_sh,
                                   n_time=n_time, Sbase=self.Sbase)

        # set hte time array profile
        if n_time > 0:
            circuit.time_array = self.time_profile

        # compile the buses and the shunt devices
        i_ld = 0
        i_ctrl_gen = 0
        i_sta_gen = 0
        i_batt = 0
        i_sh = 0
        self.bus_names = np.zeros(n, dtype=object)
        for i, bus in enumerate(self.buses):

            # bus parameters
            self.bus_names[i] = bus.name
            circuit.bus_names[i] = bus.name
            circuit.bus_vnom[i] = bus.Vnom  # kV
            circuit.Vmax[i] = bus.Vmax
            circuit.Vmin[i] = bus.Vmin
            circuit.bus_types[i] = bus.determine_bus_type().value[0]

            # Add buses dictionary entry
            self.bus_dictionary[bus] = i

            for elm in bus.loads:
                circuit.load_names[i_ld] = elm.name
                circuit.load_power[i_ld] = elm.S
                circuit.load_current[i_ld] = elm.I
                circuit.load_admittance[i_ld] = elm.Y
                circuit.load_enabled[i_ld] = elm.active
                circuit.load_mttf[i_ld] = elm.mttf
                circuit.load_mttr[i_ld] = elm.mttr

                if n_time > 0:
                    circuit.load_power_profile[:, i_ld] = elm.Sprof.values[:, 0]
                    circuit.load_current_profile[:, i_ld] = elm.Iprof.values[:, 0]
                    circuit.load_admittance_profile[:, i_ld] = np.nan_to_num(1 / elm.Zprof.values[:, 0])

                    if use_opf_vals:
                        # subtract the load shedding from the generation
                        circuit.load_power_profile[:, i_ld] -= opf_time_series_results.load_shedding[:, i_ctrl_gen]

                circuit.C_load_bus[i_ld, i] = 1
                i_ld += 1

            for elm in bus.static_generators:
                circuit.static_gen_names[i_sta_gen] = elm.name
                circuit.static_gen_power[i_sta_gen] = elm.S
                circuit.static_gen_enabled[i_sta_gen] = elm.active
                circuit.static_gen_mttf[i_sta_gen] = elm.mttf
                circuit.static_gen_mttr[i_sta_gen] = elm.mttr
                # circuit.static_gen_dispatchable[i_sta_gen] = elm.enabled_dispatch

                if n_time > 0:
                    circuit.static_gen_power_profile[:, i_sta_gen] = elm.Sprof.values[:, 0]

                circuit.C_sta_gen_bus[i_sta_gen, i] = 1
                i_sta_gen += 1

            for elm in bus.controlled_generators:
                circuit.controlled_gen_names[i_ctrl_gen] = elm.name
                circuit.controlled_gen_power[i_ctrl_gen] = elm.P
                circuit.controlled_gen_voltage[i_ctrl_gen] = elm.Vset
                circuit.controlled_gen_qmin[i_ctrl_gen] = elm.Qmin
                circuit.controlled_gen_qmax[i_ctrl_gen] = elm.Qmax
                circuit.controlled_gen_pmin[i_ctrl_gen] = elm.Pmin
                circuit.controlled_gen_pmax[i_ctrl_gen] = elm.Pmax
                circuit.controlled_gen_enabled[i_ctrl_gen] = elm.active
                circuit.controlled_gen_dispatchable[i_ctrl_gen] = elm.enabled_dispatch
                circuit.controlled_gen_mttf[i_ctrl_gen] = elm.mttf
                circuit.controlled_gen_mttr[i_ctrl_gen] = elm.mttr

                if n_time > 0:
                    # power profile
                    if use_opf_vals:
                        circuit.controlled_gen_power_profile[:, i_ctrl_gen] = \
                            opf_time_series_results.controlled_generator_power[:, i_ctrl_gen]
                    else:
                        circuit.controlled_gen_power_profile[:, i_ctrl_gen] = elm.Pprof.values[:, 0]

                    # Voltage profile
                    circuit.controlled_gen_voltage_profile[:, i_ctrl_gen] = elm.Vsetprof.values[:, 0]

                circuit.C_ctrl_gen_bus[i_ctrl_gen, i] = 1
                circuit.V0[i] *= elm.Vset
                i_ctrl_gen += 1

            for elm in bus.batteries:
                # 'name', 'bus', 'active', 'P', 'Vset', 'Snom', 'Enom',
                # 'Qmin', 'Qmax', 'Pmin', 'Pmax', 'Cost', 'enabled_dispatch', 'mttf', 'mttr',
                # 'soc_0', 'max_soc', 'min_soc', 'charge_efficiency', 'discharge_efficiency'
                circuit.battery_names[i_batt] = elm.name
                circuit.battery_power[i_batt] = elm.P
                circuit.battery_voltage[i_batt] = elm.Vset
                circuit.battery_qmin[i_batt] = elm.Qmin
                circuit.battery_qmax[i_batt] = elm.Qmax
                circuit.battery_enabled[i_batt] = elm.active
                circuit.battery_dispatchable[i_batt] = elm.enabled_dispatch
                circuit.battery_mttf[i_batt] = elm.mttf
                circuit.battery_mttr[i_batt] = elm.mttr

                circuit.battery_pmin[i_batt] = elm.Pmin
                circuit.battery_pmax[i_batt] = elm.Pmax
                circuit.battery_Enom[i_batt] = elm.Enom
                circuit.battery_soc_0[i_batt] = elm.soc_0
                circuit.battery_discharge_efficiency[i_batt] = elm.discharge_efficiency
                circuit.battery_charge_efficiency[i_batt] = elm.charge_efficiency
                circuit.battery_min_soc[i_batt] = elm.min_soc
                circuit.battery_max_soc[i_batt] = elm.max_soc

                if n_time > 0:
                    # power profile
                    if use_opf_vals:
                        circuit.battery_power_profile[:, i_batt] = \
                            opf_time_series_results.battery_power[:, i_batt]
                    else:
                        circuit.battery_power_profile[:, i_batt] = elm.Pprof.values[:, 0]
                    # Voltage profile
                    circuit.battery_voltage_profile[:, i_batt] = elm.Vsetprof.values[:, 0]

                circuit.C_batt_bus[i_batt, i] = 1
                circuit.V0[i] *= elm.Vset
                i_batt += 1

            for elm in bus.shunts:
                circuit.shunt_names[i_sh] = elm.name
                circuit.shunt_admittance[i_sh] = elm.Y
                circuit.shunt_mttf[i_sh] = elm.mttf
                circuit.shunt_mttr[i_sh] = elm.mttr

                if n_time > 0:
                    circuit.shunt_admittance_profile[:, i_sh] = elm.Yprof.values[:, 0]

                circuit.C_shunt_bus[i_sh, i] = 1
                i_sh += 1

        # Compile the branches
        self.branch_names = np.zeros(m, dtype=object)
        for i, branch in enumerate(self.branches):

            self.branch_names[i] = branch.name
            f = self.bus_dictionary[branch.bus_from]
            t = self.bus_dictionary[branch.bus_to]

            # connectivity
            circuit.C_branch_bus_f[i, f] = 1
            circuit.C_branch_bus_t[i, t] = 1
            circuit.F[i] = f
            circuit.T[i] = t

            # name and state
            circuit.branch_names[i] = branch.name
            circuit.branch_states[i] = branch.active
            circuit.br_mttf[i] = branch.mttf
            circuit.br_mttr[i] = branch.mttr

            # impedance and tap
            circuit.R[i] = branch.R
            circuit.X[i] = branch.X
            circuit.G[i] = branch.G
            circuit.B[i] = branch.B
            circuit.br_rates[i] = branch.rate
            circuit.tap_mod[i] = branch.tap_module
            circuit.tap_ang[i] = branch.angle

            # tap changer
            circuit.is_bus_to_regulated[i] = branch.bus_to_regulated
            circuit.tap_position[i] = branch.tap_changer.tap
            circuit.min_tap[i] = branch.tap_changer.min_tap
            circuit.max_tap[i] = branch.tap_changer.max_tap
            circuit.tap_inc_reg_up[i] = branch.tap_changer.inc_reg_up
            circuit.tap_inc_reg_down[i] = branch.tap_changer.inc_reg_down
            circuit.vset[i] = branch.vset

            # switches
            if branch.branch_type == BranchType.Switch:
                circuit.switch_indices.append(i)

            # virtual taps for transformers where the connection voltage is off
            elif branch.branch_type == BranchType.Transformer:
                circuit.tap_f[i], circuit.tap_t[i] = branch.get_virtual_taps()

        # Assign and return
        self.numerical_circuit = circuit
        return self.numerical_circuit

    def create_profiles(self, steps, step_length, step_unit, time_base: datetime = datetime.now()):
        """
        Set the default profiles in all the objects enabled to have profiles
        Args:
            steps: Number of time steps
            step_length: time length (1, 2, 15, ...)
            step_unit: unit of the time step
            time_base: Date to start from
        """

        index = [None] * steps
        for i in range(steps):
            if step_unit == 'h':
                index[i] = time_base + timedelta(hours=i * step_length)
            elif step_unit == 'm':
                index[i] = time_base + timedelta(minutes=i * step_length)
            elif step_unit == 's':
                index[i] = time_base + timedelta(seconds=i * step_length)

        self.format_profiles(index)

    def format_profiles(self, index):
        """
        Format the pandas profiles in place using a time index
        Args:
            index: Time profile
        """

        self.time_profile = np.array(index)

        for bus in self.buses:

            for elm in bus.loads:
                elm.create_profiles(index)

            for elm in bus.static_generators:
                elm.create_profiles(index)

            for elm in bus.controlled_generators:
                elm.create_profiles(index)

            for elm in bus.batteries:
                elm.create_profiles(index)

            for elm in bus.shunts:
                elm.create_profiles(index)

    def get_node_elements_by_type(self, element_type):
        """
        Get set of elements and their parent nodes
        Args:
            element_type: String {'Load', 'StaticGenerator', 'ControlledGenerator', 'Battery', 'Shunt'}

        Returns: List of elements, list of matching parent buses
        """
        elements = list()
        parent_buses = list()

        if element_type == 'Load':
            for bus in self.buses:
                for elm in bus.loads:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'StaticGenerator':
            for bus in self.buses:
                for elm in bus.static_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'ControlledGenerator':
            for bus in self.buses:
                for elm in bus.controlled_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'Battery':
            for bus in self.buses:
                for elm in bus.batteries:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'Shunt':
            for bus in self.buses:
                for elm in bus.shunts:
                    elements.append(elm)
                    parent_buses.append(bus)

        return elements, parent_buses

    def set_power(self, S):
        """
        Set the power array in the circuits
        @param S: Array of power values in MVA for all the nodes in all the islands
        """
        for circuit_island in self.circuits:
            idx = circuit_island.bus_original_idx  # get the buses original indexing in the island
            circuit_island.power_flow_input.Sbus = S[idx]  # set the values

    def add_bus(self, obj: Bus):
        """
        Add bus keeping track of it as object
        @param obj:
        """
        self.buses.append(obj)

    def delete_bus(self, obj: Bus):
        """
        Remove bus
        @param obj: Bus object
        """

        # remove associated branches in reverse order
        for i in range(len(self.branches) - 1, -1, -1):
            if self.branches[i].bus_from == obj or self.branches[i].bus_to == obj:
                self.branches.pop(i)

        # remove the bus itself
        self.buses.remove(obj)

    def add_branch(self, obj: Branch):
        """
        Add a branch object to the circuit
        @param obj: Branch object
        """
        self.branches.append(obj)

    def delete_branch(self, obj: Branch):
        """
        Delete a branch object from the circuit
        @param obj:
        """
        self.branches.remove(obj)

    def add_load(self, bus: Bus, api_obj=None):
        """
        Add load object to a bus
        Args:
            bus: Bus object
            api_obj: Load object
        """
        if api_obj is None:
            api_obj = Load()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        if api_obj.name == 'Load':
            api_obj.name += '@' + bus.name

        bus.loads.append(api_obj)

        return api_obj

    def add_controlled_generator(self, bus: Bus, api_obj=None):
        """
        Add controlled generator to a bus
        Args:
            bus: Bus object
            api_obj: ControlledGenerator object
        """
        if api_obj is None:
            api_obj = ControlledGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.controlled_generators.append(api_obj)

        return api_obj

    def add_static_generator(self, bus: Bus, api_obj=None):
        """
        Add a static generator object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: StaticGenerator object
        """
        if api_obj is None:
            api_obj = StaticGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.static_generators.append(api_obj)

        return api_obj

    def add_battery(self, bus: Bus, api_obj=None):
        """
        Add battery object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: Battery object to add it to
        """
        if api_obj is None:
            api_obj = Battery()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.batteries.append(api_obj)

        return api_obj

    def add_shunt(self, bus: Bus, api_obj=None):
        """
        Add shunt object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: Shunt object
        """
        if api_obj is None:
            api_obj = Shunt()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.shunts.append(api_obj)

        return api_obj

    def add_wire(self, obj: Wire):
        """
        Add wire object
        :param obj: Wire object
        """
        self.wire_types.append(obj)

    def delete_wire(self, i):
        """
        Remove wire
        :param i: index
        """
        self.wire_types.pop(i)

    def add_overhead_line(self, obj: Tower):
        """
        Add overhead line
        :param obj: Tower object
        """
        self.overhead_line_types.append(obj)

    def delete_overhead_line(self, i):

        self.overhead_line_types.pop(i)

    def add_underground_line(self, obj: UndergroundLineType):

        self.underground_cable_types.append(obj)

    def delete_underground_line(self, i):

        self.underground_cable_types.pop(i)

    def add_sequence_line(self, obj: SequenceLineType):

        self.sequence_line_types.append(obj)

    def delete_sequence_line(self, i):

        self.sequence_line_types.pop(i)

    def add_transformer_type(self, obj: TransformerType):

        self.transformer_types.append(obj)

    def delete_transformer_type(self, i):

        self.transformer_types.pop(i)

    def apply_all_branch_types(self):
        """
        Apply all the branch types
        """
        logger = list()
        for branch in self.branches:
            branch.apply_template(branch.template, self.Sbase, logger=logger)

        return logger

    def plot_graph(self, ax=None):
        """
        Plot the grid
        @param ax: Matplotlib axis object
        @return: Nothing
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        nx.draw_spring(self.graph, ax=ax)

    def export_pf(self, file_name, power_flow_results):
        """
        Export power flow results to file
        :param file_name: Excel file name
        :return: Nothing
        """

        if power_flow_results is not None:
            df_bus, df_branch = power_flow_results.export_all()

            df_bus.index = self.bus_names
            df_branch.index = self.branch_names

            writer = pd.ExcelWriter(file_name)
            df_bus.to_excel(writer, 'Bus results')
            df_branch.to_excel(writer, 'Branch results')
            writer.save()
        else:
            raise Exception('There are no power flow results!')

    def export_profiles(self, file_name):
        """
        Export object profiles to file
        :param file_name: Excel file name
        :return: Nothing
        """

        if self.time_profile is not None:

            # collect data
            P = list()
            Q = list()
            Ir = list()
            Ii = list()
            G = list()
            B = list()
            P_gen = list()
            V_gen = list()
            E_batt = list()

            load_names = list()
            gen_names = list()
            bat_names = list()

            for bus in self.buses:

                for elm in bus.loads:
                    load_names.append(elm.name)
                    P.append(elm.Sprof.values.real[:, 0])
                    Q.append(elm.Sprof.values.imag[:, 0])

                    Ir.append(elm.Iprof.values.real[:, 0])
                    Ii.append(elm.Iprof.values.imag[:, 0])

                    G.append(elm.Zprof.values.real[:, 0])
                    B.append(elm.Zprof.values.imag[:, 0])

                for elm in bus.controlled_generators:
                    gen_names.append(elm.name)

                    P_gen.append(elm.Pprof.values[:, 0])
                    V_gen.append(elm.Vsetprof.values[:, 0])

                for elm in bus.batteries:
                    bat_names.append(elm.name)
                    gen_names.append(elm.name)
                    P_gen.append(elm.Pprof.values[:, 0])
                    V_gen.append(elm.Vsetprof.values[:, 0])
                    E_batt.append(elm.energy_array.values[:, 0])

            # form DataFrames
            P = pd.DataFrame(data=np.array(P).transpose(), index=self.time_profile, columns=load_names)
            Q = pd.DataFrame(data=np.array(Q).transpose(), index=self.time_profile, columns=load_names)
            Ir = pd.DataFrame(data=np.array(Ir).transpose(), index=self.time_profile, columns=load_names)
            Ii = pd.DataFrame(data=np.array(Ii).transpose(), index=self.time_profile, columns=load_names)
            G = pd.DataFrame(data=np.array(G).transpose(), index=self.time_profile, columns=load_names)
            B = pd.DataFrame(data=np.array(B).transpose(), index=self.time_profile, columns=load_names)
            P_gen = pd.DataFrame(data=np.array(P_gen).transpose(), index=self.time_profile, columns=gen_names)
            V_gen = pd.DataFrame(data=np.array(V_gen).transpose(), index=self.time_profile, columns=gen_names)
            E_batt = pd.DataFrame(data=np.array(E_batt).transpose(), index=self.time_profile, columns=bat_names)

            writer = pd.ExcelWriter(file_name)
            P.to_excel(writer, 'P loads')
            Q.to_excel(writer, 'Q loads')

            Ir.to_excel(writer, 'Ir loads')
            Ii.to_excel(writer, 'Ii loads')

            G.to_excel(writer, 'G loads')
            B.to_excel(writer, 'B loads')

            P_gen.to_excel(writer, 'P generators')
            V_gen.to_excel(writer, 'V generators')

            E_batt.to_excel(writer, 'Energy batteries')
            writer.save()
        else:
            raise Exception('There are no time series!')

    def copy(self):
        """
        Returns a deep (true) copy of this circuit
        @return:
        """

        cpy = MultiCircuit()

        cpy.name = self.name

        bus_dict = dict()
        for bus in self.buses:
            bus_cpy = bus.copy()
            bus_dict[bus] = bus_cpy
            cpy.add_bus(bus_cpy)

        for branch in self.branches:
            cpy.add_branch(branch.copy(bus_dict))

        cpy.time_profile = self.time_profile

        return cpy

    def dispatch(self):
        """
        Dispatch either load or generation using a simple equalised share rule of the shedding to be done
        @return: Nothing
        """
        if self.numerical_circuit is not None:

            # get the total power balance
            balance = abs(self.numerical_circuit.Sbus.sum())

            if balance > 0:  # more generation than load, dispatch generation
                Gmax = 0
                Lt = 0
                for bus in self.buses:
                    for load in bus.loads:
                        Lt += abs(load.S)
                    for gen in bus.controlled_generators:
                        Gmax += abs(gen.Snom)

                # reassign load
                factor = Lt / Gmax
                print('Decreasing generation by ', factor * 100, '%')
                for bus in self.buses:
                    for gen in bus.controlled_generators:
                        gen.P *= factor

            elif balance < 0:  # more load than generation, dispatch load

                Gmax = 0
                Lt = 0
                for bus in self.buses:
                    for load in bus.loads:
                        Lt += abs(load.S)
                    for gen in bus.controlled_generators:
                        Gmax += abs(gen.P + 1j * gen.Qmax)

                # reassign load
                factor = Gmax / Lt
                print('Decreasing load by ', factor * 100, '%')
                for bus in self.buses:
                    for load in bus.loads:
                        load.S *= factor

            else:  # nothing to do
                pass

        else:
            warn('The grid must be compiled before dispatching it')

    def set_state(self, t):
        """
        Set the profiles state at the index t as the default values
        :param t:
        :return:
        """
        for bus in self.buses:
            bus.set_state(t)



