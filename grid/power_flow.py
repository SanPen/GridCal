# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""
This file contains the classes to run power flow simulations recursively
"""

from scipy.sparse.linalg import splu
from PyQt4.QtCore import QThread, SIGNAL
from warnings import warn

import numpy as np
from numpy import asarray, argmax, arange, array, zeros, pi, exp, r_, c_, conj, \
                  angle, ix_, complex_, nonzero, copy, finfo
from scipy.sparse import csr_matrix
from scipy.optimize import minimize
from .dcpf import dcpf
from .newtonpf import newtonpf
from .iwamoto_nr_pf import IwamotoNR
from .fdpf import fdpf
from .gausspf import gausspf
from .helm import helm
from .Zbus import zbus
from .branch_definitions import *
from .bus_definitions import *
from .gen_definitions import *

from enum import Enum


class SolverType(Enum):
    NR = 1
    NRFD_XB = 2
    NRFD_BX = 3
    GAUSS = 4
    DC = 5,
    HELM = 6,
    ZBUS = 7,
    IWAMOTO = 8


class MultiCircuitPowerFlow(QThread):
    """
    This class handles the power flow simulation that allows the simulation of multiple islands
    """
    def __init__(self, baseMVA,  bus, gen, branch, graph, solver_type, is_an_island=False):
        QThread.__init__(self)

        self.baseMVA = baseMVA
        self.bus = bus.copy()
        self.gen = gen.copy()
        self.branch = branch.copy()
        self.graph = graph.copy()
        self.recalculate_islands = True
        self.solver_type = solver_type

        self.islands_nodes = None
        self.is_an_island = is_an_island
        self.last_power_flow_succeeded = False
        self.grid_survives = True

        self.has_results = False


        # declare results arrays:
        nb = len(self.bus)
        nl = len(self.branch)
        ng = len(gen)
        self.voltage = zeros(nb, dtype=complex)
        self.collapsed_nodes = zeros(nb, dtype=bool)
        self.power = zeros(nb, dtype=complex)
        self.power_from = zeros(nl, dtype=complex)
        self.power_to = zeros(nl, dtype=complex)
        self.losses = zeros(nl, dtype=complex)
        self.loading = zeros(nl, dtype=complex)
        self.current = zeros(nl, dtype=complex)

        if not is_an_island:
            self.island_circuits, self.original_indices, \
            self.recalculate_islands = self.get_islands(self.graph, self.baseMVA, self.bus, self.gen, self.branch)
        else:
            self.circuit_power_flow = self.get_power_flow_instance(solver_type)

        # run options
        self.solver_type = solver_type
        self.tolerance = 1e-3
        self.max_iterations = 20
        self.enforce_reactive_power_limits = True
        self.isMaster = True
        self.cancel = False
        self.solver_to_retry_with = None

    def set_loads(self, P, Q):
        """
        Set the loads powers in all the islands power flows
        @param P:
        @param Q:
        @return:
        """
        for i in range(len(self.island_circuits)):
            idx = self.original_indices[i][0]
            self.island_circuits[i].circuit_power_flow.set_loads(P[idx], Q[idx], in_pu=False)

    def set_generators(self, P):
        """
        Set the generator powers in all the islands power flows
        @param P:
        @return:
        """
        for i in range(len(self.island_circuits)):
            idx = self.original_indices[i][1]
            self.island_circuits[i].circuit_power_flow.set_generators(P[idx], in_pu=False)

    def get_failed_edges(self, branch):
        """
        Returns a list of tuples with the failed edges
        """
        if branch is not None:
            nl = len(branch)
            failed_edges = list()

            for i in range(nl):
                f = int(branch[i, F_BUS])
                t = int(branch[i, T_BUS])
                status = int(branch[i, BR_STATUS])

                if status == 0:
                    failed_edges.append((f, t))

            return failed_edges
        else:
            return None

    def get_islands(self, graph, baseMVA, bus, gen, branch):
        """
        Computes the islands of this circuit and composes the respective island's data structures

        Returns:
            list of Circuit instances with the data of this circuit split by island groups.
        """
        from networkx import connected_components

        # get the failed edges
        failed_edges = self.get_failed_edges(branch)

        # remove the failed edges from the graph
        G = graph.copy()
        if failed_edges is not None:
            for e in failed_edges:
                G.remove_edge(*e)

        # get he groups of nodes that are connected together
        groups = connected_components(G)
        islands = list()
        for island in groups:
            islands.append(list(island))

        nl = len(branch)
        branch[:, O_INDEX] = list(range(nl))

        island_circuits = list()
        original_indices = list()

        for island in islands:
            island.sort()
            original_indices_entry = [None] * 3  # this stores the original indices of bus, gen, branch of the island

            # island is a list of the nodes that form an island
            print(island)

            # populate the buses structure
            bus = array(self.bus[island, :].copy())
            original_indices_entry[0] = island

            # Populate the generators structure
            bus_gen_idx = self.gen[:, GEN_BUS].astype(np.int)

            # for i in range(len(bus_gen_idx)):
            #     if bus_gen_idx[i] in island:
            #         generators.append(self.gen[i, :])
            gen_original_indices = [i for i in range(len(bus_gen_idx)) if bus_gen_idx[i] in island]
            gen = self.gen[gen_original_indices, :]
            original_indices_entry[1] = gen_original_indices

            # Populate the branches structure
            bus_from_idx = self.branch[:, F_BUS].astype(np.int)
            bus_to_idx = self.branch[:, T_BUS].astype(np.int)
            # for i in range(len(bus_from_idx)):
            #     if bus_from_idx[i] in island and bus_to_idx[i] in island:
            #         branches.append(self.branch[i, :].copy())
            branch_original_indices = [i for i in range(len(bus_from_idx)) if bus_from_idx[i] in island and bus_to_idx[i] in island]
            branch = self.branch[branch_original_indices, :].copy()
            original_indices_entry[2] = branch_original_indices

            # new circuit hosting the island grid
            circuit = MultiCircuitPowerFlow(baseMVA, bus, gen, branch, graph, self.solver_type, is_an_island=True)

            # add the circuit to the islands
            island_circuits.append(circuit)

            original_indices.append(original_indices_entry)

        recalculate_islands = False
        return island_circuits, original_indices, recalculate_islands

    def get_power_flow_instance(self, solver_type=SolverType.NR):
        """
        Initializes an instance of the power flow module from this circuit definition
        """

        # now it is needed to re number the buses in all the structures
        if self.is_an_island:
            bus = self.bus.copy()
            gen = self.gen.copy()
            branch = self.branch.copy()

            for i in range(len(bus)):
                # i is the new bus index, the old bus index has to be replaced in the branches and generation structures
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
        else:
            bus = self.bus
            gen = self.gen
            branch = self.branch

        return CircuitPowerFlow(self.baseMVA, bus, branch, gen, solver_type)

    def set_run_options(self, solver_type=SolverType.NRFD_BX, tol=1e-3, max_it=10, enforce_reactive_power_limits=True,
                        isMaster=True, set_last_solution=True, solver_to_retry_with=None):
        self.solver_type = solver_type
        self.tolerance = tol
        self.max_iterations = max_it
        self.enforce_reactive_power_limits = enforce_reactive_power_limits
        self.isMaster = isMaster
        self.set_last_solution = set_last_solution
        self.solver_to_retry_with = solver_to_retry_with

    def run(self):
        """
        Runs a power flow with the current data and fills the structures
        """
        if self.is_an_island:
            if self.circuit_power_flow is None:
                self.circuit_power_flow = self.get_power_flow_instance(self.solver_type)
            else:
                self.circuit_power_flow.solver_type = self.solver_type

            # check if converged
            self.last_power_flow_succeeded = self.circuit_power_flow.run(tol=self.tolerance, max_it=self.max_iterations,
                                                                         enforce_q_limits=self.enforce_reactive_power_limits,
                                                                         remember_last_solution=False, verbose=True,
                                                                         set_last_solution=self.set_last_solution)
            print('Succeeded: ', self.last_power_flow_succeeded)
            if not self.last_power_flow_succeeded:
                if self.solver_to_retry_with is not None:
                    print('Retrying with ', self.solver_to_retry_with)
                    self.circuit_power_flow.solver_type = self.solver_to_retry_with
                    self.last_power_flow_succeeded = self.circuit_power_flow.run(tol=self.tolerance, max_it=self.max_iterations,
                                                                                 enforce_q_limits=self.enforce_reactive_power_limits,
                                                                                 remember_last_solution=False, verbose=True,
                                                                                 set_last_solution=self.set_last_solution)

            self.grid_survives = self.circuit_power_flow.is_the_solution_collapsed()
            # if self.solver_type == SolverType.HELM and not self.last_power_flow_succeeded:
            #     self.grid_survives = False

            # get the nodal results
            self.voltage[:] = self.circuit_power_flow.get_voltage_pu()
            self.collapsed_nodes[:] = 1 - int(self.grid_survives)

            # get the branches results
            self.circuit_power_flow.update_branches_power_flow()  # calculate the branches flow
            # only valid branches are used
            self.power_from[self.circuit_power_flow.in_service_branches] = self.circuit_power_flow.Sf
            self.power_to[self.circuit_power_flow.in_service_branches] = self.circuit_power_flow.St
            self.current[self.circuit_power_flow.in_service_branches] = self.circuit_power_flow.get_branch_current_flows()
            self.loading[self.circuit_power_flow.in_service_branches] = self.circuit_power_flow.get_branch_loading()
            self.losses[self.circuit_power_flow.in_service_branches] = self.circuit_power_flow.get_losses()

        else:
            # run all the islands
            self.last_power_flow_succeeded = [0] * len(self.island_circuits)
            i = 0
            self.cancel = False
            island_count = len(self.island_circuits)
            if self.isMaster:
                self.emit(SIGNAL('progress(float)'), 0.0)
            for island in self.island_circuits:

                # run island power flow
                island.set_run_options(self.solver_type, self.tolerance, self.max_iterations,
                                       self.enforce_reactive_power_limits,
                                       solver_to_retry_with=self.solver_to_retry_with)
                island.run()

                self.last_power_flow_succeeded[i] = island.last_power_flow_succeeded

                b_idx = self.original_indices[i][0]
                br_idx = self.original_indices[i][2]

                # if island.last_power_flow_succeeded or self.solver_type == SolverType.HELM:

                # get the nodal results
                self.voltage[b_idx] = island.voltage
                self.collapsed_nodes[b_idx] = island.collapsed_nodes

                # get the branches results
                # only valid branches are used
                self.power_from[br_idx] = island.power_from
                self.power_to[br_idx] = island.power_to
                self.current[br_idx] = island.current
                self.loading[br_idx] = island.loading
                self.losses[br_idx] = island.losses

                # else:
                #     busm1 = -1.0 * ones(len(b_idx))
                #     brm1 = -1.0 * ones(len(br_idx))
                #
                #     # get the nodal results
                #     self.voltage[b_idx] = busm1
                #     self.collapsed_nodes[b_idx] = 1 - int(self.grid_survives)
                #
                #     # get the branches results
                #     self.power_from[br_idx] = brm1
                #     self.power_to[br_idx] = brm1
                #     self.current[br_idx] = brm1
                #     self.loading[br_idx] = brm1
                #     self.losses[br_idx] = brm1

                # emmit the progress signal
                if self.isMaster:
                    prog = ((i+1)/island_count)*100
                    self.emit(SIGNAL('progress(float)'), prog)
                i += 1

                if self.cancel:
                    break

        self.has_results = True

        if self.isMaster:
            # send the finnish signal
            self.emit(SIGNAL('done()'))

    def end_process(self):
        self.cancel = True

    def run_frequency_simulation(self):
        # frequency drop simulation
        max_t_steps = 1000
        dt = 0.01
        ld = sum(self.bus[:, PD])
        ge = sum(self.gen[:, PG])
        t, Freq = self.frequency_calculation(t0=0,
                                            max_t_steps=max_t_steps,
                                            dt=dt,
                                            fnom=50,
                                            J=5000,
                                            PG=ge,
                                            Droop=16.,
                                            PG_ctrl=100,
                                            PD=ld,
                                            SRL_def=0.01,
                                            AGC_P_def=0.0,
                                            AGC_I_def=0.20,
                                            K=0.10,
                                            P_failure=0.)

        last_freq = Freq[len(Freq)-1]
        print("Load:", ld)
        print("Gen:", ge)
        print("Frequency (" + str(max_t_steps * dt) + "s) = " + str(last_freq))

        # if converged, check if the solution is valid
        if self.last_power_flow_succeeded:
            self.last_power_flow_succeeded = self.circuit_power_flow.is_the_voltage_valid()

        if not self.last_power_flow_succeeded:
            if 49 <= last_freq <= 51:
                # is stable
                self.grid_survives = True
                print("Survives")
            else:
                self.grid_survives = False
        else:
            self.grid_survives = True


class CircuitPowerFlow(object):
    """
    This class handles the power flow of a single connected circuit
    """
    def __init__(self, base_power, bus_struct, branch_struct, gen_struct, solver_type=SolverType.HELM, initialize_solvers=True):
        """
        Constructor

        Args:
            base_power: circuit base power (typically 100 MVA)

            bus_struct: MATPOWER bus structure

            branch_struct: MATPOWER branch structure

            gen_struct: MATPOWER generator structure

            solver_type: type of solver enumerated in the class SolverType
        """

        ################################################################################################################
        # Declaration of variables
        ################################################################################################################
        # base power
        self.baseMVA = 100

        # buses structure
        self.bus = None

        # generators structure
        self.gen = None

        # branches structure
        self.branch = None

        # list of slack bus indices
        self.ref_list = list()

        # list of PV bus indices
        self.pv_list = list()

        # list of pq bus indices
        self.pq_list = list()

        # list of bus types
        self.bus_types = list()

        # list of pv and pq indices for the DC calculation
        self.pvpq_list = list()

        # Admittance matrix
        self.Ybus = None

        # Admittance for the 'from' buses of the branches
        self.Yf = None

        # Admittance for the 'to' buses of the branches
        self.Yt = None

        # Shunt admittances of the nodes
        self.Ysh = None

        # Susceptance matrix for the Fast decoupled algorithm
        self.Bp = None

        self.Bpp = None

        # Bp matrix sparse factorization
        self.Bp_solver = None

        # Bpp matrix sparse factorization
        self.Bpp_solver = None

        # vector of power injections
        self.Sbus = None

        # vector of the initial voltage
        self.V0 = None

        # vector of the taps of the branches
        self.tap = None

        # number of buses
        self.nb = 0

        # number of branches
        self.nl = 0

        # number of generators
        self.ng = 0

        # internal to external bus index mapping index
        self.i2e = list()

        # external to internal bus index mapping index
        self.e2i = list()

        # indices of the generators that are on
        self.active_generators = None

        # list of buses hosting generators
        self.active_generators_buses = None

        # active generators - bus connectivity matrix
        self.Cg = None

        # indices of the offline branches
        self.out_of_service_branches = None

        # indices of the online branches
        self.in_service_branches = None

        # power at the branches 'from' bus
        self.Sf = None

        # power at the branches 'to' bus
        self.St = None

        self.Vn_from = None  # branches nominal voltage at the 'from' side

        self.Vn_to = None  # branches nominal voltage at the 'to' side

        # branch power flow
        self.branch_flows = None

        # solver type being used
        self.solver_type = None

        self.some_power_changed = True

        self.need_to_update_branches_power = True

        self.Va0 = None

        self.B = None

        self.Bf = None

        self.Pbusinj = None

        self.Pfinj = None

        self.EPS = finfo(float).eps
        ################################################################################################################

        self.solver_type = solver_type

        self.baseMVA = base_power
        self.bus = bus_struct.copy()
        self.gen = gen_struct.copy()
        self.branch = branch_struct.copy()

        self.original_load = (self.bus[:, PD] + 1j * self.bus[:, QD]).copy()

        self.generator_P = gen_struct[:, PG].copy()
        self.generator_Q = gen_struct[:, QG].copy()

        self.original_gen = (self.generator_P + 1j * self.generator_Q).copy()

        self.bus_Vm = bus_struct[:, VM].copy()
        self.bus_Va = bus_struct[:, VA].copy()

        # sizes of things
        self.nb = self.bus.shape[0]      # number of buses
        self.nl = self.branch.shape[0]   # number of branches
        self.ng = self.gen.shape[0]      # number of generators

        # create map of external bus numbers to bus indices
        self.i2e = self.bus[:, BUS_I].astype(int)
        self.e2i = zeros(max(self.i2e) + 1, int)
        self.e2i[self.i2e] = arange(self.nb)

        # get bus index lists of each type of bus
        self.ref_list, self.pv_list, self.pq_list, self.bus_types = bustypes(self.bus, self.gen, self.Sbus)
        self.pvpq_list = np.matrix(r_[self.pv_list, self.pq_list])

        # update the elements status (who's on and off)
        self.update_elements_status()

        # initial state
        self.V0 = self.bus[:, VM] * exp(1j * pi/180 * self.bus[:, VA])
        self.V0[self.active_generators_buses] = self.gen[self.active_generators, VG] / abs(self.V0[self.active_generators_buses]) * self.V0[self.active_generators_buses]

        # build admittance matrices
        self.Ybus, self.Yf, self.Yt, self.Ysh, self.A = self.makeYbus(self.baseMVA, self.bus, self.branch)

        # check buses nominal voltage
        self.Vnom = self.bus[:, BASE_KV].astype(np.double)
        if len(np.where(self.Vnom == 0.0)[0]) > 0:
            self.are_zero_Vn = True
            print('Warning: There are buses nominal voltages equal to zero.')
        else:
            self.are_zero_Vn = False

        # from branches nominal voltages
        self.Vn_from = self.bus[self.branch[:, F_BUS].astype(int), BASE_KV]

        # to branches nominal voltages
        self.Vn_to = self.bus[self.branch[:, T_BUS].astype(int), BASE_KV]

        # DC matrices
        self.Bp, self.Bpp = self.makeB(self.baseMVA, self.bus, self.branch, solver_type)

        # reduce B matrices
        pvpq_ = r_[self.pv_list, self.pq_list]
        self.Bp = self.Bp[array([pvpq_]).T, pvpq_].tocsc()  # splu requires a CSC matrix
        self.Bpp = self.Bpp[array([self.pq_list]).T, self.pq_list].tocsc()

        # factor B matrices
        self.Bp_solver = None
        self.Bpp_solver = None
        if initialize_solvers:
            self.Bp_solver = splu(self.Bp)
            self.Bpp_solver = splu(self.Bpp)

        # for DC ##############################################################################################

        # voltage angles in radians
        self.Va0 = self.bus[:, VA] * (pi / 180)

        # build B matrices and phase shift injections
        self.B, self.Bf, self.Pbusinj, self.Pfinj = self.makeBdc(self.baseMVA, self.bus, self.branch)

        # update the power vector from the case data
        self.update_power()

        # update the transformers and lines tap variables
        self.update_taps()

    def set_original_values(self):
        self.gen[:, PG] = self.generator_P.copy()
        self.gen[:, QG] = self.generator_Q.copy()
        self.bus[:, VM] = self.bus_Vm.copy()
        self.bus[:, VA] = self.bus_Va.copy()

        self.V0 = self.bus[:, VM] * exp(1j * pi/180.0 * self.bus[:, VA])
        self.V0[self.active_generators_buses] = self.gen[self.active_generators, VG] / abs(self.V0[self.active_generators_buses]) * self.V0[self.active_generators_buses]

    def update_power(self):
        """
        compute complex bus power injections [generation - load]
        """
        self.Sbus = self.makeSbus(self.baseMVA, self.bus, self.gen, self.active_generators, self.Cg)
        self.some_power_changed = False

    def update_taps(self):
        """
        update the tap configuration of the branch elements
        """
        self.tap = ones(self.nl, dtype=np.complex_)  # default tap ratio = 1 for lines
        xfmr = find(self.branch[:, TAP])  # indices of transformers
        self.tap[xfmr] = self.branch[xfmr, TAP]  # include transformer tap ratios
        self.tap *= exp(1j * pi / 180 * self.branch[:, SHIFT])  # add phase shifters

    def update_elements_status(self):
        """
        Updates the circuit lists
        """
        self.out_of_service_branches = find(self.branch[:, BR_STATUS] == 0)         # out-of-service branches
        self.in_service_branches = find(self.branch[:, BR_STATUS]).astype(int)  # in-service branches
        self.active_generators = find(self.gen[:, GEN_STATUS] > 0)    # which generators are on?
        self.active_generators_buses = self.gen[self.active_generators, GEN_BUS].astype(int)  # what buses are they at?
        ngon = self.active_generators.shape[0]
        self.Cg = sparse((ones(ngon), (self.active_generators_buses, range(ngon))), (self.nb, ngon))

    def update_power_flow_solution(self, V):
        """
        Updates bus, gen, branch data structures to match power flow solution.

        Args:

            V: bus voltages in complex form

        @author: Ray Zimmerman (PSERC Cornell)
        """

        # ---- update bus voltages -----
        self.bus[:, VM] = abs(V)
        self.bus[:, VA] = angle(V) * 180 / pi

        # ---- update Qg for all gens and Pg for slack bus(es) -----
        #  generator info

        #  compute total injected bus powers
        Sbus = V[self.active_generators_buses] * conj(self.Ybus[self.active_generators_buses, :] * V)

        #  update Qg for all generators
        self.gen[:, QG] = zeros(self.gen.shape[0])              # zero out all Qg
        self.gen[self.active_generators, QG] = Sbus.imag * self.baseMVA + self.bus[self.active_generators_buses, QD]    # inj Q + local Qd
        #  ... at this point any buses with more than one generator will have
        #  the total Q dispatch for the bus assigned to each generator. This
        #  must be split between them. We do it first equally, then in proportion
        #  to the reactive range of the generator.

        if len(self.active_generators) > 1:
            #  build connection matrix, element i, j is 1 if gen on(i) at bus j is ON
            nb = self.bus.shape[0]
            ngon = self.active_generators.shape[0]
            Cg = csr_matrix((ones(ngon), (range(ngon), self.active_generators_buses)), (ngon, nb))

            #  divide Qg by number of generators at the bus to distribute equally
            ngg = Cg * Cg.sum(0).T    # ngon x 1, number of gens at this gen's bus
            ngg = asarray(ngg).flatten()  # 1D array
            self.gen[self.active_generators, QG] = self.gen[self.active_generators, QG] / ngg

            #  divide proportionally
            Cmin = csr_matrix((self.gen[self.active_generators, QMIN], (range(ngon), self.active_generators_buses)), (ngon, nb))
            Cmax = csr_matrix((self.gen[self.active_generators, QMAX], (range(ngon), self.active_generators_buses)), (ngon, nb))
            Qg_tot = Cg.T * self.gen[self.active_generators, QG]  # nb x 1 vector of total Qg at each bus
            Qg_min = Cmin.sum(0).T       # nb x 1 vector of min total Qg at each bus
            Qg_max = Cmax.sum(0).T       # nb x 1 vector of max total Qg at each bus
            Qg_min = asarray(Qg_min).flatten()  # 1D array
            Qg_max = asarray(Qg_max).flatten()  # 1D array

            #  gens at buses with Qg range = 0
            ig = find(Cg * Qg_min == Cg * Qg_max)
            Qg_save = self.gen[self.active_generators[ig], QG]
            self.gen[self.active_generators, QG] = self.gen[self.active_generators, QMIN] + (Cg * ((Qg_tot - Qg_min) / (Qg_max - Qg_min + self.EPS))) * (self.gen[self.active_generators, QMAX] -self. gen[self.active_generators, QMIN])    # ^ avoid div by 0
            self.gen[self.active_generators[ig], QG] = Qg_save  # (terms are mult by 0 anyway)

        #  update Pg for slack bus(es)
        #  inj P + local Pd
        for k in range(len(self.ref_list)):
            refgen = find(self.active_generators_buses == self.ref_list[k])  # which is(are) the reference gen(s)?
            self.gen[self.active_generators[refgen[0]], PG] = \
                    Sbus[refgen[0]].real * self.baseMVA + self.bus[self.ref_list[k], PD]
            if len(refgen) > 1:       # more than one generator at this ref bus
                #  subtract off what is generated by other gens at this bus
                self.gen[self.active_generators[refgen[0]], PG] = \
                    self.gen[self.active_generators[refgen[0]], PG] - sum(self.gen[self.active_generators[refgen[1:len(refgen)]], PG])

        # ---- update/compute branch power flows -----
        # complex power at "from" bus
        #self.Sf = V[self.branch[self.in_service_branches, F_BUS].astype(int)] * conj(self.Yf[self.in_service_branches, :] * V) * self.baseMVA
        #  complex power injected at "to" bus
        #self.St = V[self.branch[self.in_service_branches, T_BUS].astype(int)] * conj(self.Yt[self.in_service_branches, :] * V) * self.baseMVA
        # asign the values to the branch structures
        #self.branch[ix_(self.in_service_branches, [PF, QF, PT, QT])] = c_[self.Sf.real, self.Sf.imag, self.St.real, self.St.imag]
        #self.branch[ix_(self.out_of_service_branches, [PF, QF, PT, QT])] = zeros((len(self.out_of_service_branches), 4))

    def update_branches_power_flow(self):
        """
        Updates the branches power flow
        """
        # complex power at "from" bus
        self.Sf = self.V0[self.branch[self.in_service_branches, F_BUS].astype(int)] * conj(self.Yf[self.in_service_branches, :] * self.V0) * self.baseMVA
        #  complex power injected at "to" bus
        self.St = self.V0[self.branch[self.in_service_branches, T_BUS].astype(int)] * conj(self.Yt[self.in_service_branches, :] * self.V0) * self.baseMVA

        self.need_to_update_branches_power = False

    def makeSbus(self, baseMVA, bus, gen, on, Cg):
        """
        Builds the vector of complex bus power injections.
    
        Returns the vector of complex bus power injections, that is, generation
        minus load. Power is expressed in per unit.
    
        @see: L{makeYbus}
    
        @author: Ray Zimmerman (PSERC Cornell)
        """
        # generator info
        #on = find(gen[:, GEN_STATUS] > 0)      # which generators are on?
        #gbus = gen[on, GEN_BUS]                # what buses are they at?
    
        # form net complex bus power injection vector
        #nb = bus.shape[0]
        #ngon = on.shape[0]
    
        # connection matrix, element i, j is 1 if gen on(j) at bus i is ON
        #Cg = sparse((ones(ngon), (gbus, range(ngon))), (nb, ngon))
    
        # power injected by gens plus power injected by loads converted to p.u.
        Sbus = (Cg * (gen[on, PG] + 1j * gen[on, QG]) - (bus[:, PD] + 1j * bus[:, QD])) / baseMVA
    
        return Sbus
    
    def makeYbus(self, baseMVA, bus, branch):
        """Builds the bus admittance matrix and branch admittance matrices.
    
        Returns the full bus admittance matrix (i.e. for all buses) and the
        matrices C{Yf} and C{Yt} which, when multiplied by a complex voltage
        vector, yield the vector currents injected into each line from the
        "from" and "to" buses respectively of each line. Does appropriate
        conversions to p.u.
    
        @see: L{makeSbus}
    
        @author: Ray Zimmerman (PSERC Cornell)
        """
        # constants
        nb = bus.shape[0]     # number of buses
        nl = branch.shape[0]  # number of lines
    
        # check that bus numbers are equal to indices to bus (one set of bus nums)
        if any(bus[:, BUS_I] != list(range(nb))):
            raise Exception('buses must appear in order by bus number\n')
    
        # for each branch, compute the elements of the branch admittance matrix where
        #
        #     | If |   | Yff  Yft |   | Vf |
        #     |    | = |          | * |    |
        #     | It |   | Ytf  Ytt |   | Vt |
        #
        stat = branch[:, BR_STATUS]              # ones at in-service branches
        Ys = stat / (branch[:, BR_R] + 1j * branch[:, BR_X])  # series admittance
        Bc = stat * branch[:, BR_B]              # line charging susceptance
        tap = ones(nl, dtype=complex_)                           # default tap ratio = 1
        i = nonzero(branch[:, TAP])              # indices of non-zero tap ratios
        tap[i] = branch[i, TAP]                  # assign non-zero tap ratios
        tap *= exp(1j * pi / 180 * branch[:, SHIFT])  # add phase shifters
    
        Ytt = Ys + 1j * Bc / 2
        Yff = Ytt / (tap * conj(tap))
        Yft = - Ys / conj(tap)
        Ytf = - Ys / tap
    
        # compute shunt admittance
        # if Psh is the real power consumed by the shunt at V = 1.0 p.u.
        # and Qsh is the reactive power injected by the shunt at V = 1.0 p.u.
        # then Psh - j Qsh = V * conj(Ysh * V) = conj(Ysh) = Gs - j Bs,
        # i.e. Ysh = Psh + j Qsh, so ...
        # vector of shunt admittances
        Ysh = (bus[:, GS] + 1j * bus[:, BS]) / baseMVA
    
        # build connection matrices
        f = branch[:, F_BUS]  # list of "from" buses
        t = branch[:, T_BUS]  # list of "to" buses
    
        # connection matrix for line & from buses
        Cf = csr_matrix((ones(nl), (range(nl), f)), (nl, nb))
        # connection matrix for line & to buses
        Ct = csr_matrix((ones(nl), (range(nl), t)), (nl, nb))
    
        # build Yf and Yt such that Yf * V is the vector of complex branch currents injected
        # at each branch's "from" bus, and Yt is the same for the "to" bus end
        i = r_[range(nl), range(nl)]  # double set of row indices
    
        Yf = csr_matrix((r_[Yff, Yft], (i, r_[f, t])), (nl, nb))
        Yt = csr_matrix((r_[Ytf, Ytt], (i, r_[f, t])), (nl, nb))
        # Yf = spdiags(Yff, 0, nl, nl) * Cf + spdiags(Yft, 0, nl, nl) * Ct
        # Yt = spdiags(Ytf, 0, nl, nl) * Cf + spdiags(Ytt, 0, nl, nl) * Ct
    
        # build Ybus
        Ybus = Cf.T * Yf + Ct.T * Yt + \
            csr_matrix((Ysh, (range(nb), range(nb))), (nb, nb))

        # connectivity matrix
        A = Cf + Ct
    
        return Ybus, Yf, Yt, Ysh, A
    
    def makeBdc(self, baseMVA, bus, branch):
        """Builds the B matrices and phase shift injections for DC power flow.
    
        Returns the B matrices and phase shift injection vectors needed for a
        DC power flow.
        The bus real power injections are related to bus voltage angles by::
            P = Bbus * Va + PBusinj
        The real power flows at the from end the lines are related to the bus
        voltage angles by::
            Pf = Bf * Va + Pfinj
        Does appropriate conversions to p.u.
    
        @see: L{dcpf}
    
        @author: Carlos E. Murillo-Sanchez (PSERC Cornell & Universidad
        Autonoma de Manizales)
        @author: Ray Zimmerman (PSERC Cornell)
        """
        # constants
        nb = bus.shape[0]          # number of buses
        nl = branch.shape[0]       # number of lines
    
        # check that bus numbers are equal to indices to bus (one set of bus nums)
        if any(bus[:, BUS_I] != list(range(nb))):
            raise Exception('makeBdc: buses must be numbered consecutively in bus matrix\n')
    
        # for each branch, compute the elements of the branch B matrix and the phase
        # shift "quiescent" injections, where
        #
        #      | Pf |   | Bff  Bft |   | Vaf |   | Pfinj |
        #      |    | = |          | * |     | + |       |
        #      | Pt |   | Btf  Btt |   | Vat |   | Ptinj |
        #
        stat = branch[:, BR_STATUS]               # ones at in-service branches
        b = stat / branch[:, BR_X]                # series susceptance
        tap = ones(nl)                            # default tap ratio = 1
        i = find(branch[:, TAP])               # indices of non-zero tap ratios
        tap[i] = branch[i, TAP]                   # assign non-zero tap ratios
        b = b / tap
    
        # build connection matrix Cft = Cf - Ct for line and from - to buses
        f = branch[:, F_BUS]                           # list of "from" buses
        t = branch[:, T_BUS]                           # list of "to" buses
        i = r_[range(nl), range(nl)]                   # double set of row indices
        # connection matrix
        Cft = sparse((r_[ones(nl), -ones(nl)], (i, r_[f, t])), (nl, nb))
    
        # build Bf such that Bf * Va is the vector of real branch powers injected
        # at each branch's "from" bus
        Bf = sparse((r_[b, -b], (i, r_[f, t])), shape=(nl, nb))  # = spdiags(b, 0, nl, nl) * Cft
    
        # build Bbus
        Bbus = Cft.T * Bf
    
        # build phase shift injection vectors
        Pfinj = b * (-branch[:, SHIFT] * pi / 180)  # injected at the from bus ...
        # Ptinj = -Pfinj                            # and extracted at the to bus
        Pbusinj = Cft.T * Pfinj                # Pbusinj = Cf * Pfinj + Ct * Ptinj
    
        return Bbus, Bf, Pbusinj, Pfinj
    
    def makeB(self, baseMVA, bus, branch, solver_type):
        """Builds the FDPF matrices, B prime and B double prime.
    
        Returns the two matrices B prime and B double prime used in the fast
        decoupled power flow. Does appropriate conversions to p.u. C{alg} is the
        value of the C{PF_ALG} option specifying the power flow algorithm.
    
        @see: L{fdpf}
    
        @author: Ray Zimmerman (PSERC Cornell)
        """
        # constants
        nb = bus.shape[0]          # number of buses
        nl = branch.shape[0]       # number of lines
    
        # -----  form Bp (B prime)  -----
        temp_branch = copy(branch)                 # modify a copy of branch
        temp_bus = copy(bus)                       # modify a copy of bus
        temp_bus[:, BS] = zeros(nb)                # zero out shunts at buses
        temp_branch[:, BR_B] = zeros(nl)           # zero out line charging shunts
        temp_branch[:, TAP] = ones(nl)             # cancel out taps
        if solver_type == SolverType.NRFD_XB:      # if XB method
            temp_branch[:, BR_R] = zeros(nl)       # zero out line resistance
        Bp = -1 * self.makeYbus(baseMVA, temp_bus, temp_branch)[0].imag
    
        # -----  form Bpp (B double prime)  -----
        temp_branch = copy(branch)                 # modify a copy of branch
        temp_branch[:, SHIFT] = zeros(nl)          # zero out phase shifters
        if solver_type == SolverType.NRFD_BX:      # if BX method
            temp_branch[:, BR_R] = zeros(nl)       # zero out line resistance
        Bpp = -1 * self.makeYbus(baseMVA, bus, temp_branch)[0].imag
    
        return Bp, Bpp

    def run(self, tol=1e-3, max_it=10, enforce_q_limits=True, remember_last_solution=False, verbose=False, set_last_solution=True):
        """
        Runs a power flow.

        Runs a power flow [full AC Newton's method by default] and optionally
        returns the solved values in the data matrices, a flag which is C{True} if
        the algorithm was successful in finding a solution, and the elapsed
        time in seconds. All input arguments are optional. If C{casename} is
        provided it specifies the name of the input data file or dict
        containing the power flow data. The default value is 'case9'.

        If enforce_q_limits=True then
        if any generator reactive power limit is violated after running the AC
        power flow, the corresponding bus is converted to a PQ bus, with Qg at
        the limit, and the case is re-run. The voltage magnitude at the bus
        will deviate from the specified value in order to satisfy the reactive
        power limit. If the reference bus is converted to PQ, the first
        remaining PV bus will be used as the slack bus for the next iteration.
        This may result in the real power output at this generator being
        slightly off from the specified values.

        Enforcing of generator Q limits inspired by contributions from Mu Lin,
        Lincoln University, New Zealand (1/14/05).

        Args:
            tol: solution tolerance

            max_it: maximum number of iterations

            enforce_q_limits: Boolean to review the reactive power limits on PV buses or not

            verbose: Boolean variable to print on the console while solving

        @author: Ray Zimmerman (PSERC Cornell)
        """

        self.need_to_update_branches_power = True

        if not remember_last_solution:
            self.set_original_values()

        if self.some_power_changed:
            self.update_power()

        if self.solver_type == SolverType.DC:
            # initial state

            # compute complex bus power injections [generation - load]
            # adjusted for phase shifters and real shunts
            Pbus = self.Sbus.real - self.Pbusinj - self.bus[:, GS] / self.baseMVA

            # "run" the power flow
            Va = dcpf(self.B, Pbus, self.Va0, self.ref_list, self.pvpq_list)
            V = self.bus[:, VM] * exp(1j * Va)
            self.V0 = V  # Store the voltage solution as the initial solution for later

            # update data matrices with solution
            self.branch[:, [QF, QT]] = zeros((self.nl, 2))
            self.branch[:, PF] = (self.Bf * Va + self.Pfinj) * self.baseMVA
            self.branch[:, PT] = -self.branch[:, PF]
            self.bus[:, VM] = ones(self.nb)
            self.bus[:, VA] = Va * (180 / pi)
            # update Pg for slack generator (1st gen at ref bus)
            # (note: other gens at ref bus are accounted for in Pbus)
            #      Pg = Pinj + Pload + Gs
            #      newPg = oldPg + newPinj - oldPinj
            nref = len(self.ref_list)
            refgen = zeros(nref, dtype=int)
            for k in range(nref):
                temp = find(self.active_generators_buses == self.ref_list[k])
                refgen[k] = self.active_generators[temp[0]]
            self.gen[refgen, PG] += (self.B[self.ref_list, :] * Va - Pbus[self.ref_list]) * self.baseMVA

            success = 1

        else:  # if it is not DC, it is AC.

            if not set_last_solution:
                self.V0 = ones(self.nb, dtype=np.complex)


            if enforce_q_limits:
                ref0 = self.ref_list                    # save index and angle of
                Varef0 = self.bus[ref0, VA]             # original reference bus(es)

                # remember the types because they might change during the iteration
                ref = self.ref_list
                pq = self.pq_list
                pv = self.pv_list
                btypes = self.bus_types

                limited = []                            # list of indices of gens @ Q lims
                fixedQg = zeros(self.gen.shape[0])      # Qg of gens at Q limits

            repeat = True
            while repeat:

                # run the power flow
                if self.solver_type == SolverType.NR:
                    V, success, _ = newtonpf(self.Ybus, self.Sbus, self.V0, pv, pq, tol, max_it, verbose)
                    # success = 1

                elif self.solver_type == SolverType.NRFD_BX or self.solver_type == SolverType.NRFD_XB:

                    if len(pq) != self.Bpp.shape[0]:  # need to rebuild the matrices
                        self.Bp, self.Bpp = self.makeB(self.baseMVA, self.bus, self.branch, self.solver_type)
                        # reduce B matrices
                        pvpq_ = r_[pv, pq]
                        self.Bp = self.Bp[array([pvpq_]).T, pvpq_].tocsc()  # splu requires a CSC matrix
                        self.Bpp = self.Bpp[array([pq]).T, pq].tocsc()
                        # factor B matrices
                        self.Bp_solver = splu(self.Bp)
                        self.Bpp_solver = splu(self.Bpp)

                    V, success, _ = fdpf(self.Ybus, self.Sbus, self.V0, self.Bp_solver, self.Bpp_solver,
                                         pv, pq, tol, max_it, verbose)

                elif self.solver_type == SolverType.GAUSS:
                    V, success, _ = gausspf(self.Ybus, self.Sbus, self.V0, ref, pv, pq, tol, max_it, verbose)

                elif self.solver_type == SolverType.HELM:
                    cmax = 151
                    if len(ref) == 0:
                        ref, pv, pq, btypes = bustypes(self.bus, self.gen, self.Sbus)
                    V = helm(self.Ybus, ref, cmax, self.Sbus, self.V0, btypes, eps=1e-3)
                    success = 1
                    print(V)
                elif self.solver_type == SolverType.IWAMOTO:
                    V, success, _ = IwamotoNR(self.Ybus, self.Sbus, self.V0, pv, pq, tol, max_it, robust=True)

                elif self.solver_type == SolverType.ZBUS:

                    Qlim = dict()
                    jj = 0
                    for ii in self.gen[:, GEN_BUS]:
                        if ii-1 > -1:
                            Qlim[ii-1] = [self.gen[jj, QMIN]/self.baseMVA, self.gen[jj, QMAX]/self.baseMVA]
                        jj += 1

                    V, success = zbus(self.Ybus, ref, max_it, self.Sbus, self.V0, btypes, Qlim, tol, self.V0)

                else:
                    raise Exception('Solver not recognised')

                self.V0 = V  # Store he voltage solution as the initial solution for later

                # update data matrices with solution
                self.update_power_flow_solution(V)  # updates the global variables

                if enforce_q_limits:             # enforce generator Q limits
                    # find gens with violated Q constraints
                    gen_status = self.gen[:, GEN_STATUS] > 0
                    qg_max_lim = self.gen[:, QG] > self.gen[:, QMAX]
                    qg_min_lim = self.gen[:, QG] < self.gen[:, QMIN]

                    # indices of the generators violating the higher reactive power limit
                    mx = find(gen_status & qg_max_lim)
                    # indices of the generators violating the lower reactive power limit
                    mn = find(gen_status & qg_min_lim)

                    if len(mx) > 0 or len(mn) > 0:  # we have some Q limit violations

                        # No PV generators, only the slack is left and it violates its reactive power limits
                        if len(pv) == 0:
                            if verbose:
                                if len(mx) > 0:
                                    warn('Gen ' + str(mx + 1) + ' [only one left] exceeds upper Q limit : INFEASIBLE PROBLEM\n')
                                else:
                                    warn('Gen ' + str(mn + 1) + ' [only one left] exceeds lower Q limit : INFEASIBLE PROBLEM\n')

                            success = 0
                            break

                        # one at a time?
                        if enforce_q_limits == 2:    # fix largest violation, ignore the rest
                            k = argmax(r_[self.gen[mx, QG] - self.gen[mx, QMAX], self.gen[mn, QMIN] - self.gen[mn, QG]])
                            if k > len(mx):
                                mn = mn[k - len(mx)]
                                mx = []
                            else:
                                mx = mx[k]
                                mn = []

                        if verbose and len(mx) > 0:
                            for i in range(len(mx)):
                                print('Gen ' + str(mx[i] + 1) + ' at upper Q limit, converting to PQ bus\n')

                        if verbose and len(mn) > 0:
                            for i in range(len(mn)):
                                print('Gen ' + str(mn[i] + 1) + ' at lower Q limit, converting to PQ bus\n')

                        # save corresponding limit values
                        fixedQg[mx] = self.gen[mx, QMAX]
                        fixedQg[mn] = self.gen[mn, QMIN]
                        mx = r_[mx, mn].astype(int)

                        # convert to PQ bus
                        self.gen[mx, QG] = fixedQg[mx]  # set Qg to binding
                        for i in mx:   # [one at a time, since they may be at same bus]
                            self.gen[i, GEN_STATUS] = 0  # temporarily turn off gen,
                            bi = self.gen[i, GEN_BUS]   # adjust load accordingly,
                            self.bus[bi, [PD, QD]] = (self.bus[bi, [PD, QD]] - self.gen[i, [PG, QG]])

                        if len(ref) > 1 and any(self.bus[self.gen[mx, GEN_BUS], BUS_TYPE] == REF):
                            warn('Sorry, PYPOWER cannot enforce Q limits for slack buses in systems with multiple slacks.')

                        self.bus[self.gen[mx, GEN_BUS].astype(int), BUS_TYPE] = PQ   # set violating PV buses to PQ

                        # update bus index lists of each type of bus
                        ref_temp = ref
                        ref, pv, pq, btypes = bustypes(self.bus, self.gen, self.Sbus)
                        if verbose and ref != ref_temp:
                            print('Bus ', ref, ' is new slack bus\n')

                        limited = r_[limited, mx].astype(int)  # list of generator indices that have been limited
                    else:
                        repeat = 0  # no more generator Q limits violated
                else:
                    repeat = 0  # don't enforce generator Q limits, once is enough

            if enforce_q_limits and len(limited) > 0:
                # restore injections from limited gens [those at Q limits]
                self.gen[limited, QG] = fixedQg[limited]    # restore Qg value,

                for i in limited:  # [one at a time, since they may be at same bus]
                    bi = self.gen[i, GEN_BUS]  # re-adjust load,
                    self.bus[bi, [PD, QD]] = self.bus[bi, [PD, QD]] + self.gen[i, [PG, QG]]
                    self.gen[i, GEN_STATUS] = 1  # and turn gen back on

                if ref != ref0:
                    # adjust voltage angles to make original ref bus correct
                    self.bus[:, VA] = self.bus[:, VA] - self.bus[ref0, VA] + Varef0

        return success

    def get_voltage_pu(self):
        """
        Returns the complex voltage vector that has been computed in per unit values
        """
        return self.V0

    def get_voltage(self):
        """
        Returns the voltage solution in kV
        """
        return self.V0 * self.Vnom

    def get_branch_current_flows(self):
        """
        Computes the current in the circuit branches in kA

        # checked against Digsilent Power Factory
        """
        if not self.are_zero_Vn:

            if self.need_to_update_branches_power:
                self.update_branches_power_flow()

            I_from = self.Sf / (np.sqrt(3) * self.Vn_from[self.in_service_branches])
            I_to = self.St / (np.sqrt(3) * self.Vn_to[self.in_service_branches])
            return np.minimum(I_from, I_to)

        else:
            warn('Since there are nominal voltages equal to zero, it is impossible to compute the currents.')

    def get_branches_power_flow(self):
        """
        Computes the power in the circuit branches in MVA
        Returns:
            Loading values in complex form for AC solvers
            Loading values in real form for DC solvers
        """

        L = self.A * (self.Cg * (self.gen[self.active_generators, PG] + 1j * self.gen[self.active_generators, QG]) \
                      - (self.bus[:, PD] + 1j * self.bus[:, QD]))

        if self.solver_type == SolverType.DC:
            return self.branch[:, PF]
        else:
            if self.need_to_update_branches_power:
                self.update_branches_power_flow()

            return np.minimum(self.Sf, self.St)  # branch_flows

    def get_bus_names(self):
        """
        Get a list of names listing the buses
        """
        names = list(self.bus[:, BUS_I].astype(np.int).astype(np.str_))
        for i in range(self.nb):
            names[i] = 'bus ' + names[i]
        return names

    def get_branches_names(self):
        """
        Get a list of names listing the branches
        """
        from_ = list(self.branch[:, F_BUS].astype(np.int).astype(np.str_))
        to_ = list(self.branch[:, T_BUS].astype(np.int).astype(np.str_))
        names = np.zeros(self.nl, dtype=np.object)
        for i in range(self.nl):
            names[i] = 'branch ' + from_[i] + '-' + to_[i]
        return names

    def get_branch_loading(self):
        """
        Returns the branches loading in per unit with respect to the Rate_A
        """
        idx = np.where(self.branch[self.in_service_branches, RATE_A] != 0)[0]
        if self.solver_type == SolverType.DC:
            return np.abs(self.get_branches_power_flow()[idx]) / self.branch[idx, RATE_A]
        else:
            return np.abs(self.get_branches_power_flow()[idx]) / self.branch[idx, RATE_A]
        # raise Exception('Some branch ratings are zero, therefore the loading calculation cannot be performed.')

    def get_bus_voltage_deviation(self):
        """
        Calculates the voltage deviations magnitudes with sign in such way that
        if a lowe violation is negative and a higher violation is positive

        i.e. for the interval 0.95, 1.05
        a voltage =0.92 would give 0.92-0.95 = -0.03
        a voltage = 1.06 would give 1.06 - 1.05 = 0.01
        """
        high = self.bus[:, VMAX]
        low = self.bus[:, VMIN]
        violates_high = self.bus[:, VM] > high
        violates_low = self.bus[:, VM] < low
        return (violates_high * (self.bus[:, VM] - high)) + (violates_low * (self.bus[:, VM] - low))

    def get_bus_voltage_relative_distance(self):
        """
        Returns the normalized voltage given the boundaries of the voltage
        """
        high = self.bus[:, VMAX]
        low = self.bus[:, VMIN]
        med = (high + low) / 2.0
        V = self.bus[:, VM]
        violates_high = V > med
        violates_low = V < med
        return (violates_high * (V - med))/(high-med) + (violates_low * (med - V))/(med-low)

    def get_losses(self):
        """
        Computes the losses in the branches

        # checked against Digsilent Power Factory
        """
        if self.solver_type == SolverType.DC:
            return np.zeros_like(self.in_service_branches)
        else:
            if self.need_to_update_branches_power:
                self.update_branches_power_flow()
            return np.absolute(self.Sf.real - self.St.real)

    def set_loads(self, P, Q=None, in_pu=True, indices_list=None):
        """
        Set all the systems loads

        Args:
            loads_P: Array of active power loads of the size equal to the number of buses containing the Power

            loads_Q: Array of reactive power loads of the size equal to the number of buses containing the Power

            in_pu: is the power in per unit?

            indices_list: indices of the loads to set, if not None, the power arrays must be of the same size
        """
        if indices_list is None:
            if in_pu:
                self.bus[:, PD] = P * self.baseMVA
                if Q is not None:
                    self.bus[:, QD] = Q * self.baseMVA
            else:
                self.bus[:, PD] = P
                if Q is not None:
                    self.bus[:, QD] = Q
        else:
            if in_pu:
                self.bus[indices_list, PD] = P * self.baseMVA
                if Q is not None:
                    self.bus[indices_list, QD] = Q * self.baseMVA
            else:
                self.bus[indices_list, PD] = P
                if Q is not None:
                    self.bus[indices_list, QD] = Q

        self.some_power_changed = True

    def set_generators(self, P, Q=None, in_pu=True, indices_list=None):
        """
        Set all the systems loads

        Args:
            loads_P: Array of active power generation of the size equal to the number of buses containing the Power

            loads_Q: Array of reactive power generation of the size equal to the number of buses containing the Power

            in_pu: is the power in per unit?

            indices_list: indices of the generators to set, if not None, the power arrays must be of the same size
        """
        if indices_list is None:
            if in_pu:
                self.gen[:, PG] = P * self.baseMVA
                if Q is not None:
                    self.gen[:, QG] = Q * self.baseMVA
            else:
                self.gen[:, PG] = P
                if Q is not None:
                    self.gen[:, QG] = Q
        else:
            if in_pu:
                self.gen[indices_list, PG] = P * self.baseMVA
                if Q is not None:
                    self.gen[indices_list, QG] = Q * self.baseMVA
            else:
                self.gen[indices_list, PG] = P
                if Q is not None:
                    self.gen[indices_list, QG] = Q

        self.some_power_changed = True

    def is_the_voltage_valid(self):
        """
        Returns if the voltage solution is the so called low voltage solution which is mathematically valid, but not
        realistic.
        """
        return not np.any(self.bus[:, VM]<0.0)

    def is_the_solution_collapsed(self):
        return not np.any(self.bus[:, VM]<0.8)

    def re_dispatch_power(self):
        """
        This function re-dispatches the power in order to obtain a stable voltage solution by changing the load in the
        grid.

        Returns:

            True if succeeded or False if not
        """
        np.set_printoptions(precision=3, linewidth=500)
        print("Optimizing load shedding...")

        # calculate the load shedding values
        total_load = sum(self.original_load)
        load_ratios = self.original_load / total_load
        load_idx = np.where(self.original_load > 0)[0]

        P_Q_ratio = self.original_load[load_idx].imag / self.original_load[load_idx].real

        total_gen = sum(self.original_gen[1:]) # skip the first because that'll be the slack

        excess = total_gen - total_load

        load_inc = load_ratios * excess

        modified_loads = self.original_load + load_inc

        x0 = modified_loads[load_idx]

        # set voltage seed
        self.V0 = ones(self.nb, dtype=np.complex)
        self.V0[self.active_generators_buses] = self.gen[self.active_generators, VG] / abs(self.V0[self.active_generators_buses]) * self.V0[self.active_generators_buses]

        # set the loads
        self.bus[:, PD] = modified_loads.real
        self.bus[:, QD] = modified_loads.imag
        self.update_power()

        converged = self.run()

        is_valid = self.is_the_voltage_valid()

        print(self.V0)

        bnds = list()
        for i in load_idx:
            bnds.append((0, self.original_load[i]))

        def f_obj(x):

            self.bus[load_idx, PD] = x
            self.bus[load_idx, QD] = x * P_Q_ratio
            self.update_power()

            self.V0 = ones(self.nb, dtype=np.complex)
            converged = self.run()

            if np.any(np.isnan(self.bus[:, VM])):
                self.bus[:, VM] = zeros(self.nb)

            if converged:
                if self.is_the_voltage_valid():
                    f = max(abs(self.get_bus_voltage_deviation()))
                else:
                    f = 1e6
            else:
                f = 1e6

            print(f, x)
            print(self.bus[:, VM])
            print()
            return f

        res = minimize(f_obj, x0=x0, method='SLSQP', bounds=bnds, tol=1e-2)

        # set the solution
        # f_obj(res.x)
        print("Done!")
        return is_valid


if __name__ == '__main__'and __package__ is None:
    from os import sys, path
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

    from .cases import case9

    #runpf(case9)

