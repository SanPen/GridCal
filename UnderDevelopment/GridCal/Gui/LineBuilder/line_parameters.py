from numpy import pi, cos, sin, log, arccos, sqrt, exp
import numpy as np

"""
Equations source:
a) ATP-EMTP theory book

Typical values of earth 
10 Ω/​m3 - Resistivity of swampy ground 
100 Ω/​m3 - Resistivity of average damp earth 
1000 Ω/​m3 - Resistivity of dry earth 
"""


class Wire:

    def __init__(self, name, xpos, ypos, gmr, r, x, phase=0):
        """
        Wire definition
        :param name: Name of the wire type
        :param x: x position (m)
        :param y: y position (m)
        :param gmr: Geometric Mean Radius (m)
        :param r: Resistance per unit length (Ohm / km)
        :param r: Reactance per unit length (Ohm / km)
        :param phase: 0->Neutral, 1->A, 2->B, 3->C
        """
        self.name = name
        self.xpos = xpos
        self.ypos = ypos
        self.r = r
        self.x = x
        self.gmr = gmr
        self.phase = phase

    def copy(self):
        """
        Copy of the wire
        :return:
        """
        return Wire(self.name, self.x, self.y, self.gmr, self.r, self.phase)


def z_ij_EMTP(n, x_i, x_j, h_i, h_j, D_ij, f, rho):

    sgn = np.zeros(n)

    a = 4 * pi * sqrt(5) * 1e-4 * D_ij * sqrt(f / rho)
    b = np.zeros(n)
    c = np.zeros(n)
    d = np.zeros(n)

    P = np.zeros(n)
    Q = np.zeros(n)

    b[1] = sqrt(2) / 6  # b1
    b[2] = 1 / 16  # b2

    c[2] = log(2 / 1.7811) + 1 + 1/2 - 1/4

    cos_theta_ij = (h_i + h_j) / D_ij
    sin_theta_ij = (x_i - x_j) / D_ij

    P[0] = pi / 8
    Q[0] = 1/2 * (1 / 2 + log(2 / exp(0.57722)))

    for i in range(1, n):

        sgn[i] = pow(-1, ((i+1)/2) % 2)

        d[i] = b[i] * pi / 4

        if i > 1:
            b[i] = sgn[i] * b[i-2] / (i * (i + 2))

            c[i] = c[i-2] + 1 / i + 1 / (i+2)

    if a <= 5:

        a_i_cos_i = pow(a, i-1)


def get_d_ij(xi, yi, xj, yj):
    """
    Distance module between wires
    :param xi: x position of the wire i
    :param yi: y position of the wire i
    :param xj: x position of the wire j
    :param yj: y position of the wire j
    :return: distance module
    """

    return sqrt((xi - xj)**2 + (yi - yj)**2)


def get_D_ij(xi, yi, xj, yj):
    """
    Distance module between the wire i and the image of the wire j
    :param xi: x position of the wire i
    :param yi: y position of the wire i
    :param xj: x position of the wire j
    :param yj: y position of the wire j
    :return: Distance module between the wire i and the image of the wire j
    """
    return sqrt((xi - xj) ** 2 + (yi + yj) ** 2)


def z_ii(r_i, x_i, h_i, gmr_i, f, rho):
    """
    Self impedance
    Formula 4.3 from ATP-EMTP theory book
    :param r_i: wire resistance
    :param x_i: wire reactance
    :param h_i: wire vertical position (m)
    :param gmr_i: wire geometric mean radius (m)
    :param f: system frequency (Hz)
    :param rho: earth resistivity (Ohm / m^3)
    :return: self impedance in Ohm / m
    """
    w = 2 * pi * f  # rad

    mu_0 = 4 * pi * 1e-4  # H/km

    mu_0_2pi = 2e-4  # H/km

    p = sqrt(rho / (1j * w * mu_0))

    z = r_i + 1j * (w * mu_0_2pi * log((2 * (h_i + p)) / gmr_i) + x_i)

    return z


