# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple, List, Callable
import numba as nb
import numpy as np
from scipy.sparse import lil_matrix, csc_matrix
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.Derivatives.ac_jacobian import create_J_vc_csc
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (
    compute_fx_error, power_flow_post_process_nonlinear_3ph
)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_inside_method,
                                                                                     compute_slack_distribution)
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                    compute_fx, polar_to_rect,
                                                                                    fortescue_012_to_abc)
from VeraGridEngine.Topology.simulation_indices import compile_types
from VeraGridEngine.basic_structures import Vec, IntVec, CxVec, CxMat, BoolVec, Logger
from VeraGridEngine.Utils.Sparse.csc2 import (CSC, scipy_to_mat)


# @nb.njit(cache=True)
def lookup_from_mask(mask: BoolVec) -> IntVec:
    """

    :param mask:
    :return:
    """
    lookup = [-1] * len(mask)  # start with all -1
    # lookup = np.full(len(mask), -1, dtype=int)  # TODO: investigate why this change breaks the code
    counter = 0
    for i, m in enumerate(mask):
        if m:
            lookup[i] = counter
            counter += 1

    return lookup


def compute_ybus_generator(nc: NumericalCircuit) -> Tuple[csc_matrix, CxMat]:
    """
    Compute the Ybus matrix for a generator in a 3-phase system
    :param nc: NumericalCircuit
    :return: Ybus
    """

    n = nc.bus_data.nbus
    m = nc.generator_data.nelm

    Ybus_gen = lil_matrix((3 * n, 3 * n), dtype=complex)
    idx3 = np.array([0, 1, 2])
    Yzeros = np.zeros((3 * n, 3 * n), dtype=complex)

    for k in range(m):
        f = nc.generator_data.bus_idx[k]
        f3 = 3 * f + idx3

        # r0 = nc.generator_data.r0[k] * 2.0
        # x0 = nc.generator_data.x0[k] * 2.0
        # r1 = nc.generator_data.r1[k] * 2.0
        # x1 = nc.generator_data.x1[k] * 2.0
        # r2 = nc.generator_data.r2[k] * 2.0
        # x2 = nc.generator_data.x2[k] * 2.0

        r0 = nc.generator_data.r0[k] * 1.0
        x0 = nc.generator_data.x0[k] * 1.0
        r1 = nc.generator_data.r1[k] * 1.0
        x1 = nc.generator_data.x1[k] * 1.0
        r2 = nc.generator_data.r2[k] * 1.0
        x2 = nc.generator_data.x2[k] * 1.0

        # Fortescue
        Zabc = fortescue_012_to_abc(r0 + 1j * x0, r1 + 1j * x1, r2 + 1j * x2)
        Yabc = np.linalg.inv(Zabc)
        Ybus_gen[np.ix_(f3, f3)] = Yabc
        Yzeros[np.ix_(f3, f3)] = Yabc

    return Ybus_gen.tocsc(), Yzeros


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
    Cf = lil_matrix((3 * m, 3 * n), dtype=int)
    Ct = lil_matrix((3 * m, 3 * n), dtype=int)
    Yf = lil_matrix((3 * m, 3 * n), dtype=complex)
    Yt = lil_matrix((3 * m, 3 * n), dtype=complex)

    idx3 = np.array([0, 1, 2])  # array that we use to generate the 3-phase indices

    R = np.zeros(3 * m, dtype=bool)

    for k in range(m):
        f = nc.passive_branch_data.F[k]
        t = nc.passive_branch_data.T[k]

        f3 = 3 * f + idx3
        t3 = 3 * t + idx3
        k3 = 3 * k + idx3

        Yf[np.ix_(k3, f3)] = nc.passive_branch_data.Yff3[k3, :]
        Yf[np.ix_(k3, t3)] = nc.passive_branch_data.Yft3[k3, :]
        Yt[np.ix_(k3, f3)] = nc.passive_branch_data.Ytf3[k3, :]
        Yt[np.ix_(k3, t3)] = nc.passive_branch_data.Ytt3[k3, :]

        R[3 * k + 0] = nc.passive_branch_data.phA[k]
        R[3 * k + 1] = nc.passive_branch_data.phB[k]
        R[3 * k + 2] = nc.passive_branch_data.phC[k]

        Cf[k3, f3] = 1
        Ct[k3, t3] = 1

    zero_mask = (R == 0)
    Cfcopy = Cf.copy()
    Ctcopy = Ct.copy()

    Cfcopy[zero_mask, :] = 0
    Ctcopy[zero_mask, :] = 0

    Ctot = Cfcopy + Ctcopy
    col_sums = np.array(Ctot.sum(axis=0))[0, :]
    binary_bus_mask = (col_sums > 0).astype(bool)

    Ysh_bus = np.zeros((n * 3, n * 3), dtype=complex)
    for k in range(nc.shunt_data.nelm):
        f = nc.shunt_data.bus_idx[k]
        k3 = 3 * k + idx3
        f3 = 3 * f + idx3
        Ysh_bus[np.ix_(f3, f3)] += nc.shunt_data.Y3_star[np.ix_(k3, idx3)] / (nc.Sbase / 3)

    for k in range(nc.load_data.nelm):
        f = nc.load_data.bus_idx[k]
        k3 = 3 * k + idx3
        f3 = 3 * f + idx3
        Ysh_bus[np.ix_(f3, f3)] += nc.load_data.Y3_star[np.ix_(k3, idx3)] / (nc.Sbase / 3)

    Ybus = Cf.T @ Yf + Ct.T @ Yt + Ysh_bus
    Ybus = Ybus[binary_bus_mask, :][:, binary_bus_mask]
    Ysh_bus = Ysh_bus[binary_bus_mask]
    Yf = Yf[R, :][:, binary_bus_mask]
    Yt = Yt[R, :][:, binary_bus_mask]

    bus_idx_lookup = lookup_from_mask(binary_bus_mask)
    branch_lookup = lookup_from_mask(R)

    Ybus = csc_matrix(Ybus)

    return Ybus.tocsc(), Yf.tocsc(), Yt.tocsc(), Ysh_bus, binary_bus_mask, bus_idx_lookup, branch_lookup


