# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import sys

from PySide2 import QtWidgets

from GridCal.Gui.Main.ConsoleLog import *


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
    sys.exit(app.exec_())
