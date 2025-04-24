# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import string
from typing import Tuple, List, Optional
from random import randint
from enum import Enum
from difflib import SequenceMatcher
import numpy as np
import pandas as pd
from PySide6 import QtWidgets, QtCore
import matplotlib

matplotlib.use('QtAgg')  # Or 'Qt5Agg' — depending on your matplotlib version

from matplotlib import pyplot as plt

from GridCal.Gui.general_dialogues import LogsDialogue
from GridCal.Gui.gui_functions import get_list_model
from GridCal.Gui.ProfilesInput.profiles_from_data_gui import Ui_Dialog
from GridCal.Gui.ProfilesInput.excel_dialog import ExcelDialog
from GridCal.Gui.messages import error_msg, info_msg
from GridCal.Gui.toast_widget import ToastManager
from GridCalEngine import DeviceType
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.Devices.Parents.editable_device import uuid2idtag, GCProp
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import Mat, BoolVec, Logger


def try_parse_dates(date_series: pd.Series, formats: Optional[List[str]] = None) -> Tuple[pd.Series, str, bool]:
    """
    Tries to parse a pandas Series of strings into datetime using a list of common formats.

    Parameters:
    - date_series (pd.Series): The input series of date strings.
    - formats (List[str], optional): List of datetime formats to try. If None, defaults to common ones.

    Returns:
    - pd.Series: A pandas Series of parsed datetime objects (or original strings if none matched).
    """
    if formats is None:
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%d-%m %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%d-%m %H:%M",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%d.%m.%Y",
            "%Y%m%dT%H%M%S",
            "%Y-%m-%d",
        ]

    for fmt in formats:
        try:
            parsed = pd.to_datetime(date_series, format=fmt, errors='raise')
            print(f"Succeeded with format {fmt}")
            return parsed, f"Succeeded with format {fmt}", True
        except (ValueError, TypeError):
            continue

    # Try letting pandas infer if none of the formats matched
    try:
        parsed = pd.to_datetime(date_series, errors='raise')
        return parsed, f"Succeeded parsing time", True
    except Exception:
        print("Failed to parse dates using all known formats.")
        return date_series, "Failed to parse dates using all known formats.", False  # Return as is if nothing worked


class MultiplierType(Enum):
    """
    MultiplierType
    """
    Mult = 1


class ProfileAssociation:
    """
    ProfileAssociation
    """

    def __init__(self, elm: ALL_DEV_TYPES, scale: float = 1.0, multiplier: float = 1.0, profile_name: str = ''):
        """

        :param elm: GridCal device
        :param scale: Sacling of the profile
        :param multiplier:
        :param profile_name:
        """
        self.elm: ALL_DEV_TYPES = elm
        self.scale: float = scale
        self.multiplier: float = multiplier
        self.profile_name: str = profile_name

    @property
    def name(self):
        """

        :return:
        """
        return self.elm.name

    @property
    def code(self):
        """

        :return:
        """
        return self.elm.code

    @property
    def idtag(self):
        """

        :return:
        """
        return self.elm.idtag

    def get_at(self, idx):
        """

        :param idx:
        :return:
        """
        if idx == 0:
            return self.name
        elif idx == 1:
            return self.code
        elif idx == 2:
            return self.idtag
        elif idx == 3:
            return self.profile_name
        elif idx == 4:
            return self.scale
        elif idx == 5:
            return self.multiplier
        else:
            return ''


