import numpy as np
from sympy import symbols

np.set_printoptions(linewidth=20000, precision=3, suppress=True)

Ty_conn = np.array([[1, 0, 0],
                    [0, 1, 0],
                    [0, 0, 1]])

Td_conn = 1/np.sqrt(3) * np.array([[1, -1, 0],
                                   [0, 1, -1],
                                   [-1, 0, 1]])

hv_at_from = True

ys = symbols('Ysc')
a = symbols('T')
ysh = symbols('Ym')
conn = 'Yy'

if conn == 'Yy':
    Tf = Ty_conn
    Tt = a * Ty_conn
    ysh_f = np.diag([ysh / 2, ysh / 2, ysh / 2])
    ysh_t = ysh_f
elif conn == 'Yd':
    if hv_at_from:
        Tf = Ty_conn
        Tt = a * Td_conn
        ysh_f = np.diag([ysh / 2, ysh / 2, ysh / 2])
        ysh_t = np.diag([ysh, ysh, ysh])
    else:
        Tt = Ty_conn
        Tf = a * Td_conn
        ysh_t = np.diag([ysh / 2, ysh / 2, ysh / 2])
        ysh_f = np.diag([ysh, ysh, ysh])
elif conn == 'Dy':
    if hv_at_from:
        Tf = Td_conn
        Tt = a * Ty_conn
        ysh_f = np.diag([ysh, ysh, ysh])
        ysh_t = np.diag([ysh / 2, ysh / 2, ysh / 2])
    else:
        Tt = Td_conn
        Tf = a * Ty_conn
        ysh_t = np.diag([ysh, ysh, ysh])
        ysh_f = np.diag([ysh / 2, ysh / 2, ysh / 2])
elif conn == 'Dd':
    Tf = Td_conn
    Tt = a * Td_conn
    ysh_f = np.diag([ysh, ysh, ysh])
    ysh_t = ysh_f

Yff = Tf.T * ys @ Tf + ysh_f
Yft = -Tf.T * ys @ Tt
Ytf = -Tt.T * ys @ Tf
Ytt = Tt.T * ys @ Tt + ysh_t

print()
print(Yff)
print()
print(Yft)
print()
print(Ytf)
print()
print(Ytt)