"""
Three-phase Power Flow Analysis - Enrique Acha

4.2. Over-head transmission lines
"""

import numpy as np

np.set_printoptions(precision=4, suppress=True)

# Distances
ha = 27.5 # [m]
hb = 27.5 # [m]
hc = 27.5 # [m]
dab = 12.65 # [m]
dbc = 12.65 # [m]
dca = dab+dbc # [m]
d_bundle = 0.46 # [m]

R = 0.1363e-3 # Resistance [Ohm/km]
n = 4 # Number of conductors per phase
w = 2*np.pi*50 # Angular frequency [rad/s]
mu_0 = 4*np.pi*10**-4 / 1000 # Permeability of the free space [H/m]
resistivity = 100 # Earth resistivity [Ohm/m]
conductivity  = 1/resistivity # Earth conductivity [S/m]

p = 1 / np.sqrt(1j * w * mu_0 * conductivity) # Complex Depth Beneath [m]

r_ext = 10.5e-3 # Conductor external radius [m]
gmr = r_ext * np.exp(-1/4) # Geometrical Mean Radius [m]

gmr_eq = (gmr * d_bundle * np.sqrt(2) * d_bundle * d_bundle)**(1/4) # Equivalent GMR [m]
print(gmr_eq)

# Self Impedances [Ohm/m]
Zaa = R/n + 1j * w * mu_0 / (2*np.pi) * np.log(2*(ha+p)/gmr_eq)
Zbb = R/n + 1j * w * mu_0 / (2*np.pi) * np.log(2*(hb+p)/gmr_eq)
Zcc = R/n + 1j * w * mu_0 / (2*np.pi) * np.log(2*(hc+p)/gmr_eq)

# Mutual Impedances [Ohm/m]
Zab = 1j * w * mu_0 / (2*np.pi) * np.log(np.sqrt((ha + hb + 2*p)**2 + dab**2) / np.sqrt((ha-hb)**2+dab**2))
Zbc = 1j * w * mu_0 / (2*np.pi) * np.log(np.sqrt((hb + hc + 2*p)**2 + dbc**2) / np.sqrt((hb-hc)**2+dbc**2))
Zca = 1j * w * mu_0 / (2*np.pi) * np.log(np.sqrt((hc + ha + 2*p)**2 + dca**2) / np.sqrt((hc-ha)**2+dca**2))

Z = np.zeros((3,3), complex)
Z[0,0] = Zaa
Z[1,1] = Zbb
Z[2,2] = Zcc
Z[0,1] = Zab
Z[1,0] = Zab
Z[0,2] = Zca
Z[2,0] = Zca
Z[1,2] = Zbc
Z[2,1] = Zbc
Z *= 1000 # Impedance Matrix [Ohm/km]
print('\nZ =\n', Z)


epsilon_0 = 8.85e-12 # Permittivity of the free space [F/m]
h= 27.5 # [m]

# Matrix of Potential Coefficients
P = np.zeros((3,3))
Paa = np.log(2*h/r_ext)
Pab = np.log(np.sqrt(4*h**2+dab**2)/dab)
Pbc = np.log(np.sqrt(4*h**2+dbc**2)/dbc)
Pca = np.log(np.sqrt(4*h**2+dca**2)/dca)
np.fill_diagonal(P, Paa)
P[0,1] = Pab
P[1,0] = Pab
P[1,2] = Pbc
P[2,1] = Pbc
P[0,2] = Pca
P[2,0] = Pca
print('\nP =\n', P)
Y = 1j * w * 2 * np.pi * epsilon_0 * np.linalg.inv(P) # Admittance Matrix [S/m]
Y = Y * 1e9 # Admittance Matrix [uS/km]
print('\nY =\n', Y)