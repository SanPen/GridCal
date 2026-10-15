# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import io
import unicodedata
import numpy as np
import pandas as pd
from typing import List, Union, Any, Dict
from datetime import datetime
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (QApplication, QDialog, QTableView, QVBoxLayout, QPushButton, QHBoxLayout,
                               QLabel, QComboBox, QSpacerItem, QSizePolicy, QWidget)

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from VeraGridEngine.basic_structures import Logger, IntVec
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.Parents.editable_device import GCProp
from VeraGrid.Gui.gui_functions import ComboModel, get_list_model, get_checked_indices, get_chck_list_model
from VeraGrid.Gui.Icons.icon_associations import device_type_icons
from VeraGrid.Gui.object_model import ObjectsModel
from VeraGrid.Gui.object_column_filter_dialog import PopupResizeGrip
from VeraGridEngine.enumerations import (FaultType, MethodShortCircuit, PhasesShortCircuit, FileType, CGMESVersions,
                                         DeviceType, LogSeverity)


class CenteredDialog(QDialog):
    """
    Class to make the dialogues centered
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """

        :param event:
        :return:
        """
        super().showEvent(event)
        parent_widget: QtWidgets.QWidget | None = self.parentWidget()
        screen: QtGui.QScreen | None
        target_center: QtCore.QPoint
        dialog_geometry: QtCore.QRect = self.frameGeometry()

        if parent_widget is None:
            screen = QApplication.primaryScreen()

            if screen is None:
                target_center = QtCore.QPoint(0, 0)
            else:
                target_center = screen.availableGeometry().center()
        else:
            target_center = parent_widget.window().frameGeometry().center()

        dialog_geometry.moveCenter(target_center)
        self.move(dialog_geometry.topLeft())


class NewProfilesStructureDialogue(CenteredDialog):
    """
    New profile dialogue window
    """

    def __init__(self) -> None:
        super(NewProfilesStructureDialogue, self).__init__()
        self.setObjectName("self")
        # self.resize(200, 71)
        # self.setMinimumSize(QtCore.QSize(200, 71))
        # self.setMaximumSize(QtCore.QSize(200, 71))
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        # icon = QtGui.QIcon()
        # icon.addPixmap(QtGui.QPixmap("Icons/Plus-32.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        # self.setWindowIcon(icon)
        self.layout = QtWidgets.QVBoxLayout(self)

        # calendar
        self.calendar = QtWidgets.QDateTimeEdit()
        d = datetime.today()
        self.calendar.setDateTime(QtCore.QDateTime(d.year, 1, 1, 00, 00, 00))

        # number of time steps
        self.steps_spinner = QtWidgets.QSpinBox()
        self.steps_spinner.setMinimum(1)
        self.steps_spinner.setMaximum(9999999)
        self.steps_spinner.setValue(1)

        # time step length
        self.step_length = QtWidgets.QDoubleSpinBox()
        self.step_length.setMinimum(1)
        self.step_length.setMaximum(60)
        self.step_length.setValue(1)

        # units combo box
        self.units = QtWidgets.QComboBox()
        self.units.setModel(ComboModel(text_items=[(unit, unit) for unit in ['h', 'm', 's']]))

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText(self.tr('Accept'))
        self.accept_btn.clicked.connect(self.accept_click)

        # labels

        # add all to the GUI
        self.layout.addWidget(QtWidgets.QLabel(self.tr("Start date")))
        self.layout.addWidget(self.calendar)

        self.layout.addWidget(QtWidgets.QLabel(self.tr("Number of time steps")))
        self.layout.addWidget(self.steps_spinner)

        self.layout.addWidget(QtWidgets.QLabel(self.tr("Time step length")))
        self.layout.addWidget(self.step_length)

        self.layout.addWidget(QtWidgets.QLabel(self.tr("Time units")))
        self.layout.addWidget(self.units)

        self.layout.addWidget(self.accept_btn)

        self.setLayout(self.layout)

        self.setWindowTitle(self.tr('New profiles structure'))

    def accept_click(self):
        self.accept()

    def get_values(self):
        steps = self.steps_spinner.value()

        step_length = self.step_length.value()

        step_unit = self.units.currentData()

        time_base = self.calendar.dateTime()

        return steps, step_length, step_unit, time_base.toPython()


def get_log_severity_parent_brushes(severity: LogSeverity) -> tuple[QtGui.QBrush, QtGui.QBrush]:
    """
    Build the background and foreground brushes for one top-level log severity.

    :param severity: Log severity to style.
    :return: Background and foreground brushes.
    """
    # Only the top-level severity rows are highlighted; every child row keeps the default Qt styling.

    if severity == LogSeverity.Error:
        severity_color: str = "#ff0000"

    elif severity == LogSeverity.Warning:
        severity_color = "#ff9900"

    elif severity == LogSeverity.Information:
        severity_color = "#808080"

    else:
        severity_color = "#00aa00"

    background: QtGui.QBrush = QtGui.QBrush(QtGui.QColor(severity_color))
    foreground_color: str = "#ffffff"
    foreground: QtGui.QBrush = QtGui.QBrush(QtGui.QColor(foreground_color))

    return background, foreground


def apply_log_severity_parent_style(items: List[QtGui.QStandardItem],
                                    severity: LogSeverity) -> None:
    """
    Apply the severity color to one top-level log row.

    :param items: Row items to color.
    :param severity: Log severity associated with the row.
    :return: None.
    """
    # White text is used only on these items because they also receive a bright background fill.
    background: QtGui.QBrush
    foreground: QtGui.QBrush
    background, foreground = get_log_severity_parent_brushes(severity=severity)

    item: QtGui.QStandardItem
    for item in items:
        item.setBackground(background)
        item.setForeground(foreground)


def fill_tree_from_logs(logger: Logger) -> QtGui.QStandardItemModel:
    """
    Fill logger tree
    :param logger: Logger instance
    :return: QStandardItemModel instance
    """
    d: Union[
        Dict[str, Dict[str, List[tuple[str, str, str, str]]]],
        Dict[str, Dict[str, List[List[str]]]]
    ] = logger.to_dict()
    editable: bool = False
    model: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(list((
        QtCore.QCoreApplication.translate("LogsDialogue", 'Time'),
        QtCore.QCoreApplication.translate("LogsDialogue", 'Class'),
        QtCore.QCoreApplication.translate("LogsDialogue", 'Property'),
        QtCore.QCoreApplication.translate("LogsDialogue", 'Device'),
        QtCore.QCoreApplication.translate("LogsDialogue", 'Value'),
        QtCore.QCoreApplication.translate("LogsDialogue", 'Expected value'),
    )))
    parent: QtGui.QStandardItem = model.invisibleRootItem()

    for severity_text, messages_dict in d.items():
        severity: LogSeverity = LogSeverity(severity_text)
        severity_child: QtGui.QStandardItem = QtGui.QStandardItem(str(severity))
        severity_row_items: List[QtGui.QStandardItem] = list((severity_child,
                                                              QtGui.QStandardItem(""),
                                                              QtGui.QStandardItem(""),
                                                              QtGui.QStandardItem(""),
                                                              QtGui.QStandardItem(""),
                                                              QtGui.QStandardItem("")))
        apply_log_severity_parent_style(items=severity_row_items, severity=severity)

        # print(severity)

        for message, data_list in messages_dict.items():
            message_child: QtGui.QStandardItem = QtGui.QStandardItem(message)
            message_row_items: List[QtGui.QStandardItem] = list((message_child,
                                                                 QtGui.QStandardItem(""),
                                                                 QtGui.QStandardItem(""),
                                                                 QtGui.QStandardItem(""),
                                                                 QtGui.QStandardItem(""),
                                                                 QtGui.QStandardItem("")))

            # print('\t', message)
            try:
                for time, cls, prop, elm, value, expected_value in data_list:
                    # print('\t', '\t', time, elm, value, expected_value)

                    time_child: QtGui.QStandardItem = QtGui.QStandardItem(time)
                    time_child.setEditable(editable)

                    elm_cls: QtGui.QStandardItem = QtGui.QStandardItem(cls)
                    elm_cls.setEditable(editable)

                    elm_prop: QtGui.QStandardItem = QtGui.QStandardItem(prop)
                    elm_prop.setEditable(editable)

                    elm_child: QtGui.QStandardItem = QtGui.QStandardItem(elm)
                    elm_child.setEditable(editable)

                    value_child: QtGui.QStandardItem = QtGui.QStandardItem(value)
                    value_child.setEditable(editable)

                    expected_val_child: QtGui.QStandardItem = QtGui.QStandardItem(expected_value)
                    expected_val_child.setEditable(editable)

                    row_items: List[QtGui.QStandardItem] = list((time_child, elm_cls, elm_prop, elm_child,
                                                                 value_child, expected_val_child))
                    message_child.appendRow(row_items)
            except OverflowError as e:
                print(e)

            group_item: QtGui.QStandardItem
            for group_item in message_row_items:
                group_item.setEditable(editable)

            severity_child.appendRow(message_row_items)

        for group_item in severity_row_items:
            group_item.setEditable(editable)
        parent.appendRow(severity_row_items)

    return model


class LogSeverityItemDelegate(QtWidgets.QStyledItemDelegate):
    """
    Paint explicitly colored log rows without theme hover overlays.
    """
    __slots__ = tuple()

    def initStyleOption(self,
                        option: QtWidgets.QStyleOptionViewItem,
                        index: QtCore.QModelIndex) -> None:
        """
        Prepare the style option used to paint one log item.

        :param option: Style option to be modified before painting.
        :param index: Model index being painted.
        :return: None.
        """
        super(LogSeverityItemDelegate, self).initStyleOption(option, index)

        # Top-level severity cells carry a model background; theme hover fills must not cover it.
        background: Any = index.data(QtCore.Qt.ItemDataRole.BackgroundRole)
        if isinstance(background, QtGui.QBrush) and background.style() != QtCore.Qt.BrushStyle.NoBrush:
            option.state = option.state & ~QtWidgets.QStyle.StateFlag.State_MouseOver
        else:
            pass


class LogSeverityTreeView(QtWidgets.QTreeView):
    """
    Tree view that fills complete severity rows, including the branch gutter.
    """
    __slots__ = tuple()

    def drawRow(self,
                painter: QtGui.QPainter,
                option: QtWidgets.QStyleOptionViewItem,
                index: QtCore.QModelIndex) -> None:
        """
        Paint one tree row.

        :param painter: Painter used by Qt for the viewport.
        :param option: Style option containing the row rectangle.
        :param index: First-column index for the row being painted.
        :return: None.
        """
        # Severity rows store a background brush on column zero; child rows keep the normal theme paint.
        background: Any = index.data(QtCore.Qt.ItemDataRole.BackgroundRole)
        if isinstance(background, QtGui.QBrush) and background.style() != QtCore.Qt.BrushStyle.NoBrush:
            painter.fillRect(option.rect, background)
        else:
            pass

        super(LogSeverityTreeView, self).drawRow(painter, option, index)


class MTreeExpandHook(QtCore.QObject):
    """
    MTreeExpandHook( QTreeView )
    """

    def __init__(self, tree):
        super(MTreeExpandHook, self).__init__()
        self.setParent(tree)
        # NOTE viewport for click event listen
        tree.viewport().installEventFilter(self)
        self.tree = tree

    def eventFilter(self, receiver, event):
        if (
                # NOTE mouse left click
                event.type() == QtCore.QEvent.Type.MouseButtonPress
                # NOTE keyboard shift press
                and event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            # NOTE get mouse local position
            pos = self.tree.mapFromGlobal(QtGui.QCursor.pos())
            index = self.tree.indexAt(pos)
            if not self.tree.isExpanded(index):
                # NOTE expand all child
                self.tree.expandRecursively(index)
                return True
        return super(MTreeExpandHook, self).eventFilter(self.tree, event)


class LogsDialogue(CenteredDialog):
    """
    New profile dialogue window
    """

    def __init__(self, name: str, logger: Logger, expand_all=True, modal: bool = True,
                 parent: QWidget | None = None):
        """

        :param name:
        :param logger:
        :param expand_all:
        :param modal:
        """
        super(LogsDialogue, self).__init__(parent=parent)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.logger: Logger = logger

        self.setModal(modal)

        # logs_list
        self.logs_table = LogSeverityTreeView()
        model = fill_tree_from_logs(logger)
        self.logs_table.setModel(model)
        self.log_severity_delegate: LogSeverityItemDelegate = LogSeverityItemDelegate(self.logs_table)
        self.logs_table.setItemDelegate(self.log_severity_delegate)
        self.logs_table.setAnimated(True)
        self.logs_table.setAlternatingRowColors(True)
        self.logs_table.setUniformRowHeights(True)
        self.logs_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.logs_table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.logs_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.logs_table.setAllColumnsShowFocus(True)
        self.logs_table.header().setStretchLastSection(False)
        self.logs_table.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.logs_table.setColumnWidth(0, 320)
        # MTreeExpandHook(self.logs_table)

        if expand_all:
            self.logs_table.expandAll()
        else:
            pass

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText(self.tr('Accept'))
        self.accept_btn.clicked.connect(self.accept_click)

        self.save_btn = QtWidgets.QPushButton()
        self.save_btn.setText(self.tr('Save'))
        self.save_btn.clicked.connect(self.save_click)

        self.copy_btn = QtWidgets.QPushButton()
        self.copy_btn.setText(self.tr('Copy'))
        self.copy_btn.clicked.connect(self.copy_click)

        self.btn_frame = QtWidgets.QFrame()
        self.btn_layout = QtWidgets.QHBoxLayout(self.btn_frame)
        self.btn_spacer = QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Policy.Expanding)
        self.btn_layout.addWidget(self.save_btn)
        self.btn_layout.addWidget(self.copy_btn)
        self.btn_layout.addSpacerItem(self.btn_spacer)
        self.btn_layout.addWidget(self.accept_btn)
        self.btn_frame.setLayout(self.btn_layout)

        # add all to the GUI
        self.main_layout.addWidget(self.logs_table)
        self.main_layout.addWidget(self.btn_frame)

        self.setLayout(self.main_layout)

        self.setWindowTitle(name)

        h = 400
        self.resize(int(1.61 * h), h)

    def accept_click(self) -> None:
        """
        Accept and close
        """
        self.accept()

    def save_click(self):
        """
        Save the logs to excel or CSV
        """
        file, filter_ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self.tr("Export results"),
            '',
            filter=self.tr("CSV (*.csv);;Excel files (*.xlsx)"),
        )

        if file != '':
            if 'xlsx' in filter_:
                f = file
                if not f.endswith('.xlsx'):
                    f += '.xlsx'
                self.logger.to_xlsx(f)

            if 'csv' in filter_:
                f = file
                if not f.endswith('.csv'):
                    f += '.csv'
                self.logger.to_csv(f)

    def copy_click(self):
        """
        Copy logs to the clipboard
        """
        df = self.logger.to_df()
        s = io.StringIO()
        df.to_csv(s, sep='\t')
        txt = s.getvalue()

        # copy to clipboard
        cb = QtWidgets.QApplication.clipboard()
        cb.clear()
        cb.setText(txt)


class DeviceSelectorPanel(QtWidgets.QFrame):
    """
    Searchable panel to select one device from a device tree.
    """

    selection_made = QtCore.Signal(object)
    selection_cancelled = QtCore.Signal()

    def __init__(self,
                 devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]],
                 allow_none: bool = False,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """
        Constructor.

        :param devices_by_type: Dictionary with device types and their devices.
        :param allow_none: Add a selectable None entry.
        :param parent: Parent widget.
        """
        QtWidgets.QFrame.__init__(self, parent=parent)

        self.devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]] = devices_by_type
        self.allow_none: bool = allow_none
        self.selected_device: ALL_DEV_TYPES | None = None
        self.has_selection: bool = False
        self.resize_grip_at_top: bool = False

        # Build the visible search controls before the model is populated.
        self.main_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        self.search_box: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self)
        self.search_box.setPlaceholderText(self.tr("Search"))
        self.search_box.setAttribute(QtCore.Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.tree_view: QtWidgets.QTreeView = QtWidgets.QTreeView(self)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        # Keep a source model and filter proxy so the item payloads survive searches.
        self.source_model: QtGui.QStandardItemModel = QtGui.QStandardItemModel(self)
        self.proxy_model: QtCore.QSortFilterProxyModel = QtCore.QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)
        self.proxy_model.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(0)
        self.proxy_model.setFilterRole(QtCore.Qt.ItemDataRole.UserRole + 2)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.tree_view.setModel(self.proxy_model)

        self.button_box: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.size_grip: PopupResizeGrip = PopupResizeGrip(parent=self)

        self.main_layout.addWidget(self.search_box)
        self.main_layout.addWidget(self.tree_view)
        self.main_layout.addWidget(self.button_box)

        self.search_box.textChanged.connect(self.apply_filter)
        self.tree_view.doubleClicked.connect(self.accept_index)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.fill_tree()
        self.position_size_grip()

    @staticmethod
    def normalize_search_text(text: str) -> str:
        """
        Normalize case and diacritics for selector matching.

        The visible text remains unchanged, so composed characters and input
        methods keep working while an unaccented query can match accented names.

        :param text: Visible device name or user query.
        :return: Case-folded text without combining diacritical marks.
        """
        decomposed_text: str = unicodedata.normalize('NFD', text)
        normalized_text: str = ''.join(
            character for character in decomposed_text if unicodedata.combining(character) == 0
        ).casefold()
        return normalized_text

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """
        Focus the search field when the selector popup opens.

        :param event: Widget show event.
        :return: None.
        """
        super().showEvent(event)
        self.search_box.setFocus(QtCore.Qt.FocusReason.PopupFocusReason)

    def set_resize_grip_at_top(self, value: bool) -> None:
        """
        Select the vertical edge used by the resize handle.

        :param value: True to place the handle on the top edge.
        :return: None.
        """
        self.resize_grip_at_top = value
        self.size_grip.set_resize_from_top(value=value)
        self.position_size_grip()

    def position_size_grip(self) -> None:
        """
        Place the resize handle on the active right border corner of the popup.

        :return: None.
        """
        x_position: int = max(0, self.width() - self.size_grip.width())

        if self.resize_grip_at_top:
            y_position: int = 0
        else:
            y_position = max(0, self.height() - self.size_grip.height())

        self.size_grip.move(x_position, y_position)
        self.size_grip.raise_()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """
        Keep the resize handle attached to the border while the popup changes size.

        :param event: Resize event.
        :return: None.
        """
        super().resizeEvent(event)
        self.position_size_grip()

    def _finish_selection(self, selected_device: ALL_DEV_TYPES | None) -> None:
        """
        Store and emit one valid selection.

        :param selected_device: Selected device or None.
        :return: None.
        """
        self.selected_device = selected_device
        self.has_selection = True
        self.selection_made.emit(selected_device)

    def fill_tree(self) -> None:
        """
        Fill the tree model with one top-level row per device type.

        :return: None.
        """
        self.source_model.clear()

        if self.allow_none:
            # The None row clears an existing object link through the same selector flow.
            none_item: QtGui.QStandardItem = QtGui.QStandardItem(self.tr("None"))
            none_item.setEditable(False)
            none_item.setData(True, QtCore.Qt.ItemDataRole.UserRole + 1)
            none_item.setData(
                self.normalize_search_text(none_item.text()),
                QtCore.Qt.ItemDataRole.UserRole + 2,
            )
            self.source_model.appendRow(none_item)
        else:
            pass

        for device_type, devices in self.devices_by_type.items():
            if len(devices) > 0:
                # Device type rows group leaves but are not assignable values.
                device_type_item: QtGui.QStandardItem = QtGui.QStandardItem(device_type.value)
                icon_path: str | None = device_type_icons.get(device_type.value, None)
                if icon_path is not None:
                    device_type_item.setIcon(QtGui.QIcon(icon_path))
                else:
                    pass

                device_type_item.setEditable(False)
                device_type_item.setSelectable(False)
                device_type_item.setData(
                    self.normalize_search_text(device_type_item.text()),
                    QtCore.Qt.ItemDataRole.UserRole + 2,
                )

                for device in devices:
                    # Device objects are stored in UserRole while names remain the visible text.
                    device_item: QtGui.QStandardItem = QtGui.QStandardItem(device.name)
                    if icon_path is not None:
                        device_item.setIcon(QtGui.QIcon(icon_path))
                    else:
                        pass

                    device_item.setEditable(False)
                    device_item.setData(device, QtCore.Qt.ItemDataRole.UserRole)
                    device_item.setData(True, QtCore.Qt.ItemDataRole.UserRole + 1)
                    device_item.setData(
                        self.normalize_search_text(device_item.text()),
                        QtCore.Qt.ItemDataRole.UserRole + 2,
                    )
                    device_type_item.appendRow(device_item)

                self.source_model.appendRow(device_type_item)
            else:
                pass

        self.tree_view.expandAll()

    def apply_filter(self, text: str) -> None:
        """
        Apply the search text to the tree proxy model.

        :param text: Text to search.
        :return: None.
        """
        # Qt's proxy handles recursive matching through the device tree.
        normalized_text: str = self.normalize_search_text(text)
        escaped_text: str = QtCore.QRegularExpression.escape(normalized_text)
        expression: QtCore.QRegularExpression = QtCore.QRegularExpression(escaped_text)
        expression.setPatternOptions(QtCore.QRegularExpression.PatternOption.CaseInsensitiveOption)
        self.proxy_model.setFilterRegularExpression(expression)
        self.tree_view.expandAll()

    def accept_index(self, proxy_index: QtCore.QModelIndex) -> None:
        """
        Accept the dialogue when a device leaf is double-clicked.

        :param proxy_index: Index received from the filtered tree view.
        :return: None.
        """
        source_index: QtCore.QModelIndex = self.proxy_model.mapToSource(proxy_index)
        selected_device: ALL_DEV_TYPES | None = self.source_model.data(
            source_index,
            QtCore.Qt.ItemDataRole.UserRole,
        )
        is_selectable_value: bool = self.source_model.data(
            source_index,
            QtCore.Qt.ItemDataRole.UserRole + 1,
        ) is True

        if is_selectable_value:
            self._finish_selection(selected_device=selected_device)
        else:
            pass

    def accept(self) -> None:
        """
        Accept the dialogue if one device is selected.

        :return: None.
        """
        selected_index: QtCore.QModelIndex = self.tree_view.currentIndex()

        if selected_index.isValid():
            source_index: QtCore.QModelIndex = self.proxy_model.mapToSource(selected_index)
            selected_device: ALL_DEV_TYPES | None = self.source_model.data(
                source_index,
                QtCore.Qt.ItemDataRole.UserRole,
            )
            is_selectable_value: bool = self.source_model.data(
                source_index,
                QtCore.Qt.ItemDataRole.UserRole + 1,
            ) is True

            if is_selectable_value:
                self._finish_selection(selected_device=selected_device)
            else:
                pass
        else:
            pass

    def reject(self) -> None:
        """
        Emit cancellation.

        :return: None.
        """
        self.selection_cancelled.emit()

    def get_selected_device(self) -> ALL_DEV_TYPES | None:
        """
        Get the selected device.

        :return: Selected device or None.
        """
        return self.selected_device


class DeviceSelectorDialogue(CenteredDialog):
    """
    Dialogue to select one device from a searchable device tree.
    """

    def __init__(self,
                 devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]],
                 allow_none: bool = False,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """
        Constructor.

        :param devices_by_type: Dictionary with device types and their devices.
        :param allow_none: Add a selectable None entry.
        :param parent: Parent widget.
        """
        CenteredDialog.__init__(self, parent=parent)

        self.setWindowTitle(self.tr("Device selection"))
        self.setSizeGripEnabled(True)
        self.resize(500, 600)

        self.panel: DeviceSelectorPanel = DeviceSelectorPanel(
            devices_by_type=devices_by_type,
            allow_none=allow_none,
            parent=self,
        )

        self.main_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        self.main_layout.addWidget(self.panel)

        self.panel.selection_made.connect(self.accept)
        self.panel.selection_cancelled.connect(self.reject)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """
        Keep the selector visible on the current screen when it opens.

        :param event: Show event.
        :return: None.
        """
        CenteredDialog.showEvent(self, event)

        screen: QtGui.QScreen | None = self.screen()

        if screen is None:
            screen = QApplication.primaryScreen()
        else:
            pass

        if screen is not None:
            available_geometry: QtCore.QRect = screen.availableGeometry()
            frame_geometry: QtCore.QRect = self.frameGeometry()

            if frame_geometry.width() > available_geometry.width() or frame_geometry.height() > available_geometry.height():
                new_width: int = min(self.width(), available_geometry.width())
                new_height: int = min(self.height(), available_geometry.height())
                self.resize(new_width, new_height)
                frame_geometry = self.frameGeometry()
            else:
                pass

            if frame_geometry.left() < available_geometry.left():
                frame_geometry.moveLeft(available_geometry.left())
            else:
                pass

            if frame_geometry.right() > available_geometry.right():
                frame_geometry.moveRight(available_geometry.right())
            else:
                pass

            if frame_geometry.top() < available_geometry.top():
                frame_geometry.moveTop(available_geometry.top())
            else:
                pass

            if frame_geometry.bottom() > available_geometry.bottom():
                frame_geometry.moveBottom(available_geometry.bottom())
            else:
                pass

            self.move(frame_geometry.topLeft())
        else:
            pass

    @property
    def has_selection(self) -> bool:
        """
        Return whether a selectable row has been accepted.

        :return: True when a value was selected.
        """
        return self.panel.has_selection

    def get_selected_device(self) -> ALL_DEV_TYPES | None:
        """
        Get the selected device.

        :return: Selected device or None.
        """
        return self.panel.get_selected_device()


class BusConnectionObject:
    """
    Minimal object used by ObjectsModel to edit a list of bus connections.
    """

    __slots__ = ("device_type", "property_list", "selected_buses")

    def __init__(self, bus_count: int) -> None:
        """
        Constructor.

        :param bus_count: Number of bus properties to expose.
        """
        self.device_type: DeviceType = DeviceType.BusDevice
        self.property_list: List[GCProp] = list()
        self.selected_buses: List[ALL_DEV_TYPES | None] = list()

        if bus_count == 1:
            self.property_list.append(GCProp(prop_name="bus",
                                             units="",
                                             tpe=DeviceType.BusDevice,
                                             definition="Connection bus"))
            self.selected_buses.append(None)
        else:
            self.property_list.append(GCProp(prop_name="bus_from",
                                             units="",
                                             tpe=DeviceType.BusDevice,
                                             definition="From bus"))
            self.selected_buses.append(None)
            self.property_list.append(GCProp(prop_name="bus_to",
                                             units="",
                                             tpe=DeviceType.BusDevice,
                                             definition="To bus"))
            self.selected_buses.append(None)

            for i in range(2, bus_count):
                bus_number: int = i + 1
                self.property_list.append(GCProp(prop_name=f"bus_{bus_number}",
                                                 units="",
                                                 tpe=DeviceType.BusDevice,
                                                 definition=f"Bus {bus_number}"))
                self.selected_buses.append(None)

    def get_value(self, prop: GCProp, t_idx: int | None) -> ALL_DEV_TYPES | None:
        """
        Get one bus property value.

        :param prop: Property descriptor.
        :param t_idx: Unused time index.
        :return: Selected bus or None.
        """
        for i, local_prop in enumerate(self.property_list):
            if prop.name == local_prop.name:
                return self.selected_buses[i]
            else:
                pass

        return None

    def set_value(self, prop: GCProp, t_idx: int | None, value: ALL_DEV_TYPES | None) -> None:
        """
        Set one bus property value.

        :param prop: Property descriptor.
        :param t_idx: Unused time index.
        :param value: Selected bus.
        :return: None.
        """
        for i, local_prop in enumerate(self.property_list):
            if prop.name == local_prop.name:
                self.selected_buses[i] = value
            else:
                pass

    def get_buses(self) -> List[ALL_DEV_TYPES | None]:
        """
        Get the selected buses in property order.

        :return: Selected bus list.
        """
        return self.selected_buses

    def __str__(self) -> str:
        """
        Get the row header label.

        :return: Object label.
        """
        return "Buses"


class NewConnectedDeviceDialogue(CenteredDialog):
    """
    Dialogue to define a new device name and its connected buses.
    """

    def __init__(self,
                 name: str,
                 bus_count: int,
                 buses: List[ALL_DEV_TYPES],
                 parent: QtWidgets.QWidget | None = None,
                 allow_last_bus_none: bool = False) -> None:
        """
        Constructor.

        :param name: Default device name.
        :param bus_count: Number of buses that must be selected.
        :param buses: Available buses.
        :param parent: Parent widget.
        :param allow_last_bus_none: Allow the last bus slot to remain empty.
        """
        CenteredDialog.__init__(self, parent=parent)

        self.setWindowTitle(self.tr("New device"))
        self.resize(520, 180 + 30 * bus_count)

        self.buses: List[ALL_DEV_TYPES] = buses
        self.allow_last_bus_none: bool = allow_last_bus_none
        self.bus_connection: BusConnectionObject = BusConnectionObject(bus_count=bus_count)

        self.main_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        self.name_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self)
        self.name_edit.setText(name)
        self.bus_table: QtWidgets.QTableView = QtWidgets.QTableView(self)
        self.bus_model: ObjectsModel = ObjectsModel(
            objects=[self.bus_connection],
            property_list=self.bus_connection.property_list,
            time_index=None,
            parent=self.bus_table,
            editable=True,
            transposed=True,
            dictionary_of_lists={DeviceType.BusDevice: self.buses},
        )
        self.bus_table.setModel(self.bus_model)
        self.bus_table.horizontalHeader().setStretchLastSection(True)

        self.main_layout.addWidget(QtWidgets.QLabel(self.tr("Name"), self))
        self.main_layout.addWidget(self.name_edit)
        self.main_layout.addWidget(self.bus_table)

        self.button_box: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

    def accept(self) -> None:
        """
        Accept only when the name and all bus slots are filled.

        :return: None.
        """
        has_name: bool = self.name_edit.text().strip() != ""
        has_all_buses: bool = True
        has_repeated_buses: bool = False
        selected_bus_set: set[ALL_DEV_TYPES] = set()

        selected_buses: List[ALL_DEV_TYPES | None] = self.bus_connection.get_buses()
        last_bus_idx: int = len(selected_buses) - 1

        for bus_idx, selected_bus in enumerate(selected_buses):
            if selected_bus is None:
                if self.allow_last_bus_none and bus_idx == last_bus_idx:
                    pass
                else:
                    has_all_buses = False
            else:
                if selected_bus in selected_bus_set:
                    has_repeated_buses = True
                else:
                    selected_bus_set.add(selected_bus)

        if has_name and has_all_buses and not has_repeated_buses:
            CenteredDialog.accept(self)
        else:
            pass

    def get_name(self) -> str:
        """
        Get the configured device name.

        :return: Device name.
        """
        return self.name_edit.text().strip()

    def get_buses(self) -> List[ALL_DEV_TYPES | None]:
        """
        Get the selected bus list.

        :return: Selected bus list.
        """
        return self.bus_connection.get_buses()


class ElementsDialogue(CenteredDialog):
    """
    Selected elements dialogue window
    """

    def __init__(self, name, elements: Union[List[ALL_DEV_TYPES], None] = None):
        super(ElementsDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.layout = QtWidgets.QVBoxLayout(self)

        # build elements list
        self.objects_table = QtWidgets.QTableView()

        if elements is not None:
            if len(elements) > 0:
                model = ObjectsModel(objects=elements,
                                     time_index=None,
                                     property_list=list(elements[0].property_list),
                                     parent=self.objects_table,
                                     editable=False)

                self.objects_table.setModel(model)
            else:
                raise Exception("No elements passed :/")
        else:
            raise Exception("No elements passed :/")

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Proceed')
        self.accept_btn.clicked.connect(self.accept_click)

        # Copy button
        self.copy_btn = QtWidgets.QPushButton()
        self.copy_btn.setText('Copy')
        self.copy_btn.clicked.connect(self.copy_click)

        # add all to the GUI
        self.layout.addWidget(self.objects_table)
        self.frame2 = QtWidgets.QFrame()
        self.layout.addWidget(self.frame2)
        self.layout2 = QtWidgets.QHBoxLayout(self.frame2)

        self.layout2.addWidget(self.accept_btn)
        # self.layout2.addWidget(QtWidgets.QSpacerItem())
        self.layout2.addWidget(self.copy_btn)

        self.setLayout(self.layout)

        self.setWindowTitle(name)

        self.is_accepted = False

    def accept_click(self):
        """
        Accept action
        :return:
        """
        self.is_accepted = True
        self.accept()

    def copy_click(self):
        pass


class TimeReIndexDialogue(CenteredDialog):
    """
    New profile dialogue window
    """

    def __init__(self):
        super(TimeReIndexDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted = False

        # year
        d2 = datetime.now()
        self.date_time_editor = QtWidgets.QDateTimeEdit()
        self.date_time_editor.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.date_time_editor.setDateTime(QtCore.QDateTime(d2.year, d2.month, d2.day, d2.hour, d2.minute, 0))

        # time step length
        self.step_length = QtWidgets.QDoubleSpinBox()
        self.step_length.setMinimum(0.0001)
        self.step_length.setMaximum(1000)
        self.step_length.setValue(1)

        # units combo box
        self.units = QtWidgets.QComboBox()
        self.units.setModel(ComboModel(text_items=[(unit, unit) for unit in ['h', 'm', 's']]))

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText(self.tr('Accept'))
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(QtWidgets.QLabel(self.tr("Start date")))
        self.main_layout.addWidget(self.date_time_editor)

        self.main_layout.addWidget(QtWidgets.QLabel(self.tr("Time step length")))
        self.main_layout.addWidget(self.step_length)

        self.main_layout.addWidget(QtWidgets.QLabel(self.tr("Time units")))
        self.main_layout.addWidget(self.units)

        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(self.tr('Time re-index'))

        h = 120
        self.resize(h, int(1.1 * h))

    def accept_click(self):
        """
        Accept and close
        """
        self.is_accepted = True
        self.accept()


class CorrectInconsistenciesDialogue(CenteredDialog):
    """
    New profile dialogue window
    """

    def __init__(self):
        super(CorrectInconsistenciesDialogue, self).__init__()
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted = False

        self.label1 = QtWidgets.QLabel()
        self.label1.setText(self.tr("Minimum generator set point"))

        # min voltage
        self.min_voltage = QtWidgets.QDoubleSpinBox()
        self.min_voltage.setMinimum(0)
        self.min_voltage.setMaximum(2)
        self.min_voltage.setSingleStep(0.01)
        self.min_voltage.setValue(0.98)

        self.label2 = QtWidgets.QLabel()
        self.label2.setText(self.tr("Maximum generator set point"))

        # min voltage
        self.max_voltage = QtWidgets.QDoubleSpinBox()
        self.max_voltage.setMinimum(0)
        self.max_voltage.setMaximum(2)
        self.max_voltage.setSingleStep(0.01)
        self.max_voltage.setValue(1.02)

        self.label3 = QtWidgets.QLabel()
        self.label3.setText(self.tr("Maximum virtual tap difference"))

        self.max_virtual_tap = QtWidgets.QDoubleSpinBox()
        self.max_virtual_tap.setMinimum(0)
        self.max_virtual_tap.setMaximum(1)
        self.max_virtual_tap.setSingleStep(0.01)
        self.max_virtual_tap.setValue(0.1)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText(self.tr('Accept'))
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.min_voltage)
        self.main_layout.addWidget(self.label2)
        self.main_layout.addWidget(self.max_voltage)
        self.main_layout.addWidget(self.label3)
        self.main_layout.addWidget(self.max_virtual_tap)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(self.tr('Correct inconsistencies'))

        h = 120
        self.resize(h, int(1.1 * h))

    def accept_click(self):
        """
        Accept and close
        """
        self.is_accepted = True
        self.accept()


def clear_qt_layout(layout: QtWidgets.QLayout) -> None:
    """
    Remove all widgets from a layout object
    :param layout:
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()

        if child_layout is not None:
            clear_qt_layout(child_layout)
            child_layout.deleteLater()
        elif widget is not None:
            # Fully detach the widget now so stale layout items do not outlive it.
            widget.setParent(None)
            widget.deleteLater()


