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
import numpy as np
from typing import List
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QTableView, QVBoxLayout, QPushButton, QHBoxLayout, QDialog, QSpacerItem, QSizePolicy
from GridCal.Gui.GeneralDialogues import ArrayTableModel
from GridCal.Gui.messages import error_msg
from GridCalEngine.Devices.Injections.controllable_shunt import ControllableShunt


class ControllableShuntArray(ArrayTableModel):

    def __init__(self, data: List[np.ndarray], headers: List[str]):
        ArrayTableModel.__init__(self, data=data, headers=headers)

    def setData(self, index: QModelIndex, value: float, role=Qt.EditRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        if not index.isValid():
            return False

        if role == Qt.EditRole:
            row = index.row()
            column = index.column()
            try:
                value = float(value)
            except ValueError:
                return False

            if row > 0:
                if value > self._data[column][row - 1]:  # only allow incremental data
                    self._data[column][row] = value
                else:
                    error_msg(text="Only incremental data is allowed", title="Set data")
            else:
                if len(self._data[column]) > 1:
                    if value < self._data[column][1]:
                        self._data[column][row] = value
                    else:
                        error_msg(text="Only incremental data is allowed", title="Set data")
                else:
                    self._data[column][row] = value

            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
            return True

        return False


class ControllableShuntEditor(QDialog):
    """
    ArrayEditor
    """

    def __init__(self, api_object: ControllableShunt):
        QDialog.__init__(self)

        self.setWindowTitle("Controllable shunt editor")

        self.api_object = api_object
        self.model = ControllableShuntArray(data=[self.api_object.g_steps,
                                                  self.api_object.b_steps],
                                            headers=["G steps (MW)", "B steps (MVAr)"])

        self.table_view = QTableView()
        self.table_view.setModel(self.model)

        self.add_button = QPushButton("Add")
        self.delete_button = QPushButton("Delete")
        self.done_button = QPushButton("Done")

        self.add_button.clicked.connect(self.add_row)
        self.delete_button.clicked.connect(self.delete_row)
        self.done_button.clicked.connect(self.accept_click)

        layout = QVBoxLayout()
        layout.addWidget(self.table_view)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Maximum))
        button_layout.addWidget(self.done_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def get_g_steps(self) -> np.ndarray:
        """

        :return:
        """
        return self.model.get_data()[0]

    def get_b_steps(self) -> np.ndarray:
        """

        :return:
        """
        return self.model.get_data()[1]

    def add_row(self):
        """
        Add row
        """
        row_count = self.model.rowCount()
        self.model.insertRows(row_count, 1)

    def delete_row(self):
        """
        Delete the selected rows
        """
        selected_indexes = self.table_view.selectionModel().selectedIndexes()

        rows = list({index.row() for index in selected_indexes})
        rows.sort(reverse=True)
        for r in rows:
            self.model.removeRows(position=r, rows=1)

    def accept_click(self):
        """

        :return:
        """
        self.accept()
