from sympy import symbols
import numpy as np
import GridCalEngine.api as gce
from GridCalEngine import WindingsConnection

np.set_printoptions(linewidth=20000, precision=3, suppress=True)

trafo = gce.Transformer2W(name='Test',
                          r=0,
                          x=1,
                          g=0,
                          b=1,
                          tap_module=1,
                          tap_phase=0,
                          conn=WindingsConnection.GG
                          )

Ys = 1 / (trafo.R + 1j * trafo.X)
Ysh = (trafo.G + 1j * trafo.B) / 2
m = trafo.tap_module
tau = trafo.tap_phase
mf = 1
mt = 1

yff = (Ys + Ysh) / (m**2 * mf**2 * np.exp(2j*tau))
yft = -Ys / (m * mf * mt)
ytf = -Ys / (m * mf * mt * np.exp(2j*tau))
ytt = (Ys + Ysh) / mt**2

Yphase = np.zeros((2, 2), complex)
Yphase[0,0] = yff
Yphase[0,1] = yft
Yphase[1,0] = ytf
Yphase[1,1] = ytt

Yprimitive = np.zeros((6, 6), complex)

Yprimitive[0:2,0:2] = Yphase
Yprimitive[2:4,2:4] = Yphase
Yprimitive[4:6,4:6] = Yphase

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
print()
print(Ci)
print()
Ytrafo = Ci @ Yprimitive @ Cu
print()
print(Ytrafo)
print()
