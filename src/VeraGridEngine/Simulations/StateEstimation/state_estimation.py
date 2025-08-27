# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import time
from typing import Tuple

import pandas as pd
from scipy import sparse
from scipy.linalg import lstsq
from scipy.sparse import hstack as sphs, vstack as spvs, csc_matrix, diags
from scipy.sparse.linalg import factorized, spsolve, spilu, splu, lsqr
import numpy as np
from VeraGridEngine.Simulations.StateEstimation.state_estimation_inputs import StateEstimationInput
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import power_flow_post_process_nonlinear
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.Derivatives.matpower_derivatives import (dSbus_dV_matpower, dSbr_dV_matpower,
                                                                         dIbr_dV_matpower)
from VeraGridEngine.Simulations.StateEstimation.state_estimation_results import NumericStateEstimationResults
from VeraGridEngine.basic_structures import CscMat, IntVec, CxVec, Vec, ObjVec, Logger


def Jacobian_SE(Ybus: csc_matrix, Yf: csc_matrix, Yt: csc_matrix, V: CxVec,
                f: IntVec, t: IntVec, Cf: csc_matrix, Ct: csc_matrix,
                inputs: StateEstimationInput, pvpq: IntVec,
                load_per_bus: CxVec,
                fixed_slack: bool):
    """
    Get the arrays for calculation
    :param Ybus: Admittance matrix
    :param Yf: "from" admittance matrix
    :param Yt: "to" admittance matrix
    :param V: Voltages complex vector
    :param f: array of "from" indices of branches
    :param t: array of "to" indices of branches
    :param Cf: Connectivity matrix "from"
    :param Ct: Connectivity matrix "to"
    :param inputs: instance of StateEstimationInput
    :param pvpq: array of pq|pv bus indices
    :param load_per_bus: Array of load per bus in p.u. (used to compute the Pg and Qg measurements)
    :param fixed_slack: if true, the measurements on the slack bus are omitted
    :return: H (jacobian), h (residual), S (power injections)
    """
    n = Ybus.shape[0]

    # compute currents
    I = Ybus @ V
    If = Yf @ V
    It = Yt @ V

    # compute powers
    S = V * np.conj(I)
    Sf = V[f] * np.conj(If)
    St = V[t] * np.conj(It)

    dS_dVa, dS_dVm = dSbus_dV_matpower(Ybus, V)
    dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm = dSbr_dV_matpower(Yf, Yt, V, f, t, Cf, Ct)
    dIf_dVa, dIf_dVm, dIt_dVa, dIt_dVm = dIbr_dV_matpower(Yf, Yt, V)

    # compute the derivatives of absolute current:
    # using the identity d|I|2/dx = 2 * re(diags(conj(I)) x dI/dx)
    # so we will square the current measurements for using these derivatives
    dabsIf2_dVa = 2.0 * (diags(np.conj(If)) @ dIf_dVa).real
    dabsIf2_dVm = 2.0 * (diags(np.conj(If)) @ dIf_dVm).real
    dabsIt2_dVa = 2.0 * (diags(np.conj(It)) @ dIt_dVa).real
    dabsIt2_dVm = 2.0 * (diags(np.conj(It)) @ dIt_dVm).real

    # slice derivatives
    dP_dVa = dS_dVa[np.ix_(inputs.p_idx, pvpq)].real
    dQ_dVa = dS_dVa[np.ix_(inputs.q_idx, pvpq)].imag
    dPg_dVa = dS_dVa[np.ix_(inputs.pg_idx, pvpq)].real
    dQg_dVa = dS_dVa[np.ix_(inputs.qg_idx, pvpq)].imag
    dPf_dVa = dSf_dVa[np.ix_(inputs.pf_idx, pvpq)].real
    dPt_dVa = dSt_dVa[np.ix_(inputs.pt_idx, pvpq)].real
    dQf_dVa = dSf_dVa[np.ix_(inputs.qf_idx, pvpq)].imag
    dQt_dVa = dSt_dVa[np.ix_(inputs.qt_idx, pvpq)].imag
    dIf_dVa = np.abs(dabsIf2_dVa[np.ix_(inputs.if_idx, pvpq)])
    dIt_dVa = np.abs(dabsIt2_dVa[np.ix_(inputs.it_idx, pvpq)])
    dVm_dVa = csc_matrix(np.zeros((len(inputs.vm_idx), len(pvpq))))
    dVa_dVa = csc_matrix(np.diag(np.ones(n))[np.ix_(inputs.va_idx, pvpq)])

    if fixed_slack:
        # With the fixed slack, we don't need to compute the derivative values for the slack Vm
        dP_dVm = dS_dVm[np.ix_(inputs.p_idx, pvpq)].real
        dQ_dVm = dS_dVm[np.ix_(inputs.q_idx, pvpq)].imag
        dPg_dVm = dS_dVm[np.ix_(inputs.pg_idx, pvpq)].real
        dQg_dVm = dS_dVm[np.ix_(inputs.qg_idx, pvpq)].imag
        dPf_dVm = dSf_dVm[np.ix_(inputs.pf_idx, pvpq)].real
        dPt_dVm = dSt_dVm[np.ix_(inputs.pt_idx, pvpq)].real
        dQf_dVm = dSf_dVm[np.ix_(inputs.qf_idx, pvpq)].imag
        dQt_dVm = dSt_dVm[np.ix_(inputs.qt_idx, pvpq)].imag
        dIf_dVm = np.abs(dabsIf2_dVm[np.ix_(inputs.if_idx, pvpq)])
        dIt_dVm = np.abs(dabsIt2_dVm[np.ix_(inputs.it_idx, pvpq)])
        dVm_dVm = csc_matrix(np.diag(np.ones(n))[np.ix_(inputs.vm_idx, pvpq)])
        dVa_dVm = csc_matrix(np.zeros((len(inputs.va_idx), len(pvpq))))
    else:
        # With the non fixed slack, we need to compute the derivative values for the slack Vm
        dP_dVm = dS_dVm[inputs.p_idx, :].real
        dQ_dVm = dS_dVm[inputs.q_idx, :].imag
        dPg_dVm = dS_dVm[inputs.pg_idx, :].real
        dQg_dVm = dS_dVm[inputs.qg_idx, :].imag
        dPf_dVm = dSf_dVm[inputs.pf_idx, :].real
        dPt_dVm = dSt_dVm[inputs.pt_idx, :].real
        dQf_dVm = dSf_dVm[inputs.qf_idx, :].imag
        dQt_dVm = dSt_dVm[inputs.qt_idx, :].imag
        dIf_dVm = np.abs(dabsIf2_dVm[inputs.if_idx, :])
        dIt_dVm = np.abs(dabsIt2_dVm[inputs.it_idx, :])
        dVm_dVm = csc_matrix(np.diag(np.ones(n))[inputs.vm_idx, :])
        dVa_dVm = csc_matrix(np.zeros((len(inputs.va_idx), n)))

    # pack the Jacobian
    H = spvs([
        sphs([dP_dVa, dP_dVm]),
        sphs([dQ_dVa, dQ_dVm]),
        sphs([dPg_dVa, dPg_dVm]),
        sphs([dQg_dVa, dQg_dVm]),
        sphs([dPf_dVa, dPf_dVm]),
        sphs([dPt_dVa, dPt_dVm]),
        sphs([dQf_dVa, dQf_dVm]),
        sphs([dQt_dVa, dQt_dVm]),
        sphs([dIf_dVa, dIf_dVm]),
        sphs([dIt_dVa, dIt_dVm]),
        sphs([dVm_dVa, dVm_dVm]),
        sphs([dVa_dVa, dVa_dVm])
    ])

    # pack the mismatch vector (calculated estimates in per-unit)
    h = np.r_[
        S[inputs.p_idx].real,  # P
        S[inputs.q_idx].imag,  # Q
        S[inputs.pg_idx].real - load_per_bus[inputs.pg_idx].real,  # Pg
        S[inputs.qg_idx].imag - load_per_bus[inputs.qg_idx].imag,  # Qg
        Sf[inputs.pf_idx].real,  # Pf
        St[inputs.pt_idx].real,  # Pt
        Sf[inputs.qf_idx].imag,  # Qf
        St[inputs.qt_idx].imag,  # Qt
        np.power(np.abs(If[inputs.if_idx]), 2),  # If
        np.power(np.abs(It[inputs.it_idx]), 2),  # It
        np.abs(V[inputs.vm_idx]),  # Vm
        np.angle(V[inputs.va_idx]),  # Va
    ]

    return H, h, S


