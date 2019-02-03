# This file is a python port of the routines included in MATPOWER to perform continuation power flow.
# The license is the same BSD-style that is provided in LICENSE_MATPOWER

from numpy import angle, conj, exp, r_, linalg, Inf, dot, zeros
from scipy.sparse import hstack, vstack
from scipy.sparse.linalg import splu
from enum import Enum

from GridCal.Engine.Numerical.jacobian_based_power_flow import Jacobian


class VCStopAt(Enum):
    Nose = 'Nose'
    Full = 'Full curve'


def cpf_p(parametrization, step, z, V, lam, Vprv, lamprv, pv, pq, pvpq):
    """
    Computes the value of the CPF  function.
    Args:
        parametrization: Value of  option (1: Natural, 2:Arc-length, 3: pseudo arc-length)
        step: continuation step size
        z: normalized tangent prediction vector from previous step
        V: complex bus voltage vector at current solution
        lam: scalar lambda value at current solution
        Vprv: complex bus voltage vector at previous solution
        lamprv: scalar lambda value at previous solution
        pv: vector of indices of PV buses
        pq: vector of indices of PQ buses
        pvpq: vector of indices of PQ and PV buses

    Returns:
        value of the parametrization function at the current point
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
    if parametrization == 1:        # natural
        if lam >= lamprv:
            P = lam - lamprv - step
        else:
            P = lamprv - lam - step

    elif parametrization == 2:    # arc length
        Va = angle(V)
        Vm = abs(V)
        Vaprv = angle(Vprv)
        Vmprv = abs(Vprv)
        a = r_[Va[pvpq], Vm[pq], lam]
        b = r_[Vaprv[pvpq], Vmprv[pq], lamprv]
        P = sum((a - b)**2) - step**2

    elif parametrization == 3:    # pseudo arc length
        nb = len(V)
        Va = angle(V)
        Vm = abs(V)
        Vaprv = angle(Vprv)
        Vmprv = abs(Vprv)
        a = z[r_[pv, pq, nb+pq, 2*nb+1]]
        b = r_[Va[pvpq], Vm[pq], lam]
        c = r_[Vaprv[pvpq], Vmprv[pq], lamprv]
        P = dot(a, b - c) - step

    return P


def cpf_p_jac(parametrization, z, V, lam, Vprv, lamprv, pv, pq, pvpq):
    """
    Computes partial derivatives of CPF parametrization function.
    Args:
        parametrization:
        z: normalized tangent prediction vector from previous step
        V: complex bus voltage vector at current solution
        lam: scalar lambda value at current solution
        Vprv: complex bus voltage vector at previous solution
        lamprv: scalar lambda value at previous solution
        pv: vector of indices of PV buses
        pq: vector of indices of PQ buses
        pvpq: vector of indices of PQ and PV buses

    Returns:
        DP_DV : partial of parametrization function w.r.t. voltages
        DP_DLAM : partial of parametrization function w.r.t. lambda
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
    if parametrization == 1:   # natural
        npv = len(pv)
        npq = len(pq)
        dP_dV = zeros(npv + 2 * npq)
        if lam >= lamprv:
            dP_dlam = 1.0
        else:
            dP_dlam = -1.0

    elif parametrization == 2:  # arc length
        Va = angle(V)
        Vm = abs(V)
        Vaprv = angle(Vprv)
        Vmprv = abs(Vprv)
        dP_dV = 2 * (r_[Va[pvpq], Vm[pq]] - r_[Vaprv[pvpq], Vmprv[pq]])
        if lam == lamprv:   # first step
            dP_dlam = 1.0   # avoid singular Jacobian that would result from [dP_dV, dP_dlam] = 0
        else:
            dP_dlam = 2 * (lam - lamprv)

    elif parametrization == 3:  # pseudo arc length
        nb = len(V)
        dP_dV = z[r_[pv, pq, nb + pq]]
        dP_dlam = z[2 * nb + 1][0]

    return dP_dV, dP_dlam


