# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
from enum import Enum
from typing import Callable, Dict, List, Union, Any, Tuple, TYPE_CHECKING, Set, Sequence
from PySide6 import QtCore, QtWidgets, QtGui
from collections import defaultdict

from VeraGridEngine import X_Y_SequenceType
from VeraGridEngine.basic_structures import IntVec, BoolVec
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit, CGMES_ASSETS
from VeraGridEngine.IO.cim.cgmes.base import Base as CgmesBase
from VeraGridEngine.Devices.Branches.line_locations import LineLocations
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.enumerations import SimulationTypes, WindingType, WaveformSequenceType, V_I_CurveSequenceType
from VeraGrid.Gui.font_config import MENU_FONT_SIZE
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely, exec_dialog_safely, is_dialog_available
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue

if TYPE_CHECKING:
    from VeraGrid.Gui.object_model import ObjectsModel


ComboStableKey = Union[str, int, float, bool, None]


class BoolCheckboxDelegate(QtWidgets.QStyledItemDelegate):
    """
    Delegate that paints boolean values as checkboxes and toggles them on double click.
    """

    def __init__(self, parent: QtWidgets.QTableView) -> None:
        """
        Constructor.

        :param parent: Parent table view.
        """
        QtWidgets.QStyledItemDelegate.__init__(self, parent)

    def get_checkbox_rect(self, option: QtWidgets.QStyleOptionViewItem) -> QtCore.QRect:
        """
        Get a centered checkbox rectangle for one cell.

        :param option: Cell style option.
        :return: Checkbox rectangle.
        """
        checkbox_option: QtWidgets.QStyleOptionButton = QtWidgets.QStyleOptionButton()
        style: QtWidgets.QStyle

        if option.widget is not None:
            style = option.widget.style()
        else:
            style = QtWidgets.QApplication.style()

        checkbox_rect: QtCore.QRect = style.subElementRect(
            QtWidgets.QStyle.SubElement.SE_CheckBoxIndicator,
            checkbox_option,
            option.widget,
        )
        x_position: int = option.rect.x() + int((option.rect.width() - checkbox_rect.width()) / 2)
        y_position: int = option.rect.y() + int((option.rect.height() - checkbox_rect.height()) / 2)

        return QtCore.QRect(x_position, y_position, checkbox_rect.width(), checkbox_rect.height())

    def paint(self,
              painter: QtGui.QPainter,
              option: QtWidgets.QStyleOptionViewItem,
              index: QtCore.QModelIndex) -> None:
        """
        Paint the cell as a centered checkbox.

        :param painter: Painter.
        :param option: Cell style option.
        :param index: Model index.
        :return: None.
        """
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            painter.fillRect(option.rect, option.palette.base())

        checkbox_option: QtWidgets.QStyleOptionButton = QtWidgets.QStyleOptionButton()
        checkbox_option.rect = self.get_checkbox_rect(option=option)
        checkbox_option.state = QtWidgets.QStyle.StateFlag.State_Enabled

        if index.data(QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.Checked:
            checkbox_option.state = checkbox_option.state | QtWidgets.QStyle.StateFlag.State_On
        else:
            checkbox_option.state = checkbox_option.state | QtWidgets.QStyle.StateFlag.State_Off

        if option.widget is not None:
            option.widget.style().drawPrimitive(
                QtWidgets.QStyle.PrimitiveElement.PE_IndicatorCheckBox,
                checkbox_option,
                painter,
                option.widget,
            )
        else:
            QtWidgets.QApplication.style().drawPrimitive(
                QtWidgets.QStyle.PrimitiveElement.PE_IndicatorCheckBox,
                checkbox_option,
                painter,
            )

    def createEditor(self,
                     parent: QtWidgets.QWidget,
                     option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> None:
        """
        Disable edit widgets for checkbox cells.

        :param parent: Parent widget.
        :param option: Cell style option.
        :param index: Model index.
        :return: None.
        """
        del parent
        del option
        del index
        return None

    def editorEvent(self,
                    event: QtCore.QEvent,
                    model: QtCore.QAbstractItemModel,
                    option: QtWidgets.QStyleOptionViewItem,
                    index: QtCore.QModelIndex) -> bool:
        """
        Toggle the boolean value on double click.

        :param event: Editor event.
        :param model: Table model.
        :param option: Cell style option.
        :param index: Model index.
        :return: True when the value was toggled.
        """
        del option

        if event.type() == QtCore.QEvent.Type.MouseButtonDblClick:
            if isinstance(event, QtGui.QMouseEvent) and event.button() == QtCore.Qt.MouseButton.LeftButton:
                current_state: object = index.data(QtCore.Qt.ItemDataRole.CheckStateRole)

                if current_state == QtCore.Qt.CheckState.Checked:
                    new_state: QtCore.Qt.CheckState = QtCore.Qt.CheckState.Unchecked
                else:
                    new_state = QtCore.Qt.CheckState.Checked

                return model.setData(index, new_state, QtCore.Qt.ItemDataRole.CheckStateRole)
            else:
                return False
        else:
            return False


def translate_context_menu_text(text: str) -> str:
    """
    Translate one runtime-created context-menu label.

    :param text: Source label.
    :return: Translated label or the original text when no catalog entry exists.
    """
    if text == "":
        return text

    translated_text: str = QtCore.QCoreApplication.translate("ContextMenu", text)
    return translated_text if translated_text != "" else text


class TreeDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning QComboBox in every
    cell of the column to which it's applied
    """
    commitData = QtCore.Signal(object)
    """
    
    """

    def __init__(self, parent, data=None):
        """
        Constructor
        :param parent: QTableView parent object
        :param data: dictionary of lists
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

        # dictionary of lists
        self.data = data if data is not None else defaultdict()

    @QtCore.Slot()
    def double_click(self):
        """
        double click
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        tree = QtWidgets.QTreeView(parent)

        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(['Template'])

        for key in self.data.keys():
            # add parent node
            parent1 = QtGui.QStandardItem(str(key))

            # add children to parent
            for elm in self.data[key]:
                child1 = QtGui.QStandardItem(str(elm))
                parent1.appendRow([child1])

            model.appendRow(parent1)

        tree.setModel(model)
        tree.doubleClicked.connect(self.double_click)
        return tree

    def setEditorData(self, editor, index):
        """

        :param editor:
        :param index:
        """
        print(editor)
        print(index)

    def setModelData(self, editor, model, index):
        """

        :param editor:
        :param model:
        :param index:
        """
        print(editor)
        print(model)
        print(index)

        # model.setData(index, self.object_names[editor.currentIndex()])


class ComboDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning QComboBox in every
    cell of the column to which it's applied
    """
    commitData = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QTableView, objects: List[Any], object_names: List[str]) -> None:
        """
        Constructor
        :param parent: QTableView parent object
        :param objects: List of objects to set. i.e. [True, False] or [Line1, Line2, ...]
        :param object_names: List of Object names to display. i.e. ['True', 'False']
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

        # objects to sent to the model associated to the combobox. i.e. [True, False]
        self.objects = objects

        # object description to display in the combobox. i.e. ['True', 'False']
        self.object_names = object_names

    @QtCore.Slot()
    def currentIndexChanged(self) -> None:
        """
        currentIndexChanged
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index: QtCore.QModelIndex):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(self.object_names)
        combo.currentIndexChanged.connect(self.currentIndexChanged)
        return combo

    def setEditorData(self, editor: QtWidgets.QComboBox, index: QtCore.QModelIndex):
        """
        Open the editor at the cell's current value. The match is done on the actual
        object (EditRole) first and only then on the display string, because for plain
        (non str-mixin) enums str(value) legitimately differs from the display name.

        :param editor: combo editor
        :param index: model index being edited
        """
        editor.blockSignals(True)

        obj_val = index.model().data(index, role=QtCore.Qt.ItemDataRole.EditRole)
        if obj_val in self.objects:
            editor.setCurrentIndex(self.objects.index(obj_val))
        else:
            display_val = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
            if display_val in self.object_names:
                editor.setCurrentIndex(self.object_names.index(display_val))
            else:
                # unknown current value so we keep the editor at its default position 
                pass

        editor.blockSignals(False)

    def setModelData(self,
                     editor: QtWidgets.QComboBox,
                     model: QtCore.QAbstractItemModel,
                     index: QtCore.QModelIndex):
        """

        :param editor:
        :param model:
        :param index:
        """
        if len(self.objects) > 0:
            if editor.currentIndex() < len(self.objects):
                model.setData(index, self.objects[editor.currentIndex()])


class TextDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning QLineEdit in every
    cell of the column to which it's applied
    """

    commitData = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QTableView) -> None:
        """
        Constructor
        :param parent: QTableView parent object
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

    @QtCore.Slot()
    def returnPressed(self):
        """
        returnPressed
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent: QtWidgets.QWidget,
                     option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> QtWidgets.QLineEdit:
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        editor = QtWidgets.QLineEdit(parent)
        editor.returnPressed.connect(self.returnPressed)
        return editor

    def setEditorData(self, editor: QtWidgets.QLineEdit, index):
        """

        :param editor:
        :param index:
        """
        editor.blockSignals(True)
        val = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
        editor.setText(val)
        editor.blockSignals(False)

    def setModelData(self, editor: QtWidgets.QLineEdit, model, index):
        """

        :param editor:
        :param model:
        :param index:
        """
        model.setData(index, editor.text())


class FloatDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning QDoubleSpinBox in every
    cell of the column to which it's applied
    """

    commitData = QtCore.Signal(object)

    def __init__(self,
                 parent: QtWidgets.QTableView,
                 min_: float = -1e200,
                 max_: float = 1e200,
                 decimals: int = 6) -> None:
        """
        Constructor
        :param parent: QTableView parent object
        """
        QtWidgets.QItemDelegate.__init__(self, parent)
        self.min = min_
        self.max = max_
        self.decimals = decimals

    @QtCore.Slot()
    def returnPressed(self) -> None:
        """
        returnPressed
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent: QtWidgets.QWidget,
                     option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> QtWidgets.QDoubleSpinBox:
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        editor = QtWidgets.QDoubleSpinBox(parent)
        editor.setMaximum(self.max)
        editor.setMinimum(self.min)
        editor.setDecimals(self.decimals)
        editor.editingFinished.connect(self.returnPressed)
        return editor

    def setEditorData(self, editor: QtWidgets.QDoubleSpinBox, index):
        """

        :param editor:
        :param index:
        """
        editor.blockSignals(True)
        try:
            val = float(index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole))
        except ValueError:
            val = 0.0
        editor.setValue(val)
        editor.blockSignals(False)

    def setModelData(self, editor: QtWidgets.QDoubleSpinBox, model, index):
        """

        :param editor:
        :param model:
        :param index:
        """
        model.setData(index, editor.value())


class IntDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning QDoubleSpinBox in every
    cell of the column to which it's applied
    """

    commitData = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QTableView, min_: int = -99999, max_: int = 99999) -> None:
        """
        Constructor
        :param parent: QTableView parent object
        """
        QtWidgets.QItemDelegate.__init__(self, parent)
        self.min = min_
        self.max = max_

    @QtCore.Slot()
    def returnPressed(self):
        """
        returnPressed
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        editor = QtWidgets.QSpinBox(parent)
        editor.setMaximum(self.max)
        editor.setMinimum(self.min)
        editor.editingFinished.connect(self.returnPressed)
        return editor

    def setEditorData(self, editor: QtWidgets.QDoubleSpinBox, index):
        """

        :param editor:
        :param index:
        """
        editor.blockSignals(True)
        val = int(index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole))
        # try:
        #     val = int(index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole))
        # except ValueError:
        #     val = 1
        editor.setValue(val)
        editor.blockSignals(False)

    def setModelData(self, editor: QtWidgets.QDoubleSpinBox, model, index):
        """

        :param editor:
        :param model:
        :param index:
        """
        model.setData(index, editor.value())


class ComplexDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning Complex Editor in every
    cell of the column to which it's applied
    """

    commitData = QtCore.Signal(object)

    def __init__(self, parent):
        """
        Constructor
        :param parent: QTableView parent object
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

    @QtCore.Slot()
    def returnPressed(self):
        """

        :return:
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        editor = QtWidgets.QFrame(parent)
        main_layout = QtWidgets.QHBoxLayout(editor)
        main_layout.layout().setContentsMargins(0, 0, 0, 0)

        real = QtWidgets.QDoubleSpinBox()
        real.setMaximum(9999)
        real.setMinimum(-9999)
        real.setDecimals(8)

        imag = QtWidgets.QDoubleSpinBox()
        imag.setMaximum(9999)
        imag.setMinimum(-9999)
        imag.setDecimals(8)

        main_layout.addWidget(real)
        main_layout.addWidget(imag)
        # main_layout.addWidget(button)

        # button.clicked.connect(self.returnPressed)

        return editor

    def setEditorData(self, editor: QtWidgets.QFrame, index):
        """

        :param editor:
        :param index:
        :return:
        """
        editor.blockSignals(True)
        val = complex(index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole))
        editor.children()[1].setValue(val.real)
        editor.children()[2].setValue(val.imag)
        editor.blockSignals(False)

    def setModelData(self, editor: QtWidgets.QFrame, model, index):
        """

        :param editor:
        :param model:
        :param index:
        :return:
        """
        val = complex(editor.children()[1].value(), editor.children()[2].value())
        model.setData(index, val)


class LineLocationsDelegate(QtWidgets.QItemDelegate):
    """
    A delegate that places a fully functioning LineLocations Editor in every
    cell of the column to which it's applied
    """

    commitData = QtCore.Signal(object)

    def __init__(self, parent):
        """
        Constructor
        :param parent: QTableView parent object
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

        self.line_locations: Union[None, LineLocations] = None

    @QtCore.Slot()
    def returnPressed(self):
        """

        :return:
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent: QtWidgets.QWidget,
                     option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        editor = QtWidgets.QFrame(parent)
        main_layout = QtWidgets.QHBoxLayout(editor)
        main_layout.layout().setContentsMargins(0, 0, 0, 0)

        table = QtWidgets.QTableView()

        main_layout.addWidget(table)
        # main_layout.addWidget(button)

        # button.clicked.connect(self.returnPressed)
        editor.showNormal()

        return editor

    def setEditorData(self, editor: QtWidgets.QFrame, index):
        """

        :param editor:
        :param index:
        :return:
        """
        editor.blockSignals(True)
        self.line_locations: LineLocations = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
        # editor.children()[1].setValue(val.real)
        editor.blockSignals(False)

    def setModelData(self, editor: QtWidgets.QFrame, model: ObjectsModel, index):
        """

        :param editor:
        :param model:
        :param index:
        :return:
        """
        table = editor.children()[1]
        # model.setData(index, val)


