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
from GridCalEngine.basic_structures import Vec, Mat, IntVec


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
        :param m: the number of basis functions.
        :param c: the basis functions weights (m×1 vector).  --> changes with multiple objectives
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
        W = []  # weights
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
        assert m >= d

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

        # Recursive least squares algorithm
        v = np.matmul(self.P, phi, out=self.scratch)
        g0 = v / (1 + np.inner(phi,
                               v))  # --> changes with multiple objectives.  Let g depend on the objective index. Do this initialization for all objectives.
        # P ← P - gvᵀ
        self.P = dger(-1.0, g0, v, a=self.P,
                      overwrite_x=False, overwrite_y=True, overwrite_a=True)

        # for each objective index...
        for i in range(self.n_obj):
            g = g0 * (y[i] - np.inner(phi, self.c[i, :]))  # --> changes with multiple objectives.
            ## So do this calculation for all different objectives, make sure c and y correspond to the right objective
            # So there will be multiple g: one for each. Initialize them the same way with g = v / (1 + np.inner(phi, v))
            self.c[i, :] += g  # do this for each objective

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
        b = np.multiply(self.c, phi_prime, out=self.scratch)  # use c[obj_index]
        return np.matmul(b, self.W)  # 1×d vector

    # --> changes with multiple objectives.
    # Find a way to scalarize mutliple objectives
    def g_scalarize(self, x, scalarization_weights: Vec):
        """
        Evaluates the basis functions at `x`.
        :param x: the decision variable values
        :param scalarization_weights: vector of size n_obj
        """
        # single_obj = inner product between scalarization_weights and vector of g
        # or: single_obj = sum of scalarization_weights[obj_index]*g[obj_index]
        # return single_obj
        return self.g(x) @ scalarization_weights

    # We need to also calculate the Jacobian of the scalarized single_obj,
    # But we can ignore it for now
    # def scalarized_jac
    # Probably just scalarization_weights[obj_index]*g_jac[obj_index]

    def minimum(self, x0, scalarization_weights):
        """
        Find a minimum of the surrogate model approximately.
        :param x0: the initial guess.
        """
        res = minimize(self.g_scalarize, x0,
                       args=(scalarization_weights,),
                       method='L-BFGS-B',
                       # --> changes with multiple objectives: instead of g, minimize the single_obj that comes out of scalarize
                       bounds=self.bounds,
                       # jac=self.g_jac, # remove jacobian at first, until it is calculated
                       options={'maxiter': 20, 'maxfun': 20})
        return res.x


