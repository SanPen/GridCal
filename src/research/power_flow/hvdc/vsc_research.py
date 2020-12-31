import numpy as np

# ----------------------------------------------------------------------------------------------------------------------
# Parameters
# see: https://modeladopractico.readthedocs.io/es/latest/chapter_4_devices.html#voltage-source-converter-vsc
# ----------------------------------------------------------------------------------------------------------------------
R1 = 0.0001
X1 = 0.05
m = 0.8
theta = 0.1
Gsw = 1e-5  # should be around these values
Beq = 0.001  # should be around these values
# ----------------------------------------------------------------------------------------------------------------------

Y1 = 1.0 / complex(R1, X1)
y11 = Y1
y12 = -m * np.exp(1.0j * theta) * Y1
y21 = -m * np.exp(-1.0j * theta) * Y1
y22 = Gsw + m * m * (Y1 + 1.0j * Beq)

Vac = 0.995 * np.exp(-1j*0.02)
Vdc = 1.0

Y = np.array([[y11, y12],
              [y21, y22]])
V = np.array([Vac, Vdc])

I = np.dot(Y, V)

Iac, Idc = I

print('Vac:', Vac)
print('Vdc:', Vdc)
print('->')
print('Iac:', Iac)
print('Idc:', Idc)

V = np.linalg.solve(Y, I)

Vac2, Vdc2 = V
print()
print('Vac2:', Vac2)
print('Vdc2:', Vdc2)
