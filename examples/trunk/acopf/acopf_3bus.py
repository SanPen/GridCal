import numpy as np


"""
Code to solve a 3-bus OPF
Everything is rudimentary to test the IPM

# Data
Bus 1 - Slack (e1=1, f1=0)
Bus 2 - PQ generator (q2=0)
Bus 3 - PQ load (p3=-0.5, q3=-0.2)
Lines: Z = (0.01 + 0.05j)

# Restrictions
- Current limit of lines
- Under and overvoltage limits
- Kirchhoff for power balance

# Unknowns
x = e2, e3, f2, f3 (rectangular form)

# Objective function
f(x) = a1 + b1p1(x) + c1p1(x)^2 + a2 + b2p2(x) + c2p2(x)^2

# Equality constraints g
q2(x) - q2sp = 0
p3(x) - p3sp = 0
q3(x) - q3sp = 0


# Inequality constraints h
lc^2 - i12(x)^2 >= 0
lc^2 - i23(x)^2 >= 0
lc^2 - i31(x)^2 >= 0
vu^2 - e2^2 - f2^2 >= 0
vu^2 - e3^2 - f3^2 >= 0
e2^2 + f2^2 - vl^2 >= 0
e3^2 + f3^2 - vl^2 >= 0
"""


a1 = 0.1
b1 = 0.2
c1 = 0.4
a2 = 0.1
b2 = 0.2
c2 = 0.4
e1 = 1.0
f1 = 0.0

q2sp = 0.0
p3sp = -0.5
q3sp = -0.2

Z = 0.01 + 0.05j
Y = 1 / Z
g = np.real(Y)
b = np.imag(Y)

lc = 0.5
vu = 1.1
vl = 0.9


def f_obj(x):
    e2, e3, f2, f3 = x[:]
    P1 = g * (e1 * (2 * e1 - e2 - e3) - f1 * (-2 * f1 + f2 + f3)) + b * (e1 * (-2 * f1 + f2 + f3) + f1 * (2 * e1 - e2 - e3))
    P2 = g * (e2 * (2 * e2 - e1 - e3) - f2 * (-2 * f2 + f1 + f3)) + b * (e2 * (-2 * f2 + f1 + f3) + f2 * (2 * e2 - e1 - e3))
    return a1 + b1 * P1 + c1 * P1**2 + a2 + b2 * P2 + c2 * P2**2


def h_i12(x):
    e2, e3, f2, f3 = x[:]
    i12sq = (g * (e1 - e2) - b * (f1 - f2))**2 + (b * (e1 - e2) + g * (f1 - f2))**2
    return lc**2 - i12sq

def h_i23(x):
    e2, e3, f2, f3 = x[:]
    i23sq = (g * (e2 - e3) - b * (f2 - f3))**2 + (b * (e2 - e3) + g * (f2 - f3))**2
    return lc**2 - i23sq

def h_i31(x):
    e2, e3, f2, f3 = x[:]
    i31sq = (g * (e3 - e1) - b * (e3 - e1))**2 + (b * (e3 - e1) + g * (f3 - f1))**2
    return lc**2 - i31sq

def h_vl2(x):
    e2, e3, f2, f3 = x[:]
    return e2**2 + f2**2 - vl**2

def h_vl3(x):
    e2, e3, f2, f3 = x[:]
    return e3**2 + f3**2 - vl**2

def h_vu2(x):
    e2, e3, f2, f3 = x[:]
    return vu**2 - e2**2 - f2**2

def h_vu3(x):
    e2, e3, f2, f3 = x[:]
    return vu**2 - e3**2 - f3**2


def g_q2(x):
    e2, e3, f2, f3 = x[:]
    Q2 = g * (e2 * (-2 * f2 + f1 + f3) + f2 * (2 * e2 - e1 - e3)) - b * (e2 * (2 * e2 - e1 - e3) - f2 * (-2 * f2 + f1 + f3))
    return Q2 - q2sp

