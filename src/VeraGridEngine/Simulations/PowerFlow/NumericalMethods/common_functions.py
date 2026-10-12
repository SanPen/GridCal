# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numba as nb
import numpy as np
from scipy.sparse import csc_matrix
from VeraGridEngine.basic_structures import Vec, CxVec, IntVec, CscMat, CxMat, BoolVec
from VeraGridEngine.enumerations import GeneratorType
from VeraGridEngine.Utils.NumericalMethods.common import fortescue_012_to_abc
from typing import Tuple


def asynchronous_impedance(slip: float, Rs: float, Xs: float, Xm: float,
                          Rr: float, Xr: float) -> complex:
    """Return the existing single-cage equivalent on the machine base.

    :param slip: Sequence slip (s for positive sequence, 2-s for negative).
    :param Rs: Stator resistance in pu.
    :param Xs: Stator reactance in pu.
    :param Xm: Magnetising reactance in pu.
    :param Rr: Rotor resistance in pu.
    :param Xr: Rotor reactance in pu.
    :return: Terminal sequence impedance in pu.
    """
    zr: complex = Rr / slip + 1j * Xr
    zpar: complex = (1j * Xm * zr) / (1j * Xm + zr)
    return Rs + 1j * Xs + zpar


def active_power_mismatch(slip: float,
                          u: complex,
                          Rs: float,
                          Xs: float,
                          Xm: float,
                          Rr: float,
                          Xr: float,
                          P: float,
                          Sr: float) -> float:
    """

    :param slip:
    :param u:
    :param Rs:
    :param Xs:
    :param Xm:
    :param Rr:
    :param Xr:
    :param P:
    :param Sr:
    :return:
    """
    z: complex = asynchronous_impedance(slip, Rs, Xs, Xm, Rr, Xr)
    i: complex = u / z
    s: complex = -u * np.conj(i)
    return s.real - P / Sr


def solve_slip(f, a, b, tol, max_iter, u, Rs, Xs, Xm, Rr, Xr, P, Sr):
    """

    :param f:
    :param a:
    :param b:
    :param tol:
    :param max_iter:
    :param u:
    :param Rs:
    :param Xs:
    :param Xm:
    :param Rr:
    :param Xr:
    :param P:
    :param Sr:
    :return:
    """
    # TODO: Poner typos a todo y no usar punteros a funciones que no pintan nada
    fa = f(a, u, Rs, Xs, Xm, Rr, Xr, P, Sr)
    fb = f(b, u, Rs, Xs, Xm, Rr, Xr, P, Sr)

    if fa * fb > 0:
        raise ValueError("No sign change in interval.")

    for _ in range(max_iter):
        c = 0.5 * (a + b)
        fc = f(c, u, Rs, Xs, Xm, Rr, Xr, P, Sr)

        if abs(fc) < tol or abs(b - a) < tol:
            return c

        if fa * fc < 0:
            b = c
            fb = fc
        else:
            a = c
            fa = fc

    return 0.5 * (a + b)


def asynchronous_gen_q(u: complex,
                       Rs: float,
                       Xs: float,
                       Xm: float,
                       Rr: float,
                       Xr: float,
                       P: float,
                       Sr: float) -> float:
    """

    :param u:
    :param Rs:
    :param Xs:
    :param Xm:
    :param Rr:
    :param Xr:
    :param P:
    :param Sr:
    :return:
    """
    slip = solve_slip(f=active_power_mismatch,
                      a=-0.05, b=-1e-6, tol=1e-10, max_iter=200,
                      u=u, Rs=Rs, Xs=Xs, Xm=Xm, Rr=Rr, Xr=Xr, P=P, Sr=Sr)
    z: complex = asynchronous_impedance(slip, Rs, Xs, Xm, Rr, Xr)
    i = u / z
    s = -u * np.conj(i)
    return s.imag * Sr


def asynchronous_gen_currents(voltage: CxVec, Rs: float, Xs: float, Xm: float,
                              Rr: float, Xr: float, P: float, Sr: float,
                              y0: complex = 0j) -> CxVec:
    """Compute ABC injections with one slip and the existing single-cage model.

    :param voltage: Three phase-to-ground voltages in pu.
    :param Rs: Stator resistance in machine pu.
    :param Xs: Stator reactance in machine pu.
    :param Xm: Magnetising reactance in machine pu.
    :param Rr: Rotor resistance in machine pu.
    :param Xr: Rotor reactance in machine pu.
    :param P: Positive-sequence electrical active injection in MW, as in PF AS mode.
    :param Sr: Machine rated power in MVA.
    :param y0: Effective zero-sequence admittance in machine pu (zero for D/Y).
    :return: Phase current injections in MW / pu voltage, as used by the ABC residual.
    """
    if not np.all(np.isfinite((Rs, Xs, Xm, Rr, Xr, P, Sr, y0))) or Sr <= 0.0 or Xm <= 0.0 or Rr <= 0.0:
        raise ValueError('Asynchronous generator requires finite parameters, Snom > 0, Xm > 0 and Rr > 0.')
    else:
        pass
    rotation: CxVec = np.exp(-2j * np.pi / 3 * np.arange(3))
    u1: complex = voltage @ rotation.conj() / 3.0
    # Keep the established positive-sequence P/slip law. PF AS mode adds passive
    # negative/zero-sequence losses to the terminal power without redispatching P1.
    slip: float = solve_slip(f=active_power_mismatch, a=-0.05, b=-1e-6,
                             tol=1e-10, max_iter=200, u=u1, Rs=Rs, Xs=Xs, Xm=Xm,
                             Rr=Rr, Xr=Xr, P=P, Sr=Sr)
    z1: complex = asynchronous_impedance(slip, Rs, Xs, Xm, Rr, Xr)
    z2: complex = asynchronous_impedance(2.0-slip, Rs, Xs, Xm, Rr, Xr)
    # Fortescue preserves terminal coupling. This voltage-dependent injection is
    # evaluated in the residual, not added again as a constant Ybus shunt.
    return -(fortescue_012_to_abc(y0, 1.0/z1, 1.0/z2) @ voltage) * Sr / 3.0


def compute_asynchronous_generator_q(
        V: CxVec,
        gen_bus_idx: IntVec,
        gen_active: BoolVec,
        gen_types,
        Rs: Vec,
        Xs: Vec,
        Xm: Vec,
        Rr: Vec,
        Xr: Vec,
        P: Vec,
        Snom: Vec,
) -> Vec:
    """
    Compute the voltage-dependent reactive power of asynchronous generators.
    """
    q = np.zeros(len(gen_bus_idx), dtype=float)

    for gen_idx in range(len(gen_bus_idx)):
        bus_idx = gen_bus_idx[gen_idx]
        if gen_active[gen_idx] and bus_idx > -1 and gen_types[gen_idx] == GeneratorType.Asynchronous.idx():
            q[gen_idx] = asynchronous_gen_q(u=V[bus_idx],
                                            Rs=Rs[gen_idx],
                                            Xs=Xs[gen_idx],
                                            Xm=Xm[gen_idx],
                                            Rr=Rr[gen_idx],
                                            Xr=Xr[gen_idx],
                                            P=P[gen_idx],
                                            Sr=Snom[gen_idx])

    return q


def compute_asynchronous_generator_q_per_bus(
        nbus: int,
        V: CxVec,
        gen_bus_idx: IntVec,
        gen_active: BoolVec,
        gen_types,
        Rs: Vec,
        Xs: Vec,
        Xm: Vec,
        Rr: Vec,
        Xr: Vec,
        P: Vec,
        Snom: Vec,
) -> Vec:
    """
    Compute the voltage-dependent asynchronous generator Q summed by bus.
    """
    q_per_bus = np.zeros(nbus, dtype=float)
    q = compute_asynchronous_generator_q(V=V,
                                         gen_bus_idx=gen_bus_idx,
                                         gen_active=gen_active,
                                         gen_types=gen_types,
                                         Rs=Rs,
                                         Xs=Xs,
                                         Xm=Xm,
                                         Rr=Rr,
                                         Xr=Xr,
                                         P=P,
                                         Snom=Snom)

    for gen_idx in range(len(gen_bus_idx)):
        bus_idx = gen_bus_idx[gen_idx]
        if bus_idx > -1:
            q_per_bus[bus_idx] += q[gen_idx]

    return q_per_bus


