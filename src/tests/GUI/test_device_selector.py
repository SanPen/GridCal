"""Regression tests for searchable foreign-key device selectors."""

from typing import Dict, List

from PySide6 import QtCore, QtWidgets

import VeraGridEngine.Devices as dev
from VeraGrid.Gui.general_dialogues import DeviceSelectorPanel
from VeraGrid.Gui.object_model import DeviceSelectorDelegate, ObjectsModel, RemedialActionPropertyDelegate
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.enumerations import DeviceType, RemedialActionPropertyEnum


def get_visible_child_names(panel: DeviceSelectorPanel) -> List[str]:
    """
    Return visible device-leaf names from a selector panel.

    :param panel: Populated selector panel.
    :return: Visible child names across all device-type groups.
    """
    names: List[str] = list()
    parent_row: int
    for parent_row in range(panel.proxy_model.rowCount()):
        parent_index: QtCore.QModelIndex = panel.proxy_model.index(parent_row, 0)
        child_row: int
        for child_row in range(panel.proxy_model.rowCount(parent_index)):
            child_index: QtCore.QModelIndex = panel.proxy_model.index(child_row, 0, parent_index)
            names.append(str(panel.proxy_model.data(child_index)))
    return names


def get_combo_values(editor: QtWidgets.QComboBox) -> List[RemedialActionPropertyEnum]:
    """
    Return all remedial-action properties stored by a combo box.

    :param editor: Property editor.
    :return: Enum values in display order.
    """
    values: List[RemedialActionPropertyEnum] = list()
    item_index: int
    for item_index in range(editor.count()):
        item_value: object = editor.itemData(item_index)
        if isinstance(item_value, RemedialActionPropertyEnum):
            values.append(item_value)
        else:
            pass
    return values


def test_device_selector_search_matches_accented_names(
        qt_app: QtWidgets.QApplication) -> None:
    """
    Check composed accents and accent-insensitive selector searches.

    :param qt_app: Shared Qt application.
    :return: None.
    """
    application: QtWidgets.QApplication = qt_app
    devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]] = {
        DeviceType.BusDevice: [dev.Bus(name='Ávila'), dev.Bus(name='Peñíscola')],
    }
    panel: DeviceSelectorPanel = DeviceSelectorPanel(devices_by_type=devices_by_type)

    panel.search_box.setText('avila')
    application.processEvents()
    assert get_visible_child_names(panel=panel) == ['Ávila']

    panel.search_box.setText('PEÑISCOLA')
    application.processEvents()
    assert get_visible_child_names(panel=panel) == ['Peñíscola']

    panel.search_box.setText('´')
    application.processEvents()
    assert panel.search_box.text() == '´'


def test_generator_bus_selector_remains_type_specific(
        qt_app: QtWidgets.QApplication) -> None:
    """
    Check that the remedial-action selector does not change generator bus selection.

    :param qt_app: Shared Qt application.
    :return: None.
    """
    application: QtWidgets.QApplication = qt_app
    circuit: dev.MultiCircuit = dev.MultiCircuit()
    bus: dev.Bus = circuit.add_bus(dev.Bus(name='Generator bus'))
    generator: dev.Generator = circuit.add_generator(
        bus=None,
        api_obj=dev.Generator(name='Generator'),
    )
    generator_template: ALL_DEV_TYPES
    dictionary_of_lists: Dict[DeviceType, List[ALL_DEV_TYPES]]
    generator_template, dictionary_of_lists = circuit.get_dictionary_of_lists(DeviceType.GeneratorDevice)
    del generator_template
    table_view: QtWidgets.QTableView = QtWidgets.QTableView()
    model: ObjectsModel = ObjectsModel(
        objects=[generator],
        property_list=generator.property_list,
        time_index=None,
        parent=table_view,
        editable=True,
        dictionary_of_lists=dictionary_of_lists,
    )
    table_view.setModel(model)
    bus_column: int = model.attributes.index('bus')
    empty: bool
    selector_lists: Dict[DeviceType, List[ALL_DEV_TYPES]]
    empty, selector_lists = model._get_delegate_objects_dict(bus_column)

    assert not empty
    assert selector_lists == {DeviceType.BusDevice: [bus]}
    assert isinstance(table_view.itemDelegateForColumn(bus_column), DeviceSelectorDelegate)
    assert model.setData(model.index(0, bus_column), bus)
    assert generator.bus is bus
    application.processEvents()


