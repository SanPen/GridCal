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

from GridCal.__version__ import __GridCal_VERSION__
from GridCal.Gui.Main.MainWindow import *
from GridCal.Gui.GridEditorWidget import *
from GridCal.Gui.ConsoleWidget import ConsoleWidget
from GridCal.Gui.ProfilesInput.profile_dialogue import ProfileInputGUI

import os.path
import platform
import sys
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


class ProfileTypes(Enum):
    Loads = 1,
    Generators = 2


class NewProfilesStructureDialogue(QDialog):
    """
    New profile dialogue window
    """
    def __init__(self):
        super(NewProfilesStructureDialogue, self).__init__()
        self.setObjectName("self")
        # self.resize(200, 71)
        # self.setMinimumSize(QtCore.QSize(200, 71))
        # self.setMaximumSize(QtCore.QSize(200, 71))
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        # icon = QtGui.QIcon()
        # icon.addPixmap(QtGui.QPixmap("Icons/Plus-32.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        # self.setWindowIcon(icon)
        self.layout = QVBoxLayout(self)

        # calendar
        self.calendar = QDateTimeEdit()
        d = datetime.today()
        self.calendar.setDateTime(QDateTime(d.year, 1, 1, 00, 00, 00))

        # number of time steps
        self.steps_spinner = QSpinBox()
        self.steps_spinner.setMinimum(1)
        self.steps_spinner.setMaximum(9999999)
        self.steps_spinner.setValue(1)

        # time step length
        self.step_length = QDoubleSpinBox()
        self.step_length.setMinimum(1)
        self.step_length.setMaximum(60)
        self.step_length.setValue(1)

        # units combo box
        self.units = QComboBox()
        self.units.setModel(get_list_model(['h', 'm', 's']))

        # accept button
        self.accept_btn = QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # labels

        # add all to the GUI
        self.layout.addWidget(QLabel("Start date"))
        self.layout.addWidget(self.calendar)

        self.layout.addWidget(QLabel("Number of time steps"))
        self.layout.addWidget(self.steps_spinner)

        self.layout.addWidget(QLabel("Time step length"))
        self.layout.addWidget(self.step_length)

        self.layout.addWidget(QLabel("Time units"))
        self.layout.addWidget(self.units)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle('New profiles structure')

    def accept_click(self):
        self.accept()

    def get_values(self):
        steps = self.steps_spinner.value()

        step_length = self.step_length.value()

        step_unit = self.units.currentText()

        time_base = self.calendar.dateTime()

        # a = QDateTime(2011, 4, 22, 00, 00, 00)
        # a
        return steps, step_length, step_unit, time_base.toPyDateTime()


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

        self.project_directory = None

        # solvers dictionary
        self.solvers_dict = OrderedDict()
        self.solvers_dict['Levenberg-Marquardt'] = SolverType.LM
        self.solvers_dict['Fast-Decoupled'] = SolverType.FASTDECOUPLED
        self.solvers_dict['Newton-Raphson'] = SolverType.NR
        # self.solvers_dict['NR Fast decoupled (BX)'] = SolverType.NRFD_BX
        # self.solvers_dict['NR Fast decoupled (XB)'] = SolverType.NRFD_XB
        self.solvers_dict['Newton-Raphson-Iwamoto'] = SolverType.IWAMOTO
        # self.solvers_dict['Gauss-Seidel'] = SolverType.GAUSS
        # self.solvers_dict['Z-Matrix Gauss-Seidel'] = SolverType.ZBUS
        self.solvers_dict['Holomorphic embedding [HELM]'] = SolverType.HELM
        # self.solvers_dict['Z-Matrix HELM'] = SolverType.HELMZ
        # self.solvers_dict['Continuation NR'] = SolverType.CONTINUATION_NR
        self.solvers_dict['Linear AC approximation'] = SolverType.LACPF
        self.solvers_dict['DC approximation'] = SolverType.DC

        lst = list(self.solvers_dict.keys())
        mdl = get_list_model(lst)
        self.ui.solver_comboBox.setModel(mdl)
        self.ui.retry_solver_comboBox.setModel(mdl)

        self.ui.solver_comboBox.setCurrentIndex(0)
        self.ui.retry_solver_comboBox.setCurrentIndex(0)

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

        # solvers dictionary
        self.lp_solvers_dict = OrderedDict()
        self.lp_solvers_dict['DC OPF'] = SolverType.DC_OPF
        self.lp_solvers_dict['AC OPF'] = SolverType.AC_OPF

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

        pfo = PowerFlowInput(1, 1)
        self.ui.simulationDataStructuresListView.setModel(get_list_model(pfo.available_structures))

        # add the widgets
        self.ui.schematic_layout.addWidget(self.grid_editor)
        self.grid_editor.setStretchFactor(1, 10)
        self.ui.splitter_8.setStretchFactor(1, 15)
        self.ui.simulationDataSplitter.setStretchFactor(1, 15)

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

        self.results_df = None

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

        # Table clicks
        self.ui.cascade_tableView.clicked.connect(self.cascade_table_click)

        # combobox
        self.ui.profile_device_type_comboBox.currentTextChanged.connect(self.profile_device_type_changed)

        # sliders
        self.ui.profile_start_slider.valueChanged.connect(self.profile_sliders_changed)
        self.ui.profile_end_slider.valueChanged.connect(self.profile_sliders_changed)

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
        # self.ui.actionTransient_stability.setVisible(True)
        # self.ui.tab_7.setVisible(True)
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

    def UNLOCK(self):
        """
        Unloack the interface
        @return:
        """
        self.LOCK(False)

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

        msg = 'GridCal\n\n'
        msg += 'Copyright (C) 2018 Santiago Peñate Vera.\n'
        msg += 'This program comes with ABSOLUTELY NO WARRANTY. \n'
        msg += 'This is free software, and you are welcome to redistribute it under certain conditions; \n\n'

        msg += "GridCal is licensed under the GNU general public license V.3 "
        msg += 'See the license file for more details. \n\n'

        msg += "GridCal has been carefully crafted since 2015 to serve as a platform for research and consultancy." \
               "The calculation engine has been designed in an object oriented fashion. " \
               "The Newton-Raphson power flow has been adapted from MatPower, and many other methods have been added, " \
               "enhancing them to run fast in the object oriented scheme.\n\n"

        msg += "The source of Gridcal can be found at:\n" + url + "\n\n"

        msg += "Gridcal version " + str(__GridCal_VERSION__) + '\n\n'

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
        class NodeType(Enum):
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
        dte = datetime.now().strftime("%b %d %Y %H:%M:%S")
        self.console.print_text('\n' + dte + '->' + msg_)

    def compile(self, use_opf_vals=False, dispatch_storage=False):
        """
        This function compiles the circuit and updates the UI accordingly
        """

        try:
            self.circuit.compile(use_opf_vals, dispatch_storage=dispatch_storage)
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.msg(str(exc_traceback) + '\n' + str(exc_value), 'Circuit compilation')

        if self.circuit.time_profile is not None:
            mdl = get_list_model(self.circuit.time_profile)
            self.ui.vs_departure_comboBox.setModel(mdl)
            self.ui.vs_target_comboBox.setModel(mdl)
            self.ui.profile_time_selection_comboBox.setModel(mdl)

    def auto_layout(self):
        """
        Automatic layout of the nodes
        """

        # guilty assumption
        do_it = True

        # if the ask, checkbox is checked, then ask
        if self.ui.ask_before_appliying_layout_checkBox.isChecked():
            reply = QMessageBox.question(self, 'Message', 'Are you sure you want to try an automatic layout?',
                                         QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                do_it = True
            else:
                do_it = False

        if do_it:
            if self.circuit.graph is None:
                self.circuit.compile()

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
                self.ui.dataStructuresListView.setModel(get_list_model(self.grid_editor.object_types))

                # delete all widgets
                for i in reversed(range(self.ui.schematic_layout.count())):
                    self.ui.schematic_layout.itemAt(i).widget().deleteLater()

                # add the widgets
                self.ui.schematic_layout.addWidget(self.grid_editor)
                self.ui.splitter_8.setStretchFactor(1, 15)

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
        # declare the allowed file types
        # files_types = "Excel (*.xlsx);;Excel 97 (*.xls);;DigSILENT (*.dgs);;MATPOWER (*.m);;PSS/e (*.raw)"

        files_types = "Formats (*.xlsx *.xls *.dgs *.m *.raw *.json)"
        # call dialog to select the file

        filename, type_selected = QFileDialog.getOpenFileName(self, 'Open file',
                                                              directory=self.project_directory,
                                                              filter=files_types)

        if len(filename) > 0:

            self.LOCK()

            # store the working directory
            self.project_directory = os.path.dirname(filename)
            # print(filename)
            self.circuit = MultiCircuit()

            self.ui.progress_label.setText('Loading file...')
            QtGui.QGuiApplication.processEvents()

            try:
                self.circuit.load_file(filename=filename)
            except Exception as ex:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.msg(str(exc_traceback) + '\n' + str(exc_value), 'File loading')

            # self.circuit.load_file(filename=filename)

            self.ui.progress_label.setText('Creating schematic...')
            QtGui.QGuiApplication.processEvents()
            self.create_schematic_from_api(explode_factor=1)
            self.grid_editor.name_label.setText(self.circuit.name)
            try:
                self.ui.comments_textEdit.setText(self.circuit.comments)
            except:
                pass
            self.ui.progress_label.setText('Compiling grid...')
            QtGui.QGuiApplication.processEvents()
            self.compile()

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

            self.ui.progress_label.setText('Done!')
            QtGui.QGuiApplication.processEvents()
            self.UNLOCK()

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
            # extension['Numpy Case (*.npz)'] = '.npz'

            if file_extension == '':
                filename = name + extension[type_selected]

            # call to save the file in the circuit

            self.circuit.save_file(filename)

            # try:
            #     self.circuit.save_file(filename)
            # except:
            #     exc_type, exc_value, exc_traceback = sys.exc_info()
            #     self.msg(str(exc_traceback) + '\n' + str(exc_value), 'File saving')

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
            if self.circuit.graph is None:
                self.circuit.compile()

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
                self.circuit.export_pf(file_name=filename)
        else:
            pass

    def export_object_profiles(self):
        """
        Export object profiles
        """
        if self.circuit.time_profile is not None:
            if self.circuit.graph is None:
                self.circuit.compile()

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
                self.circuit.export_profiles(file_name=filename)
        else:
            self.msg('There are no profiles!')

    def export_simulation_data(self):
        """
        Export the calculation objects to file
        """

        if self.circuit.graph is None:
            self.circuit.compile()

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
            self.circuit.save_calculation_objects(file_path=filename)

    def export_diagram(self):
        """
        Save the schematic
        :return:
        """
        if self.grid_editor is not None:

            # declare the allowed file types
            files_types = "Png (*.png)"

            # call dialog to select the file
            filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file',
                                                                  self.project_directory, files_types)

            if filename is not "":

                name, file_extension = os.path.splitext(filename)

                extension = dict()
                extension['Png (*.png)'] = '.png'

                # add the file extension if needed
                if file_extension == '':
                    filename = name + extension[type_selected]

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
        # clear all
        self.grid_editor.diagramView.scene_.clear()
        self.grid_editor.circuit = self.circuit  # set pointer to the circuit

        # first create the buses
        for bus in self.circuit.buses:
            # print(bus.x, bus.y)
            graphic_obj = self.grid_editor.diagramView.add_bus(bus=bus, explode_factor=explode_factor)
            graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
            bus.graphic_obj = graphic_obj
            bus.graphic_obj.create_children_icons()
            bus.graphic_obj.arrange_children()

        for branch in self.circuit.branches:
            terminal_from = branch.bus_from.graphic_obj.terminal
            terminal_to = branch.bus_to.graphic_obj.terminal
            graphic_obj = BranchGraphicItem(terminal_from, terminal_to, self.grid_editor.diagramScene, branch=branch)
            graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
            terminal_from.hosting_connections.append(graphic_obj)
            terminal_to.hosting_connections.append(graphic_obj)
            graphic_obj.redraw()
            branch.graphic_obj = graphic_obj

        # Align lines
        for bus in self.circuit.buses:
            bus.graphic_obj.arrange_children()

        #  center the view
        self.grid_editor.center_nodes()

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

                    S = self.circuit.power_flow_results.Sbranch[i]

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

                    branch.is_transformer = True

                else:

                    pass   # is a line

        else:
            self.msg('There are no branches!')

    def view_objects_data(self):
        """
        on click, display the objects properties
        Returns:

        """
        elm_type = self.ui.dataStructuresListView.selectedIndexes()[0].data()

        # ['Buses', 'Branches', 'Loads', 'Static Generators', 'Controlled Generators', 'Batteries']

        if elm_type == 'Buses':
            elm = Bus()
            mdl = ObjectsModel(self.circuit.buses, elm.edit_headers, elm.units, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True)

        elif elm_type == 'Branches':
            elm = Branch(None, None)
            mdl = ObjectsModel(self.circuit.branches, elm.edit_headers, elm.units, elm.edit_types,
                               parent=self.ui.dataStructureTableView, editable=True, non_editable_indices=[1, 2])

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

    def view_simulation_objects_data(self):
        """
        Simulation data structure clicked
        """

        i = self.ui.simulation_data_island_comboBox.currentIndex()

        if i > -1:
            if self.circuit.graph is None:
                self.circuit.compile()

            elm_type = self.ui.simulationDataStructuresListView.selectedIndexes()[0].data()

            df = self.circuit.circuits[i].power_flow_input.get_structure(elm_type)

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

            self.compile()

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

        # Assign profiles
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

        set_last_solution = self.ui.remember_last_solution_checkBox.isChecked()

        dispatch_storage = self.ui.dispatch_storage_checkBox.isChecked()

        if self.ui.helm_retry_checkBox.isChecked():
            solver_to_retry_with = self.solvers_dict[self.ui.retry_solver_comboBox.currentText()]
        else:
            solver_to_retry_with = None

        mp = self.ui.use_multiprocessing_checkBox.isChecked()

        ops = PowerFlowOptions(solver_type=solver_type,
                               aux_solver_type=solver_to_retry_with,
                               verbose=False,
                               robust=False,
                               initialize_with_existing_solution=True,
                               tolerance=tolerance,
                               max_iter=max_iter,
                               control_q=enforce_q_limits,
                               multi_core=mp,
                               dispatch_storage=dispatch_storage)

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
            self.compile()

            # get the power flow options from the GUI
            options = self.get_selected_power_flow_options()

            # compute the automatic precision
            if self.ui.auto_precision_checkBox.isChecked():
                lg = np.log10(abs(self.circuit.power_flow_input.Sbus.real))
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
        if self.circuit.power_flow_results is not None:
            # print('Vbus:\n', abs(self.circuit.power_flow_results.voltage))
            # print('Sbr:\n', abs(self.circuit.power_flow_results.Sbranch))
            # print('ld:\n', abs(self.circuit.power_flow_results.loading))

            self.ui.progress_label.setText('Colouring power flow results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.color_based_of_pf(s_bus=self.circuit.power_flow_results.Sbus,
                                   s_branch=self.circuit.power_flow_results.Sbranch,
                                   voltages=self.circuit.power_flow_results.voltage,
                                   loadings=self.circuit.power_flow_results.loading,
                                   types=self.circuit.power_flow_input.types,
                                   losses=self.circuit.power_flow_results.losses)
            self.update_available_results()

            msg_ = 'Power flow converged: ' + str(self.circuit.power_flow_results.converged) \
                   + '\n\terr: ' + str(self.circuit.power_flow_results.error) \
                   + '\n\telapsed: ' + str(self.circuit.power_flow_results.elapsed) \
                   + '\n\tmethods: ' + str(self.circuit.power_flow_results.methods) \
                   + '\n\tinner iter: ' + str(self.circuit.power_flow_results.inner_iterations) \
                   + '\n\touter iter: ' + str(self.circuit.power_flow_results.outer_iterations)
            self.console_msg(msg_)

        else:
            warn('Something went wrong, There are no power flow results.')
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
        if self.circuit.power_flow_results is not None:
            # print('Vbus:\n', abs(self.circuit.short_circuit_results.voltage))
            # print('Sbr:\n', abs(self.circuit.short_circuit_results.Sbranch))
            # print('ld:\n', abs(self.circuit.short_circuit_results.loading))

            self.ui.progress_label.setText('Colouring short circuit results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.color_based_of_pf(s_bus=self.circuit.short_circuit_results.Sbus,
                                   s_branch=self.circuit.short_circuit_results.Sbranch,
                                   voltages=self.circuit.short_circuit_results.voltage,
                                   types=self.circuit.power_flow_input.types,
                                   loadings=self.circuit.short_circuit_results.loading)
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
                    self.compile()

                    n = len(self.circuit.buses)
                    #  compose the base power
                    Sbase = zeros(n, dtype=complex)
                    for c in self.circuit.circuits:
                        Sbase[c.bus_original_idx] = c.power_flow_input.Sbus

                    vc_inputs = VoltageCollapseInput(Sbase=Sbase,
                                                     Vbase=self.power_flow.results.voltage,
                                                     Starget=Sbase * alpha)

                    # create object
                    self.voltage_stability = VoltageCollapse(grid=self.circuit, options=vc_options, inputs=vc_inputs)

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

                    self.compile()

                    self.power_flow.run_at(start_idx)

                    vc_inputs = VoltageCollapseInput(Sbase=self.circuit.time_series_input.Sprof.values[start_idx, :],
                                                     Vbase=self.power_flow.results.voltage,
                                                     Starget=self.circuit.time_series_input.Sprof.values[end_idx, :]
                                                     )

                    # create object
                    self.voltage_stability = VoltageCollapse(grid=self.circuit, options=vc_options, inputs=vc_inputs)

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
                # Sbus = V * conj(self.circuit.power_flow_input.Ybus * V)
                Sbranch, Ibranch, loading, losses, Sbus = self.power_flow.pf.power_flow_post_process(self.circuit, V)

                self.color_based_of_pf(s_bus=Sbus,
                                       s_branch=Sbranch,
                                       voltages=V,
                                       loadings=loading,
                                       types=self.circuit.power_flow_input.types)
                self.update_available_results()
            else:
                self.msg('The voltage stability did not converge.\nIs this case already at the collapse limit?')
        else:
            warn('Something went wrong, There are no power flow results.')
        self.UNLOCK()

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

                if self.optimal_power_flow_time_series is None and use_opf_vals:
                    use_opf_vals = False
                    self.msg('There are not OPF time series, '
                             'therefore this operation will continue with the profile stored values.')
                    self.ui.actionUse_OPF_in_TS.setChecked(False)

                options = self.get_selected_power_flow_options()

                self.compile(use_opf_vals=use_opf_vals, dispatch_storage=options.dispatch_storage)

                start = self.ui.profile_start_slider.value()
                end = self.ui.profile_end_slider.value() + 1

                self.time_series = TimeSeries(grid=self.circuit, options=options, start=start, end=end)

                # Set the time series run options
                self.time_series.progress_signal.connect(self.ui.progressBar.setValue)
                self.time_series.progress_text.connect(self.ui.progress_label.setText)
                self.time_series.done_signal.connect(self.UNLOCK)
                self.time_series.done_signal.connect(self.post_time_series)

                self.time_series.start()

            else:
                self.msg('There are no time series.')
        else:
            pass

    def post_time_series(self):
        """
        Events to do when the time series simulation has finished
        @return:
        """

        if self.circuit.time_series_results is not None:

            voltage = self.circuit.time_series_results.voltage.max(axis=0)
            loading = self.circuit.time_series_results.loading.max(axis=0)
            Sbranch = self.circuit.time_series_results.Sbranch.max(axis=0)

            self.color_based_of_pf(s_bus=None, s_branch=Sbranch, voltages=voltage, loadings=loading,
                                   types=self.circuit.power_flow_input.types)

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
                self.compile()

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
        # print('post_stochastic')
        # update the results in the circuit structures
        # print('Vbus:\n', abs(self.monte_carlo.results.voltage))
        # print('Ibr:\n', abs(self.monte_carlo.results.current))
        # print('ld:\n', abs(self.monte_carlo.results.loading))

        if not self.monte_carlo.__cancel__:
            self.color_based_of_pf(voltages=self.monte_carlo.results.voltage,
                                   loadings=self.monte_carlo.results.loading,
                                   s_branch=self.monte_carlo.results.sbranch,
                                   types=self.circuit.power_flow_input.types,
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
                self.compile()

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
                                   types=self.circuit.power_flow_input.types,
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
            self.compile()

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
                                   types=self.circuit.power_flow_input.types,
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

            self.ui.progress_label.setText('Compiling the grid...')
            QtGui.QGuiApplication.processEvents()
            self.compile()

            # get the power flow options from the GUI
            load_shedding = self.ui.load_shedding_checkBox.isChecked()
            realistic_results = self.ui.show_real_values_for_lp_checkBox.isChecked()
            solver = self.lp_solvers_dict[self.ui.lpf_solver_comboBox.currentText()]
            options = OptimalPowerFlowOptions(load_shedding=load_shedding,
                                              solver=solver,
                                              realistic_results=realistic_results)

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

            if self.optimal_power_flow.all_solved:

                self.color_based_of_pf(voltages=self.optimal_power_flow.results.voltage,
                                       loadings=self.optimal_power_flow.results.loading,
                                       types=self.circuit.power_flow_input.types,
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
                self.compile()

                # gather the simulation options
                load_shedding = self.ui.load_shedding_checkBox.isChecked()
                solver = self.lp_solvers_dict[self.ui.lpf_solver_comboBox.currentText()]
                options = OptimalPowerFlowOptions(load_shedding=load_shedding, solver=solver)
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
                                   types=self.circuit.power_flow_input.types)

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

    def set_cancel_state(self):
        """
        Cancel whatever's going on that can be cancelled
        @return:
        """
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

    def update_available_results(self):
        """
        Update the results that are displayed in the results tab
        """
        lst = list()
        self.available_results_dict = dict()
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

        # update the list of islands
        self.ui.simulation_data_island_comboBox.clear()
        self.ui.simulation_data_island_comboBox.addItems([str(circuit) for circuit in self.circuit.circuits])
        if len(self.circuit.circuits) > 0:
            self.ui.simulation_data_island_comboBox.setCurrentIndex(0)

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

        self.available_results_dict = dict()
        self.ui.result_listView.setModel(None)
        self.ui.resultsTableView.setModel(None)
        self.ui.result_type_listView.setModel(None)
        self.ui.result_element_selection_listView.setModel(None)
        self.ui.resultsPlot.clear(force=True)
        self.ui.simulationDataStructureTableView.setModel(None)
        self.ui.tableView.setModel(None)
        self.ui.transient_events_tableView.setModel(None)

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
                names = self.circuit.bus_names
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
            res_mdl = None
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
                res_mdl = PandasModel(self.results_df)

                # set hte table model
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