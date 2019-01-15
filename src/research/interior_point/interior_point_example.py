import numpy as np
from scipy.sparse import csc_matrix, diags, vstack, hstack
from scipy.sparse.linalg import inv, spsolve


def simplex(A, c, b):

    nr = len(b)

    I = diags(np.ones(nr))

    # form tableau blocks
    t1 = vstack((c, A))
    t2 = vstack((np.zeros((1, nr)), I))
    t3 = vstack(())


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
    min: -6x1 - 14x2 + 0x3 + 0x4 + 0x5
    
    s.t:
    2x1 + 1x2 + 1x3          = 12
    2x1 + 3x2 +     1x4      = 15
    1x1 + 7x2 +          1x5 = 21
    
    x1 >=0, x2>=0, x3 >=0, x4>=0, x5>=0
    """

    c_ = np.array([-6, -14, 0, 0, 0])

    A_ = csc_matrix([[2, 1, 1, 0, 0],
                     [2, 3, 0, 1, 0],
                     [1, 7, 0, 0, 1]])

    b_ = np.array([12, 15, 21])

    x_0 = np.array([1, 1, 9, 10, 13])

    print('x0', x_0)

    # solve
    x = interior_point(A=A_, c=c_, x0=x_0, tol=1e-8)

    print()
    print('Solution:', x)
    print('Constraints mismatch:', A_ * x - b_)

