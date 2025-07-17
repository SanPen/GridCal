# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'grid_reduce_gui.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFrame,
    QHBoxLayout, QListView, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget)

class Ui_ReduceDialog(object):
    def setupUi(self, ReduceDialog):
        if not ReduceDialog.objectName():
            ReduceDialog.setObjectName(u"ReduceDialog")
        ReduceDialog.resize(574, 335)
        self.verticalLayout_2 = QVBoxLayout(ReduceDialog)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.frame_2 = QFrame(ReduceDialog)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.listView = QListView(self.frame_2)
        self.listView.setObjectName(u"listView")

        self.horizontalLayout_2.addWidget(self.listView)


        self.verticalLayout_2.addWidget(self.frame_2)

        self.frame = QFrame(ReduceDialog)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.methodComboBox = QComboBox(self.frame)
        self.methodComboBox.setObjectName(u"methodComboBox")

        self.horizontalLayout.addWidget(self.methodComboBox)

        self.horizontalSpacer = QSpacerItem(450, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.reduceButton = QPushButton(self.frame)
        self.reduceButton.setObjectName(u"reduceButton")

        self.horizontalLayout.addWidget(self.reduceButton)


        self.verticalLayout_2.addWidget(self.frame)


        self.retranslateUi(ReduceDialog)

        QMetaObject.connectSlotsByName(ReduceDialog)
    # setupUi

    def retranslateUi(self, ReduceDialog):
        ReduceDialog.setWindowTitle(QCoreApplication.translate("ReduceDialog", u"Grid Merge", None))
#if QT_CONFIG(tooltip)
        self.reduceButton.setToolTip(QCoreApplication.translate("ReduceDialog", u"Aply the selected changes", None))
#endif // QT_CONFIG(tooltip)
        self.reduceButton.setText(QCoreApplication.translate("ReduceDialog", u"Reduce", None))
    # retranslateUi

