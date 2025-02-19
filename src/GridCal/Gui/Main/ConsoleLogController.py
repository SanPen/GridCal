# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


import sys

from PySide6 import QtWidgets

from GridCal.Gui.Main.ConsoleLog import Ui_mainWindow


class ConsoleLogDialogue(QtWidgets.QMainWindow):

    def __init__(self, parent=None, tower=None, wires_catalogue=list()):
        """
        Constructor
        Args:
            parent:
        """
        QtWidgets.QMainWindow.__init__(self, parent)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Line builder')


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = ConsoleLogDialogue()

    window.resize(int(1.61 * 400.0), 400)  # golden ratio
    window.show()
    sys.exit(app.exec())
