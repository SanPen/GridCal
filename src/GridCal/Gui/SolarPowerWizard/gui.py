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
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QDialog, QDoubleSpinBox, QFrame,
    QGridLayout, QHeaderView, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QSplitter, QTableView,
    QVBoxLayout, QWidget)
from .icons_rc import *

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(836, 561)
        icon = QIcon()
        icon.addFile(u":/Icons/icons/solar_power.svg", QSize(), QIcon.Normal, QIcon.Off)
        MainWindow.setWindowIcon(icon)
        self.actionCopy_to_clipboard = QAction(MainWindow)
        self.actionCopy_to_clipboard.setObjectName(u"actionCopy_to_clipboard")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/copy.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionCopy_to_clipboard.setIcon(icon1)
        self.actionSave = QAction(MainWindow)
        self.actionSave.setObjectName(u"actionSave")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/import_profiles.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionSave.setIcon(icon2)
        self.verticalLayout = QVBoxLayout(MainWindow)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(MainWindow)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.frame = QFrame(self.splitter)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.gridLayout_2 = QGridLayout(self.frame)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.label_3 = QLabel(self.frame)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_2.addWidget(self.label_3, 2, 0, 1, 2)

        self.label_2 = QLabel(self.frame)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_2.addWidget(self.label_2, 3, 0, 1, 1)

        self.label_5 = QLabel(self.frame)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_2.addWidget(self.label_5, 7, 0, 1, 1)

        self.latitudeSpinBox = QDoubleSpinBox(self.frame)
        self.latitudeSpinBox.setObjectName(u"latitudeSpinBox")
        self.latitudeSpinBox.setDecimals(6)
        self.latitudeSpinBox.setMinimum(-9999999.000000000000000)
        self.latitudeSpinBox.setMaximum(99999.000000000000000)

        self.gridLayout_2.addWidget(self.latitudeSpinBox, 6, 1, 1, 2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_2.addItem(self.verticalSpacer, 9, 0, 1, 1)

        self.longitudeSpinBox = QDoubleSpinBox(self.frame)
        self.longitudeSpinBox.setObjectName(u"longitudeSpinBox")
        self.longitudeSpinBox.setDecimals(6)
        self.longitudeSpinBox.setMinimum(-9999999.000000000000000)
        self.longitudeSpinBox.setMaximum(99999.000000000000000)

        self.gridLayout_2.addWidget(self.longitudeSpinBox, 7, 1, 1, 2)

        self.powerSpinBox = QDoubleSpinBox(self.frame)
        self.powerSpinBox.setObjectName(u"powerSpinBox")
        self.powerSpinBox.setMaximum(99999.000000000000000)

        self.gridLayout_2.addWidget(self.powerSpinBox, 8, 1, 1, 2)

        self.label_4 = QLabel(self.frame)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_2.addWidget(self.label_4, 6, 0, 1, 1)

        self.label = QLabel(self.frame)
        self.label.setObjectName(u"label")

        self.gridLayout_2.addWidget(self.label, 8, 0, 1, 1)

        self.label_bus = QLabel(self.frame)
        self.label_bus.setObjectName(u"label_bus")

        self.gridLayout_2.addWidget(self.label_bus, 5, 0, 1, 3)

        self.label_gen = QLabel(self.frame)
        self.label_gen.setObjectName(u"label_gen")

        self.gridLayout_2.addWidget(self.label_gen, 4, 0, 1, 3)

        self.generateButton = QPushButton(self.frame)
        self.generateButton.setObjectName(u"generateButton")

        self.gridLayout_2.addWidget(self.generateButton, 10, 2, 1, 1)

        self.splitter.addWidget(self.frame)
        self.frame_4 = QFrame(self.splitter)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.gridLayout = QGridLayout(self.frame_4)
        self.gridLayout.setObjectName(u"gridLayout")
        self.plotButton = QPushButton(self.frame_4)
        self.plotButton.setObjectName(u"plotButton")
        icon3 = QIcon()
        icon3.addFile(u":/Icons/icons/plot.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.plotButton.setIcon(icon3)

        self.gridLayout.addWidget(self.plotButton, 1, 0, 1, 2)

        self.horizontalSpacer_2 = QSpacerItem(394, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_2, 1, 2, 1, 1)

        self.acceptButton = QPushButton(self.frame_4)
        self.acceptButton.setObjectName(u"acceptButton")

        self.gridLayout.addWidget(self.acceptButton, 1, 3, 1, 1)

        self.resultsTableView = QTableView(self.frame_4)
        self.resultsTableView.setObjectName(u"resultsTableView")

        self.gridLayout.addWidget(self.resultsTableView, 0, 0, 1, 4)

        self.splitter.addWidget(self.frame_4)

        self.verticalLayout.addWidget(self.splitter)


        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Solar power wizard", None))
        self.actionCopy_to_clipboard.setText(QCoreApplication.translate("MainWindow", u"Copy to clipboard", None))
        self.actionSave.setText(QCoreApplication.translate("MainWindow", u"Save", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"Site data", None))
        self.label_2.setText("")
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Longitude", None))
        self.latitudeSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" deg", None))
        self.longitudeSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" deg", None))
        self.powerSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" MW", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Latutide", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Power", None))
        self.label_bus.setText(QCoreApplication.translate("MainWindow", u"Bus", None))
        self.label_gen.setText(QCoreApplication.translate("MainWindow", u"Generator", None))
        self.generateButton.setText(QCoreApplication.translate("MainWindow", u"Generate", None))
#if QT_CONFIG(tooltip)
        self.plotButton.setToolTip(QCoreApplication.translate("MainWindow", u"Plot data", None))
#endif // QT_CONFIG(tooltip)
        self.plotButton.setText("")
        self.acceptButton.setText(QCoreApplication.translate("MainWindow", u"Accept", None))
    # retranslateUi

