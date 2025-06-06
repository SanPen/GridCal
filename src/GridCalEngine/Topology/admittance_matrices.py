# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


import numpy as np
import scipy.sparse as sp
from typing import Union, Tuple, List
from GridCalEngine.enumerations import WindingsConnection
from GridCalEngine.basic_structures import ObjVec, Vec, CxVec, IntVec


class AdmittanceMatrices:
    """
    Class to store admittance matrices
    """

    def __init__(self,
                 Ybus: sp.csc_matrix,
                 Yf: sp.csc_matrix,
                 Yt: sp.csc_matrix,
                 Cf: sp.csc_matrix,
                 Ct: sp.csc_matrix,
                 yff: CxVec,
                 yft: CxVec,
                 ytf: CxVec,
                 ytt: CxVec,
                 Yshunt_bus: CxVec):
        """
        Constructor
        :param Ybus: Admittance matrix
        :param Yf: Admittance matrix of the branches with their "from" bus
        :param Yt: Admittance matrix of the branches with their "to" bus
        :param Cf: Connectivity matrix of the branches with their "from" bus
        :param Ct: Connectivity matrix of the branches with their "to" bus
        :param yff: admittance from-from primitives vector
        :param yft: admittance from-to primitives vector
        :param ytf: admittance to-from primitives vector
        :param ytt: admittance to-to primitives vector
        :param Yshunt_bus: array of shunt admittances per bus
        """
        self.Ybus = Ybus if Ybus.format == 'csc' else Ybus.tocsc()

        self.Yf = Yf if Yf.format == 'csc' else Yf.tocsc()

        self.Yt = Yt if Yt.format == 'csc' else Yt.tocsc()

        self.Cf = Cf if Cf.format == 'csc' else Cf.tocsc()

        self.Ct = Ct if Ct.format == 'csc' else Ct.tocsc()

        self.yff = yff

        self.yft = yft

        self.ytf = ytf

        self.ytt = ytt

        self.Yshunt_bus = Yshunt_bus

    def modify_taps(self, m: Vec, m2: Vec, tau: Vec, tau2: Vec,
                    idx: Union[IntVec, None] = None) -> Tuple[sp.csc_matrix, sp.csc_matrix, sp.csc_matrix]:
        """
        Compute the new admittance matrix given the tap variation
        :param m: previous tap module
        :param m2: new tap module
        :param tau: previous tap angle
        :param tau2: new tap angle
        :param idx: indices that apply, if none assumes that m and m2 length math yff etc...
        :return: Ybus, Yf, Yt
        """

        if idx is None:
            # update all primitives
            self.yff = (self.yff * (m * m) / (m2 * m2))
            self.yft = self.yft * (m * np.exp(-1.0j * tau)) / (m2 * np.exp(-1.0j * tau2))
            self.ytf = self.ytf * (m * np.exp(1.0j * tau)) / (m2 * np.exp(1.0j * tau2))
            self.ytt = self.ytt
        else:
            # add arrays must have the same size as idx
            lidx = len(idx)
            assert len(m) == lidx
            assert len(m2) == lidx
            assert len(tau) == lidx
            assert len(tau2) == lidx

            # update primitives signaled by idx
            self.yff[idx] = (self.yff[idx] * (m * m) / (m2 * m2))
            self.yft[idx] = self.yft[idx] * (m * np.exp(-1.0j * tau)) / (m2 * np.exp(-1.0j * tau2))
            self.ytf[idx] = self.ytf[idx] * (m * np.exp(1.0j * tau)) / (m2 * np.exp(1.0j * tau2))
            self.ytt[idx] = self.ytt[idx]

        # update the matrices
        self.Yf = sp.diags(self.yff) * self.Cf + sp.diags(self.yft) * self.Ct
        self.Yt = sp.diags(self.ytf) * self.Cf + sp.diags(self.ytt) * self.Ct
        self.Ybus = self.Cf.T * self.Yf + self.Ct.T * self.Yt + sp.diags(self.Yshunt_bus)

        return self.Ybus, self.Yf, self.Yt

    def copy(self) -> "AdmittanceMatrices":
        """
        Get a deep copy
        """
        return AdmittanceMatrices(Ybus=self.Ybus.copy(),
                                  Yf=self.Yf.copy(),
                                  Yt=self.Yt.copy(),
                                  Cf=self.Cf.copy(),
                                  Ct=self.Ct.copy(),
                                  yff=self.yff.copy(),
                                  yft=self.yft.copy(),
                                  ytf=self.ytf.copy(),
                                  ytt=self.ytt.copy(),
                                  Yshunt_bus=self.Yshunt_bus.copy())