class ColorPickerDelegate(QtWidgets.QItemDelegate):
    """
    Color picker delegate
    """
    commitData = QtCore.Signal(object)

    def __init__(self, parent):
        """

        :param parent:
        """
        super(ColorPickerDelegate, self).__init__(parent)

    @QtCore.Slot()
    def returnPressed(self):
        """

        :return:
        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        colorDialog = QtWidgets.QColorDialog(parent)
        return colorDialog

    def setEditorData(self, editor: QtWidgets.QColorDialog, index):
        """

        :param editor:
        :param index:
        """
        editor.blockSignals(True)
        val = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
        color = QtGui.QColor.fromString(val)
        editor.setCurrentColor(color)
        editor.blockSignals(False)

    def setModelData(self, editor: QtWidgets.QColorDialog, model, index):
        """

        :param editor:
        :param model:
        :param index:
        :return:
        """
        model.setData(index, editor.currentColor().name())


class DateTimeDelegate(QtWidgets.QItemDelegate):
    """
    DateTime picker delegate that handles Unix epoch seconds
    and can be initialized with a default epoch date.
    """
    commitData = QtCore.Signal(object)

    def __init__(self, parent, default_epoch: int = 0):
        super().__init__(parent)
        # Store default epoch or None
        self.default_epoch: int = default_epoch

    @QtCore.Slot()
    def returnPressed(self):
        """

        """
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index):
        """

        :param parent:
        :param option:
        :param index:
        :return:
        """
        editor = QtWidgets.QDateTimeEdit(parent)
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("yyyy/MM/dd HH:mm:ss")

        # Set initial datetime from default_epoch if provided
        if self.default_epoch is not None:
            dt = QtCore.QDateTime.fromSecsSinceEpoch(int(self.default_epoch))
            editor.setDateTime(dt)

        editor.dateTimeChanged.connect(lambda: self.commitData.emit(editor))
        return editor

    def setEditorData(self, editor: QtWidgets.QDateTimeEdit, index):
        """

        :param editor:
        :param index:
        """
        editor.blockSignals(True)
        val = index.model().data(index, QtCore.Qt.ItemDataRole.DisplayRole)
        if isinstance(val, (int, float)):
            dt = QtCore.QDateTime.fromSecsSinceEpoch(int(val))
        elif isinstance(val, str):
            dt = QtCore.QDateTime.fromString(val, "yyyy/MM/dd")
        else:
            # fallback to current datetime or default_epoch if provided
            if self.default_epoch is not None:
                dt = QtCore.QDateTime.fromSecsSinceEpoch(int(self.default_epoch))
            else:
                dt = QtCore.QDateTime.currentDateTime()
        editor.setDateTime(dt)
        editor.blockSignals(False)

    def setModelData(self, editor: QtWidgets.QDateTimeEdit, model, index):
        """

        :param editor:
        :param model:
        :param index:
        """
        dt = editor.dateTime()
        epoch_seconds = dt.toSecsSinceEpoch()
        model.setData(index, epoch_seconds)


def get_list_model(lst: Sequence[Union[str, ALL_DEV_TYPES]],
                   checks=False,
                   check_value=False) -> QtGui.QStandardItemModel:
    """
    Pass a list to a list model
    """
    list_model = QtGui.QStandardItemModel()
    if lst is not None:
        if not checks:
            for val in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setEditable(False)
                list_model.appendRow(item)
        else:
            for val in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setEditable(False)
                item.setCheckable(True)
                if check_value:
                    item.setCheckState(QtCore.Qt.CheckState.Checked)
                list_model.appendRow(item)

    return list_model


def get_elm_chck_list_model(lst: List[ALL_DEV_TYPES], check_status: BoolVec) -> QtGui.QStandardItemModel:
    """
    Pass a list to a list model
    """
    list_model = QtGui.QStandardItemModel()
    for elm, val in zip(lst, check_status):
        # for the list model
        item = QtGui.QStandardItem(str(elm.name))
        item.setEditable(False)
        item.setCheckable(True)
        if val:
            item.setCheckState(QtCore.Qt.CheckState.Checked)
        list_model.appendRow(item)

    return list_model


def get_chck_list_model(lst: List[str], check_status: List[bool]) -> QtGui.QStandardItemModel:
    """
    Pass a list to a list model
    """
    list_model = QtGui.QStandardItemModel()
    for elm, val in zip(lst, check_status):
        # for the list model
        item = QtGui.QStandardItem(elm)
        item.setEditable(False)
        item.setCheckable(True)
        if val:
            item.setCheckState(QtCore.Qt.CheckState.Checked)
        list_model.appendRow(item)

    return list_model


class ComboModel(QtGui.QStandardItemModel):
    """
    Combo-box model storing translated display labels separately from runtime
    values and persistent configuration keys.
    """

    __slots__ = ("_translate",)

    SourceTextRole = QtCore.Qt.ItemDataRole.UserRole + 1
    StableKeyRole = QtCore.Qt.ItemDataRole.UserRole + 2

    def __init__(self,
                 enum_values: Sequence[Enum] | None = None,
                 text_items: Sequence[Tuple[str, Any]] | None = None,
                 icon_enum_values: Sequence[Tuple[Enum, str]] | None = None,
                 icon_text_items: Sequence[Tuple[str, Any, str]] | None = None,
                 translate: Callable[[str], str] | None = None) -> None:
        """
        Constructor.

        :param enum_values: Optional enum values to add immediately.
        :param text_items: Optional (label, runtime data) items to add immediately.
        :param icon_enum_values: Optional (enum value, icon path) items to add immediately.
        :param icon_text_items: Optional (label, runtime data, icon path) items to add immediately.
        :param translate: Optional label translation function, typically ``self.tr``.
        """
        QtGui.QStandardItemModel.__init__(self)
        self._translate: Callable[[str], str] | None = translate
        if enum_values is None:
            pass
        else:
            for enum_value in enum_values:
                self.add_enum(enum_value=enum_value)

        if text_items is None:
            pass
        else:
            for source_text, data in text_items:
                stable_key: ComboStableKey
                if isinstance(data, (str, int, float, bool)):
                    stable_key = data
                else:
                    stable_key = str(source_text)
                self.add_combo_item(source_text=str(source_text), data=data, stable_key=stable_key)

        if icon_enum_values is None:
            pass
        else:
            for enum_value, icon_path in icon_enum_values:
                self.add_icon_enum(enum_value=enum_value, icon_path=icon_path)

        if icon_text_items is None:
            pass
        else:
            for source_text, data, icon_path in icon_text_items:
                stable_key: ComboStableKey
                if isinstance(data, (str, int, float, bool)):
                    stable_key = data
                else:
                    stable_key = str(source_text)
                self.add_combo_item(source_text=str(source_text),
                                    data=data,
                                    stable_key=stable_key,
                                    icon_path=icon_path)

    def _get_display_text(self, source_text: str) -> str:
        """
        Get the current display text for a source label.

        :param source_text: Untranslated label.
        :return: Translated label when a translator is available.
        """
        if self._translate is None:
            return source_text
        else:
            return self._translate(source_text)

    def add_combo_item(self,
                       source_text: str,
                       data: Any,
                       stable_key: ComboStableKey,
                       icon_path: str | None = None,
                       checks: bool = False,
                       check_value: bool = False) -> None:
        """
        Add one item with separate display text, runtime data and stable key.

        :param source_text: Untranslated display label.
        :param data: Runtime value returned by ``QComboBox.currentData()``.
        :param stable_key: Serializable value used for settings persistence.
        :param icon_path: Optional icon resource path.
        :param checks: Add a check box to the item.
        :param check_value: Initial check state when checks is true.
        :return: Nothing.
        """
        display_text: str = self._get_display_text(source_text=source_text)
        item = QtGui.QStandardItem(display_text)
        item.setEditable(False)
        item.setData(data, QtCore.Qt.ItemDataRole.UserRole)
        item.setData(source_text, self.SourceTextRole)
        item.setData(stable_key, self.StableKeyRole)
        if icon_path is None:
            pass
        else:
            icon = QtGui.QIcon()
            icon.addPixmap(QtGui.QPixmap(icon_path))
            item.setIcon(icon)
        if checks:
            item.setCheckable(True)
            if check_value:
                item.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                pass
        else:
            pass
        self.appendRow(item)

    def add_text(self,
                 source_text: str,
                 data: str,
                 checks: bool = False,
                 check_value: bool = False) -> None:
        """
        Add one text-backed item.

        :param source_text: Untranslated display label.
        :param data: Runtime string value.
        :param checks: Add a check box to the item.
        :param check_value: Initial check state when checks is true.
        :return: Nothing.
        """
        self.add_combo_item(source_text=source_text,
                            data=data,
                            stable_key=data,
                            checks=checks,
                            check_value=check_value)

    def add_enum(self,
                 enum_value: Enum,
                 checks: bool = False,
                 check_value: bool = False) -> None:
        """
        Add one enum-backed item.

        :param enum_value: Runtime enum value.
        :param checks: Add a check box to the item.
        :param check_value: Initial check state when checks is true.
        :return: Nothing.
        """
        source_text: str = str(enum_value.value)
        self.add_combo_item(source_text=source_text,
                            data=enum_value,
                            stable_key=source_text,
                            checks=checks,
                            check_value=check_value)

    def add_icon_enum(self,
                      enum_value: Enum,
                      icon_path: str,
                      checks: bool = False,
                      check_value: bool = False) -> None:
        """
        Add one enum-backed item with an icon.

        :param enum_value: Runtime enum value.
        :param icon_path: Icon resource path.
        :param checks: Add a check box to the item.
        :param check_value: Initial check state when checks is true.
        :return: Nothing.
        """
        source_text: str = str(enum_value.value)
        self.add_combo_item(source_text=source_text,
                            data=enum_value,
                            stable_key=source_text,
                            icon_path=icon_path,
                            checks=checks,
                            check_value=check_value)

    def retranslate(self, translate: Callable[[str], str] | None) -> None:
        """
        Refresh all display labels from their stored source text.

        :param translate: New translation function.
        :return: Nothing.
        """
        self._translate = translate
        for row_idx in range(self.rowCount()):
            item = self.item(row_idx)
            source_text = item.data(self.SourceTextRole)
            if isinstance(source_text, str):
                item.setText(self._get_display_text(source_text=source_text))
            else:
                pass


class CustomFileSystemModel(QtWidgets.QFileSystemModel):
    """
    CustomFileSystemModel
    """

    def __init__(self, root_path: str, ext_filter: Union[None, List[str]] = None):
        super(CustomFileSystemModel, self).__init__()

        self.ext_filter = ext_filter if ext_filter is not None else ['*.py']

        self.setNameFilters(ext_filter)
        self.setRootPath(root_path)


def get_logger_tree_model(logger: DataLogger) -> QtGui.QStandardItemModel:
    """
    Fill logger tree
    :param logger: Logger instance
    :return: QStandardItemModel instance
    """
    d = logger.to_dict()
    editable = False
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(['Time', 'Element', 'Class', 'Property', 'Value', 'Expected value', 'comment'])
    parent = model.invisibleRootItem()

    for severity, messages_dict in d.items():
        severity_child = QtGui.QStandardItem(severity)

        # print(severity)

        for message, data_list in messages_dict.items():
            message_child = QtGui.QStandardItem(message)

            # print('\t', message)

            for time, elm, elm_class, elm_property, value, expected_value, comment in data_list:
                # print('\t', '\t', time, elm, value, expected_value)

                time_child = QtGui.QStandardItem(time)
                time_child.setEditable(editable)

                elm_child = QtGui.QStandardItem(str(elm))
                elm_child.setEditable(editable)

                elm_class_child = QtGui.QStandardItem(str(elm_class))
                elm_class_child.setEditable(editable)

                elm_property_child = QtGui.QStandardItem(str(elm_property))
                elm_property_child.setEditable(editable)

                value_child = QtGui.QStandardItem(str(value))
                value_child.setEditable(editable)

                expected_val_child = QtGui.QStandardItem(str(expected_value))
                expected_val_child.setEditable(editable)

                comment_val_child = QtGui.QStandardItem(str(comment))
                comment_val_child.setEditable(editable)

                message_child.appendRow([time_child, elm_child, elm_class_child,
                                         elm_property_child, value_child, expected_val_child, comment_val_child])

            message_child.setEditable(editable)

            severity_child.appendRow(message_child)

        severity_child.setEditable(editable)
        parent.appendRow(severity_child)

    return model


def get_icon_list_model(lst: List[Tuple[str, str]], checks=False,
                        check_value=False) -> QtGui.QStandardItemModel:
    """

    :param lst:
    :param checks:
    :param check_value:
    :return:
    """
    list_model = QtGui.QStandardItemModel()
    if lst is not None:
        if not checks:
            for val, icon_path in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setEditable(False)
                icon = QtGui.QIcon()
                icon.addPixmap(QtGui.QPixmap(icon_path))
                item.setIcon(icon)
                list_model.appendRow(item)
        else:
            for val, icon_path in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                icon = QtGui.QIcon()
                icon.addPixmap(QtGui.QPixmap(icon_path))
                item.setIcon(icon)
                item.setEditable(False)
                item.setCheckable(True)
                if check_value:
                    item.setCheckState(QtCore.Qt.CheckState.Checked)
                list_model.appendRow(item)

    return list_model


def get_checked_indices(mdl: QtGui.QStandardItemModel) -> IntVec:
    """
    Get a list of the selected indices in a QStandardItemModel
    :param mdl:
    :return:
    """
    idx = list()
    for row in range(mdl.rowCount()):
        item = mdl.item(row)
        if item.checkState() == QtCore.Qt.CheckState.Checked:
            idx.append(row)

    return np.array(idx)


def get_checked_values(mdl: QtGui.QStandardItemModel) -> List[str]:
    """
    Get a list of the selected values in a QStandardItemModel
    :param mdl:
    :return:
    """
    idx = list()
    for row in range(mdl.rowCount()):
        item = mdl.item(row)
        if item.checkState() == QtCore.Qt.CheckState.Checked:
            idx.append(item.text())

    return idx


def fill_model_from_dict(parent: QtGui.QStandardItem,
                         d: Dict[str, Union[Dict[str, Any], List[str]]],
                         editable=False,
                         icons: Dict[str, str] = None,
                         font_size: int = MENU_FONT_SIZE):
    """
    Fill TreeViewModel from dictionary
    :param parent: Parent QStandardItem
    :param d: item
    :param editable
    :param icons
    :param font_size
    :return: Nothing
    """
    font = QtGui.QFont()
    font.setPointSize(font_size)

    if isinstance(d, dict):
        for k, v in d.items():
            name = str(k)
            child = QtGui.QStandardItem(name)
            child.setEditable(editable)
            child.setFont(font)

            if icons is not None:
                icon_path = icons.get(name, None)
                if icon_path is not None:
                    icon_path = icons[name]
                    _icon = QtGui.QIcon()
                    _icon.addPixmap(QtGui.QPixmap(icon_path))
                    child.setIcon(_icon)
                else:
                    pass
                    # print(f"path {name} has no icon: check 'setup_objects_tree()'")

            parent.appendRow(child)
            fill_model_from_dict(parent=child, d=v, icons=icons)
    elif isinstance(d, list):
        for v in d:
            fill_model_from_dict(parent=parent, d=v, icons=icons)
    else:
        name = str(d)
        item = QtGui.QStandardItem(name)
        item.setFont(font)

        if icons is not None:
            icon_path = icons.get(name, None)
            if icon_path is not None:
                icon_path = icons[name]
                _icon = QtGui.QIcon()
                _icon.addPixmap(QtGui.QPixmap(icon_path))
                item.setIcon(_icon)
            else:
                pass
                # print(f"path {name} has no icon: check 'setup_objects_tree()'")
        item.setEditable(editable)
        parent.appendRow(item)


def get_tree_model(d, top='', icons: Dict[str, str] = None) -> QtGui.QStandardItemModel:
    """
    Build a tree model from a dictionary
    :param d: Any dictionary
    :param top: Table header
    :param icons: Dictionary of icons (name of the node, icon to match)
    :return:
    """
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels([top])
    fill_model_from_dict(model.invisibleRootItem(), d=d, editable=False, icons=icons)

    return model


def get_simulation_tree_icons() -> Dict[SimulationTypes, str]:
    """
    Build the icon map shared by simulation-oriented tree views.

    :return: Mapping from simulation types to icon resource paths.
    """
    return {
        SimulationTypes.PowerFlow_run: ':/Icons/icons/pf',
        SimulationTypes.PowerFlow3ph_run: ':/Icons/icons/pf3',
        SimulationTypes.PowerFlowTimeSeries3ph_run: ':/Icons/icons/pf3',
        SimulationTypes.PowerFlowTimeSeries_run: ':/Icons/icons/pf_ts.png',
        SimulationTypes.OPF_run: ':/Icons/icons/dcopf.png',
        SimulationTypes.OPFTimeSeries_run: ':/Icons/icons/dcopf_ts.png',
        SimulationTypes.ShortCircuit_run: ':/Icons/icons/short_circuit.png',
        SimulationTypes.LinearAnalysis_run: ':/Icons/icons/ptdf.png',
        SimulationTypes.LinearAnalysis_TS_run: ':/Icons/icons/ptdf_ts.png',
        SimulationTypes.SigmaAnalysis_run: ':/Icons/icons/sigma.png',
        SimulationTypes.StochasticPowerFlow: ':/Icons/icons/stochastic_power_flow.png',
        SimulationTypes.ContingencyAnalysis_run: ':/Icons/icons/otdf.png',
        SimulationTypes.ContingencyAnalysisTS_run: ':/Icons/icons/otdf_ts.png',
        SimulationTypes.NetTransferCapacity_run: ':/Icons/icons/atc.png',
        SimulationTypes.NetTransferCapacityTS_run: ':/Icons/icons/atc_ts.png',
        SimulationTypes.OptimalNetTransferCapacityTimeSeries_run: ':/Icons/icons/ntc_opf_ts.png',
        SimulationTypes.InputsAnalysis_run: ':/Icons/icons/stats.png',
        SimulationTypes.NodeGrouping_run: ':/Icons/icons/ml.png',
        SimulationTypes.ContinuationPowerFlow_run: ':/Icons/icons/continuation_power_flow.png',
        SimulationTypes.ClusteringAnalysis_run: ':/Icons/icons/clustering.png',
        SimulationTypes.InvestmentsEvaluation_run: ':/Icons/icons/expansion_planning.png',
        SimulationTypes.NodalCapacity_run: ':/Icons/icons/nodal_capacity.png',
        SimulationTypes.NodalCapacityTimeSeries_run: ':/Icons/icons/nodal_capacity.png',
        SimulationTypes.OPF_NTC_run: ':/Icons/icons/ntc_opf.png',
        SimulationTypes.OPF_NTC_TS_run: ':/Icons/icons/ntc_opf_ts.png',
        SimulationTypes.Reliability_run: ':/Icons/icons/reliability.png',
        SimulationTypes.RmsSmallSignal_run: ':/Icons/icons/ss_icon.png',
        SimulationTypes.RmsDynamic_run: ':/Icons/icons/dyn.png',
        SimulationTypes.EmtSmallSignal_run: ':/Icons/icons/ss_emt_icon.png',
        SimulationTypes.EmtDynamic_run: ':/Icons/icons/dyn_emt.png',
        SimulationTypes.StateEstimation_run: ':/Icons/icons/SE.png',
    }


def get_tree_item_path(item: QtGui.QStandardItem) -> List[str]:
    """
    Get the path of an item in a tree
    :param item: QStandardItem
    :return: path in a list
    """
    item_parent = item.parent()
    path = [item.text()]
    while item_parent is not None:
        parent_text = item_parent.text()
        path.append(parent_text)
        item_parent = item_parent.parent()
    path.reverse()
    return path


CIM_OBJECT_ROLE = QtCore.Qt.UserRole + 120
CIM_LOADED_ROLE = QtCore.Qt.UserRole + 121


def _get_cim_object_id(obj: Any):
    if isinstance(obj, CgmesBase) and obj.rdfid is not None:
        return obj.rdfid
    else:
        return id(obj)


def _get_cim_object_label(class_tag, device):
    if class_tag is not None:
        return class_tag
    elif isinstance(device, CgmesBase):
        return device.rdfid
    else:
        return str(device)


def _collect_cim_ancestor_ids(item: QtGui.QStandardItem) -> Set[Any]:
    ids: Set[Any] = set()
    current = item
    while current is not None:
        obj = current.data(CIM_OBJECT_ROLE)
        if obj is not None:
            ids.add(_get_cim_object_id(obj))
        current = current.parent()
    return ids


def create_cim_object_item(class_tag,
                           device: CGMES_ASSETS,
                           editable=False,
                           lazy=True) -> QtGui.QStandardItem:
    item = QtGui.QStandardItem(_get_cim_object_label(class_tag, device))
    item.setEditable(editable)
    item.setData(device, CIM_OBJECT_ROLE)
    item.setData(False, CIM_LOADED_ROLE)

    if lazy and getattr(device, 'declared_properties', None):
        # Placeholder child to show expand arrow; removed on load.
        item.appendRow(QtGui.QStandardItem(""))

    if not lazy:
        populate_cim_item_children(item, editable=editable)

    return item


def populate_cim_item_children(item: QtGui.QStandardItem, editable=False):
    """
    Populate immediate children for a CIM object item. Designed for lazy loading.
    """
    device = item.data(CIM_OBJECT_ROLE)
    if device is None:
        return

    if item.data(CIM_LOADED_ROLE):
        return

    ancestor_ids = _collect_cim_ancestor_ids(item)
    item.removeRows(0, item.rowCount())

    for property_name, cim_prop in device.declared_properties.items():

        property_value = getattr(device, property_name)

        if isinstance(property_value, CgmesBase):

            prop_id = _get_cim_object_id(property_value)
            we_are_in_a_recursive_loop = prop_id in ancestor_ids

            if not we_are_in_a_recursive_loop:
                tpe = str(property_value.tpe)
                class_name_child = create_cim_object_item(class_tag=tpe,
                                                          device=property_value,
                                                          editable=editable,
                                                          lazy=True)
                class_name_child.setEditable(editable)

                property_name_child = QtGui.QStandardItem(tpe)
                property_name_child.setEditable(editable)

                value_child = QtGui.QStandardItem(property_value.rdfid)
                value_child.setEditable(editable)
            else:
                class_name_child = QtGui.QStandardItem("Recursive object (" + str(len(ancestor_ids)) + ")")
                class_name_child.setEditable(editable)

                property_name_child = QtGui.QStandardItem(property_name)
                property_name_child.setEditable(editable)

                value_child = QtGui.QStandardItem(str(property_value))
                value_child.setEditable(editable)
        else:
            tpe = (str(type(property_value)).replace('class', '')
                   .replace("'", "")
                   .replace("<", "")
                   .replace(">", "").strip())

            class_name_child = QtGui.QStandardItem(tpe)
            class_name_child.setEditable(editable)

            property_name_child = QtGui.QStandardItem(property_name)
            property_name_child.setEditable(editable)

            value_child = QtGui.QStandardItem(str(property_value))
            value_child.setEditable(editable)

        item.appendRow([class_name_child, property_name_child, value_child])

    item.setData(True, CIM_LOADED_ROLE)


def add_cim_object_node(class_tag,
                        device: CGMES_ASSETS,
                        editable=False,
                        already_visited: Union[Set, None] = None):
    """

    :param class_tag:
    :param device:
    :param editable:
    :param already_visited:
    :return:
    """
    if already_visited is None:
        already_visited = set()

    if class_tag is None:
        class_tag = _get_cim_object_label(class_tag=None, device=device)

    # create root node
    device_child = QtGui.QStandardItem(class_tag)

    # register visit to avoid cyclic recursion
    device_id = _get_cim_object_id(device)
    already_visited.add(device_id)

    try:
        for property_name, cim_prop in device.declared_properties.items():

            property_value = getattr(device, property_name)

            if isinstance(property_value, CgmesBase):

                prop_id = _get_cim_object_id(property_value)
                we_are_in_a_recursive_loop = prop_id in already_visited

                if not we_are_in_a_recursive_loop:

                    # if the property is an object, recursively add it
                    tpe = str(property_value.tpe)
                    class_name_child = add_cim_object_node(class_tag=tpe,
                                                           device=property_value,
                                                           editable=editable,
                                                           already_visited=already_visited)
                    class_name_child.setEditable(editable)

                    property_name_child = QtGui.QStandardItem(tpe)
                    property_name_child.setEditable(editable)

                    value_child = QtGui.QStandardItem(property_value.rdfid)
                    value_child.setEditable(editable)
                else:
                    # print('Recursive loop...')
                    # return device_child
                    class_name_child = QtGui.QStandardItem("Recursive object (" + str(len(already_visited)) + ")")
                    class_name_child.setEditable(editable)

                    property_name_child = QtGui.QStandardItem(property_name)
                    property_name_child.setEditable(editable)

                    value_child = QtGui.QStandardItem(str(property_value))
                    value_child.setEditable(editable)
            else:
                # if the property is a value (float, str, bool, etc.) just add it

                tpe = (str(type(property_value)).replace('class', '')
                       .replace("'", "")
                       .replace("<", "")
                       .replace(">", "").strip())

                class_name_child = QtGui.QStandardItem(tpe)
                class_name_child.setEditable(editable)

                property_name_child = QtGui.QStandardItem(property_name)
                property_name_child.setEditable(editable)

                value_child = QtGui.QStandardItem(str(property_value))
                value_child.setEditable(editable)

            device_child.appendRow([class_name_child, property_name_child, value_child])
    finally:
        already_visited.discard(device_id)

    return device_child


def get_cim_tree_model(cim_model: CgmesCircuit):
    """
    Fill logger tree
    :param cim_model: Logger instance
    :return: QStandardItemModel instance
    """

    editable = False
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(['Object class', 'Property', 'Value'])
    root_node = model.invisibleRootItem()

    for class_name, device_list in cim_model.elements_by_type.items():

        class_child = QtGui.QStandardItem(class_name + " (" + str(len(device_list)) + ")")

        for device in device_list:
            # add device with all it's properties
            device_child = create_cim_object_item(class_tag=None,
                                                  device=device,
                                                  editable=editable,
                                                  lazy=True)

            device_child.setEditable(editable)

            class_child.appendRow(device_child)

        class_child.setEditable(editable)
        root_node.appendRow(class_child)

    return model


def add_sub_menu(menu: QtWidgets.QMenu,
                 text: str,
                 icon_path: str = "",
                 icon_pixmap: QtGui.QPixmap = None, ):
    entry = menu.addMenu(translate_context_menu_text(text))

    if icon_pixmap is None:
        if len(icon_path) > 0:
            edit_icon = QtGui.QIcon()
            edit_icon.addPixmap(QtGui.QPixmap(icon_path))
            entry.setIcon(edit_icon)
    else:
        # prefer the icon pixmap if provided
        edit_icon = QtGui.QIcon()
        edit_icon.addPixmap(icon_pixmap)
        entry.setIcon(edit_icon)

    return entry


def add_menu_entry(menu: QtWidgets.QMenu,
                   text: str,
                   icon_path: str = "",
                   icon_pixmap: QtGui.QPixmap = None,
                   function_ptr=None,
                   checkeable=False,
                   checked_value=False,
                   font_size: int = MENU_FONT_SIZE) -> QtGui.QAction:
    """
    Add a context menu entry
    :param menu:
    :param text:
    :param icon_path:
    :param icon_pixmap:
    :param function_ptr:
    :param checkeable:
    :param checked_value:
    :param font_size:
    :return:
    """

    entry: QtGui.QAction = menu.addAction(translate_context_menu_text(text))

    font = QtGui.QFont()
    font.setPointSize(font_size)
    entry.setFont(font)

    if checkeable:
        entry.setCheckable(checkeable)
        entry.setChecked(bool(checked_value))

    if icon_pixmap is None:
        if len(icon_path) > 0:
            edit_icon = QtGui.QIcon()
            edit_icon.addPixmap(QtGui.QPixmap(icon_path))
            entry.setIcon(edit_icon)
    else:
        # prefer the icon pixmap if provided
        edit_icon = QtGui.QIcon()
        edit_icon.addPixmap(icon_pixmap)
        entry.setIcon(edit_icon)

    if function_ptr is not None:
        entry.triggered.connect(function_ptr)

    return entry


def create_spinbox(value: float, minimum: float, maximum: float, decimals: int = 4) -> QtWidgets.QDoubleSpinBox:
    """

    :param value:
    :param minimum:
    :param maximum:
    :param decimals:
    :return:
    """
    sn_spinner = QtWidgets.QDoubleSpinBox()
    sn_spinner.setMinimum(minimum)
    sn_spinner.setMaximum(maximum)
    sn_spinner.setDecimals(decimals)
    sn_spinner.setValue(value)
    return sn_spinner


def create_int_spinbox(value: int, minimum: int, maximum: int) -> QtWidgets.QSpinBox:
    """

    :param value:
    :param minimum:
    :param maximum:
    :return:
    """
    sn_spinner = QtWidgets.QSpinBox()
    sn_spinner.setMinimum(minimum)
    sn_spinner.setMaximum(maximum)
    sn_spinner.setValue(value)
    return sn_spinner


class AsyncTask(QtCore.QRunnable):
    def __init__(self, task):
        super().__init__()
        self.task = task

    @QtCore.Slot()
    def run(self):
        self.task()


def create_menu_button(parent,
                       toolbar: QtWidgets.QToolBar,
                       position: QtGui.QAction,
                       actions: List[QtGui.QAction],
                       pixmap_name: str="",
                       tooltip_text: str = "",
                       remove_actions: bool = True) -> QtWidgets.QToolButton:
    """

    :param parent: parent widget
    :param toolbar: Toolbar to insert the button
    :param position: Position at which to insert the button
    :param actions: List of actions to pack
    :param pixmap_name: optional button icon
    :param tooltip_text: Tooltip text to show
    :param remove_actions: optional remove actions
    :return: QToolButton
    """
    button = QtWidgets.QToolButton(parent)

    if pixmap_name != "":
        button.setIcon(QtGui.QPixmap(pixmap_name))
    else:
        button.setIcon(actions[0].icon())

    button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)

    if tooltip_text != "":
        button.setToolTip(tooltip_text)
    else:
        button.setToolTip(actions[0].toolTip())

    menu = QtWidgets.QMenu(button)
    for action in actions:
        menu.addAction(action)
    button.setMenu(menu)

    # Main click executes the first action
    button.clicked.connect(actions[0].trigger)

    toolbar.insertWidget(position, button)

    # Remove the original actions from the toolbar so they are only available in the menu
    if remove_actions:
        for action in actions:
            toolbar.removeAction(action)

    return button


class WaveformPoint:
    __slots__ = ("time", "value")

    def __init__(self, time: float, value: float):
        self.time = time
        self.value = value

    def __repr__(self):
        return f"WaveformPoint({self.time}, {self.value})"


class SequenceEditorDialog(QtWidgets.QDialog):
    def __init__(self, parent, sequence_type: WaveformSequenceType | V_I_CurveSequenceType | X_Y_SequenceType ):
        super().__init__(parent)
        self.sequence_type = sequence_type
        self._plot_dialogue: PlotDialogue | None = None
        self.setWindowTitle(self.tr("Sequence editor"))
        self.setMinimumSize(600, 500)

        layout = QtWidgets.QVBoxLayout(self)

        button_layout = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("Add point")
        self.delete_btn = QtWidgets.QPushButton("Delete point")
        self.up_btn = QtWidgets.QPushButton("Move up")
        self.down_btn = QtWidgets.QPushButton("Move down")

        self.add_btn.clicked.connect(self.add_point)
        self.delete_btn.clicked.connect(self.delete_point)
        self.up_btn.clicked.connect(self.move_up)
        self.down_btn.clicked.connect(self.move_down)

        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.up_btn)
        button_layout.addWidget(self.down_btn)
        layout.addLayout(button_layout)

        self.table = QtWidgets.QTableWidget(0, 2)
        if self.sequence_type is type[V_I_CurveSequenceType]:
            self.table.setHorizontalHeaderLabels(["Voltage", "Current"])
        elif self.sequence_type is type[WaveformSequenceType]:
            self.table.setHorizontalHeaderLabels(["time", "value"])
        elif self.sequence_type is type[X_Y_SequenceType]:
            self.table.setHorizontalHeaderLabels(["X", "Y"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self.plot_button: QtWidgets.QPushButton = QtWidgets.QPushButton(self.tr("Show plot"), self)
        self.plot_button.clicked.connect(self.show_plot)
        layout.addWidget(self.plot_button)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Release the retained native plot dialog before closing.

        :param event: Qt close event.
        :return: None.
        """
        self.close_plot_dialogue()
        QtWidgets.QDialog.closeEvent(self, event)

    def done(self, result: int) -> None:
        """
        Release the retained native plot dialog before accepting or rejecting.

        :param result: Qt dialog result code.
        :return: None.
        """
        self.close_plot_dialogue()
        QtWidgets.QDialog.done(self, result)

    def show_plot(self) -> None:
        """Show the current sequence in one retained native chart dialog.

        :return: None.
        """
        self.close_plot_dialogue()
        self._plot_dialogue = PlotDialogue(title=self.tr("Sequence plot"), parent=self)
        self.update_plot()
        self._plot_dialogue.show()

    def close_plot_dialogue(self) -> None:
        """Dispose the owned modeless chart before this editor is destroyed.

        :return: None.
        """
        if is_dialog_available(self._plot_dialogue):
            self._plot_dialogue.reject()
            delete_dialog_safely(dialog=self._plot_dialogue)
        else:
            pass
        self._plot_dialogue = None

    def add_point(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem("0.0"))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem("0.0"))
        self.update_plot()

    def delete_point(self):
        rows = sorted(set(i.row() for i in self.table.selectedIndexes()), reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self.update_plot()

    def move_up(self):
        rows = sorted(set(i.row() for i in self.table.selectedIndexes()))
        if len(rows) == 0 or rows[0] == 0:
            return
        for r in rows:
            self.swap_rows(r, r - 1)
        self.update_plot()

    def move_down(self):
        rows = sorted(set(i.row() for i in self.table.selectedIndexes()), reverse=True)
        if len(rows) == 0 or rows[-1] == self.table.rowCount() - 1:
            return
        for r in rows:
            self.swap_rows(r, r + 1)
        self.update_plot()

    def swap_rows(self, r1: int, r2: int):
        t1 = self.table.item(r1, 0)
        v1 = self.table.item(r1, 1)
        t2 = self.table.item(r2, 0)
        v2 = self.table.item(r2, 1)

        if t1 is None:
            t1 = QtWidgets.QTableWidgetItem("0.0")
            self.table.setItem(r1, 0, t1)
        if v1 is None:
            v1 = QtWidgets.QTableWidgetItem("0.0")
            self.table.setItem(r1, 1, v1)
        if t2 is None:
            t2 = QtWidgets.QTableWidgetItem("0.0")
            self.table.setItem(r2, 0, t2)
        if v2 is None:
            v2 = QtWidgets.QTableWidgetItem("0.0")
            self.table.setItem(r2, 1, v2)

        t1_text = t1.text()
        v1_text = v1.text()
        t1.setText(t2.text())
        v1.setText(v2.text())
        t2.setText(t1_text)
        v2.setText(v1_text)

    def update_plot(self):
        values_0: list[float] = list()
        values_1: list[float] = list()
        for row in range(self.table.rowCount()):
            item_0 = self.table.item(row, 0)
            item_1 = self.table.item(row, 1)
            if item_0 is not None and item_1 is not None:
                try:
                    values_0.append(float(item_0.text()))
                    values_1.append(float(item_1.text()))
                except ValueError:
                    pass

        if is_dialog_available(self._plot_dialogue) and len(values_0) > 0:
            x_axis_title: str = "X"
            y_axis_title: str = "Y"
            if self.sequence_type is V_I_CurveSequenceType:
                x_axis_title = self.tr("Voltage")
                y_axis_title = self.tr("Current")
            elif self.sequence_type is WaveformSequenceType:
                x_axis_title = self.tr("Time")
                y_axis_title = self.tr("Value")
            else:
                pass
            accepted: bool = self._plot_dialogue.set_line_series(
                x_values=np.asarray(values_0, dtype=float),
                series_names=(self.tr("Sequence"),),
                series_values=(np.asarray(values_1, dtype=float),),
                title=self.tr("Sequence plot"),
                x_axis_title=x_axis_title,
                y_axis_title=y_axis_title,
            )
            if accepted:
                self._plot_dialogue.chart.add_scatter_series(
                    name="",
                    x_values=np.asarray(values_0, dtype=float),
                    y_values=np.asarray(values_1, dtype=float),
                    color="#2563eb",
                )
            else:
                self._plot_dialogue.chart.clear()
        elif is_dialog_available(self._plot_dialogue):
            self._plot_dialogue.chart.clear()
        else:
            pass

    def accept(self) -> None:
        # points count check
        if self.sequence_type in [type[WaveformSequenceType], type[X_Y_SequenceType]]:
            row_count = self.table.rowCount()
            if row_count < 2:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("Invalid number of points"),
                    self.tr("At least two points are required."),
                )
                return

        # increasing values check
        if self.sequence_type in [type[WaveformSequenceType], type[X_Y_SequenceType]]:
            row_count = self.table.rowCount()
            prev_x: float | None = None
            for row in range(row_count):
                item = self.table.item(row, 0)
                if item is None:
                    continue
                try:
                    x = float(item.text())
                except ValueError:
                    QtWidgets.QMessageBox.warning(
                        self,
                        self.tr("Invalid values"),
                        self.tr("Non-numeric value in column 0 at row {row_number}.").format(row_number=row + 1),
                    )
                    return
                if prev_x is not None and x <= prev_x:
                    if self.sequence_type is WaveformSequenceType:
                        QtWidgets.QMessageBox.warning(
                            self,
                            self.tr("Invalid waveform"),
                            self.tr("Arbitrary source waveform times must be strictly increasing."),
                        )

                    elif self.sequence_type is X_Y_SequenceType:
                        QtWidgets.QMessageBox.warning(
                            self,
                            self.tr("Invalid points"),
                            self.tr("y points must be strictly increasing."),
                        )
                    return
                prev_x = x

        super().accept()

    def set_points(self, points):
        self.table.setRowCount(0)
        for p in points:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(p[0])))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(p[1])))
        self.update_plot()

    def get_points(self):
        points = []
        for row in range(self.table.rowCount()):
            t_item = self.table.item(row, 0)
            v_item = self.table.item(row, 1)
            if t_item is not None and v_item is not None:
                try:
                    t = float(t_item.text())
                    v = float(v_item.text())
                    points.append(np.array([t, v], dtype=np.float64))
                except ValueError:
                    pass
        return points