def cpf_corrector(Ybus, Ibus, Sbus, V0, pv, pq, lam0, Sxfr, Vprv, lamprv, z, step, parametrization, tol, max_it, verbose):
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

     The extra continuation inputs are LAM0 (initial predicted lambda),
     SXFR ([delP+j*delQ] transfer/loading vector for all buses), VPRV
     (final complex V corrector solution from previous continuation step),
     LAMPRV (final lambda corrector solution from previous continuation step),
     Z (normalized predictor for all buses), and STEP (continuation step size).
     The extra continuation output is LAM (final corrector lambda).

    Args:
        Ybus:
        Ibus:
        Sbus:
        V0:
        pv:
        pq:
        lam0:
        Sxfr:
        Vprv:
        lamprv:
        z:
        step:
        parametrization:
        tol:
        max_it:
        verbose:

    Returns:

    """
    """
    # CPF_CORRECTOR  Solves the corrector step of a continuation power flow using a
    #   full Newton method with selected parametrization scheme.
    #   [V, CONVERGED, I, LAM] = CPF_CORRECTOR(YBUS, SBUS, V0, REF, PV, PQ, ...
    #                 LAM0, SXFR, VPRV, LPRV, Z, STEP, parametrization, MPOPT)
    #   solves for bus voltages and lambda given the full system admittance
    #   matrix (for all buses), the complex bus power injection vector (for
    #   all buses), the initial vector of complex bus voltages, and column
    #   vectors with the lists of bus indices for the swing bus, PV buses, and
    #   PQ buses, respectively. The bus voltage vector contains the set point
    #   for generator (including ref bus) buses, and the reference angle of the
    #   swing bus, as well as an initial guess for remaining magnitudes and
    #   angles. MPOPT is a MATPOWER options struct which can be used to
    #   set the termination tolerance, maximum number of iterations, and
    #   output options (see MPOPTION for details). Uses default options if
    #   this parameter is not given. Returns the final complex voltages, a
    #   flag which indicates whether it converged or not, the number
    #   of iterations performed, and the final lambda.
    #
    #   The extra continuation inputs are LAM0 (initial predicted lambda),
    #   SXFR ([delP+j*delQ] transfer/loading vector for all buses), VPRV
    #   (final complex V corrector solution from previous continuation step),
    #   LAMPRV (final lambda corrector solution from previous continuation step),
    #   Z (normalized predictor for all buses), and STEP (continuation step size).
    #   The extra continuation output is LAM (final corrector lambda).
    #
    #   See also RUNCPF.
    
    #   MATPOWER
    #   Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
    #   by Ray Zimmerman, PSERC Cornell,
    #   Shrirang Abhyankar, Argonne National Laboratory,
    #   and Alexander Flueck, IIT
    #
    #   Modified by Alexander J. Flueck, Illinois Institute of Technology
    #   2001.02.22 - corrector.m (ver 1.0) based on newtonpf.m (MATPOWER 2.0)
    #
    #   Modified by Shrirang Abhyankar, Argonne National Laboratory
    #   (Updated to be compatible with MATPOWER version 4.1)
    #
    #   $Id: cpf_corrector.m 2644 2015-03-11 19:34:22Z ray $
    #
    #   This file is part of MATPOWER.
    #   Covered by the 3-clause BSD License (see LICENSE file for details).
    #   See http://www.pserc.cornell.edu/matpower/ for more info.
    """

    # initialize
    converged = 0
    i = 0
    V = V0
    Va = angle(V)
    Vm = abs(V)
    lam = lam0             # set lam to initial lam0
    
    # set up indexing for updating V
    npv = len(pv)
    npq = len(pq)
    pvpq = r_[pv, pq]
    nj = npv+npq*2
    nb = len(V)         # number of buses
    j1 = 1

    '''
    # MATLAB code
    j2 = npv           # j1:j2 - V angle of pv buses
    j3 = j2 + 1
    j4 = j2 + npq      # j3:j4 - V angle of pq buses
    j5 = j4 + 1
    j6 = j4 + npq      # j5:j6 - V mag of pq buses
    j7 = j6 + 1
    j8 = j6 + 1        # j7:j8 - lambda
    '''

    # j1:j2 - V angle of pv buses
    j1 = 0
    j2 = npv
    # j3:j4 - V angle of pq buses
    j3 = j2
    j4 = j2 + npq
    # j5:j6 - V mag of pq buses
    j5 = j4
    j6 = j4 + npq
    j7 = j6
    j8 = j6+1
    
    # evaluate F(x0, lam0), including Sxfr transfer/loading
    mis = V * conj(Ybus * V) - Sbus - lam * Sxfr
    F = r_[mis[pvpq].real,
           mis[pq].imag]
    
    # evaluate P(x0, lambda0)
    P = cpf_p(parametrization, step, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
    # augment F(x,lambda) with P(x,lambda)
    F = r_[F, P]
    
    # check tolerance
    normF = linalg.norm(F, Inf)
    # if verbose > 1:
    #     sys.stdout.write('\n it    max P & Q mismatch (p.u.)')
    #     sys.stdout.write('\n----  ---------------------------')
    #     sys.stdout.write('\n#3d        #10.3e' (i, normF))

    if normF < tol:
        converged = True
        if verbose:
            print('\nConverged!\n')

    # do Newton iterations
    while not converged and i < max_it:
        # update iteration counter
        i += 1
        
        # evaluate Jacobian
        J = Jacobian(Ybus, V, Ibus, pq, pvpq)
    
        dF_dlam = -r_[Sxfr[pvpq].real, Sxfr[pq].imag]
        dP_dV, dP_dlam = cpf_p_jac(parametrization, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
        # augment J with real/imag -Sxfr and z^T
        '''
        J = [   J   dF_dlam 
              dP_dV dP_dlam ]
        '''
        J = vstack([
            hstack([J, dF_dlam.reshape(nj, 1)]),
            hstack([dP_dV, dP_dlam])
            ], format="csc")
    
        # compute update step
        dx = -splu(J).solve(F)   #-np.linalg.solve(J, F)
    
        # update voltage
        if npv:
            Va[pv] += dx[j1:j2]

        if npq:
            Va[pq] += dx[j3:j4]
            Vm[pq] += dx[j5:j6]

        V = Vm * exp(1j * Va)
        Vm = abs(V)            # update Vm and Va again in case
        Va = angle(V)          # we wrapped around with a negative Vm
    
        # update lambda
        lam += dx[j7:j8][0]
    
        # evaluate F(x, lam)
        mis = V * conj(Ybus * V) - Sbus - lam*Sxfr
        F = r_[mis[pv].real,
               mis[pq].real,
               mis[pq].imag]
    
        # evaluate P(x, lambda)
        # , step, z, V, lam, Vprv, lamprv, pv, pq, pvpq
        P = cpf_p(parametrization, step, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
        # augment F(x,lambda) with P(x,lambda)
        F = r_[F, P]
    
        # check for convergence
        normF = linalg.norm(F, Inf)
        
        if verbose > 1:
            print('\n#3d        #10.3e', i, normF)
        
        if normF < tol:
            converged = 1
            if verbose:
                print('\nNewton''s method corrector converged in ', i, ' iterations.\n')

    if verbose:
        if not converged:
            print('\nNewton method corrector did not converge in  ', i, ' iterations.\n')

    return V, converged, i, lam, normF


def cpf_predictor(V, Ibus, lam, Ybus, Sxfr, pv, pq, step, z, Vprv, lamprv, parametrization):
    """
    %CPF_PREDICTOR  Performs the predictor step for the continuation power flow
    %   [V0, LAM0, Z] = CPF_PREDICTOR(VPRV, LAMPRV, YBUS, SXFR, PV, PQ, STEP, Z)
    %
    %   Computes a prediction (approximation) to the next solution of the
    %   continuation power flow using a normalized tangent predictor.
    %
    %   Inputs:
    %       V : complex bus voltage vector at current solution
    %       LAM : scalar lambda value at current solution
    %       YBUS : complex bus admittance matrix
    %       SXFR : complex vector of scheduled transfers (difference between
    %              bus injections in base and target cases)
    %       PV : vector of indices of PV buses
    %       PQ : vector of indices of PQ buses
    %       STEP : continuation step length
    %       Z : normalized tangent prediction vector from previous step
    %       VPRV : complex bus voltage vector at previous solution
    %       LAMPRV : scalar lambda value at previous solution
    %       parametrization : Value of cpf.parametrization option.
    %
    %   Outputs:
    %       V0 : predicted complex bus voltage vector
    %       LAM0 : predicted lambda continuation parameter
    %       Z : the normalized tangent prediction vector
    
    %   MATPOWER
    %   Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
    %   by Shrirang Abhyankar, Argonne National Laboratory
    %   and Ray Zimmerman, PSERC Cornell
    %
    %   $Id: cpf_predictor.m 2644 2015-03-11 19:34:22Z ray $
    %
    %   This file is part of MATPOWER.
    %   Covered by the 3-clause BSD License (see LICENSE file for details).
    %   See http://www.pserc.cornell.edu/matpower/ for more info.
    """
    # sizes
    nb = len(V)
    npv = len(pv)
    npq = len(pq)
    pvpq = r_[pv, pq]
    nj = npv+npq*2
    # compute Jacobian for the power flow equations
    J = Jacobian(Ybus, V, Ibus, pq, pvpq)
    
    dF_dlam = -r_[Sxfr[pvpq].real, Sxfr[pq].imag]
    dP_dV, dP_dlam = cpf_p_jac(parametrization, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
    # linear operator for computing the tangent predictor
    '''
        J = [   J   dF_dlam
              dP_dV dP_dlam ]
    '''
    J = vstack([
        hstack([J, dF_dlam.reshape(nj, 1)]),
        hstack([dP_dV, dP_dlam])
        ], format="csc")

    Vaprv = angle(V)
    Vmprv = abs(V)
    
    # compute normalized tangent predictor
    s = zeros(npv + 2 * npq + 1)
    s[npv + 2 * npq] = 1                    # increase in the direction of lambda
    z[r_[pvpq, nb+pq, 2*nb]] = splu(J).solve(s)  # spsolve(J, s)  # tangent vector
    z /= linalg.norm(z)                         # normalize_string tangent predictor  (dividing by the euclidean norm)
    
    Va0 = Vaprv
    Vm0 = Vmprv
    lam0 = lam
    
    # prediction for next step
    Va0[pvpq] = Vaprv[pvpq] + step * z[pvpq]
    Vm0[pq] = Vmprv[pq] + step * z[nb+pq]
    lam0 = lam + step * z[2*nb]
    V0 = Vm0 * exp(1j * Va0)
        
    return V0, lam0, z


def continuation_nr(Ybus, Ibus_base, Ibus_target, Sbus_base, Sbus_target, V, pv, pq, step, approximation_order,
                    adapt_step, step_min, step_max, error_tol=1e-3, tol=1e-6, max_it=20,
                    stop_at=VCStopAt.Nose, verbose=False, call_back_fx=None):
    """
    Runs a full AC continuation power flow using a normalized tangent
    predictor and selected approximation_order scheme.
    :param Ybus: Admittance matrix
    :param Ibus_base:
    :param Ibus_target:
    :param Sbus_base: Power array of the base solvable case
    :param Sbus_target: Power array of the case to be solved
    :param V: Voltage array of the base solved case
    :param pv: Array of pv indices
    :param pq: Array of pq indices
    :param step: Adaptation step
    :param approximation_order: order of the approximation {1, 2, 3}
    :param adapt_step: use adaptive step size?
    :param step_min: minimum step size
    :param step_max: maximum step size
    :param error_tol: Error tolerance
    :param tol: Solutions tolerance
    :param max_it: Maximum iterations
    :param stop_at:  Value of Lambda to stop at. It can be a number or {'NOSE', 'FULL'}
    :param verbose: Display additional intermediate information?
    :param call_back_fx: Function to call on every iteration passing the lambda parameter
    :return: Voltage_series: List of all the voltage solutions from the base to the target
             Lambda_series: Lambda values used in the continuation


    Ported from MATPOWER
        Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
        by Ray Zimmerman, PSERC Cornell,
        Shrirang Abhyankar, Argonne National Laboratory,
        and Alexander Flueck, IIT

        $Id: runcpf.m 2644 2015-03-11 19:34:22Z ray $

        This file is part of MATPOWER.
        Covered by the 3-clause BSD License (see LICENSE file for details).
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
    continuation = 1
    cont_steps = 0
    pvpq = r_[pv, pq]

    z = zeros(2 * nb + 1)
    z[2 * nb] = 1.0

    # result arrays
    voltage_series = list()
    lambda_series = list()

    # Simulation
    while continuation:
        cont_steps += 1

        # prediction for next step
        V0, lam0, z = cpf_predictor(V, Ibus_base, lam, Ybus, Sxfr, pv, pq, step, z, V_prev, lam_prev, approximation_order)

        # save previous voltage, lambda before updating
        V_prev = V.copy()
        lam_prev = lam

        # correction
        # Ybus, Sbus, V0, ref, pv, pq, lam0, Sxfr, Vprv, lamprv, z, step, parametrization, tol, max_it, verbose
        V, success, i, lam, normF = cpf_corrector(Ybus, Ibus_base,  Sbus_base, V0, pv, pq, lam0, Sxfr, V_prev,
                                                  lam_prev, z, step, approximation_order, tol, max_it, verbose)
        if not success:
            continuation = 0
            print('step ', cont_steps, ' : lambda = ', lam, ', corrector did not converge in ', i, ' iterations\n')
            break

        if verbose:
            print('Step: ', cont_steps, ' Lambda prev: ', lam_prev, ' Lambda: ', lam)
            print(V)
        voltage_series.append(V)
        lambda_series.append(lam)

        if verbose > 2:
            print('step ', cont_steps, ' : lambda = ', lam)
        elif verbose > 1:
            print('step ', cont_steps, ': lambda = ', lam, ', ', i, ' corrector Newton steps\n')

        if stop_at == VCStopAt.Full:
            if abs(lam) < 1e-8:  # traced the full continuation curve
                if verbose:
                    print('\nTraced full continuation curve in ', cont_steps, ' continuation steps\n')
                continuation = 0

            elif (lam < lam_prev) and (lam - step < 0):   # next step will overshoot
                step = lam             # modify step-size
                approximation_order = 1   # change to natural parametrization
                adapt_step = 0         # disable step-adaptivity

        elif stop_at == VCStopAt.Nose:
            if lam < lam_prev:                        # reached the nose point
                if verbose:
                    print('\nReached steady state loading limit in ', cont_steps, ' continuation steps\n')
                continuation = 0
        else:
            raise Exception('Stop point ' + stop_at + ' not recognised.')

        if adapt_step and continuation:
            # Adapt step size
            cpf_error = linalg.norm(r_[angle(V[pq]), abs(V[pvpq]), lam] - r_[angle(V0[pq]), abs(V0[pvpq]), lam0], Inf)

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

    return voltage_series, lambda_series, normF, success