def compute_admittances(R: Vec,
                        X: Vec,
                        G: Vec,
                        B: Vec,
                        tap_module: Vec,
                        vtap_f: Vec,
                        vtap_t: Vec,
                        tap_angle: Vec,
                        Cf: sp.csc_matrix,
                        Ct: sp.csc_matrix,
                        Yshunt_bus: CxVec,
                        conn: Union[List[WindingsConnection], ObjVec],
                        seq: int,
                        add_windings_phase: bool = False) -> AdmittanceMatrices:
    """
    Compute the complete admittance matrices for the general power flow methods (Newton-Raphson based)

    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param tap_angle: array of tap angles (for all Branches, regardless of their type)
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param Yshunt_bus: array of shunts equivalent power per bus, from the shunt devices (p.u.)
    :param seq: Sequence [0, 1, 2]
    :param conn: array of windings connections (numpy array of WindingsConnection)
    :param add_windings_phase: Add the phases of the transformer windings (for short circuits mainly)
    :return: Admittance instance
    """

    # compute G-switch
    # Gsw = G0sw + a * np.power(If, 2) + b * If + c

    # form the admittance matrices
    ys = 1.0 / (R + 1.0j * (X + 1e-20))  # series admittance
    ysh_2 = (G + 1j * B) / 2.0  # shunt admittance

    # compose the primitives
    if add_windings_phase:

        r30_deg = np.exp(1.0j * np.pi / 6.0)

        if seq == 0:  # zero sequence
            # add always the shunt term, the series depends on the connection
            # one ys vector for the from side, another for the to side, and the shared one
            ysf = np.zeros(len(ys), dtype=complex)
            yst = np.zeros(len(ys), dtype=complex)
            ysft = np.zeros(len(ys), dtype=complex)

            for i, con in enumerate(conn):
                if con == WindingsConnection.GG:
                    ysf[i] = ys[i]
                    yst[i] = ys[i]
                    ysft[i] = ys[i]
                elif con == WindingsConnection.GD:
                    ysf[i] = ys[i]

            yff = (ysf + ysh_2) / (tap_module * tap_module * vtap_f * vtap_f)
            yft = -ysft / (tap_module * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t)
            ytf = -ysft / (tap_module * np.exp(+1.0j * tap_angle) * vtap_t * vtap_f)
            ytt = (yst + ysh_2) / (vtap_t * vtap_t)

        elif seq == 2:  # negative sequence
            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1
                                   for con in conn])

            yff = (ys + ysh_2) / (tap_module * tap_module * vtap_f * vtap_f)
            yft = -ys / (tap_module * np.exp(+1.0j * tap_angle) * vtap_f * vtap_t) * np.conj(factor_psh)
            ytf = -ys / (tap_module * np.exp(-1.0j * tap_angle) * vtap_t * vtap_f) * factor_psh
            ytt = (ys + ysh_2) / (vtap_t * vtap_t)

        elif seq == 1:  # positive sequence

            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1.0
                                   for con in conn])

            yff = (ys + ysh_2) / (tap_module * tap_module * vtap_f * vtap_f)
            yft = -ys / (tap_module * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t) * factor_psh
            ytf = -ys / (tap_module * np.exp(1.0j * tap_angle) * vtap_t * vtap_f) * np.conj(factor_psh)
            ytt = (ys + ysh_2) / (vtap_t * vtap_t)
        else:
            raise Exception('Unsupported sequence when computing the admittance matrix sequence={}'.format(seq))

    else:  # original

        yff = (ys + ysh_2) / (tap_module * tap_module * vtap_f * vtap_f)
        yft = -ys / (tap_module * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t)
        ytf = -ys / (tap_module * np.exp(1.0j * tap_angle) * vtap_t * vtap_f)
        ytt = (ys + ysh_2) / (vtap_t * vtap_t)

    # compose the matrices
    Yf = sp.diags(yff) * Cf + sp.diags(yft) * Ct
    Yt = sp.diags(ytf) * Cf + sp.diags(ytt) * Ct
    Ybus = Cf.T * Yf + Ct.T * Yt + sp.diags(Yshunt_bus)

    return AdmittanceMatrices(Ybus.tocsc(), Yf.tocsc(), Yt.tocsc(), Cf.tocsc(), Ct.tocsc(),
                              yff, yft, ytf, ytt, Yshunt_bus)


