# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'gui.ui',
# licensing of 'gui.ui' applies.
#
# Created: Sun Aug 25 15:35:40 2019
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

        self.retranslateUi(GisWindow)
        QtCore.QMetaObject.connectSlotsByName(GisWindow)

    def retranslateUi(self, GisWindow):
        GisWindow.setWindowTitle(QtWidgets.QApplication.translate("GisWindow", "GridCal - GIS", None, -1))

from .icons_rc import *

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    GisWindow = QtWidgets.QMainWindow()
    ui = Ui_GisWindow()
    ui.setupUi(GisWindow)
    GisWindow.show()
    sys.exit(app.exec_())

