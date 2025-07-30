from sympy import symbols, Matrix
import numpy as np
import sympy as sp
np.set_printoptions(linewidth=20000, precision=3, suppress=True)

def clean_matrix(matrix, threshold=1e-10, decimals=3):
    cleaned_matrix = []
    for row in matrix:
        cleaned_row = []
        for expr in row:
            cleaned_expr = 0
            for term in expr.as_ordered_terms():
                coeff, symbol = term.as_coeff_Mul()
                if abs(coeff.evalf()) >= threshold:
                    rounded_coeff = sp.N(coeff, decimals)
                    cleaned_expr += rounded_coeff * symbol
            cleaned_row.append(sp.N(cleaned_expr, decimals))
        cleaned_matrix.append(cleaned_row)
    return sp.Matrix(cleaned_matrix)

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

connexion = 'Zz'

Cu = np.zeros((6, 6))
Ci = np.zeros((6, 6))

if connexion == 'Yy':
    Cu[0, 0] = 1
    Cu[1, 3] = 1
    Cu[2, 1] = 1
    Cu[3, 4] = 1
    Cu[4, 2] = 1
    Cu[5, 5] = 1
    Ci[0, 0] = 1
    Ci[1, 2] = 1
    Ci[2, 4] = 1
    Ci[3, 1] = 1
    Ci[4, 3] = 1
    Ci[5, 5] = 1
    Ytrafo = Ci @ Yprimitive @ Cu

elif connexion == 'Dd':
    Cu[0,0] = 1 / np.sqrt(3)
    Cu[0,1] = -1 / np.sqrt(3)
    Cu[1,3] = 1 / np.sqrt(3)
    Cu[1,4] = -1 / np.sqrt(3)
    Cu[2,1] = 1 / np.sqrt(3)
    Cu[2,2] = -1 / np.sqrt(3)
    Cu[3,4] = 1 / np.sqrt(3)
    Cu[3,5] = -1 / np.sqrt(3)
    Cu[4,2] = 1 / np.sqrt(3)
    Cu[4,0] = -1 / np.sqrt(3)
    Cu[5,5] = 1 / np.sqrt(3)
    Cu[5,3] = -1 / np.sqrt(3)
    Ci[0,0] = 1 / np.sqrt(3)
    Ci[0,4] = -1 / np.sqrt(3)
    Ci[1,0] = -1 / np.sqrt(3)
    Ci[1,2] = 1 / np.sqrt(3)
    Ci[2,2] = -1 / np.sqrt(3)
    Ci[2,4] = 1 / np.sqrt(3)
    Ci[3,1] = 1 / np.sqrt(3)
    Ci[3,5] = -1 / np.sqrt(3)
    Ci[4,3] = 1 / np.sqrt(3)
    Ci[4,1] = -1 / np.sqrt(3)
    Ci[5,5] = 1 / np.sqrt(3)
    Ci[5,3] = -1 / np.sqrt(3)
    Ytrafo = Ci @ Yprimitive @ Cu

elif connexion == 'Yd':
    Cu[0,0] = 1 # U1 = UA
    Cu[1,3] = 1 / np.sqrt(3) # U2 = Ua - Ub
    Cu[1,4] = -1 / np.sqrt(3)
    Cu[2,1] = 1 # U3 = UB
    Cu[3,4] = 1 / np.sqrt(3) # U4 = Ub - Uc
    Cu[3,5] = -1 / np.sqrt(3)
    Cu[4,2] = 1 # U5 = UC
    Cu[5,5] = 1 / np.sqrt(3) # U6 = Uc - Ua
    Cu[5,3] = -1 / np.sqrt(3)
    Ci[0,0] = 1 # IA = I1
    Ci[1,2] = 1 # IB = I3
    Ci[2,4] = 1 # IC = I5
    Ci[3,1] = 1 / np.sqrt(3) # Ia = I2 - I6
    Ci[3,5] = -1 / np.sqrt(3)
    Ci[4,3] = 1 / np.sqrt(3) # Ib = I4 - I2
    Ci[4,1] = -1 / np.sqrt(3)
    Ci[5,5] = 1 / np.sqrt(3) # Ic = I6 - I4
    Ci[5,3] = -1 / np.sqrt(3)
    Ytrafo = Ci @ Yprimitive @ Cu