def compute_Ibus(nc: NumericalCircuit) -> CxVec:
    """
    Compute the Ibus vector
    :param nc:
    :return:
    """
    n = nc.bus_data.nbus
    idx3 = np.array([0, 1, 2])
    Ibus = np.zeros(n * 3, dtype=complex)

    for k in range(nc.load_data.nelm):
        f = nc.load_data.bus_idx[k]
        k3 = 3 * k + idx3
        f3 = 3 * f + idx3
        Ibus[f3] -= nc.load_data.I3_star[k3] * nc.load_data.active[k]

    return Ibus


def compute_Sbus_star(nc: NumericalCircuit, V: CxVec, mask) -> Tuple[CxVec, CxVec]:
    """
    Compute the Ibus vector
    :param nc:
    :param V:
    :param mask:
    :return:
    """
    n = nc.bus_data.nbus
    idx3 = np.array([0, 1, 2])
    Sbus = np.zeros(n * 3, dtype=complex)

    for k in range(nc.load_data.nelm):
        f = nc.load_data.bus_idx[k]
        k3 = 3 * k + idx3
        f3 = 3 * f + idx3
        Sbus[f3] -= nc.load_data.S3_star[k3] * nc.load_data.active[k]

    # Y_power_star_linear = np.conj(Sbus[mask]) / np.power(np.abs(V), 2)
    Y_power_star_linear = np.conj(Sbus[mask]) / np.abs(V) ** 2

    return Sbus, Y_power_star_linear


