from __future__ import annotations

import sys

from PySide6 import QtWidgets

import VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_editor_graphics as graph
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.Workspace.Tabs.dynamic_editor_tab import DynamicEditorTab
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import (
    DynamicEditorEntry,
    build_dynamic_editor_entry,
    get_templates_for_entry,
)
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_session import DynamicEditorWorkspaceSession
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import BlockType, DynamicSimulationMode, VarPowerFlowReferenceType


DynamicTemplate = RmsModelTemplate | EmtModelTemplate


def get_qt_application() -> QtWidgets.QApplication:
    """Return the process-wide Qt application used by the GUI integration tests.

    :return: Existing application, or a newly created application when pytest
        has not initialized one yet.
    """
    application: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if application is None:
        return QtWidgets.QApplication(sys.argv)
    else:
        return application


def collect_block_contract_counts(block: Block) -> tuple[int, ...]:
    """Count every runtime-relevant collection in a symbolic block tree.

    ``duplicate_block`` rebuilds expressions with fresh variable identities and
    may normalize their written form. Exact equation semantics are therefore
    compared on the final compiled problems; this pre-Apply check ensures the
    Library clone did not lose any part of the catalog payload.

    :param block: Root symbolic block to inspect.
    :return: Counts for blocks, variables, equations, initial equations,
        parameters, event parameters and mappings.
    """
    all_blocks: list[Block] = block.get_all_blocks()
    return (
        len(all_blocks),
        sum(len(current_block.in_vars) for current_block in all_blocks),
        sum(len(current_block.out_vars) for current_block in all_blocks),
        sum(len(current_block.state_vars) for current_block in all_blocks),
        sum(len(current_block.algebraic_vars) for current_block in all_blocks),
        sum(len(current_block.diff_vars) for current_block in all_blocks),
        sum(len(current_block.state_eqs) for current_block in all_blocks),
        sum(len(current_block.algebraic_eqs) for current_block in all_blocks),
        sum(len(current_block.init_eqs) for current_block in all_blocks),
        sum(len(current_block.diff_init_eqs) for current_block in all_blocks),
        sum(len(current_block.parameters) for current_block in all_blocks),
        sum(len(current_block.event_dict) for current_block in all_blocks),
        sum(len(current_block.external_mapping) for current_block in all_blocks),
        sum(len(current_block.api_obj_mapping) for current_block in all_blocks),
    )


def find_named_block(root_block: Block, block_name: str) -> Block:
    """Find the first named block in a symbolic hierarchy.

    :param root_block: Hierarchy root.
    :param block_name: Exact block name requested by the test.
    :return: Matching block.
    :raises AssertionError: If the expected block was not persisted.
    """
    candidate: Block
    for candidate in root_block.get_all_blocks():
        if candidate.name == block_name:
            return candidate
        else:
            pass

    raise AssertionError(f"The Dynamic Editor did not persist template block '{block_name}'.")


def _select_template(entry: DynamicEditorEntry,
                     mode: DynamicSimulationMode,
                     template_name: str) -> DynamicTemplate:
    """Select the same named template exposed by the Dynamic Editor library.

    :param entry: Dynamic Editor entry for one device.
    :param mode: RMS or EMT editor mode.
    :param template_name: Exact library template name.
    :return: Matching dynamic template.
    :raises AssertionError: If the catalog filtering does not expose it.
    """
    catalog_entries: list[object] = get_templates_for_entry(entry=entry, mode=mode)
    catalog_entry: object
    for catalog_entry in catalog_entries:
        if isinstance(catalog_entry, (RmsModelTemplate, EmtModelTemplate)):
            if catalog_entry.name == template_name:
                return catalog_entry
            else:
                pass
        else:
            pass

    raise AssertionError(f"Template '{template_name}' is not available for {entry.api_object.name} in {mode.name} mode.")


