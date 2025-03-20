# MIT License
#
# Copyright (c) 2020 Laurens Bliek
# MVRSM uses a piece-wise linear surrogate model for optimization of
# expensive cost functions with mixed-integer variables.
#
# MVRSM_minimize(obj, x0, lb, ub, num_int, max_evals, rand_evals) solves the minimization problem
#
# min f(x)
# st. lb<=x<=ub, the first num_int variables of x are integer
#
# where obj is the objective function, x0 the initial guess,
# lb and ub are the bounds, num_int is the number of integer variables,
# and max_evals is the maximum number of objective evaluations (rand_evals of these
# are random evaluations).
#
# Laurens Bliek, 06-03-2019
#
# Source: https://github.com/lbliek/MVRSM
# Article: Black-box Mixed-Variable Optimization using a Surrogate Model that Satisfies Integer Constraints,
# 		   by Laurens Bliek, Arthur Guijt, Sicco Verwer, Mathijs de Weerdt

import math
import random
import numpy as np
from typing import List, Tuple
from scipy.linalg.blas import dger
from scipy.optimize import minimize
from GridCalEngine.Utils.NumericalMethods.non_dominated_sorting import non_dominated_sorting, dominates
from GridCalEngine.basic_structures import Vec, Mat


def relu(x):
    """
    The Rectified Linear Unit (ReLU) function.
    :param x: the input and output vector
    """
    return np.maximum(0, x, out=x)


def relu_deriv(x):
    """
    The derivative of the rectified linear unit function,
    defined with `relu_deriv(0) = 0.5`.
    :param x: the input and output vector
    """
    return np.heaviside(x, 0.5, out=x)


