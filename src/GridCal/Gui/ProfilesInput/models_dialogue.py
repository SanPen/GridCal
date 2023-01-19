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

import os
import numpy as np
import pandas as pd
from PySide2.QtWidgets import *
from typing import List, Dict
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Gui.GuiFunctions import PandasModel, get_list_model
from GridCal.Gui.ProfilesInput.profiles_from_models_gui import *
from GridCal.Gui.ProfilesInput.excel_dialog import *


class GridsModelItem:

    def __init__(self, path, time=""):
        """

        :param path:
        """
        self.time = time

        self.path: str = path

        self.name = os.path.basename(path)

    def get_at(self, idx):

        # 'Time', 'Name', 'Folder'
        if idx == 0:
            return self.time
        if idx == 1:
            return self.name
        elif idx == 2:
            return self.path
        else:
            return ''


class GridsModel(QAbstractTableModel):

    def __init__(self):
        QAbstractTableModel.__init__(self)

        self._values_: List[GridsModelItem] = list()

        self._headers_ = ['Time', 'Name', 'Path']

    def append(self, val: GridsModelItem):
        self._values_.append(val)

    def set_path_at(self, i, path):
        if i < len(self._values_):
            self._values_[i].path = path
            self._values_[i].name = os.path.basename(path)

    def items(self):
        return self._values_

    def remove(self, idx: int):
        self._values_.pop(idx)

    def rowCount(self, parent=None):
        return len(self._values_)

    def columnCount(self, parent=None):
        return len(self._headers_)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self._values_[index.row()].get_at(index.column()))
        return None

    def headerData(self, p_int, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._headers_[p_int]
            elif orientation == QtCore.Qt.Vertical:
                return p_int
        return None


def assign_grid(t, loaded_grid: MultiCircuit, main_grid: MultiCircuit):
    pass


class ModelsInputGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, use_native_dialogues=True, time_array=[]):
        """

        :param parent:
        :param use_native_dialogues: use the native file selection dialogues?
        :param time_array: time array
        """

        """

        Args:
            parent:
            use_native_dialogues: 
        """
        QtWidgets.QDialog.__init__(self, parent)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Models import dialogue')

        self.use_native_dialogues = use_native_dialogues

        self.grids_model: GridsModel = GridsModel()

        for t in time_array:
            self.grids_model.append(GridsModelItem("", str(t)))

        self.ui.modelsTableView.setModel(None)
        self.ui.modelsTableView.setModel(self.grids_model)
        self.ui.modelsTableView.repaint()

        # click
        self.ui.addModelsButton.clicked.connect(self.add_models)

    def add_models(self):
        # declare the allowed file types
        files_types = "Formats (*.raw *.RAW *.rawx *.xml *.m *.epc *.EPC)"
        # call dialog to select the file
        # filename, type_selected = QFileDialog.getOpenFileNameAndFilter(self, 'Save file', '', files_types)

        # call dialog to select the file

        options = QFileDialog.Options()
        if self.use_native_dialogues:
            options |= QFileDialog.DontUseNativeDialog

        filenames, type_selected = QFileDialog.getOpenFileNames(self, 'Add files',
                                                                filter=files_types,
                                                                options=options)

        if len(filenames):
            for i, file_path in enumerate(filenames):
                self.grids_model.set_path_at(i, file_path)

            self.ui.modelsTableView.setModel(None)
            self.ui.modelsTableView.setModel(self.grids_model)
            self.ui.modelsTableView.repaint()

    def process(self, main_grid: MultiCircuit):
        """
        Process the imported data
        :param main_grid: Grid to apply the values to, it has to have declared profiles already
        :return: None
        """
        for t, entry in enumerate(self.grids_model.items()):

            if os.path.exists(entry.path):
                loaded_grid = FileOpen(entry.path).open()
                assign_grid(t=t, loaded_grid=loaded_grid, main_grid=main_grid)




if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = ModelsInputGUI()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

