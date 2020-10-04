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
import scipy.sparse as sp


def compute_connectivity(branch_active, Cf_, Ct_):
    """
    Compute the from and to connectivity matrices applying the branch states
    :param branch_active: array of branch states
    :param Cf_: Connectivity branch-bus "from"
    :param Ct_: Connectivity branch-bus "to"
    :return:
    """
    br_states_diag = sp.diags(branch_active)
    Cf = br_states_diag * Cf_
    Ct = br_states_diag * Ct_

    return Cf, Ct


def compute_admittances(R, X, G, B, k, m, mf, mt, theta, Beq, If, Cf, Ct, G0, a, b, c, Yshunt_bus):
    """
    Compute the complete admittance matrices for the general power flow methods (Newton-Raphson based)
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

    # compute G-switch
    Gsw = G0 + a * np.power(If, 2) + b * If + c

    # SHUNT --------------------------------------------------------------------------------------------------------
    yshunt_f = Cf * Yshunt_bus
    yshunt_t = Ct * Yshunt_bus

    # form the admittance matrices ---------------------------------------------------------------------------------

    ys = 1.0 / (R + 1.0j * X)  # series admittance
    bc2 = (G + 1j * B) / 2  # shunt admittance
    # k is already filled with the appropriate value for each type of branch
    mp = k * m

    # compose the primitives
    Yff = Gsw + (ys + bc2 + 1.0j * Beq + yshunt_f) / (mp * mp * mf * mf)
    Yft = -ys / (mp * np.exp(-1.0j * theta) * mf * mt)
    Ytf = -ys / (mp * np.exp(1.0j * theta) * mt * mf)
    Ytt = (ys + bc2 + yshunt_t) / (mt * mt)

    # compose the matrices
    Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
    Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
    Ybus = sp.csc_matrix(Cf.T * Yf + Ct.T * Yt)

    return Ybus, Yf, Yt


def compute_split_admittances(R, X, G, B, k, m, mf, mt, theta, Beq, If, Cf, Ct, G0, a, b, c, Yshunt_bus):
    """
    Compute the complete admittance matrices for the general power flow methods (Newton-Raphson based)
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
    B2t = sp.diags(b2_tf) * Cf + -sp.diags(b2_tt) * Ct
    B2 = Cf.T * B2f + Ct.T * B2t

    return B1, B2


def compute_linear_admittances(X, m, Cf, Ct):
    """
    Compute the linear admittances for methods such as the "DC power flow" of the PTDF
    :param X: array of branch reactance (p.u.)
    :param m: array of tap modules (for all branches, regardless of their type)
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :return: Bbus, Bf
    """

    b = 1.0 / (np.abs(m) * X + 1e-20)

    b_tt = sp.diags(b)
    Bf = b_tt * Cf - b_tt * Ct
    Bt = -b_tt * Cf + b_tt * Ct
    Bbus = Cf.T * Bf + Ct.T * Bt

    return Bbus, Bf