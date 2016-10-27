# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os
import sys
from copy import deepcopy
from os.path import basename, splitext, exists
from sys import stderr
from warnings import warn

import networkx as nx
from matplotlib import pyplot as plt
from numpy import argsort, arange, concatenate, finfo, array, zeros, c_, ndim, any
from scipy.io import loadmat, savemat
from scipy.sparse import issparse, vstack, hstack

from grid.ImportParsers.matpower_parser import parse_matpower_file
# from grid import run_userfcn

from grid.ImportParsers.DGS_Parser import read_DGS

from grid.MonteCarlo import *

# from typing import TypeVar

PY2 = sys.version_info[0] == 2
EPS = finfo(float).eps


"""
Defines constants for named column indices to areas matrix.

The index, name and meaning of each column of the areas matrix is given below:

columns 0-1
    0.  C{AREA_I}           area number
    1.  C{PRICE_REF_BUS}    price reference bus for this area

@author: Ray Zimmerman (PSERC Cornell)
@author: Richard Lincoln
@author: Santiago Peñate Vera
"""

# define the indices
AREA_I = 0    # area number
PRICE_REF_BUS = 1    # price reference bus for this area

if not PY2:
    basestring = str


class Circuit(object):
    """
    This class:
        stores the circuit data (fragmented in islands or not)
        stores the instances of the solvers.
        Provides graph calculation and plotting
    """
    def __init__(self, filename=None, is_file=False, data_in_zero_base=False, is_an_island=False):

        self.baseMVA = 100

        # Structures
        self.bus = None

        self.gen = None

        self.branch = None

        self.available_data_structures = ["Buses", "Generators", "Branches", "YBus matrix", "Sbus vector"]

        self.is_an_island = is_an_island

        self.grid_survives = True

        self.circuit_graph = None

        self.bus_names = None

        self.branch_names = None

        self.gen_names = None

        # Solvers
        self.power_flow = None # Power flow instance

        self.time_series = None  # time series instance

        self.monte_carlo = None  # MonteCarlo instance

        self.stochastic_collocation = None  # MonteCarlo instance

        self.voltage_stability = None  # voltage stability instance

        # default arguments
        if filename is not None:

            if is_file:
                name, file_extension = os.path.splitext(filename)
                print(name, file_extension)
                if file_extension == '.xls' or file_extension == '.xlsx':
                    ppc = load_from_xls(filename)
                    data_in_zero_base = True
                elif file_extension == '.dgs':
                    ppc = load_from_dgs(filename)
                elif file_extension == '.m':
                    ppc = parse_matpower_file(filename)
                    data_in_zero_base = True

            else:
                # read data
                ppc = loadcase(filename)

                # add the results columns to the branch structure, if needed
                if ppc["branch"].shape[1] < QT:
                    ppc["branch"] = c_[ppc["branch"],
                                       zeros((ppc["branch"].shape[0],
                                              QT - ppc["branch"].shape[1] + 1))]

            if not data_in_zero_base:
                # convert the 1-indexing to internal indexing
                # ppc = ext2int(ppc)

                # pass to 0-indexing
                bus = ppc["bus"]
                gen = ppc["gen"]
                branch = ppc["branch"]
                for i in range(len(bus)):
                    #  i is the new bus index, the old bus index
                    # has to be replaced in the branches
                    # and generation structures
                    old_i = bus[i, BUS_I]

                    for k in range(len(gen)):
                        if gen[k, GEN_BUS] == old_i:
                            gen[k, GEN_BUS] = i

                    for k in range(len(branch)):
                        if branch[k, F_BUS] == old_i:
                            branch[k, F_BUS] = i
                        elif branch[k, T_BUS] == old_i:
                            branch[k, T_BUS] = i
                    bus[i, BUS_I] = int(i)
                ppc["bus"] = bus
                ppc["gen"] = gen
                ppc["branch"] = branch

            # set the structures into the correct shape
            nb, b_cols_in = np.shape(ppc["bus"])
            nl, l_cols_in = np.shape(ppc["branch"])
            ng, g_cols_in = np.shape(ppc["gen"])

            b_cols = len(bus_headers)
            g_cols = len(gen_headers)
            l_cols = len(branch_headers)

            self.bus = zeros((nb, b_cols))
            self.gen = zeros((ng, g_cols))
            self.branch = zeros((nl, l_cols))

            self.baseMVA = ppc["baseMVA"]
            self.bus[:, range(b_cols_in)] = ppc["bus"].copy()
            self.gen[:, range(g_cols_in)] = ppc["gen"].copy()
            self.branch[:, range(l_cols_in)] = ppc["branch"].copy()

            # if the format is extended apply the default properties like ACTIVE = 1 in all branches
            if l_cols_in < l_cols:
                self.branch[:, O_INDEX] = list(range(nl))

            # for the circuit full graph (including unavailable branches)
            self.circuit_graph = self.get_graph()

            if np.count_nonzero(self.bus[:, BUS_X]) == 0:
                # no bus positions are provided, calculate the spectral positions
                # self.graph_pos = nx.spectral_layout(self.circuit_graph)
                D = nx.floyd_warshall_numpy(self.circuit_graph, nodelist=None, weight='weight')
                try:
                    self.graph_pos = self.cmdscale(D)
                except:
                    self.graph_pos = nx.spectral_layout(self.circuit_graph)
                for i in range(len(self.bus)):
                    x, y = self.graph_pos[i]
                    self.bus[i, BUS_X] = x
                    self.bus[i, BUS_Y] = y
                print("Using spectral positions")
            else:
                # use the bus structure provided positions
                self.graph_pos = self.get_bus_pos_dictionary()
                print("Using file positions")

            # initialize the solvers (at this point the circuit should have loaded the data)
            self.initialize_solvers()

            # assign the profiles
            if 'Lprof' in ppc.keys():
                self.time_series.set_master_time(ppc['master_time'])
                self.time_series.load_profiles = ppc['Lprof'].astype(np.complex)

            if 'LprofQ' in ppc.keys():
                self.time_series.load_profiles += 1j * ppc['LprofQ']

            if 'Gprof' in ppc.keys():
                if not self.time_series.is_ready():
                    self.time_series.set_master_time(ppc['master_time'])
                self.time_series.gen_profiles = ppc['Gprof']

            # set names
            if 'bus_names' in ppc.keys():
                self.bus_names = ppc['bus_names']
            else:
                self.bus_names = self.get_bus_labels()

            if 'branch_names' in ppc.keys():
                self.branch_names = ppc['branch_names']
            else:
                self.branch_names = self.get_branch_labels()

            if 'gen_names' in ppc.keys():
                self.gen_names = ppc['gen_names']
            else:
                self.gen_names = self.get_gen_labels()

            print('Circuit loaded!')

    def initialize_solvers(self):
        """
        Initializes instances of all the solvers (Power Flow, Time Series, etc...)
        @return: Nothing
        """

        self.initialize_power_flow_solver()

        if self.power_flow is not None:

            self.time_series = TimeSeries(self.power_flow)

            self.voltage_stability = MultiCircuitVoltageStability(self.baseMVA, self.bus, self.gen, self.branch,
                                                                  self.circuit_graph, solver_type=SolverType.NR)

    def initialize_power_flow_solver(self, solver_type=SolverType.IWAMOTO):
        """
        Initializes a power flow instance with the current circuit values
        Args:
            solver_type:

        Returns:

        """
        self.power_flow = MultiCircuitPowerFlow(self.baseMVA, self.bus, self.gen, self.branch,
                                                self.circuit_graph, solver_type=solver_type)

    def initialize_TimeSeries(self):
        """

        @return:
        """
        if self.time_series is None:
            self.initialize_power_flow_solver()
            self.time_series = TimeSeries(self.power_flow)
        else:
            self.initialize_power_flow_solver()
            self.time_series.pf = self.power_flow

    def initialize_MonteCarlo(self, mode: TimeGroups):
        """
        Initializes a monte carlo solver instance
        @return:
        """
        if self.time_series is not None:
            self.initialize_TimeSeries()
            self.monte_carlo = MonteCarlo(self.time_series, mode)
            # self.monte_carlo = MonteCarloMultiThread(self.time_series, mode)
            self.stochastic_collocation = StochasticCollocation(self.time_series, level=2)
        else:
            print('No time series object ready')

    def run_time_series(self):
        """

        @param solver_type:
        @return:
        """
        # check that the instances exist
        if self.power_flow is None or self.time_series is None:
            self.initialize_solvers()

        self.time_series.run()

    def update_power_flow_results(self):
        """
        Updates the power flow object results to the circuit structures
        Returns:

        """
        if self.power_flow.has_results:
            # nodal results
            self.bus[:, VM] = abs(self.power_flow.voltage)
            self.bus[:, VA] = angle(self.power_flow.voltage, True)

            # Branch results
            self.branch[:, PF] = np.real(self.power_flow.power_from)
            self.branch[:, QF] = np.imag(self.power_flow.power_from)
            self.branch[:, PT] = np.real(self.power_flow.power_to)
            self.branch[:, QT] = np.imag(self.power_flow.power_to)
            self.branch[:, LOADING] = abs(self.power_flow.loading)
            self.branch[:, BR_CURRENT] = abs(self.power_flow.current)
            self.branch[:, LOSSES] = abs(self.power_flow.losses)
        else:
            warn('No results in the power flow object to update the circuit.')

    def set_branch_status(self, lits_of_edges, status=1):
        """
        Set the branches status
        """
        for e in lits_of_edges:
            f = e[0]
            t = e[1]
            for i in range(len(self.branch)):
                ff = int(self.branch[i, F_BUS])
                tt = int(self.branch[i, T_BUS])
                if f == ff and t == tt:
                    self.branch[i, BR_STATUS] = status

    def get_graph(self):
        """
        Composes a graph of the grid where the buses are the vertex and the branches are the edges

        Returns:
            g: NetworkX graph structure
        """
        # from ..reliability.graphs import nx

        nb = len(self.bus)
        nl = len(self.branch)

        g = nx.MultiGraph()  # allows more than one edge per node pair

        # include the buses: There might be buses without connections
        for i in range(nb):
            b_idx = int(self.bus[i, BUS_I])
            g.add_node(b_idx)

        # include branches
        for i in range(nl):
            # if int(self.branch[i, BR_STATUS]) > 0:  # if the branch is on-line:
            f = int(self.branch[i, F_BUS])
            t = int(self.branch[i, T_BUS])

            z = abs(self.branch[i, BR_R] + 1j * self.branch[i, BR_X])
            g.add_edge(f, t, weight=z)

        # print(len(g.edges()))
        # print(c-1)
        return g

    def get_failed_edges(self):
        """
        Returns a list of tuples with the failed edges
        """
        if self.branch is not None:
            nl = len(self.branch)
            failed_edges = list()

            for i in range(nl):
                f = int(self.branch[i, F_BUS])
                t = int(self.branch[i, T_BUS])
                status = int(self.branch[i, BR_STATUS])

                if status == 0:
                    failed_edges.append((f, t))

            return failed_edges
        else:
            return None

    def get_working_edges(self):
        """
        Returns a list of tuples with the failed edges
        """
        if self.branch is not None:
            nl = len(self.branch)
            working_edges = list()
            idx = list()
            for i in range(nl):
                f = int(self.branch[i, F_BUS])
                t = int(self.branch[i, T_BUS])
                status = int(self.branch[i, BR_STATUS])

                if status == 1:
                    working_edges.append((f, t))
                    idx.append(i)

            return working_edges, idx
        else:
            return None

    def get_working_and_failed_edges(self):
        """
        Returns a list of tuples with the failed edges
        """
        if self.branch is not None:
            idx_working = np.where(self.branch[:, BR_STATUS].astype(int) == 1)[0]
            idx_failed = np.where(self.branch[:, BR_STATUS].astype(int) == 0)[0]
            working_edges = [(int(self.branch[i, F_BUS]), int(self.branch[i, T_BUS])) for i in idx_working]
            failed_edges = [(int(self.branch[i, F_BUS]), int(self.branch[i, T_BUS])) for i in idx_failed]

            return working_edges, failed_edges, idx_working, idx_failed
        else:
            return None, None, None, None

    def get_working_and_collapsed_nodes(self):
        """
        Returns which indices are collapsed and which are not
        @return:
        """
        if self.bus is not None:
            if self.power_flow.has_results:
                collapsed = self.power_flow.collapsed_nodes
            else:
                collapsed = self.bus[:, COLLAPSED].astype(int)

            idx_working = np.where(collapsed == 0)[0]
            idx_failed = np.where(collapsed == 1)[0]
            return idx_working, idx_failed
        else:
            return None, None

    def get_bus_pos_dictionary(self):
        """
        Makes a dictionary of the buses positions where the key is the node index
        @return: dictionary[node] = position
        """

        d = dict()
        k = 0
        for i in self.bus[:, BUS_I]:
            d[i] = (self.bus[k, BUS_X], self.bus[k, BUS_Y])
            k += 1
        return d

    def get_node_dict(self, magnitude, indices=None):
        """
        """
        dictionary = dict()

        if indices is None:
            indices = range(len(self.bus))

        for i in indices:
            idx = self.bus[i, BUS_I].astype(int)
            strng = str(idx) + "\n" + str('% 6.3f' % magnitude[i])
            dictionary[idx] = strng
        return dictionary

    def get_branch_dict(self, magnitude):
        """
        """
        dictionary = dict()
        for i in range(len(self.branch)):
            dictionary[i] = magnitude[i]
        return dictionary

    def cmdscale(self, D):
        """
        Classical multidimensional scaling (MDS)

        Parameters
        ----------
        D : (n, n) array
            Symmetric distance matrix.

        Returns
        -------
        npos : (n, 2) array
            Configuration matrix. Each column represents a dimension. Only the
            p dimensions corresponding to positive eigenvalues of B are returned.
            Note that each dimension is only determined up to an overall sign,
            corresponding to a reflection.

        """
        from sklearn import manifold

        seed = np.random.RandomState(seed=3)
        mds = manifold.MDS(n_components=2, max_iter=3000, eps=1e-9, random_state=seed,
                           dissimilarity="precomputed", n_jobs=1)
        pos = mds.fit(D).embedding_

        # nmds = manifold.MDS(n_components=2, metric=False, max_iter=3000, eps=1e-12,
        #                     dissimilarity="precomputed", random_state=seed, n_jobs=1,
        #                     n_init=1)
        # npos = nmds.fit_transform(D, init=pos)

        return pos

    def plot_graph(self, ax, mode=1, pos=None, node_size=800):
        """
        Plots the circuit graph

        Args:
            ax: axis object to plot in

            mode: {0, 1, 2}
                0: Plot the graph with a single color
                1: Plot the graph using different colors per node type
                2: Plot the graph using the voltage and loading to color

            pos: Dictionary of the nodes position

            node_size: Size of the nodes
        """
        if pos is None:
            pos = nx.spectral_layout(self.circuit_graph)

        # clear
        ax.cla()

        if node_size is None:
            node_size = 12 * 100
        picker_thr = node_size / 100
        font_size = int(float(node_size / 160))

        if mode == 0:  # plot with the same colouring
            color = '#A0CBE2'
            node_artist = nx.draw_networkx_nodes(self.circuit_graph, pos=pos, node_color=color, with_labels=False,
                                                 node_size=node_size, ax=ax)

            node_labels = dict()
            for i in self.bus[:, BUS_I].astype(int):
                node_labels[self.bus[i, BUS_I].astype(int)] = i

            nx.draw_networkx_labels(self.circuit_graph, pos=pos, labels=node_labels, font_size=font_size, ax=ax)

            edge_artist = nx.draw_networkx_edges(self.circuit_graph, pos=pos, width=4, ax=ax)
            nx.draw(self.circuit_graph)

        elif mode == 1:  # color by node type

            working_edges, failed_edges, working_edges_idx, failed_edges_idx = self.get_working_and_failed_edges()

            none_color = "#0071FF"
            gen_vctrl_color = "#FF005D"
            gen_color = "#B200FF"
            load_color = "#FF8700"
            shunt_color = ""

            gen_idx_list = list(self.gen[:, GEN_BUS])

            # set node colors
            nb = len(self.bus)
            color = [None] * nb
            for i in range(nb):
                if i in gen_idx_list:
                    color[i] = gen_vctrl_color
                else:
                    if self.bus[i, PD] == 0 and self.bus[i, QD] == 0:
                        color[i] = none_color
                    elif self.bus[i, PD] > 0:  # load
                        color[i] = load_color
                    elif self.bus[i, PD] < 0:  # non controlled gen
                        color[i] = gen_color

            v = self.bus[:, VM]

            # generator info
            on = find(self.gen[:, GEN_STATUS] > 0)      # which generators are on?
            gbus = self.gen[on, GEN_BUS]                # what buses are they at?

            # form net complex bus power injection vector
            nb = self.bus.shape[0]
            ngon = on.shape[0]

            # connection matrix, element i, j is 1 if gen on(j) at bus i is ON
            Cg = sparse((ones(ngon), (gbus, range(ngon))), (nb, ngon))
            Sbus = (Cg * (self.gen[on, PG] + 1j * self.gen[on, QG]) - (self.bus[:, PD] + 1j * self.bus[:, QD])) / self.baseMVA

            node_labels = self.get_node_dict(Sbus.real)
            node_artist = nx.draw_networkx_nodes(self.circuit_graph, pos=pos, node_color=color, with_labels=False,
                                                 node_size=node_size, ax=ax)

            nx.draw_networkx_labels(self.circuit_graph, pos=pos, labels=node_labels, font_size=font_size, ax=ax)

            # edge_artist = nx.draw_networkx_edges(self.circuit_graph, pos=pos, width=4, ax=ax)
            edge_artist = nx.draw_networkx_edges(self.circuit_graph, pos, edgelist=working_edges, edge_color='black',
                                                 width=4, cmap=plt.get_cmap('rainbow'), ax=ax)

            if len(failed_edges) > 0:
                edge_artist2 = nx.draw_networkx_edges(self.circuit_graph, pos, edgelist=failed_edges, edge_color='black',
                                                      style='dashed', width=4, ax=ax)

        elif mode == 2:  # plot with results

            working_edges, failed_edges, working_edges_idx, failed_edges_idx = self.get_working_and_failed_edges()

            # define nodes #############################################################################################
            working_nodes_idx, collapsed_nodes_idx = self.get_working_and_collapsed_nodes()

            # plot nodes
            nb = len(self.bus)
            if self.power_flow.has_results:
                v = abs(self.power_flow.voltage)
                branch_loading = 100*abs(self.power_flow.loading[working_edges_idx])
            else:
                v = self.bus[:, VM]
                branch_loading = self.branch[working_edges_idx, LOADING]

            v_high = self.bus[:, VMAX]
            v_low = self.bus[:, VMIN]

            ok_color = '#A6FF00'  # nice green
            too_high_color = '#FF005D'  # nice red
            too_low_color = '#00A6FF'  # nice blue
            collapsed_color = '#494949'  # white

            node_color = array([collapsed_color] * nb)
            too_high_idx = np.where((v >= v_high) == 1)[0]
            too_low_idx = np.where((v <= v_low) == 1)[0]
            ok_idx = np.where((v > v_low).astype(np.bool) + (v < v_high).astype(np.bool) == 1)[0]

            node_color[ok_idx] = ok_color
            node_color[too_high_idx] = too_high_color
            node_color[too_low_idx] = too_low_color
            node_color[collapsed_nodes_idx] = collapsed_color
            node_color = node_color.tolist()

            node_artist = nx.draw_networkx_nodes(self.circuit_graph, pos=pos, node_color=node_color, with_labels=False,
                                                 node_size=node_size, ax=ax)

            # plot node labels
            node_labels = self.get_node_dict(v, working_nodes_idx)
            nx.draw_networkx_labels(self.circuit_graph, pos=pos, labels=node_labels, font_size=font_size, ax=ax)

            if len(collapsed_nodes_idx) > 0:
                node_labels = self.get_node_dict(v, collapsed_nodes_idx)
                nx.draw_networkx_labels(self.circuit_graph, pos=pos, labels=node_labels, font_size=font_size,
                                        font_color='#FFFFFF' , ax=ax)

            # define edges #############################################################################################

            edge_color = (255 * branch_loading).astype(int)

            # plot edges
            edge_artist = nx.draw_networkx_edges(self.circuit_graph, pos, edgelist=working_edges, edge_color=edge_color,
                                                 width=4, cmap=plt.get_cmap('rainbow'), ax=ax)

            if len(failed_edges) > 0:
                edge_artist2 = nx.draw_networkx_edges(self.circuit_graph, pos, edgelist=failed_edges, edge_color='black',
                                                      style='dashed', width=4, ax=ax)
                # edge_artist2.set_picker(picker_thr)

        # set pickers
        node_artist.set_picker(picker_thr)
        # edge_artist.set_picker(2)

        ax.set_aspect('equal', 'datalim')
        ax.set_axis_off()
        ax.grid(True)
        cf = ax.get_figure()
        cf.set_facecolor('w')
        return node_artist, mode

    def get_gen_labels(self):
        """
        Get an array of labels for the generators
        @return:
        """
        return ['Gen @bus ' + str(i) for i in self.gen[:, GEN_BUS].astype(int)]

    def get_bus_labels(self):
        """
        Get an array of labels for the nodes
        @return:
        """
        return ['Bus ' + str(i) for i in self.bus[:, BUS_I].astype(int)]

    def get_branch_labels(self):
        """
        Get an array of labels for the branches
        @return:
        """
        return ['Branch ' + str(i[0]) + '-' + str(i[1]) for i in self.branch[:, [F_BUS, T_BUS]].astype(int)]

    def save_circuit(self, filename):
        """
        Saves the circuit configuration and data structures to an excel file
        """
        dir_name = os.path.dirname(filename)
        name, file_extension = os.path.splitext(filename)

        if file_extension in ['.xls', '.xlsx']:
            import pandas as pd

            # Create a Pandas Excel writer using XlsxWriter as the engine.
            writer = pd.ExcelWriter(filename, engine='xlsxwriter')

            # write conf
            dta = zeros((2, 2), dtype=np.object)
            dta[0, 0] = "Property"
            dta[0, 1] = "Value"

            dta[1, 0] = "baseMVA"
            dta[1, 1] = self.baseMVA
            df = pd.DataFrame(data=dta)
            df.to_excel(writer, index=False, header=False, sheet_name='Conf')

            # write buses
            df = pd.DataFrame(data=self.bus, columns=bus_headers, index=self.bus_names)
            df.to_excel(writer, index=True, header=True, sheet_name='Bus')

            # write gen
            df = pd.DataFrame(data=self.gen, columns=gen_headers, index=self.gen_names)
            df.to_excel(writer, index=True, header=True, sheet_name='Gen')

            # write branch
            df = pd.DataFrame(data=self.branch, columns=branch_headers, index=self.branch_names)
            df.to_excel(writer, index=True, header=True, sheet_name='Branch')

            if self.time_series.is_ready():
                # write loads profile
                if self.time_series.load_profiles is not None:
                    cols = self.get_bus_labels()
                    # this only writes the real part
                    df = pd.DataFrame(data=self.time_series.load_profiles, columns=cols, index=self.time_series.time)
                    df.to_excel(writer, index=True, header=True, sheet_name='Lprof')

                    # we need to write the reactive part separately
                    df = pd.DataFrame(data=np.imag(self.time_series.load_profiles), columns=cols, index=self.time_series.time)
                    df.to_excel(writer, index=True, header=True, sheet_name='LprofQ')

                # write generators profile
                if self.time_series.gen_profiles is not None:
                    cols = self.get_gen_labels()
                    df = pd.DataFrame(data=self.time_series.gen_profiles, columns=cols, index=self.time_series.time)
                    df.to_excel(writer, index=True, header=True, sheet_name='Gprof')

            # Close the Pandas Excel writer and output the Excel file.
            writer.save()
        elif file_extension == '.npz':

            mcpf = MultiCircuitPowerFlow(self.baseMVA, self.bus, self.gen, self.branch, self.circuit_graph, solver_type=SolverType.NR)

            i = 1
            for pf in mcpf.island_circuits:
                # Save different numpy arrays for research purposes
                filename = name + '_' + str(i) + '.npz'

                pfs = pf.get_power_flow_instance()

                np.savez(filename, Y=pfs.Ybus.todense(), S=pfs.Sbus, Type=pfs.bus_types, V0=pfs.V0, Bdc=pfs.B)
                i += 1

        elif file_extension == '.json':
            import json

            # make dictionary of data
            json_dict = dict()

            # write conf
            json_dict["baseMVA"] = self.baseMVA

            # write buses
            json_dict["bus"] = self.bus.tolist()
            json_dict["bus_names"] = list(self.bus_names)

            # write gen
            json_dict["gen"] = self.gen.tolist()
            json_dict["gen_names"] = list(self.gen_names)

            # write branch
            json_dict["branch"] = self.branch.tolist()
            json_dict["branch_names"] = list(self.branch_names)

            if self.time_series.is_ready():
                # write loads profile
                if self.time_series.load_profiles is not None:
                    json_dict["time_profile"] = list(self.time_series.time.astype(np.str))
                    json_dict["load_profiles_P"] = np.real(self.time_series.load_profiles).tolist()
                    json_dict["load_profiles_Q"] = np.imag(self.time_series.load_profiles).tolist()

                # write generators profile
                if self.time_series.gen_profiles is not None:
                    json_dict["gen_profiles_P"] = self.time_series.gen_profiles.tolist()

            # json.dumps(json_dict, ensure_ascii=False)

            with open(filename, 'w') as outfile:
                json.dump(json_dict, outfile, ensure_ascii=False)

    def set_time_profile_state_to_the_circuit(self, t, Copy_Results_also):
        """
        Updates the current circuit structure with a snapshot of the time series
        Args:
            t:
            Copy_Results_also:

        Returns:

        """
        # set the input state
        if self.time_series.load_profiles is not None:
            load_s = self.time_series.load_profiles[t, :]
            self.bus[:, PD] = np.real(load_s)
            self.bus[:, QD] = np.imag(load_s)
        else:
            raise Warning('There are no load profiles')

        if self.time_series.gen_profiles is not None:
            pgen = self.time_series.gen_profiles[t, :]
            self.gen[:, PG] = pgen
        else:
            raise Warning('There are no generation profiles')

        if Copy_Results_also:
            v = self.time_series.voltages[t, :]
            ld = self.time_series.loadings[t, :]
            ls = self.time_series.losses[t, :]
            c = self.time_series.currents[t, :]

            # set the buses magnitudes
            self.bus[:, VM] = abs(v)
            self.bus[:, VA] = angle(v, True)

            # set the branches magnitudes
            self.branch[:, BR_CURRENT] = abs(c)
            self.branch[:, LOADING] = abs(ld)
            self.branch[:, LOSSES] = abs(ls)

    def frequency_calculation(self,
                              t0,
                              max_t_steps=1000,
                              dt=0.1,
                              fnom=50,
                              J=5000,
                              PG=45000.,
                              Droop=16.,
                              PG_ctrl=0.,
                              PD=40000.,
                              SRL_def=0.0,
                              AGC_P_def=0.0,
                              AGC_I_def=0.0,
                              K=0.0,
                              P_failure=-5000.):

        # Calculation variables (initialization)
        t = np.linspace(0, dt*max_t_steps, max_t_steps)
        dFreq = np.zeros(max_t_steps)
        Freq = np.zeros(max_t_steps)
        Load = np.zeros(max_t_steps)
        SRL = np.zeros(max_t_steps)
        Generation = np.zeros(max_t_steps)
        PC = np.zeros(max_t_steps)
        AGC_P = np.zeros(max_t_steps)
        AGC_I = np.zeros(max_t_steps)
        SC = np.zeros(max_t_steps)
        Inbalance = np.zeros(max_t_steps)

        # set the calculation function
        def iteration(i, accumulated_dFreq, load, gen):
            Load[i] = load
            Generation[i] = gen
            SRL[i] = dFreq[i] * Load[i] * SRL_def
            PC[i] = dFreq[i] / (Droop * fnom) * PG_ctrl
            AGC_P[i] = dFreq[i] * AGC_P_def * K
            AGC_I[i] = accumulated_dFreq * dt * AGC_I_def * K
            SC[i] = AGC_P[i] + AGC_I[i]
            Inbalance[i] = Generation[i] + PC[i] + SC[i] - Load[i] - SRL[i]

            dFreq[i+1] = dFreq[i] + (Inbalance[i]/J) * (t[i+1] - t[i])
            Freq[i+1] = fnom + dFreq[i]

        # initial values
        Freq[0] = fnom
        accumulated_dFreq = dFreq[0]

        # Calculation
        for i in range(max_t_steps-1):
            gen = PG
            if t[i] < t0:
                load = PD
            else:
                load = PD + P_failure
                #
                # if Freq[i] < 49.8:
                #     if P_failure > 0:
                #         load = Load[i-1] * 0.9
                #     else:
                #         gen = Generation[i-1] * 0.9

            iteration(i, accumulated_dFreq, load, gen)
            accumulated_dFreq += dFreq[i+1]

        return t, Freq

