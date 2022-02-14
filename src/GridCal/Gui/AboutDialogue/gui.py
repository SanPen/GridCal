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

from .icons_rc import *

class Ui_AboutDialog(object):
    def setupUi(self, AboutDialog):
        if not AboutDialog.objectName():
            AboutDialog.setObjectName(u"AboutDialog")
        AboutDialog.resize(462, 367)
        icon = QIcon()
        icon.addFile(u":/Icons/icons/GridCal_icon.svg", QSize(), QIcon.Normal, QIcon.Off)
        AboutDialog.setWindowIcon(icon)
        self.verticalLayout_2 = QVBoxLayout(AboutDialog)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.tabWidget = QTabWidget(AboutDialog)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.gridLayout = QGridLayout(self.tab)
        self.gridLayout.setObjectName(u"gridLayout")
        self.mainLabel = QLabel(self.tab)
        self.mainLabel.setObjectName(u"mainLabel")
        self.mainLabel.setLayoutDirection(Qt.LeftToRight)
        self.mainLabel.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)
        self.mainLabel.setWordWrap(True)
        self.mainLabel.setOpenExternalLinks(True)
        self.mainLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)

        self.gridLayout.addWidget(self.mainLabel, 0, 1, 2, 2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 1, 0, 1, 1)

        self.label = QLabel(self.tab)
        self.label.setObjectName(u"label")
        self.label.setMinimumSize(QSize(48, 48))
        self.label.setMaximumSize(QSize(48, 48))
        self.label.setPixmap(QPixmap(u":/Icons/icons/GridCal_icon.svg"))
        self.label.setScaledContents(True)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.versionLabel = QLabel(self.tab)
        self.versionLabel.setObjectName(u"versionLabel")
        self.versionLabel.setOpenExternalLinks(True)
        self.versionLabel.setTextInteractionFlags(Qt.LinksAccessibleByMouse|Qt.TextSelectableByMouse)

        self.gridLayout.addWidget(self.versionLabel, 3, 1, 1, 1)

        self.copyrightLabel = QLabel(self.tab)
        self.copyrightLabel.setObjectName(u"copyrightLabel")
        self.copyrightLabel.setOpenExternalLinks(True)
        self.copyrightLabel.setTextInteractionFlags(Qt.LinksAccessibleByMouse|Qt.TextSelectableByMouse)

        self.gridLayout.addWidget(self.copyrightLabel, 4, 1, 1, 1)

        self.tabWidget.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.verticalLayout = QVBoxLayout(self.tab_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.contributorsLabel = QLabel(self.tab_2)
        self.contributorsLabel.setObjectName(u"contributorsLabel")
        self.contributorsLabel.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)

        self.verticalLayout.addWidget(self.contributorsLabel)

        self.tabWidget.addTab(self.tab_2, "")
        self.tab_3 = QWidget()
        self.tab_3.setObjectName(u"tab_3")
        self.gridLayout_2 = QGridLayout(self.tab_3)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.updateLabel = QLabel(self.tab_3)
        self.updateLabel.setObjectName(u"updateLabel")
        self.updateLabel.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.updateLabel.setWordWrap(True)
        self.updateLabel.setTextInteractionFlags(Qt.LinksAccessibleByMouse|Qt.TextSelectableByMouse)

        self.gridLayout_2.addWidget(self.updateLabel, 0, 1, 1, 1)

        self.updateButton = QPushButton(self.tab_3)
        self.updateButton.setObjectName(u"updateButton")
        self.updateButton.setMaximumSize(QSize(80, 16777215))

        self.gridLayout_2.addWidget(self.updateButton, 0, 0, 1, 1)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_2.addItem(self.verticalSpacer_2, 1, 0, 1, 1)

        self.tabWidget.addTab(self.tab_3, "")
        self.tab_4 = QWidget()
        self.tab_4.setObjectName(u"tab_4")
        self.verticalLayout_3 = QVBoxLayout(self.tab_4)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.licenseTextEdit = QTextEdit(self.tab_4)
        self.licenseTextEdit.setObjectName(u"licenseTextEdit")

        self.verticalLayout_3.addWidget(self.licenseTextEdit)

        self.tabWidget.addTab(self.tab_4, "")

        self.verticalLayout_2.addWidget(self.tabWidget)


        self.retranslateUi(AboutDialog)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(AboutDialog)
    # setupUi

    def retranslateUi(self, AboutDialog):
        AboutDialog.setWindowTitle(QCoreApplication.translate("AboutDialog", u"About GridCal", None))
        self.mainLabel.setText(QCoreApplication.translate("AboutDialog", u"<html><head/><body><p align=\"justify\"><span style=\" font-weight:600;\">GridCal</span> has been carefully crafted since 2015 to serve as a platform for research and consultancy. </p><p align=\"justify\">Visit <a href=\"https://gridcal.org\"><span style=\" text-decoration: underline; color:#0000ff;\">https://gridcal.org</span></a> for more details.</p><p align=\"justify\">This program comes with absolutelly no warranty. This is free software, and you are welcome to redistribute it under the conditions set by the license. GridCal is licensed under the lesser GNU general public license version 3. See the license file for more details.</p><p align=\"justify\">The source of GridCal can be found at: <a href=\"https://github.com/SanPen/GridCal\"><span style=\" text-decoration: underline; color:#0000ff;\">https://github.com/SanPen/GridCal</span></a></p></body></html>", None))
        self.label.setText("")
        self.versionLabel.setText(QCoreApplication.translate("AboutDialog", u"version", None))
        self.copyrightLabel.setText(QCoreApplication.translate("AboutDialog", u"Copyright", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("AboutDialog", u"About", None))
        self.contributorsLabel.setText(QCoreApplication.translate("AboutDialog", u"TextLabel", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("AboutDialog", u"Contributors", None))
        self.updateLabel.setText(QCoreApplication.translate("AboutDialog", u"TextLabel", None))
        self.updateButton.setText(QCoreApplication.translate("AboutDialog", u"Update", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3), QCoreApplication.translate("AboutDialog", u"Update", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_4), QCoreApplication.translate("AboutDialog", u"License", None))
    # retranslateUi

