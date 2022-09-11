# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from .icons_rc import *

class Ui_GisWindow(object):
    def setupUi(self, GisWindow):
        if not GisWindow.objectName():
            GisWindow.setObjectName(u"GisWindow")
        GisWindow.resize(938, 577)
        icon = QIcon()
        icon.addFile(u":/icons/icons/map.svg", QSize(), QIcon.Normal, QIcon.Off)
        GisWindow.setWindowIcon(icon)
        self.actionSave_map = QAction(GisWindow)
        self.actionSave_map.setObjectName(u"actionSave_map")
        icon1 = QIcon()
        icon1.addFile(u":/icons/icons/savec.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionSave_map.setIcon(icon1)
        self.centralwidget = QWidget(GisWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.webFrame = QFrame(self.centralwidget)
        self.webFrame.setObjectName(u"webFrame")
        self.webFrame.setFrameShape(QFrame.StyledPanel)
        self.webFrame.setFrameShadow(QFrame.Raised)

        self.verticalLayout.addWidget(self.webFrame)

        GisWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(GisWindow)
        self.statusbar.setObjectName(u"statusbar")
        GisWindow.setStatusBar(self.statusbar)
        self.toolBar = QToolBar(GisWindow)
        self.toolBar.setObjectName(u"toolBar")
        self.toolBar.setMovable(False)
        self.toolBar.setFloatable(False)
        GisWindow.addToolBar(Qt.TopToolBarArea, self.toolBar)

        self.toolBar.addAction(self.actionSave_map)

        self.retranslateUi(GisWindow)

        QMetaObject.connectSlotsByName(GisWindow)
    # setupUi

    def retranslateUi(self, GisWindow):
        GisWindow.setWindowTitle(QCoreApplication.translate("GisWindow", u"GridCal - GIS", None))
        self.actionSave_map.setText(QCoreApplication.translate("GisWindow", u"Save map", None))
#if QT_CONFIG(tooltip)
        self.actionSave_map.setToolTip(QCoreApplication.translate("GisWindow", u"Save this map", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(shortcut)
        self.actionSave_map.setShortcut(QCoreApplication.translate("GisWindow", u"Ctrl+S", None))
#endif // QT_CONFIG(shortcut)
        self.toolBar.setWindowTitle(QCoreApplication.translate("GisWindow", u"toolBar", None))
    # retranslateUi

