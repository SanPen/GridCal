import numpy as np

np.set_printoptions(linewidth=20000, precision=2, suppress=True)

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

Sstar_from_delta = np.linalg.pinv(Cu) * Sstar @ Ci.T
print('\nSstar_from_delta = \n', Sstar_from_delta)