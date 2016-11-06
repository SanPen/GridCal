import sys
import xlrd

from PyQt4 import QtCore, QtGui
try:
    from excel_sheet_selection import *
except:
    from .excel_sheet_selection import *


class ExcelDialog(QtGui.QDialog):

    def __init__(self, parent=None, excel_file=None):
        QtGui.QDialog.__init__(self, parent)
        self.ui = Ui_ExcelSelectionDialog()
        self.ui.setupUi(self)

        self.excel_sheet = None

        if excel_file is not None:
            xls = xlrd.open_workbook(excel_file, on_demand=True)
            self.sheet_names = xls.sheet_names()
            self.ui.sheets_list.addItems(self.sheet_names)

        # click
        QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL('accepted()'), self.accepted)
        QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL('rejected()'), self.rejected)

    def accepted(self):
        if len(self.ui.sheets_list.selectedIndexes()):
            self.excel_sheet = self.ui.sheets_list.selectedIndexes()[0].row()
        print('self.excel_sheet: ', self.excel_sheet)


    def rejected(self):
        print('self.excel_sheet: ', self.excel_sheet)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = ExcelDialog()
    window.show()
    sys.exit(app.exec_())