def compute_passive_admittances(R: Vec,
                                X: Vec,
                                G: Vec,
                                B: Vec,
                                vtap_f: Vec,
                                vtap_t: Vec,
                                Cf: sp.csc_matrix,
                                Ct: sp.csc_matrix,
                                Yshunt_bus: CxVec,
                                conn: Union[List[WindingsConnection], ObjVec],
                                seq: int,
                                add_windings_phase: bool = False) -> AdmittanceMatrices:
    """
    Compute the complete admittance matrices only using passive elements

    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param Yshunt_bus: array of shunts equivalent power per bus, from the shunt devices (p.u.)
    :param seq: Sequence [0, 1, 2]
    :param conn: array of windings connections (numpy array of WindingsConnection)
    :param add_windings_phase: Add the phases of the transformer windings (for short circuits mainly)
    :return: Admittance instance
    """

    # form the admittance matrices
    ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
    bc2 = (G + 1j * B) / 2.0  # shunt admittance

    # compose the primitives
    if add_windings_phase:
        r30_deg = np.exp(1.0j * np.pi / 6.0)

        if seq == 0:  # zero sequence
            # add always the shunt term, the series depends on the connection
            # one ys vector for the from side, another for the to side, and the shared one
            ysf = np.zeros(len(ys), dtype=complex)
            yst = np.zeros(len(ys), dtype=complex)
            ysft = np.zeros(len(ys), dtype=complex)

            for i, con in enumerate(conn):
                if con == WindingsConnection.GG:
                    ysf[i] = ys[i]
                    yst[i] = ys[i]
                    ysft[i] = ys[i]
                elif con == WindingsConnection.GD:
                    ysf[i] = ys[i]

            yff = (ysf + bc2) / (vtap_f * vtap_f)
            yft = -ysft / (vtap_f * vtap_t)
            ytf = -ysft / (vtap_t * vtap_f)
            ytt = (yst + bc2) / (vtap_t * vtap_t)

        elif seq == 2:  # negative sequence
            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1
                                   for con in conn])

            yff = (ys + bc2) / (vtap_f * vtap_f)
            yft = -ys / (vtap_f * vtap_t) * factor_psh
            ytf = -ys / (vtap_t * vtap_f) * np.conj(factor_psh)
            ytt = (ys + bc2) / (vtap_t * vtap_t)

        elif seq == 1:  # positive sequence

            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1.0
                                   for con in conn])

            yff = (ys + bc2) / (vtap_f * vtap_f)
            yft = -ys / (vtap_f * vtap_t) * factor_psh
            ytf = -ys / (vtap_t * vtap_f) * np.conj(factor_psh)
            ytt = (ys + bc2) / (vtap_t * vtap_t)
        else:
            raise Exception('Unsupported sequence when computing the admittance matrix sequence={}'.format(seq))

    else:  # original
        yff = (ys + bc2) / (vtap_f * vtap_f)
        yft = -ys / (vtap_f * vtap_t)
        ytf = -ys / (vtap_t * vtap_f)
        ytt = (ys + bc2) / (vtap_t * vtap_t)

    # compose the matrices
    Yf = sp.diags(yff) * Cf + sp.diags(yft) * Ct
    Yt = sp.diags(ytf) * Cf + sp.diags(ytt) * Ct
    Ybus = Cf.T * Yf + Ct.T * Yt + sp.diags(Yshunt_bus)

    return AdmittanceMatrices(Ybus, Yf, Yt, Cf, Ct, yff, yft, ytf, ytt, Yshunt_bus)


