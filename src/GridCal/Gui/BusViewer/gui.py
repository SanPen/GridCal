# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 5.15.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QDate, QDateTime, QMetaObject,
    QObject, QPoint, QRect, QSize, QTime, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPalette, QPainter,
    QPixmap, QRadialGradient)
from PySide2.QtWidgets import *

from .icons_rc import *

class Ui_BusViewerWindow(object):
    def setupUi(self, BusViewerWindow):
        if not BusViewerWindow.objectName():
            BusViewerWindow.setObjectName(u"BusViewerWindow")
        BusViewerWindow.resize(841, 518)
        icon = QIcon()
        icon.addFile(u":/Icons/icons/automatic_layout.svg", QSize(), QIcon.Normal, QIcon.Off)
        BusViewerWindow.setWindowIcon(icon)
        self.actionCopy_to_clipboard = QAction(BusViewerWindow)
        self.actionCopy_to_clipboard.setObjectName(u"actionCopy_to_clipboard")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/copy.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionCopy_to_clipboard.setIcon(icon1)
        self.actionSave = QAction(BusViewerWindow)
        self.actionSave.setObjectName(u"actionSave")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/import_profiles.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionSave.setIcon(icon2)
        self.verticalLayout = QVBoxLayout(BusViewerWindow)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.toolsFrame = QFrame(BusViewerWindow)
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

        self.gridLayout.addWidget(self.drawButton, 0, 2, 1, 1)

        self.label_2 = QLabel(self.toolsFrame)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 0, 0, 1, 1)

        self.horizontalSpacer = QSpacerItem(621, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 0, 3, 1, 1)

        self.levelSpinBox = QSpinBox(self.toolsFrame)
        self.levelSpinBox.setObjectName(u"levelSpinBox")
        self.levelSpinBox.setMinimum(1)

        self.gridLayout.addWidget(self.levelSpinBox, 0, 1, 1, 1)

        self.busNameLabel = QLabel(self.toolsFrame)
        self.busNameLabel.setObjectName(u"busNameLabel")

        self.gridLayout.addWidget(self.busNameLabel, 0, 4, 1, 1)


        self.verticalLayout.addWidget(self.toolsFrame)

        self.editorFrame = QFrame(BusViewerWindow)
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


        self.retranslateUi(BusViewerWindow)

        QMetaObject.connectSlotsByName(BusViewerWindow)
    # setupUi

    def retranslateUi(self, BusViewerWindow):
        BusViewerWindow.setWindowTitle(QCoreApplication.translate("BusViewerWindow", u"Bus viewer", None))
        self.actionCopy_to_clipboard.setText(QCoreApplication.translate("BusViewerWindow", u"Copy to clipboard", None))
        self.actionSave.setText(QCoreApplication.translate("BusViewerWindow", u"Save", None))
#if QT_CONFIG(tooltip)
        self.drawButton.setToolTip(QCoreApplication.translate("BusViewerWindow", u"Draw schematic", None))
#endif // QT_CONFIG(tooltip)
        self.drawButton.setText("")
        self.label_2.setText(QCoreApplication.translate("BusViewerWindow", u"Levels to expand", None))
        self.busNameLabel.setText("")
    # retranslateUi

