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
import networkx as nx
from scipy.sparse import lil_matrix, diags, csc_matrix
from typing import List, Dict


from GridCal.Engine.Core.csc_graph import Graph
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.Core.calculation_inputs import CalculationInputs


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

        for l in range(A.indptr[j], A.indptr[j + 1]):
            i = A.indices[l]  # row index

            if not visited[i]:
                visited[i] = True
                br_idx[n_visited] = i
                n_visited += 1

    # resize vector
    br_idx = br_idx[:n_visited]

    return br_idx


def calc_connectivity(branch_active, C_branch_bus_f, C_branch_bus_t, apply_temperature, R_corrected, R, X, G, B,
                      branch_tolerance_mode: BranchImpedanceMode, impedance_tolerance, tap_mod, tap_ang, tap_t, tap_f,
                      Ysh):
    """
    Build all the admittance related objects
    :param branch_active: array of branch active
    :param C_branch_bus_f: branch-bus from connectivity matrix
    :param C_branch_bus_t: branch-bus to connectivity matrix
    :param apply_temperature: apply temperature correction?
    :param R_corrected: Use the corrected resistance?
    :param R: array of resistance
    :param X: array of reactance
    :param G: array of conductance
    :param B: array of susceptance
    :param branch_tolerance_mode: branch tolerance mode (enum: BranchImpedanceMode)
    :param impedance_tolerance: impedance tolerance
    :param tap_mod: tap modules array
    :param tap_ang: tap angles array
    :param tap_t: virtual tap to array
    :param tap_f: virtual tap from array
    :param Ysh: shunt admittance injections
    :return: Ybus: Admittance matrix
             Yf: Admittance matrix of the from buses
             Yt: Admittance matrix of the to buses
             B1: Fast decoupled B' matrix
             B2: Fast decoupled B'' matrix
             Yseries: Admittance matrix of the series elements
             Ys: array of series admittances
             GBc: array of shunt conductances
             Cf: Branch-bus from connectivity matrix
             Ct: Branch-to from connectivity matrix
             C_bus_bus: Adjacency matrix
             C_branch_bus: branch-bus connectivity matrix
             islands: List of islands bus indices (each list element is a list of bus indices of the island)
    """
    # form the connectivity matrices with the states applied
    states_dia = diags(branch_active)
    Cf = states_dia * C_branch_bus_f
    Ct = states_dia * C_branch_bus_t

    # use the specified of the temperature-corrected resistance
    if apply_temperature:
        R = R_corrected
    else:
        R = R

    # modify the branches impedance with the lower, upper tolerance values
    if branch_tolerance_mode == BranchImpedanceMode.Lower:
        R *= (1 - impedance_tolerance / 100.0)
    elif branch_tolerance_mode == BranchImpedanceMode.Upper:
        R *= (1 + impedance_tolerance / 100.0)
    else:
        pass

    Ys = 1.0 / (R + 1.0j * X)
    GBc = G + 1.0j * B
    tap = tap_mod * np.exp(1.0j * tap_ang)

    # branch primitives in vector form
    Ytt = (Ys + GBc / 2.0) / (tap_t * tap_t)
    Yff = (Ys + GBc / 2.0) / (tap_f * tap_f * tap * np.conj(tap))
    Yft = - Ys / (tap_f * tap_t * np.conj(tap))
    Ytf = - Ys / (tap_t * tap_f * tap)

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
    b1 = 1.0 / (X + 1e-20)
    B1f = diags(-b1) * Cf + diags(-b1) * Ct
    B1t = diags(-b1) * Cf + diags(-b1) * Ct
    B1 = csc_matrix(Cf.T * B1f + Ct.T * B1t)

    b2 = b1 + B
    b2_ff = -(b2 / (tap * np.conj(tap))).real
    b2_ft = -(b1 / np.conj(tap)).real
    b2_tf = -(b1 / tap).real
    b2_tt = - b2
    B2f = diags(b2_ff) * Cf + diags(b2_ft) * Ct
    B2t = diags(b2_tf) * Cf + diags(b2_tt) * Ct
    B2 = csc_matrix(Cf.T * B2f + Ct.T * B2t)

    ################################################################################################################
    # Bus connectivity
    ################################################################################################################
    # branch - bus connectivity
    C_branch_bus = Cf + Ct

    # Connectivity node - Connectivity node connectivity matrix
    C_bus_bus = C_branch_bus.T * C_branch_bus

    return Ybus, Yf, Yt, B1, B2, Yseries, Ys, GBc, Cf, Ct, C_bus_bus, C_branch_bus


