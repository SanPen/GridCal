# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Callable, List

from PySide6 import QtCore, QtGui

from VeraGridEngine.Devices.Branches.underground_cable_type import UndergroundCableType
from VeraGridEngine.Devices.Branches.underground_line_type import CableInSystem, UndergroundLineType
from VeraGridEngine.Devices.Parents.editable_device import GCProp


class UndergroundCableCatalogueModel(QtCore.QAbstractTableModel):
    """Editable view of the supported cable-construction properties."""

    __slots__ = ('cables', 'properties', 'edit_callback')

    def __init__(self,
                 cables: List[UndergroundCableType],
                 edit_callback: Callable[[], object] | None = None) -> None:
        """Create the catalogue table.

        :param cables: Shared cable catalogue entries.
        :param edit_callback: Function called after changing a physical input.
        :return: None.
        """
        QtCore.QAbstractTableModel.__init__(self)
        self.cables: List[UndergroundCableType] = cables
        self.edit_callback: Callable[[], object] | None = edit_callback
        # Reuse the engine metadata so this editor and the database table expose
        # the same scalar inputs, units and read-only informational fields.
        self.properties: tuple[GCProp, ...] = (
            UndergroundCableType.CLASS_REGISTERED_PROPERTIES['name'],
            *UndergroundCableType.LOCAL_PROPERTY_DECLARATIONS,
        )

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return the catalogue size.

        :param parent: Unused parent index for a flat table.
        :return: Number of cable types.
        """
        return len(self.cables)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return the number of visible cable-construction fields.

        :param parent: Unused parent index for a flat table.
        :return: Number of table columns.
        """
        return len(self.properties)

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> str | None:
        """Return one table header.

        :param section: Header index.
        :param orientation: Header orientation.
        :param role: Qt data role.
        :return: Header text when requested.
        """
        if orientation == QtCore.Qt.Orientation.Horizontal and 0 <= section < len(self.properties):
            prop: GCProp = self.properties[section]
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                label: str = prop.name.replace('_', ' ')
                return f'{label} ({prop.units})' if prop.units else label
            elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
                return prop.definition
            else:
                return None
        else:
            return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """Respect the cable property's editability.

        :param index: Table cell.
        :return: Qt item flags.
        """
        if index.isValid():
            flags: QtCore.Qt.ItemFlag = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
            if self.cables[index.row()].is_property_editable(self.properties[index.column()]):
                return flags | QtCore.Qt.ItemFlag.ItemIsEditable
            else:
                return flags
        else:
            return QtCore.Qt.ItemFlag.NoItemFlags

    def data(self,
             index: QtCore.QModelIndex,
             role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> str | None:
        """Return one scalar cable value or its description.

        :param index: Table cell.
        :param role: Qt data role.
        :return: Display value or ``None`` for unsupported roles.
        """
        if index.isValid():
            cable: UndergroundCableType = self.cables[index.row()]
            prop: GCProp = self.properties[index.column()]
            if role in (QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole):
                return str(cable.get_value(prop=prop, t_idx=None))
            elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
                return prop.definition
            elif role == QtCore.Qt.ItemDataRole.ForegroundRole and not cable.is_property_editable(prop):
                return QtGui.QColor('gray')
            else:
                return None
        else:
            return None

    def setData(self,
                index: QtCore.QModelIndex,
                value: object,
                role: int = QtCore.Qt.ItemDataRole.EditRole) -> bool:
        """Store one edited scalar input using the shared device API.

        :param index: Table cell.
        :param value: Editor value.
        :param role: Qt data role.
        :return: Whether the value was accepted.
        """
        if (index.isValid() and role == QtCore.Qt.ItemDataRole.EditRole
                and self.cables[index.row()].is_property_editable(self.properties[index.column()])):
            cable: UndergroundCableType = self.cables[index.row()]
            prop: GCProp = self.properties[index.column()]
            try:
                cable.set_value(prop=prop, t_idx=None, value=prop.tpe(value))
                accepted: bool = True
            except (TypeError, ValueError):
                accepted = False

            if accepted:
                self.dataChanged.emit(self.index(index.row(), 0),
                                      self.index(index.row(), self.columnCount() - 1),
                                      [QtCore.Qt.ItemDataRole.DisplayRole, role,
                                       QtCore.Qt.ItemDataRole.ForegroundRole])
                if self.edit_callback is not None:
                    self.edit_callback()
                else:
                    pass
            else:
                pass
            return accepted
        else:
            return False


class UndergroundCableSystemModel(QtCore.QAbstractTableModel):
    """Editable view of cables positioned inside one ``TypCabsys``."""

    __slots__ = ('system', 'header', 'edit_callback')

    def __init__(self,
                 system: UndergroundLineType,
                 edit_callback: Callable[[], object] | None = None) -> None:
        """Create the cable-composition model.

        :param system: Cable system edited by the dialog.
        :param edit_callback: Function called after changing a position or phase.
        :return: None.
        """
        QtCore.QAbstractTableModel.__init__(self)
        self.system: UndergroundLineType = system
        self.edit_callback: Callable[[], object] | None = edit_callback
        self.header: List[str] = list(
            ('Cable', 'X (m)', 'Depth (m)', 'Phase', 'Circuit index', 'Phase name')
        )

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return the number of positioned cables.

        :param parent: Unused parent index.
        :return: Composition row count.
        """
        return len(self.system.cables_in_system.data)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """Return the number of composition columns.

        :param parent: Unused parent index.
        :return: Composition column count.
        """
        return len(self.header)

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> str | None:
        """Return one composition header.

        :param section: Header index.
        :param orientation: Header orientation.
        :param role: Qt data role.
        :return: Header text when requested.
        """
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return self.header[section]
        else:
            return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """Allow edits only for position, depth and phase.

        :param index: Table cell.
        :return: Qt item flags.
        """
        if index.isValid() and index.column() in (1, 2, 3):
            return (
                QtCore.Qt.ItemFlag.ItemIsEditable
                | QtCore.Qt.ItemFlag.ItemIsEnabled
                | QtCore.Qt.ItemFlag.ItemIsSelectable
            )
        elif index.isValid():
            return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        else:
            return QtCore.Qt.ItemFlag.NoItemFlags

    def data(self,
             index: QtCore.QModelIndex,
             role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> str | None:
        """Return one cable-composition value.

        :param index: Table cell.
        :param role: Qt data role.
        :return: Display value or ``None``.
        """
        if index.isValid() and role in (
            QtCore.Qt.ItemDataRole.DisplayRole,
            QtCore.Qt.ItemDataRole.EditRole,
        ):
            relation: CableInSystem = self.system.cables_in_system.data[index.row()]
            column: int = index.column()
            if column == 0:
                value: str | float | int = relation.name
            elif column == 1:
                value = relation.xpos
            elif column == 2:
                value = relation.ypos
            elif column == 3:
                value = relation.phase
            elif column == 4:
                value = relation.circuit_index
            else:
                value = relation.phase_type
            return str(value)
        else:
            return None

    def setData(self,
                index: QtCore.QModelIndex,
                value: object,
                role: int = QtCore.Qt.ItemDataRole.EditRole) -> bool:
        """Store one edited position or phase.

        :param index: Table cell.
        :param value: Editor value.
        :param role: Qt data role.
        :return: Whether the value was accepted.
        """
        if index.isValid() and role == QtCore.Qt.ItemDataRole.EditRole and index.column() in (1, 2, 3):
            relation: CableInSystem = self.system.cables_in_system.data[index.row()]
            try:
                if index.column() == 1:
                    relation.xpos = float(value)
                elif index.column() == 2:
                    relation.ypos = float(value)
                else:
                    relation.phase = int(value)
                accepted: bool = True
            except (TypeError, ValueError):
                accepted = False
            if accepted:
                self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), 5), [role])
                if self.edit_callback is not None:
                    self.edit_callback()
                else:
                    pass
            else:
                pass
            return accepted
        else:
            return False

    def add(self, relation: CableInSystem) -> None:
        """Append one cable to the edited system.

        :param relation: New cable-position relationship.
        :return: None.
        """
        row: int = self.rowCount()
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.system.cables_in_system.append(element=relation)
        self.endInsertRows()

    def delete(self, row: int) -> None:
        """Delete one composition row.

        :param row: Zero-based row index.
        :return: None.
        """
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self.system.cables_in_system.data.pop(row)
        self.endRemoveRows()