def voltage_q_droop(ut: complex,
                    u_setpoint_min: float,
                    u_setpoint_max: float,
                    u_setpoint: float,
                    Q_setpoint: float,
                    S_r: float,
                    droop: float,
                    Q_min: float,
                    Q_max: float,
                    S_base: float):
    """
    Find the actual reactive power output for generators controlled with a voltage droop.
    :param ut: Actual voltage value at the terminal [pu]
    :param u_setpoint_min: Minimum voltage setpoint [pu]
    :param u_setpoint_max: Maximum voltage setpoint [pu]
    :param u_setpoint: Specified voltage setpoint [pu]
    :param Q_setpoint: Specified dispatch reactive power [MVAr]
    :param S_r: Rated apparent power [MVA]
    :param droop: Voltage droop value [%]
    :param Q_min: Minimum reactive power the converter can inject/absorb [MVAr]
    :param Q_max: Maximum reactive power the converter can inject/absorb [MVAr]
    :param S_base: Base power of the network [MVA]
    """
    u = np.abs(ut)
    # Voltage limits
    if u > u_setpoint_max:
        u = u_setpoint_max
    elif u < u_setpoint_min:
        u = u_setpoint_min
    else:
        u = u

    Q_droop = S_r * 100 / (droop + 1e-20)  # Additional reactive power for the specified voltage droop [MVAr]

    Q = Q_setpoint * S_base - Q_droop * (u_setpoint - u)  # Actual reactive power output [MVAr]

    # Reactive power limits
    # if Q > Q_max:
    #     Q = Q_max
    # elif Q < Q_min:
    #     Q = Q_min
    # else:
    #     Q = Q

    return Q / S_base


def voltage_pdc_droop(ut: complex,
                      un: complex,
                      u_setpoint_min: float,
                      u_setpoint_max: float,
                      u_setpoint: float,
                      Pdc_setpoint: float,
                      S_r: float,
                      droop: float,
                      P_min: float,
                      P_max: float,
                      S_base: float) -> float:
    """
    Find the actual DC power output for converters controlled with a voltage droop,
    where the converter terminal sits on the positive pole.

    Implements Pdc = Pdc_setp - Pdroop * (Vdc_setp - Vdc) 
    with the voltage being the difference Vdc = Re(ut - un)
    where un = 0 for monopolar converters

    :param ut: Actual voltage value at the pole terminal [pu]
    :param un: Actual voltage value at the return/negative terminal [pu]
    :param u_setpoint_min: Minimum voltage setpoint [pu]
    :param u_setpoint_max: Maximum voltage setpoint [pu]
    :param u_setpoint: Specified voltage setpoint [pu]
    :param Pdc_setpoint: Specified dispatch DC power [MW]
    :param S_r: Rated apparent power [MVA]
    :param droop: Voltage droop value [%]
    :param P_min: Minimum DC power the converter can inject/absorb [MW]
    :param P_max: Maximum DC power the converter can inject/absorb [MW]
    :param S_base: Base power of the network [MVA]
    """
    # signed pole-to-return voltage, positive for a positive pole
    u: float = np.real(ut) - np.real(un)

    # Voltage limits
    if u > u_setpoint_max:
        u = u_setpoint_max
    elif u < u_setpoint_min:
        u = u_setpoint_min
    else:
        u = u

    P_droop = S_r * 100 / droop  # Scaled slope

    Pdc = Pdc_setpoint * S_base - P_droop * (u_setpoint - u)  # in MW

    # DC power limits
    if Pdc > P_max:
        Pdc = P_max
    elif Pdc < P_min:
        Pdc = P_min
    else:
        Pdc = Pdc

    return Pdc / S_base


def voltage_pdc_droop_neg(ut: complex,
                          un: complex,
                          u_setpoint_min: float,
                          u_setpoint_max: float,
                          u_setpoint: float,
                          Pdc_setpoint: float,
                          S_r: float,
                          droop: float,
                          P_min: float,
                          P_max: float,
                          S_base: float) -> float:
    """
    Find the actual DC power output for converters controlled with a voltage droop,
    where the converter terminal sits on the negative pole

    The measured voltage is flipped, Vdc = Re(un - ut), so it enters the droop law
    as a positive magnitude

    :param ut: Actual voltage value at the pole terminal [pu]
    :param un: Actual voltage value at the return/negative terminal [pu]
    :param u_setpoint_min: Minimum voltage setpoint [pu]
    :param u_setpoint_max: Maximum voltage setpoint [pu]
    :param u_setpoint: Specified voltage setpoint [pu]
    :param Pdc_setpoint: Specified dispatch DC power [MW]
    :param S_r: Rated apparent power [MVA]
    :param droop: Voltage droop value [%]
    :param P_min: Minimum DC power the converter can inject/absorb [MW]
    :param P_max: Maximum DC power the converter can inject/absorb [MW]
    :param S_base: Base power of the network [MVA]
    """
    # flipped pole to return voltage, positive for a negative pole
    u: float = np.real(un) - np.real(ut)

    # Voltage limits
    if u > u_setpoint_max:
        u = u_setpoint_max
    elif u < u_setpoint_min:
        u = u_setpoint_min
    else:
        u = u

    P_droop = S_r * 100 / droop  # Scaled slope

    Pdc = Pdc_setpoint * S_base - P_droop * (u_setpoint - u)  # output in MW

    # DC power limits
    if Pdc > P_max:
        Pdc = P_max
    elif Pdc < P_min:
        Pdc = P_min
    else:
        Pdc = Pdc

    return Pdc / S_base


@nb.jit(cache=True, fastmath=True)
def polar_to_rect(Vm: Vec, Va: Vec) -> CxVec:
    """
    Convert polar to rectangular coordinates
    :param Vm: Module
    :param Va: Angle in radians
    :return: Polar vector
    """
    return Vm * np.exp(1.0j * Va)


def expand(n, arr: Vec, idx: IntVec, default: float) -> Vec:
    """
    Expand array
    :param n: number of elements
    :param arr: short array
    :param idx: indices in the longer array
    :param default: default value for the longer array
    :return: longer array
    """
    x = np.full(n, default)
    if len(arr):
        x[idx] = arr
    return x


@nb.jit(cache=True, fastmath=True)
def compute_zip_power(S0: CxVec, I0: CxVec, Y0: CxVec, Vm: Vec) -> CxVec:
    """
    Compute the equivalent power injection
    :param S0: Base power (P + jQ)
    :param I0: Base current (Ir + jIi)
    :param Y0: Base admittance (G + jB)
    :param Vm: voltage module, for the 3ph power flow the complete voltage phasor is used (Vm + Va)
    :return: complex power injection
    """
    return S0 + np.conj(I0 + Y0 * Vm) * Vm


def compute_zip_current(S0: CxVec, I0: CxVec, Y0: CxVec, Vm: Vec) -> CxVec:
    """
    Compute the equivalent current injection
    :param S0: Base power (P + jQ)
    :param I0: Base current (Ir + jIi)
    :param Y0: Base admittance (G + jB)
    :param Vm: voltage module, for the 3ph power flow the complete voltage phasor is used (Vm + Va)
    :return: complex current injection
    """
    return I0 + np.conj(S0 / Vm) + Y0 * Vm


def compute_power(Ybus: csc_matrix, V: CxVec) -> CxVec:
    """
    Compute the power from the admittance matrix and the voltage
    :param Ybus: Admittance matrix
    :param V: Voltage vector
    :return: Calculated power injections
    """
    return V * np.conj(Ybus @ V)


def compute_current(Ybus: csc_matrix, V: CxVec) -> CxVec:
    """
    Compute the current from the admittance matrix and the voltage
    :param Ybus: Admittance matrix
    :param V: Voltage vector
    :return: Calculated current injections
    """
    return Ybus @ V


@nb.jit(cache=True, fastmath=True)
def compute_fx(Scalc: CxVec, Sbus: CxVec, idx_dP: IntVec, idx_dQ: IntVec) -> Vec:
    """
    Compute the NR-like error function
    f = [∆P(pqpv), ∆Q(pq)]
    :param Scalc: Calculated power injections
    :param Sbus: Specified power injections
    :param idx_dP: Array of node indices updated with dP (pvpq)
    :param idx_dQ: Array of node indices updated with dQ (pq)
    :return: error
    """
    # dS = Scalc - Sbus  # compute the mismatch
    # return np.r_[dS[idx_dP].real, dS[idx_dQ].imag]

    n = len(idx_dP) + len(idx_dQ)

    fx = np.empty(n, dtype=float)

    k = 0
    for i in idx_dP:
        # F1(x0) Power balance mismatch - Va
        # fx[k] = mis[i].real
        fx[k] = Scalc[i].real - Sbus[i].real
        k += 1

    for i in idx_dQ:
        # F2(x0) Power balance mismatch - Vm
        # fx[k] = mis[i].imag
        fx[k] = Scalc[i].imag - Sbus[i].imag
        k += 1

    return fx


def compute_fx_error(fx: Vec) -> float:
    """
    Compute the infinite norm of fx
    this is the same as max(abs(fx))
    :param fx: vector
    :return: infinite norm
    """
    return np.linalg.norm(fx, np.inf)


@nb.jit()
def get_Sf(k: IntVec, Vm: Vec, V: CxVec, yff: CxVec, yft: CxVec, F: IntVec, T: IntVec):
    """

    :param k:
    :param Vm:
    :param V:
    :param yff:
    :param yft:
    :param F:
    :param T:
    :return:
    """
    f = F[k]
    t = T[k]
    return np.power(Vm[f], 2.0) * np.conj(yff[k]) + V[f] * np.conj(V[t]) * np.conj(yft[k])


