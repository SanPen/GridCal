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
    Gx = sparse.csc_matrix([[1],[-2 * x[1]], [-1]])
    Gxx = PI.toarray()[0][0] * sparse.csc_matrix([[0, 0, 0], [0, -2, 0],[0, 0, 0]])

    H = sparse.csc_matrix([[x[0] ** 2 - x[1] ** 2 + x[2] ** 2 - 2], [x[0] ** 2 + x[1] ** 2 + x[2] ** 2 - 10]])
    Hx = sparse.csc_matrix([[2 * x[0], 2 * x[0]],[-2 * x[1], 2* x[1]],[2 * x[2], 2 * x[2]]])
    Hxx = LAMBDA.toarray()[0][0] * sparse.csc_matrix([[2, 0, 0], [0, -2, 0], [0, 0, 2]])
    Hxx += LAMBDA.toarray()[0][1] * sparse.csc_matrix([[2, 0, 0], [0, 2, 0], [0, 0, 2]])

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx





def brock_eval(x):

    NV = 3
    NE = 0
    NI = 2

    f = 100 * (x[1] - x[0] ** 2) ** 2 + (1 - x[0]) ** 2
    fx = sparse.csc_matrix([[400 * (x[1] ** 3 - x[0] * x[1]) + 2 * x[0] -  2],[ 200 * (x[1] - x[0]**2 )]])
    fxx =sparse.csc_matrix([[1200 * x[0]**2 - x[1] + 2, -400 * x[0]],[-400 * x[0], 200]])

    G = sparse.csc_matrix((0,1))
    Gx = sparse.csc_matrix((NE, NV))
    Gxx = sparse.csc_matrix((NV, NV))

    H = sparse.csc_matrix((0, 1))
    Hx = sparse.csc_matrix((NI, NV))
    Hxx = sparse.csc_matrix((NV, NV))

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx

