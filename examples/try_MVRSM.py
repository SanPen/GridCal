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
from re import I
import time
import csv
import numpy as np
import matplotlib.pyplot as plt
from enum import Enum
from mpl_toolkits.mplot3d import Axes3D
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowResults, PowerFlowOptions
from GridCalEngine.enumerations import SolverType

from itertools import product
from scipy.optimize import minimize, Bounds


def relu(x):
    """
    The Rectified Linear Unit (ReLU) function.
    :param x: the input
    """
    return np.maximum(0, x)


def relu_deriv(x):
    """
    The derivative of the rectified linear unit function,
    defined with `relu_deriv(0) = 0.5`.
    :param x: the input
    """
    return (x > 0) + 0.5 * (x == 0)


class SurrogateModel:
    def __init__(self, m, c, W, b, reg, bounds: Bounds):
        """
        Container for the surrogate model data, defined as a linear combination of
        `m` basis functions whose weights `c` are to be trained. The basis function
        `Φ_k(x)` is a ReLU with input `z_k(x)`, a linear function with weights `W_{k, ·}ᵀ`
        and bias `b_k`.
        Let `d` be the number of (discrete and continuous) decision variables.
        :param m: the number of basis functions.
        :param c: the basis functions weights (m×1 vector).
        :param W: the `z_k(x)` functions weights (m×d matrix).
        :param b: the `z_k(x)` functions biases (m×1 vector).
        :param reg: the regularization parameter.
        :param bounds: the decision variable bounds.
        """
        self.m = m
        self.c = c
        self.W = W
        self.b = b
        self.P = np.diag(np.full(m, 1 / reg))  # RLS covariance matrix
        self.bounds = bounds

    @classmethod
    def init(cls, d, lb, ub, num_int) -> 'SurrogateModel':
        """
        Initializes a surrogate model.
        :param d: the number of (discrete and continuous) decision variables.
        :param lb: the lower bound of the decision variable values.
        :param ub: the upper bound of the decision variable values.
        :param num_int: the number of discrete decision variables (`0 ≤ num_int ≤ d`).
        """
        # Define the basis functions parameters.
        # TODO: ask Laurens if it is possible to know size beforehand
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

        # Add `num_cont` random linearly independent basis functions (and parallel ones)
        # that depend on both integer and continuous variables, where `num_cont` is
        # the number of continuous variables.
        num_cont = d - num_int
        W_cont = np.random.random((num_cont, d))
        W_cont = (2 * W_cont - 1) / d  # normalize between -1/d and 1/d.
        for k in range(num_cont):
            # Find the set in which `b` needs to lie by moving orthogonal to W.
            signs = np.sign(W_cont[k])

            # Find relevant corner points of the [lb, ub] hypercube.
            corner_1 = np.copy(lb)
            corner_2 = np.copy(ub)
            for j in range(d):
                if signs[j] < 0:
                    corner_1[j] = ub[j]
                    corner_2[j] = lb[j]

            # Calculate minimal distance from hyperplane to corner points.
            b1 = np.dot(W_cont[k], corner_1)
            b2 = np.dot(W_cont[k], corner_2)

            if b1 > b2:
                print('Warning: b1>b2. This may lead to problems.')

            # Add the same number of basis functions as for the discrete variables.
            # for j in range(math.ceil(int_basis_count / num_int)):
            #     # or just add 1000 of them
            #     # for j in range(1000):
            #     b_j = (b2 - b1) * np.random.random() + b1
            #     W.append(W_cont[k])
            #     b.append(-float(b_j))

        W = np.asarray(W)
        b = np.asarray(b)
        m = len(b)  # the number of basis functions

        c = np.zeros(m)  # the model weights
        # Set model weights corresponding to discrete basis functions to 1, stimulates convexity.
        c[1:int_basis_count + 1] = 1

        # The regularization parameter. 1e-8 is good for the noiseless case,
        # replace by ≈1e-3 if there is noise.
        reg = 1e-8
        return cls(m, c, W, b, reg, Bounds(lb, ub))

    def phi(self, x):
        """
        Evaluates the basis functions at `x`.
        :param x: the decision variable values
        """
        z = np.matmul(self.W, x) + self.b
        return relu(z)

    def phi_deriv(self, x):
        """
        Evaluates the derivatives of the basis functions with respect to `x`.
        :param x: the decision variable values
        """
        z = np.matmul(self.W, x) + self.b
        return relu_deriv(z)

    def update(self, x, y):
        """
        Updates the model upon the observation of a new data point `(x, y)`.
        :param x: the decision variables values
        :param y: the objective function value `y(x)`
        """
        phi = self.phi(x)  # basis function values for k = 1, ..., m.

        # Recursive least squares algorithm
        v = np.matmul(self.P, phi)
        g = v / (1 + np.inner(phi, v))
        self.P -= np.outer(g, v)
        self.c += (y - np.inner(phi, self.c)) * g

    def g(self, x):
        """
        Evaluates the surrogate model at `x`.
        :param x: the decision variable values.
        """
        phi = self.phi(x)
        return np.inner(self.c, phi)

    def g_jac(self, x):
        """
        Evaluates the Jacobian of the model at `x`.
        :param x: the decision variable values.
        """
        phi_prime = self.phi_deriv(x)
        # Treat phi_prime as a column vector to scale the rows w_1, ..., w_m
        # of W by Φ'_1, ..., Φ'_m, respectively.
        W_scaled = phi_prime[:, None] * self.W
        return np.matmul(self.c, W_scaled)

    def minimum(self, x0):
        """
        Find a minimum of the surrogate model approximately.
        :param x0: the initial guess.
        """
        res = minimize(self.g, x0, method='L-BFGS-B', bounds=self.bounds, jac=self.g_jac,
                       options={'maxiter': 20, 'maxfun': 20})
        return res.x


