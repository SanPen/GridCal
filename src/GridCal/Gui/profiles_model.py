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
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Union
from PySide6 import QtCore, QtWidgets
from warnings import warn

from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.enumerations import DeviceType
from GridCal.Gui.GuiFunctions import (ComboDelegate, TextDelegate, FloatDelegate, ComplexDelegate)


class ObjectHistory:
    """
    ObjectHistory
    """

    def __init__(self, max_undo_states: int = 100) -> None:
        """
        Constructor
        :param max_undo_states: maximum number of undo states
        """
        self.max_undo_states = max_undo_states
        self.position = 0
        self.undo_stack = list()
        self.redo_stack = list()

    def add_state(self, action_name, data: dict):
        """
        Add an undo state
        :param action_name: name of the action that was performed
        :param data: dictionary {column index -> profile array}
        """

        # if the stack is too long delete the oldest entry
        if len(self.undo_stack) > (self.max_undo_states + 1):
            self.undo_stack.pop(0)

        # stack the newest entry
        self.undo_stack.append((action_name, data))

        self.position = len(self.undo_stack) - 1

        # print('Stored', action_name)

    def redo(self):
        """
        Re-do table
        :return: table instance
        """
        val = self.redo_stack.pop()
        self.undo_stack.append(val)
        return val

    def undo(self):
        """
        Un-do table
        :return: table instance
        """
        val = self.undo_stack.pop()
        self.redo_stack.append(val)
        return val

    def can_redo(self):
        """
        is it possible to redo?
        :return: True / False
        """
        return len(self.redo_stack) > 0

    def can_undo(self):
        """
        Is it possible to undo?
        :return: True / False
        """
        return len(self.undo_stack) > 0


class ProfilesModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with profiles from objects
    """

    def __init__(self,
                 time_array: pd.DatetimeIndex,
                 elements: List[EditableDevice],
                 device_type: DeviceType,
                 magnitude: str,
                 data_format,
                 parent,
                 max_undo_states=100):
        """

        :param time_array: array of time
        :param device_type: string with Load, StaticGenerator, etc...
        :param magnitude: magnitude to display 'S', 'P', etc...
        :param data_format:
        :param parent: Parent object: the QTableView object
        :param max_undo_states:
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.parent = parent

        self.data_format = data_format

        self.time_array = time_array

        self.device_type = device_type

        self.magnitude = magnitude

        self.non_editable_indices = list()

        self.editable = True

        self.elements = elements

        self.formatter = lambda x: "%.2f" % x

        # contains copies of the table
        self.history = ObjectHistory(max_undo_states)

        # add the initial state
        # self.add_state(columns=range(self.columnCount()), action_name='initial')

        self.set_delegates()

    def set_delegates(self) -> None:
        """
        Set the cell editor types depending on the attribute_types array
        :return:
        """

        if self.data_format is bool:
            delegate = ComboDelegate(self.parent, [True, False], ['True', 'False'])
            self.parent.setItemDelegate(delegate)

        elif self.data_format is float:
            delegate = FloatDelegate(self.parent)
            self.parent.setItemDelegate(delegate)

        elif self.data_format is str:
            delegate = TextDelegate(self.parent)
            self.parent.setItemDelegate(delegate)

        elif self.data_format is complex:
            delegate = ComplexDelegate(self.parent)
            self.parent.setItemDelegate(delegate)

    def update(self):
        """
        update
        """
        # row = self.rowCount()
        # self.beginInsertRows(QtCore.QModelIndex(), row, row)
        # # whatever code
        # self.endInsertRows()

        self.layoutAboutToBeChanged.emit()

        self.layoutChanged.emit()

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """
        Get the display mode
        :param index:
        :return:
        """

        if self.editable and index.column() not in self.non_editable_indices:
            return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def rowCount(self, parent: QtCore.QModelIndex = None) -> int:
        """
        Get number of rows
        :param parent:
        :return:
        """
        return len(self.time_array)

    def columnCount(self, parent: Union[None, QtCore.QModelIndex] = None) -> int:
        """
        Get number of columns
        :param parent:
        :return:
        """
        return len(self.elements)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Union[str, None]:
        """
        Get the data to display
        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                c = index.column()
                r = index.row()
                profile_attr_name = self.elements[c].properties_with_profile[self.magnitude]
                profile = getattr(self.elements[c], profile_attr_name)
                return str(profile[r])

        return None

    def setData(self,
                index: QtCore.QModelIndex,
                value: float,
                role: QtCore.Qt.ItemDataRole = QtCore.Qt.ItemDataRole.DisplayRole) -> bool:
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """
        c = index.column()
        if c not in self.non_editable_indices:
            r = index.row()
            profile_attr_name = self.elements[index.column()].properties_with_profile[self.magnitude]
            profile = getattr(self.elements[index.column()], profile_attr_name)
            profile[r] = value

            # self.add_state(columns=[c], action_name='')
        else:
            pass  # the column cannot be edited

        return True

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role=QtCore.Qt.ItemDataRole.DisplayRole):
        """
        Get the headers to display
        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if len(self.elements):
                if orientation == QtCore.Qt.Orientation.Horizontal:
                    return str(self.elements[section].name)
                elif orientation == QtCore.Qt.Orientation.Vertical:
                    if self.time_array is None:
                        return str(section)
                    else:
                        return pd.to_datetime(self.time_array[section]).strftime('%d-%m-%Y %H:%M:%S')

        return None

    def paste_from_clipboard(self, row_idx=0, col_idx=0):
        """

        Args:
            row_idx:
            col_idx:
        """
        n = len(self.elements)
        nt = len(self.time_array)

        if n > 0:
            formatter = self.elements[0].registered_properties[self.magnitude].tpe

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            text = cb.text()

            rows = text.split('\n')

            mod_cols = list()

            # gather values
            for r, row in enumerate(rows):

                values = row.split('\t')
                r2 = r + row_idx
                for c, val in enumerate(values):

                    c2 = c + col_idx

                    try:
                        val2 = formatter(val)
                        parsed = True
                    except:
                        warn("could not parse '" + str(val) + "'")
                        parsed = False
                        val2 = ''

                    if parsed:
                        if c2 < n and r2 < nt:
                            mod_cols.append(c2)
                            prof = self.elements[c2].get_profile(magnitude=self.magnitude)
                            arr = prof.toarray()
                            arr[r2] = val2
                            prof.set(arr)
                        else:
                            print('Out of profile bounds')

        else:
            # there are no elements
            pass

    def copy_to_clipboard(self, cols: Union[None, List[int]] = None) -> None:
        """
        Copy profiles to clipboard
        :param cols:
        :return:
        """

        elements = self.elements if cols is None else [self.elements[i] for i in cols]

        n = len(elements)

        if n > 0:

            nt = len(self.time_array)

            # gather values
            names = np.empty(n, dtype=object)
            values = np.empty((nt, n), dtype=object)

            for c in range(n):
                names[c] = elements[c].name
                prof = elements[c].get_profile(self.magnitude)
                values[:, c] = prof.toarray().astype(str)

            # header first
            data = '\t' + '\t'.join(names) + '\n'

            # data
            for t, date in enumerate(self.time_array):
                data += str(date) + '\t' + '\t'.join(values[t, :]) + '\n'

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText(data)

        else:
            # there are no elements
            pass

    def add_state(self, columns: List[int], action_name: str = ''):
        """
        Compile data of an action and store the data in the undo history
        :param columns: list of column indices changed
        :param action_name: name of the action
        :return: None
        """
        data = dict()

        for col in columns:
            # profile_property = self.elements[col].properties_with_profile[self.magnitude]
            # data[col] = getattr(self.elements[col], profile_property).copy()
            data[col] = self.elements[col].get_profile(self.magnitude)
            # TODO: check if devices do not have a profile

        self.history.add_state(action_name, data)

    def restore(self, data: dict):
        """
        Set profiles data from undo history
        :param data: dictionary comming from the history
        :return:
        """
        for col, array in data.items():
            profile_property = self.elements[col].properties_with_profile[self.magnitude]
            setattr(self.elements[col], profile_property, array)

    def undo(self):
        """
        Un-do table changes
        """
        if self.history.can_undo():
            action, data = self.history.undo()

            self.restore(data)

            print('Undo ', action)

            self.update()

    def redo(self):
        """
        Re-do table changes
        """
        if self.history.can_redo():
            action, data = self.history.redo()

            self.restore(data)

            print('Redo ', action)

            self.update()