elif connexion == 'Dy':
    Cu[0, 0] = 1 / np.sqrt(3) # U1 = UA - UB
    Cu[0, 1] = -1 / np.sqrt(3)
    Cu[1, 3] = 1 # U2 = Ua
    Cu[2, 1] = 1 / np.sqrt(3)  # U3 = UB - UC
    Cu[2, 2] = -1 / np.sqrt(3)
    Cu[3, 4] = 1  # U4 = Ub
    Cu[4, 2] = 1 / np.sqrt(3)  # U5 = UC - UA
    Cu[4, 0] = -1 / np.sqrt(3)
    Cu[5, 5] = 1  # U6 = Uc
    Ci[0, 0] = 1 / np.sqrt(3) # IA = I1 - I5
    Ci[0, 4] = -1 / np.sqrt(3)
    Ci[1, 2] = 1 / np.sqrt(3)  # IB = I3 - I1
    Ci[1, 0] = -1 / np.sqrt(3)
    Ci[2, 4] = 1 / np.sqrt(3)  # IC = I5 - I3
    Ci[2, 2] = -1 / np.sqrt(3)
    Ci[3, 1] = 1 # Ia = I2
    Ci[4, 3] = 1  # Ib = I4
    Ci[5, 5] = 1  # Ic = I6
    Ytrafo = Ci @ Yprimitive @ Cu

elif connexion == 'Yz':
    Yprimitive = np.zeros((12, 12), dtype=object)
    Yprimitive[0:2, 0:2] = Y_2x2 * 2
    Yprimitive[2:4, 2:4] = Y_2x2 * 2
    Yprimitive[4:6, 4:6] = Y_2x2 * 2
    Yprimitive[6:8, 6:8] = Y_2x2 * 2
    Yprimitive[8:10, 8:10] = Y_2x2 * 2
    Yprimitive[10:12, 10:12] = Y_2x2 * 2
    Cu = np.zeros((6, 12))
    Cu[0, 0] = 1
    Cu[0, 2] = 1
    Cu[1, 4] = 1
    Cu[1, 6] = 1
    Cu[2, 8] = 1
    Cu[2, 10] = 1
    Cu[3, 1] = 1
    Cu[3, 7] = -1
    Cu[4, 5] = 1
    Cu[4, 11] = -1
    Cu[5, 9] = 1
    Cu[5, 3] = -1
    Ci = np.zeros((12, 6))
    Ci[0, 0] = 1
    Ci[1, 3] = 1
    Ci[2, 0] = 1
    Ci[3, 5] = -1
    Ci[4, 1] = 1
    Ci[5, 4] = 1
    Ci[6, 1] = 1
    Ci[7, 3] = -1
    Ci[8, 2] = 1
    Ci[9, 5] = 1
    Ci[10, 2] = 1
    Ci[11, 4] = -1
    Ytrafo = np.linalg.pinv(Ci) @ Yprimitive @ np.linalg.pinv(Cu)

elif connexion == 'Zy':
    Yprimitive = np.zeros((12, 12), dtype=object)
    Yprimitive[0:2, 0:2] = Y_2x2 * 2
    Yprimitive[2:4, 2:4] = Y_2x2 * 2
    Yprimitive[4:6, 4:6] = Y_2x2 * 2
    Yprimitive[6:8, 6:8] = Y_2x2 * 2
    Yprimitive[8:10, 8:10] = Y_2x2 * 2
    Yprimitive[10:12, 10:12] = Y_2x2 * 2
    Cu = np.zeros((6, 12))
    Cu[0, 0] = 1
    Cu[0, 6] = -1
    Cu[1, 4] = 1
    Cu[1, 10] = -1
    Cu[2, 8] = 1
    Cu[2, 2] = -1
    Cu[3, 1] = 1
    Cu[3, 3] = 1
    Cu[4, 5] = 1
    Cu[4, 7] = 1
    Cu[5, 9] = 1
    Cu[5, 11] = 1
    Ci = np.zeros((12, 6))
    Ci[0, 0] = 1
    Ci[1, 3] = 1
    Ci[2, 2] = -1
    Ci[3, 3] = 1
    Ci[4, 1] = 1
    Ci[5, 4] = 1
    Ci[6, 0] = -1
    Ci[7, 4] = 1
    Ci[8, 2] = 1
    Ci[9, 5] = 1
    Ci[10, 1] = -1
    Ci[11, 5] = 1
    Ytrafo = np.linalg.pinv(Ci) @ Yprimitive @ np.linalg.pinv(Cu)

