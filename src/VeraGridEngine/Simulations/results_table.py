# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union, List
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from VeraGridEngine.enumerations import ResultTypes, DeviceType
from VeraGridEngine.basic_structures import StrVec, Mat, Vec
from VeraGridEngine.Devices.types import ALL_DEV_TYPES


class ResultsTable:
    """
    Class to populate a Qt table view with data from the results
    """

    def __init__(self,
                 data: Union[Mat, Vec],
                 columns: StrVec,
                 index: StrVec,
                 title: str,
                 cols_device_type: DeviceType,
                 idx_device_type: DeviceType,
                 units: str = "",
                 xlabel: str = "",
                 ylabel: str = "",
                 editable=False,
                 palette=None,
                 editable_min_idx: int = -1,
                 decimals: int = 6):
        """
        ResultsTable constructor
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
        if data.ndim == 1:
            # assert compatible dimensions
            assert len(data) == len(index)

            self.data_c = data.reshape(-1, 1)

        elif data.ndim == 2:
            # assert compatible dimensions
            assert data.shape[0] == len(index)
            assert data.shape[1] == len(columns)

            self.data_c = data
        else:
            raise Exception("Unsupported number of dimensions {}".format(data.ndim))

        self.cols_c = columns
        self.index_c = index

        self.editable = editable
        self.editable_min_idx = editable_min_idx
        self.palette = palette
        self.title = title
        self.x_label = xlabel
        self.y_label = ylabel
        self.units = units
        self.r, self.c = self.data_c.shape
        self.isDate = False
        if self.r > 0 and self.c > 0:
            if isinstance(self.index_c[0], np.datetime64):
                self.index_c = pd.to_datetime(self.index_c)
                self.isDate = True

        self.decimals: int = decimals
        self.format_string = '.' + str(decimals) + 'f'
        self.formatter = lambda x: self.format_string % x

        self.cols_device_type: DeviceType = cols_device_type
        self.idx_device_type: DeviceType = idx_device_type

        # list of devices that match the columns or rows for filtering
        self._col_devices = list()
        self._idx_devices = list()

    @property
    def col_devices(self):
        """

        :return:
        """
        return self._col_devices

    @property
    def idx_devices(self):
        """

        :return:
        """
        return self._idx_devices

    def set_col_devices(self, devices_list: List[ALL_DEV_TYPES]):
        """
        Set the list of devices that matches the results for filtering
        :param devices_list:
        """
        self._col_devices = devices_list

    def set_idx_devices(self, devices_list: List[ALL_DEV_TYPES]):
        """
        Set the list of devices that matches the results for filtering
        :param devices_list:
        """
        self._idx_devices = devices_list

    def transpose(self):
        """
        Transpose the results in-place
        """
        self.data_c = self.data_c.transpose()
        self.r, self.c = self.data_c.shape
        self.x_label, self.y_label = self.y_label, self.x_label
        self.cols_c, self.index_c = self.index_c, self.cols_c
        self._col_devices, self._idx_devices = self._idx_devices, self._col_devices

    def sort_column(self, c: int, max_to_min: bool = True):
        """

        :param c:
        :param max_to_min:
        :return:
        """
        try:
            sorting_arr = self.data_c[:, c].astype(float)
        except ValueError:
            print("Not a float column...")
            sorting_arr = self.data_c[:, c]

        if max_to_min:
            idx = sorting_arr.argsort()[::-1]
        else:
            idx = sorting_arr.argsort()

        self.data_c = self.data_c[idx]
        self.index_c = self.index_c[idx]

    def slice_cols(self, col_idx) -> "ResultsTable":
        """
        Make column slicing
        :param col_idx: indices of the columns
        :return: Nothing
        """
        sliced_model = ResultsTable(data=self.data_c[:, col_idx],
                                    columns=np.array([self.cols_c[i] for i in col_idx]),
                                    index=np.array(self.index_c),
                                    palette=None,
                                    title=self.title,
                                    xlabel=self.x_label,
                                    ylabel=self.y_label,
                                    units=self.units,
                                    editable=self.editable,
                                    editable_min_idx=self.editable_min_idx,
                                    decimals=self.decimals,
                                    cols_device_type=self.cols_device_type,
                                    idx_device_type=self.idx_device_type)

        return sliced_model

    def slice_rows(self, idx) -> "ResultsTable":
        """
        Make rows slicing
        :param idx: indices of the columns
        :return: Nothing
        """
        sliced_model = ResultsTable(data=self.data_c[idx, :],
                                    columns=self.cols_c,
                                    index=np.array([self.index_c[i] for i in idx]),
                                    palette=None,
                                    title=self.title,
                                    xlabel=self.x_label,
                                    ylabel=self.y_label,
                                    units=self.units,
                                    editable=self.editable,
                                    editable_min_idx=self.editable_min_idx,
                                    decimals=self.decimals,
                                    cols_device_type=self.cols_device_type,
                                    idx_device_type=self.idx_device_type)

        return sliced_model

    def slice_all(self, row_idx, col_idx) -> "ResultsTable":
        """
        Make rows slicing
        :param row_idx: indices of the rows
        :param col_idx: indices of the columns
        :return: ResultsTable
        """
        sliced_model = ResultsTable(data=self.data_c[row_idx, :][:, col_idx],
                                    columns=np.array([self.cols_c[i] for i in col_idx]),
                                    index=np.array([self.index_c[i] for i in row_idx]),
                                    palette=None,
                                    title=self.title,
                                    xlabel=self.x_label,
                                    ylabel=self.y_label,
                                    units=self.units,
                                    editable=self.editable,
                                    editable_min_idx=self.editable_min_idx,
                                    decimals=self.decimals,
                                    cols_device_type=self.cols_device_type,
                                    idx_device_type=self.idx_device_type)
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
            if txt2 in str(val).lower():
                idx.append(i)
        idx = np.array(idx, dtype=int)
        if len(idx) > 0:
            return self.slice_rows(idx)
        else:
            return None

    def copy_to_column(self, row: int, col: int):
        """
        Copies one value to all the column
        @param row: Row of the value
        @param col: Column of the value
        @return: Nothing
        """
        self.data_c[:, col] = self.data_c[row, col]

    def is_complex(self) -> bool:
        """
        Is the data complex?
        :return:
        """
        return self.data_c.dtype == complex

    def get_data(self):
        """
        Returns: index, columns, data
        """
        n = len(self.cols_c)

        if n > 0:
            # gather values
            if isinstance(self.cols_c, pd.Index):
                names = self.cols_c.values

                if len(names) > 0:
                    if isinstance(names[0], ResultTypes):
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

        self.x_label = 'Probability of value<=x'

    def convert_to_abs(self):
        """
        Convert the data to abs
        :return:
        """
        try:
            self.data_c = np.abs(self.data_c)
        except TypeError:
            print('Could not convert to abs :/')

    def to_df(self) -> pd.DataFrame:
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

    def plot(self, ax=None, selected_col_idx=None, selected_rows=None, stacked=False):
        """
        Plot the data model
        :param ax: Matplotlib axis
        :param selected_col_idx: list of selected column indices
        :param selected_rows: list of rows to plot
        :param stacked: Stack plot?
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

        if stacked and len(columns) > 1:
            # --- 1. Filter Out Columns That Are Entirely Zero ---
            df_filtered = df.loc[:, (df != 0).any()]
            data = df_filtered.values  # Convert the filtered DataFrame to a NumPy array
            n_series = data.shape[1]

            # --- 2. Prepare the Positive and Negative Parts ---
            # For positive plotting: keep positive values and set non-positive ones to 0.
            data_pos = np.where(data > 0, data, 0)
            # For negative plotting: keep negative values and set non-negative ones to 0.
            data_neg = np.where(data < 0, data, 0)

            # --- 3. Compute Cumulative Sums Along the Series Axis ---
            cum_pos = np.cumsum(data_pos, axis=1)
            cum_neg = np.cumsum(data_neg, axis=1)

            # --- 4. Plot Using Matplotlib's fill_between ---
            # Use a colormap to generate distinct colors for each series.
            colors = plt.cm.viridis(np.linspace(0, 1, n_series))

            # x-axis will use the DataFrame's DatetimeIndex.
            x = df_filtered.index

            # Plot the positive areas for each series.
            for i in range(n_series):
                if i == 0:
                    if cum_pos[:, i].sum() != 0:
                        ax.fill_between(x, 0, cum_pos[:, i], color=colors[i],
                            label=f'{df_filtered.columns[i]}')
                else:
                    if cum_pos[:, i].sum() != 0:
                        ax.fill_between(x, cum_pos[:, i - 1], cum_pos[:, i], color=colors[i],
                            label=f'{df_filtered.columns[i]}')

            # Plot the negative areas for each series.
            for i in range(n_series):
                if i == 0:
                    if cum_neg[:, i].sum() != 0:
                        ax.fill_between(x, 0, cum_neg[:, i], color=colors[i], alpha=0.6,
                            label=f'{df_filtered.columns[i]}')
                else:
                    if cum_neg[:, i].sum() != 0:
                        ax.fill_between(x, cum_neg[:, i - 1], cum_neg[:, i], color=colors[i], alpha=0.6,
                            label=f'{df_filtered.columns[i]}')

            # Add legend and labels for clarity
            ax.set_title(self.title, fontsize=14)
            ax.set_ylabel(self.y_label, fontsize=11)
            ax.set_xlabel(self.x_label, fontsize=11)
            ax.legend(loc='upper right', fontsize='small')
        else:
            ax.set_title(self.title, fontsize=14)
            ax.set_ylabel(self.y_label, fontsize=11)
            ax.set_xlabel(self.x_label, fontsize=11)
            try:
                df.plot(ax=ax, legend=plot_legend)
            except TypeError:
                print('No numeric data to plot...')

    def plot_device(self, ax=None, device_idx: int = 0, stacked=False, title: str = ""):
        """
        Plot the data model
        :param ax: Matplotlib axis
        :param device_idx: list of selected column indices
        :param stacked: Stack plot?
        :param title: Title of the plot
        """
        index, columns, data = self.get_data()

        # columns = [columns[device_idx]]
        columns = [self.title] if title == "" else [title]
        data = data[:, device_idx]

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
        ax.set_ylabel(self.y_label, fontsize=11)
        ax.set_xlabel(self.x_label, fontsize=11)
        try:
            df.plot(ax=ax, legend=plot_legend, stacked=stacked)
        except TypeError:
            print('No numeric data to plot...')