def scale(y, y0, scale_threshold=1e-8):
    """
    Scale the objective with respect to the initial objective value,
    causing the optimum to lie below zero. This helps exploration and
    prevents the algorithm from getting stuck at the boundary.
    :param y: the objective function value.
    :param y0: the initial objective function value, `y(x0)`.
    :param scale_threshold: value under which no scaling is done
    """
    y -= y0
    if abs(y0) > scale_threshold:
        y /= abs(y0)
    return y


def inv_scale(y_scaled, y0, scale_threshold=1e-8):
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


def normalize_md(y_terms, scale_factors):
    denom = scale_factors[0] - scale_factors[1]
    denom[denom == 0] = 1

    return (y_terms - scale_factors[1]) / denom


def inv_norm_md(y_terms, scale_factors):
    difference = scale_factors[0] - scale_factors[1]

    return y_terms * difference + scale_factors[1]


def get_scale_factors(scaling_values):
    terms_max = np.max(scaling_values, axis=0)
    terms_min = np.min(scaling_values, axis=0)

    return terms_max, terms_min


class FunctionType(Enum):
    Sum = "sum"
    Rosenbrock = "rosenbrock"
    Rastrigin = "rastrigin"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return FunctionType[s]
        except KeyError:
            return s


def MVRSM_minimize(obj_func, x0, lb, ub, num_int, max_evals, rand_evals=0, obj_threshold=0.0, args=(),
                   stop_crit=None, rand_search_bias=0.5, log_times=False, scale_threshold=1e-8, f_obj_dim=1,
                   f_obj_tpe=FunctionType.Sum):
    """

        :param obj_func: objective function
        :param x0: Initial solution
        :param lb: lower bound
        :param ub: Upper bound
        :param num_int: number of integer variables
        :param max_evals: maximum number of evaluations
        :param rand_evals: number of random initial evaluations
        :param obj_threshold:
        :param args: extra arguments to be passed to obj_func appart from x
        :param stop_crit:
        :param rand_search_bias:
        :param log_times:
        :param scale_threshold: value under which no scaling is done
        :param f_obj_dim: if 1 objective function returns single float, otherwise a vector of size = f_obj_dim
        :param f_obj_tpe: objective function type (Sum, Rosenbrock,...)
        :return: best x, best y, SurrogateModel
        """
    d = len(x0)  # number of decision variables
    # assert num_int == d  # [GTEP] This is a modified version that only supports discrete variables.

    model = SurrogateModel.init(d, lb, ub, num_int)
    next_x = np.array(x0)  # candidate solution
    best_x = np.copy(next_x)  # best candidate solution found so far
    best_y = math.inf  # least objective function value found so far, equal to obj(best_x).

    scaling_values = np.zeros((rand_evals, f_obj_dim))
    x_rand_evals = np.zeros((rand_evals, len(x0)))

    # TODO: bucle for para iteraciones previas a escalado
    for i in range(rand_evals):
        if log_times:
            iter_start = time.time()
        if stop_crit is not None and stop_crit:
            break

        # Evaluate the objective and scale it.
        x = next_x.astype(float, copy=False)
        if f_obj_tpe == FunctionType.Sum:
            vals_unscaled = obj_func(x.astype(int), *args)  # [GTEP]: added astype(int)
        elif f_obj_tpe == FunctionType.Rosenbrock:
            vals_unscaled = x.copy()
        # Perform random search
        # next_x = np.random.binomial(1, rand_search_bias, num_int)  # [GTEP]
        next_x[0:num_int] = np.random.randint(lb[0:num_int], ub[0:num_int] + 1)  # integer variables
        next_x[num_int:d] = np.random.uniform(lb[num_int:d], ub[num_int:d])  # continuous variables

        scaling_values[i, :] = vals_unscaled
        x_rand_evals[i, :] = x
        # print(scaling_values)
        pass

    scale_factors = get_scale_factors(scaling_values)
    all_norm_data = np.zeros((max_evals - rand_evals, f_obj_dim))
    # Iteratively evaluate the objective, update the model, find the minimum of the model,
    # and explore the search space.
    for i in range(rand_evals, max_evals):

        # Evaluate the objective and scale it.
        x = next_x.astype(float, copy=False)
        if f_obj_tpe == FunctionType.Sum:
            values_orig = obj_func(x)  # [GTEP]: added astype(int)
            values_norm = normalize_md(values_orig, scale_factors)
            y_unscaled = np.sum(values_norm)
        elif f_obj_tpe == FunctionType.Rosenbrock:
            values_orig = x.copy()
            values_norm = normalize_md(values_orig, scale_factors)
            y_unscaled = obj_func(values_norm)

        all_norm_data[i - rand_evals:] = values_norm

        if i == rand_evals:
            y0 = y_unscaled
        # noinspection PyUnboundLocalVariable
        y = scale(y_unscaled, y0, scale_threshold=1e-8)

        # Keep track of the best found objective value and candidate solution so far.
        if y < best_y:
            best_x = np.copy(x)
            best_y = y
        print(values_norm, y)
        # Update the surrogate model
        if log_times:
            update_start = time.time()
        # TODO: ask if model should be updated with normalized x
        model.update(x, y)
        if log_times:
            # noinspection PyUnboundLocalVariable
            print(f'Update time: {time.time() - update_start}')

        # Minimize surrogate model
        if log_times:
            min_start = time.time()
        next_x = model.minimum(best_x)
        if log_times:
            # noinspection PyUnboundLocalVariable
            print(f'Minimization time: {time.time() - min_start}')

        # Round discrete variables to the nearest integer.
        next_x[0:num_int].round(out=next_x[0:num_int])

        # Just to be sure, clip the decision variables to the bounds.
        np.clip(next_x, lb, ub, out=next_x)

        # Check if minimizer really gives better result
        # if model.g(next_X) > model.g(x) + 1e-8:
        # print('Warning: minimization of the surrogate model yielded a worse solution')

        # Perform exploration to prevent the algorithm from getting stuck in local minima
        # of the surrogate model.

        # Skip exploration in the last iteration (to end at the exact minimum of the surrogate model).
        if i < max_evals - 2:
            # Randomly perturb the discrete variables. Each x_i is shifted n units
            # to the left (if dir is False) or to the right (if dir is True).
            # The bounds of each variable are respected.
            int_pert_prob = 1 / d  # probability that x_i is permuted
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

            # # Just to be sure, clip the decision variables to the bounds again.
            # np.clip(next_x, lb, ub, out=next_x)
            if stop_crit is not None:
                stop_crit.add(y_unscaled)

        if y_unscaled < obj_threshold:
            break

        if log_times:
            # noinspection PyUnboundLocalVariable
            print(f'Iteration time: {time.time() - iter_start}')

    # evaluate random search values
    normed_values = (scaling_values - scale_factors[1]) / (scale_factors[0] - scale_factors[1])
    all_norm_data = np.append(normed_values, all_norm_data, axis=0)

    if f_obj_tpe == FunctionType.Sum:
        fobj_values = np.sum(normed_values, axis=0)
    elif f_obj_tpe == FunctionType.Rosenbrock:
        fobj_values = rosenbrock_function(np.array([x for x in normed_values]))

    best_index = np.argmin(fobj_values)
    y_min = fobj_values[best_index]
    ymin_scale = scale(y_min, y0, scale_threshold)
    if ymin_scale < best_y:
        best_y = ymin_scale
        best_x = x_rand_evals[best_index, :]

    return best_x, inv_scale(best_y, y0, scale_threshold), model, all_norm_data, scale_factors