########################################################################################################################
# Functions outside the class
########################################################################################################################


def format_structure(arr, format_arr):
    """
    Formats numpy array by column using an array of format per column
    Args:
        arr: Numpy array to be formatted
        format_arr: Vector containing the format specification
    Returns:
        Formatted array
    """
    struct = np.zeros_like(arr)

    r, c = np.shape(arr)

    for col in range(c):
        struct[:, col] = arr[:, col].astype(format_arr[col])

    return struct


def ext2int(ppc, val_or_field=None, ordering=None, dim=0):
    """
    Converts external to internal indexing.

    This function has two forms, the old form that operates on
    and returns individual matrices and the new form that operates
    on and returns an entire PYPOWER case dict.

    1.  C{ppc = ext2int(ppc)}

    If the input is a single PYPOWER case dict, then all isolated
    buses, off-line generators and branches are removed along with any
    generators, branches or areas connected to isolated buses. Then the
    buses are renumbered consecutively, beginning at 0, and the
    generators are sorted by increasing bus number. Any 'ext2int'
    callback routines registered in the case are also invoked
    automatically. All of the related
    indexing information and the original data matrices are stored under
    the 'order' key of the dict to be used by C{int2ext} to perform
    the reverse conversions. If the case is already using internal
    numbering it is returned unchanged.

    Example::
        ppc = ext2int(ppc)

    @see: L{int2ext}, L{e2i_field}, L{e2i_data}

    @author: Ray Zimmerman (PSERC Cornell)
    """
    ppc = deepcopy(ppc)
    if val_or_field is None:  # nargin == 1
        first = 'order' not in ppc
        if first or ppc["order"]["state"] == 'e':
            # initialize order
            if first:
                o = {
                        'ext':      {
                                'bus':      None,
                                'branch':   None,
                                'gen':      None
                        },
                        'bus':      { 'e2i':      None,
                                      'i2e':      None,
                                      'status':   {}
                        },
                        'gen':      { 'e2i':      None,
                                      'i2e':      None,
                                      'status':   {}
                        },
                        'branch':   { 'status': {} }
                    }
            else:
                o = ppc["order"]

            # sizes
            nb = ppc["bus"].shape[0]
            ng = ppc["gen"].shape[0]
            ng0 = ng
            if 'A' in ppc:
                dc = True if ppc["A"].shape[1] < (2 * nb + 2 * ng) else False
            elif 'N' in ppc:
                dc = True if ppc["N"].shape[1] < (2 * nb + 2 * ng) else False
            else:
                dc = False

            # save data matrices with external ordering
            if 'ext' not in o: o['ext'] = {}
            o["ext"]["bus"] = ppc["bus"].copy()
            o["ext"]["branch"] = ppc["branch"].copy()
            o["ext"]["gen"] = ppc["gen"].copy()
            if 'areas' in ppc:
                if len(ppc["areas"]) == 0:  # if areas field is empty
                    del ppc['areas']        # delete it (so it's ignored)
                else:                       # otherwise
                    o["ext"]["areas"] = ppc["areas"].copy()  # save it

            # check that all buses have a valid BUS_TYPE
            bt = ppc["bus"][:, BUS_TYPE]
            err = find(~((bt == PQ) | (bt == PV) | (bt == REF) | (bt == NONE)))
            if len(err) > 0:
                sys.stderr.write('ext2int: bus %d has an invalid BUS_TYPE\n' % err)

            # determine which buses, branches, gens are connected and
            # in-service
            n2i = sparse((range(nb), (ppc["bus"][:, BUS_I], zeros(nb))),
                         shape=(max(ppc["bus"][:, BUS_I]) + 1, 1))
            n2i = array(n2i.todense().flatten())[0, :]  # as 1D array
            bs = (bt != NONE)                           # bus status
            o["bus"]["status"]["on"] = find(bs)         # connected
            o["bus"]["status"]["off"] = find(~bs)       # isolated
            gs = ((ppc["gen"][:, GEN_STATUS] > 0) &          # gen status
                   bs[n2i[ppc["gen"][:, GEN_BUS].astype(int)]])
            o["gen"]["status"]["on"] = find(gs)    # on and connected
            o["gen"]["status"]["off"] = find(~gs)    # off or isolated

            brs = (ppc["branch"][:, BR_STATUS].astype(int) &  # branch status
                    bs[n2i[ppc["branch"][:, F_BUS].astype(int)]] &
                    bs[n2i[ppc["branch"][:, T_BUS].astype(int)]]).astype(bool)

            o["branch"]["status"]["on"] = find(brs)  # on and conn
            o["branch"]["status"]["off"] = find(~brs)
            if 'areas' in ppc:
                ar = bs[ n2i[ppc["areas"][:, PRICE_REF_BUS].astype(int)] ]
                o["areas"] = {"status": {}}
                o["areas"]["status"]["on"] = find(ar)
                o["areas"]["status"]["off"] = find(~ar)

            # delete stuff that is "out"
            if len(o["bus"]["status"]["off"]) > 0:
                # ppc["bus"][o["bus"]["status"]["off"], :] = array([])
                ppc["bus"] = ppc["bus"][o["bus"]["status"]["on"], :]
            if len(o["branch"]["status"]["off"]) > 0:
                # ppc["branch"][o["branch"]["status"]["off"], :] = array([])
                ppc["branch"] = ppc["branch"][o["branch"]["status"]["on"], :]
            if len(o["gen"]["status"]["off"]) > 0:
                # ppc["gen"][o["gen"]["status"]["off"], :] = array([])
                ppc["gen"] = ppc["gen"][o["gen"]["status"]["on"], :]
            if 'areas' in ppc and (len(o["areas"]["status"]["off"]) > 0):
                # ppc["areas"][o["areas"]["status"]["off"], :] = array([])
                ppc["areas"] = ppc["areas"][o["areas"]["status"]["on"], :]

            # update size
            nb = ppc["bus"].shape[0]

            # apply consecutive bus numbering
            o["bus"]["i2e"] = ppc["bus"][:, BUS_I].copy()
            o["bus"]["e2i"] = zeros(max(o["bus"]["i2e"]) + 1)
            o["bus"]["e2i"][o["bus"]["i2e"].astype(int)] = arange(nb)
            ppc["bus"][:, BUS_I] = \
                o["bus"]["e2i"][ ppc["bus"][:, BUS_I].astype(int) ].copy()
            ppc["gen"][:, GEN_BUS] = \
                o["bus"]["e2i"][ ppc["gen"][:, GEN_BUS].astype(int) ].copy()
            ppc["branch"][:, F_BUS] = \
                o["bus"]["e2i"][ ppc["branch"][:, F_BUS].astype(int) ].copy()
            ppc["branch"][:, T_BUS] = \
                o["bus"]["e2i"][ ppc["branch"][:, T_BUS].astype(int) ].copy()
            if 'areas' in ppc:
                ppc["areas"][:, PRICE_REF_BUS] = \
                    o["bus"]["e2i"][ ppc["areas"][:,
                        PRICE_REF_BUS].astype(int) ].copy()

            # reorder gens in order of increasing bus number
            o["gen"]["e2i"] = argsort(ppc["gen"][:, GEN_BUS])
            o["gen"]["i2e"] = argsort(o["gen"]["e2i"])

            ppc["gen"] = ppc["gen"][o["gen"]["e2i"].astype(int), :]

            if 'int' in o:
                del o['int']
            o["state"] = 'i'
            ppc["order"] = o

            # update gencost, A and N
            if 'gencost' in ppc:
                ordering = ['gen']            # Pg cost only
                if ppc["gencost"].shape[0] == (2 * ng0):
                    ordering.append('gen')    # include Qg cost
                ppc = e2i_field(ppc, 'gencost', ordering)
            if 'A' in ppc or 'N' in ppc:
                if dc:
                    ordering = ['bus', 'gen']
                else:
                    ordering = ['bus', 'bus', 'gen', 'gen']
            if 'A' in ppc:
                ppc = e2i_field(ppc, 'A', ordering, 1)
            if 'N' in ppc:
                ppc = e2i_field(ppc, 'N', ordering, 1)

            # execute userfcn callbacks for 'ext2int' stage
            if 'userfcn' in ppc:
                ppc = run_userfcn(ppc['userfcn'], 'ext2int', ppc)
    else:                    # convert extra data
        if isinstance(val_or_field, str) or isinstance(val_or_field, list):
            # field
            warn('Calls of the form ppc = ext2int(ppc, '
                '\'field_name\', ...) have been deprecated. Please '
                'replace ext2int with e2i_field.', DeprecationWarning)
            gen, branch = val_or_field, ordering
            ppc = e2i_field(ppc, gen, branch, dim)

        else:
            # value
            warn('Calls of the form val = ext2int(ppc, val, ...) have been '
                 'deprecated. Please replace ext2int with e2i_data.',
                 DeprecationWarning)
            gen, branch = val_or_field, ordering
            ppc = e2i_data(ppc, gen, branch, dim)

    return ppc


