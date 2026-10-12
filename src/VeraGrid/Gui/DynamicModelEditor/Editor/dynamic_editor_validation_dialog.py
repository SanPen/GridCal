# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dynamic_editor_validation_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
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
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QComboBox,
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QTableView, QVBoxLayout, QWidget)

class Ui_ValidationSectionDialog(object):
    def setupUi(self, ValidationSectionDialog):
        if not ValidationSectionDialog.objectName():
            ValidationSectionDialog.setObjectName(u"ValidationSectionDialog")
        ValidationSectionDialog.resize(920, 600)
        ValidationSectionDialog.setMinimumSize(QSize(700, 420))
        self.mainLayout = QVBoxLayout(ValidationSectionDialog)
        self.mainLayout.setSpacing(6)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(6, 6, 6, 6)
        self.introLabel = QLabel(ValidationSectionDialog)
        self.introLabel.setObjectName(u"introLabel")
        self.introLabel.setWordWrap(True)

        self.mainLayout.addWidget(self.introLabel)

        self.summaryFilterLayout = QHBoxLayout()
        self.summaryFilterLayout.setSpacing(6)
        self.summaryFilterLayout.setObjectName(u"summaryFilterLayout")
        self.summaryLabel = QLabel(ValidationSectionDialog)
        self.summaryLabel.setObjectName(u"summaryLabel")
        font = QFont()
        font.setBold(True)
        self.summaryLabel.setFont(font)

        self.summaryFilterLayout.addWidget(self.summaryLabel)

        self.summaryHorizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.summaryFilterLayout.addItem(self.summaryHorizontalSpacer)

        self.filterLabel = QLabel(ValidationSectionDialog)
        self.filterLabel.setObjectName(u"filterLabel")

        self.summaryFilterLayout.addWidget(self.filterLabel)

        self.resultsFilterComboBox = QComboBox(ValidationSectionDialog)
        self.resultsFilterComboBox.setObjectName(u"resultsFilterComboBox")
        self.resultsFilterComboBox.setMinimumSize(QSize(220, 0))

        self.summaryFilterLayout.addWidget(self.resultsFilterComboBox)


        self.mainLayout.addLayout(self.summaryFilterLayout)

        self.resultsTableView = QTableView(ValidationSectionDialog)
        self.resultsTableView.setObjectName(u"resultsTableView")
        self.resultsTableView.setMinimumSize(QSize(0, 220))
        self.resultsTableView.setAlternatingRowColors(True)
        self.resultsTableView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.resultsTableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.resultsTableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.resultsTableView.setWordWrap(True)
        self.resultsTableView.horizontalHeader().setStretchLastSection(True)
        self.resultsTableView.verticalHeader().setVisible(False)

        self.mainLayout.addWidget(self.resultsTableView)

        self.emptyStateLabel = QLabel(ValidationSectionDialog)
        self.emptyStateLabel.setObjectName(u"emptyStateLabel")
        self.emptyStateLabel.setVisible(False)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.emptyStateLabel.sizePolicy().hasHeightForWidth())
        self.emptyStateLabel.setSizePolicy(sizePolicy)
        self.emptyStateLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emptyStateLabel.setWordWrap(True)

        self.mainLayout.addWidget(self.emptyStateLabel)

        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setSpacing(6)
        self.buttonLayout.setObjectName(u"buttonLayout")
        self.showIssuesButton = QPushButton(ValidationSectionDialog)
        self.showIssuesButton.setObjectName(u"showIssuesButton")

        self.buttonLayout.addWidget(self.showIssuesButton)

        self.buttonHorizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.buttonLayout.addItem(self.buttonHorizontalSpacer)

        self.buttonBox = QDialogButtonBox(ValidationSectionDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Ok)

        self.buttonLayout.addWidget(self.buttonBox)


        self.mainLayout.addLayout(self.buttonLayout)

#if QT_CONFIG(shortcut)
        self.filterLabel.setBuddy(self.resultsFilterComboBox)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(ValidationSectionDialog)
        self.buttonBox.accepted.connect(ValidationSectionDialog.accept)

        QMetaObject.connectSlotsByName(ValidationSectionDialog)
    # setupUi

    def retranslateUi(self, ValidationSectionDialog):
        ValidationSectionDialog.setWindowTitle(QCoreApplication.translate("ValidationSectionDialog", u"Model Consistency Validation", None))
        self.introLabel.setText(QCoreApplication.translate("ValidationSectionDialog", u"Check the edited model's equation counts, variable names, parameter mappings, and variable initialization. This report is informational and does not block saving the model.", None))
        self.summaryLabel.setText("")
        self.filterLabel.setText(QCoreApplication.translate("ValidationSectionDialog", u"Show:", None))
#if QT_CONFIG(tooltip)
        self.resultsFilterComboBox.setToolTip(QCoreApplication.translate("ValidationSectionDialog", u"Filter validation results by check", None))
#endif // QT_CONFIG(tooltip)
        self.emptyStateLabel.setText(QCoreApplication.translate("ValidationSectionDialog", u"No validation results match this filter.", None))
#if QT_CONFIG(tooltip)
        self.showIssuesButton.setToolTip(QCoreApplication.translate("ValidationSectionDialog", u"Show issues in the model", None))
#endif // QT_CONFIG(tooltip)
        self.showIssuesButton.setText(QCoreApplication.translate("ValidationSectionDialog", u"Show Issues", None))
    # retranslateUi

