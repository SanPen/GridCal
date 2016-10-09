# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'excel_sheet_selection.ui'
#
# Created: Tue Dec 29 15:28:34 2015
#      by: PyQt4 UI code generator 4.10.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_ExcelSelectionDialog(object):
    def setupUi(self, ExcelSelectionDialog):
        ExcelSelectionDialog.setObjectName(_fromUtf8("ExcelSelectionDialog"))
        ExcelSelectionDialog.resize(272, 229)
        ExcelSelectionDialog.setMaximumSize(QtCore.QSize(272, 229))
        ExcelSelectionDialog.setModal(True)
        self.verticalLayout = QtGui.QVBoxLayout(ExcelSelectionDialog)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.sheets_list = QtGui.QListWidget(ExcelSelectionDialog)
        self.sheets_list.setFrameShape(QtGui.QFrame.StyledPanel)
        self.sheets_list.setObjectName(_fromUtf8("sheets_list"))
        self.verticalLayout.addWidget(self.sheets_list)
        self.buttonBox = QtGui.QDialogButtonBox(ExcelSelectionDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(ExcelSelectionDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("accepted()")), ExcelSelectionDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("rejected()")), ExcelSelectionDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(ExcelSelectionDialog)

    def retranslateUi(self, ExcelSelectionDialog):
        ExcelSelectionDialog.setWindowTitle(_translate("ExcelSelectionDialog", "Excel sheet selection", None))


if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    ExcelSelectionDialog = QtGui.QDialog()
    ui = Ui_ExcelSelectionDialog()
    ui.setupUi(ExcelSelectionDialog)
    ExcelSelectionDialog.show()
    sys.exit(app.exec_())