def get_measurements_and_deviations(se_input: StateEstimationInput, Sbase: float,
                                    use_current_squared_meas:bool = True)-> Tuple[Vec, Vec, ObjVec]:
    """
    get_measurements_and_deviations the measurements into "measurements" and "sigma"
    ordering: Pinj, Pflow, Qinj, Qflow, Iflow, Vm
    :param se_input: StateEstimationInput object
    :param Sbase: base power in MVA (i.e. 100 MVA)
    :return: measurements vector in per-unit, sigma vector in per-unit
    """

    nz = se_input.size()
    measurements = np.zeros(nz, dtype=object)
    magnitudes = np.zeros(nz)
    sigma = np.zeros(nz)

    # go through the measurements in order and form the vectors
    k = 0
    for lst in [se_input.p_inj,
                se_input.q_inj,
                se_input.pg_inj,
                se_input.qg_inj,
                se_input.pf_value,
                se_input.pt_value,
                se_input.qf_value,
                se_input.qt_value]:
        for m in lst:
            magnitudes[k] = m.get_value_pu(Sbase)
            sigma[k] = m.get_standard_deviation_pu(Sbase)
            measurements[k] = m
            k += 1
    if not use_current_squared_meas:
        for lst in [se_input.if_value, se_input.it_value]:
            for m in lst:
                I_pu = m.get_value_pu(Sbase)
                sig_I = m.get_standard_deviation_pu(Sbase)

                # Use current magnitude directly (more stable)
                y = max(abs(I_pu), 1e-4)  # Avoid zero
                sig_y = sig_I

                magnitudes[k] = y
                sigma[k] = sig_y
                measurements[k] = m
                k += 1
    else:
        # current measurements need to be squared
        for lst in [se_input.if_value,
                    se_input.it_value]:
            for m in lst:
                magnitudes[k] = np.power(m.get_value_pu(Sbase), 2)
                sigma[k] = m.get_standard_deviation_pu(Sbase)
                measurements[k] = m
                k += 1

    for lst in [se_input.vm_value,
                se_input.va_value]:
        for m in lst:
            magnitudes[k] = m.value
            sigma[k] = m.sigma
            measurements[k] = m
            k += 1

    return magnitudes, sigma, measurements


