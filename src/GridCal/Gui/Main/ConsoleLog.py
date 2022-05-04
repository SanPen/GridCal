# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ConsoleLog.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from .icons_rc import *

class Ui_mainWindow(object):
    def setupUi(self, mainWindow):
        if not mainWindow.objectName():
            mainWindow.setObjectName(u"mainWindow")
        mainWindow.resize(516, 327)
        mainWindow.setBaseSize(QSize(0, 0))
        icon = QIcon()
        icon.addFile(u":/Program icon/GridCal_icon.svg", QSize(), QIcon.Normal, QIcon.Off)
        mainWindow.setWindowIcon(icon)
        mainWindow.setIconSize(QSize(24, 24))
        mainWindow.setDocumentMode(False)
        mainWindow.setTabShape(QTabWidget.Rounded)
        mainWindow.setUnifiedTitleAndToolBarOnMac(False)
        self.actionSave = QAction(mainWindow)
        self.actionSave.setObjectName(u"actionSave")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/savec.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionSave.setIcon(icon1)
        self.centralwidget = QWidget(mainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.plainTextEdit = QPlainTextEdit(self.centralwidget)
        self.plainTextEdit.setObjectName(u"plainTextEdit")
        palette = QPalette()
        brush = QBrush(QColor(255, 255, 255, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Text, brush)
        brush1 = QBrush(QColor(0, 170, 127, 255))
        brush1.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Base, brush1)
        brush2 = QBrush(QColor(255, 255, 255, 128))
        brush2.setStyle(Qt.SolidPattern)
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
        palette.setBrush(QPalette.Active, QPalette.PlaceholderText, brush2)
#endif
        palette.setBrush(QPalette.Inactive, QPalette.Text, brush)
        palette.setBrush(QPalette.Inactive, QPalette.Base, brush1)
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
        palette.setBrush(QPalette.Inactive, QPalette.PlaceholderText, brush2)
#endif
        brush3 = QBrush(QColor(120, 120, 120, 255))
        brush3.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Disabled, QPalette.Text, brush3)
        brush4 = QBrush(QColor(240, 240, 240, 255))
        brush4.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Disabled, QPalette.Base, brush4)
        brush5 = QBrush(QColor(0, 0, 0, 128))
        brush5.setStyle(Qt.SolidPattern)
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
        palette.setBrush(QPalette.Disabled, QPalette.PlaceholderText, brush5)
#endif
        self.plainTextEdit.setPalette(palette)
        font = QFont()
        font.setFamily(u"Consolas")
        self.plainTextEdit.setFont(font)
        self.plainTextEdit.setFrameShape(QFrame.NoFrame)
        self.plainTextEdit.setReadOnly(True)
        self.plainTextEdit.setPlainText(u"Console")

        self.verticalLayout.addWidget(self.plainTextEdit)

        mainWindow.setCentralWidget(self.centralwidget)
        self.menuBar = QMenuBar(mainWindow)
        self.menuBar.setObjectName(u"menuBar")
        self.menuBar.setGeometry(QRect(0, 0, 516, 21))
        self.menuSave = QMenu(self.menuBar)
        self.menuSave.setObjectName(u"menuSave")
        mainWindow.setMenuBar(self.menuBar)

        self.menuBar.addAction(self.menuSave.menuAction())
        self.menuSave.addAction(self.actionSave)

        self.retranslateUi(mainWindow)

        QMetaObject.connectSlotsByName(mainWindow)
    # setupUi

    def retranslateUi(self, mainWindow):
        mainWindow.setWindowTitle(QCoreApplication.translate("mainWindow", u"GridCal", None))
        self.actionSave.setText(QCoreApplication.translate("mainWindow", u"Save", None))
#if QT_CONFIG(shortcut)
        self.actionSave.setShortcut(QCoreApplication.translate("mainWindow", u"Ctrl+S, Ctrl+S", None))
#endif // QT_CONFIG(shortcut)
        self.plainTextEdit.setDocumentTitle(QCoreApplication.translate("mainWindow", u"Logger", None))
        self.plainTextEdit.setPlaceholderText(QCoreApplication.translate("mainWindow", u">", None))
        self.menuSave.setTitle(QCoreApplication.translate("mainWindow", u"File", None))
    # retranslateUi

