import numpy as np

conn = 'Y'

if conn == 'Y':
    I = np.array([
        [Ia],
        [Ib],
        [Ic]
    ])
else:
    Ci = np.array([
        [1, 0, -1],
        [-1, 1, 0],
        [0, -1, 1]
    ])
    I = Ci @ np.array([[Iab], [Ibc], [Ica]])