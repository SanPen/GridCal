# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import re
import numpy as np
import pandas as pd
from PySide6 import QtWidgets, QtCore
from typing import List
from datetime import datetime, timedelta

from GridCal.Gui.messages import yes_no_question
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Utils.progress_bar import print_progress_bar
from GridCal.Gui.ProfilesInput.profiles_from_models_gui import Ui_Dialog


def extract_and_convert_to_datetime(filename, logger: Logger) -> pd.DatetimeIndex | None:
    """
    Try to extract date from file name
    :param filename: file name
    :param logger: Logger
    :return: pd.DateTimeIndex or None
    """
    date_patterns = [
        (r'\b(\d{4}[^\d]\d{2}[^\d]\d{2})\b', '%Y-%m-%d'),  # YYYY-MM-DD
        (r'\b(\d{4}[^\d]\d{2}[^\d]\d{2})\b', '%Y_%m_%d'),  # YYYY_MM_DD
        (r'\b(\d{8})\b', '%Y%m%d'),  # YYYYMMDD
        (r'\b(\d{12})\b', '%Y%m%d%H%M'),  # YYYYMMDDHHMM
        (r'\b(\d{8}_\d{4})\b', '%Y%m%d_%H%M'),  # YYYYMMDD_HHMM
        (r'\b(\d{4}[^\d]\d{2}[^\d]\d{2}_\d{4})\b', '%Y-%m-%d_%H%M'),  # YYYY-MM-DD_HHMM
        (r'\b(\d{4}[^\d]\d{2}[^\d]\d{2}_\d{4})\b', '%Y_%m_%d_%H%M')  # YYYY_MM_DD_HHMM
    ]

    date_str = filename
    for date_pattern, frmt in date_patterns:
        match = re.search(date_pattern, filename)
        if match:
            date_str = match.group(1)

            # Try to parse the date string
            try:
                date_object = pd.to_datetime(date_str, format=frmt, errors='raise')

                return date_object
            except ValueError:
                # print(f"Unable to parse date from: {date_str}")
                pass

    logger.add_error(msg="Unable to parse date from", value=date_str)

    return None  # Return None if no valid date is found


class GridsModelItem:
    """
    GridsModelItem
    """

    def __init__(self, path, tme, logger: Logger):
        """

        :param path:
        """
        suggested_tme = extract_and_convert_to_datetime(filename=os.path.basename(path), logger=logger)
        self.time = suggested_tme if suggested_tme is not None else tme

        self.path: str = path

        self.name = os.path.basename(path)

    def get_at(self, idx: int) -> str | pd.Timestamp:
        """

        :param idx:
        :return:
        """
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
    """
    GridsModel
    """

    def __init__(self) -> None:
        """

        """
        QtCore.QAbstractTableModel.__init__(self)

        self._values_: List[GridsModelItem] = list()

        self._headers_ = ['Time', 'Name', 'Path']

    def update(self):
        """
        update table
        """
        self.layoutAboutToBeChanged.emit()
        self.layoutChanged.emit()

    def clear(self) -> None:
        """

        :return:
        """
        self._values_.clear()
        self.update()

    def append(self, val: GridsModelItem):
        """

        :param val:
        :return:
        """
        self._values_.append(val)
        self.update()

    def set_path_at(self, i: int, path: str):
        """

        :param i:
        :param path:
        :return:
        """
        if i < len(self._values_):
            self._values_[i].path = path
            self._values_[i].name = os.path.basename(path)
        self.update()

    def items(self) -> List[GridsModelItem]:
        """

        :return:
        """
        return self._values_

    def remove(self, idx: int):
        """

        :param idx:
        :return:
        """
        self._values_.pop(idx)
        self.update()

    def rowCount(self, parent: QtCore.QModelIndex = None) -> int:
        """

        :param parent:
        :return:
        """
        return len(self._values_)

    def columnCount(self, parent: QtCore.QModelIndex = None) -> int:
        """

        :param parent:
        :return:
        """
        return len(self._headers_)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> None | str:
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                # return self.formatter(self._data[index.row(), index.column()])
                return str(self._values_[index.row()].get_at(index.column()))
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
                return self._headers_[section]
            elif orientation == QtCore.Qt.Orientation.Vertical:
                return section
        return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """

        :param index:
        :return:
        """
        return (QtCore.Qt.ItemFlag.ItemIsDropEnabled |
                QtCore.Qt.ItemFlag.ItemIsEnabled |
                QtCore.Qt.ItemFlag.ItemIsEditable |
                QtCore.Qt.ItemFlag.ItemIsSelectable |
                QtCore.Qt.ItemFlag.ItemIsDragEnabled)

    def supportedDropActions(self):
        """

        :return:
        """
        return QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction

    def dropMimeData(self, data: QtCore.QMimeData,
                     action: QtCore.Qt.DropAction,
                     row: int, column: int,
                     parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex) -> bool:
        """

        :param data:
        :param action:
        :param row:
        :param column:
        :param parent:
        :return:
        """
        pass


