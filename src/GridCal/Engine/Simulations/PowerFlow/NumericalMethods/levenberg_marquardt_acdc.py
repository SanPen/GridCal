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

from scipy.sparse.linalg import spsolve

from GridCal.Engine.Core.admittance_matrices import compile_y_acdc
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.common_functions import *
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.acdc_jacobian import fubm_jacobian, AcDcSolSlicer


def LM_ACDC(nc: "SnapshotData", Vbus, S0, I0, Y0,
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

    Va = np.angle(V)
    Vm = np.abs(V)

    Sbus = S0 + I0 * Vm + Y0 * np.power(Vm, 2)  # compute the ZIP power injection

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
        dz = compute_acdc_fx(Vm=Vm,
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
                V = polar_to_rect(Vm, Va)
                Sbus = S0 + I0 * Vm + Y0 * np.power(Vm, 2)  # compute the ZIP power injection

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
            Scalc = compute_power(Ybus, V)
            dz = compute_acdc_fx(Vm=Vm,
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
        Scalc = S0 + I0 * Vm + Y0 * np.power(Vm, 2)  # compute the ZIP power injection
        iter_ = 0
        Ybus = None
        Yf = None
        Yt = None

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, norm_f, Scalc, m, theta, Beq, Ybus, Yf, Yt, iter_, elapsed)

