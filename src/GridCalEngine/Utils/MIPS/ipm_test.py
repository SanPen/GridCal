# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import numpy as np
import math
from scipy import sparse


def NLP_test(x, LAMBDA, PI):
    NV = 3
    NE = 1
    NI = 2

    f = -x[0] * x[1] - x[1] * x[2]
    fx = sparse.csc_matrix([[-x[1]], [-x[0] - x[2]], [-x[1]]])
    fxx = sparse.csc_matrix([[0, -1, 0], [-1, 0, -1], [0, -1, 0]])

    G = sparse.csc_matrix([x[0] - x[1] ** 2 - x[2]])
    Gx = sparse.csc_matrix([[1], [-2 * x[1]], [-1]])
    Gxx = PI.toarray()[0][0] * sparse.csc_matrix([[0, 0, 0], [0, -2, 0], [0, 0, 0]])

    H = sparse.csc_matrix([[x[0] ** 2 - x[1] ** 2 + x[2] ** 2 - 2], [x[0] ** 2 + x[1] ** 2 + x[2] ** 2 - 10]])
    Hx = sparse.csc_matrix([[2 * x[0], 2 * x[0]], [-2 * x[1], 2 * x[1]], [2 * x[2], 2 * x[2]]])
    Hxx = LAMBDA.toarray()[0][0] * sparse.csc_matrix([[2, 0, 0], [0, -2, 0], [0, 0, 2]])
    Hxx += LAMBDA.toarray()[0][1] * sparse.csc_matrix([[2, 0, 0], [0, 2, 0], [0, 0, 2]])

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx


def brock_eval(x, LAMBDA, PI):
    NV = 3
    NE = 0
    NI = 2

    f = 100 * (x[1] - x[0] ** 2) ** 2 + (1 - x[0]) ** 2
    fx = sparse.csc_matrix([[400 * (x[1] ** 3 - x[0] * x[1]) + 2 * x[0] - 2], [200 * (x[1] - x[0] ** 2)]])
    fxx = sparse.csc_matrix([[1200 * x[0] ** 2 - x[1] + 2, -400 * x[0]], [-400 * x[0], 200]])

    G = sparse.csc_matrix((0, 1))
    Gx = sparse.csc_matrix((NE, NV))
    Gxx = sparse.csc_matrix((NV, NV))

    H = sparse.csc_matrix((0, 1))
    Hx = sparse.csc_matrix((NI, NV))
    Hxx = sparse.csc_matrix((NV, NV))

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx



#def x2var(x):
 #   return vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf


#def var2x(vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf):
#    return np.r_[vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf]


def eval_f(x):

    fval = -x[0] * x[1] - x[1] * x[2]

    return np.array([fval])

def eval_g(x):

    gval = x[0] - x[1] **2 - x[2]

    return np.array([gval])

def eval_h(x):

    hval1 = x[0] ** 2 - x[1] ** 2 + x[2] ** 2 - 2
    hval2 = x[0] ** 2 + x[1] ** 2 + x[2] ** 2 - 10

    hval = np.r_[hval1, hval2]

    return hval


def calc_jacobian(func, x, arg = (), h=1e-5):
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.

    :param func: Vector-valued function (R^n -> R^m).
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a numpy array.
    """
    nx = len(x)
    f0 = func(x)
    jac = np.zeros((len(f0), nx))

    for i in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[i] += h
        f_plus_h = func(x_plus_h, *arg)
        jac[:, i] = (f_plus_h - f0) / h

    return jac


def calc_hessian(func, x, MULT, arg=(), h=1e-5):
    """
    Compute the Hessian matrix of `func` at `x` using finite differences.

    :param func: Scalar-valued function (R^n -> R).
    :param x: Point at which to evaluate the Hessian (numpy array).
    :param h: Small step for finite difference.
    :return: Hessian matrix as a numpy array.
    """
    n = len(x)
    const = len(func(x)) # For objective function, it will be passed as 1. The MULT will be 1 aswell.
    hessians = np.zeros((n,n))

    for eq in range(const):
        hessian = np.zeros((n,n))
        for i in range(n):
            for j in range(n):
                x_ijp = np.copy(x)
                x_ijp[i] += h
                x_ijp[j] += h
                f_ijp = func(x_ijp, *arg)[eq]

                x_ijm = np.copy(x)
                x_ijm[i] += h
                x_ijm[j] -= h
                f_ijm = func(x_ijm, *arg)[eq]


                x_jim = np.copy(x)
                x_jim[i] -= h
                x_jim[j] += h
                f_jim = func(x_jim, *arg)[eq]

                x_jjm = np.copy(x)
                x_jjm[i] -= h
                x_jjm[j] -= h
                f_jjm = func(x_jjm, *arg)[eq]

                a = MULT[eq] * (f_ijp - f_ijm - f_jim + f_jjm) / (4 * h ** 2)
                hessian[i, j] = a
        hessians += hessian
    return hessians


def evaluate_power_flow(x, PI=np.array([5]), LAMBDA=np.array([10,20]), h=1e-5):

    d_f = -x[0] * x[1] - x[1] * x[2]
    d_fx = sparse.csc_matrix([[-x[1]], [-x[0] - x[2]], [-x[1]]])
    d_fxx = sparse.csc_matrix([[0, -1, 0], [-1, 0, -1], [0, -1, 0]])

    d_G = sparse.csc_matrix([x[0] - x[1] ** 2 - x[2]])
    d_Gx = sparse.csc_matrix([[1], [-2 * x[1]], [-1]])
    d_Gxx = PI[0] * sparse.csc_matrix([[0, 0, 0], [0, -2, 0], [0, 0, 0]])

    d_H = sparse.csc_matrix([[x[0] ** 2 - x[1] ** 2 + x[2] ** 2 - 2], [x[0] ** 2 + x[1] ** 2 + x[2] ** 2 - 10]])
    d_Hx = sparse.csc_matrix([[2 * x[0], 2 * x[0]], [-2 * x[1], 2 * x[1]], [2 * x[2], 2 * x[2]]])
    d_Hxx = LAMBDA[0] * sparse.csc_matrix([[2, 0, 0], [0, -2, 0], [0, 0, 2]])
    d_Hxx += LAMBDA[1] * sparse.csc_matrix([[2, 0, 0], [0, 2, 0], [0, 0, 2]])

    f = eval_f(x=x)
    G = eval_g(x=x)
    H = eval_h(x=x)

    fx = calc_jacobian(func=eval_f, x=x, h=h)
    Gx = calc_jacobian(func=eval_g, x=x, h=h)
    Hx = calc_jacobian(func=eval_h, x=x, h=h)

    fxx = calc_hessian(func=eval_f, x=x, MULT=np.array([1]), h=h)
    Gxx = calc_hessian(func=eval_g, x=x, MULT=PI, h=h)
    Hxx = calc_hessian(func=eval_h, x=x, MULT=LAMBDA, h=h)

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx



if __name__ == '__main__':
    evaluate_power_flow(x=np.array([1.,1.,1.]))