def scale(y, y0,
          scale_threshold=1e-8):  # normalize: do this for every objective so that all objectives are more or less in the same range
    """
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
    #
    # if abs(y0) > scale_threshold
    #     y /= abs(y0)
    return y


def inv_scale(y_scaled, y0,
              scale_threshold=1e-8):  # do this for every objective so that all objectives are more or less in the same range
    """
    Computes the inverse function of `scale(y, y0)`.
    :param y_scaled: the scaled objective function value.
    :param y0: the initial objective function value, `y(x0)`.
    :param scale_threshold: value under which no scaling is done
    :return: the value `y` such that `scale(y, y0) = y_scaled`.
    """
    if abs(y0) > scale_threshold:
        y_scaled *= abs(y0)
    return y_scaled + y0


def dominates(sol_a: Vec, sol_b: Vec):
    """
    Check if a solution dominates another in the Pareto sense
    :param sol_a: Array representing the solution A (row of the population)
    :param sol_b: Array representing the solution B (row of the population)
    :return: A dominates B?
    """
    # Check if sol_a dominates sol_b
    better_in_any = False
    for a, b in zip(sol_a, sol_b):
        if a > b:  # Assuming a lower value is better; change logic if otherwise
            return False  # sol_a is worse in at least one objective
        elif a < b:
            better_in_any = True
    return better_in_any


def get_non_dominated_fronts(population: Mat) -> List[List[int]]:
    """
    2D non dominated sorting
    :param population: matrix (n points, ndim)
    :return: Fronts ordered by position (front 1, front 2, Front 3, ...)
            Each front is a list of integers representing the positions in the population matrix
    """
    fronts = [[]]  # Initialize the first front
    dom_counts = np.zeros(len(population))  # [0] * len(population)  # Dominance counts
    dom_sets = [set() for _ in range(len(population))]  # Sets of solutions dominated by each individual

    for i, sol_i in enumerate(population):
        for j, sol_j in enumerate(population):
            if i != j:
                if dominates(sol_i, sol_j):
                    dom_sets[i].add(j)
                elif dominates(sol_j, sol_i):
                    dom_counts[i] += 1

        if dom_counts[i] == 0:  # If no one dominates this solution, it's in the first front
            fronts[0].append(i)

    current_front = 0
    while fronts[current_front]:
        next_front = []
        for i in fronts[current_front]:
            for j in dom_sets[i]:
                dom_counts[j] -= 1  # Reduce the domination count
                if dom_counts[j] == 0:  # If it's not dominated by any other, it's in the next front
                    next_front.append(j)
        current_front += 1
        fronts.append(next_front)

    return fronts[:-1]  # Exclude the last empty front


def crowding_distance(front: List[int], population: Mat) -> Vec:
    """

    :param front: list of integers representing the positions in the population matrix
    :param population: Matrix of function evaluations (Npoints, NObjdim)
    :return:
    """

    # Initialize crowding distances
    distances = np.zeros(len(front))

    if len(front) == 0:
        return distances

    # Number of objectives
    num_objectives = population.shape[1]

    for m in range(num_objectives):
        # Sort solutions by this objective
        front.sort(key=lambda x: population[x, m])

        # Boundary points are always selected
        distances[0] = float('inf')
        distances[-1] = float('inf')

        # Objective range
        obj_range = population[front[-1], m] - population[front[0], m]
        if obj_range == 0:
            continue  # Avoid division by zero

        # Update crowding distances
        for i in range(1, len(front) - 1):
            distances[i] += (population[front[i + 1], m] - population[front[i - 1], m]) / obj_range

    return distances


def sort_by_crowding(fronts: List[List[int]], population: Mat) -> Tuple[Mat, IntVec]:
    """

    :param fronts: Fronts ordered by position (front 1, front 2, Front 3, ...)
            Each front is a list of integers representing the positions in the population matrix
    :param population: Matrix of function evaluations (Npoints, NObjdim)
    :return: sorted population, array of sorting indices
    """
    # Assuming 'fronts' is the output from your get_non_dominated_fronts function
    # and 'population' contains all your solutions
    crowding_distances = []
    for front in fronts:
        distances = crowding_distance(front, population)
        crowding_distances.append(distances)

    sorted_fronts = []
    for front, distances in zip(fronts, crowding_distances):
        # Pair each solution with its distance and sort by distance in descending order
        sorted_front = sorted(list(zip(front, distances)), key=lambda s: s[1], reverse=True)
        sorted_fronts.append([item[0] for item in sorted_front])  # Extract the sorted indices

    sorting_indices = []
    remaining_slots = population.shape[0]  # however many individuals you want in the new population

    for sorted_front in sorted_fronts:
        if len(sorted_front) <= remaining_slots:
            # If the entire front fits, add all individuals from this front to the new population
            sorting_indices.extend(sorted_front)
            remaining_slots -= len(sorted_front)
        else:
            # If not all individuals fit, select the ones with the largest crowding distance
            sorting_indices.extend(sorted_front[:remaining_slots])
            break  # The new population is now full

    return population[sorting_indices, :], sorting_indices


def non_dominated_sorting(y_values: Mat, x_values: Mat):
    """
    Use non dominated sorting and crowded sorting to sort the multidimensional objectives
    :param y_values: Matrix of function evaluations (Npoints, NObjdim)
    :param x_values: Matrix of values (Npoints, Ndim)
    :return: Return the pareto y and matching x. The pareto front may have less values than the population
             [Sorted population, Sorted input values (X)]
    """
    # obtain the sorting fronts
    fronts = get_non_dominated_fronts(y_values)

    # use the fronts to sort using the crowded sortig algorithm
    # sorted_population, sorting_indices = sort_by_crowding(fronts=fronts, population=y_values)
    sorted_population, sorting_indices = sort_by_crowding(fronts=[fronts[0]], population=y_values)

    return sorted_population, x_values[sorting_indices, :]


def MVRSM_multi_minimize(obj_func, x0: Vec, lb: Vec, ub: Vec, num_int: int, max_evals: int, n_objectives: int,
                         rand_evals: int = 0, args=()):
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
    :param args: extra arguments to be passed to obj_func appart from x
    :return: pareto front y, pareto front x, all y not sorted
    """
    d = len(x0)  # number of decision variables

    model = SurrogateModel.init(n_objectives, d, lb, ub, num_int)
    next_x = x0  # candidate solution

    y_population = np.zeros((max_evals, n_objectives))
    x_population = np.zeros((max_evals, d))

    # Iteratively evaluate the objective, update the model, find the minimum of the model,
    # and explore the search space.
    for i in range(max_evals):

        # Evaluate the objective function
        x = next_x.astype(float, copy=False)
        y = obj_func(x, *args)

        # store the solution in the population at the position "i"
        y_population[i, :] = y
        x_population[i, :] = x

        # Update the surrogate model
        model.update(x, y)

        if i >= rand_evals:
            # rnd_weights = np.random.rand(n_objectives)
            rnd_weights = np.random.lognormal(0, 1, n_objectives)
            # rnd_weights = np.full(n_objectives, 0.5)
            scalarization_weights = rnd_weights / rnd_weights.sum()

            # Minimize surrogate model
            next_x = model.minimum(x, scalarization_weights)

            # Round discrete variables to the nearest integer.
            next_x[0:num_int].round(out=next_x[0:num_int])

            # Just to be sure, clip the decision variables to the bounds.
            np.clip(next_x, lb, ub, out=next_x)

        # Perform exploration to prevent the algorithm from getting stuck in local minima
        # of the surrogate model.
        if i < rand_evals:
            # Perform random search
            # next_x = np.random.binomial(1, rand_search_bias, num_int)  # [GTEP]
            next_x[0:num_int] = np.random.binomial(1, np.random.rand(), num_int)  # integer variables
            next_x[num_int:d] = np.random.uniform(lb[num_int:d], ub[num_int:d])  # continuous variables

        # Skip exploration in the last iteration (to end at the exact minimum of the surrogate model).
        elif i < max_evals - 2:
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
    y_sorted, x_sorted = non_dominated_sorting(y_values=y_population.copy(),
                                               x_values=x_population)

    return y_sorted, x_sorted, y_population, x_population


