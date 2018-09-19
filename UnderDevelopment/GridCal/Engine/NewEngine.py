import numpy as np
import pandas as pd
from scipy.sparse import lil_matrix, diags, csc_matrix, find, coo_matrix
import matplotlib.pyplot as plt
import networkx as nx
from warnings import warn

from GridCal.Engine.BasicStructures import BusMode

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


class CalculationResults:

    def __init__(self, nbus, nbr):
        """
        Class to store grid calculated values from Power flow ans State estimation
        """

        # node voltages vector (p.u.)
        self.V = np.zeros(nbus, dtype=complex)

        # node power injections (p.u.)
        self.Sbus = np.zeros(nbus, dtype=complex)

        # branch power injected at the from side (p.u.)
        self.Sf = np.zeros(nbr, dtype=complex)

        # branch power injected at the to side (p.u.)
        self.St = np.zeros(nbr, dtype=complex)

        # branch current injected at the from side (p.u.)
        self.If = np.zeros(nbr, dtype=complex)

        # branch current injected at the to side (p.u.)
        self.It = np.zeros(nbr, dtype=complex)

        # power flowing through the branch (p.u.)
        self.Sbranch = np.zeros(nbr, dtype=complex)

        # current flowing through the branch (p.u.)
        self.Ibranch = np.zeros(nbr, dtype=complex)

        # losses of the branch (p.u.)
        self.losses = np.zeros(nbr, dtype=complex)

        # did this solution converge?
        self.converged = False

        # power mismatch of this solution (p.u.)
        self.error = 0.0

        self.iterations = 0

        self.elapsed = 0

    def merge(self, results, bus_idx, br_idx):

        # node voltages vector (p.u.)
        self.V[bus_idx] = results.V

        # node power injections (p.u.)
        self.Sbus[bus_idx] = results.Sbus

        # branch power injected at the from side (p.u.)
        self.Sf[br_idx] = results.Sf

        # branch power injected at the to side (p.u.)
        self.St[br_idx] = results.St

        # branch current injected at the from side (p.u.)
        self.If[br_idx] = results.If

        # branch current injected at the to side (p.u.)
        self.It[br_idx] = results.It

        # power flowing through the branch (p.u.)
        self.Sbranch[br_idx] = results.Sbranch

        # current flowing through the branch (p.u.)
        self.Ibranch[br_idx] = results.Ibranch

        # losses of the branch (p.u.)
        self.losses[br_idx] = results.losses

        # did this solution converge?
        self.converged *= results.converged

        # power mismatch of this solution (p.u.)
        self.error = max(self.error, results.error)

    def print(self, bus_names, branch_names):
        """
        Print the results
        :return:
        """
        try:

            df_bus = pd.DataFrame(
                np.c_[np.abs(self.V), np.angle(self.V), self.V.real, self.V.imag, self.Sbus.real, self.Sbus.imag],
                index=bus_names, columns=['|V|', 'angle', 're{V}', 'im{V}', 'P', 'Q'])
            # df_bus.sort_index(inplace=True)

            df_branch = pd.DataFrame(
                np.c_[self.losses.real, self.losses.imag, self.Sbranch.real, self.Sbranch.imag],
                index=branch_names, columns=['re{Losses}', 'im{Losses}', 're{S}', 'im{S}'])
            # df_branch.sort_index(inplace=True)

            print('\nResults')
            print('Bus results:\n', df_bus)
            print('\nBranch results:\n', df_branch)
            print('\nConverged:', self.converged)
            print('Error:', self.error)
            print('Iterations:', self.iterations)
            print('Elapsed:', self.elapsed, 's')
        except Exception as e:
            print(e)


