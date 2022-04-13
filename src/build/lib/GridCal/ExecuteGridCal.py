# This file is part of GridCal.g
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
print('Loading GridCal...')
import os
import sys
import matplotlib
# matplotlib.use('Qt5Agg')
PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))
from GridCal.__version__ import about_msg
from GridCal.Gui.Main.GridCalMain import run
from GridCal.Gui.Main.banner import Ui_splashScreen, QMainWindow, Qt, QApplication
import platform

if platform.system() == 'Windows':
    # this makes the icon display properly under windows
    import ctypes
    myappid = 'mycompany.myproduct.subproduct.version'  # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


class Splash(QMainWindow):

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        QMainWindow.__init__(self, parent)
        self.ui = Ui_splashScreen()
        self.ui.setupUi(self)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)


if __name__ == "__main__":
    print(about_msg)

    # app = QApplication(sys.argv)
    # app.setStyle('Fusion')  # ['Breeze', 'Oxygen', 'QtCurve', 'Windows', 'Fusion']
    #
    # splash = Splash()
    # splash.show()

    run(use_native_dialogues=False)
    # sys.exit(app.exec_())