def compute_tap_control_admittances_injectins(
        tap_module: Vec,
        tap_angle: Vec,
        Cf: sp.csc_matrix,
        Ct: sp.csc_matrix,
        seq: int,
        conn: Union[List[WindingsConnection], ObjVec],
        add_windings_phase: bool = False) -> Tuple[CxVec, CxVec, CxVec, CxVec]:
    """
    Compute the complete admittance matrices for the general power flow methods (Newton-Raphson based)

    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param tap_angle: array of tap angles (for all Branches, regardless of their type)
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param seq: Sequence [0, 1, 2]
    :param conn: array of windings connections (numpy array of WindingsConnection)
    :param add_windings_phase: Add the phases of the transformer windings (for short circuits mainly)
    :return: Admittance instance
    """

    # compose the primitives
    if add_windings_phase:
        r30_deg = np.exp(1.0j * np.pi / 6.0)

        if seq == 0:  # zero sequence

            Yff = 1.0 / (tap_module * tap_module)
            Yft = -1.0 / (tap_module * np.exp(-1.0j * tap_angle))
            Ytf = -1.0 / (tap_module * np.exp(+1.0j * tap_angle))
            Ytt = np.zeros_like(tap_module)

        elif seq == 2:  # negative sequence
            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1
                                   for con in conn])

            Yff = 1.0 / (tap_module * tap_module)
            Yft = -1.0 / (tap_module * np.exp(+1.0j * tap_angle)) * factor_psh
            Ytf = -1.0 / (tap_module * np.exp(-1.0j * tap_angle)) * np.conj(factor_psh)
            Ytt = np.zeros_like(tap_module)

        elif seq == 1:  # positive sequence

            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1.0
                                   for con in conn])

            Yff = 1.0 / (tap_module * tap_module)
            Yft = -1.0 / (tap_module * np.exp(-1.0j * tap_angle)) * factor_psh
            Ytf = -1.0 / (tap_module * np.exp(1.0j * tap_angle)) * np.conj(factor_psh)
            Ytt = np.zeros_like(tap_module)
        else:
            raise Exception('Unsupported sequence when computing the admittance matrix sequence={}'.format(seq))

    else:  # original
        Yff = 1.0 / (tap_module * tap_module)
        Yft = -1.0 / (tap_module * np.exp(-1.0j * tap_angle))
        Ytf = -1.0 / (tap_module * np.exp(1.0j * tap_angle))
        Ytt = np.zeros_like(tap_module)

    # Yf_bus = Cf.T @ Yff + Ct.T @ Yft
    # Yt_bus = Cf.T @ Ytf

    return Yff, Yft, Ytf, Ytt


def compile_y_acdc(Cf: sp.csc_matrix,
                   Ct: sp.csc_matrix,
                   C_bus_shunt: sp.csc_matrix,
                   shunt_admittance: CxVec,
                   shunt_active: IntVec,
                   ys: CxVec,
                   B: Vec,
                   Sbase: float,
                   tap_module: Vec,
                   tap_angle: Vec,
                   Beq: Vec,
                   Gsw: Vec,
                   virtual_tap_from: Vec,
                   virtual_tap_to: Vec) -> Tuple[
    sp.csc_matrix, sp.csc_matrix, sp.csc_matrix, CxVec, CxVec, CxVec, CxVec, CxVec]:
    """
    Compile the admittance matrices using the variable elements
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param C_bus_shunt:
    :param shunt_admittance:
    :param shunt_active:
    :param ys: array of branch series admittances
    :param B: array of branch susceptances
    :param Sbase: base power (i.e. 100 MVA)
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param tap_angle: array of tap angles (for all Branches, regardless of their type)
    :param Beq: Array of equivalent susceptance
    :param Gsw: Array of branch (converter) losses
    :param virtual_tap_from: array of virtual taps at the "from" side
    :param virtual_tap_to: array of virtual taps at the "to" side
    :return: Ybus, Yf, Yt, tap
    """

    # SHUNT --------------------------------------------------------------------------------------------------------
    Yshunt_from_devices = C_bus_shunt * (shunt_admittance * shunt_active / Sbase)
    yshunt_f = Cf * Yshunt_from_devices
    yshunt_t = Ct * Yshunt_from_devices

    # form the admittance matrices ---------------------------------------------------------------------------------
    bc2 = 1j * B / 2  # shunt conductance
    # mp = circuit.k * m  # k is already filled with the appropriate value for each type of branch

    tap = tap_module * np.exp(1.0j * tap_angle)

    # compose the primitives
    yff = Gsw + (ys + bc2 + 1.0j * Beq + yshunt_f) / (tap_module * tap_module * virtual_tap_from * virtual_tap_from)
    yft = -ys / (np.conj(tap) * virtual_tap_from * virtual_tap_to)
    ytf = -ys / (tap * virtual_tap_from * virtual_tap_to)
    ytt = ys + bc2 + yshunt_t / (virtual_tap_to * virtual_tap_to)

    # compose the matrices
    Yf = sp.diags(yff) * Cf + sp.diags(yft) * Ct
    Yt = sp.diags(ytf) * Cf + sp.diags(ytt) * Ct
    Ybus = sp.csc_matrix(Cf.T * Yf + Ct.T * Yt)

    return Ybus, Yf.tocsc(), Yt.tocsc(), tap, yff, yft, ytf, ytt


