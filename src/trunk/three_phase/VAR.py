from sympy import symbols, Matrix
import numpy as np
from scipy.linalg import block_diag
np.set_printoptions(linewidth=20000, precision=3, suppress=True)

f = 50 # Frequency [Hz]
connexion = 'Star'
L = 0  # Phase inductance [H]
C = 1 # Phase capacitance [F]

if L != 0:
    Yphase = 1 / (1j * 2 * np.pi * f * L) # Shunt admittance [S]

elif C != 0:
    Yphase = 1j * 2 * np.pi * f * C # Shunt admittance [S]

if connexion == 'Delta':
    Yphase = 3 * Yphase # Ystar = 3 * Ydelta

Y = block_diag(Yphase, Yphase, Yphase)
print(Y)