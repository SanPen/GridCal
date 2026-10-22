# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dynamic_events_page_ui.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QHBoxLayout,
    QHeaderView, QLineEdit, QPushButton, QSizePolicy,
    QSplitter, QToolBar, QTreeView, QVBoxLayout,
    QWidget)
from VeraGrid.Gui.Icons.icons_rc import *

class Ui_DynamicEventsPage(object):
    def setupUi(self, DynamicEventsPage):
        if not DynamicEventsPage.objectName():
            DynamicEventsPage.setObjectName(u"DynamicEventsPage")
        DynamicEventsPage.resize(1000, 600)
        self.actionNewGroup = QAction(DynamicEventsPage)
        self.actionNewGroup.setObjectName(u"actionNewGroup")
        icon = QIcon()
        icon.addFile(u":/Icons/icons/add_event_group.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionNewGroup.setIcon(icon)
        self.actionAddEvent = QAction(DynamicEventsPage)
        self.actionAddEvent.setObjectName(u"actionAddEvent")
        icon1 = QIcon()
        icon1.addFile(u":/Icons/icons/plus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionAddEvent.setIcon(icon1)
        self.actionRemove = QAction(DynamicEventsPage)
        self.actionRemove.setObjectName(u"actionRemove")
        icon2 = QIcon()
        icon2.addFile(u":/Icons/icons/minus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionRemove.setIcon(icon2)
        self.mainLayout = QVBoxLayout(DynamicEventsPage)
        self.mainLayout.setSpacing(0)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.eventsToolBar = QToolBar(DynamicEventsPage)
        self.eventsToolBar.setObjectName(u"eventsToolBar")
        self.eventsToolBar.setMovable(False)
        self.eventsToolBar.setIconSize(QSize(24, 24))
        self.eventsToolBar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.eventsToolBar.setFloatable(False)

        self.mainLayout.addWidget(self.eventsToolBar)

        self.eventsSplitter = QSplitter(DynamicEventsPage)
        self.eventsSplitter.setObjectName(u"eventsSplitter")
        self.eventsSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.eventsSplitter.setChildrenCollapsible(True)
        self.parametersFrame = QFrame(self.eventsSplitter)
        self.parametersFrame.setObjectName(u"parametersFrame")
        self.parametersFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.parametersLayout = QVBoxLayout(self.parametersFrame)
        self.parametersLayout.setSpacing(0)
        self.parametersLayout.setObjectName(u"parametersLayout")
        self.parametersLayout.setContentsMargins(0, 0, 3, 0)
        self.parametersSearchFrame = QFrame(self.parametersFrame)
        self.parametersSearchFrame.setObjectName(u"parametersSearchFrame")
        self.parametersSearchFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.parametersSearchLayout = QHBoxLayout(self.parametersSearchFrame)
        self.parametersSearchLayout.setObjectName(u"parametersSearchLayout")
        self.parametersSearchLayout.setContentsMargins(0, 4, 0, 4)
        self.parametersSearchLineEdit = QLineEdit(self.parametersSearchFrame)
        self.parametersSearchLineEdit.setObjectName(u"parametersSearchLineEdit")

        self.parametersSearchLayout.addWidget(self.parametersSearchLineEdit)

        self.parametersSearchButton = QPushButton(self.parametersSearchFrame)
        self.parametersSearchButton.setObjectName(u"parametersSearchButton")
        self.parametersSearchButton.setMaximumSize(QSize(32, 16777215))
        icon3 = QIcon()
        icon3.addFile(u":/Icons/icons/magnifying_glass.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.parametersSearchButton.setIcon(icon3)
        self.parametersSearchButton.setFlat(True)

        self.parametersSearchLayout.addWidget(self.parametersSearchButton)


        self.parametersLayout.addWidget(self.parametersSearchFrame)

        self.parametersTreeView = QTreeView(self.parametersFrame)
        self.parametersTreeView.setObjectName(u"parametersTreeView")
        self.parametersTreeView.setDragEnabled(True)
        self.parametersTreeView.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.parametersTreeView.setDefaultDropAction(Qt.DropAction.CopyAction)

        self.parametersLayout.addWidget(self.parametersTreeView)

        self.eventsSplitter.addWidget(self.parametersFrame)
        self.eventsFrame = QFrame(self.eventsSplitter)
        self.eventsFrame.setObjectName(u"eventsFrame")
        self.eventsFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.eventsLayout = QVBoxLayout(self.eventsFrame)
        self.eventsLayout.setSpacing(0)
        self.eventsLayout.setObjectName(u"eventsLayout")
        self.eventsLayout.setContentsMargins(3, 0, 0, 0)
        self.eventsSearchFrame = QFrame(self.eventsFrame)
        self.eventsSearchFrame.setObjectName(u"eventsSearchFrame")
        self.eventsSearchFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.eventsSearchLayout = QHBoxLayout(self.eventsSearchFrame)
        self.eventsSearchLayout.setObjectName(u"eventsSearchLayout")
        self.eventsSearchLayout.setContentsMargins(0, 4, 0, 4)
        self.eventsSearchLineEdit = QLineEdit(self.eventsSearchFrame)
        self.eventsSearchLineEdit.setObjectName(u"eventsSearchLineEdit")

        self.eventsSearchLayout.addWidget(self.eventsSearchLineEdit)

        self.eventsSearchButton = QPushButton(self.eventsSearchFrame)
        self.eventsSearchButton.setObjectName(u"eventsSearchButton")
        self.eventsSearchButton.setMaximumSize(QSize(32, 16777215))
        self.eventsSearchButton.setIcon(icon3)
        self.eventsSearchButton.setFlat(True)

        self.eventsSearchLayout.addWidget(self.eventsSearchButton)


        self.eventsLayout.addWidget(self.eventsSearchFrame)

        self.eventsTreeView = QTreeView(self.eventsFrame)
        self.eventsTreeView.setObjectName(u"eventsTreeView")
        self.eventsTreeView.setAcceptDrops(True)
        self.eventsTreeView.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.eventsTreeView.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.eventsTreeView.setAlternatingRowColors(True)
        self.eventsTreeView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.eventsTreeView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.eventsLayout.addWidget(self.eventsTreeView)

        self.eventsSplitter.addWidget(self.eventsFrame)

        self.mainLayout.addWidget(self.eventsSplitter)


        self.eventsToolBar.addAction(self.actionNewGroup)
        self.eventsToolBar.addSeparator()
        self.eventsToolBar.addAction(self.actionAddEvent)
        self.eventsToolBar.addAction(self.actionRemove)

        self.retranslateUi(DynamicEventsPage)

        QMetaObject.connectSlotsByName(DynamicEventsPage)
    # setupUi

    def retranslateUi(self, DynamicEventsPage):
        DynamicEventsPage.setWindowTitle(QCoreApplication.translate("DynamicEventsPage", u"Dynamic Events", None))
        self.actionNewGroup.setText("")
#if QT_CONFIG(tooltip)
        self.actionNewGroup.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Create an event group", None))
#endif // QT_CONFIG(tooltip)
        self.actionAddEvent.setText("")
#if QT_CONFIG(tooltip)
        self.actionAddEvent.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Add an event to the selected event group", None))
#endif // QT_CONFIG(tooltip)
        self.actionRemove.setText("")
#if QT_CONFIG(tooltip)
        self.actionRemove.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Remove the selected event or event group", None))
#endif // QT_CONFIG(tooltip)
        self.parametersSearchLineEdit.setPlaceholderText(QCoreApplication.translate("DynamicEventsPage", u"Search devices or parameters", None))
#if QT_CONFIG(tooltip)
        self.parametersSearchButton.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Filter the parameters tree", None))
#endif // QT_CONFIG(tooltip)
        self.parametersSearchButton.setText("")
#if QT_CONFIG(tooltip)
        self.parametersTreeView.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Drag a parameter to an event group", None))
#endif // QT_CONFIG(tooltip)
        self.eventsSearchLineEdit.setPlaceholderText(QCoreApplication.translate("DynamicEventsPage", u"Search event groups or events", None))
#if QT_CONFIG(tooltip)
        self.eventsSearchButton.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Filter the events tree", None))
#endif // QT_CONFIG(tooltip)
        self.eventsSearchButton.setText("")
#if QT_CONFIG(tooltip)
        self.eventsTreeView.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Edit event groups and their events", None))
#endif // QT_CONFIG(tooltip)
    # retranslateUi