def _find_root_wrapper(editor: DynamicBlockEditorGUI,
                       reference: VarPowerFlowReferenceType,
                       block_type: BlockType) -> graph.PortItem:
    """Resolve one exact root-interface port by its semantic network reference.

    :param editor: Active root Dynamic Editor.
    :param reference: Required network reference.
    :param block_type: Input or output connection direction.
    :return: Matching protected or grouped root-interface port.
    :raises AssertionError: If the GUI did not materialize the required port.
    """
    scene_item: object
    interface_ports: list[graph.PortItem]
    interface_port: graph.PortItem
    mapped_var: Var | None = editor.main_block.external_mapping.get(reference, None)

    for scene_item in editor.scene.items():
        if isinstance(scene_item, graph.ProtectedConnectionBlockItem) and scene_item.subsys is not None:
            semantic_reference: VarPowerFlowReferenceType | None = editor._get_semantic_root_interface_reference(
                wrapper_block=scene_item.subsys,
                block_type=block_type,
            )
            if semantic_reference == reference:
                if block_type == BlockType.INPUT_CONN:
                    interface_ports = scene_item.outputs
                elif block_type == BlockType.OUTPUT_CONN:
                    interface_ports = scene_item.inputs
                else:
                    interface_ports = list()

                if len(interface_ports) == 1:
                    return interface_ports[0]
                else:
                    pass
            else:
                pass
        elif isinstance(scene_item, graph.MeasurementsItem):
            if block_type == BlockType.INPUT_CONN:
                interface_ports = scene_item.outputs
            elif block_type == BlockType.OUTPUT_CONN:
                interface_ports = scene_item.inputs
            else:
                interface_ports = list()

            for interface_port in interface_ports:
                if interface_port.base_var is None:
                    pass
                elif (mapped_var is not None
                      and interface_port.base_var.non_mutable_uid == mapped_var.non_mutable_uid):
                    return interface_port
                elif mapped_var is None and interface_port.base_var.ref == reference:
                    return interface_port
                else:
                    pass
        else:
            pass

    raise AssertionError(f"The Dynamic Editor did not create the root port for {reference.name}.")


def _find_template_port(item: graph.GenericBlockItem,
                        reference: VarPowerFlowReferenceType,
                        is_input: bool) -> graph.PortItem:
    """Resolve one template port by its model-side semantic reference.

    :param item: Template graphics item created from the library.
    :param reference: Required power-flow reference.
    :param is_input: Whether the required port is an input.
    :return: Matching graphical port.
    :raises AssertionError: If the template does not expose the expected port.
    """
    ports: list[graph.PortItem] = item.inputs if is_input else item.outputs
    port: graph.PortItem
    for port in ports:
        if port.base_var is not None and port.base_var.ref == reference:
            return port
        else:
            pass

    raise AssertionError(f"The dropped template did not expose port {reference.name}.")


def _dispose_page(page: DynamicEditorTab, application: QtWidgets.QApplication) -> None:
    """Release one editor page through the production teardown path.

    :param page: Dynamic Editor tab to release.
    :param application: Qt application that owns deferred widget events.
    :return: None.
    """
    page.prepare_to_delete()
    page.close()
    page.deleteLater()
    application.processEvents()


