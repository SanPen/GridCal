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
    Class to populate a Qt table view with a pandas data frame
    """
    def __init__(self, objects, attributes, parent=None, editable=False, non_editable_indices=list()):
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.attributes = attributes

        self.objects = objects

        self.editable = editable

        self.non_editable_indices = non_editable_indices

        self.r = len(self.objects)

        self.c = len(self.attributes)

        self.formatter = lambda x: "%.2f" % x

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
                attr = self.attributes[index.column()]
                if 'bus' in attr:
                    return str(getattr(self.objects[index.row()], attr).name)
                else:
                    return str(getattr(self.objects[index.row()], attr))
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
            setattr(self.objects[index.row()], self.attributes[index.column()], value)
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
            if orientation == QtCore.Qt.Horizontal:
                return self.attributes[p_int]
            elif orientation == QtCore.Qt.Vertical:
                return str(p_int)

        return None

    # def copy_to_column(self, row, col):
    #     """
    #     Copies one value to all the column
    #     @param row: Row of the value
    #     @param col: Column of the value
    #     @return: Nothing
    #     """
    #     self.data[:, col] = self.data[row, col]


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
    A delegate that places a fully functioning QComboBox in every
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
    A delegate that places a fully functioning QComboBox in every
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
        editor = QDoubleSpinBox(parent)
        editor.setMaximum(9999)
        editor.setMinimum(-9999)
        editor.editingFinished.connect(self.returnPressed)
        return editor

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        val = float(index.model().data(index))
        editor.setValue(val)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value())


def get_list_model(lst, checks=False):
    """
    Pass a list to a list model
    """
    list_model = QStandardItemModel()
    if lst is not None:
        if not checks:
            for val in lst:
                # for the list model
                item = QStandardItem(val)
                item.setEditable(False)
                list_model.appendRow(item)
        else:
            for val in lst:
                # for the list model
                item = QStandardItem(val)
                item.setEditable(False)
                item.setCheckable(True)
                item.setCheckState(QtCore.Qt.Checked)
                list_model.appendRow(item)

    return list_model
