import numpy as np

# Matriz de fases de rama
R = np.array([
    [1, 1, 1],
    [0, 1, 1],
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
    [0, 0, 1],
    [1, 1, 0],
    [0, 1, 0],
])
print('\nR = \n', R)

# Connectividad rama-nudo
C_NR = np.array([
    [1, 1, 0, 0, 0, 0, 0, 0],
    [1, 0, 1, 0, 0, 0, 0, 1],
    [0, 1, 0, 1, 1, 0, 0, 0],
    [0, 0, 1, 0, 0, 0, 1, 0],
    [0, 0, 0, 1, 0, 1, 1, 0],
    [0, 0, 0, 0, 1, 1, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 1]
])
print('\nC_NR= \n', C_NR)

# Matriz de fases de nodo
N = C_NR @ R
print('\nN = \n', N)

# Mascara
M = (N > 0).astype(int).reshape(-1)
print('\nM = \n', M)

