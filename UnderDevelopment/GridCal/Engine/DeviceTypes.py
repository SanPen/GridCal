# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import numpy as np
from numpy import pi, cos, sin, log, arccos, sqrt, exp
from matplotlib import pyplot as plt
from PyQt5 import QtCore
from enum import Enum

"""
Equations source:
a) ATP-EMTP theory book

Typical values of earth 
10 Ω/​m3 - Resistivity of swampy ground 
100 Ω/​m3 - Resistivity of average damp earth 
1000 Ω/​m3 - Resistivity of dry earth 
"""


class BranchType(Enum):
    Branch = 'branch',
    Line = 'line',
    Transformer = 'transformer',
    Reactance = 'reactance',
    Switch = 'switch'


class Wire:

    def __init__(self, name='', xpos=0, ypos=0, gmr=0.01, r=0.01, x=0.0, phase=0):
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
        self.wire_name = name
        self.xpos = xpos
        self.ypos = ypos
        self.r = r
        self.x = x
        self.gmr = gmr
        self.phase = phase

        self.edit_headers = ['wire_name', 'r', 'x', 'gmr']
        self.units = ['', 'Ohm/km', 'Ohm/km', 'm']
        self.non_editable_indices = list()
        self.edit_types = {'wire_name': str,
                           'r': float,
                           'x': float,
                           'gmr': float,
                           'xpos': float,
                           'ypos': float,
                           'phase': int}

    def copy(self):
        """
        Copy of the wire
        :return:
        """
        return Wire(self.wire_name, self.xpos, self.ypos, self.gmr, self.r, self.x, self.phase)

    def get_save_data(self):
        dta = list()
        for property in self.edit_headers:
            dta.append(getattr(self, property))
        return dta

    def __str__(self):
        return self.wire_name


class WiresCollection(QtCore.QAbstractTableModel):

    def __init__(self, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.header = ['Name', 'R (Ohm/km)', 'GMR (m)']

        self.index_prop = {0: 'wire_name', 1: 'r', 2: 'gmr'}

        self.converter = {0: str, 1: float, 2: float}

        self.editable = [True, True, True]

        self.wires = list()

    def add(self, wire: Wire):
        """
        Add wire
        :param wire:
        :return:
        """
        row = len(self.wires)
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.wires.append(wire)
        self.endInsertRows()

    def delete(self, index):
        """
        Delete wire
        :param index:
        :return:
        """
        row = len(self.wires)
        self.beginRemoveRows(QtCore.QModelIndex(), row - 1, row - 1)
        self.wires.pop(index)
        self.endRemoveRows()

    def is_used(self, name):
        """
        checks if the name is used
        """
        n = len(self.wires)
        for i in range(n-1, -1, -1):
            if self.wires[i].wire_name == name:
                return True
        return False

    def flags(self, index):
        if self.editable[index.column()]:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.wires)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.header)

    def parent(self, index=None):
        return QtCore.QModelIndex()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                val = getattr(self.wires[index.row()], self.index_prop[index.column()])
                return str(val)
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.header[p_int]

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        """
        if self.editable[index.column()]:
            wire = self.wires[index.row()]
            attr = self.index_prop[index.column()]

            if attr == 'tower_name':
                if self.is_used(value):
                    pass
                else:
                    setattr(wire, attr, self.converter[index.column()](value))
            else:
                setattr(wire, attr, self.converter[index.column()](value))

        return True


class BranchTemplate:

    def __init__(self, name='BranchTemplate', tpe=BranchType.Branch):

        self.name = name

        self.tpe = tpe

        self.edit_headers = []
        self.units = []
        self.non_editable_indices = []
        self.edit_types = {}

    def __str__(self):
        return self.name

    def get_save_data(self):

        dta = list()
        for property in self.edit_headers:
            dta.append(getattr(self, property))
        return dta


class SequenceLineType(QtCore.QAbstractTableModel):

    def __init__(self, parent=None, edit_callback=None, name='SequenceLine',
                 R=0, X=0, G=0, B=0, R0=0, X0=0, G0=0, B0=0, tpe=BranchType.Line):
        """

        :param parent:
        :param edit_callback:
        :param name: name of the model
        :param R: Resistance of positive sequence in Ohm/km
        :param X: Reactance of positive sequence in Ohm/km
        :param G: Conductance of positive sequence in Ohm/km
        :param B: Susceptance of positive sequence in Ohm/km
        :param R0: Resistance of zero sequence in Ohm/km
        :param X0: Reactance of zero sequence in Ohm/km
        :param G0: Conductance of zero sequence in Ohm/km
        :param B0: Susceptance of zero sequence in Ohm/km
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        # BranchTemplate.__init__(self, name=name, tpe=BranchType.Line)

        self.name = name

        self.tpe = tpe

        # impedances and admittances per unit of length
        self.R = R
        self.X = X
        self.G = G
        self.B = B

        self.R0 = R0
        self.X0 = X0
        self.G0 = G0
        self.B0 = B0

        self.edit_headers = ['name', 'R', 'X', 'G', 'B', 'R0', 'X0', 'G0', 'B0']
        self.units = ['', 'Ohm/km', 'Ohm/km', 'S/km', 'S/km', 'Ohm/km', 'Ohm/km', 'S/km', 'S/km']
        self.non_editable_indices = []
        self.edit_types = {'name': str,
                           'R': float,
                           'X': float,
                           'G': float,
                           'B': float,
                           'R0': float,
                           'X0': float,
                           'G0': float,
                           'B0': float}

    def __str__(self):
        return self.name

    def get_save_data(self):

        dta = list()
        for property in self.edit_headers:
            dta.append(getattr(self, property))
        return dta


