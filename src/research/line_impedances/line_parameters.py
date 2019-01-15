from math import pi, cos, sin, log, acos, sqrt, pow

"""
Equations source:
a) https://vismor.com/documents/power_systems/transmission_lines/S2.SS1.php
b) William H. Kersting - Distribution system modelling (3rd Ed.)


Typical values of earth 
10 Ω/​m3 - Resistivity of swampy ground 
100 Ω/​m3 - Resistivity of average damp earth 
1000 Ω/​m3 - Resistivity of dry earth 
"""






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


def z_ii(r_i, h_i, gmr_i, f, rho):
    """
    Self impedance
    :param r_i: wire resistance
    :param h_i: wire vertical position (m)
    :param gmr_i: wire geometric mean radius (m)
    :param f: system frequency (Hz)
    :param rho: earth resistivity (Ohm / m^3)
    :return: self impedance in Ohm / m
    """
    w = 2 * pi * f

    k = 4 * pi * h_i * sqrt(2 * rho * f)

    theta = 0

    p = p_approx(k, theta)

    q = q_approx(k, theta)

    z = r_i + 1j * 2 * w * log(2 * h_i / gmr_i) + 4 * w * (p + 1j * q)

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
    w = 2 * pi * f

    k = 2 * pi * D_ij * sqrt(2 * rho * f)

    theta = acos(h_i + h_j) / D_ij

    p = p_approx(k, theta)

    q = q_approx(k, theta)

    z = 2j * w * log(D_ij / d_ij) + 4 * w * (p + 1j * q)

    return z


def calc_z_matrix():
    pass