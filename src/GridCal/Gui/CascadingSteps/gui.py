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
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QTableView, QVBoxLayout, QWidget)
from .icons_rc import *

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(477, 536)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.frame_10 = QFrame(Dialog)
        self.frame_10.setObjectName(u"frame_10")
        self.frame_10.setFrameShape(QFrame.NoFrame)
        self.frame_10.setFrameShadow(QFrame.Raised)
        self.verticalLayout_5 = QVBoxLayout(self.frame_10)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.frame_11 = QFrame(self.frame_10)
        self.frame_11.setObjectName(u"frame_11")
        self.frame_11.setFrameShape(QFrame.NoFrame)
        self.frame_11.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_11)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.run_cascade_pushButton = QPushButton(self.frame_11)
        self.run_cascade_pushButton.setObjectName(u"run_cascade_pushButton")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/run_cascade.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.run_cascade_pushButton.setIcon(icon)

        self.horizontalLayout_3.addWidget(self.run_cascade_pushButton)

        self.run_cascade_step_pushButton = QPushButton(self.frame_11)
        self.run_cascade_step_pushButton.setObjectName(u"run_cascade_step_pushButton")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/run_cascade_step.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.run_cascade_step_pushButton.setIcon(icon1)

        self.horizontalLayout_3.addWidget(self.run_cascade_step_pushButton)

        self.copy_cascade_step_pushButton = QPushButton(self.frame_11)
        self.copy_cascade_step_pushButton.setObjectName(u"copy_cascade_step_pushButton")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/copy.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.copy_cascade_step_pushButton.setIcon(icon2)

        self.horizontalLayout_3.addWidget(self.copy_cascade_step_pushButton)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)

        self.clear_cascade_pushButton = QPushButton(self.frame_11)
        self.clear_cascade_pushButton.setObjectName(u"clear_cascade_pushButton")
        icon3 = QIcon()
        icon3.addFile(u":/Icons/icons/delete.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.clear_cascade_pushButton.setIcon(icon3)

        self.horizontalLayout_3.addWidget(self.clear_cascade_pushButton)


        self.verticalLayout_5.addWidget(self.frame_11)

        self.label_27 = QLabel(self.frame_10)
        self.label_27.setObjectName(u"label_27")
        palette = QPalette()
        brush = QBrush(QColor(119, 118, 123, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.WindowText, brush)
        palette.setBrush(QPalette.Inactive, QPalette.WindowText, brush)
        brush1 = QBrush(QColor(190, 190, 190, 255))
        brush1.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Disabled, QPalette.WindowText, brush1)
        self.label_27.setPalette(palette)

        self.verticalLayout_5.addWidget(self.label_27)

        self.cascade_tableView = QTableView(self.frame_10)
        self.cascade_tableView.setObjectName(u"cascade_tableView")

        self.verticalLayout_5.addWidget(self.cascade_tableView)


        self.verticalLayout.addWidget(self.frame_10)


        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
#if QT_CONFIG(tooltip)
        self.run_cascade_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Run complete cascading process", None))
#endif // QT_CONFIG(tooltip)
        self.run_cascade_pushButton.setText("")
#if QT_CONFIG(tooltip)
        self.run_cascade_step_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Run next cascading state", None))
#endif // QT_CONFIG(tooltip)
        self.run_cascade_step_pushButton.setText("")
#if QT_CONFIG(tooltip)
        self.copy_cascade_step_pushButton.setToolTip(QCoreApplication.translate("Dialog", u"Copy cascade state to normal grid state", None))
#endif // QT_CONFIG(tooltip)
        self.copy_cascade_step_pushButton.setText("")
        self.clear_cascade_pushButton.setText("")
        self.label_27.setText(QCoreApplication.translate("Dialog", u"Cascading steps", None))
    # retranslateUi

