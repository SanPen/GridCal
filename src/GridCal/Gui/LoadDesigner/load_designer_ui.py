# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'load_designer_ui.ui'
##
## Created by: Qt User Interface Compiler version 6.5.3
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
from PySide6.QtWidgets import (QApplication, QDialog, QDoubleSpinBox, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QSplitter, QTableView,
    QTimeEdit, QToolBox, QVBoxLayout, QWidget)

from GridCal.Gui.Widgets.matplotlibwidget import MatplotlibWidget
from .icons_rc import *

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(941, 590)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(1, 1, 1, 1)
        self.splitter_3 = QSplitter(Dialog)
        self.splitter_3.setObjectName(u"splitter_3")
        self.splitter_3.setOrientation(Qt.Horizontal)
        self.frame_8 = QFrame(self.splitter_3)
        self.frame_8.setObjectName(u"frame_8")
        self.frame_8.setFrameShape(QFrame.NoFrame)
        self.frame_8.setFrameShadow(QFrame.Raised)
        self.verticalLayout_7 = QVBoxLayout(self.frame_8)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(-1, 9, -1, -1)
        self.toolBox = QToolBox(self.frame_8)
        self.toolBox.setObjectName(u"toolBox")
        self.page_3 = QWidget()
        self.page_3.setObjectName(u"page_3")
        self.page_3.setGeometry(QRect(0, 0, 848, 352))
        self.verticalLayout_3 = QVBoxLayout(self.page_3)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, -1, 0, -1)
        self.frame_2 = QFrame(self.page_3)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setMinimumSize(QSize(300, 0))
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.frame_2)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.frame_3 = QFrame(self.frame_2)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setFrameShape(QFrame.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_3)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.label = QLabel(self.frame_3)
        self.label.setObjectName(u"label")
        self.label.setMaximumSize(QSize(160, 16777215))

        self.horizontalLayout_3.addWidget(self.label)

        self.night_valley_timeEdit = QTimeEdit(self.frame_3)
        self.night_valley_timeEdit.setObjectName(u"night_valley_timeEdit")
        self.night_valley_timeEdit.setTime(QTime(3, 0, 0))

        self.horizontalLayout_3.addWidget(self.night_valley_timeEdit)

        self.night_valley_doubleSpinBox = QDoubleSpinBox(self.frame_3)
        self.night_valley_doubleSpinBox.setObjectName(u"night_valley_doubleSpinBox")
        self.night_valley_doubleSpinBox.setDecimals(4)
        self.night_valley_doubleSpinBox.setMaximum(9999999.000000000000000)
        self.night_valley_doubleSpinBox.setValue(4.000000000000000)

        self.horizontalLayout_3.addWidget(self.night_valley_doubleSpinBox)


        self.verticalLayout_4.addWidget(self.frame_3)

        self.frame_4 = QFrame(self.frame_2)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_4 = QHBoxLayout(self.frame_4)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.label_2 = QLabel(self.frame_4)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setMaximumSize(QSize(160, 16777215))

        self.horizontalLayout_4.addWidget(self.label_2)

        self.morning_peak_timeEdit = QTimeEdit(self.frame_4)
        self.morning_peak_timeEdit.setObjectName(u"morning_peak_timeEdit")
        self.morning_peak_timeEdit.setTime(QTime(10, 0, 0))

        self.horizontalLayout_4.addWidget(self.morning_peak_timeEdit)

        self.morning_peak_doubleSpinBox = QDoubleSpinBox(self.frame_4)
        self.morning_peak_doubleSpinBox.setObjectName(u"morning_peak_doubleSpinBox")
        self.morning_peak_doubleSpinBox.setDecimals(4)
        self.morning_peak_doubleSpinBox.setMaximum(9999999.000000000000000)
        self.morning_peak_doubleSpinBox.setValue(12.000000000000000)

        self.horizontalLayout_4.addWidget(self.morning_peak_doubleSpinBox)


        self.verticalLayout_4.addWidget(self.frame_4)

        self.frame_5 = QFrame(self.frame_2)
        self.frame_5.setObjectName(u"frame_5")
        self.frame_5.setFrameShape(QFrame.NoFrame)
        self.frame_5.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_6 = QHBoxLayout(self.frame_5)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.label_4 = QLabel(self.frame_5)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setMaximumSize(QSize(160, 16777215))

        self.horizontalLayout_6.addWidget(self.label_4)

        self.afternoon_valley_timeEdit = QTimeEdit(self.frame_5)
        self.afternoon_valley_timeEdit.setObjectName(u"afternoon_valley_timeEdit")
        self.afternoon_valley_timeEdit.setTime(QTime(15, 0, 0))

        self.horizontalLayout_6.addWidget(self.afternoon_valley_timeEdit)

        self.afternoon_valley_doubleSpinBox = QDoubleSpinBox(self.frame_5)
        self.afternoon_valley_doubleSpinBox.setObjectName(u"afternoon_valley_doubleSpinBox")
        self.afternoon_valley_doubleSpinBox.setDecimals(4)
        self.afternoon_valley_doubleSpinBox.setMaximum(9999999.000000000000000)
        self.afternoon_valley_doubleSpinBox.setValue(8.000000000000000)

        self.horizontalLayout_6.addWidget(self.afternoon_valley_doubleSpinBox)


        self.verticalLayout_4.addWidget(self.frame_5)

        self.frame_6 = QFrame(self.frame_2)
        self.frame_6.setObjectName(u"frame_6")
        self.frame_6.setFrameShape(QFrame.NoFrame)
        self.frame_6.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_7 = QHBoxLayout(self.frame_6)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.label_5 = QLabel(self.frame_6)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setMaximumSize(QSize(160, 16777215))

        self.horizontalLayout_7.addWidget(self.label_5)

        self.evening_peak_timeEdit = QTimeEdit(self.frame_6)
        self.evening_peak_timeEdit.setObjectName(u"evening_peak_timeEdit")
        self.evening_peak_timeEdit.setTime(QTime(20, 0, 0))

        self.horizontalLayout_7.addWidget(self.evening_peak_timeEdit)

        self.evening_peak_doubleSpinBox = QDoubleSpinBox(self.frame_6)
        self.evening_peak_doubleSpinBox.setObjectName(u"evening_peak_doubleSpinBox")
        self.evening_peak_doubleSpinBox.setDecimals(4)
        self.evening_peak_doubleSpinBox.setMaximum(9999999.000000000000000)
        self.evening_peak_doubleSpinBox.setValue(16.000000000000000)

        self.horizontalLayout_7.addWidget(self.evening_peak_doubleSpinBox)


        self.verticalLayout_4.addWidget(self.frame_6)

        self.frame_7 = QFrame(self.frame_2)
        self.frame_7.setObjectName(u"frame_7")
        self.frame_7.setFrameShape(QFrame.NoFrame)
        self.frame_7.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_8 = QHBoxLayout(self.frame_7)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer_2)

        self.draw_by_peak_pushButton = QPushButton(self.frame_7)
        self.draw_by_peak_pushButton.setObjectName(u"draw_by_peak_pushButton")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/gear.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.draw_by_peak_pushButton.setIcon(icon)

        self.horizontalLayout_8.addWidget(self.draw_by_peak_pushButton)


        self.verticalLayout_4.addWidget(self.frame_7)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer)


        self.verticalLayout_3.addWidget(self.frame_2)

        self.toolBox.addItem(self.page_3, u"Definition by peak points")
        self.page = QWidget()
        self.page.setObjectName(u"page")
        self.page.setGeometry(QRect(0, 0, 848, 352))
        self.verticalLayout_2 = QVBoxLayout(self.page)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.tableView = QTableView(self.page)
        self.tableView.setObjectName(u"tableView")

        self.verticalLayout_2.addWidget(self.tableView)

        self.frame = QFrame(self.page)
        self.frame.setObjectName(u"frame")
        self.frame.setMaximumSize(QSize(16777215, 40))
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.draw_by_points_pushButton = QPushButton(self.frame)
        self.draw_by_points_pushButton.setObjectName(u"draw_by_points_pushButton")
        self.draw_by_points_pushButton.setIcon(icon)

        self.horizontalLayout_2.addWidget(self.draw_by_points_pushButton)


        self.verticalLayout_2.addWidget(self.frame)

        self.toolBox.addItem(self.page, u"Definition by data points")

        self.verticalLayout_7.addWidget(self.toolBox)

        self.frame_9 = QFrame(self.frame_8)
        self.frame_9.setObjectName(u"frame_9")
        self.frame_9.setMinimumSize(QSize(0, 150))
        self.frame_9.setFrameShape(QFrame.StyledPanel)
        self.frame_9.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_9 = QHBoxLayout(self.frame_9)
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")

        self.verticalLayout_7.addWidget(self.frame_9)

        self.splitter_3.addWidget(self.frame_8)
        self.PlotFrame = QFrame(self.splitter_3)
        self.PlotFrame.setObjectName(u"PlotFrame")
        self.PlotFrame.setFrameShape(QFrame.NoFrame)
        self.PlotFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.PlotFrame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.plotwidget = MatplotlibWidget(self.PlotFrame)
        self.plotwidget.setObjectName(u"plotwidget")

        self.horizontalLayout.addWidget(self.plotwidget)

        self.splitter_3.addWidget(self.PlotFrame)

        self.verticalLayout.addWidget(self.splitter_3)


        self.retranslateUi(Dialog)

        self.toolBox.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"Night valley", None))
        self.night_valley_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u" MW", None))
        self.label_2.setText(QCoreApplication.translate("Dialog", u"Morning Peak", None))
        self.morning_peak_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u" MW", None))
        self.label_4.setText(QCoreApplication.translate("Dialog", u"Afternoon valley", None))
        self.afternoon_valley_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u" MW", None))
        self.label_5.setText(QCoreApplication.translate("Dialog", u"Evening Peak", None))
        self.evening_peak_doubleSpinBox.setSuffix(QCoreApplication.translate("Dialog", u" MW", None))
        self.draw_by_peak_pushButton.setText("")
        self.toolBox.setItemText(self.toolBox.indexOf(self.page_3), QCoreApplication.translate("Dialog", u"Definition by peak points", None))
        self.draw_by_points_pushButton.setText("")
        self.toolBox.setItemText(self.toolBox.indexOf(self.page), QCoreApplication.translate("Dialog", u"Definition by data points", None))
    # retranslateUi

