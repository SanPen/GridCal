# This file is a python port of the routines included in MATPOWER to perform continuation power flow.
# The license is the same BSD-style that is provided in LICENSE_MATPOWER

import numpy as np
from scipy.sparse import hstack, vstack
from scipy.sparse.linalg import spsolve
from enum import Enum
from GridCal.Engine.basic_structures import ReactivePowerControlMode, Logger
from GridCal.Engine.Simulations.PowerFlow.discrete_controls import control_q_direct
from GridCal.Engine.Core.common_functions import compile_types
from GridCal.Engine.Simulations.PowerFlow.high_speed_jacobian import AC_jacobian


class CpfStopAt(Enum):
    Nose = 'Nose'
    ExtraOverloads = 'Extra overloads'
    Full = 'Full curve'


class CpfParametrization(Enum):
    Natural = 'Natural'
    ArcLength = 'Arc Length'
    PseudoArcLength = 'Pseudo Arc Length'


class CpfNumericResults:

    def __init__(self):
        self.V = list()
        self.Sbus = list()
        self.lmbda = list()
        self.Sf = list()
        self.St = list()
        self.loading = list()
        self.losses = list()
        self.normF = list()
        self.success = list()

    def add(self, v, sbus, Sf, St, lam, losses, loading, normf, converged):
        self.V.append(v)
        self.Sbus.append(sbus)
        self.lmbda.append(lam)
        self.Sf.append(Sf)
        self.St.append(St)
        self.loading.append(loading)
        self.losses.append(losses)
        self.normF.append(normf)
        self.success.append(converged)

    def __len__(self):
        return len(self.V)


def cpf_p(parametrization: CpfParametrization, step, z, V, lam, V_prev, lamprv, pv, pq, pvpq):
    """
    Computes the value of the Current Parametrization Function
    :param parametrization: Value of  option (1: Natural, 2:Arc-length, 3: pseudo arc-length)
    :param step: continuation step size
    :param z: normalized tangent prediction vector from previous step
    :param V: complex bus voltage vector at current solution
    :param lam: scalar lambda value at current solution
    :param V_prev: complex bus voltage vector at previous solution
    :param lamprv: scalar lambda value at previous solution
    :param pv: vector of indices of PV buses
    :param pq: vector of indices of PQ buses
    :param pvpq: vector of indices of PQ and PV buses
    :return: value of the parametrization function at the current point
    """

    """
    #CPF_P Computes the value of the CPF parametrization function.
    #
    #   P = CPF_P(parametrization, STEP, Z, V, LAM, VPRV, LAMPRV, PV, PQ)
    #
    #   Computes the value of the parametrization function at the current
    #   solution point.
    #
    #   Inputs:
    #       parametrization : Value of cpf.parametrization option
    #       STEP : continuation step size
    #       Z : normalized tangent prediction vector from previous step
    #       V : complex bus voltage vector at current solution
    #       LAM : scalar lambda value at current solution
    #       VPRV : complex bus voltage vector at previous solution
    #       LAMPRV : scalar lambda value at previous solution
    #       PV : vector of indices of PV buses
    #       PQ : vector of indices of PQ buses
    #
    #   Outputs:
    #       P : value of the parametrization function at the current point
    #
    #   See also CPF_PREDICTOR, CPF_CORRECTOR.

    #   MATPOWER
    #   Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
    #   by Shrirang Abhyankar, Argonne National Laboratory
    #   and Ray Zimmerman, PSERC Cornell
    #
    #   $Id: cpf_p.m 2644 2015-03-11 19:34:22Z ray $
    #
    #   This file is part of MATPOWER.
    #   Covered by the 3-clause BSD License (see LICENSE file for details).
    #   See http://www.pserc.cornell.edu/matpower/ for more info.

    ## evaluate P(x0, lambda0)
    """
    if parametrization == CpfParametrization.Natural:        # natural
        if lam >= lamprv:
            P = lam - lamprv - step
        else:
            P = lamprv - lam - step

    elif parametrization == CpfParametrization.ArcLength:    # arc length
        Va = np.angle(V)
        Vm = np.abs(V)
        Va_prev = np.angle(V_prev)
        Vm_prev = np.abs(V_prev)
        a = np.r_[Va[pvpq], Vm[pq], lam]
        b = np.r_[Va_prev[pvpq], Vm_prev[pq], lamprv]
        P = np.sum(np.power(a - b, 2)) - np.power(step, 2)

    elif parametrization == CpfParametrization.PseudoArcLength:    # pseudo arc length
        nb = len(V)
        Va = np.angle(V)
        Vm = np.abs(V)
        Va_prev = np.angle(V_prev)
        Vm_prev = np.abs(V_prev)
        a = z[np.r_[pv, pq, nb + pq, 2 * nb]]
        b = np.r_[Va[pvpq], Vm[pq], lam]
        c = np.r_[Va_prev[pvpq], Vm_prev[pq], lamprv]
        P = np.dot(a, b - c) - step
    else:
        # natural
        if lam >= lamprv:
            P = lam - lamprv - step
        else:
            P = lamprv - lam - step

    return P


