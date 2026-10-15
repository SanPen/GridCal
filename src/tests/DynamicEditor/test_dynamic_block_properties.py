"""Regression tests for the modal Dynamic Editor block properties workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import numpy as np
import shiboken6

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtTest import QTest
import pytest

import VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_editor_graphics as graph
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGridEngine.enumerations import BlockSymbolKind
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties import (
    BlockParameterDraftModel,
    BlockSymbolDraftRow,
    BlockCodeBuffer,
    BlockEquationDraft,
    BlockVariableRenameRequest,
    BlockStructuralEditRequest,
    DaeCodeDiagnostic,
    DynamicBlockPropertiesDialog,
    build_block_symbol_namespace,
    build_equation_code,
    parse_equation_code,
    replace_dae_identifier,
    resolve_block_documentation_url,
    serialize_dae_expression,
    synchronize_dae_variable_declarations,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties import RuntimeModeDraft
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.add_symbol_dialog import (
    AddSymbolDialog,
    AddSymbolSelection,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties import (
    EquationExportEntry,
    build_equation_pdf_suggested_name,
    build_latex_source,
    build_list_equation_entries,
    build_mapping_equation_entries,
    build_state_equation_entries,
    expand_latex_fractions_for_wrapping,
    expand_latex_square_roots_for_wrapping,
    render_wrapped_equation,
    write_equation_pdf,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_utilities import create_block_of_type
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_utilities import (
    create_default_template_builder,
    get_blocktype2template_builder_dict,
    initialize_template_builder_from_block,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.BlockProperties.dynamic_latex_renderer import (
    LatexRenderer,
    RenderedEquation,
    RenderedSvgEquation,
)
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import ManufacturerNativeModel
from VeraGridEngine.IO.manufacturer_native.model_info import (
    ManufacturerNativeModelInfo,
    ManufacturerNativeSignalInfo,
)
from VeraGridEngine.IO.manufacturer_native.runtime_session import (
    ManufacturerNativeRuntimeSession,
    _RuntimeBinding,
)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagramNode
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import (
    BlockType,
    BlockSymbolCategory,
    DeviceType,
    DynamicSimulationMode,
    EmtFaultPlacementSide,
    IeeeCigreDllDataType,
    EquationExportSection,
    FaultType,
    ParamPowerFlowReferenceType,
    ProceduralLogicType,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Utils.Symbolic.block import Block, normalize_event_parameter_initialization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, get_expression_vars, symbolic_to_string
from VeraGridEngine.Utils.procedural_logic import (
    HardSaturationLogic,
    IeeeCigreDllSignalBinding,
    ManufacturerNativeControllerLogic,
    ProceduralLogicCodec,
)
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_governor_emt
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template_v2 import get_genqec_rms
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.Templates.BasicBlockCatalog import (
    BasicBlockTemplateDescriptor,
    get_basic_block_catalog_descriptor_by_key,
    get_editor_ready_basic_block_catalog_descriptors,
    load_basic_block_catalog_template,
)
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import (
    build_lookup_array_spline_runtime_template,
    build_lookup_matrix_linear_runtime_template,
)
from VeraGridEngine.Templates.BasicBlockCatalog.predefined_blocks import generic
from VeraGridEngine.Templates.ProceduralLogicCatalog import (
    ProceduralBlockTemplateDescriptor,
    build_procedural_block_catalog_template,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    LibraryDeviceTemplateSpec,
    build_dynamic_library_device_template,
    get_dynamic_library_device_specs,
    get_dynamic_library_procedural_descriptors,
)


def get_qt_application() -> QtWidgets.QApplication:
    """Return the process QApplication required by modal widget tests."""
    application: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if application is None:
        return QtWidgets.QApplication(list())
    else:
        return application


def stage_test_symbol(
        dialogue: DynamicBlockPropertiesDialog,
        owner: Block,
        name: str,
        kind: BlockSymbolKind,
        exported: bool = False,
        value: float | None = 0.0,
        create_derivative: bool = False,
        external_reference: VarPowerFlowReferenceType | None = None,
        static_reference: ParamPowerFlowReferenceType | None = None,
) -> None:
    """Stage one typed add-property selection without opening a modal dialog.

    :param dialogue: Block-properties dialog receiving the detached draft.
    :param owner: Block that owns the new symbol.
    :param name: Valid symbolic identifier.
    :param kind: Primary symbol role.
    :param exported: Whether the symbol is also exposed as output.
    :param value: Local initial value, or ``None`` for device initialization.
    :param create_derivative: Whether a state receives a derivative variable.
    :param external_reference: Optional power-flow initialization source.
    :param static_reference: Optional static-parameter device mapping.
    :return: None.
    """
    selection: AddSymbolSelection = AddSymbolSelection(
        owner=owner,
        name=name,
        kind=kind,
        exported=exported,
        value=value,
        create_derivative=create_derivative,
        external_reference=external_reference,
        static_reference=static_reference,
    )
    dialogue._stage_add_symbol_selection(selection=selection)


def close_dirty_block_property_dialogue(dialogue: DynamicBlockPropertiesDialog) -> None:
    """Close a dirty properties dialog in tests without showing confirmation.

    :param dialogue: Dialog whose failed validation leaves unapplied changes.
    :return: None.
    """
    dialogue.prepare_to_delete()
    dialogue.close()


class BlockPropertiesApiStub:
    """Provide the minimum API-object contract required by the editor fixture."""

    __slots__ = ("name", "rms_template", "emt_template", "device_type")

    def __init__(self) -> None:
        """Initialize an API object without an attached dynamic template.

        :return: None.
        """
        self.name: str = "Block properties stub"
        self.rms_template: None = None
        self.emt_template: None = None
        self.device_type: DeviceType = DeviceType.NoDevice


def build_catalog_block_properties_editor() -> DynamicBlockEditorGUI:
    """Build an EMT editor used to exercise catalogue-backed Block Properties.

    :return: Visible dynamic editor with an empty root block.
    """
    # Ensure Qt owns an application before any editor widget is constructed.
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application

    # Use an isolated circuit and symbolic factory so each test owns its state.
    editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        current_block=Block(),
        api_object=BlockPropertiesApiStub(),
        current_theme="Light",
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
        circuit=MultiCircuit(),
        is_root_editor=False,
        modal=False,
    )
    editor.show()
    editor.activateWindow()
    return editor


def build_catalog_block_item_for_properties(
        editor: DynamicBlockEditorGUI,
        template_key: str,
) -> graph.GenericBlockItem:
    """Materialize one catalogue block for a Block Properties test.

    :param editor: Dynamic editor receiving the catalogue block.
    :param template_key: Stable key of the requested Basic Block template.
    :return: Materialized graphics item containing the symbolic block.
    """
    descriptor: BasicBlockTemplateDescriptor = (
        get_basic_block_catalog_descriptor_by_key()[template_key]
    )
    block_item: object = editor.create_library_payload_item(
        descriptor,
        10.0,
        20.0,
    )
    assert isinstance(block_item, graph.GenericBlockItem)
    return block_item


def test_scene_block_name_is_edited_inline_and_persisted() -> None:
    """Change Name must edit the scene label without opening a modal dialogue.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    editor: DynamicBlockEditorGUI = build_catalog_block_properties_editor()
    block_item: graph.GenericBlockItem = build_catalog_block_item_for_properties(
        editor=editor,
        template_key="pulse",
    )
    block: Block | None = block_item.subsys
    assert block is not None

    # The context-menu controller now starts editing on the existing graphics
    # label. The old implementation would block here while executing a dialog.
    editor.rename_block_item(block_item)
    assert block_item.name_item.textInteractionFlags() & QtCore.Qt.TextInteractionFlag.TextEditable
    block_item.name_item.setPlainText("renamed_pulse")
    enter_event: QtGui.QKeyEvent = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Return,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    block_item.name_item.keyPressEvent(enter_event)
    application.processEvents()

    assert block.name == "renamed_pulse"
    assert block_item.name == "renamed_pulse"
    assert block_item.name_item.toPlainText() == "renamed_pulse"
    diagram_node: BlockDiagramNode | None = editor.diagram.node_data.get(block.uid, None)
    assert diagram_node is not None
    assert diagram_node.name == "renamed_pulse"
    assert block_item.name_item.textInteractionFlags() == QtCore.Qt.TextInteractionFlag.NoTextInteraction

    editor.has_unapplied_changes = False
    editor.close()


class AliasRenameReceiver(QtCore.QObject):
    """Apply a complete connected-variable rename for a properties test."""

    __slots__ = ("_dialogue",)

    def __init__(self, dialogue: DynamicBlockPropertiesDialog) -> None:
        """Store the dialogue whose aliases are updated by the request.

        :param dialogue: Properties dialogue containing the connected rows.
        :return: None.
        """
        super().__init__()
        self._dialogue: DynamicBlockPropertiesDialog = dialogue

    @QtCore.Slot(object)
    def apply_rename(self, request: object) -> None:
        """Rename every displayed variable sharing the selected stable UID.

        :param request: Synchronous rename request emitted by Block Properties.
        :return: None.
        """
        if isinstance(request, BlockVariableRenameRequest):
            selected_variable: Var = request.get_variable()
            selected_stable_uid: int = selected_variable.non_mutable_uid
            requested_name: str = request.get_requested_name()
            row_index: int
            for row_index in range(self._dialogue._symbol_model.rowCount()):
                draft_row: BlockSymbolDraftRow | None = self._dialogue._symbol_model.get_row(row_index)
                if draft_row is not None:
                    draft_variable: Var | None = draft_row.get_variable()
                else:
                    draft_variable = None
                if (
                    draft_variable is not None
                    and draft_variable.non_mutable_uid == selected_stable_uid
                ):
                    draft_variable.set_name(requested_name)
                else:
                    pass
            request.set_result(success=True, new_name=requested_name)
        else:
            pass


class AppliedSceneRefreshReceiver(QtCore.QObject):
    """Model the owning editor updating names and children after Apply."""

    __slots__ = ("_root", "_new_child", "_variable")

    def __init__(self, root: Block, new_child: Block, variable: Var) -> None:
        """Keep the scene-side identities changed by the synchronous callback.

        :param root: Working block whose owners are reordered.
        :param new_child: Interface child introduced by scene reconstruction.
        :param variable: Existing variable whose display alias is restored.
        :return: None.
        """
        super().__init__()
        self._root: Block = root
        self._new_child: Block = new_child
        self._variable: Var = variable

    @QtCore.Slot(object)
    def refresh_scene(self, uid: object) -> None:
        """Apply only the scene updates belonging to this receiver's block.

        :param uid: Identity emitted after the block data is committed.
        :return: None.
        """
        if uid == self._root.uid:
            self._root.name = "Refreshed root"
            self._variable.set_name("restored_state")
            if self._new_child not in self._root.children:
                self._root.children.insert(0, self._new_child)
            else:
                pass
        else:
            pass


class StructuralRefreshReceiver(QtCore.QObject):
    """Replace one child without evaluating a real template or simulation."""

    __slots__ = ("_replacement",)

    def __init__(self, replacement: Block) -> None:
        """Keep the generated child supplied by the structural test.

        :param replacement: Model used as the successful rebuild result.
        :return: None.
        """
        super().__init__()
        self._replacement: Block = replacement

    @QtCore.Slot(object)
    def rebuild(self, request: object) -> None:
        """Complete a rebuild using the public synchronous request interface.

        :param request: Structural request from the properties dialog.
        :return: None.
        """
        if isinstance(request, BlockStructuralEditRequest):
            request.get_block().children = list((self._replacement,))
            request.set_result(True, "")
        else:
            pass


@pytest.fixture(autouse=True)
def close_block_property_dialogues() -> Iterator[None]:
    """Destroy every modal created by a test before the next Qt test starts.

    :yield: Control to the individual test before deterministic Qt teardown.
    """
    yield

    # Qt owns binary children independently from Python's garbage collector.
    # Close every dialogue while its wrapper is still valid, then deliver the
    # deferred-delete events before another test can reuse the application.
    application: QtWidgets.QApplication = get_qt_application()
    top_level_widgets: list[QtWidgets.QWidget] = list(application.topLevelWidgets())
    widget: QtWidgets.QWidget
    for widget in top_level_widgets:
        if isinstance(widget, DynamicBlockPropertiesDialog):
            widget.prepare_to_delete()
            widget.close()
        else:
            pass
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    application.processEvents()


def test_side_panel_contains_only_library_while_modal_loads_block_parameters() -> None:
    """Keep parameter editing in Block Properties instead of the editor sidebar.

    :return: None.
    """
    editor: DynamicBlockEditorGUI = build_catalog_block_properties_editor()
    block_item: graph.GenericBlockItem = build_catalog_block_item_for_properties(
        editor=editor,
        template_key="pulse",
    )
    assert block_item.subsys is not None

    # Select the catalogue block while the editor remains on its sole Library page.
    editor.ui.toolBox.setCurrentWidget(editor.ui.page_7)
    editor.scene.clearSelection()
    block_item.setSelected(True)
    QtWidgets.QApplication.processEvents()

    assert editor.ui.toolBox.count() == 1
    assert editor.ui.toolBox.currentWidget() is editor.ui.page_7

    # Parameter rows belong to the dedicated Block Properties dialogue.
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block=block_item.subsys,
        block_type_name=graph.EditorGraphicsCommonFeatures.TEMPLATE_NODE_TYPE,
        var_factory=editor.var_factory,
    )
    assert dialogue._parameter_model.rowCount() > 0
    dialogue.close()

    editor.has_unapplied_changes = False
    editor.close()


def test_modal_parameter_edit_preserves_non_structural_block_identity() -> None:
    """Edit a catalogue constant without reconstructing its symbolic block.

    :return: None.
    """
    editor: DynamicBlockEditorGUI = build_catalog_block_properties_editor()
    block_item: graph.GenericBlockItem = build_catalog_block_item_for_properties(
        editor=editor,
        template_key="pulse",
    )
    assert block_item.subsys is not None
    target_block: Block = block_item.subsys
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block=target_block,
        block_type_name=graph.EditorGraphicsCommonFeatures.TEMPLATE_NODE_TYPE,
        var_factory=editor.var_factory,
    )
    dialogue.blockApplied.connect(editor.on_block_properties_applied)
    assert dialogue._parameter_model.rowCount() > 0
    value_index: QtCore.QModelIndex = dialogue._parameter_model.index(0, 2)
    assert dialogue._parameter_model.data(value_index) == "None"
    changed_value: float = 1.0

    # Apply one value edit through the same model used by the properties table.
    assert dialogue._parameter_model.setData(
        value_index,
        changed_value,
        QtCore.Qt.ItemDataRole.EditRole,
    )
    dialogue.apply_changes()

    assert editor.get_block_from_main_block(target_block.uid) is target_block
    applied_value_found: bool = False
    child_block: Block
    for child_block in target_block.get_all_blocks():
        expression: Expr
        for expression in child_block.event_dict.values():
            if isinstance(expression, Const):
                if expression.value == changed_value:
                    applied_value_found = True
                else:
                    pass
            else:
                pass
    assert applied_value_found
    dialogue.close()

    editor.has_unapplied_changes = False
    editor.close()


def test_scene_refresh_after_rename_keeps_property_name_cells_bound() -> None:
    """Applying a renamed scene block must retain every visible Name value.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    editor: DynamicBlockEditorGUI = build_catalog_block_properties_editor()
    block_item: graph.GenericBlockItem = build_catalog_block_item_for_properties(
        editor=editor,
        template_key="pulse",
    )
    assert block_item.subsys is not None
    target_block: Block = block_item.subsys
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block=target_block,
        block_type_name=graph.EditorGraphicsCommonFeatures.TEMPLATE_NODE_TYPE,
        var_factory=editor.var_factory,
    )
    dialogue.blockApplied.connect(editor.on_block_properties_applied)
    dialogue.variableRenameRequested.connect(editor.on_variable_rename_requested)

    source_row: BlockSymbolDraftRow | None = dialogue._symbol_model.get_row(0)
    assert source_row is not None
    source_index: QtCore.QModelIndex = find_property_index(
        dialogue,
        source_row.get_name(),
        source_row.get_owner(),
    )
    assert source_index.isValid()
    assert dialogue._property_tree_model.setData(source_index, "renamed_signal")
    dialogue.apply_changes()
    application.processEvents()

    assert "renamed_signal" in build_block_symbol_namespace(target_block)
    editor.has_unapplied_changes = False
    editor.close()


def test_parameter_modal_exposes_pulse_runtime_modes_in_python_code() -> None:
    """Show dynamic parameters and expose retained modes in Python code.

    :return: None.
    """
    editor: DynamicBlockEditorGUI = build_catalog_block_properties_editor()
    block_item: graph.GenericBlockItem = build_catalog_block_item_for_properties(
        editor=editor,
        template_key="pulse",
    )
    assert block_item.subsys is not None
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block=block_item.subsys,
        block_type_name=graph.EditorGraphicsCommonFeatures.TEMPLATE_NODE_TYPE,
        var_factory=editor.var_factory,
    )

    # Dynamic parameters and retained modes remain separate tree categories;
    # retained modes are also authored in the owner-specific Python source.
    row_types: list[str] = list()
    row_index: int
    for row_index in range(dialogue._parameter_model.rowCount()):
        index: QtCore.QModelIndex = dialogue._parameter_model.index(row_index, 0)
        row_types.append(
            str(
                dialogue._parameter_model.data(
                    index,
                    QtCore.Qt.ItemDataRole.DisplayRole,
                )
            )
        )

    assert any(row_type.startswith("Dynamic parameter") for row_type in row_types)
    assert not any(row_type.startswith("Mode parameter") for row_type in row_types)
    assert "retained_modes = {" in dialogue._equation_buffers[0].get_code()
    assert "procedural_logic = [" in dialogue._equation_buffers[0].get_code()
    group_names: list[str] = get_property_group_names(dialogue)
    assert "General structure" not in group_names
    assert "Retained modes" in group_names
    tab_labels: list[str] = list()
    tab_index: int
    for tab_index in range(dialogue.ui.tab_widget.count()):
        tab_labels.append(dialogue.ui.tab_widget.tabText(tab_index))
    assert "Runtime logic" not in tab_labels
    dialogue.close()

    editor.has_unapplied_changes = False
    editor.close()


def find_property_index(dialogue: DynamicBlockPropertiesDialog, name: str,
                        owner: Block | None = None) -> QtCore.QModelIndex:
    """Locate a leaf through the tree's existing symbol identity.

    :param dialogue: Open properties containing the hierarchical model.
    :param name: Local symbol name to select.
    :param owner: Optional owner used to distinguish repeated names.
    :return: Name-column index, or an invalid index if absent.
    """
    group_row: int
    for group_row in range(dialogue._property_tree_model.rowCount()):
        group: QtCore.QModelIndex = dialogue._property_tree_model.index(group_row, 0)
        owner_row: int
        for owner_row in range(dialogue._property_tree_model.rowCount(group)):
            parent: QtCore.QModelIndex = dialogue._property_tree_model.index(owner_row, 0, group)
            symbol_row: int
            for symbol_row in range(dialogue._property_tree_model.rowCount(parent)):
                index: QtCore.QModelIndex = dialogue._property_tree_model.index(symbol_row, 0, parent)
                draft: BlockSymbolDraftRow | None = dialogue._property_tree_model.symbol_row(index)
                if draft is not None and draft.get_name() == name and (owner is None or draft.get_owner() is owner):
                    return index
                else:
                    pass
    return QtCore.QModelIndex()


def find_retained_mode_index(dialogue: DynamicBlockPropertiesDialog,
                             name: str,
                             owner: Block | None = None) -> QtCore.QModelIndex:
    """Locate a retained-mode leaf through its runtime draft identity.

    :param dialogue: Open properties containing the hierarchical model.
    :param name: Retained-mode name to select.
    :param owner: Optional owner used to distinguish repeated local names.
    :return: Name-column index, or an invalid index if absent.
    """
    group_row: int
    for group_row in range(dialogue._property_tree_model.rowCount()):
        group: QtCore.QModelIndex = dialogue._property_tree_model.index(group_row, 0)
        owner_row: int
        for owner_row in range(dialogue._property_tree_model.rowCount(group)):
            parent: QtCore.QModelIndex = dialogue._property_tree_model.index(owner_row, 0, group)
            mode_row: int
            for mode_row in range(dialogue._property_tree_model.rowCount(parent)):
                index: QtCore.QModelIndex = dialogue._property_tree_model.index(mode_row, 0, parent)
                mode: RuntimeModeDraft | None = dialogue._property_tree_model.retained_mode_row(index)
                if mode is not None and mode.get_name() == name and (owner is None or mode.get_owner() is owner):
                    return index
                else:
                    pass
    return QtCore.QModelIndex()


def get_property_group_names(dialogue: DynamicBlockPropertiesDialog) -> list[str]:
    """Return visible first-level property groups in display order.

    :param dialogue: Open properties dialogue whose tree is inspected.
    :return: Visible non-empty property-category labels.
    """
    result: list[str] = list()
    group_row: int
    for group_row in range(dialogue._property_tree_model.rowCount()):
        group_index: QtCore.QModelIndex = dialogue._property_tree_model.index(group_row, 0)
        result.append(str(group_index.data()))
    return result


def build_test_block() -> tuple[Block, Var, Var, Const]:
    """Build a small block with equations and an editable numeric parameter."""
    state_variable: Var = Var("x")
    parameter_variable: Var = Var("gain")
    parameter_constant: Const = Const(2.0, name="gain")
    block: Block = Block(
        name="test_block",
        state_vars=[state_variable],
        state_eqs=[parameter_variable],
        parameters={parameter_variable: parameter_constant},
        api_obj_mapping={ParamPowerFlowReferenceType.Pl0: parameter_variable},
        init_eqs={state_variable: Const(1.0)},
    )
    return block, state_variable, parameter_variable, parameter_constant


def test_equation_code_roundtrip_preserves_variable_identity() -> None:
    """Dictionary keys parsed from code must reuse the block's existing Vars."""
    block: Block
    state_variable: Var
    parameter_variable: Var
    parameter_constant: Const
    block, state_variable, parameter_variable, parameter_constant = build_test_block()
    _unused_parameter_variable: Var = parameter_variable
    _unused_parameter_constant: Const = parameter_constant

    code: str = build_equation_code(block)
    draft: BlockEquationDraft = parse_equation_code(code, build_block_symbol_namespace(block))
    initialization_keys: list[Var] = list(draft.get_init_eqs().keys())

    assert "state_vars = [x]" in code
    assert "algebraic_vars = []" in code
    assert "diff_vars = []" in code
    assert "Map every state variable to the right-hand side" in code
    assert "state_eqs = {" in code
    assert "    x: gain," in code
    assert "Write each complete equation with one single '='" in code
    assert len(initialization_keys) == 1
    assert initialization_keys[0] is state_variable
    assert symbolic_to_string(draft.get_state_eqs()[0]) == "gain"
    state_declaration: list[Var] | None = draft.get_variable_declaration("state_vars")
    assert state_declaration == list([state_variable])


