import numpy as np

conn = 'Y'
equipment = 'L'

if equipment == 'L':
    Y = np.array([1 / (1j * 2 * np.pi * f * L), 1 / (1j * 2 * np.pi * f * L), 1 / (1j * 2 * np.pi * f * L)])

elif equipment == 'C':
    Y = np.array([1j * 2 * np.pi * f * C, 1j * 2 * np.pi * f * C, 1j * 2 * np.pi * f * C])

if conn == 'D':
    Y = 3 * Y