class UndergroundLineType(QtCore.QAbstractTableModel):

    def __init__(self, parent=None, edit_callback=None, name='UndergroundLine', tpe=BranchType.Line):
        QtCore.QAbstractTableModel.__init__(self, parent)
        # BranchTemplate.__init__(self, name=name, tpe=BranchType.Line)

        self.name = name

        self.tpe = tpe

        self.seq_resistance = complex(0, 0)
        self.seq_admittance = complex(0, 0)

        self.edit_headers = ['name', ]
        self.units = ['', ]
        self.non_editable_indices = []
        self.edit_types = {'name': str}

    def __str__(self):
        return self.name

    def get_save_data(self):

        dta = list()
        for property in self.edit_headers:
            dta.append(getattr(self, property))
        return dta


class Tower(QtCore.QAbstractTableModel):

    def __init__(self, parent=None, edit_callback=None, name='Tower', tpe=BranchType.Branch):
        QtCore.QAbstractTableModel.__init__(self, parent)
        # BranchTemplate.__init__(self, name=name, tpe=BranchType.Line)

        self.tpe = tpe

        # properties
        self.tower_name = name
        self.earth_resistivity = 100
        self.frequency = 50
        self.seq_resistance = complex(0, 0)
        self.seq_admittance = complex(0, 0)

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

        # other properties
        self.wires = list()
        self.edit_callback = edit_callback

        # wire properties for edition
        self.header = ['Wire', 'X (m)', 'Y (m)', 'Phase', 'Ri (Ohm/km)', 'Xi (Ohm/km)', 'GMR (m)']

        self.index_prop = {0: 'wire_name', 1: 'xpos', 2: 'ypos', 3: 'phase', 4: 'r', 5: 'x', 6: 'gmr'}

        self.converter = {0: str, 1: float, 2: float, 3: int, 4: float, 5: float, 6: float}

        self.editable_wire = [False, True, True, True, True, True, True]

        # properties for the object model
        self.edit_headers = ['tower_name', 'earth_resistivity', 'frequency', 'seq_resistance', 'seq_admittance']
        self.units = ['', 'Ohm/m3', 'Hz', 'Ohm/km', 'S/km']
        self.non_editable_indices = [3, 4]
        self.edit_types = {'tower_name': str,
                           'earth_resistivity': float,
                           'frequency': float,
                           'seq_resistance': complex,
                           'seq_admittance': complex}

    def __str__(self):
        return self.tower_name

    def get_save_data(self, dta_list=list()):
        """
        store the tower data into dta_list in a SQL-like fashion to avoid 3D like structures
        :param dta_list: list to append the data to
        :return: nothing
        """
        # generate the tower data
        tower_dta = list()
        for property in self.edit_headers:
            tower_dta.append(getattr(self, property))

        # add the wire data
        wire_prop = [p for p in self.index_prop.values()]
        for wire in self.wires:
            wire_dta = list(tower_dta)
            for property in wire_prop:
                wire_dta.append(getattr(wire, property))
            dta_list.append(wire_dta)

    def get_wire_properties(self):
        return [self.index_prop[i] for i in range(len(self.index_prop))]

    def get_save_headers(self):
        """
        Return the tower header + wire header
        :return:
        """
        wire_hdr = self.get_wire_properties()
        hdr = self.edit_headers + wire_hdr
        return hdr

    def add(self, wire: Wire):
        """
        Add wire
        :param wire:
        :return:
        """
        row = self.rowCount()
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.wires.append(wire)
        self.endInsertRows()

    def delete(self, index):
        """
        Delete wire
        :param index:
        :return:
        """
        row = self.rowCount()
        self.beginRemoveRows(QtCore.QModelIndex(), row - 1, row - 1)
        self.wires.pop(index)
        self.endRemoveRows()

    def plot(self, ax=None):
        """
        Plot wires position
        :param ax: Axis object
        """
        if ax is None:
            fig = plt.Figure(figsize=(12, 6))
            ax = fig.add_subplot(1, 1, 1)

        n = len(self.wires)
        x = np.zeros(n)
        y = np.zeros(n)
        for i, wire in enumerate(self.wires):
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

    def check(self, logger=list()):
        """
        Check that the wires configuration make sense
        :return:
        """

        for i, wire_i in enumerate(self.wires):

            if wire_i.gmr < 0:
                logger.append('The wires' + wire_i.wire_name + '(' + str(i) + ') has GRM=0 which is impossible.')
                return False

            for j, wire_j in enumerate(self.wires):

                if i != j:
                    if wire_i.xpos == wire_j.xpos and wire_i.ypos == wire_j.ypos:
                        logger.append('The wires' + wire_i.wire_name + '(' + str(i) + ') and ' +
                                      wire_j.wire_name + '(' + str(j) + ') have the same position which is impossible.')
                        return False
                else:
                    pass

        return True

    def compute(self):
        """
        Compute the tower matrices
        :return:
        """
        # heck the wires configuration
        all_ok = self.check()

        if all_ok:
            # Impedances
            self.z_abcn, self.z_phases_abcn, self.z_abc, \
            self.z_phases_abc, self.z_seq = calc_z_matrix(self.wires, f=self.frequency, rho=self.earth_resistivity)

            # Admittances
            self.y_abcn, self.y_phases_abcn, self.y_abc, \
            self.y_phases_abc, self.y_seq = calc_y_matrix(self.wires, f=self.frequency, rho=self.earth_resistivity)

            self.seq_resistance = self.z_seq[1, 1]
            self.seq_admittance = self.y_seq[1, 1]
        else:
            pass

    def delete_by_name(self, wire: Wire):
        n = len(self.wires)
        for i in range(n-1, -1, -1):
            if self.wires[i].wire_name == wire.wire_name:
                self.delete(i)

    def is_used(self, wire: Wire):
        n = len(self.wires)
        for i in range(n-1, -1, -1):
            if self.wires[i].wire_name == wire.wire_name:
                return True

    def flags(self, index):
        if self.editable_wire[index.column()]:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

    def rowCount(self, parent=None):
        return len(self.wires)

    def columnCount(self, parent=None):
        return len(self.header)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                val = getattr(self.wires[index.row()], self.index_prop[index.column()])
                return str(val)
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.header[p_int]

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        """
        if self.editable_wire[index.column()]:
            wire = self.wires[index.row()]
            attr = self.index_prop[index.column()]

            try:
                val = self.converter[index.column()](value)
            except:
                val = 0

            # correct the phase to the correct range
            if attr == 'phase':
                if val < 0 or val > 3:
                    val = 0

            setattr(wire, attr, val)

            if self.edit_callback is not None:
                self.edit_callback()

        return True


class TransformerType:

    def __init__(self, hv_nominal_voltage=0, lv_nominal_voltage=0, nominal_power=0, copper_losses=0, iron_losses=0,
                 no_load_current=0, short_circuit_voltage=0, gr_hv1=0.5, gx_hv1=0.5,
                 name='TransformerType', tpe=BranchType.Transformer):
        """
        Constructor
        @param hv_nominal_voltage: High voltage side nominal voltage (kV)
        @param lv_nominal_voltage: Low voltage side nominal voltage (kV)
        @param nominal_power: Transformer nominal power (MVA)
        @param copper_losses: Copper losses (kW)  [also known as short circuit power]
        @param iron_losses: Iron Losses (kW) [also known as no load power]
        @param no_load_current: No load current (%)
        @param short_circuit_voltage: Short circuit voltage (%)
        @param gr_hv1: Resistive contribution to the HV side (default is 50%)
        @param gx_hv1: Reactive contribution to the HV side (default is 50%)
        """

        self.name = name

        self.tpe = tpe

        self.type_name = 'TransformerType'

        self.properties_with_profile = None

        self.HV_nominal_voltage = hv_nominal_voltage

        self.LV_nominal_voltage = lv_nominal_voltage

        self.Nominal_power = nominal_power

        self.Copper_losses = copper_losses

        self.Iron_losses = iron_losses

        self.No_load_current = no_load_current

        self.Short_circuit_voltage = short_circuit_voltage

        self.GR_hv1 = gr_hv1

        self.GX_hv1 = gx_hv1

        self.edit_headers = ['name',
                             'HV_nominal_voltage',
                             'LV_nominal_voltage',
                             'Nominal_power',
                             'Copper_losses',
                             'Iron_losses',
                             'No_load_current',
                             'Short_circuit_voltage']

        self.units = ['',
                      'kV',
                      'kV',
                      'MVA',
                      'kW',
                      'kW',
                      '%',
                      '%']

        self.non_editable_indices = list()

        self.edit_types = {'name': str,
                           'HV_nominal_voltage': float,
                           'LV_nominal_voltage': float,
                           'Nominal_power': float,
                           'Copper_losses': float,
                           'Iron_losses': float,
                           'No_load_current': float,
                           'Short_circuit_voltage': float}

    def __str__(self):
        return self.name

    def get_save_data(self):

        dta = list()
        for property in self.edit_headers:
            dta.append(getattr(self, property))
        return dta

    def get_impedances(self):
        """
        Compute the branch parameters of a transformer from the short circuit
        test values
        @return:
            leakage_impedance: Series impedance
            magnetizing_impedance: Shunt impedance
        """
        Vhv = self.HV_nominal_voltage

        Vlv = self.LV_nominal_voltage

        Sn = self.Nominal_power

        Pcu = self.Copper_losses

        Pfe = self.Iron_losses

        I0 = self.No_load_current

        Vsc = self.Short_circuit_voltage

        GRhv = self.GR_hv1

        GXhv = self.GX_hv1

        # Zn_hv = (Vhv ** 2) / Sn
        # Zn_lv = (Vlv ** 2) / Sn

        # Series impedance
        zsc = Vsc / 100.0
        rsc = (Pcu / 1000.0) / Sn
        xsc = sqrt(zsc ** 2 - rsc ** 2)

        # rcu_hv = rsc * self.GR_hv1
        # rcu_lv = rsc * (1 - self.GR_hv1)
        # xs_hv = xsc * self.GX_hv1
        # xs_lv = xsc * (1 - self.GX_hv1)

        zs = rsc + 1j * xsc

        # Shunt impedance (leakage)
        if Pfe > 0.0 and I0 > 0.0:
            rfe = Sn / (Pfe / 1000.0)
            zm = 1.0 / (I0 / 100.0)
            xm = 1.0 / sqrt((1.0 / (zm ** 2)) - (1.0 / (rfe ** 2)))
            rm = sqrt(xm * xm - zm * zm)
        else:
            rm = 0.0
            xm = 0.0

        zsh = rm + 1j * xm

        return zs, zsh

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
    Zaa = mat[keep, :][:, keep]
    Zag = mat[keep, :][:, embed]
    Zga = mat[embed, :][:, keep]
    Zgg = mat[embed, :][:, embed]

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
        z_prim[i, i] = z_ii(r_i=wire_i.r, x_i=wire_i.x, h_i=wire_i.ypos, gmr_i=wire_i.gmr, f=f, rho=rho)

        # mutual impedances
        for j, wire_j in enumerate(wires):

            if i != j:
                #  mutual impedance
                d_ij = get_d_ij(wire_i.xpos, wire_i.ypos, wire_j.xpos, wire_j.ypos)

                # D_ij = get_D_ij(wire_i.xpos, wire_i.ypos, wire_j.xpos, wire_j.ypos)

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
        p_prim[i, i] = one_two_pi_e0 * log(2 * wire_i.ypos / wire_i.gmr)

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