@nb.jit()
def get_St(k: IntVec, Vm: Vec, V: CxVec, ytf: CxVec, ytt: CxVec, F: IntVec, T: IntVec):
    """

    :param k:
    :param Vm:
    :param V:
    :param ytf:
    :param ytt:
    :param F:
    :param T:
    :return:
    """
    f = F[k]
    t = T[k]
    return np.power(Vm[t], 2.0) * np.conj(ytt[k]) + V[t] * np.conj(V[f]) * np.conj(ytf[k])


@nb.jit()
def get_If(k: IntVec, V: CxVec, yff: CxVec, yft: CxVec, F: IntVec, T: IntVec):
    """

    :param k:
    :param V:
    :param yff:
    :param yft:
    :param F:
    :param T:
    :return:
    """
    f = F[k]
    t = T[k]
    return np.conj(V[f]) * np.conj(yff[k]) + np.conj(V[t]) * np.conj(yft[k])


@nb.jit()
def get_It(k: IntVec, V: CxVec, ytf: CxVec, ytt: CxVec, F: IntVec, T: IntVec):
    """

    :param k:
    :param V:
    :param ytf:
    :param ytt:
    :param F:
    :param T:
    :return:
    """
    f = F[k]
    t = T[k]
    return np.conj(V[t]) * np.conj(ytt[k]) + np.conj(V[f]) * np.conj(ytf[k])


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


@nb.jit(cache=True)
def floating_star_currents(Va, Vb, Vc, Istar_a, Istar_b, Istar_c, Vn0) -> Tuple[complex, complex, complex, complex]:
    """
    Given the phase voltages and currents of a floating star connected current load,
    this function calculates the phase currents (Ia, Ib, Ic) and the neutral voltage (Vn),
    such that they meet the condition that the current flowing through the neutral point is equal to zero,
    since the neutral point of the star is floating -> In = Ia + Ib + Ic = 0
    :param Va: Phase A load voltage
    :param Vb: Phase B load voltage
    :param Vc: Phase C load voltage
    :param Istar_a: Phase A load current
    :param Istar_b: Phase B load current
    :param Istar_c: Phase C load current
    :param Vn0: Last-iteration neutral point voltage or
                just the center of the phase voltages (Va,Vb,Vc) at the first iteration
    :return: Ia, Ib, Ic, Vn
    """
    zero_voltage = 1e-5
    zero_current = complex(0.0, 0.0)
    # unknown: Vn (complex). Start from last-iter Vn0 or center of Va,Vb,Vc
    Vn = Vn0
    error = 1.0
    iteration = 0
    max_iterations = 25

    # Remove @nb.jit decorator - nested functions can't be decorated
    def Iphase(U, Istar):
        Umag = abs(U)
        if Umag < 1e-12:  # guard
            return nb.complex128(0.0)  # Changed from complex64 to complex128
        return np.conj(Istar) * (U / Umag)

    while error > 1e-6 and iteration <= max_iterations:  # few Newton steps are usually enough

        if abs(Va) > zero_voltage and abs(Vb) > zero_voltage and abs(Vc) > zero_voltage:

            Ua, Ub, Uc = Va - Vn, Vb - Vn, Vc - Vn

            Ia = Iphase(Ua, Istar_a)
            Ib = Iphase(Ub, Istar_b)
            Ic = Iphase(Uc, Istar_c)
            F = Ia + Ib + Ic  # complex residual
            if abs(F) < 1e-9:
                return Ia, Ib, Ic, Vn

            # Jacobian dF/dVn (complex), derived from d/dVn [U/|U|] = -(1/|U|)(I - U U*/|U|^2)
            # A simple, very stable approximation is to use a secant-like step:
            eps = 1e-6
            dV = eps * (1.0 + 1.0j)
            Uad, Ubd, Ucd = Va - (Vn + dV), Vb - (Vn + dV), Vc - (Vn + dV)
            Iad = Iphase(Uad, Istar_a)
            Ibd = Iphase(Ubd, Istar_b)
            Icd = Iphase(Ucd, Istar_c)
            Fd = Iad + Ibd + Icd
            Jsec = (Fd - F) / dV if dV != 0 else 1.0
            if Jsec == 0:
                return zero_voltage, zero_voltage, zero_voltage, zero_voltage
            # damped update
            Vn = Vn - 0.7 * F / Jsec

        elif abs(Va) > zero_voltage and abs(Vb) > zero_voltage:

            Ua, Ub = Va - Vn, Vb - Vn

            Ia = Iphase(Ua, Istar_a)
            Ib = Iphase(Ub, Istar_b)
            F = Ia + Ib  # complex residual
            if abs(F) < 1e-9:
                return Ia, Ib, zero_current, Vn

            # Jacobian dF/dVn (complex), derived from d/dVn [U/|U|] = -(1/|U|)(I - U U*/|U|^2)
            # A simple, very stable approximation is to use a secant-like step:
            eps = 1e-6
            dV = eps * (1.0 + 1.0j)
            Uad, Ubd = Va - (Vn + dV), Vb - (Vn + dV)
            Iad = Iphase(Uad, Istar_a)
            Ibd = Iphase(Ubd, Istar_b)
            Fd = Iad + Ibd
            Jsec = (Fd - F) / dV if dV != 0 else 1.0
            if Jsec == 0:
                return zero_voltage, zero_voltage, zero_voltage, zero_voltage
            # damped update
            Vn = Vn - 0.7 * F / Jsec

        elif abs(Vb) > zero_voltage and abs(Vc) > zero_voltage:

            Ub, Uc = Vb - Vn, Vc - Vn

            Ib = Iphase(Ub, Istar_b)
            Ic = Iphase(Uc, Istar_c)
            F = Ib + Ic  # complex residual
            if abs(F) < 1e-9:
                return zero_current, Ib, Ic, Vn

            # Jacobian dF/dVn (complex), derived from d/dVn [U/|U|] = -(1/|U|)(I - U U*/|U|^2)
            # A simple, very stable approximation is to use a secant-like step:
            eps = 1e-6
            dV = eps * (1.0 + 1.0j)
            Ubd, Ucd = Vb - (Vn + dV), Vc - (Vn + dV)
            Ibd = Iphase(Ubd, Istar_b)
            Icd = Iphase(Ucd, Istar_c)
            Fd = Ibd + Icd
            Jsec = (Fd - F) / dV if dV != 0 else 1.0
            if Jsec == 0:
                return zero_voltage, zero_voltage, zero_voltage, zero_voltage
            # damped update
            Vn = Vn - 0.7 * F / Jsec

        elif abs(Vc) > zero_voltage and abs(Va) > zero_voltage:

            Ua, Uc = Va - Vn, Vc - Vn

            Ia = Iphase(Ua, Istar_a)
            Ic = Iphase(Uc, Istar_c)
            F = Ia + Ic  # complex residual
            if abs(F) < 1e-9:
                return Ia, zero_current, Ic, Vn

            # Jacobian dF/dVn (complex), derived from d/dVn [U/|U|] = -(1/|U|)(I - U U*/|U|^2)
            # A simple, very stable approximation is to use a secant-like step:
            eps = 1e-6
            dV = eps * (1.0 + 1.0j)
            Uad, Ucd = Va - (Vn + dV), Vc - (Vn + dV)
            Iad = Iphase(Uad, Istar_a)
            Icd = Iphase(Ucd, Istar_c)
            Fd = Iad + Icd
            Jsec = (Fd - F) / dV if dV != 0 else 1.0
            if Jsec == 0:
                return zero_voltage, zero_voltage, zero_voltage, zero_voltage
            # damped update
            Vn = Vn - 0.7 * F / Jsec

        else:
            return zero_voltage, zero_voltage, zero_voltage, zero_voltage

        error = np.abs(Vn - Vn0)
        iteration += 1

    # final phase currents to inject (load consumes → subtract at phases)
    if abs(Va) > zero_voltage and abs(Vb) > zero_voltage and abs(Vc) > zero_voltage:
        Ua, Ub, Uc = Va - Vn, Vb - Vn, Vc - Vn
        Ia = Iphase(Ua, Istar_a)
        Ib = Iphase(Ub, Istar_b)
        Ic = Iphase(Uc, Istar_c)
    elif abs(Va) > zero_voltage and abs(Vb) > zero_voltage:
        Ua, Ub = Va - Vn, Vb - Vn
        Ia = Iphase(Ua, Istar_a)
        Ib = Iphase(Ub, Istar_b)
        Ic = complex(0.0, 0.0)
    elif abs(Vb) > zero_voltage and abs(Vc) > zero_voltage:
        Ub, Uc = Vb - Vn, Vc - Vn
        Ia = complex(0.0, 0.0)
        Ib = Iphase(Ub, Istar_b)
        Ic = Iphase(Uc, Istar_c)
    elif abs(Va) > zero_voltage and abs(Vc) > zero_voltage:
        Ua, Uc = Va - Vn, Vc - Vn
        Ia = Iphase(Ua, Istar_a)
        Ib = complex(0.0, 0.0)
        Ic = Iphase(Uc, Istar_c)
    else:
        Ia = complex(0.0, 0.0)
        Ib = complex(0.0, 0.0)
        Ic = complex(0.0, 0.0)

    return Ia, Ib, Ic, Vn


