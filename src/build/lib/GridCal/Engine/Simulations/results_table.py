# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

from matplotlib import pyplot as plt
from GridCal.Engine.Simulations.result_types import ResultTypes


class ResultsTable:
    """
    Class to populate a Qt table view with data from the results
    """
    def __init__(self, data: np.ndarray, columns, index, palette=None, title='', xlabel='', ylabel='', units='',
                 editable=False, editable_min_idx=-1, decimals=6):
        """

        :param data:
        :param columns:
        :param index:
        :param palette:
        :param title:
        :param xlabel:
        :param ylabel:
        :param editable:
        :param editable_min_idx:
        :param decimals:
        """
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

    def slice_cols(self, col_idx):
        """
        Make column slicing
        :param col_idx: indices of the columns
        :return: Nothing
        """
        sliced_model = ResultsTable(data=self.data_c[:, col_idx],
                                    columns=[self.cols_c[i] for i in col_idx],
                                    index=self.index_c,
                                    palette=None,
                                    title=self.title,
                                    xlabel=self.xlabel,
                                    ylabel=self.ylabel,
                                    units=self.units,
                                    editable=self.editable,
                                    editable_min_idx=self.editable_min_idx,
                                    decimals=6)

        sliced_model.format_string = self.format_string
        return sliced_model

    def slice_rows(self, idx):
        """
        Make rows slicing
        :param idx: indices of the columns
        :return: Nothing
        """
        sliced_model = ResultsTable(data=self.data_c[idx, :],
                                    columns=self.cols_c,
                                    index=[self.index_c[i] for i in idx],
                                    palette=None,
                                    title=self.title,
                                    xlabel=self.xlabel,
                                    ylabel=self.ylabel,
                                    units=self.units,
                                    editable=self.editable,
                                    editable_min_idx=self.editable_min_idx,
                                    decimals=6)

        sliced_model.format_string = self.format_string
        return sliced_model

    def slice_all(self, row_idx, col_idx):
        """
        Make rows slicing
        :param row_idx: indices of the rows
        :param col_idx: indices of the columns
        :return: Nothing
        """
        sliced_model = ResultsTable(data=self.data_c[row_idx, :][:, col_idx],
                                    columns=[self.cols_c[i] for i in col_idx],
                                    index=[self.index_c[i] for i in row_idx],
                                    palette=None,
                                    title=self.title,
                                    xlabel=self.xlabel,
                                    ylabel=self.ylabel,
                                    units=self.units,
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
            if txt2 in val.lower():
                idx.append(i)
        idx = np.array(idx, dtype=int)
        if len(idx) > 0:
            return self.slice_cols(idx)
        else:
            return None

    def search_in_rows(self, txt):
        """
        Search stuff
        :param txt:
        :return:
        """
        idx = list()
        txt2 = str(txt).lower()
        for i, val in enumerate(self.index_c):
            if txt2 in val.lower():
                idx.append(i)
        idx = np.array(idx, dtype=int)
        if len(idx) > 0:
            return self.slice_rows(idx)
        else:
            return None

    def search(self, txt: str):
        """
        Search stuff
        :param txt:
        :return:
        """
        txt = txt.strip()
        cols = np.array(self.cols_c).astype(str)
        index = np.array(self.index_c).astype(str)

        if txt.startswith('<'):

            txt = txt.replace(' ', '')
            try:
                val = float(txt[1:])
                row_idx, col_idx = np.where(self.data_c < val)

                if len(self.cols_c) == 1:
                    return self.slice_rows(row_idx)
                else:
                    row_idx = np.unique(row_idx)
                    col_idx = np.unique(col_idx)
                    return self.slice_all(row_idx, col_idx)

            except ValueError:
                return None

        elif txt.startswith('>'):

            txt = txt.replace(' ', '')
            try:
                val = float(txt[1:])
                row_idx, col_idx = np.where(self.data_c > val)

                if len(self.cols_c) == 1:
                    return self.slice_rows(row_idx)
                else:
                    row_idx = np.unique(row_idx)
                    col_idx = np.unique(col_idx)
                    return self.slice_all(row_idx, col_idx)

            except ValueError:
                return None

        elif txt.startswith('!='):

            txt = txt.replace(' ', '')
            try:
                val = float(txt[2:])
                row_idx, col_idx = np.where(self.data_c != val)

                if len(self.cols_c) == 1:
                    return self.slice_rows(row_idx)
                else:
                    row_idx = np.unique(row_idx)
                    col_idx = np.unique(col_idx)
                    return self.slice_all(row_idx, col_idx)

            except ValueError:
                return None
        else:
            # search by similar text
            row_idx = list()
            txt2 = str(txt).lower()
            for i, val in enumerate(index):
                if txt2 in val.lower():
                    row_idx.append(i)
            row_idx = np.array(row_idx, dtype=int)

            col_idx = list()
            txt2 = str(txt).lower()
            for i, val in enumerate(cols):
                if txt2 in val.lower():
                    col_idx.append(i)
            col_idx = np.array(col_idx, dtype=int)

            if len(col_idx) > 0:

                if len(row_idx) == 0:
                    # if some col was found but no row, pick all
                    row_idx = np.arange(len(self.index_c))

            else:
                if len(row_idx) > 0:
                    # if some row was found, but no column, pick all
                    col_idx = np.arange(len(self.cols_c))

            return self.slice_all(row_idx, col_idx)

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
        try:
            self.data_c = np.abs(self.data_c)
        except TypeError:
            print('Could not convert to abs :/')

    def to_df(self):
        """
        get DataFrame
        """
        index, columns, data = self.get_data()

        return pd.DataFrame(data=data, index=index, columns=columns)

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
        index, columns, data = self.get_data()
        return pd.DataFrame(data=data, index=index, columns=columns)

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
        try:
            df.plot(ax=ax, legend=plot_legend)
        except TypeError:
            print('No numeric data to plot...')


