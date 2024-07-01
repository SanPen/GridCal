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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDoubleSpinBox, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QSizePolicy, QSpacerItem, QStatusBar,
    QTabWidget, QToolBar, QTreeView, QVBoxLayout,
    QWidget)
from .icons_rc import *

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(912, 540)
        icon = QIcon()
        icon.addFile(u":/icons/icons/inputs_analysis 2.svg", QSize(), QIcon.Normal, QIcon.Off)
        MainWindow.setWindowIcon(icon)
        self.actionSave_diagnostic = QAction(MainWindow)
        self.actionSave_diagnostic.setObjectName(u"actionSave_diagnostic")
        icon1 = QIcon()
        icon1.addFile(u":/icons/icons/savec.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionSave_diagnostic.setIcon(icon1)
        self.actionFix_issues = QAction(MainWindow)
        self.actionFix_issues.setObjectName(u"actionFix_issues")
        icon2 = QIcon()
        icon2.addFile(u":/icons/icons/fix.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.actionFix_issues.setIcon(icon2)
        self.actionAnalyze = QAction(MainWindow)
        self.actionAnalyze.setObjectName(u"actionAnalyze")
        self.actionAnalyze.setIcon(icon)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout_2 = QVBoxLayout(self.centralwidget)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.verticalLayout = QVBoxLayout(self.tab)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.logsTreeView = QTreeView(self.tab)
        self.logsTreeView.setObjectName(u"logsTreeView")
        self.logsTreeView.setFrameShape(QFrame.NoFrame)

        self.verticalLayout.addWidget(self.logsTreeView)

        self.tabWidget.addTab(self.tab, icon, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.horizontalLayout = QHBoxLayout(self.tab_2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.frame = QFrame(self.tab_2)
        self.frame.setObjectName(u"frame")
        self.frame.setMaximumSize(QSize(400, 16777215))
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.gridLayout = QGridLayout(self.frame)
        self.gridLayout.setObjectName(u"gridLayout")
        self.label_4 = QLabel(self.frame)
        self.label_4.setObjectName(u"label_4")
        palette = QPalette()
        brush = QBrush(QColor(119, 118, 123, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.WindowText, brush)
        palette.setBrush(QPalette.Active, QPalette.Text, brush)
        palette.setBrush(QPalette.Active, QPalette.ButtonText, brush)
        brush1 = QBrush(QColor(0, 0, 0, 255))
        brush1.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Inactive, QPalette.WindowText, brush1)
        palette.setBrush(QPalette.Inactive, QPalette.Text, brush1)
        palette.setBrush(QPalette.Inactive, QPalette.ButtonText, brush1)
        brush2 = QBrush(QColor(190, 190, 190, 255))
        brush2.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Disabled, QPalette.WindowText, brush2)
        palette.setBrush(QPalette.Disabled, QPalette.Text, brush2)
        palette.setBrush(QPalette.Disabled, QPalette.ButtonText, brush2)
        self.label_4.setPalette(palette)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.label_4.setFont(font)

        self.gridLayout.addWidget(self.label_4, 3, 0, 1, 1)

        self.label_5 = QLabel(self.frame)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout.addWidget(self.label_5, 11, 0, 1, 1)

        self.transformerVccMaxSpinBox = QDoubleSpinBox(self.frame)
        self.transformerVccMaxSpinBox.setObjectName(u"transformerVccMaxSpinBox")
        self.transformerVccMaxSpinBox.setDecimals(1)
        self.transformerVccMaxSpinBox.setValue(20.000000000000000)

        self.gridLayout.addWidget(self.transformerVccMaxSpinBox, 11, 2, 1, 1)

        self.label = QLabel(self.frame)
        self.label.setObjectName(u"label")

        self.gridLayout.addWidget(self.label, 1, 0, 1, 1)

        self.virtualTapToleranceSpinBox = QDoubleSpinBox(self.frame)
        self.virtualTapToleranceSpinBox.setObjectName(u"virtualTapToleranceSpinBox")
        self.virtualTapToleranceSpinBox.setDecimals(1)
        self.virtualTapToleranceSpinBox.setMaximum(9999.000000000000000)
        self.virtualTapToleranceSpinBox.setValue(10.000000000000000)

        self.gridLayout.addWidget(self.virtualTapToleranceSpinBox, 9, 1, 1, 2)

        self.label_3 = QLabel(self.frame)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 7, 0, 1, 1)

        self.label_12 = QLabel(self.frame)
        self.label_12.setObjectName(u"label_12")
        palette1 = QPalette()
        palette1.setBrush(QPalette.Active, QPalette.WindowText, brush)
        palette1.setBrush(QPalette.Active, QPalette.Text, brush)
        palette1.setBrush(QPalette.Active, QPalette.ButtonText, brush)
        palette1.setBrush(QPalette.Inactive, QPalette.WindowText, brush1)
        palette1.setBrush(QPalette.Inactive, QPalette.Text, brush1)
        palette1.setBrush(QPalette.Inactive, QPalette.ButtonText, brush1)
        palette1.setBrush(QPalette.Disabled, QPalette.WindowText, brush2)
        palette1.setBrush(QPalette.Disabled, QPalette.Text, brush2)
        palette1.setBrush(QPalette.Disabled, QPalette.ButtonText, brush2)
        self.label_12.setPalette(palette1)
        self.label_12.setFont(font)

        self.gridLayout.addWidget(self.label_12, 0, 0, 1, 1)

        self.label_11 = QLabel(self.frame)
        self.label_11.setObjectName(u"label_11")

        self.gridLayout.addWidget(self.label_11, 2, 0, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 94, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 15, 1, 1, 2)

        self.transformerTapAngleMaxSpinBox = QDoubleSpinBox(self.frame)
        self.transformerTapAngleMaxSpinBox.setObjectName(u"transformerTapAngleMaxSpinBox")
        self.transformerTapAngleMaxSpinBox.setMinimum(-99.000000000000000)
        self.transformerTapAngleMaxSpinBox.setValue(3.140000000000000)

        self.gridLayout.addWidget(self.transformerTapAngleMaxSpinBox, 7, 2, 1, 1)

        self.transformerTapAngleMinSpinBox = QDoubleSpinBox(self.frame)
        self.transformerTapAngleMinSpinBox.setObjectName(u"transformerTapAngleMinSpinBox")
        self.transformerTapAngleMinSpinBox.setMinimum(-99999.000000000000000)
        self.transformerTapAngleMinSpinBox.setMaximum(99999.000000000000000)
        self.transformerTapAngleMinSpinBox.setValue(-3.140000000000000)

        self.gridLayout.addWidget(self.transformerTapAngleMinSpinBox, 7, 1, 1, 1)

        self.label_2 = QLabel(self.frame)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 5, 0, 1, 1)

        self.label_15 = QLabel(self.frame)
        self.label_15.setObjectName(u"label_15")

        self.gridLayout.addWidget(self.label_15, 14, 0, 1, 1)

        self.transformerTapModuleMinSpinBox = QDoubleSpinBox(self.frame)
        self.transformerTapModuleMinSpinBox.setObjectName(u"transformerTapModuleMinSpinBox")
        self.transformerTapModuleMinSpinBox.setValue(0.950000000000000)

        self.gridLayout.addWidget(self.transformerTapModuleMinSpinBox, 5, 1, 1, 1)

        self.lineNominalVoltageToleranceSpinBox = QDoubleSpinBox(self.frame)
        self.lineNominalVoltageToleranceSpinBox.setObjectName(u"lineNominalVoltageToleranceSpinBox")
        self.lineNominalVoltageToleranceSpinBox.setDecimals(1)
        self.lineNominalVoltageToleranceSpinBox.setMaximum(9999.000000000000000)
        self.lineNominalVoltageToleranceSpinBox.setValue(10.000000000000000)

        self.gridLayout.addWidget(self.lineNominalVoltageToleranceSpinBox, 14, 1, 1, 2)

        self.label_13 = QLabel(self.frame)
        self.label_13.setObjectName(u"label_13")

        self.gridLayout.addWidget(self.label_13, 12, 1, 1, 1)

        self.label_14 = QLabel(self.frame)
        self.label_14.setObjectName(u"label_14")
        palette2 = QPalette()
        palette2.setBrush(QPalette.Active, QPalette.WindowText, brush)
        palette2.setBrush(QPalette.Active, QPalette.Text, brush)
        palette2.setBrush(QPalette.Active, QPalette.ButtonText, brush)
        palette2.setBrush(QPalette.Inactive, QPalette.WindowText, brush1)
        palette2.setBrush(QPalette.Inactive, QPalette.Text, brush1)
        palette2.setBrush(QPalette.Inactive, QPalette.ButtonText, brush1)
        palette2.setBrush(QPalette.Disabled, QPalette.WindowText, brush2)
        palette2.setBrush(QPalette.Disabled, QPalette.Text, brush2)
        palette2.setBrush(QPalette.Disabled, QPalette.ButtonText, brush2)
        self.label_14.setPalette(palette2)
        self.label_14.setFont(font)

        self.gridLayout.addWidget(self.label_14, 13, 0, 1, 1)

        self.label_6 = QLabel(self.frame)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout.addWidget(self.label_6, 9, 0, 1, 1)

        self.fixTimeSeriesCheckBox = QCheckBox(self.frame)
        self.fixTimeSeriesCheckBox.setObjectName(u"fixTimeSeriesCheckBox")
        self.fixTimeSeriesCheckBox.setChecked(True)

        self.gridLayout.addWidget(self.fixTimeSeriesCheckBox, 16, 1, 1, 2)

        self.genVsetMaxSpinBox = QDoubleSpinBox(self.frame)
        self.genVsetMaxSpinBox.setObjectName(u"genVsetMaxSpinBox")
        self.genVsetMaxSpinBox.setValue(1.050000000000000)

        self.gridLayout.addWidget(self.genVsetMaxSpinBox, 1, 2, 1, 1)

        self.transformerVccMinSpinBox = QDoubleSpinBox(self.frame)
        self.transformerVccMinSpinBox.setObjectName(u"transformerVccMinSpinBox")
        self.transformerVccMinSpinBox.setDecimals(1)
        self.transformerVccMinSpinBox.setMinimum(0.000000000000000)
        self.transformerVccMinSpinBox.setMaximum(100.000000000000000)
        self.transformerVccMinSpinBox.setValue(1.000000000000000)

        self.gridLayout.addWidget(self.transformerVccMinSpinBox, 11, 1, 1, 1)

        self.genVsetMinSpinBox = QDoubleSpinBox(self.frame)
        self.genVsetMinSpinBox.setObjectName(u"genVsetMinSpinBox")
        self.genVsetMinSpinBox.setValue(0.950000000000000)

        self.gridLayout.addWidget(self.genVsetMinSpinBox, 1, 1, 1, 1)

        self.transformerTapModuleMaxSpinBox = QDoubleSpinBox(self.frame)
        self.transformerTapModuleMaxSpinBox.setObjectName(u"transformerTapModuleMaxSpinBox")
        self.transformerTapModuleMaxSpinBox.setValue(1.050000000000000)

        self.gridLayout.addWidget(self.transformerTapModuleMaxSpinBox, 5, 2, 1, 1)


        self.horizontalLayout.addWidget(self.frame)

        self.frame_2 = QFrame(self.tab_2)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.gridLayout_2 = QGridLayout(self.frame_2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.label_8 = QLabel(self.frame_2)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout_2.addWidget(self.label_8, 1, 0, 1, 1)

        self.verticalSpacer_2 = QSpacerItem(20, 373, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_2.addItem(self.verticalSpacer_2, 3, 0, 1, 1)

        self.label_16 = QLabel(self.frame_2)
        self.label_16.setObjectName(u"label_16")
        palette3 = QPalette()
        palette3.setBrush(QPalette.Active, QPalette.WindowText, brush)
        palette3.setBrush(QPalette.Active, QPalette.Text, brush)
        palette3.setBrush(QPalette.Active, QPalette.ButtonText, brush)
        palette3.setBrush(QPalette.Inactive, QPalette.WindowText, brush1)
        palette3.setBrush(QPalette.Inactive, QPalette.Text, brush1)
        palette3.setBrush(QPalette.Inactive, QPalette.ButtonText, brush1)
        palette3.setBrush(QPalette.Disabled, QPalette.WindowText, brush2)
        palette3.setBrush(QPalette.Disabled, QPalette.Text, brush2)
        palette3.setBrush(QPalette.Disabled, QPalette.ButtonText, brush2)
        self.label_16.setPalette(palette3)
        self.label_16.setFont(font)

        self.gridLayout_2.addWidget(self.label_16, 0, 0, 1, 1)

        self.activePowerImbalanceSpinBox = QDoubleSpinBox(self.frame_2)
        self.activePowerImbalanceSpinBox.setObjectName(u"activePowerImbalanceSpinBox")
        self.activePowerImbalanceSpinBox.setDecimals(1)
        self.activePowerImbalanceSpinBox.setMaximum(999.000000000000000)
        self.activePowerImbalanceSpinBox.setValue(3.000000000000000)

        self.gridLayout_2.addWidget(self.activePowerImbalanceSpinBox, 1, 1, 1, 1)


        self.horizontalLayout.addWidget(self.frame_2)

        self.horizontalSpacer = QSpacerItem(565, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        icon3 = QIcon()
        icon3.addFile(u":/icons/icons/gear.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.tabWidget.addTab(self.tab_2, icon3, "")

        self.verticalLayout_2.addWidget(self.tabWidget)

        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.toolBar = QToolBar(MainWindow)
        self.toolBar.setObjectName(u"toolBar")
        self.toolBar.setMovable(False)
        MainWindow.addToolBar(Qt.TopToolBarArea, self.toolBar)

        self.toolBar.addAction(self.actionAnalyze)
        self.toolBar.addAction(self.actionFix_issues)
        self.toolBar.addAction(self.actionSave_diagnostic)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Grid Analysis Dialog", None))
        self.actionSave_diagnostic.setText(QCoreApplication.translate("MainWindow", u"Save diagnostic", None))
        self.actionFix_issues.setText(QCoreApplication.translate("MainWindow", u"Fix issues", None))
        self.actionAnalyze.setText(QCoreApplication.translate("MainWindow", u"Analyze", None))
#if QT_CONFIG(tooltip)
        self.actionAnalyze.setToolTip(QCoreApplication.translate("MainWindow", u"Analyze the grid data", None))
#endif // QT_CONFIG(tooltip)
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("MainWindow", u"Analysis", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Transformers", None))
#if QT_CONFIG(tooltip)
        self.label_5.setToolTip(QCoreApplication.translate("MainWindow", u"VCC: Short circuit voltage from the short circuit study", None))
#endif // QT_CONFIG(tooltip)
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"VCC ", None))
        self.transformerVccMaxSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" %", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Voltage set point", None))
#if QT_CONFIG(tooltip)
        self.virtualTapToleranceSpinBox.setToolTip(QCoreApplication.translate("MainWindow", u"This is the tolerance for the difference between a transformer winding nominal voltage and the nominal voltage of the bus it is connected to.", None))
#endif // QT_CONFIG(tooltip)
        self.virtualTapToleranceSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" %", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"Tap angles", None))
        self.label_12.setText(QCoreApplication.translate("MainWindow", u"Generators", None))
        self.label_11.setText("")
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Tap module", None))
#if QT_CONFIG(tooltip)
        self.label_15.setToolTip(QCoreApplication.translate("MainWindow", u"Percentual difference between the nominal voltages at both sides of a line", None))
#endif // QT_CONFIG(tooltip)
        self.label_15.setText(QCoreApplication.translate("MainWindow", u"Vnom difference", None))
#if QT_CONFIG(tooltip)
        self.lineNominalVoltageToleranceSpinBox.setToolTip(QCoreApplication.translate("MainWindow", u"Percentual difference between the nominal voltages at both sides of a line", None))
#endif // QT_CONFIG(tooltip)
        self.lineNominalVoltageToleranceSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" %", None))
        self.label_13.setText("")
        self.label_14.setText(QCoreApplication.translate("MainWindow", u"Lines", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"Virtual tap tolerance", None))
        self.fixTimeSeriesCheckBox.setText(QCoreApplication.translate("MainWindow", u"Fix time series values", None))
        self.transformerVccMinSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" %", None))
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"Active power imbalance", None))
        self.label_16.setText(QCoreApplication.translate("MainWindow", u"System", None))
        self.activePowerImbalanceSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" %", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("MainWindow", u"Settings", None))
        self.toolBar.setWindowTitle(QCoreApplication.translate("MainWindow", u"toolBar", None))
    # retranslateUi