elif connexion == 'Zz':
    Yprimitive = np.zeros((12, 12), dtype=object)
    Yprimitive[0:2, 0:2] = Y_2x2 * 2
    Yprimitive[2:4, 2:4] = Y_2x2 * 2
    Yprimitive[4:6, 4:6] = Y_2x2 * 2
    Yprimitive[6:8, 6:8] = Y_2x2 * 2
    Yprimitive[8:10, 8:10] = Y_2x2 * 2
    Yprimitive[10:12, 10:12] = Y_2x2 * 2
    Cu = np.zeros((6, 12))
    Cu[0, 0] = 1
    Cu[0, 6] = -1
    Cu[1, 4] = 1
    Cu[1, 10] = -1
    Cu[2, 8] = 1
    Cu[2, 2] = -1
    Cu[3, 1] = 1
    Cu[3, 7] = -1
    Cu[4, 5] = 1
    Cu[4, 11] = -1
    Cu[5, 9] = 1
    Cu[5, 3] = -1
    Ci = np.zeros((12, 6))
    Ci[0, 0] = 1
    Ci[1, 3] = 1
    Ci[2, 2] = -1
    Ci[3, 5] = -1
    Ci[4, 1] = 1
    Ci[5, 4] = 1
    Ci[6, 0] = -1
    Ci[7, 3] = -1
    Ci[8, 2] = 1
    Ci[9, 5] = 1
    Ci[10, 1] = -1
    Ci[11, 4] = -1
    Ytrafo = np.linalg.pinv(Ci) @ Yprimitive @ np.linalg.pinv(Cu)

elif connexion == 'Dz':
    Yprimitive = np.zeros((12, 12), dtype=object)
    Yprimitive[0:2, 0:2] = Y_2x2 * 2
    Yprimitive[2:4, 2:4] = Y_2x2 * 2
    Yprimitive[4:6, 4:6] = Y_2x2 * 2
    Yprimitive[6:8, 6:8] = Y_2x2 * 2
    Yprimitive[8:10, 8:10] = Y_2x2 * 2
    Yprimitive[10:12, 10:12] = Y_2x2 * 2
    Cu_left = np.zeros((6, 6))
    Cu_left[0, 0] = 1 / np.sqrt(3)
    Cu_left[0, 1] = -1 / np.sqrt(3)
    Cu_left[1, 1] = 1 / np.sqrt(3)
    Cu_left[1, 2] = -1 / np.sqrt(3)
    Cu_left[2, 2] = 1 / np.sqrt(3)
    Cu_left[2, 0] = -1 / np.sqrt(3)
    Cu_left[3, 3] = 1
    Cu_left[4, 4] = 1
    Cu_left[5, 5] = 1
    Cu_right = np.zeros((6, 12))
    Cu_right[0, 0] = 1
    Cu_right[0, 2] = 1
    Cu_right[1, 4] = 1
    Cu_right[1, 6] = 1
    Cu_right[2, 8] = 1
    Cu_right[2, 10] = 1
    Cu_right[3, 1] = 1
    Cu_right[3, 7] = -1
    Cu_right[4, 5] = 1
    Cu_right[4, 11] = -1
    Cu_right[5, 9] = 1
    Cu_right[5, 3] = -1
    Ci_left = np.zeros((12, 12))
    Ci_left[0, 0] = 1
    Ci_left[0, 8] = -1
    Ci_left[1, 2] = 1
    Ci_left[1, 10] = -1
    Ci_left[2, 4] = 1
    Ci_left[2, 0] = -1
    Ci_left[3, 6] = 1
    Ci_left[3, 2] = -1
    Ci_left[4, 8] = 1
    Ci_left[4, 4] = -1
    Ci_left[5, 10] = 1
    Ci_left[5, 6] = -1
    Ci_left[6, 1] = 1
    Ci_left[7, 3] = 1
    Ci_left[8, 5] = 1
    Ci_left[9, 7] = 1
    Ci_left[10, 9] = 1
    Ci_left[11, 11] = 1
    Ci_right = np.zeros((12, 6))
    Ci_right[0, 0] = 1 * np.sqrt(3)
    Ci_right[1, 0] = 1 * np.sqrt(3)
    Ci_right[2, 1] = 1 * np.sqrt(3)
    Ci_right[3, 1] = 1 * np.sqrt(3)
    Ci_right[4, 2] = 1 * np.sqrt(3)
    Ci_right[5, 2] = 1 * np.sqrt(3)
    Ci_right[6, 3] = 1
    Ci_right[7, 5] = -1
    Ci_right[8, 4] = 1
    Ci_right[9, 3] = -1
    Ci_right[10, 5] = 1
    Ci_right[11, 4] = -1
    Cu = np.linalg.pinv(Cu_left) @ Cu_right
    Ci = np.linalg.pinv(Ci_left) @ Ci_right
    Ytrafo = np.linalg.pinv(Ci) @ Yprimitive @ np.linalg.pinv(Cu)

