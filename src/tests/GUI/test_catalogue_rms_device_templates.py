"""Contracts for catalogue actions derived from the dynamic Library."""

from __future__ import annotations

import copy
from pathlib import Path

from PySide6 import QtWidgets

import VeraGridEngine.api as vg
from VeraGrid.Gui.CatalogueElementsDialogue.catalogue_actions import CatalogueAction
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_utilities import (
    create_default_template_builder,
    initialize_template_builder_from_block,
)
from VeraGrid.Gui.CatalogueElementsDialogue.catalogue_elements_dialogue import (
    CatalogueElementsSelectionDialogue,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    LibraryDeviceTemplateSpec,
    get_dynamic_library_device_specs,
)
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Templates.Rms.hvdc_vsc_gfl_rms_template_v2 import HvdcVscGflRmsTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import BlockType, ConverterControlType, DeviceType, DynamicSimulationMode


def test_rms_catalogue_matches_library_devices(qt_app: QtWidgets.QApplication) -> None:
    """Require a one-to-one mapping between RMS Devices and catalogue actions.

    :param qt_app: Shared Qt application required to construct the dialog.
    :return: None.
    """
    application: QtWidgets.QApplication = qt_app
    circuit: MultiCircuit = MultiCircuit()
    dialog: CatalogueElementsSelectionDialogue = CatalogueElementsSelectionDialogue(
        parent=None,
        circuit=circuit,
    )
    actions: list[CatalogueAction] = dialog.build_rms_actions()
    specs: list[LibraryDeviceTemplateSpec] = get_dynamic_library_device_specs(
        mode=DynamicSimulationMode.RMS,
    )

    assert list(action.unique_key for action in actions) == list(
        spec.unique_key for spec in specs
    )
    assert list(action.name for action in actions) == list(spec.label for spec in specs)
    assert all(action.voltage_text == "" for action in actions)
    assert list(action.description_text for action in actions) == list(
        spec.description for spec in specs
    )
    assert len(set(action.unique_key for action in actions)) == len(actions)
    assert any(spec.unique_key.startswith("rms:international:") for spec in specs)
    assert all("governor" not in action.unique_key.lower() for action in actions)
    assert all("exciter" not in action.unique_key.lower() for action in actions)
    assert all("stabilizer" not in action.unique_key.lower() for action in actions)

    line_action: CatalogueAction | None = None
    action: CatalogueAction
    for action in actions:
        if action.unique_key == "rms:get_line_rms_template":
            line_action = action
        else:
            pass
    assert line_action is not None
    line_action.execute(circuit=circuit)
    assert circuit.rms_models[-1].code == line_action.unique_key

    dialog.close()
    application.processEvents()


