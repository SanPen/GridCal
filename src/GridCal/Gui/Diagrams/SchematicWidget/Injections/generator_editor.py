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
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (QDialog, QTableView, QVBoxLayout, QHBoxLayout,
                               QPushButton, QSplitter, QFrame, QSpacerItem, QSizePolicy)
from GridCalEngine.Devices.Injections.generator_q_curve import GeneratorQCurve
from GridCalEngine.basic_structures import Mat, Vec
from GridCal.Gui.Diagrams.SchematicWidget.matplotlibwidget import MatplotlibWidget


class GeneratorQCurveEditorTableModel(QAbstractTableModel):
    """
    GeneratorQCurveEditorTableModel
    """

    def __init__(self, data: Mat, headers, parent=None, callback=None):
        super(GeneratorQCurveEditorTableModel, self).__init__(parent)
        self._data = data
        self._headers = headers
        self.callback = callback

    def rowCount(self, parent=QModelIndex()):
        """

        :param parent:
        :return:
        """
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        """

        :param parent:
        :return:
        """
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return str(self._data[index.row(), index.column()])

    def setData(self, index, value, role=Qt.EditRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        if role == Qt.EditRole:
            try:
                # Attempt to convert the input to a float value
                value = float(value)
            except ValueError:
                return False  # Input is not a valid float

            # Update the data in the model
            self._data[index.row(), index.column()] = value
            self.dataChanged.emit(index, index)
            if self.callback is not None:
                self.callback()

            if index.column() == 0:
                self.sortData()

            return True

    def flags(self, index):
        """

        :param index:
        :return:
        """
        return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable

    def headerData(self,
                   section: int,
                   orientation: Qt.Orientation,
                   role=Qt.ItemDataRole.DisplayRole):
        """

        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return super(GeneratorQCurveEditorTableModel, self).headerData(section, orientation, role)

    def addRow(self, rowData: Vec):
        """

        :param rowData:
        """
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._data = np.vstack([self._data, rowData])
        self.endInsertRows()

    def delRow(self, i):
        """

        :param i:
        """
        if self._data.shape[0] > 0:
            self.beginRemoveRows(QModelIndex(), i, i)
            self._data = np.delete(self._data, i, axis=0)
            self.endRemoveRows()

    def delLastRow(self):
        """

        """
        if self._data.shape[0] > 0:
            i = self._data.shape[0] - 1
            self.beginRemoveRows(QModelIndex(), i, i)
            self._data = np.delete(self._data, i, axis=0)
            self.endRemoveRows()

    def sortData(self):
        """

        """
        # Get the indices that would sort the array along the first column
        sorted_indices = np.argsort(self._data[:, 0])

        # Use the indices to reorder the rows
        self._data = self._data[sorted_indices]

        self.layoutChanged.emit()

    def getData(self):
        """

        :return:
        """
        return self._data


class GeneratorQCurveEditor(QDialog):
    """
    GeneratorQCurveEditor
    """

    def __init__(self, q_curve: GeneratorQCurve, Qmin, Qmax, Pmin, Pmax, Snom):
        """

        :param q_curve:
        :param Qmin:
        :param Qmax:
        :param Pmin:
        :param Pmax:
        :param Snom:
        """

        super(GeneratorQCurveEditor, self).__init__()

        self.setWindowTitle("Reactive power curve editor")

        self.q_curve: GeneratorQCurve = q_curve
        self.Qmin = Qmin
        self.Qmax = Qmax
        self.Pmin = Pmin
        self.Pmax = Pmax
        self.Snom = Snom

        self.headers = ["P", "Qmin", "Qmax"]

        self.table_model = GeneratorQCurveEditorTableModel(data=self.q_curve.get_data(),
                                                           headers=self.headers,
                                                           callback=self.plot)

        self.l_frame = QFrame()
        self.r_frame = QFrame()
        self.buttons_frame = QFrame()
        self.buttons_frame.setMaximumHeight(40)

        self.l_layout = QVBoxLayout(self.l_frame)
        self.r_layout = QVBoxLayout(self.r_frame)
        self.buttons_layout = QHBoxLayout(self.buttons_frame)

        self.l_layout.setContentsMargins(0, 0, 0, 0)
        self.r_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)

        # Enable row selection
        self.table_view = QTableView()
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.setModel(self.table_model)

        self.add_row_button = QPushButton("Add")
        self.add_row_button.clicked.connect(self.addRow)

        self.del_button = QPushButton("Del")
        self.del_button.clicked.connect(self.removeSelectedRow)

        # self.sort_button = QPushButton("Sort")
        # self.sort_button.clicked.connect(self.sort)

        self.buttons_layout.addWidget(self.add_row_button)
        # self.buttons_layout.addWidget(self.sort_button)
        self.buttons_layout.addSpacerItem(QSpacerItem(40, 30, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.buttons_layout.addWidget(self.del_button)

        self.l_layout.addWidget(self.table_view)
        self.l_layout.addWidget(self.buttons_frame)

        self.plotter = MatplotlibWidget()
        self.r_layout.addWidget(self.plotter)

        # Create a splitter to create a vertical split view
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.l_frame)
        splitter.addWidget(self.r_frame)

        central_layout = QVBoxLayout(self)
        central_layout.addWidget(splitter)
        central_layout.setContentsMargins(0, 0, 0, 0)

        self.plot()

    def addRow(self):
        """
        Add a new row of zeros
        :return:
        """
        self.table_model.addRow(np.zeros(3))

    def removeSelectedRow(self):
        """

        :return:
        """
        selected_indexes = self.table_view.selectionModel().selectedRows()

        if selected_indexes:
            # Assuming the selection model is set to single selection mode
            row = selected_indexes[0].row()
            self.table_model.delRow(row)
        else:
            # if no selection, delete the last row
            self.table_model.delLastRow()

    def sort(self):
        self.table_model.sortData()

    def collect_data(self):
        """
        Collect the data from the data model into the curve object
        """
        self.q_curve.set(self.table_model.getData())
        self.Snom = self.q_curve.get_Snom()
        self.Qmax = self.q_curve.get_Qmax()
        self.Qmin = self.q_curve.get_Qmin()
        self.Pmax = self.q_curve.get_Pmax()
        self.Pmin = self.q_curve.get_Pmin()

    def closeEvent(self, event):
        """
        On close, recover the data
        :param event:
        :return:
        """
        self.collect_data()

    def plot(self):
        """
        Plot the chart
        :return:
        """
        self.plotter.clear()

        self.collect_data()

        # plot the limits
        radius = self.q_curve.get_Snom()
        theta = np.linspace(0, 2 * np.pi, 100)
        x = radius * np.cos(theta)
        y = radius * np.sin(theta)
        self.plotter.plot(x, y,
                          color='gray',
                          marker=None,
                          linestyle='dotted',
                          linewidth=1,
                          markersize=4)

        # plot the data
        self.q_curve.plot(ax=self.plotter.canvas.ax)

        self.plotter.redraw()
        self.plotter.canvas.fig.tight_layout()
