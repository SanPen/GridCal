# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'gui.ui',
# licensing of 'gui.ui' applies.
#
# Created: Mon Dec  9 12:39:51 2019
#      by: pyside2-uic  running on PySide2 5.13.0
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore, QtGui, QtWidgets

class Ui_GisWindow(object):
    def setupUi(self, GisWindow):
        GisWindow.setObjectName("GisWindow")
        GisWindow.resize(938, 577)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/icons/icons/map.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        GisWindow.setWindowIcon(icon)
        self.centralwidget = QtWidgets.QWidget(GisWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.webFrame = QtWidgets.QFrame(self.centralwidget)
        self.webFrame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.webFrame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.webFrame.setObjectName("webFrame")
        self.verticalLayout.addWidget(self.webFrame)
        GisWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QtWidgets.QStatusBar(GisWindow)
        self.statusbar.setObjectName("statusbar")
        GisWindow.setStatusBar(self.statusbar)
        self.toolBar = QtWidgets.QToolBar(GisWindow)
        self.toolBar.setMovable(False)
        self.toolBar.setFloatable(False)
        self.toolBar.setObjectName("toolBar")
        GisWindow.addToolBar(QtCore.Qt.TopToolBarArea, self.toolBar)
        self.actionSave_map = QtWidgets.QAction(GisWindow)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/icons/icons/savec.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionSave_map.setIcon(icon1)
        self.actionSave_map.setObjectName("actionSave_map")
        self.toolBar.addAction(self.actionSave_map)

        self.retranslateUi(GisWindow)
        QtCore.QMetaObject.connectSlotsByName(GisWindow)

    def retranslateUi(self, GisWindow):
        GisWindow.setWindowTitle(QtWidgets.QApplication.translate("GisWindow", "GridCal - GIS", None, -1))
        self.toolBar.setWindowTitle(QtWidgets.QApplication.translate("GisWindow", "toolBar", None, -1))
        self.actionSave_map.setText(QtWidgets.QApplication.translate("GisWindow", "Save map", None, -1))
        self.actionSave_map.setToolTip(QtWidgets.QApplication.translate("GisWindow", "Save this map", None, -1))
        self.actionSave_map.setShortcut(QtWidgets.QApplication.translate("GisWindow", "Ctrl+S", None, -1))

from .icons_rc import *

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    GisWindow = QtWidgets.QMainWindow()
    ui = Ui_GisWindow()
    ui.setupUi(GisWindow)
    GisWindow.show()
    sys.exit(app.exec_())

