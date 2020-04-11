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
from scipy.sparse import diags, hstack as hstack_s, vstack as vstack_s
from scipy.sparse.linalg import factorized
from scipy.sparse import csc_matrix
from typing import List, Dict

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.topology import Graph
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.PowerFlow.power_flow_aux import compile_types
from GridCal.Engine.Simulations.sparse_solve import get_sparse_type


def calc_connectivity(idx_pi, idx_hvdc, idx_vsc,
                      C_branch_bus_f, C_branch_bus_t, branch_active, bus_active,  # common to all branches

                      # just for the pi-branch model
                      apply_temperature, R_corrected,
                      R, X, G, B, branch_tolerance_mode: BranchImpedanceMode, impedance_tolerance,
                      tap_mod, tap_ang, tap_t, tap_f, Ysh,

                      # for the HVDC lines
                      Rdc,

                      # for the VSC lines
                      R1, X1, Gsw, Beq, m, theta):
    """
    Build all the admittance related objects
    :param branch_active: array of branch active
    :param bus_active: array of bus active
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

    sparse = get_sparse_type()

    # form the connectivity matrices with the states applied -----------------------------------------------------------
    br_states_diag = sp.diags(branch_active)
    Cf = br_states_diag * C_branch_bus_f
    Ct = br_states_diag * C_branch_bus_t

    # Declare the empty primitives -------------------------------------------------------------------------------------

    # The composition order is and will be: Pi model, HVDC, VSC

    n_pi = len(idx_pi)
    n_hvdc = len(idx_hvdc)
    n_vsc = len(idx_vsc)

    mm = n_pi + n_hvdc + n_vsc
    Ytt = np.empty(mm, dtype=complex)
    Yff = np.empty(mm, dtype=complex)
    Yft = np.empty(mm, dtype=complex)
    Ytf = np.empty(mm, dtype=complex)

    # Branch primitives in vector form, for Yseries
    Ytts = np.empty(mm, dtype=complex)
    Yffs = np.empty(mm, dtype=complex)
    Yfts = np.empty(mm, dtype=complex)
    Ytfs = np.empty(mm, dtype=complex)

    # PI BRANCH MODEL --------------------------------------------------------------------------------------------------

    # use the specified of the temperature-corrected resistance
    if apply_temperature:
        R = R_corrected

    # modify the branches impedance with the lower, upper tolerance values
    if branch_tolerance_mode == BranchImpedanceMode.Lower:
        R *= (1 - impedance_tolerance / 100.0)
    elif branch_tolerance_mode == BranchImpedanceMode.Upper:
        R *= (1 + impedance_tolerance / 100.0)

    Ys = 1.0 / (R + 1.0j * X)
    GBc = G + 1.0j * B
    Ys2 = (Ys + GBc / 2.0)
    tap = tap_mod * np.exp(1.0j * tap_ang)

    # branch primitives in vector form for Ybus
    Ytt[idx_pi] = Ys2 / (tap_t * tap_t)
    Yff[idx_pi] = Ys2 / (tap_f * tap_f * tap * np.conj(tap))
    Yft[idx_pi] = - Ys / (tap_f * tap_t * np.conj(tap))
    Ytf[idx_pi] = - Ys / (tap_t * tap_f * tap)

    # branch primitives in vector form, for Yseries
    Ytts[idx_pi] = Ys
    Yffs[idx_pi] = Ys / (tap * np.conj(tap))
    Yfts[idx_pi] = - Ys / np.conj(tap)
    Ytfs[idx_pi] = - Ys / tap

    # HVDC LINE MODEL --------------------------------------------------------------------------------------------------
    Ydc = 1 / Rdc
    Ytt[idx_hvdc] = Ydc
    Yff[idx_hvdc] = Ydc
    Yft[idx_hvdc] = - Ydc
    Ytf[idx_hvdc] = - Ydc

    Ytts[idx_hvdc] = Ydc
    Yffs[idx_hvdc] = Ydc
    Yfts[idx_hvdc] = - Ydc
    Ytfs[idx_hvdc] = - Ydc

    # VSC MODEL --------------------------------------------------------------------------------------------------------
    Y_vsc = 1.0 / (R1 + 1.0j * X1)  # Y1
    Yff[idx_vsc] = Y_vsc
    Yft[idx_vsc] = -m * np.exp(1.0j * theta) * Y_vsc
    Ytf[idx_vsc] = -m * np.exp(-1.0j * theta) * Y_vsc
    Ytt[idx_vsc] = Gsw + m * m * (Y_vsc + 1.0j * Beq)

    Yffs[idx_vsc] = Y_vsc
    Yfts[idx_vsc] = -m * np.exp(1.0j * theta) * Y_vsc
    Ytfs[idx_vsc] = -m * np.exp(-1.0j * theta) * Y_vsc
    Ytts[idx_vsc] = m * m * (Y_vsc + 1.0j)

    # form the admittance matrices -------------------------------------------------------------------------------------
    Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
    Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
    Ybus = sparse(Cf.T * Yf + Ct.T * Yt + sp.diags(Ysh))

    # form the admittance matrices of the series and shunt elements ----------------------------------------------------
    Yfs = sp.diags(Yffs) * Cf + sp.diags(Yfts) * Ct
    Yts = sp.diags(Ytfs) * Cf + sp.diags(Ytts) * Ct
    Yseries = sparse(Cf.T * Yfs + Ct.T * Yts)

    Gsh = np.zeros(mm, dtype=complex)
    Gsh[idx_pi] = GBc
    Gsh[idx_vsc] = Gsw + 1j * Beq
    Yshunt = Ysh + Cf.T * Gsh + Ct.T * Gsh

    # Form the matrices for fast decoupled -----------------------------------------------------------------------------
    reactances = np.zeros(mm, dtype=float)
    reactances[idx_pi] = X
    reactances[idx_vsc] = X1

    susceptances = np.zeros(mm, dtype=float)
    susceptances[idx_pi] = B
    susceptances[idx_vsc] = Beq

    all_taps = np.ones(mm, dtype=complex)
    all_taps[idx_pi] = tap
    all_taps[idx_vsc] = m * np.exp(1j * theta)

    b1 = 1.0 / (reactances + 1e-20)
    b1_tt = sp.diags(b1)
    B1f = b1_tt * Cf - b1_tt * Ct
    B1t = -b1_tt * Cf + b1_tt * Ct
    B1 = sparse(Cf.T * B1f + Ct.T * B1t)

    b2 = b1 + susceptances
    b2_ff = -(b2 / (all_taps * np.conj(all_taps))).real
    b2_ft = -(b1 / np.conj(all_taps)).real
    b2_tf = -(b1 / all_taps).real
    b2_tt = - b2

    B2f = -sp.diags(b2_ff) * Cf + sp.diags(b2_ft) * Ct
    B2t = sp.diags(b2_tf) * Cf + -sp.diags(b2_tt) * Ct
    B2 = sparse(Cf.T * B2f + Ct.T * B2t)

    # Bus connectivity -------------------------------------------------------------------------------------------------

    # branch - bus connectivity
    C_branch_bus = Cf + Ct

    # Connectivity node - Connectivity node connectivity matrix
    bus_states_diag = sp.diags(bus_active)
    C_bus_bus = bus_states_diag * (C_branch_bus.T * C_branch_bus)

    return Ybus, Yf, Yt, B1, B2, Yseries, Yshunt, Ys, GBc, Cf, Ct, C_bus_bus, C_branch_bus


def calc_islands(circuit: "SnapshotIsland", bus_active, C_bus_bus, C_branch_bus, C_bus_gen, C_bus_batt,
                 nbus, nbr, ignore_single_node_islands=False) -> List["SnapshotIsland"]:
    """
    Partition the circuit in islands for the designated time intervals
    :param circuit: CalculationInputs instance with all the data regardless of the islands and the branch states
    :param C_bus_bus: bus-bus connectivity matrix
    :param C_branch_bus: branch-bus connectivity matrix
    :param C_bus_gen: gen-bus connectivity matrix
    :param C_bus_batt: battery-bus connectivity matrix
    :param nbus: number of buses
    :param nbr: number of branches
    :param ignore_single_node_islands: Ignore the single node islands
    :return: list of CalculationInputs instances
    """
    # find the islands of the circuit
    g = Graph(C_bus_bus=sp.csc_matrix(C_bus_bus),
              C_branch_bus=sp.csc_matrix(C_branch_bus),
              bus_states=bus_active)

    islands = g.find_islands()

    # clear the list of circuits
    calculation_islands = list()

    # find the branches that belong to each island
    island_branches = list()

    if len(islands) > 1:

        # there are islands, pack the islands into sub circuits
        for island_bus_idx in islands:

            if ignore_single_node_islands and len(island_bus_idx) <= 1:
                keep = False
            else:
                keep = True

            if keep:
                # get the branch indices of the island
                island_br_idx = g.get_branches_of_the_island(island_bus_idx)
                island_br_idx = np.sort(island_br_idx)  # sort
                island_branches.append(island_br_idx)

                # indices of batteries and controlled generators that belong to this island
                gen_idx = np.where(C_bus_gen[island_bus_idx, :].sum(axis=0) > 0)[0]
                bat_idx = np.where(C_bus_batt[island_bus_idx, :].sum(axis=0) > 0)[0]

                # Get the island circuit (the bus types are computed automatically)
                # The island original indices are generated within the get_island function
                circuit_island = circuit.get_island(island_bus_idx, island_br_idx, gen_idx, bat_idx)

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

        # append a list with all the branch indices for completeness
        island_branches.append(island_br_idx)

    # return the list of islands
    return calculation_islands


class SnapshotIsland:
    """
    This class represents a SnapshotData for a single island
    """

    def __init__(self, nbus, nbr, nhvdc, nvsc, nbat, nctrlgen, Sbase=100):
        """

        :param nbus:
        :param nbr:
        :param nbat:
        :param nctrlgen:
        :param Sbase:
        """
        self.nbus = nbus
        self.nbr = nbr
        self.nhvdc = nhvdc
        self.nvsc = nvsc

        self.Sbase = Sbase

        self.original_bus_idx = list()
        self.original_branch_idx = list()
        self.original_time_idx = list()

        self.bus_names = np.empty(self.nbus, dtype=object)

        # common to all branches
        mm = nbr + nhvdc + nvsc
        self.branch_names = np.empty(mm, dtype=object)
        self.F = np.zeros(mm, dtype=int)
        self.T = np.zeros(mm, dtype=int)
        self.C_branch_bus_f = csc_matrix((mm, nbus), dtype=int)
        self.C_branch_bus_t = csc_matrix((mm, nbus), dtype=int)

        # resulting matrices (calculation)
        self.Yf = csc_matrix((nbr, nbus), dtype=complex)
        self.Yt = csc_matrix((nbr, nbus), dtype=complex)
        self.Ybus = csc_matrix((nbus, nbus), dtype=complex)
        self.Yseries = csc_matrix((nbus, nbus), dtype=complex)
        self.B1 = csc_matrix((nbus, nbus), dtype=float)
        self.B2 = csc_matrix((nbus, nbus), dtype=float)
        self.Bpqpv = None
        self.Bref = None

        self.Ysh_helm = np.zeros(nbus, dtype=complex)
        self.Ysh = np.zeros(nbus, dtype=complex)
        self.Sbus = np.zeros(nbus, dtype=complex)
        self.Ibus = np.zeros(nbus, dtype=complex)

        self.Vbus = np.ones(nbus, dtype=complex)
        self.Vmin = np.ones(nbus, dtype=float)
        self.Vmax = np.ones(nbus, dtype=float)
        self.types = np.zeros(nbus, dtype=int)
        self.Qmin = np.zeros(nbus, dtype=float)
        self.Qmax = np.zeros(nbus, dtype=float)
        self.Sinstalled = np.zeros(nbus, dtype=float)

        # vectors to re-calculate the admittance matrices
        self.Ys = np.zeros(nbr, dtype=complex)
        self.GBc = np.zeros(nbr, dtype=complex)
        self.tap_f = np.zeros(nbr, dtype=float)
        self.tap_t = np.zeros(nbr, dtype=float)
        self.tap_ang = np.zeros(nbr, dtype=float)
        self.tap_mod = np.ones(nbr, dtype=float)

        # needed fot the tap changer
        self.is_bus_to_regulated = np.zeros(nbr, dtype=int)
        self.bus_to_regulated_idx = None
        self.tap_position = np.zeros(nbr, dtype=int)
        self.min_tap = np.zeros(nbr, dtype=int)
        self.max_tap = np.zeros(nbr, dtype=int)
        self.tap_inc_reg_up = np.zeros(nbr, dtype=float)
        self.tap_inc_reg_down = np.zeros(nbr, dtype=float)
        self.vset = np.zeros(nbr, dtype=float)

        # vsc
        self.vsc_m = np.ones(nvsc, dtype=float)

        # Active power control
        self.controlled_gen_pmin = np.zeros(nctrlgen, dtype=float)
        self.controlled_gen_pmax = np.zeros(nctrlgen, dtype=float)
        self.controlled_gen_enabled = np.zeros(nctrlgen, dtype=bool)
        self.controlled_gen_dispatchable = np.zeros(nctrlgen, dtype=bool)

        self.battery_pmin = np.zeros(nbat, dtype=float)
        self.battery_pmax = np.zeros(nbat, dtype=float)
        self.battery_Enom = np.zeros(nbat, dtype=float)
        self.battery_soc_0 = np.zeros(nbat, dtype=float)
        self.battery_discharge_efficiency = np.zeros(nbat, dtype=float)
        self.battery_charge_efficiency = np.zeros(nbat, dtype=float)
        self.battery_min_soc = np.zeros(nbat, dtype=float)
        self.battery_max_soc = np.zeros(nbat, dtype=float)
        self.battery_enabled = np.zeros(nbat, dtype=bool)
        self.battery_dispatchable = np.zeros(nbat, dtype=bool)

        # computed on consolidation
        self.dispatcheable_batteries_bus_idx = list()

        # connectivity matrices used to formulate OPF problems
        self.C_bus_load = None
        self.C_bus_batt = None
        self.C_bus_sta_gen = None
        self.C_bus_gen = None
        self.C_bus_shunt = None

        # ACPF system matrix factorization
        self.Asys = None

        self.branch_rates = np.zeros(nbr)

        self.pq = list()
        self.pv = list()
        self.ref = list()
        self.sto = list()
        self.pqpv = list()  # it is sorted

        self.logger = Logger()

        self.available_structures = ['Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries',
                                     "B'", "B''", 'Types', 'Jacobian', 'Qmin', 'Qmax']

    def consolidate(self):
        """
        Compute the magnitudes that cannot be computed vector-wise
        """
        self.bus_to_regulated_idx = np.where(self.is_bus_to_regulated == True)[0]

        dispatcheable_batteries_idx = np.where(self.battery_dispatchable == True)[0]

        self.dispatcheable_batteries_bus_idx = np.where(np.array(self.C_bus_batt[:, dispatcheable_batteries_idx].sum(axis=0))[0] > 0)[0]

        #
        self.ref, self.pq, self.pv, self.pqpv = compile_types(self.Sbus, self.types)

        #
        self.Bpqpv = self.Ybus.imag[np.ix_(self.pqpv, self.pqpv)]
        self.Bref = self.Ybus.imag[np.ix_(self.pqpv, self.ref)]

    def get_island(self, bus_idx, branch_idx, gen_idx, bat_idx) -> "SnapshotIsland":
        """
        Get a sub-island
        :param bus_idx: bus indices of the island
        :param branch_idx: branch indices of the island
        :return: CalculationInputs instance
        """
        obj = SnapshotIsland(len(bus_idx), len(branch_idx), 0, 0, len(bat_idx), len(gen_idx))

        # remember the island original indices
        obj.original_bus_idx = bus_idx
        obj.original_branch_idx = branch_idx

        obj.Yf = self.Yf[np.ix_(branch_idx, bus_idx)]
        obj.Yt = self.Yt[np.ix_(branch_idx, bus_idx)]
        obj.Ybus = self.Ybus[np.ix_(bus_idx, bus_idx)]
        obj.Yseries = self.Yseries[np.ix_(bus_idx, bus_idx)]
        obj.B1 = self.B1[np.ix_(bus_idx, bus_idx)]
        obj.B2 = self.B2[np.ix_(bus_idx, bus_idx)]

        obj.Ysh = self.Ysh[bus_idx]
        obj.Sbus = self.Sbus[bus_idx]
        obj.Ibus = self.Ibus[bus_idx]
        obj.Vbus = self.Vbus[bus_idx]
        obj.types = self.types[bus_idx]
        obj.Qmin = self.Qmin[bus_idx]
        obj.Qmax = self.Qmax[bus_idx]
        obj.Vmin = self.Vmin[bus_idx]
        obj.Vmax = self.Vmax[bus_idx]
        obj.Sinstalled = self.Sinstalled[bus_idx]

        obj.F = self.F[branch_idx]
        obj.T = self.T[branch_idx]
        obj.branch_rates = self.branch_rates[branch_idx]
        obj.bus_names = self.bus_names[bus_idx]
        obj.branch_names = self.branch_names[branch_idx]

        obj.C_branch_bus_f = self.C_branch_bus_f[np.ix_(branch_idx, bus_idx)]
        obj.C_branch_bus_t = self.C_branch_bus_t[np.ix_(branch_idx, bus_idx)]

        obj.C_bus_load = self.C_bus_load[bus_idx, :]
        obj.C_bus_batt = self.C_bus_batt[bus_idx, :]
        obj.C_bus_sta_gen = self.C_bus_sta_gen[bus_idx, :]
        obj.C_bus_gen = self.C_bus_gen[bus_idx, :]
        obj.C_bus_shunt = self.C_bus_shunt[bus_idx, :]

        obj.is_bus_to_regulated = self.is_bus_to_regulated[branch_idx]
        obj.tap_position = self.tap_position[branch_idx]
        obj.min_tap = self.min_tap[branch_idx]
        obj.max_tap = self.max_tap[branch_idx]
        obj.tap_inc_reg_up = self.tap_inc_reg_up[branch_idx]
        obj.tap_inc_reg_down = self.tap_inc_reg_down[branch_idx]
        obj.vset = self.vset[branch_idx]
        obj.tap_ang = self.tap_ang[branch_idx]
        obj.tap_mod = self.tap_mod[branch_idx]

        obj.Ys = self.Ys
        obj.GBc = self.GBc
        obj.tap_f = self.tap_f
        obj.tap_t = self.tap_t

        obj.controlled_gen_pmin = self.controlled_gen_pmin[gen_idx]
        obj.controlled_gen_pmax = self.controlled_gen_pmax[gen_idx]
        obj.controlled_gen_enabled = self.controlled_gen_enabled[gen_idx]
        obj.controlled_gen_dispatchable = self.controlled_gen_dispatchable[gen_idx]
        obj.battery_pmin = self.battery_pmin[bat_idx]
        obj.battery_pmax = self.battery_pmax[bat_idx]
        obj.battery_Enom = self.battery_Enom[bat_idx]
        obj.battery_soc_0 = self.battery_soc_0[bat_idx]
        obj.battery_discharge_efficiency = self.battery_discharge_efficiency[bat_idx]
        obj.battery_charge_efficiency = self.battery_charge_efficiency[bat_idx]
        obj.battery_min_soc = self.battery_min_soc[bat_idx]
        obj.battery_max_soc = self.battery_max_soc[bat_idx]
        obj.battery_enabled = self.battery_enabled[bat_idx]
        obj.battery_dispatchable = self.battery_dispatchable[bat_idx]

        obj.consolidate()

        return obj

    # def compute_branch_results(self, V) -> "PowerFlowResults":
    #     """
    #     Compute the branch magnitudes from the voltages
    #     :param V: Voltage vector solution in p.u.
    #     :return: PowerFlowResults instance
    #     """
    #
    #     # declare circuit results
    #     data = PowerFlowResults(self.nbus, self.nbr)
    #
    #     # copy the voltage
    #     data.V = V
    #
    #     # power at the slack nodes
    #     data.Sbus = self.Sbus.copy()
    #     data.Sbus[self.ref] = V[self.ref] * np.conj(self.Ybus[self.ref, :].dot(V))
    #
    #     # Reactive power at the pv nodes: keep the original P injection and set the calculated reactive power
    #     Q = (V[self.pv] * np.conj(self.Ybus[self.pv, :].dot(V))).imag
    #
    #     data.Sbus[self.pv] = self.Sbus[self.pv].real + 1j * Q
    #
    #     # Branches current, loading, etc
    #     data.If = self.Yf * V
    #     data.It = self.Yt * V
    #     data.Sf = self.C_branch_bus_f * V * np.conj(data.If)
    #     data.St = self.C_branch_bus_t * V * np.conj(data.It)
    #
    #     # Branch losses in MVA
    #     data.losses = (data.Sf + data.St)
    #
    #     # Branch current in p.u.
    #     data.Ibranch = np.maximum(data.If, data.It)
    #
    #     # Branch power in MVA
    #     data.Sbranch = np.maximum(data.Sf, data.St)
    #
    #     # Branch loading in p.u.
    #     data.loading = data.Sbranch / (self.branch_rates + 1e-9)
    #
    #     return data

    def re_calc_admittance_matrices(self, tap_mod):
        """
        Recalculate the admittance matrices as the tap changes
        :param tap_mod: tap modules per bus
        :return: Nothing, the matrices are changed in-place
        """
        # here the branch_bus matrices do have the states embedded
        Cf = self.C_branch_bus_f
        Ct = self.C_branch_bus_t

        tap = np.r_[tap_mod * np.exp(1.0j * self.tap_ang), ]

        # branch primitives in vector form
        Ytt = (self.Ys + self.GBc / 2.0) / (self.tap_t * self.tap_t)
        Yff = (self.Ys + self.GBc / 2.0) / (self.tap_f * self.tap_f * tap * np.conj(tap))
        Yft = - self.Ys / (self.tap_f * self.tap_t * np.conj(tap))
        Ytf = - self.Ys / (self.tap_t * self.tap_f * tap)

        # form the admittance matrices
        self.Yf = diags(Yff) * Cf + diags(Yft) * Ct
        self.Yt = diags(Ytf) * Cf + diags(Ytt) * Ct
        self.Ybus = csc_matrix(Cf.T * self.Yf + Ct.T * self.Yt + diags(self.Ysh))

        # branch primitives in vector form
        Ytts = self.Ys
        Yffs = Ytts / (tap * np.conj(tap))
        Yfts = - self.Ys / np.conj(tap)
        Ytfs = - self.Ys / tap

        # form the admittance matrices of the series elements
        Yfs = diags(Yffs) * Cf + diags(Yfts) * Ct
        Yts = diags(Ytfs) * Cf + diags(Ytts) * Ct
        self.Yseries = csc_matrix(Cf.T * Yfs + Ct.T * Yts)
        Gsh = self.GBc / 2.0
        self.Ysh += Cf.T * Gsh + Ct.T * Gsh

        X = (1 / self.Ys).imag
        b1 = 1.0 / (X + 1e-20)
        B1f = diags(-b1) * Cf + diags(-b1) * Ct
        B1t = diags(-b1) * Cf + diags(-b1) * Ct
        self.B1 = csc_matrix(Cf.T * B1f + Ct.T * B1t)

        b2 = b1 + self.GBc.imag  # B == GBc.imag
        b2_ff = -(b2 / (tap * np.conj(tap))).real
        b2_ft = -(b1 / np.conj(tap)).real
        b2_tf = -(b1 / tap).real
        b2_tt = - b2
        B2f = diags(b2_ff) * Cf + diags(b2_ft) * Ct
        B2t = diags(b2_tf) * Cf + diags(b2_tt) * Ct
        self.B2 = csc_matrix(Cf.T * B2f + Ct.T * B2t)

    def build_linear_ac_sys_mat(self):
        """
        Get the AC linear approximation matrices
        :return:
        """
        A11 = -self.Yseries.imag[np.ix_(self.pqpv, self.pqpv)]
        A12 = self.Ybus.real[np.ix_(self.pqpv, self.pq)]
        A21 = -self.Yseries.real[np.ix_(self.pq, self.pqpv)]
        A22 = -self.Ybus.imag[np.ix_(self.pq, self.pq)]

        A = vstack_s([hstack_s([A11, A12]),
                      hstack_s([A21, A22])], format="csc")

        # form the slack system matrix
        A11s = -self.Yseries.imag[np.ix_(self.ref, self.pqpv)]
        A12s = self.Ybus.real[np.ix_(self.ref, self.pq)]
        A_slack = hstack_s([A11s, A12s], format="csr")

        self.Asys = factorized(A)
        return A, A_slack

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

        elif structure_type == 'Yshunt':
            df = pd.DataFrame(data=self.Ysh, columns=['Shunt admittance (p.u.)'], index=self.bus_names)

        elif structure_type == 'Yseries':
            df = pd.DataFrame(data=self.Yseries.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == "B'":
            df = pd.DataFrame(data=self.B1.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == "B''":
            df = pd.DataFrame(data=self.B2.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Types':
            df = pd.DataFrame(data=self.types, columns=['Bus types'], index=self.bus_names)

        elif structure_type == 'Qmin':
            df = pd.DataFrame(data=self.Qmin, columns=['Qmin'], index=self.bus_names)

        elif structure_type == 'Qmax':
            df = pd.DataFrame(data=self.Qmax, columns=['Qmax'], index=self.bus_names)

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

    def print(self, bus_names):
        """
        print in console
        :return:
        """
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


class SnapshotData:
    """
    This class represents the set of numerical inputs for simulations that require
    static values from the snapshot mode (power flow, short circuit, voltage collapse, PTDF, etc.)
    """

    def __init__(self, n_bus, n_pi, n_hvdc, n_vsc, n_ld, n_gen, n_sta_gen, n_batt, n_sh,
                 idx_pi, idx_hvdc, idx_vsc, Sbase):
        """
        Topology constructor
        :param n_bus: number of nodes
        :param n_pi: number of branches
        :param n_ld: number of loads
        :param n_gen: number of generators
        :param n_sta_gen: number of generators
        :param n_batt: number of generators
        :param n_sh: number of shunts
        :param n_hvdc: number of dc lines
        :param n_vsc: number of VSC converters
        :param idx_pi: pi model branch indices
        :param idx_hvdc: hvdc model branch indices
        :param idx_vsc: vsc model branch indices
        :param Sbase: circuit base power
        """

        # number of buses
        self.nbus = n_bus

        # number of branches
        self.nbr = n_pi

        self.n_hvdc = n_hvdc

        self.n_vsc = n_vsc

        self.n_batt = n_batt

        self.n_gen = n_gen

        self.n_ld = n_ld

        self.idx_pi = idx_pi

        self.idx_hvdc = idx_hvdc

        self.idx_vsc = idx_vsc

        # base power
        self.Sbase = Sbase

        self.time_array = None

        # bus ----------------------------------------------------------------------------------------------------------
        self.bus_names = np.empty(n_bus, dtype=object)
        self.bus_vnom = np.zeros(n_bus, dtype=float)
        self.bus_active = np.ones(n_bus, dtype=int)
        self.V0 = np.ones(n_bus, dtype=complex)
        self.Vmin = np.ones(n_bus, dtype=float)
        self.Vmax = np.ones(n_bus, dtype=float)
        self.bus_types = np.empty(n_bus, dtype=int)

        # branch common ------------------------------------------------------------------------------------------------
        mm = n_pi + n_hvdc + n_vsc
        self.branch_names = np.empty(mm, dtype=object)
        self.branch_active = np.zeros(mm, dtype=int)
        self.F = np.zeros(mm, dtype=int)
        self.T = np.zeros(mm, dtype=int)
        self.branch_rates = np.zeros(mm, dtype=float)
        self.C_branch_bus_f = sp.lil_matrix((mm, n_bus), dtype=int)
        self.C_branch_bus_t = sp.lil_matrix((mm, n_bus), dtype=int)

        # pi model -----------------------------------------------------------------------------------------------------
        self.branch_R = np.zeros(n_pi, dtype=float)
        self.branch_X = np.zeros(n_pi, dtype=float)
        self.branch_G = np.zeros(n_pi, dtype=float)
        self.branch_B = np.zeros(n_pi, dtype=float)
        self.branch_impedance_tolerance = np.zeros(n_pi, dtype=float)
        self.branch_tap_f = np.ones(n_pi, dtype=float)  # tap generated by the difference in nominal voltage at the form side
        self.branch_tap_t = np.ones(n_pi, dtype=float)  # tap generated by the difference in nominal voltage at the to side
        self.branch_tap_mod = np.zeros(n_pi, dtype=float)  # normal tap module
        self.branch_tap_ang = np.zeros(n_pi, dtype=float)  # normal tap angle

        self.branch_cost = np.zeros(n_pi, dtype=float)

        self.branch_mttf = np.zeros(n_pi, dtype=float)
        self.branch_mttr = np.zeros(n_pi, dtype=float)

        self.branch_temp_base = np.zeros(n_pi, dtype=float)
        self.branch_temp_oper = np.zeros(n_pi, dtype=float)
        self.branch_alpha = np.zeros(n_pi, dtype=float)

        self.branch_is_bus_to_regulated = np.zeros(n_pi, dtype=bool)
        self.branch_tap_position = np.zeros(n_pi, dtype=int)
        self.branch_min_tap = np.zeros(n_pi, dtype=int)
        self.branch_max_tap = np.zeros(n_pi, dtype=int)
        self.branch_tap_inc_reg_up = np.zeros(n_pi, dtype=float)
        self.branch_tap_inc_reg_down = np.zeros(n_pi, dtype=float)
        self.branch_vset = np.zeros(n_pi, dtype=float)
        self.branch_switch_indices = list()

        # hvdc line ----------------------------------------------------------------------------------------------------
        self.hvdc_R = np.zeros(n_hvdc, dtype=float)
        self.hvdc_Pset = np.zeros(n_hvdc, dtype=float)

        # vsc converter ------------------------------------------------------------------------------------------------
        self.vsc_R1 = np.zeros(n_vsc, dtype=float)
        self.vsc_X1 = np.zeros(n_vsc, dtype=float)
        self.vsc_G0 = np.zeros(n_vsc, dtype=float)
        self.vsc_Beq = np.zeros(n_vsc, dtype=float)
        self.vsc_m = np.zeros(n_vsc, dtype=float)
        self.vsc_theta = np.zeros(n_vsc, dtype=float)

        # load ---------------------------------------------------------------------------------------------------------
        self.load_names = np.empty(n_ld, dtype=object)
        self.load_power = np.zeros(n_ld, dtype=complex)
        self.load_current = np.zeros(n_ld, dtype=complex)
        self.load_admittance = np.zeros(n_ld, dtype=complex)
        self.load_active = np.zeros(n_ld, dtype=bool)

        self.load_cost = np.zeros(n_ld, dtype=float)

        self.load_mttf = np.zeros(n_ld, dtype=float)
        self.load_mttr = np.zeros(n_ld, dtype=float)

        self.C_bus_load = sp.lil_matrix((n_bus, n_ld), dtype=int)

        # battery ------------------------------------------------------------------------------------------------------
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
        self.battery_cost = np.zeros(n_batt, dtype=float)

        self.battery_dispatchable = np.zeros(n_batt, dtype=bool)
        self.battery_active = np.zeros(n_batt, dtype=bool)
        self.battery_mttf = np.zeros(n_batt, dtype=float)
        self.battery_mttr = np.zeros(n_batt, dtype=float)

        self.C_bus_batt = sp.lil_matrix((n_bus, n_batt), dtype=int)

        # static generator ---------------------------------------------------------------------------------------------
        self.static_gen_names = np.empty(n_sta_gen, dtype=object)
        self.static_gen_power = np.zeros(n_sta_gen, dtype=complex)
        self.static_gen_dispatchable = np.zeros(n_sta_gen, dtype=bool)

        self.static_gen_active = np.zeros(n_sta_gen, dtype=bool)

        self.static_gen_mttf = np.zeros(n_sta_gen, dtype=float)
        self.static_gen_mttr = np.zeros(n_sta_gen, dtype=float)

        self.C_bus_sta_gen = sp.lil_matrix((n_bus, n_sta_gen), dtype=int)

        # controlled generator -----------------------------------------------------------------------------------------
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
        self.generator_cost = np.zeros(n_gen, dtype=float)
        self.generator_nominal_power = np.zeros(n_gen, dtype=float)

        self.generator_active = np.zeros(n_gen, dtype=bool)

        self.generator_mttf = np.zeros(n_gen, dtype=float)
        self.generator_mttr = np.zeros(n_gen, dtype=float)

        self.C_bus_gen = sp.lil_matrix((n_bus, n_gen), dtype=int)

        # shunt --------------------------------------------------------------------------------------------------------
        self.shunt_names = np.empty(n_sh, dtype=object)
        self.shunt_admittance = np.zeros(n_sh, dtype=complex)

        self.shunt_active = np.zeros(n_sh, dtype=bool)

        self.shunt_mttf = np.zeros(n_sh, dtype=float)
        self.shunt_mttr = np.zeros(n_sh, dtype=float)

        self.C_bus_shunt = sp.lil_matrix((n_bus, n_sh), dtype=int)

    def get_power_injections(self):
        """
        returns the complex power injections in MW+jMVAr
        """
        Sbus = - self.C_bus_load * self.load_power.T  # MW
        Sbus += self.C_bus_gen * self.generator_power.T
        Sbus += self.C_bus_batt * self.battery_power.T
        Sbus += self.C_bus_sta_gen * self.static_gen_power.T
        # HVDC forced power
        Sbus += self.hvdc_Pset * self.C_branch_bus_f[self.idx_hvdc, :]
        Sbus -= self.hvdc_Pset * self.C_branch_bus_t[self.idx_hvdc, :]

        return Sbus

    def get_branch_number(self):
        """
        Get the number of branches
        :return:
        """
        return self.nbr + self.n_hvdc + self.n_vsc

    def get_raw_circuit(self, add_generation, add_storage) -> SnapshotIsland:
        """

        :param add_generation:
        :param add_storage:
        :return:
        """
        # Declare object to store the calculation inputs
        circuit = SnapshotIsland(nbus=self.nbus,
                                 nbr=self.nbr,
                                 nhvdc=self.n_hvdc,
                                 nvsc=self.n_vsc,
                                 nbat=self.n_batt,
                                 nctrlgen=self.n_gen)

        # branches
        circuit.branch_rates = self.branch_rates
        circuit.F = self.F
        circuit.T = self.T
        circuit.tap_f = self.branch_tap_f
        circuit.tap_t = self.branch_tap_t
        circuit.bus_names = self.bus_names
        circuit.branch_names = self.branch_names

        # connectivity matrices
        circuit.C_bus_load = self.C_bus_load
        circuit.C_bus_batt = self.C_bus_batt
        circuit.C_bus_sta_gen = self.C_bus_sta_gen
        circuit.C_bus_gen = self.C_bus_gen
        circuit.C_bus_shunt = self.C_bus_shunt

        # needed for the tap changer
        circuit.is_bus_to_regulated = self.branch_is_bus_to_regulated
        circuit.tap_position = self.branch_tap_position
        circuit.min_tap = self.branch_min_tap
        circuit.max_tap = self.branch_max_tap
        circuit.tap_inc_reg_up = self.branch_tap_inc_reg_up
        circuit.tap_inc_reg_down = self.branch_tap_inc_reg_down
        circuit.vset = self.branch_vset
        circuit.tap_ang = self.branch_tap_ang
        circuit.tap_mod = self.branch_tap_mod

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
        Ysh = self.C_bus_shunt * (self.shunt_admittance / self.Sbase)

        # Loads
        S = self.C_bus_load * (- self.load_power / self.Sbase * self.load_active)
        I = self.C_bus_load * (- self.load_current / self.Sbase * self.load_active)
        Ysh += self.C_bus_load * (self.load_admittance / self.Sbase * self.load_active)

        if add_generation:
            # static generators
            S += self.C_bus_sta_gen * (self.static_gen_power / self.Sbase * self.static_gen_active)

            # generators
            pf2 = np.power(self.generator_power_factor, 2.0)
            # compute the reactive power from the active power and the power factor
            pf_sign = (self.generator_power_factor + 1e-20) / np.abs(self.generator_power_factor + 1e-20)
            Q = pf_sign * self.generator_power * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
            gen_S = self.generator_power + 1j * Q
            S += self.C_bus_gen * (gen_S / self.Sbase * self.generator_active)

        installed_generation_per_bus = self.C_bus_gen * (self.generator_nominal_power * self.generator_active)

        # batteries
        if add_storage:
            S += self.C_bus_batt * (self.battery_power / self.Sbase * self.battery_active)

        # HVDC forced power
        S += (self.hvdc_Pset / self.Sbase) * self.C_branch_bus_f[self.idx_hvdc, :]
        S -= (self.hvdc_Pset / self.Sbase) * self.C_branch_bus_t[self.idx_hvdc, :]

        # Qmax
        q_max = self.C_bus_gen * (self.generator_qmax / self.Sbase) + self.C_bus_batt * (self.battery_qmax / self.Sbase)

        # Qmin
        q_min = self.C_bus_gen * (self.generator_qmin / self.Sbase) + self.C_bus_batt * (self.battery_qmin / self.Sbase)

        # assign the values
        circuit.Ysh = Ysh
        circuit.Sbus = S
        circuit.Ibus = I
        circuit.Vbus = self.V0
        circuit.Sbase = self.Sbase
        circuit.types = self.bus_types
        circuit.Qmax = q_max
        circuit.Qmin = q_min
        circuit.Sinstalled = installed_generation_per_bus

        return circuit

    def compute(self, add_storage=True, add_generation=True, apply_temperature=False,
                branch_tolerance_mode=BranchImpedanceMode.Specified,
                ignore_single_node_islands=False) -> List[SnapshotIsland]:
        """
        Compute the cross connectivity matrices to determine the circuit connectivity
        towards the calculation. Additionally, compute the calculation matrices.
        :param add_storage:
        :param add_generation:
        :param apply_temperature:
        :param branch_tolerance_mode:
        :param ignore_single_node_islands: If True, the single node islands are omitted
        :return: list of CalculationInputs instances where each one is a circuit island
        """

        # get the raw circuit with the inner arrays computed
        circuit = self.get_raw_circuit(add_generation=add_generation, add_storage=add_storage)

        """
          n_br, n_hvdc, n_vsc, 
          C_branch_bus_f, C_branch_bus_t,  branch_active,  bus_active,  # common to all branches
          
          # just for the pi-branch model
          apply_temperature, R_corrected,
          R, X, G, B, branch_tolerance_mode: BranchImpedanceMode, impedance_tolerance,
          tap_mod, tap_ang, tap_t, tap_f, Ysh,
          
          # for the HVDC lines
          Rdc,
          
          # for the VSC lines
          R1, X1, Gsw, Beq, m, theta
        """

        # compute the connectivity and the different admittance matrices
        circuit.Ybus, \
        circuit.Yf, \
        circuit.Yt, \
        circuit.B1, \
        circuit.B2, \
        circuit.Yseries, \
        circuit.Ysh_helm, \
        circuit.Ys, \
        circuit.GBc, \
        circuit.C_branch_bus_f, \
        circuit.C_branch_bus_t, \
        C_bus_bus, \
        C_branch_bus = calc_connectivity(idx_pi=self.idx_pi,
                                         idx_hvdc=self.idx_hvdc,
                                         idx_vsc=self.idx_vsc,
                                         C_branch_bus_f=self.C_branch_bus_f,
                                         C_branch_bus_t=self.C_branch_bus_t,
                                         branch_active=self.branch_active,
                                         bus_active=self.bus_active,

                                         # pi model
                                         apply_temperature=apply_temperature,
                                         R_corrected=self.R_corrected(),
                                         R=self.branch_R,
                                         X=self.branch_X,
                                         G=self.branch_G,
                                         B=self.branch_B,
                                         branch_tolerance_mode=branch_tolerance_mode,
                                         impedance_tolerance=self.branch_impedance_tolerance,
                                         tap_mod=self.branch_tap_mod,
                                         tap_ang=self.branch_tap_ang,
                                         tap_t=self.branch_tap_t,
                                         tap_f=self.branch_tap_f,
                                         Ysh=circuit.Ysh,

                                         # HVDC line
                                         Rdc=self.hvdc_R,

                                         # VSC model
                                         R1=self.vsc_R1,
                                         X1=self.vsc_X1,
                                         Gsw=self.vsc_G0,
                                         Beq=self.vsc_Beq,
                                         m=self.vsc_m,
                                         theta=self.vsc_theta
                                         )

        #  split the circuit object into the individual circuits that may arise from the topological islands
        calculation_islands = calc_islands(circuit=circuit,
                                           bus_active=self.bus_active,
                                           C_bus_bus=C_bus_bus,
                                           C_branch_bus=C_branch_bus,
                                           C_bus_gen=self.C_bus_gen,
                                           C_bus_batt=self.C_bus_batt,
                                           nbus=self.nbus,
                                           nbr=self.get_branch_number(),
                                           ignore_single_node_islands=ignore_single_node_islands)

        for island in calculation_islands:
            self.bus_types[island.original_bus_idx] = island.types

        # return the list of islands
        return calculation_islands

    def R_corrected(self):
        """
        Returns temperature corrected resistances (numpy array) based on a formula
        provided by: NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.branch_R * (1.0 + self.branch_alpha * (self.branch_temp_oper - self.branch_temp_base))

    def get_B(self, apply_temperature=False):
        """

        :param apply_temperature:
        :return:
        """

        # Shunts
        Ysh = self.C_bus_shunt.T * (self.shunt_admittance / self.Sbase)

        # Loads
        Ysh += self.C_bus_load.T * (self.load_admittance / self.Sbase * self.load_active)

        # form the connectivity matrices with the states applied
        states_dia = sp.diags(self.branch_active)
        Cf = states_dia * self.C_branch_bus_f
        Ct = states_dia * self.C_branch_bus_t

        if apply_temperature:
            R = self.R_corrected()
        else:
            R = self.branch_R

        Ys = 1.0 / (R + 1.0j * self.branch_X)
        GBc = self.branch_G + 1.0j * self.branch_B
        tap = self.branch_tap_mod * np.exp(1.0j * self.branch_tap_ang)

        # branch primitives in vector form
        Ytt = (Ys + GBc / 2.0) / (self.branch_tap_t * self.branch_tap_t)
        Yff = (Ys + GBc / 2.0) / (self.branch_tap_f * self.branch_tap_f * tap * np.conj(tap))
        Yft = - Ys / (self.branch_tap_f * self.branch_tap_t * np.conj(tap))
        Ytf = - Ys / (self.branch_tap_t * self.branch_tap_f * tap)

        # form the admittance matrices
        Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
        Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
        Ybus = sp.csc_matrix(Cf.T * Yf + Ct.T * Yt + sp.diags(Ysh))

        return Ybus.imag

