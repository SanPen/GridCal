# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import scipy.sparse as sp


def compute_connectivity(branch_active, Cf_, Ct_):
    """
    Compute the from and to connectivity matrices applying the branch states
    :param branch_active: array of branch states
    :param Cf_: Connectivity branch-bus "from"
    :param Ct_: Connectivity branch-bus "to"
    :return: Final Ct and Cf in CSC format
    """
    br_states_diag = sp.diags(branch_active)
    Cf = br_states_diag * Cf_
    Ct = br_states_diag * Ct_

    return Cf.tocsc(), Ct.tocsc()


def compute_admittances(R, X, G, B, k, tap_module, vtap_f, vtap_t, tap_angle, Beq, If, Cf, Ct, G0, a, b, c, Yshunt_bus):
    """
    Compute the complete admittance matrices for the general power flow methods (Newton-Raphson based)
    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param k: array of converter values: 1 for regular branches, sqrt(3) / 2 for VSC
    :param tap_module: array of tap modules (for all branches, regardless of their type)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param tap_angle: array of tap angles (for all branches, regardless of their type)
    :param Beq: Array of equivalent susceptance
    :param If: Array of currents "from" in all the branches
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param G0:
    :param a:
    :param b:
    :param c:
    :param Yshunt_bus: array of shunts equivalent power per bus, from the shunt devices (p.u.)
    :return: Ybus, Yf, Yt
    """

    # compute G-switch
    Gsw = G0 + a * np.power(If, 2) + b * If + c

    # form the admittance matrices
    ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
    bc2 = (G + 1j * B) / 2.0  # shunt admittance
    # k is already filled with the appropriate value for each type of branch
    mp = k * tap_module

    # compose the primitives
    Yff = Gsw + (ys + bc2 + 1.0j * Beq) / (mp * mp * vtap_f * vtap_f)
    Yft = -ys / (mp * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t)
    Ytf = -ys / (mp * np.exp(1.0j * tap_angle) * vtap_t * vtap_f)
    Ytt = (ys + bc2) / (vtap_t * vtap_t)

    # compose the matrices
    Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
    Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
    Ybus = Cf.T * Yf + Ct.T * Yt + sp.diags(Yshunt_bus)

    return Admittance(Ybus, Yf, Yt, Cf, Ct, Yff, Yft, Ytf, Ytt, Yshunt_bus, Gsw)


def compile_y_acdc(Cf, Ct, C_bus_shunt, shunt_admittance, shunt_active, ys, B, Sbase,
                   m, theta, Beq, Gsw, mf, mt):
    """
    Compile the admittance matrices using the variable elements
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param C_bus_shunt:
    :param shunt_admittance:
    :param shunt_active:
    :param ys:
    :param B:
    :param Sbase:
    :param m: array of tap modules (for all branches, regardless of their type)
    :param theta: array of tap angles (for all branches, regardless of their type)
    :param Beq: Array of equivalent susceptance
    :param Gsw: Array of branch (converter) losses
    :param mf: array of virtual taps at the "from" side
    :param mt: array of virtual taps at the "to" side
    :return: Ybus, Yf, Yt, tap
    """

    # SHUNT --------------------------------------------------------------------------------------------------------
    Yshunt_from_devices = C_bus_shunt * (shunt_admittance * shunt_active / Sbase)
    yshunt_f = Cf * Yshunt_from_devices
    yshunt_t = Ct * Yshunt_from_devices

    # form the admittance matrices ---------------------------------------------------------------------------------
    bc2 = 1j * B / 2  # shunt conductance
    # mp = circuit.k * m  # k is already filled with the appropriate value for each type of branch

    tap = m * np.exp(1.0j * theta)

    # compose the primitives
    Yff = Gsw + (ys + bc2 + 1.0j * Beq + yshunt_f) / (m * m * mf * mf)
    Yft = -ys / (np.conj(tap) * mf * mt)
    Ytf = -ys / (tap * mf * mt)
    Ytt = ys + bc2 + yshunt_t / (mt * mt)

    # compose the matrices
    Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
    Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
    Ybus = sp.csc_matrix(Cf.T * Yf + Ct.T * Yt)

    return Ybus, Yf.tocsc(), Yt.tocsc(), tap


def compute_split_admittances(R, X, G, B, k, m, mf, mt, theta, Beq, If, Cf, Ct, G0, a, b, c, Yshunt_bus):
    """
    Compute the complete admittance matrices for the helm method and others that may require them
    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param k: array of converter values: 1 for regular branches, sqrt(3) / 2 for VSC
    :param m: array of tap modules (for all branches, regardless of their type)
    :param mf: array of virtual taps at the "from" side
    :param mt: array of virtual taps at the "to" side
    :param theta: array of tap angles (for all branches, regardless of their type)
    :param Beq: Array of equivalent susceptance
    :param If: Array of currents "from" in all the branches
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param G0:
    :param Inom:
    :param Yshunt_bus: array of shunts equivalent power per bus (p.u.)
    :return: Ybus, Yf, Yt
    """

    Gsw = G0 + a * np.power(If, 2) + b * If + c

    ys = 1.0 / (R + 1.0j * X)  # series admittance
    ysh = (G + 1j * B) / 2  # shunt admittance

    # k is already filled with the appropriate value for each type of branch
    tap = k * m * np.exp(1.0j * theta)

    # compose the primitives
    Yffs = Gsw + ys / (tap * np.conj(tap) * mf * mf)
    Yfts = - ys / (np.conj(tap) * mf * mt)
    Ytfs = - ys / (tap * mt * mf)
    Ytts = ys / (mt * mt)

    # compose the matrices
    Yfs = sp.diags(Yffs) * Cf + sp.diags(Yfts) * Ct
    Yts = sp.diags(Ytfs) * Cf + sp.diags(Ytts) * Ct
    Yseries = Cf.T * Yfs + Ct.T * Yts
    Yshunt = Cf.T * ysh + Ct.T * ysh + Yshunt_bus

    GBc = G + 1.0j * B
    Gsh = GBc / 2.0
    Ysh = Yshunt_bus + Cf.T * Gsh + Ct.T * Gsh

    return Yseries, Yshunt