def ext2int1(bus, gen, branch, areas=None):
    """Converts from (possibly non-consecutive) external bus numbers to
    consecutive internal bus numbers which start at 1. Changes are made
    to BUS, GEN, BRANCH and optionally AREAS matrices, which are returned
    along with a vector of indices I2E that can be passed to INT2EXT to
    perform the reverse conversion.

    @see: L{int2ext}
    @see: U{http://www.pserc.cornell.edu/matpower/}
    """
    i2e = bus[:, BUS_I].astype(int)
    e2i = zeros(max(i2e) + 1)
    e2i[i2e] = arange(bus.shape[0])

    bus[:, BUS_I]    = e2i[ bus[:, BUS_I].astype(int)    ]
    gen[:, GEN_BUS]  = e2i[ gen[:, GEN_BUS].astype(int)  ]
    branch[:, F_BUS] = e2i[ branch[:, F_BUS].astype(int) ]
    branch[:, T_BUS] = e2i[ branch[:, T_BUS].astype(int) ]
    if areas is not None and len(areas) > 0:
        areas[:, PRICE_REF_BUS] = e2i[ areas[:, PRICE_REF_BUS].astype(int) ]

        return i2e, bus, gen, branch, areas

    return i2e, bus, gen, branch


def int2ext(ppc, val_or_field=None, oldval=None, ordering=None, dim=0):
    """Converts internal to external bus numbering.

    C{ppc = int2ext(ppc)}

    If the input is a single PYPOWER case dict, then it restores all
    buses, generators and branches that were removed because of being
    isolated or off-line, and reverts to the original generator ordering
    and original bus numbering. This requires that the 'order' key
    created by L{ext2int} be in place.

    Example::
        ppc = int2ext(ppc)

    @see: L{ext2int}, L{i2e_field}, L{i2e_data}

    @author: Ray Zimmerman (PSERC Cornell)
    """
    ppc = deepcopy(ppc)
    if val_or_field is None: # nargin == 1
        if 'order' not in ppc:
            sys.stderr.write('int2ext: ppc does not have the "order" field '
                'required for conversion back to external numbering.\n')
        o = ppc["order"]

        if o["state"] == 'i':
            ## execute userfcn callbacks for 'int2ext' stage
            if 'userfcn' in ppc:
                ppc = run_userfcn(ppc["userfcn"], 'int2ext', ppc)

            ## save data matrices with internal ordering & restore originals
            o["int"] = {}
            o["int"]["bus"]    = ppc["bus"].copy()
            o["int"]["branch"] = ppc["branch"].copy()
            o["int"]["gen"]    = ppc["gen"].copy()
            ppc["bus"]     = o["ext"]["bus"].copy()
            ppc["branch"]  = o["ext"]["branch"].copy()
            ppc["gen"]     = o["ext"]["gen"].copy()
            if 'gencost' in ppc:
                o["int"]["gencost"] = ppc["gencost"].copy()
                ppc["gencost"] = o["ext"]["gencost"].copy()
            if 'areas' in ppc:
                o["int"]["areas"] = ppc["areas"].copy()
                ppc["areas"] = o["ext"]["areas"].copy()
            if 'A' in ppc:
                o["int"]["A"] = ppc["A"].copy()
                ppc["A"] = o["ext"]["A"].copy()
            if 'N' in ppc:
                o["int"]["N"] = ppc["N"].copy()
                ppc["N"] = o["ext"]["N"].copy()

            ## update data (in bus, branch and gen only)
            ppc["bus"][o["bus"]["status"]["on"], :] = \
                o["int"]["bus"]
            ppc["branch"][o["branch"]["status"]["on"], :] = \
                o["int"]["branch"]
            ppc["gen"][o["gen"]["status"]["on"], :] = \
                o["int"]["gen"][o["gen"]["i2e"], :]
            if 'areas' in ppc:
                ppc["areas"][o["areas"]["status"]["on"], :] = \
                    o["int"]["areas"]

            ## revert to original bus numbers
            ppc["bus"][o["bus"]["status"]["on"], BUS_I] = \
                o["bus"]["i2e"] \
                    [ ppc["bus"][o["bus"]["status"]["on"], BUS_I].astype(int) ]
            ppc["branch"][o["branch"]["status"]["on"], F_BUS] = \
                o["bus"]["i2e"][ ppc["branch"] \
                    [o["branch"]["status"]["on"], F_BUS].astype(int) ]
            ppc["branch"][o["branch"]["status"]["on"], T_BUS] = \
                o["bus"]["i2e"][ ppc["branch"] \
                    [o["branch"]["status"]["on"], T_BUS].astype(int) ]
            ppc["gen"][o["gen"]["status"]["on"], GEN_BUS] = \
                o["bus"]["i2e"][ ppc["gen"] \
                    [o["gen"]["status"]["on"], GEN_BUS].astype(int) ]
            if 'areas' in ppc:
                ppc["areas"][o["areas"]["status"]["on"], PRICE_REF_BUS] = \
                    o["bus"]["i2e"][ ppc["areas"] \
                    [o["areas"]["status"]["on"], PRICE_REF_BUS].astype(int) ]

            if 'ext' in o: del o['ext']
            o["state"] = 'e'
            ppc["order"] = o
        else:
            sys.stderr.write('int2ext: ppc claims it is already using '
                         'external numbering.\n')
    else:                    ## convert extra data
        if isinstance(val_or_field, str) or isinstance(val_or_field, list):
            ## field (key)
            warn('Calls of the form MPC = INT2EXT(MPC, ''FIELD_NAME'', ...) have been deprecated. Please replace INT2EXT with I2E_FIELD.')
            bus, gen = val_or_field, oldval
            if ordering is not None:
                dim = ordering
            ppc = i2e_field(ppc, bus, gen, dim)
        else:
            ## value
            warn('Calls of the form VAL = INT2EXT(MPC, VAL, ...) have been deprecated. Please replace INT2EXT with I2E_DATA.')
            bus, gen, branch = val_or_field, oldval, ordering
            ppc = i2e_data(ppc, bus, gen, branch, dim)

    return ppc


