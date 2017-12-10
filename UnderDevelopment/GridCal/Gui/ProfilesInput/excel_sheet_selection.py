# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'excel_sheet_selection.ui'
#
# Created by: PyQt5 UI code generator 5.9
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_ExcelSelectionDialog(object):
    def setupUi(self, ExcelSelectionDialog):
        ExcelSelectionDialog.setObjectName("ExcelSelectionDialog")
        ExcelSelectionDialog.resize(272, 229)
        ExcelSelectionDialog.setMaximumSize(QtCore.QSize(272, 229))
        ExcelSelectionDialog.setModal(True)
        self.verticalLayout = QtWidgets.QVBoxLayout(ExcelSelectionDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.sheets_list = QtWidgets.QListWidget(ExcelSelectionDialog)
        self.sheets_list.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.sheets_list.setObjectName("sheets_list")
        self.verticalLayout.addWidget(self.sheets_list)
        self.buttonBox = QtWidgets.QDialogButtonBox(ExcelSelectionDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(ExcelSelectionDialog)
        self.buttonBox.accepted.connect(ExcelSelectionDialog.accept)
        self.buttonBox.rejected.connect(ExcelSelectionDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(ExcelSelectionDialog)

    def retranslateUi(self, ExcelSelectionDialog):
        _translate = QtCore.QCoreApplication.translate
        ExcelSelectionDialog.setWindowTitle(_translate("ExcelSelectionDialog", "Excel sheet selection"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    ExcelSelectionDialog = QtWidgets.QDialog()
    ui = Ui_ExcelSelectionDialog()
    ui.setupUi(ExcelSelectionDialog)
    ExcelSelectionDialog.show()
    sys.exit(app.exec_())