class SurrogateModel:
    """
    SurrogateModel
    """

    def __init__(self, n_obj: int, m: int, c: Mat, W: Mat, b: Vec, reg: float, bounds: List[Tuple[float, float]]):
        """
        Container for the surrogate model data, defined as a linear combination of
        `m` basis functions whose weights `c` are to be trained. The basis function
        `Φ_k(x)` is a ReLU with input `z_k(x)`, a linear function with weights `W_{k, ·}ᵀ`
        and bias `b_k`.
        Let `d` be the number of (discrete and continuous) decision variables.
        :param n_obj: the number of decision variables
        :param m: the number of basis functions.
        :param c: the basis functions weights (n_obj x m matrix).  --> changes with multiple objectives
        :param W: the `z_k(x)` functions weights (m×d matrix).
        :param b: the `z_k(x)` functions biases (m×1 vector).
        :param reg: the regularization parameter.
        :param bounds: the decision variable bounds. (scipy's bounds)
        """
        self.n_obj = n_obj
        self.m = m
        self.c = c
        self.W = W
        self.b = b
        # RLS covariance matrix, stored in column-major order (we *almost* exclusively
        # treat this matrix with BLAS routines).
        self.P = np.zeros((m, m), order='F')
        np.fill_diagonal(self.P, 1 / reg)
        self.bounds = bounds
        self.scratch = np.zeros(m)  # vector to store temporary results and avoid unnecessary allocations.

    @classmethod
    def init(cls, n_obj: int, d: int, lb: Vec, ub: Vec, num_int: int) -> 'SurrogateModel':
        """
        Initializes a surrogate model.
        :param n_obj: number of objective function dimensions
        :param d: the number of (discrete and continuous) decision variables.
        :param lb: the lower bound of the decision variable values.
        :param ub: the upper bound of the decision variable values.
        :param num_int: the number of discrete decision variables (`0 ≤ num_int ≤ d`).
        """
        # Define the basis functions parameters.
        W = []  # weights  TODO: can we know the size beforehand?
        b = []  # biases

        # Add a constant basis functions independent of x, giving the model an offset.
        W.append([0] * d)
        b.append(1)

        # Add basis functions dependent on one integer variable
        for k in range(num_int):
            for i in range(int(lb[k]), int(ub[k]) + 1):
                weights = np.zeros(d)
                if i == lb[k]:
                    weights[k] = 1
                    W.append(weights)
                    b.append(-i)
                elif i == ub[k]:
                    weights[k] = -1
                    W.append(weights)
                    b.append(i)
                else:
                    weights[k] = -1
                    W.append(weights)
                    b.append(i)

                    weights = np.zeros(d)
                    weights[k] = 1
                    W.append(weights)
                    b.append(-i)

        # Add basis functions dependent on two subsequent integer variables
        for k in range(1, num_int):
            for i in range(int(lb[k]) - int(ub[k - 1]), int(ub[k]) - int(lb[k - 1]) + 1):
                weights = np.zeros(d)
                if i == lb[k] - ub[k - 1]:
                    weights[k] = 1
                    weights[k - 1] = -1
                    W.append(weights)
                    b.append(-i)
                elif i == ub[k] - lb[k - 1]:
                    weights[k] = -1
                    weights[k - 1] = 1
                    W.append(weights)
                    b.append(i)
                else:
                    weights[k] = -1
                    weights[k - 1] = 1
                    W.append(weights)
                    b.append(i)

                    weights = np.zeros(d)
                    weights[k] = 1
                    weights[k - 1] = -1
                    W.append(weights)
                    b.append(-i)

        # The number of basis functions only related to discrete variables.
        int_basis_count = len(b) - 1

        W = np.asarray(W)
        b = np.asarray(b)
        m = len(b)  # the number of basis functions
        # assert m >= d

        c = np.zeros((n_obj, m))  # the model weights --> changes with multiple objectives
        # something like c = np.zeros(m, nr_objectives)
        # or: nr_objectives number of vectors c
        # Set model weights corresponding to discrete basis functions to 1, stimulates convexity.
        c[:, 1:int_basis_count + 1] = 1

        # The regularization parameter. 1e-8 is good for the noiseless case,
        # replace by ≈1e-3 if there is noise.
        reg = 1e-8
        bounds = list(zip(lb, ub))
        return cls(n_obj, m, c, W, b, reg, bounds)

    def phi(self, x, out=None):
        """
        Evaluates the basis functions at `x`.
        :param x: the decision variable values
        :param out: the vector in which to put the result; `None` to allocate.
        """
        z = np.matmul(self.W, x, out=out)
        z += self.b
        return relu(z)

    def phi_deriv(self, x, out=None):
        """
        Evaluates the derivatives of the basis functions with respect to `x`.
        :param x: the decision variable values
        :param out: the vector in which to put the result; `None` to allocate.
        """
        z = np.matmul(self.W, x, out=out)
        z += self.b
        return relu_deriv(z)

    def update(self, x, y):
        """
        Updates the model upon the observation of a new data point `(x, y)`.
        :param x: the decision variables values
        :param y: the objective function value `y(x)`
        """

        phi = self.phi(x)  # basis function values for k = 1, ..., m.
        # st = timeit.default_timer()
        # Recursive least squares algorithm
        v = np.matmul(self.P, phi, out=self.scratch)
        # end = timeit.default_timer()
        # print(f"Time to calculate v: {end - st}")

        # st = timeit.default_timer()
        # --> changes with multiple objectives.  Let g depend on the objective index. Do this initialization for all objectives.
        g0 = v / (1 + np.inner(phi, v))
        # P ← P - gvᵀ
        # end = timeit.default_timer()
        # print(f"Time to calculate g0: {end - st}")

        # st = timeit.default_timer()
        self.P = dger(-1.0, g0, v, a=self.P, overwrite_x=False, overwrite_y=True, overwrite_a=True)
        # end = timeit.default_timer()
        # print(f"Time to update P: {end - st}")

        # st = timeit.default_timer()
        # for each objective index...
        for i in range(self.n_obj):
            g = g0 * (y[i] - np.inner(phi, self.c[i, :]))  # --> changes with multiple objectives.
            ## So do this calculation for all different objectives, make sure c and y correspond to the right objective
            # So there will be multiple g: one for each. Initialize them the same way with g = v / (1 + np.inner(phi, v))
            self.c[i, :] += g  # do this for each objective
        # end = timeit.default_timer()
        # print(f"Time to update c: {end - st}")

    def g(self, x):  # change this to have the objective index in the argument   def g(self, x, obj_index):
        """
        Evaluates the surrogate model at `x`.
        :param x: the decision variable values.
        """
        phi = self.phi(x)  # phi does not change with multiple obj.
        # ret = np.empty(self.n_obj, dtype=float)
        # for i in range(self.n_obj):
        #     ret[i] = np.inner(self.c[i,:], phi)   # c[obj_index]
        return self.c @ phi  # vector of size n_obj

    def g_jac(self, x):  # change this to have the objective index in the argument   def g(self, x, obj_index):
        """
        Evaluates the Jacobian of the model at `x`.
        :param x: the decision variable values.
        """
        phi_prime = self.phi_deriv(x, out=self.scratch)
        # b = np.multiply(self.c[i,:], phi_prime, out=self.scratch)  # use c[obj_index]
        b = np.empty((self.n_obj, self.m))
        for i in range(self.n_obj):
            b[i, :] = self.c[i, :] * phi_prime
        return b @ self.W  # n_obj×d matrix

    def g_scalarize(self, x, scalarization_weights: Vec):
        """
        Evaluates the linear scalarization of multiple objectives.
        :param x: the decision variable values
        :param scalarization_weights: vector of size n_obj
        """
        # single_obj = inner product between scalarization_weights and vector of g
        # or: single_obj = sum of scalarization_weights[obj_index]*g[obj_index]
        # return single_obj
        return self.g(x) @ scalarization_weights

    def g_scalarize_max(self, x, scalarization_weights):
        """
        Evaluates the maximum or Tchebycheff scalarization of multiple objectives.
        :param x: the decision variable values
        :param scalarization_weights: vector of size n_obj
        """
        # worst objective after multiplying with weight
        mul = np.multiply(self.g(x), scalarization_weights)
        j = np.argmax(mul)
        return self.g(x)[j]

    def g_scalarize_jac(self, x, scalarization_weights):
        """
        Evaluates the Jacobian of the linear scalarization of multiple objectives.
        :param x: the decision variable values
        :param scalarization_weights: vector of size n_obj
        """
        return np.matmul(scalarization_weights, self.g_jac(x))

    def g_scalarize_max_jac(self, x, scalarization_weights):
        """
        Evaluates the Jacobian of the maximum or Tchebycheff scalarization of multiple objectives.
        :param x: the decision variable values
        :param scalarization_weights: vector of size n_obj
        """
        mul = np.multiply(self.g(x), scalarization_weights)
        j = np.argmax(mul)
        return self.g_jac(x)[j, :]

    def augmented_Tchebycheff(self, x, scalarization_weights):
        """
        Evaluates the augmented Tchebycheff scalarization of multiple objectives.
        :param x: the decision variable values
        :param scalarization_weights: vector of size n_obj
        """
        # Augmented Tchebycheff scalarization from ``ParEGO: A Hybrid Algorithm With On-Line Landscape Approximation for Expensive Multiobjective Optimization Problems''
        return self.g_scalarize_max(x, scalarization_weights) + 0.05 * self.g_scalarize(x, scalarization_weights)

    def augmented_Tchebycheff_jac(self, x, scalarization_weights):
        """
        Evaluates the Jacobian of the augmented Tchebycheff scalarization of multiple objectives.
        :param x: the decision variable values
        :param scalarization_weights: vector of size n_obj
        """
        return self.g_scalarize_max_jac(x, scalarization_weights) + 0.05 * self.g_scalarize_jac(x,
                                                                                                scalarization_weights)

    def minimum(self, x0: Vec, scalarization_weights: Vec) -> Vec:
        """
        Find a minimum of the surrogate model approximately.
        :param x0: the initial guess.
        :param scalarization_weights: weights for the scalarization of multiple objectives
        :return minimization evaluation and corresponding function values
        """
        scalarization_type = 2  # 0=linear, 1=max, 0.5 is a mix, 2 is augmented Tchebycheff.
        # max seems to capture the shape of nonconvex pareto front better (also according to theory)
        # but has worse performance

        # Current default is the augmented Tchebycheff, as it is used in other papers.

        if scalarization_type == 0:
            # with linear scalarization
            # print('Using linear scalarization')
            res = minimize(self.g_scalarize, x0, args=(scalarization_weights,), method='L-BFGS-B', bounds=self.bounds,
                           jac=self.g_scalarize_jac,
                           options={'maxiter': 20, 'maxfun': 20})
            return res.x
        elif scalarization_type == 1:
            # with max scalarization
            # Similar to:
            # Golovin, Daniel and Qiuyi Zhang. “Random Hypervolume Scalarizations for
            # Provable Multi-Objective Black Box Optimization.” ArXiv abs/2006.04655 (2020): n. pag.
            # print('Using max scalarization')
            res = minimize(self.g_scalarize_max, x0, args=(scalarization_weights,), method='L-BFGS-B',
                           bounds=self.bounds,
                           jac=self.g_scalarize_max_jac,
                           options={'maxiter': 20, 'maxfun': 20})
            return res.x
        elif scalarization_type == 0.5:
            # with mix scalarization
            r = random.random()
            if r > 0.5:
                # print('Using mixed scalarization (now max)')
                res = minimize(self.g_scalarize_max, x0, args=(scalarization_weights,), method='L-BFGS-B',
                               bounds=self.bounds,
                               jac=self.g_scalarize_max_jac,
                               options={'maxiter': 20, 'maxfun': 20})
                return res.x
            elif r <= 0.5:
                # print('Using mixed scalarization (now linear)')
                res = minimize(self.g_scalarize, x0, args=(scalarization_weights,), method='L-BFGS-B',
                               bounds=self.bounds,
                               jac=self.g_scalarize_jac,
                               options={'maxiter': 20, 'maxfun': 20})
                return res.x
            else:
                raise Exception('Warning: wrong random number generated')
        elif scalarization_type == 2:
            # with augmented Tchebycheff scalarization
            # (from ``ParEGO: A Hybrid Algorithm With On-Line Landscape Approximation for Expensive
            # Multiobjective Optimization Problems'')
            # Warning: type 2 Augmented Tchebycheff is untested!!!
            # print('Using augmented Tchebycheff scalarization')
            res = minimize(self.augmented_Tchebycheff, x0, args=(scalarization_weights,), method='L-BFGS-B',
                           bounds=self.bounds,
                           jac=self.augmented_Tchebycheff_jac,
                           options={'maxiter': 20, 'maxfun': 20})
            return res.x
        else:
            raise Exception('Warning: wrong scalarization chosen.')