def test_state_equation_mapping_is_stored_in_declared_state_order() -> None:
    """Dictionary insertion order must not change the Engine state-equation order."""
    first_state: Var = Var("first_state")
    second_state: Var = Var("second_state")
    namespace: dict[str, Expr] = dict({
        first_state.name: first_state,
        second_state.name: second_state,
    })
    code: str = (
        "state_vars = [first_state, second_state]\n"
        "state_eqs = {\n"
        "    second_state: 2.0,\n"
        "    first_state: 1.0,\n"
        "}\n"
        "algebraic_eqs = []\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )

    draft: BlockEquationDraft = parse_equation_code(code, namespace)

    assert [symbolic_to_string(expression) for expression in draft.get_state_eqs()] == [
        "1.0",
        "2.0",
    ]


def test_state_equation_mapping_requires_exact_state_keys() -> None:
    """Missing or unrelated state keys must be rejected before changing the Engine."""
    first_state: Var = Var("first_state")
    second_state: Var = Var("second_state")
    unrelated_state: Var = Var("unrelated_state")
    namespace: dict[str, Expr] = dict({
        first_state.name: first_state,
        second_state.name: second_state,
        unrelated_state.name: unrelated_state,
    })
    code: str = (
        "state_vars = [first_state, second_state]\n"
        "state_eqs = {first_state: 1.0, unrelated_state: 3.0}\n"
        "algebraic_eqs = []\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )

    with pytest.raises(ValueError, match="missing=.*second_state.*unexpected=.*unrelated_state"):
        parse_equation_code(code, namespace)


def test_complete_algebraic_equalities_convert_to_engine_residuals() -> None:
    """Every supported equality arrangement must produce the expected residual."""
    power: Var = Var("power")
    voltage: Var = Var("voltage")
    current: Var = Var("current")
    namespace: dict[str, Expr] = dict({
        power.name: power,
        voltage.name: voltage,
        current.name: current,
    })
    generated_block: Block = Block(
        name="generated_algebraic",
        algebraic_vars=list((power,)),
        algebraic_eqs=list((power - voltage * current,)),
    )
    generated_code: str = build_equation_code(generated_block)
    assert "    0 = power - (voltage * current)," in generated_code
    generated_draft: BlockEquationDraft = parse_equation_code(generated_code, namespace)
    assert symbolic_to_string(generated_draft.get_algebraic_eqs()[0]) == (
        "(power - (voltage * current))"
    )

    code: str = (
        "state_vars = []\n"
        "state_eqs = {}\n"
        "algebraic_eqs = [\n"
        "    0 = power - voltage * current,\n"
        "    power = voltage * current,\n"
        "    power - voltage * current = 0,\n"
        "]\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )

    draft: BlockEquationDraft = parse_equation_code(code, namespace)
    residual_texts: list[str] = list()
    residual: Expr
    for residual in draft.get_algebraic_eqs():
        residual_texts.append(symbolic_to_string(residual))

    assert residual_texts == list((
        "(power - (voltage * current))",
        "((voltage * current) - power)",
        "(power - (voltage * current))",
    ))


@pytest.mark.parametrize(
    "invalid_equation",
    list((
        "power - voltage * current",
        "power = voltage = current",
        "power < voltage * current",
        "power | voltage",
    )),
)
def test_algebraic_entries_require_one_visible_equality(invalid_equation: str) -> None:
    """Residual-only, chained, inequality, and reserved-marker forms must fail."""
    power: Var = Var("power")
    voltage: Var = Var("voltage")
    current: Var = Var("current")
    namespace: dict[str, Expr] = dict({
        power.name: power,
        voltage.name: voltage,
        current.name: current,
    })
    code: str = (
        "state_vars = []\n"
        "state_eqs = {}\n"
        f"algebraic_eqs = [{invalid_equation}]\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )

    with pytest.raises(ValueError):
        parse_equation_code(code, namespace)


def test_dae_identifier_rename_updates_only_complete_symbol_tokens() -> None:
    """Variable renames must preserve comments and longer symbol names."""
    source_code: str = (
        "state_vars = [x, x_ref]\n"
        "state_eqs = {x: x + x_ref}\n"
        "# x remains explanatory"
    )

    renamed_code: str = replace_dae_identifier(source_code, "x", "speed")

    assert "state_vars = [speed, x_ref]" in renamed_code
    assert "state_eqs = {speed: speed + x_ref}" in renamed_code
    assert "# x remains explanatory" in renamed_code


def test_dialogue_rename_updates_each_connected_local_name_in_dae_code() -> None:
    """One shared stable UID must not hide distinct old names during rename."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    source_variable: Var = Var("const_CONST_1")
    connected_variable: Var = Var(
        "connected_signal",
        non_mutable_uid=source_variable.non_mutable_uid,
    )
    source_block: Block = Block(
        name="CONST_1",
        algebraic_vars=list((source_variable,)),
        algebraic_eqs=list((source_variable - Const(1.0),)),
    )
    connected_block: Block = Block(
        name="GAIN_1",
        algebraic_vars=list((connected_variable,)),
        algebraic_eqs=list((connected_variable - Const(2.0),)),
    )
    root_block: Block = Block(
        name="generic",
        children=list((source_block, connected_block)),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        root_block,
        "CUSTOM",
        VarFactory(),
    )
    rename_receiver: AliasRenameReceiver = AliasRenameReceiver(dialogue)
    dialogue.variableRenameRequested.connect(rename_receiver.apply_rename)

    source_index: QtCore.QModelIndex = find_property_index(dialogue, "const_CONST_1")
    connected_index: QtCore.QModelIndex = find_property_index(dialogue, "connected_signal")
    assert source_index.isValid()
    assert connected_index.isValid()
    source_persistent_index: QtCore.QPersistentModelIndex = QtCore.QPersistentModelIndex(source_index)
    connected_persistent_index: QtCore.QPersistentModelIndex = QtCore.QPersistentModelIndex(connected_index)
    editable_flag: QtCore.Qt.ItemFlag = QtCore.Qt.ItemFlag.ItemIsEditable
    assert dialogue._property_tree_model.flags(source_index) & editable_flag
    assert dialogue._property_tree_model.setData(source_index, "k1")

    assert source_variable.name == "k1"
    assert connected_variable.name == "k1"
    buffer_codes: list[str] = list()
    equation_buffer: BlockCodeBuffer
    for equation_buffer in dialogue._equation_buffers:
        buffer_codes.append(equation_buffer.get_code())
    combined_code: str = "\n".join(buffer_codes)
    assert "const_CONST_1" not in combined_code
    assert "connected_signal" not in combined_code
    assert "algebraic_vars = [k1]" in combined_code
    assert all(
        dialogue._symbol_model.index(row_index, 1).data() == "k1"
        for row_index in range(dialogue._symbol_model.rowCount())
    )
    # A text-only rename must not reset the source model and invalidate the
    # persistent indexes stored by the property tree. Both original leaf
    # indexes must immediately display the accepted name.
    assert source_persistent_index.isValid()
    assert connected_persistent_index.isValid()
    assert source_persistent_index.data() == "k1"
    assert connected_persistent_index.data() == "k1"
    renamed_source_index: QtCore.QModelIndex = find_property_index(dialogue, "k1", source_block)
    renamed_connected_index: QtCore.QModelIndex = find_property_index(dialogue, "k1", connected_block)
    assert renamed_source_index.isValid()
    assert renamed_connected_index.isValid()
    assert renamed_source_index.data() == "k1"
    assert renamed_connected_index.data() == "k1"

    # Applying reloads the source draft model. The rebuilt tree must bind its
    # Name cells to the reloaded rows instead of retaining invalid reset-time
    # indexes that leave only the neighbouring Type column visible.
    dialogue.apply_changes()
    application.processEvents()
    assert source_variable.name == "k1"
    assert connected_variable.name == "k1"


def test_variable_declaration_synchronization_preserves_other_dae_source() -> None:
    """Managed declarations may change without rewriting equations or comments."""
    source_code: str = (
        "state_vars = [\n    old_x,\n]\n"
        "algebraic_vars = []\n"
        "diff_vars = []\n\n"
        "state_eqs = {\n    # User equation comment\n    old_x: old_x,\n}\n"
    )

    updated_code: str = synchronize_dae_variable_declarations(
        code=source_code,
        state_names=list(("old_x", "new_x",)),
        algebraic_names=list(("new_y",)),
        differential_names=list(("d_new_x",)),
    )

    assert "state_vars = [old_x, new_x]" in updated_code
    assert "algebraic_vars = [new_y]" in updated_code
    assert "diff_vars = [d_new_x]" in updated_code
    assert "# User equation comment\n    old_x: old_x," in updated_code


def test_equation_code_removes_only_redundant_root_parentheses() -> None:
    """DAE source must stay readable without changing expression precedence."""
    state_variable: Var = Var("x")
    input_variable: Var = Var("input_signal")
    divisor_variable: Var = Var("divisor")
    expression: Expr = (state_variable - input_variable) / divisor_variable
    block: Block = Block(
        name="precedence_test",
        state_vars=[state_variable],
        state_eqs=[expression],
        in_vars=[input_variable],
        parameters={divisor_variable: Const(2.0, name="divisor")},
        api_obj_mapping={ParamPowerFlowReferenceType.Pl0: divisor_variable},
    )

    code: str = build_equation_code(block)
    assert "    x: (x - input_signal) / divisor," in code
    assert "    x: ((x - input_signal) / divisor)," not in code
    assert serialize_dae_expression(expression) == "(x - input_signal) / divisor"

    draft: BlockEquationDraft = parse_equation_code(
        code,
        build_block_symbol_namespace(block),
    )
    assert symbolic_to_string(draft.get_state_eqs()[0]) == symbolic_to_string(expression)


@pytest.mark.parametrize(
    "invalid_code",
    [
        "import os",
        "state_eqs = []\nalgebraic_eqs = []\ninit_eqs = {}",
        (
            "state_eqs = []\n"
            "algebraic_eqs = []\n"
            "differential_eqs = []\n"
            "init_eqs = {}\n"
            "diff_init_eqs = {}"
        ),
        (
            "state_eqs = [unknown]\n"
            "algebraic_eqs = []\n"
            "init_eqs = {}\n"
            "diff_init_eqs = {}"
        ),
    ],
)
def test_equation_code_rejects_programs_outside_supported_dae_language(invalid_code: str) -> None:
    """The DAE editor is parsed as data and never accepts arbitrary Python."""
    block: Block
    state_variable: Var
    parameter_variable: Var
    parameter_constant: Const
    block, state_variable, parameter_variable, parameter_constant = build_test_block()
    _unused_state_variable: Var = state_variable
    _unused_parameter_variable: Var = parameter_variable
    _unused_parameter_constant: Const = parameter_constant

    with pytest.raises(ValueError):
        parse_equation_code(invalid_code, build_block_symbol_namespace(block))


def test_invalid_dialog_draft_does_not_mutate_block() -> None:
    """A failed Apply must leave all symbolic and numeric source values untouched."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    block: Block
    state_variable: Var
    parameter_variable: Var
    parameter_constant: Const
    block, state_variable, parameter_variable, parameter_constant = build_test_block()
    original_state_equation: object = block.state_eqs[0]
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())
    tab_names: list[str] = list()
    tab_index: int
    for tab_index in range(dialogue.ui.tab_widget.count()):
        tab_names.append(dialogue.ui.tab_widget.tabText(tab_index))
    assert tab_names == list(("General options", "DAE model", "LaTeX rendering"))
    assert not dialogue.ui.tab_widget.tabIcon(dialogue.ui.tab_widget.indexOf(dialogue.ui.general_page)).isNull()
    assert dialogue._dae_editor.parentWidget() is dialogue.ui.dae_editor_container
    assert dialogue.ui.latex_page.isAncestorOf(dialogue.ui.latex_selection_tree)
    assert dialogue.ui.horizontalLayout_3.indexOf(dialogue.ui.validate_code_button) + 2 == (
        dialogue.ui.horizontalLayout_3.indexOf(dialogue.ui.apply_button)
    )
    property_header: QtWidgets.QHeaderView = dialogue.ui.property_tree.header()
    assert property_header.sectionResizeMode(0) == QtWidgets.QHeaderView.ResizeMode.Interactive
    assert property_header.sectionResizeMode(1) == QtWidgets.QHeaderView.ResizeMode.Interactive
    assert property_header.sectionResizeMode(2) == QtWidgets.QHeaderView.ResizeMode.Interactive
    assert property_header.sectionResizeMode(3) == QtWidgets.QHeaderView.ResizeMode.Interactive
    assert "retained_modes = {" in dialogue._dae_editor.toPlainText()
    dialogue._dae_editor.setPlainText("state_eqs = {")
    assert dialogue._dae_editor.get_diagnostics() == list()
    dialogue.ui.validate_code_button.click()
    assert len(dialogue._dae_editor.get_diagnostics()) == 1
    assert "closed" in dialogue._dae_editor.get_diagnostics()[0].get_message().lower()

    dialogue.apply_changes()

    assert block.state_eqs[0] is original_state_equation
    assert parameter_constant.value == 2.0
    close_dirty_block_property_dialogue(dialogue)


def test_valid_dialog_draft_applies_equations_and_parameters_together() -> None:
    """Apply a DAE draft and a dynamic parameter in one transaction.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    block: Block
    state_variable: Var
    parameter_variable: Var
    parameter_constant: Const
    block, state_variable, parameter_variable, parameter_constant = build_test_block()
    dynamic_parameter: Var = Var("dynamic_gain")
    block.event_dict[dynamic_parameter] = Const(0.5)
    emitted_uids: list[int] = list()
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())
    value_index = dialogue._parameter_model.index(0, 2)
    assert dialogue._parameter_model.setData(value_index, "3.5")
    dialogue._dae_editor.setPlainText(
        "state_vars = [x]\n"
        "state_eqs = {x: gain + dynamic_gain}\n"
        "algebraic_eqs = []\n"
        "init_eqs = {x: 0}\n"
        "diff_init_eqs = {}"
    )
    dialogue.blockApplied.connect(emitted_uids.append)

    dialogue.apply_changes()

    assert parameter_constant.value == 2.0
    assert block.event_dict[dynamic_parameter].value == 3.5
    assert symbolic_to_string(block.state_eqs[0]) == "(gain + dynamic_gain)"
    assert list(block.init_eqs.keys())[0] is state_variable
    assert emitted_uids == [block.uid]
    dialogue.close()


def test_governor_mapping_symbols_are_available_to_dae_parser() -> None:
    """Mapped symbols such as Pm_ref must parse even when not listed as events."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block = get_governor_emt(var_factory).block
    namespace: dict[str, Expr] = build_block_symbol_namespace(block)

    assert "Pm_ref" in namespace
    parse_equation_code(build_equation_code(block), namespace)

    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GOV_EMT",
        var_factory,
    )
    dialogue.apply_changes()
    dialogue.close()


def test_recursive_dialog_selects_child_with_equations_and_labels_output_role() -> None:
    """Composite blocks expose child equations and keep primary/output roles separate."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    child: Block = get_governor_emt(var_factory).block
    root: Block = Block(name="complete", children=[child])
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(root, "CUSTOM", var_factory)

    assert dialogue._equation_buffers[dialogue._active_equation_buffer_index].get_block() is child
    assert "Pm_ref" in dialogue._dae_editor.toPlainText()

    tm_row: int | None = None
    row_index: int
    for row_index in range(dialogue._symbol_model.rowCount()):
        if dialogue._symbol_model.index(row_index, 1).data() == "Tm":
            tm_row = row_index
        else:
            pass
    assert tm_row is not None
    assert dialogue._symbol_model.index(tm_row, 2).data() == BlockSymbolKind.ALGEBRAIC.value
    assert dialogue._symbol_model.index(tm_row, 3).data(
        QtCore.Qt.ItemDataRole.CheckStateRole
    ) == QtCore.Qt.CheckState.Checked

    stage_test_symbol(dialogue, child, "child_probe", BlockSymbolKind.ALGEBRAIC)

    # A newly staged algebraic variable is not a complete model until its
    # equation is added. Apply must reject that intermediate state without
    # mutating the live child block.
    dialogue.apply_changes()
    assert all(variable.name != "child_probe" for variable in child.algebraic_vars)
    assert "algebraic variables" in dialogue._dae_editor.toolTip()

    equation_code: str = dialogue._dae_editor.toPlainText()
    equation_code = equation_code.replace(
        "algebraic_vars = [y2_3_gov, Tm]",
        "algebraic_vars = [y2_3_gov, Tm, child_probe]",
        1,
    )
    equation_code = equation_code.replace(
        "algebraic_eqs = [",
        "algebraic_eqs = [\n    0 = child_probe,",
        1,
    )
    dialogue._dae_editor.setPlainText(equation_code)
    dialogue.apply_changes()

    assert [variable.name for variable in child.algebraic_vars][-1] == "child_probe"
    assert all(variable.name != "child_probe" for variable in root.algebraic_vars)
    dialogue.close()


def test_governor_runtime_share_mapping_survives_noop_apply() -> None:
    """A valid event-backed generator sharing reference must survive Apply.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    var_factory: VarFactory = VarFactory()
    governor: Block = get_governor_emt(var_factory).block
    mapping_key: ParamPowerFlowReferenceType = ParamPowerFlowReferenceType.generator_share_p_ref
    runtime_parameter: Var | None = governor.api_obj_mapping.get(mapping_key, None)
    assert runtime_parameter is not None
    assert mapping_key.is_runtime_parameter_reference()
    assert runtime_parameter in governor.event_dict
    assert runtime_parameter not in governor.parameters
    emitted_uids: list[int] = list()

    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        governor,
        "CUSTOM",
        var_factory,
    )
    dialogue.blockApplied.connect(emitted_uids.append)
    dialogue.apply_changes()

    assert emitted_uids == [governor.uid]
    assert governor.api_obj_mapping[mapping_key] is runtime_parameter
    assert runtime_parameter in governor.event_dict
    assert runtime_parameter not in governor.parameters
    application.processEvents()


def test_staged_symbol_is_created_only_when_apply_is_pressed() -> None:
    """Staged variables validate in code before Apply and can independently be outputs."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block = Block(name="editable")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", var_factory)
    stage_test_symbol(dialogue, block, "new_output", BlockSymbolKind.ALGEBRAIC, exported=True)
    assert len(block.algebraic_vars) == 0
    assert len(block.out_vars) == 0

    dialogue._dae_editor.setPlainText(
        "state_vars = []\n"
        "state_eqs = {}\n"
        "algebraic_eqs = [0 = new_output - 1]\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )
    dialogue.ui.validate_code_button.click()
    assert dialogue._dae_editor.get_diagnostics() == list()

    dialogue.apply_changes()
    assert [variable.name for variable in block.algebraic_vars] == ["new_output"]
    assert block.out_vars[0] is block.algebraic_vars[0]
    dialogue.close()


def test_validation_feedback_is_shown_as_toast_without_inline_text() -> None:
    """Validation warnings must no longer write to the old inline status label.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        Block(name="validation_feedback"),
        "GENERIC",
        VarFactory(),
    )

    dialogue._show_dae_validation_message(
        "Model is valid. Warning:\nMode output has no writer.",
        "color: #9a6700;",
    )

    assert dialogue._dae_editor.get_diagnostics() == list()
    dialogue.close()


