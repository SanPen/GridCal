import numpy as np
import sympy
from pprint import pprint
# Define fundamental symbols
R, X, G, B, t, phi = sympy.symbols('R, X, G, B, t, phi', real=True)
I = sympy.I  # Imaginary unit

# --- Define Admittances Symbolically ---
yff = sympy.Symbol('y_ff')
yft = sympy.Symbol('y_ft')
ytf = sympy.Symbol('y_tf')
ytt = sympy.Symbol('y_tt')

F = np.array([0, 2, 4, 6, 8, 10])
T = np.array([1, 3, 5, 7, 9, 11])

Y_ff = np.diag([yff, yff, yff, yff, yff, yff])
Y_ft = np.diag([yft, yft, yft, yft, yft, yft])
Y_tf = np.diag([ytf, ytf, ytf, ytf, ytf, ytf])
Y_tt = np.diag([ytt, ytt, ytt, ytt, ytt, ytt])

Cf = np.zeros((6, 12))
Ct = np.zeros((6, 12))

for i in range(6):
    Cf[i, F[i]] = 1
    Ct[i, T[i]] = 1

Yfps = Y_ff @ Cf + Y_ft @ Ct
Ytps = Y_tf @ Cf + Y_tt @ Ct

Yps = Cf.T @ Yfps + Ct.T @ Ytps

print('Yps: ', Yps)

# ----------

C_i_ps_abc = np.array([
    [1, 0, 0, 0, 0, 0],
    [0, 0, 0, 1, 0, 0],
    [1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, -1, 0],
    [0, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 0],
    [0, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, -1],
    [0, 0, 1, 0, 0, 0],
    [0, 0, 0, 0, 0, 1],
    [0, 0, 1, 0, 0, 0],
    [0, 0, 0, -1, 0, 0],
])

C_v_abc_ps = np.array([
    [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0],
    [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1],
    [0, 0, 0, -1, 0, 1, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, -1, 0, 1, 0, 0],
])

C_pseudo_i_ps_abc = np.linalg.pinv(C_i_ps_abc)
C_pseudo_v_abc_ps = np.linalg.pinv(C_v_abc_ps)

Yabc = C_pseudo_i_ps_abc @ Yps @ C_pseudo_v_abc_ps

print('Yabc: ', Yabc)
pprint(Yabc)

# ----------

