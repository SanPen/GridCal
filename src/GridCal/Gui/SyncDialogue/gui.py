# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'gui.ui',
# licensing of 'gui.ui' applies.
#
# Created: Mon Jan  6 14:16:49 2020
#      by: pyside2-uic  running on PySide2 5.13.0
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(941, 590)
        self.verticalLayout = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout.setContentsMargins(1, 1, 1, 1)
        self.verticalLayout.setObjectName("verticalLayout")
        self.frame = QtWidgets.QFrame(Dialog)
        self.frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame.setObjectName("frame")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.frame)
        self.verticalLayout_2.setContentsMargins(-1, -1, -1, 0)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.treeView = QtWidgets.QTreeView(self.frame)
        self.treeView.setAlternatingRowColors(True)
        self.treeView.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.treeView.setAnimated(True)
        self.treeView.setObjectName("treeView")
        self.verticalLayout_2.addWidget(self.treeView)
        self.verticalLayout.addWidget(self.frame)
        self.frame_2 = QtWidgets.QFrame(Dialog)
        self.frame_2.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame_2.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_2.setObjectName("frame_2")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.frame_2)
        self.horizontalLayout.setContentsMargins(-1, 0, -1, -1)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.accept_selected_pushButton = QtWidgets.QPushButton(self.frame_2)
        self.accept_selected_pushButton.setText("")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/Icons/icons/accept.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.accept_selected_pushButton.setIcon(icon)
        self.accept_selected_pushButton.setObjectName("accept_selected_pushButton")
        self.horizontalLayout.addWidget(self.accept_selected_pushButton)
        self.reject_selected_pushButton = QtWidgets.QPushButton(self.frame_2)
        self.reject_selected_pushButton.setText("")
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/Icons/icons/delete.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.reject_selected_pushButton.setIcon(icon1)
        self.reject_selected_pushButton.setObjectName("reject_selected_pushButton")
        self.horizontalLayout.addWidget(self.reject_selected_pushButton)
        spacerItem = QtWidgets.QSpacerItem(632, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.doit_pushButton = QtWidgets.QPushButton(self.frame_2)
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap(":/Icons/icons/accept2.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.doit_pushButton.setIcon(icon2)
        self.doit_pushButton.setObjectName("doit_pushButton")
        self.horizontalLayout.addWidget(self.doit_pushButton)
        self.verticalLayout.addWidget(self.frame_2)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtWidgets.QApplication.translate("Dialog", "Dialog", None, -1))
        self.accept_selected_pushButton.setToolTip(QtWidgets.QApplication.translate("Dialog", "Accept selected", None, -1))
        self.reject_selected_pushButton.setToolTip(QtWidgets.QApplication.translate("Dialog", "Reject selected changes", None, -1))
        self.doit_pushButton.setToolTip(QtWidgets.QApplication.translate("Dialog", "Process all changes as especified", None, -1))
        self.doit_pushButton.setText(QtWidgets.QApplication.translate("Dialog", "Do it", None, -1))

from .icons_rc import *

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Dialog = QtWidgets.QDialog()
    ui = Ui_Dialog()
    ui.setupUi(Dialog)
    Dialog.show()
    sys.exit(app.exec_())