def test_catalogue_hvdc_controls_survive_save_reload_and_insertion(
        qt_app: QtWidgets.QApplication,
        tmp_path: Path,
) -> None:
    """Keep selected HVDC control modes visible through file and editor copies."""
    circuit = MultiCircuit()
    spec = next(
        item for item in get_dynamic_library_device_specs(DynamicSimulationMode.RMS)
        if item.source == BlockType.GFL_VSC_HVDC_RMS
    )
    builder = HvdcVscGflRmsTemplate(circuit.var_factory)
    builder.params_dict["control1"].value = ConverterControlType.Pdc
    builder.params_dict["control2"].value = ConverterControlType.Vm_ac
    builder.params_dict["cdc"].value = 0.73
    template = builder.eval()
    template.code = spec.unique_key
    circuit.add_rms_model(template)
    expected_config = {"control1": "Pdc", "control2": "Vm_ac", "cdc": 0.73}

    copied_block = copy.deepcopy(template.block)
    assert copied_block.modal_template_config == expected_config
    assert copied_block.modal_template_config is not template.block.modal_template_config
    assert Block.parse(template.block.to_dict()).modal_template_config == expected_config
    legacy_data = template.block.to_dict()
    legacy_data.pop("modal_template_kind")
    legacy_data.pop("modal_template_config")
    legacy_block = Block.parse(legacy_data)
    legacy_builder = create_default_template_builder(
        circuit.var_factory,
        BlockType.GFL_VSC_HVDC_RMS,
        legacy_block.name,
    )
    assert legacy_builder is not None
    initialize_template_builder_from_block(
        legacy_builder,
        legacy_block,
        BlockType.GFL_VSC_HVDC_RMS,
    )
    assert legacy_builder.get_value("control1") is ConverterControlType.Pdc
    assert legacy_builder.get_value("control2") is ConverterControlType.Vm_ac

    path = tmp_path / "catalogue_hvdc.veragrid"
    vg.save_file(circuit, str(path))
    reopened = vg.open_file(str(path))
    saved_template = reopened.rms_models[0]
    assert saved_template.code == spec.unique_key
    assert saved_template.block.modal_template_kind == template.block.modal_template_kind
    assert saved_template.block.modal_template_config == expected_config
    assert template.block.compare(saved_template.block)

    class VscStub:
        name = "VSC"
        device_type = DeviceType.VscDevice
        rms_template = None
        emt_template = None

    editor = DynamicBlockEditorGUI(
        var_factory=reopened.var_factory,
        current_block=Block(),
        api_object=VscStub(),
        current_theme="Light",
        mode=DynamicSimulationMode.RMS,
        templates_list=[],
        circuit=reopened,
        is_root_editor=False,
        modal=False,
    )
    item = editor.create_materialized_template_block_item(
        template=saved_template,
        source_var_factory=reopened.var_factory,
        x_pos=100,
        y_pos=100,
    )
    # Keep assertion failures from opening an unsaved-changes prompt at teardown.
    editor.has_unapplied_changes = False
    assert item is not None
    block = item.subsys
    assert block.modal_template_config == expected_config
    assert editor.diagram.node_data[block.uid].tpe == BlockType.GFL_VSC_HVDC_RMS.name

    editor.request_open_block_properties(block)
    dialogue = editor._block_properties_dialogue
    assert dialogue is not None
    settings = {
        dialogue._general_structural_model.index(row, 0).data():
        dialogue._general_structural_model.index(row, 1).data()
        for row in range(dialogue._general_structural_model.rowCount())
    }
    assert settings["control1"] == "Pdc"
    assert settings["control2"] == "Vm_ac"
    dialogue.close()
    editor.has_unapplied_changes = False
    editor.close()
    qt_app.processEvents()


def test_emt_catalogue_matches_library_devices(qt_app: QtWidgets.QApplication) -> None:
    """Require a one-to-one mapping between EMT Devices and catalogue actions.

    :param qt_app: Shared Qt application required to construct the dialog.
    :return: None.
    """
    application: QtWidgets.QApplication = qt_app
    circuit: MultiCircuit = MultiCircuit()
    dialog: CatalogueElementsSelectionDialogue = CatalogueElementsSelectionDialogue(
        parent=None,
        circuit=circuit,
    )
    actions: list[CatalogueAction] = dialog.build_emt_actions()
    specs: list[LibraryDeviceTemplateSpec] = get_dynamic_library_device_specs(
        mode=DynamicSimulationMode.EMT,
    )

    assert list(action.unique_key for action in actions) == list(
        spec.unique_key for spec in specs
    )
    assert list(action.name for action in actions) == list(spec.label for spec in specs)
    assert all(action.voltage_text == "" for action in actions)
    assert list(action.description_text for action in actions) == list(
        spec.description for spec in specs
    )
    assert len(set(action.unique_key for action in actions)) == len(actions)
    assert all("governor" not in action.unique_key.lower() for action in actions)
    assert all("exciter" not in action.unique_key.lower() for action in actions)
    assert all("stabilizer" not in action.unique_key.lower() for action in actions)

    load_action: CatalogueAction | None = None
    action: CatalogueAction
    for action in actions:
        if action.unique_key == "emt:get_dc_load_emt_template":
            load_action = action
        else:
            pass
    assert load_action is not None
    load_action.execute(circuit=circuit)
    assert circuit.emt_models[-1].code == load_action.unique_key

    dialog.close()
    application.processEvents()