def test_new_state_derivative_is_visible_and_preserves_its_base_variable() -> None:
    """Creating a state derivative must stage and apply a visible differential row."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block = Block(name="editable_state")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        var_factory,
    )
    stage_test_symbol(
        dialogue,
        block,
        "d111",
        BlockSymbolKind.STATE,
        create_derivative=True,
    )

    state_index: QtCore.QModelIndex = find_property_index(dialogue, "d111")
    derivative_index: QtCore.QModelIndex = find_property_index(dialogue, "d_d111")
    assert state_index.isValid()
    assert derivative_index.isValid()
    assert derivative_index.siblingAtColumn(1).data() == BlockSymbolKind.DIFFERENTIAL.value
    assert block.state_vars == list()
    assert block.diff_vars == list()

    # The state equation stores the RHS. The separately staged derivative is
    # the corresponding LHS identity and therefore needs no extra equation.
    dialogue._dae_editor.setPlainText(
        "state_vars = [d111]\n"
        "state_eqs = {d111: 0}\n"
        "algebraic_eqs = []\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )
    dialogue.apply_changes()

    assert [variable.name for variable in block.state_vars] == ["d111"]
    assert [variable.name for variable in block.diff_vars] == ["d_d111"]
    assert block.diff_vars[0].base_var is block.state_vars[0]
    assert block.state_vars[0].diff_var is block.diff_vars[0]
    dialogue.close()


def test_new_variables_immediately_update_dae_variable_declarations() -> None:
    """Adding table rows must immediately synchronize the visible DAE declarations."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block = Block(name="automatic_declarations")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        var_factory,
    )

    stage_test_symbol(
        dialogue,
        block,
        "speed",
        BlockSymbolKind.STATE,
        create_derivative=True,
    )

    state_code: str = dialogue._dae_editor.toPlainText()
    assert "state_vars = [speed]" in state_code
    assert "algebraic_vars = []" in state_code
    assert "diff_vars = [d_speed]" in state_code
    assert "# Map every state variable to the right-hand side" in state_code

    stage_test_symbol(dialogue, block, "torque", BlockSymbolKind.ALGEBRAIC)

    algebraic_code: str = dialogue._dae_editor.toPlainText()
    assert "state_vars = [speed]" in algebraic_code
    assert "algebraic_vars = [torque]" in algebraic_code
    assert "diff_vars = [d_speed]" in algebraic_code

    speed_index: QtCore.QModelIndex = find_property_index(dialogue, "speed")
    assert speed_index.isValid()
    dialogue.ui.property_tree.setCurrentIndex(speed_index)
    dialogue.delete_property_symbol()
    staged_removal_code: str = dialogue._dae_editor.toPlainText()
    assert "state_vars = []" in staged_removal_code
    assert "algebraic_vars = [torque]" in staged_removal_code
    assert "diff_vars = []" in staged_removal_code
    assert "speed: 0.0" not in staged_removal_code
    assert "d_speed: 0.0" not in staged_removal_code
    assert "torque: 0.0" in staged_removal_code
    close_dirty_block_property_dialogue(dialogue)


def test_deleted_variables_immediately_update_dae_variable_declarations() -> None:
    """State deletion cascades to its derivative, but not in the reverse direction."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    speed_variable: Var = Var("speed")
    speed_differential: Var = Var("d_speed", base_var=speed_variable)
    angle_variable: Var = Var("angle")
    angle_differential: Var = Var("d_angle", base_var=angle_variable)
    algebraic_variable: Var = Var("torque")
    block: Block = Block(
        name="deleted_declarations",
        state_vars=list((speed_variable, angle_variable,)),
        state_eqs=list((speed_variable, angle_variable,)),
        algebraic_vars=list((algebraic_variable,)),
        algebraic_eqs=list((algebraic_variable,)),
        diff_vars=list((speed_differential, angle_differential,)),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        var_factory,
    )

    names_to_remove: tuple[str, ...] = ("d_speed", "angle", "torque", "speed")
    expected_declarations: tuple[str, ...] = (
        "diff_vars = [d_angle]",
        "state_vars = [speed]",
        "algebraic_vars = []",
        "state_vars = []",
    )
    removal_index: int
    for removal_index in range(len(names_to_remove)):
        target_name: str = names_to_remove[removal_index]
        target_index: QtCore.QModelIndex = find_property_index(dialogue, target_name)
        assert target_index.isValid()
        dialogue.ui.property_tree.setCurrentIndex(target_index)
        dialogue.delete_property_symbol()
        updated_code: str = dialogue._dae_editor.toPlainText()
        assert expected_declarations[removal_index] in updated_code
        if target_name == "d_speed":
            assert "state_vars = [speed, angle]" in updated_code
        elif target_name == "angle":
            assert "diff_vars = []" in updated_code
        else:
            pass

    final_code: str = dialogue._dae_editor.toPlainText()
    assert "state_vars = []" in final_code
    assert "algebraic_vars = []" in final_code
    assert "diff_vars = []" in final_code
    assert "state_eqs = {" in final_code
    assert "algebraic_eqs = [" in final_code
    assert dialogue._property_tree_model.rowCount() == 0
    close_dirty_block_property_dialogue(dialogue)


def test_new_input_is_applied_without_offering_external_mapping() -> None:
    """A user-created input must become a port and never request a PF mapping."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block | None = create_block_of_type(
        var_factory,
        BlockType.PI_CURRENT_CONTROLLER,
        "PI_CURRENT_CONTROLLER_test",
    )
    assert isinstance(block, Block)
    initial_input_count: int = len(block.in_vars)
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        BlockType.PI_CURRENT_CONTROLLER.name,
        var_factory,
    )
    add_dialog: AddSymbolDialog = AddSymbolDialog(
        BlockSymbolCategory.VARIABLES,
        list((block,)),
        block,
    )
    assert add_dialog._ui.new_external_reference_label.isHidden()
    assert add_dialog._ui.new_external_reference.isHidden()
    add_dialog.close()
    stage_test_symbol(dialogue, block, "additional_input", BlockSymbolKind.INPUT)
    assert "additional_input" in dialogue._dae_editor.get_language_context().get_namespace()
    dialogue.apply_changes()

    assert len(block.in_vars) == initial_input_count + 1
    assert block.in_vars[-1].name == "additional_input"
    assert all(mapped_variable is not block.in_vars[-1] for mapped_variable in block.external_mapping.values())
    dialogue.close()


def test_legacy_equation_backed_output_does_not_block_new_input() -> None:
    """A saved output-only variable with an equation must remain editable."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    algebraic_variable: Var = var_factory.add_var("algebraic_signal")
    legacy_output: Var = var_factory.add_var("legacy_signal")
    block: Block = Block(
        name="legacy_equation_output",
        algebraic_vars=list([algebraic_variable]),
        algebraic_eqs=list([algebraic_variable, legacy_output]),
        out_vars=list([legacy_output]),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        var_factory,
    )
    stage_test_symbol(dialogue, block, "additional_input", BlockSymbolKind.INPUT)
    dialogue.apply_changes()

    assert block.in_vars[-1].name == "additional_input"
    dialogue.close()


def test_existing_variable_can_stop_being_an_output_on_apply() -> None:
    """An existing algebraic variable must expose a staged removable Output flag."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    exported_variable: Var = var_factory.add_var("exported_signal")
    block: Block = Block(
        name="editable_output",
        algebraic_vars=list([exported_variable]),
        algebraic_eqs=list([exported_variable - Const(1.0)]),
        out_vars=list([exported_variable]),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "CUSTOM", var_factory)
    output_index: QtCore.QModelIndex = dialogue._symbol_model.index(0, 3)

    assert output_index.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable
    assert dialogue._symbol_model.setData(
        output_index,
        QtCore.Qt.CheckState.Unchecked,
        QtCore.Qt.ItemDataRole.CheckStateRole,
    )
    assert block.out_vars == list([exported_variable])
    export_changes: list[tuple[Block, Var, bool]] = dialogue._symbol_model.get_output_export_changes()
    assert export_changes == list([(block, exported_variable, False)])

    dialogue.apply_changes()

    assert block.out_vars == list()
    assert block.algebraic_vars == list([exported_variable])
    dialogue.close()

    # Reopening must still expose the primary algebraic variable so the user
    # can publish it again without recreating either the variable or equation.
    reopened_dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "CUSTOM",
        var_factory,
    )
    reopened_output_index: QtCore.QModelIndex = reopened_dialogue._symbol_model.index(0, 3)
    assert reopened_dialogue._symbol_model.setData(
        reopened_output_index,
        QtCore.Qt.CheckState.Checked,
        QtCore.Qt.ItemDataRole.CheckStateRole,
    )
    reopened_dialogue.apply_changes()

    assert block.algebraic_vars == list([exported_variable])
    assert block.out_vars == list([exported_variable])
    reopened_dialogue.close()


def test_input_and_parameter_cannot_be_exported() -> None:
    """Inputs and configuration parameters must never expose Output checkboxes."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    input_variable: Var = Var("input_signal")
    parameter_variable: Var = Var("gain")
    block: Block = Block(
        name="output_roles",
        in_vars=list([input_variable]),
        parameters=dict({parameter_variable: Const(1.0)}),
        api_obj_mapping=dict({ParamPowerFlowReferenceType.Pl0: parameter_variable}),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "CUSTOM", VarFactory())
    input_output_index: QtCore.QModelIndex = dialogue._symbol_model.index(0, 3)
    parameter_output_index: QtCore.QModelIndex = dialogue._symbol_model.index(1, 3)

    assert not input_output_index.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable
    assert not parameter_output_index.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable
    dialogue.close()


def test_load_rms_device_initialized_event_parameters_are_editable() -> None:
    """Editing a mapped event parameter must select its local value source."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block | None = create_block_of_type(
        var_factory=var_factory,
        block_type=BlockType.LOAD_RMS,
        item_name="LOAD_RMS_test",
    )

    assert isinstance(block, Block)
    child: Block = block.children[0]
    event_variables: dict[str, Var] = dict((variable.name, variable) for variable in child.event_dict.keys())
    assert child.event_dict[event_variables["Pl0"]].value is None
    assert child.event_dict[event_variables["Ql0"]].value is None
    assert event_variables["Pl0"] not in child.init_eqs
    assert event_variables["Ql0"] not in child.init_eqs
    assert block.api_obj_mapping == dict()
    assert child.api_obj_mapping == {
        ParamPowerFlowReferenceType.Pl0: event_variables["Pl0"],
        ParamPowerFlowReferenceType.Ql0: event_variables["Ql0"],
    }

    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        BlockType.LOAD_RMS.name,
        var_factory,
    )
    row_by_name: dict[str, int] = dict()
    row_index: int
    for row_index in range(dialogue._parameter_model.rowCount()):
        parameter_name: object = dialogue._parameter_model.index(row_index, 1).data()
        if isinstance(parameter_name, str):
            row_by_name[parameter_name] = row_index
        else:
            pass

    assert set(row_by_name.keys()) == set(["Pl0", "Ql0"])
    assert dialogue._parameter_model.index(row_by_name["Pl0"], 2).data() == "None"
    assert dialogue._parameter_model.index(row_by_name["Ql0"], 2).data() == "None"
    assert dialogue._parameter_model.setData(
        dialogue._parameter_model.index(row_by_name["Pl0"], 2),
        "Pl + 0.1",
    )
    assert dialogue._parameter_model.setData(
        dialogue._parameter_model.index(row_by_name["Ql0"], 2),
        "-0.2",
    )
    dialogue.apply_changes()

    pl0_expression: Expr = child.event_dict[event_variables["Pl0"]]
    assert not isinstance(pl0_expression, Const)
    assert set(variable.name for variable in get_expression_vars(pl0_expression)) == set(["Pl"])
    assert child.event_dict[event_variables["Ql0"]].value == -0.2
    assert event_variables["Pl0"] not in child.init_eqs
    # Explicit GUI values replace the former device source without changing
    # event_dict ownership, so each parameter retains exactly one initializer.
    assert child.api_obj_mapping == dict()
    assert event_variables["Ql0"] not in child.init_eqs
    dialogue.close()


def test_general_parameters_show_only_event_dict_values() -> None:
    """Keep every fixed constant outside the General options value table.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    mapped_parameter: Var = Var("mapped_parameter")
    local_parameter: Var = Var("local_parameter")
    dynamic_parameter: Var = Var("dynamic_parameter")
    child: Block = Block(
        name="parameter_owner",
        parameters=dict({
            mapped_parameter: Const(None),
            local_parameter: Const(2.0),
        }),
        api_obj_mapping=dict({
            ParamPowerFlowReferenceType.dc_line_r_pu: mapped_parameter,
            ParamPowerFlowReferenceType.dc_line_l_pu_seconds: local_parameter,
        }),
        event_dict=dict({dynamic_parameter: Const(0.05)}),
    )
    root: Block = Block(
        name="mapped_root",
        children=list((child,)),
    )

    parameter_model: BlockParameterDraftModel = BlockParameterDraftModel(root)
    displayed_names: set[str] = set()
    row_index: int
    for row_index in range(parameter_model.rowCount()):
        displayed_name: object = parameter_model.index(row_index, 1).data()
        if isinstance(displayed_name, str):
            displayed_names.add(displayed_name)
        else:
            pass

    assert displayed_names == set(("dynamic_parameter",))
    assert mapped_parameter in child.parameters
    assert local_parameter in child.parameters
    assert (
        child.api_obj_mapping[ParamPowerFlowReferenceType.dc_line_r_pu]
        is mapped_parameter
    )
    assert (
        child.api_obj_mapping[ParamPowerFlowReferenceType.dc_line_l_pu_seconds]
        is local_parameter
    )


def test_legacy_event_parameter_initialization_is_normalized_once() -> None:
    """Move a legacy init expression while preserving an explicit event value."""
    inherited_event: Var = Var("inherited_event")
    explicit_event: Var = Var("explicit_event")
    source_variable: Var = Var("source_variable")
    inherited_expression: Expr = source_variable + Const(1.0)
    child: Block = Block(
        name="legacy_child",
        event_dict=dict({
            inherited_event: Const(None),
            explicit_event: Const(4.0),
        }),
        init_eqs=dict({
            inherited_event: inherited_expression,
            explicit_event: source_variable,
        }),
    )
    root: Block = Block(name="legacy_root", children=list([child]))

    normalize_event_parameter_initialization(block=root)

    assert child.event_dict[inherited_event] is inherited_expression
    assert child.event_dict[explicit_event].value == 4.0
    assert inherited_event not in child.init_eqs
    assert explicit_event not in child.init_eqs


def test_validate_button_rejects_unknown_symbols_and_python_syntax_errors() -> None:
    """Explicit validation reports both unresolved symbols and malformed Python code."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block = Block(name="validation_target")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", var_factory)

    dialogue._dae_editor.setPlainText(
        "state_vars = []\n"
        "state_eqs = {}\n"
        "algebraic_eqs = [0 = missing_symbol]\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )
    assert dialogue._dae_editor.get_diagnostics() == list()
    dialogue.ui.validate_code_button.click()
    assert "Unknown symbol 'missing_symbol'" in dialogue._dae_editor.toolTip()
    assert dialogue._dae_editor.get_diagnostics()[0].get_line() == 3

    dialogue._dae_editor.setPlainText(
        "state_vars = []\n"
        "state_eqs = {}\n"
        "algebraic_eqs = [0 = (1 + 2]\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )
    assert dialogue._dae_editor.get_diagnostics() == list()
    dialogue.ui.validate_code_button.click()
    assert len(dialogue._dae_editor.get_diagnostics()) == 1
    assert dialogue._dae_editor.get_diagnostics()[0].get_line() == 3
    assert "validate again" in dialogue._dae_editor.get_diagnostics()[0].get_message()
    selections: list[QtWidgets.QTextEdit.ExtraSelection] = dialogue._dae_editor.extraSelections()
    assert len(selections) == 1
    assert selections[0].cursor.hasSelection()
    assert selections[0].cursor.selectedText() == "("
    close_dirty_block_property_dialogue(dialogue)


def test_validate_button_marks_the_equation_after_a_missing_comma() -> None:
    """A following complete equality must identify its missing leading comma."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    first: Var = Var("first")
    second: Var = Var("second")
    block: Block = Block(
        name="comma_target",
        algebraic_vars=list([first, second]),
        algebraic_eqs=list([first, second]),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )
    dialogue._dae_editor.setPlainText(
        "state_vars = []\n"
        "state_eqs = {}\n"
        "algebraic_eqs = [\n"
        "    0 = (first - 1)\n"
        "    0 = (second - 2),\n"
        "    0 = (missing_name - 3),\n"
        "]\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )

    assert dialogue._dae_editor.get_diagnostics() == list()
    dialogue.ui.validate_code_button.click()

    assert len(dialogue._dae_editor.get_diagnostics()) == 1
    diagnostic: DaeCodeDiagnostic = dialogue._dae_editor.get_diagnostics()[0]
    assert diagnostic.get_line() == 5
    assert "missing comma" in diagnostic.get_message().lower()
    close_dirty_block_property_dialogue(dialogue)


def test_validate_button_marks_a_cross_line_unmatched_opening_parenthesis() -> None:
    """A later closing bracket must highlight the earlier unmatched opener."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        Block(name="parenthesis_target"),
        "GENERIC",
        VarFactory(),
    )
    dialogue._dae_editor.setPlainText(
        "state_vars = []\n"
        "state_eqs = {}\n"
        "algebraic_eqs = [\n"
        "    0 = (1 + 2,\n"
        "]\n"
        "init_eqs = {}\n"
        "diff_init_eqs = {}"
    )

    dialogue.ui.validate_code_button.click()

    assert len(dialogue._dae_editor.get_diagnostics()) == 1
    diagnostic: DaeCodeDiagnostic = dialogue._dae_editor.get_diagnostics()[0]
    assert diagnostic.get_line() == 4
    assert "validate again" in diagnostic.get_message()
    selections: list[QtWidgets.QTextEdit.ExtraSelection] = dialogue._dae_editor.extraSelections()
    assert selections[0].cursor.selectedText() == "("
    close_dirty_block_property_dialogue(dialogue)


def test_switching_designer_tabs_preserves_pending_code_and_undo() -> None:
    """Switching Designer-owned pages must preserve the active DAE document.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        Block(name="relocated_equations"),
        "GENERIC",
        VarFactory(),
    )
    assert dialogue._dae_editor.parentWidget() is dialogue.ui.dae_editor_container
    original_code: str = dialogue._dae_editor.toPlainText()
    owner_index: int = dialogue.ui.equation_owner_combo.currentIndex()

    # Make a real text edit so both the pending buffer and the document's undo
    # history can reveal an accidental replacement during panel relocation.
    dialogue._dae_editor.insertPlainText("# Pending equation edit\n")
    pending_code: str = dialogue._dae_editor.toPlainText()
    dialogue.ui.dae_code_search.setText("Pending equation edit")
    assert dialogue._dae_editor.document().isUndoAvailable()

    # The pages are fixed by the Designer file. Merely changing pages must not
    # rebuild or reparent the Python editor created for its DAE placeholder.
    dialogue.ui.tab_widget.setCurrentWidget(dialogue.ui.latex_page)
    dialogue.ui.tab_widget.setCurrentWidget(dialogue.ui.dae_model_page)

    assert dialogue.ui.tab_widget.currentWidget() is dialogue.ui.dae_model_page
    assert dialogue._dae_editor.parentWidget() is dialogue.ui.dae_editor_container
    assert dialogue.ui.equation_owner_combo.currentIndex() == owner_index
    assert dialogue._dae_editor.toPlainText() == pending_code
    assert dialogue._equation_buffers[owner_index].get_code() == pending_code
    assert dialogue.ui.dae_code_search.text() == "Pending equation edit"
    assert dialogue._dae_editor.document().isUndoAvailable()

    # Undo must still update the original buffer through its existing signal
    # connection, proving that the panel did not acquire a detached editor.
    dialogue._dae_editor.undo()
    assert dialogue._dae_editor.toPlainText() == original_code
    assert dialogue._equation_buffers[owner_index].get_code() == original_code
    dialogue.close()
    application.processEvents()


def test_generated_structure_is_the_first_tree_branch() -> None:
    """General structural settings lead the non-empty property categories.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    builder: TemplateDefinition | None = create_default_template_builder(
        var_factory,
        BlockType.GFL_VSC_HVDC_RMS,
        BlockType.GFL_VSC_HVDC_RMS.name,
    )
    assert builder is not None
    template: RmsModelTemplate = builder.eval()
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        template.block,
        BlockType.GFL_VSC_HVDC_RMS.name,
        var_factory,
        structural_block_type=BlockType.GFL_VSC_HVDC_RMS,
        structural_builder=builder,
    )
    dialogue.show()
    dialogue.ui.tab_widget.setCurrentIndex(0)
    application.processEvents()

    tree: QtCore.QAbstractItemModel = dialogue._property_tree_model
    structure_group: QtCore.QModelIndex = tree.index(0, 0)
    assert structure_group.data() == "General structure"
    assert tree.rowCount(structure_group) == dialogue._general_structural_model.rowCount()
    group_names: list[str] = get_property_group_names(dialogue)
    assert "Parameters" in group_names
    assert "Variables" in group_names
    assert tree.index(0, 0, structure_group).data() == dialogue._general_structural_model.index(0, 0).data()
    assert tree.index(0, 2, structure_group).data() == dialogue._general_structural_model.index(0, 1).data()
    dialogue.close()


