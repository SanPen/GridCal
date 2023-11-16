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

import numpy as np
import pandas as pd
from typing import Dict, List, Union, Any, Tuple
from PySide6 import QtCore, QtWidgets, QtGui
from warnings import warn
from enum import EnumMeta
from collections import defaultdict

from GridCalEngine.Core.Devices import BranchTemplate, Bus, ContingencyGroup
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.basic_structures import IntVec
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_circuit import CgmesCircuit, IdentifiedObject
import GridCal


class TreeDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning QComboBox in every
    cell of the column to which it's applied
    """
    commitData = QtCore.Signal(object)
    """
    
    """
    def __init__(self, parent, data=defaultdict()):
        """
        Constructor
        :param parent: QTableView parent object
        :param data: dictionary of lists
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

        # dictionary of lists
        self.data = data

    @QtCore.Slot()
    def double_click(self):
        """
        double click
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        tree = QtWidgets.QTreeView(parent)

        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(['Template'])

        for key in self.data.keys():
            # add parent node
            parent1 = QtGui.QStandardItem(str(key))

            # add children to parent
            for elm in self.data[key]:
                child1 = QtGui.QStandardItem(str(elm))
                parent1.appendRow([child1])

            model.appendRow(parent1)

        tree.setModel(model)
        tree.doubleClicked.connect(self.double_click)
        return tree

    def setEditorData(self, editor, index):
        """

        :param editor:
        :param index:
        """
        print(editor)
        print(index)

    def setModelData(self, editor, model, index):
        """

        :param editor:
        :param model:
        :param index:
        """
        print(editor)
        print(model)
        print(index)

        # model.setData(index, self.object_names[editor.currentIndex()])


class ComboDelegate(QtWidgets.QItemDelegate):

    """
    A delegate that places a fully functioning QComboBox in every
    cell of the column to which it's applied
    """
    commitData = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QTableView, objects: List[bool], object_names: List[str]) -> None:
        """
        Constructor
        :param parent: QTableView parent object
        :param objects: List of objects to set. i.e. [True, False]
        :param object_names: List of Object names to display. i.e. ['True', 'False']
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

        # objects to sent to the model associated to the combobox. i.e. [True, False]
        self.objects = objects

        # object description to display in the combobox. i.e. ['True', 'False']
        self.object_names = object_names

    @QtCore.Slot()
    def currentIndexChanged(self):
        """
        currentIndexChanged
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(self.object_names)
        combo.currentIndexChanged.connect(self.currentIndexChanged)
        return combo

    def setEditorData(self, editor, index):
        """

        :param editor:
        :param index:
        """
        editor.blockSignals(True)
        val = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
        try:
            idx = self.object_names.index(val)
            editor.setCurrentIndex(idx)
            editor.blockSignals(False)
        except ValueError:
            pass

    def setModelData(self, editor, model, index):
        """

        :param editor:
        :param model:
        :param index:
        """
        if len(self.objects) > 0:
            if editor.currentIndex() < len(self.objects):
                model.setData(index, self.objects[editor.currentIndex()])


class TextDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning QLineEdit in every
    cell of the column to which it's applied
    """

    commitData = QtCore.Signal(object)

    def __init__(self, parent):
        """
        Constructor
        :param parent: QTableView parent object
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

    @QtCore.Slot()
    def returnPressed(self):
        """
        returnPressed
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        editor = QtWidgets.QLineEdit(parent)
        editor.returnPressed.connect(self.returnPressed)
        return editor

    def setEditorData(self, editor, index):
        """

        :param editor:
        :param index:
        """
        editor.blockSignals(True)
        val = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
        editor.setText(val)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        """

        :param editor:
        :param model:
        :param index:
        """
        model.setData(index, editor.text())


class FloatDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning QDoubleSpinBox in every
    cell of the column to which it's applied
    """

    commitData = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QTableView, min_: float = -1e200, max_: float = 1e200) -> None:
        """
        Constructor
        :param parent: QTableView parent object
        """
        QtWidgets.QItemDelegate.__init__(self, parent)
        self.min = min_
        self.max = max_

    @QtCore.Slot()
    def returnPressed(self):
        """
        returnPressed
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        editor = QtWidgets.QDoubleSpinBox(parent)
        editor.setMaximum(self.max)
        editor.setMinimum(self.min)
        editor.setDecimals(8)
        editor.editingFinished.connect(self.returnPressed)
        return editor

    def setEditorData(self, editor, index):
        """

        :param editor:
        :param index:
        """
        editor.blockSignals(True)
        val = float(index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole))
        editor.setValue(val)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        """

        :param editor:
        :param model:
        :param index:
        """
        model.setData(index, editor.value())


class ComplexDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning Complex Editor in every
    cell of the column to which it's applied
    """

    commitData = QtCore.Signal(object)

    def __init__(self, parent):
        """
        Constructor
        :param parent: QTableView parent object
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

    @QtCore.Slot()
    def returnPressed(self):
        """

        :return:
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        editor = QtWidgets.QFrame(parent)
        main_layout = QtWidgets.QHBoxLayout(editor)
        main_layout.layout().setContentsMargins(0, 0, 0, 0)

        real = QtWidgets.QDoubleSpinBox()
        real.setMaximum(9999)
        real.setMinimum(-9999)
        real.setDecimals(8)

        imag = QtWidgets.QDoubleSpinBox()
        imag.setMaximum(9999)
        imag.setMinimum(-9999)
        imag.setDecimals(8)

        main_layout.addWidget(real)
        main_layout.addWidget(imag)
        # main_layout.addWidget(button)

        # button.clicked.connect(self.returnPressed)

        return editor

    def setEditorData(self, editor: QtWidgets.QFrame, index):
        """

        :param editor:
        :param index:
        :return:
        """
        editor.blockSignals(True)
        val = complex(index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole))
        editor.children()[1].setValue(val.real)
        editor.children()[2].setValue(val.imag)
        editor.blockSignals(False)

    def setModelData(self, editor: QtWidgets.QFrame, model, index):
        """

        :param editor:
        :param model:
        :param index:
        :return:
        """
        val = complex(editor.children()[1].value(), editor.children()[2].value())
        model.setData(index, val)


class ColorPickerDelegate(QtWidgets.QItemDelegate):
    """
    Color picker delegate
    """
    commitData = QtCore.Signal(object)

    def __init__(self, parent):
        """

        :param parent:
        """
        super(ColorPickerDelegate, self).__init__(parent)

    @QtCore.Slot()
    def returnPressed(self):
        """

        :return:
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        colorDialog = QtWidgets.QColorDialog(parent)
        return colorDialog

    def setEditorData(self, editor: QtWidgets.QColorDialog, index):
        editor.blockSignals(True)
        val = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
        color = QtGui.QColor.fromString(val)
        editor.setCurrentColor(color)
        editor.blockSignals(False)

    def setModelData(self, editor: QtWidgets.QColorDialog, model, index):
        """

        :param editor:
        :param model:
        :param index:
        :return:
        """
        model.setData(index, editor.currentColor().name())


class PandasModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """
    def __init__(self, data: pd.DataFrame, parent=None, editable=False, editable_min_idx=-1, decimals=6):
        """

        :param data:
        :param parent:
        :param editable:
        :param editable_min_idx:
        :param decimals:
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.data_c = data.values
        self.cols_c = data.columns
        self.index_c = data.index.values
        self.editable = editable
        self.editable_min_idx = editable_min_idx
        self.r, self.c = self.data_c.shape
        self.isDate = False
        if self.r > 0 and self.c > 0:
            if isinstance(self.index_c[0], np.datetime64):
                self.index_c = pd.to_datetime(self.index_c)
                self.isDate = True

        self.format_string = '.' + str(decimals) + 'f'

        self.formatter = lambda x: "%.2f" % x

    def flags(self, index):
        if self.editable and index.column() > self.editable_min_idx:
            return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def rowCount(self, parent=None):
        """

        :param parent:
        :return:
        """
        return self.r

    def columnCount(self, parent=None):
        """

        :param parent:
        :return:
        """
        return self.c

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid() and role == QtCore.Qt.ItemDataRole.DisplayRole:

            val = self.data_c[index.row(), index.column()]
            if isinstance(val, str):
                return val
            elif isinstance(val, complex):
                if val.real != 0 or val.imag != 0:
                    return val.__format__(self.format_string)
                else:
                    return '0'
            else:
                if val != 0:
                    return val.__format__(self.format_string)
                else:
                    return '0'
        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        self.data_c[index.row(), index.column()] = value
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
                return self.cols_c[section]
            elif orientation == QtCore.Qt.Orientation.Vertical:
                if self.index_c is None:
                    return section
                else:
                    if self.isDate:
                        return self.index_c[section].strftime('%Y/%m/%d  %H:%M.%S')
                    else:
                        return str(self.index_c[section])
        return None

    def copy_to_column(self, row, col):
        """
        Copies one value to all the column
        @param row: Row of the value
        @param col: Column of the value
        @return: Nothing
        """
        self.data_c[:, col] = self.data_c[row, col]

    def is_complex(self) -> bool:
        """
        id the data type complex?
        :return: True / False
        """
        return self.data_c.dtype == complex

    def is_2d(self) -> bool:
        """
        actually check if the array is 1D or 2D
        :return: true if it is really a 2D data set
        """

        is_2d_ = len(self.data_c.shape) == 2
        if is_2d_:
            if self.data_c.shape[1] <= 1:
                is_2d_ = False
        return is_2d_

    def get_data(self, mode=None):
        """

        Args:
            mode: 'real', 'imag', 'abs'

        Returns: index, columns, data

        """
        n = len(self.cols_c)

        if n > 0:
            # gather values
            if type(self.cols_c) == pd.Index:
                names = self.cols_c.values

                if len(names) > 0:
                    if type(names[0]) == ResultTypes:
                        names = [val.name for val in names]

            elif type(self.cols_c) == ResultTypes:
                names = [val.name for val in self.cols_c]
            else:
                names = [val.name for val in self.cols_c]

            if self.is_complex():

                if mode == 'real':
                    values = self.data_c.real
                elif mode == 'imag':
                    values = self.data_c.imag
                elif mode == 'abs':
                    values = np.abs(self.data_c)
                else:
                    values = self.data_c.astype(object)

            else:
                values = self.data_c

            return self.index_c, names, values
        else:
            # there are no elements
            return list(), list(), list()

    def get_df(self, mode=None):
        """
        Get the data as pandas DataFrame
        :return: DataFrame
        """
        index, columns, data = self.get_data(mode=mode)
        return pd.DataFrame(data=data, index=index, columns=columns)

    def save_to_excel(self, file_name, mode):
        """
        Save the data to excel
        Args:
            file_name:
            mode: 'real', 'imag', 'abs'

        Returns:

        """
        index, columns, data = self.get_data(mode=mode)

        df = pd.DataFrame(data=data, index=index, columns=columns)
        df.to_excel(file_name)

    def copy_to_clipboard(self, mode=None):
        """
        Copy profiles to clipboard
        Args:
            mode: 'real', 'imag', 'abs'
        """
        n = len(self.cols_c)

        if n > 0:

            if mode == 'numpy':
                txt = fast_data_to_numpy_text(self.data_c)
            else:
                index, columns, data = self.get_data(mode=mode)

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


class ObjectsModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with the properties of objects
    """
    def __init__(self, objects, editable_headers, parent=None, editable=False,
                 non_editable_attributes=list(), transposed=False, check_unique=list(),
                 dictionary_of_lists={}):
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

        self.attribute_types = [editable_headers[attr].tpe for attr in self.attributes]

        self.units = [editable_headers[attr].units for attr in self.attributes]

        self.tips = [editable_headers[attr].definition for attr in self.attributes]

        self.objects = objects

        self.editable = editable

        self.non_editable_attributes = non_editable_attributes

        self.check_unique = check_unique

        self.r = len(self.objects)

        self.c = len(self.attributes)

        self.formatter = lambda x: "%.2f" % x

        self.transposed = transposed

        self.dictionary_of_lists = dictionary_of_lists

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

            elif tpe is BranchTemplate or tpe is str:

                if 'color' in self.attributes[i]:
                    delegate = ColorPickerDelegate(self.parent)
                else:
                    delegate = TextDelegate(self.parent)

                F(i, delegate)

            elif tpe is BranchTemplate:
                F(i, None)

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

                objects = self.dictionary_of_lists[tpe.value]
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

    def data_raw(self, r, c):
        """
        Get the data to display
        :param index:
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