# @nb.jit(cache=True)
def floating_star_powers(Ua,
                         Ub,
                         Uc,
                         Sa,
                         Sb,
                         Sc) -> Tuple[complex, complex, complex, complex]:
    """
    Given the phase voltages and complex powers of a floating star connected power load,
    this function calculates the phase currents (Ia, Ib, Ic) and the neutral voltage (Un),
    such that they meet the condition that the current flowing through the neutral point is equal to zero,
    since the neutral point of the star is floating -> In = Ia + Ib + Ic = 0
    :param Ua: Phase A load voltage
    :param Ub: Phase B load voltage
    :param Uc: Phase C load voltage
    :param Sa: Phase A load complex power
    :param Sb: Phase B load complex power
    :param Sc: Phase C load complex power
    :return: Ia, Ib, Ic, Un
    """
    zero_current = complex(1e-10, 1e-10)

    # A·x2 + B·x + c = 0
    # x = (-B +- sqrt(B2 - 4·A·C)) / 2·A

    if np.abs(Sa + Sb + Sc) > np.abs(zero_current):
        A = Sa + Sb + Sc
    else:
        A = zero_current
    B = -(Sa * (Ub + Uc) + Sb * (Ua + Uc) + Sc * (Ua + Ub))
    C = Sa * Ub * Uc + Sb * Ua * Uc + Sc * Ua * Ub

    Un_p = (-B + np.sqrt(B ** 2 - 4 * A * C)) / (2 * A)
    Un_n = (-B - np.sqrt(B ** 2 - 4 * A * C)) / (2 * A)

    if np.abs(Un_p) < np.abs(Un_n) and np.abs(Un_p) != 0.0 and np.abs(Un_p) <= 1.0:
        Un = Un_p
    elif np.abs(Un_n) != 0.0 and np.abs(Un_n) <= 1.0:
        Un = Un_n
    else:
        Un = complex(0.0, 0.0)

    if np.abs(Ua) > np.abs(zero_current) and np.abs(Ua - Un) > np.abs(zero_current):
        Ia = np.conj(Sa / (Ua - Un))
    else:
        Ia = zero_current

    if np.abs(Ub) > np.abs(zero_current) and np.abs(Ub - Un) > np.abs(zero_current):
        Ib = np.conj(Sb / (Ub - Un))
    else:
        Ib = zero_current

    if np.abs(Uc) > np.abs(zero_current) and np.abs(Uc - Un) > np.abs(zero_current):
        Ic = np.conj(Sc / (Uc - Un))
    else:
        Ic = zero_current

    return Ia, Ib, Ic, Un


def power_flow_post_process_nonlinear_3ph(Sbus: CxVec,
                                          V: CxVec,
                                          Vn_floating: CxVec,
                                          F: IntVec,
                                          T: IntVec,
                                          pv: IntVec,
                                          vd: IntVec,
                                          Ybus: CscMat,
                                          Yf: CscMat,
                                          Yt: CscMat,
                                          Yshunt_bus: CxVec,
                                          branch_rates: Vec,
                                          Sbase: float,
                                          bus_lookup: IntVec,
                                          branch_lookup: IntVec):
    """


    :param Sbus:
    :param V:
    :param Vn_floating:
    :param F:
    :param T:
    :param pv:
    :param vd:
    :param Ybus:
    :param Yf:
    :param Yt:
    :param Yshunt_bus:
    :param branch_rates:
    :param Sbase:
    :param bus_lookup:
    :param branch_lookup:
    :return:
    """
    V_expanded = expand_magnitudes(V, bus_lookup)
    Vn_floating_expanded = expand_magnitudes(Vn_floating, bus_lookup)

    # Compute the basic Sbus
    Sbus = V * np.conj(Ybus @ V)

    # Add the shunt power V^2 x Y^*
    Vm = np.abs(V)
    Sbus += np.conj(Yshunt_bus) @ (Vm * Vm)

    # power at the slack nodes
    if len(vd) > 0:
        Sbus[vd] = V[vd] * np.conj(Ybus[vd, :] @ V)

    # Reactive power at the pv nodes
    if len(pv) > 0:
        P_pv = Sbus[pv].real
        Q_pv = (V[pv] * np.conj(Ybus[pv, :] @ V)).imag
        Sbus[pv] = P_pv + 1j * Q_pv  # keep the original P injection and set the calculated reactive power for PV nodes

    Sbus_expanded = expand_magnitudes(Sbus, bus_lookup)

    # Branches current, loading, etc
    Vf_expanded = V_expanded[F]
    Vt_expanded = V_expanded[T]
    Vf_floating_expanded = Vn_floating_expanded[F]
    Vt_floating_expanded = Vn_floating_expanded[T]

    If = Yf @ V
    It = Yt @ V
    If_expanded = expand_magnitudes(If, branch_lookup)
    It_expanded = expand_magnitudes(It, branch_lookup)

    Sf_expanded = Vf_expanded * np.conj(If_expanded) * (Sbase / 3)
    St_expanded = Vt_expanded * np.conj(It_expanded) * (Sbase / 3)

    Sf_load_expanded = (Vf_expanded - Vf_floating_expanded) * np.conj(If_expanded) * (Sbase / 3)
    St_load_expanded = (Vt_expanded - Vt_floating_expanded) * np.conj(It_expanded) * (Sbase / 3)

    # Branch losses in MVA
    losses = (Sf_expanded + St_expanded)

    # branch voltage increment
    Vbranch = Vf_expanded - Vt_expanded

    # Branch loading in p.u.
    loading = Sf_expanded / (branch_rates + 1e-9)

    return Sf_expanded, St_expanded, If_expanded, It_expanded, Vbranch, loading, losses, Sbus_expanded, V_expanded


def power_flow_post_process_nonlinear(Sbus: CxVec,
                                      V: CxVec,
                                      F: IntVec,
                                      T: IntVec,
                                      pv: IntVec,
                                      vd: IntVec,
                                      Ybus: CscMat,
                                      Yf: CscMat,
                                      Yt: CscMat,
                                      Yshunt_bus: CxVec,
                                      branch_rates: Vec,
                                      Sbase: float):
    """

    :param Sbus:
    :param V:
    :param F:
    :param T:
    :param pv:
    :param vd:
    :param Ybus:
    :param Yf:
    :param Yt:
    :param Yshunt_bus:
    :param branch_rates:
    :param Sbase:
    :return:
    """

    # power at the slack nodes
    Sbus[vd] = V[vd] * np.conj(Ybus[vd, :] @ V)

    # Reactive power at the pv nodes
    P_pv = Sbus[pv].real
    Q_pv = (V[pv] * np.conj(Ybus[pv, :] @ V)).imag
    Sbus[pv] = P_pv + 1j * Q_pv  # keep the original P injection and set the calculated reactive power for PV nodes

    # Add the shunt power V^2 x Y^*
    Vm = np.abs(V)
    Sbus += Vm * Vm * np.conj(Yshunt_bus)

    # Branches current, loading, etc
    Vf = V[F]
    Vt = V[T]
    If = Yf @ V
    It = Yt @ V
    Sf = Vf * np.conj(If) * Sbase
    St = Vt * np.conj(It) * Sbase

    # Branch losses in MVA
    losses = (Sf + St)

    # branch voltage increment
    Vbranch = Vf - Vt

    # Branch loading in p.u.
    loading = Sf / (branch_rates + 1e-9)

    return Sf, St, If, It, Vbranch, loading, losses, Sbus


def power_flow_post_process_linear(Sbus: CxVec, V: CxVec,
                                   active: IntVec, X: Vec, tap_module: Vec, tap_angle: Vec,
                                   F: IntVec, T: IntVec,
                                   branch_rates: Vec, Sbase: float):
    """

    :param Sbus:
    :param V:
    :param active:
    :param X:
    :param tap_module:
    :param tap_angle:
    :param F:
    :param T:
    :param branch_rates:
    :param Sbase:
    :return:
    """

    # DC power flow
    theta = np.angle(V, deg=False)
    theta_f = theta[F]
    theta_t = theta[T]

    b = active.astype(float) / (X * tap_module)
    # Pf = calculation_inputs.Bf @ theta - b * calculation_inputs.branch_data.tap_angle

    Pf = b * (theta_f - theta_t - tap_angle)

    Sfb = Pf * Sbase
    Stb = -Pf * Sbase

    Vf = V[F]
    Vt = V[T]
    Vbranch = Vf - Vt
    If = Pf / (Vf + 1e-20)
    It = -If

    # losses are not considered in the power flow computation
    losses = np.zeros(len(X))

    # Branch loading in p.u.
    loading = Sfb / (branch_rates + 1e-9)

    return Sfb, Stb, If, It, Vbranch, loading, losses, Sbus