class CheckListDialogue(CenteredDialog):
    """
    New profile dialogue window
    """

    def __init__(self,
                 objects_list: List[str],
                 title='Select objects',
                 ask_for_group_name: bool = False,
                 group_label: str = "",
                 group_text: str = "",
                 default: List[bool] | None = None,
                 default_val: bool = True):
        """

        :param objects_list: List of names to display
        :param title: Window title
        :param ask_for_group_name: Ask for a group name (i.e. investments group name...)
        :param group_label: Name of the property
        :param group_text: Tentative group name
        """
        CenteredDialog.__init__(self)

        self.objects_list = objects_list
        self.default_vals = default if default is not None else [default_val for e in objects_list]

        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False
        self.selected_indices: List[int] = list()
        self.status_dict: Dict[str, bool] = dict()

        self.label1 = QtWidgets.QLabel()
        self.label1.setText("Selected objects")

        self.group_label = QtWidgets.QLabel()
        self.group_label.setText(group_label)
        self.group_name_text = QtWidgets.QTextEdit()
        self.group_name_text.setText(group_text)
        self.group_name_text.setMaximumHeight(30)

        # list
        self.list_view = QtWidgets.QListView()
        # self.mdl = get_list_model(lst=objects_list,
        #                           checks=True,
        #                           check_value=default_val)

        self.mdl = get_chck_list_model(
            lst=objects_list,
            check_status=self.default_vals
        )

        self.list_view.setModel(self.mdl)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        if ask_for_group_name:
            self.main_layout.addWidget(self.group_label)
            self.main_layout.addWidget(self.group_name_text)

        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.list_view)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        h = 260
        self.resize(h, int(0.8 * h))

    def get_group_text(self) -> str:
        """
        Get the group text
        :return: string
        """
        return self.group_name_text.toPlainText()

    def selected(self, val: str) -> bool:
        """
        Check if the value was selected
        :param val:
        :return:
        """
        return self.status_dict.get(val, False)

    def accept_click(self):
        """
        Accept and close
        """
        self.is_accepted = True

        self.selected_indices: IntVec = get_checked_indices(self.mdl)

        for row in range(self.mdl.rowCount()):
            item = self.mdl.item(row)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                self.status_dict[self.objects_list[row]] = True
            else:
                self.status_dict[self.objects_list[row]] = False

        self.accept()


