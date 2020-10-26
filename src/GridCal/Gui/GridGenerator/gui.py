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

from .matplotlibwidget import MatplotlibWidget

from .icons_rc import *

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(841, 518)
        icon = QIcon()
        icon.addFile(u":/Icons/icons/automatic_layout.svg", QSize(), QIcon.Normal, QIcon.Off)
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
        self.verticalLayout_2 = QVBoxLayout(MainWindow)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.splitter_3 = QSplitter(MainWindow)
        self.splitter_3.setObjectName(u"splitter_3")
        self.splitter_3.setOrientation(Qt.Horizontal)
        self.frame_8 = QFrame(self.splitter_3)
        self.frame_8.setObjectName(u"frame_8")
        self.frame_8.setMaximumSize(QSize(400, 16777215))
        self.frame_8.setFrameShape(QFrame.NoFrame)
        self.frame_8.setFrameShadow(QFrame.Raised)
        self.verticalLayout_7 = QVBoxLayout(self.frame_8)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(-1, 0, -1, -1)
        self.frame = QFrame(self.frame_8)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.gridLayout = QGridLayout(self.frame)
        self.gridLayout.setObjectName(u"gridLayout")
        self.power_SpinBox = QDoubleSpinBox(self.frame)
        self.power_SpinBox.setObjectName(u"power_SpinBox")
        self.power_SpinBox.setMaximum(9999999.000000000000000)
        self.power_SpinBox.setValue(100.000000000000000)

        self.gridLayout.addWidget(self.power_SpinBox, 7, 1, 1, 1)

        self.label_9 = QLabel(self.frame)
        self.label_9.setObjectName(u"label_9")
        palette = QPalette()
        brush = QBrush(QColor(136, 138, 133, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.WindowText, brush)
        palette.setBrush(QPalette.Active, QPalette.Text, brush)
        palette.setBrush(QPalette.Active, QPalette.ButtonText, brush)
        brush1 = QBrush(QColor(136, 138, 133, 128))
        brush1.setStyle(Qt.SolidPattern)
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
        palette.setBrush(QPalette.Active, QPalette.PlaceholderText, brush1)
#endif
        palette.setBrush(QPalette.Inactive, QPalette.WindowText, brush)
        palette.setBrush(QPalette.Inactive, QPalette.Text, brush)
        palette.setBrush(QPalette.Inactive, QPalette.ButtonText, brush)
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
        palette.setBrush(QPalette.Inactive, QPalette.PlaceholderText, brush1)
#endif
        brush2 = QBrush(QColor(190, 190, 190, 255))
        brush2.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Disabled, QPalette.WindowText, brush2)
        palette.setBrush(QPalette.Disabled, QPalette.Text, brush2)
        palette.setBrush(QPalette.Disabled, QPalette.ButtonText, brush2)
        brush3 = QBrush(QColor(0, 0, 0, 128))
        brush3.setStyle(Qt.SolidPattern)
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
        palette.setBrush(QPalette.Disabled, QPalette.PlaceholderText, brush3)
