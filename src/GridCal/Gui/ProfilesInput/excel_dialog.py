import sys
import openpyxl

from PySide2 import QtCore, QtGui, QtWidgets

from GridCal.Gui.ProfilesInput.excel_sheet_selection import *


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
        print('Accepted: self.excel_sheet: ', self.excel_sheet)
        self.close()

    def rejected_action(self):
        print('Rejected: self.excel_sheet: ', self.excel_sheet)
        self.close()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = ExcelDialog()
    window.show()
    sys.exit(app.exec_())