import numpy as np
from sympy import symbols
from scipy.linalg import block_diag

np.set_printoptions(linewidth=20000, precision=3, suppress=True)

yff = symbols('yff')
yft = symbols('yft')
ytf = symbols('ytf')
ytt = symbols('ytt')

y_primitive = np.zeros((2,2), object)
y_primitive[0,0] = yff
y_primitive[0,1] = yft
y_primitive[1,0] = ytf
y_primitive[1,1] = ytt

Yprimitive = block_diag(y_primitive, y_primitive, y_primitive, y_primitive, y_primitive, y_primitive)

Cu = np.zeros((6,12))
Ci = np.zeros((12,6))

Cu[0,0] = 1
Cu[0,2] = 1
Cu[1,4] = 1
Cu[1,6] = 1
Cu[2,8] = 1
Cu[2,10] = 1
Cu[3,11] = -1
Cu[3,1] = 1
Cu[4,3] = -1
Cu[4,5] = 1
Cu[5,7] = -1
Cu[5,9] = 1

Ci[0,0] = 1
Ci[1,3] = 1
Ci[2,0] = 1
Ci[3,4] = -1
Ci[4,1] = 1
Ci[5,4] = 1
Ci[6,1] = 1
Ci[7,5] = -1
Ci[8,2] = 1
Ci[9,5] = 1
Ci[10,2] = 1
Ci[11,3] = -1

Y = np.linalg.pinv(Ci) @ Yprimitive @ np.linalg.pinv(Cu)
print(Y)