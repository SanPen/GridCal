# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'gui.ui',
# licensing of 'gui.ui' applies.
#
# Created: Tue Oct  8 08:16:16 2019
#      by: pyside2-uic  running on PySide2 5.13.0
#
# WARNING! All changes made in this file will be lost!

from PySide2 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(933, 528)
        self.verticalLayout = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tabWidget = QtWidgets.QTabWidget(Dialog)
        self.tabWidget.setObjectName("tabWidget")
        self.tab = QtWidgets.QWidget()
        self.tab.setObjectName("tab")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.tab)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.splitter = QtWidgets.QSplitter(self.tab)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self.frame_4 = QtWidgets.QFrame(self.splitter)
        self.frame_4.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame_4.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_4.setObjectName("frame_4")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout(self.frame_4)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.frame = QtWidgets.QFrame(self.frame_4)
        self.frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame.setObjectName("frame")
        self.horizontalLayout_5 = QtWidgets.QHBoxLayout(self.frame)
        self.horizontalLayout_5.setContentsMargins(0, -1, 0, -1)
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.open_button = QtWidgets.QPushButton(self.frame)
        self.open_button.setText("")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/Icons/icons/import_profiles.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.open_button.setIcon(icon)
        self.open_button.setObjectName("open_button")
        self.horizontalLayout_5.addWidget(self.open_button)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_5.addItem(spacerItem)
        self.label_5 = QtWidgets.QLabel(self.frame)
        self.label_5.setObjectName("label_5")
        self.horizontalLayout_5.addWidget(self.label_5)
        self.units_combobox = QtWidgets.QComboBox(self.frame)
        self.units_combobox.setObjectName("units_combobox")
        self.horizontalLayout_5.addWidget(self.units_combobox)
        self.verticalLayout_5.addWidget(self.frame)
        self.sources_list = QtWidgets.QListView(self.frame_4)
        self.sources_list.setObjectName("sources_list")
        self.verticalLayout_5.addWidget(self.sources_list)
        self.frame_6 = QtWidgets.QFrame(self.splitter)
        self.frame_6.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame_6.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_6.setObjectName("frame_6")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.frame_6)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.frame_10 = QtWidgets.QFrame(self.frame_6)
        self.frame_10.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame_10.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_10.setObjectName("frame_10")
        self.horizontalLayout_7 = QtWidgets.QHBoxLayout(self.frame_10)
        self.horizontalLayout_7.setContentsMargins(0, -1, 0, -1)
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.autolink_button = QtWidgets.QPushButton(self.frame_10)
        self.autolink_button.setText("")
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/Icons/icons/auto-link.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.autolink_button.setIcon(icon1)
        self.autolink_button.setObjectName("autolink_button")
        self.horizontalLayout_7.addWidget(self.autolink_button)
        self.autolink_slider = QtWidgets.QSlider(self.frame_10)
        self.autolink_slider.setMinimum(1)
        self.autolink_slider.setMaximum(100)
        self.autolink_slider.setProperty("value", 60)
        self.autolink_slider.setOrientation(QtCore.Qt.Horizontal)
        self.autolink_slider.setObjectName("autolink_slider")
        self.horizontalLayout_7.addWidget(self.autolink_slider)
        self.rnd_link_pushButton = QtWidgets.QPushButton(self.frame_10)
        self.rnd_link_pushButton.setText("")
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap(":/Icons/icons/auto-link-rnd.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.rnd_link_pushButton.setIcon(icon2)
        self.rnd_link_pushButton.setObjectName("rnd_link_pushButton")
        self.horizontalLayout_7.addWidget(self.rnd_link_pushButton)
        self.assign_to_all_pushButton = QtWidgets.QPushButton(self.frame_10)
        self.assign_to_all_pushButton.setText("")
        icon3 = QtGui.QIcon()
        icon3.addPixmap(QtGui.QPixmap(":/Icons/icons/link-to-all.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.assign_to_all_pushButton.setIcon(icon3)
        self.assign_to_all_pushButton.setObjectName("assign_to_all_pushButton")
        self.horizontalLayout_7.addWidget(self.assign_to_all_pushButton)
        self.assign_to_selection_pushButton = QtWidgets.QPushButton(self.frame_10)
        self.assign_to_selection_pushButton.setText("")
        icon4 = QtGui.QIcon()
        icon4.addPixmap(QtGui.QPixmap(":/Icons/icons/link-to-selection.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.assign_to_selection_pushButton.setIcon(icon4)
        self.assign_to_selection_pushButton.setObjectName("assign_to_selection_pushButton")
        self.horizontalLayout_7.addWidget(self.assign_to_selection_pushButton)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_7.addItem(spacerItem1)
        self.clear_selection_button = QtWidgets.QPushButton(self.frame_10)
        self.clear_selection_button.setText("")
        icon5 = QtGui.QIcon()
        icon5.addPixmap(QtGui.QPixmap(":/Icons/icons/delete.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.clear_selection_button.setIcon(icon5)
        self.clear_selection_button.setObjectName("clear_selection_button")
        self.horizontalLayout_7.addWidget(self.clear_selection_button)
        self.verticalLayout_3.addWidget(self.frame_10)
        self.assignation_table = QtWidgets.QTableView(self.frame_6)
        self.assignation_table.setObjectName("assignation_table")
        self.verticalLayout_3.addWidget(self.assignation_table)
        self.frame_9 = QtWidgets.QFrame(self.frame_6)
        self.frame_9.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame_9.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_9.setObjectName("frame_9")
        self.gridLayout = QtWidgets.QGridLayout(self.frame_9)
        self.gridLayout.setContentsMargins(0, -1, 0, 0)
        self.gridLayout.setObjectName("gridLayout")
        spacerItem2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem2, 0, 3, 1, 1)
        self.set_multiplier_button = QtWidgets.QPushButton(self.frame_9)
        self.set_multiplier_button.setText("")
        icon6 = QtGui.QIcon()
        icon6.addPixmap(QtGui.QPixmap(":/Icons/icons/multiply.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.set_multiplier_button.setIcon(icon6)
        self.set_multiplier_button.setObjectName("set_multiplier_button")
        self.gridLayout.addWidget(self.set_multiplier_button, 0, 0, 1, 1)
        self.multSpinBox = QtWidgets.QDoubleSpinBox(self.frame_9)
        self.multSpinBox.setMinimum(-99999.0)
        self.multSpinBox.setMaximum(99999.0)
        self.multSpinBox.setObjectName("multSpinBox")
        self.gridLayout.addWidget(self.multSpinBox, 0, 1, 1, 1)
        self.doit_button = QtWidgets.QPushButton(self.frame_9)
        self.doit_button.setStatusTip("")
        self.doit_button.setText("")
        icon7 = QtGui.QIcon()
        icon7.addPixmap(QtGui.QPixmap(":/Icons/icons/gear.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.doit_button.setIcon(icon7)
        self.doit_button.setObjectName("doit_button")
        self.gridLayout.addWidget(self.doit_button, 0, 5, 1, 1)
        self.normalized_checkBox = QtWidgets.QCheckBox(self.frame_9)
        self.normalized_checkBox.setObjectName("normalized_checkBox")
        self.gridLayout.addWidget(self.normalized_checkBox, 0, 4, 1, 1)
        self.verticalLayout_3.addWidget(self.frame_9)
        self.horizontalLayout_2.addWidget(self.splitter)
        self.tabWidget.addTab(self.tab, "")
        self.tab_2 = QtWidgets.QWidget()
        self.tab_2.setObjectName("tab_2")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout(self.tab_2)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.splitter_3 = QtWidgets.QSplitter(self.tab_2)
        self.splitter_3.setOrientation(QtCore.Qt.Horizontal)
        self.splitter_3.setObjectName("splitter_3")
        self.frame_8 = QtWidgets.QFrame(self.splitter_3)
        self.frame_8.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame_8.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_8.setObjectName("frame_8")
        self.verticalLayout_7 = QtWidgets.QVBoxLayout(self.frame_8)
        self.verticalLayout_7.setContentsMargins(-1, 0, -1, -1)
        self.verticalLayout_7.setObjectName("verticalLayout_7")
        self.tableView = QtWidgets.QTableView(self.frame_8)
        self.tableView.setObjectName("tableView")
        self.verticalLayout_7.addWidget(self.tableView)
        self.PlotFrame = QtWidgets.QFrame(self.splitter_3)
        self.PlotFrame.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.PlotFrame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.PlotFrame.setObjectName("PlotFrame")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.PlotFrame)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.plotwidget = MatplotlibWidget(self.PlotFrame)
        self.plotwidget.setObjectName("plotwidget")
        self.horizontalLayout.addWidget(self.plotwidget)
        self.horizontalLayout_4.addWidget(self.splitter_3)
        self.tabWidget.addTab(self.tab_2, "")
        self.verticalLayout.addWidget(self.tabWidget)

        self.retranslateUi(Dialog)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtWidgets.QApplication.translate("Dialog", "Dialog", None, -1))
        self.open_button.setToolTip(QtWidgets.QApplication.translate("Dialog", "Import file", None, -1))
        self.label_5.setText(QtWidgets.QApplication.translate("Dialog", "Units", None, -1))
        self.autolink_button.setToolTip(QtWidgets.QApplication.translate("Dialog", "Automatic link profiles to objects based on their name", None, -1))
        self.autolink_slider.setToolTip(QtWidgets.QApplication.translate("Dialog", "Auto-link string simmilarity", None, -1))
        self.rnd_link_pushButton.setToolTip(QtWidgets.QApplication.translate("Dialog", "Random-link profiles and objects", None, -1))
        self.assign_to_all_pushButton.setToolTip(QtWidgets.QApplication.translate("Dialog", "Assign profile to all objects", None, -1))
        self.assign_to_selection_pushButton.setToolTip(QtWidgets.QApplication.translate("Dialog", "Assign profile to object selection", None, -1))
        self.clear_selection_button.setToolTip(QtWidgets.QApplication.translate("Dialog", "Clear selection", None, -1))
        self.set_multiplier_button.setToolTip(QtWidgets.QApplication.translate("Dialog", "Set multiplier", None, -1))
        self.doit_button.setToolTip(QtWidgets.QApplication.translate("Dialog", "Do it!", None, -1))
        self.normalized_checkBox.setToolTip(QtWidgets.QApplication.translate("Dialog", "Check if you want the profiles to be normalized on the base object property", None, -1))
        self.normalized_checkBox.setText(QtWidgets.QApplication.translate("Dialog", "normalized", None, -1))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QtWidgets.QApplication.translate("Dialog", "Assignation", None, -1))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QtWidgets.QApplication.translate("Dialog", "Plot", None, -1))

from .matplotlibwidget import MatplotlibWidget
from .icons_rc import *

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Dialog = QtWidgets.QDialog()
    ui = Ui_Dialog()
    ui.setupUi(Dialog)
    Dialog.show()
    sys.exit(app.exec_())
