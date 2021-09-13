# Parametric analysis

# import packages
import numpy as np
from GridCal.Engine import *
import random
from functions_PQ import *
np.set_printoptions(precision=12)
random.seed(42)

# definitions
x_bus = 4  # check
indx_Vbus = x_bus - 1
ssz = 0.1  # discrete length

P2 = np.arange(0, 40, ssz)
Q2 = np.arange(0, 30, ssz)
P3 = np.arange(0, 30, ssz)
Q3 = np.arange(0, 45, ssz)
P4 = np.arange(0, 25, ssz)
Q4 = np.arange(0, 20, ssz)
P5 = np.arange(0, 30, ssz)
Q5 = np.arange(0, 20, ssz)

n_param = 8  # the 8 powers
Mm = 10  # number of modes, arbitrary value, >1.5Nterms
delta = 1e-5  # variation to compute the gradients

mat_mp = np.zeros((Mm, n_param), dtype=float)  # store samples

for ll in range(Mm):
	for kk in range(n_param):
		mat_mp[ll, 0] = random.sample(list(P2), 1)[0]
		mat_mp[ll, 1] = random.sample(list(Q2), 1)[0]
		mat_mp[ll, 2] = random.sample(list(P3), 1)[0]
		mat_mp[ll, 3] = random.sample(list(Q3), 1)[0]
		mat_mp[ll, 4] = random.sample(list(P4), 1)[0]
		mat_mp[ll, 5] = random.sample(list(Q4), 1)[0]
		mat_mp[ll, 6] = random.sample(list(P5), 1)[0]
		mat_mp[ll, 7] = random.sample(list(Q5), 1)[0]

C = np.zeros((n_param, n_param), dtype=float)  # covariance matrix
# Ag_store = []  # store gradients

for ll in range(Mm):
    # retrieve samples
	pp0 = mat_mp[ll, 0]
	pp1 = mat_mp[ll, 1]
	pp2 = mat_mp[ll, 2]
	pp3 = mat_mp[ll, 3]
	pp4 = mat_mp[ll, 4]
	pp5 = mat_mp[ll, 5]
	pp6 = mat_mp[ll, 6]
	pp7 = mat_mp[ll, 7]

    # initial solution
	v5_sol = V5(pp0, pp1, pp2, pp3, pp4, pp5, pp6, pp7, indx_Vbus)

    # solution with variations
	v5_sol_pp0 = V5(pp0 + delta, pp1, pp2, pp3, pp4, pp5, pp6, pp7, indx_Vbus)
	v5_sol_pp1 = V5(pp0, pp1 + delta, pp2, pp3, pp4, pp5, pp6, pp7, indx_Vbus)
	v5_sol_pp2 = V5(pp0, pp1, pp2 + delta, pp3, pp4, pp5, pp6, pp7, indx_Vbus)
	v5_sol_pp3 = V5(pp0, pp1, pp2, pp3 + delta, pp4, pp5, pp6, pp7, indx_Vbus)
	v5_sol_pp4 = V5(pp0, pp1, pp2, pp3, pp4 + delta, pp5, pp6, pp7, indx_Vbus)
	v5_sol_pp5 = V5(pp0, pp1, pp2, pp3, pp4, pp5 + delta, pp6, pp7, indx_Vbus)
	v5_sol_pp6 = V5(pp0, pp1, pp2, pp3, pp4, pp5, pp6 + delta, pp7, indx_Vbus)
	v5_sol_pp7 = V5(pp0, pp1, pp2, pp3, pp4, pp5, pp6, pp7 + delta, indx_Vbus)

	# compute gradients
	Ag = np.array([[(v5_sol_pp0 - v5_sol) / delta],
				   [(v5_sol_pp1 - v5_sol) / delta],
				   [(v5_sol_pp2 - v5_sol) / delta],
				   [(v5_sol_pp3 - v5_sol) / delta],
				   [(v5_sol_pp4 - v5_sol) / delta],
				   [(v5_sol_pp5 - v5_sol) / delta],
				   [(v5_sol_pp6 - v5_sol) / delta],
				   [(v5_sol_pp7 - v5_sol) / delta]])

	# Ag_store.append(Ag.T)
	Ag_prod = np.dot(Ag, Ag.T)  # product between gradients (row x col) in a matrix multiplication fashion
	C += 1 / Mm * Ag_prod

print('covariance matrix:\n', C)

w, v = np.linalg.eig(C)
print('Eigenvalues:\n', w)  # eigenvalues
print('Eigenvectors:\n', v)  # eigenvectors

# define matrix Q
nterms = 4  # expansions order + 1
matA = np.zeros((Mm, nterms), dtype=float)  # matrix Q from the monograph
d1 = 1  # should be picked according to the truncation error
Wy = v[:, d1 - 1]  # only first column
Wz = v[:, d1:]  # rest of columns

yy_vec = []
for ll in range(Mm):
	yy = np.dot(Wy.T, mat_mp[ll, :])
	yy_vec.append(yy)
	for nn in range(nterms):
		matA[ll, nn] = yy ** nn  # original

	zz = np.dot(Wz.T, mat_mp[ll, :])

zz_mean = 1 / Mm * zz  # non-changing directions

# compute h(y). Maybe we could use the results from V5(...)?
h_vec = []
yy_vec = np.array(yy_vec)
for ll in range(Mm):
	y_in = np.dot(Wy, yy_vec[ll]) + np.dot(Wz, zz_mean)  # as in shen2020
	vv5 = V5(y_in[0], y_in[1], y_in[2], y_in[3], y_in[4], y_in[5], y_in[6], y_in[7], indx_Vbus)
	h_vec.append(vv5)

h_vec = np.array(h_vec)

# finally, compute c vector
# c_vec = np.dot(np.dot(np.linalg.inv(np.dot(matA.T, matA)), matA.T), h_vec)
c_vec = np.dot(np.linalg.solve(np.dot(matA.T, matA), matA.T), h_vec)
print('Polynomial coefficients for V5:\n', c_vec)

# everything done, now compute one solution and check
ppp = [25, 12, 8, 33, 21, 4, 17, 11]
vv5s = V5(ppp[0], ppp[1], ppp[2], ppp[3], ppp[4], ppp[5], ppp[6], ppp[7], indx_Vbus)
y_val = np.dot(Wy.T, np.array(ppp))  # transform 8 dimensions into 1

# use final polynomial
vv5p = c_vec[0] * y_val ** 0 + c_vec[1] * y_val ** 1 + c_vec[2] * y_val ** 2 + c_vec[3] * y_val ** 3

# print results
print('V5 estimated:', vv5p)
print('V5 computed:', vv5s)
print('V5 error:', abs(vv5p-vv5s))

