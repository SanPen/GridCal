from numpy import pi, cos, sin, log, arccos, sqrt
import numpy as np

"""
Equations source:
a) https://vismor.com/documents/power_systems/transmission_lines/S2.SS1.php
b) William H. Kersting - Distribution system modelling (3rd Ed.)
c) ATP-EMTP theory book

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


def p_approx(k, theta):
    """

    :param k:
    :param theta:
    :return:
    """
    a1 = pi / 8
    a2 = k * cos(theta) / (3 * sqrt(2))
    a3 = k * k * cos(2 * theta) * (0.6728 + log(2 / k)) / 16
    a4 = k * k * theta * sin(2 * theta) / 16
    a5 = k * k * k * cos(3 * theta) / (45 * sqrt(2))
    a6 = k * k * k * k * pi * cos(4 * theta) / 1536
    return a1 - a2 + a3 + a4 + a5 - a6


def q_approx(k, theta):
    """

    :param k:
    :param theta:
    :return:
    """
    a1 = 0.5 * log(2 / k)
    a2 = k * cos(theta) / (3 * sqrt(2))
    a3 = pi * k * k * cos(2 * theta) / 64
    a4 = k * k * k * cos(3 * theta) / (45 * sqrt(2))
    a5 = k * k * k * k * sin(4 * theta) / 384
    a6 = k * k * k * k * cos(4 * theta) * (1.0895 + log(2 / k)) / 384
    return -0.0386 + a1 + a2 - a3 + a4 - a5 - a6


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
    :param r_i: wire resistance
    :param h_i: wire vertical position (m)
    :param gmr_i: wire geometric mean radius (m)
    :param f: system frequency (Hz)
    :param rho: earth resistivity (Ohm / m^3)
    :return: self impedance in Ohm / m
    """
    # w = 2 * pi * f  # rad
    #
    # mu_0 = 4 * pi * 1e-7  # H/m
    #
    # k = sqrt(5) * 1000 * mu_0 * 2 * h_i * sqrt(f / rho)
    #
    # theta = 0
    #
    # p = p_approx(k, theta)
    #
    # q = q_approx(k, theta)
    #
    # z = r_i + 1j * 2 * w * log(2 * h_i / gmr_i) + 4 * w * (p + 1j * q)

    z = r_i + p + 1j * (w * mu_0 / (2 * pi) * log(2 * h_i / gmr_i) + x_i + q)

    return z


def z_ij(h_i, h_j, d_ij, D_ij, f, rho):
    """
    Mutual impedance
    :param h_i: wire i vertical position (m)
    :param h_j: wire j vertical position (m)
    :param d_ij: Distance module between the wires i and j
    :param D_ij: Distance module between the wire i and the image of the wire j
    :param f: system frequency (Hz)
    :param rho: earth resistivity (Ohm / m^3)
    :return: mutual impedance in Ohm / m
    """
    w = 2 * pi * f  # rad

    mu_0 = 4 * pi * 1e-7  # H/m

    k = sqrt(5) * 1000 * mu_0 * D_ij * sqrt(f / rho)

    theta = arccos((h_i + h_j) / D_ij)

    p = p_approx(k, theta)

    q = q_approx(k, theta)

    z = 2j * w * log(D_ij / d_ij) + 4 * w * (p + 1j * q)

    return z


def calc_z_matrix(wires: list, f=50, rho=100):
    """
    Impedance matrix
    :param wires: list of wire objects
    :param f: system frequency (Hz)
    :param rho: earth resistivity
    :return: 4 by 4 impedance matrix where the order of the phases is: N, A, B, C
    """
    z = np.zeros((4, 4), dtype=complex)

    for i, wire_i in enumerate(wires):

        # self impedance
        z[wire_i.phase, wire_i.phase] += z_ii(r_i=wire_i.r, h_i=wire_i.y, gmr_i=wire_i.gmr, f=f, rho=rho)

        for j, wire_j in enumerate(wires):

            if i != j:
                #  mutual impedance
                d_ij = get_d_ij(wire_i.xpos, wire_i.ypos, wire_j.xpos, wire_j.ypos)

                D_ij = get_D_ij(wire_i.xpos, wire_i.ypos, wire_j.xpos, wire_j.ypos)

                z[wire_i.phase, wire_j.phase] += z_ij(h_i=wire_i.y, h_j=wire_j.y, d_ij=d_ij, D_ij=D_ij, f=f, rho=rho)

            else:
                # they are the same wire and it is already accounted in the self impedance
                pass

    return z
