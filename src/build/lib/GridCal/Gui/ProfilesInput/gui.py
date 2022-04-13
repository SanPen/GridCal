# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gui.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from .matplotlibwidget import MatplotlibWidget

from .icons_rc import *

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(933, 528)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.tabWidget = QTabWidget(Dialog)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.horizontalLayout_2 = QHBoxLayout(self.tab)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.tab)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.frame_4 = QFrame(self.splitter)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.verticalLayout_5 = QVBoxLayout(self.frame_4)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(-1, 0, -1, 0)
        self.frame = QFrame(self.frame_4)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.frame)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, -1, 0, -1)
        self.open_button = QPushButton(self.frame)
        self.open_button.setObjectName(u"open_button")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/import_profiles.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.open_button.setIcon(icon)

        self.horizontalLayout_5.addWidget(self.open_button)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_2)

        self.label_5 = QLabel(self.frame)
        self.label_5.setObjectName(u"label_5")

        self.horizontalLayout_5.addWidget(self.label_5)

        self.units_combobox = QComboBox(self.frame)
        self.units_combobox.setObjectName(u"units_combobox")

        self.horizontalLayout_5.addWidget(self.units_combobox)


        self.verticalLayout_5.addWidget(self.frame)

        self.sources_list = QListView(self.frame_4)
        self.sources_list.setObjectName(u"sources_list")

        self.verticalLayout_5.addWidget(self.sources_list)

        self.frame_2 = QFrame(self.frame_4)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.nameTransformationComboBox = QComboBox(self.frame_2)
        self.nameTransformationComboBox.setObjectName(u"nameTransformationComboBox")
        self.nameTransformationComboBox.setMinimumSize(QSize(200, 0))

        self.horizontalLayout_3.addWidget(self.nameTransformationComboBox)

        self.transformNamesPushButton = QPushButton(self.frame_2)
        self.transformNamesPushButton.setObjectName(u"transformNamesPushButton")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/transform.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.transformNamesPushButton.setIcon(icon1)

        self.horizontalLayout_3.addWidget(self.transformNamesPushButton)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer)


        self.verticalLayout_5.addWidget(self.frame_2)

        self.splitter.addWidget(self.frame_4)
        self.frame_6 = QFrame(self.splitter)
        self.frame_6.setObjectName(u"frame_6")
        self.frame_6.setFrameShape(QFrame.NoFrame)
        self.frame_6.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame_6)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, -1)
        self.frame_10 = QFrame(self.frame_6)
        self.frame_10.setObjectName(u"frame_10")
        self.frame_10.setFrameShape(QFrame.NoFrame)
        self.frame_10.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_7 = QHBoxLayout(self.frame_10)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, -1, 0, -1)
        self.autolink_button = QPushButton(self.frame_10)
        self.autolink_button.setObjectName(u"autolink_button")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/auto-link.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.autolink_button.setIcon(icon2)

        self.horizontalLayout_7.addWidget(self.autolink_button)

        self.autolink_slider = QSlider(self.frame_10)
        self.autolink_slider.setObjectName(u"autolink_slider")
        self.autolink_slider.setMinimum(1)
        self.autolink_slider.setMaximum(100)
        self.autolink_slider.setValue(60)
        self.autolink_slider.setOrientation(Qt.Horizontal)

        self.horizontalLayout_7.addWidget(self.autolink_slider)

        self.rnd_link_pushButton = QPushButton(self.frame_10)
        self.rnd_link_pushButton.setObjectName(u"rnd_link_pushButton")
        icon3 = QIcon()
        icon3.addFile(u":/Icons/icons/auto-link-rnd.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.rnd_link_pushButton.setIcon(icon3)

        self.horizontalLayout_7.addWidget(self.rnd_link_pushButton)

        self.assign_to_all_pushButton = QPushButton(self.frame_10)
        self.assign_to_all_pushButton.setObjectName(u"assign_to_all_pushButton")
        icon4 = QIcon()
        icon4.addFile(u":/Icons/icons/link-to-all.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.assign_to_all_pushButton.setIcon(icon4)

        self.horizontalLayout_7.addWidget(self.assign_to_all_pushButton)

        self.assign_to_selection_pushButton = QPushButton(self.frame_10)
        self.assign_to_selection_pushButton.setObjectName(u"assign_to_selection_pushButton")
        icon5 = QIcon()
        icon5.addFile(u":/Icons/icons/link-to-selection.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.assign_to_selection_pushButton.setIcon(icon5)

        self.horizontalLayout_7.addWidget(self.assign_to_selection_pushButton)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_7.addItem(self.horizontalSpacer_4)

        self.clear_selection_button = QPushButton(self.frame_10)
        self.clear_selection_button.setObjectName(u"clear_selection_button")
        icon6 = QIcon()
        icon6.addFile(u":/Icons/icons/delete.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.clear_selection_button.setIcon(icon6)

        self.horizontalLayout_7.addWidget(self.clear_selection_button)


        self.verticalLayout_3.addWidget(self.frame_10)

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
        self.set_multiplier_button = QPushButton(self.frame_9)
        self.set_multiplier_button.setObjectName(u"set_multiplier_button")
        icon7 = QIcon()
        icon7.addFile(u":/Icons/icons/multiply.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.set_multiplier_button.setIcon(icon7)

        self.gridLayout.addWidget(self.set_multiplier_button, 0, 0, 1, 1)

        self.normalized_checkBox = QCheckBox(self.frame_9)
        self.normalized_checkBox.setObjectName(u"normalized_checkBox")

        self.gridLayout.addWidget(self.normalized_checkBox, 0, 5, 1, 1)

        self.multSpinBox = QDoubleSpinBox(self.frame_9)
        self.multSpinBox.setObjectName(u"multSpinBox")
        self.multSpinBox.setMinimum(-99999.000000000000000)
        self.multSpinBox.setMaximum(99999.000000000000000)

        self.gridLayout.addWidget(self.multSpinBox, 0, 1, 1, 1)

        self.doit_button = QPushButton(self.frame_9)
        self.doit_button.setObjectName(u"doit_button")
        icon8 = QIcon()
        icon8.addFile(u":/Icons/icons/gear.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.doit_button.setIcon(icon8)

        self.gridLayout.addWidget(self.doit_button, 0, 6, 1, 1)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_3, 0, 3, 1, 1)

        self.setUnassignedToZeroCheckBox = QCheckBox(self.frame_9)
        self.setUnassignedToZeroCheckBox.setObjectName(u"setUnassignedToZeroCheckBox")
        self.setUnassignedToZeroCheckBox.setChecked(True)

        self.gridLayout.addWidget(self.setUnassignedToZeroCheckBox, 0, 4, 1, 1)


        self.verticalLayout_3.addWidget(self.frame_9)

        self.splitter.addWidget(self.frame_6)

        self.horizontalLayout_2.addWidget(self.splitter)

        self.tabWidget.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.horizontalLayout_4 = QHBoxLayout(self.tab_2)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.splitter_3 = QSplitter(self.tab_2)
        self.splitter_3.setObjectName(u"splitter_3")
        self.splitter_3.setOrientation(Qt.Horizontal)
        self.frame_8 = QFrame(self.splitter_3)
        self.frame_8.setObjectName(u"frame_8")
        self.frame_8.setFrameShape(QFrame.NoFrame)
        self.frame_8.setFrameShadow(QFrame.Raised)
        self.verticalLayout_7 = QVBoxLayout(self.frame_8)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(-1, 0, -1, -1)
        self.tableView = QTableView(self.frame_8)
        self.tableView.setObjectName(u"tableView")

        self.verticalLayout_7.addWidget(self.tableView)

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

        self.horizontalLayout_4.addWidget(self.splitter_3)

        self.tabWidget.addTab(self.tab_2, "")

        self.verticalLayout.addWidget(self.tabWidget)


        self.retranslateUi(Dialog)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
#if QT_CONFIG(tooltip)
        self.open_button.setToolTip(QCoreApplication.translate("Dialog", u"Import file", None))
#endif // QT_CONFIG(tooltip)
        self.open_button.setText("")
        self.label_5.setText(QCoreApplication.translate("Dialog", u"Units", None))
#if QT_CONFIG(tooltip)
        self.transformNamesPushButton.setToolTip(QCoreApplication.translate("Dialog", u"Transform the input profile names", None))
#endif // QT_CONFIG(tooltip)
        self.transformNamesPushButton.setText("")
#if QT_CONFIG(tooltip)
        self.autolink_button.setToolTip(QCoreApplication.translate("Dialog", u"Automatic link profiles to objects based on their name", None))
#endif // QT_CONFIG(tooltip)
        self.autolink_button.setText("")
#if QT_CONFIG(tooltip)
        self.autolink_slider.setToolTip(QCoreApplication.translate("Dialog", u"Auto-link string simmilarity", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.rnd_link_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Random-link profiles and objects", None))
#endif // QT_CONFIG(tooltip)
        self.rnd_link_pushButton.setText("")
#if QT_CONFIG(tooltip)
        self.assign_to_all_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Assign profile to all objects", None))
#endif // QT_CONFIG(tooltip)
        self.assign_to_all_pushButton.setText("")
#if QT_CONFIG(tooltip)
        self.assign_to_selection_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Assign profile to object selection", None))
#endif // QT_CONFIG(tooltip)
        self.assign_to_selection_pushButton.setText("")
#if QT_CONFIG(tooltip)
        self.clear_selection_button.setToolTip(QCoreApplication.translate("Dialog", u"Clear selection", None))
#endif // QT_CONFIG(tooltip)
        self.clear_selection_button.setText("")
#if QT_CONFIG(tooltip)
        self.set_multiplier_button.setToolTip(QCoreApplication.translate("Dialog", u"Set multiplier", None))
#endif // QT_CONFIG(tooltip)
        self.set_multiplier_button.setText("")
#if QT_CONFIG(tooltip)
        self.normalized_checkBox.setToolTip(QCoreApplication.translate("Dialog", u"Check if you want the profiles to be normalized on the base object property", None))
#endif // QT_CONFIG(tooltip)
        self.normalized_checkBox.setText(QCoreApplication.translate("Dialog", u"normalized", None))
#if QT_CONFIG(tooltip)
        self.doit_button.setToolTip(QCoreApplication.translate("Dialog", u"Do it!", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(statustip)
        self.doit_button.setStatusTip("")
#endif // QT_CONFIG(statustip)
        self.doit_button.setText(QCoreApplication.translate("Dialog", u"Accept", None))
#if QT_CONFIG(statustip)
        self.setUnassignedToZeroCheckBox.setStatusTip(QCoreApplication.translate("Dialog", u"The profiles for the unassigned objects are set to zero, otherwise they are not set and they remain the default value form the snapshot", None))
#endif // QT_CONFIG(statustip)
        self.setUnassignedToZeroCheckBox.setText(QCoreApplication.translate("Dialog", u"Set unassigned to zero", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("Dialog", u"Assignation", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("Dialog", u"Plot", None))
    # retranslateUi