@nb.njit(cache=True)
def compute_current_loads(bus_idx: IntVec,
                          bus_lookup: IntVec,
                          V: CxVec,
                          Istar: CxVec,
                          Idelta: CxVec) -> Tuple[CxVec, CxVec]:
    """

    :param bus_idx:
    :param bus_lookup:
    :param V:
    :param Istar:
    :param Idelta:
    :return:
    """
    n = len(V)
    nelm = len(bus_idx)
    I = np.zeros(n, dtype=nb.complex128)

    zero_load = 0.0 + 0.0j

    for k in range(nelm):

        f = bus_idx[k]

        a = 3 * f + 0
        b = 3 * f + 1
        c = 3 * f + 2

        ab = 3 * k + 0
        bc = 3 * k + 1
        ca = 3 * k + 2

        a2 = bus_lookup[a]
        b2 = bus_lookup[b]
        c2 = bus_lookup[c]

        delta = (Idelta[ab] != zero_load or Idelta[bc] != zero_load or Idelta[ca] != zero_load)
        star = (Istar[ab] != zero_load or Istar[bc] != zero_load or Istar[ca] != zero_load)

        ab_connected = (Idelta[ab] != zero_load)
        bc_connected = (Idelta[bc] != zero_load)
        ca_connected = (Idelta[ca] != zero_load)

        a_connected = (Istar[ab] != zero_load)
        b_connected = (Istar[bc] != zero_load)
        c_connected = (Istar[ca] != zero_load)

        if delta and ab_connected and bc_connected and ca_connected:
            voltage_angle_ab = np.angle(V[a2] - V[b2])
            voltage_angle_bc = np.angle(V[b2] - V[c2])
            voltage_angle_ca = np.angle(V[c2] - V[a2])

            I[a2] += -np.conj(Idelta[ab]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle_ab)
            I[b2] += np.conj(Idelta[ab]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle_ab)

            I[b2] += -np.conj(Idelta[bc]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle_bc)
            I[c2] += np.conj(Idelta[bc]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle_bc)

            I[c2] += -np.conj(Idelta[ca]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle_ca)
            I[a2] += np.conj(Idelta[ca]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle_ca)

        elif delta and ab_connected:
            voltage_angle = np.angle(V[a2] - V[b2])
            I[a2] += -np.conj(Idelta[ab]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle)
            I[b2] += np.conj(Idelta[ab]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle)

        elif delta and bc_connected:
            voltage_angle = np.angle(V[b2] - V[c2])
            I[b2] += -np.conj(Idelta[bc]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle)
            I[c2] += np.conj(Idelta[bc]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle)

        elif delta and ca_connected:
            voltage_angle = np.angle(V[c2] - V[a2])
            I[c2] += -np.conj(Idelta[ca]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle)
            I[a2] += np.conj(Idelta[ca]) / (np.sqrt(3)) * 1 * np.exp(1j * voltage_angle)

        elif star and a_connected and b_connected and c_connected:
            voltage_angle_a = np.angle(V[a2])
            voltage_angle_b = np.angle(V[b2])
            voltage_angle_c = np.angle(V[c2])
            I[a2] += -np.conj(Istar[ab]) * 1 * np.exp(1j * voltage_angle_a)
            I[b2] += -np.conj(Istar[bc]) * 1 * np.exp(1j * voltage_angle_b)
            I[c2] += -np.conj(Istar[ca]) * 1 * np.exp(1j * voltage_angle_c)

        elif star and a_connected:
            voltage_angle = np.angle(V[a2])
            I[a2] += -np.conj(Istar[ab]) * 1 * np.exp(1j * voltage_angle)

        elif star and b_connected:
            voltage_angle = np.angle(V[b2])
            I[b2] += -np.conj(Istar[bc]) * 1 * np.exp(1j * voltage_angle)

        elif star and c_connected:
            voltage_angle = np.angle(V[c2])
            I[c2] += -np.conj(Istar[ca]) * 1 * np.exp(1j * voltage_angle)

        else:
            # raise ValueError('Incorrect current load definition')
            pass

    Y_current_linear = I / V

    return I, Y_current_linear


