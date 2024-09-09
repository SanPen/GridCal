# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 6.6.2
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
    QFrame, QGridLayout, QHeaderView, QLabel,
    QPushButton, QRadioButton, QSizePolicy, QSpacerItem,
    QSplitter, QTableView, QVBoxLayout, QWidget)
from .icons_rc import *

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(853, 420)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(-1, 0, -1, 9)
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
        self.gridLayout_2 = QGridLayout(self.frame_2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setVerticalSpacing(2)
        self.gridLayout_2.setContentsMargins(-1, 0, -1, 0)
        self.nameComboBox = QComboBox(self.frame_2)
        self.nameComboBox.setObjectName(u"nameComboBox")

        self.gridLayout_2.addWidget(self.nameComboBox, 5, 1, 1, 2)

        self.longitudeCheckBox = QCheckBox(self.frame_2)
        self.longitudeCheckBox.setObjectName(u"longitudeCheckBox")

        self.gridLayout_2.addWidget(self.longitudeCheckBox, 15, 0, 2, 1)

        self.latitudeComboBox = QComboBox(self.frame_2)
        self.latitudeComboBox.setObjectName(u"latitudeComboBox")

        self.gridLayout_2.addWidget(self.latitudeComboBox, 14, 1, 1, 2)

        self.open_button = QPushButton(self.frame_2)
        self.open_button.setObjectName(u"open_button")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/import_profiles.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.open_button.setIcon(icon)

        self.gridLayout_2.addWidget(self.open_button, 2, 0, 1, 1)

        self.longitudeComboBox = QComboBox(self.frame_2)
        self.longitudeComboBox.setObjectName(u"longitudeComboBox")

        self.gridLayout_2.addWidget(self.longitudeComboBox, 16, 1, 1, 2)

        self.nameRadioButton = QRadioButton(self.frame_2)
        self.nameRadioButton.setObjectName(u"nameRadioButton")
        self.nameRadioButton.setChecked(True)

        self.gridLayout_2.addWidget(self.nameRadioButton, 5, 0, 1, 1)

        self.label_4 = QLabel(self.frame_2)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_2.addWidget(self.label_4, 7, 0, 1, 1)

        self.codeComboBox = QComboBox(self.frame_2)
        self.codeComboBox.setObjectName(u"codeComboBox")

        self.gridLayout_2.addWidget(self.codeComboBox, 6, 1, 1, 2)

        self.yCheckBox = QCheckBox(self.frame_2)
        self.yCheckBox.setObjectName(u"yCheckBox")

        self.gridLayout_2.addWidget(self.yCheckBox, 11, 0, 2, 1)

        self.xComboBox = QComboBox(self.frame_2)
        self.xComboBox.setObjectName(u"xComboBox")

        self.gridLayout_2.addWidget(self.xComboBox, 10, 1, 1, 2)

        self.label_2 = QLabel(self.frame_2)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_2.addWidget(self.label_2, 3, 0, 1, 1)

        self.yComboBox = QComboBox(self.frame_2)
        self.yComboBox.setObjectName(u"yComboBox")

        self.gridLayout_2.addWidget(self.yComboBox, 12, 1, 1, 2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_2.addItem(self.verticalSpacer, 17, 0, 1, 3)

        self.codeRadioButton = QRadioButton(self.frame_2)
        self.codeRadioButton.setObjectName(u"codeRadioButton")

        self.gridLayout_2.addWidget(self.codeRadioButton, 6, 0, 1, 1)

        self.latitudeCheckBox = QCheckBox(self.frame_2)
        self.latitudeCheckBox.setObjectName(u"latitudeCheckBox")

        self.gridLayout_2.addWidget(self.latitudeCheckBox, 13, 0, 2, 1)

        self.xCheckBox = QCheckBox(self.frame_2)
        self.xCheckBox.setObjectName(u"xCheckBox")

        self.gridLayout_2.addWidget(self.xCheckBox, 9, 0, 2, 1)

        self.label_3 = QLabel(self.frame_2)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_2.addWidget(self.label_3, 4, 0, 1, 3)

        self.label = QLabel(self.frame_2)
        self.label.setObjectName(u"label")

        self.gridLayout_2.addWidget(self.label, 1, 0, 1, 1)

        self.label_5 = QLabel(self.frame_2)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_2.addWidget(self.label_5, 8, 0, 1, 3)


        self.verticalLayout_2.addWidget(self.frame_2)

        self.splitter.addWidget(self.frame_4)
        self.frame_6 = QFrame(self.splitter)
        self.frame_6.setObjectName(u"frame_6")
        self.frame_6.setFrameShape(QFrame.NoFrame)
        self.frame_6.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame_6)
        self.verticalLayout_3.setSpacing(2)
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
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_3, 0, 1, 1, 1)

        self.acceptButton = QPushButton(self.frame_9)
        self.acceptButton.setObjectName(u"acceptButton")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/gear.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.acceptButton.setIcon(icon1)

        self.gridLayout.addWidget(self.acceptButton, 0, 2, 1, 1)

        self.refreshButton = QPushButton(self.frame_9)
        self.refreshButton.setObjectName(u"refreshButton")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/transform.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.refreshButton.setIcon(icon2)

        self.gridLayout.addWidget(self.refreshButton, 0, 0, 1, 1)


        self.verticalLayout_3.addWidget(self.frame_9)

        self.splitter.addWidget(self.frame_6)

        self.verticalLayout.addWidget(self.splitter)


        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.longitudeCheckBox.setText(QCoreApplication.translate("Dialog", u"Bus longitude", None))
        self.open_button.setText(QCoreApplication.translate("Dialog", u"Load file", None))
        self.nameRadioButton.setText(QCoreApplication.translate("Dialog", u"Name", None))
        self.label_4.setText("")
        self.yCheckBox.setText(QCoreApplication.translate("Dialog", u"Bus y position", None))
        self.label_2.setText("")
        self.codeRadioButton.setText(QCoreApplication.translate("Dialog", u"Code", None))
        self.latitudeCheckBox.setText(QCoreApplication.translate("Dialog", u"Bus latitude", None))
        self.xCheckBox.setText(QCoreApplication.translate("Dialog", u"Bus x position", None))
        self.label_3.setText(QCoreApplication.translate("Dialog", u"Match mathod:", None))
        self.label.setText("")
        self.label_5.setText(QCoreApplication.translate("Dialog", u"Assigning magnitudes", None))
#if QT_CONFIG(tooltip)
        self.acceptButton.setToolTip(QCoreApplication.translate("Dialog", u"Do it!", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(statustip)
        self.acceptButton.setStatusTip("")
#endif // QT_CONFIG(statustip)
        self.acceptButton.setText(QCoreApplication.translate("Dialog", u"Accept", None))
        self.refreshButton.setText(QCoreApplication.translate("Dialog", u"Match", None))
    # retranslateUi