class ProfileAssociations(QtCore.QAbstractTableModel):
    """
    ProfileAssociations
    """

    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)

        self.__values: List[ProfileAssociation] = list()

        self.__headers = ['Name', 'Code', 'Idtag', 'Profile', 'Scale', 'Multiplier']

    def update(self):
        """
        update table
        """
        self.layoutAboutToBeChanged.emit()
        self.layoutChanged.emit()

    def append(self, val: ProfileAssociation):
        """

        :param val:
        :return:
        """
        self.__values.append(val)
        self.update()

    def set_profile_at(self, idx: int, profile_name: str) -> None:
        """

        :param idx:
        :param profile_name:
        :return:
        """
        self.__values[idx].profile_name = profile_name
        self.update()

    def set_scale_at(self, idx: int, value: float) -> None:
        """

        :param idx:
        :param value:
        :return:
        """
        self.__values[idx].scale = value
        self.update()

    def set_multiplier_at(self, idx: int, value: float) -> None:
        """

        :param idx:
        :param value:
        :return:
        """
        self.__values[idx].multiplier = value
        self.update()

    def get_profile_at(self, idx: int) -> str:
        """

        :param idx:
        :return:
        """
        return self.__values[idx].profile_name

    def get_scale_at(self, idx: int) -> float:
        """

        :param idx:
        :return:
        """
        return self.__values[idx].scale

    def get_multiplier_at(self, idx: int) -> float:
        """

        :param idx:
        :return:
        """
        return self.__values[idx].multiplier

    def clear_at(self, idx):
        """

        :param idx:
        :return:
        """
        self.__values[idx].profile_name = ''
        self.__values[idx].scale = 1
        self.__values[idx].multiplier = 1
        self.update()

    def rowCount(self, parent: QtCore.QModelIndex = None) -> int:
        """

        :param parent:
        :return:
        """
        return len(self.__values)

    def columnCount(self, parent=None):
        """

        :param parent:
        :return:
        """
        return len(self.__headers)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                return str(self.__values[index.row()].get_at(index.column()))
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
                return self.__headers[section]
            elif orientation == QtCore.Qt.Orientation.Vertical:
                return section
        return None


class StringSubstitutions(Enum):
    """
    StringSubstitutions
    """
    PSSeBranchName = 'N1_NME1_V1_N2_NME2_V2_CKT -> N1_N2_CKT'
    PSSeBusGenerator = 'N1_NME1_V1 -> N1_1'
    PSSeBusLoad = 'N -> N_1'


def check_similarity(name_to_search: str,
                     code_to_search: str,
                     idtag_to_search: str,
                     names_array: List[str],
                     threshold: float) -> int | None:
    """
    Search a value in the array of input names
    :param name_to_search: name of the GridCal object
    :param code_to_search: code (secondary id) of the GridCal object
    :param idtag_to_search: idtag to search
    :param names_array: array of names coming from the profile
    :param threshold: similarity threshold
    :return: index of the profile entry match or None if no match was found
    """
    # exact match of the name or the code or idtag
    for idx, name in enumerate(names_array):
        if name == name_to_search:
            return idx
        elif name == code_to_search:
            return idx
        elif uuid2idtag(name) == idtag_to_search:
            return idx

    # else, find the most likely match with the name if the threshold is appropriate
    if 0.01 <= threshold < 1.0:
        max_val = 0
        max_idx = None
        for idx_s, col_name in enumerate(names_array):
            profile_name = col_name.strip()

            # find the string distance
            d = SequenceMatcher(None, name_to_search, profile_name).ratio()

            if d > max_val:
                max_val = d
                max_idx = idx_s

        # assign the string with the closest profile (60% or better similarity)
        if max_idx is not None and max_val > threshold:
            return max_idx
        else:
            return None
    else:
        return None


