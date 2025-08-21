# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import time
from typing import Tuple

import pandas as pd
from scipy.sparse import hstack as sphs, vstack as spvs, csc_matrix, diags
from scipy.sparse.linalg import factorized, spsolve
import numpy as np
from GridCalEngine.Simulations.StateEstimation.state_estimation_inputs import StateEstimationInput
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import power_flow_post_process_nonlinear
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Simulations.Derivatives.matpower_derivatives import (dSbus_dV_matpower, dSbr_dV_matpower,
                                                                        dIbr_dV_matpower)
from GridCalEngine.Simulations.StateEstimation.state_estimation_results import NumericStateEstimationResults
from GridCalEngine.basic_structures import CscMat, IntVec, CxVec, Vec, ObjVec, Logger


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

    # slice derivatives
    dP_dVa = dS_dVa[np.ix_(inputs.p_idx, pvpq)].real
    dQ_dVa = dS_dVa[np.ix_(inputs.q_idx, pvpq)].imag
    dPg_dVa = dS_dVa[np.ix_(inputs.pg_idx, pvpq)].real
    dQg_dVa = dS_dVa[np.ix_(inputs.qg_idx, pvpq)].imag
    dPf_dVa = dSf_dVa[np.ix_(inputs.pf_idx, pvpq)].real
    dPt_dVa = dSt_dVa[np.ix_(inputs.pt_idx, pvpq)].real
    dQf_dVa = dSf_dVa[np.ix_(inputs.qf_idx, pvpq)].imag
    dQt_dVa = dSt_dVa[np.ix_(inputs.qt_idx, pvpq)].imag
    dIf_dVa = np.abs(dIf_dVa[np.ix_(inputs.if_idx, pvpq)])
    dIt_dVa = np.abs(dIt_dVa[np.ix_(inputs.it_idx, pvpq)])
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
        dIf_dVm = np.abs(dIf_dVm[np.ix_(inputs.if_idx, pvpq)])
        dIt_dVm = np.abs(dIt_dVm[np.ix_(inputs.it_idx, pvpq)])
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
        dIf_dVm = np.abs(dIf_dVm[inputs.if_idx, :])
        dIt_dVm = np.abs(dIt_dVm[inputs.it_idx, :])
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
        np.abs(If[inputs.if_idx]),  # If
        np.abs(It[inputs.it_idx]),  # It
        np.abs(V[inputs.vm_idx]),  # Vm
        np.angle(V[inputs.va_idx]),  # Va
    ]

    return H, h, S  # Return Sbus in pu


