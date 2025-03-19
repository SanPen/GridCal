# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, Dict
import numpy as np
from numpy import pi, log, sqrt
from matplotlib import pyplot as plt

from GridCalEngine.basic_structures import Logger, Mat, IntVec
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Branches.wire import Wire
from GridCalEngine.enumerations import SubObjectType

"""
Equations source:
a) ATP-EMTP theory book

Typical values of earth 
10 Ω/m3 - Resistivity of swampy ground 
100 Ω/m3 - Resistivity of average damp earth 
1000 Ω/m3 - Resistivity of dry earth 
"""


class WireInTower:
    """
    Wire -> Tower association
    """

    def __init__(self, wire: Wire, xpos: float = 0.0, ypos: float = 0.0, phase: int = 1):
        """
        Wire in a tower
        :param wire: Wire instance
        :param xpos: x position in m
        :param ypos: y position in m
        :param phase: 0->Neutral, 1->A, 2->B, 3->C
        """
        self.wire: Wire = wire

        self.name: str = wire.name

        self.xpos: float = xpos

        self.ypos: float = ypos

        self._phase: int = phase

        self.circuit_index: int = 0

        self.phase_type: str = ""

        self.set_phase(phase)

        self.device_type = DeviceType.WireDevice

    def __eq__(self, other: "WireInTower"):
        return (self.wire == other.wire
                and self.xpos == other.xpos
                and self.ypos == other.ypos
                and self.phase == other.phase
                and self.circuit_index == other.circuit_index
                and self.name == other.name)

    def set_phase(self, phase: int):
        """
        Pase setter

         A    B    C   circuit_idx
        --------------------------
         1    2    3       1
         4    5    6       2
         7    8    9       3
         ...

        :param phase:
        :return: None
        """
        k = int((phase - 1) / 3)
        n_circuit = k + 1

        if phase == 0:
            self._phase = phase
            self.phase_type = "N"
            self.circuit_index = 0

        elif (phase - 1) % 3 == 0:
            self._phase = phase
            self.phase_type = "A"
            self.circuit_index = n_circuit

        elif (phase - 2) % 3 == 0:
            self._phase = phase
            self.phase_type = "B"
            self.circuit_index = n_circuit

        elif (phase - 3) % 3 == 0:
            self._phase = phase
            self.phase_type = "C"
            self.circuit_index = n_circuit

        else:
            print("Cannot recognize the phase...")

    @property
    def phase(self):
        return self._phase

    @phase.setter
    def phase(self, phase: int):
        """
        Pase setter
        :param phase: phase number
        """
        self.set_phase(phase)

    def to_dict(self) -> Dict[str, str | float | int]:
        """
        data to dict
        :return: json like dictionary
        """
        return {
            "wire": self.wire.idtag,
            "name": self.name,
            "xpos": self.xpos,
            "ypos": self.ypos,
            "phase": self.phase,
            "circuit_index": self.circuit_index,
        }

    def parse(self, data: Dict[str, str | float | int], wire_dict: dict[str, Wire]):
        """
        Parse data from json dictionary
        :param data: data to parse
        :param wire_dict: wires dictionary
        :return:
        """
        self.wire: Wire = wire_dict.get(data["wire"])
        self.name: str = data["name"]
        self.xpos: float = data["xpos"]
        self.ypos: float = data["ypos"]
        self.phase: int = data["phase"]
        self.circuit_index: int = data.get("circuit_index", 1)