def b_test(sigma2: Vec,
           H: csc_matrix,
           dz: np.ndarray,
           HtWH: csc_matrix,
           c_threshold: float = 4.0,
           logger: Logger | None = None):
    """
    From RELIABLE BAD DATA PROCESSING FOR REAL-TIME STATE ESTIMATION, 1983
    Monticelli & Garcia (1983) 'b-test' bad data detection
    :param sigma2: sigma 2
    :param H: Jacobian at the solution (m x k)
    :param dz: residuals r = z - h(x^) (length m)
    :param HtWH: G = H^T W H (k x k)
    :param c_threshold: detection threshold 'c' (use 4.0 as in the paper)
    :return:
        'r'      : residuals r_i
        'sigma2' : sigma_i^2
        'Pii'    : residual variances P_ii
        'rN'     : normalized residuals r_i / sqrt(P_ii)
        'imax'   : index of largest |rN|
        'b'      : b at imax
        'is_bad' : bool
    """

    m, k = H.shape

    # Factorize G once, then solve G y = H_i^T for each i
    # Use LU so we can reuse for many RHS
    lu = factorized(HtWH.tocsc())
    # For the system to be observable the eigenvalues should be greater than zero -> matrix pos definate
    eigvals = np.linalg.eigvalsh(HtWH.toarray())
    assert np.all(eigvals > 0), "Unobservable-System"

    # Compute h_i = H_i G^{-1} H_i^T and then Pii = sigma_i^2 - h_i
    # Do it row-by-row but reusing the factorization
    Pii = np.empty(m, dtype=float)

    # iterate efficiently over rows of H
    H_csr = H.tocsr()

    for i in range(m):
        # get sparse row i as (data, indices)
        row = H_csr.getrow(i)
        if row.nnz == 0:
            # no sensitivity: Pii = sigma^2 (critical measurement with no redundancy)
            Pii[i] = sigma2[i]
        else:

            # Solve y = G^{-1} H_i^T
            y = lu(row.T.toarray())  # shape (k,1)

            # h_i = H_i y
            h_i = float(row.dot(y).ravel()[0])
            Pii[i] = sigma2[i] - h_i

            # numerical guard
            if Pii[i] <= 0:
                # If numerical issues produce tiny negative values, clamp to a small positive eps
                Pii[i] = max(Pii[i], 1e-14)
            elif Pii[i] < 1e-10:  # Too small - likely numerical error
                Pii[i] = max(1e-10, sigma2[i] * 0.01)  # Conservative estimate
            elif Pii[i] > sigma2[i]:  # Impossible physically
                logger.add_warning(f"Pii[{i}] > sigma2[{i}] ({Pii[i]:.2e} > {sigma2[i]:.2e})")
                Pii[i] = sigma2[i] * 0.5  # Reasonable default
    r = dz
    rN = r / np.sqrt(Pii)

    imax = np.argmax(np.abs(rN)).astype(int)
    # b_i = (sigma_i / Pii) * r_i   with sigma_i = sqrt(sigma2_i)
    b = (np.sqrt(sigma2[imax]) / Pii[imax]) * r[imax]

    # compute where the measurements are bad
    is_bad = np.abs(b) > c_threshold

    return r, sigma2, Pii, rN, imax, b, is_bad


