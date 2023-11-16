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
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

from GridCalEngine.Core.admittance_matrices import compile_y_acdc
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.acdc_jacobian import fubm_jacobian, AcDcSolSlicer
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.basic_structures import CxVec


def LM_ACDC(nc: NumericalCircuit, Vbus: CxVec, S0: CxVec, I0: CxVec, Y0: CxVec,
            tolerance=1e-6, max_iter=4, verbose=False) -> NumericPowerFlowResults:
    """
    Solves the power flow problem by the Levenberg-Marquardt power flow algorithm.
    It is usually better than Newton-Raphson, but it takes an order of magnitude more time to converge.

    :param verbose:
    :param Y0:
    :param I0:
    :param S0:
    :param Vbus:
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

    Va = np.angle(V)
    Vm = np.abs(V)

    # compute the ZIP power injection
    Sbus = cf.compute_zip_power(S0=S0, I0=I0, Y0=Y0, Vm=Vm)

    Vmfset = nc.branch_data.vf_set
    m = nc.branch_data.tap_module.copy()
    tau = nc.branch_data.tap_angle.copy()
    Beq = nc.branch_data.Beq.copy()
    Gsw = nc.branch_data.G0sw
    Pfset = nc.branch_data.Pfset / nc.Sbase
    Qfset = nc.branch_data.Qfset / nc.Sbase
    Qtset = nc.branch_data.Qfset / nc.Sbase
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

    if (npq + npv) > 0:
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
                                           C_bus_shunt=nc.shunt_data.C_bus_elm,
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
        Gsw = cf.compute_converter_losses(V=V, It=It, F=F,
                                          alpha1=nc.branch_data.alpha1,
                                          alpha2=nc.branch_data.alpha2,
                                          alpha3=nc.branch_data.alpha3,
                                          iVscL=nc.i_vsc)

        # compute total mismatch
        Scalc = cf.compute_power(Ybus, V)
        dz = cf.compute_acdc_fx(Vm=Vm,
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

        norm_f = np.max(np.abs(dz))

        update_jacobian = True
        converged = norm_f < tolerance
        iter_ = 0
        nu = 2.0
        lbmda = 0
        f_prev = 1e9  # very large number

        # generate lookup pvpq -> index pvpq (used in createJ)
        pvpq_lookup = np.zeros(Ybus.shape[0], dtype=int)
        pvpq_lookup[pvpq] = np.arange(len(pvpq))

        while not converged and iter_ < max_iter:

            # evaluate Jacobian
            if update_jacobian:
                H = fubm_jacobian(nb, nl, nc.k_pf_tau, nc.k_pf_dp, nc.k_qf_m, nc.k_qt_m, nc.k_vt_m, nc.k_zero_beq, nc.k_vf_beq,
                                  nc.i_vf_beq, nc.i_vt_m,
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
                dVa, dVm, dBeq, dm, dTau = sol_slicer.split(dx)

                # assign the new values
                Va[sol_slicer.va_idx] -= dVa
                Vm[sol_slicer.vm_idx] -= dVm
                Beq[sol_slicer.beq_idx] -= dBeq
                m[sol_slicer.m_idx] -= dm
                tau[sol_slicer.tau_idx] -= dTau

                V = cf.polar_to_rect(Vm, Va)

                # compute the ZIP power injection
                Sbus = cf.compute_zip_power(S0=S0, I0=I0, Y0=Y0, Vm=Vm)

            else:
                update_jacobian = False
                lbmda *= nu
                nu *= 2.0

            # compute initial admittances
            Ybus, Yf, Yt, tap = compile_y_acdc(Cf=Cf,
                                               Ct=Ct,
                                               C_bus_shunt=nc.shunt_data.C_bus_elm,
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
            Gsw = cf.compute_converter_losses(V=V, It=It, F=F,
                                              alpha1=nc.branch_data.alpha1,
                                              alpha2=nc.branch_data.alpha2,
                                              alpha3=nc.branch_data.alpha3,
                                              iVscL=nc.i_vsc)

            # check convergence
            Scalc = cf.compute_power(Ybus, V)
            dz = cf.compute_acdc_fx(Vm=Vm,
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

            norm_f = np.max(np.abs(dz))
            converged = norm_f < tolerance
            f_prev = f

            if verbose:
                print('dx:', dx)
                print('Va:', Va)
                print('Vm:', Vm)
                print('theta:', tau)
                print('ma:', m)
                print('Beq:', Beq)
                print('norm_f:', norm_f)

            # update iteration counter
            iter_ += 1
    else:
        norm_f = 0
        converged = True
        Scalc = S0 + I0 * Vm + Y0 * np.power(Vm, 2)  # compute the ZIP power injection
        iter_ = 0
        Ybus = None
        Yf = None
        Yt = None

    end = time.time()
    elapsed = end - start

    # return NumericPowerFlowResults(V, converged, norm_f, Scalc, m, theta, Beq, Ybus, Yf, Yt, iter_, elapsed)
    return NumericPowerFlowResults(V=V, converged=converged, norm_f=norm_f,
                                   Scalc=Scalc, ma=m, theta=tau, Beq=Beq,
                                   Ybus=Ybus, Yf=Yf, Yt=Yt,
                                   iterations=iter_, elapsed=elapsed)