def g_p3(x):
    e2, e3, f2, f3 = x[:]
    P3 = g * (e3 * (2 * e3 - e1 - e2) - f3 * (-2 * f3 + f1 + f2)) + b * (e3 * (-2 * f3 + f1 + f2) + f3 * (2 * e3 - e1 - e2))
    return P3 - p3sp

def g_q3(x):
    e2, e3, f2, f3 = x[:]
    Q3 = g * (e3 * (-2 * f3 + f1 + f2) + f3 * (2 * e3 - e1 - e2)) - b * (e3 * (2 * e3 - e1 - e2) - f3 * (-2 * f3 + f1 + f2))
    return Q3 - q3sp


"""
IPM

[[L, 0, -Atg, -Ath],
 [0, Z, 0, S],
 [Ag, 0, 0, 0],
 [Ah, -I, 0, 0]]
* 
[[Ax],
 [As],
 [Ay],
 [Az]]
=
-[[Tf - Atg * y - Ath * z],
 [S * z - mu * e],
 [g],
 [h - s]]


Sizes:
x = 4
g = 3, hence y = 3
h = 7, hence z = 7, s = 7, e = 7
Ag = 3x4
Ah = 7x4
Hg = [3x4]*3
Hh = [7x4]*7
"""


# Derive functions to generate gradient and hessian

def gen_grad(x, f, eps=1e-8):
    """
    Generate the gradient of function f w.r.t. vector x
    Return a vector
    """
    n_x = len(x)
    grad_vec = np.zeros(n_x, dtype=float)
    x_new = np.zeros(n_x, dtype=float)
    for i in range(n_x):
        x_new[:] = x[:]
        x_new[i] += eps
        grad_vec[i] = (f(x_new) - f(x)) / eps

    return grad_vec


def gen_hess(x, f, eps=1e-3):
    """
    Generate the hessian matrix of a function f w.r.t. vector x
    Return a matrix
    """
    n_x = len(x)
    hess_mat = np.zeros((n_x, n_x), dtype=float)
    grad_col0 = gen_grad(x, f)
    x_new = np.zeros(n_x, dtype=float)
    for i in range(n_x):
        x_new[:] = x[:]
        x_new[i] += eps
        hess_mat[:,i] = (gen_grad(x_new, f) - grad_col0) / eps

    return hess_mat


n_g = 3
n_h = 7
n_x = 4

n_rows = n_x + n_g + 2 * n_h
n_cols = n_rows
# J = np.zeros((n_rows, n_cols), dtype=float)  # constituted by J1 to J16
# J = np.array([[J1, J2, J3, J4],
#               [J5, J6, J7, J8],
#               [J9, J10, J11, J12],
#               [J13, J14, J15, J16]])


x = np.array([1.0, 1.0, 0.0, 0.0])
y = np.array([5.0]*n_g)
z = np.array([1.0]*n_h)
s = np.array([1.0]*n_h)

mu = 1.0
e = np.array([1.0]*n_h)

def build_J_easy():
    J2 = np.zeros((n_x, n_h), dtype=float)
    J5 = np.zeros((n_h, n_x), dtype=float)
    J7 = np.zeros((n_h, n_g), dtype=float)
    J10 = np.zeros((n_g, n_h), dtype=float)
    J11 = np.zeros((n_g, n_g), dtype=float)
    J12 = np.zeros((n_g, n_h), dtype=float)
    J14 = - np.diag([1.0]*n_h)
    J15 = np.zeros((n_h, n_g), dtype=float)
    J16 = np.zeros((n_h, n_h), dtype=float)
    return J2, J5, J7, J10, J11, J12, J14, J15, J16

def build_J6(z):
    J6 = np.diag(z)
    return J6

def build_J8(s):
    J8 = np.diag(s)
    return J8

