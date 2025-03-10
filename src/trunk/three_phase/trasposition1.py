
import numpy as np


Zs = np.array([[0.5706 + 0.4848j, 0.1580 + 0.4236j, 0.1559 + 0.5017j, 0],
               [0.1580 + 0.4236j, 0.5655 + 1.1052j, 0.1535 + 0.3849j, 0],
               [0.1559 + 0.5017j, 0.1535 + 0.3849j, 0.5616 + 1.1212j, 0]])

conn1 = [0, 1, 2]  # ABC
conn2 = [1, 0, 2]  # BAC

Vm1 = np.array([10, 10, 10])
Vm2 = np.array([9.95, 9.93, 9.91])
Va1 = np.array([0, -120, 120])
Va2 = Va1 - np.array([10, 9.5, 8])

V1 = Vm1 * np.exp(1j * Va1)
V2 = Vm2 * np.exp(1j * Va2)
dV = V1 - V2

# dV = Z @ I, I = Y @ dV

Ys = np.linalg.inv(Zs)
I1 = Ys @ V1
I2 = Ys @ V2

If = Ys @ dV

print("I1", I1)
print("I2", I2)