class ObjectHistory:
    """
    ObjectHistory
    """

    def __init__(self, max_undo_states=100):
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


class RosetaObjectsModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with the properties of objects
    """
    def __init__(self, objects, editable_headers, parent=None, editable=False,
                 non_editable_attributes=list(), transposed=False, check_unique=list(),
                 dictionary_of_lists={}):
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

        self.non_editable_attributes = non_editable_attributes

        self.check_unique = check_unique

        self.r = len(self.objects)

        self.c = len(self.attributes)

        self.formatter = lambda x: "%.2f" % x

        self.transposed = transposed

        self.dictionary_of_lists = dictionary_of_lists

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

    def data_raw(self, r, c):
        """
        Get the data to display
        :param index:
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
        tpe = self.attribute_types[attr_idx]

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


class ProfilesModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with profiles from objects
    """
    def __init__(self, multi_circuit, device_type: DeviceType, magnitude, format, parent, max_undo_states=100):
        """

        Args:
            multi_circuit: MultiCircuit instance
            device_type: string with Load, StaticGenerator, etc...
            magnitude: magnitude to display 'S', 'P', etc...
            parent: Parent object: the QTableView object
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.parent = parent

        self.format = format

        self.circuit = multi_circuit

        self.device_type = device_type

        self.magnitude = magnitude

        self.non_editable_indices = list()

        self.editable = True

        self.r = len(self.circuit.time_profile)

        self.elements = self.circuit.get_elements_by_type(device_type)

        self.c = len(self.elements)

        self.formatter = lambda x: "%.2f" % x

        # contains copies of the table
        self.history = ObjectHistory(max_undo_states)

        # add the initial state
        self.add_state(columns=range(self.columnCount()), action_name='initial')

        self.set_delegates()

    def set_delegates(self):
        """
        Set the cell editor types depending on the attribute_types array
        :return:
        """

        if self.format is bool:
            delegate = ComboDelegate(self.parent, [True, False], ['True', 'False'])
            self.parent.setItemDelegate(delegate)

        elif self.format is float:
            delegate = FloatDelegate(self.parent)
            self.parent.setItemDelegate(delegate)

        elif self.format is str:
            delegate = TextDelegate(self.parent)
            self.parent.setItemDelegate(delegate)

        elif self.format is complex:
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

    def flags(self, index):
        """
        Get the display mode
        :param index:
        :return:
        """

        if self.editable and index.column() not in self.non_editable_indices:
            return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def rowCount(self, parent=None):
        """
        Get number of rows
        :param parent:
        :return:
        """
        return self.r

    def columnCount(self, parent=None):
        """
        Get number of columns
        :param parent:
        :return:
        """
        return self.c

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """
        Get the data to display
        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                profile_property = self.elements[index.column()].properties_with_profile[self.magnitude]
                array = getattr(self.elements[index.column()], profile_property)
                return str(array[index.row()])

        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """
        c = index.column()
        r = index.row()
        if c not in self.non_editable_indices:
            profile_property = self.elements[c].properties_with_profile[self.magnitude]
            getattr(self.elements[c], profile_property)[r] = value

            self.add_state(columns=[c], action_name='')
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
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return str(self.elements[section].name)
            elif orientation == QtCore.Qt.Orientation.Vertical:
                if self.circuit.time_profile is None:
                    return str(section)
                else:
                    return pd.to_datetime(self.circuit.time_profile[section]).strftime('%d-%m-%Y %H:%M')

        return None

    def paste_from_clipboard(self, row_idx=0, col_idx=0):
        """

        Args:
            row_idx:
            col_idx:
        """
        n = len(self.elements)
        nt = len(self.circuit.time_profile)

        if n > 0:
            profile_property = self.elements[0].properties_with_profile[self.magnitude]
            formatter = self.elements[0].editable_headers[self.magnitude].tpe

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

                    if parsed:
                        if c2 < n and r2 < nt:
                            mod_cols.append((c2))
                            getattr(self.elements[c2], profile_property)[r2] = val2
                        else:
                            print('Out of profile bounds')

            if len(mod_cols) > 0:
                self.add_state(mod_cols, 'paste')
        else:
            # there are no elements
            pass

    def copy_to_clipboard(self):
        """
        Copy profiles to clipboard
        """
        n = len(self.elements)

        if n > 0:
            profile_property = self.elements[0].properties_with_profile[self.magnitude]

            # gather values
            names = [None] * n
            values = [None] * n
            for c in range(n):
                names[c] = self.elements[c].name
                values[c] = getattr(self.elements[c], profile_property)
            values = np.array(values).transpose().astype(str)

            # header first
            data = '\t' + '\t'.join(names) + '\n'

            # data
            for t, date in enumerate(self.circuit.time_profile):
                data += str(date) + '\t' + '\t'.join(values[t, :]) + '\n'

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText(data)

        else:
            # there are no elements
            pass

    def add_state(self, columns, action_name=''):
        """
        Compile data of an action and store the data in the undo history
        :param columns: list of column indices changed
        :param action_name: name of the action
        :return: None
        """
        data = dict()

        for col in columns:
            profile_property = self.elements[col].properties_with_profile[self.magnitude]
            data[col] = getattr(self.elements[col], profile_property).copy()

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