elif connexion == 'Zd':
    Yprimitive = np.zeros((12, 12), dtype=object)
    Yprimitive[0:2, 0:2] = Y_2x2 * 2
    Yprimitive[2:4, 2:4] = Y_2x2 * 2
    Yprimitive[4:6, 4:6] = Y_2x2 * 2
    Yprimitive[6:8, 6:8] = Y_2x2 * 2
    Yprimitive[8:10, 8:10] = Y_2x2 * 2
    Yprimitive[10:12, 10:12] = Y_2x2 * 2
    Cu_left = np.zeros((6, 6))
    Cu_left[0, 0] = 1
    Cu_left[1, 1] = 1
    Cu_left[2, 2] = 1
    Cu_left[3, 3] = 1 / np.sqrt(3)
    Cu_left[3, 4] = -1 / np.sqrt(3)
    Cu_left[4, 4] = 1 / np.sqrt(3)
    Cu_left[4, 5] = -1 / np.sqrt(3)
    Cu_left[5, 3] = -1 / np.sqrt(3)
    Cu_left[5, 5] = 1 / np.sqrt(3)
    Cu_right = np.zeros((6, 12))
    Cu_right[0, 0] = 1
    Cu_right[0, 6] = -1
    Cu_right[1, 4] = 1
    Cu_right[1, 10] = -1
    Cu_right[2, 8] = 1
    Cu_right[2, 2] = -1
    Cu_right[3, 1] = 1
    Cu_right[3, 3] = 1
    Cu_right[4, 5] = 1
    Cu_right[4, 7] = 1
    Cu_right[5, 9] = 1
    Cu_right[5, 11] = 1
    Ci_left = np.zeros((12, 12))
    Ci_left[0, 0] = 1
    Ci_left[1, 2] = 1
    Ci_left[2, 4] = 1
    Ci_left[3, 6] = 1
    Ci_left[4, 8] = 1
    Ci_left[5, 10] = 1
    Ci_left[6, 1] = 1
    Ci_left[6, 9] = -1
    Ci_left[7, 3] = 1
    Ci_left[7, 11] = -1
    Ci_left[8, 5] = 1
    Ci_left[8, 1] = -1
    Ci_left[9, 7] = 1
    Ci_left[9, 3] = -1
    Ci_left[10, 9] = 1
    Ci_left[10, 5] = -1
    Ci_left[11, 11] = 1
    Ci_left[11, 7] = -1
    Ci_right = np.zeros((12, 6))
    Ci_right[0, 0] = 1
    Ci_right[1, 2] = -1
    Ci_right[2, 1] = 1
    Ci_right[3, 0] = -1
    Ci_right[4, 2] = 1
    Ci_right[5, 1] = -1
    Ci_right[6, 3] = 1 * np.sqrt(3)
    Ci_right[7, 3] = 1 * np.sqrt(3)
    Ci_right[8, 4] = 1 * np.sqrt(3)
    Ci_right[9, 4] = 1 * np.sqrt(3)
    Ci_right[10, 5] = 1 * np.sqrt(3)
    Ci_right[11, 5] = 1 * np.sqrt(3)
    Cu = np.linalg.pinv(Cu_left) @ Cu_right
    Ci = np.linalg.pinv(Ci_left) @ Ci_right
    Ytrafo = np.linalg.pinv(Ci) @ Yprimitive @ np.linalg.pinv(Cu)

print(Cu)
print()
print(Ci)
print()

cleaned = clean_matrix(Ytrafo, threshold=1e-10)
sp.pprint(cleaned)

print('\n')

# Extract yff, yft, ytf, ytt for the 9 possible combinations