class GeneratorsProfileOptionsDialogue(QtWidgets.QDialog):
    """
    Dialogue to show after profile import
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Generator active power options")
        self.setModal(True)  # Make the dialog modal

        # Create checkboxes
        self.correct_active_profile = QtWidgets.QCheckBox("Correct active profile")
        self.correct_active_profile.setToolTip("The generators active will be set to False if the power is zero")

        self.set_non_dispatchable = QtWidgets.QCheckBox("Set to non-dispatchable")
        self.set_non_dispatchable.setToolTip("Teh generators matched will be set set to non dispatchable. "
                                             "This is usefull to specify renewable generation")

        # Create layout and add checkboxes
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.correct_active_profile)
        layout.addWidget(self.set_non_dispatchable)

        # Create OK button to close the dialog
        ok_button = QtWidgets.QPushButton("OK")
        ok_button.clicked.connect(self.accept)  # Close modal on button click
        layout.addWidget(ok_button)

        self.setLayout(layout)


class ProfileInputGUI(QtWidgets.QDialog):
    """
    ProfileInputGUI
    """

    def __init__(self,
                 parent: QtWidgets.QWidget,
                 circuit: MultiCircuit,
                 dev_type: DeviceType,
                 objects: List[ALL_DEV_TYPES],
                 magnitude: str):
        """

        :param parent:
        :param circuit: MultiCircuit object
        :param dev_type: DeviceType of the objects
        :param objects: List of objects to which set a profile to
        :param magnitude: Property of the objects to which set the pandas DataFrame
        """
        QtWidgets.QDialog.__init__(self, parent)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.toast_manager = ToastManager(parent=self, position_top=False)

        self.project_directory: str | None = None

        self.circuit = circuit
        self.magnitude = magnitude
        self.dev_type = dev_type
        self.prop: GCProp = objects[0].get_property_by_name(magnitude)
        self.objects: List[ALL_DEV_TYPES] = objects

        self.setWindowTitle(f'Profiles import for {dev_type.value}.{magnitude} [{self.prop.tpe}]')

        # results
        self.data: Mat | None = None
        self.time: pd.DatetimeIndex | None = None

        self.was_accepted = False

        # units
        self.units = dict()
        self.units['Y'] = 1e24
        self.units['Z'] = 1e21
        self.units['E'] = 1e18
        self.units['P'] = 1e15
        self.units['T'] = 1e12
        self.units['G'] = 1e9
        self.units['M'] = 1e6
        self.units['k'] = 1e3
        self.units['-'] = 1.0
        self.units['m'] = 1e-3
        self.units['µ'] = 1e-6
        self.units['n'] = 1e-9
        self.units['p'] = 1e-12
        self.units['f'] = 1e-15
        self.units['a'] = 1e-18
        self.units['z'] = 1e-21
        self.units['y'] = 1e-24

        relevant_units = ['T', 'G', 'M', 'k', '-', 'm']
        self.ui.units_combobox.addItems(relevant_units)
        self.ui.units_combobox.setCurrentIndex(2)

        # initialize associations
        self.also_reactive_power = False

        # create the table model
        self.associations = ProfileAssociations()
        for elm in self.objects:
            self.associations.append(ProfileAssociation(elm=elm))

        self.display_associations()

        self.ui.splitter.setStretchFactor(0, 3)
        self.ui.splitter.setStretchFactor(1, 7)

        # set name transformations
        self.transformations = {
            StringSubstitutions.PSSeBranchName.value: StringSubstitutions.PSSeBranchName,
            StringSubstitutions.PSSeBusGenerator.value: StringSubstitutions.PSSeBusGenerator,
            StringSubstitutions.PSSeBusLoad.value: StringSubstitutions.PSSeBusLoad
        }
        self.ui.nameTransformationComboBox.setModel(get_list_model(list(self.transformations.keys())))

        self.original_data_frame: pd.DataFrame | None = None
        self.fig = None

        self.ui.autolink_slider.setValue(100)  # Set slider to max value

        self.profile_names = list()

        self.excel_dialogue: ExcelDialog | None = None

        # click
        self.ui.open_button.clicked.connect(self.import_profile)
        self.ui.set_multiplier_button.clicked.connect(lambda: self.set_multiplier(MultiplierType.Mult))
        self.ui.autolink_button.clicked.connect(self.auto_link)
        self.ui.rnd_link_pushButton.clicked.connect(self.rnd_link)
        self.ui.assign_to_selection_pushButton.clicked.connect(self.link_to_selection)
        self.ui.assign_to_all_pushButton.clicked.connect(self.link_to_all)
        self.ui.doit_button.clicked.connect(self.do_it)
        self.ui.clear_selection_button.clicked.connect(self.clear_selection)
        self.ui.transformNamesPushButton.clicked.connect(self.transform_names)
        self.ui.plotButton.clicked.connect(self.plot_selected)

        # double click
        self.ui.assignation_table.doubleClicked.connect(self.assignation_table_double_click)

    def get_multiplier(self) -> float:
        """
        Gets the necessary multiplier to pass the profile units to Mega
        Remember that the power units in GridCal are the MVA
        """
        unit = self.ui.units_combobox.currentText()
        return self.units[unit] / self.units['M']

    def import_profile(self) -> None:
        """
        Select a file to be loaded
        """

        # declare the allowed file types
        files_types = "Formats (*.xlsx *.xls *.csv)"

        # call dialog to select the file
        filename, type_selected = QtWidgets.QFileDialog.getOpenFileName(self,
                                                                        caption='Open file',
                                                                        filter=files_types)

        if len(filename) > 0:
            # get the filename extension
            name, file_extension = os.path.splitext(filename)

            # Depending on the extension load the file
            if file_extension == '.csv':
                try:
                    df = pd.read_csv(filename,
                                     index_col=0,
                                     # dtype=float,  # do not use if dates are expected
                                     dayfirst=True)
                    # try to assign
                    self.assign_origin_df(df=df)

                except ValueError as e:
                    error_msg(text=str(e), title="Value error loading CSV file")
                    return

                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(filename, index_col=0, encoding='windows-1252')

                        # try to assign
                        self.assign_origin_df(df=df)

                    except Exception as e:
                        error_msg(str(e), title="Error")
                        return

            elif file_extension in ['.xlsx', '.xls']:

                # select the sheet from the file
                self.excel_dialogue = ExcelDialog(self, filename)
                self.excel_dialogue.exec()
                sheet_index = self.excel_dialogue.excel_sheet

                if sheet_index is not None:
                    df = pd.read_excel(filename, sheet_name=sheet_index, index_col=0)

                    # try to assign
                    self.assign_origin_df(df=df)
                else:
                    return

            else:
                error_msg(text="Could not open:\n" + filename, title="File open")
                return

    def try_format_the_source_data(self, df: pd.DataFrame = None) -> Tuple[pd.DataFrame, bool, Logger]:
        """
        This function heavily checks the data imported for invalid stuff
        :return: corrected DataFrame if possible, all_ok?, logger
        """
        logger = Logger()
        all_ok = True
        len_prof = df.shape[0]
        if self.circuit.has_time_series:
            if len_prof != len(self.circuit.time_profile) and len(self.circuit.time_profile) > 0:
                logger.add_error(msg="Profile length does not match",
                                 value=len_prof,
                                 expected_value=self.circuit.get_time_number())
                all_ok = False
            else:
                # try to recognize the time
                time_array, msg, ok = try_parse_dates(df.index)

                if not ok:
                    logger.add_error(msg="Imported dates are garbage. "
                                         "Use a proper format like day/month/year hour:minute:second",
                                     value=len_prof,
                                     expected_value=self.circuit.get_time_number())
                    all_ok = False
                else:
                    self.time = time_array
        else:
            self.time = self.circuit.time_profile

        if all_ok:

            # correct the column names
            cols = [str(x).strip() for x in df.columns.values]
            df.columns = cols

            # try to format the data as we want it
            if self.prop.tpe == float:

                if df.dtypes.apply(lambda dt: np.issubdtype(dt, np.number)).all():

                    try:
                        df = df.astype(float)
                    except Exception as e:

                        # run the diagnostic
                        for i in range(df.shape[0]):
                            for j in range(df.shape[1]):
                                try:
                                    a = float(df.values[i, j])
                                except Exception as e2:
                                    logger.add_error(msg=f"{e2}", value=df.values[i, j])

                        all_ok = False

                        logger.add_error(msg=f"Could not convert all data to float")

                    # replace NaN
                    try:
                        df.fillna(0, inplace=True)
                    except ValueError as e:
                        logger.add_error(msg=f"Could not replace NaN")
                else:
                    all_ok = False
                    logger.add_error(msg=f"We are expecting float, but the data doesn't seem to be that")

            elif self.prop.tpe == int:

                if df.dtypes.apply(lambda dt: np.issubdtype(dt, np.number)).all():

                    try:
                        df = df.astype(int)
                    except Exception as e:

                        logger.add_error(msg=f"Could not convert all data to int")

                        # run the diagnostic
                        for i in range(df.shape[0]):
                            for j in range(df.shape[1]):
                                try:
                                    a = int(df.values[i, j])
                                except Exception as e2:
                                    logger.add_error(msg=f"{e2}", value=df.values[i, j])

                        all_ok = False
                else:
                    all_ok = False
                    logger.add_error(msg=f"We are expecting int, but the data doesn't seem to be that")

            elif self.prop.tpe == bool:

                if df.dtypes.apply(lambda dt: np.issubdtype(dt, np.bool)).all():
                    try:
                        df = df.astype(bool)
                    except Exception as e:

                        logger.add_error(msg=f"Could not convert all data to bool")

                        # run the diagnostic
                        for i in range(df.shape[0]):
                            for j in range(df.shape[1]):
                                try:
                                    a = bool(df.values[i, j])
                                except Exception as e2:
                                    logger.add_error(msg=f"{e2}", value=df.values[i, j])

                        all_ok = False
                else:
                    all_ok = False
                    logger.add_error(msg=f"We are expecting bool, but the data doesn't seem to be that")

        return df, all_ok, logger

    def assign_origin_df(self, df: pd.DataFrame):
        """
        Try to assign the loaded data
        :param df: DataFrame
        """
        df, all_ok, logger = self.try_format_the_source_data(df=df)

        if all_ok:
            self.original_data_frame = df

            # set the profile names list
            self.profile_names = np.array([str(e).strip() for e in self.original_data_frame.columns.values],
                                          dtype=object)

            self.ui.sources_list.setModel(get_list_model(self.profile_names))

            self.toast_manager.show_info_toast("Profiles loaded for assigning...")

            # If the columns in the loaded data file do not match the length of the objects,
            # it likely indicates an update of profiles. Therefore, uncheck the checkbox to preserve the original
            # profiles that are not included in the update.
            if self.original_data_frame.shape[1] != len(self.objects):
                self.ui.setUnassignedToZeroCheckBox.setChecked(False)

        else:
            if logger.has_logs():
                dlg = LogsDialogue("Import issues", logger)
                dlg.setModal(True)
                dlg.exec()

    def plot_selected(self):
        """
        Plot the selected profile
        """
        if self.original_data_frame is not None:
            if len(self.ui.sources_list.selectedIndexes()) > 0:
                idx = self.ui.sources_list.selectedIndexes()[0].row()
                col_name = self.original_data_frame.columns[idx]
                try:
                    plt.ion()
                    self.fig = plt.Figure(figsize=(8, 6))
                    ax = self.fig.add_subplot(111)
                    self.original_data_frame[col_name].plot(ax=ax)
                    plt.show()
                except TypeError as e:
                    self.toast_manager.show_error_toast(str(e))
            else:
                self.toast_manager.show_warning_toast("No profile selected :/")
        else:
            self.toast_manager.show_warning_toast("No data loaded :/")

    def display_associations(self) -> None:
        """

        @return:
        """
        self.ui.assignation_table.setModel(self.associations)
        self.ui.assignation_table.repaint()

    def make_association(self, source_idx: int, obj_idx: int, scale: float = 1.0, mult: float = 1.0) -> None:
        """
        Makes an association in the associations table
        """
        if scale is None:
            scale = self.get_multiplier()

        if mult is None:
            mult = 1.0

        self.associations.set_profile_at(obj_idx, self.profile_names[source_idx])
        self.associations.set_scale_at(obj_idx, scale)
        self.associations.set_multiplier_at(obj_idx, mult)

    def assignation_table_double_click(self):
        """
        Set the selected profile into the clicked slot
        """
        if len(self.ui.sources_list.selectedIndexes()) > 0:
            idx_s = self.ui.sources_list.selectedIndexes()[0].row()
            idx_o = self.ui.assignation_table.selectedIndexes()[0].row()
            col = self.ui.assignation_table.selectedIndexes()[0].column()

            self.make_association(idx_s, idx_o, mult=1.0)

    def set_multiplier(self, tpe):
        """
        Set the table multipliers
        """
        if len(self.ui.assignation_table.selectedIndexes()) > 0:
            mult = self.ui.multSpinBox.value()
            for index in self.ui.assignation_table.selectedIndexes():
                idx = index.row()

                if tpe == MultiplierType.Mult:
                    self.associations.set_multiplier_at(idx, mult)

            self.display_associations()

    @staticmethod
    def normalize_string(s):
        """
        Normalizes a string
        """
        for p in string.punctuation:
            s = s.replace(p, '')
        return s.lower().strip()

    def auto_link(self):
        """
        Performs an automatic link between the sources and the objectives based on the names
        """
        mult = self.get_multiplier()
        threshold = self.ui.autolink_slider.value() / 100.0
        profile_names = list(self.profile_names.copy())

        for idx_o, elm in enumerate(self.objects):

            idx: int | None = check_similarity(name_to_search=elm.name.strip(),
                                               code_to_search=elm.code.strip(),
                                               idtag_to_search=elm.idtag.strip(),
                                               names_array=profile_names,
                                               threshold=threshold)

            # assign the string with the closest match profile
            if idx is not None:
                # make the association
                self.make_association(idx, idx_o, 1.0, mult)

        self.display_associations()

    def rnd_link(self):
        """
        Random link
        """
        # scale = self.get_multiplier()
        mult = 1
        scale = self.get_multiplier()

        if self.ui.sources_list.model() is not None:

            if self.ui.sources_list.model().rowCount() > 0:
                # make a list of the source indices
                source_indices = [i for i in range(self.ui.sources_list.model().rowCount())]

                # make a list of the destination indices
                destination_indices = [i for i in range(self.ui.assignation_table.model().rowCount())]

                # while there are elements in the destination indices
                while len(destination_indices) > 0:
                    # pick a random source
                    rnd_idx_s = randint(0, len(source_indices) - 1)

                    # pick and delete_with_dialogue a random destination
                    rnd_idx_o = randint(0, len(destination_indices) - 1)

                    # get the actual index
                    idx_s = source_indices[rnd_idx_s]

                    # get the actual index
                    idx_o = destination_indices.pop(rnd_idx_o)

                    # make the association
                    self.make_association(idx_s, idx_o, scale, mult)

                self.display_associations()
            else:
                pass
        else:
            pass

    def link_to_selection(self):
        """
        Links the selected origin with the selected destinations
        """

        if len(self.ui.sources_list.selectedIndexes()) > 0:
            idx_s = self.ui.sources_list.selectedIndexes()[0].row()

            scale = self.get_multiplier()
            mult = 1
            scale = self.get_multiplier()

            # set of different rows
            sel_rows = {item.row() for item in self.ui.assignation_table.selectedIndexes()}

            for idx_o in sel_rows:
                self.make_association(idx_s, idx_o, scale, mult)

            self.display_associations()

    def link_to_all(self):
        """
        Links the selected origin with all the destinations
        """

        if len(self.ui.sources_list.selectedIndexes()) > 0:
            idx_s = self.ui.sources_list.selectedIndexes()[0].row()
            mult = 1
            scale = self.get_multiplier()

            # set of different rows
            n_rows = self.ui.assignation_table.model().rowCount()

            for idx_o in range(n_rows):
                self.make_association(idx_s, idx_o, scale, mult)

            self.display_associations()

    def get_profiles_data(self) -> Tuple[Mat | None, BoolVec | None]:
        """
        Return ths assigned profiles
        @return:
            Array of profiles assigned to the input objectives
            Array specifying which objectives are not assigned
        """

        if self.original_data_frame is None:
            return None, None

        n_obj = len(self.objects)
        rows_o, cols_o = np.shape(self.original_data_frame)

        profiles = [None] * n_obj
        zeroed = np.zeros(n_obj, dtype=bool)  # array to know which profiles are only zeros

        for i_obj in range(n_obj):

            scale = self.associations.get_scale_at(i_obj)
            mult = self.associations.get_multiplier_at(i_obj)
            profile_name = self.associations.get_profile_at(i_obj)

            if profile_name != '':
                # active power
                if self.also_reactive_power:
                    vals = self.original_data_frame[profile_name].values * scale * mult + 0j
                else:
                    vals = self.original_data_frame[profile_name].values * scale * mult

            else:
                vals = np.zeros(rows_o)

                if self.ui.setUnassignedToZeroCheckBox.isChecked():
                    zeroed[i_obj] = False
                else:
                    zeroed[i_obj] = True

            profiles[i_obj] = vals

        return np.array(profiles).transpose(), zeroed

    def clear_selection(self):
        """
        Clear the selected associations
        """
        for idx in self.ui.assignation_table.selectedIndexes():
            obj_idx = idx.row()
            self.associations.clear_at(obj_idx)
        self.display_associations()

    def transform_names(self):
        """
        Transform the names of the inputs
        :return:
        """
        if self.original_data_frame is not None:
            mode_txt = self.ui.nameTransformationComboBox.currentText()
            mode = self.transformations[mode_txt]

            if mode == StringSubstitutions.PSSeBranchName:

                for i, name in enumerate(self.profile_names):
                    if '_':
                        vals = name.split('_')
                        if len(vals) < 7:
                            pass
                        else:
                            self.profile_names[i] = vals[0] + '_' + vals[3] + '_' + vals[6]
                self.original_data_frame.columns = self.profile_names

            if mode == StringSubstitutions.PSSeBusGenerator:

                for i, name in enumerate(self.profile_names):
                    if '_':
                        vals = name.split('_')
                        if len(vals) == 3:
                            self.profile_names[i] = vals[0] + '_1'
                self.original_data_frame.columns = self.profile_names

            elif mode == StringSubstitutions.PSSeBusLoad:
                for i, name in enumerate(self.profile_names):
                    self.profile_names[i] = name + '_1'
                self.original_data_frame.columns = self.profile_names

    def has_profile(self, i: int) -> bool:
        """
        Return if an object index has an associated profile
        :param i:
        :return:
        """
        return self.associations.get_profile_at(i) != ""

    def do_it(self) -> None:
        """
        Close. The data has to be queried later to the object by the parent by calling get_association_data
        """

        if self.time is not None:

            # Generate profiles
            self.data, zeroed = self.get_profiles_data()

            if self.prop.tpe == float:
                normalized = self.ui.normalized_checkBox.isChecked()
            else:
                normalized = False

            # if there are no profiles, set the loaded one
            if self.circuit.time_profile is None:
                self.circuit.format_profiles(self.time)
            else:
                if self.circuit.get_time_number() == 0:
                    self.circuit.format_profiles(self.time)

            # Assign profiles
            for i, elm in enumerate(self.objects):
                if not zeroed[i]:

                    if normalized:
                        arr = self.data[:, i]
                        mx = arr.max()
                        if mx != 0.0:
                            arr /= mx  # divide each series by the maximum of itself

                        base_value = elm.get_snapshot_value_by_name(self.magnitude)
                        data = arr * base_value
                    else:
                        data = self.data[:, i]

                    # assign the profile to the object
                    elm.set_profile_array(magnitude=self.magnitude, arr=data)
                else:
                    pass

            self.was_accepted = True
            self.close()
        else:
            self.was_accepted = False
            info_msg(text="No time profile.\nConsider loading a valid source of data.",
                     title="No time profile")
