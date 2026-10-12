from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.Main.SubClasses.Model.data_base import DataBaseTableMain
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType
import pytest
import VeraGridEngine.api as vg
from VeraGrid.Gui.DeviceEditors.DcLineEditor.dc_line_editor import DcLineEditor


def _find_device_type_index(model: QtCore.QAbstractItemModel,
                            parent: QtCore.QModelIndex,
                            device_type: DeviceType) -> QtCore.QModelIndex:
    """
    Locate one device leaf in the database tree.

    :param model: Tree model to inspect.
    :param parent: Parent index whose children are searched.
    :param device_type: Stable enum payload to find.
    :return: Matching model index or an invalid index when absent.
    """
    row: int
    for row in range(model.rowCount(parent)):
        index: QtCore.QModelIndex = model.index(row, 0, parent)
        payload: object = index.data(QtCore.Qt.ItemDataRole.UserRole)
        if payload == device_type:
            return index
        else:
            child_index: QtCore.QModelIndex = _find_device_type_index(
                model=model,
                parent=index,
                device_type=device_type,
            )
            if child_index.isValid():
                return child_index
            else:
                pass
    return QtCore.QModelIndex()


def test_database_has_one_common_cable_system_catalogue(qt_app: object) -> None:
    """
    Exercise the real GUI add action for the DC cable catalogue.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    _application: object = qt_app
    gui: DataBaseTableMain = DataBaseTableMain()
    gui.hide()

    try:
        gui.circuit = MultiCircuit()
        gui.setup_objects_tree()
        tree_model: QtCore.QAbstractItemModel | None = gui.ui.dataStructuresTreeView.model()
        assert tree_model is not None
        cable_index: QtCore.QModelIndex = _find_device_type_index(
            model=tree_model,
            parent=QtCore.QModelIndex(),
            device_type=DeviceType.UnderGroundLineDevice,
        )
        assert cable_index.isValid()
        assert not _find_device_type_index(tree_model, QtCore.QModelIndex(), DeviceType.DcCableTypeDevice).isValid()

        selection_model: QtCore.QItemSelectionModel | None = gui.ui.dataStructuresTreeView.selectionModel()
        assert selection_model is not None
        selection_model.select(
            cable_index,
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QtCore.QItemSelectionModel.SelectionFlag.Rows,
        )
        gui.ui.dataStructuresTreeView.setCurrentIndex(cable_index)
        gui.view_objects_data()
        gui.add_objects()
        QtWidgets.QApplication.processEvents()

        table_model: QtCore.QAbstractItemModel | None = gui.ui.dataStructureTableView.model()
        assert len(gui.circuit.underground_cable_types) == 1
        assert gui.circuit.underground_cable_types[0].name == 'Cable System 1'
        assert table_model is not None
        assert table_model.rowCount() == 1
    finally:
        gui.close()
        gui.deleteLater()
        QtWidgets.QApplication.processEvents()


def test_dc_editor_preserves_length_units_and_applies_common_system(qt_app):
    grid = vg.MultiCircuit()
    buses = [vg.Bus(Vnom=320.0, is_dc=True) for _ in range(2)]
    for bus in buses:
        grid.add_bus(bus)
    system = vg.UndergroundLineType(R=0.02, X=0.3141592653589793, C=0.25, Vnom=320.0)
    grid.add_underground_line(system)
    model = vg.RmsModelTemplate(name='DC dynamics')
    model.tpe = DeviceType.DCLineDevice
    grid.add_rms_model(model)
    system.disable_auto_updates()
    system.rms_template = model
    system.enable_auto_updates()
    line = vg.DcLine(bus_from=buses[0], bus_to=buses[1], length=10.0, rate=250.0)
    grid.add_dc_line(line)
    line.apply_template(system, 100.0)
    editor = DcLineEditor(line, Sbase=100.0, templates=[system], current_template=system)
    try:
        assert editor.ui.lengthSpinBox.value() == 10.0
        assert editor.ui.resistanceSpinBox.value() == pytest.approx(0.02)
        assert not editor.ui.resistanceSpinBox.isEnabled()
        editor.ui.lengthSpinBox.setValue(20.0)
        editor.accept_click()
        assert line.length == 20.0
        assert line.template is system
        assert line.rms_template is model
        assert line.R == pytest.approx(0.4 / 1024.0)
        assert line.rate == pytest.approx(250.0)
        assert line.get_applied_dynamic_values_pu_seconds(100.0) == pytest.approx(
            (0.02 / 1024.0, 0.25e-6 * 20.0 * 1024.0))
        editor.use_template.setChecked(False)
        editor.ui.resistanceSpinBox.setValue(0.1)
        editor.accept_click()
        assert line.template is None
        assert line.R == pytest.approx(2.0 / 1024.0)
    finally:
        editor.close()
        editor.deleteLater()


def test_dc_editor_selects_physical_conductor(qt_app):
    from VeraGridEngine.enumerations import CableResistanceInput
    system = vg.UndergroundLineType(Vnom=15.0)
    for number in (1, 2):
        cable = vg.UndergroundCableType(resistance_input=CableResistanceInput.DcResistance,
                                       core_dc_resistance=0.2 * number, sheath_dc_resistance=0.8)
        system.add_cable_relationship(cable, xpos=0.25 * number, ypos=1.0, phase=number)
    buses = [vg.Bus(Vnom=15.0, is_dc=True) for _ in range(2)]
    line = vg.DcLine(bus_from=buses[0], bus_to=buses[1], length=2.0, rate=30.0)
    editor = DcLineEditor(line, templates=[system])
    try:
        editor.load_template_btn_click()
        editor.conductor_combo.setCurrentIndex(1)
        assert editor.ui.resistanceSpinBox.value() == pytest.approx(0.4)
        editor.accept_click()
        assert line.dc_conductor == 2
        assert line.R == pytest.approx(0.8 / 2.25)
        assert line.template is system
    finally:
        editor.close()
        editor.deleteLater()