def test_apply_refreshes_code_baseline_and_latex_without_losing_comments() -> None:
    """Accepted edits stay visible and become clean drafts for the next Apply.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    state: Var = Var("state")
    root: Block = Block(name="root", state_vars=list((state,)), state_eqs=list((Const(2.0),)))
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(root, "GENERIC", VarFactory())
    source: str = dialogue._dae_editor.toPlainText().replace("state: 2.0", "state: 7.0")
    dialogue._dae_editor.setPlainText("# Keep the author's explanation\n" + source)
    dialogue.ui.latex_selection_tree.topLevelItem(0).child(0).setCheckState(0, QtCore.Qt.CheckState.Checked)
    dialogue.apply_changes()
    application.processEvents()

    assert symbolic_to_string(root.state_eqs[0]) == "7.0"


def test_apply_refreshes_owner_lists_tree_aliases_and_latex_after_scene_callback() -> None:
    """Refresh after scene reconstruction and retain selections by owner identity.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    state: Var = Var("aliased_state")
    child: Block = Block(name="original", state_vars=list((state,)), state_eqs=list((Const(3.0),)))
    extra_state: Var = Var("extra_state")
    extra: Block = Block(name="new interface", state_vars=list((extra_state,)), state_eqs=list((Const(4.0),)))
    root: Block = Block(name="root", children=list((child,)))
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(root, "GENERIC", VarFactory())
    receiver: AppliedSceneRefreshReceiver = AppliedSceneRefreshReceiver(root, extra, state)
    dialogue.blockApplied.connect(receiver.refresh_scene)
    dialogue.ui.equation_owner_combo.setCurrentIndex(1)
    dialogue._dae_editor.insertPlainText("# Child comment\n")
    dialogue.ui.latex_selection_tree.topLevelItem(1).child(0).setCheckState(0, QtCore.Qt.CheckState.Checked)
    dialogue.apply_changes()
    application.processEvents()

    assert root.name == "Refreshed root"
    assert root.children == list((extra, child))
    assert state.name == "restored_state"


def test_structural_apply_refreshes_removed_owners_and_accepts_new_baselines() -> None:
    """A rebuild discards obsolete children and permits the next edit or Apply.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    var_factory: VarFactory = VarFactory()
    count: TemplateProp = TemplateProp("count", "", "Generated child count", int, 1)
    builder: TemplateDefinition = TemplateDefinition(var_factory, list((count,)))
    old_child: Block = Block(name="old")
    state: Var = Var("new_state")
    replacement: Block = Block(name="rebuilt", state_vars=list((state,)), state_eqs=list((Const(8.0),)))
    root: Block = Block(name="root", children=list((old_child,)))
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        root, "GENERIC", var_factory,
        structural_block_type=BlockType.GFL_VSC_HVDC_RMS, structural_builder=builder,
    )
    receiver: StructuralRefreshReceiver = StructuralRefreshReceiver(replacement)
    dialogue.structuralRebuildRequested.connect(receiver.rebuild)

    assert dialogue._general_structural_model.setData(dialogue._general_structural_model.index(0, 1), "2")
    dialogue.apply_changes()
    application.processEvents()
    assert root.children == list((replacement,))
    assert replacement.state_vars == list((state,))
    assert symbolic_to_string(replacement.state_eqs[0]) == "8.0"


def test_structural_rebuild_does_not_discard_staged_mapping_changes() -> None:
    """A typed mapping must be applied separately from a structural rebuild.

    :return: None.
    """
    var_factory: VarFactory = VarFactory()
    count: TemplateProp = TemplateProp("count", "", "Generated child count", int, 1)
    builder: TemplateDefinition = TemplateDefinition(var_factory, list((count,)))
    state: Var = Var("state")
    block: Block = Block(
        name="root",
        state_vars=list((state,)),
        state_eqs=list((Const(0.0),)),
        external_mapping=dict(((VarPowerFlowReferenceType.P, state),)),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        var_factory,
        structural_block_type=BlockType.GFL_VSC_HVDC_RMS,
        structural_builder=builder,
    )
    mapping_index: QtCore.QModelIndex = find_property_index(
        dialogue,
        "state",
    ).siblingAtColumn(2)

    assert dialogue._property_tree_model.setData(
        mapping_index,
        VarPowerFlowReferenceType.Q,
    )
    assert dialogue._symbol_model.has_mapping_changes()
    assert dialogue._general_structural_model.setData(
        dialogue._general_structural_model.index(0, 1),
        "2",
    )

    dialogue.apply_changes()

    assert block.external_mapping == {VarPowerFlowReferenceType.P: state}
    close_dirty_block_property_dialogue(dialogue)


def test_emt_generator_binary_functions_validate_in_dialogue() -> None:
    """The EMT generator's ``atan2`` expressions must use the safe GUI parser."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block | None = create_block_of_type(
        var_factory,
        BlockType.EMT_GENERATOR,
        "EMT_GENERATOR_test",
    )

    assert isinstance(block, Block)
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        BlockType.EMT_GENERATOR.name,
        var_factory,
    )
    dialogue.validate_complete_dae_code()
    assert dialogue._dae_editor.get_diagnostics() == list()
    dialogue.close()


def test_genraw_initialization_keys_are_only_dae_unknowns() -> None:
    """GENRAW event parameters must not be duplicated in ``init_eqs``.

    :return: None.
    """
    var_factory: VarFactory = VarFactory()
    template: RmsModelTemplate = get_genrow_rms_template(var_factory)
    owner: Block
    for owner in template.block.get_all_blocks():
        allowed_variables: set[Var] = set(owner.state_vars)
        allowed_variables.update(owner.algebraic_vars)
        assert set(owner.init_eqs).issubset(allowed_variables)


def test_rlc_combo_library_block_has_a_default_constructor() -> None:
    """Dragging RLC Combo must yield a balanced explicit/implicit DAE block."""
    var_factory: VarFactory = VarFactory()
    block: Block | None = create_block_of_type(
        var_factory,
        BlockType.RLC_COMBO_EMT,
        "RLC_combo_test",
    )

    assert isinstance(block, Block)
    assert len(block.in_vars) > 0
    assert len(block.out_vars) > 0
    assert len(block.state_vars) == len(block.state_eqs) == 6
    assert len(block.algebraic_vars) == len(block.algebraic_eqs) == 7
    assert [variable.name for variable in block.state_vars] == [
        "iL_A", "vCapA", "iL_B", "vCapB", "iL_C", "vCapC",
    ]
    assert [variable.name for variable in block.algebraic_vars if variable.name.startswith("iC_")] == [
        "iC_A", "iC_B", "iC_C",
    ]


def test_rlc_combo_rendered_pdf_uses_matching_state_derivatives(tmp_path: Path) -> None:
    """RLC export must pair inductor and capacitor RHS entries and create a PDF."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block | None = create_block_of_type(
        var_factory,
        BlockType.RLC_COMBO_EMT,
        "RLC_COMBO_EMT_test",
    )
    assert isinstance(block, Block)
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        BlockType.RLC_COMBO_EMT.name,
        var_factory,
    )

    drafts: list[BlockEquationDraft] = dialogue._parse_all_equation_buffers_for_export()
    dialogue.select_all_latex_sections()
    entries: list[EquationExportEntry] = dialogue._build_selected_equation_entries(drafts)
    state_entries: list[EquationExportEntry] = list()
    entry: EquationExportEntry
    for entry in entries:
        if entry.get_section() == EquationExportSection.STATE:
            state_entries.append(entry)
        else:
            pass
    assert [entry.get_latex().split(" = ", maxsplit=1)[0] for entry in state_entries] == [
        r"d_{iL\_A}",
        "dvCapA",
        r"d_{iL\_B}",
        "dvCapB",
        r"d_{iL\_C}",
        "dvCapC",
    ]

    destination: Path = tmp_path / "rlc_combo_rendered.pdf"
    write_equation_pdf(
        str(destination),
        block.name,
        entries,
    )
    payload: bytes = destination.read_bytes()
    assert payload.startswith(b"%PDF")
    assert b"/Subtype /Image" not in payload
    dialogue.close()


def test_every_builder_backed_library_block_has_a_valid_default() -> None:
    """Removing creation wizards requires every mapped builder to evaluate directly."""
    builder_classes: dict[BlockType, type[TemplateDefinition]] = get_blocktype2template_builder_dict()
    block_type: BlockType
    for block_type in builder_classes:
        builder: TemplateDefinition | None = create_default_template_builder(
            VarFactory(),
            block_type,
            block_type.name,
        )
        assert builder is not None
        template: EmtModelTemplate = builder.eval()
        assert isinstance(template.block, Block)


def test_every_phase_selective_builder_defaults_to_abc_without_neutral() -> None:
    """All phase-capable drag defaults must consistently represent an ABC network."""
    builder_classes: dict[BlockType, type[TemplateDefinition]] = get_blocktype2template_builder_dict()
    block_type: BlockType
    for block_type in builder_classes:
        builder: TemplateDefinition | None = create_default_template_builder(
            VarFactory(),
            block_type,
            block_type.name,
        )
        assert builder is not None
        phase_a: TemplateProp | None = builder.params_dict.get("phA", None)
        phase_b: TemplateProp | None = builder.params_dict.get("phB", None)
        phase_c: TemplateProp | None = builder.params_dict.get("phC", None)
        phase_n: TemplateProp | None = builder.params_dict.get("phN", None)
        if phase_a is not None or phase_b is not None or phase_c is not None:
            assert phase_a is not None and phase_a.value is True
            assert phase_b is not None and phase_b.value is True
            assert phase_c is not None and phase_c.value is True
            if phase_n is not None:
                assert phase_n.value is False
            else:
                pass
        else:
            pass


@pytest.mark.parametrize(
    ("template_name", "expected_suffix"),
    list([
        ("complete_generator_rms_template", "RMS\\complete_generator.md"),
        ("complete_generator_emt_template", "EMT\\complete_generator.md"),
        ("Genrow rms template", "RMS\\genrou_genrow.md"),
        ("Line_rms_template", "RMS\\line.md"),
        ("Load rms template", "RMS\\load.md"),
        ("Voltage source RMS template", "RMS\\voltage_source.md"),
        ("PVD1 DC-MPPT RMS template", "RMS\\distributed_pv.md"),
        ("ESD1 RMS template", "RMS\\battery.md"),
        ("rms_trafo_template", "RMS\\2w_transformer.md"),
        ("vsc_rms_template", "RMS\\gfm_vsc.md"),
        ("emt_thevenin_eq_generator_template", "EMT\\thevenin_generator.md"),
        ("ideal_converter_emt", "EMT\\ideal_converter.md"),
        ("pseudo_converter_emt", "EMT\\full_pseudo_converter.md"),
        ("switched_converter_emt", "EMT\\switched_converter.md"),
        ("dc_load_emt_template", "EMT\\dc_load.md"),
        ("dc_line_power_input_emt", "EMT\\dc_line.md"),
        ("transformer_emt_template", "EMT\\transformer.md"),
        ("xfmr_emt_template", "EMT\\xfmr.md"),
        ("C_shunt", "EMT\\shunt_c_abc.md"),
        ("L_shunt", "EMT\\shunt_l_abc.md"),
        ("R_shunt", "EMT\\shunt_r_abc.md"),
        ("EXP_Load_EMT_3ph", "EMT\\exponential_load_abc.md"),
        ("ZIP_Load_EMT_3ph", "EMT\\zip_load_abc.md"),
        ("Pi", "EMT\\pi_line_abc.md"),
        ("Bergeron", "EMT\\bergeron_line_abc.md"),
        ("induction_motor_emt_template", "EMT\\single_cage_induction_motor.md"),
        ("induction_motor_double_cage_emt_template", "EMT\\double_cage_induction_motor.md"),
        ("bess_avm_grid_following_emt", "EMT\\bess.md"),
        ("pv_avm_grid_following_emt", "EMT\\pv_plant_grid_following.md"),
        ("VSC_GridForming", "EMT\\vsc_grid_forming_gfm.md"),
        ("Pll_transform_rms", "library\\pll_transformer.md"),
    ]),
)
def test_template_documentation_uses_composite_and_pll_online_page(template_name: str,
                                                                    expected_suffix: str) -> None:
    """Generic template nodes must resolve their exact online documentation page."""
    expected_html_suffix: str = expected_suffix.replace("\\", "/")[:-3] + ".html"
    documentation_url: str | None = resolve_block_documentation_url("TEMPLATE", template_name)

    assert documentation_url is not None
    assert documentation_url.startswith(
        "https://veragrid.readthedocs.io/en/latest/md_source/dyn_templates/"
    )
    assert documentation_url.endswith(expected_html_suffix)
    assert "\\" not in documentation_url


# This check belongs to the documentation validation suite, not to ``src/tests``.
# Tests under ``src/tests`` must not require files from the external ``doc`` tree.
# def test_all_explicit_native_documentation_paths_exist() -> None:
#     """Keep every native BlockType documentation association on disk."""
#     documentation_root: Path = Path(__file__).resolve().parents[3] / "doc" / "md_source" / "dyn_templates"
#     mapped_count: int = 0
#     block_type: BlockType
#     for block_type in BlockType:
#         relative_path: str | None = _get_documentation_relative_path(block_type.name, block_type.name)
#         if relative_path is not None:
#             mapped_count += 1
#             assert (documentation_root / relative_path).is_file(), block_type.name
#         else:
#             pass
#
#     assert mapped_count >= 60


# def test_every_dynamic_block_page_explains_the_block_and_its_use() -> None:
#     """Every published block page must explain what it represents and why it is used."""
#     documentation_root: Path = Path(__file__).resolve().parents[3] / "doc" / "md_source" / "dyn_templates"
#     documentation_paths: list[Path] = list(
#         documentation_path
#         for documentation_path in documentation_root.rglob("*.md")
#         if documentation_path.name not in ("dynamic_model_library_index.md", "dae_block_authoring.md")
#     )
#
#     assert len(documentation_paths) >= 780
#     documentation_path: Path
#     for documentation_path in documentation_paths:
#         documentation: str = documentation_path.read_text(encoding="utf-8")
#         assert documentation.count("<!-- veragrid-block-introduction:start -->") == 1, documentation_path
#         assert documentation.count("<!-- veragrid-block-introduction:end -->") == 1, documentation_path
#         assert "## Engineering context" not in documentation, documentation_path
#         assert "## Typical use" in documentation, documentation_path
#         assert len(documentation.split()) >= 75, documentation_path


def test_cigre_surge_source_uses_its_catalogue_markdown() -> None:
    """Resolve the CIGRE source to its exact online catalogue page."""
    documentation_url: str | None = resolve_block_documentation_url(
        BlockType.CIGRE_SURGE_CURRENT_SOURCE_EMT.name,
        "CIGRE_SURGE_CURRENT_SOURCE_EMT_1",
    )

    assert documentation_url is not None
    assert documentation_url.endswith("library/cigre_surge_current_source_emt.html")


def test_every_basic_catalogue_template_resolves_its_own_markdown() -> None:
    """Require one type-id-specific online page for every draggable template."""
    descriptor: BasicBlockTemplateDescriptor
    for descriptor in get_editor_ready_basic_block_catalog_descriptors():
        template: EmtModelTemplate = load_basic_block_catalog_template(
            descriptor=descriptor,
            var_factory=VarFactory(),
        )
        documentation_url: str | None = resolve_block_documentation_url(
            "TEMPLATE",
            template.block.name,
        )

        assert documentation_url is not None, descriptor.display_label
        assert documentation_url.endswith(
            f"library/catalog/typ_{descriptor.typ_id}.html"
        ), descriptor.display_label


def test_procedural_template_documentation_uses_engine_logic_type_after_rename() -> None:
    """Procedural Block info must survive user-visible block renaming.

    :return: None.
    """
    descriptor: ProceduralBlockTemplateDescriptor
    for descriptor in get_dynamic_library_procedural_descriptors():
        template: EmtModelTemplate = build_procedural_block_catalog_template(
            descriptor=descriptor,
            var_factory=VarFactory(),
        )
        template.block.name = "User renamed procedural block"
        documentation_url: str | None = resolve_block_documentation_url(
            BlockType.PROCEDURAL_LOGIC.name,
            template.block.name,
            template.block,
        )

        assert documentation_url is not None
        assert documentation_url.endswith(
            f"procedural_logic/{descriptor.logic_tpe.value}.html"
        )


@pytest.mark.parametrize("block_type, page_name", (
    (BlockType.GFL_VSC_HVDC_RMS, "hvdc_vsc_gfl"),
    (BlockType.VSC_PLL_RMS, "vsc_pll"),
    (BlockType.VSC_ELECTRICAL_RMS, "vsc_electrical"),
    (BlockType.VSC_ACTIVE_CONTROL_RMS, "vsc_active_control"),
    (BlockType.VSC_REACTIVE_CONTROL_RMS, "vsc_reactive_control"),
    (BlockType.VSC_CURRENT_LIMITER_RMS, "vsc_current_limiter"),
    (BlockType.VSC_VD_HAT_RMS, "vsc_vd_hat"),
    (BlockType.VSC_VQ_HAT_RMS, "vsc_vq_hat"),
    (BlockType.VSC_DC_LINK_RMS, "vsc_dc_link"),
    (BlockType.DC_LINE_RMS, "dc_line"),
    (BlockType.VOLTAGE_SOURCE_RMS, "voltage_source"),
))
def test_rms_component_block_info_uses_native_type_after_rename(
        block_type: BlockType,
        page_name: str,
) -> None:
    """Enable each RMS component's published reference despite a display rename.

    :param block_type: Persisted Library type used by Block properties.
    :param page_name: Expected page in the existing RMS documentation section.
    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    expected_url: str = (
        "https://veragrid.readthedocs.io/en/latest/md_source/dyn_templates/RMS/"
        + page_name + ".html"
    )
    # The page belongs to the predefined native type, not the user's current
    # name. In particular, a DC-line RMS entry must not fall back to EMT docs.
    renamed_block: Block = Block(name="Renamed component for the practical session")
    assert resolve_block_documentation_url(block_type.name, renamed_block.name) == expected_url
    assert resolve_block_documentation_url(block_type.name.lower(), block_type.name) == expected_url

    # Block info is dispatched by the block's canvas context menu; the
    # properties dialogue deliberately owns no documentation button.
    assert resolve_block_documentation_url(
        block_type.name,
        renamed_block.name,
        renamed_block,
    ) == expected_url