def int2ext1(i2e, bus, gen, branch, areas):
    """Converts from the consecutive internal bus numbers back to the originals
    using the mapping provided by the I2E vector returned from C{ext2int}.

    @see: L{ext2int}
    @see: U{http://www.pserc.cornell.edu/matpower/}
    """
    bus[:, BUS_I]    = i2e[ bus[:, BUS_I].astype(int) ]
    gen[:, GEN_BUS]  = i2e[ gen[:, GEN_BUS].astype(int) ]
    branch[:, F_BUS] = i2e[ branch[:, F_BUS].astype(int) ]
    branch[:, T_BUS] = i2e[ branch[:, T_BUS].astype(int) ]

    if areas is not None and len(areas) > 0:
        areas[:, PRICE_REF_BUS] = i2e[areas[:, PRICE_REF_BUS].astype(int)]
        return bus, gen, branch, areas

    return bus, gen, branch


def loadcase(casefile, return_as_obj=True, expect_gencost=True, expect_areas=True):
    """Returns the individual data matrices or an dict containing them
    as values.

    Here C{casefile} is either a dict containing the keys C{baseMVA}, C{bus},
    C{gen}, C{branch}, C{areas}, C{gencost}, or a string containing the name
    of the file. If C{casefile} contains the extension '.mat' or '.py', then
    the explicit file is searched. If C{casefile} containts no extension, then
    L{loadcase} looks for a '.mat' file first, then for a '.py' file.  If the
    file does not exist or doesn't define all matrices, the function returns
    an exit code as follows:

        0.  all variables successfully defined
        1.  input argument is not a string or dict
        2.  specified extension-less file name does not exist
        3.  specified .mat file does not exist
        4.  specified .py file does not exist
        5.  specified file fails to define all matrices or contains syntax
            error

    If the input data is not a dict containing a 'version' key, it is
    assumed to be a PYPOWER case file in version 1 format, and will be
    converted to version 2 format.

    @author: Carlos E. Murillo-Sanchez (PSERC Cornell & Universidad
    Autonoma de Manizales)
    @author: Ray Zimmerman (PSERC Cornell)
    """
    if return_as_obj == True:
        expect_gencost = False
        expect_areas = False

    info = 0
    lasterr = ''

    # read data into case object
    if isinstance(casefile, basestring):
        # check for explicit extension
        if casefile.endswith(('.py', '.mat')):
            rootname, extension = splitext(casefile)
            fname = basename(rootname)
        else:
            # set extension if not specified explicitly
            rootname = casefile
            if exists(casefile + '.mat'):
                extension = '.mat'
            elif exists(casefile + '.py'):
                extension = '.py'
            else:
                info = 2
            fname = basename(rootname)

        # attempt to read file
        if info == 0:
            if extension == '.mat':       # from MAT file
                try:
                    d = loadmat(rootname + extension, struct_as_record=True)
                    if 'ppc' in d or 'mpc' in d:    # it's a MAT/PYPOWER dict
                        if 'ppc' in d:
                            struct = d['ppc']
                        else:
                            struct = d['mpc']
                        val = struct[0, 0]

                        s = {}
                        for a in val.dtype.names:
                            s[a] = val[a]
                    else:                 # individual data matrices
                        d['version'] = '1'

                        s = {}
                        for k, v in d.items():
                            s[k] = v

                    s['baseMVA'] = s['baseMVA'][0]  # convert array to float

                except IOError as e:
                    info = 3
                    lasterr = str(e)
            elif extension == '.py':      # from Python file
                try:
                    if PY2:
                        execfile(rootname + extension)
                    else:
                        exec(compile(open(rootname + extension).read(),
                                     rootname + extension, 'exec'))

                    try:   # assume it returns an object
                        s = eval(fname)()
                    except ValueError as e:
                        info = 4
                        lasterr = str(e)
                    # if not try individual data matrices
                    if info == 0 and not isinstance(s, dict):
                        s = dict()
                        s['version'] = '1'
                        if expect_gencost:
                            try:
                                s['baseMVA'], s['bus'], s['gen'], s['branch'], \
                                s['areas'], s['gencost'] = eval(fname)()
                            except IOError as e:
                                info = 4
                                lasterr = str(e)
                        else:
                            if return_as_obj:
                                try:
                                    s['baseMVA'], s['bus'], s['gen'], \
                                        s['branch'], s['areas'], \
                                        s['gencost'] = eval(fname)()
                                except ValueError as e:
                                    try:
                                        s['baseMVA'], s['bus'], s['gen'], \
                                            s['branch'] = eval(fname)()
                                    except ValueError as e:
                                        info = 4
                                        lasterr = str(e)
                            else:
                                try:
                                    s['baseMVA'], s['bus'], s['gen'], \
                                        s['branch'] = eval(fname)()
                                except ValueError as e:
                                    info = 4
                                    lasterr = str(e)

                except IOError as e:
                    info = 4
                    lasterr = str(e)

                if info == 4 and exists(rootname + '.py'):
                    info = 5
                    err5 = lasterr

    elif isinstance(casefile, dict):
        s = deepcopy(casefile)
    else:
        info = 1

    # check contents of dict
    if info == 0:
        # check for required keys
        if (s['baseMVA'] is None or s['bus'] is None \
            or s['gen'] is None or s['branch'] is None) or \
            (expect_gencost and s['gencost'] is None) or \
            (expect_areas and s['areas'] is None):
            info = 5   # missing some expected fields
            err5 = 'missing data'
        else:
            # remove empty areas if not needed
            if hasattr(s, 'areas') and (len(s['areas']) == 0) and (not expect_areas):
                del s['areas']

            # all fields present, copy to ppc
            ppc = deepcopy(s)
            if not hasattr(ppc, 'version'):  # hmm, struct with no 'version' field
                if ppc['gen'].shape[1] < 21: # version 2 has 21 or 25 cols
                    ppc['version'] = '1'
                else:
                    ppc['version'] = '2'

            if ppc['version'] == '1':
                # convert from version 1 to version 2
                ppc['gen'], ppc['branch'] = ppc_1to2(ppc['gen'], ppc['branch']);
                ppc['version'] = '2'

    if info == 0:  # no errors
        if return_as_obj:
            return ppc
        else:
            result = [ppc['baseMVA'], ppc['bus'], ppc['gen'], ppc['branch']]
            if expect_gencost:
                if expect_areas:
                    result.extend([ppc['areas'], ppc['gencost']])
                else:
                    result.extend([ppc['gencost']])
            return result
    else:  # error encountered
        if info == 1:
            sys.stderr.write('Input arg should be a case or a string '
                             'containing a filename\n')
        elif info == 2:
            sys.stderr.write('Specified case not a valid file\n')
        elif info == 3:
            sys.stderr.write('Specified MAT file does not exist\n')
        elif info == 4:
            sys.stderr.write('Specified Python file does not exist\n')
        elif info == 5:
            sys.stderr.write('Syntax error or undefined data '
                             'matrix(ices) in the file\n')
        else:
            sys.stderr.write('Unknown error encountered loading case.\n')

        sys.stderr.write(lasterr + '\n')

        return info


def load_from_xls(filename):
    """
    Loads the excel file content to a dictionary for parsing the data
    """
    print()
    ppc = dict()

    import pandas as pd
    xl = pd.ExcelFile(filename)
    names = xl.sheet_names

    for name in names:

        # df.head()

        if name.lower() == "conf":
            df = xl.parse(name)
            ppc["baseMVA"] = np.double(df.values[0, 1])
        elif name.lower() == "bus":
            df = xl.parse(name)
            ppc["bus"] = np.nan_to_num(df.values)
            if len(df) > 0:
                if df.index.values.tolist()[0] != 0:
                    ppc['bus_names'] = df.index.values.tolist()
        elif name.lower() == "gen":
            df = xl.parse(name)
            ppc["gen"] = np.nan_to_num(df.values)
            if len(df) > 0:
                if df.index.values.tolist()[0] != 0:
                    ppc['gen_names'] = df.index.values.tolist()
        elif name.lower() == "branch":
            df = xl.parse(name)
            ppc["branch"] = np.nan_to_num(df.values)
            if len(df) > 0:
                if df.index.values.tolist()[0] != 0:
                    ppc['branch_names'] = df.index.values.tolist()
        elif name.lower() == "lprof":
            df = xl.parse(name, index_col=0)
            ppc["Lprof"] = np.nan_to_num(df.values)
            ppc["master_time"] = df.index
        elif name.lower() == "lprofq":
            df = xl.parse(name, index_col=0)
            ppc["LprofQ"] = np.nan_to_num(df.values)
            # ppc["master_time"] = df.index.values
        elif name.lower() == "gprof":
            df = xl.parse(name, index_col=0)
            ppc["Gprof"] = np.nan_to_num(df.values)
            ppc["master_time"] = df.index  # it is the same

    return ppc


