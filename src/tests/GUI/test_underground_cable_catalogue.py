from PySide6 import QtCore, QtWidgets
import pytest

from VeraGrid.Gui.DeviceEditors.UndergroundCableBuilder.table_models import UndergroundCableCatalogueModel
from VeraGrid.Gui.object_model import ObjectsModel
from VeraGridEngine.Devices.Branches.underground_cable_type import UndergroundCableType
from VeraGridEngine.Devices.Parents.editable_device import GCProp
from VeraGridEngine.enumerations import CableResistanceInput


def test_cable_layer_fields_editable_in_both_tables(qt_app: object) -> None:
    """Keep the builder and database table aligned with the scalar cable API.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    _application: object = qt_app
    cable: UndergroundCableType = UndergroundCableType(name='Manual')
    builder_model: UndergroundCableCatalogueModel = UndergroundCableCatalogueModel(cables=list((cable,)))
    property_names: tuple[str, ...] = tuple(prop.name for prop in builder_model.properties)

    # Each supported layer has its own numeric field, not a shared vector cell.
    field_name: str
    for field_name in ('nominal_voltage', 'core_diameter', 'core_internal_diameter',
                       'cable_diameter', 'sheath_thickness', 'main_insulation_thickness',
                       'core_resistivity', 'sheath_resistivity',
                       'core_filling_factor', 'sheath_filling_factor',
                       'core_relative_permeability', 'sheath_relative_permeability',
                       'main_insulation_permittivity', 'outer_insulation_permittivity',
                       'main_insulation_loss_tangent', 'outer_insulation_loss_tangent',
                       'skin_effect_factor'):
        prop: GCProp = cable.registered_properties[field_name]
        column: int = property_names.index(field_name)
        index: QtCore.QModelIndex = builder_model.index(0, column)
        assert prop.tpe is float
        assert builder_model.flags(index) & QtCore.Qt.ItemFlag.ItemIsEditable
        assert builder_model.data(index, QtCore.Qt.ItemDataRole.ToolTipRole) == prop.definition
        assert builder_model.headerData(column, QtCore.Qt.Orientation.Horizontal,
                                        QtCore.Qt.ItemDataRole.ToolTipRole) == prop.definition
        label: str = field_name.replace('_', ' ')
        expected_header: str = f'{label} ({prop.units})' if prop.units else label
        assert builder_model.headerData(column, QtCore.Qt.Orientation.Horizontal) == expected_header

    core_index: QtCore.QModelIndex = builder_model.index(0, property_names.index('core_resistivity'))
    original_sheath: float = cable.sheath_resistivity
    assert builder_model.setData(core_index, '2.0')
    assert cable.core_resistivity == 2.0
    assert cable.sheath_resistivity == original_sheath
    assert not builder_model.setData(core_index, 'invalid')
    assert cable.core_resistivity == 2.0

    # The generic database editor needs no special cable widget to edit scalars.
    view: QtWidgets.QTableView = QtWidgets.QTableView()
    database_model: ObjectsModel = ObjectsModel(
        objects=list((cable,)),
        property_list=list(cable.property_list),
        time_index=None,
        parent=view,
        editable=True,
    )
    sheath_index: QtCore.QModelIndex = database_model.index(0, database_model.attributes.index('sheath_resistivity'))
    assert database_model.flags(sheath_index) & QtCore.Qt.ItemFlag.ItemIsEditable
    assert database_model.setData(sheath_index, 2.8, QtCore.Qt.ItemDataRole.EditRole)
    assert cable.sheath_resistivity == 2.8
    assert cable.core_resistivity == 2.0

    # Derived resistance and the informational proximity factor are read-only.
    for field_name in ('core_dc_resistance', 'sheath_dc_resistance', 'proximity_effect_factor'):
        index = builder_model.index(0, property_names.index(field_name))
        assert not builder_model.flags(index) & QtCore.Qt.ItemFlag.ItemIsEditable
        assert not builder_model.setData(index, 123.0)
        database_index: QtCore.QModelIndex = database_model.index(0, database_model.attributes.index(field_name))
        assert not database_model.flags(database_index) & QtCore.Qt.ItemFlag.ItemIsEditable

    view.deleteLater()


@pytest.mark.parametrize('transposed', [False, True])
def test_resistance_selector_controls_both_tables(qt_app: object, transposed: bool) -> None:
    cable = UndergroundCableType()
    other = UndergroundCableType(name='Other cable')
    builder = UndergroundCableCatalogueModel(cables=[cable, other])
    names = [prop.name for prop in builder.properties]
    view = QtWidgets.QTableView()
    database = ObjectsModel(objects=[cable, other], property_list=list(cable.property_list),
                            time_index=None, parent=view, editable=True, transposed=transposed)

    def db_index(name: str, obj: int = 0) -> QtCore.QModelIndex:
        attr = database.attributes.index(name)
        return database.index(attr, obj) if transposed else database.index(obj, attr)

    def builder_index(name: str) -> QtCore.QModelIndex:
        return builder.index(0, names.index(name))

    original_r = cable.core_dc_resistance
    original_sheath_r = cable.sheath_dc_resistance
    assert builder.setData(builder_index('resistance_input'), CableResistanceInput.DcResistance)
    assert cable.core_dc_resistance == pytest.approx(original_r)
    assert cable.sheath_dc_resistance == pytest.approx(original_sheath_r)
    for name in ('core_resistivity', 'core_filling_factor', 'sheath_resistivity', 'sheath_filling_factor'):
        assert not builder.flags(builder_index(name)) & QtCore.Qt.ItemFlag.ItemIsEditable
        assert not database.flags(db_index(name)) & QtCore.Qt.ItemFlag.ItemIsEditable
        assert not builder.setData(builder_index(name), 12.0)
        assert not database.setData(db_index(name), 12.0, QtCore.Qt.ItemDataRole.EditRole)
        assert database.flags(db_index(name, 1)) & QtCore.Qt.ItemFlag.ItemIsEditable

    assert database.flags(db_index('core_dc_resistance')) & QtCore.Qt.ItemFlag.ItemIsEditable
    assert database.setData(db_index('core_dc_resistance'), 0.4, QtCore.Qt.ItemDataRole.EditRole)
    assert cable.core_dc_resistance == 0.4
    assert database.flags(db_index('sheath_dc_resistance')) & QtCore.Qt.ItemFlag.ItemIsEditable
    assert database.setData(db_index('sheath_dc_resistance'), 0.8, QtCore.Qt.ItemDataRole.EditRole)
    assert cable.sheath_dc_resistance == 0.8
    assert not builder.setData(builder_index('core_dc_resistance'), -0.1)
    assert not builder.setData(builder_index('core_dc_resistance'), float('nan'))
    assert not builder.setData(builder_index('sheath_dc_resistance'), -0.1)
    assert not builder.setData(builder_index('sheath_dc_resistance'), float('inf'))
    assert cable.core_dc_resistance == 0.4
    assert database.setData(db_index('resistance_input'), CableResistanceInput.Resistivity,
                            QtCore.Qt.ItemDataRole.EditRole)
    assert cable.core_dc_resistance == pytest.approx(0.4)
    assert cable.sheath_dc_resistance == pytest.approx(0.8)
    assert not database.flags(db_index('core_dc_resistance')) & QtCore.Qt.ItemFlag.ItemIsEditable
    assert not database.flags(db_index('sheath_dc_resistance')) & QtCore.Qt.ItemFlag.ItemIsEditable
    assert not builder.setData(builder_index('core_filling_factor'), 101.0)
    assert not builder.setData(builder_index('sheath_filling_factor'), 101.0)
    assert builder.setData(builder_index('core_diameter'), cable.core_diameter * 2.0)
    assert cable.core_dc_resistance == pytest.approx(0.1)
    assert cable.sheath_dc_resistance < 0.8
    view.deleteLater()


def test_builder_has_resistance_mode_dropdown(qt_app: object) -> None:
    from VeraGrid.Gui.DeviceEditors.UndergroundCableBuilder.underground_cable_builder import UndergroundCableBuilderGUI

    cable = UndergroundCableType()
    dialog = UndergroundCableBuilderGUI(cables_catalogue=[cable])
    model = dialog.catalogue_model
    column = next(i for i, prop in enumerate(model.properties) if prop.name == 'resistance_input')
    index = model.index(0, column)
    view = dialog.ui.wires_tableView
    delegate = view.itemDelegateForColumn(column)
    editor = delegate.createEditor(view, QtWidgets.QStyleOptionViewItem(), index)
    delegate.setEditorData(editor, index)
    assert editor.count() == 2
    assert [p.name for p in model.properties if p.tpe is CableResistanceInput] == ['resistance_input']
    assert editor.currentText() == CableResistanceInput.Resistivity.value
    editor.setCurrentIndex(1)
    delegate.setModelData(editor, model, index)
    assert cable.resistance_input == CableResistanceInput.DcResistance
    editor.deleteLater()
    dialog.deleteLater()


@pytest.mark.parametrize('layer', ['core', 'sheath'])
def test_copy_resistance_column_respects_each_cables_input_mode(qt_app: object, layer: str) -> None:
    source = UndergroundCableType(resistance_input=CableResistanceInput.DcResistance,
                                  core_dc_resistance=0.4, sheath_dc_resistance=0.4)
    material = UndergroundCableType()
    direct = UndergroundCableType(resistance_input=CableResistanceInput.DcResistance,
                                  core_dc_resistance=0.6, sheath_dc_resistance=0.6)
    name = f'{layer}_dc_resistance'
    material_r = getattr(material, name)
    view = QtWidgets.QTableView()
    model = ObjectsModel(objects=[source, material, direct], property_list=list(source.property_list),
                         time_index=None, parent=view, editable=True)
    model.copy_to_column(model.index(0, model.attributes.index(name)))
    assert getattr(direct, name) == 0.4
    assert getattr(material, name) == material_r
    view.deleteLater()
