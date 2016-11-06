"""
Santiago Penate Vera 2015
"""

import math
import numpy as np
import matplotlib.pyplot as plt

np.set_printoptions(linewidth=200)


def abc2seq(z_abc_matrix):
    """
    Converts the ABC impedance to 012 Impedance
    @param z_abc_matrix:
    @return:
    """
    ang = 2.0 * math.pi / 3.0  # 120 deg in radians
    a = math.cos(ang) + math.sin(ang) * 1j
    mat = np.matrix([[1, 1, 1], [1, a, a ** 2], [1, a ** 2, a]])
    mat_inv = 1.0 / 3.0 * np.matrix([[1, 1, 1], [1, a ** 2, a], [1, a, a ** 2]])

    return mat_inv * z_abc_matrix * mat


class CarsonEquations(object):
    """
    Carsosn's equations to compute a line impedance   

    See Kersting pag 83, 84
    """

    def __init__(self, frequency, earth_resistivity):
        """
        Constructor
        @param frequency:
        @param earth_resistivity:
        """
        self.G = 0.1609347e-3  # Ohm/mile
        self.freq = frequency  # Hz
        self.ro = earth_resistivity  # ohm m

        self.C1 = math.pi ** 2 * self.freq * self.G  # Ohm/mile
        self.C2 = 4 * math.pi * self.freq * self.G  # Ohm/mile
        self.C3 = 7.6786 + 0.5 * math.log(self.ro / self.freq)  # ?

    def zii(self, r_i, gmr_i):
        """
        Auto impedance
        @param r_i:
        @param gmr_i:
        @return:
        """
        return r_i + self.C1 + (self.C2 * (math.log(1.0 / gmr_i) + self.C3)) * 1j

    def zij(self, d_ij):
        """
        Mutual impedance
        @param d_ij:
        @return:
        """
        return self.C1 + (self.C2 * (math.log(1.0 / d_ij) + self.C3)) * 1j


class Conductor(object):
    """
    Simple metallic conductor

    When a conductor is displays in duplex, triplex or cuadruplex
    configurations, the GMR changes and of course the resistance
    """

    def __init__(self, name, gmr, resistance, diameter, capacity):
        """
        Constructor
        @param name:
        @param gmr: Geometric Mean Radius
        @param resistance:
        @param diameter:
        @param capacity:
        """
        self.Name = name
        self.GMR = float(gmr)
        self.r = float(resistance)
        self.d = float(diameter)
        self.Capacity = float(capacity)


class CableConcentricNeutral(object):
    """
    Cable containing distributed embedded neutral
    """

    def __init__(self, phase_conductor, neutral_conductor, number_of_neutrals, cable_diameter):
        """
        Constructor
        @param phase_conductor:
        @param neutral_conductor:
        @param number_of_neutrals:
        @param cable_diameter:
        """
        self.phase = phase_conductor
        self.neutral = neutral_conductor
        self.k = float(number_of_neutrals)
        self.d_od = float(cable_diameter)

        # calculated parameters
        self.R = (self.d_od - self.neutral.d) / 24.0  # ft (el 24 es 2*12)

        # the neutral cable is recalculated as an equivalent neutral 
        # given the number of neutrals (k)

        # See Kersting pag 102
        self.neutral.GMR = (self.neutral.GMR * self.k * self.R ** (self.k - 1)) ** (1.0 / self.k)  # ft
        self.neutral.r /= self.k  # ohm/mile


class CableTapeShield:
    """
    Cable with no neutral and with a metal inner shield
    """

    def __init__(self, phase_conductor: Conductor, tape_diameter, tape_thickness, earth_resistivity):
        """
        Constructor
        @param phase_conductor:
        @param tape_diameter:
        @param tape_thickness:
        @param earth_resistivity:
        """
        self.phase = phase_conductor
        self.d_s = float(tape_diameter)  # inches
        self.T = float(tape_thickness)  # millimetres
        self.ro = earth_resistivity  # Ohm-m

        # calculated parameters        
        self.GMR_shield = ((self.d_s / 2.0) - (self.T / 2000.0)) / 12.0  # ft
        self.r_shield = 7.9385e-8 * self.ro / (self.T * self.d_s)  # ohm/mile

        # generate the neutral equivalent to the tape
        self.neutral = Conductor('tape', self.GMR_shield, self.r_shield, 0, 0)