def get_x_y(x):
    costs = [10, 15, 20, 25, 30] * round(len(x) / 5)
    x_value = np.sum(x * costs[:len(x)])
    y_value = 1 / (np.sum(x) + 2)

    return x_value, y_value


def rosenbrock_function(array):
    a = 1.0
    b = 100.0

    x = array[0]
    y = array[1]

    return b * (y - x ** 2) ** 2 + (x - a) ** 2


def rastrigin_function(x):
    n = len(x)
    A = 10
    return A * n + np.sum(x ** 2 - A * np.cos(2 * np.pi * x), axis=1)


def plot_md_function(function, scalef):
    # Generate all possible binary vectors of length 3
    binary_vectors = np.array(list(product([0., 1.], repeat=20)))

    values_norm = normalize_md([function(binary_vector) for binary_vector in binary_vectors], scalef)
    x_values, y_values = zip(*values_norm)
    x_values = np.array(x_values)
    y_values = np.array(y_values)

    # Calculate z values
    z_values = y_values + x_values
    best_index = np.argmin(z_values)
    print(binary_vectors[best_index], z_values[best_index])

    # Create a 3D plot
    fig = plt.figure(1)
    ax = fig.add_subplot(111, projection='3d')

    # Downsample the data
    sample_indices = np.random.choice(len(x_values), size=min(1000, len(x_values)), replace=False)

    # Plot the results with smaller markers and alpha
    ax.scatter(x_values[sample_indices], y_values[sample_indices], z_values[sample_indices],
               s=5, alpha=0.5, label='Function Results')

    # Add labels
    ax.set_xlabel('Economic crit')
    ax.set_ylabel('Technical crit')
    ax.set_zlabel('Objective function')

    # Set a title
    plt.title('Results of Simple sum function')

    # Remove legend and grid for better performance
    ax.legend().set_visible(False)
    ax.grid(False)
    ax.set_xlim([0, 1.2])  # Adjust the limits as needed
    ax.set_ylim([0, 1.2])
    ax.set_zlim([0, 2])  # Adjust the limits as needed


