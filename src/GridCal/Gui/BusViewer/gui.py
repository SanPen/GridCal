# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 6.5.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel,
    QMainWindow, QPushButton, QSizePolicy, QSpacerItem,
    QSpinBox, QToolBar, QVBoxLayout, QWidget)
from .icons_rc import *

class Ui_BusViewerWindow(object):
    def setupUi(self, BusViewerWindow):
        if not BusViewerWindow.objectName():
            BusViewerWindow.setObjectName(u"BusViewerWindow")
        BusViewerWindow.resize(898, 571)
        BusViewerWindow.setToolButtonStyle(Qt.ToolButtonIconOnly)
        BusViewerWindow.setUnifiedTitleAndToolBarOnMac(False)
        self.actiondraw = QAction(BusViewerWindow)
        self.actiondraw.setObjectName(u"actiondraw")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/automatic_layout.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actiondraw.setIcon(icon)
        self.actionExpand_nodes = QAction(BusViewerWindow)
        self.actionExpand_nodes.setObjectName(u"actionExpand_nodes")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/plus (gray).svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionExpand_nodes.setIcon(icon1)
        self.actionScrink_nodes = QAction(BusViewerWindow)
        self.actionScrink_nodes.setObjectName(u"actionScrink_nodes")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/minus (gray).svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionScrink_nodes.setIcon(icon2)
        self.actionAdjust_to_window_size = QAction(BusViewerWindow)
        self.actionAdjust_to_window_size.setObjectName(u"actionAdjust_to_window_size")
        icon3 = QIcon()
        icon3.addFile(u":/Icons/icons/resize.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionAdjust_to_window_size.setIcon(icon3)
        self.centralwidget = QWidget(BusViewerWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.toolsFrame = QFrame(self.centralwidget)
        self.toolsFrame.setObjectName(u"toolsFrame")
        self.toolsFrame.setMaximumSize(QSize(16777215, 40))
        self.toolsFrame.setFrameShape(QFrame.NoFrame)
        self.toolsFrame.setFrameShadow(QFrame.Raised)
        self.gridLayout = QGridLayout(self.toolsFrame)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(8, 0, 8, 0)
        self.drawButton = QPushButton(self.toolsFrame)
        self.drawButton.setObjectName(u"drawButton")
        self.drawButton.setIcon(icon)

        self.gridLayout.addWidget(self.drawButton, 0, 3, 1, 1)

        self.label_2 = QLabel(self.toolsFrame)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 0, 0, 1, 1)

        self.horizontalSpacer = QSpacerItem(621, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 0, 4, 1, 1)

        self.busNameLabel = QLabel(self.toolsFrame)
        self.busNameLabel.setObjectName(u"busNameLabel")

        self.gridLayout.addWidget(self.busNameLabel, 0, 5, 1, 1)

        self.levelSpinBox = QSpinBox(self.toolsFrame)
        self.levelSpinBox.setObjectName(u"levelSpinBox")
        self.levelSpinBox.setMinimum(1)

        self.gridLayout.addWidget(self.levelSpinBox, 0, 2, 1, 1)


        self.verticalLayout.addWidget(self.toolsFrame)

        self.editorFrame = QFrame(self.centralwidget)
        self.editorFrame.setObjectName(u"editorFrame")
        self.editorFrame.setFrameShape(QFrame.NoFrame)
        self.editorFrame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.editorFrame)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.editorLayout = QVBoxLayout()
        self.editorLayout.setObjectName(u"editorLayout")

        self.verticalLayout_2.addLayout(self.editorLayout)


        self.verticalLayout.addWidget(self.editorFrame)

        BusViewerWindow.setCentralWidget(self.centralwidget)
        self.toolBar = QToolBar(BusViewerWindow)
        self.toolBar.setObjectName(u"toolBar")
        self.toolBar.setEnabled(True)
        self.toolBar.setMovable(False)
        BusViewerWindow.addToolBar(Qt.TopToolBarArea, self.toolBar)

        self.toolBar.addAction(self.actiondraw)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionAdjust_to_window_size)
        self.toolBar.addAction(self.actionScrink_nodes)
        self.toolBar.addAction(self.actionExpand_nodes)

        self.retranslateUi(BusViewerWindow)

        QMetaObject.connectSlotsByName(BusViewerWindow)
    # setupUi

    def retranslateUi(self, BusViewerWindow):
        BusViewerWindow.setWindowTitle(QCoreApplication.translate("BusViewerWindow", u"MainWindow", None))
        self.actiondraw.setText(QCoreApplication.translate("BusViewerWindow", u"draw", None))
        self.actionExpand_nodes.setText(QCoreApplication.translate("BusViewerWindow", u"Expand nodes", None))
        self.actionScrink_nodes.setText(QCoreApplication.translate("BusViewerWindow", u"Scrink nodes", None))
        self.actionAdjust_to_window_size.setText(QCoreApplication.translate("BusViewerWindow", u"Adjust to window size", None))
#if QT_CONFIG(tooltip)
        self.drawButton.setToolTip(QCoreApplication.translate("BusViewerWindow", u"Draw schematic", None))
#endif // QT_CONFIG(tooltip)
        self.drawButton.setText("")
        self.label_2.setText(QCoreApplication.translate("BusViewerWindow", u"Levels to expand", None))
        self.busNameLabel.setText("")
        self.toolBar.setWindowTitle(QCoreApplication.translate("BusViewerWindow", u"toolBar", None))
    # retranslateUi

