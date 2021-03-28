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
from PySide2.QtWidgets import *
from PySide2 import QtCore
from matplotlib import pyplot as plt
from GridCal.Engine.Simulations.result_types import ResultTypes


class ResultsModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with data from the results
    """
    def __init__(self, data: np.ndarray, columns, index, palette=None, title='', xlabel='', ylabel='', units='',
                 parent=None, editable=False, editable_min_idx=-1, decimals=6):
        """

        :param data:
        :param columns:
        :param index:
        :param palette:
        :param title:
        :param xlabel:
        :param ylabel:
        :param parent:
        :param editable:
        :param editable_min_idx:
        :param decimals:
        """
        QtCore.QAbstractTableModel.__init__(self, parent)

        if len(data.shape) == 1:
            self.data_c = data.reshape(-1, 1)
        else:
            self.data_c = data
        self.cols_c = columns
        self.index_c = index

        self.editable = editable
        self.editable_min_idx = editable_min_idx
        self.palette = palette
        self.title = title
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.units = units
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
            return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

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

            val = self.data_c[index.row(), index.column()]

            if role == QtCore.Qt.DisplayRole:

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

            elif role == QtCore.Qt.BackgroundRole:

                return None  # QBrush(Qt.yellow)

        return None

    def headerData(self, p_int, orientation, role):
        """

        :param p_int:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                if len(self.cols_c) > p_int:
                    return self.cols_c[p_int]

            elif orientation == QtCore.Qt.Vertical:
                if self.index_c is None:
                    return p_int
                else:
                    if self.isDate:
                        return self.index_c[p_int].strftime('%Y/%m/%d  %H:%M.%S')
                    else:
                        return str(self.index_c[p_int])
        return None

    def slice_cols(self, col_idx):
        """
        Make column slicing
        :param col_idx: indices of the columns
        :return: Nothing
        """
        sliced_model = ResultsModel(data=self.data_c[:, col_idx],
                                    columns=self.cols_c[col_idx],
                                    index=self.index_c,
                                    palette=None,
                                    title=self.title,
                                    xlabel=self.xlabel,
                                    ylabel=self.ylabel,
                                    units=self.units,
                                    parent=None,
                                    editable=self.editable,
                                    editable_min_idx=self.editable_min_idx,
                                    decimals=6)

        sliced_model.format_string = self.format_string
        return sliced_model

    def search_in_columns(self, txt):
        """
        Search stuff
        :param txt:
        :return:
        """
        idx = list()
        txt2 = str(txt).lower()
        for i, val in enumerate(self.cols_c):

            if txt2 in val:
                idx.append(i)

        if len(idx) > 0:
            return self.slice_cols(idx)
        else:
            return None

    def copy_to_column(self, row, col):
        """
        Copies one value to all the column
        @param row: Row of the value
        @param col: Column of the value
        @return: Nothing
        """
        self.data_c[:, col] = self.data_c[row, col]

    def is_complex(self):
        return self.data_c.dtype == complex

    def get_data(self):
        """
        Returns: index, columns, data
        """
        n = len(self.cols_c)

        if n > 0:
            # gather values
            if type(self.cols_c) == pd.Index:
                names = self.cols_c.values

                if len(names) > 0:
                    if type(names[0]) == ResultTypes:
                        names = [str(val) for val in names]
            else:
                names = [str(val) for val in self.cols_c]

            values = self.data_c

            return self.index_c, names, values
        else:
            # there are no elements
            return self.index_c, list(), self.data_c

    def convert_to_cdf(self):
        """
        Convert the data in-place to CDF based
        :return:
        """

        # calculate the proportional values of samples
        n = self.data_c.shape[0]
        if n > 1:
            self.index_c = np.arange(n, dtype=float) / (n - 1)
        else:
            self.index_c = np.arange(n, dtype=float)

        for i in range(self.data_c.shape[1]):
            self.data_c[:, i] = np.sort(self.data_c[:, i], axis=0)

        self.xlabel = 'Probability of value<=x'

    def convert_to_abs(self):
        """
        Convert the data to abs
        :return:
        """
        self.data_c = np.abs(self.data_c)

    def save_to_excel(self, file_name):
        """
        save data to excel
        :param file_name:
        """
        index, columns, data = self.get_data()

        pd.DataFrame(data=data, index=index, columns=columns).to_excel(file_name)

    def save_to_csv(self, file_name):
        """
        Save data to csv
        :param file_name:
        """
        index, columns, data = self.get_data()
        pd.DataFrame(data=data, index=index, columns=columns).to_csv(file_name)

    def get_data_frame(self):
        """
        Save data to csv
        """
        index, columns, data = self.get_data()
        return pd.DataFrame(data=data, index=index, columns=columns)

    def copy_to_clipboard(self):
        """
        Copy profiles to clipboard
        """
        n = len(self.cols_c)

        if n > 0:

            index, columns, data = self.get_data()

            txt = fast_data_to_text(data, columns, index)

            # copy to clipboard
            cb = QApplication.clipboard()
            cb.clear(mode=cb.Clipboard)
            cb.setText(txt, mode=cb.Clipboard)

        else:
            # there are no elements
            pass

    def copy_numpy_to_clipboard(self):
        """
        Copy profiles to clipboard
        """
        n = len(self.cols_c)

        if n > 0:

            index, columns, data = self.get_data()

            txt = fast_data_to_numpy_text(data)

            # copy to clipboard
            cb = QApplication.clipboard()
            cb.clear(mode=cb.Clipboard)
            cb.setText(txt, mode=cb.Clipboard)

        else:
            # there are no elements
            pass

    def plot(self, ax=None, selected_col_idx=None, selected_rows=None):
        """
        Plot the data model
        :param ax: Matplotlib axis
        :param selected_col_idx: list of selected column indices
        :param selected_rows: list of rows to plot
        """

        index, columns, data = self.get_data()

        if selected_col_idx is not None:
            columns = [columns[i] for i in selected_col_idx]
            data = data[:, selected_col_idx]

        if selected_rows is not None:
            index = [index[i] for i in selected_rows]
            data = data[selected_rows, :]

        if ax is None:
            fig = plt.figure(figsize=(12, 6))
            ax = fig.add_subplot(111)

        if 'voltage' in self.title.lower():
            data[data == 0] = 'nan'  # to avoid plotting the zeros

        if len(columns) > 15:
            plot_legend = False
        else:
            plot_legend = True

        df = pd.DataFrame(data=data, index=index, columns=columns)
        ax.set_title(self.title, fontsize=14)
        ax.set_ylabel(self.ylabel, fontsize=11)
        ax.set_xlabel(self.xlabel, fontsize=11)
        df.plot(ax=ax, legend=plot_legend)


# @nb.njit()
def fast_data_to_text(data, columns, index):
    # header first
    txt = '\t' + '\t'.join(columns) + '\n'

    # data
    for t, index_value in enumerate(index):
        if data[t, :].sum() != 0.0:
            txt += str(index_value) + '\t' + '\t'.join([str(x) for x in data[t, :]]) + '\n'

    return txt


# @nb.njit()
def fast_data_to_numpy_text(data):

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