import numpy as np
# Transmission line coordinates [m]
Xa = -12.65
Ya = 27.5
Xb = 0
Yb = 27.5
Xc = 12.65
Yc = 27.5

# Distances [m]
dab = np.sqrt((Xa-Xb)**2 + (Ya-Yb)**2)
dbc = np.sqrt((Xb-Xc)**2 + (Yb-Yc)**2)
dca = np.sqrt((Xc-Xa)**2 + (Yc-Ya)**2)

h = Ya # [m]
r_ext = 10.5e-3 # Conductor external radius [m]


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
P[2,0] = Pca
P[0,2] = Pca
print('\nP =\n', P)

w = 2*np.pi*50 # Angular frequency [rad/s]
epsilon_0 = 8.85 * 10**(-9) # Permittivity of the free space [F/km]
Y = 1j * w * 2 * np.pi * epsilon_0 * (np.linalg.inv(P))
print('\nY =\n', Y*1e6)