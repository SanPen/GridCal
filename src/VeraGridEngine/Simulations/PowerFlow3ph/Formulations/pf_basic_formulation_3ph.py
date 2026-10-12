# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple, List, Callable
import numba as nb
import numpy as np
from scipy.sparse import lil_matrix, csc_matrix, vstack
from scipy.sparse.linalg import splu
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.Derivatives.ac_jacobian import create_J_vc_csc
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (
    compute_fx_error, power_flow_post_process_nonlinear_3ph, floating_star_currents, floating_star_powers,
    asynchronous_gen_currents
)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_inside_method,
                                                                                     compute_slack_distribution)
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_current,
                                                                                    compute_power,
                                                                                    compute_fx,
                                                                                    polar_to_rect,
                                                                                    fortescue_012_to_abc)
from VeraGridEngine.Topology.simulation_indices import compile_types
from VeraGridEngine.basic_structures import Vec, IntVec, CxVec, CxMat, BoolVec, Logger
from VeraGridEngine.Utils.Sparse.csc2 import (CSC, scipy_to_mat)
from VeraGridEngine.enumerations import BusMode, WindingType, GeneratorType, ShuntConnectionType
from VeraGridEngine.Simulations.PowerFlow3ph.Formulations.positive_sequence_control import PositiveSequenceControl
from VeraGridEngine.Simulations.PowerFlow3ph.Formulations.common_mode_control import CommonModeControl


@nb.jit(cache=True)
def lookup_from_mask(mask: BoolVec) -> IntVec:
    """
    This function builds the lookup vector based on the information provided by the mask vector.
    The mask is a boolean vector with True for existing buses and False for non-existing buses.
    The lookup vector will save a -1 for non-existing buses and will order the existing buses from 0 to n.
    :param mask: Boolean vector with True for existing buses and False for non-existing buses.
    :return: lookup
    """
    lookup = np.full(len(mask), -1, dtype=nb.int64)
    counter = 0
    for i, m in enumerate(mask):
        if m:
            lookup[i] = counter
            counter += 1

    return lookup


def compute_ybus_generator(nc: NumericalCircuit) -> Tuple[csc_matrix]:
    """
    Compute the Ybus matrix for a generator in a 3-phase system with neutral.
    It is used only during the short-circuit analysis, not in power flow simulations.
    :param nc: NumericalCircuit
    :return: Ybus
    """

    n = nc.bus_data.nbus
    m = nc.generator_data.nelm

    Ybus_gen = lil_matrix((4 * n, 4 * n), dtype=complex)
    idx4 = np.array([0, 1, 2, 3])

    for k in range(m):
        f = nc.generator_data.bus_idx[k]
        f4 = 4 * f + idx4

        r0 = nc.generator_data.r0[k]
        x0 = nc.generator_data.x0[k]
        r1 = nc.generator_data.r1[k]
        x1 = nc.generator_data.x1[k]
        r2 = nc.generator_data.r2[k]
        x2 = nc.generator_data.x2[k]

        # Fortescue
        Zabc = fortescue_012_to_abc(complex(r0, x0), complex(r1, x1), complex(r2, x2))
        Ybus_gen[np.ix_(f4[1:4], f4[1:4])] = np.linalg.inv(Zabc)

    return Ybus_gen.tocsc()


def compute_ybus(nc: NumericalCircuit) -> Tuple[csc_matrix, csc_matrix, csc_matrix, CxVec, BoolVec, IntVec, IntVec]:
    """
    Compute admittances and masks

    The mask is a boolean vector that indicates which bus phases are active

    The bus_idx_lookup will relate the original bus indices with the sliced bus indices
    This is useful for managing the sliced bus indices in the power flow problem. For instance:

    original_pq_buses = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    mask = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]

    And the lookup becomes:
    bus_idx_lookup = [0, 1, -1, 2, -1, 3, -1, 4, -1, 5, -1, 6, -1, 7, -1, 8, -1, 9, -1, 10, -1]

    And then it will be simple to get the sliced bus indices that we finally need:
    sliced_pq_buses = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


    :param nc: NumericalCircuit
    :return: Ybus, Yf, Yt, Yshunt_bus, mask, bus_idx_lookup
    """

    n = nc.bus_data.nbus
    m = nc.passive_branch_data.nelm
    Cf = lil_matrix((4 * m, 4 * n), dtype=int)
    Ct = lil_matrix((4 * m, 4 * n), dtype=int)
    Yf = lil_matrix((4 * m, 4 * n), dtype=complex)
    Yt = lil_matrix((4 * m, 4 * n), dtype=complex)

    idx4 = np.array([0, 1, 2, 3])  # array that we use to generate the 3-phase indices

    R = np.zeros(4 * m, dtype=bool)

    for k in range(m):
        f = nc.passive_branch_data.F[k]
        t = nc.passive_branch_data.T[k]

        f4 = 4 * f + idx4
        t4 = 4 * t + idx4
        k4 = 4 * k + idx4

        Yf[np.ix_(k4, f4)] = nc.passive_branch_data.Yff3[k4, :]
        Yf[np.ix_(k4, t4)] = nc.passive_branch_data.Yft3[k4, :]
        Yt[np.ix_(k4, f4)] = nc.passive_branch_data.Ytf3[k4, :]
        Yt[np.ix_(k4, t4)] = nc.passive_branch_data.Ytt3[k4, :]

        R[4 * k + 0] = nc.passive_branch_data.phN[k]
        R[4 * k + 1] = nc.passive_branch_data.phA[k]
        R[4 * k + 2] = nc.passive_branch_data.phB[k]
        R[4 * k + 3] = nc.passive_branch_data.phC[k]

        Cf[k4, f4] = 1
        Ct[k4, t4] = 1

    if nc.passive_branch_data.Ycoupling3.nnz > 0:
        mutual: csc_matrix = nc.passive_branch_data.Ycoupling3 @ vstack((Cf, Ct), format='csc')
        Yf += mutual[:4 * m, :]
        Yt += mutual[4 * m:, :]
    else:
        pass

    zero_mask = (R == 0)
    Cfcopy = Cf.copy()
    Ctcopy = Ct.copy()

    Cfcopy[zero_mask, :] = 0
    Ctcopy[zero_mask, :] = 0

    Ctot = Cfcopy + Ctcopy
    col_sums = np.array(Ctot.sum(axis=0))[0, :]
    binary_bus_mask = (col_sums > 0).astype(bool)

    F = np.array(nc.passive_branch_data.F, dtype=int)
    T = np.array(nc.passive_branch_data.T, dtype=int)

    # --- build CSR-like incidence list: branches per bus (Numba-friendly) ---
    deg = np.zeros(n, dtype=np.int64)  # number of incident branches per bus (the bus “degree”)
    for k in range(m):
        deg[F[k]] += 1
        deg[T[k]] += 1

    # Index pointer into bus_branches that gives where each bus’s incident branches start and end
    ptr = np.zeros(n + 1, dtype=np.int64)
    for i in range(n):
        ptr[i + 1] = ptr[i] + deg[i]

    bus_branches = np.zeros(ptr[-1], dtype=np.int64)
    fill = np.zeros(n, dtype=np.int64)
    for k in range(m):
        f = F[k]
        t = T[k]

        pos_f = ptr[f] + fill[f]
        bus_branches[pos_f] = k
        fill[f] += 1

        pos_t = ptr[t] + fill[t]
        bus_branches[pos_t] = k
        fill[t] += 1

    bus_has_neutral = np.ones(4 * n, dtype=bool)  # por defecto el neutro del bus está activo

    for bus_idx in range(n):
        start = ptr[bus_idx]
        end = ptr[bus_idx + 1]

        grounded_here = False

        # Only buses with at least one incident branch need the explicit grounding scan.
        # Isolated buses keep the default neutral-active state and fall through untouched.
        if start == end:
            grounded_here = False
        else:
            # Iterate only over branches actually connected to this bus and stop as
            # soon as one grounded-star terminal is found.
            for p in range(start, end):
                k = bus_branches[p]

                if F[k] == bus_idx and nc.passive_branch_data.conn_f[k] == WindingType.GroundedStar.idx():
                    grounded_here = True
                    break
                else:
                    if T[k] == bus_idx and nc.passive_branch_data.conn_t[k] == WindingType.GroundedStar.idx():
                        grounded_here = True
                        break
                    else:
                        pass

        if grounded_here:
            bus_has_neutral[4 * bus_idx + 0] = False  # desactiva el nodo de neutro del bus
        else:
            pass

    bus_has_neutral[0::4] &= nc.bus_data.bus_types != BusMode.Slack_tpe.value

    grounded_shunt_buses = nc.shunt_data.bus_idx[
        nc.shunt_data.active & nc.shunt_data.grounds_neutral
    ]
    bus_has_neutral[4 * grounded_shunt_buses] = False

    # aplica la prioridad: si algún trafo, shunt o el slack aterra el neutro, el neutro se elimina del solver
    binary_bus_mask[0::4] = binary_bus_mask[0::4] & bus_has_neutral[0::4]

    Ysh_bus = np.zeros((n * 4, n * 4), dtype=complex)
    for k in range(nc.shunt_data.nelm):
        f = nc.shunt_data.bus_idx[k]
        k4 = 4 * k + idx4
        f4 = 4 * f + idx4
        Ysh_bus[np.ix_(f4, f4)] += nc.shunt_data.Y3_star[np.ix_(k4, idx4)] / (nc.Sbase / 3)

    for k in range(nc.load_data.nelm):
        f = nc.load_data.bus_idx[k]
        k4 = 4 * k + idx4
        f4 = 4 * f + idx4
        Ysh_bus[np.ix_(f4, f4)] += nc.load_data.Y3_star[np.ix_(k4, idx4)] / (nc.Sbase / 3)

    Ybus = Cfcopy.T @ Yf + Ctcopy.T @ Yt + Ysh_bus

    Ybus = Ybus[np.ix_(binary_bus_mask, binary_bus_mask)]
    Ysh_bus = Ysh_bus[np.ix_(binary_bus_mask, binary_bus_mask)]
    Yf = Yf[np.ix_(R, binary_bus_mask)]
    Yt = Yt[np.ix_(R, binary_bus_mask)]

    bus_idx_lookup = lookup_from_mask(binary_bus_mask)
    branch_lookup = lookup_from_mask(R)

    Ybus = csc_matrix(Ybus)

    return Ybus.tocsc(), Yf.tocsc(), Yt.tocsc(), Ysh_bus, binary_bus_mask, bus_idx_lookup, branch_lookup


