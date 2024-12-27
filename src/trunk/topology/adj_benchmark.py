import datetime
import numpy as np
from scipy.sparse import csc_matrix, lil_matrix, coo_matrix


def method_A(F, T, n, m, lil=True):

    if lil:
        C = lil_matrix((m, n))
        for k in range(m):
            C[k, F[k]] = 1
            C[k, T[k]] = 1
    else:
        i = np.r_[np.arange(m, dtype=int), np.arange(m, dtype=int)]
        j = np.r_[F, T]
        data = np.ones(m* 2, dtype=int)
        C = coo_matrix((data, (i, j)), shape=(m, n), dtype=int)

    # compute the adjacency matrix
    A = C.T @ C

    return A.tocsc()


def method_B(F, T, n, m):
    A = lil_matrix((n, n))
    for k in range(m):
        f = F[k]
        t = T[k]
        A[f, f] += 1
        A[f, t] += 1
        A[t, f] += 1
        A[t, t] += 1

    return A.tocsc()


# create random branches connectivity
n_ = 10000
m_ = 120000
F_ = np.random.randint(0, n_ - 1, m_)
T_ = np.random.randint(0, n_ - 1, m_)

t0 = datetime.datetime.now()
for i in range(100):
    method_A(F_, T_, n_, m_, lil=False)

t1 = datetime.datetime.now()

for i in range(100):
    method_B(F_, T_, n_, m_)

t2 = datetime.datetime.now()

print("A:", (t1 - t0).seconds)
print("B:", (t2 - t1).seconds)
