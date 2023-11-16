# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

from typing import Union
from PySide6 import QtCore
from GridCalEngine.Core.Devices.Branches.wire import Wire
from GridCalEngine.Core.Devices.Branches.templates.overhead_line_type import OverheadLineType, WireInTower

"""
Equations source:
a) ATP-EMTP theory book

Typical values of earth 
10 Ω/m3 - Resistivity of swampy ground 
100 Ω/m3 - Resistivity of average damp earth 
1000 Ω/m3 - Resistivity of dry earth 
"""


class WiresTable(QtCore.QAbstractTableModel):

    def __init__(self, parent=None):

        QtCore.QAbstractTableModel.__init__(self, parent)

        self.header = ['Name', 'R (Ohm/km)', 'GMR (m)', 'max current (kA)']

        self.index_prop = {0: 'name', 1: 'r', 2: 'gmr', 3: 'max_current'}

        self.converter = {0: str, 1: float, 2: float, 3: float}

        self.editable = [True, True, True, True]

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
            return (QtCore.Qt.ItemFlag.ItemIsEditable |
                    QtCore.Qt.ItemFlag.ItemIsEnabled |
                    QtCore.Qt.ItemFlag.ItemIsSelectable)
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.wires)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.header)

    def parent(self, index=None):
        return QtCore.QModelIndex()

    def data(self,
             index: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex],
             role=QtCore.Qt.ItemDataRole.DisplayRole):

        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                val = getattr(self.wires[index.row()], self.index_prop[index.column()])
                return str(val)
        return None

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role=QtCore.Qt.ItemDataRole.DisplayRole):

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self.header[section]

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.DisplayRole):
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


class WiresCollection(QtCore.QAbstractTableModel):

    def __init__(self, parent=None, wires_in_tower=()):
        """

        :param parent:
        :param wires_in_tower:
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.header = ['name', 'X (m)', 'Y (m)', 'phase']

        self.index_prop = {0: 'name', 1: 'xpos', 2: 'ypos', 3: 'phase'}

        self.converter = {0: str, 1: float, 2: float, 3: float}

        self.editable = [False, True, True, True]

        self.wires_in_tower = list(wires_in_tower)

    def add(self, wire: WireInTower):
        """
        Add wire
        :param wire:
        :return:
        """
        row = len(self.wires_in_tower)
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.wires_in_tower.append(wire)
        self.endInsertRows()

    def delete(self, index):
        """
        Delete wire
        :param index: index of the wire
        :return:
        """
        row = len(self.wires_in_tower)
        self.beginRemoveRows(QtCore.QModelIndex(), row - 1, row - 1)
        self.wires_in_tower.pop(index)
        self.endRemoveRows()

    def is_used(self, name):
        """
        checks if the name is used
        """
        n = len(self.wires_in_tower)
        for i in range(n-1, -1, -1):
            if self.wires_in_tower[i].name == name:
                return True
        return False

    def flags(self, index):
        if self.editable[index.column()]:
            return (QtCore.Qt.ItemFlag.ItemIsEditable |
                    QtCore.Qt.ItemFlag.ItemIsEnabled |
                    QtCore.Qt.ItemFlag.ItemIsSelectable)
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.wires_in_tower)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.header)

    def parent(self, index=None):
        return QtCore.QModelIndex()

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                val = getattr(self.wires_in_tower[index.row()], self.index_prop[index.column()])
                return str(val)
        return None

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self.header[section]

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        """
        if self.editable[index.column()]:
            wire = self.wires_in_tower[index.row()]
            attr = self.index_prop[index.column()]

            if attr == 'tower_name':
                if self.is_used(value):
                    pass
                else:
                    setattr(wire, attr, self.converter[index.column()](value))
            else:
                setattr(wire, attr, self.converter[index.column()](value))

        return True


class TowerModel(QtCore.QAbstractTableModel):

    def __init__(self, parent=None, edit_callback=None, tower: Union[OverheadLineType, None] = None):
        """

        :param parent:
        :param edit_callback:
        :param tower:
        """

        QtCore.QAbstractTableModel.__init__(self)

        if tower is None:
            self.tower = OverheadLineType()
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
            return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

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

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                val = getattr(self.tower.wires_in_tower[index.row()], self.tower.index_prop[index.column()])
                return str(val)
        return None

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self.tower.header[section]

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.DisplayRole):
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
            except ValueError:
                val = 0
            except TypeError:
                val = 0

            # correct the phase to the correct range
            if attr == 'phase':
                if val < 0 or val > 3:
                    val = 0

            setattr(wire, attr, val)

            if self.edit_callback is not None:
                self.edit_callback()

        return True

