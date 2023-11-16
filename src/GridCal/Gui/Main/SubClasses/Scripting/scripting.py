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
import os
import numpy as np
import pandas as pd
from typing import Union
from matplotlib import pyplot as plt
import datetime as dtelib
from PySide6.QtGui import QFont, QFontMetrics
from GridCal.Gui.Main.SubClasses.io import IoMain
from GridCal.Gui.Main.SubClasses.Scripting.python_highlighter import PythonHighlighter
from GridCal.Gui.GeneralDialogues import clear_qt_layout
from GridCal.Gui.GuiFunctions import CustomFileSystemModel
from GridCal.Gui.messages import error_msg, yes_no_question

try:
    from GridCal.Gui.ConsoleWidget import ConsoleWidget

    qt_console_available = True
except ModuleNotFoundError:
    print('No qtconsole available')
    qt_console_available = False


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

        # Console
        self.console: Union[ConsoleWidget, None] = None
        try:
            self.create_console()
        except TypeError:
            error_msg('The console has failed because the QtConsole guys have a bug in their package :(')

        # Source code text ---------------------------------------------------------------------------------------------
        # Set the font for your widget
        font = QFont("Consolas", 10)  # Replace "Consolas" with your preferred monospaced font
        self.ui.sourceCodeTextEdit.setFont(font)

        # Set tab width to 4 spaces
        font_metrics = QFontMetrics(font)
        tab_stop_width = font_metrics.horizontalAdvance(' ' * 4)  # Width of 4 spaces in the selected font
        self.ui.sourceCodeTextEdit.setTabStopDistance(tab_stop_width)

        self.ui.sourceCodeTextEdit.highlighter = PythonHighlighter(self.ui.sourceCodeTextEdit.document())

        # tree view
        root_path = self.scripts_path()
        self.python_fs_model = CustomFileSystemModel(root_path=self.scripts_path(), ext_filter=['*.py'])
        self.ui.sourceCodeTreeView.setModel(self.python_fs_model)
        self.ui.sourceCodeTreeView.setRootIndex(self.python_fs_model.index(root_path))

        # actions ------------------------------------------------------------------------------------------------------
        self.ui.actionReset_console.triggered.connect(self.create_console)

        # buttonclicks -------------------------------------------------------------------------------------------------
        self.ui.runSourceCodeButton.clicked.connect(self.run_source_code)
        self.ui.saveSourceCodeButton.clicked.connect(self.save_source_code)
        self.ui.deleteSourceCodeFileButton.clicked.connect(self.delete_source_code)

        # double clicked -----------------------------------------------------------------------------------------------
        self.ui.sourceCodeTreeView.doubleClicked.connect(self.source_code_tree_clicked)

    def create_console(self) -> None:
        """
        Create console
        """
        if qt_console_available:
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

    def console_msg(self, *msg_):
        """
        Print some message in the console.

        Arguments:

            **msg_** (str): Message

        """
        dte = dtelib.datetime.now().strftime("%b %d %Y %H:%M:%S")

        txt = self.ui.outputTextEdit.toPlainText()

        for e in msg_:
            if isinstance(e, list):
                txt += '\n' + dte + '->\n'
                for elm in e:
                    txt += str(elm) + "\n"
            else:
                txt += '\n' + dte + '->'
                txt += " " + str(e)

        self.ui.outputTextEdit.setPlainText(txt)

    def run_source_code(self):
        """
        Run the source code in the IPython console
        """
        code = self.ui.sourceCodeTextEdit.toPlainText()

        if code[-1] != '\n':
            code += "\n"

        self.console.execute_command(code)

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

    def save_source_code(self):
        """
        Save the source code
        """
        name = self.ui.sourceCodeNameLineEdit.text().strip()

        if name != '':
            fname = name + '.py'
            pth = os.path.join(self.scripts_path(), fname)
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