def compute_generators(bus_idx: IntVec,
                       bus_lookup: IntVec,
                       V: CxVec,
                       P: Vec,
                       Q: Vec,
                       control_mode_int: IntVec) -> CxVec:
    """

    :param bus_idx:
    :param bus_lookup:
    :param V:
    :param P:
    :param Q:
    :param control_mode_int:
    :return:
    """
    n = len(V)
    nelm = len(bus_idx)
    Igen = np.zeros(n, dtype=complex)

    for k in range(nelm):

        if control_mode_int[k] == 1:  # GeneratorControlMode.V: 1
            Q[k] = 0.0

        f = bus_idx[k]

        a = 4 * f + 1
        b = 4 * f + 2
        c = 4 * f + 3

        a2 = bus_lookup[a]
        b2 = bus_lookup[b]
        c2 = bus_lookup[c]

        # Fixed-power units can share a terminal with each other and a U1 regulator.
        Igen[a2] += np.conj((P[k] + Q[k] * 1j) / 3 / V[a2])
        Igen[b2] += np.conj((P[k] + Q[k] * 1j) / 3 / V[b2])
        Igen[c2] += np.conj((P[k] + Q[k] * 1j) / 3 / V[c2])

    return Igen


# @nb.jit(cache=True)
def compute_current_loads(bus_idx: IntVec,
                          bus_lookup: IntVec,
                          V: CxVec,
                          Istar: CxVec,
                          Idelta: CxVec,
                          Ifloating: CxVec) -> Tuple[CxVec, CxVec, CxVec]:
    """

    :param bus_idx:
    :param bus_lookup:
    :param V:
    :param Istar:
    :param Idelta:
    :param Ifloating:
    :return:
    """
    n = len(V)
    nelm = len(bus_idx)

    # I = np.zeros(n, dtype=nb.complex128)
    I = np.zeros(n, dtype=complex)

    # zero_load = nb.complex128(0.0)
    zero_load = complex(0.0, 0.0)

    # Un_floating = np.zeros(len(V), dtype=nb.complex128)
    Un_floating = np.zeros(len(V), dtype=complex)

    for k in range(nelm):

        f = bus_idx[k]

        n = 4 * f + 0
        a = 4 * f + 1
        b = 4 * f + 2
        c = 4 * f + 3

        n2 = bus_lookup[n]
        a2 = bus_lookup[a]
        b2 = bus_lookup[b]
        c2 = bus_lookup[c]

        nn = 4 * k + 0
        ab = 4 * k + 1
        bc = 4 * k + 2
        ca = 4 * k + 3

        star = (Istar[ab] != zero_load or Istar[bc] != zero_load or Istar[ca] != zero_load)
        floating = (Ifloating[ab] != zero_load or Ifloating[bc] != zero_load or Ifloating[ca] != zero_load)
        delta = (Idelta[ab] != zero_load or Idelta[bc] != zero_load or Idelta[ca] != zero_load)

        n_connected = (Istar[nn] != zero_load and n2 >= 0)
        a_connected = (Istar[ab] != zero_load)
        b_connected = (Istar[bc] != zero_load)
        c_connected = (Istar[ca] != zero_load)

        ab_connected = (Idelta[ab] != zero_load)
        bc_connected = (Idelta[bc] != zero_load)
        ca_connected = (Idelta[ca] != zero_load)

        voltage_angle_n = np.angle(V[n2])
        voltage_angle_a = np.angle(V[a2])
        voltage_angle_b = np.angle(V[b2])
        voltage_angle_c = np.angle(V[c2])

        voltage_angle_ab = np.angle(V[a2] - V[b2])
        voltage_angle_bc = np.angle(V[b2] - V[c2])
        voltage_angle_ca = np.angle(V[c2] - V[a2])

        if delta and ab_connected and bc_connected and ca_connected:

            if a2 >= 0 and b2 >= 0 and c2 >= 0:
                Iab = np.conj(Idelta[ab] / np.sqrt(3)) * np.exp(1j * voltage_angle_ab)
                Ibc = np.conj(Idelta[bc] / np.sqrt(3)) * np.exp(1j * voltage_angle_bc)
                Ica = np.conj(Idelta[ca] / np.sqrt(3)) * np.exp(1j * voltage_angle_ca)
                I[a2] = -(Iab - Ica)
                I[b2] = -(Ibc - Iab)
                I[c2] = -(Ica - Ibc)

            elif a2 < 0:
                Ibc = np.conj(Idelta[bc] / np.sqrt(3)) * np.exp(1j * voltage_angle_bc)
                I[b2] = -Ibc
                I[c2] = Ibc

            elif b2 < 0:
                Ica = np.conj(Idelta[ca] / np.sqrt(3)) * np.exp(1j * voltage_angle_ca)
                I[a2] = Ica
                I[c2] = -Ica

            elif c2 < 0:
                Iab = np.conj(Idelta[ab] / np.sqrt(3)) * np.exp(1j * voltage_angle_ab)
                I[a2] = -Iab
                I[b2] = Iab

            else:
                I[a2] = zero_load
                I[b2] = zero_load
                I[c2] = zero_load

        elif delta and ab_connected:

            if a2 >= 0 and b2 >= 0:
                Iab = np.conj(Idelta[ab] / np.sqrt(3)) * np.exp(1j * voltage_angle_ab)
                I[a2] = -Iab
                I[b2] = -(-Iab)
            else:
                I[a2] = zero_load
                I[b2] = zero_load

        elif delta and bc_connected:

            if b2 >= 0 and c2 >= 0:
                Ibc = np.conj(Idelta[bc] / np.sqrt(3)) * np.exp(1j * voltage_angle_bc)
                I[b2] = -Ibc
                I[c2] = -(-Ibc)
            else:
                I[b2] = zero_load
                I[c2] = zero_load

        elif delta and ca_connected:

            if c2 >= 0 and a2 >= 0:
                Ica = np.conj(Idelta[ca] / np.sqrt(3)) * np.exp(1j * voltage_angle_ca)
                I[a2] = -(-Ica)
                I[c2] = -Ica
            else:
                I[a2] = zero_load
                I[c2] = zero_load

        elif star and a_connected and b_connected and c_connected and n_connected:

            Uan = V[a2] - V[n2]
            Ubn = V[b2] - V[n2]
            Ucn = V[c2] - V[n2]

            Ian = np.conj(Istar[ab]) * (Uan / abs(Uan))
            Ibn = np.conj(Istar[bc]) * (Ubn / abs(Ubn))
            Icn = np.conj(Istar[ca]) * (Ucn / abs(Ucn))

            I[a2] -= Ian
            I[b2] -= Ibn
            I[c2] -= Icn
            I[n2] += (Ian + Ibn + Icn)

        elif star and a_connected and b_connected and n_connected:

            Uan = V[a2] - V[n2]
            Ubn = V[b2] - V[n2]

            Ian = np.conj(Istar[ab]) * (Uan / abs(Uan))
            Ibn = np.conj(Istar[bc]) * (Ubn / abs(Ubn))

            I[a2] -= Ian
            I[b2] -= Ibn
            I[n2] += (Ian + Ibn)

        elif star and b_connected and c_connected and n_connected:

            Ubn = V[b2] - V[n2]
            Ucn = V[c2] - V[n2]

            Ibn = np.conj(Istar[bc]) * (Ubn / abs(Ubn))
            Icn = np.conj(Istar[ca]) * (Ucn / abs(Ucn))

            I[b2] -= Ibn
            I[c2] -= Icn
            I[n2] += (Ibn + Icn)

        elif star and a_connected and c_connected and n_connected:

            Uan = V[a2] - V[n2]
            Ucn = V[c2] - V[n2]

            Ian = np.conj(Istar[ab]) * (Uan / abs(Uan))
            Icn = np.conj(Istar[ca]) * (Ucn / abs(Ucn))

            I[a2] -= Ian
            I[c2] -= Icn
            I[n2] += (Ian + Icn)

        elif star and a_connected and n_connected:

            Uan = V[a2] - V[n2]
            Ian = np.conj(Istar[ab]) * (Uan / abs(Uan))
            I[a2] -= Ian
            I[n2] += Ian

        elif star and b_connected and n_connected:

            Ubn = V[b2] - V[n2]
            Ibn = np.conj(Istar[bc]) * (Ubn / abs(Ubn))
            I[b2] -= Ibn
            I[n2] += Ibn

        elif star and c_connected and n_connected:

            Ucn = V[c2] - V[n2]
            Icn = np.conj(Istar[ca]) * (Ucn / abs(Ucn))
            I[c2] -= Icn
            I[n2] += Icn

        elif star and a_connected and b_connected and c_connected:

            if a2 >= 0:
                I[a2] -= np.conj(Istar[ab]) * np.exp(1j * voltage_angle_a)
            if b2 >= 0:
                I[b2] -= np.conj(Istar[bc]) * np.exp(1j * voltage_angle_b)
            if c2 >= 0:
                I[c2] -= np.conj(Istar[ca]) * np.exp(1j * voltage_angle_c)

        elif star and a_connected and b_connected:

            if a2 >= 0:
                I[a2] -= np.conj(Istar[ab]) * np.exp(1j * voltage_angle_a)
            if b2 >= 0:
                I[b2] -= np.conj(Istar[bc]) * np.exp(1j * voltage_angle_b)

        elif star and b_connected and c_connected:

            if b2 >= 0:
                I[b2] -= np.conj(Istar[bc]) * np.exp(1j * voltage_angle_b)
            if c2 >= 0:
                I[c2] -= np.conj(Istar[ca]) * np.exp(1j * voltage_angle_c)

        elif star and a_connected and c_connected:

            if a2 >= 0:
                I[a2] -= np.conj(Istar[ab]) * np.exp(1j * voltage_angle_a)
            if c2 >= 0:
                I[c2] -= np.conj(Istar[ca]) * np.exp(1j * voltage_angle_c)

        elif star and a_connected:
            if a2 >= 0:
                I[a2] -= np.conj(Istar[ab]) * np.exp(1j * voltage_angle_a)

        elif star and b_connected:
            if b2 >= 0:
                I[b2] -= np.conj(Istar[bc]) * np.exp(1j * voltage_angle_b)

        elif star and c_connected:
            if c2 >= 0:
                I[c2] -= np.conj(Istar[ca]) * np.exp(1j * voltage_angle_c)

        elif floating:

            Vn_prev = (V[a2] + V[b2] + V[c2]) / 3

            if a2 >= 0 and b2 >= 0 and c2 >= 0:
                Ia, Ib, Ic, Un = floating_star_currents(V[a2], V[b2], V[c2],
                                                        Ifloating[ab], Ifloating[bc], Ifloating[ca],
                                                        Vn_prev)
            elif a2 >= 0 and b2 >= 0:
                Ia, Ib, Ic, Un = floating_star_currents(V[a2], V[b2], zero_load,
                                                        Ifloating[ab], Ifloating[bc], zero_load,
                                                        Vn_prev)
            elif b2 >= 0 and c2 >= 0:
                Ia, Ib, Ic, Un = floating_star_currents(zero_load, V[b2], V[c2],
                                                        zero_load, Ifloating[bc], Ifloating[ca],
                                                        Vn_prev)
            elif a2 >= 0 and c2 >= 0:
                Ia, Ib, Ic, Un = floating_star_currents(V[a2], zero_load, V[c2],
                                                        Ifloating[ab], zero_load, Ifloating[ca],
                                                        Vn_prev)
            else:
                Ia, Ib, Ic, Un = zero_load, zero_load, zero_load, zero_load

            I[a2] -= Ia
            I[b2] -= Ib
            I[c2] -= Ic

            Un_floating[a2] = Un
            Un_floating[b2] = Un
            Un_floating[c2] = Un

        else:
            pass

    # Y_current_linear = np.zeros_like(I, dtype=nb.complex128)
    Y_current_linear = np.zeros_like(I, dtype=complex)
    for i in range(len(V)):
        if abs(V[i]) > 1e-12:
            Y_current_linear[i] = I[i] / V[i]

    return I, Y_current_linear, Un_floating