@nb.jit(cache=True)
def split_bus_quantity(
        Qbus: Vec,
        gen_bus_idx: IntVec,
        Qmin_gen: Vec,
        Qmax_gen: Vec,
        gen_status: BoolVec,
        control_mode_int_gen: IntVec,
        Q0_gen: Vec,
        Vset_gen: Vec,
        k_droop_gen: Vec,
        dead_band_gen: Vec,
        batt_bus_idx: IntVec,
        Qmin_batt: Vec,
        Qmax_batt: Vec,
        batt_status: BoolVec,
        control_mode_int_batt: IntVec,
        Q0_batt: Vec,
        v_ctrl_val_gen: int,
        qv_droop_val_gen: int,
        Vm: Vec,
        atol: float = 1e-12,
) -> Tuple[Vec, Vec]:
    """
    Split a per-bus reactive power quantity among online generators and batteries.

    The function separates generator-like elements into two families:

    1. Generators.
    2. Batteries.

    Both families are treated as reactive power providers connected to buses.
    The bus-level reactive power ``Qbus`` is split among all online controlling
    elements at each bus, regardless of whether the element is a generator or a
    battery.

    Online non-controlling generators and online non-controlling batteries are
    assigned their initial reactive power set point ``Q0``. Their contribution
    is subtracted from the bus reactive power before the controlling elements
    share the remaining value.

    For each bus ``i``, the fixed non-controlling contribution is:

    .. math::

        Qfixed_i =
        \\sum_{k \\in G_i,\\ online,\\ not\\ controlling} Q0^{gen}_k
        +
        \\sum_{m \\in B_i,\\ online,\\ not\\ controlling} Q0^{batt}_m

    The reactive power left for controlling elements is:

    .. math::

        Qctrl_i = Qbus_i - Qfixed_i

    The aggregate controlling limits include both generators and batteries:

    .. math::

        Qctrl^{min}_i =
        \\sum_{k \\in G_i,\\ online,\\ controlling} Qmin^{gen}_k
        +
        \\sum_{m \\in B_i,\\ online,\\ controlling} Qmin^{batt}_m

    .. math::

        Qctrl^{max}_i =
        \\sum_{k \\in G_i,\\ online,\\ controlling} Qmax^{gen}_k
        +
        \\sum_{m \\in B_i,\\ online,\\ controlling} Qmax^{batt}_m

    The normalized sharing factor at each bus is:

    .. math::

        r_i =
        \\frac{
            Qctrl_i - Qctrl^{min}_i
        }{
            Qctrl^{max}_i - Qctrl^{min}_i
        }

    after clipping ``Qctrl_i`` to the aggregate controlling capability.

    Final assignments are:

    * Offline generators receive zero.
    * Offline batteries receive zero.
    * Online non-controlling generators receive ``Q0_gen``.
    * Online non-controlling batteries receive ``Q0_batt``.
    * Online controlling generators share the residual bus Q using their own
      ``Qmin_gen`` and ``Qmax_gen``.
    * Online controlling batteries share the residual bus Q using their own
      ``Qmin_batt`` and ``Qmax_batt``.

    This function assumes that generators and batteries use the same reactive
    power sign convention as ``Qbus``.

    This function assumes that all arrays have compatible sizes and that
    ``gen_bus_idx`` and ``batt_bus_idx`` contain valid zero-based bus indices.
    Input validation should be done by the caller or by a Python wrapper outside
    this Numba function.

    :param Qbus:
        Total reactive generator-like power requested at each bus.
    :type Qbus: Vec
    :param gen_bus_idx:
        Bus index of each generator.
    :type gen_bus_idx: IntVec
    :param Qmin_gen:
        Minimum reactive power limit of each generator.
    :type Qmin_gen: Vec
    :param Qmax_gen:
        Maximum reactive power limit of each generator.
    :type Qmax_gen: Vec
    :param gen_status:
        Generator status vector. ``True`` means online.
    :type gen_status: BoolVec
    :param control_mode_int_gen:
        Generator control flag. ``True`` means the generator participates in
        reactive power sharing.
    :type control_mode_int_gen: BoolVec
    :param Q0_gen:
        Initial or fixed reactive power set point of each generator.
    :type Q0_gen: Vec
    :param Vset_gen:
        Voltage set point of each generator.
    :type Vset_gen: Vec
    :param k_droop_gen:
        QV droop constant of each generator.
    :type k_droop_gen: Vec
    :param dead_band_gen:
        QV droop dead band of each generator.
    :type dead_band_gen: Vec
    :param batt_bus_idx:
        Bus index of each battery.
    :type batt_bus_idx: IntVec
    :param Qmin_batt:
        Minimum reactive power limit of each battery.
    :type Qmin_batt: Vec
    :param Qmax_batt:
        Maximum reactive power limit of each battery.
    :type Qmax_batt: Vec
    :param batt_status:
        Battery status vector. ``True`` means online.
    :type batt_status: BoolVec
    :param control_mode_int_batt:
        Battery control flag. ``True`` means the battery participates in
        reactive power sharing.
    :type control_mode_int_batt: BoolVec
    :param Q0_batt:
        Initial or fixed reactive power set point of each battery.
    :type Q0_batt: Vec
    :param v_ctrl_val_gen:
    :param qv_droop_val_gen:
    :param Vm:
        Converged voltage magnitude per bus.
    :type Vm: Vec
    :param atol:
        Tolerance used to detect zero aggregate reactive range.
    :type atol: float
    :return:
        Reactive power assigned to generators and batteries.
    :rtype: Tuple[Vec, Vec]
    """

    # Sizes are known from the input arrays, so all memory required by the
    # algorithm is allocated before doing any numerical work.
    n_bus: int = len(Qbus)
    n_gen: int = len(gen_bus_idx)
    n_batt: int = len(batt_bus_idx)

    # Final reactive power of generators and batteries.
    # These start from Q0 because non-controlling online elements preserve Q0.
    # Controlling and offline elements are overwritten in the final passes.
    q_gen: Vec = Q0_gen.copy()
    q_batt: Vec = Q0_batt.copy()

    # Fixed non-controlling contribution per bus.
    # This includes both generators and batteries that are online but not
    # controlling.
    qfixed_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)

    # Aggregate reactive limits of online controlling elements.
    # These include both controlling generators and controlling batteries.
    qmin_control_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    qmax_control_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)

    # Number of online controlling elements per bus.
    # This counts both controlling generators and controlling batteries.
    control_count_per_bus: np.ndarray = np.zeros(n_bus, dtype=np.int64)

    # Normalized bus sharing factor for online controlling elements.
    qshare_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    q_droop_value: float
    delta_v: float
    qmin_gen_value: float
    qmax_gen_value: float

    # -------------------------------------------------------------------------
    # First generator pass.
    # -------------------------------------------------------------------------
    # Build part of the bus-level aggregate quantities from generators:
    #
    # 1. Online non-controlling generators add Q0_gen to qfixed_per_bus.
    # 2. Online controlling generators add Qmin_gen and Qmax_gen to the
    #    aggregate controlling capability.
    # 3. Offline generators add nothing.
    # -------------------------------------------------------------------------
    for gen_idx in range(n_gen):
        bus_idx = gen_bus_idx[gen_idx]

        if gen_status[gen_idx]:
            if control_mode_int_gen[gen_idx] == v_ctrl_val_gen:
                qmin_control_per_bus[bus_idx] += Qmin_gen[gen_idx]
                qmax_control_per_bus[bus_idx] += Qmax_gen[gen_idx]
                control_count_per_bus[bus_idx] += 1
                qfixed_per_bus[bus_idx] += 0.0
            elif control_mode_int_gen[gen_idx] == qv_droop_val_gen:
                # The droop-controlled generator reactive power is known once
                # the final bus voltage is known, so it behaves as a fixed
                # contribution in the post-processing split.
                delta_v = Vset_gen[gen_idx] - Vm[bus_idx]
                q_droop_value = 0.0

                if abs(delta_v) > dead_band_gen[gen_idx]:
                    if delta_v > dead_band_gen[gen_idx]:
                        q_droop_value = (
                            (delta_v - dead_band_gen[gen_idx])
                            * k_droop_gen[gen_idx]
                            * Qmax_gen[gen_idx]
                        )
                    else:
                        if delta_v < -dead_band_gen[gen_idx]:
                            q_droop_value = (
                                (delta_v + dead_band_gen[gen_idx])
                                * k_droop_gen[gen_idx]
                                * Qmax_gen[gen_idx]
                            )
                        else:
                            q_droop_value = 0.0

                    if q_droop_value > Qmax_gen[gen_idx]:
                        q_droop_value = Qmax_gen[gen_idx]
                    else:
                        pass

                    if q_droop_value < Qmin_gen[gen_idx]:
                        q_droop_value = Qmin_gen[gen_idx]
                    else:
                        pass
                else:
                    q_droop_value = 0.0

                qfixed_per_bus[bus_idx] += q_droop_value
                qmin_control_per_bus[bus_idx] += 0.0
                qmax_control_per_bus[bus_idx] += 0.0
                control_count_per_bus[bus_idx] += 0
            else:
                qfixed_per_bus[bus_idx] += Q0_gen[gen_idx]
                qmin_control_per_bus[bus_idx] += 0.0
                qmax_control_per_bus[bus_idx] += 0.0
                control_count_per_bus[bus_idx] += 0
        else:
            qfixed_per_bus[bus_idx] += 0.0
            qmin_control_per_bus[bus_idx] += 0.0
            qmax_control_per_bus[bus_idx] += 0.0
            control_count_per_bus[bus_idx] += 0

    # -------------------------------------------------------------------------
    # First battery pass.
    # -------------------------------------------------------------------------
    # Add the battery contribution to the same bus-level aggregate quantities.
    #
    # This is what makes generators and batteries share the same residual
    # reactive power pool at each bus.
    # -------------------------------------------------------------------------
    for batt_idx in range(n_batt):
        bus_idx = batt_bus_idx[batt_idx]

        if batt_status[batt_idx]:
            if control_mode_int_batt[batt_idx] == v_ctrl_val_gen:
                qmin_control_per_bus[bus_idx] += Qmin_batt[batt_idx]
                qmax_control_per_bus[bus_idx] += Qmax_batt[batt_idx]
                control_count_per_bus[bus_idx] += 1
                qfixed_per_bus[bus_idx] += 0.0
            else:
                qfixed_per_bus[bus_idx] += Q0_batt[batt_idx]
                qmin_control_per_bus[bus_idx] += 0.0
                qmax_control_per_bus[bus_idx] += 0.0
                control_count_per_bus[bus_idx] += 0
        else:
            qfixed_per_bus[bus_idx] += 0.0
            qmin_control_per_bus[bus_idx] += 0.0
            qmax_control_per_bus[bus_idx] += 0.0
            control_count_per_bus[bus_idx] += 0

    # -------------------------------------------------------------------------
    # Bus pass.
    # -------------------------------------------------------------------------
    # Compute one normalized sharing factor per bus.
    #
    # The same factor is later applied to both controlling generators and
    # controlling batteries connected to the bus.
    # -------------------------------------------------------------------------
    for bus_idx in range(n_bus):
        qfixed_value = qfixed_per_bus[bus_idx]

        qmin_control_value = qmin_control_per_bus[bus_idx]
        qmax_control_value = qmax_control_per_bus[bus_idx]
        qrange_control_value = qmax_control_value - qmin_control_value

        qcontrol_required_value = Qbus[bus_idx] - qfixed_value
        control_count_value = control_count_per_bus[bus_idx]

        if control_count_value > 0:
            # Reject non-finite aggregate limits before normalizing because a
            # NaN bus capability would otherwise leak into the sharing factor.
            if np.isfinite(qrange_control_value) and np.isfinite(qcontrol_required_value):
                if qrange_control_value > atol:
                    # Clip the residual controlling request to the combined
                    # controlling capability of generators and batteries.
                    if qcontrol_required_value < qmin_control_value:
                        qcontrol_limited_value = qmin_control_value
                    else:
                        if qcontrol_required_value > qmax_control_value:
                            qcontrol_limited_value = qmax_control_value
                        else:
                            qcontrol_limited_value = qcontrol_required_value

                    # Compute the normalized bus loading factor.
                    qshare_value = (qcontrol_limited_value - qmin_control_value) / qrange_control_value

                    # Numerical safety after clipping.
                    if qshare_value < 0.0:
                        qshare_per_bus[bus_idx] = 0.0
                    else:
                        if qshare_value > 1.0:
                            qshare_per_bus[bus_idx] = 1.0
                        else:
                            qshare_per_bus[bus_idx] = qshare_value
                else:
                    # There are controlling elements, but their aggregate reactive
                    # range is zero. They will be assigned their Qmin values.
                    qshare_per_bus[bus_idx] = 0.0
            else:
                qshare_per_bus[bus_idx] = 0.0
        else:
            # There are no online controlling elements at this bus.
            qshare_per_bus[bus_idx] = 0.0

    # -------------------------------------------------------------------------
    # Second generator pass.
    # -------------------------------------------------------------------------
    # Assign final generator reactive power.
    # -------------------------------------------------------------------------
    for gen_idx in range(n_gen):
        bus_idx = gen_bus_idx[gen_idx]

        if gen_status[gen_idx]:
            if control_mode_int_gen[gen_idx] == v_ctrl_val_gen:
                qmin_gen_value = Qmin_gen[gen_idx]
                qmax_gen_value = Qmax_gen[gen_idx]
                qrange_gen_value = qmax_gen_value - qmin_gen_value

                # Reject non-finite limits before reconstructing the device Q
                # because 0 * NaN still raises an invalid warning in NumPy.
                if np.isfinite(qmin_gen_value) and np.isfinite(qmax_gen_value):
                    q_gen[gen_idx] = qmin_gen_value + qshare_per_bus[bus_idx] * qrange_gen_value
                else:
                    q_gen[gen_idx] = 0.0
            elif control_mode_int_gen[gen_idx] == qv_droop_val_gen:
                # Recompute the same droop law so the reported per-generator Q
                # matches the fixed contribution used in the bus decomposition.
                delta_v = Vset_gen[gen_idx] - Vm[bus_idx]
                q_droop_value = 0.0

                if abs(delta_v) > dead_band_gen[gen_idx]:
                    if delta_v > dead_band_gen[gen_idx]:
                        q_droop_value = (
                            (delta_v - dead_band_gen[gen_idx])
                            * k_droop_gen[gen_idx]
                            * Qmax_gen[gen_idx]
                        )
                    else:
                        if delta_v < -dead_band_gen[gen_idx]:
                            q_droop_value = (
                                (delta_v + dead_band_gen[gen_idx])
                                * k_droop_gen[gen_idx]
                                * Qmax_gen[gen_idx]
                            )
                        else:
                            q_droop_value = 0.0

                    if q_droop_value > Qmax_gen[gen_idx]:
                        q_droop_value = Qmax_gen[gen_idx]
                    else:
                        pass

                    if q_droop_value < Qmin_gen[gen_idx]:
                        q_droop_value = Qmin_gen[gen_idx]
                    else:
                        pass
                else:
                    q_droop_value = 0.0

                q_gen[gen_idx] = q_droop_value
            else:
                q_gen[gen_idx] = Q0_gen[gen_idx]
        else:
            q_gen[gen_idx] = 0.0

    # -------------------------------------------------------------------------
    # Second battery pass.
    # -------------------------------------------------------------------------
    # Assign final battery reactive power using the same bus sharing factors that
    # were used for generators.
    # -------------------------------------------------------------------------
    for batt_idx in range(n_batt):
        bus_idx = batt_bus_idx[batt_idx]

        if batt_status[batt_idx]:
            if control_mode_int_batt[batt_idx] == v_ctrl_val_gen:
                qmin_batt_value = Qmin_batt[batt_idx]
                qmax_batt_value = Qmax_batt[batt_idx]
                qrange_batt_value = qmax_batt_value - qmin_batt_value

                # Reject non-finite limits before reconstructing the device Q
                # because 0 * NaN still raises an invalid warning in NumPy.
                if np.isfinite(qmin_batt_value) and np.isfinite(qmax_batt_value):
                    q_batt[batt_idx] = qmin_batt_value + qshare_per_bus[bus_idx] * qrange_batt_value
                else:
                    q_batt[batt_idx] = 0.0
            else:
                q_batt[batt_idx] = Q0_batt[batt_idx]
        else:
            q_batt[batt_idx] = 0.0

    return q_gen, q_batt


