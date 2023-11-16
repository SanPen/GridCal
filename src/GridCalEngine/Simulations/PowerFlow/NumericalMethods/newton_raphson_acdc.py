# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Core.admittance_matrices import compile_y_acdc
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_inside_method
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.acdc_jacobian import fubm_jacobian, AcDcSolSlicer
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_acdc_fx,
                                                                                   compute_converter_losses,
                                                                                   compute_power, compute_zip_power)
from GridCalEngine.basic_structures import ReactivePowerControlMode, CxVec
import GridCalEngine.Simulations.sparse_solve as gcsp


def NR_LS_ACDC(nc: NumericalCircuit,
               V0: CxVec,
               S0: CxVec,
               I0: CxVec,
               Y0: CxVec,
               tolerance=1e-6,
               max_iter=4,
               mu_0=1.0,
               acceleration_parameter=0.05,
               verbose=False,
               control_q=ReactivePowerControlMode.NoControl) -> NumericPowerFlowResults:
    """
    Newton-Raphson Line search with the FUBM formulation
    :param nc: NumericalCircuit
    :param V0: Initial voltage solution
    :param S0: Power injections
    :param I0: Current injections
    :param Y0: Admittance injections
    :param tolerance: maximum error allowed
    :param max_iter: maximum number of iterations
    :param mu_0: Initial solution multiplier
    :param acceleration_parameter: Acceleration parameter (rate to decrease mu)
    :param verbose: Verbose?
    :param control_q: Reactive power control mode
    :return: NumericPowerFlowResults
    """
    start = time.time()

    # initialize the variables
    nb = nc.nbus
    nl = nc.nbr
    V = V0

    Va = np.angle(V)
    Vm = np.abs(V)

    # compute the ZIP power injection
    Sbus = compute_zip_power(S0=S0, I0=I0, Y0=Y0, Vm=Vm)

    Vmfset = nc.branch_data.vf_set
    m = nc.branch_data.tap_module.copy()
    tau = nc.branch_data.tap_angle.copy()
    Beq = nc.branch_data.Beq.copy()
    Gsw = nc.branch_data.G0sw
    Pfset = nc.branch_data.Pfset / nc.Sbase
    Qfset = nc.branch_data.Qfset / nc.Sbase
    Qtset = nc.branch_data.Qfset / nc.Sbase
    Qmin = nc.Qmin_bus
    Qmax = nc.Qmax_bus
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
    i_ctrl_v = np.unique(np.r_[nc.i_vf_beq, nc.i_vt_m])
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
    sol_slicer = AcDcSolSlicer(pvpq=pvpq,
                               pq=pq,
                               k_zero_beq=nc.k_zero_beq,
                               k_vf_beq=nc.k_vf_beq,
                               k_qf_m=nc.k_qf_m,
                               k_qt_m=nc.k_qt_m,
                               k_vt_m=nc.k_vt_m,
                               k_pf_tau=nc.k_pf_tau,
                               k_pf_dp=nc.k_pf_dp)

    # -------------------------------------------------------------------------
    # compute initial admittances
    Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                       C_bus_shunt=nc.shunt_data.C_bus_elm.tocsc(),
                                       shunt_admittance=nc.shunt_data.admittance,
                                       shunt_active=nc.shunt_data.active,
                                       ys=Ys,
                                       B=Bc,
                                       Sbase=nc.Sbase,
                                       tap_module=m, tap_angle=tau, Beq=Beq, Gsw=Gsw,
                                       virtual_tap_from=nc.branch_data.virtual_tap_f,
                                       virtual_tap_to=nc.branch_data.virtual_tap_t)

    #  compute branch power Sf
    If = Yf * V  # complex current injected at "from" bus, Yf(br, :) * V; For in-service Branches
    It = Yt * V  # complex current injected at "to"   bus, Yt(br, :) * V; For in-service Branches
    Sf = V[F] * np.conj(If)  # complex power injected at "from" bus
    St = V[T] * np.conj(It)  # complex power injected at "to"   bus

    # compute converter losses
    Gsw = compute_converter_losses(V=V, It=It, F=F,
                                   alpha1=nc.branch_data.alpha1,
                                   alpha2=nc.branch_data.alpha2,
                                   alpha3=nc.branch_data.alpha3,
                                   iVscL=nc.i_vsc)

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
                         k_pf_tau=nc.k_pf_tau,
                         k_qf_m=nc.k_qf_m,
                         k_zero_beq=nc.k_zero_beq,
                         k_qt_m=nc.k_qt_m,
                         k_pf_dp=nc.k_pf_dp,
                         i_vf_beq=nc.i_vf_beq,
                         i_vt_m=nc.i_vt_m)

    norm_f = np.max(np.abs(fx))

    # -------------------------------------------------------------------------
    converged = norm_f < tolerance
    iterations = 0
    while not converged and iterations < max_iter:

        # compute the Jacobian
        J = fubm_jacobian(nb, nl, nc.k_pf_tau, nc.k_pf_dp, nc.k_qf_m, nc.k_qt_m, nc.k_vt_m, nc.k_zero_beq, nc.k_vf_beq,
                          nc.i_vf_beq, nc.i_vt_m,
                          F, T, Ys, k2, tap, m, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq)

        # solve the linear system
        dx = gcsp.super_lu_linsolver(J, -fx)

        if not np.isnan(dx).any():  # check if the solution worked

            # split the solution
            dVa, dVm, dBeq, dm, dTau = sol_slicer.split(dx)

            # set the restoration values
            prev_Vm = Vm.copy()
            prev_Va = Va.copy()
            prev_m = m.copy()
            prev_tau = tau.copy()
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
                    tau = prev_tau.copy()
                    Beq = prev_Beq.copy()

                # assign the new values
                Va[sol_slicer.va_idx] -= dVa * mu
                Vm[sol_slicer.vm_idx] -= dVm * mu
                Beq[sol_slicer.beq_idx] -= dBeq * mu
                m[sol_slicer.m_idx] -= dm * mu
                tau[sol_slicer.tau_idx] -= dTau * mu

                V = Vm * np.exp(1j * Va)

                # compute the ZIP power injection
                Sbus = compute_zip_power(S0=S0, I0=I0, Y0=Y0, Vm=Vm)

                # compute admittances
                Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf, Ct=Ct,
                                                   C_bus_shunt=nc.shunt_data.C_bus_elm.tocsc(),
                                                   shunt_admittance=nc.shunt_data.admittance,
                                                   shunt_active=nc.shunt_data.active,
                                                   ys=Ys,
                                                   B=Bc,
                                                   Sbase=nc.Sbase,
                                                   tap_module=m, tap_angle=tau, Beq=Beq, Gsw=Gsw,
                                                   virtual_tap_from=nc.branch_data.virtual_tap_f,
                                                   virtual_tap_to=nc.branch_data.virtual_tap_t)

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
                                               iVscL=nc.i_vsc)

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
                                     k_pf_tau=nc.k_pf_tau,
                                     k_qf_m=nc.k_qf_m,
                                     k_zero_beq=nc.k_zero_beq,
                                     k_qt_m=nc.k_qt_m,
                                     k_pf_dp=nc.k_pf_dp,
                                     i_vf_beq=nc.i_vf_beq,
                                     i_vt_m=nc.i_vt_m)

                norm_f_new = np.max(np.abs(fx))
                cond = norm_f_new > norm_f  # condition to back track (no improvement at all)

                mu *= acceleration_parameter
                l_iter += 1

            if l_iter > 1 and norm_f_new > norm_f:
                # this means that not even the backtracking was able to correct the solution so, restore and end
                Va = prev_Va.copy()
                Vm = prev_Vm.copy()
                m = prev_m.copy()
                tau = prev_tau.copy()
                Beq = prev_Beq.copy()
                V = Vm * np.exp(1j * Va)
                end = time.time()
                elapsed = end - start

                # set the state for the next solver_type
                nc.branch_data.tap_module = m
                nc.branch_data.tap_angle = tau
                nc.branch_data.Beq = Beq

                # return NumericPowerFlowResults(V, converged, norm_f_new, prev_Scalc,
                #                                m, tau, Beq, Ybus, Yf, Yt, iterations, elapsed)
                return NumericPowerFlowResults(V=V, converged=converged, norm_f=norm_f,
                                               Scalc=Scalc, ma=m, theta=tau, Beq=Beq,
                                               Ybus=Ybus, Yf=Yf, Yt=Yt,
                                               iterations=iterations, elapsed=elapsed)
            else:
                # the iteration was ok, check the controls if the error is small enough
                if norm_f < 1e-2:

                    for idx in nc.i_vsc:
                        # correct m (tap modules)
                        if m[idx] < nc.branch_data.tap_module_min[idx]:
                            m[idx] = nc.branch_data.tap_module_min[idx]
                        elif m[idx] > nc.branch_data.tap_module_max[idx]:
                            m[idx] = nc.branch_data.tap_module_max[idx]

                        # correct theta (tap angles)
                        if tau[idx] < nc.branch_data.tap_angle_min[idx]:
                            tau[idx] = nc.branch_data.tap_angle_min[idx]
                        elif tau[idx] > nc.branch_data.tap_angle_max[idx]:
                            tau[idx] = nc.branch_data.tap_angle_max[idx]

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

                        # compute the ZIP power injection
                        Sbus = compute_zip_power(S0=S0, I0=I0, Y0=Y0, Vm=Vm)

                        if n_changes > 0:
                            # adjust internal variables to the new pq|pv values
                            npv = len(pv)
                            npq = len(pq)

                            # re declare the slicer because the indices of pq and pv changed
                            sol_slicer = AcDcSolSlicer(pvpq=pvpq,
                                                       pq=pq,
                                                       k_zero_beq=nc.k_zero_beq,
                                                       k_vf_beq=nc.k_vf_beq,
                                                       k_qf_m=nc.k_qf_m,
                                                       k_qt_m=nc.k_qt_m,
                                                       k_vt_m=nc.k_vt_m,
                                                       k_pf_tau=nc.k_pf_tau,
                                                       k_pf_dp=nc.k_pf_dp)

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
                                                 k_pf_tau=nc.k_pf_tau,
                                                 k_qf_m=nc.k_qf_m,
                                                 k_zero_beq=nc.k_zero_beq,
                                                 k_qt_m=nc.k_qt_m,
                                                 k_pf_dp=nc.k_pf_dp,
                                                 i_vf_beq=nc.i_vf_beq,
                                                 i_vt_m=nc.i_vt_m)
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
                print('theta:', tau)
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

    # return NumericPowerFlowResults(V, converged, norm_f, Scalc,
    #                                m, tau, Beq, Ybus, Yf, Yt, iterations, elapsed)
    return NumericPowerFlowResults(V=V, converged=converged, norm_f=norm_f,
                                   Scalc=Scalc, ma=m, theta=tau, Beq=Beq,
                                   Ybus=Ybus, Yf=Yf, Yt=Yt,
                                   iterations=iterations, elapsed=elapsed)