def plot_MVRSM_data(data, f_obj_tpe):
    # Extract columns from the data
    x_values = data[:, 0]
    y_values = data[:, 1]
    if f_obj_tpe == FunctionType.Sum:
        z_values = x_values + y_values
    elif f_obj_tpe == FunctionType.Rosenbrock:
        z_values = np.array([rosenbrock_function(values) for values in data])

    # Create a 3D plot
    fig = plt.figure(2)
    ax = fig.add_subplot(111, projection='3d')

    # Plot the results
    ax.scatter(x_values, y_values, z_values, s=5, alpha=0.5, label='Data Points')

    # Add labels
    ax.set_xlabel('Economic crit')
    ax.set_ylabel('Technical crit')
    ax.set_zlabel('Objective function')

    # Add a legend
    ax.legend()

    # Show the plot
    plt.title('Results MVRSM')

    # Remove legend and grid for better performance
    ax.legend().set_visible(False)
    ax.grid(False)
    # ax.set_xlim([0, 1.2])  # Adjust the limits as needed
    # ax.set_ylim([0, 1.2])
    # ax.set_zlim([0, 2])  # Adjust the limits as needed


def plot_combined_functions(function, data, scalef):
    # Generate all possible binary vectors of length 3
    binary_vectors = np.array(list(product([0., 1.], repeat=20)))

    # Evaluate all function results
    values_nonorm = np.array([function(binary_vector) for binary_vector in binary_vectors])
    values_norm = normalize_md(values_nonorm, scalef)
    x_values1, y_values1 = zip(*values_norm)
    x_values1 = np.array(x_values1)
    y_values1 = np.array(y_values1)
    z_values1 = y_values1 + x_values1

    best_index1 = np.argmin(z_values1)
    print(binary_vectors[best_index1], z_values1[best_index1])

    # Downsample the data
    sample_indices = np.random.choice(len(x_values1), size=min(1000, len(x_values1)), replace=False)

    # Get MVRSM results
    x_values2 = data[:, 0]
    y_values2 = data[:, 1]
    z_values2 = x_values2 + y_values2

    # Create a 3D plot for normalization data
    fig = plt.figure(1)
    ax = fig.add_subplot(111, projection='3d')

    # Plot function data points
    ax.scatter(x_values1[sample_indices], y_values1[sample_indices], z_values1[sample_indices], c='blue',
               label='Function Results', s=5, alpha=0.2)

    # Function minimum point
    ax.scatter(x_values1[best_index1], y_values1[best_index1], z_values1[best_index1],
               c='red', label='Min Point', s=8)

    # Plot MVRSM evaluated points
    ax.scatter(x_values2, y_values2, z_values2, c='green', label='MVRSM results', s=10, alpha=0.8)

    # Get no-normalized points
    x_values1_nonorm, y_values1_nonorm = zip(*values_nonorm)
    x_values1_nonorm = np.array(x_values1_nonorm)
    y_values1_nonorm = np.array(y_values1_nonorm)
    z_values1_nonorm = y_values1_nonorm + x_values1_nonorm

    # Get MVRSM points no norm
    data_nonorm = inv_norm_md(data, scalef)
    z_nonorm = np.sum(data_nonorm, axis=1)

    # Add labels
    ax.set_xlabel('Economic crit')
    ax.set_ylabel('Technical crit')
    ax.set_zlabel('Objective function')
    ax.legend()
    ax.grid(False)
    plt.title('z=x+y normalized results')

    fig = plt.figure(2)
    ax = fig.add_subplot(111, projection='3d')

    # Plot function data points
    ax.scatter(x_values1_nonorm[sample_indices], y_values1_nonorm[sample_indices], z_values1_nonorm[sample_indices],
               c='blue', label='Function Results', s=5, alpha=0.5)

    # Plot MVRSM evaluated points
    ax.scatter(data_nonorm[:, 0], data_nonorm[:, 1], z_nonorm, c='green', label='MVRSM results', s=5, alpha=0.8)

    # Add labels
    ax.set_xlabel('Economic crit')
    ax.set_ylabel('Technical crit')
    ax.set_zlabel('Objective function')
    ax.grid(False)

    # Add a legend
    ax.legend()

    # Set axis limits and remove grid
    # ax.set_xlim([0, 1.3])
    # ax.set_ylim([0, 1.3])
    # ax.set_zlim([0, 2])
    ax.grid(False)

    # Show the plot
    plt.title('Simple sum no-normalized results')
    plt.show()


