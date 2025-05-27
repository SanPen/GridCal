import numpy as np

phases = np.array([1, 2, 3])

for i in range(len(phases)):
    phases[i] -= 1

print(phases)