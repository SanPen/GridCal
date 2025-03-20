# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import asyncio
from typing import Union, List, Callable
import pandas as pd
from PySide6 import QtWidgets

import GridCal.Gui.gui_functions as gf
import GridCal.Session.export_results_driver as exprtdrv
import GridCal.Session.file_handler as filedrv
from GridCal.Gui.GridMerge.grid_diff import GridDiffDialogue
from GridCal.Gui.GridMerge.grid_merge import GridMergeDialogue
from GridCal.plugins import install_plugin, get_plugin_info
from GridCal.Gui.CoordinatesInput.coordinates_dialogue import CoordinatesInputGUI
from GridCal.Gui.general_dialogues import LogsDialogue, CustomQuestionDialogue
from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg, info_msg
from GridCal.Gui.GridGenerator.grid_generator_dialogue import GridGeneratorGUI
from GridCal.Gui.RosetaExplorer.RosetaExplorer import RosetaExplorerGUI
from GridCal.Gui.Main.SubClasses.Settings.configuration import ConfigurationMain

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_newton_pa import NEWTON_PA_AVAILABLE
from GridCalEngine.Compilers.circuit_to_pgm import PGM_AVAILABLE
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.enumerations import CGMESVersions, SimulationTypes
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.contingency_parser import import_contingencies_from_json, export_contingencies_json_file
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile
from GridCalEngine.IO.gridcal.remote import RemoteInstruction
from GridCalEngine.IO.gridcal.catalogue import save_catalogue, load_catalogue
from GridCal.templates import (get_cables_catalogue, get_transformer_catalogue, get_wires_catalogue,
                               get_sequence_lines_catalogue)


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

        self.accepted_extensions = ['.gridcal', '.dgridcal', '.xlsx', '.xls', '.sqlite', '.gch5',
                                    '.dgs', '.m', '.raw', '.RAW', '.json', '.uct',
                                    '.ejson2', '.ejson3', '.p', '.nc', '.hdf5',
                                    '.xml', '.rawx', '.zip', '.dpx', '.epc', '.EPC',
                                    '.gcplugin']

        self.cgmes_version_dict = {x.value: x for x in [CGMESVersions.v2_4_15,
                                                        CGMESVersions.v3_0_0]}
        self.ui.cgmes_version_comboBox.setModel(gf.get_list_model(list(self.cgmes_version_dict.keys())))

        self.cgmes_profiles_dict = {x.value: x for x in [cgmesProfile.EQ,
                                                         cgmesProfile.OP,
                                                         cgmesProfile.SC,
                                                         cgmesProfile.TP,
                                                         cgmesProfile.SV,
                                                         cgmesProfile.SSH,
                                                         cgmesProfile.DY,
                                                         cgmesProfile.DL,
                                                         cgmesProfile.GL]}
        self.ui.cgmes_profiles_listView.setModel(gf.get_list_model(list(self.cgmes_profiles_dict.keys()),
                                                                   checks=True, check_value=True))

        self.ui.raw_export_version_comboBox.addItems(["33", "35"])

        self.ui.actionNew_project.triggered.connect(self.new_project)
        self.ui.actionOpen_file.triggered.connect(self.open_file)
        self.ui.actionAdd_circuit.triggered.connect(self.import_circuit)
        self.ui.actionExport_circuit_differential.triggered.connect(self.export_circuit_differential)
        self.ui.actionSave.triggered.connect(self.save_file)
        self.ui.actionSave_as.triggered.connect(self.save_file_as)
        self.ui.actionExport_all_the_device_s_profiles.triggered.connect(self.export_object_profiles)
        self.ui.actionExport_all_results.triggered.connect(self.export_all)
        self.ui.actiongrid_Generator.triggered.connect(self.grid_generator)
        self.ui.actionImport_bus_coordinates.triggered.connect(self.import_bus_coordinates)
        self.ui.actionImport_contingencies.triggered.connect(self.import_contingencies)
        self.ui.actionExport_contingencies.triggered.connect(self.export_contingencies)
        self.ui.actionAdd_default_catalogue.triggered.connect(self.add_default_catalogue)
        self.ui.actionAdd_custom_catalogue.triggered.connect(self.load_custom_catalogue)
        self.ui.actionExportCatalogue.triggered.connect(self.save_custom_catalogue)

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

                any_grid_delta = False
                any_normal_grid = False

                for event in events:
                    file_name = event.toLocalFile()
                    name, file_extension = os.path.splitext(file_name)
                    if file_extension.lower() in self.accepted_extensions:
                        file_names.append(file_name)

                        if file_name.endswith('.dgridcal'):
                            any_grid_delta = True
                        elif file_name.endswith('.gcplugin'):
                            self.install_plugin_now(file_name)
                            return
                        else:
                            any_normal_grid = True

                    else:
                        error_msg('The file type ' + file_extension.lower() + ' is not accepted :(')

                if self.circuit.valid_for_simulation() > 0:

                    if any_grid_delta and not any_normal_grid:
                        # only grid deltas...
                        self.open_file_now(filenames=file_names,
                                           post_function=self.post_import_circuit)
                    else:
                        quit_msg = ("Are you sure that you want to quit the current grid and open a new one?"
                                    "\n If the process is cancelled the grid will remain.")
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

        self.setup_objects_tree()

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

        if create_default_diagrams:
            self.add_complete_bus_branch_diagram()
            self.add_map_diagram(ask=False)
            self.set_diagram_widget(self.diagram_widgets_list[0])

        self.collect_memory()

    def new_project(self):
        """
        Create new grid
        :return:
        """
        if self.circuit.valid_for_simulation() > 0:
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
            if self.circuit.valid_for_simulation() > 0:
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

    def open_file_threaded(self, post_function=None,
                           allow_diff_file_format: bool = False,
                           title: str = 'Open file'):
        """
        Open file from a Qt thread to remain responsive
        :param post_function: Any function to run after
        :param allow_diff_file_format: Allow loading GridCal diff files?
        :param title: Title of the open window
        """

        files_types = "*.gridcal "

        if allow_diff_file_format:
            files_types += "*.dgridcal "

        files_types += "*.gch5 *.xlsx *.xls *.sqlite *.dgs "
        files_types += "*.m *.raw *.RAW *.rawx *.uct *.json *.ejson2 *.ejson3 *.xml "
        files_types += "*.zip *.dpx *.epc *.EPC *.nc *.hdf5 *.p"

        dialogue = QtWidgets.QFileDialog(None,
                                         caption=title,
                                         directory=self.project_directory,
                                         filter=f"Formats ({files_types})")

        if dialogue.exec():
            filenames = dialogue.selectedFiles()
            self.open_file_now(filenames, post_function)

    def open_file_now(self, filenames: Union[str, List[str]],
                      post_function: Union[None, Callable[[], None]] = None) -> None:
        """
        Open a file without questions
        :param filenames: list of file names (maybe more than one because of CIM TP and EQ files)
        :param post_function: function callback
        :return: Nothing
        """
        if len(filenames) > 0:

            for f_name in filenames:
                if not os.path.exists(f_name):
                    error_msg(text=f"The file does not exists :(\n{f_name}", title="File opening")
                    return

            self.file_name = filenames[0]

            # store the working directory
            self.project_directory = os.path.dirname(self.file_name)

            # lock the ui
            self.LOCK()

            # create thread
            self.open_file_thread_object = filedrv.FileOpenThread(
                file_name=filenames if len(filenames) > 1 else filenames[0],
                previous_circuit=self.circuit,
                options=self.get_file_open_options()
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
                if self.open_file_thread_object.circuit is not None:
                    self.circuit = self.open_file_thread_object.circuit
                    self.file_name = self.open_file_thread_object.file_name

                if self.circuit.has_diagrams():
                    # create the diagrams that came with the file
                    # task = gf.AsyncTask(self.create_circuit_stored_diagrams)
                    # self.task_pool.start(task)
                    self.create_circuit_stored_diagrams()

                else:
                    if self.circuit.get_bus_number() > 300:
                        # quit_msg = ("The grid is quite large, hence the schematic might be slow.\n"
                        #             "Do you want to enable the schematic?\n"
                        #             "(you can always enable the drawing later)")
                        # reply = QtWidgets.QMessageBox.question(self, 'Enable schematic', quit_msg,
                        #                                        QtWidgets.QMessageBox.StandardButton.Yes,
                        #                                        QtWidgets.QMessageBox.StandardButton.No)
                        #
                        # if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
                        #     # create schematic
                        #     self.add_complete_bus_branch_diagram()
                        info_msg(text="The circuit has too many buses for an efficient diagram."
                                      "You can create diagrams and maps for parts of the circuit "
                                      "(or even the complete circuit) by going into the database "
                                      "and creating diagrams from there",
                                 title="The grid is quite big...")

                    else:
                        # create schematic
                        self.add_complete_bus_branch_diagram()

                # set base magnitudes
                self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
                self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)

                # set circuit comments
                try:
                    self.ui.comments_textEdit.setText(str(self.circuit.comments))
                except ValueError:
                    pass

                # update the drop-down menus that display dates
                self.update_date_dependent_combos()
                self.update_from_to_list_views()

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

                # if this was a CGMES file, launch the Rosetta GUI
                if self.open_file_thread_object.cgmes_circuit:

                    show_rosetta = yes_no_question(title="Show rosetta",
                                                   text="Do you want to open the Rosetta CGMEs browser?")

                    if show_rosetta:
                        self.rosetta_gui = RosetaExplorerGUI()
                        self.rosetta_gui.set_grid_model(self.open_file_thread_object.cgmes_circuit)
                        self.rosetta_gui.set_logger(self.open_file_thread_object.cgmes_logger)
                        self.rosetta_gui.update_combo_boxes()
                        self.rosetta_gui.show()

                else:
                    # else, show the logger if it is necessary
                    if len(self.open_file_thread_object.logger) > 0:
                        dlg = LogsDialogue('Open file logger', self.open_file_thread_object.logger)
                        dlg.exec()

            else:
                warning_msg(text='Error while loading the file(s)')
                # else, show the logger if it is necessary
                if len(self.open_file_thread_object.logger) > 0:
                    dlg = LogsDialogue('Open file logger', self.open_file_thread_object.logger)
                    dlg.exec()
        else:
            # center nodes
            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, SchematicWidget):
                    diagram.center_nodes()

        self.collect_memory()
        self.setup_time_sliders()
        self.get_circuit_snapshot_datetime()
        self.change_theme_mode()

    def install_plugin_now(self, fname: str):
        """
        Install plugin
        :param fname: name of the plugin
        """
        if fname.endswith('.gcplugin'):
            info = get_plugin_info(fname)

            if info is not None:

                if not info.is_compatible():
                    error_msg(f"{info.name} {info.version} requires GridCal {info.gridcal_version}",
                              "Plugin install")
                    return

                # search for the plugin
                for key, plugin in self.plugins_info.plugins.items():
                    if plugin.name == info.name:

                        ok = yes_no_question(f"There is a plugin already: "
                                             f"{plugin.name} {plugin.version} "
                                             f"The new plugin is {info.version}. "
                                             f"Install?", "Plugin install")
                        if not ok:
                            return
                        else:
                            break

                install_plugin(fname)
                self.add_plugins()
                info_msg(f"{info.name} {info.version} installed!", "Plugin install")
            else:
                error_msg("There is no manifest :(", "Plugin install")
        else:
            error_msg("Does not seem to be a plugin :/", "Plugin install")

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

    def import_circuit(self):
        """
        Prompt to add another circuit
        """
        self.open_file_threaded(post_function=self.post_import_circuit,
                                allow_diff_file_format=True)

    def post_import_circuit(self):
        """
        Stuff to do after opening another circuit
        :return: Nothing
        """
        self.stuff_running_now.remove('file_open')

        if self.open_file_thread_object is not None:

            new_circuit = self.open_file_thread_object.circuit

            if len(self.open_file_thread_object.logger) > 0:
                dlg = LogsDialogue('Open file logger',
                                   self.open_file_thread_object.logger)
                dlg.exec()

            if self.open_file_thread_object.valid:

                merge_dlg = GridMergeDialogue(grid=self.circuit, diff=new_circuit)
                merge_dlg.exec_()

                if merge_dlg.added_grid:
                    # Create a blank diagram and add to it
                    # logger = self.circuit.add_circuit(new_circuit)

                    # for sure, we want to add to the current schematic
                    diagram_widget = self.get_selected_diagram_widget()

                elif merge_dlg.merged_grid:

                    dlg3 = CustomQuestionDialogue(title="Grid merge",
                                                  question="How do you want to represent the merged grid?",
                                                  answer1="Create new diagram",
                                                  answer2="Add to current diagram")
                    dlg3.exec()

                    if dlg3.accepted_answer == 1:
                        # Create a blank diagram and add to it
                        diagram_widget = self.create_blank_schematic_diagram(name=new_circuit.name)

                    elif dlg3.accepted_answer == 2:
                        diagram_widget = self.get_selected_diagram_widget()

                    else:
                        # not imported
                        return

                    if diagram_widget is not None:
                        if isinstance(diagram_widget, SchematicWidget):
                            injections_by_bus = new_circuit.get_injection_devices_grouped_by_bus()
                            injections_by_fluid_node = new_circuit.get_injection_devices_grouped_by_fluid_node()
                            injections_by_cn = new_circuit.get_injection_devices_grouped_by_cn()
                            diagram_widget.add_elements_to_schematic(buses=new_circuit.buses,
                                                                     connectivity_nodes=new_circuit.connectivity_nodes,
                                                                     busbars=new_circuit.bus_bars,
                                                                     lines=new_circuit.lines,
                                                                     dc_lines=new_circuit.dc_lines,
                                                                     transformers2w=new_circuit.transformers2w,
                                                                     transformers3w=new_circuit.transformers3w,
                                                                     hvdc_lines=new_circuit.hvdc_lines,
                                                                     vsc_devices=new_circuit.vsc_devices,
                                                                     upfc_devices=new_circuit.upfc_devices,
                                                                     switches=new_circuit.switch_devices,
                                                                     fluid_nodes=new_circuit.fluid_nodes,
                                                                     fluid_paths=new_circuit.fluid_paths,
                                                                     injections_by_bus=injections_by_bus,
                                                                     injections_by_fluid_node=injections_by_fluid_node,
                                                                     injections_by_cn=injections_by_cn,
                                                                     explode_factor=1.0,
                                                                     prog_func=None,
                                                                     text_func=None)
                            diagram_widget.set_selected_buses(buses=new_circuit.buses)
                        else:
                            info_msg("No schematic diagram was selected...", title="Add to current diagram")

                else:
                    return



    def export_circuit_differential(self):
        """
        Prompt to export a diff of this circuit and a base one
        """
        # check that this circuit is ok
        # logger = Logger()
        # _, ok = self.circuit.get_all_elements_dict(logger=logger)
        #
        # if ok:
        #     self.open_file_threaded(post_function=self.post_create_circuit_differential,
        #                             allow_diff_file_format=True,
        #                             title="Load base grid to compare...")
        # else:
        #     dlg = LogsDialogue('This circuit has duplicated idtags :(', logger)
        #     dlg.exec()

        dlg = GridDiffDialogue(grid=self.circuit)
        dlg.exec()


    # def post_create_circuit_differential(self):
    #     """
    #
    #     :return:
    #     """
    #     self.stuff_running_now.remove('file_open')
    #
    #     if self.open_file_thread_object is not None:
    #
    #         if self.open_file_thread_object.logger.has_logs():
    #             dlg = LogsDialogue('Open file logger', self.open_file_thread_object.logger)
    #             dlg.exec()
    #
    #         if self.open_file_thread_object.valid:
    #
    #             if not self.circuit.valid_for_simulation():
    #                 # load the circuit right away
    #                 self.stuff_running_now.append('file_open')
    #                 self.post_open_file()
    #             else:
    #                 # diff the circuit
    #                 new_circuit = self.open_file_thread_object.circuit
    #
    #                 dict_logger = Logger()
    #                 _, dict_ok = new_circuit.get_all_elements_dict(logger=dict_logger)
    #
    #                 if dict_ok:
    #                     # create the differential
    #                     ok, diff_logger, dgrid = self.circuit.differentiate_circuits(new_circuit)
    #
    #                     if diff_logger.has_logs():
    #                         dlg = LogsDialogue('Grid differences', diff_logger)
    #                         dlg.exec()
    #
    #                     # select the file to save
    #                     filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file',
    #                                                                                     dgrid.name,
    #                                                                                     "GridCal diff (*.dgridcal)")
    #
    #                     if filename != '':
    #
    #                         # if the user did not enter the extension, add it automatically
    #                         name, file_extension = os.path.splitext(filename)
    #
    #                         if file_extension == '':
    #                             filename = name + ".dgridcal"
    #
    #                         # we were able to compose the file correctly, now save it
    #                         self.save_file_now(filename=filename,
    #                                            type_selected=type_selected,
    #                                            grid=dgrid)
    #                 else:
    #                     dlg = LogsDialogue('The base circuit has duplicated idtags :(', dict_logger)
    #                     dlg.exec()

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

        if self.server_driver.is_running():
            instruction = RemoteInstruction(operation=SimulationTypes.NoSim)
            self.server_driver.send_job(grid=self.circuit, instruction=instruction)

        else:
            # declare the allowed file types
            files_types = ("GridCal zip (*.gridcal);;"
                           "GridCal HDF5 (*.gch5);;"
                           "Excel (*.xlsx);;"
                           "CGMES (*.zip);;"
                           "CIM (*.xml);;"
                           "Electrical Json V3 (*.ejson3);;"
                           "Raw (*.raw);;"
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
                    extension['CGMES (*.zip)'] = '.zip'
                    extension['Electrical Json V2 (*.ejson2)'] = '.ejson2'
                    extension['Electrical Json V3 (*.ejson3)'] = '.ejson3'
                    extension['GridCal zip (*.gridcal)'] = '.gridcal'
                    extension['Raw (*.raw)'] = '.raw'
                    extension['Rawx (*.rawx)'] = '.rawx'
                    extension['GridCal HDF5 (*.gch5)'] = '.gch5'
                    extension['Sqlite (*.sqlite)'] = '.sqlite'
                    extension['Newton (*.newton)'] = '.newton'
                    extension['PGM Json (*.pgm)'] = '.pgm'

                    if file_extension == '':
                        filename = name + extension[type_selected]

                    # we were able to compose the file correctly, now save it
                    self.file_name = filename
                    self.save_file_now(self.file_name, type_selected=type_selected)
            else:
                # save directly
                self.save_file_now(self.file_name)

    def get_file_save_options(self) -> filedrv.FileSavingOptions:
        """
        Compose the file saving options
        :return: FileSavingOptions
        """

        if self.ui.saveResultsCheckBox.isChecked():
            sessions_data = self.session.get_save_data()
        else:
            sessions_data = list()

        # get json files to store
        json_files = {"gui_config": self.get_gui_config_data()}

        cgmes_version = self.cgmes_version_dict[self.ui.cgmes_version_comboBox.currentText()]

        cgmes_profiles_txt = gf.get_checked_values(mdl=self.ui.cgmes_profiles_listView.model())
        cgmes_profiles = [self.cgmes_profiles_dict[e] for e in cgmes_profiles_txt]

        one_file_per_profile = self.ui.cgmes_single_profile_per_file_checkBox.isChecked()

        cgmes_map_areas_like_raw = self.ui.cgmes_map_regions_like_raw_checkBox.isChecked()

        raw_version = self.ui.raw_export_version_comboBox.currentText()

        options = filedrv.FileSavingOptions(cgmes_boundary_set=self.current_boundary_set,
                                            simulation_drivers=self.get_simulations(),
                                            sessions_data=sessions_data,
                                            dictionary_of_json_files=json_files,
                                            cgmes_version=cgmes_version,
                                            cgmes_profiles=cgmes_profiles,
                                            cgmes_one_file_per_profile=one_file_per_profile,
                                            cgmes_map_areas_like_raw=cgmes_map_areas_like_raw,
                                            raw_version=raw_version)

        return options

    def get_file_open_options(self) -> filedrv.FileOpenOptions:
        """
        Compose the file open options
        :return: FileOpenOptions
        """

        cgmes_map_areas_like_raw = self.ui.cgmes_map_regions_like_raw_checkBox.isChecked()
        try_to_map_dc_to_hvdc_line = self.ui.cgmes_dc_as_hvdclines_checkBox.isChecked()

        options = filedrv.FileOpenOptions(cgmes_map_areas_like_raw=cgmes_map_areas_like_raw,
                                          try_to_map_dc_to_hvdc_line=try_to_map_dc_to_hvdc_line)

        return options

    def save_file_now(self, filename: str, type_selected: str = "", grid: Union[MultiCircuit, None] = None):
        """
        Save the file right now, without questions
        :param filename: filename to save to
        :param type_selected: File type description as it appears
                              in the file saving dialogue i.e. GridCal zip (*.gridcal)
        :param grid: MultiCircuit or None, if None, self.circuit is taken
        """

        if ('file_save' not in self.stuff_running_now) and ('file_open' not in self.stuff_running_now):
            # lock the ui
            self.LOCK()

            # check not to kill threads avoiding segmentation faults
            if self.save_file_thread_object is not None:
                if self.save_file_thread_object.isRunning():
                    ok = yes_no_question("There is a saving procedure running.\nCancel and retry?")
                    if ok:
                        self.save_file_thread_object.quit()

            options = self.get_file_save_options()
            options.type_selected = type_selected

            self.save_file_thread_object = filedrv.FileSaveThread(circuit=self.circuit if grid is None else grid,
                                                                  file_name=filename,
                                                                  options=options)

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
                dlg.exec()

        self.stuff_running_now.remove('file_save')

        self.ui.model_version_label.setText('Model v. ' + str(self.circuit.model_version))
        self.ui.grid_idtag_label.setText('idtag. ' + str(self.circuit.idtag))

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
        self.grid_generator_dialogue.exec()

        if self.grid_generator_dialogue.applied:

            if self.circuit.valid_for_simulation() > 0:
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
                if isinstance(diagram, SchematicWidget):
                    diagram.name.setText(f"Random grid {self.circuit.get_bus_number()} buses")

            # set base magnitudes
            self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
            self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)
            self.ui.model_version_label.setText(f"Model v. {self.circuit.model_version}")
            self.ui.grid_idtag_label.setText('idtag. ' + str(self.circuit.idtag))

            # set circuit comments
            self.ui.comments_textEdit.setText("Grid generated randomly using the RPGM algorithm.")

            # update the drop down menus that display dates
            self.update_date_dependent_combos()
            self.update_from_to_list_views()

            # clear the results
            self.clear_results()

    def import_bus_coordinates(self):
        """

        :return:
        """
        self.coordinates_window = CoordinatesInputGUI(self, self.circuit.get_buses())
        self.coordinates_window.exec()
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

        available_results = self.get_available_drivers()

        if len(available_results) > 0:

            files_types = "Zip file (*.zip)"
            fname = os.path.join(self.project_directory, 'Results of ' + self.ui.grid_name_line_edit.text())

            filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

            if filename != "":
                self.LOCK()

                self.stuff_running_now.append('export_all')
                self.export_all_thread_object = exprtdrv.ExportAllThread(circuit=self.circuit,
                                                                         drivers_list=available_results,
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
                dlg.exec()

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

                    for category, elms_in_category in calc_input.available_structures.items():
                        for elm_type in elms_in_category:
                            name = f"{category}_{elm_type}@{c}"
                            df = calc_input.get_structure(elm_type).astype(str)
                            df.to_excel(excel_writer=writer,
                                        sheet_name=name[:31])  # excel supports 31 chars per sheet name

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
                    data_dict = self.last_file_driver.load_session_objects(session_name=session_name,
                                                                           study_name=study_name)

                    logger = self.session.register_driver_from_disk_data(grid=self.circuit,
                                                                         study_name=study_name,
                                                                         data_dict=data_dict)

                    if logger.has_logs():
                        dlg = LogsDialogue(name="Results parsing", logger=logger, expand_all=True)
                        dlg.exec()

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
                dlg.exec()

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

    def add_default_catalogue(self) -> None:
        """
        Add default catalogue to circuit
        """

        self.circuit.transformer_types += get_transformer_catalogue()
        self.circuit.underground_cable_types += get_cables_catalogue()
        self.circuit.wire_types += get_wires_catalogue()
        self.circuit.sequence_line_types += get_sequence_lines_catalogue()

    def load_custom_catalogue(self):
        """
        Load a catalogue file and add it to the current one
        """
        # this will be filled with: open dialogue tab only, then connect select_csv_file from there
        """
        Open select component window for uploading catalogue data
        """

        files_types = "Catalogue file (*.xlsx)"

        filename, type_selected = QtWidgets.QFileDialog.getOpenFileName(parent=self,
                                                                        caption="Load catalogue",
                                                                        dir=self.project_directory,
                                                                        filter=files_types)

        if len(filename) > 0:
            if os.path.exists(filename):

                data, logger = load_catalogue(fname=filename)

                if logger.has_logs():
                    dlg = LogsDialogue('Open catalogue logger', logger)
                    dlg.exec()

                self.circuit.add_catalogue(data)
        else:
            return None

    def save_custom_catalogue(self):
        """
        Save the current catalogue
        """

        # declare the allowed file types
        files_types = "Catalogue file (*.xlsx)"

        # call dialog to select the file
        filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self,
                                                                        'Save catalogue', '', files_types)

        if not (filename.endswith('.xlsx')):
            filename += ".xlsx"

        if filename != "":
            save_catalogue(fname=filename, grid=self.circuit)

    def set_circuit(self, grid: MultiCircuit, create_diagram: bool = True):
        """

        :param grid:
        :param create_diagram:
        :return:
        """
        self.remove_all_diagrams()

        self.circuit = grid

        if create_diagram:
            self.add_complete_bus_branch_diagram()

        self.update_date_dependent_combos()
        self.update_from_to_list_views()
        self.clear_results()
        self.collect_memory()
        self.setup_time_sliders()
        self.get_circuit_snapshot_datetime()
        self.change_theme_mode()
