# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import io
import sys
import builtins
from code import InteractiveConsole
import numpy as np
import pandas as pd
from PySide6.QtGui import QFont, QFontMetrics, Qt
from PySide6 import QtWidgets, QtCore
from matplotlib import pyplot as plt

from GridCalEngine.IO.file_system import get_create_gridcal_folder
from GridCalEngine.IO.file_system import scripts_path
from GridCal.Gui.Main.SubClasses.io import IoMain
from GridCal.Gui.Main.SubClasses.Scripting.python_highlighter import PythonHighlighter
from GridCal.Gui.gui_functions import CustomFileSystemModel
import GridCal.Gui.gui_functions as gf
from GridCal.Gui.messages import error_msg, yes_no_question


class ScriptingMain(IoMain):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        IoMain.__init__(self, parent)

        # Source code text ---------------------------------------------------------------------------------------------
        # Set the font for your widget
        font = QFont("Consolas", 10)  # Replace "Consolas" with your preferred monospaced font

        self.interpreter = InteractiveConsole(locals=globals())
        self.completer = QtWidgets.QCompleter()

        # Set splitter sizes to 80% for output and 20% for input
        self.ui.consoleSplitter.setSizes([800, 200])

        # console output
        self.ui.consoleOutputTextEdit.setText("GridCal console\n")
        self.ui.consoleOutputTextEdit.setReadOnly(True)
        self.ui.consoleOutputTextEdit.setFont(font)
        self.ui.consoleOutputTextEdit.setPlaceholderText("GridCal console output")
        PythonHighlighter(self.ui.consoleOutputTextEdit.document())

        # quick input
        self.ui.consoleInputTextEdit.setPlaceholderText("Enter Python code here\nType Ctrl + Enter to run")
        self.ui.consoleInputTextEdit.setFont(font)
        PythonHighlighter(self.ui.consoleInputTextEdit.document())
        self.ui.consoleInputTextEdit.installEventFilter(self)  # Install event filter to handle Ctrl+Enter

        # Source code
        self.ui.sourceCodeTextEdit.setFont(font)
        font_metrics = QFontMetrics(font)  # Set tab width to 4 spaces
        tab_stop_width = font_metrics.horizontalAdvance(' ' * 4)  # Width of 4 spaces in the selected font
        self.ui.sourceCodeTextEdit.setTabStopDistance(tab_stop_width)
        self.ui.sourceCodeTextEdit.highlighter = PythonHighlighter(self.ui.sourceCodeTextEdit.document())
        self.ui.sourceCodeTextEdit.setPlaceholderText("Enter or load Python code here\nType Ctrl + Enter to run")
        self.ui.sourceCodeTextEdit.installEventFilter(self)  # Install event filter to handle Ctrl+Enter

        self.add_console_vars()

        # Set up IntelliSense
        self.setup_intellisense()

        # scripts tree view --------------------------------------------------------------------------------------------
        self.python_fs_model = CustomFileSystemModel(root_path=scripts_path(), ext_filter=['*.py'])
        self.ui.sourceCodeTreeView.setModel(self.python_fs_model)
        self.ui.sourceCodeTreeView.setRootIndex(self.python_fs_model.index(scripts_path()))

        # actions ------------------------------------------------------------------------------------------------------
        self.ui.actionReset_console.triggered.connect(self.reset_console)

        # button clicks -------------------------------------------------------------------------------------------------
        self.ui.runSourceCodeButton.clicked.connect(self.run_source_code)
        self.ui.saveSourceCodeButton.clicked.connect(self.save_source_code)
        self.ui.clearSourceCodeButton.clicked.connect(self.clear_source_code)
        self.ui.runCommandButton.clicked.connect(self.run_command)
        self.ui.clearConsoleButton.clicked.connect(self.clear_console)

        # double clicked -----------------------------------------------------------------------------------------------
        self.ui.sourceCodeTreeView.doubleClicked.connect(self.source_code_tree_clicked)

        # context menu
        self.ui.sourceCodeTreeView.customContextMenuRequested.connect(self.show_source_code_tree_context_menu)

        # Set context menu policy to CustomContextMenu
        self.ui.sourceCodeTreeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def reset_console(self):
        """
        Reset console
        :return:
        """
        self.interpreter = InteractiveConsole(locals=globals())
        self.add_console_vars()

    def add_console_vars(self):
        """
        Add vars to the console
        :return:
        """
        self.interpreter.locals["hlp"] = self.print_console_help
        self.interpreter.locals["np"] = np
        self.interpreter.locals["pd"] = pd
        self.interpreter.locals["plt"] = plt
        self.interpreter.locals["clc"] = self.clear_console
        self.interpreter.locals['app'] = self
        self.interpreter.locals['circuit'] = self.circuit
        self.interpreter.locals['user_folder'] = get_create_gridcal_folder

    def print_console_help(self):

        self.append_output("")
        self.append_output('GridCal internal commands.\n')
        self.append_output('If a command is unavailable is because the study has not been executed yet.')

        self.append_output('\n\nclc():\tclear the console.')

        self.append_output('\n\nApp functions:')
        self.append_output('\tapp.new_project(): Clear all.')
        self.append_output('\tapp.open_file(): Prompt to load GridCal compatible file')
        self.append_output('\tapp.save_file(): Prompt to save GridCal file')
        self.append_output('\tapp.export_diagram(): Prompt to export the diagram in png.')
        self.append_output('\tapp.create_schematic_from_api(): Create the schematic from the circuit information.')
        self.append_output('\tapp.adjust_all_node_width(): Adjust the width of all the nodes according to their name.')
        self.append_output('\tapp.numerical_circuit: get compilation of the assets.')
        self.append_output('\tapp.islands: get compilation of the assets split into the topological islands.')

        self.append_output('\n\nCircuit functions:')
        self.append_output('\tapp.circuit.plot_graph(): Plot a graph in a Matplotlib window. Call plt.show() after.')

        self.append_output('\n\nPower flow results:')
        self.append_output('\tapp.session.power_flow.voltage:\t the nodal voltages in per unit')
        self.append_output('\tapp.session.power_flow.current:\t the branch currents in per unit')
        self.append_output('\tapp.session.power_flow.loading:\t the branch loading in %')
        self.append_output('\tapp.session.power_flow.losses:\t the branch losses in per unit')
        self.append_output('\tapp.session.power_flow.power:\t the nodal power Injections in per unit')
        self.append_output('\tapp.session.power_flow.Sf:\t the branch power Injections in per unit at the "from" side')
        self.append_output('\tapp.session.power_flow.St:\t the branch power Injections in per unit at the "to" side')

        self.append_output('\n\nShort circuit results:')
        self.append_output('\tapp.session.short_circuit.voltage:\t the nodal voltages in per unit')
        self.append_output('\tapp.session.short_circuit.current:\t the branch currents in per unit')
        self.append_output('\tapp.session.short_circuit.loading:\t the branch loading in %')
        self.append_output('\tapp.session.short_circuit.losses:\t the branch losses in per unit')
        self.append_output('\tapp.session.short_circuit.power:\t the nodal power Injections in per unit')
        self.append_output('\tapp.session.short_circuit.power_from:\t the branch power Injections in per unit at the "from" side')
        self.append_output('\tapp.session.short_circuit.power_to:\t the branch power Injections in per unit at the "to" side')
        self.append_output('\tapp.session.short_circuit.short_circuit_power:\t Short circuit power in MVA of the grid nodes')

        self.append_output('\n\nOptimal power flow results:')
        self.append_output('\tapp.session.optimal_power_flow.voltage:\t the nodal voltages angles in rad')
        self.append_output('\tapp.session.optimal_power_flow.load_shedding:\t the branch loading in %')
        self.append_output('\tapp.session.optimal_power_flow.losses:\t the branch losses in per unit')
        self.append_output('\tapp.session.optimal_power_flow.Sbus:\t the nodal power Injections in MW')
        self.append_output('\tapp.session.optimal_power_flow.Sf:\t the branch power Sf')

        self.append_output('\n\nTime series power flow results:')
        self.append_output('\tapp.session.power_flow_ts.time:\t Profiles time index (pandas DateTimeIndex object)')
        self.append_output('\tapp.session.power_flow_ts.load_profiles:\t Load profiles matrix (row: time, col: node)')
        self.append_output('\tapp.session.power_flow_ts.gen_profiles:\t Generation profiles matrix (row: time, col: node)')
        self.append_output('\tapp.session.power_flow_ts.voltages:\t nodal voltages results matrix (row: time, col: node)')
        self.append_output('\tapp.session.power_flow_ts.currents:\t Branches currents results matrix (row: time, col: branch)')
        self.append_output('\tapp.session.power_flow_ts.loadings:\t Branches loadings results matrix (row: time, col: branch)')
        self.append_output('\tapp.session.power_flow_ts.losses:\t Branches losses results matrix (row: time, col: branch)')

        self.append_output('\n\nVoltage stability power flow results:')
        self.append_output('\tapp.session.continuation_power_flow.voltage:\t Voltage values for every power multiplication factor.')
        self.append_output('\tapp.session.continuation_power_flow.lambda:\t Value of power multiplication factor applied')
        self.append_output('\tapp.session.continuation_power_flow.Sf:\t Power values for every power multiplication factor.')

        self.append_output('\n\nMonte Carlo power flow results:')
        self.append_output('\tapp.session.stochastic_power_flow.V_avg:\t nodal voltage average result.')
        self.append_output('\tapp.session.stochastic_power_flow.I_avg:\t branch current average result.')
        self.append_output('\tapp.session.stochastic_power_flow.Loading_avg:\t branch loading average result.')
        self.append_output('\tapp.session.stochastic_power_flow.Losses_avg:\t branch losses average result.')
        self.append_output('\tapp.session.stochastic_power_flow.V_std:\t nodal voltage standard deviation result.')
        self.append_output('\tapp.session.stochastic_power_flow.I_std:\t branch current standard deviation result.')
        self.append_output('\tapp.session.stochastic_power_flow.Loading_std:\t branch loading standard deviation result.')
        self.append_output('\tapp.session.stochastic_power_flow.Losses_std:\t branch losses standard deviation result.')
        self.append_output('\tapp.session.stochastic_power_flow.V_avg_series:\t nodal voltage average series.')
        self.append_output('\tapp.session.stochastic_power_flow.V_std_series:\t branch current standard deviation series.')
        self.append_output('\tapp.session.stochastic_power_flow.error_series:\t Monte Carlo error series (the convergence value).')
        self.append_output('The same for app.latin_hypercube_sampling')

    def setup_intellisense(self):
        """

        :return:
        """
        # Gather names from builtins and globals
        keywords = set(dir(builtins)) | set(globals().keys())

        self.completer.setModel(QtCore.QStringListModel(sorted(keywords)))
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setWidget(self.ui.consoleInputTextEdit)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent):
        """
        Event filter to capture Ctrl + Enter
        :param watched:
        :param event:
        :return:
        """
        if watched == self.ui.consoleInputTextEdit and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.run_command()
                return True

        elif watched == self.ui.sourceCodeTextEdit and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.run_source_code()
                return True

        return super().eventFilter(watched, event)

    def execute_command(self, command: str, silent: bool = False):
        """
        Run a command
        :param command: Python command to run
        :param silent: Silent mode
        """

        if not silent:
            self.append_output(f">>> {command}")

        try:

            if silent:
                ret = self.interpreter.runcode(command)
            else:
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = io.StringIO()
                sys.stderr = io.StringIO()

                ret = self.interpreter.runcode(command)

                stdout_output = sys.stdout.getvalue()
                stderr_output = sys.stderr.getvalue()
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                if stdout_output:
                    self.append_output(stdout_output)
                if stderr_output:
                    self.append_output(stderr_output)

                if ret:
                    self.append_output(str(ret))

        except Exception as e:
            self.append_output(str(e))

    def run_command(self):
        """
        Run command
        :return:
        """
        command = self.ui.consoleInputTextEdit.toPlainText()
        self.ui.consoleInputTextEdit.clear()
        self.execute_command(command)

    def append_output(self, text: str):
        """
        Add some text to the output
        :param text: text to append
        """
        self.ui.consoleOutputTextEdit.append(text)

    def clear_console(self):
        """
        Clear console output
        """
        self.ui.consoleOutputTextEdit.clear()

    def run_source_code(self):
        """
        Run the source code in the IPython console
        """
        code_source = self.ui.sourceCodeTextEdit.toPlainText()

        if code_source[-1] != '\n':
            code_source += "\n"

        self.execute_command(code_source)

    def source_code_tree_clicked(self, index):
        """
        On double click on a source code tree item, load the source code
        """
        pth = self.python_fs_model.filePath(index)

        if os.path.exists(pth):
            with open(pth, 'r') as f:
                txt = "\n".join(line.rstrip() for line in f)
                self.ui.sourceCodeTextEdit.setPlainText(txt)

            name = os.path.basename(pth)
            self.ui.sourceCodeNameLineEdit.setText(name.replace('.py', ''))
        else:
            error_msg(pth + ' does not exists :/', 'Open script')

    def clear_source_code(self):
        """
        Clear source code
        """
        ok = yes_no_question(text='Are you sure you want to clear source code?',
                             title='Clear Source Code')

        if ok:
            self.ui.sourceCodeNameLineEdit.setText("")
            self.ui.sourceCodeTextEdit.setPlainText("")

    def save_source_code(self):
        """
        Save the source code
        """
        name = self.ui.sourceCodeNameLineEdit.text().strip()

        if name != '':
            fname = name + '.py'
            pth = os.path.join(scripts_path(), fname)
            with open(pth, 'w') as f:
                f.write(self.ui.sourceCodeTextEdit.toPlainText())
        else:
            error_msg("Please enter a name for the script", title="Save script")

    def delete_source_code(self):
        """
        Delete the selected file
        """
        index = self.ui.sourceCodeTreeView.currentIndex()
        pth = self.python_fs_model.filePath(index)
        if os.path.exists(pth):
            ok = yes_no_question(text="Do you want to delete {}?".format(pth), title="Delete source code file")

            if ok:
                os.remove(pth)
        else:
            error_msg(pth + ' does not exists :/', "Delete source code file")

    def show_source_code_tree_context_menu(self, pos: QtCore.QPoint):
        """
        Show source code tree view context menu
        :param pos: Relative click position
        """
        context_menu = QtWidgets.QMenu(parent=self.ui.diagramsListView)

        gf.add_menu_entry(menu=context_menu,
                          text="Delete",
                          icon_path=":/Icons/icons/delete.svg",
                          function_ptr=self.delete_source_code)

        # Convert global position to local position of the list widget
        mapped_pos = self.ui.sourceCodeTreeView.viewport().mapToGlobal(pos)
        context_menu.exec(mapped_pos)