class DeleteDialogue(CenteredDialog):
    """
    New profile dialogue window
    """

    def __init__(self,
                 names_list: List[str],
                 title='Select objects',
                 delete_from_db: bool = False,
                 ask_for_group_name: bool = False,
                 group_label: str = "",
                 group_text: str = "",
                 checks=True,
                 check_value=True):
        """

        :param names_list: List of names to display
        :param title: Window title
        :param ask_for_group_name: Ask for a group name (i.e. investments group name...)
        :param group_label: Name of the property
        :param group_text: Tentative group name
        """
        CenteredDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False
        self.selected_indices: List[int] = list()

        self.label1 = QtWidgets.QLabel()
        self.label1.setText("Selected objects")

        self.group_label = QtWidgets.QLabel()
        self.group_label.setText(group_label)
        self.group_name_text = QtWidgets.QTextEdit()
        self.group_name_text.setText(group_text)
        self.group_name_text.setMaximumHeight(30)

        # list
        self.list_view = QtWidgets.QListView()
        self.mdl = get_list_model(names_list, checks=checks, check_value=check_value)
        self.list_view.setModel(self.mdl)

        # delete_with_dialogue from DB check
        self.delete_from_db_check = QtWidgets.QCheckBox()
        self.delete_from_db_check.setText(r'Remove from the database')
        self.delete_from_db_check.setChecked(delete_from_db)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        if ask_for_group_name:
            self.main_layout.addWidget(self.group_label)
            self.main_layout.addWidget(self.group_name_text)

        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.list_view)
        self.main_layout.addWidget(self.delete_from_db_check)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        h = 260
        self.resize(h, int(0.8 * h))

    @property
    def delete_from_db(self):
        return self.delete_from_db_check.isChecked()

    def get_group_text(self) -> str:
        """
        Get the group text
        :return: string
        """
        return self.group_name_text.toPlainText()

    def accept_click(self):
        """
        Accept and close
        """
        self.is_accepted = True

        self.selected_indices: IntVec = get_checked_indices(self.mdl)
        self.accept()