def cpf_p_jac(parametrization: CpfParametrization, z, V, lam, Vprv, lamprv, pv, pq, pvpq):
    """
    Computes partial derivatives of Current Parametrization Function (CPF).
    :param parametrization:
    :param z: normalized tangent prediction vector from previous step
    :param V: complex bus voltage vector at current solution
    :param lam: scalar lambda value at current solution
    :param Vprv: complex bus voltage vector at previous solution
    :param lamprv: scalar lambda value at previous solution
    :param pv: vector of indices of PV buses
    :param pq: vector of indices of PQ buses
    :param pvpq: vector of indices of PQ and PV buses
    :return:  partial of parametrization function w.r.t. voltages
              partial of parametrization function w.r.t. lambda
    """

    """
    #CPF_P_JAC Computes partial derivatives of CPF parametrization function.
    #
    #   [DP_DV, DP_DLAM ] = CPF_P_JAC(parametrization, Z, V, LAM, ...
    #                                                   VPRV, LAMPRV, PV, PQ)
    #
    #   Computes the partial derivatives of the continuation power flow
    #   parametrization function w.r.t. bus voltages and the continuation
    #   parameter lambda.
    #
    #   Inputs:
    #       parametrization : Value of cpf.parametrization option.
    #       Z : normalized tangent prediction vector from previous step
    #       V : complex bus voltage vector at current solution
    #       LAM : scalar lambda value at current solution
    #       VPRV : complex bus voltage vector at previous solution
    #       LAMPRV : scalar lambda value at previous solution
    #       PV : vector of indices of PV buses
    #       PQ : vector of indices of PQ buses
    #
    #   Outputs:
    #       DP_DV : partial of parametrization function w.r.t. voltages
    #       DP_DLAM : partial of parametrization function w.r.t. lambda
    #
    #   See also CPF_PREDICTOR, CPF_CORRECTOR.

    #   MATPOWER
    #   Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
    #   by Shrirang Abhyankar, Argonne National Laboratory
    #   and Ray Zimmerman, PSERC Cornell
    #
    #   $Id: cpf_p_jac.m 2644 2015-03-11 19:34:22Z ray $
    #
    #   This file is part of MATPOWER.
    #   Covered by the 3-clause BSD License (see LICENSE file for details).
    #   See http://www.pserc.cornell.edu/matpower/ for more info.
    """

    if parametrization == CpfParametrization.Natural:   # natural
        npv = len(pv)
        npq = len(pq)
        dP_dV = np.zeros(npv + 2 * npq)
        if lam >= lamprv:
            dP_dlam = 1.0
        else:
            dP_dlam = -1.0

    elif parametrization == CpfParametrization.ArcLength:  # arc length
        Va = np.angle(V)
        Vm = np.abs(V)
        Vaprv = np.angle(Vprv)
        Vmprv = np.abs(Vprv)
        dP_dV = 2.0 * (np.r_[Va[pvpq], Vm[pq]] - np.r_[Vaprv[pvpq], Vmprv[pq]])

        if lam == lamprv:   # first step
            dP_dlam = 1.0   # avoid singular Jacobian that would result from [dP_dV, dP_dlam] = 0
        else:
            dP_dlam = 2.0 * (lam - lamprv)

    elif parametrization == CpfParametrization.PseudoArcLength:  # pseudo arc length
        nb = len(V)
        dP_dV = z[np.r_[pv, pq, nb + pq]]
        dP_dlam = z[2 * nb]

    else:
        # pseudo arc length for any other case
        nb = len(V)
        dP_dV = z[np.r_[pv, pq, nb + pq]]
        dP_dlam = z[2 * nb]

    return dP_dV, dP_dlam