class SeriesAdmittanceMatrices:
    """
    Admittance matrices for HELM and the AC linear methods
    """

    def __init__(self, Yseries: sp.csc_matrix, Yshunt: CxVec):
        self.Yseries = Yseries
        self.Yshunt = Yshunt


def compute_split_admittances(R: Vec,
                              X: Vec,
                              G: Vec,
                              B: Vec,
                              active: IntVec,
                              tap_module: Vec,
                              vtap_f: Vec,
                              vtap_t: Vec,
                              tap_angle: Vec,
                              Cf: sp.csc_matrix,
                              Ct: sp.csc_matrix,
                              Yshunt_bus: CxVec) -> SeriesAdmittanceMatrices:
    """
    Compute the complete admittance matrices for the helm method and others that may require them
    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param active: array of active branches (bool)
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param tap_angle: array of tap angles (for all Branches, regardless of their type)
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param Yshunt_bus: array of shunts equivalent power per bus (p.u.)
    :return: Yseries, Yshunt
    """

    ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
    ysh = (G + 1j * B) / 2  # shunt admittance

    # k is already filled with the appropriate value for each type of branch
    tap = tap_module * np.exp(1.0j * tap_angle)

    # compose the primitives
    yff = ys / (tap * np.conj(tap) * vtap_f * vtap_f)
    yft = - ys / (np.conj(tap) * vtap_f * vtap_t)
    ytf = - ys / (tap * vtap_t * vtap_f)
    ytt = ys / (vtap_t * vtap_t)

    yff *= active
    yft *= active
    ytf *= active
    ytt *= active

    # compose the matrices
    Yfs = sp.diags(yff) * Cf + sp.diags(yft) * Ct
    Yts = sp.diags(ytf) * Cf + sp.diags(ytt) * Ct
    Yseries = Cf.T * Yfs + Ct.T * Yts
    Yshunt = Cf.T * ysh + Ct.T * ysh + Yshunt_bus

    # GBc = G + 1.0j * B
    # Gsh = GBc / 2.0
    # Ysh = Yshunt_bus + Cf.T * Gsh + Ct.T * Gsh

    return SeriesAdmittanceMatrices(Yseries, Yshunt)


class FastDecoupledAdmittanceMatrices:
    """
    Admittance matrices for Fast decoupled method
    """

    def __init__(self, B1: sp.csc_matrix, B2: sp.csc_matrix):
        self.B1 = B1
        self.B2 = B2