def scale(y, y0, scale_threshold=1e-8):
    """
    # normalize: do this for every objective so that all objectives are more or less in the same range
    Scale the objective with respect to the initial objective value,
    causing the optimum to lie below zero. This helps exploration and
    prevents the algorithm from getting stuck at the boundary.
    :param y: the objective function value.
    :param y0: the initial objective function value, `y(x0)`.
    :param scale_threshold: value under which no scaling is done
    """
    y = np.asarray(y)
    y0 = np.asarray(y0)
    y0 = abs(y0)
    y -= y0
    for i in range(len(y)):
        if y0[i] > scale_threshold:
            y[i] /= y0[i]
    return y


def inv_scale(y_scaled, y0,
              scale_threshold=1e-8):
    """
    Computes the inverse function of `scale(y, y0)`.
    :param y_scaled: the scaled objective function value.
    :param y0: the initial objective function value, `y(x0)`.
    :param scale_threshold: value under which no scaling is done
    :return: the value `y` such that `scale(y, y0) = y_scaled`.
    """
    for i in range(len(y0)):
        if abs(y0[i]) > scale_threshold:
            y_scaled[i] *= abs(y0[i])
    return y_scaled + y0


def get_norm_factors(scaling_values):
    """
    Computes the factors used to normalize objective function criteria..
    :param scaling_values: Array with all the criteria obtained during random evaluation process.
    :return: Tuple of arrays where 1st array is maximum values of y and second minimum values.
    """
    terms_max = np.max(scaling_values, axis=0)
    terms_min = np.min(scaling_values, axis=0)

    return terms_max, terms_min


