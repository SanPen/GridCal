# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import io
import sys

from PySide6.QtGui import QFont, QFontMetrics, Qt
from PySide6 import QtWidgets, QtCore

from GridCalEngine.IO.file_system import scripts_path
from GridCal.Gui.Main.SubClasses.io import IoMain
from GridCal.Gui.python_highlighter import PythonHighlighter
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


        # Source code
        self.ui.sourceCodeTextEdit.setFont(font)
        font_metrics = QFontMetrics(font)  # Set tab width to 4 spaces
        tab_stop_width = font_metrics.horizontalAdvance(' ' * 4)  # Width of 4 spaces in the selected font
        self.ui.sourceCodeTextEdit.setTabStopDistance(tab_stop_width)
        self.ui.sourceCodeTextEdit.highlighter = PythonHighlighter(self.ui.sourceCodeTextEdit.document())
        self.ui.sourceCodeTextEdit.setPlaceholderText("Enter or load Python code here\nType Ctrl + Enter to run")
        self.ui.sourceCodeTextEdit.installEventFilter(self)  # Install event filter to handle Ctrl+Enter

        self.add_console_vars()

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
        self.ui.clearConsoleButton.clicked.connect(self.clear_console)

        # double clicked -----------------------------------------------------------------------------------------------
        self.ui.sourceCodeTreeView.doubleClicked.connect(self.source_code_tree_clicked)

        # context menu
        self.ui.sourceCodeTreeView.customContextMenuRequested.connect(self.show_source_code_tree_context_menu)

        # Set context menu policy to CustomContextMenu
        self.ui.sourceCodeTreeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)




    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent):
        """
        Event filter to capture Ctrl + Enter
        :param watched:
        :param event:
        :return:
        """

        if watched == self.ui.sourceCodeTextEdit and event.type() == QtCore.QEvent.Type.KeyPress:
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

    def append_output(self, text: str):
        """
        Add some text to the output
        :param text: text to append
        """
        self.console.append_output(text)

    def run_source_code(self):
        """
        Run the source code in the IPython console
        """
        source_code = self.ui.sourceCodeTextEdit.toPlainText()

        if source_code[-1] != '\n':
            source_code += "\n"

        self.console.execute(source_code)
        self.console.append_output(">>> ")

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
