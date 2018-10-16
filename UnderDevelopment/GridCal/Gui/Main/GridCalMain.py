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
from GridCal.Engine.DeviceTypes import Tower, Wire, TransformerType, SequenceLineType, UndergroundLineType
from GridCal.Gui.ProfilesInput.profile_dialogue import ProfileInputGUI
from GridCal.Gui.Analysis.AnalysisDialogue import GridAnalysisGUI
from GridCal.Gui.LineBuilder.LineBuilderDialogue import TowerBuilderGUI
from GridCal.Gui.GeneralDialogues import *

# Engine imports
from GridCal.Engine.BlackOutDriver import *
from GridCal.Engine.IoStructures import *
# from GridCal.Engine.OpfDriver import *
from GridCal.Engine.OpfTimeSeriesDriver import *
# from GridCal.Engine.OptimizationDriver import *
from GridCal.Engine.PowerFlowDriver import *
from GridCal.Engine.ShortCircuitDriver import *
# from GridCal.Engine.StateEstimationDriver import *
from GridCal.Engine.StochasticDriver import *
from GridCal.Engine.TimeSeriesDriver import *
from GridCal.Engine.TransientStabilityDriver import *
from GridCal.Engine.VoltageCollapseDriver import *
from GridCal.Engine.TopologyDriver import TopologyReduction, TopologyReductionOptions
from GridCal.Engine.TopologyDriver import select_branches_to_reduce
from GridCal.Engine.GridAnalysis import TimeSeriesResultsAnalysis

import gc
import os.path
import platform
import sys
import datetime
from collections import OrderedDict
from enum import Enum
from matplotlib.colors import LinearSegmentedColormap, Colormap
from multiprocessing import cpu_count
from geopy.geocoders import Nominatim

__author__ = 'Santiago Peñate Vera'

"""
This class is the handler of the main gui of GridCal.
"""

########################################################################################################################
# Main Window
########################################################################################################################


class ResultTypes(Enum):
    bus_voltage_per_unit = 1,
    bus_voltage = 2,
    bus_s_v_curve = 3,
    bus_QV_curve = 4,
    bus_active_power = 5,
    bus_reactive_power = 6,
    bus_active_and_reactive_power = 7,
    bus_apparent_power = 8,
    branch_current_per_unit = 9,
    branch_current = 10,
    branch_power_flow_per_unit = 11,
    branch_power_flow = 12,
    branch_losses = 13,
    branches_loading = 14,
    gen_reactive_power_pu = 15,
    gen_reactive_power = 16


