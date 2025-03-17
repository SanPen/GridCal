# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tower_builder.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDoubleSpinBox,
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QSplitter, QTableView, QVBoxLayout, QWidget)

from GridCal.Gui.Widgets.matplotlibwidget import MatplotlibWidget
from .icons_rc import *

class Ui_TowerBuilderDialog(object):
    def setupUi(self, TowerBuilderDialog):
        if not TowerBuilderDialog.objectName():
            TowerBuilderDialog.setObjectName(u"TowerBuilderDialog")
        TowerBuilderDialog.resize(934, 714)
        font = QFont()
        font.setPointSize(9)
        TowerBuilderDialog.setFont(font)
        self.verticalLayout_3 = QVBoxLayout(TowerBuilderDialog)
        self.verticalLayout_3.setSpacing(1)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(6, 6, 6, 6)
        self.frame_6 = QFrame(TowerBuilderDialog)
        self.frame_6.setObjectName(u"frame_6")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame_6.sizePolicy().hasHeightForWidth())
        self.frame_6.setSizePolicy(sizePolicy)
        self.frame_6.setMaximumSize(QSize(16777215, 32))
        self.frame_6.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_6.setFrameShadow(QFrame.Shadow.Plain)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_6)
        self.horizontalLayout_3.setSpacing(5)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(1, 1, 1, 1)
        self.label_9 = QLabel(self.frame_6)
        self.label_9.setObjectName(u"label_9")

        self.horizontalLayout_3.addWidget(self.label_9)

        self.name_lineEdit = QLineEdit(self.frame_6)
        self.name_lineEdit.setObjectName(u"name_lineEdit")

        self.horizontalLayout_3.addWidget(self.name_lineEdit)

        self.label_13 = QLabel(self.frame_6)
        self.label_13.setObjectName(u"label_13")

        self.horizontalLayout_3.addWidget(self.label_13)

        self.voltage_doubleSpinBox = QDoubleSpinBox(self.frame_6)
        self.voltage_doubleSpinBox.setObjectName(u"voltage_doubleSpinBox")
        self.voltage_doubleSpinBox.setDecimals(1)
        self.voltage_doubleSpinBox.setMinimum(0.100000000000000)
        self.voltage_doubleSpinBox.setMaximum(100000000.000000000000000)
        self.voltage_doubleSpinBox.setValue(100.000000000000000)

        self.horizontalLayout_3.addWidget(self.voltage_doubleSpinBox)

        self.label_8 = QLabel(self.frame_6)
        self.label_8.setObjectName(u"label_8")

        self.horizontalLayout_3.addWidget(self.label_8)

        self.frequency_doubleSpinBox = QDoubleSpinBox(self.frame_6)
        self.frequency_doubleSpinBox.setObjectName(u"frequency_doubleSpinBox")
        self.frequency_doubleSpinBox.setDecimals(0)
        self.frequency_doubleSpinBox.setValue(50.000000000000000)

        self.horizontalLayout_3.addWidget(self.frequency_doubleSpinBox)

        self.label_11 = QLabel(self.frame_6)
        self.label_11.setObjectName(u"label_11")

        self.horizontalLayout_3.addWidget(self.label_11)

        self.rho_doubleSpinBox = QDoubleSpinBox(self.frame_6)
        self.rho_doubleSpinBox.setObjectName(u"rho_doubleSpinBox")
        self.rho_doubleSpinBox.setMaximum(9999999.000000000000000)
        self.rho_doubleSpinBox.setValue(100.000000000000000)

        self.horizontalLayout_3.addWidget(self.rho_doubleSpinBox)


        self.verticalLayout_3.addWidget(self.frame_6)

        self.main_splitter = QSplitter(TowerBuilderDialog)
        self.main_splitter.setObjectName(u"main_splitter")
        self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
        self.frame_8 = QFrame(self.main_splitter)
        self.frame_8.setObjectName(u"frame_8")
        self.frame_8.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_8.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame_8)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(1, 1, 1, 1)
        self.splitter = QSplitter(self.frame_8)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Vertical)
        self.frame_3 = QFrame(self.splitter)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_8 = QVBoxLayout(self.frame_3)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.verticalLayout_8.setContentsMargins(1, 1, 1, 1)
        self.label_12 = QLabel(self.frame_3)
        self.label_12.setObjectName(u"label_12")

        self.verticalLayout_8.addWidget(self.label_12)

        self.wires_tableView = QTableView(self.frame_3)
        self.wires_tableView.setObjectName(u"wires_tableView")

        self.verticalLayout_8.addWidget(self.wires_tableView)

        self.splitter.addWidget(self.frame_3)
        self.frame_4 = QFrame(self.splitter)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.frame_4)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(1, 1, 1, 1)
        self.frame = QFrame(self.frame_4)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.label_10 = QLabel(self.frame)
        self.label_10.setObjectName(u"label_10")

        self.horizontalLayout_2.addWidget(self.label_10)

        self.add_to_tower_pushButton = QPushButton(self.frame)
        self.add_to_tower_pushButton.setObjectName(u"add_to_tower_pushButton")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/plus.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.add_to_tower_pushButton.setIcon(icon)

        self.horizontalLayout_2.addWidget(self.add_to_tower_pushButton)

        self.delete_from_tower_pushButton = QPushButton(self.frame)
        self.delete_from_tower_pushButton.setObjectName(u"delete_from_tower_pushButton")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/minus.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.delete_from_tower_pushButton.setIcon(icon1)

        self.horizontalLayout_2.addWidget(self.delete_from_tower_pushButton)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)


        self.verticalLayout_4.addWidget(self.frame)

        self.tower_tableView = QTableView(self.frame_4)
        self.tower_tableView.setObjectName(u"tower_tableView")

        self.verticalLayout_4.addWidget(self.tower_tableView)

        self.splitter.addWidget(self.frame_4)
        self.frame_2 = QFrame(self.splitter)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout = QVBoxLayout(self.frame_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(1, 1, 1, 1)
        self.frame_7 = QFrame(self.frame_2)
        self.frame_7.setObjectName(u"frame_7")
        self.frame_7.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_7.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.frame_7)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(1, 1, 1, 1)
        self.label = QLabel(self.frame_7)
        self.label.setObjectName(u"label")

        self.horizontalLayout_4.addWidget(self.label)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_4.addItem(self.horizontalSpacer_3)

        self.matrixViewComboBox = QComboBox(self.frame_7)
        self.matrixViewComboBox.setObjectName(u"matrixViewComboBox")

        self.horizontalLayout_4.addWidget(self.matrixViewComboBox)


        self.verticalLayout.addWidget(self.frame_7)

        self.matrixTableView = QTableView(self.frame_2)
        self.matrixTableView.setObjectName(u"matrixTableView")

        self.verticalLayout.addWidget(self.matrixTableView)

        self.splitter.addWidget(self.frame_2)

        self.verticalLayout_2.addWidget(self.splitter)

        self.main_splitter.addWidget(self.frame_8)
        self.PlotFrame = QFrame(self.main_splitter)
        self.PlotFrame.setObjectName(u"PlotFrame")
        self.PlotFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.PlotFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_7 = QVBoxLayout(self.PlotFrame)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(1, 1, 1, 1)
        self.label_4 = QLabel(self.PlotFrame)
        self.label_4.setObjectName(u"label_4")

        self.verticalLayout_7.addWidget(self.label_4)

        self.plotwidget = MatplotlibWidget(self.PlotFrame)
        self.plotwidget.setObjectName(u"plotwidget")

        self.verticalLayout_7.addWidget(self.plotwidget)

        self.frame_9 = QFrame(self.PlotFrame)
        self.frame_9.setObjectName(u"frame_9")
        self.frame_9.setMaximumSize(QSize(16777215, 24))
        self.frame_9.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_9.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.frame_9)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.compute_pushButton = QPushButton(self.frame_9)
        self.compute_pushButton.setObjectName(u"compute_pushButton")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/calc.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.compute_pushButton.setIcon(icon2)
        self.compute_pushButton.setIconSize(QSize(16, 16))

        self.horizontalLayout_5.addWidget(self.compute_pushButton)

        self.horizontalSpacer_4 = QSpacerItem(19, 19, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_4)

        self.acceptButton = QPushButton(self.frame_9)
        self.acceptButton.setObjectName(u"acceptButton")

        self.horizontalLayout_5.addWidget(self.acceptButton)


        self.verticalLayout_7.addWidget(self.frame_9)

        self.main_splitter.addWidget(self.PlotFrame)

        self.verticalLayout_3.addWidget(self.main_splitter)


        self.retranslateUi(TowerBuilderDialog)

        QMetaObject.connectSlotsByName(TowerBuilderDialog)
    # setupUi

    def retranslateUi(self, TowerBuilderDialog):
        TowerBuilderDialog.setWindowTitle(QCoreApplication.translate("TowerBuilderDialog", u"Tower creation", None))
        self.label_9.setText(QCoreApplication.translate("TowerBuilderDialog", u"Name", None))
        self.label_13.setText(QCoreApplication.translate("TowerBuilderDialog", u"Voltage", None))
        self.voltage_doubleSpinBox.setSuffix(QCoreApplication.translate("TowerBuilderDialog", u" kV", None))
        self.label_8.setText(QCoreApplication.translate("TowerBuilderDialog", u"Frequency", None))
        self.frequency_doubleSpinBox.setSuffix(QCoreApplication.translate("TowerBuilderDialog", u" Hz", None))
        self.label_11.setText(QCoreApplication.translate("TowerBuilderDialog", u"Earth resistivity", None))
        self.rho_doubleSpinBox.setSuffix(QCoreApplication.translate("TowerBuilderDialog", u" \u03a9/m^3", None))
        self.label_12.setText(QCoreApplication.translate("TowerBuilderDialog", u"Wire catalogue", None))
        self.label_10.setText(QCoreApplication.translate("TowerBuilderDialog", u"Wire composition", None))
#if QT_CONFIG(tooltip)
        self.add_to_tower_pushButton.setToolTip(QCoreApplication.translate("TowerBuilderDialog", u"Add wire", None))
#endif // QT_CONFIG(tooltip)
        self.add_to_tower_pushButton.setText("")
#if QT_CONFIG(tooltip)
        self.delete_from_tower_pushButton.setToolTip(QCoreApplication.translate("TowerBuilderDialog", u"Delete wire", None))
#endif // QT_CONFIG(tooltip)
        self.delete_from_tower_pushButton.setText("")
        self.label.setText(QCoreApplication.translate("TowerBuilderDialog", u"Matrix", None))
        self.label_4.setText(QCoreApplication.translate("TowerBuilderDialog", u"Tower", None))
#if QT_CONFIG(tooltip)
        self.compute_pushButton.setToolTip(QCoreApplication.translate("TowerBuilderDialog", u"Compute matrices", None))
#endif // QT_CONFIG(tooltip)
        self.compute_pushButton.setText("")
        self.acceptButton.setText(QCoreApplication.translate("TowerBuilderDialog", u"Accept", None))
    # retranslateUi