@nb.njit(cache=True)
def compute_Sbus_delta(bus_idx: IntVec,
                       Sdelta: CxVec,
                       Ydelta: CxVec,
                       V: CxVec,
                       bus_lookup: IntVec) -> Tuple[CxVec, CxVec]:
    """

    :param bus_idx:
    :param Sdelta:
    :param Ydelta:
    :param V:
    :param bus_lookup:
    :return:
    """
    n = len(V)
    nelm = len(bus_idx)
    S = np.zeros(n, dtype=nb.complex128)
    for k in range(nelm):
        f = bus_idx[k]

        a = 3 * f + 0
        b = 3 * f + 1
        c = 3 * f + 2

        ab = 3 * k + 0
        bc = 3 * k + 1
        ca = 3 * k + 2

        a2 = bus_lookup[a]
        b2 = bus_lookup[b]
        c2 = bus_lookup[c]

        # ab2 = bus_lookup[ab]
        # bc2 = bus_lookup[bc]
        # ca2 = bus_lookup[ca]

        ab_connected = (Sdelta[ab] != 0.0 + 0.0j or Ydelta[ab] != 0.0 + 0.0j)
        bc_connected = (Sdelta[bc] != 0.0 + 0.0j or Ydelta[bc] != 0.0 + 0.0j)
        ca_connected = (Sdelta[ca] != 0.0 + 0.0j or Ydelta[ca] != 0.0 + 0.0j)

        if ab_connected and bc_connected and ca_connected:
            if a2 > -1 and b2 > -1 and c2 > -1:
                S[a2] = -1 * ((V[a2] * Sdelta[ab]) / (V[a2] - V[b2]) - (V[a2] * Sdelta[ca]) / (V[c2] - V[a2]))
                S[b2] = -1 * ((V[b2] * Sdelta[bc]) / (V[b2] - V[c2]) - (V[b2] * Sdelta[ab]) / (V[a2] - V[b2]))
                S[c2] = -1 * ((V[c2] * Sdelta[ca]) / (V[c2] - V[a2]) - (V[c2] * Sdelta[bc]) / (V[b2] - V[c2]))
            else:
                raise Exception('Incorrect load phasing, non-existing phases for this load')

        elif ab_connected:
            if a2 > -1 and b2 > -1:
                S[a2] = -1 * V[a2] * Sdelta[ab] / (V[a2] - V[b2])
                S[b2] = -1 * V[b2] * Sdelta[ab] / (V[b2] - V[a2])

                # Admittance
                S[a2] += -1 * V[a2] * np.conj((V[a2] - V[b2]) * Ydelta[ab] / 3)
                S[b2] += -1 * V[b2] * np.conj((V[b2] - V[a2]) * Ydelta[ab] / 3)
            else:
                raise Exception('Incorrect load phasing, non-existing phases for this load')

        elif bc_connected:
            if b2 > -1 and c2 > -1:
                S[b2] = -1 * V[b2] * Sdelta[bc] / (V[b2] - V[c2])
                S[c2] = -1 * V[c2] * Sdelta[bc] / (V[c2] - V[b2])

                # Admittance
                S[b2] += -1 * V[b2] * np.conj((V[b2] - V[c2]) * Ydelta[bc] / 3)
                S[c2] += -1 * V[c2] * np.conj((V[c2] - V[b2]) * Ydelta[bc] / 3)
            else:
                raise Exception('Incorrect load phasing, non-existing phases for this load')

        elif ca_connected:
            if c2 > -1 and a2 > -1:
                S[c2] = -1 * V[c2] * Sdelta[ca] / (V[c2] - V[a2])
                S[a2] = -1 * V[a2] * Sdelta[ca] / (V[a2] - V[c2])

                # Admittance
                S[c2] += -1 * V[c2] * np.conj((V[c2] - V[a2]) * Ydelta[ca] / 3)
                S[a2] += -1 * V[a2] * np.conj((V[a2] - V[c2]) * Ydelta[ca] / 3)
            else:
                raise Exception('Incorrect load phasing, non-existing phases for this load')

    Y_power_delta_linear = np.conj(S) / np.pow(np.abs(V), 2)

    return S, Y_power_delta_linear


def calc_autodiff_jacobian(func: Callable[[Vec], Vec], x: Vec, h=1e-6) -> CSC:
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


@nb.njit(cache=True)
def expand3ph(x: np.ndarray):
    """
    Expands a numpy array to 3-pase copying the same values
    :param x:
    :return:
    """
    n = len(x)
    idx3 = np.array([0, 1, 2])
    x3 = np.zeros(3 * n, dtype=x.dtype)

    for k in range(n):
        x3[3 * k + idx3] = x[k]
    return x3


@nb.njit(cache=True)
def expand3phIndices(x: np.ndarray):
    """
    Expands a numpy array to 3-pase copying the same values
    :param x:
    :return:
    """
    n = len(x)
    idx3 = np.array([0, 1, 2])
    x3 = np.zeros(3 * n, dtype=x.dtype)

    for k in range(n):
        x3[3 * k + idx3] = 3 * x[k] + idx3
    return x3


