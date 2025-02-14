# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os.path
import sys

# import qdarktheme
from PySide6 import QtWidgets, QtGui

from GridCal.Gui.Main.MainWindow import QApplication
from GridCal.Gui.Main.SubClasses.Scripting.scripting import ScriptingMain
import GridCal.ThirdParty.qdarktheme as qdarktheme
from GridCal.__version__ import __GridCal_VERSION__

__author__ = 'Santiago Peñate Vera'

"""
This class is the handler of the main gui of GridCal.
"""


########################################################################################################################
# Main Window
########################################################################################################################

class GridCalMainGUI(ScriptingMain):
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

        self.load_all_config()

        self.add_complete_bus_branch_diagram()
        #self.add_map_diagram(ask=False)
        self.set_diagram_widget(self.diagram_widgets_list[0])
        self.update_available_results()

    def save_all_config(self) -> None:
        """
        Save all configuration files needed
        """
        self.save_gui_config()
        self.save_server_config()

    def load_all_config(self) -> None:
        """
        Load all configuration files needed
        """
        self.load_gui_config()
        self.load_server_config()
        self.add_plugins()

        # apply the theme selected by the settings
        self.change_theme_mode()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
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
                self.save_all_config()
                self.stop_all_threads()
                event.accept()
            else:
                # save config regardless
                self.save_all_config()
                event.ignore()
        else:
            # no buses so exit
            # save config regardless
            self.save_all_config()
            self.stop_all_threads()
            event.accept()


def runGridCal() -> None:
    """
    Main function to run the GUI
    :return:
    """
    # if hasattr(qdarktheme, 'enable_hi_dpi'):
    qdarktheme.enable_hi_dpi()

    app = QApplication(sys.argv)
    # app.setStyle('Fusion')  # ['Breeze', 'Oxygen', 'QtCurve', 'Windows', 'Fusion']

    window_ = GridCalMainGUI()

    # process the argument if provided
    if len(sys.argv) > 1:
        f_name = sys.argv[1]
        if os.path.exists(f_name):
            window_.open_file_now(filenames=[f_name])

    # launch
    h_ = 780
    window_.resize(int(1.7 * h_), h_)  # almost the golden ratio :)
    window_.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    runGridCal()