class LookupMatrixEditorDialog(QtWidgets.QDialog):
    """
    Dialog for editing a 2-D lookup matrix.

    The user edits X breakpoints and Y breakpoints in two separate tables.
    A third table shows the Z matrix whose first row holds the X values,
    first column holds the Y values, and the remaining cells are the
    user-editable Z values.  Both the row and column headers update
    dynamically whenever X or Y points change.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plot_dialogue: PlotDialogue | None = None
        self.setWindowTitle(self.tr("Lookup matrix editor"))
        self.setMinimumSize(750, 650)

        main_layout = QtWidgets.QVBoxLayout(self)

        # ── X points section ────────────────────────────────────────────
        x_group = QtWidgets.QGroupBox("X breakpoints")
        x_layout = QtWidgets.QHBoxLayout(x_group)

        self.x_table = QtWidgets.QTableWidget(0, 1)
        self.x_table.setHorizontalHeaderLabels(["X"])
        self.x_table.horizontalHeader().setStretchLastSection(True)
        self.x_table.setSelectionBehavior(QtWidgets.QTableWidget.SelectionBehavior.SelectRows)
        self.x_table.setMaximumHeight(150)
        self.x_table.itemChanged.connect(self._on_x_changed)
        x_layout.addWidget(self.x_table)

        x_btn_layout = QtWidgets.QVBoxLayout()
        self.x_add_btn = QtWidgets.QPushButton("Add")
        self.x_del_btn = QtWidgets.QPushButton("Delete")
        self.x_up_btn = QtWidgets.QPushButton("Up")
        self.x_down_btn = QtWidgets.QPushButton("Down")
        self.x_add_btn.clicked.connect(self._add_x)
        self.x_del_btn.clicked.connect(self._del_x)
        self.x_up_btn.clicked.connect(self._up_x)
        self.x_down_btn.clicked.connect(self._down_x)
        for btn in (self.x_add_btn, self.x_del_btn, self.x_up_btn, self.x_down_btn):
            x_btn_layout.addWidget(btn)
        x_btn_layout.addStretch()
        x_layout.addLayout(x_btn_layout)

        main_layout.addWidget(x_group)

        # ── Y points section ────────────────────────────────────────────
        y_group = QtWidgets.QGroupBox("Y breakpoints")
        y_layout = QtWidgets.QHBoxLayout(y_group)

        self.y_table = QtWidgets.QTableWidget(0, 1)
        self.y_table.setHorizontalHeaderLabels(["Y"])
        self.y_table.horizontalHeader().setStretchLastSection(True)
        self.y_table.setSelectionBehavior(QtWidgets.QTableWidget.SelectionBehavior.SelectRows)
        self.y_table.setMaximumHeight(150)
        self.y_table.itemChanged.connect(self._on_y_changed)
        y_layout.addWidget(self.y_table)

        y_btn_layout = QtWidgets.QVBoxLayout()
        self.y_add_btn = QtWidgets.QPushButton("Add")
        self.y_del_btn = QtWidgets.QPushButton("Delete")
        self.y_up_btn = QtWidgets.QPushButton("Up")
        self.y_down_btn = QtWidgets.QPushButton("Down")
        self.y_add_btn.clicked.connect(self._add_y)
        self.y_del_btn.clicked.connect(self._del_y)
        self.y_up_btn.clicked.connect(self._up_y)
        self.y_down_btn.clicked.connect(self._down_y)
        for btn in (self.y_add_btn, self.y_del_btn, self.y_up_btn, self.y_down_btn):
            y_btn_layout.addWidget(btn)
        y_btn_layout.addStretch()
        y_layout.addLayout(y_btn_layout)

        main_layout.addWidget(y_group)

        # ── Z matrix section ────────────────────────────────────────────
        matrix_group = QtWidgets.QGroupBox("Z matrix  (row = Y, column = X)")
        matrix_layout = QtWidgets.QVBoxLayout(matrix_group)

        self.matrix_table = QtWidgets.QTableWidget()
        self.matrix_table.horizontalHeader().setStretchLastSection(True)
        self.matrix_table.setSelectionBehavior(QtWidgets.QTableWidget.SelectionBehavior.SelectItems)
        matrix_layout.addWidget(self.matrix_table)

        main_layout.addWidget(matrix_group)

        # The chart dialog is constructed only when requested so table edits
        # never own a native paint object while this editor is hidden.
        self.plot_button: QtWidgets.QPushButton = QtWidgets.QPushButton(self.tr("Show plot"), self)
        self.plot_button.clicked.connect(self.show_plot)
        main_layout.addWidget(self.plot_button)

        # ── Dialog buttons ──────────────────────────────────────────────
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Release the retained native plot dialog before closing.

        :param event: Qt close event.
        :return: None.
        """
        self.close_plot_dialogue()
        QtWidgets.QDialog.closeEvent(self, event)

    def done(self, result: int) -> None:
        """
        Release the retained native plot dialog before accepting or rejecting.

        :param result: Qt dialog result code.
        :return: None.
        """
        self.close_plot_dialogue()
        QtWidgets.QDialog.done(self, result)

    def show_plot(self) -> None:
        """Show the current lookup rows in one retained native chart dialog.

        :return: None.
        """
        self.close_plot_dialogue()
        self._plot_dialogue = PlotDialogue(title=self.tr("Lookup surface plot"), parent=self)
        self._update_plot()
        self._plot_dialogue.show()

    def close_plot_dialogue(self) -> None:
        """Dispose the owned modeless chart before this editor is destroyed.

        :return: None.
        """
        if is_dialog_available(self._plot_dialogue):
            self._plot_dialogue.reject()
            delete_dialog_safely(dialog=self._plot_dialogue)
        else:
            pass
        self._plot_dialogue = None

    # ── X table helpers ─────────────────────────────────────────────────

    def _add_x(self):
        self.x_table.blockSignals(True)
        row = self.x_table.rowCount()
        self.x_table.insertRow(row)
        self.x_table.setItem(row, 0, QtWidgets.QTableWidgetItem("0.0"))
        self.x_table.blockSignals(False)
        self._rebuild_matrix()

    def _del_x(self):
        rows = sorted(set(i.row() for i in self.x_table.selectedIndexes()), reverse=True)
        self.x_table.blockSignals(True)
        for r in rows:
            self.x_table.removeRow(r)
        self.x_table.blockSignals(False)
        self._rebuild_matrix()

    def _up_x(self):
        rows = sorted(set(i.row() for i in self.x_table.selectedIndexes()))
        if not rows or rows[0] == 0:
            return
        self.x_table.blockSignals(True)
        for r in rows:
            self._swap_x_rows(r, r - 1)
        self.x_table.blockSignals(False)
        self._rebuild_matrix()

    def _down_x(self):
        rows = sorted(set(i.row() for i in self.x_table.selectedIndexes()), reverse=True)
        if not rows or rows[-1] == self.x_table.rowCount() - 1:
            return
        self.x_table.blockSignals(True)
        for r in rows:
            self._swap_x_rows(r, r + 1)
        self.x_table.blockSignals(False)
        self._rebuild_matrix()

    def _swap_x_rows(self, r1: int, r2: int):
        item1 = self.x_table.item(r1, 0)
        item2 = self.x_table.item(r2, 0)
        if item1 is None:
            item1 = QtWidgets.QTableWidgetItem("0.0")
            self.x_table.setItem(r1, 0, item1)
        if item2 is None:
            item2 = QtWidgets.QTableWidgetItem("0.0")
            self.x_table.setItem(r2, 0, item2)
        item1.setText(item2.text())

    # ── Y table helpers ─────────────────────────────────────────────────

    def _add_y(self):
        self.y_table.blockSignals(True)
        row = self.y_table.rowCount()
        self.y_table.insertRow(row)
        self.y_table.setItem(row, 0, QtWidgets.QTableWidgetItem("0.0"))
        self.y_table.blockSignals(False)
        self._rebuild_matrix()

    def _del_y(self):
        rows = sorted(set(i.row() for i in self.y_table.selectedIndexes()), reverse=True)
        self.y_table.blockSignals(True)
        for r in rows:
            self.y_table.removeRow(r)
        self.y_table.blockSignals(False)
        self._rebuild_matrix()

    def _up_y(self):
        rows = sorted(set(i.row() for i in self.y_table.selectedIndexes()))
        if not rows or rows[0] == 0:
            return
        self.y_table.blockSignals(True)
        for r in rows:
            self._swap_y_rows(r, r - 1)
        self.y_table.blockSignals(False)
        self._rebuild_matrix()

    def _down_y(self):
        rows = sorted(set(i.row() for i in self.y_table.selectedIndexes()), reverse=True)
        if not rows or rows[-1] == self.y_table.rowCount() - 1:
            return
        self.y_table.blockSignals(True)
        for r in rows:
            self._swap_y_rows(r, r + 1)
        self.y_table.blockSignals(False)
        self._rebuild_matrix()

    def _swap_y_rows(self, r1: int, r2: int):
        item1 = self.y_table.item(r1, 0)
        item2 = self.y_table.item(r2, 0)
        if item1 is None:
            item1 = QtWidgets.QTableWidgetItem("0.0")
            self.y_table.setItem(r1, 0, item1)
        if item2 is None:
            item2 = QtWidgets.QTableWidgetItem("0.0")
            self.y_table.setItem(r2, 0, item2)
        item1.setText(item2.text())

    # ── Signal handlers ─────────────────────────────────────────────────

    def _on_x_changed(self, item: QtWidgets.QTableWidgetItem):
        if item.column() == 0:
            self._rebuild_matrix()

    def _on_y_changed(self, item: QtWidgets.QTableWidgetItem):
        if item.column() == 0:
            self._rebuild_matrix()

    # ── Matrix rebuild ──────────────────────────────────────────────────

    def _read_x_values(self) -> list[float]:
        values: list[float] = []
        for row in range(self.x_table.rowCount()):
            item = self.x_table.item(row, 0)
            if item is not None:
                try:
                    values.append(float(item.text()))
                except ValueError:
                    values.append(0.0)
        return values

    def _read_y_values(self) -> list[float]:
        values: list[float] = []
        for row in range(self.y_table.rowCount()):
            item = self.y_table.item(row, 0)
            if item is not None:
                try:
                    values.append(float(item.text()))
                except ValueError:
                    values.append(0.0)
        return values

    def _rebuild_matrix(self):
        x_vals = self._read_x_values()
        y_vals = self._read_y_values()
        x_count = len(x_vals)
        y_count = len(y_vals)

        # preserve existing z values where possible
        old_z: dict[tuple[int, int], str] = {}
        for r in range(1, self.matrix_table.rowCount()):
            for c in range(1, self.matrix_table.columnCount()):
                item = self.matrix_table.item(r, c)
                if item is not None:
                    old_z[(r, c)] = item.text()

        self.matrix_table.blockSignals(True)
        self.matrix_table.setRowCount(y_count + 1)
        self.matrix_table.setColumnCount(x_count + 1)

        # header row (X values)
        self.matrix_table.setHorizontalHeaderItem(0, QtWidgets.QTableWidgetItem(""))
        for c, xval in enumerate(x_vals, start=1):
            self.matrix_table.setHorizontalHeaderItem(c, QtWidgets.QTableWidgetItem(str(xval)))

        # header column (Y values)
        self.matrix_table.setVerticalHeaderItem(0, QtWidgets.QTableWidgetItem(""))
        for r, yval in enumerate(y_vals, start=1):
            self.matrix_table.setVerticalHeaderItem(r, QtWidgets.QTableWidgetItem(str(yval)))

        # fill cells
        for r in range(y_count + 1):
            for c in range(x_count + 1):
                if r == 0 and c == 0:
                    item = QtWidgets.QTableWidgetItem("")
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.matrix_table.setItem(r, c, item)
                elif r == 0 or c == 0:
                    item = QtWidgets.QTableWidgetItem("")
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.matrix_table.setItem(r, c, item)
                else:
                    text = old_z.get((r, c), "0.0")
                    self.matrix_table.setItem(r, c, QtWidgets.QTableWidgetItem(text))

        self.matrix_table.blockSignals(False)
        self._update_plot()

    # ── Plot ────────────────────────────────────────────────────────────

    def _update_plot(self):
        x_vals = self._read_x_values()
        y_vals = self._read_y_values()
        z_matrix = self._read_z_matrix()
        if is_dialog_available(self._plot_dialogue) and len(x_vals) > 0 and len(y_vals) > 0 and len(z_matrix) > 0:
            try:
                z_values: np.ndarray = np.asarray(z_matrix, dtype=float)
                if z_values.shape == (len(y_vals), len(x_vals)):
                    series_names: list[str] = list()
                    series_values: list[np.ndarray] = list()
                    row_index: int
                    for row_index in range(len(y_vals)):
                        series_names.append(self.tr("Y = {value}").format(value=y_vals[row_index]))
                        series_values.append(z_values[row_index])
                    accepted: bool = self._plot_dialogue.set_line_series(
                        x_values=np.asarray(x_vals, dtype=float),
                        series_names=series_names,
                        series_values=series_values,
                        title=self.tr("Lookup surface plot"),
                        x_axis_title=self.tr("X"),
                        y_axis_title=self.tr("Z"),
                    )
                    if accepted:
                        pass
                    else:
                        self._plot_dialogue.chart.clear()
                else:
                    self._plot_dialogue.chart.clear()
            except (TypeError, ValueError):
                self._plot_dialogue.chart.clear()
        elif is_dialog_available(self._plot_dialogue):
            self._plot_dialogue.chart.clear()
        else:
            pass

    # ── Data accessors ──────────────────────────────────────────────────

    def _read_z_matrix(self) -> list[list[float]]:
        matrix: list[list[float]] = []
        for r in range(1, self.matrix_table.rowCount()):
            row: list[float] = []
            for c in range(1, self.matrix_table.columnCount()):
                item = self.matrix_table.item(r, c)
                if item is not None:
                    try:
                        row.append(float(item.text()))
                    except ValueError:
                        row.append(0.0)
                else:
                    row.append(0.0)
            matrix.append(row)
        return matrix

    def set_data(self, x_points, y_points, z_matrix):
        self.x_table.blockSignals(True)
        self.y_table.blockSignals(True)
        self.x_table.setRowCount(0)
        self.y_table.setRowCount(0)

        for x in x_points:
            row = self.x_table.rowCount()
            self.x_table.insertRow(row)
            self.x_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(float(x))))

        for y in y_points:
            row = self.y_table.rowCount()
            self.y_table.insertRow(row)
            self.y_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(float(y))))

        self.x_table.blockSignals(False)
        self.y_table.blockSignals(False)
        self._rebuild_matrix()

        # fill z values from the provided matrix
        if z_matrix is not None:
            for r_idx, row in enumerate(z_matrix):
                for c_idx, val in enumerate(row):
                    item = self.matrix_table.item(r_idx + 1, c_idx + 1)
                    if item is not None:
                        item.setText(str(float(val)))

    def get_data(self) -> tuple[list[float], list[float], list[list[float]]]:
        return self._read_x_values(), self._read_y_values(), self._read_z_matrix()

    def accept(self) -> None:
        x_vals = self._read_x_values()
        y_vals = self._read_y_values()

        if len(x_vals) < 2:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Invalid number of X points"),
                self.tr("At least two X breakpoints are required."),
            )
            return

        if len(y_vals) < 2:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Invalid number of Y points"),
                self.tr("At least two Y breakpoints are required."),
            )
            return

        # check X strictly increasing
        for i in range(1, len(x_vals)):
            if x_vals[i] <= x_vals[i - 1]:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("Invalid X breakpoints"),
                    self.tr("X values must be strictly increasing."),
                )
                return

        # check Y strictly increasing
        for i in range(1, len(y_vals)):
            if y_vals[i] <= y_vals[i - 1]:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("Invalid Y breakpoints"),
                    self.tr("Y values must be strictly increasing."),
                )
                return

        super().accept()


class SequenceDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, parent, sequence_type: type[WaveformSequenceType] | type[V_I_CurveSequenceType] | type[X_Y_SequenceType]):
        QtWidgets.QStyledItemDelegate.__init__(self, parent)
        self.sequence_type: type[WaveformSequenceType] | type[V_I_CurveSequenceType] | type[X_Y_SequenceType] = sequence_type

    def paint(self, painter, option, index):
        painter.save()

        btn_option = QtWidgets.QStyleOptionButton()
        btn_option.rect = option.rect

        val = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
        if val is not None and len(val) > 0:
            btn_option.text = f"Edit  ({len(val)} points)"
        else:
            btn_option.text = "Edit points"

        QtWidgets.QApplication.style().drawControl(
            QtWidgets.QStyle.CE_PushButton, btn_option, painter
        )

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            if not (index.flags() & QtCore.Qt.ItemFlag.ItemIsEditable):
                return False
            dialog = SequenceEditorDialog(self.parent(), self.sequence_type)
            current = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
            if current is not None:
                dialog.set_points(current)
            if exec_dialog_safely(dialog=dialog) == QtWidgets.QDialog.DialogCode.Accepted:
                model.setData(index, dialog.get_points())
            return True
        return False


class ZmatrixDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, parent):
        QtWidgets.QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        painter.save()

        btn_option = QtWidgets.QStyleOptionButton()
        btn_option.rect = option.rect

        val = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
        if val is not None:
            x_pts, y_pts, z_mat = val
            btn_option.text = f"Edit matrix  ({len(x_pts)}x{len(y_pts)})"
        else:
            btn_option.text = "Edit matrix"

        QtWidgets.QApplication.style().drawControl(
            QtWidgets.QStyle.CE_PushButton, btn_option, painter
        )

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            if not (index.flags() & QtCore.Qt.ItemFlag.ItemIsEditable):
                return False
            dialog = LookupMatrixEditorDialog(self.parent())
            current = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
            if current is not None:
                x_pts, y_pts, z_mat = current
                dialog.set_data(x_pts, y_pts, z_mat)
            if exec_dialog_safely(dialog=dialog) == QtWidgets.QDialog.DialogCode.Accepted:
                model.setData(index, dialog.get_data())
            return True
        return False


