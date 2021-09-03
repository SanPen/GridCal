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

import os
import time

import numpy as np
import numba as nb
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve
from scipy.sparse import lil_matrix, diags, csc_matrix

from GridCal.Engine.Core.admittance_matrices import compile_y_acdc
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.Simulations.PowerFlow.discrete_controls import control_q_inside_method
from GridCal.Engine.Simulations.PowerFlow.high_speed_fubm_jacobian import fubm_jacobian
from GridCal.Engine.basic_structures import ReactivePowerControlMode


@nb.jit(nopython=True, cache=True)
def compute_converter_losses(V, It, F, alpha1, alpha2, alpha3, iVscL):
    """
    Compute the converter losses according to the IEC 62751-2
    :param V: array of voltages
    :param It: array of currents "to"
    :param F: array of "from" bus indices of every branch
    :param alpha1: array of alpha1 parameters
    :param alpha2: array of alpha2 parameters
    :param alpha3: array of alpha3 parameters
    :param iVscL: array of VSC converter indices
    :return: switching losses array
    """
    # # Standard IEC 62751-2 Ploss Correction for VSC losses
    # Ivsc = np.abs(It[iVscL])
    # PLoss_IEC = alpha3[iVscL] * np.power(Ivsc, 2)
    # PLoss_IEC += alpha2[iVscL] * np.power(Ivsc, 2)
    # PLoss_IEC += alpha1[iVscL]
    #
    # # compute G-switch
    # Gsw = np.zeros(len(F))
    # Gsw[iVscL] = PLoss_IEC / np.power(np.abs(V[F[iVscL]]), 2)

    Gsw = np.zeros(len(F))
    for i in iVscL:
        Ivsc = np.abs(It[i])
        Ivsc2 = Ivsc * Ivsc

        # Standard IEC 62751-2 Ploss Correction for VSC losses
        PLoss_IEC = alpha3[i] * Ivsc2 + alpha2[i] * Ivsc + alpha1[i]

        # compute G-switch
        Gsw[i] = PLoss_IEC / np.power(np.abs(V[F[i]]), 2)

    return Gsw


def compute_fx(Ybus, V, Vm, Sbus, Sf, St, Pfset, Qfset, Qtset, Vmfset, Kdp, F,
               pvpq, pq, iPfsh, iQfma, iBeqz, iQtma, iPfdp, VfBeqbus, Vtmabus):
    """
    Compute the increments vector
    :param Ybus: Admittance matrix
    :param V: Voltages array
    :param Vm: Voltages module array
    :param Sbus: Array of bus power matrix
    :param Pfset: Array of Pf set values per branch
    :param Qfset: Array of Qf set values per branch
    :param Qtset: Array of Qt set values per branch
    :param Vmfset: Array of Vf module set values per branch
    :param Kdp: Array of branch droop value per branch
    :param F:
    :param T:
    :param pvpq:
    :param pq:
    :param iPfsh:
    :param iQfma:
    :param iBeqz:
    :param iQtma:
    :param iPfdp:
    :param VfBeqbus:
    :param Vtmabus:
    :return:
    """
    Scalc = V * np.conj(Ybus * V)
    mis = Scalc - Sbus  # F1(x0) & F2(x0) Power balance mismatch

    misPbus = mis[pvpq].real  # F1(x0) Power balance mismatch - Va
    misQbus = mis[pq].imag  # F2(x0) Power balance mismatch - Vm
    misPfsh = Sf[iPfsh].real - Pfset[iPfsh]  # F3(x0) Pf control mismatch
    misQfma = Sf[iQfma].imag - Qfset[iQfma]  # F4(x0) Qf control mismatch
    misBeqz = Sf[iBeqz].imag - 0  # F5(x0) Qf control mismatch
    misBeqv = mis[VfBeqbus].imag  # F6(x0) Vf control mismatch
    misVtma = mis[Vtmabus].imag  # F7(x0) Vt control mismatch
    misQtma = St[iQtma].imag - Qtset[iQtma]  # F8(x0) Qt control mismatch
    misPfdp = -Sf[iPfdp].real + Pfset[iPfdp] + Kdp[iPfdp] * (Vm[F[iPfdp]] - Vmfset[iPfdp])  # F9(x0) Pf control mismatch, Droop Pf - Pfset = Kdp*(Vmf - Vmfset)
    # -------------------------------------------------------------------------

    #  Create F vector
    # FUBM ---------------------------------------------------------------------

    df = np.r_[misPbus,  # F1(x0) Power balance mismatch - Va
               misQbus,  # F2(x0) Power balance mismatch - Vm
               misBeqv,  # F5(x0) Qf control    mismatch - Beq
               misVtma,  # F6(x0) Vf control    mismatch - Beq
               misPfsh,  # F4(x0) Qf control    mismatch - ma
               misQfma,  # F8(x0) Qt control    mismatch - ma
               misBeqz,  # F7(x0) Vt control    mismatch - ma
               misQtma,  # F3(x0) Pf control    mismatch - Theta_shift
               misPfdp]  # F9(x0) Pf control    mismatch - Theta_shift Droop

    return df, Scalc