def plot_mesh(function, scalef, data, figure):
    x_values1 = np.arange(-200, 200, 10)
    y_values1 = np.arange(-1, 3, 0.1)

    # Create a meshgrid from x_values1 and y_values1
    x_mesh, y_mesh = np.meshgrid(x_values1, y_values1)

    # Compute the z values for every combination of x and y using the function
    z_values1 = function(np.array([x_mesh, y_mesh]))

    # Create a 3D plot
    fig = plt.figure(figure)
    ax = fig.add_subplot(111, projection='3d')

    # Plot the surface
    ax.plot_trisurf(x_mesh.flatten(), y_mesh.flatten(), z_values1.flatten(), cmap='viridis', linewidth=0.2,
                    antialiased=True)
    # Get unnorm data
    unorm_data = np.array([inv_norm_md(vals, scalef) for vals in data])
    z_data = np.array([function(value) for value in unorm_data])
    ax.scatter(unorm_data[:, 0], unorm_data[:, 1], z_data, color='red', s=50, label='MVRSM solution points')
    plt.title('No-normalization Rosenbreck')

    # now plot normalized figure
    values_norm = normalize_md(np.column_stack((x_values1, y_values1)), scalef)
    x_values1_norm, y_values1_norm = zip(*values_norm)
    x_values1_norm = np.array(x_values1_norm)
    y_values1_norm = np.array(y_values1_norm)

    # Create a meshgrid from x_values1_norm and y_values1_norm
    x_mesh_norm, y_mesh_norm = np.meshgrid(x_values1_norm, y_values1_norm)

    # Compute the z values for every combination of x and y using the function
    z_values1_norm = function(np.array([x_mesh_norm, y_mesh_norm]))

    # Find the minimum value and corresponding indices
    min_index = np.unravel_index(np.argmin(z_values1_norm), z_values1_norm.shape)
    min_x_norm, min_y_norm, min_z_norm = x_mesh_norm[min_index], y_mesh_norm[min_index], z_values1_norm[min_index]

    # Create a 3D plot
    fig = plt.figure(figure + 1)
    ax = fig.add_subplot(111, projection='3d')

    # Plot the surface
    ax.plot_trisurf(x_mesh_norm.flatten(), y_mesh_norm.flatten(), z_values1_norm.flatten(), cmap='viridis',
                    linewidth=0.1, antialiased=True)

    # Mark the minimum point on the normalized plot
    ax.scatter([min_x_norm], [min_y_norm], [min_z_norm], color='black', s=100, label='Minimum Point (Normalized)')

    # Get MVRSM solution points
    # nvals = normalize_md(mvrsm_x, scalef)
    # z_norm = function(nvals)
    # ax.scatter(nvals[0], nvals[1], z_norm, color='black', s=100, label='Minimum Point (MVRSM)')
    # print(f"Minimum (Normalized): x = {min_x_norm}, y = {min_y_norm}, z = {min_z_norm}")
    z_norm = np.array([function(value) for value in data])
    ax.scatter(data[:, 0], data[:, 1], z_norm, color='red', s=50, label='MVRSM solution points')
    plt.title('Normalization Rosenbreck')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('Rosenbreck')
    ax.legend()