class UndergroundLine:
    """
    line composed of 3 phases and one neutral    
    """

    def __init__(self):
        """
        Constructor
        """
        self.conductors = list()
        self.neutrals = list()
        self.conductors_positions = list()
        self.neutrals_positions = list()

    def add_cable_concentric_neutral(self, cable: CableConcentricNeutral, x, y):
        """
        Add the phase and equiv. neutral conductors to the line set up
        @param cable:
        @param x:
        @param y:
        @return:
        """
        self.conductors.append(cable.phase)
        self.conductors_positions.append(x + y * 1j)  # the position is stored as a complex number

        self.neutrals.append(cable.neutral)
        self.neutrals_positions.append(x + (y + cable.R) * 1j)

    def add_cable_tape_shield(self, cable: CableTapeShield, x, y):
        """
        Add the phase and equiv. neutral conductors to the line set up
        @param cable:
        @param x:
        @param y:
        @return:
        """
        self.conductors.append(cable.phase)
        self.conductors_positions.append(x + y * 1j)  # the position is stored as a complex number

        self.neutrals.append(cable.neutral)
        self.neutrals_positions.append(x + y * 1j)


class Trench:
    """
    Trench that can contain many parallel circuits
    """

    def __init__(self, frequency, earth_resistivity):
        """
        Constructor
        @param frequency:
        @param earth_resistivity:
        """
        self.freq = frequency
        self.ro = earth_resistivity

        self.lines = list()

        # phases of the cables        
        self.phases = list()
        self.phases_pos = list()
        # neutrals of the cables
        self.neutrals = list()
        self.neutrals_pos = list()

        # single extra neutral
        self.neutral = None
        self.neutral_pos = None

        # all the conductors and their positions ordered
        self.conductors = list()
        self.positions = list()

    def add_line(self, cable: UndergroundLine):
        """
        Add an underground line to the trench (A line is supposed to be 3-phase)
        @param cable:
        @return:
        """
        self.lines.append(cable)

    def add_neutral(self, cond: Conductor, x, y):
        """
        The trench can host a single separated neutral
        @param cond:
        @param x:
        @param y:
        @return:
        """
        self.neutral = cond
        self.neutral_pos = x + y * 1j  # the position is stored as a complex number

    def compile(self):
        """
        compose the conductors in a structured manner;
        first the phase circuit conductors and at last the neutral
        """
        self.conductors = list()
        self.positions = list()

        if self.neutral is not None:
            self.neutrals.append(self.neutral)
            self.neutrals_pos.append(self.neutral_pos)

        for lne in self.lines:
            self.phases += lne.conductors
            self.phases_pos += lne.conductors_positions
            self.neutrals += lne.neutrals
            self.neutrals_pos += lne.neutrals_positions

        self.conductors += self.phases
        self.positions += self.phases_pos
        self.conductors += self.neutrals
        self.positions += self.neutrals_pos

    def draw(self):
        """

        @return:
        """
        self.compile()
        for p in self.positions:
            plt.plot(p.real, p.imag, 'o')
        plt.show()

    def kron(self, z):
        """
        The neutrals are grouped after the phases
        @param z:
        @return:
        """
        n = len(self.conductors)
        m = len(self.neutrals)

        zij = z[0:n - m, 0:n - m]
        zin = z[n - m:n, 0:n - m]
        znj = z[0:n - m, n - m:n]
        znn = np.matrix(z[n - m:n, n - m:n])
        return zij - zin * np.linalg.inv(znn) * znj

    def distance(self, i, j):
        """
        Distance between conductors
        @param i:
        @param j:
        @return:
        """
        d = abs(self.positions[i] - self.positions[j])
        if d == 0:  # evaluation of a tape-shield vs conductor in the same cable
            if self.conductors[i].Name == 'tape':
                d = self.conductors[i].GMR
            else:
                d = self.conductors[j].GMR
        return d

    def impedance_matrix(self):
        """
        Returns the ABC impedance matrix of the lines set up        
        """
        self.compile()

        eq = CarsonEquations(self.freq, self.ro)
        n = len(self.conductors)
        # m = len(self.neutrals)
        z = np.zeros((n, n), dtype=np.complex)
        for i in range(n):
            for j in range(n):
                if i == j:
                    z[i, j] = eq.zii(self.conductors[i].r, self.conductors[i].GMR)
                else:
                    z[i, j] = eq.zij(self.distance(i, j))

        return z

        # if m > 0:
        #     return self.kron(z)
        # else:
        #     return z