class ElementsDialogue(QtWidgets.QDialog):
    """
    Selected elements dialogue window
    """

    def __init__(self, name, elements: list()):
        super(ElementsDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.layout = QtWidgets.QVBoxLayout(self)

        # build elements list
        self.objects_table = QtWidgets.QTableView()

        if len(elements) > 0:
            model = ObjectsModel(elements, elements[0].edit_headers, elements[0].units, elements[0].edit_types,
                                 parent=self.objects_table, editable=False, non_editable_indices=[1, 2, 14])

            self.objects_table.setModel(model)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Proceed')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.layout.addWidget(QtWidgets.QLabel("Logs"))
        self.layout.addWidget(self.objects_table)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle(name)

        self.accepted = False

    def accept_click(self):
        self.accepted = True
        self.accept()


class FileOpenThread(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, app, file_name):
        """

        :param app: instance of MainGui
        """
        QThread.__init__(self)

        self.app = app

        self.file_name = file_name

        self.valid = False

        self.logger = list()

        self.circuit = None

        self.__cancel__ = False

    def progress_callback(self, val):
        """
        Send progress report
        :param val: lambda value
        :return: None
        """
        self.progress_text.emit('Running voltage collapse lambda:' + "{0:.2f}".format(val) + '...')

    def open_file_process(self, filename):
        """
        process to open a file without asking
        :return:
        """

        # print(filename)
        self.circuit = MultiCircuit()

        path, fname = os.path.split(filename)

        self.progress_text.emit('Loading ' + fname + '...')

        self.logger = list()

        try:
            self.logger += self.circuit.load_file(filename=filename)

            self.valid = True

        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logger.append(str(exc_traceback) + '\n' + str(exc_value))
            self.valid = False

        # post events
        self.progress_text.emit('Creating schematic...')

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        self.open_file_process(filename=self.file_name)

        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


class MainGUI(QMainWindow):

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        QWidget.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)

        # Declare circuit
        self.circuit = MultiCircuit()

        self.calculation_inputs_to_display = None

        self.project_directory = None

        # solvers dictionary
        self.solvers_dict = OrderedDict()
        self.solvers_dict['Newton-Raphson in power'] = SolverType.NR
        self.solvers_dict['Newton-Raphson in current'] = SolverType.NRI
        self.solvers_dict['Newton-Raphson-Iwamoto'] = SolverType.IWAMOTO
        self.solvers_dict['Levenberg-Marquardt'] = SolverType.LM
        self.solvers_dict['Fast-Decoupled'] = SolverType.FASTDECOUPLED
        self.solvers_dict['Holomorphic embedding [HELM]'] = SolverType.HELM
        self.solvers_dict['Linear AC approximation'] = SolverType.LACPF
        self.solvers_dict['DC approximation'] = SolverType.DC

        lst = list(self.solvers_dict.keys())
        mdl = get_list_model(lst)
        self.ui.solver_comboBox.setModel(mdl)
        # self.ui.retry_solver_comboBox.setModel(mdl)

        self.ui.solver_comboBox.setCurrentIndex(0)
        # self.ui.retry_solver_comboBox.setCurrentIndex(3)

        mdl = get_list_model(self.circuit.profile_magnitudes.keys())
        self.ui.profile_device_type_comboBox.setModel(mdl)
        self.profile_device_type_changed()

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

        # solvers dictionary
        self.lp_solvers_dict = OrderedDict()
        self.lp_solvers_dict['DC OPF'] = SolverType.DC_OPF
        self.lp_solvers_dict['AC OPF'] = SolverType.AC_OPF
        # self.lp_solvers_dict['DYCORS OPF'] = SolverType.DYCORS_OPF
        self.lp_solvers_dict['Nelder-Mead feasibility dispatch'] = SolverType.NELDER_MEAD_OPF

        self.ui.lpf_solver_comboBox.setModel(get_list_model(list(self.lp_solvers_dict.keys())))

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
        self.ui.dataStructuresSplitter.setStretchFactor(1, 15)
        self.ui.templatesSplitter.setStretchFactor(15, 1)
        self.ui.simulationDataSplitter.setStretchFactor(1, 15)
        self.ui.catalogueSplitter.setStretchFactor(1, 15)

        self.lock_ui = False
        self.ui.progress_frame.setVisible(self.lock_ui)

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

        self.results_df = None

        self.buses_for_storage = None

        self.available_results_dict = None
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
        self.ui.console_tab.layout().addWidget(self.console)

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

        self.ui.location_search_pushButton.clicked.connect(self.search_location)

        self.ui.profile_add_pushButton.clicked.connect(lambda: self.modify_profiles('+'))

        self.ui.profile_subtract_pushButton.clicked.connect(lambda: self.modify_profiles('-'))

        self.ui.profile_multiply_pushButton.clicked.connect(lambda: self.modify_profiles('*'))

        self.ui.profile_divide_pushButton.clicked.connect(lambda: self.modify_profiles('/'))

        self.ui.plot_time_series_pushButton.clicked.connect(self.plot_profiles)

        self.ui.analyze_objects_pushButton.clicked.connect(self.display_grid_analysis)

        self.ui.catalogue_add_pushButton.clicked.connect(self.add_to_catalogue)
        self.ui.catalogue_edit_pushButton.clicked.connect(self.edit_from_catalogue)
        self.ui.catalogue_delete_pushButton.clicked.connect(self.delete_from_catalogue)

        self.ui.viewTemplatesButton.clicked.connect(self.view_template_toggle)

        self.ui.assignTemplateButton.clicked.connect(self.assign_template)

        self.ui.processTemplatesPushButton.clicked.connect(self.process_templates)

        self.ui.compute_simulation_data_pushButton.clicked.connect(self.update_islands_to_display)

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

        # sliders
        self.ui.profile_start_slider.valueChanged.connect(self.profile_sliders_changed)
        self.ui.profile_end_slider.valueChanged.connect(self.profile_sliders_changed)

        # doubleSpinBox
        self.ui.fbase_doubleSpinBox.valueChanged.connect(self.change_circuit_base)
        self.ui.sbase_doubleSpinBox.valueChanged.connect(self.change_circuit_base)

        self.ui.explosion_factor_doubleSpinBox.valueChanged.connect(self.explosion_factor_change)

        ################################################################################################################
        # Color maps
        ################################################################################################################
        vmax = 1.2
        seq = [(0 / vmax, 'black'),
               (0.8 / vmax, 'blue'),
               (1.0 / vmax, 'green'),
               (1.05 / vmax, 'orange'),
               (1.2 / vmax, 'red')]
        self.voltage_cmap = LinearSegmentedColormap.from_list('vcolors', seq)
        load_max = 1.5
        seq = [(0.0 / load_max, 'gray'),
               (0.8 / load_max, 'green'),
               (1.2 / load_max, 'orange'),
               (1.5 / load_max, 'red')]
        self.loading_cmap = LinearSegmentedColormap.from_list('lcolors', seq)

        ################################################################################################################
        # Other actions
        ################################################################################################################
        self.ui.actionShow_map.setVisible(False)

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

        msg += 'Copyright (C) 2018 Santiago Peñate Vera.\n'

        QMessageBox.about(self, "About GridCal", msg)

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

    def color_based_of_pf(self, s_bus, s_branch, voltages, loadings, types, losses=None, failed_br_idx=None):
        """
        Color the grid based on the results passed
        Args:
            s_bus: Buses power
            s_branch: Branches power
            voltages: Buses voltage
            loadings: Branches load
            types: Buses type
            losses: Branches losses
            failed_br_idx: failed branches
        """
        # color nodes
        vmin = 0
        vmax = 1.2
        vrng = vmax - vmin
        vabs = abs(voltages)
        vang = np.angle(voltages, deg=True)
        vnorm = (vabs - vmin) / vrng
        Sbase = self.circuit.Sbase

        '''
        class BusMode(Enum):
        PQ = 1,
        PV = 2,
        REF = 3,
        NONE = 4,
        STO_DISPATCH = 5
        '''
        bus_types = ['', 'PQ', 'PV', 'Slack', 'None', 'Storage']

        for i, bus in enumerate(self.circuit.buses):
            if bus.active:
                r, g, b, a = self.voltage_cmap(vnorm[i])
                # print(vnorm[i], '->', r*255, g*255, b*255, a)
                # QColor(r, g, b, alpha)
                bus.graphic_obj.set_tile_color(QColor(r*255, g*255, b*255, a*255))

                tooltip = str(i) + ': ' + bus.name + '\n' \
                          + 'V:' + "{:10.4f}".format(vabs[i]) + " <{:10.4f}".format(vang[i]) + 'º [p.u.]\n' \
                          + 'V:' + "{:10.4f}".format(vabs[i] * bus.Vnom) + " <{:10.4f}".format(vang[i]) + 'º [kV]'
                if s_bus is not None:
                    tooltip += '\nS: ' + "{:10.4f}".format(s_bus[i] * Sbase) + ' [MVA]'
                if types is not None:
                    tooltip += '\nType: ' + bus_types[types[i]]
                bus.graphic_obj.setToolTip(tooltip)

            else:
                bus.graphic_obj.set_tile_color(Qt.gray)

        # color branches
        if s_branch is not None:
            lnorm = abs(loadings)
            lnorm[lnorm == np.inf] = 0

            for i, branch in enumerate(self.circuit.branches):

                w = branch.graphic_obj.pen_width
                if branch.active:
                    style = Qt.SolidLine
                    r, g, b, a = self.loading_cmap(lnorm[i])
                    color = QColor(r*255, g*255, b*255, a*255)
                else:
                    style = Qt.DashLine
                    color = Qt.gray

                tooltip = str(i) + ': ' + branch.name
                tooltip += '\nloading: ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'
                if s_branch is not None:
                    tooltip += '\nPower: ' + "{:10.4f}".format(s_branch[i]) + ' [MVA]'
                if losses is not None:
                    tooltip += '\nLosses: ' + "{:10.4f}".format(losses[i]) + ' [MVA]'
                branch.graphic_obj.setToolTipText(tooltip)
                branch.graphic_obj.set_pen(QtGui.QPen(color, w, style))

        if failed_br_idx is not None:
            for i in failed_br_idx:
                w = self.circuit.branches[i].graphic_obj.pen_width
                style = Qt.DashLine
                color = Qt.gray
                self.circuit.branches[i].graphic_obj.set_pen(QtGui.QPen(color, w, style))

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
        Print in the console some message
        Args:
            msg_: Test message
        """
        dte = datetime.datetime.now().strftime("%b %d %Y %H:%M:%S")
        self.console.print_text('\n' + dte + '->' + msg_)

    # def compile(self, use_opf_vals=False, dispatch_storage=False):
    #     """
    #     This function compiles the circuit and updates the UI accordingly
    #     """
    #
    #     try:
    #         logger = list()
    #         numerical_circuit = self.circuit.compile(use_opf_vals, dispatch_storage=dispatch_storage, logger=logger)
    #
    #         if len(logger) > 0:
    #             dlg = LogsDialogue('Open file logger', logger)
    #             dlg.exec_()
    #
    #     except Exception as ex:
    #         exc_type, exc_value, exc_traceback = sys.exc_info()
    #         self.msg(str(exc_traceback) + '\n' + str(exc_value), 'Circuit compilation')
    #
    #     if self.circuit.time_profile is not None:
    #         mdl = get_list_model(self.circuit.time_profile)
    #         self.ui.vs_departure_comboBox.setModel(mdl)
    #         self.ui.vs_target_comboBox.setModel(mdl)
    #         self.ui.profile_time_selection_comboBox.setModel(mdl)

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

    def new_project(self):
        """
        Create new grid
        :return:
        """
        if len(self.circuit.buses) > 0:
            quit_msg = "Are you sure you want to quit the current grid and create a new one?"
            reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                # print('New')
                self.circuit = MultiCircuit()

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
                self.ui.resultsPlot.clear()
                self.ui.resultsTableView.setModel(None)

                # clear the simulation objects
                self.power_flow = None
                self.monte_carlo = None
                self.time_series = None
                self.voltage_stability = None
                self.results_df = None

                self.clear_results()

            else:
                pass
        else:
            pass

    def open_file(self):
        """
        Open GridCal file
        @return:
        """

        if len(self.circuit.buses) > 0:
            quit_msg = "Are you sure you want to quit the current grid and open a new one?" \
                       "\n If the process is cancelled the grid will remain."
            reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:

                self.open_file_threaded()
            else:
                pass
        else:
            # Just open the file
            self.open_file_threaded()

    def open_file_threaded(self):
        """
        Open file from a Qt thread to remain responsive
        """

        files_types = "Formats (*.xlsx *.xls *.dgs *.m *.raw *.RAW *.json *.xml *.dpx)"
        # call dialog to select the file

        filename, type_selected = QFileDialog.getOpenFileName(self, 'Open file',
                                                              directory=self.project_directory,
                                                              filter=files_types)

        if len(filename) > 0:

            # store the working directory
            self.project_directory = os.path.dirname(filename)

            # loack the ui
            self.LOCK()

            # create thread
            self.open_file_thread_object = FileOpenThread(app=self, file_name=filename)

            # make connections
            self.open_file_thread_object.progress_signal.connect(self.ui.progressBar.setValue)
            self.open_file_thread_object.progress_text.connect(self.ui.progress_label.setText)
            self.open_file_thread_object.done_signal.connect(self.UNLOCK)
            self.open_file_thread_object.done_signal.connect(self.post_open_file)

            # thread start
            self.open_file_thread_object.start()

    def post_open_file(self):
        """
        Actions to perform after a file has been loaded
        """
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
                self.grid_editor.name_label.setText(self.circuit.name)

                # set base magnitudes
                self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
                self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)

                # set circuit comments
                try:
                    self.ui.comments_textEdit.setText(self.circuit.comments)
                except:
                    pass

                # # compile the circuit (fast)
                # self.compile()

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
                self.clear_results()

            else:
                warn('The file was not valid')
        else:
            pass

    def save_file(self):
        """
        Save the circuit case to a file
        """
        # declare the allowed file types
        files_types = "Excel (*.xlsx);;CIM (*.xml);;JSON (*.json)"

        # call dialog to select the file
        if self.project_directory is None:
            self.project_directory = ''

        # set grid name
        self.circuit.name = self.grid_editor.name_label.text()

        self.circuit.comments = self.ui.comments_textEdit.toPlainText()

        fname = os.path.join(self.project_directory, self.grid_editor.name_label.text())

        filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file',  fname, files_types)

        if filename is not "":
            # if the user did not enter the extension, add it automatically
            name, file_extension = os.path.splitext(filename)

            extension = dict()
            extension['Excel (*.xlsx)'] = '.xlsx'
            extension['CIM (*.xml)'] = '.xml'
            extension['JSON (*.json)'] = '.json'

            if file_extension == '':
                filename = name + extension[type_selected]

            # call to save the file in the circuit

            # logger = self.circuit.save_file(filename)
            #
            # if len(logger) > 0:
            #     dlg = LogsDialogue('Save file logger', logger)
            #     dlg.exec_()

            try:
                logger = self.circuit.save_file(filename)

                if len(logger) > 0:
                    dlg = LogsDialogue('Save file logger', logger)
                    dlg.exec_()

                # call the garbage collector to free memory
                gc.collect()

            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.msg(str(exc_traceback) + '\n' + str(exc_value), 'File saving')

    def closeEvent(self, event):
        """
        Close event
        :param event:
        :return:
        """
        if len(self.circuit.buses) > 0:
            quit_msg = "Are you sure you want to exit GridCal?"
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

            filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

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

            filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

            if filename is not "":
                if not filename.endswith('.xlsx'):
                    filename += '.xlsx'
                # TODO: correct this function
                self.circuit.export_profiles(file_name=filename)
        else:
            self.msg('There are no profiles!', 'Export object profiles')

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

        filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

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

            # call dialog to select the file
            filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

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

        # # clear all
        # self.grid_editor.diagramView.scene_.clear()
        #
        # # set "infinite" limits for the figure
        # min_x = sys.maxsize
        # min_y = sys.maxsize
        # max_x = -sys.maxsize
        # max_y = -sys.maxsize
        #
        # # first create the buses
        # for bus in self.circuit.buses:
        #     # print(bus.x, bus.y)
        #     graphic_obj = self.grid_editor.diagramView.add_bus(bus=bus, explode_factor=explode_factor)
        #     graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
        #
        #     # get the item position
        #     x = graphic_obj.pos().x()
        #     y = graphic_obj.pos().y()
        #
        #     # compute the boundaries of the grid
        #     max_x = max(max_x, x)
        #     min_x = min(min_x, x)
        #     max_y = max(max_y, y)
        #     min_y = min(min_y, y)
        #
        #     bus.graphic_obj = graphic_obj
        #     bus.graphic_obj.create_children_icons()
        #     bus.graphic_obj.arrange_children()
        #
        # # set the figure limits
        # self.grid_editor.set_limits(min_x, max_x, min_y, max_y)
        #
        # for branch in self.circuit.branches:
        #     terminal_from = branch.bus_from.graphic_obj.terminal
        #     terminal_to = branch.bus_to.graphic_obj.terminal
        #     graphic_obj = BranchGraphicItem(terminal_from, terminal_to, self.grid_editor.diagramScene, branch=branch)
        #     graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
        #     terminal_from.hosting_connections.append(graphic_obj)
        #     terminal_to.hosting_connections.append(graphic_obj)
        #     graphic_obj.redraw()
        #     branch.graphic_obj = graphic_obj
        #
        # # Align lines
        # for bus in self.circuit.buses:
        #     bus.graphic_obj.arrange_children()
        #
        # #  center the view
        # self.grid_editor.center_nodes()

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

                if abs(v1-v2) > 1.0:

                    branch.branch_type = BranchType.Transformer

                else:

                    pass   # is a line

        else:
            self.msg('There are no branches!')

    def view_objects_data(self):
        """
        On click, display the objects properties
        """
        elm_type = self.ui.dataStructuresListView.selectedIndexes()[0].data()

        self.view_template_controls(False)

        if elm_type == 'Buses':
            elm = Bus()
            mdl = ObjectsModel(self.circuit.buses, elm.edit_headers, elm.units, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True)

        elif elm_type == 'Branches':

            self.fill_catalogue_tree_view()

            elm = Branch(None, None)
            mdl = BranchObjectModel(self.circuit.branches, elm.edit_headers, elm.units, elm.edit_types,
                                    parent=self.ui.dataStructureTableView, editable=True,
                                    non_editable_indices=elm.non_editable_indices)

            self.view_template_controls(True)

        elif elm_type == 'Loads':
            elm = Load()
            mdl = ObjectsModel(self.circuit.get_loads(), elm.edit_headers, elm.units, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        elif elm_type == 'Static Generators':
            elm = StaticGenerator()
            mdl = ObjectsModel(self.circuit.get_static_generators(), elm.edit_headers, elm.units, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        elif elm_type == 'Controlled Generators':
            elm = ControlledGenerator()
            mdl = ObjectsModel(self.circuit.get_controlled_generators(), elm.edit_headers, elm.units, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        elif elm_type == 'Batteries':
            elm = Battery()
            mdl = ObjectsModel(self.circuit.get_batteries(), elm.edit_headers, elm.units, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        elif elm_type == 'Shunts':
            elm = Shunt()
            mdl = ObjectsModel(self.circuit.get_shunts(), elm.edit_headers, elm.units, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1])

        self.ui.dataStructureTableView.setModel(mdl)
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
            # add children to parent
            for elm in catalogue_dict[key]:
                child1 = QStandardItem(str(elm))
                parent1.appendRow([child1])
            model.appendRow(parent1)
        self.ui.catalogueTreeView.setModel(model)

    def view_simulation_objects_data(self):
        """
        Simulation data structure clicked
        """

        # TODO: Correct this function to operate correctly with the new engine

        i = self.ui.simulation_data_island_comboBox.currentIndex()

        if i > -1 and len(self.circuit.buses) > 0:
            elm_type = self.ui.simulationDataStructuresListView.selectedIndexes()[0].data()

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

    def new_profiles_structure(self):
        """
        Create new profiles structure
        :return:
        """
        # print('new_profiles_structure')

        dlg = NewProfilesStructureDialogue()
        if dlg.exec_():
            steps, step_length, step_unit, time_base = dlg.get_values()

            self.circuit.create_profiles(steps, step_length, step_unit, time_base)

            # # TODO: Correct this function to not to depend on a previous compilation
            # self.compile()

            self.set_up_profile_sliders()

    def delete_profiles_structure(self):
        """
        Delete all profiles
        :return: Nothing
        """

        if self.circuit.time_profile is not None:
            quit_msg = "Are you sure you want to remove the profiles?"
            reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                for bus in self.circuit.buses:
                    bus.delete_profiles()
                self.circuit.time_profile = None
                self.circuit.has_time_series = False
                self.ui.tableView.setModel(None)
                self.set_up_profile_sliders()
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

        # Load(), StaticGenerator(), ControlledGenerator(), Battery(), Shunt()

        dev_type = self.ui.profile_device_type_comboBox.currentText()
        magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type]
        idx = self.ui.device_type_magnitude_comboBox.currentIndex()
        magnitude = magnitudes[idx]

        if dev_type == 'Load':
            objects = self.circuit.get_loads()
            also_reactive_power = True

        elif dev_type == 'StaticGenerator':
            objects = self.circuit.get_static_generators()
            also_reactive_power = True

        elif dev_type == 'ControlledGenerator':
            objects = self.circuit.get_controlled_generators()
            also_reactive_power = False

        elif dev_type == 'Battery':
            objects = self.circuit.get_batteries()
            also_reactive_power = False

        elif dev_type == 'Shunt':
            objects = self.circuit.get_shunts()
            also_reactive_power = True
        else:
            objects = list()
            also_reactive_power = False

        if len(objects) > 0:
            dialogue = ProfileInputGUI(parent=self,
                                       list_of_objects=objects,
                                       magnitude=magnitude,
                                       AlsoReactivePower=also_reactive_power)
            dialogue.resize(int(1.61 * 600.0), 600)  # golden ratio
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
                        elm.profile_f[magnitude](dialogue.time, dialogue.data[:, i], dialogue.normalized)

                # set up sliders
                self.set_up_profile_sliders()

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

        dev_type = self.ui.profile_device_type_comboBox.currentText()
        magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type]
        idx = self.ui.device_type_magnitude_comboBox.currentIndex()
        magnitude = magnitudes[idx]

        if dev_type == 'Load':
            objects = self.circuit.get_loads()

        elif dev_type == 'StaticGenerator':
            objects = self.circuit.get_static_generators()

        elif dev_type == 'ControlledGenerator':
            objects = self.circuit.get_controlled_generators()

        elif dev_type == 'Battery':
            objects = self.circuit.get_batteries()

        elif dev_type == 'Shunt':
            objects = self.circuit.get_shunts()
        else:
            objects = list()

        # Assign profiles
        if len(objects) > 0:
            attr = objects[0].profile_attr[magnitude]
            if operation == '+':
                for i, elm in enumerate(objects):
                    setattr(elm, attr, getattr(elm, attr) + value)
            elif operation == '-':
                for i, elm in enumerate(objects):
                    setattr(elm, attr, getattr(elm, attr) - value)
            elif operation == '*':
                for i, elm in enumerate(objects):
                    setattr(elm, attr, getattr(elm, attr) * value)
            elif operation == '/':
                for i, elm in enumerate(objects):
                    setattr(elm, attr, getattr(elm, attr) / value)
            else:
                raise Exception('Operation not supported: ' + str(operation))

            self.display_profiles()

    def plot_profiles(self):
        """
        Plot profiles from the time events
        """
        value = self.ui.profile_factor_doubleSpinBox.value()

        dev_type = self.ui.profile_device_type_comboBox.currentText()
        magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type]
        idx = self.ui.device_type_magnitude_comboBox.currentIndex()
        magnitude = magnitudes[idx]

        if dev_type == 'Load':
            objects = self.circuit.get_loads()

        elif dev_type == 'StaticGenerator':
            objects = self.circuit.get_static_generators()

        elif dev_type == 'ControlledGenerator':
            objects = self.circuit.get_controlled_generators()

        elif dev_type == 'Battery':
            objects = self.circuit.get_batteries()

        elif dev_type == 'Shunt':
            objects = self.circuit.get_shunts()

        # get the selected element
        obj_idx = self.ui.tableView.selectedIndexes()

        # Assign profiles
        if len(obj_idx):
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111)

            k = obj_idx[0].column()
            units_dict = {objects[k].edit_headers[i]: objects[k].units[i] for i in range(len(objects[k].units))}

            unit = units_dict[magnitude]
            ax.set_ylabel(unit)

            # get the unique columns in the selected cells
            cols = set()
            for i in range(len(obj_idx)):
                cols.add(obj_idx[i].column())

            # plot every column
            for k in cols:
                attr = objects[k].profile_attr[magnitude]
                df = getattr(objects[k], attr)
                df.columns = [objects[k].name]
                df.plot(ax=ax)
            plt.show()

    def display_profiles(self):
        """
        Display profile
        """
        if self.circuit.time_profile is not None:
            # print('display_profiles')

            dev_type = self.ui.profile_device_type_comboBox.currentText()

            magnitudes, mag_types = self.circuit.profile_magnitudes[dev_type]

            idx = self.ui.device_type_magnitude_comboBox.currentIndex()
            magnitude = magnitudes[idx]
            mtype = mag_types[idx]

            mdl = ProfilesModel(multi_circuit=self.circuit, device=dev_type, magnitude=magnitude, format=mtype, parent=self.ui.tableView)
            self.ui.tableView.setModel(mdl)

    def get_selected_power_flow_options(self):
        """
        Gather power flow run options
        :return:
        """
        solver_type = self.solvers_dict[self.ui.solver_comboBox.currentText()]

        enforce_q_limits = self.ui.control_Q_checkBox.isChecked()

        exponent = self.ui.tolerance_spinBox.value()
        tolerance = 1.0 / (10.0**exponent)

        max_iter = self.ui.max_iterations_spinBox.value()

        # set_last_solution = self.ui.remember_last_solution_checkBox.isChecked()

        # dispatch_storage = self.ui.dispatch_storage_checkBox.isChecked()
        dispatch_storage= False

        if self.ui.helm_retry_checkBox.isChecked():
            # solver_to_retry_with = self.solvers_dict[self.ui.retry_solver_comboBox.currentText()]
            solver_to_retry_with = SolverType.LACPF  # to set a value
        else:
            solver_to_retry_with = None

        mp = self.ui.use_multiprocessing_checkBox.isChecked()

        ctrl_taps = self.ui.control_transformer_taps_checkBox.isChecked()

        ops = PowerFlowOptions(solver_type=solver_type,
                               aux_solver_type=solver_to_retry_with,
                               verbose=False,
                               robust=False,
                               initialize_with_existing_solution=True,
                               tolerance=tolerance,
                               max_iter=max_iter,
                               control_q=enforce_q_limits,
                               multi_core=mp,
                               dispatch_storage=dispatch_storage,
                               control_taps=ctrl_taps)

        return ops

    def run_power_flow(self):
        """
        Run a power flow simulation
        :return:
        """
        if len(self.circuit.buses) > 0:
            self.LOCK()

            self.ui.progress_label.setText('Compiling the grid...')
            QtGui.QGuiApplication.processEvents()
            # self.compile()  # compiles inside

            # get the power flow options from the GUI
            options = self.get_selected_power_flow_options()

            # compute the automatic precision
            if self.ui.auto_precision_checkBox.isChecked():
                lg = np.log10(abs(self.circuit.numerical_circuit.Sbus.real))
                lg[lg == -np.inf] = 0
                tol_idx = int(min(abs(lg))) + 3
                tolerance = 1.0 / (10.0 ** tol_idx)
                options.tolerance = tolerance
                self.ui.tolerance_spinBox.setValue(tol_idx)

            self.ui.progress_label.setText('Running power flow...')
            QtGui.QGuiApplication.processEvents()
            # set power flow object instance
            self.power_flow = PowerFlow(self.circuit, options)

            # self.power_flow.progress_signal.connect(self.ui.progressBar.setValue)
            # self.power_flow.progress_text.connect(self.ui.progress_label.setText)
            # self.power_flow.done_signal.connect(self.UNLOCK)
            # self.power_flow.done_signal.connect(self.post_power_flow)

            # self.power_flow.run()
            self.threadpool.start(self.power_flow)
            self.threadpool.waitForDone()
            self.post_power_flow()
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

            self.color_based_of_pf(s_bus=self.power_flow.results.Sbus,
                                   s_branch=self.power_flow.results.Sbranch,
                                   voltages=self.power_flow.results.voltage,
                                   loadings=self.power_flow.results.loading,
                                   types=self.circuit.numerical_circuit.bus_types,
                                   losses=self.power_flow.results.losses)
            self.update_available_results()

            # print convergence reports on the console
            for report in self.power_flow.pf.convergence_reports:
                msg_ = 'Power flow converged: \n' + report.__str__() + '\n\n'
                self.console_msg(msg_)

        else:
            if len(self.power_flow.pf.logger) > 0:
                dlg = LogsDialogue('Power flow', self.power_flow.pf.logger)
                dlg.exec_()

            self.msg('There are no power flow results.\nIs there any slack bus or controlled generator?', 'Power flow')
            QtGui.QGuiApplication.processEvents()

        self.UNLOCK()

    def run_short_circuit(self):
        """
        Run a short circuit simulation
        The short circuit simulation must be performed after a power flow simulation
        without any load or topology change
        :return:
        """
        if len(self.circuit.buses) > 0:

            if self.power_flow is not None:

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
                    # get the power flow options from the GUI
                    sc_options = ShortCircuitOptions(bus_index=sel_buses)
                    self.short_circuit = ShortCircuit(self.circuit, sc_options, self.power_flow.results)

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
                self.msg('Run a power flow simulation first.\nThe results are needed to initialize this simulation.')
        else:
            pass

    def post_short_circuit(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        # update the results in the circuit structures
        # print('Post short circuit')
        if self.power_flow.results is not None:
            # print('Vbus:\n', abs(self.circuit.short_circuit_results.voltage))
            # print('Sbr:\n', abs(self.circuit.short_circuit_results.Sbranch))
            # print('ld:\n', abs(self.circuit.short_circuit_results.loading))

            self.ui.progress_label.setText('Colouring short circuit results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.color_based_of_pf(s_bus=self.short_circuit.results.Sbus,
                                   s_branch=self.short_circuit.results.Sbranch,
                                   voltages=self.short_circuit.results.voltage,
                                   types=self.circuit.numerical_circuit.bus_types,
                                   loadings=self.short_circuit.results.loading)
            self.update_available_results()
        else:
            warn('Something went wrong, There are no power flow results.')
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
            # get the selected UI options
            use_alpha, alpha, use_profiles, start_idx, end_idx = self.get_selected_voltage_stability()

            # declare voltage collapse options
            vc_options = VoltageCollapseOptions()

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
                    self.voltage_stability = VoltageCollapse(circuit=self.circuit, options=vc_options, inputs=vc_inputs)

                    # make connections
                    self.voltage_stability.progress_signal.connect(self.ui.progressBar.setValue)
                    self.voltage_stability.progress_text.connect(self.ui.progress_label.setText)
                    self.voltage_stability.done_signal.connect(self.UNLOCK)
                    self.voltage_stability.done_signal.connect(self.post_voltage_stability)

                    # thread start
                    self.voltage_stability.start()
                else:
                    self.msg('Run a power flow simulation first.\nThe results are needed to initialize this simulation.')

            elif use_profiles:
                '''
                Here the start and finish power states are taken from the profiles
                '''
                if start_idx > -1 and end_idx > -1:

                    # lock the UI
                    self.LOCK()

                    # self.compile()

                    self.power_flow.run_at(start_idx)

                    vc_inputs = VoltageCollapseInput(Sbase=self.circuit.time_series_input.Sprof.values[start_idx, :],
                                                     Vbase=self.power_flow.results.voltage,
                                                     Starget=self.circuit.time_series_input.Sprof.values[end_idx, :])

                    # create object
                    self.voltage_stability = VoltageCollapse(circuit=self.circuit, options=vc_options, inputs=vc_inputs)

                    # make connections
                    self.voltage_stability.progress_signal.connect(self.ui.progressBar.setValue)
                    self.voltage_stability.done_signal.connect(self.UNLOCK)
                    self.voltage_stability.done_signal.connect(self.post_voltage_stability)

                    # thread start
                    self.voltage_stability.start()
                else:
                    self.msg('Check the selected start and finnish time series indices.')
        else:
            pass

    def post_voltage_stability(self):
        """
        Actions performed after the voltage stability. Launched by the thread after its execution
        :return:
        """
        if self.voltage_stability.results is not None:

            if self.voltage_stability.results.voltages is not None:
                V = self.voltage_stability.results.voltages[-1, :]

                self.color_based_of_pf(s_bus=self.voltage_stability.results.Sbus,
                                       s_branch=self.voltage_stability.results.Sbranch,
                                       voltages=V,
                                       loadings=self.voltage_stability.results.loading,
                                       types=self.circuit.numerical_circuit.bus_types)
                self.update_available_results()
            else:
                self.msg('The voltage stability did not converge.\nIs this case already at the collapse limit?')
        else:
            warn('Something went wrong, There are no voltage stability results.')
        self.UNLOCK()

    def run_time_series(self):
        """
        Run a time series power flow simulation in a separated thread from the gui
        @return:
        """
        if len(self.circuit.buses) > 0:

            if self.circuit.time_profile is not None:

                self.LOCK()

                self.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()

                use_opf_vals = self.ui.actionUse_OPF_in_TS.isChecked()

                if self.optimal_power_flow_time_series is None:
                    if use_opf_vals:
                        use_opf_vals = False
                        self.msg('There are not OPF time series, '
                                 'therefore this operation will continue with the profile stored values.')
                        self.ui.actionUse_OPF_in_TS.setChecked(False)

                    opf_time_series_results = None
                else:
                    opf_time_series_results = self.optimal_power_flow_time_series.results

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
                self.time_series.done_signal.connect(self.UNLOCK)
                self.time_series.done_signal.connect(self.post_time_series)

                self.time_series.start()

            else:
                self.msg('There are no time series.', 'Time series')
        else:
            pass

    def post_time_series(self):
        """
        Events to do when the time series simulation has finished
        @return:
        """

        if self.time_series.results is not None:

            voltage = self.time_series.results.voltage.max(axis=0)
            loading = self.time_series.results.loading.max(axis=0)
            Sbranch = self.time_series.results.Sbranch.max(axis=0)

            self.color_based_of_pf(s_bus=None, s_branch=Sbranch, voltages=voltage, loadings=loading,
                                   types=self.circuit.numerical_circuit.bus_types)

            self.update_available_results()

        else:
            print('No results for the time series simulation.')

    def run_stochastic(self):
        """
        Run a Monte Carlo simulation
        @return:
        """

        if len(self.circuit.buses) > 0:

            if self.circuit.time_profile is not None:

                self.LOCK()

                self.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()
                # self.compile()  # compiles inside

                options = self.get_selected_power_flow_options()

                tol = 10**(-1*self.ui.tolerance_stochastic_spinBox.value())
                max_iter = self.ui.max_iterations_stochastic_spinBox.value()
                self.monte_carlo = MonteCarlo(self.circuit, options, mc_tol=tol, batch_size=100, max_mc_iter=max_iter)

                self.monte_carlo.progress_signal.connect(self.ui.progressBar.setValue)
                self.monte_carlo.progress_text.connect(self.ui.progress_label.setText)
                self.monte_carlo.done_signal.connect(self.UNLOCK)
                self.monte_carlo.done_signal.connect(self.post_stochastic)

                self.monte_carlo.start()
            else:
                self.msg('There are no time series.')

        else:
            # self.msg('There are no time series.')
            pass

    def post_stochastic(self):
        """
        Actions to perform after the Monte Carlo simulation is finished
        @return:
        """
        if not self.monte_carlo.__cancel__:
            self.color_based_of_pf(voltages=self.monte_carlo.results.voltage,
                                   loadings=self.monte_carlo.results.loading,
                                   s_branch=self.monte_carlo.results.sbranch,
                                   types=self.circuit.numerical_circuit.bus_types,
                                   s_bus=None)
            self.update_available_results()

        else:
            pass

    def run_lhs(self):
        """
        Run a Monte Carlo simulation with Latin-Hypercube sampling
        @return:
        """

        if len(self.circuit.buses) > 0:

            if self.circuit.time_profile is not None:

                self.LOCK()

                self.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()
                # self.compile()  # compiles inside

                options = self.get_selected_power_flow_options()

                sampling_points = self.ui.lhs_samples_number_spinBox.value()

                self.latin_hypercube_sampling = LatinHypercubeSampling(self.circuit, options, sampling_points)

                self.latin_hypercube_sampling.progress_signal.connect(self.ui.progressBar.setValue)
                self.latin_hypercube_sampling.progress_text.connect(self.ui.progress_label.setText)
                self.latin_hypercube_sampling.done_signal.connect(self.UNLOCK)
                self.latin_hypercube_sampling.done_signal.connect(self.post_lhs)

                self.latin_hypercube_sampling.start()
            else:
                self.msg('There are no time series.')

        else:
            pass

    def post_lhs(self):
        """
        Actions to perform after the Monte Carlo simulation is finished
        @return:
        """
        # print('post_lhs')
        # update the results in the circuit structures
        # print('Vbus:\n', abs(self.latin_hypercube_sampling.results.voltage))
        # print('Ibr:\n', abs(self.latin_hypercube_sampling.results.current))
        # print('ld:\n', abs(self.latin_hypercube_sampling.results.loading))
        if not self.latin_hypercube_sampling.__cancel__:
            self.color_based_of_pf(voltages=self.latin_hypercube_sampling.results.voltage,
                                   loadings=self.latin_hypercube_sampling.results.loading,
                                   types=self.circuit.numerical_circuit.bus_types,
                                   s_branch=self.latin_hypercube_sampling.results.sbranch,
                                   s_bus=None)
            self.update_available_results()

        else:
            pass

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

            # self.ui.progress_label.setText('Compiling the grid...')
            # QtGui.QGuiApplication.processEvents()
            # self.compile()

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

            self.LOCK()

            self.ui.progress_label.setText('Compiling the grid...')
            QtGui.QGuiApplication.processEvents()
            # self.compile()  # compiles inside

            options = self.get_selected_power_flow_options()
            options.solver_type = SolverType.LM

            # step_by_step = self.ui.cascade_step_by_step_checkBox.isChecked()

            max_isl = self.ui.cascading_islands_spinBox.value()
            n_lsh_samples = self.ui.lhs_samples_number_spinBox.value()

            self.cascade = Cascading(self.circuit.copy(), options,
                                     max_additional_islands=max_isl,
                                     n_lhs_samples_=n_lsh_samples)

            # connect signals
            self.cascade.progress_signal.connect(self.ui.progressBar.setValue)
            self.cascade.progress_text.connect(self.ui.progress_label.setText)
            self.cascade.done_signal.connect(self.UNLOCK)
            self.cascade.done_signal.connect(self.post_cascade)

            # run
            self.cascade.start()

        else:
            pass

    def post_cascade(self, idx=None):
        """
        Actions to perform after the cascade simulation is finished
        """

        # update the results in the circuit structures

        n = len(self.cascade.results.events)

        if n > 0:

            # display the last event, if none is selected
            if idx is None:
                idx = n-1

            # Accumulate all the failed branches
            br_idx = zeros(0, dtype=int)
            for i in range(idx):
                br_idx = r_[br_idx, self.cascade.results.events[i].removed_idx]

            # pick the results at the designated cascade step
            results = self.cascade.results.events[idx].pf_results  # MonteCarloResults object

            # print grid
            self.color_based_of_pf(voltages=results.voltage,
                                   loadings=results.loading,
                                   types=self.circuit.numerical_circuit.bus_types,
                                   s_branch=results.sbranch,
                                   s_bus=None,
                                   failed_br_idx=br_idx)

            # Set cascade table
            self.ui.cascade_tableView.setModel(PandasModel(self.cascade.get_table()))

            # Update results
            self.update_available_results()

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
            self.LOCK()

            # get the power flow options from the GUI
            load_shedding = self.ui.load_shedding_checkBox.isChecked()
            realistic_results = self.ui.show_real_values_for_lp_checkBox.isChecked()
            generation_shedding = self.ui.generation_shedding_CheckBox.isChecked()
            solver = self.lp_solvers_dict[self.ui.lpf_solver_comboBox.currentText()]
            control_batteries = self.ui.control_batteries_checkBox.isChecked()
            load_shedding_w = self.ui.load_shedding_weight_spinBox.value()
            gen_shedding_w = self.ui.generation_shedding_weight_spinBox.value()
            pf_options = self.get_selected_power_flow_options()
            options = OptimalPowerFlowOptions(load_shedding=load_shedding,
                                              generation_shedding=generation_shedding,
                                              solver=solver,
                                              realistic_results=realistic_results,
                                              control_batteries=control_batteries,
                                              load_shedding_weight=load_shedding_w,
                                              generation_shedding_weight=gen_shedding_w,
                                              power_flow_options=pf_options)

            self.ui.progress_label.setText('Running optimal power flow...')
            QtGui.QGuiApplication.processEvents()
            # set power flow object instance
            self.optimal_power_flow = OptimalPowerFlow(self.circuit, options)

            # self.power_flow.progress_signal.connect(self.ui.progressBar.setValue)
            # self.power_flow.progress_text.connect(self.ui.progress_label.setText)
            # self.power_flow.done_signal.connect(self.UNLOCK)
            # self.power_flow.done_signal.connect(self.post_power_flow)

            # self.power_flow.run()
            self.threadpool.start(self.optimal_power_flow)
            self.threadpool.waitForDone()
            self.post_opf()
        else:
            pass

    def post_opf(self):
        """
        Actions to run after the OPF simulation
        """
        if self.optimal_power_flow is not None:

            if self.optimal_power_flow.results.converged:

                self.color_based_of_pf(voltages=self.optimal_power_flow.results.voltage,
                                       loadings=self.optimal_power_flow.results.loading,
                                       types=self.circuit.numerical_circuit.bus_types,
                                       s_branch=self.optimal_power_flow.results.Sbranch,
                                       s_bus=self.optimal_power_flow.results.Sbus)
                self.update_available_results()

            else:

                self.msg('Some islands did not solve.\n'
                         'Check that all branches have rating and \n'
                         'that there is a generator at the slack node.', 'OPF')

        self.UNLOCK()

    def run_opf_time_series(self):
        """
        OPF Time Series run
        :return:
        """
        if len(self.circuit.buses) > 0:

            if self.circuit.time_profile is not None:

                self.LOCK()

                # Compile the grid
                self.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()

                # get the power flow options from the GUI
                load_shedding = self.ui.load_shedding_checkBox.isChecked()
                realistic_results = self.ui.show_real_values_for_lp_checkBox.isChecked()
                generation_shedding = self.ui.generation_shedding_CheckBox.isChecked()
                solver = self.lp_solvers_dict[self.ui.lpf_solver_comboBox.currentText()]
                control_batteries = self.ui.control_batteries_checkBox.isChecked()
                load_shedding_w = self.ui.load_shedding_weight_spinBox.value()
                gen_shedding_w = self.ui.generation_shedding_weight_spinBox.value()
                pf_options = self.get_selected_power_flow_options()
                options = OptimalPowerFlowOptions(load_shedding=load_shedding,
                                                  generation_shedding=generation_shedding,
                                                  solver=solver,
                                                  realistic_results=realistic_results,
                                                  control_batteries=control_batteries,
                                                  load_shedding_weight=load_shedding_w,
                                                  generation_shedding_weight=gen_shedding_w,
                                                  power_flow_options=pf_options)

                start = self.ui.profile_start_slider.value()
                end = self.ui.profile_end_slider.value() + 1

                # create the OPF time series instance
                self.optimal_power_flow_time_series = OptimalPowerFlowTimeSeries(grid=self.circuit,
                                                                                 options=options,
                                                                                 start_=start,
                                                                                 end_=end)

                # make the thread connections to the GUI
                self.optimal_power_flow_time_series.progress_signal.connect(self.ui.progressBar.setValue)
                self.optimal_power_flow_time_series.progress_text.connect(self.ui.progress_label.setText)
                self.optimal_power_flow_time_series.done_signal.connect(self.UNLOCK)
                self.optimal_power_flow_time_series.done_signal.connect(self.post_opf_time_series)

                # Run
                self.optimal_power_flow_time_series.start()

            else:
                self.msg('There are no time series.\nLoad time series are needed for this simulation.')
        else:
            pass

    def post_opf_time_series(self):
        """
        Post OPF Time Series
        :return:
        """
        if self.optimal_power_flow_time_series is not None:

            voltage = self.optimal_power_flow_time_series.results.voltage.max(axis=0)
            loading = self.optimal_power_flow_time_series.results.loading.max(axis=0)
            Sbranch = self.optimal_power_flow_time_series.results.Sbranch.max(axis=0)

            self.color_based_of_pf(s_bus=None, s_branch=Sbranch, voltages=voltage, loadings=loading,
                                   types=self.circuit.numerical_circuit.bus_types)

            self.update_available_results()

        else:
            pass

    def run_transient_stability(self):
        """
        Run transient stability
        """
        if len(self.circuit.buses) > 0:

            if self.power_flow is not None:

                # Since we must run this study in the same conditions as
                # the last power flow, no compilation is needed

                self.LOCK()

                options = TransientStabilityOptions()
                options.t_sim = self.ui.transient_time_span_doubleSpinBox.value()
                options.h = self.ui.transient_time_step_doubleSpinBox.value()
                self.transient_stability = TransientStability(self.circuit,
                                                              options,
                                                              self.power_flow.results)

                try:
                    self.transient_stability.progress_signal.connect(self.ui.progressBar.setValue)
                    self.transient_stability.progress_text.connect(self.ui.progress_label.setText)
                    self.transient_stability.done_signal.connect(self.UNLOCK)
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

        self.update_available_results()

    def copy_opf_to_time_series(self):
        """
        Copy the OPF generation values to the Time series object and execute a time series simulation
        :return:
        """
        if len(self.circuit.buses) > 0:

            if self.circuit.time_profile is not None:

                if self.optimal_power_flow_time_series is not None:

                    quit_msg = "Are you sure you want overwrite the time events " \
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

            # compute the options
            rx_criteria = self.ui.rxThresholdCheckBox.isChecked()
            exponent = self.ui.rxThresholdSpinBox.value()
            rx_threshold = 1.0 / (10.0**exponent)
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

                        # reduce the grid
                        self.topology_reduction = TopologyReduction(grid=self.circuit, branch_indices=br_to_remove)

                        # Set the time series run options
                        self.topology_reduction.progress_signal.connect(self.ui.progressBar.setValue)
                        self.topology_reduction.progress_text.connect(self.ui.progress_label.setText)
                        self.topology_reduction.done_signal.connect(self.UNLOCK)
                        self.topology_reduction.done_signal.connect(self.post_reduce_grid)

                        self.topology_reduction.start()
                    else:
                        pass
                else:
                    self.msg('There were no branches identified', 'Topological grid reduction')
            else:
                self.msg('Select at least one reduction option in the topology settings', 'Topological grid reduction')
        else:
            pass

    def post_reduce_grid(self):
        """
        Actions after reducing
        :return:
        """
        self.create_schematic_from_api(explode_factor=1)

        self.clear_results()

    def storage_location(self):

        """
        Add storage markers to the schematic
        Returns:

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

            if self.monte_carlo is not None:
                self.monte_carlo.cancel()

            if self.latin_hypercube_sampling is not None:
                self.latin_hypercube_sampling.cancel()

            if self.optimal_power_flow_time_series is not None:
                self.optimal_power_flow_time_series.cancel()

            if self.cascade is not None:
                self.cascade.cancel()
        else:
            pass

    def update_available_results(self):
        """
        Update the results that are displayed in the results tab
        """
        lst = list()
        self.available_results_dict = dict()

        # clear results lists
        self.ui.result_type_listView.setModel(None)
        self.ui.result_element_selection_listView.setModel(None)

        if self.power_flow is not None:
            lst.append("Power Flow")
            self.available_results_dict["Power Flow"] = self.power_flow.results.available_results

        if self.voltage_stability is not None:
            lst.append("Voltage Stability")
            self.available_results_dict["Voltage Stability"] = self.voltage_stability.results.available_results

        if self.time_series is not None:
            lst.append("Time Series")
            self.available_results_dict["Time Series"] = self.time_series.results.available_results

        if self.monte_carlo is not None:
            lst.append("Monte Carlo")
            self.available_results_dict["Monte Carlo"] = self.monte_carlo.results.available_results

        if self.latin_hypercube_sampling is not None:
            lst.append("Latin Hypercube")
            self.available_results_dict["Latin Hypercube"] = self.latin_hypercube_sampling.results.available_results

        if self.short_circuit is not None:
            lst.append("Short Circuit")
            self.available_results_dict["Short Circuit"] = self.short_circuit.results.available_results

        if self.optimal_power_flow is not None:
            lst.append("Optimal power flow")
            self.available_results_dict["Optimal power flow"] = self.optimal_power_flow.results.available_results

        if self.optimal_power_flow_time_series is not None:
            lst.append("Optimal power flow time series")
            self.available_results_dict["Optimal power flow time series"] = self.optimal_power_flow_time_series.results.available_results

        if self.transient_stability is not None:
            lst.append("Transient stability")
            self.available_results_dict["Transient stability"] = self.transient_stability.results.available_results

        mdl = get_list_model(lst)
        self.ui.result_listView.setModel(mdl)

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

        self.buses_for_storage = None

        self.calculation_inputs_to_display = None
        self.ui.simulation_data_island_comboBox.clear()

        self.available_results_dict = dict()
        self.ui.result_listView.setModel(None)
        self.ui.resultsTableView.setModel(None)
        self.ui.result_type_listView.setModel(None)
        self.ui.result_element_selection_listView.setModel(None)

        self.ui.catalogueTableView.setModel(None)

        self.ui.simulationDataStructureTableView.setModel(None)
        self.ui.tableView.setModel(None)

        self.ui.dataStructureTableView.setModel(None)
        self.ui.catalogueTreeView.setModel(None)

        self.ui.resultsPlot.clear(force=True)
        # self.ui.resultsPlot.canvas.fig.clear()
        self.ui.resultsPlot.get_figure().set_facecolor('white')

        self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
        self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)

    def update_available_results_in_the_study(self):
        """
        Update the available results
        """
        elm = self.ui.result_listView.selectedIndexes()[0].data()
        lst = self.available_results_dict[elm]
        mdl = get_list_model(lst)
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

            study = self.ui.result_listView.selectedIndexes()[0].data()
            study_type = self.ui.result_type_listView.selectedIndexes()[0].data()

            if 'Bus' in study_type:
                names = self.circuit.bus_names
            elif 'Branch' in study_type:
                names = self.circuit.branch_names
            elif 'Load' in study_type:
                names = self.circuit.get_load_names()
            elif 'Controlled' in study_type:
                names = self.circuit.get_controlled_generator_names()
            elif 'Batter' in study_type:
                names = self.circuit.get_battery_names()
            else:
                names = None

            if indices is None:
                mdl = get_list_model(names, checks=True)
                self.ui.result_element_selection_listView.setModel(mdl)

            # clear the plot display
            self.ui.resultsPlot.clear()

            # get the plot axis
            ax = self.ui.resultsPlot.get_axis()

            self.results_df = None

            if study == 'Power Flow':
                self.results_df = self.power_flow.results.plot(result_type=study_type,
                                                               ax=ax, indices=indices, names=names)

            elif study == 'Time Series':
                self.results_df = self.time_series.results.plot(result_type=study_type,
                                                                ax=ax, indices=indices, names=names)

            elif study == 'Voltage Stability':
                self.results_df = self.voltage_stability.results.plot(result_type=study_type,
                                                                      ax=ax, indices=indices, names=names)

            elif study == 'Monte Carlo':
                self.results_df = self.monte_carlo.results.plot(result_type=study_type,
                                                                ax=ax, indices=indices, names=names)

            elif study == 'Latin Hypercube':
                self.results_df = self.latin_hypercube_sampling.results.plot(result_type=study_type,
                                                                             ax=ax, indices=indices, names=names)

            elif study == 'Short Circuit':
                self.results_df = self.short_circuit.results.plot(result_type=study_type,
                                                                  ax=ax, indices=indices, names=names)

            elif study == 'Optimal power flow':
                self.results_df = self.optimal_power_flow.results.plot(result_type=study_type,
                                                                       ax=ax, indices=indices, names=names)

            elif study == 'Optimal power flow time series':
                self.results_df = self.optimal_power_flow_time_series.results.plot(result_type=study_type,
                                                                                   ax=ax, indices=indices, names=names)

            elif study == 'Transient stability':
                self.results_df = self.transient_stability.results.plot(result_type=study_type,
                                                                        ax=ax, indices=indices, names=names)

            if self.results_df is not None:
                # set the table model
                res_mdl = PandasModel(self.results_df)
                self.ui.resultsTableView.setModel(res_mdl)

            # refresh the plot display (LEFT, RIGHT, TOP, BOTTOM are defined in CalculationEngine.py)
            self.ui.resultsPlot.get_figure().subplots_adjust(left=LEFT,
                                                             right=RIGHT,
                                                             top=TOP,
                                                             bottom=BOTTOM)
            self.ui.resultsPlot.redraw()

        else:
            pass

    def save_results_df(self):
        """
        Save the data displayed at the results as excel
        :return:
        """
        if self.results_df is not None:

            file = QFileDialog.getSaveFileName(self, "Save to Excel", '', filter="Excel files (*.xlsx)")

            if file[0] != '':

                if not file[0].endswith('.xlsx'):
                    f = file[0] + '.xlsx'
                else:
                    f = file[0]

                # Saving file
                self.results_df.astype(str).to_excel(f)

            else:
                print('Not saving file...')

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
        dialogue.resize(1.61 * 700.0, 700.0)
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
            self.ui.profile_label.setText(str(t1) + '->' + str(t2))

    def add_to_catalogue(self):
        """
        Add object to the catalogue
        :return:
        """
        print('Add')
        something_happened = False
        if len(self.ui.catalogueDataStructuresListView.selectedIndexes()) > 0:

            # get the object type
            tpe = self.ui.catalogueDataStructuresListView.selectedIndexes()[0].data()

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
                obj = Wire(name=name, xpos=0, ypos=0, gmr=0.01, r=0.01, x=0, phase=1)
                self.circuit.add_wire(obj)
                something_happened = True

            elif tpe == 'Transformers':

                name = 'XFormer_type_' + str(len(self.circuit.transformer_types))
                obj = TransformerType(hv_nominal_voltage=10, lv_nominal_voltage=0.4, nominal_power=2,
                                      copper_losses=0.8, iron_losses=0.1, no_load_current=0.1, short_circuit_voltage=0.1,
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
            tpe = self.ui.catalogueDataStructuresListView.selectedIndexes()[0].data()

            # get the selected index
            idx = self.ui.catalogueTableView.currentIndex().row()

            if idx > -1:
                if tpe == 'Overhead lines':

                    # pick the object
                    tower = self.circuit.overhead_line_types[idx]

                    # launch editor
                    dialogue = TowerBuilderGUI(tower=tower, wires_catalogue=self.circuit.wire_types)
                    dialogue.resize(1.81 * 600.0, 600.0)
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
            tpe = self.ui.catalogueDataStructuresListView.selectedIndexes()[0].data()

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
            tpe = self.ui.catalogueDataStructuresListView.selectedIndexes()[0].data()

            if tpe == 'Overhead lines':
                elm = Tower()
                mdl = ObjectsModel(self.circuit.overhead_line_types,
                                   elm.edit_headers, elm.units, elm.edit_types,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_indices=elm.non_editable_indices,
                                   check_unique=['tower_name'])

            elif tpe == 'Underground lines':
                elm = UndergroundLineType()
                mdl = ObjectsModel(self.circuit.underground_cable_types,
                                   elm.edit_headers, elm.units, elm.edit_types,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_indices=elm.non_editable_indices,
                                   check_unique=['name'])

            elif tpe == 'Sequence lines':
                elm = SequenceLineType()
                mdl = ObjectsModel(self.circuit.sequence_line_types,
                                   elm.edit_headers, elm.units, elm.edit_types,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_indices=elm.non_editable_indices,
                                   check_unique=['name'])
            elif tpe == 'Wires':
                elm = Wire(name='', xpos=0, ypos=0, gmr=0, r=0, x=0)
                mdl = ObjectsModel(self.circuit.wire_types,
                                   elm.edit_headers, elm.units, elm.edit_types,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_indices=elm.non_editable_indices,
                                   check_unique=['wire_name'])

            elif tpe == 'Transformers':
                elm = TransformerType(hv_nominal_voltage=10, lv_nominal_voltage=10, nominal_power=10,
                                      copper_losses=0, iron_losses=0, no_load_current=0.1, short_circuit_voltage=0.1,
                                      gr_hv1=0.5, gx_hv1=0.5)
                mdl = ObjectsModel(self.circuit.transformer_types,
                                   elm.edit_headers, elm.units, elm.edit_types,
                                   parent=self.ui.catalogueTableView, editable=True,
                                   non_editable_indices=elm.non_editable_indices,
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
        logger = list()

        if len(self.ui.catalogueTreeView.selectedIndexes()) > 0:

            # tree parent (category, i.e. Transformers)
            type_class = self.ui.catalogueTreeView.selectedIndexes()[0].parent().data()

            if type_class is not None:

                # template object name
                tpe_name = self.ui.catalogueTreeView.selectedIndexes()[0].data()

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
            print('Compiling...', end='')
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
        self.ui.simulation_data_island_comboBox.addItems(['Island ' + str(i) for i, circuit in enumerate(self.calculation_inputs_to_display)])
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


def run():
    """
    Main function to run the GUI
    :return:
    """
    app = QApplication(sys.argv)
    window = MainGUI()
    window.resize(int(1.61 * 700.0), 700)  # golden ratio :)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run()