if __name__ == '__main__':

    x0 = np.zeros(2)
    lb = np.array([-200, -1])
    ub = np.array([200, 3])
    num_int = 0
    max_evals = 100
    rand_evals = 20
    best_x, best_y, model, all_data, scalef = MVRSM_minimize(rosenbrock_function, x0, lb, ub, num_int, max_evals,
                                                             rand_evals, f_obj_dim=2, f_obj_tpe=FunctionType.Rosenbrock)

    # x0 = np.zeros(20)
    # lb = x0
    # ub = np.ones(20)
    # num_int = len(x0)
    # max_evals = 100
    # rand_evals = 20

    best_x, best_y, model, all_data, scalef = MVRSM_minimize(rosenbrock_function, x0, lb, ub, num_int, max_evals,
                                                             rand_evals, f_obj_dim=2, f_obj_tpe=FunctionType.Rosenbrock)
    print(best_x, best_y, scalef)

    # x_value, y_value = evaluate_all_points(binh_korn_function)

    # print(x_value, y_value)
    # plot_md_function(get_x_y, scalef)
    # plot_MVRSM_data(all_data, f_obj_tpe=FunctionType.Rosenbrock)
    # plot_combined_functions(get_x_y, all_data, scalef)
    plot_mesh(rosenbrock_function, scalef, data=all_data, figure=1)
    plt.show()