class OverheadLine(object):
    """
    line composed of 3 phases and one neutral    
    """

    def __init__(self):
        """
        Constructor
        """
        self.conductors = list()
        self.positions = list()

    def add_conductor(self, cond: Conductor, x, y):
        """
        Add a conductor to the line set up  (Overhead line)
        @param cond:
        @param x:
        @param y:
        @return:
        """
        self.conductors.append(cond)
        self.positions.append(x + y * 1j)  # the position is stored as a complex number


class Tower(object):
    """
    Tower that can contain many parallel circuits
    """

    def __init__(self, frequency, earth_resistivity):
        """
        Constructor
        @param frequency:
        @param earth_resistivity:
        """
        self.freq = frequency
        self.ro = earth_resistivity
        self.lines = list()
        self.conductors = list()
        self.positions = list()
        self.neutral = None
        self.neutral_pos = None

    def add_line(self, line_elm: OverheadLine):
        """
        Add a line to the tower (A line is supposed to be 3-phase)
        @param line_elm:
        @return:
        """
        self.lines.append(line_elm)

    def add_neutral(self, cond: Conductor, x, y):
        """
        The towers usually have a single neutral common to all the lines hosted
        hence, only one neutral is needed per tower
        @param cond:
        @param x:
        @param y:
        @return:
        """
        self.neutral = cond
        self.neutral_pos = x + y * 1j  # the position is stored as a complex number

    def draw(self):
        """

        @return:
        """
        self.compile()
        for p in self.positions:
            plt.plot(p.real, p.imag, 'o')
        plt.show()

    def kron(self, z):
        """
        The neutral is assumed to be the last one added
        @param z:
        @return:
        """
        n = len(self.conductors)
        zij = z[0:n - 1, 0:n - 1]
        zin = z[n - 1:n, 0:n - 1]
        znn = z[n - 1, n - 1]
        znj = z[0:n - 1, n - 1]
        return zij - zin * (1 / znn) * znj

    def distance(self, i, j):
        """
        Distance between conductors
        @param i:
        @param j:
        @return:
        """
        return abs(self.positions[i] - self.positions[j])

    def compile(self):
        """
        compose the conductors in a structured manner;
        first the phase circuit conductors and at last the neutral
        """
        self.conductors = list()
        self.positions = list()
        for lne in self.lines:
            self.conductors += lne.conductors
            self.positions += lne.positions

        if self.neutral is not None:
            self.conductors.append(self.neutral)
            self.positions.append(self.neutral_pos)

    def impedance_matrix(self):
        """
        Returns the ABC impedance matrix of the lines set up        
        """
        self.compile()

        eq = CarsonEquations(self.freq, self.ro)
        n = len(self.conductors)
        z = np.zeros((n, n), dtype=np.complex)
        for i in range(n):
            for j in range(n):
                if i == j:
                    z[i, j] = eq.zii(self.conductors[i].r, self.conductors[i].GMR)
                else:
                    z[i, j] = eq.zij(self.distance(i, j))

        if self.neutral is not None:
            return self.kron(z)
        else:
            return z


