import numpy as np

mask = np.array([0, 1, 1, 
                 1, 1, 0, 
                 1, 0, 1,
                 1, 0, 1,
                 1, 1, 0,
                 1, 1, 0,
                 1, 1, 1], dtype=bool)

ntotal_bus = len(mask)
indices = np.where(mask)[0]

from GridCalEngine.Utils.NumericalMethods.common import make_lookup
lookup = make_lookup(ntotal_bus, indices)

print(indices)
print(len(indices))

pq = np.array([0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], dtype=np.int32)
max_vector = np.zeros(ntotal_bus, dtype=np.int32)

count = 0
for i, val in enumerate(pq):
    idx = lookup[val]
    if idx > -1:
        max_vector[idx] = 1
        count += 1

pq_sliced = pq[:count]

print(pq_sliced)
