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
from typing import Dict, List, Union
from PySide6 import QtCore, QtWidgets, QtGui
from enum import EnumMeta
from GridCal.Gui.GuiFunctions import (TextDelegate, ColorPickerDelegate)
from GridCalEngine.Devices import Bus, ContingencyGroup
from GridCalEngine.Devices.Parents.editable_device import GCProp
from GridCalEngine.enumerations import DeviceType
from GridCal.Gui.GuiFunctions import (ComboDelegate, FloatDelegate, ComplexDelegate)
from GridCalEngine.Devices.types import ALL_DEV_TYPES


class RosetaObjectsModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with the properties of objects
    """

    def __init__(self,
                 objects,
                 editable_headers,
                 parent=None,
                 editable=False,
                 non_editable_attributes: Union[None, List[str]] = None,
                 transposed=False,
                 check_unique: Union[None, List[str]] = None,
                 dictionary_of_lists: Union[None, Dict[str, List[ALL_DEV_TYPES]]] = None):
        """

        :param objects: list of objects associated to the editor
        :param editable_headers: Dictionary with the properties and the units and type {attribute: ('unit', type)}
        :param parent: Parent object: the QTableView object
        :param editable: Is the table editable?
        :param non_editable_attributes: List of attributes that are not enabled for editing
        :param transposed: Display the table transposed?
        :param dictionary_of_lists: dictionary of lists for the Delegates
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.parent = parent

        self.attributes = list(editable_headers.keys())

        self.attribute_types = [editable_headers[attr].class_type for attr in self.attributes]

        self.units = [editable_headers[attr].get_unit() for attr in self.attributes]

        self.tips = [editable_headers[attr].description for attr in self.attributes]

        self.objects = objects

        self.editable = editable

        self.non_editable_attributes = non_editable_attributes if non_editable_attributes is not None else list()

        self.check_unique = check_unique if check_unique is not None else list()

        self.r = len(self.objects)

        self.c = len(self.attributes)

        self.formatter = lambda x: "%.2f" % x

        self.transposed = transposed

        self.dictionary_of_lists = dictionary_of_lists if dictionary_of_lists is not None else dict()

        self.set_delegates()

    def set_delegates(self):
        """
        Set the cell editor types depending on the attribute_types array
        :return:
        """

        if self.transposed:
            F = self.parent.setItemDelegateForRow
        else:
            F = self.parent.setItemDelegateForColumn

        for i in range(self.c):
            tpe = self.attribute_types[i]

            if tpe is bool:
                delegate = ComboDelegate(self.parent, [True, False], ['True', 'False'])
                F(i, delegate)

            elif tpe is float:
                delegate = FloatDelegate(self.parent)
                F(i, delegate)

            elif tpe is complex:
                delegate = ComplexDelegate(self.parent)
                F(i, delegate)

            elif tpe is None:
                F(i, None)
                if len(self.non_editable_attributes) == 0:
                    self.non_editable_attributes.append(self.attributes[i])

            elif isinstance(tpe, EnumMeta):
                objects = list(tpe)
                values = [x.value for x in objects]
                delegate = ComboDelegate(self.parent, objects, values)
                F(i, delegate)

            # elif tpe in []:
            #
            #     objects = self.dictionary_of_lists[tpe.value]
            #     values = [x.name for x in objects]
            #     delegate = ComboDelegate(self.parent, objects, values)
            #     F(i, delegate)

            else:
                F(i, None)

    def update(self):
        """
        update table
        """
        row = self.rowCount()
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        # whatever code
        self.endInsertRows()

    def flags(self, index):
        """
        Get the display mode
        :param index:
        :return:
        """
        if self.transposed:
            attr_idx = index.row()
        else:
            attr_idx = index.column()

        if self.editable and self.attributes[attr_idx] not in self.non_editable_attributes:
            return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def rowCount(self, parent=None):
        """
        Get number of rows
        :param parent:
        :return:
        """
        if self.transposed:
            return self.c
        else:
            return self.r

    def columnCount(self, parent=None):
        """
        Get number of columns
        :param parent:
        :return:
        """
        if self.transposed:
            return self.r
        else:
            return self.c

    def data_raw(self, r: int, c: int):
        """
        Get the data to display
        :param r: row index
        :param c: col index
        :return:
        """

        if self.transposed:
            obj_idx = c
            attr_idx = r
        else:
            obj_idx = r
            attr_idx = c

        attr = self.attributes[attr_idx]

        return getattr(self.objects[obj_idx], attr)

    def data_with_type(self, index):
        """
        Get the data to display
        :param index:
        :return:
        """

        if self.transposed:
            obj_idx = index.column()
            attr_idx = index.row()
        else:
            obj_idx = index.row()
            attr_idx = index.column()

        attr = self.attributes[attr_idx]

        return getattr(self.objects[obj_idx], attr)

    def data(self, index, role=None):
        """
        Get the data to display
        :param index:
        :param role:
        :return:
        """
        if index.isValid() and role == QtCore.Qt.ItemDataRole.DisplayRole:
            return str(self.data_with_type(index))

        return None

    def setData(self, index: QtCore.QModelIndex, value, role=None):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """

        if self.transposed:
            obj_idx = index.column()
            attr_idx = index.row()
        else:
            obj_idx = index.row()
            attr_idx = index.column()

        # check taken values
        if self.attributes[attr_idx] in self.check_unique:
            taken = self.attr_taken(self.attributes[attr_idx], value)
        else:
            taken = False

        if not taken:
            if self.attributes[attr_idx] not in self.non_editable_attributes:
                setattr(self.objects[obj_idx], self.attributes[attr_idx], value)
            else:
                pass  # the column cannot be edited

        return True

    def attr_taken(self, attr, val):
        """
        Checks if the attribute value is taken
        :param attr:
        :param val:
        :return:
        """
        for obj in self.objects:
            if val == getattr(obj, attr):
                return True
        return False

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

            if self.transposed:
                # for the properties in the schematic view
                if orientation == QtCore.Qt.Orientation.Horizontal:
                    return 'Value'
                elif orientation == QtCore.Qt.Orientation.Vertical:
                    if self.units[section] != '':
                        return self.attributes[section]  # + ' [' + self.units[p_int] + ']'
                    else:
                        return self.attributes[section]
            else:
                # Normal
                if orientation == QtCore.Qt.Orientation.Horizontal:
                    if self.units[section] != '':
                        return self.attributes[section]  # + ' [' + self.units[p_int] + ']'
                    else:
                        return self.attributes[section]
                elif orientation == QtCore.Qt.Orientation.Vertical:
                    return str(section)  # + ':' + str(self.objects[p_int])

        # add a tooltip
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            if section < self.c:
                if self.units[section] != "":
                    unit = '\nUnits: ' + self.units[section]
                else:
                    unit = ''
                return self.attributes[section] + unit + ' \n' + self.tips[section]
            else:
                # somehow the index is out of range
                return ""

        return None

    def copy_to_column(self, index):
        """
        Copy the value pointed by the index to all the other cells in the column
        :param index: QModelIndex instance
        :return:
        """
        value = self.data_with_type(index=index)
        col = index.column()

        for row in range(self.rowCount()):

            if self.transposed:
                obj_idx = col
                attr_idx = row
            else:
                obj_idx = row
                attr_idx = col

            if self.attributes[attr_idx] not in self.non_editable_attributes:
                setattr(self.objects[obj_idx], self.attributes[attr_idx], value)
            else:
                pass  # the column cannot be edited

    def get_data(self):
        """

        :return:
        """
        nrows = self.rowCount()
        ncols = self.columnCount()
        data = np.empty((nrows, ncols), dtype=object)

        for j in range(ncols):
            for i in range(nrows):
                data[i, j] = self.data_raw(r=i, c=j)

        columns = [self.headerData(i, orientation=QtCore.Qt.Orientation.Horizontal,
                                   role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(ncols)]

        index = [self.headerData(i, orientation=QtCore.Qt.Orientation.Vertical,
                                 role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(nrows)]

        return index, columns, data

    def copy_to_clipboard(self):
        """

        :return:
        """
        if self.columnCount() > 0:

            index, columns, data = self.get_data()

            data = data.astype(str)

            # header first
            txt = '\t' + '\t'.join(columns) + '\n'

            # data
            for t, index_value in enumerate(index):
                txt += str(index_value) + '\t' + '\t'.join(data[t, :]) + '\n'

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText(txt)


class ObjectsModelOld(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with the properties of objects
    """

    def __init__(self,
                 objects: List[ALL_DEV_TYPES],
                 editable_headers: Dict[str, GCProp],
                 parent=None,
                 editable=False,
                 transposed=False,
                 check_unique: Union[None, List[str]] = None,
                 dictionary_of_lists: Union[None, Dict[str, List[ALL_DEV_TYPES]]] = None):
        """

        :param objects: list of objects associated to the editor
        :param editable_headers: Dictionary with the properties and the units and type {attribute: ('unit', type)}
        :param parent: Parent object: the QTableView object
        :param editable: Is the table editable?
        :param transposed: Display the table transposed?
        :param dictionary_of_lists: dictionary of lists for the Delegates
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.parent = parent

        self.attributes = list(editable_headers.keys())

        self.attribute_types = [editable_headers[attr].tpe for attr in self.attributes]

        self.units = [editable_headers[attr].units for attr in self.attributes]

        self.tips = [editable_headers[attr].definition for attr in self.attributes]

        self.objects = objects

        self.editable = editable

        self.non_editable_attributes = [attr for attr in self.attributes if not editable_headers[attr].editable]

        self.check_unique = check_unique if check_unique is not None else list()

        self.r = len(self.objects)

        self.c = len(self.attributes)

        self.formatter = lambda x: "%.2f" % x

        self.transposed = transposed

        self.dictionary_of_lists = dictionary_of_lists if dictionary_of_lists is not None else dict()

        self.set_delegates()

    def set_delegates(self) -> None:
        """
        Set the cell editor types depending on the attribute_types array
        """

        if self.transposed:
            F = self.parent.setItemDelegateForRow
        else:
            F = self.parent.setItemDelegateForColumn

        for i in range(self.c):
            tpe = self.attribute_types[i]

            if tpe is bool:
                delegate = ComboDelegate(self.parent, [True, False], ['True', 'False'])
                F(i, delegate)

            elif tpe is str:

                if 'color' in self.attributes[i]:
                    delegate = ColorPickerDelegate(self.parent)
                else:
                    delegate = TextDelegate(self.parent)

                F(i, delegate)

            elif tpe is float:
                delegate = FloatDelegate(self.parent)
                F(i, delegate)

            elif tpe is complex:
                delegate = ComplexDelegate(self.parent)
                F(i, delegate)

            elif tpe is None:
                F(i, None)
                if len(self.non_editable_attributes) == 0:
                    self.non_editable_attributes.append(self.attributes[i])

            elif isinstance(tpe, EnumMeta):
                objects = list(tpe)
                values = [x.value for x in objects]
                delegate = ComboDelegate(self.parent, objects, values)
                F(i, delegate)

            elif tpe in [DeviceType.SubstationDevice,
                         DeviceType.AreaDevice,
                         DeviceType.ZoneDevice,
                         DeviceType.CountryDevice,
                         DeviceType.Technology,
                         DeviceType.ContingencyGroupDevice,
                         DeviceType.InvestmentsGroupDevice,
                         DeviceType.FuelDevice,
                         DeviceType.EmissionGasDevice,
                         DeviceType.GeneratorDevice]:

                objects = self.dictionary_of_lists[str(tpe.value)]
                values = [x.name for x in objects]
                delegate = ComboDelegate(self.parent, objects, values)
                F(i, delegate)

            else:
                F(i, None)

    def update(self):
        """
        update table
        """
        row = self.rowCount()
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        # whatever code
        self.endInsertRows()

    def flags(self, index):
        """
        Get the display mode
        :param index:
        :return:
        """
        if self.transposed:
            attr_idx = index.row()
        else:
            attr_idx = index.column()

        if self.editable and self.attributes[attr_idx] not in self.non_editable_attributes:
            return (
                    QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def rowCount(self, parent=None):
        """
        Get number of rows
        :param parent:
        :return:
        """
        if self.transposed:
            return self.c
        else:
            return self.r

    def columnCount(self, parent=None):
        """
        Get number of columns
        :param parent:
        :return:
        """
        if self.transposed:
            return self.r
        else:
            return self.c

    def data_raw(self, r: int, c: int):
        """
        Get the data to display
        :param r: row index
        :param c: col index
        :return:
        """

        if self.transposed:
            obj_idx = c
            attr_idx = r
        else:
            obj_idx = r
            attr_idx = c

        attr = self.attributes[attr_idx]
        tpe = self.attribute_types[attr_idx]

        if tpe is Bus:
            return getattr(self.objects[obj_idx], attr).name
        else:
            return getattr(self.objects[obj_idx], attr)

    def data_with_type(self, index: QtCore.QModelIndex):
        """
        Get the data to display
        :param index:
        :return:
        """

        if self.transposed:
            obj_idx = index.column()
            attr_idx = index.row()
        else:
            obj_idx = index.row()
            attr_idx = index.column()

        attr = self.attributes[attr_idx]
        tpe = self.attribute_types[attr_idx]

        if tpe is Bus:
            return getattr(self.objects[obj_idx], attr).name
        else:
            return getattr(self.objects[obj_idx], attr)

    def data(self, index, role=None):
        """
        Get the data to display
        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                return str(self.data_with_type(index))
            elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
                if 'color' in self.attributes[index.column()]:
                    return QtGui.QColor(str(self.data_with_type(index)))

        return None

    def setData(self, index, value, role=None):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """

        if self.transposed:
            obj_idx = index.column()
            attr_idx = index.row()
        else:
            obj_idx = index.row()
            attr_idx = index.column()

        tpe = self.attribute_types[attr_idx]

        # check taken values
        if self.attributes[attr_idx] in self.check_unique:
            taken = self.attr_taken(self.attributes[attr_idx], value)
        else:
            taken = False

        if not taken:
            if self.attributes[attr_idx] not in self.non_editable_attributes:

                if tpe is ContingencyGroup:
                    if value != "":
                        setattr(self.objects[obj_idx], self.attributes[attr_idx], ContingencyGroup(value))
                else:
                    setattr(self.objects[obj_idx], self.attributes[attr_idx], value)
            else:
                pass  # the column cannot be edited

        return True

    def attr_taken(self, attr, val):
        """
        Checks if the attribute value is taken
        :param attr:
        :param val:
        :return:
        """
        for obj in self.objects:
            if val == getattr(obj, attr):
                return True
        return False

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

            if self.transposed:
                # for the properties in the schematic view
                if orientation == QtCore.Qt.Orientation.Horizontal:
                    return 'Value'
                elif orientation == QtCore.Qt.Orientation.Vertical:
                    if self.units[section] != '':
                        return self.attributes[section] + ' [' + self.units[section] + ']'
                    else:
                        return self.attributes[section]
            else:
                # Normal
                if orientation == QtCore.Qt.Orientation.Horizontal:
                    if self.units[section] != '':
                        return self.attributes[section] + ' [' + self.units[section] + ']'
                    else:
                        return self.attributes[section]
                elif orientation == QtCore.Qt.Orientation.Vertical:
                    return str(section) + ':' + str(self.objects[section])

        # add a tooltip
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            if section < self.c:
                if self.units[section] != "":
                    unit = '\nUnits: ' + self.units[section]
                else:
                    unit = ''
                return self.attributes[section] + unit + ' \n' + self.tips[section]
            else:
                # somehow the index is out of range
                return ""

        return None

    def copy_to_column(self, index):
        """
        Copy the value pointed by the index to all the other cells in the column
        :param index: QModelIndex instance
        :return:
        """
        value = self.data_with_type(index=index)
        col = index.column()

        for row in range(self.rowCount()):

            if self.transposed:
                obj_idx = col
                attr_idx = row
            else:
                obj_idx = row
                attr_idx = col

            if self.attributes[attr_idx] not in self.non_editable_attributes:
                setattr(self.objects[obj_idx], self.attributes[attr_idx], value)
            else:
                pass  # the column cannot be edited

    def get_data(self):
        """

        :return:
        """
        nrows = self.rowCount()
        ncols = self.columnCount()
        data = np.empty((nrows, ncols), dtype=object)

        for j in range(ncols):
            for i in range(nrows):
                data[i, j] = self.data_raw(r=i, c=j)

        columns = [self.headerData(i, orientation=QtCore.Qt.Orientation.Horizontal,
                                   role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(ncols)]

        index = [self.headerData(i, orientation=QtCore.Qt.Orientation.Vertical,
                                 role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(nrows)]

        return index, columns, data

    def copy_to_clipboard(self):
        """

        :return:
        """
        if self.columnCount() > 0:

            index, columns, data = self.get_data()

            data = data.astype(str)

            # header first
            txt = '\t' + '\t'.join(columns) + '\n'

            # data
            for t, index_value in enumerate(index):
                txt += str(index_value) + '\t' + '\t'.join(data[t, :]) + '\n'

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText(txt)