def build_J3(x):
    grad_g1 = gen_grad(x, g_q2)
    grad_g2 = gen_grad(x, g_p3)
    grad_g3 = gen_grad(x, g_q3)
    Ag = np.vstack((grad_g1, grad_g2, grad_g3))
    return - Ag.T

def build_J4(x):
    grad_h1 = gen_grad(x, h_i12)
    grad_h2 = gen_grad(x, h_i23)
    grad_h3 = gen_grad(x, h_i31)
    grad_h4 = gen_grad(x, h_vl2)
    grad_h5 = gen_grad(x, h_vl3)
    grad_h6 = gen_grad(x, h_vu2)
    grad_h7 = gen_grad(x, h_vu3)
    Ah = np.vstack((grad_h1, grad_h2, grad_h3, grad_h4, grad_h5, grad_h6, grad_h7))
    return - Ah.T

def build_J9(x):
    grad_g1 = gen_grad(x, g_q2)
    grad_g2 = gen_grad(x, g_p3)
    grad_g3 = gen_grad(x, g_q3)
    Ag = np.vstack((grad_g1, grad_g2, grad_g3))
    return Ag

def build_J13(x):
    grad_h1 = gen_grad(x, h_i12)
    grad_h2 = gen_grad(x, h_i23)
    grad_h3 = gen_grad(x, h_i31)
    grad_h4 = gen_grad(x, h_vl2)
    grad_h5 = gen_grad(x, h_vl3)
    grad_h6 = gen_grad(x, h_vu2)
    grad_h7 = gen_grad(x, h_vu3)
    Ah = np.vstack((grad_h1, grad_h2, grad_h3, grad_h4, grad_h5, grad_h6, grad_h7))
    return Ah

def build_J1(x, y, z):
    hess_f = gen_hess(x, f_obj)

    hess_g1 = gen_hess(x, g_q2)
    hess_g2 = gen_hess(x, g_p3)
    hess_g3 = gen_hess(x, g_q3)

    hess_h1 = gen_hess(x, h_i12)
    hess_h2 = gen_hess(x, h_i23)
    hess_h3 = gen_hess(x, h_i31)
    hess_h4 = gen_hess(x, h_vl2)
    hess_h5 = gen_hess(x, h_vl3)
    hess_h6 = gen_hess(x, h_vu2)
    hess_h7 = gen_hess(x, h_vu3)

    sum_hess_g = y[0] * hess_g1 + y[1] * hess_g2 + y[2] * hess_g3
    sum_hess_h = z[0] * hess_h1 + z[1] * hess_h2 + z[2] * hess_h3 + z[3] * hess_h4 + z[4] * hess_h5 + z[5] * hess_h6 + z[6] * hess_h7

    return hess_f - sum_hess_g - sum_hess_h


def build_f1(x, y, z):
    grad_f = gen_grad(x, f_obj)

    grad_h1 = gen_grad(x, h_i12)
    grad_h2 = gen_grad(x, h_i23)
    grad_h3 = gen_grad(x, h_i31)
    grad_h4 = gen_grad(x, h_vl2)
    grad_h5 = gen_grad(x, h_vl3)
    grad_h6 = gen_grad(x, h_vu2)
    grad_h7 = gen_grad(x, h_vu3)
    Ahh = np.vstack((grad_h1, grad_h2, grad_h3, grad_h4, grad_h5, grad_h6, grad_h7))

    grad_g1 = gen_grad(x, g_q2)
    grad_g2 = gen_grad(x, g_p3)
    grad_g3 = gen_grad(x, g_q3)
    Agg = np.vstack((grad_g1, grad_g2, grad_g3))

    return grad_f - Agg.T @ y - Ahh.T @ z

def build_f2(s, z):
    Sdiag = np.diag(s)
    return Sdiag @ z - mu * e

def build_f3(x):
    g1 = g_q2(x)
    g2 = g_p3(x)
    g3 = g_q3(x)
    return np.array([g1, g2, g3])