class ListOfWires:

    def __init__(self):
        self.data: List[WireInTower] = list()

    def append(self, elm: WireInTower):
        self.data.append(elm)

    def to_list(self):
        """
        Generate list of WireInTower objects
        :return:
        """
        return [e.to_dict() for e in self.data]

    def parse(self, data: List[Dict[str, str | float | int]], wire_dict: dict[str, Wire]):
        """
        Parse data from json dictionary
        :param data:
        :param wire_dict:
        :return:
        """
        for entry in data:
            elm = WireInTower(
                wire=wire_dict.get(entry["wire"]),
                xpos=entry["xpos"],
                ypos=entry["ypos"],
                phase=entry["phase"]
            )

            elm.parse(entry, wire_dict)
            self.append(elm)

    def get_phases(self):
        """
        Get the introduced phases
        :return: list of phase numbers
        """
        x = set()
        for entry in self.data:
            x.add(entry.phase)
        return list(x)

    def get_circuits(self):
        """
        Get the introduced circuits
        :return: list of circuit numbers
        """
        x = set()
        for entry in self.data:
            x.add(entry.circuit_index)
        return list(x)

    def __eq__(self, other: "ListOfWires"):
        """
        Equality operator
        :param other:
        :return:
        """
        if len(self.data) != len(other.data):
            return False

        for elm, other_elm in zip(self.data, other.data):
            if elm != other_elm:
                return False

        return True


