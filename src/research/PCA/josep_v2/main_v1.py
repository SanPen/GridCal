# Parametric analysis of power systems

# Packages
import numpy as np
from GridCal.Engine import *
import random
import math
import itertools
np.set_printoptions(precision=10)

random.seed(42)


# Created functions
def grid_solve(p_PQ, indx_Vbus):

    """
    Define GridCal grid, with varying parameters. Can there be more than one load per bus?

    :param p_PQ: list of parameters related to active and reactive power, in MVA
    :param indx_Vbus: index of the bus of interest
    :return: the absolute value of the voltages
    """

    grid = MultiCircuit()

    bus1 = Bus('Bus 1', vnom=20)
    bus1.is_slack = True
    grid.add_bus(bus1)
    gen1 = Generator('Slack Generator', voltage_module=1.0)
    grid.add_generator(bus1, gen1)

    bus2 = Bus('Bus 2', vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, Load('load 2', P=p_PQ[0], Q=p_PQ[1]))

    bus3 = Bus('Bus 3', vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, Load('load 3', P=p_PQ[2], Q=p_PQ[3]))

    bus4 = Bus('Bus 4', vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, Load('load 4', P=p_PQ[4], Q=p_PQ[5]))

    bus5 = Bus('Bus 5', vnom=20)
    grid.add_bus(bus5)
    grid.add_load(bus5, Load('load 5', P=p_PQ[6], Q=p_PQ[7]))

    grid.add_line(Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.0))
    grid.add_line(Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.0))
    grid.add_line(Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.0))
    grid.add_line(Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.0))
    grid.add_line(Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.0))
    grid.add_line(Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.0))
    grid.add_line(Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.0))

    options = PowerFlowOptions(SolverType.NR, verbose=False)
    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    return abs(power_flow.results.voltage[indx_Vbus])


def lynn5bus():


    grid = MultiCircuit()

    bus1 = Bus('Bus 1', vnom=20)
    bus1.is_slack = True
    grid.add_bus(bus1)
    gen1 = Generator('Slack Generator', voltage_module=1.0)
    grid.add_generator(bus1, gen1)

    bus2 = Bus('Bus 2', vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, Load('load 2', P=0, Q=0))

    bus3 = Bus('Bus 3', vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, Load('load 3', P=0, Q=0))

    bus4 = Bus('Bus 4', vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, Load('load 4', P=0, Q=0))

    bus5 = Bus('Bus 5', vnom=20)
    grid.add_bus(bus5)
    grid.add_load(bus5, Load('load 5', P=0, Q=0))

    grid.add_line(Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.0))
    grid.add_line(Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.0))
    grid.add_line(Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.0))
    grid.add_line(Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.0))
    grid.add_line(Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.0))
    grid.add_line(Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.0))
    grid.add_line(Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.0))

    return grid


def power_flow(grid, S):

    calculation_input = compile_snapshot_circuit(grid)

    options = PowerFlowOptions(SolverType.NR, verbose=False)

    res = single_island_pf(circuit=calculation_input,
                           Vbus=calculation_input.Vbus,
                           Sbus=S,
                           Ibus=calculation_input.Ibus,
                           pq=calculation_input.pq,
                           pv=calculation_input.pv,
                           vd=calculation_input.vd,
                           pqpv=calculation_input.pqpv,
                           branch_rates=calculation_input.Rates,
                           options=options,
                           logger=Logger())

    return res.voltage


def samples_calc(M, n_param, indx_Vbus, param_lower_bnd, param_upper_bnd):

    """
    Calculate the gradients, build the hx vector, the covariance C matrix and store the parameters

    :param M: number of samples
    :param n_param: number of parameters
    :param indx_Vbus: index of the bus of interest
    :param param_lower_bnd: array of lower bounds for the parameters
    :param param_upper_bnd: array of upper bounds for the parameters
    :return: hx, C and the stored parameters

    """

    hx = np.zeros(M)  # h_x vector, with the x solutions at each sample. Maybe better than using zmean?
    C = np.zeros((n_param, n_param), dtype=float)
    param_store = np.zeros((M, n_param), dtype=float)

    for sample_idx in range(M):
        # generate random values for the parameters
        params = [random.uniform(param_lower_bnd[i], param_upper_bnd[i]) for i in range(n_param)]
        param_store[sample_idx, :] = params

        # x solution for each sample
        hx[sample_idx] = grid_solve(params, indx_Vbus)

        # calculate gradients and form C matrix
        Ag = np.zeros(n_param)
        for i in range(n_param):
            params_delta = np.copy(params)

            # increase a parameter by delta
            params_delta[i] += delta

            # compute gradient as [x(p + delta) - x(p)] / delta
            Ag[i] = (grid_solve(params_delta, indx_Vbus) - hx[sample_idx]) / delta

        Ag_prod = np.outer(Ag, Ag)  # vector by vector to create a matrix
        C += 1 / M * Ag_prod

    return hx, C, param_store


