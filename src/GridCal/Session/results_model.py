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
import io
import numpy as np
import pandas as pd
from PySide6 import QtCore, QtWidgets
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Utils.Filtering.results_table_filtering import FilterResultsTable


def fast_data_to_numpy_text(data: np.ndarray) -> str:
    """
    Convert numpy array to text (as to copy/paste in a python console)
    :param data: numpy array
    :return: numpy declarative string
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


class ResultsModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with data from the results
    """
    def __init__(self, table: ResultsTable, parent=None):
        """

        :param table:
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        self.table = table

        self.units = table.units

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """

        :param index:
        :return:
        """
        if self.table.editable and index.column() > self.table.editable_min_idx:
            return QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def rowCount(self, parent: QtCore.QModelIndex = None) -> int:
        """

        :param parent:
        :return:
        """
        return self.table.r

    def columnCount(self, parent: QtCore.QModelIndex = None) -> int:
        """

        :param parent:
        :return:
        """
        return self.table.c

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():

            val = self.table.data_c[index.row(), index.column()]

            if role == QtCore.Qt.ItemDataRole.DisplayRole:

                if isinstance(val, str):
                    return val
                elif isinstance(val, complex):
                    if val.real != 0 or val.imag != 0:
                        return val.__format__(self.table.format_string)
                    else:
                        return '0'
                else:
                    if val != 0:
                        return val.__format__(self.table.format_string)
                    else:
                        return '0'

            elif role == QtCore.Qt.ItemDataRole.BackgroundRole:

                return None  # QBrush(Qt.yellow)

        return None

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role=QtCore.Qt.ItemDataRole.DisplayRole):
        """
        Get the header value
        :param section: header index
        :param orientation: Orientation {QtCore.Qt.Horizontal, QtCore.Qt.Vertical}
        :param role:
        :return:
        """
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                if len(self.table.cols_c) > section:
                    val = self.table.cols_c[section]
                else:
                    return ""

            elif orientation == QtCore.Qt.Orientation.Vertical:
                if self.table.index_c is None:
                    return section
                else:
                    val = self.table.index_c[section]
            else:
                return ""

            if isinstance(val, pd.Timestamp):
                return val.strftime('%Y/%m/%d  %H:%M:%S')
            else:
                return val
        return None

    def slice_cols(self, col_idx) -> "ResultsModel":
        """
        Make column slicing
        :param col_idx: indices of the columns
        :return: Nothing
        """
        return ResultsModel(self.table.slice_cols(col_idx))

    def search_in_columns(self, txt):
        """
        Search stuff
        :param txt:
        :return:
        """
        print('Searching', txt)
        mdl = self.table.search_in_columns(txt)

        if mdl is not None:
            return ResultsModel(mdl)
        else:
            return None

    def transpose(self):
        """
        Transpose the results in-place
        """
        self.table.transpose()

    def search(self, txt: str):
        """
        Search stuff
        :param txt:
        :return:
        """
        filter_ = FilterResultsTable(self.table)
        filter_.parse(expression=txt)
        mdl = filter_.apply()

        if mdl is not None:
            return ResultsModel(mdl)
        else:
            return None

    def copy_to_column(self, row, col):
        """
        Copies one value to all the column
        @param row: Row of the value
        @param col: Column of the value
        @return: Nothing
        """
        self.table.copy_to_column(row, col)

    def is_complex(self):
        return self.table.is_complex()

    def get_data(self):
        """
        Returns: index, columns, data
        """
        return self.table.get_data()

    def convert_to_cdf(self):
        """
        Convert the data in-place to CDF based
        :return:
        """

        # calculate the proportional values of samples
        self.table.convert_to_cdf()

    def convert_to_abs(self):
        """
        Convert the data to abs
        :return:
        """
        self.table.convert_to_abs()

    def to_df(self):
        """
        get DataFrame
        """
        return self.table.to_df()

    def save_to_excel(self, file_name):
        """
        save data to excel
        :param file_name:
        """
        self.to_df().to_excel(file_name)

    def save_to_csv(self, file_name):
        """
        Save data to csv
        :param file_name:
        """
        self.to_df().to_csv(file_name)

    def get_data_frame(self):
        """
        Save data to csv
        """
        return self.table.get_data_frame()

    def copy_to_clipboard(self):
        """
        Copy profiles to clipboard
        """
        n = len(self.table.cols_c)

        if n > 0:

            df = self.get_data_frame()
            s = io.StringIO()
            df.to_csv(s, sep='\t')
            txt = s.getvalue()

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText(txt)

        else:
            # there are no elements
            pass

    def copy_numpy_to_clipboard(self):
        """
        Copy profiles to clipboard
        """
        n = len(self.table.cols_c)

        if n > 0:

            index, columns, data = self.get_data()

            txt = fast_data_to_numpy_text(data)

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText(txt)

        else:
            # there are no elements
            pass

    def plot(self, ax=None, selected_col_idx=None, selected_rows=None, stacked=False):
        """
        Plot the data model
        :param ax: Matplotlib axis
        :param selected_col_idx: list of selected column indices
        :param selected_rows: list of rows to plot
        :param stacked: stack the data?
        """

        self.table.plot(ax=ax,
                        selected_col_idx=selected_col_idx,
                        selected_rows=selected_rows,
                        stacked=stacked)