if __name__ == '__main__':
    from matplotlib import pyplot as plt
    from trunk.MVRSM.functions import dim10Rosenbrock_multi2, shaffer

    # Rosenbrock with multiple objectives to test multi-objective MVRSM
    # ff = dim10Rosenbrock_multi2
    # d = 10  # Total number of variables
    # lb = -2 * np.ones(d).astype(int)  # Lower bound
    # ub = 2 * np.ones(d).astype(int)  # Upper bound
    # num_int = 3  # number of integer variables
    # lb[0:num_int] = 0
    # ub[0:num_int] = num_int + 1

    ff = shaffer
    d_ = 1  # Total number of variables
    lb_ = np.full(d_, -10)  # Lower bound
    ub_ = np.full(d_, 10)  # Upper bound
    num_int_ = 0  # number of integer variables
    # lb[0:num_int] = 0
    # ub[0:num_int] = num_int + 1

    x0_ = np.zeros(d_)  # Initial guess
    # x0[0:num_int] = np.round(np.random.rand(num_int) * (ub[0:num_int] - lb[0:num_int]) + lb[0:num_int])  # Random initial guess (integer)
    # x0[num_int:d] = np.random.rand(d - num_int) * (ub[num_int:d] - lb[num_int:d]) + lb[num_int:d]  # Random initial guess (continuous)

    sorted_y_, sorted_x_, y_population_, x_population_ = MVRSM_multi_minimize(obj_func=ff,
                                                                              x0=x0,
                                                                              lb=lb,
                                                                              ub=ub,
                                                                              num_int=num_int,
                                                                              max_evals=400,
                                                                              n_objectives=2,
                                                                              rand_evals=100, args=())

    print("Best solutions:")
    print(sorted_y_)

    plt.scatter(sorted_y_[:, 0], sorted_y_[:, 1], 1, )
    # plt.plot(y_population_[:, 0])
    plt.show()
