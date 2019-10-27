# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.


# GUI imports
from GridCal.__version__ import __GridCal_VERSION__
from GridCal.Gui.Main.MainWindow import *
from GridCal.Gui.GridEditorWidget import *
from GridCal.Gui.ConsoleWidget import ConsoleWidget
from GridCal.Gui.ProfilesInput.profile_dialogue import ProfileInputGUI
from GridCal.Gui.Analysis.AnalysisDialogue import GridAnalysisGUI
from GridCal.Gui.TowerBuilder.LineBuilderDialogue import TowerBuilderGUI
from GridCal.Gui.GeneralDialogues import *
from GridCal.Gui.GuiFunctions import *
from GridCal.Gui.Main.visualization import colour_the_schematic

# Engine imports
from GridCal.Engine.Simulations.Stochastic.monte_carlo_driver import *
from GridCal.Engine.Simulations.PowerFlow.time_series_driver import *
from GridCal.Engine.Simulations.Dynamics.transient_stability_driver import *
from GridCal.Engine.Simulations.ContinuationPowerFlow.voltage_collapse_driver import *
from GridCal.Engine.Simulations.Topology.topology_driver import TopologyReduction, TopologyReductionOptions, \
    DeleteAndReduce
from GridCal.Engine.Simulations.Topology.topology_driver import select_branches_to_reduce
from GridCal.Engine.grid_analysis import TimeSeriesResultsAnalysis
from GridCal.Engine.Devices import Tower, Wire, TransformerType, SequenceLineType, UndergroundLineType
from GridCal.Engine.IO.file_handler import *
from GridCal.Engine.Simulations.Stochastic.blackout_driver import *
from GridCal.Engine.Simulations.OPF.opf_driver import *
from GridCal.Engine.Simulations.PTDF.ptdf_driver import *
from GridCal.Engine.Simulations.NK.n_minus_k_driver import *
from GridCal.Engine.Simulations.OPF.opf_time_series_driver import *
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import *
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import *
from GridCal.Engine.Simulations.ShortCircuit.short_circuit_driver import *
from GridCal.Engine.IO.export_results_driver import ExportAllThread
from GridCal.Engine.Simulations.result_types import SimulationTypes

import gc
import os.path
import platform
import sys
import datetime
import codecs
from collections import OrderedDict
from multiprocessing import cpu_count
from geopy.geocoders import Nominatim
from PySide2 import QtWidgets
from matplotlib.colors import LinearSegmentedColormap

try:
    from pandas.plotting import register_matplotlib_converters

    register_matplotlib_converters()
except:
    from pandas.tseries import converter

    converter.register()

__author__ = 'Santiago Peñate Vera'

"""
This class is the handler of the main gui of GridCal.
"""


########################################################################################################################
# Main Window
########################################################################################################################


