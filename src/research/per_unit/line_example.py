from math import sqrt

# system data
Sbase = 100  # MVA
V = 0.42  # kV (bus rated voltage)

# Line data
length = 0.22  # km
Imax = 0.27  # kA
R = 0.39  # Ohm/km
X = 0.081  # Ohm/km
B = 0.000113  # S/km

# pass to system base
ZbaseSys = (V**2) / Sbase  # Ohm
YbaseSys = 1.0 / ZbaseSys  # S

r = length * R / ZbaseSys  # p.u.
x = length * X / ZbaseSys  # p.u.
b = length * B / YbaseSys  # p.u.
rate = Imax * V * sqrt(3)  # MVA

print('r', r, 'p.u.')
print('x', x, 'p.u.')
print('b', b, 'p.u.')
print('rate', rate, 'MVA')
print()
