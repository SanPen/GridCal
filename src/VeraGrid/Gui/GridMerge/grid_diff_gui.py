# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'grid_diff_gui.ui'
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
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
    QHeaderView, QPushButton, QSizePolicy, QSpacerItem,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(639, 414)
        self.verticalLayout = QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.treeWidget = QTreeWidget(Dialog)
        __qtreewidgetitem = QTreeWidgetItem()
        __qtreewidgetitem.setText(0, u"1");
        self.treeWidget.setHeaderItem(__qtreewidgetitem)
        self.treeWidget.setObjectName(u"treeWidget")

        self.verticalLayout.addWidget(self.treeWidget)

        self.frame = QFrame(Dialog)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.addButton = QPushButton(self.frame)
        self.addButton.setObjectName(u"addButton")

        self.horizontalLayout.addWidget(self.addButton)

        self.horizontalSpacer = QSpacerItem(450, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.acceptButton = QPushButton(self.frame)
        self.acceptButton.setObjectName(u"acceptButton")

        self.horizontalLayout.addWidget(self.acceptButton)


        self.verticalLayout.addWidget(self.frame)


        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Grid Diff", None))
#if QT_CONFIG(tooltip)
        self.addButton.setToolTip(QCoreApplication.translate("Dialog", u"Open the base circuit to compare with", None))
#endif // QT_CONFIG(tooltip)
        self.addButton.setText(QCoreApplication.translate("Dialog", u"Open base", None))
#if QT_CONFIG(tooltip)
        self.acceptButton.setToolTip(QCoreApplication.translate("Dialog", u"Save the differentiated grid", None))
#endif // QT_CONFIG(tooltip)
        self.acceptButton.setText(QCoreApplication.translate("Dialog", u"Save diff", None))
    # retranslateUi

