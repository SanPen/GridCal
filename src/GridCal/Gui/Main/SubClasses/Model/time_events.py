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
import numpy as np
import pandas as pd
from PySide6 import QtWidgets
from matplotlib import pyplot as plt

import GridCal.Gui.GuiFunctions as gf
from GridCalEngine.enumerations import DeviceType
from GridCal.Gui.GeneralDialogues import NewProfilesStructureDialogue, TimeReIndexDialogue
from GridCal.Gui.messages import yes_no_question, warning_msg, info_msg
from GridCal.Gui.Main.SubClasses.Model.objects import ObjectsTableMain
from GridCal.Gui.ProfilesInput.models_dialogue import ModelsInputGUI
from GridCal.Gui.ProfilesInput.profile_dialogue import ProfileInputGUI


class TimeEventsMain(ObjectsTableMain):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        ObjectsTableMain.__init__(self, parent)

        mdl = gf.get_list_model(self.circuit.profile_magnitudes.keys())
        self.ui.profile_device_type_comboBox.setModel(mdl)
        self.profile_device_type_changed()

        # --------------------------------------------------------------------------------------------------------------
        self.ui.actionre_index_time.triggered.connect(self.re_index_time)

        # Buttons
        self.ui.new_profiles_structure_pushButton.clicked.connect(self.new_profiles_structure)
        self.ui.delete_profiles_structure_pushButton.clicked.connect(self.delete_profiles_structure)
        # self.ui.set_profile_state_button.clicked.connect(self.set_profiles_state_to_grid)
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

        # combobox chnage
        self.ui.profile_device_type_comboBox.currentTextChanged.connect(self.profile_device_type_changed)
        self.ui.device_type_magnitude_comboBox.currentTextChanged.connect(self.display_profiles)

    def profile_device_type_changed(self):
        """
        profile_device_type_changed
        """
        dev_type = self.ui.profile_device_type_comboBox.currentText()
        mdl = gf.get_list_model(self.circuit.profile_magnitudes[dev_type][0])
        self.ui.device_type_magnitude_comboBox.setModel(mdl)
        self.ui.device_type_magnitude_comboBox_2.setModel(mdl)

    def new_profiles_structure(self):
        """
        Create new profiles structure
        :return:
        """
        dlg = NewProfilesStructureDialogue()
        if dlg.exec_():
            steps, step_length, step_unit, time_base = dlg.get_values()

            self.ui.profiles_tableView.setModel(None)

            self.circuit.create_profiles(steps, step_length, step_unit, time_base)

            self.display_profiles()

            # self.set_up_profile_sliders()

            self.update_date_dependent_combos()

    def delete_profiles_structure(self):
        """
        Delete all profiles
        :return: Nothing
        """

        if self.circuit.time_profile is not None:
            quit_msg = "Are you sure that you want to remove the profiles?"
            reply = QtWidgets.QMessageBox.question(self, 'Message', quit_msg,
                                                   QtWidgets.QMessageBox.StandardButton.Yes,
                                                   QtWidgets.QMessageBox.StandardButton.No)

            if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
                for bus in self.circuit.buses:
                    bus.delete_profiles()
                self.circuit.time_profile = None
                self.ui.profiles_tableView.setModel(None)
                # self.set_up_profile_sliders()
                self.update_date_dependent_combos()
                self.update_area_combos()
            else:
                pass
        else:
            warning_msg('There are no profiles', 'Delete profiles')

    def import_profiles(self):
        """
        Profile importer
        """

        # Load(), StaticGenerator(), Generator(), Battery(), Shunt()

        dev_type_text = self.ui.profile_device_type_comboBox.currentText()
        magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type_text]

        idx = self.ui.device_type_magnitude_comboBox.currentIndex()
        magnitude = magnitudes[idx]

        dev_type = self.circuit.device_type_name_dict[dev_type_text]
        objects = self.circuit.get_elements_by_type(dev_type)

        if len(objects) > 0:
            self.profile_input_dialogue = ProfileInputGUI(parent=self,
                                                          list_of_objects=objects,
                                                          magnitudes=[magnitude])

            self.profile_input_dialogue.resize(int(1.61 * 600.0), 550)  # golden ratio
            self.profile_input_dialogue.exec_()  # exec leaves the parent on hold

            if self.profile_input_dialogue.time is not None:

                # if there are no profiles:
                if self.circuit.time_profile is None:
                    self.circuit.format_profiles(self.profile_input_dialogue.time)

                elif len(self.profile_input_dialogue.time) != len(self.circuit.time_profile):
                    warning_msg("The imported profile length does not match the existing one.\n"
                                "Delete the existing profiles before continuing.\n"
                                "The import action will not be performed")
                    return False

                # Assign profiles
                for i, elm in enumerate(objects):
                    if not self.profile_input_dialogue.zeroed[i]:

                        if self.profile_input_dialogue.normalized:
                            base_value = getattr(elm, magnitude)
                            data = self.profile_input_dialogue.data[:, i] * base_value
                        else:
                            data = self.profile_input_dialogue.data[:, i]

                        # assign the profile to the object
                        prof_attr = elm.properties_with_profile[magnitude]
                        setattr(elm, prof_attr, data)
                        # elm.profile_f[magnitude](dialogue.time, dialogue.data[:, i], dialogue.normalized)
                    else:
                        print(elm.name, 'skipped')

                # set up sliders
                # self.set_up_profile_sliders()
                self.update_date_dependent_combos()
                self.display_profiles()

                # ask to update active profile when magnitude is P for generators and loads
                if len(objects) > 0:
                    if magnitude == 'P':
                        if objects[0].device_type == DeviceType.GeneratorDevice:
                            ok = yes_no_question(
                                "Do you want to correct the generators active profile based on the active power profile?",
                                "Match")
                            if ok:
                                self.fix_generators_active_based_on_the_power(ask_before=False)
                        elif objects[0].device_type == DeviceType.LoadDevice:
                            ok = yes_no_question(
                                "Do you want to correct the loads active profile based on the active power profile?",
                                "Match")
                            if ok:
                                self.fix_loads_active_based_on_the_power(ask_before=False)

            else:
                pass  # the dialogue was closed

        else:
            warning_msg("There are no objects to which to assign a profile. \nYou need to load or create a grid!")

    def modify_profiles(self, operation='+'):
        """
        Edit profiles with a linear combination
        Args:
            operation: '+', '-', '*', '/'

        Returns: Nothing
        """
        value = self.ui.profile_factor_doubleSpinBox.value()

        dev_type_text = self.ui.profile_device_type_comboBox.currentText()
        magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type_text]
        idx = self.ui.device_type_magnitude_comboBox.currentIndex()
        magnitude = magnitudes[idx]

        dev_type = self.circuit.device_type_name_dict[dev_type_text]
        objects = self.circuit.get_elements_by_type(dev_type)
        # Assign profiles
        if len(objects) > 0:

            indices = self.ui.profiles_tableView.selectedIndexes()

            attr = objects[0].properties_with_profile[magnitude]

            model = self.ui.profiles_tableView.model()

            mod_cols = list()

            if len(indices) == 0:
                # no index was selected
                for i, elm in enumerate(objects):

                    tpe = getattr(elm, attr).dtype

                    if operation == '+':
                        setattr(elm, attr, (getattr(elm, attr) + value).astype(tpe))
                        mod_cols.append(i)

                    elif operation == '-':
                        setattr(elm, attr, (getattr(elm, attr) - value).astype(tpe))
                        mod_cols.append(i)

                    elif operation == '*':
                        setattr(elm, attr, (getattr(elm, attr) * value).astype(tpe))
                        mod_cols.append(i)

                    elif operation == '/':
                        setattr(elm, attr, (getattr(elm, attr) / value).astype(tpe))
                        mod_cols.append(i)

                    elif operation == 'set':
                        arr = getattr(elm, attr)
                        setattr(elm, attr, (np.ones(len(arr)) * value).astype(tpe))
                        mod_cols.append(i)

                    else:
                        raise Exception('Operation not supported: ' + str(operation))

            else:
                # indices were selected ...

                for idx in indices:

                    elm = objects[idx.column()]
                    tpe = type(getattr(elm, attr))

                    if operation == '+':
                        getattr(elm, attr)[idx.row()] += value
                        mod_cols.append(idx.column())

                    elif operation == '-':
                        getattr(elm, attr)[idx.row()] -= value
                        mod_cols.append(idx.column())

                    elif operation == '*':
                        getattr(elm, attr)[idx.row()] *= value
                        mod_cols.append(idx.column())

                    elif operation == '/':
                        getattr(elm, attr)[idx.row()] /= value
                        mod_cols.append(idx.column())

                    elif operation == 'set':
                        getattr(elm, attr)[idx.row()] = value
                        mod_cols.append(idx.column())

                    else:
                        raise Exception('Operation not supported: ' + str(operation))

            model.add_state(mod_cols, 'linear combinations')
            model.update()

    def set_profile_as_linear_combination(self):
        """
        Edit profiles with a linear combination
        Returns: Nothing
        """

        # value = self.ui.profile_factor_doubleSpinBox.value()

        dev_type_text = self.ui.profile_device_type_comboBox.currentText()
        magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type_text]
        idx_from = self.ui.device_type_magnitude_comboBox.currentIndex()
        magnitude_from = magnitudes[idx_from]

        idx_to = self.ui.device_type_magnitude_comboBox_2.currentIndex()
        magnitude_to = magnitudes[idx_to]

        if len(self.circuit.buses) > 0 and magnitude_from != magnitude_to:

            msg = "Are you sure that you want to overwrite the values " + magnitude_to + \
                  " with the values of " + magnitude_from + "?"

            reply = QtWidgets.QMessageBox.question(self, 'Message', msg,
                                                   QtWidgets.QMessageBox.StandardButton.Yes,
                                                   QtWidgets.QMessageBox.StandardButton.No)

            if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:

                dev_type = self.circuit.device_type_name_dict[dev_type_text]
                objects = self.circuit.get_elements_by_type(dev_type)

                # Assign profiles
                if len(objects) > 0:
                    attr_from = objects[0].properties_with_profile[magnitude_from]
                    attr_to = objects[0].properties_with_profile[magnitude_to]

                    for i, elm in enumerate(objects):
                        setattr(elm, attr_to, getattr(elm, attr_from) * 1.0)

                    self.display_profiles()

            else:
                # rejected the operation
                pass

        else:
            # no buses or no actual change
            pass

    def re_index_time(self):
        """
        Re-index time
        :return:
        """

        dlg = TimeReIndexDialogue()
        dlg.setModal(True)
        dlg.exec_()

        if dlg.accepted:
            self.circuit.re_index_time2(t0=dlg.date_time_editor.dateTime().toPython(),
                                        step_size=dlg.step_length.value(),
                                        step_unit=dlg.units.currentText())

            self.update_date_dependent_combos()

    def plot_profiles(self):
        """
        Plot profiles from the time events
        """
        value = self.ui.profile_factor_doubleSpinBox.value()

        dev_type_text = self.ui.profile_device_type_comboBox.currentText()
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
            units_dict = {attr: pair.units for attr, pair in objects[k].editable_headers.items()}

            unit = units_dict[magnitude]
            ax.set_ylabel(unit)

            # get the unique columns in the selected cells
            cols = set()
            for i in range(len(obj_idx)):
                cols.add(obj_idx[i].column())

            # plot every column
            dta = dict()
            for k in cols:
                attr = objects[k].properties_with_profile[magnitude]
                dta[objects[k].name] = getattr(objects[k], attr)
            df = pd.DataFrame(data=dta, index=t)
            df.plot(ax=ax)

            plt.show()

    def display_profiles(self):
        """
        Display profile
        """
        if self.circuit.time_profile is not None:

            dev_type_text = self.ui.profile_device_type_comboBox.currentText()

            magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type_text]

            if len(magnitudes) > 0:
                # get the enumeration univoque association with he device text
                dev_type = self.circuit.device_type_name_dict[dev_type_text]

                idx = self.ui.device_type_magnitude_comboBox.currentIndex()
                magnitude = magnitudes[idx]
                mtype = mag_types[idx]

                mdl = gf.ProfilesModel(multi_circuit=self.circuit,
                                       device_type=dev_type,
                                       magnitude=magnitude,
                                       format=mtype,
                                       parent=self.ui.profiles_tableView)
            else:
                mdl = None

            self.ui.profiles_tableView.setModel(mdl)


    def import_profiles_from_models(self):
        """
        Open the dialogue to load profile data from models
        """

        if len(self.circuit.buses) == 0:
            warning_msg("There are no objects to which to assign a profile. \n"
                        "You need to load or create a grid!")
            return

        if self.circuit.time_profile is None:
            self.new_profiles_structure()

        # if there are no profiles:
        if self.circuit.time_profile is not None:
            self.models_input_dialogue = ModelsInputGUI(parent=self,
                                                        time_array=self.circuit.time_profile)

            self.models_input_dialogue.resize(int(1.61 * 600.0), 550)  # golden ratio
            self.models_input_dialogue.exec_()  # exec leaves the parent on hold

            if self.models_input_dialogue.grids_model is not None:
                self.models_input_dialogue.process(main_grid=self.circuit)

                # set up sliders
                # self.set_up_profile_sliders()
                self.update_date_dependent_combos()
                self.display_profiles()

        else:
            warning_msg("You need to declare a time profile first.\n\n"
                        "Then, this button will show the dialogue to\n"
                        "load the data from the models at the time steps\n"
                        "that you prefer.\n\n"
                        "Use the 'Create profiles button'.")

    def set_profile_state_to_snapshot(self):
        """
        Set the selected profiles state in the grid
        """
        idx = self.ui.profile_time_selection_comboBox.currentIndex()

        if idx > -1:
            self.circuit.set_state(t=idx)
        else:
            info_msg('No time state selected', 'Set state')

    def copy_profiles(self):
        """
        Copy the current displayed profiles to the clipboard
        """

        mdl = self.ui.profiles_tableView.model()
        if mdl is not None:
            mdl.copy_to_clipboard()
            print('Copied!')
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