def split_reactive_power_between_generators_and_batteries(
        Qbus: Vec,
        Qfixed_bus: Vec,
        gen_bus_idx: IntVec,
        Qmin_gen: Vec,
        Qmax_gen: Vec,
        gen_status: BoolVec,
        control_mode_int_gen: IntVec,
        Q0_gen: Vec,
        Vset_gen: Vec,
        k_droop_gen: Vec,
        dead_band_gen: Vec,
        batt_bus_idx: IntVec,
        Qmin_batt: Vec,
        Qmax_batt: Vec,
        batt_status: BoolVec,
        control_mode_int_batt: IntVec,
        Q0_batt: Vec,
        v_ctrl_val_gen: int,
        qv_droop_val_gen: int,
        Vm: Vec,
        enforce_q_limits: bool = True,
        atol: float = 1e-12,
) -> Tuple[Vec, Vec]:
    """
    Split solved bus reactive power between generator-like controlling devices.

    This routine is the reactive-power post-processing counterpart of the
    generator/battery bus split. Unlike the generic quantity split, it starts
    from an already compiled fixed bus contribution ``Qfixed_bus`` that includes
    load-like injections, fixed current/admittance terms, and non-controlling
    generator-like set points captured by the numerical circuit compilation.

    The controlling residual at each bus is therefore:

    .. math::

        Qctrl_i = Qbus_i - Qfixed_i - Qdroop_i

    where ``Qdroop_i`` is the contribution of droop-controlled generators
    evaluated at the solved voltage magnitude.

    Online voltage-controlled generators and batteries share that residual
    subject to their aggregate limits. Online non-controlling generators and
    batteries keep their compiled set points. Offline devices receive zero.

    :param Qbus: Solved nodal reactive power injection.
    :param Qfixed_bus: Fixed compiled reactive contribution per bus.
    :param gen_bus_idx: Generator bus index.
    :param Qmin_gen: Generator minimum reactive power.
    :param Qmax_gen: Generator maximum reactive power.
    :param gen_status: Generator active status.
    :param control_mode_int_gen: Generator control mode codes.
    :param Q0_gen: Generator fixed reactive set point.
    :param Vset_gen: Generator voltage set points.
    :param k_droop_gen: Generator droop coefficients.
    :param dead_band_gen: Generator droop dead bands.
    :param batt_bus_idx: Battery bus index.
    :param Qmin_batt: Battery minimum reactive power.
    :param Qmax_batt: Battery maximum reactive power.
    :param batt_status: Battery active status.
    :param control_mode_int_batt: Battery control mode codes.
    :param Q0_batt: Battery fixed reactive set point.
    :param v_ctrl_val_gen: Integer code for voltage control.
    :param qv_droop_val_gen: Integer code for QV droop control.
    :param Vm: Solved bus voltage magnitudes.
    :param enforce_q_limits: Clip voltage-controller Q reports to the declared capability limits.
    :param atol: Numerical zero tolerance.
    :return: Tuple with generator and battery reactive power vectors.
    """
    n_bus: int = len(Qbus)
    n_gen: int = len(gen_bus_idx)
    n_batt: int = len(batt_bus_idx)

    q_gen: Vec = Q0_gen.copy()
    q_batt: Vec = Q0_batt.copy()

    # Start from the fixed bus decomposition built during compilation. This
    # already contains load-like terms and non-controlling generator-like Q0.
    qfixed_per_bus: Vec = Qfixed_bus.copy()
    qmin_control_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    qmax_control_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    qrange_control_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    control_count_per_bus: np.ndarray = np.zeros(n_bus, dtype=np.int64)
    qshare_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    qflat_extra_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)

    delta_v: float
    q_droop_value: float
    qmin_gen_value: float
    qmax_gen_value: float

    for gen_idx in range(n_gen):
        bus_idx = gen_bus_idx[gen_idx]

        if gen_status[gen_idx]:
            if control_mode_int_gen[gen_idx] == v_ctrl_val_gen:
                qmin_control_per_bus[bus_idx] += Qmin_gen[gen_idx]
                qmax_control_per_bus[bus_idx] += Qmax_gen[gen_idx]
                control_count_per_bus[bus_idx] += 1
            elif control_mode_int_gen[gen_idx] == qv_droop_val_gen:
                delta_v = Vset_gen[gen_idx] - Vm[bus_idx]
                q_droop_value = 0.0

                if abs(delta_v) > dead_band_gen[gen_idx]:
                    if delta_v > dead_band_gen[gen_idx]:
                        q_droop_value = (
                            (delta_v - dead_band_gen[gen_idx])
                            * k_droop_gen[gen_idx]
                            * Qmax_gen[gen_idx]
                        )
                    else:
                        if delta_v < -dead_band_gen[gen_idx]:
                            q_droop_value = (
                                (delta_v + dead_band_gen[gen_idx])
                                * k_droop_gen[gen_idx]
                                * Qmax_gen[gen_idx]
                            )
                        else:
                            q_droop_value = 0.0

                    if q_droop_value > Qmax_gen[gen_idx]:
                        q_droop_value = Qmax_gen[gen_idx]
                    else:
                        pass

                    if q_droop_value < Qmin_gen[gen_idx]:
                        q_droop_value = Qmin_gen[gen_idx]
                    else:
                        pass
                else:
                    q_droop_value = 0.0

                qfixed_per_bus[bus_idx] += q_droop_value
            else:
                pass
        else:
            pass

    for batt_idx in range(n_batt):
        bus_idx = batt_bus_idx[batt_idx]

        if batt_status[batt_idx]:
            if control_mode_int_batt[batt_idx] == v_ctrl_val_gen:
                qmin_control_per_bus[bus_idx] += Qmin_batt[batt_idx]
                qmax_control_per_bus[bus_idx] += Qmax_batt[batt_idx]
                control_count_per_bus[bus_idx] += 1
            else:
                pass
        else:
            pass

    for bus_idx in range(n_bus):
        qmin_control_value = qmin_control_per_bus[bus_idx]
        qmax_control_value = qmax_control_per_bus[bus_idx]
        qrange_control_value = qmax_control_value - qmin_control_value
        qrange_control_per_bus[bus_idx] = qrange_control_value
        qcontrol_required_value = Qbus[bus_idx] - qfixed_per_bus[bus_idx]
        control_count_value = control_count_per_bus[bus_idx]

        if control_count_value > 0:
            # Reject non-finite aggregate limits before normalizing because a
            # NaN bus capability would otherwise leak into the sharing factor.
            if np.isfinite(qrange_control_value) and np.isfinite(qcontrol_required_value):
                if qrange_control_value > atol:
                    if enforce_q_limits:
                        if qcontrol_required_value < qmin_control_value:
                            qcontrol_limited_value = qmin_control_value
                        else:
                            if qcontrol_required_value > qmax_control_value:
                                qcontrol_limited_value = qmax_control_value
                            else:
                                qcontrol_limited_value = qcontrol_required_value

                        qshare_value = (qcontrol_limited_value - qmin_control_value) / qrange_control_value

                        if qshare_value < 0.0:
                            qshare_per_bus[bus_idx] = 0.0
                        else:
                            if qshare_value > 1.0:
                                qshare_per_bus[bus_idx] = 1.0
                            else:
                                qshare_per_bus[bus_idx] = qshare_value
                    else:
                        qshare_per_bus[bus_idx] = (qcontrol_required_value - qmin_control_value) / qrange_control_value
                else:
                    qshare_per_bus[bus_idx] = 0.0
                    if not enforce_q_limits:
                        qflat_extra_per_bus[bus_idx] = (
                            (qcontrol_required_value - qmin_control_value) / control_count_value
                        )
            else:
                qshare_per_bus[bus_idx] = 0.0
        else:
            qshare_per_bus[bus_idx] = 0.0

    for gen_idx in range(n_gen):
        bus_idx = gen_bus_idx[gen_idx]

        if gen_status[gen_idx]:
            if control_mode_int_gen[gen_idx] == v_ctrl_val_gen:
                qmin_gen_value = Qmin_gen[gen_idx]
                qmax_gen_value = Qmax_gen[gen_idx]
                qrange_gen_value = qmax_gen_value - qmin_gen_value
                # Reject non-finite limits before reconstructing the device Q
                # because 0 * NaN still raises an invalid warning in NumPy.
                if np.isfinite(qmin_gen_value) and np.isfinite(qmax_gen_value):
                    if qrange_control_per_bus[bus_idx] > atol:
                        q_gen[gen_idx] = qmin_gen_value + qshare_per_bus[bus_idx] * qrange_gen_value
                    else:
                        q_gen[gen_idx] = qmin_gen_value + qflat_extra_per_bus[bus_idx]
                else:
                    q_gen[gen_idx] = 0.0
            elif control_mode_int_gen[gen_idx] == qv_droop_val_gen:
                delta_v = Vset_gen[gen_idx] - Vm[bus_idx]
                q_droop_value = 0.0

                if abs(delta_v) > dead_band_gen[gen_idx]:
                    if delta_v > dead_band_gen[gen_idx]:
                        q_droop_value = (
                            (delta_v - dead_band_gen[gen_idx])
                            * k_droop_gen[gen_idx]
                            * Qmax_gen[gen_idx]
                        )
                    else:
                        if delta_v < -dead_band_gen[gen_idx]:
                            q_droop_value = (
                                (delta_v + dead_band_gen[gen_idx])
                                * k_droop_gen[gen_idx]
                                * Qmax_gen[gen_idx]
                            )
                        else:
                            q_droop_value = 0.0

                    if q_droop_value > Qmax_gen[gen_idx]:
                        q_droop_value = Qmax_gen[gen_idx]
                    else:
                        pass

                    if q_droop_value < Qmin_gen[gen_idx]:
                        q_droop_value = Qmin_gen[gen_idx]
                    else:
                        pass
                else:
                    q_droop_value = 0.0

                q_gen[gen_idx] = q_droop_value
            else:
                q_gen[gen_idx] = Q0_gen[gen_idx]
        else:
            q_gen[gen_idx] = 0.0

    for batt_idx in range(n_batt):
        bus_idx = batt_bus_idx[batt_idx]

        if batt_status[batt_idx]:
            if control_mode_int_batt[batt_idx] == v_ctrl_val_gen:
                qmin_batt_value = Qmin_batt[batt_idx]
                qmax_batt_value = Qmax_batt[batt_idx]
                qrange_batt_value = qmax_batt_value - qmin_batt_value
                # Reject non-finite limits before reconstructing the device Q
                # because 0 * NaN still raises an invalid warning in NumPy.
                if np.isfinite(qmin_batt_value) and np.isfinite(qmax_batt_value):
                    if qrange_control_per_bus[bus_idx] > atol:
                        q_batt[batt_idx] = qmin_batt_value + qshare_per_bus[bus_idx] * qrange_batt_value
                    else:
                        q_batt[batt_idx] = qmin_batt_value + qflat_extra_per_bus[bus_idx]
                else:
                    q_batt[batt_idx] = 0.0
            else:
                q_batt[batt_idx] = Q0_batt[batt_idx]
        else:
            q_batt[batt_idx] = 0.0

    return q_gen, q_batt


