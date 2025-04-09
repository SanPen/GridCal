from sympy import symbols, Matrix
import numpy as np

np.set_printoptions(linewidth=20000, precision=3, suppress=True)

Ys = symbols('Ys')
Ysh = symbols('Ysh')
a = symbols('a')

Y_2x2 = Matrix([
    [Ys/a**2 + Ysh/2, -Ys/np.conjugate(a)],
    [-Ys/a, Ys + Ysh/2]
])

Y_6x6_primitive = np.zeros((6, 6), dtype=object)

Y_6x6_primitive[0:2,0:2] = Y_2x2
Y_6x6_primitive[2:4,2:4] = Y_2x2
Y_6x6_primitive[4:6,4:6] = Y_2x2

connexion = 'Dd'

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

print()
print(Cu)
print()
print(Ci)
print()
Ytrafo = Ci @ Y_6x6_primitive @ Cu
print()
print(Ytrafo)
print()