def slice_indices(pq: IntVec, bus_lookup: IntVec) -> IntVec:
    """
    Slice the indices based on the bus_lookup
    :param pq: original bus indices
    :param bus_lookup: mapping between original and sliced bus indices
    :return:
    """

    max_nnz = len(pq)
    vec = np.zeros(max_nnz, dtype=int)

    counter = 0
    for pq_idx in pq:
        val = bus_lookup[pq_idx]
        if val > -1:
            vec[counter] = val
            counter += 1

    return vec[:counter]


def expand_indices_3ph(x: np.ndarray) -> np.ndarray:
    """
    Expands a numpy array to 3-pase copying the same values
    :param x:
    :return:
    """
    n = len(x)
    idx3 = np.array([0, 1, 2])
    x3 = np.zeros(3 * n, dtype=x.dtype)

    for k in range(n):
        x3[3 * k + idx3] = 3 * x[k] + idx3

    return x3


def expand_slice_indices_3ph(x: np.ndarray, bus_lookup: IntVec):
    """
    Expands and slices a numpy array to 3-phase copying the same values
    :param x:
    :param bus_lookup:
    :return:
    """
    x3 = expand_indices_3ph(x)

    x3_final = slice_indices(x3, bus_lookup)
    return np.sort(x3_final)


def expandVoltage3ph(V0: CxVec) -> CxVec:
    """
    Expands a numpy array to 3-pase copying the same values
    :param V0: array of bus voltages in positive sequence
    :return: Array of three-phase voltages in 3-phase ABC
    """
    n = len(V0)
    idx3 = np.array([0, 1, 2])
    angles = np.array([0, -2 * np.pi / 3, 2 * np.pi / 3])
    Vm = np.abs(V0)
    Va = np.angle(V0)
    x3 = np.zeros(3 * n, dtype=complex)

    for k in range(n):
        x3[3 * k + idx3] = Vm[k] * np.exp(1j * (Va[k] + angles))

    return x3


def expand_magnitudes(magnitude: CxVec, lookup: IntVec):
    """
    :param magnitude:
    :param lookup:
    :return:
    """
    n_buses_total = len(lookup)
    magnitude_expanded = np.zeros(n_buses_total, dtype=complex)
    for i, value in enumerate(lookup):
        if value < 0:
            magnitude_expanded[i] = 0.0 + 0.0j
        else:
            magnitude_expanded[i] = magnitude[value]

    return magnitude_expanded


def expand_matrix(magnitude: np.ndarray, lookup: IntVec):
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
    magnitude_expanded = np.zeros((n_buses_total, n_buses_total), dtype=complex)

    for i, value in enumerate(lookup):
        if value >= 0:
            # Assign the value from the original matrix to the expanded matrix
            magnitude_expanded[i, i] = magnitude[value, value]
        # Else, the row and column for that index will already be zeros by default.

    return magnitude_expanded