def test_custom_block_disables_online_catalogue_documentation() -> None:
    """A genuinely custom node must not pretend to have catalogue documentation."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    custom_block: Block = Block(name="User-authored control model")
    assert resolve_block_documentation_url("CUSTOM", custom_block.name) is None


def test_property_tree_accepts_unmapped_static_parameter_literal() -> None:
    """An immutable local literal must not require a device mapping."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    block: Block
    state_variable: Var
    parameter_variable: Var
    parameter_constant: Const
    block, state_variable, parameter_variable, parameter_constant = build_test_block()
    _unused_state_variable: Var = state_variable
    _unused_parameter_variable: Var = parameter_variable
    _unused_parameter_constant: Const = parameter_constant
    block.api_obj_mapping.clear()
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())

    assert dialogue.ui.property_tree.model() is dialogue._property_tree_model
    assert dialogue._property_tree_model.columnCount() == 4
    assert get_property_group_names(dialogue) == list(("Parameters", "Variables"))
    first_group_index: QtCore.QModelIndex = dialogue._property_tree_model.index(0, 0)
    assert dialogue._property_tree_model.columnCount(first_group_index) == 4
    first_owner_index: QtCore.QModelIndex = dialogue._property_tree_model.index(0, 0, first_group_index)
    assert first_owner_index.siblingAtColumn(3).isValid()
    assert find_property_index(dialogue, "x").isValid()
    gain_value_index: QtCore.QModelIndex = find_property_index(
        dialogue,
        "gain",
    ).siblingAtColumn(2)
    assert gain_value_index.data() == "2.0"
    assert parameter_variable not in block.event_dict
    dialogue._symbol_model.build_validation_namespace(build_block_symbol_namespace(block))
    assert dialogue._property_tree_model.setData(gain_value_index, "3.0")
    dialogue.apply_changes()
    assert block.api_obj_mapping == dict()
    assert block.parameters[parameter_variable] is parameter_constant
    assert parameter_constant.value == 3.0
    dialogue.close()


def test_block_properties_searches_filter_tables_and_navigate_python_code() -> None:
    """Every requested Block properties search must act on its own data view."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    block: Block
    state_variable: Var
    parameter_variable: Var
    parameter_constant: Const
    block, state_variable, parameter_variable, parameter_constant = build_test_block()
    _unused_state_variable: Var = state_variable
    _unused_parameter_variable: Var = parameter_variable
    _unused_parameter_constant: Const = parameter_constant
    dynamic_parameter: Var = Var("runtime_coefficient")
    block.event_dict[dynamic_parameter] = Const(0.1)
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )

    state_index: QtCore.QModelIndex = find_property_index(dialogue, "x")
    gain_index: QtCore.QModelIndex = find_property_index(dialogue, "gain")
    event_index: QtCore.QModelIndex = find_property_index(dialogue, "runtime_coefficient")
    dialogue.ui.property_search.setText("runtime_coefficient")
    assert not dialogue.ui.property_tree.isRowHidden(event_index.row(), event_index.parent())
    assert dialogue.ui.property_tree.isRowHidden(gain_index.row(), gain_index.parent())
    assert dialogue.ui.property_tree.isRowHidden(state_index.row(), state_index.parent())
    dialogue.ui.property_search.setText("missing")
    assert dialogue.ui.property_tree.isRowHidden(event_index.row(), event_index.parent())
    dialogue.ui.property_search.clear()
    assert not dialogue.ui.property_tree.isRowHidden(state_index.row(), state_index.parent())

    dialogue.ui.dae_code_search.setText("state_eqs")
    active_match: int
    match_count: int
    active_match, match_count = dialogue._dae_editor.get_search_position()
    assert active_match == 1
    assert match_count >= 1
    dialogue.find_next_dae_code_match()
    next_match: int
    next_count: int
    next_match, next_count = dialogue._dae_editor.get_search_position()
    assert next_count == match_count
    assert next_match == (2 if match_count > 1 else 1)
    dialogue.close()


def test_property_tree_edits_values_mappings_and_outputs_transactionally() -> None:
    """Tree edits must reach the existing drafts and mutate only on Apply.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    state: Var = Var("x")
    static: Var = Var("rated")
    dynamic: Var = Var("gain")
    block: Block = Block(
        name="tree_edits", state_vars=list((state,)), state_eqs=list((dynamic,)),
        parameters=dict(((static, Const(10.0)),)), event_dict=dict(((dynamic, Const(2.0)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, static),)),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())
    static_index: QtCore.QModelIndex = find_property_index(dialogue, "rated").siblingAtColumn(2)
    dynamic_index: QtCore.QModelIndex = find_property_index(dialogue, "gain").siblingAtColumn(2)
    state_index: QtCore.QModelIndex = find_property_index(dialogue, "x")
    assert static_index.data() == "Pl0"
    assert dialogue._property_tree_model.setData(static_index, ParamPowerFlowReferenceType.Ql0)
    assert dialogue._property_tree_model.setData(dynamic_index, "5.0")
    assert dialogue._property_tree_model.setData(state_index.siblingAtColumn(2), VarPowerFlowReferenceType.Q)
    assert dialogue._property_tree_model.setData(
        state_index.siblingAtColumn(3), QtCore.Qt.CheckState.Checked, QtCore.Qt.ItemDataRole.CheckStateRole,
    )
    assert block.event_dict[dynamic].value == 2.0
    assert block.out_vars == list()
    assert ParamPowerFlowReferenceType.Pl0 in block.api_obj_mapping
    dialogue.apply_changes()
    assert block.event_dict[dynamic].value == 5.0
    assert block.api_obj_mapping[ParamPowerFlowReferenceType.Ql0] is static
    assert block.external_mapping[VarPowerFlowReferenceType.Q] is state
    assert block.out_vars == list((state,))
    close_dirty_block_property_dialogue(dialogue)
    application.processEvents()


def test_block_properties_prepare_to_delete_detaches_live_view_editors() -> None:
    """Teardown must detach active property-tree editors before Qt destruction.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    state: Var = Var("x")
    static: Var = Var("rated")
    block: Block = Block(
        name="tree_teardown",
        state_vars=list((state,)),
        parameters=dict(((static, Const(10.0)),)),
        api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, static),)),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )
    dialogue.show()
    static_index: QtCore.QModelIndex = find_property_index(dialogue, "rated").siblingAtColumn(2)

    dialogue.ui.property_tree.openPersistentEditor(static_index)
    application.processEvents()

    assert len(dialogue.ui.property_tree.findChildren(QtWidgets.QComboBox)) > 0

    dialogue.prepare_to_delete()

    assert dialogue.ui.property_tree.model() is None
    assert dialogue.ui.special_settings_table.model() is None
    assert dialogue.ui.equation_owner_combo.count() == 0
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    application.processEvents()

    assert dialogue.ui.property_tree.findChildren(QtWidgets.QComboBox) == list()
    dialogue.close()


def test_new_dynamic_parameter_value_binds_applied_identity() -> None:
    """A numeric event-parameter value must bind the real Var after Apply.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    base: Var = Var("base")
    block: Block = Block(name="new_expression", event_dict=dict(((base, Const(2.0)),)))
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())
    stage_test_symbol(dialogue, block, "scaled", BlockSymbolKind.EVENT_PARAMETER)
    value_index: QtCore.QModelIndex = find_property_index(dialogue, "scaled").siblingAtColumn(2)
    assert value_index.isValid()
    assert not dialogue._property_tree_model.setData(value_index, "base * 3")
    assert dialogue._property_tree_model.setData(value_index, "6.0")
    dialogue.validate_complete_dae_code()
    assert dialogue._dae_editor.get_diagnostics() == list()
    dialogue.apply_changes()
    applied_variable: Var = list(block.event_dict.keys())[-1]
    assert applied_variable.name == "scaled"
    assert block.event_dict[applied_variable].value == 6.0
    dialogue.close()
    application.processEvents()


def test_new_static_parameter_accepts_optional_local_mapping() -> None:
    """A new static parameter may use a literal or an owner-local mapping.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="new_static_parameter")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )

    # A local literal is a complete immutable parameter declaration even when
    # the optional device-backed initial-value selector stays empty.
    add_dialog: AddSymbolDialog = AddSymbolDialog(
        BlockSymbolCategory.PARAMETERS,
        list((block,)),
        block,
    )
    static_parameter_index: int = add_dialog._ui.new_symbol_kind.findData(
        BlockSymbolKind.PARAMETER
    )
    add_dialog._ui.new_symbol_kind.setCurrentIndex(static_parameter_index)
    add_dialog._ui.new_symbol_name.setText("rated_power")
    add_dialog._ui.new_parameter_value.setValue(4.0)
    assert add_dialog._ui.new_parameter_value.isEnabled()
    assert add_dialog._ui.new_static_reference.currentData() is None
    assert add_dialog._ui.new_static_reference.findData(
        ParamPowerFlowReferenceType.generator_share_p_ref
    ) >= 0
    add_dialog._accept_selection()
    local_selection: AddSymbolSelection | None = add_dialog.get_selection()
    assert local_selection is not None
    assert local_selection.get_static_reference() is None
    assert local_selection.get_value() == 4.0
    assert not find_property_index(dialogue, "rated_power").isValid()
    add_dialog.close()

    mapped_dialog: AddSymbolDialog = AddSymbolDialog(
        BlockSymbolCategory.PARAMETERS,
        list((block,)),
        block,
    )
    mapped_static_index: int = mapped_dialog._ui.new_symbol_kind.findData(
        BlockSymbolKind.PARAMETER
    )
    mapped_dialog._ui.new_symbol_kind.setCurrentIndex(mapped_static_index)
    mapped_dialog._ui.new_symbol_name.setText("device_rated_power")
    mapped_reference_index: int = mapped_dialog._ui.new_static_reference.findData(
        ParamPowerFlowReferenceType.Pl0
    )
    mapped_dialog._ui.new_static_reference.setCurrentIndex(mapped_reference_index)
    assert not mapped_dialog._ui.new_parameter_value.isEnabled()
    mapped_dialog._accept_selection()
    mapped_selection: AddSymbolSelection | None = mapped_dialog.get_selection()
    assert mapped_selection is not None
    assert mapped_selection.get_static_reference() == ParamPowerFlowReferenceType.Pl0
    assert mapped_selection.get_value() is None
    mapped_dialog.close()

    # Feed the actual dialog results into the staged model. The local selection
    # must create only a numeric parameter, while the mapped selection must
    # create an owner-local Const(None) and its device initialization entry.
    dialogue._stage_add_symbol_selection(selection=local_selection)
    dialogue._stage_add_symbol_selection(selection=mapped_selection)
    dialogue.apply_changes()

    local_parameters: list[Var] = [
        variable for variable in block.parameters.keys() if variable.name == "rated_power"
    ]
    mapped_parameters: list[Var] = [
        variable for variable in block.parameters.keys() if variable.name == "device_rated_power"
    ]
    assert len(local_parameters) == 1
    assert len(mapped_parameters) == 1
    assert block.parameters[local_parameters[0]].value == 4.0
    assert all(mapped_variable is not local_parameters[0] for mapped_variable in block.api_obj_mapping.values())
    assert block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0] is mapped_parameters[0]
    assert block.parameters[mapped_parameters[0]].value is None
    dialogue.close()
    application.processEvents()


def test_new_event_parameter_accepts_local_device_initial_mapping() -> None:
    """A mapped dynamic parameter must remain owned by event_dict.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="new_mapped_event_parameter")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )

    add_dialog: AddSymbolDialog = AddSymbolDialog(
        BlockSymbolCategory.PARAMETERS,
        list((block,)),
        block,
    )
    add_dialog._ui.new_symbol_name.setText("active_power_reference")
    assert add_dialog._ui.new_symbol_kind.currentData() == BlockSymbolKind.EVENT_PARAMETER
    assert add_dialog._ui.new_parameter_value.isEnabled()
    mapped_reference_index: int = add_dialog._ui.new_static_reference.findData(
        ParamPowerFlowReferenceType.Pl0
    )
    add_dialog._ui.new_static_reference.setCurrentIndex(mapped_reference_index)
    assert not add_dialog._ui.new_parameter_value.isEnabled()
    add_dialog._accept_selection()
    selection: AddSymbolSelection | None = add_dialog.get_selection()
    assert selection is not None
    assert selection.get_value() is None
    assert selection.get_static_reference() == ParamPowerFlowReferenceType.Pl0
    dialogue._stage_add_symbol_selection(selection=selection)
    add_dialog.close()
    dialogue.apply_changes()

    applied_event_parameters: list[Var] = [
        variable
        for variable in block.event_dict
        if variable.name == "active_power_reference"
    ]
    assert len(applied_event_parameters) == 1
    applied_parameter: Var = applied_event_parameters[0]
    assert applied_parameter not in block.parameters
    assert block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0] is applied_parameter
    assert block.event_dict[applied_parameter].value is None
    dialogue.close()
    application.processEvents()


def test_emt_library_templates_declare_each_static_parameter_once() -> None:
    """Require unique hierarchical ownership in every registered EMT template.

    This catalogue-wide contract prevents a wrapper and one of its descendants
    from exposing the same symbolic constant twice, which would make recursive
    EMT problem assembly count one physical parameter more than once.

    :return: None.
    """
    template_specs: list[LibraryDeviceTemplateSpec] = get_dynamic_library_device_specs(
        mode=DynamicSimulationMode.EMT,
    )
    template_spec: LibraryDeviceTemplateSpec
    for template_spec in template_specs:
        built_template: RmsModelTemplate | EmtModelTemplate | None = build_dynamic_library_device_template(
            spec=template_spec,
            var_factory=VarFactory(),
        )
        assert isinstance(built_template, EmtModelTemplate)

        parameter_owner_by_uid: dict[int, Block] = dict()
        owner_block: Block
        for owner_block in built_template.block.get_all_blocks():
            parameter_variable: Var
            for parameter_variable in owner_block.parameters:
                stable_uid: int | None = parameter_variable.non_mutable_uid
                assert stable_uid is not None
                previous_owner: Block | None = parameter_owner_by_uid.get(stable_uid, None)
                assert previous_owner is None, (
                    f"{template_spec.unique_key}: parameter '{parameter_variable.name}' "
                    + f"is declared by both '{previous_owner.name}' and '{owner_block.name}'"
                )
                parameter_owner_by_uid[stable_uid] = owner_block


@pytest.mark.parametrize(
    "mode",
    (DynamicSimulationMode.RMS, DynamicSimulationMode.EMT),
)
def test_library_template_api_mappings_are_owned_locally(
        mode: DynamicSimulationMode,
) -> None:
    """Require every registered template mapping to use one local storage role.

    API references initialize both immutable ``Block.parameters`` and mutable
    ``Block.event_dict`` targets. Checking the entire registered device catalogue
    prevents wrapper blocks from silently exposing mappings owned by descendants
    after recursive block discovery changes.

    :param mode: Dynamic simulation domain whose registered templates are checked.
    :return: None.
    """
    template_specs: list[LibraryDeviceTemplateSpec] = get_dynamic_library_device_specs(
        mode=mode,
    )
    template_spec: LibraryDeviceTemplateSpec

    # Build each public device template exactly through the Library path used by
    # the editor, then validate every recursively discoverable block owner.
    for template_spec in template_specs:
        built_template: RmsModelTemplate | EmtModelTemplate | None = build_dynamic_library_device_template(
            spec=template_spec,
            var_factory=VarFactory(),
        )
        assert built_template is not None
        assert built_template.name == template_spec.label

        owner_block: Block
        for owner_block in built_template.block.get_all_blocks():
            mapping_key: ParamPowerFlowReferenceType
            mapping_target: Var | None
            for mapping_key, mapping_target in owner_block.api_obj_mapping.items():
                mapping_context: str = (
                    f"{template_spec.unique_key}: block '{owner_block.name}', "
                    + f"mapping '{mapping_key.name}'"
                )
                assert mapping_target is not None, mapping_context
                target_is_constant: bool = mapping_target in owner_block.parameters
                target_is_runtime: bool = mapping_target in owner_block.event_dict
                assert target_is_constant != target_is_runtime, mapping_context