def load_from_dgs(filename):
    """
    Use the DGS parset to get a circuit structure dictionary
    @param filename:
    @return: Circuit dictionary
    """
    baseMVA, BUSES, BRANCHES, GEN, graph, gpos, BUS_NAMES, BRANCH_NAMES, GEN_NAMES = read_DGS(filename)

    ppc = dict()
    ppc["baseMVA"] = baseMVA
    ppc["bus"] = BUSES.values
    ppc['bus_names'] = BUS_NAMES
    ppc["gen"] = GEN.values
    ppc['gen_names'] = GEN_NAMES
    ppc["branch"] = BRANCHES.values
    ppc['branch_names'] = BRANCH_NAMES

    return ppc

def ppc_1to2(gen, branch):
    # -----  gen  -----
    # use the version 1 values for column names
    if gen.shape[1] >= APF:
        sys.stderr.write('ppc_1to2: gen matrix appears to already be in '
                         'version 2 format\n')
        return gen, branch

    shift = MU_PMAX - PMIN - 1
    tmp = array([MU_PMAX, MU_PMIN, MU_QMAX, MU_QMIN]) - shift
    mu_Pmax, mu_Pmin, mu_Qmax, mu_Qmin = tmp

    # add extra columns to gen
    tmp = zeros((gen.shape[0], shift))
    if gen.shape[1] >= mu_Qmin:
        gen = c_[ gen[:, 0:PMIN + 1], tmp, gen[:, mu_Pmax:mu_Qmin] ]
    else:
        gen = c_[ gen[:, 0:PMIN + 1], tmp ]

    # -----  branch  -----
    # use the version 1 values for column names
    shift = PF - BR_STATUS - 1
    tmp = array([PF, QF, PT, QT, MU_SF, MU_ST]) - shift
    Pf, Qf, Pt, Qt, mu_Sf, mu_St = tmp

    # add extra columns to branch
    tmp = ones((branch.shape[0], 1)) * array([-360, 360])
    tmp2 = zeros((branch.shape[0], 2))
    if branch.shape[1] >= mu_St - 1:
        branch = c_[ branch[:, 0:BR_STATUS + 1], tmp, branch[:, PF - 1:MU_ST + 1], tmp2 ]
    elif branch.shape[1] >= QT - 1:
        branch = c_[ branch[:, 0:BR_STATUS + 1], tmp, branch[:, PF - 1:QT + 1] ]
    else:
        branch = c_[ branch[:, 0:BR_STATUS + 1], tmp ]

    return gen, branch


def isload(gen):
    """
    Checks for dispatchable loads.

    Returns a column vector of 1's and 0's. The 1's correspond to rows of the
    C{gen} matrix which represent dispatchable loads. The current test is
    C{Pmin < 0 and Pmax == 0}. This may need to be revised to allow sensible
    specification of both elastic demand and pumped storage units.

    @author: Ray Zimmerman (PSERC Cornell)
    """
    return (gen[:, PMIN] < 0) & (gen[:, PMAX] == 0)


def savecase(fname, ppc, comment=None, version='2'):
    """Saves a PYPOWER case file, given a filename and the data.

    Writes a PYPOWER case file, given a filename and data dict. The C{fname}
    parameter is the name of the file to be created or overwritten. Returns
    the filename, with extension added if necessary. The optional C{comment}
    argument is either string (single line comment) or a list of strings which
    are inserted as comments. When using a PYPOWER case dict, if the
    optional C{version} argument is '1' it will modify the data matrices to
    version 1 format before saving.

    @author: Carlos E. Murillo-Sanchez (PSERC Cornell & Universidad
    Autonoma de Manizales)
    @author: Ray Zimmerman (PSERC Cornell)
    """
    ppc_ver = ppc["version"] = version
    baseMVA, bus, gen, branch = \
        ppc["baseMVA"], ppc["bus"], ppc["gen"], ppc["branch"]
    areas = ppc["areas"] if "areas" in ppc else None
    gencost = ppc["gencost"] if "gencost" in ppc else None

    ## modifications for version 1 format
    if ppc_ver == "1":
        raise NotImplementedError
#        ## remove extra columns of gen
#        if gen.shape[1] >= MU_QMIN:
#            gen = c_[gen[:, :PMIN], gen[:, MU_PMAX:MU_QMIN]]
#        else:
#            gen = gen[:, :PMIN]
#        ## use the version 1 values for column names
#        shift = MU_PMAX - PMIN - 1
#        tmp = array([MU_PMAX, MU_PMIN, MU_QMAX, MU_QMIN]) - shift
#        MU_PMAX, MU_PMIN, MU_QMAX, MU_QMIN = tmp
#
#        ## remove extra columns of branch
#        if branch.shape[1] >= MU_ST:
#            branch = c_[branch[:, :BR_STATUS], branch[:, PF:MU_ST]]
#        elif branch.shape[1] >= QT:
#            branch = c_[branch[:, :BR_STATUS], branch[:, PF:QT]]
#        else:
#            branch = branch[:, :BR_STATUS]
#        ## use the version 1 values for column names
#        shift = PF - BR_STATUS - 1
#        tmp = array([PF, QF, PT, QT, MU_SF, MU_ST]) - shift
#        PF, QF, PT, QT, MU_SF, MU_ST = tmp

    ## verify valid filename
    l = len(fname)
    rootname = ""
    if l > 2:
        if fname[-3:] == ".py":
            rootname = fname[:-3]
            extension = ".py"
        elif l > 4:
            if fname[-4:] == ".mat":
                rootname = fname[:-4]
                extension = ".mat"

    if not rootname:
        rootname = fname
        extension = ".py"
        fname = rootname + extension

    indent = '    '  # four spaces
    indent2 = indent + indent

    # open and write the file
    if extension == ".mat":     ## MAT-file
        savemat(fname, ppc)
    else:                       ## Python file
        try:
            fd = open(fname, "wb")
        except Exception as detail:
            stderr.write("savecase: %s.\n" % detail)
            return fname

        # function header, etc.
        if ppc_ver == "1":
            raise NotImplementedError
#            if (areas != None) and (gencost != None) and (len(gencost) > 0):
#                fd.write('function [baseMVA, bus, gen, branch, areas, gencost] = %s\n' % rootname)
#            else:
#                fd.write('function [baseMVA, bus, gen, branch] = %s\n' % rootname)
#            prefix = ''
        else:
            fd.write('def %s():\n' % basename(rootname))
            prefix = 'ppc'
        if comment:
            if isinstance(comment, basestring):
                fd.write('#%s\n' % comment)
            elif isinstance(comment, list):
                for c in comment:
                    fd.write('#%s\n' % c)
        fd.write('\n%s## PYPOWER Case Format : Version %s\n' % (indent, ppc_ver))
        if ppc_ver != "1":
            fd.write("%sppc = {'version': '%s'}\n" % (indent, ppc_ver))
        fd.write('\n%s##-----  Power Flow Data  -----##\n' % indent)
        fd.write('%s## system MVA base\n' % indent)
        fd.write("%s%s['baseMVA'] = %.9g\n" % (indent, prefix, baseMVA))

        ## bus data
        ncols = bus.shape[1]
        fd.write('\n%s## bus data\n' % indent)
        fd.write('%s# bus_i type Pd Qd Gs Bs area Vm Va baseKV zone Vmax Vmin' % indent)
        if ncols >= MU_VMIN + 1:             ## opf SOLVED, save with lambda's & mu's
            fd.write('lam_P lam_Q mu_Vmax mu_Vmin')
        fd.write("\n%s%s['bus'] = array([\n" % (indent, prefix))
        if ncols < MU_VMIN + 1:              ## opf NOT SOLVED, save without lambda's & mu's
            for i in range(bus.shape[0]):
                fd.write('%s[%d, %d, %.9g, %.9g, %.9g, %.9g, %d, %.9g, %.9g, %.9g, %d, %.9g, %.9g],\n' % ((indent2,) + tuple(bus[i, :VMIN + 1])))
        else:                            ## opf SOLVED, save with lambda's & mu's
            for i in range(bus.shape[0]):
                fd.write('%s[%d, %d, %.9g, %.9g, %.9g, %.9g, %d, %.9g, %.9g, %.9g, %d, %.9g, %.9g, %.4f, %.4f, %.4f, %.4f],\n' % ((indent2,) + tuple(bus[:, :MU_VMIN + 1])))
        fd.write('%s])\n' % indent)

        ## generator data
        ncols = gen.shape[1]
        fd.write('\n%s## generator data\n' % indent)
        fd.write('%s# bus Pg Qg Qmax Qmin Vg mBase status Pmax Pmin' % indent)
        if ppc_ver != "1":
            fd.write(' Pc1 Pc2 Qc1min Qc1max Qc2min Qc2max ramp_agc ramp_10 ramp_30 ramp_q apf')
        if ncols >= MU_QMIN + 1:             # opf SOLVED, save with mu's
            fd.write(' mu_Pmax mu_Pmin mu_Qmax mu_Qmin')
        fd.write("\n%s%s['gen'] = array([\n" % (indent, prefix))
        if ncols < MU_QMIN + 1:              ## opf NOT SOLVED, save without mu's
            if ppc_ver == "1":
                for i in range(gen.shape[0]):
                    fd.write('%s[%d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d, %.9g, %.9g],\n' % ((indent2,) + tuple(gen[i, :PMIN + 1])))
            else:
                for i in range(gen.shape[0]):
                    fd.write('%s[%d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g],\n' % ((indent2,) + tuple(gen[i, :APF + 1])))
        else:
            if ppc_ver == "1":
                for i in range(gen.shape[0]):
                    fd.write('%s[%d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d, %.9g, %.9g, %.4f, %.4f, %.4f, %.4f],\n' % ((indent2,) + tuple(gen[i, :MU_QMIN + 1])))
            else:
                for i in range(gen.shape[0]):
                    fd.write('%s[%d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.4f, %.4f, %.4f, %.4f],\n' % ((indent2,) + tuple(gen[i, :MU_QMIN + 1])))
        fd.write('%s])\n' % indent)

        ## branch data
        ncols = branch.shape[1]
        fd.write('\n%s## branch data\n' % indent)
        fd.write('%s# fbus tbus r x b rateA rateB rateC ratio angle status' % indent)
        if ppc_ver != "1":
            fd.write(' angmin angmax')
        if ncols >= QT + 1:                  ## power flow SOLVED, save with line flows
            fd.write(' Pf Qf Pt Qt')
        if ncols >= MU_ST + 1:               ## opf SOLVED, save with mu's
            fd.write(' mu_Sf mu_St')
            if ppc_ver != "1":
                fd.write(' mu_angmin mu_angmax')
        fd.write('\n%s%s[\'branch\'] = array([\n' % (indent, prefix))
        if ncols < QT + 1:                   ## power flow NOT SOLVED, save without line flows or mu's
            if ppc_ver == "1":
                for i in range(branch.shape[0]):
                    fd.write('%s[%d, %d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d],\n' % ((indent2,) + tuple(branch[i, :BR_STATUS + 1])))
            else:
                for i in range(branch.shape[0]):
                    fd.write('%s[%d, %d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d, %.9g, %.9g],\n' % ((indent2,) + tuple(branch[i, :ANGMAX + 1])))
        elif ncols < MU_ST + 1:            ## power flow SOLVED, save with line flows but without mu's
            if ppc_ver == "1":
                for i in range(branch.shape[0]):
                    fd.write('%s[%d, %d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d, %.4f, %.4f, %.4f, %.4f],\n' % ((indent2,) + tuple(branch[i, :QT + 1])))
            else:
                for i in range(branch.shape[0]):
                    fd.write('%s[%d, %d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d, %.9g, %.9g, %.4f, %.4f, %.4f, %.4f],\n' % ((indent2,) + tuple(branch[i, :QT + 1])))
        else:                            ## opf SOLVED, save with lineflows & mu's
            if ppc_ver == "1":
                for i in range(branch.shape[0]):
                    fd.write('%s[%d, %d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f],\n' % ((indent2,) + tuple(branch[i, :MU_ST + 1])))
            else:
                for i in range(branch.shape[0]):
                    fd.write('%s[%d, %d, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %.9g, %d, %.9g, %.9g, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f],\n' % ((indent2,) + tuple(branch[i, :MU_ANGMAX + 1])))
        fd.write('%s])\n' % indent)

        ## OPF data
        if (areas != None) and (len(areas) > 0) or (gencost != None) and (len(gencost) > 0):
            fd.write('\n%s##-----  OPF Data  -----##' % indent)
        if (areas != None) and (len(areas) > 0):
            ## area data
            fd.write('\n%s## area data\n' % indent)
            fd.write('%s# area refbus\n' % indent)
            fd.write("%s%s['areas'] = array([\n" % (indent, prefix))
            if len(areas) > 0:
                for i in range(areas.shape[0]):
                    fd.write('%s[%d, %d],\n' % ((indent2,) + tuple(areas[i, :PRICE_REF_BUS + 1])))
            fd.write('%s])\n' % indent)
        if gencost != None and len(gencost) > 0:
            ## generator cost data
            fd.write('\n%s## generator cost data\n' % indent)
            fd.write('%s# 1 startup shutdown n x1 y1 ... xn yn\n' % indent)
            fd.write('%s# 2 startup shutdown n c(n-1) ... c0\n' % indent)
            fd.write('%s%s[\'gencost\'] = array([\n' % (indent, prefix))
            if len(gencost > 0):
                if any(gencost[:, MODEL] == PW_LINEAR):
                    n1 = 2 * max(gencost[gencost[:, MODEL] == PW_LINEAR,  NCOST])
                else:
                    n1 = 0
                if any(gencost[:, MODEL] == POLYNOMIAL):
                    n2 =     max(gencost[gencost[:, MODEL] == POLYNOMIAL, NCOST])
                else:
                    n2 = 0
                n = int( max([n1, n2]) )
                if gencost.shape[1] < n + 4:
                    stderr.write('savecase: gencost data claims it has more columns than it does\n')
                template = '%s[%d, %.9g, %.9g, %d'
                for i in range(n):
                    template = template + ', %.9g'
                template = template + '],\n'
                for i in range(gencost.shape[0]):
                    fd.write(template % ((indent2,) + tuple(gencost[i])))
            fd.write('%s])\n' % indent)

        ## generalized OPF user data
        if ("A" in ppc) and (len(ppc["A"]) > 0) or ("N" in ppc) and (len(ppc["N"]) > 0):
            fd.write('\n%s##-----  Generalized OPF User Data  -----##' % indent)

        ## user constraints
        if ("A" in ppc) and (len(ppc["A"]) > 0):
            ## A
            fd.write('\n%s## user constraints\n' % indent)
            print_sparse(fd, prefix + "['A']", ppc["A"])
            if ("l" in ppc) and (len(ppc["l"]) > 0) and ("u" in ppc) and (len(ppc["u"]) > 0):
                fd.write('%slu = array([\n' % indent)
                for i in range(len(l)):
                    fd.write('%s[%.9g, %.9g],\n' % (indent2, ppc["l"][i], ppc["u"][i]))
                fd.write('%s])\n' % indent)
                fd.write("%s%s['l'] = lu[:, 0]\n" % (indent, prefix))
                fd.write("%s%s['u'] = lu[:, 1]\n\n" % (indent, prefix))
            elif ("l" in ppc) and (len(ppc["l"]) > 0):
                fd.write("%s%s['l'] = array([\n" % (indent, prefix))
                for i in range(len(l)):
                    fd.write('%s[%.9g],\n' % (indent2, ppc["l"][i]))
                fd.write('%s])\n\n' % indent)
            elif ("u" in ppc) and (len(ppc["u"]) > 0):
                fd.write("%s%s['u'] = array([\n" % (indent, prefix))
                for i in range(len(l)):
                    fd.write('%s[%.9g],\n' % (indent2, ppc["u"][i]))
                fd.write('%s])\n\n' % indent)

        ## user costs
        if ("N" in ppc) and (len(ppc["N"]) > 0):
            fd.write('\n%s## user costs\n' % indent)
            print_sparse(fd, prefix + "['N']", ppc["N"])
            if ("H" in ppc) and (len(ppc["H"]) > 0):
                print_sparse(fd, prefix + "['H']", ppc["H"])
            if ("fparm" in ppc) and (len(ppc["fparm"]) > 0):
                fd.write("%sCw_fparm = array([\n" % indent)
                for i in range(ppc["Cw"]):
                    fd.write('%s[%.9g, %d, %.9g, %.9g, %.9g],\n' % ((indent2,) + tuple(ppc["Cw"][i]) + tuple(ppc["fparm"][i, :])))
                fd.write('%s])\n' % indent)
                fd.write('%s%s[\'Cw\']    = Cw_fparm[:, 0]\n' % (indent, prefix))
                fd.write("%s%s['fparm'] = Cw_fparm[:, 1:5]\n" % (indent, prefix))
            else:
                fd.write("%s%s['Cw'] = array([\n" % (indent, prefix))
                for i in range(len(ppc["Cw"])):
                    fd.write('%s[%.9g],\n' % (indent2, ppc["Cw"][i]))
                fd.write('%s])\n' % indent)

        ## user vars
        if ('z0' in ppc) or ('zl' in ppc) or ('zu' in ppc):
            fd.write('\n%s## user vars\n' % indent)
            if ('z0' in ppc) and (len(ppc['z0']) > 0):
                fd.write('%s%s["z0"] = array([\n' % (indent, prefix))
                for i in range(len(ppc['z0'])):
                    fd.write('%s[%.9g],\n' % (indent2, ppc["z0"]))
                fd.write('%s])\n' % indent)
            if ('zl' in ppc) and (len(ppc['zl']) > 0):
                fd.write('%s%s["zl"] = array([\n' % (indent2, prefix))
                for i in range(len(ppc['zl'])):
                    fd.write('%s[%.9g],\n' % (indent2, ppc["zl"]))
                fd.write('%s])\n' % indent)
            if ('zu' in ppc) and (len(ppc['zu']) > 0):
                fd.write('%s%s["zu"] = array([\n' % (indent, prefix))
                for i in range(len(ppc['zu'])):
                    fd.write('%s[%.9g],\n' % (indent2, ppc["zu"]))
                fd.write('%s])\n' % indent)

        ## execute userfcn callbacks for 'savecase' stage
        if 'userfcn' in ppc:
            run_userfcn(ppc["userfcn"], 'savecase', ppc, fd, prefix)

        fd.write('\n%sreturn ppc\n' % indent)

        ## close file
        fd.close()

    return fname


