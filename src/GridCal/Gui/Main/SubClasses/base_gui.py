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

import ctypes
import gc
import os.path
import sys
import threading
import webbrowser
from typing import List, Union

# import darkdetect
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

# GUI importswa
from PySide6 import QtGui, QtWidgets, QtCore

# Engine imports
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Simulations as sim
from GridCalEngine.enumerations import EngineType
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit, compile_numerical_circuit_at
import GridCal.Gui.GuiFunctions as gf
import GridCal.Session.synchronization_driver as syncdrv
from GridCalEngine.Compilers.circuit_to_bentayga import BENTAYGA_AVAILABLE
from GridCalEngine.Compilers.circuit_to_newton_pa import NEWTON_PA_AVAILABLE
from GridCalEngine.Compilers.circuit_to_pgm import PGM_AVAILABLE
from GridCal.Gui.AboutDialogue.about_dialogue import AboutDialogueGuiGUI
from GridCal.Gui.Analysis.AnalysisDialogue import GridAnalysisGUI
from GridCal.Gui.ContingencyPlanner.contingency_planner_dialogue import ContingencyPlannerGUI
from GridCal.Gui.CoordinatesInput.coordinates_dialogue import CoordinatesInputGUI
from GridCal.Gui.GeneralDialogues import CheckListDialogue, StartEndSelectionDialogue
from GridCal.Gui.messages import yes_no_question, warning_msg, info_msg, error_msg
from GridCal.Gui.GridGenerator.grid_generator_dialogue import GridGeneratorGUI
from GridCal.Gui.Main.MainWindow import Ui_mainWindow, QMainWindow
from GridCal.Gui.Main.object_select_window import ObjectSelectWindow
from GridCal.Gui.ProfilesInput.models_dialogue import ModelsInputGUI
from GridCal.Gui.ProfilesInput.profile_dialogue import ProfileInputGUI
from GridCal.Session.session import SimulationSession, GcThread
from GridCal.Gui.SigmaAnalysis.sigma_analysis_dialogue import SigmaAnalysisGUI
from GridCal.Gui.SyncDialogue.sync_dialogue import SyncDialogueWindow
from GridCal.Gui.TowerBuilder.LineBuilderDialogue import TowerBuilderGUI
from GridCal.Gui.GeneralDialogues import clear_qt_layout
from GridCal.Gui.ConsoleWidget import ConsoleWidget
from GridCal.Gui.Diagrams.generic_graphics import IS_DARK
from GridCal.templates import (get_cables_catalogue, get_transformer_catalogue, get_wires_catalogue,
                               get_sequence_lines_catalogue)


def terminate_thread(thread):
    """
    Terminates a python thread from another thread.

    :param thread: a threading.Thread instance
    """
    if not thread.is_alive():
        return False

    exc = ctypes.py_object(SystemExit)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread.ident), exc)
    if res == 0:
        raise ValueError("nonexistent thread id")
    elif res > 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")

    return True


def traverse_objects(name, obj, lst: list, i=0):
    """

    :param name:
    :param obj:
    :param lst:
    :param i:
    """
    lst.append((name, sys.getsizeof(obj)))
    if i < 10:
        if hasattr(obj, '__dict__'):
            for name2, obj2 in obj.__dict__.items():
                if isinstance(obj2, np.ndarray):
                    lst.append((name + "/" + name2, sys.getsizeof(obj2)))
                else:
                    if isinstance(obj2, list):
                        # list or
                        for k, obj3 in enumerate(obj2):
                            traverse_objects(name=name + "/" + name2 + '[' + str(k) + ']',
                                             obj=obj3, lst=lst, i=i + 1)
                    elif isinstance(obj2, dict):
                        # list or
                        for name3, obj3 in obj2.items():
                            traverse_objects(name=name + "/" + name2 + '[' + name3 + ']',
                                             obj=obj3, lst=lst, i=i + 1)
                    else:
                        # normal obj
                        if obj2 != obj:
                            traverse_objects(name=name + "/" + name2, obj=obj2, lst=lst, i=i + 1)