def predictor(V, Ibus, lam, Ybus, Sxfr, pv, pq, step, z, Vprv, lamprv,
              parametrization: CpfParametrization, pvpq_lookup):
    """
    Computes a prediction (approximation) to the next solution of the
    continuation power flow using a normalized tangent predictor.
    :param V: complex bus voltage vector at current solution
    :param Ibus:
    :param lam: scalar lambda value at current solution
    :param Ybus: complex bus admittance matrix
    :param Sxfr: complex vector of scheduled transfers (difference between bus injections in base and target cases)
    :param pv: vector of indices of PV buses
    :param pq: vector of indices of PQ buses
    :param step: continuation step length
    :param z: normalized tangent prediction vector from previous step
    :param Vprv: complex bus voltage vector at previous solution
    :param lamprv: scalar lambda value at previous solution
    :param parametrization: Value of cpf parametrization option.
    :return: V0 : predicted complex bus voltage vector
             LAM0 : predicted lambda continuation parameter
             Z : the normalized tangent prediction vector
    """

    # sizes
    nb = len(V)
    npv = len(pv)
    npq = len(pq)
    pvpq = np.r_[pv, pq]
    nj = npv + npq * 2

    # compute Jacobian for the power flow equations
    J = AC_jacobian(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq)

    dF_dlam = -np.r_[Sxfr[pvpq].real, Sxfr[pq].imag]

    dP_dV, dP_dlam = cpf_p_jac(parametrization, z, V, lam, Vprv, lamprv, pv, pq, pvpq)

    # linear operator for computing the tangent predictor
    '''
    J2 = [   J   dF_dlam
           dP_dV dP_dlam ]
    '''
    J2 = vstack([hstack([J, dF_dlam.reshape(nj, 1)]),
                 hstack([dP_dV, dP_dlam])], format="csc")

    Va_prev = np.angle(V)
    Vm_prev = np.abs(V)

    # compute normalized tangent predictor
    s = np.zeros(npv + 2 * npq + 1)

    # increase in the direction of lambda
    s[npv + 2 * npq] = 1

    # tangent vector
    z[np.r_[pvpq, nb + pq, 2 * nb]] = spsolve(J2, s)

    # normalize_string tangent predictor  (dividing by the euclidean norm)
    z /= np.linalg.norm(z)

    Va0 = Va_prev
    Vm0 = Vm_prev
    # lam0 = lam

    # prediction for next step
    Va0[pvpq] = Va_prev[pvpq] + step * z[pvpq]
    Vm0[pq] = Vm_prev[pq] + step * z[pq + nb]
    lam0 = lam + step * z[2 * nb]
    V0 = Vm0 * np.exp(1j * Va0)

    return V0, lam0, z


