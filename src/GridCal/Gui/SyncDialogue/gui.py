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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFrame,
    QHBoxLayout, QHeaderView, QPushButton, QSizePolicy,
    QSpacerItem, QTreeView, QVBoxLayout, QWidget)
from .icons_rc import *

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(941, 590)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(1, 1, 1, 1)
        self.frame = QFrame(Dialog)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(-1, -1, -1, 0)
        self.treeView = QTreeView(self.frame)
        self.treeView.setObjectName(u"treeView")
        self.treeView.setAlternatingRowColors(True)
        self.treeView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.treeView.setAnimated(True)

        self.verticalLayout_2.addWidget(self.treeView)


        self.verticalLayout.addWidget(self.frame)

        self.frame_2 = QFrame(Dialog)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame_2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(-1, 0, -1, -1)
        self.accept_selected_pushButton = QPushButton(self.frame_2)
        self.accept_selected_pushButton.setObjectName(u"accept_selected_pushButton")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/accept.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.accept_selected_pushButton.setIcon(icon)

        self.horizontalLayout.addWidget(self.accept_selected_pushButton)

        self.reject_selected_pushButton = QPushButton(self.frame_2)
        self.reject_selected_pushButton.setObjectName(u"reject_selected_pushButton")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/delete.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.reject_selected_pushButton.setIcon(icon1)

        self.horizontalLayout.addWidget(self.reject_selected_pushButton)

        self.horizontalSpacer = QSpacerItem(632, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.doit_pushButton = QPushButton(self.frame_2)
        self.doit_pushButton.setObjectName(u"doit_pushButton")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/accept2.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.doit_pushButton.setIcon(icon2)

        self.horizontalLayout.addWidget(self.doit_pushButton)


        self.verticalLayout.addWidget(self.frame_2)


        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
#if QT_CONFIG(tooltip)
        self.accept_selected_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Accept selected", None))
#endif // QT_CONFIG(tooltip)
        self.accept_selected_pushButton.setText("")
#if QT_CONFIG(tooltip)
        self.reject_selected_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Reject selected changes", None))
#endif // QT_CONFIG(tooltip)
        self.reject_selected_pushButton.setText("")
#if QT_CONFIG(tooltip)
        self.doit_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Process all changes as especified", None))
#endif // QT_CONFIG(tooltip)
        self.doit_pushButton.setText(QCoreApplication.translate("Dialog", u"Do it", None))
    # retranslateUi

