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
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QDialog, QGridLayout, QHeaderView,
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget)
from .icons_rc import *

class Ui_AboutDialog(object):
    def setupUi(self, AboutDialog):
        if not AboutDialog.objectName():
            AboutDialog.setObjectName(u"AboutDialog")
        AboutDialog.resize(672, 365)
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

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

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
        self.updateButton = QPushButton(self.tab_3)
        self.updateButton.setObjectName(u"updateButton")
        self.updateButton.setMaximumSize(QSize(80, 16777215))

        self.gridLayout_2.addWidget(self.updateButton, 2, 1, 1, 1)

        self.librariesTableWidget = QTableWidget(self.tab_3)
        self.librariesTableWidget.setObjectName(u"librariesTableWidget")

        self.gridLayout_2.addWidget(self.librariesTableWidget, 0, 0, 1, 2)

        self.updateLabel = QLabel(self.tab_3)
        self.updateLabel.setObjectName(u"updateLabel")

        self.gridLayout_2.addWidget(self.updateLabel, 2, 0, 1, 1)

        self.tabWidget.addTab(self.tab_3, "")
        self.tab_4 = QWidget()
        self.tab_4.setObjectName(u"tab_4")
        self.verticalLayout_3 = QVBoxLayout(self.tab_4)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.licenseTextEdit = QTextEdit(self.tab_4)
        self.licenseTextEdit.setObjectName(u"licenseTextEdit")
        font = QFont()
        font.setFamilies([u"Cousine"])
        self.licenseTextEdit.setFont(font)
        self.licenseTextEdit.setTextInteractionFlags(Qt.LinksAccessibleByKeyboard|Qt.LinksAccessibleByMouse|Qt.TextBrowserInteraction|Qt.TextSelectableByKeyboard|Qt.TextSelectableByMouse)

        self.verticalLayout_3.addWidget(self.licenseTextEdit)

        self.tabWidget.addTab(self.tab_4, "")

        self.verticalLayout_2.addWidget(self.tabWidget)


        self.retranslateUi(AboutDialog)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(AboutDialog)
    # setupUi

    def retranslateUi(self, AboutDialog):
        AboutDialog.setWindowTitle(QCoreApplication.translate("AboutDialog", u"About GridCal", None))
        self.mainLabel.setText(QCoreApplication.translate("AboutDialog", u"<html><head/><body><p align=\"justify\"><span style=\" font-weight:600;\">GridCal</span> has been carefully crafted since 2015 to serve as a platform for research and consultancy. </p><p align=\"justify\">Visit <a href=\"https://www.advancedgridinsights.com/gridcal\"><span style=\" text-decoration: underline; color:#26a269;\">https://www.advancedgridinsights.com/gridcal</span></a> for more details.</p><p align=\"justify\">This program comes with absolutelly no warranty. This is free software, and you are welcome to redistribute it under the conditions set by the license. GridCal is licensed under the lesser GNU general public license version 3. See the license file for more details.</p><p align=\"justify\">The source of GridCal can be found at: <a href=\"https://github.com/SanPen/GridCal\"><span style=\" text-decoration: underline; color:#26a269;\">https://github.com/SanPen/GridCal</span></a></p></body></html>", None))
        self.label.setText("")
        self.versionLabel.setText(QCoreApplication.translate("AboutDialog", u"version", None))
        self.copyrightLabel.setText(QCoreApplication.translate("AboutDialog", u"Copyright", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("AboutDialog", u"About", None))
        self.contributorsLabel.setText(QCoreApplication.translate("AboutDialog", u"TextLabel", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("AboutDialog", u"Contributors", None))
        self.updateButton.setText(QCoreApplication.translate("AboutDialog", u"Update", None))
        self.updateLabel.setText("")
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3), QCoreApplication.translate("AboutDialog", u"Libraries", None))
        self.licenseTextEdit.setHtml(QCoreApplication.translate("AboutDialog", u"<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><meta charset=\"utf-8\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:'Cousine'; font-size:11pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">+==============+==========================================+</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">| Package      | License                                  |</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">+==============+==========================================+</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-inden"
                        "t:0; text-indent:0px;\">| setuptools   | MIT                                      |</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">+--------------+------------------------------------------+</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">| wheel        | MIT                                      |</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">+--------------+------------------------------------------+</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">| PySide6      | LGPL                                     |</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">+--------------+----------------------------------------"
                        "--+</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">| numpy        | BSD                                      |</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">+--------------+------------------------------------------+</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">| scipy        | BSD                                      |</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">+--------------+------------------------------------------+</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\">| networkx     | BSD                                      |</p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; marg"
                        "in-right:0px; -qt-block-indent:0; text-indent:0px;\">+--------------+------------------------------------------+</p></body></html>", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_4), QCoreApplication.translate("AboutDialog", u"License", None))
    # retranslateUi

