import numpy as np

def load_admittance(connection: str,
                     Ya: complex,
                     Yb: complex,
                     Yc: complex,
                     Yab: complex,
                     Ybc: complex,
                     Yca: complex,
                     ):

    if connection == 'Y':
        Y = np.array([Ya, Yb, Yc])
    else:
        Y = np.array([
            (Yab * Ybc + Ybc * Yca + Yca * Yab) / Ybc,
            (Yab * Ybc + Ybc * Yca + Yca * Yab) / Yca,
            (Yab * Ybc + Ybc * Yca + Yca * Yab) / Yab
        ])

    return Y