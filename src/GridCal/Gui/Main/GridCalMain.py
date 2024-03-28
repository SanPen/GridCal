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
import os.path
import sys

import qdarktheme
from PySide6 import QtWidgets

from GridCal.Gui.Main.MainWindow import QApplication
from GridCal.Gui.Main.SubClasses.Scripting.scripting import ScriptingMain
from GridCal.__version__ import __GridCal_VERSION__

__author__ = 'Santiago Peñate Vera'

"""
This class is the handler of the main gui of GridCal.
"""


########################################################################################################################
# Main Window
########################################################################################################################

class MainGUI(ScriptingMain):
    """
    MainGUI
    """

    def __init__(self) -> None:
        """
        Main constructor
        """

        # create main window
        ScriptingMain.__init__(self, parent=None)
        self.setWindowTitle('GridCal ' + __GridCal_VERSION__)
        self.setAcceptDrops(True)

        ################################################################################################################
        # Set splitters
        ################################################################################################################

        # 1:4
        self.ui.dataStructuresSplitter.setStretchFactor(0, 3)
        self.ui.dataStructuresSplitter.setStretchFactor(1, 4)

        self.ui.simulationDataSplitter.setStretchFactor(1, 15)

        self.ui.results_splitter.setStretchFactor(0, 2)
        self.ui.results_splitter.setStretchFactor(1, 4)

        self.ui.diagram_selection_splitter.setStretchFactor(0, 10)
        self.ui.diagram_selection_splitter.setStretchFactor(1, 2)

        ################################################################################################################
        # Other actions
        ################################################################################################################

        self.ui.grid_colouring_frame.setVisible(True)

        self.ui.actionSync.setVisible(False)

        self.modify_ui_options_according_to_the_engine()

        # this is the contingency planner tab, invisible until done
        self.ui.tabWidget_3.setTabVisible(4, True)

        self.clear_results()

        self.load_gui_config()

        self.add_complete_bus_branch_diagram()
        self.add_map_diagram()
        self.set_diagram_widget(self.diagram_widgets_list[0])

    def closeEvent(self, event):
        """
        Close event
        :param event:
        :return:
        """
        if self.circuit.get_bus_number() > 0:
            quit_msg = "Are you sure that you want to exit GridCal?"
            reply = QtWidgets.QMessageBox.question(self, 'Close', quit_msg,
                                                   QtWidgets.QMessageBox.StandardButton.Yes,
                                                   QtWidgets.QMessageBox.StandardButton.No)

            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                # save config regardless
                self.save_gui_config()
                self.stop_all_threads()
                event.accept()
            else:
                # save config regardless
                self.save_gui_config()
                event.ignore()
        else:
            # no buses so exit
            # save config regardless
            self.save_gui_config()
            self.stop_all_threads()
            event.accept()


def runGridCal() -> None:
    """
    Main function to run the GUI
    :return:
    """
    qdarktheme.enable_hi_dpi()
    app = QApplication(sys.argv)
    # app.setStyle('Fusion')  # ['Breeze', 'Oxygen', 'QtCurve', 'Windows', 'Fusion']

    window_ = MainGUI()

    # process the argument if provided
    if len(sys.argv) > 1:
        f_name = sys.argv[1]
        if os.path.exists(f_name):
            window_.open_file_now(filenames=[f_name])

    # launch
    h_ = 780
    window_.resize(int(1.7 * h_), h_)  # almost the golden ratio :)
    window_.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    runGridCal()
