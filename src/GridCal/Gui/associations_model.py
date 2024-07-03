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

from typing import Dict, List, Union

from PySide6 import QtCore, QtGui, QtWidgets

from GridCal.Gui.GuiFunctions import (FloatDelegate)
from GridCalEngine.Devices.Associations.association import Association, Associations
from GridCalEngine.Devices.Parents.editable_device import GCProp
from GridCalEngine.Devices.types import ASSOCIATION_TYPES, ALL_DEV_TYPES


def try_convert_to_float(value: str) -> Union[float, str]:
    """

    :param value:
    :return:
    """
    try:
        return float(value)
    except ValueError:
        return value


class AssociationsModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with the properties of objects
    """

    def __init__(self,
                 objects: List[ALL_DEV_TYPES],
                 associated_objects: List[ASSOCIATION_TYPES],
                 gc_prop: GCProp,
                 table_view: QtWidgets.QTableView,
                 decimals: int = 2):
        """

        :param objects:
        :param associated_objects:
        :param gc_prop:
        :param table_view:
        """
        QtCore.QAbstractTableModel.__init__(self)

        self._table_view = table_view

        self._objects: List[ALL_DEV_TYPES] = objects

        self._associated_objects: List[ASSOCIATION_TYPES] = associated_objects

        self._associated_obj_2_idx: Dict[ASSOCIATION_TYPES, int] = dict()

        for i, obj in enumerate(self._associated_objects):
            self._associated_obj_2_idx[obj] = i

        self._gc_prop = gc_prop

        # relate the objects to the associations
        # [object index][associated object index] -> association
        self._sp_data: List[Dict[int, Association]] = list()

        for i, obj in enumerate(self._objects):
            associations_list: List[Association] = getattr(obj, self._gc_prop.name)
            entries_dict = {self._associated_obj_2_idx[asoc.api_object]: asoc for asoc in associations_list}
            self._sp_data.append(entries_dict)

        self._formatter = lambda x: f"%.2f" % x

        self._decimals = decimals

        # self.set_delegates()

    def get_association(self, i: int, j: int) -> Union[None, Association]:
        """
        Get the association at some coordinates
        :param i: row index
        :param j: column index
        :return: Association or None
        """
        # return self._sp_data[i].get(j, None)
        associations: Associations = getattr(self._objects[i], self._gc_prop.name)
        associated_obj = self._associated_objects[j]
        return associations.at_key(associated_obj.idtag)

    def create_association(self, i: int, j: int, value: float) -> Association:
        """
        Get the association at some coordinates
        :param i: row index
        :param j: column index
        :param value: value to associate
        :return: Association
        """
        associations: Associations = getattr(self._objects[i], self._gc_prop.name)
        assoc = associations.add_object(api_object=self._associated_objects[j], val=value)
        return assoc

    def remove_association(self, i: int, j: int) -> None:
        """
        Remove the association at some coordinates
        :param i: row index
        :param j: column index
        :return: Association or None
        """
        associations: Associations = getattr(self._objects[i], self._gc_prop.name)
        associated_obj = self._associated_objects[j]
        associations.remove_by_key(associated_obj.idtag)

    def set_delegates(self) -> None:
        """
        Set the cell editor types depending on the attribute_types array
        """

        for i in range(len(self._associated_objects)):
            delegate = FloatDelegate(self._table_view, decimals=self._decimals)
            self._table_view.setItemDelegateForColumn(i, delegate)

    def update(self):
        """
        update table
        """
        row = self.rowCount()
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        # whatever code
        self.endInsertRows()

    def flags(self, index: QtCore.QModelIndex):
        """
        Get the display mode
        :param index:
        :return:
        """
        return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def rowCount(self, parent: QtCore.QModelIndex = None) -> int:
        """
        Get number of rows
        :param parent:
        :return:
        """
        return len(self._objects)

    def columnCount(self, parent: QtCore.QModelIndex = None) -> int:
        """
        Get number of columns
        :param parent:
        :return:
        """
        return len(self._associated_objects)

    def data(self, index: QtCore.QModelIndex, role=None):
        """
        Get the data to display
        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:

                association = self.get_association(i=index.row(), j=index.column())
                if association is None:
                    return "-"
                else:
                    return str(association.value)

        return None

    def setData(self, index: QtCore.QModelIndex, value: Union[float, str], role: Union[int, None] = None) -> bool:
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """
        if len(self._objects) == 0 or len(self._associated_objects) == 0:
            return True

        value2 = try_convert_to_float(value)

        if isinstance(value2, (float, int)):
            association = self.get_association(i=index.row(), j=index.column())
            if association is None:
                # create an association
                self.create_association(i=index.row(), j=index.column(), value=float(value2))
                print(f"Created association {self._objects[index.row()]} "
                      f"with {self._associated_objects[index.column()]}")
            else:
                # there was a previous association, change the value
                association.value = value2

        elif isinstance(value2, str):
            if str(value2).strip() == "-":
                self.remove_association(i=index.row(), j=index.column())
                print(f"Removed association {self._objects[index.row()]} "
                      f"with {self._associated_objects[index.column()]}")

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

            # Normal
            if orientation == QtCore.Qt.Orientation.Horizontal:
                # return f"H{section}"  #
                # if 0 <= section < len(self._associated_objects):
                return self._associated_objects[section].name

            elif orientation == QtCore.Qt.Orientation.Vertical:
                # return f"V{section}"  #
                # if 0 <= section < len(self._objects):
                return self._objects[section].name

        # add a tooltip
        # elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
        #     if orientation == QtCore.Qt.Orientation.Horizontal:
        #         return f"{section}:{self.associated_objects[section].name}"
        #
        #     elif orientation == QtCore.Qt.Orientation.Vertical:
        #         return f"{section}:{self.objects[section].name}"

        return None