class InputNumberDialogue(CenteredDialog):
    """
    New InputNumberDialogue window
    """

    def __init__(self, min_value: float, max_value: float, default_value: float, is_int: bool = False,
                 title='Select objects', text='', decimals=2, suffix='', h=80, w=240):
        """

        :param min_value:
        :param max_value:
        :param is_int:
        :param title:
        :param text:
        :param decimals:
        :param suffix:
        :param h:
        :param w:
        """
        CenteredDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False
        self.value = 0 if is_int else 0.0

        self.label1 = QtWidgets.QLabel()
        self.label1.setText(text)

        # min voltage
        self.input_box = QtWidgets.QSpinBox() if is_int else QtWidgets.QDoubleSpinBox()
        self.input_box.setMinimum(min_value)
        self.input_box.setMaximum(max_value)
        self.input_box.setSuffix(suffix)
        self.input_box.setValue(default_value)

        if not is_int:
            self.input_box.setDecimals(decimals)

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.input_box)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        self.resize(w, h)

    def accept_click(self):
        """
        Accept and close
        """
        self.is_accepted = True

        self.value = self.input_box.value()
        self.accept()


class InputSearchDialogue(CenteredDialog):
    """
    New InputNumberDialogue window
    """

    def __init__(self, deafault_value: str, title='Search', prompt='', h=80, w=240):
        """
        :default_value:
        :param title:
        :param prompt:
        :param h:
        :param w:
        """

        self.searchText = ""
        CenteredDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False

        self.label1 = QtWidgets.QLabel()
        self.label1.setText(prompt)

        # min voltage
        self.input_box = QtWidgets.QLineEdit()

        # search button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Search')
        self.accept_btn.clicked.connect(self.search_click)

        # add all to the GUI
        self.main_layout.addWidget(self.label1)
        self.main_layout.addWidget(self.input_box)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        self.resize(w, h)

    def search_click(self):
        """
        Serach and close
        """
        self.is_accepted = True

        self.searchText = self.input_box.text()
        self.accept()