#endif
        self.label_9.setPalette(palette)
        font = QFont()
        font.setPointSize(16)
        self.label_9.setFont(font)

        self.gridLayout.addWidget(self.label_9, 0, 0, 1, 1)

        self.b_SpinBox = QDoubleSpinBox(self.frame)
        self.b_SpinBox.setObjectName(u"b_SpinBox")
        self.b_SpinBox.setDecimals(6)
        self.b_SpinBox.setValue(0.000010000000000)

        self.gridLayout.addWidget(self.b_SpinBox, 10, 1, 1, 1)

        self.label_2 = QLabel(self.frame)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 7, 0, 1, 1)

        self.r_SpinBox = QDoubleSpinBox(self.frame)
        self.r_SpinBox.setObjectName(u"r_SpinBox")
        self.r_SpinBox.setDecimals(6)
        self.r_SpinBox.setValue(0.000100000000000)

        self.gridLayout.addWidget(self.r_SpinBox, 8, 1, 1, 1)

        self.label_3 = QLabel(self.frame)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 1, 0, 1, 1)

        self.label_6 = QLabel(self.frame)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout.addWidget(self.label_6, 10, 0, 1, 1)

        self.x_SpinBox = QDoubleSpinBox(self.frame)
        self.x_SpinBox.setObjectName(u"x_SpinBox")
        self.x_SpinBox.setDecimals(6)
        self.x_SpinBox.setValue(0.001000000000000)

        self.gridLayout.addWidget(self.x_SpinBox, 9, 1, 1, 1)

        self.load_nodes_SpinBox = QDoubleSpinBox(self.frame)
        self.load_nodes_SpinBox.setObjectName(u"load_nodes_SpinBox")
        self.load_nodes_SpinBox.setDecimals(1)
        self.load_nodes_SpinBox.setMinimum(1.000000000000000)
        self.load_nodes_SpinBox.setMaximum(100.000000000000000)
        self.load_nodes_SpinBox.setValue(50.000000000000000)

        self.gridLayout.addWidget(self.load_nodes_SpinBox, 5, 1, 1, 1)

        self.label_4 = QLabel(self.frame)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout.addWidget(self.label_4, 8, 0, 1, 1)

        self.ratio_SpinBox = QDoubleSpinBox(self.frame)
        self.ratio_SpinBox.setObjectName(u"ratio_SpinBox")
        self.ratio_SpinBox.setDecimals(4)
        self.ratio_SpinBox.setMinimum(0.000000000000000)
        self.ratio_SpinBox.setMaximum(1.000000000000000)
        self.ratio_SpinBox.setValue(0.333000000000000)

        self.gridLayout.addWidget(self.ratio_SpinBox, 2, 1, 1, 1)

        self.label_11 = QLabel(self.frame)
        self.label_11.setObjectName(u"label_11")

        self.gridLayout.addWidget(self.label_11, 2, 0, 1, 1)

        self.nodes_spinBox = QSpinBox(self.frame)
        self.nodes_spinBox.setObjectName(u"nodes_spinBox")
        self.nodes_spinBox.setMinimum(2)
        self.nodes_spinBox.setMaximum(999999999)
        self.nodes_spinBox.setValue(100)

        self.gridLayout.addWidget(self.nodes_spinBox, 1, 1, 1, 1)

        self.label_10 = QLabel(self.frame)
        self.label_10.setObjectName(u"label_10")
        palette1 = QPalette()
        palette1.setBrush(QPalette.Active, QPalette.WindowText, brush)
        palette1.setBrush(QPalette.Active, QPalette.Text, brush)
        palette1.setBrush(QPalette.Active, QPalette.ButtonText, brush)
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
        palette1.setBrush(QPalette.Active, QPalette.PlaceholderText, brush1)
#endif
        palette1.setBrush(QPalette.Inactive, QPalette.WindowText, brush)
        palette1.setBrush(QPalette.Inactive, QPalette.Text, brush)
        palette1.setBrush(QPalette.Inactive, QPalette.ButtonText, brush)
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
        palette1.setBrush(QPalette.Inactive, QPalette.PlaceholderText, brush1)
#endif
        palette1.setBrush(QPalette.Disabled, QPalette.WindowText, brush2)
        palette1.setBrush(QPalette.Disabled, QPalette.Text, brush2)
        palette1.setBrush(QPalette.Disabled, QPalette.ButtonText, brush2)
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
        palette1.setBrush(QPalette.Disabled, QPalette.PlaceholderText, brush3)
