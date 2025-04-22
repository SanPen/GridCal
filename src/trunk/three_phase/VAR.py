from sympy import symbols, Matrix
import numpy as np
from scipy.linalg import block_diag
np.set_printoptions(linewidth=20000, precision=5, suppress=True)

element = 'Shunt Inductor'
connexion = 'Star'

if element == 'Shunt Inductor':
    L = 1 # Phase inductance [H]
    Z = 1j * 2 * np.pi * 50 * L # Shunt admittance [S]
    Ysh = 1/Z

elif element == 'Shunt Capacitor':
    C = 1 # Phase capacitance [F]
    Z = 1 / (1j * 2 * np.pi * 50 * C) # Shunt admittance [S]
    Ysh = 1 / Z

if connexion == 'Delta':
    Ysh = 3 * Ysh # Ystar = 3 * Ydelta

Y = block_diag(Ysh, Ysh, Ysh)
print(Y)