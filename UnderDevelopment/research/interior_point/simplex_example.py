import numpy as np
from scipy.sparse import csc_matrix, diags, vstack, hstack
from scipy.sparse.linalg import inv, spsolve


def simplex(A, c, b):
    nr = len(b)
    nv = len(c)
    I = diags(np.ones(nr))

    bi = b.copy()

    # form tableau blocks
    M = hstack((A, I))

    x = np.r_[np.zeros(nv), b]

    fx = np.r_[c, np.zeros(nr)]

    # pick the most negative of the variables in fx
    var_idx = np.argmin(fx)
    xj = fx[var_idx]

    bi = bi / xj

    return 0


def interior_point(A, c, x0, tol=1e-6, max_iter=100):
    """
    Interior point solver for linear systems
    Source: Computational methods for electric power systems (3rd Ed.) - Mariesa L- Crow  (CRC Press)
    Args:
        A: Restrictions matrix
        c: Objective function coefficients
        x0: Feasible solution
        tol: Tolerance
        max_iter: Maximum number of iterations
    Returns: Optimal solution x
    """
    n = len(c)

    e = np.ones(n)

    I = diags(e)

    x = x0.copy()

    x_prev = x0.copy()

    converged = False

    iterations = 0

    last_f = 1e20

    while not converged and iterations < max_iter:

        D = diags(x)

        Ap = A * D

        cp = D * c

        # Pp = I - Ap.transpose() * inv(Ap * Ap.transpose()) * Ap

        Pp = I - Ap.transpose() * spsolve(Ap * Ap.transpose(), Ap)  # avoid using matrix inversions...

        p0 = - Pp * cp

        alpha = 0.9

        theta = - p0.min()

        xp = e + (alpha / theta) * p0

        x = D * xp

        f = c.dot(x)

        # back track
        b_iter = 0
        while f > last_f and b_iter < 10:
            alpha *= 0.25

            xp = e + (alpha / theta) * p0

            x = D * xp

            f = c.dot(x)

            b_iter += 1

            print('\talpha:', alpha)

        error = np.linalg.norm(x - x_prev, np.inf)

        converged = error < tol

        x_prev = x.copy()

        last_f = f

        iterations += 1

        print('f:', f, '\terror:', error)

    return x


if __name__ == '__main__':
    """
    Problem:
    min: -6x1 - 14x2

    s.t:
    2x1 + 1x2 <= 12
    2x1 + 3x2 <= 15
    1x1 + 7x2 <= 21

    x1 >=0, x2>=0
    """

    c_ = np.array([-6, -14])

    A_ = csc_matrix([[2, 1],
                     [2, 3],
                     [1, 7]])

    b_ = np.array([12, 15, 21])

    # solve
    x = simplex(A=A_, c=c_, b=b_)

    print()
    print('Solution:', x)
    print('Constraints mismatch:', A_ * x - b_)