def test_retained_mode_category_hides_redundant_type_selector() -> None:
    """The sole retained-mode type must remain selected without a visible choice.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="retained_mode_form")
    add_dialog: AddSymbolDialog = AddSymbolDialog(
        BlockSymbolCategory.RETAINED_MODES,
        list((block,)),
        block,
    )

    assert add_dialog._ui.new_symbol_kind.currentData() == BlockSymbolKind.MODE_PARAMETER
    assert add_dialog._ui.new_symbol_kind_label.isHidden()
    assert add_dialog._ui.new_symbol_kind.isHidden()
    add_dialog.close()
    application.processEvents()


def test_add_symbol_dialog_uses_focused_category_pages() -> None:
    """Each context category must expose only its relevant controls.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="focused_add_symbol_form")
    parameter_dialog: AddSymbolDialog = AddSymbolDialog(
        BlockSymbolCategory.PARAMETERS,
        list((block,)),
        block,
    )

    assert parameter_dialog._ui.symbol_options_stack.currentWidget() is (
        parameter_dialog._ui.parameter_page
    )
    assert parameter_dialog._ui.new_symbol_kind.itemData(0) == BlockSymbolKind.EVENT_PARAMETER
    assert parameter_dialog._ui.new_symbol_kind.itemData(1) == BlockSymbolKind.PARAMETER
    variable_dialog: AddSymbolDialog = AddSymbolDialog(
        BlockSymbolCategory.VARIABLES,
        list((block,)),
        block,
    )
    assert variable_dialog._ui.symbol_options_stack.currentWidget() is (
        variable_dialog._ui.variable_page
    )
    assert variable_dialog._ui.new_symbol_kind.itemData(0) == BlockSymbolKind.INPUT
    assert variable_dialog._ui.new_symbol_kind.itemData(1) == BlockSymbolKind.STATE
    assert variable_dialog._ui.new_symbol_kind.itemData(2) == BlockSymbolKind.ALGEBRAIC

    parameter_dialog.close()
    variable_dialog.close()
    application.processEvents()


def test_add_symbol_dialog_is_released_after_each_invocation() -> None:
    """Independent add-symbol dialogs must release their complete Qt trees.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="repeatable_add_symbol_form")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )
    dialog_index: int
    for dialog_index in range(3):
        _unused_dialog_index: int = dialog_index
        add_dialog: AddSymbolDialog = AddSymbolDialog(
            BlockSymbolCategory.VARIABLES,
            list((block,)),
            block,
            dialogue,
        )
        add_dialog.close()
        add_dialog.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        application.processEvents()
        assert not shiboken6.isValid(add_dialog)
        assert dialogue.findChildren(AddSymbolDialog) == list()

    dialogue.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    application.processEvents()

    assert not shiboken6.isValid(dialogue)


def test_property_tree_reveals_categories_after_their_first_staged_row() -> None:
    """Hide empty groups and reveal each symbol group after its first addition.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="conditional_property_groups")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )

    assert get_property_group_names(dialogue) == list()

    stage_test_symbol(dialogue, block, "runtime_gain", BlockSymbolKind.EVENT_PARAMETER)
    assert get_property_group_names(dialogue) == list(("Parameters",))

    stage_test_symbol(dialogue, block, "input_signal", BlockSymbolKind.INPUT)
    assert get_property_group_names(dialogue) == list(("Parameters", "Variables"))

    stage_test_symbol(dialogue, block, "held_signal", BlockSymbolKind.MODE_PARAMETER)
    assert get_property_group_names(dialogue) == list((
        "Parameters",
        "Variables",
        "Retained modes",
    ))

    close_dirty_block_property_dialogue(dialogue)
    application.processEvents()


def test_new_variables_receive_default_initialization_source_entries() -> None:
    """Stage zero initialization for new block-owned variables and derivatives.

    Inputs receive their values through connections and therefore remain absent
    from ``init_eqs``. Semantic equation validation is deliberately outside this
    add-symbol regression.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="new_variable_initialization")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )

    stage_test_symbol(
        dialogue,
        block,
        "state_signal",
        BlockSymbolKind.STATE,
        create_derivative=True,
    )

    stage_test_symbol(dialogue, block, "algebraic_signal", BlockSymbolKind.ALGEBRAIC)

    stage_test_symbol(dialogue, block, "input_signal", BlockSymbolKind.INPUT)

    source: str = dialogue._dae_editor.toPlainText()
    assert "state_signal: 0.0" in source
    assert "algebraic_signal: 0.0" in source
    assert "d_state_signal: 0.0" in source
    assert "input_signal: 0.0" not in source
    assert "state_vars = [state_signal]" in source
    assert "algebraic_vars = [algebraic_signal]" in source
    assert "diff_vars = [d_state_signal]" in source
    close_dirty_block_property_dialogue(dialogue)
    application.processEvents()


def test_generic_outputs_receive_zero_initialization() -> None:
    """Generic output ports must start with editable deterministic values.

    :return: None.
    """
    block: Block = generic(VarFactory(), inputs=1, outputs=2)

    assert list(block.init_eqs.keys()) == block.out_vars
    initial_expression: Expr
    for initial_expression in block.init_eqs.values():
        assert isinstance(initial_expression, Const)
        assert initial_expression.value == 0.0


def test_retained_mode_tree_leaves_initialization_to_python_code() -> None:
    """Retained-mode initialization must not have a second tree editor.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    source_variable: Var = Var("source_signal")
    block: Block = Block(
        name="mode_expression",
        algebraic_vars=list((source_variable,)),
        algebraic_eqs=list((source_variable,)),
        init_eqs=dict(((source_variable, Const(0.0)),)),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )
    stage_test_symbol(dialogue, block, "held_signal", BlockSymbolKind.MODE_PARAMETER)

    mode_index: QtCore.QModelIndex = find_retained_mode_index(
        dialogue,
        "held_signal",
        block,
    )
    assert mode_index.isValid()
    assert dialogue._property_tree_model.setData(mode_index, "latched_signal")
    source_index: QtCore.QModelIndex = mode_index.siblingAtColumn(2)
    editable_flag: QtCore.Qt.ItemFlag = QtCore.Qt.ItemFlag.ItemIsEditable
    assert source_index.data() is None
    assert not dialogue._property_tree_model.flags(source_index) & editable_flag
    assert not dialogue._property_tree_model.setData(source_index, "source_signal")

    dialogue._dae_editor.setPlainText(
        dialogue._dae_editor.toPlainText().replace(
            "latched_signal: 0.0",
            "latched_signal: source_signal",
        )
    )
    assert "latched_signal: source_signal" in dialogue._dae_editor.toPlainText()
    assert "held_signal" not in dialogue._dae_editor.toPlainText()

    dialogue.apply_changes()

    assert len(block.mode_dict) == 1
    assert list(block.mode_dict.keys())[0].name == "latched_signal"
    applied_initial_expression: Expr = list(block.mode_dict.values())[0]
    assert get_expression_vars(applied_initial_expression) == list((source_variable,))
    dialogue.close()
    application.processEvents()


def test_adding_parent_retained_mode_displays_parent_and_preserves_child_equations() -> None:
    """Adding a mode must show its owner without modifying the previous source.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    var_factory: VarFactory = VarFactory()
    child_output: Var = var_factory.add_var("child_output")
    child: Block = Block(
        name="equation_child",
        algebraic_vars=list((child_output,)),
        algebraic_eqs=list((child_output,)),
    )
    root: Block = Block(name="mode_parent", children=list((child,)))
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        root,
        "GENERIC",
        var_factory,
    )
    active_index_before: int = dialogue._active_equation_buffer_index
    active_code_before: str = dialogue._dae_editor.toPlainText()
    assert dialogue._equation_buffers[active_index_before].get_block() is child

    stage_test_symbol(dialogue, root, "held_mode", BlockSymbolKind.MODE_PARAMETER)

    assert dialogue._active_equation_buffer_index == 0
    assert dialogue._equation_buffers[dialogue._active_equation_buffer_index].get_block() is root
    assert dialogue._dae_editor.toPlainText() == dialogue._equation_buffers[0].get_code()
    assert "held_mode: 0.0" in dialogue._dae_editor.toPlainText()
    assert dialogue._equation_buffers[active_index_before].get_code() == active_code_before
    assert "held_mode: 0.0" in dialogue._equation_buffers[0].get_code()
    retained_mode_index: QtCore.QModelIndex = find_retained_mode_index(
        dialogue,
        "held_mode",
        root,
    )
    assert retained_mode_index.isValid()
    retained_mode_source: QtCore.QModelIndex = retained_mode_index.siblingAtColumn(2)
    assert retained_mode_source.data() is None
    dialogue.apply_changes()
    assert len(child.algebraic_eqs) == 1
    assert "child_output" in str(child.algebraic_eqs[0])
    assert [mode.name for mode in root.mode_dict] == list(("held_mode",))
    dialogue.close()
    application.processEvents()


def test_procedural_menu_inserts_selected_logic_into_active_owner() -> None:
    """The grouped Add action must insert directly without a persistent selector.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="procedural_menu")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )
    concrete_types: list[ProceduralLogicType] = list()
    time_delay_action: QtGui.QAction | None = None
    menu_action: QtGui.QAction
    for menu_action in dialogue._procedural_add_menu.actions():
        action_data: object = menu_action.data()
        if isinstance(action_data, ProceduralLogicType):
            concrete_types.append(action_data)
            if action_data == ProceduralLogicType.TimeDelay:
                time_delay_action = menu_action
            else:
                pass
        else:
            pass

    assert set(concrete_types) == set(ProceduralLogicType) - set((ProceduralLogicType.Base, ProceduralLogicType.ManufacturerNativeController))
    assert time_delay_action is not None
    time_delay_action.trigger()

    source: str = dialogue._dae_editor.toPlainText()
    assert "time_delay(" in source
    assert "output=None" in source
    assert dialogue._dae_editor.textCursor().selectedText() == "None"
    close_dirty_block_property_dialogue(dialogue)
    application.processEvents()


def test_adding_symbol_does_not_validate_incomplete_procedural_logic() -> None:
    """Stage symbols before resolving a procedural output placeholder.

    Add symbol is an editing operation and must therefore accept variables,
    parameters, and modes while ``fixed_sample(output=None)`` is incomplete.
    Explicit validation and Apply must still reject that draft and leave the
    Engine block unchanged.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="incomplete_fixed_sample")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )
    fixed_sample_action: QtGui.QAction | None = None
    menu_action: QtGui.QAction
    for menu_action in dialogue._procedural_add_menu.actions():
        action_data: object = menu_action.data()
        if action_data == ProceduralLogicType.FixedSample:
            fixed_sample_action = menu_action
        else:
            pass
    assert fixed_sample_action is not None
    fixed_sample_action.trigger()
    assert "fixed_sample(" in dialogue._dae_editor.toPlainText()
    assert "output=None" in dialogue._dae_editor.toPlainText()

    stage_test_symbol(dialogue, block, "input_signal", BlockSymbolKind.INPUT)
    assert "input_signal" in dialogue._namespace

    stage_test_symbol(dialogue, block, "runtime_gain", BlockSymbolKind.EVENT_PARAMETER)
    assert "runtime_gain" in dialogue._namespace

    stage_test_symbol(dialogue, block, "sample_mode", BlockSymbolKind.MODE_PARAMETER)

    staged_source: str = dialogue._dae_editor.toPlainText()
    assert "sample_mode: 0.0" in staged_source
    assert "output=None" in staged_source
    assert "sample_mode" in dialogue._dae_editor.get_language_context().get_mode_names()
    assert len(block.in_vars) == 0
    assert len(block.event_dict) == 0
    assert len(block.mode_dict) == 0
    assert len(block.procedural_logic) == 0

    dialogue.apply_changes()
    assert len(block.in_vars) == 0
    assert len(block.event_dict) == 0
    assert len(block.mode_dict) == 0
    assert len(block.procedural_logic) == 0
    close_dirty_block_property_dialogue(dialogue)
    application.processEvents()


def test_pending_symbol_rename_updates_code_and_numeric_parameters() -> None:
    """Inline renaming a new symbol must not leave its earlier name in drafts.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    gain: Var = Var("gain")
    block: Block = Block(name="pending_rename", event_dict=dict(((gain, Const(2.0)),)))
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())
    stage_test_symbol(dialogue, block, "speed", BlockSymbolKind.STATE)
    dialogue._dae_editor.setPlainText(
        "state_vars = [speed]\nstate_eqs = {speed: gain}\nalgebraic_eqs = []\ninit_eqs = {}\ndiff_init_eqs = {}"
    )
    assert not dialogue._property_tree_model.setData(find_property_index(dialogue, "gain").siblingAtColumn(2), "speed + 1")
    assert dialogue._property_tree_model.setData(find_property_index(dialogue, "gain").siblingAtColumn(2), "3.0")
    assert not dialogue._property_tree_model.setData(find_property_index(dialogue, "speed"), "gain")
    assert dialogue._property_tree_model.setData(find_property_index(dialogue, "speed"), "omega")
    assert "speed" not in dialogue._dae_editor.toPlainText()
    assert "state_vars = [omega]" in dialogue._dae_editor.toPlainText()
    assert find_property_index(dialogue, "gain").siblingAtColumn(2).data() == "3.0"
    dialogue.apply_changes()
    assert block.state_vars[0].name == "omega"
    assert block.event_dict[gain].value == 3.0
    dialogue.close()
    application.processEvents()


def test_parent_mapping_to_child_static_parameter_is_rejected() -> None:
    """A static mapping must be owned by the block declaring its parameter.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    rating: Var = Var("rating")
    child: Block = Block(name="child", parameters=dict(((rating, Const(10.0)),)))
    root: Block = Block(
        name="root", children=list((child,)), api_obj_mapping=dict(((ParamPowerFlowReferenceType.Pl0, rating),)),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(root, "GENERIC", VarFactory())
    root_index: QtCore.QModelIndex = find_property_index(dialogue, "rating", root)
    assert root_index.parent().parent().data() == "Variables"
    assert root_index.siblingAtColumn(2).data() == "Pl0"
    child_index: QtCore.QModelIndex = find_property_index(dialogue, "rating", child)
    assert child_index.parent().parent().data() == "Parameters"
    assert child_index.siblingAtColumn(2).data() == "10.0"
    with pytest.raises(ValueError, match="same block's parameters or event_dict"):
        dialogue._symbol_model.build_validation_namespace(build_block_symbol_namespace(root))
    dialogue.close()
    application.processEvents()


def test_new_dynamic_parameter_expression_text_is_rejected_before_apply() -> None:
    """Pending numeric parameter cells must reject symbolic expressions.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    block: Block = Block(name="pending_cycle")
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())
    name: str
    for name in ("first_gain", "second_gain"):
        stage_test_symbol(dialogue, block, name, BlockSymbolKind.EVENT_PARAMETER)
    assert not dialogue._property_tree_model.setData(
        find_property_index(dialogue, "first_gain").siblingAtColumn(2), "second_gain + 1",
    )
    assert find_property_index(dialogue, "first_gain").siblingAtColumn(2).data() == "0.0"
    assert block.event_dict == dict()
    close_dirty_block_property_dialogue(dialogue)
    application.processEvents()


def test_python_runtime_is_preserved_by_noop_apply() -> None:
    """A no-op source Apply must not rebuild modes or procedural instances.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    source: Var = Var("source")
    mode: Var = Var("saturation_mode")
    mode_initial: Const = Const(0.0)
    logic: HardSaturationLogic = HardSaturationLogic("saturation_mode", source, Const(-1.0), Const(1.0))
    block: Block = Block(
        name="hidden_runtime", algebraic_vars=list((source,)), algebraic_eqs=list((source,)),
        mode_dict=dict(((mode, mode_initial),)), procedural_logic=list((logic,)),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())
    assert dialogue.ui.tab_widget.count() == 3
    assert "hard_saturation(" in dialogue._dae_editor.toPlainText()
    dialogue.apply_changes()
    assert block.mode_dict[mode] is mode_initial
    assert block.procedural_logic[0] is logic
    assert logic.u_expr is source
    dialogue.close()
    application.processEvents()


def test_property_owner_selection_guides_symbol_addition() -> None:
    """Owner selection assigns a newly staged symbol to the chosen child.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    existing_gain: Var = Var("existing_gain")
    child: Block = Block(
        name="child",
        event_dict=dict(((existing_gain, Const(1.0)),)),
    )
    root: Block = Block(name="root", children=list((child,)))
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(root, "GENERIC", VarFactory())
    child_index: QtCore.QModelIndex = find_property_index(
        dialogue,
        "existing_gain",
        child,
    ).parent()
    assert child_index.isValid()
    stage_test_symbol(dialogue, child, "child_gain", BlockSymbolKind.EVENT_PARAMETER)
    assert find_property_index(dialogue, "child_gain", child).isValid()
    close_dirty_block_property_dialogue(dialogue)
    application.processEvents()


def test_symbol_mapping_column_applies_power_flow_and_device_references() -> None:
    """Mapping edits must update the actual block dictionaries used at initialization."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    block: Block
    state_variable: Var
    parameter_variable: Var
    parameter_constant: Const
    block, state_variable, parameter_variable, parameter_constant = build_test_block()
    _unused_parameter_constant: Const = parameter_constant
    block.external_mapping[VarPowerFlowReferenceType.P] = state_variable
    block.api_obj_mapping[ParamPowerFlowReferenceType.Pl0] = parameter_variable
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())

    state_mapping_index: QtCore.QModelIndex = dialogue._symbol_model.index(0, 4)
    parameter_mapping_index: QtCore.QModelIndex = dialogue._symbol_model.index(1, 4)
    assert state_mapping_index.data() == "VarPowerFlowReferenceType.P"
    assert parameter_mapping_index.data() == "ParamPowerFlowReferenceType.Pl0"
    assert dialogue._symbol_model.setData(
        state_mapping_index,
        "VarPowerFlowReferenceType.Q",
    )
    assert dialogue._symbol_model.setData(
        parameter_mapping_index,
        "ParamPowerFlowReferenceType.Ql0",
    )

    dialogue.apply_changes()

    assert block.external_mapping == {VarPowerFlowReferenceType.Q: state_variable}
    assert block.api_obj_mapping == {ParamPowerFlowReferenceType.Ql0: parameter_variable}
    dialogue.close()


def test_mapping_editability_matches_variable_and_parameter_semantics() -> None:
    """Both immutable and event parameters may edit device mappings."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    input_variable: Var = Var("command")
    algebraic_variable: Var = Var("power")
    static_parameter: Var = Var("rated_power")
    event_parameter: Var = Var("power_step")
    block: Block = Block(
        name="mapping_semantics",
        in_vars=[input_variable],
        algebraic_vars=[algebraic_variable],
        algebraic_eqs=[algebraic_variable],
        parameters={static_parameter: Const(100.0, name="rated_power")},
        event_dict={event_parameter: Const(0.0, name="power_step")},
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )
    row_by_name: dict[str, int] = dict()
    row_index: int
    for row_index in range(dialogue._symbol_model.rowCount()):
        name_index: QtCore.QModelIndex = dialogue._symbol_model.index(row_index, 1)
        row_by_name[str(name_index.data())] = row_index

    input_index: QtCore.QModelIndex = dialogue._symbol_model.index(row_by_name["command"], 4)
    variable_index: QtCore.QModelIndex = dialogue._symbol_model.index(row_by_name["power"], 4)
    static_index: QtCore.QModelIndex = dialogue._symbol_model.index(row_by_name["rated_power"], 4)
    event_index: QtCore.QModelIndex = dialogue._symbol_model.index(row_by_name["power_step"], 4)
    editable_flag: QtCore.Qt.ItemFlag = QtCore.Qt.ItemFlag.ItemIsEditable

    assert not dialogue._symbol_model.flags(input_index) & editable_flag
    assert dialogue._symbol_model.flags(variable_index) & editable_flag
    assert dialogue._symbol_model.flags(static_index) & editable_flag
    assert dialogue._symbol_model.flags(event_index) & editable_flag
    input_tree_value_index: QtCore.QModelIndex = find_property_index(
        dialogue,
        "command",
    ).siblingAtColumn(2)
    assert input_tree_value_index.data() == ""
    assert not dialogue._property_tree_model.flags(input_tree_value_index) & editable_flag
    assert not dialogue._symbol_model.setData(
        input_index,
        "VarPowerFlowReferenceType.P",
    )
    assert dialogue._symbol_model.setData(
        variable_index,
        "VarPowerFlowReferenceType.P",
    )
    assert not dialogue._symbol_model.setData(
        variable_index,
        "ParamPowerFlowReferenceType.Pl0",
    )
    assert dialogue._symbol_model.setData(
        static_index,
        "ParamPowerFlowReferenceType.Pl0",
    )
    assert dialogue._symbol_model.setData(
        static_index,
        "None",
    )
    assert not dialogue._symbol_model.setData(
        static_index,
        "VarPowerFlowReferenceType.P",
    )
    assert not dialogue._symbol_model.setData(
        event_index,
        "VarPowerFlowReferenceType.P",
    )
    assert dialogue._symbol_model.setData(
        event_index,
        "ParamPowerFlowReferenceType.Ql0",
    )

    dialogue.apply_changes()

    assert block.external_mapping == {VarPowerFlowReferenceType.P: algebraic_variable}
    assert block.api_obj_mapping == {ParamPowerFlowReferenceType.Ql0: event_parameter}
    dialogue.close()