def print_sparse(fd, varname, A):
    A = A.tocoo()
    i, j, s = A.row, A.col, A.data
    m, n = A.shape

    if len(s) == 0:
        fd.write('%s = sparse((%d, %d))\n' % (varname, m, n))
    else:
        fd.write('ijs = array([\n')
    for k in range(len(i)):
        fd.write('[%d, %d, %.9g],\n' % (i[k], j[k], s[k]))

    fd.write('])\n')
    fd.write('%s = sparse(ijs[:, 0], ijs[:, 1], ijs[:, 2], %d, %d)\n' % (varname, m, n))


def get_reorder(A, idx, dim=0):
    """Returns A with one of its dimensions indexed::

        B = get_reorder(A, idx, dim)

    Returns A[:, ..., :, idx, :, ..., :], where dim determines
    in which dimension to place the idx.

    @author: Ray Zimmerman (PSERC Cornell)
    """
    ndims = ndim(A)
    if ndims == 1:
        B = A[idx].copy()
    elif ndims == 2:
        if dim == 0:
            B = A[idx, :].copy()
        elif dim == 1:
            B = A[:, idx].copy()
        else:
            raise ValueError('dim (%d) may be 0 or 1' % dim)
    else:
        raise ValueError('number of dimensions (%d) may be 1 or 2' % dim)

    return B


def set_reorder(A, B, idx, dim=0):
    """Assigns B to A with one of the dimensions of A indexed.

    @return: A after doing A(:, ..., :, IDX, :, ..., :) = B
    where DIM determines in which dimension to place the IDX.

    @see: L{get_reorder}

    @author: Ray Zimmerman (PSERC Cornell)
    """
    A = A.copy()
    ndims = ndim(A)
    if ndims ==  1:
        A[idx] = B
    elif ndims == 2:
        if dim == 0:
            A[idx, :] = B
        elif dim == 1:
            A[:, idx] = B
        else:
            raise ValueError('dim (%d) may be 0 or 1' % dim)
    else:
        raise ValueError('number of dimensions (%d) may be 1 or 2' % dim)

    return A


def e2i_data(ppc, val, ordering, dim=0):
    """Converts data from external to internal indexing.

    When given a case dict that has already been converted to
    internal indexing, this function can be used to convert other data
    structures as well by passing in 2 or 3 extra parameters in
    addition to the case dict. If the value passed in the 2nd
    argument is a column vector, it will be converted according to the
    C{ordering} specified by the 3rd argument (described below). If C{val}
    is an n-dimensional matrix, then the optional 4th argument (C{dim},
    default = 0) can be used to specify which dimension to reorder.
    The return value in this case is the value passed in, converted
    to internal indexing.

    The 3rd argument, C{ordering}, is used to indicate whether the data
    corresponds to bus-, gen- or branch-ordered data. It can be one
    of the following three strings: 'bus', 'gen' or 'branch'. For
    data structures with multiple blocks of data, ordered by bus,
    gen or branch, they can be converted with a single call by
    specifying C{ordering} as a list of strings.

    Any extra elements, rows, columns, etc. beyond those indicated
    in C{ordering}, are not disturbed.

    Examples:
        A_int = e2i_data(ppc, A_ext, ['bus','bus','gen','gen'], 1)

        Converts an A matrix for user-supplied OPF constraints from
        external to internal ordering, where the columns of the A
        matrix correspond to bus voltage angles, then voltage
        magnitudes, then generator real power injections and finally
        generator reactive power injections.

        gencost_int = e2i_data(ppc, gencost_ext, ['gen','gen'], 0)

        Converts a GENCOST matrix that has both real and reactive power
        costs (in rows 1--ng and ng+1--2*ng, respectively).
    """
    if 'order' not in ppc:
        sys.stderr.write('e2i_data: ppc does not have the \'order\' field '
                'required to convert from external to internal numbering.\n')
        return

    o = ppc['order']
    if o['state'] != 'i':
        sys.stderr.write('e2i_data: ppc does not have internal ordering '
                'data available, call ext2int first\n')
        return

    if isinstance(ordering, str):        ## single set
        if ordering == 'gen':
            idx = o[ordering]["status"]["on"][ o[ordering]["e2i"] ]
        else:
            idx = o[ordering]["status"]["on"]
        val = get_reorder(val, idx, dim)
    else:                            ## multiple: sets
        b = 0  ## base
        new_v = []
        for ordr in ordering:
            n = o["ext"][ordr].shape[0]
            v = get_reorder(val, b + arange(n), dim)
            new_v.append( e2i_data(ppc, v, ordr, dim) )
            b = b + n
        n = val.shape[dim]
        if n > b:                ## the rest
            v = get_reorder(val, arange(b, n), dim)
            new_v.append(v)

        if issparse(new_v[0]):
            if dim == 0:
                vstack(new_v, 'csr')
            elif dim == 1:
                hstack(new_v, 'csr')
            else:
                raise ValueError('dim (%d) may be 0 or 1' % dim)
        else:
            val = concatenate(new_v, dim)
    return val


def e2i_field(ppc, field, ordering, dim=0):
    """Converts fields of C{ppc} from external to internal indexing.

    This function performs several different tasks, depending on the
    arguments passed.

    When given a case dict that has already been converted to
    internal indexing, this function can be used to convert other data
    structures as well by passing in 2 or 3 extra parameters in
    addition to the case dict.

    The 2nd argument is a string or list of strings, specifying
    a field in the case dict whose value should be converted by
    a corresponding call to L{e2i_data}. In this case, the converted value
    is stored back in the specified field, the original value is
    saved for later use and the updated case dict is returned.
    If C{field} is a list of strings, they specify nested fields.

    The 3rd and optional 4th arguments are simply passed along to
    the call to L{e2i_data}.

    Examples:
        ppc = e2i_field(ppc, ['reserves', 'cost'], 'gen')

        Reorders rows of ppc['reserves']['cost'] to match internal generator
        ordering.

        ppc = e2i_field(ppc, ['reserves', 'zones'], 'gen', 1)

        Reorders columns of ppc['reserves']['zones'] to match internal
        generator ordering.

    @see: L{i2e_field}, L{e2i_data}, L{ext2int}
    """
    if isinstance(field, basestring):
        key = '["%s"]' % field
    else:
        key = '["%s"]' % '"]["'.join(field)

        v_ext = ppc["order"]["ext"]
        for fld in field:
            if fld not in v_ext:
                v_ext[fld] = {}
                v_ext = v_ext[fld]

    exec('ppc["order"]["ext"]%s = ppc%s.copy()' % (key, key))
    exec('ppc%s = e2i_data(ppc, ppc%s, ordering, dim)' % (key, key))

    return ppc


def i2e_data(ppc, val, oldval, ordering, dim=0):
    """Converts data from internal to external bus numbering.

    For a case dict using internal indexing, this function can be
    used to convert other data structures as well by passing in 3 or 4
    extra parameters in addition to the case dict. If the value passed
    in the 2nd argument C{val} is a column vector, it will be converted
    according to the ordering specified by the 4th argument (C{ordering},
    described below). If C{val} is an n-dimensional matrix, then the
    optional 5th argument (C{dim}, default = 0) can be used to specify
    which dimension to reorder. The 3rd argument (C{oldval}) is used to
    initialize the return value before converting C{val} to external
    indexing. In particular, any data corresponding to off-line gens
    or branches or isolated buses or any connected gens or branches
    will be taken from C{oldval}, with C[val} supplying the rest of the
    returned data.

    The C{ordering} argument is used to indicate whether the data
    corresponds to bus-, gen- or branch-ordered data. It can be one
    of the following three strings: 'bus', 'gen' or 'branch'. For
    data structures with multiple blocks of data, ordered by bus,
    gen or branch, they can be converted with a single call by
    specifying C[ordering} as a list of strings.

    Any extra elements, rows, columns, etc. beyond those indicated
    in C{ordering}, are not disturbed.

    Examples:
        A_ext = i2e_data(ppc, A_int, A_orig, ['bus','bus','gen','gen'], 1)

        Converts an A matrix for user-supplied OPF constraints from
        internal to external ordering, where the columns of the A
        matrix correspond to bus voltage angles, then voltage
        magnitudes, then generator real power injections and finally
        generator reactive power injections.

        gencost_ext = i2e_data(ppc, gencost_int, gencost_orig, ['gen','gen'], 0)

        Converts a C{gencost} matrix that has both real and reactive power
        costs (in rows 1--ng and ng+1--2*ng, respectively).

    @see: L{e2i_data}, L{i2e_field}, L{int2ext}.
    """

    if 'order' not in ppc:
        sys.stderr.write('i2e_data: ppc does not have the \'order\' field '
                'required for conversion back to external numbering.\n')
        return

    o = ppc["order"]
    if o['state'] != 'i':
        sys.stderr.write('i2e_data: ppc does not appear to be in internal '
                'order\n')
        return

    if isinstance(ordering, str):         ## single set
        if ordering == 'gen':
            v = get_reorder(val, o[ordering]["i2e"], dim)
        else:
            v = val
        val = set_reorder(oldval, v, o[ordering]["status"]["on"], dim)
    else:                                 ## multiple sets
        be = 0  ## base, external indexing
        bi = 0  ## base, internal indexing
        new_v = []
        for ordr in ordering:
            ne = o["ext"][ordr].shape[0]
            ni = ppc[ordr].shape[0]
            v = get_reorder(val, bi + arange(ni), dim)
            oldv = get_reorder(oldval, be + arange(ne), dim)
            new_v.append( int2ext(ppc, v, oldv, ordr, dim) )
            be = be + ne
            bi = bi + ni
        ni = val.shape[dim]
        if ni > bi:              ## the rest
            v = get_reorder(val, arange(bi, ni), dim)
            new_v.append(v)
        val = concatenate(new_v, dim)

    return val