def corrector(Ybus, Ibus, Sbus, V0, pv, pq, lam0, Sxfr, Vprv, lamprv, z, step, parametrization, tol, max_it,
              pvpq_lookup, verbose, mu_0=1.0, acceleration_parameter=0.5):
    """
    Solves the corrector step of a continuation power flow using a full Newton method
    with selected parametrization scheme.

    solves for bus voltages and lambda given the full system admittance
    matrix (for all buses), the complex bus power injection vector (for
    all buses), the initial vector of complex bus voltages, and column
    vectors with the lists of bus indices for the swing bus, PV buses, and
    PQ buses, respectively. The bus voltage vector contains the set point
    for generator (including ref bus) buses, and the reference angle of the
    swing bus, as well as an initial guess for remaining magnitudes and
    angles.

     Uses default options if this parameter is not given. Returns the
     final complex voltages, a flag which indicates whether it converged or not,
     the number of iterations performed, and the final lambda.

    :param Ybus: Admittance matrix (CSC sparse)
    :param Ibus: Bus current injections
    :param Sbus: Bus power injections
    :param V0:  Bus initial voltages
    :param pv: list of pv nodes
    :param pq: list of pq nodes
    :param lam0: initial value of lambda (loading parameter)
    :param Sxfr: [delP+j*delQ] transfer/loading vector for all buses
    :param Vprv: final complex V corrector solution from previous continuation step
    :param lamprv: final lambda corrector solution from previous continuation step
    :param z: normalized predictor for all buses
    :param step: continuation step size
    :param parametrization:
    :param tol: Tolerance (p.u.)
    :param max_it: max iterations
    :param verbose: print information?
    :return: Voltage, converged, iterations, lambda, power error, calculated power
    """

    # initialize
    i = 0
    V = V0
    Va = np.angle(V)
    Vm = np.abs(V)
    lam = lam0             # set lam to initial lam0
    dVa = np.zeros_like(Va)
    dVm = np.zeros_like(Vm)
    dlam = 0

    # set up indexing for updating V
    npv = len(pv)
    npq = len(pq)
    pvpq = np.r_[pv, pq]
    nj = npv + npq * 2

    # j1:j2 - V angle of pv and pq buses
    j1 = 0
    j2 = npv + npq
    # j2:j3 - V mag of pq buses
    j3 = j2 + npq

    # evaluate F(x0, lam0), including Sxfr transfer/loading
    Scalc = V * np.conj(Ybus * V)
    mismatch = Scalc - Sbus - lam * Sxfr
    # F = np.r_[mismatch[pvpq].real, mismatch[pq].imag]
    
    # evaluate P(x0, lambda0)
    P = cpf_p(parametrization, step, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
    # augment F(x,lambda) with P(x,lambda)
    F = np.r_[mismatch[pvpq].real, mismatch[pq].imag, P]
    
    # check tolerance
    normF = np.linalg.norm(F, np.Inf)
    converged = normF < tol
    if verbose:
        print('\nConverged!\n')

    dF_dlam = -np.r_[Sxfr[pvpq].real, Sxfr[pq].imag]

    # do Newton iterations
    while not converged and i < max_it:

        # update iteration counter
        i += 1
        
        # evaluate Jacobian
        J = AC_jacobian(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq)

        dP_dV, dP_dlam = cpf_p_jac(parametrization, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
        # augment J with real/imag - Sxfr and z^T
        '''
        J = [   J   dF_dlam 
              dP_dV dP_dlam ]
        '''
        J = vstack([hstack([J, dF_dlam.reshape(nj, 1)]),
                    hstack([dP_dV, dP_dlam])], format="csc")
    
        # compute update step
        dx = spsolve(J, F)
        dVa[pvpq] = dx[j1:j2]
        dVm[pq] = dx[j2:j3]
        dlam = dx[j3]

        # set the restoration values
        prev_Vm = Vm.copy()
        prev_Va = Va.copy()
        prev_lam = lam

        # set the values and correct with an adaptive mu if needed
        mu = mu_0  # ideally 1.0
        back_track_condition = True
        l_iter = 0
        normF_new = 0.0
        while back_track_condition and l_iter < max_it and mu > tol:

            # restore the previous values if we are backtracking (the first iteration is the normal NR procedure)
            if l_iter > 0:
                Va = prev_Va.copy()
                Vm = prev_Vm.copy()
                lam = prev_lam
    
            # update the variables from the solution
            Va -= mu * dVa
            Vm -= mu * dVm
            lam -= mu * dlam

            # update Vm and Va again in case we wrapped around with a negative Vm
            V = Vm * np.exp(1j * Va)

            # evaluate F(x, lam)
            Scalc = V * np.conj(Ybus * V)
            mismatch = Scalc - Sbus - lam * Sxfr

            # evaluate the parametrization function P(x, lambda)
            P = cpf_p(parametrization, step, z, V, lam, Vprv, lamprv, pv, pq, pvpq)

            # compose the mismatch vector
            F = np.r_[mismatch[pvpq].real, mismatch[pq].imag, P]

            # check for convergence
            normF_new = np.linalg.norm(F, np.Inf)

            back_track_condition = normF_new > normF
            mu *= acceleration_parameter
            l_iter += 1

            if verbose:
                print('\n#3d        #10.3e', i, normF)

        if l_iter > 1 and back_track_condition:
            # this means that not even the backtracking was able to correct the solution so, restore and end
            Va = prev_Va.copy()
            Vm = prev_Vm.copy()
            V = Vm * np.exp(1.0j * Va)

            return V, converged, i, lam, normF, Scalc
        else:
            normF = normF_new

        converged = normF < tol
        if verbose:
            print('\nNewton''s method corrector converged in ', i, ' iterations.\n')

    if verbose:
        if not converged:
            print('\nNewton method corrector did not converge in  ', i, ' iterations.\n')

    return V, converged, i, lam, normF, Scalc


def continuation_nr(Ybus, Cf, Ct, Yf, Yt, branch_rates, Sbase, Ibus_base, Ibus_target, Sbus_base, Sbus_target,
                    V, distributed_slack, bus_installed_power,
                    vd, pv, pq, step, approximation_order: CpfParametrization,
                    adapt_step, step_min, step_max, error_tol=1e-3, tol=1e-6, max_it=20,
                    stop_at=CpfStopAt.Nose, control_q=ReactivePowerControlMode.NoControl,
                    qmax_bus=None, qmin_bus=None, original_bus_types=None, base_overload_number=0,
                    verbose=False, call_back_fx=None, logger=Logger()) -> CpfNumericResults:
    """
    Runs a full AC continuation power flow using a normalized tangent
    predictor and selected approximation_order scheme.
    :param Ybus: Admittance matrix
    :param Cf: Connectivity matrix of the branches and the "from" nodes
    :param Ct: Connectivity matrix of the branches and the "to" nodes
    :param Yf: Admittance matrix of the "from" nodes
    :param Yt: Admittance matrix of the "to" nodes
    :param branch_rates: array of branch rates to check the overload condition
    :param Ibus_base:
    :param Ibus_target:
    :param Sbus_base: Power array of the base solvable case
    :param Sbus_target: Power array of the case to be solved
    :param V: Voltage array of the base solved case
    :param distributed_slack: Distribute the slack?
    :param bus_installed_power: array of installed power per bus
    :param vd: Array of slack bus indices
    :param pv: Array of pv bus indices
    :param pq: Array of pq bus indices
    :param step: Adaptation step
    :param approximation_order: order of the approximation {Natural, Arc, Pseudo arc}
    :param adapt_step: use adaptive step size?
    :param step_min: minimum step size
    :param step_max: maximum step size
    :param error_tol: Error tolerance
    :param tol: Solutions tolerance
    :param max_it: Maximum iterations
    :param stop_at:  Value of Lambda to stop at. It can be a number or {'NOSE', 'FULL'}
    :param control_q: Type of reactive power control
    :param qmax_bus: Array of maximum reactive power per node
    :param qmin_bus: Array of minimum reactive power per node
    :param original_bus_types: array of bus types
    :param base_overload_number: number of overloads in the base situation (used when stop_at=CpfStopAt.ExtraOverloads)
    :param verbose: Display additional intermediate information?
    :param call_back_fx: Function to call on every iteration passing the lambda parameter
    :param logger: Logger instance
    :return: CpfNumericResults instance


    Ported from MATPOWER
        Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
        by Ray Zimmerman, PSERC Cornell,
        Shrirang Abhyankar, Argonne National Laboratory, and Alexander Flueck, IIT

        $Id: runcpf.m 2644 2015-03-11 19:34:22Z ray $

        MATPOWER is covered by the 3-clause BSD License (see LICENSE file for details).
        See http://www.pserc.cornell.edu/matpower/ for more info.
    """

    ########################################
    # INITIALIZATION
    ########################################

    # scheduled transfer
    Sxfr = Sbus_target - Sbus_base
    nb = len(Sbus_base)
    lam = 0
    lam_prev = lam   # lam at previous step
    V_prev = V       # V at previous step
    continuation = True
    cont_steps = 0
    pvpq = np.r_[pv, pq]
    bus_types = original_bus_types.copy()

    z = np.zeros(2 * nb + 1)
    z[2 * nb] = 1.0

    # generate lookup pvpq -> index pvpq (used in createJ)
    pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
    pvpq_lookup[pvpq] = np.arange(len(pvpq))

    # compute total bus installed power
    total_installed_power = bus_installed_power.sum()

    # result arrays
    results = CpfNumericResults()

    # Simulation
    while continuation:
        cont_steps += 1

        # prediction for next step -------------------------------------------------------------------------------------
        V0, lam0, z = predictor(V=V,
                                Ibus=Ibus_base,
                                lam=lam,
                                Ybus=Ybus,
                                Sxfr=Sxfr,
                                pv=pv,
                                pq=pq,
                                step=step,
                                z=z,
                                Vprv=V_prev,
                                lamprv=lam_prev,
                                parametrization=approximation_order,
                                pvpq_lookup=pvpq_lookup)

        # save previous voltage, lambda before updating
        V_prev = V.copy()
        lam_prev = lam

        # correction ---------------------------------------------------------------------------------------------------
        V, success, i, lam, normF, Scalc = corrector(Ybus=Ybus,
                                                     Ibus=Ibus_base,
                                                     Sbus=Sbus_base,
                                                     V0=V0,
                                                     pv=pv,
                                                     pq=pq,
                                                     lam0=lam0,
                                                     Sxfr=Sxfr,
                                                     Vprv=V_prev,
                                                     lamprv=lam_prev,
                                                     z=z,
                                                     step=step,
                                                     parametrization=approximation_order,
                                                     tol=tol,
                                                     max_it=max_it,
                                                     pvpq_lookup=pvpq_lookup,
                                                     verbose=verbose)

        if distributed_slack:
            # Distribute the slack power
            slack_power = Scalc[vd].real.sum()

            if total_installed_power > 0.0:
                delta = slack_power * bus_installed_power / total_installed_power

                # rerun with the slack distributed and replace the results
                # also, initialize with the last voltage
                V, success, i, lam, normF, Scalc = corrector(Ybus=Ybus,
                                                             Ibus=Ibus_base,
                                                             Sbus=Sbus_base + delta,
                                                             V0=V,
                                                             pv=pv,
                                                             pq=pq,
                                                             lam0=lam0,
                                                             Sxfr=Sxfr,
                                                             Vprv=V_prev,
                                                             lamprv=lam_prev,
                                                             z=z,
                                                             step=step,
                                                             parametrization=approximation_order,
                                                             tol=tol,
                                                             max_it=max_it,
                                                             pvpq_lookup=pvpq_lookup,
                                                             verbose=verbose)

        if success:

            # branch values --------------------------------------------------------------------------------------------
            # Branches current, loading, etc
            Vf = Cf * V
            Vt = Ct * V
            If = Yf * V  # in p.u.
            It = Yt * V  # in p.u.
            Sf = Vf * np.conj(If) * Sbase  # in MVA
            St = Vt * np.conj(It) * Sbase  # in MVA

            # Branch losses in MVA
            losses = Sf + St

            # Branch loading in p.u.
            loading = Sf.real / (branch_rates + 1e-9)

            # store series values --------------------------------------------------------------------------------------

            results.add(V, Scalc, Sf, St, lam, losses, loading, normF, success)

            if verbose:
                print('Step: ', cont_steps, ' Lambda prev: ', lam_prev, ' Lambda: ', lam)
                print(V)

            # Check controls
            if control_q == ReactivePowerControlMode.Direct:
                Vm = np.abs(V)
                V, \
                Qnew, \
                types_new, \
                any_q_control_issue = control_q_direct(V=V,
                                                       Vm=Vm,
                                                       Vset=Vm,
                                                       Q=Scalc.imag,
                                                       Qmax=qmax_bus,
                                                       Qmin=qmin_bus,
                                                       types=bus_types,
                                                       original_types=original_bus_types,
                                                       verbose=verbose)
            else:
                # did not check Q limits
                any_q_control_issue = False
                types_new = bus_types
                Qnew = Scalc.imag

            # Check the actions of the Q-control
            if any_q_control_issue:
                bus_types = types_new
                Sbus = Scalc.real + 1j * Qnew

                Sxfr = Sbus_target - Sbus  # TODO: really?

                vd, pq, pv, pqpv = compile_types(Sbus, types_new, logger)
            else:
                if verbose:
                    print('Q controls Ok')

            if stop_at == CpfStopAt.Full:

                if abs(lam) < 1e-8:
                    # traced the full continuation curve
                    if verbose:
                        print('\nTraced full continuation curve in ', cont_steps, ' continuation steps\n')
                    continuation = False

                elif (lam < lam_prev) and (lam - step < 0):
                    # next step will overshoot

                    # modify step-size
                    step = lam

                    # change to natural parametrization
                    approximation_order = CpfParametrization.Natural

                    # disable step-adaptivity
                    adapt_step = 0

            elif stop_at == CpfStopAt.Nose:

                if lam < lam_prev:
                    # reached the nose point
                    if verbose:
                        print('\nReached steady state loading limit in ', cont_steps, ' continuation steps\n')
                    continuation = False

            elif stop_at == CpfStopAt.ExtraOverloads:
                    # look for overloads and determine if there are more overloads than in the base situation
                idx = np.where(np.abs(loading) > 1)[0]
                if len(idx) > base_overload_number:
                    continuation = False

            else:
                raise Exception('Stop point ' + stop_at.value + ' not recognised.')

            if adapt_step and continuation:

                # Adapt step size
                fx = np.r_[np.angle(V[pq]), np.abs(V[pvpq]), lam] - np.r_[np.angle(V0[pq]), np.abs(V0[pvpq]), lam0]
                cpf_error = np.linalg.norm(fx, np.Inf)

                if cpf_error == 0:
                    cpf_error = 1e-20

                if cpf_error < error_tol:
                    # Increase step size
                    step = step * error_tol / cpf_error
                    if step > step_max:
                        step = step_max

                else:
                    # Decrease step size
                    step = step * error_tol / cpf_error
                    if step < step_min:
                        step = step_min

            # call callback function
            if call_back_fx is not None:
                call_back_fx(lam)

        else:
            continuation = False
            if verbose:
                print('step ', cont_steps, ' : lambda = ', lam, ', corrector did not converge in ', i, ' iterations\n')

    return results


if __name__ == '__main__':

    from GridCal.Engine import *
    from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit

    fname = os.path.join('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids', 'IEEE_14.xlsx')
    # fname = os.path.join('..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'lynn5buspv.xlsx')

    print('Reading...')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR, verbose=False,
                                  initialize_with_existing_solution=False,
                                  multi_core=False, dispatch_storage=True,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  control_p=True)

    ####################################################################################################################
    # PowerFlowDriver
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlowDriver(main_circuit, pf_options)
    power_flow.run()

    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sf|:', abs(power_flow.results.Sf))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())

    ####################################################################################################################
    # Voltage collapse
    ####################################################################################################################
    vc_options = ContinuationPowerFlowOptions(step=0.001,
                                              approximation_order=CpfParametrization.ArcLength,
                                              adapt_step=True,
                                              step_min=0.00001,
                                              step_max=0.2,
                                              error_tol=1e-3,
                                              tol=1e-6,
                                              max_it=20,
                                              stop_at=CpfStopAt.Full,
                                              verbose=False)

    # just for this test
    numeric_circuit = compile_snapshot_circuit(main_circuit)
    numeric_inputs = numeric_circuit.split_into_islands(ignore_single_node_islands=pf_options.ignore_single_node_islands)
    Sbase_ = np.zeros(len(main_circuit.buses), dtype=complex)
    Vbase_ = np.zeros(len(main_circuit.buses), dtype=complex)
    for c in numeric_inputs:
        Sbase_[c.original_bus_idx] = c.Sbus
        Vbase_[c.original_bus_idx] = c.Vbus

    np.random.seed(42)
    unitary_vector = -1 + 2 * np.random.random(len(main_circuit.buses))

    # unitary_vector = random.random(len(grid.buses))
    vc_inputs = ContinuationPowerFlowInput(Sbase=Sbase_,
                                           Vbase=Vbase_,
                                           Starget=Sbase_ * 2,  # (1 + unitary_vector)
                                           )
    vc = ContinuationPowerFlowDriver(circuit=main_circuit, options=vc_options, inputs=vc_inputs, pf_options=pf_options)
    vc.run()
    df = vc.results.plot()

    print(df)

    plt.show()
