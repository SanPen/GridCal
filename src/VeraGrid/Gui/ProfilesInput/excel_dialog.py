# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import sys
import openpyxl

from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.ProfilesInput.excel_sheet_selection import Ui_ExcelSelectionDialog


class ExcelDialog(QtWidgets.QDialog):

    def __init__(self, parent=None, excel_file=None):
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_ExcelSelectionDialog()
        self.ui.setupUi(self)

        self.excel_sheet = None

        if excel_file is not None:
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            self.sheet_names = wb.sheetnames
            self.ui.sheets_list.addItems(self.sheet_names)

        # click
        self.ui.buttonBox.accepted.connect(self.accepted_action)
        self.ui.buttonBox.rejected.connect(self.rejected_action)
        self.ui.sheets_list.doubleClicked.connect(self.accepted_action)

    def accepted_action(self):
        if len(self.ui.sheets_list.selectedIndexes()):
            self.excel_sheet = self.ui.sheets_list.selectedIndexes()[0].row()
        self.close()

    def rejected_action(self):
        self.close()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = ExcelDialog()
    window.show()
    sys.exit(app.exec())