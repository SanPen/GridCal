# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import scipy as sp

from typing import List
from GridCalEngine.basic_structures import IntVec, CxVec
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Topology.admittance_matrices import compute_admittances
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.helm_power_flow import (helm_coefficients_dY,
                                                                                  helm_preparation_dY,
                                                                                  HelmPreparation)


def calc_V_outage(nc: NumericalCircuit,
                  If: CxVec,
                  Ybus: sp.sparse.csc_matrix,
                  sys_mat_factorization,
                  V0: CxVec,
                  S0: CxVec,
                  Uini,
                  Xini,
                  Yslack,
                  Vslack,
                  vec_P,
                  vec_Q,
                  Ysh,
                  vec_W,
                  pq: IntVec,
                  pv: IntVec,
                  vd: IntVec,
                  pqpv: IntVec,
                  contingency_br_indices: IntVec):
    """
    Calculate the voltage due to outages in a non-linear manner with HELM.
    The main novelty is the introduction of s.AY, thus delaying it
    Use directly V from HELM, do not go for Pade, may need more time for not much benefit
    :param nc: NumericalCircuit instance
    :param If: from currents of the initial power flow
    :param Ybus: original admittance matrix
    :param sys_mat_factorization:
    :param V0: initial voltage array
    :param S0: vector of powers
    :param Uini:
    :param Xini:
    :param Yslack:
    :param Vslack:
    :param vec_P:
    :param vec_Q:
    :param Ysh: array of shunt admittances
    :param vec_W:
    :param pq: set of PQ buses
    :param pv: set of PV buses
    :param vd: set of slack buses
    :param pqpv: set of PQ + PV buses
    :param contingency_br_indices: array of branch indices of the contingency
    :return: V, Sf, loading, norm_f
    """

    # sys_mat_factorization, Uini, Xini, Yslack, Vslack, \
    #     vec_P, vec_Q, Ysh, vec_W, pq_, pv_, pqpv_, \
    #     npqpv, n = helm_preparation_dY(Yseries=Yseries, V0=V0, S0=S0,
    #                                    Ysh0=Ysh0, pq=pq, pv=pv, sl=vd, pqpv=pqpv)

    # compute the admittance of the contingency branches
    adm = compute_admittances(R=nc.passive_branch_data.R[contingency_br_indices],
                              X=nc.passive_branch_data.X[contingency_br_indices],
                              G=nc.passive_branch_data.G[contingency_br_indices],
                              B=nc.passive_branch_data.B[contingency_br_indices],
                              tap_module=nc.active_branch_data.tap_module[contingency_br_indices],
                              vtap_f=nc.passive_branch_data.virtual_tap_f[contingency_br_indices],
                              vtap_t=nc.passive_branch_data.virtual_tap_t[contingency_br_indices],
                              tap_angle=nc.active_branch_data.tap_angle[contingency_br_indices],
                              Cf=nc.passive_branch_data.Cf[contingency_br_indices, :],
                              Ct=nc.passive_branch_data.Ct[contingency_br_indices, :],
                              Yshunt_bus=np.zeros(nc.nbus, dtype=complex),
                              conn=nc.passive_branch_data.conn[contingency_br_indices],
                              seq=1,
                              add_windings_phase=False)

    # solve the modified HELM
    _, V, _, norm_f = helm_coefficients_dY(dY=adm.Ybus,
                                           sys_mat_factorization=sys_mat_factorization,
                                           Uini=Uini,
                                           Xini=Xini,
                                           Yslack=Yslack,
                                           Ysh=Ysh,
                                           Ybus=Ybus,
                                           vec_P=vec_P,
                                           vec_Q=vec_Q,
                                           S0=S0,
                                           vec_W=vec_W,
                                           V0=V0,
                                           Vslack=Vslack,
                                           pq=pq,
                                           pv=pv,
                                           pqpv=pqpv,
                                           npqpv=len(pqpv),
                                           nbus=nc.nbus,
                                           sl=vd,
                                           tolerance=1e-6,
                                           max_coeff=10)

    # compute flows
    Sf = (nc.passive_branch_data.Cf * V) * np.conj(adm.Yf * V) * nc.Sbase

    # compute contingency loading
    loading = Sf / (nc.passive_branch_data.rates + 1e-9)

    return V, Sf, loading, norm_f