class StartEndSelectionDialogue(CenteredDialog):
    """
    New StartEndSelectionDialogue window
    """

    def __init__(self, min_value: int, max_value: int, time_array,
                 title='Simulation limits selection', h=80, w=240):
        """

        :param min_value:
        :param max_value:
        :param time_array:
        :param title:
        :param h:
        :param w:
        """
        CenteredDialog.__init__(self)
        self.setObjectName("self")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.is_accepted: bool = False

        self.time_array = time_array
        nt = len(time_array) - 1

        self.start_slider = QtWidgets.QSlider()
        self.start_slider.setMinimum(0)
        self.start_slider.setMaximum(nt)
        self.start_slider.setValue(min_value)
        self.start_slider.valueChanged.connect(self.slider_change)
        self.start_slider.setOrientation(QtCore.Qt.Orientation.Horizontal)

        self.start_label = QtWidgets.QLabel()

        self.end_slider = QtWidgets.QSlider()
        self.end_slider.setMinimum(0)
        self.end_slider.setMaximum(nt)
        self.end_slider.setValue(max_value)
        self.end_slider.valueChanged.connect(self.slider_change)
        self.end_slider.setOrientation(QtCore.Qt.Orientation.Horizontal)

        self.end_label = QtWidgets.QLabel()

        # accept button
        self.accept_btn = QtWidgets.QPushButton()
        self.accept_btn.setText('Accept')
        self.accept_btn.clicked.connect(self.accept_click)

        # add all to the GUI
        self.main_layout.addWidget(self.start_slider)
        self.main_layout.addWidget(self.start_label)
        self.main_layout.addWidget(self.end_slider)
        self.main_layout.addWidget(self.end_label)
        self.main_layout.addWidget(self.accept_btn)

        self.setLayout(self.main_layout)

        self.setWindowTitle(title)

        self.start_value = min_value
        self.end_value = max_value

        self.resize(w, h)

        self.slider_change()

    def slider_change(self):
        """
        On any slider change...
        """
        self.start_value = self.start_slider.value()
        self.end_value = self.end_slider.value()

        if self.start_value > self.end_value:
            self.end_slider.setValue(self.start_value)
            self.end_value = self.start_value

        t1 = pd.to_datetime(self.time_array[self.start_value]).strftime('%d/%m/%Y %H:%M')
        t2 = pd.to_datetime(self.time_array[self.end_value]).strftime('%d/%m/%Y %H:%M')
        self.start_label.setText(str(t1))
        self.end_label.setText(str(t2) + ' [{0}]'.format(self.end_value - self.start_value))

    def accept_click(self):
        """
        Accept and close
        """
        self.is_accepted = True

        self.accept()