###############################################################################
# General values
###############################################################################
freq = 60  # Hz
earth_resistivity_ = 100  # ohm-m

###############################################################################
# Example 1, one line (3 phases + neutral)
###############################################################################
print("Example 1: 1 circuit in a tower")

conductor1 = Conductor('336,400 26/7 ACSR', 0.0244, 0.306, 0.721, 530)
neutral = Conductor('4/0 6/1 ACSR', 0.00814, 0.5920, 0.563, 340)

line = OverheadLine()
line.add_conductor(conductor1, 0.0, 29.0)
line.add_conductor(conductor1, 2.5, 29.)
line.add_conductor(conductor1, 7.0, 29.0)

tower1 = Tower(freq, earth_resistivity_)
tower1.add_line(line)
tower1.add_neutral(neutral, 4.0, 25.0)
Z1 = tower1.impedance_matrix()
print(Z1)
tower1.draw()

###############################################################################
# Example 2, one tower with two lines (3 + 3 phases + 1 neutral)
###############################################################################
print("Example 2: 2 circuits per tower with a common neutral")

conductor1 = Conductor('336,400 26/7 ACSR', 0.0244, 0.306, 0.721, 530)
conductor2 = Conductor('250,000 AA', 0.0171, 0.41, 0.567, 329)
neutral = Conductor('4/0 6/1 ACSR', 0.00814, 0.5920, 0.563, 340)

line1 = OverheadLine()
line1.add_conductor(conductor1, 0.0, 35.0)
line1.add_conductor(conductor1, 2.5, 35.)
line1.add_conductor(conductor1, 7.0, 35.0)

line2 = OverheadLine()
line2.add_conductor(conductor2, 2.5, 33.0)
line2.add_conductor(conductor2, 7.0, 33.)
line2.add_conductor(conductor2, 0.0, 33.0)

tower1 = Tower(freq, earth_resistivity_)
tower1.add_line(line1)
tower1.add_line(line2)
tower1.add_neutral(neutral, 4.0, 29.0)

Z2 = tower1.impedance_matrix()
print(Z2)


###############################################################################
# Example 3, three cables in a trench
###############################################################################

print("Example 3: three cables in a trench")

phase = Conductor('250,000 AA', 0.0171, 0.41, 0.567, 329)
neutral = Conductor('14 AWG SLD copper', 0.00208, 14.8722, 0.0641, 20)

cable1 = CableConcentricNeutral(phase, neutral, 13, 1.29)
cable2 = cable1
cable3 = cable1

trench_line = UndergroundLine()
trench_line.add_cable_concentric_neutral(cable1, 0, 0)
trench_line.add_cable_concentric_neutral(cable1, 0.5, 0)
trench_line.add_cable_concentric_neutral(cable1, 1, 0)

trench = Trench(freq, earth_resistivity_)
trench.add_line(trench_line)

Z3 = trench.impedance_matrix()
print(Z3)

###############################################################################
# Example 4, one cable in a trench with neutral
###############################################################################

print("Example 4: one cable in a trench with neutral")

phase = Conductor('1/0 AA', 0.0111, 0.97, 0.368, 202)
neutral = Conductor('1/0 copper 7 strand', 0.01113, 0.607, 0.368, 310)

# phase_conductor, tape_diameter, tape_thickness, earth_resistivity
cable1 = CableTapeShield(phase, 0.88, 5, earth_resistivity_)

trench_line = UndergroundLine()
trench_line.add_cable_tape_shield(cable1, 0, 0)

trench = Trench(freq, earth_resistivity_)
trench.add_line(trench_line)
trench.add_neutral(neutral, 0.25, 0)

Z4 = trench.impedance_matrix()
print(abc2seq(Z4))

