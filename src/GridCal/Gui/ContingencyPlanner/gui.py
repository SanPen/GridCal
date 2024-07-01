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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDoubleSpinBox,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QListView, QPushButton, QSizePolicy,
    QSpacerItem, QSpinBox, QVBoxLayout, QWidget)
from .icons_rc import *

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(709, 427)
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
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.frame_74 = QFrame(MainWindow)
        self.frame_74.setObjectName(u"frame_74")
        self.frame_74.setFrameShape(QFrame.NoFrame)
        self.frame_74.setFrameShadow(QFrame.Raised)
        self.formLayout = QFormLayout(self.frame_74)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setContentsMargins(2, 2, 2, 2)
        self.frame_71 = QFrame(self.frame_74)
        self.frame_71.setObjectName(u"frame_71")
        self.frame_71.setFrameShape(QFrame.NoFrame)
        self.frame_71.setFrameShadow(QFrame.Raised)
        self.gridLayout_26 = QGridLayout(self.frame_71)
        self.gridLayout_26.setObjectName(u"gridLayout_26")
        self.contingencyBranchTypesListView = QListView(self.frame_71)
        self.contingencyBranchTypesListView.setObjectName(u"contingencyBranchTypesListView")

        self.gridLayout_26.addWidget(self.contingencyBranchTypesListView, 1, 0, 1, 3)

        self.label_100 = QLabel(self.frame_71)
        self.label_100.setObjectName(u"label_100")

        self.gridLayout_26.addWidget(self.label_100, 6, 0, 1, 1)

        self.filterContingencyBranchesByVoltageMinSpinBox = QDoubleSpinBox(self.frame_71)
        self.filterContingencyBranchesByVoltageMinSpinBox.setObjectName(u"filterContingencyBranchesByVoltageMinSpinBox")
        self.filterContingencyBranchesByVoltageMinSpinBox.setMaximum(99999999999.000000000000000)

        self.gridLayout_26.addWidget(self.filterContingencyBranchesByVoltageMinSpinBox, 5, 1, 1, 2)

        self.label_99 = QLabel(self.frame_71)
        self.label_99.setObjectName(u"label_99")

        self.gridLayout_26.addWidget(self.label_99, 5, 0, 1, 1)

        self.addBranchesToContingencyCheckBox = QCheckBox(self.frame_71)
        self.addBranchesToContingencyCheckBox.setObjectName(u"addBranchesToContingencyCheckBox")
        self.addBranchesToContingencyCheckBox.setChecked(True)

        self.gridLayout_26.addWidget(self.addBranchesToContingencyCheckBox, 0, 0, 1, 3)

        self.filterContingencyBranchesByVoltageCheckBox = QCheckBox(self.frame_71)
        self.filterContingencyBranchesByVoltageCheckBox.setObjectName(u"filterContingencyBranchesByVoltageCheckBox")

        self.gridLayout_26.addWidget(self.filterContingencyBranchesByVoltageCheckBox, 3, 0, 1, 3)

        self.filterContingencyBranchesByVoltageMaxSpinBox = QDoubleSpinBox(self.frame_71)
        self.filterContingencyBranchesByVoltageMaxSpinBox.setObjectName(u"filterContingencyBranchesByVoltageMaxSpinBox")
        self.filterContingencyBranchesByVoltageMaxSpinBox.setMaximum(999999999999.000000000000000)
        self.filterContingencyBranchesByVoltageMaxSpinBox.setValue(600.000000000000000)

        self.gridLayout_26.addWidget(self.filterContingencyBranchesByVoltageMaxSpinBox, 6, 1, 1, 2)

        self.label = QLabel(self.frame_71)
        self.label.setObjectName(u"label")
        self.label.setMinimumSize(QSize(0, 26))

        self.gridLayout_26.addWidget(self.label, 2, 0, 1, 3)


        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.frame_71)

        self.frame_72 = QFrame(self.frame_74)
        self.frame_72.setObjectName(u"frame_72")
        self.frame_72.setFrameShape(QFrame.NoFrame)
        self.frame_72.setFrameShadow(QFrame.Raised)
        self.gridLayout_27 = QGridLayout(self.frame_72)
        self.gridLayout_27.setObjectName(u"gridLayout_27")
        self.contingenctyInjectionsListView = QListView(self.frame_72)
        self.contingenctyInjectionsListView.setObjectName(u"contingenctyInjectionsListView")

        self.gridLayout_27.addWidget(self.contingenctyInjectionsListView, 1, 0, 1, 2)

        self.contingencyFilterInjectionsByPowerMinSpinBox = QDoubleSpinBox(self.frame_72)
        self.contingencyFilterInjectionsByPowerMinSpinBox.setObjectName(u"contingencyFilterInjectionsByPowerMinSpinBox")
        self.contingencyFilterInjectionsByPowerMinSpinBox.setMaximum(999999999999999.000000000000000)

        self.gridLayout_27.addWidget(self.contingencyFilterInjectionsByPowerMinSpinBox, 6, 1, 1, 1)

        self.contingencyInjectionPowerReductionSpinBox = QDoubleSpinBox(self.frame_72)
        self.contingencyInjectionPowerReductionSpinBox.setObjectName(u"contingencyInjectionPowerReductionSpinBox")
        self.contingencyInjectionPowerReductionSpinBox.setMaximum(100.000000000000000)
        self.contingencyInjectionPowerReductionSpinBox.setValue(100.000000000000000)

        self.gridLayout_27.addWidget(self.contingencyInjectionPowerReductionSpinBox, 2, 1, 1, 1)

        self.label_112 = QLabel(self.frame_72)
        self.label_112.setObjectName(u"label_112")

        self.gridLayout_27.addWidget(self.label_112, 2, 0, 1, 1)

        self.addInjectionsToContingencyCheckBox = QCheckBox(self.frame_72)
        self.addInjectionsToContingencyCheckBox.setObjectName(u"addInjectionsToContingencyCheckBox")

        self.gridLayout_27.addWidget(self.addInjectionsToContingencyCheckBox, 0, 0, 1, 2)

        self.contingencyFilterInjectionsByPowerCheckBox = QCheckBox(self.frame_72)
        self.contingencyFilterInjectionsByPowerCheckBox.setObjectName(u"contingencyFilterInjectionsByPowerCheckBox")

        self.gridLayout_27.addWidget(self.contingencyFilterInjectionsByPowerCheckBox, 4, 0, 1, 2)

        self.contingencyFilterInjectionsByPowerMaxSpinBox = QDoubleSpinBox(self.frame_72)
        self.contingencyFilterInjectionsByPowerMaxSpinBox.setObjectName(u"contingencyFilterInjectionsByPowerMaxSpinBox")
        self.contingencyFilterInjectionsByPowerMaxSpinBox.setMaximum(9999999999999.000000000000000)
        self.contingencyFilterInjectionsByPowerMaxSpinBox.setValue(1000.000000000000000)

        self.gridLayout_27.addWidget(self.contingencyFilterInjectionsByPowerMaxSpinBox, 7, 1, 1, 1)

        self.label_110 = QLabel(self.frame_72)
        self.label_110.setObjectName(u"label_110")

        self.gridLayout_27.addWidget(self.label_110, 6, 0, 1, 1)

        self.label_111 = QLabel(self.frame_72)
        self.label_111.setObjectName(u"label_111")

        self.gridLayout_27.addWidget(self.label_111, 7, 0, 1, 1)


        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.frame_72)

        self.frame_75 = QFrame(self.frame_74)
        self.frame_75.setObjectName(u"frame_75")
        self.frame_75.setFrameShape(QFrame.NoFrame)
        self.frame_75.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_37 = QHBoxLayout(self.frame_75)
        self.horizontalLayout_37.setObjectName(u"horizontalLayout_37")
        self.horizontalLayout_37.setContentsMargins(1, 2, 9, 2)
        self.horizontalSpacer_27 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_37.addItem(self.horizontalSpacer_27)

        self.contingencyNspinBox = QSpinBox(self.frame_75)
        self.contingencyNspinBox.setObjectName(u"contingencyNspinBox")
        self.contingencyNspinBox.setMinimum(1)
        self.contingencyNspinBox.setMaximum(2)

        self.horizontalLayout_37.addWidget(self.contingencyNspinBox)

        self.autoNminusXButton = QPushButton(self.frame_75)
        self.autoNminusXButton.setObjectName(u"autoNminusXButton")

        self.horizontalLayout_37.addWidget(self.autoNminusXButton)


        self.formLayout.setWidget(1, QFormLayout.SpanningRole, self.frame_75)


        self.verticalLayout_2.addWidget(self.frame_74)


        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Contingency planner", None))
        self.actionCopy_to_clipboard.setText(QCoreApplication.translate("MainWindow", u"Copy to clipboard", None))
        self.actionSave.setText(QCoreApplication.translate("MainWindow", u"Save", None))
        self.label_100.setText(QCoreApplication.translate("MainWindow", u"Max", None))
        self.filterContingencyBranchesByVoltageMinSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" kV", None))
        self.label_99.setText(QCoreApplication.translate("MainWindow", u"Min", None))
        self.addBranchesToContingencyCheckBox.setText(QCoreApplication.translate("MainWindow", u"Add branches", None))
        self.filterContingencyBranchesByVoltageCheckBox.setText(QCoreApplication.translate("MainWindow", u"Filter branches by voltage", None))
        self.filterContingencyBranchesByVoltageMaxSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" kV", None))
        self.label.setText("")
        self.contingencyFilterInjectionsByPowerMinSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" MW", None))
        self.contingencyInjectionPowerReductionSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" %", None))
        self.label_112.setText(QCoreApplication.translate("MainWindow", u"Contingency power", None))
        self.addInjectionsToContingencyCheckBox.setText(QCoreApplication.translate("MainWindow", u"Add Injections", None))
        self.contingencyFilterInjectionsByPowerCheckBox.setText(QCoreApplication.translate("MainWindow", u"Filter by power", None))
        self.contingencyFilterInjectionsByPowerMaxSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u" MW", None))
        self.label_110.setText(QCoreApplication.translate("MainWindow", u"Min", None))
        self.label_111.setText(QCoreApplication.translate("MainWindow", u"Max", None))
        self.contingencyNspinBox.setPrefix(QCoreApplication.translate("MainWindow", u"N-", None))
#if QT_CONFIG(tooltip)
        self.autoNminusXButton.setToolTip(QCoreApplication.translate("MainWindow", u"Automatically generate the all the N-x contingencies following the settings below", None))
#endif // QT_CONFIG(tooltip)
        self.autoNminusXButton.setText(QCoreApplication.translate("MainWindow", u"Generate", None))
    # retranslateUi

