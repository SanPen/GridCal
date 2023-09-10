# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from PySide6 import QtWidgets, QtCore
from typing import List
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.file_handler import FileOpen
from GridCal.Gui.ProfilesInput.profiles_from_models_gui import Ui_Dialog


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


class GridsModel(QtCore.QAbstractTableModel):

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)

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
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self._values_[index.row()].get_at(index.column()))
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
                return self._headers_[p_int]
            elif orientation == QtCore.Qt.Vertical:
                return p_int
        return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        """

        :param index:
        :return:
        """
        return QtCore.Qt.ItemIsDropEnabled | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsDragEnabled

    def supportedDropActions(self) -> bool:
        """

        :return:
        """
        return QtCore.Qt.MoveAction | QtCore.Qt.CopyAction

    def dropEvent(self, event):
        """

        :param event:
        """
        if (event.source() is not self or
                (event.dropAction() != QtCore.Qt.MoveAction and
                 self.dragDropMode() != QtWidgets.QAbstractItemView.InternalMove)):
            super().dropEvent(event)
        selection = self.selectedIndexes()
        from_index = selection[0].row() if selection else -1

        globalPos = self.viewport().mapToGlobal(event.pos())
        header = self.verticalHeader()
        to_index = header.logicalIndexAt(header.mapFromGlobal(globalPos).y())
        if to_index < 0:
            to_index = header.logicalIndex(self.model().rowCount() - 1)

        if from_index != to_index:
            from_index = header.visualIndex(from_index)
            to_index = header.visualIndex(to_index)
            header.moveSection(from_index, to_index)
            event.accept()
            event.setDropAction(QtCore.Qt.IgnoreAction)
        super().dropEvent(event)


def assign_grid(t, loaded_grid: MultiCircuit, main_grid: MultiCircuit, use_secondary_key):
    """
    Assign all the values of the loaded grid to the profiles of the main grid at the time step t
    :param t: time step index
    :param loaded_grid: loaded grid
    :param main_grid: main grid
    :param use_secondary_key: Use the secondary key ("code") to match
    """
    # for each list of devices with profiles...
    for dev_template in main_grid.get_objects_with_profiles_list():

        # get the device type
        device_type = dev_template.device_type

        # get dictionary of devices
        main_elms_dict = main_grid.get_elements_dict_by_type(device_type, use_secondary_key=use_secondary_key)

        # get list of devices
        loaded_elms = loaded_grid.get_elements_by_type(device_type)

        # for each device
        for loaded_elm in loaded_elms:

            # fast way to avoid double lookup
            main_elm = main_elms_dict.get(loaded_elm.code if use_secondary_key else loaded_elm.idtag, None)

            if main_elm is not None:

                # for every property with profile, set the profile value with the element value
                for prop, profile_prop in main_elm.properties_with_profile.items():

                    getattr(main_elm, profile_prop)[t] = getattr(loaded_elm, prop)


class ModelsInputGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, time_array=[]):
        """

        :param parent:
        :param time_array: time array
        """

        QtWidgets.QDialog.__init__(self, parent)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Models import dialogue')

        self.ui.deleteModelsButton.setVisible(False)

        self.grids_model: GridsModel = GridsModel()

        for t in time_array:
            self.grids_model.append(GridsModelItem("", str(t)))

        self.ui.matchUsingCodeCheckBox.setChecked(True)

        self.ui.modelsTableView.setModel(None)
        self.ui.modelsTableView.setModel(self.grids_model)
        self.ui.modelsTableView.repaint()

        # click
        self.ui.addModelsButton.clicked.connect(self.add_models)
        self.ui.acceptModelsButton.clicked.connect(self.accept)

    def accept(self):
        self.close()

    def add_models(self):
        # declare the allowed file types
        files_types = "Formats (*.raw *.RAW *.rawx *.xml *.m *.epc *.EPC)"
        # call dialog to select the file
        # filename, type_selected = QFileDialog.getOpenFileNameAndFilter(self, 'Save file', '', files_types)

        # call dialog to select the file
        filenames, type_selected = QtWidgets.QFileDialog.getOpenFileNames(self, 'Add files', filter=files_types)

        if len(filenames):
            for i, file_path in enumerate(filenames):
                self.grids_model.set_path_at(i, file_path)

            self.ui.modelsTableView.setModel(None)
            self.ui.modelsTableView.setModel(self.grids_model)
            self.ui.modelsTableView.repaint()

    def process(self, main_grid: MultiCircuit, write_report=False, report_name="import_report.xlsx"):
        """
        Process the imported data
        :param main_grid: Grid to apply the values to, it has to have declared profiles already
        :param write_report: Write the imports report
        :param report_name: File name or complete path of the Excel report
        :return: None
        """
        use_secondary_key = self.ui.matchUsingCodeCheckBox.isChecked()

        n = len(self.grids_model.items())
        data_m = dict()
        data_a = dict()
        index = [''] * n

        for t, entry in enumerate(self.grids_model.items()):

            index[t] = entry.name

            if os.path.exists(entry.path):
                print(entry.path)
                loaded_grid = FileOpen(entry.path).open()
                assign_grid(t=t,
                            loaded_grid=loaded_grid,
                            main_grid=main_grid,
                            use_secondary_key=use_secondary_key)

                if write_report:
                    for i, bus in enumerate(loaded_grid.buses):
                        arr_m = data_m.get(bus.code, None)
                        arr_a = data_a.get(bus.code, None)
                        if arr_m is None:
                            arr_m = np.zeros(n, dtype=float)
                            data_m[bus.code] = arr_m
                            arr_a = np.zeros(n, dtype=float)
                            data_a[bus.code] = arr_a

                        arr_m[t] = bus.Vm0 * float(bus.active)
                        arr_a[t] = bus.Va0 * float(bus.active)

        if write_report:
            with pd.ExcelWriter(report_name) as w:  # pylint: disable=abstract-class-instantiated
                pd.DataFrame(data=data_m, index=index).to_excel(w, sheet_name="Vm")
                pd.DataFrame(data=data_a, index=index).to_excel(w, sheet_name="Va")


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = ModelsInputGUI()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

