from cvxopt import spmatrix

A = spmatrix([2, -1, 2, -2, 1, 4],  [1, 2, 0, 2, 3, 2],  [0, 0, 1, 1, 2, 3])
B = spmatrix(1.0, range(4), range(4)) * 2

C = A + B

print("A:\n", A)
print("B:\n", B)
print("C:\n", C)
print("2C:\n", 2 * C)
print("C x B:\n", C * B)