def compute_fast_decoupled_admittances(X, B, m, mf, mt, Cf, Ct):
    """
    Compute the admittance matrices for the fast decoupled method
    :param X: array of branch reactance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param m: array of tap modules (for all branches, regardless of their type)
    :param mf: array of virtual taps at the "from" side
    :param mt: array of virtual taps at the "to" side
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :return: B' and B''
    """

    b1 = 1.0 / (X + 1e-20)
    b1_tt = sp.diags(b1)
    B1f = b1_tt * Cf - b1_tt * Ct
    B1t = -b1_tt * Cf + b1_tt * Ct
    B1 = Cf.T * B1f + Ct.T * B1t

    b2 = b1 + B
    b2_ff = -(b2 / (m * np.conj(m)) * mf * mf).real
    b2_ft = -(b1 / (np.conj(m) * mf * mt)).real
    b2_tf = -(b1 / (m * mt * mf)).real
    b2_tt = - b2 / (mt * mt)

    B2f = -sp.diags(b2_ff) * Cf + sp.diags(b2_ft) * Ct
    B2t = sp.diags(b2_tf) * Cf - sp.diags(b2_tt) * Ct
    B2 = Cf.T * B2f + Ct.T * B2t

    return B1.tocsc(), B2.tocsc()


def compute_linear_admittances(nbr, X, R, m, active, Cf, Ct, ac, dc):
    """
    Compute the linear admittances for methods such as the "DC power flow" of the PTDF
    :param nbr: Number of branches
    :param X: array of branch reactance (p.u.)
    :param R: array of branch resistance (p.u.)
    :param m: array of tap modules (for all branches, regardless of their type)
    :param active: array of branch active (bool)
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param ac: array of ac branches indices
    :param dc: array of dc branches indices
    :return: Bbus, Bf, Btheta
    """

    m_abs = np.abs(m)
    if len(dc):
        # compose the vector for AC-DC grids where the R is needed for this matrix
        # even if conceptually we only want the susceptance
        b = np.zeros(nbr)
        b[ac] = 1.0 / (m_abs[ac] * X[ac] * active[ac] + 1e-20)  # for ac branches
        b[dc] = 1.0 / (m_abs[dc] * R[dc] * active[dc] + 1e-20)  # for dc branches
    else:
        b = 1.0 / (m_abs * X * active + 1e-20)  # for ac branches

    b_tt = sp.diags(b)  # This is Bd from the
    Bf = b_tt * Cf - b_tt * Ct
    Bt = -b_tt * Cf + b_tt * Ct
    Bbus = Cf.T * Bf + Ct.T * Bt
    Btheta = (b_tt * (Cf + Ct)).T

    """
    According to the KULeuven document "DC power flow in unit commitment models"
    The DC power flow is:
    
    Pbus = (A^T x Bd x A) x bus_angles + (Bd x A)^T x branch_angles
    
    Identifying the already computed matrices, it becomes:
    
    Pbus = Bbus x bus_angles + Btheta x branch_angles
    
    If we solve for bus angles:
    
    bus_angles = Bbus^-1 x (Pbus - Btheta x branch_angles)
    """

    return Bbus, Bf, Btheta


class Admittance:

    def __init__(self, Ybus, Yf, Yt, Cf, Ct, yff, yft, ytf, ytt, Yshunt_bus, Gsw):

        self.Ybus = Ybus

        self.Yf = Yf

        self.Yt = Yt

        self.Cf = Cf

        self.Ct = Ct

        self.yff = yff

        self.yft = yft

        self.ytf = ytf

        self.ytt = ytt

        self.Yshunt_bus = Yshunt_bus

        self.Gsw = Gsw

    def modify_taps(self, m, m2, idx=None):
        """
        Compute the new admittance matrix given the tap variation
        :param m: previous tap
        :param m2: new tap
        :param idx: indices that apply, if none assumes that m and m2 length math yff etc...
        :return: Ybus, Yf, Yt
        """

        if idx is None:
            yff = ((self.yff - self.Gsw) * (m * m) / (m2 * m2)) + self.Gsw
            yft = self.yft * m / m2
            ytf = self.ytf * m / m2
            ytt = self.ytt
        else:
            yff = self.yff.copy()
            yft = self.yft.copy()
            ytf = self.ytf.copy()
            ytt = self.ytt.copy()

            yff[idx] = ((yff[idx] - self.Gsw[idx]) * (m * m) / (m2 * m2)) + self.Gsw[idx]
            yft[idx] = yft[idx] * m / m2
            ytf[idx] = ytf[idx] * m / m2

        # compose the matrices
        Yf = sp.diags(yff) * self.Cf + sp.diags(yft) * self.Ct
        Yt = sp.diags(ytf) * self.Cf + sp.diags(ytt) * self.Ct
        Ybus = self.Cf.T * Yf + self.Ct.T * Yt + sp.diags(self.Yshunt_bus)

        return Ybus, Yf, Yt