class OverheadLineType(EditableDevice):

    def __init__(self, name='Tower', idtag: str | None = None,
                 Vnom: float = 1.0,
                 earth_resistivity: float = 100,
                 frequency: float = 50):
        """
        Overhead line editor
        :param name: name
        :param idtag:
        :param Vnom: Nominal voltage (kV)
        :param earth_resistivity: Earth resistivity (ohm/m3)
        :param frequency: system frequency (Hz)
        """
        super().__init__(name=name,
                         idtag=idtag,
                         code='',
                         device_type=DeviceType.OverheadLineTypeDevice)

        # list of wires in the tower
        self.wires_in_tower: ListOfWires = ListOfWires()

        # nominal voltage
        self.Vnom = Vnom  # kV

        self.earth_resistivity = earth_resistivity  # ohm/m3

        self.frequency = frequency  # Hz

        # current rating of the tower in kA
        self.Imax = 0.0

        # impedances
        self.z_abcn = None
        self.z_phases_abcn = None
        self.z_abc = None
        self.z_phases_abc = None
        self.z_seq = None
        self.z_0123 = None

        self.y_abcn = None
        self.y_phases_abcn = None
        self.y_abc = None
        self.y_phases_abc = None
        self.y_seq = None
        self.y_0123 = None

        # wire properties for edition (do not confuse with the properties of this very object...)
        self.header = ['Wire', 'X (m)', 'Y (m)', 'Phase', "Circuit Index", "Phase name"]
        self.index_prop = {0: 'name', 1: 'xpos', 2: 'ypos', 3: 'phase', 4: 'circuit_index', 5: 'phase_type'}
        self.converter = {0: str, 1: float, 2: float, 3: int, 4: int, 5: str}
        self.editable_wire = [False, True, True, True, False, False]

        self.register(key='earth_resistivity', units='Ohm/m3', tpe=float, definition='Earth resistivity')
        self.register(key='frequency', units='Hz', tpe=float, definition='Frequency')
        # self.register(key='R1', units='Ohm/Km', tpe=float, definition='Positive sequence resistance')
        # self.register(key='X1', units='Ohm/Km', tpe=float, definition='Positive sequence reactance')
        # self.register(key='Bsh1', units='uS/Km', tpe=float, definition='Positive sequence shunt susceptance')
        # self.register(key='R0', units='Ohm/Km', tpe=float, definition='Zero-sequence resistance')
        # self.register(key='X0', units='Ohm/Km', tpe=float, definition='Zero sequence reactance')
        # self.register(key='Bsh0', units='uS/Km', tpe=float, definition='Zero sequence shunt susceptance')
        self.register(key='Imax', units='kA', tpe=float, definition='Current rating of the tower', old_names=['rating'])
        self.register(key='Vnom', units='kV', tpe=float, definition='Voltage rating of the line')

        self.register(key='wires_in_tower', units='', tpe=SubObjectType.ListOfWires, definition='List of wires',
                      editable=False, display=False)

    def get_ys(self, circuit_idx: int, Sbase: float, length: float, Vnom: float):
        """
        get the series admittance matrix in p.u. (total)
        :param circuit_idx: Circuit index (starting by 0)
        :param Sbase: Base power (MVA)
        :param length: Line length (km)
        :param Vnom: Nominal voltage (kV)
        :return: Series admittance in p.u.
        """
        Zbase = (Vnom * Vnom) / Sbase

        k = (3 * circuit_idx) + np.array([0, 1, 2])
        z = self.z_abc[np.ix_(k, k)] * length / Zbase
        y = np.linalg.inv(z)
        return y

    def get_ysh(self, circuit_idx: int, Sbase: float, length: float, Vnom: float):
        """
        get the shunt admittance matrix in p.u. (total)
        :param circuit_idx: Circuit index (starting by 0)
        :param Sbase: Base power (MVA)
        :param length: Line length (km)
        :param Vnom: Nominal voltage (kV)
        :return: Shunt admittance in p.u.
        """
        Zbase = (Vnom * Vnom) / Sbase
        Ybase = 1 / Zbase
        k = (3 * circuit_idx) + np.array([0, 1, 2])
        y = self.y_abc[np.ix_(k, k)] * length * -1e6 / Ybase
        return y

    def add_wire_relationship(self, wire: Wire,
                              xpos: float = 0.0,
                              ypos: float = 0.0,
                              phase: int = 1):
        """
        Wire in a tower
        :param wire: Wire instance
        :param xpos: x position in m
        :param ypos: y position in m
        :param phase: 0->Neutral, 1->A, 2->B, 3->C
        """
        w = WireInTower(wire=wire, xpos=xpos, ypos=ypos, phase=phase)
        self.wires_in_tower.append(w)

    # def z_series(self):
    #     """
    #     positive sequence series impedance in Ohm per unit of length
    #     """
    #     return self.R1 + 1j * self.X1
    #
    # def z0_series(self):
    #     """
    #     zero sequence series impedance in Ohm per unit of length
    #     """
    #     return self.R0 + 1j * self.X0
    #
    # def z2_series(self):
    #     """
    #     negative sequence series impedance in Ohm per unit of length
    #     """
    #     return self.R0 + 1j * self.X0
    #
    # def y_shunt(self):
    #     """
    #     positive sequence shunt admittance in S per unit of length
    #     """
    #     return 1j * self.Bsh1
    #
    # def y0_shunt(self):
    #     """
    #     zero sequence shunt admittance in S per unit of length
    #     """
    #     return 1j * self.Bsh0
    #
    # def y2_shunt(self):
    #     """
    #     negative sequence shunt admittance in S per unit of length
    #     """
    #     return 1j * self.Bsh0

    def plot(self, ax=None):
        """
        Plot wires position
        :param ax: Axis object
        """
        if ax is None:
            fig = plt.Figure(figsize=(12, 6))
            ax = fig.add_subplot(1, 1, 1)

        n = len(self.wires_in_tower.data)

        if n > 0:
            x = np.zeros(n)
            y = np.zeros(n)
            for i, wire_tower in enumerate(self.wires_in_tower.data):
                x[i] = wire_tower.xpos
                y[i] = wire_tower.ypos

            ax.plot(x, y, '.')
            ax.set_title('Tower wire position', fontsize=14)
            ax.set_xlabel('m', fontsize=8)
            ax.set_ylabel('m', fontsize=8)
            ax.tick_params(axis='x', labelsize=8)
            ax.tick_params(axis='y', labelsize=8)
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
        for i, wire_i in enumerate(self.wires_in_tower.data):

            phases.add(wire_i.phase)

            if wire_i.ypos != 0.0:
                all_y_zero = False

            if wire_i.wire.GMR < 0:
                logger.add('The wires' + wire_i.name + '(' + str(i) + ') has GRM=0 which is impossible.')
                return False

            for j, wire_j in enumerate(self.wires_in_tower.data):

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

        # if there is a phase, all the preceding ones must be present too
        mx = max(phases)
        missing_phases = False
        for i in range(1, mx):
            if i not in phases:
                logger.add('Missing phase', value=i)
                missing_phases = True

        if missing_phases:
            return False

        return True

    def compute_rating(self):
        """
        Compute the sum of the wires max current in A
        :return: max current (I) of the tower in A
        """
        r = 0
        for wit in self.wires_in_tower.data:
            r += wit.wire.max_current

        return r

    def compute(self):
        """
        Compute the tower matrices
        :return:
        """
        # check the wires configuration
        all_ok = self.check()

        if all_ok:
            try:
                # Impedances
                (self.z_abcn,
                 self.z_phases_abcn,
                 self.z_abc,
                 self.z_phases_abc,
                 self.z_seq) = calc_z_matrix(self.wires_in_tower, f=self.frequency, rho=self.earth_resistivity)

                # Admittances
                (self.y_abcn,
                 self.y_phases_abcn,
                 self.y_abc,
                 self.y_phases_abc,
                 self.y_seq) = calc_y_matrix(self.wires_in_tower, f=self.frequency, rho=self.earth_resistivity)

                # compute the tower rating in kA
                self.Imax = self.compute_rating()

            except np.linalg.LinAlgError as e:
                print(e)

        else:
            pass

    def is_used(self, wire):
        """

        :param wire:
        :return:
        """
        n = len(self.wires_in_tower.data)
        for i in range(n - 1, -1, -1):
            if self.wires_in_tower.data[i].wire.name == wire.name:
                return True

    def get_sequence_values(self, circuit_idx: int, seq: int = 1):
        """
        Get the positive sequence values R1 [Ohm], X1[Ohm] and Bsh1 [S].
        :param circuit_idx: Circuit indexation (starts at 0)
        :param seq: Sequence number (0, 1, 2)
        :return: R1 [Ohm], X1[Ohm] and Bsh1 [S]
        """
        a1 = 3 * circuit_idx + seq
        R1 = self.z_seq[a1, a1].real
        X1 = self.z_seq[a1, a1].imag
        Bsh1 = self.y_seq[a1, a1].imag * 1e6
        return R1, X1, Bsh1

    def get_values(self, Sbase, length, circuit_index: int = 1, round_vals: bool = False, Vnom: float | None = None):
        """
        Get the sequence values of the template
        :param Sbase: Base power
        :param length: Length of the line
        :param circuit_index: index of the circuit
        :param round_vals: Boolean to round parameter values
        :param Vnom: nominal voltage for the per unit calculation (kV)
        :return: Line parameters and rate
        """

        Vn = self.Vnom if Vnom is None else Vnom
        Zbase = (Vn * Vn) / Sbase
        Ybase = 1 / Zbase

        a0 = 3 * circuit_index
        R0 = self.z_seq[a0, a0].real
        X0 = self.z_seq[a0, a0].imag
        Bsh0 = self.y_seq[a0, a0].imag * 1e6

        a1 = 3 * circuit_index + 1
        R1 = self.z_seq[a1, a1].real
        X1 = self.z_seq[a1, a1].imag
        Bsh1 = self.y_seq[a1, a1].imag * 1e6

        z1 = (R1 + 1j * X1) * length / Zbase
        y1 = 1j * Bsh1 * length * -1e6 / Ybase

        z0 = (R0 + 1j * X0) * length / Zbase
        y0 = 1j * Bsh0 * length * -1e6 / Ybase

        if round_vals:
            R1 = np.round(z1.real, 6)
            X1 = np.round(z1.imag, 6)
            B1 = np.round(y1.imag, 6)

            R0 = np.round(z0.real, 6)
            X0 = np.round(z0.imag, 6)
            B0 = np.round(y0.imag, 6)

        else:
            R1 = z1.real
            X1 = z1.imag
            B1 = y1.imag

            R0 = z0.real
            X0 = z0.imag
            B0 = y0.imag

        z2 = (R0 + 1j * X0) * length / Zbase
        y2 = 1j * Bsh0 * length * -1e6 / Ybase

        # get the rating in MVA = kA * kV
        rate = self.Imax * Vn * np.sqrt(3)

        return R1, X1, B1, R0, X0, B0, rate

    def __str__(self) -> str:
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

    mu_0 = 4 * pi * 1e-4  # H/Km

    mu_0_2pi = 2e-4  # H/Km

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

    mu_0 = 4 * pi * 1e-4  # H/Km

    mu_0_2pi = 2e-4  # H/Km

    p = sqrt(rho / (1j * w * mu_0))

    z = 1j * w * mu_0_2pi * log(sqrt(pow(h_i + h_j + 2 * p, 2) + pow(x_i - x_j, 2)) / d_ij)

    return z