def solve_se_lm(nc: NumericalCircuit,
                Ybus: CscMat,
                Yf: CscMat,
                Yt: CscMat,
                Yshunt_bus: CxVec,
                F: IntVec,
                T: IntVec,
                Cf: csc_matrix,
                Ct: csc_matrix,
                se_input: StateEstimationInput,
                vd: IntVec,
                pv: IntVec,
                no_slack: IntVec,
                tol=1e-9,
                max_iter=100,
                verbose: int = 0,
                c_threshold: float = 4.0,
                prefer_correct: bool = False,
                fixed_slack: bool = False,
                logger: Logger | None = None) -> NumericStateEstimationResults:
    """
    Solve the state estimation problem using the Levenberg-Marquadt method
    :param nc: instance of NumericalCircuit
    :param Ybus: Admittance matrix
    :param Yf: Admittance matrix of the from Branches
    :param Yt: Admittance matrix of the to Branches
    :param Yshunt_bus: Array of shunt admittances
    :param F: array with the from bus indices of all the Branches
    :param T: array with the to bus indices of all the Branches
    :param Cf:
    :param Ct:
    :param se_input: state estimation input instance (contains the measurements)
    :param vd: array of slack node indices
    :param pv: array of PV node indices
    :param no_slack: array of non-slack node indices
    :param tol: Tolerance
    :param max_iter: Maximum nuber of iterations
    :param verbose: Verbosity level
    :param c_threshold: Bad data detection threshold 'c' (4 as default)
    :param prefer_correct: if true the measurements are corrected instead of deleted
    :param fixed_slack: if true, the measurements on the slack bus are omitted
    :param logger: log it out
    :return: NumericPowerFlowResults instance
    """
    start_time = time.time()
    # confidence_value = 0.95
    bad_data_detected = False
    logger = logger if logger is not None else Logger()

    n_no_slack = len(no_slack)
    n = Ybus.shape[0]
    V = nc.bus_data.Vbus.copy()
    Va = np.angle(V)
    Vm = np.abs(V)
    load_per_bus = nc.load_data.get_injections_per_bus() / nc.Sbase

    # pick the measurements and uncertainties (initially in physical units: MW, MVAr, A, pu V)
    z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase)

    # Levenberg-Marquardt method
    iter_ = 0
    converged = False
    norm_f = 1e20
    nu = 2.0
    error_list = list()
    # first computation of the jacobian and free term
    H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct, se_input, no_slack, load_per_bus, fixed_slack)

    # compute the weights matrix using per-unit sigma
    sigma2 = np.power(sigma, 2.0)
    W_vec = 1.0 / sigma2
    W = diags(W_vec)

    # measurements error (in per-unit)
    dz = z - h

    # compose the jacobian of the problem
    HtW = H.T @ W
    Gx = HtW @ H

    # compose the residual
    gx = HtW @ dz

    # measurements error (in per-unit)
    # dz = z - h

    # first value of mu
    mu = 1e-3 * float(Gx.diagonal().max())

    # system matrix for levenberg-marquardt
    Idn = diags(np.full(Gx.shape[0], mu))
    Asys = Gx.T @ Gx + Idn
    rhs = Gx.T @ gx

    # set the previous objective function value
    obj_val_prev = 1e20

    # objective function
    obj_val = 0.5 * dz @ (W * dz)

    while not converged and iter_ < max_iter:

        # Solve the increment
        dx = spsolve(Asys, rhs)

        if norm_f < (tol * 10.0):
            try:
                r, sigma2, Pii, rN, imax, b, bad_data_detected = b_test(sigma2=sigma2, H=H, dz=dz, HtWH=Gx,
                                                                    c_threshold=c_threshold, logger=logger)
            except AssertionError as e:
                if str(e) == "Unobservable-System":
                    return NumericStateEstimationResults(V=V,
                                                         Scalc=Scalc,
                                                         norm_f=norm_f,
                                                         converged=False,
                                                         iterations=iter_,
                                                         elapsed=time.time() - start_time,
                                                         bad_data_detected=False,
                                                         is_observable=False)


            if bad_data_detected:
                if prefer_correct:
                    if Pii[imax] > 1e-10:  # if the value is not corrected in b_test alone
                        z_tilde_imax = z[imax] - (sigma[imax] ** 2 / Pii[imax]) * r[imax]

                        logger.add_info("Measurement corrected",
                                        device=measurements[imax].api_object.name,
                                        device_class=measurements[imax].device_type.value,
                                        device_property="value",
                                        value=z[imax],
                                        expected_value=z_tilde_imax)

                        # correct the bad data index
                        z[imax] = z_tilde_imax
                    else:
                        # Pii is very small - this is likely a critical measurement
                        # TODO -> Do not delete
                        logger.add_warning(f"Measurement {imax} appears critical (Pii={Pii[imax]:.2e})")
                        # Don't correct critical measurements, just remove them
                        # delete measurements
                        mask = np.ones(len(z), dtype=int)
                        mask[imax] = 0

                        se_input = se_input.slice_with_mask(mask=mask)

                        # pick the measurements and uncertainties (initially in physical units: MW, MVAr, A, pu V)
                        z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase)

                        # compute the weights matrix using per-unit sigma
                        sigma2 = np.power(sigma, 2.0)
                        cov = 1.0 / sigma2
                        W = diags(cov).tocsc()
                else:

                    logger.add_info("Measurement deleted",
                                    device=measurements[imax].api_object.name,
                                    device_class=measurements[imax].device_type.value,
                                    device_property="value",
                                    value=z[imax],
                                    expected_value="")

                    # delete measurements
                    mask = np.ones(len(z), dtype=int)
                    mask[imax] = 0

                    se_input = se_input.slice_with_mask(mask=mask)

                    # pick the measurements and uncertainties (initially in physical units: MW, MVAr, A, pu V)
                    z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase)

                    # compute the weights matrix using per-unit sigma
                    sigma2 = np.power(sigma, 2.0)
                    cov = 1.0 / sigma2
                    W = diags(cov).tocsc()

        # L-M ratios of convergence
        dF = obj_val_prev - obj_val
        dL = 0.5 * dx @ (mu * dx + gx)

        if (dF != 0.0) and (dL > 0.0):
            rho = dF / dL
            mu *= max([1.0 / 3.0, 1.0 - np.power(2 * rho - 1, 3.0)])
            nu = 2.0

            # modify the solution
            if fixed_slack:
                dVa = dx[:n_no_slack]
                dVm = dx[n_no_slack:]
                Va[no_slack] += dVa
                Vm[no_slack] += dVm  # yes, this is for all the buses
            else:
                dVa = dx[:n_no_slack]
                dVm = dx[n_no_slack:]
                Va[no_slack] += dVa
                Vm += dVm  # yes, this is for all the buses

            V = Vm * np.exp(1j * Va)

            # if verbose > 1:
            #     dva = np.zeros(n)
            #     dva[: n_no_slack] = dVa
            #     df = pd.DataFrame(data={"dVa": dva, "dVm": dVm, "Va": Va, "Vm": Vm})
            #     print(df)

            # update system
            H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct, se_input, no_slack, load_per_bus, fixed_slack)

            # record the previous objective function value
            obj_val_prev = obj_val

            # measurements error (in per-unit)
            dz = z - h

            # compose the jacobian of the problem
            HtW = H.T @ W
            Gx = HtW @ H

            # compose the residual
            gx = HtW @ dz
            #
            # # measurements error (in per-unit)
            # dz = z - h

            # system matrix for levenberg-marquardt
            Idn = diags(np.full(Gx.shape[0], mu))
            Asys = Gx.T @ Gx + Idn
            rhs = Gx.T @ gx

            # objective function
            obj_val = 0.5 * dz @ (W * dz)

        else:
            mu *= nu
            nu *= 2.0

        # compute the convergence
        norm_f = np.linalg.norm(dx, np.inf)
        converged = norm_f < tol

        error_list.append(norm_f)

        if verbose > 0:
            print(f"Norm_f {norm_f}")

        # update loops
        iter_ += 1

    # Compute the Branches power and the slack buses power
    Sf, St, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process_nonlinear(
        Sbus=Scalc,
        V=V,
        F=nc.passive_branch_data.F,
        T=nc.passive_branch_data.T,
        pv=pv,
        vd=vd,
        Ybus=Ybus,
        Yf=Yf,
        Yt=Yt,
        Yshunt_bus=Yshunt_bus,
        branch_rates=nc.passive_branch_data.rates,
        Sbase=nc.Sbase)

    if verbose > 1:
        from matplotlib import pyplot as plt
        plt.plot(error_list)
        plt.yscale('log')
        # plt.show()

    return NumericStateEstimationResults(V=V,
                                         Scalc=Scalc,
                                         m=nc.active_branch_data.tap_module,
                                         tau=nc.active_branch_data.tap_angle,
                                         Sf=Sf,
                                         St=St,
                                         If=If,
                                         It=It,
                                         loading=loading,
                                         losses=losses,
                                         Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                         St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                         If_vsc=np.zeros(nc.nvsc, dtype=float),
                                         It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                         losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                         loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                         Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         norm_f=norm_f,
                                         converged=converged,
                                         iterations=iter_,
                                         is_observable=bool(converged),
                                         elapsed=time.time() - start_time,
                                         bad_data_detected=bad_data_detected)


