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

        # pass the attributes to a index: attribute dictionary
        self.attributes = attributes

        self.objects = objects

        self.editable = editable
        self.non_editable_indices = non_editable_indices
        self.r = len(self.objects)
        self.c = len(self.attributes)
        # self.isDate = False

        # if self.r > 0 and self.c > 0:
        #     if isinstance(self.index[0], np.datetime64):
        #         self.index = pd.to_datetime(self.index)
        #         self.isDate = True

        self.formatter = lambda x: "%.2f" % x

    def flags(self, index):
        """

        :param index:
        :return:
        """
        if self.editable and index.column() not in self.non_editable_indices:
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled

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

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """

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

        :param p_int:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.attributes[p_int]
            elif orientation == QtCore.Qt.Vertical:
                # if hasattr(self.objects[p_int], 'name'):
                #     return getattr(self.objects[p_int], 'name')
                # else:
                #     return str(p_int)
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


def get_list_model(lst, checks=False):
    """
    Pass a list to a list model
    """
    list_model = QStandardItemModel()
    i = 0
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
