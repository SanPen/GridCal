import cvxopt
import numpy as np


def cvxopt_solve_minmax(n, a, B, x_min=-42, x_max=42, solver=None):
    """

    :param n:
    :param a:
    :param B:
    :param x_min:
    :param x_max:
    :param solver:
    :return:
    """
    c = np.hstack([np.zeros(n), [1]])

    # cvxopt constraint format: G * x <= h
    # first,  a + B * x[0:n] <= x[n]
    G1 = np.zeros((n, n + 1))
    G1[0:n, 0:n] = B
    G1[:, n] = -np.ones(n)
    h1 = -a

    # then, x_min <= x <= x_max
    x_min = x_min * np.ones(n)
    x_max = x_max * np.ones(n)
    G2 = np.vstack([np.hstack([np.eye(n), np.zeros((n, 1))]),
                    np.hstack([-np.eye(n), np.zeros((n, 1))])])
    h2 = np.hstack([x_max, -x_min])

    c = cvxopt.matrix(c)
    G = cvxopt.matrix(np.vstack([G1, G2]))
    h = cvxopt.matrix(np.hstack([h1, h2]))
    sol = cvxopt.solvers.lp(c, G, h, solver=solver)
    return np.array(sol['x']).reshape((n + 1,))
