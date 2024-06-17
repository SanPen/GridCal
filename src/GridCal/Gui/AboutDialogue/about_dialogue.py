import os
import sys
import chardet
import subprocess
from PySide6 import QtWidgets
from typing import List
from GridCal.Gui.AboutDialogue.gui import Ui_AboutDialog
from GridCal.__version__ import __GridCal_VERSION__, contributors_msg, copyright_msg
from GridCal.update import check_version, get_upgrade_command
from GridCalEngine.__version__ import __GridCalEngine_VERSION__
from GridCalEngine.Compilers.circuit_to_newton_pa import (NEWTON_PA_AVAILABLE,
                                                          NEWTON_PA_RECOMMENDED_VERSION,
                                                          NEWTON_PA_VERSION)
from GridCalEngine.Compilers.circuit_to_bentayga import (BENTAYGA_AVAILABLE,
                                                         BENTAYGA_RECOMMENDED_VERSION,
                                                         BENTAYGA_VERSION)
from GridCalEngine.Compilers.circuit_to_pgm import (PGM_AVAILABLE,
                                                    PGM_RECOMMENDED_VERSION,
                                                    PGM_VERSION)


class AboutDialogueGuiGUI(QtWidgets.QDialog):
    """
    AboutDialogueGuiGUI
    """
    def __init__(self, parent=None):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_AboutDialog()
        self.ui.setupUi(self)
        self.setWindowTitle('About GridCal')
        self.setAcceptDrops(True)

        self.ui.librariesTableWidget.setColumnCount(4)
        self.ui.librariesTableWidget.setRowCount(4)
        self.ui.librariesTableWidget.setHorizontalHeaderLabels(["Name", "version", "supported version", "licensed"])

        self.ui.librariesTableWidget.setItem(0, 0, QtWidgets.QTableWidgetItem("GridCal"))
        self.ui.librariesTableWidget.setItem(0, 1, QtWidgets.QTableWidgetItem(__GridCal_VERSION__))
        self.ui.librariesTableWidget.setItem(0, 2, QtWidgets.QTableWidgetItem(__GridCalEngine_VERSION__))
        self.ui.librariesTableWidget.setItem(0, 3, QtWidgets.QTableWidgetItem("True"))

        self.ui.librariesTableWidget.setItem(1, 0, QtWidgets.QTableWidgetItem("NewtonPa"))
        self.ui.librariesTableWidget.setItem(1, 1, QtWidgets.QTableWidgetItem(NEWTON_PA_VERSION
                                                                              if NEWTON_PA_AVAILABLE else
                                                                              "Not installed"))
        self.ui.librariesTableWidget.setItem(1, 2, QtWidgets.QTableWidgetItem(NEWTON_PA_RECOMMENDED_VERSION))
        self.ui.librariesTableWidget.setItem(1, 3, QtWidgets.QTableWidgetItem(str(NEWTON_PA_AVAILABLE)))

        self.ui.librariesTableWidget.setItem(2, 0, QtWidgets.QTableWidgetItem("Bentayga"))
        self.ui.librariesTableWidget.setItem(2, 1, QtWidgets.QTableWidgetItem(BENTAYGA_VERSION
                                                                              if BENTAYGA_AVAILABLE else
                                                                              "Not installed"))
        self.ui.librariesTableWidget.setItem(2, 2, QtWidgets.QTableWidgetItem(BENTAYGA_RECOMMENDED_VERSION))
        self.ui.librariesTableWidget.setItem(2, 3, QtWidgets.QTableWidgetItem(str(BENTAYGA_AVAILABLE)))

        self.ui.librariesTableWidget.setItem(3, 0, QtWidgets.QTableWidgetItem("power-grid-model"))
        self.ui.librariesTableWidget.setItem(3, 1, QtWidgets.QTableWidgetItem(PGM_VERSION
                                                                              if PGM_AVAILABLE else
                                                                              "Not installed"))
        self.ui.librariesTableWidget.setItem(3, 2, QtWidgets.QTableWidgetItem(PGM_RECOMMENDED_VERSION))
        self.ui.librariesTableWidget.setItem(3, 3, QtWidgets.QTableWidgetItem(str(PGM_AVAILABLE)))

        # check the version in pypi
        version_code, latest_version = check_version()

        self.upgrade_cmd: List[str] = ['']

        if version_code == 1:
            addendum = '\nThere is a newer version: ' + latest_version

            self.upgrade_cmd = get_upgrade_command(latest_version)
            command = ' '.join(self.upgrade_cmd)
            self.ui.updateLabel.setText('\n\nTerminal command to update:\n\n' + command)
            self.ui.updateButton.setVisible(True)

        elif version_code == -1:
            addendum = '\nThis version is newer than the version available in the repositories (' + latest_version + ')'
            self.ui.updateLabel.setText(addendum)
            self.ui.updateButton.setVisible(False)

        elif version_code == 0:
            addendum = '\nGridCal is up to date.'
            self.ui.updateLabel.setText(addendum)
            self.ui.updateButton.setVisible(False)

        elif version_code == -2:
            addendum = '\nIt was impossible to check for a newer version'
            self.ui.updateLabel.setText(addendum)
            self.ui.updateButton.setVisible(False)

        else:
            addendum = ''
            self.ui.updateLabel.setText(addendum)
            self.ui.updateButton.setVisible(False)

        # self.ui.mainLabel.setText(about_msg)
        self.ui.versionLabel.setText('GridCal version: ' + __GridCal_VERSION__ + ', ' + addendum)
        self.ui.copyrightLabel.setText(copyright_msg)
        self.ui.contributorsLabel.setText(contributors_msg)

        # click
        self.ui.updateButton.clicked.connect(self.update)

        self.show_license()

    def msg(self, text, title="Warning"):
        """
        Message box
        :param text: Text to display
        :param title: Name of the window
        """
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        retval = msg.exec_()

    def update(self):
        """
        Upgrade GridCal
        :return:
        """
        list_files = subprocess.run(self.upgrade_cmd,
                                    stdout=subprocess.PIPE,
                                    text=True,
                                    input="Hello from the other side")  # upgrade_cmd is a list already
        if list_files.returncode != 0:
            self.msg("The exit code was: %d" % list_files.returncode)
        else:
            self.msg('GridCal updated successfully')

    def show_license(self):
        """
        Show the license
        """
        here = os.path.abspath(os.path.dirname(__file__))
        license_file = os.path.join(here, '..', '..', 'LICENSE.txt')

        # make a guess of the file encoding
        detection = chardet.detect(open(license_file, "rb").read())

        with open(license_file, 'r', encoding=detection['encoding']) as file:
            license_txt = file.read()

        self.ui.licenseTextEdit.setPlainText(license_txt)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = AboutDialogueGuiGUI()
    # window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())