def abc_2_seq(mat):
    """
    Convert ABC to sequence components
    :param mat: ABC impedances matrix (3x3, 6x6, 9x9, etc...)
    Returns: Sequence matrix (3x3, 6x6, 9x9, etc...) where the 3x3 blocks are the sequences
    """
    if mat.ndim == 2:
        if mat.shape[0] == mat.shape[1]:
            if mat.shape[0] % 3 == 0:

                n_circuits = mat.shape[0] // 3
                n = mat.shape[0]
                z_seq = np.zeros((n, n), dtype=mat.dtype)

                a = np.exp(2j * np.pi / 3)
                a2 = a * a
                A = np.array([[1, 1, 1], [1, a2, a], [1, a, a2]])
                Ainv = (1.0 / 3.0) * np.array([[1, 1, 1], [1, a, a2], [1, a2, a]])

                for k in range(n_circuits):
                    i = (3 * k) + np.array([0, 1, 2])
                    j = i
                    mat_abc = mat[np.ix_(i, j)]
                    z_seq[np.ix_(i, j)] = Ainv.dot(mat_abc).dot(A)

                return z_seq
            else:
                return np.zeros_like(mat)
        else:
            return np.zeros((3, 3))
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


def wire_bundling(phases_set: List[int], primitive: Mat, phases_vector: IntVec):
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


