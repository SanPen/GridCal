import numpy as np

def load_power(connection: str,
               Sa: complex,
               Sb: complex,
               Sc: complex,
               Sab: complex,
               Sbc: complex,
               Sca: complex,
               Ua: complex,
               Ub: complex,
               Uc: complex
               ):

    if connection == 'Y':
        S = np.array([Sa, Sb, Sc])
    else:
        S = np.array([
            (Ua * Sab) / (Ua - Ub) - (Ua * Sca) / (Uc - Ua),
            (Ub * Sbc) / (Ub - Uc) - (Ub * Sab) / (Ua - Ub),
            (Uc * Sca) / (Uc - Ua) - (Uc * Sbc) / (Ub - Uc),
        ])

    return S