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

import time

import numpy as np

from GridCal.Engine.Core.admittance_matrices import compile_y_acdc
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_inside_method
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.acdc_jacobian import fubm_jacobian, AcDcSolSlicer
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_acdc_fx, compute_converter_losses, compute_power
from GridCal.Engine.basic_structures import ReactivePowerControlMode
import GridCal.Engine.Simulations.sparse_solve as gcsp


def NR_LS_ACDC(nc: "SnapshotData", Vbus, S0, I0, Y0,
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

    Va = np.angle(V)
    Vm = np.abs(V)

    Sbus = S0 + I0 * Vm + Y0 * np.power(Vm, 2)  # compute the ZIP power injection

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
    sol_slicer = AcDcSolSlicer(npq, npv,
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
    Scalc = compute_power(Ybus, V)
    fx = compute_acdc_fx(Vm=Vm,
                         Sbus=Sbus,
                         Scalc=Scalc,
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
        dx = gcsp.super_lu_linsolver(J, -fx)

        if not np.isnan(dx).any():  # check if the solution worked

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

                Sbus = S0 + I0 * Vm + Y0 * np.power(Vm, 2)  # compute the ZIP power injection

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
                Scalc = compute_power(Ybus, V)
                fx = compute_acdc_fx(Vm=Vm,
                                     Sbus=Sbus,
                                     Scalc=Scalc,
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
                        n_changes, Scalc, S0, pv, pq, pvpq, messages = control_q_inside_method(Scalc, S0, pv, pq,
                                                                                               pvpq, Qmin, Qmax)

                        Sbus = S0 + I0 * Vm + Y0 * np.power(Vm, 2)  # compute the ZIP power injection

                        if n_changes > 0:
                            # adjust internal variables to the new pq|pv values
                            npv = len(pv)
                            npq = len(pq)

                            # re declare the slicer because the indices of pq and pv changed
                            sol_slicer = AcDcSolSlicer(npq, npv,
                                                       len(nc.VfBeqbus),
                                                       len(nc.Vtmabus),
                                                       len(nc.iPfsh),
                                                       len(nc.iQfma),
                                                       len(nc.iBeqz),
                                                       len(nc.iQtma),
                                                       len(nc.iPfdp))

                            # recompute the mismatch, based on the new S0
                            Scalc = compute_power(Ybus, V)
                            fx = compute_acdc_fx(Vm=Vm,
                                                 Sbus=Sbus,
                                                 Scalc=Scalc,
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

                            # if verbose > 0:
                            #     for sense, idx, var in messages:
                            #         msg = "Bus " + str(idx) + " changed to PQ, limited to " + str(var * 100) + " MVAr"
                            #         logger.add_debug(msg)

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
        else:
            iterations = max_iter
            converged = False

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, m, theta, Beq, Ybus, Yf, Yt, iterations, elapsed)

