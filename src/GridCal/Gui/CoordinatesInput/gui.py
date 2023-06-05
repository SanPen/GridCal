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
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QPushButton, QRadioButton, QSizePolicy,
    QSpacerItem, QSplitter, QTableView, QVBoxLayout,
    QWidget)
from .icons_rc import *

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(769, 420)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(-1, 0, -1, 9)
        self.frame = QFrame(Dialog)
        self.frame.setObjectName(u"frame")
        self.frame.setMaximumSize(QSize(16777215, 40))
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.frame)
        self.horizontalLayout_5.setSpacing(1)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.open_button = QPushButton(self.frame)
        self.open_button.setObjectName(u"open_button")
        self.open_button.setMinimumSize(QSize(0, 0))
        icon = QIcon()
        icon.addFile(u":/Icons/icons/import_profiles.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.open_button.setIcon(icon)
        self.open_button.setIconSize(QSize(24, 24))

        self.horizontalLayout_5.addWidget(self.open_button)

        self.refreshButton = QPushButton(self.frame)
        self.refreshButton.setObjectName(u"refreshButton")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/transform.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.refreshButton.setIcon(icon1)
        self.refreshButton.setIconSize(QSize(24, 24))

        self.horizontalLayout_5.addWidget(self.refreshButton)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_2)


        self.verticalLayout.addWidget(self.frame)

        self.splitter = QSplitter(Dialog)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.frame_4 = QFrame(self.splitter)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame_4)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.frame_2 = QFrame(self.frame_4)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.formLayout = QFormLayout(self.frame_2)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setContentsMargins(-1, 0, -1, -1)
        self.xComboBox = QComboBox(self.frame_2)
        self.xComboBox.setObjectName(u"xComboBox")

        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.xComboBox)

        self.yComboBox = QComboBox(self.frame_2)
        self.yComboBox.setObjectName(u"yComboBox")

        self.formLayout.setWidget(3, QFormLayout.FieldRole, self.yComboBox)

        self.latitudeComboBox = QComboBox(self.frame_2)
        self.latitudeComboBox.setObjectName(u"latitudeComboBox")

        self.formLayout.setWidget(4, QFormLayout.FieldRole, self.latitudeComboBox)

        self.longitudeComboBox = QComboBox(self.frame_2)
        self.longitudeComboBox.setObjectName(u"longitudeComboBox")

        self.formLayout.setWidget(5, QFormLayout.FieldRole, self.longitudeComboBox)

        self.xCheckBox = QCheckBox(self.frame_2)
        self.xCheckBox.setObjectName(u"xCheckBox")

        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.xCheckBox)

        self.yCheckBox = QCheckBox(self.frame_2)
        self.yCheckBox.setObjectName(u"yCheckBox")

        self.formLayout.setWidget(3, QFormLayout.LabelRole, self.yCheckBox)

        self.latitudeCheckBox = QCheckBox(self.frame_2)
        self.latitudeCheckBox.setObjectName(u"latitudeCheckBox")

        self.formLayout.setWidget(4, QFormLayout.LabelRole, self.latitudeCheckBox)

        self.longitudeCheckBox = QCheckBox(self.frame_2)
        self.longitudeCheckBox.setObjectName(u"longitudeCheckBox")

        self.formLayout.setWidget(5, QFormLayout.LabelRole, self.longitudeCheckBox)

        self.nameRadioButton = QRadioButton(self.frame_2)
        self.nameRadioButton.setObjectName(u"nameRadioButton")
        self.nameRadioButton.setChecked(True)

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.nameRadioButton)

        self.codeRadioButton = QRadioButton(self.frame_2)
        self.codeRadioButton.setObjectName(u"codeRadioButton")

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.codeRadioButton)

        self.nameComboBox = QComboBox(self.frame_2)
        self.nameComboBox.setObjectName(u"nameComboBox")

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.nameComboBox)

        self.codeComboBox = QComboBox(self.frame_2)
        self.codeComboBox.setObjectName(u"codeComboBox")

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.codeComboBox)


        self.verticalLayout_2.addWidget(self.frame_2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)

        self.splitter.addWidget(self.frame_4)
        self.frame_6 = QFrame(self.splitter)
        self.frame_6.setObjectName(u"frame_6")
        self.frame_6.setFrameShape(QFrame.NoFrame)
        self.frame_6.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame_6)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.assignation_table = QTableView(self.frame_6)
        self.assignation_table.setObjectName(u"assignation_table")

        self.verticalLayout_3.addWidget(self.assignation_table)

        self.frame_9 = QFrame(self.frame_6)
        self.frame_9.setObjectName(u"frame_9")
        self.frame_9.setFrameShape(QFrame.NoFrame)
        self.frame_9.setFrameShadow(QFrame.Raised)
        self.gridLayout = QGridLayout(self.frame_9)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, -1, 0, 0)
        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_3, 0, 1, 1, 1)

        self.acceptButton = QPushButton(self.frame_9)
        self.acceptButton.setObjectName(u"acceptButton")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/gear.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.acceptButton.setIcon(icon2)

        self.gridLayout.addWidget(self.acceptButton, 0, 2, 1, 1)


        self.verticalLayout_3.addWidget(self.frame_9)

        self.splitter.addWidget(self.frame_6)

        self.verticalLayout.addWidget(self.splitter)


        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
#if QT_CONFIG(tooltip)
        self.open_button.setToolTip(QCoreApplication.translate("Dialog", u"Import file", None))
#endif // QT_CONFIG(tooltip)
        self.open_button.setText("")
#if QT_CONFIG(tooltip)
        self.refreshButton.setToolTip(QCoreApplication.translate("Dialog", u"Refresh assignation table", None))
#endif // QT_CONFIG(tooltip)
        self.refreshButton.setText("")
        self.xCheckBox.setText(QCoreApplication.translate("Dialog", u"Bus x position", None))
        self.yCheckBox.setText(QCoreApplication.translate("Dialog", u"Bus y position", None))
        self.latitudeCheckBox.setText(QCoreApplication.translate("Dialog", u"Bus latitude", None))
        self.longitudeCheckBox.setText(QCoreApplication.translate("Dialog", u"Bus longitude", None))
        self.nameRadioButton.setText(QCoreApplication.translate("Dialog", u"Name", None))
        self.codeRadioButton.setText(QCoreApplication.translate("Dialog", u"Code", None))
#if QT_CONFIG(tooltip)
        self.acceptButton.setToolTip(QCoreApplication.translate("Dialog", u"Do it!", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(statustip)
        self.acceptButton.setStatusTip("")
#endif // QT_CONFIG(statustip)
        self.acceptButton.setText(QCoreApplication.translate("Dialog", u"Accept", None))
    # retranslateUi