def solve_se_nr(nc: NumericalCircuit,
                Ybus: CscMat,
                Yf: CscMat,
                Yt: CscMat,
                Yshunt_bus: CxVec,
                F: IntVec,
                T: IntVec,
                Cf: csc_matrix,
                Ct: csc_matrix,
                se_input: StateEstimationInput,
                vd: IntVec,
                pv: IntVec,
                no_slack: IntVec,
                tol=1e-9,
                max_iter=100,
                verbose: int = 0,
                c_threshold: float = 4.0,
                prefer_correct: bool = False,
                fixed_slack: bool = False,
                logger: Logger | None = None) -> NumericStateEstimationResults:
    """
    Solve the state estimation problem using the Levenberg-Marquadt method
    :param nc: instance of NumericalCircuit
    :param Ybus: Admittance matrix
    :param Yf: Admittance matrix of the from Branches
    :param Yt: Admittance matrix of the to Branches
    :param Yshunt_bus: Array of shunt admittances
    :param F: array with the from bus indices of all the Branches
    :param T: array with the to bus indices of all the Branches
    :param Cf:
    :param Ct:
    :param se_input: state estimation input instance (contains the measurements)
    :param vd: array of slack node indices
    :param pv: array of PV node indices
    :param no_slack: array of non-slack node indices
    :param tol: Tolerance
    :param max_iter: Maximum nuber of iterations
    :param verbose: Verbosity level
    :param c_threshold: Bad data detection threshold 'c' (4 as default)
    :param prefer_correct: if true the measurements are corrected instead of deleted
    :param fixed_slack: if true, the measurements on the slack bus are omitted
    :param logger: log it out
    :return: NumericPowerFlowResults instance
    """
    start_time = time.time()
    # confidence_value = 0.95
    bad_data_detected = False
    logger = logger if logger is not None else Logger()

    n_no_slack = len(no_slack)

    n = Ybus.shape[0]
    V = nc.bus_data.Vbus.copy()
    Va = np.angle(V)
    Vm = np.abs(V)
    Scalc = np.zeros(nc.nbus, dtype=complex)

    load_per_bus = nc.load_data.get_injections_per_bus() / nc.Sbase

    # pick the measurements and uncertainties (initially in physical units: MW, MVAr, A, pu V)
    z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase)

    # compute the weights matrix using per-unit sigma
    sigma2 = np.power(sigma, 2.0)
    W_vec = 1.0 / sigma2
    W = diags(W_vec)

    iter_ = 0
    converged = False
    norm_f = 1e20

    error_list = list()

    while not converged and iter_ < max_iter:

        # update system
        H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct, se_input, no_slack, load_per_bus, fixed_slack)

        # measurements error (in per-unit)
        dz = z - h

        # compose the jacobian of the problem
        HtW = H.T @ W
        Gx = HtW @ H

        # compose the residual
        gx = HtW @ dz

        # Solve the increment
        dx = spsolve(Gx, gx) # (HtW @ dz) * (new_state) = HtW @ H

        # modify the solution
        if fixed_slack:
            dVa = dx[:n_no_slack]
            dVm = dx[n_no_slack:]
            Va[no_slack] += dVa
            Vm[no_slack] += dVm  # yes, this is for all the buses
        else:
            dVa = dx[:n_no_slack]
            dVm = dx[n_no_slack:]
            Va[no_slack] += dVa
            Vm += dVm  # yes, this is for all the buses

        V = Vm * np.exp(1j * Va)

        # This is because this formulation may produce negative Vm
        # and by doing this it is corrected
        Vm = np.abs(V)
        Va = np.angle(V)

        # if norm_f < (tol * 10.0):
        #     r, sigma2, Pii, rN, imax, b, bad_data_detected = b_test(sigma2=sigma2, H=H, dz=dz, HtWH=Gx,
        #                                                             c_threshold=c_threshold, logger=logger)
        #
        #     if bad_data_detected:
        #         if prefer_correct:
        #             if Pii[imax] > 1e-10:  # if the value is not corrected in b_test alone
        #                 z_tilde_imax = z[imax] - (sigma[imax] ** 2 / Pii[imax]) * r[imax]
        #
        #                 logger.add_info("Measurement corrected",
        #                                 device=measurements[imax].api_object.name,
        #                                 device_class=measurements[imax].device_type.value,
        #                                 device_property="value",
        #                                 value=z[imax],
        #                                 expected_value=z_tilde_imax)
        #
        #                 # correct the bad data index
        #                 z[imax] = z_tilde_imax
        #             else:
        #                 # Pii is very small - this is likely a critical measurement
        #                 logger.add_warning(f"Measurement {imax} appears critical (Pii={Pii[imax]:.2e})")
        #                 # Don't correct critical measurements, just remove them
        #                 # delete measurements
        #                 mask = np.ones(len(z), dtype=int)
        #                 mask[imax] = 0
        #
        #                 se_input = se_input.slice_with_mask(mask=mask)
        #
        #                 # pick the measurements and uncertainties (initially in physical units: MW, MVAr, A, pu V)
        #                 z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase)
        #
        #                 # compute the weights matrix using per-unit sigma
        #                 sigma2 = np.power(sigma, 2.0)
        #                 cov = 1.0 / sigma2
        #                 W = diags(cov).tocsc()
        #         else:
        #
        #             logger.add_info("Measurement deleted",
        #                             device=measurements[imax].api_object.name,
        #                             device_class=measurements[imax].device_type.value,
        #                             device_property="value",
        #                             value=z[imax],
        #                             expected_value="")
        #
        #             # delete measurements
        #             mask = np.ones(len(z), dtype=int)
        #             mask[imax] = 0
        #
        #             se_input = se_input.slice_with_mask(mask=mask)
        #
        #             # pick the measurements and uncertainties (initially in physical units: MW, MVAr, A, pu V)
        #             z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase)
        #
        #             # compute the weights matrix using per-unit sigma
        #             sigma2 = np.power(sigma, 2.0)
        #             cov = 1.0 / sigma2
        #             W = diags(cov).tocsc()

        if verbose > 1:
            dva = np.zeros(n)
            dva[: n_no_slack] = dVa
            df = pd.DataFrame(data={"dVa": dva, "dVm": dVm, "Va": Va, "Vm": Vm})
            print(df)

        # compute the convergence
        norm_f = np.linalg.norm(gx, np.inf)
        converged = norm_f < tol

        error_list.append(norm_f)

        if verbose > 0:
            print(f"Norm_f {norm_f}")

        # update loops
        iter_ += 1

    # Compute the Branches power and the slack buses power
    Sf, St, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process_nonlinear(
        Sbus=Scalc,
        V=V,
        F=nc.passive_branch_data.F,
        T=nc.passive_branch_data.T,
        pv=pv,
        vd=vd,
        Ybus=Ybus,
        Yf=Yf,
        Yt=Yt,
        Yshunt_bus=Yshunt_bus,
        branch_rates=nc.passive_branch_data.rates,
        Sbase=nc.Sbase)

    if verbose > 1:
        from matplotlib import pyplot as plt
        plt.plot(error_list)
        plt.yscale('log')
        # plt.show()

    return NumericStateEstimationResults(V=V,
                                         Scalc=Scalc,
                                         m=nc.active_branch_data.tap_module,
                                         tau=nc.active_branch_data.tap_angle,
                                         Sf=Sf,
                                         St=St,
                                         If=If,
                                         It=It,
                                         loading=loading,
                                         losses=losses,
                                         Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                         St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                         If_vsc=np.zeros(nc.nvsc, dtype=float),
                                         It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                         losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                         loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                         Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         norm_f=norm_f,
                                         converged=bool(converged),
                                         iterations=iter_,
                                         elapsed=time.time() - start_time,
                                         is_observable=bool(converged),
                                         bad_data_detected=bad_data_detected)

