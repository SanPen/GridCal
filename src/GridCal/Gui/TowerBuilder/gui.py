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
from PySide6.QtWidgets import (QApplication, QDialog, QDoubleSpinBox, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QSplitter, QTabWidget, QTableView, QVBoxLayout,
    QWidget)

from GridCal.Gui.Widgets.matplotlibwidget import MatplotlibWidget
from .icons_rc import *

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(1183, 675)
        self.gridLayout = QGridLayout(Dialog)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(1, 1, 1, 1)
        self.tabWidget = QTabWidget(Dialog)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.verticalLayout_6 = QVBoxLayout(self.tab_2)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.main_splitter = QSplitter(self.tab_2)
        self.main_splitter.setObjectName(u"main_splitter")
        self.main_splitter.setOrientation(Qt.Horizontal)
        self.frame_8 = QFrame(self.main_splitter)
        self.frame_8.setObjectName(u"frame_8")
        self.frame_8.setFrameShape(QFrame.NoFrame)
        self.frame_8.setFrameShadow(QFrame.Raised)
        self.verticalLayout_5 = QVBoxLayout(self.frame_8)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.frame_5 = QFrame(self.frame_8)
        self.frame_5.setObjectName(u"frame_5")
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame_5.sizePolicy().hasHeightForWidth())
        self.frame_5.setSizePolicy(sizePolicy)
        self.frame_5.setFrameShape(QFrame.NoFrame)
        self.frame_5.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame_5)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label_9 = QLabel(self.frame_5)
        self.label_9.setObjectName(u"label_9")

        self.horizontalLayout.addWidget(self.label_9)

        self.name_lineEdit = QLineEdit(self.frame_5)
        self.name_lineEdit.setObjectName(u"name_lineEdit")

        self.horizontalLayout.addWidget(self.name_lineEdit)


        self.verticalLayout_5.addWidget(self.frame_5)

        self.frame_6 = QFrame(self.frame_8)
        self.frame_6.setObjectName(u"frame_6")
        sizePolicy.setHeightForWidth(self.frame_6.sizePolicy().hasHeightForWidth())
        self.frame_6.setSizePolicy(sizePolicy)
        self.frame_6.setFrameShape(QFrame.NoFrame)
        self.frame_6.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_6)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)

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


        self.verticalLayout_5.addWidget(self.frame_6)

        self.splitter = QSplitter(self.frame_8)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setMaximumSize(QSize(16777215, 16777215))
        self.splitter.setOrientation(Qt.Vertical)
        self.frame_3 = QFrame(self.splitter)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setFrameShape(QFrame.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.verticalLayout_8 = QVBoxLayout(self.frame_3)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.label_12 = QLabel(self.frame_3)
        self.label_12.setObjectName(u"label_12")

        self.verticalLayout_8.addWidget(self.label_12)

        self.wires_tableView = QTableView(self.frame_3)
        self.wires_tableView.setObjectName(u"wires_tableView")

        self.verticalLayout_8.addWidget(self.wires_tableView)

        self.frame_7 = QFrame(self.frame_3)
        self.frame_7.setObjectName(u"frame_7")
        self.frame_7.setFrameShape(QFrame.StyledPanel)
        self.frame_7.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.frame_7)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.add_to_tower_pushButton = QPushButton(self.frame_7)
        self.add_to_tower_pushButton.setObjectName(u"add_to_tower_pushButton")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/plus.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.add_to_tower_pushButton.setIcon(icon)

        self.horizontalLayout_4.addWidget(self.add_to_tower_pushButton)

        self.horizontalSpacer_3 = QSpacerItem(990, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_4.addItem(self.horizontalSpacer_3)


        self.verticalLayout_8.addWidget(self.frame_7)

        self.splitter.addWidget(self.frame_3)
        self.frame_4 = QFrame(self.splitter)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.frame_4)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(9, 9, 9, 9)
        self.label_10 = QLabel(self.frame_4)
        self.label_10.setObjectName(u"label_10")

        self.verticalLayout_4.addWidget(self.label_10)

        self.tower_tableView = QTableView(self.frame_4)
        self.tower_tableView.setObjectName(u"tower_tableView")

        self.verticalLayout_4.addWidget(self.tower_tableView)

        self.frame = QFrame(self.frame_4)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.delete_from_tower_pushButton = QPushButton(self.frame)
        self.delete_from_tower_pushButton.setObjectName(u"delete_from_tower_pushButton")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/minus.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.delete_from_tower_pushButton.setIcon(icon1)

        self.horizontalLayout_2.addWidget(self.delete_from_tower_pushButton)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.compute_pushButton = QPushButton(self.frame)
        self.compute_pushButton.setObjectName(u"compute_pushButton")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/calc.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.compute_pushButton.setIcon(icon2)
        self.compute_pushButton.setIconSize(QSize(16, 16))

        self.horizontalLayout_2.addWidget(self.compute_pushButton)


        self.verticalLayout_4.addWidget(self.frame)

        self.splitter.addWidget(self.frame_4)

        self.verticalLayout_5.addWidget(self.splitter)

        self.main_splitter.addWidget(self.frame_8)
        self.PlotFrame = QFrame(self.main_splitter)
        self.PlotFrame.setObjectName(u"PlotFrame")
        self.PlotFrame.setFrameShape(QFrame.NoFrame)
        self.PlotFrame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_7 = QVBoxLayout(self.PlotFrame)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(9, 9, 9, 9)
        self.label_4 = QLabel(self.PlotFrame)
        self.label_4.setObjectName(u"label_4")

        self.verticalLayout_7.addWidget(self.label_4)

        self.plotwidget = MatplotlibWidget(self.PlotFrame)
        self.plotwidget.setObjectName(u"plotwidget")

        self.verticalLayout_7.addWidget(self.plotwidget)

        self.frame_9 = QFrame(self.PlotFrame)
        self.frame_9.setObjectName(u"frame_9")
        self.frame_9.setMaximumSize(QSize(16777215, 24))
        self.frame_9.setFrameShape(QFrame.StyledPanel)
        self.frame_9.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.frame_9)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_4 = QSpacerItem(19, 19, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_4)

        self.acceptButton = QPushButton(self.frame_9)
        self.acceptButton.setObjectName(u"acceptButton")

        self.horizontalLayout_5.addWidget(self.acceptButton)


        self.verticalLayout_7.addWidget(self.frame_9)

        self.main_splitter.addWidget(self.PlotFrame)

        self.verticalLayout_6.addWidget(self.main_splitter)

        self.tabWidget.addTab(self.tab_2, "")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.verticalLayout_3 = QVBoxLayout(self.tab)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.frame_10 = QFrame(self.tab)
        self.frame_10.setObjectName(u"frame_10")
        self.frame_10.setFrameShape(QFrame.StyledPanel)
        self.frame_10.setFrameShadow(QFrame.Raised)
        self.gridLayout_2 = QGridLayout(self.frame_10)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.label_2 = QLabel(self.frame_10)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_2.addWidget(self.label_2, 0, 1, 1, 1)

        self.label_6 = QLabel(self.frame_10)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_2.addWidget(self.label_6, 2, 0, 1, 1)

        self.z_tableView_abcn = QTableView(self.frame_10)
        self.z_tableView_abcn.setObjectName(u"z_tableView_abcn")

        self.gridLayout_2.addWidget(self.z_tableView_abcn, 1, 0, 1, 1)

        self.y_tableView_abcn = QTableView(self.frame_10)
        self.y_tableView_abcn.setObjectName(u"y_tableView_abcn")

        self.gridLayout_2.addWidget(self.y_tableView_abcn, 1, 1, 1, 1)

        self.label_7 = QLabel(self.frame_10)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout_2.addWidget(self.label_7, 4, 0, 1, 1)

        self.z_tableView_abc = QTableView(self.frame_10)
        self.z_tableView_abc.setObjectName(u"z_tableView_abc")

        self.gridLayout_2.addWidget(self.z_tableView_abc, 3, 0, 1, 1)

        self.label = QLabel(self.frame_10)
        self.label.setObjectName(u"label")

        self.gridLayout_2.addWidget(self.label, 0, 0, 1, 1)

        self.z_tableView_seq = QTableView(self.frame_10)
        self.z_tableView_seq.setObjectName(u"z_tableView_seq")

        self.gridLayout_2.addWidget(self.z_tableView_seq, 5, 0, 1, 1)

        self.label_3 = QLabel(self.frame_10)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_2.addWidget(self.label_3, 2, 1, 1, 1)

        self.y_tableView_abc = QTableView(self.frame_10)
        self.y_tableView_abc.setObjectName(u"y_tableView_abc")

        self.gridLayout_2.addWidget(self.y_tableView_abc, 3, 1, 1, 1)

        self.label_5 = QLabel(self.frame_10)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_2.addWidget(self.label_5, 4, 1, 1, 1)

        self.y_tableView_seq = QTableView(self.frame_10)
        self.y_tableView_seq.setObjectName(u"y_tableView_seq")

        self.gridLayout_2.addWidget(self.y_tableView_seq, 5, 1, 1, 1)


        self.verticalLayout_3.addWidget(self.frame_10)

        self.tabWidget.addTab(self.tab, "")

        self.gridLayout.addWidget(self.tabWidget, 4, 0, 1, 1)


        self.retranslateUi(Dialog)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Tower creation", None))
        self.label_9.setText(QCoreApplication.translate("Dialog", u"Name", None))
        self.label_8.setText(QCoreApplication.translate("Dialog", u"Frequency (Hz)", None))
        self.label_11.setText(QCoreApplication.translate("Dialog", u"Earth resistivity (Ohm/m^3)", None))
        self.label_12.setText(QCoreApplication.translate("Dialog", u"Wire catalogue", None))
