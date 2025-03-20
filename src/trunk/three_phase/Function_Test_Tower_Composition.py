import numpy as np

"""
Three-phase Power Flow Analysis - Enrique Acha

4.2. Over-head transmission lines
"""

U = 500e3 # Nominal Voltage [V]
R = 0.1363 # Resistance [Ohm/km] Panther (30x3.00 / 7x3.00 ACSR)
rho = 100 # Earth Resistivity [Ohm/m]
f = 50 # Frequency [Hz]

"""
Four bundled conductors per phase with a separation of 0,46 m between adjacent conductors, 
placed at the corners of a square. No shielding wires are considered.

The phase conductors are placed on the tower with the given coordinates [m]:
"""

Xa = -12.65
Xb = 0
Xc = 12.65
Ya = 27.5
Yb = 27.5
Yc = 27.5

n = 4 # number of conductors per phase
r_ext = 0.46 # Separation between adjacent conductors [m]
w = 2*np.pi*f # Angular Velocity [rad/s]
mu_0 = 4*np.pi*10**-4 # Permeability of the free space [H/km]
sigma = 1/rho # Earth Conductivity [S/m]
p = 1 / np.sqrt(1j*w*mu_0*sigma) # Complex depth beneath the ground at which the mirroring surface is located [m]
gmr = r_ext * np.exp(-1/4) # Geometrical Mean Radius [m]
gmr_eq =

Zseries = R/n + 1j * w * mu_0 / (2*np.pi) * np.log(2*(Ya+p)/gmr)
print(Zseries)