class MainGUI(QMainWindow):

    def __init__(self, parent=None, use_native_dialogues=True):
        """

        @param parent:
        """

        # create main window
        QMainWindow.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)

        self.setAcceptDrops(True)

        self.use_native_dialogues = use_native_dialogues

        # Declare circuit
        self.circuit = MultiCircuit()

        self.calculation_inputs_to_display = None

        self.project_directory = os.path.expanduser("~")

        # solvers dictionary
        self.solvers_dict = OrderedDict()
        self.solvers_dict[SolverType.NR.value] = SolverType.NR
        self.solvers_dict[SolverType.NRI.value] = SolverType.NRI
        self.solvers_dict[SolverType.IWAMOTO.value] = SolverType.IWAMOTO
        self.solvers_dict[SolverType.LM.value] = SolverType.LM
        self.solvers_dict[SolverType.FASTDECOUPLED.value] = SolverType.FASTDECOUPLED
        self.solvers_dict[SolverType.HELM.value] = SolverType.HELM
        self.solvers_dict[SolverType.LACPF.value] = SolverType.LACPF
        self.solvers_dict[SolverType.DC.value] = SolverType.DC

        lst = list(self.solvers_dict.keys())
        mdl = get_list_model(lst)
        self.ui.solver_comboBox.setModel(mdl)
        # self.ui.retry_solver_comboBox.setModel(mdl)

        self.ui.solver_comboBox.setCurrentIndex(0)
        # self.ui.retry_solver_comboBox.setCurrentIndex(3)

        mdl = get_list_model(self.circuit.profile_magnitudes.keys())
        self.ui.profile_device_type_comboBox.setModel(mdl)
        self.profile_device_type_changed()

        # reactive power controls
        self.q_control_modes_dict = OrderedDict()
        self.q_control_modes_dict['No control'] = ReactivePowerControlMode.NoControl
        self.q_control_modes_dict['Direct'] = ReactivePowerControlMode.Direct
        self.q_control_modes_dict['Iterative'] = ReactivePowerControlMode.Iterative
        lst = list(self.q_control_modes_dict.keys())
        mdl = get_list_model(lst)
        self.ui.reactive_power_control_mode_comboBox.setModel(mdl)

        # taps controls (transformer voltage regulator)
        self.taps_control_modes_dict = OrderedDict()
        self.taps_control_modes_dict['No control'] = TapsControlMode.NoControl
        self.taps_control_modes_dict['Direct'] = TapsControlMode.Direct
        self.taps_control_modes_dict['Iterative'] = TapsControlMode.Iterative
        lst = list(self.taps_control_modes_dict.keys())
        mdl = get_list_model(lst)
        self.ui.taps_control_mode_comboBox.setModel(mdl)

        # Automatic layout modes
        mdl = get_list_model(['fruchterman_reingold_layout',
                              'spectral_layout',
                              'circular_layout',
                              'random_layout',
                              'shell_layout',
                              'spring_layout'])
        self.ui.automatic_layout_comboBox.setModel(mdl)

        # list of styles
        plt_styles = plt.style.available
        self.ui.plt_style_comboBox.setModel(get_list_model(plt_styles))

        if 'fivethirtyeight' in plt_styles:
            self.ui.plt_style_comboBox.setCurrentText('fivethirtyeight')

        # branch types for reduction
        mdl = get_list_model(BranchTypeConverter(BranchType.Branch).options, checks=True)
        self.ui.removeByTypeListView.setModel(mdl)

        # opf solvers dictionary
        self.lp_solvers_dict = OrderedDict()
        self.lp_solvers_dict[SolverType.DC_OPF.value] = SolverType.DC_OPF
        self.lp_solvers_dict[SolverType.AC_OPF.value] = SolverType.AC_OPF
        self.ui.lpf_solver_comboBox.setModel(get_list_model(list(self.lp_solvers_dict.keys())))

        self.opf_time_groups = OrderedDict()
        self.opf_time_groups[TimeGrouping.NoGrouping.value] = TimeGrouping.NoGrouping
        self.opf_time_groups[TimeGrouping.Monthly.value] = TimeGrouping.Monthly
        self.opf_time_groups[TimeGrouping.Weekly.value] = TimeGrouping.Weekly
        self.opf_time_groups[TimeGrouping.Daily.value] = TimeGrouping.Daily
        self.opf_time_groups[TimeGrouping.Hourly.value] = TimeGrouping.Hourly
        self.ui.opf_time_grouping_comboBox.setModel(get_list_model(list(self.opf_time_groups.keys())))

        self.mip_solvers_dict = OrderedDict()
        self.mip_solvers_dict[MIPSolvers.CBC.value] = MIPSolvers.CBC
        self.mip_solvers_dict[MIPSolvers.CPLEX.value] = MIPSolvers.CPLEX
        self.mip_solvers_dict[MIPSolvers.GUROBI.value] = MIPSolvers.GUROBI
        self.mip_solvers_dict[MIPSolvers.XPRESS.value] = MIPSolvers.XPRESS
        self.ui.mip_solver_comboBox.setModel(get_list_model(list(self.mip_solvers_dict.keys())))

        # voltage collapse mode (full, nose)
        self.ui.vc_stop_at_comboBox.setModel(get_list_model([VCStopAt.Nose.value, VCStopAt.Full.value]))
        self.ui.vc_stop_at_comboBox.setCurrentIndex(0)

        # export modes
        mdl = get_list_model(['real', 'imag', 'abs'])
        self.ui.export_mode_comboBox.setModel(mdl)
        self.ui.export_mode_comboBox.setCurrentIndex(0)

        # do not allow MP under windows because it crashes
        if platform.system() == 'Windows':
            self.ui.use_multiprocessing_checkBox.setEnabled(False)

        ################################################################################################################
        # Declare the schematic editor
        ################################################################################################################

        # create diagram editor object
        self.ui.lat1_doubleSpinBox.setValue(60)
        self.ui.lon1_doubleSpinBox.setValue(30)
        self.ui.zoom_spinBox.setValue(5)

        lat0 = self.ui.lat1_doubleSpinBox.value()
        lon0 = self.ui.lon1_doubleSpinBox.value()
        zoom = self.ui.zoom_spinBox.value()
        self.grid_editor = GridEditor(self.circuit, lat0=lat0, lon0=lon0, zoom=zoom)

        self.ui.dataStructuresListView.setModel(get_list_model(self.grid_editor.object_types))

        self.ui.catalogueDataStructuresListView.setModel(get_list_model(self.grid_editor.catalogue_types))

        pfo = CalculationInputs(1, 1, 1, 1, 1)
        self.ui.simulationDataStructuresListView.setModel(get_list_model(pfo.available_structures))

        # add the widgets
        self.ui.schematic_layout.addWidget(self.grid_editor)
        self.grid_editor.setStretchFactor(1, 10)

        # 1:4
        self.ui.dataStructuresSplitter.setStretchFactor(0, 1)
        self.ui.dataStructuresSplitter.setStretchFactor(1, 4)

        # 4:1
        self.ui.templatesSplitter.setStretchFactor(0, 4)
        self.ui.templatesSplitter.setStretchFactor(1, 1)

        self.ui.simulationDataSplitter.setStretchFactor(1, 15)
        self.ui.catalogueSplitter.setStretchFactor(1, 15)

        self.ui.results_splitter.setStretchFactor(0, 1)
        self.ui.results_splitter.setStretchFactor(1, 4)

        self.lock_ui = False
        self.ui.progress_frame.setVisible(self.lock_ui)

        # threads
        self.power_flow = None
        self.short_circuit = None
        self.monte_carlo = None
        self.time_series = None
        self.voltage_stability = None
        self.latin_hypercube_sampling = None
        self.cascade = None
        self.optimal_power_flow = None
        self.optimal_power_flow_time_series = None
        self.transient_stability = None
        self.topology_reduction = None
        self.open_file_thread_object = None
        self.save_file_thread_object = None
        self.ptdf_analysis = None
        self.otdf_analysis = None
        self.painter = None
        self.delete_and_reduce_driver = None
        self.export_all_thread_object = None

        self.stuff_running_now = list()

        self.file_name = ''

        self.results_mdl = ResultsModel(data=np.zeros((0, 0)), columns=np.zeros(0), index=np.zeros(0))

        # list of all the objects of the selected type under the Objects tab
        self.type_objects_list = list()

        self.buses_for_storage = None

        self.available_results_dict = None
        self.available_results_steps_dict = None

        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(cpu_count())

        ################################################################################################################
        # Console
        ################################################################################################################

        self.console = ConsoleWidget(customBanner="GridCal console.\n\n"
                                                  "type hlp() to see the available specific commands.\n\n"
                                                  "the following libraries are already loaded:\n"
                                                  "np: numpy\n"
                                                  "pd: pandas\n"
                                                  "plt: matplotlib\n"
                                                  "app: This instance of GridCal\n\n")
        # add the console widget to the user interface
        self.ui.main_console_tab.layout().addWidget(self.console)

        # push some variables to the console
        self.console.push_vars({"hlp": self.print_console_help,
                                "np": np,
                                "pd": pd,
                                "plt": plt,
                                "clc": self.clc,
                                'app': self})

        ################################################################################################################
        # Connections
        ################################################################################################################
        self.ui.actionNew_project.triggered.connect(self.new_project)

        self.ui.actionOpen_file.triggered.connect(self.open_file)

        self.ui.actionSave.triggered.connect(self.save_file)

        self.ui.actionSave_as.triggered.connect(self.save_file_as)

        self.ui.actionPower_flow.triggered.connect(self.run_power_flow)

        self.ui.actionShort_Circuit.triggered.connect(self.run_short_circuit)

        self.ui.actionVoltage_stability.triggered.connect(self.run_voltage_stability)

        self.ui.actionPower_Flow_Time_series.triggered.connect(self.run_time_series)

        self.ui.actionPower_flow_Stochastic.triggered.connect(self.run_stochastic)

        self.ui.actionLatin_Hypercube_Sampling.triggered.connect(self.run_lhs)

        self.ui.actionTransient_stability.triggered.connect(self.run_transient_stability)

        self.ui.actionBlackout_cascade.triggered.connect(self.view_cascade_menu)

        self.ui.actionShow_map.triggered.connect(self.show_map)

        self.ui.actionOPF.triggered.connect(self.run_opf)

        self.ui.actionOPF_time_series.triggered.connect(self.run_opf_time_series)

        self.ui.actionAbout.triggered.connect(self.about_box)

        self.ui.actionExport.triggered.connect(self.export_diagram)

        self.ui.actionAuto_rate_branches.triggered.connect(self.auto_rate_branches)

        self.ui.actionDetect_transformers.triggered.connect(self.detect_transformers)

        self.ui.actionExport_all_power_flow_results.triggered.connect(self.export_pf_results)

        self.ui.actionExport_all_the_device_s_profiles.triggered.connect(self.export_object_profiles)

        self.ui.actionCopy_OPF_profiles_to_Time_series.triggered.connect(self.copy_opf_to_time_series)

        self.ui.actionGrid_Reduction.triggered.connect(self.reduce_grid)

        self.ui.actionStorage_location_suggestion.triggered.connect(self.storage_location)

        self.ui.actionLaunch_data_analysis_tool.triggered.connect(self.display_grid_analysis)

        self.ui.actionOnline_documentation.triggered.connect(self.show_online_docs)

        self.ui.actionExport_all_results.triggered.connect(self.export_all)

        self.ui.actionDelete_selected.triggered.connect(self.delete_selected_from_the_schematic)

        self.ui.actionPTDF.triggered.connect(self.run_ptdf)

        self.ui.actionOTDF.triggered.connect(self.run_otdf)

        # Buttons

        self.ui.cancelButton.clicked.connect(self.set_cancel_state)

        self.ui.new_profiles_structure_pushButton.clicked.connect(self.new_profiles_structure)

        self.ui.delete_profiles_structure_pushButton.clicked.connect(self.delete_profiles_structure)

        self.ui.set_profile_state_button.clicked.connect(self.set_profiles_state_to_grid)

        self.ui.edit_profiles_pushButton.clicked.connect(self.import_profiles)

        self.ui.profile_display_pushButton.clicked.connect(self.display_profiles)

        self.ui.plot_pushButton.clicked.connect(self.item_results_plot)

        self.ui.select_all_pushButton.clicked.connect(self.check_all_result_objects)

        self.ui.select_none_pushButton.clicked.connect(self.check_none_result_objects)

        self.ui.saveResultsButton.clicked.connect(self.save_results_df)

        self.ui.set_profile_state_button.clicked.connect(self.set_state)

        self.ui.setValueToColumnButton.clicked.connect(self.set_value_to_column)

        self.ui.run_cascade_pushButton.clicked.connect(self.run_cascade)

        self.ui.clear_cascade_pushButton.clicked.connect(self.clear_cascade)

        self.ui.run_cascade_step_pushButton.clicked.connect(self.run_cascade_step)

        self.ui.exportSimulationDataButton.clicked.connect(self.export_simulation_data)

        self.ui.view_map_pushButton.clicked.connect(self.update_map)

        self.ui.filter_pushButton.clicked.connect(self.smart_search)

        self.ui.location_search_pushButton.clicked.connect(self.search_location)

        self.ui.profile_add_pushButton.clicked.connect(lambda: self.modify_profiles('+'))

        self.ui.profile_subtract_pushButton.clicked.connect(lambda: self.modify_profiles('-'))

        self.ui.profile_multiply_pushButton.clicked.connect(lambda: self.modify_profiles('*'))

        self.ui.profile_divide_pushButton.clicked.connect(lambda: self.modify_profiles('/'))

        self.ui.set_profile_value_pushButton.clicked.connect(lambda: self.modify_profiles('set'))

        self.ui.set_linear_combination_profile_pushButton.clicked.connect(self.set_profile_as_linear_combination)

        self.ui.plot_time_series_pushButton.clicked.connect(self.plot_profiles)

        self.ui.analyze_objects_pushButton.clicked.connect(self.display_grid_analysis)

        self.ui.catalogue_add_pushButton.clicked.connect(self.add_to_catalogue)

        self.ui.catalogue_edit_pushButton.clicked.connect(self.edit_from_catalogue)

        self.ui.catalogue_delete_pushButton.clicked.connect(self.delete_from_catalogue)

        self.ui.viewTemplatesButton.clicked.connect(self.view_template_toggle)

        self.ui.assignTemplateButton.clicked.connect(self.assign_template)

        self.ui.processTemplatesPushButton.clicked.connect(self.process_templates)

        self.ui.compute_simulation_data_pushButton.clicked.connect(self.update_islands_to_display)

        self.ui.copy_profile_pushButton.clicked.connect(self.copy_profiles)

        self.ui.paste_profiles_pushButton.clicked.connect(self.paste_profiles)

        self.ui.colour_results_pushButton.clicked.connect(self.colour_now)

        self.ui.view_previous_simulation_step_pushButton.clicked.connect(self.colour_previous_simulation_step)

        self.ui.view_next_simulation_step_pushButton.clicked.connect(self.colour_next_simulation_step)

        self.ui.close_colour_toolbox_pushButton.clicked.connect(self.hide_color_tool_box)

        self.ui.copy_results_pushButton.clicked.connect(self.copy_results_data)

        self.ui.undo_pushButton.clicked.connect(self.undo)

        self.ui.redo_pushButton.clicked.connect(self.redo)

        self.ui.delete_selected_objects_pushButton.clicked.connect(self.delete_selected_objects)

        self.ui.delete_and_reduce_pushButton.clicked.connect(self.delete_and_reduce_selected_objects)

        self.ui.highlight_selection_buses_pushButton.clicked.connect(self.highlight_selection_buses)

        self.ui.clear_highlight_pushButton.clicked.connect(self.clear_big_bus_markers)

        self.ui.highlight_by_property_pushButton.clicked.connect(self.highlight_based_on_property)

        self.ui.plot_data_pushButton.clicked.connect(self.plot_results)

        # node size
        self.ui.actionBigger_nodes.triggered.connect(self.bigger_nodes)

        self.ui.actionSmaller_nodes.triggered.connect(self.smaller_nodes)

        self.ui.actionCenter_view.triggered.connect(self.center_nodes)

        self.ui.actionAutoatic_layout.triggered.connect(self.auto_layout)

        # list clicks
        self.ui.result_listView.clicked.connect(self.update_available_results_in_the_study)

        self.ui.result_type_listView.clicked.connect(self.result_type_click)

        self.ui.dataStructuresListView.clicked.connect(self.view_objects_data)

        self.ui.simulationDataStructuresListView.clicked.connect(self.view_simulation_objects_data)

        self.ui.catalogueDataStructuresListView.clicked.connect(self.catalogue_element_selected)

        # Table clicks
        self.ui.cascade_tableView.clicked.connect(self.cascade_table_click)

        # combobox
        self.ui.profile_device_type_comboBox.currentTextChanged.connect(self.profile_device_type_changed)

        self.ui.plt_style_comboBox.currentTextChanged.connect(self.plot_style_change)

        self.ui.available_results_to_color_comboBox.currentTextChanged.connect(self.update_available_steps_to_color)

        # sliders
        self.ui.profile_start_slider.valueChanged.connect(self.profile_sliders_changed)
        self.ui.profile_end_slider.valueChanged.connect(self.profile_sliders_changed)

        # doubleSpinBox
        self.ui.fbase_doubleSpinBox.valueChanged.connect(self.change_circuit_base)
        self.ui.sbase_doubleSpinBox.valueChanged.connect(self.change_circuit_base)

        self.ui.explosion_factor_doubleSpinBox.valueChanged.connect(self.explosion_factor_change)

        # line edit enter
        self.ui.smart_search_lineEdit.returnPressed.connect(self.smart_search)

        ################################################################################################################
        # Other actions
        ################################################################################################################
        self.ui.actionShow_map.setVisible(False)

        self.ui.grid_colouring_frame.setVisible(False)

        # template
        self.view_templates(False)
        self.view_template_controls(False)

        self.view_cascade_menu()
        self.show_map()

    def LOCK(self, val=True):
        """
        Lock the interface to prevent new simulation launches
        :param val:
        :return:
        """
        self.lock_ui = val
        self.ui.progress_frame.setVisible(self.lock_ui)
        QtGui.QGuiApplication.processEvents()

    def UNLOCK(self):
        """
        Unloack the interface
        @return:
        """
        self.LOCK(False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """
        Drop file on the GUI, the default behaviour is to load the file
        :param event: event containing all the information
        """
        # print(event)
        if event.mimeData().hasUrls:
            file_name = event.mimeData().urls()[0].toLocalFile()
            name, file_extension = os.path.splitext(file_name)
            accepted = ['.gridcal', '.xlsx', '.xls', '.dgs', '.m', '.raw', '.RAW', '.json', '.xml', '.dpx']
            if file_extension.lower() in accepted:
                self.open_file_now(filename=file_name)
            else:
                self.msg('File type not accepted :(')

    def add_simulation(self, val: SimulationTypes):
        """
        Add a simulation to the simulations list
        :param val: simulation type
        """
        self.stuff_running_now.append(val)

    def remove_simulation(self, val: SimulationTypes):
        """
        Remove a simulation from the simulations list
        :param val: simulation type
        """
        if val in self.stuff_running_now:
            self.stuff_running_now.remove(val)

    def view_templates(self, value=True):
        """
        View the frame
        Args:
            value:

        Returns:

        """
        self.ui.templatesFrame.setVisible(value)

        # fill the catalogue
        if value:
            self.fill_catalogue_tree_view()

    def view_template_controls(self, value=True):
        """
        View the buttons
        Args:
            value:

        Returns:

        """
        self.ui.viewTemplatesButton.setVisible(value)
        self.ui.processTemplatesPushButton.setVisible(value)

    def view_template_toggle(self):

        if self.ui.templatesFrame.isVisible():
            self.view_templates(False)
        else:
            self.view_templates(True)

    def view_cascade_menu(self):
        """
        show/hide the cascade simulation menu
        """
        self.ui.cascade_menu.setVisible(self.ui.actionBlackout_cascade.isChecked())
        self.ui.cascade_grid_splitter.setStretchFactor(1, 4)

    def show_map(self):
        """
        show/hide the cascade simulation menu
        """
        val = self.ui.actionShow_map.isChecked()
        self.ui.map_frame.setVisible(val)
        self.grid_editor.diagramView.view_map(val)

    def about_box(self):
        """
        Display about box
        :return:
        """
        url = 'https://github.com/SanPen/GridCal'

        msg = "Gridcal v" + str(__GridCal_VERSION__) + '\n\n'

        msg += "GridCal has been carefully crafted since 2015 to serve as a platform for research and consultancy.\n\n"

        msg += 'This program comes with ABSOLUTELY NO WARRANTY. \n'
        msg += 'This is free software, and you are welcome to redistribute it under certain conditions; '

        msg += "GridCal is licensed under the GNU general public license V.3 "
        msg += 'See the license file for more details. \n\n'
        msg += "The source of Gridcal can be found at:\n" + url + "\n\n"

        msg += 'Copyright (C) 2019\nSantiago Peñate Vera\nMichel Lavoie'

        QMessageBox.about(self, "About GridCal", msg)

    def show_online_docs(self):
        """
        OPen the online documentation in a web browser
        """
        import webbrowser
        webbrowser.open('https://gridcal.readthedocs.io/en/latest/', new=2)

    @staticmethod
    def print_console_help():
        """
        print the console help in the console
        @return:
        """
        print('GridCal internal commands.\n')
        print('If a command is unavailable is because the study has not been executed yet.')

        print('\n\nclc():\tclear the console.')

        # self.power_flow = None
        # self.short_circuit = None
        # self.monte_carlo = None
        # self.time_series = None
        # self.voltage_stability = None
        # self.latin_hypercube_sampling = None
        # self.cascade = None
        # self.optimal_power_flow = None
        # self.optimal_power_flow_time_series = None

        print('\n\nApp functions:')
        print('\tapp.new_project(): Clear all.')
        print('\tapp.open_file(): Prompt to load GridCal compatible file')
        print('\tapp.save_file(): Prompt to save GridCal file')
        print('\tapp.export_diagram(): Prompt to export the diagram in png.')
        print('\tapp.create_schematic_from_api(): Create the schematic from the circuit information.')
        print('\tapp.adjust_all_node_width(): Adjust the width of all the nodes according to their name.')

        print('\n\nCircuit functions:')
        print('\tapp.circuit.compile(): Compile the grid(s)')
        print('\tapp.circuit.plot_graph(): Plot a graph in a Matplotlib window. Call plt.show() after.')
        print('\tapp.circuit.load_file("file_name.xlsx/.m/.raw/.dgs"): Load GridCal compatible file')
        print('\tapp.circuit.save_file("file_name.xlsx"): Save GridCal file')
        print('\tapp.circuit.export_pf("file_name.xlsx"): Export power flow results to Excel')

        print('\n\nPower flow results:')
        print('\tapp.power_flow.voltage:\t the nodal voltages in per unit')
        print('\tapp.power_flow.current:\t the branch currents in per unit')
        print('\tapp.power_flow.loading:\t the branch loading in %')
        print('\tapp.power_flow.losses:\t the branch losses in per unit')
        print('\tapp.power_flow.power:\t the nodal power injections in per unit')
        print('\tapp.power_flow.power_from:\t the branch power injections in per unit at the "from" side')
        print('\tapp.power_flow.power_to:\t the branch power injections in per unit at the "to" side')

        print('\n\nShort circuit results:')
        print('\tapp.short_circuit.voltage:\t the nodal voltages in per unit')
        print('\tapp.short_circuit.current:\t the branch currents in per unit')
        print('\tapp.short_circuit.loading:\t the branch loading in %')
        print('\tapp.short_circuit.losses:\t the branch losses in per unit')
        print('\tapp.short_circuit.power:\t the nodal power injections in per unit')
        print('\tapp.short_circuit.power_from:\t the branch power injections in per unit at the "from" side')
        print('\tapp.short_circuit.power_to:\t the branch power injections in per unit at the "to" side')
        print('\tapp.short_circuit.short_circuit_power:\t Short circuit power in MVA of the grid nodes')

        print('\n\nOptimal power flow results:')
        print('\tapp.optimal_power_flow.voltage:\t the nodal voltages angles in rad')
        print('\tapp.optimal_power_flow.load_shedding:\t the branch loading in %')
        print('\tapp.optimal_power_flow.losses:\t the branch losses in per unit')
        print('\tapp.optimal_power_flow.Sbus:\t the nodal power injections in MW')
        print('\tapp.optimal_power_flow.Sbranch:\t the branch power flows')
        print('\tapp.optimal_power_flow.losses:\t the branch losses in MVA')
        print('\tapp.optimal_power_flow.short_circuit_power:\t Short circuit power in MVA of the grid nodes')

        print('\n\nTime series power flow results:')
        print('\tapp.time_series.time:\t Profiles time index (pandas DateTimeIndex object)')
        print('\tapp.time_series.load_profiles:\t Load profiles matrix (row: time, col: node)')
        print('\tapp.time_series.gen_profiles:\t Generation profiles matrix (row: time, col: node)')
        print('\tapp.time_series.voltages:\t nodal voltages results matrix (row: time, col: node)')
        print('\tapp.time_series.currents:\t branches currents results matrix (row: time, col: branch)')
        print('\tapp.time_series.loadings:\t branches loadings results matrix (row: time, col: branch)')
        print('\tapp.time_series.losses:\t branches losses results matrix (row: time, col: branch)')

        print('\n\nVoltage stability power flow results:')
        print('\tapp.voltage_stability.continuation_voltage:\t Voltage values for every power multiplication factor.')
        print('\tapp.voltage_stability.continuation_lambda:\t Value of power multiplication factor applied')
        print('\tapp.voltage_stability.continuation_power:\t Power values for every power multiplication factor.')

        print('\n\nMonte Carlo power flow results:')
        print('\tapp.monte_carlo.V_avg:\t nodal voltage average result.')
        print('\tapp.monte_carlo.I_avg:\t branch current average result.')
        print('\tapp.monte_carlo.Loading_avg:\t branch loading average result.')
        print('\tapp.monte_carlo.Losses_avg:\t branch losses average result.')
        print('\tapp.monte_carlo.V_std:\t nodal voltage standard deviation result.')
        print('\tapp.monte_carlo.I_std:\t branch current standard deviation result.')
        print('\tapp.monte_carlo.Loading_std:\t branch loading standard deviation result.')
        print('\tapp.monte_carlo.Losses_std:\t branch losses standard deviation result.')
        print('\tapp.monte_carlo.V_avg_series:\t nodal voltage average series.')
        print('\tapp.monte_carlo.V_std_series:\t branch current standard deviation series.')
        print('\tapp.monte_carlo.error_series:\t Monte Carlo error series (the convergence value).')
        print('The same for app.latin_hypercube_sampling')

    def clc(self):
        """
        Clear the console
        """
        self.console.clear()

    

    def msg(self, text, title="Warning"):
        """
        Message box
        :param text: Text to display
        :param title: Name of the window
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()

    def console_msg(self, msg_):
        """
        Print some message in the console.

        Arguments:

            **msg_** (str): Message

        """
        dte = datetime.datetime.now().strftime("%b %d %Y %H:%M:%S")
        self.console.print_text('\n' + dte + '->' + msg_)

    def auto_layout(self):
        """
        Automatic layout of the nodes
        """

        # guilty assumption
        do_it = True

        # if the ask, checkbox is checked, then ask
        if self.ui.ask_before_appliying_layout_checkBox.isChecked():
            reply = QMessageBox.question(self, 'Message', 'Are you sure that you want to try an automatic layout?',
                                         QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                do_it = True
            else:
                do_it = False

        if do_it:
            if self.circuit.graph is None:
                try:
                    self.circuit.build_graph()
                except:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    self.msg(str(exc_traceback) + '\n' + str(exc_value), 'Automatic layout')

            alg = dict()
            alg['circular_layout'] = nx.circular_layout
            alg['random_layout'] = nx.random_layout
            alg['shell_layout'] = nx.shell_layout
            alg['spring_layout'] = nx.spring_layout
            alg['spectral_layout'] = nx.spectral_layout
            alg['fruchterman_reingold_layout'] = nx.fruchterman_reingold_layout

            sel = self.ui.automatic_layout_comboBox.currentText()
            pos_alg = alg[sel]

            # get the positions of a spring layout of the graph
            if sel == 'random_layout':
                pos = pos_alg(self.circuit.graph)
            else:
                pos = pos_alg(self.circuit.graph, scale=10)

            # assign the positions to the graphical objects of the nodes
            for i, bus in enumerate(self.circuit.buses):
                try:
                    x, y = pos[i] * 500
                    bus.graphic_obj.setPos(QPoint(x, y))
                except KeyError as ex:
                    warn('Node ' + str(i) + ' not in graph!!!! \n' + str(ex))
            # adjust the view
            self.center_nodes()

        else:
            pass  # asked and decided ot to change the layout

    def bigger_nodes(self):
        """
        Move the nodes more separated
        """
        if self.grid_editor is not None:
            self.grid_editor.bigger_nodes()

    def smaller_nodes(self):
        """
        Move the nodes closer
        """
        if self.grid_editor is not None:
            self.grid_editor.smaller_nodes()

    def center_nodes(self):
        """
        Center the nodes in the screen
        """
        if self.grid_editor is not None:
            # self.grid_editor.center_nodes()
            self.grid_editor.diagramView.fitInView(self.grid_editor.diagramScene.sceneRect(), Qt.KeepAspectRatio)
            self.grid_editor.diagramView.scale(1.0, 1.0)

    def new_project_now(self):
        """
        New project right now without asking questions
        """
        # clear the circuit model
        self.circuit = MultiCircuit()

        # clear the file name
        self.file_name = ''

        lat0 = self.ui.lat1_doubleSpinBox.value()
        lon0 = self.ui.lon1_doubleSpinBox.value()
        zoom = self.ui.zoom_spinBox.value()

        self.grid_editor = GridEditor(self.circuit, lat0=lat0, lon0=lon0, zoom=zoom)

        self.grid_editor.diagramView.view_map(False)

        self.ui.dataStructuresListView.setModel(get_list_model(self.grid_editor.object_types))

        # delete all widgets
        for i in reversed(range(self.ui.schematic_layout.count())):
            self.ui.schematic_layout.itemAt(i).widget().deleteLater()

        # add the widgets
        self.ui.schematic_layout.addWidget(self.grid_editor)
        # self.ui.splitter_8.setStretchFactor(1, 15)

        # clear the results
        # self.ui.resultsPlot.clear()
        self.ui.resultsTableView.setModel(None)

        # clear the comments
        self.ui.comments_textEdit.setText("")

        # clear the simulation objects
        self.power_flow = None
        self.short_circuit = None
        self.monte_carlo = None
        self.time_series = None
        self.voltage_stability = None
        self.latin_hypercube_sampling = None
        self.cascade = None
        self.optimal_power_flow = None
        self.optimal_power_flow_time_series = None
        self.transient_stability = None
        self.topology_reduction = None
        self.open_file_thread_object = None
        self.save_file_thread_object = None

        self.stuff_running_now = list()

        self.clear_results()

    def new_project(self):
        """
        Create new grid
        :return:
        """
        if len(self.circuit.buses) > 0:
            quit_msg = "Are you sure that you want to quit the current grid and create a new one?"
            reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.new_project_now()

    def open_file(self):
        """
        Open GridCal file
        @return:
        """
        if ('file_save' not in self.stuff_running_now) and ('file_open' not in self.stuff_running_now):
            if len(self.circuit.buses) > 0:
                quit_msg = "Are you sure that you want to quit the current grid and open a new one?" \
                           "\n If the process is cancelled the grid will remain."
                reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

                if reply == QMessageBox.Yes:
                    self.new_project_now()
                    self.open_file_threaded()
                else:
                    pass
            else:
                # Just open the file
                self.open_file_threaded()

        else:
            self.msg('There is a file being processed now.')

    def open_file_threaded(self):
        """
        Open file from a Qt thread to remain responsive
        """

        files_types = "Formats (*.gridcal *.xlsx *.xls *.dgs *.m *.raw *.RAW *.json *.xml *.dpx)"
        # files_types = ''
        # call dialog to select the file

        options = QFileDialog.Options()
        if self.use_native_dialogues:
            options |= QFileDialog.DontUseNativeDialog

        filename, type_selected = QtWidgets.QFileDialog.getOpenFileName(parent=self,
                                                                        caption='Open file',
                                                                        directory=self.project_directory,
                                                                        filter=files_types,
                                                                        options=options)

        if len(filename) > 0:
            self.open_file_now(filename)

    def open_file_now(self, filename):
        """

        :param filename:
        :return:
        """
        self.file_name = filename

        # store the working directory
        self.project_directory = os.path.dirname(self.file_name)

        # lock the ui
        self.LOCK()

        # create thread
        self.open_file_thread_object = FileOpenThread(file_name=self.file_name)

        # make connections
        self.open_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
        self.open_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
        self.open_file_thread_object.done_signal.connect(self.UNLOCK)
        self.open_file_thread_object.done_signal.connect(self.post_open_file)

        # thread start
        self.open_file_thread_object.start()

        self.stuff_running_now.append('file_open')

    def post_open_file(self):
        """
        Actions to perform after a file has been loaded
        """

        self.stuff_running_now.remove('file_open')

        if self.open_file_thread_object is not None:

            if len(self.open_file_thread_object.logger) > 0:
                if len(self.open_file_thread_object.logger) > 0:
                    dlg = LogsDialogue('Open file logger', self.open_file_thread_object.logger)
                    dlg.exec_()

            if self.open_file_thread_object.valid:

                # assign the loaded circuit
                self.circuit = self.open_file_thread_object.circuit

                # create schematic
                self.create_schematic_from_api(explode_factor=1)

                # set circuit name
                self.grid_editor.name_label.setText(str(self.circuit.name))

                # set base magnitudes
                self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
                self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)

                # set circuit comments
                try:
                    self.ui.comments_textEdit.setText(str(self.circuit.comments))
                except:
                    pass

                # update the drop down menus that display dates
                self.update_date_dependent_combos()

                # clear the results
                self.clear_results()

            else:
                warn('The file was not valid')
        else:
            pass

    def update_date_dependent_combos(self):
        """
        update the drop down menus that display dates
        """
        if self.circuit.time_profile is not None:
            # print('Profiles available')
            mdl = get_list_model(self.circuit.time_profile)
            # setup profile sliders
            self.set_up_profile_sliders()
        else:
            mdl = QStandardItemModel()
        self.ui.profile_time_selection_comboBox.setModel(mdl)
        self.ui.vs_departure_comboBox.setModel(mdl)
        self.ui.vs_target_comboBox.setModel(mdl)

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
        files_types = "GridCal zip (*.gridcal);;Excel (*.xlsx);;CIM (*.xml);;JSON (*.json)"

        # call dialog to select the file
        if self.project_directory is None:
            self.project_directory = ''

        # set grid name
        self.circuit.name = self.grid_editor.name_label.text()

        # gather comments
        self.circuit.comments = self.ui.comments_textEdit.toPlainText()

        if self.file_name == '':
            # if the global file_name is empty, ask where to save
            fname = os.path.join(self.project_directory, self.grid_editor.name_label.text())

            options = QFileDialog.Options()
            if self.use_native_dialogues:
                options |= QFileDialog.DontUseNativeDialog

            filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types,
                                                                  options=options)

            if filename != '':

                # if the user did not enter the extension, add it automatically
                name, file_extension = os.path.splitext(filename)

                extension = dict()
                extension['Excel (*.xlsx)'] = '.xlsx'
                extension['CIM (*.xml)'] = '.xml'
                extension['JSON (*.json)'] = '.json'
                extension['GridCal zip (*.gridcal)'] = '.gridcal'

                if file_extension == '':
                    filename = name + extension[type_selected]

                # we were able to compose the file correctly, now save it
                self.file_name = filename
                self.save_file_now(self.file_name)
        else:

            # save directly
            self.save_file_now(self.file_name)

    def save_file_now(self, filename):
        """
        Save the file right now, without questions
        :param filename: filename to save to
        """

        if ('file_save' not in self.stuff_running_now) and ('file_open' not in self.stuff_running_now):
            # lock the ui
            self.LOCK()

            self.save_file_thread_object = FileSaveThread(self.circuit, filename)

            # make connections
            self.save_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
            self.save_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
            self.save_file_thread_object.done_signal.connect(self.UNLOCK)
            self.save_file_thread_object.done_signal.connect(self.post_file_save)

            # thread start
            self.save_file_thread_object.start()

            self.stuff_running_now.append('file_save')

        else:
            self.msg('There is a file being processed..')

    def post_file_save(self):
        """
        Actions after the threaded file save
        """
        if len(self.save_file_thread_object.logger) > 0:
            dlg = LogsDialogue('Save file logger', self.save_file_thread_object.logger)
            dlg.exec_()

        self.stuff_running_now.remove('file_save')

        # call the garbage collector to free memory
        gc.collect()

    def closeEvent(self, event):
        """
        Close event
        :param event:
        :return:
        """
        if len(self.circuit.buses) > 0:
            quit_msg = "Are you sure that you want to exit GridCal?"
            reply = QMessageBox.question(self, 'Close', quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            # no buses so exit
            event.accept()

    def export_pf_results(self):
        """
        Export power flow results
        """
        if self.power_flow is not None:
            # if self.circuit.graph is None:
            #     self.compile()

            # declare the allowed file types
            files_types = "Excel file (*.xlsx)"
            # call dialog to select the file
            if self.project_directory is None:
                self.project_directory = ''

            # set grid name
            self.circuit.name = self.grid_editor.name_label.text()

            fname = os.path.join(self.project_directory, 'power flow results of ' + self.grid_editor.name_label.text())

            options = QFileDialog.Options()
            if self.use_native_dialogues:
                options |= QFileDialog.DontUseNativeDialog

            filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types,
                                                                  options=options)

            if filename is not "":
                if not filename.endswith('.xlsx'):
                    filename += '.xlsx'
                # TODO: Correct this function
                self.circuit.export_pf(file_name=filename, power_flow_results=self.power_flow.results)
        else:
            self.msg('There are no power flow results', 'Save power flow results')

    def export_object_profiles(self):
        """
        Export object profiles
        """
        if self.circuit.time_profile is not None:
            # if self.circuit.graph is None:
            #     self.compile()

            # declare the allowed file types
            files_types = "Excel file (*.xlsx)"
            # call dialog to select the file
            if self.project_directory is None:
                self.project_directory = ''

            # set grid name
            self.circuit.name = self.grid_editor.name_label.text()

            fname = os.path.join(self.project_directory, 'profiles of ' + self.grid_editor.name_label.text())

            options = QFileDialog.Options()
            if self.use_native_dialogues:
                options |= QFileDialog.DontUseNativeDialog

            filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types,
                                                                  options=options)

            if filename is not "":
                if not filename.endswith('.xlsx'):
                    filename += '.xlsx'
                # TODO: correct this function
                self.circuit.export_profiles(file_name=filename)
        else:
            self.msg('There are no profiles!', 'Export object profiles')

    def export_all(self):
        """
        Export all the results
        :return:
        """

        # set grid name
        self.circuit.name = self.grid_editor.name_label.text()

        available_results = self.get_available_results()

        if len(available_results) > 0:

            files_types = "Zip file (*.zip)"
            fname = os.path.join(self.project_directory, 'Results of ' + self.grid_editor.name_label.text())
            options = QFileDialog.Options()
            if self.use_native_dialogues:
                options |= QFileDialog.DontUseNativeDialog

            filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types,
                                                                  options=options)

            if filename is not "":
                self.LOCK()

                self.stuff_running_now.append('export_all')
                self.export_all_thread_object = ExportAllThread(circuit=self.circuit,
                                                                simulations_list=available_results,
                                                                file_name=filename)

                self.export_all_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
                self.export_all_thread_object.progress_text.connect(self.ui.progress_label.setText)
                self.export_all_thread_object.done_signal.connect(self.post_export_all)
                self.export_all_thread_object.start()
        else:
            self.msg('There are no result available :/')

    def post_export_all(self):
        """
        Actions post export all
        """
        self.stuff_running_now.remove('export_all')
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

        # set grid name
        self.circuit.name = self.grid_editor.name_label.text()

        fname = os.path.join(self.project_directory, self.grid_editor.name_label.text())

        options = QFileDialog.Options()
        if self.use_native_dialogues:
            options |= QFileDialog.DontUseNativeDialog

        filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types,
                                                              options=options)

        if filename is not "":
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            # TODO: Correct this function to not to depend on a previous compilation
            self.circuit.save_calculation_objects(file_path=filename)

    def export_diagram(self):
        """
        Save the schematic
        :return:
        """
        if self.grid_editor is not None:

            # declare the allowed file types
            files_types = "Scalable Vector Graphics (*.svg);;Portable Network Graphics (*.png)"
            # files_types = 'PDF (*.pdf)'

            fname = os.path.join(self.project_directory, self.grid_editor.name_label.text())

            options = QFileDialog.Options()
            if self.use_native_dialogues:
                options |= QFileDialog.DontUseNativeDialog

            # call dialog to select the file
            filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types,
                                                                  options=options)

            if filename is not "":
                # save in factor * K
                factor = self.ui.resolution_factor_spinBox.value()
                w = 1920 * factor
                h = 1080 * factor
                self.grid_editor.export(filename, w, h)

    def create_schematic_from_api(self, explode_factor=1):
        """
        This function explores the API values and draws an schematic layout
        @return:
        """
        # set pointer to the circuit
        self.grid_editor.circuit = self.circuit

        self.grid_editor.schematic_from_api(explode_factor=explode_factor)

    def post_create_schematic(self):

        self.UNLOCK()

    def update_map(self):
        """
        Update map
        :return:
        """
        lat0 = self.ui.lat1_doubleSpinBox.value()
        lon0 = self.ui.lon1_doubleSpinBox.value()
        zoom = self.ui.zoom_spinBox.value()
        self.grid_editor.diagramView.map.load_map(lat0, lon0, zoom)
        self.grid_editor.diagramView.adapt_map_size()

    def search_location(self):
        """
        Find the latitude and longitude of a lauwsy-defined location
        :return:
        """
        geolocator = Nominatim()
        location_text = self.ui.location_lineEdit.text()

        if location_text.strip() != '':
            try:
                location = geolocator.geocode(location_text)
                self.ui.lon1_doubleSpinBox.setValue(float(location.longitude))
                self.ui.lat1_doubleSpinBox.setValue(float(location.latitude))
            except:
                self.msg('Location finding failed. \nCheck your connection.', 'Location finding')

    def search_location(self):
        """
        Find the latitude and longitude of a lauwsy-defined location
        :return:
        """
        geolocator = Nominatim()
        location_text = self.ui.location_lineEdit.text()

        if location_text.strip() != '':
            try:
                location = geolocator.geocode(location_text)
                self.ui.lon1_doubleSpinBox.setValue(float(location.longitude))
                self.ui.lat1_doubleSpinBox.setValue(float(location.latitude))
            except:
                self.msg('Location finding failed. \nCheck your connection.', 'Location finding')

    def auto_rate_branches(self):
        """
        Rate the branches that do not have rate
        """

        if len(self.circuit.branches) > 0:

            if self.power_flow is not None:
                factor = self.ui.branch_rating_doubleSpinBox.value()

                for i, branch in enumerate(self.circuit.branches):

                    S = self.power_flow.results.Sbranch[i]

                    if branch.rate < 1e-3 or self.ui.rating_override_checkBox.isChecked():
                        r = np.round(abs(S) * factor, 1)
                        branch.rate = r if r > 0.0 else 1.0
                    else:
                        pass  # the rate is ok

            else:
                self.msg('Run a power flow simulation first.\nThe results are needed in this function.')

        else:
            self.msg('There are no branches!')

    def detect_transformers(self):
        """
        Detect which branches are transformers
        """
        if len(self.circuit.branches) > 0:

            for branch in self.circuit.branches:

                v1 = branch.bus_from.Vnom
                v2 = branch.bus_to.Vnom

                if abs(v1 - v2) > 1.0:

                    branch.branch_type = BranchType.Transformer

                else:

                    pass  # is a line

        else:
            self.msg('There are no branches!')

    def view_objects_data(self):
        """
        On click, display the objects properties
        """
        elm_type = self.ui.dataStructuresListView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

        self.view_template_controls(False)

        if elm_type == 'Buses':
            elm = Bus()
            elements = self.circuit.buses

        elif elm_type == 'Branches':

            self.fill_catalogue_tree_view()

            elm = Branch(None, None)
            elements = self.circuit.branches

            self.view_template_controls(True)

        elif elm_type == 'Loads':
            elm = Load()
            elements = self.circuit.get_loads()

        elif elm_type == 'Static Generators':
            elm = StaticGenerator()
            elements = self.circuit.get_static_generators()

        elif elm_type == 'Generators':
            elm = Generator()
            elements = self.circuit.get_generators()

        elif elm_type == 'Batteries':
            elm = Battery()
            elements = self.circuit.get_batteries()

        elif elm_type == 'Shunts':
            elm = Shunt()
            elements = self.circuit.get_shunts()

        else:
            raise Exception('elm_type not understood: ' + elm_type)

        if elm_type == 'Branches':
            mdl = BranchObjectModel(elements, elm.editable_headers,
                                    parent=self.ui.dataStructureTableView, editable=True,
                                    non_editable_attributes=elm.non_editable_attributes)
        else:

            mdl = ObjectsModel(elements, elm.editable_headers,
                               parent=self.ui.dataStructureTableView, editable=True,
                               non_editable_attributes=elm.non_editable_attributes)
        self.type_objects_list = elements
        self.ui.dataStructureTableView.setModel(mdl)
        self.ui.property_comboBox.clear()
        self.ui.property_comboBox.addItems(mdl.attributes)
        self.view_templates(False)

    def fill_catalogue_tree_view(self):
        """
        Fill the Catalogue tree view with the catalogue types
        """

        catalogue_dict = self.circuit.get_catalogue_dict(branches_only=True)

        model = QStandardItemModel()

        model.setHorizontalHeaderLabels(['Template'])

        for key in catalogue_dict.keys():
            # add parent node
            parent1 = QStandardItem(str(key))
            parent1.setEditable(False)

            # add children to parent
            for elm in catalogue_dict[key]:
                child1 = QStandardItem(str(elm))
                child1.setEditable(False)
                parent1.appendRow([child1])

            # add parent to the model
            model.appendRow(parent1)

        # set the model to the tree
        self.ui.catalogueTreeView.setModel(model)

    def view_simulation_objects_data(self):
        """
        Simulation data structure clicked
        """

        # TODO: Correct this function to operate correctly with the new engine

        i = self.ui.simulation_data_island_comboBox.currentIndex()

        if i > -1 and len(self.circuit.buses) > 0:
            elm_type = self.ui.simulationDataStructuresListView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

            df = self.calculation_inputs_to_display[i].get_structure(elm_type)

            # df = self.circuit.circuits[i].power_flow_input.get_structure(elm_type)

            mdl = PandasModel(df)

            self.ui.simulationDataStructureTableView.setModel(mdl)

        else:
            pass

    def profile_device_type_changed(self):
        """

        """
        dev_type = self.ui.profile_device_type_comboBox.currentText()
        mdl = get_list_model(self.circuit.profile_magnitudes[dev_type][0])
        self.ui.device_type_magnitude_comboBox.setModel(mdl)
        self.ui.device_type_magnitude_comboBox_2.setModel(mdl)

    def new_profiles_structure(self):
        """
        Create new profiles structure
        :return:
        """
        # print('new_profiles_structure')

        dlg = NewProfilesStructureDialogue()
        if dlg.exec_():
            steps, step_length, step_unit, time_base = dlg.get_values()

            self.ui.profiles_tableView.setModel(None)

            self.circuit.create_profiles(steps, step_length, step_unit, time_base)

            self.display_profiles()

            self.set_up_profile_sliders()

            self.update_date_dependent_combos()

    def delete_profiles_structure(self):
        """
        Delete all profiles
        :return: Nothing
        """

        if self.circuit.time_profile is not None:
            quit_msg = "Are you sure that you want to remove the profiles?"
            reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                for bus in self.circuit.buses:
                    bus.delete_profiles()
                self.circuit.time_profile = None
                self.circuit.has_time_series = False
                self.ui.profiles_tableView.setModel(None)
                self.set_up_profile_sliders()
                self.update_date_dependent_combos()
            else:
                pass
        else:
            self.msg('There are no profiles', 'Delete profiles')

    def set_profiles_state_to_grid(self):
        """
        Set the profiles scenario at the selected time index to the main values of the grid
        :return: Nothing
        """
        if self.circuit.time_profile is not None:
            t = self.ui.profile_time_selection_comboBox.currentIndex()

            if t > -1:
                name_t = self.ui.profile_time_selection_comboBox.currentText()
                quit_msg = "Replace the grid values by the scenario at " + name_t
                reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

                if reply == QMessageBox.Yes:
                    for bus in self.circuit.buses:
                        bus.set_profile_values(t)
                else:
                    pass
            else:
                self.msg('No profile time selected', 'Set profile values')
        else:
            self.msg('There are no profiles', 'Set profile values')

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
            dialogue = ProfileInputGUI(parent=self,
                                       list_of_objects=objects,
                                       magnitudes=[magnitude],
                                       use_native_dialogues=self.use_native_dialogues)
            dialogue.resize(int(1.61 * 600.0), 550)  # golden ratio
            dialogue.exec()  # exec leaves the parent on hold

            if dialogue.time is not None:

                # if there are no profiles:
                if self.circuit.time_profile is None:
                    self.circuit.format_profiles(dialogue.time)

                elif len(dialogue.time) != len(self.circuit.time_profile):
                    self.msg("The imported profile length does not match the existing one.\n"
                             "Delete the existing profiles before continuing.\n"
                             "The import action will not be performed")
                    return False

                # Assign profiles
                for i, elm in enumerate(objects):
                    if not dialogue.zeroed[i]:

                        if dialogue.normalized:
                            data = dialogue.data[:, i]
                        else:
                            data = dialogue.data[:, i]

                        # assign the profile to the object
                        prof_attr = elm.properties_with_profile[magnitude]
                        setattr(elm, prof_attr, data)
                        # elm.profile_f[magnitude](dialogue.time, dialogue.data[:, i], dialogue.normalized)

                # set up sliders
                self.set_up_profile_sliders()
                self.update_date_dependent_combos()

            else:
                pass  # the dialogue was closed

        else:
            self.msg("There are no objects to which to assign a profile")

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

                if operation == '+':
                    for i, elm in enumerate(objects):
                        setattr(elm, attr, getattr(elm, attr) + value)
                        mod_cols.append(i)

                elif operation == '-':
                    for i, elm in enumerate(objects):
                        setattr(elm, attr, getattr(elm, attr) - value)
                        mod_cols.append(i)

                elif operation == '*':
                    for i, elm in enumerate(objects):
                        setattr(elm, attr, getattr(elm, attr) * value)
                        mod_cols.append(i)

                elif operation == '/':
                    for i, elm in enumerate(objects):
                        setattr(elm, attr, getattr(elm, attr) / value)
                        mod_cols.append(i)

                elif operation == 'set':
                    for i, elm in enumerate(objects):
                        arr = getattr(elm, attr)
                        setattr(elm, attr, np.ones(len(arr)) * value)
                        mod_cols.append(i)

                else:
                    raise Exception('Operation not supported: ' + str(operation))

            else:
                # indices were selected ...

                for idx in indices:

                    elm = objects[idx.column()]

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

            # self.display_profiles()
            model.update()
            # self.update_date_dependent_combos()

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

            reply = QMessageBox.question(self, 'Message', msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:

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
            # print('display_profiles')

            dev_type_text = self.ui.profile_device_type_comboBox.currentText()

            magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type_text]

            # get the enumeration univoque association with he device text
            dev_type = self.circuit.device_type_name_dict[dev_type_text]

            idx = self.ui.device_type_magnitude_comboBox.currentIndex()
            magnitude = magnitudes[idx]
            mtype = mag_types[idx]

            mdl = ProfilesModel(multi_circuit=self.circuit,
                                device_type=dev_type,
                                magnitude=magnitude,
                                format=mtype,
                                parent=self.ui.profiles_tableView)

            self.ui.profiles_tableView.setModel(mdl)

    def get_selected_power_flow_options(self):
        """
        Gather power flow run options
        :return:
        """
        solver_type = self.solvers_dict[self.ui.solver_comboBox.currentText()]

        reactve_power_control_mode = self.q_control_modes_dict[
            self.ui.reactive_power_control_mode_comboBox.currentText()]
        q_steepness_factor = self.ui.q_steepness_factor_spinBox.value()
        taps_control_mode = self.taps_control_modes_dict[self.ui.taps_control_mode_comboBox.currentText()]

        exponent = self.ui.tolerance_spinBox.value()
        tolerance = 1.0 / (10.0 ** exponent)

        max_iter = self.ui.max_iterations_spinBox.value()

        max_outer_iter = self.ui.outer_loop_spinBox.value()

        dispatch_storage = False

        if self.ui.helm_retry_checkBox.isChecked():
            retry_with_other_methods = True  # to set a value
        else:
            retry_with_other_methods = False

        if self.ui.apply_impedance_tolerances_checkBox.isChecked():
            branch_impedance_tolerance_mode = BranchImpedanceMode.Upper
        else:
            branch_impedance_tolerance_mode = BranchImpedanceMode.Specified

        mp = self.ui.use_multiprocessing_checkBox.isChecked()

        temp_correction = self.ui.temperature_correction_checkBox.isChecked()

        distributed_slack = self.ui.distributed_slack_checkBox.isChecked()

        ignore_single_node_islands = self.ui.ignore_single_node_islands_checkBox.isChecked()

        ops = PowerFlowOptions(solver_type=solver_type,
                               retry_with_other_methods=retry_with_other_methods,
                               verbose=False,
                               initialize_with_existing_solution=True,
                               tolerance=tolerance,
                               max_iter=max_iter,
                               max_outer_loop_iter=max_outer_iter,
                               control_q=reactve_power_control_mode,
                               multi_core=mp,
                               dispatch_storage=dispatch_storage,
                               control_taps=taps_control_mode,
                               apply_temperature_correction=temp_correction,
                               branch_impedance_tolerance_mode=branch_impedance_tolerance_mode,
                               q_steepness_factor=q_steepness_factor,
                               distributed_slack=distributed_slack,
                               ignore_single_node_islands=ignore_single_node_islands)

        return ops

    def run_power_flow(self):
        """
        Run a power flow simulation
        :return:
        """
        if len(self.circuit.buses) > 0:

            if SimulationTypes.PowerFlow_run not in self.stuff_running_now:

                self.LOCK()

                self.add_simulation(SimulationTypes.PowerFlow_run)

                self.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()
                # self.compile()  # compiles inside

                # get the power flow options from the GUI
                options = self.get_selected_power_flow_options()

                # compute the automatic precision
                if self.ui.auto_precision_checkBox.isChecked():
                    numerical = self.circuit.compile()
                    S = numerical.load_power / numerical.Sbase
                    lg = np.log10(abs(S))
                    lg[lg == -np.inf] = 0
                    tol_idx = int(min(abs(lg))) + 3
                    tolerance = 1.0 / (10.0 ** tol_idx)
                    options.tolerance = tolerance
                    self.ui.tolerance_spinBox.setValue(tol_idx)

                self.ui.progress_label.setText('Running power flow...')
                QtGui.QGuiApplication.processEvents()
                # set power flow object instance
                self.power_flow = PowerFlowDriver(self.circuit, options)

                self.power_flow.progress_signal.connect(self.ui.progressBar.setValue)
                self.power_flow.progress_text.connect(self.ui.progress_label.setText)
                self.power_flow.done_signal.connect(self.UNLOCK)
                self.power_flow.done_signal.connect(self.post_power_flow)
                self.power_flow.start()

            else:
                self.msg('Another simulation of the same type is running...')
        else:
            pass

    def post_power_flow(self):
        """
        Action performed after the power flow.
        Returns:

        """
        # update the results in the circuit structures
        # print('Post power flow')
        if self.power_flow.results is not None:
            self.ui.progress_label.setText('Colouring power flow results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.remove_simulation(SimulationTypes.PowerFlow_run)

            colour_the_schematic(circuit=self.circuit,
                                 s_bus=self.power_flow.results.Sbus,
                                 s_branch=self.power_flow.results.Sbranch,
                                 voltages=self.power_flow.results.voltage,
                                 loadings=self.power_flow.results.loading,
                                 types=self.power_flow.results.bus_types,
                                 losses=self.power_flow.results.losses)
            self.update_available_results()

            # print convergence reports on the console
            for report in self.power_flow.convergence_reports:
                msg_ = 'Power flow converged: \n' + report.__str__() + '\n\n'
                self.console_msg(msg_)

        else:
            self.msg('There are no power flow results.\nIs there any slack bus or generator?', 'Power flow')
            QtGui.QGuiApplication.processEvents()

        if len(self.power_flow.logger) > 0:
            dlg = LogsDialogue('Power flow', self.power_flow.logger)
            dlg.exec_()

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def run_short_circuit(self):
        """
        Run a short circuit simulation
        The short circuit simulation must be performed after a power flow simulation
        without any load or topology change
        :return:
        """
        if len(self.circuit.buses) > 0:
            if SimulationTypes.ShortCircuit_run not in self.stuff_running_now:
                if self.power_flow is not None:

                    self.add_simulation(SimulationTypes.ShortCircuit_run)

                    # Since we must run this study in the same conditions as
                    # the last power flow, no compilation is needed

                    # get the short circuit selected buses
                    sel_buses = list()
                    for i, bus in enumerate(self.circuit.buses):
                        if bus.graphic_obj.sc_enabled is True:
                            sel_buses.append(i)

                    if len(sel_buses) == 0:
                        self.msg('You need to enable some buses for short circuit.'
                                 + '\nEnable them by right click, and selecting on the context menu.')
                    else:
                        self.LOCK()

                        if self.ui.apply_impedance_tolerances_checkBox.isChecked():
                            branch_impedance_tolerance_mode = BranchImpedanceMode.Lower
                        else:
                            branch_impedance_tolerance_mode = BranchImpedanceMode.Specified

                        # get the power flow options from the GUI
                        sc_options = ShortCircuitOptions(bus_index=sel_buses,
                                                         branch_impedance_tolerance_mode=branch_impedance_tolerance_mode)

                        pf_options = self.get_selected_power_flow_options()

                        self.short_circuit = ShortCircuit(grid=self.circuit,
                                                          options=sc_options,
                                                          pf_options=pf_options,
                                                          pf_results=self.power_flow.results)

                        # self.threadpool.start(self.short_circuit)
                        # self.threadpool.waitForDone()
                        # self.post_short_circuit()

                        try:
                            self.threadpool.start(self.short_circuit)
                            self.threadpool.waitForDone()
                            self.post_short_circuit()

                        except Exception as ex:
                            exc_type, exc_value, exc_traceback = sys.exc_info()
                            self.msg(str(exc_traceback) + '\n' + str(exc_value), 'Short circuit')
                            self.short_circuit = None
                            self.UNLOCK()

                else:
                    self.msg(
                        'Run a power flow simulation first.\nThe results are needed to initialize this simulation.')
            else:
                self.msg('Another short circuit is being executed now...')
        else:
            pass

    def post_short_circuit(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        # update the results in the circuit structures
        if self.power_flow.results is not None:

            self.remove_simulation(SimulationTypes.ShortCircuit_run)

            self.ui.progress_label.setText('Colouring short circuit results in the grid...')
            QtGui.QGuiApplication.processEvents()

            colour_the_schematic(circuit=self.circuit,
                                 s_bus=self.short_circuit.results.Sbus,
                                 s_branch=self.short_circuit.results.Sbranch,
                                 voltages=self.short_circuit.results.voltage,
                                 types=self.short_circuit.results.bus_types,
                                 loadings=self.short_circuit.results.loading)
            self.update_available_results()
        else:
            warn('Something went wrong, There are no power flow results.')

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def run_ptdf(self):
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if len(self.circuit.buses) > 0:
            if SimulationTypes.PTDF_run not in self.stuff_running_now:

                self.add_simulation(SimulationTypes.PTDF_run)

                if len(self.circuit.buses) > 0:
                    self.LOCK()

                    pf_options = self.get_selected_power_flow_options()

                    options = PTDFOptions(group_by_technology=self.ui.group_by_gen_technology_checkBox.isChecked(),
                                          use_multi_threading=self.ui.use_multiprocessing_checkBox.isChecked(),
                                          power_increment=self.ui.ptdf_power_delta_doubleSpinBox.value())

                    self.ptdf_analysis = PTDF(grid=self.circuit, options=options, pf_options=pf_options)

                    self.ui.progress_label.setText('Running optimal power flow...')
                    QtGui.QGuiApplication.processEvents()

                    self.ptdf_analysis.progress_signal.connect(self.ui.progressBar.setValue)
                    self.ptdf_analysis.progress_text.connect(self.ui.progress_label.setText)
                    self.ptdf_analysis.done_signal.connect(self.post_ptdf)

                    self.ptdf_analysis.start()
            else:
                self.msg('Another PTDF is being executed now...')
        else:
            pass

    def post_ptdf(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        self.remove_simulation(SimulationTypes.PTDF_run)

        # update the results in the circuit structures
        if not self.ptdf_analysis.__cancel__:
            if self.ptdf_analysis.results is not None:

                self.ui.progress_label.setText('Colouring PTDF results in the grid...')
                QtGui.QGuiApplication.processEvents()

                self.update_available_results()
            else:
                self.msg('Something went wrong, There are no PTDF results.')

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def run_otdf(self):
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if len(self.circuit.buses) > 0:
            if SimulationTypes.OTDF_run not in self.stuff_running_now:

                self.add_simulation(SimulationTypes.OTDF_run)

                if len(self.circuit.buses) > 0:
                    self.LOCK()

                    pf_options = self.get_selected_power_flow_options()

                    options = NMinusKOptions(use_multi_threading=self.ui.use_multiprocessing_checkBox.isChecked())

                    self.otdf_analysis = NMinusK(grid=self.circuit, options=options, pf_options=pf_options)

                    self.otdf_analysis.progress_signal.connect(self.ui.progressBar.setValue)
                    self.otdf_analysis.progress_text.connect(self.ui.progress_label.setText)
                    self.otdf_analysis.done_signal.connect(self.post_otdf)

                    self.otdf_analysis.start()
            else:
                self.msg('Another OTDF is being executed now...')
        else:
            pass

    def post_otdf(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        self.remove_simulation(SimulationTypes.OTDF_run)

        # update the results in the circuit structures
        if not self.otdf_analysis.__cancel__:
            if self.otdf_analysis.results is not None:

                self.ui.progress_label.setText('Colouring PTDF results in the grid...')
                QtGui.QGuiApplication.processEvents()

                self.update_available_results()
            else:
                self.msg('Something went wrong, There are no PTDF results.')

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def get_selected_voltage_stability(self):
        """
        Gather the voltage stability options
        :return:
        """
        use_alpha = self.ui.start_vs_from_default_radioButton.isChecked()

        alpha = self.ui.alpha_doubleSpinBox.value()

        use_profiles = self.ui.start_vs_from_selected_radioButton.isChecked()

        start_idx = self.ui.vs_departure_comboBox.currentIndex()

        end_idx = self.ui.vs_target_comboBox.currentIndex()

        return use_alpha, alpha, use_profiles, start_idx, end_idx

    def run_voltage_stability(self):
        """
        Run voltage stability (voltage collapse) in a separated thread
        :return:
        """

        if len(self.circuit.buses) > 0:

            if SimulationTypes.VoltageCollapse_run not in self.stuff_running_now:

                # get the selected UI options
                use_alpha, alpha, use_profiles, start_idx, end_idx = self.get_selected_voltage_stability()

                mode = self.ui.vc_stop_at_comboBox.currentText()

                vc_stop_at_dict = {VCStopAt.Nose.value: VCStopAt.Nose,
                                   VCStopAt.Full.value: VCStopAt.Full}

                # declare voltage collapse options
                vc_options = VoltageCollapseOptions(step=0.0001,
                                                    approximation_order=VCParametrization.Natural,
                                                    adapt_step=True,
                                                    step_min=0.00001,
                                                    step_max=0.2,
                                                    error_tol=1e-3,
                                                    tol=1e-6,
                                                    max_it=20,
                                                    stop_at=vc_stop_at_dict[mode],
                                                    verbose=False)

                if use_alpha:
                    '''
                    use the current power situation as start
                    and a linear combination of the current situation as target
                    '''
                    if self.power_flow is not None:
                        # lock the UI
                        self.LOCK()

                        self.ui.progress_label.setText('Compiling the grid...')
                        QtGui.QGuiApplication.processEvents()
                        # self.compile()

                        n = len(self.circuit.buses)
                        #  compose the base power
                        Sbase = self.power_flow.results.Sbus

                        vc_inputs = VoltageCollapseInput(Sbase=Sbase,
                                                         Vbase=self.power_flow.results.voltage,
                                                         Starget=Sbase * alpha)

                        # create object
                        self.voltage_stability = VoltageCollapse(circuit=self.circuit, options=vc_options,
                                                                 inputs=vc_inputs)

                        # make connections
                        self.voltage_stability.progress_signal.connect(self.ui.progressBar.setValue)
                        self.voltage_stability.progress_text.connect(self.ui.progress_label.setText)
                        self.voltage_stability.done_signal.connect(self.post_voltage_stability)

                        # thread start
                        self.voltage_stability.start()
                    else:
                        self.msg('Run a power flow simulation first.\n'
                                 'The results are needed to initialize this simulation.')

                elif use_profiles:
                    '''
                    Here the start and finish power states are taken from the profiles
                    '''
                    if start_idx > -1 and end_idx > -1:

                        # lock the UI
                        self.LOCK()

                        # self.compile()

                        self.power_flow.run_at(start_idx)

                        vc_inputs = VoltageCollapseInput(
                            Sbase=self.circuit.time_series_input.Sprof.values[start_idx, :],
                            Vbase=self.power_flow.results.voltage,
                            Starget=self.circuit.time_series_input.Sprof.values[end_idx, :])

                        # create object
                        self.voltage_stability = VoltageCollapse(circuit=self.circuit, options=vc_options,
                                                                 inputs=vc_inputs)

                        # make connections
                        self.voltage_stability.progress_signal.connect(self.ui.progressBar.setValue)
                        self.voltage_stability.done_signal.connect(self.post_voltage_stability)

                        # thread start
                        self.voltage_stability.start()
                    else:
                        self.msg('Check the selected start and finnish time series indices.')
            else:
                self.msg('Another voltage collapse simulation is running...')
        else:
            pass

    def post_voltage_stability(self):
        """
        Actions performed after the voltage stability. Launched by the thread after its execution
        :return:
        """
        if self.voltage_stability.results is not None:

            self.remove_simulation(SimulationTypes.VoltageCollapse_run)

            if self.voltage_stability.results.voltages is not None:
                V = self.voltage_stability.results.voltages[-1, :]

                colour_the_schematic(circuit=self.circuit,
                                     s_bus=self.voltage_stability.results.Sbus,
                                     s_branch=self.voltage_stability.results.Sbranch,
                                     voltages=V,
                                     loadings=self.voltage_stability.results.loading,
                                     types=self.voltage_stability.results.bus_types)
                self.update_available_results()
            else:
                self.msg('The voltage stability did not converge.\nIs this case already at the collapse limit?')
        else:
            warn('Something went wrong, There are no voltage stability results.')

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def run_time_series(self):
        """
        Run a time series power flow simulation in a separated thread from the gui
        @return:
        """
        if len(self.circuit.buses) > 0:
            if SimulationTypes.TimeSeries_run not in self.stuff_running_now:
                if self.circuit.time_profile is not None:

                    self.LOCK()

                    self.add_simulation(SimulationTypes.TimeSeries_run)

                    self.ui.progress_label.setText('Compiling the grid...')
                    QtGui.QGuiApplication.processEvents()

                    use_opf_vals = self.ui.actionUse_OPF_in_TS.isChecked()

                    if self.optimal_power_flow_time_series is None:
                        if use_opf_vals:
                            use_opf_vals = False
                            self.msg('There are no OPF time series, '
                                     'therefore this operation will not use OPF information.')
                            self.ui.actionUse_OPF_in_TS.setChecked(False)

                        opf_time_series_results = None
                    else:
                        if self.optimal_power_flow_time_series.results is not None:
                            opf_time_series_results = self.optimal_power_flow_time_series.results
                        else:
                            self.msg('There are no OPF time series results, '
                                     'therefore this operation will not use OPF information.')
                            self.ui.actionUse_OPF_in_TS.setChecked(False)
                            opf_time_series_results = None
                            use_opf_vals = False

                    options = self.get_selected_power_flow_options()
                    start = self.ui.profile_start_slider.value()
                    end = self.ui.profile_end_slider.value() + 1

                    self.time_series = TimeSeries(grid=self.circuit, options=options,
                                                  use_opf_vals=use_opf_vals,
                                                  opf_time_series_results=opf_time_series_results,
                                                  start_=start, end_=end)

                    # Set the time series run options
                    self.time_series.progress_signal.connect(self.ui.progressBar.setValue)
                    self.time_series.progress_text.connect(self.ui.progress_label.setText)
                    self.time_series.done_signal.connect(self.post_time_series)

                    self.time_series.start()

                else:
                    self.msg('There are no time series.', 'Time series')
            else:
                self.msg('Another time series power flow is being executed now...')
        else:
            pass

    def post_time_series(self):
        """
        Events to do when the time series simulation has finished
        @return:
        """

        if self.time_series.results is not None:

            self.remove_simulation(SimulationTypes.TimeSeries_run)

            voltage = self.time_series.results.voltage.max(axis=0)
            loading = self.time_series.results.loading.max(axis=0)
            Sbranch = self.time_series.results.Sbranch.max(axis=0)

            colour_the_schematic(circuit=self.circuit,
                                 s_bus=None, s_branch=Sbranch, voltages=voltage, loadings=loading,
                                 types=self.time_series.results.bus_types)

            self.update_available_results()

        else:
            print('No results for the time series simulation.')

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def run_stochastic(self):
        """
        Run a Monte Carlo simulation
        @return:
        """

        if len(self.circuit.buses) > 0:

            if SimulationTypes.MonteCarlo_run not in self.stuff_running_now:

                if self.circuit.time_profile is not None:

                    self.LOCK()

                    self.add_simulation(SimulationTypes.MonteCarlo_run)

                    self.ui.progress_label.setText('Compiling the grid...')
                    QtGui.QGuiApplication.processEvents()
                    # self.compile()  # compiles inside

                    options = self.get_selected_power_flow_options()

                    tol = 10 ** (-1 * self.ui.tolerance_stochastic_spinBox.value())
                    max_iter = self.ui.max_iterations_stochastic_spinBox.value()
                    self.monte_carlo = MonteCarlo(self.circuit, options, mc_tol=tol, batch_size=100,
                                                  max_mc_iter=max_iter)

                    self.monte_carlo.progress_signal.connect(self.ui.progressBar.setValue)
                    self.monte_carlo.progress_text.connect(self.ui.progress_label.setText)
                    self.monte_carlo.done_signal.connect(self.post_stochastic)

                    self.monte_carlo.start()
                else:
                    self.msg('There are no time series.')

            else:
                self.msg('Another Monte Carlo simulation is running...')

        else:
            # self.msg('There are no time series.')
            pass

    def post_stochastic(self):
        """
        Actions to perform after the Monte Carlo simulation is finished
        @return:
        """
        if not self.monte_carlo.__cancel__:

            self.remove_simulation(SimulationTypes.MonteCarlo_run)

            colour_the_schematic(circuit=self.circuit,
                                 voltages=self.monte_carlo.results.voltage,
                                 loadings=self.monte_carlo.results.loading,
                                 s_branch=self.monte_carlo.results.sbranch,
                                 types=self.monte_carlo.results.bus_types,
                                 s_bus=None)
            self.update_available_results()

        else:
            pass

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def run_lhs(self):
        """
        Run a Monte Carlo simulation with Latin-Hypercube sampling
        @return:
        """

        if len(self.circuit.buses) > 0:

            if SimulationTypes.LatinHypercube_run not in self.stuff_running_now:

                if self.circuit.time_profile is not None:

                    self.add_simulation(SimulationTypes.LatinHypercube_run)

                    self.LOCK()

                    self.ui.progress_label.setText('Compiling the grid...')
                    QtGui.QGuiApplication.processEvents()
                    # self.compile()  # compiles inside

                    options = self.get_selected_power_flow_options()

                    sampling_points = self.ui.lhs_samples_number_spinBox.value()

                    self.latin_hypercube_sampling = LatinHypercubeSampling(self.circuit, options, sampling_points)

                    self.latin_hypercube_sampling.progress_signal.connect(self.ui.progressBar.setValue)
                    self.latin_hypercube_sampling.progress_text.connect(self.ui.progress_label.setText)
                    self.latin_hypercube_sampling.done_signal.connect(self.post_lhs)

                    self.latin_hypercube_sampling.start()
                else:
                    self.msg('There are no time series.')
            else:
                self.msg('Another latin hypercube is being sampled...')
        else:
            pass

    def post_lhs(self):
        """
        Actions to perform after the Monte Carlo simulation is finished
        @return:
        """

        self.remove_simulation(SimulationTypes.LatinHypercube_run)

        if not self.latin_hypercube_sampling.__cancel__:
            colour_the_schematic(circuit=self.circuit,
                                 voltages=self.latin_hypercube_sampling.results.voltage,
                                 loadings=self.latin_hypercube_sampling.results.loading,
                                 types=self.latin_hypercube_sampling.results.bus_types,
                                 s_branch=self.latin_hypercube_sampling.results.sbranch,
                                 s_bus=None)
            self.update_available_results()

        else:
            pass

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def clear_cascade(self):
        """
        Clear cascade simulation
        """
        self.cascade = None
        self.ui.cascade_tableView.setModel(None)

    def run_cascade_step(self):
        """
        Run cascade step
        """
        if len(self.circuit.buses) > 0:

            self.LOCK()

            if self.cascade is None:
                options = self.get_selected_power_flow_options()
                options.solver_type = SolverType.LM
                max_isl = self.ui.cascading_islands_spinBox.value()
                self.cascade = Cascading(self.circuit.copy(), options, max_additional_islands=max_isl)

            self.cascade.perform_step_run()

            self.post_cascade()

            self.UNLOCK()

    def run_cascade(self):
        """
        Run a cascading to blackout simulation
        """
        # print('run_cascade')

        if len(self.circuit.buses) > 0:

            if SimulationTypes.Cascade_run not in self.stuff_running_now:

                self.add_simulation(SimulationTypes.Cascade_run)

                self.LOCK()

                self.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()
                # self.compile()  # compiles inside

                options = self.get_selected_power_flow_options()
                options.solver_type = SolverType.LM

                max_isl = self.ui.cascading_islands_spinBox.value()
                n_lsh_samples = self.ui.lhs_samples_number_spinBox.value()

                self.cascade = Cascading(self.circuit.copy(), options,
                                         max_additional_islands=max_isl,
                                         n_lhs_samples_=n_lsh_samples)

                # connect signals
                self.cascade.progress_signal.connect(self.ui.progressBar.setValue)
                self.cascade.progress_text.connect(self.ui.progress_label.setText)
                self.cascade.done_signal.connect(self.post_cascade)

                # run
                self.cascade.start()

            else:
                self.msg('Another cascade is running...')
        else:
            pass

    def post_cascade(self, idx=None):
        """
        Actions to perform after the cascade simulation is finished
        """

        # update the results in the circuit structures

        self.remove_simulation(SimulationTypes.Cascade_run)

        n = len(self.cascade.results.events)

        if n > 0:

            # display the last event, if none is selected
            if idx is None:
                idx = n - 1

            # Accumulate all the failed branches
            br_idx = zeros(0, dtype=int)
            for i in range(idx):
                br_idx = np.r_[br_idx, self.cascade.results.events[i].removed_idx]

            # pick the results at the designated cascade step
            results = self.cascade.results.events[idx].pf_results  # MonteCarloResults object

            # print grid
            colour_the_schematic(circuit=self.circuit,
                                 voltages=results.voltage,
                                 loadings=results.loading,
                                 types=results.bus_types,
                                 s_branch=results.sbranch,
                                 s_bus=None,
                                 failed_br_idx=br_idx)

            # Set cascade table
            self.ui.cascade_tableView.setModel(PandasModel(self.cascade.get_table()))

            # Update results
            self.update_available_results()

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def cascade_table_click(self):
        """
        Display cascade upon cascade scenario click
        Returns:

        """

        idx = self.ui.cascade_tableView.currentIndex()
        if idx.row() > -1:
            self.post_cascade(idx=idx.row())

    def run_opf(self):
        """
        Run OPF simulation
        """
        if len(self.circuit.buses) > 0:

            if SimulationTypes.OPF_run not in self.stuff_running_now:

                self.remove_simulation(SimulationTypes.OPF_run)

                self.LOCK()

                # get the power flow options from the GUI
                solver = self.lp_solvers_dict[self.ui.lpf_solver_comboBox.currentText()]
                mip_solver = self.mip_solvers_dict[self.ui.mip_solver_comboBox.currentText()]
                pf_options = self.get_selected_power_flow_options()
                options = OptimalPowerFlowOptions(solver=solver,
                                                  mip_solver=mip_solver,
                                                  power_flow_options=pf_options)

                self.ui.progress_label.setText('Running optimal power flow...')
                QtGui.QGuiApplication.processEvents()
                # set power flow object instance
                self.optimal_power_flow = OptimalPowerFlow(self.circuit, options)

                self.optimal_power_flow.progress_signal.connect(self.ui.progressBar.setValue)
                self.optimal_power_flow.progress_text.connect(self.ui.progress_label.setText)
                self.optimal_power_flow.done_signal.connect(self.post_opf)

                self.optimal_power_flow.start()

            else:
                self.msg('Another OPF is being run...')
        else:
            pass

    def post_opf(self):
        """
        Actions to run after the OPF simulation
        """
        if self.optimal_power_flow is not None:

            self.remove_simulation(SimulationTypes.OPF_run)

            if self.optimal_power_flow.results.converged:

                colour_the_schematic(circuit=self.circuit,
                                     voltages=self.optimal_power_flow.results.voltage,
                                     loadings=self.optimal_power_flow.results.loading,
                                     types=self.optimal_power_flow.results.bus_types,
                                     s_branch=self.optimal_power_flow.results.Sbranch,
                                     s_bus=self.optimal_power_flow.results.Sbus)
                self.update_available_results()

            else:

                self.msg('Some islands did not solve.\n'
                         'Check that all branches have rating and \n'
                         'that there is a generator at the slack node.', 'OPF')

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def run_opf_time_series(self):
        """
        OPF Time Series run
        :return:
        """
        if len(self.circuit.buses) > 0:

            if SimulationTypes.OPFTimeSeries_run not in self.stuff_running_now:

                if self.circuit.time_profile is not None:

                    self.add_simulation(SimulationTypes.OPFTimeSeries_run)

                    self.LOCK()

                    # Compile the grid
                    self.ui.progress_label.setText('Compiling the grid...')
                    QtGui.QGuiApplication.processEvents()

                    # get the power flow options from the GUI
                    solver = self.lp_solvers_dict[self.ui.lpf_solver_comboBox.currentText()]
                    mip_solver = self.mip_solvers_dict[self.ui.mip_solver_comboBox.currentText()]
                    grouping = self.opf_time_groups[self.ui.opf_time_grouping_comboBox.currentText()]
                    pf_options = self.get_selected_power_flow_options()

                    options = OptimalPowerFlowOptions(solver=solver,
                                                      grouping=grouping,
                                                      mip_solver=mip_solver,
                                                      power_flow_options=pf_options)

                    start = self.ui.profile_start_slider.value()
                    end = self.ui.profile_end_slider.value() + 1

                    # create the OPF time series instance
                    # if non_sequential:
                    self.optimal_power_flow_time_series = OptimalPowerFlowTimeSeries(grid=self.circuit,
                                                                                     options=options,
                                                                                     start_=start,
                                                                                     end_=end)

                    # make the thread connections to the GUI
                    self.optimal_power_flow_time_series.progress_signal.connect(self.ui.progressBar.setValue)
                    self.optimal_power_flow_time_series.progress_text.connect(self.ui.progress_label.setText)
                    self.optimal_power_flow_time_series.done_signal.connect(self.post_opf_time_series)

                    # Run
                    self.optimal_power_flow_time_series.start()

                else:
                    self.msg('There are no time series.\nLoad time series are needed for this simulation.')

            else:
                self.msg('Another OPF time series is running already...')

        else:
            pass

    def post_opf_time_series(self):
        """
        Post OPF Time Series
        :return:
        """
        if self.optimal_power_flow_time_series is not None:

            if len(self.optimal_power_flow_time_series.logger) > 0:
                dlg = LogsDialogue('logger', self.optimal_power_flow_time_series.logger)
                dlg.exec_()

            # remove from the current simulations
            self.remove_simulation(SimulationTypes.OPFTimeSeries_run)

            if self.optimal_power_flow_time_series.results is not None:
                voltage = self.optimal_power_flow_time_series.results.voltage.max(axis=0)
                loading = self.optimal_power_flow_time_series.results.loading.max(axis=0)
                Sbranch = self.optimal_power_flow_time_series.results.Sbranch.max(axis=0)

                colour_the_schematic(circuit=self.circuit,
                                     s_bus=None, s_branch=Sbranch, voltages=voltage, loadings=loading,
                                     types=self.optimal_power_flow_time_series.results.bus_types)

                self.update_available_results()

                msg = 'OPF time series elapsed ' + str(self.optimal_power_flow_time_series.elapsed) + ' s'
                self.console_msg(msg)

        else:
            pass

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def run_transient_stability(self):
        """
        Run transient stability
        """
        if len(self.circuit.buses) > 0:

            if self.power_flow is not None:

                # Since we must run this study in the same conditions as
                # the last power flow, no compilation is needed

                self.LOCK()

                self.add_simulation(SimulationTypes.TransientStability_run)

                options = TransientStabilityOptions()
                options.t_sim = self.ui.transient_time_span_doubleSpinBox.value()
                options.h = self.ui.transient_time_step_doubleSpinBox.value()
                self.transient_stability = TransientStability(self.circuit,
                                                              options,
                                                              self.power_flow.results)

                try:
                    self.transient_stability.progress_signal.connect(self.ui.progressBar.setValue)
                    self.transient_stability.progress_text.connect(self.ui.progress_label.setText)
                    self.transient_stability.done_signal.connect(self.post_transient_stability)

                    # Run
                    self.transient_stability.start()

                except Exception as ex:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    self.msg(str(exc_traceback) + '\n' + str(exc_value), 'Transient stability')
                    self.transient_stability = None
                    self.UNLOCK()

            else:
                self.msg('Run a power flow simulation first.\nThe results are needed to initialize this simulation.')
        else:
            pass

    def post_transient_stability(self):
        """
        Executed when the transient stability is done
        :return:
        """
        self.remove_simulation(SimulationTypes.TransientStability_run)

        self.update_available_results()

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def copy_opf_to_time_series(self):
        """
        Copy the OPF generation values to the Time series object and execute a time series simulation
        :return:
        """
        if len(self.circuit.buses) > 0:

            if self.circuit.time_profile is not None:

                if self.optimal_power_flow_time_series is not None:

                    quit_msg = "Are you sure that you want overwrite the time events " \
                               "with the simulated by the OPF time series?"
                    reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

                    if reply == QMessageBox.Yes:

                        self.circuit.apply_lp_profiles()

                    else:
                        pass

                else:
                    self.msg('There are no OPF time series execution.'
                             '\nRun OPF time series to be able to copy the value to the time series object.')

            else:
                self.msg('There are no time series.\nLoad time series are needed for this simulation.')
        else:
            pass

    def reduce_grid(self):
        """
        Reduce grid by removing branches and nodes according to the selected options
        """

        if len(self.circuit.buses) > 0:

            if SimulationTypes.TopologyReduction_run not in self.stuff_running_now:

                # compute the options
                rx_criteria = self.ui.rxThresholdCheckBox.isChecked()
                exponent = self.ui.rxThresholdSpinBox.value()
                rx_threshold = 1.0 / (10.0 ** exponent)
                # type_criteria = self.ui.removeByTypeCheckBox.isChecked()
                # selected_type_txt = self.ui.removeByTypeComboBox.currentText()
                # selected_type = BranchTypeConverter(BranchType.Branch).conv[selected_type_txt]

                # get the selected indices
                checked = get_checked_indices(self.ui.removeByTypeListView.model())

                if len(checked) > 0:

                    selected_types = list()
                    for i in checked:
                        selected_type_txt = self.ui.removeByTypeListView.model().item(i).text()
                        selected_type = BranchTypeConverter(BranchType.Branch).conv[selected_type_txt]
                        selected_types.append(selected_type)

                    # compose options
                    options = TopologyReductionOptions(rx_criteria=rx_criteria,
                                                       rx_threshold=rx_threshold,
                                                       selected_types=selected_types)

                    # find which branches to remove
                    br_to_remove = select_branches_to_reduce(circuit=self.circuit,
                                                             rx_criteria=options.rx_criteria,
                                                             rx_threshold=options.rx_threshold,
                                                             selected_types=options.selected_type)
                    if len(br_to_remove) > 0:
                        # raise dialogue
                        elms = [self.circuit.branches[i] for i in br_to_remove]
                        diag = ElementsDialogue('Elements to be reduced', elms)
                        diag.show()
                        diag.exec_()

                        if diag.accepted:

                            self.LOCK()

                            self.add_simulation(SimulationTypes.TopologyReduction_run)

                            # reduce the grid
                            self.topology_reduction = TopologyReduction(grid=self.circuit, branch_indices=br_to_remove)

                            # Set the time series run options
                            self.topology_reduction.progress_signal.connect(self.ui.progressBar.setValue)
                            self.topology_reduction.progress_text.connect(self.ui.progress_label.setText)
                            self.topology_reduction.done_signal.connect(self.post_reduce_grid)

                            self.topology_reduction.start()
                        else:
                            pass
                    else:
                        self.msg('There were no branches identified', 'Topological grid reduction')
                else:
                    self.msg('Select at least one reduction option in the topology settings',
                             'Topological grid reduction')
            else:
                self.msg('Another topological reduction is being conducted...', 'Topological grid reduction')
        else:
            pass

    def post_reduce_grid(self):
        """
        Actions after reducing
        """

        self.remove_simulation(SimulationTypes.TopologyReduction_run)

        self.create_schematic_from_api(explode_factor=1)

        self.clear_results()

        if len(self.stuff_running_now) == 0:
            self.UNLOCK()

    def storage_location(self):

        """
        Add storage markers to the schematic
        """

        if len(self.circuit.buses) > 0:

            if self.ui.actionStorage_location_suggestion.isChecked():

                if self.time_series is not None:

                    # get the numerical object of the circuit
                    numeric_circuit = self.circuit.compile()

                    # perform a time series analysis
                    ts_analysis = TimeSeriesResultsAnalysis(numeric_circuit, self.time_series.results)

                    # get the indices of the buses selected for storage
                    idx = np.where(ts_analysis.buses_selected_for_storage_frequency > 0)[0]

                    if len(idx) > 0:

                        frequencies = ts_analysis.buses_selected_for_storage_frequency[idx]

                        fmax = np.max(frequencies)

                        # prepare the color map
                        seq = [(0, 'green'),
                               (0.6, 'orange'),
                               (1.0, 'red')]
                        cmap = LinearSegmentedColormap.from_list('vcolors', seq)

                        self.buses_for_storage = list()

                        for i, freq in zip(idx, frequencies):

                            bus = self.circuit.buses[i]
                            self.buses_for_storage.append(bus)

                            # add a marker to the bus if there are no batteries in it
                            if bus.graphic_obj.big_marker is None and len(bus.batteries) == 0:
                                r, g, b, a = cmap(freq / fmax)
                                color = QColor(r * 255, g * 255, b * 255, a * 255)
                                bus.graphic_obj.add_big_marker(color=color)
                    else:

                        self.msg('No problems were detected, therefore no storage is suggested', 'Storage location')

                else:
                    self.msg('There is no time series simulation.\n It is needed for this functionality.',
                             'Storage location')

            else:

                # delete the red dots
                if self.buses_for_storage is not None:

                    for bus in self.buses_for_storage:
                        # add a marker to the bus...
                        if bus.graphic_obj.big_marker is not None:
                            bus.graphic_obj.delete_big_marker()
                else:
                    pass
        else:
            pass

    def set_cancel_state(self):
        """
        Cancel whatever's going on that can be cancelled
        @return:
        """

        '''
        self.power_flow = None
        self.short_circuit = None
        self.monte_carlo = None
        self.time_series = None
        self.voltage_stability = None
        self.latin_hypercube_sampling = None
        self.cascade = None
        self.optimal_power_flow = None
        self.optimal_power_flow_time_series = None
        self.transient_stability = None
        self.topology_reduction = None

        '''

        reply = QMessageBox.question(self, 'Message', 'Are you sure that you want to cancel the simulation?',
                                     QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # send the cancel state to whatever it is being executed

            if self.power_flow is not None:
                self.power_flow.cancel()

            if self.monte_carlo is not None:
                self.monte_carlo.cancel()

            if self.time_series is not None:
                self.time_series.cancel()

            if self.voltage_stability is not None:
                self.voltage_stability.cancel()

            if self.latin_hypercube_sampling is not None:
                self.latin_hypercube_sampling.cancel()

            if self.optimal_power_flow_time_series is not None:
                self.optimal_power_flow_time_series.cancel()

            if self.cascade is not None:
                self.cascade.cancel()

            if self.ptdf_analysis is not None:
                self.ptdf_analysis.cancel()
        else:
            pass

    def get_available_results(self):
        """
        Get a list of all the available results' objects
        :return: list[object]
        """
        lst = list()

        if self.power_flow is not None:
            if self.power_flow.results is not None:
                lst.append(self.power_flow)

        if self.voltage_stability is not None:
            if self.voltage_stability.results is not None:
                lst.append(self.voltage_stability)

        if self.time_series is not None:
            if self.time_series.results is not None:
                lst.append(self.time_series)

        if self.monte_carlo is not None:
            if self.monte_carlo.results is not None:
                lst.append(self.monte_carlo)

        if self.latin_hypercube_sampling is not None:
            if self.latin_hypercube_sampling.results is not None:
                lst.append(self.latin_hypercube_sampling)

        if self.short_circuit is not None:
            if self.short_circuit.results is not None:
                lst.append(self.short_circuit)

        if self.optimal_power_flow is not None:
            if self.optimal_power_flow.results is not None:
                lst.append(self.optimal_power_flow)

        if self.optimal_power_flow_time_series is not None:
            if self.optimal_power_flow_time_series.results is not None:
                lst.append(self.optimal_power_flow_time_series)

        if self.transient_stability is not None:
            if self.transient_stability.results is not None:
                lst.append(self.transient_stability)

        if self.ptdf_analysis is not None:
            if self.ptdf_analysis.results is not None:
                lst.append(self.ptdf_analysis)

        if self.otdf_analysis is not None:
            if self.otdf_analysis.results is not None:
                lst.append(self.otdf_analysis)

        return lst

    def update_available_results(self):
        """
        Update the results that are displayed in the results tab
        """
        lst = list()
        self.available_results_dict = dict()
        self.available_results_steps_dict = dict()

        # clear results lists
        self.ui.result_type_listView.setModel(None)
        self.ui.result_element_selection_listView.setModel(None)

        available_results = self.get_available_results()

        for driver in available_results:
            lst.append(driver.name)
            self.available_results_dict[driver.name] = driver.results.available_results
            self.available_results_steps_dict[driver.name] = driver.get_steps()
        #
        #
        # if self.power_flow is not None:
        #     if self.power_flow.results is not None:
        #         lst.append("Power Flow")
        #         self.available_results_dict["Power Flow"] = self.power_flow.results.available_results
        #         self.available_results_steps_dict["Power Flow"] = self.power_flow.get_steps()
        #
        # if self.voltage_stability is not None:
        #     if self.voltage_stability.results is not None:
        #         lst.append("Voltage Stability")
        #         self.available_results_dict["Voltage Stability"] = self.voltage_stability.results.available_results
        #         self.available_results_steps_dict["Voltage Stability"] = self.voltage_stability.get_steps()
        #
        # if self.time_series is not None:
        #     if self.time_series.results is not None:
        #         lst.append("Time Series")
        #         self.available_results_dict["Time Series"] = self.time_series.results.available_results
        #         self.available_results_steps_dict["Time Series"] = self.time_series.get_steps()
        #
        # if self.monte_carlo is not None:
        #     if self.monte_carlo.results is not None:
        #         lst.append("Monte Carlo")
        #         self.available_results_dict["Monte Carlo"] = self.monte_carlo.results.available_results
        #         self.available_results_steps_dict["Monte Carlo"] = self.monte_carlo.get_steps()
        #
        # if self.latin_hypercube_sampling is not None:
        #     if self.latin_hypercube_sampling.results is not None:
        #         lst.append("Latin Hypercube")
        #         self.available_results_dict["Latin Hypercube"] = self.latin_hypercube_sampling.results.available_results
        #         self.available_results_steps_dict["Latin Hypercube"] = self.latin_hypercube_sampling.get_steps()
        #
        # if self.short_circuit is not None:
        #     if self.short_circuit.results is not None:
        #         lst.append("Short Circuit")
        #         self.available_results_dict["Short Circuit"] = self.short_circuit.results.available_results
        #         self.available_results_steps_dict["Short Circuit"] = self.short_circuit.get_steps()
        #
        # if self.optimal_power_flow is not None:
        #     if self.optimal_power_flow.results is not None:
        #         lst.append("Optimal power flow")
        #         self.available_results_dict["Optimal power flow"] = self.optimal_power_flow.results.available_results
        #         self.available_results_steps_dict["Optimal power flow"] = self.optimal_power_flow.get_steps()
        #
        # if self.optimal_power_flow_time_series is not None:
        #     if self.optimal_power_flow_time_series.results is not None:
        #         lst.append("Optimal power flow time series")
        #         self.available_results_dict[
        #             "Optimal power flow time series"] = self.optimal_power_flow_time_series.results.available_results
        #         self.available_results_steps_dict[
        #             "Optimal power flow time series"] = self.optimal_power_flow_time_series.get_steps()
        #
        # if self.transient_stability is not None:
        #     if self.transient_stability.results is not None:
        #         lst.append("Transient stability")
        #         self.available_results_dict["Transient stability"] = self.transient_stability.results.available_results
        #         self.available_results_steps_dict["Transient stability"] = self.transient_stability.get_steps()
        #
        # if self.ptdf_analysis is not None:
        #     if self.ptdf_analysis.results is not None:
        #         lst.append("PTDF")
        #         self.available_results_dict["PTDF"] = self.ptdf_analysis.results.available_results
        #         self.available_results_steps_dict["PTDF"] = self.ptdf_analysis.get_steps()
        #
        # if self.otdf_analysis is not None:
        #     if self.otdf_analysis.results is not None:
        #         lst.append("OTDF")
        #         self.available_results_dict["OTDF"] = self.otdf_analysis.results.available_results
        #         self.available_results_steps_dict["OTDF"] = self.otdf_analysis.get_steps()

        mdl = get_list_model(lst)
        self.ui.result_listView.setModel(mdl)
        self.ui.available_results_to_color_comboBox.setModel(mdl)

        if len(lst) > 1:
            self.ui.grid_colouring_frame.setVisible(True)
        else:
            self.ui.grid_colouring_frame.setVisible(False)

    def clear_results(self):
        """
        Clear the results tab
        """
        self.power_flow = None
        self.short_circuit = None
        self.monte_carlo = None
        self.time_series = None
        self.voltage_stability = None
        self.optimal_power_flow = None
        self.optimal_power_flow_time_series = None
        self.transient_stability = None
        self.ptdf_analysis = None

        self.buses_for_storage = None

        self.calculation_inputs_to_display = None
        self.ui.simulation_data_island_comboBox.clear()

        self.available_results_dict = dict()
        self.ui.result_listView.setModel(None)
        self.ui.resultsTableView.setModel(None)
        self.ui.result_type_listView.setModel(None)
        self.ui.available_results_to_color_comboBox.model().clear()
        self.ui.result_element_selection_listView.setModel(None)

        self.ui.catalogueTableView.setModel(None)

        self.ui.simulationDataStructureTableView.setModel(None)
        self.ui.profiles_tableView.setModel(None)

        self.ui.dataStructureTableView.setModel(None)
        self.ui.catalogueTreeView.setModel(None)

        self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
        self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)

    def hide_color_tool_box(self):
        """
        Hide the colour tool box
        """
        self.ui.grid_colouring_frame.setVisible(False)

    def colour_now(self):
        """
        Color the grid now
        """
        if self.ui.available_results_to_color_comboBox.currentIndex() > -1:

            current_study = self.ui.available_results_to_color_comboBox.currentText()
            current_step = self.ui.simulation_results_step_comboBox.currentIndex()

            if current_study == 'Power Flow':

                colour_the_schematic(circuit=self.circuit,
                                     s_bus=self.power_flow.results.Sbus,
                                     s_branch=self.power_flow.results.Sbranch,
                                     voltages=self.power_flow.results.voltage,
                                     loadings=self.power_flow.results.loading,
                                     types=self.circuit.numerical_circuit.bus_types,
                                     losses=self.power_flow.results.losses)

            elif current_study == 'Time Series':

                voltage = self.time_series.results.voltage[current_step, :]
                loading = self.time_series.results.loading[current_step, :]
                Sbranch = self.time_series.results.Sbranch[current_step, :]

                colour_the_schematic(circuit=self.circuit,
                                     s_bus=None,
                                     s_branch=Sbranch,
                                     voltages=voltage,
                                     loadings=loading,
                                     types=self.circuit.numerical_circuit.bus_types)

            elif current_study == 'Voltage Stability':

                colour_the_schematic(circuit=self.circuit,
                                     s_bus=self.voltage_stability.results.Sbus,
                                     s_branch=self.voltage_stability.results.Sbranch,
                                     voltages=self.voltage_stability.results.voltages[current_step, :],
                                     loadings=self.voltage_stability.results.loading,
                                     types=self.circuit.numerical_circuit.bus_types)

            elif current_study == 'Monte Carlo':

                colour_the_schematic(circuit=self.circuit,
                                     voltages=self.monte_carlo.results.V_points[current_step, :],
                                     loadings=self.monte_carlo.results.loading_points[current_step, :],
                                     s_branch=self.monte_carlo.results.Sbr_points[current_step, :],
                                     types=self.circuit.numerical_circuit.bus_types,
                                     s_bus=self.monte_carlo.results.S_points[current_step, :])

            elif current_study == 'Latin Hypercube':

                colour_the_schematic(circuit=self.circuit,
                                     voltages=self.latin_hypercube_sampling.results.V_points[current_step, :],
                                     loadings=self.latin_hypercube_sampling.results.loading_points[current_step, :],
                                     s_branch=self.latin_hypercube_sampling.results.Sbr_points[current_step, :],
                                     types=self.circuit.numerical_circuit.bus_types,
                                     s_bus=self.latin_hypercube_sampling.results.S_points[current_step, :])

            elif current_study == 'Short Circuit':
                colour_the_schematic(circuit=self.circuit,
                                     s_bus=self.short_circuit.results.Sbus,
                                     s_branch=self.short_circuit.results.Sbranch,
                                     voltages=self.short_circuit.results.voltage,
                                     types=self.circuit.numerical_circuit.bus_types,
                                     loadings=self.short_circuit.results.loading)

            elif current_study == 'Optimal power flow':
                colour_the_schematic(circuit=self.circuit,
                                     voltages=self.optimal_power_flow.results.voltage,
                                     loadings=self.optimal_power_flow.results.loading,
                                     types=self.circuit.numerical_circuit.bus_types,
                                     s_branch=self.optimal_power_flow.results.Sbranch,
                                     s_bus=self.optimal_power_flow.results.Sbus)

            elif current_study == 'Optimal power flow time series':

                voltage = self.optimal_power_flow_time_series.results.voltage[current_step, :]
                loading = self.optimal_power_flow_time_series.results.loading[current_step, :]
                Sbranch = self.optimal_power_flow_time_series.results.Sbranch[current_step, :]

                colour_the_schematic(circuit=self.circuit,
                                     s_bus=None,
                                     s_branch=Sbranch,
                                     voltages=voltage,
                                     loadings=loading,
                                     types=self.circuit.numerical_circuit.bus_types)

            elif current_study == 'PTDF':

                voltage = self.ptdf_analysis.results.pf_results[current_step].voltage
                loading = self.ptdf_analysis.results.sensitivity_matrix[current_step, :]
                Sbranch = self.ptdf_analysis.results.pf_results[current_step].Sbranch

                colour_the_schematic(circuit=self.circuit,
                                     s_bus=None,
                                     s_branch=Sbranch,
                                     voltages=voltage,
                                     loadings=loading,
                                     types=self.circuit.numerical_circuit.bus_types,
                                     loading_label='Sensitivity')

            elif current_study == 'Transient stability':
                pass

    def colour_next_simulation_step(self):
        """
        Next colour step
        """
        current_step = self.ui.simulation_results_step_comboBox.currentIndex()
        count = self.ui.simulation_results_step_comboBox.count()

        if count > 0:
            nxt = current_step + 1

            if nxt >= count:
                nxt = count - 1

            self.ui.simulation_results_step_comboBox.setCurrentIndex(nxt)

            self.colour_now()

    def colour_previous_simulation_step(self):
        """
        Prev colour step
        """
        current_step = self.ui.simulation_results_step_comboBox.currentIndex()
        count = self.ui.simulation_results_step_comboBox.count()

        if count > 0:
            prv = current_step - 1

            if prv < 0:
                prv = 0

            self.ui.simulation_results_step_comboBox.setCurrentIndex(prv)

            self.colour_now()

    def update_available_steps_to_color(self):
        """
        Update the available simulation steps in the combo box
        """
        if self.ui.available_results_to_color_comboBox.currentIndex() > -1:
            current_study = self.ui.available_results_to_color_comboBox.currentText()

            lst = self.available_results_steps_dict[current_study]

            mdl = get_list_model(lst)

            self.ui.simulation_results_step_comboBox.setModel(mdl)

    def update_available_results_in_the_study(self):
        """
        Update the available results
        """
        elm = self.ui.result_listView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)
        lst = self.available_results_dict[elm]
        mdl = EnumModel(lst)
        self.ui.result_type_listView.setModel(mdl)

    def result_type_click(self, qt_val=None, indices=None):
        """
        plot all the values for the selected result type
        :param qt_val: trash variable to store what the QT object sends
        :param indices: element indices selected for plotting
        :return: Nothing
        """

        if len(self.ui.result_listView.selectedIndexes()) > 0 and \
                len(self.ui.result_type_listView.selectedIndexes()) > 0:

            study = self.ui.result_listView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)
            study_type = self.ui.result_type_listView.model().items[
                self.ui.result_type_listView.selectedIndexes()[0].row()]

            if study_type.value[1] == DeviceType.BusDevice:
                names = self.circuit.bus_names
            elif study_type.value[1] == DeviceType.BranchDevice:
                names = self.circuit.branch_names
            elif study_type.value[1] == DeviceType.BusDevice.LoadDevice:
                names = self.circuit.get_load_names()
            elif study_type.value[1] == DeviceType.BusDevice.GeneratorDevice:
                names = self.circuit.get_controlled_generator_names()
            elif study_type.value[1] == DeviceType.BusDevice.BatteryDevice:
                names = self.circuit.get_battery_names()
            else:
                names = None

            if indices is None:
                mdl = get_list_model(names, checks=True)
                self.ui.result_element_selection_listView.setModel(mdl)

            self.results_mdl = None

            if study == PowerFlowDriver.name:
                if self.power_flow.results is not None:
                    self.results_mdl = self.power_flow.results.mdl(result_type=study_type, indices=indices, names=names)
                else:
                    self.msg('There seem to be no results :(')

            elif study == TimeSeries.name:
                if self.time_series.results is not None:
                    self.results_mdl = self.time_series.results.mdl(result_type=study_type, indices=indices, names=names)
                else:
                    self.msg('There seem to be no results :(')

            elif study == VoltageCollapse.name:
                if self.voltage_stability.results is not None:
                    self.results_mdl = self.voltage_stability.results.mdl(result_type=study_type,
                                                                          indices=indices, names=names)
                else:
                    self.msg('There seem to be no results :(')

            elif study == MonteCarlo.name:
                if self.monte_carlo.results is not None:
                    self.results_mdl = self.monte_carlo.results.mdl(result_type=study_type,
                                                                    indices=indices, names=names)
                else:
                    self.msg('There seem to be no results :(')

            elif study == LatinHypercubeSampling.name:
                if self.latin_hypercube_sampling.results is not None:
                    self.results_mdl = self.latin_hypercube_sampling.results.mdl(result_type=study_type,
                                                                                 indices=indices, names=names)
                else:
                    self.msg('There seem to be no results :(')

            elif study == ShortCircuit.name:
                if self.short_circuit.results is not None:
                    self.results_mdl = self.short_circuit.results.mdl(result_type=study_type,
                                                                      indices=indices, names=names)
                else:
                    self.msg('There seem to be no results :(')

            elif study == OptimalPowerFlow.name:
                if self.optimal_power_flow.results is not None:
                    self.results_mdl = self.optimal_power_flow.results.mdl(result_type=study_type,
                                                                           indices=indices, names=names)
                else:
                    self.msg('There seem to be no results :(')

            elif study == OptimalPowerFlowTimeSeries.name:
                if self.optimal_power_flow_time_series.results is not None:
                    self.results_mdl = self.optimal_power_flow_time_series.results.mdl(result_type=study_type,
                                                                                       indices=indices,
                                                                                       names=names)
                else:
                    self.msg('There seem to be no results :(')

            elif study == PTDF.name:
                if self.ptdf_analysis.results is not None:
                    self.results_mdl = self.ptdf_analysis.results.mdl(result_type=study_type,
                                                                      indices=indices,
                                                                      names=names)
                else:
                    self.msg('There seem to be no results :(')

            elif study == NMinusK.name:
                if self.otdf_analysis.results is not None:
                    self.results_mdl = self.otdf_analysis.results.mdl(result_type=study_type,
                                                                      indices=indices,
                                                                      names=names)
                else:
                    self.msg('There seem to be no results :(')

            if self.results_mdl is not None:
                # set the table model
                self.ui.resultsTableView.setModel(self.results_mdl)
            else:
                self.ui.resultsTableView.setModel(None)

    def plot_results(self):
        """

        :return:
        """
        if self.results_mdl is not None:

            plt.rcParams["date.autoformatter.minute"] = "%Y-%m-%d %H:%M:%S"

            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111)
            mode = self.ui.export_mode_comboBox.currentText()
            self.results_mdl.plot(ax=ax, mode=mode)
            plt.show()

    def save_results_df(self):
        """
        Save the data displayed at the results as excel
        """
        mdl = self.ui.resultsTableView.model()
        mode = self.ui.export_mode_comboBox.currentText()
        if mdl is not None:

            options = QFileDialog.Options()
            if self.use_native_dialogues:
                options |= QFileDialog.DontUseNativeDialog

            file, filter = QFileDialog.getSaveFileName(self, "Export results", '',
                                                       filter="CSV (*.csv);;Excel files (*.xlsx)",
                                                       options=options)

            if file != '':
                if 'xlsx' in filter:
                    f = file
                    if not f.endswith('.xlsx'):
                        f += '.xlsx'
                    mdl.save_to_excel(f, mode=mode)
                    print('Saved!')
                if'csv' in filter:
                    f = file
                    if not f.endswith('.csv'):
                        f += '.csv'
                    mdl.save_to_csv(f, mode=mode)
                    print('Saved!')
                else:
                    self.msg(file[0] + ' is not valid :(')
        else:
            self.msg('There is no profile displayed, please display one', 'Copy profile to clipboard')

    def copy_results_data(self):
        """
        Copy the current displayed profiles to the clipboard
        """
        mdl = self.ui.resultsTableView.model()
        mode = self.ui.export_mode_comboBox.currentText()
        if mdl is not None:
            mdl.copy_to_clipboard(mode=mode)
            print('Copied!')
        else:
            self.msg('There is no profile displayed, please display one', 'Copy profile to clipboard')

    def item_results_plot(self):
        """
        Same as result_type_click but for the selected items
        :return:
        """
        mdl = self.ui.result_element_selection_listView.model()
        if mdl is not None:
            indices = get_checked_indices(mdl)
            self.result_type_click(qt_val=None, indices=indices)

    def check_all_result_objects(self):
        """
        Check all the result objects
        :return:
        """
        mdl = self.ui.result_element_selection_listView.model()
        if mdl is not None:
            for row in range(mdl.rowCount()):
                mdl.item(row).setCheckState(QtCore.Qt.Checked)

    def check_none_result_objects(self):
        """
        Check all the result objects
        :return:
        """
        mdl = self.ui.result_element_selection_listView.model()
        if mdl is not None:
            for row in range(mdl.rowCount()):
                mdl.item(row).setCheckState(QtCore.Qt.Unchecked)

    def set_state(self):
        """
        Set the selected profiles state in the grid
        :return:
        """
        idx = self.ui.profile_time_selection_comboBox.currentIndex()

        if idx > -1:
            self.circuit.set_state(t=idx)
        else:
            self.msg('No time state selected', 'Set state')

    def set_value_to_column(self):
        """
        Set the value to all the column
        :return: Nothing
        """
        idx = self.ui.dataStructureTableView.currentIndex()
        mdl = self.ui.dataStructureTableView.model()  # is of type ObjectsModel
        col = idx.column()
        if mdl is not None:
            if col > -1:
                # print(idx.row(), idx.column())
                mdl.copy_to_column(idx)
                # update the view
                self.view_objects_data()
            else:
                self.msg('Select some element to serve as source to copy', 'Set value to column')
        else:
            pass

    def display_grid_analysis(self):
        """
        Display the grid analysis GUI
        """

        dialogue = GridAnalysisGUI(parent=self, object_types=self.grid_editor.object_types, circuit=self.circuit)
        dialogue.resize(1.61 * 600.0, 600.0)
        dialogue.setModal(False)
        dialogue.show()
        dialogue.exec_()

    def adjust_all_node_width(self):
        """
        Adapt the width of all the nodes to their names
        """
        for bus in self.circuit.buses:
            bus.graphic_obj.adapt()

    def set_up_profile_sliders(self):
        """
        Set up profiles
        :return:
        """
        if self.circuit.time_profile is not None:
            t = len(self.circuit.time_profile) - 1

            self.ui.profile_start_slider.setMinimum(0)
            self.ui.profile_start_slider.setMaximum(t)
            self.ui.profile_start_slider.setValue(0)

            self.ui.profile_end_slider.setMinimum(0)
            self.ui.profile_end_slider.setMaximum(t)
            self.ui.profile_end_slider.setValue(t)
        else:
            pass

    def change_circuit_base(self):
        """
        Update the circuit base values from the UI
        """
        self.circuit.Sbase = self.ui.sbase_doubleSpinBox.value()
        self.circuit.fBase = self.ui.fbase_doubleSpinBox.value()

    def explosion_factor_change(self):
        """
        Chenge the node explosion factor
        """
        if self.grid_editor is not None:
            self.grid_editor.expand_factor = self.ui.explosion_factor_doubleSpinBox.value()

            print('Explosion factor changed to:', self.grid_editor.expand_factor)

    def profile_sliders_changed(self):
        """
        Correct sliders if they change
        :return:
        """
        start = self.ui.profile_start_slider.value()
        end = self.ui.profile_end_slider.value()

        if start > end:
            self.ui.profile_end_slider.setValue(start)
            end = start

        if self.circuit.time_profile is not None:
            t1 = self.circuit.time_profile[start]
            t2 = self.circuit.time_profile[end]
            t1 = pd.to_datetime(t1).strftime('%d/%m/%Y %H:%M')
            t2 = pd.to_datetime(t2).strftime('%d/%m/%Y %H:%M')
            self.ui.profile_label.setText(str(t1) + ' -> ' + str(t2))

    def add_to_catalogue(self):
        """
        Add object to the catalogue
        :return:
        """
        something_happened = False
        if len(self.ui.catalogueDataStructuresListView.selectedIndexes()) > 0:

            # get the object type
            tpe = self.ui.catalogueDataStructuresListView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

            if tpe == 'Overhead lines':

                obj = Tower()
                obj.frequency = self.circuit.fBase
                obj.tower_name = 'Tower_' + str(len(self.circuit.overhead_line_types))
                self.circuit.add_overhead_line(obj)
                something_happened = True

            elif tpe == 'Underground lines':

                name = 'Cable_' + str(len(self.circuit.underground_cable_types))
                obj = UndergroundLineType(name=name)
                self.circuit.add_underground_line(obj)
                something_happened = True

            elif tpe == 'Sequence lines':

                name = 'SequenceLine_' + str(len(self.circuit.sequence_line_types))
                obj = SequenceLineType(name=name)
                self.circuit.add_sequence_line(obj)
                something_happened = True

            elif tpe == 'Wires':

                name = 'Wire_' + str(len(self.circuit.wire_types))
                obj = Wire(name=name, gmr=0.01, r=0.01, x=0)
                self.circuit.add_wire(obj)
                something_happened = True

            elif tpe == 'Transformers':

                name = 'XFormer_type_' + str(len(self.circuit.transformer_types))
                obj = TransformerType(hv_nominal_voltage=10, lv_nominal_voltage=0.4, nominal_power=2,
                                      copper_losses=0.8, iron_losses=0.1, no_load_current=0.1,
                                      short_circuit_voltage=0.1,
                                      gr_hv1=0.5, gx_hv1=0.5, name=name)
                self.circuit.add_transformer_type(obj)
                something_happened = True

            else:
                pass

        else:
            pass

        if something_happened:
            self.catalogue_element_selected()

    def edit_from_catalogue(self):
        """
        Edit catalogue element
        """
        something_happened = False
        if len(self.ui.catalogueDataStructuresListView.selectedIndexes()) > 0:

            # get the object type
            tpe = self.ui.catalogueDataStructuresListView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

            # get the selected index
            idx = self.ui.catalogueTableView.currentIndex().row()

            if idx > -1:
                if tpe == 'Overhead lines':

                    # pick the object
                    tower = self.circuit.overhead_line_types[idx]

                    # launch editor
                    dialogue = TowerBuilderGUI(tower=tower, wires_catalogue=self.circuit.wire_types)
                    dialogue.resize(1.81 * 700.0, 700.0)
                    dialogue.exec()

                    something_happened = True

                elif tpe == 'Wires':

                    self.msg('No editor available.\nThe values can be changes from within the table.', 'Wires')

                elif tpe == 'Transformers':

                    self.msg('No editor available.\nThe values can be changes from within the table.', 'Transformers')

                else:
                    pass
            else:
                self.msg('Select an element from the table')
        else:
            self.msg('Select a catalogue element and then a catalogue object')

        if something_happened:
            self.catalogue_element_selected()

    def delete_from_catalogue(self):
        """
        Delete element from catalogue
        :return:
        """
        something_happened = False
        if len(self.ui.catalogueDataStructuresListView.selectedIndexes()) > 0:

            # get the object type
            tpe = self.ui.catalogueDataStructuresListView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

            # get the selected index
            idx = self.ui.catalogueTableView.currentIndex().row()

            if idx > -1:
                if tpe == 'Overhead lines':

                    self.circuit.delete_overhead_line(idx)
                    something_happened = True

                elif tpe == 'Underground lines':

                    self.circuit.delete_underground_line(idx)
                    something_happened = True

                elif tpe == 'Sequence lines':

                    self.circuit.delete_sequence_line(idx)
                    something_happened = True

                elif tpe == 'Wires':

                    self.circuit.delete_wire(idx)
                    something_happened = True

                elif tpe == 'Transformers':

                    self.circuit.delete_transformer_type(idx)
                    something_happened = True

                else:
                    pass
            else:
                self.msg('Select an element from the table')
        else:
            self.msg('Select a catalogue element and then a catalogue object')

        if something_happened:
            self.catalogue_element_selected()

    def catalogue_element_selected(self):
        """
        Catalogue element clicked
        """

        if len(self.ui.catalogueDataStructuresListView.selectedIndexes()) > 0:

            # get the clicked type
            tpe = self.ui.catalogueDataStructuresListView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

            if tpe == 'Overhead lines':
                elm = Tower()
                mdl = ObjectsModel(self.circuit.overhead_line_types,
                                   elm.editable_headers,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_attributes=elm.non_editable_attributes,
                                   check_unique=['name'])

            elif tpe == 'Underground lines':
                elm = UndergroundLineType()
                mdl = ObjectsModel(self.circuit.underground_cable_types,
                                   elm.editable_headers,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_attributes=elm.non_editable_attributes,
                                   check_unique=['name'])

            elif tpe == 'Sequence lines':
                elm = SequenceLineType()
                mdl = ObjectsModel(self.circuit.sequence_line_types,
                                   elm.editable_headers,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_attributes=elm.non_editable_attributes,
                                   check_unique=['name'])
            elif tpe == 'Wires':
                elm = Wire(name='', gmr=0, r=0, x=0)
                mdl = ObjectsModel(self.circuit.wire_types,
                                   elm.editable_headers,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_attributes=elm.non_editable_attributes,
                                   check_unique=['name'])

            elif tpe == 'Transformers':
                elm = TransformerType(hv_nominal_voltage=10, lv_nominal_voltage=10, nominal_power=10,
                                      copper_losses=0, iron_losses=0, no_load_current=0.1, short_circuit_voltage=0.1,
                                      gr_hv1=0.5, gx_hv1=0.5)
                mdl = ObjectsModel(self.circuit.transformer_types,
                                   elm.editable_headers,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_attributes=elm.non_editable_attributes,
                                   check_unique=['name'])

            else:
                mdl = None

            # Set model
            self.ui.catalogueTableView.setModel(mdl)

        else:
            pass

    def assign_template(self):
        """
        Assign the selected branch templates
        """
        logger = Logger()

        if len(self.ui.catalogueTreeView.selectedIndexes()) > 0:

            # tree parent (category, i.e. Transformers)
            type_class = self.ui.catalogueTreeView.selectedIndexes()[0].parent().data(role=QtCore.Qt.DisplayRole)

            if type_class is not None:

                # template object name
                tpe_name = self.ui.catalogueTreeView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

                # get the compatible BRanch Type that matches the type class
                compatible_types = {'Wires': None,
                                    'Overhead lines': BranchType.Line,
                                    'Underground lines': BranchType.Line,
                                    'Sequence lines': BranchType.Line,
                                    'Transformers': BranchType.Transformer}
                compatible_type = compatible_types[type_class]

                # get catalogue dictionary of the selected type
                branch_type_dict = self.circuit.get_catalogue_dict_by_name(type_class=type_class)

                # is the name in the catalogue?
                if tpe_name in branch_type_dict.keys():

                    # get the actual object from the types dictionary
                    branch_type = branch_type_dict[tpe_name]

                    # for each unique row index
                    unique_rows = set([i.row() for i in self.ui.dataStructureTableView.selectedIndexes()])
                    for i in unique_rows:

                        # if the template and the branch types match...
                        if self.circuit.branches[i].branch_type == compatible_type:

                            # apply the branch type
                            self.circuit.branches[i].apply_template(branch_type, Sbase=self.circuit.Sbase)

                        else:
                            logger.append(str(branch_type) + '->' + self.circuit.branches[i].name + '[' + str(i)
                                          + ']: The type does not match the branch type!')

                    if len(logger) > 0:
                        dlg = LogsDialogue('Assign branch template', logger)
                        dlg.exec_()

                else:
                    self.msg(tpe_name + ' is not in the types', 'Assign branch type')
                    # update catalogue displayed

            else:
                self.msg('Select a type from the catalogue not the generic category', 'Assign branch type')
        else:
            self.msg('Select a type from the catalogue', 'Assign branch type')

    def process_templates(self):
        """
        Process all branches templates
        """
        if self.circuit is not None:
            logger = self.circuit.apply_all_branch_types()

            if len(logger) > 0:
                dlg = LogsDialogue('Process templates', logger)
                dlg.exec_()

    def recompile_circuits_for_display(self):
        """
        Recompile the circuits available to display
        :return:
        """
        if self.circuit is not None:
            # print('Compiling...', end='')
            numerical_circuit = self.circuit.compile()
            self.calculation_inputs_to_display = numerical_circuit.compute()
            return True
        else:
            self.calculation_inputs_to_display = None
            return False

    def update_islands_to_display(self):
        """
        Compile the circuit and allow the display of the calculation objects
        :return:
        """
        self.recompile_circuits_for_display()
        self.ui.simulation_data_island_comboBox.clear()
        self.ui.simulation_data_island_comboBox.addItems(
            ['Island ' + str(i) for i, circuit in enumerate(self.calculation_inputs_to_display)])
        if len(self.calculation_inputs_to_display) > 0:
            self.ui.simulation_data_island_comboBox.setCurrentIndex(0)

    def plot_style_change(self):
        """
        Change the style
        :return:
        """
        style = self.ui.plt_style_comboBox.currentText()
        plt.style.use(style)
        print('Style changed to', style)

    def copy_profiles(self):
        """
        Copy the current displayed profiles to the clipboard
        """

        mdl = self.ui.profiles_tableView.model()
        if mdl is not None:
            mdl.copy_to_clipboard()
            print('Copied!')
        else:
            self.msg('There is no profile displayed, please display one', 'Copy profile to clipboard')

    def paste_profiles(self):
        """
        Paste clipboard data into the profile
        """
        print('Paste')

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
            print('Pasted!')
        else:
            self.msg('There is no profile displayed, please display one', 'Paste profile to clipboard')

    def undo(self):
        """
        Undo table changes
        """

        model = self.ui.profiles_tableView.model()
        if model is not None:
            model.undo()
        else:
            pass

    def redo(self):
        """
        redo table changes
        """
        model = self.ui.profiles_tableView.model()
        if model is not None:
            model.redo()
        else:
            pass

    def display_filter(self, elements):
        """
        Display a list of elements that comes from a filter
        :param elements:
        :return:
        """
        if len(elements) > 0:

            elm = elements[0]

            if elm.device_type in [DeviceType.BranchDevice, DeviceType.SequenceLineDevice,
                                   DeviceType.UnderGroundLineDevice]:

                mdl = BranchObjectModel(elements, elm.editable_headers,
                                        parent=self.ui.dataStructureTableView, editable=True,
                                        non_editable_attributes=elm.non_editable_attributes)
            else:

                mdl = ObjectsModel(elements, elm.editable_headers,
                                   parent=self.ui.dataStructureTableView, editable=True,
                                   non_editable_attributes=elm.non_editable_attributes)

            self.ui.dataStructureTableView.setModel(mdl)

        else:

            self.ui.dataStructureTableView.setModel(None)

    def smart_search(self):
        """
        Filter
        """

        if len(self.type_objects_list) > 0:
            command = self.ui.smart_search_lineEdit.text().lower()
            attr = self.ui.property_comboBox.currentText()

            elm = self.type_objects_list[0]
            tpe = elm.editable_headers[attr].tpe

            filtered_objects = list()

            if command.startswith('>') and not command.startswith('>='):
                # greater than selection
                args = command.replace('>', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) > args]

            elif command.startswith('<') and not command.startswith('<='):
                # "less than" selection
                args = command.replace('<', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) < args]

            elif command.startswith('>='):
                # greater or equal than selection
                args = command.replace('>=', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) >= args]

            elif command.startswith('<='):
                # "less or equal than" selection
                args = command.replace('<=', '').strip()

                try:
                    args = tpe(args)
                except:
                    self.msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) <= args]

            elif command.startswith('*'):
                # "like" selection
                args = command.replace('*', '').strip()

                if tpe == str:

                    try:
                        args = tpe(args)
                    except:
                        self.msg('Could not parse the argument for the data type')
                        return

                    filtered_objects = [x for x in self.type_objects_list if args in getattr(x, attr).lower()]

                elif tpe == DeviceType.BusDevice:
                    filtered_objects = [x for x in self.type_objects_list if args in getattr(x, attr).name.lower()]

                else:
                    self.msg('This filter type is only valid for strings')

            elif command.startswith('='):
                # Exact match
                args = command.replace('=', '').strip()

                if tpe == str:

                    try:
                        args = tpe(args)
                    except:
                        self.msg('Could not parse the argument for the data type')
                        return

                    filtered_objects = [x for x in self.type_objects_list if getattr(x, attr).lower() == args]

                elif tpe == DeviceType.BusDevice:
                    filtered_objects = [x for x in self.type_objects_list if args == getattr(x, attr).name.lower()]

                else:
                    filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) == args]

            elif command.startswith('!='):
                # Exact match
                args = command.replace('==', '').strip()

                if tpe == str:

                    try:
                        args = tpe(args)
                    except:
                        self.msg('Could not parse the argument for the data type')
                        return

                    filtered_objects = [x for x in self.type_objects_list if getattr(x, attr).lower() != args]

                elif tpe == DeviceType.BusDevice:
                    filtered_objects = [x for x in self.type_objects_list if args != getattr(x, attr).name.lower()]

                else:
                    filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) != args]

            else:
                filtered_objects = self.type_objects_list

            self.display_filter(filtered_objects)

        else:
            # nothing to search
            pass

    def delete_and_reduce_selected_objects(self):
        """
        Delete and reduce the buses
        This function removes the buses but whenever a bus is removed, the devices connected to it
        are inherited by the bus of higher voltage that is connected.
        If the bus is isolated, those devices are lost.
        """
        model = self.ui.dataStructureTableView.model()

        if model is not None:
            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.objects

            if len(objects) > 0:

                if objects[0].device_type == DeviceType.BusDevice:

                    if len(sel_idx) > 0:

                        reply = QMessageBox.question(self, 'Message',
                                                     'Are you sure that you want to delete and reduce the selected elements?',
                                                     QMessageBox.Yes, QMessageBox.No)

                        if reply == QMessageBox.Yes:

                            self.LOCK()

                            self.add_simulation(SimulationTypes.Delete_and_reduce_run)

                            self.delete_and_reduce_driver = DeleteAndReduce(grid=self.circuit,
                                                                            objects=objects,
                                                                            sel_idx=sel_idx)

                            self.delete_and_reduce_driver.progress_signal.connect(self.ui.progressBar.setValue)
                            self.delete_and_reduce_driver.progress_text.connect(self.ui.progress_label.setText)
                            self.delete_and_reduce_driver.done_signal.connect(self.UNLOCK)
                            self.delete_and_reduce_driver.done_signal.connect(self.post_delete_and_reduce_selected_objects)

                            self.delete_and_reduce_driver.start()

                        else:
                            # selected QMessageBox.No
                            pass

                    else:
                        # no selection
                        pass

                else:
                    self.msg('This function is only applicable to buses')

            else:
                # no objects
                pass
        else:
            pass

    def post_delete_and_reduce_selected_objects(self):
        """
        POst delete and merge buses
        """
        if self.delete_and_reduce_driver is not None:

            print('Removing graphics...')
            for bus in self.delete_and_reduce_driver.buses_merged:
                bus.graphic_obj.create_children_icons()
                bus.graphic_obj.arrange_children()

            print('Reprinting schematic graphics...')
            self.create_schematic_from_api(explode_factor=1)

            self.clear_results()

            self.remove_simulation(SimulationTypes.Delete_and_reduce_run)

            self.UNLOCK()

    def delete_selected_objects(self):
        """
        Delete selection
        """

        model = self.ui.dataStructureTableView.model()

        if model is not None:
            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.objects

            if len(sel_idx) > 0:

                reply = QMessageBox.question(self, 'Message',
                                             'Are you sure that you want to delete the selected elements?',
                                             QMessageBox.Yes, QMessageBox.No)

                if reply == QMessageBox.Yes:

                    # get the unique rows
                    unique = set()
                    for idx in sel_idx:
                        unique.add(idx.row())

                    unique = list(unique)
                    unique.sort(reverse=True)
                    for r in unique:
                        obj = objects.pop(r)

                        if obj.graphic_obj is not None:
                            # this is a more complete function than the circuit one because it removes the
                            # graphical items too, and for loads and generators it deletes them properly
                            obj.graphic_obj.remove()

                    # update the view
                    self.display_filter(objects)
                else:
                    pass
            else:
                self.msg('Select some cells')
        else:
            pass

    def clear_big_bus_markers(self):
        """
        clears all the buses "big marker"
        """
        for bus in self.circuit.buses:
            bus.graphic_obj.delete_big_marker()

    def set_big_bus_marker(self, buses, color: QColor):
        """
        Set a big marker at the selected buses
        :param buses: list of Bus objects
        :param color: colour to use
        """
        for bus in buses:
            bus.graphic_obj.add_big_marker(color=color)
            bus.graphic_obj.setSelected(True)

    def highlight_selection_buses(self):
        """
        Highlight and select the buses of the selected objects
        """

        model = self.ui.dataStructureTableView.model()

        if model is not None:

            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.objects

            if len(objects) > 0:

                if len(sel_idx) > 0:

                    unique = set()
                    for idx in sel_idx:
                        unique.add(idx.row())
                    sel_obj = list()
                    for idx in unique:
                        sel_obj.append(objects[idx])

                    elm = objects[0]

                    self.clear_big_bus_markers()
                    color = QColor(55, 200, 171, 180)

                    if elm.device_type == DeviceType.BusDevice:

                        self.set_big_bus_marker(buses=sel_obj, color=color)

                    elif elm.device_type == DeviceType.BranchDevice:
                        buses = list()
                        for br in sel_obj:
                            buses.append(br.bus_from)
                            buses.append(br.bus_to)
                        self.set_big_bus_marker(buses=buses, color=color)

                    else:
                        buses = list()
                        for elm in sel_obj:
                            buses.append(elm.bus)
                        self.set_big_bus_marker(buses=buses, color=color)

                else:
                    self.msg('Select some elements to highlight', 'Highlight')
            else:
                pass

    def highlight_based_on_property(self):
        """
        Highlight and select the buses of the selected objects
        """

        model = self.ui.dataStructureTableView.model()

        if model is not None:
            objects = model.objects

            if len(objects) > 0:

                elm = objects[0]
                attr = self.ui.property_comboBox.currentText()
                tpe = elm.editable_headers[attr].tpe

                if tpe in [float, int]:

                    self.clear_big_bus_markers()

                    if elm.device_type == DeviceType.BusDevice:
                        # buses
                        buses = objects
                        values = [getattr(elm, attr) for elm in objects]

                    elif elm.device_type == DeviceType.BranchDevice:
                        # branches
                        buses = list()
                        values = list()
                        for br in objects:
                            buses.append(br.bus_from)
                            buses.append(br.bus_to)
                            val = getattr(br, attr)
                            values.append(val)
                            values.append(val)

                    else:
                        # loads, generators, etc...
                        buses = [elm.bus for elm in objects]
                        values = [getattr(elm, attr) for elm in objects]

                    # build the color map
                    seq = [(0.0, 'gray'),
                           (0.5, 'orange'),
                           (1, 'red')]
                    cmap = LinearSegmentedColormap.from_list('lcolors', seq)
                    mx = max(values)

                    if mx != 0:
                        # color based on the value
                        for bus, value in zip(buses, values):
                            r, g, b, a = cmap(value / mx)
                            color = QColor(r * 255, g * 255, b * 255, a * 255)
                            bus.graphic_obj.add_big_marker(color=color)
                    else:
                        self.msg('The maximum value is 0, so the coloring cannot be applied',
                                 'Highlight based on property')
                else:
                    self.msg('The selected property must be of a numeric type',
                             'Highlight based on property')

            else:
                pass

    def delete_selected_from_the_schematic(self):
        """
        Prompt to delete the selected buses from the schematic
        """
        if len(self.circuit.buses) > 0:

            # get the selected buses
            selected = [bus for bus in self.circuit.buses if bus.graphic_obj.isSelected()]

            if len(selected) > 0:
                reply = QMessageBox.question(self, 'Delete',
                                             'Are you sure that you want to delete the selected elements?',
                                             QMessageBox.Yes, QMessageBox.No)

                if reply == QMessageBox.Yes:

                    # remove the buses (from the schematic and the circuit)
                    for bus in selected:
                        if bus.graphic_obj is not None:
                            # this is a more complete function than the circuit one because it removes the
                            # graphical items too, and for loads and generators it deletes them properly
                            bus.graphic_obj.remove()
                else:
                    pass
            else:
                self.msg('Select some elements from the schematic', 'Delete buses')
        else:
            pass


def run(use_native_dialogues=True):
    """
    Main function to run the GUI
    :return:
    """
    app = QApplication(sys.argv)
    window = MainGUI(use_native_dialogues=use_native_dialogues)
    window.resize(int(1.61 * 700.0), 700)  # golden ratio :)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run()