def normalize_md(y_no_normalized, norm_factors):
    """
    Computes the normalization of y_no_normalized --> y_normalized=(y_no_normalized-y_min)/(y_max-y_min).
    :param y_no_normalized: The no normalized objective function values: np.array.shape[1]=f_obj_dim.
    :param norm_factors: Tuple of arrays where 1st array is maximum values of y and second minimum values.
    :return: the value `y_normalized` such that `normalize_md(y_no_normalized, y0) = y_normalized`.
    """
    max_min = norm_factors[0] - norm_factors[1]
    max_min[max_min == 0] = 1

    return (y_no_normalized - norm_factors[1]) / max_min


def inv_normalize_md(y_normalized, norm_factors):
    """
    Computes the inverse of normalize_md(y_no_normalized, norm_factors).
    :param y_normalized: The normalized objective function values: np.array.shape[1]=f_obj_dim.
    :param norm_factors: Tuple of arrays where 1st array is maximum values of y and second minimum values.
    :return: the value `y_no_normalized` such that `inv_normalize_md(y_normalized, y0) = y_no_normalized`.
    """

    max_min = norm_factors[0] - norm_factors[1]

    return y_normalized * max_min + norm_factors[1]


def MVRSM_mo_pareto(obj_func,
                    x0: Vec,
                    lb: Vec,
                    ub: Vec,
                    num_int: int,
                    max_evals: int,
                    n_objectives: int,
                    rand_evals: int = 0,
                    args=()):
    """
    MVRSM algorithm for multiple objectives
    x = [integer vars | float vars]
    :param obj_func: objective function
    :param x0: Initial solution [int vars | float vars]
    :param lb: lower bound
    :param ub: Upper bound
    :param num_int: number of integer variables sice x will be split by this amount ([int vars | float vars])
    :param max_evals: maximum number of evaluations
    :param n_objectives: number of objectives expected
    :param rand_evals: number of random initial evaluations
    :param args: extra arguments to be passed to obj_func apart from x
    :return: pareto front y, pareto front x, all y not sorted
    """
    d = len(x0)  # number of decision variables

    model = SurrogateModel.init(n_objectives, d, lb, ub, num_int)
    next_x = np.array(x0, dtype=float)  # candidate solution

    best_x = np.copy(next_x)  # best candidate solution found so far
    best_y = obj_func(best_x)  # least objective function value found so far, equal to obj(best_x).
    # Do this if best_y does not have a value for each objective:
    # if n_objectives >=2:
    #    best_y = [math.inf]*n_objectives  # least objective function value found so far, equal to obj(best_x).

    # Initialize storing arrays
    y_population = np.zeros((max_evals, n_objectives))
    x_population = np.zeros((max_evals, d))

    # if n_objectives >= 2:  # should always be declared
    Pareto_index = []  # List of the iterations of which evaluated solutions are currently Pareto optimal

    # Start random iterations loop
    for i in range(rand_evals):
        # Evaluate random point
        x = next_x.astype(float, copy=False)
        y = obj_func(x, *args)

        # Store evaluated point
        x_population[i, :] = x
        y_population[i, :] = y

        # Perform random search
        next_x[0:num_int] = np.random.binomial(1, np.random.rand(), num_int)  # integer variables
        next_x[num_int:d] = np.random.uniform(lb[num_int:d], ub[num_int:d])  # continuous variables
        # next_x[num_int:d] = np.random.beta(np.random.uniform(0, 5), np.random.uniform(0, 5), size=d-num_int)

    # Once random iterations finish, get y_max and y_min for each objective
    normalization_factors = get_norm_factors(y_population[:rand_evals, :])

    # Normalize objectives obtained in random evaluations
    objectives_normalized = normalize_md(y_population[:rand_evals, :], normalization_factors)

    # Get best point yet
    sorted_y, sorted_x, sorting_indices = non_dominated_sorting(objectives_normalized,
                                                                x_population[:rand_evals, :])
    best_y = sorted_y[0]
    best_x = sorted_x[0]

    # Update the model with the normalized random evaluation points
    for rand_it in range(len(objectives_normalized)):
        model.update(x=x_population[rand_it], y=objectives_normalized[rand_it])
        # print(f"Time to update model: {e_time - st_time}")

    # Iteratively evaluate the objective, update the model, find the minimum of the model,
    # and explore the search space.
    for i in range(rand_evals, max_evals):

        # Evaluate the objective function
        x = next_x.astype(float, copy=False)
        y = obj_func(x, *args)

        # Store the solution in the population at the position "i"
        y_population[i, :] = y
        x_population[i, :] = x

        # Update the surrogate model
        y_normalized = normalize_md(y_no_normalized=y, norm_factors=normalization_factors)

        model.update(x=x, y=y_normalized)
        # e_time = time.time()
        # print(f"Time to update model: {e_time - st_time}")

        # Keep track of Pareto front
        # Note: Should actually do this for the random evaluations too
        # Note2: Can make this shorter by using the existing dominates function
        if n_objectives >= 2:
            if i == rand_evals:
                Pareto_index.append(i)
            else:
                y_is_dominated = 0  # whether y is dominated by any of the previous Pareto optimal solutions

                # Pareto optimal points that should be removed because they are not Pareto optimal anymore due to y
                pp_to_remove = []

                for pp in Pareto_index:
                    y_dominates_pp = 0
                    pp_dominates_y = 0
                    TOL = 1e-8  # tolerance level for determining Pareto optimality
                    y_pp_scaled = normalize_md(y_population[pp, :], normalization_factors)

                    # Check if y is exactly the same as pp, in which case it is not
                    # useful to add it to the list of Pareto optimal solutions
                    if np.all(y_pp_scaled == y_normalized):
                        y_is_dominated = 1
                        break
                    for obj_i in range(n_objectives):
                        # Situation A: y is dominated by pp
                        diff = y_pp_scaled[obj_i] - y_normalized[obj_i]
                        if diff < -TOL:
                            pp_dominates_y += 1

                        # Situation B: pp dominated by y
                        if diff > TOL:
                            y_dominates_pp += 1
                    # print('pp_dominates_y', pp_dominates_y)
                    # print('y_dominates_pp', y_dominates_pp)
                    # Situation A: y is dominated by pp
                    if pp_dominates_y >= 1 and y_dominates_pp == 0:
                        # keep list the same, and don't add y
                        # y is dominated by pp so stop checking other pp
                        y_is_dominated = 1
                        # print('A')
                        break

                    # Situation B: pp dominated by y
                    if y_dominates_pp >= 1 and pp_dominates_y == 0:
                        pp_to_remove.append(pp)
                        # print('B')
                for pp in pp_to_remove:
                    Pareto_index.remove(pp)
                # Situation C: pp and y don't dominate each other, for every pp --> y is then Pareto optimal
                if y_is_dominated == 0:
                    Pareto_index.append(i)

        # Get scalarization weights
        rnd_weights = np.random.rand(n_objectives)
        # rnd_weights = np.random.lognormal(0, 1, n_objectives)
        # rnd_weights = np.full(n_objectives, 0.5)
        scalarization_weights = rnd_weights / rnd_weights.sum()

        # Pick a random Pareto optimal x to start optimization from
        if n_objectives >= 2:
            rand_pp = np.random.randint(len(Pareto_index))
            best_x = x_population[Pareto_index[rand_pp], :]
        # if n_objectives == 1:
        #     if y_normalized < best_y:
        #         best_x = np.copy(x)
        #         best_y = y

        # Minimize surrogate model
        if n_objectives == 1:
            if dominates(y, best_y):
                best_x = np.copy(x)
                best_y = y_normalized
        # st_time = time.time()
        next_x = model.minimum(x0=best_x, scalarization_weights=scalarization_weights)
        # e_time = time.time()
        # print(f"Time to find minimum: {e_time - st_time}")
        # Round discrete variables to the nearest integer.
        next_x[0:num_int].round(out=next_x[0:num_int])

        # Just to be sure, clip the decision variables to the bounds.
        np.clip(next_x, lb, ub, out=next_x)

        # Perform exploration to prevent the algorithm from getting stuck in local minima
        # of the surrogate model.

        # Skip exploration in the last iteration (to end at the exact minimum of the surrogate model).
        if i < max_evals - 2:
            # Randomly perturb the discrete variables. Each x_i is shifted n units
            # to the left (if dir is False) or to the right (if dir is True).
            # The bounds of each variable are respected.

            int_pert_prob = 1.0 / d  # probability that x_i is permuted

            # integer exploration
            for j in range(num_int):

                r = random.random()  # determines n
                direction = random.getrandbits(1)  # whether to explore towards -∞ or +∞
                value = next_x[j]

                while r < int_pert_prob:

                    if lb[j] == value < ub[j]:
                        value += 1

                    elif lb[j] < value == ub[j]:
                        value -= 1

                    elif lb[j] < value < ub[j]:
                        value += 1 if direction else -1

                    r *= 2

                next_x[j] = value

            # Continuous exploration
            for j in range(num_int, d):

                value = next_x[j]

                while True:  # re-sample while out of bounds.
                    # Choose a variance that scales inversely with the number of decision variables.
                    # Note that Var(aX) = a^2 Var(X) for any random variable.
                    delta = np.random.normal() * (ub[j] - lb[j]) * 0.1 / math.sqrt(d)

                    if lb[j] <= value + delta <= ub[j]:
                        next_x[j] += delta
                        break

    # apply non-dominated sorting
    y_sorted, x_sorted, sorting_indices = non_dominated_sorting(y_values=y_population.copy(),
                                                                x_values=x_population)

    return y_sorted, x_sorted, y_population, x_population