def calc_islands(circuit: CalculationInputs, C_bus_bus, C_branch_bus, C_gen_bus, C_batt_bus,
                 nbus, nbr, time_idx=None) -> List[CalculationInputs]:
    """
    Partition the circuit in islands for the designated time intervals
    :param circuit: CalculationInputs instance with all the data regardless of the islands and the branch states
    :param C_bus_bus: bus-bus connectivity matrix
    :param C_branch_bus: branch-bus connectivity matrix
    :param C_gen_bus: gen-bus connectivity matrix
    :param C_batt_bus: battery-bus connectivity matrix
    :param nbus: number of buses
    :param nbr: number of branches
    :param time_idx: array with the time indices where this set of islands belongs to
                    (if None all the time series are kept)
    :return: list of CalculationInputs instances
    """
    # find the islands of the circuit
    islands = Graph(csc_matrix(C_bus_bus)).find_islands()

    # clear the list of circuits
    calculation_islands = list()

    # find the branches that belong to each island
    island_branches = list()

    if len(islands) > 1:

        # there are islands, pack the islands into sub circuits
        for island_bus_idx in islands:
            # get the branch indices of the island
            island_br_idx = get_branches_of_the_island(island_bus_idx, C_branch_bus)
            island_br_idx = np.sort(island_br_idx)  # sort
            island_branches.append(island_br_idx)

            # indices of batteries and controlled generators that belong to this island
            gen_idx = np.where(C_gen_bus[:, island_bus_idx].sum(axis=0) > 0)[0]
            bat_idx = np.where(C_batt_bus[:, island_bus_idx].sum(axis=0) > 0)[0]

            # Get the island circuit (the bus types are computed automatically)
            # The island original indices are generated within the get_island function
            circuit_island = circuit.get_island(island_bus_idx, island_br_idx, gen_idx, bat_idx)

            if time_idx is not None:
                circuit_island.trim_profiles(time_idx=time_idx)

            # store the island
            calculation_islands.append(circuit_island)

    else:
        # Only one island

        # compile bus types
        circuit.consolidate()

        # only one island, no need to split anything
        calculation_islands.append(circuit)

        island_bus_idx = np.arange(start=0, stop=nbus, step=1, dtype=int)
        island_br_idx = np.arange(start=0, stop=nbr, step=1, dtype=int)

        # set the indices in the island too
        circuit.original_bus_idx = island_bus_idx
        circuit.original_branch_idx = island_br_idx

        if time_idx is not None:
            circuit.trim_profiles(time_idx=time_idx)

        # append a list with all the branch indices for completeness
        island_branches.append(island_br_idx)

    # return the list of islands
    return calculation_islands