# @nb.jit(cache=True)
def compute_power_loads(bus_idx: IntVec,
                        bus_lookup: IntVec,
                        V: CxVec,
                        Sstar: CxVec,
                        Sfloating: CxVec,
                        Sdelta: CxVec) -> Tuple[CxVec, CxVec, CxVec]:
    """

    :param bus_idx:
    :param bus_lookup:
    :param V:
    :param Sstar:
    :param Sfloating:
    :param Sdelta:
    :return:
    """
    n = len(V)
    nelm = len(bus_idx)

    # I = np.zeros(n, dtype=nb.complex128)
    I = np.zeros(n, dtype=complex)

    # zero_load = nb.complex128(0.0)
    zero_load = 0.0 + 0.0j

    # Un_floating = np.zeros(len(V), dtype=nb.complex128)
    Un_floating = np.zeros(len(V), dtype=complex)

    for k in range(nelm):

        f = bus_idx[k]

        n = 4 * f + 0
        a = 4 * f + 1
        b = 4 * f + 2
        c = 4 * f + 3

        n2 = bus_lookup[n]
        a2 = bus_lookup[a]
        b2 = bus_lookup[b]
        c2 = bus_lookup[c]

        nn = 4 * k + 0
        ab = 4 * k + 1
        bc = 4 * k + 2
        ca = 4 * k + 3

        star = (Sstar[ab] != zero_load or Sstar[bc] != zero_load or Sstar[ca] != zero_load)
        floating = (Sfloating[ab] != zero_load or Sfloating[bc] != zero_load or Sfloating[ca] != zero_load)
        delta = (Sdelta[ab] != zero_load or Sdelta[bc] != zero_load or Sdelta[ca] != zero_load)

        n_connected = (Sstar[nn] != zero_load and n2 >= 0)
        a_connected = (Sstar[ab] != zero_load)
        b_connected = (Sstar[bc] != zero_load)
        c_connected = (Sstar[ca] != zero_load)

        ab_connected = (Sdelta[ab] != zero_load)
        bc_connected = (Sdelta[bc] != zero_load)
        ca_connected = (Sdelta[ca] != zero_load)

        if delta and ab_connected and bc_connected and ca_connected:

            if a2 >= 0 and b2 >= 0 and c2 >= 0:
                I[a2] -= np.conj(Sdelta[ab] / (V[a2] - V[b2]))
                I[a2] -= np.conj(Sdelta[ca] / (V[a2] - V[c2]))
                I[b2] -= np.conj(Sdelta[ab] / (V[b2] - V[a2]))
                I[b2] -= np.conj(Sdelta[bc] / (V[b2] - V[c2]))
                I[c2] -= np.conj(Sdelta[bc] / (V[c2] - V[b2]))
                I[c2] -= np.conj(Sdelta[ca] / (V[c2] - V[a2]))

            elif a2 < 0:
                I[b2] -= np.conj(Sdelta[bc] / (V[b2] - V[c2]))
                I[c2] -= np.conj(Sdelta[bc] / (V[c2] - V[b2]))

            elif b2 < 0:
                I[a2] -= np.conj(Sdelta[ca] / (V[a2] - V[c2]))
                I[c2] -= np.conj(Sdelta[ca] / (V[c2] - V[a2]))

            elif c2 < 0:
                I[a2] -= np.conj(Sdelta[ab] / (V[a2] - V[b2]))
                I[b2] -= np.conj(Sdelta[ab] / (V[b2] - V[a2]))

        elif delta and ab_connected:

            if a2 >= 0 and b2 >= 0:
                I[a2] -= np.conj(Sdelta[ab] / (V[a2] - V[b2]))
                I[b2] -= np.conj(Sdelta[ab] / (V[b2] - V[a2]))
            else:
                I[a2] -= zero_load
                I[b2] -= zero_load

        elif delta and bc_connected:

            if b2 >= 0 and c2 >= 0:
                I[b2] -= np.conj(Sdelta[bc] / (V[b2] - V[c2]))
                I[c2] -= np.conj(Sdelta[bc] / (V[c2] - V[b2]))
            else:
                I[b2] -= zero_load
                I[c2] -= zero_load

        elif delta and ca_connected:

            if c2 >= 0 and a2 >= 0:
                I[c2] -= np.conj(Sdelta[ca] / (V[c2] - V[a2]))
                I[a2] -= np.conj(Sdelta[ca] / (V[a2] - V[c2]))
            else:
                I[c2] -= zero_load
                I[a2] -= zero_load

        elif star and a_connected and b_connected and c_connected and n_connected:

            Uan = V[a2] - V[n2]
            Ubn = V[b2] - V[n2]
            Ucn = V[c2] - V[n2]

            Ian = np.conj(Sstar[ab] / Uan)
            Ibn = np.conj(Sstar[bc] / Ubn)
            Icn = np.conj(Sstar[ca] / Ucn)

            I[a2] -= Ian
            I[b2] -= Ibn
            I[c2] -= Icn
            I[n2] += (Ian + Ibn + Icn)

        elif star and a_connected and b_connected and n_connected:

            Uan = V[a2] - V[n2]
            Ubn = V[b2] - V[n2]

            Ian = np.conj(Sstar[ab] / Uan)
            Ibn = np.conj(Sstar[bc] / Ubn)

            I[a2] -= Ian
            I[b2] -= Ibn
            I[n2] += (Ian + Ibn)

        elif star and b_connected and c_connected and n_connected:

            Ubn = V[b2] - V[n2]
            Ucn = V[c2] - V[n2]

            Ibn = np.conj(Sstar[bc] / Ubn)
            Icn = np.conj(Sstar[ca] / Ucn)

            I[b2] -= Ibn
            I[c2] -= Icn
            I[n2] += (Ibn + Icn)

        elif star and a_connected and c_connected and n_connected:

            Uan = V[a2] - V[n2]
            Ucn = V[c2] - V[n2]

            Ian = np.conj(Sstar[ab] / Uan)
            Icn = np.conj(Sstar[ca] / Ucn)

            I[a2] -= Ian
            I[c2] -= Icn
            I[n2] += (Ian + Icn)

        elif star and a_connected and n_connected:

            Uan = V[a2] - V[n2]
            Ian = np.conj(Sstar[ab] / Uan)
            I[a2] -= Ian
            I[n2] += Ian

        elif star and b_connected and n_connected:

            Ubn = V[b2] - V[n2]
            Ibn = np.conj(Sstar[bc] / Ubn)
            I[b2] -= Ibn
            I[n2] += Ibn

        elif star and c_connected and n_connected:

            Ucn = V[c2] - V[n2]
            Icn = np.conj(Sstar[ca] / Ucn)
            I[c2] -= Icn
            I[n2] += Icn

        elif star and a_connected and b_connected and c_connected:

            if a2 >= 0:
                I[a2] -= np.conj(Sstar[ab] / (V[a2]))
            if b2 >= 0:
                I[b2] -= np.conj(Sstar[bc] / (V[b2]))
            if c2 >= 0:
                I[c2] -= np.conj(Sstar[ca] / (V[c2]))

        elif star and a_connected and b_connected:

            if a2 >= 0:
                I[a2] -= np.conj(Sstar[ab] / (V[a2]))
            if b2 >= 0:
                I[b2] -= np.conj(Sstar[bc] / (V[b2]))

        elif star and b_connected and c_connected:

            if b2 >= 0:
                I[b2] -= np.conj(Sstar[bc] / (V[b2]))
            if c2 >= 0:
                I[c2] -= np.conj(Sstar[ca] / (V[c2]))

        elif star and a_connected and c_connected:

            if a2 >= 0:
                I[a2] -= np.conj(Sstar[ab] / (V[a2]))
            if c2 >= 0:
                I[c2] -= np.conj(Sstar[ca] / (V[c2]))

        elif star and a_connected:
            if a2 >= 0:
                I[a2] -= np.conj(Sstar[ab] / (V[a2]))

        elif star and b_connected:
            if b2 >= 0:
                I[b2] -= np.conj(Sstar[bc] / (V[b2]))

        elif star and c_connected:
            if c2 >= 0:
                I[c2] -= np.conj(Sstar[ca] / (V[c2]))

        elif floating:

            if a2 >= 0 and b2 >= 0 and c2 >= 0:
                Ia, Ib, Ic, Un = floating_star_powers(V[a2], V[b2], V[c2],
                                                      Sfloating[ab], Sfloating[bc], Sfloating[ca])
                I[a2] -= Ia
                I[b2] -= Ib
                I[c2] -= Ic

            elif a2 >= 0 and b2 >= 0:
                Ia, Ib, Ic, Un = floating_star_powers(V[a2], V[b2], zero_load,
                                                      Sfloating[ab], Sfloating[bc], zero_load)
                I[a2] -= Ia
                I[b2] -= Ib
                I[c2] -= zero_load

            elif b2 >= 0 and c2 >= 0:
                Ia, Ib, Ic, Un = floating_star_powers(zero_load, V[b2], V[c2],
                                                      zero_load, Sfloating[bc], Sfloating[ca])
                I[a2] -= zero_load
                I[b2] -= Ib
                I[c2] -= Ic

            elif a2 >= 0 and c2 >= 0:
                Ia, Ib, Ic, Un = floating_star_powers(V[a2], zero_load, V[c2],
                                                      Sfloating[ab], zero_load, Sfloating[ca])
                I[a2] -= Ia
                I[b2] -= zero_load
                I[c2] -= Ic

            else:
                I[a2] -= zero_load
                I[b2] -= zero_load
                I[c2] -= zero_load
                Un = zero_load

            Un_floating[a2] = Un
            Un_floating[b2] = Un
            Un_floating[c2] = Un

        else:
            pass

    # Y_power_linear = np.zeros_like(I, dtype=nb.complex128)
    Y_power_linear = np.zeros_like(I, dtype=complex)
    for i in range(len(V)):
        if abs(V[i]) > 1e-12:
            Y_power_linear[i] = I[i] / V[i]

    return I, Y_power_linear, Un_floating