def build_f4(x, s):
    h1 = h_i12(x) - s[0]
    h2 = h_i23(x) - s[1]
    h3 = h_i31(x) - s[2]
    h4 = h_vl2(x) - s[3]
    h5 = h_vl3(x) - s[4]
    h6 = h_vu2(x) - s[5]
    h7 = h_vu3(x) - s[6]
    return np.array([h1, h2, h3, h4, h5, h6, h7])


def calc_as(x, Ax, s, As, tau=0.995):
    #  https://www.tu-ilmenau.de/fileadmin/Bereiche/IA/prozessoptimierung/vorlesungsskripte/abebe_geletu/IPM_Slides.pdf
    vec_x = []

    for i in range(len(x)):
        if Ax[i] < 0:
            vec_x.append(x[i] / - Ax[i])
        else:
            vec_x.append(1)

    vec_s = []
    for i in range(len(s)):
        if As[i] < 0:
            vec_s.append(s[i] / - As[i])
        else:
            vec_s.append(1)

    amax = min(min(vec_x), min(vec_s))

    return min(1, 0.999 * amax)


Nmax = 50
for i in range(Nmax):

    J2, J5, J7, J10, J11, J12, J14, J15, J16 = build_J_easy()

    J1 = build_J1(x, y, z)
    J3 = build_J3(x)
    J4 = build_J4(x)
    J6 = build_J6(z)
    J8 = build_J8(s)
    J9 = build_J9(x)
    J13 = build_J13(x)

    Jrow1 = np.hstack((J1, J2, J3, J4))
    Jrow2 = np.hstack((J5, J6, J7, J8))
    Jrow3 = np.hstack((J9, J10, J11, J12))
    Jrow4 = np.hstack((J13, J14, J15, J16))

    J = np.vstack((Jrow1, Jrow2, Jrow3, Jrow4))

    print(i)

    vf1 = build_f1(x, y, z)
    vf2 = build_f2(s, z)
    vf3 = build_f3(x)
    vf4 = build_f4(x, s)

    fvec = np.hstack((vf1, vf2, vf3, vf4))

    Ax = - np.linalg.inv(J) @ fvec

    Axx = Ax[:4]
    Ass = Ax[4:4+n_h]
    Ayy = Ax[4+n_h:4+n_h+n_g]
    Azz = Ax[4+n_h+n_g:]

    # asmax = calc_as(x, Axx, s, Ass)  # not working!?
    # azmax = calc_as(y, Ayy, z, Azz)

    asmax = 1.0
    azmax = 0.5

    x[:] += asmax * Axx
    s[:] += asmax * Ass
    y[:] += azmax * Ayy
    z[:] += azmax * Azz

    mu *= 0.6

    print('x', x)
    print('s', s)
    print('y', y)
    print('z', z)
    print('Errors: ', abs(fvec))

    print(g_q2(x))
    print(g_p3(x))
    print(g_q3(x))

    print(h_i12(x))
    print(h_i23(x))
    print(h_i31(x))
    print(h_vl2(x))
    print(h_vl3(x))
    print(h_vu2(x))
    print(h_vu3(x))

    e2, e3, f2, f3 = x[:]
    P1 = g * (e1 * (2 * e1 - e2 - e3) - f1 * (-2 * f1 + f2 + f3)) + b * (e1 * (-2 * f1 + f2 + f3) + f1 * (2 * e1 - e2 - e3))
    P2 = g * (e2 * (2 * e2 - e1 - e3) - f2 * (-2 * f2 + f1 + f3)) + b * (e2 * (-2 * f2 + f1 + f3) + f2 * (2 * e2 - e1 - e3))
    print('P1: ', P1)
    print('P2: ', P2)



# if __name__ == "__main__":
#     xx = [1.0, 1.01, 0.2, 0.0]
#     yy = [1.0]*3
#     zz = [1.0]*7
#     # Jj3 = build_J3(xx)
#     Jj1 = build_J1(xx, yy, zz)
#     print('done')