def build_dynamic_model_with_editor(application: QtWidgets.QApplication,
                                    circuit: MultiCircuit,
                                    device: DynamicDevice,
                                    mode: DynamicSimulationMode,
                                    template_name: str) -> Block:
    """Build and persist one device model through the real Dynamic Editor path.

    The test opens the same ``DynamicEditorTab`` used by the workspace, creates
    a catalog payload through the library drop command, makes graphical port
    connections, applies the isolated working document and reopens it. This
    covers substantially more GUI behavior than assigning ``device.*_template``
    directly from Python.

    :param application: Shared Qt application.
    :param circuit: Circuit owning the device and template catalog.
    :param device: RMS/EMT-capable device to edit.
    :param mode: Dynamic simulation mode.
    :param template_name: Exact catalog template to drop.
    :return: Persisted template block inside the editor-owned root model.
    """
    entry: DynamicEditorEntry | None = build_dynamic_editor_entry(api_object=device, circuit=circuit)
    if entry is None:
        raise AssertionError(f"The Dynamic Editor cannot open device '{device.name}'.")
    else:
        pass
    assert mode in entry.available_modes

    # Resolve the payload from the same circuit catalog shown by the Library.
    selected_template: DynamicTemplate = _select_template(
        entry=entry,
        mode=mode,
        template_name=template_name,
    )
    session: DynamicEditorWorkspaceSession = DynamicEditorWorkspaceSession()
    page: DynamicEditorTab = session.create_page(entry=entry, mode=mode)
    page.set_dynamic_editor_entry(entry)
    page.show()
    application.processEvents()

    editor: DynamicBlockEditorGUI | None = page.editor
    if editor is None:
        _dispose_page(page=page, application=application)
        raise AssertionError("The Dynamic Editor tab did not create its root editor.")
    else:
        pass

    template_item: object = editor.create_library_payload_item(
        payload=selected_template,
        x_pos=420.0,
        y_pos=220.0,
    )
    if isinstance(template_item, graph.GenericBlockItem) and template_item.subsys is not None:
        template_block: Block = template_item.subsys
    else:
        _dispose_page(page=page, application=application)
        raise AssertionError("The Dynamic Editor library did not create a template block item.")

    # Validate the library clone before graphical connections and Apply are
    # allowed to adapt root mappings and names to the owning network device.
    assert collect_block_contract_counts(selected_template.block) == collect_block_contract_counts(
        template_block
    )

    # Grouped measurements already exist when the root editor opens. Connect their
    # phase ports directly, without invoking the retired per-port relayout workflow.
    expected_connection_count: int = len(template_block.in_vars) + len(template_block.out_vars)
    variable: Var

    # Reproduce the user wiring every network input from the device boundary.
    for variable in template_block.in_vars:
        if isinstance(variable.ref, VarPowerFlowReferenceType):
            input_wrapper_port: graph.PortItem = _find_root_wrapper(
                editor=editor,
                reference=variable.ref,
                block_type=BlockType.INPUT_CONN,
            )
            editor.scene.connect_ports(
                input_wrapper_port,
                _find_template_port(item=template_item, reference=variable.ref, is_input=True),
            )
        else:
            _dispose_page(page=page, application=application)
            raise AssertionError(f"Template input '{variable.name}' has no network reference.")

    # Reproduce the user wiring every model output back to the device boundary.
    for variable in template_block.out_vars:
        if isinstance(variable.ref, VarPowerFlowReferenceType):
            output_wrapper_port: graph.PortItem = _find_root_wrapper(
                editor=editor,
                reference=variable.ref,
                block_type=BlockType.OUTPUT_CONN,
            )
            editor.scene.connect_ports(
                _find_template_port(item=template_item, reference=variable.ref, is_input=False),
                output_wrapper_port,
            )
        else:
            _dispose_page(page=page, application=application)
            raise AssertionError(f"Template output '{variable.name}' has no network reference.")

    assert page.has_unapplied_changes
    assert len(editor.diagram.con_data) == expected_connection_count
    assert all(
        connection_record.routing_payload is not None
        for connection_record in editor.diagram.con_data.values()
    )
    editor.apply_changes()
    application.processEvents()
    assert page.has_unapplied_changes is False
    _dispose_page(page=page, application=application)

    # Reopen a fresh editor document to verify that Apply persisted both the
    # symbolic hierarchy and the diagram connections used by future sessions.
    reopened_page: DynamicEditorTab = session.create_page(entry=entry, mode=mode)
    reopened_page.set_dynamic_editor_entry(entry)
    reopened_page.show()
    application.processEvents()
    reopened_editor: DynamicBlockEditorGUI | None = reopened_page.editor
    if reopened_editor is None:
        _dispose_page(page=reopened_page, application=application)
        raise AssertionError("The persisted dynamic model could not be reopened.")
    else:
        pass

    scene_connections: list[graph.ConnectionItem] = list(
        scene_item
        for scene_item in reopened_editor.scene.items()
        if isinstance(scene_item, graph.ConnectionItem)
    )
    assert len(reopened_editor.diagram.con_data) == expected_connection_count
    assert len(scene_connections) == expected_connection_count
    assert all(connection.path().isEmpty() is False for connection in scene_connections)
    _dispose_page(page=reopened_page, application=application)
    session.reset_for_tests()

    saved_root: Block = device.rms_model if mode == DynamicSimulationMode.RMS else device.emt_model
    return find_named_block(root_block=saved_root, block_name=template_name)
