# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'substation_designer_gui.ui'
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
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpacerItem, QTableView,
    QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(450, 312)
        self.gridLayout = QGridLayout(Dialog)
        self.gridLayout.setObjectName(u"gridLayout")
        self.frame = QFrame(Dialog)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_2 = QGridLayout(self.frame)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.label_3 = QLabel(self.frame)
        self.label_3.setObjectName(u"label_3")
        font = QFont()
        font.setPointSize(10)
        self.label_3.setFont(font)

        self.gridLayout_2.addWidget(self.label_3, 0, 0, 1, 2)

        self.tableView = QTableView(self.frame)
        self.tableView.setObjectName(u"tableView")
        self.tableView.setFont(font)

        self.gridLayout_2.addWidget(self.tableView, 2, 0, 1, 2)


        self.gridLayout.addWidget(self.frame, 4, 0, 1, 3)

        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")
        self.label.setFont(font)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.frame_2 = QFrame(Dialog)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame_2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.addVlButton = QPushButton(self.frame_2)
        self.addVlButton.setObjectName(u"addVlButton")
        self.addVlButton.setFont(font)

        self.horizontalLayout.addWidget(self.addVlButton)

        self.deleteVlButton = QPushButton(self.frame_2)
        self.deleteVlButton.setObjectName(u"deleteVlButton")
        self.deleteVlButton.setFont(font)

        self.horizontalLayout.addWidget(self.deleteVlButton)

        self.horizontalSpacer = QSpacerItem(171, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.createButton = QPushButton(self.frame_2)
        self.createButton.setObjectName(u"createButton")
        self.createButton.setMaximumSize(QSize(80, 16777215))
        self.createButton.setFont(font)

        self.horizontalLayout.addWidget(self.createButton)


        self.gridLayout.addWidget(self.frame_2, 5, 0, 1, 3)

        self.label_2 = QLabel(Dialog)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setFont(font)

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.se_name_lineEdit = QLineEdit(Dialog)
        self.se_name_lineEdit.setObjectName(u"se_name_lineEdit")
        self.se_name_lineEdit.setFont(font)

        self.gridLayout.addWidget(self.se_name_lineEdit, 0, 2, 1, 1)

        self.se_code_lineEdit = QLineEdit(Dialog)
        self.se_code_lineEdit.setObjectName(u"se_code_lineEdit")
        self.se_code_lineEdit.setFont(font)

        self.gridLayout.addWidget(self.se_code_lineEdit, 1, 2, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(40, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_2, 0, 1, 1, 1)


        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.label_3.setText(QCoreApplication.translate("Dialog", u"Voltage levels", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"Name", None))
#if QT_CONFIG(tooltip)
        self.addVlButton.setToolTip(QCoreApplication.translate("Dialog", u"Add voltage level", None))
#endif // QT_CONFIG(tooltip)
        self.addVlButton.setText(QCoreApplication.translate("Dialog", u"+", None))
#if QT_CONFIG(tooltip)
        self.deleteVlButton.setToolTip(QCoreApplication.translate("Dialog", u"Remove voltage level", None))
#endif // QT_CONFIG(tooltip)
        self.deleteVlButton.setText(QCoreApplication.translate("Dialog", u"-", None))
#if QT_CONFIG(tooltip)
        self.createButton.setToolTip(QCoreApplication.translate("Dialog", u"Create substation", None))
#endif // QT_CONFIG(tooltip)
        self.createButton.setText(QCoreApplication.translate("Dialog", u"Create", None))
        self.label_2.setText(QCoreApplication.translate("Dialog", u"Code", None))
    # retranslateUi

