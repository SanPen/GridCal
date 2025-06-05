import numpy as np

pq = np.array([15, 16, 17, 18, 19, 20], dtype=np.int32)

mask = np.array([1, 1, 1,
                 1, 1, 1,
                 0, 1, 1,
                 1, 1, 0,
                 1, 1, 1,
                 0, 0, 1,
                 0, 1, 0], dtype=bool)
indices = np.where(mask)[0]

same_indices = [i for i in pq if i in indices]

print()