#if QT_CONFIG(tooltip)
        self.add_to_tower_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Add wire", None))
#endif // QT_CONFIG(tooltip)
        self.add_to_tower_pushButton.setText("")
        self.label_10.setText(QCoreApplication.translate("Dialog", u"Wire compisition", None))
#if QT_CONFIG(tooltip)
        self.delete_from_tower_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Delete wire", None))
#endif // QT_CONFIG(tooltip)
        self.delete_from_tower_pushButton.setText("")
#if QT_CONFIG(tooltip)
        self.compute_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Compute matrices", None))
#endif // QT_CONFIG(tooltip)
        self.compute_pushButton.setText("")
        self.label_4.setText(QCoreApplication.translate("Dialog", u"Tower", None))
        self.acceptButton.setText(QCoreApplication.translate("Dialog", u"Accept", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("Dialog", u"Tower designer", None))
        self.label_2.setText(QCoreApplication.translate("Dialog", u"   Y shunt (uS / km) for ABCN", None))
        self.label_6.setText(QCoreApplication.translate("Dialog", u"   Z series (Ohm / km) for ABC", None))
        self.label_7.setText(QCoreApplication.translate("Dialog", u"   Z series (Ohm / km) in sequence components", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"   Z series (Ohm / km) for ABCN", None))
        self.label_3.setText(QCoreApplication.translate("Dialog", u"   Y shunt (uS / km) for ABC", None))
        self.label_5.setText(QCoreApplication.translate("Dialog", u"   Y shunt (uS / km) for the sequence components", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("Dialog", u"Impedance matrices", None))
    # retranslateUi