def z_ij(x_i, x_j, h_i, h_j, d_ij, f, rho):
    """
    Mutual impedance
    Formula 4.4 from ATP-EMTP theory book
    :param x_i: wire i horizontal position (m)
    :param x_j: wire j horizontal position (m)
    :param h_i: wire i vertical position (m)
    :param h_j: wire j vertical position (m)
    :param d_ij: Distance module between the wires i and j
    :param f: system frequency (Hz)
    :param rho: earth resistivity (Ohm / m^3)
    :return: mutual impedance in Ohm / m
    """
    w = 2 * pi * f  # rad

    mu_0 = 4 * pi * 1e-4  # H/km

    mu_0_2pi = 2e-4  # H/km

    p = sqrt(rho / (1j * w * mu_0))

    z = 1j * w * mu_0_2pi * log(sqrt(pow(h_i + h_j + 2 * p, 2) + pow(x_i - x_j, 2)) / d_ij)

    return z


def abc_2_seq(mat):
    """
    Convert to sequence components
    Args:
        mat:

    Returns:

    """
    a = np.exp(2j * np.pi / 3)
    a2 = a * a
    A = np.array([[1, 1, 1], [1, a2, a], [1, a, a2]])
    Ainv = (1.0 / 3.0) * np.array([[1, 1, 1], [1, a, a2], [1, a2, a]])
    return Ainv.dot(mat).dot(A)


def calc_z_matrix(wires: list, f=50, rho=100):
    """
    Impedance matrix
    :param wires: list of wire objects
    :param f: system frequency (Hz)
    :param rho: earth resistivity
    :return: 4 by 4 impedance matrix where the order of the phases is: N, A, B, C
    """

    n = len(wires)
    z_prim = np.zeros((n, n), dtype=complex)

    # dictionary with the wire indices per phase
    phases_set = set()

    phases_abcn = np.zeros(n, dtype=int)

    for i, wire_i in enumerate(wires):

        # self impedance
        z_prim[i, i] = z_ii(r_i=wire_i.r, x_i=wire_i.x, h_i=wire_i.ypos, gmr_i=wire_i.gmr, f=f, rho=rho)

        # mutual impedances
        for j, wire_j in enumerate(wires):

            if i != j:
                #  mutual impedance
                d_ij = get_d_ij(wire_i.xpos, wire_i.ypos, wire_j.xpos, wire_j.ypos)

                # D_ij = get_D_ij(wire_i.xpos, wire_i.ypos, wire_j.xpos, wire_j.ypos)

                z_prim[i, j] = z_ij(x_i=wire_i.xpos, x_j=wire_j.xpos,
                                    h_i=wire_i.ypos, h_j=wire_j.ypos,
                                    d_ij=d_ij, f=f, rho=rho)

            else:
                # they are the same wire and it is already accounted in the self impedance
                pass

        # account for the phase
        phases_set.add(wire_i.phase)
        phases_abcn[i] = wire_i.phase

    # bundle the phases
    z_abcn = z_prim.copy()

    # sort the phases vector
    phases_set = list(phases_set)
    phases_set.sort(reverse=True)

    for phase in phases_set:

        # get the list of wire indices
        wires_indices = np.where(phases_abcn == phase)[0]

        if len(wires_indices) > 1:

            # get the first wire and remove it from the wires list
            i = wires_indices[0]

            # wires to keep
            a = np.r_[i, np.where(phases_abcn != phase)[0]]

            # wires to reduce
            g = wires_indices[1:]

            # column subtraction
            for k in g:
                z_abcn[:, k] -= z_abcn[:, i]

            # row subtraction
            for k in g:
                z_abcn[k, :] -= z_abcn[i, :]

            # kron - reduction to Zabcn
            Zaa = z_abcn[a, :][:, a]
            Zag = z_abcn[a, :][:, g]
            Zga = z_abcn[g, :][:, a]
            Zgg = z_abcn[g, :][:, g]

            z_abcn = Zaa - Zag.dot(np.linalg.inv(Zgg)).dot(Zga)

            # reduce the phases too
            phases_abcn = phases_abcn[a]

        else:
            # only one wire in this phase: nothing to do
            pass

    # kron - reduction to Zabc
    a = np.where(phases_abcn != 0)[0]
    g = np.where(phases_abcn == 0)[0]
    Zaa = z_abcn[a, :][:, a]
    Zag = z_abcn[a, :][:, g]
    Zga = z_abcn[g, :][:, a]
    Zgg = z_abcn[g, :][:, g]

    z_abc = Zaa - Zag.dot(np.linalg.inv(Zgg)).dot(Zga)

    # reduce the phases too
    phases_abc = phases_abcn[a]

    # compute the sequence components
    z_seq = abc_2_seq(z_abc)

    return z_abcn, phases_abcn, z_abc, phases_abc, z_seq


