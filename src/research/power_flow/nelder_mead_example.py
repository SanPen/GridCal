import copy

"""
Pure Python/Numpy implementation of the Nelder-Mead algorithm from
https://github.com/alxsoares/nelder-mead/blob/master/nelder_mead.py
Reference: https://en.wikipedia.org/wiki/Nelder%E2%80%93Mead_method

transformations from https://github.com/alexblaessle/constrNMPy/blob/master/constrNMPy/constrNMPy.py
"""


def transform_x(x, LB, UB, offset=1E-20):
    """Transforms ``x`` into constrained form, obeying upper bounds ``UB`` and lower bounds ``LB``.
    .. note:: Will add tiny offset to LB if ``LB[i]=0``, to avoid singularities.
    Idea taken from http://www.mathworks.com/matlabcentral/fileexchange/8277-fminsearchbnd--fminsearchcon
    Args:
        x (numpy.ndarray): Input vector.
        LB (numpy.ndarray): Lower bounds.
        UB (numpy.ndarray): Upper bounds.
    Keyword Args:
        offset (float): Small offset added to lower bound if LB=0.
    Returns:
        numpy.ndarray: Transformed x-values.
    """

    # Make sure everything is float
    x = np.asarray(x, dtype=np.float64)

    # Add offset if necessary to avoid singularities
    for l in LB:
        if l == 0:
            l = l + offset

    # Determine number of parameters to be fitted
    nparams = len(x)

    # Make empty vector
    xtrans = np.zeros(np.shape(x))

    # k allows some variables to be fixed, thus dropped from the
    # optimization.
    k = 0

    for i in range(nparams):

        # Upper bound only
        if UB[i] is not None and LB[i] is None:

            xtrans[i] = UB[i] - x[k] ** 2
            k = k + 1

        # Lower bound only
        elif UB[i] is None and LB[i] is not None:

            xtrans[i] = LB[i] + x[k] ** 2
            k = k + 1

        # Both bounds
        elif UB[i] is not None and LB[i] is not None:

            xtrans[i] = (np.sin(x[k]) + 1.) / 2. * (UB[i] - LB[i]) + LB[i]
            xtrans[i] = max([LB[i], min([UB[i], xtrans[i]])])
            k = k + 1

        # No bounds
        elif UB[i] is None and LB[i] is None:

            xtrans[i] = x[k]
            k = k + 1

        # NOTE: The original file has here another case for fixed variable. We might need to add this here!!!

    return np.array(xtrans)


def transform_x0(x0, LB, UB):
    r"""Transforms ``x0`` into constrained form, obeying upper bounds ``UB`` and lower bounds ``LB``.
    Idea taken from http://www.mathworks.com/matlabcentral/fileexchange/8277-fminsearchbnd--fminsearchcon
    Args:
        x0 (numpy.ndarray): Input vector.
        LB (numpy.ndarray): Lower bounds.
        UB (numpy.ndarray): Upper bounds.
    Returns:
        numpy.ndarray: Transformed x-values.
    """

    # Turn into list
    x0u = list(x0)

    k = 0
    for i in range(len(x0)):

        # Upper bound only
        if UB[i] is not None and LB[i] is None:
            if UB[i] <= x0[i]:
                x0u[k] = 0
            else:
                x0u[k] = np.sqrt(UB[i] - x0[i])
            k = k + 1

        # Lower bound only
        elif UB[i] is None and LB[i] is not None:
            if LB[i] >= x0[i]:
                x0u[k] = 0
            else:
                x0u[k] = np.sqrt(x0[i] - LB[i])
            k = k + 1

        # Both bounds
        elif UB[i] is not None and LB[i] is not None:
            if UB[i] <= x0[i]:
                x0u[k] = np.pi / 2
            elif LB[i] >= x0[i]:
                x0u[k] = -np.pi / 2
            else:
                x0u[k] = 2 * (x0[i] - LB[i]) / (UB[i] - LB[i]) - 1;
                # shift by 2*pi to avoid problems at zero in fmin otherwise, the initial simplex is vanishingly small
                x0u[k] = 2 * np.pi + np.arcsin(max([-1, min(1, x0u[k])]));
            k = k + 1

        # No bounds
        elif UB[i] is None and LB[i] is None:
            x0u[k] = x0[i]
            k = k + 1

    return np.array(x0u)


def nelder_mead(objective_function, x_start, LB, UB,
                step=0.1, no_improve_thr=10e-6,
                no_improv_break=10, max_iter=0,
                alpha=1., gamma=2., rho=-0.5, sigma=0.5):
    """
        @param f (function): function to optimize, must return a scalar score
            and operate over a numpy array of the same dimensions as x_start
        @param x_start (numpy array): initial position
        @param step (float): look-around radius in initial step
        @no_improv_thr,  no_improv_break (float, int): break after no_improv_break iterations with
            an improvement lower than no_improv_thr
        @max_iter (int): always break after this number of iterations.
            Set it to 0 to loop indefinitely.
        @alpha, gamma, rho, sigma (floats): parameters of the algorithm
            (see Wikipedia page for reference)
        return: tuple (best parameter array, best score)
    """

    # init
    dim = len(x_start)
    prev_best = objective_function(transform_x(x_start, LB, UB))
    no_improv = 0
    res = [[x_start, prev_best]]

    for i in range(dim):
        x = copy.copy(x_start)
        x[i] = x[i] + step
        score = objective_function(transform_x(x, LB, UB))
        res.append([x, score])

    # simplex iter
    iters = 0
    while 1:
        # order
        res.sort(key=lambda x: x[1])
        best = res[0][1]

        # break after max_iter
        if max_iter and iters >= max_iter:
            return res[0]
        iters += 1

        # break after no_improv_break iterations with no improvement
        print('...best so far:', best)

        if best < prev_best - no_improve_thr:
            no_improv = 0
            prev_best = best
        else:
            no_improv += 1

        if no_improv >= no_improv_break:
            return res[0]

        # centroid
        x0 = [0.] * dim
        for tup in res[:-1]:
            for i, c in enumerate(tup[0]):
                x0[i] += c / (len(res)-1)

        # reflection
        xr = x0 + alpha*(x0 - res[-1][0])
        rscore = objective_function(transform_x(xr, LB, UB))
        if res[0][1] <= rscore < res[-2][1]:
            del res[-1]
            res.append([xr, rscore])
            continue

        # expansion
        if rscore < res[0][1]:
            xe = x0 + gamma*(x0 - res[-1][0])
            escore = objective_function(transform_x(xe, LB, UB))
            if escore < rscore:
                del res[-1]
                res.append([xe, escore])
                continue
            else:
                del res[-1]
                res.append([xr, rscore])
                continue

        # contraction
        xc = x0 + rho*(x0 - res[-1][0])
        cscore = objective_function(transform_x(xc, LB, UB))
        if cscore < res[-1][1]:
            del res[-1]
            res.append([xc, cscore])
            continue

        # reduction
        x1 = res[0][0]
        nres = []
        for tup in res:
            redx = x1 + sigma*(tup[0] - x1)
            score = objective_function(transform_x(redx, LB, UB))
            nres.append([redx, score])
        res = nres


if __name__ == "__main__":
    # test
    import math
    import numpy as np

    def f(x):
        return math.sin(x[0]) * math.cos(x[1]) * (1. / (abs(x[2]) + 1))

    x0 = np.array([0., 0., 0.])
    LB = np.ones_like(x0) * -1
    UB = np.ones_like(x0) * 1
    result = nelder_mead(f, x0, LB, UB)

    print('Result')
    print(result)