class SolSlicer:

    def __init__(self, npq, npv, nVfBeqbus, nVtmabus, nPfsh, nQfma, nBeqz, nQtma, nPfdp):
        """
        Declare the slicing limits in the same order as the Jacobian rows
        :param npq:
        :param npv:
        :param nVfBeqbus:
        :param nVtmabus:
        :param nPfsh:
        :param nQfma:
        :param nBeqz:
        :param nQtma:
        :param nPfdp:
        """
        self.a0 = 0
        self.a1 = self.a0 + npq + npv
        self.a2 = self.a1 + npq
        self.a3 = self.a2 + nBeqz
        self.a4 = self.a3 + nVfBeqbus
        self.a5 = self.a4 + nQfma
        self.a6 = self.a5 + nQtma
        self.a7 = self.a6 + nVtmabus
        self.a8 = self.a7 + nPfsh
        self.a9 = self.a8 + nPfdp

    def split(self, dx):
        """
        Split the linear system solution
        :param dx:
        :return:
        """
        dVa = dx[self.a0:self.a1]
        dVm = dx[self.a1:self.a2]
        dBeq_z = dx[self.a2:self.a3]
        dBeq_v = dx[self.a3:self.a4]
        dma_Qf = dx[self.a4:self.a5]
        dma_Qt = dx[self.a5:self.a6]
        dma_Vt = dx[self.a6:self.a7]
        dtheta_Pf = dx[self.a7:self.a8]
        dtheta_Pd = dx[self.a8:self.a9]

        return dVa, dVm, dBeq_v, dma_Vt, dtheta_Pf, dma_Qf, dBeq_z, dma_Qt, dtheta_Pd


