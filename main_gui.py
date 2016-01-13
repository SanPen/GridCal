__author__ = 'santi'

# import sys
# try:
#     from .GUI.main_gui.main_gui import *
# except:
#     from GUI.main_gui.main_gui import *
#
#
# app = QtGui.QApplication(sys.argv)
# window = MainGUI()
# window.show()
# sys.exit(app.exec_())


__author__ = 'Santiago Penate Vera'
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
from matplotlib import pyplot as plt

try:
    from GUI.main_gui.gui import *
    from GUI.main_gui.profiles_input.profile_dialogue import *
    from grid.circuit_ import Circuit
    from grid.power_flow import *
    from grid.bus_definitions import *
    from grid.gen_definitions import *
    from grid.branch_definitions import *
except:
    from .GUI.main_gui.gui import *
    from .GUI.main_gui.profiles_input.profile_dialogue import *
    from .grid.circuit_ import Circuit
    from .grid.power_flow import *
    from .grid.bus_definitions import *
    from .grid.gen_definitions import *
    from .grid.branch_definitions import *


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
    voltage_per_unit = 1,
    voltage = 2,
    current_per_unit = 3,
    current = 4,
    power_at_buses_per_unit = 5,
    power_at_buses = 6,
    power_flow_per_unit = 7,
    power_flow = 8,
    branch_losses = 9,
    branches_loading = 10,
    voltage_series = 11,
    loading_series = 12
    current_series = 13


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

        # defaults
        self.ui.NRFD_option_button.setChecked(True)

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
        self.last_mode = 1
        self.node_size = 12

        # Directories
        self.project_directory = ""

        # Circuit
        self.circuit = Circuit()
        self.failed_edges = None

        # list view models
        self.available_data_structures_listModel = list_to_listModel(self.circuit.available_data_structures)

        # little difference between UNIX and Windows QT
        actiavate_action = 'activated()'
        if platform.system() == 'Windows':
            actiavate_action = 'triggered()'

        print(platform.system())

        # Button clicks connection

        QtCore.QObject.connect(self.ui.importGenButton, QtCore.SIGNAL('clicked()'), lambda: self.import_profiles(ProfileTypes.Generators))

        QtCore.QObject.connect(self.ui.importLoadButton, QtCore.SIGNAL('clicked()'), lambda: self.import_profiles(ProfileTypes.Loads))

        QtCore.QObject.connect(self.ui.visualizeGenButton, QtCore.SIGNAL('clicked()'), lambda: self.display_profiles_table(ProfileTypes.Generators))

        QtCore.QObject.connect(self.ui.visualizeLoadsButton, QtCore.SIGNAL('clicked()'), lambda: self.display_profiles_table(ProfileTypes.Loads))

        QtCore.QObject.connect(self.ui.copyResultsButton, QtCore.SIGNAL('clicked()'), self.copyResultsButton_click)

        QtCore.QObject.connect(self.ui.saveResultsButton, QtCore.SIGNAL('clicked()'), self.saveResultsButton_click)

        QtCore.QObject.connect(self.ui.set_profile_state_button, QtCore.SIGNAL('clicked()'), self.set_profile_state)

        QtCore.QObject.connect(self.ui.cancelButton, QtCore.SIGNAL('clicked()'), self.cancel)

        # menu bar action click

        QtCore.QObject.connect(self.ui.actionRedraw, QtCore.SIGNAL(actiavate_action), self.re_plot)

        QtCore.QObject.connect(self.ui.actionRedrawByType, QtCore.SIGNAL(actiavate_action), self.display_graph_by_type)

        QtCore.QObject.connect(self.ui.actionRedrawByResult, QtCore.SIGNAL(actiavate_action), self.display_graph_by_results)

        QtCore.QObject.connect(self.ui.actionAdd_node, QtCore.SIGNAL(actiavate_action), self.actionAdd_node_click)

        QtCore.QObject.connect(self.ui.actionLine, QtCore.SIGNAL(actiavate_action), self.actionLine_click)

        QtCore.QObject.connect(self.ui.actionTransformer, QtCore.SIGNAL(actiavate_action), self.actionTransformer_click)

        QtCore.QObject.connect(self.ui.actionLine_type, QtCore.SIGNAL(actiavate_action), self.actionLine_type_click)

        QtCore.QObject.connect(self.ui.actionTransformer_type, QtCore.SIGNAL(actiavate_action), self.actionTransformer_type_click)

        QtCore.QObject.connect(self.ui.actionOpen_file, QtCore.SIGNAL(actiavate_action), self.open_file)

        QtCore.QObject.connect(self.ui.actionSave, QtCore.SIGNAL(actiavate_action), self.save_file)

        # QtCore.QObject.connect(self.ui.actionImport, QtCore.SIGNAL(actiavate_action), self.actionImport_click)

        # QtCore.QObject.connect(self.ui.actionExport, QtCore.SIGNAL(actiavate_action), self.actionExport_click)

        # QtCore.QObject.connect(self.ui.actionNew_project, QtCore.SIGNAL(actiavate_action), self.actionNew_project_click)

        QtCore.QObject.connect(self.ui.actionPower_flow, QtCore.SIGNAL(actiavate_action), self.run_power_flow)

        QtCore.QObject.connect(self.ui.actionPower_Flow_Time_series, QtCore.SIGNAL(actiavate_action), self.run_time_series)

        QtCore.QObject.connect(self.ui.actionBlackout, QtCore.SIGNAL(actiavate_action), self.actionBlackout_click)


        # plot
        QtCore.QObject.connect(self.ui.actionBus_voltages, QtCore.SIGNAL(actiavate_action), lambda: self.plot_results(ResultTypes.voltage))

        QtCore.QObject.connect(self.ui.actionBus_voltages_p_u, QtCore.SIGNAL(actiavate_action), lambda: self.plot_results(ResultTypes.voltage_per_unit))

        QtCore.QObject.connect(self.ui.actionBranches_current, QtCore.SIGNAL(actiavate_action), lambda: self.plot_results(ResultTypes.current))

        QtCore.QObject.connect(self.ui.actionBranches_loading, QtCore.SIGNAL(actiavate_action), lambda: self.plot_results(ResultTypes.branches_loading))

        QtCore.QObject.connect(self.ui.actionBranches_losses, QtCore.SIGNAL(actiavate_action), lambda: self.plot_results(ResultTypes.branch_losses))

        #plot buttons

        QtCore.QObject.connect(self.ui.per_unit_voltages_Button, QtCore.SIGNAL('clicked()'), lambda: self.plot_results(ResultTypes.voltage_per_unit))

        QtCore.QObject.connect(self.ui.branches_loading_Button, QtCore.SIGNAL('clicked()'), lambda: self.plot_results(ResultTypes.branches_loading))


        QtCore.QObject.connect(self.ui.per_unit_voltages_series_Button, QtCore.SIGNAL('clicked()'), lambda: self.plot_results(ResultTypes.voltage_series))

        QtCore.QObject.connect(self.ui.branches_loading_series_Button, QtCore.SIGNAL('clicked()'), lambda: self.plot_results(ResultTypes.loading_series))

        # node size
        QtCore.QObject.connect(self.ui.actionBigger_nodes, QtCore.SIGNAL(actiavate_action), self.bigger_nodes)

        QtCore.QObject.connect(self.ui.actionSmaller_nodes, QtCore.SIGNAL(actiavate_action), self.smaller_nodes)

        # list clicks
        QtCore.QObject.connect(self.ui.dataStructuresListView, QtCore.SIGNAL('clicked(QModelIndex)'), self.display_objects_table)

        # table clicks
        QtCore.QObject.connect(self.ui.dataStructureTableView, QtCore.SIGNAL('doubleClicked(QModelIndex)'), self.dataStructureTableView_doubleClick)

        QtCore.QObject.connect(self.ui.dataStructureTableView, QtCore.SIGNAL('clicked(QModelIndex)'), self.dataStructureTableView_click)

        # table pressed
        QtCore.QObject.connect(self.ui.dataStructureTableView, QtCore.SIGNAL('entered(QModelIndex)'), self.dataStructureTableView_click)

        # splitters positions
        # self.ui.splitter_4.setStretchFactor(0.1,  0.9)

        # spin box
        # QtCore.QObject.connect(self.ui.node_size_spinbox, QtCore.SIGNAL("valueChanged(int)"), self.re_plot)

        self.UNLOCK()

    def LOCK(self, val=True):
        """

        :param val:
        :return:
        """
        self.lock_ui = val
        self.ui.progress_frame.setVisible(self.lock_ui)

    def UNLOCK(self):
        self.LOCK(False)

    def on_pick_event(self, event):
        """
        Store which text object was picked and were the pick event occurs.
        """
        self.element_dragged = event.artist
        self.pick_pos = (event.mouseevent.xdata, event.mouseevent.ydata)
        self.selected_node_idx = event.ind[0]

        # print('selected:', self.selected_node_idx)

        self.click_input_time = int(round(time.time() * 1000))

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
                name = 'node' + str(self.selected_node_idx)
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
            self.circuit.power_flow.end_process()
            self.circuit.time_series.end_process()
        else:
            pass

    def re_plot(self):
        """

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
        # print('By result')
        self.last_mode = 2
        self.re_plot()

    def display_graph_by_type(self):
        # print('By type')
        self.last_mode = 1
        self.re_plot()

    def bigger_nodes(self):
        """

        :return:
        """
        self.node_size += 2
        if self.node_size > 54:
            self.node_size = 54

        self.re_plot()

    def smaller_nodes(self):
        """

        :return:
        """
        self.node_size -=2
        if self.node_size < 2:
            self.node_size = 2

        self.re_plot()


    def runButton_click(self):
        print("Run")

    def importGenButton_click(self):
        print("importGenButton_click")

    def importLoadButton_click(self):
        print("importLoadButton_click")

    def resultsDisplayButton_click(self):
        print("resultsDisplayButton_click")

    def copyResultsButton_click(self):
        print("copyResultsButton_click")

    def saveResultsButton_click(self):
        print("saveResultsButton_click")


    def actionAdd_node_click(self):
        print("actionAdd_node_click")

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

        arr = list(np.datetime_as_string(self.circuit.time_series.time))
        self.ui.profile_time_selection_comboBox.addItems(arr)
        self.ui.results_time_selection_comboBox.addItems(arr)

    def set_profile_state(self):
        """
        Sets a snapshot of the time profiles to the current state of the circuit
        Returns:

        """
        idx = self.ui.profile_time_selection_comboBox.currentIndex()

        if self.circuit.time_series.is_ready():
            if idx > -1:

                if self.circuit.time_series.has_results():
                    self.circuit.set_time_profile_state_to_the_circuit(idx, True)
                else:
                    self.circuit.set_time_profile_state_to_the_circuit(idx, False)
        else:
            print('There are no profiles!')

    def open_file(self):
        """
        Open a file
        :return:
        """
        print("actionOpen_file_click")
        # declare the dialog
        # file_dialog = QtGui.QFileDialog(self)
        # declare the allowed file types
        files_types = "Excel 97 (*.xls);;Excel (*.xlsx);;DigSILENT (*.dgs);;MATPOWER (*.m)"
        # call dialog to select the file
        filename, type_selected = QtGui.QFileDialog.getOpenFileNameAndFilter(self, 'Open file',
                                                                       self.project_directory, files_types)

        if len(filename) > 0:
            self.project_directory = os.path.dirname(filename)
            print(filename)
            self.circuit = Circuit(filename, True)

            # set data structures list model
            self.ui.dataStructuresListView.setModel(self.available_data_structures_listModel)
            # set the first index
            index = self.available_data_structures_listModel.index(0, 0, QtCore.QModelIndex())
            self.ui.dataStructuresListView.setCurrentIndex(index)

            # clarn
            self.clean_GUI()

            # load table
            self.display_objects_table()

            # draw graph
            self.ui.gridPlot.setTitle(os.path.basename(filename))
            self.re_plot()

            # show times
            if self.circuit.time_series.is_ready():
                self.set_time_comboboxes()



    def save_file(self):
        """
        Save the circuit case to a file
        """
        # declare the allowed file types
        files_types = "Excel 97 (*.xls);;Excel (*.xlsx);;Numpy Case (*.npz)"
        # call dialog to select the file
        filename, type_selected = QtGui.QFileDialog.getSaveFileNameAndFilter(self, 'Save file',
                                                                       self.project_directory, files_types)

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
                labels = self.circuit.get_bus_labels()
                alsoQ = True
            elif profile_type == ProfileTypes.Generators:
                idx = self.circuit.gen[:, GEN_BUS].astype(int)
                labels = self.circuit.get_gen_labels()
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

    def display_profile(self, profile_type):
        """
        Show the profile in the GUI table
        @param profile_type:
        @return:
        """
        if self.circuit.time_series.time is not None:
            if profile_type == ProfileTypes.Loads:
                dta = self.circuit.time_series.load_profiles
                label = self.circuit.get_bus_labels()
            elif profile_type == ProfileTypes.Generators:
                dta = self.circuit.time_series.gen_profiles
                label = self.circuit.get_gen_labels()
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
        self.ui.profile_time_selection_comboBox.clear()
        self.ui.results_time_selection_comboBox.clear()
        self.ui.gridPlot.clear()


    def get_selected_power_flow_options(self):
        """
        Gather power flow run options
        :return:
        """
        solver_type = None

        if self.ui.NR_option_button.isChecked():
            solver_type = SolverType.NR
        elif self.ui.NRFD_option_button.isChecked():
            solver_type = SolverType.NRFD_BX
        elif self.ui.he_option_button.isChecked():
            solver_type = SolverType.HELM
        elif self.ui.gs_option_button.isChecked():
            solver_type = SolverType.GAUSS
        elif self.ui.zbus_option_button.isChecked():
            solver_type = SolverType.ZBUS
        elif self.ui.dc_option_button.isChecked():
            solver_type = SolverType.DC
        elif self.ui.NR_Iwamoto_option_button.isChecked():
            solver_type = SolverType.IWAMOTO

        check_freq_blackout = self.ui.freq_assesment_check.isChecked()

        exponent = self.ui.tolerance_spinBox.value()
        tolerance = 1.0 / (10.0**exponent)

        max_iter = self.ui.max_iterations_spinBox.value()

        set_last_solution = self.ui.remember_last_solution_checkBox.isChecked()

        if self.ui.helm_retry_checkBox.isChecked():
            solver_to_retry_with = SolverType.HELM
        else:
            solver_to_retry_with = SolverType.GAUSS

        return solver_type, check_freq_blackout, tolerance, max_iter, set_last_solution, solver_to_retry_with

    def run_power_flow(self):
        """

        :return:
        """
        print("actionPower_flow_click")

        if self.circuit.circuit_graph is not None:

            self.LOCK()

            # get circuit and solver conditions
            solver_type, check_freq_blackout, tolerance, \
            max_iter, set_last_solution, solver_to_retry_with = self.get_selected_power_flow_options()
            print('Solver: ', solver_to_retry_with)
            # threading connections
            self.connect(self.circuit.power_flow, SIGNAL("progress(float)"), self.ui.progressBar.setValue)
            self.connect(self.circuit.power_flow, SIGNAL("done()"), self.UNLOCK)
            self.connect(self.circuit.power_flow, SIGNAL("done()"), self.post_power_flow)

            # solve
            self.circuit.power_flow.set_run_options(solver_type=solver_type, tol=tolerance, max_it=max_iter,
                                                    enforce_reactive_power_limits=True, isMaster=True,
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

    def run_time_series(self):
        """
        Run the time series simulation
        @return:
        """
        print("actionPower_Flow_Time_series_click")

        if self.circuit.time_series is not None:
            if self.circuit.time_series.is_ready():
                self.LOCK()

                solver_type, check_freq_blackout, tolerance, max_iter, \
                set_las_solution, solver_to_retry_with = self.get_selected_power_flow_options()

                # set the time series power flow object the desired solver
                self.circuit.time_series.pf.solver_type = solver_type

                # set the solver to use in case of non convergence of the main solver
                self.circuit.time_series.pf.solver_to_retry_with = solver_to_retry_with

                # Set the time series run options
                self.connect(self.circuit.time_series, SIGNAL("progress(float)"), self.ui.progressBar.setValue)
                self.connect(self.circuit.time_series, SIGNAL("done()"), self.UNLOCK)

                # execute
                self.circuit.time_series.set_run_options(auto_repeat=True, tol=tolerance, max_it=max_iter, enforce_reactive_power_limits=True)
                self.circuit.time_series.start()  # the class is a Qthread

            else:
                msg = "The time series is not initialized"
                q = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 'GridCal',  msg)
                q.setStandardButtons(QtGui.QMessageBox.Ok)
                i = QtGui.QIcon()
                i.addPixmap(QtGui.QPixmap("..."), QtGui.QIcon.Normal)
                q.setWindowIcon(i)
                q.exec_()

    def actionBlackout_click(self):
        print("actionBlackout_click")

    def display_objects_table(self):
        """

        :return:
        """
        # print("dataStructuresListView_click")
        idx = self.ui.dataStructuresListView.selectedIndexes()[0].row()
        df = None
        if idx == 0:
            df = pd.DataFrame(data=self.circuit.bus, columns=bus_headers)

        elif idx == 1:
            df = pd.DataFrame(data=self.circuit.gen, columns=gen_headers)

        elif idx == 2:
            df = pd.DataFrame(data=self.circuit.branch, columns=branch_headers)

        elif idx == 3:  # Ybus
            pf = CircuitPowerFlow(self.circuit.baseMVA, self.circuit.bus, self.circuit.branch, self.circuit.gen, initialize_solvers=False)
            df = pd.DataFrame(data=pf.Ybus.todense())

            # plot the admittance matrix
            self.ui.resultsPlot.clear()
            self.ui.resultsPlot.canvas.ax.spy(pf.Ybus, precision=1e-3, marker='.', markersize=5)
            self.ui.resultsPlot.redraw()

        elif idx == 4:  # Sbus
            pf = CircuitPowerFlow(self.circuit.baseMVA, self.circuit.bus, self.circuit.branch, self.circuit.gen, initialize_solvers=False)
            df = pd.DataFrame(data=pf.Sbus)

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
        if self.circuit.time_series.is_ready():
            if profile_type == ProfileTypes.Loads:
                label = self.circuit.get_bus_labels()
                # df = pd.DataFrame(data=self.circuit.time_series.load_profiles, columns=label, index=self.circuit.time_series.time)
                df = self.circuit.time_series.get_loads_dataframe(label)
                self.ui.tableView.setModel(PandasModel(df))

            elif profile_type == ProfileTypes.Generators:
                label = self.circuit.get_gen_labels()
                # df = pd.DataFrame(data=self.circuit.time_series.gen_profiles, columns=label, index=self.circuit.time_series.time)
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
        labels = self.circuit.get_branch_labels()

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

    def display_bus_magnitude(self, ax, fig, y, ylabel, xlabel=''):
        """

        :param ax:
        :param fig:
        :param y:
        :param ylabel:
        :param xlabel:
        :return:
        """
        x = self.circuit.bus[:, BUS_I].astype(int)
        labels = self.circuit.get_bus_labels()
        r, c = np.shape(y)

        if c > 1:
            df_data = y[:, 0]
            ax.plot(x, y[:, 0], color='k', marker='o')
            ax.plot(x, y[:, 1], color='r')
            ax.plot(x, y[:, 2], color='r')
        else:
            df_data = y
            ax.plot(x, y, color='k', marker='o')

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation='vertical')

        # plot
        ax.set_aspect('auto')
        ax.axes.set_ylabel(ylabel)
        ax.axes.set_xlabel(xlabel)
        fig.tight_layout()
        self.ui.resultsPlot.redraw()
        df = pd.DataFrame(data=[df_data], columns=labels)
        self.ui.resultsTableView.setModel(PandasModel(df))

    def display_series_bus_magnitude(self, ax, fig, x, y, ylabel, xlabel='', y_limits=None, boxplot=False):
        """

        :param ax:
        :param fig:
        :param y:
        :param ylabel:
        :param xlabel:
        :return:
        """
        labels = self.circuit.get_bus_labels()

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
            df.plot(ax=ax)
        ax.set_aspect('auto')
        ax.axes.set_ylabel(ylabel)
        ax.axes.set_xlabel(xlabel)
        fig.tight_layout()
        self.ui.resultsPlot.redraw()

    def display_series_branch_magnitude(self, ax, fig, x, y, ylabel, xlabel='', y_limits=None, boxplot=False):
        """

        :param ax:
        :param fig:
        :param y:
        :param ylabel:
        :param xlabel:
        :return:
        """
        labels = self.circuit.get_branch_labels()

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
            df.plot(ax=ax)
        ax.set_aspect('auto')
        ax.axes.set_ylabel(ylabel)
        ax.axes.set_xlabel(xlabel)
        fig.tight_layout()
        self.ui.resultsPlot.redraw()

    def plot_results(self, type_of_result):
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

            t = self.ui.results_time_selection_comboBox.currentIndex()

            if type_of_result == ResultTypes.branch_losses:
                if t > -1:
                    y = abs(self.circuit.time_series.losses[t, :])
                else:
                    y = self.circuit.branch[:, LOSSES]
                ylabel = "Branch losses (MVA)"
                self.display_branch_magnitude(ax, fig, y, ylabel)

            elif type_of_result == ResultTypes.branches_loading:
                if t > -1:
                    y = abs(self.circuit.time_series.loadings[t, :])
                else:
                    y = self.circuit.branch[:, LOADING]
                ylabel = "Branch loading (%)"
                self.display_branch_magnitude(ax, fig, y * 100, ylabel)

            elif type_of_result == ResultTypes.current:
                if t > -1:
                    y = abs(self.circuit.time_series.currents[t, :])
                else:
                    y = self.circuit.branch[:, BR_CURRENT]
                ylabel = "Branch Currents (kA)"
                self.display_branch_magnitude(ax, fig, y, ylabel)

            elif type_of_result == ResultTypes.voltage_per_unit:
                if t > -1:
                    nb = len(self.circuit.bus)
                    y = zeros((nb, 3))
                    y[:, 0] = abs(self.circuit.time_series.voltages[t, :])
                    y[:, [1, 2]] = self.circuit.bus[:, [VMIN, VMAX]]
                else:
                    y = self.circuit.bus[:, [VM, VMIN, VMAX]]

                ylabel = "Bus Voltages (p.u.)"
                self.display_bus_magnitude(ax, fig, y, ylabel)

            elif type_of_result == ResultTypes.voltage:
                if t > -1:
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

            # time series
            if self.circuit.time_series.has_results():
                useboxplot = self.ui.boxplot_checkbox.isChecked()
                if type_of_result == ResultTypes.voltage_series:
                    x = self.circuit.time_series.time
                    y = abs(self.circuit.time_series.voltages)
                    # y = self.circuit.bus[:, [VM, VMIN, VMAX]]
                    ylabel = "Bus Voltages (p.u.)"
                    xlabel = 'Time'
                    self.display_series_bus_magnitude(ax, fig, x, y, ylabel, xlabel, boxplot=useboxplot)
                elif type_of_result == ResultTypes.loading_series:
                    x = self.circuit.time_series.time
                    y = abs(self.circuit.time_series.loadings)
                    # y = self.circuit.bus[:, [VM, VMIN, VMAX]]
                    ylabel = "Branch loading (%)"
                    xlabel = 'Time'
                    self.display_series_branch_magnitude(ax, fig, x, y, ylabel, xlabel, boxplot=useboxplot)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainGUI()
    window.show()
    sys.exit(app.exec_())
