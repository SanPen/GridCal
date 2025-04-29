import numpy as np

conn = 'Y'

if conn == 'Y':
    Y = np.array([Ya, Yb, Yc])
else:
    Y = np.array([
        (Yab * Ybc + Ybc * Yca + Yca * Yab) / Ybc,
        (Yab * Ybc + Ybc * Yca + Yca * Yab) / Yca,
        (Yab * Ybc + Ybc * Yca + Yca * Yab) / Yab
    ])