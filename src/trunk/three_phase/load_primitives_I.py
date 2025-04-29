import numpy as np

def load_current(connection: str,
                 Ia: complex,
                 Ib: complex,
                 Ic: complex,
                 Iab: complex,
                 Ibc: complex,
                 Ica: complex,
                 ):

    if connection == 'Y':
        I = np.array([Ia, Ib, Ic])
    else:
        I = np.array([
            Iab - Ica,
            Ibc - Iab,
            Ica - Ibc
        ])

    return I