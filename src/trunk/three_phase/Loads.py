import numpy as np
from sympy import symbols, Matrix, simplify
from scipy.linalg import block_diag
import scipy.sparse as sp
np.set_printoptions(linewidth=20000, precision=2, suppress=True)

"""
Power Definition
"""
U = 230 # Voltage module [V]
theta = 0 # Voltage phase [rad]
I = 10 # Current module [A]
phi = np.pi/6 # Current - Voltage phase displacement [rad]

# Star phase-to-neutral voltages [V]
Ua = U * np.exp(1j * theta)
Ub = U * np.exp(1j * (theta-2*np.pi/3))
Uc = U * np.exp(1j * (theta+2*np.pi/3))
Ustar = np.array([Ua, Ub, Uc])

# Star phase-to-neutral currents [A]
Ia = I * np.exp(1j * (theta-phi))
Ib = I * np.exp(1j * (theta-2*np.pi/3-phi))
Ic = I * np.exp(1j * (theta+2*np.pi/3-phi))
Istar = np.array([Ia, Ib, Ic])

# Star power [VA]
Sstar = Ustar * np.conjugate(Istar)
print('\nS_star = \n', Sstar)

# Connectivity matrices
Cu = np.array([[1,-1,0], [0,1,-1], [-1,0,1]]) # U_ph-ph = Cu @ U_ph-n
Ci = np.array([[1,0,-1], [-1,1,0], [0,-1,1]]) # I_ph-n = Ci @ I_ph-ph

Udelta = Cu @ Ustar # Phase-to-phase voltages [V]
Idelta = np.linalg.pinv(Ci) @ Istar # Phase-to-phase currents [A]

# Delta power [VA]
Sdelta = Udelta * np.conjugate(Idelta)
print('\nS_delta = \n', Sdelta)

# Compute S_star from S_delta using the derived relationship
S_star_computed = np.diag(Ustar) @ Ci @ np.diag(1 / (Cu @ Ustar)) @ Sdelta
print("\nStar power computed from S_delta (S_star_computed):\n", S_star_computed)

"""
Impedance Definition
"""
#connexion = 'Star'

#if connexion == 'Star':
    #Ya = Ga + 1j * Ba
    #Yb = Ga + 1j * Ba
    #Yc = Ga + 1j * Ba
    #else:
    #Yab = Gab + 1j * Bab
    #Ybc = Gbc + 1j * Bbc
    #Yca = Gca + 1j * Bca
    #Ya = ( Yab*Ybc + Ybc*Yca + Yca*Yab ) / Ybc
    #Yb = ( Yab*Ybc + Ybc*Yca + Yca*Yab ) / Yca
    #Yc = ( Yab*Ybc + Ybc*Yca + Yca*Yab ) / Yab

#Y = block_diag(Ya, Yb, Yc) # Mejor pasar el vector
#print('\nY = \n', Y)

Ua, Ub, Uc = symbols('Ua, Ub, Uc')
Sab, Sbc, Sca = symbols('Sab, Sbc, Sca')

Uabc = Matrix([
    [Ua, 0, 0],
    [0, Ub, 0],
    [0, 0, Uc]
])

Udelta = Matrix([
    [1 / (Ua - Ub), 0, 0],
    [0, 1 / (Ub - Uc), 0],
    [0, 0, 1 / (Uc - Ua)]
])

S = Matrix([
    [Sab],
    [Sbc],
    [Sca]
])

print(Uabc @ Ci @ Udelta @ S)
