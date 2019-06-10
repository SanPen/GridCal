# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'SmartSearch.ui',
# licensing of 'SmartSearch.ui' applies.
#
# Created: Mon Jun 10 21:53:16 2019
#      by: pyside2-uic  running on PySide2 5.12.3
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore, QtGui, QtWidgets

class Ui_SmartSearch(object):
    def setupUi(self, SmartSearch):
        SmartSearch.setObjectName("SmartSearch")
        SmartSearch.resize(692, 346)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/Icons/icons/magnifying_glass.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        SmartSearch.setWindowIcon(icon)
        self.verticalLayout = QtWidgets.QVBoxLayout(SmartSearch)
        self.verticalLayout.setObjectName("verticalLayout")
        self.frame = QtWidgets.QFrame(SmartSearch)
        self.frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame.setObjectName("frame")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.frame)
        self.horizontalLayout.setSpacing(6)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.property_comboBox = QtWidgets.QComboBox(self.frame)
        self.property_comboBox.setMinimumSize(QtCore.QSize(200, 0))
        self.property_comboBox.setObjectName("property_comboBox")
        self.horizontalLayout.addWidget(self.property_comboBox)
        self.lineEdit = QtWidgets.QLineEdit(self.frame)
        self.lineEdit.setMinimumSize(QtCore.QSize(200, 0))
        self.lineEdit.setObjectName("lineEdit")
        self.horizontalLayout.addWidget(self.lineEdit)
        self.filter_pushButton = QtWidgets.QPushButton(self.frame)
        self.filter_pushButton.setText("")
        self.filter_pushButton.setIcon(icon)
        self.filter_pushButton.setObjectName("filter_pushButton")
        self.horizontalLayout.addWidget(self.filter_pushButton)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.delete_pushButton = QtWidgets.QPushButton(self.frame)
        self.delete_pushButton.setText("")
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/Icons/icons/delete.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.delete_pushButton.setIcon(icon1)
        self.delete_pushButton.setObjectName("delete_pushButton")
        self.horizontalLayout.addWidget(self.delete_pushButton)
        self.reduce_pushButton = QtWidgets.QPushButton(self.frame)
        self.reduce_pushButton.setText("")
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap(":/Icons/icons/schematic.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.reduce_pushButton.setIcon(icon2)
        self.reduce_pushButton.setObjectName("reduce_pushButton")
        self.horizontalLayout.addWidget(self.reduce_pushButton)
        self.verticalLayout.addWidget(self.frame)
        self.tableView = QtWidgets.QTableView(SmartSearch)
        self.tableView.setObjectName("tableView")
        self.verticalLayout.addWidget(self.tableView)

        self.retranslateUi(SmartSearch)
        QtCore.QMetaObject.connectSlotsByName(SmartSearch)

    def retranslateUi(self, SmartSearch):
        SmartSearch.setWindowTitle(QtWidgets.QApplication.translate("SmartSearch", "Smart search", None, -1))
        self.lineEdit.setToolTip(QtWidgets.QApplication.translate("SmartSearch", "<html><head/><body><p>Write search criteria.  i.e.:</p><p>&gt; 20</p><p>== &quot;bus1&quot;</p><p>&gt; &quot;Bus2&quot;</p><p>== 30</p></body></html>", None, -1))
        self.delete_pushButton.setToolTip(QtWidgets.QApplication.translate("SmartSearch", "Delete", None, -1))
        self.reduce_pushButton.setToolTip(QtWidgets.QApplication.translate("SmartSearch", "Reduce", None, -1))

from .icons_rc import *

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    SmartSearch = QtWidgets.QWidget()
    ui = Ui_SmartSearch()
    ui.setupUi(SmartSearch)
    SmartSearch.show()
    sys.exit(app.exec_())