def i2e_field(ppc, field, ordering, dim=0):
    """Converts fields of MPC from internal to external bus numbering.

    For a case dict using internal indexing, this function can be
    used to convert other data structures as well by passing in 2 or 3
    extra parameters in addition to the case dict.

    If the 2nd argument is a string or list of strings, it
    specifies a field in the case dict whose value should be
    converted by L{i2e_data}. In this case, the corresponding
    C{oldval} is taken from where it was stored by L{ext2int} in
    ppc['order']['ext'] and the updated case dict is returned.
    If C{field} is a list of strings, they specify nested fields.

    The 3rd and optional 4th arguments are simply passed along to
    the call to L{i2e_data}.

    Examples:
        ppc = i2e_field(ppc, ['reserves', 'cost'], 'gen')

        Reorders rows of ppc['reserves']['cost'] to match external generator
        ordering.

        ppc = i2e_field(ppc, ['reserves', 'zones'], 'gen', 1)

        Reorders columns of ppc.reserves.zones to match external
        generator ordering.

    @see: L{e2i_field}, L{i2e_data}, L{int2ext}.
    """
    if 'int' not in ppc['order']:
        ppc['order']['int'] = {}

    if isinstance(field, str):
        key = '["%s"]' % field
    else:  # nested dicts
        key = '["%s"]' % '"]["'.join(field)

        v_int = ppc["order"]["int"]
        for fld in field:
            if fld not in v_int:
                v_int[fld] = {}
                v_int = v_int[fld]

    exec('ppc["order"]["int"]%s = ppc%s.copy()' % (key, key))
    exec('ppc%s = i2e_data(ppc, ppc%s, ppc["order"]["ext"]%s, ordering, dim)' %
         (key, key, key))

    return ppc


def merge_dicts(*dict_args):
    """
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    """
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