class NumericalCircuit:

    def __init__(self, n_bus, n_br, n_ld, n_gen, n_sta_gen, n_batt, n_sh, n_time, Sbase):
        """
        Topology constructor
        :param n_bus: number of nodes
        :param n_br: number of branches
        :param n_ld: number of loads
        :param n_gen: number of generators
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

        self.n_ctrl_gen = n_gen

        self.n_ld = n_ld

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
        self.impedance_tolerance = np.zeros(n_br, dtype=float)
        self.tap_f = np.ones(n_br, dtype=float)  # tap generated by the difference in nominal voltage at the form side
        self.tap_t = np.ones(n_br, dtype=float)  # tap generated by the difference in nominal voltage at the to side
        self.tap_mod = np.zeros(n_br, dtype=float)  # normal tap module
        self.tap_ang = np.zeros(n_br, dtype=float)  # normal tap angle
        self.br_rates = np.zeros(n_br, dtype=float)

        self.branch_active = np.zeros(n_br, dtype=int)
        self.branch_active_prof = np.zeros((n_time, n_br), dtype=int)
        self.temp_oper_prof = np.zeros((n_time, n_br), dtype=float)

        self.br_mttf = np.zeros(n_br, dtype=float)
        self.br_mttr = np.zeros(n_br, dtype=float)

        self.temp_base = np.zeros(n_br, dtype=float)
        self.temp_oper = np.zeros(n_br, dtype=float)
        self.alpha = np.zeros(n_br, dtype=float)

        self.is_bus_to_regulated = np.zeros(n_br, dtype=bool)
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
        self.load_active = np.zeros(n_ld, dtype=bool)
        self.load_active_prof = np.zeros((n_time, n_ld), dtype=bool)

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

        self.battery_dispatchable = np.zeros(n_batt, dtype=bool)
        self.battery_active = np.zeros(n_batt, dtype=bool)
        self.battery_active_prof = np.zeros((n_time, n_batt), dtype=bool)
        self.battery_mttf = np.zeros(n_batt, dtype=float)
        self.battery_mttr = np.zeros(n_batt, dtype=float)

        self.battery_power_profile = np.zeros((n_time, n_batt), dtype=float)
        self.battery_voltage_profile = np.zeros((n_time, n_batt), dtype=float)

        self.C_batt_bus = lil_matrix((n_batt, n_bus), dtype=int)

        # static generator
        self.static_gen_names = np.empty(n_sta_gen, dtype=object)
        self.static_gen_power = np.zeros(n_sta_gen, dtype=complex)
        self.static_gen_dispatchable = np.zeros(n_sta_gen, dtype=bool)

        self.static_gen_active = np.zeros(n_sta_gen, dtype=bool)
        self.static_gen_active_prof = np.zeros((n_time, n_sta_gen), dtype=bool)

        self.static_gen_mttf = np.zeros(n_sta_gen, dtype=float)
        self.static_gen_mttr = np.zeros(n_sta_gen, dtype=float)

        self.static_gen_power_profile = np.zeros((n_time, n_sta_gen), dtype=complex)

        self.C_sta_gen_bus = lil_matrix((n_sta_gen, n_bus), dtype=int)

        # controlled generator
        self.generator_names = np.empty(n_gen, dtype=object)
        self.generator_power = np.zeros(n_gen, dtype=float)
        self.generator_power_factor = np.zeros(n_gen, dtype=float)
        self.generator_voltage = np.zeros(n_gen, dtype=float)
        self.generator_qmin = np.zeros(n_gen, dtype=float)
        self.generator_qmax = np.zeros(n_gen, dtype=float)
        self.generator_pmin = np.zeros(n_gen, dtype=float)
        self.generator_pmax = np.zeros(n_gen, dtype=float)
        self.generator_dispatchable = np.zeros(n_gen, dtype=bool)
        self.generator_controllable = np.zeros(n_gen, dtype=bool)

        self.generator_active = np.zeros(n_gen, dtype=bool)
        self.generator_active_prof = np.zeros((n_time, n_gen), dtype=bool)

        self.generator_mttf = np.zeros(n_gen, dtype=float)
        self.generator_mttr = np.zeros(n_gen, dtype=float)

        self.generator_power_profile = np.zeros((n_time, n_gen), dtype=float)
        self.generator_power_factor_profile = np.zeros((n_time, n_gen), dtype=float)
        self.generator_voltage_profile = np.zeros((n_time, n_gen), dtype=float)

        self.C_gen_bus = lil_matrix((n_gen, n_bus), dtype=int)

        # shunt
        self.shunt_names = np.empty(n_sh, dtype=object)
        self.shunt_admittance = np.zeros(n_sh, dtype=complex)

        self.shunt_active = np.zeros(n_sh, dtype=bool)
        self.shunt_active_prof = np.zeros((n_time, n_sh), dtype=bool)

        self.shunt_mttf = np.zeros(n_sh, dtype=float)
        self.shunt_mttr = np.zeros(n_sh, dtype=float)

        self.shunt_admittance_profile = np.zeros((n_time, n_sh), dtype=complex)

        self.C_shunt_bus = lil_matrix((n_sh, n_bus), dtype=int)

        # Islands indices
        # self.islands = list()  # bus indices per island
        # self.island_branches = list()  # branch indices per island
        #
        # self.calculation_islands = list()

    def get_different_states(self):
        """
        Get a dictionary of different connectivity states
        :return: dictionary of states  {master state index -> list of states associated}
        """

        # initialize
        states = dict()

        for t in range(self.ntime):

            # search this state in the already existing states
            found = False
            for t2 in states.keys():
                if (self.branch_active_prof[t, :] == self.branch_active_prof[t2, :]).all():
                    states[t2].append(t)
                    found = True

            if not found:
                # new state found (append itself)
                states[t] = [t]

        return states

    def get_raw_circuit(self, add_generation, add_storage) -> CalculationInputs:
        """

        :param add_generation:
        :param add_storage:
        :return:
        """
        # Declare object to store the calculation inputs
        circuit = CalculationInputs(self.nbus, self.nbr, self.ntime, self.n_batt, self.n_ctrl_gen)

        # branches
        circuit.branch_rates = self.br_rates
        circuit.F = self.F
        circuit.T = self.T
        circuit.tap_f = self.tap_f
        circuit.tap_t = self.tap_t
        circuit.bus_names = self.bus_names
        circuit.branch_names = self.branch_names

        # connectivity matrices
        circuit.C_load_bus = self.C_load_bus
        circuit.C_batt_bus = self.C_batt_bus
        circuit.C_sta_gen_bus = self.C_sta_gen_bus
        circuit.C_ctrl_gen_bus = self.C_gen_bus
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
        circuit.tap_mod = self.tap_mod

        # active power control
        circuit.controlled_gen_pmin = self.generator_pmin
        circuit.controlled_gen_pmax = self.generator_pmax
        circuit.controlled_gen_enabled = self.generator_active
        circuit.controlled_gen_dispatchable = self.generator_dispatchable
        circuit.battery_pmin = self.battery_pmin
        circuit.battery_pmax = self.battery_pmax
        circuit.battery_Enom = self.battery_Enom
        circuit.battery_soc_0 = self.battery_soc_0
        circuit.battery_discharge_efficiency = self.battery_discharge_efficiency
        circuit.battery_charge_efficiency = self.battery_charge_efficiency
        circuit.battery_min_soc = self.battery_min_soc
        circuit.battery_max_soc = self.battery_max_soc
        circuit.battery_enabled = self.battery_active
        circuit.battery_dispatchable = self.battery_dispatchable

        ################################################################################################################
        # loads, generators, batteries, etc...
        ################################################################################################################

        # Shunts
        Ysh = self.C_shunt_bus.T * (self.shunt_admittance / self.Sbase)

        # Loads
        S = self.C_load_bus.T * (- self.load_power / self.Sbase * self.load_active)
        I = self.C_load_bus.T * (- self.load_current / self.Sbase * self.load_active)
        Ysh += self.C_load_bus.T * (self.load_admittance / self.Sbase * self.load_active)

        if add_generation:
            # static generators
            S += self.C_sta_gen_bus.T * (self.static_gen_power / self.Sbase * self.static_gen_active)

            # generators
            pf2 = np.power(self.generator_power_factor, 2.0)
            # compute the reactive power from the active power and the power factor
            pf_sign = (self.generator_power_factor + 1e-20) / np.abs(self.generator_power_factor + 1e-20)
            Q = pf_sign * self.generator_power * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
            gen_S = self.generator_power + 1j * Q
            S += self.C_gen_bus.T * (gen_S / self.Sbase * self.generator_active)

        # batteries
        if add_storage:
            S += self.C_batt_bus.T * (self.battery_power / self.Sbase * self.battery_active)

        # Qmax
        q_max = self.C_gen_bus.T * (self.generator_qmax / self.Sbase)
        q_max += self.C_batt_bus.T * (self.battery_qmax / self.Sbase)

        # Qmin
        q_min = self.C_gen_bus.T * (self.generator_qmin / self.Sbase)
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

        # if there are profiles...
        if self.ntime > 0:
            # Shunts
            Ysh_prof = self.C_shunt_bus.T * (self.shunt_admittance_profile / self.Sbase * self.shunt_active).T

            # Loads
            I_prof = self.C_load_bus.T * (- self.load_current_profile / self.Sbase * self.load_active).T
            Ysh_prof += self.C_load_bus.T * (self.load_admittance_profile / self.Sbase * self.load_active).T

            Sbus_prof = self.C_load_bus.T * (- self.load_power_profile / self.Sbase * self.load_active).T

            if add_generation:
                # static generators
                Sbus_prof += self.C_sta_gen_bus.T * (
                        self.static_gen_power_profile / self.Sbase * self.static_gen_active).T

                # generators
                pf2 = np.power(self.generator_power_factor_profile, 2.0)
                # compute the reactive power from the active power and the power factor
                pf_sign = (self.generator_power_factor_profile + 1e-20) / np.abs(
                    self.generator_power_factor_profile + 1e-20)
                Q = pf_sign * self.generator_power_profile * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
                gen_S = self.generator_power_profile + 1j * Q
                Sbus_prof += self.C_gen_bus.T * (gen_S / self.Sbase * self.generator_active).T

            # batteries
            if add_storage:
                Sbus_prof += self.C_batt_bus.T * (self.battery_power_profile / self.Sbase * self.battery_active).T

            circuit.Ysh_prof = Ysh_prof
            circuit.Sbus_prof = Sbus_prof
            circuit.Ibus_prof = I_prof
            circuit.time_array = self.time_array

        return circuit

    def compute(self, add_storage=True, add_generation=True, apply_temperature=False,
                branch_tolerance_mode=BranchImpedanceMode.Specified) -> List[CalculationInputs]:
        """
        Compute the cross connectivity matrices to determine the circuit connectivity
        towards the calculation. Additionally, compute the calculation matrices.
        :param add_storage:
        :param add_generation:
        :param apply_temperature:
        :param branch_tolerance_mode:
        :return: list of CalculationInputs instances where each one is a circuit island
        """

        # get the raw circuit with the inner arrays computed
        circuit = self.get_raw_circuit(add_generation=add_generation, add_storage=add_storage)

        # compute the connectivity and the different admittance matrices
        circuit.Ybus, \
        circuit.Yf, \
        circuit.Yt, \
        circuit.B1, \
        circuit.B2, \
        circuit.Yseries, \
        circuit.Ys, \
        circuit.GBc, \
        circuit.C_branch_bus_f, \
        circuit.C_branch_bus_t, \
        C_bus_bus, \
        C_branch_bus = calc_connectivity(branch_active=self.branch_active,
                                         C_branch_bus_f=self.C_branch_bus_f,
                                         C_branch_bus_t=self.C_branch_bus_t,
                                         apply_temperature=apply_temperature,
                                         R_corrected=self.R_corrected(),
                                         R=self.R,
                                         X=self.X,
                                         G=self.G,
                                         B=self.B,
                                         branch_tolerance_mode=branch_tolerance_mode,
                                         impedance_tolerance=self.impedance_tolerance,
                                         tap_mod=self.tap_mod,
                                         tap_ang=self.tap_ang,
                                         tap_t=self.tap_t,
                                         tap_f=self.tap_f,
                                         Ysh=circuit.Ysh)

        #  split the circuit object into the individual circuits that may arise from the topological islands
        calculation_islands = calc_islands(circuit=circuit,
                                           C_bus_bus=C_bus_bus,
                                           C_branch_bus=C_branch_bus,
                                           C_gen_bus=self.C_gen_bus,
                                           C_batt_bus=self.C_batt_bus,
                                           nbus=self.nbus,
                                           nbr=self.nbr,
                                           time_idx=None)

        for island in calculation_islands:
            self.bus_types[island.original_bus_idx] = island.types

        # return the list of islands
        return calculation_islands

    def compute_ts(self, add_storage=True, add_generation=True, apply_temperature=False,
                   branch_tolerance_mode=BranchImpedanceMode.Specified) -> Dict[int, List[CalculationInputs]]:
        """
        Compute the cross connectivity matrices to determine the circuit connectivity
        towards the calculation. Additionally, compute the calculation matrices.
        :param add_storage:
        :param add_generation:
        :param apply_temperature:
        :param branch_tolerance_mode:
        :return: dictionary of lists of CalculationInputs instances where each one is a circuit island
        """

        # get the raw circuit with the inner arrays computed
        circuit = self.get_raw_circuit(add_generation=add_generation, add_storage=add_storage)

        states = self.get_different_states()

        calculation_islands_collection = dict()

        for t, t_array in states.items():

            # compute the connectivity and the different admittance matrices
            circuit.Ybus, \
             circuit.Yf, \
             circuit.Yt, \
             circuit.B1, \
             circuit.B2, \
             circuit.Yseries, \
             circuit.Ys, \
             circuit.GBc, \
             circuit.C_branch_bus_f, \
             circuit.C_branch_bus_t, \
             C_bus_bus, \
             C_branch_bus = calc_connectivity(branch_active=self.branch_active_prof[t, :],
                                              C_branch_bus_f=self.C_branch_bus_f,
                                              C_branch_bus_t=self.C_branch_bus_t,
                                              apply_temperature=apply_temperature,
                                              R_corrected=self.R_corrected(t),
                                              R=self.R,
                                              X=self.X,
                                              G=self.G,
                                              B=self.B,
                                              branch_tolerance_mode=branch_tolerance_mode,
                                              impedance_tolerance=self.impedance_tolerance,
                                              tap_mod=self.tap_mod,
                                              tap_ang=self.tap_ang,
                                              tap_t=self.tap_t,
                                              tap_f=self.tap_f,
                                              Ysh=circuit.Ysh_prof[:, t])

            #  split the circuit object into the individual circuits that may arise from the topological islands
            calculation_islands = calc_islands(circuit=circuit,
                                               C_bus_bus=C_bus_bus,
                                               C_branch_bus=C_branch_bus,
                                               C_gen_bus=self.C_gen_bus,
                                               C_batt_bus=self.C_batt_bus,
                                               nbus=self.nbus,
                                               nbr=self.nbr,
                                               time_idx=t_array)

            calculation_islands_collection[t] = calculation_islands

            if t == 0:
                for island in calculation_islands:
                    self.bus_types[island.original_bus_idx] = island.types

        # return the list of islands
        return calculation_islands_collection

    def R_corrected(self, t=None):
        """
        Returns temperature corrected resistances (numpy array) based on a formula
        provided by: NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        if t is None:
            return self.R * (1.0 + self.alpha * (self.temp_oper - self.temp_base))
        else:
            return self.R * (1.0 + self.alpha * (self.temp_oper_prof[t, :] - self.temp_base))

    def get_B(self, apply_temperature=False):
        """

        :param apply_temperature:
        :return:
        """

        # Shunts
        Ysh = self.C_shunt_bus.T * (self.shunt_admittance / self.Sbase)

        # Loads
        Ysh += self.C_load_bus.T * (self.load_admittance / self.Sbase * self.load_active)

        # form the connectivity matrices with the states applied
        states_dia = diags(self.branch_active)
        Cf = states_dia * self.C_branch_bus_f
        Ct = states_dia * self.C_branch_bus_t

        if apply_temperature:
            R = self.R_corrected()
        else:
            R = self.R

        Ys = 1.0 / (R + 1.0j * self.X)
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

    def power_flow_post_process(self, V, only_power=False, t=0):
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
            Sbus = circuit.Sbus[t, :]

            vd = circuit.ref
            pv = circuit.pv

            # power at the slack nodes
            Sbus[vd] = V[vd] * np.conj(circuit.Ybus[t][vd, :][:, :].dot(V))

            # Reactive power at the pv nodes
            P = Sbus[pv].real
            Q = (V[pv] * np.conj(circuit.Ybus[t][pv, :][:, :].dot(V))).imag
            Sbus[pv] = P + 1j * Q  # keep the original P injection and set the calculated reactive power

            if not only_power:
                # Branches current, loading, etc
                If = circuit.Yf[t] * V
                It = circuit.Yt[t] * V
                Sf = (circuit.C_branch_bus_f[t] * V) * np.conj(If)
                St = (circuit.C_branch_bus_t[t] * V) * np.conj(It)

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
            Sbranch_all[circuit.original_branch_idx[t]] = Sbranch
            Ibranch_all[circuit.original_branch_idx[t]] = Ibranch
            loading_all[circuit.original_branch_idx[t]] = loading
            losses_all[circuit.original_branch_idx[t]] = losses
            Sbus_all[circuit.original_bus_idx[t]] = Sbus

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
                # resulting
                print('\n\n' + '-' * 40 + ' RESULTS ' + '-' * 40 + '\n')

                print('\nCf (Branch from-Bus)\n',
                      pd.DataFrame(self.calc.C_branch_bus_f.astype(int).todense(), index=self.branch_names, columns=self.bus_names))
                print('\nCt (Branch to-Bus)\n',
                      pd.DataFrame(self.calc.C_branch_bus_t.astype(int).todense(), index=self.branch_names, columns=self.bus_names))
                print('\nBus-Bus (Adjacency matrix: Graph)\n', pd.DataFrame(self.C_bus_bus.todense(), index=self.bus_names, columns=self.bus_names))

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


if __name__ == '__main__':
    from GridCal.Engine.IO.file_handler import *
    from GridCal.Engine.Simulations.ShortCircuit.short_circuit_driver import *
    from GridCal.Engine.Simulations.PowerFlow.time_series_driver import *
    from GridCal.Engine.Simulations.OPF.opf_driver import *
    from GridCal.Engine.Simulations.OPF.opf_time_series_driver import *
    from GridCal.Engine.Simulations.ContinuationPowerFlow.voltage_collapse_driver import *
    from GridCal.Engine.Simulations.Stochastic.monte_carlo_driver import *
    from GridCal.Engine.Simulations.Stochastic.lhs_driver import *
    from GridCal.Engine.Simulations.Stochastic.blackout_driver import *
    from GridCal.Engine.Simulations.Optimization.optimization_driver import *
    fname = os.path.join('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids', 'Some distribution grid.xlsx')

    print('Reading...')
    main_circuit = FileOpen(fname).open()

    compiled = main_circuit.compile().compute(compile_states=True)

    print()