def calc_y_matrix(wires: list, f=50, rho=100):
    """
    Impedance matrix
    :param wires: list of wire objects
    :param f: system frequency (Hz)
    :param rho: earth resistivity
    :return: 4 by 4 impedance matrix where the order of the phases is: N, A, B, C
    """

    n = len(wires)
    p_prim = np.zeros((n, n), dtype=complex)

    # dictionary with the wire indices per phase
    phases_set = set()

    phases_abcn = np.zeros(n, dtype=int)

    for i, wire_i in enumerate(wires):

        # self impedance
        p_prim[i, i] = 17.975109e-6 * log(2 * wire_i.ypos / wire_i.gmr)

        # mutual impedances
        for j, wire_j in enumerate(wires):

            if i != j:
                #  mutual impedance
                d_ij = get_d_ij(wire_i.xpos, wire_i.ypos, wire_j.xpos, wire_j.ypos)

                D_ij = get_D_ij(wire_i.xpos, wire_i.ypos, wire_j.xpos, wire_j.ypos)

                p_prim[i, j] = 17.975109e-6 * log(D_ij / d_ij)

            else:
                # they are the same wire and it is already accounted in the self impedance
                pass

        # account for the phase
        phases_set.add(wire_i.phase)
        phases_abcn[i] = wire_i.phase

    # bundle the phases
    p_abcn = p_prim.copy()

    # sort the phases vector
    phases_set = list(phases_set)
    phases_set.sort(reverse=True)

    for phase in phases_set:

        # get the list of wire indices
        wires_indices = np.where(phases_abcn == phase)[0]

        if len(wires_indices) > 1:

            # get the first wire and remove it from the wires list
            i = wires_indices[0]

            # wires to keep
            a = np.r_[i, np.where(phases_abcn != phase)[0]]

            # wires to reduce
            g = wires_indices[1:]

            # column subtraction
            for k in g:
                p_abcn[:, k] -= p_abcn[:, i]

            # row subtraction
            for k in g:
                p_abcn[k, :] -= p_abcn[i, :]

            # kron - reduction to Zabcn
            Zaa = p_abcn[a, :][:, a]
            Zag = p_abcn[a, :][:, g]
            Zga = p_abcn[g, :][:, a]
            Zgg = p_abcn[g, :][:, g]

            p_abcn = Zaa - Zag.dot(np.linalg.inv(Zgg)).dot(Zga)

            # reduce the phases too
            phases_abcn = phases_abcn[a]

        else:
            # only one wire in this phase: nothing to do
            pass

    # kron - reduction to Zabc
    a = np.where(phases_abcn != 0)[0]
    g = np.where(phases_abcn == 0)[0]
    Zaa = p_abcn[a, :][:, a]
    Zag = p_abcn[a, :][:, g]
    Zga = p_abcn[g, :][:, a]
    Zgg = p_abcn[g, :][:, g]

    p_abc = Zaa - Zag.dot(np.linalg.inv(Zgg)).dot(Zga)

    # reduce the phases too
    phases_abc = phases_abcn[a]

    # compute the admittance matrices
    w = 2 * pi * f
    y_abcn = 1j * w * np.linalg.inv(p_abcn)
    y_abc = 1j * w * np.linalg.inv(p_abc)

    # compute the sequence components
    y_seq = abc_2_seq(y_abc)

    return y_abcn, phases_abcn, y_abc, phases_abc, y_seq