class HelmVariations:
    """
    Class to quickly evaluate topological variations based on HELM coefficients
    """

    def __init__(self, numerical_circuit: NumericalCircuit):
        """
        Constructor
        :param numerical_circuit:
        """

        self.numerical_circuit = numerical_circuit

        self.islands = self.numerical_circuit.split_into_islands()

        self.preparations: List[HelmPreparation] = list()

        self.initialize()

    def initialize(self):
        """

        """
        # compose the HVDC power Injections
        Shvdc, _, _, _, _, _ = self.numerical_circuit.hvdc_data.get_power(Sbase=self.numerical_circuit.Sbase,
                                                                          theta=np.zeros(self.numerical_circuit.nbus))

        if len(self.islands) > 0:
            for n_island in range(len(self.islands)):
                island = self.islands[n_island]
                indices = island.get_simulation_indices()

                if len(indices.vd) == 1 and len(indices.no_slack) > 0:
                    # remap global branch indices to island branch indices
                    # branch_index_mapping = {i: idx for idx, i in island.original_branch_idx}
                    # contingency_br_indices_is = list()
                    # for c in contingency_br_indices:
                    #     ci = branch_index_mapping.get(c, None)
                    #     if ci:
                    #         contingency_br_indices_is.append(ci)

                    S0 = island.get_power_injections_pu() + Shvdc[island.bus_data.original_idx]

                    adms = island.get_series_admittance_matrices()

                    helm_prep = helm_preparation_dY(Yseries=adms.Yseries,
                                                    V0=island.bus_data.Vbus,
                                                    S0=S0,
                                                    Ysh0=adms.Yshunt,
                                                    pq=indices.pq,
                                                    pv=indices.pv,
                                                    sl=indices.vd,
                                                    pqpv=indices.no_slack)

                    self.preparations.append(helm_prep)

    def compute_variations(self, contingency_br_indices):
        """

        :param contingency_br_indices:
        :return:
        """
        n_br = self.numerical_circuit.nbr
        n_bus = self.numerical_circuit.nbus
        V = np.zeros(n_bus, dtype=complex)
        Sf = np.zeros(n_br, dtype=complex)
        loading = np.zeros(n_br, dtype=complex)

        if len(self.islands) > 0:
            for n_island in range(len(self.islands)):
                island = self.islands[n_island]
                indices = island.get_simulation_indices()
                if len(indices.vd) == 1 and len(indices.no_slack) > 0:

                    # remap global branch indices to island branch indices
                    branch_index_mapping = {i: idx for idx, i in enumerate(island.passive_branch_data.original_idx)}
                    contingency_br_indices_is = list()
                    for c in contingency_br_indices:
                        ci = branch_index_mapping.get(c, None)
                        if ci:
                            contingency_br_indices_is.append(ci)

                    pre = self.preparations[n_island]
                    adm = island.get_admittance_matrices()
                    Sbus = island.get_power_injections_pu()

                    V_isl, Sf_isl, loading_isl, err = calc_V_outage(nc=island,
                                                                    If=np.zeros(island.nbr, dtype=complex),
                                                                    Ybus=adm.Ybus,
                                                                    sys_mat_factorization=pre.sys_mat_factorization,
                                                                    V0=island.bus_data.Vbus,
                                                                    S0=Sbus,
                                                                    Uini=pre.Uini,
                                                                    Xini=pre.Xini,
                                                                    Yslack=pre.Yslack,
                                                                    Vslack=pre.Vslack,
                                                                    vec_P=pre.vec_P,
                                                                    vec_Q=pre.vec_Q,
                                                                    Ysh=pre.Ysh,
                                                                    vec_W=pre.vec_W,
                                                                    pq=pre.pq,
                                                                    pv=pre.pv,
                                                                    vd=pre.sl,
                                                                    pqpv=pre.pqpv,
                                                                    contingency_br_indices=contingency_br_indices_is)

                    # assign objects to the full matrix
                    V[island.bus_data.original_idx] = V_isl
                    Sf[island.passive_branch_data.original_idx] = Sf_isl
                    loading[island.passive_branch_data.original_idx] = loading_isl

        return V, Sf, loading
