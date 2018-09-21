import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix, diags, csc_matrix, find, coo_matrix
import matplotlib.pyplot as plt
import networkx as nx
from warnings import warn

from GridCal.Engine.BasicStructures import BusMode
from GridCal.Engine.IoStructures import CalculationInputs
from GridCal.Engine.Numerical.JacobianBased import Jacobian

pd.set_option('display.max_columns', None)
pd.set_option('display.expand_frame_repr', False)
pd.set_option('max_colwidth', -1)


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
        self.tap_mod = np.zeros(n_br, dtype=float)
        self.tap_ang = np.zeros(n_br, dtype=float)
        self.br_rates = np.zeros(n_br, dtype=float)
        self.branch_states = np.zeros(n_br, dtype=int)

        self.C_branch_bus_f = lil_matrix((n_br, n_bus), dtype=int)
        self.C_branch_bus_t = lil_matrix((n_br, n_bus), dtype=int)

        self.switch_indices = list()

        # load
        self.load_names = np.empty(n_ld, dtype=object)
        self.load_power = np.zeros(n_ld, dtype=complex)
        self.load_current = np.zeros(n_ld, dtype=complex)
        self.load_admittance = np.zeros(n_ld, dtype=complex)

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

        self.battery_power_profile = np.zeros((n_time, n_batt), dtype=float)
        self.battery_voltage_profile = np.zeros((n_time, n_batt), dtype=float)

        self.C_batt_bus = lil_matrix((n_batt, n_bus), dtype=int)

        # static generator
        self.static_gen_names = np.empty(n_sta_gen, dtype=object)
        self.static_gen_power = np.zeros(n_sta_gen, dtype=complex)

        self.static_gen_power_profile = np.zeros((n_time, n_sta_gen), dtype=complex)

        self.C_sta_gen_bus = lil_matrix((n_sta_gen, n_bus), dtype=int)

        # controlled generator
        self.controlled_gen_names = np.empty(n_ctrl_gen, dtype=object)
        self.controlled_gen_power = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_voltage = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_qmin = np.zeros(n_ctrl_gen, dtype=float)
        self.controlled_gen_qmax = np.zeros(n_ctrl_gen, dtype=float)

        self.controlled_gen_power_profile = np.zeros((n_time, n_ctrl_gen), dtype=float)
        self.controlled_gen_voltage_profile = np.zeros((n_time, n_ctrl_gen), dtype=float)

        self.C_ctrl_gen_bus = lil_matrix((n_ctrl_gen, n_bus), dtype=int)

        # shunt
        self.shunt_names = np.empty(n_sh, dtype=object)
        self.shunt_admittance = np.zeros(n_sh, dtype=complex)

        self.shunt_admittance_profile = np.zeros((n_time, n_sh), dtype=complex)

        self.C_shunt_bus = lil_matrix((n_sh, n_bus), dtype=int)

        # Islands indices
        self.islands = list()  # bus indices per island
        self.island_branches = list()  # branch indices per island

        self.calculation_islands = list()

    def compute(self):
        """
        Compute the cross connectivity matrices to determine the circuit connectivity
        towards the calculation. Additionally, compute the calculation matrices.
        """
        # Declare object to store the calculation inputs
        circuit = CalculationInputs(self.nbus, self.nbr, self.ntime)

        circuit.branch_rates = self.br_rates
        circuit.F = self.F
        circuit.T = self.T
        circuit.bus_names = self.bus_names
        circuit.branch_names = self.branch_names

        ################################################################################################################
        # loads, generators, batteries, etc...
        ################################################################################################################

        # Shunts
        Ysh = self.C_shunt_bus.T * (self.shunt_admittance / self.Sbase)

        # Loads
        S = self.C_load_bus.T * (- self.load_power / self.Sbase)
        I = self.C_load_bus.T * (- self.load_current / self.Sbase)
        Ysh += self.C_load_bus.T * (self.load_admittance / self.Sbase)

        # static generators
        S += self.C_sta_gen_bus.T * (self.static_gen_power / self.Sbase)

        # controlled generators
        S += self.C_ctrl_gen_bus.T * (self.controlled_gen_power / self.Sbase)

        # batteries
        S += self.C_batt_bus.T * (self.battery_power / self.Sbase)

        # assign the values
        circuit.Ysh = Ysh
        circuit.Sbus = S
        circuit.Ibus = I
        circuit.Vbus = self.V0
        circuit.Sbase = self.Sbase
        circuit.types = self.bus_types


        if self.ntime > 0:
            # Shunts
            Ysh_prof = self.C_shunt_bus.T * (self.shunt_admittance_profile.T / self.Sbase)

            # Loads
            I_prof = self.C_load_bus.T * (- self.load_current_profile.T / self.Sbase)
            Ysh_prof += self.C_load_bus.T * (self.load_admittance_profile.T / self.Sbase)

            Sbus_prof = self.C_load_bus.T * (- self.load_power_profile.T / self.Sbase)

            # static generators
            Sbus_prof += self.C_sta_gen_bus.T * (self.static_gen_power_profile.T / self.Sbase)

            # controlled generators
            Sbus_prof += self.C_ctrl_gen_bus.T * (self.controlled_gen_power_profile.T / self.Sbase)

            # batteries
            Sbus_prof += self.C_batt_bus.T * (self.battery_power_profile.T / self.Sbase)

            circuit.Ysh_prof = Ysh_prof
            circuit.Sbus_prof = Sbus_prof
            circuit.Ibus_prof = I_prof
            circuit.time_array = self.time_array

        ################################################################################################################
        # Form the admittance matrix
        ################################################################################################################
        Ys = self.branch_states / (self.R + 1.0j * self.X)
        GBc = self.branch_states * (self.G + 1.0j * self.B)
        tap = self.tap_mod * np.exp(1.0j * self.tap_ang)

        # branch primitives in vector form
        Ytt = Ys + GBc / 2.0
        Yff = Ytt / (tap * np.conj(tap))
        Yft = - Ys / np.conj(tap)
        Ytf = - Ys / tap

        # form the admittance matrices
        Yf = diags(Yff) * self.C_branch_bus_f + diags(Yft) * self.C_branch_bus_t
        Yt = diags(Ytf) * self.C_branch_bus_f + diags(Ytt) * self.C_branch_bus_t
        Ybus = csc_matrix(self.C_branch_bus_f.T * Yf + self.C_branch_bus_t.T * Yt + diags(Ysh))

        # branch primitives in vector form
        Ytts = Ys
        Yffs = Ytts / (tap * np.conj(tap))
        Yfts = - Ys / np.conj(tap)
        Ytfs = - Ys / tap

        # form the admittance matrices of the series elements
        Yfs = diags(Yffs) * self.C_branch_bus_f + diags(Yfts) * self.C_branch_bus_t
        Yts = diags(Ytfs) * self.C_branch_bus_f + diags(Ytts) * self.C_branch_bus_t
        Yseries = csc_matrix(self.C_branch_bus_f.T * Yfs + self.C_branch_bus_t.T * Yts)

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
        B1f = diags(-b1) * self.C_branch_bus_f + diags(-b1) * self.C_branch_bus_t
        B1t = diags(-b1) * self.C_branch_bus_f + diags(-b1) * self.C_branch_bus_t
        B1 = csc_matrix(self.C_branch_bus_f.T * B1f + self.C_branch_bus_t.T * B1t)

        b2 = b1 + self.B
        b2_ff = -(b2 / (tap * np.conj(tap))).real
        b2_ft = -(b1 / np.conj(tap)).real
        b2_tf = -(b1 / tap).real
        b2_tt = - b2
        B2f = diags(b2_ff) * self.C_branch_bus_f + diags(b2_ft) * self.C_branch_bus_t
        B2t = diags(b2_tf) * self.C_branch_bus_f + diags(b2_tt) * self.C_branch_bus_t
        B2 = csc_matrix(self.C_branch_bus_f.T * B2f + self.C_branch_bus_t.T * B2t)

        # assign to the calc element
        circuit.Ybus = Ybus
        circuit.Yf = Yf
        circuit.Yt = Yt
        circuit.B1 = B1
        circuit.B2 = B2
        circuit.Yseries = Yseries
        circuit.C_branch_bus_f = self.C_branch_bus_f
        circuit.C_branch_bus_t = self.C_branch_bus_t

        ################################################################################################################
        # Bus connectivity
        ################################################################################################################
        # branch - bus connectivity
        C_branch_bus = self.C_branch_bus_f + self.C_branch_bus_t

        # Connectivity node - Connectivity node connectivity matrix
        C_bus_bus = C_branch_bus.T * C_branch_bus

        ################################################################################################################
        # Islands
        ################################################################################################################
        # find the islands of the circuit
        self.islands = Graph(csc_matrix(C_bus_bus)).find_islands()

        # find the branches that belong to each island
        circuits = list()
        self.island_branches = list()

        if len(self.islands) > 1:

            # pack the islands
            for island in self.islands:

                # get the branch indices of the island
                island_br_idx = self.get_branches_of_the_island(island, C_branch_bus)
                self.island_branches.append(island_br_idx)

                # set the indices in the island too
                circuit.original_bus_idx = island
                circuit.original_branch_idx = island_br_idx

                # get the island circuit (the bus types are computed automatically)
                circuit = circuit.get_island(island, island_br_idx)

                # store the island
                circuits.append(circuit)
        else:
            # compile bus types
            circuit.compile_types()

            # only one island, no need to split anything
            circuits.append(circuit)

            island = np.arange(start=0, stop=self.nbus, step=1, dtype=int)
            island_br_idx = np.arange(start=0, stop=self.nbr, step=1, dtype=int)

            # set the indices in the island too
            circuit.original_bus_idx = island
            circuit.original_branch_idx = island_br_idx

            # append a list with all the branch indices for completeness
            self.island_branches.append(island_br_idx)

        # return the list of islands
        self.calculation_islands = circuits
        return self.calculation_islands

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