def calc_z_matrix(wires_in_tower: ListOfWires, f=50, rho=100):
    """
    Impedance matrix
    :param wires_in_tower: WireInTower
    :param f: system frequency (Hz)
    :param rho: earth resistivity
    :return: 4 by 4 impedance matrix where the order of the phases is: N, A, B, C
    """

    n = len(wires_in_tower.data)
    z_prim = np.zeros((n, n), dtype=complex)

    # dictionary with the wire indices per phase
    phases_set = set()

    phases_abcn = np.zeros(n, dtype=int)

    for i, wire_i in enumerate(wires_in_tower.data):

        # self impedance
        z_prim[i, i] = z_ii(r_i=wire_i.wire.R,
                            x_i=wire_i.wire.X,
                            h_i=wire_i.ypos,
                            gmr_i=wire_i.wire.GMR,
                            f=f,
                            rho=rho)

        # mutual impedances
        for j, wire_j in enumerate(wires_in_tower.data):

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

    # Ordered abc matrices
    # z_0123 = z_abcn[np.ix_(phases_abcn, phases_abcn)]

    return z_abcn, phases_abcn, z_abc, phases_abc, z_seq


def calc_y_matrix(wires_in_tower: ListOfWires, f=50, rho=100):
    """
    Impedance matrix
    :param wires_in_tower: ListOfWires
    :param f: system frequency (Hz)
    :param rho: earth resistivity
    :return: 4 by 4 impedance matrix where the order of the phases is: N, A, B, C
    """

    n = len(wires_in_tower.data)

    # Maxwell's potential matrix
    p_prim = np.zeros((n, n), dtype=complex)

    # dictionary with the wire indices per phase
    phases_set = set()

    # 1 / (2 * pi * e0) in Km/F
    e_air = 1.00058986
    e_0 = 8.854187817e-9  # F/Km
    e = e_0 * e_air
    one_two_pi_e0 = 1 / (2 * pi * e)  # Km/F

    phases_abcn = np.zeros(n, dtype=int)

    for i, wire_i in enumerate(wires_in_tower.data):

        # self impedance
        if wire_i.ypos > 0:
            p_prim[i, i] = one_two_pi_e0 * log(2 * wire_i.ypos / (wire_i.wire.GMR + 1e-12))
        else:
            p_prim[i, i] = 0
            print(wire_i.name, 'has y=0 !')

            # mutual impedances
        for j, wire_j in enumerate(wires_in_tower.data):

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

    # Ordered abc matrices
    # y_0123 = y_abcn[np.ix_(phases_abcn, phases_abcn)]

    return y_abcn, phases_abcn, y_abc, phases_abc, y_seq