class BaseMainGui(QMainWindow):
    """
    DiagramFunctionsMain
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """
        # create main window
        QMainWindow.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)

        # Declare circuit
        self.circuit: MultiCircuit = MultiCircuit()

        self.lock_ui = False
        self.ui.progress_frame.setVisible(self.lock_ui)

        self.stuff_running_now = list()

        self.session: SimulationSession = SimulationSession(name='GUI session')

        self._file_name = ''

        self.project_directory = os.path.expanduser("~")

        self.current_boundary_set: str = ""

        # threads --------------------------------------------------------------------------------------------------
        self.painter = None
        self.open_file_thread_object = None
        self.save_file_thread_object = None
        self.last_file_driver = None
        self.delete_and_reduce_driver = None
        self.export_all_thread_object = None
        self.topology_reduction = None
        self.find_node_groups_driver: Union[sim.NodeGroupsDriver, None] = None
        self.file_sync_thread = syncdrv.FileSyncThread(self.circuit, None, None)

        # simulation start end
        self.simulation_start_index: int = 0
        self.simulation_end_index: int = 0

        # window pointers ------------------------------------------------------------------------------------------
        self.file_sync_window: Union[SyncDialogueWindow, None] = None
        self.sigma_dialogue: Union[SigmaAnalysisGUI, None] = None
        self.grid_generator_dialogue: Union[GridGeneratorGUI, None] = None
        self.contingency_planner_dialogue: Union[ContingencyPlannerGUI, None] = None
        self.analysis_dialogue: Union[GridAnalysisGUI, None] = None
        self.profile_input_dialogue: Union[ProfileInputGUI, None] = None
        self.models_input_dialogue: Union[ModelsInputGUI, None] = None
        self.object_select_window: Union[ObjectSelectWindow, None] = None
        self.coordinates_window: Union[CoordinatesInputGUI, None] = None
        self.about_msg_window: Union[AboutDialogueGuiGUI, None] = None
        self.tower_builder_window: Union[TowerBuilderGUI, None] = None
        self.investment_checks_diag: Union[CheckListDialogue, None] = None
        self.contingency_checks_diag: Union[CheckListDialogue, None] = None
        self.start_end_dialogue_window: Union[StartEndSelectionDialogue, None] = None

        # available engines
        engine_lst = [EngineType.GridCal]
        if NEWTON_PA_AVAILABLE:
            engine_lst.append(EngineType.NewtonPA)
        if BENTAYGA_AVAILABLE:
            engine_lst.append(EngineType.Bentayga)
        if PGM_AVAILABLE:
            engine_lst.append(EngineType.PGM)

        self.ui.engineComboBox.setModel(gf.get_list_model([x.value for x in engine_lst]))
        self.ui.engineComboBox.setCurrentIndex(0)
        self.engine_dict = {x.value: x for x in engine_lst}

        # dark mode detection
        self.ui.dark_mode_checkBox.setChecked(IS_DARK)

        # Console
        self.console: Union[ConsoleWidget, None] = None
        try:
            self.create_console()
        except TypeError:
            error_msg('The console has failed because the QtConsole guys have a bug in their package :(')

        self.calculation_inputs_to_display = None

        # ----------------------------------------------------------------------------------------------------------
        self.ui.actionClear_stuff_running_right_now.triggered.connect(self.clear_stuff_running)
        self.ui.actionAbout.triggered.connect(self.about_box)
        self.ui.actionAuto_rate_branches.triggered.connect(self.auto_rate_branches)
        self.ui.actionDetect_transformers.triggered.connect(self.detect_transformers)
        self.ui.actionLaunch_data_analysis_tool.triggered.connect(self.display_grid_analysis)
        self.ui.actionOnline_documentation.triggered.connect(self.show_online_docs)
        self.ui.actionReport_a_bug.triggered.connect(self.report_a_bug)
        self.ui.actionAdd_default_catalogue.triggered.connect(self.add_default_catalogue)
        self.ui.actionFix_generators_active_based_on_the_power.triggered.connect(
            self.fix_generators_active_based_on_the_power
        )
        self.ui.actionFix_loads_active_based_on_the_power.triggered.connect(self.fix_loads_active_based_on_the_power)
        self.ui.actionInitialize_contingencies.triggered.connect(self.initialize_contingencies)

        # Buttons
        self.ui.cancelButton.clicked.connect(self.set_cancel_state)

        # doubleSpinBox
        self.ui.fbase_doubleSpinBox.valueChanged.connect(self.change_circuit_base)
        self.ui.sbase_doubleSpinBox.valueChanged.connect(self.change_circuit_base)

        self.ui.grid_name_line_edit.textChanged.connect(self.change_circuit_name)

    def LOCK(self, val: bool = True) -> None:
        """
        Lock the interface to prevent new simulation launches
        :param val:
        :return:
        """
        self.lock_ui = val
        self.ui.progress_frame.setVisible(self.lock_ui)
        QtGui.QGuiApplication.processEvents()

    def UNLOCK(self) -> None:
        """
        Unlock the interface
        """
        if not self.any_thread_running():
            self.LOCK(False)

    def create_console(self) -> None:
        """
        Create console
        """
        if self.console is not None:
            clear_qt_layout(self.ui.pythonConsoleTab.layout())

        self.console = ConsoleWidget(customBanner="GridCal console.\n\n"
                                                  "type hlp() to see the available specific commands.\n\n"
                                                  "the following libraries are already loaded:\n"
                                                  "np: numpy\n"
                                                  "pd: pandas\n"
                                                  "plt: matplotlib\n"
                                                  "app: This instance of GridCal\n"
                                                  "circuit: The current grid\n\n")

        self.console.buffer_size = 10000

        # add the console widget to the user interface
        self.ui.pythonConsoleTab.layout().addWidget(self.console)

        # push some variables to the console
        self.console.push_vars({"hlp": self.print_console_help,
                                "np": np,
                                "pd": pd,
                                "plt": plt,
                                "clc": self.clc,
                                'app': self,
                                'circuit': self.circuit})

        if IS_DARK:
            self.console.set_dark_theme()
        else:
            self.console.set_light_theme()

    @staticmethod
    def print_console_help():
        """
        Print the console help in the console
        @return:
        """
        print('GridCal internal commands.\n')
        print('If a command is unavailable is because the study has not been executed yet.')

        print('\n\nclc():\tclear the console.')

        print('\n\nApp functions:')
        print('\tapp.new_project(): Clear all.')
        print('\tapp.open_file(): Prompt to load GridCal compatible file')
        print('\tapp.save_file(): Prompt to save GridCal file')
        print('\tapp.export_diagram(): Prompt to export the diagram in png.')
        print('\tapp.create_schematic_from_api(): Create the schematic from the circuit information.')
        print('\tapp.adjust_all_node_width(): Adjust the width of all the nodes according to their name.')
        print('\tapp.numerical_circuit: get compilation of the assets.')
        print('\tapp.islands: get compilation of the assets split into the topological islands.')

        print('\n\nCircuit functions:')
        print('\tapp.circuit.plot_graph(): Plot a graph in a Matplotlib window. Call plt.show() after.')

        print('\n\nPower flow results:')
        print('\tapp.session.power_flow.voltage:\t the nodal voltages in per unit')
        print('\tapp.session.power_flow.current:\t the branch currents in per unit')
        print('\tapp.session.power_flow.loading:\t the branch loading in %')
        print('\tapp.session.power_flow.losses:\t the branch losses in per unit')
        print('\tapp.session.power_flow.power:\t the nodal power Injections in per unit')
        print('\tapp.session.power_flow.Sf:\t the branch power Injections in per unit at the "from" side')
        print('\tapp.session.power_flow.St:\t the branch power Injections in per unit at the "to" side')

        print('\n\nShort circuit results:')
        print('\tapp.session.short_circuit.voltage:\t the nodal voltages in per unit')
        print('\tapp.session.short_circuit.current:\t the branch currents in per unit')
        print('\tapp.session.short_circuit.loading:\t the branch loading in %')
        print('\tapp.session.short_circuit.losses:\t the branch losses in per unit')
        print('\tapp.session.short_circuit.power:\t the nodal power Injections in per unit')
        print('\tapp.session.short_circuit.power_from:\t the branch power Injections in per unit at the "from" side')
        print('\tapp.session.short_circuit.power_to:\t the branch power Injections in per unit at the "to" side')
        print('\tapp.session.short_circuit.short_circuit_power:\t Short circuit power in MVA of the grid nodes')

        print('\n\nOptimal power flow results:')
        print('\tapp.session.optimal_power_flow.voltage:\t the nodal voltages angles in rad')
        print('\tapp.session.optimal_power_flow.load_shedding:\t the branch loading in %')
        print('\tapp.session.optimal_power_flow.losses:\t the branch losses in per unit')
        print('\tapp.session.optimal_power_flow.Sbus:\t the nodal power Injections in MW')
        print('\tapp.session.optimal_power_flow.Sf:\t the branch power Sf')

        print('\n\nTime series power flow results:')
        print('\tapp.session.power_flow_ts.time:\t Profiles time index (pandas DateTimeIndex object)')
        print('\tapp.session.power_flow_ts.load_profiles:\t Load profiles matrix (row: time, col: node)')
        print('\tapp.session.power_flow_ts.gen_profiles:\t Generation profiles matrix (row: time, col: node)')
        print('\tapp.session.power_flow_ts.voltages:\t nodal voltages results matrix (row: time, col: node)')
        print('\tapp.session.power_flow_ts.currents:\t Branches currents results matrix (row: time, col: branch)')
        print('\tapp.session.power_flow_ts.loadings:\t Branches loadings results matrix (row: time, col: branch)')
        print('\tapp.session.power_flow_ts.losses:\t Branches losses results matrix (row: time, col: branch)')

        print('\n\nVoltage stability power flow results:')
        print('\tapp.session.continuation_power_flow.voltage:\t Voltage values for every power multiplication factor.')
        print('\tapp.session.continuation_power_flow.lambda:\t Value of power multiplication factor applied')
        print('\tapp.session.continuation_power_flow.Sf:\t Power values for every power multiplication factor.')

        print('\n\nMonte Carlo power flow results:')
        print('\tapp.session.stochastic_power_flow.V_avg:\t nodal voltage average result.')
        print('\tapp.session.stochastic_power_flow.I_avg:\t branch current average result.')
        print('\tapp.session.stochastic_power_flow.Loading_avg:\t branch loading average result.')
        print('\tapp.session.stochastic_power_flow.Losses_avg:\t branch losses average result.')
        print('\tapp.session.stochastic_power_flow.V_std:\t nodal voltage standard deviation result.')
        print('\tapp.session.stochastic_power_flow.I_std:\t branch current standard deviation result.')
        print('\tapp.session.stochastic_power_flow.Loading_std:\t branch loading standard deviation result.')
        print('\tapp.session.stochastic_power_flow.Losses_std:\t branch losses standard deviation result.')
        print('\tapp.session.stochastic_power_flow.V_avg_series:\t nodal voltage average series.')
        print('\tapp.session.stochastic_power_flow.V_std_series:\t branch current standard deviation series.')
        print('\tapp.session.stochastic_power_flow.error_series:\t Monte Carlo error series (the convergence value).')
        print('The same for app.latin_hypercube_sampling')

    def clc(self):
        """
        Clear the console
        """
        self.console.clear()

    @property
    def file_name(self) -> str:
        """
        Get the current file name
        :return: str
        """
        return self._file_name

    @file_name.setter
    def file_name(self, val: str):
        """
        Set the current file name
        :param val: file name
        """
        self._file_name = val
        if not isinstance(self._file_name, list):
            self.ui.file_information_label.setText(self._file_name)
        else:
            self.ui.file_information_label.setText("")

    @staticmethod
    def collect_memory() -> None:
        """
        Collect memory
        """
        for i in (0, 1, 2):
            gc.collect(generation=i)

    def get_simulation_threads(self) -> List[GcThread]:
        """
        Get all threads that has to do with simulation
        :return: list of simulation threads
        """

        all_threads = list(self.session.threads.values())

        return all_threads

    def get_process_threads(self) -> List[GcThread]:
        """
        Get all threads that has to do with processing
        :return: list of process threads
        """
        all_threads = [self.open_file_thread_object,
                       self.save_file_thread_object,
                       self.painter,
                       self.delete_and_reduce_driver,
                       self.export_all_thread_object,
                       self.find_node_groups_driver,
                       self.file_sync_thread,
                       ]
        return all_threads

    def get_all_threads(self) -> List[GcThread]:
        """
        Get all threads
        :return: list of all threads
        """
        all_threads = self.get_simulation_threads() + self.get_process_threads()
        return all_threads

    def stop_all_threads(self):
        """
        Stop all running threads
        """
        for thr in self.get_all_threads():
            if thr is not None:
                thr.quit()

        for thread in threading.enumerate():
            print(thread.name, end="")
            if "MainThread" not in thread.name:
                stat = terminate_thread(thread)
                if stat:
                    print(" killed")
                else:
                    print(" not killed")
            else:
                print(" Skipped")

        # second pass, kill main too
        for thread in threading.enumerate():
            print(thread.name, end="")
            stat = terminate_thread(thread)
            if stat:
                print(" killed")
            else:
                print(" not killed")

    def any_thread_running(self) -> bool:
        """
        Checks if any thread is running
        :return: True/False
        """
        val = False

        # this list cannot be created only once, because the None will be copied
        # instead of being a pointer to the future value like it would in a typed language
        all_threads = self.get_all_threads()

        for thr in all_threads:
            if thr is not None:
                if thr.isRunning():
                    return True
        return val

    def clear_stuff_running(self) -> None:
        """
        This clears the list of stuff running right now
        this list blocks new executions of the same threads.
        Cleaning is useful if a particular thread crashes and you want to retry.
        """
        self.stuff_running_now.clear()

    def get_all_objects_in_memory(self):
        """
        Get a list of the objects in memory
        :return:
        """
        objects = []
        # for name, obj in globals().items():
        #     objects.append([name, sys.getsizeof(obj)])

        traverse_objects('MainGUI', self, objects)

        df = pd.DataFrame(data=objects, columns=['Name', 'Size (kb)'])
        df.sort_values(by='Size (kb)', inplace=True, ascending=False)
        return df

    def expand_object_tree_nodes(self) -> None:
        """
        Expand objects' tree nodes
        """
        proxy = self.ui.dataStructuresTreeView.model()

        for row in range(proxy.rowCount()):
            index = proxy.index(row, 0)
            self.ui.dataStructuresTreeView.expand(index)

    def get_simulation_start(self) -> int:
        """
        Get the start simulation index
        """
        return self.simulation_start_index

    def get_simulation_end(self) -> int:
        """
        Get the end simulation index
        """
        return self.simulation_end_index

    def setup_sim_indices(self, st: int, en: int):
        """
        Set the simulation indices
        :param st: start index
        :param en: end index
        """
        self.simulation_start_index = st
        self.simulation_end_index = en

    def get_diagram_slider_index(self) -> Union[int, None]:
        """
        Get the diagram slider value
        :return: [None, int]
        """
        idx = self.ui.diagram_step_slider.value()
        return idx if idx > -1 else None

    def get_db_slider_index(self) -> Union[int, None]:
        """
        Get the db slider value
        :return: [None, int]
        """
        idx = self.ui.db_step_slider.value()
        return idx if idx > -1 else None

    def setup_time_sliders(self):
        """
        Setup the time sliders
        """
        for slider in [self.ui.diagram_step_slider, self.ui.db_step_slider]:
            if self.circuit.has_time_series:
                slider.setRange(-1, self.circuit.get_time_number() - 1)
            else:
                slider.setRange(-1, -1)
            slider.setValue(-1)

    def update_date_dependent_combos(self):
        """
        update the drop down menus that display dates
        """
        if self.circuit.time_profile is not None:
            mdl = gf.get_list_model([str(e) for e in self.circuit.time_profile])
            # setup profile sliders
            t = len(self.circuit.time_profile) - 1
            self.setup_sim_indices(0, t)

        else:
            mdl = QtGui.QStandardItemModel()
        self.ui.vs_departure_comboBox.setModel(mdl)
        self.ui.vs_target_comboBox.setModel(mdl)
        self.setup_time_sliders()

    def update_area_combos(self):
        """
        Update the area dependent combos
        """
        n = len(self.circuit.areas)
        mdl1 = gf.get_list_model([str(elm) for elm in self.circuit.areas], checks=True)
        mdl2 = gf.get_list_model([str(elm) for elm in self.circuit.areas], checks=True)

        self.ui.areaFromListView.setModel(mdl1)
        self.ui.areaToListView.setModel(mdl2)

        if n > 1:
            self.ui.areaFromListView.model().item(0).setCheckState(QtCore.Qt.CheckState.Checked)
            self.ui.areaToListView.model().item(1).setCheckState(QtCore.Qt.CheckState.Checked)

    def fix_generators_active_based_on_the_power(self, ask_before=True):
        """
        set the generators active based on the active power values
        :return:
        """

        if ask_before:
            ok = yes_no_question("This action sets the generation active profile based on the active power profile "
                                 "such that ig a generator active power is zero, the active value is false",
                                 "Set generation active profile")
        else:
            ok = True

        if ok:
            self.circuit.set_generators_active_profile_from_their_active_power()
            self.circuit.set_batteries_active_profile_from_their_active_power()

    def fix_loads_active_based_on_the_power(self, ask_before=True):
        """
        set the loads active based on the active power values
        :return:
        """

        if ask_before:
            ok = yes_no_question("This action sets the generation active profile based on the active power profile "
                                 "such that ig a generator active power is zero, the active value is false",
                                 "Set generation active profile")
        else:
            ok = True

        if ok:
            self.circuit.set_loads_active_profile_from_their_active_power()

    def get_preferred_engine(self) -> EngineType:
        """
        Get the currently selected engine
        :return: EngineType
        """
        val = self.ui.engineComboBox.currentText()
        return self.engine_dict[val]

    def about_box(self):
        """
        Display about box
        :return:
        """

        self.about_msg_window = AboutDialogueGuiGUI(self)
        self.about_msg_window.setVisible(True)

    @staticmethod
    def show_online_docs():
        """
        Open the online documentation in a web browser
        """
        webbrowser.open('https://gridcal.readthedocs.io/en/latest/', new=2)

    @staticmethod
    def report_a_bug():
        """
        Open the online github issues in a web browser
        """
        webbrowser.open('https://github.com/SanPen/GridCal/issues', new=2)

    def auto_rate_branches(self):
        """
        Rate the Branches that do not have rate
        """

        branches = self.circuit.get_branches()

        if len(branches) > 0:
            pf_results = self.session.power_flow

            if pf_results is not None:
                factor = self.ui.branch_rating_doubleSpinBox.value()

                for i, branch in enumerate(branches):

                    S = pf_results.Sf[i]

                    if branch.rate < 1e-3 or self.ui.rating_override_checkBox.isChecked():
                        r = np.round(abs(S) * factor, 1)
                        branch.rate = r if r > 0.0 else 1.0
                    else:
                        pass  # the rate is ok

            else:
                info_msg('Run a power flow simulation first.\nThe results are needed in this function.')

        else:
            warning_msg('There are no Branches!')

    def detect_transformers(self):
        """
        Detect which Branches are transformers
        """
        if len(self.circuit.lines) > 0:

            for elm in self.circuit.lines:

                v1 = elm.bus_from.Vnom
                v2 = elm.bus_to.Vnom

                if abs(v1 - v2) > 1.0:
                    self.circuit.convert_line_to_transformer(elm)
                else:

                    pass  # is a line

        else:
            warning_msg('There are no Branches!')

    def set_cancel_state(self) -> None:
        """
        Cancel what ever's going on that can be cancelled
        @return:
        """

        reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               'Are you sure that you want to cancel the simulation?',
                                               QtWidgets.QMessageBox.StandardButton.Yes,
                                               QtWidgets.QMessageBox.StandardButton.No)

        if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
            # send the cancel state to whatever it is being executed

            for drv in self.get_all_threads():
                if drv is not None:
                    if hasattr(drv, 'cancel'):
                        drv.cancel()
        else:
            pass

    def display_grid_analysis(self):
        """
        Display the grid analysis GUI
        """

        self.analysis_dialogue = GridAnalysisGUI(circuit=self.circuit)

        self.analysis_dialogue.resize(int(1.61 * 600.0), 600)
        self.analysis_dialogue.show()

    def change_circuit_base(self):
        """
        Update the circuit base values from the UI
        """

        Sbase_new = self.ui.sbase_doubleSpinBox.value()
        self.circuit.change_base(Sbase_new)

        self.circuit.fBase = self.ui.fbase_doubleSpinBox.value()

    def change_circuit_name(self):
        """

        :return:
        """
        self.circuit.name = self.ui.grid_name_line_edit.text().strip()

    def add_default_catalogue(self) -> None:
        """
        Add default catalogue to circuit
        """

        self.circuit.transformer_types += get_transformer_catalogue()
        self.circuit.underground_cable_types += get_cables_catalogue()
        self.circuit.wire_types += get_wires_catalogue()
        self.circuit.sequence_line_types += get_sequence_lines_catalogue()

    def get_snapshot_circuit(self):
        """
        Get a snapshot compilation
        :return: SnapshotData instance
        """
        return compile_numerical_circuit_at(circuit=self.circuit)

    @property
    def numerical_circuit(self) -> NumericalCircuit:
        """
        get the snapshot NumericalCircuit
        :return: NumericalCircuit
        """
        return self.get_snapshot_circuit()

    @property
    def islands(self) -> List[NumericalCircuit]:
        """
        get the snapshot islands
        :return: List[NumericalCircuit]
        """
        numerical_circuit = compile_numerical_circuit_at(circuit=self.circuit)
        calculation_inputs = numerical_circuit.split_into_islands()
        return calculation_inputs

    def initialize_contingencies(self):
        """
        Launch the contingency planner to initialize the contingencies
        :return:
        """
        self.contingency_planner_dialogue = ContingencyPlannerGUI(parent=self, grid=self.circuit)
        self.contingency_planner_dialogue.exec()

        # gather results
        if self.contingency_planner_dialogue.generated_results:
            if len(self.contingency_planner_dialogue.contingency_groups):
                self.circuit.contingency_groups += self.contingency_planner_dialogue.contingency_groups
                self.circuit.contingencies += self.contingency_planner_dialogue.contingencies
            else:
                info_msg(text="No contingencies were generated :/", title="Contingency planner")
