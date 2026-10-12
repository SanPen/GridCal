# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import datetime
import math

import numpy as np
from typing import Any, Dict, List, Union, Tuple
from PySide6 import QtCore, QtWidgets, QtGui
from typing import Callable
from enum import EnumMeta
from VeraGrid.Gui.gui_functions import (BoolCheckboxDelegate, IntDelegate, ComboDelegate, TextDelegate, FloatDelegate,
                                        ColorPickerDelegate,
                                        ComplexDelegate, LineLocationsDelegate, DateTimeDelegate)
from VeraGrid.Gui.Icons.icon_associations import device_type_icons
from VeraGrid.Gui.wrappable_table_model import WrappableTableModel
from VeraGridEngine.Devices import Bus, ContingencyGroup
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, GCProp, GCPROP_TYPES
from VeraGridEngine.Devices.Parents.pointer_device_parent import PointerDeviceParent
from VeraGridEngine.Devices.Branches.line_locations import LineLocations
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.enumerations import DeviceType, PrpCat, SubObjectType


class DeviceSelectorDelegate(QtWidgets.QItemDelegate):
    """
    Delegate that opens a searchable device selector for an empty device reference.
    """

    def __init__(self,
                 parent: QtWidgets.QTableView,
                 devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]],
                 allow_none: bool = True) -> None:
        """
        Constructor.

        :param parent: QTableView parent object.
        :param devices_by_type: Dictionary with device types and their devices.
        :param allow_none: Add a selectable None entry.
        """
        QtWidgets.QItemDelegate.__init__(self, parent)

        self.devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]] = devices_by_type
        self.allow_none: bool = allow_none

    @QtCore.Slot(object)
    def commit_selector_value(self, selected_device: object) -> None:
        """
        Commit the selector popup value to the table model.

        :param selected_device: Selected device or None.
        :return: None.
        """
        del selected_device
        editor: QtCore.QObject | None = self.sender()

        if isinstance(editor, QtWidgets.QWidget):
            self.commitData.emit(editor)
            self.closeEditor.emit(editor)
        else:
            pass

    @QtCore.Slot()
    def close_selector_value(self) -> None:
        """
        Close the selector popup without committing.

        :return: None.
        """
        editor: QtCore.QObject | None = self.sender()

        if isinstance(editor, QtWidgets.QWidget):
            self.closeEditor.emit(editor)
        else:
            pass

    def createEditor(self,
                     parent: QtWidgets.QWidget,
                     option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> QtWidgets.QWidget:
        """
        Create a searchable selector popup for one editable device reference.

        :param parent: Parent widget.
        :param option: Editor style option.
        :param index: Edited model index.
        :return: Searchable selector popup.
        """
        del option
        del index
        from VeraGrid.Gui.general_dialogues import DeviceSelectorPanel

        editor: DeviceSelectorPanel = DeviceSelectorPanel(
            devices_by_type=self.devices_by_type,
            allow_none=self.allow_none,
            parent=parent,
        )
        editor.setWindowFlags(QtCore.Qt.WindowType.Popup)
        editor.resize(500, 400)
        editor.selection_made.connect(self.commit_selector_value)
        editor.selection_cancelled.connect(self.close_selector_value)
        return editor

    def setModelData(self,
                     editor: QtWidgets.QWidget,
                     model: QtCore.QAbstractItemModel,
                     index: QtCore.QModelIndex) -> None:
        """
        Write the selected device from the selector popup to the model.

        :param editor: Selector popup editor.
        :param model: Edited model.
        :param index: Edited cell index.
        :return: None.
        """
        from VeraGrid.Gui.general_dialogues import DeviceSelectorPanel

        if isinstance(editor, DeviceSelectorPanel):
            if editor.has_selection:
                selected_device: ALL_DEV_TYPES | None = editor.get_selected_device()
                model.setData(index, selected_device)
            else:
                pass
        else:
            pass

    def updateEditorGeometry(self,
                             editor: QtWidgets.QWidget,
                             option: QtWidgets.QStyleOptionViewItem,
                             index: QtCore.QModelIndex) -> None:
        """
        Position the selector popup next to the edited cell.

        :param editor: Selector popup editor.
        :param option: Edited cell style option.
        :param index: Edited model index.
        :return: None.
        """
        del index
        from VeraGrid.Gui.general_dialogues import DeviceSelectorPanel

        view: QtWidgets.QWidget | None = option.widget
        size: QtCore.QSize = QtCore.QSize(500, 400)

        if view is None:
            editor.setGeometry(QtCore.QRect(option.rect.topLeft(), size))
        else:
            if isinstance(view, QtWidgets.QAbstractItemView):
                cell_bottom_left: QtCore.QPoint = view.viewport().mapToGlobal(option.rect.bottomLeft())
                cell_top_left: QtCore.QPoint = view.viewport().mapToGlobal(option.rect.topLeft())
            else:
                cell_bottom_left = view.mapToGlobal(option.rect.bottomLeft())
                cell_top_left = view.mapToGlobal(option.rect.topLeft())

            screen: QtGui.QScreen | None = QtGui.QGuiApplication.screenAt(cell_bottom_left)

            if screen is None:
                screen = QtGui.QGuiApplication.primaryScreen()
            else:
                pass

            if screen is not None:
                available_geometry: QtCore.QRect = screen.availableGeometry()
                width: int = min(size.width(), available_geometry.width())
                height: int = min(size.height(), available_geometry.height())
                top_left: QtCore.QPoint = QtCore.QPoint(cell_bottom_left)
                grip_at_top: bool = False

                if top_left.y() + height > available_geometry.bottom():
                    top_left.setY(cell_top_left.y() - height)
                    grip_at_top = True
                else:
                    pass

                if top_left.x() + width > available_geometry.right():
                    top_left.setX(available_geometry.right() - width)
                else:
                    pass

                if top_left.x() < available_geometry.left():
                    top_left.setX(available_geometry.left())
                else:
                    pass

                if top_left.y() < available_geometry.top():
                    top_left.setY(available_geometry.top())
                else:
                    pass

                editor.setGeometry(QtCore.QRect(top_left, QtCore.QSize(width, height)))
                if isinstance(editor, DeviceSelectorPanel):
                    editor.set_resize_grip_at_top(value=grip_at_top)
                else:
                    pass
            else:
                editor.setGeometry(QtCore.QRect(cell_bottom_left, size))


class ObjectsModel(WrappableTableModel):
    """
    Class to populate a Qt table view with the properties of objects
    """

    def __init__(self,
                 objects: List[ALL_DEV_TYPES],
                 property_list: List[GCProp],
                 time_index: Union[int, None],
                 parent: QtWidgets.QTableView = None,
                 editable=False,
                 transposed=False,
                 check_unique: Union[None, List[str]] = None,
                 dictionary_of_lists: Dict[DeviceType, List[ALL_DEV_TYPES]] | None = None,
                 properties_filter: PrpCat = PrpCat.All,
                 error_msg_ptr: Callable[[str], None] = None):
        """

        :param objects: list of objects associated to the editor
        :param property_list: List with the declared properties of an object
        :param parent: Parent object: the QTableView object
        :param editable: Is the table editable?
        :param transposed: Display the table transposed?
        :param dictionary_of_lists: dictionary of lists for the Delegates
        :param error_msg_ptr: Error message pointer
        """
        WrappableTableModel.__init__(self, parent)

        self.parent = parent

        self.time_index_: Union[int, None] = time_index

        self.editable = editable

        self.objects: List[ALL_DEV_TYPES] = objects

        self.property_list: List[GCProp] = list()
        self.attributes: List[str] = list()
        self.attribute_types: List[GCPROP_TYPES] = list()
        self.units: List[str] = list()
        self.tips: List[str] = list()
        self.non_editable_attributes: List[str] = list()

        for p in property_list:
            if p.display:
                if properties_filter == PrpCat.All:
                    self.property_list.append(p)
                    self.attributes.append(p.name)
                    self.attribute_types.append(p.tpe)
                    self.units.append(p.units)
                    self.tips.append(p.definition)

                    if not p.editable:
                        self.non_editable_attributes.append(p.name)
                else:
                    if properties_filter in p.category:
                        self.property_list.append(p)
                        self.attributes.append(p.name)
                        self.attribute_types.append(p.tpe)
                        self.units.append(p.units)
                        self.tips.append(p.definition)

                        if not p.editable:
                            self.non_editable_attributes.append(p.name)

        self.check_unique = check_unique if check_unique is not None else list()

        self.r = len(self.objects)

        self.c = len(self.attributes)

        self.formatter = lambda x: "%.2f" % x

        self.transposed = transposed

        self.dictionary_of_lists = dictionary_of_lists if dictionary_of_lists is not None else dict()

        self.error_msg_ptr: Callable[[str], None] | None = error_msg_ptr

        self.is_pointer_object = False
        if len(self.objects) > 0:
            if isinstance(self.objects[0], PointerDeviceParent):
                self.is_pointer_object = True

        self.set_delegates()

    def report_error(self, msg: str):
        """

        :param msg:
        :return:
        """
        if self.error_msg_ptr is not None:
            self.error_msg_ptr(msg)
        else:
            print(msg)

    def set_time_index(self, time_index: Union[int, None]):
        """
        Set the time index of the table
        :param time_index: None or integer value
        """
        self.time_index_ = time_index

        row_count: int = self.rowCount()
        col_count: int = self.columnCount()

        if row_count > 0 and col_count > 0:
            top_left: QtCore.QModelIndex = self.index(0, 0)
            bottom_right: QtCore.QModelIndex = self.index(row_count - 1, col_count - 1)
            self.dataChanged.emit(
                top_left,
                bottom_right,
                [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole],
            )
        else:
            pass

    def set_delegates(self) -> None:
        """
        Set the cell editor types depending on the attribute_types array
        """

        if self.transposed:
            F = self.parent.setItemDelegateForRow
        else:
            F = self.parent.setItemDelegateForColumn

        for i in range(self.c):

            if self.property_list[i].is_color:
                delegate = ColorPickerDelegate(self.parent)
                F(i, delegate)

            elif self.property_list[i].is_date:
                delegate = DateTimeDelegate(self.parent)
                F(i, delegate)

            else:
                tpe = self.attribute_types[i]

                if tpe is bool:
                    delegate = BoolCheckboxDelegate(self.parent)
                    F(i, delegate)

                elif tpe is str and not (self.is_pointer_object and self.attributes[i] == "device"):
                    delegate = TextDelegate(self.parent)
                    F(i, delegate)

                elif tpe is float:
                    delegate = FloatDelegate(self.parent)
                    F(i, delegate)

                elif tpe is int:
                    delegate = IntDelegate(self.parent)
                    F(i, delegate)

                elif tpe is complex:
                    delegate = ComplexDelegate(self.parent)
                    F(i, delegate)

                elif tpe is LineLocations:
                    delegate = LineLocationsDelegate(self.parent)
                    F(i, delegate)

                elif tpe is None:
                    F(i, None)
                    if len(self.non_editable_attributes) == 0:
                        self.non_editable_attributes.append(self.attributes[i])

                elif isinstance(tpe, EnumMeta):
                    objects = list(tpe)
                    values = [x.value for x in objects]
                    delegate = ComboDelegate(self.parent, objects, values)
                    F(i, delegate)

                elif tpe == SubObjectType.VarType:
                    # Symbolic event parameters are supplied by the owning dynamic model because
                    # they are not circuit devices and therefore cannot use DeviceSelectorDelegate.
                    parameter_objects: List[Any] | None = self._get_delegate_objects_single_type(i)
                    if parameter_objects is not None:
                        parameter_names: List[str] = [parameter.name for parameter in parameter_objects]
                        delegate = ComboDelegate(self.parent, parameter_objects, parameter_names)
                        F(i, delegate)
                    else:
                        F(i, None)

                else:

                    # Foreign key object references use the searchable device selector.
                    empty, objs = self._get_delegate_objects_dict(i)

                    if not empty:
                        # if isinstance(tpe, DeviceType):
                        #     device_type: DeviceType = tpe
                        # else:
                        #     if len(objs) > 0:
                        #         device_type: DeviceType = objs[0].device_type
                        #     else:
                        #         device_type: DeviceType = DeviceType.NoDevice

                        delegate = DeviceSelectorDelegate(
                            parent=self.parent,
                            devices_by_type=objs,
                        )
                        F(i, delegate)
                    else:
                        F(i, None)

    @staticmethod
    def _is_bus_property_type(tpe: GCPROP_TYPES) -> bool:
        """
        Check if a property type describes a bus reference.

        :param tpe: Property type.
        :return: True if the property type is a bus reference.
        """
        if tpe is Bus:
            return True
        else:
            if tpe == DeviceType.BusDevice:
                return True
            else:
                return False

    def _get_delegate_objects_single_type(self, attr_idx: int) -> List[ALL_DEV_TYPES] | None:
        """
        Return the object list used by one foreign-key delegate.

        The GUI first looks for a property-specific list and then falls back to the
        generic list keyed by the registered property type.

        :param attr_idx: Property index inside the visible table model.
        :return: empty, dictionary of lists of objects
        """

        prop_name = self.attributes[attr_idx]
        tpe = self.attribute_types[attr_idx]
        specific_key = (prop_name, tpe)

        if specific_key in self.dictionary_of_lists:
            return self.dictionary_of_lists[specific_key]
        else:
            if prop_name in self.dictionary_of_lists:
                return self.dictionary_of_lists[prop_name]
            else:
                if tpe in self.dictionary_of_lists:
                    return self.dictionary_of_lists[tpe]
                else:
                    if self._is_bus_property_type(tpe=tpe) and DeviceType.BusDevice in self.dictionary_of_lists:
                        return self.dictionary_of_lists[DeviceType.BusDevice]
                    else:
                        return None

    def _get_delegate_objects_dict(self, attr_idx: int) -> Tuple[bool, Dict[DeviceType, List[ALL_DEV_TYPES]]]:
        """
        Return the object list used by one foreign-key delegate.

        The GUI first looks for a property-specific list and then falls back to the
        generic list keyed by the registered property type.

        :param attr_idx: Property index inside the visible table model.
        :return: empty, dictionary of lists of objects
        """

        prop_name = self.attributes[attr_idx]
        tpe = self.attribute_types[attr_idx]
        specific_key = (prop_name, tpe)

        if self.is_pointer_object and prop_name == "device":
            tpes = self.objects[0].pointer_dev_tpes
            devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]] = dict()
            for device_type in tpes:
                if device_type == DeviceType.PhysicalDeviceType:
                    # PhysicalDeviceType is the broad-pointer sentinel, so expose
                    # only physical network lists and not unrelated dependencies.
                    physical_device_types: List[DeviceType] = [
                        DeviceType.BusDevice,
                        DeviceType.LineDevice,
                        DeviceType.DCLineDevice,
                        DeviceType.Transformer2WDevice,
                        DeviceType.Transformer3WDevice,
                        DeviceType.TransformerNwDevice,
                        DeviceType.WindingDevice,
                        DeviceType.HVDCLineDevice,
                        DeviceType.VscDevice,
                        DeviceType.UpfcDevice,
                        DeviceType.SeriesReactanceDevice,
                        DeviceType.SwitchDevice,
                    ]
                    physical_device_types.extend([
                        DeviceType.GeneratorDevice,
                        DeviceType.BatteryDevice,
                        DeviceType.LoadDevice,
                        DeviceType.ExternalGridDevice,
                        DeviceType.StaticGeneratorDevice,
                        DeviceType.ShuntDevice,
                        DeviceType.ControllableShuntDevice,
                        DeviceType.CurrentInjectionDevice,
                    ])

                    for available_type, devices in self.dictionary_of_lists.items():
                        if available_type in physical_device_types:
                            devices_by_type[available_type] = devices
                        else:
                            pass
                else:
                    devices: List[ALL_DEV_TYPES] | None = self.dictionary_of_lists.get(device_type, None)
                    if devices is not None:
                        devices_by_type[device_type] = devices
                    else:
                        pass

            return False, devices_by_type

        else:

            if specific_key in self.dictionary_of_lists:
                return False, {specific_key: self.dictionary_of_lists[specific_key]}
            else:
                if prop_name in self.dictionary_of_lists:
                    return False, {prop_name: self.dictionary_of_lists[prop_name]}
                else:
                    if tpe in self.dictionary_of_lists:
                        return False, {tpe: self.dictionary_of_lists[tpe]}
                    else:
                        if self._is_bus_property_type(tpe=tpe) and DeviceType.BusDevice in self.dictionary_of_lists:
                            return False, {DeviceType.BusDevice: self.dictionary_of_lists[DeviceType.BusDevice]}
                        else:
                            return True, dict()

    def update(self):
        """
        update table
        """
        self.r = len(self.objects)
        # row = self.rowCount()
        # self.beginInsertRows(QtCore.QModelIndex(), row, row)
        # # whatever code
        # self.endInsertRows()

        self.layoutAboutToBeChanged.emit()
        self.layoutChanged.emit()

    def _is_property_editable(self, obj_idx: int, prop: GCProp) -> bool:
        """Use instance rules when available, otherwise the property's metadata.

        Auxiliary table objects such as BusConnectionObject do not inherit
        EditableDevice and need not provide an instance editability hook.
        """
        is_property_editable = getattr(self.objects[obj_idx], "is_property_editable", None)
        if is_property_editable is None:
            return prop.editable
        return is_property_editable(prop)

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """
        Get the display mode
        :param index:
        :return:
        """
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags

        if self.transposed:
            attr_idx = index.row()
            obj_idx = index.column()
        else:
            attr_idx = index.column()
            obj_idx = index.row()

        value: Any = self.data_with_type(index=index)
        is_empty_bus_reference: bool = self._is_bus_property_type(
            tpe=self.attribute_types[attr_idx],
        ) and value is None

        instance_editable = self._is_property_editable(obj_idx, self.property_list[attr_idx])
        if self.editable and ((self.attributes[attr_idx] not in self.non_editable_attributes
                               and instance_editable) or is_empty_bus_reference):
            flags: QtCore.Qt.ItemFlag = (
                    QtCore.Qt.ItemFlag.ItemIsEditable
                    | QtCore.Qt.ItemFlag.ItemIsEnabled
                    | QtCore.Qt.ItemFlag.ItemIsSelectable
            )

            if self.attribute_types[attr_idx] is bool:
                flags = flags | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            else:
                pass

            return flags
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def rowCount(self, parent: QtCore.QModelIndex = None) -> int:
        """
        Get number of rows
        :param parent:
        :return:
        """
        if self.transposed:
            return self.c
        else:
            return self.r

    def columnCount(self, parent: QtCore.QModelIndex = None) -> int:
        """
        Get number of columns
        :param parent:
        :return:
        """
        if self.transposed:
            return self.r
        else:
            return self.c

    def data_raw(self, r, c):
        """
        Get the data to display
        :param r: row index
        :param c: column index
        :return:
        """
        if self.transposed:
            obj_idx = c
            attr_idx = r
        else:
            obj_idx = r
            attr_idx = c

        prop = self.property_list[attr_idx]
        value: Any = self.objects[obj_idx].get_value(prop=prop, t_idx=self.time_index_)

        if self._is_bus_property_type(tpe=prop.tpe):
            if value is None:
                return ""
            else:
                return value.name
        else:
            return value

    def data_with_type(self, index: QtCore.QModelIndex):
        """
        Get the data to display
        :param index:
        :return:
        """
        if self.transposed:
            obj_idx = index.column()
            attr_idx = index.row()
        else:
            obj_idx = index.row()
            attr_idx = index.column()

        if obj_idx < len(self.objects):
            prop = self.property_list[attr_idx]
            value: Any = self.objects[obj_idx].get_value(prop=prop, t_idx=self.time_index_)

            if self._is_bus_property_type(tpe=prop.tpe):
                if value is None:
                    return None
                else:
                    return value.name
            else:
                return value
        else:
            # there is a mismatch because the element was deleted without refreshing this table model
            return ""

    def get_value_at_index(self, index: QtCore.QModelIndex) -> Any | None:
        """
        Return the raw property value behind a model index.

        :param index: Source model index.
        :return: Raw property value or ``None`` when the index is invalid.
        """
        if index.isValid():
            # Translate the visual table coordinates to the object/property coordinates.
            if self.transposed:
                obj_idx: int = index.column()
                attr_idx: int = index.row()
            else:
                obj_idx = index.row()
                attr_idx = index.column()

            # Read only valid object/property pairs because stale GUI indexes can survive table refreshes.
            if 0 <= obj_idx < len(self.objects) and 0 <= attr_idx < len(self.property_list):
                prop: GCProp = self.property_list[attr_idx]
                value: Any = self.objects[obj_idx].get_value(prop=prop, t_idx=self.time_index_)
                return value
            else:
                return None
        else:
            return None

    def get_hosted_device_at_index(self, index: QtCore.QModelIndex) -> EditableDevice | None:
        """
        Return the device referenced by a table cell.

        :param index: Source model index.
        :return: Hosted editable device or ``None`` when the cell stores a scalar value.
        """
        value: Any | None = self.get_value_at_index(index=index)

        # Device-reference cells store the API object directly even if display data shows only its name.
        if isinstance(value, EditableDevice):
            return value
        else:
            return None

    @staticmethod
    def _format_date_display(value) -> str:
        """
        Format epoch seconds for display without crashing on malformed values.
        """
        if value in ("", None):
            return ""

        if isinstance(value, datetime.datetime):
            return value.strftime("%Y/%m/%d")

        if isinstance(value, (np.integer, int)):
            epoch_seconds = int(value)
        elif isinstance(value, (np.floating, float)):
            numeric_value = float(value)
            if not math.isfinite(numeric_value) or not numeric_value.is_integer():
                return str(value)
            epoch_seconds = int(numeric_value)
        else:
            try:
                epoch_seconds = int(value)
            except (TypeError, ValueError, OverflowError):
                return str(value)

        dt = QtCore.QDateTime.fromSecsSinceEpoch(epoch_seconds)

        if not dt.isValid():
            return str(value)

        return dt.toString("yyyy/MM/dd")

    def data(self, index: QtCore.QModelIndex, role=None):
        """
        Get the data to display
        :param index:
        :param role:
        :return:
        """
        if len(self.objects) == 0:
            return None

        if index.isValid():
            if self.transposed:
                attr_idx = index.row()
            else:
                attr_idx = index.column()

            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                value: Any = self.data_with_type(index)

                if self.attribute_types[attr_idx] is bool:
                    return ""
                elif self.property_list[attr_idx].is_date:
                    return self._format_date_display(value)
                else:
                    if value is None:
                        return ""
                    else:
                        return str(value)

            elif role == QtCore.Qt.ItemDataRole.EditRole:
                return self.data_with_type(index)

            elif role == QtCore.Qt.ItemDataRole.CheckStateRole:
                if self.attribute_types[attr_idx] is bool:
                    if bool(self.data_with_type(index)):
                        return QtCore.Qt.CheckState.Checked
                    else:
                        return QtCore.Qt.CheckState.Unchecked
                else:
                    pass

            elif role == QtCore.Qt.ItemDataRole.BackgroundRole:

                if self.property_list[attr_idx].is_color:
                    return QtGui.QColor(str(self.data_with_type(index)))
                else:
                    pass

            elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
                obj_idx = index.column() if self.transposed else index.row()
                prop = self.property_list[attr_idx]
                if prop.editable and not self._is_property_editable(obj_idx, prop):
                    return QtGui.QColor('gray')

            elif role == QtCore.Qt.ItemDataRole.DecorationRole:

                delegate_objects: List[ALL_DEV_TYPES] | None = self._get_delegate_objects_single_type(attr_idx)
                has_selector_data: bool = delegate_objects is not None
                is_editable_cell: bool = bool(self.flags(index) & QtCore.Qt.ItemFlag.ItemIsEditable)

                if has_selector_data and is_editable_cell:
                    tpe: GCPROP_TYPES = self.attribute_types[attr_idx]

                    if tpe == SubObjectType.VarType:
                        # Symbolic variables use an inline combo box, so a reference icon is redundant.
                        return None
                    elif isinstance(tpe, DeviceType):
                        device_type: DeviceType = tpe
                    else:
                        if delegate_objects is not None and len(delegate_objects) > 0:
                            device_type: DeviceType = delegate_objects[0].device_type
                        else:
                            device_type: DeviceType = DeviceType.NoDevice

                    icon_path: str | None = device_type_icons.get(device_type.value, None)

                    if icon_path is not None:
                        return QtGui.QIcon(icon_path)
                    else:
                        return QtGui.QIcon(":/Icons/icons/link-to-selection.png")
                else:
                    pass

        return None

    def setData(self, index: QtCore.QModelIndex, value: Union[float, str], role: Union[int, None] = None) -> bool:
        """
        Set data by simple editor (whatever text)
        :param index:
        :param value:
        :param role:
        :return:
        """
        if len(self.objects) == 0:
            return True

        if not index.isValid():
            return False

        if self.transposed:
            obj_idx = index.column()
            attr_idx = index.row()
        else:
            obj_idx = index.row()
            attr_idx = index.column()

        prop = self.property_list[attr_idx]

        if role == QtCore.Qt.ItemDataRole.CheckStateRole and prop.tpe is bool:
            value = value == QtCore.Qt.CheckState.Checked or value == int(QtCore.Qt.CheckState.Checked.value)
        else:
            pass

        # check taken values
        if self.attributes[attr_idx] in self.check_unique:
            taken = self.attr_taken(self.attributes[attr_idx], value)
        else:
            taken = False

        if not taken:
            if obj_idx < len(self.objects):
                current_value: Any = self.objects[obj_idx].get_value(prop=prop, t_idx=self.time_index_)
                is_empty_bus_reference: bool = self._is_bus_property_type(tpe=prop.tpe) and current_value is None

                if not self._is_property_editable(obj_idx, prop) and not is_empty_bus_reference:
                    return False

                if self.attributes[attr_idx] not in self.non_editable_attributes or is_empty_bus_reference:

                    try:
                        if isinstance(value, str) and value != "":
                            value2 = prop.tpe(value)
                        else:
                            value2 = value
                        self.objects[obj_idx].set_value(prop=prop, t_idx=self.time_index_, value=value2)
                        first = self.index(0, obj_idx) if self.transposed else self.index(obj_idx, 0)
                        last = (self.index(self.rowCount() - 1, obj_idx) if self.transposed
                                else self.index(obj_idx, self.columnCount() - 1))
                        self.dataChanged.emit(
                            first,
                            last,
                            [
                                QtCore.Qt.ItemDataRole.DisplayRole,
                                QtCore.Qt.ItemDataRole.EditRole,
                                QtCore.Qt.ItemDataRole.CheckStateRole,
                                QtCore.Qt.ItemDataRole.ForegroundRole,
                            ],
                        )
                    except (TypeError, ValueError) as e:
                        self.report_error(str(e))
                        return False
                else:
                    pass  # the column cannot be edited
            else:
                # the object was deleted without refreshing this table
                pass

        return True

    def attr_taken(self, attr, val):
        """
        Checks if the attribute value is taken
        :param attr:
        :param val:
        :return:
        """
        for obj in self.objects:
            if val == getattr(obj, attr):
                return True
        return False

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role=QtCore.Qt.ItemDataRole.DisplayRole):
        """
        Get the headers to display
        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if len(self.objects) == 0:
            return None

        if self._hide_headers_mode is True:
            return None

        if role == QtCore.Qt.ItemDataRole.DisplayRole:

            if self.transposed:
                # for the properties in the schematic view
                if orientation == QtCore.Qt.Orientation.Horizontal:
                    return self.objects[0].device_type.value if len(self.objects) else 'Value'
                elif orientation == QtCore.Qt.Orientation.Vertical:
                    if self.units[section] != '':
                        return self.attributes[section] + ' [' + self.units[section] + ']'
                    else:
                        return self.attributes[section]
            else:
                # Normal
                if orientation == QtCore.Qt.Orientation.Horizontal:
                    if section < len(self.attributes):
                        if self.units[section] != '':
                            return self.attributes[section] + ' [' + self.units[section] + ']'
                        else:
                            return self.attributes[section]
                    else:
                        return "Deleted :/"

                elif orientation == QtCore.Qt.Orientation.Vertical:
                    if section < len(self.objects):
                        return str(section) + ':' + str(self.objects[section])
                    else:
                        return "Deleted :/"

        # add a tooltip
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            if section < self.c:
                if self.units[section] != "":
                    unit = '\nUnits: ' + self.units[section]
                else:
                    unit = ''
                return self.attributes[section] + unit + ' \n' + self.tips[section]
            else:
                # somehow the index is out of range
                return ""

        return None

    def copy_to_column(self, index: QtCore.QModelIndex) -> None:
        """
        Copy the value pointed by the index to all the other cells in the column
        :param index: QModelIndex instance
        """
        value = self.data_with_type(index=index)
        col = index.column()

        for row in range(self.rowCount()):

            if self.transposed:
                obj_idx = col
                attr_idx = row
            else:
                obj_idx = row
                attr_idx = col

            prop = self.property_list[attr_idx]
            if (self.attributes[attr_idx] not in self.non_editable_attributes
                    and self._is_property_editable(obj_idx, prop)):
                self.setData(self.index(row, col), value, QtCore.Qt.ItemDataRole.EditRole)
            else:
                pass  # the column cannot be edited

    def get_data(self):
        """

        :return:
        """
        nrows = self.rowCount()
        ncols = self.columnCount()
        data = np.empty((nrows, ncols), dtype=object)

        for j in range(ncols):
            for i in range(nrows):
                data[i, j] = self.data_raw(r=i, c=j)

        columns = [self.headerData(i, orientation=QtCore.Qt.Orientation.Horizontal,
                                   role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(ncols)]

        index = [self.headerData(i, orientation=QtCore.Qt.Orientation.Vertical,
                                 role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(nrows)]

        return index, columns, data

    def copy_to_clipboard(self):
        """

        :return:
        """
        if self.columnCount() > 0:

            index, columns, data = self.get_data()

            data = data.astype(str)

            # header first
            txt = '\t' + '\t'.join(columns) + '\n'

            # data
            for t, index_value in enumerate(index):
                txt += str(index_value) + '\t' + '\t'.join(data[t, :]) + '\n'

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText(txt)