def test_remedial_action_group_selector_filters_devices_and_properties(
        qt_app: QtWidgets.QApplication) -> None:
    """
    Check that monitored devices and limits are both restricted to supported values.

    :param qt_app: Shared Qt application.
    :return: None.
    """
    application: QtWidgets.QApplication = qt_app
    circuit: dev.MultiCircuit = dev.MultiCircuit()
    bus_from: dev.Bus = circuit.add_bus(dev.Bus(name='From', Vnom=110.0))
    bus_to: dev.Bus = circuit.add_bus(dev.Bus(name='To', Vnom=110.0))
    line: dev.Line = circuit.add_line(dev.Line(bus_from=bus_from, bus_to=bus_to, name='Line'))
    transformer: dev.Transformer2W = circuit.add_transformer2w(
        dev.Transformer2W(bus_from=bus_from, bus_to=bus_to, name='Transformer'),
    )
    group: dev.RemedialActionGroup = dev.RemedialActionGroup()
    circuit.add_remedial_action_group(group)
    group_template: ALL_DEV_TYPES
    dictionary_of_lists: Dict[DeviceType, List[ALL_DEV_TYPES]]
    group_template, dictionary_of_lists = circuit.get_dictionary_of_lists(
        DeviceType.RemedialActionGroupDevice,
    )
    del group_template
    table_view: QtWidgets.QTableView = QtWidgets.QTableView()
    model: ObjectsModel = ObjectsModel(
        objects=[group],
        property_list=group.property_list,
        time_index=None,
        parent=table_view,
        editable=True,
        dictionary_of_lists=dictionary_of_lists,
    )
    table_view.setModel(model)
    device_column: int = model.attributes.index('monitored_device')
    empty: bool
    selector_lists: Dict[DeviceType, List[ALL_DEV_TYPES]]
    empty, selector_lists = model._get_delegate_objects_dict(device_column)

    assert not empty
    assert selector_lists == {
        DeviceType.BusDevice: [bus_from, bus_to],
        DeviceType.LineDevice: [line],
        DeviceType.Transformer2WDevice: [transformer],
    }
    assert isinstance(table_view.itemDelegateForColumn(device_column), DeviceSelectorDelegate)

    property_column: int = model.attributes.index('property_type')
    property_delegate: QtWidgets.QAbstractItemDelegate = table_view.itemDelegateForColumn(property_column)
    assert isinstance(property_delegate, RemedialActionPropertyDelegate)
    property_index: QtCore.QModelIndex = model.index(0, property_column)

    assert model.setData(model.index(0, device_column), line)
    line_editor: QtWidgets.QComboBox = property_delegate.createEditor(
        table_view,
        QtWidgets.QStyleOptionViewItem(),
        property_index,
    )
    assert get_combo_values(editor=line_editor) == [
        RemedialActionPropertyEnum.Loading,
        RemedialActionPropertyEnum.ContingencyLoading,
    ]
    property_delegate.setModelData(line_editor, model, property_index)
    assert group.property_type == RemedialActionPropertyEnum.Loading

    assert model.setData(model.index(0, device_column), bus_from)
    assert group.property_type is None
    bus_editor: QtWidgets.QComboBox = property_delegate.createEditor(
        table_view,
        QtWidgets.QStyleOptionViewItem(),
        property_index,
    )
    assert get_combo_values(editor=bus_editor) == [
        RemedialActionPropertyEnum.Vmin,
        RemedialActionPropertyEnum.Vmax,
    ]
    application.processEvents()
