# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'SelectComponents.ui'
##
## Created by: Qt User Interface Compiler version 6.6.3
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QDialog,
                               QDialogButtonBox, QFrame, QGridLayout, QLabel,
                               QSizePolicy, QVBoxLayout, QWidget)
from .icons_rc import *
from .icons_rc import *


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(527, 368)
        self.verticalLayout = QVBoxLayout(MainWindow)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.frame = QFrame(MainWindow)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.checkBox = QCheckBox(self.frame)
        self.checkBox.setObjectName(u"checkBox")
        self.checkBox.setAutoExclusive(True)

        self.gridLayout.addWidget(self.checkBox, 3, 1, 1, 1)

        self.checkBox_3 = QCheckBox(self.frame)
        self.checkBox_3.setObjectName(u"checkBox_3")
        self.checkBox_3.setAutoExclusive(True)

        self.gridLayout.addWidget(self.checkBox_3, 5, 1, 1, 1)

        self.checkBox_7 = QCheckBox(self.frame)
        self.checkBox_7.setObjectName(u"checkBox_7")
        self.checkBox_7.setAutoExclusive(True)

        self.gridLayout.addWidget(self.checkBox_7, 9, 1, 1, 1)

        self.checkBox_2 = QCheckBox(self.frame)
        self.checkBox_2.setObjectName(u"checkBox_2")
        self.checkBox_2.setAutoExclusive(True)

        self.gridLayout.addWidget(self.checkBox_2, 4, 1, 1, 1)

        self.checkBox_4 = QCheckBox(self.frame)
        self.checkBox_4.setObjectName(u"checkBox_4")
        self.checkBox_4.setAutoExclusive(True)

        self.gridLayout.addWidget(self.checkBox_4, 6, 1, 1, 1)

        self.label_2 = QLabel(self.frame)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 10, 1, 1, 1)

        self.label = QLabel(self.frame)
        self.label.setObjectName(u"label")
        font = QFont()
        font.setPointSize(16)
        self.label.setFont(font)

        self.gridLayout.addWidget(self.label, 1, 1, 1, 1)

        self.checkBox_5 = QCheckBox(self.frame)
        self.checkBox_5.setObjectName(u"checkBox_5")
        self.checkBox_5.setAutoExclusive(True)

        self.gridLayout.addWidget(self.checkBox_5, 7, 1, 1, 1)

        self.checkBox_6 = QCheckBox(self.frame)
        self.checkBox_6.setObjectName(u"checkBox_6")
        self.checkBox_6.setAutoExclusive(True)

        self.gridLayout.addWidget(self.checkBox_6, 8, 1, 1, 1)

        self.label_3 = QLabel(self.frame)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 2, 1, 1, 1)

        self.verticalLayout_3.addLayout(self.gridLayout)

        self.buttonBox = QDialogButtonBox(self.frame)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout_3.addWidget(self.buttonBox)

        self.verticalLayout_2.addWidget(self.frame)

        self.verticalLayout.addLayout(self.verticalLayout_2)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Dialog", None))
        self.checkBox.setText(QCoreApplication.translate("MainWindow", u"Transformer", None))
        self.checkBox_3.setText(QCoreApplication.translate("MainWindow", u"Line", None))
        self.checkBox_7.setText(QCoreApplication.translate("MainWindow", u"Substation", None))
        self.checkBox_2.setText(QCoreApplication.translate("MainWindow", u"Cable", None))
        self.checkBox_4.setText(QCoreApplication.translate("MainWindow", u"Turbine", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"(Only one may be selected at a time.)", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Insert Catalogue Component", None))
        self.checkBox_5.setText(QCoreApplication.translate("MainWindow", u"Reactor", None))
        self.checkBox_6.setText(QCoreApplication.translate("MainWindow", u"Switchgear", None))
        self.label_3.setText(
            QCoreApplication.translate("MainWindow", u"Please select the component data to add to the catalogue:",
                                       None))
    # retranslateUi
