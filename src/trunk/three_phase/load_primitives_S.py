import numpy as np

conn = 'Y'

if conn == 'Y':
    S = np.array([
        [Sa],
        [Sb],
        [Sc]
    ])
else:
    S = np.array([
        [(Ua * Sab) / (Ua - Ub) - (Ua * Sca) / (Uc - Ua)],
        [(Ub * Sbc) / (Ub - Uc) - (Ub * Sab) / (Ua - Ub)],
        [(Uc * Sca) / (Uc - Ua) - (Uc * Sbc) / (Ub - Uc)],
    ])