def solve_se_gauss_newton(nc: NumericalCircuit,
                          Ybus: CscMat,
                          Yf: CscMat,
                          Yt: CscMat,
                          Yshunt_bus: CxVec,
                          F: IntVec,
                          T: IntVec,
                          Cf: csc_matrix,
                          Ct: csc_matrix,
                          se_input: StateEstimationInput,
                          vd: IntVec,
                          pv: IntVec,
                          no_slack: IntVec,
                          tol=1e-9,
                          max_iter=100,
                          verbose: int = 0,
                          c_threshold: float = 4.0,
                          prefer_correct: bool = False,
                          fixed_slack: bool = False,
                          logger: Logger | None = None) -> NumericStateEstimationResults:
    """
    Linearize the non-linear measurement model around the current state estimate (Jacobian H)

    Solve the linear WLS problem: Δx = 1/(HᵀWH)HᵀWdz

    Update the state: x = x + Δx

    Repeat until convergence
    """
    start_time = time.time()
    logger = logger if logger is not None else Logger()

    # Initialization
    n_no_slack = len(no_slack)
    V = nc.bus_data.Vbus.copy()  # initial guess (can be flat start or power flow solution)
    Va = np.angle(V)
    Vm = np.abs(V)
    load_per_bus = nc.load_data.get_injections_per_bus() / nc.Sbase

    # Get measurements
    z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase, use_current_squared_meas=True)
    # Weight matrix with regularization to avoid numerical issues
    sigma2 = np.power(sigma, 2.0)
    W_vec = 1.0 / np.maximum(sigma2, 1e-10)  # Avoid division by zero
    W = diags(W_vec)

    # Simple iterative method (Gauss-Newton style)
    iter_ = 0
    converged = False
    norm_f = 1e20
    error_list = []
    # Step control parameters
    max_step_va = 0.3  # radians
    max_step_vm = 0.2  # per unit
    relaxation = 1.1   # initial step relaxation
    obj_val_prev = 1e30

    while not converged and iter_ < max_iter:
        # Compute Jacobian and measurement function at current state
        H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct, se_input, no_slack, load_per_bus, fixed_slack)

        # Measurement residuals
        dz = z - h
        # Objective function value
        obj_val = 0.5 * dz @ (W * dz)

        # Build normal equations
        HtW = H.T @ W
        G = HtW @ H  # Gain matrix
        # Add regularization to handle ill-conditioning
        reg_factor = 1e-6 * G.diagonal().max()
        G_reg = G + reg_factor * sparse.eye(G.shape[0])
        g = HtW @ dz  # Gradient

        # Solve for state update
        try:
            dx = spsolve(G_reg, g)
        except:
            # If matrix is singular, use pseudo-inverse
            dx = spilu(G).solve(g)
        #Update state
        if fixed_slack:
            dVa = dx[:n_no_slack]
            dVm = dx[n_no_slack:]
            dVa = np.clip(dVa, -max_step_va, max_step_va)
            dVm = np.clip(dVm, -max_step_vm, max_step_vm)
            Va[no_slack] += dVa
            Vm[no_slack] += dVm
        else:
            dVa = dx[:n_no_slack]
            dVm = dx[n_no_slack:]
            dVa = np.clip(dVa, -max_step_va, max_step_va)
            dVm = np.clip(dVm, -max_step_vm, max_step_vm)
            Va[no_slack] += dVa
            Vm += dVm

        V = Vm * np.exp(1j * Va)

        # Adaptive step control based on objective function improvement
        # if obj_val < obj_val_prev:
        #     # Good step - slightly increase relaxation
        #     relaxation = min(1.0, relaxation * 1.1)
        # else:
        #     # Bad step - reduce step size and backtrack
        #     relaxation *= 0.8
        #     if fixed_slack:
        #         Va[no_slack] -= relaxation * dVa
        #         Vm[no_slack] -= relaxation * dVm
        #     else:
        #         Va[no_slack] -= relaxation * dVa
        #         Vm -= relaxation * dVm
        #     V = Vm * np.exp(1j * Va)
        #     continue  # Recompute with smaller step

        obj_val_prev = obj_val
        Vm = np.abs(V)
        Va = np.angle(V)
        # Check convergence
        norm_f = np.linalg.norm(dx, np.inf)
        converged = norm_f < tol

        error_list.append(norm_f)

        if verbose > 0:
            print(f"Iter {iter_}: norm_f = {norm_f:.6e}, obj_val = {obj_val:.6e}, "
                  f"relax = {relaxation:.3f}")

        iter_ += 1

        #  Add bad data detection like LM does
        # if norm_f < tol * 10 and iter_ > 3:
        #     r, sigma2, Pii, rN, imax, b, bad_data_detected = b_test(
        #         sigma2=sigma2, H=H, dz=dz, HtWH=G, c_threshold=c_threshold, logger=logger
        #     )
        #
        #     if bad_data_detected and prefer_correct:
        #         # Implement correction logic similar to LM
        #         if Pii[imax] > 1e-10:
        #             z_tilde_imax = z[imax] - (sigma[imax] ** 2 / Pii[imax]) * r[imax]
        #             z[imax] = z_tilde_imax
        #             if verbose > 0:
        #                 logger.add_info(f"Corrected measurement {imax}")

    # Final processing
    Sf, St, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process_nonlinear(
        Sbus=Scalc, V=V, F=nc.passive_branch_data.F, T=nc.passive_branch_data.T,
        pv=pv, vd=vd, Ybus=Ybus, Yf=Yf, Yt=Yt, Yshunt_bus=Yshunt_bus,
        branch_rates=nc.passive_branch_data.rates, Sbase=nc.Sbase
    )

    end_time = time.time()
    logger.add_info(f"State estimation completed in {iter_} iterations, time: {end_time - start_time:.3f}s")

    if verbose > 1:
        from matplotlib import pyplot as plt
        plt.plot(error_list)
        plt.yscale('log')
        # plt.show()

    return NumericStateEstimationResults(V=V,
                                         Scalc=Scalc,
                                         m=nc.active_branch_data.tap_module,
                                         tau=nc.active_branch_data.tap_angle,
                                         Sf=Sf,
                                         St=St,
                                         If=If,
                                         It=It,
                                         loading=loading,
                                         losses=losses,
                                         Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                         St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                         If_vsc=np.zeros(nc.nvsc, dtype=float),
                                         It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                         losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                         loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                         Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         norm_f=norm_f,
                                         converged=bool(converged),
                                         iterations=iter_,
                                         elapsed=time.time() - start_time,
                                         is_observable=bool(converged),
                                         bad_data_detected=False)