def assign_grid(t, grid_to_add: MultiCircuit, main_grid: MultiCircuit, use_secondary_key, logger: Logger):
    """
    Assign all the values of the loaded grid to the profiles of the main grid at the time step t
    :param t: time step index
    :param grid_to_add: grid to add to the main cirucuit
    :param main_grid: main grid
    :param use_secondary_key: Use the secondary key ("code") to match
    :param logger: Logger
    """
    # for each device type that we see in the tree ...
    for dev_template in main_grid.template_items():

        # get the device type
        device_type = dev_template.device_type

        # get dictionary of devices
        main_elms_dict = main_grid.get_elements_dict_by_type(device_type, use_secondary_key=use_secondary_key)

        # get list of devices
        elms_from_the_grid_to_add = grid_to_add.get_elements_by_type(device_type)

        # for each device
        for elm_to_add in elms_from_the_grid_to_add:

            # try to find the element in the main grid: fast way to avoid double lookup
            main_elm = main_elms_dict.get(elm_to_add.code if use_secondary_key else elm_to_add.idtag, None)

            if main_elm is not None:

                # for every property with profile, set the profile value with the element value
                for prop, profile_prop in main_elm.properties_with_profile.items():
                    # copy the element profile properties to the main element at the time index t
                    getattr(main_elm, profile_prop)[t] = getattr(elm_to_add, prop)

            else:
                logger.add_warning("Element not found in the main grid, added on the fly",
                                   value=elm_to_add.name)
                main_grid.add_element(elm_to_add)