def test_duplicate_power_flow_mapping_is_rejected_before_application() -> None:
    """One internal block cannot initialize two identities from the same PF reference."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    first_variable: Var = Var("x")
    second_variable: Var = Var("y")
    block: Block = Block(
        name="mapping_test",
        algebraic_vars=[first_variable, second_variable],
        algebraic_eqs=[first_variable, second_variable],
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())
    first_mapping_index: QtCore.QModelIndex = dialogue._symbol_model.index(0, 4)
    second_mapping_index: QtCore.QModelIndex = dialogue._symbol_model.index(1, 4)
    assert dialogue._symbol_model.setData(
        first_mapping_index,
        "VarPowerFlowReferenceType.P",
    )
    assert dialogue._symbol_model.setData(
        second_mapping_index,
        "VarPowerFlowReferenceType.P",
    )

    dialogue.apply_changes()

    assert len(block.external_mapping) == 0
    close_dirty_block_property_dialogue(dialogue)


def test_external_mapping_only_identity_remains_visible_in_initialization_column() -> None:
    """A PF-mapped identity must never disappear because it has no displayed DAE role."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    mapped_variable: Var = Var("pf_seed")
    block: Block = Block(
        name="mapping_only_test",
        external_mapping={VarPowerFlowReferenceType.DcPathModeSeed: mapped_variable},
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(block, "GENERIC", VarFactory())

    assert dialogue._symbol_model.rowCount() == 1
    assert dialogue._symbol_model.index(0, 1).data() == "pf_seed"
    assert dialogue._symbol_model.index(0, 4).data() == (
        "VarPowerFlowReferenceType.DcPathModeSeed"
    )
    dialogue.close()


def test_equation_pdf_writer_and_copyable_latex_source(tmp_path: Path) -> None:
    """Selected equations must provide copyable source and one rendered PDF."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    rendered_name: str = build_equation_pdf_suggested_name("Generator")
    assert rendered_name == "Generator_dynamic_equations_latex_rendered.pdf"
    entries: list[EquationExportEntry] = list([
        EquationExportEntry(
            "Generator",
            EquationExportSection.STATE,
            r"\frac{d\omega}{dt}=\frac{T_m-T_e}{M}",
        ),
    ])
    latex_source: str = build_latex_source(entries)
    assert "% Generator - State equations" in latex_source
    assert r"\[" in latex_source
    assert r"\frac{d\omega}{dt}=\frac{T_m-T_e}{M}" in latex_source
    assert r"\]" in latex_source

    destination: Path = tmp_path / rendered_name
    write_equation_pdf(str(destination), "Generator template", entries)
    rendered_payload: bytes = destination.read_bytes()
    assert rendered_payload.startswith(b"%PDF")
    assert len(rendered_payload) > 1000
    # Rendered documents contain native PDF text and SVG paths. No raster
    # image object may be embedded, otherwise zooming would pixelate content.
    assert b"/Subtype /Image" not in rendered_payload


def test_state_and_algebraic_export_entries_use_dae_equation_sides() -> None:
    """State exports use diff-variable LHS while residual exports use zero."""
    first_state_rhs: Const = Const(2.0)
    second_state_rhs: Const = Const(3.0)
    first_state: Var = Var("x")
    first_differential: Var = Var("d_x", base_var=first_state)
    state_entries: list[EquationExportEntry] = build_state_equation_entries(
        "DAE block",
        list([first_state_rhs, second_state_rhs]),
        list([first_differential]),
    )
    algebraic_entries: list[EquationExportEntry] = build_list_equation_entries(
        "DAE block",
        EquationExportSection.ALGEBRAIC,
        list([Const(4.0)]),
    )

    assert state_entries[0].get_latex().startswith(r"d_{x} = ")
    assert state_entries[1].get_latex().startswith("0 = ")
    assert algebraic_entries[0].get_latex().startswith("0 = ")


def test_latex_selection_has_no_differential_section() -> None:
    """Legacy differential residuals are absent from the editable DAE and export groups."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    state_variable: Var = Var("x")
    differential_variable: Var = Var("d_x", base_var=state_variable)
    algebraic_variable: Var = Var("y")
    legacy_differential_expression: Expr = differential_variable - algebraic_variable
    block: Block = Block(
        name="section_test",
        state_vars=list([state_variable]),
        state_eqs=list([Const(1.0)]),
        algebraic_vars=list([algebraic_variable]),
        algebraic_eqs=list([algebraic_variable]),
        diff_vars=list([differential_variable]),
        differential_eqs=list([legacy_differential_expression]),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )
    root_item: QtWidgets.QTreeWidgetItem = dialogue.ui.latex_selection_tree.topLevelItem(0)
    section_labels: list[str] = list()
    section_counts: dict[str, str] = dict()
    child_index: int
    for child_index in range(root_item.childCount()):
        child_item: QtWidgets.QTreeWidgetItem = root_item.child(child_index)
        label: str = child_item.text(0)
        section_labels.append(label)
        section_counts[label] = child_item.text(1)

    assert "Differential equations" not in section_labels
    assert "differential_eqs" not in dialogue._dae_editor.toPlainText()
    assert section_counts["State equations"] == "1"
    assert section_counts["Algebraic equations"] == "1"
    assert dialogue.ui.latex_source_preview.isReadOnly()
    assert dialogue.ui.export_rendered_button.toolTip() == "Save redered PDF"
    dialogue.select_all_latex_sections()
    latex_source: str = dialogue.ui.latex_source_preview.toPlainText()
    assert "% section_test - State equations" in latex_source
    assert r"\[" in latex_source
    assert r"\]" in latex_source

    # Applying the four editable sections must not erase or reinterpret a
    # legacy Engine field that the dialogue deliberately does not expose.
    dialogue.apply_changes()
    assert len(block.differential_eqs) == 1
    assert block.differential_eqs[0] is legacy_differential_expression
    dialogue.close()


def test_latex_block_checkbox_selects_all_non_empty_sections() -> None:
    """The block checkbox controls its sections and reflects partial selection.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    state_variable: Var = Var("x")
    differential_variable: Var = Var("d_x", base_var=state_variable)
    algebraic_variable: Var = Var("y")
    block: Block = Block(
        name="selectable_block",
        state_vars=list((state_variable,)),
        state_eqs=list((Const(1.0),)),
        algebraic_vars=list((algebraic_variable,)),
        algebraic_eqs=list((algebraic_variable,)),
        diff_vars=list((differential_variable,)),
    )
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )
    root_item: QtWidgets.QTreeWidgetItem = dialogue.ui.latex_selection_tree.topLevelItem(0)

    assert root_item.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable
    assert root_item.checkState(0) == QtCore.Qt.CheckState.Unchecked

    # Selecting the block must include every section that contains equations,
    # while unavailable sections remain disabled and unchecked.
    root_item.setCheckState(0, QtCore.Qt.CheckState.Checked)
    application.processEvents()
    child_index: int
    for child_index in range(root_item.childCount()):
        child_item: QtWidgets.QTreeWidgetItem = root_item.child(child_index)
        if child_item.flags() & QtCore.Qt.ItemFlag.ItemIsEnabled:
            assert child_item.checkState(0) == QtCore.Qt.CheckState.Checked
        else:
            assert child_item.checkState(0) == QtCore.Qt.CheckState.Unchecked

    # A direct section edit must be visible in the aggregate block state.
    state_item: QtWidgets.QTreeWidgetItem = root_item.child(0)
    state_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
    application.processEvents()
    assert root_item.checkState(0) == QtCore.Qt.CheckState.PartiallyChecked

    root_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
    application.processEvents()
    for child_index in range(root_item.childCount()):
        child_item = root_item.child(child_index)
        assert child_item.checkState(0) == QtCore.Qt.CheckState.Unchecked
    dialogue.close()


def test_rendered_pdf_equations_wrap_before_scaling() -> None:
    """Long rendered equations must become readable lines that all fit the page width."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    renderer: LatexRenderer = LatexRenderer(font_size=10, dpi=144)
    latex: str = (
        r"0 = \frac{alpha + beta + gamma + delta + epsilon + zeta + eta + theta "
        r"+ iota + kappa + lambda + mu + nu + xi + omicron + pi}{tau + sigma}"
    )
    maximum_width: int = 260
    rendered_lines: list[RenderedSvgEquation] = render_wrapped_equation(
        renderer,
        latex,
        maximum_width,
    )

    expanded_latex: str = expand_latex_fractions_for_wrapping(latex)
    assert r"\frac" not in expanded_latex
    assert "/" in expanded_latex
    assert len(rendered_lines) > 1
    rendered_line: RenderedSvgEquation
    for rendered_line in rendered_lines:
        assert rendered_line.get_size().width() <= maximum_width
    unsupported_latex: str = r"\command_that_mathtext_does_not_support{Vm}"
    unsupported_lines: list[RenderedSvgEquation] = render_wrapped_equation(
        renderer,
        unsupported_latex,
        maximum_width,
    )
    assert len(unsupported_lines) == 1
    assert unsupported_lines[0].get_uses_mathtext() is False
    assert unsupported_latex.encode("utf-8") in unsupported_lines[0].get_data().data()
    assert unsupported_lines[0].get_size().width() <= maximum_width


def test_genqec_equations_render_as_literal_text_and_wrap_long_roots() -> None:
    """GENQEC equation SVGs keep their source text and wrap long radicands."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    block: Block = get_genqec_rms(VarFactory()).block.children[0]
    entries: list[EquationExportEntry] = list()
    entries.extend(build_state_equation_entries(
        block.name,
        block.state_eqs,
        block.diff_vars,
    ))
    entries.extend(build_list_equation_entries(
        block.name,
        EquationExportSection.ALGEBRAIC,
        block.algebraic_eqs,
    ))
    entries.extend(build_mapping_equation_entries(
        block.name,
        EquationExportSection.INITIALIZATION,
        block.init_eqs,
    ))
    renderer: LatexRenderer = LatexRenderer(font_size=10, dpi=144)
    assert "Pg - (Vd" in entries[8].get_latex()
    assert "Qg - (Vq" in entries[9].get_latex()
    assert "Te - (Psid" in entries[14].get_latex()
    assert "Sat - (1 + Sa)" in entries[17].get_latex()
    assert r"1 \times 10^{-5}" in entries[25].get_latex()
    assert r"\mathrm{j}" in entries[28].get_latex()
    entry: EquationExportEntry
    for entry in entries:
        latex_source: str = entry.get_latex()
        rendered: RenderedSvgEquation = renderer.render_svg(latex_source)
        assert not rendered.get_uses_mathtext(), latex_source
        assert latex_source.encode("utf-8") in rendered.get_data().data(), latex_source

    long_root: str = entries[28].get_latex()
    wrapped_root: str = expand_latex_square_roots_for_wrapping(long_root)
    assert r"\sqrt" not in wrapped_root
    wrapped_lines: list[RenderedSvgEquation] = render_wrapped_equation(
        renderer,
        long_root,
        520,
    )
    assert len(wrapped_lines) > 1
    wrapped_line: RenderedSvgEquation
    for wrapped_line in wrapped_lines:
        assert wrapped_line.get_size().width() <= 520


def test_lookup_and_jmarti_builders_expose_conditional_special_settings() -> None:
    """Structured lookup data and JMarti options belong in the optional second tab."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    block_type: BlockType
    for block_type in (
        BlockType.LOOKUP_ARRAY_LINEAR,
        BlockType.EMT_JMARTI_LINE,
    ):
        var_factory: VarFactory = VarFactory()
        builder: TemplateDefinition | None = create_default_template_builder(
            var_factory,
            block_type,
            block_type.name,
        )
        assert builder is not None
        template: EmtModelTemplate = builder.eval()
        block: Block = template.block
        initialize_template_builder_from_block(builder, block, block_type)
        dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
            block,
            block_type.name,
            var_factory,
            structural_block_type=block_type,
            structural_builder=builder,
        )
        tab_names: list[str] = list()
        tab_index: int
        for tab_index in range(dialogue.ui.tab_widget.count()):
            tab_names.append(dialogue.ui.tab_widget.tabText(tab_index))
        assert tab_names == list((
            "General options",
            "DAE model",
            "LaTeX rendering",
            "Special configuration",
        ))
        if block_type == BlockType.EMT_JMARTI_LINE:
            assert dialogue._special_structural_model.rowCount() > 20
        else:
            assert dialogue._special_structural_model.rowCount() > 0
        dialogue.close()


def test_dynamic_lookup_builder_recovers_point_count_and_boundary_rule() -> None:
    """Recover dynamic lookup structure from its persisted symbolic block.

    :return: None.
    """
    source_builder: TemplateDefinition | None = create_default_template_builder(
        var_factory=VarFactory(),
        block_type=BlockType.LOOKUP_ARRAY_LINEAR_VARIABLE,
        item_name="dynamic_lookup",
    )
    assert source_builder is not None
    source_builder.params_dict["point_count"].value = 4
    source_builder.params_dict["clip"].value = False
    source_template: EmtModelTemplate = source_builder.eval()

    restored_builder: TemplateDefinition | None = create_default_template_builder(
        var_factory=VarFactory(),
        block_type=BlockType.LOOKUP_ARRAY_LINEAR_VARIABLE,
        item_name="dynamic_lookup",
    )
    assert restored_builder is not None
    initialize_template_builder_from_block(
        builder=restored_builder,
        block=source_template.block,
        block_type=BlockType.LOOKUP_ARRAY_LINEAR_VARIABLE,
    )

    assert len(source_template.block.in_vars) == 9
    assert restored_builder.params_dict["point_count"].value == 4
    assert restored_builder.params_dict["clip"].value is False


def test_lookup_array_spline_and_matrix_linear_have_distinct_block_types() -> None:
    """Prevent the legacy lookup enum collision from returning.

    :return: None.
    """
    assert BlockType.LOOKUP_ARRAY_OBJECT_SPLINE != BlockType.LOOKUP_MATRIX_LINEAR
    assert BlockType.LOOKUP_ARRAY_OBJECT_SPLINE.value == "LOOKUP_ARRAY_OBJECT_SPLINE"


def test_lookup_spline_clips_above_last_point() -> None:
    """Clamp a spline lookup to its final sample above the tabulated range.

    :return: None.
    """
    template: EmtModelTemplate = build_lookup_array_spline_runtime_template(
        vf=VarFactory(),
        x_points=(0.0, 1.0, 2.0),
        y_points=(0.0, 10.0, 20.0),
        name="spline_upper_clip",
    )
    block: Block = template.block
    value_by_uid: dict[int, float] = dict()
    value_by_uid[block.in_vars[0].uid] = 3.0
    value_by_uid[block.out_vars[0].uid] = 20.0
    parameter_variable: Var
    parameter_expression: Expr
    for parameter_variable, parameter_expression in block.event_dict.items():
        assert isinstance(parameter_expression, Const)
        assert isinstance(parameter_expression.value, (int, float))
        value_by_uid[parameter_variable.uid] = float(parameter_expression.value)

    residual: float = float(block.algebraic_eqs[0].eval_uid(value_by_uid))
    assert residual == pytest.approx(0.0)


def test_lookup_matrix_rejects_unordered_axes() -> None:
    """Reject ambiguous two-dimensional lookup axes before equation creation.

    :return: None.
    """
    with pytest.raises(ValueError, match="x-axis values must be strictly increasing"):
        build_lookup_matrix_linear_runtime_template(
            vf=VarFactory(),
            x_points=(0.0, 0.0),
            y_points=(0.0, 1.0),
            z_matrix=((0.0, 1.0), (2.0, 3.0)),
            name="invalid_matrix",
        )


def test_fault_builder_recovers_all_settings_after_block_roundtrip() -> None:
    """Restore fault topology, orientation, control, and values after reopening.

    :return: None.
    """
    source_builder: TemplateDefinition | None = create_default_template_builder(
        var_factory=VarFactory(),
        block_type=BlockType.FAULT_EMT,
        item_name="persisted_fault",
    )
    assert source_builder is not None
    source_builder.params_dict["fault_type"].value = FaultType.LLG
    source_builder.params_dict["placement_side"].value = EmtFaultPlacementSide.ToSide
    source_builder.params_dict["phA"].value = False
    source_builder.params_dict["phB"].value = True
    source_builder.params_dict["phC"].value = True
    source_builder.params_dict["signal_controlled"].value = True
    source_builder.params_dict["initial_closed"].value = True
    source_builder.params_dict["fault_resistance"].value = 0.021
    source_builder.params_dict["ground_resistance"].value = 0.034
    source_builder.params_dict["open_conductance"].value = 2.0e-7
    source_builder.params_dict["fault_time_constant"].value = 2.5e-4
    source_builder.params_dict["command_threshold"].value = 0.61
    source_builder.params_dict["name"].value = "persisted_fault"
    generated_template: EmtModelTemplate = source_builder.eval()
    restored_block: Block = Block.parse(
        data=generated_template.block.to_dict(),
        procedural_logic_codec=ProceduralLogicCodec(),
    )

    restored_builder: TemplateDefinition | None = create_default_template_builder(
        var_factory=VarFactory(),
        block_type=BlockType.FAULT_EMT,
        item_name=restored_block.name,
    )
    assert restored_builder is not None
    initialize_template_builder_from_block(
        builder=restored_builder,
        block=restored_block,
        block_type=BlockType.FAULT_EMT,
    )

    assert restored_builder.get_value("fault_type") is FaultType.LLG
    assert restored_builder.get_value("placement_side") is EmtFaultPlacementSide.ToSide
    assert not restored_builder.get_value("phA")
    assert restored_builder.get_value("phB")
    assert restored_builder.get_value("phC")
    assert restored_builder.get_value("signal_controlled")
    assert restored_builder.get_value("initial_closed")
    assert restored_builder.get_value("fault_resistance") == pytest.approx(0.021)
    assert restored_builder.get_value("ground_resistance") == pytest.approx(0.034)
    assert restored_builder.get_value("open_conductance") == pytest.approx(2.0e-7)
    assert restored_builder.get_value("fault_time_constant") == pytest.approx(2.5e-4)
    assert restored_builder.get_value("command_threshold") == pytest.approx(0.61)
    assert restored_builder.get_value("name") == "persisted_fault"