#endif
        self.label_10.setPalette(palette1)
        self.label_10.setFont(font)

        self.gridLayout.addWidget(self.label_10, 3, 0, 1, 1)

        self.label_8 = QLabel(self.frame)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout.addWidget(self.label_8, 5, 0, 1, 1)

        self.generation_nodes_SpinBox = QDoubleSpinBox(self.frame)
        self.generation_nodes_SpinBox.setObjectName(u"generation_nodes_SpinBox")
        self.generation_nodes_SpinBox.setDecimals(1)
        self.generation_nodes_SpinBox.setMinimum(1.000000000000000)
        self.generation_nodes_SpinBox.setMaximum(100.000000000000000)
        self.generation_nodes_SpinBox.setValue(30.000000000000000)

        self.gridLayout.addWidget(self.generation_nodes_SpinBox, 4, 1, 1, 1)

        self.label_7 = QLabel(self.frame)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout.addWidget(self.label_7, 4, 0, 1, 1)

        self.label_5 = QLabel(self.frame)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout.addWidget(self.label_5, 9, 0, 1, 1)

        self.label_12 = QLabel(self.frame)
        self.label_12.setObjectName(u"label_12")

        self.gridLayout.addWidget(self.label_12, 6, 0, 1, 1)

        self.power_factor_SpinBox = QDoubleSpinBox(self.frame)
        self.power_factor_SpinBox.setObjectName(u"power_factor_SpinBox")
        self.power_factor_SpinBox.setMaximum(1.000000000000000)
        self.power_factor_SpinBox.setValue(0.800000000000000)

        self.gridLayout.addWidget(self.power_factor_SpinBox, 6, 1, 1, 1)


        self.verticalLayout_7.addWidget(self.frame)

        self.frame_2 = QFrame(self.frame_8)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.applyButton = QPushButton(self.frame_2)
        self.applyButton.setObjectName(u"applyButton")
        self.applyButton.setMinimumSize(QSize(24, 24))
        icon3 = QIcon()
        icon3.addFile(u":/Icons/icons/color_grid.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.applyButton.setIcon(icon3)

        self.horizontalLayout_2.addWidget(self.applyButton)

        self.previewButton = QPushButton(self.frame_2)
        self.previewButton.setObjectName(u"previewButton")
        self.previewButton.setMinimumSize(QSize(24, 24))
        icon4 = QIcon()
        icon4.addFile(u":/Icons/icons/run_cascade_step.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.previewButton.setIcon(icon4)

        self.horizontalLayout_2.addWidget(self.previewButton)

        self.horizontalSpacer = QSpacerItem(543, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)


        self.verticalLayout_7.addWidget(self.frame_2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_7.addItem(self.verticalSpacer)

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


        self.verticalLayout_2.addLayout(self.verticalLayout)


        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.actionCopy_to_clipboard.setText(QCoreApplication.translate("MainWindow", u"Copy to clipboard", None))
        self.actionSave.setText(QCoreApplication.translate("MainWindow", u"Save", None))
        self.power_SpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" MW", None))
        self.label_9.setText(QCoreApplication.translate("MainWindow", u"Graph", None))
        self.b_SpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" p.u./km", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Grid power", None))
        self.r_SpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" p.u./km", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"Number of nodes", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"Susceptance (B)", None))
        self.x_SpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" p.u./km", None))
        self.load_nodes_SpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" %", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Resistance (R)", None))
        self.label_11.setText(QCoreApplication.translate("MainWindow", u"Expansion ratio", None))
        self.nodes_spinBox.setSuffix(QCoreApplication.translate("MainWindow", u" nodes", None))
        self.label_10.setText(QCoreApplication.translate("MainWindow", u"Devices", None))
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"Load nodes", None))
        self.generation_nodes_SpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" %", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"Generation nodes", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Reactance(X) ", None))
        self.label_12.setText(QCoreApplication.translate("MainWindow", u"Power factor", None))
#if QT_CONFIG(tooltip)
        self.applyButton.setToolTip(QCoreApplication.translate("MainWindow", u"Create Grid", None))
#endif // QT_CONFIG(tooltip)
        self.applyButton.setText("")
#if QT_CONFIG(tooltip)
        self.previewButton.setToolTip(QCoreApplication.translate("MainWindow", u"Preview", None))
#endif // QT_CONFIG(tooltip)
        self.previewButton.setText("")
    # retranslateUi

