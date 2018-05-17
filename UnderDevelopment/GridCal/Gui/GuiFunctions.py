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
import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5 import QtCore
from PyQt5.QtGui import *


class ComboDelegate(QItemDelegate):
    commitData = QtCore.pyqtSignal(object)
    """
    A delegate that places a fully functioning QComboBox in every
    cell of the column to which it's applied
    """
    def __init__(self, parent, objects, object_names):
        """
        Constructoe
        :param parent: QTableView parent object
        :param objects: List of objects to set. i.e. [True, False]
        :param object_names: List of Object names to display. i.e. ['True', 'False']
        """
        QItemDelegate.__init__(self, parent)

        # objects to sent to the model associated to the combobox. i.e. [True, False]
        self.objects = objects

        # object description to display in the combobox. i.e. ['True', 'False']
        self.object_names = object_names

    @QtCore.pyqtSlot()
    def currentIndexChanged(self):
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self.object_names)
        combo.currentIndexChanged.connect(self.currentIndexChanged)
        return combo

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        val = index.model().data(index)
        idx = self.object_names.index(val)
        editor.setCurrentIndex(idx)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, self.object_names[editor.currentIndex()])


class TextDelegate(QItemDelegate):
    commitData = QtCore.pyqtSignal(object)
    """
    A delegate that places a fully functioning QLineEdit in every
    cell of the column to which it's applied
    """
    def __init__(self, parent):
        """
        Constructoe
        :param parent: QTableView parent object
        """
        QItemDelegate.__init__(self, parent)

    @QtCore.pyqtSlot()
    def returnPressed(self):
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.returnPressed.connect(self.returnPressed)
        return editor

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        val = index.model().data(index)
        editor.setText(val)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text())


class FloatDelegate(QItemDelegate):
    commitData = QtCore.pyqtSignal(object)
    """
    A delegate that places a fully functioning QDoubleSpinBox in every
    cell of the column to which it's applied
    """
    def __init__(self, parent, min_=-9999, max_=9999):
        """
        Constructoe
        :param parent: QTableView parent object
        """
        QItemDelegate.__init__(self, parent)
        self.min = min_
        self.max = max_

    @QtCore.pyqtSlot()
    def returnPressed(self):
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        editor = QDoubleSpinBox(parent)
        editor.setMaximum(self.max)
        editor.setMinimum(self.min)
        editor.setDecimals(8)
        editor.editingFinished.connect(self.returnPressed)
        return editor

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        val = float(index.model().data(index))
        editor.setValue(val)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value())


class ComplexDelegate(QItemDelegate):
    commitData = QtCore.pyqtSignal(object)
    """
    A delegate that places a fully functioning Complex Editor in every
    cell of the column to which it's applied
    """
    def __init__(self, parent):
        """
        Constructoe
        :param parent: QTableView parent object
        """
        QItemDelegate.__init__(self, parent)

    @QtCore.pyqtSlot()
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
        editor = QFrame(parent)
        main_layout = QHBoxLayout(editor)
        main_layout.layout().setContentsMargins(0, 0, 0, 0)

        real = QDoubleSpinBox()
        real.setMaximum(9999)
        real.setMinimum(-9999)
        real.setDecimals(8)

        imag = QDoubleSpinBox()
        imag.setMaximum(9999)
        imag.setMinimum(-9999)
        imag.setDecimals(8)

        # button = QPushButton()

        main_layout.addWidget(real)
        main_layout.addWidget(imag)
        # main_layout.addWidget(button)

        # button.clicked.connect(self.returnPressed)

        return editor

    def setEditorData(self, editor, index):
        """

        :param editor:
        :param index:
        :return:
        """
        editor.blockSignals(True)
        val = complex(index.model().data(index))
        editor.children()[1].setValue(val.real)
        editor.children()[2].setValue(val.imag)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        """

        :param editor:
        :param model:
        :param index:
        :return:
        """
        val = complex(editor.children()[1].value(), editor.children()[2].value())
        model.setData(index, val)


class PandasModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """
    def __init__(self, data, parent=None, editable=False, editable_min_idx=-1):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.data = np.array(data.values)
        self._cols = data.columns
        self.index = data.index.values
        self.editable = editable
        self.editable_min_idx = editable_min_idx
        self.r, self.c = np.shape(self.data)
        self.isDate = False
        if self.r > 0 and self.c > 0:
            if isinstance(self.index[0], np.datetime64):
                self.index = pd.to_datetime(self.index)
                self.isDate = True

        self.formatter = lambda x: "%.2f" % x

    def flags(self, index):
        if self.editable and index.column() > self.editable_min_idx:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

    def rowCount(self, parent=None):
        return self.r

    def columnCount(self, parent=None):
        return self.c

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self.data[index.row(), index.column()])
        return None

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
        self.data[index.row(), index.column()] = value
        # print("setData", index.row(), index.column(), value)

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._cols[p_int]
            elif orientation == QtCore.Qt.Vertical:
                if self.index is None:
                    return p_int
                else:
                    if self.isDate:
                        return self.index[p_int].strftime('%Y/%m/%d  %H:%M.%S')
                    else:
                        return str(self.index[p_int])
        return None

    def copy_to_column(self, row, col):
        """
        Copies one value to all the column
        @param row: Row of the value
        @param col: Column of the value
        @return: Nothing
        """
        self.data[:, col] = self.data[row, col]


class ObjectsModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with the properties of objects
    """
    def __init__(self, objects, attributes, attr_units, attr_types, parent=None, editable=False, non_editable_indices=list(),
                 transposed=False):
        """

        :param objects: list of objects associated to the editor
        :param attributes: Attribute list of the object
        :param attr_types: Types of the attributes. This is used to assign the appropriate editor (float, str, complex, bool)
        :param parent: Parent object: the QTableView object
        :param editable: Is the table editable?
        :param non_editable_indices: List of attributes that are not enabled for editing
        :param transposed: Display the table transposed?
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.parent = parent

        self.attributes = attributes

        self.attribute_types = attr_types

        self.units = attr_units

        self.objects = objects

        self.editable = editable

        self.non_editable_indices = non_editable_indices

        self.r = len(self.objects)

        self.c = len(self.attributes)

        self.formatter = lambda x: "%.2f" % x

        self.transposed = transposed

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
            tpe = self.attribute_types[self.attributes[i]]
            if tpe is bool:
                delegate = ComboDelegate(self.parent, [True, False], ['True', 'False'])
                F(i, delegate)

            elif tpe is float:
                delegate = FloatDelegate(self.parent)
                F(i, delegate)

            elif tpe is str:
                delegate = TextDelegate(self.parent)
                F(i, delegate)

            elif tpe is complex:
                delegate = ComplexDelegate(self.parent)
                F(i, delegate)
            elif tpe is None:
                F(i, None)
                if len(self.non_editable_indices) == 0:
                    self.non_editable_indices.append(i)
            else:
                pass

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

        if self.editable and attr_idx not in self.non_editable_indices:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

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

    def data_with_type(self, index):
        """
        Get the data to display
        :param index:
        :param role:
        :return:
        """

        if self.transposed:
            obj_idx = index.column()
            attr_idx = index.row()
        else:
            obj_idx = index.row()
            attr_idx = index.column()

        attr = self.attributes[attr_idx]
        if 'bus' in attr:
            return getattr(self.objects[obj_idx], attr).name
        else:
            return getattr(self.objects[obj_idx], attr)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """
        Get the data to display
        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                return str(self.data_with_type(index))
        return None

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
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

        if attr_idx not in self.non_editable_indices:
            setattr(self.objects[obj_idx], self.attributes[attr_idx], value)
        else:
            pass  # the column cannot be edited

    def headerData(self, p_int, orientation, role):
        """
        Get the headers to display
        :param p_int:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.DisplayRole:

            if self.transposed:
                if orientation == QtCore.Qt.Horizontal:
                    return 'Value'
                elif orientation == QtCore.Qt.Vertical:
                    if self.units[p_int] != '':
                        return self.attributes[p_int] + ' [' + self.units[p_int] + ']'
                    else:
                        return self.attributes[p_int]
            else:
                if orientation == QtCore.Qt.Horizontal:
                    if self.units[p_int] != '':
                        return self.attributes[p_int] + ' [' + self.units[p_int] + ']'
                    else:
                        return self.attributes[p_int]
                elif orientation == QtCore.Qt.Vertical:
                    return str(p_int)

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

            if attr_idx not in self.non_editable_indices:
                setattr(self.objects[obj_idx], self.attributes[attr_idx], value)
            else:
                pass  # the column cannot be edited


class ProfilesModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with profiles from objects
    """
    def __init__(self, multi_circuit, device, magnitude, format, parent):
        """

        Args:
            multi_circuit: MultiCircuit instance
            device: string with Load, StaticGenerator, etc...
            magnitude: magnitude to display 'S', 'P', etc...
            parent: Parent object: the QTableView object
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.parent = parent

        self.format = format

        self.circuit = multi_circuit

        self.device = device

        self.magnitude = magnitude

        self.non_editable_indices = list()

        self.editable = True

        self.r = len(self.circuit.time_profile)

        self.elements, self.buses = self.circuit.get_node_elements_by_type(device)

        self.c = len(self.elements)

        self.formatter = lambda x: "%.2f" % x

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

    def flags(self, index):
        """
        Get the display mode
        :param index:
        :return:
        """

        if self.editable and index.column() not in self.non_editable_indices:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

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

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """
        Get the data to display
        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:

                df = getattr(self.elements[index.column()], self.magnitude + 'prof')
                return str(df.values[index.row(), 0])

        return None

    def setData(self, index, value, role=QtCore.Qt.DisplayRole):
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """

        if index.column() not in self.non_editable_indices:
            getattr(self.elements[index.column()], self.magnitude + 'prof').values[index.row(), 0] = value
        else:
            pass  # the column cannot be edited

    def headerData(self, p_int, orientation, role):
        """
        Get the headers to display
        :param p_int:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.DisplayRole:

            if role == QtCore.Qt.DisplayRole:
                if orientation == QtCore.Qt.Horizontal:
                    return str(self.elements[p_int].name)
                elif orientation == QtCore.Qt.Vertical:
                    if self.circuit.time_profile is None:
                        return str(p_int)
                    else:
                        return str(self.circuit.time_profile[p_int])

        return None

    # def copy_to_column(self, row, col):
    #     """
    #     Copies one value to all the column
    #     @param row: Row of the value
    #     @param col: Column of the value
    #     @return: Nothing
    #     """
    #     self.data[:, col] = self.data[row, col]


def get_list_model(lst, checks=False):
    """
    Pass a list to a list model
    """
    list_model = QStandardItemModel()
    if lst is not None:
        if not checks:
            for val in lst:
                # for the list model
                item = QStandardItem(str(val))
                item.setEditable(False)
                list_model.appendRow(item)
        else:
            for val in lst:
                # for the list model
                item = QStandardItem(str(val))
                item.setEditable(False)
                item.setCheckable(True)
                item.setCheckState(QtCore.Qt.Checked)
                list_model.appendRow(item)

    return list_model


def get_checked_indices(mdl: QStandardItemModel()):
    """
    Get a list of the selected indices in a QStandardItemModel
    :param mdl:
    :return:
    """
    idx = list()
    for row in range(mdl.rowCount()):
        item = mdl.item(row)
        if item.checkState() == QtCore.Qt.Checked:
            idx.append(row)

    return np.array(idx)