def test_genraw_properties_dialogue_opens_with_absolute_value_latex() -> None:
    """GENRAW equations containing adjacent absolute delimiters must render safely."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    var_factory: VarFactory = VarFactory()
    block: Block | None = create_block_of_type(var_factory, BlockType.GENRAW, "GENRAW_test")

    assert isinstance(block, Block)
    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        BlockType.GENRAW.name,
        var_factory,
    )
    assert dialogue.validate_dae_code()
    dialogue.close()


def test_genraw_rendered_pdf_accepts_absolute_value_initialization(tmp_path: Path) -> None:
    """GENRAW absolute-value initialization must compile in rendered export."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    block: Block | None = create_block_of_type(
        VarFactory(),
        BlockType.GENRAW,
        "GENRAW_test",
    )
    assert isinstance(block, Block)
    entries: list[EquationExportEntry] = list()
    owner: Block
    for owner in block.get_all_blocks():
        entries.extend(build_state_equation_entries(
            owner.name,
            owner.state_eqs,
            owner.diff_vars,
        ))
        residual_expressions: list[Expr] = list(owner.algebraic_eqs)
        entries.extend(build_list_equation_entries(
            owner.name,
            EquationExportSection.ALGEBRAIC,
            residual_expressions,
        ))
        entries.extend(build_mapping_equation_entries(
            owner.name,
            EquationExportSection.INITIALIZATION,
            owner.init_eqs,
        ))
        entries.extend(build_mapping_equation_entries(
            owner.name,
            EquationExportSection.DERIVATIVE_INITIALIZATION,
            owner.diff_init_eqs,
        ))

    destination: Path = tmp_path / "genraw_rendered.pdf"
    write_equation_pdf(
        str(destination),
        block.name,
        entries,
    )

    payload: bytes = destination.read_bytes()
    assert payload.startswith(b"%PDF")
    assert len(payload) > 1000


def test_latex_renderer_keeps_unsupported_and_oversized_text_readable() -> None:
    """Unsupported commands and oversized sources use Qt's readable text fallback."""
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    renderer: LatexRenderer = LatexRenderer()

    rendered: RenderedEquation = renderer.render(r"\command_that_mathtext_does_not_support{Vm}")
    assert not rendered.get_pixmap().isNull()
    assert rendered.get_size().height() >= 24
    assert not rendered.get_uses_mathtext()

    oversized_latex: str = " + ".join(["very_long_symbol"] * 1000)
    oversized_rendering: RenderedEquation = renderer.render(oversized_latex)
    assert not oversized_rendering.get_pixmap().isNull()
    assert oversized_rendering.get_size().width() < 1000
    assert not oversized_rendering.get_uses_mathtext()


def test_manufacturer_native_controller_opens_as_read_only_block() -> None:
    """Inspect an importer-owned controller without reconstructing or mutating it.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    _unused_application: QtWidgets.QApplication = application
    controller: ManufacturerNativeControllerLogic = ManufacturerNativeControllerLogic(
        provider_idtag="provider-id",
        model_info_sha256="1" * 64,
        signal_bindings=tuple(),
        parameter_overrides=tuple(),
        name="Manufacturer controller",
    )
    block: Block = Block(
        name="manufacturer block",
        procedural_logic=(controller,),
        is_decomposable=False,
    )
    original_data: dict[str, object] = controller.to_data()
    original_entries: tuple[object, ...] = tuple(block.procedural_logic)

    dialogue: DynamicBlockPropertiesDialog = DynamicBlockPropertiesDialog(
        block,
        "GENERIC",
        VarFactory(),
    )

    assert "read-only manufacturer model" in dialogue.windowTitle()
    assert not dialogue.ui.apply_button.isEnabled()
    assert not dialogue.ui.procedural_add_button.isEnabled()
    assert dialogue._dae_editor.isReadOnly()
    assert "manufacturer_native_controller(" not in dialogue._dae_editor.toPlainText()
    assert "Internal manufacturer_native_controller entry" in dialogue._dae_editor.toPlainText()

    dialogue.validate_complete_dae_code()
    dialogue.apply_changes()

    assert tuple(block.procedural_logic) == original_entries
    assert block.procedural_logic[0] is controller
    assert controller.to_data() == original_data
    dialogue.prepare_to_delete()


def test_manufacturer_native_controller_has_transient_scene_presentation() -> None:
    """Expose the canonical OEM block with real ports and no root self-alias.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    circuit: MultiCircuit = MultiCircuit()
    provider: ManufacturerNativeModel = ManufacturerNativeModel(
        name="Qualified OEM provider"
    )
    provider.model_info = b"veragrid-manufacturer-native-model-info-v2\n{}"
    circuit.add_manufacturer_native_model(provider)
    input_variable: Var = Var(name="u")
    input_vector_variable: Var = Var(name="u_q")
    output_variable: Var = Var(name="y")
    controller: ManufacturerNativeControllerLogic = ManufacturerNativeControllerLogic(
        provider_idtag=provider.idtag,
        model_info_sha256=provider.model_info_sha256,
        signal_bindings=(
            IeeeCigreDllSignalBinding(True, 0, 0, input_variable),
            IeeeCigreDllSignalBinding(True, 0, 1, input_vector_variable),
            IeeeCigreDllSignalBinding(False, 0, 0, output_variable),
        ),
        parameter_overrides=tuple(),
        name="Manufacturer controller",
    )
    root_block: Block = Block(
        in_vars=(input_variable, input_vector_variable),
        out_vars=(output_variable,),
        mode_dict={output_variable: Const(0.0)},
        name="OEM root",
        procedural_logic=(controller,),
        is_decomposable=False,
    )
    editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=VarFactory(),
        current_block=root_block,
        root_block=root_block,
        api_object=BlockPropertiesApiStub(),
        current_theme="Light",
        mode=DynamicSimulationMode.RMS,
        templates_list=list(),
        circuit=circuit,
        is_root_editor=False,
        modal=False,
    )
    editor.show()
    application.processEvents()

    oem_items: list[graph.GenericBlockItem] = [
        scene_item
        for scene_item in editor.scene.items()
        if isinstance(scene_item, graph.GenericBlockItem)
        and scene_item.subsys is root_block
    ]
    assert len(oem_items) == 1
    oem_item: graph.GenericBlockItem = oem_items[0]
    assert [port.base_var for port in oem_item.inputs] == [
        input_variable,
        input_vector_variable,
    ]
    assert [port.base_var for port in oem_item.outputs] == [output_variable]
    assert all(port.isVisible() for port in oem_item.inputs)
    assert all(port.isVisible() for port in oem_item.outputs)
    assert "Provider: Qualified OEM provider" in oem_item.toolTip()
    assert "Interface: ieee_cigre_v1_1" in oem_item.toolTip()
    assert "Domain: RMS" in oem_item.toolTip()
    assert "Inputs: 1" in oem_item.toolTip()
    assert "Outputs: 1" in oem_item.toolTip()
    assert "Reference: Valid" in oem_item.toolTip()

    wrapper_items: list[graph.MeasurementsItem] = [
        scene_item
        for scene_item in editor.scene.items()
        if isinstance(scene_item, graph.MeasurementsItem)
    ]
    assert len(wrapper_items) == 3
    assert all(
        not wrapper_item.sceneBoundingRect().intersects(oem_item.sceneBoundingRect())
        for wrapper_item in wrapper_items
    )

    # Exercise ordinary GUI wires. Root wrappers intentionally expose the
    # same canonical Vars as the atomic block, so these branches persist while
    # the symbolic registry remains empty.
    input_port: graph.PortItem
    for input_port in oem_item.inputs:
        matching_sources: list[graph.PortItem] = [
            wrapper_item.outputs[0]
            for wrapper_item in wrapper_items
            if len(wrapper_item.outputs) == 1
            and wrapper_item.outputs[0].base_var is input_port.base_var
        ]
        assert len(matching_sources) == 1
        editor.attach_new_connection_item(item=graph.ConnectionItem(
            source_port=matching_sources[0],
            target_port=input_port,
            diagram=editor.diagram,
            editor=editor,
        ))

    output_port: graph.PortItem
    for output_port in oem_item.outputs:
        matching_targets: list[graph.PortItem] = [
            wrapper_item.inputs[0]
            for wrapper_item in wrapper_items
            if len(wrapper_item.inputs) == 1
            and wrapper_item.inputs[0].base_var is output_port.base_var
        ]
        assert len(matching_targets) == 1
        editor.attach_new_connection_item(item=graph.ConnectionItem(
            source_port=output_port,
            target_port=matching_targets[0],
            diagram=editor.diagram,
            editor=editor,
        ))

    assert len(root_block.diagram.con_data) == 3
    connection_records: list[object] = [
        connection
        for connections in editor.var_factory.get_connections_dict().values()
        for connection in connections
    ]
    assert connection_records == list()

    # The real block retains the established read-only properties gesture.
    scene_center: QtCore.QPointF = oem_item.mapToScene(oem_item.rect().center())
    view_position: QtCore.QPoint = editor.view.mapFromScene(scene_center)
    QTest.mouseDClick(
        editor.view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=view_position,
    )
    application.processEvents()
    properties_dialogue: DynamicBlockPropertiesDialog | None = (
        editor._block_properties_dialogue
    )
    assert properties_dialogue is not None
    assert "read-only manufacturer model" in properties_dialogue.windowTitle()
    assert not properties_dialogue.ui.apply_button.isEnabled()
    properties_dialogue.prepare_to_delete()
    properties_dialogue.close()
    application.processEvents()

    # Reference diagnostics decorate the real item instead of adding another
    # graphics object or runtime validator.
    controller.model_info_sha256 = "2" * 64
    editor._add_manufacturer_native_controller_presentations()
    assert "ModelInfo digest mismatch" in oem_item.toolTip()
    assert oem_item._validation_highlighted

    controller.model_info_sha256 = provider.model_info_sha256
    editor._add_manufacturer_native_controller_presentations()
    assert "Reference: Valid" in oem_item.toolTip()
    assert not oem_item._validation_highlighted

    original_connection_count: int = len(root_block.diagram.con_data)
    editor.rebuild_scene_from_diagram()
    application.processEvents()
    reopened_items: list[graph.GenericBlockItem] = [
        scene_item
        for scene_item in editor.scene.items()
        if isinstance(scene_item, graph.GenericBlockItem)
        and scene_item.subsys is root_block
    ]
    assert len(reopened_items) == 1
    assert len(reopened_items[0].inputs) == 2
    assert len(reopened_items[0].outputs) == 1
    assert len(root_block.diagram.con_data) == original_connection_count
    assert editor.var_factory.get_connections_dict() == dict()

    editor.has_unapplied_changes = False
    editor.close()
    application.processEvents()


def test_manufacturer_native_controller_follows_emt_interface_wrappers() -> None:
    """Compose an OEM child with aliases and consume its remapped runtime map.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()
    circuit: MultiCircuit = MultiCircuit()
    provider: ManufacturerNativeModel = ManufacturerNativeModel(
        name="Qualified PPC provider"
    )
    provider.model_info = b"veragrid-manufacturer-native-model-info-v2\n{}"
    circuit.add_manufacturer_native_model(provider)

    # Every variable participating in template duplication or editor aliases
    # belongs to the same factory that owns the connection graph.
    var_factory: VarFactory = VarFactory()
    source_input: Var = var_factory.add_var(name="ppc_input")
    source_output: Var = var_factory.add_var(name="ppc_output")
    source_controller: ManufacturerNativeControllerLogic = ManufacturerNativeControllerLogic(
        provider_idtag=provider.idtag,
        model_info_sha256=provider.model_info_sha256,
        signal_bindings=(
            IeeeCigreDllSignalBinding(True, 0, 0, source_input),
            IeeeCigreDllSignalBinding(False, 0, 0, source_output),
        ),
        parameter_overrides=tuple(),
        name="PPC controller",
    )
    source_block: Block = Block(
        in_vars=(source_input,),
        out_vars=(source_output,),
        mode_dict={source_output: Const(0.0)},
        name="OEM PPC",
        procedural_logic=(source_controller,),
        is_decomposable=False,
    )
    template: RmsModelTemplate = RmsModelTemplate(name="OEM PPC")
    template.block = source_block

    parent_input: Var = var_factory.add_var(name="plant_measurement")
    parent_output: Var = var_factory.add_var(name="plant_command")
    parent_block: Block = Block(
        in_vars=(parent_input,),
        out_vars=(parent_output,),
        mode_dict={parent_output: Const(0.0)},
        name="Plant controller",
        is_decomposable=True,
    )
    editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=var_factory,
        current_block=parent_block,
        root_block=parent_block,
        api_object=BlockPropertiesApiStub(),
        current_theme="Light",
        mode=DynamicSimulationMode.RMS,
        templates_list=(template,),
        circuit=circuit,
        is_root_editor=False,
        modal=False,
    )
    editor.show()
    application.processEvents()

    child_item_result: graph.BlockItem | graph.GenericBlockItem | None = (
        editor.create_template_block_item(template=template, x_pos=320.0, y_pos=180.0)
    )
    assert isinstance(child_item_result, graph.GenericBlockItem)
    child_item: graph.GenericBlockItem = child_item_result
    child_block: Block = child_item.subsys
    assert child_block is not source_block
    assert child_block.in_vars[0].uid != source_input.uid
    assert child_block.out_vars[0].uid != source_output.uid
    assert child_block.in_vars[0].non_mutable_uid != parent_input.non_mutable_uid
    assert child_block.out_vars[0].non_mutable_uid != parent_output.non_mutable_uid
    original_child_input_uid: int = child_block.in_vars[0].uid
    original_child_output_uid: int = child_block.out_vars[0].uid
    original_child_controller: ManufacturerNativeControllerLogic = child_block.procedural_logic[0]
    assert original_child_controller.signal_bindings[0].get_variable() is child_block.in_vars[0]
    assert original_child_controller.signal_bindings[1].get_variable() is child_block.out_vars[0]
    assert original_child_controller.signal_bindings[0].get_variable().uid == original_child_input_uid
    assert original_child_controller.signal_bindings[1].get_variable().uid == original_child_output_uid

    wrapper_items: list[graph.MeasurementsItem] = [
        scene_item
        for scene_item in editor.scene.items()
        if isinstance(scene_item, graph.MeasurementsItem)
    ]
    input_wrappers: list[graph.MeasurementsItem] = [
        wrapper_item
        for wrapper_item in wrapper_items
        if len(wrapper_item.outputs) == 1
        and wrapper_item.outputs[0].base_var is parent_input
    ]
    output_wrappers: list[graph.MeasurementsItem] = [
        wrapper_item
        for wrapper_item in wrapper_items
        if len(wrapper_item.inputs) == 1
        and wrapper_item.inputs[0].base_var is parent_output
    ]
    assert len(input_wrappers) == 1
    assert len(output_wrappers) == 1

    input_connection: graph.ConnectionItem = graph.ConnectionItem(
        source_port=input_wrappers[0].outputs[0],
        target_port=child_item.inputs[0],
        diagram=editor.diagram,
        editor=editor,
    )
    editor.attach_new_connection_item(item=input_connection)
    controller_after_input: ManufacturerNativeControllerLogic = child_block.procedural_logic[0]
    assert controller_after_input.signal_bindings[0].get_variable() is child_block.in_vars[0]
    assert controller_after_input.signal_bindings[0].get_variable().uid == child_block.in_vars[0].uid
    output_connection: graph.ConnectionItem = graph.ConnectionItem(
        source_port=child_item.outputs[0],
        target_port=output_wrappers[0].inputs[0],
        diagram=editor.diagram,
        editor=editor,
    )
    editor.attach_new_connection_item(item=output_connection)
    editor._add_manufacturer_native_controller_presentations()

    assert len(parent_block.diagram.con_data) == 2
    alias_count: int = sum(
        len(connections)
        for connections in editor.var_factory.get_connections_dict().values()
    )
    assert alias_count == 2
    child_controller: ManufacturerNativeControllerLogic = child_block.procedural_logic[0]
    input_binding: IeeeCigreDllSignalBinding = child_controller.signal_bindings[0]
    output_binding: IeeeCigreDllSignalBinding = child_controller.signal_bindings[1]
    assert input_binding.get_variable() is child_block.in_vars[0]
    assert output_binding.get_variable() is child_block.out_vars[0]
    assert input_binding.get_variable().uid == parent_input.uid
    assert output_binding.get_variable().uid == parent_output.uid
    assert "Provider: Qualified PPC provider" in child_item.toolTip()
    assert "Reference: Valid" in child_item.toolTip()

    # Exercise the existing runtime mapping and publication owners with the
    # exact remapped child binding UIDs produced by the GUI connection path.
    input_signal: ManufacturerNativeSignalInfo = ManufacturerNativeSignalInfo(
        name="ppc_input",
        description="PPC measurement",
        unit="pu",
        data_type=IeeeCigreDllDataType.REAL64,
        width=1,
    )
    output_signal: ManufacturerNativeSignalInfo = ManufacturerNativeSignalInfo(
        name="ppc_output",
        description="PPC command",
        unit="pu",
        data_type=IeeeCigreDllDataType.REAL64,
        width=1,
    )
    model_info: ManufacturerNativeModelInfo = object.__new__(
        ManufacturerNativeModelInfo
    )
    model_info.input_ports = (input_signal,)
    model_info.output_ports = (output_signal,)

    problem: EmtProblemDae = object.__new__(EmtProblemDae)
    problem._uid2idx_vars = {input_binding.get_variable().uid: 0}
    problem._uid2idx_event_params = {output_binding.get_variable().uid: 0}
    problem._uid2idx_params = dict()
    problem._parameters_values = list()
    runtime_session: ManufacturerNativeRuntimeSession = object.__new__(
        ManufacturerNativeRuntimeSession
    )
    runtime_session._problem = problem
    input_sources: tuple[tuple[int, int], ...]
    output_indices: tuple[int, ...]
    input_sources, output_indices = runtime_session._resolve_mapping(
        problem=problem,
        logic=child_controller,
        model_info=model_info,
    )
    runtime_binding: _RuntimeBinding = object.__new__(_RuntimeBinding)
    runtime_binding.input_sources = input_sources
    runtime_binding.output_indices = output_indices
    runtime_input: tuple[int | float, ...] = runtime_session._inputs(
        binding=runtime_binding,
        x=np.asarray((0.75,), dtype=float),
        params=np.asarray((0.0,), dtype=float),
    )
    runtime_parameters: np.ndarray = np.asarray((0.0,), dtype=float)
    runtime_session._publish(
        binding=runtime_binding,
        outputs=(0.42,),
        params=runtime_parameters,
    )
    assert runtime_input == (0.75,)
    assert runtime_parameters.tolist() == [0.42]

    # Exercise the ordinary GUI removal path and require the controller bindings
    # to return to the independent child identities saved before composition.
    editor.remove_connection_item(item=input_connection)
    editor.remove_connection_item(item=output_connection)
    restored_controller: ManufacturerNativeControllerLogic = child_block.procedural_logic[0]
    restored_input_binding: IeeeCigreDllSignalBinding = restored_controller.signal_bindings[0]
    restored_output_binding: IeeeCigreDllSignalBinding = restored_controller.signal_bindings[1]
    assert restored_input_binding.get_variable() is child_block.in_vars[0]
    assert restored_output_binding.get_variable() is child_block.out_vars[0]
    assert restored_input_binding.get_variable().uid == original_child_input_uid
    assert restored_output_binding.get_variable().uid == original_child_output_uid
    assert child_block.in_vars[0].uid == original_child_input_uid
    assert child_block.out_vars[0].uid == original_child_output_uid
    assert len(parent_block.diagram.con_data) == 0
    restored_alias_count: int = sum(
        len(connections)
        for connections in editor.var_factory.get_connections_dict().values()
    )
    assert restored_alias_count == 0

    editor.has_unapplied_changes = False
    editor.close()
    application.processEvents()
