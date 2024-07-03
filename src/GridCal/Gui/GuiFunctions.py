# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Union, Any, Tuple
from PySide6 import QtCore, QtWidgets, QtGui
from warnings import warn
from enum import EnumMeta
from collections import defaultdict

from GridCalEngine.Devices import Bus, ContingencyGroup
from GridCalEngine.Devices.Parents.editable_device import GCProp, EditableDevice
from GridCalEngine.enumerations import DeviceType, ResultTypes
from GridCalEngine.basic_structures import IntVec
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit, Base
from GridCalEngine.Devices.Branches.line_locations import LineLocations
from GridCalEngine.Devices.types import ALL_DEV_TYPES


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
    def currentIndexChanged(self):
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

        :param editor:
        :param index:
        """
        editor.blockSignals(True)
        val = index.model().data(index, role=QtCore.Qt.ItemDataRole.DisplayRole)
        try:
            idx = self.object_names.index(val)
            editor.setCurrentIndex(idx)
            editor.blockSignals(False)
        except ValueError:
            pass

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

    def __init__(self, parent):
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

    def createEditor(self, parent, option, index):
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

    def setModelData(self, editor: QtWidgets.QFrame, model: "ObjectsModel", index):
        """

        :param editor:
        :param model:
        :param index:
        :return:
        """
        table = editor.children()[1]
        # model.setData(index, val)
        print()


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


def get_list_model(lst: List[Union[str, ALL_DEV_TYPES]], checks=False, check_value=False) -> QtGui.QStandardItemModel:
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


class CustomFileSystemModel(QtWidgets.QFileSystemModel):
    """
    CustomFileSystemModel
    """

    def __init__(self, root_path: str, ext_filter: Union[None, List[str]] = None):
        super(CustomFileSystemModel, self).__init__()

        self.ext_filter = ext_filter if ext_filter is not None else ['*.py']

        self.setNameFilters(ext_filter)
        self.setRootPath(root_path)


def get_logger_tree_model(logger: DataLogger):
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


def get_icon_list_model(lst: List[Tuple[str, QtGui.QIcon]], checks=False,
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
            for val, icon in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setEditable(False)
                item.setIcon(icon)
                list_model.appendRow(item)
        else:
            for val, icon in lst:
                # for the list model
                item = QtGui.QStandardItem(str(val))
                item.setIcon(icon)
                item.setEditable(False)
                item.setCheckable(True)
                if check_value:
                    item.setCheckState(QtCore.Qt.CheckState.Checked)
                list_model.appendRow(item)

    return list_model


def get_checked_indices(mdl: QtGui.QStandardItemModel()) -> IntVec:
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


def get_checked_values(mdl: QtGui.QStandardItemModel()) -> List[str]:
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
                         icons: Dict[str, str] = None):
    """
    Fill TreeViewModel from dictionary
    :param parent: Parent QStandardItem
    :param d: item
    :param editable
    :param icons
    :return: Nothing
    """
    if isinstance(d, dict):
        for k, v in d.items():
            name = str(k)
            child = QtGui.QStandardItem(name)
            child.setEditable(editable)

            if icons is not None:
                if name in icons.keys():
                    icon_path = icons[name]
                    _icon = QtGui.QIcon()
                    _icon.addPixmap(QtGui.QPixmap(icon_path))
                    child.setIcon(_icon)

            parent.appendRow(child)
            fill_model_from_dict(parent=child, d=v, icons=icons)
    elif isinstance(d, list):
        for v in d:
            fill_model_from_dict(parent=parent, d=v, icons=icons)
    else:
        name = str(d)
        item = QtGui.QStandardItem(name)
        if icons is not None:
            if name in icons.keys():
                icon_path = icons[name]
                _icon = QtGui.QIcon()
                _icon.addPixmap(QtGui.QPixmap(icon_path))
                item.setIcon(_icon)
        item.setEditable(editable)
        parent.appendRow(item)


def get_tree_model(d, top='', icons: Dict[str, str] = None):
    """

    :param d:
    :param top:
    :param icons:
    :return:
    """
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels([top])
    fill_model_from_dict(model.invisibleRootItem(), d=d, editable=False, icons=icons)

    return model


def get_tree_item_path(item: QtGui.QStandardItem):
    """

    :param item:
    :return:
    """
    item_parent = item.parent()
    path = [item.text()]
    while item_parent is not None:
        parent_text = item_parent.text()
        path.append(parent_text)
        item_parent = item_parent.parent()
    path.reverse()
    return path


def add_cim_object_node(class_tag,
                        device: Base,
                        editable=False,
                        already_visited: Union[List, None] = None):
    """

    :param class_tag:
    :param device:
    :param editable:
    :param already_visited:
    :return:
    """
    if already_visited is None:
        already_visited = list()

    if class_tag is None:
        if hasattr(device, 'name'):
            if device.name is not None:
                if device.name != '':
                    class_tag = device.name
                else:
                    class_tag = device.rdfid
            else:
                class_tag = device.rdfid
        else:
            class_tag = device.rdfid

    # create root node
    device_child = QtGui.QStandardItem(class_tag)

    # register visit to avoid cyclic recursion
    already_visited.append(device)

    for property_name, cim_prop in device.declared_properties.items():

        property_value = getattr(device, property_name)

        if hasattr(property_value, 'rdfid'):

            we_are_in_a_recursive_loop = False
            if len(already_visited) > 7:
                for e in already_visited:
                    if property_value.rdfid == e.rdfid:
                        we_are_in_a_recursive_loop = True

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
            device_child = add_cim_object_node(class_tag=None, device=device, editable=editable, already_visited=list())

            device_child.setEditable(editable)

            class_child.appendRow(device_child)

        class_child.setEditable(editable)
        root_node.appendRow(class_child)

    return model


def add_menu_entry(menu: QtWidgets.QMenu,
                   text: str,
                   icon_path: str = "",
                   function_ptr=None,
                   checkeable=False,
                   checked_value=False) -> QtGui.QAction:
    """
    Add a context menu entry
    :param menu:
    :param text:
    :param icon_path:
    :param function_ptr:
    :param checkeable:
    :param checked_value:
    :return:
    """

    entry = menu.addAction(text)

    if checkeable:
        entry.setCheckable(checkeable)
        entry.setChecked(checked_value)

    if len(icon_path) > 0:
        edit_icon = QtGui.QIcon()
        edit_icon.addPixmap(QtGui.QPixmap(icon_path))
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