class CalculationInputs:

    def __init__(self, nbus, nbr, ntime):
        """
        Constructor
        :param nbus: number of buses
        :param nbr: number of branches
        :param ntime: number of time steps
        """
        self.nbus = nbus
        self.nbr = nbr
        self.ntime = ntime

        self.Sbase = 100.0

        self.time_array = None

        # resulting matrices (calculation)
        self.Yf = csc_matrix((nbr, nbus), dtype=complex)
        self.Yt = csc_matrix((nbr, nbus), dtype=complex)
        self.Ybus = csc_matrix((nbus, nbus), dtype=complex)

        self.Ysh = np.zeros(nbus, dtype=complex)
        self.Sbus = np.zeros(nbus, dtype=complex)
        self.Ibus = np.zeros(nbus, dtype=complex)

        self.Ysh_prof = np.zeros((ntime, nbus), dtype=complex)
        self.Sbus_prof = np.zeros((ntime, nbus), dtype=complex)
        self.Ibus_prof = np.zeros((ntime, nbus), dtype=complex)

        self.Vbus = np.ones(nbus, dtype=complex)
        self.types = np.zeros(nbus, dtype=int)
        self.Qmin = np.zeros(nbus, dtype=float)
        self.Qmax = np.zeros(nbus, dtype=float)

        self.C_branch_bus_f = csc_matrix((nbr, nbus), dtype=complex)
        self.C_branch_bus_t = csc_matrix((nbr, nbus), dtype=complex)

        self.branch_rates = np.zeros(nbr)

        self.pq = list()
        self.pv = list()
        self.ref = list()
        self.sto = list()
        self.pqpv = list()

        self.logger =list()

    def compile_types(self, types_new=None):
        """
        Compile the types
        :param types_new: new array of types to consider
        :return: Nothing
        """
        if types_new is not None:
            self.types = types_new.copy()
        self.pq = np.where(self.types == BusMode.PQ.value[0])[0]
        self.pv = np.where(self.types == BusMode.PV.value[0])[0]
        self.ref = np.where(self.types == BusMode.REF.value[0])[0]
        self.sto = np.where(self.types == BusMode.STO_DISPATCH.value)[0]

        if len(self.ref) == 0:  # there is no slack!

            if len(self.pv) == 0:  # there are no pv neither -> blackout grid

                warn('There are no slack nodes selected')
                self.logger.append('There are no slack nodes selected')

            else:  # select the first PV generator as the slack

                mx = max(self.Sbus[self.pv])
                if mx > 0:
                    # find the generator that is injecting the most
                    i = np.where(self.Sbus == mx)[0][0]

                else:
                    # all the generators are injecting zero, pick the first pv
                    i = self.pv[0]

                # delete the selected pv bus from the pv list and put it in the slack list
                self.pv = np.delete(self.pv, np.where(self.pv == i)[0])
                self.ref = [i]
                # print('Setting bus', i, 'as slack')

            self.ref = np.ndarray.flatten(np.array(self.ref))
            self.types[self.ref] = BusMode.REF.value[0]
        else:
            pass  # no problem :)

        self.pqpv = np.r_[self.pq, self.pv]
        self.pqpv.sort()
        pass

    def get_island(self, bus_idx, branch_idx):
        """
        Get a sub-island
        :param bus_idx: bus indices of the island
        :param branch_idx: branch indices of the island
        :return: CalculationInputs instance
        """
        obj = CalculationInputs(len(bus_idx), len(branch_idx))

        obj.Yf = self.Yf[branch_idx, :][:, bus_idx]
        obj.Yt = self.Yt[branch_idx, :][:, bus_idx]
        obj.Ybus = self.Ybus[bus_idx, :][:, bus_idx]
        obj.Ysh = self.Ysh[bus_idx]
        obj.Sbus = self.Sbus[bus_idx]
        obj.Ibus = self.Ibus[bus_idx]
        obj.Vbus = self.Vbus[bus_idx]
        obj.types = self.types[bus_idx]
        obj.Qmin = self.Qmin[bus_idx]
        obj.Qmax = self.Qmax[bus_idx]

        obj.C_branch_bus_f = self.C_branch_bus_f[branch_idx, :][:, bus_idx]
        obj.C_branch_bus_t = self.C_branch_bus_t[branch_idx, :][:, bus_idx]

        obj.compile_types()

        return obj

    def compute_branch_results(self, V):
        """
        Compute the branch magnitudes from the voltages
        :param V: Voltage vector solution in p.u.
        :return: CalculationResults instance with all the grid magnitudes
        """

        # declare circuit results
        data = CalculationResults(self.nbus, self.nbr)

        # copy the voltage
        data.V = V

        # power at the slack nodes
        data.Sbus = self.Sbus.copy()
        data.Sbus[self.ref] = V[self.ref] * np.conj(self.Ybus[self.ref, :].dot(V))

        # Reactive power at the pv nodes: keep the original P injection and set the calculated reactive power
        Q = (V[self.pv] * np.conj(self.Ybus[self.pv, :].dot(V))).imag

        data.Sbus[self.pv] = self.Sbus[self.pv].real + 1j * Q

        # Branches current, loading, etc
        data.If = self.Yf * V
        data.It = self.Yt * V
        data.Sf = self.C_branch_bus_f * V * np.conj(data.If)
        data.St = self.C_branch_bus_t * V * np.conj(data.It)

        # Branch losses in MVA
        data.losses = (data.Sf + data.St)

        # Branch current in p.u.
        data.Ibranch = np.maximum(data.If, data.It)

        # Branch power in MVA
        data.Sbranch = np.maximum(data.Sf, data.St)

        # Branch loading in p.u.
        data.loading = data.Sbranch / (self.branch_rates + 1e-9)

        return data

    def print(self, bus_names):
        """
        print in console
        :return:
        """
        # print('\ntypes\n', self.types)
        # print('\nSbus\n', self.Sbus)
        # print('\nVbus\n', self.Vbus)
        # print('\nYsh\n', self.Ysh)

        df_bus = pd.DataFrame(
            np.c_[self.types, np.abs(self.Vbus), np.angle(self.Vbus), self.Vbus.real, self.Vbus.imag,
                  self.Sbus.real, self.Sbus.imag, self.Ysh.real, self.Ysh.imag],
            index=bus_names, columns=['Type', '|V|', 'angle', 're{V}', 'im{V}', 'P', 'Q', 'Gsh', 'Bsh'])
        # df_bus.sort_index(inplace=True)

        print('\nBus info\n', df_bus)

        if self.nbus < 100:
            print('\nYbus\n', pd.DataFrame(self.Ybus.todense(), columns=bus_names, index=bus_names))

        print('PQ:', self.pq)
        print('PV:', self.pv)
        print('REF:', self.ref)


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
        self.bus_types = np.empty(n_bus, dtype=int)

        # branch
        self.branch_names = np.empty(n_br, dtype=object)

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

    def compute(self):
        """
        Compute the cross connectivity matrices to determine the circuit connectivity
        towards the calculation. Additionally, compute the calculation matrices.
        """
        # Declare object to store the calculation inputs
        circuit = CalculationInputs(self.nbus, self.nbr, self.ntime)

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

        # assign to the calc element
        circuit.Ybus = Ybus
        circuit.Yf = Yf
        circuit.Yt = Yt
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

                # get the island circuit (the bus types are computed automatically)
                circuit = circuit.get_island(island, island_br_idx)

                # store the island
                circuits.append(circuit)
        else:
            # compile bus types
            circuit.compile_types()

            # only one island, no need to split anything
            circuits.append(circuit)

            # append a list with all the branch indices for completeness
            self.island_branches.append(np.arange(start=0, stop=self.nbr, step=1, dtype=int))

        # return the list of islands
        return circuits

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