class CustomQuestionDialogue(CenteredDialog):
    """
    Custom question dialogue
    """

    def __init__(self, title: str, question: str, answer1: str, answer2: str):
        super().__init__()

        self.setWindowTitle(title)

        layout = QtWidgets.QVBoxLayout()
        button_layout = QtWidgets.QHBoxLayout()

        label = QtWidgets.QLabel(question)
        label.setWordWrap(True)
        layout.addWidget(label)

        button_layout.addSpacerItem(QtWidgets.QSpacerItem(10, 10, QtWidgets.QSizePolicy.Policy.Expanding))

        button_1 = QtWidgets.QPushButton(answer1)
        button_1.clicked.connect(self.b1_clicked)
        button_layout.addWidget(button_1)

        button_2 = QtWidgets.QPushButton(answer2)
        button_2.clicked.connect(self.b2_clicked)
        button_layout.addWidget(button_2)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.accepted_answer = 0

    def b1_clicked(self):
        """
        Button 1 clicked
        :return:
        """
        self.accepted_answer = 1
        self.accept()

    def b2_clicked(self):
        """
        Button 2 clicked
        :return:
        """
        self.accepted_answer = 2
        self.accept()


class ArrayTableModel(QAbstractTableModel):
    """
    ArrayTableModel
    """

    def __init__(self, data: List[np.ndarray], headers: List[str]):
        super().__init__()

        self._data = data
        self.headers = headers

    def get_data(self) -> List[np.ndarray]:
        """
        Get the model internal data
        :return: list of arrays
        """
        return self._data

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """

        :param parent:
        :return:
        """
        return self._data[0].shape[0]

    def columnCount(self, parent: QModelIndex = QModelIndex()):
        """

        :param parent:
        :return:
        """
        return len(self._data)  # We have two columns, one for each array

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """

        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.headers[section]
            if orientation == Qt.Orientation.Vertical:
                return section  # To show row numbers starting from 0
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Union[None, str]:
        """

        :param index:
        :param role:
        :return:
        """
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            row = index.row()
            column = index.column()
            return str(self._data[column][row])

        return None

    def setData(self, index: QModelIndex, value: float, role=Qt.ItemDataRole.EditRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        if not index.isValid():
            return False

        if role == Qt.ItemDataRole.EditRole:
            row = index.row()
            column = index.column()
            try:
                value = float(value)
            except ValueError:
                return False

            self._data[column][row] = value

            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
            return True

        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """

        :param index:
        :return:
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

    def insertRows(self, position: int, rows=1, parent=QModelIndex()):
        """

        :param position:
        :param rows:
        :param parent:
        :return:
        """
        self.beginInsertRows(parent, position, position + rows - 1)

        for i in range(len(self._data)):
            self._data[i] = np.insert(self._data[i], position, [0] * rows)

        # set active to true
        self._data[0][-1] = 1

        self.endInsertRows()
        return True

    def removeRows(self, position: int, rows=1, parent=QModelIndex()):
        """

        :param position:
        :param rows:
        :param parent:
        :return:
        """
        self.beginRemoveRows(parent, position, position + rows - 1)

        for i in range(len(self._data)):
            self._data[i] = np.delete(self._data[i], slice(position, position + rows))

        self.endRemoveRows()
        return True