class DiagramsModel(QtCore.QAbstractListModel):
    """
    Model for the diagrams
    # from GridCal.Gui.BusViewer.bus_viewer_dialogue import BusViewerGUI
    # from GridCal.Gui.GridEditorWidget import GridEditorWidget
    # from GridCal.Gui.MapWidget.grid_map_widget import GridMapWidget
    """
    def __init__(self, list_of_diagrams: List[Union["GridEditorWidget", "GridMapWidget", "BusViewerGUI"]]):
        """
        Enumeration model
        :param list_of_diagrams: list of enumeration values to show
        """
        QtCore.QAbstractListModel.__init__(self)
        self.items = list_of_diagrams

        self.bus_branch_editor_icon = QtGui.QIcon()
        self.bus_branch_editor_icon.addPixmap(QtGui.QPixmap(":/Icons/icons/schematic.svg"))

        self.bus_branch_vecinity_icon = QtGui.QIcon()
        self.bus_branch_vecinity_icon.addPixmap(QtGui.QPixmap(":/Icons/icons/grid_icon.svg"))

        self.map_editor_icon = QtGui.QIcon()
        self.map_editor_icon.addPixmap(QtGui.QPixmap(":/Icons/icons/map.svg"))

    def flags(self, index):
        """
        Get the display mode
        :param index:
        :return:
        """
        return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def rowCount(self, parent=QtCore.QModelIndex()):
        """

        :param parent:
        :return:
        """
        return len(self.items)

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():

            diagram = self.items[index.row()]

            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                return diagram.name
            elif role == QtCore.Qt.ItemDataRole.DecorationRole:

                if isinstance(diagram, GridCal.Gui.GridEditorWidget.BusBranchEditorWidget):
                    return self.bus_branch_editor_icon
                elif isinstance(diagram, GridCal.Gui.MapWidget.grid_map_widget.GridMapWidget):
                    return self.map_editor_icon
                elif isinstance(diagram, GridCal.Gui.BusViewer.bus_viewer_dialogue.BusViewerWidget):
                    return self.bus_branch_vecinity_icon

        return None

    def setData(self, index, value, role=None):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """

        self.items[index.row()].name = value

        return True


def get_list_model(lst: List[Union[str, DeviceType]], checks=False, check_value=False) -> QtGui.QStandardItemModel:
    """
    Pass a list to a list model
    """
    list_model = QtGui.QStandardItemModel()
    if lst is not None:
        if not checks:
            for val in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setEditable(False)
                list_model.appendRow(item)
        else:
            for val in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setEditable(False)
                item.setCheckable(True)
                if check_value:
                    item.setCheckState(QtCore.Qt.CheckState.Checked)
                list_model.appendRow(item)

    return list_model


class CustomFileSystemModel(QtWidgets.QFileSystemModel):
    def __init__(self, root_path: str, ext_filter: List[str] = ['*.py']):
        super(CustomFileSystemModel, self).__init__()

        self.setNameFilters(ext_filter)
        self.setRootPath(root_path)


def get_logger_tree_model(logger: DataLogger):
    """
    Fill logger tree
    :param logger: Logger instance
    :return: QStandardItemModel instance
    """
    d = logger.to_dict()
    editable = False
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(['Time', 'Element', 'Class', 'Property', 'Value', 'Expected value', 'comment'])
    parent = model.invisibleRootItem()

    for severity, messages_dict in d.items():
        severity_child = QtGui.QStandardItem(severity)

        # print(severity)

        for message, data_list in messages_dict.items():
            message_child = QtGui.QStandardItem(message)

            # print('\t', message)

            for time, elm, elm_class, elm_property, value, expected_value, comment in data_list:

                # print('\t', '\t', time, elm, value, expected_value)

                time_child = QtGui.QStandardItem(time)
                time_child.setEditable(editable)

                elm_child = QtGui.QStandardItem(elm)
                elm_child.setEditable(editable)

                elm_class_child = QtGui.QStandardItem(elm_class)
                elm_class_child.setEditable(editable)

                elm_property_child = QtGui.QStandardItem(elm_property)
                elm_property_child.setEditable(editable)

                value_child = QtGui.QStandardItem(value)
                value_child.setEditable(editable)

                expected_val_child = QtGui.QStandardItem(expected_value)
                expected_val_child.setEditable(editable)

                comment_val_child = QtGui.QStandardItem(comment)
                comment_val_child.setEditable(editable)

                message_child.appendRow([time_child, elm_child, elm_class_child,
                                         elm_property_child, value_child, expected_val_child, comment_val_child])

            message_child.setEditable(editable)

            severity_child.appendRow(message_child)

        severity_child.setEditable(editable)
        parent.appendRow(severity_child)

    return model


def get_icon_list_model(lst: List[Tuple[str, QtGui.QIcon]], checks=False, check_value=False) -> QtGui.QStandardItemModel:
    """

    :param lst:
    :param checks:
    :param check_value:
    :return:
    """
    list_model = QtGui.QStandardItemModel()
    if lst is not None:
        if not checks:
            for val, icon in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setEditable(False)
                item.setIcon(icon)
                list_model.appendRow(item)
        else:
            for val, icon in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setIcon(icon)
                item.setEditable(False)
                item.setCheckable(True)
                if check_value:
                    item.setCheckState(QtCore.Qt.CheckState.Checked)
                list_model.appendRow(item)

    return list_model


def get_checked_indices(mdl: QtGui.QStandardItemModel()) -> IntVec:
    """
    Get a list of the selected indices in a QStandardItemModel
    :param mdl:
    :return:
    """
    idx = list()
    for row in range(mdl.rowCount()):
        item = mdl.item(row)
        if item.checkState() == QtCore.Qt.CheckState.Checked:
            idx.append(row)

    return np.array(idx)


def fill_model_from_dict(parent: QtGui.QStandardItem,
                         d: Dict[str, Union[Dict[str, Any], List[str]]],
                         editable=False,
                         icons: Dict[str, str] = None):
    """
    Fill TreeViewModel from dictionary
    :param parent: Parent QStandardItem
    :param d: item
    :param editable
    :param icons
    :return: Nothing
    """
    if isinstance(d, dict):
        for k, v in d.items():
            name = str(k)
            child = QtGui.QStandardItem(name)
            child.setEditable(editable)

            if icons is not None:
                if name in icons.keys():
                    icon_path = icons[name]
                    _icon = QtGui.QIcon()
                    _icon.addPixmap(QtGui.QPixmap(icon_path))
                    child.setIcon(_icon)

            parent.appendRow(child)
            fill_model_from_dict(parent=child, d=v, icons=icons)
    elif isinstance(d, list):
        for v in d:
            fill_model_from_dict(parent=parent, d=v, icons=icons)
    else:
        name = str(d)
        item = QtGui.QStandardItem(name)
        if icons is not None:
            if name in icons.keys():
                icon_path = icons[name]
                _icon = QtGui.QIcon()
                _icon.addPixmap(QtGui.QPixmap(icon_path))
                item.setIcon(_icon)
        item.setEditable(editable)
        parent.appendRow(item)


def get_tree_model(d, top='', icons: Dict[str, str] = None):
    """

    :param d:
    :param top:
    :param icons:
    :return:
    """
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels([top])
    fill_model_from_dict(model.invisibleRootItem(), d=d, editable=False, icons=icons)

    return model


def get_tree_item_path(item: QtGui.QStandardItem):
    """

    :param item:
    :return:
    """
    item_parent = item.parent()
    path = [item.text()]
    while item_parent is not None:
        parent_text = item_parent.text()
        path.append(parent_text)
        item_parent = item_parent.parent()
    path.reverse()
    return path


def fast_data_to_numpy_text(data: np.ndarray):
    """
    Convert numpy to text
    :param data: numpy array
    :return:
    """
    if len(data.shape) == 1:
        txt = '[' + ', '.join(['{0:.6f}'.format(x) for x in data]) + ']'

    elif len(data.shape) == 2:

        if data.shape[1] > 1:
            # header first
            txt = '['

            # data
            for t in range(data.shape[0]):
                txt += '[' + ', '.join(['{0:.6f}'.format(x) for x in data[t, :]]) + '],\n'

            txt += ']'
        else:
            txt = '[' + ', '.join(['{0:.6f}'.format(x) for x in data[:, 0]]) + ']'
    else:
        txt = '[]'

    return txt


def add_cim_object_node(class_tag, device: IdentifiedObject, editable=False, already_visited=list()):
    """

    :param class_tag:
    :param device:
    :param editable:
    :param already_visited:
    :return:
    """
    if class_tag is None:
        if hasattr(device, 'name'):
            if device.name is not None:
                if device.name != '':
                    class_tag = device.name
                else:
                    class_tag = device.rdfid
            else:
                class_tag = device.rdfid
        else:
            class_tag = device.rdfid

    # create root node
    device_child = QtGui.QStandardItem(class_tag)

    # register visit to avoid cyclic recursion
    already_visited.append(device)

    for property_name, cim_prop in device.declared_properties.items():

        property_value = getattr(device, property_name)

        if hasattr(property_value, 'rdfid'):

            we_are_in_a_recursive_loop = False
            if len(already_visited) > 7:
                for e in already_visited:
                    if property_value.rdfid == e.rdfid:
                        we_are_in_a_recursive_loop = True

            if not we_are_in_a_recursive_loop:

                # if the property is an object, recursively add it
                tpe = str(property_value.tpe)
                class_name_child = add_cim_object_node(tpe,
                                                       property_value,
                                                       editable=editable,
                                                       already_visited=already_visited)
                class_name_child.setEditable(editable)

                property_name_child = QtGui.QStandardItem(tpe)
                property_name_child.setEditable(editable)

                value_child = QtGui.QStandardItem(property_value.rdfid)
                value_child.setEditable(editable)
            else:
                # print('Recursive loop...')
                # return device_child
                class_name_child = QtGui.QStandardItem("Recursive object (" + str(len(already_visited)) + ")")
                class_name_child.setEditable(editable)

                property_name_child = QtGui.QStandardItem(property_name)
                property_name_child.setEditable(editable)

                value_child = QtGui.QStandardItem(str(property_value))
                value_child.setEditable(editable)
        else:
            # if the property is a value (float, str, bool, etc.) just add it

            tpe = str(type(property_value)).replace('class', '')\
                .replace("'", "")\
                .replace("<", "")\
                .replace(">", "").strip()

            class_name_child = QtGui.QStandardItem(tpe)
            class_name_child.setEditable(editable)

            property_name_child = QtGui.QStandardItem(property_name)
            property_name_child.setEditable(editable)

            value_child = QtGui.QStandardItem(str(property_value))
            value_child.setEditable(editable)

        device_child.appendRow([class_name_child, property_name_child, value_child])

    return device_child


def get_cim_tree_model(cim_model: CgmesCircuit):
    """
    Fill logger tree
    :param cim_model: Logger instance
    :return: QStandardItemModel instance
    """

    editable = False
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(['Object class', 'Property', 'Value'])
    root_node = model.invisibleRootItem()

    for class_name, device_list in cim_model.elements_by_type.items():

        class_child = QtGui.QStandardItem(class_name + " (" + str(len(device_list)) + ")")

        for device in device_list:

            # add device with all it's properties
            device_child = add_cim_object_node(class_tag=None, device=device, editable=editable, already_visited=list())

            device_child.setEditable(editable)

            class_child.appendRow(device_child)

        class_child.setEditable(editable)
        root_node.appendRow(class_child)

    return model