class ModelsInputGUI(QtWidgets.QDialog):
    """
    ModelsInputGUI
    """

    def __init__(self, parent=None) -> None:
        """

        :param parent:
        """

        QtWidgets.QDialog.__init__(self, parent)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Models import dialogue')

        self.grids_model: GridsModel = GridsModel()

        self.logger = Logger()

        self.ui.matchUsingCodeCheckBox.setChecked(True)

        self.ui.modelsTableView.setModel(None)
        self.ui.modelsTableView.setModel(self.grids_model)
        self.ui.modelsTableView.repaint()

        # click
        self.ui.addModelsButton.clicked.connect(self.add_models)
        self.ui.acceptModelsButton.clicked.connect(self.accept)
        self.ui.deleteModelsButton.clicked.connect(self.clear_model)

    def accept(self) -> None:
        """

        :return:
        """
        super().accept()
        self.close()

    def clear_model(self) -> None:
        """
        Delete the import data
        :return:
        """
        if self.grids_model.rowCount() > 0:
            ok = yes_no_question("Do you want to clear the import data?")
            if ok:
                self.grids_model.clear()

    def add_models(self) -> None:
        """
        Add the selected models
        """
        # declare the allowed file types
        files_types = "Formats (*.raw *.RAW *.rawx *.xml *.m *.epc *.EPC)"

        # call dialog to select the file
        filenames, type_selected = QtWidgets.QFileDialog.getOpenFileNames(self, 'Add files', filter=files_types)

        if len(filenames):

            b = self.grids_model.rowCount()
            d = datetime.today()
            base_date = datetime(d.year, 1, 1, 00, 00, 00)
            base_inc = 1  # 1 hour

            for i, file_path in enumerate(filenames):
                tme = base_date + timedelta(hours=base_inc * (i + b))
                self.grids_model.append(GridsModelItem(file_path, tme=tme, logger=self.logger))

            self.ui.modelsTableView.setModel(None)
            self.ui.modelsTableView.setModel(self.grids_model)
            self.ui.modelsTableView.repaint()

    def generate_time_array(self, main_grid: MultiCircuit, logger: Logger):
        """
        Generate time profile from model
        :param main_grid:
        :param logger:
        :return:
        """
        n = len(self.grids_model.items())

        t_profile = np.zeros(n, dtype=object)

        d = datetime.today()
        base_date = datetime(d.year, 1, 1, 00, 00, 00)
        base_inc = 1  # 1 hour

        for t, entry in enumerate(self.grids_model.items()):
            if entry.time is not None:
                if isinstance(entry.time, pd.DatetimeIndex):
                    t_profile[t] = entry.time
                else:
                    try:
                        t_profile[t] = pd.to_datetime(entry.time)
                    except ValueError:
                        t_profile[t] = base_date + timedelta(hours=base_inc * t)
                        logger.add_info(msg="Could not convert time",
                                        device="time array",
                                        device_property="",
                                        value=str(entry.time))

        # set the circuit time profile
        main_grid.time_profile = pd.to_datetime(t_profile)
        main_grid.ensure_profiles_exist()

    def process(self, main_grid: MultiCircuit, logger: Logger):
        """
        Process the imported data
        :param main_grid: Grid to apply the values to, it has to have declared profiles already
        :param logger: Logger
        :return: None
        """
        use_secondary_key = self.ui.matchUsingCodeCheckBox.isChecked()

        n = len(self.grids_model.items())

        self.generate_time_array(main_grid=main_grid, logger=logger)

        for t, entry in enumerate(self.grids_model.items()):
            name = os.path.basename(entry.path)
            print_progress_bar(iteration=t+1, total=n, txt=name)

            if os.path.exists(entry.path):
                loaded_grid = FileOpen(entry.path).open()
                assign_grid(t=t,
                            grid_to_add=loaded_grid,
                            main_grid=main_grid,
                            use_secondary_key=use_secondary_key,
                            logger=logger)

                logger.add_info(msg="Loaded grid",
                                device=name,
                                device_property="Path",
                                value=entry.path)

        print()  # to finalize the progressbar

        # check devices' status: if an element is connected to disconnected
        # buses the branch must be disconnected too. This is to handle the
        # typical PSSe garbage modelling practices
        for elm in main_grid.get_branches_iter(add_vsc=True, add_hvdc=True):
            if not (elm.bus_from.active and elm.bus_to.active):
                elm.active = False
                logger.add_warning(msg="Inconsistent active state",
                                   device=elm.name,
                                   device_property="Snapshot")

            for t in range(main_grid.get_time_number()):
                if not (elm.bus_from.active_prof[t] and elm.bus_to.active_prof[t]):
                    elm.active_prof[t] = False
                    logger.add_warning(msg="Inconsistent active state",
                                       device=elm.name,
                                       device_property=str(t))

        for elm in main_grid.get_injection_devices_iter():
            if not elm.bus.active:
                elm.active = False
                logger.add_warning(msg="Inconsistent active state",
                                   device=elm.name,
                                   device_property="Snapshot")

            for t in range(main_grid.get_time_number()):
                if not elm.bus.active_prof[t]:
                    elm.active_prof[t] = False
                    logger.add_warning(msg="Inconsistent active state",
                                       device=elm.name,
                                       device_property=str(t))

# if __name__ == "__main__":
#     import sys
#     app = QtWidgets.QApplication(sys.argv)
#     window = ModelsInputGUI()
#     window.resize(1.61 * 700.0, 600.0)  # golden ratio
#     window.show()
#     sys.exit(app.exec())
