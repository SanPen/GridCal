# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'MainWindow.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from .icons_rc import *

class Ui_mainWindow(object):
    def setupUi(self, mainWindow):
        if not mainWindow.objectName():
            mainWindow.setObjectName(u"mainWindow")
        mainWindow.resize(549, 535)
        mainWindow.setBaseSize(QSize(0, 0))
        mainWindow.setAcceptDrops(True)
        icon = QIcon()
        icon.addFile(u":/Icons/icons/roseta.svg", QSize(), QIcon.Normal, QIcon.Off)
        mainWindow.setWindowIcon(icon)
        mainWindow.setAutoFillBackground(False)
        mainWindow.setIconSize(QSize(48, 48))
        mainWindow.setToolButtonStyle(Qt.ToolButtonIconOnly)
        mainWindow.setDocumentMode(False)
        mainWindow.setTabShape(QTabWidget.Rounded)
        mainWindow.setDockNestingEnabled(False)
        mainWindow.setUnifiedTitleAndToolBarOnMac(False)
        self.actionOpen = QAction(mainWindow)
        self.actionOpen.setObjectName(u"actionOpen")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/loadc.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionOpen.setIcon(icon1)
        self.actionConvert_to_psse = QAction(mainWindow)
        self.actionConvert_to_psse.setObjectName(u"actionConvert_to_psse")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/area_transfer.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionConvert_to_psse.setIcon(icon2)
        self.actionConvert_to_CGMES = QAction(mainWindow)
        self.actionConvert_to_CGMES.setObjectName(u"actionConvert_to_CGMES")
        self.actionConvert_to_CGMES.setIcon(icon2)
        self.centralwidget = QWidget(mainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.frame_4 = QFrame(self.centralwidget)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame_4)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.filterLineEdit = QLineEdit(self.frame_4)
        self.filterLineEdit.setObjectName(u"filterLineEdit")

        self.horizontalLayout.addWidget(self.filterLineEdit)

        self.filterComboBox = QComboBox(self.frame_4)
        self.filterComboBox.setObjectName(u"filterComboBox")

        self.horizontalLayout.addWidget(self.filterComboBox)

        self.filterButton = QPushButton(self.frame_4)
        self.filterButton.setObjectName(u"filterButton")

        self.horizontalLayout.addWidget(self.filterButton)


        self.verticalLayout.addWidget(self.frame_4)

        self.mainTreeView = QTreeView(self.centralwidget)
        self.mainTreeView.setObjectName(u"mainTreeView")

        self.verticalLayout.addWidget(self.mainTreeView)

        mainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(mainWindow)

        QMetaObject.connectSlotsByName(mainWindow)
    # setupUi

    def retranslateUi(self, mainWindow):
        mainWindow.setWindowTitle(QCoreApplication.translate("mainWindow", u"Tree model viewer", None))
        self.actionOpen.setText(QCoreApplication.translate("mainWindow", u"Open", None))
#if QT_CONFIG(shortcut)
        self.actionOpen.setShortcut(QCoreApplication.translate("mainWindow", u"Ctrl+O", None))
#endif // QT_CONFIG(shortcut)
        self.actionConvert_to_psse.setText(QCoreApplication.translate("mainWindow", u"Convert to PSS/e", None))
        self.actionConvert_to_CGMES.setText(QCoreApplication.translate("mainWindow", u"Convert to CGMES", None))
        self.filterButton.setText(QCoreApplication.translate("mainWindow", u"Filter", None))
    # retranslateUi

