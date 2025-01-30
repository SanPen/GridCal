# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from typing import List
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QTableView, QVBoxLayout, QPushButton, QHBoxLayout, QDialog, QSpacerItem, QSizePolicy
from GridCal.Gui.general_dialogues import ArrayTableModel
from GridCalEngine.Devices.Injections.controllable_shunt import ControllableShunt


class ControllableShuntArray(ArrayTableModel):

    def __init__(self, data: List[np.ndarray], headers: List[str], dtypes: List[np.dtype]):
        ArrayTableModel.__init__(self, data=data, headers=headers)
        self.dtypes = dtypes

    def setData(self, index: QModelIndex, value: float, role=Qt.ItemDataRole.EditRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        if not index.isValid():
            return False

        if role == Qt.ItemDataRole.EditRole:
            row = index.row()
            column = index.column()
            try:
                value = float(value)
            except ValueError:
                return False

            tpe = self.dtypes[column]
            self._data[column][row] = tpe(value)

            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
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
        self.model = ControllableShuntArray(data=[self.api_object.active_steps,
                                                  self.api_object.g_steps,
                                                  self.api_object.b_steps],
                                            headers=["Active", "G steps (MW)", "B steps (MVAr)"],
                                            dtypes=[bool, float, float])

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

    def get_active_steps(self) -> np.ndarray:
        """

        :return:
        """
        return self.model.get_data()[0]


    def get_g_steps(self) -> np.ndarray:
        """

        :return:
        """
        return self.model.get_data()[1]

    def get_b_steps(self) -> np.ndarray:
        """

        :return:
        """
        return self.model.get_data()[2]



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