class ArrayEditor(CenteredDialog):
    """
    ArrayEditor
    """

    def __init__(self):
        CenteredDialog.__init__(self)

        self.setWindowTitle(self.tr("Array Editor"))

        self._g_steps = np.arange(10)
        self._b_steps = np.arange(10)
        self.model = ArrayTableModel(data=[self._g_steps, self._b_steps], headers=["G", "B"])

        self.table_view = QTableView()
        self.table_view.setModel(self.model)

        self.add_button = QPushButton(self.tr("Add"))
        self.delete_button = QPushButton(self.tr("Delete"))

        self.add_button.clicked.connect(self.add_row)
        self.delete_button.clicked.connect(self.delete_row)

        layout = QVBoxLayout()
        layout.addWidget(self.table_view)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.delete_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def add_row(self):
        """
        Add row
        """
        row_count = self.model.rowCount()
        self.model.insertRows(row_count, 1)

    def delete_row(self):
        """
        Delete the selected rows
        """
        selected_indexes = self.table_view.selectionModel().selectedIndexes()

        rows = list({index.row() for index in selected_indexes})
        rows.sort(reverse=True)
        for r in rows:
            self.model.removeRows(position=r, rows=1)


# ----------------------------------------------------
# VALIDITY RULES
# ----------------------------------------------------