def orthogonal_decomposition(C, tr_error, l_exp):

    """
    Orthogonal decomposition of the covariance matrix to determine the meaningful directions

    :param C: covariance matrix
    :param tr_error: allowed truncation error
    :param l_exp: expansion order
    :return: transformation matrix Wy, number of terms N_t and meaningful directions k

    """

    # eigenvalues and eigenvectors
    v, w = np.linalg.eig(C)

    v_sum = np.sum(v)
    err_v = 1
    k = 0  # meaningful directions
    while err_v > tr_error:
        err_v = 1 - v[k] / v_sum
        k += 1

    N_t = int(math.factorial(l_exp + k) / (math.factorial(k) * math.factorial(l_exp)))  # number of terms
    Wy = w[:, :k]  # and for now, do not define Wz

    return Wy, N_t, k


def permutate(k, l_exp):

    """
    Generate the permutations for all exponents of y
    :param k: number of meaningful directions
    :param l_exp: expansion order
    :return perms: array of permutations
    """

    Nt = int(math.factorial(l_exp + k) / (math.factorial(l_exp) * math.factorial(k)))

    lst = [ll for ll in range(l_exp + 1)] * k
    perms_all = set(itertools.permutations(lst, k))
    perms = []
    for per in perms_all:
        if sum(per) <= l_exp:
            perms.append(per)

    return perms


def polynomial_coeff(M, N_t, Wy, param_store, hx, perms):

    """
    Calculate the coefficients c

    :param M: number of samples
    :param N_t: number of terms
    :param Wy: transformation matrix to go from p to y
    :param param_store: stored values of the parameters for each sample
    :param hx: solutions of the state for each sample
    :param perms: permutations of exponents
    :return: array with c coefficients
    """
    Q = np.zeros((M, N_t), dtype=float)  # store the values of the basis function

    for ll in range(M):
        yy = np.dot(Wy.T, param_store[ll, :])  # go from p to y
        for nn in range(N_t):  # fill a row
            res = 1
            for kk in range(k):  # basis function, with all permutations
                res = res * yy[kk] ** perms[nn][kk]
            Q[ll, nn] = res

    # c_vec = np.dot(np.dot(np.linalg.inv(np.dot(Q.T, Q)), Q.T), hx)
    c_vec = np.dot(np.linalg.solve(np.dot(Q.T, Q), Q.T), hx)

    return c_vec


if __name__ == '__main__':
    # Input values
    x_bus = 5  # bus of interest
    n_param = 8  # number of parameters
    l_exp = 3  # expansion order
    k_est = 0.2  # proportion of expected meaningful directions
    factor_MNt = 2.5  # M = factor_MNt * Nterms, should be around 1.5 and 3
    param_lower_bnd = [0, 0, 0, 0, 0, 0, 0, 0]  # lower limits, in MVA
    param_upper_bnd = [50, 50, 50, 50, 50, 50, 50, 50]  # upper limits, in MVA
    delta = 1e-1  # small increment to calculate gradients
    tr_error = 0.1  # truncation error allowed

    # p1 q1 p2 q2
    # Pl | Ql | Pg

    # PPG = sum(Pl)


    # 1. Initial calculations
    n_k_est = int(k_est * n_param)  # estimated meaningful directions
    N_terms_est = int(math.factorial(l_exp + n_k_est) / (math.factorial(n_k_est) * math.factorial(l_exp)))  # estimated number of terms
    M = int(factor_MNt * N_terms_est)  # estimated number of samples
    indx_Vbus = x_bus - 1  # index to grab the voltage

    # 2. Compute gradients and covariance matrix
    hx, C, param_store = samples_calc(M, n_param, indx_Vbus, param_lower_bnd, param_upper_bnd)

    # 3. Perform orthogonal decomposition
    Wy, N_t, k = orthogonal_decomposition(C, tr_error, l_exp)

    # 4. Generate permutations
    perms = permutate(k, l_exp)

    # 5. Find polynomial coefficients
    c_vec = polynomial_coeff(M, N_t, Wy, param_store, hx, perms)
    print('Array of coefficients: ', c_vec)

    # 6. Test
    pp = [random.uniform(param_lower_bnd[kk], param_upper_bnd[kk]) for kk in range(n_param)]  # random parameters

    x_real = grid_solve(pp, indx_Vbus)

    y_red = np.dot(Wy.T, np.array(pp))
    x_est = 0
    for nn in range(N_t):
        x_est += c_vec[nn] * y_red ** nn  # change for the generic polynomial, todo

    print('Actual state:           ', x_real)
    print('Estimated state:        ', x_est[0])
    print('Error:                  ', abs(x_real - x_est[0]))