def decoupled_state_estimation(nc: NumericalCircuit,
                          Ybus: CscMat,
                          Yf: CscMat,
                          Yt: CscMat,
                          Yshunt_bus: CxVec,
                          F: IntVec,
                          T: IntVec,
                          Cf: csc_matrix,
                          Ct: csc_matrix,
                          se_input: StateEstimationInput,
                          vd: IntVec,
                          pv: IntVec,
                          no_slack: IntVec,
                          tol=1e-9,
                          max_iter=100,
                          verbose: int = 0,
                          c_threshold: float = 4.0,
                          prefer_correct: bool = False,
                          fixed_slack: bool = False,
                          logger: Logger | None = None) -> NumericStateEstimationResults:
    """
    Fast decoupled WLS state estimator using LU decomposition.
    Active power -> angles
    Reactive power -> voltage magnitudes
    """
    start_time = time.time()
    logger if logger is not None else Logger()
    load_per_bus = nc.load_data.get_injections_per_bus() / nc.Sbase

    # --- Initialize voltages ---
    V = nc.bus_data.Vbus.copy()
    Va = np.angle(V)
    Vm = np.abs(V)

    # Identify non-slack buses
    non_slack_buses = no_slack  # Your no_slack variable
    n_non_slack = len(non_slack_buses)

    # --- Measurement vector and weights ---
    z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase,
                                                             use_current_squared_meas=False)
    W = diags(1.0 / sigma ** 2, 0, format="csc")


    # --- Create measurement type mapping based on processing order ---
    # The measurements are processed in this fixed order:
    # 1. p_inj, 2. q_inj, 3. pg_inj, 4. qg_inj,
    # 5. pf_value, 6. pt_value, 7. qf_value, 8. qt_value,
    # 9. if_value, 10. it_value, 11. vm_value, 12. va_value

    # Count measurements in each category
    counts = [
        len(se_input.p_inj), len(se_input.q_inj),
        len(se_input.pg_inj), len(se_input.qg_inj),
        len(se_input.pf_value), len(se_input.pt_value),
        len(se_input.qf_value), len(se_input.qt_value),
        len(se_input.if_value), len(se_input.it_value),
        len(se_input.vm_value), len(se_input.va_value)
    ]

    # Create measurement type array
    measurement_types = []
    for i, count in enumerate(counts):
        if i in [0, 2, 4, 5]:  # p_inj, pg_inj, pf_value, pt_value
            measurement_types.extend(['P'] * count)
        elif i in [1, 3, 6, 7]:  # q_inj, qg_inj, qf_value, qt_value
            measurement_types.extend(['Q'] * count)
        else:  # current and voltage measurements (I, V, θ)
            measurement_types.extend(['Other'] * count)

    measurement_types = np.array(measurement_types)

    # Create indices for active and reactive measurements
    a_idx = np.where(measurement_types == 'P')[0]  # Active power measurements
    r_idx = np.where(measurement_types == 'Q')[0]  # Reactive power measurements

    if verbose > 0:
        logger.add_info(f"Active power measurements: {len(a_idx)}")
        logger.add_info(f"Reactive power measurements: {len(r_idx)}")

    relax_theta = 1.0  # angle relaxation
    relax_V = 0.5  # voltage relaxation
    reg_eps = 1e-8  # tiny reg for Ga
    reg_eps_v = 1e-6  # slightly larger reg for Gr
    max_theta_step = 0.3
    max_V_step = 0.2
    iter_count = 0
    converged = False
    previous_max_update = 1e6

    while not converged and iter_count < max_iter:
        iter_count += 1

        # --- 1) Recompute Jacobian and measurement function
        H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct,
                                  se_input, non_slack_buses, load_per_bus, fixed_slack)
        if H.shape[0] != z.shape[0]:
            raise ValueError(f"H rows ({H.shape[0]}) != len(z) ({len(z)}) - check measurement ordering")

        dz = z - h

        # --- 2) Build and factorize Ga (P-subsystem)
        Ha = H.tocsr()[a_idx, :n_non_slack]  # dP/dθ (rows = P-meas, cols = θ_non_slack)
        Wa = W[a_idx, :][:, a_idx].tocsc()
        Ga = Ha.T @ Wa @ Ha
        if Ga.shape[0] > 0:
            #Ga_reg = Ga + eps_base * np.diag(np.max(np.abs(Ga), axis=0))
            Ga = Ga + reg_eps * diags(np.ones(Ga.shape[0]), 0, format='csc')

        # --- 3) Compute Ta
        Ta = Ha.T @ Wa @ dz[a_idx]/1
        # --- 4) Solve Ga * dtheta = Ta
        try:
            lu_ga = splu(Ga)
            dtheta = lu_ga.solve(Ta)
        except Exception:
            dtheta = lstsq(Ga.toarray(), Ta, rcond=None)[0]

        # safety clip + apply relaxation
        if np.any(np.abs(dtheta) > max_theta_step):
            dtheta = np.clip(dtheta, -max_theta_step, max_theta_step)
        Va[non_slack_buses] += relax_theta * dtheta
        V = Vm * np.exp(1j * Va)  # recompute complex voltage after angle update

        # --- 5) Recompute Jacobian/h after angle update (needed for Q-subsystem) ---
        H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct,
                                  se_input, non_slack_buses, load_per_bus, fixed_slack)
        dz = z - h

        # --- 6) Build and factorize Gr (Q-subsystem)
        Hr = H.tocsr()[r_idx, n_non_slack:2 * n_non_slack]  # dQ/dV for non-slack V columns
        Wr = W[r_idx, :][:, r_idx].tocsc()
        Gr = Hr.T @ Wr @ Hr
        if Gr.shape[0] > 0:
            #Gr_reg = Gr + eps_base * np.diag(np.max(np.abs(Gr), axis=0))
            Gr = Gr + reg_eps_v * diags(np.ones(Gr.shape[0]), 0, format='csc')

        # --- 7) Compute Tr and solve Gr * dV = Tr
        dz_r_scaled = dz[r_idx] / np.maximum(Vm, 0.01)
        Tr = Hr.T @ Wr @ dz_r_scaled
        try:
            lu_gr = splu(Gr)
            dV = lu_gr.solve(Tr)
        except Exception:
            dV = lstsq(Gr.toarray(), Tr, rcond=None)[0]

        # safety clip + apply relaxation
        if np.any(np.abs(dV) > max_V_step):
            dV = np.clip(dV, -max_V_step, max_V_step)
        Vm[non_slack_buses] += relax_V * dV
        V = Vm * np.exp(1j * Va)

        # --- 8) Convergence & divergence checks
        max_theta_update = np.max(np.abs(dtheta)) if dtheta.size > 0 else 0.0
        max_V_update = np.max(np.abs(dV)) if dV.size > 0 else 0.0
        norm_f = max(max_theta_update, max_V_update)

        if verbose > 0:
            logger.add_info(f"Iter {iter_count}: max update = {norm_f:.6f}, max |dz| = {np.max(np.abs(dz)):.6f}")

        # simple divergence guard
        if norm_f > previous_max_update * 5 and iter_count > 1:
            if verbose > 0:
                logger.add_info(f"Divergence detected at iteration {iter_count}")
                logger.add_info(f"Updates: theta={max_theta_update:.6f}, V={max_V_update:.6f}")
            break

        previous_max_update = norm_f

        if norm_f < tol*100: # decoupled solution checks for both active & reactive parts against tolerance,
            # so its a bit lower, but it also provides same(very) result for all tests with more stricter tol
            converged = True
            if verbose > 0:
                logger.add_info(f"Converged at iter {iter_count}")
            break

    Sf, St, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process_nonlinear(
        Sbus=Scalc, V=V, F=nc.passive_branch_data.F, T=nc.passive_branch_data.T,
        pv=pv, vd=vd, Ybus=Ybus, Yf=Yf, Yt=Yt, Yshunt_bus=Yshunt_bus,
        branch_rates=nc.passive_branch_data.rates, Sbase=nc.Sbase
    )
    return NumericStateEstimationResults(V=V,
                                         Scalc=Scalc,
                                         m=nc.active_branch_data.tap_module,
                                         tau=nc.active_branch_data.tap_angle,
                                         Sf=Sf,
                                         St=St,
                                         If=If,
                                         It=It,
                                         loading=loading,
                                         losses=losses,
                                         Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                         St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                         If_vsc=np.zeros(nc.nvsc, dtype=float),
                                         It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                         losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                         loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                         Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                         norm_f=norm_f,
                                         converged=bool(converged),
                                         iterations=iter_count,
                                         elapsed=time.time() - start_time,
                                         is_observable=bool(converged), # by default it is observable if it converges
                                         bad_data_detected=False)