def compute_fast_decoupled_admittances(X: Vec,
                                       B: Vec,
                                       tap_module: Vec,
                                       active: IntVec,
                                       vtap_f: Vec,
                                       vtap_t: Vec,
                                       Cf: sp.csc_matrix,
                                       Ct: sp.csc_matrix) -> FastDecoupledAdmittanceMatrices:
    """
    Compute the admittance matrices for the fast decoupled method
    :param X: array of branch reactance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param active: array of active branches (bool)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :return: B' and B''
    """

    b1 = active / (X + 1e-20)
    b1_tt = sp.diags(b1)
    B1f = b1_tt * Cf - b1_tt * Ct
    B1t = -b1_tt * Cf + b1_tt * Ct
    B1 = Cf.T * B1f + Ct.T * B1t

    b2 = b1 + B
    b2_ff = -(b2 / (tap_module * np.conj(tap_module)) * vtap_f * vtap_f).real
    b2_ft = -(b1 / (np.conj(tap_module) * vtap_f * vtap_t)).real
    b2_tf = -(b1 / (tap_module * vtap_t * vtap_f)).real
    b2_tt = - b2 / (vtap_t * vtap_t)

    B2f = -sp.diags(b2_ff) * Cf + sp.diags(b2_ft) * Ct
    B2t = sp.diags(b2_tf) * Cf - sp.diags(b2_tt) * Ct
    B2 = Cf.T * B2f + Ct.T * B2t

    return FastDecoupledAdmittanceMatrices(B1=B1.tocsc(), B2=B2.tocsc())


class LinearAdmittanceMatrices:
    """
    Admittance matrices for linear methods (DC power flow, PTDF, ..)
    """

    def __init__(self, Bbus: sp.csc_matrix, Bf: sp.csc_matrix, Gbus: sp.csc_matrix, Gf: sp.csc_matrix):
        self.Bbus = Bbus
        self.Bf = Bf
        self.Gbus = Gbus
        self.Gf = Gf

    def get_Bred(self, pqpv: IntVec) -> sp.csc_matrix:
        """
        Get Bred or Bpqpv for the PTDF and DC power flow
        :param pqpv: list of non-slack indices
        :return: B[pqpv, pqpv]
        """
        return self.Bbus[np.ix_(pqpv, pqpv)].tocsc()

    def get_Bslack(self, pqpv: IntVec, vd: IntVec) -> sp.csc_matrix:
        """
        Get Bslack for the PTDF and DC power flow
        :param pqpv: list of non-slack indices
        :param vd: list of slack ndices
        :return: B[pqpv, vd]
        """
        return self.Bbus[np.ix_(pqpv, vd)].tocsc()


def compute_linear_admittances(nbr: int,
                               X: Vec,
                               R: Vec,
                               m: Vec,
                               active: IntVec,
                               Cf: sp.csc_matrix,
                               Ct: sp.csc_matrix,
                               ac: IntVec,
                               dc: IntVec) -> LinearAdmittanceMatrices:
    """
    Compute the linear admittances for methods such as the "DC power flow" of the PTDF
    :param nbr: Number of Branches
    :param X: array of branch reactance (p.u.)
    :param R: array of branch resistance (p.u.)
    :param m: array of branch tap modules (p.u.)
    :param active: array of branch active (bool)
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param ac: array of ac Branches indices
    :param dc: array of dc Branches indices
    :return: Bbus, Bf
    """
    b = 1.0 / (X * active * m + 1e-20)  # for ac Branches
    b_tt = sp.diags(b)  # This is Bd from the
    Bf = b_tt * Cf - b_tt * Ct
    Bt = -b_tt * Cf + b_tt * Ct
    Bbus = Cf.T * Bf + Ct.T * Bt

    g = 1.0 / (R * active + 1e-20)  # for dc Branches
    g_tt = sp.diags(g)  # This is Bd from the
    Gf = g_tt * Cf - g_tt * Ct
    Gt = -g_tt * Cf + g_tt * Ct
    Gbus = Cf.T * Gf + Ct.T * Gt

    """
    According to the KULeuven document "DC power flow in unit commitment models"
    The DC power flow is:
    
    Pbus = (A^T x Bd x A) x bus_angles + (Bd x A)^T x branch_angles
    
    Identifying the already computed matrices, it becomes:
    
    Pbus = Bbus x bus_angles + Btau x branch_angles
    
    If we solve for bus angles:
    
    bus_angles = Bbus^-1 x (Pbus - Btau x branch_angles)
    """

    return LinearAdmittanceMatrices(Bbus=Bbus, Bf=Bf, Gbus=Gbus, Gf=Gf)