def calc_autodiff_jacobian(func: Callable[[Vec], Vec], x: Vec, h: float = 1e-6) -> CSC:
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.
    df/dx = (f(x+h) - f(x)) / h

    :param func: function accepting a vector x and args, and returning either a vector or a
                 tuple where the first argument is a vector and the second.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a CSC matrix.
    """
    nx = len(x)
    f0 = func(x)

    n_rows = len(f0)

    jac = lil_matrix((n_rows, nx))

    for j in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[j] += h
        f_plus_h = func(x_plus_h)
        row = (f_plus_h - f0) / h
        for i in range(n_rows):
            if row[i] != 0.0:
                jac[i, j] = row[i]

    return scipy_to_mat(jac.tocsc())


@nb.jit(cache=True)
def expand3ph(x: np.ndarray) -> np.ndarray:
    """
    Expands a numpy array to 3-pase copying the same values
    :param x:
    :return:
    """
    n = len(x)
    idx4 = np.array([0, 1, 2, 3])
    x4 = np.zeros(4 * n, dtype=x.dtype)

    for k in range(n):
        x4[4 * k + idx4] = x[k]
    return x4


@nb.jit(cache=True)
def slice_indices(pq: IntVec, bus_lookup: IntVec) -> IntVec:
    """
    Slice the indices based on the bus_lookup
    :param pq: original bus indices
    :param bus_lookup: mapping between original and sliced bus indices
    :return:
    """

    max_nnz = len(pq)
    vec = np.zeros(max_nnz, dtype=nb.int64)
    counter = 0
    for pq_idx in pq:
        val = bus_lookup[pq_idx]
        if val > -1:
            vec[counter] = val
            counter += 1

    return vec[:counter]


@nb.jit(cache=True)
def expand_indices_3ph(x: np.ndarray) -> np.ndarray:
    """
    Expands a numpy array to 3-pase copying the same values
    :param x:
    :return:
    """
    n = len(x)
    idx4 = np.array([0, 1, 2, 3])
    x4 = np.zeros(4 * n, dtype=nb.int64)

    for k in range(n):
        x4[4 * k + idx4] = 4 * x[k] + idx4

    return x4


@nb.jit(cache=True)
def expand_slice_indices_3ph(x: np.ndarray, bus_lookup: IntVec) -> np.ndarray:
    """
    Expands and slices a numpy array to 3-phase copying the same values
    :param x:
    :param bus_lookup:
    :return:
    """
    x3 = expand_indices_3ph(x)

    x3_final = slice_indices(x3, bus_lookup)
    return np.sort(x3_final)


@nb.jit(cache=True)
def expandVoltage3ph(V0: CxVec) -> CxVec:
    """
    Expands a numpy array to 3-pase copying the same values
    :param V0: array of bus voltages in positive sequence
    :return: Array of three-phase voltages in 3-phase ABC
    """
    n = len(V0)
    idx4 = np.array([0, 1, 2, 3], dtype=nb.int64)

    angles = np.array([0, 0, -2 * np.pi / 3, 2 * np.pi / 3], dtype=nb.float64)

    Vm = np.abs(V0)
    Va = np.angle(V0)
    x4 = np.zeros(4 * n, dtype=nb.complex128)

    for k in range(n):
        x4[4 * k] = 1e-4 * np.exp(1j * Va[k])
        x4[4 * k + idx4[1:]] = Vm[k] * np.exp(1j * (Va[k] + angles[1:]))

    return x4


@nb.jit(cache=True)
def expand_magnitudes(magnitude: CxVec, lookup: IntVec) -> CxVec:
    """
    Expands the masked magnitude using the lookup saving zeros where the lookup is -1,
    which means that this bus did not exist, and it was previously eliminated.
    :param magnitude: The magnitude to expand, for instance, the voltage vector at each bus
    :param lookup: The vector which contains the information about the existing and eliminated buses
    :return: magnitude_expanded
    """
    n_buses_total = len(lookup)
    magnitude_expanded = np.zeros(n_buses_total, dtype=nb.complex128)
    for i, value in enumerate(lookup):
        if value < 0:
            magnitude_expanded[i] = nb.complex128(0.0)
        else:
            magnitude_expanded[i] = magnitude[value]

    return magnitude_expanded


@nb.jit(cache=True)
def expand_matrix(magnitude: np.ndarray, lookup: IntVec) -> CxMat:
    """
    Expands a matrix by adding zero rows and columns based on the lookup indices.
    If a lookup value is negative, the corresponding row and column in the matrix
    will be replaced by zeros.

    :param magnitude: 2D numpy array (matrix to expand)
    :param lookup: List of indices for lookup
    :return: Expanded matrix with zeros in the rows and columns where lookup values are negative
    """
    n_buses_total = len(lookup)

    # Initialize the expanded matrix as a zero matrix of the same size as the lookup
    magnitude_expanded = np.zeros((n_buses_total, n_buses_total), dtype=nb.complex128)

    for i, value in enumerate(lookup):
        if value >= 0:
            # Assign the value from the original matrix to the expanded matrix
            magnitude_expanded[i, i] = magnitude[value, value]
        # Else, the row and column for that index will already be zeros by default.

    return magnitude_expanded


def passive_neutral_reduction(nc: NumericalCircuit, ybus: csc_matrix,
                              mask: BoolVec) -> Tuple[IntVec, csc_matrix | None]:
    """Eliminate only linear, zero-injection neutral equations by exact Schur reduction.

    The voltage map reconstructs neutral voltages; no neutral is grounded and no
    phase common mode is constrained. Singular neutral blocks remain explicit.

    :param nc: Compiled network and nonlinear injection connections.
    :param ybus: Admittance matrix after removing absent or grounded conductors.
    :param mask: Full NABC conductor mask corresponding to ybus.
    :return: Retained indices and optional full-voltage reconstruction matrix.
    """
    candidates: BoolVec = np.flatnonzero(mask) % 4 == 0
    protected: BoolVec = np.zeros(nc.nbus, dtype=bool)
    # Explicit star P/I loads need their neutral voltage during each iteration.
    for k in range(nc.load_data.nelm):
        if nc.load_data.S3_star[4 * k] != 0 or nc.load_data.I3_star[4 * k] != 0:
            protected[nc.load_data.bus_idx[k]] = True
        else:
            pass
    candidates &= ~np.repeat(protected, 4)[mask]
    keep: IntVec = np.flatnonzero(~candidates)
    neutral: IntVec = np.flatnonzero(candidates)
    if len(neutral) == 0:
        return keep, None
    else:
        try:
            response: CxMat = -splu(ybus[neutral, :][:, neutral].tocsc()).solve(
                ybus[neutral, :][:, keep].toarray())
        except RuntimeError:
            return np.arange(ybus.shape[0]), None
        else:
            lift: lil_matrix = lil_matrix((ybus.shape[0], len(keep)), dtype=complex)
            lift[keep, np.arange(len(keep))] = 1.0
            lift[neutral, :] = response
            return keep, lift.tocsc()


class PfBasicFormulation3Ph(PfFormulationTemplate):

    __slots__ = (
        "Ybus",
        "Yf",
        "Yt",
        "Yshunt_bus",
        "mask",
        "bus_lookup",
        "branch_lookup",
        "full_admittances",
        "retained",
        "voltage_lift",
        "Un_floating_current",
        "Un_floating_power",
        "logger",
        "nc",
        "S0",
        "Qmin",
        "Qmax",
        "vd",
        "pq",
        "pv",
        "pqv",
        "p",
        "no_slack",
        "idx_dVa",
        "idx_dVm",
        "idx_dP",
        "idx_dQ",
        "positive_sequence",
        "common_mode",
    )

    def __init__(self,
                 V0: CxVec,
                 S0: CxVec,
                 Qmin: Vec,
                 Qmax: Vec,
                 nc: NumericalCircuit,
                 options: PowerFlowOptions,
                 logger: Logger) -> None:
        """
        PfBasicFormulation3Ph
        :param V0: Array of nodal initial solution (3N)
        :param S0: Array of power injections (3N)
        :param Qmin: Array of bus reactive power upper limit (N, not 3N)
        :param Qmax: Array of bus reactive power lower limit (N, not 3N)
        :param nc: NumericalCircuit
        :param options: PowerFlowOptions
        """
        self.full_admittances: tuple = compute_ybus(nc)
        self.Ybus, self.Yf, self.Yt, self.Yshunt_bus, self.mask, self.bus_lookup, self.branch_lookup = self.full_admittances
        self.retained, self.voltage_lift = passive_neutral_reduction(nc, self.Ybus, self.mask)
        if self.voltage_lift is not None:
            # Schur complement of passive N equations, using the existing solver unchanged.
            self.Ybus = (self.Ybus[self.retained, :] @ self.voltage_lift).tocsc()
            self.Yf = (self.Yf @ self.voltage_lift).tocsc()
            self.Yt = (self.Yt @ self.voltage_lift).tocsc()
            self.Yshunt_bus = self.Yshunt_bus[np.ix_(self.retained, self.retained)]
            retained_full: IntVec = np.flatnonzero(self.mask)[self.retained]
            self.mask = np.zeros_like(self.mask)
            self.mask[retained_full] = True
            self.bus_lookup = lookup_from_mask(self.mask)
        else:
            pass
        V0new = V0[self.mask]

        self.Un_floating_current = np.zeros(len(V0new), dtype=complex)
        self.Un_floating_power = np.zeros(len(V0new), dtype=complex)

        PfFormulationTemplate.__init__(self, V0=V0new.astype(complex), options=options)
        self.logger = logger
        self.nc = nc
        self.S0: CxVec = S0[self.mask].copy()
        self.positive_sequence: PositiveSequenceControl = PositiveSequenceControl(nc, self.bus_lookup)

        self.Qmin = expand3ph(Qmin)[self.mask] * 100e6
        self.Qmax = expand3ph(Qmax)[self.mask] * 100e6

        # U1 regulation retains all phase balance equations; its extra Q unknown
        # and voltage constraint replace the three fixed phase magnitudes.
        bus_types: IntVec = self.nc.bus_data.bus_types.copy()
        bus_types[self.positive_sequence.bus_idx] = BusMode.PQ_tpe.value
        vd, pq, pv, pqv, p, no_slack = compile_types(
            Pbus=S0.real,
            types=bus_types
        )

        self.vd = expand_slice_indices_3ph(vd, self.bus_lookup)
        self.pq = expand_slice_indices_3ph(pq, self.bus_lookup)
        self.pv = expand_slice_indices_3ph(pv, self.bus_lookup)
        self.pqv = expand_slice_indices_3ph(pqv, self.bus_lookup)
        self.p = expand_slice_indices_3ph(p, self.bus_lookup)
        self.no_slack = expand_slice_indices_3ph(no_slack, self.bus_lookup)

        self.idx_dVa = np.r_[self.pv, self.pq, self.pqv, self.p]
        self.idx_dVm = np.r_[self.pq, self.p]
        self.idx_dP = self.idx_dVa
        self.idx_dQ = np.r_[self.pq, self.pqv]

        self.common_mode: CommonModeControl = CommonModeControl(
            nc, self.full_admittances, self.bus_lookup, self.idx_dP, self.idx_dQ, self.positive_sequence)

    def x2var(self, x: Vec) -> None:
        """
        Convert X to decision variables
        :param x: solution vector
        """
        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)

        # update the vectors
        self.Va[self.idx_dVa] = x[0:a]
        self.Vm[self.idx_dVm] = x[a:b]
        self.positive_sequence.q[:] = x[b:]

    def var2x(self) -> Vec:
        """
        Convert the internal decision variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Va[self.idx_dVa],
            self.Vm[self.idx_dVm],
            self.positive_sequence.q
        ]

    def update_bus_types(self, pq: IntVec, pv: IntVec, pqv: IntVec, p: IntVec) -> None:
        """

        :param pq:
        :param pv:
        :param pqv:
        :param p:
        :return:
        """
        self.pq = pq
        self.pv = pv
        self.pqv = pqv
        self.p = p

        self.idx_dVa = np.r_[self.pv, self.pq, self.pqv, self.p]
        self.idx_dVm = np.r_[self.pq, self.p]
        self.idx_dP = self.idx_dVa
        self.idx_dQ = np.r_[self.pq, self.pqv]

        self.common_mode = CommonModeControl(
            self.nc, self.full_admittances, self.bus_lookup, self.idx_dP, self.idx_dQ, self.positive_sequence)

    def size(self) -> int:
        """
        Size of the jacobian matrix
        :return:
        """
        return len(self.idx_dVa) + len(self.idx_dVm) + len(self.positive_sequence.q)

    def generator_currents(self, voltage: CxVec, q: Vec) -> CxVec:
        """Combine legacy injections and U1 sources with their passive sequence responses.

        :param voltage: Retained phase voltages in pu.
        :param q: U1 regulator reactive powers in system pu.
        :return: Generator currents in MW / pu voltage.
        """
        regular: IntVec = self.positive_sequence.regular_idx
        asynchronous: IntVec = regular[
            self.nc.generator_data.tpe_int[regular] == GeneratorType.Asynchronous.idx()]
        regular = regular[self.nc.generator_data.tpe_int[regular] != GeneratorType.Asynchronous.idx()]
        currents: CxVec = compute_generators(
            bus_idx=self.nc.generator_data.bus_idx[regular],
            bus_lookup=self.bus_lookup,
            V=voltage,
            P=self.nc.generator_data.p[regular],
            Q=self.nc.generator_data.q[regular],
            control_mode_int=self.nc.generator_data.control_mode_int[regular]
        )
        # Asynchronous machines replace the fixed PQ injection, including on a
        # bus shared with a voltage regulator. Their reactive power is not a setpoint.
        gen: int
        for gen in asynchronous:
            phases: IntVec = self.bus_lookup[4 * self.nc.generator_data.bus_idx[gen] + np.array((1, 2, 3))]
            if np.any(phases < 0):
                raise ValueError('Asynchronous generator requires all three phases: '
                                 + str(self.nc.generator_data.names[gen]))
            else:
                pass
            y0: complex = 0j
            connection: int = self.nc.generator_data.conn[gen]
            if connection == ShuntConnectionType.GroundedStar.idx():
                z0: complex = complex(self.nc.generator_data.r0[gen], self.nc.generator_data.x0[gen])
                if not np.isfinite(z0) or abs(z0) < 1e-12:
                    raise ValueError('Asynchronous generator Z0 must be finite and nonzero for Yg: '
                                     + str(self.nc.generator_data.names[gen]) + '. Check R0/X0 and grounding data.')
                else:
                    # R0/X0 use the system base; the equivalent uses the machine base.
                    y0 = self.nc.Sbase / (self.nc.generator_data.snom[gen] * z0)
            elif connection in (ShuntConnectionType.Delta.idx(), ShuntConnectionType.FloatingStar.idx()):
                pass
            else:
                raise ValueError('Asynchronous generator with an explicit neutral is not supported in ABC: '
                                 + str(self.nc.generator_data.names[gen]))
            try:
                currents[phases] += asynchronous_gen_currents(
                    voltage=voltage[phases], Rs=self.nc.generator_data.Rs[gen],
                    Xs=self.nc.generator_data.Xs[gen], Xm=self.nc.generator_data.Xm[gen],
                    Rr=self.nc.generator_data.Rr[gen], Xr=self.nc.generator_data.Xr[gen],
                    P=self.nc.generator_data.p[gen], Sr=self.nc.generator_data.snom[gen], y0=y0)
            except ValueError as error:
                raise ValueError(str(self.nc.generator_data.names[gen]) + ': ' + str(error)) from error
        self.positive_sequence.add_currents(currents, voltage, q)
        return currents

    def compute_f(self, x: Vec) -> Vec:
        """
        Compute the function residual
        :param x: Solution vector
        :return: f
        """

        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)

        # copy the sliceable vectors
        Va = self.Va.copy()
        Vm = self.Vm.copy()

        # update the vectors
        Va[self.idx_dVa] = x[0:a]
        Vm[self.idx_dVm] = x[a:b]

        V = polar_to_rect(Vm, Va)

        # compute the function residual
        # Assumes the internal vars were updated already with self.x2var()

        Igen = self.generator_currents(V, x[b:])

        (Ipower,
         Y_power_linear,
         self.Un_floating_power) = compute_power_loads(
            bus_idx=self.nc.load_data.bus_idx,
            bus_lookup=self.bus_lookup,
            V=V,
            Sstar=self.nc.load_data.S3_star,
            Sfloating=self.nc.load_data.S3_floatingstar,
            Sdelta=self.nc.load_data.S3_delta
        )

        (Icurrent,
         Y_current_linear,
         self.Un_floating_current) = compute_current_loads(
            bus_idx=self.nc.load_data.bus_idx,
            bus_lookup=self.bus_lookup,
            V=V,
            Istar=self.nc.load_data.I3_star,
            Idelta=self.nc.load_data.I3_delta,
            Ifloating=self.nc.load_data.I3_floatingstar
        )

        Ibus = (Igen + Ipower + Icurrent) / (self.nc.Sbase / 3) / (V / np.abs(V))
        Icalc = compute_current(self.Ybus, V) / (V / np.abs(V))

        dI = (Icalc - Ibus)  # compute the mismatch
        _f = np.r_[
            dI[self.idx_dP].real,
            dI[self.idx_dQ].imag,
            self.positive_sequence.residual(V, x[b:])
        ]

        self.common_mode.apply(V, _f)
        return _f

    def check_error(self, x: Vec) -> Tuple[float, Vec]:
        """
        Check error of the solution without affecting the problem
        :param x: Solution vector
        :return: error
        """
        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)

        # update the vectors
        Va = self.Va.copy()
        Vm = self.Vm.copy()
        Va[self.idx_dVa] = x[0:a]
        Vm[self.idx_dVm] = x[a:b]

        # compute the complex voltage
        V = polar_to_rect(Vm, Va)

        # compute the function residual
        # Assumes the internal vars were updated already with self.x2var()

        Igen = self.generator_currents(V, x[b:])

        (Ipower,
         Y_power_linear,
         self.Un_floating_power) = compute_power_loads(bus_idx=self.nc.load_data.bus_idx,
                                                       bus_lookup=self.bus_lookup,
                                                       V=V,
                                                       Sstar=self.nc.load_data.S3_star,
                                                       Sfloating=self.nc.load_data.S3_floatingstar,
                                                       Sdelta=self.nc.load_data.S3_delta)

        (Icurrent,
         Y_current_linear,
         self.Un_floating_current) = compute_current_loads(bus_idx=self.nc.load_data.bus_idx,
                                                           bus_lookup=self.bus_lookup,
                                                           V=V,
                                                           Istar=self.nc.load_data.I3_star,
                                                           Idelta=self.nc.load_data.I3_delta,
                                                           Ifloating=self.nc.load_data.I3_floatingstar)

        Ibus = (Igen + Ipower + Icurrent) / (self.nc.Sbase / 3) / (V / np.abs(V))
        Icalc = compute_current(self.Ybus, V) / (V / np.abs(V))

        # print('\nIbus =', abs(Ibus))
        # print('Icalc =', abs(Icalc))

        dI = (Icalc - Ibus)  # compute the mismatch
        _f = np.r_[
            dI[self.idx_dP].real,
            dI[self.idx_dQ].imag,
            self.positive_sequence.residual(V, x[b:])
        ]

        # compute the error
        original_error: float = compute_fx_error(_f)
        self.common_mode.apply(V, _f)
        return max(original_error, compute_fx_error(_f)), x

    def update(self, x: Vec, update_controls: bool = False) -> Tuple[float, bool, Vec, Vec]:
        """
        Update step
        :param x: Solution vector
        :param update_controls:
        :return: error, converged?, x
        """
        # set the problem state
        self.x2var(x)

        # compute the complex voltage
        self.V = polar_to_rect(self.Vm, self.Va)

        # compute the function residual
        # Assumes the internal vars were updated already with self.x2var()

        Igen = self.generator_currents(self.V, self.positive_sequence.q)

        (Ipower,
         Y_power_linear,
         self.Un_floating_power) = compute_power_loads(bus_idx=self.nc.load_data.bus_idx,
                                                       bus_lookup=self.bus_lookup,
                                                       V=self.V,
                                                       Sstar=self.nc.load_data.S3_star,
                                                       Sfloating=self.nc.load_data.S3_floatingstar,
                                                       Sdelta=self.nc.load_data.S3_delta)

        (Icurrent,
         Y_current_linear,
         self.Un_floating_current) = compute_current_loads(bus_idx=self.nc.load_data.bus_idx,
                                                           bus_lookup=self.bus_lookup,
                                                           V=self.V,
                                                           Istar=self.nc.load_data.I3_star,
                                                           Idelta=self.nc.load_data.I3_delta,
                                                           Ifloating=self.nc.load_data.I3_floatingstar)

        Ibus = (Igen + Ipower + Icurrent) / (self.nc.Sbase / 3) / (self.V / np.abs(self.V))
        Icalc = compute_current(self.Ybus, self.V) / (self.V / np.abs(self.V))
        self.Scalc = compute_power(self.Ybus, self.V)

        dI = (Icalc - Ibus)  # compute the mismatch
        self._f = np.r_[
            dI[self.idx_dP].real,
            dI[self.idx_dQ].imag,
            self.positive_sequence.residual(self.V, self.positive_sequence.q)
        ]

        # Keep every original KCL/control equation in the convergence check. A reference
        # must never hide an incompatible injection in the replaced equation.
        original_error: float = compute_fx_error(self._f)
        self.common_mode.apply(self.V, self._f)
        self._error = max(original_error, compute_fx_error(self._f))

        # review reactive power limits
        # it is only worth checking Q limits with a low error
        # since with higher errors, the Q values may be far from realistic
        # finally, the Q control only makes sense if there are pv nodes
        if update_controls and self._error < self._controls_tol:
            if self.options.control_Q:
                any_change = self.positive_sequence.enforce_limits()
            else:
                any_change = False

            # update Q limits control
            if self.options.control_Q and (len(self.pv) + len(self.p)) > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(self.Scalc,
                                                                  self.S0,  # TODO:  attribute defined outside __init__
                                                                  self.pv, self.pq,
                                                                  self.pqv, self.p,
                                                                  self.Qmin,
                                                                  self.Qmax)

                if len(changed) > 0:
                    any_change = True

                    # update the bus type lists
                    self.update_bus_types(pq=pq, pv=pv, pqv=pqv, p=p)

                    # the composition of x may have changed, so recompute
                    x = self.var2x()

            # update Slack control
            if self.options.distributed_slack:
                ok, delta = compute_slack_distribution(Scalc=self.Scalc,
                                                       vd=self.vd,
                                                       bus_installed_power=expand3ph(self.nc.bus_data.installed_power)[
                                                           self.mask])
                if ok:
                    any_change = True
                    # Update the objective power to reflect the slack distribution
                    self.S0 += delta  # TODO:  attribute defined outside __init__

            if any_change:
                # recompute the error based on the new Scalc and S0
                self._f = self.fx()

                # compute the error
                self._error, _ = self.check_error(x)

        # converged?
        self._converged = self._error < self.options.tolerance

        return self._error, self._converged, x, self.f

    def fx(self) -> Vec:
        """
        # Scalc = V · (Y x V - I)^*
        # Sbus = S0 + I0*Vm + Y0*Vm^2
        :return:
        """

        # NOTE: Assumes the internal vars were updated already with self.x2var()

        Igen = self.generator_currents(self.V, self.positive_sequence.q)

        Ipower, Y_power_linear, self.Un_floating_power = compute_power_loads(bus_idx=self.nc.load_data.bus_idx,
                                                                             bus_lookup=self.bus_lookup,
                                                                             V=self.V,
                                                                             Sstar=self.nc.load_data.S3_star,
                                                                             Sfloating=self.nc.load_data.S3_floatingstar,
                                                                             Sdelta=self.nc.load_data.S3_delta)

        Icurrent, Y_current_linear, self.Un_floating_current = compute_current_loads(bus_idx=self.nc.load_data.bus_idx,
                                                                                     bus_lookup=self.bus_lookup,
                                                                                     V=self.V,
                                                                                     Istar=self.nc.load_data.I3_star,
                                                                                     Idelta=self.nc.load_data.I3_delta,
                                                                                     Ifloating=self.nc.load_data.I3_floatingstar)

        Ibus = (Igen + Ipower + Icurrent) / (self.nc.Sbase / 3) / (self.V / np.abs(self.V))
        Icalc = compute_current(self.Ybus, self.V) / (self.V / np.abs(self.V))

        self._f = np.r_[compute_fx(Icalc, Ibus, self.idx_dP, self.idx_dQ),
                        self.positive_sequence.residual(self.V, self.positive_sequence.q)]

        self.common_mode.apply(self.V, self._f)
        return self._f

    def Jacobian(self, autodiff: bool = True) -> CSC:
        """
        :param autodiff: If True, use autodiff to compute the Jacobian

        :return:
        """

        # Assumes the internal vars were updated already with self.x2var()
        if self.Ybus.format != 'csc':
            self.Ybus = self.Ybus.tocsc()

        if autodiff or len(self.positive_sequence.q) > 0 or len(self.common_mode.phases) > 0:
            J = calc_autodiff_jacobian(func=self.compute_f,
                                       x=self.var2x(),
                                       h=1e-8)

            return J

        else:
            nbus = self.Ybus.shape[0]

            # Create J in CSC order
            J = create_J_vc_csc(nbus, self.Ybus.data, self.Ybus.indptr, self.Ybus.indices,
                                self.V, self.idx_dVa, self.idx_dVm, self.idx_dP, self.idx_dQ)

        return J

    def get_x_names(self) -> List[str]:
        """
        Names matching x
        :return:
        """
        cols = [f'dVa {i}' for i in self.idx_dVa]
        cols += [f'dVm {i}' for i in self.idx_dVm]
        cols += [f'Q U1 bus {i}' for i in self.positive_sequence.bus_idx]

        return cols

    def get_fx_names(self) -> List[str]:
        """
        Names matching fx
        :return:
        """
        rows = [f'dP {i}' for i in self.idx_dP]
        rows += [f'dQ {i}' for i in self.idx_dQ]
        rows += [f'U1 or Q limit bus {i}' for i in self.positive_sequence.bus_idx]

        return rows

    def get_solution(self, elapsed: float, iterations: int) -> NumericPowerFlowResults:
        """
        Get the problem solution
        :param elapsed: Elapsed seconds
        :param iterations: Iteration number
        :return: NumericPowerFlowResults
        """
        # Reconstruct passive neutrals before the existing full-network post-processing.
        ybus, yf, yt, ysh, mask, lookup, branch_lookup = self.full_admittances
        voltage: CxVec = self.V
        floating: CxVec = self.Un_floating_current + self.Un_floating_power
        if self.voltage_lift is not None:
            voltage = self.voltage_lift @ self.V
            floating = np.zeros(len(voltage), dtype=complex)
            floating[self.retained] = self.Un_floating_current + self.Un_floating_power
        else:
            pass
        # Compute the Branches power and the slack buses power
        Sf, St, If, It, Vbranch, loading, losses, Sbus, V_expanded = power_flow_post_process_nonlinear_3ph(
            Sbus=self.Scalc,
            V=voltage,
            Vn_floating=floating,
            F=expand_indices_3ph(self.nc.passive_branch_data.F),
            T=expand_indices_3ph(self.nc.passive_branch_data.T),
            pv=self.retained[self.pv],
            vd=self.retained[self.vd],
            Ybus=ybus,
            Yf=yf,
            Yt=yt,
            Yshunt_bus=ysh,
            branch_rates=expand3ph(self.nc.passive_branch_data.rates),
            Sbase=self.nc.Sbase,
            bus_lookup=lookup,
            branch_lookup=branch_lookup
        )

        return NumericPowerFlowResults(
            V=V_expanded,
            Scalc=Sbus * (self.nc.Sbase / 3),
            m=np.ones(3 * self.nc.nbr, dtype=float),
            tau=np.zeros(3 * self.nc.nbr, dtype=float),
            Sf=Sf,
            St=St,
            If=If,
            It=It,
            loading=loading,
            losses=losses,
            Pfp_vsc=np.zeros(self.nc.nvsc, dtype=float),
            Pfn_vsc=np.zeros(self.nc.nvsc, dtype=float),
            St_vsc=np.zeros(3 * self.nc.nvsc, dtype=complex),
            If_vsc=np.zeros(self.nc.nvsc, dtype=float),
            It_vsc=np.zeros(3 * self.nc.nvsc, dtype=complex),
            losses_vsc=np.zeros(self.nc.nvsc, dtype=float),
            loading_vsc=np.zeros(self.nc.nvsc, dtype=float),
            Sf_hvdc=np.zeros(3 * self.nc.nhvdc, dtype=complex),
            St_hvdc=np.zeros(3 * self.nc.nhvdc, dtype=complex),
            losses_hvdc=np.zeros(self.nc.nhvdc, dtype=complex),
            loading_hvdc=np.zeros(self.nc.nhvdc, dtype=complex),
            norm_f=self.error,
            converged=self.converged,
            iterations=iterations,
            elapsed=elapsed
        )
