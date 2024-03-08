# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
from numpy import pi, log, sqrt
from matplotlib import pyplot as plt

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Branches.wire import Wire

"""
Equations source:
a) ATP-EMTP theory book

Typical values of earth 
10 Ω/m3 - Resistivity of swampy ground 
100 Ω/m3 - Resistivity of average damp earth 
1000 Ω/m3 - Resistivity of dry earth 
"""


class WireInTower:

    def __init__(self, wire: Wire, xpos=0, ypos=0, phase=1):
        """
        Wire in a tower
        :param wire: Wire instance
        :param xpos: x position in m
        :param ypos: y position in m
        :param phase: 0->Neutral, 1->A, 2->B, 3->C
        """
        self.wire = wire

        self.name = wire.name

        self.xpos = xpos

        self.ypos = ypos

        self.phase = phase

        self.device_type = DeviceType.WireDevice


class OverheadLineType(EditableDevice):

    def __init__(self, name='Tower', idtag=None):
        """
        Overhead line editor
        :param name: name
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code='',
                                device_type=DeviceType.OverheadLineTypeDevice)

        # list of wires in the tower
        self.wires_in_tower = list()

        self.Vnom = 1.0

        # properties
        # self.tower_name = name
        self.earth_resistivity = 100
        self.frequency = 50

        # total series impedance (positive sequence)
        self.R1 = 0.0
        self.X1 = 0.0

        # total shunt admittance (positive sequence)
        self.Bsh1 = 0.0

        # total series impedance (positive sequence)
        self.R0 = 0.0
        self.X0 = 0.0

        # total shunt admittance (positive sequence)
        self.Bsh0 = 0.0

        # current rating of the tower in kA
        self.Imax = 0.0

        # impedances
        self.z_abcn = None
        self.z_phases_abcn = None
        self.z_abc = None
        self.z_phases_abc = None
        self.z_seq = None

        self.y_abcn = None
        self.y_phases_abcn = None
        self.y_abc = None
        self.y_phases_abc = None
        self.y_seq = None

        # wire properties for edition (do not confuse with the properties of this very object...)
        self.header = ['Wire', 'X (m)', 'Y (m)', 'Phase']
        self.index_prop = {0: 'name', 1: 'xpos', 2: 'ypos', 3: 'phase'}
        self.converter = {0: str, 1: float, 2: float, 3: int}
        self.editable_wire = [False, True, True, True]

        self.register(key='earth_resistivity', units='Ohm/m3', tpe=float, definition='Earth resistivity')
        self.register(key='frequency', units='Hz', tpe=float, definition='Frequency')
        self.register(key='R1', units='Ohm/km', tpe=float, definition='Positive sequence resistance')
        self.register(key='X1', units='Ohm/km', tpe=float, definition='Positive sequence reactance')
        self.register(key='Bsh1', units='uS/km', tpe=float, definition='Positive sequence shunt susceptance')
        self.register(key='R0', units='Ohm/km', tpe=float, definition='Zero-sequence resistance')
        self.register(key='X0', units='Ohm/km', tpe=float, definition='Zero sequence reactance')
        self.register(key='Bsh0', units='uS/km', tpe=float, definition='Zero sequence shunt susceptance')
        self.register(key='Imax', units='kA', tpe=float, definition='Current rating of the tower', old_names=['rating'])
        self.register(key='Vnom', units='kV', tpe=float, definition='Voltage rating of the line')

    def add_wire(self, w: WireInTower):
        """

        :param w:
        :return:
        """
        self.wires_in_tower.append(w)

    def z_series(self):
        """
        positive sequence series impedance in Ohm per unit of length
        """
        return self.R1 + 1j * self.X1

    def z0_series(self):
        """
        zero sequence series impedance in Ohm per unit of length
        """
        return self.R0 + 1j * self.X0

    def z2_series(self):
        """
        negative sequence series impedance in Ohm per unit of length
        """
        return self.R0 + 1j * self.X0

    def y_shunt(self):
        """
        positive sequence shunt admittance in S per unit of length
        """
        return 1j * self.Bsh1

    def y0_shunt(self):
        """
        zero sequence shunt admittance in S per unit of length
        """
        return 1j * self.Bsh0

    def y2_shunt(self):
        """
        negative sequence shunt admittance in S per unit of length
        """
        return 1j * self.Bsh0

    def plot(self, ax=None):
        """
        Plot wires position
        :param ax: Axis object
        """
        if ax is None:
            fig = plt.Figure(figsize=(12, 6))
            ax = fig.add_subplot(1, 1, 1)

        n = len(self.wires_in_tower)

        if n > 0:
            x = np.zeros(n)
            y = np.zeros(n)
            for i, wire in enumerate(self.wires_in_tower):
                x[i] = wire.xpos
                y[i] = wire.ypos

            ax.plot(x, y, '.')
            ax.set_title('Tower wire position')
            ax.set_xlabel('m')
            ax.set_ylabel('m')
            ax.set_xlim([min(0, np.min(x) - 1), np.max(x) + 1])
            ax.set_ylim([0, np.max(y) + 1])
            ax.patch.set_facecolor('white')
            ax.grid(False)
            ax.grid(which='major', axis='y', linestyle='--')
        else:
            # there are no wires
            pass

    def check(self, logger=Logger()):
        """
        Check that the wires configuration make sense
        :return:
        """

        all_y_zero = True
        phases = set()
        for i, wire_i in enumerate(self.wires_in_tower):

            phases.add(wire_i.phase)

            if wire_i.ypos != 0.0:
                all_y_zero = False

            if wire_i.wire.gmr < 0:
                logger.add('The wires' + wire_i.name + '(' + str(i) + ') has GRM=0 which is impossible.')
                return False

            for j, wire_j in enumerate(self.wires_in_tower):

                if i != j:
                    if wire_i.xpos == wire_j.xpos and wire_i.ypos == wire_j.ypos:
                        logger.add('The wires' + wire_i.name + '(' + str(i) + ') and ' +
                                   wire_j.name + '(' + str(j) + ') have the same position which is impossible.')
                        return False
                else:
                    pass

        if all_y_zero:
            logger.add('All the vertical coordinates (y) are exactly zero.\n'
                       'If this is correct, try a very small value.')
            return False

        if len(phases) == 1:
            logger.add('All the wires are in the same phase!')
            return False

        return True

    def compute_rating(self):
        """
        Compute the sum of the wires max current in A
        :return: max current iof the tower in A
        """
        r = 0
        for wire in self.wires_in_tower:
            r += wire.wire.max_current

        return r

    def compute(self):
        """
        Compute the tower matrices
        :return:
        """
        # heck the wires configuration
        all_ok = self.check()

        if all_ok:
            # Impedances
            self.z_abcn, \
                self.z_phases_abcn, \
                self.z_abc, \
                self.z_phases_abc, \
                self.z_seq = calc_z_matrix(self.wires_in_tower, f=self.frequency, rho=self.earth_resistivity)

            # Admittances
            self.y_abcn, \
                self.y_phases_abcn, \
                self.y_abc, \
                self.y_phases_abc, \
                self.y_seq = calc_y_matrix(self.wires_in_tower, f=self.frequency, rho=self.earth_resistivity)

            # compute the tower rating in kA
            self.Imax = self.compute_rating()

            self.R0 = self.z_seq[0, 0].real
            self.X0 = self.z_seq[0, 0].imag
            self.Bsh0 = self.y_seq[0, 0].imag * 1e6

            self.R1 = self.z_seq[1, 1].real
            self.X1 = self.z_seq[1, 1].imag
            self.Bsh1 = self.y_seq[1, 1].imag * 1e6
        else:
            pass

    def is_used(self, wire):
        """

        :param wire:
        :return:
        """
        n = len(self.wires_in_tower)
        for i in range(n - 1, -1, -1):
            if self.wires_in_tower[i].wire.name == wire.name:
                return True

    def get_values(self, Sbase, length):
        """

        :param Sbase:
        :param length:
        :return:
        """
        Vn = self.Vnom
        Zbase = (Vn * Vn) / Sbase
        Ybase = 1 / Zbase

        z1 = self.z_series() * length / Zbase
        y1 = self.y_shunt() * length * -1e6 / Ybase
        R1 = np.round(z1.real, 6)
        X1 = np.round(z1.imag, 6)
        B1 = np.round(y1.imag, 6)

        z0 = self.z0_series() * length / Zbase
        y0 = self.y0_shunt() * length * -1e6 / Ybase
        R0 = np.round(z0.real, 6)
        X0 = np.round(z0.imag, 6)
        B0 = np.round(y0.imag, 6)

        z2 = self.z2_series() * length / Zbase
        y2 = self.y2_shunt() * length * -1e6 / Ybase

        # get the rating in MVA = kA * kV
        rate = self.Imax * Vn * np.sqrt(3)

        return R1, X1, B1, R0, X0, B0, rate

    def __str__(self):
        return self.name


def get_d_ij(xi, yi, xj, yj):
    """
    Distance module between wires
    :param xi: x position of the wire i
    :param yi: y position of the wire i
    :param xj: x position of the wire j
    :param yj: y position of the wire j
    :return: distance module
    """

    return sqrt((xi - xj) ** 2 + (yi - yj) ** 2)


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
    if mat.shape == (3, 3):
        a = np.exp(2j * np.pi / 3)
        a2 = a * a
        A = np.array([[1, 1, 1], [1, a2, a], [1, a, a2]])
        Ainv = (1.0 / 3.0) * np.array([[1, 1, 1], [1, a, a2], [1, a2, a]])
        return Ainv.dot(mat).dot(A)
    else:
        return np.zeros((3, 3))


def kron_reduction(mat, keep, embed):
    """
    Perform the Kron reduction
    :param mat: primitive matrix
    :param keep: indices to keep
    :param embed: indices to remove / embed
    :return:
    """
    Zaa = mat[np.ix_(keep, keep)]
    Zag = mat[np.ix_(keep, embed)]
    Zga = mat[np.ix_(embed, keep)]
    Zgg = mat[np.ix_(embed, embed)]

    return Zaa - Zag.dot(np.linalg.inv(Zgg)).dot(Zga)


def wire_bundling(phases_set, primitive, phases_vector):
    """
    Algorithm to bundle wires per phase
    :param phases_set: set of phases (list with unique occurrences of each phase values, i.e. [0, 1, 2, 3])
    :param primitive: Primitive matrix to reduce by bundling wires
    :param phases_vector: Vector that contains the phase of each wire
    :return: reduced primitive matrix, corresponding phases
    """
    for phase in phases_set:

        # get the list of wire indices
        wires_indices = np.where(phases_vector == phase)[0]

        if len(wires_indices) > 1:

            # get the first wire and remove it from the wires list
            i = wires_indices[0]

            # wires to keep
            a = np.r_[i, np.where(phases_vector != phase)[0]]

            # wires to reduce
            g = wires_indices[1:]

            # column subtraction
            for k in g:
                primitive[:, k] -= primitive[:, i]

            # row subtraction
            for k in g:
                primitive[k, :] -= primitive[i, :]

            # kron - reduction to Zabcn
            primitive = kron_reduction(mat=primitive, keep=a, embed=g)

            # reduce the phases too
            phases_vector = phases_vector[a]

        else:
            # only one wire in this phase: nothing to do
            pass

    return primitive, phases_vector


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
        z_prim[i, i] = z_ii(r_i=wire_i.wire.r, x_i=wire_i.wire.x, h_i=wire_i.ypos, gmr_i=wire_i.wire.gmr, f=f, rho=rho)

        # mutual impedances
        for j, wire_j in enumerate(wires):

            if i != j:
                #  mutual impedance
                d_ij = get_d_ij(wire_i.xpos, wire_i.ypos, wire_j.xpos, wire_j.ypos)

                z_prim[i, j] = z_ij(x_i=wire_i.xpos, x_j=wire_j.xpos,
                                    h_i=wire_i.ypos + 1e-12, h_j=wire_j.ypos + 1e-12,
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

    # wire bundling
    z_abcn, phases_abcn = wire_bundling(phases_set=phases_set, primitive=z_abcn, phases_vector=phases_abcn)

    # kron - reduction to Zabc
    a = np.where(phases_abcn != 0)[0]
    g = np.where(phases_abcn == 0)[0]
    z_abc = kron_reduction(mat=z_abcn, keep=a, embed=g)

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

    # Maxwell's potential matrix
    p_prim = np.zeros((n, n), dtype=complex)

    # dictionary with the wire indices per phase
    phases_set = set()

    # 1 / (2 * pi * e0) in km/F
    e_air = 1.00058986
    e_0 = 8.854187817e-9  # F/km
    e = e_0 * e_air
    one_two_pi_e0 = 1 / (2 * pi * e)  # km/F

    phases_abcn = np.zeros(n, dtype=int)

    for i, wire_i in enumerate(wires):

        # self impedance
        if wire_i.ypos > 0:
            p_prim[i, i] = one_two_pi_e0 * log(2 * wire_i.ypos / (wire_i.wire.gmr + 1e-12))
        else:
            p_prim[i, i] = 0
            print(wire_i.name, 'has y=0 !')

            # mutual impedances
        for j, wire_j in enumerate(wires):

            if i != j:
                #  mutual impedance
                d_ij = get_d_ij(wire_i.xpos, wire_i.ypos + 1e-12, wire_j.xpos, wire_j.ypos + 1e-12)

                D_ij = get_D_ij(wire_i.xpos, wire_i.ypos + 1e-12, wire_j.xpos, wire_j.ypos + 1e-12)

                p_prim[i, j] = one_two_pi_e0 * log(D_ij / d_ij)

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

    # wire bundling
    p_abcn, phases_abcn = wire_bundling(phases_set=phases_set, primitive=p_abcn, phases_vector=phases_abcn)

    # kron - reduction to Zabc
    a = np.where(phases_abcn != 0)[0]
    g = np.where(phases_abcn == 0)[0]
    p_abc = kron_reduction(mat=p_abcn, keep=a, embed=g)

    # reduce the phases too
    phases_abc = phases_abcn[a]

    # compute the admittance matrices
    w = 2 * pi * f
    y_abcn = 1j * w * np.linalg.inv(p_abcn)
    y_abc = 1j * w * np.linalg.inv(p_abc)

    # compute the sequence components
    y_seq = abc_2_seq(y_abc)

    return y_abcn, phases_abcn, y_abc, phases_abc, y_seq
