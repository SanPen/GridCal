from sympy import symbols, Matrix
import numpy as np

np.set_printoptions(linewidth=20000, precision=3, suppress=True)

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

connexion = 'Yz'

Cu = np.zeros((6, 6))
Ci = np.zeros((6, 6))

if connexion == 'Yy':
    Cu[0, 0] = 1
    Cu[1, 3] = 1
    Cu[2, 1] = 1
    Cu[3, 4] = 1
    Cu[4, 2] = 1
    Cu[5, 5] = 1
    Ci = np.linalg.inv(Cu)

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

elif connexion == 'Yz':
    Yprimitive = np.zeros((12, 12), dtype=object)

    Yprimitive[0:2, 0:2] = Y_2x2
    Yprimitive[2:4, 2:4] = Y_2x2
    Yprimitive[4:6, 4:6] = Y_2x2
    Yprimitive[6:8, 6:8] = Y_2x2
    Yprimitive[8:10, 8:10] = Y_2x2
    Yprimitive[10:12, 10:12] = Y_2x2

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

print()
print(Cu)
print()
print(Ci)
print()
Ytrafo = np.linalg.pinv(Ci) @ Yprimitive @ np.linalg.pinv(Cu)
print()
print(Ytrafo)
print()