class WindingTypeDelegate(QtWidgets.QItemDelegate):
    commitData = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QTableView):
        QtWidgets.QItemDelegate.__init__(self, parent)

        self._items = [
            ("Grounded Star (Yg)", WindingType.GroundedStar),
            ("Neutral Star (Yn)", WindingType.NeutralStar),
            ("Floating Star (Y)", WindingType.FloatingStar),
            ("Delta", WindingType.Delta),
            ("Grounded ZigZag (Zg)", WindingType.GroundedZigZag),
            ("Neutral ZigZag (Zn)", WindingType.NeutralZigZag),
            ("Floating ZigZag (Z)", WindingType.FloatingZigZag),
        ]

    @QtCore.Slot()
    def currentIndexChanged(self) -> None:
        self.commitData.emit(self.sender())

    def createEditor(self, parent, option, index: QtCore.QModelIndex):
        combo = QtWidgets.QComboBox(parent)
        for label, _ in self._items:
            combo.addItem(label)
        combo.currentIndexChanged.connect(self.currentIndexChanged)
        return combo

    def setEditorData(self, editor: QtWidgets.QComboBox, index: QtCore.QModelIndex):
        editor.blockSignals(True)
        val = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
        labels = [label for label, _ in self._items]
        try:
            idx = labels.index(val)
            editor.setCurrentIndex(idx)
        except ValueError:
            pass
        editor.blockSignals(False)

    def setModelData(self,
                     editor: QtWidgets.QComboBox,
                     model: QtCore.QAbstractItemModel,
                     index: QtCore.QModelIndex):
        idx = editor.currentIndex()
        if 0 <= idx < len(self._items):
            model.setData(index, self._items[idx][1])