class PfBasicFormulation3Ph(PfFormulationTemplate):

    def __init__(self,
                 V0: CxVec,
                 S0: CxVec,
                 Qmin: Vec,
                 Qmax: Vec,
                 nc: NumericalCircuit,
                 options: PowerFlowOptions,
                 logger: Logger):
        """
        PfBasicFormulation3Ph
        :param V0: Array of nodal initial solution (3N)
        :param S0: Array of power injections (3N)
        :param Qmin: Array of bus reactive power upper limit (N, not 3N)
        :param Qmax: Array of bus reactive power lower limit (N, not 3N)
        :param nc: NumericalCircuit
        :param options: PowerFlowOptions
        """
        self.Ybus, self.Yf, self.Yt, self.Yshunt_bus, self.mask, self.bus_lookup, self.branch_lookup = compute_ybus(nc)
        V0new = V0[self.mask]

        PfFormulationTemplate.__init__(self, V0=V0new.astype(complex), options=options)
        self.logger = logger
        self.nc = nc

        self.S0, self.Y_power_star_linear = compute_Sbus_star(nc, V0new, self.mask)
        self.Y_power_star_linear: CxVec
        self.S0 = self.S0 / (nc.Sbase / 3)
        self.Y_power_star_linear = self.Y_power_star_linear / (nc.Sbase / 3)
        self.I0: CxVec = compute_Ibus(nc) / (nc.Sbase / 3)

        self.Qmin = expand3ph(Qmin)[self.mask] * 100e6
        self.Qmax = expand3ph(Qmax)[self.mask] * 100e6

        vd, pq, pv, pqv, p, no_slack = compile_types(
            Pbus=S0.real,
            types=self.nc.bus_data.bus_types
        )

        self.S0 = self.S0[self.mask]
        self.I0 = self.I0[self.mask]
        # self.V = self.V[self.mask]

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

    def x2var(self, x: Vec):
        """
        Convert X to decision variables
        :param x: solution vector
        """
        a = len(self.idx_dVa)
        b = a + len(self.idx_dVm)

        # update the vectors
        self.Va[self.idx_dVa] = x[0:a]
        self.Vm[self.idx_dVm] = x[a:b]

    def var2x(self) -> Vec:
        """
        Convert the internal decision variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Va[self.idx_dVa],
            self.Vm[self.idx_dVm]
        ]

    def update_bus_types(self, pq: IntVec, pv: IntVec, pqv: IntVec, p: IntVec):
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

    def size(self) -> int:
        """
        Size of the jacobian matrix
        :return:
        """
        return len(self.idx_dVa) + len(self.idx_dVm)

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
        Sdelta2star, Y_power_delta_linear = compute_Sbus_delta(bus_idx=self.nc.load_data.bus_idx,
                                                               Sdelta=self.nc.load_data.S3_delta,
                                                               Ydelta=self.nc.load_data.Y3_delta,
                                                               V=V,
                                                               bus_lookup=self.bus_lookup)

        I0, Y_current_linear = compute_current_loads(bus_idx=self.nc.load_data.bus_idx,
                                                     bus_lookup=self.bus_lookup,
                                                     V=self.V,
                                                     Istar=self.nc.load_data.I3_star,
                                                     Idelta=self.nc.load_data.I3_delta)

        self.I0 = I0 / (self.nc.Sbase / 3)
        self.Y_current_linear = Y_current_linear / (self.nc.Sbase / 3)

        Sbus = compute_zip_power(self.S0, self.I0, np.zeros(len(self.S0), dtype=complex), self.V) + Sdelta2star / (
                self.nc.Sbase / 3)
        Scalc = compute_power(self.Ybus, V)
        dS = Scalc - Sbus  # compute the mismatch
        _f = np.r_[
            dS[self.idx_dP].real,
            dS[self.idx_dQ].imag
        ]

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
        Sdelta2star, Y_power_delta_linear = compute_Sbus_delta(bus_idx=self.nc.load_data.bus_idx,
                                                               Sdelta=self.nc.load_data.S3_delta,
                                                               Ydelta=self.nc.load_data.Y3_delta,
                                                               V=V,
                                                               bus_lookup=self.bus_lookup)

        I0, Y_current_linear = compute_current_loads(bus_idx=self.nc.load_data.bus_idx,
                                                     bus_lookup=self.bus_lookup,
                                                     V=self.V,
                                                     Istar=self.nc.load_data.I3_star,
                                                     Idelta=self.nc.load_data.I3_delta)

        self.I0 = I0 / (self.nc.Sbase / 3)
        self.Y_current_linear = Y_current_linear / (self.nc.Sbase / 3)

        Sbus = compute_zip_power(self.S0, self.I0, np.zeros(len(self.S0), dtype=complex), self.V) + Sdelta2star / (
                self.nc.Sbase / 3)
        Scalc = compute_power(self.Ybus, V)
        dS = Scalc - Sbus  # compute the mismatch
        _f = np.r_[
            dS[self.idx_dP].real,
            dS[self.idx_dQ].imag
        ]

        # compute the error
        return compute_fx_error(_f), x

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
        Sdelta2star, Y_power_delta_linear = compute_Sbus_delta(bus_idx=self.nc.load_data.bus_idx,
                                                               Sdelta=self.nc.load_data.S3_delta,
                                                               Ydelta=self.nc.load_data.Y3_delta,
                                                               V=self.V,
                                                               bus_lookup=self.bus_lookup)

        I0, Y_current_linear = compute_current_loads(bus_idx=self.nc.load_data.bus_idx,
                                                     bus_lookup=self.bus_lookup,
                                                     V=self.V,
                                                     Istar=self.nc.load_data.I3_star,
                                                     Idelta=self.nc.load_data.I3_delta)

        self.I0 = I0 / (self.nc.Sbase / 3)
        self.Y_current_linear = Y_current_linear / (self.nc.Sbase / 3)

        Sbus = compute_zip_power(self.S0, self.I0, np.zeros(len(self.S0), dtype=complex), self.V) + Sdelta2star / (
                self.nc.Sbase / 3)
        self.Scalc = compute_power(self.Ybus, self.V)
        dS = self.Scalc - Sbus  # compute the mismatch
        self._f = np.r_[
            dS[self.idx_dP].real,
            dS[self.idx_dQ].imag
        ]
        # self._f = compute_fx(self.Scalc, Sbus, self.idx_dP, self.idx_dQ)
        Sbus_expanded = expand_magnitudes(Sbus, self.bus_lookup)
        # compute the error
        self._error = compute_fx_error(self._f)

        # review reactive power limits
        # it is only worth checking Q limits with a low error
        # since with higher errors, the Q values may be far from realistic
        # finally, the Q control only makes sense if there are pv nodes
        if update_controls and self._error < self._controls_tol:
            any_change = False

            # update Q limits control
            if self.options.control_Q and (len(self.pv) + len(self.p)) > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(self.Scalc, self.S0,
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
                                                       bus_installed_power=self.nc.bus_data.installed_power)
                if ok:
                    any_change = True
                    # Update the objective power to reflect the slack distribution
                    self.S0 += delta

            if any_change:
                # recompute the error based on the new Scalc and S0
                self._f = self.fx()

                # compute the error
                self._error = compute_fx_error(self._f)

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

        Sdelta2star, Y_power_delta_linear = compute_Sbus_delta(bus_idx=self.nc.load_data.bus_idx,
                                                               Sdelta=self.nc.load_data.S3_delta,
                                                               Ydelta=self.nc.load_data.Y3_delta,
                                                               V=self.V,
                                                               bus_lookup=self.bus_lookup)

        I0, Y_current_linear = compute_current_loads(bus_idx=self.nc.load_data.bus_idx,
                                                     bus_lookup=self.bus_lookup,
                                                     V=self.V,
                                                     Istar=self.nc.load_data.I3_star,
                                                     Idelta=self.nc.load_data.I3_delta)

        self.I0 = I0 / (self.nc.Sbase / 3)
        self.Y_current_linear = Y_current_linear / (self.nc.Sbase / 3)

        Sbus = compute_zip_power(self.S0, self.I0, np.zeros(len(self.S0), dtype=complex), self.V) + Sdelta2star / (
                self.nc.Sbase / 3)
        self.Scalc = self.V * np.conj(self.Ybus @ self.V - self.I0)

        self._f = compute_fx(self.Scalc, Sbus, self.idx_dP, self.idx_dQ)
        return self._f

    def Jacobian(self, autodiff: bool = False) -> CSC:
        """
        :param autodiff: If True, use autodiff to compute the Jacobian

        :return:
        """
        # Assumes the internal vars were updated already with self.x2var()
        if self.Ybus.format != 'csc':
            self.Ybus = self.Ybus.tocsc()

        if autodiff:
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

        return cols

    def get_fx_names(self) -> List[str]:
        """
        Names matching fx
        :return:
        """
        rows = [f'dP {i}' for i in self.idx_dP]
        rows += [f'dQ {i}' for i in self.idx_dQ]

        return rows

    def get_solution(self, elapsed: float, iterations: int) -> NumericPowerFlowResults:
        """
        Get the problem solution
        :param elapsed: Elapsed seconds
        :param iterations: Iteration number
        :return: NumericPowerFlowResults
        """
        # Compute the Branches power and the slack buses power
        Sf, St, If, It, Vbranch, loading, losses, Sbus, V_expanded = power_flow_post_process_nonlinear_3ph(
            Sbus=self.Scalc,
            V=self.V,
            F=expand_indices_3ph(self.nc.passive_branch_data.F),
            T=expand_indices_3ph(self.nc.passive_branch_data.T),
            pv=self.pv,
            vd=self.vd,
            Ybus=self.Ybus,
            Yf=self.Yf,
            Yt=self.Yt,
            Yshunt_bus=self.Yshunt_bus,
            branch_rates=expand3ph(self.nc.passive_branch_data.rates),
            Sbase=self.nc.Sbase,
            bus_lookup=self.bus_lookup,
            branch_lookup=self.branch_lookup
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
            Pf_vsc=np.zeros(self.nc.nvsc, dtype=float),
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