# def read_DGS(filename):
#     ###############################################################################
#     # Read the file
#     ###############################################################################
#     f = open(filename, errors='replace')
#     lines = f.readlines()
#     f.close()
#
#     ###############################################################################
#     # Process the data
#     ###############################################################################
#     data = dict()
#
#     """
#     Numpy types:
#
#     'b' 	boolean
#     'i' 	(signed) integer
#     'u' 	unsigned integer
#     'f' 	floating-point
#     'c' 	complex-floating point
#     'O' 	(Python) objects
#     'S', 'a' 	(byte-)string
#     'U' 	Unicode
#     'V' 	raw data (void)
#     """
#
#     """
#     DGS types
#
#     a
#     p
#     i
#     r
#
#     """
#     types_dict = dict()
#     types_dict["a"] = "|S32"
#     types_dict["p"] = "|S32"
#     types_dict["i"] = "<i4"
#     types_dict["r"] = "<f4"
#     types_dict["d"] = "<f4"
#
#     types_dict2 = dict()
#
#     CurrentType = None
#     DataTypes = None
#     Header = None
#
#     Headers = dict()
#     # parse the file lines
#     for line in lines:
#
#         if line.startswith("$$"):
#             line = line[2:]
#             chnks = line.split(";")
#             CurrentType = chnks[0]
#             data[CurrentType] = list()
#
#             # analyze types
#             DataTypes = list()
#             DataTypes2 = list()
#             Header = list()
#             for i in range(1, len(chnks)):
#                 token = chnks[i].split("(")
#                 name = token[0]
#                 tpe = token[1][:-1]
#                 DataTypes.append((name, types_dict[tpe[0]]))
#                 Header.append(name)
#
#             types_dict2[CurrentType] = DataTypes
#
#             Headers[CurrentType] = Header
#
#         elif line.startswith("*"):
#             pass
#
#         elif line.startswith("  "):
#             if CurrentType is not None:
#                 line = line.strip()
#                 chnks = line.split(";")
#                 chnks = ["0" if x == "" else x for x in chnks]
#                 data[CurrentType].append(array(tuple(chnks)))
#
#
#     # format keys
#
#     for key in data.keys():
#         print("Converting " + str(key))
#         table = array([tuple(x) for x in data[key]],dtype=types_dict2[key])
#         table = array([list(x) for x in table],dtype=np.object)
#         header = Headers[key]
#         data[key] = df(data=table, columns=header)
#
#     # positions dictionary
#     obj_id = data['IntGrf']['pDataObj'].values
#     x_vec = data['IntGrf']['rCenterX'].values
#     y_vec = data['IntGrf']['rCenterY'].values
#     pos_dict = dict()
#     for i in range(len(obj_id)):
#         pos_dict[obj_id[i]] = (x_vec[i], y_vec[i])
#     ###############################################################################
#     # Refactor data into classes
#     ###############################################################################
#
#     # store tables for easy refference
#
#     '''
#     ###############################################################################
#     *  Line
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  typ_id: Type in TypLne,TypTow,TypGeo,TypCabsys
#     *  chr_name: Characteristic Name
#     *  dline: Parameters: Length of Line in km
#     *  fline: Parameters: Derating Factor
#     *  outserv: Out of Service
#     *  pStoch: Failures: Element model in StoTyplne
#     '''
#     if "ElmLne" in data.keys():
#         lines = data["ElmLne"]
#     else:
#         lines = np.zeros((0,20))
#
#
#
#     '''
#     ###############################################################################
#     *  Line Type
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  chr_name: Characteristic Name
#     *  Ithr: Rated Short-Time (1s) Current (Conductor) in kA
#     *  aohl_: Cable / OHL
#     *  cline: Parameters per Length 1,2-Sequence: Capacitance C' in uF/km
#     *  cline0: Parameters per Length Zero Sequence: Capacitance C0' in uF/km
#     *  nlnph: Phases:1:2:3
#     *  nneutral: Number of Neutrals:0:1
#     *  rline: Parameters per Length 1,2-Sequence: AC-Resistance R'(20°C) in Ohm/km
#     *  rline0: Parameters per Length Zero Sequence: AC-Resistance R0' in Ohm/km
#     *  rtemp: Max. End Temperature in degC
#     *  sline: Rated Current in kA
#     *  uline: Rated Voltage in kV
#     *  xline: Parameters per Length 1,2-Sequence: Reactance X' in Ohm/km
#     *  xline0: Parameters per Length Zero Sequence: Reactance X0' in Ohm/km
#     '''
#     if "TypLne" in data.keys():
#         lines_types = data["TypLne"]
#     else:
#         lines_types = np.zeros((0,20))
#
#     '''
#     ###############################################################################
#     *  2-Winding Transformer
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  typ_id: Type in TypTr2
#     *  chr_name: Characteristic Name
#     *  sernum: Serial Number
#     *  constr: Year of Construction
#     *  cgnd_h: Internal Grounding Impedance, HV Side: Star Point:Connected:Not connected
#     *  cgnd_l: Internal Grounding Impedance, LV Side: Star Point:Connected:Not connected
#     *  i_auto: Auto Transformer
#     *  nntap: Tap Changer 1: Tap Position
#     *  ntrcn: Controller, Tap Changer 1: Automatic Tap Changing
#     *  outserv: Out of Service
#     *  ratfac: Rating Factor
#     '''
#     if "ElmTr2" in data.keys():
#         transformers = data["ElmTr2"]
#     else:
#         transformers = np.zeros((0,20))
#
#
#
#     '''
#     ###############################################################################
#     *  2-Winding Transformer Type
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  chr_name: Characteristic Name
#     *  curmg: Magnetising Impedance: No Load Current in %
#     *  dutap: Tap Changer 1: Additional Voltage per Tap in %
#     *  frnom: Nominal Frequency in Hz
#     *  manuf: Manufacturer
#     *  nntap0: Tap Changer 1: Neutral Position
#     *  nt2ag: Vector Group: Phase Shift in *30deg
#     *  ntpmn: Tap Changer 1: Minimum Position
#     *  ntpmx: Tap Changer 1: Maximum Position
#     *  pcutr: Positive Sequence Impedance: Copper Losses in kW
#     *  pfe: Magnetising Impedance: No Load Losses in kW
#     *  phitr: Tap Changer 1: Phase of du in deg
#     *  strn: Rated Power in MVA
#     *  tap_side: Tap Changer 1: at Side:HV:LV
#     *  tr2cn_h: Vector Group: HV-Side:Y :YN:Z :ZN:D
#     *  tr2cn_l: Vector Group: LV-Side:Y :YN:Z :ZN:D
#     *  uk0tr: Zero Sequence Impedance: Short-Circuit Voltage uk0 in %
#     *  uktr: Positive Sequence Impedance: Short-Circuit Voltage uk in %
#     *  ur0tr: Zero Sequence Impedance: SHC-Voltage (Re(uk0)) uk0r in %
#     *  utrn_h: Rated Voltage: HV-Side in kV
#     *  utrn_l: Rated Voltage: LV-Side in kV
#     *  zx0hl_n: Zero Sequence Magnetising Impedance: Mag. Impedance/uk0
#     '''
#     if "TypTr2" in data.keys():
#         transformers_types = data["TypTr2"]
#     else:
#         transformers_types = np.zeros((0,20))
#
#     '''
#     ###############################################################################
#     *  Terminal
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  typ_id: Type in TypBar
#     *  chr_name: Characteristic Name
#     *  iUsage: Usage:Busbar:Junction Node:Internal Node
#     *  outserv: Out of Service
#     *  phtech: Phase Technology:ABC:ABC-N:BI:BI-N:2PH:2PH-N:1PH:1PH-N:N
#     *  uknom: Nominal Voltage: Line-Line in kV
#     '''
#     if "ElmTerm" in data.keys():
#         buses = data["ElmTerm"]
#     else:
#         buses = np.zeros((0,20))
#
#
#     '''
#     ###############################################################################
#     *  Cubicle
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  chr_name: Characteristic Name
#     *  obj_bus: Bus Index
#     *  obj_id: Connected with in Elm*
#     '''
#     if "StaCubic" in data.keys():
#         cubicles = data["StaCubic"]
#     else:
#         cubicles = np.zeros((0,20))
#
#     '''
#     ###############################################################################
#     *  General Load
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  typ_id: Type in TypLod,TypLodind
#     *  chr_name: Characteristic Name
#     *  outserv: Out of Service
#     *  plini: Operating Point: Active Power in MW
#     *  qlini: Operating Point: Reactive Power in Mvar
#     *  scale0: Operating Point: Scaling Factor
#     '''
#     if "ElmLod" in data.keys():
#         loads = data["ElmLod"]
#     else:
#         loads = np.zeros((0,20))
#
#
#
#     '''
#     ###############################################################################
#     *  External Grid
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  chr_name: Characteristic Name
#     *  bustp: Bus Type:PQ:PV:SL
#     *  cgnd: Internal Grounding Impedance: Star Point:Connected:Not connected
#     *  iintgnd: Neutral Conductor: N-Connection:None:At terminal (ABC-N):Separate terminal
#     *  ikssmin: Min. Values: Short-Circuit Current Ik''min in kA
#     *  r0tx0: Max. Values Impedance Ratio: R0/X0 max.
#     *  r0tx0min: Min. Values Impedance Ratio: R0/X0 min.
#     *  rntxn: Max. Values: R/X Ratio (max.)
#     *  rntxnmin: Min. Values: R/X Ratio (min.)
#     *  snss: Max. Values: Short-Circuit Power Sk''max in MVA
#     *  snssmin: Min. Values: Short-Circuit Power Sk''min in MVA
#     '''
#     if "ElmXnet" in data.keys():
#         external = data["ElmXnet"]
#     else:
#         external = np.zeros((0,20))
#
#
#     '''
#     ###############################################################################
#     *  Grid
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  frnom: Nominal Frequency in Hz
#     '''
#     if "ElmNet" in data.keys():
#         grid = data["ElmNet"]
#     else:
#         grid = np.zeros((0,20))
#
#
#
#     '''
#     ###############################################################################
#     '''
#     if "ElmGenstat" in data.keys():
#         static_generators = data["ElmGenstat"]
#     else:
#         static_generators = np.zeros((0,20))
#
#
#     '''
#     ###############################################################################
#     *  Synchronous Machine
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  typ_id: Type in TypSym
#     *  chr_name: Characteristic Name
#     *  i_mot: Generator/Motor
#     *  iv_mode: Local Controller
#     *  ngnum: Number of: parallel Machines
#     *  outserv: Out of Service
#     *  pgini: Dispatch: Active Power in MW
#     *  q_max: Reactive Power Operational Limits: Max. in p.u.
#     *  q_min: Reactive Power Operational Limits: Min. in p.u.
#     *  qgini: Dispatch: Reactive Power in Mvar
#     *  usetp: Dispatch: Voltage in p.u.
#     '''
#     if "ElmSym" in data.keys():
#         synchronous_machine = data["ElmSym"]
#     else:
#         synchronous_machine = np.zeros((0,20))
#
#
#     '''
#     ###############################################################################
#     *  Synchronous Machine Type
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  cosn: Power Factor
#     *  rstr: Stator Resistance: rstr in p.u.
#     *  satur: For single fed short-circuit: Machine Type IEC909/IEC60909
#     *  sgn: Nominal Apparent Power in MVA
#     *  ugn: Nominal Voltage in kV
#     *  xd: Synchronous Reactances: xd in p.u.
#     *  xdsat: For single fed short-circuit: Reciprocal of short-circuit ratio (xdsat) in p.u.
#     *  xdsss: Subtransient Reactance: saturated value xd''sat in p.u.
#     *  xq: Synchronous Reactances: xq in p.u.
#     '''
#     if "TypSym" in data.keys():
#         synchronous_machine_type = data["TypSym"]
#     else:
#         synchronous_machine_type = np.zeros((0,20))
#
#
#     '''
#     ###############################################################################
#     *  Asynchronous Machine
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  typ_id: Type in TypAsm*,TypAsmo*,TypAsm1*
#     *  chr_name: Characteristic Name
#     *  i_mot: Generator/Motor
#     *  ngnum: Number of: parallel Machines
#     *  outserv: Out of Service
#     *  pgini: Dispatch: Active Power in MW
#     '''
#     if "ElmAsm" in data.keys():
#         asynchronous_machine = data["ElmAsm"]
#     else:
#         asynchronous_machine = np.zeros((0,20))
#
#
#     '''
#     ###############################################################################
#     *  Synchronous Machine Type
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  i_mode: Input Mode
#     *  aiazn: Consider Transient Parameter: Locked Rotor Current (Ilr/In) in p.u.
#     *  amazn: Locked Rotor Torque in p.u.
#     *  amkzn: Torque at Stalling Point in p.u.
#     *  anend: Nominal Speed in rpm
#     *  cosn: Rated Power Factor
#     *  effic: Efficiency at nominal Operation in %
#     *  frequ: Nominal Frequency in Hz
#     *  i_cage: Rotor
#     *  nppol: No of Pole Pairs
#     *  pgn: Power Rating: Rated Mechanical Power in kW
#     *  ugn: Rated Voltage in kV
#     *  xmrtr: Rotor Leakage Reac. Xrm in p.u.
#     *  xstr: Stator Reactance Xs in p.u.
#     '''
#     if "TypAsmo" in data.keys():
#         asynchronous_machine_type = data["TypAsmo"]
#     else:
#         asynchronous_machine_type = np.zeros((0,20))
#
#
#     '''
#     ###############################################################################
#     *  Shunt/Filter
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  chr_name: Characteristic Name
#     *  ctech: Technology
#     *  fres: Design Parameter (per Step): Resonance Frequency in Hz
#     *  greaf0: Design Parameter (per Step): Quality Factor (at fr)
#     *  iswitch: Controller: Switchable
#     *  ncapa: Controller: Act.No. of Step
#     *  ncapx: Controller: Max. No. of Steps
#     *  outserv: Out of Service
#     *  qtotn: Design Parameter (per Step): Rated Reactive Power, L-C in Mvar
#     *  shtype: Shunt Type
#     *  ushnm: Nominal Voltage in kV
#     '''
#     if "ElmShnt" in data.keys():
#         shunts = data["ElmShnt"]
#     else:
#         shunts = np.zeros((0,20))
#
#
#     '''
#     ###############################################################################
#     *  Breaker/Switch
#     *
#     *  ID: Unique identifier for DGS file
#     *  loc_name: Name
#     *  fold_id: In Folder
#     *  typ_id: Type in TypSwitch
#     *  chr_name: Characteristic Name
#     *  aUsage: Switch Type
#     *  nneutral: No. of Neutrals:0:1
#     *  nphase: No. of Phases:1:2:3
#     *  on_off: Closed
#     '''
#     if "ElmCoup" in data.keys():
#         switches = data["ElmCoup"]
#     else:
#         switches = np.zeros((0,20))
#
#
#
#     # put the tables that connect to a terminal in a list
#     classes = [lines, transformers, loads, external, static_generators, shunts]
#
#     #put the brach classes in a list
#     branch_classes = [lines, transformers]
#
#     # generator classes
#     generator_classes = [static_generators, synchronous_machine,
#                          asynchronous_machine]
#
#     ###############################################################################
#     # Post process the data
#     ###############################################################################
#
#     # dictionary to store the terminals ID associated with an object ID
#     terminals_dict = dict()
#
#     # construct the terminals dictionary
#     cub_obj_idx = cubicles['obj_id'].values
#     cub_term_idx = cubicles['fold_id'].values
#     ID_idx = 0
#     for cla in classes:
#         if cla.__len__() > 0:
#             for ID in cla['ID'].values:
#                 idx = np.where(cubicles == ID)[0]
#                 terminals_dict[ID] = cub_term_idx[idx]
#
#
#     ###############################################################################
#     # Generate GridCal data
#     ###############################################################################
#
#
#     baseMVA = 100
#     frequency = grid['frnom'][0]
#     w = 2.0 * np.pi * frequency
#
#     BUSES = list()
#     bus_line = np.zeros(len(bus_headers), dtype=np.object)
#
#     BRANCHES = list()
#     branch_line = np.zeros(len(branch_headers), dtype=np.object)
#
#     GEN = list()
#     gen_line = np.zeros(len(gen_headers), dtype=np.object)
#
#     g = nx.graph.Graph()
#
#     # terminals
#     print('Parsing terminals')
#     buses_dict = dict()
#     gpos = dict()
#     for i in range(len(buses)):
#         ID = buses['ID'][i]
#         x, y = pos_dict[ID]
#         bus_ = bus_line.copy()
#         bus_[BUS_I] = BUSES.__len__() +1  # ID
#         bus_[VM] = 1.0  # VM
#         bus_[VA] = 0.0  # VA
#         bus_[BASE_KV] = buses['uknom'][i]  # BaseKv
#         bus_[VMAX] = 1.05  # VMax
#         bus_[VMIN] = 0.95  # VMin
#         bus_[BUS_X] = x
#         bus_[BUS_Y] = y
#         # bus_[BUS_NAME] = buses['loc_name'][i]  # BUS_Name
#         bus_[BUS_TYPE] = 1  # PQ
#         BUSES.append(bus_)
#
#         buses_dict[ID] = i
#         gpos[i] = (x, y)
#
#     BUSES = np.array(BUSES, dtype=np.object)
#
#     # Branches
#     print('Parsing lines')
#     lines_ID = lines['ID']
#     lines_type_id = lines['typ_id']
#     line_types_ID = lines_types['ID']
#     lines_lenght = lines['dline']
#
#     if 'outserv' in lines.keys():
#         lines_enables = lines['outserv']
#     else:
#         lines_enables = np.ones(len(lines_ID))
#
#     lines_R = lines_types['rline']
#     lines_L = lines_types['xline']
#     lines_C = lines_types['cline']
#     lines_rate = lines_types['sline']
#     lines_voltage = lines_types['uline']
#     for i in range(len(lines)):
#         line_ = branch_line.copy()
#
#         ID = lines_ID[i]
#         ID_Type = lines_type_id[i]
#         type_idx = np.where(line_types_ID == ID_Type)[0][0]
#
#         buses = terminals_dict[ID]  # arry with the ID of the connection Buses
#         bus1 = buses_dict[buses[0]]
#         bus2 = buses_dict[buses[1]]
#
#         status = lines_enables[i]
#
#         # impedances
#         lenght = np.double(lines_lenght[i])
#         R = np.double(lines_R[type_idx]) * lenght  # Ohm
#         L = np.double(lines_L[type_idx]) * lenght  # Ohm
#         C = np.double(lines_C[type_idx]) * lenght * w *1e-6 # S
#
#         # pass impedance to per unit
#         vbase = np.double(lines_voltage[type_idx])  # kV
#         zbase = vbase**2 / baseMVA  # Ohm
#         ybase = 1.0 / zbase  # S
#         r = R / zbase  # pu
#         l = L / zbase  # pu
#         c = C / ybase  # pu
#
#         # rated power
#         Irated = np.double(lines_rate[type_idx])  # kA
#         Smax = Irated * vbase  # MVA
#
#         # put all in the correct column
#         line_[F_BUS] = bus1
#         line_[T_BUS] = bus2
#         line_[BR_R] = r
#         line_[BR_X] = l
#         line_[BR_B] = c
#         line_[RATE_A] = Smax
#         line_[BR_STATUS] = status
#         BRANCHES.append(line_)
#
#         # add edge to graph
#         # g.add_edge(bus1, bus2)
#
#
#
#     print('Parsing transformers')
#
#     type_ID = transformers_types['ID']
#     HV_nominal_voltage = transformers_types['utrn_h']
#     LV_nominal_voltage = transformers_types['utrn_l']
#     Nominal_power = transformers_types['strn']
#     Copper_losses = transformers_types['pcutr']
#     Iron_losses = transformers_types['pfe']
#     No_load_current = transformers_types['curmg']
#     Short_circuit_voltage = transformers_types['uktr']
#     #GR_hv1 = transformers_types['ID']
#     #GX_hv1 = transformers_types['ID']
#     for i in range(len(transformers)):
#         line_ = branch_line.copy()
#
#         ID = transformers['ID'][i]
#         ID_Type = transformers['typ_id'][i]
#         type_idx = np.where(type_ID == ID_Type)[0][0]
#
#         buses = terminals_dict[ID]  # arry with the ID of the connection Buses
#         bus1 = buses_dict[buses[0]]
#         bus2 = buses_dict[buses[1]]
#
#         Smax = Nominal_power[type_idx]
#
#         Zs, Zsh = get_transformer_impedances(HV_nominal_voltage=HV_nominal_voltage[type_idx],
#                                              LV_nominal_voltage=LV_nominal_voltage[type_idx],
#                                              Nominal_power=Smax,
#                                              Copper_losses=Copper_losses[type_idx],
#                                              Iron_losses=Iron_losses[type_idx],
#                                              No_load_current=No_load_current[type_idx],
#                                              Short_circuit_voltage=Short_circuit_voltage[type_idx],
#                                              GR_hv1=0.5,
#                                              GX_hv1=0.5)
#
#         status = 1 - transformers['outserv'][i]
#
#         # put all in the correct column
#         line_[F_BUS] = bus1
#         line_[T_BUS] = bus2
#         line_[BR_R] = Zs.real
#         line_[BR_X] = Zs.imag
#         line_[BR_B] = Zsh.imag
#         line_[RATE_A] = Smax
#         line_[BR_STATUS] = status
#         BRANCHES.append(line_)
#
#         # add edge to graph
#         # g.add_edge(bus1, bus2)
#
#     print('Parsing Loads')
#     loads_ID = loads['ID']
#     loads_P = loads['plini']
#     loads_Q = loads['qlini']
#     for i in range(len(loads)):
#         ID = loads_ID[i]
#         bus_idx = buses_dict[(terminals_dict[ID][0])]
#
#         p = loads_P[i]  # in MW
#         q = loads_Q[i]  # in MVA
#
#         BUSES[bus_idx, PD] += p
#         BUSES[bus_idx, QD] += q
#
#     print('Parsing external connections')
#     externals_ID = external['ID']
#     for i in range(len(external)):
#         ID = externals_ID[i]
#         bus_idx = buses_dict[(terminals_dict[ID][0])]
#         BUSES[bus_idx, BUS_TYPE] = 3  # slack
#
#         gen_ = gen_line.copy()
#         gen_[GEN_BUS] = bus_idx
#         gen_[VG] = 1.0
#
#         GEN.append(gen_)
#
#     # Prepare to return
#     ppc = dict()
#     BRANCHES = np.array(BRANCHES, dtype=np.object)
#     GEN = np.array(GEN, dtype=np.object)
#
#     BUSES[:, BUS_I] += 1
#     BRANCHES[:, F_BUS] += 1
#     BRANCHES[:, T_BUS] += 1
#     GEN[:, GEN_BUS] += 1
#     ppc["baseMVA"] = baseMVA
#     ppc["bus"] = BUSES
#     ppc["branch"] = BRANCHES
#     ppc["gen"] = GEN
#
#     # print('Plotting grid...')
#     # nx.draw(g, pos=gpos)
#
#     from matplotlib import pyplot as plt
#     plt.show()
#
#     print('Done!')
#
#     return ppc