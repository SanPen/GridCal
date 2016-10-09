#!/usr/bin/env python3
__author__ = 'Santiago Peñate Vera'
"""
This class is the handler of the main GUI of GridCal.
"""

import sys
import os.path
from matplotlib.backend_bases import PickEvent, MouseEvent
import platform
import time
import pandas as pd
from PyQt4 import QtCore, QtGui
from numpy import take
from enum import Enum
import matplotlib
matplotlib.use("Qt4Agg")
from matplotlib import pyplot as plt

from GUI.main_gui.gui import *
from GUI.main_gui.profiles_input.profile_dialogue import *
from grid.CircuitModule import Circuit
from grid.PowerFlow import *
from grid.TimeSeries import *
from grid.MonteCarlo import *
from grid.BusDefinitions import *
from grid.GenDefinitions import *
from grid.BranchDefinitions import *

# define the IPython console
print(platform.system())
if platform.system() == 'Linux':
    from IPython.qt.console.rich_ipython_widget import RichIPythonWidget
    from IPython.qt.inprocess import QtInProcessKernelManager
    from IPython.lib import guisupport

    class QIPythonWidget(RichIPythonWidget):
        """
        Convenience class for a live IPython console widget.
        We can replace the standard banner using the customBanner argument
        """

        def __init__(self, customBanner=None, *args, **kwargs):
            if customBanner is not None:
                self.banner = customBanner
            super(QIPythonWidget, self).__init__(*args, **kwargs)
            self.kernel_manager = kernel_manager = QtInProcessKernelManager()
            kernel_manager.start_kernel(show_banner=False)
            kernel_manager.kernel.gui = 'qt4'
            self.kernel_client = kernel_client = self._kernel_manager.client()
            kernel_client.start_channels()

            def stop():
                kernel_client.stop_channels()
                kernel_manager.shutdown_kernel()
                guisupport.get_app_qt4().exit()

            self.exit_requested.connect(stop)

        def pushVariables(self, variableDict):
            """
            Given a dictionary containing name / value pairs, push those variables
            to the IPython console widget
            """
            self.kernel_manager.kernel.shell.push(variableDict)

        def clearTerminal(self):
            """
            Clears the terminal
            """
            self._control.clear()

            # self.kernel_manager

        def printText(self, text):
            """
            Prints some plain text to the console
            """
            self._append_plain_text(text)

        def executeCommand(self, command):
            """
            Execute a command in the frame of the console widget
            """
            self._execute(command, False)


elif platform.system() == 'Windows':
    from qtconsole.qt import QtGui
    from qtconsole.rich_jupyter_widget import RichJupyterWidget
    from qtconsole.inprocess import QtInProcessKernelManager

    class QIPythonWidget(RichJupyterWidget):
        """
        Convenience class for a live IPython console widget.
        We can replace the standard banner using the customBanner argument
        """
        def __init__(self, customBanner=None, *args, **kwargs):
            super(QIPythonWidget, self).__init__(*args, **kwargs)

            if customBanner is not None:
                self.banner = customBanner

            self.kernel_manager = kernel_manager = QtInProcessKernelManager()
            kernel_manager.start_kernel(show_banner=False)
            kernel_manager.kernel.gui = 'qt4'
            self.kernel_client = kernel_client = self._kernel_manager.client()
            kernel_client.start_channels()

            def stop():
                kernel_client.stop_channels()
                kernel_manager.shutdown_kernel()
                guisupport.get_app_qt4().exit()
            self.exit_requested.connect(stop)

        def pushVariables(self, variableDict):
            """
            Given a dictionary containing name / value pairs, push those variables
            to the IPython console widget
            """
            self.kernel_manager.kernel.shell.push(variableDict)

        def clearTerminal(self):
            """
            Clears the terminal
            """
            self._control.clear()

            # self.kernel_manager

        def printText(self, text):
            """
            Prints some plain text to the console
            """
            self._append_plain_text(text)

        def executeCommand(self, command):
            """
            Execute a command in the frame of the console widget
            """
            self._execute(command, False)


def list_to_listModel(lst):
    """
    Pass a list to a list model
    """
    list_model = QtGui.QStandardItemModel()
    i = 0
    if lst is not None:
        for val in lst:
            # for the list model
            item = QtGui.QStandardItem(val)
            item.setEditable(False)
            list_model.appendRow(item)

    return list_model


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


