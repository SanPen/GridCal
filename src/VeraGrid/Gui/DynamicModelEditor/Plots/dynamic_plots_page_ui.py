# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dynamic_plots_page_ui.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QHeaderView,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QSplitter, QTreeView, QVBoxLayout, QWidget)
from VeraGrid.Gui.Icons.icons_rc import *

class Ui_DynamicPlotsPage(object):
    def setupUi(self, DynamicPlotsPage):
        if not DynamicPlotsPage.objectName():
            DynamicPlotsPage.setObjectName(u"DynamicPlotsPage")
        DynamicPlotsPage.resize(900, 560)
        self.mainLayout = QVBoxLayout(DynamicPlotsPage)
        self.mainLayout.setSpacing(0)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.searchFrame = QFrame(DynamicPlotsPage)
        self.searchFrame.setObjectName(u"searchFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.searchFrame.sizePolicy().hasHeightForWidth())
        self.searchFrame.setSizePolicy(sizePolicy)
        self.searchFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.searchLayout = QHBoxLayout(self.searchFrame)
        self.searchLayout.setObjectName(u"searchLayout")
        self.searchLayout.setContentsMargins(2, 4, 0, 4)
        self.searchLineEdit = QLineEdit(self.searchFrame)
        self.searchLineEdit.setObjectName(u"searchLineEdit")
        self.searchLineEdit.setMinimumSize(QSize(240, 0))
        self.searchLineEdit.setMaximumSize(QSize(240, 16777215))

        self.searchLayout.addWidget(self.searchLineEdit)

        self.searchButton = QPushButton(self.searchFrame)
        self.searchButton.setObjectName(u"searchButton")
        self.searchButton.setMinimumSize(QSize(32, 0))
        self.searchButton.setMaximumSize(QSize(32, 16777215))
        icon = QIcon()
        icon.addFile(u":/Icons/icons/magnifying_glass.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.searchButton.setIcon(icon)
        self.searchButton.setFlat(True)

        self.searchLayout.addWidget(self.searchButton)

        self.searchHorizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.searchLayout.addItem(self.searchHorizontalSpacer)

        self.addDynamicPlotButton = QPushButton(self.searchFrame)
        self.addDynamicPlotButton.setObjectName(u"addDynamicPlotButton")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/plus (gray).png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.addDynamicPlotButton.setIcon(icon1)

        self.searchLayout.addWidget(self.addDynamicPlotButton)

        self.deleteDynamicPlotButton = QPushButton(self.searchFrame)
        self.deleteDynamicPlotButton.setObjectName(u"deleteDynamicPlotButton")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/minus (gray).png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.deleteDynamicPlotButton.setIcon(icon2)

        self.searchLayout.addWidget(self.deleteDynamicPlotButton)


        self.mainLayout.addWidget(self.searchFrame)

        self.plotsSplitter = QSplitter(DynamicPlotsPage)
        self.plotsSplitter.setObjectName(u"plotsSplitter")
        self.plotsSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.availableVariablesTreeView = QTreeView(self.plotsSplitter)
        self.availableVariablesTreeView.setObjectName(u"availableVariablesTreeView")
        self.plotsSplitter.addWidget(self.availableVariablesTreeView)
        self.plotsTreeView = QTreeView(self.plotsSplitter)
        self.plotsTreeView.setObjectName(u"plotsTreeView")
        self.plotsSplitter.addWidget(self.plotsTreeView)

        self.mainLayout.addWidget(self.plotsSplitter)


        self.retranslateUi(DynamicPlotsPage)

        QMetaObject.connectSlotsByName(DynamicPlotsPage)
    # setupUi

    def retranslateUi(self, DynamicPlotsPage):
        DynamicPlotsPage.setWindowTitle(QCoreApplication.translate("DynamicPlotsPage", u"Dynamic Plots", None))
        self.searchLineEdit.setPlaceholderText(QCoreApplication.translate("DynamicPlotsPage", u"Type to search devices or variables", None))
#if QT_CONFIG(tooltip)
        self.searchButton.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Filter devices and variables", None))
#endif // QT_CONFIG(tooltip)
        self.searchButton.setText("")
#if QT_CONFIG(tooltip)
        self.addDynamicPlotButton.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Create a persistent dynamic plot", None))
#endif // QT_CONFIG(tooltip)
        self.addDynamicPlotButton.setText("")
#if QT_CONFIG(tooltip)
        self.deleteDynamicPlotButton.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Remove the selected plot or variable", None))
#endif // QT_CONFIG(tooltip)
        self.deleteDynamicPlotButton.setText("")
#if QT_CONFIG(tooltip)
        self.availableVariablesTreeView.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Drag a variable or parameter to a dynamic plot", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.plotsTreeView.setToolTip(QCoreApplication.translate("DynamicPlotsPage", u"Persistent dynamic plots for this simulation family", None))
#endif // QT_CONFIG(tooltip)
    # retranslateUi
