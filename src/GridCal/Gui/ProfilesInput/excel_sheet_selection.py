# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'excel_sheet_selection.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QFrame, QListWidget, QListWidgetItem, QSizePolicy,
    QVBoxLayout, QWidget)

class Ui_ExcelSelectionDialog(object):
    def setupUi(self, ExcelSelectionDialog):
        if not ExcelSelectionDialog.objectName():
            ExcelSelectionDialog.setObjectName(u"ExcelSelectionDialog")
        ExcelSelectionDialog.resize(272, 229)
        ExcelSelectionDialog.setMaximumSize(QSize(272, 229))
        ExcelSelectionDialog.setModal(True)
        self.verticalLayout = QVBoxLayout(ExcelSelectionDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.sheets_list = QListWidget(ExcelSelectionDialog)
        self.sheets_list.setObjectName(u"sheets_list")
        self.sheets_list.setFrameShape(QFrame.StyledPanel)

        self.verticalLayout.addWidget(self.sheets_list)

        self.buttonBox = QDialogButtonBox(ExcelSelectionDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(ExcelSelectionDialog)
        self.buttonBox.accepted.connect(ExcelSelectionDialog.accept)
        self.buttonBox.rejected.connect(ExcelSelectionDialog.reject)

        QMetaObject.connectSlotsByName(ExcelSelectionDialog)
    # setupUi

    def retranslateUi(self, ExcelSelectionDialog):
        ExcelSelectionDialog.setWindowTitle(QCoreApplication.translate("ExcelSelectionDialog", u"Excel sheet selection", None))
    # retranslateUi