def get_measurements_and_deviations(se_input: StateEstimationInput, Sbase: float) -> Tuple[Vec, Vec, ObjVec]:
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
                se_input.qt_value,
                se_input.if_value,
                se_input.it_value]:
        for m in lst:
            magnitudes[k] = m.get_value_pu(Sbase)
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
    # For the system to be observable the eigenvalues should be greater than zero -> matric pos definate
    eigvals = np.linalg.eigvalsh(HtWH.toarray())
    assert np.all(eigvals > 0)

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
    nvd = len(vd)
    n = Ybus.shape[0]
    V = nc.bus_data.Vbus.copy()

    load_per_bus = nc.load_data.get_injections_per_bus() / nc.Sbase

    # pick the measurements and uncertainties (initially in physical units: MW, MVAr, A, pu V)
    z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase)

    # compute the weights matrix using per-unit sigma
    sigma2 = np.power(sigma, 2.0)
    cov = 1.0 / sigma2
    W = diags(cov).tocsc()

    # Levenberg-Marquardt method

    iter_ = 0
    if fixed_slack:
        Idn = csc_matrix(np.identity(2 * n - 2 * nvd))  # identity matrix
    else:
        Idn = csc_matrix(np.identity(2 * n - nvd))  # identity matrix

    Va = np.angle(V)
    Vm = np.abs(V)

    converged = False
    norm_f = 1e20
    nu = 2.0
    error_list = list()
    # first computation of the jacobian and free term
    H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct, se_input, no_slack, load_per_bus, fixed_slack)

    # measurements error (in per-unit)
    dz = z - h
    mu = None
    # System matrix
    # H1 = H^t·W
    # H1 = H.transpose() @ W
    #
    # # H2 = H1·H
    # H2 = H1 @ H
    #
    # # set first value of mu (any large number)
    # mu = 1e-3 * H2.diagonal().max()
    #
    # # compute system matrix
    # Gx = H2 + mu * Idn
    #
    # # right hand side
    # # H^t·W·dz
    # gx = H1 @ dz

    # -------------------------------

    w_sqrt = 1.0 / np.sqrt(sigma2)  # length m
    J = H.multiply(w_sqrt[:, None])  # weighted Jacobian
    r_t = w_sqrt * dz  # weighted residual

    # Normal equations: G = J^T J
    G = (J.T @ J).tocsc()

    # Levenberg–Marquardt damping
    if iter_ == 0:  # initialize mu only once
        mu = 1e-3 * float(G.diagonal().max())
    Gx = G + mu * Idn

    # RHS
    gx = J.T @ r_t
    # set the previous objective function value
    obj_val_prev = 1e20

    # objective function
    obj_val = 0.5 * dz @ (W * dz)

    while not converged and iter_ < max_iter:

        # Solve the increment
        # dx = spsolve(Gx, gx)
        solver = factorized(Gx)  # pre-factorize
        dx = solver(gx)  # much faster than spsolve

        if norm_f < (tol * 10.0):
            # bad data detection
            # here we compare the obj func wrt CHI2NV of degree of freedom,
            # degree of freedom is defined as the difference
            # between all the available measurements and min required measurements for observability.
            # deg_of_freedom = len(z_phys) - 2 * n_no_slack
            # threshold_chi2 = chi2.ppf(confidence_value, df=deg_of_freedom)
            # if obj_val <= threshold_chi2:
            #     logger.add_info(f"No bad data detected")
            # else:
            #     bad_data_detected = True
            #     logger.add_warning(f"Bad data detected")
            try:
                r, sigma2, Pii, rN, imax, b, bad_data_detected = b_test(sigma2=sigma2, H=H, dz=dz, HtWH=G,
                                                                        c_threshold=c_threshold, logger=logger)
            except AssertionError as ae:
                logger.add_warning(f"The system is not observable while identifying bad data, {ae}")

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
                                                     elapsed=time.time() - start_time,
                                                     bad_data_detected=bad_data_detected)

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

            if verbose > 1:
                dva = np.zeros(n)
                dva[: n_no_slack] = dVa
                df = pd.DataFrame(data={"dVa": dva, "dVm": dVm, "Va": Va, "Vm": Vm})
                print(df)

            # update system
            H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct, se_input, no_slack, load_per_bus, fixed_slack)

            # measurements error (in per-unit)
            dz = z - h

            # record the previous objective function value
            obj_val_prev = obj_val

            # objective function
            obj_val = 0.5 * dz @ (W * dz)

            # # System matrix
            # # H1 = H^t·W
            # H1 = H.transpose() @ W
            #
            # # H2 = H1·H
            # H2 = H1 @ H
            #
            # # compute system matrix
            # Gx = H2 + mu * Idn
            #
            # # right hand side
            # # H^t·W·dz
            # gx = H1 @ dz

            w_sqrt = 1.0 / np.sqrt(sigma2)  # length m
            J = H.multiply(w_sqrt[:, None])  # weighted Jacobian
            r_t = w_sqrt * dz  # weighted residual

            # Normal equations: G = J^T J
            G = (J.T @ J).tocsc()

            # Levenberg–Marquardt damping
            if mu is None or iter_ == 0:  # initialize mu only once
                mu = 1e-3 * float(G.diagonal().max())
            Gx = G + mu * Idn

            # RHS
            gx = J.T @ r_t

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
        plt.show()

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

    load_per_bus = nc.load_data.get_injections_per_bus() / nc.Sbase

    # pick the measurements and uncertainties (initially in physical units: MW, MVAr, A, pu V)
    z, sigma, measurements = get_measurements_and_deviations(se_input=se_input, Sbase=nc.Sbase)

    # compute the weights matrix using per-unit sigma
    sigma2 = np.power(sigma, 2.0)
    R_inv = diags(1.0 / sigma2)

    iter_ = 0
    converged = False
    norm_f = 1e20

    error_list = list()

    while not converged and iter_ < max_iter:

        # update system
        H, h, Scalc = Jacobian_SE(Ybus, Yf, Yt, V, F, T, Cf, Ct, se_input, no_slack, load_per_bus, fixed_slack)
        # measurements error (in per-unit)
        dz = z - h

        Gx = (H.T @ R_inv) @ H
        gx = (H.T @ R_inv) @ dz

        # Solve the increment
        dx = spsolve(Gx, gx)

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
        plt.show()

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
                                         elapsed=time.time() - start_time,
                                         bad_data_detected=bad_data_detected)
