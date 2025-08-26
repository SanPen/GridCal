# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import pandas as pd
from typing import List
from PySide6 import QtWidgets
from matplotlib import pyplot as plt

import GridCal.Gui.gui_functions as gf
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCal.Gui.general_dialogues import NewProfilesStructureDialogue, TimeReIndexDialogue, LogsDialogue
from GridCal.Gui.messages import yes_no_question, warning_msg, info_msg
from GridCal.Gui.Main.SubClasses.Model.data_base import DataBaseTableMain
from GridCal.Gui.ProfilesInput.models_dialogue import ModelsInputGUI
from GridCal.Gui.ProfilesInput.profile_dialogue import ProfileInputGUI, GeneratorsProfileOptionsDialogue
from GridCal.Gui.profiles_model import ProfilesModel


class TimeEventsMain(DataBaseTableMain):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        DataBaseTableMain.__init__(self, parent)

        # --------------------------------------------------------------------------------------------------------------
        self.ui.actionre_index_time.triggered.connect(self.re_index_time)

        # Buttons
        self.ui.new_profiles_structure_pushButton.clicked.connect(self.new_profiles_structure)
        self.ui.delete_profiles_structure_pushButton.clicked.connect(self.delete_profiles_structure)
        self.ui.edit_profiles_pushButton.clicked.connect(self.import_profiles)
        self.ui.edit_profiles_from_models_pushButton.clicked.connect(self.import_profiles_from_models)
        self.ui.set_profile_state_button.clicked.connect(self.set_profile_state_to_snapshot)
        self.ui.profile_add_pushButton.clicked.connect(lambda: self.modify_profiles('+'))
        self.ui.profile_subtract_pushButton.clicked.connect(lambda: self.modify_profiles('-'))
        self.ui.profile_multiply_pushButton.clicked.connect(lambda: self.modify_profiles('*'))
        self.ui.profile_divide_pushButton.clicked.connect(lambda: self.modify_profiles('/'))
        self.ui.set_profile_value_pushButton.clicked.connect(lambda: self.modify_profiles('set'))
        self.ui.set_linear_combination_profile_pushButton.clicked.connect(self.set_profile_as_linear_combination)
        self.ui.plot_time_series_pushButton.clicked.connect(self.plot_profiles)
        self.ui.copy_profile_pushButton.clicked.connect(self.copy_profiles)
        self.ui.paste_profiles_pushButton.clicked.connect(self.paste_profiles)

        # combobox change
        self.ui.device_type_magnitude_comboBox.currentTextChanged.connect(self.profile_device_type_changed)

    def profile_device_type_changed(self):
        """
        profile_device_type_changed
        """
        self.display_profiles(proxy_mdl=self.get_current_objects_model_view())

    def new_profiles_structure(self):
        """
        Create new profiles structure
        :return:
        """
        dlg = NewProfilesStructureDialogue()
        if dlg.exec():
            steps, step_length, step_unit, time_base = dlg.get_values()

            self.ui.profiles_tableView.setModel(None)

            self.circuit.create_profiles(steps=steps,
                                         step_length=step_length,
                                         step_unit=step_unit,
                                         time_base=time_base)

            self.display_profiles(proxy_mdl=self.get_current_objects_model_view())

            self.update_date_dependent_combos()

    def delete_profiles_structure(self):
        """
        Delete all profiles
        :return: Nothing
        """

        if self.circuit.time_profile is not None:
            quit_msg = "Are you sure that you want to delete the profiles?"
            reply = QtWidgets.QMessageBox.question(self, 'Message', quit_msg,
                                                   QtWidgets.QMessageBox.StandardButton.Yes,
                                                   QtWidgets.QMessageBox.StandardButton.No)

            if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
                self.circuit.delete_profiles()
                self.ui.profiles_tableView.setModel(None)
                self.update_date_dependent_combos()
                self.update_from_to_list_views()
            else:
                pass
        else:
            warning_msg('There are no profiles', 'Delete profiles')

    def import_profiles(self):
        """
        Profile importer
        """
        dev_type_text = self.get_db_object_selected_type()

        if dev_type_text is not None:
            idx = self.ui.device_type_magnitude_comboBox.currentIndex()

            magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type_text]
            dev_type = self.circuit.device_type_name_dict[dev_type_text]
            objects: List[ALL_DEV_TYPES] = self.circuit.get_elements_by_type(dev_type)
            magnitude = magnitudes[idx]

            if len(objects) > 0 and idx > -1:
                self.profile_input_dialogue = ProfileInputGUI(parent=self,
                                                              circuit=self.circuit,
                                                              dev_type=dev_type,
                                                              objects=objects,
                                                              magnitude=magnitude)

                self.profile_input_dialogue.resize(int(1.61 * 600.0), 550)  # golden ratio
                self.profile_input_dialogue.exec()  # exec leaves the parent on hold

                # Note: the ProfileInputGUI will handle the profile assigning

                if self.profile_input_dialogue.was_accepted:

                    # set up sliders
                    self.update_date_dependent_combos()
                    self.display_profiles(proxy_mdl=self.get_current_objects_model_view())
                    self.show_info_toast("Profiles imported", duration=3000)

                    # ask to update active profile when magnitude is P for generators and loads
                    if len(objects) > 0:
                        if magnitude == 'P':
                            if objects[0].device_type == DeviceType.GeneratorDevice:

                                dlg = GeneratorsProfileOptionsDialogue()
                                dlg.exec()

                                if dlg.correct_active_profile.isChecked():
                                    self.fix_generators_active_based_on_the_power(ask_before=False)
                                    self.show_info_toast("Generators active status set")

                                if dlg.set_non_dispatchable.isChecked():
                                    for i, elm in enumerate(objects):
                                        if self.profile_input_dialogue.has_profile(i):
                                            # if there was a profile, we want the generator not dispatchable
                                            elm.enabled_dispatch = False
                                        else:
                                            elm.enabled_dispatch = True

                                    self.show_info_toast("Generators dispatchable status set")

                            elif objects[0].device_type == DeviceType.LoadDevice:
                                ok1 = yes_no_question("Do you want to correct the loads active profile "
                                                      "based on the active power profile?",
                                                      "Match")
                                if ok1:
                                    self.fix_loads_active_based_on_the_power(ask_before=False)
                                    self.show_info_toast("Loads active status set")

                    else:
                        # the dialogue was closed
                        self.show_warning_toast("No profiles imported...")
                else:
                    # the dialogue was closed
                    self.show_warning_toast("No profiles imported...")

            else:
                self.show_error_toast("There are no objects...", duration=3000)

    def modify_profiles(self, operation='+'):
        """
        Edit profiles with a linear combination
        Args:
            operation: '+', '-', '*', '/'

        Returns: Nothing
        """
        value = self.ui.profile_factor_doubleSpinBox.value()

        dev_type_text = self.get_db_object_selected_type()

        if dev_type_text is not None:
            magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type_text]
            idx = self.ui.device_type_magnitude_comboBox.currentIndex()
            magnitude = magnitudes[idx]

            dev_type = self.circuit.device_type_name_dict[dev_type_text]
            objects: List[ALL_DEV_TYPES] = self.circuit.get_elements_by_type(dev_type)
            # Assign profiles
            if len(objects) > 0:

                indices = self.ui.profiles_tableView.selectedIndexes()

                # attr = objects[0].properties_with_profile[magnitude]

                model = self.ui.profiles_tableView.model()

                mod_cols = list()

                if len(indices) == 0:
                    # no index was selected
                    for i, elm in enumerate(objects):

                        # get the property object
                        gc_prop = elm.registered_properties[magnitude]

                        # get the profile
                        profile = elm.get_profile_by_prop(prop=gc_prop)

                        # compute the dense array (this is the simple way of doing this)
                        array = profile.toarray()

                        if operation == '+':
                            mod_array = (array + value).astype(gc_prop.tpe)
                            mod_cols.append(i)

                        elif operation == '-':
                            mod_array = (array - value).astype(gc_prop.tpe)
                            mod_cols.append(i)

                        elif operation == '*':
                            mod_array = (array * value).astype(gc_prop.tpe)
                            mod_cols.append(i)

                        elif operation == '/':
                            mod_array = (array / value).astype(gc_prop.tpe)
                            mod_cols.append(i)

                        elif operation == 'set':
                            mod_array = (np.ones(len(array)) * value).astype(gc_prop.tpe)
                            mod_cols.append(i)

                        else:
                            raise Exception('Operation not supported: ' + str(operation))

                        # apply the newly computed array
                        profile.set(arr=mod_array)

                else:
                    # indices were selected ...

                    for idx in indices:

                        # get the device
                        elm = objects[idx.column()]

                        # get the property object
                        gc_prop = elm.registered_properties[magnitude]

                        # get the profile
                        profile = elm.get_profile_by_prop(prop=gc_prop)

                        # compute the dense array (this is the simple way of doing this)
                        array = profile.toarray().copy()

                        if operation == '+':
                            array[idx.row()] += value
                            mod_cols.append(idx.column())

                        elif operation == '-':
                            array[idx.row()] -= value
                            mod_cols.append(idx.column())

                        elif operation == '*':
                            array[idx.row()] *= value
                            mod_cols.append(idx.column())

                        elif operation == '/':
                            array[idx.row()] /= value
                            mod_cols.append(idx.column())

                        elif operation == 'set':
                            array[idx.row()] = value
                            mod_cols.append(idx.column())

                        else:
                            raise Exception('Operation not supported: ' + str(operation))

                        # apply the newly computed array
                        profile.set(arr=array)

                # update model
                model.update()

    def set_profile_as_linear_combination(self):
        """
        Edit profiles with a linear combination
        Returns: Nothing
        """
        logger: Logger = Logger()
        # value = self.ui.profile_factor_doubleSpinBox.value()

        dev_type_text = self.get_db_object_selected_type()
        if dev_type_text is not None:
            magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type_text]
            idx_from = self.ui.device_type_magnitude_comboBox.currentIndex()
            magnitude_from = magnitudes[idx_from]

            idx_to = self.ui.device_type_magnitude_comboBox_2.currentIndex()
            magnitude_to = magnitudes[idx_to]

            if self.circuit.valid_for_simulation() and magnitude_from != magnitude_to:

                msg = "Are you sure that you want to overwrite the values " + magnitude_to + \
                      " with the values of " + magnitude_from + "?"

                reply = QtWidgets.QMessageBox.question(self, 'Message', msg,
                                                       QtWidgets.QMessageBox.StandardButton.Yes,
                                                       QtWidgets.QMessageBox.StandardButton.No)

                if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:

                    dev_type = self.circuit.device_type_name_dict[dev_type_text]
                    objects: List[ALL_DEV_TYPES] = self.circuit.get_elements_by_type(dev_type)

                    # Assign profiles
                    if len(objects) > 0:

                        for i, elm in enumerate(objects):
                            profile_from = elm.get_profile(magnitude=magnitude_from)
                            profile_to = elm.get_profile(magnitude=magnitude_to)
                            if profile_from is not None and profile_to is not None:
                                profile_to.set(profile_from.toarray())
                            else:
                                print(f"P or Q profile None in {elm.name}")

                        self.display_profiles(proxy_mdl=self.get_current_objects_model_view())

                else:
                    # rejected the operation
                    pass

            else:
                # no buses or no actual change
                pass

        if logger.has_logs():
            dlg = LogsDialogue("Set profile", logger=logger)
            dlg.exec()

    def re_index_time(self):
        """
        Re-index time
        :return:
        """

        dlg = TimeReIndexDialogue()
        dlg.setModal(True)
        dlg.exec()

        if dlg.is_accepted:
            self.circuit.re_index_time2(t0=dlg.date_time_editor.dateTime().toPython(),
                                        step_size=dlg.step_length.value(),
                                        step_unit=dlg.units.currentText())

            self.update_date_dependent_combos()

    def plot_profiles(self):
        """
        Plot profiles from the time events
        """
        dev_type_text = self.get_db_object_selected_type()

        if dev_type_text is not None:
            magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type_text]
            idx = self.ui.device_type_magnitude_comboBox.currentIndex()
            magnitude = magnitudes[idx]

            dev_type = self.circuit.device_type_name_dict[dev_type_text]
            objects = self.circuit.get_elements_by_type(dev_type)

            # get the selected element
            obj_idx = self.ui.profiles_tableView.selectedIndexes()

            t = self.circuit.time_profile

            # Assign profiles
            if len(obj_idx):
                fig = plt.figure(figsize=(12, 8))
                ax = fig.add_subplot(111)

                k = obj_idx[0].column()
                units_dict = {attr: pair.units for attr, pair in objects[k].registered_properties.items()}

                unit = units_dict[magnitude]
                ax.set_ylabel(unit)

                # get the unique columns in the selected cells
                cols = set()
                for i in range(len(obj_idx)):
                    cols.add(obj_idx[i].column())

                # plot every column
                dta = dict()
                for k in cols:
                    dta[objects[k].name] = objects[k].get_profile(magnitude=magnitude).toarray()
                df = pd.DataFrame(data=dta, index=t)
                df.plot(ax=ax)

                plt.show()

    def import_profiles_from_models(self):
        """
        Open the dialogue to load profile data from models
        """

        if not self.circuit.valid_for_simulation():
            warning_msg("There are no objects to which to assign a profile. \n"
                        "You need to load or create a grid!")
            return

        if self.circuit.time_profile is None:
            self.models_input_dialogue = ModelsInputGUI(parent=self)

            self.models_input_dialogue.resize(int(1.61 * 600.0), 550)  # golden ratio
            self.models_input_dialogue.exec()  # exec leaves the parent on hold

            if self.models_input_dialogue.grids_model is not None:

                logger = Logger()
                self.models_input_dialogue.process(main_grid=self.circuit, logger=logger)

                # set up sliders
                self.update_date_dependent_combos()
                self.display_profiles(proxy_mdl=self.get_current_objects_model_view())

                if logger.has_logs():
                    dialogue = LogsDialogue(name="Import profiles", logger=logger)
                    dialogue.exec()

        else:
            warning_msg("The import of profiles from many grid models "
                        "can only be done if the grid has not profiles :/")

    def get_circuit_snapshot_datetime(self):
        """
        Set the datetime from the circuit
        """
        val = self.circuit.snapshot_time
        self.ui.snapshot_dateTimeEdit.setDateTime(val)

    def set_profile_state_to_snapshot(self):
        """
        Set the selected profiles state in the grid
        """
        idx = self.ui.db_step_slider.value()

        if idx > -1:
            self.circuit.set_state(t=idx)
            self.get_circuit_snapshot_datetime()
            self.show_info_toast("Profile value set to the snapshot")
        else:
            info_msg('Select a time series step to copy to the snapshot', 'Set snapshot')

    def copy_profiles(self):
        """
        Copy the current displayed profiles to the clipboard
        """

        mdl: ProfilesModel = self.ui.profiles_tableView.model()

        cols = set()
        if len(self.ui.profiles_tableView.selectedIndexes()) > 0:
            for index in self.ui.profiles_tableView.selectedIndexes():
                row_idx = index.row()
                col_idx = index.column()
                cols.add(col_idx)
        else:
            row_idx = 0
            col_idx = 0

        if mdl is not None:
            mdl.copy_to_clipboard(cols=list(cols))
        else:
            warning_msg('There is no profile displayed, please display one', 'Copy profile to clipboard')

    def paste_profiles(self):
        """
        Paste clipboard data into the profile
        """

        mdl = self.ui.profiles_tableView.model()
        if mdl is not None:

            if len(self.ui.profiles_tableView.selectedIndexes()) > 0:
                index = self.ui.profiles_tableView.selectedIndexes()[0]
                row_idx = index.row()
                col_idx = index.column()
            else:
                row_idx = 0
                col_idx = 0

            mdl.paste_from_clipboard(row_idx=row_idx, col_idx=col_idx)
        else:
            warning_msg('There is no profile displayed, please display one', 'Paste profile to clipboard')
