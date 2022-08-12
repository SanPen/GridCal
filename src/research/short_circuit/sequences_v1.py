# Unbalanced short circuit using sequences
# Josep Fanals
# adapted from https://gist.github.com/poypoyan/1d68424596cbe9fae01b644840b27c96#file-3pzbus-py
# followed the same structure, but no abc
# main reference: (abdel-akher, 2005): https://ieeexplore.ieee.org/document/1490591?arnumber=1490591
# another reference: (barrero, 2004): Sistemas de energía eléctrica

import numpy as np


class Adm:

    """
    Ybus = [[Y0, 0, 0], [0, Y1, 0], [0, 0, Y2]]
    where Y0, Y1 and Y2 have all sizes n_bus * n_bus
    """

    def __init__(self, n_bus):
        self.Ybus = np.zeros((3 * n_bus, 3 * n_bus), dtype=complex)
        self.n_bus = n_bus

    def add_genload(self, bus_idx, Z0, Z1, Z2):
        """Add the impedances of a generator/load in the admittance matrix

        :param bus_idx: index of the bus where the gen/load is placed
        :param Z0: zero seq. impedance of the element
        :param Z1: positive seq. impedance of the element
        :param Z2: negative seq. impedance of the element (usually Z1 = Z2 for a gen)
        """

        self.Ybus[bus_idx, bus_idx] += 1 / Z0
        self.Ybus[self.n_bus + bus_idx, self.n_bus + bus_idx] += 1 / Z1
        self.Ybus[2 * self.n_bus + bus_idx, 2 * self.n_bus + bus_idx] += 1 / Z2

    def add_line(self, bus_f, bus_t, Z0, Z1):
        """Add the impedances of a transmission line,
        considering it is balanced and perfectly transposed (realistic consideration).
        We also assume no shunt impedances for now (not hard to add)

        :param bus_f: from bus index
        :param bus_t: to bus index
        :param Z0: zero seq. impedance of the line (about 2.5 Z1)
        :param Z1: positive and negative seq. impedance of the line
        """

        # can write it more compact?
        # zero seq.
        self.Ybus[bus_f, bus_f] += 1 / Z0
        self.Ybus[bus_t, bus_t] += 1 / Z0
        self.Ybus[bus_f, bus_t] -= 1 / Z0
        self.Ybus[bus_t, bus_f] -= 1 / Z0

        # positive seq.
        self.Ybus[self.n_bus + bus_f, self.n_bus + bus_f] += 1 / Z1
        self.Ybus[self.n_bus + bus_t, self.n_bus + bus_t] += 1 / Z1
        self.Ybus[self.n_bus + bus_f, self.n_bus + bus_t] -= 1 / Z1
        self.Ybus[self.n_bus + bus_t, self.n_bus + bus_f] -= 1 / Z1

        # negative seq.
        self.Ybus[2 * self.n_bus + bus_f, 2 * self.n_bus + bus_f] += 1 / Z1
        self.Ybus[2 * self.n_bus + bus_t, 2 * self.n_bus + bus_t] += 1 / Z1
        self.Ybus[2 * self.n_bus + bus_f, 2 * self.n_bus + bus_t] -= 1 / Z1
        self.Ybus[2 * self.n_bus + bus_t, 2 * self.n_bus + bus_f] -= 1 / Z1

    def add_trafo(self, bus_f, bus_t, con_f, con_t, Zs):
        """Add a transformer to the admittance matrix,
        considering the 6 different possible connections, which we call them:
        - S: star
        - G: grounded star
        - D: delta

        :param bus_f: from bus index
        :param bus_t: to bus index
        :param con_f: connection on the from bus (S, GS or D)
        :param con_t: connection on the to bus (S, GS or D)
        :param Zs: leakage impedance, we assume yp = ym = ys (check abdel-akher, 2005)
        """

        # positive and negative seq.
        if (con_f == 'G' and con_t == 'D') or (con_f == 'S' and con_t == 'D'):
            self.Ybus[self.n_bus + bus_f, self.n_bus + bus_f] += 1 / Zs
            self.Ybus[self.n_bus + bus_t, self.n_bus + bus_t] += 1 / Zs
            self.Ybus[self.n_bus + bus_f, self.n_bus + bus_t] -= 1 / Zs * np.exp(1j * np.pi / 6)
            self.Ybus[self.n_bus + bus_t, self.n_bus + bus_f] -= 1 / Zs * np.exp(-1j * np.pi / 6)

            self.Ybus[2 * self.n_bus + bus_f, 2 * self.n_bus + bus_f] += 1 / Zs
            self.Ybus[2 * self.n_bus + bus_t, 2 * self.n_bus + bus_t] += 1 / Zs
            self.Ybus[2 * self.n_bus + bus_f, 2 * self.n_bus + bus_t] -= 1 / Zs * np.exp(-1j * np.pi / 6)
            self.Ybus[2 * self.n_bus + bus_t, 2 * self.n_bus + bus_f] -= 1 / Zs * np.exp(1j * np.pi / 6)

        else:
            self.Ybus[self.n_bus + bus_f, self.n_bus + bus_f] += 1 / Zs
            self.Ybus[self.n_bus + bus_t, self.n_bus + bus_t] += 1 / Zs
            self.Ybus[self.n_bus + bus_f, self.n_bus + bus_t] -= 1 / Zs
            self.Ybus[self.n_bus + bus_t, self.n_bus + bus_f] -= 1 / Zs

            self.Ybus[2 * self.n_bus + bus_f, 2 * self.n_bus + bus_f] += 1 / Zs
            self.Ybus[2 * self.n_bus + bus_t, 2 * self.n_bus + bus_t] += 1 / Zs
            self.Ybus[2 * self.n_bus + bus_f, 2 * self.n_bus + bus_t] -= 1 / Zs
            self.Ybus[2 * self.n_bus + bus_t, 2 * self.n_bus + bus_f] -= 1 / Zs

        # zero seq.
        if con_f == 'G' and con_t == 'G':
            self.Ybus[bus_f, bus_f] += 1 / Zs
            self.Ybus[bus_t, bus_t] += 1 / Zs
            self.Ybus[bus_f, bus_t] -= 1 / Zs
            self.Ybus[bus_t, bus_f] -= 1 / Zs
        elif con_f == 'G' and con_t == 'D':
            self.Ybus[bus_f, bus_f] += 1 / Zs
        else:
            pass  # no admittance connected to no bus

    def get_decoupled_Y012(self):
        """Obtain the Y0, Y1, Y2 decoupled (in principle) submatrices,
        and also compute the Z0, Z1 and Z2 matrices
        """
        self.Y0 = self.Ybus[0:self.n_bus, 0:self.n_bus]
        self.Y1 = self.Ybus[self.n_bus:2*self.n_bus, self.n_bus:2*self.n_bus]
        self.Y2 = self.Ybus[2*self.n_bus:, 2*self.n_bus:]

        # function to check if there are non-zero terms outside the diag?

        self.Z0 = np.linalg.inv(self.Y0)
        self.Z1 = np.linalg.inv(self.Y1)
        self.Z2 = np.linalg.inv(self.Y2)


