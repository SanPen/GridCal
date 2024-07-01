# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'profiles_from_models_gui.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QApplication, QCheckBox,
    QDialog, QFrame, QHBoxLayout, QHeaderView,
    QPushButton, QSizePolicy, QSpacerItem, QTableView,
    QVBoxLayout, QWidget)
from .icons_rc import *

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(724, 522)
        self.verticalLayout_2 = QVBoxLayout(Dialog)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.frame_3 = QFrame(Dialog)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setMaximumSize(QSize(16777215, 34))
        self.frame_3.setFrameShape(QFrame.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_6 = QHBoxLayout(self.frame_3)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.addModelsButton = QPushButton(self.frame_3)
        self.addModelsButton.setObjectName(u"addModelsButton")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/plus.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.addModelsButton.setIcon(icon)

        self.horizontalLayout_6.addWidget(self.addModelsButton)

        self.deleteModelsButton = QPushButton(self.frame_3)
        self.deleteModelsButton.setObjectName(u"deleteModelsButton")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/delete3.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.deleteModelsButton.setIcon(icon1)

        self.horizontalLayout_6.addWidget(self.deleteModelsButton)

        self.horizontalSpacer_5 = QSpacerItem(725, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_6.addItem(self.horizontalSpacer_5)


        self.verticalLayout_2.addWidget(self.frame_3)

        self.frame_5 = QFrame(Dialog)
        self.frame_5.setObjectName(u"frame_5")
        self.frame_5.setFrameShape(QFrame.NoFrame)
        self.frame_5.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.frame_5)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, -1, 0, -1)
        self.modelsTableView = QTableView(self.frame_5)
        self.modelsTableView.setObjectName(u"modelsTableView")
        self.modelsTableView.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.modelsTableView.setDragDropMode(QAbstractItemView.InternalMove)
        self.modelsTableView.setDefaultDropAction(Qt.MoveAction)
        self.modelsTableView.setAlternatingRowColors(True)
        self.modelsTableView.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.verticalLayout.addWidget(self.modelsTableView)


        self.verticalLayout_2.addWidget(self.frame_5)

        self.frame_7 = QFrame(Dialog)
        self.frame_7.setObjectName(u"frame_7")
        self.frame_7.setMaximumSize(QSize(16777215, 40))
        self.frame_7.setFrameShape(QFrame.NoFrame)
        self.frame_7.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_8 = QHBoxLayout(self.frame_7)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.matchUsingCodeCheckBox = QCheckBox(self.frame_7)
        self.matchUsingCodeCheckBox.setObjectName(u"matchUsingCodeCheckBox")

        self.horizontalLayout_8.addWidget(self.matchUsingCodeCheckBox)

        self.horizontalSpacer_6 = QSpacerItem(814, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer_6)

        self.acceptModelsButton = QPushButton(self.frame_7)
        self.acceptModelsButton.setObjectName(u"acceptModelsButton")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/gear.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.acceptModelsButton.setIcon(icon2)

        self.horizontalLayout_8.addWidget(self.acceptModelsButton)


        self.verticalLayout_2.addWidget(self.frame_7)


        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.addModelsButton.setText(QCoreApplication.translate("Dialog", u"Add", None))
        self.deleteModelsButton.setText(QCoreApplication.translate("Dialog", u"Delete", None))
#if QT_CONFIG(tooltip)
        self.matchUsingCodeCheckBox.setToolTip(QCoreApplication.translate("Dialog", u"If checked, the objects are match using the code property, otherwise the idtag property is used", None))
#endif // QT_CONFIG(tooltip)
        self.matchUsingCodeCheckBox.setText(QCoreApplication.translate("Dialog", u"Match using code", None))
        self.acceptModelsButton.setText(QCoreApplication.translate("Dialog", u"Accept", None))
    # retranslateUi

