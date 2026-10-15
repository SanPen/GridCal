# -*- coding: utf-8 -*-

# Form generated from reading UI file 'dynamic_events_page_ui.ui'.
# Changes belong in the .ui file and must be regenerated with update_gui_file.py.

from PySide6.QtCore import QCoreApplication, QMetaObject, QSize, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLineEdit,
                               QPushButton, QSplitter, QToolBar, QTreeView,
                               QVBoxLayout, QWidget)
from VeraGrid.Gui.Icons.icons_rc import *


class Ui_DynamicEventsPage(object):
    """Generated Qt widget tree for the global dynamic events page."""

    def setupUi(self, DynamicEventsPage):
        """Create the widgets declared in ``dynamic_events_page_ui.ui``.

        :param DynamicEventsPage: Widget receiving the generated controls.
        :return: None.
        """
        if not DynamicEventsPage.objectName():
            DynamicEventsPage.setObjectName(u"DynamicEventsPage")
        else:
            pass
        DynamicEventsPage.resize(1000, 600)
        self.actionNewGroup = QAction(DynamicEventsPage)
        self.actionNewGroup.setObjectName(u"actionNewGroup")
        event_group_icon = QIcon()
        event_group_icon.addFile(u":/Icons/icons/event_group.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionNewGroup.setIcon(event_group_icon)
        self.actionAddEvent = QAction(DynamicEventsPage)
        self.actionAddEvent.setObjectName(u"actionAddEvent")
        add_icon = QIcon()
        add_icon.addFile(u":/Icons/icons/plus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionAddEvent.setIcon(add_icon)
        self.actionRemove = QAction(DynamicEventsPage)
        self.actionRemove.setObjectName(u"actionRemove")
        remove_icon = QIcon()
        remove_icon.addFile(u":/Icons/icons/minus.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.actionRemove.setIcon(remove_icon)
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
        self.eventsToolBar.addAction(self.actionNewGroup)
        self.eventsToolBar.addSeparator()
        self.eventsToolBar.addAction(self.actionAddEvent)
        self.eventsToolBar.addAction(self.actionRemove)
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
        search_icon = QIcon()
        search_icon.addFile(u":/Icons/icons/magnifying_glass.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.parametersSearchButton.setIcon(search_icon)
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
        self.eventsSearchButton.setIcon(search_icon)
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
        self.retranslateUi(DynamicEventsPage)
        QMetaObject.connectSlotsByName(DynamicEventsPage)

    def retranslateUi(self, DynamicEventsPage):
        """Translate user-visible strings.

        :param DynamicEventsPage: Widget receiving translated strings.
        :return: None.
        """
        DynamicEventsPage.setWindowTitle(QCoreApplication.translate("DynamicEventsPage", u"Dynamic Events", None))
        self.actionNewGroup.setText("")
        self.actionNewGroup.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Create an event group", None))
        self.actionAddEvent.setText("")
        self.actionAddEvent.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Add an event to the selected event group", None))
        self.actionRemove.setText("")
        self.actionRemove.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Remove the selected event or event group", None))
        self.parametersSearchLineEdit.setPlaceholderText(QCoreApplication.translate("DynamicEventsPage", u"Search devices or parameters", None))
        self.parametersSearchButton.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Filter the parameters tree", None))
        self.parametersSearchButton.setText("")
        self.parametersTreeView.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Drag a parameter to an event group", None))
        self.eventsSearchLineEdit.setPlaceholderText(QCoreApplication.translate("DynamicEventsPage", u"Search event groups or events", None))
        self.eventsSearchButton.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Filter the events tree", None))
        self.eventsSearchButton.setText("")
        self.eventsTreeView.setToolTip(QCoreApplication.translate("DynamicEventsPage", u"Edit event groups and their events", None))
