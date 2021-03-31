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
import PySide2

from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp
from PySide2 import QtCore


class Wire(EditableDevice):

    def __init__(self, name='', idtag=None, gmr=0.01, r=0.01, x=0.0, max_current=1):
        """
        Wire definition
        :param name: Name of the wire type
        :param gmr: Geometric Mean Radius (m)
        :param r: Resistance per unit length (Ohm / km)
        :param x: Reactance per unit length (Ohm / km)
        :param max_current: Maximum current of the conductor in (kA)

        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=True,
                                device_type=DeviceType.WireDevice,
                                editable_headers={'name': GCProp('', str, "Name of the conductor"),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'r': GCProp('Ohm/km', float, "resistance of the conductor"),
                                                  'x': GCProp('Ohm/km', float, "reactance of the conductor"),
                                                  'gmr': GCProp('m', float, "Geometric Mean Radius of the conductor"),
                                                  'max_current': GCProp('kA', float, "Maximum current of the conductor")
                                                  },
                                non_editable_attributes=list(),
                                properties_with_profile={})

        # self.wire_name = name
        self.r = r
        self.x = x
        self.gmr = gmr
        self.max_current = max_current

    def copy(self):
        """
        Copy of the wire
        :return:
        """
        # name='', idtag=None, gmr=0.01, r=0.01, x=0.0, max_current=1
        return Wire(name=self.name, gmr=self.gmr, r=self.r, x=self.x, max_current=self.max_current)


class WiresTable(QtCore.QAbstractTableModel):

    def __init__(self, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.header = ['Name', 'R (Ohm/km)', 'GMR (m)']

        self.index_prop = {0: 'name', 1: 'r', 2: 'gmr'}

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
            if self.wires[i].name == name:
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