class MainGUI(QtGui.QMainWindow):

    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)

        # global vars
        self.lock_ui = False

        # global models
        self.results_tree_model = None

        # move node variable
        self.selected_node_idx = None
        self.click_input_time = None
        self.element_dragged = None
        self.pick_pos = None
        self.ui.gridPlot.canvas.mpl_connect("pick_event", self.on_pick_event)
        self.ui.gridPlot.canvas.mpl_connect("button_release_event", self.on_release_event)

        # plots set-up
        self.ui.gridPlot.setTitle("Network graph")
        self.ui.gridPlot.canvas.set_graph_mode()
        self.ui.gridPlot.canvas.ax.set_axis_off()
        self.ui.gridPlot.canvas.ax.get_figure().set_facecolor('w')
        self.ui.resultsPlot.canvas.ax.get_figure().set_facecolor('w')
        self.ui.statisticalGridPlot.canvas.ax.get_figure().set_facecolor('w')
        self.last_mode = 1
        self.node_size = 12

        # solvers combobox
        from collections import OrderedDict
        self.solvers_dict = OrderedDict()

        self.solvers_dict['Newton-Raphson [NR]'] = SolverType.NR
        self.solvers_dict['NR Fast decoupled (BX)'] = SolverType.NRFD_BX
        self.solvers_dict['NR Fast decoupled (XB)'] = SolverType.NRFD_XB
        self.solvers_dict['Newton-Raphson-Iwamoto'] = SolverType.IWAMOTO
        self.solvers_dict['Gauss-Seidel'] = SolverType.GAUSS
        self.solvers_dict['Z-Matrix Gauss-Seidel'] = SolverType.ZBUS
        self.solvers_dict['Holomorphic embedding [HELM]'] = SolverType.HELM
        self.solvers_dict['Z-Matrix HELM'] = SolverType.HELMZ
        self.solvers_dict['Continuation NR'] = SolverType.CONTINUATION_NR
        self.solvers_dict['DC approximation'] = SolverType.DC

        lst = list(self.solvers_dict.keys())
        # lst.sort()
        mdl = list_to_listModel(lst)
        self.ui.solver_comboBox.setModel(mdl)
        self.ui.retry_solver_comboBox.setModel(mdl)

        self.ui.solver_comboBox.setCurrentIndex(0)
        self.ui.retry_solver_comboBox.setCurrentIndex(3)

        # Directories
        self.project_directory = ""

        # Circuit
        self.circuit = Circuit()
        self.failed_edges = None

        # Stochastic
        self.ui.group_by_comboBox.addItem('No grouping')
        self.ui.group_by_comboBox.addItem('Day')
        self.ui.group_by_comboBox.addItem('Hour')
        self.ui.group_by_comboBox.setCurrentIndex(0)

        # list view models
        self.available_data_structures_listModel = list_to_listModel(self.circuit.available_data_structures)

        # tree view models
        # self.results_tree_model = None
        # self.family_results_per_family = dict()

        # console
        self.ipyConsole = QIPythonWidget(customBanner="GridCal console.\n\n"
                                                      "type gridcalhelp() to see the available specific commands.\n\n"
                                                      "the following libraries are already loaded:\n"
                                                      "np: numpy\n"
                                                      "pd: pandas\n"
                                                      "plt: matplotlib\n\n")
        self.ui.console_tab.layout().addWidget(self.ipyConsole)
        self.ipyConsole.pushVariables({"gridcalhelp": self.print_console_help, "np": np, "pd": pd, "plt": plt, "clc": self.clc})

        # Button clicks connection

        self.ui.importGenButton.clicked.connect(lambda: self.import_profiles(ProfileTypes.Generators))

        self.ui.importLoadButton.clicked.connect(lambda: self.import_profiles(ProfileTypes.Loads))

        self.ui.visualizeGenButton.clicked.connect(lambda: self.display_profiles_table(ProfileTypes.Generators))

        self.ui.visualizeLoadsButton.clicked.connect(lambda: self.display_profiles_table(ProfileTypes.Loads))

        self.ui.saveResultsButton.clicked.connect(self.saveResultsButton_click)

        self.ui.set_profile_state_button.clicked.connect(self.set_profile_state)

        self.ui.cancelButton.clicked.connect(self.cancel)

        self.ui.substation_apply_changes_button.clicked.connect(self.apply_substation_editor)

        self.ui.connections_apply_changes_button.clicked.connect(self.apply_connections_editor)

        self.ui.powerplants_apply_changes_button.clicked.connect(self.apply_powerplant_editor)

        self.ui.calculate_data_characterization_button.clicked.connect(self.init_statistical_characterization)

        # menu bar action click

        self.ui.actionRedraw.triggered.connect(self.re_plot)

        self.ui.actionRedrawByType.triggered.connect(self.display_graph_by_type)

        self.ui.actionRedrawByResult.triggered.connect(self.display_graph_by_type)

        self.ui.actionLine.triggered.connect(self.actionLine_click)

        self.ui.actionTransformer.triggered.connect(self.actionTransformer_click)

        self.ui.actionLine_type.triggered.connect(self.actionTransformer_click)

        self.ui.actionTransformer_type.triggered.connect(self.actionTransformer_type_click)

        self.ui.actionOpen_file.triggered.connect(self.open_file)

        self.ui.actionSave.triggered.connect(self.save_file)

        self.ui.actionPower_flow.triggered.connect(self.run_power_flow)

        self.ui.actionVoltage_stability.triggered.connect(self.run_voltage_stability)

        self.ui.actionPower_Flow_Time_series.triggered.connect(self.run_time_series)

        self.ui.actionPower_flow_Stochastic.triggered.connect(self.run_stochastic)

        self.ui.actionBlackout.triggered.connect(self.actionBlackout_click)

        self.ui.actionAbout.triggered.connect(self.about_box)

        # node size
        self.ui.actionBigger_nodes.triggered.connect(self.bigger_nodes)

        self.ui.actionSmaller_nodes.triggered.connect(self.smaller_nodes)

        # list clicks
        self.ui.dataStructuresListView.clicked.connect(self.display_objects_table)

        self.ui.substations_listview.clicked.connect(self.populate_substation_editor)

        self.ui.connections_listview.clicked.connect(self.populate_connections_editor)

        self.ui.powerplants_listView.clicked.connect(self.populate_powerplant_editor)

        # table clicks
        self.ui.dataStructureTableView.doubleClicked.connect(self.dataStructureTableView_doubleClick)

        self.ui.dataStructureTableView.clicked.connect(self.dataStructureTableView_click)

        # table pressed
        self.ui.dataStructureTableView.entered.connect(self.dataStructureTableView_click)

        # splitters positions
        # self.ui.splitter_4.setStretchFactor(0.1,  0.9)

        # spin box
        # QtCore.QObject.connect(self.ui.node_size_spinbox, QtCore.SIGNAL("valueChanged(int)"), self.re_plot)

        # tree view selection
        self.ui.pf_results_treeView.clicked.connect(self.handle_pf_tree_results)
        self.ui.sta_results_treeView.clicked.connect(self.handle_sta_tree_results)
        self.ui.ts_results_treeView.clicked.connect(self.handle_ts_tree_results)
        self.ui.sto_results_treeView.clicked.connect(self.handle_sto_tree_results)
        self.ui.statistical_characterization_treeview.clicked.connect(self.handle_tree_stc_selection)

        self.UNLOCK()

    ####################################################################################################################
    # General use functions
    ####################################################################################################################

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

    def date64_to_str(self, dte):
        """
        Pretty-print for date64 values
        @param dte:
        @return:
        """
        import pandas as pd
        ts = pd.to_datetime(str(dte))
        return ts.strftime('%d/%m/%Y %H:%M:%S')

    def about_box(self):

        url = 'https://github.com/SanPen/GridCal'

        msg = "GridCal is a research oriented electrical grid calculation software.\n"
        msg += "GridCal has been designed by Santiago Peñate Vera since 2015.\n"
        msg += "The calculation engine has been adapted from MatPower, \n" \
               "enhancing it and turning it into a fast object oriented power flow solver.\n\n"

        msg += "The source of Gridcal can be found at:\n" + url + "\n"

        QtGui.QMessageBox.about(self, "About GridCal", msg)

    ####################################################################################################################
    # Grid graph functions
    ####################################################################################################################

    def on_pick_event(self, event):
        """
        Store which text object was picked and were the pick event occurs.
        """
        self.element_dragged = event.artist
        self.pick_pos = (event.mouseevent.xdata, event.mouseevent.ydata)
        self.selected_node_idx = event.ind[0]

        # print('selected:', self.selected_node_idx)

        self.click_input_time = int(round(time.time() * 1000))

        self.ui.gridPlot.canvas.rec_zoom()

        return True

    def on_release_event(self, event):
        """
        Update text position and redraw
        """

        if self.click_input_time is not None:

            click_output_time = int(round(time.time() * 1000))

            # if the time elapsed since the pick and the release is > 400 ms, we're dragging otherwise just clicking
            dragging = (click_output_time - self.click_input_time) > 400

            if dragging:
                old_pos = self.element_dragged.get_offsets()[self.selected_node_idx]
                old_pos = np.ndarray.flatten(old_pos)

                if event.xdata is not None and event.ydata is not None:
                    new_pos = (old_pos[0] + event.xdata - self.pick_pos[0],
                               old_pos[1] + event.ydata - self.pick_pos[1])

                    if abs(new_pos - old_pos).any() > 0.7:
                        self.move_bus(new_pos, self.selected_node_idx)

            else:
                # Clicking an element
                # x = self.circuit.bus[:, BUS_X]
                # y = self.circuit.bus[:, BUS_Y]
                # self.node_xy = x, y
                data = self.circuit.bus[self.selected_node_idx, :]
                name = self.circuit.bus_names[self.selected_node_idx]
                df = pd.DataFrame(data=data.transpose(), index=bus_headers, columns=[name])
                model = PandasModel(df)
                self.ui.item_table.setModel(model)

        # un-select to prevent weird behaviours
        self.selected_node_idx = None
        self.click_input_time = None
        self.element_dragged = None
        self.pick_pos = None

        return True

    def move_bus(self, newpos, idx=None):
        """
        Action to move bus on screen
        """
        if self.selected_node_idx is not None:
            self.circuit.bus[self.selected_node_idx, BUS_X] = newpos[0]
            self.circuit.bus[self.selected_node_idx, BUS_Y] = newpos[1]
            self.circuit.graph_pos[self.selected_node_idx] = newpos

            self.re_plot()

    def cancel(self):
        """
        Cancell all the background process threads
        Returns:

        """
        quit_msg = "Are you sure you want to cancel the process?"
        reply = QtGui.QMessageBox.question(self, 'Cancel process',
                         quit_msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            if self.circuit.power_flow is not None:
                self.circuit.power_flow.end_process()
            if self.circuit.time_series is not None:
                self.circuit.time_series.end_process()
            if self.circuit.voltage_stability is not None:
                self.circuit.voltage_stability.end_process()
            if self.circuit.monte_carlo is not None:
                self.circuit.monte_carlo.end_process()
            self.UNLOCK()
        else:
            pass

    def re_plot(self):
        """
        Re-plot the graph
        :return:
        """
        # plot
        # print('replot')
        if self.circuit.circuit_graph is not None:
            self.ui.gridPlot.clear()

            mode_ = self.last_mode

            artist, self.last_mode = self.circuit.plot_graph(ax=self.ui.gridPlot.canvas.ax,
                                                             mode=mode_,
                                                             pos=self.circuit.graph_pos,
                                                             node_size=self.node_size*100)
            self.ui.gridPlot.canvas.set_last_zoom()
            self.ui.gridPlot.redraw()

    def display_graph_by_results(self):
        """
        display the graph using the color code of the results (gradient values)
        @return:
        """
        # print('By result')
        self.last_mode = 2
        self.re_plot()

    def display_graph_by_type(self):
        """
        display the graph using the color code of the node type
        @return:
        """
        # print('By type')
        self.last_mode = 1
        self.re_plot()

    def bigger_nodes(self):
        """
        Increase the nodes size
        :return:
        """
        self.node_size += 2
        if self.node_size > 54:
            self.node_size = 54

        self.re_plot()

    def smaller_nodes(self):
        """
        reduce the nodes size
        :return:
        """
        self.node_size -=2
        if self.node_size < 2:
            self.node_size = 2

        self.re_plot()

    ####################################################################################################################
    # Editors functions
    ####################################################################################################################

    def populate_editors_defaults(self):
        """
        Create the editors default values
        @return:
        """
        # nodes names list model
        bus_model = QtGui.QStandardItemModel(self)
        for elm in self.circuit.bus_names:
            item = QtGui.QStandardItem(elm)
            item.setEditable(False)
            bus_model.appendRow(item)

        branch_model = QtGui.QStandardItemModel(self)
        for elm in self.circuit.branch_names:
            item = QtGui.QStandardItem(elm)
            item.setEditable(False)
            branch_model.appendRow(item)

        gen_model = QtGui.QStandardItemModel(self)
        for elm in self.circuit.gen_names:
            item = QtGui.QStandardItem(elm)
            item.setEditable(False)
            gen_model.appendRow(item)

        # substations
        self.ui.substations_listview.setModel(bus_model)

        # connections
        self.ui.connections_listview.setModel(branch_model)
        self.ui.connections_bus1.setModel(bus_model)
        self.ui.connections_bus2.setModel(bus_model)

        # power plants
        self.ui.powerplants_listView.setModel(gen_model)
        self.ui.powerplants_bus.setModel(bus_model)

        # link executors
        self.ui.substations_listview.selectionModel().selectionChanged.connect(self.populate_substation_editor)
        self.ui.connections_listview.selectionModel().selectionChanged.connect(self.populate_connections_editor)
        self.ui.powerplants_listView.selectionModel().selectionChanged.connect(self.populate_powerplant_editor)

    def populate_substation_editor(self, index):
        """
        Fill the substation editor given the substation index
        @param index:
        @return:
        """
        if isinstance(index, QtGui.QItemSelection):
            idx = index.indexes()[0].row()
        else:
            idx = index.row()
        # print(idx)
        self.ui.substation_name.setText(self.circuit.bus_names[idx])
        self.ui.substation_basekva.setValue(self.circuit.bus[idx, BASE_KV])

        self.ui.substation_vabs.setValue(self.circuit.bus[idx, VM])
        self.ui.substation_vangle.setValue(self.circuit.bus[idx, VA])
        self.ui.substation_vmax.setValue(self.circuit.bus[idx, VMAX])
        self.ui.substation_vmin.setValue(self.circuit.bus[idx, VMIN])

        self.ui.substation_p.setValue(self.circuit.bus[idx, PD])
        self.ui.substation_q.setValue(self.circuit.bus[idx, QD])
        self.ui.substation_g.setValue(self.circuit.bus[idx, GS])
        self.ui.substation_b.setValue(self.circuit.bus[idx, BS])

        self.ui.substation_slack_checkBox.setChecked(self.circuit.bus[idx, BUS_TYPE] == 3)

        self.ui.dispatchable_load_checkBox.setChecked(self.circuit.bus[idx, DISPATCHABLE_BUS] == 1)

        self.ui.substation_fix_power_checkBox.setChecked(self.circuit.bus[idx, FIX_POWER_BUS] == 1)

    def apply_substation_editor(self):
        """
        Apply to the buses structure the substation edited values
        @return:
        """
        if len(self.ui.substations_listview.selectedIndexes()) > 0:
            index = self.ui.substations_listview.selectedIndexes()[0]
            idx = index.row()

            if idx > -1:
                busname = self.ui.substation_name.text()
                self.circuit.bus_names[idx] = busname
                self.circuit.bus[idx, BASE_KV] = self.ui.substation_basekva.value()

                is_gen_node = idx in self.circuit.gen[:, GEN_BUS].astype(int)

                if self.ui.substation_slack_checkBox.isChecked():
                    if is_gen_node:
                        self.circuit.bus[idx, BUS_TYPE] = 3  # SLACK
                    else:
                        self.ui.substation_slack_checkBox.setChecked(False)
                else:
                    if is_gen_node:
                        self.circuit.bus[idx, BUS_TYPE] = 2  # PV
                    else:
                        self.circuit.bus[idx, BUS_TYPE] = 1  # PQ

                self.circuit.bus[idx, DISPATCHABLE_BUS] = int(self.ui.dispatchable_load_checkBox.isChecked())
                self.circuit.bus[idx, FIX_POWER_BUS] = int(self.ui.substation_fix_power_checkBox.isChecked())

                self.circuit.bus[idx, VM] = self.ui.substation_vabs.value()
                self.circuit.bus[idx, VA] = self.ui.substation_vangle.value()
                self.circuit.bus[idx, VMAX] = self.ui.substation_vmax.value()
                self.circuit.bus[idx, VMIN] = self.ui.substation_vmin.value()

                self.circuit.bus[idx, PD] = self.ui.substation_p.value()
                self.circuit.bus[idx, QD] = self.ui.substation_q.value()
                self.circuit.bus[idx, GS] = self.ui.substation_g.value()
                self.circuit.bus[idx, BS] = self.ui.substation_b.value()

                self.ui.substations_listview.model().item(idx).setText(busname)
                self.ui.connections_bus1.model().item(idx).setText(busname)
                self.ui.connections_bus2.model().item(idx).setText(busname)
                self.ui.powerplants_bus.model().item(idx).setText(busname)

    def populate_connections_editor(self, index):
        """
        Fill the connections editor given the selected branch index
        @param index:
        @return:
        """
        if isinstance(index, QtGui.QItemSelection):
            idx = index.indexes()[0].row()
        else:
            idx = index.row()

        self.ui.connections_name.setText(self.circuit.branch_names[idx])

        self.ui.connections_bus1.setCurrentIndex(self.circuit.branch[idx, F_BUS])
        self.ui.connections_bus2.setCurrentIndex(self.circuit.branch[idx, T_BUS])

        self.ui.connections_status.setChecked(self.circuit.branch[idx, BR_STATUS] == 1)

        self.ui.connections_r.setValue(self.circuit.branch[idx, BR_R])
        self.ui.connections_x.setValue(self.circuit.branch[idx, BR_X])
        self.ui.connections_b.setValue(self.circuit.branch[idx, BR_B])

        self.ui.connections_nominal_power.setValue(self.circuit.branch[idx, RATE_A])
        self.ui.connections_ratio.setValue(self.circuit.branch[idx, TAP])
        self.ui.connections_shift.setValue(self.circuit.branch[idx, SHIFT])

    def apply_connections_editor(self):
        """
        Apply the connections edited values to the branches structure
        @return:
        """
        if len(self.ui.connections_listview.selectedIndexes()) > 0:
            idx = self.ui.connections_listview.selectedIndexes()[0].row()

            if idx > -1:
                self.circuit.branch_names[idx] = self.ui.connections_name.text()

                self.circuit.branch[idx, F_BUS] = self.ui.connections_bus1.currentIndex()
                self.circuit.branch[idx, T_BUS] = self.ui.connections_bus2.currentIndex()

                if self.ui.connections_status.isChecked():
                    self.circuit.branch[idx, BR_STATUS] = 1
                else:
                    self.circuit.branch[idx, BR_STATUS] = 0

                self.circuit.branch[idx, BR_R] = self.ui.connections_r.value()
                self.circuit.branch[idx, BR_X] = self.ui.connections_x.value()
                self.circuit.branch[idx, BR_B] = self.ui.connections_b.value()

                self.circuit.branch[idx, RATE_A] = self.ui.connections_nominal_power.value()
                self.circuit.branch[idx, TAP] = self.ui.connections_ratio.value()
                self.circuit.branch[idx, SHIFT] = self.ui.connections_shift.value()

                self.ui.connections_listview.model().item(idx).setText(self.circuit.branch_names[idx])

    def populate_powerplant_editor(self, index):
        """
        Fill the power plant editor given the generators selected index
        @param index:
        @return:
        """
        if isinstance(index, QtGui.QItemSelection):
            idx = index.indexes()[0].row()
        else:
            idx = index.row()

        self.ui.powerplants_name.setText(self.circuit.gen_names[idx])
        self.ui.powerplants_bus.setCurrentIndex(self.circuit.gen[idx, GEN_BUS])

        self.ui.powerplants_basepower.setValue(self.circuit.gen[idx, MBASE])
        self.ui.powerplants_status.setChecked(self.circuit.gen[idx, GEN_STATUS] == 1)

        self.ui.powerplants_p.setValue(self.circuit.gen[idx, PG])
        self.ui.powerplants_v.setValue(self.circuit.gen[idx, VG])

        self.ui.powerplants_pmax.setValue(self.circuit.gen[idx, PMAX])
        self.ui.powerplants_pmin.setValue(self.circuit.gen[idx, PMIN])
        self.ui.powerplants_qmax.setValue(self.circuit.gen[idx, QMIN])
        self.ui.powerplants_qmin.setValue(self.circuit.gen[idx, QMAX])

        self.ui.dispatchable_gen_checkBox.setChecked(self.circuit.gen[idx, DISPATCHABLE_GEN] == 1)

        self.ui.powerplants_fix_power_checkBox.setChecked(self.circuit.gen[idx, FIX_POWER_GEN] == 1)

    def apply_powerplant_editor(self):
        """
        Apply the power plant edited values to the generators structure
        @return:
        """
        if len(self.ui.powerplants_listView.selectedIndexes()) > 0:
            idx = self.ui.powerplants_listView.selectedIndexes()[0].row()

            if idx > -1:
                self.circuit.gen_names[idx] = self.ui.powerplants_name.text()
                self.circuit.gen[idx, GEN_BUS] = self.ui.powerplants_bus.currentIndex()

                self.circuit.gen[idx, MBASE] = self.ui.powerplants_basepower.value()

                self.circuit.gen[idx, GEN_STATUS] = int(self.ui.powerplants_status.isChecked())
                self.circuit.gen[idx, DISPATCHABLE_GEN] = int(self.ui.dispatchable_gen_checkBox.isChecked())
                self.circuit.gen[idx, FIX_POWER_GEN] = int(self.ui.powerplants_fix_power_checkBox.isChecked())

                self.circuit.gen[idx, PG] = self.ui.powerplants_p.value()
                self.circuit.gen[idx, VG] = self.ui.powerplants_v.value()

                self.circuit.gen[idx, PMAX] = self.ui.powerplants_pmax.value()
                self.circuit.gen[idx, PMIN] = self.ui.powerplants_pmin.value()
                self.circuit.gen[idx, QMIN] = self.ui.powerplants_qmax.value()
                self.circuit.gen[idx, QMAX] = self.ui.powerplants_qmin.value()

                self.ui.powerplants_listView.model().item(idx).setText(self.circuit.gen_names[idx])

    ####################################################################################################################

    def saveResultsButton_click(self):
        """
        Save the results table to excel
        @return:
        """
        print("saveResultsButton_click")

        mdl = self.ui.resultsTableView.model()
        if mdl is not None:
            df = pd.DataFrame(data=mdl._data, index=mdl.index, columns=mdl._cols)

            # declare the allowed file types
            files_types = "Excel (*.xlsx);;Numpy Case (*.npz)"
            # call dialog to select the file
            filename, type_selected = QtGui.QFileDialog.getSaveFileNameAndFilter(self, 'Save file',
                                                                                 self.project_directory,
                                                                                 files_types)

            if filename is not "":
                # if the user did not enter the extension, add it automatically
                name, file_extension = os.path.splitext(filename)

                extension = dict()
                extension['Excel 97 (*.xls)'] = '.xls'
                extension['Excel (*.xlsx)'] = '.xlsx'
                extension['Numpy Case (*.npz)'] = '.npz'

                if file_extension == '':
                    filename = name + extension[type_selected]

                df.to_excel(filename, 'Results')

                print("Copied!")

    def actionLine_click(self):
        print("actionLine_click")

    def actionTransformer_click(self):
        print("actionTransformer_click")

    def actionLine_type_click(self):
        print("actionLine_type_click")

    def actionTransformer_type_click(self):
        print("actionTransformer_type_click")

    def set_time_comboboxes(self):
        """
        Sets the time indices in the comboboxes to select the profiles snapshot
        Returns:

        """
        self.ui.profile_time_selection_comboBox.clear()
        self.ui.results_time_selection_comboBox.clear()

        # arr = list(self.date64_to_str(self.circuit.time_series.time))
        for tme in self.circuit.time_series.time:
            arr = self.date64_to_str(tme)
            self.ui.profile_time_selection_comboBox.addItem(arr)
            self.ui.results_time_selection_comboBox.addItem(arr)

    def set_profile_state(self):
        """
        Sets a snapshot of the time profiles to the current state of the circuit
        Returns:

        """
        if self.circuit.time_series is not None:
            idx = self.ui.profile_time_selection_comboBox.currentIndex()

            if self.circuit.time_series.is_ready():
                if idx > -1:

                    if self.circuit.time_series.has_results():
                        self.circuit.set_time_profile_state_to_the_circuit(idx, True)
                    else:
                        self.circuit.set_time_profile_state_to_the_circuit(idx, False)

                    self.re_plot()
            else:
                print('There are no profiles!')

    def open_file(self):
        """
        Open a file
        :return:
        """
        # declare the allowed file types
        files_types = "Excel 97 (*.xls);;Excel (*.xlsx);;DigSILENT (*.dgs);;MATPOWER (*.m)"
        # call dialog to select the file
        filename, type_selected = QtGui.QFileDialog.getOpenFileNameAndFilter(self, 'Open file',
                                                                             self.project_directory,
                                                                             files_types)

        if len(filename) > 0:
            # store the working directory
            self.project_directory = os.path.dirname(filename)
            print(filename)
            self.circuit = Circuit(filename, True)

            # set data structures list model
            self.ui.dataStructuresListView.setModel(self.available_data_structures_listModel)
            # set the first index
            index = self.available_data_structures_listModel.index(0, 0, QtCore.QModelIndex())
            self.ui.dataStructuresListView.setCurrentIndex(index)

            # clean UI
            self.clean_GUI()

            # load table
            self.display_objects_table()

            # draw graph
            self.ui.gridPlot.setTitle(os.path.basename(filename))
            self.re_plot()

            # show times
            if self.circuit.time_series is not None:
                if self.circuit.time_series.is_ready():
                    self.set_time_comboboxes()

            # tree view at the results
            # self.set_results_treeview_structure()

            # populate editors
            self.populate_editors_defaults()

    def pass_to_QStandardItem_list(self, list_):
        """
        Creates a list of QStandardItem from a list
        @param list_:
        @return:
        """
        res = list()
        for elm in list_:
            elm1 = QtGui.QStandardItem(elm)
            elm1.setEditable(False)
            res.append(elm1)
        return res

    def set_pf_results_treeview_structure(self, tree: QtGui.QTreeView, bus_results, branch_results, gen_results):
        """
        Sets the results tree-view data structure
        @return:
        """
        model = QtGui.QStandardItemModel()
        model.setParent(tree)
        model.setHorizontalHeaderLabels(['Elements'])

        tree.setModel(model)
        tree.setUniformRowHeights(True)
        tree.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)

        per_bus_results = self.pass_to_QStandardItem_list(bus_results)
        per_branch_results = self.pass_to_QStandardItem_list(branch_results)
        per_generator_results = self.pass_to_QStandardItem_list(gen_results)

        # nodes
        if len(bus_results) > 0:
            buses = QtGui.QStandardItem('Buses')
            buses.setEditable(False)

            bus = QtGui.QStandardItem('All')
            bus.appendRows(per_bus_results)
            bus.setEditable(False)
            buses.appendRow(bus)

            names = self.circuit.bus_names
            for name in names:
                bus = QtGui.QStandardItem(name)
                bus.appendRows(per_bus_results)
                bus.setEditable(False)
                buses.appendRow(bus)

            model.appendRow(buses)

        # branches
        if len(branch_results) > 0:
            branches = QtGui.QStandardItem('Branches')
            branches.setEditable(False)

            branch = QtGui.QStandardItem('All')
            branch.appendRows(per_branch_results)
            branch.setEditable(False)
            branches.appendRow(branch)

            names = self.circuit.branch_names
            for name in names:
                branch = QtGui.QStandardItem(name)
                branch.appendRows(per_branch_results)
                branch.setEditable(False)
                branches.appendRow(branch)

            model.appendRow(branches)

        # generators
        if len(gen_results) > 0:
            generators = QtGui.QStandardItem('Generators')
            generators.setEditable(False)

            gen = QtGui.QStandardItem('All')
            gen.appendRows(per_generator_results)
            gen.setEditable(False)
            generators.appendRow(gen)

            names = self.circuit.gen_names
            for name in names:
                gen = QtGui.QStandardItem(name)
                gen.appendRows(per_generator_results)
                gen.setEditable(False)
                generators.appendRow(gen)

            model.appendRow(generators)

    def set_statistical_characterization_treeview(self):
        """
        Set the statistical characterization tree view
        @return:
        """
        self.stcm_tree_model = QtGui.QStandardItemModel()
        self.stcm_tree_model.setParent(self.ui.statistical_characterization_treeview)
        self.stcm_tree_model.setHorizontalHeaderLabels(['Time groups'])

        self.ui.statistical_characterization_treeview.setModel(self.stcm_tree_model)
        self.ui.statistical_characterization_treeview.setUniformRowHeights(True)
        self.ui.statistical_characterization_treeview.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)

        # nodes
        for i in range(len(self.circuit.monte_carlo.stat_groups)):
            name = self.date64_to_str(self.circuit.monte_carlo.t_from[i]) + '->' + self.date64_to_str(self.circuit.monte_carlo.t_to[i])
            item = QtGui.QStandardItem(name)
            item.setEditable(False)
            self.stcm_tree_model.appendRow(item)

        # self.stcm_tree_model.appendRow(times)

    def save_file(self):
        """
        Save the circuit case to a file
        """
        # declare the allowed file types
        files_types = "Excel 97 (*.xls);;Excel (*.xlsx);;Numpy Case (*.npz);;JSON (*.json)"
        # call dialog to select the file
        filename, type_selected = QtGui.QFileDialog.getSaveFileNameAndFilter(self, 'Save file',
                                                                             self.project_directory,
                                                                             files_types)

        if filename is not "":
            # if the user did not enter the extension, add it automatically
            name, file_extension = os.path.splitext(filename)

            extension = dict()
            extension['Excel 97 (*.xls)'] = '.xls'
            extension['Excel (*.xlsx)'] = '.xlsx'
            extension['Numpy Case (*.npz)'] = '.npz'

            if file_extension == '':
                filename = name + extension[type_selected]

            # call to save the file in the circuit
            self.circuit.save_circuit(filename)

    def import_profiles(self, profile_type):
        """
        Call the dialogue to import profiles
        @param profile_type: Type of profile to import
        @return:
        """
        if self.circuit.circuit_graph is not None:
            if profile_type == ProfileTypes.Loads:
                idx = self.circuit.bus[:, BUS_I].astype(int)
                labels = self.circuit.bus_names
                alsoQ = True
            elif profile_type == ProfileTypes.Generators:
                idx = self.circuit.gen[:, GEN_BUS].astype(int)
                labels = self.circuit.gen_names
                alsoQ = False
            else:
                return

            # collect the profiles
            dialog = ProfileInputGUI(self, labels, alsoQ)
            dialog.exec_()
            profiles, time_profile, zeroed = dialog.get_profile(self, labels, alsoQ)

            if profiles is not None:
                # replace time profile
                if self.circuit.time_series.time is None:
                    self.circuit.time_series.set_master_time(time_profile)
                elif (time_profile != self.circuit.time_series.time).all():
                    # prompt to replace the time profile
                    quit_msg = "Replace the master time?"
                    reply = QtGui.QMessageBox.question(self, 'GridCal',quit_msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
                    if reply == QtGui.QMessageBox.Yes:
                        self.circuit.time_series.set_master_time(time_profile)

                # set the profile where it corresponds
                if profile_type == ProfileTypes.Loads:
                    self.circuit.time_series.set_loads_profile(profiles)
                elif profile_type == ProfileTypes.Generators:
                    self.circuit.time_series.set_generators_profile(profiles)
                else:
                    return

                # show the imported profile
                self.display_profile(profile_type)
                # display times
                self.set_time_comboboxes()

    def get_tree_depth(self, elm):
        """
        Given a treeview clicked element, this function finds the distance from the root
        and provides a list of the sub-root indices
        @param elm: Clicked element
        @return: Node depth, list of parent indices
        """
        depth = 0
        indices = [elm.row()]
        while elm.row() > -1:
            elm = elm.parent()
            indices.append(elm.row())
            depth += 1

        return depth, indices

    def display_profile(self, profile_type):
        """
        Show the profile in the GUI table
        @param profile_type:
        @return:
        """
        if self.circuit.time_series.time is not None:
            if profile_type == ProfileTypes.Loads:
                dta = self.circuit.time_series.load_profiles
                label = self.circuit.bus_names
            elif profile_type == ProfileTypes.Generators:
                dta = self.circuit.time_series.gen_profiles
                label = self.circuit.gen_names
            else:
                return

            df = pd.DataFrame(data=dta, columns=label, index=self.circuit.time_series.time)
            model = PandasModel(df)
            self.ui.tableView.setModel(model)

    def clean_GUI(self):
        """
        Initializes the comboboxes and tables
        Returns:

        """
        self.ui.tableView.setModel(None)
        # if self.results_tree_model is not None:
        #     # self.results_tree_model.clear()
        #     del self.results_tree_model

        self.ui.pf_results_treeView.setModel(None)
        self.ui.sta_results_treeView.setModel(None)
        self.ui.ts_results_treeView.setModel(None)
        self.ui.sto_results_treeView.setModel(None)

        self.ui.profile_time_selection_comboBox.clear()
        self.ui.results_time_selection_comboBox.clear()
        self.ui.gridPlot.clear()

    def get_selected_power_flow_options(self):
        """
        Gather power flow run options
        :return:
        """
        solver_type = self.solvers_dict[self.ui.solver_comboBox.currentText()]

        enforce_Q_limits = self.ui.control_Q_checkBox.isChecked()

        check_freq_blackout = self.ui.freq_assesment_check.isChecked()

        exponent = self.ui.tolerance_spinBox.value()
        tolerance = 1.0 / (10.0**exponent)

        max_iter = self.ui.max_iterations_spinBox.value()

        set_last_solution = self.ui.remember_last_solution_checkBox.isChecked()

        if self.ui.helm_retry_checkBox.isChecked():
            solver_to_retry_with = self.solvers_dict[self.ui.retry_solver_comboBox.currentText()]
        else:
            solver_to_retry_with = None

        return solver_type, check_freq_blackout, tolerance, max_iter, set_last_solution, solver_to_retry_with, enforce_Q_limits

    def run_power_flow(self):
        """
        Run a power flow simulation
        :return:
        """

        if self.circuit.circuit_graph is not None:

            # reload current circuit values in new power flow instance
            self.circuit.initialize_power_flow_solver()

            if self.circuit.power_flow is not None:
                self.LOCK()

                # initialize the solvers to  capture the possible grid changes
                self.circuit.initialize_power_flow_solver()

                # get circuit and solver conditions
                solver_type, check_freq_blackout, tolerance, \
                max_iter, set_last_solution, solver_to_retry_with, \
                enforce_Q_limits = self.get_selected_power_flow_options()

                # check the auto precision
                if self.ui.auto_precision_checkBox.isChecked():
                    active_generators = find(self.circuit.gen[:, GEN_STATUS] > 0)  # which generators are on?
                    active_generators_buses = self.circuit.gen[active_generators, GEN_BUS].astype(int)
                    ngon = active_generators.shape[0]
                    nb = len(self.circuit.bus)
                    Cg = sparse((ones(ngon), (active_generators_buses, range(ngon))), (nb, ngon))
                    Sbus = (Cg * (self.circuit.gen[active_generators, PG] + 1j * self.circuit.gen[active_generators, QG]) - (self.circuit.bus[:, PD] + 1j * self.circuit.bus[:, QD])) / self.circuit.baseMVA

                    mn = min(abs(Sbus[Sbus != 0]))
                    order = int(-np.log10(mn))+3
                    tolerance = 1.0 * 10.0**(-order)
                    self.ui.tolerance_spinBox.setValue(order)

                print('Solver: ', solver_to_retry_with)
                # threading connections
                self.connect(self.circuit.power_flow, SIGNAL("progress(float)"), self.ui.progressBar.setValue)
                self.connect(self.circuit.power_flow, SIGNAL("done()"), self.UNLOCK)
                self.connect(self.circuit.power_flow, SIGNAL("done()"), self.post_power_flow)

                # solve
                #
                self.circuit.power_flow.set_run_options(solver_type=solver_type, tol=tolerance, max_it=max_iter,
                                                        enforce_reactive_power_limits=enforce_Q_limits, isMaster=True,
                                                        set_last_solution=set_last_solution,
                                                        solver_to_retry_with=solver_to_retry_with)
                self.circuit.power_flow.start()

    def post_power_flow(self):
        """
        Actions to perform after the power flow.
        This cannot be in the power flow routine since it executes the power flow asynchronously
        Returns:

        """
        # update the results in the circuit structures
        self.circuit.update_power_flow_results()

        # Plot
        self.display_graph_by_results()
        self.display_objects_table()

        # set results tree view
        bus_results = ['Voltage (p.u.)', 'Voltage (kV)', 'Active power (MW)', 'Reactive power (MVar)',
                       'Active and reactive power (MW, MVar)', 'Apparent power (MVA)']
        branch_results = ['Loading (%)', 'Current (p.u.)', 'Current (kA)', 'Losses (MVA)']
        gen_results = ['Reactive power (p.u.)', 'Reactive power (MVar)']

        self.set_pf_results_treeview_structure(self.ui.pf_results_treeView, bus_results, branch_results, gen_results)

        self.ipyConsole.pushVariables({'powerflow': self.circuit.power_flow})

    def handle_pf_tree_results(self, index):
        """
        Handle the power flow results tree view selection
        @param index:
        @return:
        """
        depth, indices = self.get_tree_depth(index)

        if len(indices) != 4:
            return

        '''
        Buses:
            Bus:
                'Voltage (p.u.)',
                'Voltage (kV)',
                'Active power (MW)',
                'Reactive power (MVar)',
                'Active and reactive power (MW, MVar)',
                'Apparent power (MVA)'

        Branches:
            Branch:
                'Loading (%)',
                'Current (p.u.)',
                'Current (kA)',
                'Losses (MVA)'

        Generators:
            Gen:
                'Reactive power (p.u.)',
                'Reactive power (MVar)'
        '''

        result = indices[0]
        element = indices[1] - 1  # bus, brach or gen index (if -1, then is all)
        category = indices[2]  # Bus, Branch, Gen
        t = self.ui.results_time_selection_comboBox.currentIndex()
        if t == -1:
            t = None
        print('PF Depth: ', depth, indices)

        if category == 0:  # Buses

            if element == -1:
                print('All')

                if result == 0:  # Voltage (p.u.)
                    self.plot_results(ResultTypes.bus_voltage_per_unit, t=t)
                elif result == 1:  # Voltage (kV)
                    self.plot_results(ResultTypes.bus_voltage, t=t)
                elif result == 2:  # Active power (MW)
                    self.plot_results(ResultTypes.bus_active_power, t=t)
                elif result == 3:  # Reactive power (MVar)
                    self.plot_results(ResultTypes.bus_reactive_power, t=t)
                elif result == 4:  # Active and reactive power (MW, MVar)
                    self.plot_results(ResultTypes.bus_active_and_reactive_power, t=t)
                elif result == 5:  # Apparent power (MVA)
                    self.plot_results(ResultTypes.bus_apparent_power, t=t)
            else:
                print('Other')
                if result == 0:  # Voltage (p.u.)
                    self.plot_results(ResultTypes.bus_voltage_per_unit, element, t=t)
                elif result == 1:  # Voltage (kV)
                    self.plot_results(ResultTypes.bus_voltage, element, t=t)
                elif result == 2:  # Active power (MW)
                    self.plot_results(ResultTypes.bus_active_power, element, t=t)
                elif result == 3:  # Reactive power (MVar)
                    self.plot_results(ResultTypes.bus_reactive_power, element, t=t)
                elif result == 4:  # Active and reactive power (MW, MVar)
                    self.plot_results(ResultTypes.bus_active_and_reactive_power, element, t=t)
                elif result == 5:  # Apparent power (MVA)
                    self.plot_results(ResultTypes.bus_apparent_power, element, t=t)

        elif category == 1:  # Branches

            if element == -1:
                print('All')

                if result == 0:  # Loading (%)
                    self.plot_results(ResultTypes.branches_loading, t=t)
                elif result == 1:  # Current (p.u.)
                    self.plot_results(ResultTypes.branch_current_per_unit, t=t)
                elif result == 2:  # Current (kA)
                    self.plot_results(ResultTypes.branch_current, t=t)
                elif result == 3:  # Losses (MVA)
                    self.plot_results(ResultTypes.branch_losses, t=t)
            else:
                print('Other')

                if result == 0:  # Loading (%)
                    self.plot_results(ResultTypes.branches_loading, element, t=t)
                elif result == 1:  # Current (p.u.)
                    self.plot_results(ResultTypes.branch_current_per_unit, element, t=t)
                elif result == 2:  # Current (kA)
                    self.plot_results(ResultTypes.branch_current, element, t=t)
                elif result == 3:  # Losses (MVA)
                    self.plot_results(ResultTypes.branch_losses, element, t=t)

        elif category == 2:  # Generators

            if element == -1:
                print('All')

                if result == 0:  # Reactive power (p.u.)
                    self.plot_results(ResultTypes.gen_reactive_power_pu, t=t)
                elif result == 1:  # Reactive power (MVar)
                    self.plot_results(ResultTypes.gen_reactive_power, t=t)
            else:
                print('Other')

                if result == 0:  # Reactive power (p.u.)
                    self.plot_results(ResultTypes.gen_reactive_power_pu, element, t=t)
                elif result == 1:  # Reactive power (MVar)
                    self.plot_results(ResultTypes.gen_reactive_power, element, t=t)

    def run_voltage_stability(self):
        """
        Run a voltage stability simulation
        @return:
        """
        if self.circuit.circuit_graph is not None:
            # reload current circuit values in new power flow instance
            self.circuit.initialize_power_flow_solver()

            self.LOCK()

            # initialize the solvers to  capture the possible grid changes
            self.circuit.initialize_power_flow_solver()

            # get circuit and solver conditions
            solver_type, check_freq_blackout, tolerance, \
            max_iter, set_last_solution, solver_to_retry_with, \
            enforce_Q_limits = self.get_selected_power_flow_options()
            print('Solver: ', solver_to_retry_with)
            # threading connections
            self.connect(self.circuit.voltage_stability, SIGNAL("progress(float)"), self.ui.progressBar.setValue)
            self.connect(self.circuit.voltage_stability, SIGNAL("done()"), self.post_voltage_stability)

            # solve
            self.circuit.voltage_stability.set_run_options(solver_type=solver_type, tol=tolerance, max_it=max_iter,
                                                           enforce_reactive_power_limits=enforce_Q_limits, isMaster=True,
                                                           set_last_solution=set_last_solution,
                                                           solver_to_retry_with=solver_to_retry_with)

            self.circuit.voltage_stability.start()

    def post_voltage_stability(self):
        """
        Actions to run after a voltage stability simulation
        @return:
        """
        self.UNLOCK()

        # set results tree view
        bus_results = ['S-V curve', 'Q-V curve']
        branch_results = []
        gen_results = []
        self.set_pf_results_treeview_structure(self.ui.sta_results_treeView, bus_results, branch_results, gen_results)

        self.ipyConsole.pushVariables({'voltagestability': self.circuit.voltage_stability})

    def handle_sta_tree_results(self, index):
        """
        Handle the voltage stablity results tree view selection
        @param index:
        @return:
        """
        depth, indices = self.get_tree_depth(index)

        if len(indices) != 4:
            return

        '''
        Buses:
            Bus:
                'S-V curve',
                'Q-V curve'
        '''

        result = indices[0]
        element = indices[1] - 1  # bus, brach or gen index (if -1, then is all)
        category = indices[2]  # Bus, Branch, Gen

        print('PF Depth: ', depth, indices)

        if category == 0:  # Buses

            if element == -1:
                print('All')

                if result == 0:  # S-V curve
                    self.plot_results(ResultTypes.bus_s_v_curve, series=True)
                elif result == 1:  # Q-V curve
                    self.plot_results(ResultTypes.bus_QV_curve, series=True)

            else:
                print('Other')
                if result == 0:  # S-V curve
                    self.plot_results(ResultTypes.bus_s_v_curve, element)
                elif result == 1:  # Q-V curve
                    self.plot_results(ResultTypes.bus_QV_curve, element)

    def run_time_series(self):
        """
        Run the time series simulation
        @return:
        """
        if self.circuit.time_series is not None:
            if self.circuit.time_series.is_ready():
                self.LOCK()

                # initialize the solvers to  capture the possible grid changes
                self.circuit.initialize_TimeSeries()
                
                solver_type, check_freq_blackout, tolerance, max_iter, \
                set_last_solution, solver_to_retry_with, enforce_Q_limits = self.get_selected_power_flow_options()

                # set the time series power flow object the desired solver
                self.circuit.time_series.pf.solver_type = solver_type

                # set the solver to use in case of non convergence of the main solver
                self.circuit.time_series.pf.solver_to_retry_with = solver_to_retry_with

                # Set the time series run options
                self.connect(self.circuit.time_series, SIGNAL("progress(float)"), self.ui.progressBar.setValue)
                self.connect(self.circuit.time_series, SIGNAL("done()"), self.post_time_series)

                # execute
                self.circuit.time_series.set_run_options(auto_repeat=True, tol=tolerance, max_it=max_iter,
                                                         enforce_reactive_power_limits=enforce_Q_limits)
                self.circuit.time_series.start()  # the class is a Qthread

            else:
                msg = "The time series is not initialized"
                q = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 'GridCal',  msg)
                q.setStandardButtons(QtGui.QMessageBox.Ok)
                i = QtGui.QIcon()
                i.addPixmap(QtGui.QPixmap("..."), QtGui.QIcon.Normal)
                q.setWindowIcon(i)
                q.exec_()

    def post_time_series(self):
        """
        Actions to run when the time series are over
        @return:
        """
        self.UNLOCK()

        # set results tree view
        bus_results = ['Voltage (p.u.)', 'Voltage (kV)', 'Active power (MW)', 'Reactive power (MVar)',
                       'Active and reactive power (MW, MVar)', 'Apparent power (MVA)']
        branch_results = ['Loading (%)', 'Current (p.u.)', 'Current (kA)', 'Losses (MVA)']
        gen_results = ['Reactive power (p.u.)', 'Reactive power (MVar)']

        self.set_pf_results_treeview_structure(self.ui.ts_results_treeView, bus_results, branch_results, gen_results)

        self.ipyConsole.pushVariables({'timeseries': self.circuit.time_series})

    def handle_ts_tree_results(self, index):
        """
        Handle the time series results tree view selection
        @param index:
        @return:
        """
        depth, indices = self.get_tree_depth(index)

        if len(indices) != 4:
            return

        '''
        Buses:
            Bus:
                'Voltage (p.u.)',
                'Voltage (kV)',
                'Active power (MW)',
                'Reactive power (MVar)',
                'Active and reactive power (MW, MVar)',
                'Apparent power (MVA)'

        Branches:
            Branch:
                'Loading (%)',
                'Current (p.u.)',
                'Current (kA)',
                'Losses (MVA)'

        Generators:
            Gen:
                'Reactive power (p.u.)',
                'Reactive power (MVar)'
        '''

        result = indices[0]
        element = indices[1] - 1  # bus, brach or gen index (if -1, then is all)
        category = indices[2]  # Bus, Branch, Gen
        t = self.ui.results_time_selection_comboBox.currentIndex()
        boxplot = self.ui.box_whiskers_ts_checkBox.isChecked()
        if t == -1:
            t = None
        print('PF Depth: ', depth, indices)

        if category == 0:  # Buses

            if element == -1:
                print('All')

                if result == 0:  # Voltage (p.u.)
                    self.plot_results(ResultTypes.bus_voltage_per_unit, series=True, useboxplot=boxplot)
                elif result == 1:  # Voltage (kV)
                    self.plot_results(ResultTypes.bus_voltage, series=True, useboxplot=boxplot)
                elif result == 2:  # Active power (MW)
                    self.plot_results(ResultTypes.bus_active_power, series=True, useboxplot=boxplot)
                elif result == 3:  # Reactive power (MVar)
                    self.plot_results(ResultTypes.bus_reactive_power, series=True, useboxplot=boxplot)
                elif result == 4:  # Active and reactive power (MW, MVar)
                    self.plot_results(ResultTypes.bus_active_and_reactive_power, series=True, useboxplot=boxplot)
                elif result == 5:  # Apparent power (MVA)
                    self.plot_results(ResultTypes.bus_apparent_power, series=True, useboxplot=boxplot)
            else:
                print('Other')
                if result == 0:  # Voltage (p.u.)
                    self.plot_results(ResultTypes.bus_voltage_per_unit, element, series=True, useboxplot=boxplot)
                elif result == 1:  # Voltage (kV)
                    self.plot_results(ResultTypes.bus_voltage, element, series=True, useboxplot=boxplot)
                elif result == 2:  # Active power (MW)
                    self.plot_results(ResultTypes.bus_active_power, element, series=True, useboxplot=boxplot)
                elif result == 3:  # Reactive power (MVar)
                    self.plot_results(ResultTypes.bus_reactive_power, element, series=True, useboxplot=boxplot)
                elif result == 4:  # Active and reactive power (MW, MVar)
                    self.plot_results(ResultTypes.bus_active_and_reactive_power, element, series=True,
                                      useboxplot=boxplot)
                elif result == 5:  # Apparent power (MVA)
                    self.plot_results(ResultTypes.bus_apparent_power, element, series=True, useboxplot=boxplot)

        elif category == 1:  # Branches

            if element == -1:
                print('All')

                if result == 0:  # Loading (%)
                    self.plot_results(ResultTypes.branches_loading, series=True, useboxplot=boxplot)
                elif result == 1:  # Current (p.u.)
                    self.plot_results(ResultTypes.branch_current_per_unit, series=True, useboxplot=boxplot)
                elif result == 2:  # Current (kA)
                    self.plot_results(ResultTypes.branch_current, series=True, useboxplot=boxplot)
                elif result == 3:  # Losses (MVA)
                    self.plot_results(ResultTypes.branch_losses, series=True, useboxplot=boxplot)
            else:
                print('Other')

                if result == 0:  # Loading (%)
                    self.plot_results(ResultTypes.branches_loading, element, series=True, useboxplot=boxplot)
                elif result == 1:  # Current (p.u.)
                    self.plot_results(ResultTypes.branch_current_per_unit, element, series=True, useboxplot=boxplot)
                elif result == 2:  # Current (kA)
                    self.plot_results(ResultTypes.branch_current, element, series=True, useboxplot=boxplot)
                elif result == 3:  # Losses (MVA)
                    self.plot_results(ResultTypes.branch_losses, element, series=True, useboxplot=boxplot)

        elif category == 2:  # Generators

            if element == -1:
                print('All')

                if result == 0:  # Reactive power (p.u.)
                    self.plot_results(ResultTypes.gen_reactive_power_pu, series=True, useboxplot=boxplot)
                elif result == 1:  # Reactive power (MVar)
                    self.plot_results(ResultTypes.gen_reactive_power, series=True, useboxplot=boxplot)
            else:
                print('Other')

                if result == 0:  # Reactive power (p.u.)
                    self.plot_results(ResultTypes.gen_reactive_power_pu, element, series=True, useboxplot=boxplot)
                elif result == 1:  # Reactive power (MVar)
                    self.plot_results(ResultTypes.gen_reactive_power, element, series=True, useboxplot=boxplot)

    def run_stochastic(self):
        """
        Run stochastic power flow
        @return:
        """

        if self.circuit.time_series is not None:
            if self.circuit.time_series.is_ready():
                self.LOCK()

                # Initialize the Monte Carlo module
                self.init_statistical_characterization()

                # Get Power flow settings
                solver_type, check_freq_blackout, tolerance, max_iter, \
                set_last_solution, solver_to_retry_with, enforce_Q_limits = self.get_selected_power_flow_options()

                if self.ui.montecarlo_radioButton.isChecked():
                    # set the time series power flow object the desired solver
                    self.circuit.monte_carlo.time_series.pf.solver_type = solver_type

                    # set the solver to use in case of non convergence of the main solver
                    self.circuit.monte_carlo.time_series.pf.solver_to_retry_with = solver_to_retry_with

                    # Set the time series run options
                    self.connect(self.circuit.monte_carlo, SIGNAL("progress(float)"), self.ui.progressBar.setValue)
                    self.connect(self.circuit.monte_carlo, SIGNAL("done()"), self.post_stochastic_run)

                    # execute
                    max_it = self.ui.max_iterations_stochastic_spinBox.value()
                    exponent = self.ui.tolerance_stochastic_spinBox.value()
                    tol = 1.0 / (10.0 ** exponent)
                    self.circuit.monte_carlo.set_run_options(tol=tol, max_it=max_it,
                                                             tol_pf=tolerance, max_it_pf=max_iter,
                                                             enforce_reactive_power_limits=enforce_Q_limits)
                    self.circuit.monte_carlo.start()  # the class is a Qthread

                elif self.ui.stochastic_collocation_radioButton.isChecked():

                    self.LOCK()

                    # set the time series power flow object the desired solver
                    self.circuit.stochastic_collocation.time_series.pf.solver_type = solver_type

                    # set the solver to use in case of non convergence of the main solver
                    self.circuit.stochastic_collocation.time_series.pf.solver_to_retry_with = solver_to_retry_with

                    # Set the time series run options
                    self.connect(self.circuit.stochastic_collocation, SIGNAL("progress(float)"), self.ui.progressBar.setValue)
                    self.connect(self.circuit.stochastic_collocation, SIGNAL("done()"), self.post_stochastic_run)

                    # use the precision spinboc level to set the level of precision
                    self.circuit.stochastic_collocation.level = self.ui.max_iterations_stochastic_spinBox.value()

                    # run
                    self.circuit.stochastic_collocation.start()

            else:
                msg = "The time series is not initialized"
                q = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 'GridCal', msg)
                q.setStandardButtons(QtGui.QMessageBox.Ok)
                i = QtGui.QIcon()
                i.addPixmap(QtGui.QPixmap("..."), QtGui.QIcon.Normal)
                q.setWindowIcon(i)
                q.exec_()

    def post_stochastic_run(self):
        """
        Actions to perform after the stochastic run
        @return:
        """
        self.UNLOCK()
        if self.ui.montecarlo_radioButton.isChecked():
            self.circuit.monte_carlo.plot_convergence()

        # set results tree view
        bus_results = ['Voltage (p.u.)', 'Voltage standard deviation(p.u)']
        branch_results = ['Loading (%)', 'Losses (MVA)']
        gen_results = []

        self.set_pf_results_treeview_structure(self.ui.sto_results_treeView, bus_results, branch_results, gen_results)

        if self.ui.montecarlo_radioButton.isChecked():
            self.ipyConsole.pushVariables({'stochastic': self.circuit.monte_carlo})
        else:
            self.ipyConsole.pushVariables({'stochflow': self.circuit.stochastic_collocation})

    def handle_sto_tree_results(self, index):
        """
        Handle the stochastic power flow results tree view selection
        @param index:
        @return:
        """
        depth, indices = self.get_tree_depth(index)

        if len(indices) != 4:
            return

        '''
        Buses:
            Bus:
                'Voltage (p.u.)',
                'Voltage standard deviation(p.u)'

        Branches:
            Branch:
                'Loading (%)'
                'Losses (MVA)'
        '''

        result = indices[0]
        element = indices[1] - 1  # bus, brach or gen index (if -1, then is all)
        category = indices[2]  # Bus, Branch, Gen
        t = self.ui.results_time_selection_comboBox.currentIndex()
        boxplot = self.ui.box_whiskers_ts_checkBox.isChecked()
        if t == -1:
            t = None
        print('PF Depth: ', depth, indices)

        if category == 0:  # Buses

            if element == -1:
                print('All')

                if result == 0:  # Voltage (p.u.)
                    self.plot_results(ResultTypes.bus_voltage_per_unit, series=True, useboxplot=boxplot)
                elif result == 1:  # Voltage standard deviation(p.u)
                    self.plot_results(ResultTypes.bus_voltage, series=True, useboxplot=boxplot)

            else:
                print('Other')
                if result == 0:  # Voltage (p.u.)
                    self.plot_results(ResultTypes.bus_voltage_per_unit, element, series=True, useboxplot=boxplot)
                elif result == 1:  # Voltage standard deviation(p.u)
                    self.plot_results(ResultTypes.bus_voltage, element, series=True, useboxplot=boxplot)

        elif category == 1:  # Branches

            if element == -1:
                print('All')

                if result == 0:  # Loading (%)
                    self.plot_results(ResultTypes.branches_loading, series=True, useboxplot=boxplot)
                elif result == 1:  # Losses (MVA)
                    self.plot_results(ResultTypes.branch_current_per_unit, series=True, useboxplot=boxplot)

            else:
                print('Other')

                if result == 0:  # Loading (%)
                    self.plot_results(ResultTypes.branches_loading, element, series=True, useboxplot=boxplot)
                elif result == 1:  # Losses (MVA)
                    self.plot_results(ResultTypes.branch_current_per_unit, element, series=True, useboxplot=boxplot)

    def actionBlackout_click(self):
        print("actionBlackout_click")

    def handle_tree_stc_selection(self, index):
        """
        Handles the statistical characterization tree view selection
        """
        # indexItem = self.results_tree_model.index(index.row(), 0, index.parent()).copy()
        idx = index.row()
        print(idx)
        # ax = self.ui.statisticalGridPlot.canvas.ax
        self.ui.statisticalGridPlot.clear()
        self.circuit.monte_carlo.plot_stc(idx, self.ui.statisticalGridPlot.canvas.ax)
        self.ui.statisticalGridPlot.redraw()

    def init_statistical_characterization(self):
        """
        Initializes the MonteCarlo instance and displays the statistical characterization of the profiles
        @return:
        """
        idx = self.ui.group_by_comboBox.currentIndex()

        if idx == 0:
            mode = TimeGroups.NoGroup
        elif idx == 1:
            mode = TimeGroups.ByDay
        elif idx == 2:
            mode = TimeGroups.ByHour

        self.circuit.initialize_MonteCarlo(mode)
        self.set_statistical_characterization_treeview()

    ####################################################################################################################
    # Display results functions
    ####################################################################################################################

    def display_objects_table(self):
        """

        :return:
        """
        # print("dataStructuresListView_click")
        idx = self.ui.dataStructuresListView.selectedIndexes()[0].row()
        df = None
        if idx == 0:
            df = pd.DataFrame(data=self.circuit.bus, columns=bus_headers, index=self.circuit.bus_names)

        elif idx == 1:
            df = pd.DataFrame(data=self.circuit.gen, columns=gen_headers, index=self.circuit.gen_names)

        elif idx == 2:
            df = pd.DataFrame(data=self.circuit.branch, columns=branch_headers, index=self.circuit.branch_names)

        elif idx == 3:  # Ybus
            pf = CircuitPowerFlow(self.circuit.baseMVA, self.circuit.bus, self.circuit.branch, self.circuit.gen, initialize_solvers=False)
            df = pd.DataFrame(data=pf.Ybus.todense(), columns=self.circuit.bus_names, index=self.circuit.bus_names)

            # plot the admittance matrix
            self.ui.resultsPlot.clear()
            self.ui.resultsPlot.canvas.ax.spy(pf.Ybus, precision=1e-3, marker='.', markersize=5)
            self.ui.resultsPlot.redraw()

        elif idx == 4:  # Sbus
            pf = CircuitPowerFlow(self.circuit.baseMVA, self.circuit.bus, self.circuit.branch, self.circuit.gen, initialize_solvers=False)
            df = pd.DataFrame(data=pf.Sbus, index=self.circuit.bus_names)

        if df is not None:
            model = PandasModel(df)
            self.ui.dataStructureTableView.setModel(model)

        self.selected_node_idx = None

    def display_profiles_table(self, profile_type):
        """
        Show the selected profile
        Args:
            profile_type:

        Returns:

        """
        if self.circuit.time_series is not None:
            if self.circuit.time_series.is_ready():
                if profile_type == ProfileTypes.Loads:
                    label = self.circuit.bus_names
                    df = self.circuit.time_series.get_loads_dataframe(label)
                    self.ui.tableView.setModel(PandasModel(df))

                elif profile_type == ProfileTypes.Generators:
                    label = self.circuit.gen_names
                    df = self.circuit.time_series.get_gen_dataframe(label)
                    self.ui.tableView.setModel(PandasModel(df))

    def dataStructureTableView_click(self):
        """

        :return:
        """
        if len(self.ui.dataStructureTableView.selectedIndexes()) > 0:
            idx = self.ui.dataStructureTableView.selectedIndexes()[0].row()
            # col = self.ui.dataStructureTableView.selectedIndexes()[0].column()
            self.selected_node_idx = idx
            print("idx: " + str(self.selected_node_idx))

    def dataStructureTableView_doubleClick(self):
        """

        :return:
        """
        if len(self.ui.dataStructureTableView.selectedIndexes()) > 0:
            idx = self.ui.dataStructureTableView.selectedIndexes()[0].row()
            col = self.ui.dataStructureTableView.selectedIndexes()[0].column()

            print("dataStructureTableView_click: " + str(idx) + "," + str(col))

    def display_branch_magnitude(self, ax, fig, y, ylabel, xlabel=''):
        """

        :param ax:
        :param fig:
        :param y:
        :param ylabel:
        :param xlabel:
        :return:
        """
        width = 0.5
        nx = len(self.circuit.branch)
        x = np.array(list(range(nx)))
        labels = self.circuit.branch_names

        df_data = y
        ax.bar(x, df_data, width=width, color='b', align='center')
        ax.plot(x, ones(nx) * 100, color='r')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation='vertical')
        ax.set_xlim([0-width, len(x)])

        # plot
        ax.set_aspect('auto')
        ax.axes.set_ylabel(ylabel)
        ax.axes.set_xlabel(xlabel)

        fig.tight_layout()

        self.ui.resultsPlot.redraw()

        df = pd.DataFrame(data=[df_data], columns=labels)
        self.ui.resultsTableView.setModel(PandasModel(df))

    def display_bus_magnitude(self, ax, fig, y, ylabel, xlabel='', bar=False):
        """

        :param ax:
        :param fig:
        :param y:
        :param ylabel:
        :param xlabel:
        :return:
        """
        x = self.circuit.bus[:, BUS_I].astype(int)
        labels = self.circuit.bus_names
        dims = np.ndim(y)
        print('dims:', dims)
        if dims == 2:
            r, c = np.shape(y)
            if c == 2:
                df_data = y
                df = pd.DataFrame(data=df_data, columns=ylabel)
                df.plot(ax=ax, kind='bar')
            elif c == 3:
                df_data = y[:, 0]
                df = pd.DataFrame(data=[df_data], columns=labels)
                ax.plot(x, y[:, 0], color='k', marker='o')
                ax.plot(x, y[:, 1], color='r')
                ax.plot(x, y[:, 2], color='r')
                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation='vertical')
        else:
            df_data = y

            if not bar:
                df = pd.DataFrame(data=[df_data], columns=labels, index=x)
                ax.plot(x, y, color='k', marker='o')
                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation='vertical')
            else:
                df = pd.DataFrame(data=df_data.transpose(), columns=[ylabel], index=labels)
                df.plot(ax=ax, kind='bar')
                # ax.redraw()

        # plot
        ax.set_aspect('auto')
        ax.axes.set_ylabel(ylabel)
        ax.axes.set_xlabel(xlabel)
        fig.tight_layout()
        self.ui.resultsPlot.redraw()

        self.ui.resultsTableView.setModel(PandasModel(df))

    def display_series_bus_magnitude(self, ax, fig, x, y, ylabel, xlabel='', y2=None, ylabel2=None, y_limits=None,
                                     boxplot=False, elm_idx=None):
        """

        :param ax:
        :param fig:
        :param y:
        :param ylabel:
        :param xlabel:
        :return:
        """
        labels = self.circuit.bus_names
        if elm_idx is not None:
            labels = [labels[elm_idx]]

        # plot limits
        if y_limits is not None:
            ax.plot(x, y_limits[:, 0], color='r')
            ax.plot(x, y_limits[:, 1], color='r')

        # Display data
        df = pd.DataFrame(data=y, columns=labels, index=x)
        self.ui.resultsTableView.setModel(PandasModel(df))

        # plot
        if boxplot:
            df.boxplot(ax=ax, return_type='axes')
            ax.set_xticklabels(labels, rotation='vertical')
        else:
            try:
                df.plot(yerr=y2, ax=ax)
            except:
                print("Update the version of pandas")
            # print('Mismatches:\n', y2)
        ax.set_aspect('auto')
        ax.axes.set_ylabel(ylabel)
        ax.axes.set_xlabel(xlabel)

        # add mismatch on the secondary axis
        # if y2 is not None:
        #     ax2 = ax.twinx()
        #     ax2.plot(y2, 'r.')
        #     if ylabel2 is not None:
        #         ax2.set_ylabel(ylabel2)

        fig.tight_layout()
        self.ui.resultsPlot.redraw()

    def display_series_branch_magnitude(self, ax, fig, x, y, ylabel, xlabel='', y2=None, ylabel2=None, y_limits=None,
                                        boxplot=False, elm_idx=None):
        """

        :param ax:
        :param fig:
        :param y:
        :param ylabel:
        :param xlabel:
        :return:
        """
        labels = self.circuit.branch_names
        if elm_idx is not None:
            labels = [labels[elm_idx]]

        # plot limits
        if y_limits is not None:
            ax.plot(x, y_limits[:, 0], color='r')
            ax.plot(x, y_limits[:, 1], color='r')

        # Display data
        df = pd.DataFrame(data=y, columns=labels, index=x)
        self.ui.resultsTableView.setModel(PandasModel(df))

        # plot
        if boxplot:
            df.boxplot(ax=ax, return_type='axes')
            ax.set_xticklabels(labels, rotation='vertical')
        else:
            try:
                df.plot(yerr=y2, ax=ax)
            except:
                print("Update the version of pandas")
        ax.set_aspect('auto')
        ax.axes.set_ylabel(ylabel)
        ax.axes.set_xlabel(xlabel)

        # add mismatch on the secondary axis
        # if y2 is not None:
        #     ax2 = ax.twinx()
        #     ax2.plot(y2, 'r.')
        #     if ylabel2 is not None:
        #         ax2.set_ylabel(ylabel2)

        fig.tight_layout()
        self.ui.resultsPlot.redraw()

    def display_QV_curve(self, ax, Q, V, xlabel):
        nser = len(Q)
        # if nser > 1:
        for i in range(nser):
            ax.plot(Q[i], V[i])
        # else:
        #     ax.plot(Q, V)
        df = pd.DataFrame(data=np.vstack((Q, V)).transpose(), columns=['Q', 'V'])

        ax.set_aspect('auto')
        ax.axes.set_ylabel('V')
        ax.axes.set_xlabel(xlabel)
        self.ui.resultsPlot.redraw()
        self.ui.resultsTableView.setModel(PandasModel(df))

    def plot_results(self, type_of_result,  element_idx=None, series=0, useboxplot=0, t=None):
        """
        Plots the results stored according to the passed type
        @param type_of_result: variable determining the type of results to plot
        @return: Nothing
        """
        # print(type_of_result)

        if self.circuit.circuit_graph is not None:

            self.ui.resultsPlot.clear(force=True)
            ax = self.ui.resultsPlot.canvas.ax
            fig = self.ui.resultsPlot.canvas.fig

            # pick the selected time
            use_result_at_t = (t is not None)

            if not series:

                if type_of_result == ResultTypes.branch_losses:
                    if use_result_at_t:
                        y = abs(self.circuit.time_series.losses[t, :])
                    else:
                        y = self.circuit.branch[:, LOSSES]
                    ylabel = "Branch losses (MVA)"
                    self.display_branch_magnitude(ax, fig, y, ylabel)

                elif type_of_result == ResultTypes.branches_loading:
                    if use_result_at_t:
                        y = abs(self.circuit.time_series.loadings[t, :])
                    else:
                        y = self.circuit.branch[:, LOADING]
                    ylabel = "Branch loading (%)"
                    self.display_branch_magnitude(ax, fig, y * 100, ylabel)

                elif type_of_result == ResultTypes.branch_current:
                    if use_result_at_t:
                        y = abs(self.circuit.time_series.currents[t, :])
                    else:
                        y = self.circuit.branch[:, BR_CURRENT]
                    ylabel = "Branch Currents (kA)"
                    self.display_branch_magnitude(ax, fig, y, ylabel)

                elif type_of_result == ResultTypes.bus_voltage_per_unit:
                    if use_result_at_t:
                        nb = len(self.circuit.bus)
                        y = zeros((nb, 3))
                        y[:, 0] = abs(self.circuit.time_series.voltages[t, :])
                        y[:, [1, 2]] = self.circuit.bus[:, [VMIN, VMAX]]
                    else:
                        y = self.circuit.bus[:, [VM, VMIN, VMAX]]

                    ylabel = "Bus Voltages (p.u.)"
                    self.display_bus_magnitude(ax, fig, y, ylabel)

                elif type_of_result == ResultTypes.bus_voltage:
                    if use_result_at_t:
                        nb = len(self.circuit.bus)
                        y = zeros((nb, 3))
                        y[:, 0] = abs(self.circuit.time_series.voltages[t, :]).copy()
                        y[:, [1, 2]] = self.circuit.bus[:, [VMIN, VMAX]].copy()
                    else:
                        y = self.circuit.bus[:, [VM, VMIN, VMAX]].copy()
                    y[:, 0] *= self.circuit.bus[:, BASE_KV]
                    y[:, 1] *= self.circuit.bus[:, BASE_KV]
                    y[:, 2] *= self.circuit.bus[:, BASE_KV]
                    ylabel = "Bus Voltages (kV)"
                    self.display_bus_magnitude(ax, fig, y, ylabel)

                elif type_of_result == ResultTypes.bus_active_power:
                    if use_result_at_t:
                        y = self.circuit.time_series.load_profiles[t, :].real
                    else:
                        y = self.circuit.bus[:, PD]

                    ylabel = "Bus Active power (MW)"
                    self.display_bus_magnitude(ax, fig, y, ylabel, bar=True)

                elif type_of_result == ResultTypes.bus_reactive_power:
                    if use_result_at_t:
                        y = self.circuit.time_series.load_profiles[t, :].imag
                    else:
                        y = self.circuit.bus[:, QD]

                    ylabel = "Bus reactive power (MVar)"
                    self.display_bus_magnitude(ax, fig, y, ylabel, bar=True)

                elif type_of_result == ResultTypes.bus_apparent_power:
                    if use_result_at_t:
                        y = abs(self.circuit.time_series.load_profiles[t, :])
                    else:
                        y = abs(self.circuit.bus[:, PD] + 1j * self.circuit.bus[:, QD])

                    ylabel = "Bus apparent power (MVA)"
                    self.display_bus_magnitude(ax, fig, y, ylabel, bar=True)

                elif type_of_result == ResultTypes.bus_active_and_reactive_power:
                    if use_result_at_t:
                        y = np.vstack((self.circuit.time_series.load_profiles[t, :].real, self.circuit.time_series.load_profiles[t, :].imag))
                    else:
                        y = np.vstack((self.circuit.bus[:, PD], self.circuit.bus[:, QD]))

                    ylabel = ["Active power (MW)", "Reactive power (MVar)"]
                    self.display_bus_magnitude(ax, fig, y.transpose(), ylabel, bar=False)

                elif type_of_result == ResultTypes.bus_QV_curve:

                    V = abs(self.circuit.voltage_stability.continuation_voltage[element_idx])
                    Q = self.circuit.voltage_stability.continuation_power[element_idx].imag

                    if type(Q) != int:
                        self.display_QV_curve(ax, Q, V, 'Q')
                    else:
                        ax.text(0.4, 0.6, r'There are no results', fontsize=15)
                        self.ui.resultsPlot.redraw()

                elif type_of_result == ResultTypes.bus_s_v_curve:

                    V = abs(self.circuit.voltage_stability.continuation_voltage[element_idx])
                    S = abs(self.circuit.voltage_stability.continuation_power[element_idx])

                    if type(S) != int:
                        self.display_QV_curve(ax, [S], [V], 'S')
                    else:
                        ax.text(0.4, 0.6, r'There are no results', fontsize=15)
                        self.ui.resultsPlot.redraw()

                else:
                    ax.text(0.4, 0.6, r'There are no results', fontsize=15)
                    self.ui.resultsPlot.redraw()

            else:
                # time series
                if self.circuit.time_series.has_results():

                    x = self.circuit.time_series.time

                    if type_of_result == ResultTypes.bus_voltage_per_unit:
                        if element_idx is None:
                            y = abs(self.circuit.time_series.voltages)
                        else:
                            y = abs(self.circuit.time_series.voltages)[:, element_idx]
                        y2 = self.circuit.time_series.mismatch

                        ylabel = "Bus Voltages (p.u.)"
                        xlabel = 'Time'
                        ylabel2 = 'Error'
                        self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel, y2, ylabel2,
                                                          boxplot=useboxplot, elm_idx=element_idx)

                    elif type_of_result == ResultTypes.bus_voltage:
                        if element_idx is None:
                            y = abs(self.circuit.time_series.voltages)
                            y *= self.circuit.bus[:, BASE_KV]
                        else:
                            y = abs(self.circuit.time_series.voltages)[:, element_idx]
                            y *= self.circuit.bus[element_idx, BASE_KV]

                        y2 = self.circuit.time_series.mismatch

                        ylabel = "Bus Voltages (kV)"
                        xlabel = 'Time'
                        ylabel2 = 'Error'
                        self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel, y2, ylabel2,
                                                          boxplot=useboxplot, elm_idx=element_idx)

                    elif type_of_result == ResultTypes.bus_active_power:
                        if element_idx is None:
                            y = self.circuit.time_series.load_profiles.real
                        else:
                            y = self.circuit.time_series.load_profiles[:, element_idx].real

                        ylabel = "Bus active power (MW)"
                        xlabel = 'Time'
                        self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel,
                                                          boxplot=useboxplot, elm_idx=element_idx)

                    elif type_of_result == ResultTypes.bus_reactive_power:
                        if element_idx is None:
                            y = self.circuit.time_series.load_profiles.imag
                        else:
                            y = self.circuit.time_series.load_profiles[:, element_idx].imag

                        ylabel = "Bus reactive power (MVar)"
                        xlabel = 'Time'
                        self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel,
                                                          boxplot=useboxplot, elm_idx=element_idx)

                    elif type_of_result == ResultTypes.bus_apparent_power:
                        if element_idx is None:
                            y = abs(self.circuit.time_series.load_profiles)
                        else:
                            y = abs(self.circuit.time_series.load_profiles[:, element_idx])

                        ylabel = "Bus apparent power (MVA)"
                        xlabel = 'Time'
                        self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel,
                                                          boxplot=useboxplot, elm_idx=element_idx)

                    elif type_of_result == ResultTypes.branches_loading:
                        if element_idx is None:
                            y = abs(self.circuit.time_series.loadings)*100
                        else:
                            y = abs(self.circuit.time_series.loadings)[:, element_idx]*100
                        y2 = self.circuit.time_series.mismatch

                        ylabel = "Branch loading (%)"
                        xlabel = 'Time'
                        ylabel2 = 'Error'
                        self.display_series_branch_magnitude(ax, fig, x, y, ylabel, xlabel, y2, ylabel2,
                                                             boxplot=useboxplot, elm_idx=element_idx)

                    elif type_of_result == ResultTypes.bus_QV_curve:
                        print()

                    elif type_of_result == ResultTypes.bus_s_v_curve:
                        print()

                    else:
                        ax.text(0.4, 0.6, r'There are no results', fontsize=15)
                        self.ui.resultsPlot.redraw()

                if type_of_result == ResultTypes.bus_QV_curve:

                    V = abs(self.circuit.voltage_stability.continuation_voltage)
                    Q = self.circuit.voltage_stability.continuation_power.imag

                    self.display_QV_curve(ax, Q, V, 'Q')

                elif type_of_result == ResultTypes.bus_s_v_curve:

                    V = abs(self.circuit.voltage_stability.continuation_voltage)
                    S = abs(self.circuit.voltage_stability.continuation_power)

                    self.display_QV_curve(ax, S, V, 'S')

                # else:
                #     ax.text(0.4, 0.6, r'There are no results', fontsize=15)
                #     self.ui.resultsPlot.redraw()

    ####################################################################################################################
    # Class end
    ####################################################################################################################

    def print_console_help(self):
        """
        print the console help in the console
        @return:
        """
        print('GridCal internal commands.\n')
        print('If a command is unavailable is because the study has not been executed yet.')

        print('\n\nclc():\tclear the console.')

        print('\n\nPower flow commands:')
        print('\tpowerflow.voltage:\t the nodal voltages in per unit')
        print('\tpowerflow.current:\t the branch currents in per unit')
        print('\tpowerflow.loading:\t the branch loading in %')
        print('\tpowerflow.losses:\t the branch losses in per unit')
        print('\tpowerflow.power:\t the nodal power injections in per unit')
        print('\tpowerflow.power_from:\t the branch power injections in per unit at the "from" side')
        print('\tpowerflow.power_to:\t the branch power injections in per unit at the "to" side')

        print('\n\nTime series power flow commands:')
        print('\ttimeseries.time:\t Profiles time index (pandas DateTimeIndex object)')
        print('\ttimeseries.load_profiles:\t Load profiles matrix (row: time, col: node)')
        print('\ttimeseries.gen_profiles:\t Generation profiles matrix (row: time, col: node)')
        print('\ttimeseries.voltages:\t nodal voltages results matrix (row: time, col: node)')
        print('\ttimeseries.currents:\t branches currents results matrix (row: time, col: branch)')
        print('\ttimeseries.loadings:\t branches loadings results matrix (row: time, col: branch)')
        print('\ttimeseries.losses:\t branches losses results matrix (row: time, col: branch)')

        print('\n\nVoltage stability power flow commands:')
        print('\tvoltagestability.continuation_voltage:\t Voltage values for every power multiplication factor.')
        print('\tvoltagestability.continuation_lambda:\t Value of power multiplication factor applied')
        print('\tvoltagestability.continuation_power:\t Power values for every power multiplication factor.')

        print('\n\nMonte Carlo power flow commands:')
        print('\tstochastic.V_avg:\t nodal voltage average result.')
        print('\tstochastic.I_avg:\t branch current average result.')
        print('\tstochastic.Loading_avg:\t branch loading average result.')
        print('\tstochastic.Losses_avg:\t branch losses average result.')

        print('\tstochastic.V_std:\t nodal voltage standard deviation result.')
        print('\tstochastic.I_std:\t branch current standard deviation result.')
        print('\tstochastic.Loading_std:\t branch loading standard deviation result.')
        print('\tstochastic.Losses_std:\t branch losses standard deviation result.')

        print('\tstochastic.V_avg_series:\t nodal voltage average series.')
        print('\tstochastic.V_std_series:\t branch current standard deviation series.')
        print('\tstochastic.error_series:\t Monte Carlo error series (the convergence value).')

    def clc(self):
        """
        Clear the console
        @return:
        """
        self.ipyConsole.clearTerminal()


def run():
    app = QtGui.QApplication(sys.argv)
    window = MainGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run()
