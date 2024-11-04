# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
from PySide6.QtGui import QFont, QFontMetrics, Qt
from PySide6 import QtWidgets, QtCore
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
        self.ui.sourceCodeTextEdit.setFont(font)

        # Set tab width to 4 spaces
        font_metrics = QFontMetrics(font)
        tab_stop_width = font_metrics.horizontalAdvance(' ' * 4)  # Width of 4 spaces in the selected font
        self.ui.sourceCodeTextEdit.setTabStopDistance(tab_stop_width)

        self.ui.sourceCodeTextEdit.highlighter = PythonHighlighter(self.ui.sourceCodeTextEdit.document())

        # scripts tree view
        self.python_fs_model = CustomFileSystemModel(root_path=scripts_path(), ext_filter=['*.py'])
        self.ui.sourceCodeTreeView.setModel(self.python_fs_model)
        self.ui.sourceCodeTreeView.setRootIndex(self.python_fs_model.index(scripts_path()))

        # actions ------------------------------------------------------------------------------------------------------
        self.ui.actionReset_console.triggered.connect(self.create_console)

        # buttonclicks -------------------------------------------------------------------------------------------------
        self.ui.runSourceCodeButton.clicked.connect(self.run_source_code)
        self.ui.saveSourceCodeButton.clicked.connect(self.save_source_code)
        self.ui.clearSourceCodeButton.clicked.connect(self.clear_source_code)

        # double clicked -----------------------------------------------------------------------------------------------
        self.ui.sourceCodeTreeView.doubleClicked.connect(self.source_code_tree_clicked)

        # context menu
        self.ui.sourceCodeTreeView.customContextMenuRequested.connect(self.show_source_code_tree_context_menu)

        # Set context menu policy to CustomContextMenu
        self.ui.sourceCodeTreeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

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