def split_slack_bus_quantity_between_generators_and_batteries(
        Qbus: Vec,
        Qfixed_bus: Vec,
        slack_bus_mask: BoolVec,
        gen_bus_idx: IntVec,
        Qmin_gen: Vec,
        Qmax_gen: Vec,
        gen_status: BoolVec,
        Q0_gen: Vec,
        batt_bus_idx: IntVec,
        Qmin_batt: Vec,
        Qmax_batt: Vec,
        batt_status: BoolVec,
        Q0_batt: Vec,
        atol: float = 1e-12,
) -> Tuple[Vec, Vec]:
    """
    Split one solved bus quantity among online generator-like devices at slack buses.

    This helper is used after the main power-flow post-processing to reconstruct
    the per-device values that belong to slack buses. The solved bus quantities
    are already correct, but the slack balancing residual can remain attached
    only to the bus result instead of being reassigned to the connected online
    generators and batteries.

    The split is performed independently at every slack bus. Devices connected
    to non-slack buses preserve their input values ``Q0_gen`` and ``Q0_batt``.
    Online devices connected to slack buses share the residual bus quantity
    after subtracting the fixed bus contribution ``Qfixed_bus``. Offline devices
    receive zero.

    :param Qbus: Solved per-bus quantity to reconstruct.
    :param Qfixed_bus: Fixed per-bus contribution that does not belong to the participating slack devices.
    :param slack_bus_mask: Boolean mask marking the slack buses.
    :param gen_bus_idx: Generator bus index.
    :param Qmin_gen: Generator lower bound for the reconstructed quantity.
    :param Qmax_gen: Generator upper bound for the reconstructed quantity.
    :param gen_status: Generator active status.
    :param Q0_gen: Generator baseline values kept at non-slack buses.
    :param batt_bus_idx: Battery bus index.
    :param Qmin_batt: Battery lower bound for the reconstructed quantity.
    :param Qmax_batt: Battery upper bound for the reconstructed quantity.
    :param batt_status: Battery active status.
    :param Q0_batt: Battery baseline values kept at non-slack buses.
    :param atol: Numerical zero tolerance.
    :return: Tuple with generator and battery reconstructed values.
    """
    n_bus: int = len(Qbus)
    n_gen: int = len(gen_bus_idx)
    n_batt: int = len(batt_bus_idx)

    q_gen: Vec = Q0_gen.copy()
    q_batt: Vec = Q0_batt.copy()

    qfixed_per_bus: Vec = Qfixed_bus.copy()
    qmin_control_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    qmax_control_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    qrange_control_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    control_count_per_bus: np.ndarray = np.zeros(n_bus, dtype=np.int64)
    qshare_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)
    qflat_extra_per_bus: Vec = np.zeros(n_bus, dtype=np.float64)

    gen_idx: int
    batt_idx: int
    bus_idx: int

    for gen_idx in range(n_gen):
        bus_idx = gen_bus_idx[gen_idx]

        if gen_status[gen_idx]:
            if slack_bus_mask[bus_idx]:
                qmin_control_per_bus[bus_idx] += Qmin_gen[gen_idx]
                qmax_control_per_bus[bus_idx] += Qmax_gen[gen_idx]
                control_count_per_bus[bus_idx] += 1
            else:
                qfixed_per_bus[bus_idx] += Q0_gen[gen_idx]
        else:
            pass

    for batt_idx in range(n_batt):
        bus_idx = batt_bus_idx[batt_idx]

        if batt_status[batt_idx]:
            if slack_bus_mask[bus_idx]:
                qmin_control_per_bus[bus_idx] += Qmin_batt[batt_idx]
                qmax_control_per_bus[bus_idx] += Qmax_batt[batt_idx]
                control_count_per_bus[bus_idx] += 1
            else:
                qfixed_per_bus[bus_idx] += Q0_batt[batt_idx]
        else:
            pass

    for bus_idx in range(n_bus):
        qmin_control_value: float = qmin_control_per_bus[bus_idx]
        qmax_control_value: float = qmax_control_per_bus[bus_idx]
        qrange_control_value: float = qmax_control_value - qmin_control_value
        qrange_control_per_bus[bus_idx] = qrange_control_value
        qcontrol_required_value: float = Qbus[bus_idx] - qfixed_per_bus[bus_idx]
        control_count_value: int = int(control_count_per_bus[bus_idx])

        if slack_bus_mask[bus_idx]:
            if control_count_value > 0:
                # The slack-bus report path also needs finite inputs before
                # normalizing because it intentionally skips clipping.
                if np.isfinite(qrange_control_value) and np.isfinite(qcontrol_required_value):
                    if qrange_control_value > atol:
                        # Slack-bus reporting must reproduce the solved bus balance
                        # exactly, even when the final value exceeds the declared
                        # operating limits. Therefore the normalized factor is not
                        # clipped to [0, 1] here.
                        qshare_per_bus[bus_idx] = (
                            (qcontrol_required_value - qmin_control_value) / qrange_control_value
                        )
                    else:
                        qshare_per_bus[bus_idx] = 0.0
                        qflat_extra_per_bus[bus_idx] = (
                            (qcontrol_required_value - qmin_control_value) / control_count_value
                        )
                else:
                    qshare_per_bus[bus_idx] = 0.0
                    qflat_extra_per_bus[bus_idx] = 0.0
            else:
                qshare_per_bus[bus_idx] = 0.0
        else:
            qshare_per_bus[bus_idx] = 0.0

    for gen_idx in range(n_gen):
        bus_idx = gen_bus_idx[gen_idx]

        if gen_status[gen_idx]:
            if slack_bus_mask[bus_idx]:
                qmin_gen_value: float = Qmin_gen[gen_idx]
                qmax_gen_value: float = Qmax_gen[gen_idx]
                qrange_gen_value: float = qmax_gen_value - qmin_gen_value
                if np.isfinite(qmin_gen_value) and np.isfinite(qmax_gen_value):
                    if qrange_control_per_bus[bus_idx] > atol:
                        q_gen[gen_idx] = qmin_gen_value + qshare_per_bus[bus_idx] * qrange_gen_value
                    else:
                        q_gen[gen_idx] = qmin_gen_value + qflat_extra_per_bus[bus_idx]
                else:
                    q_gen[gen_idx] = 0.0
            else:
                q_gen[gen_idx] = Q0_gen[gen_idx]
        else:
            q_gen[gen_idx] = 0.0

    for batt_idx in range(n_batt):
        bus_idx = batt_bus_idx[batt_idx]

        if batt_status[batt_idx]:
            if slack_bus_mask[bus_idx]:
                qmin_batt_value: float = Qmin_batt[batt_idx]
                qmax_batt_value: float = Qmax_batt[batt_idx]
                qrange_batt_value: float = qmax_batt_value - qmin_batt_value
                if np.isfinite(qmin_batt_value) and np.isfinite(qmax_batt_value):
                    if qrange_control_per_bus[bus_idx] > atol:
                        q_batt[batt_idx] = qmin_batt_value + qshare_per_bus[bus_idx] * qrange_batt_value
                    else:
                        q_batt[batt_idx] = qmin_batt_value + qflat_extra_per_bus[bus_idx]
                else:
                    q_batt[batt_idx] = 0.0
            else:
                q_batt[batt_idx] = Q0_batt[batt_idx]
        else:
            q_batt[batt_idx] = 0.0

    return q_gen, q_batt