def NR_LS_ACDC(nc: "SnapshotData", Vbus, Sbus,
               tolerance=1e-6, max_iter=4, mu_0=1.0, acceleration_parameter=0.05,
               verbose=False, t=0, control_q=ReactivePowerControlMode.NoControl) -> NumericPowerFlowResults:
    """
    Newton-Raphson Line search with the FUBM formulation
    :param nc: SnapshotData instance
    :param tolerance: maximum error allowed
    :param max_iter: maximum number of iterations
    :param mu_0:
    :param acceleration_parameter:
    :param verbose:
    :param t:
    :param control_q:
    :return:
    """
    start = time.time()

    # initialize the variables
    nb = nc.nbus
    nl = nc.nbr
    V = Vbus
    S0 = Sbus
    Va = np.angle(V)
    Vm = np.abs(V)
    Vmfset = nc.branch_data.vf_set[:, t]
    m = nc.branch_data.m[:, t].copy()
    theta = nc.branch_data.theta[:, t].copy()
    Beq = nc.branch_data.Beq[:, t].copy()
    Gsw = nc.branch_data.G0[:, t]
    Pfset = nc.branch_data.Pfset[:, t] / nc.Sbase
    Qfset = nc.branch_data.Qfset[:, t] / nc.Sbase
    Qtset = nc.branch_data.Qfset[:, t] / nc.Sbase
    Qmin = nc.Qmin_bus[t, :]
    Qmax = nc.Qmax_bus[t, :]
    Kdp = nc.branch_data.Kdp
    k2 = nc.branch_data.k
    Cf = nc.Cf.tocsc()
    Ct = nc.Ct.tocsc()
    F = nc.F
    T = nc.T
    Ys = 1.0 / (nc.branch_data.R + 1j * nc.branch_data.X)
    Bc = nc.branch_data.B
    pq = nc.pq.copy().astype(int)
    pvpq_orig = np.r_[nc.pv, pq].astype(int)
    pvpq_orig.sort()

    # the elements of PQ that exist in the control indices Ivf and Ivt must be passed from the PQ to the PV list
    # otherwise those variables would be in two sets of equations
    i_ctrl_v = np.unique(np.r_[nc.VfBeqbus, nc.Vtmabus])
    for val in pq:
        if val in i_ctrl_v:
            pq = pq[pq != val]

    # compose the new pvpq indices à la NR
    pv = np.unique(np.r_[i_ctrl_v, nc.pv]).astype(int)
    pv.sort()
    pvpq = np.r_[pv, pq].astype(int)
    npv = len(pv)
    npq = len(pq)

    # --------------------------------------------------------------------------
    # variables dimensions in Jacobian
    sol_slicer = SolSlicer(npq, npv,
                           len(nc.VfBeqbus),
                           len(nc.Vtmabus),
                           len(nc.iPfsh),
                           len(nc.iQfma),
                           len(nc.iBeqz),
                           len(nc.iQtma),
                           len(nc.iPfdp))

    # -------------------------------------------------------------------------
    # compute initial admittances
    Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                       C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                       shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                       shunt_active=nc.shunt_data.shunt_active[:, 0],
                                       ys=Ys,
                                       B=Bc,
                                       Sbase=nc.Sbase,
                                       m=m, theta=theta, Beq=Beq, Gsw=Gsw,
                                       mf=nc.branch_data.tap_f,
                                       mt=nc.branch_data.tap_t)

    #  compute branch power Sf
    If = Yf * V  # complex current injected at "from" bus, Yf(br, :) * V; For in-service branches
    It = Yt * V  # complex current injected at "to"   bus, Yt(br, :) * V; For in-service branches
    Sf = V[F] * np.conj(If)  # complex power injected at "from" bus
    St = V[T] * np.conj(It)  # complex power injected at "to"   bus

    # compute converter losses
    Gsw = compute_converter_losses(V=V, It=It, F=F,
                                   alpha1=nc.branch_data.alpha1,
                                   alpha2=nc.branch_data.alpha2,
                                   alpha3=nc.branch_data.alpha3,
                                   iVscL=nc.iVscL)

    # compute total mismatch
    fx, Scalc = compute_fx(Ybus=Ybus,
                           V=V,
                           Vm=Vm,
                           Sbus=S0,
                           Sf=Sf,
                           St=St,
                           Pfset=Pfset,
                           Qfset=Qfset,
                           Qtset=Qtset,
                           Vmfset=Vmfset,
                           Kdp=Kdp,
                           F=F,
                           pvpq=pvpq,
                           pq=pq,
                           iPfsh=nc.iPfsh,
                           iQfma=nc.iQfma,
                           iBeqz=nc.iBeqz,
                           iQtma=nc.iQtma,
                           iPfdp=nc.iPfdp,
                           VfBeqbus=nc.VfBeqbus,
                           Vtmabus=nc.Vtmabus)

    norm_f = np.max(np.abs(fx))

    # -------------------------------------------------------------------------
    converged = norm_f < tolerance
    iterations = 0
    while not converged and iterations < max_iter:

        # compute the Jacobian
        J = fubm_jacobian(nb, nl, nc.iPfsh, nc.iPfdp, nc.iQfma, nc.iQtma, nc.iVtma, nc.iBeqz, nc.iBeqv,
                          nc.VfBeqbus, nc.Vtmabus,
                          F, T, Ys, k2, tap, m, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq)

        # solve the linear system
        dx = sp.linalg.spsolve(J, -fx)

        # split the solution
        dVa, dVm, dBeq_v, dma_Vt, dtheta_Pf, dma_Qf, dBeq_z, dma_Qt, dtheta_Pd = sol_slicer.split(dx)

        # set the restoration values
        prev_Vm = Vm.copy()
        prev_Va = Va.copy()
        prev_m = m.copy()
        prev_theta = theta.copy()
        prev_Beq = Beq.copy()
        prev_Scalc = Scalc.copy()

        mu = mu_0  # ideally 1.0
        cond = True
        l_iter = 0
        norm_f_new = 0.0
        while cond and l_iter < max_iter and mu > tolerance:  # backtracking: if all goes well it is only done 1 time

            # restore the previous values if we are backtracking (the first iteration is the normal NR procedure)
            if l_iter > 0:
                Va = prev_Va.copy()
                Vm = prev_Vm.copy()
                m = prev_m.copy()
                theta = prev_theta.copy()
                Beq = prev_Beq.copy()

            # assign the new values
            Va[pvpq] += dVa * mu
            Vm[pq] += dVm * mu
            theta[nc.iPfsh] += dtheta_Pf * mu
            theta[nc.iPfdp] += dtheta_Pd * mu
            m[nc.iQfma] += dma_Qf * mu
            m[nc.iQtma] += dma_Qt * mu
            m[nc.iVtma] += dma_Vt * mu
            Beq[nc.iBeqz] += dBeq_z * mu
            Beq[nc.iBeqv] += dBeq_v * mu
            V = Vm * np.exp(1j * Va)

            # compute admittances
            Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                               C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                               shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                               shunt_active=nc.shunt_data.shunt_active[:, 0],
                                               ys=Ys,
                                               B=Bc,
                                               Sbase=nc.Sbase,
                                               m=m, theta=theta, Beq=Beq, Gsw=Gsw,
                                               mf=nc.branch_data.tap_f,
                                               mt=nc.branch_data.tap_t)

            #  compute branch power Sf
            If = Yf * V  # complex current injected at "from" bus
            It = Yt * V  # complex current injected at "to" bus
            Sf = V[F] * np.conj(If)  # complex power injected at "from" bus
            St = V[T] * np.conj(It)  # complex power injected at "to"   bus

            # compute converter losses
            Gsw = compute_converter_losses(V=V, It=It, F=F,
                                           alpha1=nc.branch_data.alpha1,
                                           alpha2=nc.branch_data.alpha2,
                                           alpha3=nc.branch_data.alpha3,
                                           iVscL=nc.iVscL)

            # compute total mismatch
            fx, Scalc = compute_fx(Ybus=Ybus,
                                   V=V,
                                   Vm=Vm,
                                   Sbus=S0,
                                   Sf=Sf,
                                   St=St,
                                   Pfset=Pfset,
                                   Qfset=Qfset,
                                   Qtset=Qtset,
                                   Vmfset=Vmfset,
                                   Kdp=Kdp,
                                   F=F,
                                   pvpq=pvpq,
                                   pq=pq,
                                   iPfsh=nc.iPfsh,
                                   iQfma=nc.iQfma,
                                   iBeqz=nc.iBeqz,
                                   iQtma=nc.iQtma,
                                   iPfdp=nc.iPfdp,
                                   VfBeqbus=nc.VfBeqbus,
                                   Vtmabus=nc.Vtmabus)

            norm_f_new = np.max(np.abs(fx))
            cond = norm_f_new > norm_f  # condition to back track (no improvement at all)

            mu *= acceleration_parameter
            l_iter += 1

        if l_iter > 1 and norm_f_new > norm_f:
            # this means that not even the backtracking was able to correct the solution so, restore and end
            Va = prev_Va.copy()
            Vm = prev_Vm.copy()
            m = prev_m.copy()
            theta = prev_theta.copy()
            Beq = prev_Beq.copy()
            V = Vm * np.exp(1j * Va)

            end = time.time()
            elapsed = end - start

            # set the state for the next solver_type
            nc.branch_data.m[:, 0] = m
            nc.branch_data.theta[:, 0] = theta
            nc.branch_data.Beq[:, 0] = Beq

            return NumericPowerFlowResults(V, converged, norm_f_new, prev_Scalc, m, theta, Beq, Ybus, Yf, Yt, iterations, elapsed)
        else:
            # the iteration was ok, check the controls if the error is small enough
            if norm_f < 1e-2:

                for idx in nc.iVscL:
                    # correct m (tap modules)
                    if m[idx] < nc.branch_data.m_min[idx]:
                        m[idx] = nc.branch_data.m_min[idx]
                    elif m[idx] > nc.branch_data.m_max[idx]:
                        m[idx] = nc.branch_data.m_max[idx]

                    # correct theta (tap angles)
                    if theta[idx] < nc.branch_data.theta_min[idx]:
                        theta[idx] = nc.branch_data.theta_min[idx]
                    elif theta[idx] > nc.branch_data.theta_max[idx]:
                        theta[idx] = nc.branch_data.theta_max[idx]

                # review reactive power limits
                # it is only worth checking Q limits with a low error
                # since with higher errors, the Q values may be far from realistic
                # finally, the Q control only makes sense if there are pv nodes
                if control_q != ReactivePowerControlMode.NoControl and npv > 0:

                    # check and adjust the reactive power
                    # this function passes pv buses to pq when the limits are violated,
                    # but not pq to pv because that is unstable
                    n_changes, Scalc, S0, pv, pq, pvpq = control_q_inside_method(Scalc, S0, pv, pq, pvpq, Qmin, Qmax)

                    if n_changes > 0:
                        # adjust internal variables to the new pq|pv values
                        npv = len(pv)
                        npq = len(pq)

                        # re declare the slicer because the indices of pq and pv changed
                        sol_slicer = SolSlicer(npq, npv,
                                               len(nc.VfBeqbus),
                                               len(nc.Vtmabus),
                                               len(nc.iPfsh),
                                               len(nc.iQfma),
                                               len(nc.iBeqz),
                                               len(nc.iQtma),
                                               len(nc.iPfdp))

                        # recompute the mismatch, based on the new S0
                        fx, Scalc = compute_fx(Ybus=Ybus,
                                               V=V,
                                               Vm=Vm,
                                               Sbus=S0,
                                               Sf=Sf,
                                               St=St,
                                               Pfset=Pfset,
                                               Qfset=Qfset,
                                               Qtset=Qtset,
                                               Vmfset=Vmfset,
                                               Kdp=Kdp,
                                               F=F,
                                               pvpq=pvpq,
                                               pq=pq,
                                               iPfsh=nc.iPfsh,
                                               iQfma=nc.iQfma,
                                               iBeqz=nc.iBeqz,
                                               iQtma=nc.iQtma,
                                               iPfdp=nc.iPfdp,
                                               VfBeqbus=nc.VfBeqbus,
                                               Vtmabus=nc.Vtmabus)
                        norm_f_new = np.max(np.abs(fx))

            # set the mismatch to the new mismatch
            norm_f = norm_f_new

        if verbose:
            print('dx:', dx)
            print('Va:', Va)
            print('Vm:', Vm)
            print('theta:', theta)
            print('ma:', m)
            print('Beq:', Beq)
            print('norm_f:', norm_f)

        iterations += 1
        converged = norm_f <= tolerance

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, m, theta, Beq, Ybus, Yf, Yt, iterations, elapsed)