def solve_faults(Y, n_bus, Vpre, bus_f, type_f, Zf):
    """Solve for all faults, equations from (barrero, 2004)

    :param Y: class with all admittances' info
    :param Vpre: prefault voltages (balanced, only positive seq.)
    :param bus_f: bus index where the fault appears
    :param type_f: type of fault (3x, LG, LL, LLG)
    :param Zf: fault impedance
    :return: voltages after the fault and fault currents in 012
    """

    # solve the fault
    Vpr = Vpre[bus_f]
    Zth0 = Y.Z0[bus_f, bus_f]
    Zth1 = Y.Z1[bus_f, bus_f]
    Zth2 = Y.Z2[bus_f, bus_f]

    if type_f == '3x':
        I0 = 0
        I1 = Vpr / (Zth1 + Zf)
        I2 = 0
    elif type_f == 'LG':
        I0 = Vpr / (Zth0 + Zth1 + Zth2 + 3 * Zf)
        I1 = I0
        I2 = I0
    elif type_f == 'LL':  # between phases b and c
        I0 = 0
        I1 = Vpr / (Zth1 + Zth2 + Zf)
        I2 = - I1
    elif type == 'LLG':  # between phases b and c
        I1 = Vpr / (Zth1 + Zth2 * (Zth0 + 3 * Zf) / (Zth2 + Zth0 + 3 * Zf))
        I0 = -I1 * Zth2 / (Zth2 + Zth0 + 3 * Zf)
        I2 = -I1 * (Zth0 + 3 * Zf) / (Zth2 + Zth0 + 3 * Zf)
    else:
        I0 = 0
        I1 = Vpr / (Zth1 + Zf)
        I2 = 0

    # obtain the post fault voltages
    Vpre_ok = np.zeros((n_bus, 1), dtype=complex)
    I0_vec = np.zeros((n_bus, 1), dtype=complex)
    I1_vec = np.zeros((n_bus, 1), dtype=complex)
    I2_vec = np.zeros((n_bus, 1), dtype=complex)

    Vpre_ok[:, 0] = Vpre
    I0_vec[bus_f, 0] = I0
    I1_vec[bus_f, 0] = I1
    I2_vec[bus_f, 0] = I2

    V0_fin = - np.matmul(Y.Z0, I0_vec)
    V1_fin = Vpre_ok - np.matmul(Y.Z1, I1_vec)
    V2_fin = - np.matmul(Y.Z2, I2_vec)

    return [V0_fin, V1_fin, V2_fin], [I0, I1, I2]


# example 10.6b from Hadi Saadat - Power System Analysis
Vpre = np.array([1., 1., 1., 1., 1 * np.exp(-1j * np.pi / 6)])
n_bus = len(Vpre)

Y = Adm(n_bus)
Y.add_genload(3, 0.05j + 0.25j, 0.15j, 0.15j)
Y.add_genload(4, 0.05j + 0.25j, 0.15j, 0.15j)
Y.add_line(0, 1, 0.30j, 0.125j)
Y.add_line(0, 2, 0.35j, 0.15j)
Y.add_line(1, 2, 0.7125j, 0.25j)
Y.add_trafo(3, 0, 'G', 'G', 0.1j)  # grounded - grounded
Y.add_trafo(1, 4, 'G', 'D', 0.1j)  # grounded - delta
Y.get_decoupled_Y012()

bus_f = 2
type_f = 'LG'
Zf = 0.1j

[V0, V1, V2], [I0, I1, I2] = solve_faults(Y, n_bus, Vpre, bus_f, type_f, Zf)

print('V0: ')
print(abs(V0))
print('V1: ')
print(abs(V1))
print('V2: ')
print(abs(V2))

print('\n Fault currents')
print(I0, I1, I2)

print('\n Finished!')