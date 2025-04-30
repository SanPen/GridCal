import numpy as np
import sympy as sp
from sympy import symbols, Matrix

def clean_matrix(matrix, threshold=1e-10):
    cleaned_matrix = []
    for row in matrix:
        cleaned_row = []
        for expr in row:
            cleaned_expr = 0
            for term in expr.as_ordered_terms():
                coeff, symbol = term.as_coeff_Mul()
                if abs(coeff.evalf()) >= threshold:
                    cleaned_expr += coeff * symbol
            cleaned_row.append(cleaned_expr)
        cleaned_matrix.append(cleaned_row)
    return sp.Matrix(cleaned_matrix)

Cu = np.array([
    [1, 0, 0, 0, 0, 0],
    [0, 0, 0, 1, 0, 0],
    [0, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 0],
    [0, 0, 1, 0, 0, 0],
    [0, 0, 0, 0, 0, 1],
])

Ci = np.array([
    [1, 0, 0, 0, 0, 0],
    [0, 0, 1, 0, 0, 0],
    [0, 0, 0, 0, 1, 0],
    [0, 1, 0, 0, 0, 0],
    [0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 0, 1],
])

yff = symbols('yff')
yft = symbols('yft')
ytf = symbols('ytf')
ytt = symbols('ytt')

Y_2x2 = Matrix([
    [yff, yft],
    [ytf, ytt]
])

Yprimitive = np.zeros((6, 6), dtype=object)
Yprimitive[0:2,0:2] = Y_2x2
Yprimitive[2:4,2:4] = Y_2x2
Yprimitive[4:6,4:6] = Y_2x2

Ytrafo = Ci @ Yprimitive @ Cu

cleaned = clean_matrix(Ytrafo, threshold=1e-10)
sp.pprint(cleaned)

"""
Ci = np.array([
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
])
"""