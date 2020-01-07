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


from PySide2 import QtCore
from GridCal.Engine.Devices.wire import Wire
from GridCal.Engine.Devices.tower import Tower, WireInTower

"""
Equations source:
a) ATP-EMTP theory book

Typical values of earth 
10 Ω/​m3 - Resistivity of swampy ground 
100 Ω/​m3 - Resistivity of average damp earth 
1000 Ω/​m3 - Resistivity of dry earth 
"""


class TowerModel(QtCore.QAbstractTableModel):

    def __init__(self, parent=None, edit_callback=None, tower: Tower=None):
        """

        :param parent:
        :param edit_callback:
        :param tower:
        """

        QtCore.QAbstractTableModel.__init__(self)

        if tower is None:
            self.tower = Tower()
        else:
            self.tower = tower

        # other properties
        self.edit_callback = edit_callback

    def __str__(self):
        return self.tower.name

    def add(self, wire: WireInTower):
        """
        Add wire
        :param wire:
        :return:
        """
        row = self.rowCount()
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.tower.wires_in_tower.append(wire)
        self.endInsertRows()

    def delete(self, index):
        """
        Delete wire
        :param index:
        :return:
        """
        row = self.rowCount()
        self.beginRemoveRows(QtCore.QModelIndex(), row - 1, row - 1)
        self.tower.wires_in_tower.pop(index)
        self.endRemoveRows()

    def delete_by_name(self, wire: Wire):
        """
        Delete wire by name
        :param wire: Wire object
        """
        n = len(self.tower.wires_in_tower)
        for i in range(n-1, -1, -1):
            if self.tower.wires_in_tower[i].name == wire.name:
                self.delete(i)

    def is_used(self, wire: Wire):
        """

        :param wire:
        :return:
        """
        n = len(self.tower.wires_in_tower)
        for i in range(n-1, -1, -1):
            if self.tower.wires_in_tower[i].name == wire.name:
                return True

    def flags(self, index):
        """

        :param index:
        :return:
        """
        if self.tower.editable_wire[index.column()]:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

    def rowCount(self, parent=None):
        """

        :param parent:
        :return:
        """
        return len(self.tower.wires_in_tower)

    def columnCount(self, parent=None):
        """

        :param parent:
        :return:
        """
        return len(self.tower.header)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                val = getattr(self.tower.wires_in_tower[index.row()], self.tower.index_prop[index.column()])
                return str(val)
        return None

    def headerData(self, p_int, orientation, role):
        """

        :param p_int:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.tower.header[p_int]

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        """
        if self.tower.editable_wire[index.column()]:
            wire = self.tower.wires_in_tower[index.row()]
            attr = self.tower.index_prop[index.column()]

            try:
                val = self.tower.converter[index.column()](value)
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