# class ShortCircuitSelector(CenteredDialog):
#     """
#     ShortCircuitSelector
#     """
#
#     def __init__(self) -> None:
#         super().__init__()
#         self.setWindowTitle("Short Circuit Configuration")
#
#         layout = QVBoxLayout(self)
#
#         # Fault type
#         self.cb_fault = QComboBox()
#         self.cb_fault.addItems([e.value for e in FaultType])
#         layout.addWidget(QLabel("Fault type:"))
#         layout.addWidget(self.cb_fault)
#
#         # Method
#         self.cb_method = QComboBox()
#         self.cb_method.addItems([e.value for e in MethodShortCircuit])
#         layout.addWidget(QLabel("Method:"))
#         layout.addWidget(self.cb_method)
#
#         # Phases
#         self.cb_phases = QComboBox()
#         self.cb_phases.addItems([e.value for e in PhasesShortCircuit])
#         self.phases_label = QLabel("Phases:")
#         layout.addWidget(self.phases_label)
#         layout.addWidget(self.cb_phases)
#
#         # --- VERTICAL SPACER ---
#         layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
#
#         # Accept button
#         self.btn_accept = QPushButton("Accept")
#         layout.addWidget(self.btn_accept)
#
#         # Logic connections
#         self.cb_fault.currentIndexChanged.connect(self.update_logic)
#         self.btn_accept.clicked.connect(self.accept_clicked)
#
#         self.update_logic()
#         self.fault = FaultType(self.cb_fault.currentText())
#         self.method = MethodShortCircuit(self.cb_method.currentText())
#         self.phases = PhasesShortCircuit(self.cb_phases.currentText())
#
#         self.was_accepted = False
#
#         self.cb_method.currentTextChanged.connect(self.update_view)
#
#     def update_view(self):
#         """
#
#         :return:
#         """
#
#         fault = FaultType(self.cb_fault.currentText())
#
#         # -------- UPDATE PHASES --------
#         if self.cb_method.currentText() == MethodShortCircuit.sequences.value:
#             self.cb_phases.setVisible(False)
#             self.phases_label.setVisible(False)
#         else:
#             self.cb_phases.setVisible(True)
#             self.phases_label.setVisible(True)
#             allowed_phases = valid_phases_for_fault(fault)
#             current_phase = self.cb_phases.currentText()
#
#             self.cb_phases.clear()
#             for p in allowed_phases:
#                 self.cb_phases.addItem(p.value)
#
#             if current_phase in [p.value for p in allowed_phases]:
#                 self.cb_phases.setCurrentText(current_phase)
#
#     def update_logic(self):
#         """Update available method and phase options based on the fault type."""
#
#         fault = FaultType(self.cb_fault.currentText())
#
#         # -------- UPDATE METHOD --------
#         allowed_methods = valid_methods_for_fault(fault)
#         current_method = self.cb_method.currentText()
#
#         self.cb_method.clear()
#         for m in allowed_methods:
#             self.cb_method.addItem(m.value)
#
#         if current_method in [m.value for m in allowed_methods]:
#             self.cb_method.setCurrentText(current_method)
#
#         # -------- UPDATE PHASES --------
#         if current_method == MethodShortCircuit.sequences.value:
#             self.cb_phases.setVisible(False)
#             self.phases_label.setVisible(False)
#         else:
#             self.cb_phases.setVisible(True)
#             self.phases_label.setVisible(True)
#             allowed_phases = valid_phases_for_fault(fault)
#             current_phase = self.cb_phases.currentText()
#
#             self.cb_phases.clear()
#             for p in allowed_phases:
#                 self.cb_phases.addItem(p.value)
#
#             if current_phase in [p.value for p in allowed_phases]:
#                 self.cb_phases.setCurrentText(current_phase)
#
#         self.fault = FaultType(self.cb_fault.currentText())
#         self.method = MethodShortCircuit(self.cb_method.currentText())
#         self.phases = PhasesShortCircuit(self.cb_phases.currentText())
#
#     def get_selection(self):
#         """Return the selected configuration as enums."""
#         return (
#             FaultType(self.cb_fault.currentText()),
#             MethodShortCircuit(self.cb_method.currentText()),
#             PhasesShortCircuit(self.cb_phases.currentText()),
#         )
#
#     def accept_clicked(self):
#         """Check if values are valid and close dialog."""
#         self.fault = FaultType(self.cb_fault.currentText())
#         self.method = MethodShortCircuit(self.cb_method.currentText())
#         self.phases = PhasesShortCircuit(self.cb_phases.currentText())
#         self.was_accepted = True
#         self.close()


class FileTypeSelector(CenteredDialog):
    """
    FileTypeSelector
    """

    def __init__(self, file_name: List[str] | str) -> None:
        super().__init__()
        self.setWindowTitle(self.tr("Select how to load the file"))
        self.setModal(False)
        layout = QVBoxLayout(self)

        if isinstance(file_name, list):
            txt = self.tr("You've passed a generic list of files\nselect the expected processing format")

            xml_types_count = 0
            ucte_types_count = 0
            for f in file_name:
                if f.endswith(".xml"):
                    xml_types_count += 1
                elif f.endswith(".zip"):
                    xml_types_count += 1
                elif f.endswith(".uct"):
                    ucte_types_count += 1
                elif f.endswith(".ucte"):
                    ucte_types_count += 1

            if xml_types_count > 0:
                tpes = [FileType.CGMES, FileType.CIM, FileType.Iidm]
            elif ucte_types_count > 0:
                tpes = [FileType.UCTE]
            else:
                tpes = []

        elif isinstance(file_name, str):
            txt = self.tr("You've passed a generic of file\nselect the expected processing format")

            if file_name.endswith(".xml"):
                tpes = [FileType.CGMES, FileType.CIM, FileType.Iidm]
            elif file_name.endswith(".zip"):
                tpes = [FileType.CGMES, FileType.CIM, FileType.Iidm]
            elif file_name.endswith(".uct"):
                tpes = [FileType.UCTE]
            elif file_name.endswith(".ucte"):
                tpes = [FileType.UCTE]
            else:
                tpes = []

        else:
            raise ValueError("Files should be a list of a string")

        # Text
        layout.addWidget(QLabel(txt))

        # Method
        self.cb_method = QComboBox()
        for tpe in tpes:
            self.cb_method.addItem(self.tr(tpe.value), tpe)
        layout.addWidget(QLabel(self.tr("Format:")))
        layout.addWidget(self.cb_method)

        # --- VERTICAL SPACER ---
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Accept button
        self.btn_accept = QPushButton(self.tr("Accept"))
        layout.addWidget(self.btn_accept)

        # Logic connections
        self.btn_accept.clicked.connect(self.accept_clicked)

        self.was_accepted = False
        self.file_type: FileType | None = None

    def accept_clicked(self):
        """Check if values are valid and close dialog."""
        self.file_type = self.cb_method.currentData()
        self.was_accepted = True
        self.close()


class CgmesOptionsSelector(CenteredDialog):
    """
    FileTypeSelector
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.tr("Select the CGMES options"))
        self.setModal(False)
        layout = QVBoxLayout(self)

        tpes = [CGMESVersions.v2_4_15, CGMESVersions.v3_0_0]

        # Method
        self.cb_method = QComboBox()
        for tpe in tpes:
            self.cb_method.addItem(self.tr(tpe.value), tpe)
        layout.addWidget(QLabel(self.tr("CGMES Version:")))
        layout.addWidget(self.cb_method)

        # --- VERTICAL SPACER ---
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Accept button
        self.btn_accept = QPushButton(self.tr("Accept"))
        layout.addWidget(self.btn_accept)

        # Logic connections
        self.btn_accept.clicked.connect(self.accept_clicked)

        self.was_accepted = False
        self.version: CGMESVersions | None = None

    def accept_clicked(self):
        """Check if values are valid and close dialog."""
        self.version = self.cb_method.currentData()
        self.was_accepted = True
        self.close()

# if __name__ == "__main__":
#     import sys
#
#     app = QApplication(sys.argv)
#     w = ShortCircuitSelector()
#     w.show()
#     sys.exit(app.exec())

# from PySide6.QtWidgets import QApplication
#
# app = QApplication(sys.argv)
# # window = InputNumberDialogue(min_value=3,
# #                              max_value=10,
# #                              default_value=3,
# #                              is_int=True,
# #                              title="stuff",
# #                              text="valor? fsd..xcfh.dfgbhdfbflb.lsdfnblsndf.bnsdf.bn.xdfnb.xdfbñlxdhfn.blxnd",
# #                              suffix=' cosas')
#
# window = CustomQuestionDialogue(title="My question",
#                                 question="What do you want " * 10,
#                                 answer1="Go home",
#                                 answer2="stay here")
#
# window.show()
# sys.exit(app.exec())

# app = QApplication(sys.argv)
# window = ArrayEditor()
# window.resize(400, 300)
# window.show()
# sys.exit(app.exec())
