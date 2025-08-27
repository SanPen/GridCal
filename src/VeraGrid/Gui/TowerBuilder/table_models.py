# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from typing import Union, List
from PySide6 import QtCore
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType, WireInTower

"""
Equations source:
a) ATP-EMTP theory book

Typical values of earth 
10 Ω/m3 - Resistivity of swampy ground 
100 Ω/m3 - Resistivity of average damp earth 
1000 Ω/m3 - Resistivity of dry earth 
"""




class WiresTable(QtCore.QAbstractTableModel):
    """
    Wires table for the tower
    """

    def __init__(self, parent=None):

        QtCore.QAbstractTableModel.__init__(self, parent)

        self.header = ['Name', 'R (Ohm/km)', 'Diameter (mm)', 'max current (kA)']

        self.converter = {0: str, 1: float, 2: float, 3: float}

        self.editable = [False, False, False, False]

        self.wires: List[Wire] = list()

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
        for i in range(n - 1, -1, -1):
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
                wire = self.wires[index.row()]
                if index.column() == 0:
                    return wire.name
                elif index.column() == 1:
                    return str(wire.R)
                elif index.column() == 2:
                    return str(wire.diameter)
                elif index.column() == 3:
                    return str(wire.max_current)

                return ""
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
        # if self.editable[index.column()]:
        #     wire = self.wires[index.row()]
        #     # attr = self.index_prop[index.column()]
        #
        #     if attr == 'tower_name':
        #         if self.is_used(value):
        #             pass
        #         else:
        #             wire.
        #             setattr(wire, attr, self.converter[index.column()](value))
        #     else:
        #         setattr(wire, attr, self.converter[index.column()](value))
        #
        #     wire = self.wires[index.row()]
        #     if index.column() == 0:
        #         return wire.name
        #     elif index.column() == 1:
        #         return str(wire.R)
        #     elif index.column() == 2:
        #         return str(wire.GMR)
        #     elif index.column() == 3:
        #         return str(wire.max_current)

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
        for i in range(n - 1, -1, -1):
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

    def __init__(self, edit_callback=None, tower: Union[OverheadLineType, None] = None):
        """

        :param edit_callback: compute function from the TowerBuilderGUI
        :param tower:
        """

        QtCore.QAbstractTableModel.__init__(self)

        if tower is None:
            self._tower = OverheadLineType()
        else:
            self._tower = tower

        # other properties
        self.edit_callback = edit_callback

        # wire properties for edition (do not confuse with the properties of this very object...)
        self.header = ['Wire', 'X (m)', 'Y (m)', 'Phase', "Circuit Index", "Phase name"]
        self.index_prop = {0: 'name', 1: 'xpos', 2: 'ypos', 3: 'phase', 4: 'circuit_index', 5: 'phase_type'}
        self.converter = {0: str, 1: float, 2: float, 3: int, 4: int, 5: str}
        self.editable_wire = [False, True, True, True, False, False]

    @property
    def tower(self) -> OverheadLineType:
        return self._tower

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
        self.tower.wires_in_tower.data.pop(index)
        self.endRemoveRows()

    def delete_by_name(self, wire: Wire):
        """
        Delete wire by name
        :param wire: Wire object
        """
        n = len(self.tower.wires_in_tower.data)
        for i in range(n - 1, -1, -1):
            if self.tower.wires_in_tower.data[i].name == wire.name:
                self.delete(i)

    def is_used(self, wire: Wire):
        """

        :param wire:
        :return:
        """
        n = len(self.tower.wires_in_tower.data)
        for i in range(n - 1, -1, -1):
            if self.tower.wires_in_tower.data[i].name == wire.name:
                return True

    def flags(self, index):
        """

        :param index:
        :return:
        """
        if self.editable_wire[index.column()]:
            return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def rowCount(self, parent=None):
        """

        :param parent:
        :return:
        """
        return len(self.tower.wires_in_tower.data)

    def columnCount(self, parent=None):
        """

        :param parent:
        :return:
        """
        return len(self.header)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                val = getattr(self.tower.wires_in_tower.data[index.row()], self.index_prop[index.column()])
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
                return self.header[section]

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        """
        if self.editable_wire[index.column()]:
            wire = self.tower.wires_in_tower.data[index.row()]
            attr = self.index_prop[index.column()]

            try:
                val = self.converter[index.column()](value)
            except ValueError:
                val = 0
            except TypeError:
                val = 0

            setattr(wire, attr, val)

            if self.edit_callback is not None:
                self.edit_callback()

        return True
