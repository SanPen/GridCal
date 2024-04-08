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

import os
from warnings import warn
from typing import Union
import pandas as pd
from PySide6 import QtWidgets

import GridCal.Gui.GuiFunctions as gf
import GridCal.Session.export_results_driver as exprtdrv
import GridCal.Session.file_handler as filedrv
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCal.Gui.CoordinatesInput.coordinates_dialogue import CoordinatesInputGUI
from GridCal.Gui.GeneralDialogues import LogsDialogue, CustomQuestionDialogue
from GridCal.Gui.Diagrams.DiagramEditorWidget.diagram_editor_widget import DiagramEditorWidget
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg, info_msg
from GridCal.Gui.GridGenerator.grid_generator_dialogue import GridGeneratorGUI
from GridCal.Gui.RosetaExplorer.RosetaExplorer import RosetaExplorerGUI
from GridCal.Gui.Main.SubClasses.Settings.configuration import ConfigurationMain

from GridCalEngine.Compilers.circuit_to_newton_pa import NEWTON_PA_AVAILABLE
from GridCalEngine.Compilers.circuit_to_pgm import PGM_AVAILABLE
from GridCalEngine.IO.gridcal.contingency_parser import import_contingencies_from_json, export_contingencies_json_file
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at


class IoMain(ConfigurationMain):
    """
    Inputs-Outputs Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        ConfigurationMain.__init__(self, parent)

        self.rosetta_gui: Union[RosetaExplorerGUI, None] = None

        self.accepted_extensions = ['.gridcal', '.xlsx', '.xls', '.sqlite', '.gch5',
                                    '.dgs', '.m', '.raw', '.RAW', '.json',
                                    '.ejson2', '.ejson3',
                                    '.xml', '.rawx', '.zip', '.dpx', '.epc']

        self.ui.actionNew_project.triggered.connect(self.new_project)
        self.ui.actionOpen_file.triggered.connect(self.open_file)
        self.ui.actionAdd_circuit.triggered.connect(self.add_circuit)
        self.ui.actionSave.triggered.connect(self.save_file)
        self.ui.actionSave_as.triggered.connect(self.save_file_as)
        self.ui.actionExport_all_the_device_s_profiles.triggered.connect(self.export_object_profiles)
        self.ui.actionExport_all_results.triggered.connect(self.export_all)
        self.ui.actiongrid_Generator.triggered.connect(self.grid_generator)
        self.ui.actionImport_bus_coordinates.triggered.connect(self.import_bus_coordinates)
        self.ui.actionImport_contingencies.triggered.connect(self.import_contingencies)
        self.ui.actionExport_contingencies.triggered.connect(self.export_contingencies)

        # Buttons
        self.ui.exportSimulationDataButton.clicked.connect(self.export_simulation_data)
        self.ui.loadResultFromDiskButton.clicked.connect(self.load_results_driver)

    def dragEnterEvent(self, event):
        """

        :param event:
        :return:
        """
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """

        :param event:
        :return:
        """
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """
        Drop file on the GUI, the default behaviour is to load the file
        :param event: event containing all the information
        """
        if event.mimeData().hasUrls:
            events = event.mimeData().urls()
            if len(events) > 0:

                file_names = list()

                for event in events:
                    file_name = event.toLocalFile()
                    name, file_extension = os.path.splitext(file_name)
                    if file_extension.lower() in self.accepted_extensions:
                        file_names.append(file_name)
                    else:
                        error_msg('The file type ' + file_extension.lower() + ' is not accepted :(')

                if self.circuit.get_bus_number() > 0:
                    quit_msg = "Are you sure that you want to quit the current grid and open a new one?" \
                               "\n If the process is cancelled the grid will remain."
                    reply = QtWidgets.QMessageBox.question(self, 'Message', quit_msg,
                                                           QtWidgets.QMessageBox.StandardButton.Yes,
                                                           QtWidgets.QMessageBox.StandardButton.No)

                    if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
                        self.open_file_now(filenames=file_names)
                else:
                    # Just open the file
                    self.open_file_now(filenames=file_names)

    def new_project_now(self, create_default_diagrams=True):
        """
        New project right now without asking questions
        """
        # clear the circuit model
        self.circuit = MultiCircuit()

        # clear the file name
        self.file_name = ''

        self.remove_all_diagrams()

        self.ui.dataStructuresTreeView.setModel(gf.get_tree_model(self.circuit.get_objects_with_profiles_str_dict(),
                                                                  top='Objects'))
        self.expand_object_tree_nodes()

        # clear the results
        self.ui.resultsTableView.setModel(None)
        self.ui.resultsLogsTreeView.setModel(None)

        # clear the comments
        self.ui.comments_textEdit.setText("")

        self.ui.grid_name_line_edit.setText("")

        # clear the simulation objects
        for thread in self.get_all_threads():
            thread = None

        if self.analysis_dialogue is not None:
            self.analysis_dialogue.close()

        self.clear_stuff_running()
        self.clear_results()
        self.create_console()

        if create_default_diagrams:
            self.add_complete_bus_branch_diagram()
            self.add_map_diagram()
            self.set_diagram_widget(self.diagram_widgets_list[0])

        self.collect_memory()

    def new_project(self):
        """
        Create new grid
        :return:
        """
        if self.circuit.get_bus_number() > 0:
            quit_msg = "Are you sure that you want to quit the current grid and create a new one?"
            reply = QtWidgets.QMessageBox.question(self, 'Message', quit_msg,
                                                   QtWidgets.QMessageBox.StandardButton.Yes,
                                                   QtWidgets.QMessageBox.StandardButton.No)

            if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
                self.new_project_now(create_default_diagrams=True)

    def open_file(self):
        """
        Open GridCal file
        @return:
        """
        if ('file_save' not in self.stuff_running_now) and ('file_open' not in self.stuff_running_now):
            if self.circuit.get_bus_number() > 0:
                quit_msg = ("Are you sure that you want to quit the current grid and open a new one?"
                            "\n If the process is cancelled the grid will remain.")
                reply = QtWidgets.QMessageBox.question(self, 'Message', quit_msg,
                                                       QtWidgets.QMessageBox.StandardButton.Yes,
                                                       QtWidgets.QMessageBox.StandardButton.No)

                if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
                    self.open_file_threaded()
                else:
                    pass
            else:
                # Just open the file
                self.open_file_threaded()

        else:
            warning_msg('There is a file being processed now.')

    def open_file_threaded(self, post_function=None):
        """
        Open file from a Qt thread to remain responsive
        """

        files_types = ("Formats (*.gridcal *.gch5 *.xlsx *.xls *.sqlite *.dgs "
                       "*.m *.raw *.RAW *.rawx *.json *.ejson2 *.ejson3 *.xml *.zip *.dpx *.epc *.nc *.hdf5)")

        dialogue = QtWidgets.QFileDialog(None,
                                         caption='Open file',
                                         directory=self.project_directory,
                                         filter=files_types)

        if dialogue.exec():
            filenames = dialogue.selectedFiles()
            self.open_file_now(filenames, post_function)

    def select_csv_file(self, caption='Open CSV file'):
        """
        Select a CSV file
        :return: csv file path
        """
        files_types = "CSV (*.csv)"

        filename, type_selected = QtWidgets.QFileDialog.getOpenFileName(parent=self,
                                                                        caption=caption,
                                                                        dir=self.project_directory,
                                                                        filter=files_types)

        if len(filename) > 0:
            return filename
        else:
            return None

    def open_file_now(self, filenames, post_function=None) -> None:
        """
        Open a file without questions
        :param filenames: list of file names (may be more than one because of CIM TP and EQ files)
        :param post_function: function callback
        :return: Nothing
        """
        if len(filenames) > 0:
            self.file_name = filenames[0]

            # store the working directory
            self.project_directory = os.path.dirname(self.file_name)

            # lock the ui
            self.LOCK()

            # create thread
            self.open_file_thread_object = filedrv.FileOpenThread(
                file_name=filenames if len(filenames) > 1 else filenames[0]
            )

            # make connections
            self.open_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
            self.open_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
            self.open_file_thread_object.done_signal.connect(self.UNLOCK)
            if post_function is None:
                self.open_file_thread_object.done_signal.connect(self.post_open_file)
            else:
                self.open_file_thread_object.done_signal.connect(post_function)

            # thread start
            self.open_file_thread_object.start()

            # register as the latest file driver
            self.last_file_driver = self.open_file_thread_object

            # register thread
            self.stuff_running_now.append('file_open')

    def post_open_file(self) -> None:
        """
        Actions to perform after a file has been loaded
        """

        self.stuff_running_now.remove('file_open')

        if self.open_file_thread_object is not None:

            if self.open_file_thread_object.valid:

                # assign the loaded circuit
                self.new_project_now(create_default_diagrams=False)
                self.circuit = self.open_file_thread_object.circuit
                self.file_name = self.open_file_thread_object.file_name

                if self.circuit.has_diagrams():
                    # create the diagrams that came with the file
                    self.create_circuit_stored_diagrams()

                else:
                    if self.circuit.get_bus_number() > 1500:
                        quit_msg = "The grid is quite large, hence the schematic might be slow.\n" \
                                   "Do you want to enable the schematic?\n" \
                                   "(you can always enable the drawing later)"
                        reply = QtWidgets.QMessageBox.question(self, 'Enable schematic', quit_msg,
                                                               QtWidgets.QMessageBox.StandardButton.Yes,
                                                               QtWidgets.QMessageBox.StandardButton.No)

                        if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
                            # create schematic
                            self.add_complete_bus_branch_diagram()

                    else:
                        pass
                        # create schematic
                        self.add_complete_bus_branch_diagram()

                # set base magnitudes
                self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
                self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)

                # set circuit comments
                try:
                    self.ui.comments_textEdit.setText(str(self.circuit.comments))
                except:
                    pass

                # update the drop-down menus that display dates
                self.update_date_dependent_combos()
                self.update_area_combos()

                # get the session tree structure
                session_data_dict = self.open_file_thread_object.get_session_tree()
                mdl = gf.get_tree_model(session_data_dict, 'Sessions')
                self.ui.diskSessionsTreeView.setModel(mdl)

                # apply the GUI settings if found:
                gui_config_data = self.open_file_thread_object.json_files.get('gui_config', None)
                if gui_config_data is not None:
                    self.apply_gui_config(data=gui_config_data)

                # clear the results
                self.clear_results()

                self.ui.grid_name_line_edit.setText(self.circuit.name)

                # if this was a cgmes file, launch the roseta GUI
                if self.open_file_thread_object.cgmes_circuit:
                    # if there is a CGMES file, show Rosetta and the loguer there
                    self.rosetta_gui = RosetaExplorerGUI()
                    self.rosetta_gui.set_grid_model(self.open_file_thread_object.cgmes_circuit)
                    self.rosetta_gui.set_logger(self.open_file_thread_object.cgmes_logger)
                    self.rosetta_gui.update_combo_boxes()
                    self.rosetta_gui.show()

                else:
                    # else, show the logger if it is necessary
                    if len(self.open_file_thread_object.logger) > 0:
                        dlg = LogsDialogue('Open file logger', self.open_file_thread_object.logger)
                        dlg.exec_()

            else:
                warn('The file was not valid')
        else:
            # center nodes
            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, DiagramEditorWidget):
                    diagram.center_nodes()

        self.collect_memory()
        self.setup_time_sliders()

    def add_circuit(self):
        """
        Prompt to add another circuit
        """
        self.open_file_threaded(post_function=self.post_add_circuit)

    def post_add_circuit(self):
        """
        Stuff to do after opening another circuit
        :return: Nothing
        """
        self.stuff_running_now.remove('file_open')

        if self.open_file_thread_object is not None:

            if len(self.open_file_thread_object.logger) > 0:
                dlg = LogsDialogue('Open file logger', self.open_file_thread_object.logger)
                dlg.exec_()

            if self.open_file_thread_object.valid:

                if self.circuit.get_bus_number() == 0:
                    # load the circuit
                    self.stuff_running_now.append('file_open')
                    self.post_open_file()
                else:
                    # add the circuit
                    new_circuit = self.open_file_thread_object.circuit
                    buses = self.circuit.add_circuit(new_circuit)

                    dlg = CustomQuestionDialogue(title="Add new grid",
                                                 question="Do you want to add the loaded grid to a new diagram?",
                                                 answer1="Add to new diagram",
                                                 answer2="Add to current diagram")
                    dlg.exec_()

                    if dlg.accepted_answer == 1:
                        diagram_widget = self.add_complete_bus_branch_diagram_now(name=new_circuit.name)
                    elif dlg.accepted_answer == 2:
                        diagram_widget = self.get_selected_diagram_widget()
                    else:
                        return

                    # add to schematic
                    if diagram_widget is not None:
                        if isinstance(diagram_widget, DiagramEditorWidget):
                            injections_by_bus = self.circuit.get_injection_devices_grouped_by_bus()
                            injections_by_fluid_node = self.circuit.get_injection_devices_grouped_by_fluid_node()
                            diagram_widget.add_elements_to_schematic(buses=new_circuit.buses,
                                                                     lines=new_circuit.lines,
                                                                     dc_lines=new_circuit.dc_lines,
                                                                     transformers2w=new_circuit.transformers2w,
                                                                     transformers3w=new_circuit.transformers3w,
                                                                     hvdc_lines=new_circuit.hvdc_lines,
                                                                     vsc_devices=new_circuit.vsc_devices,
                                                                     upfc_devices=new_circuit.upfc_devices,
                                                                     fluid_nodes=new_circuit.fluid_nodes,
                                                                     fluid_paths=new_circuit.fluid_paths,
                                                                     injections_by_bus=injections_by_bus,
                                                                     injections_by_fluid_node=injections_by_fluid_node,
                                                                     explode_factor=1.0,
                                                                     prog_func=None,
                                                                     text_func=None)
                            diagram_widget.set_selected_buses(buses=buses)

    def save_file_as(self):
        """
        Save this file as...
        """
        # by deleting the file_name, the save_file function will ask for it
        self.file_name = ''
        self.save_file()

    def save_file(self):
        """
        Save the circuit case to a file
        """
        # declare the allowed file types
        files_types = ("GridCal zip (*.gridcal);;"
                       "GridCal HDF5 (*.gch5);;"
                       "Excel (*.xlsx);;"
                       "CIM (*.xml);;"
                       "Electrical Json V3 (*.ejson3);;"
                       "Rawx (*.rawx);;"
                       "Sqlite (*.sqlite);;")

        if NEWTON_PA_AVAILABLE:
            files_types += "Newton (*.newton);;"

        if PGM_AVAILABLE:
            files_types += "PGM Json (*.pgm);;"

        # call dialog to select the file
        if self.project_directory is None:
            self.project_directory = ''

        # gather comments
        self.circuit.comments = self.ui.comments_textEdit.toPlainText()

        if self.file_name == '':
            # if the global file_name is empty, ask where to save
            fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

            if filename != '':

                # if the user did not enter the extension, add it automatically
                name, file_extension = os.path.splitext(filename)

                extension = dict()
                extension['Excel (*.xlsx)'] = '.xlsx'
                extension['CIM (*.xml)'] = '.xml'
                extension['Electrical Json V2 (*.ejson2)'] = '.ejson2'
                extension['Electrical Json V3 (*.ejson3)'] = '.ejson3'
                extension['GridCal zip (*.gridcal)'] = '.gridcal'
                extension['PSSe rawx (*.rawx)'] = '.rawx'
                extension['GridCal HDF5 (*.gch5)'] = '.gch5'
                extension['Sqlite (*.sqlite)'] = '.sqlite'
                extension['Newton (*.newton)'] = '.newton'
                extension['PGM Json (*.pgm)'] = '.pgm'

                if file_extension == '':
                    filename = name + extension[type_selected]

                # we were able to compose the file correctly, now save it
                self.file_name = filename
                self.save_file_now(self.file_name)
        else:
            # save directly
            self.save_file_now(self.file_name)

    def get_file_save_options(self) -> filedrv.FileSavingOptions:
        """
        Compose the file saving options
        :return: FileSavingOptions
        """

        if self.ui.saveResultsCheckBox.isChecked():
            sessions = [self.session]
        else:
            sessions = list()

        # get json files to store
        json_files = {"gui_config": self.get_gui_config_data()}

        options = filedrv.FileSavingOptions(cgmes_boundary_set=self.current_boundary_set,
                                            simulation_drivers=self.get_simulations(),
                                            sessions=sessions,
                                            dictionary_of_json_files=json_files)

        return options

    def save_file_now(self, filename):
        """
        Save the file right now, without questions
        :param filename: filename to save to
        """

        if ('file_save' not in self.stuff_running_now) and ('file_open' not in self.stuff_running_now):
            # lock the ui
            self.LOCK()

            # check to not to kill threads avoiding segmentation faults
            if self.save_file_thread_object is not None:
                if self.save_file_thread_object.isRunning():
                    ok = yes_no_question("There is a saving procedure running.\nCancel and retry?")
                    if ok:
                        self.save_file_thread_object.quit()

            self.save_file_thread_object = filedrv.FileSaveThread(circuit=self.circuit,
                                                                  file_name=filename,
                                                                  options=self.get_file_save_options())

            # make connections
            self.save_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
            self.save_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
            self.save_file_thread_object.done_signal.connect(self.UNLOCK)
            self.save_file_thread_object.done_signal.connect(self.post_file_save)

            # thread start
            self.save_file_thread_object.start()

            # register as the latest file driver
            self.last_file_driver = self.save_file_thread_object

            self.stuff_running_now.append('file_save')

        else:
            warning_msg('There is a file being processed..')

    def post_file_save(self):
        """
        Actions after the threaded file save
        """
        if self.save_file_thread_object.logger is not None:
            if len(self.save_file_thread_object.logger) > 0:
                dlg = LogsDialogue('Save file logger', self.save_file_thread_object.logger)
                dlg.exec_()

        self.stuff_running_now.remove('file_save')

        self.ui.model_version_label.setText('Model v. ' + str(self.circuit.model_version))

        # get the session tree structure
        session_data_dict = self.save_file_thread_object.get_session_tree()
        mdl = gf.get_tree_model(session_data_dict, 'Sessions')
        self.ui.diskSessionsTreeView.setModel(mdl)

        # call the garbage collector to free memory
        self.collect_memory()

    def grid_generator(self):
        """
        Open the grid generator window
        """
        self.grid_generator_dialogue = GridGeneratorGUI(parent=self)
        self.grid_generator_dialogue.resize(int(1.61 * 600.0), 550)  # golden ratio
        self.grid_generator_dialogue.exec_()

        if self.grid_generator_dialogue.applied:

            if self.circuit.get_bus_number() > 0:
                reply = QtWidgets.QMessageBox.question(self, 'Message',
                                                       'Are you sure that you want to delete '
                                                       'the current grid and replace it?',
                                                       QtWidgets.QMessageBox.StandardButton.Yes,
                                                       QtWidgets.QMessageBox.StandardButton.No)

                if reply == QtWidgets.QMessageBox.StandardButton.No:
                    return

            self.circuit = self.grid_generator_dialogue.circuit

            # create schematic
            self.redraw_current_diagram()

            # set circuit name
            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, DiagramEditorWidget):
                    diagram.name.setText(f"Random grid {self.circuit.get_bus_number()} buses")

            # set base magnitudes
            self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
            self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)
            self.ui.model_version_label.setText(f"Model v. {self.circuit.model_version}")

            # set circuit comments
            self.ui.comments_textEdit.setText("Grid generated randomly using the RPGM algorithm.")

            # update the drop down menus that display dates
            self.update_date_dependent_combos()
            self.update_area_combos()

            # clear the results
            self.clear_results()

    def import_bus_coordinates(self):
        """

        :return:
        """
        self.coordinates_window = CoordinatesInputGUI(self, self.circuit.get_buses())
        self.coordinates_window.exec_()
        self.set_xy_from_lat_lon()

    def export_object_profiles(self):
        """
        Export object profiles
        """
        if self.circuit.time_profile is not None:

            # declare the allowed file types
            files_types = "Excel file (*.xlsx)"
            # call dialog to select the file
            if self.project_directory is None:
                self.project_directory = ''

            fname = os.path.join(self.project_directory, 'profiles of ' + self.ui.grid_name_line_edit.text())

            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

            if filename != "":
                if not filename.endswith('.xlsx'):
                    filename += '.xlsx'
                # TODO: correct this function
                self.circuit.export_profiles(file_name=filename)
        else:
            warning_msg('There are no profiles!', 'Export object profiles')

    def export_all(self):
        """
        Export all the results
        :return:
        """

        available_results = self.get_available_results()

        if len(available_results) > 0:

            files_types = "Zip file (*.zip)"
            fname = os.path.join(self.project_directory, 'Results of ' + self.ui.grid_name_line_edit.text())

            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

            if filename != "":
                self.LOCK()

                self.stuff_running_now.append('export_all')
                self.export_all_thread_object = exprtdrv.ExportAllThread(circuit=self.circuit,
                                                                         simulations_list=available_results,
                                                                         file_name=filename)

                self.export_all_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
                self.export_all_thread_object.progress_text.connect(self.ui.progress_label.setText)
                self.export_all_thread_object.done_signal.connect(self.post_export_all)
                self.export_all_thread_object.start()
        else:
            warning_msg('There are no result available :/')

    def post_export_all(self):
        """
        Actions post export all
        """
        self.stuff_running_now.remove('export_all')

        if self.export_all_thread_object is not None:
            if self.export_all_thread_object.logger.has_logs():
                dlg = LogsDialogue('Export all', self.export_all_thread_object.logger)
                dlg.exec_()

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def export_simulation_data(self):
        """
        Export the calculation objects to file
        """

        # declare the allowed file types
        files_types = "Excel file (*.xlsx)"
        # call dialog to select the file
        if self.project_directory is None:
            self.project_directory = ''

        fname = os.path.join(self.project_directory, self.ui.grid_name_line_edit.text())

        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

        if filename != "":
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'

            numerical_circuit = compile_numerical_circuit_at(circuit=self.circuit)
            calculation_inputs = numerical_circuit.split_into_islands()

            with pd.ExcelWriter(filename) as writer:  # pylint: disable=abstract-class-instantiated

                for c, calc_input in enumerate(calculation_inputs):

                    for elm_type in calc_input.available_structures:
                        name = elm_type + '_' + str(c)
                        df = calc_input.get_structure(elm_type).astype(str)
                        df.to_excel(writer, name)

    def load_results_driver(self):
        """
        Load a driver from disk
        """
        idx = self.ui.diskSessionsTreeView.selectedIndexes()
        if len(idx) > 0:
            tree_mdl = self.ui.diskSessionsTreeView.model()
            item = tree_mdl.itemFromIndex(idx[0])
            path = gf.get_tree_item_path(item)

            if len(path) > 1:
                session_name = path[0]
                study_name = path[1]
                if self.last_file_driver is not None:
                    data_dict, json_files = self.last_file_driver.load_session_objects(session_name=session_name,
                                                                                       study_name=study_name)

                    self.session.register_driver_from_disk_data(self.circuit, study_name, data_dict)

                    self.update_available_results()
                else:
                    error_msg('No file driver declared :/')
            else:
                info_msg('Select a driver inside a session', 'Driver load from disk')

    def import_contingencies(self):
        """
        Open file to import contingencies file
        """

        files_types = "Formats (*.json)"

        # call dialog to select the file

        filenames, type_selected = QtWidgets.QFileDialog.getOpenFileNames(parent=self,
                                                                          caption='Open file',
                                                                          dir=self.project_directory,
                                                                          filter=files_types)

        if len(filenames) == 1:
            contingencies = import_contingencies_from_json(filenames[0])
            logger = self.circuit.set_contingencies(contingencies=contingencies)

            if len(logger) > 0:
                dlg = LogsDialogue('Contingencies import', logger)
                dlg.exec_()

    def export_contingencies(self):
        """
        Export contingencies
        :return:
        """
        if len(self.circuit.contingencies) > 0:

            # declare the allowed file types
            files_types = "JSON file (*.json)"

            # call dialog to select the file
            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', '', files_types)

            if not (filename.endswith('.json')):
                filename += ".json"

            if filename != "":
                # save file
                export_contingencies_json_file(circuit=self.circuit, file_path=filename)
