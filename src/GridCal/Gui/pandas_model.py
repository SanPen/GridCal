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
from typing import Union, Any
from PySide6 import QtCore, QtWidgets
from GridCalEngine.enumerations import ResultTypes


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


class PandasModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """

    def __init__(self,
                 data: pd.DataFrame,
                 parent: QtWidgets.QTableView = None,
                 editable=False,
                 editable_min_idx=-1,
                 decimals=6):
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

    def flags(self, index: QtCore.QModelIndex):
        """

        :param index:
        :return:
        """
        if self.editable and index.column() > self.editable_min_idx:
            return (QtCore.Qt.ItemFlag.ItemIsEditable |
                    QtCore.Qt.ItemFlag.ItemIsEnabled |
                    QtCore.Qt.ItemFlag.ItemIsSelectable)
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def rowCount(self, parent: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex] = ...) -> int:
        """

        :param parent:
        :return:
        """
        return self.r

    def columnCount(self, parent: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex] = ...) -> int:
        """

        :param parent:
        :return:
        """
        return self.c

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
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
            if isinstance(self.cols_c, pd.Index):
                names = self.cols_c.values

                if len(names) > 0:
                    if isinstance(names[0], ResultTypes):
                        names = [val.name for val in names]

            # elif isinstance(self.cols_c, ResultTypes):
            #     names = [val.value for val in self.cols_c]

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
        :param mode: numpy or other -> separated by tabs
        :return:
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
