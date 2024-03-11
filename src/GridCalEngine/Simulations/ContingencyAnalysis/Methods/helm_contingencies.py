# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
import scipy as sp

from typing import List
from GridCalEngine.basic_structures import IntVec, CxVec
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Topology.admittance_matrices import compute_admittances
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.helm_power_flow import helm_coefficients_dY, \
    helm_preparation_dY, HelmPreparation


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
    adm = compute_admittances(R=nc.branch_data.R[contingency_br_indices],
                              X=nc.branch_data.X[contingency_br_indices],
                              G=nc.branch_data.G[contingency_br_indices],
                              B=nc.branch_data.B[contingency_br_indices],
                              k=nc.branch_data.k[contingency_br_indices],
                              tap_module=nc.branch_data.tap_module[contingency_br_indices],
                              vtap_f=nc.branch_data.virtual_tap_f[contingency_br_indices],
                              vtap_t=nc.branch_data.virtual_tap_t[contingency_br_indices],
                              tap_angle=nc.branch_data.tap_angle[contingency_br_indices],
                              Beq=nc.branch_data.Beq[contingency_br_indices],
                              Cf=nc.branch_data.C_branch_bus_f[contingency_br_indices, :],
                              Ct=nc.branch_data.C_branch_bus_t[contingency_br_indices, :],
                              G0sw=nc.branch_data.G0sw[contingency_br_indices],
                              If=If[contingency_br_indices],
                              a=nc.branch_data.a[contingency_br_indices],
                              b=nc.branch_data.b[contingency_br_indices],
                              c=nc.branch_data.c[contingency_br_indices],
                              Yshunt_bus=np.zeros(nc.nbus),
                              conn=nc.branch_data.conn[contingency_br_indices],
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
    Sf = (nc.Cf * V) * np.conj(nc.Yf * V) * nc.Sbase

    # compute contingency loading
    loading = Sf / (nc.contingency_rates + 1e-9)

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
            for n_island, island in enumerate(self.islands):

                if len(island.vd) == 1 and len(island.pqpv) > 0:
                    # remap global branch indices to island branch indices
                    # branch_index_mapping = {i: idx for idx, i in island.original_branch_idx}
                    # contingency_br_indices_is = list()
                    # for c in contingency_br_indices:
                    #     ci = branch_index_mapping.get(c, None)
                    #     if ci:
                    #         contingency_br_indices_is.append(ci)

                    S0 = island.Sbus + Shvdc[island.original_bus_idx]

                    helm_prep = helm_preparation_dY(Yseries=island.Yseries,
                                                    V0=island.Vbus,
                                                    S0=S0,
                                                    Ysh0=island.Yshunt,
                                                    pq=island.pq,
                                                    pv=island.pv,
                                                    sl=island.vd,
                                                    pqpv=island.pqpv)

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
            for n_island, island in enumerate(self.islands):

                if len(island.vd) == 1 and len(island.pqpv) > 0:

                    # remap global branch indices to island branch indices
                    branch_index_mapping = {i: idx for idx, i in enumerate(island.original_branch_idx)}
                    contingency_br_indices_is = list()
                    for c in contingency_br_indices:
                        ci = branch_index_mapping.get(c, None)
                        if ci:
                            contingency_br_indices_is.append(ci)

                    pre = self.preparations[n_island]

                    V_isl, Sf_isl, loading_isl, err = calc_V_outage(nc=island,
                                                                    If=np.zeros(island.nbr),
                                                                    Ybus=island.Ybus,
                                                                    sys_mat_factorization=pre.sys_mat_factorization,
                                                                    V0=island.Vbus,
                                                                    S0=island.Sbus,
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
                    V[island.original_bus_idx] = V_isl
                    Sf[island.original_branch_idx] = Sf_isl
                    loading[island.original_branch_idx] = loading_isl

        return V, Sf, loading