def LM_ACDC(nc: "SnapshotData", Vbus, Sbus,
            tolerance=1e-6, max_iter=4, verbose=False) -> NumericPowerFlowResults:
    """
    Solves the power flow problem by the Levenberg-Marquardt power flow algorithm.
    It is usually better than Newton-Raphson, but it takes an order of magnitude more time to converge.

    :param nc: SnapshotData instance
    :param tolerance: maximum error allowed
    :param max_iter: maximum number of iterations
    :return:
    """
    start = time.time()

    # initialize the variables
    nb = nc.nbus
    nl = nc.nbr
    V = Vbus
    S0 = Sbus
    Va = np.angle(V)
    Vm = np.abs(V)
    Vmfset = nc.branch_data.vf_set[:, 0]
    m = nc.branch_data.m[:, 0].copy()
    theta = nc.branch_data.theta[:, 0].copy()
    Beq = nc.branch_data.Beq[:, 0].copy()
    Gsw = nc.branch_data.G0[:, 0]
    Pfset = nc.branch_data.Pfset[:, 0] / nc.Sbase
    Qfset = nc.branch_data.Qfset[:, 0] / nc.Sbase
    Qtset = nc.branch_data.Qfset[:, 0] / nc.Sbase
    Kdp = nc.branch_data.Kdp
    k2 = nc.branch_data.k
    Cf = nc.Cf
    Ct = nc.Ct
    F = nc.F
    T = nc.T
    Ys = 1.0 / (nc.branch_data.R + 1j * nc.branch_data.X)
    Bc = nc.branch_data.B
    pq = nc.pq.copy().astype(int)
    pvpq_orig = np.r_[nc.pv, pq].astype(int)
    pvpq_orig.sort()

    # the elements of PQ that exist in the control indices Ivf and Ivt must be passed from the PQ to the PV list
    # otherwise those variables would be in two sets of equations
    i_ctrl_v = np.unique(np.r_[nc.VfBeqbus, nc.Vtmabus])
    for val in pq:
        if val in i_ctrl_v:
            pq = pq[pq != val]

    # compose the new pvpq indices à la NR
    pv = np.unique(np.r_[i_ctrl_v, nc.pv]).astype(int)
    pv.sort()
    pvpq = np.r_[pv, pq].astype(int)
    npv = len(pv)
    npq = len(pq)

    if (npq + npv) > 0:
        # --------------------------------------------------------------------------
        # variables dimensions in Jacobian
        sol_slicer = SolSlicer(npq, npv,
                               len(nc.VfBeqbus),
                               len(nc.Vtmabus),
                               len(nc.iPfsh),
                               len(nc.iQfma),
                               len(nc.iBeqz),
                               len(nc.iQtma),
                               len(nc.iPfdp))
        # -------------------------------------------------------------------------
        # compute initial admittances
        Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                           C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                           shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                           shunt_active=nc.shunt_data.shunt_active[:, 0],
                                           ys=Ys,
                                           B=Bc,
                                           Sbase=nc.Sbase,
                                           m=m, theta=theta, Beq=Beq, Gsw=Gsw,
                                           mf=nc.branch_data.tap_f,
                                           mt=nc.branch_data.tap_t)

        #  compute branch power Sf
        If = Yf * V  # complex current injected at "from" bus, Yf(br, :) * V; For in-service branches
        It = Yt * V  # complex current injected at "to"   bus, Yt(br, :) * V; For in-service branches
        Sf = V[F] * np.conj(If)  # complex power injected at "from" bus
        St = V[T] * np.conj(It)  # complex power injected at "to"   bus

        # compute converter losses
        Gsw = compute_converter_losses(V=V, It=It, F=F,
                                       alpha1=nc.branch_data.alpha1,
                                       alpha2=nc.branch_data.alpha2,
                                       alpha3=nc.branch_data.alpha3,
                                       iVscL=nc.iVscL)

        # compute total mismatch
        dz, Scalc = compute_fx(Ybus=Ybus,
                               V=V,
                               Vm=Vm,
                               Sbus=S0,
                               Sf=Sf,
                               St=St,
                               Pfset=Pfset,
                               Qfset=Qfset,
                               Qtset=Qtset,
                               Vmfset=Vmfset,
                               Kdp=Kdp,
                               F=F,
                               pvpq=pvpq,
                               pq=pq,
                               iPfsh=nc.iPfsh,
                               iQfma=nc.iQfma,
                               iBeqz=nc.iBeqz,
                               iQtma=nc.iQtma,
                               iPfdp=nc.iPfdp,
                               VfBeqbus=nc.VfBeqbus,
                               Vtmabus=nc.Vtmabus)

        norm_f = np.max(np.abs(dz))

        update_jacobian = True
        converged = norm_f < tolerance
        iter_ = 0
        nu = 2.0
        lbmda = 0
        f_prev = 1e9  # very large number

        # generate lookup pvpq -> index pvpq (used in createJ)
        pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
        pvpq_lookup[pvpq] = np.arange(len(pvpq))

        while not converged and iter_ < max_iter:

            # evaluate Jacobian
            if update_jacobian:
                H = fubm_jacobian(nb, nl, nc.iPfsh, nc.iPfdp, nc.iQfma, nc.iQtma, nc.iVtma, nc.iBeqz, nc.iBeqv,
                                  nc.VfBeqbus, nc.Vtmabus,
                                  F, T, Ys, k2, tap, m, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq)

                if iter_ == 0:
                    # compute this identity only once
                    Idn = sp.diags(np.ones(H.shape[0]))  # csc_matrix identity

                # system matrix
                # H1 = H^t
                H1 = H.transpose()

                # H2 = H1·H
                H2 = H1.dot(H)

                # set first value of lmbda
                if iter_ == 0:
                    lbmda = 1e-3 * H2.diagonal().max()

            # compute system matrix A = H^T·H - lambda·I
            A = H2 + lbmda * Idn

            # right hand side
            # H^t·dz
            rhs = H1.dot(dz)

            # Solve the increment
            dx = spsolve(A, rhs)

            # objective function to minimize
            f = 0.5 * dz.dot(dz)

            # decision function
            val = dx.dot(lbmda * dx + rhs)
            if val > 0.0:
                rho = (f_prev - f) / (0.5 * val)
            else:
                rho = -1.0

            # lambda update
            if rho >= 0:
                update_jacobian = True
                lbmda *= max([1.0 / 3.0, 1 - (2 * rho - 1) ** 3])
                nu = 2.0

                # split the solution
                dVa, dVm, dBeq_v, dma_Vt, dtheta_Pf, dma_Qf, dBeq_z, dma_Qt, dtheta_Pd = sol_slicer.split(dx)

                # assign the new values
                Va[pvpq] -= dVa
                Vm[pq] -= dVm
                theta[nc.iPfsh] -= dtheta_Pf
                theta[nc.iPfdp] -= dtheta_Pd
                m[nc.iQfma] -= dma_Qf
                m[nc.iQtma] -= dma_Qt
                m[nc.iVtma] -= dma_Vt
                Beq[nc.iBeqz] -= dBeq_z
                Beq[nc.iBeqv] -= dBeq_v
                V = Vm * np.exp(1.0j * Va)

            else:
                update_jacobian = False
                lbmda *= nu
                nu *= 2.0

            # compute initial admittances
            Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                               C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                               shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                               shunt_active=nc.shunt_data.shunt_active[:, 0],
                                               ys=Ys,
                                               B=Bc,
                                               Sbase=nc.Sbase,
                                               m=m, theta=theta, Beq=Beq, Gsw=Gsw,
                                               mf=nc.branch_data.tap_f,
                                               mt=nc.branch_data.tap_t)

            #  compute branch power Sf
            If = Yf * V  # complex current injected at "from" bus, Yf(br, :) * V; For in-service branches
            It = Yt * V  # complex current injected at "to"   bus, Yt(br, :) * V; For in-service branches
            Sf = V[F] * np.conj(If)  # complex power injected at "from" bus
            St = V[T] * np.conj(It)  # complex power injected at "to"   bus

            # compute converter losses
            Gsw = compute_converter_losses(V=V, It=It, F=F,
                                           alpha1=nc.branch_data.alpha1,
                                           alpha2=nc.branch_data.alpha2,
                                           alpha3=nc.branch_data.alpha3,
                                           iVscL=nc.iVscL)

            # check convergence
            dz, Scalc = compute_fx(Ybus=Ybus,
                                   V=V,
                                   Vm=Vm,
                                   Sbus=S0,
                                   Sf=Sf,
                                   St=St,
                                   Pfset=Pfset,
                                   Qfset=Qfset,
                                   Qtset=Qtset,
                                   Vmfset=Vmfset,
                                   Kdp=Kdp,
                                   F=F,
                                   pvpq=pvpq,
                                   pq=pq,
                                   iPfsh=nc.iPfsh,
                                   iQfma=nc.iQfma,
                                   iBeqz=nc.iBeqz,
                                   iQtma=nc.iQtma,
                                   iPfdp=nc.iPfdp,
                                   VfBeqbus=nc.VfBeqbus,
                                   Vtmabus=nc.Vtmabus)
            norm_f = np.max(np.abs(dz))
            converged = norm_f < tolerance
            f_prev = f

            if verbose:
                print('dx:', dx)
                print('Va:', Va)
                print('Vm:', Vm)
                print('theta:', theta)
                print('ma:', m)
                print('Beq:', Beq)
                print('norm_f:', norm_f)

            # update iteration counter
            iter_ += 1
    else:
        norm_f = 0
        converged = True
        Scalc = S0  # V * np.conj(Ybus * V - Ibus)
        iter_ = 0
        Ybus = None
        Yf = None
        Yt = None

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, m, theta, Beq, Ybus, Yf, Yt, iter_, elapsed)


if __name__ == "__main__":
    from GridCal.Engine import FileOpen, compile_snapshot_circuit
    np.set_printoptions(precision=4, linewidth=100000)
    # np.set_printoptions(linewidth=10000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/LineHVDCGrid.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/fubm_case_57_14_2MTDC_ctrls.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/ACDC_example_grid.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/fubm_caseHVDC_vt.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/3Bus_controlled_transformer.gridcal'
    grid = FileOpen(fname).open()

    ####################################################################################################################
    # Compile
    ####################################################################################################################
    nc_ = compile_snapshot_circuit(grid)

    res = NR_LS_ACDC(nc=nc_,
                     Vbus=nc_.Vbus,
                     Sbus=nc_.Sbus,
                     tolerance=1e-4,
                     max_iter=20,
                     verbose=True)

    # res2 = LM_ACDC(nc=nc_, tolerance=1e-4, max_iter=20, verbose=True)

    print()
